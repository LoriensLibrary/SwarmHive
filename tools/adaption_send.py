"""Trusted send adapter for Adaption-hosted open models (REST, no SDK).

Implements the delivery_recorder `send(**request)` contract against Adaption's
Responses API so the SAME frozen experiment can be replicated on an open model
(model-replication arm). This is TRANSPORT ONLY: it maps field names and adds
no content, documents, memory or tools, so the receipt's request hash still
describes exactly what the model saw.

Field mapping (recorder request -> Adaption):
  model        -> model              (hosted model id, e.g. "gemma-4-31b-it")
  system       -> instructions
  messages[0].content (single user turn) -> input
  max_tokens   -> max_output_tokens
  tools        -> tools=[]           (explicitly none)

Auth: ADAPTION_API_KEY env var, else secrets/adaption.key (gitignored). Never printed.
Endpoint: POST https://api.prod.adaptionlabs.ai/api/v1/responses  (per API reference)
Returns an object shaped like the Anthropic response the runner already reads:
  .content[0].text, .usage.input_tokens/.output_tokens, .stop_reason, .model, .raw
Credits (not USD) are the unit of cost; recorded as usage tokens for the manifest.
"""
import json, os, urllib.request

BASE = os.environ.get("ADAPTION_BASE_URL", "https://api.prod.adaptionlabs.ai")


def _key():
    k = os.environ.get("ADAPTION_API_KEY")
    if not k and os.path.exists(os.path.join("secrets", "adaption.key")):
        k = open(os.path.join("secrets", "adaption.key"), encoding="utf-8-sig").read().strip()
    if not k:
        raise RuntimeError("NO ADAPTION KEY: set ADAPTION_API_KEY or save secrets/adaption.key")
    return k


class _Block:
    def __init__(self, text): self.type, self.text = "text", text


class _Usage:
    def __init__(self, u):
        self.input_tokens = int((u or {}).get("input_tokens") or 0)
        self.output_tokens = int((u or {}).get("output_tokens") or 0)


class AdaptionResponse:
    def __init__(self, raw):
        self.raw = raw
        self.content = [_Block(raw.get("output_text") or "")]
        self.usage = _Usage(raw.get("usage"))
        st = raw.get("status")
        self.stop_reason = {"completed": "end_turn", "incomplete": "max_tokens"}.get(st, st)
        self.model = raw.get("model")
        self.id = raw.get("id")


def send(**request):
    msgs = request.get("messages") or []
    if len(msgs) != 1 or msgs[0].get("role") != "user":
        raise ValueError("adaption_send expects exactly one user message (fixed-input dispatch)")
    body = {
        "model": request["model"],
        "instructions": request.get("system") or "",
        "input": msgs[0]["content"],
        "max_output_tokens": int(request.get("max_tokens") or 1024),
        "tools": [],            # explicitly no tools, no memory
        "store": False,
    }
    req = urllib.request.Request(
        f"{BASE}/api/v1/responses", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_key()}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = json.loads(r.read().decode("utf-8"))
    if raw.get("error"):
        raise RuntimeError(f"adaption error: {raw['error']}")
    return AdaptionResponse(raw)


def list_models():
    """GET the hosted models this key can access (availability varies by key). Read-only, no credits."""
    req = urllib.request.Request(f"{BASE}/api/v1/models?type=hosted", headers={"Authorization": f"Bearer {_key()}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.loads(r.read().decode("utf-8"))
    data = raw.get("data", raw if isinstance(raw, list) else [])
    return sorted(m.get("id") or m.get("name") for m in data)


if __name__ == "__main__":
    import sys
    if "--list" in sys.argv:
        print("hosted models for this key:", list_models()); sys.exit(0)
    # smoke test: one tiny call, prints only token counts and the reply, never the key
    r = send(model=os.environ.get("ADAPTION_MODEL", "gemma-4-31b-it"), system="Reply with the single word: ok",
             max_tokens=16, messages=[{"role": "user", "content": "ping"}])
    print("AUTH OK:", r.content[0].text.strip()[:40], "| in/out tokens:", r.usage.input_tokens, r.usage.output_tokens, "| stop:", r.stop_reason)
