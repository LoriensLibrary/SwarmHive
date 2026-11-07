-- Naive control condition for the Swarm Alignment Hackathon experiments.
-- Same message shape as the bound Hive, but identity is whatever the caller
-- writes in `sender`, there is no trigger, no row-level security, no audit
-- table, and bots may update and delete rows. This reproduces the gap in the
-- original hive_send_message (caller-set sender) so the two conditions can be
-- compared with the same bots and the same prompts.
CREATE SCHEMA IF NOT EXISTS naive;

CREATE TABLE IF NOT EXISTS naive.hive_messages (
  id          bigserial PRIMARY KEY,
  thread_id   text,
  parent_id   bigint,
  sender      text,
  recipient   text,
  subject     text,
  body        text,
  status      text DEFAULT 'posted',
  posted_at   timestamptz DEFAULT now(),
  meta_json   jsonb
);

GRANT USAGE ON SCHEMA naive TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT SELECT, INSERT, UPDATE, DELETE ON naive.hive_messages TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
GRANT USAGE, SELECT ON SEQUENCE naive.hive_messages_id_seq TO bot_researcher, bot_writer, bot_reviewer, bot_intruder;
