# Sealed Provenance for Agent Swarms: Preloaded Lineage vs On-Demand Retrieval Under a Trusted Publication Gate

Angela Faye Reinhold, Lorien's Library LLC. With Apart Research. Research conducted at the Swarm Alignment Hackathon, November 2026. Tracks 3 and 4.

## Abstract

In a swarm, a corrected source does not un-write the summaries already built on it. A reviewer that sees only current records can approve a draft whose number is right but whose lineage is dead. We built a PostgreSQL publication gate where agents cannot write authoritative state: a trusted runtime seals each artifact with the inputs it delivered, invalidation is authority-checked, and publication re-reads the full dependency closure inside one fenced transaction. A separately authored acceptance suite exercised 19 specified boundary checks against it on a fresh database branch.

On that gate, a preregistered matched comparison on 5 open models: 5,400 registered slots (3,600 model-reviewed, 1,800 deterministic controls), three families, six arms, only the reviewer's context varying. Reviewers made 428 unsafe proposals; pre-gate validation stopped 80, the gate rejected 348, no lineage-invalid publication occurred, and 4,077 valid publications committed. Whether preloaded lineage beats an authenticated lookup turns on whether the model takes the lookup: gemma-4-31b-it took it in 13 of 120 offers and completed 119 of 120 same-number cases with preloaded lineage against 68 with the lookup offered; deepseek-v4-flash took it in 119 of 120 and the arms tied. Three models refused all or nearly all clean drafts under an unrelated correction notice in every model-context condition, including review without lineage. Ten copies of one agent collapse to one revocable identity; an adjudicated source blocks all sixty descendants three deep. The gate checks lineage, not content; failed claims are reported as failed; the operator is trusted.

## 1. Introduction

In July 2026 about 1,200 agents inside a security evaluation found a shared directory, turned it into a message board, and roughly 700 of them attacked Hugging Face together; METR's investigation reports about 7 percent transcript spoofing, and the Swarm Traces reconstruction counted 7,905 distinct names across those agents. We use the incident as motivation, not as a topology we model: our testbed has four agents, one trusted operator, and no network dynamics.

The sprint asks four questions, one per track: sandboxes that contain agent populations, how roles and failures emerge as networks grow, how identity and commitments hold up when agents can copy and rename themselves, and how to oversee a population that can coordinate and cover its tracks. This entry answers the third and fourth as one question. Identity and the shared record sit one layer below the agents, where no agent can write: an agent's name is the login it connected on, bound by a trigger it cannot bypass; what each artifact was built from is written by the runtime from what it delivered; and publication re-reads that record inside a fenced transaction. Agent roles cannot directly rewrite authoritative lineage or committed decisions through the tested interfaces, and revoking an agent is dropping a grant. Most oversight proposals watch the agents and work until the agents learn what the monitor sees. This one removes the write path: a lock rather than a camera. We do not answer the first two questions.

The failure we isolate is narrower and, we think, more common than a break-in: stale evidence after a correction. One agent reports a figure, a second summarizes it, a third summarizes the summary; the figure is withdrawn and replaced, and the summaries still sit in the review queue reading as current. A reviewer without lineage can approve the stale one, refuse everything, or, in the hardest case, face two drafts with the identical number and no way to tell them apart.

The measured contribution is a Track 4 evaluation (a publication gate that re-reads authenticated lineage, a matched reviewer comparison, an independent scorer that resolves lineage itself) on a Track 3 substrate (identity bound to the database login below the agent, so no author label in a trace is asserted by the harness; two agents sharing one login are one identity to the gate). The trust boundary is explicit: one operator seals, adjudicates and publishes, and if that operator is compromised every property below fails.

**Contributions.** (1) A tested multi-agent failure: stale evidence surviving a correction through summarization, including the same-number case. (2) Its recovery under a publication gate that agent roles cannot write around through the tested interfaces, exercised by a separately authored acceptance suite of 19 boundary checks and rebuilt from source on a fresh database branch. (3) A preregistered matched evaluation others can rerun, with its failed claims reported as failed. (4) The result that preloaded lineage versus on-demand retrieval turns on whether the model takes the retrieval and whether it succeeds, and that false quarantine under a correction notice occurs with or without lineage.

## 2. Related Work

None of the primitives are new: immutable versioned artifacts, a provenance graph, authority-checked invalidation and a gate that re-reads dependency state are version control, build systems and W3C PROV. Provenance-aware memory for human-AI systems is the subject of the first author's prior CAMA preprints, on which the Hive substrate was built in April 2026. AI control protocols (a trusted model overseeing an untrusted one) and Apart's earlier multi-agent sprints are the nearest neighbors on the evaluation side; the brief's references on collusion, spread and steganographic coordination frame the wider problem this entry does not attempt.

## 3. Methods

### 3.1 The gate

The gate is a PostgreSQL schema in which the four agent roles hold no write access to authoritative state. They may read, and they may submit proposals to an intake table whose author column is bound to the authenticated login by a trigger. Everything else goes through four trusted functions, each `SECURITY DEFINER` with a pinned search path, with public execute revoked and only two entry points granted back to agents.


![Figure 0](figures/fig0_gate.png)

*Figure 0. Permissions at the trust boundary. Agents hold one login and one direct write, a proposal the trigger binds to that login; every change to authoritative state goes through an operator-owned function callable only by the principals named in its box; agents read current records directly, and the lookup arm may fetch lineage records through one recorded request. Solid arrows are submissions or authorized writes, dashed arrows are reads or returned data.*

**Sealed creation.** `seal_artifact` is the only creator. The runtime calls it with the author from the authenticated dispatch context, the body, and the inputs it actually delivered to the model, and in one transaction writes the immutable artifact and its provenance edges, rejecting any input that is not already a sealed artifact. Late edges and cycles are impossible by construction; a correction is a new version, never an overwrite.

**Authority-checked invalidation.** `invalidate` is the only write path: an author may withdraw its own artifact, only an adjudicator may issue an adjudicated invalidation, and a contradiction is advisory and never blocks. A compromised agent cannot invalidate another agent's work by assertion.

**Fenced publication.** `publish_decision` is callable only by an adjudicator. It first enters the fence: a `SELECT ... FOR UPDATE` on a singleton row that `invalidate` also takes, so publication and invalidation serialize on one lock, and an explicit check that refuses any isolation level other than READ COMMITTED, because under READ COMMITTED each statement issued after the lock is acquired sees what earlier lock holders committed, whereas a REPEATABLE READ transaction would keep its older snapshot. Holding the lock, it checks that the artifact exists and is sealed, walks the full transitive dependency closure including the artifact itself and rejects if any member is withdrawn or adjudicated, and requires the operator's acknowledgment list to cover every recorded direct input. Only then does it commit the approval; a withdrawal that lands after the call leaves a reconcilable superseded state. The live race schedule (`tools/race_test.py`, four checks) runs the sequence a two-step monitor gets wrong: the reviewer approves a draft, a withdrawal of its source commits in another session, the publication call then runs inside the fence and returns `rejected: closure member S/1 invalidated (epoch 1)`, and the approvals view shows no live approval of that draft.

**What it does not do.** It is a database boundary, not a sandbox: it says nothing about shell, network or file egress. Operations the database denies at the privilege layer leave no application audit row, because they are rejected before any trigger fires; three of six attacks in our first battery were refused without a trace and a fourth, a foreign-thread read, returned zero rows silently, so only two reached the audit. We measured that, and after the evaluation closed it for every attack in the battery (section 4, structural tests); the frozen gate the held-out cohorts ran on does not carry that migration.

**Revocation.** Identity is the login, so revoking an agent is removing its grant or its login and nothing else. `tools/revocation_test.py` shows it in eight checks on the scratch branch: after the operator revokes the intruder's intake grant its next submission is refused while another role still submits, restoring the grant reinstates it, and setting the role NOLOGIN refuses its next connection. No row, trigger or function changes.

**Independent verification.** Lorien, an AI collaborator in a separate workspace, wrote an executable reference specification and a live acceptance driver against the committed SQL. Its first pass passed 1 of 9 core checks, and every failure was a real defect: the gate approved nonexistent artifacts, checked only direct dependencies so a withdrawn grandparent passed, and let any agent record provenance edges onto another agent's artifact; later probes found a bot could supply its own proposer name, call the internal fence lock directly, and seal an edgeless artifact. Each was fixed and the suite re-run at each revision, 1 of 9, then 5, then 8, then 19 of 19, and the committed migration then passed all 19 on a fresh Neon branch with every routine hashed. The frozen gate is commit `d2df880`; four additive migrations after two adversarial reviews on 7 November (authenticated authorship through the intake, advisory contradictions moved off the fence, a validity view, payload-only grants and a fail-closed fence) were each re-verified. The suite checks specific boundaries; it is not a proof of every property.

