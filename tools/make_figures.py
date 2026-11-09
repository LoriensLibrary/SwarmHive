"""Figures for the report, generated from the committed analysis outputs (no numbers typed by hand).
  fig1_completion.png : completed-correctly rate per arm, V6 and V11, and clean-draft approval on V1, five models
  fig2_structural.png : blast radius, identity under copying, audit visibility before/after
  python -I tools/make_figures.py
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

T = json.load(open("report/heldout_results/tables.json"))
C = {k: v for k, v in T["cohorts"].items() if k.startswith("heldout_")}
order = ["heldout_gemma431bit", "heldout_deepseekv4fl", "heldout_qwen35397b", "heldout_qwen3827b", "heldout_gemma426ba4b"]
labels = {"heldout_gemma431bit": "gemma-4-31b", "heldout_deepseekv4fl": "deepseek-v4-flash", "heldout_qwen35397b": "qwen3.5-397b",
          "heldout_qwen3827b": "qwen3.8-27b", "heldout_gemma426ba4b": "gemma-4-26b-a4b"}
arms = [("current", "no lineage"), ("current_lookup", "lookup offered"), ("compact", "lineage preloaded"), ("full", "preloaded + bodies"), ("rule", "deterministic rule")]
colors = ["#b3b3b3", "#8fb8de", "#1f4e79", "#5aa9a3", "#2e7d32"]

plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.25), sharey=True)
for ax, fam, title in zip(axes, ["V6", "V11", "V1"], ["V6: same number, authority changed", "V11: same, no correction notice", "V1: clean draft, unrelated correction"]):
    x = range(len(order)); w = 0.16
    for j, (arm, lab) in enumerate(arms):
        ys = []
        for k in order:
            ar = C[k]["arm_rates"].get(f"{fam}/{arm}")
            ys.append(ar["rate"] if ar else 0)
        ax.bar([i + (j - 2) * w for i in x], ys, w, color=colors[j], label=lab, linewidth=0)
    if fam != "V1":
        for i, k in enumerate(order):
            ar = C[k]["arm_rates"].get(f"{fam}/current_lookup")
            if ar: ax.text(i, 1.045, f"{ar['lookup_used']}/{ar['lookup_offered']}", ha="center", va="bottom", fontsize=5.6, color="#333")
    ax.set_xticks(list(x)); ax.set_xticklabels([labels[k] for k in order], rotation=28, ha="right", fontsize=6.5)
    ax.set_ylim(0, 1.18); ax.set_title(title, fontsize=7.5, pad=10)
    ax.axhline(1.0, color="#999", linewidth=0.4, linestyle=":")
axes[0].set_ylabel("rate (of 60 registered)", fontsize=6.5)
h, l = axes[0].get_legend_handles_labels(); fig.legend(h, l, loc="lower center", ncol=5, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, -0.02))
fig.text(0.5, -0.09, "Completed correctly on V6 and V11; clean draft approved on V1. Above each V6/V11 group: lookups taken of offered in the lookup arm.", ha="center", fontsize=6.2, color="#333")
fig.tight_layout(rect=(0, 0.06, 1, 1))
os.makedirs("report/figures", exist_ok=True)
fig.savefig("report/figures/fig1_completion.png", dpi=220, bbox_inches="tight"); plt.close(fig)

br = json.load(open("runs/blast_radius_latest.json")); idc = json.load(open("runs/identity_copies_latest.json")); ad = json.load(open("runs/audit_denials_latest.json"))
fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.4))
ax = axes[0]
names = ["gate\n(closure walk)", "direct-\ndependency\ncheck", "no\nlineage"]; vals = [br["gate_blocked"], br["direct_check_catches"], br["no_lineage_catches"]]
b = ax.bar(names, vals, color=["#1f4e79", "#7a9cc6", "#b3b3b3"], linewidth=0)
for r, v in zip(b, vals): ax.text(r.get_x() + r.get_width() / 2, v + 1, str(v), ha="center", fontsize=7)
ax.set_ylim(0, 68); ax.set_ylabel("stale descendants blocked (of 60)", fontsize=6.5); ax.set_title("Blast radius of one adjudicated source", fontsize=7.5); ax.tick_params(labelsize=6.5)
ax = axes[1]
names = ["naive board", "bound intake"]; vals = [idc["naive_identities"], idc["bound_identities"]]
b = ax.bar(names, vals, color=["#b3b3b3", "#1f4e79"], linewidth=0)
for r, v in zip(b, vals): ax.text(r.get_x() + r.get_width() / 2, v + 0.2, str(v), ha="center", fontsize=7)
ax.set_ylim(0, 11.5); ax.set_ylabel("identities recorded for 10 copies, 1 login", fontsize=6.5); ax.set_title("Identity under copying", fontsize=7.5); ax.tick_params(labelsize=6.5)
ax = axes[2]
names = ["before migration", "after migration"]; vals = [3, ad["attacks_visible_in_audit"]]
b = ax.bar(names, vals, color=["#b3b3b3", "#1f4e79"], linewidth=0)
for r, v in zip(b, vals): ax.text(r.get_x() + r.get_width() / 2, v + 0.15, f"{v} of 6", ha="center", fontsize=7)
ax.set_ylim(0, 7); ax.set_ylabel("attacks visible in the operator audit", fontsize=6.5); ax.set_title("Denied attempts made visible", fontsize=7.5); ax.tick_params(labelsize=6.5)
fig.tight_layout(); fig.savefig("report/figures/fig2_structural.png", dpi=220, bbox_inches="tight"); plt.close(fig)
print("figures written")
