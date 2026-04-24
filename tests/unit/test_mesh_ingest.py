"""Unit tests for ``lathe.mesh_ingest.safe_load_mesh`` (SEC-2 + SEC-NEW-1)."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import trimesh

from lathe.errors import ShapeMeshLoadError, ShapeProviderExecutionError
from lathe.mesh_ingest import safe_load_mesh


def _write_valid_glb(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    mesh.export(path.as_posix())


class SafeLoadMeshHappyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_loads_small_valid_glb(self) -> None:
        path = self.tmp / "box.glb"
        _write_valid_glb(path)
        mesh = safe_load_mesh(path)
        self.assertIsInstance(mesh, trimesh.Trimesh)
        self.assertGreater(len(mesh.faces), 0)
        self.assertGreater(len(mesh.vertices), 0)


class SafeLoadMeshRejectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rejects_oversized(self) -> None:
        path = self.tmp / "big.glb"
        _write_valid_glb(path)
        with self.assertRaises(ShapeMeshLoadError) as ctx:
            safe_load_mesh(path, max_bytes=16)
        self.assertEqual(ctx.exception.code, "oversized")

    def test_rejects_disallowed_format(self) -> None:
        path = self.tmp / "bad.txt"
        path.write_bytes(b"not a mesh at all")
        with self.assertRaises(ShapeMeshLoadError) as ctx:
            safe_load_mesh(path)
        self.assertEqual(ctx.exception.code, "format_disallowed")
        self.assertEqual(ctx.exception.details.get("ext"), ".txt")

    def test_rejects_magic_mismatch_glb(self) -> None:
        path = self.tmp / "fake.glb"
        # Wrong magic: first bytes aren't ``glTF``.
        path.write_bytes(b"XXXX" + b"\x00" * 200)
        with self.assertRaises(ShapeMeshLoadError) as ctx:
            safe_load_mesh(path)
        self.assertEqual(ctx.exception.code, "magic_mismatch")

    def test_rejects_magic_mismatch_ply(self) -> None:
        path = self.tmp / "fake.ply"
        path.write_bytes(b"NOPE" + b"\x00" * 20)
        with self.assertRaises(ShapeMeshLoadError) as ctx:
            safe_load_mesh(path)
        self.assertEqual(ctx.exception.code, "magic_mismatch")

    def test_rejects_binary_stl_bad_count(self) -> None:
        path = self.tmp / "fake.stl"
        # 80-byte header + claim a billion faces with no body -> bogus.
        header = b"\x00" * 80
        count = struct.pack("<I", 1_000_000_000)
        path.write_bytes(header + count)
        with self.assertRaises(ShapeMeshLoadError) as ctx:
            safe_load_mesh(path)
        self.assertEqual(ctx.exception.code, "magic_mismatch")

    def test_rejects_trimesh_load_failure(self) -> None:
        path = self.tmp / "corrupt.glb"
        # Valid magic bytes but the rest is garbage -> trimesh will fail.
        path.write_bytes(b"glTF" + b"\xff" * 256)
        with self.assertRaises(ShapeMeshLoadError) as ctx:
            safe_load_mesh(path)
        self.assertEqual(ctx.exception.code, "trimesh_error")


class SafeLoadMeshPostLoadSanityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rejects_face_count_over_limit(self) -> None:
        path = self.tmp / "box.glb"
        _write_valid_glb(path)
        huge_faces = np.zeros((6_000_000, 3), dtype=np.int64)
        fake_mesh = mock.MagicMock(spec=trimesh.Trimesh)
        fake_mesh.faces = huge_faces
        fake_mesh.vertices = np.zeros((3, 3), dtype=float)
        fake_mesh.bounds = np.zeros((2, 3), dtype=float)
        with mock.patch("lathe.mesh_ingest.trimesh.load", return_value=fake_mesh):
            with self.assertRaises(ShapeMeshLoadError) as ctx:
                safe_load_mesh(path)
        self.assertEqual(ctx.exception.code, "post_load_sanity")
        self.assertEqual(ctx.exception.details.get("field"), "faces")

    def test_rejects_nan_vertex(self) -> None:
        path = self.tmp / "box.glb"
        _write_valid_glb(path)
        nan_vertices = np.array([[0.0, 0.0, 0.0], [float("nan"), 1.0, 2.0]], dtype=float)
        fake_mesh = mock.MagicMock(spec=trimesh.Trimesh)
        fake_mesh.faces = np.zeros((1, 3), dtype=np.int64)
        fake_mesh.vertices = nan_vertices
        fake_mesh.bounds = np.zeros((2, 3), dtype=float)
        with mock.patch("lathe.mesh_ingest.trimesh.load", return_value=fake_mesh):
            with self.assertRaises(ShapeMeshLoadError) as ctx:
                safe_load_mesh(path)
        self.assertEqual(ctx.exception.code, "post_load_sanity")
        self.assertEqual(ctx.exception.details.get("field"), "vertices")


class ProviderIntegrationTests(unittest.TestCase):
    """Verify ``_load_mesh_file`` delegates to ``safe_load_mesh`` (SEC-NEW-1)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_provider_loader_invokes_safe_load_mesh(self) -> None:
        from lathe.providers import mesh_ops

        path = self.tmp / "box.glb"
        _write_valid_glb(path)

        with mock.patch(
            "lathe.providers.mesh_ops.safe_load_mesh",
            wraps=mesh_ops.safe_load_mesh,
        ) as spy:
            result = mesh_ops._load_mesh_file(path)
        self.assertEqual(spy.call_count, 1)
        self.assertIsNotNone(result)

    def test_provider_loader_reraises_as_provider_error(self) -> None:
        from lathe.providers import mesh_ops

        path = self.tmp / "bad.txt"
        path.write_bytes(b"garbage")
        with self.assertRaises(ShapeProviderExecutionError) as ctx:
            mesh_ops._load_mesh_file(path)
        self.assertEqual(ctx.exception.code, "mesh_load_failed")
        self.assertIsInstance(ctx.exception.__cause__, ShapeMeshLoadError)


if __name__ == "__main__":
    unittest.main()
