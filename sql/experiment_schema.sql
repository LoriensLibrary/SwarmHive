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
  kind        text,                 -- 'root' | 'derivative'; NULL = unsealed/unknown lineage (ineligible)
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (artifact_id, version)
);
ALTER TABLE exp.artifacts ADD COLUMN IF NOT EXISTS kind text;
ALTER TABLE exp.artifacts DROP CONSTRAINT IF EXISTS artifacts_kind_chk;
ALTER TABLE exp.artifacts ADD CONSTRAINT artifacts_kind_chk CHECK (kind IS NULL OR kind IN ('root','derivative'));

-- Untrusted intake. Bots may only PROPOSE here; nothing in proposals is
-- authoritative. A trusted runtime reads proposals and seals artifacts.
CREATE TABLE IF NOT EXISTS exp.proposals (
  id          bigserial PRIMARY KEY,
  proposer    text NOT NULL DEFAULT session_user,
  submitted_at timestamptz NOT NULL DEFAULT now(),
  payload     jsonb NOT NULL
);
-- Bind proposer to the authenticated login; a caller-supplied proposer is a spoof.
CREATE OR REPLACE FUNCTION exp.bind_proposer() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
BEGIN
  NEW.proposer := session_user;
  NEW.submitted_at := now();
  RETURN NEW;
END $fn$;
DROP TRIGGER IF EXISTS trg_bind_proposer ON exp.proposals;
CREATE TRIGGER trg_bind_proposer BEFORE INSERT ON exp.proposals
  FOR EACH ROW EXECUTE FUNCTION exp.bind_proposer();

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

-- Serialization fence. publish_decision() and every blocking invalidation take
-- SELECT ... FOR UPDATE on this singleton row before any state check and hold it
-- through COMMIT, so a publication and a retraction cannot interleave. Singleton
-- is a serial correctness reference, not a throughput design (per-source locking
-- is a later optimization once the graph closure is sealed).
CREATE TABLE IF NOT EXISTS exp.fence (run_id text PRIMARY KEY);
INSERT INTO exp.fence(run_id) VALUES ('singleton') ON CONFLICT DO NOTHING;

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
-- The bind_author trigger belonged to the old interface where agents inserted
-- their own artifacts. Agents no longer write exp.artifacts at all; seal_artifact
-- is the sole creator and carries the true author from the trusted dispatch
-- context, so the trigger is removed (it would otherwise relabel every sealed
-- artifact as the operator). Kept the function body for reference only.
DROP TRIGGER IF EXISTS trg_bind_author ON exp.artifacts;

-- Enter the serialization fence: require READ COMMITTED (so the post-lock state
-- check sees the latest committed state, not a fixed pre-withdrawal snapshot) and
-- take the singleton row lock, held until the caller commits. Raises 0A000 under
-- any other isolation level, which the acceptance driver recognizes.
CREATE OR REPLACE FUNCTION exp._enter_fence() RETURNS void
  LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
BEGIN
  IF current_setting('transaction_isolation') <> 'read committed' THEN
    RAISE EXCEPTION 'serialization fence requires READ COMMITTED isolation' USING ERRCODE = '0A000';
  END IF;
  PERFORM 1 FROM exp.fence WHERE run_id = 'singleton' FOR UPDATE;
END $fn$;

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
  PERFORM exp._enter_fence();   -- serialize against concurrent publication
  SELECT COALESCE(MAX(epoch),0)+1 INTO v_epoch FROM exp.invalidations WHERE artifact_id=p_id AND version=p_ver;
  INSERT INTO exp.invalidations(artifact_id,version,epoch,kind,by_role)
    VALUES (p_id,p_ver,v_epoch,p_kind,session_user);
  RETURN v_epoch;
END $fn$;

-- publish_decision(): the ONLY path to an approval. What it actually enforces,
-- stated honestly (not "independent reviewer attestation"):
--   1. caller is an adjudicator (the trusted runtime);
--   2. the artifact exists and is sealed (kind set) -- unknown lineage is ineligible;
--   3. NO member of the transitive dependency closure, the artifact included, carries
--      a withdrawn/adjudicated invalidation (the authoritative eligibility check);
--   4. the operator-supplied acknowledgment list covers every DIRECT provenance edge
--      (an operator acknowledgment that it saw the recorded direct inputs, NOT a
--      model/reviewer attestation to the full history or to specific revisions).
-- Check and commit are one fenced transaction, so a retraction that linearizes
-- before this call is seen (step 3) and one that linearizes after leaves a
-- reconcilable superseded state. 'contradicted' is advisory and never blocks.
-- NOTE: acked_epoch was removed. It never changed a decision: step 3 already
-- rejects any blocking invalidation in the closure, which supersedes any
-- per-edge epoch comparison. A real independent attestation (binding artifact
-- version + full dependency snapshot, computed independently of the model) is
-- future work; it is NOT claimed here.
--   p_attest: jsonb array of {"id":..,"ver":..} naming each acknowledged direct edge.
CREATE OR REPLACE FUNCTION exp.publish_decision(p_id text, p_ver int, p_attest jsonb)
  RETURNS text LANGUAGE plpgsql SECURITY DEFINER
  SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
