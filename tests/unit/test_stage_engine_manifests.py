"""Unit tests for STAGE-10 engine-manifest adapters + STAGE-9 LOD config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import trimesh

from lathe.engine_manifests import (
    ADAPTERS,
    FILE_EXTENSIONS,
    emit_godot_manifest,
    emit_unity_manifest,
    emit_unreal_manifest,
    manifest_filename,
)
from lathe.selector_manifest import (
    GAMEPLAY_TAG_CATALOG,
    build_selector_manifest,
    write_selector_manifest,
)
from lathe.stages import lod as lod_mod


@pytest.fixture()
def engine_context() -> dict:
    return {
        "main_glb_uri": "courier_drone.glb",
        "lods": [
            {
                "level": 0,
                "mesh_uri": "lod_0.glb",
                "triangle_count": 1280,
                "distance_min": 0.0,
                "distance_max": 10.0,
                "screen_coverage": 1.0,
            },
            {
                "level": 1,
                "mesh_uri": "lod_1.glb",
                "triangle_count": 640,
                "distance_min": 10.0,
                "distance_max": 30.0,
                "screen_coverage": 0.4,
            },
            {
                "level": 2,
                "mesh_uri": "lod_2.glb",
                "triangle_count": 320,
                "distance_min": 30.0,
                "distance_max": 100.0,
                "screen_coverage": 0.15,
            },
            {
                "level": 3,
                "mesh_uri": "lod_3.glb",
                "triangle_count": 128,
                "distance_min": 100.0,
                "distance_max": None,
                "screen_coverage": 0.05,
            },
        ],
        "sockets": [
            {
                "id": "grip_main",
                "origin": [0.0, 1.0, 0.0],
                "axis": [0.0, 0.0, 1.0],
                "socket_type": "grip",
                "parent_part_id": "body",
            }
        ],
        "pivots": [
            {
                "id": "center_main",
                "origin": [0.0, 0.0, 0.0],
                "axis": [0.0, 1.0, 0.0],
                "pivot_type": "center",
            }
        ],
        "collisions": [
            {
                "id": "hull",
                "kind": "hull",
                "uri": "collision_hull.glb",
                "parent_part_id": None,
            },
            {
                "id": "parts",
                "kind": "hull",
                "uri": "collision_parts.glb",
                "parent_part_id": None,
            },
        ],
        "materials": [{"id": "steel", "display_name": "Brushed Steel"}],
        "gameplay_tags": ["kinematic", "interactable"],
    }


# --- STAGE-10: Adapters emit correct structure -----------------------------


def test_godot_manifest_has_expected_scene_graph(engine_context):
    payload = emit_godot_manifest(engine_context, "courier_drone")
    data = json.loads(payload)
    assert data["schemaVersion"] == 1
    assert data["engine"] == "godot"
    assert data["rootNode"]["type"] == "Node3D"
    assert data["rootNode"]["meta"]["gameplay_tags"] == ["kinematic", "interactable"]
    # LODs carry distance ranges.
    assert len(data["lodGroup"]) == 4
    assert data["lodGroup"][0]["visibilityRangeBegin"] == 0.0
    assert data["lodGroup"][0]["visibilityRangeEnd"] == 10.0
    # Final LOD's visibilityRangeEnd is None (infinity).
    assert data["lodGroup"][3]["visibilityRangeEnd"] is None
    assert data["lodGroup"][3]["meshUri"] == "lod_3.glb"
    # Socket nodes carry anchor_id + socket_type in meta.
    assert data["sockets"][0]["meta"]["anchor_id"] == "grip_main"
    assert data["sockets"][0]["meta"]["socket_type"] == "grip"
    # Collision reference.
    assert data["collision"]["type"] == "StaticBody3D"
    shape_uris = {s["meshUri"] for s in data["collision"]["shapes"]}
    assert shape_uris == {"collision_hull.glb", "collision_parts.glb"}


def test_unity_manifest_is_valid_yaml_text(engine_context):
    payload = emit_unity_manifest(engine_context, "courier_drone")
    assert payload.startswith("%YAML 1.1")
    # LODGroup entries with screenRelativeTransitionHeight present.
    assert "screenRelativeTransitionHeight" in payload
    # Sockets with typed anchor.
    assert "socketType: grip" in payload
    assert "anchorId: grip_main" in payload
    # Tags.
    assert "    - kinematic" in payload
    assert "    - interactable" in payload
    # Collision meshes referenced.
    assert "meshUri: collision_hull.glb" in payload
    assert "meshUri: collision_parts.glb" in payload


def test_unreal_manifest_references_lods_and_collisions(engine_context):
    payload = emit_unreal_manifest(engine_context, "courier_drone")
    data = json.loads(payload)
    assert data["engine"] == "unreal"
    assert data["actor"]["gameplayTags"] == ["kinematic", "interactable"]
    components = data["actor"]["components"]
    # Root + 4 LODs + 1 socket + 1 pivot + 2 collision bodies.
    assert any(c["class"] == "USceneComponent" for c in components)
    lod_components = [c for c in components if c["class"] == "UStaticMeshComponent"]
    assert len(lod_components) == 4
    assert lod_components[0]["minDrawDistance"] == 0.0
    assert lod_components[3]["ldMaxDrawDistance"] == -1.0  # infinite outer
    # Arrow socket component.
    arrow_components = [c for c in components if c["class"] == "UArrowComponent"]
    assert any(c["socketName"] == "grip_main" for c in arrow_components)
    # Body setup carrying collision mesh uri.
    body_components = [c for c in components if c["class"] == "UBodySetup"]
    assert {b["meshUri"] for b in body_components} == {
        "collision_hull.glb",
        "collision_parts.glb",
    }


def test_filename_helper_uses_extension_table():
    assert manifest_filename("godot", "x") == "x.lathe_for_godot.json"
    assert manifest_filename("unity", "x") == "x.lathe_for_unity.yaml"
    assert manifest_filename("unreal", "x") == "x.lathe_for_unreal.json"


def test_adapter_registry_exposes_all_three():
    assert set(ADAPTERS.keys()) == {"godot", "unity", "unreal"}
    assert set(FILE_EXTENSIONS.keys()) == {"godot", "unity", "unreal"}


# --- STAGE-9: LOD config extension -----------------------------------------


def test_lod_result_carries_default_distance_bands():
    sphere = trimesh.creation.icosphere(subdivisions=2)
    results = lod_mod.build_lods(sphere, [1.0, 0.5, 0.25, 0.1])
    # Default bands.
    assert results[0].distance_min == 0.0
    assert results[0].distance_max == 10.0
    assert results[1].distance_min == 10.0
    assert results[1].distance_max == 30.0
    assert results[3].distance_max is None
    assert results[0].screen_coverage == 1.0
    assert results[3].screen_coverage == 0.05


def test_lod_config_override_applies_to_matching_level():
    sphere = trimesh.creation.icosphere(subdivisions=2)
    cfg = [
        {"level": 1, "distance_min": 5.0, "distance_max": 20.0, "screen_coverage": 0.6},
        {"level": 3, "distance_min": 80.0, "distance_max": None, "screen_coverage": 0.02},
    ]
    results = lod_mod.build_lods(sphere, [1.0, 0.5, 0.25, 0.1], lod_config=cfg)
    assert results[0].distance_min == 0.0 and results[0].distance_max == 10.0  # untouched
    assert results[1].distance_min == 5.0
    assert results[1].distance_max == 20.0
    assert results[1].screen_coverage == 0.6
    assert results[3].distance_min == 80.0
    assert results[3].distance_max is None
    assert results[3].screen_coverage == 0.02


def test_lod_config_can_override_ratio():
    sphere = trimesh.creation.icosphere(subdivisions=2)
    cfg = [{"level": 1, "ratio": 0.75}]
    results = lod_mod.build_lods(sphere, [1.0, 0.5, 0.25, 0.1], lod_config=cfg)
    assert results[1].ratio == 0.75


# --- STAGE-9 + 10 end-to-end: selector manifest surfaces new fields --------


def test_selector_manifest_exposes_distance_bands(tmp_path):
    runtime = {
        "optimize": {
            "bundle": {
                "lod_manifest": [
                    {
                        "level": 0,
                        "part_id": "mesh",
                        "triangle_count": 1280,
                        "screen_size": 1.0,
                        "distance_min": 0.0,
                        "distance_max": 10.0,
                        "screen_coverage": 1.0,
                    },
                    {
                        "level": 1,
                        "part_id": "mesh",
                        "triangle_count": 640,
                        "distance_min": 10.0,
                        "distance_max": None,
                        "screen_coverage": 0.4,
                    },
                ],
            },
        },
    }
    manifest = build_selector_manifest(
        asset_name="x",
        variant_name=None,
        source_path="examples/x.lth",
        build_hash="abcd1234" * 4,
        runtime=runtime,
        build_dir=tmp_path / "x",
    )
    # Validate schema round-trip.
    write_selector_manifest(manifest, tmp_path / "x")
    assert manifest["lods"][0]["distanceMin"] == 0.0
    assert manifest["lods"][0]["distanceMax"] == 10.0
    assert manifest["lods"][1]["distanceMax"] is None
    assert manifest["lods"][1]["screenCoverage"] == 0.4


def test_selector_manifest_surfaces_engine_manifests(tmp_path):
    runtime = {
        "package": {
            "bundle": {
                "package_hash": "deadbeef" * 8,
                "engine_manifests": {
                    "godot": {
                        "path": "x.lathe_for_godot.json",
                        "sha256": "a" * 64,
                        "format": "json",
                    },
                    "unity": {
                        "path": "x.lathe_for_unity.yaml",
                        "sha256": "b" * 64,
                        "format": "yaml",
                    },
                    "unreal": {
                        "path": "x.lathe_for_unreal.json",
                        "sha256": "c" * 64,
                        "format": "json",
                    },
                },
            },
        },
    }
    manifest = build_selector_manifest(
        asset_name="x",
        variant_name=None,
        source_path="examples/x.lth",
        build_hash="abcd1234" * 4,
        runtime=runtime,
        build_dir=tmp_path / "x",
    )
    write_selector_manifest(manifest, tmp_path / "x")
    em = manifest["engineManifests"]
    assert set(em.keys()) == {"godot", "unity", "unreal"}
    assert em["godot"]["path"] == "x.lathe_for_godot.json"
    assert em["unity"]["format"] == "yaml"
    assert em["unreal"]["sha256"] == "c" * 64


def test_selector_manifest_surfaces_lod_config_from_asset(tmp_path):
    asset = {
        "build": {
            "optimize": {
                "lod_config": [
                    {"level": 0, "ratio": 1.0, "distance_min": 0, "distance_max": 8},
                    {"level": 1, "ratio": 0.5, "distance_min": 8, "distance_max": 25, "screen_coverage": 0.35},
                ]
            }
        }
    }
    manifest = build_selector_manifest(
        asset_name="x",
        variant_name=None,
        source_path="examples/x.lth",
        build_hash="abcd1234" * 4,
        runtime={},
        asset=asset,
        build_dir=tmp_path / "x",
    )
    assert "lodConfig" in manifest
    cfg = manifest["lodConfig"]
    assert len(cfg) == 2
    assert cfg[0]["level"] == 0
    assert cfg[0]["distance_max"] == 8.0
    assert cfg[1]["screen_coverage"] == 0.35


def test_engine_context_catalog_is_not_empty():
    assert "kinematic" in GAMEPLAY_TAG_CATALOG
    assert "door" in GAMEPLAY_TAG_CATALOG
    assert len(GAMEPLAY_TAG_CATALOG) >= 15


def test_godot_manifest_handles_zero_lods_gracefully():
    payload = emit_godot_manifest(
        {
            "main_glb_uri": "x.glb",
            "lods": [],
            "sockets": [],
            "pivots": [],
            "collisions": [],
            "materials": [],
            "gameplay_tags": [],
        },
        "x",
    )
    data = json.loads(payload)
    assert data["lodGroup"] == []
    assert data["sockets"] == []
    assert data["collision"]["shapes"] == []
