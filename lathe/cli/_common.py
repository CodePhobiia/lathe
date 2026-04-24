"""Shared helpers for the CLI subcommand modules.

Argument parsing, output formatting and runtime-config loading used
by more than one subcommand.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path
from typing import Any


def _dump(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


_SEVERITY_ANSI = {
    "error": "\033[1;31m",
    "warning": "\033[1;33m",
    "info": "\033[1;34m",
}
_ANSI_RESET = "\033[0m"


def _stderr_is_tty() -> bool:
    return bool(getattr(sys.stderr, "isatty", lambda: False)())


def _emit_error(
    code: str,
    message: str,
    next_step: str,
    *,
    exit_code: int = 2,
    source_path: str | None = None,
    source_line: int | None = None,
    severity: str = "error",
) -> None:
    """Emit a structured CLI error to stderr and exit.

    Writes a short, human-readable block:
    ``lathe error [code]: message`` followed by an optional
    ``  at <path>:<line>`` citation and a ``  Next step: <hint>`` line.
    Color is applied when stderr is a TTY.
    """

    use_color = _stderr_is_tty()
    tag = severity.lower()
    prefix = _SEVERITY_ANSI.get(tag, "") if use_color else ""
    reset = _ANSI_RESET if use_color and prefix else ""
    lines: list[str] = []
    lines.append(f"{prefix}lathe {tag} [{code}]{reset}: {message}")
    if source_path:
        citation = source_path if source_line is None else f"{source_path}:{source_line}"
        lines.append(f"  at {citation}")
    lines.append(f"  Next step: {next_step}")
    print("\n".join(lines), file=sys.stderr)
    raise SystemExit(exit_code)


def _expand_files(patterns: list[str] | None) -> list[str]:
    if not patterns:
        return []
    expanded: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            expanded.extend(matches)
        else:
            expanded.append(pattern)
    seen: set[str] = set()
    out: list[str] = []
    for item in expanded:
        resolved = str(Path(item).resolve())
        if resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out


def _diff_objects(left: Any, right: Any, path: str = "") -> dict[str, Any]:
    if type(left) is not type(right):
        return {"path": path or "$", "left": left, "right": right}
    if isinstance(left, dict):
        diffs = []
        keys = sorted(set(left) | set(right))
        for key in keys:
            if key not in left or key not in right:
                diffs.append({"path": f"{path}.{key}" if path else key, "left": left.get(key), "right": right.get(key)})
            else:
                child = _diff_objects(left[key], right[key], f"{path}.{key}" if path else key)
                if child:
                    if isinstance(child, list):
                        diffs.extend(child)
                    else:
                        diffs.append(child)
        return diffs
    if isinstance(left, list):
        if left != right:
            return {"path": path or "$", "left": left, "right": right}
        return {}
    if left != right:
        return {"path": path or "$", "left": left, "right": right}
    return {}
