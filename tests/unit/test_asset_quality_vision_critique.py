"""Phase 10 tests for ``lathe.asset_quality.vision_critique``.

Covers the requirements in
``docs/asset-quality/improvement-tasklist.md`` Phase 10:

- The payload shape contract (top-level keys, ``version`` token).
- Frozen dataclass contract for ``PatchProposal``,
  ``CritiqueIssue``, ``CritiqueProvider``, ``SkippedReason``.
- Deterministic stub provider — six evidence-view -> issue
  mappings, and the no-evidence path.
- External provider mux — disabled by default, misconfigured,
  unknown, unavailable, and the build does not crash.
- Patch validation — invalid target, invalid operation,
  malformed field path, non-serialisable value, shape-contract
  guard, public-surface guard, approved valid patch.
- Determinism — issue_id stability, byte-equal output across
  runs, sort order.
- No asset mutation, summary correctness, pipeline runtime
  publication, redacted runtime config use.
"""

from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from lathe.asset_quality.vision_critique import (
    VISION_CRITIQUE_VERSION,
    CritiqueIssue,
    CritiqueProvider,
    PatchProposal,
    SkippedReason,
    evaluate_vision_critique,
)
from lathe.validators.composition import FunctionValidator, ValidatorPipeline

_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "asset_name",
        "provider",
        "provider_config",
        "issues",
        "patch_validation",
        "summary",
        "iteration_history",
        "before_after_metrics",
        "skipped_reasons",
        "warnings",
        "diagnostics",
    }
)


def _baseline_runtime() -> dict[str, Any]:
    """Runtime dict that does NOT trigger any stub-issue threshold."""
    return {
        "quality_diagnostics": {
            "metrics": {
                "debug_material_preview_penalty": 0.10,
                "highlow_fake_detail_penalty": 0.10,
                "random_triangulation_penalty": 0.10,
            }
        },
        "family_grammar": {
            "version": "family_grammar_v1",
            "family": "industrial_crate",
            "coverage": 0.95,
            "requirement_results": [],
        },
        "material_wear_graph": {
            "version": "material_wear_v1",
            "uniform_noise": {
                "is_uniform_noise": False,
                "uniform_noise_score": 0.10,
            },
        },
        "preview_evidence": {
            "version": "preview_evidence_v1",
            "preview_summary": {
                "final_beauty_present": True,
                "material_ids_present": True,
                "final_beauty_declared": True,
                "material_ids_declared": True,
                "distinct_final_from_material_ids": True,
                "comparison_sheet_present": False,
                "comparison_sheet_requested": False,
            },
        },
        "design_brief": {
            "version": "design_brief_v1",
            "brief": {
                "material_age": "used_not_destroyed",
                "wear": "medium_edge_wear",
                "detail_density": "hero",
                "shape_language": "rectangular_with_45deg_cuts",
                "negative_constraints": [],
            },
        },
    }


def _baseline_asset() -> dict[str, Any]:
    return {"name": "industrial_crate", "intent": {"parts": ["body"]}}


# ---------------------------------------------------------------------------
# Frozen dataclass contract
# ---------------------------------------------------------------------------


def test_patch_proposal_is_frozen() -> None:
    patch = PatchProposal(
        target="design_brief",
        field="design_brief.wear",
        operation="set",
        current_value="moderate",
        proposed_value="heavy",
        rationale="test",
    )
    with pytest.raises(FrozenInstanceError):
        patch.target = "family_grammar"  # type: ignore[misc]


def test_critique_issue_is_frozen() -> None:
    issue = CritiqueIssue(
        issue_id="abcd0001",
        severity="warning",
        evidence_view="quality_diagnostics",
        recommendation="x",
        patch_proposals=(),
    )
    with pytest.raises(FrozenInstanceError):
        issue.severity = "info"  # type: ignore[misc]


def test_critique_provider_is_frozen() -> None:
    provider = CritiqueProvider(
        name="deterministic_stub", version="v1", configured=False
    )
    with pytest.raises(FrozenInstanceError):
        provider.name = "other"  # type: ignore[misc]


