"""Compile a parsed ``f_rep_program`` block into an :class:`SDFExpr`.

The Lathe ``f_rep_program <name> { ... }`` decl is recorded by the
parser as a mapping of named bindings to expressions written in the
existing Lathe expression language (``call``, ``ident``, literals,
lists). Each binding evaluates to an :class:`SDFExpr` so the program
body reads as a small dataflow graph; ``output = ...`` (or, if absent,
the last assigned binding) is the program's root.

Primitives, booleans, smooth booleans, and modifiers are all surfaced
as call-style expressions so authors can write::

    f_rep_program alien_blob {
      body = capsule(half_height=0.5, radius=0.3)
      head = translate(sphere(radius=0.2), offset=(0, 0, 0.6))
      output = smooth_union(body, head, k=0.1)
    }
"""

from __future__ import annotations

from typing import Any

from . import expressions as E

# ---------------------------------------------------------------------------
# Op registry
# ---------------------------------------------------------------------------


# Name -> (cls, positional-arg-names, named-arg defaults)
_PRIMITIVE_OPS: dict[str, tuple[type[E.SDFExpr], tuple[str, ...]]] = {
    "sphere": (E.Sphere, ("radius",)),
    "box": (E.Box, ("half_extents",)),
    "plane": (E.Plane, ("normal", "distance_offset")),
    "cylinder": (E.Cylinder, ("radius", "height")),
    "frustum": (E.Frustum, ("radius_bottom", "radius_top", "height")),
    "capped_cone": (E.Frustum, ("radius_bottom", "radius_top", "height")),
    "torus": (E.Torus, ("major_radius", "minor_radius")),
    "capsule": (E.Capsule, ("half_height", "radius")),
    "segment_capsule": (E.SegmentCapsule, ("a", "b", "radius")),
    "capsule_segment": (E.SegmentCapsule, ("a", "b", "radius")),
    "segment_box": (E.SegmentBox, ("a", "b", "half_width", "half_depth")),
    "box_segment": (E.SegmentBox, ("a", "b", "half_width", "half_depth")),
    "beam_segment": (E.SegmentBox, ("a", "b", "half_width", "half_depth")),
    "rect_beam": (E.SegmentBox, ("a", "b", "half_width", "half_depth")),
    "segment_extruded_profile": (E.SegmentExtrudedProfile, ("a", "b", "profile_points")),
    "swept_profile_segment": (E.SegmentExtrudedProfile, ("a", "b", "profile_points")),
    "profile_sweep_segment": (E.SegmentExtrudedProfile, ("a", "b", "profile_points")),
    "segment_lofted_profile": (E.SegmentLoftedProfile, ("a", "b", "profile_start", "profile_end")),
    "lofted_profile_segment": (E.SegmentLoftedProfile, ("a", "b", "profile_start", "profile_end")),
    "profile_loft_segment": (E.SegmentLoftedProfile, ("a", "b", "profile_start", "profile_end")),
    "tapered_segment_capsule": (E.TaperedSegmentCapsule, ("a", "b", "radius_start", "radius_end")),
    "tapered_capsule_segment": (E.TaperedSegmentCapsule, ("a", "b", "radius_start", "radius_end")),
    "rounded_slot": (E.RoundedSlot, ("length", "radius", "depth")),
    "slot": (E.RoundedSlot, ("length", "radius", "depth")),
    "extruded_polygon": (E.ExtrudedPolygon, ("profile_points", "depth")),
    "extruded_profile": (E.ExtrudedPolygon, ("profile_points", "depth")),
    "profile_prism": (E.ExtrudedPolygon, ("profile_points", "depth")),
    "revolved_profile": (E.RevolvedProfile, ("profile_points",)),
    "profile_revolve": (E.RevolvedProfile, ("profile_points",)),
    "lathe_profile": (E.RevolvedProfile, ("profile_points",)),
    "cone": (E.Cone, ("radius", "half_height")),
    "hex_prism": (E.HexPrism, ("radius", "half_height")),
    "ellipsoid": (E.Ellipsoid, ("half_extents",)),
}


