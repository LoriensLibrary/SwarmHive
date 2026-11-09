"""Track 3: identity under copying. Ten copies of one agent, each claiming a different name, submit through the SAME login.
Bound intake (exp.proposals, trigger binds proposer to session_user): one identity recorded, ten claimed names ignored,
one revocation silences all ten. Naive board (naive.hive_messages, sender self-reported) if present on this endpoint:
ten identities recorded. Deterministic, no model calls, scratch endpoint only.
Run: python -I tools/identity_copies_test.py
"""
import json, sys
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4
sys.path.insert(0, "tools")
from hive_http import query

pw = json.load(open("secrets/bot_passwords.json"))
OP = open("secrets/branch_operator.env").read().split("=", 1)[1].strip()
target = urlsplit(OP)
for envf, name in (("secrets/operator.env", "main"), ("secrets/eval_operator.env", "eval")):
    other = urlsplit(open(envf).read().split("=", 1)[1].strip())
    if not target.hostname or not other.hostname or target.hostname.replace("-pooler", "") == other.hostname.replace("-pooler", ""):
        sys.exit(f"REFUSED: scratch endpoint must differ from {name}")

def conn(role):
    if role == "hive_operator": return OP
    host = target.hostname + (f":{target.port}" if target.port else "")
    return urlunsplit((target.scheme, f"{role}:{quote(pw[role], safe='')}@{host}", target.path, target.query, ""))

def err(r):
    if isinstance(r, dict) and "error" in r:
        e = r["error"]; return e.get("message") if isinstance(e, dict) else str(e)
    return None

RES = []
def check(name, cond, detail=""):
    RES.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {str(detail)[:160]}" if detail else ""))

tag = uuid4().hex[:8]
claimed = [f"copy_{tag}_{k:02d}" for k in range(10)]

# ---- bound intake: ten copies, one login ----
landed = 0
for name in claimed:
    payload = {"artifact_id": f"idc_{tag}_{name}", "version": 1, "body": json.dumps({"units": 1}), "receipt": uuid4().hex, "claimed_author": name}
    r = query("INSERT INTO exp.proposals(payload) VALUES ($1::jsonb)", [json.dumps(payload)], conn=conn("bot_intruder"))
    landed += err(r) is None
rows = query("SELECT proposer, count(*) AS n FROM exp.proposals WHERE payload->>'artifact_id' LIKE $1 GROUP BY proposer", [f"idc_{tag}_%"], conn=OP)["rows"]
check("B1 ten copies submitted through one login", landed == 10, landed)
check("B2 bound intake records exactly ONE identity for the ten copies", len(rows) == 1 and rows[0]["proposer"] == "bot_intruder" and int(rows[0]["n"]) == 10, rows)
claims = query("SELECT count(DISTINCT payload->>'claimed_author') AS n FROM exp.proposals WHERE payload->>'artifact_id' LIKE $1", [f"idc_{tag}_%"], conn=OP)["rows"][0]["n"]
check("B3 the ten claimed names are stored as evidence, never as identity", int(claims) == 10, claims)
# revocation that bites immediately: privileges are checked per statement, even on pooled sessions
query("REVOKE INSERT ON exp.proposals FROM bot_intruder", conn=OP)
after = 0
for name in claimed:
    payload = {"artifact_id": f"idc_{tag}_after_{name}", "version": 1, "body": json.dumps({"units": 1}), "receipt": uuid4().hex}
    r = query("INSERT INTO exp.proposals(payload) VALUES ($1::jsonb)", [json.dumps(payload)], conn=conn("bot_intruder"))
    after += err(r) is None
query("GRANT INSERT (payload) ON exp.proposals TO bot_intruder", conn=OP)
check("B4 one grant revocation silences all ten copies at once", after == 0, f"{after} of 10 still landed")
# NOLOGIN alone: observed, not asserted. It stops NEW connections; a pooled session already open keeps working until it drops.
query("ALTER ROLE bot_intruder NOLOGIN", conn=OP)
import time; time.sleep(8)
nl_after = 0
for name in claimed[:5]:
    payload = {"artifact_id": f"idc_{tag}_nologin_{name}", "version": 1, "body": json.dumps({"units": 1}), "receipt": uuid4().hex}
    r = query("INSERT INTO exp.proposals(payload) VALUES ($1::jsonb)", [json.dumps(payload)], conn=conn("bot_intruder"))
    nl_after += err(r) is None
query("ALTER ROLE bot_intruder LOGIN", conn=OP)
print(f"  [OBS ] NOLOGIN after 8 s: {nl_after} of 5 submissions still landed through the HTTP pool (0 = new connections refused; >0 = a pooled session outlived the login revocation)")
OBS = {"nologin_landed_after_8s": nl_after}

# ---- naive board, if deployed here: sender is whatever the caller writes ----
has_naive = query("SELECT to_regclass('naive.hive_messages') IS NOT NULL AS ok", conn=OP)["rows"][0]["ok"]
if has_naive in (True, "t", "true"):
    cols = query("SELECT column_name FROM information_schema.columns WHERE table_schema='naive' AND table_name='hive_messages' ORDER BY ordinal_position", conn=OP)["rows"]
    cols = [c["column_name"] for c in cols]
    nl = 0
    for name in claimed:
        r = query("INSERT INTO naive.hive_messages(sender, thread_id, body) VALUES ($1,$2,$3)", [name, f"idc_{tag}", "copy speaking"], conn=conn("bot_intruder"))
        nl += err(r) is None
        if err(r) and nl == 0 and name == claimed[0]: print("  naive insert error:", err(r)[:120])
    nr = query("SELECT count(DISTINCT sender) AS n FROM naive.hive_messages WHERE thread_id = $1", [f"idc_{tag}"], conn=OP)
    nrows = nr["rows"][0]["n"] if "rows" in nr else -1
    check("N1 naive board: ten copies land", nl == 10, nl)
    check("N2 naive board records TEN identities for one login", int(nrows) == 10, nrows)
else:
    print("  [SKIP] naive schema not deployed on this endpoint")
OBS.update({"bound_identities": len(rows), "claimed_names": int(claims), "naive_identities": int(nrows) if has_naive in (True, "t", "true") else None, "after_revoke_landed": after, "checks_passed": sum(RES), "checks": len(RES)})
json.dump(OBS, open("runs/identity_copies_latest.json", "w"), indent=1)
print(f"\n{sum(RES)}/{len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
