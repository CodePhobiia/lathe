"""Phase 7 tests for ``lathe.asset_quality.highlow_relation``.

Covers per task #7 of ``docs/asset-quality/improvement-tasklist.md``:

- ``BakeMapEvidence`` and ``HighlowEvidence`` are frozen dataclasses.
- The fake fixture (no URIs, no maps) yields ``realness_score <= 0.05``,
  fires the warning, and verdict is ``False``.
- The mid-tier fixture mirroring industrial_crate (distinct URIs,
  identical triangle counts, four bake maps) yields a score in
  ``[0.30, 0.55]`` and fires the warning.
- The real fixture (distinct URIs, >= 30% triangle delta, four bake
  maps, no skipped reasons) yields ``realness_score >= 0.80`` and
  clears the warning.
- The skipped-evidence fixture (no high mesh URI) records structured
  ``skipped_reason`` entries and keeps the verdict negative.
- Default mode keeps ``diagnostics`` empty even when verdict fails.
- Strict mode opt-in via ``LATHE_STRICT_HIGHLOW=1`` produces a
  ``severity="error"`` diagnostic; default keeps it empty.
- Phase 1's ``highlow_fake_detail_penalty`` consumes the new evidence
  when ``runtime["highlow_relation"]`` is present.
- Phase 1's metric falls back to the legacy heuristic when the new
  evidence is absent.
- The evaluator is deterministic — identical input yields identical
  output.
- The payload shape contract is exactly the 18 keys declared in the
  master prompt.
- The ``FunctionValidator`` wrapper preserves ``passes`` semantics —
  default mode keeps ``passes=True``; strict mode flips it to
  ``passes=False`` when the verdict fails.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from lathe.asset_quality.diagnostics import evaluate_quality_diagnostics
from lathe.asset_quality.highlow_relation import (
    HIGHLOW_RELATION_VERSION,
    BakeMapEvidence,
    HighlowEvidence,
    evaluate_highlow_relation,
)
from lathe.validators.composition import FunctionValidator

_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "is_real_highlow",
        "realness_score",
        "high_mesh_uri",
        "low_mesh_uri",
        "runtime_low_uri",
        "high_triangle_count",
        "low_triangle_count",
        "triangle_delta_ratio",
        "distinct_uris",
        "distinct_triangle_counts",
        "bake_maps",
        "bake_map_count_present",
        "bake_map_count_expected",
        "skipped_reasons",
        "warnings",
        "diagnostics",
        "required",
    }
)


def _bake_outputs_full() -> dict[str, Any]:
    """Return a surface ``outputs`` dict with all four canonical maps."""
    return {
        "normal": {"uri": "stages/surface/maps/normal.png"},
        "ao": {"uri": "stages/surface/maps/ao.png"},
        "curvature": {"uri": "stages/surface/maps/curvature.png"},
        "id": {"uri": "stages/surface/maps/id.png"},
    }


def _runtime_fake() -> dict[str, Any]:
    """Runtime with no high-poly source and no bake maps."""
    return {
        "surface": {
            "bundle": {
                "highlow_relation": {
                    "high_mesh_uri": None,
                    "low_mesh_uri": None,
                    "high_triangle_count": 0,
                    "low_triangle_count": 0,
                },
                "outputs": {},
                "bake_outputs": {},
            }
        },
        "topology": {"bundle": {"mesh_uri": ""}},
    }


def _runtime_industrial_crate() -> dict[str, Any]:
    """Runtime mirroring the industrial_crate baseline (mid-tier)."""
    return {
        "surface": {
            "bundle": {
                "highlow_relation": {
                    "high_mesh_uri": "stages/shape/candidate_01.glb",
                    "low_mesh_uri": "stages/topology/topology.glb",
                    "high_triangle_count": 1376,
                    "low_triangle_count": 1376,
                },
                "outputs": _bake_outputs_full(),
                "bake_outputs": {
                    "normal": "stages/surface/maps/normal.png",
                    "ao": "stages/surface/maps/ao.png",
                    "curvature": "stages/surface/maps/curvature.png",
                    "id": "stages/surface/maps/id.png",
                },
            }
        },
        "topology": {"bundle": {"mesh_uri": "stages/topology/topology.glb"}},
    }


def _runtime_real() -> dict[str, Any]:
    """Runtime with distinct URIs, 30%+ triangle delta, and four bake maps."""
    return {
        "surface": {
            "bundle": {
                "highlow_relation": {
                    "high_mesh_uri": "stages/shape/candidate_01_high.glb",
                    "low_mesh_uri": "stages/topology/topology_low.glb",
                    "high_triangle_count": 4000,
                    "low_triangle_count": 1376,
                },
                "outputs": _bake_outputs_full(),
            }
        },
        "topology": {"bundle": {"mesh_uri": "stages/topology/topology_low.glb"}},
    }


def _runtime_inverted_counts() -> dict[str, Any]:
    """Runtime with low-poly triangles exceeding the high-poly source."""
    return {
        "surface": {
            "bundle": {
                "highlow_relation": {
                    "high_mesh_uri": "stages/shape/high.glb",
                    "low_mesh_uri": "stages/topology/low.glb",
                    "high_triangle_count": 1000,
                    "low_triangle_count": 2000,
                },
                "outputs": _bake_outputs_full(),
            }
        },
        "topology": {"bundle": {"mesh_uri": "stages/topology/low.glb"}},
    }


def _runtime_skipped() -> dict[str, Any]:
    """Runtime with a missing high-poly source plus partial bake outputs."""
    return {
        "surface": {
            "bundle": {
                "highlow_relation": {
                    "high_mesh_uri": None,
                    "low_mesh_uri": "stages/topology/topology.glb",
                    "high_triangle_count": 0,
                    "low_triangle_count": 1376,
                },
                "outputs": {
                    "normal": {"uri": "stages/surface/maps/normal.png"},
                },
            }
        },
        "topology": {"bundle": {"mesh_uri": "stages/topology/topology.glb"}},
    }


def _asset() -> dict[str, Any]:
    return {"name": "industrial_crate", "intent": {"parts": ["body"]}}


def _nonhero_asset() -> dict[str, Any]:
    return {"name": "generic_widget", "intent": {"parts": ["body"]}}


def test_bake_map_evidence_is_frozen() -> None:
    record = BakeMapEvidence(
        map_name="normal", present=True, uri="x.png", skipped_reason=None
    )
    with pytest.raises(FrozenInstanceError):
        record.present = False  # type: ignore[misc]


def test_highlow_evidence_is_frozen() -> None:
    record = HighlowEvidence(
        high_mesh_uri=None,
        low_mesh_uri=None,
        runtime_low_uri=None,
        high_triangle_count=None,
        low_triangle_count=None,
        distinct_uris=False,
        distinct_triangle_counts=False,
        triangle_delta_ratio=0.0,
        bake_maps=(),
        bake_map_count_present=0,
        bake_map_count_expected=4,
        skipped_reasons=(),
        is_real_highlow=False,
        realness_score=0.0,
        required=True,
    )
    with pytest.raises(FrozenInstanceError):
        record.realness_score = 1.0  # type: ignore[misc]


def test_payload_shape_contract_matches_eighteen_keys() -> None:
    payload = evaluate_highlow_relation(_asset(), _runtime_industrial_crate())
    assert set(payload.keys()) == _PAYLOAD_KEYS
    assert payload["version"] == HIGHLOW_RELATION_VERSION
    assert payload["required"] is True


def test_fake_fixture_is_clearly_fake() -> None:
    payload = evaluate_highlow_relation(_asset(), _runtime_fake())
    assert payload["realness_score"] <= 0.05
    assert payload["is_real_highlow"] is False
    assert payload["warnings"], "fake fixture should fire a warning"
    assert payload["bake_map_count_present"] == 0
    assert payload["bake_map_count_expected"] == 4


def test_industrial_crate_baseline_lands_in_mid_tier_band() -> None:
    payload = evaluate_highlow_relation(_asset(), _runtime_industrial_crate())
    assert 0.30 <= payload["realness_score"] <= 0.55, payload["realness_score"]
    assert payload["is_real_highlow"] is False
    assert payload["warnings"], "mid-tier fixture should fire a warning"
    assert payload["distinct_uris"] is True
    assert payload["distinct_triangle_counts"] is False
    assert payload["bake_map_count_present"] == 4


def test_real_fixture_clears_warning() -> None:
    payload = evaluate_highlow_relation(_asset(), _runtime_real())
    assert payload["realness_score"] >= 0.80, payload["realness_score"]
    assert payload["is_real_highlow"] is True
    assert payload["warnings"] == []
    assert payload["distinct_triangle_counts"] is True
    assert payload["triangle_delta_ratio"] >= 0.20
    assert payload["bake_map_count_present"] == 4
    assert payload["skipped_reasons"] == []


def test_inverted_triangle_counts_do_not_receive_detail_credit() -> None:
    payload = evaluate_highlow_relation(_asset(), _runtime_inverted_counts())

    assert payload["triangle_delta_ratio"] == 0.0
    assert payload["distinct_triangle_counts"] is True
    assert payload["is_real_highlow"] is False
    assert payload["warnings"], "inverted counts should fire a hero warning"
    assert "inverted high/low" in payload["warnings"][0]


def test_skipped_fixture_records_structured_reasons() -> None:
    payload = evaluate_highlow_relation(_asset(), _runtime_skipped())
    assert payload["is_real_highlow"] is False
    assert payload["warnings"], "skipped fixture should fire a warning"
    assert payload["skipped_reasons"], "skipped fixture should record reasons"
    reasons = {entry["reason"] for entry in payload["skipped_reasons"]}
    assert "no_high_poly_source" in reasons
    bake_reasons = {
        entry["skipped_reason"]
        for entry in payload["bake_maps"]
        if entry["skipped_reason"] is not None
    }
    assert bake_reasons == {"no_high_poly_source"}


def test_default_mode_emits_no_diagnostics_even_when_verdict_fails() -> None:
    payload = evaluate_highlow_relation(_asset(), _runtime_fake())
    assert payload["diagnostics"] == []


def test_strict_mode_flips_diagnostics_to_error_severity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LATHE_STRICT_HIGHLOW", "1")
    payload = evaluate_highlow_relation(_asset(), _runtime_fake())
    assert len(payload["diagnostics"]) == 1
    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == "L6701"
    assert diagnostic["name"] == "highlow_fake_detail"
    assert diagnostic["severity"] == "error"


def test_strict_mode_truthy_variants_all_enable_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for value in ("1", "true", "TRUE", "yes", "Yes"):
        monkeypatch.setenv("LATHE_STRICT_HIGHLOW", value)
        payload = evaluate_highlow_relation(_asset(), _runtime_fake())
        assert payload["diagnostics"], f"value {value!r} should enable strict mode"


def test_strict_mode_disabled_when_env_unset_or_falsy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LATHE_STRICT_HIGHLOW", raising=False)
    payload_unset = evaluate_highlow_relation(_asset(), _runtime_fake())
    assert payload_unset["diagnostics"] == []
    for value in ("0", "false", "no", ""):
        monkeypatch.setenv("LATHE_STRICT_HIGHLOW", value)
        payload = evaluate_highlow_relation(_asset(), _runtime_fake())
        assert payload["diagnostics"] == [], f"value {value!r} should not enable strict mode"


def test_strict_mode_does_not_diagnose_real_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LATHE_STRICT_HIGHLOW", "1")
    payload = evaluate_highlow_relation(_asset(), _runtime_real())
    assert payload["diagnostics"] == []


def test_nonhero_assets_do_not_require_highlow_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LATHE_STRICT_HIGHLOW", "1")
    runtime = _runtime_fake()

    payload = evaluate_highlow_relation(_nonhero_asset(), runtime)
    runtime["highlow_relation"] = payload
    quality_payload = evaluate_quality_diagnostics(_nonhero_asset(), runtime)

    assert payload["required"] is False
    assert payload["warnings"] == []
    assert payload["diagnostics"] == []
    assert quality_payload["metrics"]["highlow_fake_detail_penalty"] == 0.0
    assert not any("highlow_fake_detail_penalty" in w for w in quality_payload["warnings"])


def test_function_validator_default_passes_even_on_low_score() -> None:
    validator = FunctionValidator(
        name="highlow_relation",
        fn=evaluate_highlow_relation,
        stage_dependencies=["topology", "surface"],
        weight=0.0,
    )
    runtime = _runtime_fake()
    runtime["topology"] = {"bundle": {"mesh_uri": ""}}
    runtime["surface"]["bundle"].setdefault("backend_id", "test")
    report = validator.evaluate(runtime, _asset(), artifacts={})
    assert report["passes"] is True
    assert report["diagnostics"] == []


def test_function_validator_strict_mode_flips_passes_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LATHE_STRICT_HIGHLOW", "1")
    validator = FunctionValidator(
        name="highlow_relation",
        fn=evaluate_highlow_relation,
        stage_dependencies=["topology", "surface"],
        weight=0.0,
    )
    runtime = _runtime_fake()
    runtime["topology"] = {"bundle": {"mesh_uri": ""}}
    runtime["surface"]["bundle"].setdefault("backend_id", "test")
    report = validator.evaluate(runtime, _asset(), artifacts={})
    assert report["passes"] is False
    assert report["diagnostics"], "strict mode should produce diagnostics"


def test_phase1_metric_consumes_new_evidence_when_present() -> None:
    runtime = _runtime_industrial_crate()
    highlow_payload = evaluate_highlow_relation(_asset(), runtime)
    runtime["highlow_relation"] = highlow_payload
    quality_payload = evaluate_quality_diagnostics(_asset(), runtime)
    metric_value = quality_payload["metrics"]["highlow_fake_detail_penalty"]
    expected = round(1.0 - highlow_payload["realness_score"], 6)
    assert metric_value == expected
    assert metric_value > 0.40


def test_phase1_metric_falls_back_when_new_evidence_absent() -> None:
    runtime = _runtime_industrial_crate()
    quality_payload = evaluate_quality_diagnostics(_asset(), runtime)
    metric_value = quality_payload["metrics"]["highlow_fake_detail_penalty"]
    assert 0.0 <= metric_value <= 1.0
    assert metric_value > 0.40


def test_evaluator_is_deterministic_across_calls() -> None:
    runtime = _runtime_industrial_crate()
    asset = _asset()
    first = evaluate_highlow_relation(asset, runtime)
    second = evaluate_highlow_relation(asset, runtime)
    assert first == second


def test_evaluator_tolerates_missing_surface_bundle() -> None:
    payload = evaluate_highlow_relation(_asset(), {})
    assert payload["version"] == HIGHLOW_RELATION_VERSION
    assert payload["is_real_highlow"] is False
    assert payload["realness_score"] == 0.0
    assert payload["bake_map_count_present"] == 0
    assert payload["high_mesh_uri"] is None


def test_runtime_low_uri_is_sourced_from_topology_bundle() -> None:
    payload = evaluate_highlow_relation(_asset(), _runtime_real())
    assert payload["runtime_low_uri"] == "stages/topology/topology_low.glb"


def test_bake_outputs_short_form_takes_precedence() -> None:
    runtime = _runtime_industrial_crate()
    runtime["surface"]["bundle"]["bake_outputs"] = {
        "normal": "override/normal.png",
        "ao": "override/ao.png",
        "curvature": "override/curvature.png",
        "id": "override/id.png",
    }
    payload = evaluate_highlow_relation(_asset(), runtime)
    map_uris = {entry["map_name"]: entry["uri"] for entry in payload["bake_maps"]}
    assert map_uris["normal"] == "override/normal.png"
