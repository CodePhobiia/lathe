"""Wave 6 contract tests: zone_binding + mask_compiler + pbr_composer + feature_ops_v2."""

from __future__ import annotations

from lathe.asset_quality.feature_ops_v2 import (
    PRIORITY_FEATURE_OPS,
    get_spec,
    validate_op_params,
)
from lathe.surface_graph.mask_compiler import (
    CANONICAL_MASK_NAMES,
    WearMaskRecipe,
    compile_mask_graph,
    condition_to_params,
)
from lathe.surface_graph.pbr_composer import (
    BUILTIN_ARCHETYPES,
    compose_pbr_channels,
    resolve_archetype,
)
from lathe.surface_graph.zone_binding import (
    ZoneTag,
    ZoneAtlas,
    FaceZoneAssignment,
    atlas_from_face_parts,
    group_faces_by_material_class,
)


def test_zone_atlas_groups_faces_by_material() -> None:
    atlas = ZoneAtlas(
        zones=(
            ZoneTag(zone_id="body", material_class="painted_steel"),
            ZoneTag(zone_id="trim", material_class="brass"),
        ),
        face_assignments=(
            FaceZoneAssignment(face_index=0, zone_id="body"),
            FaceZoneAssignment(face_index=1, zone_id="body"),
            FaceZoneAssignment(face_index=2, zone_id="trim"),
        ),
    )
    grouped = group_faces_by_material_class(atlas)
    assert grouped["painted_steel"] == [0, 1]
    assert grouped["brass"] == [2]


def test_atlas_from_face_parts_preserves_attribution() -> None:
    face_parts = ["body", "body", "handle", "body", "handle"]
    atlas = atlas_from_face_parts(face_parts, material_by_region={"body": "painted_steel", "handle": "rubber"})
    assert atlas.face_count() == 5
    assert atlas.faces_for_zone("body") == (0, 1, 3)
    assert atlas.faces_for_zone("handle") == (2, 4)


def test_condition_scalar_is_monotone() -> None:
    """condition 0 → all params low; condition 1 → all params high."""
    p_low = condition_to_params(0.0)
    p_high = condition_to_params(1.0)
    for key in (
        "paint_chipping_amount",
        "exposed_metal_fraction",
        "dust_accumulation",
        "scratch_density",
    ):
        assert p_high[key] > p_low[key]


def test_mask_graph_environment_modulation() -> None:
    """Humid environments raise rust; arid environments lower it."""
    base = WearMaskRecipe(target_zone_id="body", condition=0.7, environment="neutral")
    humid = WearMaskRecipe(target_zone_id="body", condition=0.7, environment="humid_industrial")
    arid = WearMaskRecipe(target_zone_id="body", condition=0.7, environment="arid")
    g_base = compile_mask_graph(base)
    g_humid = compile_mask_graph(humid)
    g_arid = compile_mask_graph(arid)
    assert g_humid.masks["fastener_rust_mask"] > g_base.masks["fastener_rust_mask"]
    assert g_arid.masks["fastener_rust_mask"] < g_base.masks["fastener_rust_mask"]


def test_pbr_channels_correlated_with_mask_graph() -> None:
    """Higher condition → rougher, more rust-tinted, less metallic on steel."""
    archetype = resolve_archetype("painted_steel", "utility_industrial_v1")
    low = compile_mask_graph(
        WearMaskRecipe(target_zone_id="body", condition=0.05, environment="neutral")
    )
    high = compile_mask_graph(
        WearMaskRecipe(target_zone_id="body", condition=0.85, environment="humid_industrial")
    )
    pbr_low = compose_pbr_channels(archetype, low)
    pbr_high = compose_pbr_channels(archetype, high)
    # Worn metal should be rougher, more rust-orange, more AO-intense.
    assert pbr_high.roughness > pbr_low.roughness
    assert pbr_high.ao_intensity > pbr_low.ao_intensity


def test_resolve_archetype_falls_back_gracefully() -> None:
    """Unknown material+visual combos fall back to painted_steel.utility_industrial."""
    archetype = resolve_archetype("invented_material", "invented_visual_language_v1")
    assert archetype.material_class == "painted_steel"


def test_priority_feature_ops_defined() -> None:
    """All 8 priority feature ops have specs."""
    expected = {
        "op.panel_inset",
        "op.edge_group_select",
        "op.weighted_bevel",
        "op.trim_sweep",
        "op.profile_sweep",
        "op.fastener_pattern",
        "op.boolean_group",
        "op.lod_policy",
    }
    assert set(PRIORITY_FEATURE_OPS.keys()) == expected


def test_feature_op_param_validation() -> None:
    """validate_op_params returns missing required keys."""
    missing = validate_op_params("op.panel_inset", {"target_face": "body.front_face"})
    assert "margin_cm" in missing
    assert "depth_cm" in missing
    assert validate_op_params("op.panel_inset",
                              {"target_face": "x", "margin_cm": 1.0, "depth_cm": 0.5}) == []


def test_canonical_mask_names() -> None:
    assert "edge_wear_mask" in CANONICAL_MASK_NAMES
    assert "fastener_rust_mask" in CANONICAL_MASK_NAMES
    assert "decal_fade_mask" in CANONICAL_MASK_NAMES
