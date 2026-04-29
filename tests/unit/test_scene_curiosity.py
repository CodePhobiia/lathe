from __future__ import annotations

import copy
import json
from pathlib import Path

from lathe.scene.curiosity import expand_anchor, summarize_curiosity
from lathe.scene.graph import check_scene_graph
from lathe.wonder import validate_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def _object_transforms(scene_graph: dict) -> dict[str, dict]:
    return {item["object_id"]: copy.deepcopy(item["transform"]) for item in scene_graph["objects"]}


def test_summarize_curiosity_emits_cards_with_hidden_state_and_continuity() -> None:
    summary = summarize_curiosity(_scene())

    assert summary["schema_version"] == "lathe.curiosity_summary.v1"
    assert summary["scene_id"] == "alchemist_observatory"
    assert summary["diagnostics"] == []
    assert [card["anchor_id"] for card in summary["cards"]] == [
        "curiosity_sealed_archive",
        "curiosity_warm_lens",
    ]

    warm_lens = next(card for card in summary["cards"] if card["anchor_id"] == "curiosity_warm_lens")
    assert warm_lens["visible_clue"] == "The black glass lens glows faintly even though the room is abandoned."
    assert warm_lens["suggested_user_actions"] == ["inspect lens", "align astrolabe", "open star map"]
    assert warm_lens["linked_hidden_ids"] == ["hidden_warm_lens_truth"]
    assert warm_lens["hidden_state"][0]["reveal_condition"] == "User inspects the lens or aligns the astrolabe."
    assert [option["option_id"] for option in warm_lens["expansion_options"]] == [
        "hidden_star_map",
        "opened_archive",
    ]
    assert "preserve table position" in warm_lens["continuity_constraints"]


def test_expand_anchor_preserves_hidden_state_reveal_conditions() -> None:
    scene_graph = _scene()
    before_hidden_state = copy.deepcopy(scene_graph["hidden_state"])

    result = expand_anchor(scene_graph, "curiosity_warm_lens", "hidden_star_map")

    assert result.diagnostics == []
    assert result.scene_graph["hidden_state"] == before_hidden_state
    assert result.scene_graph["hidden_state"][0]["reveal_condition"] == "User inspects the lens or aligns the astrolabe."
    assert scene_graph["hidden_state"] == before_hidden_state


def test_expand_anchor_generates_alchemist_observatory_branch_graph() -> None:
    scene_graph = _scene()

    result = expand_anchor(scene_graph, "curiosity_sealed_archive", "forbidden_archive")

    assert result.diagnostics == []
    assert result.ok is True
    assert result.scene_graph is not scene_graph
    assert result.scene_graph["version"] == scene_graph["version"] + 1
    assert result["version"] == scene_graph["version"] + 1
    assert "region_curiosity_sealed_archive_forbidden_archive" in {
        item["region_id"] for item in result.scene_graph["regions"]
    }
    assert {
        "obj_curiosity_sealed_archive_forbidden_archive_archive_room_shell",
        "obj_curiosity_sealed_archive_forbidden_archive_bone_shelf_kit",
        "obj_curiosity_sealed_archive_forbidden_archive_sealed_star_charts",
    } <= {item["object_id"] for item in result.scene_graph["objects"]}
    assert result.scene_graph["memory_events"][-1]["event_id"] == (
        "mem_curiosity_sealed_archive_forbidden_archive_expanded"
    )
    assert "hidden_archive_door_truth" in result.scene_graph["memory_events"][-1]["affected_ids"]
    assert validate_contract("scene_graph", result.scene_graph) == []
    assert check_scene_graph(result.scene_graph, root=EXAMPLE_SCENE.parent) == []


def test_expand_anchor_reports_invalid_anchor_option_and_target_diagnostics() -> None:
    missing_anchor = expand_anchor(_scene(), "curiosity_missing", "hidden_star_map")
    missing_option = expand_anchor(_scene(), "curiosity_warm_lens", "missing_option")

    invalid_target_scene = _scene()
    invalid_target_scene["curiosity_anchors"][0]["expansion_options"][0]["target_scope"] = "obj_missing_001"
    invalid_target = expand_anchor(invalid_target_scene, "curiosity_warm_lens", "hidden_star_map")
    summary = summarize_curiosity(invalid_target_scene)

    assert _codes(missing_anchor.diagnostics) == {"C2206"}
    assert _codes(missing_option.diagnostics) == {"C2207"}
    assert "C2204" in _codes(invalid_target.diagnostics)
    assert "C2204" in _codes(summary["diagnostics"])
    assert invalid_target.scene_graph == invalid_target_scene


def test_expand_anchor_preserves_existing_object_ids_and_transforms() -> None:
    scene_graph = _scene()
    original_object_ids = [item["object_id"] for item in scene_graph["objects"]]
    original_transforms = _object_transforms(scene_graph)

    result = expand_anchor(scene_graph, "curiosity_warm_lens", "opened_archive")

    assert result.diagnostics == []
    assert [item["object_id"] for item in result.scene_graph["objects"][: len(original_object_ids)]] == original_object_ids
    for object_id, transform in original_transforms.items():
        expanded_object = next(item for item in result.scene_graph["objects"] if item["object_id"] == object_id)
        assert expanded_object["transform"] == transform
    assert _object_transforms(scene_graph) == original_transforms
