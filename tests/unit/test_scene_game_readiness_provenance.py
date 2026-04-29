from __future__ import annotations

import jsonschema
from lathe.scene import (
    get_asset_provenance_scene_schema,
    get_game_readiness_schema,
    validate_asset_provenance_scene_payload,
    validate_game_readiness_payload,
    validate_scene_game_readiness,
    validate_scene_provenance,
)


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def _scene() -> dict:
    return {
        "scene_id": "game_room",
        "version": 1,
        "objects": [
            {
                "object_id": "obj_archive_door_001",
                "role": "interactive",
                "state": {"collision": "box", "secret_compartment": "unopened"},
                "affordances": [{"id": "open_door", "action": "open"}],
                "provenance": {"source": "deterministic_lathe", "commercial_use": True},
            },
            {
                "object_id": "obj_floor_panel_001",
                "role": "architecture",
                "state": {"pivot_mode": "base_center"},
                "provenance": {"source": "deterministic_lathe", "commercial_use": True},
            },
        ],
        "exports": [],
    }


def _game_readiness_payload() -> dict:
    return {
        "schema_version": "lathe.game_readiness.v1",
        "scene_id": "game_room",
        "target": "generic_game",
        "objects": [
            {
                "object_id": "obj_archive_door_001",
                "mobility": "static",
                "interactable": True,
                "collision": {"type": "box", "required": True},
                "pivot": {"mode": "base_center"},
                "snap_points": [{"name": "door_socket", "position": [0, 0, 0]}],
                "gameplay_tags": ["door", "quest"],
            }
        ],
    }


def _asset_provenance_payload() -> dict:
    return {
        "schema_version": "lathe.asset_provenance_scene.v1",
        "scene_id": "game_room",
        "objects": [
            {
                "object_id": "obj_archive_door_001",
                "provenance": {
                    "source": "deterministic_lathe",
                    "commercial_use": True,
                    "export_permission": "allowed",
                },
                "content_safety": {"status": "passed", "categories": ["environment_prop"]},
                "brand_ip": {"status": "cleared"},
                "user_upload": {"present": False, "safety_status": "passed"},
            }
        ],
        "exports": [
            {
                "target": "glb",
                "path": "exports/game_room.glb",
                "permission": "allowed",
                "source_object_ids": ["obj_archive_door_001"],
            }
        ],
    }


def test_game_readiness_and_provenance_schemas_are_valid_json_schemas() -> None:
    jsonschema.Draft202012Validator.check_schema(get_game_readiness_schema())
    jsonschema.Draft202012Validator.check_schema(get_asset_provenance_scene_schema())


def test_game_readiness_and_provenance_payloads_validate() -> None:
    assert validate_game_readiness_payload(_game_readiness_payload()) == []
    assert validate_asset_provenance_scene_payload(_asset_provenance_payload()) == []


def test_game_readiness_payload_schema_reports_errors() -> None:
    payload = _game_readiness_payload()
    payload["objects"][0]["snap_points"][0]["name"] = "Bad Name"

    diagnostics = validate_game_readiness_payload(payload)

    assert diagnostics
    assert diagnostics[0]["code"] == "GAME_READINESS_SCHEMA_VALIDATION"
    assert diagnostics[0]["path"] == "/objects/0/snap_points/0/name"


def test_game_readiness_reports_missing_collision_and_pivot() -> None:
    diagnostics = validate_scene_game_readiness(_scene())

    by_code = {diagnostic["code"]: diagnostic for diagnostic in diagnostics}
    assert {"GR1001", "GR1002"} <= set(by_code)
    assert by_code["GR1001"]["path"] == "/objects/1"
    assert by_code["GR1002"]["path"] == "/objects/0"


def test_game_readiness_uses_standalone_metadata_payload() -> None:
    scene = _scene()
    scene["objects"][0]["state"].pop("collision")
    scene["objects"][1]["state"].pop("pivot_mode")
    payload = _game_readiness_payload()
    payload["objects"].append(
        {
            "object_id": "obj_floor_panel_001",
            "collision": {"type": "mesh", "required": True},
            "pivot": {"mode": "base_center"},
        }
    )

    diagnostics = validate_scene_game_readiness(scene, game_readiness=payload)

    assert "GR1001" not in _codes(diagnostics)
    assert "GR1002" not in _codes(diagnostics)


def test_game_readiness_reports_invalid_snap_point_names() -> None:
    scene = _scene()
    scene["objects"][0]["state"]["snap_points"] = ["Bad Name"]

    diagnostics = validate_scene_game_readiness(scene)

    diagnostic = next(item for item in diagnostics if item["code"] == "GR1003")
    assert diagnostic["path"] == "/objects/0/state/snap_points/0"


def test_scene_provenance_reports_missing_and_incomplete_provider_metadata() -> None:
    scene = _scene()
    scene["objects"].append({"object_id": "obj_missing_provenance_001", "role": "dressing_prop"})
    scene["objects"].append(
        {
            "object_id": "obj_provider_tree_001",
            "role": "dressing_prop",
            "provenance": {"source": "provider_generated", "commercial_use": True},
        }
    )

    diagnostics = validate_scene_provenance(scene)

    assert {"PR1001", "PR1002"} <= _codes(diagnostics)
    by_code = {diagnostic["code"]: diagnostic for diagnostic in diagnostics}
    assert by_code["PR1001"]["path"] == "/objects/2/provenance"
    assert by_code["PR1002"]["path"] == "/objects/3/provenance/provider"


def test_secret_bearing_metadata_is_reported_without_false_positive_on_scene_lore() -> None:
    scene = _scene()
    scene["objects"][0]["state"]["api_key"] = "sk-test1234567890"
    scene["exports"].append(
        {
            "target": "glb",
            "format": "glb",
            "path": "exports/game_room.glb",
            "metadata": {"authorization": "Bearer abcdefghijklmnop"},
        }
    )

    game_diagnostics = validate_scene_game_readiness(scene)
    provenance_diagnostics = validate_scene_provenance(scene)

    assert "GR9001" in _codes(game_diagnostics)
    assert "PR9001" in _codes(provenance_diagnostics)
    assert all(diagnostic["details"]["field"] != "secret_compartment" for diagnostic in provenance_diagnostics)
    assert all("sk-test1234567890" not in diagnostic["message"] for diagnostic in provenance_diagnostics)
