from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from lathe.scene import artifacts as scene_artifacts
from lathe.scene import executor as scene_executor
from lathe.scene import load_and_validate_scene_package_manifest
from lathe.scene.executor import SceneBuildError, build_scene_preview
from lathe.scene.materialize import SceneMaterializeError
from lathe.wonder import validate_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_png(path: Path) -> None:
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def _assert_glb(path: Path) -> None:
    assert path.read_bytes().startswith(b"glTF")


def _assert_preview_artifact_contract(package_dir: Path, manifest: dict) -> None:
    scene_plan = _json(package_dir / "reports" / "scene_plan.json")
    scene_manifest = _json(package_dir / "reports" / "scene_manifest.json")
    render_report = _json(package_dir / "reports" / "scene_render_artifacts.json")
    export_report = _json(package_dir / "reports" / "scene_export_artifacts.json")

    renders = manifest["renders"]
    assert renders
    planned_renders = scene_manifest["planned_renders"]
    built_renders = scene_manifest["built_renders"]
    expected_camera_passes = {
        task["camera_id"]: set(task["passes"])
        for task in scene_plan["render_tasks"]
    }
    manifest_camera_passes: dict[str, set[str]] = {}
    for entry in renders:
        manifest_camera_passes.setdefault(entry["camera_id"], set()).update(entry["passes"])
    assert set(expected_camera_passes) <= set(manifest_camera_passes)
    for camera_id, passes in expected_camera_passes.items():
        assert passes <= manifest_camera_passes[camera_id]
    assert "camera_topdown_debug" in manifest_camera_passes
    assert scene_artifacts.CONTACT_SHEET_CAMERA_ID in manifest_camera_passes
    assert render_report["contact_sheets"] == [
        {
            "camera_id": scene_artifacts.CONTACT_SHEET_CAMERA_ID,
            "path": f"renders/{scene_artifacts.CONTACT_SHEET_CAMERA_ID}/beauty.png",
            "object_count": len(_scene()["objects"]),
            "width": render_report["resolution"][0],
            "height": render_report["resolution"][1],
        }
    ]
    assert {entry["status"] for entry in renders} == {"built"}
    assert {entry["status"] for entry in built_renders} == {"built"}
    assert {entry["status"] for entry in planned_renders} == {"planned"}
    assert {entry["artifact_path"] for entry in built_renders} == {entry["path"] for entry in renders}
    assert {entry["path"] for entry in render_report["artifacts"]} == {entry["path"] for entry in renders}
    for entry in renders:
        assert entry["path"].startswith("renders/")
        assert entry["path"].endswith(".png")
        assert len(entry["passes"]) == 1
        _assert_png(package_dir / entry["path"])

    exports = manifest["exports"]
    assert exports
    planned_exports = scene_manifest["planned_exports"]
    built_exports = scene_manifest["built_exports"]
    expected_glb_exports = {
        task["task_id"]
        for task in scene_plan["export_tasks"]
        if task["target"] == "glb" or task["format"] == "glb"
    }
    glb_exports = [entry for entry in exports if entry["target"] == "glb"]
    assert {entry["status"] for entry in exports} == {"built"}
    assert {entry["status"] for entry in planned_exports} == {"planned"}
    assert {entry["status"] for entry in built_exports} == {"built"}
    assert len(glb_exports) == len(expected_glb_exports)
    assert {entry["artifact_path"] for entry in built_exports if entry["target"] == "glb"} == {
        entry["path"] for entry in glb_exports
    }
    assert {
        entry["path"]
        for entry in export_report["artifacts"]
        if entry["target"] == "glb"
    } == {entry["path"] for entry in glb_exports}
    for entry in glb_exports:
        assert entry["path"].startswith("exports/")
        assert entry["path"].endswith(".glb")
        _assert_glb(package_dir / entry["path"])


