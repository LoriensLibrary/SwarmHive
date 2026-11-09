"""Per-arm outcomes pooled over the five held-out cohorts (descriptive): what the reviewer sees, who enforces, how many unsafe
proposals, how many reached the gate and were rejected, how many were stopped before the gate, unsafe commits, correct publications.
Writes report/heldout_results/ARM_TABLE.md and arm_outcomes.json.  python -I tools/arm_outcomes.py
"""
import json, glob, collections, os
sees = {"current": "queued drafts, current source, correction notice; no lineage",
        "current_lookup": "current, plus one optional authenticated lookup of the lineage records",
        "compact": "current, plus lineage records preloaded (versions, delivered inputs, invalidation status)",
        "full": "compact, plus the historical bodies as recorded inputs",
        "rule": "lineage records only; approves the queued draft whose closure is valid",
        "rule_content": "rule, plus a check of the figure against the current source"}
enf = {"current": "model proposes; gate decides", "current_lookup": "model proposes; gate decides", "compact": "model proposes; gate decides",
       "full": "model proposes; gate decides", "rule": "deterministic; gate decides", "rule_content": "deterministic; gate decides"}
dirs = sorted(d for d in glob.glob("runs/holdout_heldout_*") if os.path.exists(d + "/scored.json") and os.path.exists(d + "/run_summary.json"))
agg = collections.defaultdict(collections.Counter)
for d in dirs:
    tr = {t["run_id"]: t for t in (json.loads(l) for l in open(d + "/traces.jsonl", encoding="utf-8"))}
    for l in open(d + "/scored.json", encoding="utf-8"):
        r = json.loads(l)
        if not r.get("run_id"): continue
        arm = r["condition"]; t = tr.get(r["run_id"], {})
        a = agg[arm]; a["registered"] += 1
        a["complete"] += r["status"] == "complete"
        a["unsafe_proposals"] += bool(r.get("proposed_bad_approval"))
        a["gate_rejections"] += int(r.get("gate_rejections") or 0)
        a["unsafe_commits"] += int(r.get("accepted_bad_actions") or 0)
        a["correct_publications"] += int(r.get("correct_publications") or 0)
        ev = t.get("gate_events") or []
        a["gate_calls"] += 1 if t.get("gate_called") else 0
order = ["current", "current_lookup", "compact", "full", "rule", "rule_content"]
rows = []
for arm in order:
    a = agg[arm]; stopped = a["unsafe_proposals"] - a["gate_rejections"]
    rows.append(dict(arm=arm, registered=a["registered"], complete=a["complete"], unsafe_proposals=a["unsafe_proposals"], rejected_at_gate=a["gate_rejections"],
                     stopped_before_gate=stopped, unsafe_commits=a["unsafe_commits"], correct_publications=a["correct_publications"]))
json.dump({"cohorts": dirs, "rows": rows}, open("report/heldout_results/arm_outcomes.json", "w"), indent=1)
hdr = "| arm | what the reviewer sees | enforcement | registered | complete | unsafe proposals | rejected at the gate | stopped before the gate | lineage-invalid commits | correct publications |"
sep = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
lines = [hdr, sep] + [f"| {r['arm'].replace('_', ' + ') if r['arm'] != 'rule_content' else 'rule + content'} | {sees[r['arm']]} | {enf[r['arm']]} | {r['registered']} | {r['complete']} | {r['unsafe_proposals']} | {r['rejected_at_gate']} | {r['stopped_before_gate']} | {r['unsafe_commits']} | {r['correct_publications']} |" for r in rows]
tot = {k: sum(r[k] for r in rows) for k in ("registered", "complete", "unsafe_proposals", "rejected_at_gate", "stopped_before_gate", "unsafe_commits", "correct_publications")}
lines.append(f"| all | | | {tot['registered']} | {tot['complete']} | {tot['unsafe_proposals']} | {tot['rejected_at_gate']} | {tot['stopped_before_gate']} | {tot['unsafe_commits']} | {tot['correct_publications']} |")
open("report/heldout_results/ARM_TABLE.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
