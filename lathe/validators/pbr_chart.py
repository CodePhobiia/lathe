"""Roadmap §5.9 — PBR chart compliance validator (renderer-dependent).

When the surface stage emits a PBR test-chart render (a stable scene
illuminated by a known HDRI showing all material zones side by side),
this validator checks the rendered chart for canonical PBR ranges:

* Metallic ∈ {0, 1} (no in-between values; metallic should be a binary
  mask after quantization).
* Dielectric F0 ≈ 0.04 (sampled from a non-metallic patch's specular
  response).
* Albedo magnitudes within the safe sRGB range [30, 243] for non-
  metallic surfaces.

When no chart render is available the validator emits
``severity: info`` and ``status: renderer_unavailable``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

VERSION = "lathe.validate.pbr_chart_compliance_v1"

_DEFAULT_RENDER_DIR_KEY = "pbr_chart_render_dir"
_METALLIC_BINARY_TOLERANCE = 0.10
_DIELECTRIC_F0_TARGET = 0.04
_DIELECTRIC_F0_TOLERANCE = 0.01
_ALBEDO_LOW = 30
_ALBEDO_HIGH = 243


def _chart_dir(runtime: dict[str, Any]) -> Path | None:
    render_eval = runtime.get("render_eval") if isinstance(runtime.get("render_eval"), dict) else {}
    raw = render_eval.get(_DEFAULT_RENDER_DIR_KEY)
    if isinstance(raw, str) and raw:
        path = Path(raw)
        return path if path.is_dir() else None
    surface = runtime.get("surface") if isinstance(runtime.get("surface"), dict) else {}
    stage_dir = surface.get("stage_dir")
    if isinstance(stage_dir, (str, Path)):
        candidate = Path(stage_dir) / "pbr_chart"
        return candidate if candidate.is_dir() else None
    return None


def _load_image_rgb(path: Path) -> np.ndarray | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return np.asarray(image.convert("RGB"), dtype=np.uint8)
    except (FileNotFoundError, OSError, ValueError, ImportError):
        return None


def _load_grayscale(path: Path) -> np.ndarray | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return np.asarray(image.convert("L"), dtype=np.uint8)
    except (FileNotFoundError, OSError, ValueError, ImportError):
        return None


def _metallic_binary_score(metallic: np.ndarray) -> float:
    """Reward binary metallic maps; penalise mid-grey halftones."""
    norm = metallic.astype(np.float64) / 255.0
    distance_to_binary = np.minimum(norm, 1.0 - norm)
    mid_share = float(np.mean(distance_to_binary > _METALLIC_BINARY_TOLERANCE))
    return max(0.0, min(1.0, 1.0 - mid_share / 0.20))


def _dielectric_f0_score(specular: np.ndarray) -> tuple[float, float]:
    """Sample the *darkest* specular cluster and compare to F0=0.04."""
    flat = specular.astype(np.float64).ravel() / 255.0
    if flat.size == 0:
        return 0.0, 0.0
    cutoff = np.percentile(flat, 25.0)
    sample = flat[flat <= cutoff]
    if sample.size == 0:
        return 0.0, 0.0
    measured = float(np.mean(sample))
    delta = abs(measured - _DIELECTRIC_F0_TARGET)
    score = max(0.0, min(1.0, 1.0 - delta / max(1e-9, _DIELECTRIC_F0_TOLERANCE)))
    return score, measured


def _albedo_range_score(albedo: np.ndarray) -> tuple[float, float]:
    luma = (
        0.2126 * albedo[..., 0].astype(np.float64)
        + 0.7152 * albedo[..., 1].astype(np.float64)
        + 0.0722 * albedo[..., 2].astype(np.float64)
    )
    in_range = float(np.mean((luma >= _ALBEDO_LOW) & (luma <= _ALBEDO_HIGH)))
    return in_range, float(np.mean(luma))


def evaluate_pbr_chart_compliance(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate PBR chart channel-range compliance from a rendered chart."""
    chart_dir = _chart_dir(runtime)
    if chart_dir is None:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "renderer_unavailable",
            "severity": "info",
            "evidence": {"reason": "no PBR chart render directory configured"},
        }

    albedo_path = chart_dir / "albedo.png"
    metallic_path = chart_dir / "metallic.png"
    specular_path = chart_dir / "specular.png"

    albedo = _load_image_rgb(albedo_path) if albedo_path.exists() else None
    metallic = _load_grayscale(metallic_path) if metallic_path.exists() else None
    specular = _load_grayscale(specular_path) if specular_path.exists() else None

    if albedo is None and metallic is None and specular is None:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "renderer_unavailable",
            "severity": "info",
            "evidence": {
                "reason": "PBR chart channel renders unavailable",
                "expected_paths": [str(albedo_path), str(metallic_path), str(specular_path)],
            },
        }

    sub_scores: dict[str, float] = {}
    extras: dict[str, Any] = {}
    if metallic is not None:
        sub_scores["metallic_binary"] = _metallic_binary_score(metallic)
    if specular is not None:
        score, measured = _dielectric_f0_score(specular)
        sub_scores["dielectric_f0"] = score
        extras["dielectric_f0_measured"] = round(measured, 6)
        extras["dielectric_f0_target"] = _DIELECTRIC_F0_TARGET
    if albedo is not None:
        score, mean_luma = _albedo_range_score(albedo)
        sub_scores["albedo_range"] = score
        extras["albedo_in_range_share"] = round(score, 6)
        extras["albedo_mean_luma"] = round(mean_luma, 6)

    if not sub_scores:
        return {
            "version": VERSION,
            "score": 1.0,
            "status": "renderer_unavailable",
            "severity": "info",
            "evidence": {"reason": "no usable PBR chart channels"},
        }
    final_score = round(float(np.mean(list(sub_scores.values()))), 6)

    if final_score < 0.45:
        status, severity = "fail", "error"
    elif final_score < 0.65:
        status, severity = "warn", "warning"
    else:
        status, severity = "pass", "info"

    return {
        "version": VERSION,
        "score": final_score,
        "status": status,
        "severity": severity,
        "evidence": {
            "sub_scores": {k: round(v, 6) for k, v in sub_scores.items()},
            "chart_dir": str(chart_dir),
            "albedo_low": _ALBEDO_LOW,
            "albedo_high": _ALBEDO_HIGH,
            **extras,
        },
    }
