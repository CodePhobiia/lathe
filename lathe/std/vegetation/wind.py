"""Wind animation program (vertex-band sway hint).

Lathe doesn't run a runtime, so wind manifests as:
1. A per-vertex (or per-primitive) ``wind_band`` integer attribute
   (0 = trunk/rigid, 1 = main branches, 2 = leaves/secondary).
2. A recommended sway parameter dict for the engine to consume:
   per-band amplitude (cm), frequency (Hz), turbulence factor, and
   a global wind direction.

This output goes into the ``vegetation_library_ir`` bundle so engine
adapters (Unity/Unreal/Godot/Roblox) can map it onto their own wind
shader inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WindProgram:
    """A compiled wind program."""

    name: str
    wind_direction: tuple[float, float, float] = (1.0, 0.0, 0.0)
    base_strength: float = 1.0
    band_amplitudes_cm: list[float] = field(default_factory=lambda: [0.0, 1.5, 4.0])
    band_frequencies_hz: list[float] = field(default_factory=lambda: [0.0, 0.6, 1.4])
    band_turbulence: list[float] = field(default_factory=lambda: [0.0, 0.2, 0.55])
    gust_period_s: float = 6.0
    gust_strength: float = 0.4

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "wind_direction": list(self.wind_direction),
            "base_strength": self.base_strength,
            "band_amplitudes_cm": list(self.band_amplitudes_cm),
            "band_frequencies_hz": list(self.band_frequencies_hz),
            "band_turbulence": list(self.band_turbulence),
            "gust_period_s": self.gust_period_s,
            "gust_strength": self.gust_strength,
        }


def _coerce_xyz(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return default
    return default


def _coerce_float_list(value: Any, default: list[float]) -> list[float]:
    if isinstance(value, (list, tuple)):
        out: list[float] = []
        for v in value:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                continue
        return out if out else list(default)
    return list(default)


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, dict) and value.get("type") == "unit":
        try:
            return float(value.get("value", default))
        except (TypeError, ValueError):
            return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compile_wind_program(decl: dict[str, Any]) -> WindProgram:
    """Lower a normalized ``wind_program`` decl into a ``WindProgram``."""
    values = decl.get("values", {}) or {}
    return WindProgram(
        name=decl.get("name", "wind"),
        wind_direction=_coerce_xyz(values.get("direction"), (1.0, 0.0, 0.0)),
        base_strength=_coerce_float(values.get("strength"), 1.0),
        band_amplitudes_cm=_coerce_float_list(
            values.get("band_amplitudes_cm"), [0.0, 1.5, 4.0]
        ),
        band_frequencies_hz=_coerce_float_list(
            values.get("band_frequencies_hz"), [0.0, 0.6, 1.4]
        ),
        band_turbulence=_coerce_float_list(values.get("band_turbulence"), [0.0, 0.2, 0.55]),
        gust_period_s=_coerce_float(values.get("gust_period_s"), 6.0),
        gust_strength=_coerce_float(values.get("gust_strength"), 0.4),
    )


DEFAULT_WIND_PROGRAMS: dict[str, WindProgram] = {
    "calm": WindProgram(
        name="calm",
        base_strength=0.3,
        band_amplitudes_cm=[0.0, 0.4, 1.5],
        band_frequencies_hz=[0.0, 0.3, 0.7],
        band_turbulence=[0.0, 0.05, 0.15],
        gust_period_s=12.0,
        gust_strength=0.15,
    ),
    "breezy": WindProgram(
        name="breezy",
        base_strength=1.0,
        band_amplitudes_cm=[0.0, 1.5, 4.0],
        band_frequencies_hz=[0.0, 0.6, 1.4],
        band_turbulence=[0.0, 0.2, 0.55],
        gust_period_s=6.0,
        gust_strength=0.4,
    ),
    "stormy": WindProgram(
        name="stormy",
        base_strength=2.5,
        band_amplitudes_cm=[0.5, 5.0, 12.0],
        band_frequencies_hz=[0.2, 1.4, 3.0],
        band_turbulence=[0.1, 0.55, 0.85],
        gust_period_s=2.5,
        gust_strength=0.9,
    ),
}


def assign_wind_bands(primitives: list[dict]) -> list[dict]:
    """Ensure every primitive has a ``wind_band`` field.

    Trunk/cylinder/revolved → 0 (rigid). Branch swept profiles → 1.
    Leaf cards (extruded with the ``leaf_card`` tag) → 2. Default → 0.
    """
    out: list[dict] = []
    for prim in primitives:
        if "wind_band" in prim:
            out.append(prim)
            continue
        tags = prim.get("tags", []) or []
        ptype = prim.get("primitive_type", "")
        if "leaf_card" in tags:
            band = 2
        elif "branch" in tags or ptype == "swept_profile":
            band = 1
        else:
            band = 0
        out.append({**prim, "wind_band": band})
    return out
