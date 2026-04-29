from __future__ import annotations

import json
from pathlib import Path

from lathe.scene.camera_lock import lock_camera
from lathe.scene.patch import apply_scene_patch

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"
EXAMPLE_PATCH = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_patch_more_sacred.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _patch() -> dict:
    return json.loads(EXAMPLE_PATCH.read_text(encoding="utf-8"))


def test_lock_existing_camera_produces_deterministic_hash() -> None:
    first, first_diagnostics = lock_camera(_scene(), "camera_reveal")
    second, second_diagnostics = lock_camera(_scene(), "camera_reveal")

    assert first_diagnostics == []
    assert second_diagnostics == []
    assert first == second
    assert first is not None
    assert first["schema_version"] == "lathe.camera_lock.v1"
    assert first["scene_id"] == "alchemist_observatory"
    assert first["camera_id"] == "camera_reveal"
    assert first["target"] == "obj_astrolabe_table_001"
    assert first["position"] == [-5.2, -5.6, 2.4]
    assert first["camera_hash"].startswith("sha256:")


def test_missing_camera_reports_clear_diagnostic() -> None:
    camera_lock, diagnostics = lock_camera(_scene(), "camera_missing_001")

    assert camera_lock is None
    assert diagnostics
    assert diagnostics[0]["code"] == "CL1002"
    assert "does not exist" in diagnostics[0]["message"]


def test_repeated_runs_produce_identical_json() -> None:
    first, first_diagnostics = lock_camera(_scene(), "camera_reveal")
    second, second_diagnostics = lock_camera(_scene(), "camera_reveal")

    assert first_diagnostics == []
    assert second_diagnostics == []
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_camera_lock_survives_non_camera_scene_patch() -> None:
    before_lock, before_diagnostics = lock_camera(_scene(), "camera_reveal")
    patch_result = apply_scene_patch(_scene(), _patch())
    after_lock, after_diagnostics = lock_camera(patch_result.scene_graph, "camera_reveal")

    assert before_diagnostics == []
    assert patch_result.diagnostics == []
    assert after_diagnostics == []
    assert before_lock is not None
    assert after_lock is not None
    assert after_lock["camera_hash"] == before_lock["camera_hash"]
    assert after_lock["position"] == before_lock["position"]
    assert after_lock["target"] == before_lock["target"]
    assert after_lock["fov_degrees"] == before_lock["fov_degrees"]
