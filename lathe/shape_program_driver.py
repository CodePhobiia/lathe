"""Execute grammar-lowered ShapeIR v2 programs as native shape candidates.

The grammar-lowering layer already knows how to turn semantic family
requirements into a ShapeProgram and how to lower many of those ops to stable
ShapeIR v1 primitive records. This module makes that path executable inside
the shape stage without changing public .lth syntax or the stable handoff
contract.
"""

from __future__ import annotations

import math
from dataclasses import fields, replace
from typing import Any, Sequence

import numpy as np

from .asset_graph import AssetGraph
from .asset_quality.grammar_lowering import (
    GRAMMAR_LOWERING_VERSION,
    evaluate_grammar_lowering,
)
from .asset_quality.construction_graph import evaluate_construction_graph
from .asset_quality.shape_ir_v2 import (
    ShapeOp,
    ShapeProgram,
    lower_to_v1,
    materialize_v1_records_with_kernel_imports,
)
from .asset_quality.shape_ir_v2 import (
    BOOLEAN_OPS,
    EDGE_OPS,
    INTEGRATION_OPS,
    REPETITION_OPS,
    SOP_OPS,
    SOLID_OPS,
    WEAR_OPS,
)
from .shape_authoring_context import ShapeAuthoringContext, authoring_context_from_asset_graph
from .shape_ir import ShapeIR, ShapePrimitive, ShapeRegion

GRAMMAR_PROGRAM_EXECUTION_VERSION = "lathe.shape.grammar_program_execution_v1"

_PRIMITIVE_FIELDS = {field.name for field in fields(ShapePrimitive)}
_OP_FAMILY_BUCKETS: tuple[tuple[frozenset[str], str], ...] = (
    (SOLID_OPS, "solid_ops"),
    (BOOLEAN_OPS, "boolean_ops"),
    (EDGE_OPS, "edge_ops"),
    (SOP_OPS, "sop_ops"),
    (REPETITION_OPS, "repetition_ops"),
    (INTEGRATION_OPS, "integration_ops"),
    (WEAR_OPS, "wear_ops"),
)
_OP_TO_FAMILY_BUCKET = {
    op_name: bucket
    for family, bucket in _OP_FAMILY_BUCKETS
    for op_name in family
}
_GENERIC_RECIPE_FAMILIES = frozenset(
    {
        "generic",
        "hard_surface_prop_generic",
        "env_module_generic",
        "mechanical_assembly_generic",
    }
)
_RECIPE_FAMILY_ALIASES = {
    "procedural_weapon": "weapon_prop",
    "hero_sword": "weapon_prop",
    "procedural_vehicle": "vehicle_prop",
    "procedural_boat": "vehicle_prop",
    "procedural_furniture": "furniture_prop",
    "procedural_foliage": "natural_form",
    "procedural_terrain": "terrain_heightfield_system",
    "procedural_interior": "environment_architecture",
    "procedural_urban_prop": "environment_architecture",
    "procedural_road": "environment_architecture",
    "procedural_machine": "machine_console",
    "console_terminal": "machine_console",
    "control_pedestal": "machine_console",
    "sci_fi_wall_panel": "environment_architecture",
}


def _slug(value: object) -> str:
    text = str(value or "").strip().lower()
    out: list[str] = []
    previous_sep = False
    for char in text:
        if char.isalnum():
            out.append(char)
            previous_sep = False
        elif not previous_sep:
            out.append("_")
            previous_sep = True
    return "".join(out).strip("_") or "value"


def _float_tuple(value: object, length: int) -> tuple[float, ...] | None:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None


def _int_tuple(value: object, length: int) -> tuple[int, ...] | None:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    try:
        return tuple(int(item) for item in value)
    except (TypeError, ValueError):
        return None


def _points(value: object, length: int) -> list[tuple[float, ...]] | None:
    if not isinstance(value, (list, tuple)):
        return None
    out: list[tuple[float, ...]] = []
    for item in value:
        point = _float_tuple(item, length)
        if point is None:
            return None
        out.append(point)
    return out


def _point_sections(value: object) -> list[list[tuple[float, float]]] | None:
    if not isinstance(value, (list, tuple)):
        return None
    sections: list[list[tuple[float, float]]] = []
    for section in value:
        points = _points(section, 2)
        if points is None:
            return None
        sections.append([(float(u), float(v)) for u, v in points])
    return sections


def _height_data(value: object) -> list[list[float]] | None:
    if not isinstance(value, (list, tuple)):
        return None
    out: list[list[float]] = []
    for row in value:
        if not isinstance(row, (list, tuple)):
            return None
        try:
            out.append([float(item) for item in row])
        except (TypeError, ValueError):
            return None
    return out


def _mesh_vertices(value: object) -> list[list[float]] | None:
    points = _points(value, 3)
    if points is None:
        return None
    return [[float(x), float(y), float(z)] for x, y, z in points]


def _mesh_faces(value: object) -> list[list[int]] | None:
    if not isinstance(value, (list, tuple)):
        return None
    out: list[list[int]] = []
    for face in value:
        values = _int_tuple(face, 3)
        if values is None:
            return None
        a, b, c = values
        out.append([int(a), int(b), int(c)])
    return out


