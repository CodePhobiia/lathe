"""Phase 4 deterministic ``SemanticConstructionGraph`` representation.

Adds an internal graph IR that records the construction relationships
(nodes and edges) implied by the asset's intent and runtime data — so
later phases (ShapeIR v2, grammar lowering, material/wear graph) and the
existing ``family_grammar`` validator have a structured surface to read
beyond the raw parts list.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 7.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 4.
Per-node-type / edge-type reference:
``docs/asset-quality/semantic-construction-graph.md``.

Extraction model
----------------

Phase 4 is an additive, best-effort layer:

1. Reads ``asset["intent"]["parts"]`` and infers a ``node_type`` for
   each part name via a deterministic case-insensitive substring map.
2. Optionally consumes
   ``runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]`` for
   additional structural hints; absence is tolerated and never raises.
3. Reads ``runtime["design_brief"]["brief"]["family"]`` for the
   ``family`` slot, falling back to ``"generic"``.

Edges are conservative on purpose:

- Every non-``primary_volume`` node receives an ``attached_to`` edge
  pointing to the first ``primary_volume`` node (when one exists).
- Two nodes that share a base name with ``_l`` / ``_r`` suffixes form a
  ``mirrors`` edge (alphabetical source ordering, deterministic).

Phase 6's grammar lowering will populate richer edge types
(``inset_into``, ``wraps_around``, ``cuts``, etc.) once ShapeIR v2 lands
in Phase 5; those node and edge slots are reserved here so the JSON
shape stays stable across the upgrade.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``design_brief`` and before
``family_grammar`` (both with ``stage_dependencies=[]`` and
``weight=0.0``). Topological order plus FIFO tie-break keeps the
registration-order placement, so ``family_grammar`` reads the graph
when present.

Output additively appears under the top-level ``construction_graph``
key of the validate-stage report. Like Phases 1, 2 and 3, the layer is
informational evidence only and never blocks certification — it omits
the ``diagnostics`` field so the ``FunctionValidator`` wrapper treats
the validator as passing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CONSTRUCTION_GRAPH_VERSION = "construction_graph_v1"


NODE_TYPES: frozenset[str] = frozenset(
    {
        "primary_volume",
        "frame",
        "panel",
        "inset",
        "trim",
        "guard",
        "rail",
        "bracket",
        "vent",
        "conduit",
        "latch",
        "weld",
        "socket",
        "mount",
        "handle",
        "hinge",
        "fastener",
        "decal_zone",
        "wear_zone",
        "material_zone",
    }
)


EDGE_TYPES: frozenset[str] = frozenset(
    {
        "attached_to",
        "inset_into",
        "wraps_around",
        "mirrors",
        "aligned_with",
        "supports",
        "cuts",
        "contains",
        "wears_on",
        "material_bound_to",
    }
)


@dataclass(frozen=True)
class ConstructionNode:
    """One construction node in the semantic graph.

    ``attributes`` is intentionally open-ended: Phase 5+ (ShapeIR v2)
    populates it with operation hints, dimensions, and bevel settings.
    Phase 4 leaves it empty — the field exists so the JSON shape stays
    stable across the upgrade.
    """

    node_id: str
    node_type: str
    attributes: dict[str, Any]


@dataclass(frozen=True)
class ConstructionEdge:
    """One construction edge between two nodes in the semantic graph."""

    source_id: str
    target_id: str
    edge_type: str
    attributes: dict[str, Any]


@dataclass(frozen=True)
class SemanticConstructionGraph:
    """A frozen semantic graph of construction nodes and edges."""

    asset_name: str
    family: str
    nodes: tuple[ConstructionNode, ...]
    edges: tuple[ConstructionEdge, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict (lists in place of tuples)."""
        return {
            "asset_name": self.asset_name,
            "family": self.family,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "attributes": dict(node.attributes),
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "edge_type": edge.edge_type,
                    "attributes": dict(edge.attributes),
                }
                for edge in self.edges
            ],
        }


# Rules are evaluated in declaration order; first substring match wins.
# Reorder with care — names that contain multiple tokens (e.g.
# "latch_panel" or "corner_guard_panel") resolve to the type of the
# earliest matching rule. Phase 5+ may add tokens here; preserve the
# intended precedence by appending broader tokens to the end and
# anchoring the contract via tests when the choice is non-obvious
# (see ``test_substring_rule_precedence_first_match_wins``).
_NODE_TYPE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("body",), "primary_volume"),
    (("lid",), "panel"),
    (("frame",), "frame"),
    (("vent", "grille", "grill", "louver", "louvre", "slat"), "vent"),
    (("conduit", "cable", "pipe", "duct", "raceway"), "conduit"),
    (("weld", "welded", "welding"), "weld"),
    (("latch", "clasp", "lock"), "latch"),
    (("bracket", "brace", "gusset"), "bracket"),
    (("panel",), "panel"),
    (("trim", "band"), "trim"),
    (("corner_guard", "corner", "guard"), "guard"),
    (("rail",), "rail"),
    (("socket",), "socket"),
    (("mount",), "mount"),
    (("handle",), "handle"),
    (("hinge",), "hinge"),
    (("fastener", "bolt", "rivet", "screw"), "fastener"),
    (("decal", "label", "warning"), "decal_zone"),
    (("wear",), "wear_zone"),
    (("material",), "material_zone"),
    (("foot", "feet"), "mount"),
)


