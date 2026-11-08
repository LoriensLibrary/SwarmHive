# Held-out evaluation: preregistration (draft for Lorien's review, 2026-11-07 late evening EST)

Written after the nine-case development canary (seven models, 378 registered slots, 0.468 credits) and before any held-out freeze. Everything below is fixed before the first held-out call; any change afterwards is a new evaluation version with its own freeze id.

## 1. Claim under test

Under a trusted runtime that seals every artifact with its delivered inputs and a publication gate that re-reads the full lineage closure, a reviewer given authenticated lineage **preloaded** in its context (compact) reaches correct publication at least as often as a reviewer that may **fetch** the same lineage on demand (current plus one lookup), and does so with fewer model calls and tokens. Correctness advantage over the lookup arm is not claimed; the canary already shows the lookup arm is used in a minority of offers (17 of 63), so the preregistered primary is intention-to-treat: lookup offered, whether or not used.

Secondary, descriptive: the no-lineage arm (current) as a diagnostic floor; the full-history arm as a ceiling; the two deterministic arms (rule, rule_content) as the lineage-only and lineage-plus-figure references, which bound what a model can add.

## 2. Design

- **Families (primary):** V6 same-number authority change (stale and fresh drafts byte-identical, only lineage differs), V11 the same with no correction notice delivered to the reviewer (lineage is the only signal), V1 false-quarantine control (an unrelated correction before review; the queued draft is clean). All with `prose_names=off`, fixture upstream (identical presealed bodies across providers), authenticated authorship through the intake.
- **Diagnostics (separate freeze, descriptive):** V0, V3, V4, V5, V7, V8, V9, V10, at smaller n, on three models.
- **Arms:** current, current_lookup, compact, full, rule, rule_content. Order randomized per instance, identical across arms within the block; queue order counterbalanced per instance.
- **n:** 60 instances per primary family per model (180 instances, 1080 runs, at most 900 provider requests per model). Chosen by dry-running the preregistered test on synthetic data (`tools/analysis.py --synthetic`): with all-tie results and the Holm-worst alpha of 0.05/6, the one-sided score lower bound is -0.125 at n = 40 (outside the margin) and -0.087 at n = 60 (inside it). Sixty is therefore the smallest round size at which a clean tie can establish non-inferiority; it is not a power guarantee for any effect. Instances are template draws differing in figures, item and site; intervals describe resampling of this template, not a task distribution. The frozen task order **interleaves the three families round-robin**, so a cumulative budget stop late in a cohort cannot remove one whole family.
- **Models:** the seven Adaption-hosted open models from the canary, each its own cohort, never pooled. Claude Sonnet 5.5 as a separate provider cohort under its own USD ceiling if time permits.
- **Output budget:** one uniform `max_output_tokens` for every model and arm, frozen. Proposed 6000. Reasoning tokens recorded per call. A provider stop at the budget is `invalid_output` in its registered slot, reason `output_budget_exhausted` when the answer text is empty.
- **Sampling:** temperature 0.0 on every request, frozen. Retries 0. One request in flight per cohort.

## 3. Model inclusion rule (protocol reliability, never efficacy)

A model enters the held-out set only if, in a budget canary at the frozen output budget of 6000 (nine matched cases, six arms, same freeze shape as the development canary, run for **all seven models including gemma-4-31b-it**, since the budget itself changed), **at least 33 of its 36 model-reviewed slots return a valid structured reply** (parseable, allowlisted selection, typed result). Models below the threshold are reported as excluded for protocol reliability with their canary numbers, not dropped silently. The rule is applied before any held-out result exists and ignores which arm did better.

At the 1,200-token budget the development canary gave 36 of 36 valid for gemma-4-31b-it, 30 of 36 for gemma-4-26b-a4b-it, and 11 to 21 of 36 for the five reasoning models. Of the 108 replies that stopped at the cap, 101 were empty and 7 were partial text. The attribution of the empty replies to the reasoning channel is an **inference**: the adapter in use did not archive the provider's reasoning-token details. The adapter now records `reasoning_tokens`, the provider's `incomplete_details.reason`, and whether the answer text was empty, so the budget canary measures this directly.

### 3a. Outcome of the budget canary and the resulting tiers (applied 2026-11-08 04:43Z, before any held-out freeze)

Valid model-reviewed slots of 36 at the 6000 budget: gemma-4-31b-it 36, deepseek-v4-flash 34, qwen3.5-397b 31, qwen3.8-27b 30, gemma-4-26b-a4b-it 30, glm-53-flash 1, glm-5.2 0 (both settled replies spent all 6000 output tokens on reasoning; the rest were provider HTTP 504 or guard-stopped). Nineteen HTTP 504 gateway timeouts occurred before the 240 s transport timeout; each kept its full reserve as unresolved. 504 and guard-stop are reported as failure categories distinct from output-budget exhaustion and from malformed replies.

