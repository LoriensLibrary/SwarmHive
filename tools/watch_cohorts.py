"""Watch running cohort processes; exit when the named cohorts have finished (process gone and run_summary.json written),
or when a cohort budget-stops, or after --max-minutes. Prints a status line every --every seconds.
  python -I tools/watch_cohorts.py --wait heldout_gemma431bit heldout_deepseekv4fl --max-minutes 240
"""
import argparse, json, os, glob, time, subprocess, collections

def alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
    return str(pid) in out

def status_line(d):
    led = [json.loads(l) for l in open(d + "/ledger.jsonl")] if os.path.exists(d + "/ledger.jsonl") else []
    ev = collections.Counter(r["event"] for r in led); un = ev.get("unresolved", 0); att = ev.get("debit", 0)
    settled = max([r.get("spend_after", 0) for r in led if r["event"] == "actual"] or [0])
    tr = sum(1 for _ in open(d + "/traces.jsonl")) if os.path.exists(d + "/traces.jsonl") else 0
    done = os.path.exists(d + "/run_summary.json")
    return f"{os.path.basename(d):38s} attempts {att:4d} 504 {un:3d} stops {ev.get('budget_stop',0)+ev.get('attempt_cap',0):2d} traces {tr:4d} settled {settled:.3f} {'DONE' if done else ''}"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--wait", nargs="+", required=True); ap.add_argument("--every", type=int, default=300); ap.add_argument("--max-minutes", type=int, default=360)
    a = ap.parse_args()
    L = json.load(open("runs/launch_logs/LAUNCH.json")); pids = dict(L["pids"])
    t0 = time.time()
    while True:
        print(time.strftime("%H:%M:%S"), flush=True)
        dirs = {c: next(iter(glob.glob(f"runs/holdout_{c}_*")), None) for c in a.wait}
        for c in a.wait:
            if dirs[c]: print("  " + status_line(dirs[c]), flush=True)
        finished = all(dirs[c] and os.path.exists(dirs[c] + "/run_summary.json") for c in a.wait)
        dead = [c for c in a.wait if not alive(pids[c]) and not (dirs[c] and os.path.exists(dirs[c] + "/run_summary.json"))]
        if finished: print("ALL WAITED COHORTS FINISHED", flush=True); return
        if dead: print("PROCESS GONE WITHOUT SUMMARY:", dead, flush=True); return
        if time.time() - t0 > a.max_minutes * 60: print("MAX WAIT REACHED", flush=True); return
        time.sleep(a.every)

if __name__ == "__main__":
    main()
