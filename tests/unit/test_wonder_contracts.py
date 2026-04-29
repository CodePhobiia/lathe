from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
from lathe.wonder import (
    CONTRACT_SPECS,
    get_contract_schema,
    load_and_validate_contract,
    validate_contract,
    wonder_capabilities,
    wonder_status,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "wonder"


def _cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})},
        check=False,
    )


def test_wonder_schemas_are_valid_json_schemas() -> None:
    for contract_id in CONTRACT_SPECS:
        with_diagnostics = get_contract_schema(contract_id)
        jsonschema.Draft202012Validator.check_schema(with_diagnostics)


def test_alchemist_observatory_contract_examples_validate() -> None:
    examples = {
        "dream_brief": EXAMPLE_DIR / "dream_brief.json",
        "scene_graph": EXAMPLE_DIR / "scene_graph.json",
        "scene_patch": EXAMPLE_DIR / "scene_patch_more_sacred.json",
        "render_inspection": EXAMPLE_DIR / "render_inspection.example.json",
        "world_memory": EXAMPLE_DIR / "world_memory.json",
        "scene_manifest": EXAMPLE_DIR / "expected" / "scene_manifest.example.json",
        "wonder_report": EXAMPLE_DIR / "expected" / "wonder_report.example.json",
    }
    for contract_id, path in examples.items():
        with_diagnostics, diagnostics = load_and_validate_contract(contract_id, path)
        assert with_diagnostics["schema_version"] == CONTRACT_SPECS[contract_id].schema_version
        assert diagnostics == []


def test_scene_graph_requires_stable_object_identity() -> None:
    scene_graph = json.loads((EXAMPLE_DIR / "scene_graph.json").read_text(encoding="utf-8"))
    scene_graph["objects"][0]["object_id"] = "astrolabe_table"

    diagnostics = validate_contract("scene_graph", scene_graph)

    assert diagnostics
    assert diagnostics[0]["contract"] == "scene_graph"
    assert diagnostics[0]["path"] == "/objects/0/object_id"


def test_negative_schema_fixtures_fail_with_diagnostics() -> None:
    invalid_fixtures = {
        "scene_manifest": [
            FIXTURE_DIR / "invalid_scene_manifest_bad_object_id.json",
            FIXTURE_DIR / "invalid_scene_manifest_missing_objects.json",
        ],
        "scene_patch": [
            FIXTURE_DIR / "invalid_scene_patch_bad_scope.json",
        ],
    }

    for contract_id, paths in invalid_fixtures.items():
        for path in paths:
            _payload, diagnostics = load_and_validate_contract(contract_id, path)
            assert diagnostics, path
            assert all(diagnostic["contract"] == contract_id for diagnostic in diagnostics)


def test_schema_roundtrip_fixtures_validate_after_json_serialisation() -> None:
    roundtrip_fixtures = {
        "scene_manifest": FIXTURE_DIR / "roundtrip_scene_manifest.json",
        "wonder_report": FIXTURE_DIR / "roundtrip_wonder_report.json",
    }

    for contract_id, path in roundtrip_fixtures.items():
        payload, diagnostics = load_and_validate_contract(contract_id, path)
        assert diagnostics == []

        roundtripped = json.loads(json.dumps(payload, sort_keys=True))
        assert roundtripped == payload
        assert validate_contract(contract_id, roundtripped) == []


def test_wonder_cli_validation_success() -> None:
    result = _cli("wonder", "validate-scene", str(EXAMPLE_DIR / "scene_graph.json"))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["contract"] == "scene_graph"
    assert payload["diagnostics"] == []


