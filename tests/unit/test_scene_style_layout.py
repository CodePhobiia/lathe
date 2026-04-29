from __future__ import annotations

from copy import deepcopy

import jsonschema
import pytest
from lathe.scene.camera_lighting import plan_camera_lighting, validate_camera_lighting
from lathe.scene.layout import (
    get_layout_plan_schema,
    plan_instance_reuse,
    plan_layout,
    validate_layout_plan_payload,
)
from lathe.scene.style import (
    apply_style_pack,
    builtin_style_pack_ids,
    extract_style_pack,
    get_builtin_style_pack,
    get_style_pack_schema,
    iter_builtin_style_packs,
    style_pack_fingerprint,
    validate_scene_style,
    validate_style_pack_payload,
)


def _transform(x: float, y: float, z: float = 0.5) -> dict:
    return {
        "position": [x, y, z],
        "rotation": [0, 0, 0],
        "scale": [1, 1, 1],
    }


def _object(
    object_id: str,
    *,
    x: float,
    y: float,
    lathe_asset: str = "shared_crate",
    source_family: str = "crate_family",
    state: dict | None = None,
    surface_overrides: dict | None = None,
    affordances: list[dict] | None = None,
) -> dict:
    return {
        "object_id": object_id,
        "name": object_id.replace("obj_", "").replace("_", " ").title(),
        "role": "dressing_prop",
        "region": "region_main",
        "lathe_asset": lathe_asset,
        "source_family": source_family,
        "variant": "small",
        "transform": _transform(x, y),
        "material_bindings": [{"slot": "body", "material": "mat_warm_clay"}],
        "semantic_tags": ["crate"],
        "state": state or {"open": False},
        "surface_overrides": surface_overrides or {},
        "affordances": affordances or [],
        "provenance": {"source": "deterministic_lathe", "commercial_use": True},
    }


def _scene(*, overlap: bool = False) -> dict:
    blocker_x = 0 if overlap else -2
    blocker_y = 0.25 if overlap else 1.8
    return {
        "schema_version": "lathe.scene_graph.v1",
        "scene_id": "style_layout_scene",
        "version": 1,
        "prompt": "A compact style and layout test scene.",
        "style_bible": {
            "mood": ["warm", "readable"],
            "palette": ["warm clay", "cool teal"],
            "materials": ["clay", "painted metal"],
            "forms": ["simple blocks"],
            "lighting": ["soft key"],
            "avoid": ["photoreal noise"],
        },
        "layout": {
            "room_size": [8, 8, 4],
            "main_path": {"from": "region_entry", "to": "obj_focus_001", "width": 1.0},
            "focal_point": "obj_focus_001",
            "density": "medium",
            "avoid_intersections": True,
        },
        "regions": [
            {
                "region_id": "region_main",
                "name": "Main",
                "type": "interior",
                "purpose": "Primary test area.",
                "mood": "warm",
                "bounds": {"center": [0, 0, 1], "size": [8, 8, 4]},
            },
            {
                "region_id": "region_entry",
                "name": "Entry",
                "type": "threshold",
                "purpose": "Path start.",
                "mood": "quiet",
                "bounds": {"center": [0, -3, 0.5], "size": [2, 1, 1]},
            },
        ],
        "objects": [
            _object("obj_focus_001", x=0, y=2, lathe_asset="focus_plinth", state={"open": False}),
            _object("obj_crate_001", x=blocker_x, y=blocker_y, state={"open": False}),
            _object("obj_crate_002", x=blocker_x, y=blocker_y if overlap else -1.5, state={"open": True}),
        ],
        "relationships": [],
        "materials": [
            {
                "material_id": "mat_warm_clay",
                "name": "Warm Clay",
                "role": "surface",
                "palette_refs": ["warm clay"],
                "pbr": {"basecolor": "#b36a45", "metallic": 0, "roughness": 0.7},
            }
        ],
        "lights": [
            {
                "light_id": "light_key_001",
                "type": "area",
                "target": "obj_focus_001",
                "color": "warm clay",
                "intensity": 0.8,
                "purpose": "Readable warm key light.",
            }
        ],
        "cameras": [
            {
                "camera_id": "camera_reveal",
                "target": "obj_focus_001",
                "framing": "cinematic_wide",
                "purpose": "Show the whole test space.",
                "transform": _transform(-4, -4, 2),
                "fov_degrees": 48,
            }
        ],
        "curiosity_anchors": [],
        "hidden_state": [],
        "exports": [],
        "build_artifacts": [],
        "memory_events": [],
    }


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def _without_source_index(records: list[dict]) -> list[dict]:
    return [{key: value for key, value in record.items() if key != "source_index"} for record in records]


def test_style_pack_and_layout_plan_schemas_are_valid_json_schemas() -> None:
    jsonschema.Draft202012Validator.check_schema(get_style_pack_schema())
    jsonschema.Draft202012Validator.check_schema(get_layout_plan_schema())


