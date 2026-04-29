from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lathe.scene.history import (
    append_scene_history_record,
    branch_history,
    create_scene_history,
    create_scene_history_record,
    validate_scene_history_payload,
)
from lathe.scene.memory import create_world_memory
from lathe.scene.patch import apply_scene_patch

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


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def test_create_and_update_scene_history_record() -> None:
    scene = _scene()
    patch = _patch()
    result = apply_scene_patch(scene, patch)
    record = create_scene_history_record(
        scene,
        patch,
        result,
        forward_patch_path="scene_patch_more_sacred.json",
    )

    history = append_scene_history_record(create_scene_history(), record)
    updated_record = {**record, "validation_reports": [{"ok": True, "lane": "unit"}]}
    updated_history = append_scene_history_record(history, updated_record)

    assert validate_scene_history_payload(updated_history) == []
    assert len(updated_history["records"]) == 1
    assert updated_history["records"][0]["event_id"] == "mem_patch_more_sacred_001"
    assert updated_history["records"][0]["forward_patch"]["path"] == "scene_patch_more_sacred.json"
    assert updated_history["records"][0]["inverse_patch"]["payload"]["operations"]
    assert updated_history["records"][0]["validation_reports"] == [{"ok": True, "lane": "unit"}]
    assert updated_history["records"][0]["comparison_reports"] == []


def test_branch_history_emits_events_and_optional_reports() -> None:
    scene = _scene()
    patch = _patch()
    result = apply_scene_patch(scene, patch)
    record = create_scene_history_record(
        scene,
        patch,
        result,
        validation_reports=[{"ok": True, "lane": "schema"}],
        render_reports=[{"ok": True, "lane": "proxy"}],
        comparison_reports=[{"ok": True, "lane": "pixel"}],
    )
    history = append_scene_history_record(create_scene_history(), record)
    memory = create_world_memory(scene, summary="Branch history test.", events=[result.patch_event])

    payload = branch_history(memory, "main", scene_history=history)
    without_history = branch_history(memory, "main")

    assert payload["schema_version"] == "lathe.scene_branch_history.v1"
    assert payload["event_ids"] == ["mem_patch_more_sacred_001"]
    assert payload["events"][0]["event_id"] == "mem_patch_more_sacred_001"
    assert payload["history_records"][0]["event_id"] == "mem_patch_more_sacred_001"
    assert payload["validation_reports"] == [{"ok": True, "lane": "schema"}]
    assert payload["render_reports"] == [{"ok": True, "lane": "proxy"}]
    assert payload["comparison_reports"] == [{"ok": True, "lane": "pixel"}]
    assert without_history["validation_reports"] == []
    assert without_history["render_reports"] == []
    assert without_history["comparison_reports"] == []


def test_wonder_cli_branch_history_writes_expected_shape(tmp_path: Path) -> None:
    scene = _scene()
    patch = _patch()
    result = apply_scene_patch(scene, patch)
    record = create_scene_history_record(scene, patch, result)
    history = append_scene_history_record(create_scene_history(), record)
    memory = create_world_memory(scene, summary="Branch history CLI test.", events=[result.patch_event])
    memory_path = tmp_path / "world_memory.json"
    history_path = tmp_path / "history.json"
    out_path = tmp_path / "branch_history.json"
    _write_json(memory_path, memory)
    _write_json(history_path, history)

    result_cli = _cli(
        "wonder",
        "branch-history",
        "--memory",
        str(memory_path),
        "--branch",
        "main",
        "--history",
        str(history_path),
        "--out",
        str(out_path),
    )

    assert result_cli.returncode == 0, result_cli.stderr
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["event_ids"] == ["mem_patch_more_sacred_001"]
    assert payload["validation_reports"] == []
    assert payload["render_reports"] == []
    assert payload["comparison_reports"] == []
