from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from lathe.scene.executor import build_scene_preview
from lathe.wonder import (
    build_alpha_gate_report,
    build_evidence_trace,
    catalog_wonder_examples,
    generate_scene_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_ROOT = REPO_ROOT / "tests" / "snapshots" / "wonder"
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"

pytestmark = pytest.mark.golden


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _snapshot(name: str) -> dict[str, Any]:
    return _read_json(SNAPSHOT_ROOT / name)


def _scene_plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": plan["schema_version"],
        "plan_id": plan["plan_id"],
        "scene_id": plan["scene_id"],
        "source_brief_id": plan["source_brief_id"],
        "counts": plan["metadata"]["counts"],
        "asset_task_ids": [task["task_id"] for task in plan["asset_tasks"]],
        "render_task_ids": [task["task_id"] for task in plan["render_tasks"]],
        "export_task_ids": [task["task_id"] for task in plan["export_tasks"]],
    }


def _scene_manifest_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest["schema_version"],
        "scene_id": manifest["scene_id"],
        "mode": manifest["mode"],
        "status": manifest["status"],
        "offline": manifest["offline"],
        "executor": manifest["build_options"]["executor"],
        "runtime": manifest["build_options"]["runtime"],
        "object_ids": [item["object_id"] for item in manifest["objects"]],
        "planned_render_task_ids": [item["task_id"] for item in manifest["planned_renders"]],
        "built_render_pairs": [
            [item["camera_id"], item["render_pass"], item["status"]] for item in manifest["built_renders"]
        ],
        "planned_export_task_ids": [item["task_id"] for item in manifest["planned_exports"]],
        "built_export_targets": [
            [item["target"], item["format"], item["status"]] for item in manifest["built_exports"]
        ],
        "quality_status": manifest["quality"]["status"],
        "quality_score": manifest["quality"]["score"],
        "diagnostic_summary": manifest["quality"]["summary"],
    }


def _scene_build_report_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report["schema_version"],
        "scene_id": report["scene_id"],
        "mode": report["mode"],
        "status": report["status"],
        "executor": report["build_options"]["executor"],
        "runtime": report["build_options"]["runtime"],
        "artifact_keys": sorted(report["artifacts"]),
        "counts": report["counts"],
        "quality": report["quality"],
        "asset_task_ids": [item["task_id"] for item in report["asset_build_reports"]],
        "asset_statuses": sorted({item["status"] for item in report["asset_build_reports"]}),
        "cache_reuse": report["cache_reuse"],
        "asset_materialization": report["asset_materialization"],
        "provider_fallback_trace": report["provider_fallback_trace"],
        "diagnostics": report["diagnostics"],
    }


def _alpha_gate_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report["schema_version"],
        "core_alpha_gate": report["core_alpha_gate"],
        "blocking_missing_runtimes": report["blocking_missing_runtimes"],
        "alpha_decision_ready": report["alpha_decision_ready"],
        "remaining_human_decision": report["remaining_human_decision"],
        "optional_lane_keys": sorted(report["optional_lanes"]),
        "lane_ids": [lane["id"] for lane in report["lanes"]],
        "report_bundle_keys": sorted(report["report_bundle"]),
        "non_runtime_deferred_lane_names": sorted(
            {
                lane["lane"]
                for lane in report["known_deferred_lanes"]
                if lane["lane"] in {"human_alpha_decision", "scene_source"}
            }
        ),
        "example_catalog_summary": report["reports"]["example_catalog_summary"],
    }


def _example_catalog_summary(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": catalog["schema_version"],
        "summary": catalog["summary"],
        "examples": [
            {
                "name": item["name"],
                "status": item["status"],
                "scene_source": item["scene_source"],
                "preview_evidence": item["preview_evidence"],
                "deferred_lanes": item["deferred_lanes"],
            }
            for item in catalog["examples"]
        ],
    }


def _evidence_trace_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report["schema_version"],
        "ok": report["ok"],
        "status": report["status"],
        "summary": report["summary"],
        "coverage_texts": [item["text"] for item in report["coverage"]],
    }


def _render_comparison_summary(comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": comparison["schema_version"],
        "camera_lock_status": comparison["camera_lock_status"],
        "dimensions": comparison["dimensions"],
        "pixel_delta": comparison["pixel_delta"],
        "semantic_delta_status": comparison["semantic_delta"]["status"],
        "status": comparison["status"],
        "has_camera_hash": "camera_hash" in comparison,
    }


def test_generated_scene_plan_snapshot_is_stable() -> None:
    brief = _read_json(EXAMPLE_DIR / "dream_brief.json")
    scene_graph = _read_json(EXAMPLE_DIR / "scene_graph.json")
    plan = generate_scene_plan(brief, scene_graph=scene_graph)

    assert _scene_plan_summary(plan) == _snapshot("scene_plan.summary.json")


def test_scene_manifest_snapshot_is_stable(tmp_path: Path) -> None:
    build_scene_preview(EXAMPLE_DIR / "scene_graph.json", tmp_path / "dist_scene", deterministic=True, allow_fallback=True)
    manifest = _read_json(tmp_path / "dist_scene" / "alchemist_observatory" / "reports" / "scene_manifest.json")

    assert _scene_manifest_summary(manifest) == _snapshot("scene_manifest.summary.json")


def test_scene_build_report_snapshot_is_stable(tmp_path: Path) -> None:
    build_scene_preview(EXAMPLE_DIR / "scene_graph.json", tmp_path / "dist_scene", deterministic=True, allow_fallback=True)
    report = _read_json(tmp_path / "dist_scene" / "alchemist_observatory" / "reports" / "build_report.json")

    assert _scene_build_report_summary(report) == _snapshot("scene_build_report.summary.json")


def test_alpha_gate_snapshot_shape_is_stable(tmp_path: Path) -> None:
    report = build_alpha_gate_report(EXAMPLE_DIR, tmp_path / "alpha_gate")

    assert _alpha_gate_summary(report) == _snapshot("alpha_gate.summary.json")


def test_evidence_traceability_snapshot_shape_is_stable(tmp_path: Path) -> None:
    marker = tmp_path / "marker.json"
    marker.write_text("{}", encoding="utf-8")
    tasks_path = tmp_path / "wonder-tasks.md"
    evidence_path = tmp_path / "evidence.md"
    tasks_path.write_text("# Tasks\n\n- [x] Run snapshot command.\n", encoding="utf-8")
    evidence_path.write_text(
        "# Evidence\n\n"
        "| Date | Task | Type | Command | Output | Status | Result |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        f"| 2026-04-29 | Run snapshot command. | command | `python -m pytest` | {marker} | passed | Passed. |\n",
        encoding="utf-8",
    )

    report = build_evidence_trace(tasks_path, evidence_path, repo_root=tmp_path)

    assert _evidence_trace_summary(report) == _snapshot("evidence_traceability.summary.json")


def test_example_catalog_snapshot_is_stable() -> None:
    catalog = catalog_wonder_examples(REPO_ROOT / "examples" / "wonder")

    assert _example_catalog_summary(catalog) == _snapshot("example_catalog.summary.json")


def test_render_comparison_snapshot_is_stable() -> None:
    comparison = _read_json(EXAMPLE_DIR / "expected" / "render_comparison.example.json")

    assert _render_comparison_summary(comparison) == _snapshot("render_comparison.summary.json")
