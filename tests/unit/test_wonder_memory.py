from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lathe.scene.memory import (
    append_memory_event,
    append_memory_event_idempotent,
    create_world_memory,
    load_and_validate_world_memory,
    record_rejected_patch,
    redact_memory_payload,
    validate_world_memory,
)
from lathe.scene.patch import apply_scene_patch

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
EXAMPLE_SCENE = EXAMPLE_DIR / "scene_graph.json"
EXAMPLE_MEMORY = EXAMPLE_DIR / "world_memory.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _memory() -> dict:
    return json.loads(EXAMPLE_MEMORY.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _codes(diagnostics: list[dict]) -> list[str]:
    return [diagnostic["code"] for diagnostic in diagnostics]


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def test_world_memory_example_validates_against_scene_graph() -> None:
    _payload, diagnostics = load_and_validate_world_memory(EXAMPLE_MEMORY, scene_graph=EXAMPLE_SCENE)

    assert diagnostics == []


def test_world_memory_reports_missing_affected_scene_entity() -> None:
    world_memory = _memory()
    world_memory["events"][0]["affected_ids"].append("obj_missing_001")

    diagnostics = validate_world_memory(world_memory, scene_graph=_scene())

    assert "M1002" in _codes(diagnostics)
    missing = next(item for item in diagnostics if item["code"] == "M1002")
    assert missing["name"] == "invalid_memory_affected_id"
    assert missing["path"] == "/events/0/affected_ids/3"
    assert missing["details"]["affected_id"] == "obj_missing_001"


def test_world_memory_reports_branch_event_that_does_not_exist() -> None:
    world_memory = _memory()
    world_memory["branches"][0]["event_ids"].append("mem_missing_001")

    diagnostics = validate_world_memory(world_memory, scene_graph=_scene())

    assert "M1006" in _codes(diagnostics)
    invalid = next(item for item in diagnostics if item["code"] == "M1006")
    assert invalid["name"] == "invalid_branch_event"
    assert invalid["path"] == "/branches/0/event_ids/4"


def test_world_memory_reports_missing_parent_branch() -> None:
    world_memory = _memory()
    world_memory["branches"].append(
        {
            "branch_id": "archive_branch",
            "name": "Archive",
            "status": "active",
            "parent_branch": "missing_parent",
            "event_ids": [],
        }
    )

    diagnostics = validate_world_memory(world_memory, scene_graph=_scene())

    assert "M1011" in _codes(diagnostics)
    invalid = next(item for item in diagnostics if item["code"] == "M1011")
    assert invalid["name"] == "invalid_parent_branch"
    assert invalid["path"] == "/branches/1/parent_branch"


def test_world_memory_reports_orphan_event_branch() -> None:
    world_memory = _memory()
    world_memory["events"][0]["branch_id"] = "missing_branch"

    diagnostics = validate_world_memory(world_memory, scene_graph=_scene())

    assert "M1012" in _codes(diagnostics)
    invalid = next(item for item in diagnostics if item["code"] == "M1012")
    assert invalid["name"] == "invalid_event_branch"
    assert invalid["path"] == "/events/0/branch_id"


def test_world_memory_reports_event_missing_from_declared_branch() -> None:
    world_memory = _memory()
    removed_event_id = world_memory["branches"][0]["event_ids"].pop(0)
    assert world_memory["events"][0]["event_id"] == removed_event_id

    diagnostics = validate_world_memory(world_memory, scene_graph=_scene())

    assert "M1013" in _codes(diagnostics)
    invalid = next(item for item in diagnostics if item["code"] == "M1013")
    assert invalid["name"] == "event_missing_from_branch"
    assert invalid["path"] == "/events/0/branch_id"


def test_append_memory_event_rejects_missing_branch() -> None:
    world_memory = create_world_memory(_scene(), summary="Initial empty continuity memory.")
    event = {
        "event_id": "mem_added_fact_001",
        "type": "fact",
        "scope": "object",
        "text": "This event names a missing branch.",
        "affected_ids": ["obj_astrolabe_table_001"],
        "branch_id": "missing_branch",
        "source": "unit_test",
    }

    updated, diagnostics = append_memory_event(world_memory, event, scene_graph=_scene())

    assert "M1012" in _codes(diagnostics)
    assert updated["events"] == [event]
    assert world_memory["events"] == []


def test_create_world_memory_from_scene_graph_is_valid() -> None:
    world_memory = create_world_memory(_scene(), summary="Initial empty continuity memory.")

    diagnostics = validate_world_memory(world_memory, scene_graph=_scene())

    assert diagnostics == []
    assert world_memory["schema_version"] == "lathe.world_memory.v1"
    assert world_memory["scene_id"] == "alchemist_observatory"
    assert world_memory["current_branch"] == "main"


def test_append_memory_event_returns_valid_copy_and_updates_branch() -> None:
    world_memory = create_world_memory(_scene(), summary="Initial empty continuity memory.")
    event = {
        "event_id": "mem_added_fact_001",
        "type": "fact",
        "scope": "object",
        "text": "The astrolabe table remains the focal interaction object.",
        "affected_ids": ["obj_astrolabe_table_001"],
        "branch_id": "main",
        "source": "unit_test",
    }

    updated, diagnostics = append_memory_event(world_memory, event, scene_graph=_scene())

    assert diagnostics == []
    assert world_memory["events"] == []
    assert updated["events"] == [event]
    assert updated["branches"][0]["event_ids"] == ["mem_added_fact_001"]


def test_append_memory_event_idempotent_does_not_duplicate_or_mutate_caller() -> None:
    world_memory = create_world_memory(_scene(), summary="Initial empty continuity memory.")
    event = {
        "event_id": "mem_added_fact_001",
        "type": "fact",
        "scope": "object",
        "text": "The astrolabe table remains central.",
        "affected_ids": ["obj_astrolabe_table_001"],
        "source": "unit_test",
    }

    first = append_memory_event_idempotent(world_memory, event, "patch-001")
    second = append_memory_event_idempotent(first, event, "patch-001")

    assert world_memory["events"] == []
    assert len(second["events"]) == 1
    assert second["events"][0]["metadata"]["idempotency_key"] == "patch-001"
    assert second["branches"][0]["event_ids"] == ["mem_added_fact_001"]


def test_redact_memory_payload_catches_nested_secret_fields() -> None:
    payload = {
        "schema_version": "lathe.world_memory.v1",
        "metadata": {
            "credentials": {
                "api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
                "nested": [{"password": "hunter2"}],
            }
        },
    }

    redacted = redact_memory_payload(payload)

    assert redacted["metadata"]["credentials"]["api_key"] == "[REDACTED]"
    assert redacted["metadata"]["credentials"]["nested"][0]["password"] == "[REDACTED]"
    assert payload["metadata"]["credentials"]["api_key"].startswith("sk-proj-")


def test_redact_memory_payload_catches_emails_tokens_and_phone_text() -> None:
    payload = {
        "text": (
            "Contact maker@example.com at +1 (415) 555-1212 with "
            "Bearer abcdefghijklmnopqrstuvwxyz or ghp_abcdefghijklmnopqrstuvwxyz123456."
        )
    }

    redacted = redact_memory_payload(payload)

    assert "maker@example.com" not in redacted["text"]
    assert "+1 (415) 555-1212" not in redacted["text"]
    assert "Bearer abcdefghijklmnopqrstuvwxyz" not in redacted["text"]
    assert "ghp_abcdefghijklmnopqrstuvwxyz123456" not in redacted["text"]
    assert redacted["text"].count("[REDACTED]") >= 4


def test_record_rejected_patch_creates_valid_redacted_memory_event() -> None:
    world_memory = create_world_memory(_scene(), summary="Rejected patch memory.")
    patch = {
        "schema_version": "lathe.scene_patch.v1",
        "patch_id": "patch_secret_reject_001",
        "scope": "object",
        "target_id": "obj_astrolabe_table_001",
        "instruction": "Use token sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "preserve": ["object_id"],
        "allowed_changes": ["metadata"],
        "operations": [
            {
                "op": "copy",
                "from": "/objects/1/state/cracked",
                "path": "/objects/0/state/copied_cracked",
            }
        ],
    }
    result = apply_scene_patch(_scene(), patch)

    updated = record_rejected_patch(world_memory, patch, result.rejected_operations, "scope mismatch")

    assert validate_world_memory(updated) == []
    event = updated["events"][0]
    assert event["metadata"]["status"] == "rejected"
    assert event["metadata"]["reason"] == "scope mismatch"
    assert event["metadata"]["rejected_patch"]["instruction"] == "Use token [REDACTED]"
    assert event["affected_ids"] == ["obj_astrolabe_table_001"]


def test_wonder_cli_validate_world_memory_with_scene_graph_success() -> None:
    result = _cli(
        "wonder",
        "validate-world-memory",
        str(EXAMPLE_MEMORY),
        "--scene-graph",
        str(EXAMPLE_SCENE),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["contract"] == "world_memory"
    assert payload["diagnostics"] == []


def test_wonder_cli_validate_world_memory_reports_scene_graph_link_errors(tmp_path: Path) -> None:
    world_memory = _memory()
    world_memory["continuity_constraints"][0]["affected_ids"].append("region_missing_001")
    invalid_path = tmp_path / "world_memory.json"
    invalid_path.write_text(json.dumps(world_memory), encoding="utf-8")

    result = _cli("wonder", "validate-world-memory", str(invalid_path), "--scene-graph", str(EXAMPLE_SCENE))

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["contract"] == "world_memory"
    assert "M1002" in _codes(payload["diagnostics"])


def test_wonder_cli_append_memory_event_is_idempotent(tmp_path: Path) -> None:
    world_memory = create_world_memory(_scene(), summary="CLI idempotent append.")
    event = {
        "event_id": "mem_cli_fact_001",
        "type": "fact",
        "scope": "object",
        "text": "The astrolabe table remains central.",
        "affected_ids": ["obj_astrolabe_table_001"],
        "source": "unit_test",
    }
    memory_path = tmp_path / "world_memory.json"
    event_path = tmp_path / "event.json"
    first_path = tmp_path / "world_memory.first.json"
    second_path = tmp_path / "world_memory.second.json"
    _write_json(memory_path, world_memory)
    _write_json(event_path, event)

    first = _cli(
        "wonder",
        "append-memory-event",
        str(memory_path),
        "--event",
        str(event_path),
        "--idempotency-key",
        "patch-001",
        "--out",
        str(first_path),
    )
    second = _cli(
        "wonder",
        "append-memory-event",
        str(first_path),
        "--event",
        str(event_path),
        "--idempotency-key",
        "patch-001",
        "--out",
        str(second_path),
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    updated = json.loads(second_path.read_text(encoding="utf-8"))
    assert len(updated["events"]) == 1
    assert updated["events"][0]["metadata"]["idempotency_key"] == "patch-001"


def test_wonder_cli_redact_memory_writes_redacted_copy(tmp_path: Path) -> None:
    raw_path = tmp_path / "memory.raw.json"
    out_path = tmp_path / "memory.redacted.json"
    _write_json(
        raw_path,
        {
            "text": "Email maker@example.com with Bearer abcdefghijklmnopqrstuvwxyz.",
            "metadata": {"api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz123456"},
        },
    )

    result = _cli("wonder", "redact-memory", str(raw_path), "--out", str(out_path))

    assert result.returncode == 0, result.stderr
    redacted = json.loads(out_path.read_text(encoding="utf-8"))
    assert "maker@example.com" not in redacted["text"]
    assert "Bearer abcdefghijklmnopqrstuvwxyz" not in redacted["text"]
    assert redacted["metadata"]["api_key"] == "[REDACTED]"
