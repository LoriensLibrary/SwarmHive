"""D6: the approval/retraction race, with REAL concurrent transactions.

Lorien's point: a monitor that checks dependency state and THEN approves in a
separate step can race a retraction that lands in the gap. This test uses two
live psycopg connections to show:

  A. NAIVE check-then-approve (two steps, a gap between): a withdrawal that
     commits in the gap produces a BAD approval of a withdrawn dependency.
  B. ATOMIC gate, retraction already committed: publish_decision rejects.
  C. ATOMIC gate under SERIALIZABLE whose snapshot predates the retraction:
     the approval LINEARIZES BEFORE the retraction (valid at its logical time),
     and a reconciliation query then flags the derived artifact as
     needs-revalidation. We report exactly which of these Postgres does, rather
     than claim serialization magically prevents it.

Run: python -I tools/race_test.py
"""
import hashlib, json, sys
import psycopg

OP = open("secrets/operator.env").read().split("=", 1)[1].strip()
pw = json.load(open("secrets/bot_passwords.json"))
HOST = "ep-summer-paper-bbe7uhtw.c-15.us-east-1.aws.neon.tech"
conn_str = lambda b: OP if b == "hive_operator" else f"postgresql://{b}:{pw[b]}@{HOST}/hive?sslmode=require"
h = lambda s: hashlib.sha256(s.encode()).hexdigest()
RES = []
def check(name, cond, detail=""):
    RES.append(cond); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  <- {detail}" if detail else ""))

def op_exec(sql, params=None, fetch=False):
    with psycopg.connect(OP, sslmode="require") as c:
        with c.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall() if fetch else None

def setup():
    op_exec("TRUNCATE exp.approvals, exp.invalidations, exp.provenance, exp.artifacts")
    # S v1 by researcher, W v1 by writer derived from S
    with psycopg.connect(conn_str("bot_researcher"), sslmode="require") as c:
        c.execute("INSERT INTO exp.artifacts(artifact_id,version,author_role,body,content_hash) VALUES ('S',1,'bot_researcher',%s,%s)",
                  ("finding", h("finding"))); c.commit()
    with psycopg.connect(conn_str("bot_writer"), sslmode="require") as c:
        c.execute("INSERT INTO exp.artifacts(artifact_id,version,author_role,body,content_hash) VALUES ('W',1,'bot_writer',%s,%s)",
                  ("draft", h("draft"))); c.execute("INSERT INTO exp.provenance VALUES ('W',1,'S',1)"); c.commit()

def withdraw_S():
    with psycopg.connect(conn_str("bot_researcher"), sslmode="require") as c:
        c.execute("SELECT exp.invalidate('S',1,'withdrawn')"); c.commit()

# ---- A. NAIVE check-then-approve races the retraction ----
setup()
gate = psycopg.connect(OP, sslmode="require"); gate.autocommit = False
with gate.cursor() as cur:
    cur.execute("SELECT COALESCE(MAX(epoch),0) FROM exp.invalidations WHERE artifact_id='S' AND version=1 AND kind IN ('withdrawn','adjudicated')")
    seen = cur.fetchone()[0]                      # monitor sees clean (0)
withdraw_S()                                       # retraction lands in the gap
with gate.cursor() as cur:                         # monitor approves based on its stale check
    cur.execute("INSERT INTO exp.approvals(artifact_id,version,reviewer,decision,reason) VALUES ('W',1,'naive_monitor','approved','checked earlier')")
gate.commit(); gate.close()
bad = op_exec("SELECT decision FROM exp.approvals WHERE reviewer='naive_monitor'", fetch=True)
check("A naive check-then-approve produces a BAD approval of a withdrawn dep",
      bad and bad[0][0] == "approved", f"seen-clean-epoch={seen}, approval={bad}")

# ---- B. ATOMIC gate, retraction already committed -> reject ----
setup(); withdraw_S()
r = op_exec("SELECT exp.publish_decision('W',1,'[{\"id\":\"S\",\"ver\":1,\"acked_epoch\":0}]'::jsonb)", fetch=True)
check("B atomic gate rejects once retraction is committed", str(r[0][0]).startswith("rejected"), r[0][0])

# ---- C. ATOMIC gate under SERIALIZABLE, snapshot before the retraction ----
setup()
gate = psycopg.connect(OP, sslmode="require"); gate.autocommit = False
gate.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
with gate.cursor() as cur:
    cur.execute("SELECT 1"); cur.fetchone()        # take the snapshot now (pre-retraction)
withdraw_S()                                        # retraction commits in another txn
serialization_error = None; gate_result = None
try:
    with gate.cursor() as cur:
        cur.execute("SELECT exp.publish_decision('W',1,'[{\"id\":\"S\",\"ver\":1,\"acked_epoch\":0}]'::jsonb)")
        gate_result = cur.fetchone()[0]
    gate.commit()
except psycopg.errors.SerializationFailure as e:
    serialization_error = str(e).splitlines()[0]; gate.rollback()
finally:
    gate.close()
# Reconciliation: find approvals whose dependency now carries a blocking invalidation.
recon = op_exec("""
  SELECT a.artifact_id, a.version FROM exp.approvals a
  JOIN exp.provenance p ON p.derived_id=a.artifact_id AND p.derived_ver=a.version
  JOIN exp.invalidations i ON i.artifact_id=p.source_id AND i.version=p.source_ver
   AND i.kind IN ('withdrawn','adjudicated')
  WHERE a.decision='approved'""", fetch=True)
if serialization_error:
    check("C SERIALIZABLE raised 40001, gate retried would see the retraction", True, serialization_error)
else:
    linearized_before = gate_result == "approved"
    flagged = ("W", 1) in [tuple(x) for x in (recon or [])]
    check("C gate approved against pre-retraction snapshot (linearized before)", linearized_before, f"gate={gate_result}")
    check("C reconciliation flags the stale approval for revalidation", flagged, f"recon={recon}")

print(f"\n{sum(RES)}/{len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
