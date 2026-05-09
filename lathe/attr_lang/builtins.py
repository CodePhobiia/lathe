"""Built-in functions and namespaces for the attribute mini-language.

Each built-in is a Python callable taking ``(context, *positional, **kwargs)``
and returning a value. ``context`` is the
:class:`~lathe.attr_lang.evaluator.EvalContext` so built-ins can read
auto-derived signals (``@P``, ``@N``, ``@curvature``, ``@ao``, ``@height``,
``@up_dot``, ``@id``, ``@material_zone``, ``@uv``, ``@world_pos``,
``@P_local``, ``@face_index``, ``@vertex_index``) and emit deterministic
results.

Implementations are intentionally pure-Python and dependency-free. They
treat scalars and 3-tuples uniformly via small vector helpers below. They
prefer determinism over fidelity — the goal is a stable evaluator that the
deterministic surface stages can rely on, not a high-performance shader.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

from .errors import EvalError, TypeMismatchError, UnknownBuiltinError

Value = Any
BuiltinFn = Callable[..., Value]


# ----------------------------------------------------------------------
# Vector helpers (operate on scalars or fixed-length tuples uniformly)
# ----------------------------------------------------------------------


def _is_vec(v: Value) -> bool:
    return isinstance(v, tuple) and 2 <= len(v) <= 4 and all(
        isinstance(c, (int, float, bool)) for c in v
    )


def _to_float(v: Value, *, ctx_name: str = "value") -> float:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    raise TypeMismatchError(f"expected scalar for {ctx_name}, got {type(v).__name__}")


def _vec_op(a: Value, b: Value, fn: Callable[[float, float], float]) -> Value:
    if _is_vec(a) and _is_vec(b):
        if len(a) != len(b):
            raise TypeMismatchError(
                f"vector size mismatch: len {len(a)} vs len {len(b)}"
            )
        return tuple(fn(float(x), float(y)) for x, y in zip(a, b))
    if _is_vec(a):
        bf = _to_float(b)
        return tuple(fn(float(x), bf) for x in a)
    if _is_vec(b):
        af = _to_float(a)
        return tuple(fn(af, float(y)) for y in b)
    return fn(_to_float(a), _to_float(b))


def _unary_vec(a: Value, fn: Callable[[float], float]) -> Value:
    if _is_vec(a):
        return tuple(fn(float(x)) for x in a)
    return fn(_to_float(a))


# ----------------------------------------------------------------------
# Math built-ins
# ----------------------------------------------------------------------


def _b_min(_ctx, *args: Value) -> Value:
    if not args:
        raise EvalError("min() requires at least one argument")
    if len(args) == 1 and isinstance(args[0], (list, tuple)) and not _is_vec(args[0]):
        return min(_to_float(x) for x in args[0])
    return min(_to_float(x) for x in args)


def _b_max(_ctx, *args: Value) -> Value:
    if not args:
        raise EvalError("max() requires at least one argument")
    if len(args) == 1 and isinstance(args[0], (list, tuple)) and not _is_vec(args[0]):
        return max(_to_float(x) for x in args[0])
    return max(_to_float(x) for x in args)


def _b_clamp(_ctx, x: Value, lo: Value = 0.0, hi: Value = 1.0) -> Value:
    return _vec_op(_vec_op(x, lo, max), hi, min)


def _smoothstep_scalar(lo: float, hi: float, x: float) -> float:
    if hi == lo:
        return 0.0 if x < lo else 1.0
    t = max(0.0, min(1.0, (x - lo) / (hi - lo)))
    return t * t * (3.0 - 2.0 * t)


def _b_smoothstep(_ctx, lo: Value, hi: Value, x: Value) -> Value:
    if _is_vec(x):
        return tuple(
            _smoothstep_scalar(_to_float(lo), _to_float(hi), float(c)) for c in x
        )
    return _smoothstep_scalar(_to_float(lo), _to_float(hi), _to_float(x))


def _b_step(_ctx, edge: Value, x: Value) -> Value:
    if _is_vec(x):
        e = _to_float(edge)
        return tuple(0.0 if float(c) < e else 1.0 for c in x)
    return 0.0 if _to_float(x) < _to_float(edge) else 1.0


def _b_mix(_ctx, a: Value, b: Value, t: Value) -> Value:
    return _vec_op(a, b, lambda x, y: x + (y - x) * _to_float(t))


def _b_dot(_ctx, a: Value, b: Value) -> Value:
    if not (_is_vec(a) and _is_vec(b)):
        raise TypeMismatchError("dot() expects two vectors")
    if len(a) != len(b):
        raise TypeMismatchError("dot() vector size mismatch")
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _b_length(_ctx, v: Value) -> Value:
    if _is_vec(v):
        return math.sqrt(sum(float(c) * float(c) for c in v))
    return abs(_to_float(v))


def _b_normalize(_ctx, v: Value) -> Value:
    if not _is_vec(v):
        raise TypeMismatchError("normalize() expects a vector")
    mag = math.sqrt(sum(float(c) * float(c) for c in v))
    if mag == 0.0:
        return tuple(0.0 for _ in v)
    return tuple(float(c) / mag for c in v)


def _b_abs(_ctx, x: Value) -> Value:
    return _unary_vec(x, abs)


def _b_floor(_ctx, x: Value) -> Value:
    return _unary_vec(x, math.floor)


def _b_ceil(_ctx, x: Value) -> Value:
    return _unary_vec(x, math.ceil)


def _b_sin(_ctx, x: Value) -> Value:
    return _unary_vec(x, math.sin)


def _b_cos(_ctx, x: Value) -> Value:
    return _unary_vec(x, math.cos)


def _b_pow(_ctx, x: Value, exponent: Value) -> Value:
    return _vec_op(x, exponent, lambda a, b: math.pow(a, b))


def _b_sqrt(_ctx, x: Value) -> Value:
    return _unary_vec(x, math.sqrt)


# ----------------------------------------------------------------------
# Noise / pattern built-ins (deterministic stand-ins)
#
# These are intentionally simple. They are reproducible given the same
# context+args; richer kernels can be swapped in later behind the same
# call signatures.
# ----------------------------------------------------------------------


def _hash_floats(*xs: float) -> float:
    """A tiny deterministic hash of floats into [0,1)."""

    s = 2654435761
    for x in xs:
        # Mix the bit pattern via integer trickery.
        bits = int.from_bytes(
            int(round((x % 1024.0) * 1e6)).to_bytes(8, "little", signed=True),
            "little",
            signed=True,
        )
        s ^= bits & 0xFFFFFFFFFFFFFFFF
        s = (s * 1000003) & 0xFFFFFFFFFFFFFFFF
    return ((s >> 17) & 0xFFFFFF) / float(0xFFFFFF)


def _sample_position(ctx) -> tuple[float, float, float]:
    p = ctx.lookup_attr("P", default=(0.0, 0.0, 0.0))
    if _is_vec(p) and len(p) >= 3:
        return (float(p[0]), float(p[1]), float(p[2]))
    return (0.0, 0.0, 0.0)


def _b_noise(ctx, kind: Value = "perlin", *, scale: Value = 1.0,
             octaves: Value = 4, seed: Value = 0, **_: Any) -> Value:
    kind_str = kind if isinstance(kind, str) else getattr(kind, "value", "perlin")
    if isinstance(kind_str, str) is False:
        kind_str = "perlin"
    s = _to_float(scale, ctx_name="scale")
    o = max(1, int(_to_float(octaves, ctx_name="octaves")))
    sd = _to_float(seed, ctx_name="seed")
    px, py, pz = _sample_position(ctx)
    accum = 0.0
    amp = 1.0
    norm = 0.0
    for i in range(o):
        accum += amp * _hash_floats(
            px * s * (i + 1), py * s * (i + 1), pz * s * (i + 1), sd, ord(kind_str[0])
        )
        norm += amp
        amp *= 0.5
    return accum / norm if norm > 0 else 0.0


def _b_pattern(ctx, kind: Value = "brick", *, scale: Value = 1.0, **_: Any) -> Value:
    kind_str = kind if isinstance(kind, str) else "brick"
    s = _to_float(scale, ctx_name="scale")
    px, py, _pz = _sample_position(ctx)
    if kind_str == "brick":
        row = math.floor(py * s)
        offset = 0.5 if int(row) % 2 == 0 else 0.0
        u = (px * s + offset) % 1.0
        v = (py * s) % 1.0
        return 1.0 if (0.05 < u < 0.95 and 0.05 < v < 0.95) else 0.0
    if kind_str == "tile":
        u = (px * s) % 1.0
        v = (py * s) % 1.0
        return 1.0 if (0.05 < u < 0.95 and 0.05 < v < 0.95) else 0.0
    if kind_str == "weave":
        u = math.floor(px * s) + math.floor(py * s)
        return float(int(u) % 2)
    raise EvalError(f"unknown pattern kind {kind_str!r}")


# ----------------------------------------------------------------------
# Mask helpers — return a float in [0,1].
# ----------------------------------------------------------------------


def _b_mask_curvature_peaks(ctx, *, threshold: Value = 0.3) -> Value:
    k = _to_float(ctx.lookup_attr("curvature", default=0.0))
    t = _to_float(threshold)
    return _smoothstep_scalar(t, 1.0, k)


def _b_mask_curvature_valleys(ctx, *, threshold: Value = 0.3) -> Value:
    k = _to_float(ctx.lookup_attr("curvature", default=0.0))
    t = _to_float(threshold)
    return _smoothstep_scalar(t, 1.0, -k)


def _b_mask_ao_below(ctx, threshold: Value = 0.5) -> Value:
    ao = _to_float(ctx.lookup_attr("ao", default=1.0))
    return 1.0 - _smoothstep_scalar(_to_float(threshold) - 0.05, _to_float(threshold) + 0.05, ao)


def _b_mask_ao_above(ctx, threshold: Value = 0.5) -> Value:
    ao = _to_float(ctx.lookup_attr("ao", default=1.0))
    return _smoothstep_scalar(_to_float(threshold) - 0.05, _to_float(threshold) + 0.05, ao)


def _b_mask_slope_above(ctx, angle_deg: Value = 30.0) -> Value:
    up = ctx.lookup_attr("up_dot", default=None)
    if up is None:
        n = ctx.lookup_attr("N", default=(0.0, 0.0, 1.0))
        up = float(n[2]) if _is_vec(n) and len(n) >= 3 else 0.0
    angle = math.radians(_to_float(angle_deg))
    cutoff = math.cos(angle)
    return 1.0 - _smoothstep_scalar(cutoff - 0.05, cutoff + 0.05, _to_float(up))


def _b_mask_world_up_facing(ctx, *, min_dot: Value = 0.7) -> Value:
    up = ctx.lookup_attr("up_dot", default=None)
    if up is None:
        n = ctx.lookup_attr("N", default=(0.0, 0.0, 1.0))
        up = float(n[2]) if _is_vec(n) and len(n) >= 3 else 0.0
    return _smoothstep_scalar(_to_float(min_dot) - 0.05, _to_float(min_dot) + 0.05, _to_float(up))


# ----------------------------------------------------------------------
# Palette / ramp built-ins
# ----------------------------------------------------------------------


def _b_palette_lookup(ctx, name: Value, t: Value) -> Value:
    palette = ctx.resolve_palette(str(name))
    return _ramp_linear(_to_float(t), palette)


def _b_palette_swatch(ctx, name: Value, idx: Value) -> Value:
    palette = ctx.resolve_palette(str(name))
    if not palette:
        raise EvalError(f"palette {name!r} is empty")
    i = int(_to_float(idx)) % len(palette)
    return palette[i]


def _ramp_linear(t: float, colors: Sequence[Value]) -> Value:
    if not colors:
        raise EvalError("ramp requires at least one color")
    if len(colors) == 1:
        return colors[0]
    t = max(0.0, min(1.0, t))
    scaled = t * (len(colors) - 1)
    i = int(scaled)
    frac = scaled - i
    if i >= len(colors) - 1:
        return colors[-1]
    a, b = colors[i], colors[i + 1]
    if _is_vec(a) and _is_vec(b):
        return tuple(float(x) + (float(y) - float(x)) * frac for x, y in zip(a, b))
    return _to_float(a) + (_to_float(b) - _to_float(a)) * frac


def _ramp_hermite(t: float, colors: Sequence[Value]) -> Value:
    if not colors:
        raise EvalError("ramp requires at least one color")
    if len(colors) == 1:
        return colors[0]
    t = max(0.0, min(1.0, t))
    scaled = t * (len(colors) - 1)
    i = int(scaled)
    frac = scaled - i
    smoothed = frac * frac * (3.0 - 2.0 * frac)
    if i >= len(colors) - 1:
        return colors[-1]
    a, b = colors[i], colors[i + 1]
    if _is_vec(a) and _is_vec(b):
        return tuple(
            float(x) + (float(y) - float(x)) * smoothed for x, y in zip(a, b)
        )
    return _to_float(a) + (_to_float(b) - _to_float(a)) * smoothed


def _b_ramp(_ctx, t: Value, colors: Value) -> Value:
    if not isinstance(colors, (list, tuple)) or _is_vec(colors):
        raise TypeMismatchError("ramp expects a list of colors as its second argument")
    return _ramp_linear(_to_float(t), list(colors))


def _b_ramp_hermite(_ctx, t: Value, colors: Value) -> Value:
    if not isinstance(colors, (list, tuple)) or _is_vec(colors):
        raise TypeMismatchError(
            "ramp.hermite expects a list of colors as its second argument"
        )
    return _ramp_hermite(_to_float(t), list(colors))


# ----------------------------------------------------------------------
# Public registry
# ----------------------------------------------------------------------


# Top-level callable identifiers. Members of namespaces (``palette.lookup``,
# ``mask.curvature_peaks``, etc.) live in ``NAMESPACES``.
TOP_LEVEL_BUILTINS: dict[str, BuiltinFn] = {
    "min": _b_min,
    "max": _b_max,
    "clamp": _b_clamp,
    "smoothstep": _b_smoothstep,
    "step": _b_step,
    "mix": _b_mix,
    "dot": _b_dot,
    "length": _b_length,
    "normalize": _b_normalize,
    "abs": _b_abs,
    "floor": _b_floor,
    "ceil": _b_ceil,
    "sin": _b_sin,
    "cos": _b_cos,
    "pow": _b_pow,
    "sqrt": _b_sqrt,
    "noise": _b_noise,
    "pattern": _b_pattern,
    # Mask helpers also accessible bare (per spec example
    # ``mask = curvature_peaks(threshold=0.3) & ao_below(0.5)``).
    "curvature_peaks": _b_mask_curvature_peaks,
    "curvature_valleys": _b_mask_curvature_valleys,
    "ao_below": _b_mask_ao_below,
    "ao_above": _b_mask_ao_above,
    "slope_above": _b_mask_slope_above,
    "world_up_facing": _b_mask_world_up_facing,
}


# Namespaces are dict-of-callables. Member access on these names produces a
# bound callable; member access can also dot through to nested entries
# (e.g. ``ramp.hermite``).
NAMESPACES: dict[str, dict[str, BuiltinFn]] = {
    "palette": {
        "lookup": _b_palette_lookup,
        "swatch": _b_palette_swatch,
    },
    "mask": {
        "curvature_peaks": _b_mask_curvature_peaks,
        "curvature_valleys": _b_mask_curvature_valleys,
        "ao_below": _b_mask_ao_below,
        "ao_above": _b_mask_ao_above,
        "slope_above": _b_mask_slope_above,
        "world_up_facing": _b_mask_world_up_facing,
    },
    # ramp behaves both as a callable (linear) and as a namespace (hermite).
    "ramp": {
        "hermite": _b_ramp_hermite,
    },
}


# Namespaces that are *also* directly callable when used without member access.
DIRECTLY_CALLABLE_NAMESPACES: dict[str, BuiltinFn] = {
    "ramp": _b_ramp,
}


# Constants that resolve at parse-time inside the expression body.
CONSTANTS: dict[str, Value] = {
    "pi": math.pi,
    "tau": math.tau,
    "world_up": (0.0, 0.0, 1.0),
}


def resolve_top_level(name: str) -> BuiltinFn | dict[str, BuiltinFn] | Value:
    """Resolve a bare identifier to a callable, namespace dict, or constant.

    Raises :class:`UnknownBuiltinError` if the name is not registered.
    """

    if name in TOP_LEVEL_BUILTINS:
        return TOP_LEVEL_BUILTINS[name]
    if name in NAMESPACES:
        return NAMESPACES[name]
    if name in CONSTANTS:
        return CONSTANTS[name]
    raise UnknownBuiltinError(f"unknown identifier {name!r}")
