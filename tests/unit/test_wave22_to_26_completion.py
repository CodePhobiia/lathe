"""Waves 22–26 completion tests: repair gate + scene compose + variation + engine validation + wonder."""

from __future__ import annotations

from lathe.authoring.variation import (
    analyze_variation,
    signature_for_construction_graph,
)
from lathe.repair_loop_gate import (
    demonstrate_repair_loop,
    gate_class_anchor_failure,
)
from lathe.runtime.asset_contract import (
    AssetRuntimeContract,
    LODEntry,
    RigJoint,
    SocketBinding,
)
from lathe.runtime.engine_adapters import emit_all_engine_manifests
from lathe.runtime.engine_validator import (
    validate_all_engine_manifests,
    validate_engine_manifest,
    validate_hinge_physics,
)
from lathe.scene.kit_graph import ArchetypeReference, KitGraph
from lathe.scene.scene_compose import compose_scene_from_kit, composition_to_dict
from lathe.wonder.wonder_cli import (
    plan_wonder_build,
    quick_wonder_request_from_prompt,
)


# Wave 22 — Repair gate


def test_gate_returns_trigger_for_class_anchor_failure() -> None:
    bundle = {
        "diagnostics": [
            {
                "code": "L6500",
                "name": "class_anchor_fail.crate_v1",
                "repair_actions": ["add_secondary_features"],
            }
        ]
    }
    trigger = gate_class_anchor_failure(bundle, budget_remaining=3)
    assert trigger is not None
    assert "add_secondary_features" in trigger.repair_actions
    assert trigger.budget_remaining == 3


def test_gate_returns_none_when_no_budget() -> None:
    bundle = {"diagnostics": [{"code": "L6500", "repair_actions": ["x"]}]}
    assert gate_class_anchor_failure(bundle, budget_remaining=0) is None


def test_gate_returns_none_when_no_class_anchor_failure() -> None:
    bundle = {"diagnostics": [{"code": "L6403", "repair_actions": ["x"]}]}
    assert gate_class_anchor_failure(bundle, budget_remaining=3) is None


def test_demonstrate_repair_loop_converges() -> None:
    """Mock loop showing diagnose → repair → rebuild → pass."""
    asset = {"name": "test_crate"}
    initial = {"state": "featureless"}

    def planner(asset, runtime, actions):
        return {"add": list(actions)}

    def rebuilder(asset, runtime, plan):
        return {**runtime, "state": "composed", "added": plan["add"]}

    def validator(asset, runtime):
        if runtime.get("state") == "composed":
            return {"diagnostics": []}
        return {
            "diagnostics": [
                {"code": "L6500", "repair_actions": ["add_secondary_features"]}
            ]
        }

    result = demonstrate_repair_loop(asset, initial, planner, rebuilder, validator)
    assert result.converged is True
    assert result.rounds == 1
    assert "add_secondary_features" in result.repair_actions_applied


# Wave 23 — (LOD on-disk emission is covered via multi_lod_emission in Wave 19)


# Wave 24 — Scene compose + variation


def test_compose_scene_emits_instances_per_archetype() -> None:
    kit = KitGraph(
        kit_id="test_kit",
        visual_language_id="utility_industrial_v1",
        archetypes=(
            ArchetypeReference(
                role="crate",
                source_lth="examples/industrial_crate.lth",
                asset_name="industrial_crate",
                repetition_limit=4,
                condition_distribution=(0.1, 0.7),
            ),
            ArchetypeReference(
                role="door",
                source_lth="examples/mechanical_door.lth",
                asset_name="mechanical_door",
                repetition_limit=2,
                condition_distribution=(0.2, 0.5),
            ),
        ),
    )
    composition = compose_scene_from_kit(kit, world_seed=42)
    assert composition.instance_count() == 6
    crates = [i for i in composition.instances if i.archetype_role == "crate"]
    doors = [i for i in composition.instances if i.archetype_role == "door"]
    assert len(crates) == 4
    assert len(doors) == 2
    # Stratified conditions: first crate at low, last at high.
    assert crates[0].condition < crates[-1].condition
    # Per-instance seeds are unique.
    seeds = {i.seed for i in composition.instances}
    assert len(seeds) == 6


def test_compose_scene_deterministic_for_same_world_seed() -> None:
    kit = KitGraph(
        kit_id="test_kit",
        visual_language_id="utility_industrial_v1",
        archetypes=(
            ArchetypeReference(
                role="crate", source_lth="x", asset_name="c", repetition_limit=3,
            ),
        ),
    )
    c1 = compose_scene_from_kit(kit, world_seed=100)
    c2 = compose_scene_from_kit(kit, world_seed=100)
    assert composition_to_dict(c1) == composition_to_dict(c2)


