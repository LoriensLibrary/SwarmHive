-- Converged experiment schema (Swarm Alignment Hackathon).
-- Immutable artifact versions, operator/runtime-recorded provenance edges,
-- an authority-checked invalidation log, and ONE trusted publication gate.
-- Agents never write approvals or invalidations directly; the only path to an
-- approved artifact is publish_decision(), and the only path to an invalidation
-- is invalidate(), both SECURITY DEFINER with pinned search_path.

CREATE SCHEMA IF NOT EXISTS exp;

-- Immutable artifacts. A correction is a NEW (artifact_id, version), never an
-- overwrite. author_role is bound to the authenticated login by the trigger.
CREATE TABLE IF NOT EXISTS exp.artifacts (
  artifact_id text NOT NULL,
  version     int  NOT NULL,
  author_role text NOT NULL,
  claimed_author text,
  body        text NOT NULL,
  content_hash text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (artifact_id, version)
);

-- Provenance edges: which source (id,version) was DELIVERED as input to a
-- derived (id,version). Recorded by the runtime, not self-asserted as truth.
CREATE TABLE IF NOT EXISTS exp.provenance (
  derived_id   text NOT NULL,
  derived_ver  int  NOT NULL,
  source_id    text NOT NULL,
  source_ver   int  NOT NULL,
  PRIMARY KEY (derived_id, derived_ver, source_id, source_ver)
);

-- Invalidations. epoch is monotonic per artifact_id/version. kind distinguishes
-- the three authorities. Agents cannot write here; only invalidate() can.
CREATE TABLE IF NOT EXISTS exp.invalidations (
  artifact_id text NOT NULL,
  version     int  NOT NULL,
  epoch       int  NOT NULL,
  kind        text NOT NULL CHECK (kind IN ('withdrawn','contradicted','adjudicated')),
  by_role     text NOT NULL,
  at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (artifact_id, version, epoch)
);

-- Approvals. Only publish_decision() inserts here.
CREATE TABLE IF NOT EXISTS exp.approvals (
  artifact_id text NOT NULL,
  version     int  NOT NULL,
  reviewer    text NOT NULL,
  decision    text NOT NULL CHECK (decision IN ('approved','rejected')),
  reason      text,
  at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (artifact_id, version, reviewer, at)
);

-- Adjudicators allowed to issue 'adjudicated' invalidations and act as the
-- trusted reviewer/publication gate. Operator-managed.
CREATE TABLE IF NOT EXISTS exp.adjudicators (role text PRIMARY KEY);

-- Bind artifact author to the authenticated login; keep any claimed name.
CREATE OR REPLACE FUNCTION exp.bind_author() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
BEGIN
  IF NEW.author_role IS DISTINCT FROM session_user THEN
    NEW.claimed_author := NEW.author_role;
  END IF;
  NEW.author_role := session_user;
  RETURN NEW;
END $fn$;
DROP TRIGGER IF EXISTS trg_bind_author ON exp.artifacts;
CREATE TRIGGER trg_bind_author BEFORE INSERT ON exp.artifacts
  FOR EACH ROW EXECUTE FUNCTION exp.bind_author();

-- invalidate(): the ONLY way to write an invalidation. Authority is checked
-- against the authenticated login, not asserted by the caller.
--   withdrawn    : only the artifact's own author may withdraw its own version.
--   adjudicated  : only a role listed in exp.adjudicators.
--   contradicted : any authenticated agent may PROPOSE a contradiction, but it
--                  is advisory and does NOT by itself block publication.
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
  SELECT COALESCE(MAX(epoch),0)+1 INTO v_epoch FROM exp.invalidations WHERE artifact_id=p_id AND version=p_ver;
  INSERT INTO exp.invalidations(artifact_id,version,epoch,kind,by_role)
    VALUES (p_id,p_ver,v_epoch,p_kind,session_user);
  RETURN v_epoch;
END $fn$;

-- publish_decision(): the ONLY path to an approval. In one transaction it
-- re-reads dependency state, requires the attestation to cover EVERY real
-- provenance edge (omitted lineage -> reject, never clean by default), and
-- rejects if any covered dependency has a BLOCKING invalidation (withdrawn or
-- adjudicated) with epoch greater than the epoch the reviewer acknowledged.
-- 'contradicted' is advisory and does not block. Check and commit are one
-- transaction, closing the check-then-approve TOCTOU for a retraction that
-- linearizes before this call.
--   p_attest: jsonb array of {"id":..,"ver":..,"acked_epoch":..} per dependency.
CREATE OR REPLACE FUNCTION exp.publish_decision(p_id text, p_ver int, p_attest jsonb)
  RETURNS text LANGUAGE plpgsql SECURITY DEFINER
  SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
