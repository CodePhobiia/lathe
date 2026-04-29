"""Phase 3 tests for ``lathe.asset_quality.family_grammar``.

Covers per task #3.4 of ``docs/asset-quality/improvement-tasklist.md``:

- ``FamilyRequirement`` / ``FamilyGrammar`` / ``FamilyGrammarResult``
  dataclasses construct correctly and stay frozen.
- The ``industrial_crate`` grammar has 10 requirements with 4 required +
  6 recommended severities.
- Coverage formula: empty asset -> 0.0; full coverage -> 1.0; the actual
  ``industrial_crate.lth`` baseline parts list -> 0.40.
- Per-requirement status is correct (satisfied vs missing) for
  representative inputs.
- Recommendations are emitted one per missing/partial requirement.
- Generic fallback grammar: unknown family -> coverage=1.0, no
  recommendations, no requirement_results.
- Missing ``runtime["design_brief"]`` falls back to generic gracefully.
- Missing ``intent`` / missing ``parts`` does not crash.
- Payload shape matches the master prompt exactly.
- Determinism: same input -> same output.
- Case-insensitive part matching.
- Absence of a ``diagnostics`` field so the FunctionValidator wrapper
  treats the validator as passing.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from lathe.asset_quality.family_grammar import (
    FAMILY_GRAMMAR_VERSION,
    FamilyGrammar,
    FamilyGrammarResult,
    FamilyRequirement,
    evaluate_family_grammar,
)


_EXPECTED_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "family",
        "coverage",
        "satisfied_count",
        "partial_count",
        "missing_count",
        "requirement_results",
        "recommendations",
    }
)


_INDUSTRIAL_CRATE_REQUIREMENT_NAMES: tuple[str, ...] = (
    "body_shell",
    "lid_seam",
    "corner_guards",
    "latch_or_latch_plate",
    "recessed_or_bracketed_handles",
    "foot_rails_or_feet",
    "trim_bands",
    "fasteners",
    "warning_or_decal_zones",
    "edge_wear_masks",
)


def _runtime_with_family(family: str) -> dict[str, Any]:
    """Build a runtime that publishes a Phase 2-style design_brief block."""
    return {"design_brief": {"brief": {"family": family}}}


def _crate_runtime() -> dict[str, Any]:
    return _runtime_with_family("industrial_crate")


def test_family_requirement_dataclass_is_frozen() -> None:
    req = FamilyRequirement(
        name="body_shell",
        description="primary body shell",
        severity="required",
        detection_signals=("body",),
        recommendation_template="Add a body shell.",
    )

    assert req.name == "body_shell"
    assert req.severity == "required"
    assert req.detection_signals == ("body",)
    assert req.recommendation_template == "Add a body shell."
    with pytest.raises(FrozenInstanceError):
        req.severity = "optional"  # type: ignore[misc]


def test_family_grammar_dataclass_is_frozen() -> None:
    requirement = FamilyRequirement(
        name="body_shell",
        description="primary body shell",
        severity="required",
        detection_signals=("body",),
        recommendation_template="Add a body shell.",
    )
    grammar = FamilyGrammar(
        family="industrial_crate",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=(requirement,),
    )

    assert grammar.family == "industrial_crate"
    assert grammar.version == "family_grammar_v1"
    assert grammar.requirements == (requirement,)
    with pytest.raises(FrozenInstanceError):
        grammar.family = "mechanical_door"  # type: ignore[misc]


def test_family_grammar_result_dataclass_is_frozen() -> None:
    sample = FamilyGrammarResult(
        family="industrial_crate",
        version=FAMILY_GRAMMAR_VERSION,
        requirement_results=(
            {
                "name": "body_shell",
                "severity": "required",
                "status": "satisfied",
                "evidence": {"matched_parts": ["body"]},
            },
        ),
        coverage=1.0,
        satisfied_count=1,
        partial_count=0,
        missing_count=0,
        recommendations=(),
    )

    assert getattr(sample, "coverage") == 1.0
    assert sample.satisfied_count == 1
    with pytest.raises(FrozenInstanceError):
        setattr(sample, "coverage", 0.0)


def test_industrial_crate_grammar_has_ten_requirements_in_canonical_order() -> None:
    asset: dict[str, Any] = {"intent": {"parts": []}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _INDUSTRIAL_CRATE_REQUIREMENT_NAMES
    assert len(payload["requirement_results"]) == 10


def test_industrial_crate_grammar_severity_split_matches_master_prompt() -> None:
    """Master-prompt Section 2 table: body_shell, lid_seam, corner_guards,
    latch_or_latch_plate, recessed_or_bracketed_handles are ``required``;
    foot_rails_or_feet, trim_bands, fasteners, warning_or_decal_zones,
    edge_wear_masks are ``recommended``. No ``optional`` requirements at
    Phase 3."""
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    severities = [item["severity"] for item in payload["requirement_results"]]
    assert severities.count("required") == 5
    assert severities.count("recommended") == 5
    assert severities.count("optional") == 0


def test_industrial_crate_required_set_matches_master_prompt() -> None:
    """Required = body_shell, lid_seam, corner_guards, latch_or_latch_plate,
    recessed_or_bracketed_handles. Locks the canonical encoding."""
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    required_names = {
        item["name"]
        for item in payload["requirement_results"]
        if item["severity"] == "required"
    }
    assert required_names == {
        "body_shell",
        "lid_seam",
        "corner_guards",
        "latch_or_latch_plate",
        "recessed_or_bracketed_handles",
    }


def test_payload_shape_matches_phase_3_contract() -> None:
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    assert payload["version"] == FAMILY_GRAMMAR_VERSION
    assert FAMILY_GRAMMAR_VERSION == "family_grammar_v1"
    assert set(payload.keys()) == _EXPECTED_PAYLOAD_KEYS
    assert isinstance(payload["coverage"], float)
    assert isinstance(payload["requirement_results"], list)
    assert isinstance(payload["recommendations"], list)
    assert isinstance(payload["satisfied_count"], int)
    assert isinstance(payload["partial_count"], int)
    assert isinstance(payload["missing_count"], int)


def test_no_diagnostics_field_so_validator_pipeline_treats_as_passing() -> None:
    """Mirrors Phase 1/2's contract: ``FunctionValidator`` only flips
    ``passes`` to ``False`` when a diagnostics entry has ``severity == 'error'``.
    Returning no ``diagnostics`` field keeps the validator passing."""
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    assert "diagnostics" not in payload


def test_empty_asset_yields_zero_coverage_for_industrial_crate() -> None:
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    assert payload["family"] == "industrial_crate"
    assert payload["coverage"] == 0.0
    assert payload["satisfied_count"] == 0
    assert payload["partial_count"] == 0
    assert payload["missing_count"] == 10


def test_full_coverage_when_every_requirement_is_satisfied() -> None:
    asset = {
        "intent": {
            "parts": [
                "body",
                "lid",
                "corner_guard_a",
                "latch_plate",
                "handle_l",
                "foot_l",
                "trim_band",
                "rivet_a",
                "warning_decal",
                "edge_wear_mask",
            ]
        }
    }
    payload = evaluate_family_grammar(asset, _crate_runtime())

    assert payload["coverage"] == 1.0
    assert payload["satisfied_count"] == 10
    assert payload["partial_count"] == 0
    assert payload["missing_count"] == 0
    assert payload["recommendations"] == []


def test_industrial_crate_baseline_parts_list_yields_coverage_zero_point_four() -> None:
    """The actual baseline ``examples/industrial_crate.lth`` parts list
    matches 4 of the 10 grammar requirements (body_shell, latch_or_latch_plate,
    recessed_or_bracketed_handles, foot_rails_or_feet) so coverage = 0.40."""
    asset = {
        "intent": {
            "parts": [
                "body",
                "latch_plate",
                "handle_l",
                "handle_r",
                "foot_l",
                "foot_r",
            ]
        }
    }
    payload = evaluate_family_grammar(asset, _crate_runtime())

    assert payload["satisfied_count"] == 4
    assert payload["missing_count"] == 6
    assert payload["coverage"] == 0.4

    statuses = {item["name"]: item["status"] for item in payload["requirement_results"]}
    assert statuses["body_shell"] == "satisfied"
    assert statuses["latch_or_latch_plate"] == "satisfied"
    assert statuses["recessed_or_bracketed_handles"] == "satisfied"
    assert statuses["foot_rails_or_feet"] == "satisfied"
    assert statuses["lid_seam"] == "missing"
    assert statuses["corner_guards"] == "missing"
    assert statuses["trim_bands"] == "missing"
    assert statuses["fasteners"] == "missing"
    assert statuses["warning_or_decal_zones"] == "missing"
    assert statuses["edge_wear_masks"] == "missing"


def test_recommendations_length_equals_missing_plus_partial_count() -> None:
    asset = {"intent": {"parts": ["body", "latch_plate", "handle_l"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    assert len(payload["recommendations"]) == (
        payload["missing_count"] + payload["partial_count"]
    )
    assert payload["satisfied_count"] == 3
    assert payload["missing_count"] == 7


def test_evidence_includes_matched_parts_for_satisfied_requirements() -> None:
    asset = {"intent": {"parts": ["body", "handle_l", "handle_r"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    handle_entry = next(
        item
        for item in payload["requirement_results"]
        if item["name"] == "recessed_or_bracketed_handles"
    )
    assert handle_entry["status"] == "satisfied"
    assert handle_entry["evidence"]["matched_parts"] == ["handle_l", "handle_r"]

    lid_entry = next(
        item for item in payload["requirement_results"] if item["name"] == "lid_seam"
    )
    assert lid_entry["status"] == "missing"
    assert lid_entry["evidence"]["matched_parts"] == []


def test_unknown_family_falls_back_to_generic_grammar() -> None:
    runtime = _runtime_with_family("unrecognized_family")
    payload = evaluate_family_grammar({"intent": {"parts": ["body"]}}, runtime)

    assert payload["family"] == "generic"
    assert payload["coverage"] == 1.0
    assert payload["requirement_results"] == []
    assert payload["recommendations"] == []
    assert payload["satisfied_count"] == 0
    assert payload["missing_count"] == 0


def test_missing_design_brief_falls_back_to_generic_gracefully() -> None:
    payload = evaluate_family_grammar({"intent": {"parts": ["body"]}}, {})

    assert payload["family"] == "generic"
    assert payload["coverage"] == 1.0
    assert payload["requirement_results"] == []
    assert payload["recommendations"] == []


def test_missing_intent_does_not_crash() -> None:
    payload = evaluate_family_grammar({}, _crate_runtime())

    assert payload["family"] == "industrial_crate"
    assert payload["satisfied_count"] == 0
    assert payload["missing_count"] == 10
    assert payload["coverage"] == 0.0


def test_missing_parts_list_does_not_crash() -> None:
    payload = evaluate_family_grammar({"intent": {}}, _crate_runtime())

    assert payload["family"] == "industrial_crate"
    assert payload["satisfied_count"] == 0
    assert payload["missing_count"] == 10


def test_part_matching_is_case_insensitive() -> None:
    asset = {"intent": {"parts": ["BODY", "Latch_Plate", "HANDLE_L", "FOOT_L"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    statuses = {item["name"]: item["status"] for item in payload["requirement_results"]}
    assert statuses["body_shell"] == "satisfied"
    assert statuses["latch_or_latch_plate"] == "satisfied"
    assert statuses["recessed_or_bracketed_handles"] == "satisfied"
    assert statuses["foot_rails_or_feet"] == "satisfied"


def test_evaluation_is_deterministic_across_runs() -> None:
    asset = {
        "intent": {
            "parts": [
                "body",
                "latch_plate",
                "handle_l",
                "handle_r",
                "foot_l",
                "foot_r",
            ]
        }
    }
    runtime = _crate_runtime()

    first = evaluate_family_grammar(asset, runtime)
    second = evaluate_family_grammar(asset, runtime)

    assert first == second


def test_recommendations_skip_satisfied_requirements() -> None:
    """Recommendations must reference only missing/partial requirements;
    satisfied requirements never produce a recommendation entry."""
    asset = {"intent": {"parts": ["body", "lid", "corner", "latch", "handle"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    satisfied_names = {
        item["name"]
        for item in payload["requirement_results"]
        if item["status"] == "satisfied"
    }
    for recommendation in payload["recommendations"]:
        for satisfied in satisfied_names:
            assert satisfied not in recommendation, (
                f"Recommendation should not reference satisfied requirement {satisfied!r}: {recommendation!r}"
            )


def test_recommendations_pair_to_unsatisfied_requirements_by_index() -> None:
    """``recommendations[i]`` must be the ``recommendation_template`` of the
    i-th unsatisfied requirement in declaration order. Catches a refactor
    that swaps recommendation strings between requirements — substring
    coupling alone (the previous test) would not detect that.
    """
    from lathe.asset_quality.family_grammar import (
        _GRAMMARS,
    )

    asset = {"intent": {"parts": ["body", "handle"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    unsatisfied_requirement_names = [
        result["name"]
        for result in payload["requirement_results"]
        if result["status"] in {"missing", "partial"}
    ]

    name_to_template = {
        req.name: req.recommendation_template
        for req in _GRAMMARS["industrial_crate"].requirements
    }

    assert len(payload["recommendations"]) == len(unsatisfied_requirement_names)
    for index, requirement_name in enumerate(unsatisfied_requirement_names):
        expected_template = name_to_template[requirement_name]
        assert payload["recommendations"][index] == expected_template, (
            f"recommendations[{index}] should be the template of "
            f"{requirement_name!r}; got mismatch."
        )
