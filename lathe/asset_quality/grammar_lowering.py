"""Grammar-lowering validator — synthesizer-driven (Cycle 3 post-decommission).

Validate-stage informational reporter. Lowers an asset's declared
construction-graph + family alias into a ShapeIR v2 ShapeProgram via
the procedural synthesizer, then reports the result + a v1 adapter
trace as additive validator evidence.

This file is the procedural successor to the original 71-entry
``_RECIPES`` registry. Per ``docs/asset-quality/lathe-northstar-full-implementation-plan.md``
v2 §6.3 Round 6, every family that existed in the registry has been
migrated to a declarative ``FamilyAlias`` + ``CompositionPolicy`` +
``StyleKnowledge`` triple under ``std/procedural/knowledge/``. Lowering
now flows through ``synthesize_procedural_program(asset, runtime)``
regardless of family — there is no family-keyed dispatch in this
module.

Public surface:
  - ``evaluate_grammar_lowering(asset, runtime) -> dict`` — the
    validate-stage entry point. Always informational; never blocks.
  - ``GRAMMAR_LOWERING_VERSION`` — payload version tag.
  - ``RecipeResult`` — frozen dataclass returned by the internal
    lowering helper. Carried for downstream consumers that previously
    pulled it from the recipe path.

The module additively contributes ``grammar_lowering`` to the
validate-stage report. ``v1_lowering`` carries the v2→v1 adapter trace
(records, diagnostics, unsupported ops); ``shape_program`` carries the
synthesizer's emitted program; ``synthesized_graph_nodes`` reports any
nodes the synthesizer's composition policies added on top of the
authored construction graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .construction_graph import NODE_TYPES, _classify_part
from .procedural_synthesizer import synthesize_procedural_program
from .shape_ir_v2 import (
    BOOLEAN_OPS,
    EDGE_OPS,
    INTEGRATION_OPS,
    REPETITION_OPS,
    SHAPE_IR_V2_VERSION,
    SOP_OPS,
    SOLID_OPS,
    WEAR_OPS,
    ShapeOp,
    ShapeProgram,
    lower_to_v1,
)


GRAMMAR_LOWERING_VERSION = "grammar_lowering_v1"


@dataclass(frozen=True)
class RecipeResult:
    """Frozen lowering result.

    Carried for compatibility with the previous recipe-driven shape;
    the synthesizer's :class:`SynthesisResult` is unwrapped into this
    dataclass so downstream consumers (validators, trace assemblers)
    don't need to change.
    """

    family: str
    shape_program: ShapeProgram
    synthesized_graph_nodes: tuple[dict[str, Any], ...]


# --------------------------------------------------------------------
# Lightweight dict / value helpers
# --------------------------------------------------------------------


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _value_at_path(source: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _iter_text_fragments(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        fragment = value.strip()
        return (fragment,) if fragment else ()
    if isinstance(value, list):
        fragments: list[str] = []
        for entry in value:
            fragments.extend(_iter_text_fragments(entry))
        return tuple(fragments)
    if isinstance(value, dict):
        fragments = []
        for key in sorted(value.keys(), key=str):
            key_fragment = str(key).strip()
            if key_fragment:
                fragments.append(key_fragment)
            fragments.extend(_iter_text_fragments(value[key]))
        return tuple(fragments)
    return ()


def _slug_fragment(value: str) -> str:
    lowered = value.lower()
    chars: list[str] = []
    previous_was_separator = False
    for char in lowered:
        if char.isalnum():
            chars.append(char)
            previous_was_separator = False
            continue
        if not previous_was_separator:
            chars.append("_")
            previous_was_separator = True
    slug = "".join(chars).strip("_")
    return slug[:48] if slug else "value"


# --------------------------------------------------------------------
# Authored-graph + repair-policy synthesized nodes
# --------------------------------------------------------------------


_AUTHORED_SOURCE_NODE_FIELDS: tuple[tuple[tuple[str, ...], str | None], ...] = (
    (("intent", "parts"), None),
    (("intent", "materials"), "material_zone"),
    (("intent", "interactions"), "socket"),
    (("features", "allow"), None),
    (("assembly", "components"), None),
    (("assembly", "mechanisms"), "socket"),
    (("assembly", "traits"), None),
    (("surface", "materials"), "material_zone"),
    (("surface", "patterns"), "decal_zone"),
)

_MAX_AUTHORED_SOURCE_NODES = 32

_REPAIR_POLICY_HARDSURFACE_DEFAULT_FEATURES = (
    "edge_break",
    "trim_band",
    "fastener_grid",
    "panel_frame",
    "support_bracket",
)

_REPAIR_POLICY_ACTION_FEATURES: dict[str, tuple[str, ...]] = {
    "add_secondary_features": ("trim_band", "fastener_grid"),
    "restore_edge_treatment": ("edge_break",),
    "increase_panel_depth": ("panel_frame", "trim_band", "inset_panel"),
    "improve_attachment_integration": ("socket_point", "support_bracket", "mount_plate"),
    "refine_support_layout": ("support_bracket", "mount_plate"),
    "restore_hinge_alignment": ("hinge", "support_bracket"),
    "shroud_exposed_frame": ("tube_shroud",),
}

_REPAIR_POLICY_FEATURE_NODE_TYPES: dict[str, tuple[str, ...]] = {
    "edge_break": ("trim",),
    "trim_band": ("trim",),
    "fastener_grid": ("fastener",),
    "panel_frame": ("panel",),
    "inset_panel": ("inset",),
    "support_bracket": ("bracket",),
    "socket_point": ("socket",),
    "mount_plate": ("mount",),
    "hinge": ("hinge",),
    "tube_shroud": ("conduit",),
}


def _node(
    node_id: str,
    node_type: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one synthesized construction-graph node dict.

    The dict shape mirrors ``construction_graph.evaluate_construction_graph``
    so downstream phases can merge synthesized nodes into the live
    graph without translation.
    """
    return {
        "node_id": node_id,
        "node_type": node_type,
        "attributes": dict(attributes) if attributes else {},
    }


