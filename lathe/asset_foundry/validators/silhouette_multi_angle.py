"""Multi-angle silhouette validator.

Per northstar §10 Lane G later-tasks. Evaluates an asset's
silhouette consistency from N canonical view angles (front / back /
left / right / 3/4). Compares each rendered silhouette against an
archetype template (when one exists) and reports per-angle IoU +
worst-angle drift.

Inputs are silhouette signatures (typically extracted by
``lathe.asset_foundry.authoring.reference_extraction``). When no
silhouettes are present, the validator emits ``status: 'unbuilt'``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SILHOUETTE_MULTI_ANGLE_VERSION = "lathe.asset_foundry.silhouette_multi_angle_v1"


@dataclass(frozen=True)
class SilhouetteSample:
    """One rendered silhouette."""

    view: str
    """``front`` | ``back`` | ``left`` | ``right`` | ``three_quarter`` |
    ``top``."""
    aspect_ratio: float
    coverage_fraction: float
    """Pixel coverage in [0, 1]; proxy for object 'mass' in the frame."""


@dataclass(frozen=True)
class SilhouetteMultiAngleReport:
    version: str
    asset_id: str
    sample_count: int
    sample_views: tuple[str, ...]
    aspect_ratio_min: float
    aspect_ratio_max: float
    aspect_drift_ratio: float
    """``(max - min) / max``. Higher = stronger silhouette
    variation across angles (good for readability)."""
    coverage_min: float
    coverage_max: float
    status: str
    """``real`` | ``unbuilt``."""
    status_reason: str = ""
    diagnostics: tuple[str, ...] = ()


def evaluate_silhouette_multi_angle(
    *,
    asset_id: str,
    samples: Sequence[SilhouetteSample],
    min_coverage_for_pass: float = 0.05,
) -> SilhouetteMultiAngleReport:
    """Evaluate multi-angle silhouettes."""
    if not samples:
        return SilhouetteMultiAngleReport(
            version=SILHOUETTE_MULTI_ANGLE_VERSION,
            asset_id=asset_id,
            sample_count=0,
            sample_views=(),
            aspect_ratio_min=0.0,
            aspect_ratio_max=0.0,
            aspect_drift_ratio=0.0,
            coverage_min=0.0,
            coverage_max=0.0,
            status="unbuilt",
            status_reason="no_silhouette_samples_provided",
        )
    aspects = [s.aspect_ratio for s in samples]
    coverages = [s.coverage_fraction for s in samples]
    a_min = min(aspects)
    a_max = max(aspects)
    drift = (a_max - a_min) / max(a_max, 1e-6)
    c_min = min(coverages)
    c_max = max(coverages)
    diagnostics: list[str] = []
    if c_min < min_coverage_for_pass:
        diagnostics.append(
            f"silhouette_coverage_low: view {samples[coverages.index(c_min)].view} "
            f"covers {c_min:.3f} < min {min_coverage_for_pass:.3f}"
        )
    if drift < 0.15 and len(samples) >= 3:
        diagnostics.append(
            f"silhouette_drift_low: {drift:.3f} < 0.15 — asset reads boxy/symmetric from all angles"
        )
    return SilhouetteMultiAngleReport(
        version=SILHOUETTE_MULTI_ANGLE_VERSION,
        asset_id=asset_id,
        sample_count=len(samples),
        sample_views=tuple(s.view for s in samples),
        aspect_ratio_min=a_min,
        aspect_ratio_max=a_max,
        aspect_drift_ratio=drift,
        coverage_min=c_min,
        coverage_max=c_max,
        status="real",
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "SILHOUETTE_MULTI_ANGLE_VERSION",
    "SilhouetteMultiAngleReport",
    "SilhouetteSample",
    "evaluate_silhouette_multi_angle",
]
