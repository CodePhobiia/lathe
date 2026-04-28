"""Unit tests for ``lathe.geometry_kernel``.

Tests the shape-stage fusion kernel — ``fuse_shape_ir`` and
``solid_ir_from_shape`` — plus the supporting sdf primitives and the
face-assignment helper. Because the current family-set routes every
hero family into the exact_mesh or component_assembly branch, we cover
the contract surface exposed by those branches (watertightness, face
label length, reporting) and also the fallback paths (non-hero family,
empty primitives, unsupported types).
"""

from __future__ import annotations

import time
import unittest
from typing import ClassVar

import numpy as np
from lathe.errors import ContractViolation
from lathe.fidelity import FidelityProfile
from lathe.geometry_kernel import (
    _assign_face_parts,
    _box_sdf,
    _cylinder_sdf,
    _primitive_bounds,
    fuse_shape_ir,
    solid_ir_from_shape,
)
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


def _shape_ir(
    *,
    family: str = "industrial_crate",
    primitives: list[ShapePrimitive] | None = None,
    regions: list[ShapeRegion] | None = None,
) -> ShapeIR:
    return ShapeIR(
        asset_name="demo",
        family=family,
        blueprint_id="bp",
        symmetry_axis=None,
        units="m",
        primitives=list(primitives or []),
        regions=list(regions or []),
        primitives_used=[],
        part_graph=[],
        signature={"blueprint_notes": []},
    )


def _box(
    part: str,
    center: tuple[float, float, float],
    extents: tuple[float, float, float] = (2.0, 2.0, 2.0),
) -> ShapePrimitive:
    return ShapePrimitive(primitive_type="box", part=part, center=center, extents=extents)


def _region_for(
    part: str,
    center: tuple[float, float, float],
    extents: tuple[float, float, float] = (2.0, 2.0, 2.0),
) -> ShapeRegion:
    return ShapeRegion(name=f"r_{part}", part=part, component="hull", center=center, extents=extents)


