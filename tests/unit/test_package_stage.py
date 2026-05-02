from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh
from lathe.core.stages import package as package_stage
from lathe.errors import BuildError
from PIL import Image
from trimesh.visual.material import PBRMaterial


def test_selector_manifest_write_failure_is_hard_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executor = SimpleNamespace(
        asset_name="demo",
        program={"variants": []},
        cache_key="abc123",
        runtime={},
        asset={},
        out_dir=tmp_path,
    )
    monkeypatch.setattr(package_stage, "build_selector_manifest", lambda **_: {"schemaVersion": 1})

    def _fail_write(_manifest: dict, _build_dir: Path) -> Path:
        raise ValueError("schema invalid")

    monkeypatch.setattr(package_stage, "write_selector_manifest", _fail_write)

    with pytest.raises(BuildError, match=r"selector_manifest[.]json could not be written") as excinfo:
        package_stage._write_selector_manifest(executor, {"diagnostics": []})

    assert excinfo.value.diagnostics[0]["code"] == "LPKG_SELECTOR_MANIFEST_WRITE_FAILED"


def _write_texture(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), color=color).save(path)


def test_package_stage_copies_surface_textures_and_embeds_pbr_material(tmp_path: Path) -> None:
    surface_dir = tmp_path / "stages" / "surface"
    maps_dir = surface_dir / "maps"
    for name, color in {
        "basecolor": (180, 180, 190),
        "normal": (128, 128, 255),
        "orm": (120, 160, 220),
        "ao": (210, 210, 210),
        "emissive": (0, 0, 0),
    }.items():
        _write_texture(maps_dir / f"{name}.png", color)

    executor = SimpleNamespace(
        out_dir=tmp_path,
        stage_dirs={"surface": surface_dir},
        runtime={
            "surface": {
                "bundle": {
                    "outputs": {
                        name: {"uri": f"maps/{name}.png"}
                        for name in ("basecolor", "normal", "orm", "ao", "emissive")
                    }
                }
            }
        },
    )
    package_dir = tmp_path / "stages" / "package"

    textures = package_stage._copy_surface_textures(executor, package_dir)
    assert set(textures) == {"basecolor", "normal", "orm", "ao", "emissive"}
    assert all(path.is_file() for path in textures.values())

    mesh = trimesh.creation.box()
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.zeros((len(mesh.vertices), 2), dtype=np.float64))
    textured = package_stage._mesh_with_pbr_textures(mesh, textures)

    assert isinstance(textured.visual.material, PBRMaterial)
    assert textured.visual.material.baseColorTexture is not None
    assert textured.visual.material.normalTexture is not None


def test_game_asset_manifest_collects_pipeline_authoring_metadata(tmp_path: Path) -> None:
    executor = SimpleNamespace(
        asset_name="demo_asset",
        out_dir=tmp_path,
        asset={"kind": "hard_surface_prop", "package": {"formats": ["glb"], "game_asset_manifest": True}},
        runtime={
            "uv": {
                "bundle": {
                    "uv_sets": [{"name": "base"}],
                    "packing_report": {"chart_count": 3},
                    "uv_organization": {"chart_grouping": "material"},
                    "chart_manifest": [{"chart_id": "uvc_01_body"}],
                }
            },
            "surface": {
                "bundle": {
                    "material_slots": 3,
                    "material_zones": [{"part": "body", "material": "painted_steel"}],
                    "material_id_layout": {"count": 3},
                    "surface_story_placement_plan": {"placement_count": 2},
                    "highlow_relation": {"source": "hero_surface_runtime_v1"},
                }
            },
            "physics": {"bundle": {"collision": {"proxy": "convex_hull"}}},
            "interfaces": {"bundle": {"sockets": [{"id": "socket_a"}], "pivots": [], "anchors": []}},
            "highlow_relation": {"source": "optimize_lod_highlow_v1"},
        },
    )
    outputs = [{"format": "glb", "uri": "stages/package/demo_asset.glb"}]
    texture_outputs = [{"format": "basecolor_texture", "uri": "stages/package/textures/basecolor.png"}]
    optimize_bundle = {
        "lods": [{"name": "lod1", "mesh_uri": "stages/optimize/lod_1.glb"}],
        "collision": {"hull_uri": "stages/optimize/collision_hull.glb"},
        "highlow_relation": {"source": "optimize_lod_highlow_v1", "low_lod_level": 2},
    }

    entry = package_stage._write_game_asset_manifest(
        executor=executor,
        stage_dir=tmp_path,
        outputs=outputs,
        optimize_bundle=optimize_bundle,
        texture_outputs=texture_outputs,
    )
    payload = json.loads((tmp_path / "game_asset_manifest.json").read_text(encoding="utf-8"))

    assert entry["format"] == "game_asset_manifest"
    assert payload["schema"] == "lathe.game_asset_manifest.v1"
    assert payload["uv"]["uv_organization"]["chart_grouping"] == "material"
    assert payload["materials"]["material_id_layout"]["count"] == 3
    assert payload["surface_story"]["placement_count"] == 2
    assert payload["highlow_relation"]["source"] == "optimize_lod_highlow_v1"
    assert payload["interfaces"]["sockets"][0]["id"] == "socket_a"
