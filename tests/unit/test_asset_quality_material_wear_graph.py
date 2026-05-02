"""Phase 8 tests for ``lathe.asset_quality.material_wear_graph``.

Covers per task #8 of ``docs/asset-quality/improvement-tasklist.md``:

- ``WearMask``, ``MaterialZone``, ``MaterialWearGraph`` are frozen.
- ``WEAR_MASK_TYPES`` is exactly five members; ``ZONE_TYPES`` is
  exactly two — both pinned by exact-membership comparison.
- The industrial_crate default graph carries the expected counts of
  base materials, underlayers, and wear masks; every wear mask's
  ``mask_type`` is in ``WEAR_MASK_TYPES``; every zone's ``zone_type``
  is in ``ZONE_TYPES``.
- ``MaterialWearGraph.to_dict`` round-trips (tuples become lists,
  dicts are preserved).
- The validator payload contract is exactly the eight top-level keys
  declared in the master prompt.
- No top-level ``diagnostics`` key (informational contract — mirrors
  Phases 1 through 7).
- Binding validation: the industrial_crate default's bindings all
  resolve when the runtime carries the recipe nodes; unknown
  ``bound_node_id`` values land in ``orphan_node_bindings``.
- Uniform-noise score: clean fixture (3+ zones + all bindings
  resolved) lands ``<= 0.05``; uniform fixture (1 zone, no bindings)
  lands ``>= 0.85``; industrial_crate default with the recipe nodes
  resolved lands at the documented baseline value.
- Generic-family fallback: empty graph, score ``= 1.0``, warning
  fires.
- ``skipped_reasons`` records ``incomplete_bake_maps`` when the
  Phase 7 evidence reports fewer than four bake maps present.
- Determinism: the same input yields the same output across calls.
- Missing intent / construction graph / design brief never crash.
- The publishable payload arrays (materials, underlayers, wear_masks,
  skipped_reasons, warnings) are all lists in the JSON form.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from lathe.asset_quality.material_wear_graph import (
    MATERIAL_WEAR_VERSION,
    WEAR_MASK_TYPES,
    ZONE_TYPES,
    MaterialWearGraph,
    MaterialZone,
    WearMask,
    _industrial_crate_default_graph,
    evaluate_material_wear_graph,
)
from lathe.surface_runtime import _material_wear_graph_hooks

_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "family",
        "graph",
        "graph_summary",
        "binding_validation",
        "uniform_noise",
        "skipped_reasons",
    }
)


_RECIPE_NODES: tuple[dict[str, Any], ...] = (
    {"node_id": "recipe.body_shell", "node_type": "primary_volume", "attributes": {}},
    {"node_id": "recipe.lid_seam", "node_type": "panel", "attributes": {}},
    {"node_id": "recipe.handle_l", "node_type": "handle", "attributes": {}},
    {"node_id": "recipe.handle_r", "node_type": "handle", "attributes": {}},
    {"node_id": "recipe.foot_rail_front", "node_type": "rail", "attributes": {}},
    {"node_id": "recipe.foot_rail_back", "node_type": "rail", "attributes": {}},
    {"node_id": "recipe.warning_decal_zone", "node_type": "decal_zone", "attributes": {}},
    *tuple(
        {"node_id": f"recipe.corner_guard_{index}", "node_type": "guard", "attributes": {}}
        for index in range(8)
    ),
)


_SHAPE_OP_TARGETS: tuple[str, ...] = (
    "body.outer_edges",
    "body.top_band",
    "body.bottom_front",
    "body.bottom_back",
    "body.left_face",
    "body.right_face",
    "body.front_face",
    "body.corners",
)


def _runtime_industrial_crate(
    *,
    bake_maps_present: int = 4,
    surface_zone_count: int = 1,
    include_surface_outputs: bool = True,
    include_edge_targets: bool = True,
    extra_recipe_nodes: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Return a runtime dict that mirrors a live industrial_crate build.

    The ``surface.bundle.material_zones`` count and the count of bake
    maps reported under ``highlow_relation`` are tunable so the
    fixtures can isolate the uniform-noise score's two terms (zone
    diversity and the skipped-reasons branch).
    """
    bake_maps = [
        {"map_name": name, "present": True, "uri": f"x/{name}", "skipped_reason": None}
        for name in ("normal", "ao", "curvature", "id")[:bake_maps_present]
    ]
    surface_zones = [
        {"material": f"mat_{index}", "part": "body"}
        for index in range(surface_zone_count)
    ]
    surface_bundle: dict[str, Any] = {"material_zones": surface_zones}
    if include_surface_outputs:
        surface_bundle["outputs"] = {"basecolor": {"uri": "maps/basecolor.png"}}
    runtime = {
        "design_brief": {"brief": {"family": "industrial_crate"}},
        "construction_graph": {"nodes": []},
        "grammar_lowering": {
            "synthesized_graph_nodes": list(_RECIPE_NODES) + list(extra_recipe_nodes),
            "shape_program": {
                "ops": [
                    {"op": "op.test", "target": target, "parameters": {}}
                    for target in _SHAPE_OP_TARGETS
                ]
            },
        },
        "highlow_relation": {"bake_maps": bake_maps},
        "surface": {"bundle": surface_bundle},
    }
    if not include_edge_targets:
        runtime["grammar_lowering"]["shape_program"] = {"ops": []}
    return runtime


