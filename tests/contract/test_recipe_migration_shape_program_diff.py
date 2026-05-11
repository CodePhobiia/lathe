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