def test_skipped_reason_is_frozen() -> None:
    record = SkippedReason(category="vision_provider", reason="not_configured")
    with pytest.raises(FrozenInstanceError):
        record.reason = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Top-level payload shape
# ---------------------------------------------------------------------------


def test_evaluate_vision_critique_returns_v1_payload() -> None:
    payload = evaluate_vision_critique(_baseline_asset(), _baseline_runtime())

    assert payload["version"] == VISION_CRITIQUE_VERSION
    assert payload["version"] == "vision_critique_v1"
    missing = _PAYLOAD_KEYS - payload.keys()
    extra = payload.keys() - _PAYLOAD_KEYS
    assert not missing, f"missing required keys: {sorted(missing)}"
    assert not extra, f"unexpected keys: {sorted(extra)}"
    assert payload["asset_name"] == "industrial_crate"
    assert isinstance(payload["provider"], dict)
    assert isinstance(payload["provider_config"], dict)
    assert isinstance(payload["issues"], list)
    assert isinstance(payload["patch_validation"], dict)
    assert isinstance(payload["summary"], dict)
    assert isinstance(payload["iteration_history"], list)
    assert isinstance(payload["before_after_metrics"], dict)
    assert isinstance(payload["skipped_reasons"], list)
    assert payload["warnings"] == []
    assert payload["diagnostics"] == []


# ---------------------------------------------------------------------------
# Deterministic stub provider behaviour
# ---------------------------------------------------------------------------


def test_deterministic_stub_runs_when_no_runtime_config() -> None:
    runtime = _baseline_runtime()
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    assert payload["provider"]["name"] == "deterministic_stub"
    assert payload["provider"]["version"] == "v1"
    assert payload["provider"]["configured"] is False
    assert any(
        record["reason"] == "vision_provider_not_configured"
        for record in payload["skipped_reasons"]
    )


def test_deterministic_stub_synthesizes_issues_from_quality_diagnostics() -> None:
    runtime = _baseline_runtime()
    runtime["quality_diagnostics"]["metrics"]["debug_material_preview_penalty"] = 0.85
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    matches = [
        issue
        for issue in payload["issues"]
        if issue["evidence_view"] == "quality_diagnostics"
        and "debug-material" in issue["recommendation"]
    ]
    assert matches, payload["issues"]
    issue = matches[0]
    assert issue["severity"] == "warning"
    assert any(
        patch["target"] == "design_brief" and "material_age" in patch["field"]
        for patch in issue["patch_proposals"]
    )


def test_deterministic_stub_synthesizes_issues_from_family_grammar() -> None:
    runtime = _baseline_runtime()
    runtime["family_grammar"]["coverage"] = 0.40
    runtime["family_grammar"]["requirement_results"] = [
        {"name": "lid_seam", "status": "missing"},
        {"name": "corner_guards", "status": "partial"},
    ]
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    matches = [
        issue
        for issue in payload["issues"]
        if issue["evidence_view"] == "family_grammar"
    ]
    assert matches
    issue = matches[0]
    patch_targets = {patch["target"] for patch in issue["patch_proposals"]}
    assert patch_targets == {"family_grammar"}
    proposed = [
        patch["proposed_value"]
        for patch in issue["patch_proposals"]
        if patch["field"] == "family_grammar.missing_requirements"
    ]
    assert proposed and "lid_seam" in proposed[0]


def test_deterministic_stub_synthesizes_issues_from_material_wear_graph() -> None:
    runtime = _baseline_runtime()
    runtime["material_wear_graph"]["uniform_noise"]["is_uniform_noise"] = True
    runtime["material_wear_graph"]["uniform_noise"]["uniform_noise_score"] = 0.95
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    matches = [
        issue
        for issue in payload["issues"]
        if issue["evidence_view"] == "material_wear_graph"
    ]
    assert matches
    issue = matches[0]
    assert any(
        patch["field"] == "design_brief.wear"
        for patch in issue["patch_proposals"]
    )


