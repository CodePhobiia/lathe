"""Terminal report renderer (BL-36, Plan 08 Phase 6; RPT-2/3, V0.2 E4).

Renders a ``build_report.json`` dict as a readable block for stdout.
Uses ``rich`` if available for colored tables; otherwise falls back
to hand-rolled ANSI (or no color, if stdout is not a TTY or
``use_color=False``). Mirrors the four RPT-1 HTML sections.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
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
    for source in build_report.get("diagnostics") or []:
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


def _read_json(path: Path) -> Any | None:
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _resolve_build_dir(build_report: dict[str, Any]) -> Path | None:
    out_dir = build_report.get("out_dir")
    if not out_dir:
        return None
    try:
        path = Path(str(out_dir))
    except (TypeError, ValueError):
        return None
    return path if path.is_dir() else None


def _refs_manifest_lines(build_dir: Path, *, use_color: bool) -> list[str]:
    manifest = _read_json(build_dir / "selector_manifest.json")
    if not isinstance(manifest, dict):
        return []
    lines: list[str] = [_paint("Refs & Selector Manifest", "bold", "cyan", enabled=use_color)]
    for label, key in (
        ("Parts", "parts"),
        ("Sockets", "sockets"),
        ("Pivots", "pivots"),
        ("Collisions", "collisions"),
        ("LODs", "lods"),
        ("Materials", "materials"),
    ):
        items = manifest.get(key) or []
        if not isinstance(items, list):
            items = []
        top_names: list[str] = []
        for item in items[:3]:
            if isinstance(item, dict):
                name = item.get("name") or item.get("id")
                if name:
                    top_names.append(str(name))
        suffix = f"  [{', '.join(top_names)}]" if top_names else ""
        lines.append(f"  {label:<11}{len(items):>4}{suffix}")
    lines.append("")
    return lines


def _geometry_kernel_lines(build_dir: Path, *, use_color: bool) -> list[str]:
    bundle = _read_json(build_dir / "stages" / "shape" / "bundle.json")
    if not isinstance(bundle, dict):
        return []
    stats = bundle.get("bundle_stats")
    if not isinstance(stats, dict):
        return []
    kernel_id = stats.get("geometry_kernel") or bundle.get("backend_id") or "?"
    watertight_rate = stats.get("watertight_rate")
    candidates = stats.get("candidate_count", 0)
    watertight = stats.get("watertight_candidate_count", 0)
    try:
        pct = f"{float(watertight_rate) * 100.0:.1f}%"
    except (TypeError, ValueError):
        pct = "n/a"
    lines = [_paint("Geometry Kernel", "bold", "cyan", enabled=use_color)]
    lines.append(f"  kernel_id:        {kernel_id}")
    lines.append(f"  watertight_rate:  {pct}  ({watertight}/{candidates} candidates)")
    determinism = bundle.get("determinism_class")
    if determinism:
        lines.append(f"  determinism:      {determinism}")
    lines.append("")
    return lines


def _lod_ladder_lines(build_dir: Path, *, use_color: bool) -> list[str]:
    manifest = _read_json(build_dir / "stages" / "optimize" / "lod_manifest.json")
    if not isinstance(manifest, dict):
        return []
    lods = manifest.get("lods") or []
    if not isinstance(lods, list) or not lods:
        return []
    lines = [_paint("LOD Ladder", "bold", "cyan", enabled=use_color)]
    lines.append(f"  {'level':<6}{'ratio':<8}{'tris':<10}path")
    for lod in lods:
        if not isinstance(lod, dict):
            continue
        level = lod.get("level", "?")
        ratio = lod.get("ratio", "?")
        tris = lod.get("tris", lod.get("triangle_count", "?"))
        path = str(lod.get("path") or "").replace("\\", "/")
        lines.append(f"  {level!s:<6}{ratio!s:<8}{tris!s:<10}{path}")
    lines.append("")
    return lines


def _collision_proxies_lines(build_dir: Path, *, use_color: bool) -> list[str]:
    manifest = _read_json(build_dir / "stages" / "optimize" / "collision_manifest.json")
    if not isinstance(manifest, dict):
        return []
    proxies = manifest.get("proxies") or []
    if not isinstance(proxies, list) or not proxies:
        return []
    lines = [_paint("Collision Proxies", "bold", "cyan", enabled=use_color)]
    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        name = proxy.get("name") or "?"
        tris = proxy.get("tris")
        tris_s = f"tris={tris}" if tris is not None else ""
        lines.append(f"  {name}  {tris_s}".rstrip())
        for sub in proxy.get("subproxies") or []:
            if not isinstance(sub, dict):
                continue
            sname = sub.get("name") or "?"
            stris = sub.get("tris")
            lines.append(f"    - {sname}  tris={stris}")
    lines.append("")
    return lines


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
                f"  {name.ljust(width)}  {_paint(status.upper(), color, enabled=use_color)}  {summary}"
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

    build_dir = _resolve_build_dir(build_report)
    if build_dir is not None:
        for extra in (
            _refs_manifest_lines(build_dir, use_color=use_color),
            _geometry_kernel_lines(build_dir, use_color=use_color),
            _lod_ladder_lines(build_dir, use_color=use_color),
            _collision_proxies_lines(build_dir, use_color=use_color),
        ):
            lines.extend(extra)

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

    build_dir = _resolve_build_dir(build_report)
    if build_dir is not None:
        _render_rich_extended(console, build_dir, Table)

    out_dir = build_report.get("out_dir")
    if out_dir:
        console.print(f"[dim]Build directory: {out_dir}[/]")

    return buf.getvalue()


def _render_rich_extended(console: Any, build_dir: Path, Table: Any) -> None:
    manifest = _read_json(build_dir / "selector_manifest.json")
    if isinstance(manifest, dict):
        table = Table(title="Refs & Selector Manifest", show_header=True, header_style="bold cyan")
        table.add_column("Category")
        table.add_column("Count")
        table.add_column("Top 3")
        for label, key in (
            ("Parts", "parts"),
            ("Sockets", "sockets"),
            ("Pivots", "pivots"),
            ("Collisions", "collisions"),
            ("LODs", "lods"),
            ("Materials", "materials"),
        ):
            items = manifest.get(key) or []
            items = items if isinstance(items, list) else []
            top = ", ".join(str(i.get("name") or i.get("id") or "") for i in items[:3] if isinstance(i, dict))
            table.add_row(label, str(len(items)), top or "(none)")
        console.print(table)

    bundle = _read_json(build_dir / "stages" / "shape" / "bundle.json")
    if isinstance(bundle, dict) and isinstance(bundle.get("bundle_stats"), dict):
        stats = bundle["bundle_stats"]
        try:
            pct = f"{float(stats.get('watertight_rate')) * 100.0:.1f}%"
        except (TypeError, ValueError):
            pct = "n/a"
        table = Table(title="Geometry Kernel", show_header=False)
        table.add_column("k")
        table.add_column("v")
        table.add_row("kernel_id", str(stats.get("geometry_kernel") or bundle.get("backend_id") or "?"))
        table.add_row(
            "watertight",
            f"{pct}  ({stats.get('watertight_candidate_count', 0)}/{stats.get('candidate_count', 0)})",
        )
        console.print(table)

    lod_manifest = _read_json(build_dir / "stages" / "optimize" / "lod_manifest.json")
    if isinstance(lod_manifest, dict) and lod_manifest.get("lods"):
        table = Table(title="LOD Ladder", show_header=True, header_style="bold cyan")
        table.add_column("Level")
        table.add_column("Ratio")
        table.add_column("Tris")
        table.add_column("Path")
        for lod in lod_manifest["lods"]:
            if not isinstance(lod, dict):
                continue
            table.add_row(
                str(lod.get("level", "?")),
                str(lod.get("ratio", "?")),
                str(lod.get("tris", lod.get("triangle_count", "?"))),
                str(lod.get("path") or "").replace("\\", "/"),
            )
        console.print(table)

    coll_manifest = _read_json(build_dir / "stages" / "optimize" / "collision_manifest.json")
    if isinstance(coll_manifest, dict) and coll_manifest.get("proxies"):
        table = Table(title="Collision Proxies", show_header=True, header_style="bold cyan")
        table.add_column("Proxy")
        table.add_column("Tris")
        for proxy in coll_manifest["proxies"]:
            if not isinstance(proxy, dict):
                continue
            table.add_row(str(proxy.get("name", "?")), str(proxy.get("tris", "")))
            for sub in proxy.get("subproxies") or []:
                if not isinstance(sub, dict):
                    continue
                table.add_row(f"  - {sub.get('name', '?')}", str(sub.get("tris", "")))
        console.print(table)


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
