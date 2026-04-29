from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
from lathe.scene import (
    ROBLOX_ASSET_KIT_STACK_ID,
    ROBLOX_EXPORT_BUNDLE_VERSION,
    ROBLOX_LOW_POLY_PROFILE,
    build_roblox_manifest,
    export_roblox_asset_kit,
    get_roblox_manifest_schema,
    get_roblox_profile_schema,
    load_and_check_scene_graph,
    validate_roblox_manifest_payload,
    validate_roblox_profile,
    validate_roblox_profile_payload,
)
from lathe.wonder import load_and_validate_contract
from lathe.wonder.contracts import validate_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "abandoned_roblox_mall"


def _scene() -> dict:
    return json.loads((EXAMPLE_DIR / "scene_graph.json").read_text(encoding="utf-8"))


def _profile() -> dict:
    return json.loads((EXAMPLE_DIR / "roblox_profile.json").read_text(encoding="utf-8"))


def _example_asset_kit() -> dict:
    return json.loads((EXAMPLE_DIR / "roblox_asset_kit.example.json").read_text(encoding="utf-8"))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes(), usedforsecurity=False).hexdigest()


def test_roblox_profile_and_manifest_schemas_are_valid_json_schemas() -> None:
    jsonschema.Draft202012Validator.check_schema(get_roblox_profile_schema())
    jsonschema.Draft202012Validator.check_schema(get_roblox_manifest_schema())


def test_roblox_lowpoly_profile_constant_validates() -> None:
    assert validate_roblox_profile_payload(ROBLOX_LOW_POLY_PROFILE) == []


def test_abandoned_roblox_mall_example_validates_contracts() -> None:
    dream_brief, dream_diagnostics = load_and_validate_contract(
        "dream_brief", EXAMPLE_DIR / "dream_brief.json"
    )
    scene_graph, scene_diagnostics = load_and_check_scene_graph(EXAMPLE_DIR / "scene_graph.json")
    profile = _profile()

    assert dream_brief["constraints"]["platform"] == "roblox"
    assert dream_diagnostics == []
    assert scene_diagnostics == []
    assert validate_roblox_profile_payload(profile) == []
    assert validate_roblox_profile(scene_graph, profile) == []

    manifest = build_roblox_manifest(scene_graph, profile)

    assert manifest["schema_version"] == "lathe.roblox_manifest.v1"
    assert manifest["units"]["length"] == "studs"
    assert manifest["summary"]["scores"]["mobile"]["score"] == 100
    assert manifest["summary"]["scores"]["mobile"]["status"] == "passed"
    assert manifest["diagnostics"] == []
    assert validate_roblox_manifest_payload(manifest) == []


def test_roblox_profile_reports_deterministic_object_diagnostics() -> None:
    scene_graph = _scene()
    profile = _profile()
    scene_graph["objects"][0]["lathe_asset"] = "Bad Name"
    scene_graph["objects"][0]["state"]["triangle_count"] = 6000
    scene_graph["objects"][1]["state"]["mesh_count"] = 2
    scene_graph["objects"][1]["state"]["max_texture_resolution"] = 2048
    scene_graph["objects"][2]["state"].pop("collision")
    scene_graph["objects"][3]["state"].pop("pivot")
    scene_graph["objects"][3]["transform"]["position"][0] = 5.25

    diagnostics = validate_roblox_profile(scene_graph, profile)

    assert {
        "RB1001",
        "RB2001",
        "RB2003",
        "RB2005",
        "RB3001",
        "RB4001",
        "RB5001",
    } <= _codes(diagnostics)
    by_code = {diagnostic["code"]: diagnostic for diagnostic in diagnostics}
    assert by_code["RB1001"]["path"] == "/objects/0/lathe_asset"
    assert by_code["RB2001"]["path"] == "/objects/0/state/triangle_count"
    assert by_code["RB2003"]["path"] == "/objects/1/state/mesh_count"
    assert by_code["RB2005"]["path"] == "/objects/1/state/max_texture_resolution"
    assert by_code["RB3001"]["path"] == "/objects/2"
    assert by_code["RB4001"]["path"] == "/objects/3"
    assert by_code["RB5001"]["path"] == "/objects/3/transform/position"


def test_roblox_profile_reports_scene_budget_overages_from_metadata() -> None:
    profile = copy.deepcopy(_profile())
    profile["budgets"]["max_scene_triangles"] = 1000

    diagnostics = validate_roblox_profile(_scene(), profile)

    assert "RB2002" in _codes(diagnostics)
    diagnostic = next(item for item in diagnostics if item["code"] == "RB2002")
    assert diagnostic["details"]["triangle_count"] == 13000
    assert diagnostic["details"]["max_scene_triangles"] == 1000


def test_roblox_manifest_preserves_diagnostics_and_score_components() -> None:
    scene_graph = _scene()
    scene_graph["objects"][0]["state"].pop("collision")
    scene_graph["objects"][0]["transform"]["position"][1] = 1.25

    manifest = build_roblox_manifest(scene_graph, _profile())

    assert {"RB3001", "RB5001"} <= _codes(manifest["diagnostics"])
    assert manifest["summary"]["errors"] == 2
    assert manifest["summary"]["scores"]["collision"]["status"] == "failed"
    assert manifest["summary"]["scores"]["snap_grid"]["status"] == "failed"
    assert manifest["summary"]["scores"]["mobile"]["status"] == "failed"
    assert validate_roblox_manifest_payload(manifest) == []


