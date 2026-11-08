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
  temperature  -> temperature        (frozen sampling config, sent on every request)
  tools        -> tools=[]           (explicitly none)

Auth: ADAPTION_API_KEY env var, else secrets/adaption.key (gitignored). Never printed.
Endpoint: POST https://api.prod.adaptionlabs.ai/api/v1/responses  (per API reference)
Returns an object shaped like the Anthropic response the runner already reads:
  .content[0].text, .usage.input_tokens/.output_tokens, .stop_reason, .model, .raw
Credits (not USD) are the unit of cost; recorded as usage tokens for the manifest.
"""
import json, os, urllib.request

HOSTED_BASE_URL = "https://api.prod.adaptionlabs.ai"
TRANSPORT_TIMEOUT_S = 240   # frozen per run (Lorien's b8630c0 extension); long reasoning replies exceeded 120 s
BASE = os.environ.get("ADAPTION_BASE_URL", HOSTED_BASE_URL)


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
    """Absent or malformed counters stay None so the runner's guard fails closed instead of refunding a reserve.
    reasoning_tokens (from output_tokens_details) is recorded for the output-budget protocol; it is part of output_tokens."""
    def __init__(self, u):
        counts = u if isinstance(u, dict) else {}
        self.input_tokens = counts.get("input_tokens")
        self.output_tokens = counts.get("output_tokens")
        details = counts.get("output_tokens_details") if isinstance(counts.get("output_tokens_details"), dict) else {}
        self.reasoning_tokens = details.get("reasoning_tokens")


class AdaptionResponse:
    def __init__(self, raw):
        self.raw = raw
        text = raw.get("output_text")
        if not isinstance(text, str) or not text.strip():   # absent or whitespace-only: assemble from message items so a real answer is never read as empty
            parts = []
            for item in raw.get("output") or []:
                if isinstance(item, dict) and item.get("type") == "message":
                    for c in item.get("content") or []:
                        if isinstance(c, dict) and c.get("type") in ("output_text", "text") and c.get("text"): parts.append(c["text"])
            text = "".join(parts)
        self.content = [_Block(text or "")]
        self.usage = _Usage(raw.get("usage"))
        self.output_item_types = [i.get("type") for i in (raw.get("output") or []) if isinstance(i, dict)]
        st = raw.get("status")
        details = raw.get("incomplete_details") if isinstance(raw.get("incomplete_details"), dict) else {}
        if st == "completed":
            self.stop_reason = "end_turn"
        elif st == "incomplete":
            # only the documented output-budget reason maps to max_tokens; any other incomplete reason is kept verbatim
            self.stop_reason = "max_tokens" if details.get("reason") == "max_output_tokens" else f"incomplete:{details.get('reason') or 'unspecified'}"
        else:
            self.stop_reason = st
        self.incomplete_reason = details.get("reason")
        self.model = raw.get("model")
        self.id = raw.get("id")


def _positive_int(v, name):
    if type(v) is not int or v < 1:
        raise ValueError(f"{name} must be an explicit positive integer (got {v!r}); the runner never sends a default budget")
    return v


def send(**request):
    msgs = request.get("messages") or []
    if len(msgs) != 1 or msgs[0].get("role") != "user":
        raise ValueError("adaption_send expects exactly one user message (fixed-input dispatch)")
    body = {
        "model": request["model"],
        "instructions": request.get("system") or "",
        "input": msgs[0]["content"],
        "max_output_tokens": _positive_int(request.get("max_tokens"), "max_tokens"),   # explicit, positive; never a silent default
        "tools": [],            # explicitly no tools, no memory
        "store": False,
    }
    if request.get("temperature") is not None:
        body["temperature"] = float(request["temperature"])
    req = urllib.request.Request(
        f"{BASE}/api/v1/responses", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_key()}"})
    with urllib.request.urlopen(req, timeout=_positive_int(request.get("transport_timeout_s") or TRANSPORT_TIMEOUT_S, "transport_timeout_s")) as r:
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
