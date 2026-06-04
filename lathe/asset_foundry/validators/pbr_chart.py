"""PBR chart compliance validator.

Per northstar §10 Lane G later-tasks. Checks the per-material PBR
values against industry guidance (Frostbite / Substance / Unreal):

  - Dielectric basecolor must be in physically plausible sRGB
    range (no pure black, no super-saturated 100% values).
  - Metalness must be near 0 (dielectric) or near 1 (metal); no
    in-between.
  - Roughness must be > 0.05 (no perfect mirrors except glass).
  - Emissive must be tagged with intensity for HDR/non-HDR pipelines.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

PBR_CHART_COMPLIANCE_VERSION = "lathe.asset_foundry.pbr_chart_compliance_v1"


@dataclass(frozen=True)
class PbrChartReport:
    version: str
    asset_id: str
    materials_checked: int
    materials_compliant: int
    overall_compliance_score: float
    diagnostics: tuple[str, ...]


def _parse_hex(hex_str: str) -> tuple[float, float, float]:
    s = hex_str.lstrip("#")
    if len(s) != 6:
        return (0.5, 0.5, 0.5)
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return (r, g, b)


def _check_material(material: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Return (compliant, diagnostics)."""
    diagnostics: list[str] = []
    compliant = True

    base_color = material.get("base_color")
    metalness = material.get("metalness", 0.0)
    roughness = material.get("roughness", 0.5)

    if isinstance(base_color, str) and base_color.startswith("#"):
        r, g, b = _parse_hex(base_color)
        # Dielectric basecolor guard.
        if metalness < 0.1:
            if max(r, g, b) > 0.96:
                diagnostics.append(
                    f"dielectric_basecolor_too_bright: {base_color} (>0.96 in some channel)"
                )
                compliant = False
            if max(r, g, b) < 0.04:
                diagnostics.append(
                    f"dielectric_basecolor_too_dark: {base_color} (<0.04 in all channels)"
                )
                compliant = False
        # Metal basecolor guard.
        if metalness > 0.9:
            avg = (r + g + b) / 3.0
            if avg < 0.20:
                diagnostics.append(
                    f"metal_basecolor_too_dark: avg {avg:.3f} < 0.20"
                )
                compliant = False

    if not isinstance(metalness, (int, float)):
        diagnostics.append("metalness_missing_or_not_numeric")
        compliant = False
    elif 0.1 < metalness < 0.9:
        diagnostics.append(
            f"metalness_in_uncanny_valley: {metalness:.3f} should be near 0 or 1"
        )
        compliant = False

    if not isinstance(roughness, (int, float)):
        diagnostics.append("roughness_missing_or_not_numeric")
        compliant = False
    elif roughness < 0.05:
        diagnostics.append(
            f"roughness_too_smooth: {roughness:.3f} < 0.05 (mirror)"
        )
        compliant = False

    emission = material.get("emission")
    emission_color = material.get("emission_color")
    if emission is not None and emission_color is None:
        diagnostics.append("emission_intensity_without_color")
        compliant = False

    return compliant, diagnostics


def evaluate_pbr_chart_compliance(
    *,
    asset_id: str,
    materials: Sequence[Mapping[str, Any]],
) -> PbrChartReport:
    if not materials:
        return PbrChartReport(
            version=PBR_CHART_COMPLIANCE_VERSION,
            asset_id=asset_id,
            materials_checked=0,
            materials_compliant=0,
            overall_compliance_score=1.0,
            diagnostics=("no_materials_to_check",),
        )
    diagnostics: list[str] = []
    compliant_count = 0
    for i, mat in enumerate(materials):
        is_compliant, mat_diags = _check_material(mat)
        if is_compliant:
            compliant_count += 1
        for d in mat_diags:
            mat_id = mat.get("name") or f"material_{i:02d}"
            diagnostics.append(f"{mat_id}: {d}")
    score = compliant_count / len(materials)
    return PbrChartReport(
        version=PBR_CHART_COMPLIANCE_VERSION,
        asset_id=asset_id,
        materials_checked=len(materials),
        materials_compliant=compliant_count,
        overall_compliance_score=score,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "PBR_CHART_COMPLIANCE_VERSION",
    "PbrChartReport",
    "evaluate_pbr_chart_compliance",
]