_DEFAULT_NODE_TYPE = "panel"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _classify_part(part_name: str) -> str:
    """Return the ``node_type`` for a part name via the substring map."""
    lowered = part_name.lower()
    for tokens, node_type in _NODE_TYPE_RULES:
        for token in tokens:
            if token in lowered:
                return node_type
    return _DEFAULT_NODE_TYPE


def _resolve_family(runtime: dict[str, Any]) -> str:
    """Return the family token published by Phase 2's design_brief, or ``"generic"``."""
    design_brief = _as_dict(runtime.get("design_brief"))
    brief = _as_dict(design_brief.get("brief"))
    family = brief.get("family")
    if isinstance(family, str) and family:
        return family
    return "generic"


def _collect_part_node_ids(asset: dict[str, Any]) -> list[str]:
    """Return part ids from ``asset["intent"]["parts"]`` in declaration order."""
    intent = _as_dict(asset.get("intent"))
    raw_parts = _as_list(intent.get("parts"))
    parts: list[str] = []
    for part in raw_parts:
        if isinstance(part, str) and part:
            parts.append(part)
    return parts


_AUTHORED_GRAPH_NODE_FIELDS: tuple[tuple[tuple[str, ...], str | None], ...] = (
    (("intent", "materials"), "material_zone"),
    (("intent", "interactions"), "socket"),
    (("features", "allow"), None),
    (("assembly", "components"), None),
    (("assembly", "mechanisms"), "socket"),
    (("assembly", "traits"), None),
    (("surface", "materials"), "material_zone"),
    (("surface", "patterns"), "decal_zone"),
)

_MAX_AUTHORED_GRAPH_NODES = 32
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
        fragments: list[str] = []
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


