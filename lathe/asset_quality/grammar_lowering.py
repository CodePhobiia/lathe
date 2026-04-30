"""Phase 6 deterministic grammar-lowering recipes.

Lowers a family grammar's construction requirements into ShapeIR v2
operations + synthesized semantic-construction-graph nodes. The
industrial_crate recipe is the first concrete consumer of Phases 3
(family grammar), 4 (construction graph), and 5 (ShapeIR v2 + v1
adapter).

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 7.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 6.
Per-requirement reference: ``docs/asset-quality/grammar-lowering-v1.md``.

Design summary
--------------

Phase 6 is **internal IR + recipe + adapter wiring** plus live
family-grammar evidence. It does not
touch ``.lth`` syntax, ``lathe.shape.intent_mesh_handoff_v1``, the
public schema, or the v1 shape bundle. The recipe is a pure function
that takes a design brief, a parts list, and the current
construction-graph nodes and returns a frozen :class:`RecipeResult`
with a :class:`ShapeProgram` and a tuple of synthesized graph nodes.

The recipe's synthesized graph nodes live under
``runtime["grammar_lowering"]["synthesized_graph_nodes"]``. The live
validator pipeline runs grammar lowering before family grammar, and
``family_grammar`` merges those synthesized nodes into its read-only
evidence view so coverage reflects the recipe without mutating
``runtime["construction_graph"]["nodes"]``.

The validator never produces blocking diagnostics. v2-adapter
diagnostics for ops that have no v1 equivalent are surfaced under the
nested ``v1_lowering`` payload — they are evidence for forward phases
(Phase 7's high-poly producer turns those into v1-supported records),
not validator-pipeline blockers.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately before ``family_grammar`` and before
``quality_diagnostics``, both with ``stage_dependencies=[]`` and
``weight=0.0``. Topological order plus FIFO tie-break preserves the
registration-order placement.

Output additively appears under the top-level ``grammar_lowering`` key
of the validate-stage report (the 20th top-level key, on top of the 19
that Phases 0 through 5 publish).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .construction_graph import NODE_TYPES
from .shape_ir_v2 import (
    BOOLEAN_OPS,
    EDGE_OPS,
    INTEGRATION_OPS,
    REPETITION_OPS,
    SHAPE_IR_V2_VERSION,
    SOLID_OPS,
    WEAR_OPS,
    ShapeOp,
    ShapeProgram,
    lower_to_v1,
)


GRAMMAR_LOWERING_VERSION = "grammar_lowering_v1"


# Canonical industrial_crate body dimensions taken from the upgrade spec
# Section 7.3 (`primary_form = crate_squat_box(width: 92cm, height: 58cm,
# depth: 64cm)`).
_INDUSTRIAL_CRATE_BODY_WIDTH_CM: float = 92.0
_INDUSTRIAL_CRATE_BODY_HEIGHT_CM: float = 58.0
_INDUSTRIAL_CRATE_BODY_DEPTH_CM: float = 64.0


@dataclass(frozen=True)
class RecipeResult:
    """Result of lowering one family grammar into v2 ops + graph nodes.

    ``shape_program`` is the :class:`ShapeProgram` (Phase 5) the recipe
    emitted — its ops carry stable ``purpose`` strings keyed off the
    triggering grammar requirement. ``synthesized_graph_nodes`` is the
    tuple of graph-node dicts the family-grammar validator merges into
    its read-only evidence view.
    """

    family: str
    shape_program: ShapeProgram
    synthesized_graph_nodes: tuple[dict[str, Any], ...]


def _purpose(requirement: str, suffix: str) -> str:
    """Return the canonical ``purpose`` string for a recipe op.

    Format: ``<requirement>.<suffix>`` (e.g. ``"body_shell.primary_volume"``).
    The format is stable across phases so trace consumers can join op
    purpose to grammar requirement without re-keying.
    """
    return f"{requirement}.{suffix}"


def _node(node_id: str, node_type: str) -> dict[str, Any]:
    """Return one synthesized construction-graph node dict.

    The dict shape mirrors :func:`lathe.asset_quality.construction_graph.evaluate_construction_graph`
    so a downstream phase can merge synthesized nodes into the live
    graph without translation. ``attributes`` is empty at Phase 6;
    Phase 5+ ops carry their parameters on the matching ShapeOp instead.
    """
    return {
        "node_id": node_id,
        "node_type": node_type,
        "attributes": {},
    }


def _industrial_crate_body_shell() -> tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]:
    """Return the v2 ops + graph nodes for the ``body_shell`` requirement.

    Emits one ``solid.box`` op carrying the spec-canonical industrial
    crate dimensions (92cm x 58cm x 64cm) and one ``primary_volume``
    graph node.
    """
    ops = (
        ShapeOp(
            op="solid.box",
            target="body",
            parameters={
                "width_cm": _INDUSTRIAL_CRATE_BODY_WIDTH_CM,
                "height_cm": _INDUSTRIAL_CRATE_BODY_HEIGHT_CM,
                "depth_cm": _INDUSTRIAL_CRATE_BODY_DEPTH_CM,
            },
            purpose=_purpose("body_shell", "primary_volume"),
        ),
    )
    nodes = (_node("recipe.body_shell", "primary_volume"),)
    return ops, nodes


def _industrial_crate_lid_seam() -> tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]:
    """Return the v2 ops + graph nodes for the ``lid_seam`` requirement.

    Emits an ``op.inset`` carving a 0.4cm-deep band on the body's top
    band followed by an ``op.cut_panel_line`` to mark the visible lid
    break, plus one ``panel`` graph node tagged as the lid seam.
    """
    ops = (
        ShapeOp(
            op="op.inset",
            target="body.top_band",
            parameters={"depth_cm": 0.4},
            purpose=_purpose("lid_seam", "inset"),
        ),
        ShapeOp(
            op="op.cut_panel_line",
            target="body.top_band",
            parameters={"width_cm": 0.4},
            purpose=_purpose("lid_seam", "cut"),
        ),
    )
    nodes = (_node("recipe.lid_seam", "panel"),)
    return ops, nodes


def _industrial_crate_corner_guards() -> tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]:
    """Return the v2 ops + graph nodes for the ``corner_guards`` requirement.

    Emits one ``op.corner_guard_set`` carrying the eight-corner intent
    plus eight ``guard`` graph nodes (one per body corner) so the
    construction graph reflects the per-corner authoring intent the v1
    runtime cannot yet model.
    """
    ops = (
        ShapeOp(
            op="op.corner_guard_set",
            target="body.corners",
            parameters={"size_cm": 4.0, "guard_count": 8},
            purpose=_purpose("corner_guard_set", "eight_corners"),
        ),
    )
    nodes = tuple(_node(f"recipe.corner_guard_{index}", "guard") for index in range(8))
    return ops, nodes


def _industrial_crate_latch_or_latch_plate() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``latch_or_latch_plate`` requirement.

    Emits one ``op.mount_plate`` on the body's front face plus one
    ``inset`` graph node so downstream graph consumers see a recessed
    latch surface.
    """
    ops = (
        ShapeOp(
            op="op.mount_plate",
            target="body.front_face",
            parameters={"width_cm": 8.0, "height_cm": 6.0},
            purpose=_purpose("latch_plate", "mount_plate"),
        ),
    )
    nodes = (_node("recipe.latch_plate", "inset"),)
    return ops, nodes


