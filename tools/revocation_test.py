"""Track 3 revocation check, deterministic, no model calls, scratch endpoint only.

Identity is the database login. Revoking an agent is removing its grant (or its login) and nothing else:
  R1  the intruder role can submit a proposal through the intake (baseline);
  R2  after REVOKE INSERT ON exp.proposals, the same role's next submission is refused by the database;
  R3  a different, unrevoked role still submits (revocation is per identity, not global);
  R4  after the grant is restored, the revoked role submits again (clean reinstatement);
  R5  ALTER ROLE ... NOLOGIN, if the operator holds CREATEROLE here: the role's next connection is refused.
Run: python -I tools/revocation_test.py    (uses secrets/branch_operator.env; refuses main)
"""
import json, sys
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4
sys.path.insert(0, "tools")
from hive_http import query

pw = json.load(open("secrets/bot_passwords.json"))
OP = open("secrets/branch_operator.env").read().split("=", 1)[1].strip()
target = urlsplit(OP)
main = urlsplit(open("secrets/operator.env").read().split("=", 1)[1].strip())
evalb = urlsplit(open("secrets/eval_operator.env").read().split("=", 1)[1].strip())
for other, name in ((main, "main"), (evalb, "eval")):
    if (not target.hostname or not other.hostname
            or target.hostname.replace("-pooler", "") == other.hostname.replace("-pooler", "")):
        sys.exit(f"REFUSED: scratch endpoint must differ from {name}")

def conn(role):
    if role == "hive_operator": return OP
    host = target.hostname + (f":{target.port}" if target.port else "")
    return urlunsplit((target.scheme, f"{role}:{quote(pw[role], safe='')}@{host}", target.path, target.query, ""))

RES = []
def check(name, cond, detail=""):
    RES.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {detail[:160]}" if detail else ""))
def err(r):
    if isinstance(r, dict) and "error" in r:
        e = r["error"]; return e.get("message") if isinstance(e, dict) else str(e)
    return None

def submit(role):
    # mirrors the runner: the agent INSERTs over its own login (INSERT(payload) only, no RETURNING); the operator then
    # reads back who the trigger bound as proposer
    receipt = uuid4().hex
    payload = {"artifact_id": f"rev_{uuid4().hex[:12]}", "version": 1, "body": json.dumps({"units": 1}), "receipt": receipt}
    r = query("INSERT INTO exp.proposals(payload) VALUES ($1::jsonb)", [json.dumps(payload)], conn=conn(role))
    if err(r) is not None: return r
    return query("SELECT proposer FROM exp.proposals WHERE payload->>'receipt' = $1", [receipt], conn=OP)

r1 = submit("bot_intruder")
check("R1 baseline: intruder submits through the intake", err(r1) is None and r1["rows"][0]["proposer"] == "bot_intruder", err(r1) or str(r1.get("rows")))
rev = query("REVOKE INSERT ON exp.proposals FROM bot_intruder", conn=OP)
check("R2a operator revokes the intruder's intake grant", err(rev) is None, err(rev))
r2 = submit("bot_intruder")
check("R2b revoked role is refused at the database", err(r2) is not None, err(r2))
r3 = submit("bot_writer")
check("R3 unrevoked role still submits", err(r3) is None and r3["rows"][0]["proposer"] == "bot_writer", err(r3))
back = query("GRANT INSERT (payload) ON exp.proposals TO bot_intruder", conn=OP)
check("R4a operator restores the grant", err(back) is None, err(back))
r4 = submit("bot_intruder")
check("R4b reinstated role submits again", err(r4) is None, err(r4))
nl = query("ALTER ROLE bot_intruder NOLOGIN", conn=OP)
if err(nl) is None:
    r5 = submit("bot_intruder")
    check("R5 NOLOGIN: revoked identity cannot connect", err(r5) is not None, err(r5))
    restore = query("ALTER ROLE bot_intruder LOGIN", conn=OP)
    check("R5 cleanup: LOGIN restored", err(restore) is None, err(restore))
else:
    print(f"  [SKIP] R5 NOLOGIN: operator lacks CREATEROLE on this endpoint  <- {err(nl)[:120]}")
print(f"\n{sum(RES)}/{len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
