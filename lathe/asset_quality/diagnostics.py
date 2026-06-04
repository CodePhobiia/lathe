"""Phase 1 deterministic asset-quality diagnostics.

Adds a complementary diagnostic layer on top of the existing
``visual_quality`` validator. Detects prototype-look failure modes that
pass technical certification but still read as blockout-quality geometry
to a human reviewer. All metrics are deterministic proxies synthesized
from existing runtime data — no images, no external services, no
Blender / Roblox dependencies.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 13.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Section 1.
Per-metric reference: ``docs/asset-quality/quality-diagnostics-v1.md``.

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` after ``visual_quality`` so that
``runtime["visual_quality"]`` is populated when this validator runs
(see ``lathe/validators/composition.py:287-291`` for the propagation).

Output additively appears under the top-level ``quality_diagnostics``
key of the validate-stage report. Existing report fields are preserved
and the validator never produces blocking diagnostics at Phase 1
(per tasklist Section 1.2 ``severity`` note).
"""

from __future__ import annotations

from typing import Any

from ..repair_planner import suggest_repairs_for_metric
from ..validators.render_class import evaluate_render_class_validators
from .highlow_relation import is_highlow_required

VERSION = "asset_quality_diagnostics_v1"

_RANDOM_TRI_WARN = 0.30
_DEBUG_MATERIAL_WARN = 0.50
_HIGHLOW_FAKE_WARN = 0.40
_ATTACHMENT_SEATING_WARN = 0.50
_HIERARCHY_BALANCE_WARN = 0.50
_FAMILY_GRAMMAR_COVERAGE_WARN = 0.50


_RECOMMENDATIONS: dict[str, str] = {
    "random_triangulation_penalty": (
        "Add controlled panel lines, bevels, or simplified topology on large "
        "flat faces. Avoid arbitrary diagonal triangulation."
    ),
    "debug_material_preview_penalty": (
        "Replace flat material-ID look with authored PBR — vary roughness, "
        "add albedo storytelling (paint chips, dirt), use a richer normal "
        "map."
    ),
    "highlow_fake_detail_penalty": (
        "Add a real high-poly source (bevels, embossed detail, chamfered "
        "edges) and bake to the runtime low-poly's normal/AO/curvature "
        "maps. If hero mode is intended, opt into the Phase 7 high-poly "
        "producer."
    ),
    "attachment_seating_quality": (
        "Seat attachments (handles, hinges, latches, panels) into sockets, "
        "brackets, mount plates, or recessed insets rather than placing "
        "them as separate primitives on top of the body."
    ),
    "primary_secondary_tertiary_balance": (
        "Add medium-scale construction features — frames, rails, corner "
        "guards, panel breaks, trim — between the primary body and "
        "tertiary details so the asset reads as designed rather than "
        "blockout."
    ),
    "family_grammar_coverage": (
        "Add the family-grammar requirements flagged in the "
        "family_grammar.requirement_results section — see the "
        "recommendations there for specifics."
    ),
}

_CLASS_ANCHOR_METRIC_BY_EVIDENCE: dict[str, str] = {
    "bounded_volume_present": "hard_surface_class_anchor_bounded_volume",
    "vertical_panel_present": "hard_surface_class_anchor_bounded_volume",
    "panel_breakup_present": "hard_surface_class_anchor_panel_breakup",
    "frame_or_panel_breakup_present": "hard_surface_class_anchor_panel_breakup",
    "corner_reinforcement_present": "hard_surface_class_anchor_corner_reinforcement",
    "lid_seam_or_trim_present": "hard_surface_class_anchor_access_seam",
    "hinge_present": "hard_surface_class_anchor_access_seam",
    "handle_present": "hard_surface_class_anchor_fastener_trim_detail",
    "handles_or_latch_present": "hard_surface_class_anchor_fastener_trim_detail",
    "lock_plate_or_latch_present": "hard_surface_class_anchor_fastener_trim_detail",
    "material_separation": "hard_surface_class_anchor_material_separation",
    "scale_plausibility_crate": "hard_surface_class_anchor_scale_plausibility",
    "scale_plausibility_door": "hard_surface_class_anchor_scale_plausibility",
    "non_trivial_silhouette": "hard_surface_class_anchor_silhouette",
    "face_count_sufficient": "hard_surface_class_anchor_face_count",
}