_BOOLEAN_OPS: dict[str, type[E.SDFExpr]] = {
    "union": E.Union,
    "intersect": E.Intersect,
    "subtract": E.Subtract,
    "smooth_union": E.SmoothUnion,
    "smooth_intersect": E.SmoothIntersect,
    "smooth_subtract": E.SmoothSubtract,
    "chamfer_union": E.ChamferUnion,
    "chamfer_intersect": E.ChamferIntersect,
    "chamfer_subtract": E.ChamferSubtract,
    "chamfer_difference": E.ChamferSubtract,
}


_MODIFIER_OPS = {
    "translate",
    "rotate",
    "scale",
    "scale3",
    "twist",
    "bend",
    "taper",
    "mirror",
    "repeat",
    "offset",
    "shell",
    "displace",
    "warp",
}


def parse_f_rep_program(program: dict[str, Any]) -> dict[str, E.SDFExpr]:
    """Parse the body of an ``f_rep_program`` decl into named SDF nodes.

    Args:
        program: the decl dict with shape
            ``{"name": str, "values": {<binding>: <expr-ast>, ...}}``.

    Returns:
        Mapping of binding name to :class:`SDFExpr`.
    """
    bindings: dict[str, E.SDFExpr] = {}
    values = program.get("values") if isinstance(program, dict) else None
    if not isinstance(values, dict):
        return bindings
    for name, raw_expr in values.items():
        if not isinstance(name, str):
            continue
        bindings[name] = _to_sdf(raw_expr, bindings, name)
    return bindings


def compile_program(program: dict[str, Any], *, output: str | None = None) -> E.SDFExpr:
    """Compile a program decl and return the root :class:`SDFExpr`.

    Args:
        program: the decl dict (``parse_f_rep_program`` input shape).
        output: optional binding name selecting the root. Defaults to
            ``"output"`` when present, otherwise the last assigned
            binding in declaration order.

    Returns:
        The root :class:`SDFExpr` for downstream extraction.
    """
    bindings = parse_f_rep_program(program)
    if not bindings:
        raise ValueError(
            f"f_rep_program {program.get('name', '<unknown>')!r} has no bindings to compile"
        )
    root_key = output or ("output" if "output" in bindings else list(bindings)[-1])
    if root_key not in bindings:
        raise ValueError(
            f"f_rep_program output {root_key!r} not found "
            f"(known bindings: {sorted(bindings)})"
        )
    return bindings[root_key]


# ---------------------------------------------------------------------------
# AST -> SDFExpr
# ---------------------------------------------------------------------------


def _to_sdf(node: Any, bindings: dict[str, E.SDFExpr], context: str) -> E.SDFExpr:
    """Recursively turn an expression-AST node into an SDF node."""
    # Already-built SDF (allows hosted Python composition)
    if isinstance(node, E.SDFExpr):
        return node

    # Identifier (Lark / fast parser variants).
    if isinstance(node, dict):
        ntype = node.get("type") or node.get("node_type")
        if ntype in {"ident", "ident_expr", "qident"}:
            name = node.get("name") or node.get("value")
            if isinstance(name, str) and name in bindings:
                return bindings[name]
            raise ValueError(
                f"f_rep binding {context!r} references unknown identifier {name!r}"
            )
        if ntype == "call":
            op = str(node.get("name") or node.get("callee") or "")
            args = node.get("args") or []
            return _build_call(op, args, bindings, context)

    # Plain string identifier (e.g. parser emits literal references).
    if isinstance(node, str) and node in bindings:
        return bindings[node]

    raise ValueError(
        f"f_rep binding {context!r} got unsupported expression node: {node!r}"
    )


