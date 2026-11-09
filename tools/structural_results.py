"""Structural (deterministic, no-model) results for the report: containment battery naive vs bound, identity under copying,
blast radius of a compromised source. Reads committed run outputs; writes report/structural/SECTION.md.
  python -I tools/structural_results.py
"""
import json, os
os.makedirs("report/structural", exist_ok=True)
nv = json.load(open("runs/naive_r2/result.json", encoding="utf-8"))["counts"]
bd = json.load(open("runs/bound_hardened/result.json", encoding="utf-8"))["counts"]
idc = json.load(open("runs/identity_copies_latest.json"))
br = json.load(open("runs/blast_radius_latest.json"))
ad = json.load(open("runs/audit_denials_latest.json"))

def yn(v): return "yes" if v in (True, "true", "t") else "no"
rows = [("spoofed identities that landed", nv["spoofed_identities_landed"], bd["spoofed_identities_landed"]),
        ("board fooled by a spoofed sender", yn(nv["spoof_fooled_board"]), yn(bd["spoof_fooled_board"])),
        ("board fooled by a rename", yn(nv["rename_fooled_board"]), yn(bd["rename_fooled_board"])),
        ("rows read from a thread the intruder is not party to", nv["foreign_thread_rows_read"], bd["foreign_thread_rows_read"]),
        ("another agent's message tampered", yn(nv["message_tampered"]), yn(bd["message_tampered"])),
        ("messages deleted by the intruder", nv["messages_deleted_by_intruder"], bd["messages_deleted_by_intruder"]),
        ("spoof attempts recorded in the operator audit", nv["spoof_attempts_logged"], bd["spoof_attempts_logged"]),
        ("audit readable by the intruder", yn(nv["audit_readable_by_intruder"]), yn(bd["audit_readable_by_intruder"])),
        ("honest three-agent chain completed", yn(nv["honest_chain_completed"]), yn(bd["honest_chain_completed"]))]
T1 = ["| effect of the six scripted attacks | naive shared board | identity bound below the agent |", "| --- | --- | --- |"] + [f"| {a} | {b} | {c} |" for a, b, c in rows]
T2 = ["| ten copies of one agent, ten claimed names, one login | naive board | bound intake |", "| --- | --- | --- |",
      f"| identities recorded | {idc['naive_identities']} | {idc['bound_identities']} |",
      f"| claimed names kept as evidence | not applicable (name is identity) | {idc['claimed_names']} |",
      f"| submissions that land after one grant revocation | not applicable (no grants) | {idc['after_revoke_landed']} of 10 |"]
T3 = ["| after the root is adjudicated | descendants blocked (of 60, three deep) | unrelated approved (of 20) |", "| --- | --- | --- |",
      f"| gate, full closure walk | {br['gate_blocked']} (depth 1: {br['by_depth']['1']}, depth 2: {br['by_depth']['2']}, depth 3: {br['by_depth']['3']}) | {br['unrelated_approved']} |",
      f"| direct-dependency check only | {br['direct_check_catches']} | 20 |",
      f"| no lineage | 0 | 20 |"]
vis = ad["visible"]
T4 = ["| attack by the intruder login | effect, before and after | in the operator audit before | in the operator audit after |", "| --- | --- | --- | --- |",
      f"| spoof another agent's name on a post | none (sender overwritten) | yes | {'yes' if vis['spoof_sender'] else 'no'} |",
      f"| post under a brand-new name | none (sender overwritten) | yes | {'yes' if vis['rename_identity'] else 'no'} |",
      f"| read a thread it is not party to | none (zero rows) | no | {'yes' if vis['read_foreign_thread'] else 'no'} |",
      f"| read the operator audit | none | no | {'yes' if vis['read_audit'] else 'no'} |",
      f"| edit another agent's message | none | no | {'yes' if vis['tamper_message'] else 'no'} |",
      f"| delete messages | none | no | {'yes' if vis['delete_message'] else 'no'} |"]
sec = f"""Four deterministic tests run on a disposable branch with no model calls. They measure the substrate's structural claims directly, with the honest agents model-driven where agents act and the attacker a fixed script, because a model asked to impersonate another agent declined the role.

**Containment battery, naive board versus bound board.** The same six attacks (spoof a sender, rename, read a foreign thread, edit another agent's message, delete, replay) fired by the intruder login against both schemas. Three of the six are refused outright on the bound board and three are accepted as statements with no effect, because the trigger overwrites the claimed sender and the audit records the attempt. The report's earlier limitation stands: the three refused statements leave no application audit row, because the database rejects them before any trigger runs.

{chr(10).join(T1)}

**Identity under copying.** Ten copies of one agent, each claiming a different name, submitting through one login (`tools/identity_copies_test.py`). On the naive board a name is an identity, so ten copies are ten agents, which is the shape of the motivating incident. On the bound intake the trigger binds all ten to the one authenticated login, keeps the ten claimed names as evidence, and a single grant revocation silences all ten at once; revoking the login itself refused new connections within seconds on the HTTP path.

{chr(10).join(T2)}

**Blast radius of one compromised source.** One root, twenty agent drafts built on it, twenty summaries of those, twenty summaries of the summaries (sixty descendants, three deep), plus twenty artifacts on an independent root (`tools/blast_radius_test.py`). Before the root is adjudicated, descendants publish. After it, the gate's closure walk blocks all sixty at every depth and still approves all twenty unrelated artifacts, with a median publish decision of {br['publish_median_s']} s over HTTPS. A monitor that checks only direct dependencies, the common design, catches the twenty at depth one and passes forty stale artifacts; a monitor with no lineage passes all sixty. This is what "a correction does not un-write the summaries built on it" costs without sealed lineage, and what it costs with it.

{chr(10).join(T3)}

**Closing the audit blind spot.** The battery measured a limitation: three of the six attacks were refused by the database's privilege layer before any trigger ran, so the operator audit never saw them, and a read of a foreign thread returned zero rows silently. We closed it after the evaluation with an additive migration (`sql/hive_audit_denials.sql`, tested by `tools/audit_denials_test.py`, scratch branch only, not part of the frozen gate the held-out cohorts ran on). The attempt is accepted at the privilege layer and denied by row security, so it still has no effect, and the attempt itself is recorded: statement-level triggers fire on zero-row updates and deletes, and the read policies call a function that writes one audit row per transaction with the statement text before returning false. After the migration all six attacks appear in the audit ({ad['attacks_visible_in_audit']} of 6, from 3 of 6), the victim thread is unchanged (tampered rows {ad['tampered']}), an honest agent's own-thread query records nothing ({ad['honest_own_query_false_positives']} rows), and an honest agent's unfiltered scan of the whole table records one denied read, which is a true description of that statement: it asked for rows it may not see. Raw statements against tables the agents hold no privilege on at all remain invisible; the gateway in future work is for those.

{chr(10).join(T4)}
"""
open("report/structural/SECTION.md", "w", encoding="utf-8").write(sec); print(sec)
