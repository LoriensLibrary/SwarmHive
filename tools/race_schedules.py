"""Overlapping-transaction schedules for the fence, on the scratch branch (never main or eval). Each schedule holds one
transaction open while the other runs in a thread, measures that the second one actually waited on the fence, and checks
the outcome the lock protocol predicts.

  E  publication holds the fence first, a withdrawal arrives and waits; publication commits an approval; the withdrawal
     then commits; the validity view shows no live approval (approval followed by supersession).
  F  a withdrawal holds the fence first, publication arrives and waits; the withdrawal commits; publication then sees it
     and rejects.
  G  a withdrawal holds the fence and ROLLS BACK; the waiting publication then approves (an aborted invalidation leaves
     no trace) and the approval stays live.
  H  publication holds the fence and ROLLS BACK; no approval row exists afterwards; a later withdrawal proceeds.

Run: python -I tools/race_schedules.py     (writes runs/race_schedules_latest.json)
"""
import json, sys, threading, time, uuid
from urllib.parse import quote, urlsplit, urlunsplit
import psycopg

OP = open("secrets/branch_operator.env").read().split("=", 1)[1].strip()
t = urlsplit(OP)
for envf, name in (("secrets/operator.env", "main"), ("secrets/eval_operator.env", "eval")):
    o = urlsplit(open(envf).read().split("=", 1)[1].strip())
    if t.hostname.replace("-pooler", "") == o.hostname.replace("-pooler", ""):
        sys.exit(f"REFUSED: scratch endpoint must differ from {name}")
pw = json.load(open("secrets/bot_passwords.json"))
def dsn(role):
    if role == "hive_operator": return OP
    host = t.hostname + (f":{t.port}" if t.port else "")
    return urlunsplit((t.scheme, f"{role}:{quote(pw[role], safe='')}@{host}", t.path, t.query, ""))

P = "psched_" + uuid.uuid4().hex[:6] + "_"
HOLD = 3.0
RES, OUT = [], {}
def check(name, cond, detail=""):
    RES.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {detail}" if detail else ""))

def op(sql, params=None, fetch=False):
    with psycopg.connect(OP, sslmode="require", autocommit=True) as c:
        cur = c.execute(sql, params or []); return cur.fetchall() if fetch else None

def fresh():
    s, w = P + uuid.uuid4().hex[:4] + "S", P + uuid.uuid4().hex[:4] + "W"
    op("SELECT exp.seal_artifact('bot_researcher',%s,1,'finding','[]'::jsonb)", (s,))
    op("SELECT exp.seal_artifact('bot_writer',%s,1,'draft',%s::jsonb)", (w, json.dumps([{"id": s, "ver": 1}])))
    return s, w

def live(w): return op("SELECT count(*) FROM exp.current_approvals WHERE artifact_id=%s", (w,), fetch=True)[0][0]
def rows(w): return [r[0] for r in op("SELECT decision FROM exp.approvals WHERE artifact_id=%s ORDER BY 1", (w,), fetch=True)]

def publish_now(s, w, out):
    t0 = time.perf_counter()
    with psycopg.connect(OP, sslmode="require") as c:
        c.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
        out["result"] = c.execute("SELECT exp.publish_decision(%s,1,%s::jsonb)", (w, json.dumps([{"id": s, "ver": 1}]))).fetchone()[0]; c.commit()
    out["waited_s"] = round(time.perf_counter() - t0, 2)

def withdraw_now(s, out):
    t0 = time.perf_counter()
    with psycopg.connect(dsn("bot_researcher"), sslmode="require", autocommit=True) as c:
        c.execute("SELECT exp.invalidate(%s,1,'withdrawn')", (s,))
    out["waited_s"] = round(time.perf_counter() - t0, 2)

