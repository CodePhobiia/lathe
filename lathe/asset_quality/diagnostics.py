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


VERSION = "asset_quality_diagnostics_v1"

_RANDOM_TRI_WARN = 0.30
_DEBUG_MATERIAL_WARN = 0.50
_HIGHLOW_FAKE_WARN = 0.40
_ATTACHMENT_SEATING_WARN = 0.50
_HIERARCHY_BALANCE_WARN = 0.50


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


def _random_triangulation_penalty(visual_metrics: dict[str, Any]) -> float:
    tiny = _as_float(visual_metrics.get("geometry_tiny_face_penalty"))
    stair = _as_float(visual_metrics.get("geometry_stair_step_penalty"))
    if not stair:
        stair = _as_float(visual_metrics.get("stair_step_penalty"))
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


def _highlow_fake_detail_penalty(runtime: dict[str, Any]) -> float:
    surface_bundle = _as_dict(_as_dict(runtime.get("surface")).get("bundle"))
    highlow = _as_dict(surface_bundle.get("highlow_relation"))
    high_uri = highlow.get("high_mesh_uri")
    low_uri = highlow.get("low_mesh_uri")
    distinct_uris = bool(high_uri and low_uri and high_uri != low_uri)
    high_triangles = _as_float(highlow.get("high_triangle_count"))
    low_triangles = _as_float(highlow.get("low_triangle_count"))
    if high_triangles > 0.0:
        triangle_delta = abs(high_triangles - low_triangles) / max(1.0, high_triangles)
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
        Additive payload with ``version``, ``metrics`` (5 floats),
        ``warnings`` (list of strings), and ``recommendations``
        (list of strings). No ``diagnostics`` key — Phase 1 is
        informational only and never blocks certification pass/fail.
    """
    visual_metrics = _visual_metrics(runtime)

    metrics = {
        "random_triangulation_penalty": _random_triangulation_penalty(visual_metrics),
        "debug_material_preview_penalty": _debug_material_preview_penalty(visual_metrics),
        "highlow_fake_detail_penalty": _highlow_fake_detail_penalty(runtime),
        "attachment_seating_quality": _attachment_seating_quality(asset, runtime),
        "primary_secondary_tertiary_balance": _primary_secondary_tertiary_balance(
            asset, runtime
        ),
    }

    warnings: list[str] = []
    recommendations: list[str] = []

    if metrics["random_triangulation_penalty"] > _RANDOM_TRI_WARN:
        warnings.append(
            "large flat faces split by noisy diagonal topology "
            f"(random_triangulation_penalty={metrics['random_triangulation_penalty']:.3f})"
        )
        recommendations.append(_RECOMMENDATIONS["random_triangulation_penalty"])

    if metrics["debug_material_preview_penalty"] > _DEBUG_MATERIAL_WARN:
        warnings.append(
            "surface appears material-ID/debug colored rather than authored PBR "
            f"(debug_material_preview_penalty={metrics['debug_material_preview_penalty']:.3f})"
        )
        recommendations.append(_RECOMMENDATIONS["debug_material_preview_penalty"])

    if metrics["highlow_fake_detail_penalty"] > _HIGHLOW_FAKE_WARN:
        warnings.append(
            "hero asset lacks meaningful high-poly/low-poly distinction "
            f"(highlow_fake_detail_penalty={metrics['highlow_fake_detail_penalty']:.3f})"
        )
        recommendations.append(_RECOMMENDATIONS["highlow_fake_detail_penalty"])

    if metrics["attachment_seating_quality"] < _ATTACHMENT_SEATING_WARN:
        warnings.append(
            "attachments appear stuck-on or under-integrated "
            f"(attachment_seating_quality={metrics['attachment_seating_quality']:.3f})"
        )
        recommendations.append(_RECOMMENDATIONS["attachment_seating_quality"])

    if metrics["primary_secondary_tertiary_balance"] < _HIERARCHY_BALANCE_WARN:
        warnings.append(
            "asset lacks medium-scale construction hierarchy "
            f"(primary_secondary_tertiary_balance={metrics['primary_secondary_tertiary_balance']:.3f})"
        )
        recommendations.append(_RECOMMENDATIONS["primary_secondary_tertiary_balance"])

    return {
        "version": VERSION,
        "metrics": metrics,
        "warnings": warnings,
        "recommendations": recommendations,
    }
