# Loads the API key from secrets/anthropic.key into the environment without
# printing it. Imported by the runner; also runnable alone as an auth check.
import os, sys
def load():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    p = os.path.join("secrets", "anthropic.key")
    if not os.path.exists(p):
        return False
    k = open(p, encoding="utf-8-sig").read().strip()
    if not k:
        return False
    os.environ["ANTHROPIC_API_KEY"] = k
    return True
if __name__ == "__main__":
    if not load():
        print("NO KEY: secrets/anthropic.key missing or empty"); sys.exit(1)
    import anthropic
    try:
        r = anthropic.Anthropic().messages.create(
            model="claude-haiku-5-5", max_tokens=16,
            messages=[{"role": "user", "content": "reply with the single word: ok"}])
        print("AUTH OK:", "".join(b.text for b in r.content if b.type == "text").strip())
    except Exception as e:
        print("AUTH FAIL:", type(e).__name__, str(e)[:160])