def test_extract_style_pack_is_schema_valid_and_fingerprint_is_strict() -> None:
    style_pack = extract_style_pack(_scene(), style_pack_id="warm_clay_style")

    assert validate_style_pack_payload(style_pack) == []
    assert style_pack["schema_version"] == "lathe.style_pack.v1"
    assert style_pack["style_bible"]["palette"] == ["warm clay", "cool teal"]
    assert style_pack["materials"][0]["material_id"] == "mat_warm_clay"

    changed = deepcopy(style_pack)
    changed["display_name"] = "Changed"
    assert "ST2002" in _codes(validate_style_pack_payload(changed))


def test_validate_scene_style_reports_missing_pack_coverage() -> None:
    style_pack = extract_style_pack(_scene())
    style_pack["palette"] = [token for token in style_pack["palette"] if token["name"] != "warm clay"]
    style_pack["style_bible"]["palette"].remove("warm clay")
    style_pack["metadata"]["fingerprint"] = "sha256:0000000000000000"

    diagnostics = validate_scene_style(_scene(), style_pack)

    assert {"ST2001", "ST2002", "ST3001", "ST3003"} <= _codes(diagnostics)


def test_apply_style_pack_replaces_bible_and_adds_missing_materials() -> None:
    scene_graph = _scene()
    style_pack = extract_style_pack(scene_graph)
    style_pack["style_bible"]["mood"] = ["cool"]
    style_pack["materials"].append(
        {
            "material_id": "mat_cool_teal",
            "name": "Cool Teal",
            "role": "surface",
            "palette_refs": ["cool teal"],
            "pbr": {"basecolor": "#4caaa0", "metallic": 0, "roughness": 0.5},
            "tags": [],
        }
    )

    applied = apply_style_pack(scene_graph, style_pack)

    assert applied["style_bible"]["mood"] == ["cool"]
    assert [material["material_id"] for material in applied["materials"]] == ["mat_cool_teal", "mat_warm_clay"]
    assert scene_graph["style_bible"]["mood"] == ["warm", "readable"]


def test_builtin_style_packs_are_schema_valid_and_fingerprinted() -> None:
    expected = {
        "cozy_fantasy_workshop",
        "dark_fantasy_ruin",
        "dead_god_observatory",
        "roblox_horror_lowpoly",
        "roblox_lowpoly_cute",
        "sci_fi_industrial",
    }

    assert set(builtin_style_pack_ids()) == expected
    packs = list(iter_builtin_style_packs())
    assert [pack["style_pack_id"] for pack in packs] == sorted(expected)

    for style_pack in packs:
        assert style_pack["schema_version"] == "lathe.style_pack.v1"
        assert style_pack["source"]["kind"] == "curated"
        assert style_pack["metadata"]["generated_by"] == "lathe.scene.style.builtin"
        assert style_pack["metadata"]["fingerprint"] == style_pack_fingerprint(style_pack)
        assert validate_style_pack_payload(style_pack) == []

    dead_god = get_builtin_style_pack("dead_god_observatory")
    assert dead_god["style_bible"]["palette"] == [
        "bone ivory",
        "oxidized copper",
        "black glass",
        "lunar blue",
        "candle gold",
    ]
    assert {material["material_id"] for material in dead_god["materials"]} == {
        "mat_bone_stone",
        "mat_oxidized_brass",
        "mat_black_obsidian_glass",
        "mat_candle_flame",
    }

    with pytest.raises(KeyError):
        get_builtin_style_pack("unknown_pack")


def test_layout_plan_is_deterministic_and_schema_valid() -> None:
    scene_graph = _scene()
    reordered = deepcopy(scene_graph)
    reordered["objects"] = list(reversed(reordered["objects"]))

    plan = plan_layout(scene_graph)
    reordered_plan = plan_layout(reordered)

    assert validate_layout_plan_payload(plan) == []
    assert plan["schema_version"] == "lathe.layout_plan.v1"
    assert [placement["object_id"] for placement in plan["placements"]] == [
        "obj_crate_001",
        "obj_crate_002",
        "obj_focus_001",
    ]
    assert _without_source_index(plan["placements"]) == _without_source_index(reordered_plan["placements"])
    assert plan["path_plan"]["waypoints"] == [[0.0, -3.0, 0.5], [0.0, 2.0, 0.5]]


