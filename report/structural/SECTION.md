Four deterministic tests run on a disposable branch with no model calls. They measure the substrate's structural claims directly, with the honest agents model-driven where agents act and the attacker a fixed script, because a model asked to impersonate another agent declined the role.

**Containment battery, naive board versus bound board.** The same six attacks (spoof a sender, rename, read a foreign thread, edit another agent's message, delete, replay) fired by the intruder login against both schemas. On the bound board three are refused outright and three are accepted as statements with no effect, because the trigger overwrites the claimed sender and the audit records the attempt.

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

**Identity under copying.** Ten copies of one agent, each claiming a different name, submitting through one login (`tools/identity_copies_test.py`). On the naive board a name is an identity, so ten copies are ten agents, the shape of the motivating incident. On the bound intake the trigger binds all ten to the one login, keeps the ten claimed names as evidence, and a single grant revocation silences all ten at once; revoking the login refused new connections within seconds.

| ten copies of one agent, ten claimed names, one login | naive board | bound intake |
| --- | --- | --- |
| identities recorded | 10 | 1 |
| claimed names kept as evidence | not applicable (name is identity) | 10 |
| submissions that land after one grant revocation | not applicable (no grants) | 0 of 10 |

**Blast radius of one compromised source.** One root, twenty agent drafts built on it, twenty summaries of those, twenty summaries of the summaries (sixty descendants, three deep), plus twenty artifacts on an independent root (`tools/blast_radius_test.py`). After the root is adjudicated the gate's closure walk blocks all sixty at every depth and still approves all twenty unrelated artifacts, median decision 0.448 s over HTTPS. A monitor that checks only direct dependencies, the common design, catches the twenty at depth one and passes forty stale artifacts; a monitor with no lineage passes all sixty.

| after the root is adjudicated | descendants blocked (of 60, three deep) | unrelated approved (of 20) |
| --- | --- | --- |
| gate, full closure walk | 60 (depth 1: 20, depth 2: 20, depth 3: 20) | 20 |
| direct-dependency check only | 20 | 20 |
| no lineage | 0 | 20 |

**Closing the audit blind spot.** Three of the six attacks were refused by the privilege layer before any trigger ran, so the audit never saw them, and a foreign-thread read returned zero rows silently. After the evaluation we closed this with an additive migration (`sql/hive_audit_denials.sql`, `tools/audit_denials_test.py`, scratch branch only, not on the frozen gate): the statement is accepted at the privilege layer, row security denies every effect, and the attempt is recorded, by statement-level triggers that fire on zero-row updates and deletes and by read policies that log once per transaction with the statement text. All six attacks now appear in the audit (6 of 6, from 3), the victim thread is unchanged (tampered rows 0), an honest agent's own-thread query records nothing, and an honest agent's unfiltered scan records one denied read, a true description of that statement. Statements against tables an agent holds no privilege on remain invisible; the gateway in future work is for those.

| attack by the intruder login | effect, before and after | in the operator audit before | in the operator audit after |
| --- | --- | --- | --- |
| spoof another agent's name on a post | none (sender overwritten) | yes | yes |
| post under a brand-new name | none (sender overwritten) | yes | yes |
| read a thread it is not party to | none (zero rows) | no | yes |
| read the operator audit | none | no | yes |
| edit another agent's message | none | no | yes |
| delete messages | none | no | yes |
