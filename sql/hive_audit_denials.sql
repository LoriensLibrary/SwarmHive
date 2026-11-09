-- Make denied attempts visible in the operator audit. Additive; bound board (public schema) only.
--
-- Measured before this migration (report, containment battery): a bot's UPDATE or DELETE on hive_messages and any
-- read of hive_audit were refused by the privilege layer BEFORE any trigger ran, so the audit never saw the attempt;
-- a SELECT on a thread the bot is not party to returned zero rows silently. Three of six attacks left no audit row.
--
-- The fix keeps every effect denied and records the attempt:
--   1. UPDATE/DELETE are GRANTED, so the statement reaches the table; row security (FORCE, no update/delete policy
--      for bots) qualifies zero rows, so nothing changes; an AFTER ... FOR EACH STATEMENT trigger fires anyway
--      (statement triggers fire on zero-row statements) and writes denied_update / denied_delete with the row count.
--   2. hive_audit gets row security and a SELECT grant for bots; its policy calls a logging function that records
--      denied_audit_read once per transaction, with the statement text, and returns false, so the read yields nothing.
--   3. hive_messages' SELECT policy calls a logging function: permitted rows return true; a denied row records
--      denied_read once per transaction with the statement text. Row security quals run on every scanned row, so
--      this records the statement, not the rows (see the test for the honest-read check).
-- Nothing an honest agent does changes: inserts bind as before, reads of own threads return as before.

GRANT UPDATE, DELETE ON public.hive_messages TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;

CREATE OR REPLACE FUNCTION public.hive_log_denied_write() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
DECLARE n int := 0;
BEGIN
  IF session_user = 'hive_operator' THEN RETURN NULL; END IF;
  EXECUTE 'SELECT count(*) FROM old_rows' INTO n;
  INSERT INTO hive_audit(db_role, action, detail)
    VALUES (session_user, 'denied_' || lower(TG_OP), jsonb_build_object('rows_affected', n, 'statement', left(current_query(), 300)));
  RETURN NULL;
END $fn$;
REVOKE EXECUTE ON FUNCTION public.hive_log_denied_write() FROM PUBLIC;

DROP TRIGGER IF EXISTS trg_hive_log_denied_update ON public.hive_messages;
CREATE TRIGGER trg_hive_log_denied_update AFTER UPDATE ON public.hive_messages
  REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION public.hive_log_denied_write();
DROP TRIGGER IF EXISTS trg_hive_log_denied_delete ON public.hive_messages;
CREATE TRIGGER trg_hive_log_denied_delete AFTER DELETE ON public.hive_messages
  REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION public.hive_log_denied_write();

-- once-per-transaction recorder used by the two read policies
CREATE OR REPLACE FUNCTION public.hive_note_denied(p_action text, p_detail jsonb) RETURNS boolean
  LANGUAGE plpgsql SECURITY DEFINER VOLATILE SET search_path = pg_catalog, public, pg_temp AS $fn$
DECLARE tx text := txid_current()::text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM hive_audit WHERE db_role = session_user AND action = p_action AND detail->>'txid' = tx) THEN
    INSERT INTO hive_audit(db_role, action, detail)
      VALUES (session_user, p_action, p_detail || jsonb_build_object('txid', tx, 'statement', left(current_query(), 300)));
  END IF;
  RETURN false;
END $fn$;
REVOKE EXECUTE ON FUNCTION public.hive_note_denied(text, jsonb) FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.hive_select_allowed(p_thread text, p_sender text, p_recipient text) RETURNS boolean
  LANGUAGE plpgsql SECURITY DEFINER VOLATILE SET search_path = pg_catalog, public, pg_temp AS $fn$
BEGIN
  IF session_user = 'hive_operator' OR p_sender = session_user OR p_recipient = session_user OR p_recipient = 'all' THEN RETURN true; END IF;
  RETURN public.hive_note_denied('denied_read', jsonb_build_object('thread', p_thread));
END $fn$;
REVOKE EXECUTE ON FUNCTION public.hive_select_allowed(text, text, text) FROM PUBLIC;

DROP POLICY IF EXISTS msg_select ON public.hive_messages;
CREATE POLICY msg_select ON public.hive_messages FOR SELECT USING (public.hive_select_allowed(thread_id, sender, recipient));

-- the audit itself: a bot's read is accepted at the privilege layer, denied by policy, and recorded
GRANT SELECT ON public.hive_audit TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
ALTER TABLE public.hive_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hive_audit FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_operator ON public.hive_audit;
CREATE POLICY audit_operator ON public.hive_audit FOR ALL USING (session_user = 'hive_operator') WITH CHECK (session_user = 'hive_operator');
DROP POLICY IF EXISTS audit_denied_read ON public.hive_audit;
CREATE POLICY audit_denied_read ON public.hive_audit FOR SELECT
  USING (session_user = 'hive_operator' OR public.hive_note_denied('denied_audit_read', '{}'::jsonb));

-- policy functions are evaluated in the caller's context; the callers are the bots. SECURITY DEFINER does the audit write.
GRANT EXECUTE ON FUNCTION public.hive_select_allowed(text, text, text) TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT EXECUTE ON FUNCTION public.hive_note_denied(text, jsonb) TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