def _record_surface_zone_component(record: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("part", "component", "region", "primitive_type", "v2_op", "v2_purpose"):
        value = record.get(key)
        if value not in (None, "", (), [], {}):
            values.append(str(value))
    tags = record.get("tags")
    if isinstance(tags, (list, tuple)):
        values.extend(str(tag) for tag in tags if str(tag))
    tokens: set[str] = set()
    for value in values:
        tokens.update(token for token in _slug(value).split("_") if token)
    decal_tokens = {"decal", "label", "warning", "marking", "marker"}
    zone_tokens = {"zone", "zones", "plate", "panel", "marker", "marking"}
    if tokens & decal_tokens and tokens & zone_tokens:
        return "decal_zone"
    if tokens & {"wear", "worn", "chip", "chips", "scratch", "scratches", "dent", "dents", "grime"}:
        return "wear_zone"
    if tokens & {"material", "materials", "finish", "finishes", "palette"} and (
        tokens & {"zone", "zones", "surface", "surfaces", "patch", "patches", "band", "bands"}
    ):
        return "material_zone"
    return ""


def _normalise_primitive_kwargs(record: dict[str, Any]) -> dict[str, Any]:
    kwargs = {key: value for key, value in record.items() if key in _PRIMITIVE_FIELDS}
    kwargs["primitive_type"] = str(record.get("primitive_type") or "")
    kwargs["part"] = str(record.get("part") or record.get("target") or "grammar_program")
    kwargs["center"] = _float_tuple(record.get("center"), 3) or (0.0, 0.0, 0.0)
    if "extents" in kwargs:
        kwargs["extents"] = _float_tuple(record.get("extents"), 3)
    if "corner_radii" in kwargs:
        kwargs["corner_radii"] = _float_tuple(record.get("corner_radii"), 8)
    if "profile_points" in kwargs:
        kwargs["profile_points"] = _points(record.get("profile_points"), 2)
    if "profile_polygon" in kwargs:
        kwargs["profile_polygon"] = _points(record.get("profile_polygon"), 2)
    if "cross_section" in kwargs:
        kwargs["cross_section"] = _points(record.get("cross_section"), 2)
    if "sweep_path" in kwargs:
        kwargs["sweep_path"] = _points(record.get("sweep_path"), 3)
    if "cross_sections" in kwargs:
        kwargs["cross_sections"] = _point_sections(record.get("cross_sections"))
    if "section_centers" in kwargs:
        kwargs["section_centers"] = _points(record.get("section_centers"), 3)
    if "resolution" in kwargs:
        kwargs["resolution"] = _int_tuple(record.get("resolution"), 2)
    if "bounds_xy" in kwargs:
        kwargs["bounds_xy"] = _float_tuple(record.get("bounds_xy"), 4)
    if "height_data" in kwargs:
        kwargs["height_data"] = _height_data(record.get("height_data"))
    if "mesh_vertices" in kwargs:
        kwargs["mesh_vertices"] = _mesh_vertices(record.get("mesh_vertices"))
    if "mesh_faces" in kwargs:
        kwargs["mesh_faces"] = _mesh_faces(record.get("mesh_faces"))

    tags = [str(tag) for tag in record.get("tags", []) if str(tag)]
    tags.append("grammar_program")
    surface_zone_component = _record_surface_zone_component(record)
    if surface_zone_component:
        tags.extend([surface_zone_component, "material_zone", "surface_detail"])
    if record.get("v2_op"):
        tags.append(f"v2_op_{_slug(record['v2_op'])}")
    if record.get("v2_purpose"):
        purpose = str(record["v2_purpose"])
        tags.append(f"grammar_requirement_{_slug(purpose.split('.', 1)[0])}")
    kwargs["tags"] = list(dict.fromkeys(tags))
    semantic_metadata = dict(kwargs.get("semantic_metadata") or {})
    for key, value in record.items():
        if key.startswith("v2_") and key not in _PRIMITIVE_FIELDS:
            semantic_metadata[key] = value
    if surface_zone_component:
        surface_role = surface_zone_component.removesuffix("_zone")
        semantic_metadata.setdefault("component", surface_zone_component)
        semantic_metadata.setdefault("material_zone", surface_zone_component)
        semantic_metadata.setdefault("material_hint", surface_zone_component)
        semantic_metadata.setdefault("surface_role", surface_role)
        shape_ir_v2 = semantic_metadata.get("shape_ir_v2")
        if isinstance(shape_ir_v2, dict):
            shape_ir_v2.setdefault("component", surface_zone_component)
            shape_ir_v2.setdefault("material_zone", surface_zone_component)
            shape_ir_v2.setdefault("material_hint", surface_zone_component)
            shape_ir_v2.setdefault("surface_role", surface_role)
    if semantic_metadata:
        kwargs["semantic_metadata"] = semantic_metadata
    if not kwargs.get("component"):
        kwargs["component"] = surface_zone_component or str(record.get("v2_op") or "grammar_program")
    if not kwargs.get("region"):
        kwargs["region"] = kwargs["part"]
    return kwargs


def _primitive_from_record(record: dict[str, Any], index: int) -> tuple[ShapePrimitive | None, dict[str, Any] | None]:
    try:
        kwargs = _normalise_primitive_kwargs(record)
        if not kwargs["primitive_type"]:
            raise ValueError("record is missing primitive_type")
        primitive = ShapePrimitive(**kwargs)
    except (TypeError, ValueError) as exc:
        return None, {
            "code": "grammar_program_record_rejected",
            "record_index": index,
            "reason": str(exc),
            "record": {key: value for key, value in record.items() if key != "source"},
        }
    return primitive, None


def _region_from_primitive(primitive: ShapePrimitive, index: int) -> ShapeRegion:
    try:
        from .exact_solids import primitive_mesh

        mesh = primitive_mesh(primitive)
        bounds = np.asarray(mesh.bounds, dtype=np.float64)
        center = tuple(float(v) for v in ((bounds[0] + bounds[1]) * 0.5))
        extents = tuple(float(max(v, 1e-6)) for v in (bounds[1] - bounds[0]))
    except Exception:
        center = primitive.center
        if primitive.extents is not None:
            extents = primitive.extents
        elif primitive.radius is not None and primitive.height is not None:
            r = float(primitive.radius)
            h = float(primitive.height)
            if primitive.axis == "x":
                extents = (h, 2.0 * r, 2.0 * r)
            elif primitive.axis == "z":
                extents = (2.0 * r, 2.0 * r, h)
            else:
                extents = (2.0 * r, h, 2.0 * r)
        else:
            extents = (1.0, 1.0, 1.0)
    part_slug = _slug(primitive.part)
    return ShapeRegion(
        name=f"grammar_{index:03d}_{part_slug}",
        part=primitive.part,
        component=primitive.component or primitive.primitive_type,
        center=center,
        extents=extents,
        tags=[*primitive.tags, "grammar_program_region"],
        required=primitive.blend_mode != "subtract",
    )


def _asset_stub(asset_graph: AssetGraph) -> dict[str, Any]:
    recipe_family = _recipe_family_for_asset_graph(asset_graph)
    context = authoring_context_from_asset_graph(asset_graph)
    raw_source_surface = asset_graph.authoring.get("source_surface", {})
    source_surface = dict(raw_source_surface) if isinstance(raw_source_surface, dict) else {}
    if context.surface_patterns:
        source_surface["patterns"] = list(context.surface_patterns)
    if context.material_zones:
        source_surface["material_zones"] = list(context.material_zones)
    if context.surface_materials:
        source_surface["materials"] = list(context.surface_materials)
    repair_policy: dict[str, Any] = {}
    if context.repair_policy_use:
        repair_policy["use"] = context.repair_policy_use
    if context.repair_policy_mode:
        repair_policy["mode"] = context.repair_policy_mode
    if context.repair_policy_allow:
        repair_policy["allow"] = list(context.repair_policy_allow)
    if context.repair_policy_deny:
        repair_policy["deny"] = list(context.repair_policy_deny)
    stub = {
        "name": asset_graph.name,
        "kind": asset_graph.kind,
        "intent": {
            "role": asset_graph.role,
            "asset_class": str(asset_graph.authoring.get("asset_class") or ""),
            "parts": [part.name for part in asset_graph.parts],
            "materials": list(asset_graph.materials),
            "style": list(asset_graph.styles),
            "interactions": list(asset_graph.interactions),
        },
        "features": {
            "allow": list(context.feature_allow),
            "density": context.feature_density,
        },
        "surface": source_surface,
        "_recipe_family": recipe_family,
    }
    if repair_policy:
        stub["repair_policy"] = repair_policy
    return stub


def _semantic_text(asset_graph: AssetGraph) -> str:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    fragments = [
        asset_graph.name,
        asset_graph.family,
        asset_graph.kind,
        asset_graph.role,
        " ".join(str(style) for style in asset_graph.styles),
        " ".join(str(part.name) for part in asset_graph.parts),
        " ".join(str(material) for material in asset_graph.materials),
        str(authoring.get("asset_class") or ""),
        str(authoring.get("style_target") or ""),
        str(authoring.get("family_ref") or ""),
        str(authoring.get("from_family") or ""),
    ]
    source_geometry = authoring.get("source_geometry")
    if isinstance(source_geometry, dict):
        fragments.extend(str(value) for value in source_geometry.values())
    source_surface = authoring.get("source_surface")
    if isinstance(source_surface, dict):
        fragments.extend(str(value) for value in source_surface.values())
    return " ".join(fragment for fragment in fragments if fragment).lower()


def _semantic_tokens(asset_graph: AssetGraph) -> frozenset[str]:
    return frozenset(token for token in _slug(_semantic_text(asset_graph)).split("_") if token)


def _recipe_family_for_asset_graph(asset_graph: AssetGraph) -> str:
    family = str(asset_graph.family or "")
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    assembly_rules = authoring.get("assembly_rules")
    if isinstance(assembly_rules, dict) and assembly_rules.get("productions"):
        return "cga_building_grammar_system"
    text = _semantic_text(asset_graph)
    tokens = _semantic_tokens(asset_graph)
    if family == "procedural_building":
        return "cga_building_grammar_system"
    if tokens & {"cga", "facade"} or "building grammar" in text or "split repeat" in text:
        return "cga_building_grammar_system"
    if "wfc" in tokens or "wave function" in text or "tile solver" in text:
        return "wfc_tile_solver_system"
    if tokens & {"heightfield", "terrain", "erosion", "biome"}:
        return "terrain_heightfield_system"
    if tokens & {"vegetation", "tree", "branch", "canopy", "grove"}:
        return "vegetation_library_system"
    if tokens & {"sdf", "metaball", "implicit", "blob"} or "f_rep" in text or "f rep" in text:
        return "f_rep_sdf_composition_system"
    if family in _RECIPE_FAMILY_ALIASES:
        return _RECIPE_FAMILY_ALIASES[family]
    if family and family not in _GENERIC_RECIPE_FAMILIES:
        return family
    return family or "generic"


def _shape_program_from_payload(payload: dict[str, Any]) -> ShapeProgram:
    ops: list[ShapeOp] = []
    for item in payload.get("ops", []):
        if not isinstance(item, dict):
            continue
        params = item.get("parameters")
        ops.append(
            ShapeOp(
                op=str(item.get("op") or ""),
                target=item.get("target"),
                parameters=params if isinstance(params, dict) else {},
                purpose=item.get("purpose"),
            )
        )
    return ShapeProgram(
        version=str(payload.get("version") or ""),
        asset_name=str(payload.get("asset_name") or "unnamed_asset"),
        family=payload.get("family"),
        ops=tuple(ops),
    )


def _shape_program_summary(program: ShapeProgram) -> dict[str, Any]:
    family_counts: dict[str, int] = {bucket: 0 for _, bucket in _OP_FAMILY_BUCKETS}
    requirement_counts: dict[str, int] = {}
    for op in program.ops:
        bucket = _OP_TO_FAMILY_BUCKET.get(op.op)
        if bucket is not None:
            family_counts[bucket] += 1
        requirement = _op_requirement(op)
        if requirement:
            requirement_counts[requirement] = requirement_counts.get(requirement, 0) + 1
    return {
        "op_count": len(program.ops),
        "ops_by_family": family_counts,
        "ops_by_requirement": dict(sorted(requirement_counts.items())),
    }


def _op_requirement(op: ShapeOp) -> str:
    purpose = str(op.purpose or "")
    if "." in purpose:
        return purpose.split(".", 1)[0]
    return purpose


def _op_is_core(op: ShapeOp) -> bool:
    tokens = set()
    tokens.update(_slug(_op_requirement(op)).split("_"))
    return bool(tokens & _CORE_REQUIREMENT_TOKENS)


def _op_is_primary_body_shell(op: ShapeOp) -> bool:
    tokens = set()
    for value in (_op_requirement(op), op.target, op.purpose, op.op):
        tokens.update(_slug(value).split("_"))
    if not (tokens & {"body", "shell", "primary", "volume", "leaf", "cabinet", "door"}):
        return False
    feature_ops = {
        "op.panel_frame",
        "op.trim_band",
        "op.fastener_grid",
        "op.vent_slats",
        "op.corner_guard_set",
        "op.socket",
        "op.bracket",
        "op.mount_plate",
        "op.weld_seam",
    }
    if op.op in feature_ops:
        return False
    return op.op.startswith("solid.") or op.op in {"sop.polybevel", "op.shell", "op.union"}


_PRIMARY_BODY_PRESERVE_TOKENS = frozenset(
    {"body", "shell", "primary", "volume", "leaf", "cabinet", "root", "core"}
)
_CONNECTION_ROUTE_RELATIONS = frozenset({"connects_to", "routes_to", "opens_to"})
_CONNECTION_ATTACH_RELATIONS = frozenset({"attach", "attached_to", "snaps_to", "mounts_to", "auto_attach"})
_CONNECTION_SUPPORT_RELATIONS = frozenset({"supports", "contains", "depends_on"})
_DETAIL_REQUIREMENT_TOKENS = frozenset(
    {
        "trim",
        "band",
        "rail",
        "fastener",
        "bolt",
        "rivet",
        "vent",
        "slat",
        "grille",
        "panel",
        "inset",
        "groove",
        "corner",
        "guard",
        "bracket",
        "mount",
        "plate",
        "latch",
        "lock",
        "handle",
        "foot",
        "feet",
        "lid",
        "seam",
        "decal",
        "wear",
        "chip",
        "socket",
    }
)


def _op_is_feature_allow_preservation_core(op: ShapeOp) -> bool:
    requirement_tokens = frozenset(token for token in _slug(_op_requirement(op)).split("_") if token)
    if requirement_tokens & _DETAIL_REQUIREMENT_TOKENS:
        return False
    if requirement_tokens & _PRIMARY_BODY_PRESERVE_TOKENS:
        return True
    target_tokens = frozenset(token for token in _slug(op.target).split("_") if token)
    return bool(
        op.op.startswith("solid.")
        and target_tokens
        and target_tokens <= _PRIMARY_BODY_PRESERVE_TOKENS
    )


def _op_is_required_composition_authoring(op: ShapeOp, context: ShapeAuthoringContext) -> bool:
    if not (
        context.socket_ids
        or context.anchor_ids
        or context.connection_count
        or context.child_module_count
        or context.module_slot_count
        or context.nested_asset_count
    ):
        return False
    target = str(op.target or "")
    purpose = str(op.purpose or "")
    if purpose.startswith(("authored_child_modules.", "authored_interfaces.", "authored_connections.")):
        return True
    if _is_authored_connection_edge_target(target):
        return True
    return target in {
        "authored_child_module_anchor_grid",
        "authored_connection_endpoint_ports",
        "authored_socket_port",
        "authored_conduit_run",
        "authored_mount_plate",
        "authored_support_bracket",
    }


def _op_matches_authoring(op: ShapeOp, context: ShapeAuthoringContext) -> bool:
    if not context.feature_allow:
        return True
    if _op_is_required_composition_authoring(op, context):
        return True
    if _op_is_core(op) or context.matches_allowed_feature(
        _op_requirement(op),
        op.target,
        op.purpose,
        op.op,
    ):
        return True
    repair_tokens = _repair_policy_authoring_tokens(context)
    if repair_tokens:
        op_tokens = _context_token_set(
            (
                _op_requirement(op),
                str(op.target or ""),
                str(op.purpose or ""),
                op.op,
            )
        )
        if repair_tokens & op_tokens:
            return True
    integration_tokens = _context_token_set(context.integration_rules)
    if integration_tokens:
        op_tokens = _context_token_set(
            (
                _op_requirement(op),
                str(op.target or ""),
                str(op.purpose or ""),
                op.op,
            )
        )
        if integration_tokens & op_tokens:
            return True
    return False


_AUTHORING_TRIM_TOKENS = frozenset({"trim", "trimmed", "band", "rail", "stripe", "rib", "ribbed"})
_AUTHORING_FASTENER_TOKENS = frozenset(
    {
        "fastener",
        "fasteners",
        "bolt",
        "bolts",
        "bolted",
        "rivet",
        "rivets",
        "riveted",
        "screw",
        "screws",
    }
)
_AUTHORING_VENT_TOKENS = frozenset(
    {
        "vent",
        "vents",
        "vented",
        "slat",
        "slats",
        "slatted",
        "grille",
        "grilles",
        "grill",
        "louver",
        "louvers",
        "louvered",
        "louvre",
        "louvres",
        "louvred",
        "slot",
        "slots",
        "slotted",
    }
)
_AUTHORING_PANEL_TOKENS = frozenset(
    {
        "panel",
        "panels",
        "frame",
        "frames",
        "framed",
        "inset",
        "insets",
        "recess",
        "recessed",
        "groove",
        "grooves",
        "grooved",
    }
)
_AUTHORING_PANEL_FRAME_DUPLICATE_TOKENS = frozenset({"frame", "frames", "framed"})
_AUTHORING_DECAL_TOKENS = frozenset(
    {"decal", "decals", "label", "labels", "warning", "warnings", "marking", "markings", "marker", "markers"}
)
_AUTHORING_MATERIAL_TOKENS = frozenset(
    {"material", "materials", "finish", "finishes", "palette", "paint", "painted", "base", "biome"}
)
_AUTHORING_SURFACE_ZONE_TOKENS = frozenset(
    {"zone", "zones", "surface", "surfaces", "patch", "patches", "band", "bands", "mask", "masks", "plate", "panel"}
)
_AUTHORING_SURFACE_EDGE_TOKENS = frozenset(
    {"edge", "edges", "corner", "corners", "surface", "surfaces", "rim", "rims"}
)
_AUTHORING_INSET_TOKENS = frozenset({"inset", "insets", "recess", "recessed"})
_AUTHORING_PANEL_LINE_TOKENS = frozenset({"groove", "grooves", "grooved", "cutline", "cutlines", "seamline"})
_AUTHORING_GUARD_TOKENS = frozenset(
    {
        "corner",
        "corners",
        "guard",
        "guards",
        "guarded",
        "bumper",
        "bumpers",
        "protector",
        "protectors",
        "protected",
    }
)
_AUTHORING_BRACKET_TOKENS = frozenset(
    {
        "bracket",
        "brackets",
        "bracketed",
        "brace",
        "braces",
        "braced",
        "support",
        "supports",
        "gusset",
        "gussets",
        "gusseted",
    }
)
_AUTHORING_BRACKET_DUPLICATE_TOKENS = frozenset(
    token for token in _AUTHORING_BRACKET_TOKENS if token not in {"support", "supports"}
)
_AUTHORING_MOUNT_TOKENS = frozenset(
    {"mount", "mounts", "mounted", "mounting", "plate", "plates", "plated", "boss", "bosses"}
)
_AUTHORING_MOUNT_DUPLICATE_TOKENS = frozenset({"mount", "mounts", "mounted", "mounting", "boss", "bosses"})
_AUTHORING_LATCH_TOKENS = frozenset(
    {
        "latch",
        "latches",
        "latched",
        "lock",
        "locks",
        "locked",
        "clasp",
        "clasps",
        "clasped",
        "catch",
        "catches",
        "hasp",
        "hasps",
    }
)
_AUTHORING_WELD_TOKENS = frozenset(
    {"weld", "welds", "welded", "seam", "seams", "bead", "beads", "beaded"}
)
_AUTHORING_HANDLE_TOKENS = frozenset(
    {
        "handle",
        "handles",
        "handled",
        "grip",
        "grips",
        "gripped",
        "pull",
        "pulls",
        "grab",
        "grabs",
        "bar",
        "bars",
    }
)
_AUTHORING_HINGE_TOKENS = frozenset(
    {
        "hinge",
        "hinges",
        "hinged",
        "pintle",
        "pintles",
        "knuckle",
        "knuckles",
        "leaf",
        "leaves",
    }
)
_AUTHORING_CONDUIT_TOKENS = frozenset(
    {
        "cable",
        "cables",
        "wire",
        "wires",
        "wired",
        "pipe",
        "pipes",
        "piped",
        "hose",
        "hoses",
        "conduit",
        "conduits",
        "loom",
        "looms",
    }
)
_AUTHORING_SOCKET_TOKENS = frozenset(
    {
        "socket",
        "sockets",
        "socketed",
        "port",
        "ports",
        "ported",
        "connector",
        "connectors",
        "connected",
        "plug",
        "plugs",
        "jack",
        "jacks",
        "slot",
        "slots",
    }
)
_AUTHORING_WEAR_TOKENS = frozenset(
    {
        "wear",
        "worn",
        "weathered",
        "damage",
        "damaged",
        "distress",
        "distressed",
        "chip",
        "chips",
        "chipped",
        "scratch",
        "scratches",
        "scratched",
        "dent",
        "dents",
        "dented",
        "edge",
        "edges",
    }
)
_AUTHORING_GRIME_TOKENS = frozenset(
    {
        "grime",
        "grimy",
        "dirt",
        "dirty",
        "soot",
        "oil",
        "oily",
        "stain",
        "stains",
        "stained",
        "smudge",
        "smudges",
    }
)
_AUTHORING_MIRROR_TOKENS = frozenset(
    {
        "mirror",
        "mirrors",
        "mirrored",
        "symmetry",
        "symmetric",
        "reflection",
        "reflected",
    }
)
_AUTHORING_INTEGRATION_BREAK_TOKENS = frozenset(
    {"break", "split", "splits", "seam", "seams", "threshold", "parting", "partingline"}
)
_AUTHORING_ARMORED_STYLE_TOKENS = frozenset(
    {
        "armor",
        "armored",
        "armour",
        "armoured",
        "plated",
        "reinforced",
        "rugged",
        "heavy",
        "military",
        "industrial",
    }
)
_AUTHORING_LIGHTWEIGHT_STYLE_TOKENS = frozenset(
    {"light", "lightweight", "ventilated", "open", "agile", "portable"}
)
_AUTHORING_SLEEK_STYLE_TOKENS = frozenset(
    {"sleek", "clean", "minimal", "streamlined", "smooth", "flush"}
)
_AUTHORING_STRUCTURAL_PROFILE_TOKENS = frozenset(
    {
        "gantry",
        "scaffold",
        "scaffolding",
        "brace",
        "braced",
        "truss",
        "frame",
        "framed",
        "support",
        "structural",
        "service",
    }
)
_AUTHORING_ROUTE_STRUCTURE_TOKENS = frozenset(
    {
        "route",
        "routed",
        "service",
        "trench",
        "conduit",
        "cable",
        "pipe",
        "duct",
        "channel",
        "raceway",
    }
)
_REPAIR_POLICY_HARDSURFACE_DEFAULT_FEATURES = (
    "edge_break",
    "trim_band",
    "rail",
    "fastener_grid",
    "panel_frame",
    "support_bracket",
)
_REPAIR_POLICY_ACTION_FEATURES: dict[str, tuple[str, ...]] = {
    "add_secondary_features": ("trim_band", "rail", "capsule_strut", "fastener_grid", "vent_slats", "weld_seam"),
    "restore_edge_treatment": ("edge_break", "weld_seam", "edge_wear"),
    "increase_panel_depth": ("panel_frame", "trim_band", "inset_panel"),
    "improve_attachment_integration": (
        "socket_point",
        "support_bracket",
        "mount_plate",
        "latch_plate",
        "pull_handle",
        "conduit_run",
        "rail",
        "capsule_strut",
    ),
    "refine_support_layout": ("support_bracket", "mount_plate", "rail", "structural_beam", "truss_frame"),
    "restore_hinge_alignment": ("hinge", "support_bracket"),
    "reauthor_surface_layer": ("edge_wear", "grime_mask"),
    "shroud_exposed_frame": ("tube_shroud",),
}
_REPAIR_POLICY_FEATURE_TOKENS: dict[str, frozenset[str]] = {
    "edge_break": frozenset({"bevel", "beveled", "chamfer", "round", "rounded", "soft"}),
    "trim_band": _AUTHORING_TRIM_TOKENS,
    "fastener_grid": _AUTHORING_FASTENER_TOKENS | frozenset({"grid"}),
    "vent_slats": _AUTHORING_VENT_TOKENS,
    "panel_frame": frozenset({"panel", "panels", "frame", "frames", "framed"}),
    "inset_panel": _AUTHORING_INSET_TOKENS | _AUTHORING_PANEL_LINE_TOKENS,
    "panel_groove": _AUTHORING_PANEL_LINE_TOKENS,
    "corner_guard": _AUTHORING_GUARD_TOKENS,
    "support_bracket": _AUTHORING_BRACKET_TOKENS,
    "socket_point": _AUTHORING_SOCKET_TOKENS,
    "mount_plate": _AUTHORING_MOUNT_TOKENS,
    "latch_plate": _AUTHORING_LATCH_TOKENS,
    "hinge": _AUTHORING_HINGE_TOKENS,
    "pull_handle": _AUTHORING_HANDLE_TOKENS,
    "conduit_run": _AUTHORING_CONDUIT_TOKENS,
    "tube_shroud": _AUTHORING_CONDUIT_TOKENS | frozenset({"tube", "tubes", "shroud", "shrouded"}),
    "rail": frozenset({"rail", "rails", "runner", "runners", "track", "tracks", "guide", "guides"}),
    "structural_beam": frozenset({"beam", "beams", "girder", "girders", "i_beam", "support"}),
    "truss_frame": frozenset({"truss", "trusses", "lattice", "brace", "braced"}),
    "ladder_frame": frozenset({"ladder", "ladders", "rung", "rungs"}),
    "capsule_strut": frozenset({"strut", "struts", "rod", "rods", "capsule", "rounded"}),
    "edge_wear": _AUTHORING_WEAR_TOKENS,
    "grime_mask": _AUTHORING_GRIME_TOKENS,
    "weld_seam": _AUTHORING_WELD_TOKENS,
    "mirror_instances": _AUTHORING_MIRROR_TOKENS,
}

_CONSTRUCTION_GRAPH_FEATURE_REQUESTS_BY_NODE_TYPE: dict[str, tuple[str, ...]] = {
    "trim": ("construction_graph.trim_band",),
    "rail": ("construction_graph.rail",),
    "beam": ("construction_graph.structural_beam",),
    "truss": ("construction_graph.truss_frame",),
    "ladder": ("construction_graph.ladder_frame",),
    "strut": ("construction_graph.capsule_strut",),
    "frame": ("construction_graph.panel_frame",),
    "bracket": ("construction_graph.support_bracket",),
    "vent": ("construction_graph.vent_slats",),
    "conduit": ("construction_graph.conduit_run",),
    "latch": ("construction_graph.latch_plate",),
    "weld": ("construction_graph.weld_seam",),
    "fastener": ("construction_graph.fastener_grid",),
    "guard": ("construction_graph.corner_guard",),
    "socket": ("construction_graph.socket_port",),
    "mount": ("construction_graph.mount_plate",),
    "handle": ("construction_graph.pull_handle",),
    "hinge": ("construction_graph.hinge_mount_plate",),
    "inset": ("construction_graph.recessed_panel",),
    "decal_zone": ("construction_graph.panel_frame",),
    "wear_zone": ("construction_graph.chip_edges",),
}

_CONSTRUCTION_GRAPH_SURFACE_REQUESTS_BY_NODE_TYPE: dict[str, tuple[str, ...]] = {
    "decal_zone": ("construction_graph.decal_zone",),
    "material_zone": ("construction_graph.material_zone",),
    "wear_zone": ("construction_graph.edge_wear",),
}

_CONSTRUCTION_GRAPH_TEXT_FEATURE_REQUESTS: tuple[tuple[frozenset[str], str], ...] = (
    (_AUTHORING_TRIM_TOKENS, "construction_graph.trim_band"),
    (_AUTHORING_FASTENER_TOKENS, "construction_graph.fastener_grid"),
    (_AUTHORING_VENT_TOKENS, "construction_graph.vent_slats"),
    (_AUTHORING_PANEL_TOKENS, "construction_graph.panel_frame"),
    (_AUTHORING_INSET_TOKENS, "construction_graph.recessed_panel"),
    (_AUTHORING_PANEL_LINE_TOKENS, "construction_graph.panel_groove"),
    (_AUTHORING_GUARD_TOKENS, "construction_graph.corner_guard"),
    (_AUTHORING_BRACKET_TOKENS, "construction_graph.support_bracket"),
    (_AUTHORING_MOUNT_DUPLICATE_TOKENS, "construction_graph.mount_plate"),
    (_AUTHORING_LATCH_TOKENS, "construction_graph.latch_plate"),
    (_AUTHORING_WELD_TOKENS, "construction_graph.weld_seam"),
    (_AUTHORING_HANDLE_TOKENS, "construction_graph.pull_handle"),
    (_AUTHORING_HINGE_TOKENS, "construction_graph.hinge_mount_plate"),
    (_AUTHORING_CONDUIT_TOKENS, "construction_graph.conduit_run"),
    (frozenset({"rail", "rails", "runner", "runners", "track", "tracks", "guide", "guides"}), "construction_graph.rail"),
    (frozenset({"beam", "beams", "girder", "girders", "i_beam", "support"}), "construction_graph.structural_beam"),
    (frozenset({"truss", "trusses", "lattice", "brace", "braced"}), "construction_graph.truss_frame"),
    (frozenset({"ladder", "ladders", "rung", "rungs"}), "construction_graph.ladder_frame"),
    (frozenset({"strut", "struts", "rod", "rods", "capsule", "rounded"}), "construction_graph.capsule_strut"),
    (_AUTHORING_SOCKET_TOKENS, "construction_graph.socket_port"),
    (_AUTHORING_GRIME_TOKENS, "construction_graph.grime_mask"),
    (_AUTHORING_WEAR_TOKENS, "construction_graph.chip_edges"),
    (_AUTHORING_MIRROR_TOKENS, "construction_graph.mirror_instances"),
)

_CONSTRUCTION_GRAPH_REPAIR_ROUTES: dict[str, dict[str, Any]] = {
    "construction_graph.trim_band": {
        "actions": ["restore_edge_treatment", "increase_panel_depth"],
        "lowered_operation": "op.trim_band",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.fastener_grid": {
        "actions": ["add_secondary_features"],
        "lowered_operation": "op.fastener_grid",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.vent_slats": {
        "actions": ["add_secondary_features"],
        "lowered_operation": "op.vent_slats",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.panel_frame": {
        "actions": ["increase_panel_depth", "add_secondary_features"],
        "lowered_operation": "op.panel_frame",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.recessed_panel": {
        "actions": ["increase_panel_depth"],
        "lowered_operation": "op.inset",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.panel_groove": {
        "actions": ["restore_edge_treatment", "increase_panel_depth"],
        "lowered_operation": "op.cut_panel_line",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.corner_guard": {
        "actions": ["improve_attachment_integration", "restore_edge_treatment"],
        "lowered_operation": "op.corner_guard_set",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.support_bracket": {
        "actions": ["improve_attachment_integration", "refine_support_layout"],
        "lowered_operation": "op.bracket",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.rail": {
        "actions": ["add_secondary_features", "refine_support_layout"],
        "lowered_operation": "solid.rail",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.structural_beam": {
        "actions": ["refine_support_layout"],
        "lowered_operation": "solid.structural_beam",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.truss_frame": {
        "actions": ["refine_support_layout"],
        "lowered_operation": "solid.truss_frame",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.ladder_frame": {
        "actions": ["refine_support_layout"],
        "lowered_operation": "solid.ladder_frame",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.capsule_strut": {
        "actions": ["add_secondary_features", "improve_attachment_integration"],
        "lowered_operation": "solid.capsule",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.mount_plate": {
        "actions": ["improve_attachment_integration"],
        "lowered_operation": "op.mount_plate",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.latch_plate": {
        "actions": ["improve_attachment_integration"],
        "lowered_operation": "op.mount_plate",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.hinge_mount_plate": {
        "actions": ["restore_hinge_alignment", "improve_attachment_integration"],
        "lowered_operation": "solid.hinge",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.pull_handle": {
        "actions": ["improve_attachment_integration"],
        "lowered_operation": "solid.handle",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.conduit_run": {
        "actions": ["add_secondary_features"],
        "lowered_operation": "sop.polywire",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.socket_port": {
        "actions": ["improve_attachment_integration"],
        "lowered_operation": "op.socket",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.chip_edges": {
        "actions": ["restore_edge_treatment"],
        "lowered_operation": "op.chip_edges",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.grime_mask": {
        "actions": ["reauthor_surface_layer"],
        "lowered_operation": "op.grime_mask",
        "target_ir": "SurfaceProgram",
    },
    "construction_graph.weld_seam": {
        "actions": ["restore_edge_treatment", "add_secondary_features"],
        "lowered_operation": "op.weld_seam",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.mirror_instances": {
        "actions": ["add_secondary_features"],
        "lowered_operation": "op.mirror",
        "target_ir": "ShapeProgram",
    },
    "construction_graph.decal_zone": {
        "actions": ["reauthor_surface_layer"],
        "lowered_operation": "sop.polyextrude",
        "target_ir": "ShapeProgram+SurfaceProgram",
        "surface_role": "decal",
    },
    "construction_graph.material_zone": {
        "actions": ["reauthor_surface_layer"],
        "lowered_operation": "sop.polyextrude",
        "target_ir": "ShapeProgram+SurfaceProgram",
        "surface_role": "material_zone",
    },
    "construction_graph.edge_wear": {
        "actions": ["restore_edge_treatment", "reauthor_surface_layer"],
        "lowered_operation": "op.chip_edges",
        "target_ir": "ShapeProgram+SurfaceProgram",
        "surface_role": "wear",
    },
}

_CONSTRUCTION_GRAPH_PANEL_REQUEST_TOKENS = frozenset(
    {
        "panel",
        "panels",
        "plate",
        "plates",
        "faceplate",
        "faceplates",
        "armor",
        "armour",
        "lid",
        "hatch",
        "door",
        "cover",
        "face",
        "front",
        "frame",
        "framed",
    }
)
_AUTHORED_BODY_WIDTH_CM = 52.0
_AUTHORED_BODY_HEIGHT_CM = 34.0
_AUTHORED_BODY_DEPTH_CM = 20.0
_AUTHORED_BODY_CENTER = (0.0, 0.0, 0.0)


def _record_requirement_value(record: dict[str, Any]) -> str:
    purpose = str(record.get("v2_purpose") or "")
    if "." in purpose:
        return purpose.split(".", 1)[0]
    return purpose


def _record_core_tokens(record: dict[str, Any]) -> frozenset[str]:
    values = [
        _record_requirement_value(record),
        record.get("part"),
        record.get("component"),
        record.get("region"),
        " ".join(str(tag) for tag in record.get("tags", []) if str(tag)),
    ]
    tokens: set[str] = set()
    for value in values:
        tokens.update(token for token in _slug(value).split("_") if token)
    return frozenset(tokens)


def _record_is_layout_core(record: dict[str, Any]) -> bool:
    return bool(_record_core_tokens(record) & _CORE_REQUIREMENT_TOKENS)


def _record_bounds(record: dict[str, Any]) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    vertices = record.get("mesh_vertices")
    if isinstance(vertices, list) and vertices:
        try:
            points = [
                (float(vertex[0]), float(vertex[1]), float(vertex[2]))
                for vertex in vertices
                if isinstance(vertex, (list, tuple)) and len(vertex) == 3
            ]
        except (TypeError, ValueError):
            points = []
        if points:
            return (
                tuple(min(point[index] for point in points) for index in range(3)),
                tuple(max(point[index] for point in points) for index in range(3)),
            )

    center = _float_tuple(record.get("center"), 3) or (0.0, 0.0, 0.0)
    primitive_type = str(record.get("primitive_type") or "")
    extents = _float_tuple(record.get("extents"), 3)
    if extents is not None:
        return (
            tuple(center[index] - extents[index] * 0.5 for index in range(3)),
            tuple(center[index] + extents[index] * 0.5 for index in range(3)),
        )

    if primitive_type == "extruded_profile":
        profile = _points(record.get("profile_polygon"), 2)
        try:
            height = float(record.get("extrude_height"))
        except (TypeError, ValueError):
            height = 0.0
        axis = str(record.get("axis") or "y")
        if profile is not None and height > 0.0 and axis in {"x", "y", "z"}:
            axis_index = {"x": 0, "y": 1, "z": 2}[axis]
            plane_axes = tuple(index for index in range(3) if index != axis_index)
            mins = [center[0], center[1], center[2]]
            maxs = [center[0], center[1], center[2]]
            mins[axis_index] = center[axis_index] - height * 0.5
            maxs[axis_index] = center[axis_index] + height * 0.5
            for offset_index, world_axis in enumerate(plane_axes):
                values = [float(point[offset_index]) for point in profile]
                mins[world_axis] = center[world_axis] + min(values)
                maxs[world_axis] = center[world_axis] + max(values)
            return (tuple(mins), tuple(maxs))

    radius = None
    try:
        if record.get("radius") is not None:
            radius = float(record["radius"])
    except (TypeError, ValueError):
        radius = None
    if primitive_type == "sphere" and radius is not None:
        return (
            tuple(center[index] - radius for index in range(3)),
            tuple(center[index] + radius for index in range(3)),
        )
    if primitive_type == "cylinder" and radius is not None:
        try:
            height = float(record.get("height"))
        except (TypeError, ValueError):
            height = radius * 2.0
        axis = str(record.get("axis") or "y")
        extents_list = [radius * 2.0, radius * 2.0, radius * 2.0]
        extents_list[{"x": 0, "y": 1, "z": 2}.get(axis, 1)] = height
        return (
            tuple(center[index] - extents_list[index] * 0.5 for index in range(3)),
            tuple(center[index] + extents_list[index] * 0.5 for index in range(3)),
        )

    return None


def _default_authoring_layout() -> dict[str, tuple[float, float, float] | float]:
    extents = (_AUTHORED_BODY_WIDTH_CM, _AUTHORED_BODY_HEIGHT_CM, _AUTHORED_BODY_DEPTH_CM)
    center = _AUTHORED_BODY_CENTER
    return {
        "center": center,
        "extents": extents,
        "front_z": center[2] + extents[2] * 0.5,
    }


def _authoring_layout_for_program(program: ShapeProgram) -> dict[str, tuple[float, float, float] | float]:
    try:
        records = lower_to_v1(program).v1_records
    except Exception:
        return _default_authoring_layout()
    bounds: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for record in records:
        if str(record.get("blend_mode") or "union") == "subtract":
            continue
        if not _record_is_layout_core(dict(record)):
            continue
        record_bounds = _record_bounds(dict(record))
        if record_bounds is not None:
            bounds.append(record_bounds)
    if not bounds:
        return _default_authoring_layout()
    mins = tuple(min(item[0][index] for item in bounds) for index in range(3))
    maxs = tuple(max(item[1][index] for item in bounds) for index in range(3))
    extents = tuple(max(maxs[index] - mins[index], 1.0) for index in range(3))
    center = tuple((mins[index] + maxs[index]) * 0.5 for index in range(3))
    return {
        "center": center,
        "extents": extents,
        "front_z": maxs[2],
    }


def _layout_vector(
    layout: dict[str, tuple[float, float, float] | float],
    key: str,
) -> tuple[float, float, float]:
    value = layout.get(key)
    if isinstance(value, tuple) and len(value) == 3:
        return value
    return _default_authoring_layout()[key]  # type: ignore[return-value]


def _layout_scalar(
    layout: dict[str, tuple[float, float, float] | float],
    key: str,
) -> float:
    value = layout.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    default = _default_authoring_layout()[key]
    return float(default) if isinstance(default, (int, float)) else 0.0


def _layout_offset(
    layout: dict[str, tuple[float, float, float] | float],
    x: float,
    y: float,
) -> tuple[float, float]:
    center = _layout_vector(layout, "center")
    extents = _layout_vector(layout, "extents")
    x_scale = extents[0] / _AUTHORED_BODY_WIDTH_CM
    y_scale = extents[1] / _AUTHORED_BODY_HEIGHT_CM
    return (center[0] + float(x) * x_scale, center[1] + float(y) * y_scale)


def _authored_front_center(
    x: float = 0.0,
    y: float = 0.0,
    *,
    thickness_cm: float = 0.0,
    clearance_cm: float = 0.04,
    layout: dict[str, tuple[float, float, float] | float] | None = None,
) -> tuple[float, float, float]:
    active_layout = layout or _default_authoring_layout()
    offset_x, offset_y = _layout_offset(active_layout, x, y)
    front_z = _layout_scalar(active_layout, "front_z")
    return (
        offset_x,
        offset_y,
        front_z + max(0.0, float(thickness_cm)) * 0.5 + max(0.0, float(clearance_cm)),
    )


def _shape_op_tokens(op: ShapeOp) -> frozenset[str]:
    tokens: set[str] = set()
    for value in (op.op, op.target, op.purpose, _op_requirement(op)):
        tokens.update(token for token in _slug(value).split("_") if token)
    return frozenset(tokens)


def _authoring_request_tokens(context: ShapeAuthoringContext) -> frozenset[str]:
    tokens: set[str] = set(context.allow_tokens)
    tokens.update(context.surface_pattern_tokens)
    tokens.update(_repair_policy_authoring_tokens(context))
    tokens.update(_context_token_set((context.style_target,)))
    style_pack_tokens = _context_token_set((context.style_pack,))
    tokens.update(style_pack_tokens)
    if style_pack_tokens & _AUTHORING_ARMORED_STYLE_TOKENS:
        tokens.update(_AUTHORING_TRIM_TOKENS)
        tokens.update(_AUTHORING_PANEL_TOKENS)
        tokens.update(_AUTHORING_GUARD_TOKENS)
        tokens.update(_AUTHORING_FASTENER_TOKENS)
    if style_pack_tokens & _AUTHORING_LIGHTWEIGHT_STYLE_TOKENS:
        tokens.update(_AUTHORING_VENT_TOKENS)
        tokens.update(_AUTHORING_PANEL_LINE_TOKENS)
    if style_pack_tokens & _AUTHORING_SLEEK_STYLE_TOKENS:
        tokens.update(_AUTHORING_PANEL_TOKENS)
        tokens.update(_AUTHORING_INSET_TOKENS)
    structural_tokens = _context_token_set((context.structural_profile,))
    route_tokens = _context_token_set((context.route_structure,))
    tokens.update(structural_tokens)
    tokens.update(route_tokens)
    if structural_tokens & _AUTHORING_STRUCTURAL_PROFILE_TOKENS:
        tokens.update(_AUTHORING_BRACKET_TOKENS)
        tokens.update(_AUTHORING_GUARD_TOKENS)
        tokens.update(_AUTHORING_TRIM_TOKENS)
    if route_tokens & _AUTHORING_ROUTE_STRUCTURE_TOKENS:
        tokens.update(_AUTHORING_CONDUIT_TOKENS)
        tokens.update(_AUTHORING_SOCKET_TOKENS)
        tokens.update(_AUTHORING_PANEL_LINE_TOKENS)
    if context.socket_ids or context.attach_connection_count or context.external_connection_count:
        tokens.update(_AUTHORING_SOCKET_TOKENS)
        tokens.update(_AUTHORING_MOUNT_TOKENS)
    if context.anchor_ids or context.support_connection_count or context.child_module_count or context.nested_asset_count:
        tokens.update(_AUTHORING_MOUNT_TOKENS)
        tokens.update(_AUTHORING_BRACKET_TOKENS)
    if context.route_connection_count or context.connection_segment_count:
        tokens.update(_AUTHORING_CONDUIT_TOKENS)
        tokens.update(_AUTHORING_SOCKET_TOKENS)
    if context.branch_connection_count:
        tokens.update(_AUTHORING_PANEL_LINE_TOKENS)
        tokens.update(_AUTHORING_SOCKET_TOKENS)
    panelization_tokens = _context_token_set((context.panelization,))
    if panelization_tokens and not (panelization_tokens & {"off", "none", "low"}):
        tokens.update({"panel", "panels", "panelization", "frame", "inset"})
        if panelization_tokens & {"high", "hero", "dense", "ultra"}:
            tokens.update({"groove", "grooved", "cutline", "seamline"})
    tokens.update(_context_token_set((context.silhouette_profile,)))
    for values in (
        context.styles,
        context.material_zones,
        context.surface_materials,
        context.integration_rules,
        context.preservation_intents,
    ):
        tokens.update(_context_token_set(values))
    return frozenset(tokens)


def _authoring_explicit_request_tokens(context: ShapeAuthoringContext) -> frozenset[str]:
    tokens: set[str] = set()
    for values in (
        tuple(context.feature_allow),
        tuple(context.surface_patterns),
        (context.style_target,),
        (context.panelization,),
        (context.style_pack,),
        (context.silhouette_profile,),
        (context.structural_profile,),
        (context.route_structure,),
        tuple(context.styles),
        tuple(context.material_zones),
        tuple(context.surface_materials),
        tuple(context.integration_rules),
        tuple(context.preservation_intents),
        (context.repair_policy_use,),
        (context.repair_policy_mode,),
        tuple(context.repair_policy_allow),
        tuple(context.socket_ids),
        tuple(context.anchor_ids),
        (context.connection_layout_mode,),
    ):
        tokens.update(_context_token_set(values))
    tokens.update(_repair_policy_authoring_tokens(context))
    panelization_tokens = _context_token_set((context.panelization,))
    if panelization_tokens and not (panelization_tokens & {"off", "none", "low"}):
        tokens.update({"panel", "panels", "inset"})
        if panelization_tokens & {"high", "hero", "dense", "ultra"}:
            tokens.update({"groove", "grooved", "cutline", "seamline"})
    return frozenset(tokens)


def _program_has_authoring_feature(
    program: ShapeProgram,
    op_names: frozenset[str],
    feature_tokens: frozenset[str],
) -> bool:
    for op in program.ops:
        if op.op in op_names:
            return True
        if _shape_op_tokens(op) & feature_tokens:
            return True
    return False


def _program_has_core_body(program: ShapeProgram) -> bool:
    return any(_op_is_primary_body_shell(op) for op in program.ops)


def _primary_body_target_for_program(program: ShapeProgram) -> str:
    for op in program.ops:
        if _op_is_primary_body_shell(op):
            return str(op.target or "body")
    return "authored_body"


def _primary_body_context_key_for_program(program: ShapeProgram) -> str:
    target = _primary_body_target_for_program(program)
    root, separator, _ = target.partition(".")
    if separator and root:
        return root
    return target


def _authoring_injection_report(
    op: ShapeOp,
    *,
    reason: str,
    matched_tokens: frozenset[str],
) -> dict[str, Any]:
    report = {
        "op": op.op,
        "target": op.target,
        "purpose": op.purpose,
        "reason": reason,
        "matched_tokens": sorted(matched_tokens),
    }
    center = op.parameters.get("center")
    if isinstance(center, (list, tuple)) and len(center) == 3:
        report["center"] = [float(value) for value in center]
    axis = op.parameters.get("axis")
    if axis:
        report["axis"] = str(axis)
    source = op.parameters.get("source")
    if isinstance(source, str) and source:
        report["source"] = source
    for key in ("pattern", "target_face", "side", "normal_axis", "row_axis", "column_axis", "line_axis"):
        value = op.parameters.get(key)
        if value not in (None, "", (), [], {}):
            report[key] = str(value)
    for key in (
        "count",
        "rows",
        "columns",
        "seed",
        "jitter_cm",
        "snap_to_grid_cm",
        "snap_cm",
        "spacing_cm",
        "row_spacing_cm",
        "column_spacing_cm",
        "width_cm",
        "height_cm",
        "length_cm",
        "depth_cm",
        "thickness_cm",
        "margin_cm",
        "seat_depth_cm",
        "normal_sign",
    ):
        value = op.parameters.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            report[key] = float(value) if isinstance(value, float) else int(value)
    seam_group = op.parameters.get("seam_group") or op.parameters.get("seam")
    if seam_group:
        report["seam_group"] = str(seam_group)
    if isinstance(source, dict):
        source_parameters = source.get("parameters")
        if isinstance(source_parameters, dict):
            report["source_box_cm"] = {
                key: float(source_parameters[key])
                for key in ("width_cm", "height_cm", "depth_cm")
                if key in source_parameters
            }
    path = op.parameters.get("path")
    if isinstance(path, (list, tuple)):
        report["path_point_count"] = len(path)
    return report


_MODULE_FOOTPRINT_SOURCE_BY_KIND: dict[str, dict[str, Any]] = {
    "building": {
        "op": "solid.rounded_box",
        "parameters": {
            "width_cm": 11.0,
            "height_cm": 7.0,
            "depth_cm": 1.2,
            "radius_cm": 0.35,
        },
    },
    "road": {
        "op": "solid.panel",
        "parameters": {
            "width_cm": 15.0,
            "height_cm": 3.2,
            "thickness_cm": 0.45,
            "axis": "z",
            "rounding_cm": 0.12,
        },
    },
    "terrain": {
        "op": "solid.sphere",
        "parameters": {
            "radius_cm": 4.2,
        },
    },
    "infrastructure": {
        "op": "solid.structural_beam",
        "parameters": {
            "length_cm": 10.0,
            "width_cm": 1.1,
            "height_cm": 1.1,
            "profile_shape": "i_beam",
            "axis": "x",
        },
    },
    "vehicle": {
        "op": "solid.capsule",
        "parameters": {
            "radius_cm": 2.4,
            "length_cm": 14.0,
            "axis": "x",
            "sections": 16,
            "rings": 8,
        },
    },
    "boat": {
        "op": "solid.extruded_profile",
        "parameters": {
            "profile_polygon": ((-7.5, -1.9), (5.6, -1.9), (7.8, 0.0), (5.6, 1.9), (-7.5, 1.9)),
            "extrude_height_cm": 0.9,
            "axis": "z",
        },
    },
    "machine": {
        "op": "solid.gear",
        "parameters": {
            "teeth": 14,
            "pitch_radius_cm": 3.1,
            "thickness_cm": 1.25,
            "bore_radius_cm": 0.65,
            "axis": "z",
        },
    },
    "interior": {
        "op": "solid.panel",
        "parameters": {
            "width_cm": 11.5,
            "height_cm": 6.2,
            "thickness_cm": 0.95,
            "axis": "z",
            "rounding_cm": 0.35,
        },
    },
    "furniture": {
        "op": "solid.rounded_box",
        "parameters": {
            "width_cm": 7.5,
            "height_cm": 4.8,
            "depth_cm": 0.7,
            "radius_cm": 0.55,
        },
    },
    "foliage": {
        "op": "solid.sphere",
        "parameters": {
            "radius_cm": 3.4,
        },
    },
    "generic": {
        "op": "solid.panel",
        "parameters": {
            "width_cm": 6.0,
            "height_cm": 4.0,
            "thickness_cm": 0.6,
            "axis": "z",
            "rounding_cm": 0.2,
        },
    },
}


def _module_footprint_source(kind: str) -> dict[str, Any]:
    source_spec = _MODULE_FOOTPRINT_SOURCE_BY_KIND.get(kind) or _MODULE_FOOTPRINT_SOURCE_BY_KIND["generic"]
    parameters = dict(source_spec.get("parameters") or {})
    parameters.setdefault("center", (0.0, 0.0, 0.0))
    return {
        "op": str(source_spec.get("op") or "solid.panel"),
        "target": f"{kind}_module_footprint_source",
        "parameters": parameters,
        "purpose": f"child_modules.{kind}_footprint_source",
    }


def _module_slot_center(
    slot: dict[str, Any],
    layout: dict[str, tuple[float, float, float] | float],
) -> tuple[float, float, float]:
    position = slot.get("normalized_position")
    if not isinstance(position, (list, tuple)) or len(position) < 3:
        position = (0.0, 0.0, 0.0)
    try:
        x_norm = float(position[0])
        z_norm = float(position[2])
    except (TypeError, ValueError):
        x_norm = z_norm = 0.0
    layout_extents = _layout_vector(layout, "extents")
    x = x_norm * max(layout_extents[0], 1.0)
    y = z_norm * max(layout_extents[1], 1.0)
    clearance = 0.35 + max(0.0, float(slot.get("clearance") or 0.0)) * 2.0
    return _authored_front_center(x, y, thickness_cm=0.75, clearance_cm=clearance, layout=layout)


def _module_slot_groups(context: ShapeAuthoringContext) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for slot in context.module_slots:
        if not isinstance(slot, dict):
            continue
        kind = _slug(slot.get("kind") or "generic")
        if kind not in _MODULE_FOOTPRINT_SOURCE_BY_KIND:
            kind = "generic"
        groups.setdefault(kind, []).append(dict(slot))
    return groups


def _module_slot_metadata(slots: Sequence[dict[str, Any]], default_kind: str) -> list[dict[str, Any]]:
    return [
        {
            "slot_id": str(slot.get("id") or ""),
            "slot_kind": str(slot.get("kind") or default_kind),
            "socket": str(slot.get("socket") or ""),
            "anchor": str(slot.get("anchor") or ""),
            "mount": str(slot.get("mount") or ""),
            "module_instance_id": str(slot.get("module_instance_id") or ""),
            "module_template": str(slot.get("module_template") or ""),
            "module_family": str(slot.get("module_family") or ""),
            "module_archetype": str(slot.get("module_archetype") or ""),
            "facing_degrees": float(slot.get("facing_degrees") or 0.0),
        }
        for slot in slots
    ]


def _module_slot_parameter_metadata(slots: Sequence[dict[str, Any]], default_kind: str) -> dict[str, Any]:
    return {
        "slot_ids": [str(slot.get("id") or "") for slot in slots],
        "slot_kinds": [str(slot.get("kind") or default_kind) for slot in slots],
        "module_templates": [str(slot.get("module_template") or "") for slot in slots],
        "module_families": [str(slot.get("module_family") or "") for slot in slots],
        "module_archetypes": [str(slot.get("module_archetype") or "") for slot in slots],
        "instance_roll_degrees": [float(slot.get("facing_degrees") or 0.0) for slot in slots],
        "instance_metadata": _module_slot_metadata(slots, default_kind),
    }


def _rotated_front_offset(x_cm: float, y_cm: float, facing_degrees: float) -> tuple[float, float]:
    radians = math.radians(float(facing_degrees))
    cos_value = math.cos(radians)
    sin_value = math.sin(radians)
    return (
        float(x_cm) * cos_value - float(y_cm) * sin_value,
        float(x_cm) * sin_value + float(y_cm) * cos_value,
    )


def _module_slot_component_center(
    slot: dict[str, Any],
    layout: dict[str, tuple[float, float, float] | float],
    *,
    offset_cm: tuple[float, float] = (0.0, 0.0),
    thickness_cm: float = 0.75,
    clearance_cm: float = 0.35,
) -> tuple[float, float, float]:
    position = slot.get("normalized_position")
    if not isinstance(position, (list, tuple)) or len(position) < 3:
        position = (0.0, 0.0, 0.0)
    try:
        x_norm = float(position[0])
        z_norm = float(position[2])
    except (TypeError, ValueError):
        x_norm = z_norm = 0.0
    layout_extents = _layout_vector(layout, "extents")
    local_x, local_y = _rotated_front_offset(
        float(offset_cm[0]),
        float(offset_cm[1]),
        float(slot.get("facing_degrees") or 0.0),
    )
    x = x_norm * max(layout_extents[0], 1.0) + local_x
    y = z_norm * max(layout_extents[1], 1.0) + local_y
    return _authored_front_center(x, y, thickness_cm=thickness_cm, clearance_cm=clearance_cm, layout=layout)


def _module_component_source(
    slot: dict[str, Any],
    component: dict[str, Any],
) -> dict[str, Any]:
    op_name = str(component.get("op") or "solid.box")
    parameters = dict(component.get("parameters") or {})
    parameters.setdefault("center", (0.0, 0.0, 0.0))
    return {
        "op": op_name,
        "target": f"{_slug(slot.get('id'))}_{_slug(component.get('role'))}_source",
        "parameters": parameters,
        "purpose": f"child_modules.{_slug(slot.get('kind'))}.{_slug(component.get('role'))}_source",
    }


def _module_assembly_components(kind: str, slot: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    template = _slug(slot.get("module_template") or "")
    archetype = _slug(slot.get("module_archetype") or "")
    if kind == "building":
        tower = "tower" in template or "tower" in archetype
        return (
            {
                "role": "main_mass",
                "op": "solid.rounded_box",
                "offset_cm": (0.0, 0.0),
                "parameters": {"width_cm": 9.5 if not tower else 5.2, "height_cm": 6.0 if not tower else 9.2, "depth_cm": 1.4, "radius_cm": 0.35},
            },
            {
                "role": "roof_cap",
                "op": "solid.extruded_profile",
                "offset_cm": (0.0, 4.2 if not tower else 6.0),
                "parameters": {
                    "profile_polygon": ((-5.4, -0.8), (0.0, 1.2), (5.4, -0.8)) if not tower else ((-3.0, -0.6), (0.0, 1.4), (3.0, -0.6)),
                    "extrude_height_cm": 1.0,
                    "axis": "z",
                },
            },
            {
                "role": "entry_socket",
                "op": "solid.panel",
                "offset_cm": (0.0, -3.6 if not tower else -4.8),
                "parameters": {"width_cm": 2.2, "height_cm": 1.5, "thickness_cm": 0.55, "axis": "z", "rounding_cm": 0.12},
            },
        )
    if kind == "road":
        return (
            {
                "role": "road_deck",
                "op": "solid.panel",
                "offset_cm": (0.0, 0.0),
                "parameters": {"width_cm": 15.5, "height_cm": 3.2, "thickness_cm": 0.45, "axis": "z", "rounding_cm": 0.12},
            },
            {
                "role": "left_curb",
                "op": "solid.rounded_box",
                "offset_cm": (0.0, 2.05),
                "parameters": {"width_cm": 15.8, "height_cm": 0.35, "depth_cm": 0.5, "radius_cm": 0.08},
            },
            {
                "role": "right_curb",
                "op": "solid.rounded_box",
                "offset_cm": (0.0, -2.05),
                "parameters": {"width_cm": 15.8, "height_cm": 0.35, "depth_cm": 0.5, "radius_cm": 0.08},
            },
            {
                "role": "lane_marker",
                "op": "solid.panel",
                "offset_cm": (0.0, 0.0),
                "parameters": {"width_cm": 10.0, "height_cm": 0.18, "thickness_cm": 0.58, "axis": "z"},
            },
        )
    if kind == "terrain":
        return (
            {
                "role": "ground_patch",
                "op": "solid.rounded_box",
                "offset_cm": (0.0, 0.0),
                "parameters": {"width_cm": 11.5, "height_cm": 7.2, "depth_cm": 0.55, "radius_cm": 1.1},
            },
            {
                "role": "mound",
                "op": "solid.sphere",
                "offset_cm": (-2.3, 1.2),
                "parameters": {"radius_cm": 2.0},
            },
            {
                "role": "rock_outcrop",
                "op": "solid.rounded_box",
                "offset_cm": (2.6, -1.4),
                "parameters": {"width_cm": 2.4, "height_cm": 1.5, "depth_cm": 1.0, "radius_cm": 0.45},
            },
        )
    if kind == "infrastructure":
        return (
            {
                "role": "junction_box",
                "op": "solid.rounded_box",
                "offset_cm": (0.0, 0.0),
                "parameters": {"width_cm": 4.4, "height_cm": 3.0, "depth_cm": 1.1, "radius_cm": 0.22},
            },
            {
                "role": "pipe_run",
                "op": "solid.cylinder",
                "offset_cm": (-3.8, 0.0),
                "parameters": {"radius_cm": 0.45, "height_cm": 7.5, "axis": "x", "sections": 16},
            },
            {
                "role": "service_rail",
                "op": "solid.structural_beam",
                "offset_cm": (3.5, 1.9),
                "parameters": {"length_cm": 5.8, "width_cm": 0.45, "height_cm": 0.65, "profile_shape": "i_beam", "axis": "x"},
            },
        )
    if kind == "vehicle":
        rotor_bonus = 1 if "drone" in template or "drone" in archetype else 0
        return (
            {
                "role": "chassis",
                "op": "solid.rounded_box",
                "offset_cm": (0.0, 0.0),
                "parameters": {"width_cm": 10.5, "height_cm": 3.2, "depth_cm": 1.15, "radius_cm": 0.45},
            },
            {
                "role": "cabin",
                "op": "solid.rounded_box",
                "offset_cm": (1.7, 1.7),
                "parameters": {"width_cm": 3.5, "height_cm": 2.4, "depth_cm": 1.05, "radius_cm": 0.35},
            },
            {
                "role": "front_axle",
                "op": "solid.cylinder",
                "offset_cm": (3.6, -2.0),
                "parameters": {"radius_cm": 0.95, "height_cm": 0.75, "axis": "z", "sections": 18},
            },
            {
                "role": "rear_axle",
                "op": "solid.cylinder",
                "offset_cm": (-3.6, -2.0),
                "parameters": {"radius_cm": 0.95, "height_cm": 0.75, "axis": "z", "sections": 18},
            },
            *(
                (
                    {
                        "role": "rotor_port",
                        "op": "solid.torus",
                        "offset_cm": (0.0, 3.0),
                        "parameters": {"major_radius_cm": 1.65, "minor_radius_cm": 0.16, "axis": "z", "sections": 24},
                    },
                )
                if rotor_bonus
                else ()
            ),
        )
    if kind == "boat":
        return (
            {
                "role": "hull",
                "op": "solid.extruded_profile",
                "offset_cm": (0.0, 0.0),
                "parameters": {
                    "profile_polygon": ((-7.5, -1.7), (5.8, -1.7), (8.0, 0.0), (5.8, 1.7), (-7.5, 1.7)),
                    "extrude_height_cm": 1.05,
                    "axis": "z",
                },
            },
            {
                "role": "deck",
                "op": "solid.panel",
                "offset_cm": (-0.7, 0.9),
                "parameters": {"width_cm": 9.5, "height_cm": 1.4, "thickness_cm": 0.55, "axis": "z", "rounding_cm": 0.18},
            },
            {
                "role": "cabin",
                "op": "solid.rounded_box",
                "offset_cm": (-2.6, 2.25),
                "parameters": {"width_cm": 2.8, "height_cm": 2.0, "depth_cm": 0.9, "radius_cm": 0.28},
            },
        )
    if kind == "machine":
        crane = "crane" in template or "crane" in archetype
        return (
            {
                "role": "base",
                "op": "solid.rounded_box",
                "offset_cm": (0.0, 0.0),
                "parameters": {"width_cm": 7.8, "height_cm": 3.6, "depth_cm": 1.2, "radius_cm": 0.3},
            },
            {
                "role": "column",
                "op": "solid.structural_beam",
                "offset_cm": (-2.0, 3.2),
                "parameters": {
                    "length_cm": 5.8,
                    "width_cm": 1.3,
                    "height_cm": 1.8,
                    "profile_shape": "i_beam",
                    "axis": "y",
                },
            },
            {
                "role": "gear_train",
                "op": "solid.gear",
                "offset_cm": (2.2, 2.5),
                "parameters": {
                    "teeth": 14 if not crane else 18,
                    "pitch_radius_cm": 1.65,
                    "thickness_cm": 0.8,
                    "bore_radius_cm": 0.35,
                    "axis": "z",
                },
            },
            {
                "role": "boom" if crane else "arm",
                "op": "solid.capsule",
                "offset_cm": (3.8, 4.1),
                "parameters": {"radius_cm": 0.35, "length_cm": 5.8 if crane else 4.4, "axis": "x", "sections": 14},
            },
        )
    if kind == "interior":
        return (
            {
                "role": "room_cell",
                "op": "solid.panel",
                "offset_cm": (0.0, 0.0),
                "parameters": {"width_cm": 10.5, "height_cm": 5.6, "thickness_cm": 0.85, "axis": "z", "rounding_cm": 0.28},
            },
            {
                "role": "partition_a",
                "op": "solid.panel",
                "offset_cm": (-2.6, 0.0),
                "parameters": {"width_cm": 0.55, "height_cm": 4.6, "thickness_cm": 1.05, "axis": "z"},
            },
            {
                "role": "ceiling_light",
                "op": "solid.cylinder",
                "offset_cm": (2.8, 2.0),
                "parameters": {"radius_cm": 0.85, "height_cm": 0.35, "axis": "z", "sections": 18},
            },
        )
    if kind == "furniture":
        return (
            {
                "role": "table_top",
                "op": "solid.panel",
                "offset_cm": (0.0, 0.8),
                "parameters": {"width_cm": 5.8, "height_cm": 2.6, "thickness_cm": 0.55, "axis": "z", "rounding_cm": 0.2},
            },
            {
                "role": "chair_a",
                "op": "solid.rounded_box",
                "offset_cm": (-2.7, -1.7),
                "parameters": {"width_cm": 1.4, "height_cm": 1.4, "depth_cm": 0.55, "radius_cm": 0.18},
            },
            {
                "role": "chair_b",
                "op": "solid.rounded_box",
                "offset_cm": (2.7, -1.7),
                "parameters": {"width_cm": 1.4, "height_cm": 1.4, "depth_cm": 0.55, "radius_cm": 0.18},
            },
        )
    if kind == "foliage":
        return (
            {
                "role": "trunk",
                "op": "solid.cylinder",
                "offset_cm": (0.0, -1.2),
                "parameters": {"radius_cm": 0.55, "height_cm": 3.2, "axis": "y", "sections": 14},
            },
            {
                "role": "canopy",
                "op": "solid.sphere",
                "offset_cm": (0.0, 1.8),
                "parameters": {"radius_cm": 2.8},
            },
            {
                "role": "understory",
                "op": "solid.sphere",
                "offset_cm": (2.2, 0.0),
                "parameters": {"radius_cm": 1.25},
            },
        )
    return (
        {
            "role": "module_body",
            "op": "solid.rounded_box",
            "offset_cm": (0.0, 0.0),
            "parameters": {"width_cm": 5.2, "height_cm": 3.2, "depth_cm": 0.7, "radius_cm": 0.22},
        },
        {
            "role": "socket_plate",
            "op": "solid.panel",
            "offset_cm": (0.0, 2.1),
            "parameters": {"width_cm": 4.2, "height_cm": 1.1, "thickness_cm": 0.55, "axis": "z", "rounding_cm": 0.12},
        },
    )


def _module_slot_assembly_ops(
    slot: dict[str, Any],
    *,
    layout: dict[str, tuple[float, float, float] | float],
) -> tuple[ShapeOp, ...]:
    kind = _slug(slot.get("kind") or "generic")
    if kind not in _MODULE_FOOTPRINT_SOURCE_BY_KIND:
        kind = "generic"
    slot_id = _slug(slot.get("id") or f"{kind}_slot")
    metadata = _module_slot_parameter_metadata((slot,), kind)
    ops: list[ShapeOp] = []
    for component in _module_assembly_components(kind, slot):
        role = _slug(component.get("role") or "component")
        target = f"authored_{slot_id}_{role}"
        offset = component.get("offset_cm")
        if not isinstance(offset, (list, tuple)) or len(offset) < 2:
            offset = (0.0, 0.0)
        center = _module_slot_component_center(
            slot,
            layout,
            offset_cm=(float(offset[0]), float(offset[1])),
            thickness_cm=float(component.get("thickness_cm") or 0.9),
            clearance_cm=0.45 + max(0.0, float(slot.get("clearance") or 0.0)),
        )
        ops.append(
            ShapeOp(
                op="op.distribute",
                target=target,
                parameters={
                    "pattern": "points",
                    "source": _module_component_source(slot, component),
                    "points": (center,),
                    "orientation_mode": "none",
                    "source_axis": "z",
                    "jitter_cm": 0.0,
                    **metadata,
                    "module_component_role": role,
                    "module_component_kind": kind,
                },
                purpose=f"authored_child_modules.{kind}.{slot_id}.{role}",
            )
        )
    return tuple(ops)


def _connection_layout_endpoint_order(context: ShapeAuthoringContext) -> tuple[str, ...]:
    point_ids = {str(point.get("endpoint") or "") for point in context.connection_layout_points}
    ordered: list[str] = []

    def append(endpoint: object) -> None:
        value = str(endpoint or "")
        if not value or value not in point_ids:
            return
        if ordered and ordered[-1] == value:
            return
        ordered.append(value)

    for edge in context.connection_route_edges:
        append(edge.get("source"))
        append(edge.get("target"))
    if len(ordered) >= 2:
        return tuple(ordered)

    return tuple(
        str(point.get("endpoint") or "")
        for point in sorted(
            context.connection_layout_points,
            key=lambda item: int(item.get("order") or 0),
        )
        if str(point.get("endpoint") or "")
    )


def _connection_layout_front_point(
    point: dict[str, Any],
    *,
    ordinal: int,
    layout: dict[str, tuple[float, float, float] | float],
    route_y: float,
) -> tuple[float, float, float]:
    position = point.get("normalized_position")
    if not isinstance(position, (list, tuple)) or len(position) < 3:
        position = (0.0, 0.0, 0.0)
    try:
        x_norm = float(position[0])
        z_norm = float(position[2])
    except (TypeError, ValueError):
        x_norm = z_norm = 0.0
    layout_extents = _layout_vector(layout, "extents")
    lane_width = min(14.0, max(6.0, layout_extents[0] * 0.18))
    x_lane = (-0.5 if ordinal % 2 == 0 else 0.5) * lane_width
    x = x_norm * max(layout_extents[0], 1.0) + x_lane
    y = route_y + z_norm * min(26.0, max(10.0, layout_extents[1] * 0.55))
    return _authored_front_center(x, y, thickness_cm=0.9, clearance_cm=0.7, layout=layout)


def _authored_connection_conduit_path(
    context: ShapeAuthoringContext,
    *,
    layout: dict[str, tuple[float, float, float] | float],
    route_y: float,
) -> tuple[tuple[tuple[float, float, float], ...] | None, dict[str, Any]]:
    if not context.connection_layout_points:
        return None, {}
    point_by_endpoint = {
        str(point.get("endpoint") or ""): dict(point)
        for point in context.connection_layout_points
        if str(point.get("endpoint") or "")
    }
    endpoint_order = tuple(
        endpoint for endpoint in _connection_layout_endpoint_order(context) if endpoint in point_by_endpoint
    )
    if len(endpoint_order) < 2:
        return None, {}
    path = tuple(
        _connection_layout_front_point(
            point_by_endpoint[endpoint],
            ordinal=index,
            layout=layout,
            route_y=route_y,
        )
        for index, endpoint in enumerate(endpoint_order)
    )
    return path, {
        "path_endpoint_ids": list(endpoint_order),
        "connection_route_edges": [dict(edge) for edge in context.connection_route_edges],
        "connection_layout_mode": context.connection_layout_mode,
        "connection_path_complexity": context.connection_path_complexity,
    }


def _authored_connection_endpoint_points(
    context: ShapeAuthoringContext,
    *,
    layout: dict[str, tuple[float, float, float] | float],
    route_y: float,
) -> tuple[tuple[tuple[float, float, float], ...], dict[str, Any]]:
    point_by_endpoint = {
        str(point.get("endpoint") or ""): dict(point)
        for point in context.connection_layout_points
        if str(point.get("endpoint") or "")
    }
    endpoint_order = tuple(
        endpoint for endpoint in _connection_layout_endpoint_order(context) if endpoint in point_by_endpoint
    )
    if not endpoint_order:
        return (), {}
    points = tuple(
        _connection_layout_front_point(
            point_by_endpoint[endpoint],
            ordinal=index,
            layout=layout,
            route_y=route_y,
        )
        for index, endpoint in enumerate(endpoint_order)
    )
    point_metadata = [dict(point_by_endpoint[endpoint]) for endpoint in endpoint_order]
    return points, {
        "connection_endpoint_ids": list(endpoint_order),
        "connection_point_metadata": point_metadata,
        "instance_metadata": point_metadata,
        "connection_route_edges": [dict(edge) for edge in context.connection_route_edges],
        "connection_layout_mode": context.connection_layout_mode,
        "connection_path_complexity": context.connection_path_complexity,
    }


def _connection_edge_relation(edge: dict[str, str]) -> str:
    return str(edge.get("relation") or "connects_to").strip().lower() or "connects_to"


def _connection_edge_geometry_kind(relation: str) -> str:
    if relation in _CONNECTION_ROUTE_RELATIONS:
        return "route_conduit"
    if relation in _CONNECTION_ATTACH_RELATIONS:
        return "attachment_strap"
    if relation in _CONNECTION_SUPPORT_RELATIONS:
        return "support_strut"
    return "route_conduit"


def _connection_edge_target(edge_index: int, geometry_kind: str) -> str:
    return f"{_connection_edge_target_prefix(geometry_kind)}{edge_index:02d}"


def _connection_edge_purpose(geometry_kind: str) -> str:
    if geometry_kind == "attachment_strap":
        return "authored_connections.attachment_edge_strap"
    if geometry_kind == "support_strut":
        return "authored_connections.support_edge_strut"
    return "authored_connections.route_edge_conduit"


def _connection_edge_profile(geometry_kind: str) -> str:
    if geometry_kind == "attachment_strap":
        return "flat_rectangular_strap"
    if geometry_kind == "support_strut":
        return "triangular_structural_strut"
    return "round_conduit"


def _connection_edge_role(geometry_kind: str) -> str:
    if geometry_kind == "attachment_strap":
        return "attachment"
    if geometry_kind == "support_strut":
        return "support"
    return "route"


def _connection_edge_target_prefix(geometry_kind: str) -> str:
    if geometry_kind == "attachment_strap":
        return "authored_connection_attachment_edge_"
    if geometry_kind == "support_strut":
        return "authored_connection_support_edge_"
    return "authored_connection_route_edge_"


def _is_authored_connection_edge_target(target: str) -> bool:
    return target.startswith(
        (
            "authored_connection_route_edge_",
            "authored_connection_attachment_edge_",
            "authored_connection_support_edge_",
        )
    )


def _connection_edge_cross_section(geometry_kind: str) -> tuple[tuple[float, float], ...] | None:
    if geometry_kind == "attachment_strap":
        return ((-1.0, -0.22), (1.0, -0.22), (1.0, 0.22), (-1.0, 0.22))
    if geometry_kind == "support_strut":
        return ((0.0, 1.0), (-0.82, -0.5), (0.82, -0.5))
    return None


def _connection_edge_radius(geometry_kind: str, edge_index: int) -> float:
    if geometry_kind == "attachment_strap":
        return 0.42 + min(0.12, (edge_index % 3) * 0.03)
    if geometry_kind == "support_strut":
        return 0.55 + min(0.15, (edge_index % 2) * 0.05)
    return 0.32


def _authored_connection_route_edge_ops(
    context: ShapeAuthoringContext,
    *,
    layout: dict[str, tuple[float, float, float] | float],
    route_y: float,
) -> tuple[ShapeOp, ...]:
    if not context.connection_route_edges or not context.connection_layout_points:
        return ()
    point_by_endpoint = {
        str(point.get("endpoint") or ""): dict(point)
        for point in context.connection_layout_points
        if str(point.get("endpoint") or "")
    }
    endpoint_order = tuple(
        endpoint for endpoint in _connection_layout_endpoint_order(context) if endpoint in point_by_endpoint
    )
    endpoint_ordinals = {endpoint: index for index, endpoint in enumerate(endpoint_order)}
    ops: list[ShapeOp] = []
    for edge_index, edge in enumerate(context.connection_route_edges):
        source_endpoint = str(edge.get("source") or "")
        target_endpoint = str(edge.get("target") or "")
        if source_endpoint not in point_by_endpoint or target_endpoint not in point_by_endpoint:
            continue
        source_point = _connection_layout_front_point(
            point_by_endpoint[source_endpoint],
            ordinal=endpoint_ordinals.get(source_endpoint, edge_index),
            layout=layout,
            route_y=route_y,
        )
        target_point = _connection_layout_front_point(
            point_by_endpoint[target_endpoint],
            ordinal=endpoint_ordinals.get(target_endpoint, edge_index + 1),
            layout=layout,
            route_y=route_y,
        )
        if all(abs(float(source_point[axis]) - float(target_point[axis])) < 1e-6 for axis in range(3)):
            continue
        relation = _connection_edge_relation(edge)
        geometry_kind = _connection_edge_geometry_kind(relation)
        bend_offset = ((edge_index % 3) - 1) * 1.35
        if geometry_kind == "attachment_strap":
            bend_offset *= 0.35
        elif geometry_kind == "support_strut":
            bend_offset += 1.6
        mid_y = (float(source_point[1]) + float(target_point[1])) * 0.5 + bend_offset
        path = (
            source_point,
            (float(source_point[0]), mid_y, float(source_point[2])),
            (float(target_point[0]), mid_y, float(target_point[2])),
            target_point,
        )
        metadata = {
            "path_endpoint_ids": [source_endpoint, target_endpoint],
            "connection_route_edge": dict(edge),
            "connection_route_edge_index": edge_index,
            "connection_edge_relation": relation,
            "connection_edge_geometry": geometry_kind,
            "connection_edge_profile": _connection_edge_profile(geometry_kind),
            "connection_edge_role": _connection_edge_role(geometry_kind),
            "connection_edge_target_prefix": _connection_edge_target_prefix(geometry_kind),
            "route_edge_source": source_endpoint,
            "route_edge_target": target_endpoint,
            "connection_route_edges": [dict(edge)],
            "connection_layout_mode": context.connection_layout_mode,
            "connection_path_complexity": context.connection_path_complexity,
        }
        cross_section = _connection_edge_cross_section(geometry_kind)
        radius_cm = _connection_edge_radius(geometry_kind, edge_index)
        geometry_parameters: dict[str, Any] = {
            "radius_cm": radius_cm,
            "path": path,
            "center": (
                (float(source_point[0]) + float(target_point[0])) * 0.5,
                mid_y,
                (float(source_point[2]) + float(target_point[2])) * 0.5,
            ),
            "connection_edge_radius_cm": radius_cm,
            **metadata,
        }
        if cross_section is not None:
            geometry_parameters["cross_section"] = cross_section
            geometry_parameters["connection_edge_cross_section"] = _connection_edge_profile(geometry_kind)
        ops.append(
            ShapeOp(
                op="sop.polywire",
                target=_connection_edge_target(edge_index, geometry_kind),
                parameters=geometry_parameters,
                purpose=_connection_edge_purpose(geometry_kind),
            )
            )
    return tuple(ops)


_MIRRORABLE_AUTHORING_OPS = frozenset(
    {
        "op.trim_band",
        "op.panel_frame",
        "op.fastener_grid",
        "op.vent_slats",
        "op.corner_guard_set",
        "op.bracket",
        "op.mount_plate",
        "op.socket",
        "op.weld_seam",
        "op.chip_edges",
        "op.scratch_mask",
        "op.dent_mask",
        "op.grime_mask",
        "sop.polywire",
        "solid.hinge",
    }
)


def _authoring_mirror_source_target(
    program: ShapeProgram,
    injected_ops: tuple[ShapeOp, ...],
) -> str:
    for op in reversed(injected_ops):
        target = str(op.target or "").strip()
        if target and op.op in _MIRRORABLE_AUTHORING_OPS:
            return target
    for op in reversed(program.ops):
        target = str(op.target or "").strip()
        if target and op.op in _MIRRORABLE_AUTHORING_OPS:
            return target
    return ""


def _mirror_pair_seed_adjusted_op(
    op: ShapeOp,
    *,
    axis: str,
    layout_extents: tuple[float, float, float],
) -> ShapeOp:
    axis_index = {"x": 0, "y": 1, "z": 2}.get(axis, 0)
    lateral_offset = -max(3.0, min(18.0, float(layout_extents[axis_index]) * 0.24))
    parameters = dict(op.parameters)
    surface_offset = parameters.get("surface_offset_cm")
    if isinstance(surface_offset, (list, tuple)) and len(surface_offset) >= 2:
        try:
            current_x = float(surface_offset[0])
            current_y = float(surface_offset[1])
        except (TypeError, ValueError):
            current_x = current_y = 0.0
        if abs(current_x) <= 1e-6:
            parameters["surface_offset_cm"] = (lateral_offset, current_y)
            parameters["mirror_pair_seed_offset_axis"] = axis
            parameters["mirror_pair_seed_offset_cm"] = lateral_offset
            return ShapeOp(op=op.op, target=op.target, parameters=parameters, purpose=op.purpose)
        return op
    center = parameters.get("center")
    if isinstance(center, (list, tuple)) and len(center) == 3:
        try:
            values = [float(item) for item in center]
        except (TypeError, ValueError):
            return op
        if abs(values[axis_index]) <= 1e-6:
            values[axis_index] = lateral_offset
            parameters["center"] = tuple(values)
            parameters["mirror_pair_seed_offset_axis"] = axis
            parameters["mirror_pair_seed_offset_cm"] = lateral_offset
            return ShapeOp(op=op.op, target=op.target, parameters=parameters, purpose=op.purpose)
    return op


def _authoring_injected_ops(
    program: ShapeProgram,
    context: ShapeAuthoringContext,
) -> tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]:
    request_tokens = _authoring_request_tokens(context)
    explicit_request_tokens = _authoring_explicit_request_tokens(context)
    if not request_tokens:
        return (), ()

    layout = _authoring_layout_for_program(program)
    layout_center = _layout_vector(layout, "center")
    layout_extents = _layout_vector(layout, "extents")
    primary_body_target = _primary_body_context_key_for_program(program)
    injected: list[ShapeOp] = []
    reports: list[dict[str, Any]] = []

    material_tokens = request_tokens & {
        "material",
        "materials",
        "finish",
        "finishes",
        "palette",
        "base",
        "biome",
        "zone",
        "zones",
    }
    material_op_tokens = {"material", "materials", "finish", "finishes", "palette", "base", "biome"}
    material_zone_tokens = {"zone", "zones", "surface", "surfaces", "patch", "patches", "band", "bands"}
    program_has_material_zone = any(
        (_shape_op_tokens(op) & material_op_tokens) and (_shape_op_tokens(op) & material_zone_tokens)
        for op in program.ops
    )
    if (
        material_tokens
        and (request_tokens & material_op_tokens)
        and (request_tokens & material_zone_tokens)
        and not program_has_material_zone
    ):
        op = ShapeOp(
            op="sop.polyextrude",
            target="authored_material_zone_patch",
            parameters={
                "profile_polygon": ((-18.0, -5.5), (18.0, -5.5), (18.0, 5.5), (-18.0, 5.5)),
                "extrude_height_cm": 0.22,
                "axis": "z",
                "center": _authored_front_center(
                    0.0,
                    -14.0,
                    thickness_cm=0.22,
                    clearance_cm=0.08,
                    layout=layout,
                ),
            },
            purpose="authored_surface_materials.material_zone_patch",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="surface_material_authoring_requested_visible_material_zone",
                matched_tokens=material_tokens,
            )
        )

    decal_tokens = request_tokens & _AUTHORING_DECAL_TOKENS
    decal_zone_tokens = {"zone", "zones", "surface", "surfaces", "plate", "panel", "marker", "marking"}
    program_has_decal_zone = any(
        (_shape_op_tokens(op) & _AUTHORING_DECAL_TOKENS) and (_shape_op_tokens(op) & decal_zone_tokens)
        for op in program.ops
    )
    if (
        decal_tokens
        and (request_tokens & decal_zone_tokens)
        and not program_has_decal_zone
    ):
        op = ShapeOp(
            op="sop.polyextrude",
            target="authored_decal_zone_marker",
            parameters={
                "profile_polygon": ((-9.0, -3.0), (9.0, -3.0), (9.0, 3.0), (-9.0, 3.0)),
                "extrude_height_cm": 0.16,
                "axis": "z",
                "center": _authored_front_center(
                    20.0,
                    12.0,
                    thickness_cm=0.16,
                    clearance_cm=0.10,
                    layout=layout,
                ),
            },
            purpose="authored_surface_patterns.decal_zone_marker",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="surface_pattern_authoring_requested_visible_decal_zone",
                matched_tokens=decal_tokens,
            )
        )

    trim_tokens = request_tokens & _AUTHORING_TRIM_TOKENS
    if trim_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.trim_band"}),
        _AUTHORING_TRIM_TOKENS,
    ):
        op = ShapeOp(
            op="op.trim_band",
            target="authored_trim_band",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "width_cm": 2.4,
                "thickness_cm": 0.9,
                "axis": "z",
                "length_axis": "x",
                "width_axis": "y",
                "normal_sign": 1.0,
                "surface_offset_cm": (
                    _layout_offset(layout, 0.0, -12.0)[0] - layout_center[0],
                    _layout_offset(layout, 0.0, -12.0)[1] - layout_center[1],
                ),
                "bevel_width_cm": 0.14,
                "bevel_segments": 2,
            },
            purpose="authored_features.trim_band",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_trim",
                matched_tokens=trim_tokens,
            )
        )

    fastener_tokens = request_tokens & _AUTHORING_FASTENER_TOKENS
    if fastener_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.fastener_grid"}),
        _AUTHORING_FASTENER_TOKENS,
    ):
        op = ShapeOp(
            op="op.fastener_grid",
            target="authored_fastener_grid",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "rows": 2,
                "columns": 4,
                "spacing_cm": 8.0,
                "axis": "z",
                "row_axis": "y",
                "column_axis": "x",
                "normal_sign": 1.0,
                "surface_offset_cm": (
                    _layout_offset(layout, 0.0, 11.0)[0] - layout_center[0],
                    _layout_offset(layout, 0.0, 11.0)[1] - layout_center[1],
                ),
                "radius_cm": 0.75,
                "height_cm": 0.45,
                "head_style": "domed",
                "include_washer": True,
                "bevel_width_cm": 0.08,
                "bevel_segments": 2,
            },
            purpose="authored_features.fastener_grid",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_fasteners",
                matched_tokens=fastener_tokens,
            )
        )

    vent_tokens = request_tokens & _AUTHORING_VENT_TOKENS
    if vent_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.vent_slats"}),
        _AUTHORING_VENT_TOKENS,
    ):
        op = ShapeOp(
            op="op.vent_slats",
            target="authored_vent_slats",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "count": 5,
                "spacing_cm": 5.0,
                "length_cm": 32.0,
                "height_cm": 2.0,
                "thickness_cm": 0.8,
                "axis": "z",
                "row_axis": "y",
                "normal_sign": 1.0,
                "surface_offset_cm": (
                    _layout_offset(layout, 0.0, 3.0)[0] - layout_center[0],
                    _layout_offset(layout, 0.0, 3.0)[1] - layout_center[1],
                ),
                "shape": "rounded_slot",
                "bevel_width_cm": 0.10,
                "bevel_segments": 2,
            },
            purpose="authored_surface_patterns.vent_slats",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_vents",
                matched_tokens=vent_tokens,
            )
        )

    panel_tokens = request_tokens & _AUTHORING_PANEL_TOKENS
    if panel_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.panel_frame"}),
        frozenset(),
    ):
        op = ShapeOp(
            op="op.panel_frame",
            target="authored_panel_frame",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "width_cm": 42.0,
                "height_cm": 24.0,
                "border_width_cm": 2.2,
                "thickness_cm": 0.9,
                "width_axis": "x",
                "height_axis": "y",
                "normal_axis": "z",
                "normal_sign": 1.0,
                "bevel_width_cm": 0.12,
                "bevel_segments": 2,
            },
            purpose="authored_features.panel_frame",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_panel_frame",
                matched_tokens=panel_tokens,
            )
        )

    inset_tokens = explicit_request_tokens & _AUTHORING_INSET_TOKENS
    if inset_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.inset"}),
        _AUTHORING_INSET_TOKENS,
    ):
        op = ShapeOp(
            op="op.inset",
            target="authored_panel_recess",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "depth_cm": 1.15,
                "width_cm": 32.0,
                "height_cm": 17.0,
                "normal_axis": "z",
                "side": "positive",
                "width_axis": "x",
                "bevel_width_cm": 0.16,
                "bevel_segments": 2,
            },
            purpose="authored_surface_patterns.recessed_panel",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_recessed_panel",
                matched_tokens=inset_tokens,
            )
        )

    panel_line_tokens = explicit_request_tokens & _AUTHORING_PANEL_LINE_TOKENS
    if panel_line_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.cut_panel_line"}),
        _AUTHORING_PANEL_LINE_TOKENS,
    ):
        for suffix, line_axis, length in (
            ("horizontal", "x", 36.0),
            ("vertical", "y", 20.0),
        ):
            op = ShapeOp(
                op="op.cut_panel_line",
                target=f"authored_panel_groove_{suffix}",
                parameters={
                    "source": primary_body_target,
                    "target_face": "front",
                    "width_cm": 0.42,
                    "length_cm": length,
                    "depth_cm": 1.0,
                    "line_axis": line_axis,
                    "normal_axis": "z",
                    "normal_sign": 1.0,
                    "blend_mode": "subtract",
                    "bevel_width_cm": 0.08,
                    "bevel_segments": 2,
                },
                purpose="authored_surface_patterns.panel_groove",
            )
            injected.append(op)
            reports.append(
                _authoring_injection_report(
                    op,
                    reason="feature_or_surface_authoring_requested_panel_groove",
                    matched_tokens=panel_line_tokens,
                )
            )

    integration_tokens = _context_token_set(context.integration_rules)
    integration_break_tokens = integration_tokens & _AUTHORING_INTEGRATION_BREAK_TOKENS
    if (
        "preserve" in integration_tokens
        and integration_break_tokens
        and not _program_has_authoring_feature(
            program,
            frozenset({"op.cut_panel_line"}),
            integration_break_tokens | frozenset({"lid", "door", "threshold"}),
        )
    ):
        y_offset = 0.0
        if "lid" in integration_tokens:
            y_offset = layout_extents[1] * 0.18
        elif "threshold" in integration_tokens:
            y_offset = -layout_extents[1] * 0.42
        seam_group = next(
            (
                str(rule)
                for rule in context.integration_rules
                if _context_token_set((str(rule),)) & integration_break_tokens
            ),
            "preserve_break",
        )
        op = ShapeOp(
            op="op.cut_panel_line",
            target="authored_integration_preserve_break",
            parameters={
                "width_cm": 0.48,
                "length_cm": max(12.0, min(layout_extents[0] * 0.82, 72.0)),
                "depth_cm": max(0.8, min(layout_extents[2] * 0.10, 2.0)),
                "center": _authored_front_center(
                    0.0,
                    y_offset,
                    thickness_cm=0.0,
                    clearance_cm=0.0,
                    layout=layout,
                ),
                "line_axis": "x",
                "normal_axis": "z",
                "blend_mode": "subtract",
                "seam_group": seam_group,
                "bevel_width_cm": 0.06,
                "bevel_segments": 1,
            },
            purpose=f"authored_integration_rules.{_slug(seam_group)}",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="geometry_integration_rule_requested_preserved_break",
                matched_tokens=integration_break_tokens,
            )
        )

    guard_tokens = request_tokens & _AUTHORING_GUARD_TOKENS
    if guard_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.corner_guard_set"}),
        _AUTHORING_GUARD_TOKENS,
    ):
        op = ShapeOp(
            op="op.corner_guard_set",
            target="authored_corner_guards",
            parameters={
                "width_cm": layout_extents[0],
                "height_cm": layout_extents[1],
                "depth_cm": layout_extents[2],
                "size_cm": 8.0,
                "center": layout_center,
                "thickness_cm": 1.0,
                "rounding_cm": 0.18,
                "bevel_width_cm": 0.10,
                "bevel_segments": 2,
            },
            purpose="authored_features.corner_guards",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_corner_guards",
                matched_tokens=guard_tokens,
            )
        )

    bracket_tokens = request_tokens & _AUTHORING_BRACKET_TOKENS
    if bracket_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.bracket"}),
        _AUTHORING_BRACKET_DUPLICATE_TOKENS,
    ):
        bracket_count = max(
            2,
            min(
                6,
                int(context.support_connection_count or 0)
                + int(context.child_module_count or 0)
                + int(context.nested_asset_count or 0),
            ),
        )
        op = ShapeOp(
            op="op.bracket",
            target="authored_support_bracket",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "clearance_cm": 4.0,
                "mount_type": "surface",
                "width_cm": 12.0 + max(0, bracket_count - 2) * 1.2,
                "height_cm": 10.0 + max(0, bracket_count - 2) * 0.8,
                "depth_cm": 8.0 + max(0, bracket_count - 2) * 0.6,
                "thickness_cm": 1.0,
                "normal_axis": "z",
                "width_axis": "x",
                "height_axis": "y",
                "normal_sign": 1.0,
                "surface_offset_cm": (
                    _layout_offset(layout, -20.0, -8.0)[0] - layout_center[0],
                    _layout_offset(layout, -20.0, -8.0)[1] - layout_center[1],
                ),
                "include_gussets": True,
                "gusset_count": bracket_count,
                "rounding_cm": 0.12,
            },
            purpose="authored_features.support_bracket",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_bracket",
                matched_tokens=bracket_tokens,
            )
        )

    mount_tokens = request_tokens & _AUTHORING_MOUNT_DUPLICATE_TOKENS
    if mount_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.mount_plate"}),
        _AUTHORING_MOUNT_DUPLICATE_TOKENS,
    ):
        mount_count = max(
            1,
            min(
                6,
                len(context.anchor_ids)
                + int(context.attach_connection_count or 0)
                + int(context.child_module_count or 0),
            ),
        )
        op = ShapeOp(
            op="op.mount_plate",
            target="authored_mount_plate",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "width_cm": 18.0 + max(0, mount_count - 1) * 1.6,
                "height_cm": 12.0 + max(0, mount_count - 1) * 0.9,
                "thickness_cm": 0.9,
                "axis": "z",
                "column_axis": "x",
                "row_axis": "y",
                "normal_sign": 1.0,
                "surface_offset_cm": (
                    _layout_offset(layout, 18.0, 8.0)[0] - layout_center[0],
                    _layout_offset(layout, 18.0, 8.0)[1] - layout_center[1],
                ),
                "hole_rows": 2,
                "hole_columns": max(2, min(4, mount_count)),
                "hole_radius_cm": 0.75,
                "bevel_width_cm": 0.12,
                "bevel_segments": 2,
            },
            purpose="authored_features.mount_plate",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_mount_plate",
                matched_tokens=mount_tokens,
            )
        )

    module_slot_groups = _module_slot_groups(context)
    all_module_slots = tuple(slot for slots in module_slot_groups.values() for slot in slots)
    module_slot_count = max(context.module_slot_count, context.nested_asset_count)
    if module_slot_count > 1 and not any(op.target == "authored_child_module_anchor_grid" for op in program.ops):
        source = {
            "op": "solid.panel",
            "target": "child_module_anchor_pad",
            "parameters": {
                "width_cm": 5.5,
                "height_cm": 3.2,
                "thickness_cm": 0.55,
                "center": (0.0, 0.0, 0.0),
            },
            "purpose": "child_modules.anchor_pad_source",
        }
        if all_module_slots:
            parameters: dict[str, Any] = {
                "pattern": "points",
                "source": source,
                "points": tuple(_module_slot_center(slot, layout) for slot in all_module_slots),
                "orientation_mode": "none",
                "source_axis": "z",
                "jitter_cm": 0.0,
                **_module_slot_parameter_metadata(all_module_slots, "module"),
            }
        else:
            columns = min(6, max(2, module_slot_count))
            rows = max(1, math.ceil(module_slot_count / columns))
            parameters = {
                "pattern": "surface_grid",
                "source": source,
                "target": primary_body_target,
                "rows": rows,
                "columns": columns,
                "row_axis": "y",
                "column_axis": "x",
                "target_face": "front",
                "source_axis": "z",
                "margin_cm": max(2.5, min(layout_extents[0], layout_extents[1]) * 0.12),
                "seat_depth_cm": 0.04,
            }
        op = ShapeOp(
            op="op.distribute",
            target="authored_child_module_anchor_grid",
            parameters=parameters,
            purpose="authored_child_modules.module_slot_anchor_grid",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="child_module_slots_requested_anchor_grid",
                matched_tokens=frozenset({"module", "anchor", "mount"}),
            )
        )

    for kind, slots in sorted(module_slot_groups.items()):
        if not slots or any(op.target == f"authored_{kind}_module_footprints" for op in program.ops):
            continue
        points = tuple(_module_slot_center(slot, layout) for slot in slots)
        op = ShapeOp(
            op="op.distribute",
            target=f"authored_{kind}_module_footprints",
            parameters={
                "pattern": "points",
                "source": _module_footprint_source(kind),
                "points": points,
                "orientation_mode": "none",
                "source_axis": "z",
                "jitter_cm": 0.0,
                **_module_slot_parameter_metadata(slots, kind),
            },
            purpose=f"authored_child_modules.{kind}_module_footprints",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="child_module_slots_requested_kind_footprints",
                matched_tokens=frozenset({"module", "footprint", kind}),
            )
        )

    existing_targets = {op.target for op in program.ops}
    injected_targets = {op.target for op in injected}
    for slot in all_module_slots:
        slot_kind = _slug(slot.get("kind") or "generic")
        if slot_kind not in _MODULE_FOOTPRINT_SOURCE_BY_KIND:
            slot_kind = "generic"
        for op in _module_slot_assembly_ops(slot, layout=layout):
            if op.target in existing_targets or op.target in injected_targets:
                continue
            injected.append(op)
            injected_targets.add(op.target)
            reports.append(
                _authoring_injection_report(
                    op,
                    reason="child_module_slots_requested_visible_module_assembly",
                    matched_tokens=frozenset({"module", "assembly", slot_kind}),
                )
            )

    latch_tokens = request_tokens & _AUTHORING_LATCH_TOKENS
    if latch_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.mount_plate"}),
        _AUTHORING_LATCH_TOKENS,
    ):
        op = ShapeOp(
            op="op.mount_plate",
            target="authored_latch_plate",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "width_cm": 10.0,
                "height_cm": 6.0,
                "thickness_cm": 0.8,
                "axis": "z",
                "column_axis": "x",
                "row_axis": "y",
                "normal_sign": 1.0,
                "surface_offset_cm": (
                    _layout_offset(layout, 18.0, -8.0)[0] - layout_center[0],
                    _layout_offset(layout, 18.0, -8.0)[1] - layout_center[1],
                ),
                "hole_count": 2,
                "hole_radius_cm": 0.45,
                "bevel_width_cm": 0.10,
                "bevel_segments": 2,
            },
            purpose="authored_features.latch_plate",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_latch_plate",
                matched_tokens=latch_tokens,
            )
        )

    weld_tokens = request_tokens & _AUTHORING_WELD_TOKENS
    if weld_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.weld_seam"}),
        _AUTHORING_WELD_TOKENS,
    ):
        op = ShapeOp(
            op="op.weld_seam",
            target="authored_weld_seam",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "width_cm": 0.9,
                "length_cm": 34.0,
                "axis": "x",
                "normal_axis": "z",
                "normal_sign": 1.0,
                "surface_offset_cm": (
                    _layout_offset(layout, 0.0, 15.0)[0] - layout_center[0],
                    _layout_offset(layout, 0.0, 15.0)[1] - layout_center[1],
                ),
                "bevel_width_cm": 0.08,
                "bevel_segments": 2,
            },
            purpose="authored_surface_patterns.weld_seam",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_weld_seam",
                matched_tokens=weld_tokens,
            )
        )

    grime_tokens = request_tokens & _AUTHORING_GRIME_TOKENS
    if grime_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.grime_mask"}),
        _AUTHORING_GRIME_TOKENS,
    ):
        op = ShapeOp(
            op="op.grime_mask",
            target="authored_grime_mask",
            parameters={
                "source": primary_body_target,
                "amount": 0.22,
                "count": 4,
                "normal_axis": "z",
                "side": "positive",
                "line_axis": "x",
                "row_axis": "y",
                "spacing_cm": 7.0,
            },
            purpose="authored_surface_patterns.grime_mask",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_grime",
                matched_tokens=grime_tokens,
            )
        )

    wear_tokens = request_tokens & _AUTHORING_WEAR_TOKENS
    if wear_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.chip_edges", "op.scratch_mask", "op.dent_mask"}),
        _AUTHORING_WEAR_TOKENS,
    ):
        op = ShapeOp(
            op="op.chip_edges",
            target="authored_edge_wear_chips",
            parameters={
                "source": primary_body_target,
                "amount": 0.24,
                "count": 3,
                "radius_cm": 0.55,
            },
            purpose="authored_surface_patterns.edge_wear_chips",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_surface_authoring_requested_edge_wear",
                matched_tokens=wear_tokens,
            )
        )

    hinge_tokens = request_tokens & _AUTHORING_HINGE_TOKENS
    if hinge_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"solid.hinge"}),
        frozenset(),
    ):
        op = ShapeOp(
            op="solid.hinge",
            target="authored_hinge_mount",
            parameters={
                "length_cm": max(10.0, min(layout_extents[1] * 0.45, 28.0)),
                "leaf_width_cm": max(2.4, min(layout_extents[0] * 0.12, 6.0)),
                "barrel_radius_cm": max(0.45, min(layout_extents[2] * 0.08, 1.4)),
                "center": _authored_front_center(-20.0, 0.0, thickness_cm=1.2, clearance_cm=0.9, layout=layout),
                "hinge_axis": "y",
                "leaf_axis": "x",
                "knuckle_count": 5,
                "screw_count_per_leaf": 2,
                "leaf_bevel_width_cm": 0.06,
                "leaf_bevel_segments": 1,
            },
            purpose="authored_features.hinge_mount_plate",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="construction_graph_requested_visible_hinge_mount",
                matched_tokens=hinge_tokens,
            )
        )

    handle_tokens = request_tokens & _AUTHORING_HANDLE_TOKENS
    if handle_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"solid.handle"}),
        _AUTHORING_HANDLE_TOKENS,
    ):
        op = ShapeOp(
            op="sop.polywire",
            target="authored_pull_handle",
            parameters={
                "radius_cm": 0.75,
                "path": (
                    _authored_front_center(-8.0, -3.0, thickness_cm=1.5, clearance_cm=1.0, layout=layout),
                    _authored_front_center(-8.0, -10.0, thickness_cm=1.5, clearance_cm=1.0, layout=layout),
                    _authored_front_center(8.0, -10.0, thickness_cm=1.5, clearance_cm=1.0, layout=layout),
                    _authored_front_center(8.0, -3.0, thickness_cm=1.5, clearance_cm=1.0, layout=layout),
                ),
                "center": _authored_front_center(0.0, -7.0, thickness_cm=1.5, clearance_cm=1.0, layout=layout),
            },
            purpose="authored_features.pull_handle",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_style_authoring_requested_handle",
                matched_tokens=handle_tokens,
            )
        )

    conduit_tokens = request_tokens & _AUTHORING_CONDUIT_TOKENS
    if conduit_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"solid.tube", "solid.curved_tube"}),
        _AUTHORING_CONDUIT_TOKENS,
    ):
        route_span = max(0, min(6, int(context.route_connection_count or 0) + int(context.connection_segment_count or 0)))
        route_y = 13.0 + min(4.0, route_span * 0.4)
        conduit_path, conduit_metadata = _authored_connection_conduit_path(
            context,
            layout=layout,
            route_y=route_y,
        )
        if conduit_path is None:
            conduit_path = (
                _authored_front_center(-22.0, route_y, thickness_cm=0.9, clearance_cm=0.7, layout=layout),
                _authored_front_center(-8.0, route_y + 3.0, thickness_cm=0.9, clearance_cm=0.7, layout=layout),
                _authored_front_center(7.0, route_y + 1.0, thickness_cm=0.9, clearance_cm=0.7, layout=layout),
                _authored_front_center(22.0, route_y + 3.0, thickness_cm=0.9, clearance_cm=0.7, layout=layout),
            )
        op = ShapeOp(
            op="sop.polywire",
            target="authored_conduit_run",
            parameters={
                "radius_cm": 0.45 + min(0.25, route_span * 0.025),
                "path": conduit_path,
                "center": _authored_front_center(0.0, route_y + 2.0, thickness_cm=0.9, clearance_cm=0.7, layout=layout),
                **conduit_metadata,
            },
            purpose="authored_surface_patterns.conduit_run",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_style_authoring_requested_conduit",
                matched_tokens=conduit_tokens,
            )
        )

    if context.connection_route_edges:
        existing_route_edge_targets = {
            str(op.target or "")
            for op in program.ops
            if _is_authored_connection_edge_target(str(op.target or ""))
        }
        for op in _authored_connection_route_edge_ops(
            context,
            layout=layout,
            route_y=14.5 + min(4.0, max(1, len(context.connection_route_edges)) * 0.35),
        ):
            if str(op.target or "") in existing_route_edge_targets:
                continue
            injected.append(op)
            existing_route_edge_targets.add(str(op.target or ""))
            reports.append(
                _authoring_injection_report(
                    op,
                    reason="connection_route_edges_requested_relation_aware_visible_geometry",
                    matched_tokens=frozenset({"connection", "route", "edge", "conduit", "strap", "support"}),
                )
            )

    if (
        context.connection_layout_points
        and not any(op.target == "authored_connection_endpoint_ports" for op in program.ops)
    ):
        endpoint_route_span = max(1, min(8, len(context.connection_layout_points)))
        endpoint_route_y = 13.0 + min(4.0, endpoint_route_span * 0.35)
        endpoint_points, endpoint_metadata = _authored_connection_endpoint_points(
            context,
            layout=layout,
            route_y=endpoint_route_y,
        )
        if endpoint_points:
            op = ShapeOp(
                op="op.distribute",
                target="authored_connection_endpoint_ports",
                parameters={
                    "pattern": "points",
                    "source": {
                        "op": "solid.cylinder",
                        "target": "connection_endpoint_port_source",
                        "parameters": {
                            "radius_cm": 1.35,
                            "height_cm": 0.7,
                            "axis": "z",
                            "sections": 18,
                            "center": (0.0, 0.0, 0.0),
                        },
                        "purpose": "connections.endpoint_port_source",
                    },
                    "points": endpoint_points,
                    "orientation_mode": "none",
                    "source_axis": "z",
                    "jitter_cm": 0.0,
                    **endpoint_metadata,
                },
                purpose="authored_connections.endpoint_ports",
            )
            injected.append(op)
            reports.append(
                _authoring_injection_report(
                    op,
                    reason="connection_layout_points_requested_visible_endpoint_ports",
                    matched_tokens=frozenset({"connection", "endpoint", "socket", "port"}),
                )
            )

    socket_tokens = request_tokens & _AUTHORING_SOCKET_TOKENS
    if socket_tokens and not _program_has_authoring_feature(
        program,
        frozenset({"op.socket", "op.rounded_slot", "op.countersunk_hole"}),
        _AUTHORING_SOCKET_TOKENS,
    ):
        socket_count = max(
            1,
            min(
                6,
                len(context.socket_ids)
                + int(context.attach_connection_count or 0)
                + int(context.route_connection_count or 0)
                + int(context.external_connection_count or 0),
            ),
        )
        op = ShapeOp(
            op="op.socket",
            target="authored_socket_port",
            parameters={
                "source": primary_body_target,
                "target_face": "front",
                "clearance_cm": 2.0,
                "width_cm": 8.0 + max(0, socket_count - 1) * 1.1,
                "height_cm": 3.2 + max(0, socket_count - 1) * 0.25,
                "depth_cm": 3.0 + max(0, socket_count - 1) * 0.3,
                "axis": "z",
                "normal_sign": 1.0,
                "surface_offset_cm": (
                    _layout_offset(layout, -15.0, 7.0)[0] - layout_center[0],
                    _layout_offset(layout, -15.0, 7.0)[1] - layout_center[1],
                ),
                "shape": "rounded_slot",
                "blend_mode": "subtract",
                "rim_bevel_cm": 0.10,
                "rim_bevel_segments": 2,
            },
            purpose="authored_features.socket_port",
        )
        injected.append(op)
        reports.append(
            _authoring_injection_report(
                op,
                reason="feature_or_style_authoring_requested_socket",
                matched_tokens=socket_tokens,
            )
        )

    mirror_tokens = request_tokens & _AUTHORING_MIRROR_TOKENS
    if mirror_tokens and not _program_has_authoring_feature(
        ShapeProgram(
            version=program.version,
            asset_name=program.asset_name,
            family=program.family,
            ops=tuple(program.ops) + tuple(injected),
        ),
        frozenset({"op.mirror"}),
        _AUTHORING_MIRROR_TOKENS,
    ):
        mirror_source = _authoring_mirror_source_target(program, tuple(injected))
        if mirror_source:
            mirror_axis = context.symmetry_axis if context.symmetry_axis in {"x", "y", "z"} else "x"
            for index, candidate in enumerate(injected):
                if str(candidate.target or "") != mirror_source:
                    continue
                injected[index] = _mirror_pair_seed_adjusted_op(
                    candidate,
                    axis=mirror_axis,
                    layout_extents=layout_extents,
                )
                break
            op = ShapeOp(
                op="op.mirror",
                target="authored_mirror_instances",
                parameters={
                    "source": mirror_source,
                    "axis": mirror_axis,
                    "include_source": True,
                    "origin_cm": 0.0,
                },
                purpose="authored_construction_graph.mirror_instances",
            )
            injected.append(op)
            reports.append(
                _authoring_injection_report(
                    op,
                    reason="construction_graph_mirror_edge_requested_instances",
                    matched_tokens=mirror_tokens,
                )
            )

    if injected and not _program_has_core_body(program):
        op = ShapeOp(
            op="sop.polybevel",
            target="authored_body",
            parameters={
                "source": {
                    "op": "solid.box",
                    "target": "authored_body_source",
                    "parameters": {
                        "width_cm": _AUTHORED_BODY_WIDTH_CM,
                        "height_cm": _AUTHORED_BODY_HEIGHT_CM,
                        "depth_cm": _AUTHORED_BODY_DEPTH_CM,
                        "center": _AUTHORED_BODY_CENTER,
                    },
                    "purpose": "body_shell.authored_box_source",
                },
                "width_cm": 1.4,
                "segments": 4,
            },
            purpose="body_shell.authored_polybevel_body",
        )
        injected.insert(0, op)
        reports.insert(
            0,
            _authoring_injection_report(
                op,
                reason="authoring_details_required_primary_body",
                matched_tokens=request_tokens,
            ),
        )

    return tuple(injected), tuple(reports)


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return None
    if converted <= 0:
        return None
    return converted


