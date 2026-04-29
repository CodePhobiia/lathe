from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from lathe.scene.graph import check_scene_graph
from lathe.scene.memory import redact_memory_payload
from lathe.scene.patch import apply_scene_patch
from lathe.scene.planner import validate_scene_plan_payload
from lathe.wonder import (
    build_repair_playbook,
    diagnose_for_llm,
    semantic_patch_request_to_scene_patch,
    validate_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"
BAD_OUTPUTS = REPO_ROOT / "docs" / "llm" / "bad_outputs"
BAD_SOURCE = BAD_OUTPUTS / "invalid_scene_source_bad_id.lth"
LLM_DOCS = REPO_ROOT / "docs" / "llm"
SCHEMA_LINKS = REPO_ROOT / "docs" / "llm" / "schema_links.md"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _json_fixture(name: str) -> dict:
    return json.loads((BAD_OUTPUTS / name).read_text(encoding="utf-8"))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def test_diagnose_for_llm_compacts_missing_id_schema_diagnostic() -> None:
    scene_graph = _scene()
    scene_graph["objects"][0].pop("object_id")

    summary = diagnose_for_llm(scene_graph)

    assert summary["status"] == "failed"
    assert summary["summary"]["errors"] == 1
    diagnostic = summary["diagnostics"][0]
    assert diagnostic["family"] == "schema"
    assert diagnostic["code"] == "WONDER_SCHEMA_VALIDATION"
    assert diagnostic["json_pointer"] == "/objects/0"
    assert diagnostic["next_action"] == "Add the missing required field at /objects/0/object_id."
    assert diagnostic["repair_options"] == [
        {
            "kind": "json_patch",
            "op": "add",
            "path": "/objects/0/object_id",
            "value_hint": "obj_<stable_snake_id>",
        }
    ]


def test_diagnose_for_llm_compacts_unsupported_scene_source_bridge_diagnostic() -> None:
    summary = diagnose_for_llm("scene hand_authored_scene {\n  version = 1\n}\n")

    diagnostic = summary["diagnostics"][0]
    assert diagnostic["code"] == "SS1002"
    assert diagnostic["family"] == "source_bridge"
    assert "embedded Scene Graph JSON" in diagnostic["next_action"]
    assert summary["repair_options"] == [
        {
            "kind": "source_bridge",
            "helper": "lathe.scene.source.scene_graph_to_source",
            "source_contract": "scene_graph",
            "schema": "schema/scene_graph.schema.json",
        }
    ]


def test_diagnose_for_llm_preserves_source_spans_for_generated_scene_source() -> None:
    summary = diagnose_for_llm(BAD_SOURCE.read_text(encoding="utf-8"))

    diagnostic = next(item for item in summary["diagnostics"] if item["json_pointer"] == "/objects/0/object_id")

    assert diagnostic["code"] == "WONDER_SCHEMA_VALIDATION"
    assert diagnostic["source_span"]["line"] >= 1
    assert diagnostic["source_span"]["column"] >= 1
    assert diagnostic["source_span"]["end_column"] > diagnostic["source_span"]["column"]
    assert "stable ID" in diagnostic["next_action"] or "canonical JSON Schema" in diagnostic["next_action"]


def test_diagnose_for_llm_suggests_preserve_constraints_for_scene_patch() -> None:
    patch = {
        "schema_version": "lathe.scene_patch.v1",
        "patch_id": "patch_missing_preserve_001",
        "scope": "object",
        "target_id": "obj_astrolabe_table_001",
        "instruction": "Make the table feel more sacred while keeping continuity.",
        "allowed_changes": ["style", "metadata"],
    }

    summary = diagnose_for_llm(patch)

    diagnostic = summary["diagnostics"][0]
    assert diagnostic["code"] == "WONDER_SCHEMA_VALIDATION"
    assert diagnostic["json_pointer"] == "/"
    assert diagnostic["repair_options"] == [
        {
            "kind": "json_patch",
            "op": "add",
            "path": "/preserve",
            "value_hint": [
                "object_id",
                "region",
                "transform.position",
                "transform.rotation",
                "transform.scale",
            ],
        }
    ]


def test_diagnose_for_llm_emits_compact_duplicate_id_repair_option() -> None:
    scene_graph = _scene()
    scene_graph["objects"][1]["object_id"] = scene_graph["objects"][0]["object_id"]
    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    summary = diagnose_for_llm({"payload": scene_graph, "diagnostics": diagnostics})

    diagnostic = summary["diagnostics"][0]
    assert diagnostic["code"] == "S1001"
    assert "details" not in diagnostic
    assert diagnostic["repair_options"] == [
        {
            "kind": "json_patch",
            "op": "replace",
            "path": "/objects/1/object_id",
            "value_hint": "obj_<stable_snake_id>",
        }
    ]
    assert summary["repair_options"] == diagnostic["repair_options"]


def test_semantic_patch_request_to_scene_patch_defaults_safe_authoring_fields() -> None:
    scene_graph = _scene()

    patch = semantic_patch_request_to_scene_patch(
        {
            "scope": "object",
            "target_id": "obj_astrolabe_table_001",
            "change": "Increase sacred ornament and warm lens emphasis.",
        },
        scene_graph=scene_graph,
    )

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
    assert patch["continuity"] == {
        "mode": "preserve_selected_ids",
        "preserved_ids": ["obj_astrolabe_table_001"],
    }
    assert validate_contract("scene_patch", patch) == []


def test_repair_playbook_accepts_diagnostics_list() -> None:
    diagnostics = [
        {
            "code": "SP1501",
            "name": "patch_target_missing",
            "severity": "error",
            "contract": "scene_patch",
            "path": "/target_id",
            "message": "Scene Patch object target 'obj_missing_001' was not found.",
            "repair_hint": "Choose an existing target_id for the object scope.",
            "source_span": {"file": "patch.json", "line": 4, "column": 16},
        }
    ]

    playbook = build_repair_playbook(diagnostics)

    assert validate_contract("llm_repair_playbook", playbook) == []
    assert playbook["schema_version"] == "lathe.llm_repair_playbook.v1"
    step = playbook["steps"][0]
    assert step["diagnostic_name"] == "patch_target_missing"
    assert step["diagnostic_code"] == "SP1501"
    assert step["path"] == "/target_id"
    assert step["source_span"]["line"] == 4
    assert "existing target_id" in step["instruction"]


def test_repair_playbook_accepts_wonder_report_wrapper() -> None:
    wrapper = {
        "ok": False,
        "contract": "scene_plan",
        "diagnostics": [
            {
                "code": "SP3002",
                "name": "missing_render_task",
                "severity": "error",
                "path": "/render_tasks",
                "message": "Scene Plan must include at least one deterministic render task.",
            }
        ],
    }

    playbook = build_repair_playbook(wrapper)

    assert playbook["summary"] == {"diagnostics": 1, "steps": 1, "omitted": 0}
    assert playbook["steps"][0]["path"] == "/render_tasks"
    assert "render" in playbook["steps"][0]["instruction"].lower()


def test_repair_playbook_unknown_diagnostic_uses_safe_generic_instruction() -> None:
    playbook = build_repair_playbook(
        [
            {
                "code": "W9999",
                "severity": "error",
                "path": "/mystery",
                "message": "A future diagnostic appeared.",
            }
        ]
    )

    step = playbook["steps"][0]
    assert step["diagnostic_name"] == "W9999"
    assert step["example_patch"] == {}
    assert step["instruction"] == "Inspect the diagnostic path, make the smallest schema-valid correction, then rerun the validator."


def test_canonical_schema_links_reference_existing_files_or_validator_backed_entries() -> None:
    text = SCHEMA_LINKS.read_text(encoding="utf-8")
    required_names = {
        "Dream Brief",
        "Scene Graph",
        "Scene Patch",
        "Render Inspection",
        "World Memory",
        "Scene Plan",
        "Scene Assembly",
        "Render Comparison",
        "LLM Repair Playbook",
    }

    for name in required_names:
        assert name in text

    for line in text.splitlines():
        if not line.startswith("- "):
            continue
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", line)
        assert links or "validator-backed" in line
        for target in links:
            assert (SCHEMA_LINKS.parent / target).resolve().exists(), line


def test_llm_prompt_facing_docs_and_schema_pointers_exist() -> None:
    required_docs = {
        "lathe_authoring_rules.md",
        "authoring_rules.md",
        "repair_playbook.md",
        "schema_links.md",
        "bad_outputs/README.md",
        "good_outputs/README.md",
    }
    for relative in required_docs:
        assert (LLM_DOCS / relative).exists(), relative

    for filename, contract, schema_version, schema_name in (
        ("dream_brief_schema.json", "dream_brief", "lathe.dream_brief.v1", "dream_brief.schema.json"),
        ("scene_graph_schema.json", "scene_graph", "lathe.scene_graph.v1", "scene_graph.schema.json"),
        ("patch_schema.json", "scene_patch", "lathe.scene_patch.v1", "scene_patch.schema.json"),
    ):
        pointer = json.loads((LLM_DOCS / filename).read_text(encoding="utf-8"))
        canonical = (LLM_DOCS / pointer["canonical_schema"]).resolve()
        assert pointer["schema_pointer_version"] == "lathe.llm_schema_pointer.v1"
        assert pointer["contract"] == contract
        assert pointer["schema_version"] == schema_version
        assert canonical.name == schema_name
        assert canonical.exists()


def test_bad_scene_plan_missing_camera_fixture_reports_expected_category() -> None:
    plan = _json_fixture("invalid_scene_plan_missing_camera.json")
    expected = _json_fixture("invalid_scene_plan_missing_camera.expected_diagnostics.json")

    diagnostics = validate_scene_plan_payload(plan)

    assert {item["code"] for item in expected["diagnostics"]}.issubset({item["code"] for item in diagnostics})
    assert {item["name"] for item in expected["diagnostics"]}.issubset({item["name"] for item in diagnostics})


def test_bad_patch_unknown_target_fixture_reports_expected_category() -> None:
    patch = _json_fixture("invalid_patch_unknown_target.json")
    expected = _json_fixture("invalid_patch_unknown_target.expected_diagnostics.json")

    result = apply_scene_patch(_scene(), patch)

    assert {item["code"] for item in expected["diagnostics"]}.issubset({item["code"] for item in result.diagnostics})
    assert {item["name"] for item in expected["diagnostics"]}.issubset({item["name"] for item in result.diagnostics})


def test_bad_memory_with_secret_fixture_is_redacted() -> None:
    payload = _json_fixture("invalid_memory_with_secret.json")
    expected = _json_fixture("invalid_memory_with_secret.expected_diagnostics.json")

    redacted = redact_memory_payload(payload)

    assert expected["diagnostics"][0]["code"] == "WM_REDACTION_APPLIED"
    assert redacted["metadata"]["operator_email"] == "[REDACTED]"
    assert redacted["metadata"]["api_key"] == "[REDACTED]"
    assert "[REDACTED]" in redacted["events"][0]["text"]


def test_wonder_llm_cli_commands_emit_json(tmp_path: Path) -> None:
    invalid_scene = _scene()
    invalid_scene["objects"][0].pop("object_id")
    invalid_path = tmp_path / "invalid_scene_graph.json"
    invalid_path.write_text(json.dumps(invalid_scene), encoding="utf-8")

    diagnose_result = _cli("wonder", "diagnose-for-llm", str(invalid_path), "--contract", "scene_graph")

    assert diagnose_result.returncode == 0, diagnose_result.stderr
    diagnose_payload = json.loads(diagnose_result.stdout)
    assert diagnose_payload["schema_version"] == "lathe.llm_diagnostic_summary.v1"
    assert diagnose_payload["status"] == "failed"
    assert diagnose_payload["diagnostics"][0]["next_action"] == "Add the missing required field at /objects/0/object_id."

    diagnostics_path = tmp_path / "diagnostics.json"
    diagnostics_path.write_text(
        json.dumps(
            [
                {
                    "code": "SP1501",
                    "name": "patch_target_missing",
                    "severity": "error",
                    "path": "/target_id",
                    "message": "Scene Patch object target 'obj_missing_001' was not found.",
                }
            ]
        ),
        encoding="utf-8",
    )
    playbook_path = tmp_path / "repair_playbook.json"
    playbook_result = _cli(
        "wonder",
        "repair-playbook",
        "--diagnostics",
        str(diagnostics_path),
        "--out",
        str(playbook_path),
    )

    assert playbook_result.returncode == 0, playbook_result.stderr or playbook_result.stdout
    playbook_payload = json.loads(playbook_result.stdout)
    assert playbook_payload["ok"] is True
    assert playbook_payload["repair_playbook"]["schema_version"] == "lathe.llm_repair_playbook.v1"
    assert playbook_path.exists()

    request_path = tmp_path / "semantic_patch_request.json"
    request_path.write_text(
        json.dumps(
            {
                "scope": "object",
                "target_id": "obj_astrolabe_table_001",
                "instruction": "Make the table more sacred and less industrial.",
            }
        ),
        encoding="utf-8",
    )
    patch_path = tmp_path / "scene_patch.json"
    patch_result = _cli(
        "wonder",
        "apply-semantic-patch",
        str(request_path),
        "--scene-graph",
        str(EXAMPLE_SCENE),
        "--out",
        str(patch_path),
    )

    assert patch_result.returncode == 0, patch_result.stderr or patch_result.stdout
    patch_payload = json.loads(patch_result.stdout)
    assert patch_payload["ok"] is True
    assert patch_payload["patch"]["schema_version"] == "lathe.scene_patch.v1"
    assert patch_payload["patch"]["preserve"] == [
        "object_id",
        "region",
        "transform.position",
        "transform.rotation",
        "transform.scale",
    ]
    assert patch_path.exists()
