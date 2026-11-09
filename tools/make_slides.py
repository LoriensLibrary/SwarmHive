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

# 2 the concrete case
s = prs.slides.add_slide(blank); title(s, "One concrete case: same number, withdrawn authorization")
bullets(s, ["A researcher reports 12 units. A writer drafts \"12 units\" from that report. The report's authorization is then withdrawn and a re-authorized recount also says 12; a fresh draft from it says \"12 units\" too.",
            "Two drafts sit in the review queue with the identical number. One descends from a withdrawn authorization; one does not. Nothing in the text tells them apart.",
            "A reviewer with no lineage picked the stale draft half the time on three of five models. Factual agreement is not publication eligibility.",
            "Question: can a trusted publication boundary stop the stale one from committing even when a model reviewer approves it? And how does the way the reviewer receives lineage change what it does?"],
        0.6, 1.5, 12.1, 5.2, size=18)

# 3 invariant and trust boundary
s = prs.slides.add_slide(blank); title(s, "The invariant and the trust boundary")
s.shapes.add_picture("report/figures/fig0_gate.png", Inches(1.3), Inches(1.25), width=Inches(10.7))
note(s, "In plain terms: an approval cannot commit if the selected draft depends on a withdrawn source, even when its number is correct. Invariant: at the publication transaction's serialization point an approval commits only if the selected artifact exists, is sealed, and neither it nor any recorded ancestor carries a blocking invalidation. Authorship is bound to authenticated principals; authoritative lineage changes are reserved for trusted functions. Assumes the trusted runtime and operator are uncompromised. Exercised by a separately authored suite of 19 boundary checks.", top=6.45, size=11)

# 4 safety accounting and evidence delivery
s = prs.slides.add_slide(blank); title(s, "Held-out evaluation (preregistered)")
s.shapes.add_picture("report/figures/fig1_completion.png", Inches(0.4), Inches(1.3), width=Inches(8.2))
bullets(s, ["Five models; 5,400 registered slots: 3,600 model-reviewed and 1,800 deterministic controls.",
            f"Reviewers produced {gate['unsafe_proposals']} unsafe proposals. Pre-gate validation stopped {gate['pre_gate_stops']}; the publication gate rejected {gate['gate_rejections']}. Zero lineage-invalid commits; {gate['correct_publications']:,} correct publications.",
            f"Evidence delivery affected completion: gemma-4-31b used optional lookup in {tk(g31)}/120 same-number cases, and preloading completed {tot(g31, 'compact')}/120 versus {tot(g31, 'current_lookup')}/120 with lookup offered; deepseek used lookup in {tk(dsr)}/120 and both protocols performed near the ceiling.",
            "Three models approved none or almost none of the clean drafts across context conditions, including review without lineage. The cause was not isolated.",
            "Scope: the gate enforces recorded-lineage eligibility, not content correctness."],
        8.8, 1.3, 4.2, 5.6, size=12)

# 5 preloading vs optional vs required retrieval
s = prs.slides.add_slide(blank); title(s, "Preloading vs optional vs required retrieval (post-hoc follow-ups)")
bullets(s, ["Required lookup: 120/120 correct completions on new gemma-4-31b instances versus 119/120 with preloading, supporting the retrieval-uptake explanation, at an estimated 724 additional tokens per settled pair (Hodges-Lehmann).",
            "Fresh DeepSeek cohort: preloading 60/60 versus 51/60 with optional lookup. Three misses followed decisions without retrieval; six were provider errors. In this cohort, optional retrieval failures included both skipped acquisition and provider errors.",
            "A second synthetic surface template (service-desk tickets) showed the same broad completion ordering, with zero lineage-invalid commits.",
            "Reading: in these tasks, preloading and required retrieval largely removed the acquisition failure, at different token costs."],
        0.6, 1.5, 12.1, 5.0, size=18)

# 6 content blind spot and limits
s = prs.slides.add_slide(blank); title(s, "Content blind spot and deployment limits")
bullets(s, ["Lineage is not truth: with valid lineage and a wrong figure (V10), the gate commits what the reviewer approves. The content rule caught every tested wrong figure; model reviewers caught some but not all.",
            "The operator is trusted and owns every function. Lineage is what the runtime delivered, not what the model relied on.",
            "A controlled reviewer-protocol evaluation over synthetic matched artifacts, not an adaptive swarm: two templates, four agents, one operator, no throughput measurements.",
            f"Supporting structural tests: copies sharing one login are attributed to one principal and revoked together; one adjudicated source blocks {br['gate_blocked']}/60 descendants where a direct-dependency check catches {br['direct_check_catches']}. The audit extension recorded all six tested attacks in committed statements; attacker-controlled rollback remains a blind spot."],
        0.6, 1.4, 12.1, 5.0, size=16)
note(s, "Reproducibility: every number regenerates from committed traces (github.com/LoriensLibrary/SwarmHive). All paid runs: 8.75 credits metered, worst case 22.23 with timeout reserves, of 100 authorized. Deviations and post-hoc additions: report Appendix B.9.", color=NAVY, size=10)
prs.save("report/SLIDES.pptx"); print("slides written")