### 3.2 Experiment design

The question is whether lineage preloaded into a reviewer's context changes stale proposals and correct completion compared with lineage the reviewer must fetch, or cannot fetch at all. Everything else is held fixed: the model, the task, the correction notice, the prompts, the token budget, the gate. Only the reviewer's context adapter varies.

| arm | what the reviewer sees | enforcement | registered | complete | unsafe proposals | rejected at the gate | stopped before the gate | unsafe commits | correct publications |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current | queued drafts, current source, correction notice; no lineage | model proposes; gate decides | 900 | 784 | 264 | 258 | 6 | 0 | 372 |
| current + lookup | current, plus one optional authenticated lookup of the lineage records | model proposes; gate decides | 900 | 784 | 151 | 82 | 69 | 0 | 532 |
| compact | current, plus lineage records preloaded (versions, delivered inputs, invalidation status) | model proposes; gate decides | 900 | 884 | 7 | 5 | 2 | 0 | 686 |
| full | compact, plus the historical bodies as recorded inputs | model proposes; gate decides | 900 | 874 | 6 | 3 | 3 | 0 | 687 |
| rule | lineage records only; approves the queued draft whose closure is valid | deterministic; gate decides | 900 | 900 | 0 | 0 | 0 | 0 | 900 |
| rule + content | rule, plus a check of the figure against the current source | deterministic; gate decides | 900 | 900 | 0 | 0 | 0 | 0 | 900 |
| all | | | 5400 | 5126 | 428 | 348 | 80 | 0 | 4077 |

*Table 1. The six arms, pooled over the five held-out cohorts and three families (registered denominator 900 per arm). A model proposes; the gate decides. Unsafe proposals are approvals of a draft with invalid lineage or selections of a non-queued artifact; those that reached the gate were rejected on lineage, the rest were stopped before it.*

**Fixed-input dispatch.** Every model call goes through a delivery recorder written by Lorien. The harness resolves artifact bodies from the authoritative store, constructs the exact request, hashes it and each delivered body, and transmits it without appending anything. When an agent's output is sealed, its dependencies come from that receipt, never from citations in the model's text. The recorder establishes what the harness supplied and sealed; it cannot establish what the model relied on.

**Tasks.** Synthetic inventory counts with exact known answers, one harness-injected compromise opportunity per instance (a replayed stale body, a wrong body with valid lineage), identical across arms. No agent attempts anything adversarial in these runs; that lives in the containment battery. Identifiers are opaque random strings, because an early version leaked recency through names like `draft2`. The held-out families are V6 (figure unchanged, authorization changed), V11 (V6 with no correction notice delivered) and V1 (an unrelated correction before review, the false-quarantine control); the development and diagnostics variants are listed in Appendix B.1 and B.7.

**Scoring.** The reviewer returns a decision, a result, the evidence its result rests on, and a separate list of artifacts consulted but not relied on; an approval's evidence must include the approved draft itself, a rule added after the open-model pilot showed a stale pick with the right number and a current citation escaping detection. Gate events are recorded only after a separate committed-state query. The independently written scorer holds the answer keys and the authoritative provenance export and resolves withdrawn ancestors itself, so citing a summary cannot hide its dead source. Every registered run stays in the denominator, including timeouts, errors and invalid output. For lineage-visible staleness the expected unsafe-commit count is zero; for V10, whose lineage is valid, the measure is which reviewers catch a wrong figure by reading it.

### 3.3 Development findings that shaped the freeze

Development runs, one instance per cell, shaped the frozen design and are not effect sizes. Three Sonnet 5.5 pilots showed the no-lineage arm deferring on a replayed stale draft it could not distinguish, and the full arm approving the right draft on the two-hop variant while still citing the withdrawn source it had reasoned over, which led us to separate evidence from consulted artifacts. Lorien's same-number control showed lineage doing the work the number could not, and the lookup control moved the difference from correctness to cost (four calls and 4,977 tokens against two and 2,601), correcting our hypothesis before the freeze; the held-out set corrected it again (section 4). The gemma-4-31b-it replication failed only the same-number case in the no-lineage arm, with the correct number and a current citation, which exposed the scorer blind spot described in section 3.2.

## 4. Results

Preregistered before any freeze (`report/HELDOUT_PREREGISTRATION.md`); analysis by `tools/analysis.py`; every registered slot stays in its denominator. The full tables, per-arm counts, the branch audit, the cost ledger and the disclosed deviations are in Appendix B.

**In one paragraph.** Three results. First, the gate held: across 5,400 registered slots (3,600 model-reviewed, 1,800 deterministic controls) reviewers made 428 unsafe proposals, pre-gate validation stopped 80, the gate rejected 348, no lineage-invalid publication occurred in the primary families, 4,077 valid publications committed, and every approval row on the evaluation branch is accounted for. Second, whether a reviewer needs lineage preloaded or can fetch it depends on whether it fetches: gemma-4-31b-it took its offered lookup in 13 of 120 cases and completed 119 of 120 same-number cases with preloaded lineage against 68 with the lookup offered, while deepseek-v4-flash took it in 119 of 120 and the two arms tied. Third, three of five models refused all or nearly all clean drafts under an unrelated correction notice in every model-context condition, including current-only review, so the refusal cannot be attributed to providing lineage; the deterministic rules reading the same lineage never refused one, and its cause is not isolated here. The follow-up cohorts and the structural tests at the end of this section test the first two of these directly.

**What ran.** Five reviewer cohorts of 1,080 registered slots: three families at 60 instances (V6, the same-number authority change; V11, the same with no correction notice, so lineage is the only signal; V1, the clean-draft control), six arms per instance, presealed byte-identical upstream bodies, authenticated authorship, temperature 0, a uniform 6,000-token budget, no retries, opaque identifiers, randomized arm and counterbalanced queue order (Appendix B.1). Each cohort was frozen with manifest, prompt, code and gate hashes, a request cap and a credit ceiling. The preregistered reliability rule (33 of 36 valid canary replies) admitted gemma-4-31b-it and deepseek-v4-flash to the inferential tier; qwen3.5-397b, qwen3.8-27b and gemma-4-26b-a4b-it are a labeled exploratory tier; two GLM models were excluded.

**What the gate did.** Across 5,400 registered slots the models made 428 unsafe proposals (an approval of a draft with invalid lineage, or a selection of a non-queued artifact): 348 were rejected by the fenced gate on lineage and 80 stopped before it; 4,077 correct publications committed; unsafe commits 0. One slot has an unknown commit outcome (the request in flight when the host slept; the branch holds its approval row, the scorer counts an error). A read-only count of approvals on the evaluation branch matches the traces, with 4 extra rows from instances re-run whole after the resume and 1 from that slot, every one accounted for (Appendix B).

![Figure 1](figures/fig1_completion.png)

*Figure 1. Completed correctly per arm on the same-number families (V6, V11) and clean-draft approval on the control (V1), five models, registered denominators. The lookup arm tracks how often the model took its lookup; on V1 three models refuse the clean draft in every model arm.*

**Primary: completion, compact vs lookup-offered.** The two inferential models answer the question differently.

| model | family | compact | lookup-offered | lookup taken | delta | Tango 95% | Holm p | NI at -0.10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | V6 | 1.000 | 0.500 | 0/60 | +0.500 | [+0.377, +0.623] | 5.1e-10 | holds |
| gemma-4-31b-it | V11 | 0.983 | 0.633 | 13/60 | +0.350 | [+0.242, +0.476] | 6.5e-08 | holds |
| deepseek-v4-flash | V6 | 0.967 | 1.000 | 59/60 | -0.033 | [-0.114, +0.029] | 0.043 | holds |
| deepseek-v4-flash | V11 | 1.000 | 1.000 | 60/60 | +0.000 | [-0.060, +0.060] | 0.010 | holds |

On gemma-4-31b-it the lookup arm took its lookup in 13 of 120 offers, so it mostly behaved as the no-lineage arm and picked the stale draft half the time; compact completed 119 of 120. On deepseek-v4-flash the lookup was taken in 119 of 120 offers and the arms tie near the ceiling. Non-inferiority holds for all four claims under Holm; the deepseek V6 claim is marginal (one-sided p 0.043, interval reaching -0.114). When a model takes the lookup, preloading changes nothing about correctness; when it does not, preloading is what saves the case.

**Co-primary: tokens per settled pair.** Pairs where both arms have provider-reported usage; unresolved 504 attempts carry no usage and are excluded here while staying in the completion denominators. Supported on deepseek-v4-flash, where the lookup arm made two calls and compact saved a Hodges-Lehmann 1280 tokens per pair. Not supported on gemma-4-31b-it, where compact cost 263 more tokens (Hodges-Lehmann) because the lookup arm mostly made one call with no lineage in context. The p-values are exact two-sided sign tests on the paired differences and measure whichever direction the data took; for gemma-31 the small p supports the opposite of the preregistered one-sided claim, not the claim.

