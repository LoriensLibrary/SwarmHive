-- Additive hardening 2 (Lorien 2026-11-08 01:33/01:37, reproduced live with pg_blocking_pids on the scratch branch).
--
-- (1) ADVISORY KEYSPACE. 'contradicted' rows lived in exp.invalidations with the same unique (artifact_id, version,
--     epoch) key as blocking kinds. An UNCOMMITTED advisory at epoch 1 followed by a blocking withdrawal of the same
--     version made the withdrawal take the fence and then wait on the advisory's unique index; an unrelated publish
--     then waited behind the fence. Advisories now live in their own table with a server-assigned key, so no
--     advisory write can ever sit on the blocking path. The gate and the current_approvals view read only
--     exp.invalidations, as before.
CREATE TABLE IF NOT EXISTS exp.advisories (
  id          bigserial PRIMARY KEY,
  artifact_id text NOT NULL,
  version     int  NOT NULL,
  by_role     text NOT NULL,
  at          timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON exp.advisories TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;

CREATE OR REPLACE FUNCTION exp.invalidate(p_id text, p_ver int, p_kind text)
  RETURNS int LANGUAGE plpgsql SECURITY DEFINER
  SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
DECLARE v_author text; v_epoch int; v_id bigint;
BEGIN
  SELECT author_role INTO v_author FROM exp.artifacts WHERE artifact_id=p_id AND version=p_ver;
  IF v_author IS NULL THEN RAISE EXCEPTION 'no such artifact %/%', p_id, p_ver; END IF;
  IF p_kind='contradicted' THEN
    -- advisory: own table, own key, no fence, never read by the gate
    INSERT INTO exp.advisories(artifact_id,version,by_role) VALUES (p_id,p_ver,session_user) RETURNING id INTO v_id;
    RETURN v_id::int;
  ELSIF p_kind='withdrawn' AND session_user <> v_author THEN
    RAISE EXCEPTION 'only the author may withdraw its own artifact';
  ELSIF p_kind='adjudicated' AND NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role=session_user) THEN
    RAISE EXCEPTION 'only an adjudicator may adjudicate';
  ELSIF p_kind NOT IN ('withdrawn','adjudicated') THEN
    RAISE EXCEPTION 'bad kind %', p_kind;
  END IF;
  PERFORM exp._enter_fence();   -- blocking kinds serialize against concurrent publication
  SELECT COALESCE(MAX(epoch),0)+1 INTO v_epoch FROM exp.invalidations WHERE artifact_id=p_id AND version=p_ver;
  INSERT INTO exp.invalidations(artifact_id,version,epoch,kind,by_role)
    VALUES (p_id,p_ver,v_epoch,p_kind,session_user);
  RETURN v_epoch;
END $fn$;
-- Advisory rows written before this migration stay in exp.invalidations as history; the gate never read them.

-- (2) EXACT PROPOSAL RECEIPT. DB.propose selected "the latest unsealed proposal for artifact/version", which a
--     same-role session could race with a substitute body. The runtime now generates a receipt token per dispatch;
--     the agent's own session inserts it inside the payload; the operator seals ONLY the row carrying that token,
--     from the expected author, with the expected body hash and an integer version. Nothing is matched by position.
CREATE OR REPLACE FUNCTION exp.seal_from_receipt(p_receipt text, p_expected_author text, p_expected_body_sha256 text, p_deps jsonb DEFAULT '[]')
  RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
DECLARE v_id bigint; v_proposer text; v_payload jsonb; v_sealed text; v_aid text; v_ver int; v_body text; v_kind text; v_n int;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role=session_user) THEN
    RAISE EXCEPTION 'only the trusted runtime (adjudicator) may seal artifacts' USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF p_receipt IS NULL OR length(p_receipt) < 16 THEN RAISE EXCEPTION 'receipt token required' USING ERRCODE = '22023'; END IF;
  SELECT count(*) INTO v_n FROM exp.proposals WHERE payload->>'receipt' = p_receipt;
  IF v_n = 0 THEN RAISE EXCEPTION 'no proposal carries receipt %', left(p_receipt, 8); END IF;
  IF v_n > 1 THEN RAISE EXCEPTION 'receipt % is ambiguous (% rows); refusing', left(p_receipt, 8), v_n USING ERRCODE = 'insufficient_privilege'; END IF;
  SELECT id, proposer, payload, sealed_as INTO v_id, v_proposer, v_payload, v_sealed
    FROM exp.proposals WHERE payload->>'receipt' = p_receipt FOR UPDATE;
  IF v_sealed IS NOT NULL THEN RAISE EXCEPTION 'proposal % already sealed as %', v_id, v_sealed USING ERRCODE = 'unique_violation'; END IF;
  IF p_expected_author IS NULL OR p_expected_author <> v_proposer THEN
    RAISE EXCEPTION 'authenticated proposer % does not match the runtime''s expected author %', v_proposer, p_expected_author
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF jsonb_typeof(v_payload->'version') IS DISTINCT FROM 'number' OR jsonb_typeof(v_payload->'artifact_id') IS DISTINCT FROM 'string'
     OR jsonb_typeof(v_payload->'body') IS DISTINCT FROM 'string' THEN
    RAISE EXCEPTION 'proposal payload must carry artifact_id (string), version (number) and body (string)' USING ERRCODE = '22023';
  END IF;
  v_aid := v_payload->>'artifact_id'; v_body := v_payload->>'body';
  IF (v_payload->'version')::numeric <> trunc((v_payload->'version')::numeric) OR (v_payload->'version')::numeric < 1 THEN
    RAISE EXCEPTION 'version must be a positive integer' USING ERRCODE = '22023';
  END IF;
  v_ver := (v_payload->'version')::int;
  IF encode(sha256(convert_to(v_body,'UTF8')),'hex') <> p_expected_body_sha256 THEN
    RAISE EXCEPTION 'proposal body hash does not match the runtime''s dispatch receipt' USING ERRCODE = 'insufficient_privilege';
  END IF;
  v_kind := exp.seal_artifact(v_proposer, v_aid, v_ver, v_body, p_deps);
  UPDATE exp.proposals SET sealed_as = v_aid || '/' || v_ver, sealed_at = now() WHERE id = v_id;
  RETURN v_kind;
END $fn$;
REVOKE EXECUTE ON FUNCTION exp.seal_from_receipt(text, text, text, jsonb) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION exp.seal_from_receipt(text, text, text, jsonb) FROM bot_researcher, bot_writer, bot_reviewer, bot_intruder;
-- seal_from_proposal(bigint, text, jsonb) remains for reference; the runner no longer calls it.
