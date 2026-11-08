"""Preregistered analysis for the held-out evaluation (report/HELDOUT_PREREGISTRATION.md, sections 4 and 5).

Inputs: one or more scored JSONL files from tools/vendor/score_runs.py plus the matching task_keys.json and
traces.jsonl, one set per cohort. Outputs a JSON summary and a Markdown table.

Inferential claims (Holm, family-wise 0.05):
  completion non-inferiority, compact vs lookup-offered, families V6 and V11, per inferential-tier model  (4 claims)
  tokens per registered case, compact vs lookup-offered, per inferential-tier model                     (2 claims)
Everything else is descriptive (V1 false quarantine, current, full, rule arms, exploratory tier, calls).

Paired binary difference: Tango's score interval (restricted MLE of the discordant cell under H0: p1 - p2 = d),
never a percentile bootstrap (all-tie data would give a degenerate interval). Non-inferiority: lower one-sided
score bound of (compact - lookup) above -MARGIN.

  python -I tools/analysis.py --synthetic                 # self-test on all-tie and discordant cases
  python -I tools/analysis.py --cohort <scored.jsonl>::<task_keys.json>::<traces.jsonl>::<model>::<tier> ... --out report/heldout_results
"""
import argparse, json, math, os, statistics, collections

MARGIN = 0.10
ALPHA = 0.05


def norm_ppf(p):
    # Acklam's rational approximation, adequate for interval bounds
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def tango_z(n12, n21, n, d):
    """Score statistic for H0: p1 - p2 = d, with p1 = P(compact yes), p2 = P(lookup yes); n12 = compact yes & lookup no."""
    B = (n12 + n21) - d * (2 * n - n12 + n21)
    q = (B + math.sqrt(max(0.0, B * B + 8 * n * n21 * d * (1 - d)))) / (4 * n)   # restricted MLE of p21 under H0; clamp guards float error at the d = -1 endpoint
    var = n * (2 * q + d * (1 - d))
    num = n12 - n21 - n * d
    if var <= 1e-15:
        if abs(num) < 1e-12: return 0.0            # all-tie boundary at d = 0: no evidence either way, not -inf
        return float("inf") if num > 0 else float("-inf")
    return num / math.sqrt(var)


def tango_bound(n12, n21, n, alpha_one_sided, lower=True):
    """One-sided score bound for p1 - p2: the d at which Z(d) equals +z (lower) or -z (upper). Z is decreasing in d."""
    z = norm_ppf(1 - alpha_one_sided)
    target = z if lower else -z
    lo, hi = -1.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if tango_z(n12, n21, n, mid) > target: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def tango_interval(n12, n21, n, alpha=ALPHA):
    return tango_bound(n12, n21, n, alpha / 2, lower=True), tango_bound(n12, n21, n, alpha / 2, lower=False)


def ni_pvalue(n12, n21, n, margin=MARGIN):
    """One-sided p-value for H0: p1 - p2 <= -margin against H1: p1 - p2 > -margin."""
    return 1 - norm_cdf(tango_z(n12, n21, n, -margin))


def holm(pvals, alpha=ALPHA):
    """Holm step-down. Returns adjusted p-values (monotone) and reject flags."""
    k = len(pvals); order = sorted(range(k), key=lambda i: pvals[i]); adj = [0.0] * k; running = 0.0
    for rank, i in enumerate(order):
        a = min(1.0, (k - rank) * pvals[i]); running = max(running, a); adj[i] = running
    return adj, [a <= alpha for a in adj]


def wilson(x, n, alpha=ALPHA):
    if n == 0: return (float("nan"), float("nan"))
    z = norm_ppf(1 - alpha / 2); p = x / n; den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den; half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def sign_test_p(diffs):
    """Exact two-sided sign test on paired differences (ties dropped): descriptive support for the cost claim's direction."""
    pos = sum(1 for d in diffs if d > 0); neg = sum(1 for d in diffs if d < 0); m = pos + neg
    if m == 0: return 1.0
    k = min(pos, neg); tail = sum(math.comb(m, i) for i in range(0, k + 1)) / 2 ** m
    return min(1.0, 2 * tail)


def hodges_lehmann(diffs):
    """Paired HL estimate: median of Walsh averages."""
    w = [(diffs[i] + diffs[j]) / 2 for i in range(len(diffs)) for j in range(i, len(diffs))]
    return statistics.median(w) if w else float("nan")


