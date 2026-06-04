"""Tests for the Phase 3 fourth-slice WFC modular ops.

Covers ``wfc_module`` / ``wfc_rule`` (declarative refs) and
``wfc_modular(...)`` (the compound op that runs the WFC solver and
emits one ShapePrimitive per cell as a translated copy of the chosen
module's primitive).
"""

from __future__ import annotations

import pytest
from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text
from lathe.shape_ir import ShapePrimitive
from lathe.wfc.mesh_program_ops import (
    WFCModuleRef,
    WFCRuleRef,
    _normalize_direction,
    build_solver_inputs,
    solve_modular,
)


def _parse_program(body: str) -> dict:
    src = (
        "module demo.wfc_test\n"
        'asset wfc_test : hard_surface_prop {\n'
        '  intent { role = "wfc test" }\n'
        "  build {\n"
        "    shape {\n"
        "      mode = generate\n"
        "      candidates = 1\n"
        "      mesh_program {\n"
        f"{body}\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    program = parse_text(src)
    return program["assets"][0]["build"]["shape"]["mesh_program"]


# --- Solver-level direct unit tests --------------------------------------


def test_normalize_direction_axis_shorthand_expands_to_pair() -> None:
    assert _normalize_direction("x") == ("+X", "-X")
    assert _normalize_direction("y") == ("+Y", "-Y")
    assert _normalize_direction("z") == ("+Z", "-Z")


def test_normalize_direction_signed_form_is_unilateral() -> None:
    assert _normalize_direction("+x") == ("+X",)
    assert _normalize_direction("-z") == ("-Z",)


def test_normalize_direction_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown direction"):
        _normalize_direction("diagonal")


def _box_primitive(name: str = "box") -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="box",
        part="body",
        center=(0.0, 0.0, 0.0),
        extents=(100.0, 100.0, 100.0),
        tags=[name],
    )


def test_solve_modular_fills_canvas_with_correct_cell_count() -> None:
    modules = [
        WFCModuleRef(name="floor", primitive=_box_primitive(), weight=1.0),
    ]
    primitives = solve_modular(
        canvas_size=(4, 1, 4),
        cell_size_cm=300.0,
        modules=modules,
        rules=[],
        seed=42,
        part="body",
    )
    # 4 * 1 * 4 = 16 cells, all filled with the only module available.
    assert len(primitives) == 16


def test_solve_modular_centers_grid_on_origin() -> None:
    modules = [
        WFCModuleRef(name="floor", primitive=_box_primitive(), weight=1.0),
    ]
    primitives = solve_modular(
        canvas_size=(2, 1, 2),
        cell_size_cm=300.0,
        modules=modules,
        rules=[],
        seed=0,
        part="body",
    )
    centers = sorted(p.center for p in primitives)
    # 2x1x2 with cell_size 300 cm: cells at -150, +150 along x and z.
    assert centers == sorted(
        [
            (-150.0, 0.0, -150.0),
            (-150.0, 0.0, 150.0),
            (150.0, 0.0, -150.0),
            (150.0, 0.0, 150.0),
        ]
    )


def test_solve_modular_is_deterministic_at_fixed_seed() -> None:
    modules = [
        WFCModuleRef(name="a", primitive=_box_primitive("a"), weight=1.0),
        WFCModuleRef(name="b", primitive=_box_primitive("b"), weight=1.0),
    ]
    a = solve_modular(
        canvas_size=(3, 1, 3),
        cell_size_cm=100.0,
        modules=modules,
        rules=[],
        seed=99,
        part="body",
    )
    b = solve_modular(
        canvas_size=(3, 1, 3),
        cell_size_cm=100.0,
        modules=modules,
        rules=[],
        seed=99,
        part="body",
    )

    def _module_grid(prims: list[ShapePrimitive]) -> dict[tuple, str]:
        out: dict[tuple, str] = {}
        for p in prims:
            cell_tag = next(t for t in p.tags if t.startswith("wfc_cell:"))
            module_tag = next(t for t in p.tags if t.startswith("wfc_module:"))
            out[cell_tag] = module_tag
        return out

    assert _module_grid(a) == _module_grid(b)


def test_solve_modular_rejects_empty_modules() -> None:
    with pytest.raises(ValueError, match="at least one module"):
        solve_modular(
            canvas_size=(2, 1, 2),
            cell_size_cm=100.0,
            modules=[],
            rules=[],
            seed=0,
            part="body",
        )


def test_build_solver_inputs_rejects_duplicate_module_names() -> None:
    modules = [
        WFCModuleRef(name="dup", primitive=_box_primitive(), weight=1.0),
        WFCModuleRef(name="dup", primitive=_box_primitive(), weight=1.0),
    ]
    with pytest.raises(ValueError, match="duplicate WFC module name"):
        build_solver_inputs(modules, [])


def test_build_solver_inputs_rejects_rule_with_unknown_module() -> None:
    modules = [WFCModuleRef(name="floor", primitive=_box_primitive(), weight=1.0)]
    rules = [
        WFCRuleRef(a="floor", b="ghost", directions=("+X",), probability=1.0)
    ]
    with pytest.raises(ValueError, match="unknown module"):
        build_solver_inputs(modules, rules)


# --- mesh_program-level integration --------------------------------------


