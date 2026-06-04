"""Reusable structural profiles layered around procedural routes and masses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def structural_elements_for_path(
    controls: Mapping[str, Any],
    *,
    family: str,
    path_profile: Mapping[str, Any],
    width: float,
    height: float,
    base_y: float = 0.0,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Return reusable structural element specs along a path profile."""
    style = _path_structure_style(controls, family=family, path_profile=path_profile)
    segments = list(path_profile.get("segments", []) or [])[: max(1, limit)]
    elements: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        index = int(segment.get("index") or len(elements))
        center = _vec3(segment.get("center"))
        extents = _vec2(segment.get("extents"))
        if center is None or extents is None:
            continue
        x, y, z = center
        seg_width, seg_depth = extents
        route_y = base_y + y
        if style in {"curbed", "barrier", "road_edge", "guarded", "truss", "walled", "tunnel", "covered"}:
            barrier_h = max(height * (0.20 if style == "curbed" else 0.42), width * 0.035)
            barrier_w = max(width * 0.040, 0.055)
            for side, sign in (("left", -1.0), ("right", 1.0)):
                elements.append(
                    _element(
                        f"{family}_structural_{style}_{side}_{index:02d}",
                        "panel" if style in {"curbed", "road_edge"} else "railing",
                        "edge",
                        (
                            x + sign * (seg_width * 0.50 + barrier_w * 0.50),
                            route_y + barrier_h * 0.50,
                            z,
                        ),
                        (barrier_w, barrier_h, seg_depth * 0.94),
                        ["structural_profile", style, "edge", side, f"path_segment_{index}"],
                    )
                )
        if style in {"walled", "tunnel", "covered", "service_trench", "corridor"}:
            wall_h = max(height * (0.78 if style != "service_trench" else 0.42), width * 0.08)
            wall_w = max(width * 0.055, 0.06)
            for side, sign in (("left", -1.0), ("right", 1.0)):
                elements.append(
                    _element(
                        f"{family}_wall_{side}_{index:02d}",
                        "panel",
                        "wall",
                        (
                            x + sign * (seg_width * 0.50 + wall_w * 0.50),
                            route_y + wall_h * 0.50,
                            z,
                        ),
                        (wall_w, wall_h, seg_depth * 0.98),
                        ["structural_profile", style, "wall", side, f"path_segment_{index}"],
                    )
                )
            if style in {"tunnel", "covered", "corridor"}:
                roof_t = max(height * 0.08, 0.045)
                elements.append(
                    _element(
                        f"{family}_roof_rib_{index:02d}",
                        "roof" if style == "covered" else "panel",
                        "roof",
                        (x, route_y + wall_h + roof_t * 0.50, z),
                        (seg_width + wall_w * 2.0, roof_t, seg_depth * 0.90),
                        ["structural_profile", style, "roof", "rib", f"path_segment_{index}"],
                    )
                )
        if style in {"truss", "elevated", "bridge", "gantry", "service_trench"}:
            post_h = max(height * (0.80 if style != "bridge" else 0.62), width * 0.10)
            post_w = max(width * 0.055, 0.055)
            for side, sign in (("left", -1.0), ("right", 1.0)):
                elements.append(
                    _element(
                        f"{family}_support_post_{side}_{index:02d}",
                        "column",
                        "support",
                        (
                            x + sign * seg_width * 0.46,
                            route_y + post_h * 0.50,
                            z,
                        ),
                        (post_w, post_h, post_w),
                        ["structural_profile", style, "support", "post", side, f"path_segment_{index}"],
                    )
                )
            beam_h = max(height * 0.070, 0.045)
            elements.append(
                _element(
                    f"{family}_crossbeam_{index:02d}",
                    "support_bracket",
                    "truss",
                    (x, route_y + post_h, z),
                    (seg_width * 1.05, beam_h, max(seg_depth * 0.16, post_w)),
                    ["structural_profile", style, "crossbeam", "truss", f"path_segment_{index}"],
                )
            )
    return elements


