"""Wave 1 geometry-detail controls for scaffold generation."""

from __future__ import annotations

from pathlib import Path

from lathe.asset_graph import build_asset_graph
from lathe.parser import parse_text
from lathe.resolver import materialize_asset
from lathe.scaffold_compiler import compile_scaffold_candidates


def _conditioning() -> dict:
    return {"reference_strength": 0.0, "image_refs": [], "material_refs": [], "mesh_refs": []}


def _source_with_detail_controls() -> str:
    return """
asset detailed_probe: hard_surface_prop {
  intent {
    role = "geometry detail probe"
    parts = [body, service_panel, socket_plate]
  }

  build {
    shape {
      mode = generate
      symmetry = x
      detail_density = hero
      edge_complexity = high
      edge_treatment = beveled
      panelization = high
      groove_density = high
      ridge_density = high
      greeble_density = high
      surface_layer_count = 3
      modular_attachment_points = 4
      detail_zones = [body]
    }
    rig { type = none joints = [] }
    interfaces {}
  }

  validate { threshold = 0.80 }
}
"""


def _asset(shape_controls: dict) -> dict:
    return {
        "name": "detail_probe",
        "kind": "hard_surface_prop",
        "intent": {
            "role": "geometry detail probe",
            "parts": ["body", "service_panel", "socket_plate"],
        },
        "features": {},
        "build": {
            "shape": {"mode": "generate", "symmetry": "x", **shape_controls},
            "rig": {},
            "interfaces": {},
        },
        "validate": {"threshold": 0.80},
        "experimental": {},
    }


def _compile(shape_controls: dict) -> dict:
    return compile_scaffold_candidates(
        build_asset_graph(_asset(shape_controls)),
        seed=113,
        candidates_count=1,
        conditioning=_conditioning(),
        mode="generate",
    )


def test_shape_detail_knobs_parse_and_materialize() -> None:
    program = parse_text(_source_with_detail_controls())
    raw_shape = program["assets"][0]["build"]["shape"]
    assert raw_shape["detail_density"] == "hero"
    assert raw_shape["edge_treatment"] == "beveled"
    assert raw_shape["detail_zones"] == ["body"]

    materialized = materialize_asset(program, "detailed_probe")
    graph = build_asset_graph(materialized)
    controls = graph.authoring["shape_controls"]
    assert controls["panelization"] == "high"
    assert controls["surface_layer_count"] == 3.0
    assert graph.authoring["feature_density"] == ""


def test_geometry_detail_controls_add_real_shape_primitives_and_runtime_metadata() -> None:
    low = _compile(
        {
            "detail_density": "low",
            "edge_complexity": 0,
            "panelization": 0,
            "groove_density": 0,
            "ridge_density": 0,
            "greeble_density": 0,
            "surface_layer_count": 0,
            "modular_attachment_points": 0,
            "detail_zones": ["body"],
        }
    )
    high = _compile(
        {
            "detail_density": "hero",
            "edge_complexity": "high",
            "edge_treatment": "beveled",
            "panelization": "high",
            "groove_density": "high",
            "ridge_density": "high",
            "greeble_density": "high",
            "surface_layer_count": 3,
            "modular_attachment_points": 4,
            "detail_zones": ["body"],
        }
    )

    low_ir = low["shape_irs"][0]
    high_ir = high["shape_irs"][0]
    low_detail_count = int(low_ir.assessment.get("geometry_detail_feature_count", 0) or 0)
    high_detail_count = int(high_ir.assessment.get("geometry_detail_feature_count", 0) or 0)
    assert high_detail_count > low_detail_count
    assert high_ir.assessment["primitive_count"] > low_ir.assessment["primitive_count"]
    assert len(high["runtime_candidates"][0]["mesh"].faces) > len(low["runtime_candidates"][0]["mesh"].faces)

    feature_types = set(high_ir.assessment["geometry_detail_feature_types"])
    assert {
        "bolt_grid",
        "corner_guard",
        "groove_channel",
        "layer_plate",
        "panel_seam",
        "raised_ridge",
        "socket_point",
    }.issubset(feature_types)

    runtime_report = high["runtime_candidates"][0]["meta"]["feature_report"]
    assert runtime_report["geometry_detail_controls"]["detail_zones"] == ["body"]
    assert runtime_report["geometry_detail_feature_count"] == high_ir.assessment["geometry_detail_feature_count"]


def test_wave1_examples_exist_and_use_geometry_detail_controls() -> None:
    examples = sorted(Path("examples").glob("geometry_wave1_*.lth"))
    assert len(examples) >= 23
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        assert len(program["assets"]) == 1
        shape = program["assets"][0]["build"]["shape"]
        assert "detail_density" in shape
        assert any(
            key in shape
            for key in (
                "panelization",
                "groove_density",
                "ridge_density",
                "greeble_density",
                "surface_layer_count",
                "modular_attachment_points",
            )
        )