def _operation_instance_evidence(op: ShapeOp, *, op_index: int) -> dict[str, Any] | None:
    parameters = op.parameters
    rows = _positive_int(parameters.get("rows"))
    columns = _positive_int(parameters.get("columns"))
    count = _positive_int(parameters.get("count"))
    points = parameters.get("points")

    instance_count: int | None = None
    placement_mode = "single"
    if rows is not None and columns is not None:
        instance_count = rows * columns
        placement_mode = "grid"
    elif count is not None:
        instance_count = count
        placement_mode = "count"
    elif isinstance(points, (list, tuple)):
        instance_count = len(points)
        placement_mode = "points"

    if instance_count is None and op.op == "op.vent_slats":
        instance_count = _positive_int(parameters.get("count")) or 1
        placement_mode = "slat_count"
    if instance_count is None and op.op == "solid.hinge":
        instance_count = 1
        placement_mode = "single_hinge"
    if instance_count is None and op.op == "op.mirror":
        instance_count = 2 if bool(parameters.get("include_source", False)) else 1
        placement_mode = "mirror"
    if instance_count is None and op.op in {
        "op.trim_band",
        "op.panel_frame",
        "op.cut_panel_line",
        "op.inset",
        "op.mount_plate",
        "op.socket",
        "op.weld_seam",
        "op.chip_edges",
        "op.scratch_mask",
        "op.dent_mask",
    }:
        instance_count = _positive_int(parameters.get("count")) or 1
        placement_mode = "count" if parameters.get("count") is not None else "single_feature"
    if instance_count is None:
        return None

    evidence: dict[str, Any] = {
        "op_index": op_index,
        "op": op.op,
        "target": op.target,
        "purpose": op.purpose,
        "instance_count": instance_count,
        "placement_mode": placement_mode,
    }
    for key in (
        "rows",
        "columns",
        "count",
        "seed",
        "jitter_cm",
        "snap_to_grid_cm",
        "snap_cm",
        "spacing_cm",
        "row_spacing_cm",
        "column_spacing_cm",
        "axis",
        "row_axis",
        "column_axis",
        "line_axis",
        "normal_axis",
        "mirror_pair_seed_offset_axis",
        "mirror_pair_seed_offset_cm",
        "seam_group",
        "seam",
    ):
        value = parameters.get(key)
        if value is not None:
            evidence[key] = value
    center = parameters.get("center")
    if isinstance(center, (list, tuple)) and len(center) == 3:
        try:
            evidence["center"] = [float(value) for value in center]
        except (TypeError, ValueError):
            pass
    return evidence


