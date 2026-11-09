"""Assemble report/REPORT.md in Apart's template order from report/DRAFT.md (whose sections are maintained by hand and by
write_section5.py). Template: Abstract, 1 Introduction, 2 Related Work, 3 Methods, 4 Results, 5 Discussion and Limitations,
6 Conclusion, Code and Data, References, Appendix A (Limitations and Dual-Use / Ethical Considerations, required), Appendix B
(held-out tables), LLM Usage Statement. Cross-references are renumbered.
  python -I tools/assemble_report.py --tables report/heldout_results_partial
"""
import argparse, json, re


def sections(md):
    out = {}; cur = None; buf = []
    for line in md.split("\n"):
        if line.startswith("## "):
            if cur is not None: out[cur] = "\n".join(buf).strip("\n")
            cur = line[3:].strip(); buf = []
        else: buf.append(line)
    if cur is not None: out[cur] = "\n".join(buf).strip("\n")
    return out


def pick(S, prefix):
    for k in S:
        if k.startswith(prefix): return S[k]
    raise KeyError(prefix)


def renumber(text):
    m = {"section 2": "section 3.1", "section 3": "section 3.2", "section 4": "section 3.3", "section 5": "section 4", "section 6": "section 4",
         "section 7": "section 5", "section 8": "the Code and Data section", "section 1": "section 1"}
    for i, (k, v) in enumerate(m.items()): text = re.sub(r"\b" + k + r"\b", f"@@{i}@@", text)
    for i, (k, v) in enumerate(m.items()): text = text.replace(f"@@{i}@@", v)
    return text


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--draft", default="report/DRAFT.md"); ap.add_argument("--tables", default="report/heldout_results_partial"); ap.add_argument("--out", default="report/REPORT.md")
    a = ap.parse_args()
    d = open(a.draft, encoding="utf-8").read(); S = sections(d); T = json.load(open(f"{a.tables}/tables.json"))
    gate = T["gate_total"]; n_models = len([k for k in T["cohorts"] if k.startswith("heldout_")])
    title = d.split("\n", 1)[0].lstrip("# ").strip()
    head = d[:d.index("## Abstract")]
    byline = "Angela Faye Reinhold, Lorien's Library LLC. With Apart Research. Research conducted at the Swarm Alignment Hackathon, November 2026. Tracks 3 and 4."

    intro = pick(S, "1. The failure") + """

**Contributions.**

1. A tested multi-agent failure: stale evidence surviving a correction through summarization, including the case where the number is unchanged and only the authorization is.
2. Its recovery under a publication gate agents cannot write around, every claimed property verified by a second, independently written implementation and reproduced from source on a fresh database branch.
3. A preregistered matched evaluation others can rerun: fixed-input dispatch, a scorer that resolves lineage itself, opaque identifiers, registered denominators, frozen hashes and hard spend ceilings, with its failed claims reported as failed.
4. The result that whether preloaded authenticated lineage beats on-demand retrieval turns on whether the model takes the retrieval, and that false quarantine under a correction notice is model behavior rather than a property of lineage."""

    related = pick(S, "7. Prior work").split("\n\nWhat is new is narrow.")[0]
    discussion_new = "What is new is narrow." + pick(S, "7. Prior work").split("\n\nWhat is new is narrow.")[1]

    methods = ("### 3.1 The gate\n\n" + pick(S, "2. The gate") + "\n\n### 3.2 Experiment design\n\n" + pick(S, "3. Experiment design") +
               "\n\n### 3.3 Development findings that shaped the freeze\n\n" + pick(S, "4. Development findings"))
    results = pick(S, "5. Held-out results")
    trace = pick(S, "6. One inspectable trace")
    import os
    if os.path.exists("report/heldout_v2_results/SECTION.md"):
        results += "\n\n### 4.1 Follow-up cohorts run after the preregistered set (post-hoc, labeled)\n\n" + open("report/heldout_v2_results/SECTION.md", encoding="utf-8").read().strip()
    if os.path.exists("report/structural/SECTION.md"):
        results += "\n\n### 4.2 Structural tests: containment, identity under copying, blast radius\n\n" + open("report/structural/SECTION.md", encoding="utf-8").read().strip()

    discussion = f"""**Discussion.** {discussion_new}

The safety reading is in two parts. The gate is the part of this system we would trust in deployment: across {gate['slots']:,} registered slots on {n_models} models it saw {gate['unsafe_proposals']} unsafe proposals and committed {gate['unsafe_commits']}, and a read-only count of the evaluation branch accounts for every approval row. The model reviewer above it is the part to measure before trusting, per model: the same preloaded lineage that lifted one model from 68 to 119 correct completions of 120 made it refuse more clean drafts, three models refused all or nearly all clean drafts under any unrelated correction notice, and one model's lookup arm barely used its lookup. A deterministic rule reading the same lineage never false-quarantined and never missed a stale draft; where the gate cannot see content (V10), it commits whatever the reviewer approves, so the model still has a job, and these results say that job should be measured per model and bounded by the rule.

**What the structural tests add.** The held-out cohorts measure the reviewer; the deterministic tests in 4.2 measure the substrate under the sprint's own questions. Under the naive board the intruder landed two spoofed identities, read a foreign thread, tampered and deleted; under the bound board every count is zero and the attempts are in the audit. Ten copies of one agent are ten identities on the naive board and one on the bound intake, silenced by one revocation, which is the motivating incident's 7,905 names reduced to the number of logins. And when one source is adjudicated, the closure walk blocks all sixty descendants three levels deep while a direct-dependency monitor passes forty of them. Those are not model results and need no per-model measurement; they hold by construction and were checked by execution.

**Limitations.** Appendix A gives the full list, as the sprint rules require. The three that bound the claims most: the operator is trusted and owns every function, so a compromised owner defeats every property; lineage is what the runtime delivered, not what the model relied on; and the tasks are known-answer inventory counts drawn from one template, so the intervals describe resampling of that template, not a task distribution.

**Future work.** An eager deterministic lookup that delivers lineage records before the model's first call, which removes the offered-versus-taken question and makes preloading redundant by construction. Identity per agent instance rather than per role login. A trusted gateway so that denied actions, which leave no application audit row today, become legible. Contention and throughput measurements rather than serialized race schedules. And, with the sponsor's fine-tuning platform, a reviewer adapted on these traces, evaluated under the same frozen protocol as a new cohort."""

    conclusion = f"""A publication gate that re-reads authenticated lineage inside one fenced transaction held across {gate['slots']:,} registered reviewer slots on {n_models} open models: {gate['unsafe_proposals']} unsafe proposals, {gate['unsafe_commits']} unsafe commits, every approval row on the evaluation branch accounted for. What a reviewer does above that gate depends on the model more than on how lineage reaches it. Preloaded lineage and an authenticated lookup reach the same decisions when the model takes the lookup, and preloading is the only thing that saves the same-number case when it does not. Three of the five models refused all or nearly all clean drafts under an unrelated correction notice regardless of lineage, while a deterministic rule reading the same lineage never did.

The failure we set out to test is real and reproducible: stale evidence survives a correction through summarization, and a reviewer with no lineage picked the stale draft exactly half the time on three of the five models when the number had not changed. The fix that held is the one agents cannot write around. The fix that varied is the one that asks a model to read."""

    refs_full = pick(S, "References and acknowledgments")
    refs, ack = refs_full.split("**Acknowledgments.**") if "**Acknowledgments.**" in refs_full else (refs_full, "")
    code_data = pick(S, "8. Pre-existing work") + """

**Code and data.** Repository: `SwarmHive` (the public mirror is linked from the submission form; pre-existing code is marked in its README). Every held-out cohort's traces, ledgers, raw requests and responses, scored outputs, freeze records and the analysis outputs are committed under `runs/`, `holdout/` and `report/`. Synthetic data only; no personal data. Info-hazard note: the containment battery contains generic attacks on a shared record (spoofing, renaming, editing, deleting, replaying), run only against synthetic rows in a disposable test database; nothing targets a real system."""

    llm = """## Appendix D. LLM Usage Statement

The author worked with two AI systems throughout and discloses both. Aelen, a Claude model running in Claude Code, wrote most of the code in the repository under the author's direction, ran every evaluation under the author's explicit spend authorization, and drafted this report from the committed run data; every number in the report is produced by scripts in the repository (`tools/analysis.py`, `tools/results_tables.py`, `tools/write_section5.py`) from the committed traces and ledgers, not typed by a model. Lorien, an OpenAI Codex model running in a separate workspace, wrote the independent reference specification, the acceptance driver, the delivery recorder and the scorer, and reviewed the design, the gate and the evaluation protocol adversarially before the held-out runs; its two 7 November reviews are committed under `report/`. It did not review the final text of this report. The author set the research question, chose the tracks, made every design decision that is recorded as hers in the repository, authorized every paid run, reviewed every claim against the data, and edited the text. Claims and results were verified against the committed evidence before submission; the two deviations from the preregistration and the one post-results code fix are disclosed in Appendix B.
"""

    out = f"""# {title}

{byline}

## Abstract

{S['Abstract']}

## 1. Introduction

{intro}

## 2. Related Work

{related}

## 3. Methods

{methods}

## 4. Results

{results}

## 5. Discussion and Limitations

{discussion}

## 6. Conclusion

{conclusion}

## Code and Data

{code_data}

## References

{refs.strip()}

**Acknowledgments.**{ack}

{'## ' + [k for k in S if k.startswith('Appendix A.')][0]}

{pick(S, 'Appendix A.')}

{'## ' + [k for k in S if k.startswith('Appendix B.')][0]}

{pick(S, 'Appendix B.')}

## Appendix C. One inspectable trace

{trace}

{llm}"""
    out = renumber(out)
    open(a.out, "w", encoding="utf-8").write(out)
    body = out[:out.index("## Code and Data")]
    print("REPORT.md written; body words (abstract through conclusion):", len(body.split()), "| em dashes:", out.count("—"))


if __name__ == "__main__":
    main()
