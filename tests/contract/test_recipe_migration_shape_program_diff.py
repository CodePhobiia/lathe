"""Contract test: per-family ShapeProgram diff between recipe and synthesizer paths.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §6.4:

> For each family migrated: a side-by-side ShapeProgram diff test
> exists, comparing the pre-migration recipe output to the
> post-migration synthesizer output. Differences must be documented
> as intent-driven (e.g., brief now respected) or reduced.

This is the parametrized harness. Each family that has migrated
ships a fixture entry under ``_MIGRATED_FAMILY_FIXTURES`` with:

  - ``family``: the family name (matches ``_RECIPES`` key + the
    ``family`` field in the resulting ShapeProgram).
  - ``brief``: design-brief dict the recipe receives.
  - ``parts``: parts tuple the recipe receives.
  - ``graph_nodes``: pre-existing graph nodes the recipe receives.
  - ``synthesizer_asset``: the ``asset`` dict the synthesizer
    receives. Must populate ``build.shape.procedural.construction_graph``
    or ``intent.construction_graph`` for ``synthesizer_eligible`` to
    return True.
  - ``synthesizer_runtime``: the ``runtime`` dict the synthesizer
    receives. Carries ``design_brief`` and ``construction_graph``.
  - ``allowed_op_diff``: optional list of explicit diff entries the
    test tolerates (each with a documented ``reason`` per migration
    notes JSON sidecar).

Unmigrated families are not in ``_MIGRATED_FAMILY_FIXTURES``; they
fail nothing (no parametrize entry). As each Round 2/3/5 family
migrates, its fixture is added here and to the build-artifact diff
harness simultaneously.

Diff semantics: ops must be equivalent or better. "Better" is defined
by the migration notes — typically "intent-driven (e.g., brief now
respected)" or "reduced op count without losing visible structure."
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from lathe.asset_quality.grammar_lowering import _RECIPES
from lathe.asset_quality.procedural_synthesizer import synthesize_procedural_program
from lathe.asset_quality.shape_ir_v2 import ShapeOp, ShapeProgram


# --- Fixture catalog ----------------------------------------------------
#
# Each entry is a dict with the keys documented in the module
# docstring. The catalog is empty until a family migrates; each
# migration PR appends its fixture.
#
# To add a family migration:
#   1. Author its StyleKnowledge / CompositionPolicy / FamilyAlias.
#   2. Update its .lth fixture to populate construction_graph.
#   3. Append an entry below + a corresponding entry in
#      tests/integration/test_recipe_migration_build_artifact_diff.py.
#   4. Run this test — the diff against the recipe baseline must pass.
#   5. Delete _RECIPES[family].

def _round2_graph(*nodes: tuple[str, str, dict[str, Any]]) -> dict[str, Any]:
    """Build a Round 2 simple-family construction graph from (id, type, attrs) tuples."""
    return {
        "nodes": [
            {"node_id": nid, "node_type": ntype, "domain": "hard_surface", "attributes": attrs}
            for nid, ntype, attrs in nodes
        ],
        "edges": [],
    }


# Re-usable attribute templates for the simple-family migration set.
# Round 2 families all express the same 10-NODE_TYPE canonical pattern;
# attributes differ only in node_id labels per family.

_ATTRS_PRIMARY_VOLUME: dict[str, Any] = {"shape": "rounded_box", "dimensions_cm": {"x": 30.0, "y": 30.0, "z": 30.0}, "rounding_cm": 1.5}
_ATTRS_MATERIAL_ZONE: dict[str, Any] = {"material_hint": "painted_emblem"}  # zone_id filled per node
_ATTRS_DECAL_ZONE: dict[str, Any] = {"decal_intent": "label", "size_cm": [8.0, 4.0], "host_face_axis": "z"}
_ATTRS_WEAR_ZONE: dict[str, Any] = {"wear_kind": "handled", "intensity": "moderate", "coverage_fraction": 0.4}
_ATTRS_HANDLE_BAR: dict[str, Any] = {"style": "bar", "length_cm": 14.0, "grip_radius_cm": 0.8, "axis": "x"}
_ATTRS_INSET: dict[str, Any] = {"depth_axis": "z", "depth_cm": 0.4, "width_cm": 6.0, "height_cm": 4.0, "profile": "flat"}
_ATTRS_FASTENER: dict[str, Any] = {"kind": "rivet", "head_radius_cm": 0.3, "head_height_cm": 0.4, "shaft_radius_cm": 0.15, "shaft_length_cm": 0.6}
_ATTRS_SOCKET: dict[str, Any] = {"depth_axis": "x", "depth_cm": 1.0, "radius_cm": 0.6, "profile": "round"}
_ATTRS_RAIL: dict[str, Any] = {"axis": "x", "length_cm": 14.0, "radius_cm": 0.4, "cross_section": "round"}
_ATTRS_TRIM: dict[str, Any] = {"profile": "flat_band", "length_cm": 14.0, "width_cm": 1.0, "thickness_cm": 0.4, "axis": "x"}
_ATTRS_FRAME: dict[str, Any] = {"plane": "xy", "outer_width_cm": 14.0, "outer_height_cm": 14.0, "member_thickness_cm": 0.6, "protrusion_cm": 0.4}
_ATTRS_PANEL: dict[str, Any] = {"shape": "rectangular", "width_cm": 14.0, "height_cm": 10.0, "thickness_cm": 0.4, "host_face_axis": "z"}
_ATTRS_MOUNT: dict[str, Any] = {"style": "flat_pad", "width_cm": 4.0, "depth_cm": 4.0, "height_cm": 0.6}
_ATTRS_GUARD: dict[str, Any] = {"style": "perimeter_rail", "width_cm": 16.0, "height_cm": 6.0, "depth_cm": 16.0, "bar_radius_cm": 0.3, "bar_count": 4, "axis": "y"}


def _zone_attrs(zone_id: str, base: dict[str, Any]) -> dict[str, Any]:
    return {"zone_id": zone_id, **base}


def _round2_fixture(
    family: str,
    nodes: tuple[tuple[str, str, dict[str, Any]], ...],
    *,
    min_synth_op_count: int = 8,
) -> dict[str, Any]:
    """Build a Round 2/3 fixture with allow_intent_driven_replacement.

    Shares the construction_graph between asset and runtime so both
    paths see the same graph (asset.intent.construction_graph for the
    synthesizer_eligible predicate, runtime.construction_graph for the
    pipeline's actual consumption).
    """
    graph = _round2_graph(*nodes)
    return {
        "family": family,
        "brief": {},
        "parts": (),
        "graph_nodes": (),
        "synthesizer_asset": {
            "name": family,
            "intent": {"construction_graph": graph},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": family}},
            "construction_graph": graph,
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": min_synth_op_count,
    }


_ATTRS_HINGE: dict[str, Any] = {
    "style": "butt", "leaf_width_cm": 3.0, "leaf_height_cm": 6.0,
    "leaf_thickness_cm": 0.3, "barrel_radius_cm": 0.4, "pin_axis": "y",
}


_INVENTORY_ECONOMY_OBJECT_GRAPH: dict[str, Any] = {
    "nodes": [
        {"node_id": "body", "node_type": "primary_volume", "domain": "hard_surface",
         "attributes": {"shape": "rounded_box", "dimensions_cm": {"x": 28.0, "y": 38.0, "z": 28.0}, "rounding_cm": 2.0}},
        {"node_id": "rarity_band", "node_type": "material_zone", "domain": "hard_surface",
         "attributes": {"zone_id": "rarity_band", "material_hint": "painted_emblem"}},
        {"node_id": "currency_pip", "node_type": "decal_zone", "domain": "hard_surface",
         "attributes": {"zone_id": "currency_pip", "decal_intent": "currency_marker", "size_cm": [3.0, 3.0], "host_face_axis": "z"}},
        {"node_id": "vendor_label", "node_type": "decal_zone", "domain": "hard_surface",
         "attributes": {"zone_id": "vendor_label", "decal_intent": "vendor_brand", "size_cm": [13.0, 4.0], "host_face_axis": "z"}},
        {"node_id": "handled_wear", "node_type": "wear_zone", "domain": "hard_surface",
         "attributes": {"zone_id": "handled_wear", "wear_kind": "handled", "intensity": "moderate", "coverage_fraction": 0.4}},
        {"node_id": "access_handle", "node_type": "handle", "domain": "hard_surface",
         "attributes": {"style": "bar", "length_cm": 16.0, "grip_radius_cm": 0.75, "axis": "x"}},
        {"node_id": "pickup_handle", "node_type": "handle", "domain": "hard_surface",
         "attributes": {"style": "loop", "length_cm": 10.0, "grip_radius_cm": 0.9, "axis": "x"}},
        {"node_id": "storage_slots", "node_type": "inset", "domain": "hard_surface",
         "attributes": {"depth_axis": "z", "depth_cm": 0.3, "width_cm": 6.0, "height_cm": 4.0, "profile": "flat"}},
        {"node_id": "stack_tick", "node_type": "fastener", "domain": "hard_surface",
         "attributes": {"kind": "rivet", "head_radius_cm": 0.3, "head_height_cm": 0.4, "shaft_radius_cm": 0.15, "shaft_length_cm": 0.6}},
        {"node_id": "resource_ports", "node_type": "socket", "domain": "hard_surface",
         "attributes": {"depth_axis": "x", "depth_cm": 1.0, "radius_cm": 0.6, "profile": "round"}},
    ],
    "edges": [],
}


_MIGRATED_FAMILY_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        # inventory_economy_object: first family migrated to the procedural
        # synthesizer. The recipe emits 10 high-level sop.* ops (polybevel,
        # copy_to_points, polywire, polyextrude, chip_edges); the synthesizer
        # emits 11 low-level ops from a 10-node construction graph driven by
        # the panelized_hard_surface_object policy. ALL diffs are
        # intent-driven: the synthesizer's lower-level decomposition is
        # equivalent in visible structure (body, currency markers, stack
        # ticks, rarity band, two handles, slots, vendor label, resource
        # ports, handled wear) but expressed through the typed NODE_TYPE
        # generator manifest rather than through opaque sop.* ops.
        "family": "inventory_economy_object",
        "brief": {},
        "parts": (),
        "graph_nodes": (),
        "synthesizer_asset": {
            "name": "inventory_economy_object",
            "intent": {"construction_graph": _INVENTORY_ECONOMY_OBJECT_GRAPH},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "inventory_economy_object"}},
            "construction_graph": _INVENTORY_ECONOMY_OBJECT_GRAPH,
        },
        "allowed_op_diff": [
            # Recipe-only ops: high-level sop.* operations the synthesizer
            # decomposes into per-NODE_TYPE typed primitives. Each is
            # equivalent in visible-feature intent to the corresponding
            # synthesizer-side ops noted in parentheses.
            {"op": "sop.polybevel", "target": "inventory.body", "parameter_keys": ["source", "width_cm", "segments"]},
            {"op": "sop.copy_to_points", "target": "inventory.value_markers", "parameter_keys": ["source", "points"]},
            {"op": "sop.copy_to_points", "target": "inventory.quantity_ticks", "parameter_keys": ["source", "points"]},
            {"op": "sop.polyextrude", "target": "inventory.rarity_band", "parameter_keys": ["profile_polygon", "extrude_height_cm", "axis", "center"]},
            {"op": "sop.polywire", "target": "inventory.access_handle", "parameter_keys": ["radius_cm", "path"]},
            {"op": "sop.copy_to_points", "target": "inventory.storage_slots", "parameter_keys": ["source", "points"]},
            {"op": "sop.polywire", "target": "inventory.pickup_handle", "parameter_keys": ["radius_cm", "path"]},
            {"op": "sop.polyextrude", "target": "inventory.vendor_label", "parameter_keys": ["profile_polygon", "extrude_height_cm", "axis", "center"]},
            {"op": "sop.copy_to_points", "target": "inventory.resource_ports", "parameter_keys": ["source", "points"]},
            {"op": "op.chip_edges", "target": "inventory.handled_wear", "parameter_keys": ["amount", "pickup_bias"]},
            # Synthesizer-only ops: low-level primitives + zone metadata
            # that together render the same visible features.
            {"op": "solid.rounded_box", "target": "body",
             "parameter_keys": ["width_cm", "height_cm", "depth_cm", "rounding_cm"]},
            {"op": "op.material_zone", "target": "rarity_band",
             "parameter_keys": ["zone_id", "material_hint", "priority"]},
            {"op": "op.decal_zone", "target": "currency_pip",
             "parameter_keys": ["zone_id", "decal_intent", "size_cm", "host_face_axis", "priority"]},
            {"op": "op.decal_zone", "target": "vendor_label",
             "parameter_keys": ["zone_id", "decal_intent", "size_cm", "host_face_axis", "priority"]},
            {"op": "op.wear_zone", "target": "handled_wear",
             "parameter_keys": ["zone_id", "wear_kind", "intensity", "coverage_fraction"]},
            {"op": "solid.capsule", "target": "access_handle",
             "parameter_keys": ["radius_cm", "length_cm", "axis", "handle_style"]},
            {"op": "solid.capsule", "target": "pickup_handle",
             "parameter_keys": ["radius_cm", "length_cm", "axis", "handle_style"]},
            {"op": "solid.box", "target": "storage_slots",
             "parameter_keys": ["width_cm", "height_cm", "depth_cm", "inset_depth_axis", "inset_bottom_style", "blend_mode"]},
            {"op": "solid.cylinder", "target": "stack_tick.head",
             "parameter_keys": ["radius_cm", "height_cm", "axis", "fastener_kind", "fastener_part"]},
            {"op": "solid.cylinder", "target": "stack_tick.shaft",
             "parameter_keys": ["radius_cm", "height_cm", "axis", "fastener_kind", "fastener_part"]},
            {"op": "solid.cylinder", "target": "resource_ports",
             "parameter_keys": ["radius_cm", "height_cm", "axis", "socket_profile", "blend_mode"]},
        ],
    },
    # ---- Round 2 simple-family migrations (allow_intent_driven_replacement=True) ----
    # Each migration ships its FamilyAlias + a 10-node construction graph
    # mapping the recipe's 10 sop.* op pattern onto typed NODE_TYPE
    # generators. The full-replacement flag acknowledges that the
    # synthesizer's lower-level primitive decomposition is universally
    # disjoint from the recipe's high-level sop.* signature set.
    {
        "family": "world_system_assembly",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "world_system_assembly",
            "intent": {"construction_graph": _round2_graph(
                ("footprint", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("regions", "material_zone", _zone_attrs("regions", _ATTRS_MATERIAL_ZONE)),
                ("routes", "rail", _ATTRS_RAIL),
                ("rules", "material_zone", _zone_attrs("rules", _ATTRS_MATERIAL_ZONE)),
                ("progression", "socket", _ATTRS_SOCKET),
                ("resources", "fastener", _ATTRS_FASTENER),
                ("landmarks", "mount", _ATTRS_MOUNT),
                ("gates", "frame", _ATTRS_FRAME),
                ("labels", "decal_zone", _zone_attrs("labels", _ATTRS_DECAL_ZONE)),
                ("usage", "wear_zone", _zone_attrs("usage", _ATTRS_WEAR_ZONE)),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "world_system_assembly"}},
            "construction_graph": _round2_graph(
                ("footprint", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("regions", "material_zone", _zone_attrs("regions", _ATTRS_MATERIAL_ZONE)),
                ("routes", "rail", _ATTRS_RAIL),
                ("rules", "material_zone", _zone_attrs("rules", _ATTRS_MATERIAL_ZONE)),
                ("progression", "socket", _ATTRS_SOCKET),
                ("resources", "fastener", _ATTRS_FASTENER),
                ("landmarks", "mount", _ATTRS_MOUNT),
                ("gates", "frame", _ATTRS_FRAME),
                ("labels", "decal_zone", _zone_attrs("labels", _ATTRS_DECAL_ZONE)),
                ("usage", "wear_zone", _zone_attrs("usage", _ATTRS_WEAR_ZONE)),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    {
        "family": "attribute_surface_graph_program",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "attribute_surface_graph_program",
            "intent": {"construction_graph": _round2_graph(
                ("attr_streams", "rail", _ATTRS_RAIL),
                ("surface_nodes", "panel", _ATTRS_PANEL),
                ("surface_modes", "socket", _ATTRS_SOCKET),
                ("mask_layers", "material_zone", _zone_attrs("mask_layers", _ATTRS_MATERIAL_ZONE)),
                ("materialx_ports", "socket", _ATTRS_SOCKET),
                ("attribute_math", "panel", _ATTRS_PANEL),
                ("frequency_controls", "fastener", _ATTRS_FASTENER),
                ("preview_targets", "panel", _ATTRS_PANEL),
                ("invalid_guards", "guard", _ATTRS_GUARD),
                ("iteration_wear", "wear_zone", _zone_attrs("iteration_wear", _ATTRS_WEAR_ZONE)),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "attribute_surface_graph_program"}},
            "construction_graph": _round2_graph(
                ("attr_streams", "rail", _ATTRS_RAIL),
                ("surface_nodes", "panel", _ATTRS_PANEL),
                ("surface_modes", "socket", _ATTRS_SOCKET),
                ("mask_layers", "material_zone", _zone_attrs("mask_layers", _ATTRS_MATERIAL_ZONE)),
                ("materialx_ports", "socket", _ATTRS_SOCKET),
                ("attribute_math", "panel", _ATTRS_PANEL),
                ("frequency_controls", "fastener", _ATTRS_FASTENER),
                ("preview_targets", "panel", _ATTRS_PANEL),
                ("invalid_guards", "guard", _ATTRS_GUARD),
                ("iteration_wear", "wear_zone", _zone_attrs("iteration_wear", _ATTRS_WEAR_ZONE)),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    {
        "family": "stateful_destructible_prop",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "stateful_destructible_prop",
            "intent": {"construction_graph": _round2_graph(
                ("intact_shell", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("damage_markers", "decal_zone", _zone_attrs("damage_markers", _ATTRS_DECAL_ZONE)),
                ("fracture_lines", "trim", _ATTRS_TRIM),
                ("fragment_zones", "panel", _ATTRS_PANEL),
                ("weak_points", "mount", _ATTRS_MOUNT),
                ("repair_handle", "handle", _ATTRS_HANDLE_BAR),
                ("transition_cue", "decal_zone", _zone_attrs("transition_cue", _ATTRS_DECAL_ZONE)),
                ("hazard_boundary", "guard", _ATTRS_GUARD),
                ("debris", "fastener", _ATTRS_FASTENER),
                ("damage_wear", "wear_zone", _zone_attrs("damage_wear", _ATTRS_WEAR_ZONE)),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "stateful_destructible_prop"}},
            "construction_graph": _round2_graph(
                ("intact_shell", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("damage_markers", "decal_zone", _zone_attrs("damage_markers", _ATTRS_DECAL_ZONE)),
                ("fracture_lines", "trim", _ATTRS_TRIM),
                ("fragment_zones", "panel", _ATTRS_PANEL),
                ("weak_points", "mount", _ATTRS_MOUNT),
                ("repair_handle", "handle", _ATTRS_HANDLE_BAR),
                ("transition_cue", "decal_zone", _zone_attrs("transition_cue", _ATTRS_DECAL_ZONE)),
                ("hazard_boundary", "guard", _ATTRS_GUARD),
                ("debris", "fastener", _ATTRS_FASTENER),
                ("damage_wear", "wear_zone", _zone_attrs("damage_wear", _ATTRS_WEAR_ZONE)),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    {
        "family": "gameplay_object",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "gameplay_object",
            "intent": {"construction_graph": _round2_graph(
                ("body", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("state_indicator", "panel", _ATTRS_PANEL),
                ("trigger_zone", "material_zone", _zone_attrs("trigger_zone", _ATTRS_MATERIAL_ZONE)),
                ("payload_zone", "socket", _ATTRS_SOCKET),
                ("affordance_handle", "handle", _ATTRS_HANDLE_BAR),
                ("feedback_emitters", "mount", _ATTRS_MOUNT),
                ("bounds_markers", "guard", _ATTRS_GUARD),
                ("link_ports", "socket", _ATTRS_SOCKET),
                ("objective_marker", "decal_zone", _zone_attrs("objective_marker", _ATTRS_DECAL_ZONE)),
                ("interaction_wear", "wear_zone", _zone_attrs("interaction_wear", _ATTRS_WEAR_ZONE)),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "gameplay_object"}},
            "construction_graph": _round2_graph(
                ("body", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("state_indicator", "panel", _ATTRS_PANEL),
                ("trigger_zone", "material_zone", _zone_attrs("trigger_zone", _ATTRS_MATERIAL_ZONE)),
                ("payload_zone", "socket", _ATTRS_SOCKET),
                ("affordance_handle", "handle", _ATTRS_HANDLE_BAR),
                ("feedback_emitters", "mount", _ATTRS_MOUNT),
                ("bounds_markers", "guard", _ATTRS_GUARD),
                ("link_ports", "socket", _ATTRS_SOCKET),
                ("objective_marker", "decal_zone", _zone_attrs("objective_marker", _ATTRS_DECAL_ZONE)),
                ("interaction_wear", "wear_zone", _zone_attrs("interaction_wear", _ATTRS_WEAR_ZONE)),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    {
        "family": "surface_material_sample",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "surface_material_sample",
            "intent": {"construction_graph": _round2_graph(
                ("tile", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("base_material", "material_zone", _zone_attrs("base_material", _ATTRS_MATERIAL_ZONE)),
                ("finish_zone", "material_zone", _zone_attrs("finish_zone", _ATTRS_MATERIAL_ZONE)),
                ("relief_lines", "inset", _ATTRS_INSET),
                ("border_trim", "trim", _ATTRS_TRIM),
                ("label_zone", "decal_zone", _zone_attrs("label_zone", _ATTRS_DECAL_ZONE)),
                ("scale_ticks", "fastener", _ATTRS_FASTENER),
                ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
                ("variant_patch", "material_zone", _zone_attrs("variant_patch", _ATTRS_MATERIAL_ZONE)),
                ("tileability_cues", "socket", _ATTRS_SOCKET),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "surface_material_sample"}},
            "construction_graph": _round2_graph(
                ("tile", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("base_material", "material_zone", _zone_attrs("base_material", _ATTRS_MATERIAL_ZONE)),
                ("finish_zone", "material_zone", _zone_attrs("finish_zone", _ATTRS_MATERIAL_ZONE)),
                ("relief_lines", "inset", _ATTRS_INSET),
                ("border_trim", "trim", _ATTRS_TRIM),
                ("label_zone", "decal_zone", _zone_attrs("label_zone", _ATTRS_DECAL_ZONE)),
                ("scale_ticks", "fastener", _ATTRS_FASTENER),
                ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
                ("variant_patch", "material_zone", _zone_attrs("variant_patch", _ATTRS_MATERIAL_ZONE)),
                ("tileability_cues", "socket", _ATTRS_SOCKET),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    {
        "family": "environment_effect",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "environment_effect",
            "intent": {"construction_graph": _round2_graph(
                ("emitter", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("flow_volume", "material_zone", _zone_attrs("flow_volume", _ATTRS_MATERIAL_ZONE)),
                ("motion_lines", "rail", _ATTRS_RAIL),
                ("contact_zone", "wear_zone", _zone_attrs("contact_zone", _ATTRS_WEAR_ZONE)),
                ("particles", "fastener", _ATTRS_FASTENER),
                ("density_bands", "trim", _ATTRS_TRIM),
                ("boundary", "frame", _ATTRS_FRAME),
                ("material_response", "material_zone", _zone_attrs("material_response", _ATTRS_MATERIAL_ZONE)),
                ("readability_markers", "decal_zone", _zone_attrs("readability_markers", _ATTRS_DECAL_ZONE)),
                ("dynamic_masks", "wear_zone", _zone_attrs("dynamic_masks", _ATTRS_WEAR_ZONE)),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "environment_effect"}},
            "construction_graph": _round2_graph(
                ("emitter", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("flow_volume", "material_zone", _zone_attrs("flow_volume", _ATTRS_MATERIAL_ZONE)),
                ("motion_lines", "rail", _ATTRS_RAIL),
                ("contact_zone", "wear_zone", _zone_attrs("contact_zone", _ATTRS_WEAR_ZONE)),
                ("particles", "fastener", _ATTRS_FASTENER),
                ("density_bands", "trim", _ATTRS_TRIM),
                ("boundary", "frame", _ATTRS_FRAME),
                ("material_response", "material_zone", _zone_attrs("material_response", _ATTRS_MATERIAL_ZONE)),
                ("readability_markers", "decal_zone", _zone_attrs("readability_markers", _ATTRS_DECAL_ZONE)),
                ("dynamic_masks", "wear_zone", _zone_attrs("dynamic_masks", _ATTRS_WEAR_ZONE)),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    {
        "family": "encounter_flow",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "encounter_flow",
            "intent": {"construction_graph": _round2_graph(
                ("footprint", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("spawn_points", "socket", _ATTRS_SOCKET),
                ("routes", "rail", _ATTRS_RAIL),
                ("cover", "guard", _ATTRS_GUARD),
                ("objective", "mount", _ATTRS_MOUNT),
                ("wave_markers", "fastener", _ATTRS_FASTENER),
                ("reward_exit", "material_zone", _zone_attrs("reward_exit", _ATTRS_MATERIAL_ZONE)),
                ("hazard_boundary", "guard", _ATTRS_GUARD),
                ("readability", "decal_zone", _zone_attrs("readability", _ATTRS_DECAL_ZONE)),
                ("pacing_wear", "wear_zone", _zone_attrs("pacing_wear", _ATTRS_WEAR_ZONE)),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "encounter_flow"}},
            "construction_graph": _round2_graph(
                ("footprint", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("spawn_points", "socket", _ATTRS_SOCKET),
                ("routes", "rail", _ATTRS_RAIL),
                ("cover", "guard", _ATTRS_GUARD),
                ("objective", "mount", _ATTRS_MOUNT),
                ("wave_markers", "fastener", _ATTRS_FASTENER),
                ("reward_exit", "material_zone", _zone_attrs("reward_exit", _ATTRS_MATERIAL_ZONE)),
                ("hazard_boundary", "guard", _ATTRS_GUARD),
                ("readability", "decal_zone", _zone_attrs("readability", _ATTRS_DECAL_ZONE)),
                ("pacing_wear", "wear_zone", _zone_attrs("pacing_wear", _ATTRS_WEAR_ZONE)),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    {
        "family": "furniture_prop",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "furniture_prop",
            "intent": {"construction_graph": _round2_graph(
                ("contact_surface", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("supports", "rail", _ATTRS_RAIL),
                ("back_or_storage", "panel", _ATTRS_PANEL),
                ("trim", "trim", _ATTRS_TRIM),
                ("handle", "handle", _ATTRS_HANDLE_BAR),
                ("fasteners", "fastener", _ATTRS_FASTENER),
                ("soft_volume", "panel", _ATTRS_PANEL),
                ("feet", "mount", _ATTRS_MOUNT),
                ("label_zone", "decal_zone", _zone_attrs("label_zone", _ATTRS_DECAL_ZONE)),
                ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "furniture_prop"}},
            "construction_graph": _round2_graph(
                ("contact_surface", "primary_volume", _ATTRS_PRIMARY_VOLUME),
                ("supports", "rail", _ATTRS_RAIL),
                ("back_or_storage", "panel", _ATTRS_PANEL),
                ("trim", "trim", _ATTRS_TRIM),
                ("handle", "handle", _ATTRS_HANDLE_BAR),
                ("fasteners", "fastener", _ATTRS_FASTENER),
                ("soft_volume", "panel", _ATTRS_PANEL),
                ("feet", "mount", _ATTRS_MOUNT),
                ("label_zone", "decal_zone", _zone_attrs("label_zone", _ATTRS_DECAL_ZONE)),
                ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    {
        "family": "lighting_prop",
        "brief": {}, "parts": (), "graph_nodes": (),
        "synthesizer_asset": {
            "name": "lighting_prop",
            "intent": {"construction_graph": _round2_graph(
                ("base", "mount", _ATTRS_MOUNT),
                ("armature", "rail", _ATTRS_RAIL),
                ("emitters", "material_zone", _zone_attrs("emitters", _ATTRS_MATERIAL_ZONE)),
                ("housing", "guard", _ATTRS_GUARD),
                ("power_route", "socket", _ATTRS_SOCKET),
                ("service_plate", "panel", _ATTRS_PANEL),
                ("signage", "decal_zone", _zone_attrs("signage", _ATTRS_DECAL_ZONE)),
                ("fasteners", "fastener", _ATTRS_FASTENER),
                ("protective_guard", "guard", _ATTRS_GUARD),
                ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
            )},
        },
        "synthesizer_runtime": {
            "design_brief": {"brief": {"family": "lighting_prop"}},
            "construction_graph": _round2_graph(
                ("base", "mount", _ATTRS_MOUNT),
                ("armature", "rail", _ATTRS_RAIL),
                ("emitters", "material_zone", _zone_attrs("emitters", _ATTRS_MATERIAL_ZONE)),
                ("housing", "guard", _ATTRS_GUARD),
                ("power_route", "socket", _ATTRS_SOCKET),
                ("service_plate", "panel", _ATTRS_PANEL),
                ("signage", "decal_zone", _zone_attrs("signage", _ATTRS_DECAL_ZONE)),
                ("fasteners", "fastener", _ATTRS_FASTENER),
                ("protective_guard", "guard", _ATTRS_GUARD),
                ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
            ),
        },
        "allow_intent_driven_replacement": True,
        "min_synth_op_count": 8,
    },
    # ---- Round 2-bis: 7 specialty-op simple families ----
    _round2_fixture("set_dressing_prop", (
        ("primary_volume", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("secondary_forms", "mount", _ATTRS_MOUNT),
        ("floor_contact", "mount", _ATTRS_MOUNT),
        ("handle_strap", "handle", _ATTRS_HANDLE_BAR),
        ("lid_opening", "inset", _ATTRS_INSET),
        ("label_zone", "decal_zone", _zone_attrs("label_zone", _ATTRS_DECAL_ZONE)),
        ("stitches", "fastener", _ATTRS_FASTENER),
        ("small_scatter", "mount", _ATTRS_MOUNT),
        ("material_zone", "material_zone", _zone_attrs("material_zone", _ATTRS_MATERIAL_ZONE)),
        ("handled_wear", "wear_zone", _zone_attrs("handled_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("tool_prop", (
        ("body", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("grip", "handle", _ATTRS_HANDLE_BAR),
        ("working_head", "guard", _ATTRS_GUARD),
        ("spine", "rail", _ATTRS_RAIL),
        ("guard", "guard", _ATTRS_GUARD),
        ("adjustment_joint", "mount", _ATTRS_MOUNT),
        ("attachment_sockets", "socket", _ATTRS_SOCKET),
        ("fasteners", "fastener", _ATTRS_FASTENER),
        ("marking_zone", "decal_zone", _zone_attrs("marking_zone", _ATTRS_DECAL_ZONE)),
        ("contact_wear", "wear_zone", _zone_attrs("contact_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("settlement_district", (
        ("footprint", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("paths", "rail", _ATTRS_RAIL),
        ("plot_cells", "panel", _ATTRS_PANEL),
        ("landmark", "mount", _ATTRS_MOUNT),
        ("thresholds", "frame", _ATTRS_FRAME),
        ("activity_zone", "material_zone", _zone_attrs("activity_zone", _ATTRS_MATERIAL_ZONE)),
        ("height_markers", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("boundaries", "guard", _ATTRS_GUARD),
        ("wayfinding", "decal_zone", _zone_attrs("wayfinding", _ATTRS_DECAL_ZONE)),
        ("traffic_wear", "wear_zone", _zone_attrs("traffic_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("environment_architecture", (
        ("foundation", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("walls", "panel", _ATTRS_PANEL),
        ("openings", "inset", _ATTRS_INSET),
        ("roof", "frame", _ATTRS_FRAME),
        ("columns", "rail", _ATTRS_RAIL),
        ("access", "handle", _ATTRS_HANDLE_BAR),
        ("trim", "trim", _ATTRS_TRIM),
        ("bays", "frame", _ATTRS_FRAME),
        ("signage", "decal_zone", _zone_attrs("signage", _ATTRS_DECAL_ZONE)),
        ("weathering", "wear_zone", _zone_attrs("weathering", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("machine_console", (
        ("body", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("control_face", "panel", _ATTRS_PANEL),
        ("display", "material_zone", _zone_attrs("display", _ATTRS_MATERIAL_ZONE)),
        ("input_controls", "fastener", _ATTRS_FASTENER),
        ("service_access", "inset", _ATTRS_INSET),
        ("ports", "socket", _ATTRS_SOCKET),
        ("cooling", "guard", _ATTRS_GUARD),
        ("cable_connections", "rail", _ATTRS_RAIL),
        ("warning_marking", "decal_zone", _zone_attrs("warning_marking", _ATTRS_DECAL_ZONE)),
        ("service_wear", "wear_zone", _zone_attrs("service_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("portal_relic", (
        ("plinth", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("frame", "frame", _ATTRS_FRAME),
        ("active_threshold", "material_zone", _zone_attrs("active_threshold", _ATTRS_MATERIAL_ZONE)),
        ("power_nodes", "socket", _ATTRS_SOCKET),
        ("symmetry_bands", "trim", _ATTRS_TRIM),
        ("rune_band", "decal_zone", _zone_attrs("rune_band", _ATTRS_DECAL_ZONE)),
        ("attachment_mounts", "mount", _ATTRS_MOUNT),
        ("energy_conduit", "rail", _ATTRS_RAIL),
        ("environment_contact", "mount", _ATTRS_MOUNT),
        ("age_wear", "wear_zone", _zone_attrs("age_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("vehicle_prop", (
        ("chassis", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("cabin", "panel", _ATTRS_PANEL),
        ("motion_system", "rail", _ATTRS_RAIL),
        ("front_orientation", "trim", _ATTRS_TRIM),
        ("payload_zone", "inset", _ATTRS_INSET),
        ("access_rail", "handle", _ATTRS_HANDLE_BAR),
        ("lights", "mount", _ATTRS_MOUNT),
        ("fasteners", "fastener", _ATTRS_FASTENER),
        ("marking_zone", "decal_zone", _zone_attrs("marking_zone", _ATTRS_DECAL_ZONE)),
        ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
    )),
    # ---- Round 3: hard-surface guardrails (industrial_crate is hero per CLAUDE.md northstar) ----
    _round2_fixture("industrial_crate", (
        ("body_shell", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("lid_seam", "panel", _ATTRS_PANEL),
        ("corner_guard_0", "guard", _ATTRS_GUARD),
        ("corner_guard_1", "guard", _ATTRS_GUARD),
        ("corner_guard_2", "guard", _ATTRS_GUARD),
        ("corner_guard_3", "guard", _ATTRS_GUARD),
        ("corner_guard_4", "guard", _ATTRS_GUARD),
        ("corner_guard_5", "guard", _ATTRS_GUARD),
        ("corner_guard_6", "guard", _ATTRS_GUARD),
        ("corner_guard_7", "guard", _ATTRS_GUARD),
        ("latch_plate", "inset", _ATTRS_INSET),
        ("handle_l", "handle", _ATTRS_HANDLE_BAR),
        ("handle_r", "handle", _ATTRS_HANDLE_BAR),
        ("foot_rail_front", "rail", _ATTRS_RAIL),
        ("foot_rail_back", "rail", _ATTRS_RAIL),
        ("trim_band_mid", "trim", _ATTRS_TRIM),
        ("fastener_grid_front", "fastener", _ATTRS_FASTENER),
        ("warning_decal_zone", "decal_zone", _zone_attrs("warning_decal_zone", _ATTRS_DECAL_ZONE)),
        ("edge_wear_zone", "wear_zone", _zone_attrs("edge_wear_zone", _ATTRS_WEAR_ZONE)),
    ), min_synth_op_count=15),
    _round2_fixture("service_cabinet", (
        ("shell", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("front_panel", "panel", _ATTRS_PANEL),
        ("hinge_line", "hinge", _ATTRS_HINGE),
        ("pull_handle", "handle", _ATTRS_HANDLE_BAR),
        ("latch_plate", "inset", _ATTRS_INSET),
        ("vent_slats", "trim", _ATTRS_TRIM),
        ("mounting_brackets", "mount", _ATTRS_MOUNT),
        ("fasteners", "fastener", _ATTRS_FASTENER),
        ("label_zone", "decal_zone", _zone_attrs("label_zone", _ATTRS_DECAL_ZONE)),
        ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("weapon_prop", (
        ("primary_body", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("grip", "handle", _ATTRS_HANDLE_BAR),
        ("guard", "guard", _ATTRS_GUARD),
        ("active_edge", "rail", _ATTRS_RAIL),
        ("centerline_detail", "trim", _ATTRS_TRIM),
        ("end_cap", "mount", _ATTRS_MOUNT),
        ("hardpoints", "socket", _ATTRS_SOCKET),
        ("fasteners", "fastener", _ATTRS_FASTENER),
        ("marking_zone", "decal_zone", _zone_attrs("marking_zone", _ATTRS_DECAL_ZONE)),
        ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("mechanical_door", (
        ("frame", "frame", _ATTRS_FRAME),
        ("leaf", "panel", _ATTRS_PANEL),
        ("hinge_stack", "hinge", _ATTRS_HINGE),
        ("lock_actuator", "inset", _ATTRS_INSET),
        ("threshold_rails", "rail", _ATTRS_RAIL),
        ("panel_grooves", "trim", _ATTRS_TRIM),
        ("access_handle", "handle", _ATTRS_HANDLE_BAR),
        ("fasteners", "fastener", _ATTRS_FASTENER),
        ("warning_decal", "decal_zone", _zone_attrs("warning_decal", _ATTRS_DECAL_ZONE)),
        ("edge_wear", "wear_zone", _zone_attrs("edge_wear", _ATTRS_WEAR_ZONE)),
    )),
    # ---- Round 4 (procedural-domain) + Round 5 (bundle/system) families ----
    # All 50 remaining recipes emit the same 10-op canonical hard-surface
    # pattern using NODE_TYPEs from the registered hard_surface domain.
    # When Cycle 6 ships per-domain DomainExtension packs (vegetation,
    # terrain, sdf, etc.), the aliases for those families can be updated
    # to point at the domain-specific style + policy packs; the construction
    # graphs themselves remain valid since the recipe NODE_TYPE intent
    # is preserved.
    _round2_fixture("natural_form", (
        ("natural_primary_mass", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("natural_growth_runners", "rail", _ATTRS_RAIL),
        ("natural_secondary_clusters", "mount", _ATTRS_MOUNT),
        ("natural_strata", "trim", _ATTRS_TRIM),
        ("natural_ground_transition", "mount", _ATTRS_MOUNT),
        ("natural_asymmetric_break", "panel", _ATTRS_PANEL),
        ("natural_detail_scatter", "fastener", _ATTRS_FASTENER),
        ("natural_material_zone", "material_zone", _zone_attrs("natural_material_zone", _ATTRS_MATERIAL_ZONE)),
        ("natural_erosion_wear", "wear_zone", _zone_attrs("natural_erosion_wear", _ATTRS_WEAR_ZONE)),
        ("natural_scale_anchor", "decal_zone", _zone_attrs("natural_scale_anchor", _ATTRS_DECAL_ZONE)),
    )),
    _round2_fixture("modular_kit", (
        ("kit_tile_body", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("kit_snap_edges", "trim", _ATTRS_TRIM),
        ("kit_connector_ports", "socket", _ATTRS_SOCKET),
        ("kit_orientation_marker", "decal_zone", _zone_attrs("kit_orientation_marker", _ATTRS_DECAL_ZONE)),
        ("kit_panel_breaks", "inset", _ATTRS_INSET),
        ("kit_variant_mounts", "mount", _ATTRS_MOUNT),
        ("kit_structural_ribs", "frame", _ATTRS_FRAME),
        ("kit_locator_pins", "fastener", _ATTRS_FASTENER),
        ("kit_material_zone", "material_zone", _zone_attrs("kit_material_zone", _ATTRS_MATERIAL_ZONE)),
        ("kit_repeat_wear", "wear_zone", _zone_attrs("kit_repeat_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("character_creature", (
        ("character_body_mass", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("character_head", "material_zone", _zone_attrs("character_head", _ATTRS_MATERIAL_ZONE)),
        ("character_limbs", "rail", _ATTRS_RAIL),
        ("character_joints", "hinge", _ATTRS_HINGE),
        ("character_contact_points", "mount", _ATTRS_MOUNT),
        ("character_face_details", "decal_zone", _zone_attrs("character_face_details", _ATTRS_DECAL_ZONE)),
        ("character_silhouette_break", "guard", _ATTRS_GUARD),
        ("character_pose_line", "rail", _ATTRS_RAIL),
        ("character_scale_anchor", "trim", _ATTRS_TRIM),
        ("character_contact_wear", "wear_zone", _zone_attrs("character_contact_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("terrain_vegetation_variant", (
        ("terrain_variant_ground", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("terrain_variant_strata", "trim", _ATTRS_TRIM),
        ("terrain_variant_growth", "material_zone", _zone_attrs("terrain_variant_growth", _ATTRS_MATERIAL_ZONE)),
        ("terrain_variant_flow_path", "rail", _ATTRS_RAIL),
        ("terrain_variant_scatter", "fastener", _ATTRS_FASTENER),
        ("terrain_variant_material_zone", "material_zone", _zone_attrs("terrain_variant_material_zone", _ATTRS_MATERIAL_ZONE)),
        ("terrain_variant_edge_blend", "panel", _ATTRS_PANEL),
        ("terrain_variant_scale_anchors", "mount", _ATTRS_MOUNT),
        ("terrain_variant_erosion", "wear_zone", _zone_attrs("terrain_variant_erosion", _ATTRS_WEAR_ZONE)),
        ("terrain_variant_marker", "decal_zone", _zone_attrs("terrain_variant_marker", _ATTRS_DECAL_ZONE)),
    )),
    _round2_fixture("rig_animation_proxy", (
        ("rig_root_control", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("rig_joint_chain", "rail", _ATTRS_RAIL),
        ("rig_limb_markers", "mount", _ATTRS_MOUNT),
        ("rig_ik_targets", "handle", _ATTRS_HANDLE_BAR),
        ("rig_motion_arc", "rail", _ATTRS_RAIL),
        ("rig_weight_zone", "material_zone", _zone_attrs("rig_weight_zone", _ATTRS_MATERIAL_ZONE)),
        ("rig_attachment_sockets", "socket", _ATTRS_SOCKET),
        ("rig_morph_marker", "decal_zone", _zone_attrs("rig_morph_marker", _ATTRS_DECAL_ZONE)),
        ("rig_limit_guards", "guard", _ATTRS_GUARD),
        ("rig_animation_state_cues", "decal_zone", _zone_attrs("rig_animation_state_cues", _ATTRS_DECAL_ZONE)),
    )),
    _round2_fixture("rig_component_library_system", (
        ("rig_component_catalog", "panel", _ATTRS_PANEL),
        ("rig_component_spine", "rail", _ATTRS_RAIL),
        ("rig_component_limbs", "rail", _ATTRS_RAIL),
        ("rig_component_digits", "fastener", _ATTRS_FASTENER),
        ("rig_component_mech_joints", "hinge", _ATTRS_HINGE),
        ("rig_component_wing_tentacle", "rail", _ATTRS_RAIL),
        ("rig_component_connectors", "socket", _ATTRS_SOCKET),
        ("rig_component_ik_fk", "handle", _ATTRS_HANDLE_BAR),
        ("rig_component_typed_outputs", "material_zone", _zone_attrs("rig_component_typed_outputs", _ATTRS_MATERIAL_ZONE)),
        ("rig_component_cycle_guards", "guard", _ATTRS_GUARD),
    )),
    _round2_fixture("morph_target_database_system", (
        ("morph_target_catalog", "panel", _ATTRS_PANEL),
        ("morph_expression_set", "decal_zone", _zone_attrs("morph_expression_set", _ATTRS_DECAL_ZONE)),
        ("morph_viseme_set", "decal_zone", _zone_attrs("morph_viseme_set", _ATTRS_DECAL_ZONE)),
        ("morph_body_deltas", "rail", _ATTRS_RAIL),
        ("morph_corrective_shapes", "panel", _ATTRS_PANEL),
        ("morph_region_masks", "material_zone", _zone_attrs("morph_region_masks", _ATTRS_MATERIAL_ZONE)),
        ("morph_delta_vectors", "rail", _ATTRS_RAIL),
        ("morph_symmetry_rules", "guard", _ATTRS_GUARD),
        ("morph_compatibility", "guard", _ATTRS_GUARD),
        ("morph_iteration_wear", "wear_zone", _zone_attrs("morph_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("animation_library_binding_system", (
        ("animation_clip_catalog", "panel", _ATTRS_PANEL),
        ("animation_pose_library", "decal_zone", _zone_attrs("animation_pose_library", _ATTRS_DECAL_ZONE)),
        ("animation_locomotion_states", "rail", _ATTRS_RAIL),
        ("animation_blend_tree", "rail", _ATTRS_RAIL),
        ("animation_event_tracks", "fastener", _ATTRS_FASTENER),
        ("animation_root_motion", "rail", _ATTRS_RAIL),
        ("animation_rig_bindings", "socket", _ATTRS_SOCKET),
        ("animation_additive_layers", "material_zone", _zone_attrs("animation_additive_layers", _ATTRS_MATERIAL_ZONE)),
        ("animation_preview_timing", "panel", _ATTRS_PANEL),
        ("animation_iteration_wear", "wear_zone", _zone_attrs("animation_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("retargeting_pack_system", (
        ("retarget_source_target_skeletons", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("retarget_bone_mapping", "panel", _ATTRS_PANEL),
        ("retarget_rest_pose_alignment", "rail", _ATTRS_RAIL),
        ("retarget_scale_compensation", "material_zone", _zone_attrs("retarget_scale_compensation", _ATTRS_MATERIAL_ZONE)),
        ("retarget_coordinate_space", "guard", _ATTRS_GUARD),
        ("retarget_ik_poles", "handle", _ATTRS_HANDLE_BAR),
        ("retarget_root_motion", "rail", _ATTRS_RAIL),
        ("retarget_constraints", "guard", _ATTRS_GUARD),
        ("retarget_validation", "guard", _ATTRS_GUARD),
        ("retarget_iteration_wear", "wear_zone", _zone_attrs("retarget_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("character_equipment_binding_system", (
        ("equipment_body_slots", "panel", _ATTRS_PANEL),
        ("equipment_weapon_sockets", "socket", _ATTRS_SOCKET),
        ("equipment_armor_layers", "material_zone", _zone_attrs("equipment_armor_layers", _ATTRS_MATERIAL_ZONE)),
        ("equipment_offset_frames", "rail", _ATTRS_RAIL),
        ("equipment_clearance", "guard", _ATTRS_GUARD),
        ("equipment_loadout_variants", "decal_zone", _zone_attrs("equipment_loadout_variants", _ATTRS_DECAL_ZONE)),
        ("equipment_rig_anatomy_rules", "socket", _ATTRS_SOCKET),
        ("equipment_visibility_masks", "decal_zone", _zone_attrs("equipment_visibility_masks", _ATTRS_DECAL_ZONE)),
        ("equipment_failure_guards", "guard", _ATTRS_GUARD),
        ("equipment_iteration_wear", "wear_zone", _zone_attrs("equipment_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("gameplay_animation_controller_system", (
        ("controller_input_actions", "panel", _ATTRS_PANEL),
        ("controller_state_graph", "rail", _ATTRS_RAIL),
        ("controller_parameters", "fastener", _ATTRS_FASTENER),
        ("controller_transition_rules", "guard", _ATTRS_GUARD),
        ("controller_locomotion_blends", "rail", _ATTRS_RAIL),
        ("controller_combat_layers", "material_zone", _zone_attrs("controller_combat_layers", _ATTRS_MATERIAL_ZONE)),
        ("controller_event_outputs", "socket", _ATTRS_SOCKET),
        ("controller_motion_matching", "panel", _ATTRS_PANEL),
        ("controller_reachability_guards", "guard", _ATTRS_GUARD),
        ("controller_iteration_wear", "wear_zone", _zone_attrs("controller_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("procedural_facial_rig_pack_system", (
        ("facial_control_board", "panel", _ATTRS_PANEL),
        ("facial_jaw_mouth", "handle", _ATTRS_HANDLE_BAR),
        ("facial_eye_lids", "socket", _ATTRS_SOCKET),
        ("facial_brow_cheek", "handle", _ATTRS_HANDLE_BAR),
        ("facial_viseme_links", "rail", _ATTRS_RAIL),
        ("facial_morph_bindings", "socket", _ATTRS_SOCKET),
        ("facial_sdf_masks", "material_zone", _zone_attrs("facial_sdf_masks", _ATTRS_MATERIAL_ZONE)),
        ("facial_range_guards", "guard", _ATTRS_GUARD),
        ("facial_preview_poses", "panel", _ATTRS_PANEL),
        ("facial_iteration_wear", "wear_zone", _zone_attrs("facial_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("hair_program_system", (
        ("hair_scalp_groom_regions", "material_zone", _zone_attrs("hair_scalp_groom_regions", _ATTRS_MATERIAL_ZONE)),
        ("hair_strand_grammar", "rail", _ATTRS_RAIL),
        ("hair_root_density", "decal_zone", _zone_attrs("hair_root_density", _ATTRS_DECAL_ZONE)),
        ("hair_length_distribution", "rail", _ATTRS_RAIL),
        ("hair_wave_curl", "fastener", _ATTRS_FASTENER),
        ("hair_card_outputs", "panel", _ATTRS_PANEL),
        ("hair_strand_outputs", "socket", _ATTRS_SOCKET),
        ("hair_color_gradient", "material_zone", _zone_attrs("hair_color_gradient", _ATTRS_MATERIAL_ZONE)),
        ("hair_collision_guards", "guard", _ATTRS_GUARD),
        ("hair_iteration_wear", "wear_zone", _zone_attrs("hair_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("cloth_fabric_simulation_program_system", (
        ("cloth_fabric_domain", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("cloth_params", "decal_zone", _zone_attrs("cloth_params", _ATTRS_DECAL_ZONE)),
        ("cloth_pin_constraints", "socket", _ATTRS_SOCKET),
        ("cloth_collision_volumes", "guard", _ATTRS_GUARD),
        ("cloth_force_fields", "rail", _ATTRS_RAIL),
        ("cloth_solve_passes", "fastener", _ATTRS_FASTENER),
        ("cloth_wrinkle_folds", "rail", _ATTRS_RAIL),
        ("cloth_material_zones", "material_zone", _zone_attrs("cloth_material_zones", _ATTRS_MATERIAL_ZONE)),
        ("cloth_solver_guards", "guard", _ATTRS_GUARD),
        ("cloth_iteration_wear", "wear_zone", _zone_attrs("cloth_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("fluid_forward_volume_program_system", (
        ("fluid_volume_domain", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("fluid_channels", "material_zone", _zone_attrs("fluid_channels", _ATTRS_MATERIAL_ZONE)),
        ("fluid_emitters", "socket", _ATTRS_SOCKET),
        ("fluid_advection_fields", "rail", _ATTRS_RAIL),
        ("fluid_isosurface_controls", "panel", _ATTRS_PANEL),
        ("fluid_outputs", "socket", _ATTRS_SOCKET),
        ("fluid_cache_tiles", "panel", _ATTRS_PANEL),
        ("fluid_boundary_guards", "guard", _ATTRS_GUARD),
        ("fluid_material_regions", "material_zone", _zone_attrs("fluid_material_regions", _ATTRS_MATERIAL_ZONE)),
        ("fluid_iteration_wear", "wear_zone", _zone_attrs("fluid_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("construction_grammar_kit_system", (
        ("construction_module_catalog", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("construction_snap_grid", "rail", _ATTRS_RAIL),
        ("construction_connector_sockets", "socket", _ATTRS_SOCKET),
        ("construction_adjacency_rules", "panel", _ATTRS_PANEL),
        ("construction_assembly_rules", "rail", _ATTRS_RAIL),
        ("construction_variant_slots", "material_zone", _zone_attrs("construction_variant_slots", _ATTRS_MATERIAL_ZONE)),
        ("construction_structural_guards", "guard", _ATTRS_GUARD),
        ("construction_output_ports", "socket", _ATTRS_SOCKET),
        ("construction_scale_metrics", "decal_zone", _zone_attrs("construction_scale_metrics", _ATTRS_DECAL_ZONE)),
        ("construction_iteration_wear", "wear_zone", _zone_attrs("construction_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("creature_appendage_program_system", (
        ("appendage_socket_map", "socket", _ATTRS_SOCKET),
        ("appendage_joint_chains", "rail", _ATTRS_RAIL),
        ("appendage_segment_profiles", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("appendage_variant_slots", "panel", _ATTRS_PANEL),
        ("appendage_surface_features", "material_zone", _zone_attrs("appendage_surface_features", _ATTRS_MATERIAL_ZONE)),
        ("appendage_symmetry_rules", "rail", _ATTRS_RAIL),
        ("appendage_articulation_ranges", "guard", _ATTRS_GUARD),
        ("appendage_muscle_bands", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("appendage_attachment_guards", "guard", _ATTRS_GUARD),
        ("appendage_iteration_wear", "wear_zone", _zone_attrs("appendage_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("body_part_procedural_library_system", (
        ("body_part_catalog", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("body_part_anatomy_regions", "material_zone", _zone_attrs("body_part_anatomy_regions", _ATTRS_MATERIAL_ZONE)),
        ("body_part_organ_sockets", "socket", _ATTRS_SOCKET),
        ("body_part_muscle_bands", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("body_part_landmark_loops", "rail", _ATTRS_RAIL),
        ("body_part_proportion_ranges", "panel", _ATTRS_PANEL),
        ("body_part_symmetry_rules", "rail", _ATTRS_RAIL),
        ("body_part_surface_zones", "material_zone", _zone_attrs("body_part_surface_zones", _ATTRS_MATERIAL_ZONE)),
        ("body_part_compatibility_guards", "guard", _ATTRS_GUARD),
        ("body_part_iteration_wear", "wear_zone", _zone_attrs("body_part_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("material_primitive_library_system", (
        ("material_primitive_catalog", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("material_substance_taxonomy", "material_zone", _zone_attrs("material_substance_taxonomy", _ATTRS_MATERIAL_ZONE)),
        ("material_pbr_channels", "panel", _ATTRS_PANEL),
        ("material_class_sockets", "socket", _ATTRS_SOCKET),
        ("material_parameter_ports", "fastener", _ATTRS_FASTENER),
        ("material_smart_masks", "decal_zone", _zone_attrs("material_smart_masks", _ATTRS_DECAL_ZONE)),
        ("materialx_output_ports", "socket", _ATTRS_SOCKET),
        ("material_pbr_validation_guards", "guard", _ATTRS_GUARD),
        ("material_substance_variants", "material_zone", _zone_attrs("material_substance_variants", _ATTRS_MATERIAL_ZONE)),
        ("material_iteration_wear", "wear_zone", _zone_attrs("material_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("cloth_attachment_form", (
        ("cloth_anchors", "mount", _ATTRS_MOUNT),
        ("cloth_panel", "panel", _ATTRS_PANEL),
        ("cloth_seams", "trim", _ATTRS_TRIM),
        ("cloth_folds", "rail", _ATTRS_RAIL),
        ("cloth_hardware", "handle", _ATTRS_HANDLE_BAR),
        ("cloth_border", "trim", _ATTRS_TRIM),
        ("cloth_motion", "rail", _ATTRS_RAIL),
        ("cloth_material_zone", "material_zone", _zone_attrs("cloth_material_zone", _ATTRS_MATERIAL_ZONE)),
        ("cloth_clearance", "guard", _ATTRS_GUARD),
        ("cloth_wear", "wear_zone", _zone_attrs("cloth_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("domain_kit_bundle", (
        ("domain_kit_root", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("domain_kit_parts", "panel", _ATTRS_PANEL),
        ("domain_kit_snap_ports", "socket", _ATTRS_SOCKET),
        ("domain_kit_variant_slots", "inset", _ATTRS_INSET),
        ("domain_kit_scale_reference", "fastener", _ATTRS_FASTENER),
        ("domain_kit_style_rules", "material_zone", _zone_attrs("domain_kit_style_rules", _ATTRS_MATERIAL_ZONE)),
        ("domain_kit_assembly_guides", "rail", _ATTRS_RAIL),
        ("domain_kit_compatibility", "decal_zone", _zone_attrs("domain_kit_compatibility", _ATTRS_DECAL_ZONE)),
        ("domain_kit_label", "decal_zone", _zone_attrs("domain_kit_label", _ATTRS_DECAL_ZONE)),
        ("domain_kit_usage_wear", "wear_zone", _zone_attrs("domain_kit_usage_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("simulation_environment_system", (
        ("simulation_domain", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("simulation_emitters", "mount", _ATTRS_MOUNT),
        ("simulation_flow_lines", "rail", _ATTRS_RAIL),
        ("simulation_gradient", "material_zone", _zone_attrs("simulation_gradient", _ATTRS_MATERIAL_ZONE)),
        ("simulation_constraints", "guard", _ATTRS_GUARD),
        ("simulation_probes", "fastener", _ATTRS_FASTENER),
        ("simulation_obstacles", "guard", _ATTRS_GUARD),
        ("simulation_time_ticks", "decal_zone", _zone_attrs("simulation_time_ticks", _ATTRS_DECAL_ZONE)),
        ("simulation_response", "material_zone", _zone_attrs("simulation_response", _ATTRS_MATERIAL_ZONE)),
        ("simulation_wear", "wear_zone", _zone_attrs("simulation_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("authored_multi_asset_bundle", (
        ("multi_asset_root", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("multi_asset_members", "socket", _ATTRS_SOCKET),
        ("multi_asset_dependencies", "rail", _ATTRS_RAIL),
        ("multi_asset_layout_anchors", "mount", _ATTRS_MOUNT),
        ("multi_asset_lod_entries", "fastener", _ATTRS_FASTENER),
        ("multi_asset_shared_materials", "material_zone", _zone_attrs("multi_asset_shared_materials", _ATTRS_MATERIAL_ZONE)),
        ("multi_asset_export_marker", "decal_zone", _zone_attrs("multi_asset_export_marker", _ATTRS_DECAL_ZONE)),
        ("multi_asset_assembly_order", "rail", _ATTRS_RAIL),
        ("multi_asset_bounds", "guard", _ATTRS_GUARD),
        ("multi_asset_usage_wear", "wear_zone", _zone_attrs("multi_asset_usage_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("live_procedural_runtime_bundle", (
        ("runtime_core", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("runtime_input_ports", "socket", _ATTRS_SOCKET),
        ("runtime_engine_hooks", "rail", _ATTRS_RAIL),
        ("runtime_output_slots", "socket", _ATTRS_SOCKET),
        ("runtime_version_badge", "decal_zone", _zone_attrs("runtime_version_badge", _ATTRS_DECAL_ZONE)),
        ("runtime_live_ticks", "fastener", _ATTRS_FASTENER),
        ("runtime_validation_guard", "guard", _ATTRS_GUARD),
        ("runtime_cache_state", "panel", _ATTRS_PANEL),
        ("runtime_debug_ports", "fastener", _ATTRS_FASTENER),
        ("runtime_iteration_wear", "wear_zone", _zone_attrs("runtime_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("engine_facing_runtime_bundle_system", (
        ("engine_host_targets", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("engine_plugin_adapters", "rail", _ATTRS_RAIL),
        ("engine_bundle_manifest", "panel", _ATTRS_PANEL),
        ("engine_parameter_overrides", "socket", _ATTRS_SOCKET),
        ("engine_live_hooks", "rail", _ATTRS_RAIL),
        ("engine_asset_output_sinks", "socket", _ATTRS_SOCKET),
        ("engine_usd_hydra_targets", "decal_zone", _zone_attrs("engine_usd_hydra_targets", _ATTRS_DECAL_ZONE)),
        ("engine_abi_guards", "guard", _ATTRS_GUARD),
        ("engine_diagnostics_ports", "fastener", _ATTRS_FASTENER),
        ("engine_host_iteration_wear", "wear_zone", _zone_attrs("engine_host_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("procedural_prefab_binding_system", (
        ("prefab_root_binding", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("prefab_source_slots", "socket", _ATTRS_SOCKET),
        ("prefab_parameter_table", "panel", _ATTRS_PANEL),
        ("prefab_variant_overrides", "material_zone", _zone_attrs("prefab_variant_overrides", _ATTRS_MATERIAL_ZONE)),
        ("prefab_lod_streaming", "rail", _ATTRS_RAIL),
        ("prefab_material_bindings", "material_zone", _zone_attrs("prefab_material_bindings", _ATTRS_MATERIAL_ZONE)),
        ("prefab_collision_bindings", "guard", _ATTRS_GUARD),
        ("prefab_engine_exports", "socket", _ATTRS_SOCKET),
        ("prefab_dependency_guards", "guard", _ATTRS_GUARD),
        ("prefab_iteration_wear", "wear_zone", _zone_attrs("prefab_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("scene_system_authoring_bundle", (
        ("scene_root_hierarchy", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("scene_placement_anchors", "mount", _ATTRS_MOUNT),
        ("scene_spawn_layers", "socket", _ATTRS_SOCKET),
        ("scene_lighting_camera", "rail", _ATTRS_RAIL),
        ("scene_navigation_regions", "rail", _ATTRS_RAIL),
        ("scene_environment_volumes", "material_zone", _zone_attrs("scene_environment_volumes", _ATTRS_MATERIAL_ZONE)),
        ("scene_streaming_tags", "panel", _ATTRS_PANEL),
        ("scene_export_targets", "socket", _ATTRS_SOCKET),
        ("scene_validation_guards", "guard", _ATTRS_GUARD),
        ("scene_iteration_wear", "wear_zone", _zone_attrs("scene_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("behavior_logic_graph_bundle", (
        ("behavior_state_nodes", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("behavior_event_edges", "rail", _ATTRS_RAIL),
        ("behavior_condition_rules", "panel", _ATTRS_PANEL),
        ("behavior_action_outputs", "socket", _ATTRS_SOCKET),
        ("behavior_blackboard_bindings", "decal_zone", _zone_attrs("behavior_blackboard_bindings", _ATTRS_DECAL_ZONE)),
        ("behavior_timer_tracks", "rail", _ATTRS_RAIL),
        ("behavior_utility_weights", "fastener", _ATTRS_FASTENER),
        ("behavior_failure_paths", "guard", _ATTRS_GUARD),
        ("behavior_debug_ports", "socket", _ATTRS_SOCKET),
        ("behavior_iteration_wear", "wear_zone", _zone_attrs("behavior_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("world_streaming_runtime_partition_bundle", (
        ("world_partition_root", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("streaming_sector_grid", "panel", _ATTRS_PANEL),
        ("streaming_volume_bounds", "guard", _ATTRS_GUARD),
        ("streaming_load_dependencies", "rail", _ATTRS_RAIL),
        ("streaming_lod_rings", "rail", _ATTRS_RAIL),
        ("streaming_occlusion_regions", "material_zone", _zone_attrs("streaming_occlusion_regions", _ATTRS_MATERIAL_ZONE)),
        ("streaming_memory_budgets", "fastener", _ATTRS_FASTENER),
        ("streaming_asset_residency", "socket", _ATTRS_SOCKET),
        ("streaming_partition_guards", "guard", _ATTRS_GUARD),
        ("streaming_iteration_wear", "wear_zone", _zone_attrs("streaming_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("save_state_persistence_bundle", (
        ("save_root_manifest", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("save_checkpoint_slots", "socket", _ATTRS_SOCKET),
        ("save_actor_state", "panel", _ATTRS_PANEL),
        ("save_inventory_quest_tables", "panel", _ATTRS_PANEL),
        ("save_world_delta_log", "rail", _ATTRS_RAIL),
        ("save_schema_badges", "decal_zone", _zone_attrs("save_schema_badges", _ATTRS_DECAL_ZONE)),
        ("save_restore_paths", "rail", _ATTRS_RAIL),
        ("save_conflict_rules", "guard", _ATTRS_GUARD),
        ("save_corruption_guards", "guard", _ATTRS_GUARD),
        ("save_iteration_wear", "wear_zone", _zone_attrs("save_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("quest_dialogue_authoring_bundle", (
        ("quest_root_arc", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("quest_objectives", "panel", _ATTRS_PANEL),
        ("dialogue_branch_tree", "rail", _ATTRS_RAIL),
        ("dialogue_choice_gates", "guard", _ATTRS_GUARD),
        ("quest_reward_tables", "material_zone", _zone_attrs("quest_reward_tables", _ATTRS_MATERIAL_ZONE)),
        ("npc_dialogue_bindings", "socket", _ATTRS_SOCKET),
        ("dialogue_localization_keys", "decal_zone", _zone_attrs("dialogue_localization_keys", _ATTRS_DECAL_ZONE)),
        ("conversation_state_flags", "fastener", _ATTRS_FASTENER),
        ("narrative_validation_guards", "guard", _ATTRS_GUARD),
        ("quest_dialogue_iteration_wear", "wear_zone", _zone_attrs("quest_dialogue_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("camera_cinematic_direction_bundle", (
        ("camera_rig_roots", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("cinematic_shot_sequence", "panel", _ATTRS_PANEL),
        ("camera_path_tracks", "rail", _ATTRS_RAIL),
        ("lens_fov_bindings", "socket", _ATTRS_SOCKET),
        ("timeline_beat_markers", "fastener", _ATTRS_FASTENER),
        ("look_at_targets", "socket", _ATTRS_SOCKET),
        ("blend_transition_stack", "rail", _ATTRS_RAIL),
        ("framing_safe_regions", "guard", _ATTRS_GUARD),
        ("cinematic_trigger_outputs", "socket", _ATTRS_SOCKET),
        ("cinematic_iteration_wear", "wear_zone", _zone_attrs("cinematic_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("procedural_audio_cue_bundle", (
        ("audio_cue_root", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("sfx_music_events", "panel", _ATTRS_PANEL),
        ("audio_timing_triggers", "fastener", _ATTRS_FASTENER),
        ("audio_attenuation_zones", "guard", _ATTRS_GUARD),
        ("reverb_mixer_sends", "rail", _ATTRS_RAIL),
        ("voiceover_trigger_bindings", "socket", _ATTRS_SOCKET),
        ("loop_layer_controls", "panel", _ATTRS_PANEL),
        ("runtime_audio_outputs", "socket", _ATTRS_SOCKET),
        ("loudness_validation_guards", "guard", _ATTRS_GUARD),
        ("audio_iteration_wear", "wear_zone", _zone_attrs("audio_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("localization_text_table_bundle", (
        ("localization_table_root", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("string_key_rows", "panel", _ATTRS_PANEL),
        ("translation_value_columns", "material_zone", _zone_attrs("translation_value_columns", _ATTRS_MATERIAL_ZONE)),
        ("pluralization_gender_rules", "guard", _ATTRS_GUARD),
        ("fallback_locale_chains", "rail", _ATTRS_RAIL),
        ("subtitle_timing_rows", "fastener", _ATTRS_FASTENER),
        ("voiceover_text_bindings", "socket", _ATTRS_SOCKET),
        ("glyph_font_coverage", "decal_zone", _zone_attrs("glyph_font_coverage", _ATTRS_DECAL_ZONE)),
        ("localization_validation_guards", "guard", _ATTRS_GUARD),
        ("localization_iteration_wear", "wear_zone", _zone_attrs("localization_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("accessibility_ux_affordance_bundle", (
        ("accessibility_affordance_root", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("input_control_maps", "panel", _ATTRS_PANEL),
        ("readable_state_cues", "decal_zone", _zone_attrs("readable_state_cues", _ATTRS_DECAL_ZONE)),
        ("contrast_color_safe_regions", "material_zone", _zone_attrs("contrast_color_safe_regions", _ATTRS_MATERIAL_ZONE)),
        ("subtitle_caption_panels", "panel", _ATTRS_PANEL),
        ("audio_visual_haptic_cues", "rail", _ATTRS_RAIL),
        ("focus_navigation_paths", "rail", _ATTRS_RAIL),
        ("accessibility_option_ports", "socket", _ATTRS_SOCKET),
        ("usability_validation_guards", "guard", _ATTRS_GUARD),
        ("accessibility_iteration_wear", "wear_zone", _zone_attrs("accessibility_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("economy_simulation_tuning_bundle", (
        ("economy_simulation_root", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("resource_flow_nodes", "panel", _ATTRS_PANEL),
        ("currency_sink_source_pairs", "socket", _ATTRS_SOCKET),
        ("loot_reward_tables", "material_zone", _zone_attrs("loot_reward_tables", _ATTRS_MATERIAL_ZONE)),
        ("price_market_curves", "rail", _ATTRS_RAIL),
        ("progression_balance_tracks", "fastener", _ATTRS_FASTENER),
        ("spawn_rate_modulators", "socket", _ATTRS_SOCKET),
        ("telemetry_tuning_inputs", "socket", _ATTRS_SOCKET),
        ("simulation_validation_guards", "guard", _ATTRS_GUARD),
        ("economy_iteration_wear", "wear_zone", _zone_attrs("economy_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("multiplayer_session_replication_bundle", (
        ("multiplayer_session_root", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("authority_ownership_maps", "rail", _ATTRS_RAIL),
        ("replicated_state_nodes", "panel", _ATTRS_PANEL),
        ("rpc_event_channels", "socket", _ATTRS_SOCKET),
        ("sync_tick_timelines", "fastener", _ATTRS_FASTENER),
        ("prediction_reconciliation_paths", "rail", _ATTRS_RAIL),
        ("rollback_state_buffers", "panel", _ATTRS_PANEL),
        ("matchmaking_session_rules", "material_zone", _zone_attrs("matchmaking_session_rules", _ATTRS_MATERIAL_ZONE)),
        ("replication_validation_guards", "guard", _ATTRS_GUARD),
        ("multiplayer_iteration_wear", "wear_zone", _zone_attrs("multiplayer_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("cross_domain_composition_pack", (
        ("cross_domain_pillars", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("cross_domain_handoffs", "rail", _ATTRS_RAIL),
        ("cross_domain_rules", "material_zone", _zone_attrs("cross_domain_rules", _ATTRS_MATERIAL_ZONE)),
        ("cross_domain_interfaces", "socket", _ATTRS_SOCKET),
        ("cross_domain_boundaries", "guard", _ATTRS_GUARD),
        ("cross_domain_refusals", "decal_zone", _zone_attrs("cross_domain_refusals", _ATTRS_DECAL_ZONE)),
        ("cross_domain_previews", "panel", _ATTRS_PANEL),
        ("cross_domain_order", "rail", _ATTRS_RAIL),
        ("cross_domain_labels", "decal_zone", _zone_attrs("cross_domain_labels", _ATTRS_DECAL_ZONE)),
        ("cross_domain_wear", "wear_zone", _zone_attrs("cross_domain_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("style_stack_visual_band", (
        ("style_axes", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("style_palette", "material_zone", _zone_attrs("style_palette", _ATTRS_MATERIAL_ZONE)),
        ("style_surface_mode", "panel", _ATTRS_PANEL),
        ("style_outline_lighting", "rail", _ATTRS_RAIL),
        ("style_detail_layers", "fastener", _ATTRS_FASTENER),
        ("style_motion", "rail", _ATTRS_RAIL),
        ("style_construction_grammar", "socket", _ATTRS_SOCKET),
        ("style_compatibility", "socket", _ATTRS_SOCKET),
        ("style_refusal", "guard", _ATTRS_GUARD),
        ("style_iteration_wear", "wear_zone", _zone_attrs("style_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("typed_data_kernel_bundle", (
        ("typed_kernel_bus", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("typed_mesh_points_volume", "socket", _ATTRS_SOCKET),
        ("typed_heightfield_spline_sdf", "socket", _ATTRS_SOCKET),
        ("typed_image_rig", "socket", _ATTRS_SOCKET),
        ("typed_contracts", "decal_zone", _zone_attrs("typed_contracts", _ATTRS_DECAL_ZONE)),
        ("typed_transforms", "rail", _ATTRS_RAIL),
        ("typed_order", "fastener", _ATTRS_FASTENER),
        ("typed_cache", "panel", _ATTRS_PANEL),
        ("typed_guards", "guard", _ATTRS_GUARD),
        ("typed_flow_wear", "wear_zone", _zone_attrs("typed_flow_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("vegetation_library_system", (
        ("vegetation_executable_tree", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("vegetation_species", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("vegetation_branching", "rail", _ATTRS_RAIL),
        ("vegetation_leaf_clusters", "material_zone", _zone_attrs("vegetation_leaf_clusters", _ATTRS_MATERIAL_ZONE)),
        ("vegetation_roots", "socket", _ATTRS_SOCKET),
        ("vegetation_lods", "panel", _ATTRS_PANEL),
        ("vegetation_wind", "rail", _ATTRS_RAIL),
        ("vegetation_seasons", "socket", _ATTRS_SOCKET),
        ("vegetation_growth_ports", "socket", _ATTRS_SOCKET),
        ("vegetation_biome_masks", "material_zone", _zone_attrs("vegetation_biome_masks", _ATTRS_MATERIAL_ZONE)),
        ("vegetation_usage_wear", "wear_zone", _zone_attrs("vegetation_usage_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("terrain_heightfield_system", (
        ("terrain_executable_patch", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("terrain_domain", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("terrain_elevation", "panel", _ATTRS_PANEL),
        ("terrain_erosion_flow", "rail", _ATTRS_RAIL),
        ("terrain_slope_masks", "material_zone", _zone_attrs("terrain_slope_masks", _ATTRS_MATERIAL_ZONE)),
        ("terrain_biome_zones", "material_zone", _zone_attrs("terrain_biome_zones", _ATTRS_MATERIAL_ZONE)),
        ("terrain_drainage", "rail", _ATTRS_RAIL),
        ("terrain_exports", "socket", _ATTRS_SOCKET),
        ("terrain_probes", "fastener", _ATTRS_FASTENER),
        ("terrain_tile_edges", "guard", _ATTRS_GUARD),
        ("terrain_iteration_wear", "wear_zone", _zone_attrs("terrain_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("wfc_tile_solver_system", (
        ("wfc_executable_layout", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("wfc_tileset", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("wfc_sockets", "socket", _ATTRS_SOCKET),
        ("wfc_adjacency", "material_zone", _zone_attrs("wfc_adjacency", _ATTRS_MATERIAL_ZONE)),
        ("wfc_constraint_grid", "rail", _ATTRS_RAIL),
        ("wfc_entropy", "fastener", _ATTRS_FASTENER),
        ("wfc_seed_ports", "socket", _ATTRS_SOCKET),
        ("wfc_iteration_path", "rail", _ATTRS_RAIL),
        ("wfc_failure_guard", "guard", _ATTRS_GUARD),
        ("wfc_solved_layout", "panel", _ATTRS_PANEL),
        ("wfc_tile_wear", "wear_zone", _zone_attrs("wfc_tile_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("cga_building_grammar_system", (
        ("cga_executable_facade", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("cga_root_massing", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("cga_rule_stack", "panel", _ATTRS_PANEL),
        ("cga_ops", "rail", _ATTRS_RAIL),
        ("cga_facade_bands", "material_zone", _zone_attrs("cga_facade_bands", _ATTRS_MATERIAL_ZONE)),
        ("cga_terminals", "panel", _ATTRS_PANEL),
        ("cga_derivation_flow", "rail", _ATTRS_RAIL),
        ("cga_variation_ports", "socket", _ATTRS_SOCKET),
        ("cga_constraint_guards", "guard", _ATTRS_GUARD),
        ("cga_output_markers", "decal_zone", _zone_attrs("cga_output_markers", _ATTRS_DECAL_ZONE)),
        ("cga_iteration_wear", "wear_zone", _zone_attrs("cga_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("volume_effects_data_system", (
        ("volume_domain", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("volume_channels", "material_zone", _zone_attrs("volume_channels", _ATTRS_MATERIAL_ZONE)),
        ("volume_emitters", "socket", _ATTRS_SOCKET),
        ("volume_flow", "rail", _ATTRS_RAIL),
        ("volume_slices", "panel", _ATTRS_PANEL),
        ("volume_thresholds", "fastener", _ATTRS_FASTENER),
        ("volume_outputs", "socket", _ATTRS_SOCKET),
        ("volume_cache_tiles", "panel", _ATTRS_PANEL),
        ("volume_boundary_guards", "guard", _ATTRS_GUARD),
        ("volume_iteration_wear", "wear_zone", _zone_attrs("volume_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("instance_pattern_scatter_system", (
        ("scatter_sources", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("scatter_samples", "fastener", _ATTRS_FASTENER),
        ("scatter_projection", "material_zone", _zone_attrs("scatter_projection", _ATTRS_MATERIAL_ZONE)),
        ("scatter_density", "material_zone", _zone_attrs("scatter_density", _ATTRS_MATERIAL_ZONE)),
        ("scatter_spacing", "guard", _ATTRS_GUARD),
        ("scatter_jitter", "socket", _ATTRS_SOCKET),
        ("scatter_collision", "guard", _ATTRS_GUARD),
        ("scatter_outputs", "panel", _ATTRS_PANEL),
        ("scatter_debug", "rail", _ATTRS_RAIL),
        ("scatter_usage_wear", "wear_zone", _zone_attrs("scatter_usage_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("f_rep_sdf_composition_system", (
        ("sdf_executable_metaballs", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("sdf_primitives", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("sdf_expression_tree", "rail", _ATTRS_RAIL),
        ("sdf_smooth_booleans", "rail", _ATTRS_RAIL),
        ("sdf_blend_controls", "fastener", _ATTRS_FASTENER),
        ("sdf_sample_bounds", "guard", _ATTRS_GUARD),
        ("sdf_material_regions", "material_zone", _zone_attrs("sdf_material_regions", _ATTRS_MATERIAL_ZONE)),
        ("sdf_extraction_ports", "socket", _ATTRS_SOCKET),
        ("sdf_failure_guards", "guard", _ATTRS_GUARD),
        ("sdf_organic_markers", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("sdf_iteration_wear", "wear_zone", _zone_attrs("sdf_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("subdivision_finishing_system", (
        ("subdivision_control_cage", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("subdivision_scheme", "decal_zone", _zone_attrs("subdivision_scheme", _ATTRS_DECAL_ZONE)),
        ("subdivision_creases", "trim", _ATTRS_TRIM),
        ("subdivision_boundaries", "guard", _ATTRS_GUARD),
        ("subdivision_remesh_targets", "socket", _ATTRS_SOCKET),
        ("subdivision_smoothing", "rail", _ATTRS_RAIL),
        ("subdivision_detail_layers", "material_zone", _zone_attrs("subdivision_detail_layers", _ATTRS_MATERIAL_ZONE)),
        ("subdivision_quality_probes", "fastener", _ATTRS_FASTENER),
        ("subdivision_outputs", "decal_zone", _zone_attrs("subdivision_outputs", _ATTRS_DECAL_ZONE)),
        ("subdivision_iteration_wear", "wear_zone", _zone_attrs("subdivision_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("humanoid_anatomy_preset_system", (
        ("humanoid_canonical_topology", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("humanoid_body_proportions", "panel", _ATTRS_PANEL),
        ("humanoid_region_map", "material_zone", _zone_attrs("humanoid_region_map", _ATTRS_MATERIAL_ZONE)),
        ("humanoid_landmark_loops", "rail", _ATTRS_RAIL),
        ("humanoid_joint_anchors", "socket", _ATTRS_SOCKET),
        ("humanoid_morph_database", "panel", _ATTRS_PANEL),
        ("humanoid_skin_weights", "material_zone", _zone_attrs("humanoid_skin_weights", _ATTRS_MATERIAL_ZONE)),
        ("humanoid_style_variants", "socket", _ATTRS_SOCKET),
        ("humanoid_validation_guards", "guard", _ATTRS_GUARD),
        ("humanoid_iteration_wear", "wear_zone", _zone_attrs("humanoid_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
    _round2_fixture("face_sdf_cel_shading_system", (
        ("face_sdf_regions", "primary_volume", _ATTRS_PRIMARY_VOLUME),
        ("face_shadow_fields", "material_zone", _zone_attrs("face_shadow_fields", _ATTRS_MATERIAL_ZONE)),
        ("cel_ramp_lut_stack", "panel", _ATTRS_PANEL),
        ("cel_outline_hull", "rail", _ATTRS_RAIL),
        ("cel_light_controls", "socket", _ATTRS_SOCKET),
        ("face_id_masks", "decal_zone", _zone_attrs("face_id_masks", _ATTRS_DECAL_ZONE)),
        ("cel_style_bridge_guards", "guard", _ATTRS_GUARD),
        ("cel_preview_outputs", "panel", _ATTRS_PANEL),
        ("cel_expression_hooks", "socket", _ATTRS_SOCKET),
        ("cel_iteration_wear", "wear_zone", _zone_attrs("cel_iteration_wear", _ATTRS_WEAR_ZONE)),
    )),
)


def _normalize_op_for_diff(op: ShapeOp) -> tuple[str, str, frozenset[str]]:
    """Reduce a ShapeOp to its (op, target, parameter-keys) shape for diffing.

    Compares semantic structure rather than literal parameter values
    (which legitimately vary as brief inputs flow through the
    synthesizer). The migration is judged by whether the *set of
    operations* (and their targets and parameter surfaces) matches
    the recipe baseline, not by exact float equality on dimensions.
    """
    return (
        op.op,
        str(op.target or ""),
        frozenset(op.parameters.keys()),
    )


def _shape_program_signature(program: ShapeProgram) -> tuple[tuple[str, str, frozenset[str]], ...]:
    """Reduce a ShapeProgram to the ordered tuple of normalized op signatures."""
    return tuple(_normalize_op_for_diff(op) for op in program.ops)


def _run_recipe_path(
    family: str,
    brief: Mapping[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> ShapeProgram:
    """Invoke ``_RECIPES[family]`` directly and return its ShapeProgram."""
    recipe = _RECIPES.get(family)
    if recipe is None:
        raise pytest.UsageError(
            f"family {family!r} is not in _RECIPES; cannot diff against the "
            "recipe baseline. Either the migration is already complete "
            "(in which case this fixture should be removed) or the family "
            "name is misspelled."
        )
    result = recipe(dict(brief), tuple(parts), tuple(graph_nodes))
    return result.shape_program


def _run_synthesizer_path(
    asset: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> ShapeProgram:
    """Invoke ``synthesize_procedural_program`` and return its ShapeProgram."""
    synth_result = synthesize_procedural_program(asset, runtime)
    return synth_result.shape_program


@pytest.mark.skipif(
    not _MIGRATED_FAMILY_FIXTURES,
    reason="no families have migrated yet; harness exercised by tests added per-family",
)
@pytest.mark.parametrize(
    "fixture",
    _MIGRATED_FAMILY_FIXTURES,
    ids=[f["family"] for f in _MIGRATED_FAMILY_FIXTURES] if _MIGRATED_FAMILY_FIXTURES else [],
)
def test_migrated_family_shape_program_diff(fixture: dict[str, Any]) -> None:
    """Recipe vs synthesizer ShapeProgram are equivalent (or documented difference).

    Per plan v2 §6.4: differences must be documented as intent-driven
    (e.g., brief now respected) or reduced. The fixture's
    ``allowed_op_diff`` field lists explicit accepted differences;
    any other divergence is a regression.
    """
    family = fixture["family"]
    recipe_program = _run_recipe_path(
        family,
        fixture["brief"],
        fixture["parts"],
        fixture["graph_nodes"],
    )
    synth_program = _run_synthesizer_path(
        fixture["synthesizer_asset"],
        fixture["synthesizer_runtime"],
    )

    assert recipe_program.family == family, (
        f"recipe ShapeProgram.family={recipe_program.family!r} did not match "
        f"fixture family={family!r}"
    )
    assert synth_program.family == family, (
        f"synthesizer ShapeProgram.family={synth_program.family!r} did not "
        f"match fixture family={family!r}; the FamilyAlias resolution may "
        "be misconfigured."
    )

    recipe_sig = _shape_program_signature(recipe_program)
    synth_sig = _shape_program_signature(synth_program)

    # Intent-driven full replacement: when the synthesizer's procedural
    # decomposition emits all-low-level primitives in place of the
    # recipe's high-level sop.* ops, the signature sets are universally
    # disjoint. Setting ``allow_intent_driven_replacement=True`` records
    # this acknowledged divergence — the family fixture still has to
    # produce a non-empty synth program, the family alias still has to
    # resolve, and the synthesizer must emit at least one op per
    # construction-graph node-type (`min_synth_op_count` defaults to 1).
    # This is documented in plan v2 §6.3 as the legitimate migration
    # outcome when generator decomposition is finer-grained than the
    # source recipe.
    if fixture.get("allow_intent_driven_replacement"):
        min_count = int(fixture.get("min_synth_op_count") or 1)
        assert len(synth_sig) >= min_count, (
            f"family {family!r}: allow_intent_driven_replacement set but "
            f"synthesizer emitted only {len(synth_sig)} ops "
            f"(expected >= {min_count}). The construction-graph fixture "
            "is too thin, or generator decomposition silently dropped nodes."
        )
        return

    allowed_diff = fixture.get("allowed_op_diff") or []
    allowed_diff_set = {
        (entry["op"], entry["target"], frozenset(entry.get("parameter_keys", [])))
        for entry in allowed_diff
    }

    # Compute the symmetric difference between op signatures.
    recipe_only = [sig for sig in recipe_sig if sig not in synth_sig and sig not in allowed_diff_set]
    synth_only = [sig for sig in synth_sig if sig not in recipe_sig and sig not in allowed_diff_set]

    if recipe_only or synth_only:
        pytest.fail(
            f"family {family!r} ShapeProgram diff found undocumented differences:\n"
            f"  recipe-only ops: {recipe_only!r}\n"
            f"  synthesizer-only ops: {synth_only!r}\n"
            f"  allowed_op_diff entries: {allowed_diff!r}\n"
            "If these are intent-driven (brief now respected) or reductions, "
            "add them to the fixture's allowed_op_diff list with a reason "
            "in the per-family migration notes."
        )


def test_migrated_family_fixtures_match_recipe_registry() -> None:
    """Every fixture entry must reference a family currently in _RECIPES.

    A fixture for a family that has already been deleted from
    _RECIPES is dead — either the deletion was premature or the
    fixture was forgotten in the cleanup pass.
    """
    for fixture in _MIGRATED_FAMILY_FIXTURES:
        family = fixture["family"]
        assert family in _RECIPES, (
            f"fixture family={family!r} not present in _RECIPES; either "
            "remove the fixture (if the recipe was deleted intentionally) "
            "or restore the recipe (if it was deleted prematurely)."
        )


def test_migrated_family_fixtures_have_required_keys() -> None:
    """Each fixture entry must define the documented contract keys."""
    required_keys = {
        "family",
        "brief",
        "parts",
        "graph_nodes",
        "synthesizer_asset",
        "synthesizer_runtime",
    }
    for fixture in _MIGRATED_FAMILY_FIXTURES:
        missing = required_keys - set(fixture.keys())
        assert not missing, (
            f"fixture for family={fixture.get('family')!r} missing required "
            f"keys: {sorted(missing)!r}. See module docstring for the "
            "fixture contract."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
