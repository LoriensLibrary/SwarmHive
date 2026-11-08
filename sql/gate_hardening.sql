-- Additive hardening on top of the frozen gate (d2df880) and seal_from_proposal.sql.
-- Findings: Aelen review H4 and Lorien review (2026-11-08 01:12): any bot's ADVISORY 'contradicted' invalidation
-- took the singleton fence lock and held it until the bot's transaction committed, so an idle bot transaction
-- could stall every publication. Also: previously approved outputs stay readable after a later revocation.
--
-- 1. invalidate(): 'contradicted' is advisory (never read by the gate), so it no longer enters the fence.
--    'withdrawn' and 'adjudicated' still serialize against publication exactly as before.
CREATE OR REPLACE FUNCTION exp.invalidate(p_id text, p_ver int, p_kind text)
  RETURNS int LANGUAGE plpgsql SECURITY DEFINER
  SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
DECLARE v_author text; v_epoch int;
BEGIN
  SELECT author_role INTO v_author FROM exp.artifacts WHERE artifact_id=p_id AND version=p_ver;
  IF v_author IS NULL THEN RAISE EXCEPTION 'no such artifact %/%', p_id, p_ver; END IF;
  IF p_kind='withdrawn' AND session_user <> v_author THEN
    RAISE EXCEPTION 'only the author may withdraw its own artifact';
  ELSIF p_kind='adjudicated' AND NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role=session_user) THEN
    RAISE EXCEPTION 'only an adjudicator may adjudicate';
  ELSIF p_kind NOT IN ('withdrawn','adjudicated','contradicted') THEN
    RAISE EXCEPTION 'bad kind %', p_kind;
  END IF;
  IF p_kind <> 'contradicted' THEN
    PERFORM exp._enter_fence();   -- blocking kinds serialize against concurrent publication; advisory ones do not
  END IF;
  SELECT COALESCE(MAX(epoch),0)+1 INTO v_epoch FROM exp.invalidations WHERE artifact_id=p_id AND version=p_ver;
  INSERT INTO exp.invalidations(artifact_id,version,epoch,kind,by_role)
    VALUES (p_id,p_ver,v_epoch,p_kind,session_user);
  RETURN v_epoch;
END $fn$;

-- 2. Session limits on agent roles: an agent cannot hold any lock or idle transaction for long.
ALTER ROLE bot_researcher SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE bot_writer     SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE bot_reviewer   SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE bot_intruder   SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE bot_researcher SET lock_timeout = '5s';
ALTER ROLE bot_writer     SET lock_timeout = '5s';
ALTER ROLE bot_reviewer   SET lock_timeout = '5s';
ALTER ROLE bot_intruder   SET lock_timeout = '5s';
ALTER ROLE bot_researcher SET statement_timeout = '30s';
ALTER ROLE bot_writer     SET statement_timeout = '30s';
ALTER ROLE bot_reviewer   SET statement_timeout = '30s';
ALTER ROLE bot_intruder   SET statement_timeout = '30s';

-- 3. Read-time validity: an approval is only CURRENT while its artifact's closure (including itself) carries no
--    blocking invalidation. Readers that want recovery semantics read this view, not exp.approvals.
CREATE OR REPLACE VIEW exp.current_approvals AS
WITH RECURSIVE clo(root_id, root_ver, id, ver) AS (
  SELECT a.artifact_id, a.version, a.artifact_id, a.version
    FROM exp.approvals a WHERE a.decision = 'approved'
  UNION
  SELECT c.root_id, c.root_ver, p.source_id, p.source_ver
    FROM exp.provenance p JOIN clo c ON p.derived_id = c.id AND p.derived_ver = c.ver
)
SELECT a.artifact_id, a.version, a.reviewer, a.at AS approved_at
  FROM exp.approvals a
 WHERE a.decision = 'approved'
   AND NOT EXISTS (
     SELECT 1 FROM clo c JOIN exp.invalidations i
       ON i.artifact_id = c.id AND i.version = c.ver AND i.kind IN ('withdrawn','adjudicated')
      WHERE c.root_id = a.artifact_id AND c.root_ver = a.version);
GRANT SELECT ON exp.current_approvals TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;

-- 4. Intake: bots may insert ONLY the payload column; ids and timestamps are server-assigned (no chosen primary keys).
REVOKE INSERT ON exp.proposals FROM bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT INSERT (payload) ON exp.proposals TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;

-- 5. The fence fails closed: if its singleton row is ever missing, nothing publishes or invalidates.
CREATE OR REPLACE FUNCTION exp._enter_fence() RETURNS void
  LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
BEGIN
  IF current_setting('transaction_isolation') <> 'read committed' THEN
    RAISE EXCEPTION 'publication requires READ COMMITTED isolation (got %)', current_setting('transaction_isolation')
      USING ERRCODE = '0A000';
  END IF;
  PERFORM 1 FROM exp.fence WHERE run_id = 'singleton' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fence row missing; refusing to proceed' USING ERRCODE = 'P0002'; END IF;
END $fn$;
