# Adversarial review of the SwarmHive entry (Aelen, 2026-11-07, tree at edc2794)

Written to Angela's instruction: "deep full review of the flaws, tear this project apart, find the issues." Independent of Lorien's pass; the two are merged afterwards. Every item carries a receipt (file and line, or the exact sentence) and the smallest fix or the honest sentence the report needs. Ordered by how much a strong Apart judge would discount the entry.

## Critical: the claim and the evidence do not match

**C1. The experiment never tests the identity property the entry is filed under.**
Receipts: `sql/experiment_schema.sql:261-285` `seal_artifact(p_author, ...)` takes the author as a plain parameter and inserts it as `author_role`; the operator asserts who wrote what. `sql/experiment_schema.sql:93-106` the `bind_author` trigger that bound authorship to the authenticated login is defined and then `DROP TRIGGER`ed, kept "for reference only". `tools/pilot_runner.py:98` the runner opens one connection as `hive_operator` from `secrets/operator.env`; no run, pilot or held-out, ever connects as `bot_researcher`, `bot_writer`, `bot_reviewer` or `bot_intruder`. So every provenance author label in every trace is an operator assertion, and the identity binding in `exp` is exercised only by Lorien's intake checks (proposals trigger, 4/4) and by the pre-existing `hive_*` schema battery, which is declared pre-existing. The README and the draft's section 1 say "identity can be bound below the agent" and file under Track 3 ("identity that holds when agents can rename and copy themselves"). The measured contribution is Track 4: a lineage-gated publication boundary and a reviewer-context comparison.
Fix: either (a) reframe honestly: primary track 4, Track 3 as the substrate it runs on, with one sentence stating that author labels in the experiment are runtime-asserted and identity binding is shown only by the separate containment battery; or (b) make it true: dispatch each stage under its role's login so the seal carries an authenticated author (needs a `seal_for_session` path or a signed dispatch token). (a) fits the time left.

**C2. The "current" arm is not lineage-free; prose citations and the correction notice leak lineage into it.**
Receipts: `tools/pilot_runner.py` `fixture_body()` writes "per `<id>/<ver>`" into every writer body when `prose_names` is true, and `prose_names` defaults to true for every variant except V4; in model mode `wsys` tells the writer "You may mention which source id a figure comes from". The notice delivered to every arm names the withdrawn `id/ver` and its `superseded_by`. A reviewer in the current arm therefore reads: draft A "per S/1", draft B "per S/2", notice "S/1 superseded by S/2". That is claimed lineage plus the answer key. Compact adds authenticated lineage to a baseline that already holds claimed lineage, which is why the lookup control erased the correctness gap and why a strong reviewer will say the design cannot show what it set out to show.
Fix: run the primary families (V6, V1) with `prose_names=False`, or add V6b/V9b with prose names off as the primary and keep the prose variants as "claimed lineage available" diagnostics. State in the report that "current" means current bodies plus whatever lineage the prose and the notice carry.

**C3. There is no lineage-only detection case.** Every stale variant delivers a correction notice. The realistic failure in the motivating incident is the agent that joined after the correction, or never saw the notice. Without a no-notice variant, compact's value cannot be separated from "reading the notice".
Fix: V11 = V6 with `notices=[]` (and optionally V3 without notice). Preregister it; it is the strongest test of authenticated lineage and costs nothing extra to run.

**C4. Sampling is neither controlled nor recorded.** `grep temperature|top_p|seed` across `tools/pilot_runner.py`, `tools/adaption_send.py` and `delivery_recorder.py` finds nothing. Anthropic defaults to temperature 1.0; Adaption's default per model is undocumented. FREEZE.json claims to pin the runtime and model configuration; it does not pin the one parameter that most changes reviewer behavior. Cohorts are then not comparable across providers even in principle.
Fix: set `temperature` explicitly in `dispatch_stage` (it is in the request, so the receipt hashes it), pass it through `adaption_send`, record it in FREEZE and run_summary, and state the value in the report. Pick one value (0 for determinism, or 1.0 to match deployment) and defend it.