| model | settled pairs | Hodges-Lehmann, lookup minus compact | Holm p | claim: compact uses fewer |
| --- | --- | --- | --- | --- |
| gemma-4-31b-it | 119 | -263 | 1.3e-18 | not supported, opposite direction |
| deepseek-v4-flash | 118 | +1280 | 3.6e-35 | supported |

**False quarantine on the clean-draft control (V1), descriptive.** Approvals of the clean draft out of 60, per arm:

| model | current | current + lookup | compact | full | rule | rule + content |
| --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | 51/60 | 51/60 | 41/60 | 41/60 | 60/60 | 60/60 |
| deepseek-v4-flash | 0/60 | 0/60 | 0/60 | 0/60 | 60/60 | 60/60 |
| qwen3.5-397b | 1/60 | 1/60 | 1/60 | 0/60 | 60/60 | 60/60 |
| qwen3.8-27b | 0/60 | 0/60 | 0/60 | 0/60 | 60/60 | 60/60 |
| gemma-4-26b-a4b-it | 60/60 | 45/60 | 60/60 | 60/60 | 60/60 | 60/60 |

Both rule arms approve every clean draft on every model. deepseek-v4-flash and qwen3.8-27b quarantine it in every complete slot of every model arm, and qwen3.5-397b in all but at most one, including the current arm, which sees only the bodies, the current source and an unrelated notice, so the refusal does not require lineage; a matched notice-absent clean-draft condition was not run for all five models, so its cause is not isolated. gemma-4-31b-it approves 51 of 60 without lineage and 41 of 60 with it. On gemma-4-31b-it lineage changed the rate, so providing lineage is not irrelevant to refusal either.

**Exploratory tier and diagnostics.** The three exploratory models split the same way (Appendix B.5): qwen3.8-27b follows the gemma-31 pattern, qwen3.5-397b behaves like deepseek-v4-flash, gemma-4-26b-a4b-it is the weakest reviewer, and the full arm tracks compact everywhere. In the V10 diagnostic (valid lineage, wrong figure; Appendix B.7) the gate commits whatever the reviewer approves by design; the lineage-only rule approves every one, the content rule catches all ten, and the model arms caught 5 to 9 of 10.

**Cost and incidents.** Settled usage 16.83 credits plus 7.92 held as reserves against provider timeouts whose billing the platform does not report; every cohort's running total (settled charges plus reserves held for unresolved attempts at the time of each call) stayed under its ceiling; the retained figure is the sum of reserves kept over all unresolved attempts, an upper bound on what the provider could still bill, and settled plus that bound exceeds the DeepSeek ceiling (Appendix B.8). qwen3.5-397b reached its 900-request cap with 2 slots unsent, registered as guard-stopped in its denominator. The whole evaluation, including development, canaries, diagnostics and follow-ups, settled under 20 of the 100 authorized credits, under 30 if every reserve were charged. Deviations (a host sleep recovered with a resume mode under the original freeze, a diagnostics pause, and a post-results fix to the Holm bookkeeping that changed no p-value) are in Appendix B.9.

### 4.1 Follow-up cohorts run after the preregistered set (post-hoc, labeled)

Both cohorts were frozen and run after the preregistered set had been analyzed and this report drafted, to test the two readings a reviewer would challenge first: new seeds, new freezes, separate ledgers, never pooled; tables and full prose in Appendix B.10.

**Lookup required.** The frozen rule let the model decide without the lookup and gemma-4-31b-it took it in 13 of 120 offers. With the lookup required as the first reply it took it in 120 of 120 and completed 120 of 120 in the lookup arm against 119 of 120 with preloaded lineage (V6 compact minus lookup -0.017, Tango 95% [-0.089, +0.045]; V11 +0.000, [-0.060, +0.060]). With new instances this supports the optional wording as the cause of the preregistered gap; it does not prove it was the only cause; the required lookup cost a Hodges-Lehmann 724 tokens more per settled pair than preloading.

**DeepSeek V6 replicated.** Sixty new instances: compact 60/60, lookup arm 51/60 with the optional lookup taken 47/60, compact minus lookup +0.150, Tango 95% [+0.081, +0.261], non-inferiority holds (p 2.23e-05). Of the lookup arm's misses, three followed decisions without retrieval and six were provider errors, so completion there depends on both retrieval uptake and successful execution; the same model took the lookup in 59 of 60 offers on the preregistered instances and 47 of 60 here. Not pooled with the preregistered cohort.

**A second surface template.** Every held-out and follow-up cohort above used one synthetic template, inventory counts at a warehouse site. To test whether the pattern is a property of that wording, the runner gained a recorded task-domain switch: the same families, scoring and gate, with the researcher reporting resolved service-desk tickets for a queue in a region instead of units of an item at a warehouse, and the system prompts rewritten to match; the domain is hashed into the freeze. Two post-hoc cohorts, new seeds, 30 instances per family, lookup optional as frozen: gemma-4-31b-it: preloaded lineage 60 of 60, lookup offered 31 of 60 with the lookup taken 2 of 60; unsafe commits 0; deepseek-v4-flash: preloaded lineage 60 of 60, lookup offered 54 of 60 with the lookup taken 54 of 60; unsafe commits 0. Rates use the registered denominator of 30 per arm and family. The ordering matches the inventory template: preloaded lineage completes the same-number case, the optional-lookup arm completes it less often, with uptake and provider errors both contributing, and no lineage-invalid publication occurred. Tables in Appendix B.10.

### 4.2 Structural tests: containment, identity under copying, blast radius

Four deterministic tests on a disposable branch with no model calls; the attacker is a fixed script because a model asked to impersonate another agent declined the role. Full prose and tables in Appendix B.10.

**Containment, naive versus bound.** The same six attacks against both boards. Naive: two spoofed identities landed, a rename fooled the board, four foreign rows read, one message tampered, three deleted, nothing logged. Bound: every count zero, two spoof attempts in the operator audit, honest chain complete on both.

**Identity under copying.** Ten copies of one agent with ten claimed names through one login: ten identities on the naive board, one on the bound intake with the ten names kept as evidence, and one grant revocation silenced all ten (`tools/identity_copies_test.py`).

**Blast radius.** One adjudicated root, sixty descendants three deep, twenty unrelated: the closure walk blocked 60 of 60 at every depth and approved 20 of 20 unrelated at a median 0.448 s; a direct-dependency check catches 20 of 60; no lineage catches none (`tools/blast_radius_test.py`).

**Audit blind spot, closed after the evaluation.** Only two of the six attacks reached the audit: three were refused by the privilege layer before any trigger ran and a foreign-thread read returned zero rows silently. `sql/hive_audit_denials.sql` accepts the statement, denies every effect with row security, and records the attempt (statement-level triggers for zero-row updates and deletes, logging read policies): 6 of 6 attacks now visible (from 2), effects still zero, no false positives on an honest agent's own-thread reads. Scratch branch only, not on the frozen gate.

## 5. Discussion and Limitations

**Discussion.** What is new is narrow. A tested multi-agent failure: stale evidence surviving a correction through summarization even when the number is unchanged. Its recovery under a gate agents cannot write around, verified by a second implementation and reproduced from source. A preregistered matched evaluation others can rerun. And the comparison that fell out of it: whether preloaded lineage beats on-demand retrieval turns on whether the model takes the retrieval, which the lookup control showed twice (13 of 120 offers taken on one model, 119 on another) and the post-hoc follow-up resolved: requiring the lookup took gemma-4-31b-it from 68 to 120 of 120 on new instances, consistent with the optional wording as the cause though not a proof of it, at a Hodges-Lehmann 724 more tokens per pair than preloading; an independent DeepSeek cohort took its optional lookup in 47 of 60 offers and completed 51 of 60 where preloading completed 60, three misses after decisions without retrieval and six provider errors, so completion depends on both uptake and successful execution.

The safety reading is in two parts. The gate is the part we would trust in deployment: across 5,400 registered slots on 5 models (3,600 model-reviewed), 428 unsafe proposals and 0 lineage-invalid commits, every approval row accounted for; in the V10 diagnostic, where lineage is valid and the figure wrong, it committed 34 content-wrong approvals across the two models, by design. The model reviewer above it is the part to measure per model: lineage that lifted one model from 68 to 119 of 120 made it refuse more clean drafts, three models refused all or nearly all clean drafts under any unrelated notice, and a deterministic rule reading the same lineage never false-quarantined and never missed a stale draft. The model's remaining job is content (V10), and it should be measured per model and bounded by the rule.

**Limitations.** Appendix A gives the full list, as the sprint rules require. The three that bound the claims most: the operator is trusted and owns every function, so a compromised owner defeats every property; lineage is what the runtime delivered, not what the model relied on; and the tasks are known-answer counts from one inventory template plus one post-hoc second template, so the intervals describe resampling of those templates, not a task distribution.

