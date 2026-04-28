from __future__ import annotations

import json
import os
from pathlib import Path

from lathe.hero_manifest import HEROES
from scripts import profile_heroes

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "perf" / "manifest.json"
DOC_PATH = REPO_ROOT / "docs" / "perf_budgets.md"
BENCHMARK_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "benchmarks.yml"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_perf_manifest_covers_every_common_hero_build() -> None:
    manifest = _load_manifest()
    manifest_heroes = manifest["heroes"]
    hero_names = {hero.asset_name for hero in HEROES}

    assert set(manifest_heroes) == hero_names
    for hero in HEROES:
        entry = manifest_heroes[hero.asset_name]
        assert isinstance(entry["total_ms_max"], int)
        assert entry["total_ms_max"] > 0
        assert set(entry["stages"]) == set(profile_heroes.STAGE_ORDER)
        for stage, budget in entry["stages"].items():
            assert isinstance(budget["ms_max"], int), stage
            assert 0 < budget["ms_max"] <= entry["total_ms_max"], stage


def test_manifest_gate_reports_pass_warn_fail_skip_and_total_rows() -> None:
    manifest = {
        "heroes": {
            "demo": {
                "total_ms_max": 100,
                "stages": {
                    "shape": {"ms_max": 10},
                    "topology": {"ms_max": 20},
                    "surface": {"ms_max": 30},
                },
            }
        }
    }
    current = {
        "wall_ms": 105,
        "stages": {
            "shape": {"current_ms": 5},
            "topology": {"current_ms": 19},
            "surface": {"current_ms": 31},
            "uv": {"current_ms": 2},
        },
    }

    rows = profile_heroes._manifest_rows("demo", current, manifest)
    statuses = {row["stage"]: row["status"] for row in rows}

    assert statuses["shape"] == "pass"
    assert statuses["topology"] == "warn"
    assert statuses["surface"] == "fail"
    assert statuses["uv"] == "skip"
    assert statuses["__total__"] == "fail"


def test_mtime_fallback_skips_cached_artifacts_with_stale_timestamps(tmp_path: Path) -> None:
    shape_dir = tmp_path / "stages" / "shape"
    topology_dir = tmp_path / "stages" / "topology"
    shape_dir.mkdir(parents=True)
    topology_dir.mkdir(parents=True)
    shape_bundle = shape_dir / "bundle.json"
    topology_bundle = topology_dir / "bundle.json"
    shape_bundle.write_text("{}", encoding="utf-8")
    topology_bundle.write_text("{}", encoding="utf-8")
    os.utime(shape_bundle, (1_000.0, 1_000.0))
    os.utime(topology_bundle, (1_001.0, 1_001.0))

    timings = profile_heroes._per_stage_timings(
        {},
        tmp_path,
        build_started_wall_s=2_000.0,
        build_finished_wall_s=2_001.0,
    )

    assert timings["shape"] == {
        "current_ms": None,
        "source": "mtime_delta_untrusted_cache_mtime",
    }
    assert timings["topology"] == {
        "current_ms": None,
        "source": "mtime_delta_untrusted_cache_mtime",
    }


def test_perf_docs_describe_the_manifest_gate_and_common_builds() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")

    assert "perf/manifest.json" in doc
    assert "scripts/profile_heroes.py --manifest" in doc
    assert "fail" in doc
    for hero in HEROES:
        assert hero.asset_name in doc or "all heroes" in doc


def test_benchmark_workflow_runs_the_hero_performance_manifest_gate() -> None:
    workflow = BENCHMARK_WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/profile_heroes.py --manifest" in workflow
    assert "--out-root tmp_perf_manifest" in workflow