def test_deterministic_stub_synthesizes_issues_from_highlow_relation() -> None:
    runtime = _baseline_runtime()
    # The Phase 1 ``highlow_fake_detail_penalty`` is sourced from
    # Phase 7's realness score: realness_score < 0.5 -> penalty > 0.5.
    runtime["quality_diagnostics"]["metrics"]["highlow_fake_detail_penalty"] = 0.85
    runtime["highlow_relation"] = {
        "version": "highlow_relation_v1",
        "is_real_highlow": False,
        "realness_score": 0.20,
        "required": True,
    }
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    matches = [
        issue
        for issue in payload["issues"]
        if issue["evidence_view"] == "highlow_relation"
    ]
    assert matches
    issue = matches[0]
    assert any(
        patch["field"] == "design_brief.detail_density"
        for patch in issue["patch_proposals"]
    )


def test_deterministic_stub_synthesizes_issues_from_preview_evidence() -> None:
    runtime = _baseline_runtime()
    runtime["preview_evidence"]["preview_summary"][
        "distinct_final_from_material_ids"
    ] = False
    runtime["preview_evidence"]["preview_summary"]["final_beauty_present"] = False
    runtime["preview_evidence"]["preview_summary"]["material_ids_present"] = True
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    matches = [
        issue
        for issue in payload["issues"]
        if issue["evidence_view"] == "preview_evidence"
    ]
    assert matches
    issue = matches[0]
    assert any(
        patch["field"] == "design_brief.negative_constraints"
        and patch["proposed_value"] == "missing_final_beauty_preview"
        for patch in issue["patch_proposals"]
    )


# ---------------------------------------------------------------------------
# External vision provider mux
# ---------------------------------------------------------------------------


def test_external_provider_disabled_by_default() -> None:
    runtime = _baseline_runtime()
    runtime["_runtime_config"] = {}
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    assert payload["provider"]["name"] == "deterministic_stub"
    assert payload["provider"]["configured"] is False
    skipped_tokens = {record["reason"] for record in payload["skipped_reasons"]}
    assert "vision_provider_not_configured" in skipped_tokens


def test_external_provider_enabled_but_unconfigured_emits_skipped_reason() -> None:
    runtime = _baseline_runtime()
    runtime["_runtime_config"] = {"vision_critique": {"enabled": True}}
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    skipped_tokens = {record["reason"] for record in payload["skipped_reasons"]}
    assert "vision_provider_misconfigured" in skipped_tokens
    assert payload["provider"]["name"] == "deterministic_stub"
    assert payload["provider"]["configured"] is False


def test_external_provider_unknown_emits_skipped_reason() -> None:
    runtime = _baseline_runtime()
    runtime["_runtime_config"] = {
        "vision_critique": {
            "enabled": True,
            "provider": "no_such_provider_xyz",
        }
    }
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    skipped_tokens = {record["reason"] for record in payload["skipped_reasons"]}
    assert "vision_provider_unknown" in skipped_tokens
    assert payload["provider"]["name"] == "deterministic_stub"


def test_external_provider_unavailable_emits_skipped_reason() -> None:
    runtime = _baseline_runtime()
    runtime["_runtime_config"] = {
        "vision_critique": {
            "enabled": True,
            "provider": "mock_http_vision_provider",
            "endpoint": "https://example.invalid",
        }
    }
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    skipped_tokens = {record["reason"] for record in payload["skipped_reasons"]}
    assert "vision_provider_unavailable" in skipped_tokens
    assert payload["provider"]["name"] == "deterministic_stub"
    assert payload["provider"]["configured"] is False


def test_external_provider_skipped_does_not_crash_build() -> None:
    runtime = _baseline_runtime()
    runtime["_runtime_config"] = {
        "vision_critique": {
            "enabled": True,
            "provider": "mock_http_vision_provider",
        }
    }
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    missing = _PAYLOAD_KEYS - payload.keys()
    assert not missing, sorted(missing)
    assert isinstance(payload["issues"], list)
    assert isinstance(payload["patch_validation"], dict)
    assert isinstance(payload["summary"], dict)


