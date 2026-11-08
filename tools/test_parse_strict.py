"""Strict reply parsing at the privileged boundary (Lorien 2026-11-08 01:12): duplicate keys, mixed prose,
arrays, wrong types and bad selections are invalid output, never a guess. No network, no database."""
import sys, os, importlib.util
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, "tools/vendor")
spec = importlib.util.spec_from_file_location("spr", "tools/pilot_runner.py"); pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)
ok = True
good = '{"decision": "approve", "artifact": {"id": "x", "ver": 1}, "result": {"units": 3}, "evidence": [{"id": "x", "ver": 1}], "consulted": []}'
assert pr.validate_proposal(pr.parse_json(good)) == ("x", 1); print("OK   clean object parses, selection (x,1)")
assert pr.validate_proposal(pr.parse_json("```json\n" + good + "\n```")) == ("x", 1); print("OK   fenced object parses")
bad = {
    "duplicate decision keys (approve wins)": '{"decision": "reject", "artifact": null, "result": null, "evidence": [], "decision": "approve"}',
    "prose before JSON": 'I think the answer is {"decision": "reject", "artifact": null, "result": null, "evidence": []}',
    "two objects": '{"decision": "reject"} {"decision": "approve", "artifact": "x"}',
    "array": '[{"decision": "reject"}]',
    "unknown decision": '{"decision": "publish", "artifact": "x", "result": null, "evidence": []}',
    "approve without artifact": '{"decision": "approve", "artifact": null, "result": {"units": 3}, "evidence": []}',
    "float version": '{"decision": "approve", "artifact": {"id": "x", "ver": 1.0}, "result": {"units": 3}, "evidence": []}',
    "evidence not a list": '{"decision": "approve", "artifact": "x", "result": {"units": 3}, "evidence": {"id": "x", "ver": 1}}',
    "evidence entry malformed": '{"decision": "approve", "artifact": "x", "result": {"units": 3}, "evidence": [{"id": "x", "ver": "1"}]}',
    "result not object": '{"decision": "approve", "artifact": "x", "result": 3, "evidence": []}',
    "NaN units": '{"decision": "approve", "artifact": "x", "result": {"units": NaN}}',
    "boolean units": '{"decision": "approve", "artifact": "x", "result": {"units": true}}',
    "missing result": '{"decision": "approve", "artifact": "x"}',
    "lookup carries a publish result": '{"decision": "lookup", "artifact": "x", "result": {"units": 3}}',
}
for name, text in bad.items():
    try:
        pr.validate_proposal(pr.parse_json(text)); print("FAIL accepted:", name); ok = False
    except pr.InvalidOutput as e:
        print("OK   rejected:", name, "->", str(e)[:50])
    except Exception as e:
        print("FAIL wrong exception:", name, type(e).__name__); ok = False
print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
