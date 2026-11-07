# Swarm test Hive: setup notes

Built 2026-11-02 for the Swarm Alignment Hackathon (Nov 6-8, 2026). This is
infrastructure built BEFORE the sprint window. Per Apart's rules it must be
declared as pre-existing in the README and the report. The experiments, logs,
and report are weekend work.

Test Hive only. It holds no personal data and never touches CAMA memory.db.

## What exists

- Neon project `swarm-test-hive` (id `fragrant-term-54511626`, us-east-1,
  Postgres 17), database `hive`, owner role `hive_operator`.
- Table `hive_messages`, same columns as the local CAMA Hive, plus
  `claimed_sender`. Table `hive_message_receipts`. Table `hive_audit`
  (operator-only).
- Four bot roles created with plain SQL, so they have no `neon_superuser`
  membership and cannot bypass row-level security: `bot_researcher`,
  `bot_writer`, `bot_reviewer`, `bot_intruder`.
- Identity binding, enforced by the database, not by the bots behaving:
  - a BEFORE INSERT trigger overwrites `sender` with the login role
    (`session_user`); if the caller filled in a different sender, the claim
    is kept in `claimed_sender` and a `sender_spoof_attempt` row is written
    to `hive_audit`;
  - row-level security: a bot reads only messages it sent, messages addressed
    to it, or messages to `all`; bots cannot update or delete anything, cannot
    read the audit log, cannot `SET ROLE`, cannot touch the trigger;
  - the operator sees everything.
- `tools/hive_http.py`: a tiny SQL-over-HTTPS client. The connection string is
  never a bot argument; it comes from the environment locally, or from the
  cloud proxy as the `Neon-Connection-String` header.

## Credentials (local only, gitignored)

- `secrets/operator.env`: the operator connection string.
- `secrets/bot_passwords.json`: one password per bot role.
- Connection string shape for a bot:
  `postgresql://<bot>:<password>@ep-summer-paper-bbe7uhtw.c-15.us-east-1.aws.neon.tech/hive?sslmode=require`

## What Angela does at claude.ai/code (I cannot)

One cloud environment per bot. In each environment, add a network secret:

- host: `ep-summer-paper-bbe7uhtw.c-15.us-east-1.aws.neon.tech`
- header: `Neon-Connection-String`
- value: that bot's connection string from `secrets/bot_passwords.json`

The bot's session then sends `POST https://<host>/sql` with a JSON body
`{"query": "...", "params": [...]}` and the proxy attaches the header. The bot
never sees its password, so it cannot swap in another bot's identity. That is
the whole point: identity is bound by the system, not by the model.

Environments to make: `swarm-researcher`, `swarm-writer`, `swarm-reviewer`,
`swarm-intruder`. The `$250` cloud credit expires Nov 5.

## Test results

Second run 2026-11-02 with `python -I tools/spoof_test.py`, over HTTPS, as each bot role (ids differ from the first run because the test rows are re-inserted each run):

```
T1 writer whoami: rows=[{'identity': 'bot_writer'}]
T2 writer posts claiming to be researcher: rows=[{'id': '5', 'sender': 'bot_writer', 'claimed_sender': 'bot_researcher'}]
T3 researcher posts honestly to reviewer: rows=[{'id': '6', 'sender': 'bot_researcher', 'claimed_sender': None}]
T4 intruder reads researcher->reviewer thread: rows=[]
T5 reviewer reads its inbox: rows=[{'id': '3', 'sender': 'bot_writer', 'claimed_sender': 'bot_researcher', 'subject': 'spoof attempt'}, {'id': '4', 'sender': 'bot_researcher', 'claimed_sender': None, 'subject': 'finding'}, {'id': '5', 'sender': 'bot_writer', 'claimed_sender': 'bot_researcher', 'subject': 'spoof attempt'}, {'id': '6', 'sender': 'bot_researcher', 'claimed_sender': None, 'subject': 'finding'}]
T6 writer SET ROLE bot_researcher: DENIED -> permission denied to set role "bot_researcher"
T7 writer edits researcher's message: DENIED -> permission denied for table hive_messages
T8 writer deletes a message: DENIED -> permission denied for table hive_messages
T9 writer reads the audit log: DENIED -> permission denied for table hive_audit
T10 writer disables the trigger: DENIED -> must be owner of table hive_messages
T11 operator reads audit: rows=[{'db_role': 'bot_writer', 'action': 'sender_spoof_attempt', 'detail': '{"thread": "t-spoof-1", "claimed": "bot_researcher"}'}, {'db_role': 'bot_writer', 'action': 'post', 'detail': '{"id": 3, "to": "bot_reviewer", "thread": "t-spoof-1"}'}, {'db_role': 'bot_researcher', 'action': 'post', 'detail': '{"id": 4, "to": "bot_reviewer", "thread": "t-real-1"}'}, {'db_role': 'bot_writer', 'action': 'sender_spoof_attempt', 'detail': '{"thread": "t-spoof-1", "claimed": "bot_researcher"}'}, {'db_role': 'bot_writer', 'action': 'post', 'detail': '{"id": 5, "to": "bot_reviewer", "thread": "t-spoof-1"}'}, {'db_role': 'bot_researcher', 'action': 'post', 'detail': '{"id": 6, "to": "bot_reviewer", "thread": "t-real-1"}'}]
```

The first run of the day failed on T2/T3: the trigger used `current_user`, which inside a SECURITY DEFINER function is the owner, so every post was rewritten to `hive_operator` and the RETURNING clause tripped RLS. Fixed by binding to `session_user` (the login role) everywhere.