def _industrial_crate_recessed_or_bracketed_handles() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``recessed_or_bracketed_handles`` requirement.

    Emits two ``op.socket`` ops (left + right) using the
    ``recessed_bracket`` mount type and two ``handle`` graph nodes
    matching the part-list naming convention (``handle_l`` /
    ``handle_r``).
    """
    ops = (
        ShapeOp(
            op="op.socket",
            target="body.left_face",
            parameters={"clearance_cm": 0.6, "mount_type": "recessed_bracket"},
            purpose=_purpose("handles", "socket_left"),
        ),
        ShapeOp(
            op="op.socket",
            target="body.right_face",
            parameters={"clearance_cm": 0.6, "mount_type": "recessed_bracket"},
            purpose=_purpose("handles", "socket_right"),
        ),
    )
    nodes = (
        _node("recipe.handle_l", "handle"),
        _node("recipe.handle_r", "handle"),
    )
    return ops, nodes


def _industrial_crate_foot_rails_or_feet() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``foot_rails_or_feet`` requirement.

    Emits two ``solid.rail`` ops spanning the bottom of the body plus
    two ``rail`` graph nodes (front + back).
    """
    ops = (
        ShapeOp(
            op="solid.rail",
            target="body.bottom_front",
            parameters={"length_cm": 60.0, "profile_cm": 4.0},
            purpose=_purpose("foot_rails", "front"),
        ),
        ShapeOp(
            op="solid.rail",
            target="body.bottom_back",
            parameters={"length_cm": 60.0, "profile_cm": 4.0},
            purpose=_purpose("foot_rails", "back"),
        ),
    )
    nodes = (
        _node("recipe.foot_rail_front", "rail"),
        _node("recipe.foot_rail_back", "rail"),
    )
    return ops, nodes


