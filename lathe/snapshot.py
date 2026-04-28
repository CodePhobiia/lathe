"""Canonical hash-based build snapshot (RPT-4, V0.2 E4).

A snapshot is a small JSON sidecar that hashes each stage bundle
(``bundle.json`` / ``report.json``) in a completed build directory.
It lets downstream tooling verify that two builds produced
bit-identical outputs without re-reading every artifact.

Canonical JSON rules (matching the wider codebase): UTF-8, sorted keys,
``(",", ": ")`` separators, no trailing newline. Stage hashes are
computed over the canonical JSON form of each stage's primary bundle,
so semantically-equivalent dicts with different key order hash the
same. Timestamps are zeroed when ``deterministic=True``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__ as _LATHE_VERSION

SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_FILENAME = ".lathe_snapshot.json"

STAGE_ORDER: tuple[str, ...] = (
    "refs",
    "intent",
    "shape",
    "topology",
    "uv",
    "surface",
    "execution",
    "rig",
    "interfaces",
    "physics",
    "optimize",
    "validate",
    "package",
)

_STAGE_BUNDLE_CANDIDATES: tuple[str, ...] = ("bundle.json", "report.json")

_DETERMINISTIC_TIMESTAMP = "0000-00-00T00:00:00Z"


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ": "), ensure_ascii=False)


def _sha256_of_canonical(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _hash_stage_dir(stage_dir: Path) -> str | None:
    """Return the sha256 of a stage's primary bundle, or None if absent."""
    if not stage_dir.is_dir():
        return None
    for name in _STAGE_BUNDLE_CANDIDATES:
        candidate = stage_dir / name
        if candidate.is_file():
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
            return _sha256_of_canonical(payload)
    return None


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(data, dict):
        return data
    return None


def collect_snapshot(build_dir: Path, *, deterministic: bool = False) -> dict[str, Any]:
    """Build a snapshot dict from a completed ``build_dir``.

    ``build_dir`` must be an existing directory. Missing stage dirs or
    unreadable bundles are tolerated: the corresponding stage hash is
    omitted from the ``stages`` map (rather than emitting ``null``).
    When ``deterministic=True`` the timestamp is zeroed.

    Raises:
        FileNotFoundError: if ``build_dir`` does not exist or is not a directory.
    """
    build_dir = Path(build_dir)
    if not build_dir.is_dir():
        raise FileNotFoundError(f"not a build directory: {build_dir}")

    stages_root = build_dir / "stages"
    stages: dict[str, str] = {}
    for stage in STAGE_ORDER:
        digest = _hash_stage_dir(stages_root / stage)
        if digest is not None:
            stages[stage] = digest

    selector = _read_json_if_exists(build_dir / "selector_manifest.json") or {}
    validate = _read_json_if_exists(stages_root / "validate" / "report.json")
    if validate is None:
        validate = _read_json_if_exists(stages_root / "validate" / "bundle.json") or {}

    snapshot: dict[str, Any] = {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "latheVersion": str(selector.get("latheVersion") or _LATHE_VERSION),
        "sourcePath": _canonical_source_path(selector.get("sourcePath")),
        "buildHash": str(selector.get("buildHash") or ""),
        "stages": stages,
        "timestamp": _DETERMINISTIC_TIMESTAMP if deterministic else _now_iso(),
    }

    score = validate.get("score") if isinstance(validate, dict) else None
    if isinstance(score, (int, float)):
        snapshot["score"] = float(score)

    certified = validate.get("certified") if isinstance(validate, dict) else None
    if certified is not None:
        snapshot["certified"] = bool(certified)

    return snapshot


def _canonical_source_path(raw: Any) -> str:
    if not raw:
        return ""
    return str(raw).replace("\\", "/")


def write_snapshot(
    build_dir: Path,
    *,
    out_path: Path | None = None,
    deterministic: bool = False,
) -> Path:
    """Emit a snapshot JSON for ``build_dir``.

    Defaults to ``<build_dir>/.lathe_snapshot.json``; pass ``out_path``
    to override. Writes canonical JSON (sorted keys) with no trailing
    newline so two deterministic runs produce byte-identical bytes.
    """
    snapshot = collect_snapshot(build_dir, deterministic=deterministic)
    target = Path(out_path) if out_path is not None else Path(build_dir) / SNAPSHOT_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_canonical_json(snapshot), encoding="utf-8")
    return target


__all__ = [
    "SNAPSHOT_FILENAME",
    "SNAPSHOT_SCHEMA_VERSION",
    "STAGE_ORDER",
    "collect_snapshot",
    "write_snapshot",
]
