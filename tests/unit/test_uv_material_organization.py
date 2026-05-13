"""UV/material-ID organization capability tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import trimesh
from lathe.core.mesh import RuntimeMesh
from lathe.core.stages.uv import run as run_uv_stage
from lathe.core.uv_ops import apply_box_uv
from lathe.normalizer import normalize_program
from lathe.parser import parse_file, parse_text
from lathe.resolver import materialize_asset
from lathe.surface_runtime import build_surface_bundle

ROOT = Path(__file__).resolve().parents[2]


_SOURCE = """
asset uv_material_probe: hard_surface_prop {
  intent {
    role = "console asset with production uv and material id organization"
    parts = [body, console_panel, trim_rail, screen_panel]
    materials = [painted_steel, bare_metal, signal_glass]
  }

  surface {
    materials = [painted_steel, bare_metal, signal_glass]
    zones.body = painted_steel
    zones.console_panel = signal_glass
    zones.trim_rail = bare_metal
    zones.screen_panel = signal_glass
  }

  build {
    shape {
      mode = generate
      detail_zones = [console_panel, trim_rail]
    }
    uv {
      sets = [base, lightmap]
      resolution = 128px
      chart_grouping = material
      material_id_strategy = per_material_zone
      texture_set_strategy = hero_surface_sets
      island_naming = semantic
    }
    surface {
      resolution = 64px
      maps = [basecolor, normal, orm]
      id_map = true
    }
    rig { type = none joints = [] }
    interfaces {}
  }

  validate { threshold = 0.80 }
  package { formats = [glb] }
}
"""


def _runtime_mesh() -> RuntimeMesh:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    face_parts = (
        ["body"] * 3
        + ["console_panel"] * 3
        + ["trim_rail"] * 3
        + ["screen_panel"] * (len(mesh.faces) - 9)
    )
    return RuntimeMesh(
        mesh=mesh,
        face_parts=face_parts,
        part_colors={"body": (120, 120, 120)},
        units="cm",
    )


def _asset() -> dict[str, Any]:
    return materialize_asset(parse_text(_SOURCE), "uv_material_probe")


def _shape_bundle() -> dict[str, Any]:
    return {
        "asset_graph": {"family": "console_terminal"},
        "selected_candidate_id": "cand_00",
        "candidates": [
            {
                "candidate_id": "cand_00",
                "mesh_uri": "stages\\shape\\cand_00.glb",
                "mesh_stats": {"triangle_count": 1200},
                "mesh_ir": {"bake_groups": [{"part": "body", "bake_group": "bg_body"}]},
            }
        ],
    }


def _topology_bundle() -> dict[str, Any]:
    return {
        "backend_id": "lathe.topology.blender_hard_surface_v1",
        "backend_version": "1.0.0",
        "mesh_uri": "stages\\topology\\topology.glb",
        "mesh_stats": {"triangle_count": 96},
        "part_groups": [
            {"name": "body"},
            {"name": "console_panel"},
            {"name": "trim_rail"},
            {"name": "screen_panel"},
        ],
    }


def test_uv_stage_bundle_emits_chart_manifest_and_material_ids(tmp_workspace: Path) -> None:
    asset = _asset()
    uv_dir = tmp_workspace / "uv"
    uv_dir.mkdir()
    topology_bundle = _topology_bundle()
    executor = SimpleNamespace(
        asset=asset,
        asset_name="uv_material_probe",
        selected_backends={"uv": {"id": "lathe.uv.xatlas_v1", "version": "1.0.0"}},
        runtime_config={"uv": {"adapter": "reference_box"}},
        out_dir=tmp_workspace,
        stage_dirs={"uv": uv_dir},
        runtime={
            "topology": {"bundle": topology_bundle, "runtime_mesh": _runtime_mesh()},
            "shape": {"bundle": {"shape_assessment": {}}},
        },
    )

    bundle = run_uv_stage(executor, topology_bundle)

    assert bundle["uv_organization"]["chart_grouping"] == "material"
    assert bundle["packing_report"]["chart_count"] == 3
    assert len(bundle["chart_manifest"]) == 3
    assert bundle["material_id_layout"]["count"] == 3


def test_uv_material_organization_fields_parse_and_normalize() -> None:
    program = normalize_program(parse_text(_SOURCE))
    asset = program["assets"][0]

    assert asset["build"]["uv"]["chart_grouping"] == "material"
    assert asset["build"]["uv"]["material_id_strategy"] == "per_material_zone"
    assert asset["build"]["uv"]["texture_set_strategy"] == "hero_surface_sets"
    assert asset["build"]["uv"]["island_naming"] == "semantic"
    assert asset["surface"]["zones"]["console_panel"] == "signal_glass"


def test_material_grouping_changes_box_uv_chart_structure() -> None:
    asset = _asset()
    _, material_meta = apply_box_uv(_runtime_mesh(), asset)

    part_asset = deepcopy(asset)
    part_asset["build"]["uv"]["chart_grouping"] = "part"
    _, part_meta = apply_box_uv(_runtime_mesh(), part_asset)

    assert part_meta["packing_report"]["chart_count"] == 4
    assert material_meta["packing_report"]["chart_count"] == 3
    assert material_meta["packing_report"]["semantic_grouping"] == "material"
    assert material_meta["uv_organization"]["chart_grouping"] == "material"
    assert material_meta["uv_organization"]["material_id_count"] == 3
    assert material_meta["material_id_layout"]["strategy"] == "per_material_zone"
    assert set(material_meta["material_id_layout"]["per_part"]) == {
        "body",
        "console_panel",
        "trim_rail",
        "screen_panel",
    }


def test_surface_bundle_receives_uv_chart_and_material_id_layout(tmp_workspace: Path) -> None:
    asset = _asset()
    uv_runtime, uv_meta = apply_box_uv(_runtime_mesh(), asset)
    uv_bundle = {
        "uv_organization": uv_meta["uv_organization"],
        "chart_manifest": uv_meta["chart_manifest"],
        "material_id_layout": uv_meta["material_id_layout"],
    }

    result = build_surface_bundle(
        asset=asset,
        out_dir=tmp_workspace,
        shape_bundle=_shape_bundle(),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=uv_runtime,
        uv_bundle=uv_bundle,
    )

    assert result["surface_manifest"]["uv_organization"]["chart_grouping"] == "material"
    assert result["surface_manifest"]["material_id_layout"]["count"] == 3
    assert result["atlas_assembly_ir"]["material_id_layout"]["strategy"] == "per_material_zone"
    assert len(result["atlas_assembly_ir"]["chart_manifest"]) == 3

    manifest_uri = result["surface_control_pack"]["manifest_uri"].replace("\\", "/")
    control_manifest = json.loads((tmp_workspace / Path(manifest_uri)).read_text(encoding="utf-8"))
    assert control_manifest["uv_organization"]["chart_count"] == 3
    assert control_manifest["material_id_layout"]["count"] == 3


def test_wave10_examples_parse_and_use_uv_material_id_controls() -> None:
    files = sorted((ROOT / "examples").glob("geometry_wave10_*.lth"))
    assert len(files) == 4

    for file in files:
        program = parse_file(file)
        asset = materialize_asset(program, program["assets"][0]["name"])
        uv = asset["build"]["uv"]
        surface = asset["build"]["surface"]
        assert uv["chart_grouping"] == "material"
        assert uv["material_id_strategy"] == "per_material_zone"
        assert uv["texture_set_strategy"]
        assert surface["id_map"] is True
        assert asset["package"]["game_asset_manifest"] is True