def paired_table(scored, keys, traces, family, arm_a="compact", arm_b="current_lookup"):
    """Per task: completed_correctly for the two arms and tokens per registered case (invalid/error slots count with their tokens)."""
    by_task = collections.defaultdict(dict)
    tok = collections.defaultdict(dict)
    tr = {t["run_id"]: t for t in traces}
    for r in scored:
        if not r.get("run_id") or not r["task_id"].startswith(family + "i"): continue
        if r["condition"] in (arm_a, arm_b):
            by_task[r["task_id"]][r["condition"]] = bool(r.get("completed_correctly"))
            t = tr.get(r["run_id"]) or {}
            toks = 0
            for key in ("raw_reviewer", "raw_reviewer_initial"):
                rr = t.get(key) or {}
                toks += (rr.get("input_tokens") or 0) + (rr.get("output_tokens") or 0)
            tok[r["task_id"]][r["condition"]] = toks
    tasks = [k for k, v in by_task.items() if arm_a in v and arm_b in v]
    n12 = sum(1 for k in tasks if by_task[k][arm_a] and not by_task[k][arm_b])
    n21 = sum(1 for k in tasks if by_task[k][arm_b] and not by_task[k][arm_a])
    n11 = sum(1 for k in tasks if by_task[k][arm_a] and by_task[k][arm_b])
    # Settled-metered token estimand: a slot whose provider attempt never returned usage (gateway timeout, budget stop,
    # upstream error) has NO metered tokens, so it must not enter the comparison as zero. Pairs with an unresolved slot
    # in either arm are excluded from the token estimate and counted; a sensitivity bound values each unresolved slot at
    # the full output budget plus its input.
    def unresolved(run):
        t = tr.get(run) or {}
        return t.get("status") in ("error",) or (t.get("raw_reviewer") is None and t.get("status") != "complete")
    runs_by = {(r["task_id"], r["condition"]): r["run_id"] for r in scored if r.get("run_id")}
    settled = [k for k in tasks if not unresolved(runs_by.get((k, arm_a))) and not unresolved(runs_by.get((k, arm_b)))]
    diffs = [tok[k][arm_b] - tok[k][arm_a] for k in settled]    # lookup minus compact tokens: positive = compact cheaper
    unres_a = sum(1 for k in tasks if unresolved(runs_by.get((k, arm_a)))); unres_b = sum(1 for k in tasks if unresolved(runs_by.get((k, arm_b))))
    return {"n": len(tasks), "both": n11, "compact_only": n12, "lookup_only": n21, "neither": len(tasks) - n11 - n12 - n21,
            "compact_rate": (n11 + n12) / len(tasks) if tasks else None, "lookup_rate": (n11 + n21) / len(tasks) if tasks else None,
            "token_diffs": diffs, "token_pairs_settled": len(settled), "unresolved_compact": unres_a, "unresolved_lookup": unres_b}


def analyze_binary(n12, n21, n, margin=MARGIN):
    d = (n12 - n21) / n if n else float("nan")
    lo, hi = tango_interval(n12, n21, n) if n else (float("nan"), float("nan"))
    return {"delta": d, "tango_95": [lo, hi], "ni_p": ni_pvalue(n12, n21, n, margin) if n else None, "margin": -margin}


