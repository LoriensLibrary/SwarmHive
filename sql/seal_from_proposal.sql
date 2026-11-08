-- Additive migration on top of the frozen gate (d2df880): authenticated authorship through the intake.
--
-- Review finding C1 (report/REVIEW_aelen_2026-11-07.md): seal_artifact(p_author, ...) takes the author as a
-- parameter the operator asserts, so no experimental run ever tested identity binding. This path closes that:
--   1. the agent, connected as ITS OWN login role, INSERTs its output into exp.proposals; trg_bind_proposer
--      overwrites proposer with session_user, so a claimed name is ignored;
--   2. the trusted runtime (an adjudicator) calls seal_from_proposal(proposal_id, expected_author, deps):
--      the author written into exp.artifacts is the AUTHENTICATED proposer of that row, never a parameter;
--      the dependencies are the runtime's delivered inputs from the dispatch receipt, never the agent's claim;
--      a mismatch between the runtime's expectation and the authenticated proposer raises (spoof or mislabel).
-- Nothing existing is altered: seal_artifact, publish_decision, invalidate and the triggers are unchanged.

ALTER TABLE exp.proposals ADD COLUMN IF NOT EXISTS sealed_as text;          -- '<artifact_id>/<version>' once sealed
ALTER TABLE exp.proposals ADD COLUMN IF NOT EXISTS sealed_at timestamptz;

CREATE OR REPLACE FUNCTION exp.seal_from_proposal(p_proposal bigint, p_expected_author text, p_deps jsonb DEFAULT '[]')
  RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
DECLARE v_proposer text; v_payload jsonb; v_id text; v_ver int; v_body text; v_kind text; v_sealed text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role=session_user) THEN
    RAISE EXCEPTION 'only the trusted runtime (adjudicator) may seal artifacts' USING ERRCODE = 'insufficient_privilege';
  END IF;
  SELECT proposer, payload, sealed_as INTO v_proposer, v_payload, v_sealed
    FROM exp.proposals WHERE id = p_proposal FOR UPDATE;
  IF v_proposer IS NULL THEN RAISE EXCEPTION 'no such proposal %', p_proposal; END IF;
  IF v_sealed IS NOT NULL THEN RAISE EXCEPTION 'proposal % already sealed as %', p_proposal, v_sealed USING ERRCODE = 'unique_violation'; END IF;
  IF p_expected_author IS NOT NULL AND p_expected_author <> v_proposer THEN
    RAISE EXCEPTION 'authenticated proposer % does not match the runtime''s expected author %', v_proposer, p_expected_author
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  v_id := v_payload->>'artifact_id'; v_ver := (v_payload->>'version')::int; v_body := v_payload->>'body';
  IF v_id IS NULL OR v_ver IS NULL OR v_body IS NULL THEN
    RAISE EXCEPTION 'proposal payload must carry artifact_id, version and body' USING ERRCODE = '22023';
  END IF;
  -- Author = authenticated proposer. Dependencies = runtime truth (p_deps), validated by seal_artifact.
  v_kind := exp.seal_artifact(v_proposer, v_id, v_ver, v_body, p_deps);
  UPDATE exp.proposals SET sealed_as = v_id || '/' || v_ver, sealed_at = now() WHERE id = p_proposal;
  RETURN v_kind;
END $fn$;

REVOKE EXECUTE ON FUNCTION exp.seal_from_proposal(bigint, text, jsonb) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION exp.seal_from_proposal(bigint, text, jsonb)
  FROM bot_researcher, bot_writer, bot_reviewer, bot_intruder;
-- Bots already hold INSERT on exp.proposals and USAGE on its sequence (frozen gate grants). They need nothing else.
