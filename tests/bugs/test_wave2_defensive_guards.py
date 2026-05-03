"""Wave 2 regression tests: defensive guards for narrow crash bugs.

Covers:

- C5  empty-extents in ``conformance._ratio_signature`` and
  ``validators.silhouette._ratio_signature`` / ``compare_scaffold_signature``.
- C6  ``repair_planner._ShapeRepairApplier._source_region_for_missing_part``
      with empty ``asset_graph.parts``.
- C7  ``parser.fast_parser_expr._call_after_name`` lookahead at EOF.
- C8  ``eval_harness._load_legacy_snapshot`` when no candidate matches
      ``selected_candidate_id``.
- C9  ``bridge.blender_plan._read_execution_bundle`` on missing /
      malformed bundle files.
- M11 ``checker.language.check_critics`` with a non-numeric ``weight``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lathe.bridge import blender_plan
from lathe.checker.language import check_critics
from lathe.conformance import _ratio_signature as conformance_ratio_signature
from lathe.errors import BuildError, LatheParseError
from lathe.parser import parse_text
from lathe.repair_planner import _ShapeRepairApplier
from lathe.shape_ir import ShapeIR, ShapeRegion
from lathe.validators.silhouette import _ratio_signature as silhouette_ratio_signature
from lathe.validators.silhouette import compare_scaffold_signature


# --- C5 -------------------------------------------------------------


def test_conformance_ratio_signature_handles_empty_extents() -> None:
    assert conformance_ratio_signature([]) == []
    assert conformance_ratio_signature([2.0, 1.0, 0.5]) == [1.0, 0.5, 0.25]


def test_silhouette_ratio_signature_handles_empty_extents() -> None:
    assert silhouette_ratio_signature([]) == []


def test_compare_scaffold_signature_handles_empty_actual_extents() -> None:
    score = compare_scaffold_signature(
        scaffold_signature={"projected_ratio": [1.0, 0.5, 0.25]},
        actual_extents=[],
        part_groups=[
            {"bounds_min": [0.0, 0.0, 0.0], "bounds_max": [1.0, 1.0, 1.0]},
            {"bounds_min": [1.0, 0.0, 0.0], "bounds_max": [2.0, 1.0, 1.0]},
        ],
    )
    assert isinstance(score, float)


# --- C6 -------------------------------------------------------------


def test_source_region_for_missing_part_with_empty_parts() -> None:
    region = ShapeRegion(
        name="r0",
        part="p",
        component="c",
        center=(0.0, 0.0, 0.0),
        extents=(1.0, 1.0, 1.0),
    )
    shape_ir = ShapeIR(
        asset_name="demo",
        family="demo",
        blueprint_id="demo_v1",
        symmetry_axis=None,
        units="cm",
        primitives=[],
        regions=[region],
        primitives_used=[],
        part_graph=[],
        signature={},
    )
    asset_graph = SimpleNamespace(parts=[])
    applier = _ShapeRepairApplier(asset_graph, shape_ir)
    # Should fall back to the first region instead of raising IndexError.
    result = applier._source_region_for_missing_part()
    assert result is not None
    assert result.name == "r0"


# --- C7 -------------------------------------------------------------


def test_parser_truncated_call_arg_raises_lathe_parse_error() -> None:
    with pytest.raises(LatheParseError):
        # Truncated call: parser would read past the last token without bounds.
        parse_text("asset Demo {\n  family: foo(\n}\n")


# --- C8 -------------------------------------------------------------


def test_load_legacy_snapshot_missing_candidate_raises_build_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lathe import eval_harness

    workspace = tmp_path
    build_dir = tmp_path / "build"
    (build_dir / "stages" / "shape").mkdir(parents=True)
    (build_dir / "stages" / "topology").mkdir(parents=True)
    (build_dir / "stages" / "interfaces").mkdir(parents=True)
    (build_dir / "stages" / "surface").mkdir(parents=True)
    (build_dir / "stages" / "shape" / "bundle.json").write_text(
        '{"selected_candidate_id": "nope", "candidates": [{"candidate_id": "a"}]}',
        encoding="utf-8",
    )
    (build_dir / "stages" / "topology" / "bundle.json").write_text(
        '{"part_groups": [], "mesh_uri": "stages/topology/topology.glb"}',
        encoding="utf-8",
    )
    (build_dir / "stages" / "interfaces" / "bundle.json").write_text("{}", encoding="utf-8")
    (build_dir / "stages" / "surface" / "bundle.json").write_text("{}", encoding="utf-8")
    benchmark = {"build_dir": "build"}
    with pytest.raises(BuildError, match="selected_candidate_id"):
        eval_harness._load_legacy_snapshot(workspace, benchmark)


# --- C9 -------------------------------------------------------------


def test_read_execution_bundle_missing_file_raises_build_error(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="could not read execution bundle"):
        blender_plan._read_execution_bundle(tmp_path)


def test_read_execution_bundle_invalid_json_raises_build_error(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "stages" / "execution"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "bundle.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(BuildError, match="not valid JSON"):
        blender_plan._read_execution_bundle(tmp_path)


def test_read_execution_bundle_non_object_raises_build_error(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "stages" / "execution"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "bundle.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(BuildError, match="not a JSON object"):
        blender_plan._read_execution_bundle(tmp_path)


# --- M11 ------------------------------------------------------------


def test_check_critics_emits_diagnostic_for_non_numeric_weight() -> None:
    diagnostics: list[dict] = []
    program = {
        "critics": [
            {
                "name": "demo",
                "body": {
                    "type": "weighted",
                    "items": [
                        {"weight": "high"},
                        {"weight": 0.5},
                    ],
                },
            }
        ]
    }
    checker = SimpleNamespace(program=program, diagnostics=diagnostics)
    check_critics(checker)
    codes = [diag.get("code") for diag in diagnostics]
    assert "L3203" in codes
    # The numeric item still contributed; total > 0 means no L3202 for the
    # zero-total path.
    assert "L3202" not in codes