DECLARE r record; a jsonb; acked int; blk int; reason text; bad record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role=session_user) THEN
    RAISE EXCEPTION 'only an adjudicator may publish decisions';
  END IF;
  -- The artifact being published must exist.
  IF NOT EXISTS (SELECT 1 FROM exp.artifacts WHERE artifact_id=p_id AND version=p_ver) THEN
    reason := format('unknown artifact %s/%s', p_id, p_ver);
    INSERT INTO exp.approvals(artifact_id,version,reviewer,decision,reason)
      VALUES (p_id,p_ver,session_user,'rejected',reason);
    RETURN 'rejected: '||reason;
  END IF;
  -- Walk the TRANSITIVE dependency closure, including the artifact itself, and
  -- reject if any node carries a blocking (withdrawn/adjudicated) invalidation.
  -- A direct-only check misses a withdrawn grandparent and a withdrawn self.
  WITH RECURSIVE clo(id,ver) AS (
    SELECT p_id, p_ver
    UNION
    SELECT pr.source_id, pr.source_ver
      FROM exp.provenance pr JOIN clo ON pr.derived_id=clo.id AND pr.derived_ver=clo.ver
  )
  SELECT c.id, c.ver, MAX(i.epoch) AS epoch INTO bad
    FROM clo c JOIN exp.invalidations i
      ON i.artifact_id=c.id AND i.version=c.ver AND i.kind IN ('withdrawn','adjudicated')
    GROUP BY c.id, c.ver LIMIT 1;
  IF bad.id IS NOT NULL THEN
    reason := format('closure member %s/%s invalidated (epoch %s)', bad.id, bad.ver, bad.epoch);
    INSERT INTO exp.approvals(artifact_id,version,reviewer,decision,reason)
      VALUES (p_id,p_ver,session_user,'rejected',reason);
    RETURN 'rejected: '||reason;
  END IF;
  FOR r IN SELECT source_id, source_ver FROM exp.provenance WHERE derived_id=p_id AND derived_ver=p_ver LOOP
    SELECT elem INTO a FROM jsonb_array_elements(p_attest) elem
      WHERE elem->>'id'=r.source_id AND (elem->>'ver')::int=r.source_ver LIMIT 1;
    IF a IS NULL THEN
      reason := format('unacknowledged dependency %s/%s', r.source_id, r.source_ver);
      INSERT INTO exp.approvals(artifact_id,version,reviewer,decision,reason)
        VALUES (p_id,p_ver,session_user,'rejected',reason);
      RETURN 'rejected: '||reason;
    END IF;
    acked := COALESCE((a->>'acked_epoch')::int, 0);
    -- A withdrawn/adjudicated dependency is DEAD and blocks regardless of what
    -- the reviewer acknowledged. acked_epoch only classifies whether the gate
    -- caught it after review (TOCTOU) or the reviewer already knew. Revalidation
    -- requires a NEW clean source version, not a higher acked_epoch. 'contradicted'
    -- is advisory and never blocks here (blocking it would be an availability attack).
    SELECT COALESCE(MAX(epoch),0) INTO blk FROM exp.invalidations
      WHERE artifact_id=r.source_id AND version=r.source_ver AND kind IN ('withdrawn','adjudicated');
    IF blk > 0 THEN
      reason := format('dependency %s/%s invalidated (epoch %s; %s)', r.source_id, r.source_ver, blk,
                       CASE WHEN blk > acked THEN 'after attestation, TOCTOU caught at gate'
                            ELSE 'known at review' END);
      INSERT INTO exp.approvals(artifact_id,version,reviewer,decision,reason)
        VALUES (p_id,p_ver,session_user,'rejected',reason);
      RETURN 'rejected: '||reason;
    END IF;
  END LOOP;
  INSERT INTO exp.approvals(artifact_id,version,reviewer,decision,reason)
    VALUES (p_id,p_ver,session_user,'approved',NULL);
  RETURN 'approved';
END $fn$;

-- Provenance authorization: an edge (derived -> source) may be recorded only by
-- the derived artifact's own author or by an adjudicator (the trusted runtime).
-- Without this, any agent can poison another artifact's lineage, forge edges,
-- or amplify quarantine. source and derived must both already exist (DAG).
CREATE OR REPLACE FUNCTION exp.authz_provenance() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
DECLARE v_author text;
BEGIN
  SELECT author_role INTO v_author FROM exp.artifacts WHERE artifact_id=NEW.derived_id AND version=NEW.derived_ver;
  IF v_author IS NULL THEN RAISE EXCEPTION 'derived artifact %/% does not exist', NEW.derived_id, NEW.derived_ver; END IF;
  IF NOT EXISTS (SELECT 1 FROM exp.artifacts WHERE artifact_id=NEW.source_id AND version=NEW.source_ver) THEN
    RAISE EXCEPTION 'source artifact %/% does not exist', NEW.source_id, NEW.source_ver;
  END IF;
  IF NEW.derived_id=NEW.source_id AND NEW.derived_ver=NEW.source_ver THEN
    RAISE EXCEPTION 'self-dependency not allowed';
  END IF;
  IF session_user <> v_author AND NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role=session_user) THEN
    RAISE EXCEPTION 'only the derived artifact author or an adjudicator may record its provenance'
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NEW;
END $fn$;
DROP TRIGGER IF EXISTS trg_authz_provenance ON exp.provenance;
CREATE TRIGGER trg_authz_provenance BEFORE INSERT ON exp.provenance
  FOR EACH ROW EXECUTE FUNCTION exp.authz_provenance();

-- Grants: agents may create their own artifacts and provenance, may read, may
-- EXECUTE invalidate (authority checked inside), but may NOT write approvals or
-- invalidations directly, and may NOT publish decisions unless an adjudicator.
GRANT USAGE ON SCHEMA exp TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT SELECT, INSERT ON exp.artifacts, exp.provenance TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT SELECT ON exp.invalidations, exp.approvals, exp.adjudicators TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT EXECUTE ON FUNCTION exp.invalidate(text,int,text) TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT EXECUTE ON FUNCTION exp.publish_decision(text,int,jsonb) TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
