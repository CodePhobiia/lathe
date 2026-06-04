"""OKLab color space conversion + blending.

Per northstar §10 Lane D priority task #7. OKLab is a perceptually
uniform color space (Björn Ottosson, 2020) that produces visibly
smooth gradients when mixing basecolor / material colors. The
Foundry uses OKLab for:
  - basecolor blending in material wear graphs (e.g. painted_steel
    + chipped_paint underlay);
  - palette ramps in stylized material atlases;
  - per-zone color mixing where naive sRGB mixing produces muddy
    midpoints.

The implementation is pure-Python and reversible. sRGB <-> linear
<-> OKLab paths use the standard transforms.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

OKLAB_VERSION = "lathe.asset_foundry.oklab_v1"


@dataclass(frozen=True)
class OklabColor:
    """A color in OKLab space."""

    L: float
    """Perceptual lightness in [0, 1]."""

    a: float
    """Green-red axis (-0.5 to 0.5 typical range)."""

    b: float
    """Blue-yellow axis (-0.5 to 0.5 typical range)."""


def srgb_to_linear(c: float) -> float:
    """sRGB component -> linear-light component."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    """Linear-light -> sRGB component."""
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def linear_rgb_to_oklab(r: float, g: float, b: float) -> OklabColor:
    """Linear-light RGB -> OKLab."""
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_ = _cbrt(l)
    m_ = _cbrt(m)
    s_ = _cbrt(s)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return OklabColor(L=L, a=a, b=b_)


def oklab_to_linear_rgb(color: OklabColor) -> tuple[float, float, float]:
    """OKLab -> linear-light RGB."""
    L, a, b = color.L, color.a, color.b
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_out = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return r, g, b_out


def srgb_hex_to_oklab(hex_str: str) -> OklabColor:
    """Parse a ``#rrggbb`` string and return an OKLab color."""
    s = hex_str.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"hex must be 6-char #rrggbb, got {hex_str!r}")
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    lr = srgb_to_linear(r)
    lg = srgb_to_linear(g)
    lb = srgb_to_linear(b)
    return linear_rgb_to_oklab(lr, lg, lb)


def oklab_to_srgb_hex(color: OklabColor) -> str:
    """OKLab -> ``#rrggbb`` clipped sRGB."""
    lr, lg, lb = oklab_to_linear_rgb(color)
    sr = max(0.0, min(1.0, linear_to_srgb(max(0.0, lr))))
    sg = max(0.0, min(1.0, linear_to_srgb(max(0.0, lg))))
    sb = max(0.0, min(1.0, linear_to_srgb(max(0.0, lb))))
    return "#{:02x}{:02x}{:02x}".format(
        int(round(sr * 255.0)),
        int(round(sg * 255.0)),
        int(round(sb * 255.0)),
    )


def oklab_mix(a: OklabColor, b: OklabColor, t: float) -> OklabColor:
    """Linear interpolation in OKLab between two colors at fraction ``t``."""
    t = max(0.0, min(1.0, t))
    return OklabColor(
        L=a.L + t * (b.L - a.L),
        a=a.a + t * (b.a - a.a),
        b=a.b + t * (b.b - a.b),
    )


def oklab_ramp(
    stops_hex: Sequence[str], steps: int
) -> tuple[str, ...]:
    """Sample a multi-stop color ramp in OKLab.

    Given color stops at evenly-spaced positions, return ``steps``
    interpolated sRGB hex colors.
    """
    if len(stops_hex) < 2 or steps < 2:
        raise ValueError("oklab_ramp requires >= 2 stops and >= 2 steps")
    stops = [srgb_hex_to_oklab(c) for c in stops_hex]
    spans = len(stops) - 1
    out: list[str] = []
    for i in range(steps):
        t = i / (steps - 1)
        span_idx = min(int(t * spans), spans - 1)
        local_t = (t * spans) - span_idx
        mixed = oklab_mix(stops[span_idx], stops[span_idx + 1], local_t)
        out.append(oklab_to_srgb_hex(mixed))
    return tuple(out)


def _cbrt(x: float) -> float:
    """Cube root that handles negative inputs."""
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


__all__ = [
    "OKLAB_VERSION",
    "OklabColor",
    "linear_rgb_to_oklab",
    "oklab_mix",
    "oklab_ramp",
    "oklab_to_linear_rgb",
    "oklab_to_srgb_hex",
    "srgb_hex_to_oklab",
    "linear_to_srgb",
    "srgb_to_linear",
]