def _source_node_type(fragment: str, fallback_node_type: str | None) -> str:
    if fallback_node_type is not None:
        return fallback_node_type
    return _classify_part(fragment)


def _source_authored_graph_nodes(asset: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return semantic graph nodes implied by already-public authoring fields.

    These nodes are additive evidence only. They let ordinary source
    authoring fields influence family grammar coverage without adding
    grammar/schema surface or mutating the live construction graph.
    """
    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path, fallback_node_type in _AUTHORED_SOURCE_NODE_FIELDS:
        raw_value = _value_at_path(asset, path)
        source_path = ".".join(path)
        for fragment in _iter_text_fragments(raw_value):
            if len(nodes) >= _MAX_AUTHORED_SOURCE_NODES:
                return tuple(nodes)
            slug = _slug_fragment(fragment)
            node_id = f"source.{source_path}.{slug}"
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            node_type = _source_node_type(fragment, fallback_node_type)
            nodes.append(
                _node(
                    node_id,
                    node_type,
                    {
                        "source": "authored_source_field",
                        "source_path": source_path,
                        "source_value": fragment,
                    },
                )
            )
    return tuple(nodes)


def _repair_policy_slugs(value: Any) -> frozenset[str]:
    return frozenset(_slug_fragment(fragment) for fragment in _iter_text_fragments(value))


def _repair_policy_feature_kinds(asset: dict[str, Any]) -> tuple[str, ...]:
    policy = _as_dict(asset.get("repair_policy"))
    if not policy:
        return ()
    request_slugs = set(_repair_policy_slugs(policy.get("use")))
    request_slugs.update(_repair_policy_slugs(policy.get("mode")))
    request_slugs.update(_repair_policy_slugs(policy.get("allow")))
    deny_slugs = _repair_policy_slugs(policy.get("deny"))
    selected: list[str] = []
    seen: set[str] = set()

    def denies(kind: str, action: str = "") -> bool:
        kind_slug = _slug_fragment(kind)
        action_slug = _slug_fragment(action) if action else ""
        if kind_slug in deny_slugs or (action_slug and action_slug in deny_slugs):
            return True
        deny_tokens = {token for slug in deny_slugs for token in slug.split("_") if token}
        kind_tokens = {token for token in kind_slug.split("_") if token}
        action_tokens = {token for token in action_slug.split("_") if token}
        return bool((kind_tokens and kind_tokens & deny_tokens) or (action_tokens and action_tokens & deny_tokens))

    def add_kind(kind: str, action: str = "") -> None:
        kind_slug = _slug_fragment(kind)
        if kind_slug not in _REPAIR_POLICY_FEATURE_NODE_TYPES or kind_slug in seen:
            return
        if denies(kind_slug, action):
            return
        seen.add(kind_slug)
        selected.append(kind_slug)

    if request_slugs & {
        "hero_hardsurface_repair",
        "hero_hard_surface_repair",
        "hardsurface_repair",
        "hard_surface_repair",
    }:
        for kind in _REPAIR_POLICY_HARDSURFACE_DEFAULT_FEATURES:
            add_kind(kind, "hero_hardsurface_repair")

    for action_slug in sorted(request_slugs):
        for kind in _REPAIR_POLICY_ACTION_FEATURES.get(action_slug, ()):
            add_kind(kind, action_slug)
        if action_slug in _REPAIR_POLICY_FEATURE_NODE_TYPES:
            add_kind(action_slug, action_slug)
    return tuple(selected)


def _source_repair_policy_graph_nodes(asset: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for kind in _repair_policy_feature_kinds(asset):
        for node_type in _REPAIR_POLICY_FEATURE_NODE_TYPES.get(kind, ()):
            if len(nodes) >= _MAX_AUTHORED_SOURCE_NODES:
                return tuple(nodes)
            node_id = f"source.repair_policy.{kind}.{node_type}"
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            nodes.append(
                _node(
                    node_id,
                    node_type,
                    {
                        "source": "repair_policy",
                        "source_path": "repair_policy",
                        "repair_policy_feature": kind,
                    },
                )
            )
    return tuple(nodes)


# --------------------------------------------------------------------
# Brief / asset resolution
# --------------------------------------------------------------------


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


def _resolve_graph_edges(runtime: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return ``runtime["construction_graph"]["edges"]`` as a tuple of dicts."""
    construction_graph = _as_dict(runtime.get("construction_graph"))
    raw_edges = construction_graph.get("edges")
    if not isinstance(raw_edges, list):
        return ()
    return tuple(edge for edge in raw_edges if isinstance(edge, dict))


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


# --------------------------------------------------------------------
# Synthesizer dispatch (replaces _RECIPES.get(family))
# --------------------------------------------------------------------


def _empty_recipe(family: str, asset_name: str) -> RecipeResult:
    """Return a :class:`RecipeResult` with an empty program.

    Used when the synthesizer cannot produce ops (no construction
    graph, no resolvable alias). The v1 adapter handles an empty
    program cleanly: no v1 records, no diagnostics.
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


def _select_recipe_result(
    family: str,
    asset_name: str,
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
    graph_edges: tuple[dict[str, Any], ...] = (),
) -> RecipeResult:
    """Run the synthesizer pipeline and return a :class:`RecipeResult`.

    The synthesizer dispatches by domain + NODE_TYPE + alias-resolved
    style + policy — no family-keyed branching. When no construction
    graph or alias is resolvable, an empty :class:`RecipeResult` is
    returned (the v1 adapter handles this cleanly).
    """
    synthesizer_asset = {
        "name": asset_name,
        "intent": {
            "parts": list(parts),
            "construction_graph": {
                "nodes": list(graph_nodes),
                "edges": list(graph_edges),
            },
        },
    }
    synthesizer_runtime = {
        "design_brief": {"brief": {**brief, "family": family}},
        "construction_graph": {
            "nodes": list(graph_nodes),
            "edges": list(graph_edges),
        },
    }
    synth_result = synthesize_procedural_program(synthesizer_asset, synthesizer_runtime)
    program = synth_result.shape_program
    if program.asset_name != asset_name:
        program = ShapeProgram(
            version=program.version,
            asset_name=asset_name,
            family=program.family,
            ops=program.ops,
        )
    synthesized_nodes = tuple(
        dict(node) for node in synth_result.synthesized_graph_nodes
    )
    return RecipeResult(
        family=family,
        shape_program=program,
        synthesized_graph_nodes=synthesized_nodes,
    )


def _merge_synthesized_nodes(
    *node_groups: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for nodes in node_groups:
        for node in nodes:
            node_id = node.get("node_id") if isinstance(node, dict) else None
            if isinstance(node_id, str) and node_id:
                if node_id in seen_ids:
                    continue
                seen_ids.add(node_id)
            merged.append(node)
    return tuple(merged)


# --------------------------------------------------------------------
# ShapeProgram summarization
# --------------------------------------------------------------------


_OP_FAMILY_BUCKETS: tuple[tuple[frozenset[str], str], ...] = (
    (SOLID_OPS, "solid_ops"),
    (BOOLEAN_OPS, "boolean_ops"),
    (EDGE_OPS, "edge_ops"),
    (SOP_OPS, "sop_ops"),
    (REPETITION_OPS, "repetition_ops"),
    (INTEGRATION_OPS, "integration_ops"),
    (WEAR_OPS, "wear_ops"),
)


_OP_TO_FAMILY_BUCKET: dict[str, str] = {
    op_name: bucket for family, bucket in _OP_FAMILY_BUCKETS for op_name in family
}


def _summarise_program(program: ShapeProgram) -> dict[str, Any]:
    """Return ``shape_program_summary`` for the validator payload."""
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


# --------------------------------------------------------------------
# v1 adapter integration
# --------------------------------------------------------------------


def _runtime_config_for_geometry_kernel(runtime: dict[str, Any]) -> dict[str, Any] | None:
    runtime_config = _as_dict(runtime.get("_runtime_config"))
    if runtime_config:
        return runtime_config
    if isinstance(runtime.get("runtime"), dict):
        return runtime
    return None


def _resolve_v1_lowering_geometry_kernel(runtime: dict[str, Any]) -> tuple[Any | None, dict[str, Any]]:
    runtime_config = _runtime_config_for_geometry_kernel(runtime)
    if runtime_config is None:
        return None, {
            "geometry_kernel_selection": "not_configured",
            "geometry_kernel": None,
        }
    # The live validate stage is informational for grammar lowering.
    # Replaying the geometry kernel here duplicates the shape-stage
    # kernel work and can dominate end-to-end builds for dense assets.
    # Keep lowering semantic and report the skipped replay honestly;
    # direct lower_to_v1(...) callers can still pass a geometry kernel
    # when materialized adapter output is desired.
    return None, {
        "geometry_kernel_selection": "skipped_validator_kernel_replay",
        "geometry_kernel": None,
        "geometry_kernel_materialization_skipped": True,
    }


def _record_has_kernel_program(record: dict[str, Any]) -> bool:
    tags = record.get("tags")
    if isinstance(tags, list) and any("kernel_program" in str(tag) for tag in tags):
        return True
    if isinstance(record.get("kernel_program"), dict):
        return True
    for value in record.values():
        if isinstance(value, dict) and isinstance(value.get("kernel_program"), dict):
            return True
    return False


def _kernel_program_record_metrics(records: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    kernel_records = tuple(record for record in records if _record_has_kernel_program(record))
    face_count = 0
    for record in kernel_records:
        faces = record.get("mesh_faces")
        if isinstance(faces, list):
            face_count += len(faces)
    return {
        "kernel_program_record_count": len(kernel_records),
        "kernel_program_face_count": face_count,
    }


# --------------------------------------------------------------------
# Validate-stage entry point
# --------------------------------------------------------------------


def evaluate_grammar_lowering(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive grammar-lowering payload for the validate stage.

    Args:
        asset: normalized asset dict. May omit ``intent`` or ``parts``;
            the function tolerates partial/empty input.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["design_brief"]["brief"]["family"]``,
            ``runtime["construction_graph"]["nodes"]`` /
            ``runtime["construction_graph"]["edges"]``, and the asset's
            parts list. Dispatches through the procedural synthesizer
            (no family-keyed branching).

    Returns:
        Additive payload with ``version``, ``family``, ``shape_program``,
        ``shape_program_summary``, ``synthesized_graph_nodes``,
        ``synthesized_node_count``, and ``v1_lowering``. No top-level
        ``diagnostics`` key — this validator is informational only and
        never blocks certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    brief = _resolve_brief(safe_runtime)
    parts = _resolve_parts(safe_asset)
    graph_nodes = _resolve_graph_nodes(safe_runtime)
    graph_edges = _resolve_graph_edges(safe_runtime)
    family = _resolve_family(brief)
    asset_name = _resolve_asset_name(safe_asset, brief)
    result = _select_recipe_result(
        family=family,
        asset_name=asset_name,
        brief=brief,
        parts=parts,
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
    )
    program = result.shape_program
    synthesized_nodes = _merge_synthesized_nodes(
        result.synthesized_graph_nodes,
        _source_authored_graph_nodes(safe_asset),
        _source_repair_policy_graph_nodes(safe_asset),
    )
    geometry_kernel, geometry_kernel_report = _resolve_v1_lowering_geometry_kernel(safe_runtime)
    adapter = lower_to_v1(program, geometry_kernel=geometry_kernel)
    kernel_metrics = _kernel_program_record_metrics(adapter.v1_records)
    return {
        "version": GRAMMAR_LOWERING_VERSION,
        "family": result.family,
        "shape_program": program.to_dict(),
        "shape_program_summary": _summarise_program(program),
        "synthesized_graph_nodes": [dict(node) for node in synthesized_nodes],
        "synthesized_node_count": len(synthesized_nodes),
        "v1_lowering": {
            "v1_record_count": len(adapter.v1_records),
            **geometry_kernel_report,
            **kernel_metrics,
            "diagnostics": [dict(item) for item in adapter.diagnostics],
            "unsupported_ops": list(adapter.unsupported_ops),
        },
    }


# --------------------------------------------------------------------
# NODE_TYPES contract anchor
# --------------------------------------------------------------------


# Anchors the synthesized-node-types contract: every node type emitted
# by the synthesized-graph-node helpers (authored fields + repair
# policies) must use a node_type from the construction_graph NODE_TYPES
# frozenset so a future opt-in merger can drop the synthesized nodes
# into the live construction graph without translation.
_SYNTHESIZED_NODE_TYPES_USED: frozenset[str] = frozenset(
    {
        "primary_volume",
        "frame",
        "panel",
        "guard",
        "inset",
        "handle",
        "hinge",
        "mount",
        "rail",
        "socket",
        "trim",
        "fastener",
        "decal_zone",
        "wear_zone",
        "material_zone",
        "bracket",
        "conduit",
    }
)


def _verify_node_type_contract() -> None:
    """Assert at import time that synthesized node types are members of NODE_TYPES."""
    unknown = _SYNTHESIZED_NODE_TYPES_USED - NODE_TYPES
    if unknown:
        raise AssertionError(
            f"grammar_lowering synthesized node types not in "
            f"construction_graph.NODE_TYPES: {sorted(unknown)}"
        )


_verify_node_type_contract()