def test_wonder_capabilities_are_machine_readable() -> None:
    payload = wonder_capabilities()

    assert payload["schema_version"] == "lathe.wonder_capabilities.v1"
    assert payload["capabilities"]["dream_brief_schema"] is True
    assert payload["capabilities"]["scene_graph_semantic_check_cli"] is True
    assert payload["capabilities"]["world_memory_schema"] is True
    assert payload["capabilities"]["scene_manifest_schema"] is True
    assert payload["capabilities"]["scene_build_report_schema"] is True
    assert payload["capabilities"]["wonder_report_schema"] is True
    assert payload["capabilities"]["deterministic_brief_to_scene_graph_lowering"] is True
    assert payload["capabilities"]["deterministic_scene_planning"] is True
    assert payload["capabilities"]["scene_asset_materialization"] is True
    assert payload["capabilities"]["scene_materialization_manifest_schema"] is True
    assert payload["capabilities"]["scene_quality_report_schema"] is True
    assert payload["capabilities"]["scene_assembly_ir"] is True
    assert payload["capabilities"]["scene_branching_helpers"] is True
    assert payload["capabilities"]["scene_repair_loop"] is True
    assert payload["capabilities"]["curiosity_expansion"] is True
    assert payload["capabilities"]["scene_benchmark_report_schema"] is True
    assert payload["capabilities"]["style_pack_schema"] is True
    assert payload["capabilities"]["layout_plan_schema"] is True
    assert payload["capabilities"]["game_readiness_schema"] is True
    assert payload["capabilities"]["asset_provenance_scene_schema"] is True
    assert payload["capabilities"]["scene_package_format"] is True
    assert payload["capabilities"]["scene_source_bridge"] is True
    assert payload["capabilities"]["scene_source_language"] is True
    assert payload["capabilities"]["scene_patch_application"] is True
    assert payload["capabilities"]["offline_scene_build_pipeline"] is True
    assert payload["capabilities"]["scene_build_pipeline"] is True
    assert payload["capabilities"]["scene_render_pipeline"] is True
    assert payload["capabilities"]["scene_export_pipeline"] is True
    assert payload["capabilities"]["blender_scene_render_pipeline"] is False
    assert payload["capabilities"]["blender_scene_export_pipeline"] is True
    assert payload["capabilities"]["roblox_profile"] is True
    assert payload["capabilities"]["roblox_manifest"] is True
    assert payload["capabilities"]["roblox_asset_kit_export"] is True
    assert {item["id"] for item in payload["contracts"]} == set(CONTRACT_SPECS)


def test_wonder_status_is_machine_readable_and_alpha_blocking() -> None:
    payload = wonder_status()

    assert payload["schema_version"] == "lathe.wonder_status.v1"
    assert payload["ok"] is True
    assert payload["readiness"]["score"] == 4
    assert payload["readiness"]["max_score"] == 10
    assert payload["readiness"]["alpha_gate_ready"] is False
    assert payload["readiness"]["task_boxes_truthful"] is True
    assert payload["evidence"]["ledger"] == "docs/wonder-readiness/evidence.md"
    assert "scripts/lathe_wonder_validate.ps1" in payload["evidence"]["validated_local_helpers"]
    assert "scripts/lathe_wonder_validate.sh" in payload["evidence"]["pending_posix_helpers"]
    assert "fresh_clone_or_ci_alpha_confirmation" in payload["evidence"]["open_gaps"]
    assert "blender_scene_render_pipeline" in payload["capability_summary"]["blocked_capabilities"]
    assert any(item["severity"] == "blocker" for item in payload["alpha_gate_blockers"])
    assert payload["capabilities"]["scene_render_pipeline"] is True
    assert payload["capabilities"]["blender_scene_render_pipeline"] is False
    assert {item["id"] for item in payload["contracts"]} == set(CONTRACT_SPECS)


def test_wonder_cli_capabilities_success() -> None:
    result = _cli("wonder", "capabilities")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "lathe.wonder_capabilities.v1"
    assert payload["capabilities"]["contract_validation_cli"] is True


def test_wonder_cli_status_success() -> None:
    result = _cli("wonder", "status")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "lathe.wonder_status.v1"
    assert payload["readiness"]["alpha_gate_ready"] is False
    assert payload["evidence"]["state"] == "review_snapshot_evidence_recorded_posix_and_alpha_gates_pending"


