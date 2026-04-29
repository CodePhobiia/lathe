"""Phase 3 deterministic ``FamilyGrammar`` IR.

Adds an internal ``FamilyGrammar`` representation that captures the
required, recommended, and optional construction concepts every hero
asset family must contain. The MVP encodes the ``industrial_crate``
grammar (10 requirements) plus a ``generic`` fallback grammar so unknown
families degrade gracefully.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 7.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 3.
Per-requirement reference: ``docs/asset-quality/family-grammar-v1.md``.

Detection model
---------------

Phase 3 detection used parts-list substring matching only. Phase 4
extends the model with the semantic construction graph: each
requirement now also carries a ``graph_node_types`` allowlist of node
types from ``lathe.asset_quality.construction_graph.NODE_TYPES``.

Detection precedence is:

1. If any entry in ``asset["intent"]["parts"]`` contains one of the
   requirement's ``detection_signals`` (case-insensitive), the
   requirement is ``"satisfied"`` and ``evidence`` includes
   ``matched_parts``.
2. Otherwise, if ``runtime["construction_graph"]["nodes"]`` contains a
   node whose ``node_type`` is in the requirement's
   ``graph_node_types`` allowlist, the requirement is ``"partial"``
   and ``evidence`` additionally includes ``matched_graph_nodes``.
3. Otherwise, the requirement is ``"missing"``.

Parts evidence dominates because parts represent explicit authoring
intent while graph evidence is derived. ``"not_applicable"`` is still
reserved for forward phases (e.g. a mechanical-door grammar might mark
``foot_rails`` as not-applicable when the brief disables them).
Backward compatibility: when ``runtime["construction_graph"]`` is
absent or malformed, the graph-elevation path is skipped and Phase 3
behaviour is preserved exactly.

Generic fallback
----------------

Unknown families fall through to the ``generic`` grammar, which has an
empty ``requirements`` tuple. ``coverage`` defaults to ``1.0`` (no
requirements means trivially satisfied), the per-status counts are
zero, and the recommendations array is empty. Phase 4+ will introduce
graph-derived requirements for the generic family; until then, the
fallback is informational only and never warns.

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``design_brief`` and before
``quality_diagnostics`` so that the family lookup uses the brief's
inferred family and the additive ``family_grammar_coverage`` metric in
``quality_diagnostics`` can read this validator's evidence.

Output additively appears under the top-level ``family_grammar`` key of
the validate-stage report. Existing report fields are preserved and the
validator never produces blocking diagnostics — like Phases 1 and 2,
this layer is informational evidence for downstream classifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FAMILY_GRAMMAR_VERSION = "family_grammar_v1"


_SEVERITY_REQUIRED = "required"
_SEVERITY_RECOMMENDED = "recommended"
_SEVERITY_OPTIONAL = "optional"

_STATUS_SATISFIED = "satisfied"
_STATUS_PARTIAL = "partial"
_STATUS_MISSING = "missing"
_STATUS_NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class FamilyRequirement:
    """One construction concept the family grammar expects.

    ``detection_signals`` is a tuple of lowercase substring tokens the
    MVP matches against ``asset["intent"]["parts"]`` (case-insensitive).
    Phase 4 extends detection to also consume the semantic construction
    graph (see ``graph_node_types``); Phase 6+ will lower these into
    ShapeIR v2 operations. The field name is intentionally generic so
    the same dataclass survives those transitions.

    ``graph_node_types`` is a tuple of construction-graph node-type
    tokens (see ``lathe.asset_quality.construction_graph.NODE_TYPES``).
    When parts-list detection misses but the construction graph contains
    a node whose ``node_type`` matches any token here, the requirement
    is elevated from ``"missing"`` to ``"partial"`` (Phase 4 semantics).
    Default is the empty tuple, which preserves Phase 3 behaviour for
    requirements that opt out of graph-based elevation.

    ``recommendation_template`` is the human-readable repair string
    surfaced in ``FamilyGrammarResult.recommendations`` when the
    requirement's status is ``"missing"`` or ``"partial"``. Co-locating
    the template with the requirement (rather than a parallel dict)
    keeps each requirement a single source of truth.
    """

    name: str
    description: str
    severity: str
    detection_signals: tuple[str, ...]
    recommendation_template: str
    graph_node_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class FamilyGrammar:
    """A frozen registry of requirements for one asset family."""

    family: str
    version: str
    requirements: tuple[FamilyRequirement, ...]


@dataclass(frozen=True)
class FamilyGrammarResult:
    """The outcome of evaluating one ``FamilyGrammar`` against an asset.

    ``coverage`` is the weighted satisfaction in ``[0.0, 1.0]``; see
    :func:`_compute_coverage` for the exact formula. ``recommendations``
    contains one human-readable repair suggestion per missing or partial
    requirement (in declaration order).
    """

    family: str
    version: str
    requirement_results: tuple[dict[str, Any], ...]
    coverage: float
    satisfied_count: int
    partial_count: int
    missing_count: int
    recommendations: tuple[str, ...]


_INDUSTRIAL_CRATE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="body_shell",
        description=(
            "A primary box-shell body forms the structural volume of the "
            "crate."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body",),
        recommendation_template=(
            "Add a primary body shell: the industrial crate grammar requires "
            "a structural box volume the rest of the construction hangs from."
        ),
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="lid_seam",
        description=(
            "A visible lid break wraps the top of the body, distinguishing "
            "the lid from the shell."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("lid",),
        recommendation_template=(
            "Add a lid seam: the industrial crate grammar requires a visible "
            "lid break wrapping the top of the body."
        ),
        graph_node_types=("panel",),
    ),
    FamilyRequirement(
        name="corner_guards",
        description=(
            "Reinforcement corner guards wrap the eight body corners and "
            "give the crate its industrial silhouette."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("corner_guard", "corner", "guard"),
        recommendation_template=(
            "Add corner guards: the industrial crate grammar requires "
            "reinforcement corners on the eight body corners."
        ),
        graph_node_types=("guard",),
    ),
    FamilyRequirement(
        name="latch_or_latch_plate",
        description=(
            "A latch or latch plate sits at the lid/body seam and grants "
            "the crate a clear front face."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("latch",),
        recommendation_template=(
            "Add a latch or latch plate at the lid/body seam so the crate has "
            "a clear front face."
        ),
        graph_node_types=("inset",),
    ),
    FamilyRequirement(
        name="recessed_or_bracketed_handles",
        description=(
            "Handles are seated into recessed wells or bracket plates "
            "rather than glued onto the shell as separate primitives."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("handle",),
        recommendation_template=(
            "Seat handles into recessed wells or bracket plates rather than "
            "placing them as floating primitives on the shell."
        ),
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="foot_rails_or_feet",
        description=(
            "Foot rails or discrete feet lift the body off the ground "
            "plane and read as functional."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("foot", "feet", "rail"),
        recommendation_template=(
            "Add foot rails or discrete feet to lift the body off the ground "
            "plane."
        ),
        graph_node_types=("mount", "rail"),
    ),
    FamilyRequirement(
        name="trim_bands",
        description=(
            "Horizontal or vertical trim bands break up the body shell "
            "and add medium-scale construction hierarchy."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("trim", "band"),
        recommendation_template=(
            "Add horizontal or vertical trim bands to break up the body shell "
            "with medium-scale construction hierarchy."
        ),
        graph_node_types=("trim",),
    ),
    FamilyRequirement(
        name="fasteners",
        description=(
            "Fasteners (bolts, rivets, screws) are visible at structural "
            "junctions and reinforce the industrial brief."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "rivet", "screw"),
        recommendation_template=(
            "Add visible fasteners (bolts, rivets, or screws) at structural "
            "junctions to reinforce the industrial brief."
        ),
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="warning_or_decal_zones",
        description=(
            "Warning text, stencils, or decal zones provide surface "
            "storytelling on the body."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("warning", "decal", "label"),
        recommendation_template=(
            "Add warning text, stencils, or decal zones to provide surface "
            "storytelling on the body."
        ),
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="edge_wear_masks",
        description=(
            "Edge wear masks expose paint chips and metal at high-traffic "
            "edges, breaking the debug-material look."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear"),
        recommendation_template=(
            "Add edge wear masks so paint chips and metal show at high-traffic "
            "edges instead of a uniform debug-material look."
        ),
        graph_node_types=("wear_zone",),
    ),
)


_GRAMMARS: dict[str, FamilyGrammar] = {
    "industrial_crate": FamilyGrammar(
        family="industrial_crate",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_INDUSTRIAL_CRATE_REQUIREMENTS,
    ),
    "generic": FamilyGrammar(
        family="generic",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=(),
    ),
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalised_parts(asset: dict[str, Any]) -> list[str]:
    """Return ``asset["intent"]["parts"]`` lowercased, tolerating shape drift."""
    intent = _as_dict(asset.get("intent"))
    raw_parts = _as_list(intent.get("parts"))
    parts: list[str] = []
    for part in raw_parts:
        if isinstance(part, str):
            parts.append(part.lower())
    return parts


def _detect_requirement(
    requirement: FamilyRequirement,
    parts: list[str],
    graph_nodes: tuple[dict[str, Any], ...] = (),
) -> tuple[str, list[str], list[str]]:
    """Return ``(status, matched_parts, matched_graph_nodes)`` for one requirement.

    Phase 4 detection precedence:

    1. Substring match against ``asset["intent"]["parts"]`` -> ``"satisfied"``.
    2. Otherwise, ``node_type`` match against the construction graph
       (``runtime["construction_graph"]["nodes"]``) -> ``"partial"``.
    3. Otherwise -> ``"missing"``.

    Parts wins over graph evidence because parts are explicit authoring
    intent, while graph evidence is derived. ``graph_nodes`` is a tuple
    of node dicts (each with at least ``node_id`` and ``node_type``) and
    defaults to the empty tuple, preserving Phase 3 behaviour for
    callers that don't pass graph evidence.
    """
    matched_parts: list[str] = []
    for part in parts:
        for token in requirement.detection_signals:
            if token in part:
                matched_parts.append(part)
                break
    if matched_parts:
        return _STATUS_SATISFIED, matched_parts, []

    matched_graph_nodes: list[str] = []
    if requirement.graph_node_types and graph_nodes:
        allowlist = set(requirement.graph_node_types)
        for entry in graph_nodes:
            if not isinstance(entry, dict):
                continue
            node_type = entry.get("node_type")
            if not isinstance(node_type, str) or node_type not in allowlist:
                continue
            node_id = entry.get("node_id")
            if isinstance(node_id, str) and node_id:
                matched_graph_nodes.append(node_id)
    if matched_graph_nodes:
        return _STATUS_PARTIAL, matched_parts, matched_graph_nodes
    return _STATUS_MISSING, matched_parts, matched_graph_nodes


def _compute_coverage(
    requirements: tuple[FamilyRequirement, ...],
    statuses: tuple[str, ...],
) -> float:
    """Return weighted coverage in ``[0.0, 1.0]``.

    Optional requirements do not count toward the denominator.
    Satisfied requirements contribute 1.0, partial contributes 0.5,
    missing contributes 0.0. ``not_applicable`` is excluded entirely
    (it neither helps nor hurts).
    """
    total_applicable = 0
    earned = 0.0
    for requirement, status in zip(requirements, statuses, strict=True):
        if requirement.severity == _SEVERITY_OPTIONAL:
            continue
        if status == _STATUS_NOT_APPLICABLE:
            continue
        total_applicable += 1
        if status == _STATUS_SATISFIED:
            earned += 1.0
        elif status == _STATUS_PARTIAL:
            earned += 0.5
    # Trivially satisfied: covers the empty-requirements path (generic
    # family fallback) today and the Phase 4+ case where every
    # requirement is "not_applicable" for a particular asset.
    if total_applicable == 0:
        return 1.0
    return round(earned / total_applicable, 6)


def _construction_graph_nodes(runtime: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return the construction-graph node dicts published by Phase 4.

    Tolerates an absent or malformed ``runtime["construction_graph"]``
    block by returning the empty tuple. Phase 3 callers that do not
    populate ``runtime["construction_graph"]`` therefore retain their
    original parts-only detection.
    """
    construction_graph = runtime.get("construction_graph")
    if not isinstance(construction_graph, dict):
        return ()
    raw_nodes = construction_graph.get("nodes")
    if not isinstance(raw_nodes, list):
        return ()
    return tuple(entry for entry in raw_nodes if isinstance(entry, dict))


