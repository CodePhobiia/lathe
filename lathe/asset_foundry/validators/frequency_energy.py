"""Frequency-energy validator.

Per northstar §10 Lane G later-tasks. Evaluates the per-band
frequency energy of an asset's silhouette / normal map / surface,
flagging assets whose energy is concentrated in the wrong bands for
their style.

For LowPolyFantasy assets, energy should sit in low + mid bands
(big silhouette + faceted facets) and stay sparse in high bands
(no microdetail). For PBR hard-surface, energy is balanced across
bands (primary/secondary/tertiary hierarchy).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

FREQUENCY_ENERGY_VERSION = "lathe.asset_foundry.frequency_energy_v1"


_STYLE_BAND_EXPECTATIONS: dict[str, tuple[float, ...]] = {
    "lowpoly_fantasy_sunset_crystal_v1": (0.35, 0.40, 0.20, 0.05),
    "hard_surface_pbr_v1": (0.25, 0.30, 0.30, 0.15),
    "default": (0.30, 0.30, 0.25, 0.15),
}


@dataclass(frozen=True)
class FrequencyEnergyReport:
    version: str
    asset_id: str
    style_pack_id: str
    band_count: int
    actual_energy_per_band: tuple[float, ...]
    expected_energy_per_band: tuple[float, ...]
    per_band_deviation: tuple[float, ...]
    """Absolute deviation per band."""
    worst_band_index: int
    worst_band_deviation: float
    overall_compliance_score: float
    """1 - mean(absolute_deviation). Higher = better."""
    diagnostics: tuple[str, ...]


def evaluate_frequency_energy(
    *,
    asset_id: str,
    style_pack_id: str,
    actual_energy_per_band: Sequence[float],
    expected_energy_per_band: Sequence[float] | None = None,
    deviation_threshold: float = 0.20,
) -> FrequencyEnergyReport:
    """Compare actual frequency energy to expected per style pack."""
    if expected_energy_per_band is None:
        expected_energy_per_band = _STYLE_BAND_EXPECTATIONS.get(
            style_pack_id, _STYLE_BAND_EXPECTATIONS["default"]
        )
    band_count = max(len(actual_energy_per_band), len(expected_energy_per_band))
    actual = list(actual_energy_per_band) + [0.0] * (band_count - len(actual_energy_per_band))
    expected = list(expected_energy_per_band) + [0.0] * (band_count - len(expected_energy_per_band))
    deviations = [abs(a - e) for a, e in zip(actual, expected)]
    worst_idx = max(range(band_count), key=lambda i: deviations[i])
    worst_dev = deviations[worst_idx]
    overall = max(0.0, 1.0 - sum(deviations) / max(1, band_count))
    diagnostics: list[str] = []
    for i, dev in enumerate(deviations):
        if dev > deviation_threshold:
            sign = "above" if actual[i] > expected[i] else "below"
            diagnostics.append(
                f"band_{i:02d}_deviation: actual {actual[i]:.3f} {sign} expected {expected[i]:.3f} (dev {dev:.3f})"
            )
    return FrequencyEnergyReport(
        version=FREQUENCY_ENERGY_VERSION,
        asset_id=asset_id,
        style_pack_id=style_pack_id,
        band_count=band_count,
        actual_energy_per_band=tuple(actual),
        expected_energy_per_band=tuple(expected),
        per_band_deviation=tuple(deviations),
        worst_band_index=worst_idx,
        worst_band_deviation=worst_dev,
        overall_compliance_score=overall,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "FREQUENCY_ENERGY_VERSION",
    "FrequencyEnergyReport",
    "evaluate_frequency_energy",
]
