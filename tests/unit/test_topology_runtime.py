"""Unit tests for ``lathe.topology_runtime``.

The topology runtime is a thin semantic derivation layer: it translates
the shape stage's ``shape_bundle`` (regions + integration reports) into a
topology-focused dict (hard-edge groups, panel seams, bake groups) and
decides whether the integrated shape should be preserved rather than
re-topologized. Actual re-topology happens in
``lathe/core/stages/topology.py`` via a Blender subprocess or the
deterministic reference cleanup — the *dispatch* decision rests on the
two functions under test here.

These tests cover both the capability-present (Blender reachable) and
capability-absent (fallback) paths. We don't drive the subprocess itself
(that's a stages-level concern) — instead we drive
``should_preserve_integrated_shape`` which is the gate the stage consults
before invoking Blender at all, and we verify the derivation output holds
its feature-semantics contract regardless of adapter availability.
"""

from __future__ import annotations

from typing import Any

import pytest
from lathe.topology_runtime import derive_topology_semantics, should_preserve_integrated_shape


def _shape_bundle(
    *,
    regions: list[dict[str, Any]] | None = None,
    candidate_id: str = "cand_00",
    integration_mode: str | None = "sdf_voxel_fusion",
    assessment: dict[str, Any] | None = None,
    watertight: bool = True,
) -> dict[str, Any]:
    if regions is None:
        regions = [
            {"name": "panel_front", "part": "body", "component": "panel"},
            {"name": "grille_vent", "part": "body", "component": "vent"},
            {"name": "lid_top", "part": "lid", "component": "lid"},
            {"name": "body_shell", "part": "body", "component": "hull"},
        ]
    candidate: dict[str, Any] = {"candidate_id": candidate_id}
    if integration_mode is not None:
        candidate["integration_report"] = {"mode": integration_mode}
    candidate["mesh_stats"] = {"watertight": watertight}
    return {
        "shape_ir": [{"regions": regions}],
        "selected_candidate_id": candidate_id,
        "candidates": [candidate],
        "shape_assessment": assessment or {"silhouette_ok": True, "score": 0.92},
    }


class TestDeriveTopologySemantics:
    def test_derive_with_blender_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "lathe.capabilities.probe_blender",
            lambda cfg=None: {"available": True, "path": "C:/fake/blender.exe", "code": "ok"},
        )
        bundle = _shape_bundle()
        result = derive_topology_semantics(bundle)
        assert {g["name"] for g in result["hard_edge_groups"]} == {
            "panel_front",
            "grille_vent",
            "lid_top",
            "body_shell",
        }
        assert "panel_front" in result["panel_seams"]
        assert "lid_top" in result["panel_seams"]
        assert "body_shell" not in result["panel_seams"]
        vent = next(g for g in result["hard_edge_groups"] if g["name"] == "grille_vent")
        assert vent["edge_class"] == "grille"
        hull = next(g for g in result["hard_edge_groups"] if g["name"] == "body_shell")
        assert hull["edge_class"] == "hard_surface_feature"

    def test_derive_with_blender_absent_reference_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "lathe.capabilities.probe_blender",
            lambda cfg=None: {"available": False, "path": None, "code": "not_found"},
        )
        bundle = _shape_bundle()
        result = derive_topology_semantics(bundle)
        assert result["feature_semantics"] == bundle["shape_assessment"]
        assert len(result["bake_groups"]) == len(bundle["shape_ir"][0]["regions"])
        boundary_names = {g["name"] for g in result["bake_groups"] if g["material_boundary"]}
        assert "panel_front" in boundary_names
        assert "grille_vent" not in boundary_names

    def test_empty_shape_ir_returns_empty_scaffolding(self) -> None:
        result = derive_topology_semantics({"shape_ir": []})
        assert result == {
            "hard_edge_groups": [],
            "panel_seams": [],
            "bake_groups": [],
            "feature_semantics": {},
            "generated_uv_semantics": {},
        }

    def test_malformed_shape_bundle_missing_region_keys_raises(self) -> None:
        bad = {"shape_ir": [{"regions": [{"component": "panel"}]}]}
        with pytest.raises(KeyError):
            derive_topology_semantics(bad)


class TestShouldPreserveIntegratedShape:
    def test_preserve_true_for_sdf_voxel_fusion(self) -> None:
        bundle = _shape_bundle(integration_mode="sdf_voxel_fusion")
        assert should_preserve_integrated_shape(bundle) is True

    def test_preserve_true_for_exact_component_assembly(self) -> None:
        bundle = _shape_bundle(integration_mode="exact_component_assembly")
        assert should_preserve_integrated_shape(bundle) is True

    def test_preserve_true_for_watertight_exact_boolean_manifold_kernel(self) -> None:
        bundle = _shape_bundle(integration_mode="exact_boolean_manifold_kernel", watertight=True)
        assert should_preserve_integrated_shape(bundle) is True

    def test_preserve_false_for_nonwatertight_exact_boolean_manifold_kernel(self) -> None:
        bundle = _shape_bundle(integration_mode="exact_boolean_manifold_kernel", watertight=False)
        assert should_preserve_integrated_shape(bundle) is False

    def test_preserve_false_when_adapter_forced(self) -> None:
        bundle = _shape_bundle(integration_mode="sdf_voxel_fusion")
        runtime_config = {"topology": {"adapter": "cleanup"}}
        assert should_preserve_integrated_shape(bundle, runtime_config) is False

    def test_preserve_false_for_unselected_candidate(self) -> None:
        bundle = _shape_bundle()
        bundle["selected_candidate_id"] = "does_not_exist"
        assert should_preserve_integrated_shape(bundle) is False

    def test_preserve_false_for_non_fusion_mode(self) -> None:
        bundle = _shape_bundle(integration_mode="proposal_only")
        assert should_preserve_integrated_shape(bundle) is False

    def test_attempted_vs_actual_provider_tracing_retained(self) -> None:
        """The derivation must not strip provenance the caller passes through.

        ``derive_topology_semantics`` itself only produces feature semantics,
        but the bundle's ``shape_assessment`` is the field the stage layer
        uses to propagate attempted-vs-actual provider traces downstream —
        we assert round-tripping holds under the stable contract.
        """
        assessment = {
            "attempted_provider": "lathe.provider.shape.vggt_local_v1",
            "actual_provider": "lathe.provider.shape.reference_conditioned_v1",
            "fallback_reason": "torch_unavailable",
        }
        bundle = _shape_bundle(assessment=assessment)
        result = derive_topology_semantics(bundle)
        assert result["feature_semantics"] == assessment
        assert (
            result["feature_semantics"]["attempted_provider"]
            != result["feature_semantics"]["actual_provider"]
        )
