from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from lathe.scene import (
    environment_module_catalog,
    environment_module_ids,
    environment_module_showcase_scene_graph,
    load_and_assemble_scene_graph,
    load_and_check_scene_graph,
    materialize_scene_assets,
    plan_layout,
    render_environment_module_docs,
    run_scene_validators,
    validate_environment_module_scene,
    validate_layout_plan_payload,
    validate_scene_assembly_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_ENVIRONMENT_MODULES = {
    "env_room_shell",
    "env_floor_tile",
    "env_wall_segment",
    "env_ceiling_segment",
    "env_arch_segment",
    "env_platform_module",
    "env_stair_module",
    "env_background_silhouette",
    "env_terrain_chunk",
}


def _write_scene(path: Path, scene_graph: dict) -> Path:
    path.write_text(json.dumps(scene_graph, indent=2) + "\n", encoding="utf-8")
    return path


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def test_environment_module_catalog_covers_phase_26_module_vocabulary() -> None:
    catalog = environment_module_catalog()

    assert set(environment_module_ids()) == EXPECTED_ENVIRONMENT_MODULES
    assert catalog["summary"] == {
        "modules": 9,
        "snap_profiles": ["grid_1m", "grid_2m"],
        "boundary_modules": 1,
    }
    assert all(module["readiness"]["mesh_runtime"] == "not_claimed" for module in catalog["modules"])
    assert all(module["snap_point_count"] > 0 for module in catalog["modules"])


def test_environment_module_showcase_scene_validates_layout_and_assembly(tmp_path: Path) -> None:
    scene_path = _write_scene(tmp_path / "scene_graph.json", environment_module_showcase_scene_graph())

    scene_graph, diagnostics = load_and_check_scene_graph(scene_path)
    layout_plan = plan_layout(scene_graph)
    validator_report = run_scene_validators(scene_graph, root=tmp_path)
    assembly = load_and_assemble_scene_graph(scene_path)

    assert diagnostics == []
    assert validate_environment_module_scene(scene_graph) == []
    assert validate_layout_plan_payload(layout_plan) == []
    assert layout_plan["wall_segments"]
    assert all(segment["aligned_to_grid"] is True for segment in layout_plan["wall_segments"])
    assert validator_report["status"] == "passed"
    assert validator_report["diagnostics"] == []
    assert validate_scene_assembly_payload(assembly) == []


def test_environment_module_showcase_materializes_to_env_module_sources(tmp_path: Path) -> None:
    scene_path = _write_scene(tmp_path / "scene_graph.json", environment_module_showcase_scene_graph())

    result = materialize_scene_assets(scene_path, tmp_path / "materialized")
    manifest = result["manifest"]

    assert result["ok"] is True
    assert manifest["summary"]["source_files"] == len(EXPECTED_ENVIRONMENT_MODULES)
    assert {entry["asset_kind"] for entry in manifest["asset_sources"]} == {"env_module"}
    assert manifest["summary"]["checker_errors"] == 0
    assert manifest["summary"]["planner_errors"] == 0


def test_environment_validator_reports_missing_boundary_shell_and_off_grid_module() -> None:
    scene_graph = environment_module_showcase_scene_graph()
    scene_graph["objects"] = [
        item for item in scene_graph["objects"] if "scene_boundary" not in item["semantic_tags"]
    ]
    scene_graph["objects"][0]["transform"]["position"][0] = 0.5

    diagnostics = validate_environment_module_scene(scene_graph)

    assert {"EV2001", "EV2003"} <= _codes(diagnostics)


def test_environment_validator_reports_missing_snap_points() -> None:
    scene_graph = environment_module_showcase_scene_graph()
    scene_graph["objects"][0]["state"]["snap_point_count"] = 0

    diagnostics = validate_environment_module_scene(scene_graph)

    assert "EV2002" in _codes(diagnostics)


def test_environment_module_validation_is_opt_in_for_non_module_scenes() -> None:
    scene_graph = deepcopy(environment_module_showcase_scene_graph())
    for item in scene_graph["objects"]:
        item["semantic_tags"] = [tag for tag in item["semantic_tags"] if tag != "env_module"]

    assert validate_environment_module_scene(scene_graph) == []


def test_environment_module_docs_are_in_sync() -> None:
    docs = (REPO_ROOT / "docs" / "wonder-readiness" / "23_environment_modules.md").read_text(encoding="utf-8")

    assert render_environment_module_docs() == docs