def _authored_graph_nodes(
    asset: dict[str, Any],
    existing_ids: set[str],
) -> tuple[ConstructionNode, ...]:
    """Return graph nodes implied by existing positive authoring fields."""
    nodes: list[ConstructionNode] = []
    seen_ids: set[str] = set(existing_ids)
    for path, fallback_node_type in _AUTHORED_GRAPH_NODE_FIELDS:
        raw_value = _value_at_path(asset, path)
        source_path = ".".join(path)
        for fragment in _iter_text_fragments(raw_value):
            if len(nodes) >= _MAX_AUTHORED_GRAPH_NODES:
                return tuple(nodes)
            node_id = f"source.{source_path}.{_slug_fragment(fragment)}"
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            node_type = fallback_node_type or _classify_part(fragment)
            nodes.append(
                ConstructionNode(
                    node_id=node_id,
                    node_type=node_type,
                    attributes={
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


def _repair_policy_graph_nodes(
    asset: dict[str, Any],
    existing_ids: set[str],
) -> tuple[ConstructionNode, ...]:
    nodes: list[ConstructionNode] = []
    seen_ids: set[str] = set(existing_ids)
    for kind in _repair_policy_feature_kinds(asset):
        for node_type in _REPAIR_POLICY_FEATURE_NODE_TYPES.get(kind, ()):
            if len(nodes) >= _MAX_AUTHORED_GRAPH_NODES:
                return tuple(nodes)
            node_id = f"source.repair_policy.{kind}.{node_type}"
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            nodes.append(
                ConstructionNode(
                    node_id=node_id,
                    node_type=node_type,
                    attributes={
                        "source": "repair_policy",
                        "source_path": "repair_policy",
                        "repair_policy_feature": kind,
                    },
                )
            )
    return tuple(nodes)


def _asset_graph_extra_node_ids(
    runtime: dict[str, Any], existing_ids: set[str]
) -> list[str]:
    """Return any extra node ids hinted by the scaffold_report asset graph.

    Best-effort: tolerates missing/malformed structures and never raises.
    Only returns ids not already present in ``existing_ids``.
    """
    shape_bundle = _as_dict(_as_dict(runtime.get("shape")).get("bundle"))
    scaffold_report = _as_dict(shape_bundle.get("scaffold_report"))
    asset_graph = _as_dict(scaffold_report.get("asset_graph"))
    extras: list[str] = []
    seen: set[str] = set()

    raw_nodes = asset_graph.get("nodes")
    if isinstance(raw_nodes, list):
        for entry in raw_nodes:
            candidate_id: str | None = None
            if isinstance(entry, str):
                candidate_id = entry
            elif isinstance(entry, dict):
                for key in ("node_id", "id", "name"):
                    value = entry.get(key)
                    if isinstance(value, str) and value:
                        candidate_id = value
                        break
            if (
                candidate_id
                and candidate_id not in existing_ids
                and candidate_id not in seen
            ):
                extras.append(candidate_id)
                seen.add(candidate_id)

    raw_parts = asset_graph.get("parts")
    if isinstance(raw_parts, list):
        for entry in raw_parts:
            if (
                isinstance(entry, str)
                and entry
                and entry not in existing_ids
                and entry not in seen
            ):
                extras.append(entry)
                seen.add(entry)

    return extras


def _build_nodes(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> tuple[ConstructionNode, ...]:
    """Return the ordered tuple of construction nodes for the asset."""
    part_ids = _collect_part_node_ids(asset)
    seen: set[str] = set(part_ids)
    extras = _asset_graph_extra_node_ids(runtime, seen)
    seen.update(extras)

    ordered_ids = list(part_ids) + list(extras)

    nodes: list[ConstructionNode] = []
    for node_id in ordered_ids:
        nodes.append(
            ConstructionNode(
                node_id=node_id,
                node_type=_classify_part(node_id),
                attributes={},
            )
        )
    authored_nodes = _authored_graph_nodes(asset, seen)
    nodes.extend(authored_nodes)
    seen.update(node.node_id for node in authored_nodes)
    nodes.extend(_repair_policy_graph_nodes(asset, seen))
    return tuple(nodes)


def _strip_lr_suffix(node_id: str) -> str | None:
    """Return the base name when ``node_id`` ends in ``_l`` or ``_r``.

    Returns ``None`` for any other suffix (including ``_left`` and
    ``_right``) so mirror detection only fires on the canonical short
    suffixes the rest of the toolchain uses.
    """
    if node_id.endswith("_l") or node_id.endswith("_r"):
        return node_id[:-2]
    return None


def _build_edges(
    nodes: tuple[ConstructionNode, ...],
) -> tuple[ConstructionEdge, ...]:
    """Build the conservative Phase 4 edge set from the node list."""
    edges: list[ConstructionEdge] = []

    primary_target: str | None = None
    for node in nodes:
        if node.node_type == "primary_volume":
            primary_target = node.node_id
            break

    if primary_target is not None:
        for node in nodes:
            if node.node_id == primary_target:
                continue
            edges.append(
                ConstructionEdge(
                    source_id=node.node_id,
                    target_id=primary_target,
                    edge_type="attached_to",
                    attributes={},
                )
            )

    bases: dict[str, list[str]] = {}
    for node in nodes:
        base = _strip_lr_suffix(node.node_id)
        if base is None:
            continue
        bases.setdefault(base, []).append(node.node_id)

    for base in sorted(bases.keys()):
        members = sorted(bases[base])
        if len(members) < 2:
            continue
        for index in range(len(members) - 1):
            for partner in members[index + 1 :]:
                edges.append(
                    ConstructionEdge(
                        source_id=members[index],
                        target_id=partner,
                        edge_type="mirrors",
                        attributes={},
                    )
                )

    return tuple(edges)


def extract_construction_graph(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> SemanticConstructionGraph:
    """Best-effort extraction of the semantic construction graph.

    Args:
        asset: normalized asset dict. May omit ``intent``, ``parts``, or
            ``name``; the function tolerates partial/empty input and
            never raises.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["design_brief"]["brief"]["family"]`` (Phase 2) and
            optionally
            ``runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]``
            for additional structural hints.

    Returns:
        A frozen :class:`SemanticConstructionGraph` with deterministic
        node and edge tuples.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}

    asset_name = safe_asset.get("name")
    if not isinstance(asset_name, str) or not asset_name:
        asset_name = "unnamed_asset"

    family = _resolve_family(safe_runtime)
    nodes = _build_nodes(safe_asset, safe_runtime)
    edges = _build_edges(nodes)

    return SemanticConstructionGraph(
        asset_name=asset_name,
        family=family,
        nodes=nodes,
        edges=edges,
    )


def evaluate_construction_graph(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive construction-graph payload for the validate stage.

    Args:
        asset: normalized asset dict.
        runtime: stage-bundle runtime dict. The graph is best-effort; a
            missing ``design_brief`` block or ``shape``/``scaffold_report``
            structure is tolerated and never raises.

    Returns:
        Additive payload with ``version`` (``"construction_graph_v1"``),
        ``family``, ``asset_name``, ``nodes`` (list of node dicts),
        ``edges`` (list of edge dicts), ``node_count``, ``edge_count``,
        ``node_types_present`` (sorted unique node types), and
        ``edge_types_present`` (sorted unique edge types). No top-level
        ``diagnostics`` key — Phase 4 is informational only and never
        blocks certification.
    """
    graph = extract_construction_graph(asset, runtime)
    return {
        "version": CONSTRUCTION_GRAPH_VERSION,
        "family": graph.family,
        "asset_name": graph.asset_name,
        "nodes": [
            {
                "node_id": node.node_id,
                "node_type": node.node_type,
                "attributes": dict(node.attributes),
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "edge_type": edge.edge_type,
                "attributes": dict(edge.attributes),
            }
            for edge in graph.edges
        ],
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "node_types_present": sorted({node.node_type for node in graph.nodes}),
        "edge_types_present": sorted({edge.edge_type for edge in graph.edges}),
    }