_CLASS_ANCHOR_RECOMMENDATIONS: dict[str, str] = {
    "hard_surface_class_anchor_bounded_volume": (
        "Refit the primary bounded volume so the asset has a readable hard-surface body "
        "before detail scoring is trusted."
    ),
    "hard_surface_class_anchor_panel_breakup": (
        "Add visible panel breakup, trim bands, or inset frames tied to semantic parts."
    ),
    "hard_surface_class_anchor_corner_reinforcement": (
        "Add corner guards, brackets, or reinforced edge features so the container reads as built."
    ),
    "hard_surface_class_anchor_access_seam": (
        "Add a visible lid, door, hinge, or access seam rather than leaving the shell monolithic."
    ),
    "hard_surface_class_anchor_material_separation": (
        "Assign distinct body and trim material zones and make the separation visible in the surface bundle."
    ),
    "hard_surface_class_anchor_fastener_trim_detail": (
        "Add handles, latches, fastener strips, or trim detail with semantic provenance."
    ),
    "hard_surface_class_anchor_scale_plausibility": (
        "Refit proportions to the class rubric's expected physical scale envelope."
    ),
    "hard_surface_class_anchor_silhouette": (
        "Add secondary features or silhouette breaks so the asset is not a featureless block."
    ),
    "hard_surface_class_anchor_face_count": (
        "Add real geometric detail where the class rubric expects more than blockout density."
    ),
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _shape_assessment(runtime: dict[str, Any]) -> dict[str, Any]:
    shape_bundle = _as_dict(_as_dict(runtime.get("shape")).get("bundle"))
    direct = _as_dict(shape_bundle.get("shape_assessment"))
    if direct:
        return direct
    scaffold_report = _as_dict(shape_bundle.get("scaffold_report"))
    return _as_dict(scaffold_report.get("shape_assessment"))


def _visual_metrics(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("visual_quality")).get("metrics"))


def _family_grammar_coverage(runtime: dict[str, Any]) -> tuple[float, bool]:
    """Return ``(coverage, evidence_present)`` from runtime.

    When the family_grammar validator has not run (or no ``coverage``
    field is present), evidence_present is ``False`` and coverage
    defaults to ``1.0`` so no warning fires. When evidence is present
    but malformed, the default also remains ``1.0`` and the boolean
    stays ``False`` so the warning is suppressed.
    """
    family_grammar = runtime.get("family_grammar")
    if not isinstance(family_grammar, dict):
        return 1.0, False
    coverage = family_grammar.get("coverage")
    try:
        return float(coverage), True
    except (TypeError, ValueError):
        return 1.0, False


def _random_triangulation_penalty(visual_metrics: dict[str, Any]) -> float:
    tiny = _as_float(visual_metrics.get("geometry_tiny_face_penalty"))
    stair = _as_float(visual_metrics.get("geometry_stair_step_penalty"))
    boolean_scar = _as_float(visual_metrics.get("boolean_scar_penalty"))
    return round(min(1.0, 0.45 * tiny + 0.30 * stair + 0.25 * boolean_scar), 6)


def _debug_material_preview_penalty(visual_metrics: dict[str, Any]) -> float:
    texture_e = _as_float(visual_metrics.get("texture_entropy"))
    roughness_v = _as_float(visual_metrics.get("roughness_variation"))
    chroma_v = _as_float(
        visual_metrics.get("surface_chroma_variation"),
        default=texture_e,
    )
    return round(
        min(
            1.0,
            0.40 * max(0.0, 1.0 - texture_e)
            + 0.35 * max(0.0, 1.0 - roughness_v)
            + 0.25 * max(0.0, 1.0 - chroma_v),
        ),
        6,
    )