def test_wonder_cli_contract_commands_skip_optional_runtime_dependencies(tmp_path: Path) -> None:
    from lathe.scene.assembly import assemble_scene
    from lathe.scene.bench import benchmark_scene
    from lathe.scene.layout import plan_layout
    from lathe.scene.materialize import materialize_scene_assets
    from lathe.scene.package import init_scene_package
    from lathe.scene.planner import plan_scene
    from lathe.scene.provenance import ASSET_PROVENANCE_SCENE_VERSION
    from lathe.scene.repair import repair_scene_offline
    from lathe.scene.roblox import build_roblox_manifest
    from lathe.scene.style import extract_style_pack
    from lathe.scene.validators import run_scene_validators
    from lathe.scene.versioning import create_branch, diff_scene_graphs

    def write_fixture(name: str, payload: object) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    scene_graph = json.loads((EXAMPLE_DIR / "scene_graph.json").read_text(encoding="utf-8"))
    render_inspection = json.loads((EXAMPLE_DIR / "render_inspection.example.json").read_text(encoding="utf-8"))
    roblox_scene = json.loads(
        (REPO_ROOT / "examples" / "wonder" / "abandoned_roblox_mall" / "scene_graph.json").read_text(
            encoding="utf-8"
        )
    )
    roblox_profile = json.loads(
        (REPO_ROOT / "examples" / "wonder" / "abandoned_roblox_mall" / "roblox_profile.json").read_text(
            encoding="utf-8"
        )
    )
    roblox_export_bundle = {
        "schema_version": "lathe.roblox_export_bundle.v1",
        "stack_id": "lathe.stack.roblox_asset_kit_v1",
        "scene_id": "abandoned_roblox_mall",
        "profile_id": "roblox_lowpoly",
        "mode": "preview",
        "status": "built",
        "paths": {
            "root": "exports/roblox",
            "manifest": "exports/roblox/roblox_manifest.json",
            "glb_folder": "exports/roblox/glb",
            "fbx_folder": "exports/roblox/fbx",
            "thumbnails": "exports/roblox/thumbnails",
            "import_instructions": "exports/roblox/import_instructions.md",
        },
        "formats": {
            "glb": {"status": "built"},
            "fbx": {
                "status": "handoff_required",
                "reason": "Downstream FBX conversion is required.",
                "handoff_manifest": "exports/roblox/fbx/fbx_handoff.json",
            },
        },
        "manifest_summary": {"objects": 4},
        "artifacts": [
            {
                "target": "roblox_manifest",
                "format": "json",
                "path": "exports/roblox/roblox_manifest.json",
                "status": "built",
            }
        ],
        "diagnostics": [],
    }
    roblox_fbx_handoff = {
        "schema_version": "lathe.roblox_fbx_handoff.v1",
        "stack_id": "lathe.stack.roblox_asset_kit_v1",
        "scene_id": "abandoned_roblox_mall",
        "status": "handoff_required",
        "source_glb": "../glb/abandoned_roblox_mall_roblox_asset_kit.glb",
        "roblox_manifest": "../roblox_manifest.json",
        "recommended_tool": "Blender or Roblox Studio import tooling",
        "units": {"length": "studs"},
        "identity_requirement": "Preserve object names and Lathe object IDs from the Roblox manifest.",
    }
    style_pack = extract_style_pack(scene_graph)
    layout_plan = plan_layout(scene_graph, style_pack=style_pack)
    game_readiness = {
        "schema_version": "lathe.game_readiness.v1",
        "scene_id": "alchemist_observatory",
        "target": "generic_game",
        "objects": [
            {
                "object_id": "obj_astrolabe_table_001",
                "mobility": "static",
                "interactable": True,
                "collision": {"type": "box", "required": True},
                "pivot": {"mode": "base_center"},
            }
        ],
    }
    asset_provenance = {
        "schema_version": ASSET_PROVENANCE_SCENE_VERSION,
        "scene_id": "alchemist_observatory",
        "objects": [
            {
                "object_id": "obj_astrolabe_table_001",
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
                "target": "scene_package",
                "path": "exports/alchemist_observatory.lathepkg",
                "permission": "allowed",
                "source_object_ids": ["obj_astrolabe_table_001"],
            }
        ],
    }
    benchmark_timings = {
        "stages": {
            "brief": {"duration_ms": 1000},
            "scene_graph": {"duration_ms": 2000},
            "source_generation": {"duration_ms": 1000},
            "check_plan": {"duration_ms": 500},
            "preview_build": {"duration_ms": 5000},
            "preview_render": {"duration_ms": 1000},
            "patch_preview": {"duration_ms": 1000},
            "final_export": {"duration_ms": 1000},
        },
        "cache": {"hits": 1, "misses": 1, "writes": 1},
    }
    benchmark_scores = {
        "metrics": {
            "prompt_to_brief": 0.9,
            "brief_to_scene": 0.9,
            "parse_check": 1.0,
            "build_success": 1.0,
            "scene_validation": 0.9,
            "style_consistency": 0.9,
            "object_count_accuracy": 0.9,
            "render_quality": 0.9,
            "patch_success": 1.0,
            "continuity_preservation": 0.9,
            "export_validity": 1.0,
        }
    }
    package_manifest_path, _package_manifest = init_scene_package(
        tmp_path / "contract_package",
        scene_id="alchemist_observatory",
    )
    extended_fixtures = {
        "validate-plan": write_fixture("scene_plan.json", plan_scene(scene_graph)),
        "validate-scene-materialization-manifest": write_fixture(
            "scene_materialization_manifest.json",
            materialize_scene_assets(EXAMPLE_DIR / "scene_graph.json", tmp_path / "materialized_assets")["manifest"],
        ),
        "validate-scene-assembly": write_fixture("scene_assembly.json", assemble_scene(scene_graph)),
        "validate-scene-branch": write_fixture("scene_branch.json", create_branch(scene_graph, "Archive Expansion")),
        "validate-scene-diff": write_fixture("scene_diff.json", diff_scene_graphs(scene_graph, scene_graph)),
        "validate-scene-quality-report": write_fixture("scene_quality.json", run_scene_validators(scene_graph)),
        "validate-scene-repair-report": write_fixture(
            "scene_repair.json", repair_scene_offline(scene_graph, render_inspection, max_rounds=1).report
        ),
        "validate-scene-benchmark-report": write_fixture(
            "scene_benchmark.json", benchmark_scene(scene_graph, benchmark_timings, benchmark_scores)
        ),
        "validate-style-pack": write_fixture("style_pack.json", style_pack),
        "validate-layout-plan": write_fixture("layout_plan.json", layout_plan),
        "validate-game-readiness": write_fixture("game_readiness.json", game_readiness),
        "validate-asset-provenance-scene": write_fixture("asset_provenance.json", asset_provenance),
        "validate-package-manifest": package_manifest_path,
        "validate-roblox-manifest": write_fixture("roblox_manifest.json", build_roblox_manifest(roblox_scene, roblox_profile)),
        "validate-roblox-export-bundle": write_fixture("roblox_export_bundle.json", roblox_export_bundle),
        "validate-roblox-fbx-handoff": write_fixture("roblox_fbx_handoff.json", roblox_fbx_handoff),
    }
    guard = tmp_path / "sitecustomize.py"
    guard.write_text(
        """
import importlib.abc
import sys

_BLOCKED = ("trimesh", "bpy", "torch", "lathe.providers", "lathe.shape_providers")


class _BlockOptionalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in _BLOCKED or any(fullname.startswith(prefix + ".") for prefix in _BLOCKED):
            raise ImportError(f"blocked optional import: {fullname}")
        return None


sys.meta_path.insert(0, _BlockOptionalImports())
""",
        encoding="utf-8",
    )
    pythonpath = str(tmp_path)
    if os.environ.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + os.environ["PYTHONPATH"]
    examples = {
        "capabilities": (),
        "status": (),
        "validate-brief": (EXAMPLE_DIR / "dream_brief.json",),
        "decompose-brief": (EXAMPLE_DIR / "dream_brief.json",),
        "lower-brief": (EXAMPLE_DIR / "dream_brief.json", "--out", tmp_path / "lower_scene_graph.json"),
        "brief-to-scene": (EXAMPLE_DIR / "dream_brief.json", "--out", tmp_path / "brief_scene_graph.json"),
        "validate-scene": (EXAMPLE_DIR / "scene_graph.json",),
        "check-scene-graph": (EXAMPLE_DIR / "scene_graph.json",),
        "check-brief-scene": (EXAMPLE_DIR / "dream_brief.json", EXAMPLE_DIR / "scene_graph.json"),
        "validate-patch": (EXAMPLE_DIR / "scene_patch_more_sacred.json",),
        "validate-render-inspection": (EXAMPLE_DIR / "render_inspection.example.json",),
        "validate-world-memory": (EXAMPLE_DIR / "world_memory.json",),
        "validate-scene-manifest": (EXAMPLE_DIR / "expected" / "scene_manifest.example.json",),
        "validate-wonder-report": (EXAMPLE_DIR / "expected" / "wonder_report.example.json",),
        "validate-roblox-profile": (
            REPO_ROOT / "examples" / "wonder" / "abandoned_roblox_mall" / "roblox_profile.json",
        ),
    }
    examples.update({command: (path,) for command, path in extended_fixtures.items()})

    for command, paths in examples.items():
        args = ("wonder", command, *[str(path) for path in paths])
        result = _cli(*args, env={"PYTHONPATH": pythonpath})

        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        if not paths:
            assert payload["schema_version"] in {"lathe.wonder_capabilities.v1", "lathe.wonder_status.v1"}
        else:
            assert payload["ok"] is True
            assert payload["diagnostics"] == []


def test_wonder_cli_validation_failure_returns_diagnostics(tmp_path: Path) -> None:
    invalid = json.loads((EXAMPLE_DIR / "dream_brief.json").read_text(encoding="utf-8"))
    invalid.pop("scale")
    invalid_path = tmp_path / "invalid_dream_brief.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

    result = _cli("wonder", "validate-brief", str(invalid_path))

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["contract"] == "dream_brief"
    assert payload["diagnostics"]
    assert payload["diagnostics"][0]["code"] == "WONDER_SCHEMA_VALIDATION"


def test_wonder_cli_rejects_future_schema_version_with_clear_diagnostic(tmp_path: Path) -> None:
    invalid = json.loads((EXAMPLE_DIR / "dream_brief.json").read_text(encoding="utf-8"))
    invalid["schema_version"] = "lathe.dream_brief.v2"
    invalid_path = tmp_path / "future_dream_brief.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

    result = _cli("wonder", "validate-brief", str(invalid_path))

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["diagnostics"][0]["code"] == "WONDER_UNSUPPORTED_SCHEMA_VERSION"
    assert "supported version is 'lathe.dream_brief.v1'" in payload["diagnostics"][0]["message"]
