"""Validate release metadata, version tags, and versioned release docs."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_URLS = {"Homepage", "Documentation", "Repository", "Issues", "Changelog"}
REQUIRED_CLASSIFIERS = {
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Multimedia :: Graphics :: 3D Modeling",
    "Topic :: Software Development :: Compilers",
}
VERSIONED_DOCS = (
    "README.md",
    "CHANGELOG.md",
    "docs/release/quality-bar.md",
    "docs/release/provenance.md",
    "docs/release/support-matrix.md",
)


def normalize_version_token(value: str) -> str:
    """Normalize a version or tag token for metadata comparisons."""
    token = value.strip().lower()
    if token.startswith("v"):
        token = token[1:]
    token = token.replace("-rc.", "rc")
    token = token.replace("-rc", "rc")
    return token.replace("rc.", "rc")


def display_version(value: str) -> str:
    """Return the public display spelling for a release version."""
    match = re.fullmatch(r"(\d+\.\d+\.\d+)rc(\d+)", normalize_version_token(value))
    if match:
        return f"{match.group(1)}-rc.{match.group(2)}"
    return value


def expected_tag_for_version(value: str) -> str:
    """Return the expected git tag for a package version."""
    return f"v{display_version(value)}"


def _load_pyproject(root: Path) -> dict[str, Any]:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _source_version(root: Path) -> str | None:
    init_text = (root / "lathe" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"\s*$', init_text, re.MULTILINE)
    return match.group(1) if match else None


def _latest_changelog_release(root: Path) -> str | None:
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    for match in re.finditer(r"^## \[([^\]]+)\]", text, re.MULTILINE):
        version = match.group(1)
        if version.lower() != "unreleased":
            return version
    return None


def _current_head_tags(root: Path) -> list[str]:
    git = shutil.which("git")
    if git is None:
        return []
    result = subprocess.run(
        [git, "tag", "--points-at", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def validate_release_metadata(
    root: Path = REPO_ROOT,
    *,
    expected_tag: str | None = None,
    require_current_tag: bool = False,
) -> list[str]:
    """Return release metadata validation failures."""
    failures: list[str] = []
    pyproject = _load_pyproject(root)
    project = pyproject.get("project", {})

    name = project.get("name")
    version = project.get("version")
    if name != "lathe":
        failures.append("project.name must be `lathe`")
    if not isinstance(version, str):
        failures.append("project.version must be a string")
        version = ""

    source_version = _source_version(root)
    if source_version != version:
        failures.append(f"lathe.__version__ ({source_version!r}) must match project.version ({version!r})")

    changelog_version = _latest_changelog_release(root)
    if normalize_version_token(changelog_version or "") != normalize_version_token(version):
        failures.append(
            f"latest CHANGELOG.md release ({changelog_version!r}) must match project.version ({version!r})"
        )

    release_tag = expected_tag or expected_tag_for_version(version)
    if normalize_version_token(release_tag) != normalize_version_token(version):
        failures.append(f"expected release tag {release_tag!r} must match project.version {version!r}")
    if require_current_tag:
        current_tags = _current_head_tags(root)
        if release_tag not in current_tags:
            failures.append(f"HEAD must be tagged {release_tag!r}; current HEAD tags: {current_tags!r}")

    readme = project.get("readme")
    if readme != "README.md" or not (root / str(readme)).is_file():
        failures.append("project.readme must point at README.md")

    license_value = project.get("license")
    license_text = license_value.get("text") if isinstance(license_value, dict) else license_value
    if license_text != "Apache-2.0":
        failures.append("project.license must be Apache-2.0")
    if "Apache License" not in (root / "LICENSE").read_text(encoding="utf-8"):
        failures.append("LICENSE must contain the Apache License text")

    requires_python = project.get("requires-python")
    if requires_python != ">=3.11":
        failures.append("project.requires-python must be >=3.11")

    classifiers = set(project.get("classifiers", []))
    missing_classifiers = sorted(REQUIRED_CLASSIFIERS - classifiers)
    if missing_classifiers:
        failures.append(f"project.classifiers missing required entries: {missing_classifiers!r}")
    unsupported_python_classifiers = sorted(
        classifier
        for classifier in classifiers
        if classifier.startswith("Programming Language :: Python :: 3.")
        and classifier
        not in {
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
        }
    )
    if unsupported_python_classifiers:
        failures.append(
            f"project.classifiers include unsupported Python versions: {unsupported_python_classifiers!r}"
        )

    dependencies = project.get("dependencies", [])
    if not dependencies:
        failures.append("project.dependencies must not be empty")
    for dependency in dependencies:
        if not isinstance(dependency, str) or "://" in dependency or " @ " in dependency:
            failures.append(f"runtime dependency must be a package specifier, got {dependency!r}")

    optional_dependencies = project.get("optional-dependencies", {})
    dependency_groups = pyproject.get("dependency-groups", {})
    for group_name in ("dev", "docs"):
        if optional_dependencies.get(group_name) != dependency_groups.get(group_name):
            failures.append(
                f"dependency-groups.{group_name} must mirror project.optional-dependencies.{group_name}"
            )

    urls = set(project.get("urls", {}))
    missing_urls = sorted(REQUIRED_URLS - urls)
    if missing_urls:
        failures.append(f"project.urls missing required entries: {missing_urls!r}")

    scripts = project.get("scripts", {})
    if scripts.get("lathe") != "lathe.cli:main":
        failures.append("project.scripts.lathe must point at lathe.cli:main")

    normalized_version = normalize_version_token(version)
    display = display_version(version)
    for relative_path in VERSIONED_DOCS:
        text = (root / relative_path).read_text(encoding="utf-8")
        if normalized_version not in normalize_version_token(text) and display not in text:
            failures.append(f"{relative_path} must mention the current release version {version!r}")

    support_matrix = (root / "docs" / "release" / "support-matrix.md").read_text(encoding="utf-8")
    for required_text in ("3.11", "3.12", "Python 3.13+", "Python <=3.10", "`requires-python` is `>=3.11`"):
        if required_text not in support_matrix:
            failures.append(f"docs/release/support-matrix.md must document {required_text!r}")

    return failures


def main(argv: list[str] | None = None) -> int:
    """Run the release metadata check CLI."""
    parser = argparse.ArgumentParser(
        description="Validate Lathe release package metadata and version agreement."
    )
    parser.add_argument(
        "--expected-tag",
        help=(
            "Release tag expected for this build, for example v0.2.0-rc.1. "
            "Defaults to the package version tag."
        ),
    )
    parser.add_argument(
        "--require-current-tag",
        action="store_true",
        help="Require HEAD to have the expected release tag. Use on release-candidate checkouts.",
    )
    args = parser.parse_args(argv)

    failures = validate_release_metadata(
        REPO_ROOT,
        expected_tag=args.expected_tag,
        require_current_tag=args.require_current_tag,
    )
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    version = _load_pyproject(REPO_ROOT)["project"]["version"]
    print(f"release metadata check passed for {expected_tag_for_version(version)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