def test_variation_analysis_detects_duplicates() -> None:
    sigs = ["a", "a", "b", "c", "d", "d", "d"]
    report = analyze_variation(sigs, diversity_threshold=0.7)
    assert report.seed_count == 7
    assert report.unique_signature_count == 4
    assert report.duplicate_count == 3
    assert report.passes_diversity_threshold is False  # 4/7 = 0.57 < 0.7


def test_variation_analysis_passes_on_distinct() -> None:
    sigs = ["a", "b", "c", "d", "e"]
    report = analyze_variation(sigs, diversity_threshold=0.7)
    assert report.diversity_ratio == 1.0
    assert report.passes_diversity_threshold is True


def test_signature_for_construction_graph_is_deterministic() -> None:
    graph = {
        "nodes": [{"node_id": "body", "node_type": "primary_volume", "attributes": {"shape": "rounded_box"}}],
        "edges": [],
    }
    s1 = signature_for_construction_graph(graph)
    s2 = signature_for_construction_graph(graph)
    assert s1 == s2

    # Different attrs → different signature.
    graph2 = {
        "nodes": [{"node_id": "body", "node_type": "primary_volume", "attributes": {"shape": "box"}}],
        "edges": [],
    }
    s3 = signature_for_construction_graph(graph2)
    assert s1 != s3


# Wave 25 — Engine validation


def _sample_contract() -> AssetRuntimeContract:
    return AssetRuntimeContract(
        asset_id="test_asset",
        lods=(LODEntry(lod_id="LOD0", glb_path="x.glb", target_tris=10000),),
        materials=("painted_steel",),
        sockets=(SocketBinding(socket_id="s1", parent_part="body"),),
        joints=(RigJoint(
            joint_id="hinge1", type="hinge",
            parent_part="frame", child_part="leaf",
            axis_world=(0.0, 0.0, 1.0),
            limits_deg=(-5.0, 105.0),
            default_angle_deg=0.0,
        ),),
    )


def test_engine_validator_passes_well_formed_manifests() -> None:
    contract = _sample_contract()
    manifests = emit_all_engine_manifests(contract)
    results = validate_all_engine_manifests(manifests)
    for engine, result in results.items():
        assert result.valid, f"{engine} validation failed: {result.notes} (missing: {result.missing_keys})"


def test_engine_validator_catches_unknown_engine() -> None:
    result = validate_engine_manifest("invented_engine", {"engine": "x"})
    assert not result.valid
    assert "unknown engine" in result.notes


def test_hinge_physics_validator_catches_inverted_limits() -> None:
    joint = {"axis_world": [0, 0, 1], "limits_deg": [180, -180], "default_angle_deg": 0}
    result = validate_hinge_physics(joint)
    assert not result.valid
    assert "inverted" in result.notes


def test_hinge_physics_validator_catches_zero_axis() -> None:
    joint = {"axis_world": [0, 0, 0], "limits_deg": [-10, 10], "default_angle_deg": 0}
    result = validate_hinge_physics(joint)
    assert not result.valid
    assert "zero magnitude" in result.notes


def test_hinge_physics_validator_accepts_valid_joint() -> None:
    joint = {"axis_world": [0, 0, 1], "limits_deg": [-5, 105], "default_angle_deg": 0}
    result = validate_hinge_physics(joint)
    assert result.valid


# Wave 26 — Wonder mode


def test_wonder_plan_builds_kit_from_prompt() -> None:
    request = quick_wonder_request_from_prompt(
        prompt="a steampunk loading bay with crates and doors",
        asset_classes={"crate": 6, "door": 2},
        visual_language="steampunk_workshop_v1",
        world_seed=42,
    )
    result = plan_wonder_build(request)
    assert result.planned_asset_count == 8
    assert result.composition.visual_language_id == "steampunk_workshop_v1"
    # 6 crates + 2 doors = 8 instances; each has a seed hierarchy.
    assert len(result.seed_hierarchies_by_instance) == 8
    assert len(result.construction_payloads_by_instance) == 8
    # Engine manifests cover all 5 by default.
    assert len(result.planned_engine_manifests) == 5


def test_wonder_plan_construction_payloads_carry_intent() -> None:
    request = quick_wonder_request_from_prompt(
        prompt="industrial crates",
        asset_classes={"crate": 3},
        visual_language="utility_industrial_v1",
        world_seed=1,
    )
    result = plan_wonder_build(request)
    first = next(iter(result.construction_payloads_by_instance.values()))
    assert first["from"] == "industrial_crate_family"
    assert first["build"]["shape"]["procedural"]["brief"]["visual_language"] == "utility_industrial_v1"
