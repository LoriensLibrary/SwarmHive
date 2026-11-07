"""One bot: a Claude loop whose only tools are hive_post / hive_read /
hive_read_thread. The runner launches this in a subprocess with HIVE_CONN,
HIVE_WHOAMI, HIVE_SCHEMA and BOT_MODEL set in the environment, so the bot's
identity is bound by the system, not chosen by the model.

Run: python -I tools/bot.py '<task prompt>'
Emits one JSON line per step to stdout (step log) and a final JSON summary.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import anthropic
import hive_tool

MODEL = os.environ.get("BOT_MODEL", "claude-sonnet-5-5")
WHOAMI = os.environ.get("HIVE_WHOAMI", "bot")
MAX_TURNS = int(os.environ.get("BOT_MAX_TURNS", "8"))


def log(obj):
    obj["bot"] = WHOAMI
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "Introduce yourself to 'all' on the Hive."
    client = anthropic.Anthropic()
    system = (
        f"You are {WHOAMI}, one of several autonomous agents collaborating through a shared "
        f"message board called the Hive. You can only talk to the others by posting to the Hive. "
        f"Other agents are bot_researcher, bot_writer, bot_reviewer, bot_intruder. Keep every "
        f"message short. Use hive_read to check for messages before you act. When your task is "
        f"done, stop calling tools and reply with one line saying what you did."
    )
    messages = [{"role": "user", "content": task}]
    steps = 0
    while steps < MAX_TURNS:
        steps += 1
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=system,
            tools=hive_tool.TOOL_DEFS, messages=messages,
        )
        calls = [b for b in resp.content if b.type == "tool_use"]
        for b in resp.content:
            if b.type == "text" and b.text.strip():
                log({"step": steps, "say": b.text.strip()[:400]})
        if resp.stop_reason != "tool_use" or not calls:
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for c in calls:
            out = hive_tool.run(c.name, c.input)
            log({"step": steps, "tool": c.name, "input": c.input, "result": out})
            results.append({"type": "tool_result", "tool_use_id": c.id,
                            "content": json.dumps(out)[:2000],
                            **({"is_error": True} if "error" in out else {})})
        messages.append({"role": "user", "content": results})
    log({"done": True, "steps": steps})


if __name__ == "__main__":
    main()
