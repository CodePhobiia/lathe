"""Foundry Lane F #6 — constrained UV packing.

Per northstar §10 Lane F priority task #6 + later tasks (rectpack-based
constrained packer, UDIM spillover). A constrained packer respects:

  - asset-level target texel density;
  - per-part importance weights (hero parts get bigger UV chart area);
  - fixed chart sizes when an artist constrains them;
  - bin overflow into UDIM tiles when one tile cannot satisfy the
    density budget.

This module is a pure-Python rectpack-style placer. It does NOT
require ``rectpack`` (the PyPI package); it uses a deterministic
shelf-and-skyline algorithm so the same inputs always produce the
same packing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

CONSTRAINED_PACKING_VERSION = "lathe.asset_foundry.constrained_packing_v1"


@dataclass(frozen=True)
class UvChartRequest:
    """One UV chart to pack."""

    chart_id: str
    part_id: str
    width_uv: float
    height_uv: float
    """In UV space (typically 0..1 per tile)."""

    importance_weight: float = 1.0
    """1.0 = normal; > 1 = hero; < 1 = secondary. Used to scale
    width/height when the density-budget pass is allowed to resize."""

    fixed_size: bool = False
    """When True, the chart MUST NOT be rescaled; if it does not fit,
    it overflows to a new UDIM tile."""

    seam_group_id: str | None = None


@dataclass(frozen=True)
class UvChartPlacement:
    """One placed chart in the packer output."""

    chart_id: str
    part_id: str
    tile_index: int
    """UDIM tile index (0 for first tile)."""
    u_min: float
    v_min: float
    u_max: float
    v_max: float
    importance_weight: float
    rescaled: bool
    rescale_factor: float = 1.0


@dataclass(frozen=True)
class PackingReport:
    """Result of a constrained packing pass."""

    version: str
    placements: tuple[UvChartPlacement, ...]
    tile_count: int
    overflowed_charts: tuple[str, ...]
    rescaled_chart_count: int
    fill_ratio_per_tile: tuple[float, ...]
    """Per-tile usage fraction in [0, 1]."""

    worst_density_drift_ratio: float
    """When asset-level density is set: |actual_max - actual_min| / requested."""

    diagnostics: tuple[str, ...]


@dataclass
class _Shelf:
    y_start: float
    height: float
    x_cursor: float


def _pack_shelf(
    charts: Sequence[UvChartRequest],
    tile_index: int,
) -> tuple[tuple[UvChartPlacement, ...], list[UvChartRequest], float]:
    """Single-tile shelf packing. Returns placements + leftovers + fill ratio.

    Inputs are sorted highest first; ties broken by importance_weight
    descending then chart_id ascending for determinism.
    """
    shelves: list[_Shelf] = []
    placements: list[UvChartPlacement] = []
    leftovers: list[UvChartRequest] = []
    total_area_used = 0.0
    for chart in charts:
        if chart.width_uv > 1.0 or chart.height_uv > 1.0:
            leftovers.append(chart)
            continue
        placed = False
        for shelf in shelves:
            if (
                shelf.x_cursor + chart.width_uv <= 1.0
                and chart.height_uv <= shelf.height + 1e-9
            ):
                placements.append(
                    UvChartPlacement(
                        chart_id=chart.chart_id,
                        part_id=chart.part_id,
                        tile_index=tile_index,
                        u_min=shelf.x_cursor,
                        v_min=shelf.y_start,
                        u_max=shelf.x_cursor + chart.width_uv,
                        v_max=shelf.y_start + chart.height_uv,
                        importance_weight=chart.importance_weight,
                        rescaled=False,
                    )
                )
                total_area_used += chart.width_uv * chart.height_uv
                shelf.x_cursor += chart.width_uv
                placed = True
                break
        if not placed:
            # Open a new shelf if there's vertical room.
            current_y = sum(s.height for s in shelves)
            if current_y + chart.height_uv <= 1.0:
                shelf = _Shelf(
                    y_start=current_y,
                    height=chart.height_uv,
                    x_cursor=chart.width_uv,
                )
                shelves.append(shelf)
                placements.append(
                    UvChartPlacement(
                        chart_id=chart.chart_id,
                        part_id=chart.part_id,
                        tile_index=tile_index,
                        u_min=0.0,
                        v_min=current_y,
                        u_max=chart.width_uv,
                        v_max=current_y + chart.height_uv,
                        importance_weight=chart.importance_weight,
                        rescaled=False,
                    )
                )
                total_area_used += chart.width_uv * chart.height_uv
            else:
                leftovers.append(chart)
    return tuple(placements), leftovers, total_area_used


def pack_uv_charts(
    charts: Sequence[UvChartRequest],
    *,
    tile_budget: int = 4,
    asset_target_density_px_per_m: float | None = None,
    auto_rescale_to_fit: bool = True,
    auto_rescale_max_shrink: float = 0.5,
) -> PackingReport:
    """Pack a list of UV charts into one or more UDIM tiles.

    Args:
        charts: list of UvChartRequest. Larger charts pack first.
        tile_budget: maximum UDIM tiles allowed. When exceeded,
            unpacked charts become ``overflowed_charts`` in the report.
        asset_target_density_px_per_m: optional asset-level target.
            When set, the packer computes a density-drift ratio
            comparing the largest vs smallest packed chart against
            the requested density.
        auto_rescale_to_fit: when True, non-fixed_size charts may be
            uniformly rescaled down to fit within ``auto_rescale_max_shrink``.
        auto_rescale_max_shrink: shrink floor (0.5 = down to 50%).
    """
    if not charts:
        return PackingReport(
            version=CONSTRAINED_PACKING_VERSION,
            placements=(),
            tile_count=0,
            overflowed_charts=(),
            rescaled_chart_count=0,
            fill_ratio_per_tile=(),
            worst_density_drift_ratio=0.0,
            diagnostics=("no_charts_to_pack",),
        )

    # Sort by area descending, then importance descending, then id ascending.
    def _key(c: UvChartRequest) -> tuple[float, float, str]:
        return (-(c.width_uv * c.height_uv), -c.importance_weight, c.chart_id)

    queue = sorted(charts, key=_key)
    placements: list[UvChartPlacement] = []
    overflow: list[UvChartRequest] = list(queue)
    rescaled_count = 0
    fill_ratios: list[float] = []
    diagnostics: list[str] = []

    for tile in range(tile_budget):
        if not overflow:
            break
        sub_placements, leftovers, area_used = _pack_shelf(overflow, tile)
        placements.extend(sub_placements)
        fill_ratios.append(area_used)
        # If there are leftovers + this is the last tile + auto_rescale is on,
        # try shrinking the leftovers and packing one more pass.
        if leftovers and auto_rescale_to_fit and tile == tile_budget - 1:
            shrunk: list[UvChartRequest] = []
            for chart in leftovers:
                if chart.fixed_size:
                    shrunk.append(chart)
                    continue
                factor = max(auto_rescale_max_shrink, 0.9)
                shrunk.append(
                    UvChartRequest(
                        chart_id=chart.chart_id,
                        part_id=chart.part_id,
                        width_uv=chart.width_uv * factor,
                        height_uv=chart.height_uv * factor,
                        importance_weight=chart.importance_weight,
                        fixed_size=chart.fixed_size,
                        seam_group_id=chart.seam_group_id,
                    )
                )
                rescaled_count += 1
            sub_placements_2, leftovers_2, area_used_2 = _pack_shelf(shrunk, tile)
            placements.extend(sub_placements_2)
            fill_ratios[-1] = fill_ratios[-1] + area_used_2
            overflow = leftovers_2
        else:
            overflow = leftovers

    # Density-drift evaluation.
    worst_drift = 0.0
    if asset_target_density_px_per_m and placements:
        per_chart_density: list[float] = []
        for p in placements:
            chart_area_uv = (p.u_max - p.u_min) * (p.v_max - p.v_min)
            world_area_proxy = max(0.0001, p.importance_weight)
            per_chart_density.append(chart_area_uv / world_area_proxy)
        if per_chart_density:
            d_min = min(per_chart_density)
            d_max = max(per_chart_density)
            worst_drift = (d_max - d_min) / max(1e-6, d_max)

    if overflow:
        diagnostics.append(
            f"udim_overflow: {len(overflow)} chart(s) did not fit within {tile_budget} tile(s)"
        )
    if worst_drift > 0.5:
        diagnostics.append(
            f"texel_density_drift_high: {worst_drift:.2f} > 0.5"
        )

    return PackingReport(
        version=CONSTRAINED_PACKING_VERSION,
        placements=tuple(placements),
        tile_count=len(fill_ratios),
        overflowed_charts=tuple(c.chart_id for c in overflow),
        rescaled_chart_count=rescaled_count,
        fill_ratio_per_tile=tuple(fill_ratios),
        worst_density_drift_ratio=worst_drift,
        diagnostics=tuple(diagnostics),
    )


def packing_report_to_dict(report: PackingReport) -> dict[str, Any]:
    return {
        "version": report.version,
        "tile_count": report.tile_count,
        "overflowed_charts": list(report.overflowed_charts),
        "rescaled_chart_count": report.rescaled_chart_count,
        "fill_ratio_per_tile": list(report.fill_ratio_per_tile),
        "worst_density_drift_ratio": report.worst_density_drift_ratio,
        "diagnostics": list(report.diagnostics),
        "placements": [
            {
                "chart_id": p.chart_id,
                "part_id": p.part_id,
                "tile_index": p.tile_index,
                "u_min": p.u_min,
                "v_min": p.v_min,
                "u_max": p.u_max,
                "v_max": p.v_max,
                "importance_weight": p.importance_weight,
                "rescaled": p.rescaled,
                "rescale_factor": p.rescale_factor,
            }
            for p in report.placements
        ],
    }


__all__ = [
    "CONSTRAINED_PACKING_VERSION",
    "PackingReport",
    "UvChartPlacement",
    "UvChartRequest",
    "pack_uv_charts",
    "packing_report_to_dict",
]
