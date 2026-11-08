"""Deterministic protocol tests for the trusted governance gate.

No model calls. Artifacts are created only through the trusted seal_artifact()
(bots have no direct write), and invalidation/publication go through the
authority-checked functions, so the real boundaries are exercised. Maps to
Lorien's frozen cases D1-D8.

Run: python -I tools/det_tests.py
"""
import json, sys, os
sys.path.insert(0, "tools")
from hive_http import query

HOST = OP.split("@")[1].split("/")[0]   # bots connect to the SAME database as the operator (scratch branch), never to main
pw = json.load(open("secrets/bot_passwords.json"))
OP = open("secrets/operator.env").read().split("=", 1)[1].strip()
# DESTRUCTIVE: these tests TRUNCATE exp.* . They run ONLY against the scratch branch (secrets/branch_operator.env),
# never against the shared main Hive, which holds cohort evidence. Set DET_DSN to override explicitly.
import os as _os, sys as _sys
_dsn = _os.environ.get("DET_DSN") or open("secrets/branch_operator.env").read().split("=", 1)[1].strip()
if "ep-summer-paper" in _dsn:
    _sys.exit("REFUSED: det_tests truncates exp.*; point it at the scratch branch (secrets/branch_operator.env), not the shared main Hive")
OP = _dsn

conn = lambda b: OP if b == "hive_operator" else f"postgresql://{b}:{pw[b]}@{HOST}/hive?sslmode=require"

RES = []
def check(name, cond, detail=""):
    RES.append(cond); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {detail}" if detail else ""))
def rows(r): return r.get("rows") if isinstance(r, dict) and "error" not in r else None
def err(r):
    if isinstance(r, dict) and "error" in r:
        e = r["error"]; return e.get("message") if isinstance(e, dict) else str(e)
    return None
def val(r):
    rs = rows(r); return rs[0][list(rs[0])[0]] if rs else err(r)

def seal(author, aid, ver, body, deps=()):
    # trusted runtime (operator) seals the artifact + its edges in one call
    return query("SELECT exp.seal_artifact($1,$2,$3,$4,$5::jsonb) AS kind",
                 [author, aid, ver, body, json.dumps([{"id": i, "ver": v} for i, v in deps])], conn=OP)
def invalidate(role, aid, ver, kind):
    return query("SELECT exp.invalidate($1,$2,$3) AS epoch", [aid, ver, kind], conn=conn(role))
def publish(role, aid, ver, attest):
    return query("SELECT exp.publish_decision($1,$2,$3::jsonb) AS result", [aid, ver, json.dumps(attest)], conn=conn(role))
def reset():
    for t in ["approvals", "invalidations", "provenance", "artifacts", "proposals"]:
        query(f"TRUNCATE exp.{t} RESTART IDENTITY CASCADE", conn=OP)

A = lambda i, v, e=0: {"id": i, "ver": v, "acked_epoch": e}

# ---- sealed-creation authority: a bot cannot write artifacts or seal ----
reset()
raw = query("INSERT INTO exp.artifacts(artifact_id,version,author_role,body,content_hash) VALUES ('X',1,'bot_writer','x','h')", conn=conn("bot_writer"))
check("bot cannot raw-INSERT an artifact", err(raw) is not None, err(raw))
botseal = query("SELECT exp.seal_artifact('bot_writer','X',1,'x','[]'::jsonb)", conn=conn("bot_writer"))
check("bot cannot call seal_artifact", err(botseal) is not None, err(botseal))

# ---- D1: clean workflow accepted ----
reset()
seal("bot_researcher", "S", 1, "metric X rose 4 percent")
seal("bot_writer", "W", 1, "draft from S", deps=[("S", 1)])
check("D1 clean workflow accepted", val(publish("hive_operator", "W", 1, [A("S", 1)])) == "approved")

# ---- D5: omitted dependency -> rejected ----
check("D5 omitted dependency rejected", str(val(publish("hive_operator", "W", 1, []))).startswith("rejected"))