def test_external_provider_invalid_output_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from lathe.asset_quality import vision_critique

    class BadVisionProvider(vision_critique._ExternalVisionProvider):
        name = "bad_vision_provider"
        version = "v0"

        def critique(
            self, asset: dict[str, Any], runtime: dict[str, Any]
        ) -> tuple[CritiqueIssue, ...]:
            return ("not-a-critique-issue",)  # type: ignore[return-value]

    monkeypatch.setitem(
        vision_critique._PROVIDER_REGISTRY,
        "bad_vision_provider",
        BadVisionProvider,
    )
    runtime = _baseline_runtime()
    runtime["_runtime_config"] = {
        "vision_critique": {
            "enabled": True,
            "provider": "bad_vision_provider",
        }
    }

    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    skipped_tokens = {record["reason"] for record in payload["skipped_reasons"]}
    assert "vision_provider_invalid_output" in skipped_tokens
    assert payload["provider"]["name"] == "deterministic_stub"


# ---------------------------------------------------------------------------
# Patch validation
# ---------------------------------------------------------------------------


def _payload_with_synthetic_issue(issue: CritiqueIssue) -> dict[str, Any]:
    """Run the validator with a runtime that yields the supplied synthetic issue.

    The deterministic stub does not expose a public injection point —
    patch validation is exercised by directly invoking the
    ``_validate_patches`` private API through the public
    :func:`evaluate_vision_critique` flow.
    """
    # Use the private function for direct test access; this is
    # acceptable inside the test module because patch validation is
    # itself a public-API behaviour and the inner helper is the
    # canonical surface to test rejections in isolation.
    from lathe.asset_quality.vision_critique import _validate_patches

    return _validate_patches((issue,))


def test_patch_validation_rejects_shape_contract_changes() -> None:
    issue = CritiqueIssue(
        issue_id="0001",
        severity="warning",
        evidence_view="quality_diagnostics",
        recommendation="r",
        patch_proposals=(
            PatchProposal(
                target="design_brief",
                field="design_brief.lathe.shape.intent_mesh_handoff_v1",
                operation="set",
                current_value=None,
                proposed_value="x",
                rationale="r",
            ),
        ),
    )
    bundle = _payload_with_synthetic_issue(issue)
    assert bundle["all_patches_valid"] is False
    assert any(
        rejection["reason"] == "touches_shape_contract"
        for rejection in bundle["rejections"]
    )


def test_patch_validation_rejects_public_surface_changes() -> None:
    issue = CritiqueIssue(
        issue_id="0002",
        severity="warning",
        evidence_view="quality_diagnostics",
        recommendation="r",
        patch_proposals=(
            PatchProposal(
                target="design_brief",
                field="design_brief.asset.uses",
                operation="set",
                current_value=None,
                proposed_value="x",
                rationale="r",
            ),
        ),
    )
    bundle = _payload_with_synthetic_issue(issue)
    assert bundle["all_patches_valid"] is False
    assert any(
        rejection["reason"] == "touches_public_surface"
        for rejection in bundle["rejections"]
    )


def test_patch_validation_rejects_invalid_target() -> None:
    issue = CritiqueIssue(
        issue_id="0003",
        severity="warning",
        evidence_view="quality_diagnostics",
        recommendation="r",
        patch_proposals=(
            PatchProposal(
                target="raw_mesh",
                field="raw_mesh.vertices",
                operation="set",
                current_value=None,
                proposed_value=[],
                rationale="r",
            ),
        ),
    )
    bundle = _payload_with_synthetic_issue(issue)
    assert bundle["all_patches_valid"] is False
    assert any(
        rejection["reason"] == "invalid_target"
        for rejection in bundle["rejections"]
    )


def test_patch_validation_rejects_invalid_operation() -> None:
    issue = CritiqueIssue(
        issue_id="0004",
        severity="warning",
        evidence_view="quality_diagnostics",
        recommendation="r",
        patch_proposals=(
            PatchProposal(
                target="design_brief",
                field="design_brief.wear",
                operation="explode",
                current_value=None,
                proposed_value="x",
                rationale="r",
            ),
        ),
    )
    bundle = _payload_with_synthetic_issue(issue)
    assert bundle["all_patches_valid"] is False
    assert any(
        rejection["reason"] == "invalid_operation"
        for rejection in bundle["rejections"]
    )


