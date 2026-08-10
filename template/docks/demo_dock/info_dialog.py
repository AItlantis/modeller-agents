# COPY THIS FILE — never import it across repos.
# See docs/ADR/ADR-0001-scaffold-not-framework.md for the rationale.
# Not CI-budget-enforced (only template/docks/lib/*.py and the launcher are).
"""info_dialog — modal Info dialog rendering a dock's README via a mini
markdown-to-HTML view.

Satisfies contracts/DOCK_CONTRACT.md §8: a dock MUST ship documentation and
expose an in-dock Info affordance that renders it. Import this module lazily
(inside a dock's setup_ui() or its Info-button handler), never at the
launcher's module scope.
"""
from __future__ import annotations

import html as html_module
import re
from pathlib import Path

from ..lib.qt_compat import QtWidgets

QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QTextBrowser = QtWidgets.QTextBrowser
QDialogButtonBox = QtWidgets.QDialogButtonBox


def render_markdown(text: str) -> str:
    """Convert a small, deliberate subset of Markdown to HTML for QTextBrowser.

    Supports: #/##/### headings, "---" rules, "- " bullets, fenced code
    blocks, and inline **bold** / *italic* / `code`. Anything else passes
    through as an escaped, line-broken paragraph.
    """
    lines = text.split("\n")
    out = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            out.append(
                "<pre style='background:#f5f5f5; padding:6px; border-radius:3px;'>"
                if in_code_block else "</pre>"
            )
            continue

        if in_code_block:
            out.append(html_module.escape(line))
            continue

        if stripped.startswith("### "):
            out.append(f"<h3 style='margin:4px 0;'>{html_module.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            out.append(f"<h2 style='margin:6px 0;'>{html_module.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            out.append(f"<h1 style='margin:8px 0;'>{html_module.escape(stripped[2:])}</h1>")
        elif stripped == "---":
            out.append("<hr/>")
        elif stripped.startswith("- "):
            out.append(f"<li>{_inline(stripped[2:])}</li>")
        elif stripped == "":
            out.append("<br/>")
        else:
            out.append(_inline(line) + "<br/>")

    if in_code_block:
        out.append("</pre>")

    body = "\n".join(out)
    return (
        "<html><body style='font-family: Segoe UI, Arial, sans-serif; "
        "font-size: 11px; margin: 6px; line-height: 1.5;'>" + body + "</body></html>"
    )


def _inline(text: str) -> str:
    escaped = html_module.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


class InfoDialog(QDialog):
    """Modal dialog showing a dock's README.md, rendered as HTML."""

    def __init__(self, doc_path: Path, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} — Info")
        self.resize(560, 480)

        layout = QVBoxLayout(self)
        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(False)
        browser.setReadOnly(True)

        text = _load_doc(doc_path)
        browser.document().setDefaultStyleSheet("")
        browser.setHtml(render_markdown(text))
        layout.addWidget(browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close
                                   if hasattr(QDialogButtonBox, "StandardButton")
                                   else QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


def _load_doc(doc_path: Path) -> str:
    try:
        if doc_path.exists():
            return doc_path.read_text(encoding="utf-8")
    except Exception:
        pass
    return f"_Documentation not found at: `{doc_path}`_"
