"""Lorien's live reproduction (2026-11-08 01:37), re-run against the hardened gate:
  session A (bot): advisory 'contradicted' on S/1, transaction left OPEN
  session B (bot author): blocking 'withdrawn' on S/1 -> must NOT wait on A
  session C (operator): publish an UNRELATED draft -> must NOT wait behind B/A
Checked with pg_blocking_pids on the SCRATCH branch (prefixed ids, nothing shared touched). Then the receipt-bound
seal: a same-role session racing a substitute body for the same artifact/version is refused.
Run: python -I tools/test_advisory_bridge.py   (uses secrets/branch_operator.env; refuses the main host)
"""
import json, sys, threading, time, uuid
import psycopg
OP = open("secrets/branch_operator.env").read().split("=", 1)[1].strip()
if "ep-summer-paper" in OP: sys.exit("REFUSED: run this on the scratch branch")
pw = json.load(open("secrets/bot_passwords.json")); HOST = OP.split("@")[1].split("/")[0]
bot = lambda b, **kw: psycopg.connect(f"postgresql://{b}:{pw[b]}@{HOST}/hive", sslmode="require", **kw)
P = "pbridge_" + uuid.uuid4().hex[:6] + "_"; RES = []
def check(name, cond, detail=""): RES.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {detail}" if detail else ""))
op = psycopg.connect(OP, sslmode="require", autocommit=True)
S, W, U, UW = P + "S", P + "W", P + "U", P + "UW"
for aid, author, deps in ((S, "bot_researcher", []), (W, "bot_writer", [{"id": S, "ver": 1}]), (U, "bot_researcher", []), (UW, "bot_writer", [{"id": U, "ver": 1}])):
    op.execute("SELECT exp.seal_artifact(%s,%s,1,%s,%s::jsonb)", (author, aid, "body " + aid, json.dumps(deps)))

# A: advisory, left open
A = bot("bot_intruder", autocommit=False); A.execute("SELECT exp.invalidate(%s,1,'contradicted')", (S,)); a_pid = A.execute("SELECT pg_backend_pid()").fetchone()[0]
# B: blocking withdrawal by the author, in a thread so we can watch whether it blocks
b_state = {}
def withdraw():
    B = bot("bot_researcher", autocommit=False); b_state["pid"] = B.execute("SELECT pg_backend_pid()").fetchone()[0]
    t0 = time.time(); B.execute("SELECT exp.invalidate(%s,1,'withdrawn')", (S,)); b_state["took"] = time.time() - t0; b_state["conn"] = B   # hold the fence open deliberately
tb = threading.Thread(target=withdraw); tb.start(); time.sleep(1.0)
blocking_b = op.execute("SELECT pg_blocking_pids(%s)", (b_state.get("pid", 0),)).fetchone()[0] if "pid" in b_state else None
check("B blocking withdrawal did not wait on A's open advisory", "took" in b_state and a_pid not in (blocking_b or []), f"blocking_pids(B)={blocking_b} took={b_state.get('took', None)}")
# C: unrelated publish while B holds the fence (B is a legitimate blocking write; it must finish, then C proceeds). Commit B now.
b_state["conn"].commit(); tb.join()
t0 = time.time()
with psycopg.connect(OP, sslmode="require") as C:
    C.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
    r = C.execute("SELECT exp.publish_decision(%s,1,%s::jsonb)", (UW, json.dumps([{"id": U, "ver": 1}]))).fetchone()[0]; C.commit()
check("C unrelated publication proceeds while A's advisory transaction is still open", r == "approved" and time.time() - t0 < 5, f"{r} in {time.time()-t0:.2f}s")
check("A's advisory landed in exp.advisories, not in the blocking keyspace", op.execute("SELECT count(*) FROM exp.invalidations WHERE artifact_id=%s AND kind='contradicted'", (S,)).fetchone()[0] == 0)
A.rollback(); A.close()

# receipt-bound seal: same-role substitute body is refused
receipt = uuid.uuid4().hex + uuid.uuid4().hex[:16]; X = P + "X"
honest = json.dumps({"units": 5}); forged = json.dumps({"units": 55})
with bot("bot_writer", autocommit=True) as w1: w1.execute("INSERT INTO exp.proposals(payload) VALUES (%s::jsonb)", (json.dumps({"artifact_id": X, "version": 1, "body": honest, "receipt": receipt}),))
with bot("bot_writer", autocommit=True) as w2: w2.execute("INSERT INTO exp.proposals(payload) VALUES (%s::jsonb)", (json.dumps({"artifact_id": X, "version": 1, "body": forged}),))   # racing substitute, no receipt
import hashlib
k = op.execute("SELECT exp.seal_from_receipt(%s,%s,%s,'[]'::jsonb)", (receipt, "bot_writer", hashlib.sha256(honest.encode()).hexdigest())).fetchone()[0]
check("receipt-bound seal takes the honest body despite a later same-role substitute", k == "root" and op.execute("SELECT body FROM exp.artifacts WHERE artifact_id=%s", (X,)).fetchone()[0] == honest)
try:
    op.execute("SELECT exp.seal_from_receipt(%s,%s,%s,'[]'::jsonb)", (receipt, "bot_writer", hashlib.sha256(forged.encode()).hexdigest())); check("wrong body hash refused", False)
except psycopg.Error as e: op.rollback() if not op.autocommit else None; check("wrong body hash / already sealed refused", True, str(e).splitlines()[0][:70])
try:
    r2 = uuid.uuid4().hex * 2; Y = P + "Y"
    with bot("bot_intruder", autocommit=True) as i1: i1.execute("INSERT INTO exp.proposals(payload) VALUES (%s::jsonb)", (json.dumps({"artifact_id": Y, "version": 1, "body": honest, "receipt": r2}),))
    op.execute("SELECT exp.seal_from_receipt(%s,%s,%s,'[]'::jsonb)", (r2, "bot_writer", hashlib.sha256(honest.encode()).hexdigest())); check("intruder proposal with expected author writer refused", False)
except psycopg.Error as e: check("intruder proposal with expected author writer refused", "does not match" in str(e), str(e).splitlines()[0][:70])
try:
    r3 = uuid.uuid4().hex * 2; Z = P + "Z"
    with bot("bot_writer", autocommit=True) as w3: w3.execute("INSERT INTO exp.proposals(payload) VALUES (%s::jsonb)", (json.dumps({"artifact_id": Z, "version": "1", "body": honest, "receipt": r3}),))
    op.execute("SELECT exp.seal_from_receipt(%s,%s,%s,'[]'::jsonb)", (r3, "bot_writer", hashlib.sha256(honest.encode()).hexdigest())); check("string version refused", False)
except psycopg.Error as e: check("string version refused (no ::int cast surprise)", "version" in str(e), str(e).splitlines()[0][:70])
print(f"\n{sum(RES)}/{len(RES)} checks passed"); sys.exit(0 if all(RES) else 1)
