"""Phase 10 optional vision-critique loop.

Allows optional rendered-preview critique to produce **semantic
patch proposals** (not raw mesh edits) against the design brief,
family grammar, and ShapeIR v2. Phase 10 is **evidence + diagnostic
only** — it does not run a renderer, drive Blender, or mutate the
asset. Patches are validated and recorded as evidence; their
application is reserved for a forward phase.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 11.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 10.
Per-feature reference: ``docs/asset-quality/vision-critique-loop.md``.

Design summary
--------------

Phase 10 introduces three layers:

- A **deterministic stub provider** that consumes the existing
  Phase 1-9 evidence views and synthesises critique issues using
  threshold-based mapping. It is a pure function over
  ``(asset, runtime)`` — no network, no disk, no clock.
- An **optional external vision provider hook** that activates only
  when the runtime config wires it via
  ``runtime["_runtime_config"]["vision_critique"]["enabled"] == True``.
  The provider mux returns truthful skipped evidence when the
  provider is missing, misconfigured, unknown, or unreachable. The
  evaluator NEVER fabricates vision-model output.
- A **patch validator** that checks every patch proposal against a
  whitelist of targets, operations, fields, and serialisable values
  (and explicitly forbids touches to the
  ``lathe.shape.intent_mesh_handoff_v1`` contract or the public
  ``.lth`` syntax). Approved patches are recorded as evidence;
  rejected patches surface in ``patch_validation.rejections`` with
  structured reason tokens.

Critique signals
----------------

The deterministic stub maps the following Phase 1-9 evidence views
into critique issues:

- ``quality_diagnostics.metrics.debug_material_preview_penalty > 0.50``
  -> material storytelling issue under ``design_brief.material_age`` /
  ``design_brief.wear``.
- ``quality_diagnostics.metrics.highlow_fake_detail_penalty > 0.40``
  -> high/low realness issue under ``design_brief.detail_density``.
- ``quality_diagnostics.metrics.random_triangulation_penalty > 0.30``
  -> shape-language issue under ``design_brief.shape_language``.
- ``family_grammar.coverage < 0.70`` -> coverage issue under
  ``family_grammar.missing_requirements``.
- ``material_wear_graph.uniform_noise.is_uniform_noise == True`` ->
  uniform-noise issue under ``design_brief.wear``.
- ``preview_evidence.preview_summary.distinct_final_from_material_ids ==
  False`` -> missing-final-beauty issue under
  ``design_brief.negative_constraints``.

Each signal emits a deterministic ``issue_id`` derived from
``blake2b((evidence_view, recommendation))``; identical inputs
always produce identical critique payloads.

Patch validation rules
----------------------

A patch is approved iff all the following hold:

1. ``target`` is one of ``{"design_brief", "family_grammar",
   "shape_ir_v2"}`` (other tokens fail with ``invalid_target``).
2. ``operation`` is one of ``{"set", "add", "remove", "increase",
   "decrease"}`` (other tokens fail with ``invalid_operation``).
3. ``field`` is a non-empty dotted path that begins with the
   ``target`` token (other shapes fail with
   ``field_path_malformed``).
4. ``proposed_value`` is JSON-serialisable (functions / sentinels /
   open file handles fail with ``non_serializable_value``).
5. The field path does NOT touch the
   ``lathe.shape.intent_mesh_handoff_v1`` contract metadata
   (``touches_shape_contract``).
6. The field path does NOT propose changes to public ``.lth``
   surface keys (``profile``, ``contract``, ``critic``, ``asset``,
   ``variant``) — those are reserved for Phase 13
   (``touches_public_surface``).

Phase 10 records validated patches AS EVIDENCE; it does NOT mutate
the asset.

Skipped-evidence contract
-------------------------

When the vision provider is unavailable, the evaluator emits one of
the following structured reason tokens (per ``AGENTS.md``, never a
fabricated critique):

- ``vision_provider_not_configured`` — no vision_critique block in
  the runtime config (default).
- ``vision_provider_misconfigured`` — block present and enabled but
  no provider id supplied.
- ``vision_provider_unknown`` — provider id not in the registry.
- ``vision_provider_unavailable`` — provider raised
  ``ConnectionError`` / ``TimeoutError`` / ``OSError`` during the
  build.

In all cases the deterministic stub still runs and the validator
returns a well-formed payload.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``preview_evidence`` and before
``geometry_integrity``. Output additively appears under the
top-level ``vision_critique`` key of the validate-stage report
(the 24th top-level key, on top of the 23 that Phases 0 through 9
publish).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


VISION_CRITIQUE_VERSION = "vision_critique_v1"

_DETERMINISTIC_STUB_NAME = "deterministic_stub"
_DETERMINISTIC_STUB_VERSION = "v1"

_SEVERITY_INFO = "info"
_SEVERITY_WARNING = "warning"
_SEVERITY_ERROR = "error"

_SEVERITY_RANK: dict[str, int] = {
    _SEVERITY_ERROR: 0,
    _SEVERITY_WARNING: 1,
    _SEVERITY_INFO: 2,
}

_VALID_PATCH_TARGETS: frozenset[str] = frozenset(
    {"design_brief", "family_grammar", "shape_ir_v2"}
)

_VALID_PATCH_OPERATIONS: frozenset[str] = frozenset(
    {"set", "add", "remove", "increase", "decrease"}
)

_PUBLIC_SURFACE_TOKENS: frozenset[str] = frozenset(
    {"profile", "contract", "critic", "asset", "variant"}
)

_SHAPE_CONTRACT_TOKEN = "lathe.shape.intent_mesh_handoff_v1"

_DEBUG_MATERIAL_THRESHOLD = 0.50
_HIGHLOW_FAKE_THRESHOLD = 0.40
_RANDOM_TRIANGULATION_THRESHOLD = 0.30
_FAMILY_GRAMMAR_COVERAGE_THRESHOLD = 0.70


@dataclass(frozen=True)
class PatchProposal:
    """One semantic patch proposal.

    A patch proposes a change to the design brief, family grammar,
    or ShapeIR v2 — never to raw mesh data or to public ``.lth``
    syntax. ``current_value`` is informational and may be ``None``
    when the validator did not read the prior state.
    """

    target: str
    field: str
    operation: str
    current_value: Any | None
    proposed_value: Any
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "field": self.field,
            "operation": self.operation,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class CritiqueIssue:
    """One critique issue with attached patch proposals.

    ``issue_id`` is a deterministic hash derived from
    ``(evidence_view, recommendation)``; identical inputs always
    produce the same id. Severity is one of ``{"info", "warning",
    "error"}``. ``evidence_view`` names the Phase 1-9 view the issue
    was synthesised from (e.g. ``"quality_diagnostics"``).
    """

    issue_id: str
    severity: str
    evidence_view: str
    recommendation: str
    patch_proposals: tuple[PatchProposal, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "severity": self.severity,
            "evidence_view": self.evidence_view,
            "recommendation": self.recommendation,
            "patch_proposals": [patch.to_dict() for patch in self.patch_proposals],
        }


@dataclass(frozen=True)
class CritiqueProvider:
    """Provider record carried in the payload.

    ``configured`` is True only when an external vision provider was
    explicitly enabled via the runtime config; the deterministic
    stub always reports ``configured=False`` even when it is the
    selected provider.
    """

    name: str
    version: str
    configured: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "configured": self.configured,
        }


@dataclass(frozen=True)
class SkippedReason:
    """One structured skipped-evidence record.

    ``category`` is the gate that was skipped (e.g.
    ``"vision_provider"``, ``"patch_validation"``). ``reason`` is a
    token from the Phase 10 vocabulary.
    """

    category: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"category": self.category, "reason": self.reason}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _issue_id(evidence_view: str, recommendation: str) -> str:
    """Derive a stable 16-char id from the evidence view + recommendation.

    Using ``blake2b`` keeps the id short and independent of Python's
    ``hash()`` randomization. Same input -> same output across runs.
    """
    payload = f"{evidence_view}|{recommendation}".encode("utf-8")
    return hashlib.blake2b(payload, digest_size=8).hexdigest()


def _is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return False
    return True


# ---------------------------------------------------------------------------
# Deterministic stub provider
# ---------------------------------------------------------------------------


def _quality_diagnostics_metrics(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("quality_diagnostics")).get("metrics"))


def _family_grammar_evidence(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(runtime.get("family_grammar"))


def _material_wear_uniform_noise(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("material_wear_graph")).get("uniform_noise"))


def _preview_summary(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("preview_evidence")).get("preview_summary"))


def _highlow_relation(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(runtime.get("highlow_relation"))


def _design_brief_brief(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("design_brief")).get("brief"))


def _missing_requirement_names(grammar: dict[str, Any]) -> list[str]:
    """Return missing/partial requirement names from the family grammar evidence."""
    requirement_results = grammar.get("requirement_results")
    if not isinstance(requirement_results, list):
        return []
    missing: list[str] = []
    for record in requirement_results:
        if not isinstance(record, dict):
            continue
        status = record.get("status")
        name = record.get("name")
        if status in ("missing", "partial") and isinstance(name, str) and name:
            missing.append(name)
    return missing


def _stub_debug_material_issue(
    metrics: dict[str, Any],
    brief: dict[str, Any],
) -> CritiqueIssue | None:
    penalty = _as_float(metrics.get("debug_material_preview_penalty"))
    if penalty <= _DEBUG_MATERIAL_THRESHOLD:
        return None
    evidence_view = "quality_diagnostics"
    recommendation = (
        "Final preview reads as debug-material colors; "
        "richer surface authoring needed."
    )
    rationale = (
        f"debug_material_preview_penalty={penalty:.3f} exceeds threshold "
        f"{_DEBUG_MATERIAL_THRESHOLD:.2f}"
    )
    patches = (
        PatchProposal(
            target="design_brief",
            field="design_brief.material_age",
            operation="set",
            current_value=brief.get("material_age"),
            proposed_value="aged",
            rationale=rationale,
        ),
        PatchProposal(
            target="design_brief",
            field="design_brief.wear",
            operation="set",
            current_value=brief.get("wear"),
            proposed_value="medium_edge_wear",
            rationale=rationale,
        ),
    )
    return CritiqueIssue(
        issue_id=_issue_id(evidence_view, recommendation),
        severity=_SEVERITY_WARNING,
        evidence_view=evidence_view,
        recommendation=recommendation,
        patch_proposals=patches,
    )


def _stub_highlow_issue(
    metrics: dict[str, Any],
    brief: dict[str, Any],
) -> CritiqueIssue | None:
    penalty = _as_float(metrics.get("highlow_fake_detail_penalty"))
    if penalty <= _HIGHLOW_FAKE_THRESHOLD:
        return None
    evidence_view = "highlow_relation"
    recommendation = (
        "High/low distinction is weak; bake more meaningful detail "
        "into the runtime low-poly."
    )
    rationale = (
        f"highlow_fake_detail_penalty={penalty:.3f} exceeds threshold "
        f"{_HIGHLOW_FAKE_THRESHOLD:.2f}"
    )
    patches = (
        PatchProposal(
            target="design_brief",
            field="design_brief.detail_density",
            operation="set",
            current_value=brief.get("detail_density"),
            proposed_value="hero",
            rationale=rationale,
        ),
    )
    return CritiqueIssue(
        issue_id=_issue_id(evidence_view, recommendation),
        severity=_SEVERITY_WARNING,
        evidence_view=evidence_view,
        recommendation=recommendation,
        patch_proposals=patches,
    )


def _stub_random_triangulation_issue(
    metrics: dict[str, Any],
    brief: dict[str, Any],
) -> CritiqueIssue | None:
    penalty = _as_float(metrics.get("random_triangulation_penalty"))
    if penalty <= _RANDOM_TRIANGULATION_THRESHOLD:
        return None
    evidence_view = "quality_diagnostics"
    recommendation = (
        "Large flat faces split by noisy diagonal topology; "
        "introduce panel lines or controlled bevels."
    )
    rationale = (
        f"random_triangulation_penalty={penalty:.3f} exceeds threshold "
        f"{_RANDOM_TRIANGULATION_THRESHOLD:.2f}"
    )
    patches = (
        PatchProposal(
            target="shape_ir_v2",
            field="shape_ir_v2.ops.cut_panel_line",
            operation="add",
            current_value=None,
            proposed_value={"reason": "introduce_controlled_panel_break"},
            rationale=rationale,
        ),
        PatchProposal(
            target="design_brief",
            field="design_brief.shape_language",
            operation="set",
            current_value=brief.get("shape_language"),
            proposed_value="rectangular_with_45deg_cuts",
            rationale=rationale,
        ),
    )
    return CritiqueIssue(
        issue_id=_issue_id(evidence_view, recommendation),
        severity=_SEVERITY_WARNING,
        evidence_view=evidence_view,
        recommendation=recommendation,
        patch_proposals=patches,
    )


def _stub_family_grammar_issue(
    grammar: dict[str, Any],
) -> CritiqueIssue | None:
    if not grammar:
        return None
    coverage_value = grammar.get("coverage")
    try:
        coverage = float(coverage_value)
    except (TypeError, ValueError):
        return None
    if coverage >= _FAMILY_GRAMMAR_COVERAGE_THRESHOLD:
        return None
    evidence_view = "family_grammar"
    recommendation = (
        "Family grammar coverage below 0.70; missing required parts."
    )
    rationale = (
        f"family_grammar.coverage={coverage:.3f} below threshold "
        f"{_FAMILY_GRAMMAR_COVERAGE_THRESHOLD:.2f}"
    )
    missing_names = _missing_requirement_names(grammar)
    patches = (
        PatchProposal(
            target="family_grammar",
            field="family_grammar.missing_requirements",
            operation="add",
            current_value=None,
            proposed_value=missing_names,
            rationale=rationale,
        ),
    )
    return CritiqueIssue(
        issue_id=_issue_id(evidence_view, recommendation),
        severity=_SEVERITY_WARNING,
        evidence_view=evidence_view,
        recommendation=recommendation,
        patch_proposals=patches,
    )


def _stub_material_wear_issue(
    uniform_noise: dict[str, Any],
    brief: dict[str, Any],
) -> CritiqueIssue | None:
    if not uniform_noise:
        return None
    if not bool(uniform_noise.get("is_uniform_noise")):
        return None
    evidence_view = "material_wear_graph"
    recommendation = (
        "Material/wear graph is uniform noise; bind masks to construction nodes."
    )
    rationale = (
        f"is_uniform_noise=True (uniform_noise_score="
        f"{_as_float(uniform_noise.get('uniform_noise_score')):.3f})"
    )
    patches = (
        PatchProposal(
            target="design_brief",
            field="design_brief.wear",
            operation="set",
            current_value=brief.get("wear"),
            proposed_value="medium_edge_wear",
            rationale=rationale,
        ),
    )
    return CritiqueIssue(
        issue_id=_issue_id(evidence_view, recommendation),
        severity=_SEVERITY_WARNING,
        evidence_view=evidence_view,
        recommendation=recommendation,
        patch_proposals=patches,
    )


def _stub_preview_evidence_issue(
    summary: dict[str, Any],
    brief: dict[str, Any],
) -> CritiqueIssue | None:
    if not summary:
        return None
    distinct = summary.get("distinct_final_from_material_ids")
    if distinct is True:
        return None
    if not summary.get("material_ids_present", False) and not summary.get(
        "final_beauty_present", False
    ):
        # No previews requested at all — Phase 9 already handles this
        # via skipped reasons; do not synthesise a Phase 10 issue.
        return None
    evidence_view = "preview_evidence"
    recommendation = (
        "No distinct final beauty preview; ensure 'turntable' is in package.previews."
    )
    rationale = "preview_summary.distinct_final_from_material_ids is False"
    current_constraints = brief.get("negative_constraints")
    if not isinstance(current_constraints, list | tuple):
        current_constraints_dict_value: list[str] = []
    else:
        current_constraints_dict_value = [
            entry for entry in current_constraints if isinstance(entry, str)
        ]
    patches = (
        PatchProposal(
            target="design_brief",
            field="design_brief.negative_constraints",
            operation="add",
            current_value=current_constraints_dict_value,
            proposed_value="missing_final_beauty_preview",
            rationale=rationale,
        ),
    )
    return CritiqueIssue(
        issue_id=_issue_id(evidence_view, recommendation),
        severity=_SEVERITY_WARNING,
        evidence_view=evidence_view,
        recommendation=recommendation,
        patch_proposals=patches,
    )


def _run_deterministic_stub(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> tuple[CritiqueIssue, ...]:
    """Synthesise critique issues from Phase 1-9 evidence views.

    Pure function: reads ``runtime`` only, no I/O, no clock. The
    six emit-or-skip checks below are idempotent — feeding the same
    runtime always produces the same set of issues in the same
    order.
    """
    metrics = _quality_diagnostics_metrics(runtime)
    grammar = _family_grammar_evidence(runtime)
    uniform_noise = _material_wear_uniform_noise(runtime)
    preview_summary_value = _preview_summary(runtime)
    brief = _design_brief_brief(runtime)
    if not brief:
        # Some test fixtures publish ``runtime["design_brief"]`` as the
        # brief dict directly rather than under ``["brief"]``. Tolerate
        # both shapes so the stub remains robust.
        candidate = _as_dict(runtime.get("design_brief"))
        if "negative_constraints" in candidate or "wear" in candidate:
            brief = candidate

    issues: list[CritiqueIssue] = []
    candidates = (
        _stub_debug_material_issue(metrics, brief),
        _stub_highlow_issue(metrics, brief),
        _stub_random_triangulation_issue(metrics, brief),
        _stub_family_grammar_issue(grammar),
        _stub_material_wear_issue(uniform_noise, brief),
        _stub_preview_evidence_issue(preview_summary_value, brief),
    )
    for issue in candidates:
        if issue is not None:
            issues.append(issue)
    return tuple(issues)


# ---------------------------------------------------------------------------
# External vision provider hook
# ---------------------------------------------------------------------------


class _ExternalVisionProvider:
    """Base class for external vision providers.

    Phase 10 ships a single registered subclass —
    :class:`_MockHttpVisionProvider` — that always raises
    ``ConnectionError``. Real provider integration is reserved for
    forward phases. The registry is documented so reviewers can see
    exactly which provider ids resolve.
    """

    name: str = "external_vision_provider"
    version: str = "v0"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = dict(config)

    def critique(
        self, asset: dict[str, Any], runtime: dict[str, Any]
    ) -> tuple[CritiqueIssue, ...]:
        raise NotImplementedError


class _MockHttpVisionProvider(_ExternalVisionProvider):
    """Stub external provider that always raises ``ConnectionError``.

    Phase 10 does NOT call any real external service. The mock
    provider exists so the unavailable-path test can verify the
    structured ``vision_provider_unavailable`` skipped reason fires
    end-to-end. Real HTTP / RPC integration belongs in a forward
    phase that goes through the full network-egress security review.
    """

    name = "mock_http_vision_provider"
    version = "v0"

    def critique(
        self, asset: dict[str, Any], runtime: dict[str, Any]
    ) -> tuple[CritiqueIssue, ...]:
        raise ConnectionError(
            "mock_http_vision_provider intentionally raises in Phase 10"
        )


_PROVIDER_REGISTRY: dict[str, Callable[[dict[str, Any]], _ExternalVisionProvider]] = {
    "mock_http_vision_provider": _MockHttpVisionProvider,
}


def _resolve_provider(
    config: dict[str, Any],
    asset: dict[str, Any],
    runtime: dict[str, Any],
) -> tuple[
    CritiqueProvider,
    tuple[CritiqueIssue, ...],
    list[SkippedReason],
]:
    """Resolve the external vision provider, falling back to the stub.

    Returns ``(provider_record, external_issues, skipped_reasons)``.
    The deterministic stub is ALWAYS the source of truth for the
    issue list — when an external provider is configured and
    succeeds, the external issues join the stub issues. When the
    provider is unavailable, the stub still runs and a structured
    skipped reason captures the failure.
    """
    skipped_reasons: list[SkippedReason] = []
    enabled = bool(config.get("enabled", False)) if isinstance(config, dict) else False
    if not enabled:
        skipped_reasons.append(
            SkippedReason("vision_provider", "vision_provider_not_configured")
        )
        return (
            CritiqueProvider(
                name=_DETERMINISTIC_STUB_NAME,
                version=_DETERMINISTIC_STUB_VERSION,
                configured=False,
            ),
            (),
            skipped_reasons,
        )

    provider_id = config.get("provider")
    if not isinstance(provider_id, str) or not provider_id:
        skipped_reasons.append(
            SkippedReason("vision_provider", "vision_provider_misconfigured")
        )
        return (
            CritiqueProvider(
                name=_DETERMINISTIC_STUB_NAME,
                version=_DETERMINISTIC_STUB_VERSION,
                configured=False,
            ),
            (),
            skipped_reasons,
        )

    factory = _PROVIDER_REGISTRY.get(provider_id)
    if factory is None:
        skipped_reasons.append(
            SkippedReason("vision_provider", "vision_provider_unknown")
        )
        return (
            CritiqueProvider(
                name=_DETERMINISTIC_STUB_NAME,
                version=_DETERMINISTIC_STUB_VERSION,
                configured=False,
            ),
            (),
            skipped_reasons,
        )

    try:
        provider = factory(config)
        external_issues = provider.critique(asset, runtime)
    except (ConnectionError, TimeoutError, OSError):
        skipped_reasons.append(
            SkippedReason("vision_provider", "vision_provider_unavailable")
        )
        return (
            CritiqueProvider(
                name=_DETERMINISTIC_STUB_NAME,
                version=_DETERMINISTIC_STUB_VERSION,
                configured=False,
            ),
            (),
            skipped_reasons,
        )

    if not isinstance(external_issues, tuple):
        external_issues = tuple(external_issues or ())
    return (
        CritiqueProvider(
            name=str(getattr(provider, "name", provider_id)),
            version=str(getattr(provider, "version", "v0")),
            configured=True,
        ),
        external_issues,
        skipped_reasons,
    )


# ---------------------------------------------------------------------------
# Patch validation
# ---------------------------------------------------------------------------


def _validate_patch(
    patch: PatchProposal,
) -> tuple[bool, str | None]:
    """Validate a single patch proposal.

    Returns ``(approved, reason_token)``. When ``approved`` is True
    ``reason_token`` is None. When False, ``reason_token`` is one of
    the structured tokens documented in the module docstring.
    """
    if patch.target not in _VALID_PATCH_TARGETS:
        return False, "invalid_target"
    if patch.operation not in _VALID_PATCH_OPERATIONS:
        return False, "invalid_operation"
    if not isinstance(patch.field, str) or not patch.field:
        return False, "field_path_malformed"
    if not patch.field.startswith(f"{patch.target}."):
        return False, "field_path_malformed"
    field_segments = [segment for segment in patch.field.split(".") if segment]
    if len(field_segments) < 2:
        return False, "field_path_malformed"
    if _SHAPE_CONTRACT_TOKEN in patch.field:
        return False, "touches_shape_contract"
    if any(segment in _PUBLIC_SURFACE_TOKENS for segment in field_segments):
        return False, "touches_public_surface"
    if not _is_json_serializable(patch.proposed_value):
        return False, "non_serializable_value"
    return True, None


def _validate_patches(
    issues: tuple[CritiqueIssue, ...],
) -> dict[str, Any]:
    """Validate every patch attached to every issue.

    Returns the ``patch_validation`` payload sub-block with
    ``all_patches_valid``, ``approved_count``, ``rejected_count``,
    and ``rejections`` (list of structured rejection records). Each
    rejection carries ``issue_id``, ``field``, and ``reason``.
    """
    approved_count = 0
    rejected_count = 0
    rejections: list[dict[str, Any]] = []
    for issue in issues:
        for patch in issue.patch_proposals:
            approved, reason = _validate_patch(patch)
            if approved:
                approved_count += 1
            else:
                rejected_count += 1
                rejections.append(
                    {
                        "issue_id": issue.issue_id,
                        "field": patch.field,
                        "reason": reason or "unknown",
                    }
                )
    return {
        "all_patches_valid": rejected_count == 0,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "rejections": rejections,
    }


# ---------------------------------------------------------------------------
# Top-level evaluator
# ---------------------------------------------------------------------------


def _resolve_asset_name(asset: dict[str, Any]) -> str:
    name = asset.get("name")
    if isinstance(name, str) and name:
        return name
    return "unnamed_asset"


def _runtime_config(runtime: dict[str, Any]) -> dict[str, Any]:
    """Return the redacted runtime config the executor publishes.

    Reads ``runtime["_runtime_config"]`` first (the canonical
    Phase 10 wiring published by the executor before validate runs)
    and falls back to ``runtime.get("config", {})`` and
    ``runtime.get("runtime_config", {})`` so unit-test harnesses that
    inject a config under either of those keys keep working.
    """
    for key in ("_runtime_config", "config", "runtime_config"):
        value = runtime.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _vision_critique_config(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_runtime_config(runtime).get("vision_critique"))


def _sort_issues(issues: tuple[CritiqueIssue, ...]) -> tuple[CritiqueIssue, ...]:
    return tuple(
        sorted(
            issues,
            key=lambda issue: (
                _SEVERITY_RANK.get(issue.severity, len(_SEVERITY_RANK)),
                issue.issue_id,
            ),
        )
    )


def _sort_skipped(records: list[SkippedReason]) -> list[SkippedReason]:
    return sorted(records, key=lambda record: (record.category, record.reason))


def _summary(
    issues: tuple[CritiqueIssue, ...], patch_validation: dict[str, Any]
) -> dict[str, Any]:
    severity_counts = {
        _SEVERITY_INFO: 0,
        _SEVERITY_WARNING: 0,
        _SEVERITY_ERROR: 0,
    }
    patch_count = 0
    for issue in issues:
        severity = issue.severity if issue.severity in severity_counts else _SEVERITY_INFO
        severity_counts[severity] += 1
        patch_count += len(issue.patch_proposals)
    return {
        "issue_count": len(issues),
        "issues_by_severity": dict(severity_counts),
        "patch_count": patch_count,
        "approved_patches": int(patch_validation.get("approved_count", 0)),
    }


def evaluate_vision_critique(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive Phase 10 vision-critique payload.

    Args:
        asset: normalized asset dict. Reads ``asset["name"]`` for
            the payload header; the deterministic stub does not
            otherwise read the asset, but the external vision
            provider hook receives the asset for forward-phase
            providers that need it.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["quality_diagnostics"]``,
            ``runtime["family_grammar"]``,
            ``runtime["material_wear_graph"]``,
            ``runtime["preview_evidence"]``,
            ``runtime["highlow_relation"]``, and
            ``runtime["design_brief"]`` — all populated by Phases 1
            through 9. Also reads ``runtime["_runtime_config"]`` (a
            redacted copy the executor publishes before validate
            runs) for the optional ``vision_critique`` provider
            block.

    Returns:
        Additive payload with ``version``
        (``"vision_critique_v1"``), ``asset_name``, ``provider``
        record, ordered ``issues`` list, ``patch_validation`` block,
        ``summary`` block, ``skipped_reasons`` list, ``warnings``
        list (always empty in Phase 10), and ``diagnostics`` list
        (always empty — Phase 10 is informational only and never
        blocks certification).
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}

    asset_name = _resolve_asset_name(safe_asset)
    config = _vision_critique_config(safe_runtime)
    provider, external_issues, skipped_reasons = _resolve_provider(
        config, safe_asset, safe_runtime
    )

    stub_issues = _run_deterministic_stub(safe_asset, safe_runtime)
    combined_issues = _sort_issues(tuple(stub_issues) + tuple(external_issues))

    patch_validation = _validate_patches(combined_issues)
    summary = _summary(combined_issues, patch_validation)
    skipped_payload = [record.to_dict() for record in _sort_skipped(skipped_reasons)]

    return {
        "version": VISION_CRITIQUE_VERSION,
        "asset_name": asset_name,
        "provider": provider.to_dict(),
        "issues": [issue.to_dict() for issue in combined_issues],
        "patch_validation": patch_validation,
        "summary": summary,
        "skipped_reasons": skipped_payload,
        "warnings": [],
        "diagnostics": [],
    }
