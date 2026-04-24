"""HTML report renderer (BL-36, Plan 08 Phase 6; RPT-1/3, V0.2 E4).

Self-contained HTML5 with inline CSS. Uses stdlib ``string.Template``
and ``html.escape`` only; no external dependencies. Renders the same
fields as the terminal report, plus the RPT-1 sections ("Refs &
Selector Manifest", "Geometry Kernel", "LOD Ladder", "Collision
Proxies") when their artifacts are on disk.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
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
  .kv { color: #a6adbb; }
  .kv b { color: #e6e6e6; font-weight: 600; }
  a.ref-link { color: #80c0ff; text-decoration: none; }
  a.ref-link:hover { text-decoration: underline; }
  .ratio-bar { display: inline-block; width: 8rem; height: 0.5rem; background: #2a2f3a;
               border-radius: 3px; overflow: hidden; vertical-align: middle; margin-right: 0.5rem; }
  .ratio-bar > span { display: block; height: 100%; background: #4a90e2; }
  model-viewer { width: 100%; height: 260px; background: #0f1115; border-radius: 6px;
                 display: block; margin-top: 0.5rem; }
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
$extended_sections
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


def _read_json(path: Path) -> Any | None:
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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


def _refs_manifest_section(build_dir: Path | None) -> str:
    """RPT-1: "Refs & Selector Manifest" section."""
    if build_dir is None:
        return ""
    manifest = _read_json(build_dir / "selector_manifest.json")
    if not isinstance(manifest, dict):
        return ""

    categories: list[tuple[str, str]] = [
        ("Parts", "parts"),
        ("Sockets", "sockets"),
        ("Pivots", "pivots"),
        ("Collisions", "collisions"),
        ("LODs", "lods"),
        ("Materials", "materials"),
    ]

    rows: list[str] = []
    for label, key in categories:
        items = manifest.get(key) or []
        if not isinstance(items, list):
            items = []
        top = items[:3]
        named_parts: list[str] = []
        for item in top:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("id") or ""
            ref = item.get("ref")
            if ref:
                named_parts.append(
                    f'<a class="ref-link" href="#ref" '
                    f'title="{_esc(ref)}"><code>{_esc(name)}</code></a>'
                )
            elif name:
                named_parts.append(f"<code>{_esc(name)}</code>")
        top_html = ", ".join(named_parts) if named_parts else '<span class="empty">(none)</span>'
        rows.append(
            "<tr>"
            f"<td>{_esc(label)}</td>"
            f"<td>{len(items)}</td>"
            f"<td>{top_html}</td>"
            "</tr>"
        )

    build_hash = manifest.get("buildHash") or ""
    header = (
        f'<div class="meta">buildHash: <code>{_esc(build_hash[:16])}'
        f'{"…" if len(str(build_hash)) > 16 else ""}</code></div>'
    )
    table = (
        "<table><thead><tr><th>Category</th><th>Count</th>"
        "<th>Top 3 named entries</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return (
        '  <section class="refs-manifest">\n'
        '    <h2>Refs &amp; Selector Manifest</h2>\n'
        f"    {header}\n    {table}\n"
        "  </section>"
    )


def _geometry_kernel_section(build_dir: Path | None) -> str:
    """RPT-2: "Geometry Kernel" section."""
    if build_dir is None:
        return ""
    bundle = _read_json(build_dir / "stages" / "shape" / "bundle.json")
    if not isinstance(bundle, dict):
        return ""
    stats = bundle.get("bundle_stats")
    if not isinstance(stats, dict):
        return ""

    kernel_id = stats.get("geometry_kernel") or bundle.get("backend_id") or ""
    watertight_rate = stats.get("watertight_rate")
    candidates = stats.get("candidate_count", 0)
    watertight = stats.get("watertight_candidate_count", 0)

    try:
        pct = f"{float(watertight_rate) * 100.0:.1f}%" if watertight_rate is not None else "n/a"
    except (TypeError, ValueError):
        pct = "n/a"

    determinism = bundle.get("determinism_class") or ""
    lines = [
        '  <section class="geometry-kernel">',
        '    <h2>Geometry Kernel</h2>',
        f'    <div class="kv"><b>kernel_id:</b> <code>{_esc(kernel_id)}</code></div>',
        f'    <div class="kv"><b>watertight_rate:</b> <code>{_esc(pct)}</code> '
        f'<span class="empty">({watertight}/{candidates} candidates)</span></div>',
    ]
    if determinism:
        lines.append(
            f'    <div class="kv"><b>determinism:</b> <code>{_esc(determinism)}</code></div>'
        )
    lines.append(
        '    <div class="meta">Deterministic under canonical JSON hashing; see '
        "<code>lathe snapshot</code>.</div>"
    )
    lines.append("  </section>")
    return "\n".join(lines)


def _lod_ladder_section(build_dir: Path | None) -> str:
    """RPT-3: "LOD Ladder" section."""
    if build_dir is None:
        return ""
    manifest = _read_json(build_dir / "stages" / "optimize" / "lod_manifest.json")
    if not isinstance(manifest, dict):
        return ""
    lods = manifest.get("lods") or []
    if not isinstance(lods, list) or not lods:
        return ""

    rows: list[str] = []
    for lod in lods:
        if not isinstance(lod, dict):
            continue
        level = lod.get("level")
        ratio = lod.get("ratio")
        tris = lod.get("tris", lod.get("triangle_count", 0))
        path = lod.get("path") or ""
        try:
            ratio_f = max(0.0, min(1.0, float(ratio)))
        except (TypeError, ValueError):
            ratio_f = 0.0
        bar = (
            f'<span class="ratio-bar"><span style="width:{ratio_f * 100:.1f}%"></span></span>'
            f"<code>{_fmt_number(ratio)}</code>"
        )
        rows.append(
            "<tr>"
            f"<td>{_esc(level)}</td>"
            f"<td>{bar}</td>"
            f"<td>{_esc(tris)}</td>"
            f"<td><code>{_esc(str(path).replace(chr(92), '/'))}</code></td>"
            "</tr>"
        )

    table = (
        "<table><thead><tr><th>Level</th><th>Ratio</th>"
        "<th>Triangles</th><th>Path</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return (
        '  <section class="lod-ladder">\n'
        '    <h2>LOD Ladder</h2>\n'
        f"    {table}\n"
        "  </section>"
    )


def _collision_proxies_section(build_dir: Path | None) -> str:
    """RPT-4: "Collision Proxies" section."""
    if build_dir is None:
        return ""
    manifest = _read_json(build_dir / "stages" / "optimize" / "collision_manifest.json")
    if not isinstance(manifest, dict):
        return ""
    proxies = manifest.get("proxies") or []
    if not isinstance(proxies, list) or not proxies:
        return ""

    rows: list[str] = []
    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        name = proxy.get("name") or ""
        tris = proxy.get("tris", "")
        aabb = proxy.get("aabb")
        aabb_str = _fmt_aabb(aabb)
        rows.append(
            "<tr>"
            f"<td>{_esc(name)}</td>"
            f"<td>{_esc(tris) if tris != '' else '&mdash;'}</td>"
            f"<td><code>{_esc(aabb_str)}</code></td>"
            "</tr>"
        )
        for sub in proxy.get("subproxies") or []:
            if not isinstance(sub, dict):
                continue
            sname = sub.get("name") or ""
            stris = sub.get("tris", "")
            saabb = _fmt_aabb(sub.get("aabb"))
            rows.append(
                "<tr>"
                f'<td style="padding-left:2rem">&rarr; {_esc(sname)}</td>'
                f"<td>{_esc(stris)}</td>"
                f"<td><code>{_esc(saabb)}</code></td>"
                "</tr>"
            )

    table = (
        "<table><thead><tr><th>Proxy</th><th>Tris</th>"
        "<th>AABB (min→max)</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return (
        '  <section class="collision-proxies">\n'
        '    <h2>Collision Proxies</h2>\n'
        f"    {table}\n"
        "  </section>"
    )


def _fmt_aabb(aabb: Any) -> str:
    if not isinstance(aabb, dict):
        return ""
    lo = aabb.get("min")
    hi = aabb.get("max")
    if not (isinstance(lo, list) and isinstance(hi, list) and len(lo) == 3 and len(hi) == 3):
        return ""
    try:
        lo_s = ", ".join(f"{float(v):.2f}" for v in lo)
        hi_s = ", ".join(f"{float(v):.2f}" for v in hi)
    except (TypeError, ValueError):
        return ""
    return f"[{lo_s}] -> [{hi_s}]"


def _extended_sections(build_dir: Path | None) -> str:
    """Concatenate the RPT-1/2/3/4 HTML sections, skipping missing ones."""
    parts = [
        _refs_manifest_section(build_dir),
        _geometry_kernel_section(build_dir),
        _lod_ladder_section(build_dir),
        _collision_proxies_section(build_dir),
    ]
    return "\n".join(p for p in parts if p)


def _resolve_build_dir(build_report: dict[str, Any]) -> Path | None:
    out_dir = build_report.get("out_dir")
    if not out_dir:
        return None
    try:
        path = Path(str(out_dir))
    except (TypeError, ValueError):
        return None
    return path if path.is_dir() else None


def render_html_report(build_report: dict[str, Any]) -> str:
    """Render ``build_report`` as a self-contained HTML document.

    The four RPT-1/2/3/4 "extended" sections (Refs & Selector Manifest,
    Geometry Kernel, LOD Ladder, Collision Proxies) are rendered only
    when ``build_report['out_dir']`` points at a real directory with
    the corresponding artifact. Pre-Wave-6 builds simply omit them.
    """

    certified = bool(build_report.get("certified"))
    build_dir = _resolve_build_dir(build_report)
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
        extended_sections=_extended_sections(build_dir),
    )
