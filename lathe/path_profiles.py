"""Reusable path-profile planning for procedural geometry families."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def path_profile_from_controls(
    controls: Mapping[str, Any],
    *,
    family: str,
    segment_count: int,
    length: float,
    width: float,
    height: float = 0.0,
    default_profile: str = "straight",
) -> dict[str, Any]:
    """Return normalized path-following segment and branch placement data."""
    count = max(1, int(segment_count))
    profile = _path_profile_name(controls, family=family, default=default_profile)
    route_count = _int_value(controls, "connection_route_count", default=0)
    branch_count = _int_value(
        controls,
        "path_branch_count",
        "connection_branch_count",
        "branch_count",
        "branches",
        default=max(0, route_count - 1) if profile in {"branch", "network"} else 0,
    )
    amplitude = width * _float_value(
        controls,
        "path_curve_strength",
        "curve_strength",
        "route_curve_strength",
        default=0.0 if profile == "straight" else 0.26,
    )
    rise = height * _float_value(
        controls,
        "path_rise",
        "route_rise",
        "stair_rise",
        "elevation_change",
        default=0.28 if profile in {"stair", "switchback"} else 0.0,
    )
    segment_length = length / count
    segments = [
        _segment(
            index=index,
            count=count,
            profile=profile,
            length=length,
            width=width,
            segment_length=segment_length,
            amplitude=amplitude,
            rise=rise,
        )
        for index in range(count)
    ]
    branches = _branches(
        count=max(0, min(12, branch_count)),
        profile=profile,
        length=length,
        width=width,
        rise=rise,
    )
    return {
        "profile": profile,
        "segments": segments,
        "branches": branches,
        "segment_count": count,
        "branch_count": len(branches),
        "path_length": round(length, 6),
        "path_width": round(width, 6),
        "path_rise": round(rise, 6),
        "path_curve_strength": round(amplitude / max(width, 1e-6), 6),
    }


def _path_profile_name(controls: Mapping[str, Any], *, family: str, default: str) -> str:
    for key in ("path_profile", "route_profile", "path_shape", "route_shape", "layout_profile"):
        value = controls.get(key)
        if value is not None and value != "":
            return _slug(str(value))
    layout_mode = _slug(str(controls.get("connection_layout_mode") or ""))
    if layout_mode == "network":
        return "network"
    if family == "procedural_bridge":  # no-family-dispatch: per-family path defaults (bridge/access); migrate values to a StyleKnowledge parameter_priors subset and resolve via the FamilyAlias style_id
        return "bridge"
    if family == "procedural_access" and int(controls.get("support_count") or 0) > 0:  # no-family-dispatch: per-family path defaults (bridge/access); migrate values to a StyleKnowledge parameter_priors subset and resolve via the FamilyAlias style_id
        return "elevated"
    if layout_mode == "linear_route" and float(controls.get("connection_path_complexity") or 0.0) > 0.30:
        return "s_curve"
    return default


def _segment(
    *,
    index: int,
    count: int,
    profile: str,
    length: float,
    width: float,
    segment_length: float,
    amplitude: float,
    rise: float,
) -> dict[str, Any]:
    t = (index + 0.5) / count
    centered = t - 0.5
    z = -length * 0.5 + segment_length * (index + 0.5)
    x = 0.0
    y = 0.0
    width_scale = 1.0
    length_scale = 0.98
    orientation = "forward"
    if profile in {"curve", "arc"}:
        x = math.sin(t * math.pi) * amplitude
        width_scale = 1.0 - 0.06 * abs(centered)
    elif profile in {"s_curve", "meander"}:
        x = math.sin(t * math.tau) * amplitude
        orientation = "meander"
    elif profile in {"switchback", "zigzag"}:
        side = -1.0 if index % 2 == 0 else 1.0
        x = side * amplitude
        length_scale = 0.78
        orientation = "switchback"
        y = rise * t
    elif profile in {"stair", "stairs", "ramp"}:
        y = rise * t
        length_scale = 0.84 if profile in {"stair", "stairs"} else 0.96
        orientation = "ascending"
    elif profile in {"tunnel", "underpass"}:
        y = -abs(rise) * 0.18
        width_scale = 1.08
        orientation = "subsurface"
    elif profile in {"bridge", "elevated"}:
        y = abs(rise) or width * 0.10
        orientation = "elevated"
    elif profile in {"branch", "network"}:
        x = math.sin(t * math.tau) * amplitude * 0.42
        orientation = "network_spine"
    return {
        "index": index,
        "center": [round(x, 6), round(y, 6), round(z, 6)],
        "extents": [round(width * width_scale, 6), round(segment_length * length_scale, 6)],
        "t": round(t, 6),
        "orientation": orientation,
        "tags": [f"path_profile_{profile}", orientation, f"path_segment_{index}"],
    }


def _branches(*, count: int, profile: str, length: float, width: float, rise: float) -> list[dict[str, Any]]:
    if count <= 0 and profile not in {"branch", "network"}:
        return []
    branch_total = count if count > 0 else 2
    directions = [
        ("east", 1.0, 0.0),
        ("west", -1.0, 0.0),
        ("north", 0.0, 1.0),
        ("south", 0.0, -1.0),
        ("northeast", 0.72, 0.72),
        ("southwest", -0.72, -0.72),
        ("northwest", -0.72, 0.72),
        ("southeast", 0.72, -0.72),
    ]
    out: list[dict[str, Any]] = []
    branch_length = max(width * 1.25, length * 0.22)
    for index in range(branch_total):
        direction, dx, dz = directions[index % len(directions)]
        horizontal = abs(dx) >= abs(dz)
        center = [
            round(dx * (width * 0.55 + branch_length * 0.50), 6),
            round(rise * 0.50 if profile in {"elevated", "bridge"} else 0.0, 6),
            round(dz * (width * 0.55 + branch_length * 0.50), 6),
        ]
        extents = [
            round(branch_length if horizontal else width * 0.72, 6),
            round(width * 0.72 if horizontal else branch_length, 6),
        ]
        out.append(
            {
                "index": index,
                "direction": direction,
                "center": center,
                "extents": extents,
                "orientation": "horizontal" if horizontal else "vertical",
                "tags": [f"path_profile_{profile}", "path_branch", direction, f"path_branch_{index}"],
            }
        )
    return out


def _int_value(controls: Mapping[str, Any], *keys: str, default: int) -> int:
    for key in keys:
        value = controls.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            continue
    return default


def _float_value(controls: Mapping[str, Any], *keys: str, default: float) -> float:
    for key in keys:
        value = controls.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _slug(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")