def synthetic():
    print("Synthetic checks (compact - lookup completion; margin -0.10)")
    lo, hi = tango_interval(0, 0, 60); assert abs(lo + hi) < 1e-6, ("all-tie interval must be symmetric", lo, hi)
    assert tango_z(0, 0, 60, 0.0) == 0.0, "all-tie statistic at d=0 must be 0"
    lo1, hi1 = tango_interval(60, 0, 60); assert hi1 > 0.99 and 0.8 < lo1 < 1.0, ("all compact-only endpoint", lo1, hi1)
    lo2, hi2 = tango_interval(0, 60, 60); assert lo2 < -0.99 and -1.0 < hi2 < -0.8, ("all lookup-only endpoint", lo2, hi2)
    print("  symmetry and endpoint tests pass")
    for label, n12, n21, n in (("all tie n=40", 0, 0, 40), ("all tie n=60", 0, 0, 60), ("all tie n=120", 0, 0, 120),
                               ("n=60, 8 compact-only, 2 lookup-only", 8, 2, 60), ("n=60, 2 compact-only, 8 lookup-only", 2, 8, 60),
                               ("n=60, 30 compact-only, 0", 30, 0, 60)):
        a = analyze_binary(n12, n21, n)
        lb6 = tango_bound(n12, n21, n, ALPHA / 6, lower=True)        # one-sided bound at the Holm-worst alpha for 6 claims
        print(f"  {label:42s} delta {a['delta']:+.3f}  95% Tango [{a['tango_95'][0]:+.4f}, {a['tango_95'][1]:+.4f}]  "
              f"lower bound at alpha=.05/6: {lb6:+.4f}  NI p {a['ni_p']:.4f}  -> {'NI holds' if lb6 > -MARGIN else 'NI not shown'} at .05/6")
    pv = [0.001, 0.04, 0.02, 0.3, 0.009, 0.5]; adj, rej = holm(pv)
    print("  Holm on", pv, "->", [round(x, 3) for x in adj], rej)
    print("  sign test p (10 pos, 2 neg):", round(sign_test_p([1] * 10 + [-1] * 2), 4), "| HL of [3,5,7,-1]:", hodges_lehmann([3, 5, 7, -1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--cohort", action="append", default=[], help="scored.jsonl::task_keys.json::traces.jsonl::model::tier (double-colon separated; Windows paths contain single colons)")
    ap.add_argument("--out", default="report/heldout_results")
    a = ap.parse_args()
    if a.synthetic: synthetic(); return
    os.makedirs(a.out, exist_ok=True)
    results = {"claims": [], "descriptive": {}}
    for spec in a.cohort:
        sc, tk, trp, model, tier = spec.split("::")
        scored = [json.loads(l) for l in open(sc) if l.strip()]; keys = json.load(open(tk)); traces = [json.loads(l) for l in open(trp)]
        results["descriptive"][model] = {"tier": tier}
        for fam in ("V6", "V11", "V1"):
            pt = paired_table(scored, keys, traces, fam)
            d = dict(pt); d.pop("token_diffs")
            results["descriptive"][model][fam] = d
            if tier == "inferential" and fam in ("V6", "V11") and pt["n"]:
                results["claims"].append({"model": model, "family": fam, "type": "completion_NI", **analyze_binary(pt["compact_only"], pt["lookup_only"], pt["n"])})
        # tokens per registered case, V6+V11 pooled within model (one cost claim per model)
        diffs = []
        for fam in ("V6", "V11"):
            diffs += paired_table(scored, keys, traces, fam)["token_diffs"]
        if tier == "inferential" and diffs:
            results["claims"].append({"model": model, "family": "V6+V11", "type": "tokens_lookup_minus_compact", "n": len(diffs),
                                      "hodges_lehmann": hodges_lehmann(diffs), "mean": statistics.mean(diffs), "sign_p": sign_test_p(diffs)})
        # per-arm rates and false quarantine (descriptive)
        arms = collections.defaultdict(lambda: collections.Counter())
        for r in scored:
            if not r.get("run_id"): continue
            fam = r["task_id"].split("i")[0]; arms[(fam, r["condition"])]["registered"] += 1
            arms[(fam, r["condition"])][r["status"]] += 1
            if r.get("completed_correctly"): arms[(fam, r["condition"])]["completed"] += 1
            if fam == "V1" and r["status"] == "complete" and not r.get("completed_correctly"): arms[(fam, r["condition"])]["false_quarantine"] += 1
        results["descriptive"][model]["arms"] = {f"{k[0]}/{k[1]}": dict(v) for k, v in arms.items()}
    pv = [c["ni_p"] for c in results["claims"] if c["type"] == "completion_NI"] + [c["sign_p"] for c in results["claims"] if c["type"] != "completion_NI"]
    if pv:
        adj, rej = holm(pv); i = 0
        for c in results["claims"]:
            c["holm_adjusted_p"] = adj[i]; c["reject_at_0.05"] = rej[i]; i += 1
    json.dump(results, open(os.path.join(a.out, "results.json"), "w"), indent=1)
    print(json.dumps(results["claims"], indent=1)[:4000])


if __name__ == "__main__":
    main()
