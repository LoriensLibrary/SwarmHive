"""Every paid platform ledger in both workspaces, with metered charges (sum of verified per-call charges) and reserves kept
for attempts whose usage never returned (an upper bound on what they could have cost). Writes
report/heldout_results/cost_reconciliation.json and prints the totals the report quotes.
  python -I tools/cost_reconciliation.py [--codex-root PATH]
The canaries and development runs were executed by Lorien in its own workspace; their ledgers are read from there when the
path is available and their recorded totals are kept in the output so the reconciliation survives without it.
"""
import argparse, glob, json, os

KEPT = ("unresolved", "missing_usage", "usage_exceeds_reserve", "unrecognized_billing_model")


def scan(root, label, strip):
    rows = []
    for lp in sorted(glob.glob(os.path.join(root, "**", "ledger.jsonl"), recursive=True)):
        led = [json.loads(l) for l in open(lp, encoding="utf-8", errors="replace") if l.strip()]
        metered = sum(float(r.get("cost", 0) or 0) for r in led if r.get("event") == "actual")
        kept = sum(float(r.get("reserve_kept", 0) or 0) for r in led if r.get("event") in KEPT)
        if metered == 0 and kept == 0: continue
        unit = next((r.get("unit") for r in led if r.get("unit")), "?")
        rows.append(dict(workspace=label, ledger=lp.replace("\\", "/").replace(strip, "<" + label + ">"), unit=unit,
                         metered=round(metered, 6), reserves_kept=round(kept, 6), unresolved=sum(1 for r in led if r.get("event") in KEPT)))
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--codex-root", default=os.path.expanduser("~/Documents/Codex/2026-11-06/che"))
    ap.add_argument("--out", default="report/heldout_results/cost_reconciliation.json"); a = ap.parse_args()
    here = os.path.abspath(".").replace("\\", "/")
    rows = scan(".", "repo", here)
    prev = json.load(open(a.out)) if os.path.exists(a.out) else {}
    if os.path.isdir(a.codex_root):
        rows += scan(a.codex_root, "codex-workspace", a.codex_root.replace("\\", "/"))
    else:
        rows += [r for r in prev.get("rows", []) if r["workspace"] == "codex-workspace"]
    credits = [r for r in rows if r["unit"] == "credits"]
    tot = dict(metered=round(sum(r["metered"] for r in credits), 4), reserves_kept=round(sum(r["reserves_kept"] for r in credits), 4))
    tot["worst_case"] = round(tot["metered"] + tot["reserves_kept"], 4)
    by_ws = {}
    for r in credits:
        w = by_ws.setdefault(r["workspace"], dict(metered=0.0, reserves_kept=0.0, ledgers=0))
        w["metered"] += r["metered"]; w["reserves_kept"] += r["reserves_kept"]; w["ledgers"] += 1
    for w in by_ws.values(): w["metered"] = round(w["metered"], 4); w["reserves_kept"] = round(w["reserves_kept"], 4)
    out = dict(authorized_credits=100, totals_credits=tot, by_workspace=by_ws, rows=rows)
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(dict(totals=tot, by_workspace=by_ws), indent=1))


if __name__ == "__main__":
    main()
