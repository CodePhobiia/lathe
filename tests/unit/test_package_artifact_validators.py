from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import trimesh
from lathe.engine_manifests.godot_import_contract import validate_godot_import_contract
from lathe.executor import build_asset
from lathe.parser import parse_file

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "examples" / "courier_drone.lth"
ASSET = "courier_drone"


def _load_glb(path: Path) -> trimesh.Scene:
    loaded = trimesh.load(path, force="scene")
    assert isinstance(loaded, trimesh.Scene)
    assert loaded.geometry
    assert sum(len(geometry.vertices) for geometry in loaded.geometry.values()) > 0
    assert sum(len(geometry.faces) for geometry in loaded.geometry.values()) > 0
    return loaded


@pytest.fixture(scope="module")
def courier_build(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp_path = tmp_path_factory.mktemp("package_artifact_validators")
    previous_cache_dir = os.environ.get("LATHE_CACHE_DIR")
    os.environ["LATHE_CACHE_DIR"] = str(tmp_path / ".lathe_cache")
    try:
        out_dir = tmp_path / ASSET
        build_asset(parse_file(SOURCE), ASSET, out_dir)
    finally:
        if previous_cache_dir is None:
            os.environ.pop("LATHE_CACHE_DIR", None)
        else:
            os.environ["LATHE_CACHE_DIR"] = previous_cache_dir
    return out_dir


@pytest.mark.slow
def test_packaged_glb_and_usd_outputs_pass_automated_validators(courier_build: Path) -> None:
    out_dir = courier_build
    package_manifest = json.loads(
        (out_dir / "stages/package/package_manifest.json").read_text(encoding="utf-8")
    )
    glb_outputs = [
        out_dir / output["uri"]
        for output in package_manifest["outputs"]
        if str(output.get("uri", "")).lower().endswith(".glb")
    ]
    usd_outputs = [
        out_dir / output["uri"]
        for output in package_manifest["outputs"]
        if str(output.get("uri", "")).lower().endswith((".usd", ".usda"))
    ]

    assert glb_outputs
    assert usd_outputs

    for glb_path in glb_outputs:
        _load_glb(glb_path)

    for usd_path in usd_outputs:
        text = usd_path.read_text(encoding="utf-8")
        assert text.startswith("#usda 1.0")
        assert f'def Xform "{ASSET}"' in text
        assert 'def Mesh "mesh"' in text
        assert "point3f[] points = [" in text
        assert "int[] faceVertexCounts = [" in text
        assert "int[] faceVertexIndices = [" in text


@pytest.mark.slow
def test_build_outputs_include_quality_metrics_for_release_review(courier_build: Path) -> None:
    out_dir = courier_build
    topology = json.loads((out_dir / "stages/topology/bundle.json").read_text(encoding="utf-8"))
    uv = json.loads((out_dir / "stages/uv/bundle.json").read_text(encoding="utf-8"))
    physics = json.loads((out_dir / "stages/physics/bundle.json").read_text(encoding="utf-8"))
    optimize = json.loads((out_dir / "stages/optimize/bundle.json").read_text(encoding="utf-8"))
    package_manifest = json.loads(
        (out_dir / "stages/package/package_manifest.json").read_text(encoding="utf-8")
    )

    mesh_stats = topology["mesh_stats"]
    assert mesh_stats["vertex_count"] > 0
    assert mesh_stats["triangle_count"] > 0
    assert isinstance(mesh_stats["watertight"], bool)
    assert mesh_stats["body_count"] > 0
    assert len(mesh_stats["extents"]) == 3
    assert all(extent > 0 for extent in mesh_stats["extents"])

    part_names = [part["name"] for part in topology["part_groups"]]
    assert len(part_names) == len(set(part_names))
    assert all(name and name == name.strip() for name in part_names)

    assert {item["name"] for item in uv["uv_sets"]} >= {"base", "lightmap"}
    assert uv["packing_report"]["chart_count"] > 0
    assert uv["packing_report"]["resolution"] >= 1024
    assert uv["texel_density"]["actual_px_per_m"] > 0
    assert uv["lightmap_ready"] is True

    budget = optimize["budget_report"]
    assert budget["materials"]["count"] <= budget["materials"]["budget"]
    assert budget["materials"]["status"] == "pass"
    assert budget["draw_calls"]["estimated"] <= budget["draw_calls"]["budget"]
    assert budget["draw_calls"]["status"] == "pass"
    assert budget["texture_memory"]["estimated_bytes"] <= budget["texture_memory"]["budget_bytes"]

    assert physics["collision_proxy"] is True
    assert physics["mass_kg"] > 0
    assert len(physics["center_of_mass"]) == 3
    assert optimize["collision"]["hull_tris"] > 0
    assert optimize["collision"]["parts_count"] > 0

    lods = optimize["lods"]
    assert len(lods) >= 2
    triangle_counts = [lod["triangle_count"] for lod in lods]
    assert triangle_counts == sorted(triangle_counts, reverse=True)
    assert all((out_dir / lod["mesh_uri"]).is_file() for lod in lods)

    output_uris = [output["uri"] for output in package_manifest["outputs"]]
    assert package_manifest["trace_path"]
    assert set(output_uris) == set(package_manifest["output_hashes"])
    assert all((out_dir / uri).is_file() for uri in output_uris)
    assert all((out_dir / preview).is_file() for preview in package_manifest["previews"])


@pytest.mark.slow
def test_build_outputs_match_godot_addon_import_contract(courier_build: Path) -> None:
    report = validate_godot_import_contract(courier_build)

    assert report["ok"], report["diagnostics"]
    assert report["diagnostics"] == []
    assert report["evidence"]["asset_id"] == ASSET
    assert report["evidence"]["glb_uri"] == f"stages/package/{ASSET}.glb"
    assert report["evidence"]["godot_engine_manifest"] == f"{ASSET}.lathe_for_godot.json"


def test_godot_addon_import_contract_rejects_missing_glb_output(tmp_path: Path) -> None:
    package_dir = tmp_path / "stages" / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "package_manifest.json").write_text(
        json.dumps(
            {
                "asset_id": "broken",
                "kind": "prop",
                "formats": ["usd"],
                "outputs": [{"format": "usd", "uri": "stages/package/broken.usda"}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "build_report.json").write_text(
        json.dumps(
            {
                "certified": True,
                "certification": {"score": 1.0, "threshold": 0.8},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "broken.lathe_for_godot.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "engine": "godot",
                "assetName": "broken",
                "lodGroup": [],
                "collision": {"shapes": []},
            }
        ),
        encoding="utf-8",
    )

    report = validate_godot_import_contract(tmp_path)

    assert not report["ok"]
    codes = {diag["code"] for diag in report["diagnostics"] if diag["severity"] == "error"}
    assert "LENG003" in codes


def test_godot_addon_import_contract_rejects_backslash_artifact_uri(tmp_path: Path) -> None:
    package_dir = tmp_path / "stages" / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "broken.glb").write_bytes(b"glTF")
    (package_dir / "package_manifest.json").write_text(
        json.dumps(
            {
                "asset_id": "broken",
                "kind": "prop",
                "formats": ["glb"],
                "outputs": [{"format": "glb", "uri": r"stages\package\broken.glb"}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "build_report.json").write_text(
        json.dumps(
            {
                "certified": True,
                "score": 1.0,
                "threshold": 0.8,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "broken.lathe_for_godot.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "engine": "godot",
                "assetName": "broken",
                "lodGroup": [],
                "collision": {"shapes": []},
            }
        ),
        encoding="utf-8",
    )

    report = validate_godot_import_contract(tmp_path)

    assert not report["ok"]
    assert any(diag["code"] == "LENG004" and "POSIX" in diag["message"] for diag in report["diagnostics"])
