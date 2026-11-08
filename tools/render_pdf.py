"""Render report/REPORT.md to report/REPORT.html and report/REPORT.pdf with Microsoft Edge headless (no extra installs).
  python -I tools/render_pdf.py
Prints the page count and the page on which 'Code and Data' starts (body pages = everything before it)."""
import markdown, subprocess, os, re, sys

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CSS = """
@page { size: Letter; margin: 0.8in 0.85in; }
body { font-family: 'Times New Roman', Georgia, serif; font-size: 10.5pt; line-height: 1.32; color: #111; }
h1 { font-size: 17pt; margin: 0 0 6pt 0; line-height: 1.2; }
h2 { font-size: 12.5pt; margin: 14pt 0 5pt 0; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 10pt 0 4pt 0; page-break-after: avoid; }
p { margin: 0 0 6pt 0; text-align: justify; }
li { margin-bottom: 2pt; }
table { border-collapse: collapse; width: 100%; font-size: 8.2pt; margin: 6pt 0 8pt 0; page-break-inside: avoid; }
th, td { border: 0.5pt solid #777; padding: 2pt 3.5pt; vertical-align: top; text-align: left; }
th { background: #eee; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 8.8pt; }
.byline { color: #333; font-size: 10pt; margin-bottom: 10pt; }
.appendix-break { page-break-before: always; }
"""


def main():
    src = open("report/REPORT.md", encoding="utf-8").read()
    # the gate diagram lives in the live doc as a widget; the PDF carries its caption as a sentence
    src = re.sub(r"\n&#91;embedded content:[^\n]*\n", "\n", src)
    src = src.replace("\n## Code and Data\n", "\n<div class=\"appendix-break\"></div>\n\n## Code and Data\n")
    html = markdown.markdown(src, extensions=["tables", "fenced_code", "sane_lists"])
    html = html.replace("<p>Angela Faye Reinhold", "<p class=\"byline\">Angela Faye Reinhold", 1)
    doc = f"<!doctype html><html><head><meta charset='utf-8'><title>Sealed Provenance for Agent Swarms</title><style>{CSS}</style></head><body>{html}</body></html>"
    open("report/REPORT.html", "w", encoding="utf-8").write(doc)
    out = os.path.abspath("report/REPORT.pdf"); inp = "file:///" + os.path.abspath("report/REPORT.html").replace("\\", "/")
    ud = os.path.join(os.environ.get("TEMP", "."), "edge_pdf_profile")   # Edge headless prints nothing without its own profile dir
    r = subprocess.run([EDGE, "--headless", "--disable-gpu", "--no-first-run", f"--user-data-dir={ud}", "--no-pdf-header-footer", f"--print-to-pdf={out}", inp], capture_output=True, text=True, timeout=120)
    if not os.path.exists(out): sys.exit("edge produced no pdf: " + (r.stderr or r.stdout)[-500:])
    from pypdf import PdfReader
    rd = PdfReader(out); n = len(rd.pages); body_end = None
    for i, pg in enumerate(rd.pages):
        t = pg.extract_text() or ""
        if "Code and Data" in t and body_end is None and i > 0: body_end = i  # 0-based page where appendices start
    print(f"pages {n}; body (before Code and Data) ends on page {body_end} (1-based: {body_end}); appendix pages {n - body_end if body_end else '?'}")


if __name__ == "__main__":
    main()
