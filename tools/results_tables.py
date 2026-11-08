"""Build the section 5 tables from the analysis output, the per-cohort traces and ledgers, and the freeze index.

  python -I tools/results_tables.py --results report/heldout_results/results.json --index holdout/heldout_v1/INDEX.json \
      --cohort heldout_gemma431bit=runs/holdout_heldout_gemma431bit_c05c68 ... [--audit-dsn-file secrets/eval_operator.env] --out report/heldout_results

Writes TABLES.md (Markdown tables, ready to paste) and tables.json (the numbers behind them). Every count is over registered slots.
The optional audit opens ONE read-only connection to the evaluation branch and counts committed approvals whose artifact ids carry the
cohort prefix, to compare with the db_verified approved events in the traces. The DSN is read from a file and never printed.
"""
import argparse, collections, glob, json, os, statistics

ARMS = ["current", "current_lookup", "compact", "full", "rule", "rule_content"]
FAMS = ["V6", "V11", "V1"]


def fam_of(task_id):
    return task_id.split("i")[0]


def load_cohort(path):
    traces = [json.loads(l) for l in open(path + "/traces.jsonl")]
    scored = [json.loads(l) for l in open(path + "/scored.json") if l.strip()] if os.path.exists(path + "/scored.json") else []
    ledger = [json.loads(l) for l in open(path + "/ledger.jsonl")] if os.path.exists(path + "/ledger.jsonl") else []
    manifest = json.load(open(path + "/manifest.json"))
    ex = json.load(open(path + "/EXECUTION.json")) if os.path.exists(path + "/EXECUTION.json") else {}
    return dict(traces=traces, scored=scored, ledger=ledger, manifest=manifest, execution=ex, done=os.path.exists(path + "/run_summary.json"))


def _records(trace):
    """every model call record on the slot: the initial reply (kept under raw_reviewer_initial when a lookup was used) and the final one."""
    rs = []
    for key in ("raw_reviewer_initial", "raw_reviewer"):
        r = trace.get(key)
        if isinstance(r, list): rs += r
        elif isinstance(r, dict): rs.append(r)
    return rs


def calls_of(trace):
    return len(_records(trace))


def tokens_of(trace):
    rs = _records(trace)
    i = sum(int(c.get("input_tokens") or 0) for c in rs); o = sum(int(c.get("output_tokens") or 0) for c in rs)
    rz = sum(int(c.get("reasoning_tokens") or 0) for c in rs)
    return i, o, rz


def slot_table(c):
    """registered / complete / invalid by reason / error by kind / missing, per model."""
    tr = c["traces"]; by_run = {t["run_id"]: t for t in tr}
    rows = collections.Counter(); per_arm_err = collections.Counter()
    for e in c["manifest"]:
        t = by_run.get(e["run_id"])
        rows["registered"] += 1
        if t is None: rows["missing"] += 1; continue
        st = t["status"]
        if st == "complete": rows["complete"] += 1
        elif st == "invalid_output":
            reason = t.get("invalid_reason") or ("pre_gate_stop" if t.get("pre_gate_stop") else None) or str(t.get("error") or "other")
            rows["invalid_" + reason] += 1
        elif st == "error":
            msg = str(t.get("error") or "")
            kind = "504" if "504" in msg else ("502" if "502" in msg else ("timeout" if "timed out" in msg.lower() or "timeout" in msg.lower() else "other"))
            rows["error_" + kind] += 1; per_arm_err[t["condition"]] += 1
        else: rows[st] += 1
    ev = collections.Counter(r["event"] for r in c["ledger"])
    rows["guard_stopped"] = ev.get("budget_stop", 0) + ev.get("attempt_cap", 0)
    rows["unresolved_504_reserves"] = ev.get("unresolved", 0)
    return rows, per_arm_err