def _industrial_crate_trim_bands() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``trim_bands`` requirement.

    Emits one ``op.trim_band`` running across the body's mid-plane
    and one ``trim`` graph node.
    """
    ops = (
        ShapeOp(
            op="op.trim_band",
            target="body.mid_plane",
            parameters={"width_cm": 2.0},
            purpose=_purpose("trim_bands", "mid_plane"),
        ),
    )
    nodes = (_node("recipe.trim_band_mid", "trim"),)
    return ops, nodes


def _industrial_crate_fasteners() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``fasteners`` requirement.

    Emits one ``op.fastener_grid`` (2 rows x 2 columns, 8cm spacing)
    on the body's front face plus one ``fastener`` graph node.
    """
    ops = (
        ShapeOp(
            op="op.fastener_grid",
            target="body.front_face",
            parameters={"rows": 2, "columns": 2, "spacing_cm": 8.0},
            purpose=_purpose("fasteners", "front_grid"),
        ),
    )
    nodes = (_node("recipe.fastener_grid_front", "fastener"),)
    return ops, nodes


def _industrial_crate_warning_or_decal_zones() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``warning_or_decal_zones`` requirement.

    Emits one ``op.repeat`` (count=1, axis=z) reserving a single decal
    zone on the body and one ``decal_zone`` graph node. ShapeIR v2 has
    no first-class decal-zone op at Phase 5; ``op.repeat`` carries the
    intent (one repetition, oriented along z) and is paired with the
    graph node so Phase 8's material/wear graph can locate the zone
    without inventing a new op family. A future ShapeIR layer may add
    a dedicated ``op.decal_zone`` and replace this slot.
    """
    ops = (
        ShapeOp(
            op="op.repeat",
            target="body.front_face",
            parameters={"count": 1, "axis": "z"},
            purpose=_purpose("warning_decal_zone", "front_face"),
        ),
    )
    nodes = (_node("recipe.warning_decal_zone", "decal_zone"),)
    return ops, nodes


def _industrial_crate_edge_wear_masks() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``edge_wear_masks`` requirement.

    Emits one ``op.chip_edges`` carrying the spec's medium-edge-wear
    intent (amount=0.28) plus one ``wear_zone`` graph node so Phase 8's
    material/wear graph can drive the wear-mask authoring.
    """
    ops = (
        ShapeOp(
            op="op.chip_edges",
            target="body.outer_edges",
            parameters={"amount": 0.28},
            purpose=_purpose("edge_wear_masks", "chip_edges"),
        ),
    )
    nodes = (_node("recipe.edge_wear_zone", "wear_zone"),)
    return ops, nodes


# Per-requirement lowering functions in industrial_crate grammar's
# canonical declaration order. Each entry returns a (ops, nodes) tuple;
# the recipe stitches them together deterministically.
_INDUSTRIAL_CRATE_LOWERERS: tuple[
    tuple[
        str,
        Any,
    ],
    ...,
] = (
    ("body_shell", _industrial_crate_body_shell),
    ("lid_seam", _industrial_crate_lid_seam),
    ("corner_guards", _industrial_crate_corner_guards),
    ("latch_or_latch_plate", _industrial_crate_latch_or_latch_plate),
    ("recessed_or_bracketed_handles", _industrial_crate_recessed_or_bracketed_handles),
    ("foot_rails_or_feet", _industrial_crate_foot_rails_or_feet),
    ("trim_bands", _industrial_crate_trim_bands),
    ("fasteners", _industrial_crate_fasteners),
    ("warning_or_decal_zones", _industrial_crate_warning_or_decal_zones),
    ("edge_wear_masks", _industrial_crate_edge_wear_masks),
)


