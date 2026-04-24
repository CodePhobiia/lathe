"""Golden snapshots for the nine hero ``.lth`` builds (BL-24, Plan 04 Phase 8).

Each hero is built once per test via :func:`lathe.executor.build_asset` and
three facets are snapshotted with syrupy:

* the normalized build report + package manifest (paths + plan + outputs);
* the sha256 of every stage bundle (stable proxy for raw mesh/surface bytes);
* the validator report scores (certified / score / threshold + sub-scores).

First-run cost (cold cache): ~3 min per hero, ~25 min total across all 9.
Cached re-run cost (``$TEMP/lathe_build_cache`` warm): ~100 ms per hero, so
the full suite finishes in under 10 s once snapshots exist.

Regenerate snapshots intentionally with::

    .venv/Scripts/python.exe -m pytest tests/golden/test_hero_bundles.py \\
        --snapshot-update

Unexpected drift — a shape/topology/UV/package change that was not meant to
move artifacts — will fail these tests and surface the diff.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from lathe.executor import build_asset
from lathe.parser import parse_file


HEROES: tuple[tuple[str, str], ...] = (
    ("courier_drone", "examples/courier_drone.lth"),
    ("brassbound_chest", "examples/brassbound_chest.lth"),
    ("industrial_crate", "examples/industrial_crate.lth"),
    ("mechanical_door", "examples/mechanical_door.lth"),
    ("console_terminal", "examples/console_terminal.lth"),
    ("sci_fi_wall_panel", "examples/sci_fi_wall_panel.lth"),
    ("service_cabinet", "examples/service_cabinet.lth"),
    ("control_pedestal", "examples/control_pedestal.lth"),
    ("supply_container", "examples/supply_container.lth"),
)

_HERO_IDS = [name for name, _ in HEROES]

_STAGE_BUNDLES: tuple[str, ...] = (
    "stages/shape/bundle.json",
    "stages/topology/bundle.json",
    "stages/uv/bundle.json",
    "stages/surface/bundle.json",
    "stages/execution/bundle.json",
    "stages/rig/bundle.json",
    "stages/interfaces/bundle.json",
    "stages/physics/bundle.json",
    "stages/optimize/bundle.json",
    "stages/package/bundle.json",
    "stages/validate/report.json",
)

# Absolute-path masking. Covers Windows drive-letter paths and POSIX tmp/var
# paths that leak in via Blender/xatlas probe reports and ref-resolution
# records. Hero refs under ``examples/refs/`` also canonicalise to ``<ABS>``
# so host-specific repo-root differences cannot drift snapshots.
_ABS_PATH_RE = re.compile(
    r"[A-Za-z]:[\\/][^\"\s]+"  # Windows absolute
    r"|/(?:tmp|var|private)/[^\"\s]+"  # POSIX tmp
)

# Keys whose string *values* are volatile runtime paths rather than semantic
# data; mask them wholesale regardless of the value contents.
_VOLATILE_STRING_KEYS = frozenset({
    "out_dir",
    "blender_path",
    "source_root",
    "resolved",
    "path",
    "trace_path",
    "manifest_path",
    "uri",  # stage-local file URIs like "stages/package/courier_drone.glb" are relative (kept), but absolute forms are masked by the regex above
})

# Latency / timing fields should never have been in the bundles, but mask any
# that slip in to future-proof the normaliser. Snapshots will include these as
# the literal ``<LATENCY>`` sentinel if encountered.
_LATENCY_KEYS = frozenset({
    "latency_ms",
    "probe_latency_ms",
    "wall_time_ms",
    "elapsed_ms",
    "duration_s",
    "duration_ms",
    "timestamp",
    "started_at",
    "finished_at",
})

_ISO_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_REPR_ID_RE = re.compile(r"at 0x[0-9a-f]+")


# Relative stage paths ship as ``stages\\package\\bundle.json`` on Windows
# and ``stages/package/bundle.json`` on POSIX (``os.sep`` via ``relpath``).
# Normalise to POSIX in ``_scrub_value`` so snapshots stay portable.


def _scrub_value(value: Any, key: str | None = None) -> Any:
    """Replace nondeterministic tokens inside a scalar with stable sentinels."""
    if isinstance(value, str):
        if key in _VOLATILE_STRING_KEYS:
            # Only mask if the string actually looks path-like; preserve names
            # like ``stages/package/bundle.json`` which are reproducible
            # relative paths we do want to snapshot.
            if _ABS_PATH_RE.search(value):
                return "<ABS>"
            # Still normalise POSIX/Windows separator divergence for
            # relative paths we preserve.
            return value.replace("\\", "/")
        if _ISO_TIMESTAMP_RE.match(value):
            return "<TIMESTAMP>"
        if _REPR_ID_RE.search(value):
            value = _REPR_ID_RE.sub("at 0x<ID>", value)
        scrubbed = _ABS_PATH_RE.sub("<ABS>", value)
        # After abs-path masking, flip any lingering Windows separators
        # inside relative-looking strings (no drive letter prefix). Do not
        # touch values where every ``\`` is already a literal escape.
        if "\\" in scrubbed and not _ABS_PATH_RE.search(scrubbed):
            scrubbed = scrubbed.replace("\\", "/")
        return scrubbed
    return value


def _normalize_bundle(obj: Any, key: str | None = None) -> Any:
    """Recursively strip timestamps / absolute paths / repr-ids / probe latency.

    The scrubber is intentionally conservative: we mask only the things we
    have *seen* drift between runs (absolute paths on the host; Blender /
    xatlas probe paths; shape-stage ref resolution). Anything we have not
    observed as volatile is kept so that real regressions still fail the
    snapshot.
    """
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            # Dict keys are sometimes relative file paths too (e.g. the
            # per-output hash map inside ``package_manifest.json``). Flip
            # Windows backslashes so POSIX hosts produce the same keys.
            norm_key = k.replace("\\", "/") if isinstance(k, str) and "\\" in k else k
            if norm_key in _LATENCY_KEYS:
                out[norm_key] = "<LATENCY>"
                continue
            out[norm_key] = _normalize_bundle(v, key=norm_key)
        return out
    if isinstance(obj, list):
        return [_normalize_bundle(v, key=key) for v in obj]
    return _scrub_value(obj, key=key)


def _hash_json(path: Path) -> str:
    """Hash the *normalised* JSON bundle at ``path``.

    We hash the normalised (path-scrubbed) form so that two runs on different
    machines — or two different tmpdirs on the same machine — produce the
    same hash. Raw bundle bytes are not stable across tmpdir locations.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    normalised = _normalize_bundle(data)
    canonical = json.dumps(normalised, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def _hero_builds(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Build every hero once per test *module* and return its out-dir.

    Per-test ``tmp_path`` would rebuild each hero three times (one per
    snapshot test) for the same cache key — needless IO even with a warm
    cache. Module-scoped builds drop the test-suite total from ~30 builds
    to ~9 without changing determinism (the build is a pure function of
    ``(program, asset_name, runtime_config)``).
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    base = tmp_path_factory.mktemp("golden_hero_builds")
    out_dirs: dict[str, Path] = {}
    for name, rel_source in HEROES:
        program = parse_file(repo_root / rel_source)
        out_dir = base / name
        build_asset(program, name, out_dir)
        out_dirs[name] = out_dir
    return out_dirs


@pytest.mark.golden
@pytest.mark.parametrize("name,source", HEROES, ids=_HERO_IDS)
def test_hero_manifest_snapshot(
    name: str,
    source: str,  # noqa: ARG001 — kept for readable parametrize ids
    _hero_builds: dict[str, Path],
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the build report + package manifest (paths, outputs, stack)."""
    out_dir = _hero_builds[name]
    build_report = json.loads((out_dir / "build_report.json").read_text(encoding="utf-8"))
    package_manifest = json.loads(
        (out_dir / "stages/package/package_manifest.json").read_text(encoding="utf-8")
    )

    manifest = {
        "build_report": _normalize_bundle(build_report),
        "package_manifest": _normalize_bundle(package_manifest),
    }
    assert manifest == snapshot


@pytest.mark.golden
@pytest.mark.parametrize("name,source", HEROES, ids=_HERO_IDS)
def test_hero_stage_bundle_hashes_snapshot(
    name: str,
    source: str,  # noqa: ARG001
    _hero_builds: dict[str, Path],
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot sha256 of every stage bundle's normalised JSON.

    This is intentionally a hash rather than the raw bundle so that any
    drift in large stage outputs (shape bundle is ~1 MB of candidates)
    still gets caught without bloating the ``.ambr`` fixture.
    """
    out_dir = _hero_builds[name]
    hashes = {relpath: _hash_json(out_dir / relpath) for relpath in _STAGE_BUNDLES}
    assert hashes == snapshot


@pytest.mark.golden
@pytest.mark.parametrize("name,source", HEROES, ids=_HERO_IDS)
def test_hero_validator_scores_snapshot(
    name: str,
    source: str,  # noqa: ARG001
    _hero_builds: dict[str, Path],
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot validator certification, score, threshold, and sub-scores."""
    out_dir = _hero_builds[name]
    report = json.loads(
        (out_dir / "stages/validate/report.json").read_text(encoding="utf-8")
    )

    scores: dict[str, Any] = {
        "certified": report["certified"],
        "score": report["score"],
        "threshold": report["threshold"],
        "rule_results": _normalize_bundle(report.get("rule_results", [])),
        "semantic_quality": _normalize_bundle(report.get("semantic_quality", {})),
        "visual_quality": _normalize_bundle(report.get("visual_quality", {})),
        "flow_quality": _normalize_bundle(report.get("flow_quality", {})),
        "reselection_attempts": report.get("reselection_attempts", 0),
        "semantic_repairs_applied": report.get("semantic_repairs_applied", []),
    }
    assert scores == snapshot
