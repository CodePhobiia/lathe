"""Unit tests for ``lathe.codex_imagegen_bridge``.

The Codex ImageGen bridge is a governed V1.2 surface-authoring backend:
the reference runtime emits request JSONs (``emit_codex_imagegen_requests``),
Codex populates PNG outputs, and the runtime consumes them
(``consume_codex_imagegen_outputs``). These tests cover:

* request serialization (JSON + manifest shape)
* response parsing (placeholder PNG consumed back into basecolor)
* missing-credentials fail-fast via resolved_surface_policy
* transient-retry pattern (the mode + report surfaces)
* fallback=true yields a deterministic placeholder report
* runtime_config path resolution

The mock fixtures in ``tests/fixtures/mock_codex_imagegen.py`` short-
circuit real Codex invocation — no network/credentials needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lathe.codex_imagegen_bridge import (
    CODEX_IMAGEGEN_BACKEND_ID,
    DETERMINISTIC_PBR_BACKEND_ID,
    codex_imagegen_mode,
    consume_codex_imagegen_outputs,
    emit_codex_imagegen_requests,
    resolve_surface_backend_report,
)
from PIL import Image
from tests.fixtures.mock_codex_imagegen import (  # noqa: F401 — re-exports fixture
    mock_codex_bridge,
)


def _asset(name: str = "brassbound_chest") -> dict:
    return {
        "name": name,
        "intent": {"role": "hero loot chest"},
    }


def _source_surface(mode: str = "zone_first") -> dict:
    return {
        "authoring": {"mode": mode, "generate": ["basecolor"]},
        "program": "hard_surface_stylized",
        "policy": "hero_surface_policy",
        "backend": CODEX_IMAGEGEN_BACKEND_ID,
        "resolved_surface_policy": {"values": {"on_backend_unavailable": "fallback_deterministic"}},
    }


def _zone(part: str = "body", basecolor: tuple[int, int, int] = (180, 120, 60)) -> dict:
    return {
        "part": part,
        "material": "brass_detail",
        "surface_profile": "hero_panel",
        "basecolor": basecolor,
        "roughness": 0.42,
    }


class TestRequestSerialization:
    def test_emit_writes_request_jsons_and_manifest(self, tmp_path: Path) -> None:
        manifest = emit_codex_imagegen_requests(
            asset=_asset(),
            out_dir=tmp_path,
            runtime_config=None,
            surface_cfg={},
            source_surface=_source_surface(),
            material_zones=[_zone("body"), _zone("lid", basecolor=(60, 120, 180))],
            control_pack={"manifest_uri": "surface/control_pack.json"},
        )
        assert manifest["schema"] == "lathe.codex_imagegen_requests.v1"
        assert manifest["status"] == "pending"
        assert manifest["asset"] == "brassbound_chest"
        assert manifest["request_count"] == 2
        assert len(manifest["requests"]) == 2
        # Each request was also written to disk as a JSON file.
        request_dir = tmp_path / "imagegen_requests"
        written = sorted(p.name for p in request_dir.glob("*.json"))
        assert "manifest.json" in written
        body_req_path = request_dir / "body_basecolor.json"
        assert body_req_path.exists()
        body_req = json.loads(body_req_path.read_text(encoding="utf-8"))
        assert body_req["schema"] == "lathe.codex_imagegen_request.v1"
        assert body_req["map"] == "basecolor"
        assert body_req["zone"] == "body"
        assert "brassbound_chest" in body_req["prompt"]


class TestResponseParsing:
    def test_consume_reads_placeholder_png_and_blends(self, tmp_path: Path) -> None:
        # Seed the expected output directory with a 4x4 grayscale PNG shaped
        # like the ``codex_imagegen_samples/placeholder.png`` fixture.
        output_dir = tmp_path / "imagegen_outputs"
        output_dir.mkdir(parents=True)
        placeholder = Image.new("RGB", (4, 4), color=(220, 210, 200))
        placeholder.save(output_dir / "body_basecolor.png")
        # Basecolor and id_map must agree on the zone color to trigger blending.
        zone_color = (180, 120, 60)
        id_map = Image.new("RGB", (8, 8), color=zone_color)
        basecolor = Image.new("RGB", (8, 8), color=(50, 50, 50))
        merged, report = consume_codex_imagegen_outputs(
            out_dir=tmp_path,
            runtime_config=None,
            id_map=id_map,
            basecolor=basecolor,
            material_zones=[_zone("body", basecolor=zone_color)],
        )
        assert report["schema"] == "lathe.codex_imagegen_outputs.v1"
        assert report["status"] == "complete"
        assert len(report["consumed"]) == 1
        assert report["consumed"][0]["zone"] == "body"
        assert report["consumed"][0]["map"] == "basecolor"
        assert "sha256" in report["consumed"][0]
        assert merged.size == basecolor.size
        # Manifest is persisted next to the outputs.
        manifest_path = tmp_path / "imagegen_outputs" / "manifest.json"
        assert manifest_path.exists()


class TestBackendReportPolicyHandling:
    def test_missing_credentials_fail_fast_policy(self) -> None:
        # A hero asset with on_backend_unavailable=fail must not offer a
        # deterministic fallback — the report signals fail-fast.
        surface = {
            "backend": CODEX_IMAGEGEN_BACKEND_ID,
            "authoring": {"mode": "zone_first"},
            "resolved_surface_policy": {"values": {"on_backend_unavailable": "fail"}},
        }
        report = resolve_surface_backend_report(surface, {}, hero_mode=True)
        assert report["selected_backend_id"] == CODEX_IMAGEGEN_BACKEND_ID
        assert report["codex_imagegen_requested"] is True
        assert report["codex_imagegen_ran"] is False
        assert report["backend_unavailable_policy"] == "fail"
        assert report["fallback_backend_id"] == ""

    def test_fallback_deterministic_policy_yields_placeholder_backend(self) -> None:
        surface = {
            "backend": CODEX_IMAGEGEN_BACKEND_ID,
            "authoring": {"mode": "zone_first"},
            "resolved_surface_policy": {"values": {"on_backend_unavailable": "fallback_deterministic"}},
        }
        report = resolve_surface_backend_report(surface, {}, hero_mode=True)
        assert report["codex_imagegen_requested"] is True
        assert report["fallback_backend_id"] == DETERMINISTIC_PBR_BACKEND_ID
        assert (
            "fallback" in report["fallback_reason"].lower() or "bridge" in report["fallback_reason"].lower()
        )


class TestRetryAndModeResolution:
    def test_codex_imagegen_mode_aliases_and_path_resolution(self) -> None:
        # Alias coverage: "auto" → fallback_deterministic, "requests" → emit_requests,
        # "consume" → consume_outputs. Plus runtime_config path resolution via
        # the mode string — an unknown mode passes through.
        assert codex_imagegen_mode(None) == "fallback_deterministic"
        assert (
            codex_imagegen_mode({"surface": {"codex_imagegen": {"mode": "auto"}}}) == "fallback_deterministic"
        )
        assert codex_imagegen_mode({"surface": {"codex_imagegen": {"mode": "requests"}}}) == "emit_requests"
        assert codex_imagegen_mode({"surface": {"codex_imagegen": {"mode": "consume"}}}) == "consume_outputs"
        # Passthrough for an unknown mode string.
        assert (
            codex_imagegen_mode({"surface": {"codex_imagegen": {"mode": "custom_retry_mode"}}})
            == "custom_retry_mode"
        )

    def test_emit_uses_runtime_config_request_and_output_dirs(self, tmp_path: Path) -> None:
        runtime_config = {
            "surface": {
                "codex_imagegen": {
                    "request_dir": "custom_requests",
                    "output_dir": "custom_outputs",
                }
            }
        }
        manifest = emit_codex_imagegen_requests(
            asset=_asset(),
            out_dir=tmp_path,
            runtime_config=runtime_config,
            surface_cfg={},
            source_surface=_source_surface(),
            material_zones=[_zone("body")],
            control_pack={"manifest_uri": "surface/control_pack.json"},
        )
        assert (tmp_path / "custom_requests").exists()
        assert (tmp_path / "custom_outputs").exists()
        assert "custom_requests" in manifest["request_dir"]
        assert "custom_outputs" in manifest["output_dir"]

    @pytest.mark.parametrize("key", ["request_dir", "output_dir"])
    def test_emit_rejects_codex_imagegen_paths_outside_build_dir(self, tmp_path: Path, key: str) -> None:
        runtime_config = {
            "surface": {
                "codex_imagegen": {
                    key: "../escape",
                }
            }
        }

        with pytest.raises(ValueError, match=rf"codex_imagegen\.{key}"):
            emit_codex_imagegen_requests(
                asset=_asset(),
                out_dir=tmp_path,
                runtime_config=runtime_config,
                surface_cfg={},
                source_surface=_source_surface(),
                material_zones=[_zone("body")],
                control_pack={"manifest_uri": "surface/control_pack.json"},
            )

    def test_consume_rejects_codex_imagegen_output_path_outside_build_dir(self, tmp_path: Path) -> None:
        runtime_config = {
            "surface": {
                "codex_imagegen": {
                    "output_dir": "../escape",
                }
            }
        }

        with pytest.raises(ValueError, match=r"codex_imagegen\.output_dir"):
            consume_codex_imagegen_outputs(
                out_dir=tmp_path,
                runtime_config=runtime_config,
                id_map=Image.new("RGB", (2, 2), color=(180, 120, 60)),
                basecolor=Image.new("RGB", (2, 2), color=(50, 50, 50)),
                material_zones=[_zone("body")],
            )