# ----------------------------------------------------------------------------
# Frozen-dataclass + registry contract
# ----------------------------------------------------------------------------


def test_wear_mask_types_membership_is_exactly_five() -> None:
    """``WEAR_MASK_TYPES`` is the canonical five-member set."""
    expected = {
        "convex_edge_wear",
        "concave_grime",
        "lower_contact_scuff",
        "handle_touch_wear",
        "decal_wear",
    }
    assert set(WEAR_MASK_TYPES) == expected
    assert len(WEAR_MASK_TYPES) == 5


def test_zone_types_membership_is_exactly_two() -> None:
    """``ZONE_TYPES`` is the canonical two-member set."""
    assert set(ZONE_TYPES) == {"base_material", "underlayer"}
    assert len(ZONE_TYPES) == 2


def test_wear_mask_dataclass_is_frozen() -> None:
    """``WearMask`` is immutable — assignment raises FrozenInstanceError."""
    mask = WearMask(
        mask_id="x",
        mask_type="convex_edge_wear",
        intensity=0.1,
        bound_node_id=None,
        bound_edge_target="body.outer_edges",
        parameters={},
    )
    with pytest.raises(FrozenInstanceError):
        mask.intensity = 0.5  # type: ignore[misc]


def test_wear_mask_validates_bounds_and_freezes_parameters() -> None:
    """Mutable constructor parameters are defensively copied and frozen."""
    raw_parameters = {"scale": {"value": 1}}
    mask = WearMask(
        mask_id="x",
        mask_type="convex_edge_wear",
        intensity=0.1,
        bound_node_id=None,
        bound_edge_target="body.outer_edges",
        parameters=raw_parameters,
    )
    raw_parameters["scale"]["value"] = 2
    assert mask.parameters["scale"]["value"] == 1
    with pytest.raises(TypeError):
        mask.parameters["new"] = 1  # type: ignore[index]
    with pytest.raises(ValueError):
        WearMask(
            mask_id="bad",
            mask_type="convex_edge_wear",
            intensity=1.5,
            bound_node_id=None,
            bound_edge_target="body.outer_edges",
            parameters={},
        )


def test_material_zone_dataclass_is_frozen() -> None:
    """``MaterialZone`` is immutable."""
    zone = MaterialZone(
        zone_id="x",
        zone_type="base_material",
        base_color="#000000",
        roughness=0.5,
        metalness=0.0,
        bound_part=None,
        parameters={},
    )
    with pytest.raises(FrozenInstanceError):
        zone.roughness = 0.9  # type: ignore[misc]


def test_material_zone_validates_bounds_and_freezes_parameters() -> None:
    """Roughness/metalness are bounded and parameter dicts are immutable."""
    raw_parameters = {"finish": {"clearcoat": 0.1}}
    zone = MaterialZone(
        zone_id="x",
        zone_type="base_material",
        base_color="#000000",
        roughness=0.5,
        metalness=0.0,
        bound_part=None,
        parameters=raw_parameters,
    )
    raw_parameters["finish"]["clearcoat"] = 0.8
    assert zone.parameters["finish"]["clearcoat"] == 0.1
    with pytest.raises(TypeError):
        zone.parameters["new"] = 1  # type: ignore[index]
    with pytest.raises(ValueError):
        MaterialZone(
            zone_id="bad",
            zone_type="base_material",
            base_color="#000000",
            roughness=-0.1,
            metalness=0.0,
            bound_part=None,
            parameters={},
        )


