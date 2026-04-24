"""Unit tests for ``lathe.mesh_ir.MeshIR``.

``MeshIR`` is the downstream handoff structure under the stable
``lathe.shape.intent_mesh_handoff_v1`` contract. It carries plain
Python lists (not numpy arrays) so that ``to_dict`` is JSON-round-trip
safe — those invariants are exercised here.

There is no ``MeshIR.from_dict`` method on the current dataclass; we
exercise the round trip via ``MeshIR(**payload)`` which is how
``lathe.geometry_kernel._FUSION_CACHE`` rehydrates cached meshes.
"""

from __future__ import annotations

import unittest

import numpy as np
import trimesh

from lathe.mesh_ir import MeshIR


def _unit_box_trimesh() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(2.0, 2.0, 2.0))


def _mesh_ir_from_trimesh(mesh: trimesh.Trimesh) -> MeshIR:
    faces = np.asarray(mesh.faces, dtype=np.int64)
    return MeshIR(
        asset_name="demo",
        family="industrial_crate",
        vertices=np.asarray(mesh.vertices, dtype=np.float64).tolist(),
        faces=faces.tolist(),
        face_parts=["body"] * int(len(faces)),
    )


class MeshIRConstructionTests(unittest.TestCase):
    def test_round_trip_from_trimesh(self) -> None:
        mesh = _unit_box_trimesh()
        ir = _mesh_ir_from_trimesh(mesh)
        self.assertEqual(len(ir.vertices), len(mesh.vertices))
        self.assertEqual(len(ir.faces), len(mesh.faces))
        self.assertEqual(len(ir.face_parts), len(mesh.faces))
        # to_trimesh should produce an equivalent mesh
        rebuilt = ir.to_trimesh()
        self.assertEqual(len(rebuilt.vertices), len(mesh.vertices))
        self.assertEqual(len(rebuilt.faces), len(mesh.faces))
        self.assertTrue(np.allclose(np.asarray(rebuilt.vertices), np.asarray(mesh.vertices)))

    def test_empty_mesh(self) -> None:
        ir = MeshIR(
            asset_name="empty",
            family="industrial_crate",
            vertices=[],
            faces=[],
            face_parts=[],
        )
        rebuilt = ir.to_trimesh()
        self.assertEqual(len(rebuilt.vertices), 0)
        self.assertEqual(len(rebuilt.faces), 0)

    def test_vertices_only_no_faces(self) -> None:
        # Cloud of vertices with no faces is valid: face_parts and faces both empty.
        ir = MeshIR(
            asset_name="cloud",
            family="industrial_crate",
            vertices=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            faces=[],
            face_parts=[],
        )
        rebuilt = ir.to_trimesh()
        self.assertEqual(len(rebuilt.vertices), 3)
        self.assertEqual(len(rebuilt.faces), 0)

    def test_default_optional_collections(self) -> None:
        mesh = _unit_box_trimesh()
        ir = _mesh_ir_from_trimesh(mesh)
        self.assertEqual(ir.material_zones, [])
        self.assertEqual(ir.seam_classes, [])
        self.assertEqual(ir.hard_edge_classes, [])
        self.assertEqual(ir.bake_groups, [])
        self.assertEqual(ir.metadata, {})


class MeshIRSerializationTests(unittest.TestCase):
    def test_to_dict_preserves_core_arrays(self) -> None:
        mesh = _unit_box_trimesh()
        ir = _mesh_ir_from_trimesh(mesh)
        payload = ir.to_dict()
        self.assertEqual(payload["asset_name"], "demo")
        self.assertEqual(payload["family"], "industrial_crate")
        self.assertEqual(len(payload["vertices"]), len(ir.vertices))
        self.assertEqual(len(payload["faces"]), len(ir.faces))
        self.assertEqual(payload["face_parts"], ir.face_parts)

    def test_dict_roundtrip_idempotent(self) -> None:
        # This is the round trip used by _FUSION_CACHE:
        # MeshIR -> to_dict -> MeshIR(**payload) -> to_dict again
        mesh = _unit_box_trimesh()
        original = _mesh_ir_from_trimesh(mesh)
        original.metadata["integration_report"] = {"mode": "exact_boolean_union", "cache_hit": False}
        payload_a = original.to_dict()
        restored = MeshIR(**payload_a)
        payload_b = restored.to_dict()
        self.assertEqual(payload_a, payload_b)
        # vertices/faces match exactly — list round-trip is lossless
        self.assertEqual(restored.vertices, original.vertices)
        self.assertEqual(restored.faces, original.faces)
        self.assertEqual(restored.face_parts, original.face_parts)
        self.assertEqual(restored.metadata, original.metadata)

    def test_face_parts_length_matches_face_count(self) -> None:
        # The contract the downstream topology/UV stages rely on: one
        # part label per face. An IR where these drift silently would
        # let bad data flow downstream — this test documents the invariant.
        mesh = _unit_box_trimesh()
        faces = np.asarray(mesh.faces, dtype=np.int64).tolist()
        ir = MeshIR(
            asset_name="demo",
            family="industrial_crate",
            vertices=np.asarray(mesh.vertices, dtype=np.float64).tolist(),
            faces=faces,
            face_parts=["body"] * len(faces),
        )
        self.assertEqual(len(ir.face_parts), len(ir.faces))

    def test_metadata_payload_round_trips(self) -> None:
        mesh = _unit_box_trimesh()
        ir = _mesh_ir_from_trimesh(mesh)
        ir.metadata = {
            "integration_report": {
                "mode": "sdf_voxel_fusion",
                "pitch": 2.35,
                "dims": [32, 32, 32],
                "primitive_count": 2,
            },
            "provider_trace": {
                "attempted": "lathe.provider.shape.learned_v1",
                "actual": "lathe.provider.shape.reference_conditioned_v1",
            },
        }
        payload = ir.to_dict()
        restored = MeshIR(**payload)
        self.assertEqual(restored.metadata, ir.metadata)
        # deeply nested values survive
        self.assertEqual(
            restored.metadata["integration_report"]["dims"], [32, 32, 32]
        )


if __name__ == "__main__":
    unittest.main()
