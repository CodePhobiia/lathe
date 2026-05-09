"""Typed node primitives for the surface-authoring DAG (V0.1 §6.1 mode 1).

Each node is a deterministic, pure-Python evaluator (numpy under the
hood) that produces either a height/scalar field, a normal map, a mask,
or a colour buffer. Node graphs are JSON-serializable -- the graph IR
is the source of truth; numpy is just the reference evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


def _hash_seed(seed: Any, salt: str) -> int:
    base = abs(int(seed) if isinstance(seed, (int, float)) else hash(str(seed)))
    return (base * 1_000_003 + abs(hash(salt))) & 0x7FFFFFFF


def _grid(size: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.indices((size, size), dtype=np.float64)
    return xx / max(1, size - 1), yy / max(1, size - 1)


def _scalar_buffer(value: Any, size: int, *, default: float = 0.0) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64)
    if arr.ndim == 0:
        return np.full((size, size), float(arr), dtype=np.float64)
    if arr.ndim == 3:
        arr = arr[..., :3].mean(axis=-1)
    if arr.shape[:2] == (size, size):
        return np.asarray(arr, dtype=np.float64)
    if arr.ndim < 2 or arr.shape[0] <= 0 or arr.shape[1] <= 0:
        return np.full((size, size), default, dtype=np.float64)
    y_idx = np.clip(
        np.round(np.linspace(0, arr.shape[0] - 1, size)).astype(np.int64),
        0,
        arr.shape[0] - 1,
    )
    x_idx = np.clip(
        np.round(np.linspace(0, arr.shape[1] - 1, size)).astype(np.int64),
        0,
        arr.shape[1] - 1,
    )
    return np.asarray(arr[np.ix_(y_idx, x_idx)], dtype=np.float64)


def _input_scalar(
    ctx: dict[str, Any],
    inputs: dict[str, str],
    key: str,
    *,
    default: float = 0.0,
) -> np.ndarray:
    size = int(ctx.get("size", 512))
    name = inputs.get(key)
    if name:
        value = ctx.get("buffers", {}).get(name)
        if value is not None:
            return _scalar_buffer(value, size, default=default)
    return np.full((size, size), default, dtype=np.float64)


def _box_blur(buffer: np.ndarray, radius: int) -> np.ndarray:
    out = np.asarray(buffer, dtype=np.float64)
    for _ in range(max(0, int(radius))):
        padded = np.pad(out, 1, mode="edge")
        out = (
            padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
            + padded[1:-1, 1:-1]
        ) / 5.0
    return out


def _smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    t = np.clip((value - edge0) / max(1e-8, edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _color_stop(value: Any) -> tuple[float, np.ndarray] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        position = float(value[0])
        color = np.asarray(value[1], dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if color.shape[0] < 3:
        return None
    color = color[:3]
    if float(np.max(color)) > 1.0:
        color = color / 255.0
    return position, np.clip(color, 0.0, 1.0)


@dataclass
class SurfaceNode:
    """Base typed surface node.

    Subclasses must implement :meth:`eval`. Evaluators receive a
    ``ctx`` dict carrying the working resolution and shared inputs
    (``@P``, ``@N``, ``@curvature``, ``@ao``, etc.) so mask expressions
    in :class:`Mask` can resolve attribute references deterministically.
    """

    name: str
    kind: str = "node"
    inputs: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "inputs": dict(self.inputs),
            "params": dict(self.params),
        }

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass
class ConstColor(SurfaceNode):
    """Constant RGB color buffer used by serialized graph recipes."""

    kind: str = "const_color"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        size = int(ctx.get("size", 512))
        raw = self.params.get("rgb", [0.0, 0.0, 0.0])
        if not isinstance(raw, (list, tuple)) or len(raw) < 3:
            raw = [0.0, 0.0, 0.0]
        rgb = np.asarray([float(raw[0]), float(raw[1]), float(raw[2])], dtype=np.float64)
        if float(np.max(rgb)) > 1.0:
            rgb = rgb / 255.0
        rgb = np.clip(rgb, 0.0, 1.0)
        out = np.empty((size, size, 3), dtype=np.float64)
        out[..., 0] = rgb[0]
        out[..., 1] = rgb[1]
        out[..., 2] = rgb[2]
        return out


@dataclass
class Noise(SurfaceNode):
    """Multi-octave procedural noise (perlin-like / worley / fractal / gradient)."""

    kind: str = "noise"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        size = int(ctx.get("size", 512))
        flavour = str(self.params.get("flavour", "perlin")).lower()
        octaves = max(1, int(self.params.get("octaves", 4)))
        frequency = float(self.params.get("frequency", 6.0))
        persistence = float(self.params.get("persistence", 0.5))
        seed = _hash_seed(self.params.get("seed", 0), self.name)
        rng = np.random.default_rng(seed)
        xx, yy = _grid(size)
        out = np.zeros_like(xx)
        amp = 1.0
        norm = 0.0
        for octave in range(octaves):
            f = frequency * (2.0 ** octave)
            phase_x = rng.uniform(0.0, 2.0 * np.pi)
            phase_y = rng.uniform(0.0, 2.0 * np.pi)
            if flavour == "worley":
                # Cheap deterministic worley: distance to nearest jittered grid point.
                cells = max(2, int(round(f)))
                cx = rng.uniform(0.0, 1.0, (cells, cells))
                cy = rng.uniform(0.0, 1.0, (cells, cells))
                dx = (xx[..., None, None] * cells - np.arange(cells)[None, None, :, None] - cx[None, None]) / cells
                dy = (yy[..., None, None] * cells - np.arange(cells)[None, None, None, :] - cy[None, None]) / cells
                dist = np.sqrt(dx * dx + dy * dy)
                contribution = 1.0 - np.min(dist.reshape(size, size, -1), axis=-1) * cells * 0.5
            elif flavour == "fractal":
                contribution = (
                    np.sin(xx * f * np.pi + phase_x)
                    * np.cos(yy * f * np.pi + phase_y)
                    * np.sin((xx + yy) * f * np.pi * 0.5 + phase_x)
                )
            elif flavour == "gradient":
                gx = rng.uniform(-1.0, 1.0)
                gy = rng.uniform(-1.0, 1.0)
                norm_g = max(1e-6, np.hypot(gx, gy))
                contribution = (xx * gx + yy * gy) / norm_g
            else:  # perlin-like (deterministic Fourier sum)
                contribution = (
                    np.sin(xx * f * np.pi * 2 + phase_x)
                    * np.cos(yy * f * np.pi * 2 + phase_y)
                )
            out += contribution * amp
            norm += amp
            amp *= persistence
        out = out / max(1e-6, norm)
        return ((out + 1.0) * 0.5).clip(0.0, 1.0)


@dataclass
class Pattern(SurfaceNode):
    """Tileable structured pattern: brick, tile, weave, hex."""

    kind: str = "pattern"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        size = int(ctx.get("size", 512))
        flavour = str(self.params.get("flavour", "brick")).lower()
        cols = max(1, int(self.params.get("cols", 8)))
        rows = max(1, int(self.params.get("rows", 4)))
        mortar = max(0.0, float(self.params.get("mortar", 0.06)))
        xx, yy = _grid(size)
        if flavour == "brick":
            row_idx = np.floor(yy * rows)
            offset = (row_idx % 2) * 0.5 / cols
            u = ((xx + offset) * cols) % 1.0
            v = (yy * rows) % 1.0
            mask = ((u > mortar) & (u < 1 - mortar) & (v > mortar) & (v < 1 - mortar)).astype(np.float64)
        elif flavour == "tile":
            u = (xx * cols) % 1.0
            v = (yy * rows) % 1.0
            mask = ((u > mortar) & (u < 1 - mortar) & (v > mortar) & (v < 1 - mortar)).astype(np.float64)
        elif flavour == "weave":
            warp = (np.sin(xx * cols * np.pi * 2) ** 2)
            weft = (np.sin(yy * rows * np.pi * 2) ** 2)
            mask = np.maximum(warp, weft)
        elif flavour == "hex":
            sqrt3 = np.sqrt(3.0)
            hx = xx * cols
            hy = yy * rows / sqrt3 * 2.0
            cell_x = np.floor(hx)
            cell_y = np.floor(hy)
            offset_x = hx - cell_x - 0.5
            offset_y = hy - cell_y - 0.5
            mask = (1.0 - np.clip(np.hypot(offset_x, offset_y) * 2.0, 0.0, 1.0))
        else:
            mask = np.ones_like(xx)
        return mask


@dataclass
class ShapeSplatter(SurfaceNode):
    """Distribute small shapes (rivets/screws/buttons) over the surface."""

    kind: str = "shape_splatter"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        size = int(ctx.get("size", 512))
        count = max(1, int(self.params.get("count", 64)))
        radius = max(1.0, float(self.params.get("radius_px", 4.0)))
        shape = str(self.params.get("shape", "disc")).lower()
        seed = _hash_seed(self.params.get("seed", 0), self.name)
        rng = np.random.default_rng(seed)
        positions = rng.uniform(0.0, 1.0, (count, 2))
        out = np.zeros((size, size), dtype=np.float64)
        for px, py in positions:
            cx = int(px * (size - 1))
            cy = int(py * (size - 1))
            x0 = max(0, int(cx - radius))
            x1 = min(size, int(cx + radius + 1))
            y0 = max(0, int(cy - radius))
            y1 = min(size, int(cy + radius + 1))
            yy, xx = np.indices((y1 - y0, x1 - x0))
            dx = xx + x0 - cx
            dy = yy + y0 - cy
            if shape == "square":
                stamp = (np.maximum(np.abs(dx), np.abs(dy)) <= radius).astype(np.float64)
            elif shape == "cross":
                stamp = ((np.abs(dx) <= radius * 0.2) | (np.abs(dy) <= radius * 0.2)).astype(np.float64)
                stamp *= (np.maximum(np.abs(dx), np.abs(dy)) <= radius).astype(np.float64)
            else:  # disc
                stamp = np.clip(1.0 - np.hypot(dx, dy) / radius, 0.0, 1.0)
            out[y0:y1, x0:x1] = np.maximum(out[y0:y1, x0:x1], stamp)
        return out


@dataclass
class Warp(SurfaceNode):
    """Deterministic UV-space warp/distort to break regularity."""

    kind: str = "warp"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        source_name = self.inputs.get("source")
        if not source_name:
            return np.zeros((int(ctx.get("size", 512)),) * 2, dtype=np.float64)
        source = ctx["buffers"][source_name]
        size = source.shape[0]
        amplitude = float(self.params.get("amplitude", 0.04))
        frequency = float(self.params.get("frequency", 3.0))
        seed = _hash_seed(self.params.get("seed", 0), self.name)
        rng = np.random.default_rng(seed)
        phase_x = rng.uniform(0.0, 2.0 * np.pi)
        phase_y = rng.uniform(0.0, 2.0 * np.pi)
        xx, yy = _grid(size)
        u = (xx + amplitude * np.sin(yy * frequency * np.pi * 2 + phase_x))
        v = (yy + amplitude * np.cos(xx * frequency * np.pi * 2 + phase_y))
        u_idx = np.clip((u * (size - 1)).astype(np.int64), 0, size - 1)
        v_idx = np.clip((v * (size - 1)).astype(np.int64), 0, size - 1)
        return source[v_idx, u_idx]


@dataclass
class Blend(SurfaceNode):
    """Pixel-wise blend of two buffers with a mask.

    Modes: ``add``, ``subtract``, ``multiply``, ``overlay``, ``screen``,
    ``mask`` (lerp by mask). All inputs are expected in [0, 1].
    """

    kind: str = "blend"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        a_name = self.inputs.get("a")
        b_name = self.inputs.get("b")
        mask_name = self.inputs.get("mask")
        if not a_name:
            return np.zeros((int(ctx.get("size", 512)),) * 2, dtype=np.float64)
        a = ctx["buffers"][a_name]
        b = ctx["buffers"].get(b_name) if b_name else np.zeros_like(a)
        mask = ctx["buffers"].get(mask_name) if mask_name else None
        if b is None:
            b = np.zeros_like(a)
        # Broadcast scalar buffers to match shape.
        if a.shape != b.shape:
            b = np.broadcast_to(b, a.shape)
        mode = str(self.params.get("mode", "add")).lower()
        if mode == "subtract":
            out = a - b
        elif mode == "multiply":
            out = a * b
        elif mode == "overlay":
            out = np.where(a < 0.5, 2.0 * a * b, 1.0 - 2.0 * (1.0 - a) * (1.0 - b))
        elif mode == "screen":
            out = 1.0 - (1.0 - a) * (1.0 - b)
        elif mode == "mask":
            m = mask if mask is not None else np.ones_like(a) * 0.5
            out = a * (1.0 - m) + b * m
        else:  # add
            out = a + b
        return np.clip(out, 0.0, 1.0)


@dataclass
class Normal(SurfaceNode):
    """Derive a tangent-space normal map from a height field."""

    kind: str = "normal"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        height_name = self.inputs.get("height")
        if not height_name:
            return np.zeros((int(ctx.get("size", 512)), int(ctx.get("size", 512)), 3), dtype=np.float64)
        height = np.asarray(ctx["buffers"][height_name], dtype=np.float64)
        strength = float(self.params.get("strength", 1.0))
        # Sobel derivatives.
        dx = np.zeros_like(height)
        dy = np.zeros_like(height)
        dx[:, 1:-1] = (height[:, 2:] - height[:, :-2]) * 0.5 * strength
        dy[1:-1, :] = (height[2:, :] - height[:-2, :]) * 0.5 * strength
        nz = np.ones_like(height)
        denom = np.sqrt(dx * dx + dy * dy + nz * nz)
        nx = -dx / denom
        ny = -dy / denom
        nzc = nz / denom
        normal = np.stack([nx, ny, nzc], axis=-1)
        return (normal + 1.0) * 0.5


@dataclass
class CurvatureSmooth(SurfaceNode):
    """Smooth curvature derived from a normal/height field; drives wear masks."""

    kind: str = "curvature_smooth"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        normal_name = self.inputs.get("normal")
        if not normal_name:
            return np.full((int(ctx.get("size", 512)),) * 2, 0.5, dtype=np.float64)
        normal = ctx["buffers"][normal_name]
        radius = max(1, int(self.params.get("radius", 3)))
        # Peaks and valleys: divergence of the (decoded) normal.
        nx = normal[..., 0] * 2.0 - 1.0
        ny = normal[..., 1] * 2.0 - 1.0
        dnx = np.zeros_like(nx)
        dny = np.zeros_like(ny)
        dnx[:, 1:-1] = nx[:, 2:] - nx[:, :-2]
        dny[1:-1, :] = ny[2:, :] - ny[:-2, :]
        curvature = (dnx + dny) * 0.5
        # Box blur ``radius`` times.
        for _ in range(radius):
            blurred = np.zeros_like(curvature)
            blurred[1:-1, 1:-1] = (
                curvature[:-2, 1:-1] + curvature[2:, 1:-1]
                + curvature[1:-1, :-2] + curvature[1:-1, 2:]
                + curvature[1:-1, 1:-1]
            ) / 5.0
            curvature = blurred
        return ((curvature + 1.0) * 0.5).clip(0.0, 1.0)


@dataclass
class AO(SurfaceNode):
    """Cheap deterministic AO from a height/normal field."""

    kind: str = "ao"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        height_name = self.inputs.get("height")
        radius = max(1, int(self.params.get("radius", 5)))
        if not height_name:
            return np.ones((int(ctx.get("size", 512)),) * 2, dtype=np.float64)
        height = ctx["buffers"][height_name]
        # Local-mean gap as cheap proxy: cavities (low height vs neighbourhood) → darker.
        source_height = height.copy()
        smoothed = height.copy()
        for _ in range(radius):
            padded = np.pad(smoothed, 1, mode="edge")
            blurred = (
                padded[:-2, 1:-1]
                + padded[2:, 1:-1]
                + padded[1:-1, :-2]
                + padded[1:-1, 2:]
                + padded[1:-1, 1:-1]
            ) / 5.0
            smoothed = blurred
        gap = smoothed - source_height
        ao = np.clip(1.0 - np.maximum(0.0, gap) * 2.5, 0.0, 1.0)
        return ao


@dataclass
class SlopeBlur(SurfaceNode):
    """Slope-directed blur/erode/dilate for authored height fields."""

    kind: str = "slope_blur"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        size = int(ctx.get("size", 512))
        source = _input_scalar(ctx, self.inputs, "source")
        slope = _input_scalar(ctx, self.inputs, "slope", default=0.5)
        samples = max(1, min(32, int(self.params.get("samples", 6))))
        strength = max(0.0, float(self.params.get("strength_px", self.params.get("strength", 2.0))))
        mode = str(self.params.get("mode", "blur")).strip().lower()
        dy, dx = np.gradient(slope)
        length = np.sqrt(dx * dx + dy * dy)
        dx = np.divide(dx, length, out=np.zeros_like(dx), where=length > 1e-8)
        dy = np.divide(dy, length, out=np.zeros_like(dy), where=length > 1e-8)
        yy, xx = np.indices((size, size), dtype=np.float64)
        if mode in {"erode", "min"}:
            out = source.copy()
        elif mode in {"dilate", "max"}:
            out = source.copy()
        else:
            out = source.copy()
        for index in range(1, samples + 1):
            amount = strength * (float(index) / float(samples))
            x_idx = np.clip(np.round(xx - dx * amount).astype(np.int64), 0, size - 1)
            y_idx = np.clip(np.round(yy - dy * amount).astype(np.int64), 0, size - 1)
            sample = source[y_idx, x_idx]
            if mode in {"erode", "min"}:
                out = np.minimum(out, sample)
            elif mode in {"dilate", "max"}:
                out = np.maximum(out, sample)
            else:
                out += sample
        if mode not in {"erode", "min", "dilate", "max"}:
            out = out / float(samples + 1)
        return np.clip(out, 0.0, 1.0)


@dataclass
class HistogramScan(SurfaceNode):
    """Convert a scalar buffer into a controllable binary/soft mask."""

    kind: str = "histogram_scan"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        source = _input_scalar(ctx, self.inputs, "source")
        threshold = float(self.params.get("threshold", self.params.get("position", 0.5)))
        softness = max(1e-6, float(self.params.get("softness", self.params.get("width", 0.08))))
        contrast = max(0.0, float(self.params.get("contrast", 1.0)))
        out = np.clip((source - threshold) / softness + 0.5, 0.0, 1.0)
        if contrast > 0.0:
            out = np.clip((out - 0.5) * contrast + 0.5, 0.0, 1.0)
        if bool(self.params.get("invert", False)):
            out = 1.0 - out
        return out


@dataclass
class Levels(SurfaceNode):
    """Remap scalar or color ranges with input/output levels and gamma."""

    kind: str = "levels"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        source_name = self.inputs.get("source")
        size = int(ctx.get("size", 512))
        source = ctx.get("buffers", {}).get(source_name) if source_name else None
        if source is None:
            source = np.zeros((size, size), dtype=np.float64)
        arr = np.asarray(source, dtype=np.float64)
        low = float(self.params.get("low", self.params.get("in_low", 0.0)))
        high = float(self.params.get("high", self.params.get("in_high", 1.0)))
        gamma = max(1e-6, float(self.params.get("gamma", 1.0)))
        out_low = float(self.params.get("out_low", 0.0))
        out_high = float(self.params.get("out_high", 1.0))
        out = np.clip((arr - low) / max(1e-8, high - low), 0.0, 1.0)
        out = np.power(out, 1.0 / gamma)
        return np.clip(out_low + out * (out_high - out_low), 0.0, 1.0)


@dataclass
class EdgeDetect(SurfaceNode):
    """Gradient-magnitude edge detector for masks and height accents."""

    kind: str = "edge_detect"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        source = _input_scalar(ctx, self.inputs, "source")
        radius = max(0, int(self.params.get("radius", 0)))
        if radius:
            source = _box_blur(source, radius)
        dy, dx = np.gradient(source)
        edge = np.sqrt(dx * dx + dy * dy)
        max_edge = float(np.max(edge))
        if max_edge > 1e-8:
            edge = edge / max_edge
        strength = max(0.0, float(self.params.get("strength", 1.0)))
        edge = np.clip(edge * strength, 0.0, 1.0)
        threshold = self.params.get("threshold")
        if threshold is not None:
            softness = max(1e-6, float(self.params.get("softness", 0.08)))
            edge = np.clip((edge - float(threshold)) / softness + 0.5, 0.0, 1.0)
        if bool(self.params.get("invert", False)):
            edge = 1.0 - edge
        return edge


@dataclass
class GradientMap(SurfaceNode):
    """Map a scalar buffer through deterministic color stops."""

    kind: str = "gradient_map"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        source = _input_scalar(ctx, self.inputs, "source")
        stops = [_color_stop(item) for item in self.params.get("stops", [])]
        stops = [item for item in stops if item is not None]
        if not stops:
            low = self.params.get("low_color", [0.0, 0.0, 0.0])
            high = self.params.get("high_color", [1.0, 1.0, 1.0])
            stops = [
                _color_stop([0.0, low]) or (0.0, np.zeros(3, dtype=np.float64)),
                _color_stop([1.0, high]) or (1.0, np.ones(3, dtype=np.float64)),
            ]
        stops = sorted(stops, key=lambda item: item[0])
        out = np.zeros(source.shape + (3,), dtype=np.float64)
        previous_pos, previous_color = stops[0]
        out[:] = previous_color
        for next_pos, next_color in stops[1:]:
            span = max(1e-8, float(next_pos) - float(previous_pos))
            t = np.clip((source - float(previous_pos)) / span, 0.0, 1.0)[..., None]
            mixed = previous_color * (1.0 - t) + next_color * t
            out = np.where((source[..., None] >= float(previous_pos)), mixed, out)
            previous_pos, previous_color = next_pos, next_color
        out = np.where((source[..., None] >= float(stops[-1][0])), stops[-1][1], out)
        return np.clip(out, 0.0, 1.0)


@dataclass
class PositionMask(SurfaceNode):
    """Mask by object/world position, falling back to UV position when absent."""

    kind: str = "position_mask"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        size = int(ctx.get("size", 512))
        axis = str(self.params.get("axis", "y")).strip().lower()
        position_name = self.inputs.get("position")
        position = ctx.get("buffers", {}).get(position_name) if position_name else None
        if position is None:
            position = ctx.get("attributes", {}).get("@P")
        if isinstance(position, np.ndarray) and position.ndim == 3 and position.shape[-1] >= 3:
            pos = np.asarray(position, dtype=np.float64)
            if pos.shape[:2] != (size, size):
                channels = [_scalar_buffer(pos[..., channel], size) for channel in range(3)]
                pos = np.stack(channels, axis=-1)
            axis_index = {"x": 0, "u": 0, "y": 1, "v": 1, "z": 2}.get(axis, 1)
            coord = pos[..., axis_index]
            coord_min = float(self.params.get("domain_min", np.min(coord)))
            coord_max = float(self.params.get("domain_max", np.max(coord)))
            coord = (coord - coord_min) / max(1e-8, coord_max - coord_min)
        else:
            xx, yy = _grid(size)
            if axis in {"x", "u"}:
                coord = xx
            elif axis in {"z"}:
                coord = np.zeros_like(xx)
            else:
                coord = yy
        low = float(self.params.get("min", self.params.get("low", 0.0)))
        high = float(self.params.get("max", self.params.get("high", 1.0)))
        softness = max(1e-6, float(self.params.get("softness", 0.04)))
        mode = str(self.params.get("mode", "band")).strip().lower()
        if mode in {"above", "greater"}:
            mask = _smoothstep(low, low + softness, coord)
        elif mode in {"below", "less"}:
            mask = 1.0 - _smoothstep(high - softness, high, coord)
        else:
            mask = _smoothstep(low, low + softness, coord)
            mask *= 1.0 - _smoothstep(high - softness, high, coord)
        if bool(self.params.get("invert", False)):
            mask = 1.0 - mask
        return np.clip(mask, 0.0, 1.0)


@dataclass
class WorldYMask(PositionMask):
    """Convenience world/vertical Y mask for grime, wear, and altitude bands."""

    kind: str = "world_y_mask"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        original_params = self.params
        self.params = {**original_params, "axis": original_params.get("axis", "y")}
        try:
            return super().eval(ctx)
        finally:
            self.params = original_params


@dataclass
class Mask(SurfaceNode):
    """Mask node -- evaluates a mask expression.

    The expression may reference attribute mini-language tokens
    (``@curvature``, ``@ao``, ``@N`` etc.) and is rewritten into a
    numpy expression. Common smart-mask presets are recognised so
    callers can author by name (``cavity``, ``edge_wear``, ``top_dirt``).
    """

    kind: str = "mask"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        preset = str(self.params.get("preset", "")).lower()
        size = int(ctx.get("size", 512))
        attribs = ctx.get("attributes", {})
        curvature = attribs.get("@curvature", ctx["buffers"].get(self.inputs.get("curvature", "")))
        ao = attribs.get("@ao", ctx["buffers"].get(self.inputs.get("ao", "")))
        normal = attribs.get("@N", ctx["buffers"].get(self.inputs.get("normal", "")))
        position = attribs.get("@P", ctx["buffers"].get(self.inputs.get("position", "")))
        if curvature is None:
            curvature = np.full((size, size), 0.5, dtype=np.float64)
        if ao is None:
            ao = np.ones((size, size), dtype=np.float64)
        if preset == "cavity":
            return (1.0 - curvature).clip(0.0, 1.0)
        if preset == "edge_wear":
            wear = curvature.clip(0.0, 1.0)
            if self.params.get("ao_gate", False):
                wear = wear * ao
            return wear
        if preset == "top_dirt":
            ny = (normal[..., 1] if normal is not None and normal.ndim == 3 else None)
            if ny is None:
                return np.full((size, size), 0.5, dtype=np.float64)
            t = (ny - 0.5) * 2.0  # decode
            return np.clip((t - 0.5) / 0.5, 0.0, 1.0)
        if preset == "bottom_grime":
            ny = (normal[..., 1] if normal is not None and normal.ndim == 3 else None)
            if ny is None:
                return np.full((size, size), 0.5, dtype=np.float64)
            t = (ny - 0.5) * 2.0
            return np.clip((-t - 0.5) / 0.5, 0.0, 1.0)
        if preset == "slope":
            ny = (normal[..., 1] if normal is not None and normal.ndim == 3 else None)
            if ny is None:
                return np.full((size, size), 0.5, dtype=np.float64)
            t = (ny - 0.5) * 2.0
            lo = float(self.params.get("min", 0.2))
            hi = float(self.params.get("max", 0.8))
            return np.clip((t - lo) / max(1e-6, hi - lo), 0.0, 1.0)
        if preset == "seam":
            return ctx["buffers"].get(self.inputs.get("seam", ""), np.zeros((size, size), dtype=np.float64))
        if preset == "decal_zone":
            return ctx["buffers"].get(self.inputs.get("decal", ""), np.zeros((size, size), dtype=np.float64))
        # Plain custom expression like "@curvature * (1 - @ao)" -- evaluated safely.
        expr = str(self.params.get("expression", "@curvature"))
        local = {
            "curvature": curvature,
            "ao": ao,
            "np": np,
        }
        safe = expr.replace("@curvature", "curvature").replace("@ao", "ao")
        try:
            value = eval(safe, {"__builtins__": {}}, local)  # noqa: S307 - sandboxed env
            value = np.asarray(value, dtype=np.float64)
            if value.ndim == 0:
                value = np.full((size, size), float(value), dtype=np.float64)
            return value.clip(0.0, 1.0)
        except Exception:  # pragma: no cover - defensive
            return curvature


@dataclass
class Layer(SurfaceNode):
    """A composited material layer: (basecolor, mask, blend mode)."""

    kind: str = "layer"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        base_name = self.inputs.get("base")
        layer_name = self.inputs.get("layer")
        mask_name = self.inputs.get("mask")
        if not base_name:
            return np.zeros((int(ctx.get("size", 512)), int(ctx.get("size", 512)), 3), dtype=np.float64)
        base = ctx["buffers"][base_name]
        layer = ctx["buffers"].get(layer_name) if layer_name else base
        mask = ctx["buffers"].get(mask_name) if mask_name else np.ones(base.shape[:2], dtype=np.float64)
        if mask.ndim == 2 and base.ndim == 3:
            mask = mask[..., None]
        if layer.ndim == 2 and base.ndim == 3:
            layer = np.repeat(layer[..., None], 3, axis=-1)
        return base * (1.0 - mask) + layer * mask


@dataclass
class Output(SurfaceNode):
    """Terminal node binding a buffer to a PBR output channel."""

    kind: str = "output"

    def eval(self, ctx: dict[str, Any]) -> np.ndarray:
        source_name = self.inputs.get("source")
        if not source_name:
            return np.zeros((int(ctx.get("size", 512)),) * 2, dtype=np.float64)
        return ctx["buffers"][source_name]


NODE_CLASSES: dict[str, type[SurfaceNode]] = {
    "const_color": ConstColor,
    "noise": Noise,
    "pattern": Pattern,
    "shape_splatter": ShapeSplatter,
    "warp": Warp,
    "blend": Blend,
    "normal": Normal,
    "curvature_smooth": CurvatureSmooth,
    "ao": AO,
    "slope_blur": SlopeBlur,
    "slopeblur": SlopeBlur,
    "histogram_scan": HistogramScan,
    "histogram": HistogramScan,
    "histogramscan": HistogramScan,
    "levels": Levels,
    "level": Levels,
    "edge_detect": EdgeDetect,
    "edgedetect": EdgeDetect,
    "gradient_map": GradientMap,
    "gradientmap": GradientMap,
    "position_mask": PositionMask,
    "positionmask": PositionMask,
    "world_y_mask": WorldYMask,
    "world_y": WorldYMask,
    "worldymask": WorldYMask,
    "mask": Mask,
    "layer": Layer,
    "output": Output,
}


def node_from_dict(payload: dict[str, Any]) -> SurfaceNode:
    """Reconstruct a typed node from a dict-shaped IR entry."""
    kind = str(payload.get("kind", "node")).lower()
    cls = NODE_CLASSES.get(kind, SurfaceNode)
    return cls(
        name=str(payload.get("name", "")),
        kind=kind,
        inputs=dict(payload.get("inputs", {})),
        params=dict(payload.get("params", {})),
    )
