"""Unit tests for ``lathe.mesh_finalize.finalize_mesh_ir``.

``finalize_mesh_ir`` turns a fused ``trimesh.Trimesh`` into a ``MeshIR``
carrying per-face part labels, seam/hard-edge/bake classification, and
material zones derived from the source ``ShapeIR.regions``. The function
itself does no geometric repair (welding/manifold fix lives further
upstream in the fusion kernel) — it's a label and metadata packaging
step with a deterministic contract. These tests cover that contract:
label length alignment, region classification routing, and graceful
handling of mismatched inputs.
"""

from __future__ import annotations

import unittest

import numpy as np
import trimesh

from lathe.mesh_finalize import finalize_mesh_ir
from lathe.mesh_ir import MeshIR
from lathe.shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


def _unit_box_mesh() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(2.0, 2.0, 2.0))


def _region(
    *, name: str = "r_body", part: str = "body", component: str = "hull"
) -> ShapeRegion:
    return ShapeRegion(
        name=name,
        part=part,
        component=component,
        center=(0.0, 0.0, 0.0),
        extents=(2.0, 2.0, 2.0),
    )


def _shape_ir(regions: list[ShapeRegion]) -> ShapeIR:
    return ShapeIR(
        asset_name="demo",
        family="industrial_crate",
        blueprint_id="bp1",
        symmetry_axis=None,
        units="cm",
        primitives=[],
        regions=regions,
        primitives_used=[],
        part_graph=[],
        signature={},
    )


class FinalizeMeshIRTests(unittest.TestCase):
    def test_happy_finalize_with_matching_face_parts(self) -> None:
        mesh = _unit_box_mesh()
        shape_ir = _shape_ir([_region()])
        face_parts = ["body"] * len(mesh.faces)
        mesh_ir = finalize_mesh_ir(mesh, shape_ir, face_parts)

        self.assertIsInstance(mesh_ir, MeshIR)
        self.assertEqual(mesh_ir.asset_name, "demo")
        self.assertEqual(mesh_ir.family, "industrial_crate")
        self.assertEqual(len(mesh_ir.vertices), len(mesh.vertices))
        self.assertEqual(len(mesh_ir.faces), len(mesh.faces))
        self.assertEqual(len(mesh_ir.face_parts), len(mesh.faces))
        self.assertTrue(all(p == "body" for p in mesh_ir.face_parts))

    def test_mismatched_face_parts_length_falls_back_to_region_part(self) -> None:
        # face_parts length != face count → finalize substitutes the first
        # region's part for every face rather than raising.
        mesh = _unit_box_mesh()
        shape_ir = _shape_ir([_region(part="hull_plate")])
        wrong_length = ["body", "lid"]  # != len(mesh.faces)
        mesh_ir = finalize_mesh_ir(mesh, shape_ir, wrong_length)

        self.assertEqual(len(mesh_ir.face_parts), len(mesh.faces))
        self.assertTrue(all(p == "hull_plate" for p in mesh_ir.face_parts))

    def test_empty_regions_falls_back_to_mesh_label(self) -> None:
        # When both face_parts length is wrong and no regions exist,
        # the fallback label is the literal string "mesh".
        mesh = _unit_box_mesh()
        shape_ir = _shape_ir([])
        mesh_ir = finalize_mesh_ir(mesh, shape_ir, [])

        self.assertEqual(len(mesh_ir.face_parts), len(mesh.faces))
        self.assertTrue(all(p == "mesh" for p in mesh_ir.face_parts))
        self.assertEqual(mesh_ir.seam_classes, [])
        self.assertEqual(mesh_ir.hard_edge_classes, [])
        self.assertEqual(mesh_ir.bake_groups, [])
        self.assertEqual(mesh_ir.material_zones, [])

    def test_seam_and_material_classes_select_panel_like_components(self) -> None:
        mesh = _unit_box_mesh()
        regions = [
            _region(name="r_body", part="body", component="hull"),
            _region(name="r_lid", part="lid", component="lid"),
            _region(name="r_panel", part="panel", component="panel"),
            _region(name="r_vent", part="vent", component="vent"),
            _region(name="r_lock", part="lock_plate", component="lock_plate"),
        ]
        shape_ir = _shape_ir(regions)
        face_parts = ["body"] * len(mesh.faces)
        mesh_ir = finalize_mesh_ir(mesh, shape_ir, face_parts)

        seam_names = {entry["name"] for entry in mesh_ir.seam_classes}
        self.assertEqual(seam_names, {"r_lid", "r_panel"})

        material_names = {entry["name"] for entry in mesh_ir.material_zones}
        self.assertEqual(material_names, {"r_panel", "r_lock"})

        # hard_edge_classes includes every region; vent is marked not sharp.
        sharp_by_name = {entry["name"]: entry["sharp"] for entry in mesh_ir.hard_edge_classes}
        self.assertEqual(len(sharp_by_name), len(regions))
        self.assertFalse(sharp_by_name["r_vent"])
        self.assertTrue(sharp_by_name["r_body"])
        self.assertTrue(sharp_by_name["r_lid"])

        # bake_groups mirror regions 1:1 and tag each with the part name.
        self.assertEqual(len(mesh_ir.bake_groups), len(regions))
        by_name = {entry["name"]: entry for entry in mesh_ir.bake_groups}
        self.assertEqual(by_name["r_lid"]["bake_group"], "lid")

    def test_metadata_defaults_to_empty_and_passes_through_when_given(self) -> None:
        mesh = _unit_box_mesh()
        shape_ir = _shape_ir([_region()])
        mesh_ir_default = finalize_mesh_ir(mesh, shape_ir, ["body"] * len(mesh.faces))
        self.assertEqual(mesh_ir_default.metadata, {})

        payload = {"integration_report": {"mode": "exact"}, "seed": 42}
        mesh_ir_meta = finalize_mesh_ir(
            mesh, shape_ir, ["body"] * len(mesh.faces), metadata=payload
        )
        self.assertEqual(mesh_ir_meta.metadata, payload)

    def test_vertices_are_rounded_to_six_decimals(self) -> None:
        # finalize rounds vertices to 6 decimals before materialization —
        # this is the determinism contract against float-drift downstream.
        verts = np.array(
            [
                [0.000000123456789, 0.0, 0.0],
                [1.0, 1.0000005, 0.0],
                [0.5, 0.5, 1.9999994],
            ],
            dtype=np.float64,
        )
        faces = np.array([[0, 1, 2]], dtype=np.int64)
        mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        shape_ir = _shape_ir([_region()])
        mesh_ir = finalize_mesh_ir(mesh, shape_ir, ["body"])

        # Each coordinate must be rounded to <= 6 decimals of precision.
        for vert in mesh_ir.vertices:
            for coord in vert:
                self.assertAlmostEqual(coord, round(coord, 6), places=9)
        self.assertEqual(len(mesh_ir.faces), 1)
        self.assertEqual(mesh_ir.face_parts, ["body"])

    def test_large_mesh_round_trip_preserves_face_count(self) -> None:
        mesh = trimesh.creation.icosphere(subdivisions=3)
        self.assertGreater(len(mesh.faces), 500)
        shape_ir = _shape_ir([_region(part="hull")])
        face_parts = ["hull"] * len(mesh.faces)
        mesh_ir = finalize_mesh_ir(mesh, shape_ir, face_parts)

        self.assertEqual(len(mesh_ir.faces), len(mesh.faces))
        self.assertEqual(len(mesh_ir.face_parts), len(mesh.faces))
        self.assertEqual(len(mesh_ir.vertices), len(mesh.vertices))


if __name__ == "__main__":
    unittest.main()