def _result_for(
    grammar: FamilyGrammar,
    asset: dict[str, Any],
    runtime: dict[str, Any],
) -> FamilyGrammarResult:
    parts = _normalised_parts(asset)
    graph_nodes = _construction_graph_nodes(runtime)
    statuses: list[str] = []
    requirement_results: list[dict[str, Any]] = []
    recommendations: list[str] = []
    satisfied_count = 0
    partial_count = 0
    missing_count = 0

    for requirement in grammar.requirements:
        status, matched_parts, matched_graph_nodes = _detect_requirement(
            requirement, parts, graph_nodes
        )
        statuses.append(status)
        evidence: dict[str, Any] = {"matched_parts": list(matched_parts)}
        if matched_graph_nodes:
            evidence["matched_graph_nodes"] = list(matched_graph_nodes)
        requirement_results.append(
            {
                "name": requirement.name,
                "severity": requirement.severity,
                "status": status,
                "evidence": evidence,
            }
        )
        if status == _STATUS_SATISFIED:
            satisfied_count += 1
        elif status == _STATUS_PARTIAL:
            partial_count += 1
            recommendations.append(requirement.recommendation_template)
        elif status == _STATUS_MISSING:
            missing_count += 1
            recommendations.append(requirement.recommendation_template)

    coverage = _compute_coverage(grammar.requirements, tuple(statuses))

    return FamilyGrammarResult(
        family=grammar.family,
        version=grammar.version,
        requirement_results=tuple(requirement_results),
        coverage=coverage,
        satisfied_count=satisfied_count,
        partial_count=partial_count,
        missing_count=missing_count,
        recommendations=tuple(recommendations),
    )


