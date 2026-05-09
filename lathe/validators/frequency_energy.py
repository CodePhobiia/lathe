"""Roadmap §5.9 — frequency-energy validator (renderer-dependent).

Computes the FFT energy distribution of a rendered silhouette,
specifically the energy concentrated in *non-axis-aligned* bands.
Pure-cube assets project all of their FFT energy onto the X/Y
spectral axes; richer silhouettes spread energy diagonally.

When no rendered silhouette is available the validator emits
``severity: info`` and ``status: renderer_unavailable``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

VERSION = "lathe.validate.frequency_energy_v1"

_DEFAULT_PRIMARY_ANGLE = "front"
_DEFAULT_RENDER_DIR_KEY = "silhouette_render_dir"
_AXIS_BAND_WIDTH = 6
_GOOD_DIAGONAL_RATIO = 0.55


def _render_dir(runtime: dict[str, Any]) -> Path | None:
    render_eval = runtime.get("render_eval") if isinstance(runtime.get("render_eval"), dict) else {}
    raw = render_eval.get(_DEFAULT_RENDER_DIR_KEY)
    if isinstance(raw, str) and raw:
        path = Path(raw)
        return path if path.is_dir() else None
    surface = runtime.get("surface") if isinstance(runtime.get("surface"), dict) else {}
    stage_dir = surface.get("stage_dir")
    if isinstance(stage_dir, (str, Path)):
        candidate = Path(stage_dir) / "silhouettes"
        return candidate if candidate.is_dir() else None
    return None


def _load_mask(path: Path) -> np.ndarray | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            arr = np.asarray(image.convert("L"), dtype=np.uint8)
    except (FileNotFoundError, OSError, ValueError, ImportError):
        return None
    return (arr < 128).astype(np.uint8)


def _diagonal_energy_ratio(mask: np.ndarray) -> tuple[float, float, float]:
    fft = np.fft.fftshift(np.abs(np.fft.fft2(mask.astype(np.float64))))
    h, w = fft.shape
    cy, cx = h // 2, w // 2
    band = _AXIS_BAND_WIDTH

    axis_mask = np.zeros_like(fft, dtype=bool)
    axis_mask[cy - band : cy + band + 1, :] = True
    axis_mask[:, cx - band : cx + band + 1] = True

    total = float(fft.sum())
    if total <= 0:
        return 0.0, 0.0, 0.0
    axis_energy = float(fft[axis_mask].sum())
    diagonal_energy = total - axis_energy
    return float(diagonal_energy / total), float(axis_energy / total), total


def evaluate_frequency_energy(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate non-axis-aligned spectral energy on a rendered silhouette."""
    render_dir = _render_dir(runtime)
    if render_dir is None:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "renderer_unavailable",
            "severity": "info",
            "evidence": {"reason": "no silhouette render directory configured"},
        }

    candidate = render_dir / f"silhouette_{_DEFAULT_PRIMARY_ANGLE}.png"
    mask = _load_mask(candidate)
    if mask is None:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "renderer_unavailable",
            "severity": "info",
            "evidence": {
                "reason": "primary silhouette render unavailable",
                "expected_path": str(candidate),
            },
        }

    diag_ratio, axis_ratio, total_energy = _diagonal_energy_ratio(mask)
    score = round(min(1.0, diag_ratio / max(1e-9, _GOOD_DIAGONAL_RATIO)), 6)

    if score < 0.45:
        status, severity = "fail", "error"
    elif score < 0.65:
        status, severity = "warn", "warning"
    else:
        status, severity = "pass", "info"

    return {
        "version": VERSION,
        "score": score,
        "status": status,
        "severity": severity,
        "evidence": {
            "diagonal_energy_ratio": round(diag_ratio, 6),
            "axis_aligned_energy_ratio": round(axis_ratio, 6),
            "total_energy": round(total_energy, 6),
            "good_diagonal_ratio": _GOOD_DIAGONAL_RATIO,
            "axis_band_width_px": _AXIS_BAND_WIDTH,
            "render_path": str(candidate),
        },
    }