def test_layout_plan_generates_modular_wall_segments_on_region_edges() -> None:
    scene_graph = _scene()
    scene_graph["layout"]["modular_walls"] = {
        "enabled": True,
        "regions": ["region_main"],
        "sides": ["north", "south"],
        "module_length": 2.0,
        "snap_grid": 1.0,
        "height": 3.0,
        "thickness": 0.25,
    }

    plan = plan_layout(scene_graph)

    assert validate_layout_plan_payload(plan) == []
    assert plan["layout"]["modular_walls"] == {
        "enabled": True,
        "regions": ["region_main"],
        "sides": ["north", "south"],
        "module_length": 2.0,
        "snap_grid": 1.0,
        "height": 3.0,
        "thickness": 0.25,
    }
    assert len(plan["wall_segments"]) == 8
    assert {segment["side"] for segment in plan["wall_segments"]} == {"north", "south"}
    assert [segment["center"] for segment in plan["wall_segments"] if segment["side"] == "north"] == [
        [-3.0, 4.0, 0.5],
        [-1.0, 4.0, 0.5],
        [1.0, 4.0, 0.5],
        [3.0, 4.0, 0.5],
    ]
    assert all(segment["aligned_to_grid"] is True for segment in plan["wall_segments"])
    assert "LP2005" not in _codes(plan["diagnostics"])


def test_layout_plan_reports_off_grid_modular_wall_segments() -> None:
    scene_graph = _scene()
    scene_graph["layout"]["modular_walls"] = {
        "enabled": True,
        "regions": ["region_main"],
        "sides": ["north"],
        "module_length": 1.5,
        "snap_grid": 1.0,
    }

    plan = plan_layout(scene_graph)

    assert "LP2005" in _codes(plan["diagnostics"])
    assert any(segment["aligned_to_grid"] is False for segment in plan["wall_segments"])
    assert validate_layout_plan_payload(plan) == []


def test_instance_reuse_groups_share_assets_despite_instance_state_changes() -> None:
    groups = plan_instance_reuse(_scene())

    crate_group = next(group for group in groups if group["source"]["ref"] == "shared_crate")

    assert crate_group["object_ids"] == ["obj_crate_001", "obj_crate_002"]
    assert crate_group["shared_asset"] is True
    assert len({item["fingerprint"] for item in crate_group["instance_fingerprints"]}) == 2
    assert "state" in crate_group["instance_fingerprints"][0]["fields"]


def test_four_damaged_doors_share_one_family_with_instance_overrides() -> None:
    scene_graph = _scene()
    door_affordance = {"id": "affordance_inspect_scratches", "action": "inspect"}
    scene_graph["objects"] = [
        _object(
            f"obj_archive_door_{index:03d}",
            x=-3 + index,
            y=0,
            lathe_asset="sealed_archive_door",
            source_family="mechanical_door_family",
            state={"damaged": True, "damage_level": index},
            surface_overrides={"scratches": round(index * 0.2, 2), "dust": "heavy"},
            affordances=[door_affordance | {"id": f"affordance_inspect_scratches_{index:03d}"}],
        )
        for index in range(1, 5)
    ]

    groups = plan_instance_reuse(scene_graph)

    door_group = next(group for group in groups if group["source"]["ref"] == "sealed_archive_door")
    assert door_group["object_ids"] == [
        "obj_archive_door_001",
        "obj_archive_door_002",
        "obj_archive_door_003",
        "obj_archive_door_004",
    ]
    assert door_group["shared_asset"] is True
    assert "surface_overrides" in door_group["instance_override_fields"]
    assert "affordances" in door_group["instance_override_fields"]
    assert len({item["fingerprint"] for item in door_group["instance_fingerprints"]}) == 4
    assert all("surface_overrides" in item["fields"] for item in door_group["instance_fingerprints"])
    assert all("affordances" in item["fields"] for item in door_group["instance_fingerprints"])


def test_layout_plan_reports_intersections_and_blocked_path() -> None:
    plan = plan_layout(_scene(overlap=True))

    assert {"LP2002", "LP2003"} <= _codes(plan["diagnostics"])
    assert plan["intersections"] == [
        {
            "object_a": "obj_crate_001",
            "object_b": "obj_crate_002",
            "region_id": "region_main",
            "overlap": [1.0, 1.0],
        }
    ]
    assert plan["path_plan"]["blocked_by"] == ["obj_crate_001", "obj_crate_002"]
    assert validate_layout_plan_payload(plan) == []


def test_camera_lighting_plan_links_shots_to_target_lights() -> None:
    scene_graph = _scene()
    layout_plan = plan_layout(scene_graph)

    plan = plan_camera_lighting(scene_graph, layout_plan=layout_plan)

    assert validate_camera_lighting(scene_graph, layout_plan=layout_plan) == []
    assert plan["schema_version"] == "lathe.camera_lighting_plan.v1"
    assert plan["cameras"][0]["distance_to_target"] > 0
    assert plan["lights"][0]["role"] == "key"
    assert plan["links"] == [
        {
            "camera_id": "camera_reveal",
            "target": "obj_focus_001",
            "light_ids": ["light_key_001"],
        }
    ]
