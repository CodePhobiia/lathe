"""Unit tests for ``lathe.surface_runtime.build_surface_bundle``.

The surface runtime governs the V1.2 authoring bridge: it resolves the
authoring backend (deterministic PBR vs Codex ImageGen) under the
surface policy, selects the atlas/control pack path, and emits bakes
for hero families. Non-hero families short-circuit to
``lathe.surface.semantic_passthrough_v1`` — a pass-through bundle that
carries the manifest and backend report but skips the expensive bake
kernel. These tests exercise:

* passthrough (no-op) path — ``surface_backend="none"``-equivalent
* full V1.2 policy surface_policy fan-in (fields forwarded to manifest)
* codex imagegen requested with unavailable governed bridge under the
  ``fail`` policy (RuntimeError)
* mask_program + trim_sheet + decal_library field flow-through
* hero family + full bake with no runtime_config (deterministic fallback)

We use mostly the passthrough path to avoid touching PIL image IO; one
hero-family test covers the bake path with a ``tmp_workspace`` and a
minimal runtime mesh built on a ``trimesh`` box.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import trimesh
from lathe.core.mesh import RuntimeMesh
from lathe.surface_runtime import build_surface_bundle


def _asset(
    *,
    family: str = "console_terminal",
    surface_overrides: dict[str, Any] | None = None,
    build_surface_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_build_surface: dict[str, Any] = {
        "workflow": "metallic_roughness",
        "resolution": 1024,
        "maps": ["basecolor", "normal", "roughness"],
        "bakes": [],
        "decals": [],
    }
    if build_surface_overrides:
        base_build_surface.update(build_surface_overrides)
    surface: dict[str, Any] = {
        "materials": ["aluminum", "brass"],
        "program": "",
        "material_graph": "",
        "palette": "",
        "material_zones": [],
        "bake": [],
        "decals": [],
        "decal_libraries": [],
        "mask_programs": [],
        "trim_sheets": [],
        "policy": "",
    }
    if surface_overrides:
        surface.update(surface_overrides)
    return {
        "build": {"surface": base_build_surface},
        "surface": surface,
        "intent": {"parts": ["body", "panel"], "materials": ["aluminum", "brass"]},
        "assembly": {"resolved_components": []},
    }


def _shape_bundle(family: str = "console_terminal") -> dict[str, Any]:
    return {
        "asset_graph": {"family": family},
        "selected_candidate_id": "cand_00",
        "candidates": [
            {
                "candidate_id": "cand_00",
                "mesh_uri": "stages\\shape\\cand_00.glb",
                "mesh_stats": {"triangle_count": 12000},
                "mesh_ir": {"bake_groups": [{"part": "body", "bake_group": "bg_body"}]},
            }
        ],
    }


def _topology_bundle() -> dict[str, Any]:
    return {
        "mesh_uri": "stages\\topology\\topology.glb",
        "mesh_stats": {"triangle_count": 3200},
        "part_groups": [{"name": "body"}, {"name": "panel"}],
    }


def _runtime_mesh() -> RuntimeMesh:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    face_parts = ["body"] * len(mesh.faces)
    return RuntimeMesh(mesh=mesh, face_parts=face_parts, part_colors={"body": (120, 120, 120)}, units="cm")


class TestBuildSurfaceBundle:
    def test_surface_backend_none_is_passthrough_for_non_hero(self, tmp_workspace: Path) -> None:
        asset = _asset(family="generic_widget", surface_overrides={"authoring": {"backend": "none"}})
        shape_bundle = _shape_bundle(family="generic_widget")
        result = build_surface_bundle(
            asset=asset,
            out_dir=tmp_workspace,
            shape_bundle=shape_bundle,
            shape_runtime_mesh=_runtime_mesh(),
            topology_bundle=_topology_bundle(),
            uv_runtime_mesh=_runtime_mesh(),
        )
        assert result["backend_id"] == "lathe.surface.semantic_passthrough_v1"
        assert result["surface_manifest"]["hero_surface"] is False
        # Passthrough must NOT have written maps / control pack / outputs.
        assert "outputs" not in result
        assert "surface_control_pack" not in result

    def test_full_v12_surface_policy_flows_through_manifest(self, tmp_workspace: Path) -> None:
        asset = _asset(
            family="generic_widget",
            surface_overrides={
                "decal_libraries": ["std.surface.decal_library.industrial_v1"],
                "mask_programs": ["std.surface.mask.seam_highlight_v1"],
                "trim_sheets": ["std.surface.trim.metal_strips_v1"],
                "policy": "std.surface.policy.game_pbr_v1",
                "program": "std.surface.program.console_v1",
                "palette": "std.palette.console_v1",
                "resolved_surface_program": {
                    "values": {
                        "workflow": "metallic_roughness",
                        "maps": ["basecolor", "normal", "roughness", "ao"],
                        "patterns": ["hex_mesh_v1"],
                        "decals": ["service_label"],
                    }
                },
                "resolved_surface_policy": {
                    "values": {
                        "maps": ["emissive"],
                        "resolution": 2048,
                        "on_backend_unavailable": "fallback_deterministic",
                    }
                },
            },
            build_surface_overrides={
                "bake_profile": "std.surface.bake_profile.hero_v1",
                "render_fixture": "std.surface.render.booth_v1",
            },
        )
        asset["build"]["surface"]["resolved_bake_profile"] = {"values": {"maps": ["curvature"]}}
        result = build_surface_bundle(
            asset=asset,
            out_dir=tmp_workspace,
            shape_bundle=_shape_bundle(family="generic_widget"),
            shape_runtime_mesh=_runtime_mesh(),
            topology_bundle=_topology_bundle(),
            uv_runtime_mesh=_runtime_mesh(),
        )
        manifest = result["surface_manifest"]
        assert manifest["patterns"][0] == "hex_mesh_v1"
        assert "decal_library_std_surface_decal_library_industrial_v1" in manifest["patterns"]
        assert "trim_sheet_std_surface_trim_metal_strips_v1" in manifest["patterns"]
        assert manifest["decal_libraries"] == ["std.surface.decal_library.industrial_v1"]
        assert manifest["mask_programs"] == ["std.surface.mask.seam_highlight_v1"]
        assert manifest["trim_sheets"] == ["std.surface.trim.metal_strips_v1"]
        assert set(manifest["library_driven_decals"]) >= {"hazard_stripe", "trim_sheet_metal_strips"}
        assert manifest["surface_policy"] == "std.surface.policy.game_pbr_v1"
        assert manifest["bake_profile"] == "std.surface.bake_profile.hero_v1"
        assert manifest["render_fixture"] == "std.surface.render.booth_v1"
        assert "emissive" in manifest["maps"]
        assert result["surface_manifest"]["resolution"] == 2048

    def test_codex_imagegen_requested_without_bridge_fails_under_fail_policy(
        self, tmp_workspace: Path
    ) -> None:
        asset = _asset(
            family="generic_widget",
            surface_overrides={
                "authoring": {"backend": "codex_imagegen_v1"},
                "resolved_surface_policy": {"values": {"on_backend_unavailable": "fail"}},
            },
        )
        with pytest.raises(RuntimeError, match="Codex ImageGen"):
            build_surface_bundle(
                asset=asset,
                out_dir=tmp_workspace,
                shape_bundle=_shape_bundle(family="generic_widget"),
                shape_runtime_mesh=_runtime_mesh(),
                topology_bundle=_topology_bundle(),
                uv_runtime_mesh=_runtime_mesh(),
            )

    def test_missing_decal_library_does_not_raise_for_passthrough(self, tmp_workspace: Path) -> None:
        # Non-strict: missing decal library is a soft omission for the
        # passthrough path — the manifest simply carries an empty list.
        asset = _asset(family="generic_widget")
        result = build_surface_bundle(
            asset=asset,
            out_dir=tmp_workspace,
            shape_bundle=_shape_bundle(family="generic_widget"),
            shape_runtime_mesh=_runtime_mesh(),
            topology_bundle=_topology_bundle(),
            uv_runtime_mesh=_runtime_mesh(),
        )
        assert result["surface_manifest"]["decal_libraries"] == []
        assert result["surface_manifest"]["trim_sheets"] == []

    def test_mask_program_fallback_propagates_through_manifest(self, tmp_workspace: Path) -> None:
        asset = _asset(
            family="generic_widget",
            surface_overrides={"mask_programs": ["std.surface.mask.fallback_v1"]},
        )
        result = build_surface_bundle(
            asset=asset,
            out_dir=tmp_workspace,
            shape_bundle=_shape_bundle(family="generic_widget"),
            shape_runtime_mesh=_runtime_mesh(),
            topology_bundle=_topology_bundle(),
            uv_runtime_mesh=_runtime_mesh(),
        )
        assert result["surface_manifest"]["mask_programs"] == ["std.surface.mask.fallback_v1"]

    def test_hero_family_emits_full_bake_bundle(self, tmp_workspace: Path) -> None:
        """Hero family drives the full bake + control-pack path.

        Uses a small 128px resolution and a unit-box runtime mesh to keep
        the bake deterministic and cheap. We assert the bundle shape
        (backend id, HighLowRelation presence, map outputs) without
        inspecting pixel contents.
        """
        asset = _asset(
            family="console_terminal",
            build_surface_overrides={"resolution": 128, "maps": ["basecolor", "normal"]},
        )
        shape_bundle = _shape_bundle(family="console_terminal")
        result = build_surface_bundle(
            asset=asset,
            out_dir=tmp_workspace,
            shape_bundle=shape_bundle,
            shape_runtime_mesh=_runtime_mesh(),
            topology_bundle=_topology_bundle(),
            uv_runtime_mesh=_runtime_mesh(),
        )
        assert result["backend_id"] == "lathe.surface.hero_pbr_v1"
        assert result["surface_manifest"]["hero_surface"] is True
        assert set(result["outputs"].keys()) >= {
            "basecolor",
            "normal",
            "ao",
            "curvature",
            "id",
            "orm",
            "emissive",
        }
        assert result["highlow_relation"]["authoritative"] is True
        assert result["highlow_relation"]["source"] == "hero_surface_runtime_v1"
        maps_dir = tmp_workspace / "maps"
        assert (maps_dir / "basecolor.png").exists()
        assert (maps_dir / "normal.png").exists()

    def test_missing_selected_high_mesh_remains_none(self, tmp_workspace: Path) -> None:
        asset = _asset(
            family="console_terminal",
            build_surface_overrides={"resolution": 128, "maps": ["basecolor", "normal"]},
        )
        shape_bundle = _shape_bundle(family="console_terminal")
        shape_bundle["selected_candidate_id"] = "missing_candidate"

        result = build_surface_bundle(
            asset=asset,
            out_dir=tmp_workspace,
            shape_bundle=shape_bundle,
            shape_runtime_mesh=_runtime_mesh(),
            topology_bundle=_topology_bundle(),
            uv_runtime_mesh=_runtime_mesh(),
        )

        assert result["highlow_relation"]["high_mesh_uri"] is None
        assert result["highlow_relation"]["low_mesh_uri"] == "stages\\topology\\topology.glb"
        assert result["highlow_relation"]["distinction_ratio"] == 0.0