class FuseShapeIRTests(unittest.TestCase):
    def test_happy_path_two_primitives_produces_watertight_mesh(self) -> None:
        primitives = [
            _box("body", (0.0, 0.0, 0.0)),
            ShapePrimitive(
                primitive_type="cylinder",
                part="stem",
                center=(0.0, 0.0, 2.0),
                radius=0.5,
                height=2.0,
                axis="y",
            ),
        ]
        regions = [
            _region_for("body", (0.0, 0.0, 0.0)),
            _region_for("stem", (0.0, 0.0, 2.0), extents=(1.0, 2.0, 1.0)),
        ]
        shape_ir = _shape_ir(primitives=primitives, regions=regions)

        mesh_ir, report = fuse_shape_ir(shape_ir, _game_fidelity())
        self.assertIsNotNone(mesh_ir)
        assert mesh_ir is not None  # for type-checker

        rebuilt = mesh_ir.to_trimesh()
        self.assertGreater(len(rebuilt.vertices), 0)
        self.assertGreater(len(rebuilt.faces), 0)
        # face_parts length must equal face count — handoff invariant
        self.assertEqual(len(mesh_ir.face_parts), len(mesh_ir.faces))
        self.assertTrue(np.all(np.isfinite(rebuilt.vertices)))
        # report carries a mode string and solid_ir
        self.assertIn("mode", report)
        self.assertIn("solid_ir", report)

    def test_empty_primitives_returns_none_with_fallback_report(self) -> None:
        # Hero family + empty primitives → early no-primitives fallback
        shape_ir = _shape_ir(primitives=[], regions=[])
        mesh_ir, report = fuse_shape_ir(shape_ir, _game_fidelity())
        self.assertIsNone(mesh_ir)
        self.assertEqual(report["mode"], "constructive_fallback")
        self.assertEqual(report["reason"], "no primitives")

    def test_non_hero_family_reports_integration_disabled(self) -> None:
        # courier_drone is NOT in the hero set (it falls back to learned
        # providers upstream); feature_fusion reports enabled=False.
        primitives = [_box("body", (0.0, 0.0, 0.0))]
        regions = [_region_for("body", (0.0, 0.0, 0.0))]
        shape_ir = _shape_ir(family="courier_drone", primitives=primitives, regions=regions)
        mesh_ir, report = fuse_shape_ir(shape_ir, _game_fidelity())
        self.assertIsNone(mesh_ir)
        self.assertEqual(report["mode"], "constructive_fallback")
        self.assertIn("integration disabled", report["reason"])

    def test_coincident_primitives_fuse_without_nan(self) -> None:
        # Two identical boxes at the origin — the union must collapse
        # cleanly and produce a finite, nondegenerate mesh.
        primitives = [_box("body", (0.0, 0.0, 0.0)), _box("body_b", (0.0, 0.0, 0.0))]
        regions = [_region_for("body", (0.0, 0.0, 0.0)), _region_for("body_b", (0.0, 0.0, 0.0))]
        shape_ir = _shape_ir(primitives=primitives, regions=regions)
        mesh_ir, _report = fuse_shape_ir(shape_ir, _game_fidelity())
        self.assertIsNotNone(mesh_ir)
        assert mesh_ir is not None
        verts = np.asarray(mesh_ir.vertices, dtype=np.float64)
        self.assertTrue(np.all(np.isfinite(verts)))
        self.assertGreater(len(mesh_ir.faces), 0)

    def test_far_origin_numerical_stability(self) -> None:
        # Widely separated primitives shouldn't blow up the voxelization
        # or produce NaN/inf vertices.
        primitives = [
            _box("body", (0.0, 0.0, 0.0)),
            _box("top", (1000.0, 1000.0, 1000.0)),
        ]
        regions = [
            _region_for("body", (0.0, 0.0, 0.0)),
            _region_for("top", (1000.0, 1000.0, 1000.0)),
        ]
        shape_ir = _shape_ir(primitives=primitives, regions=regions)
        mesh_ir, _report = fuse_shape_ir(shape_ir, _game_fidelity())
        self.assertIsNotNone(mesh_ir)
        assert mesh_ir is not None
        verts = np.asarray(mesh_ir.vertices, dtype=np.float64)
        self.assertTrue(np.all(np.isfinite(verts)))

    def test_large_primitive_count_completes_in_reasonable_time(self) -> None:
        # 25 primitives — the exact_mesh path should handle this under 5 s.
        primitives = [_box(f"p{i}", (i * 2.5, 0.0, 0.0)) for i in range(25)]
        regions = [_region_for(f"p{i}", (i * 2.5, 0.0, 0.0)) for i in range(25)]
        shape_ir = _shape_ir(primitives=primitives, regions=regions)

        t0 = time.time()
        mesh_ir, _report = fuse_shape_ir(shape_ir, _game_fidelity())
        elapsed = time.time() - t0
        self.assertLess(elapsed, 5.0)
        self.assertIsNotNone(mesh_ir)
        assert mesh_ir is not None
        self.assertGreater(len(mesh_ir.faces), 0)

    def test_invalid_primitive_type_raises_value_error(self) -> None:
        # 'sphere' isn't supported — the kernel should raise rather than
        # silently produce a degenerate mesh.
        bad = ShapePrimitive(primitive_type="sphere", part="x", center=(0.0, 0.0, 0.0))
        regions = [_region_for("x", (0.0, 0.0, 0.0))]
        shape_ir = _shape_ir(primitives=[bad], regions=regions)
        with self.assertRaises(ValueError):
            fuse_shape_ir(shape_ir, _game_fidelity())

    def test_missing_box_extents_raises_contract_violation(self) -> None:
        bad = ShapePrimitive(primitive_type="box", part="body", center=(0.0, 0.0, 0.0))
        regions = [_region_for("body", (0.0, 0.0, 0.0))]
        shape_ir = _shape_ir(primitives=[bad], regions=regions)
        with self.assertRaises(ContractViolation):
            fuse_shape_ir(shape_ir, _game_fidelity())


class SolidIRFromShapeTests(unittest.TestCase):
    def test_propagates_asset_name_family_and_notes(self) -> None:
        primitives = [_box("body", (0.0, 0.0, 0.0))]
        shape_ir = _shape_ir(primitives=primitives, regions=[])
        shape_ir.signature["blueprint_notes"] = ["note_a", "note_b"]
        solid_ir = solid_ir_from_shape(shape_ir)
        self.assertEqual(solid_ir.asset_name, "demo")
        self.assertEqual(solid_ir.family, "industrial_crate")
        self.assertEqual(solid_ir.notes, ["note_a", "note_b"])
        self.assertEqual(len(solid_ir.operations), 1)

    def test_operation_params_include_required_primitive_fields(self) -> None:
        box = ShapePrimitive(
            primitive_type="box",
            part="body",
            center=(1.0, 2.0, 3.0),
            extents=(4.0, 5.0, 6.0),
            tags=["seam"],
        )
        cyl = ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.0, 0.0, 0.0),
            radius=0.75,
            height=1.5,
        )
        shape_ir = _shape_ir(primitives=[box, cyl], regions=[])
        solid_ir = solid_ir_from_shape(shape_ir)
        box_op, cyl_op = solid_ir.operations
        self.assertEqual(box_op.primitive_type, "box")
        self.assertEqual(box_op.tags, ["seam"])
        self.assertEqual(box_op.params["extents"], [4.0, 5.0, 6.0])
        self.assertEqual(box_op.params["center"], [1.0, 2.0, 3.0])
        self.assertEqual(cyl_op.primitive_type, "cylinder")
        self.assertEqual(cyl_op.params["radius"], 0.75)
        self.assertEqual(cyl_op.params["height"], 1.5)


