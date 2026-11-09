"""Single-file bundles for reviewers without repository access.
  report/REVIEW_BUNDLE.md : report, README, REPRODUCE, gate SQL, analysis, scorer, results tables   (fits a large context window)
  report/FULL_BUNDLE.md   : the above plus the runner, freeze generator, structural tests, audit migration, preregistration
  python -I tools/make_bundle.py
"""
import os, re

REVIEW = ["README.md", "report/REPORT.md", "REPRODUCE.md", "sql/experiment_schema.sql", "sql/seal_from_proposal.sql", "sql/gate_hardening.sql",
          "sql/gate_hardening_2.sql", "sql/gate_exact_receipt.sql", "sql/hive_audit_denials.sql", "tools/analysis.py", "tools/vendor/score_runs.py",
          "report/heldout_results/TABLES.md", "report/heldout_v2_results/TABLES.md", "report/heldout_v3_results/TABLES.md", "report/structural/TABLES.md"]
FULL_EXTRA = ["report/HELDOUT_PREREGISTRATION.md", "tools/pilot_runner.py", "tools/holdout_freeze.py", "tools/vendor/delivery_recorder.py", "tools/det_tests.py",
              "tools/race_test.py", "tools/revocation_test.py", "tools/identity_copies_test.py", "tools/blast_radius_test.py", "tools/audit_denials_test.py",
              "tools/attack_battery.py", "tools/results_tables.py", "tools/v2_followup.py", "tools/v3_domain.py", "tools/structural_results.py", "tools/arm_outcomes.py",
              "report/REVIEW_lorien_2026-11-07.txt", "report/RELEASE_REVIEW_lorien_2026-11-07.txt", "report/REVIEW_aelen_2026-11-07.md"]

HEAD = """# SwarmHive review bundle

Everything below is concatenated verbatim from the public repository github.com/LoriensLibrary/SwarmHive (Swarm Alignment
Hackathon entry, Angela Faye Reinhold, Lorien's Library LLC, November 2026). Each file is introduced by a line of the form
`===== path =====`. Figures referenced in the report are PNGs in report/figures/ and are described in their captions; the
PDF (report/REPORT.pdf) carries them. Nothing here is a secret: connection strings and keys live in an untracked secrets/ folder.

"""


def lang(path):
    return {"md": "markdown", "sql": "sql", "py": "python", "txt": "text", "json": "json"}.get(path.rsplit(".", 1)[-1], "")


def bundle(paths, out, title):
    parts = [HEAD.replace("review bundle", title)]
    parts.append("## File index\n\n" + "\n".join(f"- `{p}` ({os.path.getsize(p):,} bytes)" for p in paths if os.path.exists(p)) + "\n\n")
    for p in paths:
        if not os.path.exists(p): continue
        body = open(p, encoding="utf-8", errors="replace").read()
        body = re.sub(r"\n&#91;embedded content:[^\n]*\n", "\n", body)
        fence = "````" if "```" in body else "```"
        parts.append(f"\n\n===== {p} =====\n\n{fence}{lang(p)}\n{body.rstrip()}\n{fence}\n")
    text = "".join(parts)
    open(out, "w", encoding="utf-8").write(text)
    print(out, f"{len(text):,} chars, ~{len(text) // 4:,} tokens")


bundle(REVIEW, "report/REVIEW_BUNDLE.md", "review bundle")
bundle(REVIEW + FULL_EXTRA, "report/FULL_BUNDLE.md", "full bundle")
