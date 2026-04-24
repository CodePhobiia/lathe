"""Terminal report renderer (BL-36, Plan 08 Phase 6).

Renders a ``build_report.json`` dict as a readable block for stdout.
Uses ``rich`` if available for colored tables; otherwise falls back
to hand-rolled ANSI (or no color, if stdout is not a TTY or
``use_color=False``).
"""

from __future__ import annotations

import sys
from typing import Any

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[32m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "dim": "\033[2m",
}


def _supports_color(use_color: bool | None) -> bool:
    if use_color is not None:
        return use_color
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def _paint(text: str, *styles: str, enabled: bool) -> str:
    if not enabled:
        return text
    prefix = "".join(_ANSI.get(s, "") for s in styles)
    return f"{prefix}{text}{_ANSI['reset']}"


def _collect_validator_rows(build_report: dict[str, Any]) -> list[tuple[str, str, str]]:
    stages = build_report.get("validate_detail") or {}
    rows: list[tuple[str, str, str]] = []
    for name, payload in stages.items():
        if not isinstance(payload, dict):
            continue
        metrics = payload.get("metrics") or {}
        thresholds = payload.get("thresholds") or {}
        diags = payload.get("diagnostics") or []
        ok = not any((d.get("severity") == "error") for d in diags)
        status = "pass" if ok else "fail"
        summary = f"{len(metrics)} metrics / {len(thresholds)} thresholds / {len(diags)} diagnostics"
        rows.append((str(name), status, summary))
    return rows


def _collect_diagnostics(build_report: dict[str, Any]) -> list[dict[str, Any]]:
    diags: list[dict[str, Any]] = []
    for source in (build_report.get("diagnostics") or []):
        diags.append(dict(source))
    validate = build_report.get("validate_detail") or {}
    for name, payload in validate.items():
        if not isinstance(payload, dict):
            continue
        for diag in payload.get("diagnostics") or []:
            entry = dict(diag)
            entry.setdefault("source", str(name))
            diags.append(entry)
    return diags


def _render_plain(build_report: dict[str, Any], *, use_color: bool) -> str:
    certified = bool(build_report.get("certified"))
    asset = build_report.get("asset") or "?"
    kind = build_report.get("kind") or "?"
    score = build_report.get("score")
    threshold = build_report.get("threshold")

    banner_text = "PASS" if certified else "FAIL"
    banner_style = ("bold", "green") if certified else ("bold", "red")
    lines: list[str] = []
    score_str = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)
    threshold_str = f"{threshold:.3f}" if isinstance(threshold, (int, float)) else str(threshold)
    header = (
        f"[ {_paint(banner_text, *banner_style, enabled=use_color)} ] "
        f"{_paint(str(asset), 'bold', enabled=use_color)} "
        f"({kind})  score={score_str} threshold={threshold_str}"
    )
    lines.append(header)
    lines.append("")

    rows = _collect_validator_rows(build_report)
    if rows:
        lines.append(_paint("Validators", "bold", "cyan", enabled=use_color))
        width = max((len(r[0]) for r in rows), default=10)
        for name, status, summary in rows:
            color = "green" if status == "pass" else "red"
            lines.append(
                f"  {name.ljust(width)}  "
                f"{_paint(status.upper(), color, enabled=use_color)}  {summary}"
            )
        lines.append("")

    diagnostics = _collect_diagnostics(build_report)
    if diagnostics:
        lines.append(_paint("Diagnostics", "bold", "cyan", enabled=use_color))
        buckets: dict[str, list[dict[str, Any]]] = {}
        for d in diagnostics:
            buckets.setdefault(str(d.get("severity") or "info"), []).append(d)
        for sev in ("error", "warning", "info"):
            items = buckets.get(sev) or []
            if not items:
                continue
            color = {"error": "red", "warning": "yellow", "info": "cyan"}[sev]
            lines.append(f"  {_paint(sev.upper(), color, 'bold', enabled=use_color)} ({len(items)})")
            for d in items:
                code = d.get("code") or d.get("reason") or ""
                msg = d.get("message") or d.get("detail") or ""
                source = d.get("source")
                prefix = f"[{source}] " if source else ""
                lines.append(f"    - {prefix}{code}: {msg}" if code else f"    - {prefix}{msg}")
        lines.append("")

    suggestions = build_report.get("repair_suggestions") or []
    if suggestions:
        lines.append(_paint("Repair suggestions", "bold", "cyan", enabled=use_color))
        for item in suggestions:
            if isinstance(item, dict):
                target = item.get("target") or item.get("op") or ""
                hint = item.get("hint") or item.get("reason") or ""
                lines.append(f"  - {target}: {hint}")
            else:
                lines.append(f"  - {item}")
        lines.append("")

    outputs = build_report.get("outputs") or {}
    if outputs:
        lines.append(_paint("Artifacts", "bold", "cyan", enabled=use_color))
        for key, value in sorted(outputs.items()):
            lines.append(f"  {key}: {value}")
        lines.append("")

    out_dir = build_report.get("out_dir")
    if out_dir:
        lines.append(_paint(f"Build directory: {out_dir}", "dim", enabled=use_color))
    return "\n".join(lines).rstrip() + "\n"