def test_material_wear_graph_dataclass_is_frozen() -> None:
    """``MaterialWearGraph`` is immutable."""
    graph = MaterialWearGraph(
        family="x",
        version=MATERIAL_WEAR_VERSION,
        materials=(),
        underlayers=(),
        wear_masks=(),
    )
    with pytest.raises(FrozenInstanceError):
        graph.family = "y"  # type: ignore[misc]


# ----------------------------------------------------------------------------
# Industrial crate default graph
# ----------------------------------------------------------------------------


def test_industrial_crate_default_carries_expected_counts() -> None:
    """Spec Section 12.3: 1 base material + 1 underlayer + 15 wear masks."""
    graph = _industrial_crate_default_graph()
    assert graph.family == "industrial_crate"
    assert graph.version == MATERIAL_WEAR_VERSION
    assert len(graph.materials) == 1
    assert len(graph.underlayers) == 1
    assert len(graph.wear_masks) == 15


def test_industrial_crate_default_mask_types_cover_full_registry() -> None:
    """Each canonical wear-mask type appears at least once."""
    graph = _industrial_crate_default_graph()
    types_used = {mask.mask_type for mask in graph.wear_masks}
    assert types_used == set(WEAR_MASK_TYPES)


def test_industrial_crate_default_zone_types_use_registry_only() -> None:
    """Every default zone uses a token from ``ZONE_TYPES``."""
    graph = _industrial_crate_default_graph()
    for zone in graph.materials + graph.underlayers:
        assert zone.zone_type in ZONE_TYPES


def test_industrial_crate_default_painted_steel_body_matches_spec() -> None:
    """Painted-steel base material matches spec Section 12.3 values."""
    graph = _industrial_crate_default_graph()
    base = graph.materials[0]
    assert base.zone_id == "painted_steel_body"
    assert base.zone_type == "base_material"
    assert base.base_color == "#4f5668"
    assert base.roughness == pytest.approx(0.62)
    assert base.metalness == pytest.approx(0.0)
    assert base.bound_part == "body"


def test_industrial_crate_default_dark_bare_metal_underlayer_matches_spec() -> None:
    """Bare-metal underlayer matches spec Section 12.3 values."""
    graph = _industrial_crate_default_graph()
    under = graph.underlayers[0]
    assert under.zone_id == "dark_bare_metal"
    assert under.zone_type == "underlayer"
    assert under.base_color == "#2a2a2a"
    assert under.roughness == pytest.approx(0.50)
    assert under.metalness == pytest.approx(1.0)
    assert under.bound_part == "body"


# ----------------------------------------------------------------------------
# to_dict round-trip
# ----------------------------------------------------------------------------


def test_to_dict_round_trip_yields_lists_and_dicts() -> None:
    """All tuples become lists; dicts are preserved verbatim."""
    graph = _industrial_crate_default_graph()
    payload = graph.to_dict()
    assert isinstance(payload["materials"], list)
    assert isinstance(payload["underlayers"], list)
    assert isinstance(payload["wear_masks"], list)
    assert payload["family"] == "industrial_crate"
    assert payload["version"] == MATERIAL_WEAR_VERSION
    assert all(isinstance(zone, dict) for zone in payload["materials"])
    assert all(isinstance(mask, dict) for mask in payload["wear_masks"])
    assert payload["materials"][0]["zone_id"] == "painted_steel_body"


# ----------------------------------------------------------------------------
# Validator payload shape contract
# ----------------------------------------------------------------------------


def test_evaluate_returns_exactly_seven_top_level_keys() -> None:
    """Payload contract: only the seven master-prompt keys appear."""
    runtime = _runtime_industrial_crate()
    payload = evaluate_material_wear_graph({}, runtime)
    assert set(payload.keys()) == _PAYLOAD_KEYS


def test_evaluate_does_not_add_top_level_diagnostics_key() -> None:
    """Phase 8 is informational — no top-level ``diagnostics`` field."""
    runtime = _runtime_industrial_crate()
    payload = evaluate_material_wear_graph({}, runtime)
    assert "diagnostics" not in payload