def test_patch_validation_rejects_non_serializable_value() -> None:
    issue = CritiqueIssue(
        issue_id="0005",
        severity="warning",
        evidence_view="quality_diagnostics",
        recommendation="r",
        patch_proposals=(
            PatchProposal(
                target="design_brief",
                field="design_brief.wear",
                operation="set",
                current_value=None,
                proposed_value=lambda: None,
                rationale="r",
            ),
        ),
    )
    bundle = _payload_with_synthetic_issue(issue)
    assert bundle["all_patches_valid"] is False
    assert any(
        rejection["reason"] == "non_serializable_value"
        for rejection in bundle["rejections"]
    )


def test_patch_validation_approves_valid_design_brief_patch() -> None:
    issue = CritiqueIssue(
        issue_id="0006",
        severity="warning",
        evidence_view="quality_diagnostics",
        recommendation="r",
        patch_proposals=(
            PatchProposal(
                target="design_brief",
                field="design_brief.wear",
                operation="set",
                current_value="medium",
                proposed_value="heavy",
                rationale="r",
            ),
        ),
    )
    bundle = _payload_with_synthetic_issue(issue)
    assert bundle["all_patches_valid"] is True
    assert bundle["approved_count"] == 1
    assert bundle["rejected_count"] == 0
    assert bundle["rejections"] == []


# ---------------------------------------------------------------------------
# No mutation, determinism, sort order
# ---------------------------------------------------------------------------


def test_critique_does_not_mutate_asset() -> None:
    asset = _baseline_asset()
    runtime = _baseline_runtime()
    asset_before = copy.deepcopy(asset)
    runtime_before = copy.deepcopy(runtime)
    runtime_before.pop("_runtime_config", None)

    evaluate_vision_critique(asset, runtime)

    assert asset == asset_before
    runtime_after = copy.deepcopy(runtime)
    runtime_after.pop("_runtime_config", None)
    assert runtime_after == runtime_before


def test_evidence_is_deterministic() -> None:
    asset = _baseline_asset()
    runtime = _baseline_runtime()
    runtime["quality_diagnostics"]["metrics"]["debug_material_preview_penalty"] = 0.80
    runtime["family_grammar"]["coverage"] = 0.30

    first = evaluate_vision_critique(asset, runtime)
    second = evaluate_vision_critique(asset, copy.deepcopy(runtime))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_issue_id_is_stable_across_runs() -> None:
    runtime = _baseline_runtime()
    runtime["quality_diagnostics"]["metrics"]["debug_material_preview_penalty"] = 0.80
    payload = evaluate_vision_critique(_baseline_asset(), runtime)
    expected_ids = [issue["issue_id"] for issue in payload["issues"]]

    payload_again = evaluate_vision_critique(_baseline_asset(), runtime)
    assert [issue["issue_id"] for issue in payload_again["issues"]] == expected_ids
    for issue in payload["issues"]:
        assert isinstance(issue["issue_id"], str)
        assert len(issue["issue_id"]) == 16


def test_issues_sorted_by_severity_then_id() -> None:
    runtime = _baseline_runtime()
    # Trigger four issues so we have multiple warnings to sort.
    runtime["quality_diagnostics"]["metrics"]["debug_material_preview_penalty"] = 0.80
    runtime["quality_diagnostics"]["metrics"]["highlow_fake_detail_penalty"] = 0.80
    runtime["quality_diagnostics"]["metrics"]["random_triangulation_penalty"] = 0.80
    runtime["family_grammar"]["coverage"] = 0.30
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    severity_rank = {"error": 0, "warning": 1, "info": 2}
    keys = [
        (severity_rank.get(issue["severity"], 999), issue["issue_id"])
        for issue in payload["issues"]
    ]
    assert keys == sorted(keys)


def test_summary_counts_match_issues() -> None:
    runtime = _baseline_runtime()
    runtime["quality_diagnostics"]["metrics"]["debug_material_preview_penalty"] = 0.80
    runtime["family_grammar"]["coverage"] = 0.30
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    summary = payload["summary"]
    assert summary["issue_count"] == len(payload["issues"])
    severity_total = sum(summary["issues_by_severity"].values())
    assert severity_total == summary["issue_count"]
    expected_patch_count = sum(
        len(issue["patch_proposals"]) for issue in payload["issues"]
    )
    assert summary["patch_count"] == expected_patch_count
    assert summary["approved_patches"] == payload["patch_validation"]["approved_count"]


