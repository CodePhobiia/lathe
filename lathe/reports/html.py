"""HTML report renderer (BL-36, Plan 08 Phase 6).

Self-contained HTML5 with inline CSS. Uses stdlib ``string.Template``
and ``html.escape`` only; no external dependencies. Renders the same
fields as the terminal report.
"""

from __future__ import annotations

from html import escape
from string import Template
from typing import Any

_PAGE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Lathe build report · $asset</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         margin: 0; padding: 2rem; background: #0f1115; color: #e6e6e6; }
  h1, h2 { margin: 0 0 0.5rem; }
  section { background: #161a22; border-radius: 10px; padding: 1.25rem 1.5rem;
            margin-bottom: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.35); }
  .summary .banner { display: inline-block; padding: 0.35rem 0.85rem;
            border-radius: 999px; font-weight: 700; letter-spacing: 0.05em; }
  .summary.pass .banner { background: #1f6b3a; color: #dcffe1; }
  .summary.fail .banner { background: #7a1f1f; color: #ffe1e1; }
  .meta { color: #a6adbb; margin-top: 0.5rem; font-size: 0.95rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.95rem; }
  th, td { text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid #2a2f3a; }
  th { color: #a6adbb; font-weight: 600; }
  tr:last-child td { border-bottom: none; }
  .sev-error { color: #ff8080; font-weight: 700; }
  .sev-warning { color: #ffcc66; font-weight: 700; }
  .sev-info { color: #80c0ff; font-weight: 700; }
  code { font-family: "Fira Code", "SFMono-Regular", Menlo, monospace; font-size: 0.9rem; }
  .empty { color: #6b7280; font-style: italic; }
</style>
</head>
<body>
  <section class="summary $banner_class">
    <h1><span class="banner">$banner</span> &nbsp;$asset <small>($kind)</small></h1>
    <div class="meta">score: <code>$score</code> &nbsp; threshold: <code>$threshold</code></div>
    <div class="meta">out_dir: <code>$out_dir</code></div>
  </section>
  <section class="validators">
    <h2>Validators</h2>
    $validators_table
  </section>
  <section class="diagnostics">
    <h2>Diagnostics</h2>
    $diagnostics_table
  </section>
  <section class="suggestions">
    <h2>Repair suggestions</h2>
    $suggestions_table
  </section>
  <section class="artifacts">
    <h2>Artifacts</h2>
    $artifacts_table
  </section>
</body>
</html>
"""
)


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value))


def _fmt_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.3f}" if isinstance(value, float) else str(value)
    return _esc(value)


def _validators_table(build_report: dict[str, Any]) -> str:
    detail = build_report.get("validate_detail") or {}
    if not isinstance(detail, dict) or not detail:
        return '<p class="empty">No validator detail recorded.</p>'
    rows: list[str] = []
    for name, payload in detail.items():
        if not isinstance(payload, dict):
            continue
        metrics = payload.get("metrics") or {}
        thresholds = payload.get("thresholds") or {}
        diags = payload.get("diagnostics") or []
        ok = not any((d.get("severity") == "error") for d in diags)
        status_html = '<span class="sev-info">PASS</span>' if ok else '<span class="sev-error">FAIL</span>'
        rows.append(
            "<tr>"
            f"<td>{_esc(name)}</td>"
            f"<td>{status_html}</td>"
            f"<td>{len(metrics)}</td>"
            f"<td>{len(thresholds)}</td>"
            f"<td>{len(diags)}</td>"
            "</tr>"
        )
    if not rows:
        return '<p class="empty">No validators ran.</p>'
    return (
        "<table><thead><tr><th>Validator</th><th>Status</th>"
        "<th>Metrics</th><th>Thresholds</th><th>Diagnostics</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _diagnostics_table(build_report: dict[str, Any]) -> str:
    diagnostics: list[dict[str, Any]] = []
    for d in build_report.get("diagnostics") or []:
        if isinstance(d, dict):
            diagnostics.append(dict(d))
    detail = build_report.get("validate_detail") or {}
    if isinstance(detail, dict):
        for name, payload in detail.items():
            if not isinstance(payload, dict):
                continue
            for d in payload.get("diagnostics") or []:
                if isinstance(d, dict):
                    entry = dict(d)
                    entry.setdefault("source", str(name))
                    diagnostics.append(entry)
    if not diagnostics:
        return '<p class="empty">No diagnostics.</p>'
    rows: list[str] = []
    for d in diagnostics:
        sev = str(d.get("severity") or "info").lower()
        cls = f"sev-{sev}" if sev in {"error", "warning", "info"} else "sev-info"
        rows.append(
            "<tr>"
            f'<td class="{cls}">{_esc(sev.upper())}</td>'
            f"<td>{_esc(d.get('source') or '')}</td>"
            f"<td><code>{_esc(d.get('code') or d.get('reason') or '')}</code></td>"
            f"<td>{_esc(d.get('message') or d.get('detail') or '')}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Severity</th><th>Source</th>"
        "<th>Code</th><th>Message</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _suggestions_table(build_report: dict[str, Any]) -> str:
    suggestions = build_report.get("repair_suggestions") or []
    if not suggestions:
        return '<p class="empty">No repair suggestions recorded.</p>'
    rows: list[str] = []
    for item in suggestions:
        if isinstance(item, dict):
            rows.append(
                "<tr>"
                f"<td><code>{_esc(item.get('target') or item.get('op') or '')}</code></td>"
                f"<td>{_esc(item.get('hint') or item.get('reason') or '')}</td>"
                "</tr>"
            )
        else:
            rows.append(f"<tr><td></td><td>{_esc(item)}</td></tr>")
    return (
        "<table><thead><tr><th>Target</th><th>Hint</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _artifacts_table(build_report: dict[str, Any]) -> str:
    outputs = build_report.get("outputs") or {}
    if not isinstance(outputs, dict) or not outputs:
        return '<p class="empty">No artifacts recorded.</p>'
    rows = [
        f"<tr><td>{_esc(k)}</td><td><code>{_esc(v)}</code></td></tr>"
        for k, v in sorted(outputs.items())
    ]
    return (
        "<table><thead><tr><th>Kind</th><th>Path</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_html_report(build_report: dict[str, Any]) -> str:
    """Render ``build_report`` as a self-contained HTML document."""

    certified = bool(build_report.get("certified"))
    return _PAGE.substitute(
        asset=_esc(build_report.get("asset") or "?"),
        kind=_esc(build_report.get("kind") or "?"),
        out_dir=_esc(build_report.get("out_dir") or ""),
        score=_fmt_number(build_report.get("score")),
        threshold=_fmt_number(build_report.get("threshold")),
        banner="PASS" if certified else "FAIL",
        banner_class="pass" if certified else "fail",
        validators_table=_validators_table(build_report),
        diagnostics_table=_diagnostics_table(build_report),
        suggestions_table=_suggestions_table(build_report),
        artifacts_table=_artifacts_table(build_report),
    )