def _highlow_fake_detail_penalty(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    """Compute the prototype-look penalty for the high/low relation.

    When Phase 7's ``runtime["highlow_relation"]`` evidence is present
    the penalty is sourced from the strengthened ``realness_score`` —
    ``penalty = 1.0 - realness_score``. The Phase 7 score consumes
    distinct URIs, triangle delta, bake-map completeness, and manifest
    quality so a "hidden fake" with distinct URIs but identical maps
    is no longer credited as real.

    When that evidence is absent (e.g. legacy callers, unit tests that
    mock only the surface bundle), the function falls back to the
    Phase 1 heuristic over the surface bundle's ``highlow_relation``
    record so the metric stays defined at every callsite.
    """
    highlow_evidence = runtime.get("highlow_relation")
    if isinstance(highlow_evidence, dict) and "realness_score" in highlow_evidence:
        if highlow_evidence.get("required") is False:
            return 0.0
        realness_score = _as_float(highlow_evidence.get("realness_score"))
        penalty = 1.0 - max(0.0, min(1.0, realness_score))
        return round(max(0.0, min(1.0, penalty)), 6)
    if not is_highlow_required(asset, runtime):
        return 0.0
    surface_bundle = _as_dict(_as_dict(runtime.get("surface")).get("bundle"))
    highlow = _as_dict(surface_bundle.get("highlow_relation"))
    high_uri = highlow.get("high_mesh_uri")
    low_uri = highlow.get("low_mesh_uri")
    distinct_uris = bool(high_uri and low_uri and high_uri != low_uri)
    high_triangles = _as_float(highlow.get("high_triangle_count"))
    low_triangles = _as_float(highlow.get("low_triangle_count"))
    if high_triangles > low_triangles >= 0.0:
        triangle_delta = (high_triangles - low_triangles) / max(1.0, high_triangles)
    else:
        triangle_delta = 0.0
    realness = min(
        1.0,
        (0.45 if distinct_uris else 0.0) + min(0.55, triangle_delta / 0.18),
    )
    return round(max(0.0, 1.0 - realness), 6)


def _attachment_seating_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    intent = _as_dict(asset.get("intent"))
    parts_list = intent.get("parts") if isinstance(intent.get("parts"), list) else []
    parts = max(1, len(parts_list))
    shape_assessment = _shape_assessment(runtime)
    attach_count = _as_float(shape_assessment.get("attachment_region_count"))
    attach_coverage = min(1.0, attach_count / max(1.0, parts / 2.0))

    visual_metrics = _visual_metrics(runtime)
    integration = _as_float(visual_metrics.get("attachment_integration_quality"))
    feature_coherence = _as_float(visual_metrics.get("feature_coherence"))

    return round(
        min(1.0, 0.50 * attach_coverage + 0.30 * integration + 0.20 * feature_coherence),
        6,
    )


def _primary_secondary_tertiary_balance(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> float:
    intent = _as_dict(asset.get("intent"))
    parts_list = intent.get("parts") if isinstance(intent.get("parts"), list) else []
    parts = max(1, len(parts_list))
    shape_assessment = _shape_assessment(runtime)
    feature_count = int(_as_float(shape_assessment.get("feature_count")))
    secondary_count = max(0, feature_count - parts)
    secondary_coverage = min(1.0, secondary_count / max(2.0, parts * 1.5))

    visual_metrics = _visual_metrics(runtime)
    silhouette = _as_float(visual_metrics.get("silhouette_complexity"))
    detail = _as_float(visual_metrics.get("detail_density"))

    return round(
        min(1.0, 0.40 * secondary_coverage + 0.30 * silhouette + 0.30 * detail),
        6,
    )


def _repair_route_for_metric(metric: str, metrics: dict[str, Any]) -> dict[str, Any]:
    actions = suggest_repairs_for_metric(metric, metrics)
    if not actions:
        return {
            "executor": "",
            "target_ir": "",
            "actions": [],
            "status": "no_registered_repair_action",
        }
    if any(action in {"reauthor_surface_layer", "reselect_candidate", "regenerate_with_patch"} for action in actions):
        return {
            "executor": "lathe.repair_loop.run_repair_loop",
            "target_ir": "stage_bundle",
            "actions": actions,
            "status": "registered",
        }
    return {
        "executor": "lathe.repair_executor.execute_shape_repairs",
        "target_ir": "shape_ir",
        "actions": actions,
        "status": "registered",
    }


def _class_anchor_metric_for_evidence(evidence_key: str) -> str:
    return _CLASS_ANCHOR_METRIC_BY_EVIDENCE.get(
        evidence_key,
        f"hard_surface_class_anchor_{evidence_key}",
    )


def _class_anchor_warning_specs(
    runtime: dict[str, Any],
) -> tuple[dict[str, Any], list[tuple[str, str, str, dict[str, Any]]]]:
    """Return metrics + missing-evidence warnings from class_anchor evidence."""
    class_anchor = _as_dict(runtime.get("class_anchor"))
    class_metrics = _as_dict(class_anchor.get("metrics"))
    rubric_id = str(class_metrics.get("rubric_id") or "")
    if not rubric_id:
        return {}, []

    evidence = _as_dict(class_metrics.get("evidence"))
    severity_by_evidence = _as_dict(class_metrics.get("check_severity_by_evidence"))
    repair_by_evidence = _as_dict(class_metrics.get("repair_actions_by_evidence"))
    metrics: dict[str, Any] = {
        "hard_surface_class_anchor_score": _as_float(class_metrics.get("pass_fraction"), 1.0),
        "hard_surface_class_anchor_missing_required_count": int(
            _as_float(class_metrics.get("failed_required_count"), 0.0)
        ),
    }

    warning_specs: list[tuple[str, str, str, dict[str, Any]]] = []
    for evidence_key, raw_passed in sorted(evidence.items()):
        passed = bool(raw_passed)
        metric = _class_anchor_metric_for_evidence(str(evidence_key))
        metrics[metric] = 1.0 if passed else 0.0
        if passed:
            continue
        severity = str(severity_by_evidence.get(evidence_key) or "required")
        warning_text = (
            f"class anchor {rubric_id} missing {evidence_key} "
            f"(severity={severity})"
        )
        recommendation = _CLASS_ANCHOR_RECOMMENDATIONS.get(
            metric,
            "Add the missing class-anchor evidence through semantic construction, not mesh-only edits.",
        )
        details = {
            "rubric_id": rubric_id,
            "asset_kind": class_metrics.get("asset_kind"),
            "evidence_key": evidence_key,
            "required": severity == "required",
            "repair_action": repair_by_evidence.get(evidence_key),
            "source": "class_anchor",
        }
        warning_specs.append((metric, warning_text, recommendation, details))
    return metrics, warning_specs


def evaluate_quality_diagnostics(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate Phase 1 deterministic asset-quality diagnostics.

    Args:
        asset: normalized asset dict.
        runtime: stage-bundle runtime dict containing shape, topology,
            uv, surface, and (when run after ``visual_quality`` in the
            validator pipeline) ``visual_quality`` evidence.

    Returns:
        Additive payload with ``version``, ``metrics`` (6 floats —
        the 5 Phase 1 metrics plus the Phase 3 ``family_grammar_coverage``
        sourced from ``runtime["family_grammar"]``), ``warnings`` (list
        of strings), ``recommendations`` (list of strings), and
        ``findings`` (list of structured records carrying ``metric``,
        ``severity``, ``warning``, ``recommendation`` — index-aligned
        with ``warnings`` and ``recommendations``). No top-level
        ``diagnostics`` key — Phase 1 is informational only and never
        blocks certification pass/fail.
    """
    visual_metrics = _visual_metrics(runtime)
    family_grammar_coverage_value, family_grammar_evidence_present = (
        _family_grammar_coverage(runtime)
    )

    metrics = {
        "random_triangulation_penalty": _random_triangulation_penalty(visual_metrics),
        "debug_material_preview_penalty": _debug_material_preview_penalty(visual_metrics),
        "highlow_fake_detail_penalty": _highlow_fake_detail_penalty(asset, runtime),
        "attachment_seating_quality": _attachment_seating_quality(asset, runtime),
        "primary_secondary_tertiary_balance": _primary_secondary_tertiary_balance(
            asset, runtime
        ),
        "family_grammar_coverage": round(family_grammar_coverage_value, 6),
    }
    class_anchor_metrics, class_anchor_warning_specs = _class_anchor_warning_specs(runtime)
    metrics.update(class_anchor_metrics)

    warning_specs: list[tuple[str, bool, str]] = [
        (
            "random_triangulation_penalty",
            metrics["random_triangulation_penalty"] > _RANDOM_TRI_WARN,
            "large flat faces split by noisy diagonal topology "
            f"(random_triangulation_penalty={metrics['random_triangulation_penalty']:.3f})",
        ),
        (
            "debug_material_preview_penalty",
            metrics["debug_material_preview_penalty"] > _DEBUG_MATERIAL_WARN,
            "surface appears material-ID/debug colored rather than authored PBR "
            f"(debug_material_preview_penalty={metrics['debug_material_preview_penalty']:.3f})",
        ),
        (
            "highlow_fake_detail_penalty",
            metrics["highlow_fake_detail_penalty"] > _HIGHLOW_FAKE_WARN,
            "hero asset lacks meaningful high-poly/low-poly distinction "
            f"(highlow_fake_detail_penalty={metrics['highlow_fake_detail_penalty']:.3f})",
        ),
        (
            "attachment_seating_quality",
            metrics["attachment_seating_quality"] < _ATTACHMENT_SEATING_WARN,
            "attachments appear stuck-on or under-integrated "
            f"(attachment_seating_quality={metrics['attachment_seating_quality']:.3f})",
        ),
        (
            "primary_secondary_tertiary_balance",
            metrics["primary_secondary_tertiary_balance"] < _HIERARCHY_BALANCE_WARN,
            "asset lacks medium-scale construction hierarchy "
            f"(primary_secondary_tertiary_balance={metrics['primary_secondary_tertiary_balance']:.3f})",
        ),
        (
            "family_grammar_coverage",
            family_grammar_evidence_present
            and metrics["family_grammar_coverage"] < _FAMILY_GRAMMAR_COVERAGE_WARN,
            "family grammar coverage is below threshold "
            f"(family_grammar_coverage={metrics['family_grammar_coverage']:.3f})",
        ),
    ]

    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    repair_routes: list[dict[str, Any]] = []
    for metric, triggered, warning_text in warning_specs:
        if not triggered:
            continue
        recommendation = _RECOMMENDATIONS[metric]
        repair_route = _repair_route_for_metric(metric, metrics)
        warnings.append(warning_text)
        recommendations.append(recommendation)
        repair_routes.append({"metric": metric, **repair_route})
        findings.append(
            {
                "metric": metric,
                "severity": "warning",
                "warning": warning_text,
                "recommendation": recommendation,
                "repair_route": repair_route,
                "repair_actions": list(repair_route["actions"]),
            }
        )
    for metric, warning_text, recommendation, details in class_anchor_warning_specs:
        repair_route = _repair_route_for_metric(metric, metrics)
        warnings.append(warning_text)
        recommendations.append(recommendation)
        repair_routes.append({"metric": metric, **repair_route})
        findings.append(
            {
                "metric": metric,
                "severity": "warning",
                "warning": warning_text,
                "recommendation": recommendation,
                "details": details,
                "repair_route": repair_route,
                "repair_actions": list(repair_route["actions"]),
            }
        )

    render_class = evaluate_render_class_validators(asset, runtime)
    for child_name, child_score in render_class.get("metrics", {}).items():
        metrics[child_name] = round(float(child_score), 6)
    for finding in render_class.get("findings", []):
        findings.append(dict(finding))
        severity = str(finding.get("severity", "info"))
        status = str(finding.get("status", ""))
        # Renderer-unavailable findings are informational signals about the
        # build environment, not actionable warnings. Keep them visible in
        # ``findings`` (severity=info) but do not promote them into the
        # warning / recommendation streams that gate certification reviews.
        if severity != "warning" or status == "renderer_unavailable":
            continue
        warning_text = finding.get("warning")
        recommendation_text = finding.get("recommendation")
        if isinstance(warning_text, str) and warning_text:
            warnings.append(warning_text)
        if isinstance(recommendation_text, str) and recommendation_text:
            recommendations.append(recommendation_text)

    return {
        "version": VERSION,
        "metrics": metrics,
        "warnings": warnings,
        "recommendations": recommendations,
        "findings": findings,
        "repair_routes": repair_routes,
        "render_class_validators": render_class,
    }
