from __future__ import annotations

import json
from pathlib import Path

from lathe.checker import check_program
from lathe.parser import parse_file
from lathe.scene import (
    load_and_check_scene_graph,
    materialize_scene_assets,
    plan_scene,
    render_stdlib_catalog_markdown,
    run_scene_validators,
    stdlib_catalog,
    stdlib_component_ids,
    stdlib_showcase_scene_graph,
    validate_scene_materialization_manifest_payload,
    validate_scene_plan_payload,
    validate_stdlib_catalog,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

PHASE_25_COMPONENT_IDS = {
    "architecture_wall",
    "architecture_floor",
    "architecture_ceiling",
    "architecture_arch",
    "architecture_column",
    "architecture_stair",
    "architecture_door",
    "architecture_window",
    "architecture_bridge",
    "architecture_railing",
    "architecture_platform",
    "architecture_tunnel",
    "architecture_room_shell",
    "dressing_crate",
    "dressing_barrel",
    "dressing_book",
    "dressing_candle",
    "dressing_chain",
    "dressing_pipe",
    "dressing_vent",
    "dressing_panel",
    "dressing_debris",
    "dressing_rug",
    "dressing_banner",
    "dressing_sign",
    "natural_rock",
    "natural_root",
    "natural_vine",
    "natural_crystal",
    "natural_mushroom",
    "natural_dead_tree",
    "natural_bone",
    "natural_coral_form",
    "natural_terrain_chunk",
    "hero_altar",
    "hero_machine",
    "hero_console",
    "hero_relic",
    "hero_portal",
    "hero_vehicle",
    "hero_weapon",
    "hero_tool",
    "hero_furniture",
    "light_torch",
    "light_lamp",
    "light_neon_tube",
    "light_moon_window",
    "light_glowing_crystal",
    "light_hologram",
}


def test_wonder_stdlib_catalog_covers_phase_25_component_vocabulary() -> None:
    catalog = stdlib_catalog()
    component_ids = set(stdlib_component_ids())

    assert validate_stdlib_catalog(catalog) == []
    assert component_ids == PHASE_25_COMPONENT_IDS
    assert catalog["summary"] == {
        "components": len(PHASE_25_COMPONENT_IDS),
        "categories": [
            "architecture",
            "environmental_dressing",
            "hero_prop",
            "lighting_fixture",
            "natural_form",
        ],
        "materials": 5,
    }
    assert all(component["readiness"]["mesh_runtime"] == "not_claimed" for component in catalog["components"])
    assert all(component["source_kit"] for component in catalog["components"] if component["kind"] == "kit")
    assert all("source_kit" not in component for component in catalog["components"] if component["kind"] == "family")


def test_wonder_stdlib_showcase_scene_validates_and_plans_every_component(tmp_path: Path) -> None:
    scene_graph = stdlib_showcase_scene_graph()
    scene_path = tmp_path / "scene_graph.json"
    scene_path.write_text(json.dumps(scene_graph, indent=2) + "\n", encoding="utf-8")

    loaded, diagnostics = load_and_check_scene_graph(scene_path)
    validator_report = run_scene_validators(loaded, root=tmp_path)
    scene_plan = plan_scene(loaded)

    assert diagnostics == []
    assert validator_report["status"] == "passed"
    assert validate_scene_plan_payload(scene_plan) == []
    assert set(scene_plan["metadata"]["counts"]) >= {"objects", "asset_tasks", "render_tasks"}
    assert scene_plan["metadata"]["counts"]["objects"] == len(PHASE_25_COMPONENT_IDS)
    assert scene_plan["metadata"]["counts"]["asset_tasks"] == len(PHASE_25_COMPONENT_IDS)


def test_wonder_stdlib_showcase_materializes_to_checkable_lathe_asset_sources(tmp_path: Path) -> None:
    scene_path = tmp_path / "scene_graph.json"
    scene_path.write_text(json.dumps(stdlib_showcase_scene_graph(), indent=2) + "\n", encoding="utf-8")

    result = materialize_scene_assets(scene_path, tmp_path / "materialized")
    manifest = result["manifest"]

    assert result["ok"] is True
    assert validate_scene_materialization_manifest_payload(manifest) == []
    assert manifest["summary"]["source_files"] == len(PHASE_25_COMPONENT_IDS)
    assert manifest["summary"]["checker_errors"] == 0
    assert manifest["summary"]["planner_errors"] == 0


def test_checked_in_std_lth_files_parse_and_check() -> None:
    std_files = sorted((REPO_ROOT / "std").rglob("*.lth"))

    assert std_files
    for path in std_files:
        program = parse_file(path)
        errors = [diagnostic for diagnostic in check_program(program) if diagnostic.get("severity") == "error"]

        assert errors == [], path


def test_wonder_stdlib_catalog_docs_are_in_sync() -> None:
    rendered = render_stdlib_catalog_markdown()
    committed = (REPO_ROOT / "docs" / "wonder-readiness" / "21_stdlib_catalog.md").read_text(encoding="utf-8")

    assert rendered in committed
    for component_id in PHASE_25_COMPONENT_IDS:
        assert f"`{component_id}`" in committed
