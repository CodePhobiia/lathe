from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lathe.scene import SCENE_PACKAGE_MANIFEST_FILENAME
from lathe.scene.memory import create_world_memory

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
EXAMPLE_SCENE = EXAMPLE_DIR / "scene_graph.json"
EXAMPLE_INSPECTION = EXAMPLE_DIR / "render_inspection.example.json"
ROBLOX_EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "abandoned_roblox_mall"
ROBLOX_EXAMPLE_SCENE = ROBLOX_EXAMPLE_DIR / "scene_graph.json"
ROBLOX_PROFILE = ROBLOX_EXAMPLE_DIR / "roblox_profile.json"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _event() -> dict:
    return {
        "event_id": "mem_cli_added_fact_001",
        "type": "fact",
        "scope": "object",
        "text": "The astrolabe table remains the continuity anchor for CLI append tests.",
        "affected_ids": ["obj_astrolabe_table_001"],
        "branch_id": "main",
        "source": "unit_test",
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _assert_proxy_artifact_paths(package_dir: Path, manifest: dict) -> None:
    for render in manifest["renders"]:
        render_path = package_dir / render["path"]
        assert render["status"] == "built"
        assert render["path"].startswith("renders/")
        assert render_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    for export in manifest["exports"]:
        export_path = package_dir / export["path"]
        assert export["status"] == "built"
        assert export_path.is_file()
        if export["target"] == "glb":
            assert export["path"].startswith("exports/")
            assert export_path.read_bytes().startswith(b"glTF")


def _star_silver_material() -> dict:
    return {
        "material_id": "mat_star_silver",
        "name": "Star Silver",
        "role": "mechanisms",
        "palette_refs": ["lunar blue"],
        "pbr": {
            "basecolor": "#c7d8ff",
            "metallic": 0.75,
            "roughness": 0.28,
        },
    }


def _star_map_object() -> dict:
    return {
        "object_id": "obj_star_map_001",
        "name": "Folded Star Map",
        "role": "narrative_clue",
        "region": "region_central_chamber",
        "lathe_asset": "folded_star_map",
        "transform": {
            "position": [1.2, 0.4, 0.82],
            "rotation": [0, 0, 12],
            "scale": [0.6, 0.6, 0.6],
        },
        "material_bindings": [{"slot": "paper", "material": "mat_star_silver"}],
        "semantic_tags": ["map", "constellation", "clue"],
        "state": {"revealed": False},
        "affordances": [],
        "provenance": {
            "source": "deterministic_lathe",
            "commercial_use": True,
        },
    }


def _init_package(package_dir: Path, scene_id: str = "alchemist_observatory") -> None:
    result = _cli("scene", "package", "init", str(package_dir), "--scene-id", scene_id)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True


def _package_with_memory(tmp_path: Path) -> tuple[Path, Path, Path]:
    package_dir = tmp_path / "observatory_package"
    _init_package(package_dir)
    scene_graph = _scene()
    scene_graph_path = package_dir / "graph" / "scene_graph.json"
    memory_path = package_dir / "graph" / "world_memory.json"
    _write_json(scene_graph_path, scene_graph)
    _write_json(memory_path, create_world_memory(scene_graph, summary="CLI package memory."))
    return package_dir, scene_graph_path, memory_path


def test_scene_package_init_validate_and_inspect_emit_json(tmp_path: Path) -> None:
    package_dir = tmp_path / "cli_package"

    init_result = _cli("scene", "package", "init", str(package_dir), "--scene-id", "cli_scene")

    assert init_result.returncode == 0, init_result.stderr
    init_payload = json.loads(init_result.stdout)
    assert init_payload["ok"] is True
    assert init_payload["command"] == "scene.package.init"
    assert Path(init_payload["manifest_path"]).name == SCENE_PACKAGE_MANIFEST_FILENAME

    validate_result = _cli("scene", "package", "validate", str(package_dir))

    assert validate_result.returncode == 0, validate_result.stderr
    validate_payload = json.loads(validate_result.stdout)
    assert validate_payload["ok"] is True
    assert validate_payload["diagnostics"] == []

    inspect_result = _cli("scene", "package", "inspect", str(package_dir))

    assert inspect_result.returncode == 0, inspect_result.stderr
    inspect_payload = json.loads(inspect_result.stdout)
    assert inspect_payload["ok"] is True
    assert inspect_payload["manifest"]["scene_id"] == "cli_scene"
    assert inspect_payload["counts"]["exports"] == 0


def test_scene_check_plan_and_validate_emit_json(tmp_path: Path) -> None:
    check_result = _cli("scene", "check", str(EXAMPLE_SCENE))

    assert check_result.returncode == 0, check_result.stderr
    check_payload = json.loads(check_result.stdout)
    assert check_payload["ok"] is True
    assert check_payload["command"] == "scene.check"
    assert check_payload["scene_id"] == "alchemist_observatory"
    assert check_payload["diagnostics"] == []

    plan_path = tmp_path / "scene_plan.json"
    plan_result = _cli("scene", "plan", str(EXAMPLE_SCENE), "--mode", "preview", "--out", str(plan_path))

    assert plan_result.returncode == 0, plan_result.stderr
    plan_payload = json.loads(plan_result.stdout)
    assert plan_payload["ok"] is True
    assert plan_payload["command"] == "scene.plan"
    assert plan_payload["plan"]["schema_version"] == "lathe.scene_plan.v1"
    assert plan_path.exists()

    branch_plan_path = tmp_path / "scene_plan_branch.json"
    branch_plan_result = _cli(
        "scene",
        "plan",
        str(EXAMPLE_SCENE),
        "--mode",
        "preview",
        "--reuse-from-plan",
        str(plan_path),
        "--out",
        str(branch_plan_path),
    )

    assert branch_plan_result.returncode == 0, branch_plan_result.stderr
    branch_plan_payload = json.loads(branch_plan_result.stdout)
    assert branch_plan_payload["ok"] is True
    assert branch_plan_payload["reuse_from_plan"] == str(plan_path)
    assert branch_plan_payload["plan"]["branch_reuse"]["summary"]["new_asset_tasks"] == 0
    assert branch_plan_payload["plan"]["branch_reuse"]["summary"]["reusable_asset_tasks"] == len(
        branch_plan_payload["plan"]["asset_tasks"]
    )
    assert branch_plan_path.exists()

    bad_plan_path = tmp_path / "scene_plan_bad_cache.json"
    bad_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    bad_plan["cache_keys"][0]["asset_task_id"] = "asset_task_bad_mismatch"
    _write_json(bad_plan_path, bad_plan)
    bad_branch_plan_result = _cli(
        "scene",
        "plan",
        str(EXAMPLE_SCENE),
        "--mode",
        "preview",
        "--reuse-from-plan",
        str(bad_plan_path),
    )

    assert bad_branch_plan_result.returncode == 1
    bad_branch_plan_payload = json.loads(bad_branch_plan_result.stdout)
    assert bad_branch_plan_payload["ok"] is False
    assert "SP3006" in [diagnostic["code"] for diagnostic in bad_branch_plan_payload["diagnostics"]]

    validate_plan_result = _cli("wonder", "validate-plan", str(plan_path))

    assert validate_plan_result.returncode == 0, validate_plan_result.stderr
    validate_plan_payload = json.loads(validate_plan_result.stdout)
    assert validate_plan_payload["ok"] is True
    assert validate_plan_payload["contract"] == "scene_plan"

    validate_result = _cli("scene", "validate", str(EXAMPLE_SCENE))

    assert validate_result.returncode == 0, validate_result.stderr
    validate_payload = json.loads(validate_result.stdout)
    assert validate_payload["ok"] is True
    assert validate_payload["report"]["schema_version"] == "lathe.scene_quality_report.v1"
    assert validate_payload["report"]["status"] == "passed"


def test_scene_build_cli_package_inspect_tracks_proxy_artifacts_when_present(tmp_path: Path) -> None:
    package_root = tmp_path / "scene_build"
    build_result = _cli("scene", "build", str(EXAMPLE_SCENE), "--mode", "preview", "--out", str(package_root))

    assert build_result.returncode == 0, build_result.stderr
    build_payload = json.loads(build_result.stdout)
    assert build_payload["ok"] is True
    assert build_payload["counts"]["render_tasks"] == 3
    assert build_payload["counts"]["export_tasks"] == 3
    assert build_payload["counts"]["render_artifacts"] >= build_payload["counts"]["render_tasks"]
    assert build_payload["counts"]["export_artifacts"] >= 1

    package_dir = package_root / "alchemist_observatory"
    inspect_result = _cli("scene", "package", "inspect", str(package_dir))

    assert inspect_result.returncode == 0, inspect_result.stderr
    inspect_payload = json.loads(inspect_result.stdout)
    manifest = inspect_payload["manifest"]
    assert inspect_payload["counts"]["renders"] == len(manifest["renders"])
    assert inspect_payload["counts"]["exports"] == len(manifest["exports"])
    assert inspect_payload["counts"]["renders"] == build_payload["counts"]["render_artifacts"]
    assert any(entry["target"] == "glb" for entry in manifest["exports"])
    _assert_proxy_artifact_paths(package_dir, manifest)


def test_scene_build_cli_records_runtime_flags_and_config(tmp_path: Path) -> None:
    runtime_config_path = tmp_path / "runtime_config.json"
    _write_json(
        runtime_config_path,
        {
            "shape": {
                "provider": "reference_conditioned",
                "strict": False,
                "allow_fallback": False,
            }
        },
    )
    package_root = tmp_path / "scene_build"

    build_result = _cli(
        "scene",
        "build",
        str(EXAMPLE_SCENE),
        "--mode",
        "preview",
        "--out",
        str(package_root),
        "--runtime-config",
        str(runtime_config_path),
        "--deterministic",
        "--allow-fallback",
        "--strict",
    )

    assert build_result.returncode == 0, build_result.stderr or build_result.stdout
    build_payload = json.loads(build_result.stdout)
    build_options = build_payload["build_options"]
    package_dir = package_root / "alchemist_observatory"
    manifest = json.loads((package_dir / "scene_package_manifest.json").read_text(encoding="utf-8"))
    scene_plan = json.loads((package_dir / "reports" / "scene_plan.json").read_text(encoding="utf-8"))

    assert build_options["deterministic"] is True
    assert build_options["allow_fallback"] is True
    assert build_options["strict"] is True
    assert build_options["runtime_config"]["provided"] is True
    assert build_options["effective_runtime"] == {
        "shape_provider": "reference_conditioned",
        "shape_strict": True,
        "shape_allow_fallback": True,
    }
    assert manifest["build_options"] == build_options
    assert scene_plan["metadata"]["build_options"] == build_options


def test_scene_build_cli_rejects_invalid_runtime_config_json(tmp_path: Path) -> None:
    runtime_config_path = tmp_path / "bad_runtime_config.json"
    runtime_config_path.write_text("{ nope\n", encoding="utf-8")

    build_result = _cli(
        "scene",
        "build",
        str(EXAMPLE_SCENE),
        "--out",
        str(tmp_path / "scene_build"),
        "--runtime-config",
        str(runtime_config_path),
    )

    assert build_result.returncode == 1
    assert build_result.stderr == ""
    payload = json.loads(build_result.stdout)
    assert payload["ok"] is False
    assert payload["runtime_config"] == str(runtime_config_path)
    assert {diagnostic["code"] for diagnostic in payload["diagnostics"]} == {"SB1010"}


def test_scene_assemble_branch_diff_merge_emit_json(tmp_path: Path) -> None:
    assembly_path = tmp_path / "scene_assembly.json"
    assembly_result = _cli("scene", "assemble", str(EXAMPLE_SCENE), "--out", str(assembly_path))

    assert assembly_result.returncode == 0, assembly_result.stderr
    assembly_payload = json.loads(assembly_result.stdout)
    assert assembly_payload["ok"] is True
    assert assembly_payload["command"] == "scene.assemble"
    assert assembly_payload["assembly"]["schema_version"] == "lathe.scene_assembly.v1"
    assert assembly_path.exists()

    branch_path = tmp_path / "scene_branch.json"
    branch_result = _cli("scene", "branch", str(EXAMPLE_SCENE), "--name", "Archive Expansion", "--out", str(branch_path))

    assert branch_result.returncode == 0, branch_result.stderr
    branch_payload = json.loads(branch_result.stdout)
    assert branch_payload["ok"] is True
    assert branch_payload["branch"]["schema_version"] == "lathe.scene_branch.v1"
    assert branch_path.exists()

    source = _scene()
    source["materials"].append(_star_silver_material())
    source["objects"].append(_star_map_object())
    source_path = tmp_path / "source_scene.json"
    _write_json(source_path, source)

    diff_path = tmp_path / "scene_diff.json"
    diff_result = _cli("scene", "diff", str(EXAMPLE_SCENE), str(source_path), "--out", str(diff_path))

    assert diff_result.returncode == 0, diff_result.stderr
    diff_payload = json.loads(diff_result.stdout)
    assert diff_payload["ok"] is True
    assert diff_payload["diff"]["schema_version"] == "lathe.scene_diff.v1"
    assert diff_payload["diff"]["summary"]["objects_added"] == 1
    assert diff_path.exists()

    merge_path = tmp_path / "merged_scene.json"
    merge_result = _cli("scene", "merge", str(source_path), "--into", str(EXAMPLE_SCENE), "--out", str(merge_path))

    assert merge_result.returncode == 0, merge_result.stderr
    merge_payload = json.loads(merge_result.stdout)
    assert merge_payload["ok"] is True
    assert merge_payload["written"] is True
    assert "obj_star_map_001" in {item["object_id"] for item in merge_payload["scene_graph"]["objects"]}
    assert merge_path.exists()


def test_scene_bench_and_roblox_manifest_emit_contract_json(tmp_path: Path) -> None:
    timings_path = tmp_path / "timings.json"
    scores_path = tmp_path / "scores.json"
    _write_json(
        timings_path,
        {
            "stages": {
                "brief": {"duration_ms": 1000},
                "scene_graph": {"duration_ms": 2000},
                "source_generation": {"duration_ms": 1000},
                "check_plan": {"duration_ms": 500},
                "preview_build": {"duration_ms": 5000},
                "preview_render": {"duration_ms": 1000},
                "patch_preview": {"duration_ms": 1000},
                "final_export": {"duration_ms": 1000},
            },
            "cache": {"hits": 1, "misses": 1, "writes": 1},
        },
    )
    _write_json(
        scores_path,
        {
            "metrics": {
                "prompt_to_brief": 0.9,
                "brief_to_scene": 0.9,
                "parse_check": 1.0,
                "build_success": 1.0,
                "scene_validation": 0.9,
                "style_consistency": 0.9,
                "object_count_accuracy": 0.9,
                "render_quality": 0.9,
                "patch_success": 1.0,
                "continuity_preservation": 0.9,
                "export_validity": 1.0,
            }
        },
    )

    bench_path = tmp_path / "scene_benchmark_report.json"
    bench_result = _cli(
        "scene",
        "bench",
        str(EXAMPLE_SCENE),
        "--timings",
        str(timings_path),
        "--scores",
        str(scores_path),
        "--out",
        str(bench_path),
    )

    assert bench_result.returncode == 0, bench_result.stderr or bench_result.stdout
    bench_payload = json.loads(bench_result.stdout)
    assert bench_payload["ok"] is True
    assert bench_payload["report"]["schema_version"] == "lathe.scene_benchmark_report.v1"
    assert bench_payload["report"]["status"] == "passed"
    assert bench_path.exists()

    validate_bench_result = _cli("wonder", "validate-scene-benchmark-report", str(bench_path))

    assert validate_bench_result.returncode == 0, validate_bench_result.stderr
    assert json.loads(validate_bench_result.stdout)["ok"] is True

    manifest_path = tmp_path / "roblox_manifest.json"
    roblox_result = _cli(
        "scene",
        "roblox-manifest",
        str(ROBLOX_EXAMPLE_SCENE),
        "--profile",
        str(ROBLOX_PROFILE),
        "--out",
        str(manifest_path),
    )

    assert roblox_result.returncode == 0, roblox_result.stderr or roblox_result.stdout
    roblox_payload = json.loads(roblox_result.stdout)
    assert roblox_payload["ok"] is True
    assert roblox_payload["manifest"]["schema_version"] == "lathe.roblox_manifest.v1"
    assert roblox_payload["manifest"]["summary"]["scores"]["mobile"]["status"] == "passed"
    assert manifest_path.exists()

    validate_manifest_result = _cli("wonder", "validate-roblox-manifest", str(manifest_path))

    assert validate_manifest_result.returncode == 0, validate_manifest_result.stderr
    assert json.loads(validate_manifest_result.stdout)["ok"] is True


def test_scene_render_and_export_emit_real_proxy_artifacts(tmp_path: Path) -> None:
    import trimesh

    render_dir = tmp_path / "renders"
    render_result = _cli(
        "scene",
        "render",
        str(EXAMPLE_SCENE),
        "--out",
        str(render_dir),
        "--camera",
        "camera_reveal",
        "--passes",
        "beauty,object_id",
        "--width",
        "640",
        "--height",
        "360",
    )

    assert render_result.returncode == 0, render_result.stderr or render_result.stdout
    render_payload = json.loads(render_result.stdout)
    assert render_payload["ok"] is True
    assert render_payload["command"] == "scene.render"
    assert render_payload["report"]["schema_version"] == "lathe.scene_render_artifacts.v1"
    assert {item["render_pass"] for item in render_payload["report"]["artifacts"]} == {"beauty", "object_id"}
    assert (render_dir / "renders" / "camera_reveal" / "beauty.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert (render_dir / "renders" / "camera_reveal" / "object_index.json").is_file()

    export_dir = tmp_path / "exports"
    export_result = _cli("scene", "export", str(EXAMPLE_SCENE), "--out", str(export_dir), "--target", "glb")

    assert export_result.returncode == 0, export_result.stderr or export_result.stdout
    export_payload = json.loads(export_result.stdout)
    assert export_payload["ok"] is True
    assert export_payload["command"] == "scene.export"
    assert export_payload["report"]["schema_version"] == "lathe.scene_export_artifacts.v1"
    glb_path = export_dir / "exports" / "alchemist_observatory.glb"
    assert glb_path.read_bytes().startswith(b"glTF")
    object_index = json.loads((export_dir / "exports" / "alchemist_observatory.object_index.json").read_text())
    assert object_index["identity"]["status"] == "passed"
    astrolabe_record = next(item for item in object_index["objects"] if item["object_id"] == "obj_astrolabe_table_001")
    assert astrolabe_record["instancing"]["schema_version"] == "lathe.scene_instancing_metadata.v1"
    assert astrolabe_record["instancing"]["reuse_group_id"].startswith("reuse_group_astrolabe_table_")
    assert astrolabe_record["glb_extras"]["lathe_instancing"] == astrolabe_record["instancing"]

    loaded = trimesh.load(glb_path, force="scene")
    astrolabe_geometry = loaded.geometry["obj_astrolabe_table_001"]
    extras = astrolabe_geometry.metadata["extras"]
    assert extras["lathe_object_id"] == "obj_astrolabe_table_001"
    assert extras["lathe_instancing"]["reuse_group_id"] == astrolabe_record["instancing"]["reuse_group_id"]


def test_scene_export_usd_emits_proxy_usda_with_identity(tmp_path: Path) -> None:
    export_dir = tmp_path / "usd_exports"

    export_result = _cli("scene", "export", str(EXAMPLE_SCENE), "--out", str(export_dir), "--target", "usd")

    assert export_result.returncode == 0, export_result.stderr or export_result.stdout
    export_payload = json.loads(export_result.stdout)
    assert export_payload["ok"] is True
    assert export_payload["command"] == "scene.export"
    assert export_payload["target"] == "usd"
    assert export_payload["report"]["schema_version"] == "lathe.scene_export_artifacts.v1"
    artifacts = export_payload["report"]["artifacts"]
    assert {item["target"] for item in artifacts} == {"usd", "object_index"}
    usd_artifact = next(item for item in artifacts if item["target"] == "usd")
    assert usd_artifact["format"] == "usda"
    assert usd_artifact["identity"]["status"] == "passed"
    assert usd_artifact["layout_convention"] == "lathe.proxy_usd_layout.v1"

    usd_path = export_dir / "exports" / "alchemist_observatory.usda"
    usd_text = usd_path.read_text(encoding="utf-8")
    assert usd_text.startswith("#usda 1.0")
    assert 'def Xform "LatheScene"' in usd_text
    assert 'def Xform "Regions"' in usd_text
    assert 'def Xform "Objects"' in usd_text
    for item in _scene()["objects"]:
        assert f'string lathe_object_id = "{item["object_id"]}"' in usd_text

    object_index = json.loads(
        (export_dir / "exports" / "alchemist_observatory.usd_object_index.json").read_text(encoding="utf-8")
    )
    assert object_index["identity"]["status"] == "passed"
    assert object_index["layout_convention"]["object_root"] == "/LatheScene/Objects"
    assert {item["object_id"] for item in object_index["objects"]} == {
        item["object_id"] for item in _scene()["objects"]
    }


def test_scene_export_glb_can_include_collision_proxy_nodes(tmp_path: Path) -> None:
    import trimesh

    export_dir = tmp_path / "collision_exports"

    export_result = _cli(
        "scene",
        "export",
        str(EXAMPLE_SCENE),
        "--out",
        str(export_dir),
        "--target",
        "glb",
        "--include-collision-proxies",
    )

    assert export_result.returncode == 0, export_result.stderr or export_result.stdout
    export_payload = json.loads(export_result.stdout)
    assert export_payload["ok"] is True
    assert export_payload["include_collision_proxies"] is True
    glb_artifact = next(item for item in export_payload["report"]["artifacts"] if item["target"] == "glb")
    assert glb_artifact["collision_nodes"] == len(_scene()["objects"])

    glb_path = export_dir / "exports" / "alchemist_observatory.glb"
    object_index = json.loads((export_dir / "exports" / "alchemist_observatory.object_index.json").read_text())
    assert object_index["collision_policy"] == "simple_box_proxy"
    assert len(object_index["collision_nodes"]) == len(_scene()["objects"])
    collision_names = {item["node_name"] for item in object_index["collision_nodes"]}
    expected_collision_name = f"collision_{_scene()['objects'][0]['object_id']}"
    assert expected_collision_name in collision_names
    loaded = trimesh.load(glb_path, force="scene")
    node_names = set(getattr(loaded.graph, "nodes", []))
    geometry_names = set(getattr(loaded, "geometry", {}).keys())
    assert expected_collision_name in node_names | geometry_names


def test_scene_export_can_include_id_mask_bundle(tmp_path: Path) -> None:
    export_dir = tmp_path / "id_mask_exports"

    export_result = _cli(
        "scene",
        "export",
        str(EXAMPLE_SCENE),
        "--out",
        str(export_dir),
        "--target",
        "glb",
        "--include-id-mask-bundle",
    )

    assert export_result.returncode == 0, export_result.stderr or export_result.stdout
    export_payload = json.loads(export_result.stdout)
    assert export_payload["ok"] is True
    assert export_payload["include_id_mask_bundle"] is True
    bundle = export_payload["report"]["id_mask_bundle"]
    assert bundle["schema_version"] == "lathe.scene_id_mask_export_bundle.v1"
    assert set(bundle["cameras"]) == {
        "camera_reveal",
        "camera_warm_lens_detail",
        "camera_topdown_debug",
    }
    assert any(item["target"] == "id_mask_bundle" for item in export_payload["report"]["artifacts"])
    mask_path = export_dir / "exports" / "id_masks" / "camera_reveal" / "object_id.png"
    object_index_path = export_dir / "exports" / "id_masks" / "camera_reveal" / "object_index.json"
    bundle_path = export_dir / "exports" / "id_masks" / "id_mask_bundle.json"
    assert mask_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert object_index_path.is_file()
    assert json.loads(bundle_path.read_text(encoding="utf-8"))["schema_version"] == (
        "lathe.scene_id_mask_export_bundle.v1"
    )
    persisted_report = json.loads((export_dir / "reports" / "scene_export_artifacts.json").read_text(encoding="utf-8"))
    assert "id_mask_bundle" in persisted_report


def test_scene_render_all_cameras_emits_every_proxy_camera(tmp_path: Path) -> None:
    render_dir = tmp_path / "all_camera_renders"

    render_result = _cli(
        "scene",
        "render",
        str(EXAMPLE_SCENE),
        "--out",
        str(render_dir),
        "--all-cameras",
        "--passes",
        "beauty",
        "--width",
        "320",
        "--height",
        "180",
    )

    assert render_result.returncode == 0, render_result.stderr or render_result.stdout
    render_payload = json.loads(render_result.stdout)
    assert render_payload["ok"] is True
    assert render_payload["all_cameras"] is True
    assert render_payload["camera"] is None
    assert set(render_payload["report"]["cameras"]) == {
        "camera_reveal",
        "camera_warm_lens_detail",
        "camera_topdown_debug",
    }
    assert render_payload["report"]["contact_sheets"] == [
        {
            "camera_id": "camera_object_contact_sheet",
            "path": "renders/camera_object_contact_sheet/beauty.png",
            "object_count": len(_scene()["objects"]),
            "width": 320,
            "height": 180,
        }
    ]
    assert {item["render_pass"] for item in render_payload["report"]["artifacts"]} == {"beauty"}
    for camera_id in render_payload["report"]["cameras"]:
        assert (render_dir / "renders" / camera_id / "beauty.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert (render_dir / "renders" / camera_id / "object_index.json").is_file()
    assert (render_dir / "renders" / "camera_object_contact_sheet" / "beauty.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert (render_dir / "renders" / "camera_object_contact_sheet" / "object_index.json").is_file()


def test_scene_render_rejects_conflicting_camera_selection(tmp_path: Path) -> None:
    render_result = _cli(
        "scene",
        "render",
        str(EXAMPLE_SCENE),
        "--out",
        str(tmp_path / "renders"),
        "--camera",
        "camera_reveal",
        "--all-cameras",
    )

    assert render_result.returncode == 1
    assert render_result.stderr == ""
    payload = json.loads(render_result.stdout)
    assert payload["ok"] is False
    assert payload["diagnostics"][0]["code"] == "SR1902"


def test_scene_render_reports_proxy_render_timeout(tmp_path: Path) -> None:
    render_result = _cli(
        "scene",
        "render",
        str(EXAMPLE_SCENE),
        "--out",
        str(tmp_path / "renders"),
        "--all-cameras",
        "--timeout-seconds",
        "0",
    )

    assert render_result.returncode == 1
    assert render_result.stderr == ""
    payload = json.loads(render_result.stdout)
    assert payload["ok"] is False
    assert payload["timeout_seconds"] == 0.0
    assert payload["diagnostics"][0]["code"] == "SR1004"
    assert payload["diagnostics"][0]["name"] == "render_timeout_exceeded"


def test_scene_style_layout_and_camera_lighting_emit_contract_json(tmp_path: Path) -> None:
    style_pack_path = tmp_path / "style_pack.json"
    style_result = _cli("scene", "style-pack", str(EXAMPLE_SCENE), "--out", str(style_pack_path))

    assert style_result.returncode == 0, style_result.stderr or style_result.stdout
    style_payload = json.loads(style_result.stdout)
    assert style_payload["ok"] is True
    assert style_payload["style_pack"]["schema_version"] == "lathe.style_pack.v1"
    assert style_pack_path.exists()

    validate_style_result = _cli("wonder", "validate-style-pack", str(style_pack_path))

    assert validate_style_result.returncode == 0, validate_style_result.stderr
    assert json.loads(validate_style_result.stdout)["ok"] is True

    builtin_style_pack_path = tmp_path / "dead_god_style_pack.json"
    builtin_style_result = _cli(
        "scene",
        "style-pack",
        "--builtin",
        "dead_god_observatory",
        "--out",
        str(builtin_style_pack_path),
    )

    assert builtin_style_result.returncode == 0, builtin_style_result.stderr or builtin_style_result.stdout
    builtin_payload = json.loads(builtin_style_result.stdout)
    assert builtin_payload["ok"] is True
    assert builtin_payload["builtin"] == "dead_god_observatory"
    assert builtin_payload["style_pack"]["style_pack_id"] == "dead_god_observatory"
    assert builtin_style_pack_path.exists()

    layout_path = tmp_path / "layout_plan.json"
    layout_result = _cli(
        "scene",
        "layout",
        str(EXAMPLE_SCENE),
        "--style-pack",
        str(style_pack_path),
        "--out",
        str(layout_path),
    )

    assert layout_result.returncode == 0, layout_result.stderr or layout_result.stdout
    layout_payload = json.loads(layout_result.stdout)
    assert layout_payload["ok"] is True
    assert layout_payload["layout_plan"]["schema_version"] == "lathe.layout_plan.v1"
    assert layout_path.exists()

    validate_layout_result = _cli("wonder", "validate-layout-plan", str(layout_path))

    assert validate_layout_result.returncode == 0, validate_layout_result.stderr
    assert json.loads(validate_layout_result.stdout)["ok"] is True

    camera_lighting_path = tmp_path / "camera_lighting_plan.json"
    camera_result = _cli(
        "scene",
        "camera-lighting",
        str(EXAMPLE_SCENE),
        "--layout-plan",
        str(layout_path),
        "--out",
        str(camera_lighting_path),
    )

    assert camera_result.returncode == 0, camera_result.stderr or camera_result.stdout
    camera_payload = json.loads(camera_result.stdout)
    assert camera_payload["ok"] is True
    assert camera_payload["plan"]["schema_version"] == "lathe.camera_lighting_plan.v1"
    assert camera_lighting_path.exists()


def test_scene_repair_and_curiosity_commands_emit_json(tmp_path: Path) -> None:
    inspect_result = _cli("scene", "inspect-render", str(EXAMPLE_SCENE), str(EXAMPLE_INSPECTION))

    assert inspect_result.returncode == 0, inspect_result.stderr
    inspect_payload = json.loads(inspect_result.stdout)
    assert inspect_payload["ok"] is True
    assert inspect_payload["diagnostics"] == []

    repair_report_path = tmp_path / "repair_report.json"
    propose_result = _cli(
        "scene",
        "propose-repairs",
        str(EXAMPLE_SCENE),
        str(EXAMPLE_INSPECTION),
        "--out",
        str(repair_report_path),
    )

    assert propose_result.returncode == 0, propose_result.stderr
    propose_payload = json.loads(propose_result.stdout)
    assert propose_payload["ok"] is True
    assert propose_payload["report"]["schema_version"] == "lathe.scene_repair_report.v1"
    assert propose_payload["proposals"][0]["schema_version"] == "lathe.scene_patch.v1"
    assert repair_report_path.exists()

    repaired_scene_path = tmp_path / "repaired_scene.json"
    repair_result = _cli(
        "scene",
        "repair",
        str(EXAMPLE_SCENE),
        str(EXAMPLE_INSPECTION),
        "--out",
        str(repaired_scene_path),
        "--report-out",
        str(tmp_path / "repair_loop_report.json"),
    )

    assert repair_result.returncode == 0, repair_result.stderr
    repair_payload = json.loads(repair_result.stdout)
    assert repair_payload["ok"] is True
    assert repair_payload["written"] is True
    assert repair_payload["report"]["summary"]["applied"] == 1
    assert repaired_scene_path.exists()

    curiosity_result = _cli("scene", "curiosity", str(EXAMPLE_SCENE))

    assert curiosity_result.returncode == 0, curiosity_result.stderr
    curiosity_payload = json.loads(curiosity_result.stdout)
    assert curiosity_payload["ok"] is True
    assert curiosity_payload["summary"]["schema_version"] == "lathe.curiosity_summary.v1"
    assert len(curiosity_payload["summary"]["cards"]) >= 2

    expanded_scene_path = tmp_path / "expanded_scene.json"
    expand_result = _cli(
        "scene",
        "expand-anchor",
        str(EXAMPLE_SCENE),
        "curiosity_warm_lens",
        "--option",
        "opened_archive",
        "--out",
        str(expanded_scene_path),
    )

    assert expand_result.returncode == 0, expand_result.stderr
    expand_payload = json.loads(expand_result.stdout)
    assert expand_payload["ok"] is True
    assert expand_payload["written"] is True
    assert any(item.startswith("region_") for item in expand_payload["added_ids"])
    assert expanded_scene_path.exists()


def test_scene_package_validate_reports_missing_paths_unless_allowed(tmp_path: Path) -> None:
    package_dir = tmp_path / "cli_package"
    _init_package(package_dir, scene_id="missing_refs_scene")
    manifest_path = package_dir / SCENE_PACKAGE_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["graph"]["scene_graph"] = "graph/missing_scene_graph.json"
    _write_json(manifest_path, manifest)

    strict_result = _cli("scene", "package", "validate", str(package_dir))

    assert strict_result.returncode == 1
    assert strict_result.stderr == ""
    strict_payload = json.loads(strict_result.stdout)
    assert strict_payload["ok"] is False
    assert "P4002" in {item["code"] for item in strict_payload["diagnostics"]}

    allowed_result = _cli("scene", "package", "validate", str(manifest_path), "--allow-missing-paths")

    assert allowed_result.returncode == 0, allowed_result.stderr
    allowed_payload = json.loads(allowed_result.stdout)
    assert allowed_payload["ok"] is True
    assert allowed_payload["diagnostics"] == []


def test_scene_package_validate_reports_unsafe_package_paths(tmp_path: Path) -> None:
    package_dir = tmp_path / "cli_package"
    _init_package(package_dir, scene_id="unsafe_refs_scene")
    manifest_path = package_dir / SCENE_PACKAGE_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["exports"].append({"target": "glb", "path": "../outside.glb"})
    _write_json(manifest_path, manifest)

    result = _cli("scene", "package", "validate", str(package_dir), "--allow-missing-paths")

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "P4001" in {item["code"] for item in payload["diagnostics"]}


def test_scene_memory_inspect_direct_file_with_scene_graph(tmp_path: Path) -> None:
    memory_path = tmp_path / "world_memory.json"
    _write_json(memory_path, create_world_memory(_scene(), summary="Direct memory inspection."))

    result = _cli("scene", "memory", "inspect", str(memory_path), "--scene-graph", str(EXAMPLE_SCENE))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["contract"] == "world_memory"
    assert payload["counts"]["events"] == 0
    assert payload["memory"]["scene_id"] == "alchemist_observatory"


def test_scene_memory_append_to_package_is_idempotent(tmp_path: Path) -> None:
    package_dir, _scene_graph_path, memory_path = _package_with_memory(tmp_path)
    event_path = tmp_path / "event.json"
    _write_json(event_path, _event())

    first = _cli("scene", "memory", "append", str(package_dir), str(event_path))

    assert first.returncode == 0, first.stderr
    first_payload = json.loads(first.stdout)
    assert first_payload["ok"] is True
    assert first_payload["status"] == "appended"
    assert first_payload["appended"] is True
    assert first_payload["counts"]["events"] == 1

    second = _cli("scene", "memory", "append", str(package_dir), str(event_path))

    assert second.returncode == 0, second.stderr
    second_payload = json.loads(second.stdout)
    assert second_payload["ok"] is True
    assert second_payload["status"] == "skipped"
    assert second_payload["idempotent"] is True
    assert second_payload["appended"] is False

    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    assert [event["event_id"] for event in memory["events"]] == ["mem_cli_added_fact_001"]
    assert memory["branches"][0]["event_ids"] == ["mem_cli_added_fact_001"]