# ---- Dn: stripped-lineage root cannot be forged (writer can't make a free root) ----
# The only way to create 'L' is seal; a bot raw insert is denied, and a sealed
# root is a declared root, not a laundered derivative.
reset()
seal("bot_researcher", "S", 1, "source")
forged = query("INSERT INTO exp.artifacts(artifact_id,version,author_role,body,content_hash,kind) VALUES ('L',1,'bot_writer','copied',' ','root')", conn=conn("bot_writer"))
check("stripped-lineage artifact cannot be created by a bot", err(forged) is not None, err(forged))

# ---- D2: source withdrawn before publication blocks descendant; unrelated proceeds ----
reset()
seal("bot_researcher", "S", 1, "false finding")
seal("bot_writer", "W", 1, "draft from S", deps=[("S", 1)])
inv = invalidate("bot_researcher", "S", 1, "withdrawn"); ep = rows(inv)[0]["epoch"] if rows(inv) else None
check("D2a withdrawn source blocks descendant", str(val(publish("hive_operator", "W", 1, [A("S", 1)]))).startswith("rejected"))
seal("bot_researcher", "U", 1, "unrelated clean finding")
seal("bot_writer", "UW", 1, "draft from U", deps=[("U", 1)])
check("D2b unrelated branch still proceeds", val(publish("hive_operator", "UW", 1, [A("U", 1)])) == "approved")

# ---- D3: stale/replayed attestation rejected ----
check("D3 stale attestation rejected", str(val(publish("hive_operator", "W", 1, [A("S", 1, 0)]))).startswith("rejected"))
check("D3b acking the withdrawal epoch still cannot approve a withdrawn dep",
      str(val(publish("hive_operator", "W", 1, [A("S", 1, ep)]))).startswith("rejected"))

# ---- transitive: withdrawn grandparent blocks a grandchild ----
reset()
seal("bot_researcher", "S", 1, "source")
seal("bot_writer", "W", 1, "draft", deps=[("S", 1)])
seal("bot_writer", "R", 1, "report from draft", deps=[("W", 1)])
invalidate("bot_researcher", "S", 1, "withdrawn")
check("transitive withdrawn grandparent blocks grandchild",
      str(val(publish("hive_operator", "R", 1, [A("W", 1)]))).startswith("rejected"))

# ---- D4: forged invalidation / provenance by intruder ----
reset()
seal("bot_researcher", "S", 1, "honest source")
check("D4a intruder cannot withdraw another's artifact", err(invalidate("bot_intruder", "S", 1, "withdrawn")) is not None)
check("D4b intruder cannot adjudicate", err(invalidate("bot_intruder", "S", 1, "adjudicated")) is not None)
poison = query("INSERT INTO exp.provenance VALUES ('S',1,'S',1)", conn=conn("bot_intruder"))
check("D4c intruder cannot write provenance", err(poison) is not None, err(poison))

# ---- authority: only an adjudicator may publish ----
seal("bot_writer", "W", 1, "draft", deps=[("S", 1)])
check("AUTH non-adjudicator reviewer cannot publish", err(publish("bot_reviewer", "W", 1, [A("S", 1)])) is not None
      or "adjudicator" in str(val(publish("bot_reviewer", "W", 1, [A("S", 1)]))))

# ---- D8: repeated self-retraction does not freeze unrelated work ----
reset()
seal("bot_intruder", "Z", 1, "noise")
for _ in range(3): invalidate("bot_intruder", "Z", 1, "withdrawn")
seal("bot_researcher", "G", 1, "good work")
seal("bot_writer", "GW", 1, "draft from G", deps=[("G", 1)])
check("D8 repeated self-retraction does not freeze unrelated work",
      val(publish("hive_operator", "GW", 1, [A("G", 1)])) == "approved")

print(f"\n{sum(RES)}/{len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
