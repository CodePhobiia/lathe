"""Human-facing build report renderers (BL-36, Plan 08 Phases 6+7).

Consumes a ``build_report.json`` dict and renders either a terminal
(ANSI / plain) or self-contained HTML artifact. ``write_report`` is
the canonical entry point invoked by ``lathe build --report``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .html import render_html_report
from .terminal import render_terminal_report

__all__ = ["render_terminal_report", "render_html_report", "write_report"]


def write_report(build_report: dict[str, Any], out_dir: Path, format: str) -> Path:
    """Write a rendered report alongside ``build_report.json``.

    - ``format="html"``: writes ``report.html`` and returns its path.
    - ``format="terminal"``: writes ``report.txt`` (plain, no color).
    - ``format="json"``: ensures ``build_report.json`` exists and returns it.
    """

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = format.lower()
    if fmt == "html":
        path = out_dir / "report.html"
        path.write_text(render_html_report(build_report), encoding="utf-8")
        return path
    if fmt == "terminal":
        path = out_dir / "report.txt"
        path.write_text(render_terminal_report(build_report, use_color=False), encoding="utf-8")
        return path
    if fmt == "json":
        path = out_dir / "build_report.json"
        if not path.exists():
            path.write_text(json.dumps(build_report, indent=2), encoding="utf-8")
        return path
    raise ValueError(f"Unknown report format: {format!r}")
