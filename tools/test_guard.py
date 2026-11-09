"""Offline guard tests against a fake client. No network, no key, no DB."""
import sys, os, tempfile, importlib.util, json
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, r"<home>/Documents/Codex/2026-11-06/che/outputs/swarm_reference")
spec = importlib.util.spec_from_file_location("spr", "tools/pilot_runner.py"); pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)
pr.time.sleep = lambda s: None
req = dict(model="gemma-4-31b-it", system="x", max_tokens=pr.MAX_TOKENS, messages=[{"role": "user", "content": "y" * 1000}])

class Resp:
    def __init__(self, it=300, ot=80, usage=True):
        self.model = req["model"]
        self.content = [type("T", (), {"text": "{}"})()]; self.stop_reason = "end_turn"
        self.usage = type("U", (), {"input_tokens": it, "output_tokens": ot})() if usage else None

def model(ceiling, max_attempts=None, retries=0):
    d = tempfile.mkdtemp(); led = os.path.join(d, "ledger.jsonl")
    m = pr.Model("gemma-4-31b-it", dry_run=False, rawdir=d, provider="adaption", ceiling=ceiling, ledger=led, max_attempts=max_attempts, retries=retries)
    return m, led

res = (256000 * 0.09 + 1200 * 0.34) / 1e6
print(f"per-attempt reserve at posted gemma rates + 256k context: {res:.6f} credits")
ok = True

# 1. Lorien's reproduction: charged-but-lost 500, then retry. Ceiling fits ONE reserve, not two -> no second send.
m, led = model(ceiling=res * 1.5, retries=3); sent = []
def charged_lost(**r):
    sent.append(1); e = Exception("500"); e.code = 500; raise e
m.client = type("C", (), {"send": staticmethod(charged_lost)})()
try: m.send(**req); print("FAIL 1: returned"); ok = False
except pr.BudgetStop as e: print("1 OK: BudgetStop before 2nd send ->", str(e)[:70])
except Exception as e: print("FAIL 1: other", e); ok = False
print("   provider sends:", len(sent), "| spend (reserve kept):", round(m.spend, 6), "| attempts:", m.attempts)
assert len(sent) == 1 and m.attempts == 1 and abs(m.spend - res) < 1e-9

# 2. Missing usage -> fail closed, reserve kept.
m, led = model(ceiling=1.0); m.client = type("C", (), {"send": staticmethod(lambda **r: Resp(usage=False))})()
try: m.send(**req); print("FAIL 2"); ok = False
except RuntimeError as e: print("2 OK: missing usage failed closed; spend", round(m.spend, 6))
assert abs(m.spend - res) < 1e-9

# 3. Usage above reserved max (output > max_tokens) -> fail closed, reserve kept.
m, led = model(ceiling=1.0); m.client = type("C", (), {"send": staticmethod(lambda **r: Resp(ot=5000))})()
try: m.send(**req); print("FAIL 3"); ok = False
except RuntimeError as e: print("3 OK: usage over reserve failed closed; spend", round(m.spend, 6))
try:
    m.send(**req)
    print("FAIL 3: sent after provider broke reserve bounds"); ok = False
except pr.BudgetStop:
    assert m.attempts == 1 and abs(m.spend - res) < 1e-9
    print("3 OK: provider integrity stop remains latched")

m, led = model(ceiling=1.0)
other = Resp()
other.model = "unexpected-billing-model"
m.client = type("C", (), {"send": staticmethod(lambda **r: other)})()
try:
    m.send(**req)
    print("FAIL model: reconciled an unknown billing model"); ok = False
except RuntimeError:
    assert m.attempts == 1 and abs(m.spend - res) < 1e-9
    print("OK unregistered billing model keeps reserve")
try:
    m.send(**req)
    print("FAIL model: sent after unregistered billing model"); ok = False
except pr.BudgetStop:
    assert m.attempts == 1

# 4. Attempt cap enforced: max_attempts=2, third call stops before send.
m, led = model(ceiling=1.0, max_attempts=2); sent = []
m.client = type("C", (), {"send": staticmethod(lambda **r: (sent.append(1), Resp())[1])})()
m.send(**req); m.send(**req)
try: m.send(**req); print("FAIL 4"); ok = False
except pr.BudgetStop as e: print("4 OK: attempt cap ->", str(e)[:60], "| sends", len(sent))
assert len(sent) == 2

# 5. Reconciliation: debit then settle to verified usage at posted rate.
m, led = model(ceiling=1.0); m.client = type("C", (), {"send": staticmethod(lambda **r: Resp(357, 80))})()
m.send(**req); exp = (357 * 0.09 + 80 * 0.34) / 1e6
print("5 OK: spend after one real-shaped call", round(m.spend, 8), "expected", round(exp, 8)); assert abs(m.spend - exp) < 1e-12
print("   ledger events:", [json.loads(l)["event"] for l in open(led)])

# 6. Default retries=0: a retryable 429 raises at once (one send), reserve kept.
m, led = model(ceiling=1.0); sent = []
def r429(**r):
    sent.append(1); e = Exception("429"); e.code = 429; raise e
m.client = type("C", (), {"send": staticmethod(r429)})()
try: m.send(**req); print("FAIL 6"); ok = False
except Exception as e: print("6 OK: no automatic retry by default; sends", len(sent), "| spend", round(m.spend, 6))
assert len(sent) == 1

# 7. Unknown model / wrong provider / non-positive ceiling refused at construction.
for kw in (dict(model="mystery-7b", provider="adaption", ceiling=1.0), dict(model="gemma-4-31b-it", provider="anthropic", ceiling=1.0), dict(model="gemma-4-31b-it", provider="adaption", ceiling=0)):
    try: pr.Model(kw["model"], False, tempfile.mkdtemp(), provider=kw["provider"], ceiling=kw["ceiling"]); print("FAIL 7", kw); ok = False
    except SystemExit as e: print("7 OK refused:", str(e)[:70])

# 8. Exact request budget for the expanded primary design.
n = 60 * pr.requests_for(pr.TASKS["V6"], pr.ARMS_ALL) + 60 * pr.requests_for(pr.TASKS["V1"], pr.ARMS_ALL)
print("8 max_authorized_requests for 60xV6 + 60xV1, four arms:", n, "| worst-case reserve if every request hit max:", round(n * res, 4), "| expected at pilot means:", round(n / 9 * 9 * (357 * 0.09 + 80 * 0.34) / 1e6, 6))
print("ALL OK" if ok else "SOME FAILED")
