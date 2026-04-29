from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
from lathe.scene.assembly import (
    assemble_scene,
    contact_hints_for_bounds,
    convert_vector_units,
    estimate_transform_bounds,
    get_scene_assembly_schema,
    transform_position,
    transform_scale,
    validate_scene_assembly_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _by_object_id(records: list[dict], object_id: str) -> dict:
    return next(record for record in records if record["object_id"] == object_id)


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def test_scene_assembly_schema_is_valid_json_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(get_scene_assembly_schema())


def test_assemble_scene_preserves_object_id_metadata_and_schema_validates() -> None:
    scene_graph = _scene()

    assembly = assemble_scene(scene_graph)

    assert validate_scene_assembly_payload(assembly, package_root=EXAMPLE_SCENE.parent) == []
    assert assembly["schema_version"] == "lathe.scene_assembly.v1"
    assert assembly["scene_id"] == "alchemist_observatory"
    assert assembly["metadata"]["runtime"] == "deferred_proxy"
    astrolabe = _by_object_id(assembly["objects"], "obj_astrolabe_table_001")
    assert astrolabe["metadata"]["object_id"] == "obj_astrolabe_table_001"
    assert astrolabe["metadata"]["region_id"] == "region_central_chamber"
    assert astrolabe["metadata"]["source"]["lathe_asset"] == "astrolabe_table"
    assert astrolabe["metadata"]["material_ids"] == ["mat_oxidized_brass", "mat_black_glass"]
    assert astrolabe["metadata"]["surface_overrides"] == {}
    assert astrolabe["metadata"]["instancing"]["schema_version"] == "lathe.scene_instancing_metadata.v1"
    assert astrolabe["metadata"]["instancing"]["reuse_group_id"].startswith("reuse_group_astrolabe_table_")
    assert astrolabe["metadata"]["instancing"]["instance_override_fields"] == [
        "name",
        "role",
        "region",
        "transform",
        "semantic_tags",
        "state",
        "surface_overrides",
        "affordances",
        "provenance",
    ]
    assert astrolabe["planned_artifacts"]["asset_proxy"].startswith("build/objects/obj_astrolabe_table_001/")


def test_assemble_scene_preserves_object_transforms() -> None:
    scene_graph = _scene()

    assembly = assemble_scene(scene_graph)

    for source_object in scene_graph["objects"]:
        assembled_object = _by_object_id(assembly["objects"], source_object["object_id"])
        assert assembled_object["transform"] == source_object["transform"]


def test_transform_math_and_unit_helpers_are_deterministic() -> None:
    transform = {
        "position": [1, 2.5, 0.75],
        "rotation": [0, 0, 45],
        "scale": [2, -3, 0.5],
    }

    bounds = estimate_transform_bounds(transform, base_size=[1, 2, 4])

    assert transform_position(transform) == [1.0, 2.5, 0.75]
    assert transform_scale(transform) == [2.0, 3.0, 0.5]
    assert bounds == {
        "center": [1.0, 2.5, 0.75],
        "size": [2.0, 6.0, 2.0],
    }
    assert contact_hints_for_bounds(bounds) == {
        "estimated_bottom_z": -0.25,
        "floor_clearance": -0.25,
        "rests_on_floor": True,
        "nearest_resting_surface": "floor",
    }
    assert convert_vector_units([1.0, 0.28, 2.8], from_units="meters", to_units="studs") == [
        3.571429,
        1.0,
        10.0,
    ]


def test_assemble_scene_adds_bounds_contact_hints_and_units() -> None:
    assembly = assemble_scene(_scene())
    astrolabe = _by_object_id(assembly["objects"], "obj_astrolabe_table_001")

    assert assembly["metadata"]["units"] == {
        "scene": "meters",
        "supported_linear_units": ["centimeters", "meters", "millimeters", "studs"],
    }
    assert astrolabe["bounds"] == {
        "center": [0.0, 0.0, 0.75],
        "size": [1.4, 1.4, 1.0],
    }
    assert astrolabe["contact_hints"] == {
        "estimated_bottom_z": 0.25,
        "floor_clearance": 0.25,
        "rests_on_floor": True,
        "nearest_resting_surface": "floor",
    }
    assert validate_scene_assembly_payload(assembly, package_root=EXAMPLE_SCENE.parent) == []


def test_object_index_is_deterministic_when_scene_graph_object_order_changes() -> None:
    scene_graph = _scene()
    reordered = copy.deepcopy(scene_graph)
    reordered["objects"] = list(reversed(reordered["objects"]))

    original = assemble_scene(scene_graph)
    changed_order = assemble_scene(reordered)

    assert original["object_index"] == changed_order["object_index"]
    assert [item["object_id"] for item in original["object_index"]] == sorted(
        item["object_id"] for item in scene_graph["objects"]
    )
    assert [item["render_index"] for item in original["object_index"]] == [1, 2, 3, 4]
    assert original["object_selection_payloads"] == changed_order["object_selection_payloads"]


def test_validate_scene_assembly_reports_duplicate_render_ids() -> None:
    assembly = assemble_scene(_scene())
    assembly["cameras"][1]["planned_renders"][0]["render_id"] = assembly["cameras"][0]["planned_renders"][0]["render_id"]

    diagnostics = validate_scene_assembly_payload(assembly, package_root=EXAMPLE_SCENE.parent)

    assert "SA3003" in _codes(diagnostics)
    duplicate = next(diagnostic for diagnostic in diagnostics if diagnostic["code"] == "SA3003")
    assert duplicate["path"] == "/cameras/1/planned_renders/0/render_id"