_SEEDABLE_AUTHORING_OPS = frozenset(
    {
        "op.distribute",
        "op.repeat",
        "op.fastener_grid",
        "op.vent_slats",
        "sop.scatter_on_surface",
    }
)


def _seeded_authoring_parameters(
    op: ShapeOp,
    parameters: dict[str, Any],
    context: ShapeAuthoringContext,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if context.shape_seed is None or op.op not in _SEEDABLE_AUTHORING_OPS or "seed" in parameters:
        return parameters, None
    adjusted = dict(parameters)
    adjusted["seed"] = int(context.shape_seed)
    return adjusted, {
        "op": op.op,
        "target": op.target,
        "shape_seed": int(context.shape_seed),
        "shape_seed_source": context.shape_seed_source,
    }


_SILHOUETTE_CORE_OPS = frozenset(
    {
        "solid.box",
        "solid.panel",
        "solid.subdivision_box",
        "solid.cylinder",
        "solid.extruded_profile",
        "solid.loft",
        "solid.lofted_solid",
    }
)
_SILHOUETTE_DETAIL_TOKENS = frozenset(
    {
        "trim",
        "band",
        "panel",
        "fastener",
        "rivet",
        "bolt",
        "vent",
        "slat",
        "louver",
        "guard",
        "bracket",
        "mount",
        "socket",
        "weld",
        "scratch",
        "dent",
        "chip",
        "wear",
    }
)
_SILHOUETTE_CORE_TOKENS = frozenset(
    {
        "body",
        "shell",
        "primary",
        "volume",
        "hull",
        "root",
        "core",
        "frame",
        "door",
        "leaf",
        "cabinet",
    }
)


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _silhouette_axis_scales(context: ShapeAuthoringContext) -> tuple[tuple[float, float, float], tuple[str, ...]]:
    tokens = _context_token_set((context.silhouette_profile,))
    if not tokens:
        return (1.0, 1.0, 1.0), ()
    sx = sy = sz = 1.0
    reasons: list[str] = []
    if tokens & {"wide", "broad"}:
        sx *= 1.18
        reasons.append("wide")
    if tokens & {"long", "elongated", "stretched"}:
        sx *= 1.24
        reasons.append("long")
    if tokens & {"low", "squat", "flat"}:
        sy *= 0.84
        sx *= 1.08
        reasons.append("low")
    if tokens & {"tall", "vertical", "towering"}:
        sy *= 1.22
        sx *= 0.94
        reasons.append("tall")
    if tokens & {"narrow", "slim", "thin"}:
        sx *= 0.86
        sz *= 0.94
        reasons.append("narrow")
    if tokens & {"deep", "thick", "chunky", "bulky"}:
        sz *= 1.18
        reasons.append("deep")
    if tokens & {"compact", "small"}:
        sx *= 0.90
        sy *= 0.90
        sz *= 0.90
        reasons.append("compact")
    if tokens & {"hero", "dominant", "monumental"}:
        sx *= 1.08
        sy *= 1.08
        sz *= 1.08
        reasons.append("hero")
    scales = (
        _clamp_float(sx, 0.70, 1.45),
        _clamp_float(sy, 0.70, 1.45),
        _clamp_float(sz, 0.70, 1.45),
    )
    if all(abs(scale - 1.0) <= 1e-6 for scale in scales):
        return (1.0, 1.0, 1.0), ()
    return scales, tuple(reasons)


def _scale_numeric(value: object, scale: float) -> object:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    scaled = float(value) * scale
    if isinstance(value, int) and float(scaled).is_integer():
        return int(scaled)
    return scaled


def _scale_vec3(value: object, scales: tuple[float, float, float]) -> object:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return value
    try:
        scaled = tuple(float(value[index]) * scales[index] for index in range(3))
    except (TypeError, ValueError):
        return value
    return scaled if isinstance(value, tuple) else list(scaled)


def _scale_vec3_sequence(value: object, scales: tuple[float, float, float]) -> object:
    if not isinstance(value, (list, tuple)):
        return value
    scaled_items: list[object] = []
    changed = False
    for item in value:
        scaled = _scale_vec3(item, scales)
        changed = changed or scaled != item
        scaled_items.append(scaled)
    if not changed:
        return value
    return tuple(scaled_items) if isinstance(value, tuple) else scaled_items


def _op_record_tokens(record: dict[str, Any]) -> frozenset[str]:
    tokens: set[str] = set()
    for value in (
        record.get("op"),
        record.get("target"),
        record.get("purpose"),
        record.get("part"),
        record.get("component"),
        record.get("v2_purpose"),
    ):
        tokens.update(_slug(value).split("_"))
    tags = record.get("tags")
    tag_values = tags if isinstance(tags, (list, tuple, set)) else ()
    for tag in tag_values:
        tokens.update(_slug(tag).split("_"))
    return frozenset(token for token in tokens if token)


def _shape_op_tokens(op: ShapeOp) -> frozenset[str]:
    tokens: set[str] = set()
    for value in (op.op, op.target, op.purpose, _op_requirement(op)):
        tokens.update(_slug(value).split("_"))
    return frozenset(token for token in tokens if token)


def _op_record_is_core_silhouette(record: dict[str, Any]) -> bool:
    op_name = str(record.get("op") or record.get("v2_op") or "")
    if op_name not in _SILHOUETTE_CORE_OPS:
        return False
    tokens = _op_record_tokens(record)
    if tokens & _SILHOUETTE_DETAIL_TOKENS:
        return False
    return bool(tokens & _SILHOUETTE_CORE_TOKENS)


def _shape_op_is_core_silhouette(op: ShapeOp) -> bool:
    if op.op not in _SILHOUETTE_CORE_OPS:
        return False
    tokens = _shape_op_tokens(op)
    if tokens & _SILHOUETTE_DETAIL_TOKENS:
        return False
    return bool(tokens & _SILHOUETTE_CORE_TOKENS)


def _scale_core_dimensions(
    parameters: dict[str, Any],
    scales: tuple[float, float, float],
    *,
    op_name: str,
) -> dict[str, Any]:
    adjusted = dict(parameters)
    if "extents" in adjusted:
        adjusted["extents"] = _scale_vec3(adjusted["extents"], scales)
    if "width_cm" in adjusted:
        adjusted["width_cm"] = _scale_numeric(adjusted["width_cm"], scales[0])
    if "height_cm" in adjusted:
        adjusted["height_cm"] = _scale_numeric(adjusted["height_cm"], scales[1])
    if "depth_cm" in adjusted:
        adjusted["depth_cm"] = _scale_numeric(adjusted["depth_cm"], scales[2])
    if op_name == "solid.cylinder":
        axis = str(adjusted.get("axis") or "y").lower()
        if "height_cm" in adjusted:
            if axis == "x":
                adjusted["height_cm"] = _scale_numeric(parameters["height_cm"], scales[0])
            elif axis == "z":
                adjusted["height_cm"] = _scale_numeric(parameters["height_cm"], scales[2])
        if "radius_cm" in adjusted:
            if axis == "x":
                radius_scale = (scales[1] + scales[2]) * 0.5
            elif axis == "z":
                radius_scale = (scales[0] + scales[1]) * 0.5
            else:
                radius_scale = (scales[0] + scales[2]) * 0.5
            adjusted["radius_cm"] = _scale_numeric(adjusted["radius_cm"], radius_scale)
    return adjusted


def _scale_authoring_spatial_parameters(
    parameters: dict[str, Any],
    scales: tuple[float, float, float],
    *,
    op_name: str = "",
    scale_dimensions: bool = False,
) -> dict[str, Any]:
    adjusted = dict(parameters)
    if scale_dimensions:
        adjusted = _scale_core_dimensions(adjusted, scales, op_name=op_name)
    if "center" in adjusted:
        adjusted["center"] = _scale_vec3(adjusted["center"], scales)
    for key in ("points", "path", "sweep_path", "section_centers"):
        if key in adjusted:
            adjusted[key] = _scale_vec3_sequence(adjusted[key], scales)
    for key in ("source", "input"):
        value = adjusted.get(key)
        if isinstance(value, dict):
            adjusted[key] = _scale_authoring_operation_record(value, scales)
    for key in ("sources", "inputs"):
        value = adjusted.get(key)
        if isinstance(value, (list, tuple)):
            scaled_values: list[object] = []
            changed = False
            for item in value:
                if isinstance(item, dict):
                    scaled_item = _scale_authoring_operation_record(item, scales)
                    changed = changed or scaled_item != item
                    scaled_values.append(scaled_item)
                else:
                    scaled_values.append(item)
            if changed:
                adjusted[key] = tuple(scaled_values) if isinstance(value, tuple) else scaled_values
    return adjusted


def _scale_authoring_operation_record(
    record: dict[str, Any],
    scales: tuple[float, float, float],
) -> dict[str, Any]:
    adjusted = dict(record)
    parameters = record.get("parameters")
    if isinstance(parameters, dict):
        op_name = str(record.get("op") or "")
        adjusted["parameters"] = _scale_authoring_spatial_parameters(
            parameters,
            scales,
            op_name=op_name,
            scale_dimensions=_op_record_is_core_silhouette(record),
        )
    return adjusted


def _spatial_parameter_snapshot(parameters: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for key in (
        "center",
        "width_cm",
        "height_cm",
        "depth_cm",
        "length_cm",
        "thickness_cm",
        "extents",
    ):
        if key in parameters:
            snapshot[key] = parameters[key]
    source = parameters.get("source")
    if isinstance(source, dict):
        source_parameters = source.get("parameters")
        nested: dict[str, Any] = {
            "op": source.get("op"),
            "target": source.get("target"),
        }
        if isinstance(source_parameters, dict):
            nested["parameters"] = _spatial_parameter_snapshot(source_parameters)
        snapshot["source"] = nested
    return snapshot


def _style_pack_mode(context: ShapeAuthoringContext) -> tuple[str, frozenset[str]]:
    tokens = _context_token_set((context.style_pack,))
    if tokens & _AUTHORING_ARMORED_STYLE_TOKENS:
        return "armored", tokens
    if tokens & _AUTHORING_LIGHTWEIGHT_STYLE_TOKENS:
        return "lightweight", tokens
    if tokens & _AUTHORING_SLEEK_STYLE_TOKENS:
        return "sleek", tokens
    return "", tokens


def _style_intensity(context: ShapeAuthoringContext) -> float:
    value = context.style_intensity
    if value is None:
        return 1.0
    return _clamp_float(float(value), 0.0, 2.0)


def _style_factor(base_factor: float, intensity: float) -> float:
    if base_factor >= 1.0:
        return _clamp_float(1.0 + (base_factor - 1.0) * intensity, 0.25, 3.0)
    return _clamp_float(1.0 - (1.0 - base_factor) * intensity, 0.25, 3.0)


def _scale_present_numeric_keys(
    parameters: dict[str, Any],
    keys: tuple[str, ...],
    factor: float,
) -> bool:
    changed = False
    for key in keys:
        if key not in parameters:
            continue
        before = parameters[key]
        after = _scale_numeric(before, factor)
        if after != before:
            parameters[key] = after
            changed = True
    return changed


def _scale_profile_points(value: object, factor: float) -> object:
    if not isinstance(value, (list, tuple)):
        return value
    out: list[object] = []
    changed = False
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return value
        try:
            scaled = (float(item[0]) * factor, float(item[1]) * factor)
        except (TypeError, ValueError):
            return value
        changed = changed or scaled != tuple(item)
        out.append(scaled if isinstance(item, tuple) else list(scaled))
    if not changed:
        return value
    return tuple(out) if isinstance(value, tuple) else out


def _nested_operation_tokens(parameters: dict[str, Any]) -> frozenset[str]:
    tokens: set[str] = set()
    for key in ("source", "input"):
        value = parameters.get(key)
        if isinstance(value, dict):
            tokens.update(_op_record_tokens(value))
            source_parameters = value.get("parameters")
            if isinstance(source_parameters, dict):
                tokens.update(_nested_operation_tokens(source_parameters))
    for key in ("sources", "inputs"):
        value = parameters.get(key)
        if not isinstance(value, (list, tuple)):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            tokens.update(_op_record_tokens(item))
            source_parameters = item.get("parameters")
            if isinstance(source_parameters, dict):
                tokens.update(_nested_operation_tokens(source_parameters))
    return frozenset(tokens)


def _style_pack_adjust_parameter_tree(
    parameters: dict[str, Any],
    feature_tokens: frozenset[str],
    mode: str,
    intensity: float,
) -> dict[str, Any]:
    adjusted = dict(parameters)
    for key in ("source", "input"):
        value = adjusted.get(key)
        if isinstance(value, dict):
            adjusted[key] = _style_pack_adjust_record(value, mode, intensity)
    for key in ("sources", "inputs"):
        value = adjusted.get(key)
        if isinstance(value, (list, tuple)):
            out: list[object] = []
            changed = False
            for item in value:
                if isinstance(item, dict):
                    styled = _style_pack_adjust_record(item, mode, intensity)
                    changed = changed or styled != item
                    out.append(styled)
                else:
                    out.append(item)
            if changed:
                adjusted[key] = tuple(out) if isinstance(value, tuple) else out

    structural_tokens = (
        _AUTHORING_TRIM_TOKENS
        | _AUTHORING_PANEL_TOKENS
        | _AUTHORING_GUARD_TOKENS
        | _AUTHORING_BRACKET_TOKENS
        | _AUTHORING_MOUNT_TOKENS
        | _AUTHORING_SOCKET_TOKENS
        | _AUTHORING_WELD_TOKENS
    )
    if mode == "armored":
        if feature_tokens & structural_tokens:
            _scale_present_numeric_keys(
                adjusted,
                ("thickness_cm", "border_width_cm", "depth_cm", "height_cm"),
                _style_factor(1.18, intensity),
            )
            _scale_present_numeric_keys(adjusted, ("bevel_width_cm",), _style_factor(1.12, intensity))
        if feature_tokens & _AUTHORING_FASTENER_TOKENS:
            _scale_present_numeric_keys(
                adjusted,
                ("radius_cm", "height_cm", "bevel_width_cm"),
                _style_factor(1.14, intensity),
            )
            if "include_washer" in adjusted:
                adjusted["include_washer"] = True
            if "profile_points" in adjusted:
                adjusted["profile_points"] = _scale_profile_points(
                    adjusted["profile_points"],
                    _style_factor(1.12, intensity),
                )
        if feature_tokens & _AUTHORING_VENT_TOKENS:
            _scale_present_numeric_keys(
                adjusted,
                ("thickness_cm", "height_cm"),
                _style_factor(1.10, intensity),
            )
    elif mode == "lightweight":
        if feature_tokens & structural_tokens:
            _scale_present_numeric_keys(
                adjusted,
                ("thickness_cm", "border_width_cm", "depth_cm", "height_cm"),
                _style_factor(0.82, intensity),
            )
            _scale_present_numeric_keys(adjusted, ("bevel_width_cm",), _style_factor(0.90, intensity))
        if feature_tokens & _AUTHORING_FASTENER_TOKENS:
            _scale_present_numeric_keys(
                adjusted,
                ("radius_cm", "height_cm"),
                _style_factor(0.86, intensity),
            )
            if "profile_points" in adjusted:
                adjusted["profile_points"] = _scale_profile_points(
                    adjusted["profile_points"],
                    _style_factor(0.88, intensity),
                )
        if feature_tokens & _AUTHORING_VENT_TOKENS:
            _scale_present_numeric_keys(adjusted, ("thickness_cm",), _style_factor(0.76, intensity))
            count = _positive_int(adjusted.get("count"))
            if count is not None:
                adjusted["count"] = min(128, count + max(1, int(round(2.0 * intensity))))
    elif mode == "sleek":
        if feature_tokens & structural_tokens:
            _scale_present_numeric_keys(
                adjusted,
                ("thickness_cm", "depth_cm"),
                _style_factor(0.72, intensity),
            )
            _scale_present_numeric_keys(
                adjusted,
                ("border_width_cm", "bevel_width_cm"),
                _style_factor(0.82, intensity),
            )
        if feature_tokens & _AUTHORING_FASTENER_TOKENS:
            adjusted.setdefault("head_style", "flush")
            _scale_present_numeric_keys(adjusted, ("height_cm",), _style_factor(0.72, intensity))
        if "segments" in adjusted:
            current_segments = _positive_int(adjusted.get("segments")) or 1
            adjusted["segments"] = max(current_segments, 3)
    return adjusted


def _style_pack_adjust_record(record: dict[str, Any], mode: str, intensity: float) -> dict[str, Any]:
    adjusted = dict(record)
    parameters = record.get("parameters")
    if isinstance(parameters, dict):
        feature_tokens = _op_record_tokens(record) | _nested_operation_tokens(parameters)
        adjusted["parameters"] = _style_pack_adjust_parameter_tree(
            parameters,
            feature_tokens,
            mode,
            intensity,
        )
    return adjusted


def _style_pack_adjusted_parameters(
    op: ShapeOp,
    parameters: dict[str, Any],
    context: ShapeAuthoringContext,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    mode, tokens = _style_pack_mode(context)
    if not mode:
        return parameters, None
    intensity = _style_intensity(context)
    feature_tokens = _shape_op_tokens(op) | _nested_operation_tokens(parameters)
    adjusted = _style_pack_adjust_parameter_tree(parameters, feature_tokens, mode, intensity)
    if adjusted == parameters:
        return parameters, None
    return adjusted, {
        "op": op.op,
        "target": op.target,
        "style_pack": context.style_pack,
        "style_mode": mode,
        "style_intensity": intensity,
        "matched_tokens": sorted(tokens),
        "before": _spatial_parameter_snapshot(parameters),
        "after": _spatial_parameter_snapshot(adjusted),
    }


def _silhouette_adjusted_parameters(
    op: ShapeOp,
    parameters: dict[str, Any],
    context: ShapeAuthoringContext,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    scales, reasons = _silhouette_axis_scales(context)
    if not reasons:
        return parameters, None
    adjusted = _scale_authoring_spatial_parameters(
        parameters,
        scales,
        op_name=op.op,
        scale_dimensions=_shape_op_is_core_silhouette(op),
    )
    if adjusted == parameters:
        return parameters, None
    return adjusted, {
        "op": op.op,
        "target": op.target,
        "silhouette_profile": context.silhouette_profile,
        "axis_scales": {"x": scales[0], "y": scales[1], "z": scales[2]},
        "reasons": list(reasons),
        "before": _spatial_parameter_snapshot(parameters),
        "after": _spatial_parameter_snapshot(adjusted),
    }


def _scaled_count(
    value: object,
    multiplier: float,
    *,
    max_value: int = 512,
    area_axis: bool = False,
) -> int | None:
    current = _positive_int(value)
    if current is None:
        return None
    factor = math.sqrt(multiplier) if area_axis else multiplier
    if factor <= 0.0:
        return 1
    scaled = math.ceil(current * factor) if factor >= 1.0 else round(current * factor)
    return max(1, min(max_value, int(scaled)))


def _scale_count_param(
    parameters: dict[str, Any],
    key: str,
    multiplier: float,
    *,
    max_value: int = 512,
    area_axis: bool = False,
) -> bool:
    scaled = _scaled_count(
        parameters.get(key),
        multiplier,
        max_value=max_value,
        area_axis=area_axis,
    )
    if scaled is None or parameters.get(key) == scaled:
        return False
    parameters[key] = scaled
    return True


def _scale_spacing_for_count(
    parameters: dict[str, Any],
    *,
    count_key: str,
    old_count: int | None,
    spacing_key: str,
) -> bool:
    if old_count is None or old_count <= 1 or spacing_key not in parameters:
        return False
    new_count = _positive_int(parameters.get(count_key))
    if new_count is None or new_count <= 1 or new_count == old_count:
        return False
    try:
        spacing = float(parameters[spacing_key])
    except (TypeError, ValueError):
        return False
    if not math.isfinite(spacing) or spacing <= 0.0:
        return False
    parameters[spacing_key] = spacing * float(old_count - 1) / float(new_count - 1)
    return True


def _scale_grid_spacing(
    parameters: dict[str, Any],
    *,
    old_rows: int | None,
    old_columns: int | None,
    spacing_key: str,
) -> bool:
    if spacing_key not in parameters:
        return False
    try:
        spacing = float(parameters[spacing_key])
    except (TypeError, ValueError):
        return False
    if not math.isfinite(spacing) or spacing <= 0.0:
        return False
    new_rows = _positive_int(parameters.get("rows"))
    new_columns = _positive_int(parameters.get("columns"))
    candidates: list[float] = []
    if old_rows is not None and old_rows > 1 and new_rows is not None and new_rows > 1:
        candidates.append(spacing * float(old_rows - 1) / float(new_rows - 1))
    if (
        old_columns is not None
        and old_columns > 1
        and new_columns is not None
        and new_columns > 1
    ):
        candidates.append(spacing * float(old_columns - 1) / float(new_columns - 1))
    if not candidates:
        return False
    parameters[spacing_key] = min(candidates)
    return True


def _scale_wfc_density(parameters: dict[str, Any], multiplier: float) -> bool:
    old_width = _positive_int(parameters.get("width_cells"))
    old_depth = _positive_int(parameters.get("depth_cells"))
    changed = False
    changed |= _scale_count_param(parameters, "width_cells", multiplier, max_value=64, area_axis=True)
    changed |= _scale_count_param(parameters, "depth_cells", multiplier, max_value=64, area_axis=True)
    new_width = _positive_int(parameters.get("width_cells"))
    new_depth = _positive_int(parameters.get("depth_cells"))
    if old_width and old_depth and new_width and new_depth and "cell_size_cm" in parameters:
        try:
            cell_size = float(parameters["cell_size_cm"])
        except (TypeError, ValueError):
            cell_size = 0.0
        if math.isfinite(cell_size) and cell_size > 0.0:
            width_ratio = float(old_width) / float(new_width)
            depth_ratio = float(old_depth) / float(new_depth)
            parameters["cell_size_cm"] = cell_size * min(width_ratio, depth_ratio)
            changed = True
    return changed


def _operation_density_multiplier(op: ShapeOp, context: ShapeAuthoringContext) -> tuple[float, tuple[str, ...]]:
    if "child_modules" in str(op.purpose or "") or str(op.target or "") == "authored_child_module_anchor_grid":
        return 1.0, ()
    multiplier = context.density_multiplier if context.feature_density else 1.0
    sources: list[str] = []
    if context.feature_density:
        sources.append(context.feature_density_source or "features.density")
    tokens = _shape_op_tokens(op) | _nested_operation_tokens(op.parameters)
    trim_tokens = _AUTHORING_TRIM_TOKENS | _AUTHORING_PANEL_TOKENS | _AUTHORING_PANEL_LINE_TOKENS
    greeble_tokens = (
        _AUTHORING_FASTENER_TOKENS
        | _AUTHORING_VENT_TOKENS
        | _AUTHORING_GUARD_TOKENS
        | _AUTHORING_BRACKET_TOKENS
        | _AUTHORING_MOUNT_TOKENS
        | _AUTHORING_SOCKET_TOKENS
        | _AUTHORING_HANDLE_TOKENS
        | _AUTHORING_CONDUIT_TOKENS
        | _AUTHORING_WEAR_TOKENS
        | _AUTHORING_GRIME_TOKENS
    )
    if context.trim_density is not None and tokens & trim_tokens:
        multiplier *= max(0.0, float(context.trim_density))
        sources.append("build.shape.trim_density")
    if context.greeble_density is not None and tokens & greeble_tokens:
        multiplier *= max(0.0, float(context.greeble_density))
        sources.append("build.shape.greeble_density")
    return _clamp_float(multiplier, 0.0, 4.0), tuple(sources)


def _density_scaled_parameters(
    op: ShapeOp,
    context: ShapeAuthoringContext,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    multiplier, density_sources = _operation_density_multiplier(op, context)
    if not density_sources or abs(multiplier - 1.0) <= 1e-6:
        return op.parameters, None
    parameters = dict(op.parameters)
    before = dict(parameters)
    changed = False

    if op.op == "op.fastener_grid":
        old_rows = _positive_int(parameters.get("rows"))
        old_columns = _positive_int(parameters.get("columns"))
        changed |= _scale_count_param(parameters, "rows", multiplier, max_value=64, area_axis=True)
        changed |= _scale_count_param(parameters, "columns", multiplier, max_value=64, area_axis=True)
        changed |= _scale_grid_spacing(
            parameters,
            old_rows=old_rows,
            old_columns=old_columns,
            spacing_key="spacing_cm",
        )
    elif op.op == "op.vent_slats":
        old_count = _positive_int(parameters.get("count"))
        changed |= _scale_count_param(parameters, "count", multiplier, max_value=128)
        changed |= _scale_spacing_for_count(
            parameters,
            count_key="count",
            old_count=old_count,
            spacing_key="spacing_cm",
        )
    elif op.op == "op.repeat":
        old_count = _positive_int(parameters.get("count"))
        changed |= _scale_count_param(parameters, "count", multiplier, max_value=256)
        changed |= _scale_spacing_for_count(
            parameters,
            count_key="count",
            old_count=old_count,
            spacing_key="spacing_cm",
        )
    elif op.op == "op.distribute":
        old_rows = _positive_int(parameters.get("rows"))
        old_columns = _positive_int(parameters.get("columns"))
        old_count = _positive_int(parameters.get("count"))
        changed |= _scale_count_param(parameters, "rows", multiplier, max_value=128, area_axis=True)
        changed |= _scale_count_param(parameters, "columns", multiplier, max_value=128, area_axis=True)
        changed |= _scale_count_param(parameters, "count", multiplier, max_value=512)
        changed |= _scale_spacing_for_count(
            parameters,
            count_key="count",
            old_count=old_count,
            spacing_key="spacing_cm",
        )
        changed |= _scale_spacing_for_count(
            parameters,
            count_key="rows",
            old_count=old_rows,
            spacing_key="row_spacing_cm",
        )
        changed |= _scale_spacing_for_count(
            parameters,
            count_key="columns",
            old_count=old_columns,
            spacing_key="column_spacing_cm",
        )
        if "count" not in before and "rows" not in before and "columns" not in before:
            base_density = float(parameters.get("density", 1.0) or 1.0)
            parameters["density"] = max(0.05, base_density * multiplier)
            changed = True
    elif op.op in {"op.chip_edges", "op.scratch_mask", "op.dent_mask", "op.grime_mask"}:
        old_count = _positive_int(parameters.get("count"))
        if old_count is None:
            parameters["count"] = 2
            old_count = 2
            changed = True
        changed |= _scale_count_param(parameters, "count", multiplier, max_value=128)
        changed |= _scale_spacing_for_count(
            parameters,
            count_key="count",
            old_count=old_count,
            spacing_key="spacing_cm",
        )
    elif op.op == "solid.wfc_modular_assembly":
        changed |= _scale_wfc_density(parameters, multiplier)
    elif op.op == "solid.cga_facade":
        changed |= _scale_count_param(parameters, "floors", multiplier, max_value=64, area_axis=True)
        changed |= _scale_count_param(parameters, "bays", multiplier, max_value=64, area_axis=True)
    elif op.op == "solid.branching_tree":
        for key, max_value in (
            ("branch_count", 128),
            ("canopy_cluster_count", 256),
            ("root_count", 64),
        ):
            changed |= _scale_count_param(parameters, key, multiplier, max_value=max_value)
    elif op.op == "solid.terrain_patch":
        changed |= _scale_count_param(parameters, "resolution", multiplier, max_value=192, area_axis=True)
    elif op.op == "solid.sdf_metaball_cluster":
        changed |= _scale_count_param(parameters, "blob_count", multiplier, max_value=96, area_axis=True)
        changed |= _scale_count_param(parameters, "resolution", multiplier, max_value=128, area_axis=True)
    else:
        for key, max_value in (
            ("rung_count", 256),
            ("bay_count", 128),
            ("rib_count", 128),
            ("cross_rib_count", 128),
            ("slat_count", 128),
            ("rows", 128),
            ("columns", 128),
            ("count", 512),
        ):
            changed |= _scale_count_param(parameters, key, multiplier, max_value=max_value)

    if not changed or parameters == before:
        return op.parameters, None
    return parameters, {
        "op": op.op,
        "target": op.target,
        "feature_density": context.feature_density,
        "density_sources": list(density_sources),
        "density_multiplier": multiplier,
        "trim_density": context.trim_density,
        "greeble_density": context.greeble_density,
        "before": before,
        "after": dict(parameters),
    }


def _context_token_set(values: tuple[str, ...]) -> frozenset[str]:
    tokens: set[str] = set()
    for value in values:
        if not str(value or "").strip():
            continue
        tokens.update(token for token in _slug(value).split("_") if token)
    if tokens & {"bevel", "beveled", "eased", "round", "rounded", "soft"}:
        tokens.update({"bevel", "rounded", "soft"})
    if tokens & {"chamfer", "chamfered", "hard", "crisp", "sharp"}:
        tokens.update({"chamfer", "hard", "sharp"})
    return frozenset(tokens)


def _context_value_slugs(values: tuple[str, ...]) -> frozenset[str]:
    return frozenset(_slug(value) for value in values if str(value or "").strip())


def _repair_policy_request_values(context: ShapeAuthoringContext) -> tuple[str, ...]:
    return tuple(
        value
        for value in (
            context.repair_policy_use,
            context.repair_policy_mode,
            *context.repair_policy_allow,
        )
        if str(value or "").strip()
    )


def _repair_policy_denies_feature_kind(
    *,
    deny_slugs: frozenset[str],
    deny_tokens: frozenset[str],
    kind: str,
    action: str = "",
) -> bool:
    kind_slug = _slug(kind)
    action_slug = _slug(action)
    if kind_slug in deny_slugs or (action_slug and action_slug in deny_slugs):
        return True
    kind_tokens = frozenset(token for token in kind_slug.split("_") if token)
    action_tokens = frozenset(token for token in action_slug.split("_") if token)
    if kind_tokens and kind_tokens <= deny_tokens:
        return True
    if action_tokens and action_tokens <= deny_tokens:
        return True
    feature_tokens = _REPAIR_POLICY_FEATURE_TOKENS.get(kind_slug, frozenset())
    return bool(feature_tokens and feature_tokens & deny_tokens)


def _repair_policy_requested_feature_kinds(context: ShapeAuthoringContext) -> tuple[str, ...]:
    request_values = _repair_policy_request_values(context)
    if not request_values:
        return ()
    request_slugs = _context_value_slugs(request_values)
    request_tokens = _context_token_set(request_values)
    deny_values = tuple(value for value in context.repair_policy_deny if str(value or "").strip())
    deny_slugs = _context_value_slugs(deny_values)
    deny_tokens = _context_token_set(deny_values)
    selected: list[str] = []
    seen: set[str] = set()

    def add_kind(kind: str, action: str = "") -> None:
        kind_slug = _slug(kind)
        if kind_slug not in _REPAIR_POLICY_FEATURE_TOKENS or kind_slug in seen:
            return
        if _repair_policy_denies_feature_kind(
            deny_slugs=deny_slugs,
            deny_tokens=deny_tokens,
            kind=kind_slug,
            action=action,
        ):
            return
        seen.add(kind_slug)
        selected.append(kind_slug)

    if "hero_hardsurface_repair" in request_slugs or (
        "hero" in request_tokens
        and "repair" in request_tokens
        and ("hardsurface" in request_tokens or {"hard", "surface"} <= request_tokens)
    ):
        for kind in _REPAIR_POLICY_HARDSURFACE_DEFAULT_FEATURES:
            add_kind(kind, "hero_hardsurface_repair")

    for action_slug in request_slugs:
        for kind in _REPAIR_POLICY_ACTION_FEATURES.get(action_slug, ()):
            add_kind(kind, action_slug)
        if action_slug in _REPAIR_POLICY_FEATURE_TOKENS:
            add_kind(action_slug, action_slug)
    return tuple(selected)


def _repair_policy_authoring_tokens(context: ShapeAuthoringContext) -> frozenset[str]:
    tokens: set[str] = set()
    for kind in _repair_policy_requested_feature_kinds(context):
        tokens.update(_REPAIR_POLICY_FEATURE_TOKENS.get(kind, frozenset()))
    return frozenset(tokens)


def _repair_policy_edge_tokens(context: ShapeAuthoringContext) -> frozenset[str]:
    if "edge_break" not in _repair_policy_requested_feature_kinds(context):
        return frozenset()
    return frozenset({"bevel", "rounded", "soft"})


def _edge_authoring_adjusted_parameters(
    op: ShapeOp,
    parameters: dict[str, Any],
    context: ShapeAuthoringContext,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if op.op not in {"sop.polybevel", "op.bevel", "op.chamfer"}:
        return parameters, None
    edge_tokens = _context_token_set(context.edge_classes)
    repair_edge_tokens = _repair_policy_edge_tokens(context)
    if repair_edge_tokens:
        edge_tokens = frozenset((*edge_tokens, *repair_edge_tokens))
    edge_complexity_tokens = _context_token_set((context.edge_complexity,))
    if edge_complexity_tokens and not (edge_complexity_tokens & {"off", "none", "low"}):
        if edge_complexity_tokens & {"hard", "crisp", "sharp", "chamfer", "chamfered"}:
            edge_tokens = frozenset((*edge_tokens, "chamfer", "hard", "sharp"))
        else:
            edge_tokens = frozenset((*edge_tokens, "bevel", "rounded", "soft"))
    seam_tokens = _context_token_set(context.seam_classes)
    if not edge_tokens and not seam_tokens:
        return parameters, None

    adjusted = dict(parameters)
    before = dict(adjusted)
    if edge_tokens & {"bevel", "rounded", "soft"}:
        if "width_cm" in adjusted:
            try:
                width = float(adjusted["width_cm"])
            except (TypeError, ValueError):
                width = 0.0
            if math.isfinite(width) and width > 0.0:
                adjusted["width_cm"] = width * 1.25
        if "segments" in adjusted:
            current_segments = _positive_int(adjusted.get("segments")) or 1
            adjusted["segments"] = max(current_segments, 3)
    elif edge_tokens & {"chamfer", "hard", "sharp"} and op.op != "op.chamfer":
        if "segments" in adjusted:
            adjusted["segments"] = 1
        if "width_cm" in adjusted:
            try:
                width = float(adjusted["width_cm"])
            except (TypeError, ValueError):
                width = 0.0
            if math.isfinite(width) and width > 0.0:
                adjusted["width_cm"] = width * 0.85

    if context.seam_classes and "seam_groups" not in adjusted and "target_seam_groups" not in adjusted:
        adjusted["target_seam_groups"] = list(context.seam_classes)

    if adjusted == before:
        return parameters, None
    return adjusted, {
        "op": op.op,
        "target": op.target,
        "edge_classes": list(context.edge_classes),
        "edge_complexity": context.edge_complexity,
        "repair_policy_edge_tokens": sorted(repair_edge_tokens),
        "seam_classes": list(context.seam_classes),
        "before": before,
        "after": dict(adjusted),
    }


def _apply_authoring_context_to_program(
    program: ShapeProgram,
    context: ShapeAuthoringContext,
) -> tuple[ShapeProgram, dict[str, Any]]:
    injected_ops, injection_reports = _authoring_injected_ops(program, context)
    source_ops = tuple(program.ops) + injected_ops
    adjusted_ops: list[ShapeOp] = []
    silhouette_adjustments: list[dict[str, Any]] = []
    style_adjustments: list[dict[str, Any]] = []
    adjustments: list[dict[str, Any]] = []
    edge_adjustments: list[dict[str, Any]] = []
    seed_adjustments: list[dict[str, Any]] = []
    operation_instance_evidence: list[dict[str, Any]] = []
    filtered_ops: list[dict[str, Any]] = []
    preserved_unmatched_source_ops: list[dict[str, Any]] = []
    for index, op in enumerate(source_ops):
        if not _op_matches_authoring(op, context):
            unmatched_report = {
                "op_index": index,
                "op": op.op,
                "target": op.target,
                "purpose": op.purpose,
                "reason": "not_matched_by_features_allow",
            }
            if index >= len(program.ops) or not _op_is_feature_allow_preservation_core(op):
                filtered_ops.append(unmatched_report)
                continue
            unmatched_report["reason"] = "primary_source_body_preserved_despite_feature_allow_miss"
            preserved_unmatched_source_ops.append(unmatched_report)
        parameters, silhouette_adjustment = _silhouette_adjusted_parameters(
            op,
            op.parameters,
            context,
        )
        if silhouette_adjustment is not None:
            silhouette_adjustment["op_index"] = index
            silhouette_adjustments.append(silhouette_adjustment)
        parameters, adjustment = _density_scaled_parameters(
            ShapeOp(op=op.op, target=op.target, parameters=parameters, purpose=op.purpose),
            context,
        )
        if adjustment is not None:
            adjustment["op_index"] = index
            adjustments.append(adjustment)
        parameters, style_adjustment = _style_pack_adjusted_parameters(
            ShapeOp(op=op.op, target=op.target, parameters=parameters, purpose=op.purpose),
            parameters,
            context,
        )
        if style_adjustment is not None:
            style_adjustment["op_index"] = index
            style_adjustments.append(style_adjustment)
        parameters, edge_adjustment = _edge_authoring_adjusted_parameters(
            op,
            parameters,
            context,
        )
        if edge_adjustment is not None:
            edge_adjustment["op_index"] = index
            edge_adjustments.append(edge_adjustment)
        parameters, seed_adjustment = _seeded_authoring_parameters(
            op,
            parameters,
            context,
        )
        if seed_adjustment is not None:
            seed_adjustment["op_index"] = index
            seed_adjustments.append(seed_adjustment)
        adjusted_op = ShapeOp(
            op=op.op,
            target=op.target,
            parameters=parameters,
            purpose=op.purpose,
        )
        adjusted_ops.append(adjusted_op)
        instance_evidence = _operation_instance_evidence(adjusted_op, op_index=index)
        if instance_evidence is not None:
            operation_instance_evidence.append(instance_evidence)
    report = {
        "feature_density": context.feature_density,
        "feature_density_source": context.feature_density_source,
        "density_multiplier": context.density_multiplier,
        "repair_policy_use": context.repair_policy_use,
        "repair_policy_mode": context.repair_policy_mode,
        "repair_policy_allow": list(context.repair_policy_allow),
        "repair_policy_deny": list(context.repair_policy_deny),
        "repair_policy_feature_kinds": list(_repair_policy_requested_feature_kinds(context)),
        "shape_seed": context.shape_seed,
        "shape_seed_source": context.shape_seed_source,
        "panelization": context.panelization,
        "edge_complexity": context.edge_complexity,
        "edge_treatment": context.edge_treatment,
        "style_pack": context.style_pack,
        "silhouette_profile": context.silhouette_profile,
        "structural_profile": context.structural_profile,
        "route_structure": context.route_structure,
        "style_intensity": context.style_intensity,
        "trim_density": context.trim_density,
        "greeble_density": context.greeble_density,
        "socket_count": len(context.socket_ids),
        "anchor_count": len(context.anchor_ids),
        "connection_count": context.connection_count,
        "route_connection_count": context.route_connection_count,
        "attach_connection_count": context.attach_connection_count,
        "support_connection_count": context.support_connection_count,
        "external_connection_count": context.external_connection_count,
        "branch_connection_count": context.branch_connection_count,
        "connection_layout_mode": context.connection_layout_mode,
        "connection_segment_count": context.connection_segment_count,
        "connection_path_complexity": context.connection_path_complexity,
        "child_module_count": context.child_module_count,
        "module_slot_count": context.module_slot_count,
        "nested_asset_count": context.nested_asset_count,
        "program_op_count_before": len(program.ops),
        "program_op_count_after_injection": len(source_ops),
        "program_op_count_after": len(adjusted_ops),
        "injected_authoring_op_count": len(injection_reports),
        "injected_authoring_ops": list(injection_reports),
        "filtered_by_feature_allow": len(filtered_ops),
        "filtered_ops": filtered_ops,
        "preserved_unmatched_source_op_count": len(preserved_unmatched_source_ops),
        "preserved_unmatched_source_ops": preserved_unmatched_source_ops,
        "silhouette_adjustment_count": len(silhouette_adjustments),
        "silhouette_adjustments": silhouette_adjustments,
        "style_adjustment_count": len(style_adjustments),
        "style_adjustments": style_adjustments,
        "adjustment_count": len(adjustments),
        "adjustments": adjustments,
        "edge_adjustment_count": len(edge_adjustments),
        "edge_adjustments": edge_adjustments,
        "seed_adjustment_count": len(seed_adjustments),
        "seed_adjustments": seed_adjustments,
        "operation_instance_evidence_scope": "shape_program_after_authoring_before_v1_record_filter",
        "operation_instance_evidence_count": len(operation_instance_evidence),
        "operation_instance_evidence": operation_instance_evidence,
    }
    if (
        not silhouette_adjustments
        and not style_adjustments
        and not adjustments
        and not edge_adjustments
        and not seed_adjustments
        and not filtered_ops
        and not injected_ops
    ):
        return program, report
    return (
        ShapeProgram(
            version=program.version,
            asset_name=program.asset_name,
            family=program.family,
            ops=tuple(adjusted_ops),
        ),
        report,
    )


_CORE_REQUIREMENT_TOKENS = frozenset(
    {
        "body",
        "shell",
        "primary",
        "volume",
        "frame",
        "door",
        "leaf",
        "cabinet",
    }
)


def _record_requirement(record: dict[str, Any]) -> str:
    purpose = str(record.get("v2_purpose") or "")
    if "." in purpose:
        return purpose.split(".", 1)[0]
    return purpose


def _record_is_core(record: dict[str, Any]) -> bool:
    values = [
        _record_requirement(record),
    ]
    tokens = set()
    for value in values:
        tokens.update(_slug(value).split("_"))
    return bool(tokens & _CORE_REQUIREMENT_TOKENS)


def _record_is_primary_body_shell(record: dict[str, Any]) -> bool:
    if str(record.get("blend_mode") or "union") != "union":
        return False
    tags = {str(tag) for tag in record.get("tags", []) if str(tag)}
    v2_op = str(record.get("v2_op") or record.get("v2_source_op") or "")
    if v2_op in {
        "op.panel_frame",
        "op.trim_band",
        "op.fastener_grid",
        "op.vent_slats",
        "op.corner_guard_set",
        "op.socket",
        "op.bracket",
        "op.mount_plate",
        "op.weld_seam",
        "op.chip_edges",
    }:
        return False
    if tags & {"surface_detail", "integration_detail", "edge_chip"} and "body_shell" not in tags:
        return False
    tokens = set()
    for value in (
        record.get("part"),
        record.get("component"),
        record.get("region"),
        record.get("v2_purpose"),
        v2_op,
        " ".join(tags),
    ):
        tokens.update(_slug(value).split("_"))
    return bool(tokens & {"body", "shell", "primary", "volume", "door", "leaf", "cabinet"})


def _records_have_primary_body_shell(records: tuple[dict[str, Any], ...]) -> bool:
    return any(_record_is_primary_body_shell(dict(record)) for record in records)


def _record_is_required_composition_authoring(record: dict[str, Any], context: ShapeAuthoringContext) -> bool:
    if not (
        context.socket_ids
        or context.anchor_ids
        or context.connection_count
        or context.child_module_count
        or context.module_slot_count
        or context.nested_asset_count
    ):
        return False
    purpose = str(record.get("v2_purpose") or "")
    if purpose.startswith(("authored_child_modules.", "authored_interfaces.", "authored_connections.")):
        return True
    part = str(record.get("part") or record.get("target") or "")
    if _is_authored_connection_edge_target(part):
        return True
    return part in {
        "authored_child_module_anchor_grid",
        "authored_connection_endpoint_ports",
        "authored_socket_port",
        "authored_conduit_run",
        "authored_mount_plate",
        "authored_support_bracket",
    }


def _template_bounds_from_regions(
    template_shape_ir: ShapeIR,
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    bounds = []
    for region in template_shape_ir.regions:
        try:
            center = tuple(float(value) for value in region.center)
            extents = tuple(max(float(value), 1e-6) for value in region.extents)
        except (TypeError, ValueError):
            continue
        bounds.append(
            (
                tuple(center[index] - extents[index] * 0.5 for index in range(3)),
                tuple(center[index] + extents[index] * 0.5 for index in range(3)),
            )
        )
    if not bounds:
        return None
    mins = tuple(min(item[0][index] for item in bounds) for index in range(3))
    maxs = tuple(max(item[1][index] for item in bounds) for index in range(3))
    return mins, maxs


def _template_bounds_from_primitives(
    template_shape_ir: ShapeIR,
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    try:
        from .exact_solids import primitive_mesh
    except ImportError:
        return None
    bounds = []
    for primitive in template_shape_ir.primitives:
        if (primitive.blend_mode or "union") != "union":
            continue
        try:
            mesh = primitive_mesh(primitive)
            raw_bounds = np.asarray(mesh.bounds, dtype=np.float64)
        except Exception:
            continue
        if raw_bounds.shape == (2, 3):
            bounds.append(
                (
                    tuple(float(value) for value in raw_bounds[0]),
                    tuple(float(value) for value in raw_bounds[1]),
                )
            )
    if not bounds:
        return None
    mins = tuple(min(item[0][index] for item in bounds) for index in range(3))
    maxs = tuple(max(item[1][index] for item in bounds) for index in range(3))
    return mins, maxs


def _primary_body_record_from_program(program: ShapeProgram) -> dict[str, Any] | None:
    for op in program.ops:
        if not _op_is_primary_body_shell(op):
            continue
        body_program = ShapeProgram(
            version=program.version,
            asset_name=program.asset_name,
            family=program.family,
            ops=(op,),
        )
        try:
            result = lower_to_v1(body_program, materialize_output=False)
        except Exception:
            continue
        for record in result.v1_records:
            candidate = dict(record)
            if _record_is_primary_body_shell(candidate):
                tags = [str(tag) for tag in candidate.get("tags", []) if str(tag)]
                for tag in ("grammar_program", "body_shell", "recovered_primary_body"):
                    if tag not in tags:
                        tags.append(tag)
                candidate["tags"] = tags
                semantic_metadata = candidate.get("semantic_metadata")
                semantic_metadata = dict(semantic_metadata) if isinstance(semantic_metadata, dict) else {}
                body_metadata = semantic_metadata.get("shape_program_primary_body")
                body_metadata = dict(body_metadata) if isinstance(body_metadata, dict) else {}
                semantic_metadata["shape_program_primary_body"] = {
                    **body_metadata,
                    "source": "shape_program_driver.recovered_primary_body_op",
                    "op": op.op,
                    "target": op.target,
                    "purpose": op.purpose,
                }
                candidate["semantic_metadata"] = semantic_metadata
                return candidate
    return None


def _synthesized_primary_body_record(template_shape_ir: ShapeIR, program: ShapeProgram) -> dict[str, Any]:
    recovered = _primary_body_record_from_program(program)
    if recovered is not None:
        return recovered
    bounds = _template_bounds_from_regions(template_shape_ir) or _template_bounds_from_primitives(template_shape_ir)
    if bounds is None:
        layout = _default_authoring_layout()
        center = _layout_vector(layout, "center")
        extents = _layout_vector(layout, "extents")
    else:
        mins, maxs = bounds
        extents = tuple(max(maxs[index] - mins[index], 1.0) for index in range(3))
        center = tuple((mins[index] + maxs[index]) * 0.5 for index in range(3))
    bevel = max(0.25, min(extents) * 0.035)
    return {
        "primitive_type": "subdivision_box",
        "part": "authored_body",
        "component": "body_shell",
        "region": "authored_body.shell",
        "center": center,
        "extents": extents,
        "corner_radii": (bevel,) * 8,
        "corner_segments": 3,
        "rounding": 0.0,
        "blend_mode": "union",
        "tags": [
            "grammar_program",
            "body_shell",
            "synthesized_primary_body",
            "template_bounds_body",
        ],
        "v2_op": "shape_ir_v2.synthesized_primary_body",
        "v2_purpose": "body_shell.synthesized_from_template_bounds",
        "semantic_metadata": {
            "shape_ir_v2": {
                "v2_op": "shape_ir_v2.synthesized_primary_body",
                "v2_purpose": "body_shell.synthesized_from_template_bounds",
                "template_blueprint_id": template_shape_ir.blueprint_id,
                "source": "shape_program_driver.template_bounds_primary_body",
            }
        },
    }


def _record_matches_authoring(record: dict[str, Any], context: ShapeAuthoringContext) -> bool:
    if not context.feature_allow:
        return True
    if _record_is_core(record) or _record_is_required_composition_authoring(record, context):
        return True
    if context.matches_allowed_feature(
        _record_requirement(record),
        record.get("part"),
        record.get("v2_purpose"),
        " ".join(str(tag) for tag in record.get("tags", []) if str(tag)),
    ):
        return True
    repair_tokens = _repair_policy_authoring_tokens(context)
    if not repair_tokens:
        return False
    record_tokens = _context_token_set(
        (
            _record_requirement(record),
            str(record.get("part") or ""),
            str(record.get("component") or ""),
            str(record.get("region") or ""),
            str(record.get("v2_op") or ""),
            str(record.get("v2_source_op") or ""),
            " ".join(str(tag) for tag in record.get("tags", []) if str(tag)),
        )
    )
    return bool(repair_tokens & record_tokens)


def _record_has_kernel_program(record: dict[str, Any]) -> bool:
    tags = record.get("tags")
    if isinstance(tags, list) and any("kernel_program" in str(tag) for tag in tags):
        return True
    for value in record.values():
        if isinstance(value, dict) and isinstance(value.get("kernel_program"), dict):
            return True
    return False


def _record_operation_index(record: dict[str, Any]) -> int | None:
    semantic_metadata = record.get("semantic_metadata")
    if not isinstance(semantic_metadata, dict):
        return None
    provenance = semantic_metadata.get("shape_ir_v2")
    if not isinstance(provenance, dict):
        return None
    value = provenance.get("operation_index")
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _source_program_operation_indices(report: dict[str, Any]) -> frozenset[int]:
    value = report.get("program_op_count_before")
    if isinstance(value, bool):
        return frozenset()
    try:
        count = int(value)
    except (TypeError, ValueError):
        return frozenset()
    if count <= 0:
        return frozenset()
    return frozenset(range(count))


def _kernel_program_metrics(records: tuple[dict[str, Any], ...]) -> dict[str, int]:
    kernel_records = tuple(record for record in records if _record_has_kernel_program(record))
    face_count = 0
    for record in kernel_records:
        faces = record.get("mesh_faces")
        if isinstance(faces, list):
            face_count += len(faces)
    return {
        "kernel_program_record_count": len(kernel_records),
        "kernel_program_face_count": face_count,
    }


def _density_cap_for_requirement(requirement: str, context: ShapeAuthoringContext) -> int | None:
    multiplier = context.density_multiplier
    if multiplier <= 0.0:
        return 0
    lowered = requirement.lower()
    if multiplier >= 1.0:
        return None
    if any(token in lowered for token in ("fastener", "bolt", "rivet")):
        return max(1, int(round(8 * multiplier)))
    if any(token in lowered for token in ("vent", "slat", "groove")):
        return max(1, int(round(5 * multiplier)))
    if any(token in lowered for token in ("corner", "guard", "bracket")):
        return max(2, int(round(6 * multiplier)))
    if any(token in lowered for token in ("trim", "rail", "band")):
        return max(1, int(round(4 * multiplier)))
    return None


def _filter_records_by_authoring_context(
    records: tuple[dict[str, Any], ...],
    context: ShapeAuthoringContext,
    *,
    preserved_source_operation_indices: frozenset[int] = frozenset(),
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    filtered_by_allow = 0
    filtered_by_density = 0
    preserved_source_record_count = 0
    per_requirement_counts: dict[str, int] = {}
    per_requirement_kept: dict[str, int] = {}
    selected_operation_counts: dict[str, int] = {}
    for record in records:
        requirement = _record_requirement(record)
        per_requirement_counts[requirement] = per_requirement_counts.get(requirement, 0) + 1
        cap = _density_cap_for_requirement(requirement, context)
        if cap == 0 and not _record_is_core(record):
            filtered_by_density += 1
            continue
        if _record_operation_index(record) in preserved_source_operation_indices:
            preserved_source_record_count += 1
            per_requirement_kept[requirement] = per_requirement_kept.get(requirement, 0) + 1
            selected.append(record)
            continue
        if not _record_matches_authoring(record, context):
            filtered_by_allow += 1
            continue
        kept = per_requirement_kept.get(requirement, 0)
        if cap is not None and kept >= cap and not _record_is_core(record):
            filtered_by_density += 1
            continue
        per_requirement_kept[requirement] = kept + 1
        selected.append(record)
    if not any(_record_is_core(record) for record in selected):
        for record in records:
            if _record_is_core(record):
                selected.insert(0, record)
                break
    for record in selected:
        op_key = str(
            record.get("v2_op")
            or record.get("v2_source_op")
            or record.get("component")
            or record.get("primitive_type")
            or "record"
        )
        selected_operation_counts[op_key] = selected_operation_counts.get(op_key, 0) + 1
    report = {
        "consumed": {
            "feature_allow": list(context.feature_allow),
            "feature_density": context.feature_density,
            "density_multiplier": context.density_multiplier,
            "repair_policy_use": context.repair_policy_use,
            "repair_policy_mode": context.repair_policy_mode,
            "repair_policy_allow": list(context.repair_policy_allow),
            "repair_policy_deny": list(context.repair_policy_deny),
            "repair_policy_feature_kinds": list(_repair_policy_requested_feature_kinds(context)),
            "surface_patterns": list(context.surface_patterns),
            "material_zones": list(context.material_zones),
            "edge_classes": list(context.edge_classes),
            "seam_classes": list(context.seam_classes),
            "integration_rules": list(context.integration_rules),
            "edge_treatment": context.edge_treatment,
            "style_pack": context.style_pack,
            "silhouette_profile": context.silhouette_profile,
            "structural_profile": context.structural_profile,
            "route_structure": context.route_structure,
            "style_intensity": context.style_intensity,
            "trim_density": context.trim_density,
            "greeble_density": context.greeble_density,
            "socket_count": len(context.socket_ids),
            "anchor_count": len(context.anchor_ids),
            "connection_count": context.connection_count,
            "route_connection_count": context.route_connection_count,
            "attach_connection_count": context.attach_connection_count,
            "support_connection_count": context.support_connection_count,
            "external_connection_count": context.external_connection_count,
            "branch_connection_count": context.branch_connection_count,
            "connection_layout_mode": context.connection_layout_mode,
            "connection_segment_count": context.connection_segment_count,
            "connection_path_complexity": context.connection_path_complexity,
            "child_module_count": context.child_module_count,
            "module_slot_count": context.module_slot_count,
            "nested_asset_count": context.nested_asset_count,
        },
        "record_count_before": len(records),
        "record_count_after": len(selected),
        "filtered_by_feature_allow": filtered_by_allow,
        "filtered_by_density": filtered_by_density,
        "preserved_source_record_count": preserved_source_record_count,
        "preserved_source_operation_indices": sorted(preserved_source_operation_indices),
        "records_by_requirement": dict(sorted(per_requirement_counts.items())),
        "kept_by_requirement": dict(sorted(per_requirement_kept.items())),
        "selected_records_by_operation": dict(sorted(selected_operation_counts.items())),
    }
    return tuple(selected), report


def _construction_graph_text_fragments(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, dict):
        fragments: list[str] = []
        for key in sorted(value.keys(), key=str):
            key_text = str(key).strip()
            if key_text:
                fragments.append(key_text)
            fragments.extend(_construction_graph_text_fragments(value[key]))
        return tuple(fragments)
    if isinstance(value, (list, tuple)):
        fragments = []
        for item in value:
            fragments.extend(_construction_graph_text_fragments(item))
        return tuple(fragments)
    return ()


def _unique_strings(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def _construction_graph_payload(asset_graph: AssetGraph) -> dict[str, Any]:
    recipe_family = _recipe_family_for_asset_graph(asset_graph)
    runtime = {
        "design_brief": {
            "brief": {
                "family": recipe_family,
                "asset_name": asset_graph.name,
            }
        }
    }
    payload = evaluate_construction_graph(_asset_stub(asset_graph), runtime)
    return payload if isinstance(payload, dict) else {}


def _construction_graph_nodes(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_nodes = payload.get("nodes") if isinstance(payload, dict) else None
    if not isinstance(raw_nodes, list):
        return ()
    return tuple(dict(node) for node in raw_nodes if isinstance(node, dict))


def _construction_graph_edges(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_edges = payload.get("edges") if isinstance(payload, dict) else None
    if not isinstance(raw_edges, list):
        return ()
    return tuple(dict(edge) for edge in raw_edges if isinstance(edge, dict))


def _construction_graph_node_tokens(node: dict[str, Any]) -> frozenset[str]:
    fragments: list[str] = []
    node_id = node.get("node_id")
    if isinstance(node_id, str):
        fragments.append(node_id)
    attributes = node.get("attributes")
    if isinstance(attributes, dict):
        fragments.extend(_construction_graph_text_fragments(attributes))
    return _context_token_set(tuple(fragments))


def _construction_graph_authoring_requests(
    nodes: tuple[dict[str, Any], ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[dict[str, Any], ...]]:
    feature_requests: list[str] = []
    surface_requests: list[str] = []
    node_reports: list[dict[str, Any]] = []
    for node in nodes:
        node_type = str(node.get("node_type") or "").strip()
        node_id = str(node.get("node_id") or "").strip()
        if not node_type or node_type == "primary_volume":
            continue
        tokens = _construction_graph_node_tokens(node)
        node_feature_requests: list[str] = []
        node_surface_requests: list[str] = []
        node_feature_requests.extend(_CONSTRUCTION_GRAPH_FEATURE_REQUESTS_BY_NODE_TYPE.get(node_type, ()))
        node_surface_requests.extend(_CONSTRUCTION_GRAPH_SURFACE_REQUESTS_BY_NODE_TYPE.get(node_type, ()))
        attributes = node.get("attributes")
        attributes = attributes if isinstance(attributes, dict) else {}
        if (
            node_type == "material_zone"
            and not (
                attributes.get("source") == "authored_source_field"
                and str(attributes.get("source_path") or "") in {"intent.materials", "surface.materials"}
            )
        ):
            node_feature_requests.append("construction_graph.panel_frame")
        if node_type == "panel" and tokens & _CONSTRUCTION_GRAPH_PANEL_REQUEST_TOKENS:
            node_feature_requests.append("construction_graph.panel_frame")
        for token_group, request in _CONSTRUCTION_GRAPH_TEXT_FEATURE_REQUESTS:
            if tokens & token_group:
                node_feature_requests.append(request)
        if (tokens & _AUTHORING_DECAL_TOKENS) and (tokens & _AUTHORING_SURFACE_ZONE_TOKENS):
            node_surface_requests.append("construction_graph.decal_zone")
        if (tokens & _AUTHORING_MATERIAL_TOKENS) and (tokens & _AUTHORING_SURFACE_ZONE_TOKENS):
            node_surface_requests.append("construction_graph.material_zone")
        if (tokens & _AUTHORING_WEAR_TOKENS) and (
            tokens & _AUTHORING_SURFACE_EDGE_TOKENS or tokens & _AUTHORING_GRIME_TOKENS
        ):
            node_surface_requests.append("construction_graph.edge_wear")
        node_feature_requests = list(_unique_strings(node_feature_requests))
        node_surface_requests = list(_unique_strings(node_surface_requests))
        if not node_feature_requests and not node_surface_requests:
            continue
        feature_requests.extend(node_feature_requests)
        surface_requests.extend(node_surface_requests)
        node_reports.append(
            {
                "node_id": node_id,
                "node_type": node_type,
                "matched_tokens": sorted(tokens),
                "feature_requests": node_feature_requests,
                "surface_requests": node_surface_requests,
            }
        )
    return (
        _unique_strings(feature_requests),
        _unique_strings(surface_requests),
        tuple(node_reports),
    )


def _construction_graph_edge_authoring_requests(
    edges: tuple[dict[str, Any], ...],
) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
    feature_requests: list[str] = []
    edge_reports: list[dict[str, Any]] = []
    for edge in edges:
        edge_type = str(edge.get("edge_type") or "").strip()
        if edge_type != "mirrors":
            continue
        source_id = str(edge.get("source_id") or "").strip()
        target_id = str(edge.get("target_id") or "").strip()
        if not source_id or not target_id:
            continue
        request = "construction_graph.mirror_instances"
        feature_requests.append(request)
        edge_reports.append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type,
                "feature_requests": [request],
                "surface_requests": [],
            }
        )
    return _unique_strings(feature_requests), tuple(edge_reports)


def _authoring_context_with_construction_graph(
    context: ShapeAuthoringContext,
    construction_graph: dict[str, Any],
) -> tuple[ShapeAuthoringContext, dict[str, Any]]:
    nodes = _construction_graph_nodes(construction_graph)
    edges = _construction_graph_edges(construction_graph)
    feature_requests, surface_requests, node_reports = _construction_graph_authoring_requests(nodes)
    edge_feature_requests, edge_reports = _construction_graph_edge_authoring_requests(edges)
    feature_requests = _unique_strings([*feature_requests, *edge_feature_requests])
    request_channel_values = _unique_strings([*feature_requests, *surface_requests])
    report = {
        "version": construction_graph.get("version"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types_present": list(construction_graph.get("node_types_present") or []),
        "consumed_node_count": len(node_reports),
        "consumed_nodes": [dict(item) for item in node_reports],
        "consumed_edge_count": len(edge_reports),
        "consumed_edges": [dict(item) for item in edge_reports],
        "feature_requests": list(feature_requests),
        "surface_requests": list(surface_requests),
        "request_channel": "surface_patterns",
    }
    if not request_channel_values:
        return context, report
    augmented_surface_patterns = _unique_strings([*context.surface_patterns, *request_channel_values])
    augmented_source_paths = _unique_strings([*context.source_paths, "construction_graph.nodes"])
    return (
        replace(
            context,
            surface_patterns=augmented_surface_patterns,
            source_paths=augmented_source_paths,
        ),
        report,
    )


def _record_authoring_tokens(record: dict[str, Any]) -> frozenset[str]:
    values: list[str] = []
    for key in ("v2_op", "v2_source_op", "v2_purpose", "part", "component", "region", "primitive_type"):
        value = record.get(key)
        if value not in (None, "", (), [], {}):
            values.append(str(value))
    tags = record.get("tags")
    if isinstance(tags, (list, tuple)):
        values.extend(str(tag) for tag in tags if str(tag))
    semantic_metadata = record.get("semantic_metadata")
    if isinstance(semantic_metadata, dict):
        shape_ir_v2 = semantic_metadata.get("shape_ir_v2")
        if isinstance(shape_ir_v2, dict):
            for key in ("v2_op", "v2_purpose", "operation_id"):
                value = shape_ir_v2.get(key)
                if value not in (None, "", (), [], {}):
                    values.append(str(value))
    return _context_token_set(tuple(values))


def _construction_graph_request_matches_entry(
    request: str,
    entry: dict[str, Any],
) -> bool:
    op = str(entry.get("op") or "")
    tokens = set(entry.get("tokens") or ())
    if request == "construction_graph.trim_band":
        return op == "op.trim_band" or {"trim", "band"} <= tokens
    if request == "construction_graph.fastener_grid":
        return op == "op.fastener_grid" or {"fastener", "grid"} <= tokens
    if request == "construction_graph.vent_slats":
        return op == "op.vent_slats" or (("vent" in tokens or "vents" in tokens) and ("slat" in tokens or "slats" in tokens))
    if request == "construction_graph.panel_frame":
        return op == "op.panel_frame" or {"panel", "frame"} <= tokens
    if request == "construction_graph.recessed_panel":
        return op == "op.inset" or "inset" in tokens or "recessed" in tokens or "recess" in tokens
    if request == "construction_graph.panel_groove":
        return op == "op.cut_panel_line" or "groove" in tokens or "cutline" in tokens or "seamline" in tokens
    if request == "construction_graph.corner_guard":
        return op == "op.corner_guard_set" or {"corner", "guard"} <= tokens
    if request == "construction_graph.support_bracket":
        return op == "op.bracket" or "support_bracket" in tokens or "bracket" in tokens or "gusset" in tokens
    if request == "construction_graph.mount_plate":
        return op == "op.mount_plate" or {"mount", "plate"} <= tokens
    if request == "construction_graph.latch_plate":
        return ("latch" in tokens or "lock" in tokens or "clasp" in tokens) and (
            op == "op.mount_plate" or "plate" in tokens
        )
    if request == "construction_graph.hinge_mount_plate":
        entry_tokens = _context_token_set(
            (
                str(entry.get("part") or ""),
                str(entry.get("component") or ""),
                str(entry.get("purpose") or ""),
                op,
            )
        )
        return op == "solid.hinge" or "hinge" in entry_tokens or "hinges" in entry_tokens or "knuckle" in entry_tokens
    if request == "construction_graph.pull_handle":
        return op in {"sop.polywire", "solid.handle"} and (
            "handle" in tokens or "pull" in tokens or "grip" in tokens
        )
    if request == "construction_graph.conduit_run":
        return op in {"sop.polywire", "solid.tube", "solid.curved_tube"} and (
            "conduit" in tokens or "cable" in tokens or "pipe" in tokens or "wire" in tokens
        )
    if request == "construction_graph.socket_port":
        return op == "op.socket" or "socket" in tokens or "port" in tokens
    if request == "construction_graph.chip_edges":
        return op == "op.chip_edges" or {"chip", "edge"} <= tokens or {"chip", "edges"} <= tokens
    if request == "construction_graph.grime_mask":
        return op == "op.grime_mask" or "grime" in tokens or "dirty" in tokens or "stain" in tokens
    if request == "construction_graph.weld_seam":
        return op == "op.weld_seam" or bool(tokens & _AUTHORING_WELD_TOKENS)
    if request == "construction_graph.mirror_instances":
        return op == "op.mirror" or "mirror" in tokens or "mirrored" in tokens or "reflection" in tokens
    request_tokens = set(_context_token_set((request,))) - {"construction", "graph"}
    return bool(request_tokens and tokens & request_tokens)


def _construction_graph_surface_request_matches_entry(
    request: str,
    entry: dict[str, Any],
) -> bool:
    op = str(entry.get("op") or "")
    tokens = set(entry.get("tokens") or ())
    if request == "construction_graph.decal_zone":
        return (
            op == "sop.polyextrude"
            and bool(tokens & _AUTHORING_DECAL_TOKENS)
            and bool(tokens & _AUTHORING_SURFACE_ZONE_TOKENS)
        ) or (bool(tokens & _AUTHORING_DECAL_TOKENS) and bool(tokens & _AUTHORING_SURFACE_ZONE_TOKENS))
    if request == "construction_graph.material_zone":
        return (
            op in {"sop.polyextrude", "sop.polybevel", "op.panel_frame", "op.trim_band"}
            and bool(tokens & _AUTHORING_MATERIAL_TOKENS)
            and bool(tokens & _AUTHORING_SURFACE_ZONE_TOKENS)
        ) or (bool(tokens & _AUTHORING_MATERIAL_TOKENS) and bool(tokens & _AUTHORING_SURFACE_ZONE_TOKENS))
    if request == "construction_graph.edge_wear":
        wear_ops = {"op.chip_edges", "op.scratch_mask", "op.dent_mask", "op.grime_mask"}
        return op in wear_ops or (
            bool(tokens & (_AUTHORING_WEAR_TOKENS | _AUTHORING_GRIME_TOKENS))
            and (bool(tokens & _AUTHORING_SURFACE_EDGE_TOKENS) or bool(tokens & {"chip", "chips", "scratch", "dent"}))
        )
    request_tokens = set(_context_token_set((request,))) - {"construction", "graph"}
    return bool(request_tokens and tokens & request_tokens)


def _construction_graph_request_execution(
    requests: list[str],
    *,
    program_tokens: list[dict[str, Any]],
    record_tokens: list[dict[str, Any]],
    matcher: Any,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    execution: list[dict[str, Any]] = []
    executed: list[str] = []
    unresolved: list[str] = []
    for request in requests:
        matched_program = [
            {
                "op": item["op"],
                "target": item["target"],
                "purpose": item["purpose"],
            }
            for item in program_tokens
            if matcher(request, item)
        ]
        matched_records = [
            {
                "op": item["op"],
                "part": item["part"],
                "component": item["component"],
                "purpose": item["purpose"],
            }
            for item in record_tokens
            if matcher(request, item)
        ]
        if matched_records:
            status = "executed"
            executed.append(request)
        elif matched_program:
            status = "lowered_pending_record"
            unresolved.append(request)
        else:
            status = "unresolved"
            unresolved.append(request)
        execution.append(
            {
                "request": request,
                "status": status,
                "matched_program_ops": matched_program,
                "matched_records": matched_records,
            }
        )
    return execution, list(_unique_strings(executed)), list(_unique_strings(unresolved))


def _construction_graph_repair_route(request: str) -> dict[str, Any]:
    route = _CONSTRUCTION_GRAPH_REPAIR_ROUTES.get(request)
    if not isinstance(route, dict):
        return {
            "executor": "",
            "target_ir": "",
            "actions": [],
            "status": "no_registered_repair_action",
        }
    return {
        "executor": "lathe.shape_program_driver",
        "status": "registered",
        "request": request,
        "repair_channel": "construction_graph_authoring",
        "actions": list(route.get("actions") or []),
        "target_ir": str(route.get("target_ir") or "ShapeProgram"),
        "lowered_operation": str(route.get("lowered_operation") or ""),
        "surface_role": str(route.get("surface_role") or ""),
    }


def _construction_graph_execution_report(
    report: dict[str, Any],
    *,
    program: ShapeProgram,
    selected_records: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    enriched = dict(report)
    raw_feature_requests = report.get("feature_requests")
    feature_requests = (
        [str(item) for item in raw_feature_requests if str(item)]
        if isinstance(raw_feature_requests, list)
        else []
    )
    raw_surface_requests = report.get("surface_requests")
    surface_requests = (
        [str(item) for item in raw_surface_requests if str(item)]
        if isinstance(raw_surface_requests, list)
        else []
    )
    program_tokens = [
        {
            "op": op.op,
            "target": op.target,
            "purpose": op.purpose,
            "tokens": _shape_op_tokens(op),
        }
        for op in program.ops
    ]
    record_tokens = [
        {
            "op": str(record.get("v2_op") or record.get("v2_source_op") or ""),
            "part": str(record.get("part") or ""),
            "component": str(record.get("component") or ""),
            "purpose": str(record.get("v2_purpose") or ""),
            "tokens": _record_authoring_tokens(record),
        }
        for record in selected_records
    ]
    execution, executed, unresolved = _construction_graph_request_execution(
        feature_requests,
        program_tokens=program_tokens,
        record_tokens=record_tokens,
        matcher=_construction_graph_request_matches_entry,
    )
    surface_execution, surface_executed, surface_unresolved = _construction_graph_request_execution(
        surface_requests,
        program_tokens=program_tokens,
        record_tokens=record_tokens,
        matcher=_construction_graph_surface_request_matches_entry,
    )
    enriched["feature_request_execution"] = execution
    enriched["executed_feature_requests"] = executed
    enriched["unresolved_feature_requests"] = unresolved
    enriched["surface_request_execution"] = surface_execution
    enriched["executed_surface_requests"] = surface_executed
    enriched["unresolved_surface_requests"] = surface_unresolved
    return enriched


def _construction_graph_unresolved_diagnostics(report: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    execution = report.get("feature_request_execution")
    if not isinstance(execution, list):
        return ()
    diagnostics: list[dict[str, Any]] = []
    for item in execution:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "")
        if status == "executed":
            continue
        request = str(item.get("request") or "")
        if not request:
            continue
        matched_program_ops = item.get("matched_program_ops")
        matched_program_ops = matched_program_ops if isinstance(matched_program_ops, list) else []
        repair_route = _construction_graph_repair_route(request)
        repair_actions = list(repair_route.get("actions") or [])
        diagnostics.append(
            {
                "code": "construction_graph_feature_request_unresolved",
                "name": "construction_graph_feature_request_unresolved",
                "request": request,
                "status": status or "unresolved",
                "source": "construction_graph",
                "reason": (
                    "request matched ShapeIR v2 program op(s) but no selected v1 record survived lowering/filtering"
                    if status == "lowered_pending_record"
                    else "request was not matched by any ShapeIR v2 program op or selected v1 record"
                ),
                "repair_route": repair_route,
                "repair_actions": repair_actions,
                "suggested_repairs": repair_actions,
                "lowered_operation": repair_route.get("lowered_operation", ""),
                "matched_program_ops": [dict(op) for op in matched_program_ops if isinstance(op, dict)],
            }
        )
    return tuple(diagnostics)


def _construction_graph_unresolved_surface_diagnostics(report: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    execution = report.get("surface_request_execution")
    if not isinstance(execution, list):
        return ()
    diagnostics: list[dict[str, Any]] = []
    for item in execution:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "")
        if status == "executed":
            continue
        request = str(item.get("request") or "")
        if not request:
            continue
        matched_program_ops = item.get("matched_program_ops")
        matched_program_ops = matched_program_ops if isinstance(matched_program_ops, list) else []
        repair_route = _construction_graph_repair_route(request)
        repair_actions = list(repair_route.get("actions") or [])
        diagnostics.append(
            {
                "code": "construction_graph_surface_request_unresolved",
                "name": "construction_graph_surface_request_unresolved",
                "request": request,
                "status": status or "unresolved",
                "source": "construction_graph",
                "reason": (
                    "surface request matched ShapeIR v2 program op(s) but no selected v1 record survived lowering/filtering"
                    if status == "lowered_pending_record"
                    else "surface request was not matched by any ShapeIR v2 program op or selected v1 record"
                ),
                "repair_route": repair_route,
                "repair_actions": repair_actions,
                "suggested_repairs": repair_actions,
                "lowered_operation": repair_route.get("lowered_operation", ""),
                "matched_program_ops": [dict(op) for op in matched_program_ops if isinstance(op, dict)],
            }
        )
    return tuple(diagnostics)


def _grammar_payload(
    asset_graph: AssetGraph,
    *,
    construction_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recipe_family = _recipe_family_for_asset_graph(asset_graph)
    graph_nodes = (
        [dict(node) for node in _construction_graph_nodes(construction_graph)]
        if isinstance(construction_graph, dict)
        else []
    )
    runtime = {
        "design_brief": {
            "brief": {
                "family": recipe_family,
                "asset_name": asset_graph.name,
            }
        },
        "construction_graph": {"nodes": graph_nodes},
    }
    return evaluate_grammar_lowering(_asset_stub(asset_graph), runtime)


def compile_grammar_program_candidate(
    asset_graph: AssetGraph,
    template_shape_ir: ShapeIR,
    *,
    geometry_kernel: Any | None = None,
    augment_template: bool = False,
    materialize_selected_records: bool = True,
) -> tuple[ShapeIR, dict[str, Any]] | None:
    """Return an executable ShapeIR candidate from grammar lowering, if any."""
    construction_graph = _construction_graph_payload(asset_graph)
    authoring_context, construction_graph_report = _authoring_context_with_construction_graph(
        authoring_context_from_asset_graph(asset_graph),
        construction_graph,
    )
    payload = _grammar_payload(asset_graph, construction_graph=construction_graph)
    program = _shape_program_from_payload(payload.get("shape_program", {}))
    program, program_authoring_report = _apply_authoring_context_to_program(
        program,
        authoring_context,
    )
    program_summary = _shape_program_summary(program)
    adapter = lower_to_v1(
        program,
        geometry_kernel=geometry_kernel,
        materialize_output=False,
    )
    selected_records, authoring_report = _filter_records_by_authoring_context(
        tuple(dict(record) for record in adapter.v1_records),
        authoring_context,
        preserved_source_operation_indices=_source_program_operation_indices(program_authoring_report),
    )
    adapter_kernel_metrics = _kernel_program_metrics(tuple(dict(record) for record in adapter.v1_records))
    synthesized_primary_body = False
    selected_before_augmentation = selected_records
    if augment_template:
        selected_records = tuple(record for record in selected_records if not _record_is_core(record))
        if not selected_records:
            return None
    elif selected_records and not _records_have_primary_body_shell(selected_records):
        selected_records = (
            _synthesized_primary_body_record(template_shape_ir, program),
            *selected_records,
        )
        synthesized_primary_body = True
    diagnostics = [dict(item) for item in adapter.diagnostics]
    kernel_materialization_mode = "source_records"
    deferred_kernel_record_count = 0
    if geometry_kernel is not None and selected_records and materialize_selected_records:
        kernel_materialization_mode = "per_record_kernel_import"
        kernel_adapter = materialize_v1_records_with_kernel_imports(
            selected_records,
            program=program,
            geometry_kernel=geometry_kernel,
        )
        selected_records = tuple(dict(record) for record in kernel_adapter.v1_records)
        diagnostics.extend(dict(item) for item in kernel_adapter.diagnostics)
    elif geometry_kernel is not None and selected_records:
        kernel_materialization_mode = "deferred_to_shape_ir_kernel_program"
        deferred_kernel_record_count = len(selected_records)
    selected_kernel_metrics = _kernel_program_metrics(selected_records)
    construction_graph_report = _construction_graph_execution_report(
        construction_graph_report,
        program=program,
        selected_records=selected_records,
    )
    diagnostics.extend(_construction_graph_unresolved_diagnostics(construction_graph_report))
    diagnostics.extend(_construction_graph_unresolved_surface_diagnostics(construction_graph_report))

    primitives: list[ShapePrimitive] = list(template_shape_ir.primitives) if augment_template else []
    regions: list[ShapeRegion] = list(template_shape_ir.regions) if augment_template else []

    for index, record in enumerate(selected_records):
        primitive, diagnostic = _primitive_from_record(dict(record), index)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        assert primitive is not None
        primitives.append(primitive)
        regions.append(_region_from_primitive(primitive, len(regions)))

    if not primitives:
        return None

    primitives_used = sorted({primitive.component or primitive.primitive_type for primitive in primitives})
    primitive_count = len(primitives)
    grammar_primitive_count = len(selected_records)
    assessment = dict(template_shape_ir.assessment)
    assessment.update(
        {
            "primitive_count": primitive_count,
            "grammar_program_executed": True,
            "grammar_program_augmented_template": bool(augment_template),
            "grammar_program_version": GRAMMAR_PROGRAM_EXECUTION_VERSION,
            "grammar_lowering_version": GRAMMAR_LOWERING_VERSION,
            "grammar_program_v1_record_count": len(adapter.v1_records),
            "grammar_program_primitive_count": grammar_primitive_count,
            "grammar_program_authoring_record_count": len(selected_records),
            "grammar_program_kernel_record_count": selected_kernel_metrics["kernel_program_record_count"],
            "grammar_program_kernel_face_count": selected_kernel_metrics["kernel_program_face_count"],
            "grammar_program_deferred_kernel_record_count": deferred_kernel_record_count,
            "grammar_program_synthesized_primary_body": synthesized_primary_body,
            "grammar_program_diagnostic_count": len(diagnostics),
            "grammar_program_unsupported_ops": list(adapter.unsupported_ops),
            "feature_density": max(
                float(assessment.get("feature_density", 0.0) or 0.0),
                min(1.0, 0.35 + primitive_count * 0.018),
            ),
            "feature_coherence": max(float(assessment.get("feature_coherence", 0.0) or 0.0), 0.62),
        }
    )
    signature = dict(template_shape_ir.signature)
    signature["grammar_program_execution"] = {
        "version": GRAMMAR_PROGRAM_EXECUTION_VERSION,
        "source": GRAMMAR_LOWERING_VERSION,
        "family": payload.get("family"),
        "shape_program_summary": program_summary,
        "source_shape_program_summary": payload.get("shape_program_summary", {}),
        "v1_record_count": len(adapter.v1_records),
        "v1_kernel_program_record_count": adapter_kernel_metrics["kernel_program_record_count"],
        "v1_kernel_program_face_count": adapter_kernel_metrics["kernel_program_face_count"],
        "executed_primitive_count": grammar_primitive_count,
        "executed_kernel_program_record_count": selected_kernel_metrics["kernel_program_record_count"],
        "executed_kernel_program_face_count": selected_kernel_metrics["kernel_program_face_count"],
        "deferred_kernel_program_record_count": deferred_kernel_record_count,
        "synthesized_primary_body": synthesized_primary_body,
        "diagnostic_count": len(diagnostics),
        "unsupported_ops": list(adapter.unsupported_ops),
        "authoring_context": authoring_context.to_dict(),
        "construction_graph_consumption": construction_graph_report,
        "authoring_consumption": authoring_report,
        "authoring_program": program_authoring_report,
        "augmentation": {
            "enabled": bool(augment_template),
            "template_primitive_count": len(template_shape_ir.primitives),
            "selected_record_count_before": len(selected_before_augmentation),
            "selected_record_count_after": len(selected_records),
            "filtered_core_record_count": max(
                0,
                len(selected_before_augmentation)
                - len(selected_records)
                + (1 if synthesized_primary_body else 0),
            ),
            "synthesized_primary_body": synthesized_primary_body,
        },
        "selected_record_materialization": {
            "mode": kernel_materialization_mode,
            "requested": bool(geometry_kernel is not None and selected_records),
            "per_record_kernel_import": bool(
                geometry_kernel is not None
                and selected_records
                and materialize_selected_records
            ),
            "deferred_to_shape_ir_kernel_program": deferred_kernel_record_count > 0,
            "deferred_record_count": deferred_kernel_record_count,
        },
    }
    shape_ir = ShapeIR(
        asset_name=template_shape_ir.asset_name,
        family=asset_graph.family,
        blueprint_id=(
            f"{template_shape_ir.blueprint_id}:grammar_program_augmented"
            if augment_template
            else f"{template_shape_ir.blueprint_id}:grammar_program"
        ),
        symmetry_axis=template_shape_ir.symmetry_axis,
        units=template_shape_ir.units,
        primitives=primitives,
        regions=regions,
        primitives_used=primitives_used,
        part_graph=list(template_shape_ir.part_graph),
        signature=signature,
        assessment=assessment,
    )
    report = {
        "version": GRAMMAR_PROGRAM_EXECUTION_VERSION,
        "source": GRAMMAR_LOWERING_VERSION,
        "family": payload.get("family"),
        "shape_program_summary": program_summary,
        "source_shape_program_summary": payload.get("shape_program_summary", {}),
        "v1_record_count": len(adapter.v1_records),
        "v1_kernel_program_record_count": adapter_kernel_metrics["kernel_program_record_count"],
        "v1_kernel_program_face_count": adapter_kernel_metrics["kernel_program_face_count"],
        "authoring_record_count": len(selected_records),
        "executed_primitive_count": grammar_primitive_count,
        "executed_kernel_program_record_count": selected_kernel_metrics["kernel_program_record_count"],
        "executed_kernel_program_face_count": selected_kernel_metrics["kernel_program_face_count"],
        "deferred_kernel_program_record_count": deferred_kernel_record_count,
        "synthesized_primary_body": synthesized_primary_body,
        "diagnostics": diagnostics,
        "unsupported_ops": list(adapter.unsupported_ops),
        "authoring_context": authoring_context.to_dict(),
        "construction_graph_consumption": construction_graph_report,
        "authoring_consumption": authoring_report,
        "authoring_program": program_authoring_report,
        "augmentation": signature["grammar_program_execution"]["augmentation"],
        "selected_record_materialization": signature["grammar_program_execution"][
            "selected_record_materialization"
        ],
        "geometry_kernel": getattr(geometry_kernel, "name", None),
        "execution_state": "executed",
    }
    return shape_ir, report
