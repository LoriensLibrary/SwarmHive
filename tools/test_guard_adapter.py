"""Adapter-path regression (Lorien 2026-11-08 00:31): a real-shaped Adaption response with absent, partial,
negative or boolean usage must keep the reserve, and non-finite ceilings must be refused. No network."""
import sys, os, tempfile, importlib.util, math
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, r"C:/Users/Angela/Documents/Codex/2026-11-06/che/outputs/swarm_reference")
spec = importlib.util.spec_from_file_location("spr", "tools/pilot_runner.py"); pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)
aspec = importlib.util.spec_from_file_location("ads", "tools/adaption_send.py"); ads = importlib.util.module_from_spec(aspec); aspec.loader.exec_module(ads)
req = dict(model="gemma-4-31b-it", system="x", max_tokens=pr.MAX_TOKENS, messages=[{"role": "user", "content": "y"}])
res = (256000 * 0.09 + 1200 * 0.34) / 1e6
ok = True

def model(ceiling):
    d = tempfile.mkdtemp()
    return pr.Model("gemma-4-31b-it", False, d, provider="adaption", ceiling=ceiling, ledger=os.path.join(d, "l.jsonl"))

def through_adapter(raw):
    """Build the response exactly as adaption_send would from a raw API body."""
    return ads.AdaptionResponse(raw)

cases = {
    "absent usage": {"output_text": "{}", "status": "completed"},
    "empty usage": {"output_text": "{}", "status": "completed", "usage": {}},
    "partial usage": {"output_text": "{}", "status": "completed", "usage": {"input_tokens": 300}},
    "negative usage": {"output_text": "{}", "status": "completed", "usage": {"input_tokens": -1, "output_tokens": 80}},
    "bool usage": {"output_text": "{}", "status": "completed", "usage": {"input_tokens": True, "output_tokens": 80}},
    "string usage": {"output_text": "{}", "status": "completed", "usage": {"input_tokens": "300", "output_tokens": "80"}},
}
for name, raw in cases.items():
    m = model(1.0); m.client = type("C", (), {"send": staticmethod(lambda raw=raw, **r: through_adapter(raw))})()
    try:
        m.send(**req); print("FAIL", name, "accepted"); ok = False
    except RuntimeError:
        kept = abs(m.spend - res) < 1e-12
        print(("OK  " if kept else "FAIL"), name, "-> failed closed, reserve kept" if kept else f"-> spend {m.spend}"); ok &= kept

# good usage still reconciles through the adapter
m = model(1.0); m.client = type("C", (), {"send": staticmethod(lambda **r: through_adapter({"output_text": "{}", "status": "completed", "usage": {"input_tokens": 357, "output_tokens": 80}}))})()
m.send(**req); exp = (357 * 0.09 + 80 * 0.34) / 1e6
print(("OK  " if abs(m.spend - exp) < 1e-12 else "FAIL"), "valid usage reconciles to", round(m.spend, 8)); ok &= abs(m.spend - exp) < 1e-12

# non-finite / non-positive ceilings refused at construction
for c in (float("inf"), float("nan"), 0, -1):
    try: model(c); print("FAIL ceiling accepted:", c); ok = False
    except SystemExit: print("OK   ceiling refused:", c)
print("ALL OK" if ok else "SOME FAILED")
