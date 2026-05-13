"""Phase 13 asset-quality validator integration tests.

Confirms the experimental block flows from the asset through the
Phase 2/11/12 validators:

- ``art_direction`` overrides the family-default brief.
- ``references.use`` overrides the executor's reference-board base path.
- ``kit.use`` lands in the kit-library evidence as user-declared parts.

Also includes one end-to-end build verification that
``examples/industrial_crate_experimental.lth`` certifies and surfaces the
``user_provided_via_experimental`` annotations on all three evidence
sections.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from lathe.asset_quality.design_brief import evaluate_design_brief
from lathe.asset_quality.kit_library import (
    evaluate_kit_library,
    load_kit_library,
)
from lathe.asset_quality.reference_board import (
    evaluate_reference_board,
    load_reference_board,
)
from lathe.executor import build_asset
from lathe.parser import parse_file

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = _REPO_ROOT / "examples" / "refs" / "asset_quality" / "industrial_crate"
_EXPERIMENTAL_EXAMPLE = _REPO_ROOT / "examples" / "industrial_crate_experimental.lth"
_KIT_LIBRARY_BASE = _REPO_ROOT / "std" / "kits" / "hardsurface"


def test_design_brief_consumes_art_direction_overrides() -> None:
    asset: dict[str, Any] = {
        "name": "industrial_crate",
        "intent": {"role": "cargo"},
        "experimental": {
            "art_direction": {
                "style_tags": ["weathered_industrial", "well_used"],
                "wear": "heavy",
                "material_age": "aged",
                "detail_density": "high",
            }
        },
    }
    payload = evaluate_design_brief(asset, {})
    assert payload["brief"]["wear"] == "heavy"
    assert payload["brief"]["material_age"] == "aged"
    assert payload["brief"]["detail_density"] == "high"
    assert payload["brief"]["style_tags"] == ["weathered_industrial", "well_used"]
    assert payload["user_provided_via_experimental"]["fields"] == [
        "style_tags",
        "wear",
        "material_age",
        "detail_density",
    ]


def test_design_brief_without_overrides_has_empty_fields_list() -> None:
    asset: dict[str, Any] = {"name": "industrial_crate", "intent": {"role": "cargo"}}
    payload = evaluate_design_brief(asset, {})
    assert payload["user_provided_via_experimental"] == {"fields": []}


def test_design_brief_overrides_only_whitelisted_fields() -> None:
    asset: dict[str, Any] = {
        "name": "industrial_crate",
        "intent": {"role": "cargo"},
        "experimental": {
            "art_direction": {
                "wear": "heavy",
                "silhouette": "compact",  # not in the MVP whitelist
            }
        },
    }
    payload = evaluate_design_brief(asset, {})
    assert payload["brief"]["wear"] == "heavy"
    # Family default silhouette is unaffected by the unknown override.
    assert payload["brief"]["silhouette"] == "bold"
    assert payload["user_provided_via_experimental"]["fields"] == ["wear"]


def test_reference_board_uses_experimental_path() -> None:
    raw = load_reference_board("industrial_crate", base_path=_FIXTURE_PATH.parent)
    assert raw is not None
    runtime = {
        "_reference_board": raw,
        "_reference_board_user_provided_via_experimental": True,
    }
    payload = evaluate_reference_board(
        {"name": "industrial_crate"}, runtime
    )
    assert payload["user_provided_via_experimental"] is True
    assert payload["summary"]["all_required_present"] is True


def test_reference_board_without_experimental_is_false() -> None:
    raw = load_reference_board("industrial_crate", base_path=_FIXTURE_PATH.parent)
    runtime = {
        "_reference_board": raw,
        "_reference_board_user_provided_via_experimental": False,
    }
    payload = evaluate_reference_board(
        {"name": "industrial_crate"}, runtime
    )
    assert payload["user_provided_via_experimental"] is False


def test_kit_library_surfaces_user_declared_parts() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime = {"_kit_library": library}
    asset: dict[str, Any] = {
        "name": "industrial_crate",
        "experimental": {
            "kit": {
                "use": ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"],
            }
        },
    }
    payload = evaluate_kit_library(asset, runtime)
    assert payload["user_provided_via_experimental"] == {
        "declared_parts": ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]
    }


def test_kit_library_does_not_filter_loaded_parts_by_user_declaration() -> None:
    """Phase 13: ``kit.use`` is informational evidence only — the library
    surfaces all parts as before regardless of the declared list."""
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime = {"_kit_library": library}
    asset_full: dict[str, Any] = {
        "name": "industrial_crate",
        "experimental": {"kit": {"use": ["fasteners.hex_bolt_m6"]}},
    }
    payload_full = evaluate_kit_library(asset_full, runtime)

    asset_no_decl: dict[str, Any] = {"name": "industrial_crate"}
    payload_no_decl = evaluate_kit_library(asset_no_decl, runtime)

    assert payload_full["library"]["parts"] == payload_no_decl["library"]["parts"]
    assert (
        payload_full["summary"]["part_count"] == payload_no_decl["summary"]["part_count"]
    )


def test_kit_library_empty_user_provided_when_no_experimental_kit() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime = {"_kit_library": library}
    payload = evaluate_kit_library({"name": "industrial_crate"}, runtime)
    assert payload["user_provided_via_experimental"] == {"declared_parts": []}


@pytest.mark.skipif(
    not (_REPO_ROOT / ".tmp_tests" / "phase13_experimental").exists()
    or not (
        _REPO_ROOT
        / ".tmp_tests"
        / "phase13_experimental"
        / "industrial_crate"
        / "stages"
        / "validate"
        / "report.json"
    ).exists(),
    reason=(
        "Run `python -m lathe.cli build examples/industrial_crate_experimental.lth "
        "industrial_crate --out .tmp_tests/phase13_experimental --deterministic` "
        "to enable this end-to-end check."
    ),
)
def test_industrial_crate_experimental_example_builds_successfully() -> None:
    report_path = (
        _REPO_ROOT
        / ".tmp_tests"
        / "phase13_experimental"
        / "industrial_crate"
        / "stages"
        / "validate"
        / "report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["certified"] is True
    # 26 top-level keys preserved (Phase 13 adds NO new top-level key).
    expected_keys = {
        "certified",
        "threshold",
        "score",
        "semantic_quality",
        "visual_quality",
        "flow_quality",
        "geometry_integrity",
        "urdf_validation",
        "rule_results",
        "diagnostics",
        "repair_policy",
        "repair_suggestions",
        "failure_summary",
        "semantic_repairs_applied",
        "reselection_attempts",
        "quality_diagnostics",
        "design_brief",
        "family_grammar",
        "construction_graph",
        "grammar_lowering",
        "highlow_relation",
        "material_wear_graph",
        "preview_evidence",
        "vision_critique",
        "reference_board",
        "kit_library",
    }
    assert expected_keys.issubset(report.keys())
    assert report["design_brief"]["user_provided_via_experimental"]["fields"] == [
        "style_tags",
        "wear",
        "material_age",
        "detail_density",
    ]
    assert report["reference_board"]["user_provided_via_experimental"] is True
    assert report["kit_library"]["user_provided_via_experimental"][
        "declared_parts"
    ] == ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]


@pytest.mark.slow
def test_industrial_crate_experimental_example_builds_in_tempdir() -> None:
    """End-to-end build of the Phase 13 experimental example.

    Mirrors the established pattern from
    ``tests/test_language_v13_1.py::test_v13_1_build_emits_bridge_and_evidence_ir``:
    parse the source, build into a ``tempfile.TemporaryDirectory()``, and
    assert on the published validate report. Closes the test gap left by
    the conditionally-skipped artifact-presence check above.
    """
    program = parse_file(_EXPERIMENTAL_EXAMPLE)
    with tempfile.TemporaryDirectory(prefix="lathe_phase13_experimental_") as tmpdir:
        out_dir = Path(tmpdir) / "industrial_crate"
        report = build_asset(program, "industrial_crate", out_dir)
        assert report["certified"] is True

        validate_report = json.loads(
            (out_dir / "stages" / "validate" / "report.json").read_text(encoding="utf-8")
        )
        assert validate_report["design_brief"]["user_provided_via_experimental"][
            "fields"
        ] == ["style_tags", "wear", "material_age", "detail_density"]
        assert validate_report["reference_board"]["user_provided_via_experimental"] is True
        assert validate_report["kit_library"]["user_provided_via_experimental"][
            "declared_parts"
        ] == ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]
