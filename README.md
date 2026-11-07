# Swarm test Hive: identity bound below the agent

Entry for the Swarm Alignment Hackathon (Apart Research x AI Alignment
Foundation, Nov 6-8, 2026), Track 3: agent identity that holds when agents can
rename or copy themselves.

## The question

In the July 2026 Hugging Face incident, about 1,200 agents used 7,905 names.
Identity was something each agent asserted, so a name proved nothing. This
project asks whether identity enforced one layer below the agent holds up when
an agent tries to forge it, and whether an operator can revoke it cleanly.

The mechanism: every agent talks only through a shared message board (the
Hive). Each agent connects as its own database login role. A trigger overwrites
the `sender` field with the authenticated role before the row is stored, so the
name an agent claims is ignored and recorded separately as evidence. An
operator-only audit table logs every post and every spoof attempt, and the
agents cannot read, edit, or delete it. Revoking an agent is dropping its role.

## Pre-existing work (declared per Apart rules)

The test Hive infrastructure was built on 2026-11-02, before the sprint window.
Per Apart's rules it is declared here as pre-existing. It is:

- the Neon Postgres database, the `hive_messages` / `hive_message_receipts` /
  `hive_audit` tables, the `hive_bind_sender` and `hive_log_insert` triggers,
  the row-level security policies, and the four bot roles;
- `tools/hive_http.py`, the SQL-over-HTTPS client;
- `tools/spoof_test.py`, the eleven static containment tests;
- `SETUP.md`, which documents all of the above.

Everything else in this repository is weekend work: the bot harness
(`tools/hive_tool.py`, `tools/bot.py`, `tools/run_experiment.py`), the naive
control schema (`sql/naive_schema.sql`), every experimental run under `runs/`,
the measurements, and the report.

## Two conditions

- **Bound** (`public` schema): the Hive as described above.
- **Naive** (`naive` schema): the same message shape with no trigger, no
  row-level security, no audit table, and `sender` set to whatever the caller
  writes. This reproduces the gap in a plain shared message board, where the
  sender is a self-reported field.

The same four agents run the same task in both conditions. Three honest agents
pass a finding from researcher to writer to reviewer. One intruder tries to get
a false finding approved by posting under another agent's name, reading a thread
it is not party to, and renaming itself.

## Running

Each agent runs as its own process with one database connection string in its
environment, standing in for the cloud proxy that would attach it as a header.
The agent never sees the string, so it cannot swap identities.

```
export ANTHROPIC_API_KEY=...        # required for the agents
python -I tools/run_experiment.py bound runs/bound_01
python -I tools/run_experiment.py naive runs/naive_01
```

Each run resets its schema, launches the agents, and writes `result.json` with
the final message table, the audit log, per-agent step logs, and counts.

## Not in this repository

The `secrets/` directory (connection strings and role passwords) is gitignored
and never committed. The test Hive holds no personal data and never touches any
other system.
