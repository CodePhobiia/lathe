"""``lathe diff`` — compare two ``.lathe_snapshot.json`` files (RPT-5, V0.2).

Reads two RPT-4 snapshots and surfaces drift:

- stages whose hashes differ (drift);
- stages in only one snapshot (added / removed);
- score delta, certified-flip, latheVersion mismatch, sourcePath mismatch.

Default output is human-readable. ``--json`` emits the structured diff
envelope so CI consumers can branch on it. Matching stages with
identical hashes are suppressed unless ``--verbose`` is passed.

Exit codes:
  0 — no drift
  1 — drift detected (either stage hash, score, certified, lathe version, or source path)
  2 — bad arguments / missing file / unreadable snapshot
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ._common import _emit_error


def register(sub: argparse._SubParsersAction) -> None:
    """Register ``lathe diff`` on an existing argparse sub-parsers."""
    p = sub.add_parser(
        "diff",
        help="Compare two .lathe_snapshot.json files (RPT-5)",
        description=(
            "RPT-5 (V0.2): structural diff between two snapshot sidecars "
            "emitted by ``lathe snapshot`` (RPT-4). Exits 0 on no drift, "
            "1 on drift, 2 on usage error. Distinct from the ``ref diff`` "
            "sub-subcommand which diffs selector manifests."
        ),
    )
    p.add_argument("snapshot_a", help="First snapshot JSON (baseline)")
    p.add_argument("snapshot_b", help="Second snapshot JSON (candidate)")
    p.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")
    p.add_argument("--verbose", action="store_true", help="Include stages with matching hashes in the output")


def _load_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _stage_drift(a_stages: dict[str, str], b_stages: dict[str, str]) -> dict[str, Any]:
    """Return {matching, drifted, added, removed} for the stages maps."""
    a_keys = set(a_stages or {})
    b_keys = set(b_stages or {})
    matching: list[str] = []
    drifted: list[dict[str, str]] = []
    for stage in sorted(a_keys & b_keys):
        ah = a_stages.get(stage)
        bh = b_stages.get(stage)
        if ah == bh:
            matching.append(stage)
        else:
            drifted.append({"stage": stage, "a_hash": str(ah), "b_hash": str(bh)})
    added = sorted(b_keys - a_keys)
    removed = sorted(a_keys - b_keys)
    return {
        "matching": matching,
        "drifted": drifted,
        "added": [{"stage": s, "b_hash": str(b_stages.get(s))} for s in added],
        "removed": [{"stage": s, "a_hash": str(a_stages.get(s))} for s in removed],
    }


def _compute_diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Structured diff envelope — stable under ``--json``."""
    stages = _stage_drift(
        a.get("stages") if isinstance(a.get("stages"), dict) else {},
        b.get("stages") if isinstance(b.get("stages"), dict) else {},
    )

    score_a = a.get("score") if isinstance(a.get("score"), (int, float)) else None
    score_b = b.get("score") if isinstance(b.get("score"), (int, float)) else None
    score_delta = None
    if isinstance(score_a, (int, float)) and isinstance(score_b, (int, float)):
        score_delta = round(float(score_b) - float(score_a), 6)

    cert_a = a.get("certified")
    cert_b = b.get("certified")
    certified_flipped = isinstance(cert_a, bool) and isinstance(cert_b, bool) and cert_a != cert_b

    lathe_version_mismatch = (
        bool(a.get("latheVersion"))
        and bool(b.get("latheVersion"))
        and a.get("latheVersion") != b.get("latheVersion")
    )

    source_path_mismatch = (
        bool(a.get("sourcePath")) and bool(b.get("sourcePath")) and a.get("sourcePath") != b.get("sourcePath")
    )

    has_drift = bool(
        stages["drifted"]
        or stages["added"]
        or stages["removed"]
        or certified_flipped
        or (score_delta is not None and score_delta != 0.0)
        or lathe_version_mismatch
        or source_path_mismatch
    )

    return {
        "schemaVersion": 1,
        "a": {
            "latheVersion": a.get("latheVersion"),
            "sourcePath": a.get("sourcePath"),
            "buildHash": a.get("buildHash"),
            "score": score_a,
            "certified": cert_a,
        },
        "b": {
            "latheVersion": b.get("latheVersion"),
            "sourcePath": b.get("sourcePath"),
            "buildHash": b.get("buildHash"),
            "score": score_b,
            "certified": cert_b,
        },
        "stages": stages,
        "score_delta": score_delta,
        "certified_flipped": certified_flipped,
        "latheVersion_mismatch": lathe_version_mismatch,
        "sourcePath_mismatch": source_path_mismatch,
        "has_drift": has_drift,
    }


