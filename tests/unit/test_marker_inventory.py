from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKER_PATTERN = r"\bTODO\b|\bFIXME\b|\bHACK\b|\bplaceholder\b|\bstub\b|NotImplemented"
SCAN_ROOTS = (".github", "docs", "lathe", "scripts", "docker")
TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".j2",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_PATHS = {
    "docs/marker_inventory.md",
}
TRACKED_MARKERS = {
    ".github/ISSUE_TEMPLATE/bug_report.yml": (
        'placeholder: "0.1.0"',
        'placeholder: "3.11.9"',
    ),
    ".github/ISSUE_TEMPLATE/release_blocker.yml": ('placeholder: "v0.2-rc-hardening"',),
    "docs/next_version_roadmap.md": (
        "stub backend IDs",
        "symbol-index stub",
    ),
    "docs/plan_completeness.md": ("lathe/lsp/` is a stub",),
    "docs/legal/compliance-review-v0.2.0rc1.md": ("placeholder.png",),
    "docs/release/asset-provenance.md": ("placeholder.png",),
    "docs/release/evidence-bundle-v0.2.0rc1/mypy.txt": (
        "missing stub packages",
        "library stub for module",
    ),
    "docs/security/ci_gates.md": ("placeholder (e.g.",),
    "docs/templates/gallery_index.html.j2": (".placeholder",),
    "lathe/mesh_ingest.py": ("NotImplementedError",),
    "lathe/asset_quality/vision_critique.py": (
        "stub",
        "Stub",
        "NotImplementedError",
    ),
    "docs/asset-quality/vision-critique-loop.md": (
        "stub",
        "Stub",
    ),
    "scripts/render_gallery.py": (
        "no_blender.txt` placeholder",
        '<div class="placeholder">',
    ),
}


def _scan_files() -> list[Path]:
    paths: list[Path] = []
    for root in SCAN_ROOTS:
        root_path = REPO_ROOT / root
        if not root_path.exists():
            continue
        paths.extend(
            path
            for path in root_path.rglob("*")
            if path.is_file()
            and path.suffix.lower() in TEXT_SUFFIXES
            and not any(
                part in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for part in path.parts
            )
        )
    return sorted(paths)


def test_active_markers_are_tracked() -> None:
    import re

    offenders: list[str] = []
    marker_re = re.compile(MARKER_PATTERN, re.IGNORECASE)
    for path in _scan_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in EXCLUDED_PATHS:
            continue
        tracked_needles = TRACKED_MARKERS.get(rel, ())
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not marker_re.search(line):
                continue
            if not any(needle in line for needle in tracked_needles):
                offenders.append(f"{rel}:{line_no}: {line.strip()}")

    assert offenders == []