class PrimitiveSDFAndBoundsTests(unittest.TestCase):
    def test_primitive_bounds_box(self) -> None:
        box = _box("body", (1.0, 2.0, 3.0), extents=(2.0, 4.0, 6.0))
        bmin, bmax = _primitive_bounds(box)
        self.assertTrue(np.allclose(bmin, [0.0, 0.0, 0.0]))
        self.assertTrue(np.allclose(bmax, [2.0, 4.0, 6.0]))

    def test_primitive_bounds_cylinder_axes(self) -> None:
        # axis 'y' (default): radius on x/z, height on y
        cyl_y = ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.0, 0.0, 0.0),
            radius=1.0,
            height=4.0,
            axis="y",
        )
        bmin_y, bmax_y = _primitive_bounds(cyl_y)
        self.assertTrue(np.allclose(bmax_y - bmin_y, [2.0, 4.0, 2.0]))

        cyl_z = ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.0, 0.0, 0.0),
            radius=1.0,
            height=4.0,
            axis="z",
        )
        bmin_z, bmax_z = _primitive_bounds(cyl_z)
        self.assertTrue(np.allclose(bmax_z - bmin_z, [2.0, 2.0, 4.0]))

    def test_box_sdf_negative_inside_positive_outside(self) -> None:
        box = _box("body", (0.0, 0.0, 0.0), extents=(2.0, 2.0, 2.0))
        # center of box — strictly inside
        inside = _box_sdf(np.array([[0.0, 0.0, 0.0]]), box, rounding=0.0)
        self.assertLess(inside[0], 0.0)
        # far outside
        outside = _box_sdf(np.array([[10.0, 10.0, 10.0]]), box, rounding=0.0)
        self.assertGreater(outside[0], 0.0)

    def test_cylinder_sdf_negative_inside_positive_outside(self) -> None:
        cyl = ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.0, 0.0, 0.0),
            radius=1.0,
            height=2.0,
            axis="y",
        )
        inside = _cylinder_sdf(np.array([[0.0, 0.0, 0.0]]), cyl, rounding=0.0)
        self.assertLess(inside[0], 0.0)
        outside = _cylinder_sdf(np.array([[5.0, 0.0, 0.0]]), cyl, rounding=0.0)
        self.assertGreater(outside[0], 0.0)


class AssignFacePartsTests(unittest.TestCase):
    def test_face_parts_match_containing_region(self) -> None:
        # Assemble a simple ShapeIR with two disjoint regions, then hand
        # in a mesh whose centroids lie squarely inside one or the other.
        shape_ir = _shape_ir(
            primitives=[],
            regions=[
                _region_for("body", (0.0, 0.0, 0.0), extents=(2.0, 2.0, 2.0)),
                _region_for("stem", (10.0, 0.0, 0.0), extents=(2.0, 2.0, 2.0)),
            ],
        )

        # Fake a trimesh-like object exposing triangles_center
        class _FakeMesh:
            faces: ClassVar[list[int]] = [0, 1]
            triangles_center: ClassVar[np.ndarray] = np.array(
                [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]], dtype=np.float64
            )

        parts = _assign_face_parts(_FakeMesh(), shape_ir)
        self.assertEqual(parts, ["body", "stem"])

    def test_face_parts_falls_back_to_nearest_when_outside(self) -> None:
        # Centroid outside all regions — the nearest-region heuristic picks
        # one of the available parts (not a crash, not a default-to-empty).
        shape_ir = _shape_ir(
            primitives=[],
            regions=[
                _region_for("body", (0.0, 0.0, 0.0), extents=(2.0, 2.0, 2.0)),
                _region_for("stem", (10.0, 0.0, 0.0), extents=(2.0, 2.0, 2.0)),
            ],
        )

        class _FakeMesh:
            faces: ClassVar[list[int]] = [0]
            triangles_center: ClassVar[np.ndarray] = np.array([[5.0, 50.0, 50.0]], dtype=np.float64)

        parts = _assign_face_parts(_FakeMesh(), shape_ir)
        self.assertEqual(len(parts), 1)
        self.assertIn(parts[0], {"body", "stem"})


if __name__ == "__main__":
    unittest.main()
