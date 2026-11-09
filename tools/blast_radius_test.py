"""Blast radius of one compromised source under runtime-sealed lineage. Deterministic, no model calls, scratch endpoint only.
Graph: root S/1 (later adjudicated as wrong) -> 20 agent drafts (depth 1) -> 20 summaries (depth 2) -> 20 summaries of
summaries (depth 3) = 60 descendants; plus an independent root U/1 -> 20 unrelated drafts. After S/1 is adjudicated:
  gate (full closure walk)        : expected 60/60 descendants rejected, 20/20 unrelated approved
  direct-dependency check only    : computed from the same provenance table, catches depth 1 only (20/60)
  no lineage                      : 0/60 by construction
Run: python -I tools/blast_radius_test.py
"""
import json, sys, time
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4
sys.path.insert(0, "tools")
from hive_http import query

OP = open("secrets/branch_operator.env").read().split("=", 1)[1].strip()
target = urlsplit(OP)
for envf, name in (("secrets/operator.env", "main"), ("secrets/eval_operator.env", "eval")):
    other = urlsplit(open(envf).read().split("=", 1)[1].strip())
    if not target.hostname or not other.hostname or target.hostname.replace("-pooler", "") == other.hostname.replace("-pooler", ""):
        sys.exit(f"REFUSED: scratch endpoint must differ from {name}")

def err(r):
    if isinstance(r, dict) and "error" in r:
        e = r["error"]; return e.get("message") if isinstance(e, dict) else str(e)
    return None
def val(r):
    rs = r.get("rows") if isinstance(r, dict) else None
    return rs[0][list(rs[0])[0]] if rs else err(r)

P = f"br_{uuid4().hex[:10]}_"
def fid(x): return P + x
def seal(author, aid, ver, body, deps=()):
    r = query("SELECT exp.seal_artifact($1,$2,$3,$4,$5::jsonb) AS kind", [author, fid(aid), ver, body, json.dumps([{"id": fid(i), "ver": v} for i, v in deps])], conn=OP)
    if err(r): sys.exit(f"seal failed {aid}: {err(r)}")
def publish(aid, ver, deps):
    t = time.perf_counter()
    r = query("SELECT exp.publish_decision($1,$2,$3::jsonb) AS result", [fid(aid), ver, json.dumps([{"id": fid(i), "ver": v} for i, v in deps])], conn=OP)
    return str(val(r)), time.perf_counter() - t

RES = []
def check(name, cond, detail=""):
    RES.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {str(detail)[:160]}" if detail else ""))

N = 20
seal("bot_researcher", "S", 1, json.dumps({"units": 12, "note": "compromised source"}))
seal("bot_researcher", "U", 1, json.dumps({"units": 5, "note": "independent source"}))
desc = []   # (aid, deps, depth)
for k in range(N):
    seal("bot_writer", f"D1_{k}", 1, json.dumps({"units": 12}), [("S", 1)]); desc.append((f"D1_{k}", [("S", 1)], 1))
for k in range(N):
    seal("bot_writer", f"D2_{k}", 1, json.dumps({"units": 12}), [(f"D1_{k}", 1)]); desc.append((f"D2_{k}", [(f"D1_{k}", 1)], 2))
for k in range(N):
    seal("bot_writer", f"D3_{k}", 1, json.dumps({"units": 12}), [(f"D2_{k}", 1)]); desc.append((f"D3_{k}", [(f"D2_{k}", 1)], 3))
unrel = []
for k in range(N):
    seal("bot_writer", f"UW_{k}", 1, json.dumps({"units": 5}), [("U", 1)]); unrel.append((f"UW_{k}", [("U", 1)]))

# before the compromise is known, everything is publishable (sanity on a sample)
ok_before = sum(1 for a, d, _ in desc[::15] if publish(a, 1, d)[0] == "approved")
check("P0 before adjudication a sample of descendants publishes", ok_before == len(desc[::15]), ok_before)

# the operator adjudicates the root: a new version carries the corrected figure
r = query("SELECT exp.invalidate($1,$2,$3) AS epoch", [fid("S"), 1, "adjudicated"], conn=OP); check("P1 root adjudicated", err(r) is None, err(r))
seal("bot_researcher", "S", 2, json.dumps({"units": 9, "note": "corrected"}))

# gate: full closure walk
blocked = {1: 0, 2: 0, 3: 0}; times = []
for a, d, depth in desc:
    res, dt = publish(a, 1, d); times.append(dt)
    if res.startswith("rejected"): blocked[depth] += 1
check("P2 gate blocks every descendant at depth 1", blocked[1] == N, blocked)
check("P3 gate blocks every descendant at depth 2", blocked[2] == N, blocked)
check("P4 gate blocks every descendant at depth 3", blocked[3] == N, blocked)
appr = sum(1 for a, d in unrel if publish(a, 1, d)[0] == "approved")
check("P5 gate approves every unrelated artifact", appr == N, appr)

# the comparison monitors, computed from the same provenance table
direct = query("""SELECT count(*) AS n FROM exp.provenance p
                  WHERE p.derived_id LIKE $1 AND EXISTS (SELECT 1 FROM exp.invalidations i WHERE i.artifact_id = p.source_id AND i.version = p.source_ver)""", [P + "D%"], conn=OP)
if err(direct): sys.exit("direct-check query failed: " + err(direct))
direct_n = int(val(direct)); note = "from exp.provenance joined to exp.invalidations on the direct edge"
check("P6 a direct-dependency-only check catches depth 1 only", direct_n == N, f"{direct_n}/60 {note}")
times.sort(); med = times[len(times)//2]
summary = {"descendants": len(desc), "gate_blocked": sum(blocked.values()), "by_depth": blocked, "unrelated": N, "unrelated_approved": appr,
           "direct_check_catches": direct_n, "no_lineage_catches": 0, "publish_median_s": round(med, 3), "publish_p95_s": round(times[int(len(times)*0.95)-1], 3), "prefix": P}
print(json.dumps(summary))
json.dump(summary, open("runs/blast_radius_latest.json", "w"), indent=1)
print(f"\n{sum(RES)}/{len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
