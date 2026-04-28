"""``lathe ref diff <build_a> <build_b>`` — structural manifest diff (REF-11).

Shows added/removed/changed parts, sockets, pivots, materials between two
selector manifests. ``buildHash`` / ``packageHash`` deltas are surfaced as a
top-level summary so consumers can see when geometry changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_manifest(build_dir: Path) -> dict | None:
    p = build_dir / "selector_manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _ids(arr) -> set[str]:
    if not isinstance(arr, list):
        return set()
    return {item.get("id") for item in arr if isinstance(item, dict) and item.get("id")}


def _by_id(arr) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if isinstance(arr, list):
        for item in arr:
            if isinstance(item, dict) and item.get("id"):
                out[item["id"]] = item
    return out


def _diff_collection(a: list | None, b: list | None) -> dict:
    a_ids = _ids(a)
    b_ids = _ids(b)
    a_by = _by_id(a)
    b_by = _by_id(b)
    changed: list[dict] = []
    for pid in sorted(a_ids & b_ids):
        if a_by[pid] != b_by[pid]:
            changed.append({"id": pid, "before": a_by[pid], "after": b_by[pid]})
    return {
        "added": sorted(b_ids - a_ids),
        "removed": sorted(a_ids - b_ids),
        "changed": changed,
    }


def run_ref_diff(args) -> None:
    """Diff selector manifests from two completed build directories."""
    a_dir = Path(args.build_a)
    b_dir = Path(args.build_b)
    a = _load_manifest(a_dir)
    b = _load_manifest(b_dir)
    if a is None or b is None:
        missing = [str(p) for p, m in ((a_dir, a), (b_dir, b)) if m is None]
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"selector_manifest.json missing under: {missing}",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
    summary = {
        "build_a": str(a_dir),
        "build_b": str(b_dir),
        "asset": {"before": a.get("asset"), "after": b.get("asset")},
        "buildHash": {"before": a.get("buildHash"), "after": b.get("buildHash")},
        "packageHash": {"before": a.get("packageHash"), "after": b.get("packageHash")},
        "geometry_changed": a.get("packageHash") != b.get("packageHash"),
    }
    diff = {
        "parts": _diff_collection(a.get("parts"), b.get("parts")),
        "sockets": _diff_collection(a.get("sockets"), b.get("sockets")),
        "pivots": _diff_collection(a.get("pivots"), b.get("pivots")),
        "collisions": _diff_collection(a.get("collisions"), b.get("collisions")),
        "materials": _diff_collection(a.get("materials"), b.get("materials")),
        "diagnostics": _diff_collection(a.get("diagnostics"), b.get("diagnostics")),
    }
    print(json.dumps({"ok": True, "summary": summary, "diff": diff}, indent=2))
