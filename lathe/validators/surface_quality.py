"""Surface-quality validator.

Scores V1.2 surface-stage evidence (atlas coverage, decal integrity,
mask program legality) from the backend report.
"""

from __future__ import annotations

from typing import Any

from .visual_quality import _surface_evidence

SURFACE_THRESHOLDS = {
    "surface_authoring_quality": 0.40,
    "surface_material_zone_coherence": 0.45,
    "surface_normal_richness": 0.12,
    "surface_roughness_variation": 0.08,
    "surface_texture_entropy": 0.20,
    "surface_bake_cleanliness": 0.12,
}


def build_surface_validation_ir(
    surface_cfg: dict[str, Any], backend_report: dict[str, Any]
) -> dict[str, Any]:
    """Build surface validation ir.

    Args:
        surface_cfg: surface_cfg argument.
        backend_report: backend_report argument.

    Returns:
        The result.
    """
    return {
        "schema": "lathe.surface_validation_ir.v1",
        "backend": backend_report["selected_backend_id"],
        "evidence_metrics": [
            "surface_authoring_quality",
            "material_zone_coherence",
            "seam_continuity",
            "padding_safety",
            "normal_richness",
            "roughness_variation",
            "texture_entropy",
            "decal_coherence",
            "trim_coherence",
            "mip_safety",
            "bake_alignment_quality",
            "surface_render_plausibility",
        ],
        "required_maps": list(surface_cfg.get("maps", [])),
    }


def evaluate_surface_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Evaluate surface quality.

    Args:
        asset: asset argument.
        runtime: runtime argument.

    Returns:
        The result.
    """
    bundle = runtime.get("surface", {}).get("bundle", {})
    metrics = _surface_evidence(runtime, bundle)
    diagnostics: list[dict[str, Any]] = []
    for metric, minimum in SURFACE_THRESHOLDS.items():
        actual = float(metrics.get(metric, 0.0))
        if actual < minimum:
            diagnostics.append(
                {
                    "code": f"L65{len(diagnostics) + 1:02d}",
                    "name": f"surface_{metric}_failed",
                    "severity": "error",
                    "phase": "validate",
                    "asset": asset["name"],
                    "stage": "surface",
                    "path": f"validate.surface.{metric}",
                    "message": f"Surface validator failed for {metric}: {actual:.3f} < {minimum:.3f}",
                    "details": {"metric": metric, "actual": actual, "minimum": minimum},
                    "suggested_repairs": [
                        "reauthor_surface_layer",
                        "rederive_zone_roughness",
                        "fallback_zone_deterministic",
                    ],
                }
            )
    return {
        "schema": "lathe.surface_quality_report.v1",
        "asset": asset["name"],
        "metrics": metrics,
        "thresholds": SURFACE_THRESHOLDS,
        "diagnostics": diagnostics,
        "ok": not diagnostics,
    }
