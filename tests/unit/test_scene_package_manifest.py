from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
from lathe.scene import (
    SCENE_PACKAGE_MANIFEST_FILENAME,
    check_scene_package_manifest,
    get_scene_package_manifest_schema,
    init_scene_package,
    load_and_validate_scene_package_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _write(path: Path, text: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _package(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "observatory_package"
    for dirname in (
        "source",
        "graph",
        "build",
        "renders",
        "exports",
        "reports",
        "builds/preview",
        "builds/final",
        "render_passes/depth",
        "render_passes/normal",
        "render_passes/object_id",
        "render_passes/material_id",
        "render_passes/wireframe",
        "cache",
    ):
        (root / dirname).mkdir(parents=True, exist_ok=True)

    _write(root / "source" / "prompt.txt", "A room of brass instruments.")
    _write(root / "source" / "dream_brief.json")
    _write(root / "graph" / "scene_graph.json", '{"scene_id": "alchemist_observatory"}')
    _write(root / "graph" / "scene_patch.json")
    (root / "build" / "obj_astrolabe_table_001").mkdir()
    _write(root / "builds" / "preview" / "scene_build_proxy_manifest.json")
    _write(root / "builds" / "final" / "scene_build_proxy_manifest.json")
    _write(root / "renders" / "reveal.png", "png")
    _write(root / "render_passes" / "depth" / "camera_reveal.png", "png")
    _write(root / "render_passes" / "object_id" / "camera_reveal.png", "png")
    _write(root / "exports" / "alchemist_observatory.glb", "glb")
    _write(root / "reports" / "wonder_report.json")

    manifest = {
        "schema_version": "lathe.scene_package_manifest.v1",
        "package_id": "alchemist_observatory",
        "scene_id": "alchemist_observatory",
        "version": 1,
        "layout": {
            "source": "source",
            "graph": "graph",
            "build": "build",
            "renders": "renders",
            "exports": "exports",
            "reports": "reports",
        },
        "source": [
            {"kind": "prompt", "path": "source/prompt.txt"},
            {"kind": "dream_brief", "path": "source/dream_brief.json"},
        ],
        "graph": {
            "scene_graph": "graph/scene_graph.json",
            "patches": ["graph/scene_patch.json"],
        },
        "build": [
            {
                "kind": "asset_build",
                "path": "build/obj_astrolabe_table_001",
                "status": "planned",
                "object_id": "obj_astrolabe_table_001",
            }
        ],
        "renders": [
            {
                "camera_id": "camera_reveal",
                "path": "renders/reveal.png",
                "passes": ["beauty", "object_id"],
                "status": "planned",
            }
        ],
        "exports": [
            {
                "target": "glb",
                "path": "exports/alchemist_observatory.glb",
                "status": "planned",
            }
        ],
        "reports": [
            {
                "kind": "wonder_report",
                "path": "reports/wonder_report.json",
                "status": "planned",
            }
        ],
    }
    manifest_path = root / SCENE_PACKAGE_MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, manifest


def _codes(diagnostics: list[dict]) -> list[str]:
    return [diagnostic["code"] for diagnostic in diagnostics]


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def test_scene_package_manifest_schema_is_valid_json_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(get_scene_package_manifest_schema())


def test_validate_scene_package_manifest_accepts_folder_based_package(tmp_path: Path) -> None:
    manifest_path, _manifest = _package(tmp_path)

    payload, diagnostics = load_and_validate_scene_package_manifest(manifest_path)

    assert payload["schema_version"] == "lathe.scene_package_manifest.v1"
    assert diagnostics == []


def test_check_scene_package_manifest_rejects_unsafe_paths(tmp_path: Path) -> None:
    manifest_path, manifest = _package(tmp_path)
    manifest["exports"][0]["path"] = "../outside.glb"

    diagnostics = check_scene_package_manifest(manifest, root=manifest_path.parent)

    assert "P4001" in _codes(diagnostics)
    unsafe = next(item for item in diagnostics if item["code"] == "P4001")
    assert unsafe["name"] == "unsafe_package_path"
    assert unsafe["path"] == "/exports/0/path"


def test_check_scene_package_manifest_requires_existing_paths(tmp_path: Path) -> None:
    manifest_path, manifest = _package(tmp_path)
    (manifest_path.parent / "renders" / "reveal.png").unlink()

    diagnostics = check_scene_package_manifest(manifest, root=manifest_path.parent)

    assert "P4002" in _codes(diagnostics)
    missing = next(item for item in diagnostics if item["code"] == "P4002")
    assert missing["name"] == "missing_package_path"
    assert missing["path"] == "/renders/0/path"


def test_check_scene_package_manifest_keeps_refs_inside_section_folder(tmp_path: Path) -> None:
    manifest_path, manifest = _package(tmp_path)
    _write(manifest_path.parent / "exports" / "wonder_report.json")
    manifest["reports"][0]["path"] = "exports/wonder_report.json"

    diagnostics = check_scene_package_manifest(manifest, root=manifest_path.parent)

    assert "P4004" in _codes(diagnostics)
    outside = next(item for item in diagnostics if item["code"] == "P4004")
    assert outside["name"] == "package_path_outside_section"
    assert outside["path"] == "/reports/0/path"


def test_check_scene_package_manifest_rejects_scene_id_mismatch(tmp_path: Path) -> None:
    manifest_path, manifest = _package(tmp_path)
    scene_graph = _scene()
    scene_graph["scene_id"] = "other_observatory"
    _write(manifest_path.parent / "graph" / "scene_graph.json", json.dumps(scene_graph))

    diagnostics = check_scene_package_manifest(manifest, root=manifest_path.parent)

    assert "P4010" in _codes(diagnostics)
    mismatch = next(item for item in diagnostics if item["code"] == "P4010")
    assert mismatch["name"] == "package_scene_id_mismatch"
    assert mismatch["path"] == "/graph/scene_graph"
    assert mismatch["details"]["manifest_scene_id"] == "alchemist_observatory"
    assert mismatch["details"]["scene_graph_scene_id"] == "other_observatory"


def test_check_scene_package_manifest_accepts_phase4_build_and_render_pass_roots(tmp_path: Path) -> None:
    manifest_path, manifest = _package(tmp_path)
    manifest["build"][0]["path"] = "builds/preview/scene_build_proxy_manifest.json"
    manifest["build"].append(
        {
            "kind": "scene_build",
            "path": "builds/final/scene_build_proxy_manifest.json",
            "status": "planned",
        }
    )
    manifest["renders"] = [
        {
            "camera_id": "camera_reveal",
            "path": "renders/reveal.png",
            "passes": ["beauty"],
            "status": "planned",
        },
        {
            "camera_id": "camera_reveal",
            "path": "render_passes/depth/camera_reveal.png",
            "passes": ["depth"],
            "status": "planned",
        },
        {
            "camera_id": "camera_reveal",
            "path": "render_passes/object_id/camera_reveal.png",
            "passes": ["object_id"],
            "status": "planned",
        },
    ]

    diagnostics = check_scene_package_manifest(manifest, root=manifest_path.parent)

    assert diagnostics == []


def test_check_scene_package_manifest_requires_phase4_layout_dirs(tmp_path: Path) -> None:
    manifest_path, manifest = _package(tmp_path)
    (manifest_path.parent / "builds" / "final" / "scene_build_proxy_manifest.json").unlink()
    (manifest_path.parent / "builds" / "final").rmdir()

    diagnostics = check_scene_package_manifest(manifest, root=manifest_path.parent)

    assert "P4002" in _codes(diagnostics)
    missing = next(item for item in diagnostics if item["path"] == "/layout/builds/final")
    assert missing["name"] == "missing_package_path"


def test_init_scene_package_creates_standard_layout(tmp_path: Path) -> None:
    manifest_path, manifest = init_scene_package(tmp_path / "new_package", scene_id="new_scene")

    assert manifest_path.name == SCENE_PACKAGE_MANIFEST_FILENAME
    assert manifest["scene_id"] == "new_scene"
    for dirname in (
        "source",
        "graph",
        "build",
        "renders",
        "exports",
        "reports",
        "builds/preview",
        "builds/final",
        "render_passes/depth",
        "render_passes/normal",
        "render_passes/object_id",
        "render_passes/material_id",
        "render_passes/wireframe",
        "cache",
    ):
        assert (manifest_path.parent / dirname).is_dir()

    _payload, diagnostics = load_and_validate_scene_package_manifest(manifest_path)
    assert diagnostics == []


def test_wonder_cli_validate_package_manifest_success(tmp_path: Path) -> None:
    manifest_path, _manifest = _package(tmp_path)

    result = _cli("wonder", "validate-package-manifest", str(manifest_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["contract"] == "scene_package_manifest"
    assert payload["diagnostics"] == []


def test_wonder_cli_validate_package_manifest_reports_path_diagnostics(tmp_path: Path) -> None:
    manifest_path, manifest = _package(tmp_path)
    manifest["reports"][0]["path"] = "../report.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _cli("wonder", "validate-package-manifest", str(manifest_path))

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "P4001" in _codes(payload["diagnostics"])


def test_wonder_cli_init_package_success(tmp_path: Path) -> None:
    package_dir = tmp_path / "cli_package"

    result = _cli("wonder", "init-package", str(package_dir), "--scene-id", "cli_scene")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert Path(payload["manifest_path"]).name == SCENE_PACKAGE_MANIFEST_FILENAME
    assert (package_dir / "source").is_dir()