def test_evaluate_arrays_are_lists_in_json_form() -> None:
    """Every publishable array is a list (not a tuple) in the payload."""
    runtime = _runtime_industrial_crate()
    payload = evaluate_material_wear_graph({}, runtime)
    assert isinstance(payload["graph"]["materials"], list)
    assert isinstance(payload["graph"]["underlayers"], list)
    assert isinstance(payload["graph"]["wear_masks"], list)
    assert isinstance(payload["skipped_reasons"], list)
    assert isinstance(payload["uniform_noise"]["warnings"], list)
    assert isinstance(payload["binding_validation"]["orphan_node_bindings"], list)


# ----------------------------------------------------------------------------
# Binding validation
# ----------------------------------------------------------------------------


def test_industrial_crate_bindings_all_resolve_against_recipe_nodes() -> None:
    """When the runtime carries the recipe nodes, every node-bound
    wear mask resolves and the orphan list is empty."""
    runtime = _runtime_industrial_crate()
    payload = evaluate_material_wear_graph({}, runtime)
    binding = payload["binding_validation"]
    assert binding["all_node_bindings_resolved"] is True
    assert binding["orphan_node_bindings"] == []
    assert binding["construction_graph_node_count"] == len(_RECIPE_NODES)


def test_orphan_bindings_appear_in_orphan_node_bindings_list() -> None:
    """A wear mask whose ``bound_node_id`` is not present in the
    construction graph appears in ``orphan_node_bindings`` with its
    mask_id and flips ``all_node_bindings_resolved`` to False."""
    runtime = _runtime_industrial_crate()
    runtime["grammar_lowering"]["synthesized_graph_nodes"] = []
    runtime["construction_graph"]["nodes"] = []
    payload = evaluate_material_wear_graph({}, runtime)
    binding = payload["binding_validation"]
    assert binding["all_node_bindings_resolved"] is False
    expected_orphans = {
        mask["mask_id"]
        for mask in payload["graph"]["wear_masks"]
        if mask["bound_node_id"] is not None
    }
    assert set(binding["orphan_node_bindings"]) == expected_orphans
    assert binding["construction_graph_node_count"] == 0


def test_graph_summary_breakdown_matches_default_graph() -> None:
    """``graph_summary`` reflects resolved bindings, not declarations."""
    runtime = _runtime_industrial_crate()
    payload = evaluate_material_wear_graph({}, runtime)
    summary = payload["graph_summary"]
    assert summary["material_zone_count"] == 1
    assert summary["underlayer_count"] == 1
    assert summary["wear_mask_count"] == 15
    assert summary["wear_masks_by_type"] == {
        "concave_grime": 1,
        "convex_edge_wear": 9,
        "decal_wear": 1,
        "handle_touch_wear": 2,
        "lower_contact_scuff": 2,
    }
    assert summary["bound_to_construction_nodes"] == 14
    assert summary["bound_to_edge_targets"] == 15
    assert summary["bound_to_both"] == 14
    assert summary["declared_node_bindings"] == 14
    assert summary["declared_edge_bindings"] == 15
    assert summary["resolved_bindings"] == 15


def test_edge_bindings_require_shape_or_construction_edge_evidence() -> None:
    """Edge bindings are not considered resolved merely because strings exist."""
    runtime = _runtime_industrial_crate(include_edge_targets=False)
    payload = evaluate_material_wear_graph({}, runtime)
    summary = payload["graph_summary"]
    binding = payload["binding_validation"]
    assert summary["declared_edge_bindings"] == 15
    assert summary["bound_to_edge_targets"] == 0
    assert binding["all_edge_bindings_resolved"] is False
    assert set(binding["orphan_edge_bindings"]) == {
        mask["mask_id"]
        for mask in payload["graph"]["wear_masks"]
        if mask["bound_edge_target"] is not None
    }


# ----------------------------------------------------------------------------
# Uniform-noise score
# ----------------------------------------------------------------------------


def test_clean_fixture_score_is_at_or_below_threshold() -> None:
    """Clean fixture (3+ zones + all wear bound) lands ``<= 0.05``."""
    runtime = _runtime_industrial_crate(surface_zone_count=3)
    payload = evaluate_material_wear_graph({}, runtime)
    noise = payload["uniform_noise"]
    assert noise["uniform_noise_score"] <= 0.05
    assert noise["is_uniform_noise"] is False
    assert noise["warnings"] == []


