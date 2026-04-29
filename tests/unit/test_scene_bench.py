from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
from lathe.scene.bench import (
    SCORE_THRESHOLDS,
    STAGE_BUDGETS,
    benchmark_scene,
    get_scene_benchmark_report_schema,
    validate_scene_benchmark_report_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_PATH = REPO_ROOT / "benchmarks" / "wonder" / "prompts.json"
WONDER_BENCHMARK_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "wonder-benchmarks.yml"
WONDER_BENCHMARK_SCRIPT = REPO_ROOT / "scripts" / "ci_wonder_benchmarks.py"


def _object(object_id: str, lathe_asset: str, *, x: int = 0) -> dict:
    return {
        "object_id": object_id,
        "name": object_id.replace("obj_", "").replace("_", " ").title(),
        "role": "dressing_prop",
        "region": "region_main",
        "lathe_asset": lathe_asset,
        "transform": {"position": [x, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
        "material_bindings": [{"slot": "body", "material": "mat_stone_001"}],
        "state": {"lit": True},
    }


def _scene() -> dict:
    return {
        "schema_version": "lathe.scene_graph.v1",
        "scene_id": "bench_scene",
        "version": 1,
        "regions": [{"region_id": "region_main", "name": "Main"}],
        "objects": [
            _object("obj_lantern_001", "shared_lantern", x=0),
            _object("obj_lantern_002", "shared_lantern", x=2),
            _object("obj_gate_001", "moon_gate", x=4),
        ],
        "materials": [{"material_id": "mat_stone_001", "name": "Stone"}],
        "lights": [{"light_id": "light_key_001"}],
        "cameras": [{"camera_id": "camera_reveal_001", "target": "obj_gate_001"}],
        "curiosity_anchors": [],
        "hidden_state": [],
        "exports": [{"target": "glb", "format": "glb", "path": "exports/bench_scene.glb"}],
    }


def _passing_timings() -> dict:
    return {
        "stages": {
            "final_export": {"duration_ms": 120_000},
            "patch_preview": {"duration_ms": 30_000},
            "preview_render": {"duration_ms": 20_000},
            "preview_build": {"duration_ms": 50_000},
            "check_plan": {"duration_ms": 4_000},
            "source_generation": {"duration_ms": 8_000},
            "scene_graph": {"duration_ms": 18_000},
            "brief": {"duration_ms": 8_000},
        },
        "cache": {"hits": 2, "misses": 2, "writes": 1},
    }


def _passing_scores() -> dict:
    return {
        "metrics": {
            "export_validity": True,
            "continuity_preservation": 0.9,
            "patch_success": True,
            "render_quality": 0.82,
            "object_count_accuracy": 0.9,
            "style_consistency": 0.85,
            "scene_validation": 0.9,
            "build_success": True,
            "parse_check": True,
            "brief_to_scene": 0.88,
            "prompt_to_brief": 0.9,
        }
    }


def test_benchmark_scene_reports_pass_and_fail_thresholds() -> None:
    passing = benchmark_scene(_scene(), _passing_timings(), _passing_scores())

    assert passing["status"] == "passed"
    assert passing["summary"]["timings"] == {"passed": 8, "failed": 0, "missing": 0, "excepted": 0}

    timings = _passing_timings()
    timings["stages"]["preview_render"] = {"duration_ms": 30_001}
    failing = benchmark_scene(_scene(), timings, _passing_scores())
    preview_render = next(item for item in failing["stage_results"] if item["stage"] == "preview_render")

    assert failing["status"] == "failed"
    assert preview_render["status"] == "failed"
    assert preview_render["budget_ms"] == 30_000


def test_benchmark_scene_reports_cache_reuse_metric() -> None:
    report = benchmark_scene(_scene(), _passing_timings(), _passing_scores())

    assert report["cache_reuse"]["hits"] == 2
    assert report["cache_reuse"]["eligible"] == 4
    assert report["cache_reuse"]["reuse_ratio"] == 0.5
    assert report["cache_reuse"]["status"] == "passed"
    assert report["cache_reuse"]["potential"]["reusable_objects"] == 1
    assert report["cache_reuse"]["potential"]["potential_reuse_ratio"] == 0.3333

    timings = _passing_timings()
    timings["cache"] = {"hits": 0, "misses": 4, "writes": 3}
    failing = benchmark_scene(_scene(), timings, _passing_scores())

    assert failing["cache_reuse"]["status"] == "failed"
    assert failing["status"] == "failed"


def test_final_export_allowed_exception_is_explicit() -> None:
    timings = _passing_timings()
    timings["stages"].pop("final_export")
    timings["final_export_exception"] = "external_exporter_unavailable"

    report = benchmark_scene(_scene(), timings, _passing_scores())
    final_export = next(item for item in report["stage_results"] if item["stage"] == "final_export")

    assert report["status"] == "passed_with_exceptions"
    assert final_export["status"] == "excepted"
    assert final_export["exception"] == "external_exporter_unavailable"
    assert validate_scene_benchmark_report_payload(report) == []


def test_benchmark_scene_uses_deterministic_result_ordering() -> None:
    report = benchmark_scene(_scene(), _passing_timings(), _passing_scores())
    reordered = benchmark_scene(deepcopy(_scene()), deepcopy(_passing_timings()), deepcopy(_passing_scores()))

    assert [item["stage"] for item in report["stage_results"]] == [budget.stage for budget in STAGE_BUDGETS]
    assert [item["metric"] for item in report["score_results"]] == list(SCORE_THRESHOLDS)
    assert json.dumps(report, sort_keys=True) == json.dumps(reordered, sort_keys=True)


def test_scene_benchmark_report_schema_validates_report() -> None:
    schema = get_scene_benchmark_report_schema()
    report = benchmark_scene(_scene(), _passing_timings(), _passing_scores())

    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(report)
    assert validate_scene_benchmark_report_payload(report) == []


def test_wonder_prompt_corpus_contains_the_phase_31_prompts() -> None:
    corpus = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    expected_ids = [
        "alchemist_observatory",
        "mountain_lightning_city",
        "abandoned_roblox_mall",
        "underwater_train_station",
        "desert_oracle_shrine",
        "cozy_witch_greenhouse",
        "cyberpunk_noodle_alley",
        "ancient_moon_elevator",
        "horror_obby_lobby",
        "luxury_tycoon_showroom",
    ]

    assert corpus["schema_version"] == "lathe.wonder_benchmark_prompts.v1"
    assert [item["id"] for item in corpus["prompts"]] == expected_ids
    for prompt in corpus["prompts"]:
        assert len(prompt["style_variations"]) == 3
        assert len(prompt["patch_operations"]) == 3


def test_wonder_benchmark_nightly_workflow_runs_benchmark_lane() -> None:
    workflow = WONDER_BENCHMARK_WORKFLOW.read_text(encoding="utf-8")
    script = WONDER_BENCHMARK_SCRIPT.read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "python scripts/ci_wonder_benchmarks.py" in workflow
    assert "scene_benchmark_report.json" in workflow
    assert "tests/unit/test_scene_bench.py" in script
    assert "validate-scene-benchmark-report" in script