def gate_integrity(c):
    tr = c["traces"]; sc = {r["run_id"]: r for r in c["scored"] if r.get("run_id")}
    g = collections.Counter()
    for t in tr:
        s = sc.get(t["run_id"], {})
        g["slots"] += 1
        if s.get("proposed_bad_approval"): g["unsafe_proposals"] += 1
        if t.get("pre_gate_stop"): g["pre_gate_stops"] += 1
        g["gate_rejections"] += int(s.get("gate_rejections") or 0)
        g["unsafe_commits"] += int(s.get("accepted_bad_actions") or 0)
        g["correct_publications"] += int(s.get("correct_publications") or 0)
        evs = t.get("gate_events") or []
        if t.get("gate_called") and (not evs or any(e.get("db_verified") is not True for e in evs)): g["unknown_commit_outcome"] += 1
        g["db_verified_approved_events"] += sum(1 for e in evs if e.get("db_verified") is True and e.get("decision") == "approved")
        g["gate_calls"] += 1 if t.get("gate_called") else 0
    return g


def arm_rates(c):
    """completed_correctly rate per family and arm; calls and tokens per complete slot; lookup use."""
    sc = {r["run_id"]: r for r in c["scored"] if r.get("run_id")}; out = {}
    for fam in FAMS:
        for arm in ARMS:
            ts = [t for t in c["traces"] if fam_of(t["task_id"]) == fam and t["condition"] == arm]
            if not ts: continue
            comp = [t for t in ts if sc.get(t["run_id"], {}).get("completed_correctly")]
            settled = [t for t in ts if t.get("raw_reviewer")]
            calls = [calls_of(t) for t in settled]; toks = [sum(tokens_of(t)[:2]) for t in settled]; rz = [tokens_of(t)[2] for t in settled]
            used = sum(1 for t in ts if (t.get("lookup") or {}).get("used")); avail = sum(1 for t in ts if (t.get("lookup") or {}).get("available"))
            out[f"{fam}/{arm}"] = dict(registered=len(ts), completed=len(comp), rate=round(len(comp) / len(ts), 4),
                                      mean_calls=round(statistics.mean(calls), 2) if calls else None,
                                      mean_tokens=round(statistics.mean(toks), 1) if toks else None,
                                      mean_reasoning_tokens=round(statistics.mean(rz), 1) if rz else None,
                                      lookup_offered=avail, lookup_used=used)
    return out


def cost_row(c, idx):
    led = c["ledger"]
    settled = max([r.get("spend_after", 0.0) for r in led if r["event"] == "actual"] or [0.0])
    retained = sum(r.get("reserve_kept", 0.0) for r in led if r["event"] in ("unresolved", "missing_usage", "usage_exceeds_reserve", "unrecognized_billing_model"))
    debits = sum(1 for r in led if r["event"] == "debit")
    return dict(settled=round(settled, 4), retained=round(retained, 4), attempts=debits, ceiling=idx.get("ceiling_credits"),
                expected=idx.get("expected_credits"), at_cap=idx.get("at_cap_credits"), max_requests=idx.get("max_requests"),
                resumes=len(c["execution"].get("resumes", [])))


def audit(dsn_file, prefixes):
    import psycopg
    dsn = open(dsn_file).read().split("=", 1)[1].strip()
    out = {}
    with psycopg.connect(dsn, sslmode="require", autocommit=True, connect_timeout=20) as conn:
        conn.execute("SET default_transaction_read_only = on")
        for cohort, pre in prefixes.items():
            n = conn.execute("SELECT count(*) FROM exp.approvals WHERE decision = 'approved' AND position(%s in artifact_id) > 0", (f"_{cohort}_",)).fetchone()[0]
            out[cohort] = int(n)
    return out


def md_table(headers, rows):
    s = "| " + " | ".join(headers) + " |\n|" + "|".join([" --- "] * len(headers)) + "|\n"
    for r in rows: s += "| " + " | ".join("" if v is None else str(v) for v in r) + " |\n"
    return s


