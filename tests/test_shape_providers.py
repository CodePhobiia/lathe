from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import numpy as np
import trimesh
from PIL import Image

from lathe.executor import build_asset
from lathe.parser import parse_file
from lathe.shape_providers import mesh_from_point_maps, probe_shape_provider, resolve_shape_provider


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "courier_drone.lth"


class _MockHunyuanHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/generate":
            self.send_error(404)
            return
        self.server.request_count += 1  # type: ignore[attr-defined]
        if self.server.request_count <= self.server.failures_before_success:  # type: ignore[attr-defined]
            body = json.dumps({"status": "retry"}).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        required = {"image", "seed", "type"}
        missing = sorted(required - set(payload))
        if missing:
            self.send_error(400, f"Missing keys: {missing}")
            return
        body = self.server.glb_bytes  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "model/gltf-binary")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class MockHunyuanServer:
    def __init__(self, glb_bytes: bytes, *, failures_before_success: int = 0) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _MockHunyuanHandler)
        self.server.glb_bytes = glb_bytes  # type: ignore[attr-defined]
        self.server.failures_before_success = failures_before_success  # type: ignore[attr-defined]
        self.server.request_count = 0  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> "MockHunyuanServer":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class LatheShapeProviderTests(unittest.TestCase):
    def test_default_provider_selection_prefers_reference_fallback_without_runtime_config(self) -> None:
        program = parse_file(EXAMPLE)
        asset = next(item for item in program["assets"] if item["name"] == "courier_drone")
        selection = resolve_shape_provider(asset, {"image_refs": [{"kind": "front", "path": "front.png"}]}, runtime_config=None)
        self.assertEqual(selection["provider"]["id"], "lathe.provider.shape.reference_conditioned_v1")
        self.assertEqual(selection["selected_via"], "default_fallback")

    def test_mesh_from_point_maps_succeeds_on_synthetic_plane(self) -> None:
        h, w = 8, 8
        xs = np.linspace(-1.0, 1.0, num=w, dtype=np.float32)
        ys = np.linspace(-1.0, 1.0, num=h, dtype=np.float32)
        grid_x, grid_y = np.meshgrid(xs, ys)
        plane0 = np.stack([grid_x, grid_y, np.zeros_like(grid_x)], axis=-1)
        plane1 = np.stack([grid_x + 0.1, grid_y, np.zeros_like(grid_x) + 0.05], axis=-1)
        point_maps = np.stack([plane0, plane1], axis=0)
        confidences = np.ones((2, h, w), dtype=np.float32)
        mesh = mesh_from_point_maps(point_maps, confidences, stride=1, min_confidence=0.1, max_edge_ratio=4.0)
        self.assertIsNotNone(mesh)
        assert mesh is not None
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.faces), 0)

    def test_mesh_from_point_maps_supports_image_paths(self) -> None:
        h, w = 8, 8
        xs = np.linspace(-1.0, 1.0, num=w, dtype=np.float32)
        ys = np.linspace(-1.0, 1.0, num=h, dtype=np.float32)
        grid_x, grid_y = np.meshgrid(xs, ys)
        plane0 = np.stack([grid_x, grid_y, np.zeros_like(grid_x)], axis=-1)
        plane1 = np.stack([grid_x + 0.1, grid_y, np.zeros_like(grid_x) + 0.05], axis=-1)
        point_maps = np.stack([plane0, plane1], axis=0)
        confidences = np.ones((2, h, w), dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths: list[Path] = []
            for index in range(2):
                image = Image.new("RGB", (8, 8), (80 + index * 30, 120, 160))
                path = Path(tmpdir) / f"view_{index}.png"
                image.save(path)
                paths.append(path)
            mesh = mesh_from_point_maps(point_maps, confidences, image_paths=paths, stride=1, min_confidence=0.1, max_edge_ratio=4.0)
        self.assertIsNotNone(mesh)
        assert mesh is not None
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.faces), 0)

    def test_hunyuan_provider_probe_and_build(self) -> None:
        example_program = parse_file(EXAMPLE)
        mesh = trimesh.creation.box(extents=[72.0, 24.0, 88.0])
        glb_bytes = mesh.export(file_type="glb")
        with MockHunyuanServer(glb_bytes) as server, tempfile.TemporaryDirectory() as tmpdir:
            probe = probe_shape_provider(
                "hunyuan2_1_http",
                runtime_config={"shape": {"providers": {"hunyuan2_1_http": {"base_url": server.base_url}}}},
            )
            self.assertTrue(probe["available"])
            out_dir = Path(tmpdir) / "courier_drone"
            runtime_config = {
                "shape": {
                    "provider": "hunyuan2_1_http",
                    "strict": True,
                    "providers": {
                        "hunyuan2_1_http": {
                            "base_url": server.base_url,
                            "type": "glb",
                            "texture": False,
                            "octree_resolution": 128,
                            "num_inference_steps": 4,
                        }
                    },
                }
            }
            report = build_asset(example_program, "courier_drone", out_dir, runtime_config=runtime_config)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["provider_report"]["selected_provider_id"], "lathe.provider.shape.hunyuan2_1_http_v1")
            self.assertEqual(bundle["provider_report"]["actual_provider_id"], "lathe.provider.shape.hunyuan2_1_http_v1")
            self.assertEqual(bundle["provider_report"]["status"], "success")
            self.assertIn("execution", bundle["provider_report"])
            self.assertGreaterEqual(len(bundle["provider_report"]["execution"]["executions"]), 1)
            self.assertEqual(bundle["conformance_report"]["mode"], "provider_deltas_rejected")
            self.assertIn("proposal_bank", bundle["conformance_report"])
            selected_id = bundle["selected_candidate_id"]
            selected = next(item for item in bundle["candidates"] if item["candidate_id"] == selected_id)
            joined = " ".join(selected["selection_notes"]).lower()
            self.assertIn("native assembly", joined)

    def test_hunyuan_provider_retries_transient_failure(self) -> None:
        example_program = parse_file(EXAMPLE)
        mesh = trimesh.creation.box(extents=[72.0, 24.0, 88.0])
        glb_bytes = mesh.export(file_type="glb")
        with MockHunyuanServer(glb_bytes, failures_before_success=1) as server, tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "courier_drone"
            runtime_config = {
                "shape": {
                    "provider": "hunyuan2_1_http",
                    "strict": True,
                    "providers": {
                        "hunyuan2_1_http": {
                            "base_url": server.base_url,
                            "type": "glb",
                            "max_retries": 2,
                            "retry_backoff_s": 0.01,
                        }
                    },
                }
            }
            report = build_asset(example_program, "courier_drone", out_dir, runtime_config=runtime_config)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            executions = bundle["provider_report"]["execution"]["executions"]
            self.assertGreaterEqual(len(executions[0]["response"]["attempts"]), 2)

    def test_vggt_provider_probe_reports_unavailable_details(self) -> None:
        with patch(
            "lathe.shape_providers._probe_vggt",
            return_value={
                "available": False,
                "issues": ["torch is not installed", "vggt package is not installed"],
                "code": "unavailable",
            },
        ):
            probe = probe_shape_provider("vggt_local")
        self.assertFalse(probe["available"])
        self.assertEqual(probe["code"], "unavailable")
        self.assertIn("torch is not installed", probe["message"])


if __name__ == "__main__":
    unittest.main()
