from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

from lathe.scene.memory import append_memory_event, create_world_memory
from lathe.scene.patch import SCENE_PATCH_SCOPES, apply_scene_patch

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
EXAMPLE_SCENE = EXAMPLE_DIR / "scene_graph.json"
EXAMPLE_PATCH = EXAMPLE_DIR / "scene_patch_more_sacred.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _patch() -> dict:
    return json.loads(EXAMPLE_PATCH.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _semantic_patch(*, scope: str = "object", target_id: str = "obj_astrolabe_table_001") -> dict:
    return {
        "schema_version": "lathe.scene_patch.v1",
        "patch_id": f"patch_scope_{scope}_001",
        "scope": scope,
        "target_id": target_id,
        "instruction": f"Record a semantic-only {scope} patch.",
        "preserve": ["object_id", "transform"],
        "allowed_changes": ["metadata"],
    }


def test_apply_scene_patch_records_semantic_instruction_without_geometry_edits() -> None:
    scene_graph = _scene()
    patch = _patch()
    patch.pop("operations")
    before_objects = copy.deepcopy(scene_graph["objects"])

    result = apply_scene_patch(scene_graph, patch)

    assert result.diagnostics == []
    assert result.scene_graph["objects"] == before_objects
    assert result.scene_graph is not scene_graph
    assert result.scene_memory_event is not None
    assert result.scene_memory_event["type"] == "patch"
    assert result.patch_event["patch_id"] == "patch_more_sacred_001"
    assert result.patch_event["metadata"]["status"] == "applied"

    world_memory = create_world_memory(scene_graph, summary="Patch event suitability test.")
    _updated_memory, diagnostics = append_memory_event(world_memory, result.patch_event, scene_graph=scene_graph)
    assert diagnostics == []


def test_apply_scene_patch_supports_example_json_operations_and_preserves_continuity() -> None:
    scene_graph = _scene()
    original_ids = [item["object_id"] for item in scene_graph["objects"]]
    original_transform = copy.deepcopy(scene_graph["objects"][0]["transform"])

    result = apply_scene_patch(scene_graph, _patch())

    assert result.diagnostics == []
    assert len(result.applied_operations) == 2
    assert result.rejected_operations == []
    assert result.scene_graph["objects"][0]["semantic_tags"][-1] == "sacred"
    assert [item["object_id"] for item in result.scene_graph["objects"]] == original_ids
    assert result.scene_graph["objects"][0]["transform"] == original_transform
    assert result.scene_graph["memory_events"][-1]["event_id"] == "mem_patch_more_sacred_001"


def test_apply_scene_patch_supports_all_schema_scopes_without_invented_edits() -> None:
    targets = {
        "asset": "astrolabe_table",
        "object": "obj_astrolabe_table_001",
        "region": "region_central_chamber",
        "scene": "alchemist_observatory",
        "camera": "camera_reveal",
        "light": "light_moonbeam_001",
        "curiosity_anchor": "curiosity_warm_lens",
        "hidden_state": "hidden_warm_lens_truth",
    }

    assert tuple(targets) == SCENE_PATCH_SCOPES
    for scope, target_id in targets.items():
        result = apply_scene_patch(_scene(), _semantic_patch(scope=scope, target_id=target_id))

        assert result.diagnostics == []
        assert result.applied_operations == []
        assert result.patch_event["metadata"]["scene_patch_scope"] == scope
        assert result.scene_graph["memory_events"][-1]["type"] == "patch"


def test_apply_scene_patch_supports_json_patch_operation_set() -> None:
    patch = _semantic_patch()
    patch["patch_id"] = "patch_state_ops_001"
    patch["allowed_changes"] = ["state"]
    patch["operations"] = [
        {"op": "test", "path": "/objects/0/state/powered", "value": True},
        {"op": "copy", "from": "/objects/0/state/powered", "path": "/objects/0/state/was_powered"},
        {"op": "add", "path": "/objects/0/state/ritual_charge", "value": "high"},
        {"op": "replace", "path": "/objects/0/state/powered", "value": False},
        {
            "op": "move",
            "from": "/objects/0/state/secret_compartment",
            "path": "/objects/0/state/secret_compartment_state",
        },
        {"op": "remove", "path": "/objects/0/state/damaged"},
    ]

    result = apply_scene_patch(_scene(), patch)
    state = result.scene_graph["objects"][0]["state"]

    assert result.diagnostics == []
    assert len(result.applied_operations) == 6
    assert state["was_powered"] is True
    assert state["ritual_charge"] == "high"
    assert state["powered"] is False
    assert state["secret_compartment_state"] == "unopened"
    assert "secret_compartment" not in state
    assert "damaged" not in state


def test_apply_scene_patch_rejects_copy_from_outside_target_scope() -> None:
    patch = _semantic_patch()
    patch["patch_id"] = "patch_cross_object_copy_001"
    patch["allowed_changes"] = ["state"]
    patch["operations"] = [
        {"op": "copy", "from": "/objects/1/state/cracked", "path": "/objects/0/state/copied_cracked"},
    ]

    result = apply_scene_patch(_scene(), patch)

    assert "SP1508" in _codes(result.diagnostics)
    assert "copied_cracked" not in result.scene_graph["objects"][0]["state"]
    assert result.scene_memory_event is None
    assert result.rejected_operations[0]["index"] == 0
    assert result.rejected_operations[0]["operation"] == patch["operations"][0]
    assert result.rejected_operations[0]["diagnostics"][0]["code"] == "SP1508"


def test_apply_scene_patch_rejects_removed_preserved_json_pointer() -> None:
    patch = _semantic_patch()
    patch["patch_id"] = "patch_remove_preserved_path_001"
    patch["preserve"] = ["/objects/0/state/powered"]
    patch["allowed_changes"] = ["state"]
    patch["operations"] = [
        {"op": "remove", "path": "/objects/0/state/powered"},
    ]

    result = apply_scene_patch(_scene(), patch)

    assert "SP1505" in _codes(result.diagnostics)
    assert result.scene_graph["objects"][0]["state"]["powered"] is True
    assert result.scene_memory_event is None


def test_apply_scene_patch_rejects_preserved_transform_change() -> None:
    patch = _patch()
    patch["allowed_changes"] = ["transforms"]
    patch["operations"] = [
        {"op": "replace", "path": "/objects/0/transform/position", "value": [1, 0, 0.75]},
    ]

    result = apply_scene_patch(_scene(), patch)

    assert "SP1505" in _codes(result.diagnostics)
    assert result.scene_graph["objects"][0]["transform"]["position"] == [0, 0, 0.75]
    assert result.scene_memory_event is None
    assert result.patch_event["metadata"]["status"] == "rejected"


def test_apply_scene_patch_rejects_transform_without_allowed_change() -> None:
    patch = _semantic_patch()
    patch["patch_id"] = "patch_forbidden_transform_001"
    patch["preserve"] = []
    patch["allowed_changes"] = ["metadata"]
    patch["operations"] = [
        {"op": "replace", "path": "/objects/0/transform/scale", "value": [2, 2, 2]},
    ]

    result = apply_scene_patch(_scene(), patch)

    assert "SP1504" in _codes(result.diagnostics)
    assert result.scene_graph["objects"][0]["transform"]["scale"] == [1.4, 1.4, 1]
    assert result.scene_memory_event is None


def test_apply_scene_patch_reports_missing_target() -> None:
    patch = _semantic_patch(target_id="obj_missing_001")

    result = apply_scene_patch(_scene(), patch)

    assert "SP1501" in _codes(result.diagnostics)
    assert result.patch_event["metadata"]["status"] == "rejected"
    assert result.scene_memory_event is None


def test_scene_patch_cli_preview_emits_result_without_writing(tmp_path: Path) -> None:
    out_path = tmp_path / "updated_scene_graph.json"

    result = _cli("scene", "patch", str(EXAMPLE_SCENE), str(EXAMPLE_PATCH), "--out", str(out_path), "--preview")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["preview"] is True
    assert payload["written"] is False
    assert payload["diagnostics"] == []
    assert payload["scene_graph"]["memory_events"][-1]["type"] == "patch"
    assert not out_path.exists()


def test_scene_patch_cli_writes_valid_updated_scene_graph(tmp_path: Path) -> None:
    out_path = tmp_path / "updated_scene_graph.json"

    result = _cli("scene", "patch", str(EXAMPLE_SCENE), str(EXAMPLE_PATCH), "--out", str(out_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["written"] is True
    assert out_path.exists()
    updated = json.loads(out_path.read_text(encoding="utf-8"))
    assert updated["memory_events"][-1]["event_id"] == "mem_patch_more_sacred_001"


def test_scene_patch_cli_rejects_forbidden_patch_without_writing(tmp_path: Path) -> None:
    patch = _patch()
    patch["allowed_changes"] = ["transforms"]
    patch["operations"] = [
        {"op": "replace", "path": "/objects/0/transform/position", "value": [1, 0, 0.75]},
    ]
    patch_path = tmp_path / "forbidden_patch.json"
    out_path = tmp_path / "updated_scene_graph.json"
    _write_json(patch_path, patch)

    result = _cli("scene", "patch", str(EXAMPLE_SCENE), str(patch_path), "--out", str(out_path))

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "SP1505" in _codes(payload["diagnostics"])
    assert payload["written"] is False
    assert not out_path.exists()


def test_scene_patch_cli_marks_post_validation_failure_as_rejected(tmp_path: Path) -> None:
    patch = _semantic_patch()
    patch["patch_id"] = "patch_invalid_state_shape_001"
    patch["allowed_changes"] = ["state"]
    patch["operations"] = [
        {"op": "add", "path": "/objects/0/state/invalid_nested_state", "value": {"nested": True}},
    ]
    patch_path = tmp_path / "invalid_state_patch.json"
    out_path = tmp_path / "updated_scene_graph.json"
    _write_json(patch_path, patch)

    result = _cli("scene", "patch", str(EXAMPLE_SCENE), str(patch_path), "--out", str(out_path))

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "WONDER_SCHEMA_VALIDATION" in _codes(payload["diagnostics"])
    assert payload["patch_event"]["metadata"]["status"] == "rejected"
    assert payload["patch_event"]["metadata"]["post_validation_failed"] is True
    assert payload["scene_memory_event"] is None
    assert payload["scene_graph"]["memory_events"][-1]["event_id"] != "mem_patch_invalid_state_shape_001"
    assert payload["written"] is False
    assert not out_path.exists()