def structural_elements_for_facade(
    controls: Mapping[str, Any],
    *,
    family: str,
    width: float,
    depth: float,
    height: float,
    floors: int,
    bays: int,
) -> list[dict[str, Any]]:
    """Return reusable facade/roof structural element specs for massed buildings."""
    style = _slug(str(controls.get("structural_profile") or controls.get("facade_profile") or controls.get("facade_style") or "facade_grid"))
    floors = max(1, floors)
    bays = max(1, bays)
    elements: list[dict[str, Any]] = []
    mullion_w = max(width * 0.026, 0.055)
    band_h = max(height / floors * 0.040, 0.045)
    front_z = depth * 0.565
    for bay in range(bays + 1):
        x = -width * 0.46 + width * 0.92 * bay / max(1, bays)
        elements.append(
            _element(
                f"{family}_facade_mullion_{bay:02d}",
                "panel",
                "wall",
                (x, height * 0.50, front_z),
                (mullion_w, height * 0.94, max(depth * 0.045, 0.05)),
                ["structural_profile", style, "facade", "mullion", f"bay_{bay}"],
            )
        )
    for floor in range(floors + 1):
        y = height * floor / max(1, floors)
        elements.append(
            _element(
                f"{family}_facade_floor_band_{floor:02d}",
                "panel",
                "trim",
                (0.0, y, front_z + depth * 0.012),
                (width * 0.98, band_h, max(depth * 0.050, 0.055)),
                ["structural_profile", style, "facade", "floor_band", f"floor_{floor}"],
            )
        )
    if style in {"fortified", "buttressed", "gothic", "industrial"}:
        for side, sign in (("left", -1.0), ("right", 1.0)):
            elements.append(
                _element(
                    f"{family}_facade_buttress_{side}",
                    "column",
                    "support",
                    (sign * width * 0.52, height * 0.45, front_z + depth * 0.030),
                    (width * 0.075, height * 0.90, width * 0.075),
                    ["structural_profile", style, "facade", "buttress", side],
                )
            )
    roof_lip_h = max(height * 0.030, 0.05)
    elements.append(
        _element(
            f"{family}_roof_edge_profile",
            "roof",
            "roof",
            (0.0, height + roof_lip_h * 0.50, 0.0),
            (width * 1.10, roof_lip_h, depth * 1.12),
            ["structural_profile", style, "roof", "edge_profile"],
        )
    )
    return elements


def _path_structure_style(
    controls: Mapping[str, Any],
    *,
    family: str,
    path_profile: Mapping[str, Any],
) -> str:
    for key in ("structural_profile", "route_structure", "edge_profile", "tunnel_profile", "support_profile"):
        value = controls.get(key)
        if _present(value):
            return _slug(str(value))
    profile = _slug(str(path_profile.get("profile") or ""))
    if family == "procedural_bridge":  # no-family-dispatch: per-family structural defaults; migrate to StyleKnowledge parameter_priors and let the FamilyAlias resolve them
        return "truss"
    if family == "procedural_road":  # no-family-dispatch: per-family structural defaults; migrate to StyleKnowledge parameter_priors and let the FamilyAlias resolve them
        return "barrier" if profile in {"elevated", "bridge"} else "curbed"
    if family == "procedural_access":  # no-family-dispatch: per-family structural defaults; migrate to StyleKnowledge parameter_priors and let the FamilyAlias resolve them
        return "gantry" if profile in {"elevated", "bridge"} else "guarded"
    if family == "procedural_infrastructure":  # no-family-dispatch: per-family structural defaults; migrate to StyleKnowledge parameter_priors and let the FamilyAlias resolve them
        return "service_trench"
    if family == "procedural_interior":  # no-family-dispatch: per-family structural defaults; migrate to StyleKnowledge parameter_priors and let the FamilyAlias resolve them
        return "corridor"
    if family == "procedural_terrain":  # no-family-dispatch: per-family structural defaults; migrate to StyleKnowledge parameter_priors and let the FamilyAlias resolve them
        return "road_edge"
    return "guarded"


def _element(
    name: str,
    component_type: str,
    part_role: str,
    center: tuple[float, float, float],
    extents: tuple[float, float, float],
    tags: list[str],
) -> dict[str, Any]:
    return {
        "name": name,
        "component_type": component_type,
        "part_role": part_role,
        "center": center,
        "extents": extents,
        "tags": tags,
    }


def _vec3(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, list | tuple) or len(value) < 3:
        return None
    try:
        return float(value[0]), float(value[1]), float(value[2])
    except (TypeError, ValueError):
        return None


def _vec2(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, list | tuple) or len(value) < 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def _slug(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _present(value: Any) -> bool:
    return value is not None and value != ""
