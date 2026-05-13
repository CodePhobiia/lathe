"""Surface story placement capability tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from lathe.core.mesh import RuntimeMesh
from lathe.parser import parse_file
from lathe.resolver import materialize_asset
from lathe.surface_runtime import build_surface_bundle
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def _asset(targets: list[str], asymmetry: str = "hero_asymmetric") -> dict[str, Any]:
    return {
        "build": {
            "surface": {
                "workflow": "metallic_roughness",
                "resolution": 128,
                "maps": ["basecolor", "normal", "roughness"],
                "bakes": [],
                "decals": [],
                "id_map": True,
            }
        },
        "surface": {
            "materials": ["painted_steel", "signal_glass", "bare_metal"],
            "zones": {
                "body": "painted_steel",
                "screen_panel": "signal_glass",
                "warning_label": "bare_metal",
            },
            "story_decals": ["unit_17", "scrape_cluster", "red_bar", "heat_warning"],
            "story_targets": targets,
            "story_density": "hero",
            "story_asymmetry": asymmetry,
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
        },
        "intent": {
            "parts": ["body", "screen_panel", "warning_label"],
            "materials": ["painted_steel", "signal_glass", "bare_metal"],
        },
        "assembly": {"resolved_components": []},
    }


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
        "mesh_uri": "stages\\topology\\topology.glb",
        "mesh_stats": {"triangle_count": 96},
        "part_groups": [{"name": "body"}, {"name": "screen_panel"}, {"name": "warning_label"}],
    }


def _runtime_mesh() -> RuntimeMesh:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    face_parts = ["body"] * 4 + ["screen_panel"] * 4 + ["warning_label"] * (len(mesh.faces) - 8)
    return RuntimeMesh(mesh=mesh, face_parts=face_parts, part_colors={"body": (120, 120, 120)}, units="cm")


def _build(tmp_path: Path, targets: list[str]) -> dict[str, Any]:
    return build_surface_bundle(
        asset=_asset(targets),
        out_dir=tmp_path,
        shape_bundle=_shape_bundle(),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
        uv_bundle={
            "material_id_layout": {
                "per_part": {
                    "body": "matid_01_painted_steel",
                    "screen_panel": "matid_02_signal_glass",
                    "warning_label": "matid_03_bare_metal",
                }
            }
        },
    )


def _image(root: Path, bundle: dict[str, Any], name: str) -> np.ndarray:
    return np.asarray(Image.open(root / bundle["outputs"][name]["uri"]).convert("RGB"), dtype=np.float64)


def test_story_targets_produce_placement_plan_and_move_visible_marks(tmp_path: Path) -> None:
    body_dir = tmp_path / "body"
    screen_dir = tmp_path / "screen"
    body = _build(body_dir, ["body"])
    screen = _build(screen_dir, ["screen_panel"])

    body_plan = body["surface_story_placement_plan"]
    screen_plan = screen["surface_story_placement_plan"]
    assert body_plan["density"] == "hero"
    assert body_plan["asymmetry"] == "hero_asymmetric"
    assert body_plan["placement_count"] == 4
    assert {entry["target_part"] for entry in body_plan["placements"]} == {"body"}
    assert {entry["target_part"] for entry in screen_plan["placements"]} == {"screen_panel"}
    assert body_plan["placements"][0]["material_id"] == "matid_01_painted_steel"
    assert screen_plan["placements"][0]["material_id"] == "matid_02_signal_glass"
    assert body_plan["placements"][0]["anchor_uv"] != screen_plan["placements"][0]["anchor_uv"]

    base_delta = np.mean(np.abs(_image(body_dir, body, "basecolor") - _image(screen_dir, screen, "basecolor")))
    assert base_delta > 0.5

    manifest_uri = body["surface_control_pack"]["manifest_uri"].replace("\\", "/")
    control_manifest = json.loads((body_dir / Path(manifest_uri)).read_text(encoding="utf-8"))
    assert control_manifest["surface_story_placement_plan"]["placement_count"] == 4
    assert body["atlas_assembly_ir"]["surface_story_placement_plan"]["placements"][0]["target_part"] == "body"


def test_wave11_examples_parse_and_use_story_placement_controls() -> None:
    files = sorted((ROOT / "examples").glob("geometry_wave11_*.lth"))
    assert len(files) == 4

    for file in files:
        program = parse_file(file)
        asset = materialize_asset(program, program["assets"][0]["name"])
        surface = asset["surface"]
        assert surface["story_decals"]
        assert surface["story_targets"]
        assert surface["story_density"]
        assert surface["story_asymmetry"]
        assert asset["build"]["surface"]["id_map"] is True
        assert asset["package"]["game_asset_manifest"] is True
