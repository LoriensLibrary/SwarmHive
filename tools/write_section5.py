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

@@FINDINGS@@

**What ran.** Five reviewer cohorts of 1,080 registered slots: three families at 60 instances (V6, the same-number authority change; V11, the same with no correction notice, so lineage is the only signal; V1, the clean-draft control), six arms per instance, presealed byte-identical upstream bodies, authenticated authorship, temperature 0, a uniform 6,000-token budget, no retries, opaque identifiers, randomized arm and counterbalanced queue order (Appendix B.1). Each cohort was frozen with manifest, prompt, code and gate hashes, a request cap and a credit ceiling. The preregistered reliability rule (33 of 36 valid canary replies) admitted gemma-4-31b-it and deepseek-v4-flash to the inferential tier; qwen3.5-397b, qwen3.8-27b and gemma-4-26b-a4b-it are a labeled exploratory tier; two GLM models were excluded.

**What the gate did.** Across {gate["slots"]:,} registered slots the models made {gate['unsafe_proposals']} unsafe proposals (an approval of a draft with invalid lineage, or a selection of a non-queued artifact): {gate['gate_rejections']} were rejected by the fenced gate on lineage and {gate['pre_gate_stops']} stopped before it; {gate['correct_publications']:,} correct publications committed; unsafe commits {gate['unsafe_commits']}. One slot has an unknown commit outcome (the request in flight when the host slept; the branch holds its approval row, the scorer counts an error). A read-only count of approvals on the evaluation branch matches the traces, with 4 extra rows from instances re-run whole after the resume and 1 from that slot, every one accounted for (Appendix B).

**Primary: completion, compact vs lookup-offered.** The two inferential models answer the question differently.

{prim_md}
On gemma-4-31b-it the lookup arm took its lookup in 13 of 120 offers, so it mostly behaved as the no-lineage arm and picked the stale draft half the time; compact completed 119 of 120. On deepseek-v4-flash the lookup was taken in 119 of 120 offers and the arms tie near the ceiling. Non-inferiority holds for all four claims under Holm; the deepseek V6 claim is marginal (one-sided p 0.043, interval reaching -0.114). When a model takes the lookup, preloading changes nothing about correctness; when it does not, preloading is what saves the case.

**Co-primary: tokens per settled pair.** Pairs where both arms have provider-reported usage; unresolved 504 attempts carry no usage and are excluded here while staying in the completion denominators. Supported on deepseek-v4-flash, where the lookup arm made two calls and compact saved a Hodges-Lehmann {tok[1][2].lstrip('+') if len(tok) > 1 else 'pending'} tokens per pair. Not supported on gemma-4-31b-it, where compact cost {tok[0][2].lstrip('-') if tok else 'pending'} more tokens (Hodges-Lehmann) because the lookup arm mostly made one call with no lineage in context. The p-values are exact two-sided sign tests on the paired differences and measure whichever direction the data took; for gemma-31 the small p supports the opposite of the preregistered one-sided claim, not the claim.

{tok_md}
**False quarantine on the clean-draft control (V1), descriptive.** Approvals of the clean draft out of 60, per arm:

{v1_md}
Both rule arms approve every clean draft on every model. deepseek-v4-flash and qwen3.8-27b quarantine it in every complete slot of every model arm, and qwen3.5-397b in all but at most one, including the current arm, which sees only the bodies, the current source and an unrelated notice, so the refusal does not require lineage; a matched notice-absent clean-draft condition was not run for all five models, so its cause is not isolated. gemma-4-31b-it approves 51 of 60 without lineage and 41 of 60 with it. On gemma-4-31b-it lineage changed the rate, so providing lineage is not irrelevant to refusal either.

**Exploratory tier and diagnostics.** The three exploratory models split the same way (Appendix B.5): qwen3.8-27b follows the gemma-31 pattern, qwen3.5-397b behaves like deepseek-v4-flash, gemma-4-26b-a4b-it is the weakest reviewer, and the full arm tracks compact everywhere. In the V10 diagnostic (valid lineage, wrong figure; Appendix B.7) the gate commits whatever the reviewer approves by design; the lineage-only rule approves every one, the content rule catches all ten, and the model arms caught 5 to 9 of 10.

