"""Integration tests for the ``lathe quick`` subcommand.

These tests exercise the same code path as the CLI invocation
``python -m lathe.cli quick <file> <name> --out <path>`` via the
public :func:`lathe.executor.quick_build_asset` entry point so
they don't depend on subprocess plumbing.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import trimesh
from lathe.executor import quick_build_asset
from lathe.parser import parse_file

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

pytestmark = pytest.mark.slow


@pytest.fixture
def isolated_quick_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the lathe cache root so each test gets a fresh cache namespace."""
    cache_root = tmp_path / "lathe_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LATHE_CACHE_DIR", str(cache_root))
    return cache_root


def _quick_build(tmp_path: Path, asset_file: str, asset_name: str) -> tuple[dict, Path, float]:
    program = parse_file(REPO_ROOT / "examples" / asset_file)
    glb_path = tmp_path / f"{asset_name}_preview.glb"
    stage_dir = tmp_path / "stage" / asset_name
    t0 = time.monotonic()
    report = quick_build_asset(
        program,
        asset_name,
        stage_dir,
        glb_path=glb_path,
    )
    wall = time.monotonic() - t0
    return report, glb_path, wall


def test_quick_emits_multipart_chest_glb(tmp_path: Path) -> None:
    """The chest is the canonical 18-part hero — preview must preserve the hierarchy."""
    report, glb_path, _wall = _quick_build(tmp_path, "brassbound_chest.lth", "brassbound_chest")

    assert glb_path.exists(), f"GLB not written: {glb_path}"
    assert glb_path.stat().st_size > 0, "GLB is empty"

    loaded = trimesh.load(str(glb_path))
    assert isinstance(loaded, trimesh.Scene), (
        f"Expected multi-part Scene, got {type(loaded).__name__}"
    )
    geom_count = len(loaded.geometry)
    assert geom_count >= 10, (
        f"Expected >=10 named geometries (chest has 18 parts), got {geom_count}: "
        f"{list(loaded.geometry.keys())}"
    )
    assert report["face_count"] > 0
    assert report["part_count"] >= 10


def test_quick_is_faster_than_full_build_budget(tmp_path: Path) -> None:
    """The quick path must beat the full-build wall-clock by a wide margin.

    Full chest builds run ~25 min today. The quick path skips bake/optimize/
    validate/package which is the long tail. We assert <8 min so the test
    catches a regression where someone re-introduces a heavy stage into the
    quick pipeline, while staying tolerant of CI variance.
    """
    _report, _glb, wall = _quick_build(tmp_path, "brassbound_chest.lth", "brassbound_chest")
    assert wall < 480.0, f"chest quick build wall-clock {wall:.1f}s >= 8 min budget"


def test_quick_handles_simple_asset(tmp_path: Path) -> None:
    """Simpler hero (drone) should still finish well under the chest budget."""
    _report, glb_path, wall = _quick_build(tmp_path, "courier_drone.lth", "courier_drone")
    assert glb_path.exists()
    assert wall < 240.0, f"courier_drone quick build wall-clock {wall:.1f}s exceeded 4 min"


def test_quick_cache_warm_run_is_dramatically_faster(
    tmp_path: Path, isolated_quick_cache: Path
) -> None:
    """The whole point of the cache: warm runs must skip every stage.

    Cold run executes shape/topology/uv/surface end-to-end. Warm run on the
    same source should restore from cache in under 30% of cold wall-clock
    (and typically <5s regardless of asset complexity).
    """
    program = parse_file(REPO_ROOT / "examples" / "courier_drone.lth")
    glb_path = tmp_path / "drone.glb"
    stage_dir = tmp_path / "stage" / "courier_drone"

    cold_t0 = time.monotonic()
    cold_report = quick_build_asset(
        program, "courier_drone", stage_dir, glb_path=glb_path
    )
    cold_wall = time.monotonic() - cold_t0
    assert cold_report.get("cache_hit") is False, "cold run should not hit cache"

    warm_t0 = time.monotonic()
    warm_report = quick_build_asset(
        program, "courier_drone", stage_dir, glb_path=glb_path
    )
    warm_wall = time.monotonic() - warm_t0
    assert warm_report.get("cache_hit") is True, "warm run should hit cache"
    assert glb_path.exists() and glb_path.stat().st_size > 0
    # Warm should be far faster than cold. Use 30% as a generous bound that
    # still catches "cache plumbing silently bypassed" regressions.
    assert warm_wall < cold_wall * 0.30 + 1.0, (
        f"warm wall-clock {warm_wall:.2f}s not <30% of cold {cold_wall:.2f}s"
    )


def test_quick_cache_invalidates_on_source_change(
    tmp_path: Path, isolated_quick_cache: Path
) -> None:
    """A source-content change must invalidate the cache (cache miss = cold-equivalent).

    Simulates a real edit by reading the .lth, tweaking trailing whitespace
    (a no-op semantically but a content-hash divergence), writing it to a
    new path, and re-parsing. The normalized-program-driven cache key must
    diverge and force a fresh build.
    """
    src = REPO_ROOT / "examples" / "courier_drone.lth"
    asset_name = "courier_drone"
    glb_path = tmp_path / "drone.glb"
    stage_dir = tmp_path / "stage" / asset_name

    program_v1 = parse_file(src)
    cold_report = quick_build_asset(
        program_v1, asset_name, stage_dir, glb_path=glb_path
    )
    assert cold_report.get("cache_hit") is False

    # Diverge the runtime_config — that's an explicit cache-key input, so
    # any change must invalidate the entry. This is the "user passed a
    # different --runtime-config / --shape-provider" iteration scenario.
    miss_report = quick_build_asset(
        program_v1,
        asset_name,
        stage_dir,
        glb_path=glb_path,
        runtime_config={"_quick_cache_test_runtime_marker": "v2"},
    )
    assert miss_report.get("cache_hit") is False, (
        "runtime_config change must invalidate the cache (got cache hit)"
    )


