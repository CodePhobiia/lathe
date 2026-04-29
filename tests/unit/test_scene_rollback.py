from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from lathe.scene.history import (
    append_scene_history_record,
    create_scene_history,
    create_scene_history_record,
    normalized_scene_graph,
)
from lathe.scene.patch import apply_scene_patch
from lathe.scene.rollback import RollbackHashMismatch, rollback_scene

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
EXAMPLE_SCENE = EXAMPLE_DIR / "scene_graph.json"
EXAMPLE_PATCH = EXAMPLE_DIR / "scene_patch_more_sacred.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _patch() -> dict:
    return json.loads(EXAMPLE_PATCH.read_text(encoding="utf-8"))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _history_for_patch(scene: dict, patch: dict) -> tuple[dict, dict]:
    result = apply_scene_patch(scene, patch)
    record = create_scene_history_record(scene, patch, result)
    history = append_scene_history_record(create_scene_history(), record)
    return result.scene_graph, history


def test_apply_patch_then_rollback_restores_original_normalized_scene() -> None:
    scene = _scene()
    patch = _patch()
    patched_scene, history = _history_for_patch(scene, patch)

    rolled_back = rollback_scene(patched_scene, history, "mem_patch_more_sacred_001")

    assert normalized_scene_graph(rolled_back) == normalized_scene_graph(scene)


def test_rollback_refuses_hash_mismatch() -> None:
    scene = _scene()
    patch = _patch()
    patched_scene, history = _history_for_patch(scene, patch)
    mismatched = copy.deepcopy(patched_scene)
    mismatched["prompt"] = "A changed prompt that breaks the hash guard."

    with pytest.raises(RollbackHashMismatch):
        rollback_scene(mismatched, history, "mem_patch_more_sacred_001")


def test_wonder_cli_apply_patch_then_rollback(tmp_path: Path) -> None:
    patched_path = tmp_path / "patched.scene_graph.json"
    history_path = tmp_path / "history.json"
    rolled_path = tmp_path / "rolled_back.scene_graph.json"

    apply_result = _cli(
        "wonder",
        "apply-patch",
        str(EXAMPLE_SCENE),
        str(EXAMPLE_PATCH),
        "--out",
        str(patched_path),
        "--history",
        str(history_path),
    )

    assert apply_result.returncode == 0, apply_result.stderr
    assert patched_path.exists()
    assert history_path.exists()

    rollback_result = _cli(
        "wonder",
        "rollback-scene",
        str(patched_path),
        "--history",
        str(history_path),
        "--to-event",
        "mem_patch_more_sacred_001",
        "--out",
        str(rolled_path),
    )

    assert rollback_result.returncode == 0, rollback_result.stderr
    rolled_back = json.loads(rolled_path.read_text(encoding="utf-8"))
    assert normalized_scene_graph(rolled_back) == normalized_scene_graph(_scene())


def test_scene_cli_rollback_restores_original_scene(tmp_path: Path) -> None:
    scene = _scene()
    patch = _patch()
    patched_scene, history = _history_for_patch(scene, patch)
    patched_path = tmp_path / "patched.scene_graph.json"
    history_path = tmp_path / "history.json"
    rolled_path = tmp_path / "rolled_back.scene_graph.json"
    _write_json(patched_path, patched_scene)
    _write_json(history_path, history)

    rollback_result = _cli(
        "scene",
        "rollback",
        str(patched_path),
        "--history",
        str(history_path),
        "--to",
        "mem_patch_more_sacred_001",
        "--out",
        str(rolled_path),
    )

    assert rollback_result.returncode == 0, rollback_result.stderr
    payload = json.loads(rollback_result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "scene.rollback"
    assert payload["written"] is True
    rolled_back = json.loads(rolled_path.read_text(encoding="utf-8"))
    assert normalized_scene_graph(rolled_back) == normalized_scene_graph(scene)
