"""Wave 11 tests: determinism + canonical repair operators."""

from __future__ import annotations

from lathe.determinism import (
    ReproducibilityManifest,
    SeedHierarchy,
    derive_subseed,
    manifest_from_build_state,
)
from lathe.determinism.seeds import derive_hierarchy
from lathe.repair_operators_v2 import (
    CANONICAL_REPAIR_OPERATORS,
    get_operator,
    validate_payload,
)


def test_derive_subseed_deterministic() -> None:
    s1 = derive_subseed(42, "kit:industrial_loading_bay_v1")
    s2 = derive_subseed(42, "kit:industrial_loading_bay_v1")
    assert s1 == s2
    s3 = derive_subseed(42, "kit:other_kit")
    assert s1 != s3


def test_derive_hierarchy_isolates_scopes() -> None:
    h1 = derive_hierarchy(world_seed=42, kit_id="bay_a", asset_id="crate_01")
    h2 = derive_hierarchy(world_seed=42, kit_id="bay_a", asset_id="crate_02")
    h3 = derive_hierarchy(world_seed=42, kit_id="bay_b", asset_id="crate_01")
    # Same world+kit, different asset → different archetype/instance seeds.
    assert h1.asset_archetype_seed != h2.asset_archetype_seed
    # Same world, different kit → different kit seeds → cascade differs.
    assert h1.kit_seed != h3.kit_seed
    # Same call → same result.
    assert h1.to_dict() == derive_hierarchy(42, "bay_a", "crate_01").to_dict()


def test_reproducibility_manifest_hash_stability() -> None:
    m = manifest_from_build_state(
        lathe_version="0.2.0rc1",
        shape_contract="lathe.shape.intent_mesh_handoff_v1",
        knowledge_pack_versions={"FamilyAlias": "v1", "CompositionPolicy": "v1"},
        world_seed=12345,
        asset_seed=678,
        shape_program_blob={"ops": [{"op": "solid.box"}]},
    )
    m2 = manifest_from_build_state(
        lathe_version="0.2.0rc1",
        shape_contract="lathe.shape.intent_mesh_handoff_v1",
        knowledge_pack_versions={"FamilyAlias": "v1", "CompositionPolicy": "v1"},
        world_seed=12345,
        asset_seed=678,
        shape_program_blob={"ops": [{"op": "solid.box"}]},
    )
    assert m.shape_graph_hash == m2.shape_graph_hash
    assert m.compiled_ir_hash == ""  # no IR blob supplied
    blob = m.to_dict()
    assert blob["world_seed"] == 12345
    assert blob["shape_graph_hash"]


def test_canonical_repair_operators_present() -> None:
    expected = {
        "insert_required_feature",
        "panelize_face",
        "add_reinforcement_pattern",
        "strengthen_silhouette",
        "assign_material_zone",
        "add_decal_zone",
        "increase_bevel_readability",
        "add_surface_wear",
        "promote_detail_to_geometry",
        "demote_detail_to_texture",
        "adjust_style_weights",
        "resample_variation",
    }
    assert expected.issubset(set(CANONICAL_REPAIR_OPERATORS.keys()))


def test_validate_payload_missing() -> None:
    missing = validate_payload("insert_required_feature", {})
    assert missing == ["role"]
    assert validate_payload("insert_required_feature", {"role": "handle"}) == []


def test_validate_payload_unknown_operator() -> None:
    missing = validate_payload("imaginary_operator", {})
    assert missing == ["unknown_operator:imaginary_operator"]


def test_repair_operator_targets_diversified() -> None:
    """Different operators target different graph stages."""
    targets = {op.mutation_target for op in CANONICAL_REPAIR_OPERATORS.values()}
    assert "construction_graph" in targets
    assert "style_overlay" in targets
    assert "seed_scope" in targets