def test_uniform_fixture_score_is_high_and_warns() -> None:
    """Uniform fixture (no zones, no bindings) lands ``>= 0.85`` and
    fires the warning. The generic-family path is the canonical
    "nothing authored" surface — empty graph + empty surface zones
    drives both the zone-diversity and binding terms to zero."""
    runtime = {
        "design_brief": {"brief": {"family": "generic"}},
        "construction_graph": {"nodes": []},
        "grammar_lowering": {"synthesized_graph_nodes": []},
        "highlow_relation": {"bake_maps": []},
        "surface": {"bundle": {"material_zones": []}},
    }
    payload = evaluate_material_wear_graph({}, runtime)
    noise = payload["uniform_noise"]
    assert noise["uniform_noise_score"] >= 0.85
    assert noise["is_uniform_noise"] is True
    assert noise["warnings"]


def test_industrial_crate_baseline_score_lands_at_documented_value() -> None:
    """Industrial crate default with all bindings resolved lands at the
    documented baseline of approximately ``0.27`` (1 material zone +
    all wear masks resolved)."""
    runtime = _runtime_industrial_crate(surface_zone_count=1)
    payload = evaluate_material_wear_graph({}, runtime)
    noise = payload["uniform_noise"]
    # 1 material + 1 surface zone -> max(1, 1)/3 = 0.333.
    # All wear masks resolved -> binding_ratio = 1.0.
    # Score = 1 - (0.4 * 0.333 + 0.6 * 1.0) = 1 - 0.7333 = 0.2667.
    assert noise["uniform_noise_score"] == pytest.approx(0.266667, abs=1e-4)
    assert noise["zone_diversity"] == pytest.approx(0.333333, abs=1e-4)
    assert noise["wear_binding_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert noise["is_uniform_noise"] is False


def test_generic_family_falls_back_to_empty_graph_with_warning() -> None:
    """Unknown family -> empty graph, score ``= 1.0``, warning fires."""
    payload = evaluate_material_wear_graph(
        {}, {"design_brief": {"brief": {"family": "generic"}}}
    )
    assert payload["family"] == "generic"
    assert payload["graph"]["materials"] == []
    assert payload["graph"]["underlayers"] == []
    assert payload["graph"]["wear_masks"] == []
    noise = payload["uniform_noise"]
    assert noise["uniform_noise_score"] == pytest.approx(1.0)
    assert noise["is_uniform_noise"] is True
    assert noise["warnings"]


def test_user_authored_material_wear_graph_values_are_consumed() -> None:
    """Resolved ``surface.material_graph`` with v1-shaped values replaces defaults."""
    asset = {
        "surface": {
            "material_graph": "custom_graph",
            "resolved_material_graph": {
                "name": "custom_graph",
                "values": {
                    "materials": [
                        {
                            "zone_id": "paint",
                            "zone_type": "base_material",
                            "base_color": "#101010",
                            "roughness": 0.5,
                            "metalness": 0.0,
                            "bound_part": "body",
                            "parameters": {},
                        }
                    ],
                    "wear_masks": [
                        {
                            "mask_id": "wear.edge",
                            "mask_type": "convex_edge_wear",
                            "intensity": 0.4,
                            "bound_node_id": None,
                            "bound_edge_target": "body.outer_edges",
                            "parameters": {},
                        }
                    ],
                },
            },
        }
    }
    runtime = _runtime_industrial_crate()
    payload = evaluate_material_wear_graph(asset, runtime)
    assert payload["graph_summary"]["graph_source"] == "surface.material_graph"
    assert payload["graph_summary"]["material_graph_reference"] == "custom_graph"
    assert payload["graph"]["materials"][0]["zone_id"] == "paint"
    assert payload["graph_summary"]["wear_mask_count"] == 1
    assert payload["binding_validation"]["orphan_edge_bindings"] == []


def test_non_lowerable_surface_material_graph_is_skipped_with_evidence() -> None:
    """Legacy material_graph metadata is carried as a skip, not invented as wear."""
    asset = {
        "surface": {
            "material_graph": "aged_brass_graph",
            "resolved_material_graph": {
                "name": "aged_brass_graph",
                "values": {
                    "base": "aged_brass",
                    "layers": ["patina", "edge_wear"],
                    "outputs": ["basecolor"],
                },
            },
        }
    }
    runtime = _runtime_industrial_crate()
    payload = evaluate_material_wear_graph(asset, runtime)
    assert payload["graph_summary"]["graph_source"] == "family_default"
    assert {
        "tool": "surface.material_graph",
        "reason": "resolved_material_graph_not_lowerable_to_material_wear_graph_v1",
        "evidence": "aged_brass_graph",
    } in payload["skipped_reasons"]


def test_surface_runtime_material_wear_hooks_carry_material_graph_metadata() -> None:
    """Surface bundles can carry additive material/wear hook metadata."""
    hooks = _material_wear_graph_hooks(
        {
            "material_graph": "aged_brass_graph",
            "resolved_material_graph": {
                "name": "aged_brass_graph",
                "values": {"base": "aged_brass"},
            },
        }
    )
    assert hooks["version"] == MATERIAL_WEAR_VERSION
    assert hooks["material_graph"] == "aged_brass_graph"
    assert hooks["has_resolved_material_graph"] is True
    assert hooks["mask_textures_generated"] is False
    assert hooks["surface_maps_driven_by_material_wear_graph"] is False
    assert {
        "tool": "surface_runtime",
        "reason": "mask_texture_generation_not_implemented",
    } in hooks["skipped_reasons"]


def test_metadata_only_surface_zones_do_not_suppress_uniform_noise_warning() -> None:
    """Surface zone metadata without map evidence is not enough for a clean score."""
    runtime = _runtime_industrial_crate(
        surface_zone_count=3,
        include_surface_outputs=False,
        include_edge_targets=False,
    )
    runtime["grammar_lowering"]["synthesized_graph_nodes"] = []
    payload = evaluate_material_wear_graph({}, runtime)
    noise = payload["uniform_noise"]
    assert noise["uniform_noise_score"] >= 0.85
    assert noise["is_uniform_noise"] is True


# ----------------------------------------------------------------------------
# Skipped reasons
# ----------------------------------------------------------------------------


def test_skipped_reasons_records_incomplete_bake_maps() -> None:
    """When fewer than four bake maps are present, ``skipped_reasons``
    captures the gap with a structured token."""
    runtime = _runtime_industrial_crate(bake_maps_present=2)
    payload = evaluate_material_wear_graph({}, runtime)
    assert {"tool": "bake_runtime", "reason": "incomplete_bake_maps"} in payload[
        "skipped_reasons"
    ]


def test_skipped_reasons_record_unimplemented_surface_hooks() -> None:
    """Full bake maps do not hide unimplemented material/wear surface hooks."""
    runtime = _runtime_industrial_crate(bake_maps_present=4)
    payload = evaluate_material_wear_graph({}, runtime)
    assert payload["skipped_reasons"] == [
        {
            "tool": "surface_runtime",
            "reason": "mask_texture_generation_not_implemented",
        },
        {
            "tool": "surface_runtime",
            "reason": "surface_map_driving_not_implemented",
        },
    ]


# ----------------------------------------------------------------------------
# Determinism + tolerance for missing keys
# ----------------------------------------------------------------------------


def test_evaluate_is_deterministic_across_calls() -> None:
    """Same input -> same output."""
    runtime = _runtime_industrial_crate()
    first = evaluate_material_wear_graph({}, runtime)
    second = evaluate_material_wear_graph({}, runtime)
    assert first == second


def test_missing_intent_design_brief_construction_graph_does_not_crash() -> None:
    """Empty asset + empty runtime fall through to generic without error."""
    payload = evaluate_material_wear_graph({}, {})
    assert payload["family"] == "generic"
    assert payload["graph"]["materials"] == []
    assert payload["binding_validation"]["construction_graph_node_count"] == 0
    assert payload["uniform_noise"]["is_uniform_noise"] is True


def test_evaluate_tolerates_malformed_runtime_blocks() -> None:
    """Non-dict runtime keys are tolerated (they collapse to empty)."""
    runtime: dict[str, Any] = {
        "design_brief": "not-a-dict",
        "construction_graph": [],
        "grammar_lowering": None,
        "highlow_relation": "x",
        "surface": 42,
    }
    payload = evaluate_material_wear_graph({}, runtime)
    assert payload["family"] == "generic"
    assert payload["binding_validation"]["construction_graph_node_count"] == 0


def test_version_field_matches_module_constant() -> None:
    """``version`` field equals ``MATERIAL_WEAR_VERSION``."""
    payload = evaluate_material_wear_graph({}, {})
    assert payload["version"] == MATERIAL_WEAR_VERSION
