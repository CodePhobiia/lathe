"""SynthesizerContext + Stage 1 context resolution.

Stage 1 of the 8-stage compiler pipeline. Reads authored intent from
(asset, runtime) and produces an immutable SynthesizerContext that
all subsequent stages consume.

The family_alias appears here purely as metadata. Resolution maps a
family_id to (style_id, policy_ids, domain) via the FamilyAlias
lookup. After this stage, no stage references the family identifier
for behavior — only style and policies drive subsequent stages.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .knowledge_loader import (
    CompositionPolicy,
    FamilyAlias,
    StyleKnowledge,
    load_all_alias_packs,
    load_all_policy_packs,
    load_all_style_packs,
)
from .trace import TraceBuilder


@dataclass(frozen=True)
class ConstructionNodeTyped:
    """Construction node with validated typed attributes.

    Produced by Stage 4 (validate_attributes). The original raw
    attributes from the asset are preserved in ``raw_attributes`` for
    audit; ``typed_attributes`` is the schema-validated form generators
    consume.
    """

    node_id: str
    node_type: str
    domain: str
    raw_attributes: Mapping[str, Any]
    typed_attributes: Any  # one of the dataclasses from .attributes
    added_by_policy: str | None = None  # policy_id if policy expansion added it


@dataclass(frozen=True)
class ConstructionEdgeTyped:
    """Construction edge with validated typed attributes."""

    source_id: str
    target_id: str
    edge_type: str
    domain: str
    raw_attributes: Mapping[str, Any]
    typed_attributes: Any
    added_by_policy: str | None = None


@dataclass(frozen=True)
class SynthesizerContext:
    """Per-synthesis-call immutable context.

    Populated by Stage 1 and refined by subsequent stages. Generators
    and decorators receive this as their second argument. No global
    state, no mutation; everything synthesizer-related flows through
    this struct.
    """

    asset: Mapping[str, Any]
    runtime: Mapping[str, Any]
    asset_name: str
    parts: tuple[str, ...]
    intent_tags: tuple[str, ...]
    brief: Mapping[str, Any]
    domain: str  # routes to domain-specific generators

    # Resolved knowledge (None means absent / no alias)
    style: StyleKnowledge | None
    policies: tuple[CompositionPolicy, ...]
    family_alias: str | None  # METADATA ONLY — never dispatched on

    # Loaded but not yet expanded — the raw authored graph
    raw_graph_nodes: tuple[Mapping[str, Any], ...]
    raw_graph_edges: tuple[Mapping[str, Any], ...]

    # Populated by Stage 4
    typed_nodes: tuple[ConstructionNodeTyped, ...] = ()
    typed_edges: tuple[ConstructionEdgeTyped, ...] = ()


def _resolve_parts(asset: Mapping[str, Any]) -> tuple[str, ...]:
    intent = asset.get("intent") if isinstance(asset, Mapping) else None
    if not isinstance(intent, Mapping):
        return ()
    raw_parts = intent.get("parts") or ()
    if not isinstance(raw_parts, (list, tuple)):
        return ()
    return tuple(str(p) for p in raw_parts if p)


def _resolve_intent_tags(asset: Mapping[str, Any]) -> tuple[str, ...]:
    intent = asset.get("intent") if isinstance(asset, Mapping) else None
    if not isinstance(intent, Mapping):
        return ()
    raw_tags = intent.get("tags") or ()
    if not isinstance(raw_tags, (list, tuple)):
        return ()
    return tuple(str(t) for t in raw_tags if t)


def _resolve_brief(runtime: Mapping[str, Any]) -> Mapping[str, Any]:
    design_brief = runtime.get("design_brief") if isinstance(runtime, Mapping) else None
    if not isinstance(design_brief, Mapping):
        return {}
    brief = design_brief.get("brief")
    return brief if isinstance(brief, Mapping) else {}


def _resolve_asset_name(asset: Mapping[str, Any], brief: Mapping[str, Any]) -> str:
    name = asset.get("name") if isinstance(asset, Mapping) else None
    if isinstance(name, str) and name:
        return name
    brief_name = brief.get("asset_name") if isinstance(brief, Mapping) else None
    if isinstance(brief_name, str) and brief_name:
        return brief_name
    return "procedural_asset"


def _resolve_graph_nodes(runtime: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    graph = runtime.get("construction_graph") if isinstance(runtime, Mapping) else None
    if not isinstance(graph, Mapping):
        return ()
    nodes = graph.get("nodes") or ()
    if not isinstance(nodes, (list, tuple)):
        return ()
    return tuple(n for n in nodes if isinstance(n, Mapping))


def _resolve_graph_edges(runtime: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    graph = runtime.get("construction_graph") if isinstance(runtime, Mapping) else None
    if not isinstance(graph, Mapping):
        return ()
    edges = graph.get("edges") or ()
    if not isinstance(edges, (list, tuple)):
        return ()
    return tuple(e for e in edges if isinstance(e, Mapping))


@dataclass
class _ResolvedKnowledge:
    style: StyleKnowledge | None
    policies: tuple[CompositionPolicy, ...]
    domain: str
    family_alias: str | None


def _resolve_knowledge(
    brief: Mapping[str, Any],
    *,
    style_packs: Mapping[str, StyleKnowledge],
    policy_packs: Mapping[str, CompositionPolicy],
    alias_packs: Mapping[str, FamilyAlias],
    trace: TraceBuilder,
) -> _ResolvedKnowledge:
    """Resolve knowledge from brief — either via family alias OR directly.

    Authored intent can specify (style_id, policy_ids, domain)
    directly in the brief. If the brief instead names a family, the
    family alias is looked up (METADATA ONLY) and resolves to the
    same (style, policies, domain) triple.

    Either path produces an identical SynthesizerContext. The family
    name appears only in the trace, never in subsequent dispatch.
    """
    family = brief.get("family") if isinstance(brief, Mapping) else None
    family = str(family) if isinstance(family, str) and family else None

    # Path 1: explicit style/policies/domain in brief (preferred procedural style)
    direct_style_id = brief.get("style_id")
    direct_policy_ids = brief.get("policy_ids")
    direct_domain = brief.get("domain")
    if direct_style_id or direct_policy_ids or direct_domain:
        style = style_packs.get(str(direct_style_id)) if direct_style_id else None
        policies = tuple(
            policy_packs[str(pid)]
            for pid in (direct_policy_ids or ())
            if str(pid) in policy_packs
        )
        domain = str(direct_domain) if direct_domain else (
            policies[0].domain if policies else "hard_surface"
        )
        return _ResolvedKnowledge(style=style, policies=policies, domain=domain, family_alias=family)

    # Path 2: family alias lookup. The .lth ``from <family>`` convention
    # appends a ``_family`` suffix (``industrial_crate_family``) while the
    # alias JSON registry is keyed by the stem (``industrial_crate``).
    # Accept either form so callers don't need to normalize upstream.
    if family is not None:
        alias = alias_packs.get(family)  # no-family-dispatch: declarative alias-pack lookup, see _family_alias_exists
        if alias is None and family.endswith("_family"):
            stem = family[: -len("_family")]
            alias = alias_packs.get(stem)  # no-family-dispatch: same registry, stem form
        if alias is not None:
            trace.emit(
                "alias_resolved",
                stage=1,
                family=family,
                style_id=alias.style_id,
                policy_ids=list(alias.policy_ids),
                domain=alias.domain,
            )
            style = style_packs.get(alias.style_id)
            policies = tuple(
                policy_packs[pid] for pid in alias.policy_ids if pid in policy_packs
            )
            return _ResolvedKnowledge(
                style=style,
                policies=policies,
                domain=alias.domain,
                family_alias=family,
            )
        trace.emit("alias_missing", stage=1, family=family)

    # Path 3: no knowledge resolved — synthesizer runs on the authored
    # graph alone, biased only by generator-internal defaults.
    return _ResolvedKnowledge(
        style=None, policies=(), domain="hard_surface", family_alias=family
    )


def resolve_context(
    asset: Mapping[str, Any],
    runtime: Mapping[str, Any],
    *,
    style_packs: Mapping[str, StyleKnowledge] | None = None,
    policy_packs: Mapping[str, CompositionPolicy] | None = None,
    alias_packs: Mapping[str, FamilyAlias] | None = None,
    trace: TraceBuilder | None = None,
) -> SynthesizerContext:
    """Stage 1 of the compiler pipeline. Build the immutable context.

    Knowledge packs are loaded once per call by default. Tests pass
    pre-loaded mappings to bypass disk IO; production code lets the
    function load from std/procedural/knowledge/.
    """
    trace = trace if trace is not None else TraceBuilder()
    trace.emit("stage_start", stage=1)

    style_packs = style_packs if style_packs is not None else load_all_style_packs()
    policy_packs = policy_packs if policy_packs is not None else load_all_policy_packs()
    alias_packs = alias_packs if alias_packs is not None else load_all_alias_packs()

    brief = _resolve_brief(runtime)
    parts = _resolve_parts(asset)
    intent_tags = _resolve_intent_tags(asset)
    asset_name = _resolve_asset_name(asset, brief)
    raw_nodes = _resolve_graph_nodes(runtime)
    raw_edges = _resolve_graph_edges(runtime)

    resolved = _resolve_knowledge(
        brief,
        style_packs=style_packs,
        policy_packs=policy_packs,
        alias_packs=alias_packs,
        trace=trace,
    )
    if resolved.style is not None:
        trace.emit("style_loaded", stage=1, style_id=resolved.style.style_id)
    for policy in resolved.policies:
        trace.emit("policy_loaded", stage=1, policy_id=policy.policy_id)

    ctx = SynthesizerContext(
        asset=asset,
        runtime=runtime,
        asset_name=asset_name,
        parts=parts,
        intent_tags=intent_tags,
        brief=brief,
        domain=resolved.domain,
        style=resolved.style,
        policies=resolved.policies,
        family_alias=resolved.family_alias,
        raw_graph_nodes=raw_nodes,
        raw_graph_edges=raw_edges,
    )
    trace.emit("stage_end", stage=1)
    return ctx
