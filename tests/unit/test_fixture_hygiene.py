from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures"
FIXTURE_README = FIXTURE_ROOT / "README.md"
ALLOWED_TOP_LEVEL = {
    "__init__.py",
    "README.md",
    "codex_imagegen_samples",
    "fmt",
    "mock_blender.py",
    "mock_codex_imagegen.py",
    "mock_hunyuan.py",
    "mock_vggt.py",
    "mock_xatlas.py",
    "sample_programs.py",
    "telemetry",
}


def test_fixture_directory_contains_only_documented_top_level_entries() -> None:
    observed = {path.name for path in FIXTURE_ROOT.iterdir()}

    assert observed == ALLOWED_TOP_LEVEL


def test_fixture_readme_documents_every_committed_fixture() -> None:
    text = FIXTURE_README.read_text(encoding="utf-8")
    missing = [name for name in sorted(ALLOWED_TOP_LEVEL - {"README.md", "__init__.py"}) if name not in text]

    assert missing == []


def test_fixture_tree_has_no_generated_caches_or_large_unreviewed_files() -> None:
    offenders: list[str] = []
    for path in FIXTURE_ROOT.rglob("*"):
        rel = path.relative_to(FIXTURE_ROOT).as_posix()
        if "__pycache__" in path.parts:
            offenders.append(rel)
            continue
        if path.is_file() and path.stat().st_size > 64 * 1024:
            offenders.append(rel)

    assert offenders == []