def test_roblox_asset_kit_example_declares_stack_and_outputs() -> None:
    example = _example_asset_kit()

    assert example["schema_version"] == "lathe.roblox_asset_kit_example.v1"
    assert example["stack_id"] == ROBLOX_ASSET_KIT_STACK_ID
    assert example["scene_graph"] == "scene_graph.json"
    assert example["profile"] == "roblox_profile.json"
    assert "exports/roblox/glb/abandoned_roblox_mall_roblox_asset_kit.glb" in example["expected_outputs"]
    assert "exports/roblox/import_instructions.md" in example["expected_outputs"]


def test_roblox_asset_kit_export_writes_glb_manifest_thumbnails_and_handoff(tmp_path: Path) -> None:
    report = export_roblox_asset_kit(_scene(), tmp_path, profile=_profile())

    assert report["schema_version"] == ROBLOX_EXPORT_BUNDLE_VERSION
    assert report["stack_id"] == ROBLOX_ASSET_KIT_STACK_ID
    assert report["status"] == "built"
    assert report["formats"]["glb"]["status"] == "built"
    assert report["formats"]["fbx"]["status"] == "handoff_required"
    assert report["diagnostics"] == []

    manifest_path = tmp_path / "exports" / "roblox" / "roblox_manifest.json"
    glb_path = tmp_path / "exports" / "roblox" / "glb" / "abandoned_roblox_mall_roblox_asset_kit.glb"
    thumbnail_path = tmp_path / "exports" / "roblox" / "thumbnails" / "scene_thumbnail.png"
    contact_sheet_path = tmp_path / "exports" / "roblox" / "thumbnails" / "object_contact_sheet.png"
    instructions_path = tmp_path / "exports" / "roblox" / "import_instructions.md"
    fbx_handoff_path = tmp_path / "exports" / "roblox" / "fbx" / "fbx_handoff.json"
    report_path = tmp_path / "reports" / "roblox_export_bundle.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fbx_handoff = json.loads(fbx_handoff_path.read_text(encoding="utf-8"))
    bundle = json.loads(report_path.read_text(encoding="utf-8"))

    assert validate_roblox_manifest_payload(manifest) == []
    assert validate_contract("roblox_export_bundle", report) == []
    assert validate_contract("roblox_export_bundle", bundle) == []
    assert validate_contract("roblox_fbx_handoff", fbx_handoff) == []
    assert glb_path.read_bytes()[:4] == b"glTF"
    assert thumbnail_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert contact_sheet_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "Roblox Asset Kit Import" in instructions_path.read_text(encoding="utf-8")
    assert fbx_handoff["status"] == "handoff_required"
    assert bundle["stack_id"] == ROBLOX_ASSET_KIT_STACK_ID
    for artifact in report["artifacts"]:
        assert (tmp_path / artifact["path"]).exists(), artifact
    assert not list(tmp_path.rglob("*.fbx"))
    assert not list(tmp_path.rglob("*.rbxmx"))


def test_roblox_asset_kit_export_is_deterministic(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"

    export_roblox_asset_kit(_scene(), left, profile=_profile())
    export_roblox_asset_kit(_scene(), right, profile=_profile())

    relative_paths = (
        "exports/roblox/roblox_manifest.json",
        "exports/roblox/glb/abandoned_roblox_mall_roblox_asset_kit.glb",
        "exports/roblox/glb/abandoned_roblox_mall_roblox_asset_kit.object_index.json",
        "exports/roblox/thumbnails/scene_thumbnail.png",
        "exports/roblox/thumbnails/object_contact_sheet.png",
        "exports/roblox/import_instructions.md",
        "exports/roblox/fbx/fbx_handoff.json",
        "reports/roblox_export_bundle.json",
    )

    for relative_path in relative_paths:
        assert _sha256(left / relative_path) == _sha256(right / relative_path), relative_path


def test_roblox_asset_kit_failed_export_removes_stale_success_artifacts(tmp_path: Path) -> None:
    export_roblox_asset_kit(_scene(), tmp_path, profile=_profile())
    glb_path = tmp_path / "exports" / "roblox" / "glb" / "abandoned_roblox_mall_roblox_asset_kit.glb"
    thumbnail_path = tmp_path / "exports" / "roblox" / "thumbnails" / "scene_thumbnail.png"
    handoff_path = tmp_path / "exports" / "roblox" / "fbx" / "fbx_handoff.json"
    assert glb_path.exists()
    assert thumbnail_path.exists()
    assert handoff_path.exists()

    profile = _profile()
    profile["budgets"]["max_mesh_triangles"] = 1
    report = export_roblox_asset_kit(_scene(), tmp_path, profile=profile)

    assert report["status"] == "failed"
    assert report["formats"]["glb"]["status"] == "not_built"
    assert report["formats"]["fbx"]["status"] == "not_built"
    assert "RB2001" in _codes(report["diagnostics"])
    assert not glb_path.exists()
    assert not thumbnail_path.exists()
    assert not handoff_path.exists()
    assert validate_contract("roblox_export_bundle", report) == []


def test_scene_roblox_export_cli_writes_asset_kit_bundle(tmp_path: Path) -> None:
    result = _cli(
        "scene",
        "roblox-export",
        str(EXAMPLE_DIR / "scene_graph.json"),
        "--profile",
        str(EXAMPLE_DIR / "roblox_profile.json"),
        "--out",
        str(tmp_path),
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["ok"] is True
    assert payload["report"]["stack_id"] == ROBLOX_ASSET_KIT_STACK_ID
    assert (tmp_path / "exports" / "roblox" / "roblox_manifest.json").exists()
    assert (tmp_path / "exports" / "roblox" / "glb" / "abandoned_roblox_mall_roblox_asset_kit.glb").exists()
