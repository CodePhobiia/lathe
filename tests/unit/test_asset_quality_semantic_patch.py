"""Phase 16 tests for semantic asset patching."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lathe.asset_quality.certification import MODE_STRICT, MODE_WARNING, certify_example, validate_example
from lathe.asset_quality.semantic_patch import (
    PATCH_SCHEMA_VERSION,
    apply_semantic_patch,
    compare_before_after,
    validate_patch_payload,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES_ROOT = _REPO_ROOT / "examples" / "asset_quality"
_HERO = _EXAMPLES_ROOT / "hero_sword"
_GOLDEN = _EXAMPLES_ROOT / "golden_industrial_crate"


def _patch_payload(operation: dict, *, preserve: list[str] | None = None) -> dict:
    return {
        "asset_id": "hero_sword",
        "operations": [operation],
        "preserve": preserve or ["construction_identity"],
        "schema_version": PATCH_SCHEMA_VERSION,
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_patch_validation_accepts_supported_operations() -> None:
    operations = [
        {
            "bound_nodes": ["crossguard"],
            "material": "gold_guard_trim",
            "operation": "modify_material",
            "target": "material_wear_graph.material_zones.brass_guard_trim",
        },
        {
            "operation": "adjust_proportion",
            "target": "silhouette_plan.proportion_rules.guard_width_to_blade_width",
            "value": 4.1,
        },
        {
            "mask": {
                "bound_edge_target": "blade.left_edge",
                "mask_id": "test_blade_nick",
                "mask_type": "convex_edge_wear",
            },
            "operation": "add_wear",
            "target": "material_wear_graph.wear_masks",
        },
        {
            "node": {
                "category": "focal_detail",
                "node_id": "test_guard_gem",
                "parent_id": "crossguard",
            },
            "operation": "add_detail",
            "target": "construction_graph.nodes",
        },
        {
            "keywords_add": ["obsidian"],
            "operation": "set_style",
            "target": "design_brief.style",
            "theme": "ancient obsidian hero sword",
        },
        {
            "operation": "set_platform_profile",
            "profile": {"target": "roblox_runtime_proxy"},
            "target": "design_brief.platform_profile",
        },
    ]

    for operation in operations:
        assert validate_patch_payload(_patch_payload(operation))["ok"] is True


def test_patch_validation_rejects_forbidden_targets_and_values() -> None:
    invalid_operations = [
        (
            {
                "operation": "adjust_proportion",
                "target": "raw_mesh.vertices",
                "value": 1.0,
            },
            "raw_mesh_or_source_patch_forbidden",
        ),
        (
            {
                "operation": "adjust_proportion",
                "target": "design_brief.asset.uses",
                "value": 1.0,
            },
            "touches_public_surface",
        ),
        (
            {
                "operation": "set_style",
                "target": "design_brief.lathe.shape.intent_mesh_handoff_v1",
                "theme": "bad",
            },
            "touches_shape_contract",
        ),
        (
            {
                "operation": "explode",
                "target": "design_brief.style",
                "value": "bad",
            },
            "invalid_operation",
        ),
        (
            {
                "operation": "adjust_proportion",
                "target": "silhouette_plan.proportion_rules.guard_width_to_blade_width",
                "value": lambda: None,
            },
            "non_serializable_value",
        ),
    ]

    for operation, reason in invalid_operations:
        result = validate_patch_payload(_patch_payload(operation))
        assert result["ok"] is False
        assert any(rejection["reason"] == reason for rejection in result["rejected_operations"])


def test_malformed_preserve_token_is_rejected() -> None:
    result = validate_patch_payload(
        _patch_payload(
            {
                "operation": "adjust_proportion",
                "target": "silhouette_plan.proportion_rules.guard_width_to_blade_width",
                "value": 4.1,
            },
            preserve=["blade.length", "unknown.identity"],
        )
    )

    assert result["ok"] is False
    assert any(diagnostic["reason"] == "malformed_preserve_token" for diagnostic in result["diagnostics"])


def test_wider_blade_patch_updates_proportions_and_preserves_identity(tmp_path: Path) -> None:
    out = tmp_path / "hero_sword_wider"

    result = apply_semantic_patch(_HERO, _HERO / "patches" / "wider_blade.json", out)

    assert result["ok"] is True
    assert result["preserve_checks"]["all_preserved"] is True
    silhouette = _read_json(out / "silhouette_plan.json")
    graph = _read_json(out / "construction_graph.json")
    assert silhouette["proportion_rules"]["guard_width_to_blade_width"] == 4.1
    blade = next(node for node in graph["nodes"] if node["node_id"] == "long_tapered_blade")
    assert blade["bounds"]["width"] == 0.108
    assert blade["bounds"]["height"] == 0.875
    warning = validate_example(out, mode=MODE_WARNING)
    assert warning["ok"] is True
    strict = validate_example(out, mode=MODE_STRICT)
    assert strict["gates"]["strict_blockers"] == ["real_bake_not_executed"]


def test_gold_guard_patch_changes_guard_material_only(tmp_path: Path) -> None:
    out = tmp_path / "hero_sword_gold_guard"

    result = apply_semantic_patch(_HERO, _HERO / "patches" / "gold_guard_trim.json", out)

    assert result["ok"] is True
    graph = _read_json(out / "construction_graph.json")
    zones = _read_json(out / "material_wear_graph.json")["material_zones"]
    refs = {node["node_id"]: node.get("material_zone_ref") for node in graph["nodes"]}
    assert refs["crossguard"] == "gold_guard_trim"
    assert refs["guard_socket_focal"] == "gold_guard_trim"
    assert refs["round_pommel"] == "brass_guard_trim"
    gold_zone = next(zone for zone in zones if zone["zone_id"] == "gold_guard_trim")
    assert gold_zone["bound_nodes"] == ["crossguard", "guard_socket_focal"]


def test_edge_battle_damage_patch_adds_blade_edge_wear_only(tmp_path: Path) -> None:
    out = tmp_path / "hero_sword_edge_damage"

    result = apply_semantic_patch(_HERO, _HERO / "patches" / "edge_battle_damage.json", out)

    assert result["ok"] is True
    masks = _read_json(out / "material_wear_graph.json")["wear_masks"]
    added = [mask for mask in masks if mask["mask_id"].startswith("blade_") and "battle_nicks" in mask["mask_id"]]
    assert {mask["bound_edge_target"] for mask in added} == {"blade.left_edge", "blade.right_edge"}
    assert {mask["bound_node_id"] for mask in added} == {"edge_wear_anchors"}


def test_roblox_safe_patch_tightens_budget_and_records_constraint(tmp_path: Path) -> None:
    out = tmp_path / "hero_sword_roblox"

    result = apply_semantic_patch(_HERO, _HERO / "patches" / "roblox_safe_profile.json", out)

    assert result["ok"] is True
    platform = _read_json(out / "design_brief.json")["platform_profile"]
    assert platform["target"] == "roblox_runtime_proxy"
    assert platform["triangle_budget_warning"] == 7000
    assert platform["triangle_budget_strict"] == 5000
    assert platform["phase16_profile"] == "roblox_safe_proxy"
    assert platform["mesh_regeneration_required"] is True


def test_preserve_conflict_fails_without_output(tmp_path: Path) -> None:
    out = tmp_path / "hero_sword_bad"
    payload = _patch_payload(
        {
            "bounds": {"height": 1.0},
            "node_id": "long_tapered_blade",
            "operation": "adjust_proportion",
            "target": "silhouette_plan.proportion_rules.guard_width_to_blade_width",
            "value": 4.1,
        },
        preserve=["blade.length"],
    )

    result = apply_semantic_patch(_HERO, payload, out)

    assert result["ok"] is False
    assert result["rejected_operations"][0]["reason"] == "patch_conflicts_with_preserve"
    assert not out.exists()


def test_compare_before_after_reports_semantic_and_preview_deltas(tmp_path: Path) -> None:
    out = tmp_path / "hero_sword_wider"
    apply_semantic_patch(_HERO, _HERO / "patches" / "wider_blade.json", out)
    comparison_path = out / "comparison.json"

    comparison = compare_before_after(_HERO, out, comparison_path)

    assert comparison_path.exists()
    assert comparison["asset_id"] == "hero_sword"
    assert comparison["flags"]["requires_human_review"] is True
    assert comparison["preview_sha256"]["changed"]
    assert comparison["strict_blockers"]["after"] == ["real_bake_not_executed"]


def test_cli_patch_and_compare_write_outputs(tmp_path: Path) -> None:
    out = tmp_path / "hero_sword_cli"
    comparison = out / "comparison.json"

    patch_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "lathe.cli",
            "asset-quality",
            "patch",
            "examples/asset_quality/hero_sword",
            "examples/asset_quality/hero_sword/patches/wider_blade.json",
            "--out",
            str(out),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert patch_run.returncode == 0, patch_run.stderr
    compare_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "lathe.cli",
            "asset-quality",
            "compare-before-after",
            "examples/asset_quality/hero_sword",
            str(out),
            "--out",
            str(comparison),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert compare_run.returncode == 0, compare_run.stderr
    assert (out / "patch_result.json").exists()
    assert comparison.exists()


def test_base_fixtures_keep_truthful_certification_claims() -> None:
    golden = certify_example(_GOLDEN)
    hero = certify_example(_HERO)

    assert golden["scores"]["total"] == 96
    assert hero["scores"]["total"] == 95
    for certificate in (golden, hero):
        assert certificate["claims"]["external_renderer_verified"] is False
        assert certificate["claims"]["real_high_low_bake_verified"] is False
        assert certificate["claims"]["certified_for_production_game_use"] is False