**C5. Nobody outside this laptop can run anything.** `tools/pilot_runner.py:22` and `:320` default `LORIEN_REF` to `<home>/Documents/Codex/...`; `delivery_recorder.py` and `score_runs.py` are imported from there and are not in the repository. FREEZE.json hashes those two files, so the freeze references bytes a judge cannot see. `requirements.txt` lists `psycopg` and `anthropic` only. The database is a private Neon branch; the schema can be rebuilt, but the README does not say how to seed roles and the adjudicator row for `exp`.
Fix: vendor `delivery_recorder.py` and `score_runs.py` into `tools/vendor/` with Lorien's attribution and hash the vendored copies; add a `REPRODUCE.md` with the exact role, grant and seed commands and the fresh-branch recipe already used for the 19/19 rebuild.

## High: findings that change what the report may claim

**H1. A 20-line rule beats the model on everything except V10.** The `rule` arm (lineage-only eligibility, no model) completes every stale variant in the dry run and will do so live, because the gate and the rule read the same lineage. If live cohorts confirm it, the honest claim is: authenticated lineage is the mechanism; a model reviewer adds content checking (V10) and nothing else measured here. The draft frames compact memory as the contribution. Rewrite the contribution around the mechanism and position the model as the content layer, with V10 as the evidence for why the model is still needed.

**H2. The gate commits a factually wrong draft.** Dry run, V10: every arm including `rule` approves the eligible-but-wrong draft and `publish_decision` commits it (accepted_bad = 1 in all five arms). The draft's section 3 says accepted bad actions have "expected value zero" under the common gate. That is true only for lineage-detectable staleness. Rewrite: the gate is a lineage boundary; content errors with valid lineage pass it by design, and V10 measures which reviewers catch them.

**H3. Identity is per role, not per agent instance.** `sql/experiment_schema.sql:135` `withdrawn` requires `session_user = author_role`. All writers share the `bot_writer` login, so any writer instance can withdraw any writer's artifact. Copying or renaming an agent inside a role, the exact Track 3 threat, is invisible to the gate. State it plainly in limitations, or add per-instance logins (one role per agent instance, membership in a group role).

**H4. Any bot can stall publication.** `sql/experiment_schema.sql:311` grants `EXECUTE` on `invalidate` to all bots; `:139-143` `contradicted` is accepted from anyone; `:143` then `_enter_fence()` takes `SELECT ... FOR UPDATE` on the singleton and the lock is held until the caller's transaction commits. A bot that opens a transaction, calls `invalidate(x, 1, 'contradicted')` and idles holds the only fence; every publish and every real invalidation blocks behind it. A second bot can spam unbounded `contradicted` rows. This contradicts "tamper-resistant record" in the draft.
Fix: `contradicted` should not enter the fence (it is advisory and never read by the gate); set `idle_in_transaction_session_timeout` and `lock_timeout` on the bot roles; rate-limit or restrict `contradicted`. Add a liveness check to the acceptance suite.

**H5. The adversary is the operator.** Replay (V5) and the wrong draft (V10) are injected by the trusted runner through `_Echo` (`tools/pilot_runner.py`, `inject()`); no bot attempts anything in any experimental run. The traces therefore contain no adversarial agent behavior; the attack evidence is the separate containment battery against the pre-existing `hive_*` schema. Say "harness-injected compromise" everywhere the report says "attack", and keep the battery's results in their own paragraph.

**H6. Template instances inflate precision.** 120 instances per family differ in numbers, item and site only. The variation that intervals describe is model sampling noise at a fixed template, not variation over a task distribution. Report intervals as "over resampling of this template", give the effective design in one sentence, and resist "0/120" as a generalizable rate.

**H7. Lookup is a decision, not a treatment.** In canned mode the reviewer always requests the lookup; a live model may never request it, which collapses `current_lookup` to `current`. Report lookup-requested rate per cohort and analyze intention-to-treat (lookup offered) separately from per-protocol (lookup used).

**H8. The reviewer prompt hands over the answer structure.** `REVIEWER_SYS` says "Never put a rejected or withdrawn artifact in evidence" and the notice says which version supersedes which. Together with C2 and C3 the primary families measure instruction compliance more than detection. Pair with C2/C3 fixes; at minimum describe the prompt in the report and show it in the appendix.

