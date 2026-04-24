"""Shared helpers for the CLI subcommand modules.

Argument parsing, output formatting and runtime-config loading used
by more than one subcommand.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any


def _dump(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


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