def _write_scene(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def test_build_scene_preview_writes_offline_package_files(tmp_path: Path) -> None:
    result = build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene")
    package_dir = tmp_path / "dist_scene" / "alchemist_observatory"

    assert result["ok"] is True
    assert result["command"] == "scene.build"
    assert result["scene_id"] == "alchemist_observatory"
    assert result["mode"] == "preview"
    for relative_path in (
        "graph/scene_graph.json",
        "graph/scene_graph.normalized.json",
        "graph/world_memory.json",
        "cache/asset_reuse_report.json",
        "reports/scene_plan.json",
        "reports/build_report.json",
        "reports/validation_report.json",
        "reports/scene_quality_report.json",
        "reports/wonder_report.json",
        "reports/scene_manifest.json",
        "reports/scene_render_artifacts.json",
        "reports/scene_export_artifacts.json",
        "scene_package_manifest.json",
        "build/scene_build_proxy_manifest.json",
        "build/scene_assembly_ir.json",
        "build/object_selection_payloads.json",
    ):
        assert (package_dir / relative_path).is_file()

    manifest, diagnostics = load_and_validate_scene_package_manifest(package_dir / "scene_package_manifest.json")
    assert diagnostics == []
    assert manifest["graph"]["scene_graph"] == "graph/scene_graph.json"
    assert manifest["graph"]["scene_graph_normalized"] == "graph/scene_graph.normalized.json"
    assert result["build_options"]["schema_version"] == "lathe.scene_build_options.v1"
    assert result["build_options"]["deterministic"] is False
    assert result["build_options"]["allow_fallback"] is False
    assert result["build_options"]["strict"] is False
    assert result["build_options"]["runtime_config"] == {"provided": False, "path": None}
    assert result["build_options"]["runtime"]["provider_calls"] == "not_executed"
    assert _json(package_dir / "reports" / "scene_plan.json")["metadata"]["build_options"] == result["build_options"]
    assert _json(package_dir / "reports" / "scene_manifest.json")["build_options"] == result["build_options"]
    assert _json(package_dir / "reports" / "wonder_report.json")["build_options"] == result["build_options"]
    assert manifest["build_options"] == result["build_options"]
    assert _json(package_dir / "build" / "scene_build_proxy_manifest.json")["build_options"] == result["build_options"]
    assert validate_contract("scene_plan", _json(package_dir / "reports" / "scene_plan.json")) == []
    assert validate_contract("scene_build_report", _json(package_dir / "reports" / "build_report.json")) == []
    assert validate_contract("scene_manifest", _json(package_dir / "reports" / "scene_manifest.json")) == []
    assert validate_contract("scene_quality_report", _json(package_dir / "reports" / "validation_report.json")) == []
    assert validate_contract("wonder_report", _json(package_dir / "reports" / "wonder_report.json")) == []
    build_report = _json(package_dir / "reports" / "build_report.json")
    assert build_report["artifacts"]["scene_graph_normalized"] == "graph/scene_graph.normalized.json"
    assert build_report["artifacts"]["validation_report"] == "reports/validation_report.json"
    assert build_report["cache_reuse"]["asset_tasks"] == result["counts"]["asset_tasks"]
    assert build_report["cache_reuse"]["built_assets"] == result["counts"]["asset_tasks"]
    assert build_report["cache_reuse"]["reused_assets"] == 0
    assert build_report["provider_fallback_trace"] == result["provider_fallback_trace"]
    assert len(build_report["asset_build_reports"]) == result["counts"]["asset_tasks"]
    assert _json(package_dir / "cache" / "asset_reuse_report.json")["summary"] == build_report["cache_reuse"]
    assert _json(package_dir / "graph" / "scene_graph.normalized.json") == _json(package_dir / "graph" / "scene_graph.json")
    assert _json(package_dir / "reports" / "validation_report.json") == _json(
        package_dir / "reports" / "scene_quality_report.json"
    )
    _assert_preview_artifact_contract(package_dir, manifest)
    assert {entry["kind"] for entry in manifest["source"]} == {"prompt", "style_bible"}
    assert {entry["kind"] for entry in manifest["reports"]} == {"build_report", "validation", "wonder_report"}


def test_build_scene_preview_records_runtime_flags_and_config(tmp_path: Path) -> None:
    runtime_config_path = tmp_path / "runtime_config.json"
    _write_scene(
        runtime_config_path,
        {
            "shape": {
                "provider": "reference_conditioned",
                "strict": False,
                "allow_fallback": False,
            }
        },
    )

    result = build_scene_preview(
        EXAMPLE_SCENE,
        tmp_path / "dist_scene",
        runtime_config_path=runtime_config_path,
        deterministic=True,
        allow_fallback=True,
        strict=True,
    )
    package_dir = tmp_path / "dist_scene" / "alchemist_observatory"
    build_options = result["build_options"]

    assert build_options["deterministic"] is True
    assert build_options["allow_fallback"] is True
    assert build_options["strict"] is True
    assert build_options["runtime_config"]["provided"] is True
    assert build_options["runtime_config"]["path"].endswith("runtime_config.json")
    assert build_options["effective_runtime"] == {
        "shape_provider": "reference_conditioned",
        "shape_strict": True,
        "shape_allow_fallback": True,
    }
    assert build_options["fallbacks"]["provider_fallbacks_executed"] is False
    assert _json(package_dir / "scene_package_manifest.json")["build_options"] == build_options
    assert _json(package_dir / "reports" / "scene_plan.json")["metadata"]["build_options"] == build_options
    assert _json(package_dir / "reports" / "build_report.json")["provider_fallback_trace"] == {
        "runtime": build_options["runtime"],
        "effective_runtime": build_options["effective_runtime"],
        "fallbacks": build_options["fallbacks"],
        "diagnostic_policy": build_options["diagnostic_policy"],
    }


def test_build_scene_preview_reuses_cached_asset_proxy_manifests(tmp_path: Path) -> None:
    build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene")
    first_package = tmp_path / "dist_scene" / "alchemist_observatory"
    first_report = _json(first_package / "reports" / "build_report.json")
    first_asset_paths = [entry["path"] for entry in first_report["asset_build_reports"]]
    first_bytes = {path: (first_package / path).read_bytes() for path in first_asset_paths}

    second_result = build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene")
    second_report = _json(first_package / "reports" / "build_report.json")

    assert second_result["cache_reuse"]["asset_tasks"] == len(first_asset_paths)
    assert second_result["cache_reuse"]["reused_assets"] == len(first_asset_paths)
    assert second_report["cache_reuse"]["reused_assets"] == len(first_asset_paths)
    assert {entry["status"] for entry in second_report["asset_build_reports"]} == {"reused"}
    assert {entry["reuse_reason"] for entry in second_report["asset_build_reports"]} == {"cache_key_match"}
    assert first_bytes == {path: (first_package / path).read_bytes() for path in first_asset_paths}


def test_build_scene_preview_fails_when_asset_proxy_artifact_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def skip_asset_proxy_write(_package_dir: Path, relative_path: str, payload: dict) -> dict:
        return {
            "task_id": payload["task_id"],
            "path": relative_path,
            "cache_key": payload["cache_key"],
            "object_ids": payload["object_ids"],
            "source": payload["source"],
            "status": "built",
            "reused": False,
            "reuse_reason": "test_skip_write",
        }

    monkeypatch.setattr(scene_executor, "_write_asset_proxy_manifest", skip_asset_proxy_write)

    with pytest.raises(SceneBuildError) as exc:
        build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene")

    assert _codes(exc.value.diagnostics) == {"SB1013"}


def test_build_scene_preview_can_materialize_and_build_generated_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_materialize(scene_graph_path: Path, package_dir: Path, *, mode: str) -> dict:
        assert Path(scene_graph_path) == EXAMPLE_SCENE
        root = package_dir / "source" / "materialized_assets"
        build_report_path = root / "builds" / "fake_asset" / "build_report.json"
        build_report_path.parent.mkdir(parents=True, exist_ok=True)
        build_report_path.write_text('{"ok": true, "asset": "fake_asset"}\n', encoding="utf-8")
        manifest = {
            "schema_version": "lathe.scene_materialization_manifest.v1",
            "scene_id": "alchemist_observatory",
            "mode": mode,
            "source_scene_graph": "scene_graph.json",
            "source_scene_plan": "scene_plan.json",
            "generated_source_root": "assets",
            "summary": {
                "asset_tasks": 1,
                "source_files": 1,
                "object_instances": 1,
                "instance_friendly_sources": 0,
                "checker_errors": 0,
                "planner_errors": 0,
                "builds_requested": 1,
                "builds_succeeded": 1,
                "builds_failed": 0,
            },
            "asset_sources": [
                {
                    "asset_task_id": "asset_task_fake",
                    "asset_name": "fake_asset",
                    "asset_kind": "hard_surface_prop",
                    "cache_key": "scene_asset.v1:fake",
                    "source": {"kind": "generated_fallback", "ref": "fake_asset", "generated": True},
                    "object_ids": ["obj_astrolabe_table_001"],
                    "source_path": "assets/fake_asset/fake_asset.lth",
                    "metadata_path": "assets/fake_asset/metadata.json",
                    "material_ids": [],
                    "instancing": {
                        "instance_friendly": False,
                        "object_count": 1,
                        "requires_unique_build": False,
                        "uniqueness_reasons": [],
                    },
                    "check": {"ok": True, "diagnostics": []},
                    "plan": {"ok": True, "diagnostics": []},
                    "build": {
                        "requested": True,
                        "ok": True,
                        "asset": "fake_asset",
                        "out_dir": "builds/fake_asset",
                        "report_path": "builds/fake_asset/build_report.json",
                        "certified": True,
                        "score": 0.9,
                        "threshold": 0.8,
                        "diagnostics": [],
                    },
                }
            ],
            "diagnostics": [],
        }
        (root / "scene_materialization_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"ok": True, "manifest": manifest, "diagnostics": []}

    monkeypatch.setattr(scene_executor, "_materialize_missing_scene_assets", fake_materialize)

    result = build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene", build_assets=True)
    package_dir = tmp_path / "dist_scene" / "alchemist_observatory"
    package_manifest = _json(package_dir / "scene_package_manifest.json")
    build_report = _json(package_dir / "reports" / "build_report.json")
    materialization_manifest = _json(package_dir / "source" / "materialized_assets" / "scene_materialization_manifest.json")

    assert result["ok"] is True
    assert result["build_options"]["runtime"]["asset_build"] == "lathe.asset_build_pipeline.v1"
    assert result["build_options"]["runtime"]["asset_materialization"] == "lathe.scene.materialize.v1"
    assert result["build_options"]["fallbacks"]["deterministic_proxy_assets"] is True
    assert result["asset_materialization"] == {
        "requested": True,
        "manifest_path": "source/materialized_assets/scene_materialization_manifest.json",
        "builds_requested": 1,
        "builds_succeeded": 1,
        "builds_failed": 0,
    }
    assert result["counts"]["asset_builds_requested"] == 1
    assert package_manifest["source"][-1] == {
        "kind": "lathe_source",
        "path": "source/materialized_assets/scene_materialization_manifest.json",
        "description": "Generated Lathe asset sources and build outputs from scene materialization.",
    }
    assert build_report["asset_materialization"] == result["asset_materialization"]
    assert build_report["artifacts"]["scene_materialization_manifest"] == result["asset_materialization"]["manifest_path"]
    assert validate_contract("scene_build_report", build_report) == []
    assert validate_contract("scene_materialization_manifest", materialization_manifest) == []
    _, diagnostics = load_and_validate_scene_package_manifest(package_dir / "scene_package_manifest.json")
    assert diagnostics == []


def test_build_scene_preview_fails_when_generated_asset_build_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_materialize(_scene_graph_path: Path, package_dir: Path, *, mode: str) -> dict:
        root = package_dir / "source" / "materialized_assets"
        root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": "lathe.scene_materialization_manifest.v1",
            "scene_id": "alchemist_observatory",
            "mode": mode,
            "source_scene_graph": "scene_graph.json",
            "source_scene_plan": "scene_plan.json",
            "generated_source_root": "assets",
            "summary": {
                "asset_tasks": 1,
                "source_files": 1,
                "object_instances": 1,
                "instance_friendly_sources": 0,
                "checker_errors": 0,
                "planner_errors": 0,
                "builds_requested": 1,
                "builds_succeeded": 0,
                "builds_failed": 1,
            },
            "asset_sources": [],
            "diagnostics": [
                {
                    "code": "L6401",
                    "name": "asset_build_failed",
                    "severity": "error",
                    "path": "/asset_sources/0/build",
                    "message": "Synthetic generated asset build failure.",
                }
            ],
        }
        (root / "scene_materialization_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"ok": False, "manifest": manifest, "diagnostics": manifest["diagnostics"]}

    monkeypatch.setattr(scene_executor, "_materialize_missing_scene_assets", fake_materialize)

    with pytest.raises(SceneBuildError) as exc:
        build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene", build_assets=True)

    assert {"SB1014", "L6401"} <= _codes(exc.value.diagnostics)
    manifest_path = (
        tmp_path
        / "dist_scene"
        / "alchemist_observatory"
        / "source"
        / "materialized_assets"
        / "scene_materialization_manifest.json"
    )
    assert manifest_path.is_file()


def test_build_scene_preview_wraps_materialization_contract_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lathe.scene import materialize as scene_materialize

    def fake_materialize(_scene_graph_path: Path, _package_dir: Path, *, mode: str, build_assets: bool) -> dict:
        assert mode == "preview"
        assert build_assets is True
        raise SceneMaterializeError(
            [
                {
                    "code": "SM1002",
                    "name": "scene_materialization_plan_failed",
                    "severity": "error",
                    "path": "/scene_plan",
                    "message": "Synthetic materialization failure.",
                }
            ]
        )

    monkeypatch.setattr(scene_materialize, "materialize_scene_assets", fake_materialize)

    with pytest.raises(SceneBuildError) as exc:
        build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene", build_assets=True)

    assert {"SB1015", "SM1002"} <= _codes(exc.value.diagnostics)


def test_scene_build_report_rejects_loose_build_options_and_unsafe_artifact_paths(
    tmp_path: Path,
) -> None:
    build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene")
    report = _json(tmp_path / "dist_scene" / "alchemist_observatory" / "reports" / "build_report.json")

    missing_policy = json.loads(json.dumps(report))
    del missing_policy["build_options"]["runtime"]["renderer"]
    assert validate_contract("scene_build_report", missing_policy)

    extra_policy = json.loads(json.dumps(report))
    extra_policy["build_options"]["unexpected"] = True
    assert validate_contract("scene_build_report", extra_policy)

    unsafe_artifact = json.loads(json.dumps(report))
    unsafe_artifact["artifacts"]["scene_graph"] = "../scene_graph.json"
    assert validate_contract("scene_build_report", unsafe_artifact)

    bogus_runtime = json.loads(json.dumps(report))
    bogus_runtime["build_options"]["runtime"]["asset_materialization"] = "bogus"
    bogus_runtime["build_options"]["runtime"]["asset_build"] = "bogus"
    bogus_runtime["build_options"]["runtime"]["renderer"] = "bogus"
    bogus_runtime["build_options"]["fallbacks"]["deterministic_proxy_assets"] = False
    assert validate_contract("scene_build_report", bogus_runtime)


def test_build_scene_preview_rejects_unsafe_runtime_config_path(tmp_path: Path) -> None:
    runtime_config_path = tmp_path / "runtime_config.json"
    _write_scene(runtime_config_path, {"shape": {"provider": "reference_only"}})

    with pytest.raises(SceneBuildError) as exc:
        build_scene_preview(
            EXAMPLE_SCENE,
            tmp_path / "dist_scene",
            runtime_config_path=tmp_path / "nested" / ".." / "runtime_config.json",
        )

    assert _codes(exc.value.diagnostics) == {"SB1009"}


def test_strict_scene_build_rejects_scene_validation_warnings(tmp_path: Path) -> None:
    scene_graph = _scene()
    scene_graph["objects"][1]["transform"]["position"] = scene_graph["objects"][0]["transform"]["position"]
    warning_path = _write_scene(tmp_path / "warning_scene_graph.json", scene_graph)

    non_strict = build_scene_preview(warning_path, tmp_path / "non_strict")
    assert non_strict["ok"] is True

    with pytest.raises(SceneBuildError) as exc:
        build_scene_preview(warning_path, tmp_path / "strict", strict=True)

    assert {"SB1011", "SV1003"} <= _codes(exc.value.diagnostics)


def test_strict_scene_build_rejects_generated_fallback_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_plan_scene = scene_executor.plan_scene

    def plan_with_fallback(scene_graph: dict, *, mode: str = "preview") -> dict:
        plan = original_plan_scene(scene_graph, mode=mode)
        task = plan["asset_tasks"][0]
        task["source"] = {
            "kind": "generated_fallback",
            "ref": task["object_ids"][0],
            "generated": True,
            "generated_intent": {"object_id": task["object_ids"][0]},
        }
        plan["cache_keys"][0]["source"] = dict(task["source"])
        plan["cache_keys"][0]["shareable"] = False
        diagnostic = {
            "code": "SP1001",
            "name": "missing_object_source_reference",
            "severity": "warning",
            "contract": "scene_plan",
            "phase": "scene_planning",
            "path": "/objects/0",
            "message": "Synthetic fallback source diagnostic for strict scene build coverage.",
        }
        plan["diagnostics"].append(dict(diagnostic))
        plan["warnings"].append(dict(diagnostic))
        return plan

    monkeypatch.setattr(scene_executor, "plan_scene", plan_with_fallback)

    with pytest.raises(SceneBuildError) as exc:
        build_scene_preview(EXAMPLE_SCENE, tmp_path / "strict", strict=True)

    assert {"SB1012", "SP1001"} <= _codes(exc.value.diagnostics)


def test_build_scene_preview_preserves_object_ids_and_memory_events(tmp_path: Path) -> None:
    scene_graph = _scene()
    build_scene_preview(EXAMPLE_SCENE, tmp_path / "dist_scene")
    package_dir = tmp_path / "dist_scene" / "alchemist_observatory"

    scene_manifest = _json(package_dir / "reports" / "scene_manifest.json")
    object_ids = [item["object_id"] for item in scene_manifest["objects"]]
    assert object_ids == sorted(item["object_id"] for item in scene_graph["objects"])
    assert all(item["asset_proxy_path"].startswith("build/asset_task_") for item in scene_manifest["objects"])
    assert all(item["status"] == "planned" for item in scene_manifest["objects"])

    world_memory = _json(package_dir / "graph" / "world_memory.json")
    assert [event["event_id"] for event in world_memory["events"]] == [
        "mem_initial_fact_001",
        "mem_hidden_lens_001",
    ]
    assert [event["scope"] for event in world_memory["events"]] == ["region", "object"]
    assert world_memory["branches"][0]["event_ids"] == ["mem_initial_fact_001", "mem_hidden_lens_001"]


def test_build_scene_preview_outputs_are_deterministic(tmp_path: Path) -> None:
    build_scene_preview(EXAMPLE_SCENE, tmp_path / "first")
    build_scene_preview(EXAMPLE_SCENE, tmp_path / "second")
    first = tmp_path / "first" / "alchemist_observatory"
    second = tmp_path / "second" / "alchemist_observatory"

    manifest = _json(first / "scene_package_manifest.json")
    relative_paths = {
        "graph/scene_graph.json",
        "graph/scene_graph.normalized.json",
        "graph/world_memory.json",
        "cache/asset_reuse_report.json",
        "reports/scene_plan.json",
        "reports/build_report.json",
        "reports/validation_report.json",
        "reports/scene_quality_report.json",
        "reports/wonder_report.json",
        "reports/scene_manifest.json",
        "reports/scene_render_artifacts.json",
        "reports/scene_export_artifacts.json",
        "scene_package_manifest.json",
        "build/scene_build_proxy_manifest.json",
        "build/scene_assembly_ir.json",
        "build/object_selection_payloads.json",
        *(entry["path"] for entry in manifest["renders"]),
        *(entry["path"] for entry in manifest["exports"]),
        *(
            entry["path"]
            for entry in _json(first / "reports" / "scene_render_artifacts.json")["object_indices"]
        ),
        *(
            entry["path"]
            for entry in _json(first / "reports" / "scene_render_artifacts.json")["material_indices"]
        ),
        *(
            entry["path"]
            for entry in _json(first / "reports" / "scene_export_artifacts.json")["artifacts"]
        ),
    }
    for relative_path in relative_paths:
        assert (first / relative_path).read_bytes() == (second / relative_path).read_bytes()


def test_build_scene_preview_honors_declared_glb_export_tasks(tmp_path: Path) -> None:
    scene_graph = _scene()
    scene_graph["exports"] = [item for item in scene_graph["exports"] if item["target"] != "glb"]
    no_glb_path = _write_scene(tmp_path / "no_glb.scene_graph.json", scene_graph)

    no_glb_result = build_scene_preview(no_glb_path, tmp_path / "no_glb")
    no_glb_package = tmp_path / "no_glb" / "alchemist_observatory"

    assert no_glb_result["counts"]["export_tasks"] == 2
    assert no_glb_result["counts"]["export_artifacts"] == 0
    assert _json(no_glb_package / "scene_package_manifest.json")["exports"] == []
    assert _json(no_glb_package / "reports" / "scene_export_artifacts.json")["artifacts"] == []

    custom_scene = _scene()
    glb_export = next(item for item in custom_scene["exports"] if item["target"] == "glb")
    glb_export["path"] = "exports/custom_observatory.glb"
    custom_path = _write_scene(tmp_path / "custom_glb.scene_graph.json", custom_scene)

    custom_result = build_scene_preview(custom_path, tmp_path / "custom_glb")
    custom_package = tmp_path / "custom_glb" / "alchemist_observatory"
    manifest_exports = _json(custom_package / "scene_package_manifest.json")["exports"]

    assert custom_result["counts"]["export_artifacts"] == 2
    assert manifest_exports == [{"target": "glb", "path": "exports/custom_observatory.glb", "status": "built"}]
    _assert_glb(custom_package / "exports" / "custom_observatory.glb")


def test_build_scene_final_uses_scene_plan_render_passes(tmp_path: Path) -> None:
    build_scene_preview(EXAMPLE_SCENE, tmp_path / "final", mode="final")
    package_dir = tmp_path / "final" / "alchemist_observatory"
    scene_plan = _json(package_dir / "reports" / "scene_plan.json")
    render_report = _json(package_dir / "reports" / "scene_render_artifacts.json")

    planned_passes = {
        render_pass
        for task in scene_plan["render_tasks"]
        for render_pass in task["passes"]
    }
    assert set(render_report["passes"]) == planned_passes
    assert "wireframe" not in render_report["passes"]


def test_export_scene_glb_rejects_failed_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scene_graph = _scene()
    object_ids = {item["object_id"] for item in scene_graph["objects"]}

    def fail_identity(_glb_path: Path, expected_object_ids: list[str]) -> dict:
        assert set(expected_object_ids) == object_ids
        return {
            "status": "failed",
            "object_ids_expected": expected_object_ids,
            "object_ids_found": [],
            "object_ids_missing": expected_object_ids,
        }

    monkeypatch.setattr(scene_artifacts, "_validate_glb_identity", fail_identity)

    with pytest.raises(scene_artifacts.SceneArtifactError) as exc:
        scene_artifacts.export_scene_glb(scene_graph, tmp_path / "exports")

    assert _codes(exc.value.diagnostics) == {"SX1002"}
    assert not (tmp_path / "exports" / "reports" / "scene_export_artifacts.json").exists()


def test_build_scene_preview_rejects_invalid_scene_graph(tmp_path: Path) -> None:
    scene_graph = _scene()
    scene_graph["objects"][1]["object_id"] = scene_graph["objects"][0]["object_id"]
    invalid_path = _write_scene(tmp_path / "invalid_scene_graph.json", scene_graph)

    with pytest.raises(SceneBuildError) as exc:
        build_scene_preview(invalid_path, tmp_path / "dist_scene")

    assert "S1001" in _codes(exc.value.diagnostics)
    assert not (tmp_path / "dist_scene" / "alchemist_observatory").exists()


def test_build_scene_preview_rejects_unsafe_output_path(tmp_path: Path) -> None:
    with pytest.raises(SceneBuildError) as exc:
        build_scene_preview(EXAMPLE_SCENE, tmp_path / ".." / "outside")

    assert _codes(exc.value.diagnostics) == {"SB1004"}


def test_scene_build_cli_emits_json_and_package(tmp_path: Path) -> None:
    result = _cli("scene", "build", str(EXAMPLE_SCENE), "--out", str(tmp_path / "cli_dist"), "--mode", "preview")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "scene.build"
    assert payload["mode"] == "preview"
    assert (tmp_path / "cli_dist" / "alchemist_observatory" / "scene_package_manifest.json").is_file()