def industrial_crate_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    """Lower the industrial_crate family grammar into v2 ops + graph nodes.

    Args:
        brief: design-brief dict (Phase 2). Reserved for future recipes
            that select between sub-variants (squat / tall / wide); the
            Phase 6 industrial-crate recipe ignores its contents but the
            parameter is carried so the signature is stable across
            future variant work.
        parts: parts list from ``asset["intent"]["parts"]``. Reserved
            for future recipes that emit additional ops only when a
            specific part exists (e.g. an ``op.weld_seam`` only when a
            weld_seam part is declared); the Phase 6 industrial-crate
            recipe emits the full 10-requirement program unconditionally
            so the synthesized ShapeProgram is a deterministic function
            of the family alone.
        graph_nodes: current ``runtime["construction_graph"]["nodes"]``
            tuple. Reserved for future recipes that consume existing
            graph evidence to vary the program; the Phase 6
            industrial-crate recipe ignores it but the parameter is
            carried so a later phase can opt in without changing the
            signature.

    Returns:
        A frozen :class:`RecipeResult` carrying the
        :class:`ShapeProgram` and a tuple of synthesized graph-node
        dicts. Determinism: identical inputs always yield identical
        outputs, including op order, parameter dicts, and node ids.
    """
    del brief, parts, graph_nodes
    ops: list[ShapeOp] = []
    nodes: list[dict[str, Any]] = []
    for _requirement_name, lowerer in _INDUSTRIAL_CRATE_LOWERERS:
        requirement_ops, requirement_nodes = lowerer()
        ops.extend(requirement_ops)
        nodes.extend(requirement_nodes)
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="industrial_crate",
        family="industrial_crate",
        ops=tuple(ops),
    )
    return RecipeResult(
        family="industrial_crate",
        shape_program=program,
        synthesized_graph_nodes=tuple(nodes),
    )


def _empty_recipe(family: str, asset_name: str) -> RecipeResult:
    """Return a :class:`RecipeResult` with an empty program for ``family``.

    Used when the family is unknown or not yet covered by a Phase 6
    recipe (every family other than ``industrial_crate``). The Phase 5
    v1 adapter handles an empty program cleanly: no v1 records, no
    diagnostics.
    """
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name=asset_name,
        family=family,
        ops=(),
    )
    return RecipeResult(
        family=family,
        shape_program=program,
        synthesized_graph_nodes=(),
    )


