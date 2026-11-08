"""D6: the approval/retraction race, with REAL concurrent transactions, against the SEALED gate.

Rewritten 2026-11-07 for the frozen gate (d2df880 + addenda). The earlier version predated sealed creation:
it inserted artifacts as bots (now denied) and it TRUNCATED the shared tables (never again; this version
uses prefixed ids and deletes only its own rows).

  A. NAIVE check-then-approve (two steps, a gap between): a withdrawal that commits in the gap produces a
     BAD approval of a withdrawn dependency. (Written directly to approvals as the operator to show the hazard.)
  B. ATOMIC gate, retraction already committed: publish_decision rejects.
  C. ATOMIC gate under SERIALIZABLE: the fence REFUSES (0A000) instead of approving against a stale snapshot.
  D. ATOMIC gate, READ COMMITTED, withdrawal committed while the gate holds the fence: the gate sees it.

Run: python -I tools/race_test.py
"""
import json, sys, threading, time, uuid
import psycopg

OP = open("secrets/operator.env").read().split("=", 1)[1].strip()
pw = json.load(open("secrets/bot_passwords.json"))
HOST = OP.split("@")[1].split("/")[0]
conn_str = lambda b: OP if b == "hive_operator" else f"postgresql://{b}:{pw[b]}@{HOST}/hive?sslmode=require"
P = "prace_" + uuid.uuid4().hex[:6] + "_"
RES = []
def check(name, cond, detail=""):
    RES.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {detail}" if detail else ""))

def op(sql, params=None, fetch=False):
    with psycopg.connect(OP, sslmode="require", autocommit=True) as c:
        cur = c.execute(sql, params or [])
        return cur.fetchall() if fetch else None

def fresh():
    """New S/W pair under this test's prefix; nothing shared is touched."""
    s, w = P + uuid.uuid4().hex[:4] + "S", P + uuid.uuid4().hex[:4] + "W"
    op("SELECT exp.seal_artifact('bot_researcher',%s,1,'finding','[]'::jsonb)", (s,))
    op("SELECT exp.seal_artifact('bot_writer',%s,1,'draft',%s::jsonb)", (w, json.dumps([{"id": s, "ver": 1}])))
    return s, w

def withdraw(s):
    with psycopg.connect(conn_str("bot_researcher"), sslmode="require", autocommit=True) as c:
        c.execute("SELECT exp.invalidate(%s,1,'withdrawn')", (s,))     # author-only path, as the authenticated author role

# ---- A. NAIVE check-then-approve races the retraction ----
S, W = fresh()
gate = psycopg.connect(OP, sslmode="require"); gate.autocommit = False
seen = gate.execute("SELECT COALESCE(MAX(epoch),0) FROM exp.invalidations WHERE artifact_id=%s AND version=1 AND kind IN ('withdrawn','adjudicated')", (S,)).fetchone()[0]
withdraw(S)                                        # retraction lands in the gap
gate.execute("INSERT INTO exp.approvals(artifact_id,version,reviewer,decision,reason) VALUES (%s,1,'naive_monitor','approved','checked earlier')", (W,))
gate.commit(); gate.close()
bad = op("SELECT decision FROM exp.approvals WHERE artifact_id=%s AND reviewer='naive_monitor'", (W,), fetch=True)
check("A naive check-then-approve produces a BAD approval of a withdrawn dep", bad and bad[0][0] == "approved", f"seen-clean-epoch={seen}")

# ---- B. ATOMIC gate, retraction already committed -> reject ----
S, W = fresh(); withdraw(S)
with psycopg.connect(OP, sslmode="require") as c:
    c.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
    r = c.execute("SELECT exp.publish_decision(%s,1,%s::jsonb)", (W, json.dumps([{"id": S, "ver": 1}]))).fetchone()[0]; c.commit()
check("B atomic gate rejects once retraction is committed", str(r).startswith("rejected"), r)

# ---- C. SERIALIZABLE snapshot predating the retraction: the fence refuses rather than approving stale ----
S, W = fresh()
gate = psycopg.connect(OP, sslmode="require"); gate.autocommit = False
gate.execute("BEGIN ISOLATION LEVEL SERIALIZABLE"); gate.execute("SELECT 1").fetchone()   # snapshot now
withdraw(S)
try:
    gate.execute("SELECT exp.publish_decision(%s,1,%s::jsonb)", (W, json.dumps([{"id": S, "ver": 1}]))).fetchone(); gate.commit()
    check("C fence refuses a non READ COMMITTED publish", False, "approved or rejected without refusing")
except psycopg.Error as e:
    gate.rollback(); check("C fence refuses a non READ COMMITTED publish (0A000)", e.sqlstate == "0A000", f"{e.sqlstate}: {str(e).splitlines()[0][:70]}")
finally:
    gate.close()

# ---- D. READ COMMITTED gate vs a withdrawal racing for the fence ----
S, W = fresh()
results = {}
def publisher():
    with psycopg.connect(OP, sslmode="require") as c:
        c.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
        results["gate"] = c.execute("SELECT exp.publish_decision(%s,1,%s::jsonb)", (W, json.dumps([{"id": S, "ver": 1}]))).fetchone()[0]; c.commit()
def withdrawer():
    time.sleep(0.05); withdraw(S); results["withdrawn_at"] = time.time()
t1, t2 = threading.Thread(target=publisher), threading.Thread(target=withdrawer); t1.start(); t2.start(); t1.join(); t2.join()
approved_rows = op("SELECT decision FROM exp.approvals WHERE artifact_id=%s AND reviewer<>'naive_monitor'", (W,), fetch=True)
stale_current = op("SELECT count(*) FROM exp.current_approvals WHERE artifact_id=%s", (W,), fetch=True)[0][0]
# Either order is legal; what must hold: no approval is CURRENT once the withdrawal is committed.
check("D after a racing withdrawal, current_approvals shows no live approval of the derived draft", stale_current == 0, f"gate={results.get('gate')} rows={approved_rows}")

# cleanup: only this test's rows
op("DELETE FROM exp.approvals WHERE artifact_id LIKE %s ESCAPE '!'", (P.replace("_", "!_") + "%",))
print(f"\n{sum(RES)}/{len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
