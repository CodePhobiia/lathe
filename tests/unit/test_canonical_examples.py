"""Fast validation for shipped canonical example sources."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from lathe.checker import check_program
from lathe.core.errors import BuildError
from lathe.executor import build_asset
from lathe.normalizer import normalize_program
from lathe.parser import parse_file, parse_text
from lathe.planner import build_plan
from lathe.resolver import materialize_asset
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_GLOBS = (
    "examples/*.lth",
    "examples/api/*.lth",
    "examples/corpus/*.lth",
)
EXPECTED_BUILD_LIMITATIONS: dict[str, set[str]] = {}
EXPECTED_RECONSTRUCT_EXAMPLES = {
    "examples/reconstruct_courier_from_mesh.lth": {
        "asset": "reconstruct_courier_from_mesh",
        "images": set(),
        "meshes": {"refs/source_block.obj"},
    },
    "examples/reconstruct_courier_from_views.lth": {
        "asset": "reconstruct_courier_from_views",
        "images": {"refs/courier_front.png", "refs/courier_side.png", "refs/materials.jpg"},
        "meshes": set(),
    },
}


def _example_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in EXAMPLE_GLOBS:
        paths.extend(REPO_ROOT.glob(pattern))
    return sorted(paths)


def _primary_decl_name(path: Path) -> str:
    local_program = parse_text(path.read_text(encoding="utf-8"))
    for key in ("assets", "variants"):
        declarations = local_program.get(key, [])
        if declarations:
            return str(declarations[0]["name"])
    raise AssertionError(f"{path.relative_to(REPO_ROOT).as_posix()} has no asset or variant declaration")


def _error_codes(report: dict) -> set[str]:
    return {
        str(diag["code"])
        for diag in report.get("diagnostics", [])
        if diag.get("severity") == "error" and diag.get("code")
    }


@pytest.mark.parametrize("source_path", _example_paths(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_canonical_example_compiler_layers(source_path: Path) -> None:
    """Every shipped example should normalize, check, plan, and materialize."""
    asset_name = _primary_decl_name(source_path)
    program = parse_file(source_path)

    normalized = normalize_program(program)
    assert normalized["module"]

    diagnostics = check_program(program)
    assert [diag for diag in diagnostics if diag["severity"] == "error"] == []

    plan = build_plan(program, asset_name)
    assert plan["asset"] == asset_name
    assert plan["effective_asset"]["name"] == asset_name

    effective = materialize_asset(program, asset_name)
    assert effective["name"] == asset_name


def test_expected_build_limitations_reference_existing_examples() -> None:
    """The slow build gate's expected-failure list must stay tied to real sources."""
    known_examples = {path.relative_to(REPO_ROOT).as_posix() for path in _example_paths()}
    assert set(EXPECTED_BUILD_LIMITATIONS).issubset(known_examples)


def test_canonical_examples_use_typed_interface_entries() -> None:
    """Shipped examples should teach typed sockets and pivots, not legacy anchors."""
    bare_socket_pattern = re.compile(r"\bsockets\s*=\s*\[\s*(?!\]|socket\()", re.MULTILINE)
    for source_path in _example_paths():
        rel_source = source_path.relative_to(REPO_ROOT).as_posix()
        text = source_path.read_text(encoding="utf-8")
        assert not re.search(r"\banchors\s*=", text), rel_source
        assert not bare_socket_pattern.search(text), rel_source


def test_reconstruct_examples_and_reference_inputs_are_accepted() -> None:
    """Reconstruct gallery examples must keep real, project-relative refs."""
    observed: dict[str, dict[str, object]] = {}
    for source_path in _example_paths():
        program = parse_file(source_path)
        for asset in program.get("assets", []):
            asset_name = str(asset["name"])
            effective = materialize_asset(program, asset_name)
            if effective.get("build", {}).get("shape", {}).get("mode") != "reconstruct":
                continue

            refs = effective.get("refs", {})
            rel_source = source_path.relative_to(REPO_ROOT).as_posix()
            observed[rel_source] = {
                "asset": asset_name,
                "images": set(refs.get("images", [])),
                "meshes": set(refs.get("meshes", [])),
            }

            for ref in refs.get("images", []):
                ref_path = _resolve_example_ref(source_path, ref)
                with Image.open(ref_path) as image:
                    image.verify()

            for ref in refs.get("meshes", []):
                ref_path = _resolve_example_ref(source_path, ref)
                assert ref_path.suffix.lower() == ".obj"
                assert ref_path.stat().st_size > 0

    assert observed == EXPECTED_RECONSTRUCT_EXAMPLES


def _resolve_example_ref(source_path: Path, ref: str) -> Path:
    ref_path = Path(ref)
    assert not ref_path.is_absolute()
    resolved = (source_path.parent / ref_path).resolve()
    assert resolved.is_relative_to(source_path.parent.resolve())
    assert resolved.is_file(), ref
    return resolved


@pytest.mark.slow
@pytest.mark.parametrize("source_path", _example_paths(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_canonical_example_build_evidence(source_path: Path, tmp_path: Path) -> None:
    """Build every canonical example and assert the observed certification contract.

    Examples absent from EXPECTED_BUILD_LIMITATIONS are expected to complete the
    full build path and certify. Listed examples are known validation failures:
    they still must run far enough to emit validate/report.json, and the report
    must expose the expected validation error codes instead of crashing earlier.
    """
    asset_name = _primary_decl_name(source_path)
    rel_source = source_path.relative_to(REPO_ROOT).as_posix()
    expected_errors = EXPECTED_BUILD_LIMITATIONS.get(rel_source)
    out_dir = tmp_path / asset_name
    program = parse_file(source_path)

    if expected_errors is None:
        report = build_asset(program, asset_name, out_dir)
        assert report["certified"] is True
        assert (out_dir / "build_report.json").is_file()
        return

    try:
        report = build_asset(program, asset_name, out_dir)
    except BuildError:
        report = None
    if report is not None:
        assert report["certified"] is False, (
            f"{rel_source} is still listed in EXPECTED_BUILD_LIMITATIONS but now certifies; "
            "remove it from the expected-limitation table."
        )

    report_path = out_dir / "stages" / "validate" / "report.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["certified"] is False
    assert _error_codes(report) == expected_errors
