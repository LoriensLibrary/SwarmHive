"""Adapter stop-reason and budget edge cases (Lorien 2026-11-08 04:12). No network."""
import sys, os, importlib.util
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
spec = importlib.util.spec_from_file_location("ads", "tools/adaption_send.py"); ads = importlib.util.module_from_spec(spec); spec.loader.exec_module(ads)
sys.path.insert(0, "tools/vendor")
spec2 = importlib.util.spec_from_file_location("spr", "tools/pilot_runner.py"); pr = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(pr)
ok = True
def check(name, cond, detail=""):
    global ok; ok &= bool(cond); print(("OK  " if cond else "FAIL"), name, detail)
R = ads.AdaptionResponse
check("completed -> end_turn", R({"status": "completed", "output_text": "{}", "usage": {}}).stop_reason == "end_turn")
check("incomplete max_output_tokens -> max_tokens", R({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "usage": {}}).stop_reason == "max_tokens")
r = R({"status": "incomplete", "incomplete_details": {"reason": "content_filter"}, "usage": {}})
check("incomplete other reason kept verbatim", r.stop_reason == "incomplete:content_filter", r.stop_reason)
check("incomplete without details -> incomplete:unspecified", R({"status": "incomplete", "usage": {}}).stop_reason == "incomplete:unspecified")
check("whitespace-only output_text falls back to message items", R({"status": "completed", "output_text": "  \n", "output": [{"type": "message", "content": [{"type": "output_text", "text": "{\"decision\": \"reject\"}"}]}], "usage": {}}).content[0].text == '{"decision": "reject"}')
check("whitespace-only with no items is empty", R({"status": "completed", "output_text": " \t", "usage": {}}).content[0].text == "")
check("reasoning_tokens exposed", R({"status": "completed", "output_text": "{}", "usage": {"output_tokens_details": {"reasoning_tokens": 77}}}).usage.reasoning_tokens == 77)
for bad in (0, -5, None, "6000", 6000.0):
    try:
        ads._positive_int(bad, "max_tokens"); check(f"adapter rejects max_tokens {bad!r}", False)
    except ValueError:
        check(f"adapter rejects max_tokens {bad!r}", True)
check("adapter accepts 6000", ads._positive_int(6000, "max_tokens") == 6000)
for bad in (0, -1, "6000", 1.5):
    try:
        pr.set_max_tokens(bad); check(f"runner rejects --max-tokens {bad!r}", False)
    except SystemExit:
        check(f"runner rejects --max-tokens {bad!r}", True)
pr.set_max_tokens(6000); check("runner accepts 6000", pr.MAX_TOKENS == 6000)
import tempfile
m = pr.Model("gemma-4-31b-it", False, tempfile.mkdtemp(), provider="adaption", ceiling=1.0)
try:
    m.reserve({"model": "gemma-4-31b-it", "max_tokens": 0}); check("reserve refuses zero budget", False)
except pr.BudgetStop:
    check("reserve refuses zero budget", True)
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
