from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lathe.scene import check_scene_graph, load_and_check_scene_graph
from lathe.wonder import (
    decompose_dream_brief,
    load_and_check_brief_scene,
    lower_dream_brief_to_scene_graph,
    validate_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_BRIEF = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "dream_brief.json"
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"
UNDERWATER_BRIEF = REPO_ROOT / "examples" / "wonder" / "underwater_train_station" / "dream_brief.json"
ROBX_MALL_BRIEF = REPO_ROOT / "examples" / "wonder" / "abandoned_roblox_mall" / "dream_brief.json"


def _brief() -> dict:
    return json.loads(EXAMPLE_BRIEF.read_text(encoding="utf-8"))


def _brief_at(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _ids(scene_graph: dict, collection: str, field: str) -> list[str]:
    return [item[field] for item in scene_graph[collection]]


def test_decompose_dream_brief_emits_stable_planning_model() -> None:
    brief = _brief()

    decomposition = decompose_dream_brief(brief).as_dict()

    assert decomposition["schema_version"] == "lathe.dream_brief_decomposition.v1"
    assert decomposition["brief_id"] == "alchemist_observatory"
    assert decomposition["scene_id"] == "alchemist_observatory"
    assert decomposition["primary_region"]["region_id"] == "region_alchemist_observatory_main"
    assert [item["object_id"] for item in decomposition["elements"]] == [
        "obj_rib_architecture_001",
        "obj_central_astrolabe_002",
        "obj_moonlight_beam_003",
        "obj_sealed_archive_door_004",
    ]
    assert decomposition["focal_object_id"] == "obj_central_astrolabe_002"
    assert {camera["framing"] for camera in decomposition["camera_plan"]} >= {"cinematic_wide", "inspection", "topdown"}
    assert decomposition["export_targets"] == ["scene_graph", "lathe_source", "glb", "scene_package"]


def test_lower_dream_brief_emits_valid_scene_graph_contract() -> None:
    brief = _brief()

    scene_graph = lower_dream_brief_to_scene_graph(brief)

    assert validate_contract("scene_graph", scene_graph) == []
    assert check_scene_graph(scene_graph, root=EXAMPLE_BRIEF.parent) == []
    assert scene_graph["schema_version"] == "lathe.scene_graph.v1"
    assert scene_graph["scene_id"] == brief["brief_id"]
    assert scene_graph["brief_id"] == brief["brief_id"]
    assert scene_graph["style_bible"]["palette"] == brief["style"]["palette"]
    assert scene_graph["style_bible"]["avoid"] == [
        *brief["style"]["avoid_styles"],
        *brief["avoid"],
    ]


def test_lower_dream_brief_represents_required_elements_with_stable_ids() -> None:
    brief = _brief()

    scene_graph = lower_dream_brief_to_scene_graph(brief)

    object_ids = _ids(scene_graph, "objects", "object_id")
    assert object_ids == [
        "obj_rib_architecture_001",
        "obj_central_astrolabe_002",
        "obj_moonlight_beam_003",
        "obj_sealed_archive_door_004",
    ]
    assert [item["lathe_asset"] for item in scene_graph["objects"]] == [
        item["id"] for item in brief["required_elements"]
    ]
    assert scene_graph["layout"]["focal_point"] == "obj_central_astrolabe_002"
    assert {camera["framing"] for camera in scene_graph["cameras"]} >= {"cinematic_wide", "inspection", "topdown"}
    assert len(scene_graph["curiosity_anchors"]) >= 2
    assert len(scene_graph["hidden_state"]) == len(brief["curiosity_goals"])


def test_underwater_train_station_brief_lowers_to_multi_room_scene() -> None:
    brief = _brief_at(UNDERWATER_BRIEF)

    decomposition = decompose_dream_brief(brief).as_dict()
    scene_graph = lower_dream_brief_to_scene_graph(brief)

    assert validate_contract("scene_graph", scene_graph) == []
    assert check_scene_graph(scene_graph, root=UNDERWATER_BRIEF.parent) == []
    assert decomposition["layout_profile"] == {
        "kind": "multi_room_seed",
        "room_size": [24.0, 18.0, 6.0],
        "density": "dense",
        "main_path_width": 1.5,
    }
    assert [item["object_id"] for item in decomposition["elements"]] == [
        "obj_glass_tube_concourse_001",
        "obj_stopped_bathysphere_train_002",
        "obj_platform_edge_markers_003",
        "obj_red_signal_lamps_004",
        "obj_sealed_service_hatch_005",
        "obj_coral_platform_growth_006",
    ]
    assert decomposition["focal_object_id"] == "obj_stopped_bathysphere_train_002"
    assert [item["role"] for item in scene_graph["objects"]] == [
        "architecture",
        "hero_prop",
        "navigation",
        "light_fixture",
        "interactive",
        "dressing_prop",
    ]
    assert scene_graph["lights"][0]["type"] == "emissive_practical"
    assert {camera["framing"] for camera in scene_graph["cameras"]} >= {
        "cinematic_wide",
        "inspection",
        "topdown",
    }
    assert {item["target"] for item in scene_graph["exports"]} == {"scene_graph", "scene_package", "glb"}
    assert len(scene_graph["curiosity_anchors"]) == 3
    assert len(scene_graph["hidden_state"]) == 3


def test_abandoned_roblox_mall_brief_lowers_to_roblox_manifest_scene() -> None:
    brief = _brief_at(ROBX_MALL_BRIEF)

    decomposition = decompose_dream_brief(brief).as_dict()
    scene_graph = lower_dream_brief_to_scene_graph(brief)

    assert validate_contract("scene_graph", scene_graph) == []
    assert check_scene_graph(scene_graph, root=ROBX_MALL_BRIEF.parent) == []
    assert decomposition["layout_profile"] == {
        "kind": "single_room",
        "room_size": [12.0, 8.0, 5.5],
        "density": "medium",
        "main_path_width": 1.4,
    }
    assert [item["object_id"] for item in decomposition["elements"]] == [
        "obj_storefront_row_001",
        "obj_dry_fountain_002",
        "obj_broken_escalator_003",
        "obj_security_gate_004",
    ]
    assert decomposition["focal_object_id"] == "obj_dry_fountain_002"
    assert scene_graph["layout"]["focal_point"] == "obj_dry_fountain_002"
    assert scene_graph["exports"][1] == {
        "target": "roblox_manifest",
        "format": "json",
        "path": "dist/exports/abandoned_roblox_mall.roblox_manifest.json",
        "metadata": {
            "planned_only": True,
            "lowered_from": "dream_brief",
        },
    }
    assert {camera["camera_id"] for camera in scene_graph["cameras"]} >= {
        "camera_reveal",
        "camera_gate_detail",
        "camera_debug_topdown",
    }
    assert scene_graph["style_bible"]["avoid"] == [
        *brief["style"]["avoid_styles"],
        *brief["avoid"],
    ]
    assert len(scene_graph["curiosity_anchors"]) == 3


def test_lower_dream_brief_keeps_identity_stable_when_prompt_text_changes() -> None:
    brief = _brief()
    changed = json.loads(json.dumps(brief))
    changed["source_prompt"] = "A different sentence for the same structured scene."

    original_scene = lower_dream_brief_to_scene_graph(brief)
    changed_scene = lower_dream_brief_to_scene_graph(changed)

    assert _ids(changed_scene, "regions", "region_id") == _ids(original_scene, "regions", "region_id")
    assert _ids(changed_scene, "objects", "object_id") == _ids(original_scene, "objects", "object_id")
    assert _ids(changed_scene, "cameras", "camera_id") == _ids(original_scene, "cameras", "camera_id")
    assert _ids(changed_scene, "materials", "material_id") == _ids(original_scene, "materials", "material_id")


def test_wonder_cli_lower_brief_writes_checked_scene_graph(tmp_path: Path) -> None:
    out_path = tmp_path / "scene_graph.json"

    result = _cli("wonder", "lower-brief", str(EXAMPLE_BRIEF), "--out", str(out_path))

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["contract"] == "scene_graph"
    assert payload["source_contract"] == "dream_brief"
    assert payload["check"] == "dream_brief_lowering"
    assert payload["diagnostics"] == []
    assert out_path.exists()

    scene_graph, diagnostics = load_and_check_scene_graph(out_path)
    assert diagnostics == []
    assert scene_graph["brief_id"] == "alchemist_observatory"


def test_wonder_cli_decompose_brief_emits_model() -> None:
    result = _cli("wonder", "decompose-brief", str(EXAMPLE_BRIEF))

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["contract"] == "dream_brief_decomposition"
    assert payload["decomposition"]["focal_object_id"] == "obj_central_astrolabe_002"
    assert payload["diagnostics"] == []


def test_wonder_cli_brief_to_scene_alias_writes_checked_scene_graph(tmp_path: Path) -> None:
    out_path = tmp_path / "scene_graph.json"

    result = _cli("wonder", "brief-to-scene", str(EXAMPLE_BRIEF), "--out", str(out_path))

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["contract"] == "scene_graph"
    assert out_path.exists()
    _scene_graph, diagnostics = load_and_check_scene_graph(out_path)
    assert diagnostics == []


def test_load_and_check_brief_scene_accepts_authored_example_scene() -> None:
    _brief_payload, _scene_graph, diagnostics = load_and_check_brief_scene(EXAMPLE_BRIEF, EXAMPLE_SCENE)

    assert diagnostics == []


def test_wonder_cli_check_brief_scene_success() -> None:
    result = _cli("wonder", "check-brief-scene", str(EXAMPLE_BRIEF), str(EXAMPLE_SCENE))

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["check"] == "brief_scene_consistency"
    assert payload["diagnostics"] == []


def test_wonder_cli_check_brief_scene_reports_obvious_mismatch(tmp_path: Path) -> None:
    scene_graph = json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))
    scene_graph["brief_id"] = "wrong_brief"
    scene_graph["exports"] = [item for item in scene_graph["exports"] if item["target"] != "glb"]
    scene_graph["style_bible"]["avoid"] = ["watercolor"]
    scene_path = tmp_path / "scene_graph.json"
    scene_path.write_text(json.dumps(scene_graph), encoding="utf-8")

    result = _cli("wonder", "check-brief-scene", str(EXAMPLE_BRIEF), str(scene_path))

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    codes = {diagnostic["code"] for diagnostic in payload["diagnostics"]}
    assert {"W2001", "W2003", "W2015"} <= codes