DECLARE r record; reason text; bad record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role=session_user) THEN
    RAISE EXCEPTION 'only an adjudicator may publish decisions';
  END IF;
  PERFORM exp._enter_fence();   -- serialize against concurrent withdrawal; READ COMMITTED required
  -- The artifact being published must exist.
  IF NOT EXISTS (SELECT 1 FROM exp.artifacts WHERE artifact_id=p_id AND version=p_ver) THEN
    reason := format('unknown artifact %s/%s', p_id, p_ver);
    INSERT INTO exp.approvals(artifact_id,version,reviewer,decision,reason)
      VALUES (p_id,p_ver,session_user,'rejected',reason);
    RETURN 'rejected: '||reason;
  END IF;
  -- Unknown lineage is ineligible: only a sealed artifact (kind set by the
  -- trusted runtime) can be published.
  IF (SELECT kind FROM exp.artifacts WHERE artifact_id=p_id AND version=p_ver) IS NULL THEN
    reason := format('artifact %s/%s has unknown lineage (not sealed)', p_id, p_ver);
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
  -- Step 4: the operator-supplied acknowledgment list must name every DIRECT
  -- recorded input. (Per-edge invalidation checks were removed here: step 3
  -- already rejects any blocking invalidation anywhere in the closure.)
  FOR r IN SELECT source_id, source_ver FROM exp.provenance WHERE derived_id=p_id AND derived_ver=p_ver LOOP
    IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p_attest) elem
                   WHERE elem->>'id'=r.source_id AND (elem->>'ver')::int=r.source_ver) THEN
      reason := format('unacknowledged dependency %s/%s', r.source_id, r.source_ver);
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

-- seal_artifact(): the ONLY creator of authoritative artifacts. The trusted
-- runtime calls it, carrying the true author from the authenticated submission
-- context. It creates the artifact AND its complete input edges in one
-- transaction, sealing a root (no deps) or derivative (nonempty deps). Edges may
-- point only to already-sealed, pre-existing sources, which blocks late edges
-- and cycles. Bots cannot call it and cannot write artifacts/provenance at all.
-- Delivered-input lineage is conservative: it records which inputs were supplied,
-- not that a hidden source was excluded or that an input was actually used.
CREATE OR REPLACE FUNCTION exp.seal_artifact(p_author text, p_id text, p_ver int, p_body text, p_deps jsonb DEFAULT '[]')
  RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, exp, public, pg_temp AS $fn$
DECLARE d jsonb; n int; v_kind text; max_deps int := 32;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM exp.adjudicators WHERE role=session_user) THEN
    RAISE EXCEPTION 'only the trusted runtime (adjudicator) may seal artifacts' USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF p_author IS NULL OR p_author = '' THEN RAISE EXCEPTION 'author required'; END IF;
  IF EXISTS (SELECT 1 FROM exp.artifacts WHERE artifact_id=p_id AND version=p_ver) THEN
    RAISE EXCEPTION 'immutable artifact %/% already exists', p_id, p_ver USING ERRCODE = 'unique_violation';
  END IF;
  IF p_deps IS NULL OR jsonb_typeof(p_deps) IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION 'deps must be a json array' USING ERRCODE = '22023';  -- invalid_parameter_value
  END IF;
  n := jsonb_array_length(p_deps);
  IF n > max_deps THEN RAISE EXCEPTION 'dependency limit % exceeded', max_deps; END IF;
  v_kind := CASE WHEN n = 0 THEN 'root' ELSE 'derivative' END;
  FOR d IN SELECT value FROM jsonb_array_elements(p_deps) AS t(value) LOOP
    IF (d->>'id') = p_id AND (d->>'ver')::int = p_ver THEN RAISE EXCEPTION 'self-dependency not allowed'; END IF;
    IF NOT EXISTS (SELECT 1 FROM exp.artifacts WHERE artifact_id=d->>'id' AND version=(d->>'ver')::int AND kind IS NOT NULL) THEN
      RAISE EXCEPTION 'dependency %/% must already exist and be sealed', d->>'id', d->>'ver';
    END IF;
  END LOOP;
  INSERT INTO exp.artifacts(artifact_id,version,author_role,body,content_hash,kind)
    VALUES (p_id,p_ver,p_author,p_body,encode(sha256(convert_to(p_body,'UTF8')),'hex'),v_kind);
  FOR d IN SELECT value FROM jsonb_array_elements(p_deps) AS t(value) LOOP
    INSERT INTO exp.provenance(derived_id,derived_ver,source_id,source_ver)
      VALUES (p_id,p_ver,d->>'id',(d->>'ver')::int);
  END LOOP;
  RETURN v_kind;
END $fn$;

-- Grants. Agents may READ the authoritative tables and PROPOSE through intake,
-- may EXECUTE invalidate (authority checked inside), but may NOT write artifacts,
-- provenance, invalidations or approvals directly, may NOT seal, and may NOT
-- publish (the gate rejects non-adjudicators). The trusted runtime (operator,
-- an adjudicator) is the sole writer of authoritative state.
GRANT USAGE ON SCHEMA exp TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
REVOKE INSERT, UPDATE, DELETE ON exp.artifacts, exp.provenance FROM bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT SELECT ON exp.artifacts, exp.provenance, exp.invalidations, exp.approvals, exp.adjudicators TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT INSERT ON exp.proposals TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT USAGE, SELECT ON SEQUENCE exp.proposals_id_seq TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
-- Function ACL: PostgreSQL grants EXECUTE to PUBLIC by default, which would let
-- a bot call internal helpers directly (e.g. take the fence lock, or call seal).
-- Revoke PUBLIC from every exp function, then grant back ONLY the two intended
-- agent entry points. The SECURITY DEFINER functions call the internal helpers
-- as the owner, so revoking PUBLIC does not break their internal use.
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA exp FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION exp._enter_fence(), exp.seal_artifact(text,text,int,text,jsonb)
  FROM bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT EXECUTE ON FUNCTION exp.invalidate(text,int,text) TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT EXECUTE ON FUNCTION exp.publish_decision(text,int,jsonb) TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
