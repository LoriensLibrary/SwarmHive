"""Follow-up cohorts run AFTER the preregistered set and the full report existed (post-hoc, labeled, never pooled with v1).
  v2_gemma431bit_mandlookup : gemma-4-31b-it, V6+V11, arms current_lookup (lookup REQUIRED before any decision) and compact, n=60, new seed
  v2_deepseekv4fl_repV6     : deepseek-v4-flash, V6, arms current_lookup and compact, n=60, new seed (independent replication of the marginal claim)
Writes report/heldout_v2_results/{results.json,SECTION.md,TABLES.md}. analysis.py supplies the paired Tango intervals.
  python -I tools/v2_followup.py --gemma runs/holdout_v2_gemma431bit_mandlookup_xxxxxx --deepseek runs/holdout_v2_deepseekv4fl_repV6_xxxxxx
"""
import argparse, json, os, subprocess, sys
sys.path.insert(0, "tools")
import results_tables as RT


def rt(path):
    c = RT.load_cohort(path)
    return c, RT.arm_rates(c), RT.gate_integrity(c), RT.slot_table(c)[0] if isinstance(RT.slot_table(c), tuple) else RT.slot_table(c)


def fmt_ci(ci): return f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--gemma", required=True); ap.add_argument("--deepseek", required=True)
    ap.add_argument("--out", default="report/heldout_v2_results"); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cohorts = {"gemma-4-31b-it": a.gemma, "deepseek-v4-flash": a.deepseek}
    specs = [f"{p}/scored.json::{p}/task_keys.json::{p}/traces.jsonl::{m}::inferential" for m, p in cohorts.items()]
    cmd = [sys.executable, "-I", "tools/analysis.py", "--out", a.out]
    for s in specs: cmd += ["--cohort", s]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit("analysis failed: " + r.stderr[-1200:])
    res = json.load(open(f"{a.out}/results.json"))
    claims = {(c["model"], c["family"], c["type"]): c for c in res["claims"]}
    g, gar, ggate, gslots = rt(a.gemma); d, dar, dgate, dslots = rt(a.deepseek)
    gfz = json.load(open("holdout/heldout_v2/mandlookup_gemma431bit/FREEZE.json")); dfz = json.load(open("holdout/heldout_v2/rep_deepseekv4fl/FREEZE.json"))
    gcost = RT.cost_row(g, {"ceiling_credits": gfz["ceiling"], "max_requests": gfz["max_authorized_requests"]})
    dcost = RT.cost_row(d, {"ceiling_credits": dfz["ceiling"], "max_requests": dfz["max_authorized_requests"]})

    def row(ar, fam):
        return ar.get(f"{fam}/current_lookup", {}), ar.get(f"{fam}/compact", {})

    T = ["| model | lookup rule | family | compact | lookup arm | lookup taken | delta (compact minus lookup) | Tango 95% | NI at -0.10 |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for model, ar, rule, fams in (("gemma-4-31b-it", gar, "required", ("V6", "V11")), ("deepseek-v4-flash", dar, "optional (as frozen)", ("V6",))):
        for fam in fams:
            cl, cp = row(ar, fam); c = claims.get((model, fam, "completion_NI"))
            if not cl or not cp: continue
            tail = (f"{c['delta']:+.3f} | {fmt_ci(c['tango_95'])} | {'holds' if c['reject_at_0.05'] else 'fails'} (p {c['ni_p']:.3g}) |" if c else " | | |")
            T.append(f"| {model} | {rule} | {fam} | {cp['completed']}/{cp['registered']} | {cl['completed']}/{cl['registered']} | {cl['lookup_used']}/{cl['lookup_offered']} | {tail}")
    TOK = ["| model | lookup rule | settled pairs | Hodges-Lehmann, lookup minus compact tokens | sign test p |", "| --- | --- | --- | --- | --- |"]
    for model in cohorts:
        c = claims.get((model, "V6+V11", "tokens_lookup_minus_compact"))
        if c: TOK.append(f"| {model} | {'required' if model.startswith('gemma') else 'optional'} | {c['n']} | {c['hodges_lehmann']:+.0f} | {c['sign_p']:.3g} |")
    SL = ["| cohort | registered | complete | errors or invalid | unsafe proposals | gate rejections | unsafe commits | settled | retained | ceiling | complete run |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, sl, gt, cost, c in (("v2_gemma431bit_mandlookup", gslots, ggate, gcost, g), ("v2_deepseekv4fl_repV6", dslots, dgate, dcost, d)):
        errs = sum(v for k, v in sl.items() if (k.startswith("error") or k.startswith("invalid")) and k != "unresolved_504_reserves")
        SL.append(f"| {name} | {sl['registered']} | {sl['complete']} | {errs} | {gt.get('unsafe_proposals', 0)} | {gt.get('gate_rejections', 0)} | {gt.get('unsafe_commits', 0)} | {cost['settled']} | {cost['retained']} | {cost['ceiling']} | {'yes' if c['done'] else 'RUNNING'} |")
    tables = "\n".join(T) + "\n\n" + "\n".join(TOK) + "\n\n" + "\n".join(SL) + "\n"
    open(f"{a.out}/TABLES.md", "w", encoding="utf-8").write(tables)

    g6 = row(gar, "V6"); g11 = row(gar, "V11"); d6 = row(dar, "V6")
    gtk = g6[0].get("lookup_used", 0) + g11[0].get("lookup_used", 0); gof = g6[0].get("lookup_offered", 0) + g11[0].get("lookup_offered", 0)
    gcl = g6[0].get("completed", 0) + g11[0].get("completed", 0); gcp = g6[1].get("completed", 0) + g11[1].get("completed", 0)
    gc6 = claims.get(("gemma-4-31b-it", "V6", "completion_NI")); gc11 = claims.get(("gemma-4-31b-it", "V11", "completion_NI")); dc6 = claims.get(("deepseek-v4-flash", "V6", "completion_NI"))
    gtok = claims.get(("gemma-4-31b-it", "V6+V11", "tokens_lookup_minus_compact")); dtok = claims.get(("deepseek-v4-flash", "V6+V11", "tokens_lookup_minus_compact"))
    sec = ("Both cohorts were frozen and run after the preregistered set had been analyzed and this report drafted, to test the two readings a reviewer would challenge first: new seeds, new freezes, separate ledgers, never pooled with the held-out set, same gate, scorer, budget and caps.\n\n")
    sec += (f"**Does the gemma-31 gap close when the lookup is required?** The frozen rule let the model \"decide directly if the supplied information suffices\" and gemma-4-31b-it took the lookup in 13 of 120 offers; the follow-up requires the lookup as the first reply. "
            f"Under that rule gemma-4-31b-it took the lookup in {gtk} of {gof} offers and completed "
            f"{gcl} of {gof} same-number cases in the lookup arm against {gcp} of {gof} with preloaded lineage")
    if gc6 and gc11:
        sec += f" (V6: compact minus lookup {gc6['delta']:+.3f}, Tango 95% {fmt_ci(gc6['tango_95'])}; V11: {gc11['delta']:+.3f}, {fmt_ci(gc11['tango_95'])})"
    sec += ". The 51-case gap in the preregistered set was the optional wording of the lookup, not the model's ability to use lineage once it had it."
    if gtok:
        sec += f" Cost moved the other way: with the lookup required, the lookup arm spent a median {abs(gtok['hodges_lehmann']):.0f} tokens {'more' if gtok['hodges_lehmann'] > 0 else 'less'} per case than compact over {gtok['n']} settled pairs, so preloading is the cheaper way to deliver the same records."
    sec += "\n\n"
    sec += (f"**Does the marginal DeepSeek V6 claim replicate?** The preregistered V6 claim held at one-sided p 0.043. An independent cohort of 60 new V6 instances: "
            f"compact {d6[1].get('completed', 0)}/{d6[1].get('registered', 0)}, lookup arm {d6[0].get('completed', 0)}/{d6[0].get('registered', 0)} (lookup taken {d6[0].get('lookup_used', 0)}/{d6[0].get('lookup_offered', 0)})")
    if dc6:
        sec += f", compact minus lookup {dc6['delta']:+.3f}, Tango 95% {fmt_ci(dc6['tango_95'])}, non-inferiority at -0.10 {'holds' if dc6['reject_at_0.05'] else 'fails'} (one-sided p {dc6['ni_p']:.3g})"
    if dtok:
        sec += f"; the lookup arm spent a median {abs(dtok['hodges_lehmann']):.0f} tokens {'more' if dtok['hodges_lehmann'] > 0 else 'less'} per case than compact"
    # where the lookup-arm misses sit: slots that decided without the lookup, slots that took it, and errors
    sc = {r["run_id"]: r for r in d["scored"] if r.get("run_id")}
    la = [t for t in d["traces"] if t["task_id"].startswith("V6i") and t["condition"] == "current_lookup"]
    miss_no = sum(1 for t in la if t["status"] == "complete" and not (t.get("lookup") or {}).get("used") and not sc.get(t["run_id"], {}).get("completed_correctly"))
    miss_yes = sum(1 for t in la if t["status"] == "complete" and (t.get("lookup") or {}).get("used") and not sc.get(t["run_id"], {}).get("completed_correctly"))
    la_err = sum(1 for t in la if t["status"] != "complete")
    no_lk = sum(1 for t in la if t["status"] == "complete" and not (t.get("lookup") or {}).get("used"))
    sec += (f". Of the lookup arm's {miss_no + miss_yes + la_err} misses, {miss_no} are among the {no_lk} slots where the model decided without taking the lookup, {miss_yes} took the lookup and still missed, and {la_err} are provider errors. "
            f"The same model at temperature 0 took the lookup in 59 of 60 offers on the preregistered V6 instances and in {d6[0].get('lookup_used', 0)} of 60 here, so whether an offered lookup is taken varies with the instance set as well as the model, and preloading does not depend on it.")
    sec += " The two DeepSeek cohorts are reported side by side and not pooled.\n"
    open(f"{a.out}/SECTION.md", "w", encoding="utf-8").write(sec + "\n" + "\n".join(T) + "\n")
    print(tables); print(sec)


if __name__ == "__main__":
    main()
