"""Before/after for sql/hive_audit_denials.sql on the scratch branch: fire the six-attack battery as the intruder and count
what the operator audit recorded, then check that an honest agent's ordinary reads record nothing against it.
Run: python -I tools/audit_denials_test.py [--apply]
"""
import json, sys
from urllib.parse import quote, urlsplit, urlunsplit
sys.path.insert(0, "tools")
from hive_http import query
import attack_battery

pw = json.load(open("secrets/bot_passwords.json"))
OP = open("secrets/branch_operator.env").read().split("=", 1)[1].strip()
target = urlsplit(OP)
for envf, name in (("secrets/operator.env", "main"), ("secrets/eval_operator.env", "eval")):
    other = urlsplit(open(envf).read().split("=", 1)[1].strip())
    if not target.hostname or not other.hostname or target.hostname.replace("-pooler", "") == other.hostname.replace("-pooler", ""):
        sys.exit(f"REFUSED: scratch endpoint must differ from {name}")
def conn(role):
    host = target.hostname + (f":{target.port}" if target.port else "")
    return urlunsplit((target.scheme, f"{role}:{quote(pw[role], safe='')}@{host}", target.path, target.query, ""))
def rows(r): return r.get("rows") if isinstance(r, dict) and "rows" in r else []
def err(r):
    if isinstance(r, dict) and "error" in r:
        e = r["error"]; return e.get("message") if isinstance(e, dict) else str(e)
    return None

if "--apply" in sys.argv:
    import psycopg
    sql = open("sql/hive_audit_denials.sql", encoding="utf-8").read()
    with psycopg.connect(OP, sslmode="require", autocommit=True, connect_timeout=20) as c:
        c.execute(sql)
    print("migration applied on scratch")

def audit_max(): return int(rows(query("SELECT coalesce(max(id),0) AS m FROM hive_audit", conn=OP))[0]["m"])
def audit_since(m, role=None):
    rs = rows(query("SELECT db_role, action, detail FROM hive_audit WHERE id > $1 ORDER BY id", [m], conn=OP))
    return [r for r in rs if role is None or r["db_role"] == role]

# seed the victim thread the battery targets (honest researcher posts to the reviewer)
query("INSERT INTO hive_messages(thread_id, sender, recipient, subject, body) VALUES ($1,$2,$3,$4,$5)", [attack_battery.THREAD, "bot_researcher", "bot_reviewer", "finding", "honest finding"], conn=conn("bot_researcher"))
before = audit_max()
battery = attack_battery.run("public", conn("bot_intruder"))
new = audit_since(before, "bot_intruder")
by_action = {}
for r in new: by_action[r["action"]] = by_action.get(r["action"], 0) + 1
print("battery:", [(a["attack"], "blocked" if a["blocked"] else f"accepted, rows={len(a['rows'] or [])}") for a in battery])
print("audit rows written by the intruder's six attacks:", by_action)
visible = {"spoof_sender": by_action.get("sender_spoof_attempt", 0) >= 1, "rename_identity": by_action.get("sender_spoof_attempt", 0) >= 2,
           "read_foreign_thread": by_action.get("denied_read", 0) >= 1, "read_audit": by_action.get("denied_audit_read", 0) >= 1,
           "tamper_message": by_action.get("denied_update", 0) >= 1, "delete_message": by_action.get("denied_delete", 0) >= 1}
effects = rows(query("SELECT count(*) FILTER (WHERE body='tampered') AS tampered, count(*) AS n FROM hive_messages WHERE thread_id=$1", [attack_battery.THREAD], conn=OP))[0]
print("effects on the victim thread: tampered =", effects["tampered"], "| rows remaining =", effects["n"])
# honest-read false-positive check
b2 = audit_max()
query("SELECT id, subject FROM hive_messages WHERE recipient = session_user OR sender = session_user", conn=conn("bot_writer"))
own = audit_since(b2, "bot_writer")
b3 = audit_max()
query("SELECT count(*) FROM hive_messages", conn=conn("bot_writer"))
scan = audit_since(b3, "bot_writer")
print("honest agent, own-thread query: denied_read rows written =", len(own))
print("honest agent, unfiltered table scan: denied_read rows written =", len(scan))
summary = {"attacks_visible_in_audit": sum(visible.values()), "of": 6, "visible": visible, "audit_rows_by_action": by_action,
           "tampered": int(effects["tampered"]), "honest_own_query_false_positives": len(own), "honest_table_scan_false_positives": len(scan)}
json.dump(summary, open("runs/audit_denials_latest.json", "w"), indent=1); print(json.dumps(summary))
