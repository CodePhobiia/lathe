"""mesh_program-level WFC ops: declarative module/rule constructors and
the ``wfc_modular(...)`` solver call that fills a canvas with placed
ShapePrimitives.

This module bridges the existing ``lathe.wfc`` solver into the
``mesh_program{}`` block lowering layer. Authors declare modules and
adjacency rules using ordinary mesh_program identifiers, then call
``wfc_modular(...)`` to instantiate N translated copies of the chosen
modules' primitives onto the program's primitive list.

v1 scope (Phase 3 fourth slice):
* One or more primitives per module (the underlying ``mesh_program`` binding).
* Fixed cell size (one length-unit literal applied uniformly).
* Symmetric adjacency: ``wfc_rule(a, b, direction)`` allows both
  ``(a -> b, +d)`` and ``(b -> a, -d)`` (the underlying solver enforces
  this by construction).
* Direction shorthand: ``"x"|"y"|"z"`` expands to the +/- pair so a
  single rule allows both forward and reverse without two declarations.
* ``probability`` on a rule is recorded but not yet consumed by the v1
  solver (full WFC entropy weighting is Phase 4 work).

Out of scope: rotation handling, hierarchical WFC, adaptive cells.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from ..shape_ir import ShapePrimitive
from .adjacency import AdjacencyRules
from .solver import solve_wfc
from .tileset import DIRECTIONS, OPPOSITE, Tile, Tileset


_DIRECTION_SHORTHANDS = {
    "x": ("+X", "-X"),
    "y": ("+Y", "-Y"),
    "z": ("+Z", "-Z"),
    "+x": ("+X",),
    "-x": ("-X",),
    "+y": ("+Y",),
    "-y": ("-Y",),
    "+z": ("+Z",),
    "-z": ("-Z",),
}


@dataclass
class WFCModuleRef:
    """Author-declared WFC module: name + primitive payload + weight."""

    name: str
    primitive: ShapePrimitive | None
    weight: float
    primitives: tuple[ShapePrimitive, ...] = ()


@dataclass
class WFCRuleRef:
    """Author-declared WFC rule: ``a`` next to ``b`` along ``directions``."""

    a: str
    b: str
    directions: tuple[str, ...]
    probability: float


def _translate_primitive(
    template: ShapePrimitive, offset: tuple[float, float, float]
) -> ShapePrimitive:
    """Deep-copy a primitive and shift its center + sdf_mesh vertices.

    The exact-solid mesher honors ``primitive.center`` for box, cylinder,
    sphere, extruded_profile, lofted_solid, etc. For ``sdf_mesh`` the
    vertices are baked at extraction time, so we shift them too.
    """
    cloned = copy.deepcopy(template)
    cx, cy, cz = cloned.center
    cloned.center = (cx + offset[0], cy + offset[1], cz + offset[2])
    if cloned.primitive_type == "sdf_mesh" and cloned.mesh_vertices is not None:
        cloned.mesh_vertices = [
            [
                float(v[0]) + offset[0],
                float(v[1]) + offset[1],
                float(v[2]) + offset[2],
            ]
            for v in cloned.mesh_vertices
        ]
    return cloned


def _module_primitives(module: WFCModuleRef) -> tuple[ShapePrimitive, ...]:
    if module.primitives:
        return tuple(module.primitives)
    if module.primitive is not None:
        return (module.primitive,)
    return ()


def _normalize_direction(value: str) -> tuple[str, ...]:
    """Expand a ``"x"|"y"|"z"`` shorthand or signed ``"+x"`` into solver dirs.

    Plain ``"x"`` allows the rule in both ``+X`` and ``-X``: this matches
    author intent for "floor connects to floor along the X axis" without
    forcing two declarations. Signed forms keep the direction unilateral.
    """
    key = value.lower()
    if key not in _DIRECTION_SHORTHANDS:
        valid = sorted(_DIRECTION_SHORTHANDS)
        raise ValueError(
            f"unknown direction {value!r} (supported: {valid})"
        )
    return _DIRECTION_SHORTHANDS[key]


def build_solver_inputs(
    modules: list[WFCModuleRef], rules: list[WFCRuleRef]
) -> tuple[Tileset, AdjacencyRules]:
    """Convert authored module/rule refs into the solver's Tileset+AdjacencyRules.

    Tile.mesh_ref is set to the module name (the solver only uses it as
    an opaque tag — we look up the actual primitive from the module dict
    in the caller). AdjacencyRules.allow() symmetrizes each rule for us.
    """
    tiles: list[Tile] = []
    seen_names: set[str] = set()
    for module in modules:
        if module.name in seen_names:
            raise ValueError(f"duplicate WFC module name {module.name!r}")
        if not _module_primitives(module):
            raise ValueError(f"WFC module {module.name!r} has no primitives")
        seen_names.add(module.name)
        tiles.append(
            Tile(id=module.name, mesh_ref=module.name, weight=module.weight)
        )
    tileset = Tileset(name="wfc_modular", tiles=tiles)

    adjacency = AdjacencyRules(name="wfc_modular_rules")
    # Self-tile placement is always allowed within a single cell (degenerate
    # case the solver doesn't probe). Empty adjacency means no neighbors
    # would be valid and the solver would contradict — so we add a permissive
    # default for any module that has no rules at all: "module X may sit next
    # to itself in every direction". This is the v1 fallback that lets a
    # one-module canvas (just floor) succeed without authoring 6 self-rules.
    declared_pairs: set[tuple[str, str]] = set()
    for rule in rules:
        if rule.a not in seen_names:
            raise ValueError(
                f"WFC rule references unknown module {rule.a!r}"
            )
        if rule.b not in seen_names:
            raise ValueError(
                f"WFC rule references unknown module {rule.b!r}"
            )
        for direction in rule.directions:
            adjacency.allow(rule.a, direction, rule.b)
        declared_pairs.add((rule.a, rule.b))
        declared_pairs.add((rule.b, rule.a))

    # For modules that authors didn't constrain, allow them next to
    # everything else (and themselves) so the solver can still place them.
    # This keeps v1 ergonomic: declare only the rules you care about, and
    # the rest of the canvas behaves like an unconstrained random fill.
    for module_a in modules:
        for module_b in modules:
            if (module_a.name, module_b.name) in declared_pairs:
                continue
            for direction in DIRECTIONS:
                adjacency.allow(module_a.name, direction, module_b.name)
    return tileset, adjacency


def expand_solved_grid(
    placements: list[Any],
    modules_by_name: dict[str, WFCModuleRef],
    *,
    cell_size_cm: float,
    canvas_size: tuple[int, int, int],
    part: str,
) -> list[ShapePrimitive]:
    """Translate solved (tile_id, grid_position) pairs into ShapePrimitives.

    Each placed cell becomes a deep-copy of the module's template
    primitive shifted to the cell's world-space center. The grid is
    centered on the origin so a 10x1x10 canvas of 3m cells produces a
    30m-wide square centered at (0, 0, 0).
    """
    nx, ny, nz = canvas_size
    half_x = (nx - 1) * 0.5
    half_y = (ny - 1) * 0.5
    half_z = (nz - 1) * 0.5
    out: list[ShapePrimitive] = []
    for placement in placements:
        module = modules_by_name[placement.tile_id]
        module_primitives = _module_primitives(module)
        gx, gy, gz = placement.position
        offset = (
            (gx - half_x) * cell_size_cm,
            (gy - half_y) * cell_size_cm,
            (gz - half_z) * cell_size_cm,
        )
        for primitive_index, template in enumerate(module_primitives):
            translated = _translate_primitive(template, offset)
            translated.part = part
            tags = [
                f"wfc_cell:{gx},{gy},{gz}",
                f"wfc_module:{module.name}",
            ]
            if len(module_primitives) > 1:
                tags.append(f"wfc_module_primitive:{primitive_index}")
            translated.tags = list(translated.tags) + tags
            out.append(translated)
    return out


def solve_modular(
    *,
    canvas_size: tuple[int, int, int],
    cell_size_cm: float,
    modules: list[WFCModuleRef],
    rules: list[WFCRuleRef],
    seed: int,
    part: str,
) -> list[ShapePrimitive]:
    """End-to-end WFC modular solve: returns the final list of primitives.

    Wraps :func:`solve_wfc` so callers in ``mesh_program/`` don't need
    to thread the tileset/adjacency dance themselves.
    """
    if not modules:
        raise ValueError("wfc_modular requires at least one module")
    tileset, adjacency = build_solver_inputs(modules, rules)
    modules_by_name = {m.name: m for m in modules}
    result = solve_wfc(
        tileset,
        adjacency,
        canvas_size,
        seed=seed,
    )
    return expand_solved_grid(
        result.placements,
        modules_by_name,
        cell_size_cm=cell_size_cm,
        canvas_size=canvas_size,
        part=part,
    )
