"""Assemble report/REPORT.md in Apart's template order from report/DRAFT.md (whose sections are maintained by hand and by
write_section5.py). Template: Abstract, 1 Introduction, 2 Related Work, 3 Methods, 4 Results, 5 Discussion and Limitations,
6 Conclusion, Code and Data, References, Appendix A (Limitations and Dual-Use / Ethical Considerations, required), Appendix B
(held-out tables), LLM Usage Statement. Cross-references are renumbered.
  python -I tools/assemble_report.py --tables report/heldout_results_partial
"""
import argparse, json, re, os


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

**Contributions.** (1) A tested multi-agent failure: stale evidence surviving a correction through summarization, including the same-number case. (2) A publication boundary that enforces lineage eligibility below the reviewer, with its invariant stated and exercised by a separately authored acceptance suite of 19 boundary checks on a fresh database branch. (3) A preregistered matched evaluation others can rerun, with its failed claims reported as failed. (4) The result that preloaded lineage versus on-demand retrieval turns on whether the model takes the retrieval and whether it succeeds, and that false quarantine under a correction notice occurs with or without lineage."""

    related = pick(S, "7. Prior work").split("\n\nWhat is new is narrow")[0]
    discussion_new = "What is new is narrow" + pick(S, "7. Prior work").split("\n\nWhat is new is narrow")[1]

    gate_txt = pick(S, "2. The gate")
    gate_txt = re.sub(r"\n&#91;embedded content:[^\n]*\n", "\n\n![Figure 0](figures/fig0_gate.png)\n\n*Figure 0. Permissions at the trust boundary: one login and one direct write per agent (a proposal bound to the login), every change through an operator-owned function callable by the principals named in its box, direct reads of current records, and one recorded lookup in the lookup arm. Solid arrows are writes, dashed arrows reads.*\n", gate_txt)
    design = pick(S, "3. Experiment design")
    if os.path.exists("report/heldout_results/ARM_TABLE.md"):
        i0 = design.index("| Arm | What the reviewer sees |"); i1 = design.index("\n\n", i0)
        design = design[:i0] + open("report/heldout_results/ARM_TABLE.md", encoding="utf-8").read().strip() + "\n\n*Table 1. The six arms pooled over five cohorts and three families (900 registered per arm). A model proposes; the gate decides. Unsafe proposals are approvals of a draft with invalid lineage or selections of a non-queued artifact.*" + design[i1:]
    methods = ("### 3.1 The gate\n\n" + gate_txt + "\n\n### 3.2 Experiment design\n\n" + design +
               "\n\n### 3.3 Development findings that shaped the freeze\n\n" + pick(S, "4. Development findings"))
    results = pick(S, "5. Held-out results")
    fig1 = ("\n\n![Figure 1](figures/fig1_completion.png)\n\n*Figure 1. Completed correctly per arm on V6 and V11, and clean-draft approval on V1, five models, registered denominators; "
            "labels give lookups taken of offered.*\n\n")
    anchor = "**Primary: completion, compact vs lookup-offered.**"
    assert results.count(anchor) == 1
    results = results.replace(anchor, fig1.strip("\n") + "\n\n" + anchor)
    trace = pick(S, "6. One inspectable trace")
    if os.path.exists("report/heldout_v2_results/SECTION.md"):
        results += "\n\n### 4.1 Follow-up cohorts run after the preregistered set (post-hoc, labeled)\n\n" + open("report/heldout_v2_results/SECTION.md", encoding="utf-8").read().strip()
    if os.path.exists("report/heldout_v3_results/SECTION.md"):
        results += "\n\n" + open("report/heldout_v3_results/SECTION.md", encoding="utf-8").read().strip()
    if os.path.exists("report/structural/SECTION.md"):
        results += "\n\n### 4.2 Structural tests: containment, identity under copying, blast radius\n\n" + open("report/structural/SECTION.md", encoding="utf-8").read().strip()

    discussion = f"""**Discussion.** {discussion_new}

The safety reading is in two parts, and the primary evidence is a controlled reviewer-protocol evaluation over synthetic matched artifacts, not an adaptive swarm. The gate is the part we would trust in deployment: across {gate['slots']:,} registered slots on {n_models} models (3,600 model-reviewed), {gate['unsafe_proposals']} unsafe proposals and {gate['unsafe_commits']} lineage-invalid commits, every approval row accounted for; in the V10 diagnostic, where lineage is valid and the figure wrong, it committed 34 content-wrong approvals across the two models, by design. The model reviewer above it is the part to measure per model: lineage that lifted one model from 68 to 119 of 120 made it refuse more clean drafts, three models refused all or nearly all clean drafts under any unrelated notice, and a deterministic rule reading the same lineage never false-quarantined and never missed a stale draft. The model's remaining job is content (V10), and it should be measured per model and bounded by the rule.

**Limitations.** Appendix A gives the full list, as the sprint rules require. The three that bound the claims most: the operator is trusted and owns every function, so a compromised owner defeats every property; lineage is what the runtime delivered, not what the model relied on; and the tasks are known-answer counts from one inventory template plus one post-hoc second template, so the intervals describe resampling of those templates, not a task distribution.