_RECIPES: dict[str, Any] = {
    "industrial_crate": industrial_crate_recipe,
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _resolve_brief(runtime: dict[str, Any]) -> dict[str, Any]:
    """Return the design-brief dict published by Phase 2, or empty."""
    design_brief = _as_dict(runtime.get("design_brief"))
    return _as_dict(design_brief.get("brief"))


def _resolve_family(brief: dict[str, Any]) -> str:
    """Return the family token from the (already-resolved) design brief,
    or ``"generic"``."""
    family = brief.get("family")
    if isinstance(family, str) and family:
        return family
    return "generic"


def _resolve_parts(asset: dict[str, Any]) -> tuple[str, ...]:
    """Return the parts list from ``asset["intent"]["parts"]`` as a tuple."""
    intent = _as_dict(asset.get("intent"))
    raw_parts = _as_list(intent.get("parts"))
    return tuple(part for part in raw_parts if isinstance(part, str))


def _resolve_graph_nodes(runtime: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return ``runtime["construction_graph"]["nodes"]`` as a tuple of dicts."""
    construction_graph = _as_dict(runtime.get("construction_graph"))
    raw_nodes = construction_graph.get("nodes")
    if not isinstance(raw_nodes, list):
        return ()
    return tuple(node for node in raw_nodes if isinstance(node, dict))


def _resolve_asset_name(asset: dict[str, Any], brief: dict[str, Any]) -> str:
    """Return the asset name, falling back through the (already-resolved)
    design brief."""
    name = asset.get("name")
    if isinstance(name, str) and name:
        return name
    brief_name = brief.get("asset_name")
    if isinstance(brief_name, str) and brief_name:
        return brief_name
    return "unnamed_asset"


_OP_FAMILY_BUCKETS: tuple[tuple[frozenset[str], str], ...] = (
    (SOLID_OPS, "solid_ops"),
    (BOOLEAN_OPS, "boolean_ops"),
    (EDGE_OPS, "edge_ops"),
    (REPETITION_OPS, "repetition_ops"),
    (INTEGRATION_OPS, "integration_ops"),
    (WEAR_OPS, "wear_ops"),
)


_OP_TO_FAMILY_BUCKET: dict[str, str] = {
    op_name: bucket for family, bucket in _OP_FAMILY_BUCKETS for op_name in family
}


def _summarise_program(program: ShapeProgram) -> dict[str, Any]:
    """Return ``shape_program_summary`` for the validator payload.

    Counts ops by Phase 5 family (single dict lookup per op) and by
    triggering grammar requirement (extracted from the leading
    ``<requirement>.`` token of each op's ``purpose`` string).
    """
    family_counts: dict[str, int] = {bucket: 0 for _, bucket in _OP_FAMILY_BUCKETS}
    requirement_counts: dict[str, int] = {}
    for op in program.ops:
        bucket = _OP_TO_FAMILY_BUCKET.get(op.op)
        if bucket is not None:
            family_counts[bucket] += 1
        if op.purpose and "." in op.purpose:
            requirement_token = op.purpose.split(".", 1)[0]
            requirement_counts[requirement_token] = (
                requirement_counts.get(requirement_token, 0) + 1
            )
    return {
        "op_count": len(program.ops),
        "ops_by_family": family_counts,
        "ops_by_requirement": dict(sorted(requirement_counts.items())),
    }


def _select_recipe_result(
    family: str,
    asset_name: str,
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    """Run the matching recipe, falling back to an empty program."""
    recipe = _RECIPES.get(family)
    if recipe is None:
        return _empty_recipe(family=family, asset_name=asset_name)
    result = recipe(brief=brief, parts=parts, graph_nodes=graph_nodes)
    if result.shape_program.asset_name == asset_name:
        return result
    rebuilt_program = ShapeProgram(
        version=result.shape_program.version,
        asset_name=asset_name,
        family=result.shape_program.family,
        ops=result.shape_program.ops,
    )
    return RecipeResult(
        family=result.family,
        shape_program=rebuilt_program,
        synthesized_graph_nodes=result.synthesized_graph_nodes,
    )


def evaluate_grammar_lowering(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive grammar-lowering payload for the validate stage.

    Args:
        asset: normalized asset dict. May omit ``intent`` or ``parts``;
            the function tolerates partial/empty input.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["design_brief"]["brief"]["family"]`` (Phase 2),
            ``runtime["construction_graph"]["nodes"]`` (Phase 4), and the
            asset's parts list. The recipe is currently a function of
            family alone; the parts and graph parameters are reserved
            for future variant recipes.

    Returns:
        Additive payload with ``version`` (``"grammar_lowering_v1"``),
        ``family``, ``shape_program`` (Phase 5 ShapeProgram dict),
        ``shape_program_summary`` (op_count + ops_by_family +
        ops_by_requirement), ``synthesized_graph_nodes`` (list of
        node-dicts compatible with Phase 4's construction graph),
        ``synthesized_node_count``, and ``v1_lowering`` (nested
        v2-to-v1 adapter result with ``v1_record_count``,
        ``diagnostics``, ``unsupported_ops``). No top-level
        ``diagnostics`` key — like Phases 1 through 5, this validator
        is informational only and never blocks certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    brief = _resolve_brief(safe_runtime)
    parts = _resolve_parts(safe_asset)
    graph_nodes = _resolve_graph_nodes(safe_runtime)
    family = _resolve_family(brief)
    asset_name = _resolve_asset_name(safe_asset, brief)
    result = _select_recipe_result(
        family=family,
        asset_name=asset_name,
        brief=brief,
        parts=parts,
        graph_nodes=graph_nodes,
    )
    program = result.shape_program
    adapter = lower_to_v1(program)
    return {
        "version": GRAMMAR_LOWERING_VERSION,
        "family": result.family,
        "shape_program": program.to_dict(),
        "shape_program_summary": _summarise_program(program),
        "synthesized_graph_nodes": [dict(node) for node in result.synthesized_graph_nodes],
        "synthesized_node_count": len(result.synthesized_graph_nodes),
        "v1_lowering": {
            "v1_record_count": len(adapter.v1_records),
            "diagnostics": [dict(item) for item in adapter.diagnostics],
            "unsupported_ops": list(adapter.unsupported_ops),
        },
    }


# Anchors the synthesized-node-types contract: every recipe node must use
# a ``node_type`` from Phase 4's NODE_TYPES frozenset so a future opt-in
# merger can drop the synthesized nodes into the live construction graph
# without translation.
_SYNTHESIZED_NODE_TYPES_USED: frozenset[str] = frozenset(
    {
        "primary_volume",
        "panel",
        "guard",
        "inset",
        "handle",
        "rail",
        "trim",
        "fastener",
        "decal_zone",
        "wear_zone",
    }
)


def _verify_node_type_contract() -> None:
    """Assert at import time that recipe node types are members of NODE_TYPES."""
    unknown = _SYNTHESIZED_NODE_TYPES_USED - NODE_TYPES
    if unknown:
        raise AssertionError(
            f"grammar_lowering recipe uses node types not in construction_graph.NODE_TYPES: "
            f"{sorted(unknown)}"
        )


_verify_node_type_contract()
