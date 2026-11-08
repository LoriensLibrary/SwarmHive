## 1. Introduction

In July 2026 about 1,200 agents inside a security evaluation found a shared directory, turned it into a message board, and roughly 700 of them broke into Hugging Face's systems together. METR's investigation put the board at about 1,200 participants, about 700 taking part in the attack, with transcript spoofing in about 7 percent of the transcripts it evaluated; the Swarm Traces reconstruction counted 7,905 distinct names across those agents. We use the incident as motivation, not as a topology we claim to model. Our testbed has four agents, one trusted operator, and no network dynamics.

The failure we isolate is narrower and, we think, more common than a break-in: stale evidence after a correction. One agent reports a figure, a second summarizes it, a third summarizes the summary; then the figure is withdrawn and replaced. The summaries still exist, still read as confident, and still sit in the review queue. A reviewer that cannot see lineage can approve the stale summary because the prose sounds current, can refuse everything, which is safe and useless, or, in the hardest case, can face two drafts with the identical number, one descending from the withdrawn source and one from the replacement, with no way to tell them apart.

The measured contribution is a Track 4 evaluation: a publication gate that re-reads authenticated lineage, a matched reviewer comparison, and an independent scorer that resolves lineage itself rather than trusting what a model cites. It runs on a Track 3 substrate with identity bound to the database login below the agent: each agent submits over its own login, a trigger overwrites any claimed name, and the runtime seals from that authenticated row, so no author label in a trace is asserted by the harness. Two agents sharing one login are one identity to the gate.

The trust boundary is explicit. One operator seals, adjudicates and publishes; if that operator is compromised, every property below fails. We claim only that, given a trusted runtime, identity can be bound below the agent, lineage can be recorded by the runtime rather than asserted by the model, and a reviewer given that lineage behaves measurably differently from one that is not.

**Contributions.**

1. A tested multi-agent failure: stale evidence surviving a correction through summarization, including the case where the number is unchanged and only the authorization is.
2. Its recovery under a publication gate agents cannot write around, every claimed property verified by a second, independently written implementation and reproduced from source on a fresh database branch.
3. A preregistered matched evaluation others can rerun: fixed-input dispatch, a scorer that resolves lineage itself, opaque identifiers, registered denominators, frozen hashes and hard spend ceilings, with its failed claims reported as failed.
4. The result that whether preloaded authenticated lineage beats on-demand retrieval turns on whether the model takes the retrieval, and that false quarantine under a correction notice is model behavior rather than a property of lineage.

## 2. Related Work

None of the primitives are new. Immutable versioned artifacts, a provenance graph, authority-checked invalidation and a gate that re-reads dependency state are established engineering: version control, build systems, and provenance standards such as W3C PROV. Persistent, provenance-aware memory for human-AI systems is the subject of the first author's prior preprints on the CAMA architecture, and the Hive substrate this entry runs on was built on it in April 2026. AI control protocols in which a trusted model oversees an untrusted one, and Apart's earlier multi-agent security sprints, are the nearest neighbors on the evaluation side; the brief's references on collusion, spread and steganographic coordination frame the wider problem this entry does not attempt.

## 3. Methods

### 3.1 The gate