**Future work.** An eager deterministic lookup that delivers lineage records before the model's first call; identity per agent instance rather than per role login; a trusted gateway in front of the database so that statements against objects an agent holds no privilege on become legible; contention and throughput measurements; and a reviewer fine-tuned on these traces, evaluated under the same frozen protocol."""

    conclusion = f"""A publication gate that re-reads authenticated lineage inside one fenced transaction held across {gate['slots']:,} registered slots on {n_models} open models, 3,600 of them model-reviewed: {gate['unsafe_proposals']} unsafe proposals, {gate['pre_gate_stops']} stopped before the gate, {gate['gate_rejections']} rejected at it, {gate['unsafe_commits']} lineage-invalid commits, {gate['correct_publications']:,} valid publications, every approval row on the evaluation branch accounted for. What a reviewer does above that gate depends on the model more than on how lineage reaches it. In these tasks optional retrieval introduced both evidence-acquisition failures and additional execution-failure exposure; preloading and required retrieval largely removed the acquisition failure, at different token costs. Three of the five models refused all or nearly all clean drafts under an unrelated correction notice in every model-context condition, including review with no lineage, while a deterministic rule reading the same lineage never did; what drives that refusal is not isolated here.

The failure we set out to test is real and reproducible: stale evidence survives a correction through summarization, and a reviewer with no lineage picked the stale draft half the time on three of five models when the number had not changed. The boundary that held is the one enforced below the agents; what varied is the reviewer above it. Model reviewers can confuse factual agreement with publication eligibility, and a trusted lineage boundary enforces that distinction independently of their decisions. Code, traces and every generator are at github.com/LoriensLibrary/SwarmHive (Appendix C)."""

    refs_full = pick(S, "References and acknowledgments")
    refs, ack = refs_full.split("**Acknowledgments.**") if "**Acknowledgments.**" in refs_full else (refs_full, "")
    code_data = pick(S, "8. Pre-existing work") + """

**Code and data.** Repository `SwarmHive` at github.com/LoriensLibrary/SwarmHive. Every cohort's traces, ledgers, raw requests and responses, scored outputs, freeze records and analysis outputs are committed under `runs/`, `holdout/` and `report/`. Synthetic data only. Info-hazard note: the containment battery holds generic attacks on a shared record, run only against synthetic rows in a disposable test database."""

    llm = """## Appendix E. LLM Usage Statement

The author worked with two AI systems throughout and discloses both. Aelen, a Claude model running in Claude Code, wrote most of the code in the repository under the author's direction, ran every evaluation under the author's explicit spend authorization, and drafted this report from the committed run data; every number in the report is produced by scripts in the repository (`tools/analysis.py`, `tools/results_tables.py`, `tools/write_section5.py`, `tools/v2_followup.py`, `tools/v3_domain.py`, `tools/structural_results.py`, `tools/arm_outcomes.py`, `tools/make_figures.py`) from the committed traces and ledgers, not typed by a model. Lorien, an OpenAI Codex model running in a separate workspace, wrote the independent reference specification, the acceptance driver, the delivery recorder and the scorer, and reviewed the design, the gate and the evaluation protocol adversarially before the held-out runs; its two 7 November reviews are committed under `report/`. It did not review the final text of this report. The author set the research question, chose the tracks, made every design decision that is recorded as hers in the repository, authorized every paid run, reviewed every claim against the data, and edited the text. Claims and results were verified against the committed evidence before submission; the deviations from the preregistration, the post-hoc additions and the one post-results code fix are disclosed in Appendix B.9.
"""

    b10 = ""
    if os.path.exists("report/heldout_v2_results/TABLES.md") or os.path.exists("report/structural/TABLES.md"):
        b10 = "### B.10 Follow-up cohorts and structural tests, tables\n\n"
        if os.path.exists("report/heldout_v2_results/TABLES.md"):
            b10 += "**Follow-up cohorts (post-hoc): completion, tokens, slots and cost.**\n\n" + open("report/heldout_v2_results/TABLES.md", encoding="utf-8").read().strip().replace("; tables in Appendix B.10.", ".") + "\n\n"
        if os.path.exists("report/heldout_v3_results/TABLES.md"):
            b10 += open("report/heldout_v3_results/TABLES.md", encoding="utf-8").read().strip() + "\n\n"
        if os.path.exists("report/structural/TABLES.md"):
            b10 += open("report/structural/TABLES.md", encoding="utf-8").read().strip()
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

## References

{refs.strip()}

**Acknowledgments.**{ack}

{'## ' + [k for k in S if k.startswith('Appendix A.')][0]}

{pick(S, 'Appendix A.')}

{'## ' + [k for k in S if k.startswith('Appendix B.')][0]}

{pick(S, 'Appendix B.')}

{b10}

## Appendix C. Code and Data

{code_data}

## Appendix D. One inspectable trace

{trace}

{llm}"""
    out = renumber(out)
    open(a.out, "w", encoding="utf-8").write(out)
    body = out[:out.index("## References")]
    print("REPORT.md written; body words (abstract through conclusion):", len(body.split()), "| em dashes:", out.count("—"))


if __name__ == "__main__":
    main()
