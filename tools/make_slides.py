"""Six-slide deck for the optional slides field, built from the committed analysis outputs and the report figures.
  python -I tools/make_slides.py   -> report/SLIDES.pptx
"""
import json
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

T = json.load(open("report/heldout_results/tables.json")); gate = T["gate_total"]
br = json.load(open("runs/blast_radius_latest.json")); idc = json.load(open("runs/identity_copies_latest.json")); ad = json.load(open("runs/audit_denials_latest.json"))
g31 = T["cohorts"]["heldout_gemma431bit"]["arm_rates"]; dsr = T["cohorts"]["heldout_deepseekv4fl"]["arm_rates"]
def tot(rt, arm): return sum(rt[f"{f}/{arm}"]["completed"] for f in ("V6", "V11"))
def tk(rt): return sum(rt[f"{f}/current_lookup"]["lookup_used"] for f in ("V6", "V11"))
v2 = json.load(open("report/heldout_v2_results/results.json")); v2c = {(c["model"], c["family"], c["type"]): c for c in v2["claims"]}

NAVY = RGBColor(0x1F, 0x4E, 0x79); GREY = RGBColor(0x44, 0x44, 0x44); RED = RGBColor(0x8B, 0x00, 0x00)
prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]


def title(slide, text, sub=None):
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.9)); tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = text; p.font.size = Pt(30); p.font.bold = True; p.font.color.rgb = NAVY; p.font.name = "Georgia"
    if sub:
        p2 = tf.add_paragraph(); p2.text = sub; p2.font.size = Pt(15); p2.font.color.rgb = GREY; p2.font.name = "Georgia"


def bullets(slide, items, left, top, width, height, size=16):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height)); tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = it; p.font.size = Pt(size); p.font.name = "Georgia"; p.font.color.rgb = GREY; p.space_after = Pt(8)


def note(slide, text, top=6.85, color=GREY, size=11):
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(top), Inches(12.1), Inches(0.5)); tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = text; p.font.size = Pt(size); p.font.color.rgb = color; p.font.name = "Georgia"


