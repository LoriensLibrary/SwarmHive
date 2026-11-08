-- Bind the authenticated intake row to the complete runtime seal intent.
-- The legacy four-argument overload remains callable during rollout.
CREATE INDEX IF NOT EXISTS proposals_receipt_lookup_idx
  ON exp.proposals ((payload->>'receipt'))
  WHERE payload ? 'receipt';

CREATE OR REPLACE FUNCTION exp.seal_from_receipt(
  p_receipt text,
  p_expected_author text,
  p_expected_artifact text,
  p_expected_version integer,
  p_expected_body_sha256 text,
  p_deps jsonb DEFAULT '[]'
) RETURNS text
  LANGUAGE plpgsql SECURITY DEFINER
  SET search_path = pg_catalog, exp, pg_temp
AS $fn$
DECLARE
  v_id bigint;
  v_payload jsonb;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role = session_user) THEN
    RAISE EXCEPTION 'only the trusted runtime may seal a receipt'
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF p_receipt IS NULL OR p_receipt !~ '^[a-f0-9]{32,64}$'
     OR p_expected_author IS NULL OR p_expected_author = ''
     OR p_expected_artifact IS NULL OR p_expected_artifact = ''
     OR p_expected_version IS NULL OR p_expected_version < 1
     OR p_expected_body_sha256 IS NULL OR p_expected_body_sha256 !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'receipt, author, exact version and SHA-256 are required'
      USING ERRCODE = 'invalid_parameter_value';
  END IF;

  -- One statement rejects ambiguity in its snapshot. Seal only the exact
  -- primary key it locked, even if another row with this token appears later.
  BEGIN
    SELECT id, payload INTO STRICT v_id, v_payload
      FROM exp.proposals
      WHERE payload ? 'receipt' AND payload->>'receipt' = p_receipt
      FOR UPDATE;
  EXCEPTION
    WHEN no_data_found THEN
      RAISE EXCEPTION 'no proposal matches the receipt' USING ERRCODE = 'invalid_parameter_value';
    WHEN too_many_rows THEN
      RAISE EXCEPTION 'proposal receipt is ambiguous' USING ERRCODE = 'insufficient_privilege';
  END;

  IF jsonb_typeof(v_payload->'artifact_id') IS DISTINCT FROM 'string'
     OR jsonb_typeof(v_payload->'version') IS DISTINCT FROM 'number'
     OR jsonb_typeof(v_payload->'body') IS DISTINCT FROM 'string' THEN
    RAISE EXCEPTION 'proposal must contain a string artifact, numeric version and string body'
      USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF v_payload->>'artifact_id' IS DISTINCT FROM p_expected_artifact
     OR v_payload->>'version' IS DISTINCT FROM p_expected_version::text
     OR encode(sha256(convert_to(v_payload->>'body', 'UTF8')), 'hex') IS DISTINCT FROM p_expected_body_sha256 THEN
    RAISE EXCEPTION 'proposal does not match the expected artifact, version or body digest'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  -- Existing primary-key seal verifies session-bound proposer, reuse, and
  -- dependencies. The locked intake row cannot change between these checks.
  RETURN exp.seal_from_proposal(v_id, p_expected_author, p_deps);
END $fn$;

REVOKE EXECUTE ON FUNCTION exp.seal_from_receipt(text, text, text, integer, text, jsonb)
  FROM PUBLIC, bot_researcher, bot_writer, bot_reviewer, bot_intruder;