# ---- E: publication holds the fence first ----
S, W = fresh(); w_out = {}
pub = psycopg.connect(OP, sslmode="require"); pub.autocommit = False
pub.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
r = pub.execute("SELECT exp.publish_decision(%s,1,%s::jsonb)", (W, json.dumps([{"id": S, "ver": 1}]))).fetchone()[0]
th = threading.Thread(target=withdraw_now, args=(S, w_out)); th.start(); time.sleep(HOLD)
pub.commit(); pub.close(); th.join()
OUT["E"] = dict(publish=r, withdraw_waited_s=w_out.get("waited_s"), approval_rows=rows(W), live_after=live(W))
check("E publication first: approval commits", str(r) == "approved", r)
check("E the withdrawal waited on the fence", (w_out.get("waited_s") or 0) >= HOLD - 0.5, f"{w_out.get('waited_s')} s")
check("E after the withdrawal commits, the approval is superseded (no live approval)", live(W) == 0, f"rows={rows(W)}")

# ---- F: withdrawal holds the fence first ----
S, W = fresh(); p_out = {}
wd = psycopg.connect(dsn("bot_researcher"), sslmode="require"); wd.autocommit = False
wd.execute("SELECT exp.invalidate(%s,1,'withdrawn')", (S,))
th = threading.Thread(target=publish_now, args=(S, W, p_out)); th.start(); time.sleep(HOLD)
wd.commit(); wd.close(); th.join()
OUT["F"] = dict(publish=p_out.get("result"), publish_waited_s=p_out.get("waited_s"), live_after=live(W))
check("F withdrawal first: publication waited on the fence", (p_out.get("waited_s") or 0) >= HOLD - 0.5, f"{p_out.get('waited_s')} s")
check("F publication sees the committed withdrawal and rejects", str(p_out.get("result", "")).startswith("rejected"), p_out.get("result"))

# ---- G: withdrawal holds the fence and rolls back ----
S, W = fresh(); p_out = {}
wd = psycopg.connect(dsn("bot_researcher"), sslmode="require"); wd.autocommit = False
wd.execute("SELECT exp.invalidate(%s,1,'withdrawn')", (S,))
th = threading.Thread(target=publish_now, args=(S, W, p_out)); th.start(); time.sleep(HOLD)
wd.rollback(); wd.close(); th.join()
OUT["G"] = dict(publish=p_out.get("result"), publish_waited_s=p_out.get("waited_s"), live_after=live(W))
check("G aborted withdrawal: publication waited, then approved", str(p_out.get("result")) == "approved" and (p_out.get("waited_s") or 0) >= HOLD - 0.5, f"{p_out.get('result')} after {p_out.get('waited_s')} s")
check("G the approval stays live (the aborted invalidation left no trace)", live(W) == 1, f"live={live(W)}")

# ---- H: publication holds the fence and rolls back ----
S, W = fresh(); w_out = {}
pub = psycopg.connect(OP, sslmode="require"); pub.autocommit = False
pub.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
r = pub.execute("SELECT exp.publish_decision(%s,1,%s::jsonb)", (W, json.dumps([{"id": S, "ver": 1}]))).fetchone()[0]
th = threading.Thread(target=withdraw_now, args=(S, w_out)); th.start(); time.sleep(HOLD)
pub.rollback(); pub.close(); th.join()
OUT["H"] = dict(publish_in_aborted_txn=r, withdraw_waited_s=w_out.get("waited_s"), approval_rows=rows(W))
check("H aborted publication leaves no approval row", rows(W) == [], f"rows={rows(W)}")
check("H the waiting withdrawal then proceeds", (w_out.get("waited_s") or 0) >= HOLD - 0.5, f"{w_out.get('waited_s')} s")

op("DELETE FROM exp.approvals WHERE artifact_id LIKE %s ESCAPE '!'", (P.replace("_", "!_") + "%",))
OUT["checks_passed"], OUT["checks"] = sum(RES), len(RES)
json.dump(OUT, open("runs/race_schedules_latest.json", "w"), indent=1)
print(f"\n{sum(RES)}/{len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