def _format_human(diff: dict[str, Any], *, verbose: bool) -> str:
    """Render ``diff`` as a human-readable block."""
    lines: list[str] = []
    a_info = diff["a"]
    b_info = diff["b"]
    lines.append("lathe diff (RPT-5)")
    lines.append(
        f"  a: lathe={a_info.get('latheVersion')} source={a_info.get('sourcePath')} "
        f"build={a_info.get('buildHash')}"
    )
    lines.append(
        f"  b: lathe={b_info.get('latheVersion')} source={b_info.get('sourcePath')} "
        f"build={b_info.get('buildHash')}"
    )
    lines.append("")

    if not diff["has_drift"]:
        lines.append("no drift")
        if verbose:
            stages = diff["stages"]["matching"]
            if stages:
                lines.append(f"  matching stages: {', '.join(stages)}")
        return "\n".join(lines)

    if diff["certified_flipped"]:
        lines.append(
            f"!! certified flipped: a.certified={a_info.get('certified')} "
            f"-> b.certified={b_info.get('certified')}"
        )
    if diff["score_delta"] is not None and diff["score_delta"] != 0.0:
        arrow = "+" if diff["score_delta"] > 0 else ""
        lines.append(
            f"score: {a_info.get('score')} -> {b_info.get('score')} (delta {arrow}{diff['score_delta']})"
        )
    if diff["latheVersion_mismatch"]:
        lines.append(
            f"warning: latheVersion mismatch ({a_info.get('latheVersion')} != {b_info.get('latheVersion')})"
        )
    if diff["sourcePath_mismatch"]:
        lines.append(
            f"warning: sourcePath mismatch ({a_info.get('sourcePath')} != {b_info.get('sourcePath')})"
        )

    stages = diff["stages"]
    drifted = stages["drifted"]
    if drifted:
        lines.append(f"drifted stages ({len(drifted)}):")
        for entry in drifted:
            lines.append(f"  - {entry['stage']}: {entry['a_hash'][:12]}... -> {entry['b_hash'][:12]}...")
    if stages["added"]:
        lines.append(f"added stages ({len(stages['added'])}):")
        for entry in stages["added"]:
            lines.append(f"  + {entry['stage']}: {entry['b_hash'][:12]}...")
    if stages["removed"]:
        lines.append(f"removed stages ({len(stages['removed'])}):")
        for entry in stages["removed"]:
            lines.append(f"  - {entry['stage']}: {entry['a_hash'][:12]}...")

    if verbose:
        matching = stages["matching"]
        if matching:
            lines.append(f"matching stages ({len(matching)}): {', '.join(matching)}")

    return "\n".join(lines)


def run_diff(args: argparse.Namespace) -> None:
    """Dispatch ``lathe diff``."""
    a_path = Path(args.snapshot_a)
    b_path = Path(args.snapshot_b)

    if not a_path.exists():
        _emit_error(
            "lathe.cli.diff.missing_snapshot",
            f"snapshot not found: {a_path}",
            "Run `lathe snapshot <build_dir>` to produce one, then retry.",
            exit_code=2,
        )
        return
    if not b_path.exists():
        _emit_error(
            "lathe.cli.diff.missing_snapshot",
            f"snapshot not found: {b_path}",
            "Run `lathe snapshot <build_dir>` to produce one, then retry.",
            exit_code=2,
        )
        return

    a = _load_snapshot(a_path)
    b = _load_snapshot(b_path)
    if a is None:
        _emit_error(
            "lathe.cli.diff.unreadable_snapshot",
            f"not a valid JSON snapshot: {a_path}",
            "Regenerate with `lathe snapshot`.",
            exit_code=2,
        )
        return
    if b is None:
        _emit_error(
            "lathe.cli.diff.unreadable_snapshot",
            f"not a valid JSON snapshot: {b_path}",
            "Regenerate with `lathe snapshot`.",
            exit_code=2,
        )
        return

    diff = _compute_diff(a, b)

    if getattr(args, "as_json", False):
        print(json.dumps(diff, indent=2, sort_keys=True))
    else:
        print(_format_human(diff, verbose=bool(getattr(args, "verbose", False))))

    raise SystemExit(1 if diff["has_drift"] else 0)


__all__ = ["register", "run_diff"]