# 1 title
s = prs.slides.add_slide(blank)
tb = s.shapes.add_textbox(Inches(0.8), Inches(2.0), Inches(11.7), Inches(3.5)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; p.text = "Sealed Provenance for Agent Swarms"; p.font.size = Pt(40); p.font.bold = True; p.font.color.rgb = NAVY; p.font.name = "Georgia"
p = tf.add_paragraph(); p.text = "Preloaded lineage vs on-demand retrieval under a trusted publication gate"; p.font.size = Pt(22); p.font.color.rgb = GREY; p.font.name = "Georgia"
p = tf.add_paragraph(); p.text = "Angela Faye Reinhold, Lorien's Library LLC. Swarm Alignment Hackathon, November 2026. Tracks 3 and 4."; p.font.size = Pt(16); p.font.color.rgb = GREY; p.font.name = "Georgia"
p = tf.add_paragraph(); p.text = "github.com/LoriensLibrary/SwarmHive"; p.font.size = Pt(14); p.font.color.rgb = NAVY; p.font.name = "Georgia"

# 2 question
s = prs.slides.add_slide(blank); title(s, "The question", "Can an enforced publication boundary stop agents from committing findings whose provenance has become invalid, even when a model reviewer approves them?")
bullets(s, ["What goes wrong: a figure is reported, summarized, summarized again, then withdrawn and replaced. The summaries still read as current.",
            "The hard case: two drafts with the identical number, one descending from the withdrawn source. A reviewer with no lineage picked the stale one exactly half the time on three of five models.",
            "The sprint's third and fourth questions, treated as one: put identity and the record one layer below the agents, where no agent can write. A lock rather than a camera.",
            "Trust boundary stated up front: one operator seals, adjudicates and publishes. If that operator is compromised, every property below fails."],
        0.6, 1.6, 12.1, 5.0, size=18)

# 3 gate
s = prs.slides.add_slide(blank); title(s, "The gate: permissions at the trust boundary")
s.shapes.add_picture("report/figures/fig0_gate.png", Inches(0.8), Inches(1.35), width=Inches(11.7))
note(s, "Agents hold one login and one direct write (a proposal the trigger binds to that login). Every change to authoritative state goes through an operator-owned function; publication re-reads the full upstream closure inside a fence. Verified by an independently written acceptance suite (19 live checks) and rebuilt from source on a fresh branch.")

# 4 results
s = prs.slides.add_slide(blank); title(s, "Held-out results: five open models, 5,400 registered slots, preregistered")
s.shapes.add_picture("report/figures/fig1_completion.png", Inches(0.5), Inches(1.3), width=Inches(8.3))
bullets(s, [f"{gate['unsafe_proposals']} unsafe proposals, {gate['unsafe_commits']} unsafe commits, {gate['correct_publications']:,} correct publications; every approval row on the evaluation branch accounted for.",
            f"Preloaded lineage vs optional lookup turns on whether the model takes the lookup: gemma-4-31b took it {tk(g31)} of 120 times ({tot(g31, 'compact')} vs {tot(g31, 'current_lookup')} of 120 completed); deepseek took it {tk(dsr)} of 120 and the arms tied.",
            "False quarantine is model behavior: three of five models refused every clean draft under an unrelated notice, in every model arm. The deterministic rule never did.",
            "Failed claims reported as failed: compact did not save tokens on gemma-31."],
        9.0, 1.3, 3.9, 5.4, size=13)

# 5 follow-ups and structural
s = prs.slides.add_slide(blank); title(s, "Follow-ups and structural tests (post-hoc, labeled)")
s.shapes.add_picture("report/figures/fig2_structural.png", Inches(0.5), Inches(4.3), width=Inches(8.0))
gl = v2c.get(("gemma-4-31b-it", "V6", "completion_NI")); dl = v2c.get(("deepseek-v4-flash", "V6", "completion_NI"))
bullets(s, ["Lookup made mandatory: gemma-4-31b took it 120 of 120 and completed 120 of 120, against 119 with preloading. The gap was the optional wording, at a median 724 more tokens per case than preloading.",
            "Independent DeepSeek V6 cohort: preloaded 60 of 60, optional lookup taken 47 of 60, lookup arm 51 of 60. Whether an optional lookup is taken varies with the instance set; preloading does not depend on it.",
            "Second surface template (service-desk tickets instead of inventory): same ordering, zero unsafe commits.",
            f"Structural: ten copies of one agent are {idc['bound_identities']} identity on the bound intake ({idc['naive_identities']} on a naive board), silenced by one revocation; one adjudicated source blocks {br['gate_blocked']} of 60 descendants three deep where a direct-dependency check catches {br['direct_check_catches']}; the audit blind spot closed, {ad['attacks_visible_in_audit']} of 6 attacks now visible with zero effect."],
        0.6, 1.3, 12.1, 3.0, size=14)

# 6 limitations
s = prs.slides.add_slide(blank); title(s, "What this does not establish")
bullets(s, ["The operator is trusted and owns every function. A compromised owner defeats every property, including the audit.",
            "Lineage is what the runtime delivered, not what the model relied on. A false claim with no verifiable contradiction stays undetectable; a wrong figure with valid lineage passes the gate (V10), and only the content rule catches it.",
            "Two synthetic templates, 60 (and 30) instances per cell, no throughput or contention measurements, four agents and one operator, not the thousand-agent regime of the incident.",
            "Statements against objects an agent holds no privilege on leave no audit row; a trusted gateway is future work.",
            "Everything regenerates from committed traces: tools/analysis.py, results_tables.py, write_section5.py, v2_followup.py, v3_domain.py, structural_results.py, arm_outcomes.py, make_figures.py."],
        0.6, 1.5, 12.1, 5.2, size=17)
note(s, "Spend for the whole evaluation: under 20 of 100 authorized credits. Deviations and post-hoc additions are listed in Appendix B.9 of the report.", color=NAVY)
prs.save("report/SLIDES.pptx"); print("slides written")
