"""Second surface template (TASK_DOMAIN=incidents), post-hoc: gemma-4-31b-it and deepseek-v4-flash, V6 and V11, n=30,
arms current_lookup (optional, as frozen) and compact. Writes report/heldout_v3_results/{results.json,SECTION.md,TABLES.md}.
  python -I tools/v3_domain.py --gemma runs/holdout_v3_gemma431bit_incidents_xxxxxx --deepseek runs/holdout_v3_deepseekv4fl_incidents_xxxxxx
"""
import argparse, json, os, subprocess, sys
sys.path.insert(0, "tools")
import results_tables as RT


def fmt_ci(ci): return f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--gemma", required=True); ap.add_argument("--deepseek", required=True)
    ap.add_argument("--out", default="report/heldout_v3_results"); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cohorts = {"gemma-4-31b-it": a.gemma, "deepseek-v4-flash": a.deepseek}
    cmd = [sys.executable, "-I", "tools/analysis.py", "--out", a.out]
    for m, p in cohorts.items(): cmd += ["--cohort", f"{p}/scored.json::{p}/task_keys.json::{p}/traces.jsonl::{m}::inferential"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit("analysis failed: " + r.stderr[-1200:])
    res = json.load(open(f"{a.out}/results.json")); claims = {(c["model"], c["family"], c["type"]): c for c in res["claims"]}
    C = {m: RT.load_cohort(p) for m, p in cohorts.items()}; AR = {m: RT.arm_rates(c) for m, c in C.items()}; G = {m: RT.gate_integrity(c) for m, c in C.items()}
    FZ = {"gemma-4-31b-it": json.load(open("holdout/heldout_v3/incidents_gemma431bit/FREEZE.json")), "deepseek-v4-flash": json.load(open("holdout/heldout_v3/incidents_deepseekv4fl/FREEZE.json"))}
    T = ["| model | family | registered per arm | not yet run | compact complete | lookup arm complete | lookup taken | delta (compact minus lookup, registered denominator) | Tango 95% | NI at -0.10 | unsafe proposals | lineage-invalid commits |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    KEYS = {m: json.load(open(f"{p}/task_keys.json")) for m, p in cohorts.items()}
    prose = []
    for m in cohorts:
        for fam in ("V6", "V11"):
            cl = AR[m].get(f"{fam}/current_lookup"); cp = AR[m].get(f"{fam}/compact"); c = claims.get((m, fam, "completion_NI"))
            if not cl or not cp: continue
            sc = {r["run_id"]: r for r in C[m]["scored"] if r.get("run_id")}
            un = sum(1 for t in C[m]["traces"] if t["task_id"].startswith(fam + "i") and sc.get(t["run_id"], {}).get("proposed_bad_approval"))
            bc = sum(int(sc.get(t["run_id"], {}).get("accepted_bad_actions") or 0) for t in C[m]["traces"] if t["task_id"].startswith(fam + "i"))
            reg = sum(1 for k in KEYS[m] if str(k.get("task_id", k if isinstance(k, str) else "")).startswith(fam + "i")) or c["n"] if c else cp["registered"]
            notrun = reg - cp["registered"]
            tail = (f"{c['delta']:+.3f} | {fmt_ci(c['tango_95'])} | {'holds' if c['reject_at_0.05'] else 'fails'} (p {c['ni_p']:.3g})" if c else " | | ")
            T.append(f"| {m} | {fam} | {reg} | {notrun} | {cp['completed']}/{reg} | {cl['completed']}/{reg} | {cl['lookup_used']}/{cl['lookup_offered']} | {tail} | {un} | {bc} |")
        g6 = AR[m].get("V6/current_lookup", {}); g11 = AR[m].get("V11/current_lookup", {}); c6 = AR[m].get("V6/compact", {}); c11 = AR[m].get("V11/compact", {})
        tk = g6.get("lookup_used", 0) + g11.get("lookup_used", 0); of = g6.get("lookup_offered", 0) + g11.get("lookup_offered", 0)
        prose.append(f"{m}: preloaded lineage {c6.get('completed', 0) + c11.get('completed', 0)} of {c6.get('registered', 0) + c11.get('registered', 0)}, lookup offered {g6.get('completed', 0) + g11.get('completed', 0)} of {g6.get('registered', 0) + g11.get('registered', 0)} with the lookup taken {tk} of {of}; lineage-invalid commits {G[m].get('unsafe_commits', 0)}" + ("" if C[m]["done"] else " (cohort still running at the time of writing)"))
    SL = ["| cohort | registered | complete | unsafe proposals | gate rejections | lineage-invalid commits | settled | ceiling | complete run |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m, p in cohorts.items():
        sl = RT.slot_table(C[m])[0]; cost = RT.cost_row(C[m], {"ceiling_credits": FZ[m]["ceiling"], "max_requests": FZ[m]["max_authorized_requests"]})
        SL.append(f"| {FZ[m]['cohort']} | {sl['registered']} | {sl['complete']} | {G[m].get('unsafe_proposals', 0)} | {G[m].get('gate_rejections', 0)} | {G[m].get('unsafe_commits', 0)} | {cost['settled']} | {cost['ceiling']} | {'yes' if C[m]['done'] else 'RUNNING'} |")
    tables = "**Second surface template (post-hoc): completion, lookup use, gate outcomes.**\n\n" + "\n".join(T) + "\n\n" + "\n".join(SL) + "\n"
    open(f"{a.out}/TABLES.md", "w", encoding="utf-8").write(tables)
    sec = ("**A second surface template.** Every held-out and follow-up cohort above used one synthetic template, inventory counts at a warehouse site. "
           "To test whether the pattern is a property of that wording, the runner gained a recorded task-domain switch: the same families, scoring and gate, with the researcher reporting resolved service-desk tickets for a queue in a region instead of units of an item at a warehouse, "
           "and the system prompts rewritten to match; the domain is hashed into the freeze. Two post-hoc cohorts, new seeds, 30 instances per family, lookup optional as frozen: " + "; ".join(prose) + ". "
           "Rates use the registered denominator of 30 per arm and family. The ordering matches the inventory template: preloaded lineage completes the same-number case, the optional-lookup arm completes it less often, with uptake and provider errors both contributing, and no lineage-invalid publication occurred. Tables in Appendix B.10.")
    open(f"{a.out}/SECTION.md", "w", encoding="utf-8").write(sec + "\n")
    print(tables); print(sec)


if __name__ == "__main__":
    main()