def fmt_p(p):
    if p is None: return ""
    return f"{p:.2e}" if p < 1e-3 else f"{p:.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True); ap.add_argument("--index", required=True)
    ap.add_argument("--cohort", action="append", default=[], help="cohort_name=run_dir")
    ap.add_argument("--audit-dsn-file", default=None); ap.add_argument("--out", default="report/heldout_results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    R = json.load(open(a.results)); idx = {r["cohort"]: r for r in json.load(open(a.index))}
    cohorts = {k: load_cohort(v) for k, v in (x.split("=", 1) for x in a.cohort)}
    T = {"cohorts": {}}; md = []

    # 1. design as frozen
    rows = []
    for k, c in cohorts.items():
        r = idx[k]
        rows.append([r["tier"], r["model"], k, r["freeze_id"][:12], r["runs"], r["max_requests"], r["ceiling_credits"], r["expected_credits"], r["at_cap_credits"], r.get("seed"), "yes" if c["done"] else "RUNNING"])
    md.append("### Design as frozen\n\n" + md_table(["tier", "model", "cohort", "freeze id", "slots", "request cap", "ceiling (cr)", "modeled charge", "all-at-cap", "seed", "complete"], rows))

    # 2. slots and failure categories
    rows = []; keys = set()
    slot = {k: slot_table(c) for k, c in cohorts.items()}
    for k, (s, _) in slot.items(): keys |= set(s)
    cols = ["registered", "complete", "invalid_output_budget_exhausted", "invalid_malformed_or_nonqueued", "invalid_pre_gate_stop", "error_504", "error_502", "error_timeout", "error_other", "missing", "guard_stopped"]
    for k, (s, pe) in slot.items():
        rows.append([idx[k]["model"]] + [s.get(c, 0) for c in cols] + [", ".join(f"{arm} {n}" for arm, n in pe.most_common()) or ""])
        T["cohorts"].setdefault(k, {})["slots"] = dict(s); T["cohorts"][k]["errors_by_arm"] = dict(pe)
    md.append("### Registered slots and failure categories\n\n" + md_table(["model", "registered", "complete", "invalid: budget", "invalid: malformed/non-queued", "invalid: pre-gate stop", "error 504", "error 502", "transport timeout", "error other", "missing", "guard-stopped"] + ["errors by arm"], rows))

    # 3. primary
    rows = []
    for cl in R["claims"]:
        if cl["type"] != "completion_NI": continue
        d = R["descriptive"][cl["model"]][cl["family"]]
        lo, hi = cl["tango_95"]
        rows.append([cl["model"], cl["family"], d["n"], d["both"], d["compact_only"], d["lookup_only"], d["neither"], f"{d['compact_rate']:.3f}", f"{d['lookup_rate']:.3f}", f"{cl['delta']:+.3f}", f"[{lo:+.3f}, {hi:+.3f}]", fmt_p(cl["ni_p"]), fmt_p(cl["holm_adjusted_p"]), "holds" if cl["reject_at_0.05"] else "not shown"])
    md.append("### Primary: completion, compact vs lookup-offered (inferential tier)\n\n" + md_table(["model", "family", "n pairs", "both", "compact only", "lookup only", "neither", "compact rate", "lookup rate", "delta", "Tango 95%", "NI p (margin -0.10)", "Holm p", "non-inferiority"], rows))

    # 4. co-primary tokens + calls descriptive
    rows = []
    for cl in R["claims"]:
        if cl["type"] != "tokens_lookup_minus_compact": continue
        rows.append([cl["model"], cl["n"], f"{cl['hodges_lehmann']:+.1f}", f"{cl['mean']:+.1f}", fmt_p(cl["sign_p"]), fmt_p(cl["holm_adjusted_p"]), "yes" if cl["reject_at_0.05"] else "no"])
    md.append("### Co-primary: tokens per registered case, lookup-offered minus compact (V6 and V11 pooled within model, settled pairs only)\n\n" + md_table(["model", "settled pairs", "Hodges-Lehmann", "mean", "sign-test p", "Holm p", "reject at 0.05"], rows))

    rates = {k: arm_rates(c) for k, c in cohorts.items()}
    rows = []
    for k, rt in rates.items():
        for fam in FAMS:
            for arm in ("compact", "current_lookup"):
                r = rt.get(f"{fam}/{arm}")
                if r: rows.append([idx[k]["model"], idx[k]["tier"], fam, arm, r["mean_calls"], r["mean_tokens"], r["mean_reasoning_tokens"], f"{r['lookup_used']}/{r['lookup_offered']}" if arm == "current_lookup" else ""])
        T["cohorts"][k]["arm_rates"] = rt
    md.append("### Calls, tokens and lookup use per settled slot (descriptive)\n\n" + md_table(["model", "tier", "family", "arm", "mean calls", "mean tokens (in+out)", "mean reasoning tokens", "lookup used/offered"], rows))

    # 5. V1 false quarantine per arm
    rows = []
    for k, c in cohorts.items():
        arms = R["descriptive"].get(idx[k]["model"], {}).get("arms", {})
        for arm in ARMS:
            v = arms.get(f"V1/{arm}")
            if v: rows.append([idx[k]["model"], arm, v.get("registered", 0), v.get("complete", 0), v.get("completed", 0), v.get("false_quarantine", 0), v.get("invalid_output", 0), v.get("error", 0)])
    md.append("### V1 clean-draft control: false quarantine per arm (descriptive)\n\n" + md_table(["model", "arm", "registered", "complete", "approved clean draft", "false quarantine", "invalid", "error"], rows))

    # 6. all arms completion by family (inferential + exploratory)
    rows = []
    for k, rt in rates.items():
        for fam in FAMS:
            rows.append([idx[k]["model"], idx[k]["tier"], fam] + [(f"{rt[f'{fam}/{arm}']['completed']}/{rt[f'{fam}/{arm}']['registered']}" if f"{fam}/{arm}" in rt else "") for arm in ARMS])
    md.append("### Completed correctly per arm, all models and families (descriptive)\n\n" + md_table(["model", "tier", "family"] + ARMS, rows))

    # 7. gate integrity
    rows = []; tot = collections.Counter()
    for k, c in cohorts.items():
        g = gate_integrity(c); tot.update(g); T["cohorts"][k]["gate"] = dict(g)
        rows.append([idx[k]["model"], g["slots"], g["gate_calls"], g["unsafe_proposals"], g["pre_gate_stops"], g["gate_rejections"], g["correct_publications"], g["unsafe_commits"], g["unknown_commit_outcome"], g["db_verified_approved_events"]])
    rows.append(["all", tot["slots"], tot["gate_calls"], tot["unsafe_proposals"], tot["pre_gate_stops"], tot["gate_rejections"], tot["correct_publications"], tot["unsafe_commits"], tot["unknown_commit_outcome"], tot["db_verified_approved_events"]])
    T["gate_total"] = dict(tot)
    md.append("### Gate integrity across registered slots\n\n" + md_table(["model", "slots", "gate calls", "unsafe proposals", "pre-gate stops", "gate rejections", "correct publications", "unsafe commits", "unknown commit outcome", "db-verified approvals"], rows))

    if a.audit_dsn_file:
        try:
            au = audit(a.audit_dsn_file, {k: k for k in cohorts}); T["branch_audit"] = au
            rows = [[idx[k]["model"], T["cohorts"][k]["gate"]["db_verified_approved_events"], au.get(k)] for k in cohorts]
            md.append("### Read-only audit of the evaluation branch: committed approvals carrying each cohort's id vs db-verified approved events in the traces\n\n" + md_table(["model", "approved events in traces", "approval rows on branch"], rows))
        except Exception as e:
            md.append(f"### Branch audit\n\nnot run: {type(e).__name__}\n"); T["branch_audit_error"] = type(e).__name__

    # 8. cost
    rows = []; ts = tr = 0.0
    for k, c in cohorts.items():
        cr = cost_row(c, idx[k]); T["cohorts"][k]["cost"] = cr; ts += cr["settled"]; tr += cr["retained"]
        rows.append([idx[k]["model"], cr["attempts"], cr["max_requests"], cr["settled"], cr["retained"], cr["ceiling"], cr["expected"], cr["at_cap"], cr["resumes"]])
    rows.append(["all", "", "", round(ts, 4), round(tr, 4), "", "", "", ""])
    T["cost_total"] = dict(settled=round(ts, 4), retained=round(tr, 4))
    md.append("### Cost per cohort (platform credits)\n\n" + md_table(["model", "attempts", "request cap", "settled", "retained reserves (504)", "ceiling", "modeled charge", "all-at-cap", "resumes"], rows))

    open(os.path.join(a.out, "TABLES.md"), "w", encoding="utf-8").write("\n".join(md))
    json.dump(T, open(os.path.join(a.out, "tables.json"), "w"), indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()