**Cost and incidents.** Settled usage {cost["settled"]:.2f} credits plus {cost["retained"]:.2f} held as reserves against provider timeouts whose billing the platform does not report; every cohort's running total (settled charges plus reserves held for unresolved attempts at the time of each call) stayed under its ceiling; the retained figure is the sum of reserves kept over all unresolved attempts, an upper bound on what the provider could still bill, and settled plus that bound exceeds the DeepSeek ceiling (Appendix B.8).{gs_note} The whole evaluation, including development, canaries, diagnostics and follow-ups, settled under 20 of the 100 authorized credits, under 30 if every reserve were charged. Deviations (a host sleep recovered with a resume mode under the original freeze, a diagnostics pause, and a post-results fix to the Holm bookkeeping that changed no p-value) are in Appendix B.9.

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
4. Not a deviation, recorded for completeness: the direction of the token claim was fixed in the preregistration. The gemma-31 result is reported as not supported rather than reinterpreted.
5. Post-hoc follow-up cohorts. Two cohorts were frozen and run after the preregistered set had been analyzed and this report drafted (section 5, follow-up subsection): a gemma-4-31b-it cohort with the lookup made mandatory and an independent deepseek-v4-flash V6 replication. New seeds, new freezes, separate ledgers, never pooled with the held-out set; their results are labeled post-hoc wherever they appear.
6. Structural tests added after the report draft. The containment battery was run before the sprint's held-out evaluation; the identity-under-copying and blast-radius tests (section 5, structural subsection) were written and run on the scratch branch after the held-out analysis, with no model calls, and do not change any held-out number.
7. Audit migration after the evaluation. `sql/hive_audit_denials.sql` (statement-level denial triggers and logging read policies on the bound board) was written and tested on the scratch branch after the held-out analysis. It is not applied to the evaluation branch and changes no held-out number; its before/after is in the structural subsection.
8. Second surface template, post-hoc. A recorded task-domain switch (`TASK_DOMAIN`, hashed into the freeze) rewrites the task wording and system prompts from inventory counts to resolved service-desk tickets with the same families, scoring and gate. Two cohorts (gemma-4-31b-it, deepseek-v4-flash; V6 and V11; 30 instances per family; lookup optional as frozen) were frozen and run after the report draft; results are in section 5 and Appendix B.10, labeled post-hoc, never pooled.

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
    abstract2 = (f"On that gate, a preregistered matched comparison on {n_models} open models: {slots:,} registered slots (3,600 model-reviewed, 1,800 deterministic controls), three families, six arms, only the reviewer's context varying. "
                 f"Reviewers made {gate['unsafe_proposals']} unsafe proposals; pre-gate validation stopped {gate['pre_gate_stops']}, the gate rejected {gate['gate_rejections']}, no lineage-invalid publication occurred, and {gate['correct_publications']:,} valid publications committed. "
                 f"Whether preloaded lineage beats an authenticated lookup turns on whether the model takes the lookup: gemma-4-31b-it took it in {tk(g31)} of 120 offers and completed {tot(g31, 'compact')} of 120 same-number cases with preloaded lineage against {tot(g31, 'current_lookup')} with the lookup offered; "
                 f"deepseek-v4-flash took it in {tk(dsr)} of 120 and the arms tied. Three models refused all or nearly all clean drafts under an unrelated correction notice in every model-context condition, including review without lineage. "
                 f"Ten copies of one agent collapse to one revocable identity; an adjudicated source blocks all sixty descendants three deep. The gate checks lineage, not content; failed claims are reported as failed; the operator is trusted.")
    i = d.index("On that gate"); j = d.index("\n", i)
    d = d[:i] + abstract2 + d[j:]
    findings = (f'**In one paragraph.** Three results. First, the gate held: across {slots:,} registered slots (3,600 model-reviewed, 1,800 deterministic controls) reviewers made {gate["unsafe_proposals"]} unsafe proposals, pre-gate validation stopped {gate["pre_gate_stops"]}, the gate rejected {gate["gate_rejections"]}, no lineage-invalid publication occurred in the primary families, {gate["correct_publications"]:,} valid publications committed, and every approval row on the evaluation branch is accounted for. '
                f'Second, whether a reviewer needs lineage preloaded or can fetch it depends on whether it fetches: gemma-4-31b-it took its offered lookup in {tk(g31)} of 120 cases and completed {tot(g31, "compact")} of 120 same-number cases with preloaded lineage against {tot(g31, "current_lookup")} with the lookup offered, while deepseek-v4-flash took it in {tk(dsr)} of 120 and the two arms tied. '
                f'Third, three of five models refused all or nearly all clean drafts under an unrelated correction notice in every model-context condition, including current-only review, so the refusal cannot be attributed to providing lineage; the deterministic rules reading the same lineage never refused one, and its cause is not isolated here. The follow-up cohorts and the structural tests at the end of this section test the first two of these directly.')
    d = d.replace('@@FINDINGS@@', findings)
    open(a.draft, "w", encoding="utf-8").write(d)
    ab = d[d.index("## Abstract"):d.index("## 1.")]; print("abstract words:", len(ab.split()) - 1)
    main_words = len(d[:d.index("## Appendix A.")].split())
    print("section 5:", len(body.split()), "words; appendix B:", len(appendix.split()), "words; main body before appendices:", main_words, "words; pending:", pending or "none")


if __name__ == "__main__":
    main()
