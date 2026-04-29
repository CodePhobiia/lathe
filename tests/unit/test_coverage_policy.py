from __future__ import annotations

import configparser
import os
import tomllib
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_THRESHOLD = 65
EXPECTED_PACKAGE_GATES = {
    "parser": {"fail_under": 60, "paths": ["lathe/parser"]},
    "resolver": {"fail_under": 90, "paths": ["lathe/resolver.py"]},
    "checker": {"fail_under": 70, "paths": ["lathe/checker"]},
    "planner": {"fail_under": 90, "paths": ["lathe/planner.py"]},
    "provider_config": {
        "fail_under": 75,
        "paths": [
            "lathe/runtime_config.py",
            "lathe/providers/registry.py",
            "lathe/providers/selection.py",
        ],
    },
    "sandboxing": {"fail_under": 55, "paths": ["lathe/sandbox", "lathe/subproc.py"]},
    "cache": {"fail_under": 70, "paths": ["lathe/cache.py"]},
    "cli": {"fail_under": 35, "paths": ["lathe/cli"]},
    "telemetry": {"fail_under": 80, "paths": ["lathe/telemetry.py"]},
    "security": {
        "fail_under": 75,
        "paths": [
            "lathe/parser/prompt_injection.py",
            "lathe/net.py",
            "lathe/publish/signed_repro.py",
        ],
    },
    "scene": {"fail_under": 45, "paths": ["lathe/scene"]},
    "wonder": {"fail_under": 55, "paths": ["lathe/wonder"]},
}
EXPECTED_EXCLUDE_LINES = ["pragma: no cover"]


def _pyproject() -> dict:
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _coveragerc() -> configparser.ConfigParser:
    coveragerc = configparser.ConfigParser()
    coveragerc.read(REPO_ROOT / ".coveragerc", encoding="utf-8")
    return coveragerc


def _coveragerc_gates() -> dict[str, dict[str, object]]:
    gates: dict[str, dict[str, object]] = {}
    for name, raw_value in _coveragerc()["lathe:coverage_gates"].items():
        threshold, paths = raw_value.split("|", maxsplit=1)
        gates[name] = {
            "fail_under": int(threshold),
            "paths": [path.strip() for path in paths.split(",")],
        }
    return gates


def _path_matches_coverage_filename(configured_path: str, filename: str) -> bool:
    normalized_path = configured_path.removeprefix("lathe/").replace("\\", "/").rstrip("/")
    normalized_filename = filename.replace("\\", "/")
    return normalized_filename == normalized_path or normalized_filename.startswith(f"{normalized_path}/")


def _line_rate_for_paths(report_path: Path, configured_paths: list[str]) -> float:
    root = ET.parse(report_path).getroot()
    valid = 0
    covered = 0
    for class_node in root.findall(".//class"):
        filename = class_node.attrib.get("filename", "")
        if not any(_path_matches_coverage_filename(path, filename) for path in configured_paths):
            continue
        for line in class_node.findall("lines/line"):
            valid += 1
            if int(line.attrib.get("hits", "0")) > 0:
                covered += 1
    assert valid > 0, f"No coverage rows matched {configured_paths!r} in {report_path}"
    return covered / valid * 100


def test_coverage_threshold_is_single_ratchet_value() -> None:
    coveragerc = _coveragerc()
    pyproject = _pyproject()

    coveragerc_threshold = int(coveragerc["report"]["fail_under"])
    pyproject_threshold = int(pyproject["tool"]["coverage"]["report"]["fail_under"])

    assert coveragerc_threshold == pyproject_threshold == EXPECTED_THRESHOLD


def test_package_coverage_gates_are_declared_in_both_configs() -> None:
    pyproject_gates = _pyproject()["tool"]["lathe"]["coverage_gates"]

    assert pyproject_gates == EXPECTED_PACKAGE_GATES
    assert _coveragerc_gates() == EXPECTED_PACKAGE_GATES


def test_coverage_does_not_exclude_live_code_patterns() -> None:
    coveragerc_excludes = [
        value.strip()
        for _, value in _coveragerc().items("report")
        if value.strip() and value.strip() != "exclude_lines"
    ]
    pyproject_excludes = _pyproject()["tool"]["coverage"]["report"]["exclude_lines"]

    assert coveragerc_excludes[-len(EXPECTED_EXCLUDE_LINES) :] == EXPECTED_EXCLUDE_LINES
    assert pyproject_excludes == EXPECTED_EXCLUDE_LINES


def test_package_coverage_gate_paths_are_existing_non_adapter_sources() -> None:
    offenders: list[str] = []
    for name, gate in EXPECTED_PACKAGE_GATES.items():
        source_files: list[Path] = []
        for configured_path in gate["paths"]:
            path = REPO_ROOT / configured_path
            if "lathe/providers/adapters" in configured_path.replace("\\", "/"):
                offenders.append(f"{name}: provider adapter path is out of scope: {configured_path}")
            if not path.exists():
                offenders.append(f"{name}: missing path: {configured_path}")
            elif path.is_dir():
                source_files.extend(child for child in path.rglob("*.py") if "__pycache__" not in child.parts)
            elif path.suffix == ".py":
                source_files.append(path)
        if not source_files:
            offenders.append(f"{name}: no Python source files covered by gate")

    assert offenders == []


def test_requested_package_coverage_report_satisfies_gates() -> None:
    report = os.environ.get("LATHE_COVERAGE_GATE_XML")
    if not report:
        return

    report_path = Path(report)
    if not report_path.is_absolute():
        report_path = REPO_ROOT / report_path
    failures = []
    for name, gate in EXPECTED_PACKAGE_GATES.items():
        line_rate = _line_rate_for_paths(report_path, list(gate["paths"]))
        threshold = int(gate["fail_under"])
        if line_rate < threshold:
            failures.append(f"{name}: {line_rate:.2f}% < {threshold}%")

    assert failures == []


def test_ci_coverage_does_not_override_configured_threshold() -> None:
    checked_files = [
        ".github/workflows/coverage.yml",
        "Justfile",
    ]

    offenders = [
        relative_path
        for relative_path in checked_files
        if "--cov-fail-under" in (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    ]

    assert offenders == []
