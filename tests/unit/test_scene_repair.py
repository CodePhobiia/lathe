from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
from lathe.scene.repair import (
    get_scene_repair_report_schema,
    inspect_render,
    propose_repairs,
    repair_scene_offline,
    validate_scene_repair_report_payload,
)
from lathe.wonder import validate_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
EXAMPLE_SCENE = EXAMPLE_DIR / "scene_graph.json"
EXAMPLE_INSPECTION = EXAMPLE_DIR / "render_inspection.example.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _inspection() -> dict:
    return json.loads(EXAMPLE_INSPECTION.read_text(encoding="utf-8"))


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def test_scene_repair_report_schema_is_valid_json_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(get_scene_repair_report_schema())


def test_inspect_render_reports_missing_target_ids() -> None:
    inspection = _inspection()
    inspection["render_ref"]["camera_id"] = "camera_missing_001"
    inspection["problems"][0]["target_id"] = "obj_missing_001"
    inspection["recommended_patches"][0]["target_id"] = "obj_missing_001"

    diagnostics = inspect_render(_scene(), inspection)

    assert {"RR1002", "RR1003", "RR1004"} <= _codes(diagnostics)


def test_propose_repairs_converts_recommendations_to_scene_patch() -> None:
    result = propose_repairs(_scene(), _inspection())

    assert result.report["status"] == "proposed"
    assert validate_scene_repair_report_payload(result.report) == []
    assert len(result.proposals) == 1

    patch = result.proposals[0]
    assert patch["schema_version"] == "lathe.scene_patch.v1"
    assert patch["scope"] == "object"
    assert patch["target_id"] == "obj_astrolabe_table_001"
    assert patch["preserve"] == [
        "object_id",
        "region",
        "transform.position",
        "transform.rotation",
        "transform.scale",
    ]
    assert patch["acceptance"]["validators"] == ["style", "semantic", "composition", "continuity"]
    assert validate_contract("scene_patch", patch) == []


def test_repair_scene_offline_reports_max_rounds_skips() -> None:
    inspection = _inspection()
    second = copy.deepcopy(inspection["recommended_patches"][0])
    second["target_id"] = "obj_archive_door_001"
    second["change"] = "Make the archive door read as a clearer continuation hook."
    inspection["recommended_patches"].append(second)

    result = repair_scene_offline(_scene(), inspection, max_rounds=1)

    assert result.report["status"] == "max_rounds_reached"
    assert result.report["summary"]["applied"] == 1
    assert result.report["summary"]["skipped"] == 1
    assert result.report["rounds_completed"] == 1
    assert result.report["proposals"][1]["status"] == "skipped"
    assert result.scene_graph["memory_events"][-1]["type"] == "patch"
    assert validate_scene_repair_report_payload(result.report) == []


def test_repair_scene_offline_reports_failed_patch_diagnostics() -> None:
    inspection = _inspection()
    inspection["recommended_patches"][0]["suggested_patch"] = {
        "patch_id": "patch_bad_scope_001",
        "preserve": [],
        "allowed_changes": ["transforms"],
        "operations": [
            {"op": "replace", "path": "/objects/1/transform/position", "value": [2, 0, 0.75]},
        ],
    }

    result = repair_scene_offline(_scene(), inspection, max_rounds=1)

    assert result.report["status"] == "failed"
    assert result.report["summary"]["rejected"] == 1
    assert result.report["rounds"][0]["status"] == "rejected"
    assert "SP1508" in _codes(result.report["diagnostics"])
    assert result.scene_graph["objects"][1]["transform"]["position"] == [0, 0, 2]
    assert validate_scene_repair_report_payload(result.report) == []