def _resolve_family(runtime: dict[str, Any]) -> str:
    """Return the family token published by Phase 2's design_brief, or ``"generic"``."""
    design_brief = _as_dict(runtime.get("design_brief"))
    brief = _as_dict(design_brief.get("brief"))
    family = brief.get("family")
    if isinstance(family, str) and family:
        return family
    return "generic"


def _grammar_for(family: str) -> FamilyGrammar:
    return _GRAMMARS.get(family, _GRAMMARS["generic"])


def evaluate_family_grammar(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive family-grammar payload for the validate stage.

    Args:
        asset: normalized asset dict. May omit ``intent`` or ``parts``;
            the function tolerates partial/empty input.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["design_brief"]["brief"]["family"]`` (populated by
            the Phase 2 design_brief validator running first in
            ``_PIPELINE``); falls back to ``"generic"`` when the brief
            is absent. Also reads ``runtime["construction_graph"]["nodes"]``
            (Phase 4) and uses the graph as fallback evidence: a
            requirement whose parts-list signals do not match but whose
            ``graph_node_types`` allowlist matches a graph node is
            elevated from ``"missing"`` to ``"partial"``. Absent or
            malformed graph data preserves the parts-only Phase 3 path.

    Returns:
        Additive payload with ``version`` (``"family_grammar_v1"``),
        ``family``, ``coverage``, per-status counts, ``requirement_results``
        (list of dicts with ``name``, ``severity``, ``status``, ``evidence``;
        ``evidence`` carries ``matched_parts`` always and additionally
        ``matched_graph_nodes`` when a graph-only elevation fired), and
        ``recommendations`` (one entry per missing/partial requirement in
        declaration order). No top-level ``diagnostics`` field — like
        Phases 1 and 2, this validator is informational only and never
        blocks certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    family = _resolve_family(safe_runtime)
    grammar = _grammar_for(family)
    result = _result_for(grammar, safe_asset, safe_runtime)
    return {
        "version": result.version,
        "family": result.family,
        "coverage": result.coverage,
        "satisfied_count": result.satisfied_count,
        "partial_count": result.partial_count,
        "missing_count": result.missing_count,
        "requirement_results": list(result.requirement_results),
        "recommendations": list(result.recommendations),
    }