def test_wfc_modular_lowers_to_one_primitive_per_cell() -> None:
    body = (
        "        let floor = solid_panel(extents: [3m, 30cm, 3m])\n"
        '        let mod_floor = wfc_module(name: "floor", primitive: floor, weight: 1.0)\n'
        "        wfc_modular(\n"
        "          canvas_size: [4, 1, 4],\n"
        "          cell_size: 3m,\n"
        "          modules: [mod_floor],\n"
        "          adjacency: [],\n"
        "          seed: 42,\n"
        "        )"
    )
    primitives = lower_mesh_program(_parse_program(body))
    # 4 * 1 * 4 = 16 floor cells.
    assert len(primitives) == 16
    # Every primitive is tagged with its cell + module.
    for prim in primitives:
        assert any(t.startswith("wfc_cell:") for t in prim.tags)
        assert any(t == "wfc_module:floor" for t in prim.tags)


def test_wfc_modular_supports_multiple_modules_with_weights() -> None:
    body = (
        "        let floor = solid_panel(extents: [3m, 30cm, 3m])\n"
        '        let wall = solid_panel(extents: [3m, 3m, 30cm])\n'
        '        let mod_floor = wfc_module(name: "floor", primitive: floor, weight: 0.8)\n'
        '        let mod_wall = wfc_module(name: "wall", primitive: wall, weight: 0.2)\n'
        "        wfc_modular(\n"
        "          canvas_size: [10, 1, 10],\n"
        "          cell_size: 3m,\n"
        "          modules: [mod_floor, mod_wall],\n"
        "          adjacency: [],\n"
        "          seed: 7,\n"
        "        )"
    )
    primitives = lower_mesh_program(_parse_program(body))
    assert len(primitives) == 100
    counts = {"floor": 0, "wall": 0}
    for prim in primitives:
        for tag in prim.tags:
            if tag == "wfc_module:floor":
                counts["floor"] += 1
            elif tag == "wfc_module:wall":
                counts["wall"] += 1
    # With weight 0.8 vs 0.2 over 100 cells, floor should dominate.
    assert counts["floor"] > counts["wall"]
    assert counts["floor"] + counts["wall"] == 100


def test_wfc_module_rejects_non_primitive_target() -> None:
    body = (
        '        let mod = wfc_module(name: "x", primitive: nope, weight: 1.0)\n'
        "        wfc_modular(\n"
        "          canvas_size: [1, 1, 1],\n"
        "          cell_size: 1m,\n"
        "          modules: [mod],\n"
        "          adjacency: [],\n"
        "          seed: 0,\n"
        "        )"
    )
    with pytest.raises(MeshProgramError, match="unknown identifier"):
        lower_mesh_program(_parse_program(body))


def test_wfc_modular_rejects_unknown_module_ident() -> None:
    body = (
        "        let floor = solid_panel(extents: [3m, 30cm, 3m])\n"
        "        wfc_modular(\n"
        "          canvas_size: [2, 1, 2],\n"
        "          cell_size: 3m,\n"
        "          modules: [missing_mod],\n"
        "          adjacency: [],\n"
        "          seed: 0,\n"
        "        )"
    )
    with pytest.raises(MeshProgramError, match="unknown identifier"):
        lower_mesh_program(_parse_program(body))


def test_wfc_modular_rejects_non_module_in_modules_list() -> None:
    body = (
        "        let floor = solid_panel(extents: [3m, 30cm, 3m])\n"
        "        wfc_modular(\n"
        "          canvas_size: [2, 1, 2],\n"
        "          cell_size: 3m,\n"
        "          modules: [floor],\n"
        "          adjacency: [],\n"
        "          seed: 0,\n"
        "        )"
    )
    with pytest.raises(MeshProgramError, match="must be a wfc_module"):
        lower_mesh_program(_parse_program(body))


def test_wfc_rule_resolves_to_solver_adjacency() -> None:
    body = (
        "        let floor = solid_panel(extents: [3m, 30cm, 3m])\n"
        '        let mod_floor = wfc_module(name: "floor", primitive: floor, weight: 1.0)\n'
        '        let rule = wfc_rule(a: "floor", b: "floor", direction: "x")\n'
        "        wfc_modular(\n"
        "          canvas_size: [3, 1, 1],\n"
        "          cell_size: 3m,\n"
        "          modules: [mod_floor],\n"
        "          adjacency: [rule],\n"
        "          seed: 0,\n"
        "        )"
    )
    primitives = lower_mesh_program(_parse_program(body))
    assert len(primitives) == 3


def test_wfc_modular_canvas_centered_on_origin() -> None:
    body = (
        "        let floor = solid_panel(extents: [3m, 30cm, 3m])\n"
        '        let mod_floor = wfc_module(name: "floor", primitive: floor, weight: 1.0)\n'
        "        wfc_modular(\n"
        "          canvas_size: [10, 1, 10],\n"
        "          cell_size: 3m,\n"
        "          modules: [mod_floor],\n"
        "          adjacency: [],\n"
        "          seed: 42,\n"
        "        )"
    )
    primitives = lower_mesh_program(_parse_program(body))
    xs = [p.center[0] for p in primitives]
    zs = [p.center[2] for p in primitives]
    # 10 cells of 3m == 1000 - 50 = ±1350cm centers (cells at ±4.5 cell offset).
    assert min(xs) == pytest.approx(-1350.0)
    assert max(xs) == pytest.approx(1350.0)
    assert min(zs) == pytest.approx(-1350.0)
    assert max(zs) == pytest.approx(1350.0)