def test_phase_10_loop_evidence_blocks_are_truthful() -> None:
    runtime = _baseline_runtime()
    runtime["_runtime_config"] = {
        "vision_critique": {
            "enabled": True,
            "provider": "mock_http_vision_provider",
            "api_key": "[REDACTED]",
            "endpoint": "[REDACTED]",
            "model": "vision-v0",
        }
    }
    runtime["preview_evidence"]["preview_summary"]["comparison_sheet_requested"] = True
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    assert payload["provider_config"] == {
        "enabled": True,
        "requested_provider": "mock_http_vision_provider",
        "resolved_provider": "deterministic_stub",
        "external_provider_configured": False,
        # Wave 5 / M10: ``_safe_config_keys`` now matches credential tokens
        # against whole segments (split on _, -, .), so legitimate keys like
        # ``endpoint`` are no longer dropped. Only ``api_key`` is filtered
        # here because ``key`` is a credential segment.
        "safe_config_keys": ["enabled", "endpoint", "model", "provider"],
        "sensitive_values_redacted": True,
    }
    assert payload["before_after_metrics"]["available"] is False
    assert (
        payload["before_after_metrics"]["skipped_reason"]
        == "comparison_sheet_renderer_unavailable"
    )
    assert payload["iteration_history"][0]["applied"] is False
    assert payload["iteration_history"][0]["status"] == "evidence_recorded"


def test_no_phase_1_through_9_evidence_emits_skipped_provider_only() -> None:
    payload = evaluate_vision_critique({}, {})

    assert payload["issues"] == []
    skipped_tokens = {record["reason"] for record in payload["skipped_reasons"]}
    assert "vision_provider_not_configured" in skipped_tokens
    assert payload["patch_validation"]["all_patches_valid"] is True


def test_validator_pipeline_publishes_vision_critique_to_runtime() -> None:
    pipeline = ValidatorPipeline(
        [
            FunctionValidator(
                name="vision_critique",
                fn=evaluate_vision_critique,
                stage_dependencies=[],
                weight=0.0,
            )
        ]
    )
    asset = _baseline_asset()
    runtime: dict[str, Any] = _baseline_runtime()
    pipeline.run(runtime, asset, artifacts={})

    published = runtime.get("vision_critique")
    assert isinstance(published, dict)
    assert published.get("version") == VISION_CRITIQUE_VERSION
    assert "issues" in published
    assert "provider" in published


def test_redacted_runtime_config_is_used_when_present() -> None:
    runtime = _baseline_runtime()
    runtime["_runtime_config"] = {
        "vision_critique": {
            "enabled": True,
            "provider": "mock_http_vision_provider",
            "api_key": "[REDACTED]",
            "endpoint": "[REDACTED]",
        }
    }
    payload = evaluate_vision_critique(_baseline_asset(), runtime)

    payload_text = json.dumps(payload)
    # The redacted runtime config never lands in the report directly;
    # the only provider id surfaced in the payload is the resolved
    # name (here ``deterministic_stub`` after the unavailable
    # fallback). After Wave 5 / M10, ``endpoint`` is no longer treated as
    # a secret token (it's a *key* shape, not a credential). The value
    # ``[REDACTED]`` is what callers should put in the config when they
    # don't want raw endpoint URLs serialized. Verify that the
    # credential-token key (``api_key``) does not appear and that the
    # ``[REDACTED]`` placeholder value never lands in the payload.
    assert "api_key" not in payload_text
    assert "[REDACTED]" not in payload_text
    assert payload["provider"]["name"] == "deterministic_stub"


def test_validate_pipeline_orders_vision_after_current_diagnostics() -> None:
    from lathe.core.stages.validate import _PIPELINE

    names = [validator.name for validator in _PIPELINE.validators]

    assert names.index("quality_diagnostics") < names.index("vision_critique")
    assert names.index("preview_evidence") < names.index("vision_critique")