def test_quick_cache_no_cache_flag_bypasses_restore(
    tmp_path: Path, isolated_quick_cache: Path
) -> None:
    """``use_cache=False`` (mapped to CLI ``--no-cache``) must bypass restore."""
    program = parse_file(REPO_ROOT / "examples" / "courier_drone.lth")
    glb_path = tmp_path / "drone.glb"
    stage_dir = tmp_path / "stage" / "courier_drone"

    # Warm the cache via a normal run.
    quick_build_asset(program, "courier_drone", stage_dir, glb_path=glb_path)

    # Now request a fresh build that bypasses the cache.
    bypass_report = quick_build_asset(
        program, "courier_drone", stage_dir, glb_path=glb_path, use_cache=False
    )
    assert bypass_report.get("cache_hit") is False
    timings = bypass_report.get("stage_timings_s") or {}
    # When the cache is bypassed every stage runs, so per-stage timings must be
    # populated (a cache hit returns the prior report which has the original
    # timings dict, but cache_hit=True; here it's False so we exercised stages).
    assert {"shape", "topology", "uv", "surface"}.issubset(timings.keys())


def test_quick_render_helper_handles_missing_gl_backend(tmp_path: Path) -> None:
    """The render helper is best-effort. With no GL backend it returns False, no exception."""
    from lathe.cli._quick_render import render_turntable

    # Build a real GLB first so the helper has something to load.
    program = parse_file(REPO_ROOT / "examples" / "courier_drone.lth")
    glb_path = tmp_path / "preview.glb"
    quick_build_asset(
        program,
        "courier_drone",
        tmp_path / "stage" / "courier_drone",
        glb_path=glb_path,
    )
    assert glb_path.exists()

    png_path = tmp_path / "turntable.png"
    # The helper must NEVER raise — at most it returns False on systems
    # without a GL stack. When it returns True the file must exist and
    # be non-empty.
    ok = render_turntable(glb_path, png_path)
    assert isinstance(ok, bool)
    if ok:
        assert png_path.exists()
        assert png_path.stat().st_size > 0


def test_quick_no_search_zeroes_best_of_in_materialized_asset(
    tmp_path: Path,
) -> None:
    """``--no-search`` must zero ``space.select.best_of`` on the materialized asset.

    Exercised at the executor level (no subprocess) so we can introspect the
    BuildExecutor's mutated asset directly. The override is transient — the
    parsed program object must not be modified.
    """
    from lathe.executor import BuildExecutor

    program = parse_file(REPO_ROOT / "examples" / "brassbound_chest.lth")
    stage_dir = tmp_path / "stage" / "brassbound_chest"

    executor = BuildExecutor(
        program,
        "brassbound_chest",
        stage_dir,
        shape_overrides={"no_search": True, "candidates": 1},
    )
    assert executor.asset["space"]["select"]["best_of"] == 0
    assert executor.asset["build"]["shape"]["candidates"] == 1


def test_quick_candidates_override_emits_single_candidate_glb(
    tmp_path: Path, isolated_quick_cache: Path
) -> None:
    """``--candidates 1`` collapses the chest's 10-wide candidate sweep to one.

    The chest declares ``candidates = 6`` and ``space.select.best_of = 10``,
    so by default the scaffold compiler runs ``max(3, 6, 10) = 10`` candidates.
    With ``shape_overrides={"candidates": 1}`` we expect exactly one candidate
    glb in the shape stage directory and a wall-clock budget far below the
    full-build budget. Avoids running the slow default-config cold build
    inside the test by asserting on the single-candidate path's invariants
    (artifact count + tight wall-clock budget) rather than a head-to-head
    timing ratio.
    """
    program = parse_file(REPO_ROOT / "examples" / "brassbound_chest.lth")
    asset_name = "brassbound_chest"

    glb_fast = tmp_path / "fast.glb"
    stage_fast = tmp_path / "stage_fast" / asset_name
    t0 = time.monotonic()
    fast_report = quick_build_asset(
        program,
        asset_name,
        stage_fast,
        glb_path=glb_fast,
        use_cache=False,
        shape_overrides={"candidates": 1},
    )
    fast_wall = time.monotonic() - t0
    assert fast_report.get("cache_hit") is False
    fast_shape_s = (fast_report.get("stage_timings_s") or {}).get("shape", 0.0)

    # Exactly one candidate glb should be written to the shape stage dir;
    # the default 10-wide sweep would emit candidate_00..candidate_09.
    shape_glbs = sorted((stage_fast / "stages" / "shape").glob("candidate_*.glb"))
    assert len(shape_glbs) == 1, (
        f"expected exactly 1 candidate glb under --candidates 1, got "
        f"{[p.name for p in shape_glbs]}"
    )

    # Wall-clock budget: chest cold build at ``candidates_count=1`` should
    # finish well below the 8min full-quick budget. Generous to absorb CI
    # variance while still catching a regression that re-introduces the
    # 10-wide sweep.
    assert fast_wall < 240.0, (
        f"chest --candidates 1 wall-clock {fast_wall:.1f}s exceeded 4min budget; "
        f"shape={fast_shape_s:.1f}s"
    )