def _build_call(
    op: str, args: list[Any], bindings: dict[str, E.SDFExpr], context: str
) -> E.SDFExpr:
    op = op.lower()
    positional, named = _split_args(args)

    if op in _PRIMITIVE_OPS:
        cls, param_names = _PRIMITIVE_OPS[op]
        kwargs: dict[str, Any] = {}
        for i, value in enumerate(positional):
            if i >= len(param_names):
                raise ValueError(
                    f"f_rep {context}: too many positional args for {op!r} "
                    f"(expected {len(param_names)})"
                )
            kwargs[param_names[i]] = _resolve_value(value, bindings, context)
        for k, v in named.items():
            kwargs[k] = _resolve_value(v, bindings, context)
        return cls(**kwargs)

    if op in _BOOLEAN_OPS:
        cls = _BOOLEAN_OPS[op]
        if len(positional) < 2:
            raise ValueError(f"f_rep {context}: {op!r} requires two operands")
        a = _to_sdf(positional[0], bindings, context)
        b = _to_sdf(positional[1], bindings, context)
        kwargs = {"a": a, "b": b}
        for k, v in named.items():
            kwargs[k] = _resolve_value(v, bindings, context)
        return cls(**kwargs)

    if op == "connected_intent":
        if positional:
            child_node = positional[0]
        elif "expr" in named:
            child_node = named["expr"]
        else:
            raise ValueError(
                f"f_rep {context}: 'connected_intent' requires a child expr"
            )
        label = _resolve_value(named.get("label", "connected"), bindings, context)
        return E.ConnectedIntent(
            expr=_to_sdf(child_node, bindings, context),
            label=str(label),
        )

    if op in _MODIFIER_OPS:
        if len(positional) < 1:
            raise ValueError(f"f_rep {context}: modifier {op!r} requires a child expr")
        child = _to_sdf(positional[0], bindings, context)
        return _build_modifier(op, child, positional[1:], named, bindings, context)

    raise ValueError(f"f_rep {context}: unknown op {op!r}")


def _build_modifier(
    op: str,
    child: E.SDFExpr,
    extra_positional: list[Any],
    named: dict[str, Any],
    bindings: dict[str, E.SDFExpr],
    context: str,
) -> E.SDFExpr:
    def resolve(v):
        return _resolve_value(v, bindings, context)
    if op == "translate":
        offset = resolve(named.get("offset", extra_positional[0] if extra_positional else (0, 0, 0)))
        return E.Translate(expr=child, offset=tuple(offset))
    if op == "rotate":
        axis = resolve(named.get("axis", extra_positional[0] if extra_positional else (0, 1, 0)))
        angle = resolve(named.get("angle", extra_positional[1] if len(extra_positional) > 1 else 0.0))
        return E.Rotate(expr=child, axis=tuple(axis), angle=float(angle))
    if op == "scale":
        factor = resolve(named.get("factor", extra_positional[0] if extra_positional else 1.0))
        return E.Scale(expr=child, factor=float(factor))
    if op == "scale3":
        factors = resolve(
            named.get(
                "factors",
                named.get("scale", extra_positional[0] if extra_positional else (1, 1, 1)),
            )
        )
        return E.Scale3(expr=child, factors=tuple(float(value) for value in factors))
    if op == "twist":
        axis = resolve(named.get("axis", extra_positional[0] if extra_positional else "y"))
        rate = float(
            resolve(
                named.get(
                    "radians_per_cm",
                    named.get("rate", extra_positional[1] if len(extra_positional) > 1 else 0.0),
                )
            )
        )
        offset = float(resolve(named.get("angle_offset", 0.0)))
        return E.Twist(expr=child, axis=str(axis), radians_per_cm=rate, angle_offset=offset)
    if op == "bend":
        axis = resolve(named.get("axis", extra_positional[0] if extra_positional else "x"))
        bend_axis = resolve(
            named.get("bend_axis", extra_positional[1] if len(extra_positional) > 1 else "y")
        )
        rate = float(
            resolve(
                named.get(
                    "radians_per_cm",
                    named.get("rate", extra_positional[2] if len(extra_positional) > 2 else 0.0),
                )
            )
        )
        offset = float(resolve(named.get("angle_offset", 0.0)))
        return E.Bend(
            expr=child,
            axis=str(axis),
            bend_axis=str(bend_axis),
            radians_per_cm=rate,
            angle_offset=offset,
        )
    if op == "taper":
        axis = resolve(named.get("axis", extra_positional[0] if extra_positional else "y"))
        start_scale = float(resolve(named.get("start_scale", 1.0)))
        end_scale = float(
            resolve(
                named.get(
                    "end_scale",
                    named.get("scale", extra_positional[1] if len(extra_positional) > 1 else 0.5),
                )
            )
        )
        height = float(resolve(named.get("height", extra_positional[2] if len(extra_positional) > 2 else 1.0)))
        return E.Taper(
            expr=child,
            axis=str(axis),
            start_scale=start_scale,
            end_scale=end_scale,
            height=height,
        )
    if op == "mirror":
        axis = resolve(named.get("axis", extra_positional[0] if extra_positional else "x"))
        return E.Mirror(expr=child, axis=str(axis))
    if op == "repeat":
        axis = resolve(named.get("axis", extra_positional[0] if extra_positional else "x"))
        count = int(resolve(named.get("count", extra_positional[1] if len(extra_positional) > 1 else 3)))
        period = float(resolve(named.get("period", extra_positional[2] if len(extra_positional) > 2 else 1.0)))
        return E.Repeat(expr=child, axis=str(axis), count=count, period=period)
    if op == "offset":
        amount = float(
            resolve(
                named.get(
                    "amount",
                    named.get(
                        "offset",
                        extra_positional[0] if extra_positional else 0.0,
                    ),
                )
            )
        )
        return E.Offset(expr=child, amount=amount)
    if op == "shell":
        thickness = float(
            resolve(named.get("thickness", extra_positional[0] if extra_positional else 0.1))
        )
        return E.Shell(expr=child, thickness=thickness)
    if op == "displace":
        amplitude = float(resolve(named.get("amplitude", extra_positional[1] if len(extra_positional) > 1 else 0.05)))
        # ``noise`` is a Python-side callable; not addressable from .lth
        # source. Authors compose displacement programmatically.
        return E.Displace(expr=child, noise=None, amplitude=amplitude)
    if op == "warp":
        return E.Warp(expr=child, vector_field=None)
    raise ValueError(f"f_rep {context}: unknown modifier {op!r}")


