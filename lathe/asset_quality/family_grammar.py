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

For Phase 3's MVP, requirement detection is intentionally lightweight:
each requirement carries a tuple of ``detection_signals`` (lowercase
substring tokens), and a requirement is marked ``"satisfied"`` when at
least one entry in ``asset["intent"]["parts"]`` contains any signal
token (case-insensitive). Otherwise the requirement is ``"missing"``.

The MVP never emits ``"partial"`` — that status is reserved for
Phase 4's semantic construction graph (which can detect a corner-guard
edge present in the graph but not in the parts list) and Phase 6's
grammar lowering (which produces ShapeIR v2 operations directly).
``"not_applicable"`` is also reserved for forward phases (e.g. a
mechanical-door grammar might mark ``foot_rails`` as not-applicable
when the brief disables them).

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
    Phase 4+ will extend detection to also consume the semantic
    construction graph and ShapeIR v2 operations; the field name is
    intentionally generic so the same dataclass survives that
    transition.

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
    requirement: FamilyRequirement, parts: list[str]
) -> tuple[str, list[str]]:
    """Return ``(status, matched_parts)`` for one requirement.

    Phase 3 only emits ``"satisfied"`` or ``"missing"``. Each part is
    scanned against the requirement's ``detection_signals`` (already
    lowercase) and recorded if any token is a substring of the part
    name. Matched parts are returned in declaration order so the
    evidence is deterministic and human-readable.
    """
    matched: list[str] = []
    for part in parts:
        for token in requirement.detection_signals:
            if token in part:
                matched.append(part)
                break
    if matched:
        return _STATUS_SATISFIED, matched
    return _STATUS_MISSING, matched


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


def _result_for(grammar: FamilyGrammar, asset: dict[str, Any]) -> FamilyGrammarResult:
    parts = _normalised_parts(asset)
    statuses: list[str] = []
    requirement_results: list[dict[str, Any]] = []
    recommendations: list[str] = []
    satisfied_count = 0
    partial_count = 0
    missing_count = 0

    for requirement in grammar.requirements:
        status, matched = _detect_requirement(requirement, parts)
        statuses.append(status)
        requirement_results.append(
            {
                "name": requirement.name,
                "severity": requirement.severity,
                "status": status,
                "evidence": {"matched_parts": list(matched)},
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
            is absent.

    Returns:
        Additive payload with ``version`` (``"family_grammar_v1"``),
        ``family``, ``coverage``, per-status counts, ``requirement_results``
        (list of dicts with ``name``, ``severity``, ``status``, ``evidence``),
        and ``recommendations`` (one entry per missing/partial requirement
        in declaration order). No top-level ``diagnostics`` field — like
        Phases 1 and 2, this validator is informational only and never
        blocks certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    family = _resolve_family(safe_runtime)
    grammar = _grammar_for(family)
    result = _result_for(grammar, safe_asset)
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
