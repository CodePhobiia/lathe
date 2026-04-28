from __future__ import annotations

import re
from pathlib import Path

import pytest
from lathe.executor import build_asset
from lathe.parser import parse_file

REPO_ROOT = Path(__file__).resolve().parents[2]
QUICKSTART_SOURCE = REPO_ROOT / "examples" / "courier_drone.lth"
QUICKSTART_ASSET = "courier_drone"
QUICKSTART_DOCUMENTED_PATHS = (
    "build_report.json",
    "courier_drone.lathe_for_godot.json",
    "courier_drone.lathe_for_unity.yaml",
    "courier_drone.lathe_for_unreal.json",
    "materialized_asset.json",
    "normalized_program.json",
    "plan.json",
    "selector_manifest.json",
    "stages/shape/bundle.json",
    "stages/topology/bundle.json",
    "stages/uv/bundle.json",
    "stages/surface/bundle.json",
    "stages/validate/report.json",
    "stages/package/bundle.json",
    "stages/package/courier_drone.usda",
    "stages/package/courier_drone.glb",
    "stages/package/package_manifest.json",
    "stages/package/trace_manifest.json",
    "stages/package/previews/turntable.png",
    "stages/package/previews/wireframe.png",
    "stages/package/previews/uv_layout.png",
    "stages/package/previews/lod_sheet.png",
)


def _quickstart_mentions_path(text: str, relative_path: str) -> bool:
    if relative_path in text:
        return True
    stage_relative = relative_path.removeprefix("stages/")
    package_relative = relative_path.removeprefix("stages/package/")
    return stage_relative in text or package_relative in text or Path(relative_path).name in text


CURRENT_ARTIFACT_PATH_DOCS = [
    "docs/quickstart.md",
    "docs/cookbook/01_generate_flow.md",
    "docs/cookbook/reading_a_trace.md",
    "docs/tutorial/first_asset.md",
    "docs/tutorial/second_asset_reconstruct.md",
    "docs/business/design_partners.md",
    "docs/business/outreach_template.md",
    "docs/walkthroughs/01_godot_indie_crate_family.md",
    "docs/walkthroughs/03_agent_authored_panel.md",
    "docs/blog/01_the_build_passed.md",
    "docs/blog/02_3d_asset_generation_is_a_compiler_problem.md",
    "docs/blog/04_godot_integration_walkthrough.md",
]

LEGACY_TOP_LEVEL_ARTIFACT_PATTERNS = {
    "trace.json": re.compile(r"(?<![A-Za-z0-9_])trace\.json"),
    "manifest.json": re.compile(r"(?<![A-Za-z0-9_])manifest\.json"),
}


def test_current_artifact_docs_do_not_reference_legacy_top_level_paths() -> None:
    failures: list[str] = []
    for relative_path in CURRENT_ARTIFACT_PATH_DOCS:
        path = REPO_ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        for label, pattern in LEGACY_TOP_LEVEL_ARTIFACT_PATTERNS.items():
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                failures.append(f"{relative_path}:{line_no} still references {label}")

    assert failures == []


def test_cache_doc_distinguishes_cache_manifest_from_package_artifacts() -> None:
    text = (REPO_ROOT / "docs/cache.md").read_text(encoding="utf-8")

    assert "root `manifest.json` used only as cache metadata" in text
    assert "stages/package/package_manifest.json" in text
    assert "stages/package/trace_manifest.json" in text


@pytest.mark.slow
def test_quickstart_documented_artifact_paths_exist_after_fresh_build(tmp_path: Path) -> None:
    quickstart = (REPO_ROOT / "docs/quickstart.md").read_text(encoding="utf-8")
    missing_from_docs = [
        relative_path
        for relative_path in QUICKSTART_DOCUMENTED_PATHS
        if not _quickstart_mentions_path(quickstart, relative_path)
    ]
    assert missing_from_docs == []

    out_dir = tmp_path / QUICKSTART_ASSET
    build_asset(parse_file(QUICKSTART_SOURCE), QUICKSTART_ASSET, out_dir)

    missing_from_build = [
        relative_path
        for relative_path in QUICKSTART_DOCUMENTED_PATHS
        if not (out_dir / relative_path).is_file()
    ]
    assert missing_from_build == []
