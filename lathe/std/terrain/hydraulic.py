"""Tu-Pham (2008) hydraulic erosion — deterministic CPU implementation.

Reference: Pham, X. "Hydraulic Erosion on the GPU" (2008), Chapter 1 of
*GPU Pro 1*. The reference algorithm has six explicit per-step phases,
all of which we evaluate here on the CPU with NumPy primitives so the
solver is deterministic at fixed seed:

    1. Rain — uniform water level addition.
    2. Outflow — pipe-flux model: each cell has 4 outflow pipes (L/R/T/B);
       flux is updated from the head difference between neighbouring water
       columns and clamped so a cell never exports more water than it has.
    3. Velocity — instantaneous velocity field from net horizontal flux
       (used to drive sediment transport).
    4. Sediment capacity / erosion / deposition — capacity ``C = K_c *
       sin(slope) * |velocity|``. Where capacity exceeds carried sediment,
       lift soil from the bedrock; where capacity is lower, deposit.
    5. Sediment transport — sediment is carried by the velocity field
       (semi-Lagrangian advection with a single backwards step).
    6. Evaporation — water level is multiplied by ``1 - K_e * dt``.

This is the *real* algorithm. It is also the right algorithm for
deterministic procedural terrain: at fixed seed and parameter pack the
sequence of states is reproducible. The output is the eroded heightfield
plus three masks consumed downstream by the surface_graph Smart Mask
library:

    - ``slope_mask`` — normalised slope, recomputed after erosion.
    - ``flow_mask`` — water-flow accumulation (where rivers form).
    - ``deposition_mask`` — net sediment delta (where soil settled).

References for parameter ranges that produce visually-plausible terrain
(canyon with moderate channels, talus slopes, no runaway oscillation):
the published Tu-Pham defaults plus follow-up work by Mei, Decaudin &
Hu (2007) on shallow-water on heightfields.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .heightfield import Heightfield


@dataclass(frozen=True)
class HydraulicParams:
    """Tunable knobs for Tu-Pham hydraulic erosion."""

    rain_amount: float = 0.012
    """Water added per cell per step (uniform rain)."""

    evaporation: float = 0.015
    """Fraction of water removed per step."""

    pipe_area: float = 0.6
    """Cross-sectional pipe area; bigger => faster flow."""

    pipe_length: float = 1.0
    """Distance between adjacent water columns; cell_size."""

    gravity: float = 9.81
    """Gravity constant for the pipe-flux model."""

    sediment_capacity: float = 0.45
    """``K_c`` — multiplier on sin(slope) * |v|."""

    soil_softness: float = 0.35
    """``K_s`` — fraction of capacity-deficit that erodes per step."""

    deposition_rate: float = 0.25
    """``K_d`` — fraction of excess sediment deposited per step."""

    min_slope: float = 0.005
    """Minimum slope clamp to avoid zero-capacity stalls on flats."""

    dt: float = 1.0
    """Integration timestep (chosen with the rest of the pack to be CFL-safe)."""


def _shifted(arr: np.ndarray, dr: int, dc: int, *, fill: float = 0.0) -> np.ndarray:
    """Shift ``arr`` by (dr, dc) cells, padding the new edge with ``fill``."""
    out = np.full_like(arr, fill)
    rs = slice(max(0, dr), arr.shape[0] + min(0, dr))
    cs = slice(max(0, dc), arr.shape[1] + min(0, dc))
    rd = slice(max(0, -dr), arr.shape[0] + min(0, -dr))
    cd = slice(max(0, -dc), arr.shape[1] + min(0, -dc))
    out[rs, cs] = arr[rd, cd]
    return out


def simulate_hydraulic_erosion(
    heightfield: Heightfield,
    *,
    iterations: int = 30,
    params: HydraulicParams | None = None,
    seed: int = 0,
) -> dict[str, np.ndarray]:
    """Run ``iterations`` steps of Tu-Pham hydraulic erosion.

    Mutates ``heightfield.heights`` in place. Returns a dict containing
    the final ``water``, ``sediment``, ``flow``, and ``deposition``
    fields plus the canonical mask outputs (slope/flow/deposition) that
    the surface_graph Smart Mask library binds to.

    Determinism: at fixed ``seed``, ``params``, and starting heights the
    output is byte-identical. The solver itself is deterministic; the
    seed seeds an *intentionally tiny* perturbation field so the rain
    isn't perfectly uniform (otherwise carve patterns degenerate into
    grid-aligned stripes on synthetic noise).
    """
    if params is None:
        params = HydraulicParams()

    ny, nx = heightfield.heights.shape
    rng = np.random.default_rng(np.uint64(seed) & np.uint64(0xFFFFFFFF))
    rain_jitter = rng.random((ny, nx), dtype=np.float64) * 0.05 + 0.975

    water = np.zeros((ny, nx), dtype=np.float64)
    sediment = np.zeros((ny, nx), dtype=np.float64)
    # Outflow pipes: L (left, dc=-1), R (right, dc=+1), T (top, dr=-1), B (bottom, dr=+1).
    flux_l = np.zeros((ny, nx), dtype=np.float64)
    flux_r = np.zeros((ny, nx), dtype=np.float64)
    flux_t = np.zeros((ny, nx), dtype=np.float64)
    flux_b = np.zeros((ny, nx), dtype=np.float64)
    flow_accum = np.zeros((ny, nx), dtype=np.float64)
    deposition_total = np.zeros((ny, nx), dtype=np.float64)

    dx, dy = heightfield.cell_size
    pipe_len = max(params.pipe_length * 0.5 * (dx + dy), 1e-6)
    flux_coeff = params.dt * params.pipe_area * params.gravity / pipe_len

    for _ in range(int(iterations)):
        # 1. Rain.
        water = water + params.rain_amount * params.dt * rain_jitter

        # 2. Outflow flux update — head difference per pipe.
        head = heightfield.heights * heightfield.vertical_scale + water
        head_l = _shifted(head, 0, -1, fill=np.inf)  # neighbor on left
        head_r = _shifted(head, 0, 1, fill=np.inf)
        head_t = _shifted(head, -1, 0, fill=np.inf)
        head_b = _shifted(head, 1, 0, fill=np.inf)
        # Boundary: clamp neighbor head to current head so border cells
        # do not artificially export water off the grid.
        head_l = np.where(np.isinf(head_l), head, head_l)
        head_r = np.where(np.isinf(head_r), head, head_r)
        head_t = np.where(np.isinf(head_t), head, head_t)
        head_b = np.where(np.isinf(head_b), head, head_b)

        flux_l = np.maximum(0.0, flux_l + flux_coeff * (head - head_l))
        flux_r = np.maximum(0.0, flux_r + flux_coeff * (head - head_r))
        flux_t = np.maximum(0.0, flux_t + flux_coeff * (head - head_t))
        flux_b = np.maximum(0.0, flux_b + flux_coeff * (head - head_b))

        # Conservation clamp: a cell can't lose more water than it has.
        out_total = (flux_l + flux_r + flux_t + flux_b) * params.dt
        cell_volume = water * (dx * dy)
        scale = np.where(out_total > 1e-12, np.minimum(1.0, cell_volume / np.maximum(out_total, 1e-12)), 1.0)
        flux_l = flux_l * scale
        flux_r = flux_r * scale
        flux_t = flux_t * scale
        flux_b = flux_b * scale

        # 3. Update water and compute velocity.
        in_l = _shifted(flux_r, 0, -1)
        in_r = _shifted(flux_l, 0, 1)
        in_t = _shifted(flux_b, -1, 0)
        in_b = _shifted(flux_t, 1, 0)
        net = (in_l + in_r + in_t + in_b - (flux_l + flux_r + flux_t + flux_b))
        new_water = water + net * params.dt / (dx * dy)
        new_water = np.maximum(new_water, 0.0)
        water_avg = 0.5 * (water + new_water)
        water_avg_safe = np.where(water_avg > 1e-6, water_avg, 1e-6)
        vx = ((in_l - flux_l) + (flux_r - in_r)) / (2.0 * dy * water_avg_safe)
        vy = ((in_t - flux_t) + (flux_b - in_b)) / (2.0 * dx * water_avg_safe)
        speed = np.sqrt(vx * vx + vy * vy)

        # 4. Sediment capacity, erosion, deposition.
        slope = heightfield.slope()
        sin_slope = np.maximum(np.sin(slope), params.min_slope)
        capacity = params.sediment_capacity * sin_slope * speed
        deficit = capacity - sediment
        erode_amount = np.where(deficit > 0.0, deficit * params.soil_softness, 0.0)
        deposit_amount = np.where(deficit < 0.0, -deficit * params.deposition_rate, 0.0)
        # Border cells don't get eroded — keeps the rim deterministic.
        erode_amount[0, :] = 0.0
        erode_amount[-1, :] = 0.0
        erode_amount[:, 0] = 0.0
        erode_amount[:, -1] = 0.0
        heightfield.heights = heightfield.heights - erode_amount / max(heightfield.vertical_scale, 1e-9)
        heightfield.heights = heightfield.heights + deposit_amount / max(heightfield.vertical_scale, 1e-9)
        sediment = sediment + erode_amount - deposit_amount
        deposition_total = deposition_total + deposit_amount

        # 5. Sediment transport — single-step backwards advection.
        ny_idx = np.arange(ny, dtype=np.float64)[:, None]
        nx_idx = np.arange(nx, dtype=np.float64)[None, :]
        src_y = np.clip(ny_idx - vy * params.dt / dy, 0.0, ny - 1)
        src_x = np.clip(nx_idx - vx * params.dt / dx, 0.0, nx - 1)
        sediment = _bilinear_sample(sediment, src_y, src_x)

        # 6. Evaporation.
        water = new_water * (1.0 - params.evaporation * params.dt)
        water = np.maximum(water, 0.0)

        # Accumulate flow for the flow_mask output.
        flow_accum = flow_accum + speed * water_avg

    flow_norm = flow_accum / max(float(np.max(flow_accum)), 1e-9)
    deposition_norm = deposition_total / max(float(np.max(np.abs(deposition_total))), 1e-9)
    deposition_norm = np.clip(deposition_norm, 0.0, 1.0)
    slope_mask_out = heightfield.slope_mask()

    heightfield.set_mask("slope_mask", slope_mask_out)
    heightfield.set_mask("flow_mask", flow_norm)
    heightfield.set_mask("deposition_mask", deposition_norm)
    heightfield.set_mask("hydraulic_water", water)
    heightfield.set_mask("hydraulic_sediment", sediment)

    return {
        "water": water,
        "sediment": sediment,
        "flow_mask": flow_norm,
        "deposition_mask": deposition_norm,
        "slope_mask": slope_mask_out,
        "iterations": int(iterations),
    }


def _bilinear_sample(field: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    ny, nx = field.shape
    y0 = np.floor(ys).astype(np.int64)
    x0 = np.floor(xs).astype(np.int64)
    y1 = np.minimum(y0 + 1, ny - 1)
    x1 = np.minimum(x0 + 1, nx - 1)
    ty = ys - y0
    tx = xs - x0
    v00 = field[y0, x0]
    v10 = field[y0, x1]
    v01 = field[y1, x0]
    v11 = field[y1, x1]
    return (
        v00 * (1.0 - tx) * (1.0 - ty)
        + v10 * tx * (1.0 - ty)
        + v01 * (1.0 - tx) * ty
        + v11 * tx * ty
    )
