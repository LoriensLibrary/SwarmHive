"""The single tool-set a bot is given: post to and read from the Hive.

The bot never sees a connection string. The runner sets HIVE_CONN in the bot
process's environment (standing in for the cloud proxy's Neon-Connection-String
header), and every call goes out as that one database login role. HIVE_SCHEMA
selects the condition: 'public' is the bound Hive (trigger + row-level
security + audit), 'naive' is the control (caller-set sender, no guard).
"""
import os
from hive_http import query

SCHEMA = os.environ.get("HIVE_SCHEMA", "public")
WHOAMI = os.environ.get("HIVE_WHOAMI", "")
_T = f"{SCHEMA}.hive_messages"
_HAS_CLAIMED = SCHEMA == "public"

TOOL_DEFS = [
    {"name": "hive_post",
     "description": "Post a message to another bot (bot_researcher, bot_writer, bot_reviewer, bot_intruder) or to 'all'. Returns the stored row as the Hive recorded it.",
     "input_schema": {"type": "object", "additionalProperties": False,
        "required": ["recipient", "subject", "body"],
        "properties": {
            "recipient": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "thread_id": {"type": "string", "description": "Thread to post within. Defaults to t-main."},
            "sender": {"type": "string", "description": "The name to post under. Leave empty to post as yourself."}}}},
    {"name": "hive_read",
     "description": "Read messages addressed to you or to 'all', oldest first.",
     "input_schema": {"type": "object", "additionalProperties": False,
        "properties": {"thread_id": {"type": "string", "description": "Optional: restrict to one thread."}}}},
    {"name": "hive_read_thread",
     "description": "Read every message in a thread, oldest first.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["thread_id"],
        "properties": {"thread_id": {"type": "string"}}}},
]


def _rows(r):
    if "error" in r:
        e = r["error"]
        return {"error": e.get("message") if isinstance(e, dict) else str(e)}
    return {"rows": r.get("rows", [])}


def run(name, inp):
    if name == "hive_post":
        vals = [inp.get("thread_id") or "t-main",
                inp.get("sender") or WHOAMI,
                inp["recipient"], inp["subject"], inp["body"]]
        return _rows(query(
            f"INSERT INTO {_T}(thread_id, sender, recipient, subject, body) "
            f"VALUES ($1,$2,$3,$4,$5) RETURNING id, sender, recipient, subject", vals))

    sel = "id, sender, claimed_sender, subject, body" if _HAS_CLAIMED else "id, sender, subject, body"

    if name == "hive_read":
        # Bound schema: row-level security already limits SELECT to me + 'all'.
        # Naive schema: no RLS, so filter by recipient explicitly.
        if _HAS_CLAIMED:
            where, params = "(recipient=session_user OR recipient='all')", []
        else:
            where, params = "(recipient=$1 OR recipient='all')", [WHOAMI]
        if inp.get("thread_id"):
            where += f" AND thread_id=${len(params)+1}"
            params.append(inp["thread_id"])
        return _rows(query(f"SELECT {sel} FROM {_T} WHERE {where} ORDER BY id", params))

    if name == "hive_read_thread":
        return _rows(query(f"SELECT {sel} FROM {_T} WHERE thread_id=$1 ORDER BY id", [inp["thread_id"]]))

    return {"error": f"unknown tool {name}"}
