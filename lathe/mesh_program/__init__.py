"""Lowering for the V1.4 ``mesh_program{}`` block (roadmap §5.1, §5.7, Phase 3).

A ``mesh_program{}`` body is parsed as an ordered list of
``mesh_let`` and ``mesh_call`` statements. Each statement names either
a primitive constructor, a transform (``.translate(...)``), or a
fusion/edge-finishing op.

This module turns that AST into a deterministic
``list[ShapePrimitive]`` matching what a hand-written
``examples/bevel_demo.py`` produces, so the existing exact-solid +
post-boolean-polybevel chain in :mod:`lathe.exact_solids` consumes it
without modification.

§5.1 baseline ops:

* ``box(extents: [X, Y, Z])`` — three unit literals.
* ``box(extents: ...).translate([X, Y, Z])`` — chained method call.
* ``boolean(op: subtract|union|intersect, a: <ident>, b: <ident>,
            seam_group: "name"?)`` — fuses ``b`` into ``a`` and emits
  the canonical ``ShapePrimitive`` pair.
* ``body.subtract(other: cutter, seam_group: "name").fillet(...)`` —
  fluent boolean + edge treatment that lowers to the same executable
  seam/polybevel records.
* ``fillet_edge(target: <ident>, edge_class: "name", radius: Xcm,
                segments: N)`` — attaches a polybevel modifier.

§5.7 first wave (8 ops from ShapeIR v2). Names mirror
``lathe/asset_quality/shape_ir_v2.py`` op IDs but use ``_`` for ``.``
because lark ``IDENT`` tokens cannot contain dots:

* ``solid_panel(extents: [W, H, T])`` — rectangular slab (v2 ``solid.panel``).
* ``solid_rail(length: Lcm, profile: Pcm)`` — square-section beam.
* ``solid_prism(extents: [W, H, D])`` — triangular wedge.
* ``solid_cylinder(radius: Rcm, height: Hcm, axis: "x|y|z"?)`` — round
  column.
* ``solid_rounded_box(extents: [W, H, D], radius: Rcm)`` — chamfered
  box.
* ``op_fastener_grid(target, face, rows, cols, spacing,
                     fastener_radius, fastener_height,
                     seam_group?)`` — stamps ``rows*cols`` fasteners
  on a face and fuses them through the geometry kernel.
* ``op_vent_slats(target, face, count, slot_width, slot_length,
                  slot_depth, spacing, axis?, seam_group?)`` —
  fuses ``count`` subtractive slats through the geometry kernel.
* ``op_trim_band(target, axis, width, depth)`` — composes into a thin
  extruded ring banded around the target and fuses it through the
  geometry kernel.

Anything else raises :class:`MeshProgramError` so authors get a
clear error rather than a silent geometry drop.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Any

from ..feature_ops.bevel_real import fillet_edge as _fillet_edge_helper
from ..feature_ops.bevel_real import tag_boolean_seam_group
from ..shape_ir import ShapePrimitive

__all__ = [
    "MeshProgramError",
    "lower_mesh_program",
]


_BOOLEAN_OPS = {"union", "subtract", "intersect"}
_BOOLEAN_METHOD_ALIASES = {
    "union": "union",
    "add": "union",
    "subtract": "subtract",
    "difference": "subtract",
    "intersect": "intersect",
    "intersection": "intersect",
}
_EDGE_TREATMENT_METHODS = {"bevel", "chamfer", "fillet", "fillet_edge"}
_COMPOUND_METHOD_ALIASES = {
    "fastener_grid": "op_fastener_grid",
    "vent_slats": "op_vent_slats",
    "trim_band": "op_trim_band",
    "extrude": "op_extrude",
    "shell": "op_shell",
    "inset": "op_inset",
    "cut_panel_line": "op_cut_panel_line",
    "countersunk_hole": "op_countersunk_hole",
    "rounded_slot": "op_rounded_slot",
    "copy_to_points": "sop_copy_to_points",
    "repeat": "op_repeat",
    "array": "op_repeat",
    "distribute": "op_distribute",
    "mirror": "op_mirror",
    "scatter_on_surface": "scatter_on_surface",
    "panel_frame": "op_panel_frame",
    "corner_guard_set": "op_corner_guard_set",
    "mount_plate": "op_mount_plate",
    "socket": "op_socket",
    "bracket": "op_bracket",
    "weld_seam": "op_weld_seam",
    "weighted_normals": "op_weighted_normals",
    "mark_hard_edge": "op_mark_hard_edge",
    "bevel": "op_bevel",
    "chamfer": "op_chamfer",
    "polybevel": "sop_polybevel",
    "subdivide": "sop_subdivide",
    "remesh": "sop_remesh",
    "twist": "sop_twist",
    "taper": "sop_taper",
    "bend": "sop_bend",
    "polyextrude": "sop_polyextrude",
    "transform": "sop_transform",
    "carve": "sop_carve",
    "minkowski": "op_minkowski",
    "chip_edges": "op_chip_edges",
    "scratch_mask": "op_scratch_mask",
    "dent_mask": "op_dent_mask",
    "grime_mask": "op_grime_mask",
}
_SCATTER_METHODS = {"scatter"}
_HULL_METHODS = {"hull"}


def _supported_primitive_method_names() -> list[str]:
    return sorted(
        set(_BOOLEAN_METHOD_ALIASES)
        | _EDGE_TREATMENT_METHODS
        | set(_COMPOUND_METHOD_ALIASES)
        | _SCATTER_METHODS
        | _HULL_METHODS
        | {"mirror", "rotate", "scale", "translate"}
    )


class MeshProgramError(ValueError):
    """Raised when a ``mesh_program{}`` body cannot be lowered.

    Diagnostics carry the offending statement index when available so
    authors see ``mesh_program statement #2: ...`` rather than the
    bare error string.
    """


@dataclass
class _Value:
    """Internal binding produced by a ``let`` statement.

    Either an already-emitted ``ShapePrimitive`` (e.g. ``let body =
    box(...)``) or a synthetic boolean-result handle that points at
    the operand authored most recently for that result name (so
    ``fillet_edge(target: result, ...)`` knows which primitive to
    attach the polybevel modifier to).

    SDF authoring uses ``kind="sdf"``: ``sdf_expr`` holds an
    ``SDFExpr`` from ``lathe.f_rep`` that has not yet been extracted
    to a triangle mesh. Translation modifiers compose into the
    ``SDFExpr`` tree until ``sdf_extract`` materialises a
    ``ShapePrimitive(primitive_type="sdf_mesh", ...)``.

    WFC modular authoring uses ``kind="wfc_module"`` and
    ``kind="wfc_rule"``: ``wfc_ref`` holds the declarative
    :class:`WFCModuleRef` / :class:`WFCRuleRef` payload until a
    later ``wfc_modular(...)`` call consumes them.

    Scatter authoring uses ``kind="point_set"``: ``points`` holds a
    list of ``(x, y, z)`` cm-space coordinates that the eventual
    ``scatter(primitive:, points:, ...)`` call iterates over to emit N
    translated copies of the chosen primitive (Phase 2 §6.x — the
    Copy-to-Points productivity multiplier).
    """

    kind: str
    primitive: ShapePrimitive | None = None
    bevel_target: ShapePrimitive | None = None
    primitives: tuple[ShapePrimitive, ...] | None = None
    sdf_expr: Any | None = None
    wfc_ref: Any | None = None
    points: list[tuple[float, float, float]] | None = None


def _value_primitives(value: _Value) -> tuple[ShapePrimitive, ...]:
    if value.primitives:
        return value.primitives
    if value.primitive is not None:
        return (value.primitive,)
    return ()


def _primary_primitive(primitives: tuple[ShapePrimitive, ...]) -> ShapePrimitive | None:
    for primitive in primitives:
        if str(primitive.blend_mode or "union") == "union":
            return primitive
    return primitives[0] if primitives else None


def _primitive_value(primitives: ShapePrimitive | list[ShapePrimitive] | tuple[ShapePrimitive, ...]) -> _Value:
    if isinstance(primitives, ShapePrimitive):
        primitive_tuple = (primitives,)
    else:
        primitive_tuple = tuple(primitives)
    primary = _primary_primitive(primitive_tuple)
    return _Value(
        kind="primitive",
        primitive=primary,
        bevel_target=primary,
        primitives=primitive_tuple,
    )


def _append_unique_tags(primitive: ShapePrimitive, tags: tuple[str, ...]) -> None:
    merged = list(primitive.tags or [])
    for tag in tags:
        if tag not in merged:
            merged.append(tag)
    primitive.tags = merged


def _copy_shape_primitive_payload(
    target: ShapePrimitive,
    source: ShapePrimitive,
) -> ShapePrimitive:
    for field in fields(ShapePrimitive):
        setattr(target, field.name, deepcopy(getattr(source, field.name)))
    return target


def _replace_value_primitives(
    value: _Value,
    primitives: list[ShapePrimitive] | tuple[ShapePrimitive, ...],
) -> _Value:
    primitive_tuple = tuple(primitives)
    value.primitives = primitive_tuple
    value.primitive = _primary_primitive(primitive_tuple)
    value.bevel_target = value.primitive
    return value


def _replace_primitives_in_program(
    primitives: list[ShapePrimitive],
    old_primitives: tuple[ShapePrimitive, ...],
    new_primitives: tuple[ShapePrimitive, ...],
) -> None:
    old_ids = {id(primitive) for primitive in old_primitives}
    insert_at: int | None = None
    kept: list[ShapePrimitive] = []
    for primitive in primitives:
        if id(primitive) in old_ids:
            if insert_at is None:
                insert_at = len(kept)
            continue
        kept.append(primitive)
    if insert_at is None:
        insert_at = len(kept)
    existing_ids = {id(primitive) for primitive in kept}
    inserts: list[ShapePrimitive] = []
    for primitive in new_primitives:
        if id(primitive) in existing_ids:
            continue
        inserts.append(primitive)
        existing_ids.add(id(primitive))
    primitives[:] = [*kept[:insert_at], *inserts, *kept[insert_at:]]


def _unit_to_cm(value: Any, *, where: str) -> float:
    # Unary-negation AST node — produced by ``-12cm``. Recurse on the
    # inner value so authors can pass negative bounds / offsets without
    # waiting on the broader parser fix (task #60). Same pattern used by
    # SDF bounds_min and ``.translate([-X, ...])`` chains.
    if isinstance(value, dict) and value.get("type") == "unary" and value.get("op") == "-":
        return -_unit_to_cm(value.get("value"), where=where)
    if isinstance(value, dict) and value.get("type") == "unit":
        unit = value.get("unit")
        raw = float(value.get("value", 0.0))
        if unit == "cm":
            return raw
        if unit == "mm":
            return raw * 0.1
        if unit == "m":
            return raw * 100.0
        raise MeshProgramError(
            f"{where}: only mm/cm/m length units are supported, got {unit!r}"
        )
    if isinstance(value, (int, float)):
        return float(value)
    raise MeshProgramError(f"{where}: expected a length unit literal, got {value!r}")


def _vec3(value: Any, *, where: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise MeshProgramError(
            f"{where}: expected a 3-element list literal, got {value!r}"
        )
    components = [_unit_to_cm(item, where=where) for item in value]
    return (components[0], components[1], components[2])


def _number_vec3(value: Any, *, where: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise MeshProgramError(
            f"{where}: expected a 3-element numeric list literal, got {value!r}"
        )
    components = [
        _number_arg(item, where=f"{where}[{index}]")
        for index, item in enumerate(value)
    ]
    return (components[0], components[1], components[2])


def _vec2_length(value: Any, *, where: str) -> tuple[float, float]:
    """Parse a 2-element ``[X, Y]`` length-unit literal (e.g. ``[40m, 40m]``)."""
    if not isinstance(value, list) or len(value) != 2:
        raise MeshProgramError(
            f"{where}: expected a 2-element list literal, got {value!r}"
        )
    components = [_unit_to_cm(item, where=where) for item in value]
    return (components[0], components[1])


def _vec2_length_points(
    value: Any,
    *,
    where: str,
    min_points: int,
) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < min_points:
        raise MeshProgramError(
            f"{where}: expected at least {min_points} 2D points, got {value!r}"
        )
    points: list[tuple[float, float]] = []
    for index, point in enumerate(value):
        points.append(_vec2_length(point, where=f"{where}[{index}]"))
    return points


def _vec3_length_points(
    value: Any,
    *,
    where: str,
    min_points: int,
) -> list[tuple[float, float, float]]:
    if not isinstance(value, list) or len(value) < min_points:
        raise MeshProgramError(
            f"{where}: expected at least {min_points} 3D points, got {value!r}"
        )
    points: list[tuple[float, float, float]] = []
    for index, point in enumerate(value):
        points.append(_vec3(point, where=f"{where}[{index}]"))
    return points


def _length_list(value: Any, *, where: str, min_count: int = 1) -> list[float]:
    if not isinstance(value, list) or len(value) < min_count:
        raise MeshProgramError(
            f"{where}: expected at least {min_count} length values, got {value!r}"
        )
    return [
        _unit_to_cm(item, where=f"{where}[{index}]")
        for index, item in enumerate(value)
    ]


def _int_list(value: Any, *, where: str, count: int) -> list[int]:
    if not isinstance(value, list) or len(value) != count:
        raise MeshProgramError(
            f"{where}: expected a {count}-element integer list, got {value!r}"
        )
    return [_int(item, where=f"{where}[{index}]") for index, item in enumerate(value)]


def _string(value: Any, *, where: str) -> str:
    if not isinstance(value, str):
        raise MeshProgramError(f"{where}: expected a string literal, got {value!r}")
    return value


def _ident(value: Any, *, where: str) -> str:
    if not isinstance(value, str):
        raise MeshProgramError(f"{where}: expected an identifier, got {value!r}")
    return value


def _int(value: Any, *, where: str) -> int:
    if isinstance(value, bool):
        raise MeshProgramError(f"{where}: expected an integer, got bool")
    if isinstance(value, int):
        return value
    raise MeshProgramError(f"{where}: expected an integer, got {value!r}")


def _stable_seed(*tokens: object) -> int:
    """Return a process-stable 32-bit seed from authoring tokens."""
    state = 0x811C9DC5
    for token in tokens:
        for char in repr(token):
            state ^= ord(char) & 0xFF
            state = (state * 0x01000193) & 0xFFFFFFFF
    return state or 1


def _kwargs(args: list[dict[str, Any]], *, where: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arg in args:
        name = arg.get("name")
        if name is None:
            raise MeshProgramError(
                f"{where}: positional arguments are not supported, use 'name: value'"
            )
        if name in result:
            raise MeshProgramError(f"{where}: duplicate argument {name!r}")
        result[name] = arg.get("value")
    return result


def _eval_box_call(args: list[dict[str, Any]], *, part: str, where: str) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "extents" not in kw:
        raise MeshProgramError(f"{where}: box(...) requires 'extents'")
    extents = _vec3(kw.pop("extents"), where=f"{where}.extents")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown box(...) argument(s): {unknown}")
    return _single_v2_primitive(
        "solid.box",
        target=part,
        parameters={
            "width_cm": extents[0],
            "height_cm": extents[1],
            "depth_cm": extents[2],
        },
        where=where,
    )


def _eval_solid_box_call(args: list[dict[str, Any]], *, part: str, where: str) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "extents" in kw:
        width, height, depth = _vec3(kw.pop("extents"), where=f"{where}.extents")
    else:
        width = _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True) or 0.0
        height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True) or 0.0
        depth = _pop_length_alias(kw, where=where, names=("depth", "depth_cm"), required=True) or 0.0
    blend_mode = _pop_blend_mode(kw, where=where)
    parameters: dict[str, Any] = {
        "width_cm": width,
        "height_cm": height,
        "depth_cm": depth,
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    bevel_width = _pop_length_alias(
        kw,
        where=where,
        names=("bevel_width", "bevel_width_cm", "polybevel_width", "polybevel_width_cm"),
    )
    if bevel_width is not None:
        parameters["bevel_width_cm"] = bevel_width
    for name in ("bevel_segments", "polybevel_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_box(...) argument(s): {unknown}")
    primitive = _single_v2_primitive(
        "solid.box",
        target=part,
        parameters=parameters,
        where=where,
    )
    primitive.blend_mode = blend_mode
    if "solid_box" not in primitive.tags:
        primitive.tags = [*primitive.tags, "solid_box"]
    return primitive


_AXIS_VALUES = {"x", "y", "z"}
_FACE_VALUES = {"+x", "-x", "+y", "-y", "+z", "-z"}


def _axis_arg(value: Any, *, where: str, default: str | None = None) -> str:
    if value is None:
        if default is None:
            raise MeshProgramError(f"{where}: required axis argument is missing")
        return default
    if isinstance(value, str) and value in _AXIS_VALUES:
        return value
    raise MeshProgramError(
        f"{where}: axis must be one of 'x', 'y', 'z', got {value!r}"
    )


def _face_arg(value: Any, *, where: str) -> str:
    if isinstance(value, str) and value in _FACE_VALUES:
        return value
    raise MeshProgramError(
        f"{where}: face must be one of '+x','-x','+y','-y','+z','-z', got {value!r}"
    )


def _eval_solid_panel_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "extents" not in kw:
        raise MeshProgramError(f"{where}: solid_panel(...) requires 'extents'")
    extents = _vec3(kw.pop("extents"), where=f"{where}.extents")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_panel(...) argument(s): {unknown}"
        )
    width, height, thickness = extents
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=part,
        center=(0.0, 0.0, 0.0),
        axis="z",
        profile_polygon=[
            (-width * 0.5, -height * 0.5),
            (width * 0.5, -height * 0.5),
            (width * 0.5, height * 0.5),
            (-width * 0.5, height * 0.5),
        ],
        extrude_height=thickness,
        tags=["solid_panel", "panel_profile"],
        blend_mode="union",
    )


def _eval_solid_rail_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "length" not in kw:
        raise MeshProgramError(f"{where}: solid_rail(...) requires 'length'")
    if "profile" not in kw:
        raise MeshProgramError(f"{where}: solid_rail(...) requires 'profile'")
    length = _unit_to_cm(kw.pop("length"), where=f"{where}.length")
    profile = _unit_to_cm(kw.pop("profile"), where=f"{where}.profile")
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_rail(...) argument(s): {unknown}"
        )
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=part,
        center=(0.0, 0.0, 0.0),
        axis=axis,
        profile_polygon=[
            (-profile * 0.5, -profile * 0.5),
            (profile * 0.5, -profile * 0.5),
            (profile * 0.5, profile * 0.5),
            (-profile * 0.5, profile * 0.5),
        ],
        extrude_height=length,
        tags=["solid_rail", "rail_profile"],
        blend_mode="union",
    )


def _eval_solid_prism_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "extents" not in kw:
        raise MeshProgramError(f"{where}: solid_prism(...) requires 'extents'")
    extents = _vec3(kw.pop("extents"), where=f"{where}.extents")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_prism(...) argument(s): {unknown}"
        )
    width, height, depth = extents
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=part,
        center=(0.0, 0.0, 0.0),
        axis="z",
        profile_polygon=[
            (-width * 0.5, -height * 0.5),
            (width * 0.5, -height * 0.5),
            (0.0, height * 0.5),
        ],
        extrude_height=depth,
        tags=["solid_prism"],
        blend_mode="union",
    )


def _eval_solid_cylinder_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    blend_mode = _pop_blend_mode(kw, where=where)
    radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("radius", "radius_cm"),
        diameter_names=("diameter", "diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "radius_cm": radius,
        "height_cm": _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True),
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    for name in ("segments", "radial_segments", "radial_sections"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    bevel_width = _pop_length_alias(
        kw,
        where=where,
        names=("bevel_width", "bevel_width_cm", "polybevel_width", "polybevel_width_cm"),
    )
    if bevel_width is not None:
        parameters["bevel_width_cm"] = bevel_width
    for name in ("bevel_segments", "polybevel_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_cylinder(...) argument(s): {unknown}"
        )
    primitive = _single_v2_primitive(
        "solid.cylinder",
        target=part,
        parameters=parameters,
        where=where,
    )
    primitive.blend_mode = blend_mode
    if "solid_cylinder" not in primitive.tags:
        primitive.tags = [*primitive.tags, "solid_cylinder"]
    return primitive


def _eval_solid_rounded_box_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "extents" in kw:
        width, height, depth = _vec3(kw.pop("extents"), where=f"{where}.extents")
    else:
        width = _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True) or 0.0
        height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True) or 0.0
        depth = _pop_length_alias(kw, where=where, names=("depth", "depth_cm"), required=True) or 0.0
    blend_mode = _pop_blend_mode(kw, where=where)
    parameters: dict[str, Any] = {
        "width_cm": width,
        "height_cm": height,
        "depth_cm": depth,
        "radius_cm": _pop_length_alias(kw, where=where, names=("radius", "radius_cm"), required=True),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_rounded_box(...) argument(s): {unknown}"
        )
    primitive = _single_v2_primitive(
        "solid.rounded_box",
        target=part,
        parameters=parameters,
        where=where,
    )
    primitive.blend_mode = blend_mode
    if "solid_rounded_box" not in primitive.tags:
        primitive.tags = [*primitive.tags, "solid_rounded_box"]
    return primitive


def _pop_profile_points(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
    min_points: int,
) -> list[tuple[float, float]]:
    present = [name for name in names if name in kw]
    if len(present) != 1:
        raise MeshProgramError(
            f"{where}: requires exactly one of {', '.join(repr(name) for name in names)}"
        )
    return _vec2_length_points(
        kw.pop(present[0]),
        where=f"{where}.{present[0]}",
        min_points=min_points,
    )


def _pop_optional_angle_degrees(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
) -> float | None:
    present = [name for name in names if name in kw]
    if not present:
        return None
    if len(present) != 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    name = present[0]
    raw_unit = "rad" if name == "radians" or name.endswith("_radians") else "deg"
    return _angle_degrees_arg(
        kw.pop(name),
        where=f"{where}.{name}",
        raw_unit=raw_unit,
    )


def _pop_length_alias(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
    required: bool = False,
    default: float | None = None,
) -> float | None:
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    if not present:
        if required:
            raise MeshProgramError(
                f"{where}: requires one of {', '.join(repr(name) for name in names)}"
            )
        return default
    name = present[0]
    return _unit_to_cm(kw.pop(name), where=f"{where}.{name}")


def _pop_radius_or_diameter(
    kw: dict[str, Any],
    *,
    where: str,
    radius_names: tuple[str, ...],
    diameter_names: tuple[str, ...],
    required: bool = False,
) -> float | None:
    radius = _pop_length_alias(kw, where=where, names=radius_names)
    diameter = _pop_length_alias(kw, where=where, names=diameter_names)
    if radius is None and diameter is None:
        if required:
            names = (*radius_names, *diameter_names)
            raise MeshProgramError(
                f"{where}: requires one of {', '.join(repr(name) for name in names)}"
            )
        return None
    if radius is None:
        return float(diameter or 0.0) * 0.5
    if diameter is not None and abs(float(radius) * 2.0 - float(diameter)) > 1e-6:
        raise MeshProgramError(
            f"{where}: radius {radius!r}cm conflicts with diameter {diameter!r}cm"
        )
    return radius


def _pop_half_height_or_height(
    kw: dict[str, Any],
    *,
    where: str,
    op_name: str,
) -> float:
    has_half_height = any(name in kw for name in ("half_height", "half_height_cm"))
    has_height = any(name in kw for name in ("height", "height_cm"))
    if has_half_height and has_height:
        raise MeshProgramError(
            f"{where}: {op_name}(...) accepts either 'half_height' or 'height', not both"
        )
    half_height = _pop_length_alias(
        kw,
        where=where,
        names=("half_height", "half_height_cm"),
    )
    height = _pop_length_alias(kw, where=where, names=("height", "height_cm"))
    if half_height is None:
        if height is None:
            raise MeshProgramError(f"{where}: {op_name}(...) requires 'half_height' or 'height'")
        half_height = height * 0.5
    return half_height


def _pop_number_alias(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
    required: bool = False,
    default: float | None = None,
) -> float | None:
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    if not present:
        if required:
            raise MeshProgramError(
                f"{where}: requires one of {', '.join(repr(name) for name in names)}"
            )
        return default
    name = present[0]
    return _number_arg(kw.pop(name), where=f"{where}.{name}")


def _pop_int_alias(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
    required: bool = False,
    default: int | None = None,
) -> int | None:
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    if not present:
        if required:
            raise MeshProgramError(
                f"{where}: requires one of {', '.join(repr(name) for name in names)}"
            )
        return default
    name = present[0]
    return _int(kw.pop(name), where=f"{where}.{name}")


def _pop_length_tuple_alias(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
    count: int,
    required: bool = False,
) -> tuple[float, ...] | None:
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    if not present:
        if required:
            raise MeshProgramError(
                f"{where}: requires one of {', '.join(repr(name) for name in names)}"
            )
        return None
    name = present[0]
    raw = kw.pop(name)
    if not isinstance(raw, list) or len(raw) != count:
        raise MeshProgramError(
            f"{where}.{name}: expected a {count}-element list literal, got {raw!r}"
        )
    return tuple(_unit_to_cm(item, where=f"{where}.{name}[{index}]") for index, item in enumerate(raw))


def _pop_angle_alias(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
    required: bool = False,
    default: float | None = None,
) -> float | None:
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    if not present:
        if required:
            raise MeshProgramError(
                f"{where}: requires one of {', '.join(repr(name) for name in names)}"
            )
        return default
    name = present[0]
    raw_unit = "rad" if name == "radians" or name.endswith("_radians") else "deg"
    return _angle_degrees_arg(
        kw.pop(name),
        where=f"{where}.{name}",
        raw_unit=raw_unit,
    )


def _pop_string_alias(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
    default: str | None = None,
    allowed: set[str] | None = None,
) -> str | None:
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    if not present:
        value = default
    else:
        name = present[0]
        value = _string(kw.pop(name), where=f"{where}.{name}")
    if value is not None and allowed is not None and value not in allowed:
        raise MeshProgramError(
            f"{where}: value must be one of {sorted(allowed)}, got {value!r}"
        )
    return value


def _pop_bool_alias(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...],
    default: bool | None = None,
) -> bool | None:
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    if not present:
        return default
    name = present[0]
    return _bool_arg(kw.pop(name), where=f"{where}.{name}")


def _pop_blend_mode(kw: dict[str, Any], *, where: str) -> str:
    return _pop_string_alias(
        kw,
        where=where,
        names=("blend_mode", "blend"),
        default="union",
        allowed={"union", "subtract", "intersect"},
    ) or "union"


def _pop_optional_center(kw: dict[str, Any], *, where: str) -> tuple[float, float, float] | None:
    if "center" not in kw:
        return None
    return _vec3(kw.pop("center"), where=f"{where}.center")


def _eval_solid_revolved_profile_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    profile_points = _pop_profile_points(
        kw,
        where=where,
        names=("profile", "profile_points"),
        min_points=1,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    revolve_degrees = _pop_optional_angle_degrees(
        kw,
        where=where,
        names=("revolve_degrees", "degrees", "angle", "radians"),
    )
    start_degrees = _pop_optional_angle_degrees(
        kw,
        where=where,
        names=("revolve_start_degrees", "start_degrees", "start_angle", "start_radians"),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_revolved_profile(...) argument(s): {unknown}"
        )
    if revolve_degrees is not None and (
        revolve_degrees <= 0.0 or revolve_degrees > 360.0
    ):
        raise MeshProgramError(
            f"{where}.revolve_degrees: must satisfy 0 < value <= 360, "
            f"got {revolve_degrees}"
        )
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=part,
        center=(0.0, 0.0, 0.0),
        axis=axis,
        profile_points=profile_points,
        revolve_degrees=revolve_degrees,
        revolve_start_degrees=start_degrees,
        tags=["solid_revolved_profile", "mesh_program_profile"],
        blend_mode="union",
    )


def _eval_solid_extruded_profile_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    profile_polygon = _pop_profile_points(
        kw,
        where=where,
        names=("profile", "profile_polygon"),
        min_points=3,
    )
    height_names = [name for name in ("height", "extrude_height") if name in kw]
    if len(height_names) != 1:
        raise MeshProgramError(
            f"{where}: requires exactly one of 'height' or 'extrude_height'"
        )
    extrude_height = _unit_to_cm(
        kw.pop(height_names[0]),
        where=f"{where}.{height_names[0]}",
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z")
    start_scale = kw.pop("start_scale", kw.pop("extrude_start_scale", None))
    end_scale = kw.pop("end_scale", kw.pop("extrude_end_scale", None))
    twist_degrees = _pop_optional_angle_degrees(
        kw,
        where=where,
        names=("twist_degrees", "twist", "twist_radians"),
    )
    segments_value = kw.pop("segments", kw.pop("extrude_segments", None))
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_extruded_profile(...) argument(s): {unknown}"
        )
    if extrude_height <= 0.0:
        raise MeshProgramError(f"{where}.height: must be > 0, got {extrude_height}cm")
    start_scale_value = None
    if start_scale is not None:
        start_scale_value = _number_arg(start_scale, where=f"{where}.start_scale")
        if start_scale_value <= 0.0:
            raise MeshProgramError(
                f"{where}.start_scale: must be > 0, got {start_scale_value}"
            )
    end_scale_value = None
    if end_scale is not None:
        end_scale_value = _number_arg(end_scale, where=f"{where}.end_scale")
        if end_scale_value <= 0.0:
            raise MeshProgramError(
                f"{where}.end_scale: must be > 0, got {end_scale_value}"
            )
    segments = None
    if segments_value is not None:
        segments = _int(segments_value, where=f"{where}.segments")
        if segments < 1:
            raise MeshProgramError(f"{where}.segments: must be >= 1, got {segments}")
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=part,
        center=(0.0, 0.0, 0.0),
        axis=axis,
        profile_polygon=profile_polygon,
        extrude_height=extrude_height,
        extrude_start_scale=start_scale_value,
        extrude_end_scale=end_scale_value,
        extrude_twist_degrees=twist_degrees,
        extrude_segments=segments,
        tags=["solid_extruded_profile", "mesh_program_profile"],
        blend_mode="union",
    )


def _v2_primitives_from_op(
    op_name: str,
    *,
    target: str,
    parameters: dict[str, Any],
    where: str,
    geometry_kernel: Any | None = None,
) -> list[ShapePrimitive]:
    from ..asset_quality.shape_ir_v2 import (
        SHAPE_IR_V2_VERSION,
        ShapeOp,
        ShapeProgram,
        _primitive_from_v1_record,
        lower_to_v1,
    )

    op = ShapeOp(
        op=op_name,
        target=target,
        parameters=parameters,
        purpose=f"mesh_program.{op_name.replace('.', '_')}",
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name=f"mesh_program_{target}",
        family=None,
        ops=(op,),
    )
    try:
        result = lower_to_v1(program, geometry_kernel=geometry_kernel)
    except (TypeError, ValueError) as exc:
        raise MeshProgramError(f"{where}: {exc}") from exc
    if result.diagnostics:
        first = result.diagnostics[0]
        code = first.get("code") or "shape_ir_v2_lowering_failed"
        message = first.get("message") or first.get("param") or first
        raise MeshProgramError(f"{where}: {code}: {message}")
    if not result.v1_records:
        raise MeshProgramError(f"{where}: {op_name} produced no geometry")
    primitives = [_primitive_from_v1_record(record) for record in result.v1_records]
    primitive_count = len(primitives)
    for index, primitive in enumerate(primitives):
        _apply_mesh_vertex_bounds(primitive)
        _attach_mesh_program_generated_operation_history(
            primitive,
            op_name=op_name,
            target=target,
            parameters=parameters,
            primitive_count=primitive_count,
            primitive_index=index,
        )
    return primitives


def _v2_kernel_primitives_from_op(
    op_name: str,
    *,
    target: str,
    parameters: dict[str, Any],
    where: str,
) -> list[ShapePrimitive]:
    from ..geometry.kernel import resolve_geometry_kernel

    return _v2_primitives_from_op(
        op_name,
        target=target,
        parameters=parameters,
        where=where,
        geometry_kernel=resolve_geometry_kernel(),
    )


def _single_v2_primitive(
    op_name: str,
    *,
    target: str,
    parameters: dict[str, Any],
    where: str,
) -> ShapePrimitive:
    primitives = _v2_primitives_from_op(
        op_name,
        target=target,
        parameters=parameters,
        where=where,
    )
    if len(primitives) != 1:
        raise MeshProgramError(
            f"{where}: {op_name} produced {len(primitives)} primitives; "
            "this mesh_program constructor requires a single solid"
        )
    return primitives[0]


def _single_v2_kernel_primitive(
    op_name: str,
    *,
    target: str,
    parameters: dict[str, Any],
    where: str,
) -> ShapePrimitive:
    primitives = _v2_kernel_primitives_from_op(
        op_name,
        target=target,
        parameters=parameters,
        where=where,
    )
    if len(primitives) != 1:
        raise MeshProgramError(
            f"{where}: {op_name} produced {len(primitives)} primitives; "
            "this mesh_program constructor requires a single kernelized solid"
        )
    return primitives[0]


def _eval_swept_profile_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    cross_section = _pop_profile_points(
        kw,
        where=where,
        names=("cross_section", "profile", "profile_polygon"),
        min_points=3,
    )
    path_names = [name for name in ("path", "sweep_path") if name in kw]
    if len(path_names) != 1:
        raise MeshProgramError(f"{where}: requires exactly one of 'path' or 'sweep_path'")
    path_name = path_names[0]
    parameters: dict[str, Any] = {
        "cross_section": cross_section,
        "sweep_path": _vec3_length_points(
            kw.pop(path_name),
            where=f"{where}.{path_name}",
            min_points=2,
        ),
    }
    if "blend_mode" in kw or "blend" in kw:
        parameters["blend_mode"] = _pop_blend_mode(kw, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown swept_profile(...) argument(s): {unknown}"
        )
    primitive = _single_v2_kernel_primitive(
        "sop.sweep",
        target=part,
        parameters=parameters,
        where=where,
    )
    for tag in ("solid_swept_profile", "mesh_program_sweep"):
        if tag not in primitive.tags:
            primitive.tags = [*primitive.tags, tag]
    return primitive


def _eval_sop_sweep_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    cross_section = _pop_profile_points(
        kw,
        where=where,
        names=("cross_section", "profile", "profile_polygon"),
        min_points=3,
    )
    path_names = [name for name in ("path", "sweep_path") if name in kw]
    if len(path_names) != 1:
        raise MeshProgramError(f"{where}: requires exactly one of 'path' or 'sweep_path'")
    path_name = path_names[0]
    parameters: dict[str, Any] = {
        "cross_section": cross_section,
        "sweep_path": _vec3_length_points(
            kw.pop(path_name),
            where=f"{where}.{path_name}",
            min_points=2,
        ),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    bevel_width = _pop_length_alias(
        kw,
        where=where,
        names=("bevel_width", "bevel_width_cm", "bevel", "bevel_cm"),
    )
    if bevel_width is not None:
        parameters["bevel_width_cm"] = bevel_width
    bevel_segments = _pop_int_alias(
        kw,
        where=where,
        names=("bevel_segments",),
    )
    if bevel_segments is not None:
        parameters["bevel_segments"] = bevel_segments
    if "blend_mode" in kw or "blend" in kw:
        parameters["blend_mode"] = _pop_blend_mode(kw, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_sweep(...) argument(s): {unknown}")
    return _single_v2_kernel_primitive(
        "sop.sweep",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_lofted_solid_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "cross_sections" not in kw:
        raise MeshProgramError(f"{where}: lofted_solid(...) requires 'cross_sections'")
    raw_sections = kw.pop("cross_sections")
    if not isinstance(raw_sections, list) or len(raw_sections) < 2:
        raise MeshProgramError(
            f"{where}.cross_sections: expected at least two section polygons"
        )
    cross_sections = [
        _vec2_length_points(
            section,
            where=f"{where}.cross_sections[{index}]",
            min_points=3,
        )
        for index, section in enumerate(raw_sections)
    ]
    vertex_count = len(cross_sections[0])
    for index, section in enumerate(cross_sections):
        if len(section) != vertex_count:
            raise MeshProgramError(
                f"{where}.cross_sections[{index}]: expected {vertex_count} points, "
                f"got {len(section)}"
            )
    center_names = [name for name in ("section_centers", "centers", "path") if name in kw]
    if len(center_names) != 1:
        raise MeshProgramError(
            f"{where}: requires exactly one of 'section_centers', 'centers', or 'path'"
        )
    center_name = center_names[0]
    section_centers = _vec3_length_points(
        kw.pop(center_name),
        where=f"{where}.{center_name}",
        min_points=2,
    )
    if len(section_centers) != len(cross_sections):
        raise MeshProgramError(
            f"{where}: section_centers count must match cross_sections count "
            f"({len(section_centers)} != {len(cross_sections)})"
        )
    parameters: dict[str, Any] = {
        "sections": [
            {
                "center": section_centers[index],
                "profile_polygon": cross_sections[index],
            }
            for index in range(len(cross_sections))
        ],
    }
    if "blend_mode" in kw or "blend" in kw:
        parameters["blend_mode"] = _pop_blend_mode(kw, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown lofted_solid(...) argument(s): {unknown}"
        )
    primitive = _single_v2_kernel_primitive(
        "sop.loft",
        target=part,
        parameters=parameters,
        where=where,
    )
    for tag in ("solid_lofted_solid", "mesh_program_loft"):
        if tag not in primitive.tags:
            primitive.tags = [*primitive.tags, tag]
    return primitive


def _eval_sop_loft_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "cross_sections" not in kw:
        raise MeshProgramError(f"{where}: sop_loft(...) requires 'cross_sections'")
    raw_sections = kw.pop("cross_sections")
    if not isinstance(raw_sections, list) or len(raw_sections) < 2:
        raise MeshProgramError(
            f"{where}.cross_sections: expected at least two section polygons"
        )
    cross_sections = [
        _vec2_length_points(
            section,
            where=f"{where}.cross_sections[{index}]",
            min_points=3,
        )
        for index, section in enumerate(raw_sections)
    ]
    vertex_count = len(cross_sections[0])
    for index, section in enumerate(cross_sections):
        if len(section) != vertex_count:
            raise MeshProgramError(
                f"{where}.cross_sections[{index}]: expected {vertex_count} points, "
                f"got {len(section)}"
            )
    center_names = [name for name in ("section_centers", "centers", "path") if name in kw]
    if len(center_names) != 1:
        raise MeshProgramError(
            f"{where}: requires exactly one of 'section_centers', 'centers', or 'path'"
        )
    center_name = center_names[0]
    section_centers = _vec3_length_points(
        kw.pop(center_name),
        where=f"{where}.{center_name}",
        min_points=2,
    )
    if len(section_centers) != len(cross_sections):
        raise MeshProgramError(
            f"{where}: section_centers count must match cross_sections count "
            f"({len(section_centers)} != {len(cross_sections)})"
        )
    parameters: dict[str, Any] = {
        "sections": [
            {
                "center": section_centers[index],
                "profile_polygon": cross_sections[index],
            }
            for index in range(len(cross_sections))
        ],
    }
    bevel_width = _pop_length_alias(
        kw,
        where=where,
        names=("bevel_width", "bevel_width_cm", "bevel", "bevel_cm"),
    )
    if bevel_width is not None:
        parameters["bevel_width_cm"] = bevel_width
    bevel_segments = _pop_int_alias(
        kw,
        where=where,
        names=("bevel_segments",),
    )
    if bevel_segments is not None:
        parameters["bevel_segments"] = bevel_segments
    if "blend_mode" in kw or "blend" in kw:
        parameters["blend_mode"] = _pop_blend_mode(kw, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_loft(...) argument(s): {unknown}")
    return _single_v2_kernel_primitive(
        "sop.loft",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_helical_sweep_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("radius", "radius_cm", "coil_radius", "coil_radius_cm"),
        diameter_names=("diameter", "diameter_cm", "coil_diameter", "coil_diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "radius_cm": radius,
        "height_cm": _pop_length_alias(
            kw,
            where=where,
            names=("height", "height_cm"),
            required=True,
        ),
        "turns": _pop_number_alias(
            kw,
            where=where,
            names=("turns",),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
    if "cross_section" in kw:
        parameters["cross_section"] = _vec2_length_points(
            kw.pop("cross_section"),
            where=f"{where}.cross_section",
            min_points=3,
        )
    else:
        parameters["tube_radius_cm"] = _pop_radius_or_diameter(
            kw,
            where=where,
            radius_names=("tube_radius", "tube_radius_cm", "wire_radius", "wire_radius_cm"),
            diameter_names=("tube_diameter", "tube_diameter_cm", "wire_diameter", "wire_diameter_cm"),
            required=True,
        )
    for target, names in (
        ("segments_per_turn", ("segments_per_turn", "samples_per_turn", "path_segments")),
        ("cross_section_segments", ("cross_section_segments", "profile_segments")),
    ):
        value = _pop_int_alias(kw, where=where, names=names)
        if value is not None:
            parameters[target] = value
    phase = _pop_angle_alias(
        kw,
        where=where,
        names=("phase_degrees", "phase", "phase_radians"),
    )
    if phase is not None:
        parameters["phase_degrees"] = phase
    handedness = _pop_string_alias(
        kw,
        where=where,
        names=("handedness",),
        default="right",
        allowed={"right", "left"},
    )
    if handedness is not None:
        parameters["handedness"] = handedness
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown helical_sweep(...) argument(s): {unknown}"
        )
    return _single_v2_kernel_primitive(
        "sop.helical_sweep",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_sop_polywire_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "path" not in kw:
        raise MeshProgramError(f"{where}: polywire(...) requires 'path'")
    parameters: dict[str, Any] = {
        "path": _vec3_length_points(
            kw.pop("path"),
            where=f"{where}.path",
            min_points=2,
        ),
    }
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "wire_radius", "wire_radius_cm", "tube_radius", "tube_radius_cm"),
    )
    if radius is not None:
        parameters["radius_cm"] = radius
    start_radius = _pop_length_alias(
        kw,
        where=where,
        names=("start_radius", "start_radius_cm"),
    )
    if start_radius is not None:
        parameters["start_radius_cm"] = start_radius
    end_radius = _pop_length_alias(
        kw,
        where=where,
        names=("end_radius", "end_radius_cm"),
    )
    if end_radius is not None:
        parameters["end_radius_cm"] = end_radius
    present_radius_profiles = [
        name
        for name in ("radii", "radii_cm", "radius_profile", "radius_profile_cm", "radius_values", "radius_values_cm")
        if name in kw
    ]
    if len(present_radius_profiles) > 1:
        raise MeshProgramError(
            f"{where}: only one radius profile may be supplied, got {present_radius_profiles!r}"
        )
    if present_radius_profiles:
        profile_name = present_radius_profiles[0]
        parameters["radii_cm"] = _length_list(
            kw.pop(profile_name),
            where=f"{where}.{profile_name}",
            min_count=2,
        )
    if "cross_section" in kw:
        parameters["cross_section"] = _vec2_length_points(
            kw.pop("cross_section"),
            where=f"{where}.cross_section",
            min_points=3,
        )
    segments = _pop_int_alias(
        kw,
        where=where,
        names=("cross_section_segments", "profile_segments", "segments"),
    )
    if segments is not None:
        parameters["cross_section_segments"] = segments
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    if "blend_mode" in kw or "blend" in kw:
        parameters["blend_mode"] = _pop_blend_mode(kw, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown polywire(...) argument(s): {unknown}")
    return _single_v2_kernel_primitive(
        "sop.polywire",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_spring_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("radius", "radius_cm", "coil_radius", "coil_radius_cm"),
        diameter_names=("diameter", "diameter_cm", "coil_diameter", "coil_diameter_cm"),
        required=True,
    )
    wire_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("wire_radius", "wire_radius_cm", "tube_radius", "tube_radius_cm"),
        diameter_names=("wire_diameter", "wire_diameter_cm", "tube_diameter", "tube_diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "radius_cm": radius,
        "wire_radius_cm": wire_radius,
        "height_cm": _pop_length_alias(
            kw,
            where=where,
            names=("height", "height_cm"),
            required=True,
        ),
        "turns": _pop_number_alias(
            kw,
            where=where,
            names=("turns",),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
    for name in ("segments_per_turn", "cross_section_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    phase = _pop_angle_alias(
        kw,
        where=where,
        names=("phase_degrees", "phase", "phase_radians"),
    )
    if phase is not None:
        parameters["phase_degrees"] = phase
    handedness = _pop_string_alias(
        kw,
        where=where,
        names=("handedness",),
        default="right",
        allowed={"right", "left"},
    )
    if handedness is not None:
        parameters["handedness"] = handedness
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_spring(...) argument(s): {unknown}"
        )
    return _single_v2_kernel_primitive(
        "solid.spring",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_tube_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    outer_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("outer_radius", "outer_radius_cm"),
        diameter_names=("outer_diameter", "outer_diameter_cm", "diameter", "diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "outer_radius_cm": outer_radius,
        "height_cm": _pop_length_alias(
            kw,
            where=where,
            names=("height", "height_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
    inner_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("inner_radius", "inner_radius_cm", "bore_radius", "bore_radius_cm"),
        diameter_names=("inner_diameter", "inner_diameter_cm", "bore_diameter", "bore_diameter_cm"),
    )
    wall_thickness = _pop_length_alias(
        kw,
        where=where,
        names=("wall_thickness", "wall_thickness_cm"),
    )
    if inner_radius is None and wall_thickness is None:
        raise MeshProgramError(
            f"{where}: solid_tube(...) requires inner_radius or wall_thickness"
        )
    if inner_radius is not None and wall_thickness is not None:
        raise MeshProgramError(
            f"{where}: only one of 'inner_radius' or 'wall_thickness' may be supplied"
        )
    if inner_radius is not None:
        parameters["inner_radius_cm"] = inner_radius
    else:
        parameters["wall_thickness_cm"] = wall_thickness
    segments = _pop_int_alias(kw, where=where, names=("segments",))
    if segments is not None:
        parameters["segments"] = segments
    rim_bevel = _pop_length_alias(
        kw,
        where=where,
        names=("rim_bevel", "rim_bevel_cm"),
    )
    if rim_bevel is not None:
        parameters["rim_bevel_cm"] = rim_bevel
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_tube(...) argument(s): {unknown}")
    return _single_v2_kernel_primitive(
        "solid.tube",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_curve_extruded_profile_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    curve_name = next((name for name in ("profile_curve", "curve", "profile") if name in kw), "")
    if not curve_name:
        raise MeshProgramError(
            f"{where}: solid_curve_extruded_profile(...) requires one of 'profile_curve', 'curve', or 'profile'"
        )
    parameters: dict[str, Any] = {
        "profile_curve": _vec2_length_points(
            kw.pop(curve_name),
            where=f"{where}.{curve_name}",
            min_points=3,
        ),
        "extrude_height_cm": _pop_length_alias(
            kw,
            where=where,
            names=("extrude_height", "extrude_height_cm", "height", "height_cm"),
            required=True,
        ),
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z"),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    bevel_width = _pop_length_alias(
        kw,
        where=where,
        names=("bevel_width", "bevel_width_cm", "polybevel_width", "polybevel_width_cm"),
    )
    if bevel_width is not None:
        parameters["bevel_width_cm"] = bevel_width
    for name in ("extrude_segments", "segments", "bevel_segments", "polybevel_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    for name in ("extrude_start_scale", "start_scale", "extrude_end_scale", "end_scale"):
        value = _pop_number_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    twist = _pop_angle_alias(
        kw,
        where=where,
        names=("extrude_twist_degrees", "twist_degrees", "twist", "twist_radians"),
    )
    if twist is not None:
        parameters["extrude_twist_degrees"] = twist
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_curve_extruded_profile(...) argument(s): {unknown}"
        )
    return _single_v2_kernel_primitive(
        "solid.curve_extruded_profile",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_curve_revolved_profile_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    curve_name = next((name for name in ("profile_curve", "curve", "profile") if name in kw), "")
    if not curve_name:
        raise MeshProgramError(
            f"{where}: solid_curve_revolved_profile(...) requires one of 'profile_curve', 'curve', or 'profile'"
        )
    parameters: dict[str, Any] = {
        "profile_curve": _vec2_length_points(
            kw.pop(curve_name),
            where=f"{where}.{curve_name}",
            min_points=2,
        ),
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y"),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    revolve_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("revolve_degrees", "angle_degrees", "angle", "radians"),
    )
    if revolve_degrees is not None:
        parameters["revolve_degrees"] = revolve_degrees
    start_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("revolve_start_degrees", "start_angle_degrees", "start_angle", "start_radians"),
    )
    if start_degrees is not None:
        parameters["revolve_start_degrees"] = start_degrees
    for name in ("revolve_sections", "revolve_segments", "radial_sections", "segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_curve_revolved_profile(...) argument(s): {unknown}"
        )
    return _single_v2_kernel_primitive(
        "solid.curve_revolved_profile",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_curve_swept_profile_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    cross_section_name = next(
        (name for name in ("cross_section_curve", "cross_section", "profile_curve", "profile") if name in kw),
        "",
    )
    sweep_name = next((name for name in ("sweep_curve", "sweep_path", "path", "curve") if name in kw), "")
    if not cross_section_name:
        raise MeshProgramError(
            f"{where}: solid_curve_swept_profile(...) requires a cross-section curve"
        )
    if not sweep_name:
        raise MeshProgramError(
            f"{where}: solid_curve_swept_profile(...) requires a sweep curve/path"
        )
    parameters: dict[str, Any] = {
        "cross_section_curve": _vec2_length_points(
            kw.pop(cross_section_name),
            where=f"{where}.{cross_section_name}",
            min_points=3,
        ),
        "sweep_curve": _vec3_length_points(
            kw.pop(sweep_name),
            where=f"{where}.{sweep_name}",
            min_points=2,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    bevel_width = _pop_length_alias(
        kw,
        where=where,
        names=("bevel_width", "bevel_width_cm", "polybevel_width", "polybevel_width_cm"),
    )
    if bevel_width is not None:
        parameters["bevel_width_cm"] = bevel_width
    for name in ("bevel_segments", "polybevel_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_curve_swept_profile(...) argument(s): {unknown}"
        )
    return _single_v2_kernel_primitive(
        "solid.curve_swept_profile",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_curve_lofted_solid_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "section_curves" not in kw:
        raise MeshProgramError(f"{where}: solid_curve_lofted_solid(...) requires 'section_curves'")
    if "section_centers" not in kw:
        raise MeshProgramError(f"{where}: solid_curve_lofted_solid(...) requires 'section_centers'")
    raw_curves = kw.pop("section_curves")
    if not isinstance(raw_curves, list) or len(raw_curves) < 2:
        raise MeshProgramError(
            f"{where}.section_curves: expected at least two section curve point lists"
        )
    section_centers = _vec3_length_points(
        kw.pop("section_centers"),
        where=f"{where}.section_centers",
        min_points=2,
    )
    if len(raw_curves) != len(section_centers):
        raise MeshProgramError(
            f"{where}: section_curves count must match section_centers count "
            f"({len(raw_curves)} != {len(section_centers)})"
        )
    sections = []
    for index, raw_curve in enumerate(raw_curves):
        sections.append(
            {
                "profile_curve": _vec2_length_points(
                    raw_curve,
                    where=f"{where}.section_curves[{index}]",
                    min_points=3,
                ),
                "center": section_centers[index],
            }
        )
    parameters: dict[str, Any] = {
        "sections": sections,
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    for name in ("section_samples", "profile_samples", "samples", "sample_count"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    bevel_width = _pop_length_alias(
        kw,
        where=where,
        names=("bevel_width", "bevel_width_cm", "polybevel_width", "polybevel_width_cm"),
    )
    if bevel_width is not None:
        parameters["bevel_width_cm"] = bevel_width
    for name in ("bevel_segments", "polybevel_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_curve_lofted_solid(...) argument(s): {unknown}"
        )
    return _single_v2_kernel_primitive(
        "solid.curve_lofted_solid",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_sphere_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    blend_mode = _pop_blend_mode(kw, where=where)
    radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("radius", "radius_cm"),
        diameter_names=("diameter", "diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "radius_cm": radius,
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    for name in ("subdivisions", "subdivision_levels", "segments", "radial_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_sphere(...) argument(s): {unknown}")
    primitive = _single_v2_primitive(
        "solid.sphere",
        target=part,
        parameters=parameters,
        where=where,
    )
    primitive.blend_mode = blend_mode
    if "solid_sphere" not in primitive.tags:
        primitive.tags = [*primitive.tags, "solid_sphere"]
    return primitive


def _eval_solid_torus_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    blend_mode = _pop_blend_mode(kw, where=where)
    major_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("major_radius", "major_radius_cm", "ring_radius", "ring_radius_cm"),
        diameter_names=("major_diameter", "major_diameter_cm", "ring_diameter", "ring_diameter_cm"),
        required=True,
    )
    minor_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("minor_radius", "minor_radius_cm", "tube_radius", "tube_radius_cm"),
        diameter_names=("minor_diameter", "minor_diameter_cm", "tube_diameter", "tube_diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "major_radius_cm": major_radius,
        "minor_radius_cm": minor_radius,
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    for name in (
        "major_sections",
        "major_segments",
        "segments",
        "minor_sections",
        "minor_segments",
        "tube_segments",
    ):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_torus(...) argument(s): {unknown}")
    primitive = _single_v2_primitive(
        "solid.torus",
        target=part,
        parameters=parameters,
        where=where,
    )
    primitive.blend_mode = blend_mode
    if "solid_torus" not in primitive.tags:
        primitive.tags = [*primitive.tags, "solid_torus"]
    return primitive


def _eval_solid_curved_tube_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    tube_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("tube_radius", "tube_radius_cm", "minor_radius", "minor_radius_cm"),
        diameter_names=("tube_diameter", "tube_diameter_cm", "minor_diameter", "minor_diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "tube_radius_cm": tube_radius,
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    if "path" in kw:
        parameters["path"] = _vec3_length_points(
            kw.pop("path"),
            where=f"{where}.path",
            min_points=2,
        )
    else:
        parameters["radius_cm"] = _pop_radius_or_diameter(
            kw,
            where=where,
            radius_names=("radius", "radius_cm", "bend_radius", "bend_radius_cm"),
            diameter_names=("diameter", "diameter_cm", "bend_diameter", "bend_diameter_cm"),
            required=True,
        )
        angle = _pop_angle_alias(
            kw,
            where=where,
            names=("angle_degrees", "angle", "angle_radians"),
            required=True,
        )
        parameters["angle_degrees"] = angle
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="plane_axis", default="z")
    start_angle = _pop_angle_alias(
        kw,
        where=where,
        names=("start_angle_degrees", "start_angle", "start_radians"),
    )
    if start_angle is not None:
        parameters["start_angle_degrees"] = start_angle
    path_segments = _pop_int_alias(kw, where=where, names=("path_segments", "segments"))
    if path_segments is not None:
        parameters["path_segments"] = path_segments
    cross_section_segments = _pop_int_alias(
        kw,
        where=where,
        names=("cross_section_segments",),
    )
    if cross_section_segments is not None:
        parameters["cross_section_segments"] = cross_section_segments
    inner_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("inner_radius", "inner_radius_cm", "bore_radius", "bore_radius_cm"),
        diameter_names=("inner_diameter", "inner_diameter_cm", "bore_diameter", "bore_diameter_cm"),
    )
    if inner_radius is not None:
        parameters["inner_radius_cm"] = inner_radius
    _pop_optional_length_parameter(kw, parameters, where=where, target="wall_thickness_cm", names=("wall_thickness", "wall_thickness_cm"))
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_curved_tube(...) argument(s): {unknown}"
        )
    return _v2_kernel_primitives_from_op(
        "solid.curved_tube",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_gear_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    teeth = _pop_int_alias(
        kw,
        where=where,
        names=("teeth",),
        required=True,
    )
    pitch_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("pitch_radius", "pitch_radius_cm"),
        diameter_names=("pitch_diameter", "pitch_diameter_cm"),
    )
    outer_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("outer_radius", "outer_radius_cm"),
        diameter_names=("outer_diameter", "outer_diameter_cm"),
    )
    if pitch_radius is None:
        if outer_radius is None:
            raise MeshProgramError(
                f"{where}: requires one of 'pitch_radius', 'pitch_radius_cm', 'pitch_diameter', 'pitch_diameter_cm', 'outer_radius', 'outer_radius_cm', 'outer_diameter', 'outer_diameter_cm'"
            )
        pitch_radius = float(outer_radius) * float(teeth) / float(max(teeth + 2, 1))
    parameters: dict[str, Any] = {
        "teeth": teeth,
        "pitch_radius_cm": pitch_radius,
        "thickness_cm": _pop_length_alias(
            kw,
            where=where,
            names=("thickness", "thickness_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="z")
    if outer_radius is not None:
        parameters["outer_radius_cm"] = outer_radius
    bore_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("bore_radius", "bore_radius_cm", "hole_radius", "hole_radius_cm"),
        diameter_names=("bore_diameter", "bore_diameter_cm", "hole_diameter", "hole_diameter_cm"),
    )
    if bore_radius is not None:
        parameters["bore_radius_cm"] = bore_radius
    length_fields = {
        "addendum_cm": ("addendum", "addendum_cm"),
        "dedendum_cm": ("dedendum", "dedendum_cm"),
        "root_radius_cm": ("root_radius", "root_radius_cm"),
        "backlash_cm": ("backlash", "backlash_cm"),
        "bevel_width_cm": ("bevel_width", "bevel_width_cm"),
    }
    for parameter_name, aliases in length_fields.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    pressure_angle = _pop_angle_alias(
        kw,
        where=where,
        names=("pressure_angle_degrees", "pressure_angle", "pressure_angle_radians"),
    )
    if pressure_angle is not None:
        parameters["pressure_angle_degrees"] = pressure_angle
    helix_angle = _pop_angle_alias(
        kw,
        where=where,
        names=("helix_angle_degrees", "helix_angle", "helix_angle_radians"),
    )
    if helix_angle is not None:
        parameters["helix_angle_degrees"] = helix_angle
    twist = _pop_angle_alias(
        kw,
        where=where,
        names=("twist_degrees", "twist", "twist_radians"),
    )
    if twist is not None:
        parameters["twist_degrees"] = twist
    for name in ("tooth_samples", "helix_segments", "twist_segments", "bevel_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    helix_handedness = _pop_string_alias(
        kw,
        where=where,
        names=("helix_handedness", "handedness"),
        default="right",
        allowed={"right", "left"},
    )
    if helix_handedness is not None:
        parameters["helix_handedness"] = helix_handedness
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_gear(...) argument(s): {unknown}")
    return _single_v2_kernel_primitive(
        "solid.gear",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_threaded_cylinder_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("radius", "radius_cm"),
        diameter_names=("diameter", "diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "radius_cm": radius,
        "height_cm": _pop_length_alias(
            kw,
            where=where,
            names=("height", "height_cm"),
            required=True,
        ),
        "thread_pitch_cm": _pop_length_alias(
            kw,
            where=where,
            names=("thread_pitch", "thread_pitch_cm", "pitch", "pitch_cm"),
            required=True,
        ),
        "thread_depth_cm": _pop_length_alias(
            kw,
            where=where,
            names=("thread_depth", "thread_depth_cm", "depth", "depth_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
    thread_profile_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("thread_profile_radius", "thread_profile_radius_cm"),
        diameter_names=("thread_profile_diameter", "thread_profile_diameter_cm"),
    )
    if thread_profile_radius is not None:
        parameters["thread_profile_radius_cm"] = thread_profile_radius
    for parameter_name, aliases in {
        "thread_clearance_cm": ("thread_clearance", "thread_clearance_cm"),
        "thread_start_clearance_cm": (
            "thread_start_clearance",
            "thread_start_clearance_cm",
        ),
        "thread_end_clearance_cm": (
            "thread_end_clearance",
            "thread_end_clearance_cm",
        ),
        "thread_profile_width_cm": (
            "thread_profile_width",
            "thread_profile_width_cm",
        ),
        "thread_profile_height_cm": (
            "thread_profile_height",
            "thread_profile_height_cm",
        ),
        "thread_profile_top_width_cm": (
            "thread_profile_top_width",
            "thread_profile_top_width_cm",
        ),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    turns = _pop_number_alias(kw, where=where, names=("turns",))
    if turns is not None:
        parameters["turns"] = turns
    for target, names in (
        ("segments_per_turn", ("segments_per_turn", "thread_segments", "segments")),
        ("cross_section_segments", ("cross_section_segments", "thread_cross_section_segments")),
    ):
        value = _pop_int_alias(kw, where=where, names=names)
        if value is not None:
            parameters[target] = value
    phase = _pop_angle_alias(
        kw,
        where=where,
        names=("phase_degrees", "phase", "phase_radians"),
    )
    if phase is not None:
        parameters["phase_degrees"] = phase
    handedness = _pop_string_alias(
        kw,
        where=where,
        names=("handedness",),
        default="right",
        allowed={"right", "left"},
    )
    if handedness is not None:
        parameters["handedness"] = handedness
    thread_profile = _pop_string_alias(
        kw,
        where=where,
        names=("thread_profile",),
        default=None,
        allowed={
            "round",
            "circular",
            "triangle",
            "triangular",
            "square",
            "rectangular",
            "trapezoid",
            "trapezoidal",
        },
    )
    if thread_profile is not None:
        parameters["thread_profile"] = thread_profile
    if "thread_cross_section" in kw:
        parameters["thread_cross_section"] = _vec2_length_points(
            kw.pop("thread_cross_section"),
            where=f"{where}.thread_cross_section",
            min_points=3,
        )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_threaded_cylinder(...) argument(s): {unknown}"
        )
    return _v2_kernel_primitives_from_op(
        "solid.threaded_cylinder",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_flange_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    outer_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("outer_radius", "outer_radius_cm"),
        diameter_names=("outer_diameter", "outer_diameter_cm", "diameter", "diameter_cm"),
        required=True,
    )
    bore_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("bore_radius", "bore_radius_cm", "inner_radius", "inner_radius_cm"),
        diameter_names=("bore_diameter", "bore_diameter_cm", "inner_diameter", "inner_diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "outer_radius_cm": outer_radius,
        "bore_radius_cm": bore_radius,
        "thickness_cm": _pop_length_alias(
            kw,
            where=where,
            names=("thickness", "thickness_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="z")
    bolt_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("bolt_radius", "bolt_radius_cm", "hole_radius", "hole_radius_cm"),
        diameter_names=("bolt_diameter", "bolt_diameter_cm", "hole_diameter", "hole_diameter_cm"),
    )
    if bolt_radius is not None:
        parameters["bolt_radius_cm"] = bolt_radius
    bolt_circle_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("bolt_circle_radius", "bolt_circle_radius_cm"),
        diameter_names=("bolt_circle_diameter", "bolt_circle_diameter_cm"),
    )
    if bolt_circle_radius is not None:
        parameters["bolt_circle_radius_cm"] = bolt_circle_radius
    for parameter_name, aliases in {
        "hole_depth_cm": ("hole_depth", "hole_depth_cm"),
        "rim_bevel_cm": ("rim_bevel", "rim_bevel_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    for name in ("segments", "bolt_count"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    start_angle = _pop_angle_alias(
        kw,
        where=where,
        names=("start_angle_degrees", "start_angle", "start_radians"),
    )
    if start_angle is not None:
        parameters["start_angle_degrees"] = start_angle
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_flange(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.flange",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_hinge_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "length_cm": _pop_length_alias(
            kw,
            where=where,
            names=("length", "length_cm"),
            required=True,
        ),
        "leaf_width_cm": _pop_length_alias(
            kw,
            where=where,
            names=("leaf_width", "leaf_width_cm"),
            required=True,
        ),
        "barrel_radius_cm": _pop_radius_or_diameter(
            kw,
            where=where,
            radius_names=("barrel_radius", "barrel_radius_cm", "knuckle_radius", "knuckle_radius_cm"),
            diameter_names=("barrel_diameter", "barrel_diameter_cm", "knuckle_diameter", "knuckle_diameter_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    for axis_name in ("hinge_axis", "leaf_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(
                kw.pop(axis_name),
                where=f"{where}.{axis_name}",
            )
    for parameter_name, radius_names, diameter_names in (
        ("pin_radius_cm", ("pin_radius", "pin_radius_cm"), ("pin_diameter", "pin_diameter_cm")),
        ("screw_radius_cm", ("screw_radius", "screw_radius_cm"), ("screw_diameter", "screw_diameter_cm")),
        (
            "countersink_radius_cm",
            ("countersink_radius", "countersink_radius_cm", "sink_radius", "sink_radius_cm", "head_radius", "head_radius_cm"),
            ("countersink_diameter", "countersink_diameter_cm", "sink_diameter", "sink_diameter_cm", "head_diameter", "head_diameter_cm"),
        ),
        (
            "counterbore_radius_cm",
            ("counterbore_radius", "counterbore_radius_cm"),
            ("counterbore_diameter", "counterbore_diameter_cm"),
        ),
    ):
        _pop_optional_radius_or_diameter_parameter(
            kw,
            parameters,
            where=where,
            target=parameter_name,
            radius_names=radius_names,
            diameter_names=diameter_names,
        )
    for parameter_name, aliases in {
        "leaf_thickness_cm": ("leaf_thickness", "leaf_thickness_cm"),
        "screw_depth_cm": ("screw_depth", "screw_depth_cm"),
        "screw_span_cm": ("screw_span", "screw_span_cm"),
        "countersink_depth_cm": ("countersink_depth", "countersink_depth_cm", "sink_depth", "sink_depth_cm", "head_depth", "head_depth_cm"),
        "counterbore_depth_cm": ("counterbore_depth", "counterbore_depth_cm"),
        "screw_rim_bevel_cm": ("screw_rim_bevel", "screw_rim_bevel_cm"),
        "leaf_bevel_width_cm": ("leaf_bevel_width", "leaf_bevel_width_cm"),
        "knuckle_gap_cm": ("knuckle_gap", "knuckle_gap_cm"),
        "knuckle_bevel_width_cm": (
            "knuckle_bevel_width",
            "knuckle_bevel_width_cm",
        ),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    for name in (
        "knuckle_count",
        "segments",
        "screw_count_per_leaf",
        "leaf_bevel_segments",
        "knuckle_bevel_segments",
        "screw_rim_bevel_segments",
    ):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    style = _pop_string_alias(
        kw,
        where=where,
        names=("style", "hole_style", "screw_style"),
        allowed={"straight", "countersink", "counterbore"},
    )
    if style is not None:
        parameters["style"] = style
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_hinge(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.hinge",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_handle_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "span_cm": _pop_length_alias(
            kw,
            where=where,
            names=("span", "span_cm"),
            required=True,
        ),
        "standoff_cm": _pop_length_alias(
            kw,
            where=where,
            names=("standoff", "standoff_cm"),
            required=True,
        ),
        "grip_radius_cm": _pop_radius_or_diameter(
            kw,
            where=where,
            radius_names=("grip_radius", "grip_radius_cm", "bar_radius", "bar_radius_cm"),
            diameter_names=("grip_diameter", "grip_diameter_cm", "bar_diameter", "bar_diameter_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    for axis_name in ("span_axis", "normal_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(
                kw.pop(axis_name),
                where=f"{where}.{axis_name}",
            )
    for parameter_name, radius_names, diameter_names in (
        ("pad_radius_cm", ("pad_radius", "pad_radius_cm"), ("pad_diameter", "pad_diameter_cm")),
        ("screw_radius_cm", ("screw_radius", "screw_radius_cm"), ("screw_diameter", "screw_diameter_cm")),
        (
            "countersink_radius_cm",
            ("countersink_radius", "countersink_radius_cm", "sink_radius", "sink_radius_cm", "head_radius", "head_radius_cm"),
            ("countersink_diameter", "countersink_diameter_cm", "sink_diameter", "sink_diameter_cm", "head_diameter", "head_diameter_cm"),
        ),
        (
            "counterbore_radius_cm",
            ("counterbore_radius", "counterbore_radius_cm"),
            ("counterbore_diameter", "counterbore_diameter_cm"),
        ),
    ):
        _pop_optional_radius_or_diameter_parameter(
            kw,
            parameters,
            where=where,
            target=parameter_name,
            radius_names=radius_names,
            diameter_names=diameter_names,
        )
    for parameter_name, aliases in {
        "pad_thickness_cm": ("pad_thickness", "pad_thickness_cm"),
        "screw_spacing_cm": ("screw_spacing", "screw_spacing_cm"),
        "screw_depth_cm": ("screw_depth", "screw_depth_cm"),
        "countersink_depth_cm": ("countersink_depth", "countersink_depth_cm", "sink_depth", "sink_depth_cm", "head_depth", "head_depth_cm"),
        "counterbore_depth_cm": ("counterbore_depth", "counterbore_depth_cm"),
        "pad_bevel_width_cm": ("pad_bevel_width", "pad_bevel_width_cm"),
        "screw_rim_bevel_cm": ("screw_rim_bevel", "screw_rim_bevel_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    for name in (
        "screw_count_per_pad",
        "cross_section_segments",
        "pad_segments",
        "pad_bevel_segments",
        "screw_rim_bevel_segments",
    ):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    style = _pop_string_alias(
        kw,
        where=where,
        names=("style", "hole_style", "screw_style"),
        allowed={"straight", "countersink", "counterbore"},
    )
    if style is not None:
        parameters["style"] = style
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_handle(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.handle",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_capsule_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("radius", "radius_cm"),
        diameter_names=("diameter", "diameter_cm"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "radius_cm": radius,
        "length_cm": _pop_length_alias(
            kw,
            where=where,
            names=("length", "length_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
    for name in ("sections", "rings"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_capsule(...) argument(s): {unknown}")
    return _single_v2_kernel_primitive(
        "solid.capsule",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_subdivision_box_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    if "extents" in kw:
        width, height, depth = _vec3(kw.pop("extents"), where=f"{where}.extents")
    else:
        width = _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True) or 0.0
        height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True) or 0.0
        depth = _pop_length_alias(kw, where=where, names=("depth", "depth_cm"), required=True) or 0.0
    blend_mode = _pop_blend_mode(kw, where=where)
    parameters: dict[str, Any] = {
        "width_cm": width,
        "height_cm": height,
        "depth_cm": depth,
        "corner_radii_cm": _pop_length_tuple_alias(
            kw,
            where=where,
            names=("corner_radii", "corner_radii_cm"),
            count=8,
            required=True,
        ),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    corner_segments = _pop_int_alias(kw, where=where, names=("corner_segments",))
    if corner_segments is not None:
        parameters["corner_segments"] = corner_segments
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_subdivision_box(...) argument(s): {unknown}")
    primitive = _single_v2_primitive(
        "solid.subdivision_box",
        target=part,
        parameters=parameters,
        where=where,
    )
    primitive.blend_mode = blend_mode
    if "solid_subdivision_box" not in primitive.tags:
        primitive.tags = [*primitive.tags, "solid_subdivision_box"]
    return primitive


def _eval_solid_structural_beam_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "length_cm": _pop_length_alias(
            kw,
            where=where,
            names=("length", "length_cm"),
            required=True,
        ),
        "width_cm": _pop_length_alias(
            kw,
            where=where,
            names=("width", "width_cm"),
            required=True,
        ),
        "height_cm": _pop_length_alias(
            kw,
            where=where,
            names=("height", "height_cm"),
            required=True,
        ),
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x"),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    profile_shape = _pop_string_alias(
        kw,
        where=where,
        names=("profile_shape", "profile"),
        default="i_beam",
        allowed={"i_beam", "c_channel", "channel", "u_channel", "angle", "l_angle", "t_beam"},
    )
    if profile_shape is not None:
        parameters["profile_shape"] = profile_shape
    for parameter_name, aliases in {
        "web_thickness_cm": ("web_thickness", "web_thickness_cm"),
        "flange_thickness_cm": ("flange_thickness", "flange_thickness_cm"),
        "bevel_width_cm": ("bevel_width", "bevel_width_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    bevel_segments = _pop_int_alias(kw, where=where, names=("bevel_segments",))
    if bevel_segments is not None:
        parameters["bevel_segments"] = bevel_segments
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_structural_beam(...) argument(s): {unknown}"
        )
    return _single_v2_kernel_primitive(
        "solid.structural_beam",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_ladder_frame_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "length_cm": _pop_length_alias(
            kw,
            where=where,
            names=("length", "length_cm"),
            required=True,
        ),
        "width_cm": _pop_length_alias(
            kw,
            where=where,
            names=("width", "width_cm"),
            required=True,
        ),
        "rail_radius_cm": _pop_radius_or_diameter(
            kw,
            where=where,
            radius_names=("rail_radius", "rail_radius_cm"),
            diameter_names=("rail_diameter", "rail_diameter_cm"),
            required=True,
        ),
        "rung_count": _pop_int_alias(
            kw,
            where=where,
            names=("rung_count",),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    for axis_name in ("length_axis", "width_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(
                kw.pop(axis_name),
                where=f"{where}.{axis_name}",
            )
    _pop_optional_radius_or_diameter_parameter(
        kw,
        parameters,
        where=where,
        target="rung_radius_cm",
        radius_names=("rung_radius", "rung_radius_cm"),
        diameter_names=("rung_diameter", "rung_diameter_cm"),
    )
    for parameter_name, aliases in {
        "rung_spacing_cm": ("rung_spacing", "rung_spacing_cm"),
        "rail_span_cm": ("rail_span", "rail_span_cm"),
        "rung_length_cm": ("rung_length", "rung_length_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    segments = _pop_int_alias(kw, where=where, names=("segments",))
    if segments is not None:
        parameters["segments"] = segments
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_ladder_frame(...) argument(s): {unknown}"
        )
    return _v2_kernel_primitives_from_op(
        "solid.ladder_frame",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_truss_frame_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "length_cm": _pop_length_alias(
            kw,
            where=where,
            names=("length", "length_cm"),
            required=True,
        ),
        "height_cm": _pop_length_alias(
            kw,
            where=where,
            names=("height", "height_cm"),
            required=True,
        ),
        "member_radius_cm": _pop_radius_or_diameter(
            kw,
            where=where,
            radius_names=("member_radius", "member_radius_cm"),
            diameter_names=("member_diameter", "member_diameter_cm"),
            required=True,
        ),
        "bay_count": _pop_int_alias(
            kw,
            where=where,
            names=("bay_count", "bays"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    for axis_name in ("length_axis", "height_axis", "depth_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(
                kw.pop(axis_name),
                where=f"{where}.{axis_name}",
            )
    depth = _pop_length_alias(kw, where=where, names=("depth", "depth_cm"))
    if depth is not None:
        parameters["depth_cm"] = depth
    bracing_pattern = _pop_string_alias(
        kw,
        where=where,
        names=("bracing_pattern", "pattern"),
        default="warren",
        allowed={"warren", "pratt", "x"},
    )
    if bracing_pattern is not None:
        parameters["bracing_pattern"] = bracing_pattern
    include_depth_ties = _pop_bool_alias(
        kw,
        where=where,
        names=("include_depth_ties",),
    )
    if include_depth_ties is not None:
        parameters["include_depth_ties"] = include_depth_ties
    segments = _pop_int_alias(kw, where=where, names=("segments",))
    if segments is not None:
        parameters["segments"] = segments
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_truss_frame(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.truss_frame",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_perforated_panel_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "width_cm": _pop_length_alias(
            kw,
            where=where,
            names=("width", "width_cm"),
            required=True,
        ),
        "height_cm": _pop_length_alias(
            kw,
            where=where,
            names=("height", "height_cm"),
            required=True,
        ),
        "thickness_cm": _pop_length_alias(
            kw,
            where=where,
            names=("thickness", "thickness_cm"),
            required=True,
        ),
        "hole_radius_cm": _pop_radius_or_diameter(
            kw,
            where=where,
            radius_names=("hole_radius", "hole_radius_cm"),
            diameter_names=("hole_diameter", "hole_diameter_cm"),
            required=True,
        ),
        "rows": _pop_int_alias(kw, where=where, names=("rows",), required=True),
        "columns": _pop_int_alias(
            kw,
            where=where,
            names=("columns", "cols"),
            required=True,
        ),
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z"),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    for axis_name in ("column_axis", "row_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(
                kw.pop(axis_name),
                where=f"{where}.{axis_name}",
            )
    for parameter_name, aliases in {
        "edge_margin_cm": ("edge_margin", "edge_margin_cm"),
        "row_span_cm": ("row_span", "row_span_cm"),
        "column_span_cm": ("column_span", "column_span_cm"),
        "stagger_offset_cm": ("stagger_offset", "stagger_offset_cm"),
        "slot_length_cm": ("slot_length", "slot_length_cm"),
        "hole_depth_cm": ("hole_depth", "hole_depth_cm"),
        "corner_radius_cm": ("corner_radius", "corner_radius_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    for name in ("corner_segments",):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    for parameter_name, allowed in {
        "pattern": {"grid", "staggered", "slot_grid", "slot_staggered"},
        "hole_shape": {"round", "circular", "circle", "slot", "rounded_slot", "capsule"},
    }.items():
        value = _pop_string_alias(
            kw,
            where=where,
            names=(parameter_name,),
            default=None,
            allowed=allowed,
        )
        if value is not None:
            parameters[parameter_name] = value
    stagger = _pop_bool_alias(kw, where=where, names=("stagger",))
    if stagger is not None:
        parameters["stagger"] = stagger
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown solid_perforated_panel(...) argument(s): {unknown}"
        )
    return _v2_kernel_primitives_from_op(
        "solid.perforated_panel",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_ribbed_panel_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "width_cm": _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True),
        "height_cm": _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True),
        "thickness_cm": _pop_length_alias(kw, where=where, names=("thickness", "thickness_cm"), required=True),
        "rib_count": _pop_int_alias(kw, where=where, names=("rib_count",), required=True),
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z"),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    for axis_name in ("width_axis", "height_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(kw.pop(axis_name), where=f"{where}.{axis_name}")
    for parameter_name, aliases in {
        "rib_width_cm": ("rib_width", "rib_width_cm"),
        "rib_height_cm": ("rib_height", "rib_height_cm"),
        "rib_top_width_cm": ("rib_top_width", "rib_top_width_cm"),
        "edge_margin_cm": ("edge_margin", "edge_margin_cm"),
        "corner_radius_cm": ("corner_radius", "corner_radius_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    for name in ("cross_rib_count", "corner_segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    for parameter_name, allowed in {
        "rib_orientation": {"vertical", "horizontal", "both"},
        "rib_profile": {"rectangular", "triangular", "trapezoid"},
    }.items():
        value = _pop_string_alias(kw, where=where, names=(parameter_name,), default=None, allowed=allowed)
        if value is not None:
            parameters[parameter_name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_ribbed_panel(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.ribbed_panel",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_louver_panel_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "width_cm": _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True),
        "height_cm": _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True),
        "thickness_cm": _pop_length_alias(kw, where=where, names=("thickness", "thickness_cm"), required=True),
        "slat_count": _pop_int_alias(kw, where=where, names=("slat_count",), required=True),
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z"),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    for axis_name in ("width_axis", "height_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(kw.pop(axis_name), where=f"{where}.{axis_name}")
    for parameter_name, aliases in {
        "border_width_cm": ("border_width", "border_width_cm"),
        "slat_thickness_cm": ("slat_thickness", "slat_thickness_cm"),
        "slat_depth_cm": ("slat_depth", "slat_depth_cm"),
        "slat_spacing_cm": ("slat_spacing", "slat_spacing_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    slat_angle = _pop_angle_alias(kw, where=where, names=("slat_angle_degrees", "slat_angle", "slat_angle_radians"))
    if slat_angle is not None:
        parameters["slat_angle_degrees"] = slat_angle
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_louver_panel(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.louver_panel",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_cga_facade_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "width_cm": _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True),
        "height_cm": _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True),
        "depth_cm": _pop_length_alias(kw, where=where, names=("depth", "depth_cm"), required=True),
        "floors": _pop_int_alias(kw, where=where, names=("floors",), required=True),
        "bays": _pop_int_alias(kw, where=where, names=("bays",), required=True),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    pattern = _pop_string_alias(
        kw,
        where=where,
        names=("pattern",),
        default="office",
        allowed={"office", "residential", "industrial"},
    )
    if pattern is not None:
        parameters["pattern"] = pattern
    for axis_name in ("vertical_axis", "frontage_axis", "depth_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(kw.pop(axis_name), where=f"{where}.{axis_name}")
    for parameter_name in ("window_width_ratio", "window_height_ratio"):
        value = _pop_number_alias(kw, where=where, names=(parameter_name,))
        if value is not None:
            parameters[parameter_name] = value
    for parameter_name, aliases in {
        "frame_width_cm": ("frame_width", "frame_width_cm"),
        "relief_depth_cm": ("relief_depth", "relief_depth_cm"),
        "pane_depth_cm": ("pane_depth", "pane_depth_cm"),
        "floor_band_height_cm": ("floor_band_height", "floor_band_height_cm"),
        "pilaster_width_cm": ("pilaster_width", "pilaster_width_cm"),
        "sill_height_cm": ("sill_height", "sill_height_cm"),
        "cornice_height_cm": ("cornice_height", "cornice_height_cm"),
        "plinth_height_cm": ("plinth_height", "plinth_height_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_cga_facade(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.cga_facade",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_terrain_patch_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "width_cm": _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True),
        "depth_cm": _pop_length_alias(kw, where=where, names=("depth", "depth_cm"), required=True),
        "height_cm": _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True),
        "resolution": _pop_int_alias(kw, where=where, names=("resolution",), required=True),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    biome = _pop_string_alias(
        kw,
        where=where,
        names=("biome",),
        default="rolling_hills",
        allowed={"rolling_hills", "dunes", "alpine", "canyon", "rocky"},
    )
    if biome is not None:
        parameters["biome"] = biome
    seed = _pop_int_alias(kw, where=where, names=("seed",))
    if seed is not None:
        parameters["seed"] = seed
    for name in ("octaves", "terrace_count"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    for name in ("roughness", "border_taper", "terrace_strength", "erosion_strength"):
        value = _pop_number_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_terrain_patch(...) argument(s): {unknown}")
    return _single_v2_kernel_primitive(
        "solid.terrain_patch",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_branching_tree_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "height_cm": _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True),
        "trunk_radius_cm": _pop_length_alias(
            kw,
            where=where,
            names=("trunk_radius", "trunk_radius_cm", "base_radius", "base_radius_cm"),
            required=True,
        ),
        "branch_count": _pop_int_alias(kw, where=where, names=("branch_count", "branches"), required=True),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    for axis_name in ("vertical_axis", "radial_axis_a", "radial_axis_b"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(kw.pop(axis_name), where=f"{where}.{axis_name}")
    seed = _pop_int_alias(kw, where=where, names=("seed",))
    if seed is not None:
        parameters["seed"] = seed
    for name in ("branch_tiers", "root_count", "segments"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    for parameter_name, aliases in {
        "canopy_radius_cm": ("canopy_radius", "canopy_radius_cm"),
        "branch_sweep_cm": ("branch_sweep", "branch_sweep_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    branch_angle = _pop_angle_alias(
        kw,
        where=where,
        names=("branch_angle_degrees", "branch_angle", "branch_angle_radians"),
    )
    if branch_angle is not None:
        parameters["branch_angle_degrees"] = branch_angle
    include_canopy = _pop_bool_alias(kw, where=where, names=("include_canopy",))
    if include_canopy is not None:
        parameters["include_canopy"] = include_canopy
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_branching_tree(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.branching_tree",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_sdf_metaball_cluster_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "blob_count": _pop_int_alias(kw, where=where, names=("blob_count", "blobs"), required=True),
        "radius_cm": _pop_length_alias(kw, where=where, names=("radius", "radius_cm"), required=True),
        "field_radius_cm": _pop_length_alias(
            kw,
            where=where,
            names=("field_radius", "field_radius_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    smooth_radius = _pop_length_alias(kw, where=where, names=("smooth_radius", "smooth_radius_cm"))
    if smooth_radius is not None:
        parameters["smooth_radius_cm"] = smooth_radius
    seed = _pop_int_alias(kw, where=where, names=("seed",))
    if seed is not None:
        parameters["seed"] = seed
    resolution = _pop_int_alias(kw, where=where, names=("resolution",))
    if resolution is not None:
        parameters["resolution"] = resolution
    extraction_backend = _pop_string_alias(
        kw,
        where=where,
        names=("extraction_backend", "backend"),
        default="dual_contouring",
        allowed={"marching_cubes", "dual_contouring"},
    )
    if extraction_backend is not None:
        parameters["extraction_backend"] = extraction_backend
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_sdf_metaball_cluster(...) argument(s): {unknown}")
    return _single_v2_kernel_primitive(
        "solid.sdf_metaball_cluster",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_solid_wfc_modular_assembly_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> list[ShapePrimitive]:
    kw = _kwargs(args, where=where)
    parameters: dict[str, Any] = {
        "width_cells": _pop_int_alias(kw, where=where, names=("width_cells", "width"), required=True),
        "depth_cells": _pop_int_alias(kw, where=where, names=("depth_cells", "depth"), required=True),
        "cell_size_cm": _pop_length_alias(
            kw,
            where=where,
            names=("cell_size", "cell_size_cm"),
            required=True,
        ),
        "blend_mode": _pop_blend_mode(kw, where=where),
    }
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center
    palette = _pop_string_alias(
        kw,
        where=where,
        names=("palette",),
        default="industrial",
        allowed={"industrial", "dungeon", "city_block"},
    )
    if palette is not None:
        parameters["palette"] = palette
    for axis_name in ("vertical_axis", "width_axis", "depth_axis"):
        if axis_name in kw:
            parameters[axis_name] = _axis_arg(kw.pop(axis_name), where=f"{where}.{axis_name}")
    seed = _pop_int_alias(kw, where=where, names=("seed",))
    if seed is not None:
        parameters["seed"] = seed
    segments = _pop_int_alias(kw, where=where, names=("segments",))
    if segments is not None:
        parameters["segments"] = segments
    for parameter_name, aliases in {
        "floor_thickness_cm": ("floor_thickness", "floor_thickness_cm"),
        "wall_height_cm": ("wall_height", "wall_height_cm"),
        "wall_thickness_cm": ("wall_thickness", "wall_thickness_cm"),
        "pillar_radius_cm": ("pillar_radius", "pillar_radius_cm"),
        "floor_margin_cm": ("floor_margin", "floor_margin_cm"),
        "foundation_thickness_cm": ("foundation_thickness", "foundation_thickness_cm"),
    }.items():
        value = _pop_length_alias(kw, where=where, names=aliases)
        if value is not None:
            parameters[parameter_name] = value
    pillar_shape = _pop_string_alias(
        kw,
        where=where,
        names=("pillar_shape",),
        default="box",
        allowed={"box", "cylinder"},
    )
    if pillar_shape is not None:
        parameters["pillar_shape"] = pillar_shape
    for name in ("include_boundary_walls", "include_foundation_slab"):
        value = _pop_bool_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    for name in (
        "open_weight",
        "pillar_weight",
        "wall_weight",
        "wall_x_weight",
        "wall_z_weight",
        "corner_weight",
        "corner_ne_weight",
        "corner_nw_weight",
        "corner_se_weight",
        "corner_sw_weight",
    ):
        value = _pop_number_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown solid_wfc_modular_assembly(...) argument(s): {unknown}")
    return _v2_kernel_primitives_from_op(
        "solid.wfc_modular_assembly",
        target=part,
        parameters=parameters,
        where=where,
    )


def _eval_vegetation_trunk_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    """Build a tapered, gently bent tree trunk as a ``lofted_solid``.

    Parameters:
        height: total trunk height (length unit literal).
        base_radius: radius at the base (length unit literal).
        taper: fraction of base radius the top tapers to. 0.0 = no
            taper (cylinder); 0.4 = top radius is 40% of base. Required
            in (0, 1).
        segments: number of stacked sections along the trunk (>= 2). Each
            section becomes one ring of the lofted body. Higher =
            smoother taper/bend. Defaults to 6.
        bend: optional total bend angle (radians) applied evenly across
            segments. 0 = perfectly straight; ~0.05 = a gentle natural
            lean. Defaults to a small natural lean.

    Returns:
        A single ``lofted_solid`` ``ShapePrimitive`` whose
        cross-sections are circular polygons at decreasing radii along a
        slightly bent vertical sweep path.
    """
    kw = _kwargs(args, where=where)
    if "height" not in kw:
        raise MeshProgramError(f"{where}: vegetation_trunk(...) requires 'height'")
    if "base_radius" not in kw:
        raise MeshProgramError(
            f"{where}: vegetation_trunk(...) requires 'base_radius'"
        )
    height = _unit_to_cm(kw.pop("height"), where=f"{where}.height")
    base_radius = _unit_to_cm(kw.pop("base_radius"), where=f"{where}.base_radius")
    taper_value = kw.pop("taper", 0.3)
    if isinstance(taper_value, (int, float)) and not isinstance(taper_value, bool):
        taper = float(taper_value)
    else:
        raise MeshProgramError(
            f"{where}.taper: expected a number in (0, 1), got {taper_value!r}"
        )
    segments_value = kw.pop("segments", 6)
    segments = _int(segments_value, where=f"{where}.segments")
    bend_value = kw.pop("bend", 0.05)
    if isinstance(bend_value, (int, float)) and not isinstance(bend_value, bool):
        bend_total = float(bend_value)
    else:
        raise MeshProgramError(
            f"{where}.bend: expected a number (radians), got {bend_value!r}"
        )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown vegetation_trunk(...) argument(s): {unknown}"
        )
    if height <= 0.0:
        raise MeshProgramError(f"{where}: height must be > 0, got {height}cm")
    if base_radius <= 0.0:
        raise MeshProgramError(
            f"{where}: base_radius must be > 0, got {base_radius}cm"
        )
    if not 0.0 <= taper < 1.0:
        raise MeshProgramError(
            f"{where}: taper must be in [0, 1), got {taper}"
        )
    if segments < 2:
        raise MeshProgramError(f"{where}: segments must be >= 2, got {segments}")

    sides = 8
    base_polygon = [
        (math.cos(2.0 * math.pi * i / sides), math.sin(2.0 * math.pi * i / sides))
        for i in range(sides)
    ]
    cross_sections: list[list[tuple[float, float]]] = []
    section_centers: list[tuple[float, float, float]] = []
    top_radius = base_radius * (1.0 - taper)
    for i in range(segments + 1):
        t = i / segments
        radius = base_radius + (top_radius - base_radius) * t
        cross_sections.append([(p[0] * radius, p[1] * radius) for p in base_polygon])
        # Bend sweep: distribute bend_total evenly along Y; offset X by
        # cumulative (sin(theta_k)*step). This produces a gentle arc
        # rather than a kink at the top.
        cumulative_x = 0.0
        cumulative_y = 0.0
        step_len = height / segments
        for k in range(i):
            theta_k = bend_total * (k / max(1, segments - 1))
            cumulative_x += math.sin(theta_k) * step_len
            cumulative_y += math.cos(theta_k) * step_len
        section_centers.append((cumulative_x, cumulative_y, 0.0))

    return ShapePrimitive(
        primitive_type="lofted_solid",
        part=part,
        center=(0.0, 0.0, 0.0),
        axis="y",
        cross_sections=cross_sections,
        section_centers=section_centers,
        tags=["vegetation", "vegetation_trunk"],
        blend_mode="union",
    )


def _eval_terrain_heightfield_call(
    args: list[dict[str, Any]], *, part: str, where: str
) -> ShapePrimitive:
    """Build a procedural terrain ``heightfield`` primitive.

    Parameters:
        extents: ``[X, Y]`` length-unit literal — XY footprint of the
            terrain (centered on origin). Both must be > 0.
        resolution: integer grid resolution (used for both nx and ny).
            Must be >= 8 so the triangulated grid has enough cells to
            read as terrain rather than a flat quad.
        scale_z: length-unit literal — peak vertical relief in world
            units. The fbm noise is normalised to [0, 1] before being
            multiplied by ``scale_z``, so the resulting Z extent is at
            most ~``scale_z``.
        seed: integer seed for deterministic noise. Same seed always
            produces the same heights (delegates to numpy's
            ``default_rng`` per the existing ``lathe.std.terrain.noise``
            implementation).
        octaves: optional fbm octave count (defaults to 5). Higher =
            more fine detail. Capped sensibly to avoid runaway noise
            generation.

    Returns:
        A single ``ShapePrimitive(primitive_type="heightfield")`` whose
        ``height_data`` is the normalised noise field, ``vertical_scale``
        is ``scale_z`` (cm), and ``bounds_xy`` is centered on the
        origin. The exact-solid mesher
        (``lathe.exact_solids._heightfield_mesh``) consumes this record
        directly to emit a triangulated grid mesh.
    """
    from ..std.terrain.heightfield import Heightfield
    from ..std.terrain.noise import fbm

    kw = _kwargs(args, where=where)
    if "extents" not in kw:
        raise MeshProgramError(f"{where}: terrain_heightfield(...) requires 'extents'")
    if "resolution" not in kw:
        raise MeshProgramError(
            f"{where}: terrain_heightfield(...) requires 'resolution'"
        )
    if "scale_z" not in kw:
        raise MeshProgramError(
            f"{where}: terrain_heightfield(...) requires 'scale_z'"
        )
    if "seed" not in kw:
        raise MeshProgramError(f"{where}: terrain_heightfield(...) requires 'seed'")

    extents_xy = _vec2_length(kw.pop("extents"), where=f"{where}.extents")
    resolution = _int(kw.pop("resolution"), where=f"{where}.resolution")
    scale_z = _unit_to_cm(kw.pop("scale_z"), where=f"{where}.scale_z")
    seed = _int(kw.pop("seed"), where=f"{where}.seed")
    octaves_value = kw.pop("octaves", 5)
    octaves = _int(octaves_value, where=f"{where}.octaves")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown terrain_heightfield(...) argument(s): {unknown}"
        )

    width, depth = extents_xy
    if width <= 0.0 or depth <= 0.0:
        raise MeshProgramError(
            f"{where}: extents must be positive, got [{width}, {depth}] cm"
        )
    if resolution < 8:
        raise MeshProgramError(
            f"{where}: resolution must be >= 8, got {resolution}"
        )
    if scale_z <= 0.0:
        raise MeshProgramError(
            f"{where}: scale_z must be > 0, got {scale_z} cm"
        )
    if octaves < 1 or octaves > 10:
        raise MeshProgramError(
            f"{where}: octaves must be in [1, 10], got {octaves}"
        )

    half_x = width * 0.5
    half_y = depth * 0.5
    bounds_xy = (-half_x, -half_y, half_x, half_y)
    hf = Heightfield.zeros(
        (resolution, resolution),
        bounds_xy=bounds_xy,
        vertical_scale=scale_z,
    )
    fbm(
        hf,
        octaves=octaves,
        base_frequency=2.5,
        amplitude=1.0,
        seed=seed,
        add=False,
    )
    # Normalise noise to [0, 1] so vertical_scale is the actual peak
    # relief (not the noise amplitude). Border-tapering: multiply by a
    # raised cosine so terrain settles to baseline at the rim — gives
    # the GLB an obvious hilltop silhouette rather than a torn rectangle.
    h = hf.heights
    h_min = float(h.min())
    h_max = float(h.max())
    if h_max > h_min:
        h = (h - h_min) / (h_max - h_min)
    else:
        h = h * 0.0
    import numpy as np

    nx, ny = resolution, resolution
    fx = np.linspace(-1.0, 1.0, nx, dtype=np.float64)
    fy = np.linspace(-1.0, 1.0, ny, dtype=np.float64)
    rim_x = 0.5 * (1.0 + np.cos(np.pi * np.clip(fx, -1.0, 1.0)))
    rim_y = 0.5 * (1.0 + np.cos(np.pi * np.clip(fy, -1.0, 1.0)))
    rim = rim_y[:, None] * rim_x[None, :]
    h = h * rim
    hf.heights = h

    return ShapePrimitive(
        primitive_type="heightfield",
        part=part,
        center=(0.0, 0.0, 0.0),
        resolution=(int(nx), int(ny)),
        height_data=hf.heights.tolist(),
        bounds_xy=bounds_xy,
        vertical_scale=scale_z,
        tags=["terrain", "terrain_heightfield"],
        blend_mode="union",
    )


# ---------------------------------------------------------------------------
# SDF / F-Rep authoring ops (Phase 3 §7.6 — organic / creature primitives).
#
# These produce an ``SDFExpr`` from ``lathe.f_rep`` that lives in scope as a
# kind="sdf" ``_Value`` until ``sdf_extract`` runs marching cubes against it
# and emits a ``ShapePrimitive(primitive_type="sdf_mesh")``. The implicit
# representation is what makes capsule-blob blends, smooth-min unions, and
# other organic shapes possible without a domain-specific kernel.
# ---------------------------------------------------------------------------


def _eval_sdf_sphere_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an SDFExpr for a unit sphere of given radius (cm)."""
    from ..f_rep import Sphere

    kw = _kwargs(args, where=where)
    if "radius" not in kw:
        raise MeshProgramError(f"{where}: sdf_sphere(...) requires 'radius'")
    radius = _unit_to_cm(kw.pop("radius"), where=f"{where}.radius")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_sphere(...) argument(s): {unknown}"
        )
    if radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius}cm")
    return Sphere(radius=radius)


def _eval_sdf_capsule_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an SDFExpr for a capsule of given dimensions."""
    from ..f_rep import Capsule

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(kw, where=where, names=("radius", "radius_cm"), required=True)
    half_height = _pop_half_height_or_height(kw, where=where, op_name="sdf_capsule")
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_capsule(...) argument(s): {unknown}"
        )
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius}cm")
    if half_height <= 0.0:
        raise MeshProgramError(
            f"{where}: half_height must be > 0, got {half_height}cm"
        )
    return _orient_y_axis_sdf(
        Capsule(half_height=half_height, radius=radius),
        axis=axis,
        where=where,
    )


def _eval_sdf_capsule_between_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an arbitrary endpoint capsule SDF."""
    from ..f_rep import SegmentCapsule, TaperedSegmentCapsule

    kw = _kwargs(args, where=where)
    start_value = None
    end_value = None
    for name in ("start", "a", "from"):
        if name in kw:
            start_value = kw.pop(name)
            break
    for name in ("end", "b", "to"):
        if name in kw:
            end_value = kw.pop(name)
            break
    if start_value is None or end_value is None:
        raise MeshProgramError(
            f"{where}: sdf_capsule_between(...) requires start/end or a/b"
        )
    start = _vec3(start_value, where=f"{where}.start")
    end = _vec3(end_value, where=f"{where}.end")
    radius = _pop_length_alias(kw, where=where, names=("radius", "radius_cm"))
    radius_start = _pop_length_alias(
        kw,
        where=where,
        names=("radius_start", "start_radius", "radius_a", "radius_start_cm", "start_radius_cm"),
    )
    radius_end = _pop_length_alias(
        kw,
        where=where,
        names=("radius_end", "end_radius", "radius_b", "radius_end_cm", "end_radius_cm"),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_capsule_between(...) argument(s): {unknown}"
        )
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    dz = float(end[2]) - float(start[2])
    if dx * dx + dy * dy + dz * dz <= 1e-12:
        raise MeshProgramError(f"{where}: start and end must be distinct")
    has_taper = radius_start is not None or radius_end is not None
    if radius is not None and has_taper:
        raise MeshProgramError(
            f"{where}: supply either radius or radius_start/radius_end, not both"
        )
    if has_taper:
        if radius_start is None or radius_end is None:
            raise MeshProgramError(
                f"{where}: radius_start and radius_end must be supplied together"
            )
        if radius_start <= 0.0 or radius_end <= 0.0:
            raise MeshProgramError(
                f"{where}: tapered radii must be > 0, got {radius_start!r}, {radius_end!r}cm"
            )
        return TaperedSegmentCapsule(
            a=start,
            b=end,
            radius_start=float(radius_start),
            radius_end=float(radius_end),
        )
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    return SegmentCapsule(a=start, b=end, radius=float(radius))


def _eval_sdf_tube_path_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a tube SDF along a polyline path."""
    from ..f_rep import ConnectedIntent, SegmentCapsule, SmoothUnion, TaperedSegmentCapsule, Union

    kw = _kwargs(args, where=where)
    if "points" not in kw:
        raise MeshProgramError(f"{where}: sdf_tube_path(...) requires 'points'")
    points = _vec3_length_points(kw.pop("points"), where=f"{where}.points", min_points=2)
    radius = _pop_length_alias(kw, where=where, names=("radius", "radius_cm"))
    radii = None
    if "radii" in kw:
        radii = _length_list(kw.pop("radii"), where=f"{where}.radii", min_count=2)
    elif "point_radii" in kw:
        radii = _length_list(
            kw.pop("point_radii"),
            where=f"{where}.point_radii",
            min_count=2,
        )
    blend = _pop_length_alias(
        kw,
        where=where,
        names=("blend", "blend_cm", "blend_radius", "blend_radius_cm", "k"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_tube_path(...) argument(s): {unknown}")
    if radius is not None and radii is not None:
        raise MeshProgramError(f"{where}: supply either radius or radii, not both")
    if radii is None:
        if radius is None or radius <= 0.0:
            raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    else:
        if len(radii) != len(points):
            raise MeshProgramError(
                f"{where}: radii length must match points length "
                f"({len(points)}), got {len(radii)}"
            )
        if any(value <= 0.0 for value in radii):
            raise MeshProgramError(f"{where}: all radii must be > 0, got {radii!r}")
    if blend is None or blend < 0.0:
        raise MeshProgramError(f"{where}: blend_radius must be >= 0, got {blend!r}cm")
    segments: list[Any] = []
    for index, (start, end) in enumerate(itertools.pairwise(points)):
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        dz = float(end[2]) - float(start[2])
        if dx * dx + dy * dy + dz * dz <= 1e-12:
            raise MeshProgramError(
                f"{where}: points[{index}] and points[{index + 1}] must be distinct"
            )
        if radii is None:
            segments.append(SegmentCapsule(a=start, b=end, radius=float(radius or 0.0)))
        else:
            segments.append(
                TaperedSegmentCapsule(
                    a=start,
                    b=end,
                    radius_start=float(radii[index]),
                    radius_end=float(radii[index + 1]),
                )
            )
    accumulated = segments[0]
    for segment in segments[1:]:
        if float(blend or 0.0) > 0.0:
            accumulated = SmoothUnion(a=accumulated, b=segment, k=float(blend))
        else:
            accumulated = Union(a=accumulated, b=segment)
    return ConnectedIntent(expr=accumulated, label="tube_path")


def _eval_sdf_arc_tube_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a circular arc tube / pipe elbow SDF."""
    from ..f_rep import ConnectedIntent, SegmentCapsule, SmoothUnion, Union

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "arc_radius", "arc_radius_cm", "bend_radius", "bend_radius_cm"),
        required=True,
    )
    tube_radius = _pop_length_alias(
        kw,
        where=where,
        names=("tube_radius", "tube_radius_cm", "profile_radius", "profile_radius_cm", "wire_radius", "wire_radius_cm"),
        required=True,
    )
    sweep_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("sweep_degrees", "angle_degrees", "angle", "sweep_radians"),
        default=90.0,
    )
    start_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("start_degrees", "start_angle", "start_radians"),
        default=0.0,
    )
    segments = _pop_int_alias(
        kw,
        where=where,
        names=("segments", "path_segments", "samples"),
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z")
    center = _pop_optional_center(kw, where=where) or (0.0, 0.0, 0.0)
    blend = _pop_length_alias(
        kw,
        where=where,
        names=("blend", "blend_cm", "joint_blend", "joint_blend_cm"),
        default=0.0,
    ) or 0.0
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_arc_tube(...) argument(s): {unknown}")
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    if tube_radius is None or tube_radius <= 0.0:
        raise MeshProgramError(f"{where}: tube_radius must be > 0, got {tube_radius!r}cm")
    if tube_radius >= radius:
        raise MeshProgramError(f"{where}: tube_radius must be smaller than radius")
    if sweep_degrees is None or sweep_degrees <= 0.0 or sweep_degrees > 360.0:
        raise MeshProgramError(
            f"{where}: sweep_degrees must satisfy 0 < value <= 360, got {sweep_degrees!r}"
        )
    if segments is None:
        segments = max(6, math.ceil(abs(float(sweep_degrees)) / 8.0))
    if segments < 3:
        raise MeshProgramError(f"{where}: segments must be >= 3, got {segments}")
    segments = min(int(segments), 512)
    axis_to_plane = {
        "x": (1, 2),
        "y": (0, 2),
        "z": (0, 1),
    }
    plane_axes = axis_to_plane[axis]
    c = [float(center[0]), float(center[1]), float(center[2])]
    points: list[tuple[float, float, float]] = []
    for index in range(segments + 1):
        t = index / float(segments)
        angle = math.radians(float(start_degrees or 0.0) + float(sweep_degrees) * t)
        point = list(c)
        point[plane_axes[0]] += float(radius) * math.cos(angle)
        point[plane_axes[1]] += float(radius) * math.sin(angle)
        points.append((point[0], point[1], point[2]))
    accumulated: Any = None
    for start, end in itertools.pairwise(points):
        segment = SegmentCapsule(a=start, b=end, radius=float(tube_radius))
        if accumulated is None:
            accumulated = segment
        elif blend > 0.0:
            accumulated = SmoothUnion(a=accumulated, b=segment, k=float(blend))
        else:
            accumulated = Union(a=accumulated, b=segment)
    if accumulated is None:
        raise MeshProgramError(f"{where}: arc tube produced no segments")
    return ConnectedIntent(expr=accumulated, label="arc_tube")


def _sdf_segment_box_from_dimensions(
    *,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    width: float,
    depth: float,
    rounding: float,
    up_hint: tuple[float, float, float],
    where: str,
) -> Any:
    from ..f_rep import Offset, SegmentBox

    if width <= 0.0 or depth <= 0.0:
        raise MeshProgramError(f"{where}: width and depth must be > 0")
    if rounding < 0.0:
        raise MeshProgramError(f"{where}: rounding must be >= 0")
    half_width = 0.5 * float(width)
    half_depth = 0.5 * float(depth)
    if rounding > 0.0:
        half_width -= float(rounding)
        half_depth -= float(rounding)
        if half_width <= 0.0 or half_depth <= 0.0:
            raise MeshProgramError(
                f"{where}: rounding {rounding}cm is too large for width/depth"
            )
    expr: Any = SegmentBox(
        a=start,
        b=end,
        half_width=half_width,
        half_depth=half_depth,
        up_hint=up_hint,
    )
    if rounding > 0.0:
        expr = Offset(expr=expr, amount=float(rounding))
    return expr


def _eval_sdf_beam_between_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a rectangular beam between arbitrary 3D endpoints."""
    kw = _kwargs(args, where=where)
    start_value = None
    end_value = None
    for name in ("start", "a", "from"):
        if name in kw:
            start_value = kw.pop(name)
            break
    for name in ("end", "b", "to"):
        if name in kw:
            end_value = kw.pop(name)
            break
    if start_value is None or end_value is None:
        raise MeshProgramError(f"{where}: sdf_beam_between(...) requires start/end or a/b")
    start = _vec3(start_value, where=f"{where}.start")
    end = _vec3(end_value, where=f"{where}.end")
    if "cross_section" in kw:
        width, depth = _vec2_length(kw.pop("cross_section"), where=f"{where}.cross_section")
    elif "profile" in kw:
        width, depth = _vec2_length(kw.pop("profile"), where=f"{where}.profile")
    else:
        width = _pop_length_alias(
            kw,
            where=where,
            names=("width", "width_cm", "beam_width", "beam_width_cm"),
            required=True,
        ) or 0.0
        depth = _pop_length_alias(
            kw,
            where=where,
            names=("depth", "depth_cm", "height", "height_cm", "beam_depth", "beam_depth_cm"),
            required=True,
        ) or 0.0
    rounding = _pop_length_alias(
        kw,
        where=where,
        names=("rounding", "rounding_cm", "edge_radius", "edge_radius_cm", "radius", "radius_cm"),
        default=0.0,
    ) or 0.0
    up_hint = _number_vec3(
        kw.pop("up_hint", kw.pop("up", [0.0, 1.0, 0.0])),
        where=f"{where}.up_hint",
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_beam_between(...) argument(s): {unknown}")
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    dz = float(end[2]) - float(start[2])
    if dx * dx + dy * dy + dz * dz <= 1e-12:
        raise MeshProgramError(f"{where}: start and end must be distinct")
    return _sdf_segment_box_from_dimensions(
        start=start,
        end=end,
        width=float(width),
        depth=float(depth),
        rounding=float(rounding),
        up_hint=up_hint,
        where=where,
    )


def _eval_sdf_beam_path_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a rectangular-beam polyline path."""
    from ..f_rep import ChamferUnion, ConnectedIntent, SmoothUnion, Union

    kw = _kwargs(args, where=where)
    if "points" not in kw:
        raise MeshProgramError(f"{where}: sdf_beam_path(...) requires 'points'")
    points = _vec3_length_points(kw.pop("points"), where=f"{where}.points", min_points=2)
    if "cross_section" in kw:
        width, depth = _vec2_length(kw.pop("cross_section"), where=f"{where}.cross_section")
    elif "profile" in kw:
        width, depth = _vec2_length(kw.pop("profile"), where=f"{where}.profile")
    else:
        width = _pop_length_alias(
            kw,
            where=where,
            names=("width", "width_cm", "beam_width", "beam_width_cm"),
            required=True,
        ) or 0.0
        depth = _pop_length_alias(
            kw,
            where=where,
            names=("depth", "depth_cm", "height", "height_cm", "beam_depth", "beam_depth_cm"),
            required=True,
        ) or 0.0
    rounding = _pop_length_alias(
        kw,
        where=where,
        names=("rounding", "rounding_cm", "edge_radius", "edge_radius_cm"),
        default=0.0,
    ) or 0.0
    joint_radius = _pop_length_alias(
        kw,
        where=where,
        names=("joint_radius", "joint_radius_cm", "joint_chamfer", "joint_chamfer_cm"),
        default=0.0,
    ) or 0.0
    joint_mode = _pop_string_alias(
        kw,
        where=where,
        names=("joint_mode", "blend_mode"),
        default="union",
        allowed={"union", "smooth", "chamfer"},
    ) or "union"
    up_hint = _number_vec3(
        kw.pop("up_hint", kw.pop("up", [0.0, 1.0, 0.0])),
        where=f"{where}.up_hint",
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_beam_path(...) argument(s): {unknown}")
    segments: list[Any] = []
    for index, (start, end) in enumerate(itertools.pairwise(points)):
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        dz = float(end[2]) - float(start[2])
        if dx * dx + dy * dy + dz * dz <= 1e-12:
            raise MeshProgramError(
                f"{where}: points[{index}] and points[{index + 1}] must be distinct"
            )
        segments.append(
            _sdf_segment_box_from_dimensions(
                start=start,
                end=end,
                width=float(width),
                depth=float(depth),
                rounding=float(rounding),
                up_hint=up_hint,
                where=f"{where}.segment[{index}]",
            )
        )
    accumulated = segments[0]
    for segment in segments[1:]:
        if joint_mode == "smooth" and joint_radius > 0.0:
            accumulated = SmoothUnion(a=accumulated, b=segment, k=float(joint_radius))
        elif joint_mode == "chamfer" and joint_radius > 0.0:
            accumulated = ChamferUnion(a=accumulated, b=segment, radius=float(joint_radius))
        else:
            accumulated = Union(a=accumulated, b=segment)
    return ConnectedIntent(expr=accumulated, label="beam_path")


def _eval_sdf_swept_profile_between_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an arbitrary 2D profile swept between two 3D endpoints."""
    from ..f_rep import SegmentExtrudedProfile

    kw = _kwargs(args, where=where)
    start_value = None
    end_value = None
    for name in ("start", "a", "from"):
        if name in kw:
            start_value = kw.pop(name)
            break
    for name in ("end", "b", "to"):
        if name in kw:
            end_value = kw.pop(name)
            break
    if start_value is None or end_value is None:
        raise MeshProgramError(
            f"{where}: sdf_swept_profile_between(...) requires start/end or a/b"
        )
    profile_name = next(
        (name for name in ("profile", "profile_points", "cross_section", "profile_polygon") if name in kw),
        "",
    )
    if not profile_name:
        raise MeshProgramError(
            f"{where}: sdf_swept_profile_between(...) requires profile/profile_points"
        )
    start = _vec3(start_value, where=f"{where}.start")
    end = _vec3(end_value, where=f"{where}.end")
    profile_points = _vec2_length_points(
        kw.pop(profile_name),
        where=f"{where}.{profile_name}",
        min_points=3,
    )
    up_hint = _number_vec3(
        kw.pop("up_hint", kw.pop("up", [0.0, 1.0, 0.0])),
        where=f"{where}.up_hint",
    )
    start_scale = _pop_number_alias(
        kw,
        where=where,
        names=("start_scale", "scale_start"),
        default=1.0,
    ) or 1.0
    end_scale = _pop_number_alias(
        kw,
        where=where,
        names=("end_scale", "scale_end"),
        default=1.0,
    ) or 1.0
    twist_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("twist_degrees", "twist", "twist_radians"),
        default=0.0,
    ) or 0.0
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_swept_profile_between(...) argument(s): {unknown}"
        )
    if start_scale <= 0.0 or end_scale <= 0.0:
        raise MeshProgramError(f"{where}: start_scale and end_scale must be > 0")
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    dz = float(end[2]) - float(start[2])
    if dx * dx + dy * dy + dz * dz <= 1e-12:
        raise MeshProgramError(f"{where}: start and end must be distinct")
    area = 0.0
    for index, point in enumerate(profile_points):
        nxt = profile_points[(index + 1) % len(profile_points)]
        area += float(point[0]) * float(nxt[1]) - float(nxt[0]) * float(point[1])
    if abs(area) <= 1e-9:
        raise MeshProgramError(f"{where}: profile must enclose non-zero area")
    return SegmentExtrudedProfile(
        a=start,
        b=end,
        profile_points=tuple((float(point[0]), float(point[1])) for point in profile_points),
        up_hint=up_hint,
        start_scale=float(start_scale),
        end_scale=float(end_scale),
        twist_degrees=float(twist_degrees),
    )


def _eval_sdf_swept_profile_path_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an arbitrary 2D profile swept along a polyline path."""
    from ..f_rep import ChamferUnion, ConnectedIntent, SegmentExtrudedProfile, SmoothUnion, Union

    kw = _kwargs(args, where=where)
    if "points" not in kw:
        raise MeshProgramError(f"{where}: sdf_swept_profile_path(...) requires 'points'")
    profile_name = next(
        (name for name in ("profile", "profile_points", "cross_section", "profile_polygon") if name in kw),
        "",
    )
    if not profile_name:
        raise MeshProgramError(
            f"{where}: sdf_swept_profile_path(...) requires profile/profile_points"
        )
    points = _vec3_length_points(kw.pop("points"), where=f"{where}.points", min_points=2)
    profile_points = _vec2_length_points(
        kw.pop(profile_name),
        where=f"{where}.{profile_name}",
        min_points=3,
    )
    joint_radius = _pop_length_alias(
        kw,
        where=where,
        names=("joint_radius", "joint_radius_cm", "joint_chamfer", "joint_chamfer_cm"),
        default=0.0,
    ) or 0.0
    joint_mode = _pop_string_alias(
        kw,
        where=where,
        names=("joint_mode", "blend_mode"),
        default="union",
        allowed={"union", "smooth", "chamfer"},
    ) or "union"
    up_hint = _number_vec3(
        kw.pop("up_hint", kw.pop("up", [0.0, 1.0, 0.0])),
        where=f"{where}.up_hint",
    )
    start_scale = _pop_number_alias(
        kw,
        where=where,
        names=("start_scale", "scale_start"),
        default=1.0,
    ) or 1.0
    end_scale = _pop_number_alias(
        kw,
        where=where,
        names=("end_scale", "scale_end"),
        default=1.0,
    ) or 1.0
    twist_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("twist_degrees", "twist", "twist_radians"),
        default=0.0,
    ) or 0.0
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_swept_profile_path(...) argument(s): {unknown}"
        )
    if start_scale <= 0.0 or end_scale <= 0.0:
        raise MeshProgramError(f"{where}: start_scale and end_scale must be > 0")
    area = 0.0
    for index, point in enumerate(profile_points):
        nxt = profile_points[(index + 1) % len(profile_points)]
        area += float(point[0]) * float(nxt[1]) - float(nxt[0]) * float(point[1])
    if abs(area) <= 1e-9:
        raise MeshProgramError(f"{where}: profile must enclose non-zero area")
    profile = tuple((float(point[0]), float(point[1])) for point in profile_points)
    segments: list[Any] = []
    for index, (start, end) in enumerate(itertools.pairwise(points)):
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        dz = float(end[2]) - float(start[2])
        if dx * dx + dy * dy + dz * dz <= 1e-12:
            raise MeshProgramError(
                f"{where}: points[{index}] and points[{index + 1}] must be distinct"
            )
        segments.append(
            SegmentExtrudedProfile(
                a=start,
                b=end,
                profile_points=profile,
                up_hint=up_hint,
                start_scale=float(start_scale),
                end_scale=float(end_scale),
                twist_degrees=float(twist_degrees),
            )
        )
    accumulated = segments[0]
    for segment in segments[1:]:
        if joint_mode == "smooth" and joint_radius > 0.0:
            accumulated = SmoothUnion(a=accumulated, b=segment, k=float(joint_radius))
        elif joint_mode == "chamfer" and joint_radius > 0.0:
            accumulated = ChamferUnion(a=accumulated, b=segment, radius=float(joint_radius))
        else:
            accumulated = Union(a=accumulated, b=segment)
    return ConnectedIntent(expr=accumulated, label="swept_profile_path")


def _eval_sdf_lofted_profile_between_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a loft between two closed 2D profiles along a 3D segment."""
    from ..f_rep import SegmentLoftedProfile

    kw = _kwargs(args, where=where)
    start_value = None
    end_value = None
    for name in ("start", "a", "from"):
        if name in kw:
            start_value = kw.pop(name)
            break
    for name in ("end", "b", "to"):
        if name in kw:
            end_value = kw.pop(name)
            break
    if start_value is None or end_value is None:
        raise MeshProgramError(
            f"{where}: sdf_lofted_profile_between(...) requires start/end or a/b"
        )
    start_profile_name = next(
        (name for name in ("profile_start", "start_profile", "profile_a", "cross_section_start") if name in kw),
        "",
    )
    end_profile_name = next(
        (name for name in ("profile_end", "end_profile", "profile_b", "cross_section_end") if name in kw),
        "",
    )
    if not start_profile_name or not end_profile_name:
        raise MeshProgramError(
            f"{where}: sdf_lofted_profile_between(...) requires start/end profiles"
        )
    start = _vec3(start_value, where=f"{where}.start")
    end = _vec3(end_value, where=f"{where}.end")
    profile_start = _vec2_length_points(
        kw.pop(start_profile_name),
        where=f"{where}.{start_profile_name}",
        min_points=3,
    )
    profile_end = _vec2_length_points(
        kw.pop(end_profile_name),
        where=f"{where}.{end_profile_name}",
        min_points=3,
    )
    up_hint = _number_vec3(
        kw.pop("up_hint", kw.pop("up", [0.0, 1.0, 0.0])),
        where=f"{where}.up_hint",
    )
    twist_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("twist_degrees", "twist", "twist_radians"),
        default=0.0,
    ) or 0.0
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_lofted_profile_between(...) argument(s): {unknown}"
        )
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    dz = float(end[2]) - float(start[2])
    if dx * dx + dy * dy + dz * dz <= 1e-12:
        raise MeshProgramError(f"{where}: start and end must be distinct")
    if len(profile_start) != len(profile_end):
        raise MeshProgramError(
            f"{where}: profile_start/profile_end must have matching point counts"
        )
    for label, profile_points in (("profile_start", profile_start), ("profile_end", profile_end)):
        area = 0.0
        for index, point in enumerate(profile_points):
            nxt = profile_points[(index + 1) % len(profile_points)]
            area += float(point[0]) * float(nxt[1]) - float(nxt[0]) * float(point[1])
        if abs(area) <= 1e-9:
            raise MeshProgramError(f"{where}: {label} must enclose non-zero area")
    return SegmentLoftedProfile(
        a=start,
        b=end,
        profile_start=tuple((float(point[0]), float(point[1])) for point in profile_start),
        profile_end=tuple((float(point[0]), float(point[1])) for point in profile_end),
        up_hint=up_hint,
        twist_degrees=float(twist_degrees),
    )


def _eval_sdf_box_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an SDFExpr for an axis-aligned box from full extents (cm)."""
    from ..f_rep import Box

    kw = _kwargs(args, where=where)
    if "extents" not in kw:
        raise MeshProgramError(f"{where}: sdf_box(...) requires 'extents'")
    extents = _vec3(kw.pop("extents"), where=f"{where}.extents")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_box(...) argument(s): {unknown}"
        )
    if any(e <= 0.0 for e in extents):
        raise MeshProgramError(
            f"{where}: all extent components must be > 0, got {list(extents)}"
        )
    half_extents = (extents[0] * 0.5, extents[1] * 0.5, extents[2] * 0.5)
    return Box(half_extents=half_extents)


def _eval_sdf_rounded_box_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a rounded-box SDF from full extents and corner radius."""
    from ..f_rep import Box, Offset

    kw = _kwargs(args, where=where)
    if "extents" not in kw:
        raise MeshProgramError(f"{where}: sdf_rounded_box(...) requires 'extents'")
    extents = _vec3(kw.pop("extents"), where=f"{where}.extents")
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "corner_radius", "corner_radius_cm"),
        required=True,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_rounded_box(...) argument(s): {unknown}")
    if any(value <= 0.0 for value in extents):
        raise MeshProgramError(
            f"{where}: all extent components must be > 0, got {list(extents)}"
        )
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    half_extents = tuple(float(value) * 0.5 for value in extents)
    core_half_extents = tuple(float(value) - float(radius) for value in half_extents)
    if any(value <= 0.0 for value in core_half_extents):
        raise MeshProgramError(
            f"{where}: radius {radius}cm is too large for extents {list(extents)}"
        )
    return Offset(expr=Box(half_extents=core_half_extents), amount=float(radius))


def _eval_sdf_plane_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a half-space plane SDF for clipping/cutting bounded shapes."""
    from ..f_rep import Plane

    kw = _kwargs(args, where=where)
    normal_value = kw.pop("normal", None)
    axis_value = kw.pop("axis", None)
    if normal_value is not None and axis_value is not None:
        raise MeshProgramError(f"{where}: supply either normal or axis, not both")
    normal_sign = _pop_number_alias(
        kw,
        where=where,
        names=("normal_sign", "sign"),
        default=1.0,
    )
    distance_offset = _pop_length_alias(
        kw,
        where=where,
        names=("distance", "distance_cm", "distance_offset", "offset", "offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_plane(...) argument(s): {unknown}")
    if normal_value is not None:
        normal = _number_vec3(normal_value, where=f"{where}.normal")
    else:
        axis = _axis_arg(axis_value, where=f"{where}.axis", default="y")
        normal = _axis_vector(axis)
    sign = 1.0 if float(normal_sign or 1.0) >= 0.0 else -1.0
    nx, ny, nz = (float(component) * sign for component in normal)
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-12:
        raise MeshProgramError(f"{where}: normal must be non-zero")
    normalized = (nx / length, ny / length, nz / length)
    return Plane(
        normal=normalized,
        distance_offset=float(distance_offset or 0.0),
    )


def _orient_y_axis_sdf(expr: Any, *, axis: str, where: str) -> Any:
    """Orient an F-Rep primitive whose native axis is +Y."""
    from ..f_rep import Rotate

    resolved_axis = _axis_arg(axis, where=f"{where}.axis", default="y")
    if resolved_axis == "y":
        return expr
    if resolved_axis == "z":
        return Rotate(expr=expr, axis=(1.0, 0.0, 0.0), angle=math.radians(90.0))
    return Rotate(expr=expr, axis=(0.0, 0.0, 1.0), angle=math.radians(-90.0))


def _eval_sdf_cylinder_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a capped-cylinder SDF."""
    from ..f_rep import Cylinder

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(kw, where=where, names=("radius", "radius_cm"), required=True)
    height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True)
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_cylinder(...) argument(s): {unknown}")
    if radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius}cm")
    if height <= 0.0:
        raise MeshProgramError(f"{where}: height must be > 0, got {height}cm")
    return _orient_y_axis_sdf(Cylinder(radius=radius, height=height), axis=axis, where=where)


def _eval_sdf_frustum_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a capped conical-frustum SDF."""
    from ..f_rep import Frustum

    kw = _kwargs(args, where=where)
    radius_bottom = _pop_length_alias(
        kw,
        where=where,
        names=("radius_bottom", "bottom_radius", "base_radius", "radius_base"),
        required=True,
    )
    radius_top = _pop_length_alias(
        kw,
        where=where,
        names=("radius_top", "top_radius", "tip_radius", "radius_tip"),
        required=True,
    )
    height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True)
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_frustum(...) argument(s): {unknown}")
    if radius_bottom is None or radius_bottom <= 0.0:
        raise MeshProgramError(
            f"{where}: radius_bottom must be > 0, got {radius_bottom!r}cm"
        )
    if radius_top is None or radius_top <= 0.0:
        raise MeshProgramError(f"{where}: radius_top must be > 0, got {radius_top!r}cm")
    if height is None or height <= 0.0:
        raise MeshProgramError(f"{where}: height must be > 0, got {height!r}cm")
    return _orient_y_axis_sdf(
        Frustum(
            radius_bottom=float(radius_bottom),
            radius_top=float(radius_top),
            height=float(height),
        ),
        axis=axis,
        where=where,
    )


def _eval_sdf_rounded_cylinder_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a capped cylinder with rounded rim edges."""
    from ..f_rep import Cylinder, Offset

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(kw, where=where, names=("radius", "radius_cm"), required=True)
    height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True)
    rounding = _pop_length_alias(
        kw,
        where=where,
        names=("rounding", "rounding_cm", "edge_radius", "edge_radius_cm", "fillet_radius", "fillet_radius_cm"),
        required=True,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_rounded_cylinder(...) argument(s): {unknown}")
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    if height is None or height <= 0.0:
        raise MeshProgramError(f"{where}: height must be > 0, got {height!r}cm")
    if rounding is None or rounding <= 0.0:
        raise MeshProgramError(f"{where}: rounding must be > 0, got {rounding!r}cm")
    core_radius = float(radius) - float(rounding)
    core_height = float(height) - 2.0 * float(rounding)
    if core_radius <= 0.0 or core_height <= 0.0:
        raise MeshProgramError(
            f"{where}: rounding {rounding}cm is too large for radius={radius}cm, height={height}cm"
        )
    expr = Offset(
        expr=Cylinder(radius=core_radius, height=core_height),
        amount=float(rounding),
    )
    return _orient_y_axis_sdf(expr, axis=axis, where=where)


def _eval_sdf_rounded_slot_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an extruded pill/slot SDF for vents, handles, and cuts."""
    from ..f_rep import RoundedSlot

    kw = _kwargs(args, where=where)
    length = _pop_length_alias(
        kw,
        where=where,
        names=("length", "length_cm"),
        required=True,
    )
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "slot_radius", "slot_radius_cm"),
        required=True,
    )
    depth = _pop_length_alias(
        kw,
        where=where,
        names=("depth", "depth_cm", "thickness", "thickness_cm"),
        required=True,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x")
    normal_axis = _axis_arg(
        kw.pop("normal_axis", None),
        where=f"{where}.normal_axis",
        default="z",
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_rounded_slot(...) argument(s): {unknown}")
    if length is None or length <= 0.0:
        raise MeshProgramError(f"{where}: length must be > 0, got {length!r}cm")
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    if depth is None or depth <= 0.0:
        raise MeshProgramError(f"{where}: depth must be > 0, got {depth!r}cm")
    if length <= 2.0 * radius:
        raise MeshProgramError(
            f"{where}: length must be larger than diameter, got length={length}cm radius={radius}cm"
        )
    if axis == normal_axis:
        raise MeshProgramError(f"{where}: axis and normal_axis must differ")
    return RoundedSlot(
        length=float(length),
        radius=float(radius),
        depth=float(depth),
        axis=axis,
        normal_axis=normal_axis,
    )


def _eval_sdf_extruded_profile_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an arbitrary closed-profile extrusion SDF."""
    from ..f_rep import ExtrudedPolygon, Translate

    kw = _kwargs(args, where=where)
    profile_name = next(
        (name for name in ("profile", "profile_points", "profile_polygon", "polygon") if name in kw),
        "",
    )
    if not profile_name:
        raise MeshProgramError(
            f"{where}: sdf_extruded_profile(...) requires profile/profile_points"
        )
    profile_points = _vec2_length_points(
        kw.pop(profile_name),
        where=f"{where}.{profile_name}",
        min_points=3,
    )
    depth = _pop_length_alias(
        kw,
        where=where,
        names=("depth", "depth_cm", "height", "height_cm", "thickness", "thickness_cm"),
        required=True,
    )
    normal_axis = _axis_arg(kw.pop("normal_axis", None), where=f"{where}.normal_axis", default="z")
    axis_u = _axis_arg(kw.pop("axis_u", None), where=f"{where}.axis_u", default="x")
    axis_v = _axis_arg(kw.pop("axis_v", None), where=f"{where}.axis_v", default="y")
    center = _pop_optional_center(kw, where=where)
    normal_offset = _pop_length_alias(
        kw,
        where=where,
        names=("normal_offset", "normal_offset_cm", "surface_offset", "surface_offset_cm", "center_offset", "center_offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_extruded_profile(...) argument(s): {unknown}")
    if depth is None or depth <= 0.0:
        raise MeshProgramError(f"{where}: depth must be > 0, got {depth!r}cm")
    if len({normal_axis, axis_u, axis_v}) != 3:
        raise MeshProgramError(f"{where}: normal_axis, axis_u, and axis_v must be distinct")
    area = 0.0
    for index, point in enumerate(profile_points):
        nxt = profile_points[(index + 1) % len(profile_points)]
        area += float(point[0]) * float(nxt[1]) - float(nxt[0]) * float(point[1])
    if abs(area) <= 1e-9:
        raise MeshProgramError(f"{where}: profile must enclose non-zero area")
    expr: Any = ExtrudedPolygon(
        profile_points=tuple((float(point[0]), float(point[1])) for point in profile_points),
        depth=float(depth),
        axis_u=axis_u,
        axis_v=axis_v,
        normal_axis=normal_axis,
    )
    offset = [0.0, 0.0, 0.0]
    if center is not None:
        offset = [float(center[0]), float(center[1]), float(center[2])]
    if normal_offset:
        axis_to_index = {"x": 0, "y": 1, "z": 2}
        offset[axis_to_index[normal_axis]] += float(normal_offset)
    if any(abs(value) > 0.0 for value in offset):
        expr = Translate(expr=expr, offset=(offset[0], offset[1], offset[2]))
    return expr


def _eval_sdf_revolved_profile_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a lathed/revolved closed-profile SDF."""
    from ..f_rep import RevolvedProfile, Translate

    kw = _kwargs(args, where=where)
    profile_name = next(
        (name for name in ("profile", "profile_points", "profile_polygon", "section") if name in kw),
        "",
    )
    if not profile_name:
        raise MeshProgramError(
            f"{where}: sdf_revolved_profile(...) requires profile/profile_points"
        )
    profile_points = _vec2_length_points(
        kw.pop(profile_name),
        where=f"{where}.{profile_name}",
        min_points=3,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    revolve_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("revolve_degrees", "angle_degrees", "angle", "radians"),
    )
    start_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("revolve_start_degrees", "start_degrees", "start_angle", "start_radians"),
        default=0.0,
    )
    center = _pop_optional_center(kw, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_revolved_profile(...) argument(s): {unknown}")
    if revolve_degrees is not None and (
        revolve_degrees <= 0.0 or revolve_degrees > 360.0
    ):
        raise MeshProgramError(
            f"{where}: revolve_degrees must satisfy 0 < value <= 360, got {revolve_degrees}"
        )
    if any(float(point[0]) < 0.0 for point in profile_points):
        raise MeshProgramError(f"{where}: profile radius coordinates must be >= 0")
    area = 0.0
    for index, point in enumerate(profile_points):
        nxt = profile_points[(index + 1) % len(profile_points)]
        area += float(point[0]) * float(nxt[1]) - float(nxt[0]) * float(point[1])
    if abs(area) <= 1e-9:
        raise MeshProgramError(f"{where}: profile must enclose non-zero area")
    expr: Any = RevolvedProfile(
        profile_points=tuple((float(point[0]), float(point[1])) for point in profile_points),
        axis=axis,
        revolve_degrees=float(revolve_degrees) if revolve_degrees is not None else None,
        start_degrees=float(start_degrees or 0.0),
    )
    if center is not None:
        expr = Translate(expr=expr, offset=(float(center[0]), float(center[1]), float(center[2])))
    return expr


def _eval_sdf_gear_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an involute spur gear as an SDF extrusion."""
    from ..asset_quality.shape_ir_v2 import _gear_profile_polygon
    from ..f_rep import ChamferSubtract, Cylinder, ExtrudedPolygon, Subtract, Translate

    kw = _kwargs(args, where=where)
    teeth = _pop_int_alias(kw, where=where, names=("teeth",), required=True)
    pitch_radius = _pop_length_alias(
        kw,
        where=where,
        names=("pitch_radius", "pitch_radius_cm"),
        required=True,
    )
    thickness = _pop_length_alias(
        kw,
        where=where,
        names=("thickness", "thickness_cm", "depth", "depth_cm"),
        required=True,
    )
    axis_value = kw.pop("axis", None)
    normal_axis_value = kw.pop("normal_axis", None)
    if axis_value is not None and normal_axis_value is not None:
        raise MeshProgramError(f"{where}: supply either axis or normal_axis, not both")
    normal_axis = _axis_arg(
        axis_value if axis_value is not None else normal_axis_value,
        where=f"{where}.axis",
        default="z",
    )
    pressure_angle_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("pressure_angle_degrees", "pressure_angle", "pressure_angle_radians"),
        default=20.0,
    )
    addendum = _pop_length_alias(kw, where=where, names=("addendum", "addendum_cm"))
    dedendum = _pop_length_alias(kw, where=where, names=("dedendum", "dedendum_cm"))
    root_radius = _pop_length_alias(kw, where=where, names=("root_radius", "root_radius_cm"))
    outer_radius = _pop_length_alias(kw, where=where, names=("outer_radius", "outer_radius_cm"))
    backlash = _pop_length_alias(
        kw,
        where=where,
        names=("backlash", "backlash_cm"),
        default=0.0,
    )
    bore_radius = _pop_length_alias(kw, where=where, names=("bore_radius", "bore_radius_cm"))
    bore_chamfer = _pop_length_alias(
        kw,
        where=where,
        names=("bore_chamfer", "bore_chamfer_cm", "hole_chamfer", "hole_chamfer_cm"),
        default=0.0,
    )
    cut_padding = _pop_length_alias(
        kw,
        where=where,
        names=("cut_padding", "cut_padding_cm"),
        default=0.2,
    )
    tooth_samples = _pop_int_alias(kw, where=where, names=("tooth_samples",))
    center = _pop_optional_center(kw, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_gear(...) argument(s): {unknown}")
    if teeth is None or teeth < 3:
        raise MeshProgramError(f"{where}: teeth must be >= 3, got {teeth!r}")
    if teeth > 512:
        raise MeshProgramError(f"{where}: teeth must be <= 512, got {teeth}")
    if pitch_radius is None or pitch_radius <= 0.0:
        raise MeshProgramError(f"{where}: pitch_radius must be > 0, got {pitch_radius!r}cm")
    if thickness is None or thickness <= 0.0:
        raise MeshProgramError(f"{where}: thickness must be > 0, got {thickness!r}cm")
    if pressure_angle_degrees is None or pressure_angle_degrees < 5.0 or pressure_angle_degrees > 45.0:
        raise MeshProgramError(
            f"{where}: pressure_angle_degrees must satisfy 5 <= value <= 45, got {pressure_angle_degrees!r}"
        )
    module = 2.0 * float(pitch_radius) / float(teeth)
    addendum = float(addendum if addendum is not None else module)
    dedendum = float(dedendum if dedendum is not None else module * 1.25)
    if addendum <= 0.0 or dedendum <= 0.0:
        raise MeshProgramError(f"{where}: addendum and dedendum must be > 0")
    root_radius = float(root_radius if root_radius is not None else max(float(pitch_radius) - dedendum, float(pitch_radius) * 0.25))
    outer_radius = float(outer_radius if outer_radius is not None else float(pitch_radius) + addendum)
    if root_radius <= 0.0 or root_radius >= float(pitch_radius):
        raise MeshProgramError(f"{where}: root_radius must satisfy 0 < root_radius < pitch_radius")
    if outer_radius <= float(pitch_radius) or outer_radius <= root_radius:
        raise MeshProgramError(f"{where}: outer_radius must be greater than pitch_radius and root_radius")
    tooth_samples = int(tooth_samples or 4)
    if tooth_samples < 1:
        raise MeshProgramError(f"{where}: tooth_samples must be >= 1, got {tooth_samples}")
    tooth_samples = min(tooth_samples, 16)
    if backlash is None or backlash < 0.0:
        raise MeshProgramError(f"{where}: backlash must be >= 0, got {backlash!r}cm")
    if bore_radius is not None:
        if bore_radius < 0.0:
            raise MeshProgramError(f"{where}: bore_radius must be >= 0, got {bore_radius!r}cm")
        if bore_radius >= root_radius:
            raise MeshProgramError(f"{where}: bore_radius must be < root_radius")
    if bore_chamfer is None or bore_chamfer < 0.0:
        raise MeshProgramError(f"{where}: bore_chamfer must be >= 0, got {bore_chamfer!r}cm")
    pressure_angle = math.radians(float(pressure_angle_degrees))
    base_radius = max(root_radius, float(pitch_radius) * math.cos(pressure_angle))
    try:
        profile_polygon = _gear_profile_polygon(
            teeth=int(teeth),
            pitch_radius=float(pitch_radius),
            root_radius=root_radius,
            base_radius=base_radius,
            outer_radius=outer_radius,
            pressure_angle=pressure_angle,
            backlash=float(backlash or 0.0),
            tooth_samples=tooth_samples,
        )
    except ValueError as exc:
        raise MeshProgramError(f"{where}: {exc}") from exc
    plane_axes_by_normal = {
        "x": ("y", "z"),
        "y": ("x", "z"),
        "z": ("x", "y"),
    }
    axis_u, axis_v = plane_axes_by_normal[normal_axis]
    expr: Any = ExtrudedPolygon(
        profile_points=profile_polygon,
        depth=float(thickness),
        axis_u=axis_u,
        axis_v=axis_v,
        normal_axis=normal_axis,
    )
    if bore_radius and bore_radius > 0.0:
        bore = _orient_y_axis_sdf(
            Cylinder(
                radius=float(bore_radius),
                height=float(thickness) + 2.0 * float(cut_padding or 0.0),
            ),
            axis=normal_axis,
            where=where,
        )
        if bore_chamfer and bore_chamfer > 0.0:
            expr = ChamferSubtract(a=expr, b=bore, radius=float(bore_chamfer))
        else:
            expr = Subtract(a=expr, b=bore)
    if center is not None:
        expr = Translate(expr=expr, offset=(float(center[0]), float(center[1]), float(center[2])))
    return expr


def _eval_sdf_threaded_cylinder_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an externally threaded cylinder using a helical SDF ridge."""
    from ..f_rep import Cylinder, SegmentCapsule, SmoothUnion, Union

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "core_radius", "core_radius_cm"),
        required=True,
    )
    height = _pop_length_alias(
        kw,
        where=where,
        names=("height", "height_cm", "length", "length_cm"),
        required=True,
    )
    thread_pitch = _pop_length_alias(
        kw,
        where=where,
        names=("thread_pitch", "thread_pitch_cm", "pitch", "pitch_cm"),
        required=True,
    )
    thread_depth = _pop_length_alias(
        kw,
        where=where,
        names=("thread_depth", "thread_depth_cm", "depth", "depth_cm"),
        required=True,
    )
    thread_radius = _pop_length_alias(
        kw,
        where=where,
        names=("thread_radius", "thread_radius_cm", "ridge_radius", "ridge_radius_cm"),
    )
    turns = _pop_number_alias(kw, where=where, names=("turns",))
    start_clearance = _pop_length_alias(
        kw,
        where=where,
        names=("start_clearance", "start_clearance_cm", "thread_start_clearance", "thread_start_clearance_cm"),
        default=0.0,
    )
    end_clearance = _pop_length_alias(
        kw,
        where=where,
        names=("end_clearance", "end_clearance_cm", "thread_end_clearance", "thread_end_clearance_cm"),
        default=0.0,
    )
    segments_per_turn = _pop_int_alias(
        kw,
        where=where,
        names=("segments_per_turn", "samples_per_turn", "path_segments_per_turn"),
    )
    blend = _pop_length_alias(
        kw,
        where=where,
        names=("blend", "blend_cm", "ridge_blend", "ridge_blend_cm"),
        default=0.0,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    handedness = _pop_string_alias(
        kw,
        where=where,
        names=("handedness", "thread_handedness"),
        default="right",
        allowed={"right", "left"},
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_threaded_cylinder(...) argument(s): {unknown}")
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    if height is None or height <= 0.0:
        raise MeshProgramError(f"{where}: height must be > 0, got {height!r}cm")
    if thread_pitch is None or thread_pitch <= 0.0:
        raise MeshProgramError(f"{where}: thread_pitch must be > 0, got {thread_pitch!r}cm")
    if thread_depth is None or thread_depth <= 0.0:
        raise MeshProgramError(f"{where}: thread_depth must be > 0, got {thread_depth!r}cm")
    if thread_depth >= radius:
        raise MeshProgramError(f"{where}: thread_depth must be < radius")
    if start_clearance is None or end_clearance is None or start_clearance < 0.0 or end_clearance < 0.0:
        raise MeshProgramError(f"{where}: thread clearances must be >= 0")
    threaded_height = float(height) - float(start_clearance) - float(end_clearance)
    if threaded_height <= float(thread_pitch) * 0.25:
        raise MeshProgramError(f"{where}: clearances leave too little threaded height")
    turns_value = float(turns) if turns is not None else threaded_height / float(thread_pitch)
    if turns_value <= 0.0:
        raise MeshProgramError(f"{where}: turns must be > 0, got {turns_value}")
    ridge_radius = float(thread_radius if thread_radius is not None else float(thread_depth) * 0.5)
    if ridge_radius <= 0.0:
        raise MeshProgramError(f"{where}: thread_radius must be > 0, got {ridge_radius}cm")
    samples_per_turn = int(segments_per_turn or 16)
    if samples_per_turn < 4:
        raise MeshProgramError(f"{where}: segments_per_turn must be >= 4, got {samples_per_turn}")
    samples_per_turn = min(samples_per_turn, 96)
    sample_count = max(4, math.ceil(turns_value * samples_per_turn) + 1)
    sample_count = min(sample_count, 4096)
    handedness_sign = -1.0 if handedness == "left" else 1.0
    y0 = -0.5 * float(height) + float(start_clearance)
    path: list[tuple[float, float, float]] = []
    ridge_center_radius = float(radius) + ridge_radius * 0.55
    for index in range(sample_count):
        t = index / float(sample_count - 1)
        angle = handedness_sign * math.tau * turns_value * t
        y = y0 + threaded_height * t
        path.append(
            (
                ridge_center_radius * math.cos(angle),
                y,
                ridge_center_radius * math.sin(angle),
            )
        )
    ridge: Any = None
    for start, end in itertools.pairwise(path):
        segment = SegmentCapsule(a=start, b=end, radius=ridge_radius)
        if ridge is None:
            ridge = segment
        elif blend and blend > 0.0:
            ridge = SmoothUnion(a=ridge, b=segment, k=float(blend))
        else:
            ridge = Union(a=ridge, b=segment)
    if ridge is None:
        raise MeshProgramError(f"{where}: threaded path produced no segments")
    expr: Any = Union(a=Cylinder(radius=float(radius), height=float(height)), b=ridge)
    return _orient_y_axis_sdf(expr, axis=axis, where=where)


def _eval_sdf_flange_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a circular flange with optional central bore and bolt-circle holes."""
    from ..f_rep import ChamferSubtract, Cylinder, Frustum, Offset, Subtract, Translate, Union

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "outer_radius", "outer_radius_cm"),
        required=True,
    )
    thickness = _pop_length_alias(
        kw,
        where=where,
        names=("thickness", "thickness_cm", "height", "height_cm"),
        required=True,
    )
    rounding = _pop_length_alias(
        kw,
        where=where,
        names=("rounding", "rounding_cm", "edge_radius", "edge_radius_cm", "rim_rounding", "rim_rounding_cm"),
        default=0.0,
    ) or 0.0
    bore_radius = _pop_length_alias(
        kw,
        where=where,
        names=("bore_radius", "bore_radius_cm", "hole_radius", "hole_radius_cm"),
    )
    bolt_count = _pop_int_alias(kw, where=where, names=("bolt_count", "holes", "hole_count"))
    bolt_circle_radius = _pop_length_alias(
        kw,
        where=where,
        names=("bolt_circle_radius", "bolt_circle_radius_cm", "pcd_radius", "pcd_radius_cm"),
    )
    bolt_hole_radius = _pop_length_alias(
        kw,
        where=where,
        names=("bolt_hole_radius", "bolt_hole_radius_cm", "fastener_hole_radius", "fastener_hole_radius_cm"),
    )
    hole_chamfer = _pop_length_alias(
        kw,
        where=where,
        names=("hole_chamfer", "hole_chamfer_cm", "bore_chamfer", "bore_chamfer_cm"),
        default=0.0,
    ) or 0.0
    countersink_radius = _pop_length_alias(
        kw,
        where=where,
        names=("countersink_radius", "countersink_radius_cm", "sink_radius", "sink_radius_cm"),
    )
    countersink_depth = _pop_length_alias(
        kw,
        where=where,
        names=("countersink_depth", "countersink_depth_cm", "sink_depth", "sink_depth_cm"),
    )
    cut_padding = _pop_length_alias(
        kw,
        where=where,
        names=("cut_padding", "cut_padding_cm"),
        default=0.2,
    ) or 0.0
    axis_value = kw.pop("axis", None)
    normal_axis_value = kw.pop("normal_axis", None)
    if axis_value is not None and normal_axis_value is not None:
        raise MeshProgramError(f"{where}: supply either axis or normal_axis, not both")
    axis = _axis_arg(
        axis_value if axis_value is not None else normal_axis_value,
        where=f"{where}.axis",
        default="z",
    )
    center = _pop_optional_center(kw, where=where)
    start_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("start_degrees", "start_angle", "start_radians"),
        default=0.0,
    ) or 0.0
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_flange(...) argument(s): {unknown}")
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    if thickness is None or thickness <= 0.0:
        raise MeshProgramError(f"{where}: thickness must be > 0, got {thickness!r}cm")
    if rounding < 0.0:
        raise MeshProgramError(f"{where}: rounding must be >= 0")
    if rounding > 0.0:
        core_radius = float(radius) - float(rounding)
        core_height = float(thickness) - 2.0 * float(rounding)
        if core_radius <= 0.0 or core_height <= 0.0:
            raise MeshProgramError(f"{where}: rounding is too large for radius/thickness")
        plate: Any = Offset(expr=Cylinder(radius=core_radius, height=core_height), amount=float(rounding))
    else:
        plate = Cylinder(radius=float(radius), height=float(thickness))
    plate = _orient_y_axis_sdf(plate, axis=axis, where=where)

    cutters: list[Any] = []
    cut_depth = float(thickness) + 2.0 * float(cut_padding)
    if bore_radius is not None:
        if bore_radius <= 0.0 or bore_radius >= float(radius):
            raise MeshProgramError(f"{where}: bore_radius must satisfy 0 < bore_radius < radius")
        cutters.append(_orient_y_axis_sdf(Cylinder(radius=float(bore_radius), height=cut_depth), axis=axis, where=where))
    has_bolt_fields = bolt_count is not None or bolt_circle_radius is not None or bolt_hole_radius is not None
    if has_bolt_fields:
        if bolt_count is None or bolt_count < 1:
            raise MeshProgramError(f"{where}: bolt_count must be >= 1 when bolt holes are supplied")
        if bolt_circle_radius is None or bolt_circle_radius <= 0.0:
            raise MeshProgramError(f"{where}: bolt_circle_radius must be > 0")
        if bolt_hole_radius is None or bolt_hole_radius <= 0.0:
            raise MeshProgramError(f"{where}: bolt_hole_radius must be > 0")
        if bolt_circle_radius + bolt_hole_radius >= float(radius):
            raise MeshProgramError(f"{where}: bolt circle holes must fit inside flange radius")
        if countersink_radius is not None and (countersink_depth is None or countersink_depth <= 0.0):
            raise MeshProgramError(f"{where}: countersink_depth must be > 0 when countersink_radius is supplied")
        if countersink_depth is not None and countersink_radius is None:
            raise MeshProgramError(f"{where}: countersink_radius is required when countersink_depth is supplied")
        if countersink_radius is not None and countersink_radius <= bolt_hole_radius:
            raise MeshProgramError(f"{where}: countersink_radius must be > bolt_hole_radius")
        hole: Any = _orient_y_axis_sdf(Cylinder(radius=float(bolt_hole_radius), height=cut_depth), axis=axis, where=where)
        if countersink_radius is not None and countersink_depth is not None:
            sink = _orient_y_axis_sdf(
                Frustum(
                    radius_bottom=float(bolt_hole_radius),
                    radius_top=float(countersink_radius),
                    height=float(countersink_depth),
                ),
                axis=axis,
                where=where,
            )
            sink_offset = [0.0, 0.0, 0.0]
            sink_offset[{"x": 0, "y": 1, "z": 2}[axis]] = 0.5 * float(thickness) - 0.5 * float(countersink_depth)
            hole = Union(a=hole, b=Translate(expr=sink, offset=(sink_offset[0], sink_offset[1], sink_offset[2])))
        plane_axes_by_normal = {"x": (1, 2), "y": (0, 2), "z": (0, 1)}
        plane_axes = plane_axes_by_normal[axis]
        for index in range(int(bolt_count)):
            angle = math.radians(float(start_degrees) + 360.0 * index / float(bolt_count))
            offset = [0.0, 0.0, 0.0]
            offset[plane_axes[0]] = float(bolt_circle_radius) * math.cos(angle)
            offset[plane_axes[1]] = float(bolt_circle_radius) * math.sin(angle)
            cutters.append(Translate(expr=hole, offset=(offset[0], offset[1], offset[2])))
    if cutters:
        cutter = cutters[0]
        for next_cutter in cutters[1:]:
            cutter = Union(a=cutter, b=next_cutter)
        if hole_chamfer > 0.0:
            plate = ChamferSubtract(a=plate, b=cutter, radius=float(hole_chamfer))
        else:
            plate = Subtract(a=plate, b=cutter)
    if center is not None:
        plate = Translate(expr=plate, offset=(float(center[0]), float(center[1]), float(center[2])))
    return plate


def _extruded_profile_expr_with_axes(
    *,
    profile_points: tuple[tuple[float, float], ...],
    depth: float,
    axis_u: str,
    axis_v: str,
    normal_axis: str,
    center: tuple[float, float, float] | None,
    normal_offset: float | None,
) -> Any:
    from ..f_rep import ExtrudedPolygon, Translate

    expr: Any = ExtrudedPolygon(
        profile_points=profile_points,
        depth=float(depth),
        axis_u=axis_u,
        axis_v=axis_v,
        normal_axis=normal_axis,
    )
    offset = [0.0, 0.0, 0.0]
    if center is not None:
        offset = [float(center[0]), float(center[1]), float(center[2])]
    if normal_offset:
        offset[{"x": 0, "y": 1, "z": 2}[normal_axis]] += float(normal_offset)
    if any(abs(value) > 0.0 for value in offset):
        expr = Translate(expr=expr, offset=(offset[0], offset[1], offset[2]))
    return expr


def _eval_sdf_gusset_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a triangular structural gusset plate."""
    kw = _kwargs(args, where=where)
    length = _pop_length_alias(
        kw,
        where=where,
        names=("length", "length_cm", "base", "base_cm"),
        required=True,
    )
    height = _pop_length_alias(
        kw,
        where=where,
        names=("height", "height_cm", "rise", "rise_cm"),
        required=True,
    )
    thickness = _pop_length_alias(
        kw,
        where=where,
        names=("thickness", "thickness_cm", "depth", "depth_cm"),
        required=True,
    )
    handedness = _pop_string_alias(
        kw,
        where=where,
        names=("handedness", "slope"),
        default="right",
        allowed={"right", "left"},
    )
    normal_axis = _axis_arg(kw.pop("normal_axis", None), where=f"{where}.normal_axis", default="z")
    axis_u = _axis_arg(kw.pop("axis_u", None), where=f"{where}.axis_u", default="x")
    axis_v = _axis_arg(kw.pop("axis_v", None), where=f"{where}.axis_v", default="y")
    center = _pop_optional_center(kw, where=where)
    normal_offset = _pop_length_alias(
        kw,
        where=where,
        names=("normal_offset", "normal_offset_cm", "surface_offset", "surface_offset_cm", "center_offset", "center_offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_gusset(...) argument(s): {unknown}")
    if length is None or height is None or thickness is None or length <= 0.0 or height <= 0.0 or thickness <= 0.0:
        raise MeshProgramError(f"{where}: length, height, and thickness must be > 0")
    if len({normal_axis, axis_u, axis_v}) != 3:
        raise MeshProgramError(f"{where}: normal_axis, axis_u, and axis_v must be distinct")
    half_length = 0.5 * float(length)
    half_height = 0.5 * float(height)
    if handedness == "left":
        profile = (
            (-half_length, -half_height),
            (half_length, -half_height),
            (half_length, half_height),
        )
    else:
        profile = (
            (-half_length, -half_height),
            (half_length, -half_height),
            (-half_length, half_height),
        )
    return _extruded_profile_expr_with_axes(
        profile_points=profile,
        depth=float(thickness),
        axis_u=axis_u,
        axis_v=axis_v,
        normal_axis=normal_axis,
        center=center,
        normal_offset=normal_offset,
    )


def _eval_sdf_tapered_rib_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a trapezoid/tapered rib or dovetail-like structural profile."""
    kw = _kwargs(args, where=where)
    height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True)
    thickness = _pop_length_alias(
        kw,
        where=where,
        names=("thickness", "thickness_cm", "depth", "depth_cm"),
        required=True,
    )
    if "widths" in kw:
        bottom_width, top_width = _vec2_length(kw.pop("widths"), where=f"{where}.widths")
    else:
        bottom_width = _pop_length_alias(
            kw,
            where=where,
            names=("bottom_width", "bottom_width_cm", "base_width", "base_width_cm", "width", "width_cm"),
            required=True,
        ) or 0.0
        top_width = _pop_length_alias(
            kw,
            where=where,
            names=("top_width", "top_width_cm", "crown_width", "crown_width_cm"),
            default=bottom_width,
        ) or 0.0
    normal_axis = _axis_arg(kw.pop("normal_axis", None), where=f"{where}.normal_axis", default="z")
    axis_u = _axis_arg(kw.pop("axis_u", None), where=f"{where}.axis_u", default="x")
    axis_v = _axis_arg(kw.pop("axis_v", None), where=f"{where}.axis_v", default="y")
    center = _pop_optional_center(kw, where=where)
    normal_offset = _pop_length_alias(
        kw,
        where=where,
        names=("normal_offset", "normal_offset_cm", "surface_offset", "surface_offset_cm", "center_offset", "center_offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_tapered_rib(...) argument(s): {unknown}")
    if height is None or thickness is None or height <= 0.0 or thickness <= 0.0:
        raise MeshProgramError(f"{where}: height and thickness must be > 0")
    if bottom_width <= 0.0 or top_width <= 0.0:
        raise MeshProgramError(f"{where}: bottom/top widths must be > 0")
    if len({normal_axis, axis_u, axis_v}) != 3:
        raise MeshProgramError(f"{where}: normal_axis, axis_u, and axis_v must be distinct")
    half_bottom = 0.5 * float(bottom_width)
    half_top = 0.5 * float(top_width)
    half_height = 0.5 * float(height)
    profile = (
        (-half_bottom, -half_height),
        (half_bottom, -half_height),
        (half_top, half_height),
        (-half_top, half_height),
    )
    return _extruded_profile_expr_with_axes(
        profile_points=profile,
        depth=float(thickness),
        axis_u=axis_u,
        axis_v=axis_v,
        normal_axis=normal_axis,
        center=center,
        normal_offset=normal_offset,
    )


def _eval_sdf_panel_line_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a rounded rectangular panel-line cutter SDF."""
    from ..f_rep import RoundedSlot, Translate

    kw = _kwargs(args, where=where)
    length = _pop_length_alias(
        kw,
        where=where,
        names=("length", "length_cm"),
        required=True,
    )
    width = _pop_length_alias(
        kw,
        where=where,
        names=("width", "width_cm", "line_width", "line_width_cm"),
        required=True,
    )
    depth = _pop_length_alias(
        kw,
        where=where,
        names=("depth", "depth_cm", "cut_depth", "cut_depth_cm", "thickness", "thickness_cm"),
        required=True,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x")
    normal_axis = _axis_arg(
        kw.pop("normal_axis", None),
        where=f"{where}.normal_axis",
        default="z",
    )
    normal_offset = _pop_length_alias(
        kw,
        where=where,
        names=("normal_offset", "normal_offset_cm", "surface_offset", "surface_offset_cm", "center_offset", "center_offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_panel_line(...) argument(s): {unknown}")
    if length is None or length <= 0.0:
        raise MeshProgramError(f"{where}: length must be > 0, got {length!r}cm")
    if width is None or width <= 0.0:
        raise MeshProgramError(f"{where}: width must be > 0, got {width!r}cm")
    if depth is None or depth <= 0.0:
        raise MeshProgramError(f"{where}: depth must be > 0, got {depth!r}cm")
    radius = float(width) * 0.5
    if float(length) <= float(width):
        raise MeshProgramError(
            f"{where}: length must be larger than width, got length={length}cm width={width}cm"
        )
    if axis == normal_axis:
        raise MeshProgramError(f"{where}: axis and normal_axis must differ")
    expr = RoundedSlot(
        length=float(length),
        radius=radius,
        depth=float(depth),
        axis=axis,
        normal_axis=normal_axis,
    )
    if normal_offset:
        offset = [0.0, 0.0, 0.0]
        offset[{"x": 0, "y": 1, "z": 2}[normal_axis]] = float(normal_offset)
        return Translate(expr=expr, offset=(offset[0], offset[1], offset[2]))
    return expr


def _eval_sdf_fastener_grid_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a centered grid of raised cylindrical fastener heads."""
    from ..f_rep import Cylinder, Offset, Translate, Union

    kw = _kwargs(args, where=where)
    rows = _pop_int_alias(kw, where=where, names=("rows",), required=True)
    cols = _pop_int_alias(kw, where=where, names=("cols", "columns"), required=True)
    spacing = _vec2_length(kw.pop("spacing"), where=f"{where}.spacing") if "spacing" in kw else None
    if spacing is None:
        spacing = (
            _pop_length_alias(kw, where=where, names=("spacing_x", "column_spacing"), required=True) or 0.0,
            _pop_length_alias(kw, where=where, names=("spacing_y", "row_spacing"), required=True) or 0.0,
        )
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "fastener_radius", "fastener_radius_cm"),
        required=True,
    )
    height = _pop_length_alias(
        kw,
        where=where,
        names=("height", "height_cm", "fastener_height", "fastener_height_cm"),
        required=True,
    )
    rounding = _pop_length_alias(
        kw,
        where=where,
        names=("rounding", "rounding_cm", "head_rounding", "head_rounding_cm"),
        default=0.0,
    )
    normal_axis = _axis_arg(kw.pop("normal_axis", None), where=f"{where}.normal_axis", default="z")
    grid_axis_u = _axis_arg(kw.pop("axis_u", None), where=f"{where}.axis_u", default="x")
    grid_axis_v = _axis_arg(kw.pop("axis_v", None), where=f"{where}.axis_v", default="y")
    normal_offset = _pop_length_alias(
        kw,
        where=where,
        names=("normal_offset", "normal_offset_cm", "surface_offset", "surface_offset_cm", "center_offset", "center_offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_fastener_grid(...) argument(s): {unknown}")
    if rows is None or rows < 1:
        raise MeshProgramError(f"{where}: rows must be >= 1, got {rows!r}")
    if cols is None or cols < 1:
        raise MeshProgramError(f"{where}: cols must be >= 1, got {cols!r}")
    if spacing[0] <= 0.0 or spacing[1] <= 0.0:
        raise MeshProgramError(f"{where}: spacing values must be > 0, got {spacing!r}")
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    if height is None or height <= 0.0:
        raise MeshProgramError(f"{where}: height must be > 0, got {height!r}cm")
    if rounding is None or rounding < 0.0:
        raise MeshProgramError(f"{where}: rounding must be >= 0, got {rounding!r}cm")
    if len({normal_axis, grid_axis_u, grid_axis_v}) != 3:
        raise MeshProgramError(f"{where}: normal_axis, axis_u, and axis_v must be distinct")
    core_radius = float(radius)
    core_height = float(height)
    if rounding > 0.0:
        core_radius = float(radius) - float(rounding)
        core_height = float(height) - 2.0 * float(rounding)
        if core_radius <= 0.0 or core_height <= 0.0:
            raise MeshProgramError(
                f"{where}: rounding {rounding}cm is too large for radius={radius}cm height={height}cm"
            )
    base = Cylinder(radius=core_radius, height=core_height)
    if rounding > 0.0:
        base = Offset(expr=base, amount=float(rounding))
    base = _orient_y_axis_sdf(base, axis=normal_axis, where=where)
    axis_to_index = {"x": 0, "y": 1, "z": 2}
    expressions: list[Any] = []
    for row in range(int(rows)):
        for col in range(int(cols)):
            offset = [0.0, 0.0, 0.0]
            offset[axis_to_index[grid_axis_u]] = (col - (int(cols) - 1) * 0.5) * float(spacing[0])
            offset[axis_to_index[grid_axis_v]] = (row - (int(rows) - 1) * 0.5) * float(spacing[1])
            offset[axis_to_index[normal_axis]] = float(normal_offset or 0.0)
            expressions.append(Translate(expr=base, offset=(offset[0], offset[1], offset[2])))
    accumulated = expressions[0]
    for expr in expressions[1:]:
        accumulated = Union(a=accumulated, b=expr)
    return accumulated


def _eval_sdf_vent_slats_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a centered stack of rounded slot/slat SDFs."""
    from ..f_rep import RoundedSlot, Translate, Union

    kw = _kwargs(args, where=where)
    count = _pop_int_alias(kw, where=where, names=("count", "slats", "rows"), required=True)
    length = _pop_length_alias(kw, where=where, names=("length", "length_cm"), required=True)
    width = _pop_length_alias(
        kw,
        where=where,
        names=("width", "width_cm", "slat_width", "slat_width_cm"),
        required=True,
    )
    depth = _pop_length_alias(
        kw,
        where=where,
        names=("depth", "depth_cm", "cut_depth", "cut_depth_cm", "thickness", "thickness_cm"),
        required=True,
    )
    spacing = _pop_length_alias(
        kw,
        where=where,
        names=("spacing", "spacing_cm", "pitch", "pitch_cm"),
        required=True,
    )
    slot_axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x")
    normal_axis = _axis_arg(kw.pop("normal_axis", None), where=f"{where}.normal_axis", default="z")
    stack_axis = _axis_arg(kw.pop("stack_axis", None), where=f"{where}.stack_axis", default="y")
    normal_offset = _pop_length_alias(
        kw,
        where=where,
        names=("normal_offset", "normal_offset_cm", "surface_offset", "surface_offset_cm", "center_offset", "center_offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_vent_slats(...) argument(s): {unknown}")
    if count is None or count < 1:
        raise MeshProgramError(f"{where}: count must be >= 1, got {count!r}")
    if length is None or length <= 0.0:
        raise MeshProgramError(f"{where}: length must be > 0, got {length!r}cm")
    if width is None or width <= 0.0:
        raise MeshProgramError(f"{where}: width must be > 0, got {width!r}cm")
    if depth is None or depth <= 0.0:
        raise MeshProgramError(f"{where}: depth must be > 0, got {depth!r}cm")
    if spacing is None or spacing <= 0.0:
        raise MeshProgramError(f"{where}: spacing must be > 0, got {spacing!r}cm")
    if float(length) <= float(width):
        raise MeshProgramError(
            f"{where}: length must be larger than width, got length={length}cm width={width}cm"
        )
    if len({slot_axis, normal_axis, stack_axis}) != 3:
        raise MeshProgramError(f"{where}: axis, stack_axis, and normal_axis must be distinct")
    base = RoundedSlot(
        length=float(length),
        radius=0.5 * float(width),
        depth=float(depth),
        axis=slot_axis,
        normal_axis=normal_axis,
    )
    axis_to_index = {"x": 0, "y": 1, "z": 2}
    expressions: list[Any] = []
    for index in range(int(count)):
        offset = [0.0, 0.0, 0.0]
        offset[axis_to_index[stack_axis]] = (index - (int(count) - 1) * 0.5) * float(spacing)
        offset[axis_to_index[normal_axis]] = float(normal_offset or 0.0)
        expressions.append(Translate(expr=base, offset=(offset[0], offset[1], offset[2])))
    accumulated = expressions[0]
    for expr in expressions[1:]:
        accumulated = Union(a=accumulated, b=expr)
    return accumulated


def _eval_sdf_panel_frame_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a rounded rectangular four-side panel-frame cutter SDF."""
    from ..f_rep import RoundedSlot, Translate, Union

    kw = _kwargs(args, where=where)
    if "extents" in kw:
        width, height = _vec2_length(kw.pop("extents"), where=f"{where}.extents")
    elif "size" in kw:
        width, height = _vec2_length(kw.pop("size"), where=f"{where}.size")
    else:
        width = _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True) or 0.0
        height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True) or 0.0
    line_width = _pop_length_alias(
        kw,
        where=where,
        names=("line_width", "line_width_cm", "width_line", "frame_width", "frame_width_cm"),
        required=True,
    )
    depth = _pop_length_alias(
        kw,
        where=where,
        names=("depth", "depth_cm", "cut_depth", "cut_depth_cm", "thickness", "thickness_cm"),
        required=True,
    )
    normal_axis = _axis_arg(kw.pop("normal_axis", None), where=f"{where}.normal_axis", default="z")
    axis_u = _axis_arg(kw.pop("axis_u", None), where=f"{where}.axis_u", default="x")
    axis_v = _axis_arg(kw.pop("axis_v", None), where=f"{where}.axis_v", default="y")
    normal_offset = _pop_length_alias(
        kw,
        where=where,
        names=("normal_offset", "normal_offset_cm", "surface_offset", "surface_offset_cm", "center_offset", "center_offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_panel_frame(...) argument(s): {unknown}")
    if width <= 0.0 or height <= 0.0:
        raise MeshProgramError(f"{where}: width and height must be > 0, got {width}cm, {height}cm")
    if line_width is None or line_width <= 0.0:
        raise MeshProgramError(f"{where}: line_width must be > 0, got {line_width!r}cm")
    if depth is None or depth <= 0.0:
        raise MeshProgramError(f"{where}: depth must be > 0, got {depth!r}cm")
    if len({normal_axis, axis_u, axis_v}) != 3:
        raise MeshProgramError(f"{where}: normal_axis, axis_u, and axis_v must be distinct")
    if width <= line_width or height <= line_width:
        raise MeshProgramError(
            f"{where}: extents must be larger than line_width, got extents=({width}, {height})cm line_width={line_width}cm"
        )
    radius = 0.5 * float(line_width)
    horizontal = RoundedSlot(
        length=float(width),
        radius=radius,
        depth=float(depth),
        axis=axis_u,
        normal_axis=normal_axis,
    )
    vertical = RoundedSlot(
        length=float(height),
        radius=radius,
        depth=float(depth),
        axis=axis_v,
        normal_axis=normal_axis,
    )
    axis_to_index = {"x": 0, "y": 1, "z": 2}
    offsets = [
        (horizontal, axis_v, 0.5 * float(height) - radius),
        (horizontal, axis_v, -0.5 * float(height) + radius),
        (vertical, axis_u, 0.5 * float(width) - radius),
        (vertical, axis_u, -0.5 * float(width) + radius),
    ]
    expressions: list[Any] = []
    for expr, offset_axis, amount in offsets:
        offset = [0.0, 0.0, 0.0]
        offset[axis_to_index[offset_axis]] = amount
        offset[axis_to_index[normal_axis]] = float(normal_offset or 0.0)
        expressions.append(Translate(expr=expr, offset=(offset[0], offset[1], offset[2])))
    accumulated = expressions[0]
    for expr in expressions[1:]:
        accumulated = Union(a=accumulated, b=expr)
    return accumulated


def _eval_sdf_mount_plate_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a rounded mount plate with optional through/countersunk holes."""
    from ..f_rep import Box, ChamferSubtract, Cylinder, Frustum, Offset, Subtract, Translate, Union

    kw = _kwargs(args, where=where)
    if "extents" in kw:
        extents = _vec3(kw.pop("extents"), where=f"{where}.extents")
        width, height, thickness = extents
    elif "size" in kw:
        width, height = _vec2_length(kw.pop("size"), where=f"{where}.size")
        thickness = _pop_length_alias(
            kw,
            where=where,
            names=("thickness", "thickness_cm", "depth", "depth_cm"),
            required=True,
        ) or 0.0
    else:
        width = _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True) or 0.0
        height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True) or 0.0
        thickness = _pop_length_alias(
            kw,
            where=where,
            names=("thickness", "thickness_cm", "depth", "depth_cm"),
            required=True,
        ) or 0.0
    rounding = _pop_length_alias(
        kw,
        where=where,
        names=("rounding", "rounding_cm", "corner_radius", "corner_radius_cm", "edge_radius", "edge_radius_cm"),
        default=0.0,
    )
    normal_axis = _axis_arg(kw.pop("normal_axis", None), where=f"{where}.normal_axis", default="z")
    axis_u = _axis_arg(kw.pop("axis_u", None), where=f"{where}.axis_u", default="x")
    axis_v = _axis_arg(kw.pop("axis_v", None), where=f"{where}.axis_v", default="y")
    hole_radius = _pop_length_alias(
        kw,
        where=where,
        names=("hole_radius", "hole_radius_cm", "bore_radius", "bore_radius_cm"),
    )
    hole_rows = _pop_int_alias(kw, where=where, names=("hole_rows", "rows"))
    hole_cols = _pop_int_alias(kw, where=where, names=("hole_cols", "cols", "columns"))
    hole_spacing = _vec2_length(kw.pop("hole_spacing"), where=f"{where}.hole_spacing") if "hole_spacing" in kw else None
    if hole_spacing is None and "spacing" in kw:
        hole_spacing = _vec2_length(kw.pop("spacing"), where=f"{where}.spacing")
    hole_spacing_x = _pop_length_alias(kw, where=where, names=("hole_spacing_x", "spacing_x", "column_spacing"))
    hole_spacing_y = _pop_length_alias(kw, where=where, names=("hole_spacing_y", "spacing_y", "row_spacing"))
    hole_chamfer = _pop_length_alias(
        kw,
        where=where,
        names=("hole_chamfer", "hole_chamfer_cm", "hole_bevel", "hole_bevel_cm"),
        default=0.0,
    )
    countersink_radius = _pop_length_alias(
        kw,
        where=where,
        names=("countersink_radius", "countersink_radius_cm", "sink_radius", "sink_radius_cm"),
    )
    countersink_depth = _pop_length_alias(
        kw,
        where=where,
        names=("countersink_depth", "countersink_depth_cm", "sink_depth", "sink_depth_cm"),
    )
    cut_padding = _pop_length_alias(
        kw,
        where=where,
        names=("cut_padding", "cut_padding_cm"),
        default=0.2,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_mount_plate(...) argument(s): {unknown}")
    if width <= 0.0 or height <= 0.0 or thickness <= 0.0:
        raise MeshProgramError(
            f"{where}: width, height, and thickness must be > 0, got {width}cm, {height}cm, {thickness}cm"
        )
    if rounding is None or rounding < 0.0:
        raise MeshProgramError(f"{where}: rounding must be >= 0, got {rounding!r}cm")
    if len({normal_axis, axis_u, axis_v}) != 3:
        raise MeshProgramError(f"{where}: normal_axis, axis_u, and axis_v must be distinct")
    axis_to_index = {"x": 0, "y": 1, "z": 2}
    half = [0.0, 0.0, 0.0]
    if rounding and rounding > 0.0:
        core_width = float(width) - 2.0 * float(rounding)
        core_height = float(height) - 2.0 * float(rounding)
        core_thickness = float(thickness) - 2.0 * float(rounding)
        if core_width <= 0.0 or core_height <= 0.0 or core_thickness <= 0.0:
            raise MeshProgramError(
                f"{where}: rounding {rounding}cm is too large for extents=({width}, {height}, {thickness})cm"
            )
        half[axis_to_index[axis_u]] = 0.5 * core_width
        half[axis_to_index[axis_v]] = 0.5 * core_height
        half[axis_to_index[normal_axis]] = 0.5 * core_thickness
        plate: Any = Offset(expr=Box(tuple(half)), amount=float(rounding))
    else:
        half[axis_to_index[axis_u]] = 0.5 * float(width)
        half[axis_to_index[axis_v]] = 0.5 * float(height)
        half[axis_to_index[normal_axis]] = 0.5 * float(thickness)
        plate = Box(tuple(half))
    if hole_radius is None:
        return plate
    if hole_radius <= 0.0:
        raise MeshProgramError(f"{where}: hole_radius must be > 0, got {hole_radius!r}cm")
    rows = int(hole_rows or 1)
    cols = int(hole_cols or 1)
    if rows < 1 or cols < 1:
        raise MeshProgramError(f"{where}: hole rows/cols must be >= 1, got {rows}, {cols}")
    if hole_spacing is None:
        hole_spacing = (
            float(hole_spacing_x or 1.0),
            float(hole_spacing_y or 1.0),
        )
    if (cols > 1 and hole_spacing[0] <= 0.0) or (rows > 1 and hole_spacing[1] <= 0.0):
        raise MeshProgramError(f"{where}: hole spacing must be > 0 for repeated holes, got {hole_spacing!r}")
    if countersink_radius is not None and (countersink_depth is None or countersink_depth <= 0.0):
        raise MeshProgramError(f"{where}: countersink_depth must be > 0 when countersink_radius is supplied")
    if countersink_depth is not None and countersink_radius is None:
        raise MeshProgramError(f"{where}: countersink_radius is required when countersink_depth is supplied")
    if countersink_radius is not None and countersink_radius <= hole_radius:
        raise MeshProgramError(
            f"{where}: countersink_radius must be > hole_radius, got {countersink_radius}cm <= {hole_radius}cm"
        )
    hole_depth = float(thickness) + 2.0 * float(cut_padding or 0.0)
    bore = _orient_y_axis_sdf(
        Cylinder(radius=float(hole_radius), height=hole_depth),
        axis=normal_axis,
        where=where,
    )
    if countersink_radius is not None and countersink_depth is not None:
        sink = _orient_y_axis_sdf(
            Frustum(
                radius_bottom=float(hole_radius),
                radius_top=float(countersink_radius),
                height=float(countersink_depth),
            ),
            axis=normal_axis,
            where=where,
        )
        sink_offset = [0.0, 0.0, 0.0]
        sink_offset[axis_to_index[normal_axis]] = 0.5 * float(thickness) - 0.5 * float(countersink_depth)
        bore = Union(
            a=bore,
            b=Translate(expr=sink, offset=(sink_offset[0], sink_offset[1], sink_offset[2])),
        )
    holes: list[Any] = []
    for row in range(rows):
        for col in range(cols):
            offset = [0.0, 0.0, 0.0]
            offset[axis_to_index[axis_u]] = (col - (cols - 1) * 0.5) * float(hole_spacing[0])
            offset[axis_to_index[axis_v]] = (row - (rows - 1) * 0.5) * float(hole_spacing[1])
            holes.append(Translate(expr=bore, offset=(offset[0], offset[1], offset[2])))
    hole_expr = holes[0]
    for hole in holes[1:]:
        hole_expr = Union(a=hole_expr, b=hole)
    if hole_chamfer and hole_chamfer > 0.0:
        return ChamferSubtract(a=plate, b=hole_expr, radius=float(hole_chamfer))
    return Subtract(a=plate, b=hole_expr)


def _eval_sdf_socket_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a rounded rectangular socket/rim with an inset opening."""
    from ..f_rep import Box, ChamferSubtract, Offset, Subtract, Translate

    kw = _kwargs(args, where=where)
    if "outer_extents" in kw:
        outer_width, outer_height, thickness = _vec3(kw.pop("outer_extents"), where=f"{where}.outer_extents")
    elif "extents" in kw:
        outer_width, outer_height, thickness = _vec3(kw.pop("extents"), where=f"{where}.extents")
    else:
        outer_width = _pop_length_alias(kw, where=where, names=("outer_width", "width", "width_cm"), required=True) or 0.0
        outer_height = _pop_length_alias(kw, where=where, names=("outer_height", "height", "height_cm"), required=True) or 0.0
        thickness = _pop_length_alias(
            kw,
            where=where,
            names=("thickness", "thickness_cm", "depth", "depth_cm"),
            required=True,
        ) or 0.0
    if "opening_extents" in kw:
        opening_width, opening_height = _vec2_length(kw.pop("opening_extents"), where=f"{where}.opening_extents")
    elif "inner_extents" in kw:
        opening_width, opening_height = _vec2_length(kw.pop("inner_extents"), where=f"{where}.inner_extents")
    else:
        opening_width = _pop_length_alias(
            kw,
            where=where,
            names=("opening_width", "inner_width", "inner_width_cm"),
            required=True,
        ) or 0.0
        opening_height = _pop_length_alias(
            kw,
            where=where,
            names=("opening_height", "inner_height", "inner_height_cm"),
            required=True,
        ) or 0.0
    outer_rounding = _pop_length_alias(
        kw,
        where=where,
        names=("outer_rounding", "outer_rounding_cm", "rounding", "rounding_cm", "corner_radius", "corner_radius_cm"),
        default=0.0,
    )
    opening_rounding = _pop_length_alias(
        kw,
        where=where,
        names=("opening_rounding", "opening_rounding_cm", "inner_rounding", "inner_rounding_cm"),
        default=0.0,
    )
    opening_depth = _pop_length_alias(
        kw,
        where=where,
        names=("opening_depth", "opening_depth_cm", "cut_depth", "cut_depth_cm"),
        default=thickness,
    )
    cut_chamfer = _pop_length_alias(
        kw,
        where=where,
        names=("cut_chamfer", "cut_chamfer_cm", "opening_chamfer", "opening_chamfer_cm"),
        default=0.0,
    )
    normal_axis = _axis_arg(kw.pop("normal_axis", None), where=f"{where}.normal_axis", default="z")
    axis_u = _axis_arg(kw.pop("axis_u", None), where=f"{where}.axis_u", default="x")
    axis_v = _axis_arg(kw.pop("axis_v", None), where=f"{where}.axis_v", default="y")
    normal_offset = _pop_length_alias(
        kw,
        where=where,
        names=("normal_offset", "normal_offset_cm", "surface_offset", "surface_offset_cm", "center_offset", "center_offset_cm"),
        default=0.0,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_socket(...) argument(s): {unknown}")
    if outer_width <= 0.0 or outer_height <= 0.0 or thickness <= 0.0:
        raise MeshProgramError(
            f"{where}: outer dimensions must be > 0, got {outer_width}cm, {outer_height}cm, {thickness}cm"
        )
    if opening_width <= 0.0 or opening_height <= 0.0:
        raise MeshProgramError(
            f"{where}: opening dimensions must be > 0, got {opening_width}cm, {opening_height}cm"
        )
    if opening_width >= outer_width or opening_height >= outer_height:
        raise MeshProgramError(
            f"{where}: opening must fit inside outer extents, got opening=({opening_width}, {opening_height})cm outer=({outer_width}, {outer_height})cm"
        )
    if opening_depth is None or opening_depth <= 0.0:
        raise MeshProgramError(f"{where}: opening_depth must be > 0, got {opening_depth!r}cm")
    if len({normal_axis, axis_u, axis_v}) != 3:
        raise MeshProgramError(f"{where}: normal_axis, axis_u, and axis_v must be distinct")
    axis_to_index = {"x": 0, "y": 1, "z": 2}

    def rounded_box(width: float, height: float, depth: float, rounding: float | None) -> Any:
        half = [0.0, 0.0, 0.0]
        amount = float(rounding or 0.0)
        if amount > 0.0:
            core_width = float(width) - 2.0 * amount
            core_height = float(height) - 2.0 * amount
            core_depth = float(depth) - 2.0 * amount
            if core_width <= 0.0 or core_height <= 0.0 or core_depth <= 0.0:
                raise MeshProgramError(
                    f"{where}: rounding {amount}cm is too large for box=({width}, {height}, {depth})cm"
                )
            half[axis_to_index[axis_u]] = 0.5 * core_width
            half[axis_to_index[axis_v]] = 0.5 * core_height
            half[axis_to_index[normal_axis]] = 0.5 * core_depth
            return Offset(expr=Box(tuple(half)), amount=amount)
        half[axis_to_index[axis_u]] = 0.5 * float(width)
        half[axis_to_index[axis_v]] = 0.5 * float(height)
        half[axis_to_index[normal_axis]] = 0.5 * float(depth)
        return Box(tuple(half))

    outer = rounded_box(float(outer_width), float(outer_height), float(thickness), outer_rounding)
    opening = rounded_box(float(opening_width), float(opening_height), float(opening_depth), opening_rounding)
    if normal_offset:
        offset = [0.0, 0.0, 0.0]
        offset[axis_to_index[normal_axis]] = float(normal_offset)
        opening = Translate(expr=opening, offset=(offset[0], offset[1], offset[2]))
    if cut_chamfer and cut_chamfer > 0.0:
        return ChamferSubtract(a=outer, b=opening, radius=float(cut_chamfer))
    return Subtract(a=outer, b=opening)


def _eval_sdf_countersunk_hole_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a subtractive cylindrical bore with one or two countersunk mouths."""
    from ..f_rep import Cylinder, Frustum, Translate, Union

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "bore_radius", "bore_radius_cm"),
        required=True,
    )
    depth = _pop_length_alias(
        kw,
        where=where,
        names=("depth", "depth_cm", "height", "height_cm"),
        required=True,
    )
    countersink_radius = _pop_length_alias(
        kw,
        where=where,
        names=("countersink_radius", "sink_radius", "head_radius", "head_radius_cm"),
        required=True,
    )
    countersink_depth = _pop_length_alias(
        kw,
        where=where,
        names=("countersink_depth", "sink_depth", "head_depth", "head_depth_cm"),
        required=True,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    side = _pop_string_alias(
        kw,
        where=where,
        names=("side", "sink_side", "countersink_side"),
        default="positive",
        allowed={"positive", "negative", "both", "+", "-"},
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_countersunk_hole(...) argument(s): {unknown}"
        )
    if radius is None or radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius!r}cm")
    if depth is None or depth <= 0.0:
        raise MeshProgramError(f"{where}: depth must be > 0, got {depth!r}cm")
    if countersink_radius is None or countersink_radius <= float(radius):
        raise MeshProgramError(
            f"{where}: countersink_radius must be > radius, "
            f"got radius={radius!r}cm countersink_radius={countersink_radius!r}cm"
        )
    if countersink_depth is None or countersink_depth <= 0.0:
        raise MeshProgramError(
            f"{where}: countersink_depth must be > 0, got {countersink_depth!r}cm"
        )
    if countersink_depth > depth:
        raise MeshProgramError(
            f"{where}: countersink_depth must be <= depth, "
            f"got countersink_depth={countersink_depth}cm depth={depth}cm"
        )

    side = "positive" if side == "+" else "negative" if side == "-" else str(side)
    expr: Any = Cylinder(radius=float(radius), height=float(depth))
    if side in {"positive", "both"}:
        positive_sink = Translate(
            expr=Frustum(
                radius_bottom=float(radius),
                radius_top=float(countersink_radius),
                height=float(countersink_depth),
            ),
            offset=(0.0, 0.5 * float(depth) - 0.5 * float(countersink_depth), 0.0),
        )
        expr = Union(expr, positive_sink)
    if side in {"negative", "both"}:
        negative_sink = Translate(
            expr=Frustum(
                radius_bottom=float(countersink_radius),
                radius_top=float(radius),
                height=float(countersink_depth),
            ),
            offset=(0.0, -0.5 * float(depth) + 0.5 * float(countersink_depth), 0.0),
        )
        expr = Union(expr, negative_sink)
    return _orient_y_axis_sdf(expr, axis=axis, where=where)


def _eval_sdf_torus_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a torus SDF with its native ring normal on +Y."""
    from ..f_rep import Torus

    kw = _kwargs(args, where=where)
    major = _pop_length_alias(
        kw,
        where=where,
        names=("major_radius", "major_radius_cm", "major", "radius"),
        required=True,
    )
    minor = _pop_length_alias(
        kw,
        where=where,
        names=("minor_radius", "minor_radius_cm", "minor", "tube_radius", "tube_radius_cm"),
        required=True,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_torus(...) argument(s): {unknown}")
    if major <= 0.0:
        raise MeshProgramError(f"{where}: major_radius must be > 0, got {major}cm")
    if minor <= 0.0:
        raise MeshProgramError(f"{where}: minor_radius must be > 0, got {minor}cm")
    if minor >= major:
        raise MeshProgramError(
            f"{where}: minor_radius must be smaller than major_radius, got {minor}cm >= {major}cm"
        )
    return _orient_y_axis_sdf(
        Torus(major_radius=major, minor_radius=minor),
        axis=axis,
        where=where,
    )


def _eval_sdf_cone_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a capped-cone SDF."""
    from ..f_rep import Cone

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(kw, where=where, names=("radius", "radius_cm"), required=True)
    half_height = _pop_half_height_or_height(kw, where=where, op_name="sdf_cone")
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_cone(...) argument(s): {unknown}")
    if radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius}cm")
    if half_height <= 0.0:
        raise MeshProgramError(f"{where}: half_height must be > 0, got {half_height}cm")
    return _orient_y_axis_sdf(
        Cone(radius=radius, half_height=half_height),
        axis=axis,
        where=where,
    )


def _eval_sdf_hex_prism_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build a hexagonal-prism SDF."""
    from ..f_rep import HexPrism

    kw = _kwargs(args, where=where)
    radius = _pop_length_alias(kw, where=where, names=("radius", "radius_cm"), required=True)
    half_height = _pop_half_height_or_height(kw, where=where, op_name="sdf_hex_prism")
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_hex_prism(...) argument(s): {unknown}")
    if radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius}cm")
    if half_height <= 0.0:
        raise MeshProgramError(f"{where}: half_height must be > 0, got {half_height}cm")
    return _orient_y_axis_sdf(
        HexPrism(radius=radius, half_height=half_height),
        axis=axis,
        where=where,
    )


def _eval_sdf_ellipsoid_call(args: list[dict[str, Any]], *, part: str, where: str) -> Any:
    """Build an ellipsoid SDF from full extents or half-extents."""
    from ..f_rep import Ellipsoid

    kw = _kwargs(args, where=where)
    if "extents" in kw:
        extents = _vec3(kw.pop("extents"), where=f"{where}.extents")
        half_extents = tuple(float(value) * 0.5 for value in extents)
    elif "half_extents" in kw:
        half_extents = _vec3(kw.pop("half_extents"), where=f"{where}.half_extents")
    else:
        raise MeshProgramError(f"{where}: sdf_ellipsoid(...) requires 'extents' or 'half_extents'")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_ellipsoid(...) argument(s): {unknown}")
    if any(value <= 0.0 for value in half_extents):
        raise MeshProgramError(
            f"{where}: all half_extents components must be > 0, got {list(half_extents)}"
        )
    return Ellipsoid(half_extents=half_extents)


def _resolve_sdf(value: _Value, *, where: str) -> Any:
    """Return the SDFExpr backing a ``kind="sdf"`` binding, or raise."""
    if value.kind != "sdf" or value.sdf_expr is None:
        raise MeshProgramError(
            f"{where}: expected an SDF reference, got kind={value.kind!r}"
        )
    return value.sdf_expr


def _sdf_targets_from_kw(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    op_name: str,
    where: str,
) -> list[Any]:
    if "targets" in kw:
        targets_value = kw.pop("targets")
        if not isinstance(targets_value, list) or not targets_value:
            raise MeshProgramError(
                f"{where}: targets must be a non-empty list of identifiers, got {targets_value!r}"
            )
        expressions: list[Any] = []
        for index, ident_value in enumerate(targets_value):
            ident_name = _ident(ident_value, where=f"{where}.targets[{index}]")
            if ident_name not in bindings:
                raise MeshProgramError(
                    f"{where}: targets[{index}] references unknown identifier {ident_name!r}"
                )
            expressions.append(
                _resolve_sdf(bindings[ident_name], where=f"{where}.targets[{index}]")
            )
        return expressions
    left_value = None
    right_value = None
    for name in ("a", "source", "left", "target"):
        if name in kw:
            left_value = kw.pop(name)
            break
    for name in ("b", "cutter", "right", "other"):
        if name in kw:
            right_value = kw.pop(name)
            break
    if left_value is None or right_value is None:
        raise MeshProgramError(
            f"{where}: {op_name}(...) requires 'targets' or two SDF operands 'a' and 'b'"
        )
    left_name = _ident(left_value, where=f"{where}.a")
    right_name = _ident(right_value, where=f"{where}.b")
    if left_name not in bindings:
        raise MeshProgramError(f"{where}: a references unknown identifier {left_name!r}")
    if right_name not in bindings:
        raise MeshProgramError(f"{where}: b references unknown identifier {right_name!r}")
    return [
        _resolve_sdf(bindings[left_name], where=f"{where}.a"),
        _resolve_sdf(bindings[right_name], where=f"{where}.b"),
    ]


def _sdf_binary_operands_from_kw(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    op_name: str,
    where: str,
) -> tuple[Any, Any]:
    left_value = None
    right_value = None
    for name in ("a", "source", "left", "target"):
        if name in kw:
            left_value = kw.pop(name)
            break
    for name in ("b", "cutter", "right", "other"):
        if name in kw:
            right_value = kw.pop(name)
            break
    if left_value is None or right_value is None:
        raise MeshProgramError(f"{where}: {op_name}(...) requires SDF operands 'a' and 'b'")
    left_name = _ident(left_value, where=f"{where}.a")
    right_name = _ident(right_value, where=f"{where}.b")
    if left_name not in bindings:
        raise MeshProgramError(f"{where}: a references unknown identifier {left_name!r}")
    if right_name not in bindings:
        raise MeshProgramError(f"{where}: b references unknown identifier {right_name!r}")
    return (
        _resolve_sdf(bindings[left_name], where=f"{where}.a"),
        _resolve_sdf(bindings[right_name], where=f"{where}.b"),
    )


def _fold_sdf_binary(expressions: list[Any], binary_cls: Any) -> Any:
    accumulated = expressions[0]
    for expr in expressions[1:]:
        accumulated = binary_cls(a=accumulated, b=expr)
    return accumulated


def _fold_sdf_smooth_binary(expressions: list[Any], binary_cls: Any, *, k_cm: float) -> Any:
    accumulated = expressions[0]
    for expr in expressions[1:]:
        accumulated = binary_cls(a=accumulated, b=expr, k=k_cm)
    return accumulated


def _fold_sdf_chamfer_binary(expressions: list[Any], binary_cls: Any, *, radius_cm: float) -> Any:
    accumulated = expressions[0]
    for expr in expressions[1:]:
        accumulated = binary_cls(a=accumulated, b=expr, radius=radius_cm)
    return accumulated


def _pop_sdf_chamfer_radius(kw: dict[str, Any], *, where: str) -> float:
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "chamfer", "chamfer_cm", "width", "width_cm"),
        required=True,
    )
    if radius is None or radius < 0.0:
        raise MeshProgramError(f"{where}: chamfer radius must be >= 0, got {radius!r}cm")
    return float(radius)


def _apply_sdf_union(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    from ..f_rep import Union

    kw = _kwargs(args, where=where)
    expressions = _sdf_targets_from_kw(kw, bindings, op_name="sdf_union", where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_union(...) argument(s): {unknown}")
    return _Value(kind="sdf", sdf_expr=_fold_sdf_binary(expressions, Union))


def _apply_sdf_intersect(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    from ..f_rep import Intersect

    kw = _kwargs(args, where=where)
    expressions = _sdf_targets_from_kw(kw, bindings, op_name="sdf_intersect", where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_intersect(...) argument(s): {unknown}")
    return _Value(kind="sdf", sdf_expr=_fold_sdf_binary(expressions, Intersect))


def _apply_sdf_subtract(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    from ..f_rep import Subtract

    kw = _kwargs(args, where=where)
    left, right = _sdf_binary_operands_from_kw(kw, bindings, op_name="sdf_subtract", where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_subtract(...) argument(s): {unknown}")
    return _Value(kind="sdf", sdf_expr=Subtract(a=left, b=right))


def _apply_sdf_smooth_union(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Combine N SDF references via IQ ``opSmoothUnion`` with blend ``k``.

    ``targets`` is a list of identifiers each bound to a kind="sdf"
    ``_Value``; ``k`` is the blend radius (cm). Reduces left-to-right via
    ``SmoothUnion`` so the result is a single SDFExpr that downstream
    ``sdf_extract`` can sample.
    """
    from ..f_rep import SmoothUnion

    kw = _kwargs(args, where=where)
    if "k" not in kw:
        raise MeshProgramError(
            f"{where}: sdf_smooth_union(...) requires 'k' (blend radius)"
        )
    k_cm = _unit_to_cm(kw.pop("k"), where=f"{where}.k")
    expressions = _sdf_targets_from_kw(
        kw,
        bindings,
        op_name="sdf_smooth_union",
        where=where,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_smooth_union(...) argument(s): {unknown}"
        )
    if k_cm < 0.0:
        raise MeshProgramError(f"{where}: k must be >= 0, got {k_cm}cm")
    return _Value(
        kind="sdf",
        sdf_expr=_fold_sdf_smooth_binary(expressions, SmoothUnion, k_cm=k_cm),
    )


def _apply_sdf_smooth_intersect(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Combine N SDF references via softened intersection."""
    from ..f_rep import SmoothIntersect

    kw = _kwargs(args, where=where)
    expressions = _sdf_targets_from_kw(
        kw,
        bindings,
        op_name="sdf_smooth_intersect",
        where=where,
    )
    if "k" not in kw:
        raise MeshProgramError(f"{where}: sdf_smooth_intersect(...) requires 'k' (blend radius)")
    k_cm = _unit_to_cm(kw.pop("k"), where=f"{where}.k")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_smooth_intersect(...) argument(s): {unknown}")
    if k_cm < 0.0:
        raise MeshProgramError(f"{where}: k must be >= 0, got {k_cm}cm")
    return _Value(
        kind="sdf",
        sdf_expr=_fold_sdf_smooth_binary(expressions, SmoothIntersect, k_cm=k_cm),
    )


def _apply_sdf_smooth_subtract(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Subtract one SDF from another with an IQ smooth max edge."""
    from ..f_rep import SmoothSubtract

    kw = _kwargs(args, where=where)
    left, right = _sdf_binary_operands_from_kw(
        kw,
        bindings,
        op_name="sdf_smooth_subtract",
        where=where,
    )
    if "k" not in kw:
        raise MeshProgramError(f"{where}: sdf_smooth_subtract(...) requires 'k' (blend radius)")
    k_cm = _unit_to_cm(kw.pop("k"), where=f"{where}.k")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_smooth_subtract(...) argument(s): {unknown}")
    if k_cm < 0.0:
        raise MeshProgramError(f"{where}: k must be >= 0, got {k_cm}cm")
    return _Value(kind="sdf", sdf_expr=SmoothSubtract(a=left, b=right, k=k_cm))


def _apply_sdf_chamfer_union(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Combine N SDF references with a crisp chamfered union edge."""
    from ..f_rep import ChamferUnion

    kw = _kwargs(args, where=where)
    radius_cm = _pop_sdf_chamfer_radius(kw, where=where)
    expressions = _sdf_targets_from_kw(
        kw,
        bindings,
        op_name="sdf_chamfer_union",
        where=where,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_chamfer_union(...) argument(s): {unknown}")
    return _Value(
        kind="sdf",
        sdf_expr=_fold_sdf_chamfer_binary(expressions, ChamferUnion, radius_cm=radius_cm),
    )


def _apply_sdf_chamfer_intersect(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Combine N SDF references with a crisp chamfered intersection edge."""
    from ..f_rep import ChamferIntersect

    kw = _kwargs(args, where=where)
    radius_cm = _pop_sdf_chamfer_radius(kw, where=where)
    expressions = _sdf_targets_from_kw(
        kw,
        bindings,
        op_name="sdf_chamfer_intersect",
        where=where,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_chamfer_intersect(...) argument(s): {unknown}")
    return _Value(
        kind="sdf",
        sdf_expr=_fold_sdf_chamfer_binary(expressions, ChamferIntersect, radius_cm=radius_cm),
    )


def _apply_sdf_chamfer_subtract(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Subtract one SDF from another with a crisp chamfer around the cut."""
    from ..f_rep import ChamferSubtract

    kw = _kwargs(args, where=where)
    radius_cm = _pop_sdf_chamfer_radius(kw, where=where)
    left, right = _sdf_binary_operands_from_kw(
        kw,
        bindings,
        op_name="sdf_chamfer_subtract",
        where=where,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sdf_chamfer_subtract(...) argument(s): {unknown}")
    return _Value(kind="sdf", sdf_expr=ChamferSubtract(a=left, b=right, radius=radius_cm))


def _repeat_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    """Wrap an SDFExpr in finite, clamped domain repetition."""
    from ..f_rep import Repeat

    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x")
    count = _pop_int_alias(
        kw,
        where=where,
        names=("count", "copies", "instances"),
        required=True,
    )
    period = _pop_length_alias(
        kw,
        where=where,
        names=("period", "period_cm", "spacing", "spacing_cm"),
        required=True,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown repeat argument(s): {unknown}")
    if count is None or count < 1:
        raise MeshProgramError(f"{where}: count must be >= 1, got {count!r}")
    if period is None or period <= 0.0:
        raise MeshProgramError(f"{where}: period must be > 0, got {period!r}cm")
    return Repeat(expr=sdf_expr, axis=axis, count=count, period=period)


def _repeat_grid_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    """Wrap an SDFExpr in finite axis-aligned grid repetition."""
    from ..f_rep import Repeat

    if "counts" in kw:
        counts = _int_list(kw.pop("counts"), where=f"{where}.counts", count=3)
    else:
        counts = [
            _pop_int_alias(kw, where=where, names=("count_x", "nx"), default=1) or 1,
            _pop_int_alias(kw, where=where, names=("count_y", "ny"), default=1) or 1,
            _pop_int_alias(kw, where=where, names=("count_z", "nz"), default=1) or 1,
        ]
    if "spacing" in kw:
        spacing = list(_vec3(kw.pop("spacing"), where=f"{where}.spacing"))
    elif "period" in kw:
        spacing = list(_vec3(kw.pop("period"), where=f"{where}.period"))
    else:
        spacing = [
            _pop_length_alias(kw, where=where, names=("spacing_x", "period_x"), default=1.0) or 1.0,
            _pop_length_alias(kw, where=where, names=("spacing_y", "period_y"), default=1.0) or 1.0,
            _pop_length_alias(kw, where=where, names=("spacing_z", "period_z"), default=1.0) or 1.0,
        ]
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown repeat_grid argument(s): {unknown}")
    for axis_name, count in zip("xyz", counts, strict=False):
        if count < 1:
            raise MeshProgramError(
                f"{where}: count_{axis_name} must be >= 1, got {count}"
            )
    for axis_name, period in zip("xyz", spacing, strict=False):
        if period <= 0.0:
            raise MeshProgramError(
                f"{where}: spacing_{axis_name} must be > 0, got {period}cm"
            )
    repeated = sdf_expr
    for axis_name, count, period in zip("xyz", counts, spacing, strict=False):
        if count > 1:
            repeated = Repeat(
                expr=repeated,
                axis=axis_name,
                count=int(count),
                period=float(period),
            )
    return repeated


def _radial_array_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    """Duplicate an SDFExpr around a principal axis."""
    from ..f_rep import Rotate, Translate, Union

    count = _pop_int_alias(
        kw,
        where=where,
        names=("count", "copies", "instances"),
        required=True,
    )
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z")
    sweep_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("sweep_degrees", "angle_degrees", "angle", "sweep_radians"),
        default=360.0,
    )
    start_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("start_degrees", "start_angle", "start_radians"),
        default=0.0,
    )
    include_endpoint = _pop_bool_alias(
        kw,
        where=where,
        names=("include_endpoint", "include_end"),
        default=False,
    )
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown radial_array argument(s): {unknown}")
    if count is None or count < 1:
        raise MeshProgramError(f"{where}: count must be >= 1, got {count!r}")
    if sweep_degrees is None or sweep_degrees <= 0.0 or sweep_degrees > 360.0:
        raise MeshProgramError(
            f"{where}: sweep_degrees must satisfy 0 < value <= 360, got {sweep_degrees!r}"
        )
    if count == 1:
        angles = [float(start_degrees or 0.0)]
    else:
        full_circle = abs(float(sweep_degrees) - 360.0) <= 1e-9
        denom = count if full_circle or not include_endpoint else count - 1
        step = float(sweep_degrees) / float(max(denom, 1))
        angles = [float(start_degrees or 0.0) + step * index for index in range(count)]
    ox, oy, oz = origin
    axis_vector = _axis_vector(axis)
    accumulated: Any = None
    for degrees in angles:
        expr = Translate(expr=sdf_expr, offset=(-ox, -oy, -oz))
        expr = Rotate(expr=expr, axis=axis_vector, angle=math.radians(float(degrees)))
        expr = Translate(expr=expr, offset=(ox, oy, oz))
        accumulated = expr if accumulated is None else Union(a=accumulated, b=expr)
    return accumulated if accumulated is not None else sdf_expr


def _offset_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    """Grow or shrink an SDF by a constant signed amount."""
    from ..f_rep import Offset

    amount = _pop_length_alias(
        kw,
        where=where,
        names=("amount", "amount_cm", "distance", "distance_cm", "offset", "offset_cm"),
        required=True,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown offset argument(s): {unknown}")
    if amount is None or not math.isfinite(float(amount)):
        raise MeshProgramError(f"{where}: amount must be finite, got {amount!r}cm")
    return Offset(expr=sdf_expr, amount=float(amount))


def _shell_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    """Create a finite-thickness shell around an SDF surface."""
    from ..f_rep import Shell

    thickness = _pop_length_alias(
        kw,
        where=where,
        names=("thickness", "thickness_cm"),
        required=True,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown shell argument(s): {unknown}")
    if thickness is None or thickness <= 0.0:
        raise MeshProgramError(f"{where}: thickness must be > 0, got {thickness!r}cm")
    return Shell(expr=sdf_expr, thickness=float(thickness))


def _apply_sdf_repeat(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_repeat(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_repeat_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_repeat_grid(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_repeat_grid(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_repeat_grid_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_radial_array(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_radial_array(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_radial_array_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_scale3(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_scale3(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_scale3_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_twist(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_twist(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_twist_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_bend(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_bend(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_bend_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_taper(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_taper(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_taper_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_offset(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_offset(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_offset_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_shell(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_shell(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_shell_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _sdf_field_common_from_kw(
    kw: dict[str, Any],
    *,
    where: str,
    default_kind: str,
    default_frequency: float,
) -> tuple[str, float, int]:
    kind = _pop_string_alias(
        kw,
        where=where,
        names=("field", "noise", "kind"),
        default=default_kind,
        allowed={"gyroid", "sin", "sine", "waves"},
    )
    frequency = _pop_number_alias(
        kw,
        where=where,
        names=("frequency", "frequency_per_cm"),
        default=default_frequency,
    )
    seed = _pop_int_alias(
        kw,
        where=where,
        names=("seed",),
        default=0,
    )
    if frequency is None or frequency <= 0.0:
        raise MeshProgramError(f"{where}: frequency must be > 0, got {frequency!r}")
    return ("sin" if kind == "sine" else str(kind), float(frequency), int(seed or 0))


def _sdf_field_phase(seed: int) -> tuple[float, float, float]:
    base = float(_stable_seed("sdf_field", seed))
    return (
        (base % 997.0) * 0.017,
        (base % 1597.0) * 0.013,
        (base % 2371.0) * 0.011,
    )


def _make_sdf_noise_field(kind: str, frequency: float, seed: int) -> Any:
    import numpy as np

    phase = _sdf_field_phase(seed)

    def noise(points: Any) -> Any:
        pts = np.asarray(points, dtype=np.float64)
        x = pts[:, 0] * frequency + phase[0]
        y = pts[:, 1] * frequency + phase[1]
        z = pts[:, 2] * frequency + phase[2]
        if kind == "gyroid":
            return (
                np.sin(x) * np.cos(y)
                + np.sin(y) * np.cos(z)
                + np.sin(z) * np.cos(x)
            ) / 3.0
        return np.sin(x) * np.sin(y) * np.sin(z)

    noise.__name__ = f"{kind}_sdf_noise_seed_{seed}"
    return noise


def _make_sdf_warp_field(kind: str, frequency: float, amplitude_cm: float, seed: int) -> Any:
    import numpy as np

    phase = _sdf_field_phase(seed)

    def vector_field(points: Any) -> Any:
        pts = np.asarray(points, dtype=np.float64)
        x = pts[:, 0] * frequency + phase[0]
        y = pts[:, 1] * frequency + phase[1]
        z = pts[:, 2] * frequency + phase[2]
        if kind == "gyroid":
            return amplitude_cm * np.column_stack(
                (
                    np.sin(y) * np.cos(z),
                    np.sin(z) * np.cos(x),
                    np.sin(x) * np.cos(y),
                )
            )
        return amplitude_cm * np.column_stack(
            (
                np.sin(y + phase[2]),
                np.sin(z + phase[0]),
                np.sin(x + phase[1]),
            )
        )

    vector_field.__name__ = f"{kind}_sdf_warp_seed_{seed}"
    vector_field.lathe_amplitude_cm = float(amplitude_cm)
    return vector_field


def _displace_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    from ..f_rep import Displace

    amplitude = _pop_length_alias(
        kw,
        where=where,
        names=("amplitude", "amplitude_cm"),
        required=True,
    )
    kind, frequency, seed = _sdf_field_common_from_kw(
        kw,
        where=where,
        default_kind="gyroid",
        default_frequency=0.35,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown displace argument(s): {unknown}")
    if amplitude is None or amplitude <= 0.0:
        raise MeshProgramError(f"{where}: amplitude must be > 0, got {amplitude!r}cm")
    return Displace(
        expr=sdf_expr,
        noise=_make_sdf_noise_field(kind, frequency, seed),
        amplitude=amplitude,
    )


def _warp_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    from ..f_rep import Warp

    amplitude = _pop_length_alias(
        kw,
        where=where,
        names=("amplitude", "amplitude_cm"),
        required=True,
    )
    kind, frequency, seed = _sdf_field_common_from_kw(
        kw,
        where=where,
        default_kind="gyroid",
        default_frequency=0.25,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown warp argument(s): {unknown}")
    if amplitude is None or amplitude <= 0.0:
        raise MeshProgramError(f"{where}: amplitude must be > 0, got {amplitude!r}cm")
    return Warp(
        expr=sdf_expr,
        vector_field=_make_sdf_warp_field(kind, frequency, amplitude, seed),
    )


def _apply_sdf_displace(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_displace(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_displace_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _apply_sdf_warp(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_warp(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: target references unknown identifier {target_name!r}"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    return _Value(
        kind="sdf",
        sdf_expr=_warp_sdf_from_kw(sdf_expr, kw, where=where),
    )


def _sdf_extract_resolution_arg(value: Any, *, where: str) -> int | tuple[int, int, int]:
    if isinstance(value, list):
        if len(value) != 3:
            raise MeshProgramError(
                f"{where}: resolution list must have 3 elements, got {value!r}"
            )
        resolution = tuple(
            _int(item, where=f"{where}[{index}]")
            for index, item in enumerate(value)
        )
    else:
        resolution = _int(value, where=where)
    values = (resolution,) if isinstance(resolution, int) else resolution
    for axis, axis_resolution in zip("xyz", values, strict=False):
        if axis_resolution < 8:
            raise MeshProgramError(
                f"{where}: resolution {axis} must be >= 8, got {axis_resolution}"
            )
        if axis_resolution > 256:
            raise MeshProgramError(
                f"{where}: resolution {axis} must be <= 256 "
                f"(samples are O(X*Y*Z); split into multiple extracts if you need more), "
                f"got {axis_resolution}"
            )
    return resolution


def _sdf_extract_resolution_metadata(
    resolution: int | tuple[int, int, int],
) -> int | list[int]:
    if isinstance(resolution, int):
        return int(resolution)
    return [int(value) for value in resolution]


def _sdf_extract_scaled_resolution(
    resolution: int | tuple[int, int, int],
    *,
    scale: float,
    max_resolution: int,
) -> int | tuple[int, int, int]:
    if isinstance(resolution, int):
        return min(
            int(max_resolution),
            max(int(resolution) + 1, math.ceil(resolution * scale)),
        )
    return tuple(
        min(
            int(max_resolution),
            max(int(value) + 1, math.ceil(int(value) * scale)),
        )
        for value in resolution
    )


def _sdf_expr_connected_intent(expr: Any) -> bool:
    """Return true for SDF trees authored as one continuous body.

    This deliberately stays conservative. Union/repeat/mirror expressions can
    intentionally produce separate bodies, while transforms and deformations of
    a connected primitive should remain connected after extraction.
    """
    primitive_names = {
        "Sphere",
        "Box",
        "Cylinder",
        "Frustum",
        "Torus",
        "Capsule",
        "SegmentCapsule",
        "TaperedSegmentCapsule",
        "SegmentBox",
        "SegmentExtrudedProfile",
        "SegmentLoftedProfile",
        "RoundedSlot",
        "Cone",
        "HexPrism",
        "Ellipsoid",
        "ExtrudedPolygon",
        "RevolvedProfile",
    }
    wrapper_names = {
        "Translate",
        "Rotate",
        "Scale",
        "Scale3",
        "Twist",
        "Bend",
        "Taper",
        "Offset",
        "Displace",
        "Warp",
    }
    base_preserving_boolean_names = {
        "Subtract",
        "ChamferSubtract",
        "SmoothSubtract",
    }
    name = type(expr).__name__
    if name == "ConnectedIntent":
        return True
    if name in primitive_names:
        return True
    if name in wrapper_names:
        child = getattr(expr, "expr", None)
        return child is not None and _sdf_expr_connected_intent(child)
    if name in base_preserving_boolean_names:
        base = getattr(expr, "a", None)
        return base is not None and _sdf_expr_connected_intent(base)
    return False


def _sdf_topology_needs_connected_refinement(topology: dict[str, Any]) -> bool:
    return (
        int(topology.get("source_body_count", 0)) > 1
        or not bool(topology.get("source_watertight"))
    )


def _sdf_extract_resolution_from_cell_size(
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
    *,
    cell_size_cm: float,
    max_resolution: int,
    where: str,
) -> tuple[tuple[int, int, int], tuple[int, int, int], bool]:
    if cell_size_cm <= 0.0:
        raise MeshProgramError(
            f"{where}: cell_size must be > 0, got {cell_size_cm!r}cm"
        )
    if max_resolution < 8 or max_resolution > 256:
        raise MeshProgramError(
            f"{where}: max_resolution must be in [8, 256], got {max_resolution}"
        )
    requested: list[int] = []
    actual: list[int] = []
    clamped = False
    for axis, label in enumerate("xyz"):
        extent = float(bounds_max[axis]) - float(bounds_min[axis])
        if extent <= 0.0:
            raise MeshProgramError(
                f"{where}: bounds extent {label} must be > 0, got {extent}cm"
            )
        samples = max(8, math.ceil(extent / cell_size_cm) + 1)
        requested.append(samples)
        if samples > max_resolution:
            clamped = True
            samples = int(max_resolution)
        actual.append(samples)
    return (
        (requested[0], requested[1], requested[2]),
        (actual[0], actual[1], actual[2]),
        clamped,
    )


def _sdf_mesh_topology_metadata(vertices: Any, faces: Any) -> dict[str, Any]:
    """Return cheap truth metadata for an extracted triangle mesh."""
    face_rows = [[int(value) for value in face[:3]] for face in faces]
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for face_index, face in enumerate(face_rows):
        if len(face) != 3:
            continue
        for offset in range(3):
            left = int(face[offset])
            right = int(face[(offset + 1) % 3])
            if left == right:
                continue
            key = tuple(sorted((left, right)))
            edge_faces.setdefault(key, []).append(face_index)

    boundary_edge_count = sum(1 for attached in edge_faces.values() if len(attached) == 1)
    nonmanifold_edge_count = sum(1 for attached in edge_faces.values() if len(attached) > 2)
    edge_face_adjacency: dict[int, list[int]] = {}
    for attached in edge_faces.values():
        if len(attached) < 2:
            continue
        for face_index in attached:
            neighbors = edge_face_adjacency.setdefault(int(face_index), [])
            neighbors.extend(int(other) for other in attached if int(other) != int(face_index))

    visited: set[int] = set()
    body_count = 0
    for face_index in range(len(face_rows)):
        if face_index in visited:
            continue
        body_count += 1
        stack = [face_index]
        visited.add(face_index)
        while stack:
            current = stack.pop()
            for neighbor in edge_face_adjacency.get(current, ()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                stack.append(neighbor)

    return {
        "topology_method": "triangle_edge_incidence_v1",
        "source_vertex_count": len(vertices),
        "source_face_count": len(face_rows),
        "source_unique_edge_count": len(edge_faces),
        "source_boundary_edge_count": int(boundary_edge_count),
        "source_nonmanifold_edge_count": int(nonmanifold_edge_count),
        "source_body_count": int(body_count),
        "source_watertight": bool(
            len(face_rows) > 0
            and boundary_edge_count == 0
            and nonmanifold_edge_count == 0
        ),
    }


def _apply_sdf_extract(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Extract a triangle mesh from an SDF reference.

    Inputs:
      target: identifier bound to a kind="sdf" ``_Value``.
      resolution: optional integer grid resolution or ``[nx, ny, nz]``
        per-axis resolution (each axis >= 8).
      cell_size/cell_size_cm: optional target sample spacing in cm;
        computes per-axis resolution from the final evaluation bounds.
      bounds_min / bounds_max: optional 3-element length-unit lists
        describing the world-space evaluation box (cm). If omitted,
        Lathe infers conservative bounds for bounded SDF expressions.
      bounds_padding: optional cm padding around explicit or inferred
        bounds.
      backend/extractor: ``marching_cubes`` or ``dual_contouring``.
      iso/iso_cm: extracted isovalue in cm.

    Emits a single ``ShapePrimitive(primitive_type="sdf_mesh", ...)``
    onto the program's primitive list and returns it as the binding so
    downstream statements can reference the result if they want to.
    """
    from ..f_rep import extract_mesh

    kw = _kwargs(args, where=where)
    if "target" not in kw:
        raise MeshProgramError(f"{where}: sdf_extract(...) requires 'target'")
    target_name = _ident(kw.pop("target"), where=f"{where}.target")
    resolution_value = kw.pop("resolution", None)
    cell_size_cm = _pop_length_alias(
        kw,
        where=where,
        names=("cell_size", "cell_size_cm", "voxel_size", "voxel_size_cm", "sample_spacing", "sample_spacing_cm"),
    )
    if resolution_value is None and cell_size_cm is None:
        raise MeshProgramError(
            f"{where}: sdf_extract(...) requires resolution or cell_size"
        )
    if resolution_value is not None and cell_size_cm is not None:
        raise MeshProgramError(
            f"{where}: sdf_extract(...) accepts either resolution or cell_size, not both"
        )
    max_resolution = _pop_int_alias(
        kw,
        where=where,
        names=("max_resolution", "resolution_cap", "max_samples_per_axis"),
        default=256,
    )
    bounds_min_value = kw.pop("bounds_min", None)
    bounds_max_value = kw.pop("bounds_max", None)
    has_explicit_bounds = bounds_min_value is not None or bounds_max_value is not None
    if has_explicit_bounds and (bounds_min_value is None or bounds_max_value is None):
        raise MeshProgramError(
            f"{where}: bounds_min and bounds_max must be supplied together"
        )
    bounds_min = (
        _vec3(bounds_min_value, where=f"{where}.bounds_min")
        if bounds_min_value is not None
        else None
    )
    bounds_max = (
        _vec3(bounds_max_value, where=f"{where}.bounds_max")
        if bounds_max_value is not None
        else None
    )
    bounds_padding_cm = _pop_length_alias(
        kw,
        where=where,
        names=("bounds_padding", "bounds_padding_cm", "padding", "padding_cm"),
        default=0.0 if has_explicit_bounds else 1.0,
    )
    if bounds_padding_cm is not None and bounds_padding_cm < 0.0:
        raise MeshProgramError(
            f"{where}: bounds_padding must be >= 0, got {bounds_padding_cm}cm"
        )
    iso_cm = _pop_length_alias(
        kw,
        where=where,
        names=("iso", "iso_cm"),
        default=0.0,
    )
    extraction_backend = _pop_string_alias(
        kw,
        where=where,
        names=("backend", "extractor"),
        default="marching_cubes",
        allowed={"marching_cubes", "dual_contouring"},
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown sdf_extract(...) argument(s): {unknown}"
        )
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: sdf_extract target {target_name!r} is unknown"
        )
    sdf_expr = _resolve_sdf(bindings[target_name], where=f"{where}.target")
    sdf_expression = (
        sdf_expr.to_dict()
        if hasattr(sdf_expr, "to_dict")
        else {"op": type(sdf_expr).__name__}
    )
    from ..f_rep import estimate_bounds, resolve_extraction_backend

    if bounds_min is None or bounds_max is None:
        inferred_bounds = estimate_bounds(
            sdf_expr,
            padding=float(bounds_padding_cm or 0.0),
        )
        if inferred_bounds is None:
            raise MeshProgramError(
                f"{where}: sdf_extract(...) requires bounds_min/bounds_max "
                f"because bounds could not be inferred for {type(sdf_expr).__name__}"
            )
        bounds_min, bounds_max = inferred_bounds
        bounds_source = "inferred_sdf_expression_bounds_v1"
    elif bounds_padding_cm and float(bounds_padding_cm) > 0.0:
        pad = float(bounds_padding_cm)
        bounds_min = tuple(float(value) - pad for value in bounds_min)
        bounds_max = tuple(float(value) + pad for value in bounds_max)
        bounds_source = "explicit_author_bounds_with_padding"
    else:
        bounds_source = "explicit_author_bounds"
    for axis in range(3):
        if bounds_max[axis] <= bounds_min[axis]:
            raise MeshProgramError(
                f"{where}: bounds_max[{axis}] must be > bounds_min[{axis}], "
                f"got bounds_min={bounds_min}, bounds_max={bounds_max}"
            )

    requested_resolution_metadata: int | list[int]
    resolution_source: str
    resolution_clamped = False
    if resolution_value is not None:
        resolution = _sdf_extract_resolution_arg(
            resolution_value,
            where=f"{where}.resolution",
        )
        resolution_source = "explicit_author_resolution"
        requested_resolution_metadata = _sdf_extract_resolution_metadata(resolution)
    else:
        requested_resolution, actual_resolution, resolution_clamped = (
            _sdf_extract_resolution_from_cell_size(
                bounds_min,
                bounds_max,
                cell_size_cm=float(cell_size_cm or 0.0),
                max_resolution=int(max_resolution or 256),
                where=where,
            )
        )
        resolution = actual_resolution
        resolution_source = "cell_size_cm_adaptive"
        requested_resolution_metadata = _sdf_extract_resolution_metadata(
            requested_resolution
        )
    resolution_metadata = _sdf_extract_resolution_metadata(resolution)

    extraction_backend_info = resolve_extraction_backend(str(extraction_backend))

    def _extract_sdf_mesh_at(
        resolution_to_extract: int | tuple[int, int, int],
    ) -> tuple[Any, Any]:
        try:
            extracted_vertices, extracted_faces = extract_mesh(
                sdf_expr,
                bounds=(bounds_min, bounds_max),
                resolution=resolution_to_extract,
                backend=str(extraction_backend),
                iso=float(iso_cm or 0.0),
            )
        except ValueError as exc:
            raise MeshProgramError(f"{where}: sdf_extract backend failed: {exc}") from exc
        if len(extracted_vertices) == 0 or len(extracted_faces) == 0:
            raise MeshProgramError(
                f"{where}: sdf_extract produced an empty mesh — the SDF surface "
                f"may not intersect the bounds or resolution may be too coarse"
            )
        return extracted_vertices, extracted_faces

    vertices, faces = _extract_sdf_mesh_at(resolution)
    topology_metadata = _sdf_mesh_topology_metadata(vertices, faces)
    topology_refinement_records: list[dict[str, Any]] = []
    topology_refinement_blocked_reason: str | None = None
    topology_refinement_eligible = (
        resolution_source == "cell_size_cm_adaptive"
        and _sdf_expr_connected_intent(sdf_expr)
    )
    if (
        topology_refinement_eligible
        and _sdf_topology_needs_connected_refinement(topology_metadata)
    ):
        for attempt_index, scale in enumerate((1.2, 1.2), start=1):
            next_resolution = _sdf_extract_scaled_resolution(
                resolution,
                scale=float(scale),
                max_resolution=int(max_resolution or 256),
            )
            if next_resolution == resolution:
                topology_refinement_blocked_reason = "max_resolution_reached"
                break
            retry_record = {
                "attempt": int(attempt_index),
                "reason": "connected_intent_topology_adaptive_extract",
                "from_resolution": _sdf_extract_resolution_metadata(resolution),
                "to_resolution": _sdf_extract_resolution_metadata(next_resolution),
                "previous_source_body_count": int(
                    topology_metadata.get("source_body_count", 0)
                ),
                "previous_source_boundary_edge_count": int(
                    topology_metadata.get("source_boundary_edge_count", 0)
                ),
                "previous_source_nonmanifold_edge_count": int(
                    topology_metadata.get("source_nonmanifold_edge_count", 0)
                ),
                "previous_source_watertight": bool(
                    topology_metadata.get("source_watertight")
                ),
            }
            resolution = next_resolution
            resolution_metadata = _sdf_extract_resolution_metadata(resolution)
            vertices, faces = _extract_sdf_mesh_at(resolution)
            topology_metadata = _sdf_mesh_topology_metadata(vertices, faces)
            retry_record.update(
                {
                    "actual_source_body_count": int(
                        topology_metadata.get("source_body_count", 0)
                    ),
                    "actual_source_boundary_edge_count": int(
                        topology_metadata.get("source_boundary_edge_count", 0)
                    ),
                    "actual_source_nonmanifold_edge_count": int(
                        topology_metadata.get("source_nonmanifold_edge_count", 0)
                    ),
                    "actual_source_watertight": bool(
                        topology_metadata.get("source_watertight")
                    ),
                    "actual_source_vertex_count": int(
                        topology_metadata.get("source_vertex_count", 0)
                    ),
                    "actual_source_face_count": int(
                        topology_metadata.get("source_face_count", 0)
                    ),
                }
            )
            topology_refinement_records.append(retry_record)
            if not _sdf_topology_needs_connected_refinement(topology_metadata):
                break

    topology_refinement_metadata = {
        "topology_refinement_policy": "connected_intent_topology_adaptive_v1",
        "topology_refinement_eligible": bool(topology_refinement_eligible),
        "topology_refinement_attempted": bool(topology_refinement_records),
        "topology_refinement_records": topology_refinement_records,
    }
    if topology_refinement_blocked_reason:
        topology_refinement_metadata["topology_refinement_blocked_reason"] = (
            topology_refinement_blocked_reason
        )

    primitive_record = {
        "primitive_type": "sdf_mesh",
        "part": part,
        "center": (0.0, 0.0, 0.0),
        "mesh_vertices": [[float(v[0]), float(v[1]), float(v[2])] for v in vertices],
        "mesh_faces": [[int(f[0]), int(f[1]), int(f[2])] for f in faces],
        "tags": ["sdf", "sdf_mesh", "sdf_extract_source_mesh"],
        "blend_mode": "union",
        "component": "sdf_extract",
        "region": f"{part}.sdf_extract",
        "semantic_metadata": {
            "mesh_program_sdf_extract": {
                "operation": "mesh_program.sdf_extract",
                "target": target_name,
                "resolution": resolution_metadata,
                "requested_resolution": requested_resolution_metadata,
                "resolution_source": resolution_source,
                "resolution_clamped": bool(resolution_clamped),
                "cell_size_cm": float(cell_size_cm or 0.0),
                "max_resolution": int(max_resolution or 256),
                "bounds_min": [float(v) for v in bounds_min],
                "bounds_max": [float(v) for v in bounds_max],
                "bounds_source": bounds_source,
                "bounds_padding_cm": float(bounds_padding_cm or 0.0),
                "iso_cm": float(iso_cm or 0.0),
                "extraction_backend": dict(extraction_backend_info),
                "sdf_expression": sdf_expression,
                **topology_metadata,
                **topology_refinement_metadata,
                "materialized_as": "kernel_program.import",
            }
        },
    }
    try:
        from ..asset_quality.shape_ir_v2 import (
            ShapeOp,
            _kernel_import_record_for_single_source,
            _primitive_from_v1_record,
        )
        from ..geometry.kernel import resolve_geometry_kernel

        op = ShapeOp(
            op="mesh_program.sdf_extract",
            target=part,
            parameters={
                "target": target_name,
                "resolution": resolution_metadata,
                "requested_resolution": requested_resolution_metadata,
                "resolution_source": resolution_source,
                "resolution_clamped": bool(resolution_clamped),
                "cell_size_cm": float(cell_size_cm or 0.0),
                "max_resolution": int(max_resolution or 256),
                "bounds_min": tuple(float(v) for v in bounds_min),
                "bounds_max": tuple(float(v) for v in bounds_max),
                "bounds_source": bounds_source,
                "bounds_padding_cm": float(bounds_padding_cm or 0.0),
                "iso_cm": float(iso_cm or 0.0),
                "extraction_backend": dict(extraction_backend_info),
                **topology_metadata,
                **topology_refinement_metadata,
            },
            purpose="mesh_program.sdf_extract",
        )
        record = _kernel_import_record_for_single_source(
            op,
            source_record=primitive_record,
            geometry_kernel=resolve_geometry_kernel(),
            route="mesh_program_sdf_extract",
            asset_name="mesh_program_sdf_extract_source",
            blueprint_id="mesh_program_sdf_extract_source",
            modifier_name="mesh_program_sdf_extract_modifier",
            modifier_payload={
                "target": target_name,
                "resolution": resolution_metadata,
                "requested_resolution": requested_resolution_metadata,
                "resolution_source": resolution_source,
                "resolution_clamped": bool(resolution_clamped),
                "cell_size_cm": float(cell_size_cm or 0.0),
                "max_resolution": int(max_resolution or 256),
                "bounds_min": [float(v) for v in bounds_min],
                "bounds_max": [float(v) for v in bounds_max],
                "bounds_source": bounds_source,
                "bounds_padding_cm": float(bounds_padding_cm or 0.0),
                "iso_cm": float(iso_cm or 0.0),
                "extraction_backend": dict(extraction_backend_info),
                "sdf_expression": sdf_expression,
                **topology_metadata,
                **topology_refinement_metadata,
            },
            kernel_tag="sdf_extract_kernel_program",
        )
        primitive = _primitive_from_v1_record(record)
    except (TypeError, ValueError) as exc:
        raise MeshProgramError(f"{where}: kernel import failed for sdf_extract: {exc}") from exc
    topology_metadata = _sdf_mesh_topology_metadata(
        primitive.mesh_vertices or vertices,
        primitive.mesh_faces or faces,
    )
    _append_unique_tags(primitive, (
        "sdf_extract",
        "mesh_program_sdf_extract_kernel_program",
    ))
    _attach_mesh_program_generated_operation_history(
        primitive,
        op_name="mesh_program.sdf_extract",
        target=target_name,
        parameters={
            "target": target_name,
            "resolution": resolution_metadata,
            "requested_resolution": requested_resolution_metadata,
            "resolution_source": resolution_source,
            "resolution_clamped": bool(resolution_clamped),
            "cell_size_cm": float(cell_size_cm or 0.0),
            "max_resolution": int(max_resolution or 256),
            "bounds_min": [float(v) for v in bounds_min],
            "bounds_max": [float(v) for v in bounds_max],
            "bounds_source": bounds_source,
            "bounds_padding_cm": float(bounds_padding_cm or 0.0),
            "iso_cm": float(iso_cm or 0.0),
            "extraction_backend": dict(extraction_backend_info),
        },
        primitive_count=1,
        primitive_index=0,
    )
    metadata = dict(primitive.semantic_metadata or {})
    existing_extract_metadata = metadata.get("mesh_program_sdf_extract")
    if not isinstance(existing_extract_metadata, dict):
        existing_extract_metadata = {}
    metadata["mesh_program_sdf_extract"] = {
        **existing_extract_metadata,
        "operation": "mesh_program.sdf_extract",
        "target": target_name,
        "resolution": resolution_metadata,
        "requested_resolution": requested_resolution_metadata,
        "resolution_source": resolution_source,
        "resolution_clamped": bool(resolution_clamped),
        "cell_size_cm": float(cell_size_cm or 0.0),
        "max_resolution": int(max_resolution or 256),
        "bounds_min": [float(v) for v in bounds_min],
        "bounds_max": [float(v) for v in bounds_max],
        "bounds_source": bounds_source,
        "bounds_padding_cm": float(bounds_padding_cm or 0.0),
        "iso_cm": float(iso_cm or 0.0),
        "extraction_backend": dict(extraction_backend_info),
        "sdf_expression": sdf_expression,
        **topology_metadata,
        **topology_refinement_metadata,
        "materialized_as": "kernel_program.import",
        "kernel_program": True,
    }
    primitive.semantic_metadata = metadata
    primitives.append(primitive)
    return _Value(kind="primitive", primitive=primitive, primitives=(primitive,), bevel_target=primitive)


def _eval_wfc_module_call(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    where: str,
) -> _Value:
    """Declare a named WFC module wrapping an existing primitive binding.

    Inputs:
      name: string identifier used in adjacency rules and the solver
        output. Must be unique within the enclosing wfc_modular call.
      primitive: identifier of a previously-bound primitive let-binding.
        The module's placed copies are deep-clones of this primitive,
        translated to each cell's world-space center.
      primitives: optional list of primitive identifiers. This builds a
        multi-piece module and places every primitive for each solved
        cell.
      weight: optional float frequency hint (default 1.0). Higher values
        bias the deterministic collapse toward this module when it is
        among the allowed options for a given cell.
    """
    from ..wfc.mesh_program_ops import WFCModuleRef

    kw = _kwargs(args, where=where)
    if "name" not in kw:
        raise MeshProgramError(f"{where}: wfc_module(...) requires 'name'")
    name = _string(kw.pop("name"), where=f"{where}.name")
    has_primitive = "primitive" in kw
    has_primitives = "primitives" in kw
    if has_primitive == has_primitives:
        raise MeshProgramError(
            f"{where}: wfc_module(...) requires exactly one of "
            "'primitive' or 'primitives'"
        )
    primitive_idents: list[str] = []
    if has_primitive:
        primitive_idents.append(_ident(kw.pop("primitive"), where=f"{where}.primitive"))
    else:
        primitives_value = kw.pop("primitives")
        if not isinstance(primitives_value, list) or not primitives_value:
            raise MeshProgramError(
                f"{where}.primitives: expected a non-empty identifier list, "
                f"got {primitives_value!r}"
            )
        primitive_idents.extend(
            _ident(item, where=f"{where}.primitives[{index}]")
            for index, item in enumerate(primitives_value)
        )
    weight_value = kw.pop("weight", 1.0)
    if isinstance(weight_value, bool) or not isinstance(weight_value, (int, float)):
        raise MeshProgramError(
            f"{where}.weight: expected a number, got {weight_value!r}"
        )
    weight = float(weight_value)
    if weight <= 0.0:
        raise MeshProgramError(f"{where}: weight must be > 0, got {weight}")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown wfc_module(...) argument(s): {unknown}"
        )
    module_primitives: list[ShapePrimitive] = []
    for index, primitive_ident in enumerate(primitive_idents):
        parameter_name = "primitive" if has_primitive else f"primitives[{index}]"
        if primitive_ident not in bindings:
            raise MeshProgramError(
                f"{where}: {parameter_name!r} references unknown identifier "
                f"{primitive_ident!r}"
            )
        binding = bindings[primitive_ident]
        if binding.kind != "primitive":
            raise MeshProgramError(
                f"{where}: {parameter_name!r} must reference a primitive "
                f"let-binding, got {primitive_ident!r} "
                f"(kind={binding.kind!r})"
            )
        bound_primitives = _value_primitives(binding)
        if not bound_primitives:
            raise MeshProgramError(
                f"{where}: {parameter_name!r} binding {primitive_ident!r} "
                "has no primitives"
            )
        if has_primitive:
            module_primitives.append(bound_primitives[0])
        else:
            module_primitives.extend(bound_primitives)
    return _Value(
        kind="wfc_module",
        wfc_ref=WFCModuleRef(
            name=name,
            primitive=module_primitives[0],
            weight=weight,
            primitives=tuple(module_primitives),
        ),
    )


def _eval_wfc_rule_call(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    where: str,
) -> _Value:
    """Declare a WFC adjacency rule between two named modules.

    Inputs:
      a / b: string module names (must match a wfc_module(name:) decl).
      direction: ``"x"|"y"|"z"`` allows the pair in both signs of that
        axis (most ergonomic for "floor-to-floor along X" rules).
        Signed forms ``"+x"|"-x"|"+y"|"-y"|"+z"|"-z"`` constrain
        unilaterally.
      probability: optional float in (0, 1] recorded for v2+ entropy
        weighting; the v1 solver allows the rule unconditionally.
    """
    from ..wfc.mesh_program_ops import WFCRuleRef, _normalize_direction

    kw = _kwargs(args, where=where)
    for required in ("a", "b", "direction"):
        if required not in kw:
            raise MeshProgramError(
                f"{where}: wfc_rule(...) requires {required!r}"
            )
    name_a = _string(kw.pop("a"), where=f"{where}.a")
    name_b = _string(kw.pop("b"), where=f"{where}.b")
    direction_str = _string(kw.pop("direction"), where=f"{where}.direction")
    probability_value = kw.pop("probability", 1.0)
    if isinstance(probability_value, bool) or not isinstance(
        probability_value, (int, float)
    ):
        raise MeshProgramError(
            f"{where}.probability: expected a number, got {probability_value!r}"
        )
    probability = float(probability_value)
    if not (0.0 < probability <= 1.0):
        raise MeshProgramError(
            f"{where}: probability must be in (0, 1], got {probability}"
        )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown wfc_rule(...) argument(s): {unknown}"
        )
    try:
        directions = _normalize_direction(direction_str)
    except ValueError as exc:
        raise MeshProgramError(f"{where}.direction: {exc}") from exc
    return _Value(
        kind="wfc_rule",
        wfc_ref=WFCRuleRef(
            a=name_a, b=name_b, directions=directions, probability=probability
        ),
    )


def _apply_wfc_modular(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Run the WFC solver and append N translated module copies to primitives.

    Inputs:
      canvas_size: ``[NX, NY, NZ]`` integer cell counts. The grid is
        centered on the origin so a 10x1x10 canvas of 3m cells
        produces a 30m square footprint at Y=0.
      cell_size: length-unit literal (single scalar) — uniform cell
        edge length. v1 only supports cubic cells; per-axis sizes are
        future work.
      modules: list of ``wfc_module(...)`` references.
      adjacency: list of ``wfc_rule(...)`` references.
      seed: integer seed for the deterministic numpy RNG inside the
        solver. Same seed always produces the same dungeon.

    Side effect: every solved cell becomes one ShapePrimitive (deep
    copy of the chosen module's primitive, shifted by the cell's
    world-space offset). Primitives are tagged ``wfc_cell:gx,gy,gz``
    + ``wfc_module:<name>`` so downstream stages can audit the layout.
    """
    from ..wfc.mesh_program_ops import (
        WFCModuleRef,
        WFCRuleRef,
        solve_modular,
    )

    kw = _kwargs(args, where=where)
    for required in ("canvas_size", "cell_size", "modules", "adjacency", "seed"):
        if required not in kw:
            raise MeshProgramError(
                f"{where}: wfc_modular(...) requires {required!r}"
            )
    canvas_value = kw.pop("canvas_size")
    if not isinstance(canvas_value, list) or len(canvas_value) != 3:
        raise MeshProgramError(
            f"{where}.canvas_size: expected a 3-element integer list, "
            f"got {canvas_value!r}"
        )
    canvas_size = tuple(
        _int(v, where=f"{where}.canvas_size[{i}]") for i, v in enumerate(canvas_value)
    )
    if any(d <= 0 for d in canvas_size):
        raise MeshProgramError(
            f"{where}.canvas_size: all axes must be > 0, got {list(canvas_size)}"
        )
    cell_size_cm = _unit_to_cm(kw.pop("cell_size"), where=f"{where}.cell_size")
    if cell_size_cm <= 0.0:
        raise MeshProgramError(
            f"{where}.cell_size: must be > 0, got {cell_size_cm} cm"
        )
    modules_value = kw.pop("modules")
    adjacency_value = kw.pop("adjacency")
    seed = _int(kw.pop("seed"), where=f"{where}.seed")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown wfc_modular(...) argument(s): {unknown}"
        )
    if not isinstance(modules_value, list) or not modules_value:
        raise MeshProgramError(
            f"{where}.modules: expected a non-empty list of identifiers, "
            f"got {modules_value!r}"
        )
    modules: list[WFCModuleRef] = []
    for index, ident_value in enumerate(modules_value):
        ident_name = _ident(ident_value, where=f"{where}.modules[{index}]")
        if ident_name not in bindings:
            raise MeshProgramError(
                f"{where}.modules[{index}]: unknown identifier {ident_name!r}"
            )
        binding = bindings[ident_name]
        if binding.kind != "wfc_module" or not isinstance(
            binding.wfc_ref, WFCModuleRef
        ):
            raise MeshProgramError(
                f"{where}.modules[{index}]: {ident_name!r} must be a "
                f"wfc_module(...) binding (got kind={binding.kind!r})"
            )
        modules.append(binding.wfc_ref)
    rules: list[WFCRuleRef] = []
    if not isinstance(adjacency_value, list):
        raise MeshProgramError(
            f"{where}.adjacency: expected a list of identifiers, "
            f"got {adjacency_value!r}"
        )
    for index, ident_value in enumerate(adjacency_value):
        ident_name = _ident(ident_value, where=f"{where}.adjacency[{index}]")
        if ident_name not in bindings:
            raise MeshProgramError(
                f"{where}.adjacency[{index}]: unknown identifier {ident_name!r}"
            )
        binding = bindings[ident_name]
        if binding.kind != "wfc_rule" or not isinstance(binding.wfc_ref, WFCRuleRef):
            raise MeshProgramError(
                f"{where}.adjacency[{index}]: {ident_name!r} must be a "
                f"wfc_rule(...) binding (got kind={binding.kind!r})"
            )
        rules.append(binding.wfc_ref)

    cell_count = int(canvas_size[0] * canvas_size[1] * canvas_size[2])
    module_primitive_counts = {
        module.name: len(module.primitives or ((module.primitive,) if module.primitive else ()))
        for module in modules
    }
    try:
        emitted = solve_modular(
            canvas_size=canvas_size,
            cell_size_cm=cell_size_cm,
            modules=modules,
            rules=rules,
            seed=seed,
            part=part,
        )
    except ValueError as exc:
        raise MeshProgramError(f"{where}: {exc}") from exc

    fused = _kernel_union_legacy_primitives(
        "wfc_modular",
        source_primitives=tuple(emitted),
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="mesh_program_wfc_modular_modifier",
        modifier_payload={
            "canvas_size": [int(v) for v in canvas_size],
            "cell_size_cm": cell_size_cm,
            "module_count": len(modules),
            "module_names": [module.name for module in modules],
            "module_primitive_counts": dict(module_primitive_counts),
            "adjacency_rule_count": len(rules),
            "seed": seed,
            "cell_count": cell_count,
            "cell_primitive_count": len(emitted),
            "emitted_primitive_count": len(emitted),
            "materialized_as": "kernel_program.boolean",
        },
        tags=[
            "wfc_modular",
            "wfc_modular_assembly",
            "mesh_program_wfc_modular_kernel_program",
        ],
        kernel_tag="wfc_modular_kernel_program",
        component="wfc_modular",
        region=f"{part}.wfc_modular",
    )
    _append_unique_tags(fused, (
        "wfc_modular",
        "mesh_program_wfc_modular_kernel_program",
    ))
    metadata = dict(fused.semantic_metadata or {})
    metadata["mesh_program_wfc_modular"] = {
        "operation": "mesh_program.wfc_modular",
        "canvas_size": [int(v) for v in canvas_size],
        "cell_size_cm": cell_size_cm,
        "module_names": [module.name for module in modules],
        "module_primitive_counts": dict(module_primitive_counts),
        "adjacency_rule_count": len(rules),
        "cell_count": cell_count,
        "cell_primitive_count": len(emitted),
        "emitted_primitive_count": len(emitted),
        "materialized_as": "kernel_program.boolean",
        "kernel_program": True,
    }
    fused.semantic_metadata = metadata
    return _Value(kind="primitive", primitive=fused, primitives=(fused,), bevel_target=fused)


def _apply_translate(
    primitive: ShapePrimitive,
    args: list[dict[str, Any]],
    *,
    where: str,
) -> ShapePrimitive:
    if len(args) != 1 or args[0].get("name") is not None:
        raise MeshProgramError(
            f"{where}: .translate(...) takes a single positional 3-vector"
    )
    delta = _vec3(args[0].get("value"), where=f"{where}.offset")
    if primitive.mesh_vertices:
        primitive.mesh_vertices = [
            [
                float(vertex[0]) + delta[0],
                float(vertex[1]) + delta[1],
                float(vertex[2]) + delta[2],
            ]
            for vertex in primitive.mesh_vertices
        ]
        _apply_mesh_vertex_bounds(primitive)
        return primitive
    cx, cy, cz = primitive.center
    primitive.center = (cx + delta[0], cy + delta[1], cz + delta[2])
    return primitive


def _apply_translate_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    """Wrap an SDFExpr in ``Translate(...)`` so chained ``.translate([...])``
    on an unextracted SDF moves it through modeling space without
    materialising the mesh.
    """
    from ..f_rep import Translate

    if len(args) != 1 or args[0].get("name") is not None:
        raise MeshProgramError(
            f"{where}: .translate(...) takes a single positional 3-vector"
        )
    delta = _vec3(args[0].get("value"), where=f"{where}.offset")
    return Translate(expr=sdf_expr, offset=(delta[0], delta[1], delta[2]))


def _axis_vector(axis: str) -> tuple[float, float, float]:
    if axis == "x":
        return (1.0, 0.0, 0.0)
    if axis == "y":
        return (0.0, 1.0, 0.0)
    return (0.0, 0.0, 1.0)


def _number_arg(value: Any, *, where: str) -> float:
    if isinstance(value, dict) and value.get("type") == "unary" and value.get("op") == "-":
        return -_number_arg(value.get("value"), where=where)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise MeshProgramError(f"{where}: expected a number, got {value!r}")


def _bool_arg(value: Any, *, where: str) -> bool:
    if isinstance(value, bool):
        return bool(value)
    raise MeshProgramError(f"{where}: expected a bool, got {value!r}")


def _optional_origin_arg(
    value: Any,
    *,
    where: str,
    default: tuple[float, float, float],
) -> tuple[float, float, float]:
    if value is None:
        return default
    return _vec3(value, where=where)


def _angle_degrees_arg(
    value: Any,
    *,
    where: str,
    raw_unit: str = "deg",
) -> float:
    if isinstance(value, dict) and value.get("type") == "unary" and value.get("op") == "-":
        return -_angle_degrees_arg(value.get("value"), where=where, raw_unit=raw_unit)
    if isinstance(value, dict) and value.get("type") == "unit":
        unit = value.get("unit")
        raw = float(value.get("value", 0.0))
        if unit == "deg":
            return raw
        if unit == "rad":
            return math.degrees(raw)
        raise MeshProgramError(
            f"{where}: expected deg/rad angle unit, got {unit!r}"
        )
    raw = _number_arg(value, where=where)
    if raw_unit == "rad":
        return math.degrees(raw)
    return raw


def _rotation_degrees_from_kwargs(
    kw: dict[str, Any],
    *,
    where: str,
) -> float:
    names = [name for name in ("degrees", "radians", "angle") if name in kw]
    if len(names) != 1:
        raise MeshProgramError(
            f"{where}: .rotate(...) requires exactly one of 'degrees', "
            f"'radians', or 'angle'"
        )
    name = names[0]
    value = kw.pop(name)
    if name == "radians":
        return _angle_degrees_arg(value, where=f"{where}.{name}", raw_unit="rad")
    if name == "angle" and not (
        isinstance(value, dict) and value.get("type") == "unit"
    ):
        raise MeshProgramError(
            f"{where}.angle: use a deg/rad unit literal or the explicit "
            f"'degrees'/'radians' argument"
        )
    return _angle_degrees_arg(value, where=f"{where}.{name}", raw_unit="deg")


def _rotation_matrix(
    axis: str,
    degrees: float,
) -> list[list[float]]:
    angle = math.radians(float(degrees))
    c = math.cos(angle)
    s = math.sin(angle)
    if axis == "x":
        return [
            [1.0, 0.0, 0.0],
            [0.0, c, -s],
            [0.0, s, c],
        ]
    if axis == "y":
        return [
            [c, 0.0, s],
            [0.0, 1.0, 0.0],
            [-s, 0.0, c],
        ]
    return [
        [c, -s, 0.0],
        [s, c, 0.0],
        [0.0, 0.0, 1.0],
    ]


def _baked_mesh_primitive(
    source: ShapePrimitive,
    *,
    vertices: Any,
    faces: Any,
    tags: list[str],
    where: str,
) -> ShapePrimitive:
    import copy as _copy

    import numpy as np
    import trimesh

    verts_arr = np.asarray(vertices, dtype=np.float64)
    faces_arr = np.asarray(faces, dtype=np.int64)
    if verts_arr.ndim != 2 or verts_arr.shape[1] != 3:
        raise MeshProgramError(
            f"{where}: transformed mesh must have Nx3 vertices, got "
            f"shape={verts_arr.shape}"
        )
    if faces_arr.ndim != 2 or faces_arr.shape[1] != 3:
        raise MeshProgramError(
            f"{where}: transformed mesh must have Mx3 faces, got "
            f"shape={faces_arr.shape}"
        )
    if len(verts_arr) == 0 or len(faces_arr) == 0:
        raise MeshProgramError(f"{where}: transform produced an empty mesh")

    mesh = trimesh.Trimesh(vertices=verts_arr, faces=faces_arr, process=False)
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    with suppress(Exception):
        mesh.fix_normals()

    baked = ShapePrimitive(
        primitive_type="sdf_mesh",
        part=source.part,
        center=(0.0, 0.0, 0.0),
        tags=list(source.tags) + list(tags),
        component=source.component,
        region=source.region,
        blend_mode=source.blend_mode,
        mesh_vertices=[
            [float(v[0]), float(v[1]), float(v[2])] for v in mesh.vertices
        ],
        mesh_faces=[[int(f[0]), int(f[1]), int(f[2])] for f in mesh.faces],
        boolean_seam_groups=_copy.deepcopy(source.boolean_seam_groups),
        bevel_seam_groups=_copy.deepcopy(source.bevel_seam_groups),
    )
    _apply_mesh_vertex_bounds(baked)
    return baked


def _primitive_mesh_arrays(
    primitive: ShapePrimitive,
    *,
    where: str,
) -> tuple[Any, Any]:
    import numpy as np

    from ..exact_solids import _primitive_mesh as _exact_primitive_mesh

    mesh = _exact_primitive_mesh(primitive)
    if mesh is None or len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise MeshProgramError(f"{where}: source primitive produced an empty mesh")
    return (
        np.asarray(mesh.vertices, dtype=np.float64).copy(),
        np.asarray(mesh.faces, dtype=np.int64).copy(),
    )


def _apply_rotate(
    primitive: ShapePrimitive,
    args: list[dict[str, Any]],
    *,
    where: str,
) -> ShapePrimitive:
    import numpy as np

    kw = _kwargs(args, where=where)
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z")
    degrees = _rotation_degrees_from_kwargs(kw, where=where)
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=primitive.center,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .rotate(...) argument(s): {unknown}")

    vertices, faces = _primitive_mesh_arrays(primitive, where=where)
    pivot = np.asarray(origin, dtype=np.float64)
    matrix = np.asarray(_rotation_matrix(axis, degrees), dtype=np.float64)
    transformed = (vertices - pivot) @ matrix.T + pivot
    return _baked_mesh_primitive(
        primitive,
        vertices=transformed,
        faces=faces,
        tags=["mesh_program_rotate", f"mesh_program_rotate_axis_{axis}"],
        where=where,
    )


def _apply_scale(
    primitive: ShapePrimitive,
    args: list[dict[str, Any]],
    *,
    where: str,
) -> ShapePrimitive:
    import numpy as np

    kw = _kwargs(args, where=where)
    if "factor" not in kw:
        raise MeshProgramError(f"{where}: .scale(...) requires 'factor'")
    factor = _number_arg(kw.pop("factor"), where=f"{where}.factor")
    if factor <= 0.0:
        raise MeshProgramError(f"{where}.factor: must be > 0, got {factor}")
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=primitive.center,
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .scale(...) argument(s): {unknown}")

    vertices, faces = _primitive_mesh_arrays(primitive, where=where)
    pivot = np.asarray(origin, dtype=np.float64)
    transformed = (vertices - pivot) * factor + pivot
    return _baked_mesh_primitive(
        primitive,
        vertices=transformed,
        faces=faces,
        tags=["mesh_program_scale"],
        where=where,
    )


def _apply_mirror(
    primitive: ShapePrimitive,
    args: list[dict[str, Any]],
    *,
    where: str,
) -> ShapePrimitive:
    import numpy as np

    kw = _kwargs(args, where=where)
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x")
    include_source = _bool_arg(
        kw.pop("include_source", True),
        where=f"{where}.include_source",
    )
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .mirror(...) argument(s): {unknown}")

    vertices, faces = _primitive_mesh_arrays(primitive, where=where)
    reflected = vertices.copy()
    axis_index = _axis_to_index(axis)
    reflected[:, axis_index] = (
        2.0 * float(origin[axis_index]) - reflected[:, axis_index]
    )
    reflected_faces = faces[:, [0, 2, 1]]
    if include_source:
        out_vertices = np.concatenate([vertices, reflected], axis=0)
        out_faces = np.concatenate(
            [faces, reflected_faces + len(vertices)],
            axis=0,
        )
    else:
        out_vertices = reflected
        out_faces = reflected_faces

    tags = [
        "mesh_program_mirror",
        f"mesh_program_mirror_axis_{axis}",
    ]
    if include_source:
        tags.append("mesh_program_mirror_include_source")
    return _baked_mesh_primitive(
        primitive,
        vertices=out_vertices,
        faces=out_faces,
        tags=tags,
        where=where,
    )


def _apply_rotate_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    from ..f_rep import Rotate, Translate

    kw = _kwargs(args, where=where)
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z")
    degrees = _rotation_degrees_from_kwargs(kw, where=where)
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .rotate(...) argument(s): {unknown}")

    ox, oy, oz = origin
    expr = Translate(expr=sdf_expr, offset=(-ox, -oy, -oz))
    expr = Rotate(expr=expr, axis=_axis_vector(axis), angle=math.radians(degrees))
    return Translate(expr=expr, offset=(ox, oy, oz))


def _apply_scale_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    from ..f_rep import Scale, Translate

    kw = _kwargs(args, where=where)
    if "factor" not in kw:
        raise MeshProgramError(f"{where}: .scale(...) requires 'factor'")
    factor = _number_arg(kw.pop("factor"), where=f"{where}.factor")
    if factor <= 0.0:
        raise MeshProgramError(f"{where}.factor: must be > 0, got {factor}")
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .scale(...) argument(s): {unknown}")

    ox, oy, oz = origin
    expr = Translate(expr=sdf_expr, offset=(-ox, -oy, -oz))
    expr = Scale(expr=expr, factor=factor)
    return Translate(expr=expr, offset=(ox, oy, oz))


def _scale3_factors_from_kw(kw: dict[str, Any], *, where: str) -> tuple[float, float, float]:
    factor_names = ("factors", "factor", "scale", "scale_xyz")
    present = [name for name in factor_names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in factor_names)} may be supplied"
        )
    if present:
        raw_factors = kw.pop(present[0])
        factors = _number_vec3(raw_factors, where=f"{where}.factors")
    else:
        x = _pop_number_alias(
            kw,
            where=where,
            names=("x", "sx", "scale_x", "factor_x"),
            required=True,
        )
        y = _pop_number_alias(
            kw,
            where=where,
            names=("y", "sy", "scale_y", "factor_y"),
            required=True,
        )
        z = _pop_number_alias(
            kw,
            where=where,
            names=("z", "sz", "scale_z", "factor_z"),
            required=True,
        )
        factors = (float(x or 0.0), float(y or 0.0), float(z or 0.0))
    if any(factor <= 0.0 for factor in factors):
        raise MeshProgramError(f"{where}: scale3 factors must be > 0, got {factors!r}")
    return (float(factors[0]), float(factors[1]), float(factors[2]))


def _scale3_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    from ..f_rep import Scale3, Translate

    factors = _scale3_factors_from_kw(kw, where=where)
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .scale3(...) argument(s): {unknown}")

    ox, oy, oz = origin
    expr = Translate(expr=sdf_expr, offset=(-ox, -oy, -oz))
    expr = Scale3(expr=expr, factors=factors)
    return Translate(expr=expr, offset=(ox, oy, oz))


def _apply_scale3_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _scale3_sdf_from_kw(sdf_expr, kw, where=where)


def _twist_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    from ..f_rep import Translate, Twist

    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    rate = _pop_number_alias(
        kw,
        where=where,
        names=("radians_per_cm", "rate", "twist_rate"),
    )
    angle_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("angle_degrees", "angle", "angle_radians", "radians", "twist_degrees", "twist", "twist_radians"),
    )
    height = _pop_length_alias(
        kw,
        where=where,
        names=("height", "height_cm", "length", "length_cm"),
    )
    if rate is not None and angle_degrees is not None:
        raise MeshProgramError(
            f"{where}: use either radians_per_cm/rate or angle+height, not both"
        )
    if rate is None:
        if angle_degrees is None:
            raise MeshProgramError(
                f"{where}: twist requires radians_per_cm/rate or angle+height"
            )
        if height is None or height <= 0.0:
            raise MeshProgramError(f"{where}: angle-based twist requires height > 0")
        rate = math.radians(float(angle_degrees)) / float(height)
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown twist argument(s): {unknown}")

    ox, oy, oz = origin
    expr = Translate(expr=sdf_expr, offset=(-ox, -oy, -oz))
    expr = Twist(expr=expr, axis=axis, radians_per_cm=float(rate))
    return Translate(expr=expr, offset=(ox, oy, oz))


def _apply_twist_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _twist_sdf_from_kw(sdf_expr, kw, where=where)


def _bend_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    from ..f_rep import Bend, Translate

    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x")
    bend_axis = _axis_arg(
        kw.pop("bend_axis", None),
        where=f"{where}.bend_axis",
        default="y",
    )
    if axis == bend_axis:
        raise MeshProgramError(f"{where}: axis and bend_axis must differ")
    rate = _pop_number_alias(
        kw,
        where=where,
        names=("radians_per_cm", "rate", "bend_rate"),
    )
    angle_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("angle_degrees", "angle", "angle_radians", "radians", "bend_degrees", "bend", "bend_radians"),
    )
    length = _pop_length_alias(
        kw,
        where=where,
        names=("length", "length_cm", "height", "height_cm"),
    )
    if rate is not None and angle_degrees is not None:
        raise MeshProgramError(
            f"{where}: use either radians_per_cm/rate or angle+length, not both"
        )
    if rate is None:
        if angle_degrees is None:
            raise MeshProgramError(
                f"{where}: bend requires radians_per_cm/rate or angle+length"
            )
        if length is None or length <= 0.0:
            raise MeshProgramError(f"{where}: angle-based bend requires length > 0")
        rate = math.radians(float(angle_degrees)) / float(length)
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown bend argument(s): {unknown}")

    ox, oy, oz = origin
    expr = Translate(expr=sdf_expr, offset=(-ox, -oy, -oz))
    expr = Bend(expr=expr, axis=axis, bend_axis=bend_axis, radians_per_cm=float(rate))
    return Translate(expr=expr, offset=(ox, oy, oz))


def _apply_bend_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _bend_sdf_from_kw(sdf_expr, kw, where=where)


def _taper_sdf_from_kw(sdf_expr: Any, kw: dict[str, Any], *, where: str) -> Any:
    from ..f_rep import Taper, Translate

    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    raw_scale = kw.pop("scale", None)
    if raw_scale is not None:
        if isinstance(raw_scale, list):
            if len(raw_scale) != 2:
                raise MeshProgramError(f"{where}.scale: expected a number or [start, end]")
            start_scale = _number_arg(raw_scale[0], where=f"{where}.scale[0]")
            end_scale = _number_arg(raw_scale[1], where=f"{where}.scale[1]")
        else:
            start_scale = _pop_number_alias(
                kw,
                where=where,
                names=("start_scale", "scale_start"),
                default=1.0,
            )
            end_scale = _number_arg(raw_scale, where=f"{where}.scale")
    else:
        start_scale = _pop_number_alias(
            kw,
            where=where,
            names=("start_scale", "scale_start"),
            default=1.0,
        )
        end_scale = _pop_number_alias(
            kw,
            where=where,
            names=("end_scale", "scale_end"),
            required=True,
        )
    if start_scale is None or start_scale <= 0.0:
        raise MeshProgramError(f"{where}: start_scale must be > 0, got {start_scale!r}")
    if end_scale is None or end_scale <= 0.0:
        raise MeshProgramError(f"{where}: end_scale must be > 0, got {end_scale!r}")
    height = _pop_length_alias(
        kw,
        where=where,
        names=("height", "height_cm", "length", "length_cm"),
        required=True,
    )
    if height is None or height <= 0.0:
        raise MeshProgramError(f"{where}: height must be > 0, got {height!r}cm")
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown taper argument(s): {unknown}")

    ox, oy, oz = origin
    expr = Translate(expr=sdf_expr, offset=(-ox, -oy, -oz))
    expr = Taper(
        expr=expr,
        axis=axis,
        start_scale=float(start_scale),
        end_scale=float(end_scale),
        height=float(height),
    )
    return Translate(expr=expr, offset=(ox, oy, oz))


def _apply_taper_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _taper_sdf_from_kw(sdf_expr, kw, where=where)


def _apply_mirror_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    from ..f_rep import Mirror, Translate

    kw = _kwargs(args, where=where)
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="x")
    include_source = _bool_arg(
        kw.pop("include_source", True),
        where=f"{where}.include_source",
    )
    if not include_source:
        raise MeshProgramError(
            f"{where}.include_source: SDF mirror is a symmetry operator; "
            f"reflected-only SDF output is not supported"
        )
    origin = _optional_origin_arg(
        kw.pop("origin", None),
        where=f"{where}.origin",
        default=(0.0, 0.0, 0.0),
    )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .mirror(...) argument(s): {unknown}")

    ox, oy, oz = origin
    expr = Translate(expr=sdf_expr, offset=(-ox, -oy, -oz))
    expr = Mirror(expr=expr, axis=axis)
    return Translate(expr=expr, offset=(ox, oy, oz))


def _apply_repeat_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _repeat_sdf_from_kw(sdf_expr, kw, where=where)


def _apply_offset_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _offset_sdf_from_kw(sdf_expr, kw, where=where)


def _apply_shell_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _shell_sdf_from_kw(sdf_expr, kw, where=where)


def _apply_displace_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _displace_sdf_from_kw(sdf_expr, kw, where=where)


def _apply_warp_sdf(
    sdf_expr: Any, args: list[dict[str, Any]], *, where: str
) -> Any:
    kw = _kwargs(args, where=where)
    return _warp_sdf_from_kw(sdf_expr, kw, where=where)


def _apply_sdf_boolean_method(
    sdf_expr: Any,
    method: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    where: str,
) -> Any:
    from ..f_rep import (
        ChamferIntersect,
        ChamferSubtract,
        ChamferUnion,
        Intersect,
        SmoothIntersect,
        SmoothSubtract,
        SmoothUnion,
        Subtract,
        Union,
    )

    kw = _kwargs(args, where=where)
    other_value = _pop_first_kw(
        kw,
        ("other", "b", "cutter", "source", "right"),
    )
    if other_value is None:
        raise MeshProgramError(
            f"{where}: .{method}(...) requires other, b, cutter, source, or right"
        )
    other_name = _ident(other_value, where=f"{where}.other")
    if other_name not in bindings:
        raise MeshProgramError(
            f"{where}: other references unknown SDF identifier {other_name!r}"
        )
    other = _resolve_sdf(bindings[other_name], where=f"{where}.other")
    if method in {"smooth_union", "smooth_intersect", "smooth_subtract", "smooth_blend"}:
        k_cm = _pop_length_alias(
            kw,
            where=where,
            names=("k", "blend", "blend_radius", "blend_radius_cm"),
            required=True,
        )
        if kw:
            unknown = sorted(kw.keys())
            raise MeshProgramError(f"{where}: unknown .{method}(...) argument(s): {unknown}")
        if k_cm is None or k_cm < 0.0:
            raise MeshProgramError(f"{where}: k must be >= 0, got {k_cm!r}cm")
        if method in {"smooth_union", "smooth_blend"}:
            return SmoothUnion(a=sdf_expr, b=other, k=float(k_cm))
        if method == "smooth_intersect":
            return SmoothIntersect(a=sdf_expr, b=other, k=float(k_cm))
        return SmoothSubtract(a=sdf_expr, b=other, k=float(k_cm))
    if method in {
        "chamfer_union",
        "chamfer_add",
        "chamfer_intersect",
        "chamfer_intersection",
        "chamfer_subtract",
        "chamfer_difference",
    }:
        radius_cm = _pop_sdf_chamfer_radius(kw, where=where)
        if kw:
            unknown = sorted(kw.keys())
            raise MeshProgramError(f"{where}: unknown .{method}(...) argument(s): {unknown}")
        if method in {"chamfer_union", "chamfer_add"}:
            return ChamferUnion(a=sdf_expr, b=other, radius=float(radius_cm))
        if method in {"chamfer_intersect", "chamfer_intersection"}:
            return ChamferIntersect(a=sdf_expr, b=other, radius=float(radius_cm))
        return ChamferSubtract(a=sdf_expr, b=other, radius=float(radius_cm))
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .{method}(...) argument(s): {unknown}")
    if method in {"union", "add"}:
        return Union(a=sdf_expr, b=other)
    if method in {"intersect", "intersection"}:
        return Intersect(a=sdf_expr, b=other)
    if method in {"subtract", "difference"}:
        return Subtract(a=sdf_expr, b=other)
    raise MeshProgramError(f"{where}: unsupported SDF boolean method '.{method}(...)'")


def _eval_expr(
    expr: Any,
    bindings: dict[str, _Value],
    *,
    part: str,
    where: str,
    primitives: list[ShapePrimitive] | None = None,
) -> _Value:
    if isinstance(expr, dict) and expr.get("type") == "ident":
        name = _ident(expr.get("name"), where=where)
        if name not in bindings:
            raise MeshProgramError(f"{where}: unknown identifier {name!r}")
        return bindings[name]
    if isinstance(expr, dict) and expr.get("type") == "call":
        callee = expr.get("name")
        args = list(expr.get("args") or [])
        constructor = _SOLID_CONSTRUCTORS.get(callee or "")
        if constructor is not None:
            constructed = constructor(args, part=part, where=f"{where}.{callee}")
            return _primitive_value(constructed)
        sdf_constructor = _SDF_CONSTRUCTORS.get(callee or "")
        if sdf_constructor is not None:
            sdf_expr = sdf_constructor(args, part=part, where=f"{where}.{callee}")
            return _Value(kind="sdf", sdf_expr=sdf_expr)
        ref_constructor = _WFC_REF_CONSTRUCTORS.get(callee or "")
        if ref_constructor is not None:
            return ref_constructor(args, bindings, where=f"{where}.{callee}")
        point_generator = _POINT_GENERATORS.get(callee or "")
        if point_generator is not None:
            cloud = point_generator(args, where=f"{where}.{callee}")
            return _Value(kind="point_set", points=cloud)
        point_binding = _POINT_BINDING_CONSTRUCTORS.get(callee or "")
        if point_binding is not None:
            return point_binding(args, bindings, where=f"{where}.{callee}")
        if primitives is not None:
            compound_op = _COMPOUND_OPS.get(callee or "")
            if compound_op is not None:
                return compound_op(
                    args,
                    bindings,
                    primitives=primitives,
                    part=part,
                    where=f"{where}.{callee}",
                )
        raise MeshProgramError(
            f"{where}: unsupported call {callee!r} "
            f"(supported: {sorted(list(_SOLID_CONSTRUCTORS) + list(_SDF_CONSTRUCTORS) + list(_WFC_REF_CONSTRUCTORS) + list(_POINT_GENERATORS) + list(_POINT_BINDING_CONSTRUCTORS) + list(_COMPOUND_OPS))})"
        )
    if isinstance(expr, dict) and expr.get("type") == "method_call":
        receiver = _eval_expr(
            expr.get("receiver"),
            bindings,
            part=part,
            where=f"{where}.receiver",
            primitives=primitives,
        )
        method = expr.get("method")
        method_args = list(expr.get("args") or [])
        if receiver.kind == "sdf" and receiver.sdf_expr is not None:
            if method == "displace":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_displace_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.displace",
                    ),
                )
            if method == "translate":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_translate_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.translate",
                    ),
                )
            if method == "rotate":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_rotate_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.rotate",
                    ),
                )
            if method == "scale":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_scale_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.scale",
                    ),
                )
            if method in {"scale3", "scale_xyz"}:
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_scale3_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.{method}",
                    ),
                )
            if method == "twist":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_twist_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.twist",
                    ),
                )
            if method == "bend":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_bend_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.bend",
                    ),
                )
            if method == "taper":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_taper_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.taper",
                    ),
                )
            if method == "mirror":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_mirror_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.mirror",
                    ),
                )
            if method == "offset":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_offset_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.offset",
                    ),
                )
            if method == "repeat":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_repeat_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.repeat",
                    ),
                )
            if method in {"repeat_grid", "grid"}:
                kw = _kwargs(method_args, where=f"{where}.{method}")
                return _Value(
                    kind="sdf",
                    sdf_expr=_repeat_grid_sdf_from_kw(
                        receiver.sdf_expr,
                        kw,
                        where=f"{where}.{method}",
                    ),
                )
            if method in {"radial_array", "polar_array", "radial_repeat"}:
                kw = _kwargs(method_args, where=f"{where}.{method}")
                return _Value(
                    kind="sdf",
                    sdf_expr=_radial_array_sdf_from_kw(
                        receiver.sdf_expr,
                        kw,
                        where=f"{where}.{method}",
                    ),
                )
            if method == "shell":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_shell_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.shell",
                    ),
                )
            if method == "warp":
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_warp_sdf(
                        receiver.sdf_expr,
                        method_args,
                        where=f"{where}.warp",
                    ),
                )
            if str(method or "") in {
                "add",
                "chamfer_add",
                "chamfer_difference",
                "chamfer_intersect",
                "chamfer_intersection",
                "chamfer_subtract",
                "chamfer_union",
                "difference",
                "intersect",
                "intersection",
                "smooth_blend",
                "smooth_intersect",
                "smooth_subtract",
                "smooth_union",
                "subtract",
                "union",
            }:
                return _Value(
                    kind="sdf",
                    sdf_expr=_apply_sdf_boolean_method(
                        receiver.sdf_expr,
                        str(method or ""),
                        method_args,
                        bindings,
                        where=f"{where}.{method}",
                    ),
                )
            if str(method or "") in _SCATTER_METHODS:
                return _apply_scatter_method(
                    receiver,
                    str(method or ""),
                    method_args,
                    bindings,
                    primitives=primitives,
                    part=part,
                    where=f"{where}.{method}",
                )
            raise MeshProgramError(
                f"{where}: unsupported SDF method '.{method}(...)' "
                f"(supported: add, chamfer_add, chamfer_difference, chamfer_intersect, "
                f"chamfer_subtract, chamfer_union, difference, displace, intersect, mirror, offset, "
                f"bend, radial_array, repeat, repeat_grid, rotate, scale, scale3, scale_xyz, scatter, shell, "
                f"smooth_blend, smooth_intersect, smooth_subtract, smooth_union, "
                f"subtract, taper, translate, twist, union, warp)"
            )
        if receiver.kind != "primitive" or receiver.primitive is None:
            raise MeshProgramError(
                f"{where}: method calls only apply to primitive or SDF bindings"
            )
        if method == "translate":
            return _apply_transform_method(
                receiver,
                "translate",
                method_args,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.translate",
            )
        if method == "rotate":
            return _apply_transform_method(
                receiver,
                "rotate",
                method_args,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.rotate",
            )
        if method == "scale":
            return _apply_transform_method(
                receiver,
                "scale",
                method_args,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.scale",
            )
        if method == "mirror":
            mirror_args = list(method_args)
            named_args = {
                str(arg.get("name") or "")
                for arg in mirror_args
                if isinstance(arg, dict) and arg.get("name") is not None
            }
            if "axis" not in named_args:
                mirror_args.append({"name": "axis", "value": "x"})
            if "include_source" not in named_args:
                mirror_args.append({"name": "include_source", "value": True})
            return _apply_compound_method(
                receiver,
                "mirror",
                mirror_args,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.mirror",
            )
        boolean_op = _BOOLEAN_METHOD_ALIASES.get(str(method or ""))
        if boolean_op is not None:
            return _apply_boolean_method(
                receiver,
                boolean_op,
                method_args,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.{method}",
            )
        if str(method or "") in _HULL_METHODS:
            return _apply_hull_method(
                receiver,
                str(method or ""),
                method_args,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.{method}",
            )
        if str(method or "") in _EDGE_TREATMENT_METHODS:
            named_args = {
                str(arg.get("name") or "")
                for arg in method_args
                if isinstance(arg, dict) and arg.get("name") is not None
            }
            if (
                str(method or "") in {"bevel", "chamfer"}
                and not ({"edge_class", "seam_group"} & named_args)
                and _COMPOUND_METHOD_ALIASES.get(str(method or "")) is not None
            ):
                return _apply_compound_method(
                    receiver,
                    str(method or ""),
                    method_args,
                    bindings,
                    primitives=primitives,
                    part=part,
                    where=f"{where}.{method}",
                )
            return _apply_edge_treatment_method(
                receiver,
                str(method or ""),
                method_args,
                where=f"{where}.{method}",
            )
        if str(method or "") in _SCATTER_METHODS:
            return _apply_scatter_method(
                receiver,
                str(method or ""),
                method_args,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.{method}",
            )
        compound_op = _COMPOUND_METHOD_ALIASES.get(str(method or ""))
        if compound_op is not None:
            return _apply_compound_method(
                receiver,
                str(method or ""),
                method_args,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.{method}",
            )
        raise MeshProgramError(
            f"{where}: unsupported method '.{method}(...)' "
            f"(supported: {', '.join(_supported_primitive_method_names())})"
        )
    raise MeshProgramError(f"{where}: cannot evaluate expression {expr!r}")


def _append_boolean_operand_primitives(
    *,
    op: str,
    body_value: _Value,
    operand_value: _Value,
    primitives: list[ShapePrimitive] | None,
    part: str,
    seam_group: str | None,
) -> _Value:
    body_primitives = _value_primitives(body_value)
    operand_primitives = _value_primitives(operand_value)
    if not body_primitives or not operand_primitives:
        raise MeshProgramError("boolean operands have no primitive payload")
    for body in body_primitives:
        body.part = _authored_part_for_primitive(body, fallback=part)
        if str(body.blend_mode or "union") == "union":
            body.blend_mode = "union"
        if primitives is not None and body not in primitives:
            primitives.append(body)
    for operand in operand_primitives:
        operand.part = _authored_part_for_primitive(operand, fallback=part)
        if op == "union":
            if str(operand.blend_mode or "union") == "union":
                operand.blend_mode = "union"
        else:
            operand.blend_mode = op
        if seam_group is not None and str(operand.blend_mode or "union") == op:
            tag_boolean_seam_group(operand, seam_group=seam_group, target_part=part)
        if primitives is not None and operand not in primitives:
            primitives.append(operand)
    primary = _primary_primitive(body_primitives) or body_primitives[0]
    bevel_target = _primary_primitive(operand_primitives) or operand_primitives[-1]
    return _Value(
        kind="primitive",
        primitive=primary,
        bevel_target=bevel_target,
        primitives=(*body_primitives, *operand_primitives),
    )


def _annotate_mesh_let_binding(value: _Value, binding_name: str) -> None:
    binding_name = str(binding_name or "")
    if not binding_name:
        return
    for primitive in _value_primitives(value):
        metadata = dict(primitive.semantic_metadata or {})
        metadata.setdefault("mesh_program_source_binding", binding_name)
        v2_metadata = metadata.get("shape_ir_v2")
        v2_metadata = dict(v2_metadata) if isinstance(v2_metadata, dict) else {}
        v2_metadata.setdefault("mesh_program_source_binding", binding_name)
        metadata["shape_ir_v2"] = v2_metadata
        primitive.semantic_metadata = metadata


def _authored_part_for_primitive(primitive: ShapePrimitive, *, fallback: str) -> str:
    metadata = primitive.semantic_metadata if isinstance(primitive.semantic_metadata, dict) else {}
    binding = str(metadata.get("mesh_program_source_binding") or "").strip()
    if binding:
        return binding
    return str(primitive.part or fallback)


def _apply_deferred_boolean_op(
    op: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive] | None,
    part: str,
    where: str,
) -> _Value:
    """Record source-level boolean intent without eagerly fusing geometry.

    ``mesh_program`` booleans are the authoring syntax for the canonical
    ShapePrimitive chain consumed by ``compile_explicit_surface_mesh``. They
    should append operands and seam-group metadata, then defer real kernel
    fusion to output materialization / shape compilation. Eagerly fusing every
    boolean during lowering makes chained hard-surface assets repeatedly
    boolean mesh-backed outputs, which can stall on otherwise valid sources.
    """
    kw = _kwargs(args, where=where)
    target_key = next((key for key in ("a", "target") if key in kw), "")
    if not target_key:
        raise MeshProgramError(f"{where}: boolean(...) requires 'a' or 'target'")
    _target_name, body_value = _pop_value_parameter(
        kw,
        bindings,
        name=target_key,
        allowed_kinds=("primitive",),
        part=part,
        where=where,
    )
    _source_names, source_primitives = _pop_source_primitives_parameter(
        kw,
        bindings,
        where=where,
        part=part,
    )
    seam_group = kw.pop("seam_group", None)
    if seam_group is not None:
        seam_group = _string(seam_group, where=f"{where}.seam_group")
    # ``blend_mode`` used to be accepted by the eager v2 path. The source
    # boolean op itself remains authoritative, but keep this argument accepted
    # so existing sources do not fail while we defer execution.
    kw.pop("blend_mode", None)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown boolean(...) argument(s): {unknown}")
    return _append_boolean_operand_primitives(
        op=op,
        body_value=body_value,
        operand_value=_primitive_value(source_primitives),
        primitives=primitives,
        part=part,
        seam_group=seam_group,
    )


def _apply_boolean_method(
    receiver: _Value,
    op: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive] | None,
    part: str,
    where: str,
) -> _Value:
    if primitives is None:
        raise MeshProgramError(f"{where}: boolean methods require a mesh program output list")
    kw = _kwargs(args, where=where)
    operand_key = ""
    operand_expr: Any = None
    for candidate in (
        "sources",
        "cutters",
        "other",
        "operand",
        "b",
        "with",
        "source",
        "cutter",
    ):
        if candidate not in kw:
            continue
        operand_key = candidate
        operand_expr = kw.pop(candidate)
        break
    if operand_key == "":
        raise MeshProgramError(
            f"{where}: .{op}(...) requires one of 'other', 'operand', 'b', "
            "'with', 'source', 'cutter', 'sources', or 'cutters'"
        )
    seam_group = kw.pop("seam_group", None)
    if seam_group is not None:
        seam_group = _string(seam_group, where=f"{where}.seam_group")
    passthrough_args: list[dict[str, Any]] = []
    if "blend_mode" in kw:
        passthrough_args.append({"name": "blend_mode", "value": kw.pop("blend_mode")})
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .{op}(...) argument(s): {unknown}")
    if receiver.kind != "primitive":
        raise MeshProgramError(f"{where}: receiver must be a primitive binding")

    receiver_name = f"__receiver_{op}"
    while receiver_name in bindings:
        receiver_name = f"_{receiver_name}"
    local_bindings = dict(bindings)
    local_bindings[receiver_name] = receiver
    source_arg_name = (
        "sources"
        if operand_key in {"sources", "cutters"}
        or isinstance(operand_expr, list)
        else "source"
    )
    rewritten_args = [
        {"name": "target", "value": receiver_name},
        {"name": source_arg_name, "value": operand_expr},
    ]
    if seam_group is not None:
        rewritten_args.append({"name": "seam_group", "value": seam_group})
    rewritten_args.extend(passthrough_args)
    return _apply_deferred_boolean_op(
        op,
        rewritten_args,
        local_bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_hull_method(
    receiver: _Value,
    method: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive] | None,
    part: str,
    where: str,
) -> _Value:
    if method != "hull":
        raise MeshProgramError(f"{where}: unsupported hull method '.{method}(...)'")
    if receiver.kind != "primitive":
        raise MeshProgramError(f"{where}: receiver must be primitive geometry")
    if primitives is None:
        raise MeshProgramError(f"{where}: hull methods require a mesh program output list")
    kw = _kwargs(args, where=where)
    source_exprs: list[Any] = []
    if "sources" in kw:
        raw_sources = kw.pop("sources")
        if not isinstance(raw_sources, list) or not raw_sources:
            raise MeshProgramError(f"{where}.sources: expected a non-empty primitive list")
        source_exprs.extend(raw_sources)
    for key in ("source", "other", "operand", "with"):
        if key in kw:
            source_exprs.append(kw.pop(key))
    passthrough_args = [
        {"name": str(name), "value": value}
        for name, value in kw.items()
    ]
    if not source_exprs:
        raise MeshProgramError(
            f"{where}: .hull(...) requires 'source', 'other', 'with', or 'sources'"
        )

    receiver_name = "__receiver_hull"
    while receiver_name in bindings:
        receiver_name = f"_{receiver_name}"
    local_bindings = dict(bindings)
    local_bindings[receiver_name] = receiver
    return _apply_op_hull(
        [
            {"name": "sources", "value": [receiver_name, *source_exprs]},
            *passthrough_args,
        ],
        local_bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _pop_first_kw(kw: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in kw:
            return kw.pop(name)
    return None


def _source_record_matches_seam_group(record: dict[str, Any], edge_class: str) -> bool:
    for group in record.get("boolean_seam_groups") or []:
        if isinstance(group, dict) and str(group.get("name") or "") == edge_class:
            return True
    metadata = record.get("semantic_metadata")
    if isinstance(metadata, dict):
        shape_metadata = metadata.get("shape_ir_v2")
        if isinstance(shape_metadata, dict):
            for group in shape_metadata.get("boolean_seam_groups") or []:
                if isinstance(group, dict) and str(group.get("name") or "") == edge_class:
                    return True
    return False


def _primitive_matches_seam_group(primitive: ShapePrimitive, edge_class: str) -> bool:
    return any(
        isinstance(group, dict) and str(group.get("name") or "") == edge_class
        for group in primitive.boolean_seam_groups
    )


def _bevel_target_for_edge_class(value: _Value, edge_class: str) -> ShapePrimitive | None:
    preferred = value.bevel_target or value.primitive
    if preferred is not None and _primitive_matches_seam_group(preferred, edge_class):
        return preferred
    for primitive in _value_primitives(value):
        if _primitive_matches_seam_group(primitive, edge_class):
            return primitive
    return preferred


def _propagate_edge_treatment_to_source_records(
    records: list[Any],
    *,
    edge_class: str,
    width_cm: float,
    segments: int,
    method: str,
) -> int:
    propagated = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        metadata = record.get("semantic_metadata")
        if isinstance(metadata, dict):
            nested = metadata.get("source_shape_primitives")
            if isinstance(nested, list):
                propagated += _propagate_edge_treatment_to_source_records(
                    nested,
                    edge_class=edge_class,
                    width_cm=width_cm,
                    segments=segments,
                    method=method,
                )
        if not _source_record_matches_seam_group(record, edge_class):
            continue
        modifier = {
            "width_cm": float(width_cm),
            "segments": int(segments),
            "target_seam_groups": [edge_class],
            "source_operation": f"mesh_program.{method}",
            "operation_id": f"mesh_program.{method}:{edge_class}",
        }
        record["v2_polybevel_modifier"] = modifier
        bevel_group = {
            "width_cm": float(width_cm),
            "segments": int(segments),
            "target_seam_groups": [edge_class],
        }
        groups = [group for group in list(record.get("bevel_seam_groups") or []) if isinstance(group, dict)]
        groups.append(bevel_group)
        record["bevel_seam_groups"] = groups
        if isinstance(metadata, dict):
            shape_metadata = metadata.get("shape_ir_v2")
            if isinstance(shape_metadata, dict):
                shape_metadata["v2_polybevel_modifier"] = modifier
                shape_metadata["bevel_seam_groups"] = list(groups)
                shape_metadata["bevel_seam_group_count"] = len(groups)
        propagated += 1
    return propagated


def _apply_edge_treatment_method(
    receiver: _Value,
    method: str,
    args: list[dict[str, Any]],
    *,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    edge_class = _pop_first_kw(kw, ("edge_class", "seam_group", "edge", "target_seam_group"))
    if edge_class is None:
        raise MeshProgramError(
            f"{where}: .{method}(...) requires edge_class or seam_group"
        )
    edge_class = _string(edge_class, where=f"{where}.edge_class")
    width_value = _pop_first_kw(
        kw,
        (
            "radius",
            "radius_cm",
            "width",
            "width_cm",
            "bevel_width",
            "bevel_width_cm",
            "chamfer_width",
            "chamfer_width_cm",
        ),
    )
    if width_value is None:
        raise MeshProgramError(
            f"{where}: .{method}(...) requires radius or width"
        )
    radius_cm = _unit_to_cm(width_value, where=f"{where}.radius")
    segments_default = 1 if method == "chamfer" else 4
    segments = _int(kw.pop("segments", segments_default), where=f"{where}.segments")
    if method == "chamfer":
        segments = 1
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown .{method}(...) argument(s): {unknown}")
    target_primitive = _bevel_target_for_edge_class(receiver, edge_class)
    if target_primitive is None:
        raise MeshProgramError(f"{where}: receiver has no primitive to attach edge treatment to")
    declared_seam_groups = {
        str(group.get("name"))
        for group in target_primitive.boolean_seam_groups
        if isinstance(group, dict)
    }
    if edge_class not in declared_seam_groups:
        raise MeshProgramError(
            f"{where}: edge_class {edge_class!r} does not match any seam_group "
            "on the receiver; declare it via boolean(seam_group:) or .subtract(seam_group:)"
        )
    _fillet_edge_helper(
        target_primitive,
        edge_class=edge_class,
        radius_cm=radius_cm,
        segments=segments,
    )
    _attach_mesh_program_operation_history(
        target_primitive,
        source=target_primitive,
        op_name="op_chamfer" if method == "chamfer" else "op_bevel",
        modifier_name="v2_polybevel_modifier",
        modifier_payload={
            "width_cm": radius_cm,
            "segments": segments,
            "seam_group": edge_class,
            "target_seam_groups": [edge_class],
        },
        feature_primitive_count=1,
        component="edge_treatment",
        region=f"{target_primitive.part or 'body'}.edge_treatment",
    )
    metadata = target_primitive.semantic_metadata
    if isinstance(metadata, dict):
        raw_sources = metadata.get("source_shape_primitives")
        if isinstance(raw_sources, list):
            propagated = _propagate_edge_treatment_to_source_records(
                raw_sources,
                edge_class=edge_class,
                width_cm=radius_cm,
                segments=segments,
                method=method,
            )
            if propagated:
                metadata["edge_treatment_source_record_propagation"] = {
                    "schema": "lathe.mesh_program.edge_treatment_source_record_propagation.v1",
                    "edge_class": edge_class,
                    "width_cm": float(radius_cm),
                    "segments": int(segments),
                    "method": method,
                    "source_record_count": int(propagated),
                }
                target_primitive.semantic_metadata = metadata
    return receiver


def _apply_compound_method(
    receiver: _Value,
    method: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive] | None,
    part: str,
    where: str,
) -> _Value:
    if receiver.kind != "primitive":
        raise MeshProgramError(f"{where}: receiver must be primitive geometry")
    if primitives is None:
        raise MeshProgramError(f"{where}: compound methods require a mesh program output list")
    op_name = _COMPOUND_METHOD_ALIASES[method]
    conflicting = [
        str(arg.get("name"))
        for arg in args
        if arg.get("name") in {"target", "source", "sources"}
    ]
    if conflicting:
        raise MeshProgramError(
            f"{where}: .{method}(...) uses the receiver as target; "
            f"remove explicit {sorted(conflicting)} argument(s)"
        )
    receiver_name = f"__receiver_{method}"
    while receiver_name in bindings:
        receiver_name = f"_{receiver_name}"
    local_bindings = dict(bindings)
    local_bindings[receiver_name] = receiver
    injected_args = [{"name": "target", "value": receiver_name}, *args]
    return _COMPOUND_OPS[op_name](
        injected_args,
        local_bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_transform_method(
    receiver: _Value,
    method: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive] | None,
    part: str,
    where: str,
) -> _Value:
    if receiver.kind != "primitive":
        raise MeshProgramError(f"{where}: receiver must be primitive geometry")
    if primitives is None:
        raise MeshProgramError(f"{where}: transform methods require a mesh program output list")
    source_primitives = _value_primitives(receiver)
    if not source_primitives:
        raise MeshProgramError(f"{where}: receiver has no primitive geometry")

    injected_args: list[dict[str, Any]] = []
    if method == "translate":
        if len(args) != 1 or args[0].get("name") is not None:
            raise MeshProgramError(
                f"{where}: .translate(...) takes a single positional 3-vector"
            )
        delta = _vec3(args[0].get("value"), where=f"{where}.offset")
        injected_args.append({"name": "translation", "value": [*delta]})
    elif method == "rotate":
        kw = _kwargs(args, where=where)
        axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="z")
        degrees = _rotation_degrees_from_kwargs(kw, where=where)
        origin_supplied = "origin" in kw
        if len(source_primitives) > 1 and not origin_supplied:
            return _replace_value_primitives(
                receiver,
                [
                    _apply_rotate(
                        primitive,
                        args,
                        where=where,
                    )
                    for primitive in source_primitives
                ],
            )
        origin = _optional_origin_arg(
            kw.pop("origin", None),
            where=f"{where}.origin",
            default=source_primitives[0].center,
        )
        if kw:
            unknown = sorted(kw.keys())
            raise MeshProgramError(f"{where}: unknown .rotate(...) argument(s): {unknown}")
        injected_args.extend(
            (
                {"name": "rotation_axis", "value": axis},
                {"name": "rotation_degrees", "value": float(degrees)},
                {"name": "origin", "value": [*origin]},
            )
        )
    elif method == "scale":
        kw = _kwargs(args, where=where)
        if "factor" not in kw:
            raise MeshProgramError(f"{where}: .scale(...) requires 'factor'")
        factor = _number_arg(kw.pop("factor"), where=f"{where}.factor")
        if factor <= 0.0:
            raise MeshProgramError(f"{where}.factor: must be > 0, got {factor}")
        origin_supplied = "origin" in kw
        if len(source_primitives) > 1 and not origin_supplied:
            return _replace_value_primitives(
                receiver,
                [
                    _apply_scale(
                        primitive,
                        args,
                        where=where,
                    )
                    for primitive in source_primitives
                ],
            )
        origin = _optional_origin_arg(
            kw.pop("origin", None),
            where=f"{where}.origin",
            default=source_primitives[0].center,
        )
        if kw:
            unknown = sorted(kw.keys())
            raise MeshProgramError(f"{where}: unknown .scale(...) argument(s): {unknown}")
        injected_args.extend(
            (
                {"name": "scale", "value": float(factor)},
                {"name": "origin", "value": [*origin]},
            )
        )
    else:
        raise MeshProgramError(f"{where}: unsupported transform method '.{method}(...)'")

    receiver_name = f"__receiver_{method}"
    while receiver_name in bindings:
        receiver_name = f"_{receiver_name}"
    local_bindings = dict(bindings)
    local_bindings[receiver_name] = receiver
    return _apply_sop_transform(
        [{"name": "target", "value": receiver_name}, *injected_args],
        local_bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_scatter_method(
    receiver: _Value,
    method: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive] | None,
    part: str,
    where: str,
) -> _Value:
    if method != "scatter":
        raise MeshProgramError(f"{where}: unsupported scatter method '.{method}(...)'")
    if receiver.kind not in {"primitive", "sdf"}:
        raise MeshProgramError(f"{where}: receiver must be primitive geometry or SDF geometry")
    if primitives is None:
        raise MeshProgramError(f"{where}: scatter methods require a mesh program output list")
    conflicting = [
        str(arg.get("name"))
        for arg in args
        if arg.get("name") == "primitive"
    ]
    if conflicting:
        raise MeshProgramError(
            f"{where}: .scatter(...) uses the receiver as primitive; "
            f"remove explicit {sorted(conflicting)} argument(s)"
        )
    receiver_name = "__receiver_scatter"
    while receiver_name in bindings:
        receiver_name = f"_{receiver_name}"
    local_bindings = dict(bindings)
    local_bindings[receiver_name] = receiver
    injected_args = [{"name": "primitive", "value": receiver_name}, *args]
    return _apply_scatter(
        injected_args,
        local_bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_boolean(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    op = _ident(kw.pop("op", None), where=f"{where}.op")
    if op not in _BOOLEAN_OPS:
        raise MeshProgramError(
            f"{where}: boolean(op:) must be one of {sorted(_BOOLEAN_OPS)}, got {op!r}"
        )
    return _apply_deferred_boolean_op(
        op,
        [{"name": key, "value": value} for key, value in kw.items()],
        bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_fillet_edge(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    where: str,
) -> None:
    kw = _kwargs(args, where=where)
    target_name = _ident(kw.pop("target", None), where=f"{where}.target")
    edge_class = _string(kw.pop("edge_class", None), where=f"{where}.edge_class")
    radius_value = kw.pop("radius", None)
    if radius_value is None:
        raise MeshProgramError(f"{where}: fillet_edge(radius:) is required")
    radius_cm = _unit_to_cm(radius_value, where=f"{where}.radius")
    segments_value = kw.pop("segments", 4)
    segments = _int(segments_value, where=f"{where}.segments")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown fillet_edge(...) argument(s): {unknown}"
        )
    if target_name not in bindings:
        raise MeshProgramError(
            f"{where}: fillet_edge(target:) references unknown identifier {target_name!r}"
        )
    binding = bindings[target_name]
    target_primitive = _bevel_target_for_edge_class(binding, edge_class)
    if target_primitive is None:
        raise MeshProgramError(
            f"{where}: fillet_edge(target: {target_name!r}) has no primitive to attach to"
        )
    declared_seam_groups = {
        str(group.get("name"))
        for group in target_primitive.boolean_seam_groups
        if isinstance(group, dict)
    }
    if edge_class not in declared_seam_groups:
        raise MeshProgramError(
            f"{where}: edge_class {edge_class!r} does not match any seam_group "
            f"on target {target_name!r}; declare it via boolean(seam_group:)"
        )
    _fillet_edge_helper(
        target_primitive,
        edge_class=edge_class,
        radius_cm=radius_cm,
        segments=segments,
    )
    _attach_mesh_program_operation_history(
        target_primitive,
        source=target_primitive,
        op_name="op_bevel",
        modifier_name="v2_polybevel_modifier",
        modifier_payload={
            "width_cm": radius_cm,
            "segments": segments,
            "seam_group": edge_class,
            "target_seam_groups": [edge_class],
        },
        feature_primitive_count=1,
        component="edge_treatment",
        region=f"{target_primitive.part or 'body'}.edge_treatment",
    )


_SOLID_CONSTRUCTORS: dict[str, Any] = {
    "box": _eval_box_call,
    "solid_box": _eval_solid_box_call,
    "panel": _eval_solid_panel_call,
    "solid_panel": _eval_solid_panel_call,
    "rail": _eval_solid_rail_call,
    "solid_rail": _eval_solid_rail_call,
    "prism": _eval_solid_prism_call,
    "solid_prism": _eval_solid_prism_call,
    "cylinder": _eval_solid_cylinder_call,
    "solid_cylinder": _eval_solid_cylinder_call,
    "rounded_box": _eval_solid_rounded_box_call,
    "solid_rounded_box": _eval_solid_rounded_box_call,
    "revolved_profile": _eval_solid_revolved_profile_call,
    "solid_revolved_profile": _eval_solid_revolved_profile_call,
    "extruded_profile": _eval_solid_extruded_profile_call,
    "solid_extruded_profile": _eval_solid_extruded_profile_call,
    "sweep": _eval_sop_sweep_call,
    "sop_sweep": _eval_sop_sweep_call,
    "swept_profile": _eval_swept_profile_call,
    "solid_swept_profile": _eval_swept_profile_call,
    "loft": _eval_sop_loft_call,
    "sop_loft": _eval_sop_loft_call,
    "lofted_solid": _eval_lofted_solid_call,
    "solid_lofted_solid": _eval_lofted_solid_call,
    "polywire": _eval_sop_polywire_call,
    "sop_polywire": _eval_sop_polywire_call,
    "helical_sweep": _eval_helical_sweep_call,
    "sop_helical_sweep": _eval_helical_sweep_call,
    "solid_curve_extruded_profile": _eval_solid_curve_extruded_profile_call,
    "solid_curve_revolved_profile": _eval_solid_curve_revolved_profile_call,
    "solid_curve_swept_profile": _eval_solid_curve_swept_profile_call,
    "solid_curve_lofted_solid": _eval_solid_curve_lofted_solid_call,
    "spring": _eval_solid_spring_call,
    "solid_spring": _eval_solid_spring_call,
    "tube": _eval_solid_tube_call,
    "solid_tube": _eval_solid_tube_call,
    "curved_tube": _eval_solid_curved_tube_call,
    "solid_curved_tube": _eval_solid_curved_tube_call,
    "gear": _eval_solid_gear_call,
    "solid_gear": _eval_solid_gear_call,
    "sphere": _eval_solid_sphere_call,
    "solid_sphere": _eval_solid_sphere_call,
    "torus": _eval_solid_torus_call,
    "solid_torus": _eval_solid_torus_call,
    "subdivision_box": _eval_solid_subdivision_box_call,
    "solid_subdivision_box": _eval_solid_subdivision_box_call,
    "threaded_cylinder": _eval_solid_threaded_cylinder_call,
    "solid_threaded_cylinder": _eval_solid_threaded_cylinder_call,
    "flange": _eval_solid_flange_call,
    "solid_flange": _eval_solid_flange_call,
    "hinge": _eval_solid_hinge_call,
    "solid_hinge": _eval_solid_hinge_call,
    "handle": _eval_solid_handle_call,
    "solid_handle": _eval_solid_handle_call,
    "capsule": _eval_solid_capsule_call,
    "solid_capsule": _eval_solid_capsule_call,
    "structural_beam": _eval_solid_structural_beam_call,
    "solid_structural_beam": _eval_solid_structural_beam_call,
    "ladder_frame": _eval_solid_ladder_frame_call,
    "solid_ladder_frame": _eval_solid_ladder_frame_call,
    "truss_frame": _eval_solid_truss_frame_call,
    "solid_truss_frame": _eval_solid_truss_frame_call,
    "perforated_panel": _eval_solid_perforated_panel_call,
    "solid_perforated_panel": _eval_solid_perforated_panel_call,
    "ribbed_panel": _eval_solid_ribbed_panel_call,
    "solid_ribbed_panel": _eval_solid_ribbed_panel_call,
    "louver_panel": _eval_solid_louver_panel_call,
    "solid_louver_panel": _eval_solid_louver_panel_call,
    "cga_facade": _eval_solid_cga_facade_call,
    "solid_cga_facade": _eval_solid_cga_facade_call,
    "terrain_patch": _eval_solid_terrain_patch_call,
    "solid_terrain_patch": _eval_solid_terrain_patch_call,
    "branching_tree": _eval_solid_branching_tree_call,
    "solid_branching_tree": _eval_solid_branching_tree_call,
    "sdf_metaball_cluster": _eval_solid_sdf_metaball_cluster_call,
    "solid_sdf_metaball_cluster": _eval_solid_sdf_metaball_cluster_call,
    "wfc_modular_assembly": _eval_solid_wfc_modular_assembly_call,
    "solid_wfc_modular_assembly": _eval_solid_wfc_modular_assembly_call,
    "vegetation_trunk": _eval_vegetation_trunk_call,
    "terrain_heightfield": _eval_terrain_heightfield_call,
}

# SDF / F-Rep primitive constructors return an ``SDFExpr`` rather than a
# ``ShapePrimitive``. The lowering layer wraps them in a kind="sdf"
# ``_Value`` so ``.translate(...)`` chaining and ``sdf_smooth_union(...)``
# composition can manipulate the implicit form before extraction.
_SDF_CONSTRUCTORS: dict[str, Any] = {
    "sdf_sphere": _eval_sdf_sphere_call,
    "sdf_capsule": _eval_sdf_capsule_call,
    "sdf_capsule_between": _eval_sdf_capsule_between_call,
    "sdf_capsule_segment": _eval_sdf_capsule_between_call,
    "sdf_segment_capsule": _eval_sdf_capsule_between_call,
    "sdf_tapered_capsule_between": _eval_sdf_capsule_between_call,
    "sdf_tapered_segment_capsule": _eval_sdf_capsule_between_call,
    "sdf_tube_path": _eval_sdf_tube_path_call,
    "sdf_cable_path": _eval_sdf_tube_path_call,
    "sdf_vine_path": _eval_sdf_tube_path_call,
    "sdf_arc_tube": _eval_sdf_arc_tube_call,
    "sdf_pipe_elbow": _eval_sdf_arc_tube_call,
    "sdf_curved_handle": _eval_sdf_arc_tube_call,
    "sdf_beam_between": _eval_sdf_beam_between_call,
    "sdf_rect_beam_between": _eval_sdf_beam_between_call,
    "sdf_strut_between": _eval_sdf_beam_between_call,
    "sdf_rail_between": _eval_sdf_beam_between_call,
    "sdf_beam_path": _eval_sdf_beam_path_call,
    "sdf_rail_path": _eval_sdf_beam_path_call,
    "sdf_strut_path": _eval_sdf_beam_path_call,
    "sdf_swept_profile_between": _eval_sdf_swept_profile_between_call,
    "sdf_profile_sweep_between": _eval_sdf_swept_profile_between_call,
    "sdf_sweep_between": _eval_sdf_swept_profile_between_call,
    "sdf_swept_profile_path": _eval_sdf_swept_profile_path_call,
    "sdf_profile_sweep_path": _eval_sdf_swept_profile_path_call,
    "sdf_sweep_path": _eval_sdf_swept_profile_path_call,
    "sdf_lofted_profile_between": _eval_sdf_lofted_profile_between_call,
    "sdf_profile_loft_between": _eval_sdf_lofted_profile_between_call,
    "sdf_loft_between": _eval_sdf_lofted_profile_between_call,
    "sdf_box": _eval_sdf_box_call,
    "sdf_rounded_box": _eval_sdf_rounded_box_call,
    "sdf_plane": _eval_sdf_plane_call,
    "sdf_cylinder": _eval_sdf_cylinder_call,
    "sdf_frustum": _eval_sdf_frustum_call,
    "sdf_capped_cone": _eval_sdf_frustum_call,
    "sdf_rounded_cylinder": _eval_sdf_rounded_cylinder_call,
    "sdf_rounded_slot": _eval_sdf_rounded_slot_call,
    "sdf_slot": _eval_sdf_rounded_slot_call,
    "sdf_extruded_profile": _eval_sdf_extruded_profile_call,
    "sdf_extruded_polygon": _eval_sdf_extruded_profile_call,
    "sdf_profile_prism": _eval_sdf_extruded_profile_call,
    "sdf_profile_cut": _eval_sdf_extruded_profile_call,
    "sdf_revolved_profile": _eval_sdf_revolved_profile_call,
    "sdf_profile_revolve": _eval_sdf_revolved_profile_call,
    "sdf_lathe_profile": _eval_sdf_revolved_profile_call,
    "sdf_gear": _eval_sdf_gear_call,
    "sdf_spur_gear": _eval_sdf_gear_call,
    "sdf_involute_gear": _eval_sdf_gear_call,
    "sdf_threaded_cylinder": _eval_sdf_threaded_cylinder_call,
    "sdf_threaded_rod": _eval_sdf_threaded_cylinder_call,
    "sdf_bolt_shank": _eval_sdf_threaded_cylinder_call,
    "sdf_threaded_hole": _eval_sdf_threaded_cylinder_call,
    "sdf_tapped_hole": _eval_sdf_threaded_cylinder_call,
    "sdf_flange": _eval_sdf_flange_call,
    "sdf_bolt_flange": _eval_sdf_flange_call,
    "sdf_gusset": _eval_sdf_gusset_call,
    "sdf_triangular_gusset": _eval_sdf_gusset_call,
    "sdf_tapered_rib": _eval_sdf_tapered_rib_call,
    "sdf_trapezoid_rib": _eval_sdf_tapered_rib_call,
    "sdf_dovetail_slot": _eval_sdf_tapered_rib_call,
    "sdf_panel_line": _eval_sdf_panel_line_call,
    "sdf_panel_groove": _eval_sdf_panel_line_call,
    "sdf_groove": _eval_sdf_panel_line_call,
    "sdf_fastener_grid": _eval_sdf_fastener_grid_call,
    "sdf_bolt_grid": _eval_sdf_fastener_grid_call,
    "sdf_vent_slats": _eval_sdf_vent_slats_call,
    "sdf_slat_stack": _eval_sdf_vent_slats_call,
    "sdf_panel_frame": _eval_sdf_panel_frame_call,
    "sdf_frame": _eval_sdf_panel_frame_call,
    "sdf_mount_plate": _eval_sdf_mount_plate_call,
    "sdf_bolt_plate": _eval_sdf_mount_plate_call,
    "sdf_socket": _eval_sdf_socket_call,
    "sdf_recessed_socket": _eval_sdf_socket_call,
    "sdf_countersunk_hole": _eval_sdf_countersunk_hole_call,
    "sdf_countersink_hole": _eval_sdf_countersunk_hole_call,
    "sdf_countersink": _eval_sdf_countersunk_hole_call,
    "sdf_torus": _eval_sdf_torus_call,
    "sdf_cone": _eval_sdf_cone_call,
    "sdf_hex_prism": _eval_sdf_hex_prism_call,
    "sdf_ellipsoid": _eval_sdf_ellipsoid_call,
}

# WFC modular constructors return declarative refs (kind="wfc_module" /
# kind="wfc_rule") rather than primitives. They consume bindings because
# wfc_module(primitive: <ident>) needs to resolve the underlying primitive
# at declaration time. The eventual wfc_modular(...) call collects refs,
# runs the WFC solver, and emits N translated copies onto the program's
# primitive list — that's where the 5th paradigm meets the existing kernel.
_WFC_REF_CONSTRUCTORS: dict[str, Any] = {
    "wfc_module": _eval_wfc_module_call,
    "wfc_rule": _eval_wfc_rule_call,
}


def _mesh_vertex_bounds(
    primitive: ShapePrimitive,
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    vertices = primitive.mesh_vertices or []
    if not vertices:
        return None
    xs = [float(vertex[0]) for vertex in vertices]
    ys = [float(vertex[1]) for vertex in vertices]
    zs = [float(vertex[2]) for vertex in vertices]
    return (
        (min(xs), min(ys), min(zs)),
        (max(xs), max(ys), max(zs)),
    )


def _apply_mesh_vertex_bounds(primitive: ShapePrimitive) -> None:
    bounds = _mesh_vertex_bounds(primitive)
    if bounds is None:
        return
    bounds_min, bounds_max = bounds
    primitive.center = (
        (bounds_min[0] + bounds_max[0]) * 0.5,
        (bounds_min[1] + bounds_max[1]) * 0.5,
        (bounds_min[2] + bounds_max[2]) * 0.5,
    )
    primitive.extents = (
        bounds_max[0] - bounds_min[0],
        bounds_max[1] - bounds_min[1],
        bounds_max[2] - bounds_min[2],
    )


def _bbox_center(primitive: ShapePrimitive) -> tuple[float, float, float]:
    bounds = _mesh_vertex_bounds(primitive)
    if bounds is not None:
        bounds_min, bounds_max = bounds
        return (
            (bounds_min[0] + bounds_max[0]) * 0.5,
            (bounds_min[1] + bounds_max[1]) * 0.5,
            (bounds_min[2] + bounds_max[2]) * 0.5,
        )
    return primitive.center


def _bbox_extents(primitive: ShapePrimitive) -> tuple[float, float, float]:
    """Approximate axis-aligned extents for any solid primitive.

    The compound ops (fastener_grid, vent_slats, trim_band) need a bbox
    to position their stamped/subtracted children. ``box`` carries it
    directly; cylinders and extruded profiles derive it from
    radius/height/profile-polygon. Other primitive types fall back to a
    generic 1cm cube so authors get a non-zero result rather than a
    zero-dimension crash, but the primary supported targets are the
    bbox-trivial primitives.
    """
    pt = primitive.primitive_type
    if pt in {"box", "subdivision_box"}:
        if primitive.extents is None:
            raise MeshProgramError(
                f"primitive of type {pt!r} is missing 'extents'"
            )
        return primitive.extents
    if pt == "cylinder":
        radius = float(primitive.radius or 0.0)
        height = float(primitive.height or 0.0)
        axis = primitive.axis or "y"
        if axis == "x":
            return (height, 2.0 * radius, 2.0 * radius)
        if axis == "z":
            return (2.0 * radius, 2.0 * radius, height)
        return (2.0 * radius, height, 2.0 * radius)
    if pt == "sphere":
        radius = float(primitive.radius or 0.0)
        return (2.0 * radius, 2.0 * radius, 2.0 * radius)
    if pt == "extruded_profile":
        polygon = primitive.profile_polygon or []
        if not polygon:
            raise MeshProgramError(
                "extruded_profile primitive has no profile_polygon"
            )
        xs = [float(p[0]) for p in polygon]
        ys = [float(p[1]) for p in polygon]
        u_extent = max(xs) - min(xs)
        v_extent = max(ys) - min(ys)
        sweep = float(primitive.extrude_height or 0.0)
        axis = primitive.axis or "z"
        if axis == "x":
            return (sweep, u_extent, v_extent)
        if axis == "y":
            return (u_extent, sweep, v_extent)
        return (u_extent, v_extent, sweep)
    if pt == "revolved_profile":
        profile = primitive.profile_points or []
        if not profile:
            raise MeshProgramError(
                "revolved_profile primitive has no profile_points"
            )
        axial = [float(p[0]) for p in profile]
        radial = [max(0.0, float(p[1])) for p in profile]
        height = max(axial) - min(axial)
        diameter = 2.0 * max(radial)
        axis = primitive.axis or "y"
        if axis == "x":
            return (height, diameter, diameter)
        if axis == "z":
            return (diameter, diameter, height)
        return (diameter, height, diameter)
    if pt == "trim_band":
        normal_axis = primitive.axis or "z"
        length_axis = primitive.length_axis or _tangent_axis_defaults(normal_axis)[0]
        width_axis = primitive.width_axis or next(
            axis for axis in ("x", "y", "z") if axis not in {normal_axis, length_axis}
        )
        values = [0.0, 0.0, 0.0]
        values[_axis_to_index(normal_axis)] = max(float(primitive.thickness or 0.0), 1e-6)
        values[_axis_to_index(length_axis)] = max(float(primitive.length or 0.0), 1e-6)
        values[_axis_to_index(width_axis)] = max(float(primitive.width or 0.0), 1e-6)
        return (values[0], values[1], values[2])
    if pt == "vent_slats":
        normal_axis = primitive.axis or primitive.normal_axis or "z"
        row_axis = primitive.row_axis or _tangent_axis_defaults(normal_axis)[0]
        length_axis = primitive.length_axis or next(
            axis for axis in ("x", "y", "z") if axis not in {normal_axis, row_axis}
        )
        length = max(float(primitive.length or 0.0), 1e-6)
        height = max(float(primitive.height or primitive.width or 0.0), 1e-6)
        thickness = max(
            float(primitive.thickness or primitive.slat_depth or primitive.depth or 0.0),
            1e-6,
        )
        if primitive.slat_centers:
            extents = [thickness, thickness, thickness]
            extents[_axis_to_index(length_axis)] = length
            extents[_axis_to_index(row_axis)] = height
            mins: list[tuple[float, float, float]] = []
            maxs: list[tuple[float, float, float]] = []
            half = (extents[0] * 0.5, extents[1] * 0.5, extents[2] * 0.5)
            for center in primitive.slat_centers:
                mins.append((center[0] - half[0], center[1] - half[1], center[2] - half[2]))
                maxs.append((center[0] + half[0], center[1] + half[1], center[2] + half[2]))
            return tuple(
                max(max(point[axis] for point in maxs) - min(point[axis] for point in mins), 1e-6)
                for axis in range(3)
            )
        count = max(int(primitive.slat_count or 1), 1)
        spacing = max(float(primitive.slat_spacing or 0.0), height)
        values = [thickness, thickness, thickness]
        values[_axis_to_index(normal_axis)] = thickness
        values[_axis_to_index(row_axis)] = max(height, (count - 1) * spacing + height)
        values[_axis_to_index(length_axis)] = length
        return (values[0], values[1], values[2])
    if pt == "fastener_grid":
        normal_axis = primitive.axis or primitive.normal_axis or "z"
        row_axis = primitive.row_axis or _tangent_axis_defaults(normal_axis)[0]
        column_axis = primitive.column_axis or next(
            axis for axis in ("x", "y", "z") if axis not in {normal_axis, row_axis}
        )
        radius = max(
            float(
                primitive.washer_radius
                or primitive.radius
                or primitive.outer_radius
                or 0.0
            ),
            1e-6,
        )
        height = max(
            float(
                primitive.washer_height
                or primitive.head_height
                or primitive.height
                or 0.0
            ),
            1e-6,
        )
        diameter = radius * 2.0
        if primitive.fastener_centers:
            extents = [diameter, diameter, diameter]
            extents[_axis_to_index(normal_axis)] = height
            half = (extents[0] * 0.5, extents[1] * 0.5, extents[2] * 0.5)
            mins: list[tuple[float, float, float]] = []
            maxs: list[tuple[float, float, float]] = []
            for center in primitive.fastener_centers:
                mins.append((center[0] - half[0], center[1] - half[1], center[2] - half[2]))
                maxs.append((center[0] + half[0], center[1] + half[1], center[2] + half[2]))
            return tuple(
                max(max(point[axis] for point in maxs) - min(point[axis] for point in mins), 1e-6)
                for axis in range(3)
            )
        rows = max(int(primitive.fastener_rows or 1), 1)
        columns = max(int(primitive.fastener_columns or 1), 1)
        spacing = max(float(primitive.fastener_spacing or 0.0), diameter)
        values = [diameter, diameter, diameter]
        values[_axis_to_index(normal_axis)] = height
        values[_axis_to_index(row_axis)] = max(diameter, (rows - 1) * spacing + diameter)
        values[_axis_to_index(column_axis)] = max(diameter, (columns - 1) * spacing + diameter)
        return (values[0], values[1], values[2])
    bounds = _mesh_vertex_bounds(primitive)
    if bounds is not None:
        bounds_min, bounds_max = bounds
        return (
            bounds_max[0] - bounds_min[0],
            bounds_max[1] - bounds_min[1],
            bounds_max[2] - bounds_min[2],
        )
    raise MeshProgramError(
        f"compound ops do not yet support target primitive type {pt!r} "
        "(supported: box, subdivision_box, cylinder, sphere, extruded_profile, "
        "revolved_profile, mesh-backed primitives)"
    )


def _face_offset(
    face: str, target: ShapePrimitive
) -> tuple[tuple[float, float, float], str, str]:
    """Return ``(face_center, plane_axis, normal_axis)`` for a face.

    ``plane_axis`` is the axis along which the face's *length* runs for
    the row direction (deterministic choice); ``normal_axis`` is the
    axis perpendicular to the face. The returned center is the face's
    center in target-local coordinates (relative to target.center).
    """
    extents = _bbox_extents(target)
    center = _bbox_center(target)
    target_center = target.center
    center_delta = (
        center[0] - target_center[0],
        center[1] - target_center[1],
        center[2] - target_center[2],
    )
    half = (extents[0] * 0.5, extents[1] * 0.5, extents[2] * 0.5)
    sign = 1.0 if face[0] == "+" else -1.0
    axis_char = face[1]
    if axis_char == "x":
        return (
            (center_delta[0] + sign * half[0], center_delta[1], center_delta[2]),
            "y",
            "x",
        )
    if axis_char == "y":
        return (
            (center_delta[0], center_delta[1] + sign * half[1], center_delta[2]),
            "x",
            "y",
        )
    return (
        (center_delta[0], center_delta[1], center_delta[2] + sign * half[2]),
        "x",
        "z",
    )


def _grid_axes_for_face(
    face_normal: str, row_axis: str
) -> tuple[str, str]:
    """Return ``(row_axis, col_axis)`` — both perpendicular to the face."""
    perpendicular = sorted(set(_AXIS_VALUES) - {face_normal})
    if row_axis not in perpendicular:
        row_axis = perpendicular[0]
    col_axis = next(a for a in perpendicular if a != row_axis)
    return row_axis, col_axis


def _pop_bound_single_target_primitive(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    where: str,
) -> tuple[str, ShapePrimitive]:
    present = [name for name in ("target", "source") if name in kw]
    if len(present) != 1:
        raise MeshProgramError(f"{where}: requires exactly one of 'target' or 'source'")
    key = present[0]
    target_name = _ident(kw.pop(key, None), where=f"{where}.{key}")
    if target_name not in bindings or bindings[target_name].kind != "primitive":
        raise MeshProgramError(
            f"{where}: '{key}' must reference a primitive let-binding, "
            f"got {target_name!r}"
        )
    target_primitives = _value_primitives(bindings[target_name])
    if len(target_primitives) != 1:
        raise MeshProgramError(
            f"{where}: {key} {target_name!r} must reference exactly one primitive, "
            f"got {len(target_primitives)}"
        )
    target = target_primitives[0]
    if target not in primitives:
        primitives.append(target)
    return target_name, target


def _aggregate_bbox_target_primitive(
    target_name: str,
    target_primitives: tuple[ShapePrimitive, ...],
    *,
    part: str,
) -> ShapePrimitive:
    bbox_sources = [
        primitive
        for primitive in target_primitives
        if str(primitive.blend_mode or "union") != "subtract"
    ] or list(target_primitives)
    mins: list[tuple[float, float, float]] = []
    maxs: list[tuple[float, float, float]] = []
    for primitive in bbox_sources:
        center = _bbox_center(primitive)
        extents = _bbox_extents(primitive)
        half = (extents[0] * 0.5, extents[1] * 0.5, extents[2] * 0.5)
        mins.append((center[0] - half[0], center[1] - half[1], center[2] - half[2]))
        maxs.append((center[0] + half[0], center[1] + half[1], center[2] + half[2]))
    bounds_min = tuple(min(point[axis] for point in mins) for axis in range(3))
    bounds_max = tuple(max(point[axis] for point in maxs) for axis in range(3))
    center = tuple((bounds_min[axis] + bounds_max[axis]) * 0.5 for axis in range(3))
    extents = tuple(max(bounds_max[axis] - bounds_min[axis], 1e-6) for axis in range(3))
    return ShapePrimitive(
        primitive_type="box",
        part=part,
        center=(center[0], center[1], center[2]),
        extents=(extents[0], extents[1], extents[2]),
        tags=[
            "mesh_program_aggregate_target",
            f"mesh_program_aggregate_target_{target_name}",
        ],
        blend_mode="union",
    )


def _pop_bound_target_surface_primitives(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> tuple[str, tuple[ShapePrimitive, ...], ShapePrimitive]:
    present = [name for name in ("target", "source") if name in kw]
    if len(present) != 1:
        raise MeshProgramError(f"{where}: requires exactly one of 'target' or 'source'")
    key = present[0]
    target_name = _ident(kw.pop(key, None), where=f"{where}.{key}")
    if target_name not in bindings or bindings[target_name].kind != "primitive":
        raise MeshProgramError(
            f"{where}: '{key}' must reference a primitive let-binding, "
            f"got {target_name!r}"
        )
    target_primitives = _value_primitives(bindings[target_name])
    if not target_primitives:
        raise MeshProgramError(f"{where}: {key} {target_name!r} has no primitives")
    for primitive in target_primitives:
        if primitive not in primitives:
            primitives.append(primitive)
    if len(target_primitives) == 1:
        return target_name, target_primitives, target_primitives[0]
    return (
        target_name,
        target_primitives,
        _aggregate_bbox_target_primitive(target_name, target_primitives, part=part),
    )


def _pop_surface_normal_axis_alias(
    kw: dict[str, Any],
    *,
    where: str,
    names: tuple[str, ...] = ("normal_axis", "surface_axis", "face_axis"),
) -> tuple[str | None, str | None]:
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
        )
    if not present:
        return None, None
    name = present[0]
    return _axis_arg(kw.pop(name), where=f"{where}.{name}"), name


def _sign_from_optional_normal_sign(value: float | int | None) -> float:
    if value is None:
        return 1.0
    return -1.0 if float(value) < 0.0 else 1.0


def _require_matching_surface_sign(
    *,
    where: str,
    face: str,
    supplied_sign: float | int | None,
) -> float:
    face_sign = 1.0 if face[0] == "+" else -1.0
    if supplied_sign is not None and _sign_from_optional_normal_sign(supplied_sign) != face_sign:
        raise MeshProgramError(
            f"{where}.normal_sign: sign {supplied_sign!r} conflicts with face {face!r}"
        )
    return face_sign


def _axis_to_index(axis: str) -> int:
    return {"x": 0, "y": 1, "z": 2}[axis]


def _apply_fastener_grid(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, target_primitives, target = _pop_bound_target_surface_primitives(
        kw,
        bindings,
        primitives=primitives,
        part=part,
        where=where,
    )
    face_value = kw.pop("face", None)
    explicit_normal_axis, explicit_normal_axis_name = _pop_surface_normal_axis_alias(
        kw,
        where=where,
        names=("normal_axis", "surface_axis", "face_axis", "axis"),
    )
    normal_sign_value = _pop_number_alias(
        kw,
        where=where,
        names=("normal_sign", "sign"),
    )
    rows = _pop_int_alias(kw, where=where, names=("rows", "row_count"), required=True)
    cols = _pop_int_alias(
        kw,
        where=where,
        names=("cols", "columns", "column_count"),
        required=True,
    )
    if rows < 1 or cols < 1:
        raise MeshProgramError(f"{where}: rows/cols must each be >= 1")
    spacing = _pop_length_alias(
        kw,
        where=where,
        names=("spacing", "spacing_cm"),
        required=True,
    )
    fastener_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("fastener_radius", "fastener_radius_cm", "radius", "radius_cm"),
        diameter_names=("fastener_diameter", "fastener_diameter_cm", "diameter", "diameter_cm"),
        required=True,
    )
    fastener_height = _pop_length_alias(
        kw,
        where=where,
        names=("fastener_height", "fastener_height_cm", "height", "height_cm"),
        required=True,
    )
    seam_group = _pop_string_alias(kw, where=where, names=("seam_group", "seam"))
    output_part = _pop_string_alias(
        kw,
        where=where,
        names=("part", "output_part", "component_part"),
    )
    feature_part = output_part or part
    requested_row_axis = _pop_string_alias(
        kw,
        where=where,
        names=("row_axis", "array_axis"),
        allowed=_AXIS_VALUES,
    )
    requested_column_axis = _pop_string_alias(
        kw,
        where=where,
        names=("column_axis", "col_axis"),
        allowed=_AXIS_VALUES,
    )
    parameters: dict[str, Any] = {
        "rows": rows,
        "columns": cols,
        "spacing_cm": spacing,
        "radius_cm": fastener_radius,
        "height_cm": fastener_height,
    }
    washer_radius = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=("washer_radius", "washer_radius_cm"),
        diameter_names=("washer_diameter", "washer_diameter_cm"),
    )
    if washer_radius is not None:
        parameters["washer_radius_cm"] = washer_radius
    for parameter_key, names in (
        ("washer_height_cm", ("washer_height", "washer_height_cm")),
        ("head_height_cm", ("head_height", "head_height_cm")),
        ("bevel_width_cm", ("bevel_width", "bevel_width_cm")),
        ("seat_depth_cm", ("seat_depth", "seat_depth_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=parameter_key, names=names)
    bevel_segments = _pop_number_alias(kw, where=where, names=("bevel_segments", "segments"))
    if bevel_segments is not None:
        parameters["bevel_segments"] = bevel_segments
    head_style = _pop_string_alias(
        kw,
        where=where,
        names=("head_style", "style"),
        allowed={"domed", "flat", "conical"},
    )
    if head_style is not None:
        parameters["head_style"] = head_style
    include_washer = _pop_bool_alias(kw, where=where, names=("include_washer", "washer"))
    if include_washer is not None:
        parameters["include_washer"] = include_washer
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_instance_variation_parameters(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown op_fastener_grid(...) argument(s): {unknown}"
        )

    face: str | None
    if face_value is not None:
        face = _face_arg(face_value, where=f"{where}.face")
        _, default_row_axis, normal_axis = _face_offset(face, target)
        if explicit_normal_axis is not None and explicit_normal_axis != normal_axis:
            raise MeshProgramError(
                f"{where}.{explicit_normal_axis_name}: axis {explicit_normal_axis!r} "
                f"conflicts with face {face!r}"
            )
        sign = _require_matching_surface_sign(
            where=where,
            face=face,
            supplied_sign=normal_sign_value,
        )
    else:
        face = None
        normal_axis = explicit_normal_axis or "z"
        default_row_axis = _tangent_axis_defaults(normal_axis)[0]
        sign = _sign_from_optional_normal_sign(normal_sign_value)
    if requested_row_axis == normal_axis:
        raise MeshProgramError(
            f"{where}: row_axis {requested_row_axis!r} cannot equal the face normal {normal_axis!r}"
        )
    if requested_column_axis == normal_axis:
        raise MeshProgramError(
            f"{where}: column_axis {requested_column_axis!r} cannot equal the face normal {normal_axis!r}"
        )
    if (
        requested_row_axis is not None
        and requested_column_axis is not None
        and requested_row_axis == requested_column_axis
    ):
        raise MeshProgramError(
            f"{where}: row_axis and column_axis must be different, got {requested_row_axis!r}"
        )
    row_axis, col_axis = _grid_axes_for_face(normal_axis, default_row_axis)
    if requested_row_axis is not None:
        row_axis, col_axis = _grid_axes_for_face(normal_axis, requested_row_axis)
    if requested_column_axis is not None:
        col_axis = requested_column_axis
    if row_axis == col_axis:
        raise MeshProgramError(
            f"{where}: row_axis and column_axis must be different, got {row_axis!r}"
        )
    parameters.update(
        {
            "axis": normal_axis,
            "row_axis": row_axis,
            "column_axis": col_axis,
            "normal_sign": sign,
            **({"target_surface_scope": "aggregate"} if len(target_primitives) > 1 else {}),
            **({"face": face} if face is not None else {}),
            **({"seam_group": seam_group} if seam_group is not None else {}),
        }
    )
    aggregate_target = len(target_primitives) > 1
    source_history = _mesh_program_operation_history_from_primitives(target_primitives)
    result = _lower_v2_source_op(
        "op.fastener_grid",
        source_primitives=target_primitives,
        parameters=parameters,
        primitives=primitives,
        part=feature_part,
        where=where,
        use_geometry_kernel=not aggregate_target,
        replace_source_primitives=not aggregate_target,
        aggregate_source_primitives=aggregate_target,
    )
    result_primitives = _value_primitives(result)
    for primitive in result_primitives:
        if seam_group is not None:
            tag_boolean_seam_group(primitive, seam_group=seam_group, target_part=feature_part)
        _attach_mesh_program_operation_history(
            primitive,
            source=target,
            op_name="op_fastener_grid",
            modifier_name="v2_fastener_grid_modifier",
            modifier_payload=parameters,
            feature_primitive_count=rows * cols,
            source_history=source_history,
            component="fastener_grid",
            region=f"{feature_part}.fastener_grid",
        )
    if target_name in bindings:
        _replace_value_primitives(
            bindings[target_name],
            (*target_primitives, *result_primitives)
            if aggregate_target
            else result_primitives,
        )
    return _Value(
        kind="primitive",
        primitive=result.primitive,
        primitives=result_primitives,
        bevel_target=result.bevel_target,
    )


def _apply_vent_slats(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, target_primitives, target = _pop_bound_target_surface_primitives(
        kw,
        bindings,
        primitives=primitives,
        part=part,
        where=where,
    )
    face_value = kw.pop("face", None)
    explicit_normal_axis, explicit_normal_axis_name = _pop_surface_normal_axis_alias(
        kw,
        where=where,
    )
    normal_sign_value = _pop_number_alias(
        kw,
        where=where,
        names=("normal_sign", "sign"),
    )
    count = _pop_int_alias(kw, where=where, names=("count", "slat_count"), required=True)
    if count < 1:
        raise MeshProgramError(f"{where}: count must be >= 1")
    slot_width = _pop_length_alias(
        kw,
        where=where,
        names=("slot_width", "slot_width_cm", "width", "width_cm"),
        required=True,
    )
    slot_length = _pop_length_alias(
        kw,
        where=where,
        names=("slot_length", "slot_length_cm", "length", "length_cm"),
        required=True,
    )
    slot_depth = _pop_length_alias(
        kw,
        where=where,
        names=("slot_depth", "slot_depth_cm", "depth", "depth_cm"),
        required=True,
    )
    spacing = _pop_length_alias(
        kw,
        where=where,
        names=("spacing", "spacing_cm"),
        required=True,
    )
    axis_value = _pop_string_alias(
        kw,
        where=where,
        names=("axis", "row_axis", "array_axis"),
        allowed=_AXIS_VALUES,
    )
    seam_group = _pop_string_alias(kw, where=where, names=("seam_group", "seam"))
    output_part = _pop_string_alias(
        kw,
        where=where,
        names=("part", "output_part", "component_part"),
    )
    feature_part = output_part or part
    parameters: dict[str, Any] = {
        "count": count,
        "spacing_cm": spacing,
        "length_cm": slot_length,
        "height_cm": slot_width,
        "thickness_cm": slot_depth,
        "blend_mode": "subtract",
    }
    slat_shape = _pop_string_alias(
        kw,
        where=where,
        names=("slot_shape", "shape"),
        allowed={"rectangular", "rounded", "rounded_slot", "capsule"},
    )
    if slat_shape is not None:
        parameters["slot_shape"] = slat_shape
    for parameter_key, names in (
        ("bevel_width_cm", ("bevel_width", "bevel_width_cm", "rim_bevel", "rim_bevel_cm")),
        ("seat_depth_cm", ("seat_depth", "seat_depth_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=parameter_key, names=names)
    bevel_segments = _pop_number_alias(
        kw,
        where=where,
        names=("bevel_segments", "segments", "rim_bevel_segments"),
    )
    if bevel_segments is not None:
        parameters["bevel_segments"] = bevel_segments
    rotation_degrees = _pop_angle_alias(
        kw,
        where=where,
        names=("rotation_degrees", "rotation_deg", "angle", "radians"),
    )
    if rotation_degrees is not None:
        parameters["rotation_degrees"] = rotation_degrees
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_instance_variation_parameters(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown op_vent_slats(...) argument(s): {unknown}"
        )

    face: str | None
    face_center: tuple[float, float, float] | None
    if face_value is not None:
        face = _face_arg(face_value, where=f"{where}.face")
        face_center, default_row_axis, normal_axis = _face_offset(face, target)
        if explicit_normal_axis is not None and explicit_normal_axis != normal_axis:
            raise MeshProgramError(
                f"{where}.{explicit_normal_axis_name}: axis {explicit_normal_axis!r} "
                f"conflicts with face {face!r}"
            )
        sign = _require_matching_surface_sign(
            where=where,
            face=face,
            supplied_sign=normal_sign_value,
        )
    else:
        face = None
        face_center = None
        normal_axis = explicit_normal_axis or "z"
        default_row_axis = _tangent_axis_defaults(normal_axis)[0]
        sign = _sign_from_optional_normal_sign(normal_sign_value)
    array_axis = _axis_arg(axis_value, where=f"{where}.axis", default=default_row_axis)
    if array_axis == normal_axis:
        raise MeshProgramError(
            f"{where}: axis {array_axis!r} cannot equal the face normal {normal_axis!r}"
        )
    if (
        face_center is not None
        and str(parameters.get("blend_mode") or "subtract") in {"subtract", "intersect"}
        and "center" not in parameters
    ):
        normal_index = _axis_to_index(normal_axis)
        local = [0.0, 0.0, 0.0]
        local[normal_index] = face_center[normal_index] - sign * slot_depth * 0.5
        parameters["center"] = (
            target.center[0] + local[0],
            target.center[1] + local[1],
            target.center[2] + local[2],
        )
    parameters.update(
        {
            "axis": normal_axis,
            "row_axis": array_axis,
            "normal_sign": sign,
            **({"target_surface_scope": "aggregate"} if len(target_primitives) > 1 else {}),
            **({"face": face} if face is not None else {}),
            **({"seam_group": seam_group} if seam_group is not None else {}),
        }
    )
    aggregate_target = len(target_primitives) > 1
    source_history = _mesh_program_operation_history_from_primitives(target_primitives)
    result = _lower_v2_source_op(
        "op.vent_slats",
        source_primitives=target_primitives,
        parameters=parameters,
        primitives=primitives,
        part=feature_part,
        where=where,
        use_geometry_kernel=not aggregate_target,
        replace_source_primitives=not aggregate_target,
        aggregate_source_primitives=aggregate_target,
    )
    result_primitives = _value_primitives(result)
    for primitive in result_primitives:
        if seam_group is not None:
            tag_boolean_seam_group(primitive, seam_group=seam_group, target_part=feature_part)
        _attach_mesh_program_operation_history(
            primitive,
            source=target,
            op_name="op_vent_slats",
            modifier_name="v2_vent_slats_modifier",
            modifier_payload=parameters,
            feature_primitive_count=count,
            source_history=source_history,
            component="vent_slats",
            region=f"{feature_part}.vent_slats",
        )
    _replace_value_primitives(
        bindings[target_name],
        (*target_primitives, *result_primitives)
        if aggregate_target
        else result_primitives,
    )
    return _Value(
        kind="primitive",
        primitive=result.primitive,
        primitives=result_primitives,
        bevel_target=result.bevel_target,
    )


def _apply_trim_band(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, target_primitives, target = _pop_bound_target_surface_primitives(
        kw,
        bindings,
        primitives=primitives,
        part=part,
        where=where,
    )
    face_value = kw.pop("face", None)
    normal_axis, explicit_normal_axis_name = _pop_surface_normal_axis_alias(
        kw,
        where=where,
        names=("normal_axis", "surface_axis", "thickness_axis", "face_axis"),
    )
    normal_sign_value = _pop_number_alias(
        kw,
        where=where,
        names=("normal_sign", "sign"),
    )
    band_axis_value = _pop_string_alias(
        kw,
        where=where,
        names=("axis", "band_axis"),
        allowed=_AXIS_VALUES,
    )
    length_axis = _pop_string_alias(
        kw,
        where=where,
        names=("length_axis",),
        allowed=_AXIS_VALUES,
    )
    width = _pop_length_alias(
        kw,
        where=where,
        names=("width", "width_cm", "band_width", "band_width_cm"),
        required=True,
    )
    depth = _pop_length_alias(
        kw,
        where=where,
        names=("depth", "depth_cm", "band_depth", "band_depth_cm", "height", "height_cm"),
        required=True,
    )
    offset_value = _pop_length_alias(
        kw,
        where=where,
        names=("offset", "offset_cm"),
    )
    seam_group = _pop_string_alias(kw, where=where, names=("seam_group", "seam"))
    output_part = _pop_string_alias(
        kw,
        where=where,
        names=("part", "output_part", "component_part"),
    )
    feature_part = output_part or part
    parameters: dict[str, Any] = {
        "width_cm": width,
    }
    explicit_length = _pop_length_alias(kw, where=where, names=("length", "length_cm"))
    explicit_thickness = _pop_length_alias(kw, where=where, names=("thickness", "thickness_cm"))
    for parameter_key, names in (
        ("bevel_width_cm", ("bevel_width", "bevel_width_cm")),
        ("seat_depth_cm", ("seat_depth", "seat_depth_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=parameter_key, names=names)
    bevel_segments = _pop_number_alias(kw, where=where, names=("bevel_segments", "segments"))
    if bevel_segments is not None:
        parameters["bevel_segments"] = bevel_segments
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown op_trim_band(...) argument(s): {unknown}"
        )

    target_extents = _bbox_extents(target)
    band_axis = (
        _axis_arg(band_axis_value, where=f"{where}.axis")
        if band_axis_value is not None
        else None
    )
    if face_value is not None:
        face = _face_arg(face_value, where=f"{where}.face")
        if normal_axis is not None and normal_axis != face[1]:
            raise MeshProgramError(
                f"{where}.{explicit_normal_axis_name}: axis {normal_axis!r} "
                f"conflicts with face {face!r}"
            )
        normal_axis = face[1]
        parameters["normal_sign"] = _require_matching_surface_sign(
            where=where,
            face=face,
            supplied_sign=normal_sign_value,
        )
    elif normal_sign_value is not None:
        parameters["normal_sign"] = _sign_from_optional_normal_sign(normal_sign_value)
    if normal_axis is None:
        if band_axis is not None:
            candidate_normal_axes = [axis for axis in ("x", "y", "z") if axis != band_axis]
            normal_axis = min(candidate_normal_axes, key=lambda item: target_extents[_axis_to_index(item)])
        else:
            normal_axis = "z"
    if band_axis is None:
        band_axis = _tangent_axis_defaults(normal_axis)[0]
    band_axis_index = _axis_to_index(band_axis)
    if normal_axis == band_axis:
        raise MeshProgramError(
            f"{where}: normal_axis {normal_axis!r} cannot equal band axis {band_axis!r}"
        )
    if length_axis is None:
        length_axis = next(axis for axis in ("x", "y", "z") if axis not in {band_axis, normal_axis})
    if len({normal_axis, length_axis, band_axis}) != 3:
        raise MeshProgramError(
            f"{where}: axis, normal_axis, and length_axis must be distinct"
        )
    offset_along_axis = float(offset_value or 0.0)
    if "center" not in parameters:
        band_center = list(_bbox_center(target))
        band_center[band_axis_index] += offset_along_axis
        parameters["center"] = (band_center[0], band_center[1], band_center[2])
    elif offset_value is not None:
        band_center = list(parameters["center"])
        band_center[band_axis_index] += offset_along_axis
        parameters["center"] = (band_center[0], band_center[1], band_center[2])
    parameters.update(
        {
            "axis": normal_axis,
            "length_axis": length_axis,
            "band_axis": band_axis,
            "width_axis": band_axis,
            "length_cm": (
                explicit_length
                if explicit_length is not None
                else target_extents[_axis_to_index(length_axis)] + 2.0 * depth
            ),
            "thickness_cm": (
                explicit_thickness
                if explicit_thickness is not None
                else target_extents[_axis_to_index(normal_axis)] + 2.0 * depth
            ),
            "depth_cm": depth,
            "band_depth_cm": depth,
            "offset_cm": offset_along_axis,
            **({"target_surface_scope": "aggregate"} if len(target_primitives) > 1 else {}),
            **({"seam_group": seam_group} if seam_group is not None else {}),
        }
    )
    aggregate_target = len(target_primitives) > 1
    source_history = _mesh_program_operation_history_from_primitives(target_primitives)
    result = _lower_v2_source_op(
        "op.trim_band",
        source_primitives=target_primitives,
        parameters=parameters,
        primitives=primitives,
        part=feature_part,
        where=where,
        use_geometry_kernel=not aggregate_target,
        replace_source_primitives=not aggregate_target,
        aggregate_source_primitives=aggregate_target,
    )
    result_primitives = _value_primitives(result)
    for primitive in result_primitives:
        if seam_group is not None:
            tag_boolean_seam_group(primitive, seam_group=seam_group, target_part=feature_part)
        _attach_mesh_program_operation_history(
            primitive,
            source=target,
            op_name="op_trim_band",
            modifier_name="v2_trim_band_modifier",
            modifier_payload=parameters,
            feature_primitive_count=1,
            source_history=source_history,
            component="trim_band",
            region=f"{feature_part}.trim_band",
        )
    _replace_value_primitives(
        bindings[target_name],
        (*target_primitives, *result_primitives)
        if aggregate_target
        else result_primitives,
    )
    return _Value(
        kind="primitive",
        primitive=result.primitive,
        primitives=result_primitives,
        bevel_target=result.bevel_target,
    )


def _trunk_anchor(target: ShapePrimitive) -> tuple[tuple[float, float, float], float, float]:
    """Return (top_world, top_radius_cm, height_cm) for a vegetation trunk.

    Reads the lofted_solid trunk's top section center (world-space) and
    radius. Falls back conservatively for non-vegetation primitives so
    the op stays useful if authors point it at a cylinder/box stand-in.
    """
    cx, cy, cz = target.center
    if (
        target.primitive_type == "lofted_solid"
        and target.section_centers
        and target.cross_sections
    ):
        top_local = target.section_centers[-1]
        top_world = (cx + top_local[0], cy + top_local[1], cz + top_local[2])
        # Approximate top radius from the last section's farthest vertex
        # to the section origin — robust against polygon shape.
        top_section = target.cross_sections[-1]
        top_radius = max(math.hypot(p[0], p[1]) for p in top_section)
        first_local = target.section_centers[0]
        height = max(
            1e-6,
            math.dist(first_local, top_local),
        )
        return top_world, float(top_radius), float(height)
    if target.primitive_type == "cylinder":
        radius = float(target.radius or 1.0)
        height = float(target.height or 1.0)
        return ((cx, cy + height * 0.5, cz), radius, height)
    extents = _bbox_extents(target)
    return ((cx, cy + extents[1] * 0.5, cz), max(extents[0], extents[2]) * 0.5, extents[1])


def _apply_vegetation_canopy(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Stamp branches + leaf cards on top of a parent trunk binding.

    Parameters:
        parent: identifier of a vegetation_trunk (or any compatible
            single-primitive binding). Read positionally for the trunk's
            top anchor and radius.
        branch_count: number of branches radiating from the trunk top.
        leaf_density: total number of leaf spheres scattered across all
            branches (distributed evenly). 0 = no leaves (skeleton-only).
        leaf_size: leaf sphere radius (length unit literal).
        foliage_radius: outer envelope of the canopy in world space
            (length unit literal). Branches reach toward this radius;
            leaves scatter inside it.
        branch_pitch: optional bend (radians) of each branch from
            vertical. Defaults to ~60 degrees so branches read clearly
            outward, not just up.

    Composes deterministically — same parameters always produce the same
    primitive list. Branches are cylinders aligned along their direction
    axis (axis defaults to "y"; we use a per-branch best-fit-axis so
    lengths read correctly along the branch). Leaves are spheres.

    Returns:
        The last leaf primitive (or last branch if no leaves) so a
        downstream op can reference the canopy's most recent emission.
    """
    kw = _kwargs(args, where=where)
    parent_name = _ident(kw.pop("parent", None), where=f"{where}.parent")
    branch_count = _int(kw.pop("branch_count", None), where=f"{where}.branch_count")
    leaf_density = _int(kw.pop("leaf_density", None), where=f"{where}.leaf_density")
    leaf_size = _unit_to_cm(kw.pop("leaf_size", None), where=f"{where}.leaf_size")
    foliage_radius = _unit_to_cm(
        kw.pop("foliage_radius", None), where=f"{where}.foliage_radius"
    )
    branch_pitch_value = kw.pop("branch_pitch", 1.05)
    if isinstance(branch_pitch_value, (int, float)) and not isinstance(
        branch_pitch_value, bool
    ):
        branch_pitch = float(branch_pitch_value)
    else:
        raise MeshProgramError(
            f"{where}.branch_pitch: expected a number (radians), got {branch_pitch_value!r}"
        )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown vegetation_canopy(...) argument(s): {unknown}"
        )
    if branch_count < 1:
        raise MeshProgramError(
            f"{where}: branch_count must be >= 1, got {branch_count}"
        )
    if leaf_density < 0:
        raise MeshProgramError(
            f"{where}: leaf_density must be >= 0, got {leaf_density}"
        )
    if leaf_size <= 0.0:
        raise MeshProgramError(f"{where}: leaf_size must be > 0, got {leaf_size}cm")
    if foliage_radius <= 0.0:
        raise MeshProgramError(
            f"{where}: foliage_radius must be > 0, got {foliage_radius}cm"
        )
    if parent_name not in bindings or bindings[parent_name].kind != "primitive":
        raise MeshProgramError(
            f"{where}: 'parent' must reference a primitive let-binding, "
            f"got {parent_name!r}"
        )
    parent = bindings[parent_name].primitive
    if parent is None:
        raise MeshProgramError(
            f"{where}: parent {parent_name!r} has no primitive payload"
        )
    if parent not in primitives:
        primitives.append(parent)

    top, top_radius, _trunk_height = _trunk_anchor(parent)

    # Branches radiate from the top of the trunk in a ring; each tilts
    # outward by ``branch_pitch`` from vertical. Length is set so the
    # branch tip lands on the foliage envelope.
    branch_radius = max(0.6, top_radius * 0.45)
    branch_length = max(2.0 * leaf_size, foliage_radius)
    sin_p = math.sin(branch_pitch)
    cos_p = math.cos(branch_pitch)
    feature_primitives: list[ShapePrimitive] = []
    branch_tips: list[tuple[float, float, float]] = []
    branch_dirs: list[tuple[float, float, float]] = []
    for i in range(branch_count):
        azimuth = 2.0 * math.pi * i / branch_count
        dx = math.cos(azimuth) * sin_p
        dz = math.sin(azimuth) * sin_p
        dy = cos_p
        # Cylinder is axis-aligned; pick the axis closest to the branch
        # direction so the cylinder visually reads as the branch.
        if abs(dy) >= max(abs(dx), abs(dz)):
            axis = "y"
        elif abs(dx) >= abs(dz):
            axis = "x"
        else:
            axis = "z"
        # Branch midpoint = top + 0.5 * length * direction
        mid = (
            top[0] + 0.5 * branch_length * dx,
            top[1] + 0.5 * branch_length * dy,
            top[2] + 0.5 * branch_length * dz,
        )
        branch = ShapePrimitive(
            primitive_type="cylinder",
            part=part,
            center=mid,
            radius=branch_radius,
            height=branch_length,
            axis=axis,
            tags=["vegetation", "vegetation_branch", f"branch_{i}"],
            blend_mode="union",
        )
        feature_primitives.append(branch)
        tip = (
            top[0] + branch_length * dx,
            top[1] + branch_length * dy,
            top[2] + branch_length * dz,
        )
        branch_tips.append(tip)
        branch_dirs.append((dx, dy, dz))

    if leaf_density > 0:
        # Distribute leaves around branches deterministically. We use a
        # spherical Fibonacci pattern centered on the trunk top so leaf
        # placement is even without a PRNG.
        golden = math.pi * (3.0 - math.sqrt(5.0))
        canopy_center = (top[0], top[1] + foliage_radius * 0.4, top[2])
        for i in range(leaf_density):
            t = (i + 0.5) / max(1, leaf_density)
            phi = math.acos(1.0 - 2.0 * t)
            theta = golden * i
            # Bias upward (multiply lower-hemisphere y by 0.4) so leaves
            # cluster more above branches than below — reads as a tree
            # crown rather than a sphere.
            sin_phi = math.sin(phi)
            x = math.cos(theta) * sin_phi
            y = math.cos(phi)
            z = math.sin(theta) * sin_phi
            if y < 0.0:
                y *= 0.4
            # Slight radial jitter via deterministic stride keeps the
            # canopy from looking like a perfect sphere.
            r_jitter = 1.0 - 0.18 * ((i * 7) % 5) / 5.0
            r = foliage_radius * r_jitter
            center = (
                canopy_center[0] + x * r,
                canopy_center[1] + y * r,
                canopy_center[2] + z * r,
            )
            leaf = ShapePrimitive(
                primitive_type="sphere",
                part=part,
                center=center,
                radius=leaf_size,
                tags=["vegetation", "vegetation_leaf", f"leaf_{i}"],
                blend_mode="union",
            )
            feature_primitives.append(leaf)

    fused = _kernel_fused_legacy_feature_primitive(
        "vegetation_canopy",
        target=parent,
        feature_primitives=tuple(feature_primitives),
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="mesh_program_vegetation_canopy_modifier",
        modifier_payload={
            "parent": parent_name,
            "branch_count": branch_count,
            "leaf_density": leaf_density,
            "leaf_size_cm": leaf_size,
            "foliage_radius_cm": foliage_radius,
            "branch_pitch": branch_pitch,
            "branch_radius_cm": branch_radius,
            "branch_length_cm": branch_length,
            "branch_tip_count": len(branch_tips),
            "branch_primitive_count": branch_count,
            "leaf_primitive_count": leaf_density,
            "materialized_as": "kernel_program.boolean",
        },
        kernel_tag="vegetation_canopy_kernel_program",
        operation_tag="vegetation_canopy",
        component="vegetation_canopy",
        region=f"{part}.vegetation_canopy",
    )
    _append_unique_tags(fused, (
        "vegetation",
        "vegetation_canopy",
        "mesh_program_vegetation_canopy_kernel_program",
    ))
    metadata = dict(fused.semantic_metadata or {})
    metadata["mesh_program_vegetation_canopy"] = {
        "operation": "mesh_program.vegetation_canopy",
        "parent": parent_name,
        "parent_primitive_type": str(parent.primitive_type),
        "branch_count": branch_count,
        "leaf_density": leaf_density,
        "leaf_size_cm": leaf_size,
        "foliage_radius_cm": foliage_radius,
        "branch_pitch": branch_pitch,
        "branch_tip_count": len(branch_tips),
        "feature_primitive_count": len(feature_primitives),
        "materialized_as": "kernel_program.boolean",
        "kernel_program": True,
    }
    fused.semantic_metadata = metadata
    _replace_value_primitives(bindings[parent_name], (fused,))
    return _Value(kind="primitive", primitive=fused, primitives=(fused,), bevel_target=fused)


_TERRAIN_BIOMES = {"alpine", "rolling_hills", "rocky"}


def _apply_terrain_biome(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Apply a biome modifier to a heightfield target in-place.

    Parameters:
        target: identifier of a ``terrain_heightfield`` (or any
            heightfield-typed primitive let-binding).
        biome: one of ``"alpine"``, ``"rolling_hills"``, ``"rocky"``.
            Selects the per-biome modifier kernel:

            * ``alpine`` — adds N sharp Gaussian peaks at deterministic
              positions, scaled by ``peak_density`` and ``roughness``.
              Reads as a hilltop with rocky outcrops.
            * ``rolling_hills`` — multiplies the base relief by a
              low-frequency sinusoidal envelope so peaks soften into
              long swells. ``roughness`` controls how aggressively the
              envelope dips below 1.0.
            * ``rocky`` — adds a high-frequency fractal detail layer
              (single octave, fine cell size) on top of the base. Reads
              as crinkly rock surface.

        roughness: optional float in [0, 1]. How strong the biome
            modification is relative to the base relief. Default 0.5.
        peak_density: optional float in [0, 1]. For ``alpine``, the
            fraction of cells that get peak contribution; ignored by
            ``rolling_hills`` / ``rocky``. Default 0.2.

    The op mutates the target primitive's ``height_data`` (and updates
    the binding's ``vertical_scale`` when needed) so downstream calls
    see the modified terrain. Returns the same target as the binding so
    the op can be the final statement.
    """
    import numpy as np

    kw = _kwargs(args, where=where)
    target_name = _ident(kw.pop("target", None), where=f"{where}.target")
    biome = _string(kw.pop("biome", None), where=f"{where}.biome")
    roughness_value = kw.pop("roughness", 0.5)
    if isinstance(roughness_value, (int, float)) and not isinstance(
        roughness_value, bool
    ):
        roughness = float(roughness_value)
    else:
        raise MeshProgramError(
            f"{where}.roughness: expected a number in [0, 1], got {roughness_value!r}"
        )
    peak_density_value = kw.pop("peak_density", 0.2)
    if isinstance(peak_density_value, (int, float)) and not isinstance(
        peak_density_value, bool
    ):
        peak_density = float(peak_density_value)
    else:
        raise MeshProgramError(
            f"{where}.peak_density: expected a number in [0, 1], "
            f"got {peak_density_value!r}"
        )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown terrain_biome(...) argument(s): {unknown}"
        )

    if biome not in _TERRAIN_BIOMES:
        raise MeshProgramError(
            f"{where}: biome must be one of {sorted(_TERRAIN_BIOMES)}, got {biome!r}"
        )
    if not 0.0 <= roughness <= 1.0:
        raise MeshProgramError(
            f"{where}: roughness must be in [0, 1], got {roughness}"
        )
    if not 0.0 <= peak_density <= 1.0:
        raise MeshProgramError(
            f"{where}: peak_density must be in [0, 1], got {peak_density}"
        )
    if target_name not in bindings or bindings[target_name].kind != "primitive":
        raise MeshProgramError(
            f"{where}: 'target' must reference a primitive let-binding, "
            f"got {target_name!r}"
        )
    target = bindings[target_name].primitive
    if target is None:
        raise MeshProgramError(
            f"{where}: target {target_name!r} has no primitive payload"
        )
    if target.primitive_type != "heightfield":
        raise MeshProgramError(
            f"{where}: terrain_biome target must be a heightfield primitive, "
            f"got {target.primitive_type!r}"
        )
    if target.height_data is None or target.resolution is None:
        raise MeshProgramError(
            f"{where}: target heightfield is missing height_data/resolution"
        )
    if target not in primitives:
        primitives.append(target)

    h = np.asarray(target.height_data, dtype=np.float64)
    nx, ny = int(target.resolution[0]), int(target.resolution[1])
    # Deterministic seed derived from the heightfield bounds + biome name
    # so the same target+biome always produces the same overlay.
    biome_seed = _stable_seed(biome, target.bounds_xy or (0.0, 0.0, 0.0, 0.0))
    rng = np.random.default_rng(np.uint64(biome_seed))

    if biome == "alpine":
        # Gaussian peaks scattered over the field. Number of peaks scales
        # with peak_density and grid area; height scales with roughness.
        cell_count = nx * ny
        n_peaks = max(1, round(peak_density * 0.02 * cell_count))
        # Cap peaks to keep the loop fast even at high resolutions.
        n_peaks = min(n_peaks, 64)
        ys, xs = np.indices(h.shape)
        for _ in range(n_peaks):
            cx = float(rng.integers(0, nx))
            cy = float(rng.integers(0, ny))
            sigma = max(2.0, min(nx, ny) * 0.06)
            peak_h = 0.4 + 0.6 * float(rng.random()) * (0.5 + roughness)
            dx = xs - cx
            dy = ys - cy
            gaussian = np.exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma))
            h = h + peak_h * gaussian
    elif biome == "rolling_hills":
        # Multiply by a soft low-frequency envelope so peaks become
        # gentle swells. roughness controls envelope dip depth.
        u = np.linspace(0.0, 2.0 * np.pi, nx, dtype=np.float64)
        v = np.linspace(0.0, 2.0 * np.pi, ny, dtype=np.float64)
        env = 0.5 * (
            1.0
            + np.cos(u[None, :]) * 0.5
            + np.sin(v[:, None]) * 0.5
        )
        env = 1.0 - roughness * (1.0 - env)
        h = h * env
    elif biome == "rocky":
        # Add a high-frequency fractal detail layer on top of base.
        from ..std.terrain.heightfield import Heightfield as _HF
        from ..std.terrain.noise import fbm as _fbm

        rocky_hf = _HF.zeros(
            (nx, ny),
            bounds_xy=target.bounds_xy or (-1.0, -1.0, 1.0, 1.0),
        )
        _fbm(
            rocky_hf,
            octaves=3,
            base_frequency=8.0,
            amplitude=1.0,
            seed=int(biome_seed) & 0x7FFFFFFF,
            add=False,
        )
        rocky = rocky_hf.heights
        rmin, rmax = float(rocky.min()), float(rocky.max())
        if rmax > rmin:
            rocky = (rocky - rmin) / (rmax - rmin)
        h = h + rocky * (0.15 + 0.4 * roughness)

    # Re-normalise so vertical_scale still describes the true peak
    # relief (alpine peaks may have pushed the max above 1.0).
    new_max = float(h.max())
    if new_max > 1.0:
        h = h / new_max
    target.height_data = h.tolist()
    target.tags = list(target.tags) + [
        f"terrain_biome:{biome}",
        "terrain_biome_source_heightfield",
    ]
    try:
        from ..asset_quality.shape_ir_v2 import (
            ShapeOp,
            _kernel_import_record_for_single_source,
            _primitive_from_v1_record,
        )
        from ..geometry.kernel import resolve_geometry_kernel

        op = ShapeOp(
            op="mesh_program.terrain_biome",
            target=part,
            parameters={
                "target": target_name,
                "biome": biome,
                "roughness": roughness,
                "peak_density": peak_density,
            },
            purpose="mesh_program.terrain_biome",
        )
        record = _kernel_import_record_for_single_source(
            op,
            source_record=_source_record_for_primitive(target),
            geometry_kernel=resolve_geometry_kernel(),
            route="mesh_program_terrain_biome",
            asset_name="mesh_program_terrain_biome_source",
            blueprint_id="mesh_program_terrain_biome_source",
            modifier_name="mesh_program_terrain_biome_modifier",
            modifier_payload={
                "target": target_name,
                "biome": biome,
                "roughness": roughness,
                "peak_density": peak_density,
                "resolution": [
                    int(target.resolution[0]),
                    int(target.resolution[1]),
                ],
                "bounds_xy": [float(v) for v in (target.bounds_xy or ())],
                "vertical_scale_cm": float(target.vertical_scale or 0.0),
                "materialized_as": "kernel_program.import",
            },
            kernel_tag="terrain_biome_kernel_program",
        )
        fused = _primitive_from_v1_record(record)
    except (TypeError, ValueError) as exc:
        raise MeshProgramError(f"{where}: kernel import failed for terrain_biome: {exc}") from exc
    _append_unique_tags(fused, (
        "terrain",
        f"terrain_biome:{biome}",
        "mesh_program_terrain_biome_kernel_program",
    ))
    metadata = dict(fused.semantic_metadata or {})
    metadata["mesh_program_terrain_biome"] = {
        "operation": "mesh_program.terrain_biome",
        "target": target_name,
        "biome": biome,
        "roughness": roughness,
        "peak_density": peak_density,
        "resolution": [
            int(target.resolution[0]),
            int(target.resolution[1]),
        ],
        "bounds_xy": [float(v) for v in (target.bounds_xy or ())],
        "vertical_scale_cm": float(target.vertical_scale or 0.0),
        "materialized_as": "kernel_program.import",
        "kernel_program": True,
    }
    fused.semantic_metadata = metadata
    _replace_primitives_in_program(primitives, (target,), (fused,))
    _replace_value_primitives(bindings[target_name], (fused,))
    return _Value(kind="primitive", primitive=fused, primitives=(fused,), bevel_target=fused)


# ---------------------------------------------------------------------------
# Phase 2 §6.x — scatter / Copy-to-Points productivity multiplier.
#
# Authors describe a *point cloud* (grid, random distribution, ring) once,
# bind it to an identifier, then call ``scatter(primitive:, points:)`` to
# emit N translated copies of any primitive in a single declaration. This
# replaces dozens of explicit ``box(...).translate([x, y, z])`` lines with
# one declarative statement and generalises across all 5 domains:
# rivets/screws (hard-surface), leaf cards (vegetation), debris rocks
# (terrain), surface bumps (SDF/creature), greebles inside cells (WFC).
# ---------------------------------------------------------------------------


def _eval_points_grid_call(
    args: list[dict[str, Any]], *, where: str
) -> list[tuple[float, float, float]]:
    """Generate a 2D ``rows x cols`` grid of points within ``extents``.

    Parameters:
        extents: 2-element length-unit list ``[W, H]``. The grid is
            centered on the origin so points span ``[-W/2, +W/2]``
            along the row axis and ``[-H/2, +H/2]`` along the column
            axis. Both dimensions must be > 0.
        rows / cols: integer grid dimensions. Both must be >= 1. The
            generator emits ``rows * cols`` points; spacing is
            uniform: ``W / (cols - 1)`` and ``H / (rows - 1)`` with the
            single-row/single-col degenerate case clamped to a single
            centered point along that axis.
        plane: optional ``"+x"|"+y"|"+z"`` selecting which axis is the
            grid normal. Defaults to ``"+z"`` (XY plane, horizontal
            grid). The two non-normal axes carry the row/col extents
            in deterministic alphabetical order.

    Returns:
        Flat list of ``(x, y, z)`` cm-space tuples in row-major order.
    """
    kw = _kwargs(args, where=where)
    if "rows" not in kw:
        raise MeshProgramError(f"{where}: points_grid(...) requires 'rows'")
    if "cols" not in kw:
        raise MeshProgramError(f"{where}: points_grid(...) requires 'cols'")
    rows = _int(kw.pop("rows"), where=f"{where}.rows")
    cols = _int(kw.pop("cols"), where=f"{where}.cols")
    if "extents" in kw:
        extents_xy = _vec2_length(kw.pop("extents"), where=f"{where}.extents")
    else:
        spacing_value = _pop_first_kw(kw, ("spacing", "spacing_cm"))
        if spacing_value is None:
            raise MeshProgramError(f"{where}: points_grid(...) requires 'extents' or 'spacing'")
        spacing_cm = _unit_to_cm(spacing_value, where=f"{where}.spacing")
        if spacing_cm <= 0.0:
            raise MeshProgramError(f"{where}.spacing: must be > 0, got {spacing_cm} cm")
        extents_xy = (
            spacing_cm * float(max(rows - 1, 1)),
            spacing_cm * float(max(cols - 1, 1)),
        )
    plane_value = kw.pop("plane", "+z")
    if not isinstance(plane_value, str) or plane_value not in _FACE_VALUES:
        raise MeshProgramError(
            f"{where}.plane: must be one of '+x','-x','+y','-y','+z','-z', "
            f"got {plane_value!r}"
        )
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown points_grid(...) argument(s): {unknown}"
        )
    if rows < 1 or cols < 1:
        raise MeshProgramError(
            f"{where}: rows/cols must each be >= 1, got rows={rows}, cols={cols}"
        )
    width, height = extents_xy
    if width <= 0.0 or height <= 0.0:
        raise MeshProgramError(
            f"{where}: extents must be positive, got [{width}, {height}] cm"
        )
    normal_axis = plane_value[1]
    perpendicular = sorted(set(_AXIS_VALUES) - {normal_axis})
    row_axis = perpendicular[0]
    col_axis = perpendicular[1]
    row_index = _axis_to_index(row_axis)
    col_index = _axis_to_index(col_axis)
    points: list[tuple[float, float, float]] = []
    for r in range(rows):
        if rows == 1:
            u = 0.0
        else:
            u = -width * 0.5 + r * (width / (rows - 1))
        for c in range(cols):
            if cols == 1:
                v = 0.0
            else:
                v = -height * 0.5 + c * (height / (cols - 1))
            local = [0.0, 0.0, 0.0]
            local[row_index] = u
            local[col_index] = v
            points.append((local[0], local[1], local[2]))
    return points


def _eval_points_random_call(
    args: list[dict[str, Any]], *, where: str
) -> list[tuple[float, float, float]]:
    """Generate ``count`` deterministic uniform-random points within ``extents``.

    Parameters:
        count: integer point count. Must be >= 1.
        seed: integer RNG seed. Same seed always produces the same
            point cloud — keeps shape-stage builds reproducible.
        extents: ``[W, H]`` or ``[W, H, D]`` length-unit list. The
            cloud is centered on the origin and uniformly distributed
            within the half-extents on each axis. ``[W, H]`` pins
            ``z=0`` (planar scatter); ``[W, H, D]`` produces a 3D
            cloud.
    """
    import random

    kw = _kwargs(args, where=where)
    if "count" not in kw:
        raise MeshProgramError(f"{where}: points_random(...) requires 'count'")
    if "seed" not in kw:
        raise MeshProgramError(f"{where}: points_random(...) requires 'seed'")
    if "extents" not in kw:
        raise MeshProgramError(f"{where}: points_random(...) requires 'extents'")
    count = _int(kw.pop("count"), where=f"{where}.count")
    seed = _int(kw.pop("seed"), where=f"{where}.seed")
    extents_value = kw.pop("extents")
    if not isinstance(extents_value, list) or len(extents_value) not in (2, 3):
        raise MeshProgramError(
            f"{where}.extents: expected a 2- or 3-element list, got {extents_value!r}"
        )
    components = [
        _unit_to_cm(item, where=f"{where}.extents[{i}]")
        for i, item in enumerate(extents_value)
    ]
    if any(c <= 0.0 for c in components):
        raise MeshProgramError(
            f"{where}: extents must all be > 0, got {components}"
        )
    if len(components) == 2:
        half = (components[0] * 0.5, components[1] * 0.5, 0.0)
    else:
        half = (components[0] * 0.5, components[1] * 0.5, components[2] * 0.5)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown points_random(...) argument(s): {unknown}"
        )
    if count < 1:
        raise MeshProgramError(f"{where}: count must be >= 1, got {count}")
    rng = random.Random(seed)
    points: list[tuple[float, float, float]] = []
    for _ in range(count):
        x = rng.uniform(-half[0], half[0])
        y = rng.uniform(-half[1], half[1])
        z = rng.uniform(-half[2], half[2]) if half[2] > 0.0 else 0.0
        points.append((x, y, z))
    return points


def _eval_points_circle_call(
    args: list[dict[str, Any]], *, where: str
) -> list[tuple[float, float, float]]:
    """Generate ``count`` evenly-spaced points around a circle.

    Parameters:
        count: number of points. Must be >= 1.
        radius: circle radius (length unit literal). Must be > 0.
        axis: optional ``"x"|"y"|"z"`` — the circle's normal axis.
            Defaults to ``"y"`` (XZ-plane circle, horizontal ring).
            The two non-normal axes carry the cosine/sine components
            in deterministic alphabetical order.
    """
    kw = _kwargs(args, where=where)
    if "count" not in kw:
        raise MeshProgramError(f"{where}: points_circle(...) requires 'count'")
    if "radius" not in kw:
        raise MeshProgramError(f"{where}: points_circle(...) requires 'radius'")
    count = _int(kw.pop("count"), where=f"{where}.count")
    radius = _unit_to_cm(kw.pop("radius"), where=f"{where}.radius")
    axis = _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y")
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown points_circle(...) argument(s): {unknown}"
        )
    if count < 1:
        raise MeshProgramError(f"{where}: count must be >= 1, got {count}")
    if radius <= 0.0:
        raise MeshProgramError(f"{where}: radius must be > 0, got {radius}cm")
    perpendicular = sorted(set(_AXIS_VALUES) - {axis})
    cos_index = _axis_to_index(perpendicular[0])
    sin_index = _axis_to_index(perpendicular[1])
    points: list[tuple[float, float, float]] = []
    for i in range(count):
        theta = 2.0 * math.pi * i / count
        local = [0.0, 0.0, 0.0]
        local[cos_index] = math.cos(theta) * radius
        local[sin_index] = math.sin(theta) * radius
        points.append((local[0], local[1], local[2]))
    return points


def _eval_points_combine_call(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    where: str,
) -> _Value:
    """Concatenate multiple point-set bindings into a single point set.

    Single positional argument: a list of identifiers, each bound to a
    ``kind="point_set"`` ``_Value``. Returns one combined point set
    preserving the source order.
    """
    if len(args) != 1 or args[0].get("name") is not None:
        raise MeshProgramError(
            f"{where}: points_combine(...) takes a single positional list "
            f"of point-set identifiers"
        )
    targets_value = args[0].get("value")
    if not isinstance(targets_value, list) or not targets_value:
        raise MeshProgramError(
            f"{where}: points_combine expects a non-empty list of "
            f"point-set identifiers, got {targets_value!r}"
        )
    combined: list[tuple[float, float, float]] = []
    for index, ident_value in enumerate(targets_value):
        ident_name = _ident(ident_value, where=f"{where}[{index}]")
        if ident_name not in bindings:
            raise MeshProgramError(
                f"{where}[{index}]: unknown identifier {ident_name!r}"
            )
        binding = bindings[ident_name]
        if binding.kind != "point_set" or binding.points is None:
            raise MeshProgramError(
                f"{where}[{index}]: {ident_name!r} must reference a point_set "
                f"binding (kind='point_set'), got kind={binding.kind!r}"
        )
        combined.extend(binding.points)
    return _Value(kind="point_set", points=combined)


def _scatter_instance_metadata(
    template: ShapePrimitive,
    *,
    primitive_ident: str,
    points_ident: str,
    index: int,
    count: int,
    point_cm: tuple[float, float, float],
    placed_point_cm: tuple[float, float, float],
    jitter_offset_cm: tuple[float, float, float],
    jitter_cm: float,
    seam_group: str | None,
) -> dict[str, Any]:
    metadata = dict(template.semantic_metadata or {})
    operation_id = f"mesh_program.scatter:{points_ident}:{primitive_ident}:{index}"
    record: dict[str, Any] = {
        "operation": "mesh_program.scatter",
        "operation_id": operation_id,
        "primitive": primitive_ident,
        "points": points_ident,
        "template_part": template.part,
        "template_primitive_type": template.primitive_type,
        "point_index": int(index),
        "point_count": int(count),
        "jitter_cm": float(jitter_cm),
        "point_cm": [float(value) for value in point_cm],
        "placed_point_cm": [float(value) for value in placed_point_cm],
        "jitter_offset_cm": [float(value) for value in jitter_offset_cm],
    }
    if seam_group is not None:
        record["seam_group"] = seam_group
    previous_operation = metadata.get("operation")
    if previous_operation not in (None, "", [], {}):
        record["template_operation"] = str(previous_operation)
    metadata.update(
        {
            "operation": "mesh_program.scatter",
            "operation_id": operation_id,
            "point_scatter": record,
        }
    )
    return metadata


def _apply_scatter(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Materialize translated copies of ``primitive`` at every point in ``points``.

    Parameters:
        primitive: identifier bound to either a primitive let-binding
            (deep-copied + translated for each point) or an SDF
            let-binding (each instance becomes a ``Translate`` node
            wrapping the SDF — caller is then responsible for an
            ``sdf_extract`` on a downstream union if they want the
            cloud baked to mesh).
        points: identifier bound to a ``kind="point_set"`` binding
            produced by ``points_grid``, ``points_random``,
            ``points_circle``, or ``points_combine``.
        jitter: optional length-unit literal — peak per-axis random
            offset added to each instance's translation. Deterministic:
            seeded from the binding name + per-instance index so the
            same source always produces the same cloud. Defaults to 0
            (no jitter).
        seam_group: optional string — when provided, every emitted
            primitive is tagged into this seam group so a follow-up
            ``fillet_edge(target: ..., edge_class: <seam_group>)``
            can attach a polybevel modifier to the scattered set.

    Primitive sources are lowered through the ShapeIR v2 copy-to-points
    kernel path so the visible scatter cloud is one fused ``sdf_mesh``.
    SDF sources remain an SDF ``Union`` of translated instances.
    """
    import random as _random

    kw = _kwargs(args, where=where)
    if "primitive" not in kw:
        raise MeshProgramError(f"{where}: scatter(...) requires 'primitive'")
    if "points" not in kw:
        raise MeshProgramError(f"{where}: scatter(...) requires 'points'")
    primitive_label, primitive_binding = _pop_value_parameter(
        kw,
        bindings,
        name="primitive",
        allowed_kinds=("primitive", "sdf"),
        part=part,
        where=where,
    )
    points_label, cloud = _pop_points_parameter_with_label(
        kw,
        bindings,
        part=part,
        where=where,
    )
    jitter_value = kw.pop("jitter", None)
    if jitter_value is not None:
        jitter_cm = _unit_to_cm(jitter_value, where=f"{where}.jitter")
    else:
        jitter_cm = 0.0
    seam_group = kw.pop("seam_group", None)
    if seam_group is not None:
        seam_group = _string(seam_group, where=f"{where}.seam_group")
    output_part = _pop_string_alias(
        kw,
        where=where,
        names=("part", "output_part", "component_part"),
    )
    feature_part = output_part or part
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown scatter(...) argument(s): {unknown}"
        )
    if jitter_cm < 0.0:
        raise MeshProgramError(
            f"{where}: jitter must be >= 0, got {jitter_cm} cm"
        )
    if not cloud:
        raise MeshProgramError(
            f"{where}: 'points' point_set is empty — nothing to scatter"
        )

    # Deterministic per-call jitter: seed the RNG from the primitive
    # identifier + point identifier so the same scatter always produces
    # the same offsets, while two distinct scatter calls in the same
    # program use independent streams.
    rng = _random.Random(_stable_seed(primitive_label, points_label, jitter_cm))

    if primitive_binding.kind == "primitive" and primitive_binding.primitive is not None:
        template = primitive_binding.primitive
        placed_points: list[tuple[float, float, float]] = []
        jitter_records: list[dict[str, Any]] = []
        for index, point in enumerate(cloud):
            jx = rng.uniform(-jitter_cm, jitter_cm) if jitter_cm > 0.0 else 0.0
            jy = rng.uniform(-jitter_cm, jitter_cm) if jitter_cm > 0.0 else 0.0
            jz = rng.uniform(-jitter_cm, jitter_cm) if jitter_cm > 0.0 else 0.0
            tx = template.center[0] + point[0] + jx
            ty = template.center[1] + point[1] + jy
            tz = template.center[2] + point[2] + jz
            placed_point = (tx, ty, tz)
            placed_points.append(placed_point)
            jitter_records.append(
                {
                    "point_index": int(index),
                    "source_point_cm": [float(value) for value in point],
                    "placed_point_cm": [float(value) for value in placed_point],
                    "jitter_offset_cm": [float(jx), float(jy), float(jz)],
                }
            )
        parameters = {
            "points": placed_points,
            "seed": _stable_seed(primitive_label, points_label, jitter_cm),
        }
        value = _lower_bound_v2_source_op(
            "sop.copy_to_points",
            mesh_program_op_name="mesh_program_scatter",
            target_name=primitive_label,
            bindings=bindings,
            source_primitives=_value_primitives(primitive_binding),
            parameters=parameters,
            primitives=primitives,
            part=feature_part,
            where=where,
            modifier_name="v2_copy_to_points_modifier",
            feature_primitive_count=len(placed_points),
            component="scatter",
            region=f"{feature_part}.scatter",
        )
        for output in _value_primitives(value):
            _append_unique_tags(
                output,
                [
                    "scatter",
                    f"scatter_points:{points_label}",
                    "mesh_program_scatter_kernel_program",
                ],
            )
            metadata = dict(output.semantic_metadata or {})
            scatter_payload = {
                "operation": "mesh_program.scatter",
                "operation_id": f"mesh_program.scatter:{points_label}:{primitive_label}:kernel",
                "primitive": primitive_label,
                "points": points_label,
                "template_part": template.part,
                "template_primitive_type": template.primitive_type,
                "point_count": len(cloud),
                "jitter_cm": float(jitter_cm),
                "materialized_as": "sop.copy_to_points",
                "kernel_program": True,
                "samples": jitter_records[:128],
                "sample_record_count": min(len(jitter_records), 128),
                "sample_record_limit": 128,
            }
            if seam_group is not None:
                scatter_payload["seam_group"] = seam_group
                tag_boolean_seam_group(output, seam_group=seam_group, target_part=feature_part)
            metadata["mesh_program_scatter"] = scatter_payload
            metadata.setdefault("operation", "mesh_program.scatter")
            output.semantic_metadata = metadata
        return value

    if primitive_binding.kind == "sdf" and primitive_binding.sdf_expr is not None:
        from ..f_rep import Translate, Union

        # Each instance is a Translate of the source SDF. v1 reduces
        # them into a left-fold ``Union`` so the resulting binding is
        # still a single ``kind="sdf"`` _Value the author can pass to
        # ``sdf_smooth_union`` or ``sdf_extract``.
        accumulated: Any = None
        for point in cloud:
            jx = rng.uniform(-jitter_cm, jitter_cm) if jitter_cm > 0.0 else 0.0
            jy = rng.uniform(-jitter_cm, jitter_cm) if jitter_cm > 0.0 else 0.0
            jz = rng.uniform(-jitter_cm, jitter_cm) if jitter_cm > 0.0 else 0.0
            instance = Translate(
                expr=primitive_binding.sdf_expr,
                offset=(point[0] + jx, point[1] + jy, point[2] + jz),
            )
            accumulated = (
                instance if accumulated is None else Union(a=accumulated, b=instance)
            )
        return _Value(kind="sdf", sdf_expr=accumulated)

    raise MeshProgramError(
        f"{where}: 'primitive' must reference a primitive or SDF let-binding, "
        f"got kind={primitive_binding.kind!r}"
    )


# Maximum number of instances scatter_on_surface will emit. Above ~5000 the
# downstream boolean kernel and trimesh sampler become the bottleneck and the
# resulting GLB inflates beyond the productivity-multiplier intent of the op.
_SCATTER_ON_SURFACE_MAX_COUNT = 5000


def _append_unique_tags(primitive: ShapePrimitive, tags: list[str]) -> None:
    existing = list(primitive.tags)
    seen = set(existing)
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        existing.append(tag)
    primitive.tags = existing


def _apply_scatter_on_surface(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    """Emit copies of ``primitive`` distributed across ``target``'s surface.

    Same productivity multiplier as ``scatter(...)`` but the points are
    sampled from the actual surface of another primitive, so authors can
    say "rocks on terrain", "rivets on a curved panel", "leaves on a
    branch", "decorations on dungeon walls" without first computing the
    point cloud by hand.

    Parameters:
        primitive: identifier bound to a primitive let-binding (the
            template that gets duplicated). Must resolve to
            ``kind="primitive"``; SDF templates are out of scope for
            v1 (use ``sdf_extract`` first).
        target: identifier bound to a primitive let-binding whose
            triangle mesh defines the sampling surface. SDF targets
            are deferred to v2 — extract the SDF first if needed.
        density: items per square metre of target surface area. The
            target's mesh is built via ``_primitive_mesh`` and its
            ``trimesh.area`` (cm²) is converted to m² before scaling.
            Final ``count = int(density * area_m2)`` and is capped at
            :data:`_SCATTER_ON_SURFACE_MAX_COUNT` so a runaway density
            value cannot stall the boolean kernel.
        seed: optional integer (default 0) — feeds both
            ``trimesh.sample.sample_surface`` and the per-instance
            jitter RNG so repeats are deterministic.
        jitter: optional length-unit literal (default 0). Each
            instance's center receives an independent uniform offset
            in ``[-jitter, +jitter]`` per axis.
        align_to_normal: optional bool (default false). When true,
            each instance is rotated so the template's local +Z axis
            aligns with the face normal at the sampled surface point.
            Because :class:`ShapePrimitive` does not carry an
            orientation field, alignment is implemented by baking the
            template to a triangle mesh (``_primitive_mesh``), rotating
            the vertices, then emitting an
            ``ShapePrimitive(primitive_type="sdf_mesh", ...)`` for each
            instance.

    Side effect: for each sampled surface point, one
    ``ShapePrimitive`` is appended to ``primitives``. The target itself
    is also ensured to be in ``primitives`` so callers that built the
    target via a fresh ``let target = terrain_heightfield(...)`` see
    the terrain mesh in the output even if no other op references it.
    Returns the last emitted instance as the binding.
    """
    kw = _kwargs(args, where=where)
    if "primitive" not in kw:
        raise MeshProgramError(
            f"{where}: scatter_on_surface(...) requires 'primitive'"
        )
    if "target" not in kw:
        raise MeshProgramError(
            f"{where}: scatter_on_surface(...) requires 'target'"
        )
    if "density" not in kw:
        raise MeshProgramError(
            f"{where}: scatter_on_surface(...) requires 'density'"
        )
    primitive_label, primitive_binding = _pop_value_parameter(
        kw,
        bindings,
        name="primitive",
        allowed_kinds=("primitive",),
        part=part,
        where=where,
    )
    target_label, target_binding = _pop_value_parameter(
        kw,
        bindings,
        name="target",
        allowed_kinds=("primitive",),
        part=part,
        where=where,
    )
    density_value = kw.pop("density")
    if not isinstance(density_value, (int, float)) or isinstance(density_value, bool):
        raise MeshProgramError(
            f"{where}.density: expected a number (items per m²), "
            f"got {density_value!r}"
        )
    density = float(density_value)
    seed_value = kw.pop("seed", 0)
    seed = _int(seed_value, where=f"{where}.seed")
    jitter_value = kw.pop("jitter", None)
    if jitter_value is not None:
        jitter_cm = _unit_to_cm(jitter_value, where=f"{where}.jitter")
    else:
        jitter_cm = 0.0
    align_value = kw.pop("align_to_normal", False)
    if not isinstance(align_value, bool):
        raise MeshProgramError(
            f"{where}.align_to_normal: expected a bool, got {align_value!r}"
        )
    align_to_normal = bool(align_value)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(
            f"{where}: unknown scatter_on_surface(...) argument(s): {unknown}"
        )
    if density < 0.0:
        raise MeshProgramError(
            f"{where}: density must be >= 0, got {density}"
        )
    if jitter_cm < 0.0:
        raise MeshProgramError(
            f"{where}: jitter must be >= 0, got {jitter_cm} cm"
        )
    source_templates = _value_primitives(primitive_binding)
    if not source_templates:
        raise MeshProgramError(
            f"{where}: 'primitive' must reference a primitive let-binding "
            f"(SDF templates are not supported in v1), got "
            f"kind={primitive_binding.kind!r}"
        )
    if target_binding.primitive is None:
        raise MeshProgramError(
            f"{where}: 'target' must reference a primitive let-binding "
            f"(SDF targets are not supported in v1), got "
            f"kind={target_binding.kind!r}"
        )
    template = primitive_binding.primitive or source_templates[0]
    target_primitive = target_binding.primitive
    source_parameter: dict[str, Any] | list[dict[str, Any]]
    if len(source_templates) == 1:
        source_parameter = _source_record_for_primitive(source_templates[0])
    else:
        source_parameter = [
            _source_record_for_primitive(source) for source in source_templates
        ]

    from ..geometry.kernel import resolve_geometry_kernel

    try:
        lowered = tuple(
            _v2_primitives_from_op(
                "sop.scatter_on_surface",
                target=part,
                parameters={
                    "source": source_parameter,
                    "target": _source_record_for_primitive(target_primitive),
                    "density": density,
                    "seed": seed,
                    "jitter_cm": jitter_cm,
                    "align_to_normal": align_to_normal,
                    "include_target": True,
                    "max_count": _SCATTER_ON_SURFACE_MAX_COUNT,
                },
                where=where,
                geometry_kernel=resolve_geometry_kernel(),
            )
        )
    except (TypeError, ValueError) as exc:
        raise MeshProgramError(f"{where}: surface scatter kernel lowering failed: {exc}") from exc

    for output in lowered:
        _apply_mesh_vertex_bounds(output)
    _replace_primitives_in_program(
        primitives,
        (*_value_primitives(target_binding), *_value_primitives(primitive_binding)),
        lowered,
    )
    _replace_value_primitives(target_binding, lowered)
    for output in lowered:
        _append_unique_tags(
            output,
            [
                "scatter_on_surface",
                f"scatter_on_surface_source:{primitive_label}",
                f"scatter_on_surface_target:{target_label}",
                "mesh_program_scatter_on_surface_kernel_program",
            ],
        )
        metadata = dict(output.semantic_metadata or {})
        metadata["mesh_program_surface_scatter"] = {
            "operation": "mesh_program.scatter_on_surface",
            "operation_id": f"mesh_program.scatter_on_surface:{target_label}:{primitive_label}:kernel",
            "primitive": primitive_label,
            "target": target_label,
            "target_part": target_primitive.part,
            "target_primitive_type": target_primitive.primitive_type,
            "template_part": template.part,
            "template_primitive_type": template.primitive_type,
            "template_primitive_count": len(source_templates),
            "density_per_m2": float(density),
            "seed": int(seed),
            "jitter_cm": float(jitter_cm),
            "align_to_normal": bool(align_to_normal),
            "materialized_as": "sop.scatter_on_surface",
            "kernel_program": True,
            "include_target": True,
        }
        metadata.setdefault("operation", "mesh_program.scatter_on_surface")
        output.semantic_metadata = metadata
    return _primitive_value(lowered)


# Point-cloud generators that do not need the binding table — they take
# only literal arguments and produce a fresh point list. The ``_eval_expr``
# dispatcher wraps the result in a ``kind="point_set"`` _Value.
def _source_record_for_primitive(primitive: ShapePrimitive) -> dict[str, Any]:
    record = {
        key: value
        for key, value in primitive.to_dict().items()
        if value is not None
    }
    record.setdefault("primitive_type", primitive.primitive_type)
    record.setdefault("part", primitive.part)
    record.setdefault("center", primitive.center)
    record.setdefault("blend_mode", primitive.blend_mode or "union")
    if record.get("primitive_type") == "sdf_mesh" and record.get("mesh_vertices") and record.get("mesh_faces"):
        polybevel = record.get("v2_polybevel_modifier")
        pending_polybevel = (
            isinstance(polybevel, dict)
            and bool(polybevel)
            and "result_face_count" not in polybevel
            and "kernel_program" not in polybevel
        )
        preserve_baked_boolean = pending_polybevel or bool(record.get("boolean_seam_groups"))
        metadata = record.get("semantic_metadata")
        if isinstance(metadata, dict) and not preserve_baked_boolean:
            raw_sources = metadata.get("source_shape_primitives")
            if not isinstance(raw_sources, list) or not raw_sources:
                raw_source = metadata.get("source_shape_primitive")
                raw_sources = [raw_source] if isinstance(raw_source, dict) else []
            editable_sources = [
                deepcopy(source)
                for source in raw_sources
                if isinstance(source, dict)
                and str(source.get("primitive_type") or "")
                and str(source.get("primitive_type") or "") != "sdf_mesh"
            ]
            if editable_sources:
                history = _mesh_program_operation_history_from_primitive(primitive)
                for editable in editable_sources:
                    editable_metadata = editable.get("semantic_metadata")
                    editable_metadata = (
                        dict(editable_metadata)
                        if isinstance(editable_metadata, dict)
                        else {}
                    )
                    if history:
                        editable_metadata["mesh_program_operation_history"] = deepcopy(history)
                        v2_metadata = editable_metadata.get("shape_ir_v2")
                        v2_metadata = dict(v2_metadata) if isinstance(v2_metadata, dict) else {}
                        v2_metadata["mesh_program_operation_history"] = deepcopy(history)
                        editable_metadata["shape_ir_v2"] = v2_metadata
                    editable["semantic_metadata"] = editable_metadata
                if len(editable_sources) == 1:
                    return editable_sources[0]
                from ..asset_quality.shape_ir_v2 import _aggregate_context_record

                aggregate = _aggregate_context_record(
                    str(record.get("part") or primitive.part or "body"),
                    tuple(editable_sources),
                )
                if history:
                    aggregate["semantic_metadata"] = {
                        "mesh_program_operation_history": deepcopy(history),
                        "shape_ir_v2": {
                            "mesh_program_operation_history": deepcopy(history),
                        },
                    }
                return aggregate
        baked_modifiers: dict[str, Any] = {}
        for key in (
            "v2_polybevel_modifier",
            "bevel_seam_groups",
            "v2_subdivision_modifier",
            "v2_remesh_modifier",
            "remesh_target_edge_length_cm",
        ):
            if preserve_baked_boolean and key in {"v2_polybevel_modifier", "bevel_seam_groups"}:
                continue
            value = record.pop(key, None)
            if value not in (None, "", (), [], {}):
                baked_modifiers[key] = deepcopy(value)
        subdivision_levels = record.pop("subdivision_levels", None)
        if subdivision_levels not in (None, "", (), [], {}):
            with suppress(TypeError, ValueError):
                if int(subdivision_levels) > 0:
                    baked_modifiers["subdivision_levels"] = int(subdivision_levels)
        if baked_modifiers:
            metadata = record.get("semantic_metadata")
            metadata = dict(metadata) if isinstance(metadata, dict) else {}
            metadata["mesh_program_baked_source_modifiers"] = baked_modifiers
            record["semantic_metadata"] = metadata
    return record


def _canonical_kernel_operation_for_mesh_program(op_name: str) -> str:
    canonical = {
        "sop_polybevel": "sop.polybevel",
        "sop_subdivide": "sop.subdivide",
        "sop_remesh": "sop.remesh",
        "sop_twist": "sop.twist",
        "sop_taper": "sop.taper",
        "sop_bend": "sop.bend",
        "sop_loft": "sop.loft",
        "sop_polyextrude": "sop.polyextrude",
        "sop_polywire": "sop.polywire",
        "sop_sweep": "sop.sweep",
        "sop_transform": "sop.transform",
        "sop_carve": "sop.carve",
        "sop_copy_to_points": "sop.copy_to_points",
        "mesh_program_scatter": "mesh_program.scatter",
        "op_repeat": "op.repeat",
        "op_mirror": "op.mirror",
        "op_distribute": "op.distribute",
        "op_weighted_normals": "op.weighted_normals",
        "op_mark_hard_edge": "op.mark_hard_edge",
        "op_chip_edges": "op.chip_edges",
        "op_scratch_mask": "op.scratch_mask",
        "op_dent_mask": "op.dent_mask",
        "op_grime_mask": "op.grime_mask",
        "op_hull": "op.hull",
        "op_minkowski": "op.minkowski",
        "sop_boolean": "sop.boolean",
        "op_union": "op.union",
        "op_subtract": "op.subtract",
        "op_intersect": "op.intersect",
        "op_fastener_grid": "op.fastener_grid",
        "op_vent_slats": "op.vent_slats",
        "op_trim_band": "op.trim_band",
        "op_extrude": "op.extrude",
        "op_shell": "op.shell",
        "op_inset": "op.inset",
        "op_cut_panel_line": "op.cut_panel_line",
        "op_mount_plate": "op.mount_plate",
        "op_socket": "op.socket",
        "op_bracket": "op.bracket",
        "op_weld_seam": "op.weld_seam",
        "op_bevel": "op.bevel",
        "op_chamfer": "op.chamfer",
        "op_countersunk_hole": "op.countersunk_hole",
        "op_rounded_slot": "op.rounded_slot",
        "op_panel_frame": "op.panel_frame",
        "op_corner_guard_set": "op.corner_guard_set",
    }.get(op_name)
    if canonical:
        return canonical
    if "." in op_name:
        return op_name
    return f"mesh_program.{op_name}"


def _attach_mesh_program_generated_operation_history(
    primitive: ShapePrimitive,
    *,
    op_name: str,
    target: str,
    parameters: dict[str, Any],
    primitive_count: int,
    primitive_index: int,
) -> ShapePrimitive:
    """Attach initial operation lineage to v2-generated mesh_program solids."""
    metadata = dict(primitive.semantic_metadata or {})
    existing_history = _mesh_program_operation_history_from_primitive(primitive)
    canonical_operation = _canonical_kernel_operation_for_mesh_program(op_name)
    if any(
        str(entry.get("operation") or "") == canonical_operation
        for entry in existing_history
    ):
        return primitive

    v2_metadata = metadata.get("shape_ir_v2")
    v2_metadata = dict(v2_metadata) if isinstance(v2_metadata, dict) else {}
    operation_index = len(existing_history)
    component = str(
        primitive.component
        or target
        or primitive.part
        or primitive.primitive_type
        or "primitive"
    )
    region = str(primitive.region or f"{primitive.part}.{component}")
    entry: dict[str, Any] = {
        "operation": canonical_operation,
        "operation_index": operation_index,
        "operation_id": f"mesh_program:{canonical_operation}:{component}:{operation_index:04d}",
        "mesh_program_op": op_name,
        "modifier": "shape_ir_v2_lowering",
        "component": component,
        "region": region,
        "feature_primitive_count": int(max(1, primitive_count)),
        "generated_primitive_index": int(primitive_index),
        "generated_primitive_count": int(max(1, primitive_count)),
        "source_operation_count": operation_index,
        "target": str(target or primitive.part or ""),
        "primitive_type": str(primitive.primitive_type or ""),
    }
    if primitive.mesh_vertices is not None:
        entry["result_vertex_count"] = len(primitive.mesh_vertices)
    if primitive.mesh_faces is not None:
        entry["result_face_count"] = len(primitive.mesh_faces)
    kernel_metadata = metadata.get("kernel_result_metadata")
    if isinstance(kernel_metadata, dict):
        handoff = kernel_metadata.get("lathe_kernel_program_semantic_handoff")
        if isinstance(handoff, dict):
            entry["kernel_program_operand_count"] = int(handoff.get("operand_count") or 0)
            entry["kernel_program_source_part_count"] = int(
                handoff.get("source_part_count") or 0
            )
        face_summary = kernel_metadata.get("face_operation_summary")
        if isinstance(face_summary, dict):
            entry["face_operation_count"] = int(face_summary.get("operation_count") or 0)
        feature_detail = (
            kernel_metadata.get("lathe_kernel_feature_detail")
            or kernel_metadata.get("kernel_feature_detail")
            or kernel_metadata.get("kernel_program_feature_detail")
        )
        if isinstance(feature_detail, dict):
            entry["kernel_feature_kind"] = str(feature_detail.get("feature_kind") or "")
            entry["kernel_feature_count"] = int(feature_detail.get("feature_count") or 0)
            entry["kernel_feature_method"] = str(feature_detail.get("method") or "")
        edge_treatment = (
            kernel_metadata.get("lathe_kernel_edge_treatment")
            or kernel_metadata.get("kernel_edge_treatment")
            or kernel_metadata.get("kernel_program_edge_treatment")
        )
        if isinstance(edge_treatment, dict):
            entry["kernel_edge_treatment_kind"] = str(
                edge_treatment.get("treatment_kind") or ""
            )
            entry["kernel_edge_treatment_count"] = int(
                edge_treatment.get("edge_treatment_count") or 0
            )
            entry["kernel_edge_treatment_method"] = str(edge_treatment.get("method") or "")
        pattern_instances = (
            kernel_metadata.get("lathe_kernel_pattern_instances")
            or kernel_metadata.get("kernel_pattern_instances")
            or kernel_metadata.get("kernel_program_pattern_instances")
        )
        if isinstance(pattern_instances, dict):
            entry["kernel_pattern_kind"] = str(pattern_instances.get("pattern_kind") or "")
            entry["kernel_pattern_instance_count"] = int(
                pattern_instances.get("instance_count") or 0
            )
            entry["kernel_pattern_method"] = str(pattern_instances.get("method") or "")
        deform = (
            kernel_metadata.get("lathe_kernel_deform")
            or kernel_metadata.get("kernel_deform")
            or kernel_metadata.get("kernel_program_deform")
        )
        if isinstance(deform, dict):
            entry["kernel_deform_operation"] = str(deform.get("operation") or "")
            entry["kernel_deform_axis"] = str(deform.get("axis") or "")
            entry["kernel_deform_method"] = str(deform.get("method") or "")
        profile_path = (
            kernel_metadata.get("lathe_kernel_profile_path")
            or kernel_metadata.get("kernel_profile_path")
            or kernel_metadata.get("kernel_program_profile_path")
        )
        if isinstance(profile_path, dict):
            entry["kernel_profile_path_kind"] = str(profile_path.get("profile_kind") or "")
            entry["kernel_profile_path_operation"] = str(profile_path.get("operation") or "")
            entry["kernel_profile_path_method"] = str(profile_path.get("method") or "")
        surface_damage = (
            kernel_metadata.get("lathe_kernel_surface_damage")
            or kernel_metadata.get("kernel_surface_damage")
            or kernel_metadata.get("kernel_program_surface_damage")
        )
        if isinstance(surface_damage, dict):
            entry["kernel_surface_damage_kind"] = str(
                surface_damage.get("damage_kind") or ""
            )
            entry["kernel_surface_damage_count"] = int(
                surface_damage.get("damage_count") or 0
            )
            entry["kernel_surface_damage_method"] = str(surface_damage.get("method") or "")
    if parameters:
        entry["parameter_keys"] = sorted(str(key) for key in parameters)

    history = [*existing_history, entry]
    metadata["mesh_program_operation_history"] = history
    v2_metadata["mesh_program_operation_history"] = deepcopy(history)
    metadata["shape_ir_v2"] = v2_metadata
    primitive.semantic_metadata = metadata
    return primitive


def _mesh_program_operation_history_from_primitive(
    primitive: ShapePrimitive,
) -> list[dict[str, Any]]:
    metadata = primitive.semantic_metadata or {}
    candidates: list[Any] = []
    if isinstance(metadata, dict):
        candidates.append(metadata.get("mesh_program_operation_history"))
        v2_metadata = metadata.get("shape_ir_v2")
        if isinstance(v2_metadata, dict):
            candidates.append(v2_metadata.get("mesh_program_operation_history"))
    for candidate in candidates:
        if isinstance(candidate, list):
            history = [
                deepcopy(entry)
                for entry in candidate
                if isinstance(entry, dict) and str(entry.get("operation") or "")
            ]
            if history:
                return history
    return []


def _mesh_program_operation_history_from_primitives(
    primitives: tuple[ShapePrimitive, ...],
) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for primitive in primitives:
        for entry in _mesh_program_operation_history_from_primitive(primitive):
            if not any(existing == entry for existing in history):
                history.append(deepcopy(entry))
    return history


def _attach_mesh_program_operation_history(
    primitive: ShapePrimitive,
    *,
    source: ShapePrimitive,
    op_name: str,
    modifier_name: str,
    modifier_payload: dict[str, Any],
    feature_primitive_count: int,
    component: str,
    region: str,
    source_history: list[dict[str, Any]] | None = None,
) -> ShapePrimitive:
    metadata = dict(primitive.semantic_metadata or {})
    v2_metadata = metadata.get("shape_ir_v2")
    v2_metadata = dict(v2_metadata) if isinstance(v2_metadata, dict) else {}
    modifier = v2_metadata.get(modifier_name)
    modifier = dict(modifier) if isinstance(modifier, dict) else {}
    count_from_modifier = None
    for count_key in (
        "feature_primitive_count",
        "feature_record_count",
        "instance_count",
        "count",
        "guard_count",
        "corner_count",
        "source_record_count",
    ):
        if count_key in modifier:
            with suppress(TypeError, ValueError):
                count_from_modifier = max(1, int(modifier[count_key]))
            if count_from_modifier is not None:
                break
    source_history_entries = (
        deepcopy(source_history)
        if source_history is not None
        else _mesh_program_operation_history_from_primitive(source)
    )
    canonical_operation = _canonical_kernel_operation_for_mesh_program(op_name)
    operation_index = len(source_history_entries)
    entry: dict[str, Any] = {
        "operation": canonical_operation,
        "operation_index": operation_index,
        "operation_id": f"mesh_program:{canonical_operation}:{component}:{operation_index:04d}",
        "mesh_program_op": op_name,
        "modifier": modifier_name,
        "component": component,
        "region": region,
        "feature_primitive_count": int(count_from_modifier or feature_primitive_count),
        "source_operation_count": operation_index,
    }
    for source_key, target_key in (
        ("seam_group", "seam_group"),
        ("result_vertex_count", "result_vertex_count"),
        ("result_face_count", "result_face_count"),
        ("result_watertight", "result_watertight"),
    ):
        if source_key in modifier:
            entry[target_key] = deepcopy(modifier[source_key])
    if "seam_group" not in entry and "seam_group" in modifier_payload:
        entry["seam_group"] = deepcopy(modifier_payload["seam_group"])
    kernel_program = modifier.get("kernel_program")
    if isinstance(kernel_program, dict):
        feature_detail = (
            kernel_program.get("lathe_kernel_feature_detail")
            or kernel_program.get("kernel_feature_detail")
            or kernel_program.get("kernel_program_feature_detail")
        )
        if isinstance(feature_detail, dict):
            entry["kernel_feature_kind"] = str(feature_detail.get("feature_kind") or "")
            entry["kernel_feature_count"] = int(feature_detail.get("feature_count") or 0)
            entry["kernel_feature_method"] = str(feature_detail.get("method") or "")
        edge_treatment = (
            kernel_program.get("lathe_kernel_edge_treatment")
            or kernel_program.get("kernel_edge_treatment")
            or kernel_program.get("kernel_program_edge_treatment")
        )
        if isinstance(edge_treatment, dict):
            entry["kernel_edge_treatment_kind"] = str(
                edge_treatment.get("treatment_kind") or ""
            )
            entry["kernel_edge_treatment_count"] = int(
                edge_treatment.get("edge_treatment_count") or 0
            )
            entry["kernel_edge_treatment_method"] = str(edge_treatment.get("method") or "")
        pattern_instances = (
            kernel_program.get("lathe_kernel_pattern_instances")
            or kernel_program.get("kernel_pattern_instances")
            or kernel_program.get("kernel_program_pattern_instances")
        )
        if isinstance(pattern_instances, dict):
            entry["kernel_pattern_kind"] = str(pattern_instances.get("pattern_kind") or "")
            entry["kernel_pattern_instance_count"] = int(
                pattern_instances.get("instance_count") or 0
            )
            entry["kernel_pattern_method"] = str(pattern_instances.get("method") or "")
        deform = (
            kernel_program.get("lathe_kernel_deform")
            or kernel_program.get("kernel_deform")
            or kernel_program.get("kernel_program_deform")
        )
        if isinstance(deform, dict):
            entry["kernel_deform_operation"] = str(deform.get("operation") or "")
            entry["kernel_deform_axis"] = str(deform.get("axis") or "")
            entry["kernel_deform_method"] = str(deform.get("method") or "")
        profile_path = (
            kernel_program.get("lathe_kernel_profile_path")
            or kernel_program.get("kernel_profile_path")
            or kernel_program.get("kernel_program_profile_path")
        )
        if isinstance(profile_path, dict):
            entry["kernel_profile_path_kind"] = str(profile_path.get("profile_kind") or "")
            entry["kernel_profile_path_operation"] = str(profile_path.get("operation") or "")
            entry["kernel_profile_path_method"] = str(profile_path.get("method") or "")
        surface_damage = (
            kernel_program.get("lathe_kernel_surface_damage")
            or kernel_program.get("kernel_surface_damage")
            or kernel_program.get("kernel_program_surface_damage")
        )
        if isinstance(surface_damage, dict):
            entry["kernel_surface_damage_kind"] = str(
                surface_damage.get("damage_kind") or ""
            )
            entry["kernel_surface_damage_count"] = int(
                surface_damage.get("damage_count") or 0
            )
            entry["kernel_surface_damage_method"] = str(surface_damage.get("method") or "")
    history = [*source_history_entries, entry]
    metadata["mesh_program_operation_history"] = history
    v2_metadata["mesh_program_operation_history"] = deepcopy(history)
    metadata["shape_ir_v2"] = v2_metadata
    primitive.semantic_metadata = metadata
    return primitive


def _kernel_fused_legacy_feature_primitive(
    op_name: str,
    *,
    target: ShapePrimitive,
    feature_primitives: tuple[ShapePrimitive, ...],
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
    modifier_name: str,
    modifier_payload: dict[str, Any],
    kernel_tag: str,
    operation_tag: str,
    component: str,
    region: str,
) -> ShapePrimitive:
    if not feature_primitives:
        return target
    from ..asset_quality.shape_ir_v2 import (
        ShapeOp,
        _kernel_source_feature_records_boolean_record,
        _primitive_from_v1_record,
    )
    from ..geometry.kernel import resolve_geometry_kernel

    op = ShapeOp(
        op=_canonical_kernel_operation_for_mesh_program(op_name),
        target=part,
        parameters={},
        purpose=f"mesh_program.{op_name}",
    )
    try:
        record = _kernel_source_feature_records_boolean_record(
            op,
            source_record=_source_record_for_primitive(target),
            feature_records=tuple(
                _source_record_for_primitive(primitive)
                for primitive in feature_primitives
            ),
            geometry_kernel=resolve_geometry_kernel(),
            route=f"mesh_program_legacy_{op_name}",
            asset_name=f"mesh_program_legacy_{op_name}_boolean_source",
            blueprint_id=f"mesh_program_legacy_{op_name}_boolean_source",
            modifier_name=modifier_name,
            modifier_payload={
                **modifier_payload,
                "legacy_mesh_program_op": op_name,
                "feature_primitive_count": len(feature_primitives),
            },
            kernel_tag=kernel_tag,
            operation_tag=operation_tag,
            component=component,
            region=region,
        )
        fused = _primitive_from_v1_record(record)
    except (TypeError, ValueError) as exc:
        raise MeshProgramError(f"{where}: kernel fusion failed for {op_name}: {exc}") from exc
    _attach_mesh_program_operation_history(
        fused,
        source=target,
        op_name=op_name,
        modifier_name=modifier_name,
        modifier_payload=modifier_payload,
        feature_primitive_count=len(feature_primitives),
        component=component,
        region=region,
    )
    _apply_mesh_vertex_bounds(fused)
    _replace_primitives_in_program(primitives, (target,), (fused,))
    return fused


def _kernel_union_legacy_primitives(
    op_name: str,
    *,
    source_primitives: tuple[ShapePrimitive, ...],
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
    modifier_name: str,
    modifier_payload: dict[str, Any],
    tags: list[str],
    kernel_tag: str,
    component: str,
    region: str,
) -> ShapePrimitive:
    if not source_primitives:
        raise MeshProgramError(f"{where}: {op_name} produced no source geometry")
    from ..asset_quality.shape_ir_v2 import (
        ShapeOp,
        _kernel_union_record_for_records,
        _primitive_from_v1_record,
    )
    from ..geometry.kernel import resolve_geometry_kernel

    op = ShapeOp(
        op=_canonical_kernel_operation_for_mesh_program(op_name),
        target=part,
        parameters={},
        purpose=f"mesh_program.{op_name}",
    )
    try:
        record = _kernel_union_record_for_records(
            op,
            records=tuple(
                _source_record_for_primitive(primitive)
                for primitive in source_primitives
            ),
            geometry_kernel=resolve_geometry_kernel(),
            route=f"mesh_program_legacy_{op_name}",
            asset_name=f"mesh_program_legacy_{op_name}_sources",
            blueprint_id=f"mesh_program_legacy_{op_name}_sources",
            modifier_name=modifier_name,
            modifier_payload={
                **modifier_payload,
                "legacy_mesh_program_op": op_name,
                "source_primitive_count": len(source_primitives),
            },
            part=part,
            tags=tags,
            final_blend_mode="union",
            kernel_tag=kernel_tag,
            component=component,
            region=region,
        )
        fused = _primitive_from_v1_record(record)
    except (TypeError, ValueError) as exc:
        raise MeshProgramError(f"{where}: kernel union failed for {op_name}: {exc}") from exc
    _apply_mesh_vertex_bounds(fused)
    _replace_primitives_in_program(primitives, source_primitives, (fused,))
    return fused


def _primitive_kernel_semantic_handoff(primitive: ShapePrimitive) -> dict[str, Any]:
    metadata = primitive.semantic_metadata or {}
    direct = metadata.get("lathe_kernel_program_semantic_handoff")
    if isinstance(direct, dict):
        return direct
    kernel_metadata = metadata.get("kernel_result_metadata")
    if isinstance(kernel_metadata, dict):
        handoff = kernel_metadata.get("lathe_kernel_program_semantic_handoff")
        if isinstance(handoff, dict):
            return handoff
    return {}


def _primitive_has_pending_output_modifier(primitive: ShapePrimitive) -> bool:
    polybevel = primitive.v2_polybevel_modifier
    if isinstance(polybevel, dict) and polybevel:
        if "result_face_count" not in polybevel and "kernel_program" not in polybevel:
            return True
    return False


def _materialize_mesh_program_output_primitives(
    primitives: list[ShapePrimitive],
    *,
    part: str,
    where: str,
) -> list[ShapePrimitive]:
    if not primitives:
        return primitives
    if len(primitives) > 1:
        # The shape stage already compiles the complete ShapeIR primitive
        # program through the exact-surface path. Running a second whole-program
        # CSG solve here duplicates that work and can stall large authored
        # aggregates before the backend gets a chance to apply its bounded
        # fallback/diagnostic path.
        return primitives
    if all(_primitive_kernel_semantic_handoff(primitive) for primitive in primitives) and not any(
        _primitive_has_pending_output_modifier(primitive) for primitive in primitives
    ):
        return primitives
    from ..asset_quality.shape_ir_v2 import (
        ShapeOp,
        _kernel_import_record_for_single_source,
        _kernel_source_feature_records_boolean_record,
        _kernel_union_record_for_records,
        _primitive_from_v1_record,
    )
    from ..geometry.kernel import resolve_geometry_kernel

    records = tuple(_source_record_for_primitive(primitive) for primitive in primitives)
    op = ShapeOp(
        op="mesh_program.output_materialize",
        target=part,
        parameters={},
        purpose="mesh_program.output_materialize",
    )
    geometry_kernel = resolve_geometry_kernel()
    modifier_payload = {
        "method": "mesh_program_output_materialize_v1",
        "source_primitive_count": len(records),
        "source_primitive_types": [
            str(record.get("primitive_type") or "") for record in records
        ],
        "source_blend_modes": [
            str(record.get("blend_mode") or "union") for record in records
        ],
    }
    try:
        if len(records) == 1:
            record = _kernel_import_record_for_single_source(
                op,
                source_record=records[0],
                geometry_kernel=geometry_kernel,
                route="mesh_program_output_materialize",
                asset_name="mesh_program_output_materialize_source",
                blueprint_id="mesh_program_output_materialize_source",
                modifier_name="mesh_program_output_materialize_modifier",
                modifier_payload=modifier_payload,
                kernel_tag="mesh_program_output_materialize_kernel_program",
            )
        elif all(str(record.get("blend_mode") or "union") == "union" for record in records):
            record = _kernel_union_record_for_records(
                op,
                records=records,
                geometry_kernel=geometry_kernel,
                route="mesh_program_output_materialize",
                asset_name="mesh_program_output_materialize_sources",
                blueprint_id="mesh_program_output_materialize_sources",
                modifier_name="mesh_program_output_materialize_modifier",
                modifier_payload=modifier_payload,
                part=part,
                tags=["mesh_program_output", "mesh_program_output_materialized"],
                final_blend_mode="union",
                kernel_tag="mesh_program_output_materialize_kernel_program",
                component="mesh_program_output",
                region=f"{part}.mesh_program_output",
            )
        else:
            source_index = next(
                (
                    index
                    for index, record in enumerate(records)
                    if str(record.get("blend_mode") or "union") == "union"
                ),
                0,
            )
            source_record = records[source_index]
            feature_records = tuple(
                record for index, record in enumerate(records) if index != source_index
            )
            record = _kernel_source_feature_records_boolean_record(
                op,
                source_record=source_record,
                feature_records=feature_records,
                geometry_kernel=geometry_kernel,
                route="mesh_program_output_materialize",
                asset_name="mesh_program_output_materialize_boolean_source",
                blueprint_id="mesh_program_output_materialize_boolean_source",
                modifier_name="mesh_program_output_materialize_modifier",
                modifier_payload={
                    **modifier_payload,
                    "source_index": source_index,
                    "feature_record_count": len(feature_records),
                },
                kernel_tag="mesh_program_output_materialize_kernel_program",
                operation_tag="mesh_program_output_materialize",
                component="mesh_program_output",
                region=f"{part}.mesh_program_output",
            )
        fused = _primitive_from_v1_record(record)
    except (TypeError, ValueError) as exc:
        raise MeshProgramError(
            f"{where}: kernel materialization failed for mesh_program output: {exc}"
        ) from exc
    _apply_mesh_vertex_bounds(fused)
    _attach_mesh_program_operation_history(
        fused,
        source=primitives[0],
        op_name="mesh_program.output_materialize",
        modifier_name="mesh_program_output_materialize_modifier",
        modifier_payload=modifier_payload,
        feature_primitive_count=len(records),
        component="mesh_program_output",
        region=f"{part}.mesh_program_output",
        source_history=_mesh_program_operation_history_from_primitives(
            tuple(primitives)
        ),
    )
    _append_unique_tags(
        fused,
        (
            "mesh_program_output",
            "mesh_program_output_materialized",
            "mesh_program_output_materialize_kernel_program",
        ),
    )
    metadata = dict(fused.semantic_metadata or {})
    metadata["mesh_program_output_materialize"] = {
        "operation": "mesh_program.output_materialize",
        "source_primitive_count": len(records),
        "source_primitive_types": [
            str(record.get("primitive_type") or "") for record in records
        ],
        "source_blend_modes": [
            str(record.get("blend_mode") or "union") for record in records
        ],
        "materialized_as": "kernel_program.output_materialize",
        "kernel_program": True,
    }
    fused.semantic_metadata = metadata
    return [fused]


def _pop_target_primitives(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    where: str,
    part: str = "body",
) -> tuple[str, tuple[ShapePrimitive, ...]]:
    present = [name for name in ("target", "source") if name in kw]
    if len(present) != 1:
        raise MeshProgramError(f"{where}: requires exactly one of 'target' or 'source'")
    key = present[0]
    target_name, target_value = _pop_value_parameter(
        kw,
        bindings,
        name=key,
        allowed_kinds=("primitive",),
        part=part,
        where=where,
    )
    target_primitives = _value_primitives(target_value)
    if not target_primitives:
        raise MeshProgramError(f"{where}: target {target_name!r} has no primitives")
    return target_name, target_primitives


def _lower_v2_source_op(
    op_name: str,
    *,
    source_primitives: tuple[ShapePrimitive, ...],
    parameters: dict[str, Any],
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
    include_source_primitives: bool = False,
    use_geometry_kernel: bool = False,
    replace_source_primitives: bool = False,
    aggregate_source_primitives: bool = False,
) -> _Value:
    lowered: list[ShapePrimitive] = []
    geometry_kernel = None
    if use_geometry_kernel:
        from ..geometry.kernel import resolve_geometry_kernel

        geometry_kernel = resolve_geometry_kernel()
    if include_source_primitives:
        for source_primitive in source_primitives:
            if source_primitive not in primitives:
                primitives.append(source_primitive)
            lowered.append(source_primitive)
    if aggregate_source_primitives:
        lowered.extend(
            _v2_primitives_from_op(
                op_name,
                target=part,
                parameters={
                    **parameters,
                    "source": [
                        _source_record_for_primitive(source_primitive)
                        for source_primitive in source_primitives
                    ],
                },
                where=f"{where}[aggregate]",
                geometry_kernel=geometry_kernel,
            )
        )
    else:
        for index, source_primitive in enumerate(source_primitives):
            lowered.extend(
                _v2_primitives_from_op(
                    op_name,
                    target=part,
                    parameters={
                        **parameters,
                        "source": _source_record_for_primitive(source_primitive),
                    },
                    where=f"{where}[{index}]",
                    geometry_kernel=geometry_kernel,
                )
            )
    for primitive in lowered:
        _apply_mesh_vertex_bounds(primitive)
    if replace_source_primitives:
        if len(lowered) == len(source_primitives):
            lowered = [
                _copy_shape_primitive_payload(source_primitive, lowered_primitive)
                for source_primitive, lowered_primitive in zip(source_primitives, lowered, strict=False)
            ]
            for source_primitive in lowered:
                if source_primitive not in primitives:
                    primitives.append(source_primitive)
        else:
            _replace_primitives_in_program(
                primitives,
                source_primitives,
                tuple(lowered),
            )
    else:
        for primitive in lowered:
            if primitive not in primitives:
                primitives.append(primitive)
    return _primitive_value(lowered)


def _lower_bound_v2_source_op(
    v2_op_name: str,
    *,
    mesh_program_op_name: str,
    target_name: str,
    bindings: dict[str, _Value],
    source_primitives: tuple[ShapePrimitive, ...],
    parameters: dict[str, Any],
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
    modifier_name: str,
    feature_primitive_count: int,
    component: str,
    region: str,
) -> _Value:
    source = source_primitives[0]
    source_history = _mesh_program_operation_history_from_primitives(
        source_primitives
    )
    result = _lower_v2_source_op(
        v2_op_name,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        use_geometry_kernel=True,
        replace_source_primitives=True,
    )
    result_primitives = _value_primitives(result)
    for primitive in result_primitives:
        _attach_mesh_program_operation_history(
            primitive,
            source=source,
            op_name=mesh_program_op_name,
            modifier_name=modifier_name,
            modifier_payload=parameters,
            feature_primitive_count=feature_primitive_count,
            source_history=source_history,
            component=component,
            region=region,
        )
    _replace_value_primitives(bindings[target_name], result_primitives)
    return _Value(
        kind="primitive",
        primitive=result.primitive,
        primitives=result_primitives,
        bevel_target=result.bevel_target,
    )


def _lower_v2_literal_op(
    op_name: str,
    *,
    parameters: dict[str, Any],
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
    use_geometry_kernel: bool = False,
) -> _Value:
    geometry_kernel = None
    if use_geometry_kernel:
        from ..geometry.kernel import resolve_geometry_kernel

        geometry_kernel = resolve_geometry_kernel()
    lowered = _v2_primitives_from_op(
        op_name,
        target=part,
        parameters=parameters,
        where=where,
        geometry_kernel=geometry_kernel,
    )
    for primitive in lowered:
        _apply_mesh_vertex_bounds(primitive)
    for primitive in lowered:
        if primitive not in primitives:
            primitives.append(primitive)
    return _primitive_value(lowered)


def _pop_optional_deform_common(kw: dict[str, Any], parameters: dict[str, Any], *, where: str) -> None:
    origin = _pop_optional_center(kw, where=where)
    if origin is not None:
        parameters["origin"] = origin
    for name in ("segments", "subdivision_levels"):
        value = _pop_int_alias(kw, where=where, names=(name,))
        if value is not None:
            parameters[name] = value


def _pop_optional_blend_parameter(kw: dict[str, Any], parameters: dict[str, Any], *, where: str) -> None:
    if "blend_mode" in kw or "blend" in kw:
        parameters["blend_mode"] = _pop_blend_mode(kw, where=where)


def _pop_optional_center_parameter(kw: dict[str, Any], parameters: dict[str, Any], *, where: str) -> None:
    center = _pop_optional_center(kw, where=where)
    if center is not None:
        parameters["center"] = center


def _pop_optional_axis_parameter(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    name: str,
    default: str | None = None,
) -> None:
    if name in kw:
        axis = _axis_arg(kw.pop(name), where=f"{where}.{name}")
        existing_axis = parameters.get(name)
        if existing_axis is not None and str(existing_axis) != axis:
            raise MeshProgramError(
                f"{where}.{name}: axis {axis!r} conflicts with existing {name} {existing_axis!r}"
            )
        parameters[name] = axis
    elif default is not None:
        parameters.setdefault(name, default)


def _pop_optional_side_parameter(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    name: str,
    default: str | None = None,
) -> None:
    value = _pop_string_alias(
        kw,
        where=where,
        names=(name,),
        default=default,
        allowed={"positive", "negative"},
    )
    if value is not None:
        existing_side = parameters.get(name)
        if existing_side is not None and str(existing_side) != value:
            raise MeshProgramError(
                f"{where}.{name}: side {value!r} conflicts with existing {name} {existing_side!r}"
            )
        parameters[name] = value


def _pop_optional_length_parameter(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    target: str,
    names: tuple[str, ...],
) -> None:
    value = _pop_length_alias(kw, where=where, names=names)
    if value is not None:
        parameters[target] = value


def _pop_optional_radius_or_diameter_parameter(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    target: str,
    radius_names: tuple[str, ...],
    diameter_names: tuple[str, ...],
) -> None:
    value = _pop_radius_or_diameter(
        kw,
        where=where,
        radius_names=radius_names,
        diameter_names=diameter_names,
    )
    if value is not None:
        parameters[target] = value


def _pop_optional_number_parameter(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    target: str,
    names: tuple[str, ...],
) -> None:
    value = _pop_number_alias(kw, where=where, names=names)
    if value is not None:
        parameters[target] = value


def _inline_parameter_label(name: str, raw: Any) -> str:
    return f"inline_{name}_{_stable_seed(raw):08x}"


def _pop_value_parameter(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    name: str,
    allowed_kinds: tuple[str, ...],
    part: str,
    where: str,
) -> tuple[str, _Value]:
    if name not in kw:
        raise MeshProgramError(f"{where}: requires '{name}'")
    raw = kw.pop(name)
    if isinstance(raw, str):
        ident_name = _ident(raw, where=f"{where}.{name}")
        if ident_name not in bindings:
            raise MeshProgramError(
                f"{where}: {name!r} references unknown identifier {ident_name!r}"
            )
        value = bindings[ident_name]
        label = ident_name
    elif isinstance(raw, dict):
        scratch_primitives: list[ShapePrimitive] = []
        value = _eval_expr(
            raw,
            bindings,
            part=part,
            where=f"{where}.{name}",
            primitives=scratch_primitives,
        )
        label = _inline_parameter_label(name, raw)
    else:
        raise MeshProgramError(
            f"{where}.{name}: expected an identifier or inline expression, got {raw!r}"
        )
    if value.kind not in allowed_kinds:
        raise MeshProgramError(
            f"{where}.{name}: expected {sorted(allowed_kinds)}, got kind={value.kind!r}"
        )
    if value.kind == "primitive" and not _value_primitives(value):
        raise MeshProgramError(f"{where}.{name}: primitive value has no primitives")
    if value.kind == "sdf" and value.sdf_expr is None:
        raise MeshProgramError(f"{where}.{name}: SDF value has no expression")
    return label, value


def _pop_points_parameter_with_label(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    where: str,
    name: str = "points",
    part: str = "body",
) -> tuple[str, list[tuple[float, float, float]]]:
    if name not in kw:
        raise MeshProgramError(f"{where}: requires '{name}'")
    raw = kw.pop(name)
    if isinstance(raw, str):
        ident_name = _ident(raw, where=f"{where}.{name}")
        if ident_name not in bindings:
            raise MeshProgramError(
                f"{where}.{name}: references unknown point_set identifier {ident_name!r}"
            )
        binding = bindings[ident_name]
        if binding.kind != "point_set" or binding.points is None:
            raise MeshProgramError(
                f"{where}.{name}: {ident_name!r} must reference a point_set binding, "
                f"got kind={binding.kind!r}"
            )
        return ident_name, list(binding.points)
    if isinstance(raw, dict):
        value = _eval_expr(
            raw,
            bindings,
            part=part,
            where=f"{where}.{name}",
            primitives=None,
        )
        if value.kind != "point_set" or value.points is None:
            raise MeshProgramError(
                f"{where}.{name}: inline expression must evaluate to point_set, "
                f"got kind={value.kind!r}"
            )
        return _inline_parameter_label(name, raw), list(value.points)
    return (
        _inline_parameter_label(name, raw),
        _vec3_length_points(raw, where=f"{where}.{name}", min_points=1),
    )


def _pop_points_parameter(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    where: str,
    name: str = "points",
    part: str = "body",
) -> list[tuple[float, float, float]]:
    _, points = _pop_points_parameter_with_label(
        kw,
        bindings,
        where=where,
        name=name,
        part=part,
    )
    return points


def _source_records_from_binding_value(
    value: Any,
    bindings: dict[str, _Value],
    *,
    where: str,
    part: str = "body",
) -> list[dict[str, Any]]:
    _, source_primitives = _named_primitives_from_binding_value(
        value,
        bindings,
        where=where,
        part=part,
    )
    return [_source_record_for_primitive(primitive) for primitive in source_primitives]


def _primitives_from_binding_value(
    value: Any,
    bindings: dict[str, _Value],
    *,
    where: str,
    part: str = "body",
) -> tuple[ShapePrimitive, ...]:
    _, source_primitives = _named_primitives_from_binding_value(
        value,
        bindings,
        where=where,
        part=part,
    )
    return source_primitives


def _named_primitives_from_binding_value(
    value: Any,
    bindings: dict[str, _Value],
    *,
    where: str,
    part: str = "body",
) -> tuple[str, tuple[ShapePrimitive, ...]]:
    if isinstance(value, str):
        ident_name = _ident(value, where=where)
        if ident_name not in bindings or bindings[ident_name].kind != "primitive":
            raise MeshProgramError(
                f"{where}: must reference a primitive let-binding, got {ident_name!r}"
            )
        resolved = bindings[ident_name]
        label = ident_name
    elif isinstance(value, dict):
        scratch_primitives: list[ShapePrimitive] = []
        resolved = _eval_expr(
            value,
            bindings,
            part=part,
            where=where,
            primitives=scratch_primitives,
        )
        label = _inline_parameter_label("source", value)
        if resolved.kind != "primitive":
            raise MeshProgramError(
                f"{where}: inline expression must produce primitive geometry, "
                f"got kind={resolved.kind!r}"
            )
    else:
        raise MeshProgramError(
            f"{where}: expected a primitive identifier or inline expression, got {value!r}"
        )
    source_primitives = _value_primitives(resolved)
    if not source_primitives:
        raise MeshProgramError(f"{where}: binding {label!r} has no primitives")
    return (label, source_primitives)


def _pop_source_primitives_parameter(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    where: str,
    part: str = "body",
) -> tuple[tuple[str, ...], tuple[ShapePrimitive, ...]]:
    names: list[str] = []
    primitives: list[ShapePrimitive] = []
    sources_key = "sources" if "sources" in kw else "cutters" if "cutters" in kw else ""
    if sources_key:
        raw_sources = kw.pop(sources_key)
        if not isinstance(raw_sources, list) or not raw_sources:
            raise MeshProgramError(
                f"{where}.{sources_key}: expected a non-empty primitive list"
            )
        for index, raw_source in enumerate(raw_sources):
            name, source_primitives = _named_primitives_from_binding_value(
                raw_source,
                bindings,
                where=f"{where}.{sources_key}[{index}]",
                part=part,
            )
            names.append(name)
            primitives.extend(source_primitives)
        return tuple(names), tuple(primitives)
    source_key = next(
        (
            key
            for key in ("source", "target", "b", "cutter", "operand", "other", "with")
            if key in kw
        ),
        "",
    )
    if not source_key:
        raise MeshProgramError(f"{where}: requires 'source', 'target', or 'sources'")
    name, source_primitives = _named_primitives_from_binding_value(
        kw.pop(source_key),
        bindings,
        where=f"{where}.{source_key}",
        part=part,
    )
    return (name,), source_primitives


def _pop_source_records_parameter(
    kw: dict[str, Any],
    bindings: dict[str, _Value],
    *,
    where: str,
    part: str = "body",
) -> list[dict[str, Any]]:
    sources_key = "sources" if "sources" in kw else "cutters" if "cutters" in kw else ""
    if sources_key:
        raw_sources = kw.pop(sources_key)
        if not isinstance(raw_sources, list) or not raw_sources:
            raise MeshProgramError(
                f"{where}.{sources_key}: expected a non-empty primitive list"
            )
        records: list[dict[str, Any]] = []
        for index, raw_source in enumerate(raw_sources):
            records.extend(
                _source_records_from_binding_value(
                    raw_source,
                    bindings,
                    where=f"{where}.{sources_key}[{index}]",
                    part=part,
                )
            )
        return records
    source_key = next(
        (
            key
            for key in ("source", "target", "b", "cutter", "operand", "other", "with")
            if key in kw
        ),
        "",
    )
    if not source_key:
        raise MeshProgramError(f"{where}: requires 'source', 'target', or 'sources'")
    return _source_records_from_binding_value(
        kw.pop(source_key),
        bindings,
        where=f"{where}.{source_key}",
        part=part,
    )


def _emit_primitives_from_value(
    value: Any,
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _emit_primitives_from_value(
                item,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}[{index}]",
            )
        return
    if isinstance(value, dict):
        resolved = _eval_expr(
            value,
            bindings,
            part=part,
            where=where,
            primitives=primitives,
        )
    else:
        ident_name = _ident(value, where=where)
        if ident_name not in bindings:
            raise MeshProgramError(f"{where}: unknown identifier {ident_name!r}")
        resolved = bindings[ident_name]
    if resolved.kind != "primitive":
        raise MeshProgramError(f"{where}: emit(...) requires primitive geometry, got {resolved.kind!r}")
    emitted = _value_primitives(resolved)
    if not emitted:
        raise MeshProgramError(f"{where}: primitive binding has no geometry")
    for primitive in emitted:
        primitive.part = part
        if primitive not in primitives:
            primitives.append(primitive)


def _apply_emit(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> None:
    if not args:
        raise MeshProgramError(f"{where}: emit(...) requires at least one primitive")
    accepted_names = {None, "source", "target", "primitive", "value", "sources"}
    for arg_index, arg in enumerate(args):
        name = arg.get("name")
        if name not in accepted_names:
            raise MeshProgramError(
                f"{where}: unsupported emit(...) argument {name!r} "
                "(supported: positional, source, target, primitive, value, sources)"
            )
        value = arg.get("value")
        if name == "sources":
            if not isinstance(value, list) or not value:
                raise MeshProgramError(f"{where}.sources: expected a non-empty identifier list")
            _emit_primitives_from_value(
                value,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.sources",
            )
        else:
            suffix = str(name) if name is not None else str(arg_index)
            _emit_primitives_from_value(
                value,
                bindings,
                primitives=primitives,
                part=part,
                where=f"{where}.{suffix}",
            )


def _method_chain_root_ident(expr: Any) -> str | None:
    cursor = expr
    while isinstance(cursor, dict) and cursor.get("type") == "method_call":
        cursor = cursor.get("receiver")
    if isinstance(cursor, dict) and cursor.get("type") == "ident":
        name = cursor.get("name")
        if isinstance(name, str) and name:
            return name
    return None


def _pop_instance_variation_parameters(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
) -> None:
    for target, names in (
        ("seed", ("seed",)),
        ("scale", ("scale", "uniform_scale", "instance_scale")),
        ("scale_min", ("scale_min", "min_scale", "instance_scale_min")),
        ("scale_max", ("scale_max", "max_scale", "instance_scale_max")),
        ("scale_variation", ("scale_variation", "scale_jitter", "instance_scale_jitter")),
    ):
        value = _pop_number_alias(kw, where=where, names=names)
        if value is not None:
            parameters[target] = value
    for target, names in (
        ("jitter_cm", ("jitter", "jitter_cm")),
        ("snap_cm", ("snap", "snap_cm", "snap_to_grid", "snap_to_grid_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=target, names=names)
    for target, names in (
        (
            "roll_degrees",
            (
                "roll_degrees",
                "roll_deg",
                "rotation_degrees",
                "rotation_deg",
                "instance_roll_degrees",
                "instance_rotation_degrees",
            ),
        ),
        (
            "roll_min_degrees",
            (
                "roll_min_degrees",
                "roll_min_deg",
                "rotation_min_degrees",
                "rotation_min_deg",
                "instance_roll_min_degrees",
                "instance_rotation_min_degrees",
            ),
        ),
        (
            "roll_max_degrees",
            (
                "roll_max_degrees",
                "roll_max_deg",
                "rotation_max_degrees",
                "rotation_max_deg",
                "instance_roll_max_degrees",
                "instance_rotation_max_degrees",
            ),
        ),
        (
            "roll_jitter_degrees",
            (
                "roll_jitter_degrees",
                "roll_jitter_deg",
                "rotation_jitter_degrees",
                "rotation_jitter_deg",
                "instance_roll_jitter_degrees",
                "instance_rotation_jitter_degrees",
            ),
        ),
    ):
        value = _pop_angle_alias(kw, where=where, names=names)
        if value is not None:
            parameters[target] = value


def _pop_optional_axes_parameter(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    name: str = "axes",
) -> None:
    if name not in kw:
        return
    raw = kw.pop(name)
    if not isinstance(raw, list) or not raw:
        raise MeshProgramError(f"{where}.{name}: expected a non-empty axis list")
    axes: list[str] = []
    for index, value in enumerate(raw):
        axis = _axis_arg(value, where=f"{where}.{name}[{index}]")
        if axis not in axes:
            axes.append(axis)
    parameters[name] = axes


def _pop_common_attachment_parameters(kw: dict[str, Any], parameters: dict[str, Any], *, where: str) -> None:
    _pop_optional_length_parameter(kw, parameters, where=where, target="seat_depth_cm", names=("seat_depth", "seat_depth_cm"))
    _pop_optional_number_parameter(kw, parameters, where=where, target="normal_sign", names=("normal_sign",))
    _pop_optional_length_parameter(kw, parameters, where=where, target="bevel_width_cm", names=("bevel_width", "bevel_width_cm"))
    _pop_optional_number_parameter(kw, parameters, where=where, target="bevel_segments", names=("bevel_segments",))
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)


def _pop_detail_face_alias(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
) -> None:
    face_value = kw.pop("face", None)
    if face_value is None:
        return
    face = _face_arg(face_value, where=f"{where}.face")
    normal_axis = face[1]
    side = "positive" if face[0] == "+" else "negative"
    existing_axis = parameters.get("normal_axis")
    if existing_axis is not None and str(existing_axis) != normal_axis:
        raise MeshProgramError(
            f"{where}.face: face axis {normal_axis!r} conflicts with normal_axis {existing_axis!r}"
        )
    existing_side = parameters.get("side")
    if existing_side is not None and str(existing_side) != side:
        raise MeshProgramError(
            f"{where}.face: face side {side!r} conflicts with side {existing_side!r}"
        )
    parameters["normal_axis"] = normal_axis
    parameters["side"] = side


def _pop_detail_mask_parameters(kw: dict[str, Any], parameters: dict[str, Any], *, where: str) -> None:
    _pop_detail_face_alias(kw, parameters, where=where)
    normal_axis, normal_axis_name = _pop_surface_normal_axis_alias(
        kw,
        where=where,
        names=("normal_axis", "surface_axis", "face_axis", "axis"),
    )
    if normal_axis is not None:
        existing_axis = parameters.get("normal_axis")
        if existing_axis is not None and str(existing_axis) != normal_axis:
            raise MeshProgramError(
                f"{where}.{normal_axis_name}: axis {normal_axis!r} conflicts with face axis {existing_axis!r}"
            )
        parameters["normal_axis"] = normal_axis
    elif "normal_axis" not in parameters:
        parameters["normal_axis"] = "z"
    _pop_surface_side_parameter_with_default(
        kw,
        parameters,
        where=where,
        name="side",
        aliases=(),
        default="positive",
    )
    _pop_optional_axis_parameter(kw, parameters, where=where, name="line_axis", default=None)
    _pop_optional_axis_parameter(kw, parameters, where=where, name="row_axis", default=None)
    count = _pop_int_alias(kw, where=where, names=("count",))
    if count is not None:
        parameters["count"] = count
    for target, names in (
        ("length_cm", ("length", "length_cm")),
        ("width_cm", ("width", "width_cm")),
        ("depth_cm", ("depth", "depth_cm")),
        ("radius_cm", ("radius", "radius_cm")),
        ("thickness_cm", ("thickness", "thickness_cm")),
        ("spacing_cm", ("spacing", "spacing_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=target, names=names)
    _pop_optional_blend_parameter(kw, parameters, where=where)


def _apply_sop_polybevel(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {
        "width_cm": _pop_length_alias(
            kw,
            where=where,
            names=("width", "width_cm", "bevel_width", "bevel_width_cm"),
            required=True,
        ),
        "segments": _pop_int_alias(kw, where=where, names=("segments",), default=2),
    }
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_polybevel(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.polybevel",
        mesh_program_op_name="sop_polybevel",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_polybevel_modifier",
        feature_primitive_count=1,
        component="polybevel",
        region=f"{part}.polybevel",
    )


def _apply_sop_subdivide(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {
        "levels": _pop_int_alias(kw, where=where, names=("levels",), required=True),
    }
    scheme = _pop_string_alias(kw, where=where, names=("scheme",), default="catmull_clark")
    if scheme is not None:
        parameters["scheme"] = scheme
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_subdivide(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.subdivide",
        mesh_program_op_name="sop_subdivide",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_subdivision_modifier",
        feature_primitive_count=1,
        component="subdivide",
        region=f"{part}.subdivide",
    )


def _apply_sop_remesh(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {
        "target_edge_length_cm": _pop_length_alias(
            kw,
            where=where,
            names=("target_edge_length", "target_edge_length_cm", "edge_length", "edge_length_cm"),
            required=True,
        ),
    }
    mode = _pop_string_alias(
        kw,
        where=where,
        names=("mode",),
        default="adaptive",
        allowed={"adaptive", "uniform", "quadric"},
    )
    if mode is not None:
        parameters["mode"] = mode
    max_iterations = _pop_int_alias(kw, where=where, names=("max_iterations",))
    if max_iterations is not None:
        parameters["max_iterations"] = max_iterations
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_remesh(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.remesh",
        mesh_program_op_name="sop_remesh",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_remesh_modifier",
        feature_primitive_count=1,
        component="remesh",
        region=f"{part}.remesh",
    )


def _apply_sop_twist(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    angle = _pop_angle_alias(
        kw,
        where=where,
        names=("angle_degrees", "angle", "angle_radians", "radians"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "angle_degrees": angle,
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y"),
    }
    _pop_optional_deform_common(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_twist(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.twist",
        mesh_program_op_name="sop_twist",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_deform_modifier",
        feature_primitive_count=1,
        component="twist",
        region=f"{part}.twist",
    )


def _apply_sop_taper(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    if "scale" not in kw:
        raise MeshProgramError(f"{where}: sop_taper(...) requires 'scale'")
    raw_scale = kw.pop("scale")
    if isinstance(raw_scale, list):
        if len(raw_scale) != 2:
            raise MeshProgramError(f"{where}.scale: expected a number or [start, end]")
        scale: float | list[float] = [
            _number_arg(raw_scale[0], where=f"{where}.scale[0]"),
            _number_arg(raw_scale[1], where=f"{where}.scale[1]"),
        ]
    else:
        scale = _number_arg(raw_scale, where=f"{where}.scale")
    parameters: dict[str, Any] = {
        "scale": scale,
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y"),
    }
    start_scale = _pop_number_alias(kw, where=where, names=("start_scale",))
    if start_scale is not None:
        parameters["start_scale"] = start_scale
    _pop_optional_deform_common(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_taper(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.taper",
        mesh_program_op_name="sop_taper",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_deform_modifier",
        feature_primitive_count=1,
        component="taper",
        region=f"{part}.taper",
    )


def _apply_sop_bend(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    angle = _pop_angle_alias(
        kw,
        where=where,
        names=("angle_degrees", "angle", "angle_radians", "radians"),
        required=True,
    )
    parameters: dict[str, Any] = {
        "angle_degrees": angle,
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis", default="y"),
    }
    direction_axis = _pop_string_alias(
        kw,
        where=where,
        names=("direction_axis", "bend_axis"),
        allowed={"x", "y", "z"},
    )
    if direction_axis is not None:
        parameters["direction_axis"] = direction_axis
    _pop_optional_deform_common(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_bend(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.bend",
        mesh_program_op_name="sop_bend",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_deform_modifier",
        feature_primitive_count=1,
        component="bend",
        region=f"{part}.bend",
    )


def _apply_sop_polyextrude(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    if "target" in kw or "source" in kw:
        target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
        parameters: dict[str, Any] = {}
        distance = _pop_length_alias(
            kw,
            where=where,
            names=("distance", "distance_cm", "height", "height_cm", "extrude_height", "extrude_height_cm"),
            required=True,
        )
        face_side: str | None = None
        face_value = kw.pop("face", None)
        if face_value is not None:
            face = _face_arg(face_value, where=f"{where}.face")
            parameters["axis"] = face[1]
            face_side = "positive" if face[0] == "+" else "negative"
        side = _pop_string_alias(
            kw,
            where=where,
            names=("side",),
            allowed={"positive", "negative"},
        )
        if side is not None and face_side is not None and side != face_side:
            raise MeshProgramError(
                f"{where}.side: side {side!r} conflicts with face side {face_side!r}"
            )
        side = side or face_side
        if side is not None:
            distance = abs(float(distance)) if side == "positive" else -abs(float(distance))
        parameters["distance_cm"] = distance
        _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
        _pop_optional_center_parameter(kw, parameters, where=where)
        _pop_optional_blend_parameter(kw, parameters, where=where)
        if kw:
            unknown = sorted(kw.keys())
            raise MeshProgramError(f"{where}: unknown sop_polyextrude(...) argument(s): {unknown}")
        return _lower_bound_v2_source_op(
            "sop.polyextrude",
            mesh_program_op_name="sop_polyextrude",
            target_name=target_name,
            bindings=bindings,
            source_primitives=source_primitives,
            parameters=parameters,
            primitives=primitives,
            part=part,
            where=where,
            modifier_name="v2_polyextrude_modifier",
            feature_primitive_count=1,
            component="polyextrude",
            region=f"{part}.polyextrude",
        )

    profile_polygon = _pop_profile_points(
        kw,
        where=where,
        names=("profile", "profile_polygon", "profile_points"),
        min_points=3,
    )
    height = _pop_length_alias(
        kw,
        where=where,
        names=("height", "height_cm", "extrude_height", "extrude_height_cm", "distance", "distance_cm"),
        required=True,
    )
    parameters = {
        "profile_polygon": profile_polygon,
        "extrude_height_cm": height,
    }
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="y")
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_polyextrude(...) argument(s): {unknown}")
    return _lower_v2_literal_op(
        "sop.polyextrude",
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        use_geometry_kernel=True,
    )


def _apply_sop_transform(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {}
    for names, target in (
        (("translation", "translate", "translation_cm", "translate_cm"), "translation_cm"),
        (("origin",), "origin"),
    ):
        present = [name for name in names if name in kw]
        if len(present) > 1:
            raise MeshProgramError(
                f"{where}: only one of {', '.join(repr(name) for name in names)} may be supplied"
            )
        if present:
            name = present[0]
            parameters[target] = _vec3(kw.pop(name), where=f"{where}.{name}")
    scale = _pop_number_alias(kw, where=where, names=("scale",))
    if scale is not None:
        parameters["scale"] = scale
    _pop_optional_axis_parameter(kw, parameters, where=where, name="rotation_axis", default=None)
    present_rotation = [
        name
        for name in (
            "rotation_degrees_xyz",
            "rotate_degrees_xyz",
            "euler_degrees",
            "rotation_euler_degrees",
        )
        if name in kw
    ]
    if len(present_rotation) > 1:
        raise MeshProgramError(
            f"{where}: only one rotation vector argument may be supplied"
        )
    if present_rotation:
        name = present_rotation[0]
        raw = kw.pop(name)
        if not isinstance(raw, list) or len(raw) != 3:
            raise MeshProgramError(f"{where}.{name}: expected [x, y, z] degrees")
        parameters[name] = [
            _number_arg(raw[index], where=f"{where}.{name}[{index}]")
            for index in range(3)
        ]
    else:
        rotation = _pop_angle_alias(
            kw,
            where=where,
            names=("rotation_degrees", "rotate_degrees", "rotation_deg", "rotate_deg", "angle_degrees", "angle", "radians"),
        )
        if rotation is not None:
            parameters["rotation_degrees"] = rotation
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_transform(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.transform",
        mesh_program_op_name="sop_transform",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_transform_modifier",
        feature_primitive_count=1,
        component="transform",
        region=f"{part}.transform",
    )


def _apply_sop_carve(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "u_start": _pop_number_alias(kw, where=where, names=("u_start", "start"), required=True),
        "u_end": _pop_number_alias(kw, where=where, names=("u_end", "end"), required=True),
    }
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_carve(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.carve",
        mesh_program_op_name="sop_carve",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_carve_modifier",
        feature_primitive_count=1,
        component="carve",
        region=f"{part}.carve",
    )


def _apply_op_extrude(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "depth_cm": _pop_length_alias(
            kw,
            where=where,
            names=("depth", "depth_cm", "distance", "distance_cm"),
            required=True,
        ),
    }
    face_value = kw.pop("face", None)
    if face_value is not None:
        face = _face_arg(face_value, where=f"{where}.face")
        parameters["axis"] = face[1]
        parameters["side"] = "positive" if face[0] == "+" else "negative"
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="z")
    _pop_surface_side_parameter_with_default(
        kw,
        parameters,
        where=where,
        name="side",
        aliases=(),
        default="positive",
    )
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_extrude(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.extrude",
        mesh_program_op_name="op_extrude",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_extrude_modifier",
        feature_primitive_count=1,
        component="extrude",
        region=f"{part}.extrude",
    )


def _apply_op_shell(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "thickness_cm": _pop_length_alias(
            kw,
            where=where,
            names=("thickness", "thickness_cm"),
            required=True,
        ),
    }
    face_value = kw.pop("face", None)
    if face_value is not None:
        face = _face_arg(face_value, where=f"{where}.face")
        parameters["open_axis"] = face[1]
        parameters["open_side"] = "positive" if face[0] == "+" else "negative"
    open_axis, open_axis_name = _pop_surface_normal_axis_alias(
        kw,
        where=where,
        names=("open_axis", "normal_axis", "surface_axis", "face_axis", "axis"),
    )
    if open_axis is not None:
        existing_axis = parameters.get("open_axis")
        if existing_axis is not None and str(existing_axis) != open_axis:
            raise MeshProgramError(
                f"{where}.{open_axis_name}: axis {open_axis!r} conflicts with face axis {existing_axis!r}"
            )
        parameters["open_axis"] = open_axis
    elif "open_axis" not in parameters:
        parameters["open_axis"] = "z"
    _pop_surface_side_parameter_with_default(
        kw,
        parameters,
        where=where,
        name="open_side",
        aliases=("side",),
        default="positive",
    )
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_shell(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.shell",
        mesh_program_op_name="op_shell",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_shell_modifier",
        feature_primitive_count=2,
        component="shell",
        region=f"{part}.shell",
    )


def _apply_op_inset(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "depth_cm": _pop_length_alias(kw, where=where, names=("depth", "depth_cm"), required=True),
    }
    face_value = kw.pop("face", None)
    if face_value is not None:
        face = _face_arg(face_value, where=f"{where}.face")
        parameters["normal_axis"] = face[1]
        parameters["side"] = "positive" if face[0] == "+" else "negative"
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="normal_axis", default="z")
    side = _pop_string_alias(
        kw,
        where=where,
        names=("side",),
        allowed={"positive", "negative"},
    )
    if side is not None:
        existing_side = parameters.get("side")
        if existing_side is not None and existing_side != side:
            raise MeshProgramError(
                f"{where}.side: side {side!r} conflicts with face side {existing_side!r}"
            )
        parameters["side"] = side
    elif "side" not in parameters:
        parameters["side"] = "positive"
    _pop_optional_length_parameter(kw, parameters, where=where, target="margin_cm", names=("margin", "margin_cm"))
    _pop_optional_length_parameter(kw, parameters, where=where, target="bevel_width_cm", names=("bevel_width", "bevel_width_cm"))
    _pop_optional_number_parameter(kw, parameters, where=where, target="bevel_segments", names=("bevel_segments",))
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_inset(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.inset",
        mesh_program_op_name="op_inset",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_inset_modifier",
        feature_primitive_count=1,
        component="inset",
        region=f"{part}.inset",
    )


def _apply_op_cut_panel_line(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "width_cm": _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True),
    }
    _pop_optional_length_parameter(kw, parameters, where=where, target="depth_cm", names=("depth", "depth_cm"))
    _pop_optional_length_parameter(kw, parameters, where=where, target="length_cm", names=("length", "length_cm"))
    _pop_optional_axis_parameter(kw, parameters, where=where, name="line_axis", default="x")
    _pop_optional_number_parameter(kw, parameters, where=where, target="normal_sign", names=("normal_sign",))
    _pop_face_axis_alias(kw, parameters, where=where, axis_name="normal_axis")
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="normal_axis", default="z")
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    _pop_optional_length_parameter(kw, parameters, where=where, target="seat_depth_cm", names=("seat_depth", "seat_depth_cm"))
    _pop_optional_length_parameter(kw, parameters, where=where, target="bevel_width_cm", names=("bevel_width", "bevel_width_cm"))
    _pop_optional_number_parameter(kw, parameters, where=where, target="bevel_segments", names=("bevel_segments",))
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_cut_panel_line(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.cut_panel_line",
        mesh_program_op_name="op_cut_panel_line",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_cut_panel_line_modifier",
        feature_primitive_count=1,
        component="panel_line_cut",
        region=f"{part}.panel_line",
    )


def _pop_face_axis_alias(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    axis_name: str = "axis",
) -> None:
    face_value = kw.pop("face", None)
    if face_value is None:
        return
    face = _face_arg(face_value, where=f"{where}.face")
    axis = face[1]
    normal_sign = 1.0 if face[0] == "+" else -1.0
    existing_axis = parameters.get(axis_name)
    if existing_axis is not None and str(existing_axis) != axis:
        raise MeshProgramError(
            f"{where}.face: face axis {axis!r} conflicts with axis {existing_axis!r}"
        )
    existing_sign = parameters.get("normal_sign")
    if existing_sign is not None and (float(existing_sign) < 0.0) != (normal_sign < 0.0):
        raise MeshProgramError(
            f"{where}.face: face sign {face[0]!r} conflicts with normal_sign {existing_sign!r}"
        )
    parameters[axis_name] = axis
    parameters["normal_sign"] = normal_sign


def _pop_z_face_normal_sign_alias(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
) -> None:
    face_value = kw.pop("face", None)
    if face_value is None:
        return
    face = _face_arg(face_value, where=f"{where}.face")
    if face[1] != "z":
        raise MeshProgramError(f"{where}.face: only +/-z is supported for this operation")
    normal_sign = 1.0 if face[0] == "+" else -1.0
    existing_sign = parameters.get("normal_sign")
    if existing_sign is not None and (float(existing_sign) < 0.0) != (normal_sign < 0.0):
        raise MeshProgramError(
            f"{where}.face: face sign {face[0]!r} conflicts with normal_sign {existing_sign!r}"
        )
    parameters["normal_sign"] = normal_sign


def _tangent_axis_defaults(normal_axis: str) -> tuple[str, str]:
    if normal_axis == "x":
        return "y", "z"
    if normal_axis == "y":
        return "x", "z"
    return "x", "y"


def _pop_corner_signs_face_alias(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
) -> None:
    face_value = kw.pop("face", None)
    if face_value is None:
        return
    face = _face_arg(face_value, where=f"{where}.face")
    sign = 1.0 if face[0] == "+" else -1.0
    axis_index = {"x": 0, "y": 1, "z": 2}[face[1]]
    signs: list[list[float]] = []
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            for z_sign in (-1.0, 1.0):
                values = [x_sign, y_sign, z_sign]
                if values[axis_index] == sign:
                    signs.append(values)
    parameters["corner_signs"] = signs


def _corner_signs_for_surface_axis(axis: str, sign: float) -> list[list[float]]:
    axis_index = _axis_to_index(axis)
    signs: list[list[float]] = []
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            for z_sign in (-1.0, 1.0):
                values = [x_sign, y_sign, z_sign]
                if values[axis_index] == sign:
                    signs.append(values)
    return signs


def _corner_signs_match_surface(
    signs: Any,
    *,
    axis: str,
    sign: float,
) -> bool:
    if not isinstance(signs, list):
        return False
    axis_index = _axis_to_index(axis)
    for raw in signs:
        if not isinstance(raw, (list, tuple)) or len(raw) != 3:
            return False
        if (float(raw[axis_index]) < 0.0) != (sign < 0.0):
            return False
    return True


def _pop_axis_parameter_with_default(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    name: str,
    default: str | None = None,
) -> None:
    if name == "axis":
        axis_names = (name, "normal_axis")
    elif name == "plane_axis":
        axis_names = (name, "normal_axis", "plane_normal_axis")
    else:
        axis_names = (name,)
    present = [candidate for candidate in axis_names if candidate in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one of {', '.join(repr(candidate) for candidate in axis_names)} may be supplied"
        )
    raw_axis = kw.pop(present[0], None) if present else None
    if raw_axis is not None:
        axis = _axis_arg(raw_axis, where=f"{where}.{present[0] if present else name}")
        existing_axis = parameters.get(name)
        if existing_axis is not None and str(existing_axis) != axis:
            raise MeshProgramError(
                f"{where}.{present[0] if present else name}: axis {axis!r} conflicts with face axis {existing_axis!r}"
            )
        parameters[name] = axis
    elif name not in parameters and default is not None:
        parameters[name] = default


def _pop_surface_side_parameter_with_default(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
    name: str,
    aliases: tuple[str, ...] = ("side",),
    default: str | None = None,
) -> None:
    side = _pop_string_alias(
        kw,
        where=where,
        names=(name, *aliases),
        allowed={"positive", "negative"},
    )
    if side is not None:
        existing_side = parameters.get(name)
        if existing_side is not None and str(existing_side) != side:
            raise MeshProgramError(
                f"{where}.{name}: side {side!r} conflicts with face side {existing_side!r}"
            )
        parameters[name] = side
    elif name not in parameters and default is not None:
        parameters[name] = default


def _pop_optional_seam_group_alias(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
) -> None:
    seam_group = _pop_string_alias(kw, where=where, names=("seam_group", "seam"))
    if seam_group is not None:
        parameters["seam_group"] = seam_group


def _pop_optional_polybevel_selector_parameter(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
) -> None:
    names = (
        "target_seam_groups",
        "seam_groups",
        "edge_classes",
        "target_edge_classes",
        "edge_class",
        "target_edge_class",
        "seam_group",
        "target_seam_group",
        "seam",
    )
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one bevel/chamfer selector may be supplied; got {present}"
        )
    if not present:
        return
    name = present[0]
    raw = kw.pop(name)
    values = raw if isinstance(raw, list) else [raw]
    if not values:
        raise MeshProgramError(f"{where}.{name}: selector list must be non-empty")
    target_names: list[str] = []
    for index, value in enumerate(values):
        text = _string(value, where=f"{where}.{name}[{index}]").strip()
        if not text:
            raise MeshProgramError(f"{where}.{name}[{index}]: selector must be non-empty")
        if text not in target_names:
            target_names.append(text)
    parameters["target_seam_groups"] = target_names
    if len(target_names) == 1:
        if name in {"edge_class", "target_edge_class"}:
            parameters["edge_class"] = target_names[0]
        if name in {"seam_group", "target_seam_group", "seam"}:
            parameters["seam_group"] = target_names[0]


def _pop_optional_polybevel_edge_pair_parameter(
    kw: dict[str, Any],
    parameters: dict[str, Any],
    *,
    where: str,
) -> None:
    names = ("edge_pairs", "edge_pair", "axis_pairs", "axis_pair", "axes")
    present = [name for name in names if name in kw]
    if len(present) > 1:
        raise MeshProgramError(
            f"{where}: only one bevel/chamfer edge-pair selector may be supplied; got {present}"
        )
    if not present:
        return
    name = present[0]
    raw = kw.pop(name)
    if isinstance(raw, list) and not raw:
        raise MeshProgramError(f"{where}.{name}: edge-pair selector list must be non-empty")
    parameters["edge_pairs"] = raw


def _apply_op_countersunk_hole(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "radius_cm": _pop_radius_or_diameter(
            kw,
            where=where,
            radius_names=("radius", "radius_cm", "hole_radius", "hole_radius_cm"),
            diameter_names=("diameter", "diameter_cm", "hole_diameter", "hole_diameter_cm"),
            required=True,
        ),
        "depth_cm": _pop_length_alias(kw, where=where, names=("depth", "depth_cm"), required=True),
    }
    _pop_optional_number_parameter(kw, parameters, where=where, target="normal_sign", names=("normal_sign",))
    _pop_face_axis_alias(kw, parameters, where=where)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="z")
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    style = _pop_string_alias(
        kw,
        where=where,
        names=("style",),
        allowed={"straight", "countersink", "counterbore"},
    )
    if style is not None:
        parameters["style"] = style
    for target, radius_names, diameter_names in (
        (
            "countersink_radius_cm",
            ("countersink_radius", "countersink_radius_cm", "sink_radius", "sink_radius_cm", "head_radius", "head_radius_cm"),
            ("countersink_diameter", "countersink_diameter_cm", "sink_diameter", "sink_diameter_cm", "head_diameter", "head_diameter_cm"),
        ),
        (
            "counterbore_radius_cm",
            ("counterbore_radius", "counterbore_radius_cm"),
            ("counterbore_diameter", "counterbore_diameter_cm"),
        ),
    ):
        _pop_optional_radius_or_diameter_parameter(
            kw,
            parameters,
            where=where,
            target=target,
            radius_names=radius_names,
            diameter_names=diameter_names,
        )
    for target, names in (
        ("countersink_depth_cm", ("countersink_depth", "countersink_depth_cm", "sink_depth", "sink_depth_cm", "head_depth", "head_depth_cm")),
        ("counterbore_depth_cm", ("counterbore_depth", "counterbore_depth_cm")),
        ("rim_bevel_cm", ("rim_bevel", "rim_bevel_cm")),
        ("seat_depth_cm", ("seat_depth", "seat_depth_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=target, names=names)
    _pop_optional_number_parameter(kw, parameters, where=where, target="rim_bevel_segments", names=("rim_bevel_segments",))
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_countersunk_hole(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.countersunk_hole",
        mesh_program_op_name="op_countersunk_hole",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_countersunk_hole_modifier",
        feature_primitive_count=1,
        component="countersunk_hole",
        region=f"{part}.countersunk_hole",
    )


def _apply_op_rounded_slot(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "length_cm": _pop_length_alias(kw, where=where, names=("length", "length_cm"), required=True),
        "width_cm": _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True),
        "depth_cm": _pop_length_alias(kw, where=where, names=("depth", "depth_cm"), required=True),
    }
    _pop_optional_number_parameter(kw, parameters, where=where, target="normal_sign", names=("normal_sign",))
    _pop_face_axis_alias(kw, parameters, where=where)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="z")
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    segments = _pop_int_alias(kw, where=where, names=("segments",))
    if segments is not None:
        parameters["segments"] = segments
    rotation = _pop_angle_alias(
        kw,
        where=where,
        names=("rotation_degrees", "rotate_degrees", "rotation_deg", "rotate_deg", "angle_degrees", "angle", "radians"),
    )
    if rotation is not None:
        parameters["rotation_degrees"] = rotation
    _pop_optional_length_parameter(kw, parameters, where=where, target="seat_depth_cm", names=("seat_depth", "seat_depth_cm"))
    _pop_optional_center_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_rounded_slot(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.rounded_slot",
        mesh_program_op_name="op_rounded_slot",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_rounded_slot_modifier",
        feature_primitive_count=1,
        component="rounded_slot",
        region=f"{part}.rounded_slot",
    )


def _apply_op_bevel(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "width_cm": _pop_length_alias(
            kw,
            where=where,
            names=("width", "width_cm", "bevel_width", "bevel_width_cm"),
            required=True,
        ),
        "segments": _pop_int_alias(kw, where=where, names=("segments",), default=2),
    }
    _pop_optional_polybevel_selector_parameter(kw, parameters, where=where)
    _pop_optional_polybevel_edge_pair_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_bevel(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.bevel",
        mesh_program_op_name="op_bevel",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_polybevel_modifier",
        feature_primitive_count=1,
        component="bevel",
        region=f"{part}.bevel",
    )


def _apply_op_chamfer(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "width_cm": _pop_length_alias(
            kw,
            where=where,
            names=("width", "width_cm", "chamfer_width", "chamfer_width_cm"),
            required=True,
        ),
        "segments": _pop_int_alias(
            kw,
            where=where,
            names=("segments", "chamfer_segments", "bevel_segments"),
            default=1,
        ),
    }
    _pop_optional_polybevel_selector_parameter(kw, parameters, where=where)
    _pop_optional_polybevel_edge_pair_parameter(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_chamfer(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.chamfer",
        mesh_program_op_name="op_chamfer",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_polybevel_modifier",
        feature_primitive_count=1,
        component="chamfer",
        region=f"{part}.chamfer",
    )


def _apply_sop_copy_to_points(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {
        "points": _pop_points_parameter(kw, bindings, where=where),
    }
    _pop_optional_axis_parameter(kw, parameters, where=where, name="source_axis", default=None)
    mode = _pop_string_alias(
        kw,
        where=where,
        names=("orientation_mode", "align_to"),
        allowed={"none", "axis", "curve_tangent", "path_tangent", "tangent"},
    )
    if mode is not None:
        parameters["orientation_mode"] = mode
    align_to_curve = _pop_bool_alias(kw, where=where, names=("align_to_curve",))
    if align_to_curve is not None:
        parameters["align_to_curve"] = align_to_curve
    _pop_instance_variation_parameters(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown sop_copy_to_points(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "sop.copy_to_points",
        mesh_program_op_name="sop_copy_to_points",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_copy_to_points_modifier",
        feature_primitive_count=max(1, len(parameters["points"])),
        component="copy_to_points",
        region=f"{part}.copy_to_points",
    )


def _apply_op_repeat(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "count": _pop_int_alias(kw, where=where, names=("count",), required=True),
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis"),
    }
    _pop_optional_length_parameter(kw, parameters, where=where, target="spacing_cm", names=("spacing", "spacing_cm"))
    _pop_optional_axis_parameter(kw, parameters, where=where, name="source_axis", default=None)
    _pop_instance_variation_parameters(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_repeat(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.repeat",
        mesh_program_op_name="op_repeat",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_repeat_modifier",
        feature_primitive_count=max(1, int(parameters["count"])),
        component="repeat",
        region=f"{part}.repeat",
    )


def _apply_op_mirror(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "axis": _axis_arg(kw.pop("axis", None), where=f"{where}.axis"),
    }
    _pop_optional_length_parameter(kw, parameters, where=where, target="origin_cm", names=("origin_cm", "plane_origin_cm"))
    origin = _pop_optional_center(kw, where=where)
    if origin is not None:
        parameters["origin"] = origin
    include_source = _pop_bool_alias(kw, where=where, names=("include_source",))
    if include_source is not None:
        parameters["include_source"] = include_source
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_mirror(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.mirror",
        mesh_program_op_name="op_mirror",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_mirror_modifier",
        feature_primitive_count=2 if bool(parameters.get("include_source")) else 1,
        component="mirror",
        region=f"{part}.mirror",
    )


def _apply_op_panel_frame(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    width = _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True)
    height = _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True)
    border_width = _pop_length_alias(
        kw,
        where=where,
        names=("border_width", "border_width_cm", "rail_width", "rail_width_cm"),
    )
    if border_width is None:
        border_width = max(min(width, height) * 0.08, 0.05)
    parameters = {
        "width_cm": width,
        "height_cm": height,
        "border_width_cm": border_width,
        "thickness_cm": _pop_length_alias(kw, where=where, names=("thickness", "thickness_cm"), required=True),
    }
    _pop_face_axis_alias(kw, parameters, where=where, axis_name="normal_axis")
    normal_axis = str(parameters.get("normal_axis") or "z")
    width_default, height_default = _tangent_axis_defaults(normal_axis)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="width_axis", default=width_default)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="height_axis", default=height_default)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="normal_axis", default="z")
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    _pop_common_attachment_parameters(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_panel_frame(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.panel_frame",
        mesh_program_op_name="op_panel_frame",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_panel_frame_modifier",
        feature_primitive_count=4,
        component="panel_frame",
        region=f"{part}.panel_frame",
    )


def _apply_op_corner_guard_set(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "size_cm": _pop_length_alias(kw, where=where, names=("size", "size_cm"), required=True),
    }
    _pop_optional_axes_parameter(kw, parameters, where=where)
    _pop_corner_signs_face_alias(kw, parameters, where=where)
    explicit_normal_axis, explicit_normal_axis_name = _pop_surface_normal_axis_alias(
        kw,
        where=where,
    )
    side = _pop_string_alias(
        kw,
        where=where,
        names=("side",),
        allowed={"positive", "negative"},
    )
    normal_sign_value = _pop_number_alias(kw, where=where, names=("normal_sign", "sign"))
    if explicit_normal_axis is not None or side is not None or normal_sign_value is not None:
        normal_axis = explicit_normal_axis or "z"
        if side is not None:
            side_sign = 1.0 if side == "positive" else -1.0
            if normal_sign_value is not None and _sign_from_optional_normal_sign(normal_sign_value) != side_sign:
                raise MeshProgramError(
                    f"{where}.normal_sign: sign {normal_sign_value!r} conflicts with side {side!r}"
                )
            normal_sign = side_sign
        else:
            normal_sign = _sign_from_optional_normal_sign(normal_sign_value)
            side = "positive" if normal_sign > 0.0 else "negative"
        existing_corner_signs = parameters.get("corner_signs")
        if existing_corner_signs is not None and not _corner_signs_match_surface(
            existing_corner_signs,
            axis=normal_axis,
            sign=normal_sign,
        ):
            raise MeshProgramError(
                f"{where}.{explicit_normal_axis_name or 'normal_axis'}: surface selector "
                "conflicts with face/corner_signs"
            )
        parameters["normal_axis"] = normal_axis
        parameters["side"] = side
        parameters["normal_sign"] = normal_sign
        parameters["corner_signs"] = _corner_signs_for_surface_axis(normal_axis, normal_sign)
    _pop_optional_length_parameter(kw, parameters, where=where, target="thickness_cm", names=("thickness", "thickness_cm"))
    _pop_optional_length_parameter(kw, parameters, where=where, target="rounding_cm", names=("rounding", "rounding_cm"))
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    _pop_common_attachment_parameters(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_corner_guard_set(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.corner_guard_set",
        mesh_program_op_name="op_corner_guard_set",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_corner_guard_set_modifier",
        feature_primitive_count=4,
        component="corner_guard_set",
        region=f"{part}.corner_guard_set",
    )


def _apply_op_mount_plate(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "width_cm": _pop_length_alias(kw, where=where, names=("width", "width_cm"), required=True),
        "height_cm": _pop_length_alias(kw, where=where, names=("height", "height_cm"), required=True),
    }
    _pop_optional_length_parameter(kw, parameters, where=where, target="thickness_cm", names=("thickness", "thickness_cm"))
    _pop_optional_number_parameter(kw, parameters, where=where, target="normal_sign", names=("normal_sign",))
    _pop_face_axis_alias(kw, parameters, where=where)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="z")
    _pop_optional_axis_parameter(kw, parameters, where=where, name="column_axis", default=None)
    _pop_optional_axis_parameter(kw, parameters, where=where, name="row_axis", default=None)
    rows = _pop_int_alias(kw, where=where, names=("rows", "hole_rows"))
    if rows is not None:
        parameters["hole_rows"] = rows
    columns = _pop_int_alias(kw, where=where, names=("cols", "columns", "hole_cols", "hole_columns"))
    if columns is not None:
        parameters["hole_columns"] = columns
    hole_count = _pop_int_alias(kw, where=where, names=("hole_count", "count"))
    if hole_count is not None:
        parameters["hole_count"] = hole_count
    _pop_optional_radius_or_diameter_parameter(
        kw,
        parameters,
        where=where,
        target="hole_radius_cm",
        radius_names=("hole_radius", "hole_radius_cm"),
        diameter_names=("hole_diameter", "hole_diameter_cm"),
    )
    _pop_optional_length_parameter(kw, parameters, where=where, target="hole_depth_cm", names=("hole_depth", "hole_depth_cm"))
    _pop_optional_length_parameter(kw, parameters, where=where, target="hole_edge_margin_cm", names=("hole_edge_margin", "hole_edge_margin_cm"))
    _pop_optional_length_parameter(kw, parameters, where=where, target="hole_row_span_cm", names=("hole_row_span", "hole_row_span_cm"))
    _pop_optional_length_parameter(kw, parameters, where=where, target="hole_column_span_cm", names=("hole_column_span", "hole_column_span_cm"))
    _pop_optional_length_parameter(kw, parameters, where=where, target="hole_rim_bevel_cm", names=("hole_rim_bevel", "hole_rim_bevel_cm"))
    _pop_optional_number_parameter(kw, parameters, where=where, target="hole_rim_bevel_segments", names=("hole_rim_bevel_segments",))
    _pop_optional_radius_or_diameter_parameter(
        kw,
        parameters,
        where=where,
        target="countersink_radius_cm",
        radius_names=("countersink_radius", "countersink_radius_cm", "sink_radius", "sink_radius_cm", "head_radius", "head_radius_cm"),
        diameter_names=("countersink_diameter", "countersink_diameter_cm", "sink_diameter", "sink_diameter_cm", "head_diameter", "head_diameter_cm"),
    )
    _pop_optional_length_parameter(kw, parameters, where=where, target="countersink_depth_cm", names=("countersink_depth", "countersink_depth_cm"))
    _pop_optional_radius_or_diameter_parameter(
        kw,
        parameters,
        where=where,
        target="counterbore_radius_cm",
        radius_names=("counterbore_radius", "counterbore_radius_cm"),
        diameter_names=("counterbore_diameter", "counterbore_diameter_cm"),
    )
    _pop_optional_length_parameter(kw, parameters, where=where, target="counterbore_depth_cm", names=("counterbore_depth", "counterbore_depth_cm"))
    style = _pop_string_alias(
        kw,
        where=where,
        names=("style",),
        allowed={"straight", "countersink", "counterbore"},
    )
    if style is not None:
        parameters["style"] = style
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    _pop_common_attachment_parameters(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_mount_plate(...) argument(s): {unknown}")
    has_holes = any(
        key in parameters
        for key in (
            "hole_radius_cm",
            "hole_rows",
            "hole_columns",
            "hole_count",
            "countersink_radius_cm",
            "counterbore_radius_cm",
        )
    )
    if has_holes:
        if "hole_count" in parameters and "hole_rows" not in parameters and "hole_columns" not in parameters:
            hole_count = int(parameters["hole_count"])
        else:
            hole_count = int(parameters.get("hole_rows", 2)) * int(parameters.get("hole_columns", 2))
    else:
        hole_count = 0
    return _lower_bound_v2_source_op(
        "op.mount_plate",
        mesh_program_op_name="op_mount_plate",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_mount_plate_modifier",
        feature_primitive_count=1 + max(0, hole_count),
        component="mount_plate",
        region=f"{part}.mount_plate",
    )


def _apply_op_socket(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {}
    clearance = _pop_length_alias(kw, where=where, names=("clearance", "clearance_cm"))
    for target, names in (
        ("width_cm", ("width", "width_cm")),
        ("height_cm", ("height", "height_cm")),
        ("depth_cm", ("depth", "depth_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=target, names=names)
    _pop_optional_radius_or_diameter_parameter(
        kw,
        parameters,
        where=where,
        target="radius_cm",
        radius_names=("radius", "radius_cm"),
        diameter_names=("diameter", "diameter_cm"),
    )
    if clearance is None:
        tangent_dims = [
            float(parameters[name])
            for name in ("width_cm", "height_cm")
            if name in parameters
        ]
        if tangent_dims:
            clearance = min(tangent_dims) * 0.5
        elif "depth_cm" in parameters:
            clearance = float(parameters["depth_cm"])
        else:
            raise MeshProgramError(
                f"{where}: requires clearance/clearance_cm or socket width/height/depth"
            )
    parameters["clearance_cm"] = clearance
    shape = _pop_string_alias(
        kw,
        where=where,
        names=("shape", "socket_shape"),
        allowed={"box", "rect", "rectangular", "cylinder", "round", "circular", "rounded_slot", "capsule"},
    )
    if shape is not None:
        parameters["shape"] = shape
    _pop_optional_length_parameter(kw, parameters, where=where, target="rim_bevel_cm", names=("rim_bevel", "rim_bevel_cm"))
    _pop_optional_number_parameter(kw, parameters, where=where, target="rim_bevel_segments", names=("rim_bevel_segments",))
    segments = _pop_int_alias(kw, where=where, names=("segments",))
    if segments is not None:
        parameters["segments"] = segments
    rotation = _pop_angle_alias(
        kw,
        where=where,
        names=("rotation_degrees", "rotate_degrees", "rotation_deg", "rotate_deg", "angle_degrees", "angle", "radians"),
    )
    if rotation is not None:
        parameters["rotation_degrees"] = rotation
    _pop_optional_number_parameter(kw, parameters, where=where, target="normal_sign", names=("normal_sign",))
    _pop_face_axis_alias(kw, parameters, where=where)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="axis", default="z")
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    _pop_common_attachment_parameters(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_socket(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.socket",
        mesh_program_op_name="op_socket",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_socket_modifier",
        feature_primitive_count=1,
        component="socket",
        region=f"{part}.socket",
    )


def _apply_op_bracket(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "clearance_cm": _pop_length_alias(kw, where=where, names=("clearance", "clearance_cm"), required=True),
        "mount_type": _string(kw.pop("mount_type", None), where=f"{where}.mount_type"),
    }
    for target, names in (
        ("width_cm", ("width", "width_cm")),
        ("height_cm", ("height", "height_cm")),
        ("depth_cm", ("depth", "depth_cm")),
        ("thickness_cm", ("thickness", "thickness_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=target, names=names)
    include_gussets = _pop_bool_alias(
        kw,
        where=where,
        names=("include_gussets", "include_gusset", "gussets"),
    )
    if include_gussets is not None:
        parameters["include_gussets"] = include_gussets
    gusset_count = _pop_int_alias(kw, where=where, names=("gusset_count", "gussets_count"))
    if gusset_count is not None:
        parameters["gusset_count"] = gusset_count
    for target, names in (
        ("gusset_thickness_cm", ("gusset_thickness", "gusset_thickness_cm")),
        ("gusset_height_cm", ("gusset_height", "gusset_height_cm")),
        ("gusset_depth_cm", ("gusset_depth", "gusset_depth_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=target, names=names)
    _pop_optional_number_parameter(kw, parameters, where=where, target="normal_sign", names=("normal_sign",))
    _pop_face_axis_alias(kw, parameters, where=where, axis_name="normal_axis")
    explicit_normal_axis, explicit_normal_axis_name = _pop_surface_normal_axis_alias(
        kw,
        where=where,
        names=("normal_axis", "surface_axis", "face_axis", "axis"),
    )
    if explicit_normal_axis is not None:
        existing_axis = parameters.get("normal_axis")
        if existing_axis is not None and str(existing_axis) != explicit_normal_axis:
            raise MeshProgramError(
                f"{where}.{explicit_normal_axis_name}: axis {explicit_normal_axis!r} "
                f"conflicts with face axis {existing_axis!r}"
            )
        parameters["normal_axis"] = explicit_normal_axis
    elif "normal_axis" not in parameters:
        parameters["normal_axis"] = "z"
    bracket_normal_axis = str(parameters["normal_axis"])
    width_axis_default, height_axis_default = _tangent_axis_defaults(bracket_normal_axis)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="width_axis", default=width_axis_default)
    _pop_axis_parameter_with_default(kw, parameters, where=where, name="height_axis", default=height_axis_default)
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    _pop_common_attachment_parameters(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_bracket(...) argument(s): {unknown}")
    bracket_feature_count = 2
    if bool(parameters.get("include_gussets", False)):
        bracket_feature_count += max(1, int(parameters.get("gusset_count", 2)))
    return _lower_bound_v2_source_op(
        "op.bracket",
        mesh_program_op_name="op_bracket",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_bracket_modifier",
        feature_primitive_count=bracket_feature_count,
        component="bracket",
        region=f"{part}.bracket",
    )


def _apply_op_weld_seam(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {}
    width = _pop_length_alias(
        kw,
        where=where,
        names=("width", "width_cm", "diameter", "diameter_cm", "bead_width", "bead_width_cm"),
    )
    radius = _pop_length_alias(
        kw,
        where=where,
        names=("radius", "radius_cm", "bead_radius", "bead_radius_cm"),
    )
    if width is None:
        if radius is None:
            raise MeshProgramError(
                f"{where}: op_weld_seam(...) requires width/diameter or radius"
            )
        width = radius * 2.0
    parameters["width_cm"] = width
    if radius is not None:
        parameters["radius_cm"] = radius
    if "path" in kw:
        parameters["path"] = _vec3_length_points(kw.pop("path"), where=f"{where}.path", min_points=2)
    else:
        _pop_optional_length_parameter(kw, parameters, where=where, target="length_cm", names=("length", "length_cm"))
        _pop_face_axis_alias(kw, parameters, where=where, axis_name="normal_axis")
        normal_axis = str(parameters.get("normal_axis") or "z")
        explicit_normal_axis, explicit_normal_axis_name = _pop_surface_normal_axis_alias(
            kw,
            where=where,
        )
        if explicit_normal_axis is not None:
            if normal_axis not in ("z", explicit_normal_axis):
                raise MeshProgramError(
                    f"{where}.{explicit_normal_axis_name}: axis {explicit_normal_axis!r} "
                    f"conflicts with face axis {normal_axis!r}"
                )
            normal_axis = explicit_normal_axis
            parameters["normal_axis"] = normal_axis
        else:
            parameters["normal_axis"] = normal_axis
        axis_default, _ = _tangent_axis_defaults(normal_axis)
        line_axis = _pop_string_alias(
            kw,
            where=where,
            names=("axis", "line_axis", "seam_axis", "length_axis"),
            allowed=_AXIS_VALUES,
        )
        parameters["axis"] = _axis_arg(line_axis, where=f"{where}.axis", default=axis_default)
    segments = _pop_int_alias(kw, where=where, names=("segments",))
    if segments is not None:
        parameters["segments"] = segments
    _pop_optional_seam_group_alias(kw, parameters, where=where)
    _pop_common_attachment_parameters(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_weld_seam(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.weld_seam",
        mesh_program_op_name="op_weld_seam",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_weld_seam_modifier",
        feature_primitive_count=1,
        component="weld_seam",
        region=f"{part}.weld_seam",
    )


def _apply_op_hull(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    source_names, source_primitives = _pop_source_primitives_parameter(
        kw,
        bindings,
        where=where,
    )
    parameters: dict[str, Any] = {
        "sources": [
            _source_record_for_primitive(primitive)
            for primitive in source_primitives
        ],
    }
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_hull(...) argument(s): {unknown}")
    from ..geometry.kernel import resolve_geometry_kernel

    source_history = _mesh_program_operation_history_from_primitives(source_primitives)
    lowered = _v2_primitives_from_op(
        "op.hull",
        target=part,
        parameters=parameters,
        where=where,
        geometry_kernel=resolve_geometry_kernel(),
    )
    for primitive in lowered:
        _attach_mesh_program_operation_history(
            primitive,
            source=source_primitives[0],
            op_name="op_hull",
            modifier_name="v2_hull_modifier",
            modifier_payload=parameters,
            feature_primitive_count=len(source_primitives),
            component="hull",
            region=f"{part}.hull",
            source_history=source_history,
        )
    _replace_primitives_in_program(primitives, source_primitives, tuple(lowered))
    if source_names and source_names[0] in bindings:
        _replace_value_primitives(bindings[source_names[0]], lowered)
    return _primitive_value(lowered)


def _apply_op_minkowski(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    source_names, source_primitives = _pop_source_primitives_parameter(
        kw,
        bindings,
        where=where,
    )
    if len(source_primitives) not in {1, 2}:
        raise MeshProgramError(f"{where}: op_minkowski(...) requires one source plus optional structuring source")
    parameters: dict[str, Any] = {
        "source": _source_record_for_primitive(source_primitives[0]),
    }
    structuring_primitives: tuple[ShapePrimitive, ...] = ()
    for key in ("kernel", "structuring", "structuring_source"):
        if key not in kw:
            continue
        _structuring_name, structuring_primitives = _named_primitives_from_binding_value(
            kw.pop(key),
            bindings,
            where=f"{where}.{key}",
            part=part,
        )
        if len(structuring_primitives) != 1:
            raise MeshProgramError(f"{where}.{key}: must reference exactly one primitive")
        parameters[key] = _source_record_for_primitive(structuring_primitives[0])
        break
    if not structuring_primitives and len(source_primitives) == 2:
        structuring_primitives = (source_primitives[1],)
        parameters["structuring"] = _source_record_for_primitive(structuring_primitives[0])
    _pop_optional_length_parameter(kw, parameters, where=where, target="radius_cm", names=("radius", "radius_cm"))
    sample_limit = _pop_int_alias(kw, where=where, names=("sample_limit",))
    if sample_limit is not None:
        parameters["sample_limit"] = sample_limit
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_minkowski(...) argument(s): {unknown}")
    from ..geometry.kernel import resolve_geometry_kernel

    source_history = _mesh_program_operation_history_from_primitives(
        (*source_primitives, *structuring_primitives)
    )
    lowered = _v2_primitives_from_op(
        "op.minkowski",
        target=part,
        parameters=parameters,
        where=where,
        geometry_kernel=resolve_geometry_kernel(),
    )
    for primitive in lowered:
        _attach_mesh_program_operation_history(
            primitive,
            source=source_primitives[0],
            op_name="op_minkowski",
            modifier_name="v2_minkowski_modifier",
            modifier_payload=parameters,
            feature_primitive_count=len(source_primitives) + len(structuring_primitives),
            component="minkowski",
            region=f"{part}.minkowski",
            source_history=source_history,
        )
    _replace_primitives_in_program(
        primitives,
        (*source_primitives, *structuring_primitives),
        tuple(lowered),
    )
    if source_names and source_names[0] in bindings:
        _replace_value_primitives(bindings[source_names[0]], lowered)
    return _primitive_value(lowered)


def _apply_v2_boolean_op(
    op_name: str,
    operation: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_primitives: tuple[ShapePrimitive, ...] = ()
    target_name: str | None = None
    for key in ("target", "a"):
        if key not in kw:
            continue
        target_name, target_value = _pop_value_parameter(
            kw,
            bindings,
            name=key,
            allowed_kinds=("primitive",),
            part=part,
            where=where,
        )
        target_primitives = _value_primitives(target_value)
        if not target_primitives:
            raise MeshProgramError(
                f"{where}.{key}: binding {target_name!r} has no primitives"
            )
        break
    _source_names, source_primitives = _pop_source_primitives_parameter(
        kw,
        bindings,
        where=where,
        part=part,
    )
    source_records = [
        _source_record_for_primitive(primitive) for primitive in source_primitives
    ]
    parameters: dict[str, Any] = {"operation": operation}
    seam_group = _pop_string_alias(kw, where=where, names=("seam_group", "seam"))
    if seam_group is not None:
        parameters["seam_group"] = seam_group
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown {op_name.replace('.', '_')}(...) argument(s): {unknown}")

    from ..geometry.kernel import resolve_geometry_kernel

    geometry_kernel = resolve_geometry_kernel()
    lowered: list[ShapePrimitive] = []
    if target_primitives:
        for target_index, target_primitive in enumerate(target_primitives):
            source_history = _mesh_program_operation_history_from_primitive(target_primitive)
            current_record = _source_record_for_primitive(target_primitive)
            current_lowered: list[ShapePrimitive] = []
            for source_index, source_record in enumerate(source_records):
                op_parameters = {
                    **parameters,
                    "target": current_record,
                    "source": source_record,
                }
                current_lowered = _v2_primitives_from_op(
                    op_name,
                    target=part,
                    parameters=op_parameters,
                    where=f"{where}[{target_index}:{source_index}]",
                    geometry_kernel=geometry_kernel,
                )
                primary = _primary_primitive(tuple(current_lowered))
                if primary is None:
                    raise MeshProgramError(
                        f"{where}: {op_name} produced no fused target geometry"
                    )
                current_record = _source_record_for_primitive(primary)
            modifier_name = "v2_sop_boolean_modifier" if op_name == "sop.boolean" else "v2_boolean_modifier"
            for primitive in current_lowered:
                _attach_mesh_program_operation_history(
                    primitive,
                    source=target_primitive,
                    op_name=op_name.replace(".", "_"),
                    modifier_name=modifier_name,
                    modifier_payload=parameters,
                    feature_primitive_count=len(source_records),
                    component="boolean",
                    region=f"{part}.{operation}",
                    source_history=source_history,
                )
            lowered.extend(current_lowered)
        _replace_primitives_in_program(
            primitives,
            (*target_primitives, *source_primitives),
            tuple(lowered),
        )
        if target_name is not None and target_name in bindings:
            _replace_value_primitives(bindings[target_name], lowered)
    else:
        modifier_name = "v2_sop_boolean_modifier" if op_name == "sop.boolean" else "v2_boolean_modifier"
        for index, source_record in enumerate(source_records):
            op_parameters = dict(parameters)
            op_parameters["source"] = source_record
            current_lowered = _v2_primitives_from_op(
                op_name,
                target=part,
                parameters=op_parameters,
                where=f"{where}[{index}]",
                geometry_kernel=geometry_kernel,
            )
            source_primitive = source_primitives[index]
            for primitive in current_lowered:
                _attach_mesh_program_operation_history(
                    primitive,
                    source=source_primitive,
                    op_name=op_name.replace(".", "_"),
                    modifier_name=modifier_name,
                    modifier_payload=parameters,
                    feature_primitive_count=1,
                    component="boolean",
                    region=f"{part}.{operation}",
                )
            lowered.extend(current_lowered)
        for primitive in lowered:
            if primitive not in primitives:
                primitives.append(primitive)
    return _primitive_value(lowered)


def _apply_sop_boolean(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    operation = _pop_string_alias(
        kw,
        where=where,
        names=("operation", "op"),
        default="union",
        allowed={"union", "subtract", "intersect"},
    ) or "union"
    rebuilt_args = [{"name": key, "value": value} for key, value in kw.items()]
    return _apply_v2_boolean_op(
        "sop.boolean",
        operation,
        rebuilt_args,
        bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_op_union(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    return _apply_v2_boolean_op(
        "op.union",
        "union",
        args,
        bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_op_subtract(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    return _apply_v2_boolean_op(
        "op.subtract",
        "subtract",
        args,
        bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_op_intersect(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    return _apply_v2_boolean_op(
        "op.intersect",
        "intersect",
        args,
        bindings,
        primitives=primitives,
        part=part,
        where=where,
    )


def _apply_op_weighted_normals(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {}
    mode = _pop_string_alias(
        kw,
        where=where,
        names=("mode",),
        default="area_angle",
        allowed={"area", "angle", "area_angle"},
    )
    if mode is not None:
        parameters["mode"] = mode
    strength = _pop_number_alias(kw, where=where, names=("strength",))
    if strength is not None:
        parameters["strength"] = strength
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_weighted_normals(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.weighted_normals",
        mesh_program_op_name="op_weighted_normals",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_weighted_normals_modifier",
        feature_primitive_count=1,
        component="weighted_normals",
        region=f"{part}.weighted_normals",
    )


def _apply_op_mark_hard_edge(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters: dict[str, Any] = {}
    for key in ("edge_class", "seam_group"):
        value = _pop_string_alias(kw, where=where, names=(key,))
        if value is not None:
            parameters[key] = value
    threshold = _pop_angle_alias(
        kw,
        where=where,
        names=("angle_threshold", "angle_threshold_deg", "angle_threshold_degrees", "angle_threshold_radians"),
    )
    if threshold is not None:
        parameters["angle_threshold_deg"] = threshold
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_mark_hard_edge(...) argument(s): {unknown}")
    return _lower_bound_v2_source_op(
        "op.mark_hard_edge",
        mesh_program_op_name="op_mark_hard_edge",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_mark_hard_edge_modifier",
        feature_primitive_count=1,
        component="hard_edge",
        region=f"{part}.hard_edge",
    )


def _apply_op_distribute(
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    pattern = _pop_string_alias(
        kw,
        where=where,
        names=("pattern",),
        allowed={"linear", "grid", "radial", "arc", "along_path", "points"},
    )
    if pattern is None:
        raise MeshProgramError(f"{where}: op_distribute(...) requires 'pattern'")
    parameters: dict[str, Any] = {"pattern": pattern}
    _pop_optional_center_parameter(kw, parameters, where=where)
    for name in ("axis", "row_axis", "column_axis", "normal_axis", "source_axis", "orientation_axis", "mirror_axis"):
        _pop_optional_axis_parameter(kw, parameters, where=where, name=name, default=None)
    for target, names in (
        ("spacing_cm", ("spacing", "spacing_cm")),
        ("row_spacing_cm", ("row_spacing", "row_spacing_cm")),
        ("column_spacing_cm", ("column_spacing", "column_spacing_cm")),
        ("length_cm", ("length", "length_cm")),
        ("row_span_cm", ("row_span", "row_span_cm")),
        ("column_span_cm", ("column_span", "column_span_cm")),
        ("radius_cm", ("radius", "radius_cm")),
        ("snap_cm", ("snap", "snap_cm", "snap_to_grid", "snap_to_grid_cm")),
        ("jitter_cm", ("jitter", "jitter_cm")),
        ("mirror_origin_cm", ("mirror_origin", "mirror_origin_cm")),
        ("mirror_dedupe_epsilon_cm", ("mirror_dedupe_epsilon", "mirror_dedupe_epsilon_cm")),
    ):
        _pop_optional_length_parameter(kw, parameters, where=where, target=target, names=names)
    for target, names in (
        ("count", ("count",)),
        ("rows", ("rows",)),
        ("columns", ("columns", "cols")),
    ):
        value = _pop_int_alias(kw, where=where, names=names)
        if value is not None:
            parameters[target] = value
    for target, names in (
        ("density", ("density",)),
        ("density_per_cm", ("density_per_cm",)),
    ):
        _pop_optional_number_parameter(kw, parameters, where=where, target=target, names=names)
    for target, names in (
        ("start_angle_deg", ("start_angle", "start_angle_deg", "start_angle_degrees", "start_angle_radians")),
        ("end_angle_deg", ("end_angle", "end_angle_deg", "end_angle_degrees", "end_angle_radians")),
    ):
        angle = _pop_angle_alias(kw, where=where, names=names)
        if angle is not None:
            parameters[target] = angle
    if "path" in kw:
        parameters["path"] = _vec3_length_points(kw.pop("path"), where=f"{where}.path", min_points=2)
    if "points" in kw:
        parameters["points"] = _pop_points_parameter(kw, bindings, where=where)
    mode = _pop_string_alias(
        kw,
        where=where,
        names=("orientation_mode", "align_to"),
        allowed={"none", "axis", "curve_tangent", "path_tangent", "tangent"},
    )
    if mode is not None:
        parameters["orientation_mode"] = mode
    mirror = _pop_bool_alias(kw, where=where, names=("mirror",))
    if mirror is not None:
        parameters["mirror"] = mirror
    _pop_instance_variation_parameters(kw, parameters, where=where)
    _pop_optional_blend_parameter(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown op_distribute(...) argument(s): {unknown}")
    estimated_count = int(parameters.get("count") or 1)
    if pattern == "grid":
        estimated_count = int(parameters.get("rows") or 1) * int(parameters.get("columns") or 1)
    elif "points" in parameters:
        estimated_count = len(parameters["points"])
    return _lower_bound_v2_source_op(
        "op.distribute",
        mesh_program_op_name="op_distribute",
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name="v2_distribution_modifier",
        feature_primitive_count=max(1, estimated_count),
        component="distribute",
        region=f"{part}.distribute",
    )


def _apply_detail_mask_op(
    op_name: str,
    args: list[dict[str, Any]],
    bindings: dict[str, _Value],
    *,
    primitives: list[ShapePrimitive],
    part: str,
    where: str,
) -> _Value:
    kw = _kwargs(args, where=where)
    target_name, source_primitives = _pop_target_primitives(kw, bindings, where=where)
    parameters = {
        "amount": _pop_number_alias(kw, where=where, names=("amount",), required=True),
    }
    _pop_detail_mask_parameters(kw, parameters, where=where)
    if kw:
        unknown = sorted(kw.keys())
        raise MeshProgramError(f"{where}: unknown {op_name.replace('.', '_')}(...) argument(s): {unknown}")
    modifier_name = {
        "op.chip_edges": "v2_chip_edges_modifier",
        "op.scratch_mask": "v2_scratch_mask_modifier",
        "op.dent_mask": "v2_dent_mask_modifier",
        "op.grime_mask": "v2_grime_mask_modifier",
    }[op_name]
    component = op_name.rsplit(".", 1)[-1]
    return _lower_bound_v2_source_op(
        op_name,
        mesh_program_op_name=op_name.replace(".", "_"),
        target_name=target_name,
        bindings=bindings,
        source_primitives=source_primitives,
        parameters=parameters,
        primitives=primitives,
        part=part,
        where=where,
        modifier_name=modifier_name,
        feature_primitive_count=max(1, int(parameters.get("count") or 1)),
        component=component,
        region=f"{part}.{component}",
    )


def _apply_op_chip_edges(args, bindings, *, primitives, part, where):
    return _apply_detail_mask_op("op.chip_edges", args, bindings, primitives=primitives, part=part, where=where)


def _apply_op_scratch_mask(args, bindings, *, primitives, part, where):
    return _apply_detail_mask_op("op.scratch_mask", args, bindings, primitives=primitives, part=part, where=where)


def _apply_op_dent_mask(args, bindings, *, primitives, part, where):
    return _apply_detail_mask_op("op.dent_mask", args, bindings, primitives=primitives, part=part, where=where)


def _apply_op_grime_mask(args, bindings, *, primitives, part, where):
    return _apply_detail_mask_op("op.grime_mask", args, bindings, primitives=primitives, part=part, where=where)


_POINT_GENERATORS: dict[str, Any] = {
    "points_grid": _eval_points_grid_call,
    "points_random": _eval_points_random_call,
    "points_circle": _eval_points_circle_call,
}

# Point-cloud combiners that need the binding table to resolve identifier
# references (e.g. ``points_combine([a, b, c])``). They return a fully
# constructed ``_Value`` so the dispatcher does not have to wrap.
_POINT_BINDING_CONSTRUCTORS: dict[str, Any] = {
    "points_combine": _eval_points_combine_call,
}


_COMPOUND_OPS: dict[str, Any] = {
    "fastener_grid": _apply_fastener_grid,
    "op_fastener_grid": _apply_fastener_grid,
    "vent_slats": _apply_vent_slats,
    "op_vent_slats": _apply_vent_slats,
    "trim_band": _apply_trim_band,
    "op_trim_band": _apply_trim_band,
    "vegetation_canopy": _apply_vegetation_canopy,
    "terrain_biome": _apply_terrain_biome,
    "sdf_union": _apply_sdf_union,
    "sdf_intersect": _apply_sdf_intersect,
    "sdf_subtract": _apply_sdf_subtract,
    "sdf_smooth_union": _apply_sdf_smooth_union,
    "sdf_smooth_intersect": _apply_sdf_smooth_intersect,
    "sdf_smooth_subtract": _apply_sdf_smooth_subtract,
    "sdf_chamfer_union": _apply_sdf_chamfer_union,
    "sdf_chamfer_intersect": _apply_sdf_chamfer_intersect,
    "sdf_chamfer_subtract": _apply_sdf_chamfer_subtract,
    "sdf_chamfer_difference": _apply_sdf_chamfer_subtract,
    "sdf_repeat": _apply_sdf_repeat,
    "sdf_repeat_grid": _apply_sdf_repeat_grid,
    "sdf_radial_array": _apply_sdf_radial_array,
    "sdf_polar_array": _apply_sdf_radial_array,
    "sdf_radial_repeat": _apply_sdf_radial_array,
    "sdf_scale3": _apply_sdf_scale3,
    "sdf_scale_xyz": _apply_sdf_scale3,
    "sdf_twist": _apply_sdf_twist,
    "sdf_bend": _apply_sdf_bend,
    "sdf_taper": _apply_sdf_taper,
    "sdf_offset": _apply_sdf_offset,
    "sdf_shell": _apply_sdf_shell,
    "sdf_displace": _apply_sdf_displace,
    "sdf_warp": _apply_sdf_warp,
    "sdf_extract": _apply_sdf_extract,
    "wfc_modular": _apply_wfc_modular,
    "boolean": _apply_boolean,
    "scatter": _apply_scatter,
    "scatter_on_surface": _apply_scatter_on_surface,
    "polybevel": _apply_sop_polybevel,
    "sop_polybevel": _apply_sop_polybevel,
    "subdivide": _apply_sop_subdivide,
    "sop_subdivide": _apply_sop_subdivide,
    "remesh": _apply_sop_remesh,
    "sop_remesh": _apply_sop_remesh,
    "twist": _apply_sop_twist,
    "sop_twist": _apply_sop_twist,
    "taper": _apply_sop_taper,
    "sop_taper": _apply_sop_taper,
    "bend": _apply_sop_bend,
    "sop_bend": _apply_sop_bend,
    "polyextrude": _apply_sop_polyextrude,
    "sop_polyextrude": _apply_sop_polyextrude,
    "transform": _apply_sop_transform,
    "sop_transform": _apply_sop_transform,
    "carve": _apply_sop_carve,
    "sop_carve": _apply_sop_carve,
    "extrude": _apply_op_extrude,
    "op_extrude": _apply_op_extrude,
    "shell": _apply_op_shell,
    "op_shell": _apply_op_shell,
    "inset": _apply_op_inset,
    "op_inset": _apply_op_inset,
    "cut_panel_line": _apply_op_cut_panel_line,
    "op_cut_panel_line": _apply_op_cut_panel_line,
    "countersunk_hole": _apply_op_countersunk_hole,
    "op_countersunk_hole": _apply_op_countersunk_hole,
    "rounded_slot": _apply_op_rounded_slot,
    "op_rounded_slot": _apply_op_rounded_slot,
    "bevel": _apply_op_bevel,
    "op_bevel": _apply_op_bevel,
    "chamfer": _apply_op_chamfer,
    "op_chamfer": _apply_op_chamfer,
    "copy_to_points": _apply_sop_copy_to_points,
    "sop_copy_to_points": _apply_sop_copy_to_points,
    "repeat": _apply_op_repeat,
    "op_repeat": _apply_op_repeat,
    "mirror": _apply_op_mirror,
    "op_mirror": _apply_op_mirror,
    "panel_frame": _apply_op_panel_frame,
    "op_panel_frame": _apply_op_panel_frame,
    "corner_guard_set": _apply_op_corner_guard_set,
    "op_corner_guard_set": _apply_op_corner_guard_set,
    "mount_plate": _apply_op_mount_plate,
    "op_mount_plate": _apply_op_mount_plate,
    "socket": _apply_op_socket,
    "op_socket": _apply_op_socket,
    "bracket": _apply_op_bracket,
    "op_bracket": _apply_op_bracket,
    "weld_seam": _apply_op_weld_seam,
    "op_weld_seam": _apply_op_weld_seam,
    "hull": _apply_op_hull,
    "op_hull": _apply_op_hull,
    "minkowski": _apply_op_minkowski,
    "op_minkowski": _apply_op_minkowski,
    "sop_boolean": _apply_sop_boolean,
    "union": _apply_op_union,
    "op_union": _apply_op_union,
    "subtract": _apply_op_subtract,
    "op_subtract": _apply_op_subtract,
    "intersect": _apply_op_intersect,
    "op_intersect": _apply_op_intersect,
    "weighted_normals": _apply_op_weighted_normals,
    "op_weighted_normals": _apply_op_weighted_normals,
    "mark_hard_edge": _apply_op_mark_hard_edge,
    "op_mark_hard_edge": _apply_op_mark_hard_edge,
    "distribute": _apply_op_distribute,
    "op_distribute": _apply_op_distribute,
    "chip_edges": _apply_op_chip_edges,
    "op_chip_edges": _apply_op_chip_edges,
    "scratch_mask": _apply_op_scratch_mask,
    "op_scratch_mask": _apply_op_scratch_mask,
    "dent_mask": _apply_op_dent_mask,
    "op_dent_mask": _apply_op_dent_mask,
    "grime_mask": _apply_op_grime_mask,
    "op_grime_mask": _apply_op_grime_mask,
}


def lower_mesh_program(
    program: dict[str, Any],
    *,
    part: str = "body",
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> list[ShapePrimitive]:
    """Lower a parsed ``mesh_program{}`` AST to ``ShapePrimitive`` records.

    Args:
        program: the AST node emitted by the parser
            (``{"node_type": "mesh_program", "statements": [...]}``).
        part: target ``ShapePrimitive.part`` for every primitive
            produced by the program. Defaults to ``"body"`` so the
            simple single-part demo flows; multi-part lowerings can
            override per-program.

    Returns:
        Ordered list of ``ShapePrimitive`` records, ready for
        :func:`lathe.exact_solids.compile_explicit_surface_mesh`.
    """
    if not isinstance(program, dict) or program.get("node_type") != "mesh_program":
        raise MeshProgramError(
            "lower_mesh_program: expected a parsed mesh_program AST node"
        )
    statements = program.get("statements") or []
    def _statement_summary(index: int, stmt: dict[str, Any]) -> dict[str, Any]:
        expr = stmt.get("expr")
        summary: dict[str, Any] = {
            "index": index,
            "node_type": stmt.get("node_type"),
        }
        if stmt.get("node_type") == "mesh_let":
            summary["target"] = stmt.get("target")
        if isinstance(expr, dict):
            expr_type = expr.get("type")
            summary["expr_type"] = expr_type
            if expr_type == "call":
                summary["callee"] = expr.get("name")
            elif expr_type == "method_call":
                summary["method"] = expr.get("method")
                receiver = expr.get("receiver")
                if isinstance(receiver, dict):
                    summary["receiver_type"] = receiver.get("type")
                    if receiver.get("type") == "call":
                        summary["receiver_callee"] = receiver.get("name")
        return summary

    def _emit_progress(event: str, **payload: Any) -> None:
        if progress is None:
            return
        progress({"event": event, **payload})

    bindings: dict[str, _Value] = {}
    primitives: list[ShapePrimitive] = []
    _emit_progress("lower_start", statement_count=len(statements), part=part)
    for index, stmt in enumerate(statements):
        where = f"mesh_program statement #{index}"
        node_type = stmt.get("node_type")
        expr = stmt.get("expr")
        statement_payload = _statement_summary(index, stmt)
        _emit_progress(
            "statement_start",
            **statement_payload,
            primitive_count=len(primitives),
            binding_count=len(bindings),
        )
        result_kind = ""
        result_primitive_count = 0
        if node_type == "mesh_let":
            target = _ident(stmt.get("target"), where=f"{where}.target")
            if target in bindings:
                raise MeshProgramError(
                    f"{where}: identifier {target!r} is already bound"
                )
            if (
                isinstance(expr, dict)
                and expr.get("type") == "call"
                and expr.get("name") == "boolean"
            ):
                value = _apply_boolean(
                    list(expr.get("args") or []),
                    bindings,
                    primitives=primitives,
                    part=part,
                    where=where,
                )
            elif (
                isinstance(expr, dict)
                and expr.get("type") == "call"
                and expr.get("name") in _COMPOUND_OPS
            ):
                value = _COMPOUND_OPS[expr["name"]](
                    list(expr.get("args") or []),
                    bindings,
                    primitives=primitives,
                    part=part,
                    where=f"{where}.{expr['name']}",
                )
            else:
                value = _eval_expr(
                    expr,
                    bindings,
                    part=part,
                    where=where,
                    primitives=primitives,
                )
            _annotate_mesh_let_binding(value, target)
            bindings[target] = value
            result_kind = value.kind
            result_primitive_count = len(_value_primitives(value))
        elif node_type == "mesh_call":
            if (
                not isinstance(expr, dict)
                or expr.get("type") not in {"call", "method_call"}
            ):
                raise MeshProgramError(
                    f"{where}: bare statements must be calls, got {expr!r}"
                )
            if expr.get("type") == "method_call":
                value = _eval_expr(
                    expr,
                    bindings,
                    part=part,
                    where=where,
                    primitives=primitives,
                )
                root_ident = _method_chain_root_ident(expr)
                if root_ident is not None and root_ident in bindings:
                    bindings[root_ident] = value
                for primitive in _value_primitives(value):
                    primitive.part = part
                    if primitive not in primitives:
                        primitives.append(primitive)
                result_kind = value.kind
                result_primitive_count = len(_value_primitives(value))
                _emit_progress(
                    "statement_end",
                    **statement_payload,
                    primitive_count=len(primitives),
                    binding_count=len(bindings),
                    result_kind=result_kind,
                    result_primitive_count=result_primitive_count,
                )
                continue
            callee = expr.get("name")
            if callee == "emit":
                _apply_emit(
                    list(expr.get("args") or []),
                    bindings,
                    primitives=primitives,
                    part=part,
                    where=where,
                )
            elif callee == "fillet_edge":
                _apply_fillet_edge(
                    list(expr.get("args") or []), bindings, where=where
                )
            elif callee in _COMPOUND_OPS:
                _COMPOUND_OPS[callee](
                    list(expr.get("args") or []),
                    bindings,
                    primitives=primitives,
                    part=part,
                    where=f"{where}.{callee}",
                )
            else:
                raise MeshProgramError(
                    f"{where}: unsupported bare call {callee!r} "
                    f"(supported: emit, fillet_edge, {sorted(_COMPOUND_OPS)})"
                )
            result_kind = "call"
        else:
            raise MeshProgramError(f"{where}: unsupported statement {node_type!r}")
        _emit_progress(
            "statement_end",
            **statement_payload,
            primitive_count=len(primitives),
            binding_count=len(bindings),
            result_kind=result_kind,
            result_primitive_count=result_primitive_count,
        )
    if not primitives and bindings and all(value.kind == "primitive" for value in bindings.values()):
        seen: set[int] = set()
        for value in bindings.values():
            for primitive in _value_primitives(value):
                identity = id(primitive)
                if identity in seen:
                    continue
                primitives.append(primitive)
                seen.add(identity)
    _emit_progress("materialize_start", primitive_count=len(primitives))
    result = _materialize_mesh_program_output_primitives(
        primitives,
        part=part,
        where="lower_mesh_program.output",
    )
    _emit_progress("materialize_end", primitive_count=len(result))
    return result
