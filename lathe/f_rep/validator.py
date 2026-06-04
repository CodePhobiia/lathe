"""F-Rep program validation.

Sanity-checks an :class:`SDFExpr` tree before extraction:

* Bounded support — primitives carry finite half-extents/radii so the
  authoring extractor knows what bounding box to sweep.
* No infinite recursion — programs are DAGs, not cyclic graphs.
* Reasonable ``k`` — smooth-boolean blend radii must be non-negative.
* Reasonable resolution / extraction config — checked at the call site
  via :func:`validate_program`.

The validator returns a structured report; the ``f_rep`` checker
integration can promote any ``severity == "error"`` diagnostic into a
build-time failure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .expressions import (
    Bend,
    Box,
    Capsule,
    ChamferIntersect,
    ChamferSubtract,
    ChamferUnion,
    Cone,
    ConnectedIntent,
    Cylinder,
    Displace,
    Ellipsoid,
    ExtrudedPolygon,
    Frustum,
    HexPrism,
    Intersect,
    Mirror,
    Offset,
    Plane,
    Repeat,
    RevolvedProfile,
    Rotate,
    RoundedSlot,
    Scale,
    Scale3,
    SDFExpr,
    SegmentBox,
    SegmentCapsule,
    SegmentExtrudedProfile,
    SegmentLoftedProfile,
    Shell,
    SmoothIntersect,
    SmoothSubtract,
    SmoothUnion,
    Sphere,
    Subtract,
    Taper,
    TaperedSegmentCapsule,
    Torus,
    Translate,
    Twist,
    Union,
    Warp,
)


@dataclass
class ValidationDiagnostic:
    """One validation message."""

    code: str
    severity: str  # "error" | "warning" | "info"
    message: str
    path: str = ""


@dataclass
class ValidationReport:
    """Aggregate validation result."""

    diagnostics: list[ValidationDiagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(d.severity == "error" for d in self.diagnostics)

    def add(self, code: str, severity: str, message: str, path: str = "") -> None:
        self.diagnostics.append(
            ValidationDiagnostic(code=code, severity=severity, message=message, path=path)
        )


def validate_program(
    expr: SDFExpr,
    *,
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
    resolution: int | tuple[int, int, int] | None = None,
) -> ValidationReport:
    """Validate an SDF expression tree.

    Args:
        expr: root :class:`SDFExpr` to validate.
        bounds: optional evaluation box; when provided, primitives whose
            local extents exceed the box are flagged.
        resolution: optional grid resolution; warns when very low / very
            high.

    Returns:
        A :class:`ValidationReport` with any diagnostics found.
    """
    report = ValidationReport()
    visited: set[int] = set()
    _walk(expr, "$root", report, visited)
    if resolution is not None:
        if isinstance(resolution, int):
            res_axes = (resolution, resolution, resolution)
        else:
            res_axes = tuple(int(v) for v in resolution)
        for axis, value in zip("xyz", res_axes, strict=False):
            if value < 8:
                report.add(
                    code="FREP002",
                    severity="warning",
                    message=f"resolution.{axis}={value} is below 8 — extraction will be very coarse",
                )
            elif value > 512:
                report.add(
                    code="FREP003",
                    severity="warning",
                    message=f"resolution.{axis}={value} is above 512 — extraction may be very slow",
                )
    return report


def _walk(node: SDFExpr, path: str, report: ValidationReport, visited: set[int]) -> None:
    nid = id(node)
    if nid in visited:
        report.add(
            code="FREP010",
            severity="error",
            message="cyclic SDF expression graph (an expression references itself)",
            path=path,
        )
        return
    visited.add(nid)

    if isinstance(node, Sphere):
        if node.radius <= 0.0:
            report.add("FREP100", "error", f"sphere.radius={node.radius} must be positive", path)
    elif isinstance(node, Box):
        if any(v <= 0.0 for v in node.half_extents):
            report.add(
                "FREP101",
                "error",
                f"box.half_extents={node.half_extents} must be positive",
                path,
            )
    elif isinstance(node, Cylinder):
        if node.radius <= 0.0 or node.height <= 0.0:
            report.add(
                "FREP102",
                "error",
                f"cylinder.radius={node.radius}, height={node.height} must be positive",
                path,
            )
    elif isinstance(node, Torus):
        if node.major_radius <= 0.0 or node.minor_radius <= 0.0:
            report.add(
                "FREP103",
                "error",
                f"torus.major={node.major_radius}, minor={node.minor_radius} must be positive",
                path,
            )
        elif node.minor_radius >= node.major_radius:
            report.add(
                "FREP104",
                "warning",
                "torus.minor_radius >= major_radius produces a self-intersecting ring",
                path,
            )
    elif isinstance(node, Capsule):
        if node.half_height < 0.0 or node.radius <= 0.0:
            report.add(
                "FREP105",
                "error",
                f"capsule.half_height={node.half_height}, radius={node.radius} invalid",
                path,
            )
    elif isinstance(node, SegmentCapsule):
        if node.radius <= 0.0:
            report.add(
                "FREP110",
                "error",
                f"segment_capsule.radius={node.radius} must be positive",
                path,
            )
        if tuple(node.a) == tuple(node.b):
            report.add(
                "FREP111",
                "error",
                "segment_capsule endpoints must be distinct",
                path,
            )
    elif isinstance(node, SegmentBox):
        if node.half_width <= 0.0 or node.half_depth <= 0.0:
            report.add(
                "FREP134",
                "error",
                "segment_box half_width and half_depth must be positive",
                path,
            )
        if tuple(node.a) == tuple(node.b):
            report.add(
                "FREP135",
                "error",
                "segment_box endpoints must be distinct",
                path,
            )
        try:
            up = tuple(float(component) for component in node.up_hint)
        except (TypeError, ValueError):
            up = ()
        if len(up) != 3 or not all(math.isfinite(value) for value in up):
            report.add(
                "FREP136",
                "error",
                "segment_box up_hint must be a finite 3D vector",
                path,
            )
        elif all(abs(value) <= 1e-12 for value in up):
            report.add(
                "FREP137",
                "error",
                "segment_box up_hint must be non-zero",
                path,
            )
    elif isinstance(node, SegmentExtrudedProfile):
        if tuple(node.a) == tuple(node.b):
            report.add(
                "FREP138",
                "error",
                "segment_extruded_profile endpoints must be distinct",
                path,
            )
        try:
            points = tuple(tuple(float(component) for component in point) for point in node.profile_points)
        except (TypeError, ValueError):
            points = ()
        if len(points) < 3:
            report.add(
                "FREP139",
                "error",
                "segment_extruded_profile profile_points must contain at least three points",
                path,
            )
        elif not all(len(point) == 2 and all(math.isfinite(value) for value in point) for point in points):
            report.add(
                "FREP140",
                "error",
                "segment_extruded_profile profile_points must be finite 2D points",
                path,
            )
        else:
            area = 0.0
            for index, point in enumerate(points):
                nxt = points[(index + 1) % len(points)]
                area += point[0] * nxt[1] - nxt[0] * point[1]
            if abs(area) <= 1e-9:
                report.add(
                    "FREP141",
                    "error",
                    "segment_extruded_profile profile must enclose non-zero area",
                    path,
                )
        try:
            up = tuple(float(component) for component in node.up_hint)
        except (TypeError, ValueError):
            up = ()
        if len(up) != 3 or not all(math.isfinite(value) for value in up):
            report.add(
                "FREP142",
                "error",
                "segment_extruded_profile up_hint must be a finite 3D vector",
                path,
            )
        elif all(abs(value) <= 1e-12 for value in up):
            report.add(
                "FREP143",
                "error",
                "segment_extruded_profile up_hint must be non-zero",
                path,
            )
        if node.start_scale <= 0.0 or node.end_scale <= 0.0:
            report.add(
                "FREP144",
                "error",
                "segment_extruded_profile start_scale and end_scale must be positive",
                path,
            )
        if not math.isfinite(float(node.twist_degrees)):
            report.add(
                "FREP145",
                "error",
                "segment_extruded_profile twist_degrees must be finite",
                path,
            )
    elif isinstance(node, SegmentLoftedProfile):
        if tuple(node.a) == tuple(node.b):
            report.add(
                "FREP146",
                "error",
                "segment_lofted_profile endpoints must be distinct",
                path,
            )

        def read_profile(raw: Any) -> tuple[tuple[float, float], ...]:
            try:
                return tuple(tuple(float(component) for component in point) for point in raw)
            except (TypeError, ValueError):
                return ()

        start = read_profile(node.profile_start)
        end = read_profile(node.profile_end)
        if len(start) < 3 or len(end) < 3 or len(start) != len(end):
            report.add(
                "FREP147",
                "error",
                "segment_lofted_profile profiles must have matching point counts >= 3",
                path,
            )
        elif not all(
            len(point) == 2 and all(math.isfinite(value) for value in point)
            for point in (*start, *end)
        ):
            report.add(
                "FREP148",
                "error",
                "segment_lofted_profile profile points must be finite 2D points",
                path,
            )
        else:
            for label, points in (("profile_start", start), ("profile_end", end)):
                area = 0.0
                for index, point in enumerate(points):
                    nxt = points[(index + 1) % len(points)]
                    area += point[0] * nxt[1] - nxt[0] * point[1]
                if abs(area) <= 1e-9:
                    report.add(
                        "FREP149",
                        "error",
                        f"segment_lofted_profile {label} must enclose non-zero area",
                        path,
                    )
        try:
            up = tuple(float(component) for component in node.up_hint)
        except (TypeError, ValueError):
            up = ()
        if len(up) != 3 or not all(math.isfinite(value) for value in up):
            report.add(
                "FREP150",
                "error",
                "segment_lofted_profile up_hint must be a finite 3D vector",
                path,
            )
        elif all(abs(value) <= 1e-12 for value in up):
            report.add(
                "FREP151",
                "error",
                "segment_lofted_profile up_hint must be non-zero",
                path,
            )
        if not math.isfinite(float(node.twist_degrees)):
            report.add(
                "FREP152",
                "error",
                "segment_lofted_profile twist_degrees must be finite",
                path,
            )
    elif isinstance(node, TaperedSegmentCapsule):
        if node.radius_start <= 0.0 or node.radius_end <= 0.0:
            report.add(
                "FREP112",
                "error",
                "tapered_segment_capsule radii must be positive",
                path,
            )
        if tuple(node.a) == tuple(node.b):
            report.add(
                "FREP113",
                "error",
                "tapered_segment_capsule endpoints must be distinct",
                path,
            )
    elif isinstance(node, RoundedSlot):
        if node.length <= 0.0 or node.radius <= 0.0 or node.depth <= 0.0:
            report.add(
                "FREP114",
                "error",
                "rounded_slot length, radius, and depth must be positive",
                path,
            )
        elif node.length <= 2.0 * node.radius:
            report.add(
                "FREP115",
                "error",
                "rounded_slot length must be larger than diameter",
                path,
            )
        if str(node.axis).lower() not in {"x", "y", "z"}:
            report.add("FREP116", "error", f"rounded_slot.axis={node.axis!r}", path)
        if str(node.normal_axis).lower() not in {"x", "y", "z"}:
            report.add(
                "FREP117",
                "error",
                f"rounded_slot.normal_axis={node.normal_axis!r}",
                path,
            )
        if str(node.axis).lower() == str(node.normal_axis).lower():
            report.add(
                "FREP118",
                "error",
                "rounded_slot axis and normal_axis must be different",
                path,
            )
    elif isinstance(node, ExtrudedPolygon):
        try:
            points = tuple(tuple(float(component) for component in point) for point in node.profile_points)
        except (TypeError, ValueError):
            points = ()
        if len(points) < 3:
            report.add(
                "FREP120",
                "error",
                "extruded_polygon profile_points must contain at least three points",
                path,
            )
        elif not all(len(point) == 2 and all(math.isfinite(value) for value in point) for point in points):
            report.add(
                "FREP121",
                "error",
                "extruded_polygon profile_points must be finite 2D points",
                path,
            )
        else:
            area = 0.0
            for index, point in enumerate(points):
                nxt = points[(index + 1) % len(points)]
                area += point[0] * nxt[1] - nxt[0] * point[1]
            if abs(area) <= 1e-9:
                report.add(
                    "FREP122",
                    "error",
                    "extruded_polygon profile must enclose non-zero area",
                    path,
                )
        if node.depth <= 0.0:
            report.add(
                "FREP123",
                "error",
                f"extruded_polygon.depth={node.depth} must be positive",
                path,
            )
        axes = {
            str(node.axis_u).lower(),
            str(node.axis_v).lower(),
            str(node.normal_axis).lower(),
        }
        if not axes <= {"x", "y", "z"}:
            report.add(
                "FREP124",
                "error",
                "extruded_polygon axes must be x|y|z",
                path,
            )
        elif len(axes) != 3:
            report.add(
                "FREP125",
                "error",
                "extruded_polygon axis_u, axis_v, and normal_axis must be distinct",
                path,
            )
    elif isinstance(node, RevolvedProfile):
        try:
            points = tuple(tuple(float(component) for component in point) for point in node.profile_points)
        except (TypeError, ValueError):
            points = ()
        if len(points) < 3:
            report.add(
                "FREP126",
                "error",
                "revolved_profile profile_points must contain at least three points",
                path,
            )
        elif not all(len(point) == 2 and all(math.isfinite(value) for value in point) for point in points):
            report.add(
                "FREP127",
                "error",
                "revolved_profile profile_points must be finite 2D points",
                path,
            )
        else:
            if any(point[0] < 0.0 for point in points):
                report.add(
                    "FREP128",
                    "error",
                    "revolved_profile radius coordinates must be >= 0",
                    path,
                )
            area = 0.0
            for index, point in enumerate(points):
                nxt = points[(index + 1) % len(points)]
                area += point[0] * nxt[1] - nxt[0] * point[1]
            if abs(area) <= 1e-9:
                report.add(
                    "FREP129",
                    "error",
                    "revolved_profile profile must enclose non-zero area",
                    path,
                )
        if str(node.axis).lower() not in {"x", "y", "z"}:
            report.add("FREP130", "error", f"revolved_profile.axis={node.axis!r}", path)
        if node.revolve_degrees is not None:
            if not math.isfinite(float(node.revolve_degrees)):
                report.add(
                    "FREP131",
                    "error",
                    "revolved_profile.revolve_degrees must be finite",
                    path,
                )
            elif node.revolve_degrees <= 0.0 or node.revolve_degrees > 360.0:
                report.add(
                    "FREP132",
                    "error",
                    "revolved_profile.revolve_degrees must satisfy 0 < value <= 360",
                    path,
                )
        if not math.isfinite(float(node.start_degrees)):
            report.add(
                "FREP133",
                "error",
                "revolved_profile.start_degrees must be finite",
                path,
            )
    elif isinstance(node, Frustum):
        if node.radius_bottom <= 0.0 or node.radius_top <= 0.0 or node.height <= 0.0:
            report.add(
                "FREP119",
                "error",
                "frustum radii and height must be positive",
                path,
            )
    elif isinstance(node, Cone):
        if node.radius <= 0.0 or node.half_height <= 0.0:
            report.add(
                "FREP106", "error", "cone radius and half_height must be positive", path
            )
    elif isinstance(node, HexPrism):
        if node.radius <= 0.0 or node.half_height <= 0.0:
            report.add(
                "FREP107", "error", "hex_prism radius and half_height must be positive", path
            )
    elif isinstance(node, Ellipsoid):
        if any(v <= 0.0 for v in node.half_extents):
            report.add(
                "FREP108",
                "error",
                f"ellipsoid.half_extents={node.half_extents} must be positive",
                path,
            )
    elif isinstance(node, Plane):
        if all(v == 0.0 for v in node.normal):
            report.add("FREP109", "error", "plane.normal must be non-zero", path)
    elif isinstance(node, (Union, Intersect, Subtract)):
        _walk(node.a, f"{path}.a", report, visited)
        _walk(node.b, f"{path}.b", report, visited)
    elif isinstance(node, (SmoothUnion, SmoothIntersect, SmoothSubtract)):
        if node.k < 0.0:
            report.add(
                "FREP200",
                "error",
                f"{type(node).__name__}.k={node.k} must be >= 0",
                path,
        )
        _walk(node.a, f"{path}.a", report, visited)
        _walk(node.b, f"{path}.b", report, visited)
    elif isinstance(node, (ChamferUnion, ChamferIntersect, ChamferSubtract)):
        if node.radius < 0.0:
            report.add(
                "FREP201",
                "error",
                f"{type(node).__name__}.radius={node.radius} must be >= 0",
                path,
            )
        _walk(node.a, f"{path}.a", report, visited)
        _walk(node.b, f"{path}.b", report, visited)
    elif isinstance(node, (ConnectedIntent, Translate)):
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Rotate):
        if all(v == 0.0 for v in node.axis):
            report.add("FREP300", "error", "rotate.axis must be non-zero", path)
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Scale):
        if node.factor <= 0.0:
            report.add("FREP301", "error", "scale.factor must be positive", path)
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Scale3):
        if len(tuple(node.factors)) != 3 or any(value <= 0.0 for value in node.factors):
            report.add("FREP305", "error", "scale3.factors must be three positive values", path)
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Twist):
        if str(node.axis).lower() not in {"x", "y", "z"}:
            report.add("FREP306", "error", f"twist.axis={node.axis!r}", path)
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Bend):
        if str(node.axis).lower() not in {"x", "y", "z"}:
            report.add("FREP310", "error", f"bend.axis={node.axis!r}", path)
        if str(node.bend_axis).lower() not in {"x", "y", "z"}:
            report.add("FREP311", "error", f"bend.bend_axis={node.bend_axis!r}", path)
        if str(node.axis).lower() == str(node.bend_axis).lower():
            report.add("FREP312", "error", "bend axis and bend_axis must differ", path)
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Taper):
        if str(node.axis).lower() not in {"x", "y", "z"}:
            report.add("FREP307", "error", f"taper.axis={node.axis!r}", path)
        if node.height <= 0.0:
            report.add("FREP308", "error", "taper.height must be positive", path)
        if node.start_scale <= 0.0 or node.end_scale <= 0.0:
            report.add("FREP309", "error", "taper scales must be positive", path)
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Mirror):
        if node.axis.lower() not in {"x", "y", "z"}:
            report.add("FREP302", "error", f"mirror.axis={node.axis!r}", path)
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Repeat):
        if node.count <= 0 or node.period <= 0.0:
            report.add(
                "FREP303",
                "error",
                f"repeat.count={node.count}, period={node.period} must be positive",
                path,
            )
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Offset):
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, Shell):
        if node.thickness <= 0.0:
            report.add(
                "FREP304",
                "error",
                f"shell.thickness={node.thickness} must be positive",
                path,
            )
        _walk(node.expr, f"{path}.expr", report, visited)
    elif isinstance(node, (Displace, Warp)):
        _walk(node.expr, f"{path}.expr", report, visited)
    else:
        report.add(
            "FREP001",
            "warning",
            f"unknown SDF node type {type(node).__name__}; skipping deep validation",
            path,
        )
