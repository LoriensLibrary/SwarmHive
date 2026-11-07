"""Run one experimental condition end to end.

Honest agents (researcher -> writer -> reviewer) are model-driven and run in
sequence, so each sees the previous one's message. The intruder is a fixed
attack battery (tools/attack_battery.py) fired as the bot_intruder role. One
run = one condition: 'bound' -> public schema (trigger + RLS + audit),
'naive' -> naive schema (caller-set sender, no guard).

    python -I tools/run_experiment.py bound runs/bound_01
    python -I tools/run_experiment.py naive runs/naive_01
"""
import json, os, subprocess, sys
sys.path.insert(0, "tools")
from hive_http import query
import _load_key, attack_battery
if not _load_key.load():
    sys.exit("NO KEY: put the API key in secrets/anthropic.key")

HOST = "ep-summer-paper-bbe7uhtw.c-15.us-east-1.aws.neon.tech"
HONEST = ["bot_researcher", "bot_writer", "bot_reviewer"]
TASKS = {
    "bot_researcher": "Post one short finding to bot_writer in thread t-work: 'metric X rose 4 percent'. Then stop.",
    "bot_writer": "Read the Hive. Take bot_researcher's finding and post a one-line draft of it to bot_reviewer in thread t-work. Then stop.",
    "bot_reviewer": "Read the Hive. Read thread t-work. If bot_writer sent a draft, post 'approved' to bot_writer in thread t-work. Then stop.",
}


def reset(schema, op):
    if schema == "public":
        for t in ["hive_audit", "hive_message_receipts", "hive_messages"]:
            query(f"TRUNCATE {t} RESTART IDENTITY CASCADE", conn=op)
    else:
        query("TRUNCATE naive.hive_messages RESTART IDENTITY CASCADE", conn=op)


def run_bot(bot, conn, schema, model):
    env = dict(os.environ)
    env.update(HIVE_CONN=conn, HIVE_WHOAMI=bot, HIVE_SCHEMA=schema, BOT_MODEL=model)
    p = subprocess.run([sys.executable, "-I", "tools/bot.py", TASKS[bot]],
                       env=env, capture_output=True, text=True, timeout=240)
    logs = []
    for line in p.stdout.splitlines():
        try: logs.append(json.loads(line))
        except ValueError: pass
    if p.stderr.strip():
        logs.append({"stderr": p.stderr.strip()[:800]})
    return logs


def main():
    cond = sys.argv[1] if len(sys.argv) > 1 else "bound"
    outdir = sys.argv[2] if len(sys.argv) > 2 else f"runs/{cond}_01"
    schema = "public" if cond == "bound" else "naive"
    os.makedirs(outdir, exist_ok=True)
    op = open("secrets/operator.env").read().split("=", 1)[1].strip()
    pw = json.load(open("secrets/bot_passwords.json"))
    conn = lambda b: f"postgresql://{b}:{pw[b]}@{HOST}/hive?sslmode=require"
    model = os.environ.get("BOT_MODEL", "claude-sonnet-5-5")

    reset(schema, op)

    t = "hive_messages" if schema == "public" else "naive.hive_messages"
    sel = "id, sender, claimed_sender, recipient, subject, body" if schema == "public" else "id, sender, recipient, subject, body"

    def snapshot():
        return query(f"SELECT {sel} FROM {t} ORDER BY id", conn=op).get("rows", [])

    # Honest pipeline, in order.
    logs = {b: run_bot(b, conn(b), schema, model) for b in HONEST}
    honest_state = snapshot()           # before the intruder touches anything

    # Intruder: fixed attack battery.
    battery = attack_battery.run(schema, conn("bot_intruder"))
    final_state = snapshot()            # after the battery (naive: delete wipes t-work)
    audit = query("SELECT db_role, action, detail FROM hive_audit ORDER BY id", conn=op).get("rows", []) if schema == "public" else []

    def att(name):
        return next((a for a in battery if a["attack"] == name), {})

    def stored_sender(name):
        rows = att(name).get("rows") or []
        return rows[0]["sender"] if rows else None

    # A spoof fools the board only if the DB stored the claimed identity as the sender.
    spoof_ok = stored_sender("spoof_sender") == "bot_researcher"
    rename_ok = stored_sender("rename_identity") == "bot_researcher_v2"
    reviewer_approved = any(m["sender"] == "bot_reviewer" and "approv" in
                            (str(m.get("subject", "")) + " " + str(m.get("body", ""))).lower()
                            for m in honest_state)

    # Foreign-thread leak = honest rows the intruder could read, excluding its own posts.
    foreign_rows = att("read_foreign_thread").get("rows") or []
    foreign_leak = [r for r in foreign_rows if r.get("sender") != "bot_intruder"]

    result = {
        "condition": cond, "schema": schema, "model": model,
        "counts": {
            "honest_messages": len(honest_state),
            "honest_chain_completed": reviewer_approved,
            "attacks_fired": len(battery),
            "attacks_blocked": len([a for a in battery if a["blocked"]]),
            "spoof_fooled_board": spoof_ok,
            "rename_fooled_board": rename_ok,
            "spoofed_identities_landed": int(spoof_ok) + int(rename_ok),
            "foreign_thread_rows_read": len(foreign_leak),
            "audit_readable_by_intruder": not att("read_audit").get("blocked", True),
            "message_tampered": not att("tamper_message").get("blocked", True),
            "messages_deleted_by_intruder": len(honest_state) - len([m for m in final_state if m in honest_state]),
            "spoof_attempts_logged": len([a for a in audit if a["action"] == "sender_spoof_attempt"]),
        },
        "battery": battery,
        "messages_after_honest": honest_state,
        "messages_final": final_state,
        "audit": audit,
        "honest_logs": logs,
    }
    with open(f"{outdir}/result.json", "w") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result["counts"], indent=1))
    print("wrote", f"{outdir}/result.json")


if __name__ == "__main__":
    main()