def _render_rich(build_report: dict[str, Any]) -> str | None:
    try:
        from io import StringIO

        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:
        return None

    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor", width=100)

    certified = bool(build_report.get("certified"))
    banner = "PASS" if certified else "FAIL"
    banner_style = "bold green" if certified else "bold red"
    asset = build_report.get("asset") or "?"
    kind = build_report.get("kind") or "?"
    score = build_report.get("score")
    threshold = build_report.get("threshold")
    score_str = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)
    threshold_str = f"{threshold:.3f}" if isinstance(threshold, (int, float)) else str(threshold)
    console.print(
        Panel.fit(
            f"[{banner_style}]{banner}[/]  [bold]{asset}[/] ({kind})  "
            f"score={score_str}  threshold={threshold_str}",
            border_style="green" if certified else "red",
        )
    )

    rows = _collect_validator_rows(build_report)
    if rows:
        table = Table(title="Validators", show_header=True, header_style="bold cyan")
        table.add_column("Validator")
        table.add_column("Status")
        table.add_column("Summary")
        for name, status, summary in rows:
            style = "green" if status == "pass" else "red"
            table.add_row(name, f"[{style}]{status.upper()}[/]", summary)
        console.print(table)

    diagnostics = _collect_diagnostics(build_report)
    if diagnostics:
        table = Table(title="Diagnostics", show_header=True, header_style="bold cyan")
        table.add_column("Severity")
        table.add_column("Source")
        table.add_column("Code")
        table.add_column("Message")
        for d in diagnostics:
            sev = str(d.get("severity") or "info")
            sev_style = {"error": "red", "warning": "yellow", "info": "cyan"}.get(sev, "white")
            table.add_row(
                f"[{sev_style}]{sev.upper()}[/]",
                str(d.get("source") or ""),
                str(d.get("code") or d.get("reason") or ""),
                str(d.get("message") or d.get("detail") or ""),
            )
        console.print(table)

    suggestions = build_report.get("repair_suggestions") or []
    if suggestions:
        table = Table(title="Repair suggestions", show_header=True, header_style="bold cyan")
        table.add_column("Target")
        table.add_column("Hint")
        for item in suggestions:
            if isinstance(item, dict):
                table.add_row(
                    str(item.get("target") or item.get("op") or ""),
                    str(item.get("hint") or item.get("reason") or ""),
                )
            else:
                table.add_row("", str(item))
        console.print(table)

    outputs = build_report.get("outputs") or {}
    if outputs:
        table = Table(title="Artifacts", show_header=True, header_style="bold cyan")
        table.add_column("Kind")
        table.add_column("Path")
        for key, value in sorted(outputs.items()):
            table.add_row(str(key), str(value))
        console.print(table)

    out_dir = build_report.get("out_dir")
    if out_dir:
        console.print(f"[dim]Build directory: {out_dir}[/]")

    return buf.getvalue()


def render_terminal_report(build_report: dict[str, Any], *, use_color: bool | None = None) -> str:
    """Render a ``build_report`` dict for terminal display.

    Falls back to plain ANSI (or no color) when ``rich`` is unavailable
    or ``use_color=False``. When ``use_color`` is ``None``, detects the
    TTY status of stdout.
    """

    color_enabled = _supports_color(use_color)
    if color_enabled:
        rich_output = _render_rich(build_report)
        if rich_output is not None:
            return rich_output
    return _render_plain(build_report, use_color=color_enabled)
