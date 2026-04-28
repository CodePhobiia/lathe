from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import trimesh
from lathe.executor import build_asset
from lathe.net import NetGuardError, SafeResponse
from lathe.parser import parse_file
from lathe.providers.adapters.hunyuan import (
    _build_hunyuan_payload,
    _call_hunyuan_generate,
    _hunyuan_request,
    _normalize_hunyuan_result,
    _resolve_hunyuan_config,
    run_hunyuan_http_provider,
)
from lathe.providers.errors import ShapeProviderExecutionError
from lathe.providers.registry import provider_config
from lathe.shape_providers import mesh_from_point_maps, probe_shape_provider, resolve_shape_provider
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "courier_drone.lth"


class _MockHunyuanHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
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

    def log_message(self, format: str, *args: object) -> None:
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

    def __enter__(self) -> MockHunyuanServer:
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
        selection = resolve_shape_provider(
            asset, {"image_refs": [{"kind": "front", "path": "front.png"}]}, runtime_config=None
        )
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
            mesh = mesh_from_point_maps(
                point_maps, confidences, image_paths=paths, stride=1, min_confidence=0.1, max_edge_ratio=4.0
            )
        self.assertIsNotNone(mesh)
        assert mesh is not None
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.faces), 0)

    def test_hunyuan_provider_threads_allowlist_and_timeout_config(self) -> None:
        mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
        glb_bytes = mesh.export(file_type="glb")
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            image_path = work_dir / "front.png"
            Image.new("RGB", (4, 4), (80, 120, 160)).save(image_path)
            with patch(
                "lathe.providers.adapters.hunyuan._hunyuan_request",
                return_value=(glb_bytes, {"attempts": [], "final_attempt": {}}),
            ) as request:
                result = run_hunyuan_http_provider(
                    {"kind": "hard_surface_prop", "intent": {"parts": ["body"]}},
                    seed=7,
                    candidates_count=1,
                    conditioning={
                        "source_root": str(work_dir),
                        "image_refs": [{"kind": "front", "path": str(image_path)}],
                    },
                    work_dir=work_dir,
                    config={
                        "base_url": "https://hunyuan.example",
                        "timeout_s": 12,
                        "url_allowlist": ["hunyuan.example"],
                        "_build_id": "test",
                    },
                )

        self.assertEqual(len(result["candidates"]), 1)
        request.assert_called_once()
        self.assertEqual(request.call_args.kwargs["timeout_s"], 12)
        self.assertEqual(request.call_args.kwargs["allowlist"], ["hunyuan.example"])

    def test_hunyuan_config_resolution_normalizes_transport_and_auth_settings(self) -> None:
        config = _resolve_hunyuan_config(
            {
                "base_url": "https://hunyuan.example/",
                "request_timeout_s": 11,
                "max_retries": 3,
                "retry_backoff_s": 0.25,
                "url_allowlist": ["hunyuan.example"],
                "type": "OBJ",
                "_build_id": "unit",
            }
        )

        self.assertEqual(config.base_url, "https://hunyuan.example")
        self.assertEqual(config.generate_url, "https://hunyuan.example/generate")
        self.assertEqual(config.out_type, "obj")
        self.assertEqual(config.timeout_s, 11)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.retry_backoff_s, 0.25)
        self.assertEqual(config.allowlist, ["hunyuan.example"])
        self.assertEqual(config.build_id, "unit")
        self.assertEqual(config.auth.headers, {})

    def test_hunyuan_config_resolution_allows_loopback_without_explicit_allowlist(self) -> None:
        config = _resolve_hunyuan_config({"base_url": "http://127.0.0.1:8081", "url_allowlist": []})

        self.assertEqual(config.generate_url, "http://127.0.0.1:8081/generate")
        self.assertEqual(config.allowlist, ["127.0.0.1"])

    def test_hunyuan_payload_builder_is_pure_provider_payload_mapping(self) -> None:
        config = _resolve_hunyuan_config(
            {
                "base_url": "https://hunyuan.example",
                "remove_background": False,
                "texture": True,
                "octree_resolution": 128,
                "num_inference_steps": 9,
                "guidance_scale": 4.5,
                "num_chunks": 4000,
                "face_count": 12000,
                "type": "glb",
                "_build_id": "unit",
            }
        )

        payload = _build_hunyuan_payload(config, image_b64="abc123", seed=17)

        self.assertEqual(
            payload,
            {
                "image": "abc123",
                "remove_background": False,
                "texture": True,
                "seed": 17,
                "octree_resolution": 128,
                "num_inference_steps": 9,
                "guidance_scale": 4.5,
                "num_chunks": 4000,
                "face_count": 12000,
                "type": "glb",
            },
        )

    def test_hunyuan_transport_call_uses_backcompat_request_patch_point(self) -> None:
        config = _resolve_hunyuan_config(
            {
                "base_url": "https://hunyuan.example",
                "timeout_s": 12,
                "max_retries": 1,
                "retry_backoff_s": 0.5,
                "url_allowlist": ["hunyuan.example"],
                "_build_id": "unit",
            }
        )
        payload = {"image": "abc", "seed": 7, "type": "glb"}

        with patch(
            "lathe.providers.adapters.hunyuan._hunyuan_request",
            return_value=(b"glTF", {"attempts": [{"attempt": 1}], "final_attempt": {"attempt": 1}}),
        ) as request:
            raw, meta = _call_hunyuan_generate(config, payload)

        self.assertEqual(raw, b"glTF")
        self.assertEqual(meta["final_attempt"]["attempt"], 1)
        request.assert_called_once_with(
            "lathe.provider.shape.hunyuan2_1_http_v1",
            url="https://hunyuan.example/generate",
            payload=payload,
            timeout_s=12,
            max_retries=1,
            retry_backoff_s=0.5,
            allowlist=["hunyuan.example"],
        )

    def test_hunyuan_result_normalization_writes_artifact_and_execution_report(self) -> None:
        mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
        glb_bytes = mesh.export(file_type="glb")
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            image_path = work_dir / "front.png"
            Image.new("RGB", (4, 4), (80, 120, 160)).save(image_path)
            config = _resolve_hunyuan_config(
                {
                    "base_url": "https://hunyuan.example",
                    "url_allowlist": ["hunyuan.example"],
                    "_build_id": "unit",
                }
            )
            payload = _build_hunyuan_payload(config, image_b64="abc", seed=7)

            candidate, execution = _normalize_hunyuan_result(
                asset={"kind": "hard_surface_prop", "intent": {"parts": ["body"]}},
                conditioning={
                    "source_root": str(work_dir),
                    "image_refs": [{"kind": "front", "path": str(image_path)}],
                },
                source_image=image_path,
                payload=payload,
                raw=glb_bytes,
                response_meta={"attempts": [{"attempt": 1}], "final_attempt": {"attempt": 1}},
                work_dir=work_dir,
                provider_config=config,
                candidate_index=0,
            )

        self.assertEqual(
            candidate["meta"]["conditioning"]["provider"], "lathe.provider.shape.hunyuan2_1_http_v1"
        )
        self.assertEqual(execution["request"]["source_image"], "front.png")
        self.assertEqual(execution["request"]["seed"], 7)
        self.assertTrue(
            Path(execution["response"]["artifact_path"]).name.startswith("hunyuan_candidate_unit_00")
        )
        self.assertGreater(execution["response"]["artifact_size_bytes"], 0)

    def test_hunyuan_result_normalization_rejects_non_glb_response_before_mesh_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            image_path = work_dir / "front.png"
            Image.new("RGB", (4, 4), (80, 120, 160)).save(image_path)
            config = _resolve_hunyuan_config(
                {
                    "base_url": "https://hunyuan.example",
                    "url_allowlist": ["hunyuan.example"],
                    "_build_id": "unit",
                }
            )
            payload = _build_hunyuan_payload(config, image_b64="abc", seed=7)

            with self.assertRaises(ShapeProviderExecutionError) as ctx:
                _normalize_hunyuan_result(
                    asset={"kind": "hard_surface_prop", "intent": {"parts": ["body"]}},
                    conditioning={
                        "source_root": str(work_dir),
                        "image_refs": [{"kind": "front", "path": str(image_path)}],
                    },
                    source_image=image_path,
                    payload=payload,
                    raw=b"not a mesh",
                    response_meta={"attempts": [{"attempt": 1}], "final_attempt": {"attempt": 1}},
                    work_dir=work_dir,
                    provider_config=config,
                    candidate_index=0,
                )

            self.assertEqual(ctx.exception.code, "invalid_mesh")
            self.assertFalse((work_dir / "hunyuan_candidate_unit_00.glb").exists())

    def test_hunyuan_provider_rejects_image_ref_outside_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "work"
            source_root = Path(tmpdir) / "src"
            work_dir.mkdir()
            source_root.mkdir()
            outside = Path(tmpdir) / "outside.png"
            Image.new("RGB", (4, 4), (80, 120, 160)).save(outside)

            with self.assertRaises(ShapeProviderExecutionError) as ctx:
                run_hunyuan_http_provider(
                    {"kind": "hard_surface_prop", "intent": {"parts": ["body"]}},
                    seed=7,
                    candidates_count=1,
                    conditioning={
                        "source_root": str(source_root),
                        "image_refs": [{"kind": "front", "path": str(outside)}],
                    },
                    work_dir=work_dir,
                    config={"base_url": "https://hunyuan.example"},
                )

        self.assertEqual(ctx.exception.code, "unsafe_image_ref")

    def test_hunyuan_provider_rejects_oversized_image_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "work"
            source_root = Path(tmpdir) / "src"
            work_dir.mkdir()
            source_root.mkdir()
            image_path = source_root / "front.png"
            image_path.write_bytes(b"x" * 8)

            with (
                patch("lathe.providers.adapters.hunyuan._MAX_IMAGE_BYTES", 4),
                self.assertRaises(ShapeProviderExecutionError) as ctx,
            ):
                run_hunyuan_http_provider(
                    {"kind": "hard_surface_prop", "intent": {"parts": ["body"]}},
                    seed=7,
                    candidates_count=1,
                    conditioning={
                        "source_root": str(source_root),
                        "image_refs": [{"kind": "front", "path": str(image_path)}],
                    },
                    work_dir=work_dir,
                    config={"base_url": "https://hunyuan.example"},
                )

        self.assertEqual(ctx.exception.code, "image_file_too_large")

    def test_hunyuan_request_denies_disallowed_url_before_network(self) -> None:
        with self.assertRaises(ShapeProviderExecutionError) as ctx:
            _hunyuan_request(
                "lathe.provider.shape.hunyuan2_1_http_v1",
                url="https://example.com/generate",
                payload={"image": "x", "seed": 1, "type": "glb"},
                timeout_s=1,
                max_retries=0,
                retry_backoff_s=0.0,
                allowlist=["hunyuan.example"],
            )

        self.assertEqual(ctx.exception.code, "host_not_allowlisted")

    def test_hunyuan_request_denies_missing_allowlist_before_network(self) -> None:
        with self.assertRaises(ShapeProviderExecutionError) as ctx:
            _hunyuan_request(
                "lathe.provider.shape.hunyuan2_1_http_v1",
                url="https://hunyuan.example/generate",
                payload={"image": "x", "seed": 1, "type": "glb"},
                timeout_s=1,
                max_retries=0,
                retry_backoff_s=0.0,
                allowlist=None,
            )

        self.assertEqual(ctx.exception.code, "host_not_allowlisted")

    def test_hunyuan_request_retries_timeout_and_reports_failure(self) -> None:
        with (
            patch(
                "lathe.providers.transport.http.safe_urlopen",
                side_effect=TimeoutError("timed out"),
            ) as request,
            self.assertRaises(ShapeProviderExecutionError) as ctx,
        ):
            _hunyuan_request(
                "lathe.provider.shape.hunyuan2_1_http_v1",
                url="https://hunyuan.example/generate",
                payload={"image": "abc", "seed": 1, "type": "glb"},
                timeout_s=1,
                max_retries=1,
                retry_backoff_s=0.0,
                allowlist=["hunyuan.example"],
            )

        self.assertEqual(ctx.exception.code, "request_failed")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(len(ctx.exception.details["attempts"]), 2)

    def test_hunyuan_request_rejects_empty_success_body_as_malformed_response(self) -> None:
        response = SafeResponse(status=200, content_type="model/gltf-binary", body=b"")
        with (
            patch("lathe.providers.transport.http.safe_urlopen", return_value=response),
            self.assertRaises(ShapeProviderExecutionError) as ctx,
        ):
            _hunyuan_request(
                "lathe.provider.shape.hunyuan2_1_http_v1",
                url="https://hunyuan.example/generate",
                payload={"image": "abc", "seed": 1, "type": "glb"},
                timeout_s=1,
                max_retries=0,
                retry_backoff_s=0.0,
                allowlist=["hunyuan.example"],
            )

        self.assertEqual(ctx.exception.code, "empty_response")

    def test_hunyuan_request_maps_oversized_response_to_provider_error(self) -> None:
        error = NetGuardError(
            "response_too_large", "Response body exceeded 4 bytes", details={"max_bytes": 4}
        )
        with (
            patch("lathe.providers.transport.http.safe_urlopen", side_effect=error),
            self.assertRaises(ShapeProviderExecutionError) as ctx,
        ):
            _hunyuan_request(
                "lathe.provider.shape.hunyuan2_1_http_v1",
                url="https://hunyuan.example/generate",
                payload={"image": "abc", "seed": 1, "type": "glb"},
                timeout_s=1,
                max_retries=1,
                retry_backoff_s=0.0,
                allowlist=["hunyuan.example"],
            )

        self.assertEqual(ctx.exception.code, "response_too_large")
        self.assertEqual(ctx.exception.details["max_bytes"], 4)

    def test_hunyuan_runtime_config_requires_base_url_before_provider_construction(self) -> None:
        runtime_config = {
            "shape": {
                "providers": {
                    "hunyuan2_1_http": {
                        "base_url": "",
                    }
                }
            }
        }

        with self.assertRaises(ShapeProviderExecutionError) as ctx:
            provider_config(runtime_config, "hunyuan2_1_http")

        self.assertEqual(ctx.exception.code, "missing_base_url")

    def test_hunyuan_runtime_config_rejects_invalid_scheme_before_provider_construction(self) -> None:
        runtime_config = {
            "shape": {
                "providers": {
                    "hunyuan2_1_http": {
                        "base_url": "ftp://localhost:8081",
                    }
                }
            }
        }

        with self.assertRaises(ShapeProviderExecutionError) as ctx:
            provider_config(runtime_config, "hunyuan2_1_http")

        self.assertEqual(ctx.exception.code, "scheme_insecure")

    def test_hunyuan_runtime_config_allows_loopback_http_before_provider_construction(self) -> None:
        for base_url in ("http://localhost:8081", "http://127.0.0.1:8081", "http://[::1]:8081"):
            with self.subTest(base_url=base_url):
                config = provider_config(
                    {
                        "shape": {
                            "providers": {
                                "hunyuan2_1_http": {
                                    "base_url": base_url,
                                }
                            }
                        }
                    },
                    "hunyuan2_1_http",
                )

                self.assertEqual(config["base_url"], base_url)

    def test_hunyuan_runtime_config_rejects_non_loopback_http_before_provider_construction(self) -> None:
        runtime_config = {
            "shape": {
                "providers": {
                    "hunyuan2_1_http": {
                        "base_url": "http://hunyuan.example:8081",
                    }
                }
            }
        }

        with self.assertRaises(ShapeProviderExecutionError) as ctx:
            provider_config(runtime_config, "hunyuan2_1_http")

        self.assertEqual(ctx.exception.code, "scheme_insecure")

    def test_hunyuan_runtime_config_rejects_bad_timeout_before_provider_construction(self) -> None:
        runtime_config = {
            "shape": {
                "providers": {
                    "hunyuan2_1_http": {
                        "base_url": "https://hunyuan.example",
                        "timeout_s": 0,
                    }
                }
            }
        }

        with self.assertRaises(ShapeProviderExecutionError) as ctx:
            provider_config(runtime_config, "hunyuan2_1_http")

        self.assertEqual(ctx.exception.code, "invalid_runtime_config")
        self.assertEqual(ctx.exception.details["key"], "timeout_s")

    def test_hunyuan_runtime_config_rejects_allowlist_denial_before_provider_construction(self) -> None:
        runtime_config = {
            "shape": {
                "providers": {
                    "hunyuan2_1_http": {
                        "base_url": "https://hunyuan.example",
                        "url_allowlist": ["other.example"],
                    }
                }
            }
        }

        with self.assertRaises(ShapeProviderExecutionError) as ctx:
            provider_config(runtime_config, "hunyuan2_1_http")

        self.assertEqual(ctx.exception.code, "host_not_allowlisted")

    @pytest.mark.slow
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
            self.assertEqual(
                bundle["provider_report"]["selected_provider_id"], "lathe.provider.shape.hunyuan2_1_http_v1"
            )
            self.assertEqual(
                bundle["provider_report"]["actual_provider_id"], "lathe.provider.shape.hunyuan2_1_http_v1"
            )
            self.assertEqual(bundle["provider_report"]["status"], "success")
            self.assertIn("execution", bundle["provider_report"])
            self.assertGreaterEqual(len(bundle["provider_report"]["execution"]["executions"]), 1)
            self.assertEqual(bundle["conformance_report"]["mode"], "provider_deltas_rejected")
            self.assertIn("proposal_bank", bundle["conformance_report"])
            selected_id = bundle["selected_candidate_id"]
            selected = next(item for item in bundle["candidates"] if item["candidate_id"] == selected_id)
            joined = " ".join(selected["selection_notes"]).lower()
            self.assertIn("native assembly", joined)

    @pytest.mark.slow
    def test_hunyuan_provider_retries_transient_failure(self) -> None:
        example_program = parse_file(EXAMPLE)
        mesh = trimesh.creation.box(extents=[72.0, 24.0, 88.0])
        glb_bytes = mesh.export(file_type="glb")
        with (
            MockHunyuanServer(glb_bytes, failures_before_success=1) as server,
            tempfile.TemporaryDirectory() as tmpdir,
        ):
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