**Future work.** An eager deterministic lookup that delivers lineage records before the model's first call; identity per agent instance rather than per role login; a trusted gateway in front of the database so that statements against objects an agent holds no privilege on become legible; contention and throughput measurements; and a reviewer fine-tuned on these traces, evaluated under the same frozen protocol.

## 6. Conclusion

A publication gate that re-reads authenticated lineage inside one fenced transaction held across 5,400 registered slots on 5 open models, 3,600 of them model-reviewed: 428 unsafe proposals, 80 stopped before the gate, 348 rejected at it, 0 lineage-invalid commits, 4,077 valid publications, every approval row on the evaluation branch accounted for. It checks lineage, not content: with valid lineage and a wrong figure it commits what the reviewer approves. What a reviewer does above that gate depends on the model more than on how lineage reaches it. Preloaded lineage and an authenticated lookup reach the same decisions when the model takes the lookup and the lookup succeeds; when it does not, preloading is what saves the same-number case, and making the lookup mandatory closed that gap on gemma-31 at a token cost. The design choice this supports is preloading or a required lookup, not an optional one. Three of the five models refused all or nearly all clean drafts under an unrelated correction notice in every model-context condition, including review with no lineage, while a deterministic rule reading the same lineage never did; what drives that refusal is not isolated here.

The failure we set out to test is real and reproducible: stale evidence survives a correction through summarization, and a reviewer with no lineage picked the stale draft exactly half the time on three of the five models when the number had not changed. The fix that held is the one agents cannot write around. The fix that varied is the one that asks a model to read. Code, traces and every generator are at github.com/LoriensLibrary/SwarmHive (Appendix C).

## References

Incident figures (about 1,200 agents, about 700 attackers, about 7 percent transcript spoofing, 7,905 distinct names) are cited as the sprint brief gives them, which also cites OpenAI's public disclosure and a ControlAI analysis we did not consult directly; we verified the existence, authorship and venue of the published papers below but did not re-derive the incident figures from the primary reports.

