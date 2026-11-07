"""Deterministic protocol tests for the trusted publication gate.

No model calls. Drives artifacts/provenance/invalidation/publish as the real
DB login roles, so the authority boundaries are exercised, not simulated.
Maps to Lorien's frozen cases D1-D8. Each test prints PASS/FAIL with the gate's
own returned reason, so a failure is legible.

Run: python -I tools/det_tests.py
"""
import hashlib, json, sys, os
sys.path.insert(0, "tools")
from hive_http import query

HOST = "ep-summer-paper-bbe7uhtw.c-15.us-east-1.aws.neon.tech"
pw = json.load(open("secrets/bot_passwords.json"))
OP = open("secrets/operator.env").read().split("=", 1)[1].strip()
conn = lambda b: OP if b == "hive_operator" else f"postgresql://{b}:{pw[b]}@{HOST}/hive?sslmode=require"
h = lambda s: hashlib.sha256(s.encode()).hexdigest()

RES = []
def check(name, cond, detail=""):
    RES.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {detail}" if detail else ""))

def rows(r): return r.get("rows") if isinstance(r, dict) and "error" not in r else None
def err(r):
    if isinstance(r, dict) and "error" in r:
        e = r["error"]; return e.get("message") if isinstance(e, dict) else str(e)
    return None

def mk_artifact(role, aid, ver, body):
    return query("INSERT INTO exp.artifacts(artifact_id,version,author_role,body,content_hash) "
                 "VALUES ($1,$2,$3,$4,$5) RETURNING author_role",
                 [aid, ver, role, body, h(body)], conn=conn(role))
def mk_edge(role, did, dver, sid, sver):
    return query("INSERT INTO exp.provenance VALUES ($1,$2,$3,$4)", [did, dver, sid, sver], conn=conn(role))
def invalidate(role, aid, ver, kind):
    return query("SELECT exp.invalidate($1,$2,$3) AS epoch", [aid, ver, kind], conn=conn(role))
def publish(role, aid, ver, attest):
    return query("SELECT exp.publish_decision($1,$2,$3::jsonb) AS result", [aid, ver, json.dumps(attest)], conn=conn(role))

def reset():
    for t in ["approvals", "invalidations", "provenance", "artifacts"]:
        query(f"TRUNCATE exp.{t}", conn=OP)

def decision(r):
    rs = rows(r); return rs[0]["result"] if rs else err(r)

# ---- D1: clean workflow accepted ----
reset()
mk_artifact("bot_researcher", "S", 1, "metric X rose 4 percent")
mk_artifact("bot_writer", "W", 1, "draft: X up 4pct per S")
mk_edge("bot_writer", "W", 1, "S", 1)
d1 = decision(publish("hive_operator", "W", 1, [{"id": "S", "ver": 1, "acked_epoch": 0}]))
check("D1 clean workflow accepted", d1 == "approved", d1)

# ---- D5: omitted dependency -> rejected, never clean by default ----
d5 = decision(publish("hive_operator", "W", 1, []))
check("D5 omitted dependency rejected", str(d5).startswith("rejected"), d5)

# ---- D2: source withdrawn before publication -> descendant blocked; unrelated proceeds ----
reset()
mk_artifact("bot_researcher", "S", 1, "false finding")
mk_artifact("bot_writer", "W", 1, "draft from S")
mk_edge("bot_writer", "W", 1, "S", 1)
inv = invalidate("bot_researcher", "S", 1, "withdrawn")      # author withdraws own source
ep = rows(inv)[0]["epoch"] if rows(inv) else None
d2 = decision(publish("hive_operator", "W", 1, [{"id": "S", "ver": 1, "acked_epoch": 0}]))
check("D2a withdrawn source blocks descendant", str(d2).startswith("rejected"), d2)
mk_artifact("bot_researcher", "U", 1, "unrelated clean finding")  # independent branch
mk_artifact("bot_writer", "UW", 1, "draft from U")
mk_edge("bot_writer", "UW", 1, "U", 1)
d2b = decision(publish("hive_operator", "UW", 1, [{"id": "U", "ver": 1, "acked_epoch": 0}]))
check("D2b unrelated branch still proceeds", d2b == "approved", d2b)

# ---- D3: stale approval replay after source revision/invalidation -> rejected ----
d3 = decision(publish("hive_operator", "W", 1, [{"id": "S", "ver": 1, "acked_epoch": 0}]))
check("D3 stale attestation (acked 0 < invalidation epoch) rejected", str(d3).startswith("rejected"), d3)
# and acknowledging the current epoch does NOT clear a blocking withdrawal:
d3b = decision(publish("hive_operator", "W", 1, [{"id": "S", "ver": 1, "acked_epoch": ep}]))
check("D3b acking the withdrawal epoch still cannot approve a withdrawn dep",
      str(d3b).startswith("rejected"), d3b)

# ---- D4: forged invalidation of someone else's source -> rejected ----
reset()
mk_artifact("bot_researcher", "S", 1, "honest source")
f1 = invalidate("bot_intruder", "S", 1, "withdrawn")      # intruder is not the author
check("D4a intruder cannot withdraw another's artifact", err(f1) is not None, err(f1))
f2 = invalidate("bot_intruder", "S", 1, "adjudicated")    # intruder is not an adjudicator
check("D4b intruder cannot adjudicate", err(f2) is not None, err(f2))

# ---- Authority: only an adjudicator may publish ----
mk_artifact("bot_writer", "W", 1, "draft")
mk_edge("bot_writer", "W", 1, "S", 1)
p_bot = decision(publish("bot_reviewer", "W", 1, [{"id": "S", "ver": 1, "acked_epoch": 0}]))
check("AUTH non-adjudicator reviewer cannot publish", err(publish("bot_reviewer","W",1,[{"id":"S","ver":1,"acked_epoch":0}])) is not None
      or str(p_bot).startswith("ERROR") or "adjudicator" in str(p_bot), p_bot)

# ---- D8: compromised author retracts own input repeatedly -> bounded, no deadlock ----
reset()
mk_artifact("bot_intruder", "Z", 1, "noise")
for _ in range(3):
    invalidate("bot_intruder", "Z", 1, "withdrawn")       # repeated self-withdrawal
mk_artifact("bot_researcher", "G", 1, "good work")        # unrelated work unaffected
mk_artifact("bot_writer", "GW", 1, "draft from G")
mk_edge("bot_writer", "GW", 1, "G", 1)
d8 = decision(publish("hive_operator", "GW", 1, [{"id": "G", "ver": 1, "acked_epoch": 0}]))
check("D8 repeated self-retraction does not freeze unrelated work", d8 == "approved", d8)

print(f"\n{sum(1 for _,c in RES if c)}/{len(RES)} checks passed")
sys.exit(0 if all(c for _, c in RES) else 1)
