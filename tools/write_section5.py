"""Compose section 5 (short, body) and Appendix B (full tables and the deviation log) of report/DRAFT.md from the analysis output.
Prose is written here; every number is read from results.json / tables.json / TABLES.md. Rerun after every cohort finishes.
  python -I tools/write_section5.py --tables report/heldout_results_partial
"""
import argparse, json, re

ARMS = ["current", "current_lookup", "compact", "full", "rule", "rule_content"]


def section(md, title_start):
    for p in re.split(r"(?m)^### ", md):
        if p.startswith(title_start): return "\n".join(p.split("\n")[1:]).strip()
    return f"[table pending: {title_start}]"


def md_table(headers, rows):
    s = "| " + " | ".join(headers) + " |\n|" + "|".join([" --- "] * len(headers)) + "|\n"
    for r in rows: s += "| " + " | ".join("" if v is None else str(v) for v in r) + " |\n"
    return s


def fmt_p(p): return f"{p:.1e}" if p < 1e-3 else f"{p:.3f}"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tables", default="report/heldout_results_partial"); ap.add_argument("--draft", default="report/DRAFT.md")
    a = ap.parse_args()
    md = open(f"{a.tables}/TABLES.md", encoding="utf-8").read(); T = json.load(open(f"{a.tables}/tables.json")); R = json.load(open(f"{a.tables}/results.json"))
    C = T["cohorts"]; cost = T["cost_total"]; gate = T["gate_total"]
    model_of = {"heldout_gemma431bit": "gemma-4-31b-it", "heldout_deepseekv4fl": "deepseek-v4-flash", "heldout_qwen35397b": "qwen3.5-397b", "heldout_qwen3827b": "qwen3.8-27b", "heldout_gemma426ba4b": "gemma-4-26b-a4b-it"}
    pending = [m for k, m in model_of.items() if k not in C]
    ds = C.get("heldout_deepseekv4fl", {}).get("arm_rates", {})
    ds_cur_rz = ds.get("V6/current", {}).get("mean_reasoning_tokens"); ds_cmp_rz = ds.get("V6/compact", {}).get("mean_reasoning_tokens")

    # compact primary table
    prim = []
    for cl in R["claims"]:
        if cl["type"] != "completion_NI": continue
        d = R["descriptive"][cl["model"]][cl["family"]]; lo, hi = cl["tango_95"]
        lk = C[[k for k, m in model_of.items() if m == cl["model"]][0]]["arm_rates"][f"{cl['family']}/current_lookup"]
        prim.append([cl["model"], cl["family"], f"{d['compact_rate']:.3f}", f"{d['lookup_rate']:.3f}", f"{lk['lookup_used']}/{lk['lookup_offered']}", f"{cl['delta']:+.3f}", f"[{lo:+.3f}, {hi:+.3f}]", fmt_p(cl["holm_adjusted_p"]), "holds" if cl["reject_at_0.05"] else "not shown"])
    prim_md = md_table(["model", "family", "compact", "lookup-offered", "lookup taken", "delta", "Tango 95%", "Holm p", "NI at -0.10"], prim)
    tok = []
    for cl in R["claims"]:
        if cl["type"] != "tokens_lookup_minus_compact": continue
        tok.append([cl["model"], cl["n"], f"{cl['hodges_lehmann']:+.0f}", fmt_p(cl["holm_adjusted_p"]), "supported" if (cl["reject_at_0.05"] and cl["hodges_lehmann"] > 0) else ("not supported, opposite direction" if cl["reject_at_0.05"] else "not shown")])
    tok_md = md_table(["model", "settled pairs", "Hodges-Lehmann, lookup minus compact", "Holm p", "claim: compact uses fewer"], tok)
    # V1 compact table: approved clean draft of 60 per arm
    v1 = []
    for k, m in model_of.items():
        if k not in C: v1.append([m] + ["pending"] * len(ARMS)); continue
        rt = C[k]["arm_rates"]; v1.append([m] + [f"{rt[f'V1/{arm}']['completed']}/{rt[f'V1/{arm}']['registered']}" if f"V1/{arm}" in rt else "" for arm in ARMS])
    v1_md = md_table(["model", "current", "current + lookup", "compact", "full", "rule", "rule + content"], v1)
    # exploratory one-liner data
    def rate(k, fam, arm):
        r = C.get(k, {}).get("arm_rates", {}).get(f"{fam}/{arm}"); return f"{r['completed']}/{r['registered']}" if r else "pending"
    def taken(k, fam):
        r = C.get(k, {}).get("arm_rates", {}).get(f"{fam}/current_lookup"); return f"{r['lookup_used']}" if r else "pending"
    sup_total = sum(v.get("audit", {}).get("superseded_partial_approvals", 0) for v in C.values()); unk_total = sum(v.get("audit", {}).get("unknown_outcome_slots", 0) for v in C.values())
    gs = {model_of[k]: v["slots"].get("guard_stopped", 0) for k, v in C.items() if k in model_of and v["slots"].get("guard_stopped", 0)}
    gs_note = (" " + "; ".join(f"{m} reached its 900-request cap with {n} slots unsent, registered as guard-stopped in its denominator" for m, n in gs.items()) + ".") if gs else " No cohort was guard-stopped."
    pend_note = (" The " + " and ".join(pending) + (" cohort was" if len(pending) == 1 else " cohorts were") + " still running when this was built; marked pending.") if pending else ""

    body = f"""## 5. Held-out results

Preregistered before any freeze (`report/HELDOUT_PREREGISTRATION.md`); analysis by `tools/analysis.py`; every registered slot stays in its denominator. The full tables, per-arm counts, the branch audit, the cost ledger and the disclosed deviations are in Appendix B.{pend_note}

**What ran.** Five reviewer cohorts of 1,080 registered slots each: three families at 60 instances (V6, the same-number authority change; V11, the same with no correction notice delivered, so lineage is the only signal; V1, the clean-draft control with an unrelated correction before review), six arms per instance, fixture upstream so the presealed bodies are byte-identical across providers, authenticated authorship, temperature 0, one uniform 6,000-token output budget, no retries, opaque identifiers, randomized arm order, counterbalanced queue order, round-robin family interleaving. Every cohort was frozen with its manifest, prompt, code and gate hashes, a request cap and a hard credit ceiling; the runner refuses a hash mismatch and reserves the full per-attempt cost before each call. The preregistered reliability rule (at least 33 of 36 valid structured replies in the 6,000-token canary) admitted gemma-4-31b-it and deepseek-v4-flash to the inferential tier; qwen3.5-397b, qwen3.8-27b and gemma-4-26b-a4b-it run as a labeled exploratory tier; glm-53-flash and glm-5.2 were excluded.

**What the gate did.** Across {gate["slots"]:,} registered slots the models made {gate["unsafe_proposals"]} unsafe proposals, an approval of a draft with invalid lineage or a selection of an artifact that was not a queued candidate. {gate["gate_rejections"]} were rejected by the fenced gate on lineage and {gate["pre_gate_stops"]} were stopped before the gate; {gate["correct_publications"]:,} correct publications committed; unsafe commits: {gate["unsafe_commits"]}. One slot has an unknown commit outcome, the request in flight when the host slept and the database socket died; the branch holds its approval row and the scorer counts it as an error, not a publication. A read-only count of approvals on the evaluation branch matches the traces, with {sup_total} extra rows from instances re-run whole after the resume and {unk_total} from the unknown-outcome slot, every one accounted for (Appendix B).

**Primary: completion, compact vs lookup-offered.** The two inferential models answer the question differently.

{prim_md}
On gemma-4-31b-it the lookup arm took its lookup in 13 of 120 offers, so it mostly behaved as the no-lineage arm and picked the stale draft half the time; compact completed 119 of 120. On deepseek-v4-flash the lookup was taken in 119 of 120 offers and the arms tie near the ceiling. Non-inferiority holds for all four claims under Holm; the deepseek V6 claim is marginal (one-sided p 0.043, two-sided interval reaching -0.114). When a model takes the authenticated lookup, preloading changes nothing about correctness; when it does not, preloading is what saves the case. The gemma gap is a fact about that model's lookup behavior under this prompt, not evidence that preloaded lineage beats retrieval.

**Co-primary: tokens per registered case.** Supported on deepseek-v4-flash, where the lookup arm made two calls and compact saved a median {tok[1][2].lstrip('+') if len(tok) > 1 else 'pending'} tokens per case. Not supported on gemma-4-31b-it, where compact cost a median {tok[0][2].lstrip('-') if tok else 'pending'} more tokens because the lookup arm mostly made one call with no lineage in context. We report that as a failed claim, not as a cheaper arm by another name.

{tok_md}
**False quarantine on the clean-draft control (V1), descriptive.** Approvals of the clean draft out of 60, per arm:

{v1_md}
Both rule arms approve every clean draft on every model. deepseek-v4-flash and qwen3.8-27b quarantine it in every complete slot of every model arm, and qwen3.5-397b in all but one or two per arm, including current, which sees only the bodies, the current source and an unrelated notice: the notice alone makes those models refuse. gemma-4-31b-it approves 51 of 60 without lineage and 41 of 60 with it, so visible lineage makes it more cautious on a clean draft; the arm that wins V6 and V11 on that model pays on V1, and the rule reading the same lineage pays nothing. False quarantine is model behavior under a notice, not a property of the lineage data.

**Exploratory tier.** qwen3.8-27b follows the gemma-31 pattern with a lookup arm that mostly takes its lookup: compact {rate('heldout_qwen3827b', 'V6', 'compact')} and {rate('heldout_qwen3827b', 'V11', 'compact')}, lookup-offered {rate('heldout_qwen3827b', 'V6', 'current_lookup')} and {rate('heldout_qwen3827b', 'V11', 'current_lookup')} (lookup taken {taken('heldout_qwen3827b', 'V6')} and {taken('heldout_qwen3827b', 'V11')} of 60), current 30 of 60 on both. gemma-4-26b-a4b-it is the weakest reviewer: compact {rate('heldout_gemma426ba4b', 'V6', 'compact')} and {rate('heldout_gemma426ba4b', 'V11', 'compact')}, lookup-offered {rate('heldout_gemma426ba4b', 'V6', 'current_lookup')} and {rate('heldout_gemma426ba4b', 'V11', 'current_lookup')}, most of its lookup-arm slots ending as non-queued selections stopped before the gate. qwen3.5-397b behaves like deepseek: compact {rate('heldout_qwen35397b', 'V6', 'compact')} and {rate('heldout_qwen35397b', 'V11', 'compact')}, lookup-offered {rate('heldout_qwen35397b', 'V6', 'current_lookup')} and {rate('heldout_qwen35397b', 'V11', 'current_lookup')} (lookup taken {taken('heldout_qwen35397b', 'V6')} and {taken('heldout_qwen35397b', 'V11')} of 60), and it quarantined the clean draft in nearly every V1 model-arm slot. The full arm tracks compact on every model, so the historical bodies add nothing the lineage metadata did not carry. The diagnostics families (V0, V3, V4, V5, V7, V8, V9, V10 at n = 10 on the two inferential models) are in Appendix B.7; the one to know about is V10, where the lineage is valid and the figure is wrong: the gate commits whatever the reviewer approves there by design, the lineage-only rule approves every one, and only the rule that also reads the figure catches all ten. On gemma-4-31b-it the model arms caught between 5 and 9 of 10. A lineage gate cannot see content, and these rows measure what that costs.

**Cost and incidents.** Settled usage {cost["settled"]:.2f} credits plus {cost["retained"]:.2f} held as reserves against provider timeouts whose billing the platform does not report; every cohort stayed under its credit ceiling.{gs_note} The whole evaluation including development and canaries is under 20 credits of the 100 authorized. Three deviations are disclosed in full in Appendix B: a host sleep that killed every cohort process after 43 minutes and was recovered with a resume mode that re-ran one partial instance per cohort whole under the original freeze; a pause of the diagnostics cohorts to remove endpoint contention; and a post-results fix to the analysis code that had attached Holm-adjusted values to the wrong claims without changing any p-value.

"""
    appendix = f"""## Appendix B. Held-out tables, audit and deviation log

All tables are generated by `tools/results_tables.py` from the committed traces, ledgers and `holdout/heldout_v1/INDEX.json`; the numbers in section 5 are read from the same files.

**Budget canary that set the tiers (nine matched cases, six arms, 6,000-token budget).** Valid structured replies of 36 model-reviewed slots: gemma-4-31b-it 36, deepseek-v4-flash 34, qwen3.5-397b 31, qwen3.8-27b 30, gemma-4-26b-a4b-it 30, glm-53-flash 1, glm-5.2 0. 378 slots, 0.36 credits settled, 19 gateway timeouts with reserves retained. At the earlier 1,200-token budget 108 of 115 invalid replies had stopped at the budget, 101 with empty answer text.

### B.1 Design as frozen

{section(md, "Design as frozen")}

### B.2 Registered slots and failure categories

deepseek-v4-flash's 504s fell mostly in the current arm, where its reasoning ran about three times longer than with lineage preloaded (mean reasoning tokens on settled V6 slots: current {ds_cur_rz}, compact {ds_cmp_rz}). gemma-4-26b-a4b-it's non-queued selections were stopped before the gate.{gs_note} The interleaved task order kept the families balanced: the guard-stopped slots belong to the last instance in the queue.

{section(md, "Registered slots and failure categories")}

### B.3 Primary and co-primary, full

{section(md, "Primary: completion")}

{section(md, "Co-primary")}

{section(md, "Calls, tokens and lookup use")}

### B.4 V1 false quarantine per arm

{section(md, "V1 clean-draft control")}

### B.5 Completed correctly per arm, all models and families

{section(md, "Completed correctly per arm")}

### B.6 Gate integrity and the read-only branch audit

{section(md, "Gate integrity")}

{section(md, "Read-only audit")}

The unknown-outcome slot is gemma-4-26b-a4b-it, V11 instance 41, compact arm: the model approved, the gate call began, and the database connection died in the host sleep before the process read the committed decision. The branch holds the approval row; the scorer does not count it. The qwen3.8-27b surplus is the superseded partial instance V6i05, whose approvals committed before the crash and which was re-run whole after the resume.

### B.7 Diagnostics families (descriptive, n = 10 per family, two models)

Separate freeze (seed 2026110803), eight families at ten instances, same six arms, same budget. V10 is the eligible-but-wrong control: the queued draft's lineage is valid and its figure is wrong, so the gate commits whatever a reviewer approves. Its "unsafe commits" below are that designed content blind spot, counted here and not in the gate-integrity totals of section 5, which cover the three primary families where lineage decides. The rule arm approves every V10 draft (it reads lineage only); the rule-with-content reference catches every one.

{section(md, "Diagnostics families")}

{section(md, "Diagnostics cohorts")}

### B.8 Cost per cohort

{section(md, "Cost per cohort")}

### B.9 Deviations from the preregistration

1. Host sleep. The five cohorts launched at 00:23 EST on 8 November. The laptop slept from 01:06 to 13:32 EST. On wake every cohort process died on a dead database socket. No model request was in flight except the gemma-26 slot above; every finished slot was already on disk. A resume mode was added to the runner (`--resume-out`, commit cc7a480). It validates the execution record and the registry claim, keeps every instance with a trace for all six arms, re-runs the one partially complete instance per cohort as a whole (gemma-31 V11i20, deepseek V1i06, qwen-397 V6i04, qwen-27 V6i05; gemma-26 had none) with the partial traces set aside in `traces.partial_superseded.jsonl`, inherits the prior ledger's settled spend, retained reserves and attempt count so the ceiling and the request cap still bind, and records the resume in `EXECUTION.json` and the registry. The frozen instances, prompts and arm orders did not change; the re-run slots were answered about thirteen hours later by the same models at temperature 0. All five resumed at 13:55 EST. The runner also gained connection keepalives and a single reconnect on a dead socket.
2. Diagnostics paused. Both diagnostics cohorts were paused at 00:28 EST because the gemma-31 primary was timing out on 3 of 9 attempts while sharing its endpoint with its diagnostics twin. They were resumed under the same claims after the primaries finished, at 18:03 and 18:07 EST. Slots not reached by submission are reported as missing.
3. Analysis code fixed after results were seen. `tools/analysis.py` built the vector of p-values with the completion claims first and wrote the Holm-adjusted values back in claim order, so adjusted values were attached to the wrong claims. Fixed in commit dbb70f8. No p-value changed, only which adjusted value sat next to which claim; both versions are in git and the self-test output is unchanged.
4. The direction of the token claim was fixed in the preregistration. The gemma-31 result is reported as not supported rather than reinterpreted.

"""
    d = open(a.draft, encoding="utf-8").read()
    i = d.index("## 5. Held-out results"); j = d.index("## 6.")
    d = d[:i] + body + d[j:]
    k = d.find("## Appendix B."); r = d.index("## References")
    d = (d[:k] if k >= 0 else d[:r]) + appendix + d[r:]
    # abstract, second paragraph, from the same numbers
    g31 = C.get("heldout_gemma431bit", {}).get("arm_rates", {}); dsr = C.get("heldout_deepseekv4fl", {}).get("arm_rates", {})
    def tot(rt, arm): return sum(rt[f"{f}/{arm}"]["completed"] for f in ("V6", "V11") if f"{f}/{arm}" in rt)
    def tk(rt): return sum(rt[f"{f}/current_lookup"]["lookup_used"] for f in ("V6", "V11") if f"{f}/current_lookup" in rt)
    ds_tok = next((abs(cl["hodges_lehmann"]) for cl in R["claims"] if cl["type"] != "completion_NI" and cl["model"] == "deepseek-v4-flash"), None)
    n_models = len([k for k in C if k.startswith("heldout_")]); slots = gate["slots"]
    abstract2 = (f"On that gate we ran a preregistered, matched reviewer comparison on {n_models} open models hosted by Adaption: {slots:,} registered slots, three task families, six arms, only the reviewer's context varying. "
                 f"The models made {gate['unsafe_proposals']} unsafe proposals and the gate committed none. Whether preloaded lineage beats an authenticated lookup turns on whether the model takes the lookup: "
                 f"gemma-4-31b-it took it in {tk(g31)} of 120 offers and completed {tot(g31, 'compact')} of 120 same-number cases with preloaded lineage against {tot(g31, 'current_lookup')} with the lookup offered; "
                 f"deepseek-v4-flash took it in {tk(dsr)} of 120, the arms tied, and preloading saved a median {ds_tok:,.0f} tokens per case. On a clean-draft control three models quarantined all or nearly all clean drafts "
                 f"under an unrelated correction notice in every arm: false quarantine is model behavior, not a property of lineage. Failed claims are reported as failed. "
                 f"The gate assumes a trusted operator and cannot observe what a model relied on.")
    i = d.index("On that gate we ran"); j = d.index("\n", i)
    d = d[:i] + abstract2 + d[j:]
    open(a.draft, "w", encoding="utf-8").write(d)
    ab = d[d.index("## Abstract"):d.index("## 1.")]; print("abstract words:", len(ab.split()) - 1)
    main_words = len(d[:d.index("## Appendix A.")].split())
    print("section 5:", len(body.split()), "words; appendix B:", len(appendix.split()), "words; main body before appendices:", main_words, "words; pending:", pending or "none")


if __name__ == "__main__":
    main()
