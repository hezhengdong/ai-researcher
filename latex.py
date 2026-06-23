"""Markdown → LaTeX → PDF pipeline using tectonic."""

import re
import subprocess
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

LATEX_TEMPLATE = r"""\documentclass[12pt,a4paper]{{ctexart}}
\usepackage{{geometry}}
\usepackage{{hyperref}}
\usepackage{{enumitem}}
\geometry{{margin=2.5cm}}
\setlength{{\parindent}}{{2em}}
\setlength{{\parskip}}{{0.5em}}

\title{{{title}}}
\author{{AI Researcher}}
\date{{}}

\begin{{document}}
\maketitle

{body}

\end{{document}}
"""


def md2tex(markdown: str) -> str:
    """Convert the Synthesizer's markdown output to LaTeX body."""

    lines = markdown.split("\n")
    out: list[str] = []
    in_refs = False

    for line in lines:
        stripped = line.strip()

        # References section: treat as plain list
        if stripped.startswith("## References") or stripped == "## References":
            in_refs = True
            out.append("\\section*{References}")
            out.append("\\begin{enumerate}[leftmargin=*,label={[\\arabic*]}]")
            continue

        if in_refs:
            if stripped.startswith("[") and "] " in stripped:
                ref_text = _escape_tex(stripped)
                out.append(f"  \\item {ref_text}")
                continue
            elif stripped == "":
                continue
            else:
                # non-reference line after references section - close enumerate
                in_refs = False
                out.append("\\end{enumerate}")

        # Headings
        if stripped.startswith("### "):
            out.append("\\subsubsection*{" + _escape_tex(stripped[4:]) + "}")
        elif stripped.startswith("## "):
            out.append("\\subsection*{" + _escape_tex(stripped[3:]) + "}")
        elif stripped.startswith("# "):
            out.append("\\section*{" + _escape_tex(stripped[2:]) + "}")
        elif stripped == "":
            out.append("")
        else:
            out.append(_convert_inline(stripped))

    if in_refs:
        out.append("\\end{enumerate}")

    return "\n".join(out)


def _escape_tex(text: str) -> str:
    """Escape LaTeX special characters, but preserve [N] citation markers."""
    CITATIONS: list[str] = []

    def _save(m):
        CITATIONS.append(m.group(0))
        return f"CITEMARK{len(CITATIONS)-1:04d}ENDMARK"

    text = re.sub(r"\[\d+\]", _save, text)
    for char, replacement in [
        ("\\", "\\textbackslash{}"),
        ("&", "\\&"),
        ("%", "\\%"),
        ("$", "\\$"),
        ("#", "\\#"),
        ("_", "\\_"),
        ("{", "\\{"),
        ("}", "\\}"),
        ("~", "\\textasciitilde{}"),
        ("^", "\\textasciicircum{}"),
    ]:
        text = text.replace(char, replacement)

    def _restore(m):
        idx = int(m.group(0)[8:12])
        return CITATIONS[idx]

    text = re.sub(r"CITEMARK\d{4}ENDMARK", _restore, text)
    return text


def _convert_inline(text: str) -> str:
    """Convert bold, italic in a paragraph and escape."""
    text = _escape_tex(text)
    # **bold**
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    # *italic*
    text = re.sub(r"\*(.+?)\*", r"\\textit{\1}", text)
    return text


def generate_pdf(survey_id: int, draft: str, topic: str) -> str | None:
    """Generate PDF from survey draft. Returns PDF path or None on failure."""
    tex_path = OUTPUT_DIR / f"survey_{survey_id}.tex"
    pdf_path = OUTPUT_DIR / f"survey_{survey_id}.pdf"

    body = md2tex(draft)
    title = _escape_tex(topic)
    tex_content = LATEX_TEMPLATE.format(title=title, body=body)

    tex_path.write_text(tex_content, encoding="utf-8")

    try:
        subprocess.run(
            ["tectonic", "-X", "compile", "-o", str(OUTPUT_DIR), str(tex_path)],
            capture_output=True, text=True, timeout=60,
            cwd=str(OUTPUT_DIR),
        )
        if pdf_path.exists():
            return str(pdf_path)
        return None
    except Exception:
        return None
