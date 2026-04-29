from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from lathe.scene import (
    load_and_check_scene_graph,
    run_scene_validators,
    validate_scene_plan_payload,
)
from lathe.scene.memory import validate_world_memory
from lathe.scene.patch import apply_scene_patch
from lathe.wonder import (
    catalog_wonder_examples,
    generate_scene_plan,
    validate_contract,
    validate_wonder_example,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WONDER_ROOT = REPO_ROOT / "examples" / "wonder"
CATALOG_JSON_PATH = REPO_ROOT / "docs" / "wonder-readiness" / "20_example_catalog.json"
CATALOG_PATH = REPO_ROOT / "docs" / "wonder-readiness" / "20_example_catalog.md"
STDLIB_CATALOG_PATH = REPO_ROOT / "docs" / "wonder-readiness" / "21_stdlib_catalog.md"
WONDER_EXAMPLES_CI = REPO_ROOT / "scripts" / "ci_wonder_examples.py"

REQUIRED_ROOT_FILES = {
    "prompt.txt",
    "dream_brief.json",
    "scene_graph.json",
    "scene_source.lth",
    "world_memory.json",
    "scene_patch.example.json",
    "render_inspection.example.json",
}
REQUIRED_EXPECTED_FILES = {
    "scene_plan.example.json",
    "wonder_report.example.json",
    "scene_manifest.example.json",
    "render_comparison.example.json",
    "evidence_traceability.example.json",
    "preview_evidence.example.json",
}


def _example_dirs() -> tuple[Path, ...]:
    return tuple(sorted(path for path in WONDER_ROOT.iterdir() if path.is_dir()))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def test_every_wonder_example_has_required_golden_fixture_shape() -> None:
    for example_dir in _example_dirs():
        files = {path.name for path in example_dir.iterdir() if path.is_file()}
        expected_files = {path.name for path in (example_dir / "expected").iterdir() if path.is_file()}

        assert files >= REQUIRED_ROOT_FILES
        assert expected_files >= REQUIRED_EXPECTED_FILES


def test_validate_example_passes_for_all_examples() -> None:
    for example_dir in _example_dirs():
        report = validate_wonder_example(example_dir)

        assert report["status"] == "passed", report["diagnostics"]
        assert report["ok"] is True
        assert report["deferred_lanes"] == []


def test_catalog_examples_summarizes_all_examples() -> None:
    catalog = catalog_wonder_examples(WONDER_ROOT)

    assert catalog["schema_version"] == "lathe.wonder_example_catalog.v1"
    assert catalog["summary"] == {
        "total": len(_example_dirs()),
        "passed": len(_example_dirs()),
        "failed": 0,
        "deferred_nonblocking": 0,
    }
    assert {item["name"] for item in catalog["examples"]} == {path.name for path in _example_dirs()}
    assert all(item["scene_source"] == "valid" for item in catalog["examples"])
    assert all(item["preview_evidence"] == "present" for item in catalog["examples"])


def test_prompt_memory_patch_and_proxy_evidence_are_truthful_for_all_examples() -> None:
    for example_dir in _example_dirs():
        prompt = (example_dir / "prompt.txt").read_text(encoding="utf-8").strip()
        scene_graph, scene_diagnostics = load_and_check_scene_graph(example_dir / "scene_graph.json")
        memory = _read_json(example_dir / "world_memory.json")
        patch = _read_json(example_dir / "scene_patch.example.json")
        preview_evidence = _read_json(example_dir / "expected" / "preview_evidence.example.json")

        assert prompt
        assert scene_diagnostics == []
        assert validate_world_memory(memory, scene_graph=scene_graph) == []
        assert validate_contract("scene_patch", patch) == []
        assert apply_scene_patch(scene_graph, patch).diagnostics == []
        assert preview_evidence["schema_version"] == "lathe.preview_evidence.v1"
        assert preview_evidence["preview_build"]["evidence_type"] == "deterministic_proxy_contract"
        assert preview_evidence["preview_render"]["renderer"] == "lathe.scene.proxy_renderer.v1"
        assert preview_evidence["preview_export"]["exporter"] == "lathe.scene.proxy_glb_exporter.v1"
        assert preview_evidence["blender"]["status"] == "skipped_optional"
        assert preview_evidence["blender"]["blocking"] is False
        assert preview_evidence["roblox"]["status"] == "skipped_optional"
        assert preview_evidence["roblox"]["blocking"] is False


def test_scene_plans_and_scene_quality_validate_for_all_examples() -> None:
    for example_dir in _example_dirs():
        scene_graph, diagnostics = load_and_check_scene_graph(example_dir / "scene_graph.json")
        brief = _read_json(example_dir / "dream_brief.json")
        assert diagnostics == []

        plan = generate_scene_plan(brief, scene_graph=scene_graph)
        assert validate_scene_plan_payload(plan) == []
        assert _read_json(example_dir / "expected" / "scene_plan.example.json") == plan
        assert plan["metadata"]["counts"]["objects"] >= 4
        assert plan["metadata"]["counts"]["render_tasks"] >= 2

        report = run_scene_validators(scene_graph, root=example_dir)
        assert report["status"] == "passed"
        assert report["diagnostics"] == []


def test_scene_source_roundtrips_truthfully_for_all_examples(tmp_path: Path) -> None:
    for example_dir in _example_dirs():
        out = tmp_path / f"{example_dir.name}.scene_graph.json"
        result = _cli("scene", "source-to-scene-graph", str(example_dir / "scene_source.lth"), "--out", str(out))

        assert result.returncode == 0, result.stdout + result.stderr
        assert _read_json(out) == _read_json(example_dir / "scene_graph.json")


def test_validate_example_cli_writes_machine_readable_report(tmp_path: Path) -> None:
    out = tmp_path / "example_report.json"
    result = _cli("wonder", "validate-example", str(WONDER_ROOT / "alchemist_observatory"), "--out", str(out))

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    written = _read_json(out)
    assert payload["ok"] is True
    assert written["schema_version"] == "lathe.wonder_example_report.v1"
    assert written["status"] == "passed"


def test_catalog_examples_cli_writes_json_report(tmp_path: Path) -> None:
    out = tmp_path / "catalog.json"
    result = _cli("wonder", "catalog-examples", str(WONDER_ROOT), "--out", str(out))

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    written = _read_json(out)
    assert payload["ok"] is True
    assert payload["summary"]["failed"] == 0
    assert written["schema_version"] == "lathe.wonder_example_catalog.v1"
    assert written["summary"]["total"] == len(_example_dirs())


def test_validate_example_strict_mode_and_deferred_override() -> None:
    example_dir = WONDER_ROOT / "alchemist_observatory"
    strict_result = _cli("wonder", "validate-example", str(example_dir), "--strict")
    strict_payload = json.loads(strict_result.stdout)

    assert strict_result.returncode == 0, strict_result.stdout + strict_result.stderr
    assert strict_payload["ok"] is True

    allowed_result = _cli(
        "wonder",
        "validate-example",
        str(example_dir),
        "--strict",
        "--allow-deferred-scene-source",
    )
    allowed_payload = json.loads(allowed_result.stdout)

    assert allowed_result.returncode == 0, allowed_result.stdout + allowed_result.stderr
    assert allowed_payload["ok"] is True


def test_validate_example_strict_mode_fails_when_required_file_missing(tmp_path: Path) -> None:
    example_dir = tmp_path / "alchemist_observatory"
    shutil.copytree(WONDER_ROOT / "alchemist_observatory", example_dir)
    (example_dir / "prompt.txt").unlink()

    result = _cli(
        "wonder",
        "validate-example",
        str(example_dir),
        "--strict",
        "--allow-deferred-scene-source",
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert "WE1001" in _codes(payload["diagnostics"])


def test_wonder_catalog_docs_cover_golden_examples_and_vocab() -> None:
    catalog = CATALOG_PATH.read_text(encoding="utf-8")
    catalog_json = _read_json(CATALOG_JSON_PATH)
    stdlib_catalog = STDLIB_CATALOG_PATH.read_text(encoding="utf-8")

    for example_dir in _example_dirs():
        assert f"../../examples/wonder/{example_dir.name}/" in catalog
        assert example_dir.name in {item["name"] for item in catalog_json["examples"]}

    for term in (
        "environment_architecture",
        "navigation_marker",
        "interactive_mechanism",
        "practical_light",
        "terrace_wall_modules",
        "glass_tube_concourse",
        "courtyard_wall_shell",
    ):
        assert term in stdlib_catalog


def test_wonder_examples_ci_exercises_proxy_build_render_export_lanes() -> None:
    script = WONDER_EXAMPLES_CI.read_text(encoding="utf-8")

    assert "build_preview_" in script
    assert "validate_preview_package_" in script
    assert "render_preview_" in script
    assert "export_glb_" in script
    assert "lathe.scene.proxy_renderer.v1" in script
    assert "lathe.scene.proxy_glb_exporter.v1" in script


def test_high_object_count_stdlib_showcase_renders_contact_sheet(tmp_path: Path) -> None:
    result = _cli(
        "scene",
        "render",
        str(WONDER_ROOT / "stdlib_component_showcase" / "scene_graph.json"),
        "--out",
        str(tmp_path / "stdlib_renders"),
        "--all-cameras",
        "--mode",
        "preview",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    contact_sheet = payload["report"]["contact_sheets"][0]
    assert contact_sheet["object_count"] >= 49
    assert (tmp_path / "stdlib_renders" / contact_sheet["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