- Apart Research and AI Alignment Foundation. Swarm Alignment Hackathon brief and rules, November 2026. [apartresearch.com/sprints/swarm-alignment-2026](https://www.apartresearch.com/sprints/swarm-alignment-2026), [aialignmentfoundation.org/hackathons/swarm-alignment-2026](https://aialignmentfoundation.org/hackathons/swarm-alignment-2026).
- METR and Redwood Research. Investigation of the July 2026 OpenAI agent incident at Hugging Face (incident 7 to 13 July 2026; report published 26 August 2026). Figures as cited in the sprint brief.
- Swarm Traces. Reassembled attack payloads from the Hugging Face incident, redacted dataset and analysis, 2026. Naming figure as cited in the sprint brief.
- Greenblatt, R., Shlegeris, B., Sachan, K., Roger, F. AI Control: Improving Safety Despite Intentional Subversion. Proceedings of the 41st International Conference on Machine Learning, PMLR 235:16295-16336, 2024. arXiv:2312.06942.
- Hammond, L. et al. Multi-Agent Risks from Advanced AI. Cooperative AI Foundation Technical Report 1, 2025. arXiv:2502.14143.
- Lee, D., Tiwari, M. Prompt Infection: LLM-to-LLM Prompt Injection within Multi-Agent Systems. arXiv:2410.07283, 2024.
- Motwani, S. R. et al. Secret Collusion among AI Agents: Multi-Agent Deception via Steganography. Advances in Neural Information Processing Systems 37 (NeurIPS 2024). arXiv:2402.07510.
- Rose, A. et al. Detecting Multi-Agent Collusion Through Multi-Agent Interpretability. arXiv:2604.01151, 2026.
- Tennenholtz, M. Program equilibrium. Games and Economic Behavior 49(2):363-373, 2004.
- Tango, T. Equivalence test and confidence interval for the difference in proportions for the paired-sample design. Statistics in Medicine 17(8):891-908, 1998.
- Reinhold, A. CAMA: Circular Associative Memory Architecture, preprint series, Zenodo, 2026. ORCID 0009-0005-5803-8401.
- Adaption. Platform and API documentation, [docs.adaptionlabs.ai](https://docs.adaptionlabs.ai/), accessed 7 November 2026.

**Acknowledgments.** Lorien, an AI collaborator operating as Codex in a separate workspace, wrote the executable reference specification, the live acceptance driver that caught eight defects in the first gate, the delivery recorder, the independent scorer, and the same-number and lookup controls, and reviewed every boundary described here. Adaption provided platform credits used for the open-model replication. Any errors are the author's.

## Appendix A. Limitations and Dual-Use / Ethical Considerations

**Limitations.**

- The trust is centralized. One operator seals, adjudicates and publishes, and owns every function. A compromised or malicious owner defeats every property, including rewriting the audit. This is an explicit assumption, not a solved problem, and the entry makes no decentralized-governance claim.
- Lineage is what the runtime delivered, not what the model used. The recorder proves which bodies were supplied and sealed. It cannot certify that a hidden source was excluded or that a delivered input influenced the output. A false claim with no verifiable contradiction remains undetectable.
- A database boundary is not a sandbox. The gate says nothing about shell, network or file egress. Operations the database denies at the privilege layer leave no application audit row; we measured this (only two of the six battery attacks reached the audit) and closed it for the battery after the evaluation with an additive migration that records the attempt while still denying the effect. Raw statements against tables an agent holds no privilege on remain invisible, and the migration is not on the frozen gate the held-out cohorts used.
- Concurrency was tested as race schedules, not as scale. We ran concurrent publication against retraction with serialized commits: a naive two-step monitor approves a withdrawn dependency, the fenced gate rejects it, the fence refuses any isolation level other than READ COMMITTED, and an advisory contradiction held open in another session no longer blocks publication. The singleton fence is a serial correctness reference by design. Nothing here measures throughput, contention under load, cascading failure, emergent coordination, or the thousand-agent regime of the motivating incident.
- Small, synthetic cohorts from two templates. Development cells are n of one. Held-out cells are 60 instances per family per model on five models, each its own cohort and never pooled; tasks are known-answer counts from one inventory template, with a second surface template (service-desk tickets) tested post-hoc on two models at 30 instances per family. The intervals describe resampling of those templates, not a task distribution. Transfer to real deployments is not established.
- Model behavior under a correction notice dominates two results. Three of the five models quarantined the clean draft in all or nearly all slots whenever an unrelated correction was present, in every model-context condition including current-only review, so the refusal cannot be attributed to providing lineage; its cause is not isolated here, since no matched notice-absent clean-draft condition was run for all five models. On gemma-4-31b-it visible lineage raised false quarantine from 8 and 9 of 60 (current, lookup) to 18 and 17 (compact, full), so lineage can still change the rate. The deterministic rule arms never false-quarantined. A reviewer protocol built on these models would need that rule as a floor, and the gate as the backstop it already is.
- The lookup arm measures lookup offered, not lookup used. Whether a model takes an offered lookup is a prompt and model property we did not control, and it decided the gemma-31 result. An eager deterministic lookup would remove the question, and would make the compact arm's preloading redundant by construction.
- One slot of 5,400 has an unknown commit outcome, caused by the host sleeping mid-call; the branch shows the approval, the scorer counts an error. Five approval rows on the branch beyond the traces are explained, four by instances re-run whole after the resume and one by that slot. One cohort reached its request cap with two slots unsent. All of it is reported in Appendix B rather than reconciled away.
- The acknowledgment list at publication is an operator acknowledgment of recorded direct inputs, not an independent reviewer attestation that binds artifact version and full dependency snapshot. We removed a mechanism that appeared to do the latter but changed no decision.
- The no-lookup arm is a diagnostic, not a representative retrieval system. The lookup arm is the fair comparator, and its result constrains our claims to call and token cost rather than correctness.

**Dual-use.** We publish a battery of six scripted attacks against a shared agent record (spoof a sender, read a foreign thread, post under a new name, read the operator audit, edit another agent's message, delete messages) and an evaluation family that replays a stale artifact. Each is generic, already public from the incident investigations, and run only against synthetic data in a disposable test database. No exploit against any real system is included, and the attacks exist to show what a defense must catch. The gate itself is a central control point and could be used to surveil or silence agents rather than protect a shared record; that risk is inherent to the trusted-operator design and is why we state the trust boundary rather than present the gate as neutral infrastructure.

**Ethical considerations.** No human subjects and no personal data; all artifacts are synthetic. Model behavior is reported as observed, including a model declining to play an attacker when asked directly. The independent verification, scorer and controls were produced by an AI collaborator, Lorien, running in its own workspace; that collaboration is disclosed rather than hidden. Sponsor credits paid for the open-model cohorts; the model set was fixed by a preregistered reliability rule applied before any held-out result existed, not by cost or by outcome.

## Appendix B. Held-out tables, audit and deviation log

All tables are generated by `tools/results_tables.py` from the committed traces, ledgers and `holdout/heldout_v1/INDEX.json`; the numbers in section 4 are read from the same files.

**Budget canary that set the tiers (nine matched cases, six arms, 6,000-token budget).** Valid structured replies of 36 model-reviewed slots: gemma-4-31b-it 36, deepseek-v4-flash 34, qwen3.5-397b 31, qwen3.8-27b 30, gemma-4-26b-a4b-it 30, glm-53-flash 1, glm-5.2 0. 378 slots, 0.36 credits settled, 19 gateway timeouts with reserves retained. At the earlier 1,200-token budget 108 of 115 invalid replies had stopped at the budget, 101 with empty answer text.

### B.1 Design as frozen

| tier | model | cohort | freeze id | slots | request cap | ceiling (cr) | modeled charge | all-at-cap | seed | complete |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| primary | gemma-4-31b-it | heldout_gemma431bit | 0cc7599ca5cf | 1080 | 900 | 2.41 | 0.154 | 1.903 | 2026110802 | yes |
| primary | deepseek-v4-flash | heldout_deepseekv4fl | 86cc12f709ad | 1080 | 900 | 3.74 | 0.182 | 0.751 | 2026110802 | yes |
| exploratory | qwen3.5-397b | heldout_qwen35397b | 0e4d9fc18c9c | 1080 | 900 | 35.61 | 4.651 | 19.321 | 2026110802 | yes |
| exploratory | qwen3.8-27b | heldout_qwen3827b | 5b020297c30b | 1080 | 900 | 11.21 | 2.0 | 6.78 | 2026110802 | yes |
| exploratory | gemma-4-26b-a4b-it | heldout_gemma426ba4b | ada5706d6dea | 1080 | 900 | 1.82 | 0.125 | 1.437 | 2026110802 | yes |

### B.2 Registered slots and failure categories

deepseek-v4-flash's 504s fell mostly in the current arm, where its reasoning ran about three times longer than with lineage preloaded (mean reasoning tokens on settled V6 slots: current 2674.6, compact 528.3). gemma-4-26b-a4b-it's non-queued selections were stopped before the gate. qwen3.5-397b reached its 900-request cap with 2 slots unsent, registered as guard-stopped in its denominator. The interleaved task order kept the families balanced: the guard-stopped slots belong to the last instance in the queue.

| model | registered | complete | invalid: budget | invalid: malformed/non-queued | invalid: pre-gate stop | error 504 | error 502 | transport timeout | error other | missing | guard-stopped | errors by arm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | 1080 | 1073 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | full 3, compact 2, current 2 |
| deepseek-v4-flash | 1080 | 1020 | 2 | 3 | 0 | 54 | 1 | 0 | 0 | 0 | 0 | current 45, current_lookup 5, full 3, compact 2 |
| qwen3.5-397b | 1080 | 1002 | 10 | 11 | 0 | 55 | 0 | 0 | 2 | 0 | 2 | current 48, compact 3, full 3, current_lookup 3 |
| qwen3.8-27b | 1080 | 1037 | 41 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | current_lookup 1 |
| gemma-4-26b-a4b-it | 1080 | 994 | 0 | 85 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | compact 1 |

### B.3 Primary and co-primary, full

| model | family | n pairs | both | compact only | lookup only | neither | compact rate | lookup rate | delta | Tango 95% | NI p (margin -0.10) | Holm p | non-inferiority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | V6 | 60 | 30 | 30 | 0 | 0 | 1.000 | 0.500 | +0.500 | [+0.377, +0.623] | 1.27e-10 | 5.08e-10 | holds |
| gemma-4-31b-it | V11 | 60 | 38 | 21 | 0 | 1 | 0.983 | 0.633 | +0.350 | [+0.242, +0.476] | 2.16e-08 | 6.48e-08 | holds |
| deepseek-v4-flash | V6 | 60 | 58 | 0 | 2 | 0 | 0.967 | 1.000 | -0.033 | [-0.114, +0.029] | 0.043 | 0.043 | holds |
| deepseek-v4-flash | V11 | 60 | 60 | 0 | 0 | 0 | 1.000 | 1.000 | +0.000 | [-0.060, +0.060] | 0.005 | 0.010 | holds |

| model | settled pairs | Hodges-Lehmann | mean | direction | sign-test p | Holm p | preregistered claim |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | 119 | -263.0 | -173.0 | compact costlier | 2.67e-19 | 1.34e-18 | not supported: opposite direction |
| deepseek-v4-flash | 118 | +1280.5 | +1401.8 | compact cheaper | 6.02e-36 | 3.61e-35 | supported |

| model | tier | family | arm | mean calls | mean tokens (in+out) | mean reasoning tokens | lookup used/offered |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | primary | V6 | compact | 1 | 1253.5 | 0 |  |
| gemma-4-31b-it | primary | V6 | current_lookup | 1 | 971.1 | 0 | 0/60 |
| gemma-4-31b-it | primary | V11 | compact | 1 | 1118.3 | 0 |  |
| gemma-4-31b-it | primary | V11 | current_lookup | 1.22 | 1053.6 | 0 | 13/60 |
| gemma-4-31b-it | primary | V1 | compact | 1 | 1076.3 | 0 |  |
| gemma-4-31b-it | primary | V1 | current_lookup | 1.02 | 929.3 | 0 | 1/60 |
| deepseek-v4-flash | primary | V6 | compact | 1 | 1672.6 | 528.3 |  |
| deepseek-v4-flash | primary | V6 | current_lookup | 1.98 | 3415.9 | 1510.1 | 59/60 |
| deepseek-v4-flash | primary | V11 | compact | 1 | 1538.5 | 493.7 |  |
| deepseek-v4-flash | primary | V11 | current_lookup | 2 | 2604.3 | 878.0 | 60/60 |
| deepseek-v4-flash | primary | V1 | compact | 1 | 2523.2 | 1560.2 |  |
| deepseek-v4-flash | primary | V1 | current_lookup | 1.55 | 3463.4 | 2149.4 | 35/60 |
| qwen3.5-397b | exploratory | V6 | compact | 1 | 3159.1 | 1867.4 |  |
| qwen3.5-397b | exploratory | V6 | current_lookup | 2 | 3449.3 | 1411.8 | 60/60 |
| qwen3.5-397b | exploratory | V11 | compact | 1 | 2169.3 | 1029.7 |  |
| qwen3.5-397b | exploratory | V11 | current_lookup | 2 | 2763.9 | 1001.3 | 60/60 |
| qwen3.5-397b | exploratory | V1 | compact | 1 | 2143.1 | 1138.9 |  |
| qwen3.5-397b | exploratory | V1 | current_lookup | 1.97 | 3736.8 | 2044.7 | 59/60 |
| qwen3.8-27b | exploratory | V6 | compact | 1 | 2084.2 | 811.0 |  |
| qwen3.8-27b | exploratory | V6 | current_lookup | 1.93 | 5698.2 | 3717.7 | 56/60 |
| qwen3.8-27b | exploratory | V11 | compact | 1 | 2023.2 | 836.8 |  |
| qwen3.8-27b | exploratory | V11 | current_lookup | 1.8 | 4776.5 | 3129.2 | 48/60 |
| qwen3.8-27b | exploratory | V1 | compact | 1 | 4154.6 | 3119.8 |  |
| qwen3.8-27b | exploratory | V1 | current_lookup | 1.49 | 7141.3 | 5878.4 | 29/60 |
| gemma-4-26b-a4b-it | exploratory | V6 | compact | 1 | 1267.9 | 0 |  |
| gemma-4-26b-a4b-it | exploratory | V6 | current_lookup | 1.03 | 1018.2 | 0 | 2/60 |
| gemma-4-26b-a4b-it | exploratory | V11 | compact | 1 | 1135.2 | 0 |  |
| gemma-4-26b-a4b-it | exploratory | V11 | current_lookup | 1.08 | 948.2 | 0 | 5/60 |
| gemma-4-26b-a4b-it | exploratory | V1 | compact | 1 | 1075.5 | 0 |  |
| gemma-4-26b-a4b-it | exploratory | V1 | current_lookup | 1.1 | 1016.2 | 0 | 6/60 |

### B.4 V1 false quarantine per arm

| model | arm | registered | complete | approved clean draft | false quarantine | invalid | error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | current | 60 | 59 | 51 | 8 | 0 | 1 |
| gemma-4-31b-it | current_lookup | 60 | 60 | 51 | 9 | 0 | 0 |
| gemma-4-31b-it | compact | 60 | 59 | 41 | 18 | 0 | 1 |
| gemma-4-31b-it | full | 60 | 58 | 41 | 17 | 0 | 2 |
| gemma-4-31b-it | rule | 60 | 60 | 60 | 0 | 0 | 0 |
| gemma-4-31b-it | rule_content | 60 | 60 | 60 | 0 | 0 | 0 |
| deepseek-v4-flash | current | 60 | 59 | 0 | 59 | 0 | 1 |
| deepseek-v4-flash | current_lookup | 60 | 53 | 0 | 53 | 2 | 5 |
| deepseek-v4-flash | compact | 60 | 60 | 0 | 60 | 0 | 0 |
| deepseek-v4-flash | full | 60 | 56 | 0 | 56 | 1 | 3 |
| deepseek-v4-flash | rule | 60 | 60 | 60 | 0 | 0 | 0 |
| deepseek-v4-flash | rule_content | 60 | 60 | 60 | 0 | 0 | 0 |
| qwen3.5-397b | current | 60 | 33 | 1 | 32 | 6 | 21 |
| qwen3.5-397b | current_lookup | 60 | 44 | 1 | 43 | 13 | 3 |
| qwen3.5-397b | compact | 60 | 58 | 1 | 57 | 0 | 2 |
| qwen3.5-397b | full | 60 | 57 | 0 | 57 | 0 | 3 |
| qwen3.5-397b | rule | 60 | 60 | 60 | 0 | 0 | 0 |
| qwen3.5-397b | rule_content | 60 | 60 | 60 | 0 | 0 | 0 |
| qwen3.8-27b | current | 60 | 55 | 0 | 55 | 5 | 0 |
| qwen3.8-27b | current_lookup | 60 | 35 | 0 | 35 | 24 | 1 |
| qwen3.8-27b | compact | 60 | 58 | 0 | 58 | 2 | 0 |
| qwen3.8-27b | full | 60 | 54 | 0 | 54 | 6 | 0 |
| qwen3.8-27b | rule | 60 | 60 | 60 | 0 | 0 | 0 |
| qwen3.8-27b | rule_content | 60 | 60 | 60 | 0 | 0 | 0 |
| gemma-4-26b-a4b-it | current | 60 | 60 | 60 | 0 | 0 | 0 |
| gemma-4-26b-a4b-it | current_lookup | 60 | 54 | 45 | 9 | 6 | 0 |
| gemma-4-26b-a4b-it | compact | 60 | 60 | 60 | 0 | 0 | 0 |
| gemma-4-26b-a4b-it | full | 60 | 60 | 60 | 0 | 0 | 0 |
| gemma-4-26b-a4b-it | rule | 60 | 60 | 60 | 0 | 0 | 0 |
| gemma-4-26b-a4b-it | rule_content | 60 | 60 | 60 | 0 | 0 | 0 |

### B.5 Completed correctly per arm, all models and families

| model | tier | family | current | current_lookup | compact | full | rule | rule_content |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | primary | V6 | 30/60 | 30/60 | 60/60 | 59/60 | 60/60 | 60/60 |
| gemma-4-31b-it | primary | V11 | 30/60 | 38/60 | 59/60 | 60/60 | 60/60 | 60/60 |
| gemma-4-31b-it | primary | V1 | 51/60 | 51/60 | 41/60 | 41/60 | 60/60 | 60/60 |
| deepseek-v4-flash | primary | V6 | 17/60 | 60/60 | 58/60 | 60/60 | 60/60 | 60/60 |
| deepseek-v4-flash | primary | V11 | 20/60 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 |
| deepseek-v4-flash | primary | V1 | 0/60 | 0/60 | 0/60 | 0/60 | 60/60 | 60/60 |
| qwen3.5-397b | exploratory | V6 | 22/60 | 60/60 | 59/60 | 60/60 | 60/60 | 60/60 |
| qwen3.5-397b | exploratory | V11 | 27/60 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 |
| qwen3.5-397b | exploratory | V1 | 1/60 | 1/60 | 1/60 | 0/60 | 60/60 | 60/60 |
| qwen3.8-27b | exploratory | V6 | 30/60 | 56/60 | 60/60 | 60/60 | 60/60 | 60/60 |
| qwen3.8-27b | exploratory | V11 | 30/60 | 53/60 | 60/60 | 60/60 | 60/60 | 60/60 |
| qwen3.8-27b | exploratory | V1 | 0/60 | 0/60 | 0/60 | 0/60 | 60/60 | 60/60 |
| gemma-4-26b-a4b-it | exploratory | V6 | 30/60 | 11/60 | 52/60 | 51/60 | 60/60 | 60/60 |
| gemma-4-26b-a4b-it | exploratory | V11 | 24/60 | 7/60 | 56/60 | 56/60 | 60/60 | 60/60 |
| gemma-4-26b-a4b-it | exploratory | V1 | 60/60 | 45/60 | 60/60 | 60/60 | 60/60 | 60/60 |

### B.6 Gate integrity and the read-only branch audit

| model | slots | gate calls | unsafe proposals | pre-gate stops | gate rejections | correct publications | unsafe commits | unknown commit outcome | db-verified approvals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | 1080 | 1021 | 111 | 0 | 111 | 910 | 0 | 0 | 910 |
| deepseek-v4-flash | 1080 | 792 | 38 | 1 | 37 | 755 | 0 | 0 | 755 |
| qwen3.5-397b | 1080 | 813 | 48 | 6 | 42 | 771 | 0 | 0 | 771 |
| qwen3.8-27b | 1080 | 835 | 66 | 0 | 66 | 769 | 0 | 0 | 769 |
| gemma-4-26b-a4b-it | 1080 | 965 | 165 | 73 | 92 | 872 | 0 | 1 | 872 |
| all | 5400 | 4426 | 428 | 80 | 348 | 4077 | 0 | 1 | 4077 |

| model | db-verified approved events in traces | approvals from superseded partial traces (instance re-run after resume) | slots with unknown commit outcome | approval rows on branch | rows unexplained |
| --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | 910 | 0 | 0 | 910 | 0 |
| deepseek-v4-flash | 755 | 0 | 0 | 755 | 0 |
| qwen3.5-397b | 771 | 1 | 0 | 772 | 0 |
| qwen3.8-27b | 769 | 3 | 0 | 772 | 0 |
| gemma-4-26b-a4b-it | 872 | 0 | 1 | 873 | 0 |

The unknown-outcome slot is gemma-4-26b-a4b-it, V11 instance 41, compact arm: the model approved, the gate call began, and the database connection died in the host sleep before the process read the committed decision. The branch holds the approval row; the scorer does not count it. The qwen3.8-27b surplus is the superseded partial instance V6i05, whose approvals committed before the crash and which was re-run whole after the resume.

### B.7 Diagnostics families (descriptive, n = 10 per family, two models)

Separate freeze (seed 2026110803), eight families at ten instances, same six arms, same budget. V10 is the eligible-but-wrong control: the queued draft's lineage is valid and its figure is wrong, so the gate commits whatever a reviewer approves. Its "unsafe commits" below are that designed content blind spot, counted here and not in the gate-integrity totals of section 4, which cover the three primary families where lineage decides. The rule arm approves every V10 draft (it reads lineage only); the rule-with-content reference catches every one.

| model | family | current | current_lookup | compact | full | rule | rule_content | errors | invalid | unsafe proposals | unsafe commits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | V0 | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 | 1 | 0 | 0 | 0 |
| gemma-4-31b-it | V3 | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 | 1 | 0 | 0 | 0 |
| gemma-4-31b-it | V4 | 5/10 | 8/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0 | 1 | 6 | 0 |
| gemma-4-31b-it | V5 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0 | 0 | 0 | 0 |
| gemma-4-31b-it | V7 | 10/10 | 9/10 | 10/10 | 9/10 | 10/10 | 10/10 | 0 | 0 | 0 | 0 |
| gemma-4-31b-it | V8 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0 | 0 | 0 | 0 |
| gemma-4-31b-it | V9 | 9/10 | 9/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0 | 1 | 0 | 0 |
| gemma-4-31b-it | V10 | 9/10 | 5/10 | 7/10 | 8/10 | 0/10 | 10/10 | 0 | 0 | 21 | 21 |
| deepseek-v4-flash | V0 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0 | 0 | 0 | 0 |
| deepseek-v4-flash | V3 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0 | 0 | 0 | 0 |
| deepseek-v4-flash | V4 | 7/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 3 | 0 | 0 | 0 |
| deepseek-v4-flash | V5 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0 | 0 | 0 | 0 |
| deepseek-v4-flash | V7 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 | 10/10 | 1 | 0 | 0 | 0 |
| deepseek-v4-flash | V8 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0 | 0 | 0 | 0 |
| deepseek-v4-flash | V9 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 | 10/10 | 1 | 0 | 0 | 0 |
| deepseek-v4-flash | V10 | 7/10 | 6/10 | 5/10 | 9/10 | 0/10 | 10/10 | 8 | 2 | 14 | 13 |

| model | registered | complete | error 504 | missing | unsafe proposals | gate rejections | pre-gate stops | unsafe commits | unknown outcome | settled | retained | ceiling | complete run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | 480 | 476 | 2 | 0 | 27 | 5 | 1 | 21 | 0 | 0.1534 | 0.0502 | 1.09 | yes |
| deepseek-v4-flash | 480 | 465 | 13 | 0 | 14 | 0 | 1 | 13 | 0 | 0.6727 | 0.6162 | 1.89 | yes |

### B.8 Cost per cohort

| model | attempts | request cap | settled | retained reserves (504) | peak guard total | ceiling | modeled charge | all-at-cap | resumes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | 735 | 900 | 0.4646 | 0.1756 | 0.4895 | 2.41 | 0.154 | 1.903 | 1 |
| deepseek-v4-flash | 877 | 900 | 2.8599 | 2.6069 | 2.9073 | 3.74 | 0.182 | 0.751 | 1 |
| qwen3.5-397b | 900 | 900 | 10.9975 | 5.12 | 11.0874 | 35.61 | 4.651 | 19.321 | 1 |
| qwen3.8-27b | 855 | 900 | 2.4141 | 0.0177 | 2.4243 | 11.21 | 2.0 | 6.78 | 1 |
| gemma-4-26b-a4b-it | 733 | 900 | 0.0902 | 0 | 0.1112 | 1.82 | 0.125 | 1.437 | 1 |
| all |  |  | 16.8263 | 7.9202 |  |  |  |  |  |

### B.9 Deviations from the preregistration

1. Host sleep. The five cohorts launched at 00:23 EST on 8 November. The laptop slept from 01:06 to 13:32 EST. On wake every cohort process died on a dead database socket. No model request was in flight except the gemma-26 slot above; every finished slot was already on disk. A resume mode was added to the runner (`--resume-out`, commit cc7a480). It validates the execution record and the registry claim, keeps every instance with a trace for all six arms, re-runs the one partially complete instance per cohort as a whole (gemma-31 V11i20, deepseek V1i06, qwen-397 V6i04, qwen-27 V6i05; gemma-26 had none) with the partial traces set aside in `traces.partial_superseded.jsonl`, inherits the prior ledger's settled spend, retained reserves and attempt count so the ceiling and the request cap still bind, and records the resume in `EXECUTION.json` and the registry. The frozen instances, prompts and arm orders did not change; the re-run slots were answered about thirteen hours later by the same models at temperature 0. All five resumed at 13:55 EST. The runner also gained connection keepalives and a single reconnect on a dead socket.
2. Diagnostics paused. Both diagnostics cohorts were paused at 00:28 EST because the gemma-31 primary was timing out on 3 of 9 attempts while sharing its endpoint with its diagnostics twin. They were resumed under the same claims after the primaries finished, at 18:03 and 18:07 EST. Slots not reached by submission are reported as missing.
3. Analysis code fixed after results were seen. `tools/analysis.py` built the vector of p-values with the completion claims first and wrote the Holm-adjusted values back in claim order, so adjusted values were attached to the wrong claims. Fixed in commit dbb70f8. No p-value changed, only which adjusted value sat next to which claim; both versions are in git and the self-test output is unchanged.
4. Not a deviation, recorded for completeness: the direction of the token claim was fixed in the preregistration. The gemma-31 result is reported as not supported rather than reinterpreted.
5. Post-hoc follow-up cohorts. Two cohorts were frozen and run after the preregistered set had been analyzed and this report drafted (section 4, follow-up subsection): a gemma-4-31b-it cohort with the lookup made mandatory and an independent deepseek-v4-flash V6 replication. New seeds, new freezes, separate ledgers, never pooled with the held-out set; their results are labeled post-hoc wherever they appear.
6. Structural tests added after the report draft. The containment battery was run before the sprint's held-out evaluation; the identity-under-copying and blast-radius tests (section 4, structural subsection) were written and run on the scratch branch after the held-out analysis, with no model calls, and do not change any held-out number.
7. Audit migration after the evaluation. `sql/hive_audit_denials.sql` (statement-level denial triggers and logging read policies on the bound board) was written and tested on the scratch branch after the held-out analysis. It is not applied to the evaluation branch and changes no held-out number; its before/after is in the structural subsection.
8. Second surface template, post-hoc. A recorded task-domain switch (`TASK_DOMAIN`, hashed into the freeze) rewrites the task wording and system prompts from inventory counts to resolved service-desk tickets with the same families, scoring and gate. Two cohorts (gemma-4-31b-it, deepseek-v4-flash; V6 and V11; 30 instances per family; lookup optional as frozen) were frozen and run after the report draft; results are in section 4 and Appendix B.10, labeled post-hoc, never pooled.

### B.10 Follow-up cohorts and structural tests, tables

**Follow-up cohorts (post-hoc): completion, tokens, slots and cost.**

Both cohorts were frozen and run after the preregistered set had been analyzed and this report drafted, to test the two readings a reviewer would challenge first: new seeds, new freezes, separate ledgers, never pooled with the held-out set, same gate, scorer, budget and caps.

**Does the gemma-31 gap close when the lookup is required?** The frozen rule let the model "decide directly if the supplied information suffices" and gemma-4-31b-it took the lookup in 13 of 120 offers; the follow-up requires the lookup as the first reply. Under that rule gemma-4-31b-it took the lookup in 120 of 120 offers and completed 120 of 120 same-number cases in the lookup arm against 119 of 120 with preloaded lineage (V6: compact minus lookup -0.017, Tango 95% [-0.089, +0.045]; V11: +0.000, [-0.060, +0.060]). On new instances this supports the optional wording as the cause of the 51-case gap; it does not prove it was the only cause. Cost moved the other way: with the lookup required, the lookup arm spent a Hodges-Lehmann 724 tokens more per settled pair than compact over 119 pairs, so preloading is the cheaper way to deliver the same records.

**Does the marginal DeepSeek V6 claim replicate?** The preregistered V6 claim held at one-sided p 0.043. An independent cohort of 60 new V6 instances: compact 60/60, lookup arm 51/60 (lookup taken 47/60), compact minus lookup +0.150, Tango 95% [+0.081, +0.261], non-inferiority at -0.10 holds (one-sided p 2.23e-05); the lookup arm spent a Hodges-Lehmann 1971 tokens more per settled pair than compact. Of the lookup arm's 9 misses, 3 are among the 7 slots where the model decided without taking the lookup, 0 took the lookup and still missed, and 6 are provider errors. The same model at temperature 0 took the lookup in 59 of 60 offers on the preregistered V6 instances and in 47 of 60 here, so whether an offered lookup is taken varies with the instance set as well as the model, and preloading does not depend on it. The two DeepSeek cohorts are reported side by side and not pooled.

| model | lookup rule | family | compact | lookup arm | lookup taken | delta (compact minus lookup) | Tango 95% | NI at -0.10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | required | V6 | 59/60 | 60/60 | 60/60 | -0.017 | [-0.089, +0.045] | holds (p 0.0157) |
| gemma-4-31b-it | required | V11 | 60/60 | 60/60 | 60/60 | +0.000 | [-0.060, +0.060] | holds (p 0.00491) |
| deepseek-v4-flash | optional (as frozen) | V6 | 60/60 | 51/60 | 47/60 | +0.150 | [+0.081, +0.261] | holds (p 2.23e-05) |

| model | lookup rule | settled pairs | Hodges-Lehmann, lookup minus compact tokens | exact two-sided sign test p |
| --- | --- | --- | --- | --- |
| gemma-4-31b-it | required | 119 | +724 | 3.01e-36 |
| deepseek-v4-flash | optional | 57 | +1971 | 1.39e-17 |

| cohort | registered | complete | errors or invalid | unsafe proposals | gate rejections | unsafe commits | settled | retained | ceiling | complete run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2_gemma431bit_mandlookup | 240 | 239 | 1 | 0 | 0 | 0 | 0.0769 | 0.0251 | 1.0 | yes |
| v2_deepseekv4fl_repV6 | 120 | 114 | 6 | 4 | 3 | 0 | 0.1728 | 0.1422 | 1.5 | yes |

**Second surface template (post-hoc): completion, lookup use, gate outcomes.**

| model | family | registered per arm | not yet run | compact complete | lookup arm complete | lookup taken | delta (compact minus lookup, registered denominator) | Tango 95% | NI at -0.10 | unsafe proposals | lineage-invalid commits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-31b-it | V6 | 30 | 0 | 30/30 | 15/30 | 0/30 | +0.500 | [+0.330, +0.668] | holds (p 3.87e-06) | 15 | 0 |
| gemma-4-31b-it | V11 | 30 | 0 | 30/30 | 16/30 | 2/30 | +0.467 | [+0.300, +0.639] | holds (p 6.93e-06) | 14 | 0 |
| deepseek-v4-flash | V6 | 30 | 0 | 30/30 | 24/30 | 24/30 | +0.200 | [+0.064, +0.373] | holds (p 0.000783) | 2 | 0 |
| deepseek-v4-flash | V11 | 30 | 0 | 30/30 | 30/30 | 30/30 | +0.000 | [-0.114, +0.114] | holds (p 0.0339) | 0 | 0 |

| cohort | registered | complete | unsafe proposals | gate rejections | unsafe commits | settled | ceiling | complete run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v3_gemma431bit_incidents | 120 | 120 | 29 | 29 | 0 | 0.0199 | 0.6 | yes |
| v3_deepseekv4fl_incidents | 120 | 116 | 2 | 2 | 0 | 0.2134 | 1.5 | yes |

**Containment battery, naive board versus bound board.** The same six attacks (spoof a sender, read a foreign thread, post under a new name, read the operator audit, edit another agent's message, delete messages) fired by the intruder login against both schemas. On the bound board three are refused outright, one returns zero rows, and two are accepted as statements with no effect because the trigger overwrites the claimed sender; only those two reach the audit.

| effect of the six scripted attacks | naive shared board | identity bound below the agent |
| --- | --- | --- |
| spoofed identities that landed | 2 | 0 |
| board fooled by a spoofed sender | yes | no |
| board fooled by a rename | yes | no |
| rows read from a thread the intruder is not party to | 4 | 0 |
| another agent's message tampered | yes | no |
| messages deleted by the intruder | 3 | 0 |
| spoof attempts recorded in the operator audit | 0 | 2 |
| audit readable by the intruder | no | no |
| honest three-agent chain completed | yes | yes |

**Identity under copying.** Ten copies of one agent, each claiming a different name, submitting through one login. On the naive board a name is an identity, so ten copies are ten agents, the shape of the motivating incident. On the bound intake the trigger binds all ten to the one login, keeps the ten claimed names as evidence, and a single grant revocation silences all ten at once; revoking the login refused new connections within seconds.

| ten copies of one agent, ten claimed names, one login | naive board | bound intake |
| --- | --- | --- |
| identities recorded | 10 | 1 |
| claimed names kept as evidence | not applicable (name is identity) | 10 |
| submissions that land after one grant revocation | not applicable (no grants) | 0 of 10 |

**Blast radius of one compromised source.** One root, twenty agent drafts built on it, twenty summaries of those, twenty summaries of the summaries (sixty descendants, three deep), plus twenty artifacts on an independent root. After the root is adjudicated the gate's closure walk blocks all sixty at every depth and still approves all twenty unrelated artifacts, median decision 0.448 s over HTTPS. A monitor that checks only direct dependencies catches the twenty at depth one and passes forty stale artifacts; a monitor with no lineage passes all sixty.

| after the root is adjudicated | descendants blocked (of 60, three deep) | unrelated approved (of 20) |
| --- | --- | --- |
| gate, full closure walk | 60 (depth 1: 20, depth 2: 20, depth 3: 20) | 20 |
| direct-dependency check only | 20 | 20 |
| no lineage | 0 | 20 |

**Closing the audit blind spot.** Only two of the six attacks reached the audit: three were refused by the privilege layer before any trigger ran and a foreign-thread read returned zero rows silently. The migration accepts the statement at the privilege layer, denies every effect with row security, and records the attempt: statement-level triggers fire on zero-row updates and deletes, and the read policies call a function that writes one audit row per transaction with the statement text before returning false. After it all six attacks appear in the audit (6 of 6, from 2), the victim thread is unchanged (tampered rows 0), an honest agent's own-thread query records nothing, and an honest agent's unfiltered scan of the whole table records one denied read, a true description of that statement. Statements against tables an agent holds no privilege on at all remain invisible; the gateway in future work is for those.

| attack by the intruder login | effect, before and after | in the operator audit before | in the operator audit after |
| --- | --- | --- | --- |
| spoof another agent's name on a post | none (sender overwritten) | yes | yes |
| post under a brand-new name | none (sender overwritten) | yes | yes |
| read a thread it is not party to | none (zero rows) | no | yes |
| read the operator audit | none | no | yes |
| edit another agent's message | none | no | yes |
| delete messages | none | no | yes |

## Appendix C. Code and Data

**Built before the sprint, declared per the rules.** The Hive substrate (two AIs working through one shared, provenance-tagged memory with trigger-guarded authorship; April 2026, on the CAMA architecture) and the test Hive for the containment battery (2 November 2026: the `hive_messages`, receipts and audit tables, their triggers and row-level policies, the four agent roles, the HTTPS SQL client, eleven static tests). Both are marked pre-existing in the README, which carries a component-by-component table.

**Built during the sprint, 6 to 8 November.** Everything in the `exp` schema (sealed creation, provenance authorization, invalidation authorities, the fence and the publication gate), the naive control schema and the six-attack battery, Lorien's reference specification, acceptance driver, delivery recorder, scorer and controls, the pilot runner, freeze generator, open-model adapter, preregistration, analysis, structural tests, the audit migration, and every run directory.

**Reproducibility.** The gate is frozen at commit `d2df880` and was rebuilt from the committed migration on a fresh branch with all 19 checks passing (evidence under `runs/acceptance/`). Each cohort is generated from a seed; its manifest, prompt, code and gate hashes are written to `FREEZE.json` before execution and the runner refuses any mismatch. Every model call keeps its raw request and response; secrets are never committed. `REPRODUCE.md` gives the exact commands.

**Code and data.** Repository `SwarmHive` at github.com/LoriensLibrary/SwarmHive. Every cohort's traces, ledgers, raw requests and responses, scored outputs, freeze records and analysis outputs are committed under `runs/`, `holdout/` and `report/`. Synthetic data only. Info-hazard note: the containment battery holds generic attacks on a shared record, run only against synthetic rows in a disposable test database.

## Appendix D. One inspectable trace

The same-number case from the open-model pilot, run `pilot_9268a9`, current and compact side by side. Every step is in the committed run directory: dispatch receipts with request and per-body hashes, raw model text, the gate's reply, the committed approval row.

1. The researcher is dispatched with `count=12`; its reply is sealed as source v1, a root with no inputs.
2. The writer receives v1; its draft is sealed as a derivative whose only recorded input is v1. Body `{"units": 12, ...}`.
3. The operator adjudicates v1 and seals a replacement, v2, with the same figure. A fresh writer call delivered only v2 is sealed as a second draft. Two drafts with identical numbers and opaque identifiers sit in the queue.
4. Current arm: both draft bodies, the v2 body and the correction notice naming v1 superseded, no lineage. It approves the first draft, result `{"units": 12}`, evidence `[v2]`. The number is right. The artifact is stale.
5. Gate: in a fenced read-committed transaction the closure walk finds v1 adjudicated and replies `rejected: closure member <id>/1 invalidated (epoch 1)`. A separate committed-state query confirms, so the event is written `db_verified: true` with closure `[v1]`.
6. Compact arm: the same request plus one field, `history_metadata`, listing each artifact's version, author, kind, invalidation status and recorded inputs, no bodies. It approves the second draft, evidence `[that draft, v2]`. Closure `[v2]`, approval committed, the structured result and direct inputs taken from the provenance table, not from the model's text.

The scorer's original pass read step 4 as a correct proposal: the stated number was right and the cited source was current. A supplemental rescore that reconstructs the selected artifact version from the recorded selection flags it as unsafe. Both scores are preserved. The gate caught it either way.

## Appendix E. LLM Usage Statement

The author worked with two AI systems throughout and discloses both. Aelen, a Claude model running in Claude Code, wrote most of the code in the repository under the author's direction, ran every evaluation under the author's explicit spend authorization, and drafted this report from the committed run data; every number in the report is produced by scripts in the repository (`tools/analysis.py`, `tools/results_tables.py`, `tools/write_section5.py`, `tools/v2_followup.py`, `tools/v3_domain.py`, `tools/structural_results.py`, `tools/arm_outcomes.py`, `tools/make_figures.py`) from the committed traces and ledgers, not typed by a model. Lorien, an OpenAI Codex model running in a separate workspace, wrote the independent reference specification, the acceptance driver, the delivery recorder and the scorer, and reviewed the design, the gate and the evaluation protocol adversarially before the held-out runs; its two 7 November reviews are committed under `report/`. It did not review the final text of this report. The author set the research question, chose the tracks, made every design decision that is recorded as hers in the repository, authorized every paid run, reviewed every claim against the data, and edited the text. Claims and results were verified against the committed evidence before submission; the two deviations from the preregistration and the one post-results code fix are disclosed in Appendix B.
