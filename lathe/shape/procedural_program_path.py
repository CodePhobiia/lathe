"""Procedural-synthesizer shape backend dispatch.

Mirrors :mod:`lathe.shape.mesh_program_path` but consumes the
procedural synthesizer's :class:`SynthesisResult` instead of a
parsed ``mesh_program{}`` AST. Lowers the synthesizer's ShapeIR v2
:class:`ShapeProgram` through ``lower_to_v1`` to dict-form v1 records,
materializes those into :class:`ShapePrimitive` instances, wraps in a
:class:`ShapeIR`, and feeds the same exact-solid compilation chain.

Output is a scaffold-shaped dict identical in structure to what
:func:`lathe.scaffold_compiler.compile_scaffold_candidates` and
:func:`lathe.shape.mesh_program_path.compile_mesh_program_candidate`
return — so the rest of the shape backend (provider mux, conformance
fit, bundle assembly) consumes it unchanged.

This is the architectural placement called out by
``docs/asset-quality/procedural-synthesizer-architecture-correction.md``:
the synthesizer feeds real geometry, not a validate-stage report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from ..asset_graph import AssetGraph
from ..asset_quality.procedural_synthesizer import SynthesisResult
from ..asset_quality.shape_ir_v2 import _primitive_from_v1_record, lower_to_v1
from ..exact_solids import compile_explicit_surface_mesh
from ..fidelity import infer_fidelity_profile
from ..geometry import resolve_geometry_kernel
from ..mesh_finalize import finalize_mesh_ir
from ..scaffold_compiler import _game_pipeline_hints, _make_color
from ..shape_ir import ShapeIR, ShapePrimitive, ShapeRegion

__all__ = [
    "compile_procedural_program_candidate",
    "runtime_from_asset",
    "synthesizer_eligible",
]


def _asset_family_token(asset: dict[str, Any]) -> str | None:
    """Return the asset's resolved family name (or None).

    Looks in priority order:
      - asset.build.shape.procedural.brief.family   (procedural brief override)
      - asset.intent.family                          (intent declaration)
      - asset.family                                 (legacy top-level)
      - asset.from                                   (canonical ``from <family>`` declaration)
    """
    if not isinstance(asset, dict):
        return None
    shape_cfg = asset.get("build", {}).get("shape", {}) if isinstance(asset.get("build"), dict) else {}
    procedural = shape_cfg.get("procedural") if isinstance(shape_cfg, dict) else None
    if isinstance(procedural, dict):
        brief = procedural.get("brief")
        if isinstance(brief, dict):
            family = brief.get("family")
            if isinstance(family, str) and family:
                return family
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if isinstance(intent, dict):
        family = intent.get("family")
        if isinstance(family, str) and family:
            return family
    family = asset.get("family")
    if isinstance(family, str) and family:
        return family
    from_family = asset.get("from")
    if isinstance(from_family, str) and from_family:
        return from_family
    return None


def _family_alias_exists(family: str) -> bool:
    """Return True iff a FamilyAlias JSON is registered for ``family``.

    Accepts either the canonical family stem (``industrial_crate``) or
    the ``from``-clause form (``industrial_crate_family``); the latter
    is the .lth source convention. The alias registry is keyed by the
    stem (``family_id`` in the JSON), so we try both forms.

    Loaded lazily — the procedural_synthesizer package caches the
    alias pack mapping at import-time, so this is O(1) after first
    call. Returns False when the alias directory is missing or no
    matching family is registered.
    """
    from ..asset_quality.procedural_synthesizer.knowledge_loader import (
        load_all_alias_packs,
    )

    try:
        packs = load_all_alias_packs()
    except Exception:
        return False
    if family in packs:  # no-family-dispatch: membership check against the declarative FamilyAlias pack registry — this IS the metadata-only family-to-(style/policies/domain) lookup the procedural synthesizer was built to enable; no behavior is keyed on the family name itself, only on the alias's resolved style + policy + domain
        return True
    # Source convention strips the ``_family`` suffix when declaring an
    # alias JSON; accept the stem form too so ``from foo_family`` hits
    # the ``foo`` alias.
    if family.endswith("_family"):
        stem = family[: -len("_family")]
        if stem in packs:  # no-family-dispatch: same registry, stem form
            return True
    return False


def _asset_has_authored_parts(asset: dict[str, Any]) -> bool:
    """Return True iff asset.intent.parts is a non-empty list."""
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if not isinstance(intent, dict):
        return False
    parts = intent.get("parts")
    return isinstance(parts, list) and bool(parts)


def synthesizer_eligible(
    asset: dict[str, Any], runtime_config: dict[str, Any] | None
) -> bool:
    """Return True iff the procedural synthesizer can produce a program.

    Per Sprint 0 Phase B capstone (post-Phase A.1 + S0-3), eligibility
    now widens beyond just-authored-construction-graph. The synthesizer
    can compose a default skeleton from a FamilyAlias + authored parts
    list. Auto-graph synthesis happens in ``runtime_from_asset``.

    Eligibility requires (in priority order):
      1. No ``mesh_program{}`` block in source (mesh_program takes
         precedence — it is the explicit authored procedural path).
      2. EITHER an authored ``construction_graph`` with at least one
         node (under ``asset.build.shape.procedural.construction_graph``
         OR ``asset.intent.construction_graph``),
         OR a registered FamilyAlias + authored ``asset.intent.parts``
         list. The latter route triggers auto-graph synthesis from
         parts in ``runtime_from_asset``.
    """
    shape_cfg = asset.get("build", {}).get("shape") if isinstance(asset, dict) else None
    if isinstance(shape_cfg, dict):
        # mesh_program takes precedence — never displace it.
        mesh_program = shape_cfg.get("mesh_program")
        if isinstance(mesh_program, dict) and mesh_program.get("statements"):
            return False
        # Procedural block on the build.shape — preferred location.
        procedural = shape_cfg.get("procedural")
        if isinstance(procedural, dict):
            cg = procedural.get("construction_graph")
            if isinstance(cg, dict):
                nodes = cg.get("nodes")
                if isinstance(nodes, list) and nodes:
                    return True
    # Authored construction_graph at asset.intent.construction_graph.
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if isinstance(intent, dict):
        cg = intent.get("construction_graph")
        if isinstance(cg, dict):
            nodes = cg.get("nodes")
            if isinstance(nodes, list) and nodes:
                return True
    # Sprint 0 capstone: aliased family + authored parts → auto-graph
    # synthesis. The asset enters the synthesizer with a default
    # primary_volume derived from intent.parts.
    family = _asset_family_token(asset)
    if family and _family_alias_exists(family) and _asset_has_authored_parts(asset):
        return True
    return False


_DEFAULT_PRIMARY_VOLUME_DIMENSIONS_CM: dict[str, float] = {"x": 30.0, "y": 30.0, "z": 30.0}


# Minimum defaults per NODE_TYPE so auto-graph nodes survive the
# procedural synthesizer's Stage 4 typed-attribute validation. The
# values here are deliberately conservative — they exist to let the
# node survive validation and reach the generator stage; per-asset
# refinement (specific widths, axes, styles) happens via explicit
# construction_graph authoring or via policy expansion overrides.
# Sphere isn't here because primary_volume's auto attributes already
# pick rounded_box; node types with no entry here pass through with
# empty attributes (and will be dropped at Stage 4 — that's fine, the
# policy provides its own canonical nodes).
_NODE_TYPE_AUTO_DEFAULTS: dict[str, dict[str, Any]] = {
    "panel": {"plane": "xy", "width_cm": 14.0, "height_cm": 10.0, "thickness_cm": 0.4},
    "frame": {
        "plane": "xy",
        "outer_width_cm": 14.0,
        "outer_height_cm": 14.0,
        "member_thickness_cm": 0.6,
        "protrusion_cm": 0.4,
    },
    "trim": {
        "edge_axis": "x",
        "length_cm": 14.0,
        "cross_section_width_cm": 1.0,
        "cross_section_height_cm": 0.4,
    },
    "fastener": {
        "kind": "rivet",
        "head_radius_cm": 0.3,
        "head_height_cm": 0.4,
        "shaft_radius_cm": 0.15,
        "shaft_length_cm": 0.6,
    },
    "handle": {"style": "bar", "length_cm": 14.0, "grip_radius_cm": 0.8, "axis": "x"},
    "inset": {
        "depth_axis": "z",
        "depth_cm": 0.4,
        "width_cm": 6.0,
        "height_cm": 4.0,
    },
    "rail": {"axis": "x", "length_cm": 14.0, "radius_cm": 0.4, "cross_section": "round"},
    "socket": {"depth_axis": "x", "depth_cm": 1.0, "radius_cm": 0.6, "profile": "round"},
    "mount": {"style": "flat_pad", "width_cm": 4.0, "depth_cm": 4.0, "height_cm": 0.6},
    "guard": {
        "style": "perimeter_rail",
        "width_cm": 16.0,
        "height_cm": 6.0,
        "depth_cm": 16.0,
        "bar_radius_cm": 0.3,
        "bar_count": 4,
        "axis": "y",
    },
    "hinge": {
        "style": "butt",
        "leaf_width_cm": 3.0,
        "leaf_height_cm": 6.0,
        "leaf_thickness_cm": 0.3,
        "barrel_radius_cm": 0.4,
        "pin_axis": "y",
    },
    "latch": {
        "style": "hasp",
        "plate_width_cm": 4.0,
        "plate_height_cm": 3.0,
        "plate_thickness_cm": 0.3,
        "arm_length_cm": 2.0,
        "arm_radius_cm": 0.3,
    },
    "bracket": {
        "profile": "l_bracket",
        "leg_length_cm": 4.0,
        "leg_width_cm": 2.0,
        "thickness_cm": 0.4,
    },
    "vent": {"style": "horizontal_slat", "width_cm": 8.0, "height_cm": 6.0, "depth_cm": 1.0},
    "conduit": {"kind": "cable", "radius_cm": 0.3, "length_cm": 10.0},
    "weld": {"kind": "fillet", "bead_radius_cm": 0.2, "length_cm": 5.0},
    "material_zone": {"material_hint": "painted_steel"},
    "decal_zone": {
        "decal_intent": "label",
        "size_cm": [8.0, 4.0],
        "host_face_axis": "z",
    },
    "wear_zone": {"wear_kind": "handled", "intensity": "moderate", "coverage_fraction": 0.3},
}


def _auto_attributes_for(node_type: str, node_id: str) -> dict[str, Any]:
    """Return minimum default attributes for an auto-graph node.

    Zone-typed nodes get their ``zone_id`` from the node's id so they
    don't collide on the synthesizer's zone-merge pass. Everything else
    is the per-NODE_TYPE default table above (or empty when no entry
    is present — the node may then fail Stage 4 and be dropped, which
    is fine because the policy supplies canonical equivalents).
    """
    base = _NODE_TYPE_AUTO_DEFAULTS.get(node_type)
    if base is None:
        return {}
    attrs = dict(base)
    if node_type in ("material_zone", "decal_zone", "wear_zone"):
        attrs.setdefault("zone_id", node_id)
    return attrs


# Kind→aspect ratios for the bare-scalar ``scale`` interpretation. The
# bare number is treated as the LONGEST dimension (in cm); the aspect
# tuple maps that into (x, y, z) by relative size. Kind is a generic
# asset-class taxonomy (not family) — env_module covers doors, walls,
# fences, gates; hard_surface_prop covers crates, containers, boxes;
# etc. Without this, every asset becomes a near-cube and doors look
# like crates.
#
# Convention: ``+Z is up`` (so the longest axis of a door is Z, height).
_KIND_ASPECT: dict[str, tuple[float, float, float]] = {
    # Doors / walls / panels — flat in Y (depth), tall in Z, mid in X.
    "env_module": (0.45, 0.04, 1.0),
    # Wall-mounted / mounted modules — flat plate.
    "wall_module": (1.0, 0.04, 0.6),
    # Crates / containers / shipping props — rectangular box.
    "hard_surface_prop": (1.0, 0.65, 0.55),
    "shipping_prop": (1.0, 0.65, 0.55),
    # Gameplay objects (pickups, tools) — squarish.
    "gameplay_object": (1.0, 0.7, 0.6),
    "interactable": (1.0, 0.7, 0.6),
    # Vehicles / machinery — long in X, lower in Z.
    "vehicle": (1.0, 0.55, 0.45),
    "machinery": (1.0, 0.7, 0.75),
    # Furniture / fixtures — squarish with some depth.
    "furniture": (1.0, 0.7, 0.85),
    "fixture": (0.7, 0.7, 1.0),
}
_DEFAULT_ASPECT: tuple[float, float, float] = (1.0, 0.7, 0.7)


def _aspect_for_kind(kind: Any) -> tuple[float, float, float]:
    """Return per-axis aspect ratios for a bare-scalar ``scale``.

    Falls back to a generic mildly-rectangular default when ``kind`` is
    missing or unknown.
    """
    if isinstance(kind, str) and kind in _KIND_ASPECT:
        return _KIND_ASPECT[kind]
    return _DEFAULT_ASPECT


def _scale_to_dimensions(
    scale_value: Any, kind: Any = None
) -> dict[str, float]:
    """Translate an authored ``scale`` field into per-axis dimensions.

    Accepts:
      - bare numbers (treated as uniform cm) — uses ``kind``-based aspect
      - strings like ``"0.9m"`` (parsed to 90.0 cm) — uses ``kind`` aspect
      - dicts already shaped as dimensions_cm — used directly

    When ``kind`` is provided and matches an entry in ``_KIND_ASPECT``,
    the bare scalar is interpreted as the longest dimension and split
    into (x, y, z) via the kind's aspect ratio. This is how doors stop
    being cubes: ``kind="env_module"`` + ``scale="2.1m"`` becomes
    95 × 8 × 210 cm rather than the previous 210 × 147 × 147 cm cube.

    Returns the default 30cm cube when nothing parseable is present.
    """
    aspect = _aspect_for_kind(kind)
    if isinstance(scale_value, dict):
        # Two shapes accepted:
        #   1. explicit dimensions: {x, y, z} or {width_cm, height_cm, depth_cm}
        #   2. normalized unit form: {type: "unit", value: N, unit: "m"|"cm"}
        if any(k in scale_value for k in ("x", "y", "z", "width_cm", "height_cm", "depth_cm")):
            return {
                "x": float(scale_value.get("x") or scale_value.get("width_cm") or 30.0),
                "y": float(scale_value.get("y") or scale_value.get("height_cm") or 30.0),
                "z": float(scale_value.get("z") or scale_value.get("depth_cm") or 30.0),
            }
        if scale_value.get("type") == "unit":
            try:
                value = float(scale_value.get("value", 0.0))
                unit = str(scale_value.get("unit", "cm")).lower()
                if unit == "m":
                    d = value * 100.0
                elif unit == "cm":
                    d = value
                elif unit == "mm":
                    d = value / 10.0
                else:
                    d = value  # unknown unit — treat as cm
                if d > 0:
                    return {"x": d * aspect[0], "y": d * aspect[1], "z": d * aspect[2]}
            except (TypeError, ValueError):
                pass
    if isinstance(scale_value, (int, float)):
        d = float(scale_value)
        return {"x": d * aspect[0], "y": d * aspect[1], "z": d * aspect[2]}
    if isinstance(scale_value, str):
        text = scale_value.strip().lower()
        try:
            if text.endswith("m"):
                value_m = float(text[:-1])
                d = value_m * 100.0
                return {"x": d * aspect[0], "y": d * aspect[1], "z": d * aspect[2]}
            if text.endswith("cm"):
                d = float(text[:-2])
                return {"x": d * aspect[0], "y": d * aspect[1], "z": d * aspect[2]}
        except ValueError:
            pass
    return dict(_DEFAULT_PRIMARY_VOLUME_DIMENSIONS_CM)


def _infer_position_cm(
    part_name: str, dimensions: dict[str, float]
) -> tuple[float, float, float] | None:
    """Infer a part center position from name pattern + body dimensions.

    Returns a (x, y, z) tuple placing the part outside the body's
    bounding box (origin-centered ``dimensions_cm``) by ``+offset`` cm,
    or None when the name carries no positional hint and the part
    should remain at origin.

    Patterns recognized (case-insensitive substring or suffix matches):

      - ``_l`` / ``left_`` / ``_left`` → on -X face
      - ``_r`` / ``right_`` / ``_right`` → on +X face
      - ``_top`` / ``top_`` → on +Z face
      - ``_bottom`` / ``bottom_`` → on -Z face
      - ``foot`` / ``feet`` / ``leg`` (no L/R suffix) → centered on -Y face
      - ``handle`` (no L/R suffix) → on +Z (top) face
      - ``latch`` / ``lock`` / ``hasp`` → on +Y (front) face
      - ``hinge`` → on +X face
      - ``door_leaf`` / ``panel`` / ``leaf`` → on +Y face
      - ``threshold`` → on -Y face

    Heuristic only. Returns None when the name has no positional hint
    so the generator falls back to origin.
    """
    half_x = float(dimensions.get("x", 30.0)) / 2.0
    half_y = float(dimensions.get("y", 30.0)) / 2.0
    half_z = float(dimensions.get("z", 30.0)) / 2.0
    standoff = 3.0  # cm — push parts this far past the body bounding face

    name = part_name.lower()

    # Most specific patterns first.
    if name.endswith("_l") or "_left" in name or name.startswith("left_"):
        return (-half_x - standoff, 0.0, 0.0)
    if name.endswith("_r") or "_right" in name or name.startswith("right_"):
        return (half_x + standoff, 0.0, 0.0)
    if name.endswith("_top") or name.startswith("top_") or "_top_" in name:
        return (0.0, 0.0, half_z + standoff)
    if name.endswith("_bottom") or name.startswith("bottom_") or "_bottom_" in name:
        return (0.0, 0.0, -half_z - standoff)
    if "foot" in name or "feet" in name or name.endswith("_leg"):
        return (0.0, -half_y - standoff, 0.0)
    if "threshold" in name:
        return (0.0, -half_y - standoff, 0.0)
    if "hinge" in name:
        return (half_x + standoff, 0.0, 0.0)
    if "latch" in name or "lock" in name or "hasp" in name:
        return (0.0, half_y + standoff, 0.0)
    if "door_leaf" in name or "leaf" in name or name.endswith("_panel"):
        return (0.0, half_y + standoff, 0.0)
    if "handle" in name:
        return (0.0, 0.0, half_z + standoff)
    return None


def _auto_graph_from_parts(asset: dict[str, Any]) -> dict[str, Any]:
    """Synthesize a minimum construction_graph from authored intent.parts.

    For each part name in ``asset.intent.parts``, classify it into a
    NODE_TYPE via the existing ``construction_graph._classify_part``
    substring rules. The first part classified as ``primary_volume``
    (or, failing that, the first part listed) becomes the body
    primary_volume node and carries the asset's scale-derived
    dimensions. Other parts become NODE_TYPE nodes with minimum
    attributes the synthesizer's policy expansion completes.

    Secondary parts also receive a ``position_cm`` attribute inferred
    from their name (see :func:`_infer_position_cm`). Generators that
    honour ``position_cm`` translate the primitive's ``center`` into
    that point, placing visible features around the body's bounding
    box rather than buried inside it at origin.

    Returns an empty graph when no parts are authored. This is the
    Phase B Sprint 0 capstone — it lets every .lth that lists parts
    drive through the procedural synthesizer without grammar work.
    """
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if not isinstance(intent, dict):
        return {"nodes": [], "edges": []}
    parts = intent.get("parts") or []
    if not isinstance(parts, list) or not parts:
        return {"nodes": [], "edges": []}

    # Lazy import to avoid cycles at module import time.
    from ..asset_quality.construction_graph import _classify_part

    dimensions = _scale_to_dimensions(intent.get("scale"), kind=asset.get("kind"))
    nodes: list[dict[str, Any]] = []
    has_primary_volume = False
    for part_name in parts:
        if not isinstance(part_name, str) or not part_name.strip():
            continue
        node_type = _classify_part(part_name)
        if node_type == "primary_volume":
            has_primary_volume = True
        if node_type == "primary_volume":
            attributes: dict[str, Any] = {
                "shape": "rounded_box",
                "dimensions_cm": dimensions,
                "rounding_cm": 1.0,
            }
        else:
            attributes = _auto_attributes_for(node_type, part_name)
            position = _infer_position_cm(part_name, dimensions)
            if position is not None:
                attributes["position_cm"] = position
        nodes.append({
            "node_id": part_name,
            "node_type": node_type,
            "domain": "hard_surface",
            "attributes": attributes,
        })

    # The synthesizer policy precondition needs at least one
    # primary_volume to fire. Promote the first listed part if no part
    # classified as primary_volume — typical for parts lists like
    # ["body", ...] where body classifies correctly, but also covers
    # ["chassis", "..."] where chassis classifies as panel by default.
    if not has_primary_volume and nodes:
        first = nodes[0]
        first["node_type"] = "primary_volume"
        first["attributes"] = {
            "shape": "rounded_box",
            "dimensions_cm": dimensions,
            "rounding_cm": 1.0,
        }

    return {"nodes": nodes, "edges": [], "auto_synthesized": True}


# Region-id → (r, g, b) palette for material-aware part colouring.
# Used when face_parts attribution carries a known region_id token.
# Mirrors the ``palette_for_material`` colors in ``lathe/materials.py``
# but flattened to RGB tuples (the quick path doesn't bake full PBR).
# Keys are matched as case-insensitive substrings against part / region
# names, so ``policy.panelized_hard_surface_object.bracket.0.leg_a``
# matches on ``bracket`` and gets the brass corner-guard colour.
_REGION_COLOUR_PALETTE: tuple[tuple[str, tuple[int, int, int]], ...] = (
    # Specific region IDs from policy expansions.
    ("corner_guard", (165, 138, 92)),       # warm brass
    ("fastener_grid", (78, 84, 96)),        # dark gunmetal rivet
    ("mid_belt", (92, 110, 122)),           # mid blue-grey trim
    ("trim_band", (92, 110, 122)),
    ("warning_marker", (218, 168, 60)),     # caution yellow
    ("edge_wear", (110, 92, 70)),           # worn brown patina
    ("primary_material", (132, 140, 124)),  # painted steel sage
    ("material_zone", (132, 140, 124)),     # same as primary_material — zone ops fall through here when face-attributed
    # NODE_TYPE substring matches (lower priority).
    ("bracket", (165, 138, 92)),
    ("fastener", (78, 84, 96)),
    ("rivet", (78, 84, 96)),
    ("handle", (148, 134, 118)),            # warm steel
    ("hinge", (94, 100, 108)),              # cold steel
    ("latch", (148, 134, 118)),
    ("foot", (52, 56, 60)),                 # rubber black
    ("mount", (140, 140, 132)),
    ("panel", (138, 144, 130)),
    ("door_leaf", (138, 144, 130)),
    ("threshold", (88, 88, 84)),
    ("trim", (92, 110, 122)),
)


def _colour_for_region(name: str) -> tuple[int, int, int] | None:
    """Resolve a region/part name to a palette colour, or None.

    Performs a case-insensitive substring scan against the palette in
    declaration order — earlier entries are more specific (concrete
    region ids) and win over later entries (generic NODE_TYPE matches).
    """
    if not isinstance(name, str):
        return None
    lower = name.lower()
    for token, rgb in _REGION_COLOUR_PALETTE:
        if token in lower:
            return rgb
    return None


def _resolve_part_colors(
    asset_graph: AssetGraph,
    synthesis_result: Any,
    target_part: str,
) -> dict[str, tuple[int, int, int]]:
    """Build the part-name → RGB map for GLB export.

    Order:
      1. Authored parts (asset_graph.parts) — resolve by name token
         (handle / foot / latch / etc.) so authored "handle_l" gets
         the warm steel colour.
      2. Synthesized policy nodes — resolve by ``region_id`` (the
         policy template's region_id) or by node_type substring.
      3. Target part if not yet covered.
      4. Fallback: ``_make_color`` hash for anything still uncovered.

    The downstream ``export_runtime_scene_glb`` applies these as
    per-submesh face_colors so the GLB carries material-aware colour
    even before the full PBR bake.
    """
    colours: dict[str, tuple[int, int, int]] = {}

    for part in asset_graph.parts:
        c = _colour_for_region(part.name)
        colours[part.name] = c if c is not None else _make_color(part.name)

    synth_nodes = getattr(synthesis_result, "synthesized_graph_nodes", ())
    for node in synth_nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("node_id") or "")
        if not node_id:
            continue
        attrs = node.get("attributes") if isinstance(node.get("attributes"), Mapping) else {}
        region_id = attrs.get("region_id") if isinstance(attrs, Mapping) else None
        # Prefer region_id match (more specific) over node_id token match.
        c = _colour_for_region(str(region_id) if region_id else node_id)
        colours[node_id] = c if c is not None else _make_color(node_id)

    if target_part not in colours:
        c = _colour_for_region(target_part)
        colours[target_part] = c if c is not None else _make_color(target_part)
    return colours


def runtime_from_asset(asset: dict[str, Any]) -> dict[str, Any]:
    """Construct a synthesizer runtime from authored asset fields.

    The synthesizer's runtime is a dict containing ``design_brief`` and
    ``construction_graph``. At shape-stage time the validate-stage's
    runtime is not yet populated, so we synthesize one from the
    authored asset:

      - design_brief.brief: from asset.build.shape.procedural.brief OR
        asset.intent.brief OR {}.
      - construction_graph (priority order):
          1. asset.build.shape.procedural.construction_graph (explicit
             authored override)
          2. asset.intent.construction_graph (alternate authored
             location)
          3. Auto-synthesized graph from asset.intent.parts when neither
             of the above is present. This is the Sprint 0 capstone
             path — combined with the widened ``synthesizer_eligible``
             predicate, it lets every .lth that lists parts drive
             through the procedural synthesizer without per-asset
             construction-graph authoring.
    """
    shape_cfg = asset.get("build", {}).get("shape", {}) or {}
    procedural = shape_cfg.get("procedural") if isinstance(shape_cfg, dict) else None
    intent = asset.get("intent") if isinstance(asset, dict) else None

    brief: dict[str, Any] = {}
    if isinstance(procedural, dict):
        b = procedural.get("brief")
        if isinstance(b, dict):
            brief.update(b)
    if not brief and isinstance(intent, dict):
        b = intent.get("brief")
        if isinstance(b, dict):
            brief.update(b)
    # Propagate the asset's family into the brief if not already
    # there — the synthesizer's context resolver uses it for alias
    # lookup.
    if "family" not in brief:
        family = _asset_family_token(asset)
        if family:
            brief["family"] = family
    # B1 — wire authored intent.density into the brief so the
    # density multiplier in _resolve_count picks it up. Without
    # this, every asset defaults to density=1.0 regardless of
    # authored intent.
    if "density" not in brief and isinstance(intent, dict):
        for source in (intent.get("density"), intent.get("feature_density")):
            if isinstance(source, (int, float)) and source > 0:
                brief["density"] = float(source)
                break
    # B1 — surface authored features.allow into the brief so the
    # synthesizer's policy preconditions and (future) generator
    # gates can read it. ``features.allow`` is a stable .lth field
    # listing feature names the asset opts into; ``features.forbid``
    # is the negative form.
    features = asset.get("features") if isinstance(asset, dict) else None
    if isinstance(features, dict):
        allow_list = features.get("allow")
        if isinstance(allow_list, list):
            brief.setdefault("features_allow", [str(x) for x in allow_list if isinstance(x, str)])
        forbid_list = features.get("forbid")
        if isinstance(forbid_list, list):
            brief.setdefault("features_forbid", [str(x) for x in forbid_list if isinstance(x, str)])

    construction_graph: dict[str, Any] = {}
    if isinstance(procedural, dict):
        cg = procedural.get("construction_graph")
        if isinstance(cg, dict) and cg.get("nodes"):
            construction_graph = cg
    if not construction_graph and isinstance(intent, dict):
        cg = intent.get("construction_graph")
        if isinstance(cg, dict) and cg.get("nodes"):
            construction_graph = cg
    if not construction_graph:
        # No authored graph — synthesize from intent.parts.
        construction_graph = _auto_graph_from_parts(asset)

    return {
        "design_brief": {"brief": brief},
        "construction_graph": construction_graph,
    }


_ZONE_OP_NAMES: frozenset[str] = frozenset(
    {"op.material_zone", "op.decal_zone", "op.wear_zone"}
)


def _extract_semantic_zone_records(shape_program) -> list[dict[str, Any]]:
    """Pull op.material_zone / op.decal_zone / op.wear_zone records.

    The procedural synthesizer's metadata-only ops carry the asset's
    declared material zones, decal placements, and wear regions. They
    have no v1-lowering equivalent (no geometry), but they ARE the
    structural surface evidence downstream stages need. This helper
    extracts them into a flat list so the surface stage can consume
    them without re-walking the ShapeProgram.

    Each record carries:
      - kind: "material_zone" | "decal_zone" | "wear_zone"
      - target: the op's target identifier (host volume / face / part)
      - All op.parameters keys (zone_id, material_hint, decal_intent,
        size_cm, wear_kind, intensity, coverage_fraction, etc.)
      - purpose: the op's purpose string (provenance)
    """
    records: list[dict[str, Any]] = []
    for op in getattr(shape_program, "ops", ()):
        if op.op not in _ZONE_OP_NAMES:
            continue
        record: dict[str, Any] = {
            "kind": op.op.split(".", 1)[1],  # "material_zone" / etc.
            "target": str(op.target or ""),
            "purpose": str(op.purpose or ""),
        }
        # op.parameters is a Mapping; flatten its keys into the record
        # so the surface stage can read zone_id / material_hint / etc.
        # without unwrapping a nested dict.
        params = op.parameters if isinstance(op.parameters, dict) else {}
        for key, value in params.items():
            # Don't overwrite the structural keys.
            if key in {"kind", "target", "purpose"}:
                continue
            record[key] = value
        records.append(record)
    return records


def _regions_from_primitives(primitives: list[ShapePrimitive]) -> list[ShapeRegion]:
    """Build ShapeRegion records from primitives (mirror mesh_program path)."""
    regions: list[ShapeRegion] = []
    for index, primitive in enumerate(primitives):
        if primitive.blend_mode == "subtract":
            continue
        # Use placeholder center/extents — downstream surface/UV stages
        # consume the primitive's own bounds for material zoning, not
        # the region's stored bounds. The region exists to give the
        # primitive a stable name/component label for the topology /
        # surface stages.
        regions.append(
            ShapeRegion(
                name=f"procedural.region.{index}",
                part=str(primitive.part or "body"),
                component=str(primitive.primitive_type or "primitive"),
                center=tuple(primitive.center) if primitive.center else (0.0, 0.0, 0.0),
                extents=(1.0, 1.0, 1.0),
                tags=["procedural"],
            )
        )
    return regions


def compile_procedural_program_candidate(
    asset_graph: AssetGraph,
    synthesis_result: SynthesisResult,
    *,
    mode: str,
    conditioning: dict[str, Any],
    runtime_config: dict[str, Any] | None = None,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """Lower the synthesizer's ShapeProgram into a scaffold-shaped result.

    Returns a dict whose shape matches
    :func:`lathe.scaffold_compiler.compile_scaffold_candidates` so the
    rest of :func:`lathe.shape.backend.run_shape_backend` consumes it
    unchanged.
    """
    trace_path: Path | None = None
    latest_trace_path: Path | None = None
    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        trace_path = work_dir / "procedural_program_progress.jsonl"
        latest_trace_path = work_dir / "procedural_program_progress_latest.json"
        trace_path.write_text("", encoding="utf-8")

    def _trace(event: dict[str, Any]) -> None:
        if trace_path is None:
            return
        payload = {"time": time.time(), "asset": asset_graph.name, **event}
        line = json.dumps(payload, sort_keys=True, default=str)
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
        if latest_trace_path is not None:
            latest_trace_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )

    _trace(
        {
            "event": "compile_start",
            "mode": mode,
            "shape_program_op_count": len(synthesis_result.shape_program.ops),
            "synthesized_node_count": len(synthesis_result.synthesized_graph_nodes),
            "family_dispatch_used": synthesis_result.trace.family_dispatch_used,
        }
    )

    shape_program = synthesis_result.shape_program
    geometry_kernel = resolve_geometry_kernel(runtime_config)
    geometry_kernel_id = getattr(geometry_kernel, "name", None)

    # Lower ShapeIR v2 ShapeProgram -> v1 records (dict form)
    _trace({"event": "lower_to_v1_start", "op_count": len(shape_program.ops)})
    adapter = lower_to_v1(shape_program, geometry_kernel=geometry_kernel)
    _trace(
        {
            "event": "lower_to_v1_end",
            "v1_record_count": len(adapter.v1_records),
            "diagnostic_count": len(adapter.diagnostics),
        }
    )

    # Convert v1 records to ShapePrimitive instances
    target_part = (
        asset_graph.parts[0].name if asset_graph.parts else "body"
    )
    primitives: list[ShapePrimitive] = []
    for record in adapter.v1_records:
        try:
            primitive = _primitive_from_v1_record(record)
        except (TypeError, ValueError) as exc:
            _trace(
                {
                    "event": "primitive_skipped",
                    "primitive_type": record.get("primitive_type"),
                    "reason": str(exc),
                }
            )
            continue
        # Ensure every primitive has a part assignment
        if not primitive.part:
            primitive.part = target_part
        primitives.append(primitive)

    if not primitives:
        _trace({"event": "no_primitives", "reason": "lower_to_v1_produced_no_primitives"})
        # Empty primitive list — synthesizer ran but produced nothing
        # the kernel can build. Caller falls through to scaffold compiler.
        raise RuntimeError(
            f"procedural synthesizer produced no convertible primitives "
            f"(shape_program.ops={len(shape_program.ops)}, v1_records={len(adapter.v1_records)}). "
            f"Construction graph may be empty or generators unsupported."
        )

    primitives_used = sorted({primitive.primitive_type for primitive in primitives})
    regions = _regions_from_primitives(primitives)

    signature = {
        "shape_source": "procedural_synthesizer",
        "primitive_count": len(primitives),
        "primitives_used": primitives_used,
        "synthesized_node_count": len(synthesis_result.synthesized_graph_nodes),
    }
    assessment = {
        "shape_source": "procedural_synthesizer",
        "family_dispatch_used": synthesis_result.trace.family_dispatch_used,
        "attempted_via": synthesis_result.trace.attempted_via,
    }

    shape_ir = ShapeIR(
        asset_name=asset_graph.name,
        family=asset_graph.family,
        blueprint_id="procedural_synthesizer_v1",
        symmetry_axis=asset_graph.symmetry_axis,
        units="cm",
        primitives=primitives,
        regions=regions,
        primitives_used=primitives_used,
        part_graph=list(asset_graph.part_graph),
        signature=signature,
        assessment=assessment,
    )

    fidelity = infer_fidelity_profile(asset_graph)
    _trace(
        {
            "event": "exact_surface_start",
            "primitive_count": len(primitives),
            "geometry_kernel": geometry_kernel_id,
            "fidelity": fidelity.tier,
        }
    )
    mesh, face_parts, exact_report = compile_explicit_surface_mesh(
        shape_ir,
        fidelity,
        combine_mode="explicit_mesh",
        geometry_kernel=geometry_kernel,
    )
    _trace(
        {
            "event": "exact_surface_end",
            "vertex_count": len(mesh.vertices),
            "face_count": len(mesh.faces),
            "mode": exact_report.get("mode"),
            "boolean_kernel": exact_report.get("boolean_kernel"),
        }
    )
    if not face_parts:
        face_parts = [target_part] * len(mesh.faces)

    # Part colors: prefer material-zone / region-id derived palettes so
    # the quick-path GLB carries a coherent material story (painted
    # steel body, brass corner guards, dark steel rivets) instead of
    # the previous SHA-derived random muted greys. Falls back to
    # ``_make_color(part.name)`` when no material context is known.
    part_colors = _resolve_part_colors(asset_graph, synthesis_result, target_part)

    game_pipeline_hints = _game_pipeline_hints(asset_graph, shape_ir)
    integration_report = {
        "mode": "procedural_synthesizer_explicit_surface",
        "shape_source": "procedural_synthesizer",
        "primitive_count": len(primitives),
        "synthesized_node_count": len(synthesis_result.synthesized_graph_nodes),
        "exact_report": exact_report,
        "synthesizer_trace_entry_count": len(synthesis_result.trace.entries),
    }
    mesh_ir_payload = finalize_mesh_ir(
        mesh,
        shape_ir,
        list(face_parts),
        metadata={"integration_report": integration_report},
    ).to_dict()

    selection_notes = [
        "shape sourced from procedural synthesizer",
        f"shape_program_op_count={len(shape_program.ops)}",
        f"primitive_count={len(primitives)}",
        f"primitives_used={','.join(primitives_used)}",
        f"family_dispatch_used={synthesis_result.trace.family_dispatch_used}",
        f"fidelity={fidelity.tier}",
    ]
    candidate_score = 0.80
    semantic_zone_records = _extract_semantic_zone_records(shape_program)
    runtime_candidate = {
        "mesh": mesh,
        "face_parts": list(face_parts),
        "part_colors": part_colors,
        "units": "cm",
        "meta": {
            "parts": sorted({region.part for region in regions}) or [target_part],
            "coarse_material_slots": max(1, len(asset_graph.materials)),
            "score": candidate_score,
            "selection_notes": selection_notes,
            "conditioning": {
                "provider": None,
                "reference_strength": float(conditioning.get("reference_strength", 0.0)),
                "family": asset_graph.family,
                "native_scaffold": True,
                "mode": mode,
                "blueprint_id": shape_ir.blueprint_id,
                "shape_source": "procedural_synthesizer",
                "quality_plan_consumed": bool(conditioning.get("quality_plan_consumed")),
                "quality_generation_source_stage": conditioning.get(
                    "quality_generation_source_stage"
                ),
                "quality_conditioning": dict(conditioning.get("quality_conditioning", {})),
            },
            "blueprint_id": shape_ir.blueprint_id,
            "primitives_used": list(primitives_used),
            "shape_assessment": dict(shape_ir.assessment),
            "repairs_applied": [],
            "feature_report": {
                "shape_source": "procedural_synthesizer",
                "feature_ops_used": [],
                "shape_assessment": dict(shape_ir.assessment),
                "game_pipeline_hints": game_pipeline_hints,
            },
            "candidate_params": {"shape_source": "procedural_synthesizer"},
            "game_pipeline_hints": game_pipeline_hints,
            "integration_report": integration_report,
            "mesh_ir": mesh_ir_payload,
            "synthesizer_trace": synthesis_result.trace.to_dict(),
            # Surface-stage-consumable structural metadata. Captures the
            # synthesizer's op.material_zone / op.decal_zone / op.wear_zone
            # records so downstream stages don't have to crack open
            # shape_program ops themselves.
            "semantic_zone_records": semantic_zone_records,
        },
    }

    _trace({"event": "compile_end"})
    return {
        "asset_graph": asset_graph,
        "shape_irs": [shape_ir],
        "runtime_candidates": [runtime_candidate],
        "report": {
            "family": asset_graph.family,
            "generator": "procedural_synthesizer",
            "shape_source": "procedural_synthesizer",
            "asset_graph": asset_graph.to_dict(),
            "shape_irs": [shape_ir.to_dict()],
            "blueprints": [],
            "feature_reports": [runtime_candidate["meta"]["feature_report"]],
            "candidate_search": [{"shape_source": "procedural_synthesizer"}],
            "candidate_search_summary": [
                {
                    "candidate_index": 0,
                    "pre_score": candidate_score,
                    "shortlisted": True,
                    "shape_assessment": dict(shape_ir.assessment),
                }
            ],
            "fidelity": fidelity.to_dict(),
            "signature": dict(shape_ir.signature),
            "blueprint_id": shape_ir.blueprint_id,
            "primitives_used": list(primitives_used),
            "shape_assessment": dict(shape_ir.assessment),
            "repairs": [],
            "authoritative_candidate_reason": "procedural_synthesizer",
            "geometry_kernel": exact_report.get("boolean_kernel") or geometry_kernel_id,
            "game_pipeline_hints": game_pipeline_hints,
            "synthesizer_trace": synthesis_result.trace.to_dict(),
            "synthesized_graph_nodes": [
                dict(node) for node in synthesis_result.synthesized_graph_nodes
            ],
        },
    }
