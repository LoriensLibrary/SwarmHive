"""Trust-boundary and permission diagram for the report: who may invoke each operator-owned function, what it reads, and
what it alone may write. Drawn from code so it regenerates with the rest.  python -I tools/make_diagram.py"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

plt.rcParams.update({"font.family": "serif", "font.size": 7})
fig, ax = plt.subplots(figsize=(7.4, 3.3)); ax.set_xlim(0, 100); ax.set_ylim(0, 56); ax.axis("off")
NAVY = "#1f4e79"; GREY = "#777"


def box(x, y, w, h, text, fc, fs=5.3, ec="#333", ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.8", fc=fc, ec=ec, lw=0.8, linestyle=ls))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.2)


def arrow(p, q, color=NAVY, ls="-", lw=0.9):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=8, color=color, lw=lw, linestyle=ls, shrinkA=0, shrinkB=0))


for x, t in ((7.5, "agent roles"), (25.5, "intake"), (51, "operator-owned functions"), (84, "authoritative tables")):
    ax.text(x, 54, t, ha="center", fontsize=6.4, color="#444", fontweight="bold")

for name, y in (("bot_researcher", 44), ("bot_writer", 37), ("bot_reviewer", 30), ("bot_intruder", 23)):
    box(0.5, y, 14, 4.5, name, "#eef3f8", fs=5.8)

box(18.5, 33, 14, 10, "exp.proposals\n(one direct write)\n\ntrigger binds the\nproposer to the login", "#fff4e0", fs=5.2)
for y in (46.2, 39.2, 32.2, 25.2):
    arrow((14.5, y), (18.5, 38))

box(37, 44, 28, 7, "seal_from_proposal, seal_artifact\ncallable by: the trusted runtime only", "#e8f0fa")
box(37, 35, 28, 7, "invalidate\ncallable by: author (own) or adjudicator", "#e8f0fa")
box(37, 25, 28, 8, "publish_decision (adjudicator only)\nfence; re-read lineage; validate; commit", "#e8f0fa")
box(37, 15, 28, 8, "lookup (lookup arm only)\ncallable by the reviewer; one recorded request", "#e8f0fa")

box(70, 46, 29, 4.5, "exp.artifacts: sealed versions", "#f3f3f3", fs=5.5)
box(70, 40, 29, 4.5, "exp.provenance: delivered inputs", "#f3f3f3", fs=5.5)
box(70, 34, 29, 4.5, "exp.invalidations: epochs", "#f3f3f3", fs=5.5)
box(70, 28, 29, 4.5, "exp.approvals: decisions", "#f3f3f3", fs=5.5)
box(70, 15, 29, 7, "hive_audit, operator-only\npost-evaluation extension:\ndenied attempts recorded", "#fafafa", fs=5.2, ec="#999", ls="--")

arrow((32.5, 40), (37, 46.5))
ax.text(27.5, 47.5, "sealed from the receipt", ha="center", fontsize=5.0, color=NAVY)
arrow((65, 48.5), (70, 48.5)); arrow((65, 46.5), (70, 42.5))
arrow((65, 38.5), (70, 36.5))
arrow((65, 29), (70, 30))
arrow((70, 41.5), (65, 31.5), color=GREY, ls=":", lw=0.9)
ax.text(84.5, 25.0, "publish_decision re-reads artifacts,\nprovenance and invalidations in the fence", ha="center", fontsize=5.0, color="#555", linespacing=1.1)
arrow((37, 18), (14.5, 31.5), color=GREY, ls=":", lw=0.9)
ax.text(23.5, 21.0, "authenticated\nlookup response", ha="center", fontsize=5.0, color="#555", linespacing=1.1)

ax.add_line(Line2D([2, 8], [7, 7], color=NAVY, lw=1.0)); ax.text(9, 7, "submission or authorized write", va="center", fontsize=5.6, color="#333")
ax.add_line(Line2D([40, 46], [7, 7], color=GREY, lw=1.0, linestyle=":")); ax.text(47, 7, "authoritative read or returned data", va="center", fontsize=5.6, color="#333")
ax.text(50, 1.8, "Agent roles cannot directly modify authoritative tables; authorized changes occur only through operator-owned functions.", ha="center", fontsize=5.6, color="#333")
fig.savefig("report/figures/fig0_gate.png", dpi=220, bbox_inches="tight"); print("diagram written")
