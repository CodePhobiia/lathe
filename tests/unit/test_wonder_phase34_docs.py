from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs" / "wonder-readiness"
MKDOCS = REPO_ROOT / "mkdocs.yml"


def test_phase34_docs_exist_and_state_runtime_boundaries() -> None:
    required = {
        "06_scene_language.md": (
            "Scene Graph",
            "deferred",
            "JSON-first",
            "tests/unit/test_scene_source_roundtrip.py",
        ),
        "08_scene_package.md": (
            "lathe.scene_package_manifest.v1",
            "scene package validate",
            "proxy",
            "tests/unit/test_scene_package_manifest.py",
        ),
        "12_world_memory.md": (
            "lathe.world_memory.v1",
            "graph/world_memory.json",
            "idempotent",
            "tests/unit/test_wonder_memory.py",
        ),
        "15_mvp_demo.md": (
            "Alchemist Observatory",
            "demo-before-after",
            "semantic visual evaluation remains `not_evaluated`",
            "full runtime readiness gates",
        ),
    }

    for filename, expected_terms in required.items():
        text = (DOCS / filename).read_text(encoding="utf-8")
        assert text.startswith("# ")
        for term in expected_terms:
            assert term in text


def test_phase34_docs_are_in_mkdocs_nav() -> None:
    nav = MKDOCS.read_text(encoding="utf-8")

    for target in (
        "wonder-readiness/06_scene_language.md",
        "wonder-readiness/08_scene_package.md",
        "wonder-readiness/12_world_memory.md",
        "wonder-readiness/15_mvp_demo.md",
    ):
        assert target in nav
