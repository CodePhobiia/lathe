"""Reference-driven palette / silhouette / frequency extraction.

Per northstar §10 Lane I priority task #6. When authors provide
reference imagery (moodboards, silhouette refs, material refs), the
Foundry extracts deterministic signatures used to:

  - Bias the generator's palette toward the reference;
  - Validate generated silhouettes against reference outlines;
  - Match high-frequency detail density.

This module declares the typed signature records + extraction
functions. The functions are deterministic stubs that consume
already-extracted feature vectors (typically produced by an
external vision pipeline). When no external pipeline is wired, the
stubs surface ``status: 'unbuilt'`` per the no-fake-quality rule.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

REFERENCE_EXTRACTION_VERSION = "lathe.asset_foundry.reference_extraction_v1"


@dataclass(frozen=True)
class ReferencePalette:
    """Extracted palette signature."""

    palette_id: str
    dominant_colors_hex: tuple[str, ...]
    """Sorted from most-frequent first."""
    frequency_weights: tuple[float, ...]
    """Aligned with ``dominant_colors_hex``; sums to ~1."""
    extraction_method: str
    """``kmeans`` | ``provided`` | ``stub_unbuilt``."""
    extraction_status: str = "real"
    extraction_status_reason: str = ""


@dataclass(frozen=True)
class ReferenceSilhouette:
    """Extracted silhouette signature."""

    silhouette_id: str
    polyline_points_normalized: tuple[tuple[float, float], ...]
    """Outline polyline in [0,1] image space, CCW from outside."""
    aspect_ratio: float
    extraction_method: str
    extraction_status: str = "real"
    extraction_status_reason: str = ""


@dataclass(frozen=True)
class ReferenceFrequencySignature:
    """Extracted frequency-energy signature.

    A 1D vector indexed by spatial-frequency band. Each entry is the
    normalized energy in that band. Lower bands = large form;
    middle bands = trim/panels; high bands = fasteners + decals.
    """

    signature_id: str
    energy_per_band: tuple[float, ...]
    band_count: int
    extraction_method: str
    extraction_status: str = "real"
    extraction_status_reason: str = ""


@dataclass(frozen=True)
class ReferenceBoard:
    """A complete reference board with palette + silhouette + frequency."""

    board_id: str
    palette: ReferencePalette | None = None
    silhouettes: tuple[ReferenceSilhouette, ...] = ()
    frequency_signatures: tuple[ReferenceFrequencySignature, ...] = ()
    negative_examples: tuple[str, ...] = ()


def extract_palette_signature(
    *,
    palette_id: str,
    provided_colors_hex: Sequence[str] | None = None,
    provided_weights: Sequence[float] | None = None,
) -> ReferencePalette:
    """Build a ReferencePalette from already-extracted color counts.

    When ``provided_colors_hex`` is None, returns ``status: 'unbuilt'``
    rather than fabricating values.
    """
    if not provided_colors_hex:
        return ReferencePalette(
            palette_id=palette_id,
            dominant_colors_hex=(),
            frequency_weights=(),
            extraction_method="stub_unbuilt",
            extraction_status="unbuilt",
            extraction_status_reason="no_provided_colors",
        )
    if provided_weights is None:
        weights = tuple(1.0 / len(provided_colors_hex) for _ in provided_colors_hex)
    else:
        if len(provided_weights) != len(provided_colors_hex):
            raise ValueError(
                "provided_weights length must equal provided_colors_hex length"
            )
        weights_total = sum(provided_weights) or 1.0
        weights = tuple(w / weights_total for w in provided_weights)
    # Sort by weight descending.
    pairs = sorted(zip(provided_colors_hex, weights), key=lambda p: -p[1])
    return ReferencePalette(
        palette_id=palette_id,
        dominant_colors_hex=tuple(p[0] for p in pairs),
        frequency_weights=tuple(p[1] for p in pairs),
        extraction_method="provided",
    )


def extract_silhouette_signature(
    *,
    silhouette_id: str,
    provided_outline: Sequence[tuple[float, float]] | None = None,
) -> ReferenceSilhouette:
    """Build a ReferenceSilhouette from a provided normalized outline."""
    if not provided_outline or len(provided_outline) < 3:
        return ReferenceSilhouette(
            silhouette_id=silhouette_id,
            polyline_points_normalized=(),
            aspect_ratio=1.0,
            extraction_method="stub_unbuilt",
            extraction_status="unbuilt",
            extraction_status_reason="outline_too_short_or_missing",
        )
    xs = [p[0] for p in provided_outline]
    ys = [p[1] for p in provided_outline]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    aspect_ratio = (dx / dy) if dy > 1e-9 else 1.0
    return ReferenceSilhouette(
        silhouette_id=silhouette_id,
        polyline_points_normalized=tuple((p[0], p[1]) for p in provided_outline),
        aspect_ratio=aspect_ratio,
        extraction_method="provided",
    )


def extract_frequency_signature(
    *,
    signature_id: str,
    provided_energy_per_band: Sequence[float] | None = None,
    band_count: int = 8,
) -> ReferenceFrequencySignature:
    """Build a ReferenceFrequencySignature from energy-per-band values."""
    if not provided_energy_per_band:
        return ReferenceFrequencySignature(
            signature_id=signature_id,
            energy_per_band=(),
            band_count=band_count,
            extraction_method="stub_unbuilt",
            extraction_status="unbuilt",
            extraction_status_reason="no_provided_energy_per_band",
        )
    total = sum(provided_energy_per_band) or 1.0
    normalized = tuple(e / total for e in provided_energy_per_band)
    return ReferenceFrequencySignature(
        signature_id=signature_id,
        energy_per_band=normalized,
        band_count=len(normalized),
        extraction_method="provided",
    )


__all__ = [
    "REFERENCE_EXTRACTION_VERSION",
    "ReferenceBoard",
    "ReferenceFrequencySignature",
    "ReferencePalette",
    "ReferenceSilhouette",
    "extract_frequency_signature",
    "extract_palette_signature",
    "extract_silhouette_signature",
]
