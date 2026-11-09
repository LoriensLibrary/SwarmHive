"""Trust-boundary and permission diagram for the report: who may invoke each operator-owned function, what it reads, and
what it alone may write. Drawn from code so it regenerates with the rest.  python -I tools/make_diagram.py"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

plt.rcParams.update({"font.family": "serif", "font.size": 7})
fig, ax = plt.subplots(figsize=(7.2, 3.7)); ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis("off")
NAVY = "#1f4e79"; GREY = "#777"


def box(x, y, w, h, text, fc, fs=5.4, ec="#333", ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0", fc=fc, ec=ec, lw=0.8, linestyle=ls))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.25)


def arrow(p, q, color=NAVY, ls="-", lw=0.9):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=8, color=color, lw=lw, linestyle=ls, shrinkA=0, shrinkB=0))


for x, t in ((9.5, "agent roles (one login each)"), (32, "intake"), (57, "operator-owned functions"), (86, "authoritative tables")):
    ax.text(x, 57.8, t, ha="center", fontsize=6.6, color="#444")

for name, y in (("bot_researcher", 47), ("bot_writer", 39), ("bot_reviewer", 31), ("bot_intruder", 23)):
    box(1, y, 16, 5, name, "#eef3f8", fs=6.2)

box(22, 37, 19, 10, "exp.proposals\n\ntrigger binds proposer\nto session_user", "#fff4e0", fs=5.6)
ax.text(31.5, 49.4, "INSERT payload: the agents' one direct write", ha="center", fontsize=5.3, color=NAVY)
for y in (49.5, 41.5, 33.5, 25.5):
    arrow((17, y), (22, 42))

box(45, 47.5, 24, 7.5, "seal_from_proposal, seal_artifact\ncallable by: the trusted runtime only\n(an adjudicator role)", "#e8f0fa")
box(45, 37.5, 24, 7.5, "invalidate\ncallable by: author (withdraw own),\nadjudicator (adjudicate any)", "#e8f0fa")
box(45, 26, 24, 9, "publish_decision\ncallable by: adjudicator only\nacquire fence; re-read lineage;\nvalidate; commit", "#e8f0fa")
box(45, 14, 24, 9.5, "lookup (lookup arm only)\noptional as frozen, required in the follow-up\ncallable by: the reviewer;\none recorded request", "#e8f0fa", fs=5.2)

box(74, 50, 24, 5, "exp.artifacts: versions, sealed", "#f3f3f3", fs=5.8)
box(74, 43.5, 24, 5, "exp.provenance: delivered inputs", "#f3f3f3", fs=5.8)
box(74, 37, 24, 5, "exp.invalidations: epochs", "#f3f3f3", fs=5.8)
box(74, 30.5, 24, 5, "exp.approvals: committed decisions", "#f3f3f3", fs=5.8)
box(74, 12.5, 24, 7, "hive_audit: operator-only\npost-evaluation extension:\ndenied attempts are recorded here", "#fafafa", fs=5.2, ec="#999", ls="--")

arrow((41, 42), (45, 51)); ax.text(43.0, 34.6, "seals from\nthe receipt", ha="center", fontsize=5.1, color=NAVY, linespacing=1.1)
arrow((69, 52.5), (74, 52.5)); arrow((69, 50), (74, 46))
arrow((69, 41), (74, 39.5))
arrow((69, 30.5), (74, 33))
arrow((74, 45.2), (69, 28.5), color=GREY, ls=":", lw=0.9)
ax.text(86, 27.0, "re-read inside the fence: artifacts,\nprovenance, invalidations", ha="center", fontsize=5.1, color="#555", linespacing=1.1)
arrow((45, 18.5), (17, 32.5), color=GREY, ls=":", lw=0.9)
ax.text(29, 19.2, "authenticated lookup response", ha="center", fontsize=5.2, color="#555")

ax.add_line(Line2D([3, 9], [8.3, 8.3], color=NAVY, lw=1.0)); ax.text(10, 8.3, "submission or authorized write", va="center", fontsize=5.6, color="#333")
ax.add_line(Line2D([40, 46], [8.3, 8.3], color=GREY, lw=1.0, linestyle=":")); ax.text(47, 8.3, "authoritative read or returned data", va="center", fontsize=5.6, color="#333")
ax.text(50, 3.0, "Agent roles cannot directly modify authoritative tables. Authorized changes occur only through operator-owned functions, each callable by the principals named in its box.",
        ha="center", fontsize=5.7, color="#333")
fig.savefig("report/figures/fig0_gate.png", dpi=220, bbox_inches="tight"); print("diagram written")
