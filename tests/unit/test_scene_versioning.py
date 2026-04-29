from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
from lathe.scene.graph import check_scene_graph
from lathe.scene.versioning import (
    create_branch,
    diff_scene_graphs,
    get_scene_branch_schema,
    get_scene_diff_schema,
    merge_scene_graphs,
    validate_scene_branch_payload,
    validate_scene_diff_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def _star_silver_material() -> dict:
    return {
        "material_id": "mat_star_silver",
        "name": "Star Silver",
        "role": "mechanisms",
        "palette_refs": ["lunar blue"],
        "pbr": {
            "basecolor": "#c7d8ff",
            "metallic": 0.75,
            "roughness": 0.28,
        },
    }


def _star_map_object() -> dict:
    return {
        "object_id": "obj_star_map_001",
        "name": "Folded Star Map",
        "role": "narrative_clue",
        "region": "region_central_chamber",
        "lathe_asset": "folded_star_map",
        "transform": {
            "position": [1.2, 0.4, 0.82],
            "rotation": [0, 0, 12],
            "scale": [0.6, 0.6, 0.6],
        },
        "material_bindings": [{"slot": "paper", "material": "mat_star_silver"}],
        "semantic_tags": ["map", "constellation", "clue"],
        "state": {"revealed": False},
        "affordances": [],
        "provenance": {
            "source": "deterministic_lathe",
            "commercial_use": True,
        },
    }


def test_scene_branch_and_diff_schemas_are_valid_json_schemas() -> None:
    jsonschema.Draft202012Validator.check_schema(get_scene_branch_schema())
    jsonschema.Draft202012Validator.check_schema(get_scene_diff_schema())


def test_create_branch_payload_has_stable_ids_and_parent_reference() -> None:
    scene_graph = _scene()

    branch = create_branch(scene_graph, "Archive Expansion")

    assert branch == create_branch(scene_graph, "Archive Expansion")
    assert validate_scene_branch_payload(branch) == []
    assert branch["schema_version"] == "lathe.scene_branch.v1"
    assert branch["branch_id"] == "archive_expansion"
    assert branch["parent_branch"] == "main"
    assert branch["versions"][0]["branch_id"] == "main"
    assert branch["versions"][1]["branch_id"] == "archive_expansion"
    assert branch["versions"][1]["parents"] == [branch["base_version_id"]]


def test_scene_branch_validation_reports_missing_parent_version() -> None:
    branch = create_branch(_scene(), "Archive Expansion")
    branch["versions"][1]["parents"] = ["version_missing_001"]

    diagnostics = validate_scene_branch_payload(branch)

    assert "SB1605" in _codes(diagnostics)


def test_diff_scene_graphs_reports_object_addition() -> None:
    left = _scene()
    right = copy.deepcopy(left)
    right["materials"].append(_star_silver_material())
    right["objects"].append(_star_map_object())

    diff = diff_scene_graphs(left, right)

    assert validate_scene_diff_payload(diff) == []
    assert diff["summary"]["objects_added"] == 1
    assert diff["summary"]["materials_added"] == 1
    added = [change for change in diff["changes"] if change["kind"] == "object_added"]
    assert len(added) == 1
    assert added[0]["entity_id"] == "obj_star_map_001"
    assert added[0]["right"]["object_id"] == "obj_star_map_001"


def test_diff_scene_graphs_reports_transform_material_and_state_changes() -> None:
    left = _scene()
    right = copy.deepcopy(left)
    right["objects"][0]["transform"]["position"] = [1, 0, 0.75]
    right["objects"][0]["material_bindings"][0]["material"] = "mat_bone_ivory"
    right["objects"][0]["state"]["powered"] = False

    diff = diff_scene_graphs(left, right)
    kinds = {change["kind"] for change in diff["changes"]}

    assert validate_scene_diff_payload(diff) == []
    assert "object_transform_changed" in kinds
    assert "object_material_changed" in kinds
    assert "object_state_changed" in kinds
    assert diff["summary"]["object_transform_changes"] == 1
    assert diff["summary"]["object_material_changes"] == 1
    assert diff["summary"]["object_state_changes"] == 1


def test_scene_diff_validation_reports_summary_mismatch() -> None:
    diff = diff_scene_graphs(_scene(), _scene())
    diff["summary"]["total_changes"] = 1

    diagnostics = validate_scene_diff_payload(diff)

    assert "SD1602" in _codes(diagnostics)


def test_merge_scene_graphs_applies_non_overlapping_object_material_state_changes() -> None:
    target = _scene()
    source = copy.deepcopy(target)
    source["materials"].append(_star_silver_material())
    source["objects"][0]["material_bindings"].append({"slot": "rune", "material": "mat_star_silver"})
    source["objects"][0]["state"]["ritual_charge"] = "high"
    source["objects"].append(_star_map_object())

    result = merge_scene_graphs(source, target)
    merged = result.scene_graph

    assert result.diagnostics == []
    assert check_scene_graph(merged, root=EXAMPLE_SCENE.parent) == []
    assert "mat_star_silver" in {material["material_id"] for material in merged["materials"]}
    assert "obj_star_map_001" in {item["object_id"] for item in merged["objects"]}
    assert merged["objects"][0]["state"]["ritual_charge"] == "high"
    assert {"slot": "rune", "material": "mat_star_silver"} in merged["objects"][0]["material_bindings"]
    assert {"kind": "object_added", "object_id": "obj_star_map_001"} in result.applied_changes


def test_merge_scene_graphs_reports_conflicts_and_preserves_target_values() -> None:
    target = _scene()
    source = copy.deepcopy(target)
    target["objects"][0]["transform"]["position"] = [2, 0, 0.75]
    source["objects"][0]["transform"]["position"] = [1, 0, 0.75]
    target["objects"][0]["material_bindings"][0]["material"] = "mat_black_glass"
    source["objects"][0]["material_bindings"][0]["material"] = "mat_bone_ivory"
    target["objects"][0]["state"]["powered"] = "target_power"
    source["objects"][0]["state"]["powered"] = False

    result = merge_scene_graphs(source, target)
    codes = _codes(result.diagnostics)

    assert {"SM1602", "SM1603", "SM1604"}.issubset(codes)
    assert result.scene_graph["objects"][0]["transform"]["position"] == [2, 0, 0.75]
    assert result.scene_graph["objects"][0]["material_bindings"][0]["material"] == "mat_black_glass"
    assert result.scene_graph["objects"][0]["state"]["powered"] == "target_power"


def test_merge_scene_graphs_preserves_stable_object_ids() -> None:
    target = _scene()
    source = copy.deepcopy(target)
    original_ids = [item["object_id"] for item in target["objects"]]
    source["materials"].append(_star_silver_material())
    source["objects"].append(_star_map_object())

    result = merge_scene_graphs(source, target)
    merged_ids = [item["object_id"] for item in result.scene_graph["objects"]]

    assert result.diagnostics == []
    assert merged_ids[: len(original_ids)] == original_ids
    assert merged_ids[-1] == "obj_star_map_001"