## Medium: things a careful reader will trip over

**M1. Dirty tree for a judge.** `runs/` holds about 25 dry-run directories plus `runs/pilot_4a6b76` (the aborted first Sonnet pilot, max_tokens 300 crash) and `runs/holdout_gemma431bit_d58686` (an empty directory the runner created before the registry refused the simulated rerun). Add `runs/INDEX.md` naming the cited runs, delete or label the rest, and create the output directory after the freeze and registry checks pass.

**M2. Draft errors already identified by Lorien and not yet fixed:** section 4 says "Four variants" for the Sonnet pilot (it was three, V0/V3/V5, nine reviews); section 2 reads 8 failed checks as 8 defects and blurs first-pass 1/9 with later intake and malformed-input findings; "nothing in a single-model safety test would have caught any of it" is unsupported; the 7,905 names figure belongs to Swarm Traces, the 1,200 / 700 / 7% figures to METR; "second independently written implementation verified every property" overstates an acceptance suite that checked specific boundaries; section numbering jumps from 4 to 6; section 5 is a placeholder. Fix all before any judge sees it.

**M3. V10 needs its own outcome.** The scorer counts a correct abstention on V10 as not completed and not bad. Without a "correct abstention" column, V10 reads as universal failure. Add the column in the analysis script (not the scorer): for V10, `completed_correctly` is undefined and `correct_abstention = decision in {reject, revalidate}`.

**M4. parse_json is fragile for reasoning models.** It slices from the first `{` to the last `}`. A model that writes "{thinking...}" prose before its JSON produces `invalid_output`, scored against the arm though it is a harness artifact. Extract the last balanced JSON object instead and keep the raw text (already kept).

**M5. Fixture bodies are formulaic.** "X at Y: n units, per id/ver" repeated 120 times. Fine as a controlled test; say so, and do not call it a realistic workload.

**M6. Shared database state.** All dry runs and all cohorts share one Neon branch; thousands of leftover rows sit beside held-out rows. Prefixes separate them, but a reproduction on a clean branch starts from a different state. Run the held-out cohorts on a fresh branch from the frozen migration (the recipe exists from the 19/19 rebuild) and record the branch id in FREEZE.

**M7. Multiple comparisons.** Five arms, ten variants, seven cohorts is 350 cells. Only the preregistered primary (compact vs lookup on V6 and V1, paired) may be inferential; everything else is descriptive. Say so in the methods, not the limitations.

**M8. Operator concentration is stated but not measured.** The same login seals, adjudicates and publishes, and its DSN sits in plaintext in `secrets/operator.env`. Acceptable for a sprint; the report should say the gate protects against agents, not against the runtime.

## Low: hygiene

**L1.** No test that a fixture mismatch yields error traces with the denominator retained (the path exists; nothing exercises it). Add one tampered-body test.
**L2.** `README.md` still describes only the bound/naive containment experiment; nothing about `exp`, the gate, the runner, the freeze or the cohorts. A judge opening the repo meets the wrong project.
**L3.** `holdout_freeze.py` docstring still describes the old hash coverage.
**L4.** Evaluator-only `names` maps and `task_keys.json` live under `runs/`, where a model process with filesystem access could read them; fine here, state that keys are evaluator-only by convention, not by access control.

## What I would do with the time left, in order

1. Reframe the claim (C1, H1, H2, H5) in the abstract and section 1 before anything else; this is wording, costs nothing, and removes the biggest discount.
2. Add `prose_names=False` primaries and the no-notice V11 (C2, C3); set and freeze temperature (C4). One commit, dry-verified, then re-request Lorien's clearance.
3. Vendor the two reference files and write REPRODUCE.md (C5).
4. Fix the fence liveness hole and add it to the acceptance suite (H4); it is a real finding about the gate and belongs in the report either way.
5. Then the canary, then the cohorts, then the analysis script with paired intervals and the V10 abstention column (H6, H7, M3).
6. Report corrections (M2) with the results.
