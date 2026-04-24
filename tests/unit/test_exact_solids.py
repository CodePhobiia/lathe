"""Unit tests for ``lathe.exact_solids``.

The module exposes two public entry points and several primitive
constructors. We test construction of the translated box/cylinder
helpers, the ``_primitive_mesh`` dispatch, and both end-to-end entry
points — ``compile_explicit_surface_mesh`` and ``exactify_surface_mesh``
— under the three ShapeIR scenarios that can reach them (empty, single
primitive, multi primitive).

The ``_translated_*`` helpers are tested directly: they're the
translation equivalent of a transform composition on ``trimesh.creation``
primitives, and they're the lowest-level invariant the fuse path depends
on.
"""

from __future__ import annotations

import unittest

import numpy as np
import trimesh

from lathe.errors import ContractViolation
from lathe.exact_solids import (
    _primitive_mesh,
    _translated_box,
    _translated_cylinder,
    compile_explicit_surface_mesh,
    exactify_surface_mesh,
)
from lathe.fidelity import FidelityProfile
from lathe.shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


def _game_fidelity() -> FidelityProfile:
    return FidelityProfile(
        tier="game",
        detail_density=1.0,
        edge_weight=1.0,
        panel_depth=1.0,
        trim_complexity=3,
        support_complexity=1.0,
        silhouette_refinement=1.0,
        repair_budget=3,
    )


def _hero_fidelity() -> FidelityProfile:
    return FidelityProfile(
        tier="hero",
        detail_density=1.35,
        edge_weight=1.25,
        panel_depth=1.30,
        trim_complexity=5,
        support_complexity=1.20,
        silhouette_refinement=1.18,
        repair_budget=4,
    )


def _empty_shape_ir() -> ShapeIR:
    return ShapeIR(
        asset_name="demo",
        family="industrial_crate",
        blueprint_id="bp",
        symmetry_axis=None,
        units="m",
        primitives=[],
        regions=[],
        primitives_used=[],
        part_graph=[],
        signature={"blueprint_notes": []},
    )


def _single_box_shape_ir() -> ShapeIR:
    s = _empty_shape_ir()
    s.primitives.append(
        ShapePrimitive(
            primitive_type="box",
            part="body",
            center=(0.0, 0.0, 0.0),
            extents=(2.0, 2.0, 2.0),
        )
    )
    s.regions.append(
        ShapeRegion(
            name="r1",
            part="body",
            component="hull",
            center=(0.0, 0.0, 0.0),
            extents=(2.0, 2.0, 2.0),
        )
    )
    s.primitives_used = ["box"]
    return s


def _two_primitive_shape_ir() -> ShapeIR:
    s = _single_box_shape_ir()
    s.primitives.append(
        ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.0, 0.0, 2.0),
            radius=0.5,
            height=2.0,
            axis="y",
        )
    )
    s.regions.append(
        ShapeRegion(
            name="r2",
            part="stem",
            component="hull",
            center=(0.0, 0.0, 2.0),
            extents=(1.0, 2.0, 1.0),
        )
    )
    s.primitives_used = ["box", "cylinder"]
    return s


class TranslatedPrimitiveTests(unittest.TestCase):
    def test_translated_box_watertight_and_centered(self) -> None:
        mesh = _translated_box((2.0, 2.0, 2.0), (1.0, 2.0, 3.0))
        self.assertIsInstance(mesh, trimesh.Trimesh)
        self.assertTrue(mesh.is_watertight)
        # centroid should be near (1, 2, 3); trimesh bounds mid is exact for a box
        bmin, bmax = mesh.bounds
        midpoint = (bmin + bmax) / 2.0
        self.assertTrue(np.allclose(midpoint, [1.0, 2.0, 3.0]))
        # extents match requested
        self.assertTrue(np.allclose(bmax - bmin, [2.0, 2.0, 2.0]))

    def test_translated_cylinder_axes_orient_correctly(self) -> None:
        # axis='y' mesh should be tallest along Y
        m_y = _translated_cylinder(radius=0.5, height=2.0, center=(0.0, 0.0, 0.0), axis="y")
        ext = m_y.bounds[1] - m_y.bounds[0]
        # y axis should be ~2.0, x/z ~1.0
        self.assertAlmostEqual(ext[1], 2.0, places=4)
        self.assertAlmostEqual(ext[0], 1.0, places=4)
        self.assertAlmostEqual(ext[2], 1.0, places=4)

        # axis='z' cylinder defaults (trimesh.creation.cylinder is z-oriented) → height on z
        m_z = _translated_cylinder(radius=0.5, height=2.0, center=(0.0, 0.0, 0.0), axis="z")
        ext_z = m_z.bounds[1] - m_z.bounds[0]
        self.assertAlmostEqual(ext_z[2], 2.0, places=4)

    def test_primitive_mesh_dispatch_box_and_cylinder(self) -> None:
        box_prim = ShapePrimitive(
            primitive_type="box",
            part="body",
            center=(0.0, 0.0, 0.0),
            extents=(2.0, 2.0, 2.0),
        )
        cyl_prim = ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.0, 0.0, 0.0),
            radius=1.0,
            height=3.0,
        )
        box_mesh = _primitive_mesh(box_prim)
        cyl_mesh = _primitive_mesh(cyl_prim)
        self.assertEqual(len(box_mesh.faces), 12)  # 6 quads → 12 triangles
        self.assertGreater(len(cyl_mesh.faces), 12)  # cylinder has more sides

    def test_primitive_mesh_rejects_missing_box_extents(self) -> None:
        bad = ShapePrimitive(
            primitive_type="box", part="body", center=(0.0, 0.0, 0.0)
        )
        with self.assertRaises(ContractViolation):
            _primitive_mesh(bad)

    def test_primitive_mesh_rejects_unknown_type(self) -> None:
        weird = ShapePrimitive(
            primitive_type="torus", part="body", center=(0.0, 0.0, 0.0)
        )
        with self.assertRaises(ValueError):
            _primitive_mesh(weird)


