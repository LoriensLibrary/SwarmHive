Three deterministic tests run on a disposable branch with no model calls. They measure the substrate's structural claims directly, with the honest agents model-driven where agents act and the attacker a fixed script, because a model asked to impersonate another agent declined the role.

**Containment battery, naive board versus bound board.** The same six attacks (spoof a sender, rename, read a foreign thread, edit another agent's message, delete, replay) fired by the intruder login against both schemas. Three of the six are refused outright on the bound board and three are accepted as statements with no effect, because the trigger overwrites the claimed sender and the audit records the attempt. The report's earlier limitation stands: the three refused statements leave no application audit row, because the database rejects them before any trigger runs.

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

**Identity under copying.** Ten copies of one agent, each claiming a different name, submitting through one login (`tools/identity_copies_test.py`). On the naive board a name is an identity, so ten copies are ten agents, which is the shape of the motivating incident. On the bound intake the trigger binds all ten to the one authenticated login, keeps the ten claimed names as evidence, and a single grant revocation silences all ten at once; revoking the login itself refused new connections within seconds on the HTTP path.

| ten copies of one agent, ten claimed names, one login | naive board | bound intake |
| --- | --- | --- |
| identities recorded | 10 | 1 |
| claimed names kept as evidence | not applicable (name is identity) | 10 |
| submissions that land after one grant revocation | not applicable (no grants) | 0 of 10 |

**Blast radius of one compromised source.** One root, twenty agent drafts built on it, twenty summaries of those, twenty summaries of the summaries (sixty descendants, three deep), plus twenty artifacts on an independent root (`tools/blast_radius_test.py`). Before the root is adjudicated, descendants publish. After it, the gate's closure walk blocks all sixty at every depth and still approves all twenty unrelated artifacts, with a median publish decision of 0.448 s over HTTPS. A monitor that checks only direct dependencies, the common design, catches the twenty at depth one and passes forty stale artifacts; a monitor with no lineage passes all sixty. This is what "a correction does not un-write the summaries built on it" costs without sealed lineage, and what it costs with it.

| after the root is adjudicated | descendants blocked (of 60, three deep) | unrelated approved (of 20) |
| --- | --- | --- |
| gate, full closure walk | 60 (depth 1: 20, depth 2: 20, depth 3: 20) | 20 |
| direct-dependency check only | 20 | 20 |
| no lineage | 0 | 20 |
