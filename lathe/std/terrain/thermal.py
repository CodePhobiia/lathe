"""Thermal (talus / angle-of-repose) erosion.

Where the local slope exceeds the material's angle of repose, soil
slips downhill into lower neighbours. The model is gravity-driven and
deterministic: the per-cell delta only depends on the current heights
and the threshold angle, so two runs with identical input produce
byte-identical output without any seeded randomness.

Algorithm (Musgrave / Olsen, 1989; the "talus" model):

    For each cell ``c`` with at least one neighbour ``n`` such that
    ``h[c] - h[n] > talus_threshold``:
        - Move ``transport_rate * (max_dh - talus_threshold)`` downhill
          from ``c``, distributed across qualifying neighbours weighted
          by their relative deficit.

The threshold is expressed as a height (world units) per cell — the
solver derives the corresponding angle from the cell size when callers
pass an angle directly.
"""

from __future__ import annotations

import numpy as np

from .heightfield import Heightfield


def simulate_thermal_erosion(
    heightfield: Heightfield,
    *,
    iterations: int = 5,
    angle_of_repose_rad: float = 0.6,
    transport_rate: float = 0.5,
) -> dict[str, np.ndarray]:
    """Run ``iterations`` thermal-erosion passes (8-neighbor talus).

    Mutates ``heightfield.heights`` in place. Returns a dict with the
    cumulative ``talus_mask`` (the per-cell sum of soil moved across
    all iterations, normalised to ``[0, 1]``) and the final
    ``slope_mask``.
    """
    ny, nx = heightfield.heights.shape
    dx, dy = heightfield.cell_size
    talus_mask = np.zeros((ny, nx), dtype=np.float64)
    # Threshold height delta = tan(angle) * cell distance. We use the
    # average cell side as a simple, isotropy-respecting proxy.
    threshold = np.tan(float(angle_of_repose_rad)) * 0.5 * (dx + dy)

    neighbors = [
        (dr, dc, np.hypot(dr * dy, dc * dx))
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if not (dr == 0 and dc == 0)
    ]

    for _ in range(int(iterations)):
        z = heightfield.heights * heightfield.vertical_scale
        deltas = np.zeros_like(z)
        # Gather qualifying outflow per (dr, dc) shift.
        qualifying = []
        for dr, dc, dist in neighbors:
            shifted = _shifted(z, dr, dc, fill=np.inf)
            shifted = np.where(np.isinf(shifted), z, shifted)
            dh = z - shifted - threshold * dist / (0.5 * (dx + dy))
            qualifying.append((dr, dc, np.maximum(dh, 0.0)))
        max_dh = np.zeros_like(z)
        total = np.zeros_like(z)
        for _, _, dh in qualifying:
            max_dh = np.maximum(max_dh, dh)
            total = total + dh
        # Skip cells that are already below talus everywhere.
        active = max_dh > 0.0
        # Distribute transport_rate * max_dh / 2 across qualifying
        # neighbours weighted by individual deficit / total deficit.
        safe_total = np.where(total > 1e-12, total, 1.0)
        scale = np.where(active & (total > 1e-12), transport_rate * 0.5 * max_dh / safe_total, 0.0)
        for dr, dc, dh in qualifying:
            move = dh * scale
            deltas = deltas - move
            # Accumulate the inflow on neighbour cells.
            inflow = _shifted(move, -dr, -dc, fill=0.0)
            deltas = deltas + inflow
        heightfield.heights = heightfield.heights + deltas / max(heightfield.vertical_scale, 1e-9)
        talus_mask = talus_mask + np.abs(deltas)

    talus_norm = talus_mask / max(float(np.max(talus_mask)), 1e-9)
    slope_mask_out = heightfield.slope_mask()

    heightfield.set_mask("talus_mask", talus_norm)
    heightfield.set_mask("slope_mask", slope_mask_out)

    return {
        "talus_mask": talus_norm,
        "slope_mask": slope_mask_out,
        "iterations": int(iterations),
    }


def weathering_pass(
    heightfield: Heightfield,
    *,
    smoothing: float = 0.15,
    iterations: int = 1,
) -> Heightfield:
    """Apply Gaussian-style box-blur weathering passes.

    Uniform 3x3 averaging blends adjacent samples; ``smoothing`` is the
    fraction of the smoothed value blended back into the heights. Used
    after thermal erosion to take the final 'fresh-cut' edge off cliff
    boundaries.
    """
    for _ in range(int(iterations)):
        z = heightfield.heights
        kernel_sum = np.zeros_like(z)
        kernel_count = np.zeros_like(z)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                shifted = _shifted(z, dr, dc, fill=np.nan)
                valid = ~np.isnan(shifted)
                kernel_sum = kernel_sum + np.where(valid, shifted, 0.0)
                kernel_count = kernel_count + valid.astype(np.float64)
        smoothed = kernel_sum / np.maximum(kernel_count, 1.0)
        heightfield.heights = z * (1.0 - smoothing) + smoothed * smoothing
    return heightfield


def _shifted(arr: np.ndarray, dr: int, dc: int, *, fill: float = 0.0) -> np.ndarray:
    out = np.full_like(arr, fill)
    rs = slice(max(0, dr), arr.shape[0] + min(0, dr))
    cs = slice(max(0, dc), arr.shape[1] + min(0, dc))
    rd = slice(max(0, -dr), arr.shape[0] + min(0, -dr))
    cd = slice(max(0, -dc), arr.shape[1] + min(0, -dc))
    out[rs, cs] = arr[rd, cd]
    return out
