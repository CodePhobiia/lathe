from __future__ import annotations

import ast
import fnmatch
import subprocess
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TESTS_ROOT.parent
GENERATED_LOCAL_PATTERNS = {
    ".coverage",
    ".coverage.*",
    "coverage.json",
    "coverage.lcov",
    "coverage.xml",
    "htmlcov/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    ".hypothesis/",
    ".lathe_lark_cache/",
    "__pycache__/",
    "*.pyc",
    "dist_*/",
    "tmp_*/",
    "warm_*/",
    "cache_probe_*/",
}
GENERATED_LOCAL_TOKENS = {
    ".coverage",
    "coverage.xml",
    "htmlcov",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".lathe_lark_cache",
}
GENERATED_TOKEN_ALLOWLIST = {
    Path("unit/test_asset_provenance_docs.py"),
    Path("unit/test_coverage_policy.py"),
    Path("unit/test_marker_inventory.py"),
    Path("unit/test_test_hygiene.py"),
}
REPO_ROOT_WRITE_TOKENS = (
    'ROOT / "dist',
    "ROOT / 'dist",
    'ROOT / "tmp_',
    "ROOT / 'tmp_",
    'ROOT / "warm_',
    "ROOT / 'warm_",
    'ROOT / "cache_probe_',
    "ROOT / 'cache_probe_",
    'REPO_ROOT / "dist',
    "REPO_ROOT / 'dist",
    'REPO_ROOT / "tmp_',
    "REPO_ROOT / 'tmp_",
    'REPO_ROOT / "warm_',
    "REPO_ROOT / 'warm_",
    'REPO_ROOT / "cache_probe_',
    "REPO_ROOT / 'cache_probe_",
)


def _test_files() -> list[Path]:
    return sorted(path for path in TESTS_ROOT.rglob("test_*.py") if "__pycache__" not in path.parts)


def test_runtime_pytest_skip_calls_have_reasons() -> None:
    offenders: list[str] = []
    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_pytest_skip = (
                isinstance(func, ast.Attribute)
                and func.attr == "skip"
                and isinstance(func.value, ast.Name)
                and func.value.id == "pytest"
            )
            if not is_pytest_skip:
                continue
            has_positional_reason = bool(node.args)
            has_keyword_reason = any(keyword.arg == "reason" for keyword in node.keywords)
            if not has_positional_reason and not has_keyword_reason:
                offenders.append(f"{path.relative_to(TESTS_ROOT)}:{node.lineno}")

    assert offenders == []


def test_tests_do_not_write_repo_root_tmp_outputs() -> None:
    offenders: list[str] = []
    for path in _test_files():
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in REPO_ROOT_WRITE_TOKENS):
            offenders.append(str(path.relative_to(TESTS_ROOT)))

    assert offenders == []


def test_generated_local_leftovers_are_ignored() -> None:
    gitignore_patterns = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    missing = sorted(GENERATED_LOCAL_PATTERNS - gitignore_patterns)

    assert missing == []


def test_tests_do_not_consume_generated_local_leftovers() -> None:
    offenders: list[str] = []
    for path in _test_files():
        relative_path = path.relative_to(TESTS_ROOT)
        if relative_path in GENERATED_TOKEN_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        for token in GENERATED_LOCAL_TOKENS:
            if token in text:
                offenders.append(f"{relative_path}:{token}")

    assert offenders == []


def test_generated_local_leftovers_are_not_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    offenders = sorted(
        path
        for path in tracked
        if any(fnmatch.fnmatch(path, token.rstrip("/")) for token in GENERATED_LOCAL_PATTERNS)
        or any(path.startswith(token.rstrip("/") + "/") for token in GENERATED_LOCAL_PATTERNS)
    )

    assert offenders == []
