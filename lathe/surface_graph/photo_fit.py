"""Photo-fit mode (V0.1 §6.1 mode 2).

Substance-Sampler-class deterministic palette extraction + frequency
analysis + tile-fitting from a reference photo. **No learned model.**

Steps:
  1. Load reference image (PIL).
  2. Extract dominant palette (k-means in CIELAB).
  3. Frequency analysis (FFT) to detect tiling period.
  4. Tile-fit: extract a representative tile, apply periodic-boundary
     blending.
  5. Drive a designer_graph with the extracted palette + tile pattern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _srgb_to_linear(arr: np.ndarray) -> np.ndarray:
    a = arr / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _linear_to_xyz(rgb: np.ndarray) -> np.ndarray:
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    return rgb @ m.T


def _xyz_to_lab(xyz: np.ndarray) -> np.ndarray:
    # D65 reference white.
    ref = np.array([0.95047, 1.00000, 1.08883])
    f = xyz / ref
    f = np.where(f > (6 / 29) ** 3, np.cbrt(f), (1 / 3) * ((29 / 6) ** 2) * f + 4 / 29)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def _lab_to_xyz(lab: np.ndarray) -> np.ndarray:
    ref = np.array([0.95047, 1.00000, 1.08883])
    fy = (lab[..., 0] + 16) / 116
    fx = lab[..., 1] / 500 + fy
    fz = fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], axis=-1)
    f3 = f ** 3
    return ref * np.where(f3 > (6 / 29) ** 3, f3, 3 * (6 / 29) ** 2 * (f - 4 / 29))


def _xyz_to_srgb(xyz: np.ndarray) -> np.ndarray:
    m_inv = np.array([
        [3.2404542, -1.5371385, -0.4985314],
        [-0.9692660, 1.8760108, 0.0415560],
        [0.0556434, -0.2040259, 1.0572252],
    ])
    rgb = xyz @ m_inv.T
    rgb = np.clip(rgb, 0.0, 1.0)
    return np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * (rgb ** (1 / 2.4)) - 0.055) * 255.0


def fit_palette(image: Image.Image, k: int = 5, seed: int = 0) -> list[tuple[int, int, int]]:
    """Extract ``k`` dominant colours from ``image`` via k-means in CIELAB.

    Deterministic: seeded RNG initial centres + fixed iteration cap.
    """
    arr = np.asarray(image.convert("RGB"), dtype=np.float64)
    flat = arr.reshape(-1, 3)
    # Sub-sample for speed.
    rng = np.random.default_rng(seed)
    if flat.shape[0] > 4096:
        idx = rng.choice(flat.shape[0], size=4096, replace=False)
        sample = flat[idx]
    else:
        sample = flat
    lab = _xyz_to_lab(_linear_to_xyz(_srgb_to_linear(sample)))
    # K-means++.
    centres = [lab[rng.integers(0, lab.shape[0])]]
    for _ in range(k - 1):
        dists = np.min(np.linalg.norm(lab[:, None] - np.array(centres)[None], axis=-1), axis=1)
        probs = dists ** 2 / max(1e-9, (dists ** 2).sum())
        idx = int(rng.choice(lab.shape[0], p=probs))
        centres.append(lab[idx])
    centres = np.array(centres)
    for _ in range(16):
        dists = np.linalg.norm(lab[:, None] - centres[None], axis=-1)
        labels = np.argmin(dists, axis=1)
        new_centres = np.stack([
            lab[labels == i].mean(axis=0) if np.any(labels == i) else centres[i]
            for i in range(k)
        ])
        if np.allclose(centres, new_centres, atol=1e-3):
            break
        centres = new_centres
    rgb = _xyz_to_srgb(_lab_to_xyz(centres))
    return [tuple(int(x) for x in row.clip(0, 255)) for row in rgb]


def fit_tile_period(image: Image.Image) -> tuple[int, int]:
    """Detect a tiling period via 2D FFT autocorrelation.

    Returns ``(period_x, period_y)`` in pixels. If no strong periodic
    structure is detected we return ``(0, 0)`` so callers fall back to
    untiled noise.
    """
    grey = np.asarray(image.convert("L"), dtype=np.float64)
    grey = grey - grey.mean()
    spectrum = np.fft.fft2(grey)
    power = np.abs(spectrum) ** 2
    autocorr = np.fft.ifft2(power).real
    autocorr = np.fft.fftshift(autocorr)
    h, w = autocorr.shape
    cy, cx = h // 2, w // 2
    # Mask out the central peak (autocorrelation at zero shift is huge).
    mask = np.ones_like(autocorr, dtype=bool)
    rr = max(4, min(h, w) // 32)
    for y in range(max(0, cy - rr), min(h, cy + rr + 1)):
        for x in range(max(0, cx - rr), min(w, cx + rr + 1)):
            mask[y, x] = False
    # Find peak in masked region; report relative offsets as the tiling period.
    masked = np.where(mask, autocorr, -np.inf)
    peak_y, peak_x = np.unravel_index(np.argmax(masked), masked.shape)
    period_x = abs(int(peak_x - cx))
    period_y = abs(int(peak_y - cy))
    # Discard low-confidence detections.
    threshold = autocorr.max() * 0.10
    if masked[peak_y, peak_x] < threshold:
        return (0, 0)
    return (period_x, period_y)


def extract_representative_tile(image: Image.Image, period: tuple[int, int]) -> Image.Image:
    """Crop a representative tile from ``image`` per the detected period.

    Blends the right edge into the left and the bottom into the top to
    approximate periodic boundaries.
    """
    period_x, period_y = period
    if period_x <= 0 or period_y <= 0:
        return image.copy()
    arr = np.asarray(image.convert("RGB"), dtype=np.float64)
    h, w, _ = arr.shape
    px = min(period_x, w)
    py = min(period_y, h)
    tile = arr[:py, :px].copy()
    # Periodic blend.
    blend_w = max(1, px // 12)
    blend_h = max(1, py // 12)
    for k in range(blend_w):
        weight = k / blend_w
        tile[:, k] = tile[:, k] * (1.0 - weight) + tile[:, -1 - k] * weight
    for k in range(blend_h):
        weight = k / blend_h
        tile[k, :] = tile[k, :] * (1.0 - weight) + tile[-1 - k, :] * weight
    return Image.fromarray(tile.clip(0, 255).astype(np.uint8), mode="RGB")


def compile_photo_fit(values: dict[str, Any], *, asset_name: str = "asset") -> dict[str, Any]:
    """Compile a photo_fit surface_program block.

    Required: ``reference: <path>``. Optional: ``palette_size: int``,
    ``feed_designer: bool`` (default true). The reference is loaded via
    PIL; the extracted palette + detected tiling period drive a
    designer_graph compile so the output is the same MaterialX-shaped
    handoff.
    """
    from .designer_graph import DesignerGraph
    from .materialx import compile_materialx

    reference = values.get("reference") or values.get("photo") or values.get("image")
    palette: list[tuple[int, int, int]] = []
    period: tuple[int, int] = (0, 0)
    fallback_reason = ""
    if not reference:
        fallback_reason = "no_reference_path_provided"
    else:
        ref_path = Path(str(reference))
        if not ref_path.exists():
            fallback_reason = "reference_path_missing"
        else:
            try:
                with Image.open(ref_path) as img:
                    img.load()
                    palette = fit_palette(img, k=int(values.get("palette_size", 5)), seed=int(values.get("seed", 0)))
                    period = fit_tile_period(img)
            except (OSError, ValueError) as exc:
                fallback_reason = f"image_load_failed:{type(exc).__name__}"
    # Drive a designer_graph with extracted controls.
    derived_params = dict(values)
    if palette:
        derived_params["palette"] = palette
    if period and period[0] > 0:
        derived_params.setdefault("cols", max(2, int(round(512 / max(1, period[0])))))
        derived_params.setdefault("rows", max(2, int(round(512 / max(1, period[1])))))
        derived_params.setdefault("pattern", "tile")
    graph = DesignerGraph.from_recipe(derived_params)
    materialx_doc = compile_materialx(
        mode="photo_fit",
        outputs=graph.outputs,
        params={**derived_params, "extracted_palette": palette, "tile_period": list(period)},
        asset_name=asset_name,
    )
    return {
        "mode": "photo_fit",
        "graph_ir": graph.to_dict(),
        "outputs": dict(graph.outputs),
        "channels": {
            "basecolor": {"source": "comp_with_wear", "kind": "color3"},
            "normal": {"source": "normal", "kind": "vector3"},
            "height": {"source": "height", "kind": "float"},
            "ao": {"source": "ao", "kind": "float"},
            "curvature": {"source": "curvature", "kind": "float"},
            "metallic": {"source": "constant", "kind": "float", "value": float(values.get("metallic", 0.0))},
            "roughness": {"source": "derived_from_curvature", "kind": "float"},
        },
        "materialx_doc": materialx_doc,
        "extracted_palette": palette,
        "tile_period_px": list(period),
        "fallback_reason": fallback_reason,
        "trace": {
            "kind": "photo_fit_v1",
            "reference": str(reference) if reference else "",
            "palette_size": len(palette),
            "tile_period_px": list(period),
            "fallback_reason": fallback_reason,
            "downstream_mode": "designer_graph",
            "deterministic": True,
        },
    }
