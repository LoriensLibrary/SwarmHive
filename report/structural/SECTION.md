Four deterministic tests on a disposable branch with no model calls; the attacker is a fixed script because a model asked to impersonate another agent declined the role. Full prose and tables in Appendix B.10.

**Containment, naive versus bound.** The same six attacks against both boards. Naive: two spoofed identities landed, a rename fooled the board, four foreign rows read, one message tampered, three deleted, nothing logged. Bound: every count zero, two spoof attempts in the operator audit, honest chain complete on both.

**Identity under copying.** Ten copies of one agent with ten claimed names through one login: ten identities on the naive board, one on the bound intake with the ten names kept as evidence, and one grant revocation silenced all ten (`tools/identity_copies_test.py`).

**Blast radius.** One adjudicated root, sixty descendants three deep, twenty unrelated: the closure walk blocked 60 of 60 at every depth and approved 20 of 20 unrelated at a median 0.448 s; a direct-dependency check catches 20 of 60; no lineage catches none (`tools/blast_radius_test.py`).

**Audit blind spot, closed after the evaluation.** Only two of the six attacks reached the audit: three were refused by the privilege layer before any trigger ran and a foreign-thread read returned zero rows silently. `sql/hive_audit_denials.sql` accepts the statement, denies every effect with row security, and records the attempt (statement-level triggers for zero-row updates and deletes, logging read policies): 6 of 6 attacks now visible (from 2), effects still zero, no false positives on an honest agent's own-thread reads. Scratch branch only, not on the frozen gate.
