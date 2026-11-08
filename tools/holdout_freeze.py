"""Generate and FREEZE the held-out evaluation set (Lorien's contract, section
"Frozen pilot variants"): matched task instances per variant, fixed ids and
nonces, randomized arm order within each paired block, a manifest, and a
sha256 over the manifest + prompts + model config. Post the hash BEFORE any
execution; any change afterwards is a new evaluation version.

  python -I tools/holdout_freeze.py --variants V0,V1,V3,V4,V5,V6 --n 10 --seed 20261107 --out holdout
Then run:
  python -I tools/pilot_runner.py --spec-file holdout/instances.json --manifest holdout/manifest.json --split evaluation
"""
import argparse, hashlib, json, os, random, subprocess, sys
sys.path.insert(0, "tools")
from pilot_runner import TASKS, ARMS, REVIEWER_SYS, WRITER_SYS, RESEARCHER_SYS, LOOKUP_RULE, MAX_TOKENS, LOOKUP_MODE, MODEL_SPEC, requests_for, code_hashes

ITEMS = ["bolts", "gaskets", "valves", "filters", "spools", "brackets", "seals", "fuses", "hinges", "clamps", "rivets", "bearings"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="V0,V1,V3,V4,V5,V6"); ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20261107); ap.add_argument("--out", default="holdout")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--arms", default=",".join(ARMS), help="comma list; include current_lookup for the fourth arm")
    ap.add_argument("--provider", default="anthropic"); ap.add_argument("--ceiling", type=float, default=None)
    ap.add_argument("--split", default="evaluation"); ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("--upstream", choices=("model", "fixture"), default="model")
    a = ap.parse_args()
    arms = a.arms.split(",")
    rng = random.Random(a.seed)
    instances, manifest = [], []
    for v in a.variants.split(","):
        base = TASKS[v]
        for i in range(a.n):
            spec = dict(base)
            right = rng.randint(5, 40)
            if base.get("two_sources"):                         # V9: wrong = a+b, right = a+b2
                a_ = rng.randint(3, 20); b_ = rng.randint(3, 20); b2 = max(1, b_ + rng.choice([-3, -2, -1, 1, 2, 3]))
                spec.update(a=a_, b=b_, b2=b2); right = a_ + b2; wrong = a_ + b_
            elif base["wrong"] is None:
                wrong = None
                if base.get("bad_draft"): spec["bad_delta"] = rng.choice([2, 3, 4, 5])
            elif v == "V6":
                wrong = right                                   # same number, authority changes
            else:
                wrong = right + rng.choice([-7, -4, 3, 6, 9]); wrong = max(1, wrong)
            has_stale = bool(base.get("hops") == 2 or base.get("replay") or base.get("stale_queued") or base.get("two_sources"))   # a stale candidate is actually queued
            # counterbalanced queue order within each stratum, fixed per instance, identical across arms in the block
            spec["queue_order"] = ("stale_first" if i % 2 == 0 else "fresh_first") if has_stale else "single"
            spec.update(wrong=wrong, right=right, item=rng.choice(ITEMS), site=f"site-{rng.randint(1, 9)}")
            nonce = "h%s" % rng.getrandbits(24).to_bytes(3, "big").hex()
            tid = f"{v}i{i:02d}"
            arm_order = rng.sample(arms, len(arms))            # randomized within the paired block
            instances.append({"tid": tid, "variant": v, "nonce": nonce, "spec": spec, "arm_order": arm_order})
            task_id = f"{tid}_{nonce}"
            for arm in arm_order:
                manifest.append({"run_id": f"{tid}_{nonce}_{arm}_{a.split}", "task_id": task_id, "condition": arm, "split": a.split})
    os.makedirs(a.out, exist_ok=True)
    mbytes = json.dumps(manifest, indent=1, sort_keys=True).encode()
    with open(f"{a.out}/manifest.json", "wb") as f: f.write(mbytes)
    ibytes = json.dumps(instances, indent=1).encode()
    with open(f"{a.out}/instances.json", "wb") as f: f.write(ibytes)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = "unknown"
    prompts_sha = hashlib.sha256((REVIEWER_SYS + "\n" + WRITER_SYS + "\n" + RESEARCHER_SYS + "\n" + LOOKUP_RULE).encode()).hexdigest()
    # Everything the runner re-checks BEFORE its first paid call must be here, under these exact keys.
    freeze = {"runner_commit": commit, "seed": a.seed, "variants": a.variants.split(","), "n_per_variant": a.n,
              "arms": arms, "instances": len(instances), "runs": len(manifest), "split": a.split,
              "model": a.model, "provider": a.provider, "max_tokens": MAX_TOKENS, "lookup_mode": LOOKUP_MODE, "ceiling": a.ceiling,
              "manifest_sha256": hashlib.sha256(mbytes).hexdigest(), "instances_sha256": hashlib.sha256(ibytes).hexdigest(),
              "prompts_sha256": prompts_sha, **code_hashes(),
              "max_authorized_requests": sum(requests_for(i["spec"], i["arm_order"], a.upstream) for i in instances), "retries": a.retries, "upstream_mode": a.upstream,
              "rates": list(MODEL_SPEC[a.model]["price"]) if a.model in MODEL_SPEC else None,
              "context_tokens": MODEL_SPEC[a.model]["context"] if a.model in MODEL_SPEC else None,
              "attack_budget": "one fixed opportunity per instance (replay/stale queue), identical across arms"}
    import uuid
    freeze["freeze_id"] = hashlib.sha256((json.dumps(freeze, sort_keys=True) + uuid.uuid4().hex).encode()).hexdigest()
    freeze["frozen_at"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
    with open(f"{a.out}/FREEZE.json", "w") as f: json.dump(freeze, f, indent=1)
    print(json.dumps(freeze, indent=1))


if __name__ == "__main__":
    main()
