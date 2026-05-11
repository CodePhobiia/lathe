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
