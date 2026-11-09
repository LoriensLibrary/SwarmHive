# SwarmHive: a lineage-gated publication boundary for agent swarms

Entry for the Swarm Alignment Hackathon (Apart Research x AI Alignment Foundation, Nov 6-8, 2026).
Measured contribution: Track 4 evaluation of a publication gate that re-reads authenticated lineage inside one
fenced transaction, with a preregistered matched reviewer comparison (six arms, three families, n = 60 each) across
five open models: 5,400 registered slots, 428 unsafe proposals, 0 unsafe commits, every approval row on the
evaluation branch accounted for. Substrate: Track 3 identity bound to the database login below the agent,
exercised in every run through the intake (`sql/seal_from_proposal.sql`).

Start here: `report/REPORT.pdf` (the submitted report; `report/REPORT.md` is its source, assembled by
`tools/assemble_report.py` from `report/DRAFT.md`), `REPRODUCE.md` (run everything from this repo),
`report/REVIEW_aelen_2026-11-07.md` (adversarial review with receipts), `sql/experiment_schema.sql` (the gate,
frozen at d2df880) and `tools/pilot_runner.py` (matched arms, frozen held-out runner, spend guard).
Every number in the report regenerates from the committed traces: `tools/analysis.py`, `tools/results_tables.py`,
`tools/write_section5.py`. Held-out cohorts live under `runs/holdout_heldout_*` and `runs/holdout_diag_*`;
freeze records under `holdout/heldout_v1/`. Post-hoc follow-up cohorts (mandatory lookup; independent DeepSeek V6 replication) are under `holdout/heldout_v2/` and `runs/holdout_v2_*`, labeled post-hoc in the report. Deterministic structural tests, no model calls: `tools/revocation_test.py`, `tools/identity_copies_test.py`, `tools/blast_radius_test.py`, and `tools/audit_denials_test.py` with `sql/hive_audit_denials.sql` (post-evaluation migration that makes denied attempts visible in the audit).
The section below describes the pre-sprint containment battery that this work builds on.

---

# Pre-sprint containment battery: identity bound below the agent

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