class CompileExplicitSurfaceMeshTests(unittest.TestCase):
    def test_empty_shape_ir_returns_empty_trimesh(self) -> None:
        s = _empty_shape_ir()
        mesh, face_parts, report = compile_explicit_surface_mesh(s, _game_fidelity())
        self.assertEqual(len(mesh.faces), 0)
        self.assertEqual(face_parts, [])
        self.assertEqual(report["mode"], "exact_explicit_assembly")
        self.assertEqual(report["primitive_count"], 0)

    def test_single_primitive_produces_watertight_mesh(self) -> None:
        s = _single_box_shape_ir()
        mesh, face_parts, report = compile_explicit_surface_mesh(s, _game_fidelity())
        self.assertGreater(len(mesh.faces), 0)
        # face_parts has one label per face
        self.assertEqual(len(face_parts), int(len(mesh.faces)))
        self.assertEqual(set(face_parts), {"body"})
        self.assertEqual(report["mode"], "exact_explicit_assembly")
        self.assertEqual(report["primitive_count"], 1)

    def test_two_primitives_union_or_concatenate(self) -> None:
        s = _two_primitive_shape_ir()
        mesh, face_parts, report = compile_explicit_surface_mesh(s, _game_fidelity())
        self.assertGreater(len(mesh.faces), 0)
        # either boolean union (face_parts_out cleared) or concatenate (per-primitive labels)
        self.assertIn(report["mode"], {"exact_boolean_union", "exact_explicit_assembly"})
        self.assertEqual(report["primitive_count"], 2)

    def test_component_assembly_mode_skips_union(self) -> None:
        s = _two_primitive_shape_ir()
        mesh, face_parts, report = compile_explicit_surface_mesh(
            s, _game_fidelity(), combine_mode="component_assembly"
        )
        self.assertGreater(len(mesh.faces), 0)
        # component_assembly preserves per-primitive face_parts (no union)
        self.assertEqual(len(face_parts), int(len(mesh.faces)))
        self.assertEqual(report["mode"], "exact_component_assembly")


class ExactifySurfaceMeshTests(unittest.TestCase):
    def test_empty_mesh_returns_zero_shifts(self) -> None:
        empty = trimesh.Trimesh()
        s = _single_box_shape_ir()
        refined, report = exactify_surface_mesh(empty, s, _game_fidelity())
        self.assertEqual(len(refined.vertices), 0)
        self.assertEqual(report["projection_iterations"], 0)
        self.assertEqual(report["mean_vertex_shift"], 0.0)
        self.assertEqual(report["max_vertex_shift"], 0.0)

    def test_empty_primitives_returns_zero_shifts(self) -> None:
        mesh = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
        s = _empty_shape_ir()
        refined, report = exactify_surface_mesh(mesh, s, _game_fidelity())
        self.assertEqual(len(refined.vertices), len(mesh.vertices))
        self.assertEqual(report["projection_iterations"], 0)

    def test_nonempty_mesh_records_iterations(self) -> None:
        s = _single_box_shape_ir()
        mesh, _face_parts, _report = compile_explicit_surface_mesh(s, _game_fidelity())
        refined, exact_report = exactify_surface_mesh(mesh, s, _game_fidelity())
        self.assertGreater(len(refined.vertices), 0)
        self.assertGreaterEqual(exact_report["projection_iterations"], 1)
        self.assertIn("snap_radius", exact_report)

    def test_hero_tier_uses_more_iterations(self) -> None:
        s = _single_box_shape_ir()
        mesh, _face_parts, _report = compile_explicit_surface_mesh(s, _hero_fidelity())
        _refined, exact_report_hero = exactify_surface_mesh(mesh, s, _hero_fidelity())
        _refined_g, exact_report_game = exactify_surface_mesh(mesh, s, _game_fidelity())
        self.assertGreaterEqual(
            exact_report_hero["projection_iterations"],
            exact_report_game["projection_iterations"],
        )


if __name__ == "__main__":
    unittest.main()
