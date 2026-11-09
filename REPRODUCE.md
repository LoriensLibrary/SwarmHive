# Reproducing the gate checks and the evaluation

Everything below runs from this repository alone. The two reference files written by Lorien are vendored
byte-identically under `tools/vendor/` (see `tools/vendor/NOTICE`); FREEZE.json records their hashes.

## 1. Database

PostgreSQL 17 (we used a Neon branch). Create the operator and the four agent roles with plain SQL so none of
them inherit a superuser-like membership. `secrets/create_roles.sql` is the exact script we ran (passwords
redacted in the public tree; substitute your own):

```
CREATE ROLE hive_operator LOGIN PASSWORD '...';
CREATE ROLE bot_researcher LOGIN PASSWORD '...';
CREATE ROLE bot_writer     LOGIN PASSWORD '...';
CREATE ROLE bot_reviewer   LOGIN PASSWORD '...';
CREATE ROLE bot_intruder   LOGIN PASSWORD '...';
GRANT CREATE ON DATABASE hive TO hive_operator;
```

Connect as `hive_operator` and apply, in one transaction each:

```
psql "$HIVE_OPERATOR_DSN" -1 -f sql/experiment_schema.sql       # the frozen gate (commit d2df880)
psql "$HIVE_OPERATOR_DSN" -1 -f sql/seal_from_proposal.sql      # additive: authenticated authorship via intake
psql "$HIVE_OPERATOR_DSN" -1 -f sql/gate_hardening.sql          # see role-admin note below
psql "$HIVE_OPERATOR_DSN" -1 -f sql/gate_hardening_2.sql        # separate advisory keyspace and receipt tokens
psql "$HIVE_OPERATOR_DSN" -1 -f sql/gate_exact_receipt.sql      # bind exact ID, version, author and body digest
psql "$HIVE_OPERATOR_DSN" -c "INSERT INTO exp.adjudicators(role) VALUES ('hive_operator') ON CONFLICT DO NOTHING;"
```

For a limited operator, run the `ALTER ROLE` statements in `gate_hardening.sql` under the role administrator
and the schema statements under the schema owner. Bot timeouts are session defaults.

Secrets the tools read (never committed): `secrets/operator.env` holding `HIVE_OPERATOR_DSN=postgresql://hive_operator:...@host/hive`,
`secrets/bot_passwords.json` as `{"bot_researcher": "...", "bot_writer": "...", "bot_reviewer": "...", "bot_intruder": "..."}`,
`secrets/anthropic.key` and/or `secrets/adaption.key`.
Set `secrets/branch_operator.env` to a dedicated scratch endpoint distinct from main.
The deterministic checks use unique fixture IDs and retain their rows.

## 2. Gate checks (no model calls)

```
python -I tools/det_tests.py                                   # deterministic gate properties
python -I tools/race_test.py                                   # concurrent publish vs retraction, serialized commits
python -I tools/revocation_test.py                             # Track 3 revocation: grant revoke/restore, NOLOGIN (scratch endpoint)
python -I tools/identity_copies_test.py                         # ten copies, one login: bound vs naive identity count, one revocation
python -I tools/blast_radius_test.py                            # compromised root, 60 descendants three deep: gate vs direct check vs no lineage
python -I tools/audit_denials_test.py --apply                   # applies sql/hive_audit_denials.sql on the scratch endpoint, reruns the six-attack battery, counts audit rows
python -I tools/structural_results.py                           # tables for the report's structural subsection
python -I tools/test_guard.py              # spend guard, fake client
python -I tools/test_guard_adapter.py                          # adapter-path usage accounting
```

Lorien's acceptance driver (`postgres_checks.py --creation-api sealed --cases all`) is vendored at `tools/vendor/postgres_checks.py` (connection strings come from environment variables);
its evidence for each gate revision is under `runs/acceptance/`.

## 3. Dry run of the whole pipeline (database yes, model no)

```
python -I tools/pilot_runner.py --dry-run --upstream fixture --arms current,current_lookup,compact,full,rule --tasks V0,V1,V3,V4,V5,V6,V7,V8,V9,V10,V11
python -I tools/vendor/score_runs.py --tasks runs/<out>/task_keys.json --manifest runs/<out>/manifest.json --traces runs/<out>/traces.jsonl
```

## 4. Frozen evaluation

```
# HIVE_OPERATOR_DSN must explicitly point to the reviewed evaluation branch.
python tools/gate_preflight.py > gate-target.json
python -I tools/holdout_freeze.py --variants V6,V1 --n 120 --seed <seed> --arms current,current_lookup,compact,full,rule \
    --upstream fixture --prose-names off --model gemma-4-31b-it --provider adaption --ceiling <credits> \
    --gate-deployment gate-target.json --out holdout/<name>
# post holdout/<name>/FREEZE.json before executing anything
python -I tools/pilot_runner.py --spec-file holdout/<name>/instances.json --manifest holdout/<name>/manifest.json --split evaluation \
    --upstream fixture --model gemma-4-31b-it --provider adaption --ceiling <credits>
python -I tools/vendor/score_runs.py --tasks runs/<out>/task_keys.json --manifest runs/<out>/manifest.json --traces runs/<out>/traces.jsonl
```

The runner refuses to start if any of instances, manifest order, prompts, recorder, scorer, runner, adapter, gate
SQL, model, provider, rates, context, max_tokens, temperature, lookup mode, upstream mode, authorship, split,
ceiling or the request cap differ from FREEZE.json, and refuses a second paid execution of the same
(freeze_id, cohort) namespace (`runs/REGISTRY.jsonl`).