def _split_args(args: list[Any]) -> tuple[list[Any], dict[str, Any]]:
    """Split a Lathe call ``args`` list into positional + named.

    Handles two shapes:

    * Fast parser: each arg is ``{"name": <str>|None, "value": <expr>}``.
    * Lark transformer: positional args appear as bare expression nodes;
      named args appear as ``{"node_type": "named_arg", ...}``.
    """
    positional: list[Any] = []
    named: dict[str, Any] = {}
    for item in args:
        if isinstance(item, dict):
            if "name" in item and "value" in item:
                if item["name"] is None:
                    positional.append(item["value"])
                else:
                    named[str(item["name"])] = item["value"]
                continue
            if item.get("node_type") == "named_arg":
                named[str(item["name"])] = item["value"]
                continue
        positional.append(item)
    return positional, named


def _resolve_value(node: Any, bindings: dict[str, E.SDFExpr], context: str) -> Any:
    """Resolve a non-SDF expression value (literal, list, ident-as-binding)."""
    if isinstance(node, E.SDFExpr):
        return node
    if isinstance(node, (int, float, bool)):
        return node
    if isinstance(node, str):
        if node in bindings:
            return bindings[node]
        return node
    if isinstance(node, list):
        return [_resolve_value(item, bindings, context) for item in node]
    if isinstance(node, tuple):
        return tuple(_resolve_value(item, bindings, context) for item in node)
    if isinstance(node, dict):
        kind = node.get("type") or node.get("node_type")
        if kind in {"number", "number_lit", "string", "string_lit", "literal"}:
            return node.get("value", node.get("text"))
        if kind == "unit":
            return node.get("value")
        if kind == "list":
            items = node.get("items") or node.get("value") or []
            return [_resolve_value(item, bindings, context) for item in items]
        if kind in {"ident", "ident_expr", "qident"}:
            name = node.get("name") or node.get("value")
            if isinstance(name, str) and name in bindings:
                return bindings[name]
            return name
        if kind == "call":
            return _to_sdf(node, bindings, context)
        if "value" in node and "name" not in node:
            return _resolve_value(node["value"], bindings, context)
    return node
