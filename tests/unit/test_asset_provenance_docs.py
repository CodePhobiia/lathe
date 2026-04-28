from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_DOC = REPO_ROOT / "docs/release/asset-provenance.md"
BINARY_ASSET_SUFFIXES = {".glb", ".gltf", ".jpeg", ".jpg", ".obj", ".png", ".usd"}
ASSET_ROOTS = (REPO_ROOT / "examples", REPO_ROOT / "tests/fixtures")
GENERATED_BUILD_ROOT_PREFIXES = (
    "dist/",
    "dist_",
    "tmp_",
    "warm_",
    "_codex_tmp/",
    "site/",
    "htmlcov/",
)


def _asset_paths_requiring_provenance() -> list[str]:
    paths: list[str] = []
    for root in ASSET_ROOTS:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in BINARY_ASSET_SUFFIXES:
                paths.append(path.relative_to(REPO_ROOT).as_posix())
    return sorted(paths)


def _runtime_dependency_names() -> list[str]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names: list[str] = []
    for dependency in pyproject["project"]["dependencies"]:
        match = re.match(r"([A-Za-z0-9_.-]+)", dependency)
        if match:
            names.append(match.group(1).lower())
    return sorted(names)


def test_checked_in_binary_assets_have_release_provenance_entries() -> None:
    text = PROVENANCE_DOC.read_text(encoding="utf-8")
    missing = [path for path in _asset_paths_requiring_provenance() if f"`{path}`" not in text]
    assert missing == []


def test_direct_runtime_dependencies_are_listed_in_provenance_review() -> None:
    text = PROVENANCE_DOC.read_text(encoding="utf-8").lower()
    missing = [name for name in _runtime_dependency_names() if f"`{name}`" not in text]
    assert missing == []


def test_generated_build_artifacts_are_not_tracked_as_source() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    offenders = [
        path for path in tracked if any(path.startswith(prefix) for prefix in GENERATED_BUILD_ROOT_PREFIXES)
    ]
    assert offenders == []