- **Inferential tier (preregistered rule, unchanged):** gemma-4-31b-it and deepseek-v4-flash. Only these cohorts carry the primary and co-primary tests.
- **Exploratory tier (Angela's decision, 2026-11-07 23:5x EST):** qwen3.5-397b, qwen3.8-27b and gemma-4-26b-a4b-it, the three models at 30 or 31 of 36. Same freeze shape, same instances, same arms and budget. Reported descriptively per model with their invalid, 504 and guard-stop rates alongside; **no inferential claim, no inclusion in the Holm family, and no pooling with the inferential tier.** The tier exists to show whether the pattern holds where reply reliability was marginal, not to add power.
- **Excluded:** glm-53-flash and glm-5.2, reported with their canary numbers.

## 4. Outcomes (as computed by the vendored `score_runs.py`)

Per registered slot: status (complete, invalid_output, error, missing), `proposed_bad_approval`, `stated_answer_correct`, `citation_contract_valid`, `correct_abstention` (V10 only), `accepted_bad_actions`, `correct_publications`, `gate_rejections`, `completed_correctly`. Per call: input, output and reasoning tokens, latency, cost at posted rates.

Primary outcome: `completed_correctly` on V6 and V11, compact vs current_lookup, paired by instance. Co-primary cost outcome: model calls and total tokens **per registered case, invalid and error slots included** (per completed case would condition on a post-treatment outcome). V1 reports false quarantine per arm, defined as a complete, valid reply that did not approve the clean draft, **separately** from invalid or transport failures, which are reported by reason.

## 5. Analysis

- Paired per-instance differences, compact minus lookup-offered, per model and family. Wilson intervals for single proportions. For the paired difference of proportions, a **score-based paired interval (Tango's score interval for paired binary data, restricted maximum likelihood of the discordant cell under the null)**, implemented in `tools/analysis.py` and self-tested on all-tie and discordant synthetic cases; not a percentile bootstrap, which collapses to a degenerate interval on all-zero paired deltas. Non-inferiority for completion: compact is called non-inferior to lookup-offered if the one-sided lower score bound of (compact minus lookup) exceeds minus 0.10 at the Holm-adjusted alpha. **Margin justification is operational, not statistical:** a reviewer protocol that preloads lineage replaces a round trip to the store; if that costs more than one correct publication in ten, the saved call and tokens are not worth it to an operator, so 0.10 is the largest loss we would accept in deployment. The sample size was then chosen to be able to show that margin (section 2), not the other way round.
- Inferential claims, fixed now: completion non-inferiority on V6 and on V11 for each inferential-tier model (four claims), and **one cost claim per inferential-tier model**: tokens per registered case, lookup-offered minus compact, V6 and V11 pooled within the model, Hodges-Lehmann paired estimate with an exact sign test (six claims in all). Calls per case are reported descriptively only, since the lookup arm's call count is fixed by design at one or two. V1 is descriptive (false quarantine per arm). Holm's step-down across the six at a family-wise 0.05; unadjusted values also shown and labeled. Everything else is descriptive.
- Every registered slot stays in the denominator. Invalid, error and missing are reported by reason per model and arm, with `output_budget_exhausted` separated from malformed and non-queued selections.
- Cross-model consistency is a table of per-model effects, never a pooled estimate.
- Lookup: offered (ITT) is primary; used-only is descriptive selection and reported with the use rate.

## 6. Budget and stopping

Four numbers are reported separately for every cohort before execution, from the posted rates and the frozen budget: the **modeled expected charge** (canary token profile), the **per-attempt reserve** (documented context times input rate plus the budget times output rate), the **expected and 99th-percentile count of provider gateway timeouts** at the canary rate with the correct denominators (DeepSeek 2 of 42, Qwen 397B 5 of 45, Qwen 27B 6 of 42, both Gemmas 0 of 36), each of which retains a full reserve, and the **hard per-model ceiling** = 1.25 times the all-outputs-at-cap case plus one per-attempt reserve plus the 99th-percentile timeout count times the reserve. The stress case shown with each ceiling is how many unsettled attempts fit beside the final reserve when every output hits the cap, and the binomial probability of exceeding that count. A cohort that still stops at its ceiling is reported as guard-stopped slots in the denominator; interleaved task order keeps the three families balanced if that happens. For the nine-case budget canary at 6000 across seven models: all-outputs-at-cap 2.80 credits; all-context worst case 67.14 credits, which is what the reserve guards against and not an expected charge. Hard stop at the ceiling (reserve kept on any unsettled attempt), attempt cap enforced, registry claim per (freeze, cohort). Aggregate across all held-out cohorts stays under Angela's 100-credit authorization with the running total posted after each cohort.

## 7. What is not claimed

No decentralized governance; the operator is trusted. Identity is per role login, not per agent instance. Lineage is what the runtime delivered, not what the model used. Harness-injected compromise, not adversarial agents. Template instances, synthetic tasks, one task type. Provider timing is provider timing.
