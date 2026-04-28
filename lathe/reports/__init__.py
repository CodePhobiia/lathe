"""Human-facing build report renderers (BL-36, Plan 08 Phases 6+7; RPT-3).

Consumes a ``build_report.json`` dict and renders either a terminal
(ANSI / plain) or self-contained HTML artifact. ``write_report`` is
the canonical entry point invoked by ``lathe build --report``.

When ``deterministic=True``, the report dict is passed through
``canonicalize_report`` first: timestamps are zeroed, backslashes are
replaced with forward slashes, home paths are collapsed to ``<home>``,
stage runtimes are rounded to the nearest millisecond, and diagnostics
are sorted by code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePath
from typing import Any

from .html import render_html_report
from .terminal import render_terminal_report

__all__ = [
    "canonicalize_report",
    "render_html_report",
    "render_terminal_report",
    "write_report",
]


_ISO_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")
_ZEROED_TIMESTAMP = "0000-00-00T00:00:00Z"

_TIMESTAMP_KEYS: frozenset[str] = frozenset(
    {"timestamp", "started_at", "finished_at", "built_at", "created_at", "updated_at"}
)
_RUNTIME_KEYS: frozenset[str] = frozenset({"runtime_ms", "elapsed_ms", "duration_ms", "wall_ms"})
_RUNTIME_SEC_KEYS: frozenset[str] = frozenset(
    {"runtime_s", "elapsed_s", "duration_s", "wall_s", "elapsed_seconds"}
)


def _home_prefixes() -> list[str]:
    home = str(Path("~").expanduser())
    out: list[str] = []
    if home and home != "~":
        out.append(home.replace("\\", "/"))
        out.append(home)
    return out


def _canonical_path(raw: str) -> str:
    forward = raw.replace("\\", "/")
    for home in _home_prefixes():
        home_norm = home.replace("\\", "/")
        if forward.startswith(home_norm):
            forward = "<home>" + forward[len(home_norm) :]
            break
    return forward


def _looks_like_path(key: str, value: str) -> bool:
    if "\\" in value or "/" in value:
        return True
    if key in {"path", "source_path", "sourcePath", "out_dir", "build_dir"}:
        return True
    return False


def _canonicalize_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return _canonicalize_dict(value)
    if isinstance(value, list):
        return [_canonicalize_value(key, item) for item in value]
    if isinstance(value, str):
        if key in _TIMESTAMP_KEYS and _ISO_TIMESTAMP_RE.match(value):
            return _ZEROED_TIMESTAMP
        if _looks_like_path(key, value):
            return _canonical_path(value)
        return value
    if isinstance(value, float):
        if key in _RUNTIME_KEYS:
            return float(round(value))
        if key in _RUNTIME_SEC_KEYS:
            return round(value, 3)
    if isinstance(value, (int, float)) and key in _RUNTIME_KEYS:
        return round(float(value))
    return value


def _canonicalize_dict(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in sorted(data.keys()):
        out[k] = _canonicalize_value(str(k), data[k])
    # Sort diagnostics by code (stable across runs).
    if "diagnostics" in out and isinstance(out["diagnostics"], list):
        out["diagnostics"] = sorted(
            out["diagnostics"],
            key=lambda d: (
                str(d.get("severity") or "") if isinstance(d, dict) else "",
                str(d.get("code") or d.get("reason") or "") if isinstance(d, dict) else "",
                str(d.get("message") or "") if isinstance(d, dict) else "",
            ),
        )
    return out


def canonicalize_report(build_report: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical copy of ``build_report`` for deterministic output.

    Applies the RPT-3 rules: zero ISO8601 timestamps, forward slashes
    only, home paths collapsed to ``<home>``, runtime_ms rounded to the
    nearest ms, keys sorted recursively, diagnostics sorted by code.
    The input is not mutated.
    """
    return _canonicalize_dict(build_report)


def _canonical_json_bytes(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ": "), ensure_ascii=False)


def write_report(
    build_report: dict[str, Any],
    out_dir: Path,
    format: str,
    *,
    deterministic: bool = False,
) -> Path:
    """Write a rendered report alongside ``build_report.json``.

    - ``format="html"``: writes ``report.html`` and returns its path.
    - ``format="terminal"``: writes ``report.txt`` (plain, no color).
    - ``format="json"``: writes ``build_report.json`` and returns it.

    When ``deterministic=True``, the report dict is first passed
    through :func:`canonicalize_report`. JSON reports then use
    canonical formatting (sorted keys, ``(",", ": ")`` separators)
    so two fresh builds emit byte-identical files.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = format.lower()
    payload = canonicalize_report(build_report) if deterministic else build_report
    if fmt == "html":
        path = out_dir / "report.html"
        path.write_text(render_html_report(payload), encoding="utf-8")
        return path
    if fmt == "terminal":
        path = out_dir / "report.txt"
        path.write_text(render_terminal_report(payload, use_color=False), encoding="utf-8")
        return path
    if fmt == "json":
        path = out_dir / "build_report.json"
        if deterministic:
            path.write_text(_canonical_json_bytes(payload), encoding="utf-8")
        elif not path.exists():
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
    raise ValueError(f"Unknown report format: {format!r}")


# Re-export PurePath so tests can import through this namespace if needed.
_ = PurePath
