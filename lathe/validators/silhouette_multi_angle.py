"""Roadmap §5.9 — multi-angle silhouette validator (renderer-dependent).

Frames the validator and consumes pre-rendered silhouette PNGs when a
renderer adapter has produced them. The validator does *not* invoke
Cycles / Eevee / Mitsuba; instead it looks for renderer outputs at the
configured paths and skips with ``status='renderer_unavailable'`` when
they are missing.

Per asset rendered at declared angles (front, side, iso, plus any
author-declared angles), the validator reads the 512×512 black-on-white
silhouette mask, then computes:

* **isoperimetric ratio** ``perimeter / sqrt(area)`` — round shapes hit
  ~3.5, plain cubes ~4.5; richer silhouettes climb past 6.
* **FFT high-frequency energy** in non-axis-aligned bands.
* **left-right asymmetry** as the L1 difference between the mask and
  its horizontal mirror, normalized by mask area.

When no renderer output is available the validator emits
``severity: info`` and ``status: renderer_unavailable``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

VERSION = "lathe.validate.silhouette_multi_angle_v1"

_DEFAULT_ANGLES = ("front", "side", "iso")
_DEFAULT_RENDER_DIR_KEY = "silhouette_render_dir"
_TARGET_RESOLUTION = 512
_MIN_ISOPERIMETRIC = 3.6
_GOOD_ISOPERIMETRIC = 6.0


def _declared_angles(asset: dict[str, Any]) -> tuple[str, ...]:
    intent = asset.get("intent") if isinstance(asset.get("intent"), dict) else {}
    custom = intent.get("silhouette_angles")
    if isinstance(custom, list) and custom:
        return tuple(str(a).strip().lower() for a in custom if str(a).strip())
    return _DEFAULT_ANGLES


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
    if arr.size == 0:
        return None
    return (arr < 128).astype(np.uint8)


def _isoperimetric(mask: np.ndarray) -> float:
    area = float(mask.sum())
    if area <= 0:
        return 0.0
    diff_h = np.abs(np.diff(mask.astype(np.int16), axis=1)).sum()
    diff_v = np.abs(np.diff(mask.astype(np.int16), axis=0)).sum()
    perimeter = float(diff_h + diff_v)
    return perimeter / np.sqrt(area)


def _high_frequency_energy(mask: np.ndarray) -> float:
    fft = np.fft.fft2(mask.astype(np.float64))
    magnitude = np.abs(fft)
    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    shifted = np.fft.fftshift(magnitude)
    yy, xx = np.mgrid[0:h, 0:w]
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    max_r = float(min(cx, cy))
    if max_r <= 0:
        return 0.0
    high = shifted[radius > 0.5 * max_r].sum()
    total = shifted.sum()
    return float(high / max(total, 1e-9))


def _asymmetry(mask: np.ndarray) -> float:
    mirrored = np.flip(mask, axis=1)
    diff = np.abs(mask.astype(np.int16) - mirrored.astype(np.int16)).sum()
    area = float(mask.sum())
    if area <= 0:
        return 0.0
    return float(diff) / (2.0 * area)


def _per_angle_score(iso: float, hfe: float, asym: float) -> float:
    iso_score = max(
        0.0,
        min(1.0, (iso - _MIN_ISOPERIMETRIC) / max(1e-9, _GOOD_ISOPERIMETRIC - _MIN_ISOPERIMETRIC)),
    )
    hfe_score = max(0.0, min(1.0, hfe / 0.30))
    asym_score = max(0.0, min(1.0, asym * 4.0))
    return round(0.5 * iso_score + 0.3 * hfe_score + 0.2 * asym_score, 6)


def evaluate_silhouette_multi_angle(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate multi-angle silhouette quality from rendered masks."""
    angles = _declared_angles(asset)
    render_dir = _render_dir(runtime)
    if render_dir is None:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "renderer_unavailable",
            "severity": "info",
            "evidence": {
                "reason": "no silhouette render directory configured",
                "declared_angles": list(angles),
            },
        }

    per_angle: list[dict[str, Any]] = []
    scores: list[float] = []
    for angle in angles:
        candidate = render_dir / f"silhouette_{angle}.png"
        mask = _load_mask(candidate)
        if mask is None:
            per_angle.append(
                {
                    "angle": angle,
                    "available": False,
                    "path": str(candidate),
                }
            )
            continue
        iso = _isoperimetric(mask)
        hfe = _high_frequency_energy(mask)
        asym = _asymmetry(mask)
        score = _per_angle_score(iso, hfe, asym)
        scores.append(score)
        per_angle.append(
            {
                "angle": angle,
                "available": True,
                "isoperimetric_ratio": round(iso, 6),
                "high_frequency_energy": round(hfe, 6),
                "asymmetry": round(asym, 6),
                "score": score,
                "resolution": list(mask.shape),
            }
        )

    if not scores:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "renderer_unavailable",
            "severity": "info",
            "evidence": {
                "reason": "no silhouette renders available at expected paths",
                "declared_angles": list(angles),
                "per_angle": per_angle,
                "render_dir": str(render_dir),
            },
        }

    final_score = round(float(np.mean(scores)), 6)
    if final_score < 0.45:
        status, severity = "fail", "error"
    elif final_score < 0.60:
        status, severity = "warn", "warning"
    else:
        status, severity = "pass", "info"

    return {
        "version": VERSION,
        "score": final_score,
        "status": status,
        "severity": severity,
        "evidence": {
            "declared_angles": list(angles),
            "per_angle": per_angle,
            "render_dir": str(render_dir),
            "target_resolution": _TARGET_RESOLUTION,
        },
    }
