"""Validate stage step body.

Runs the validator pipeline (semantic, visual, flow) plus runtime
rule evaluation, computes the critic score, and decides certification.
Extracted from ``lathe/executor.py`` during Stage 2.IV; formalised into
a :class:`ValidatorPipeline` during Plan 03 Phase 5.
"""

from __future__ import annotations

from typing import Any

from ...asset_quality.construction_graph import evaluate_construction_graph
from ...asset_quality.design_brief import evaluate_design_brief
from ...asset_quality.diagnostics import evaluate_quality_diagnostics
from ...asset_quality.family_grammar import evaluate_family_grammar
from ...asset_quality.grammar_lowering import evaluate_grammar_lowering
from ...asset_quality.highlow_relation import evaluate_highlow_relation
from ...validators.composition import (
    FunctionValidator,
    ValidatorPipeline,
    build_gameplay_tag_validator,
    build_urdf_validator,
)
from ...validators.flow_quality import evaluate_flow_quality
from ...validators.geometry_integrity import evaluate_geometry_integrity
from ...validators.semantic_quality import evaluate_semantic_quality
from ...validators.visual_quality import evaluate_visual_quality
from ..common import dump_json
from ..evaluators import evaluate_critic, evaluate_metric, evaluate_rule

_PIPELINE = ValidatorPipeline(
    [
        FunctionValidator(
            name="design_brief",
            fn=evaluate_design_brief,
            stage_dependencies=[],
            weight=0.0,
        ),
        FunctionValidator(
            name="construction_graph",
            fn=evaluate_construction_graph,
            stage_dependencies=[],
            weight=0.0,
        ),
        FunctionValidator(
            name="family_grammar",
            fn=evaluate_family_grammar,
            stage_dependencies=[],
            weight=0.0,
        ),
        FunctionValidator(
            name="grammar_lowering",
            fn=evaluate_grammar_lowering,
            stage_dependencies=[],
            weight=0.0,
        ),
        FunctionValidator(
            name="semantic_quality",
            fn=evaluate_semantic_quality,
            stage_dependencies=["shape", "topology"],
        ),
        FunctionValidator(
            name="visual_quality",
            fn=evaluate_visual_quality,
            stage_dependencies=["shape", "topology", "uv", "surface"],
        ),
        FunctionValidator(
            name="flow_quality",
            fn=evaluate_flow_quality,
            stage_dependencies=["shape", "topology", "uv", "surface"],
        ),
        FunctionValidator(
            name="highlow_relation",
            fn=evaluate_highlow_relation,
            stage_dependencies=["topology", "surface"],
            weight=0.0,
        ),
        FunctionValidator(
            name="geometry_integrity",
            fn=evaluate_geometry_integrity,
            stage_dependencies=["topology"],
        ),
        FunctionValidator(
            name="quality_diagnostics",
            fn=evaluate_quality_diagnostics,
            stage_dependencies=["shape", "topology", "uv", "surface"],
            weight=0.0,
        ),
        build_urdf_validator(),
        build_gameplay_tag_validator(),
    ]
)


def _diagnostic_next_step(diag: dict[str, Any]) -> str:
    repairs = [str(item) for item in diag.get("suggested_repairs", []) if item]
    if repairs:
        return f"Apply or inspect suggested repair `{repairs[0]}`."
    path = diag.get("path")
    if path:
        return f"Inspect `{path}` and rerun `lathe check` before rebuilding."
    stage = diag.get("stage") or diag.get("phase") or "validate"
    return f"Inspect the `{stage}` report section for the failing metric and rerun the build."


def _failure_summary(
    *,
    certified: bool,
    score: float,
    threshold: float,
    diagnostics: list[dict[str, Any]],
    repair_suggestions: list[str],
) -> dict[str, Any]:
    errors = [item for item in diagnostics if item.get("severity") == "error"]
    blocking = []
    for diag in errors[:5]:
        blocking.append(
            {
                "code": diag.get("code"),
                "name": diag.get("name"),
                "stage": diag.get("stage") or diag.get("phase"),
                "path": diag.get("path"),
                "message": diag.get("message"),
                "suggested_repairs": list(diag.get("suggested_repairs", [])),
                "next_step": _diagnostic_next_step(diag),
            }
        )

    score_deficit = max(0.0, threshold - score)
    next_steps: list[str] = []
    if score_deficit > 0:
        next_steps.append(f"Raise validation score by at least {score_deficit:.3f} to meet threshold.")
    for repair in repair_suggestions[:5]:
        next_steps.append(f"Run or apply repair `{repair}`.")
    if errors and not next_steps:
        next_steps.append(_diagnostic_next_step(errors[0]))

    return {
        "status": "passed" if certified else "failed",
        "score": round(score, 6),
        "threshold": threshold,
        "score_deficit": round(score_deficit, 6),
        "error_count": len(errors),
        "blocking_diagnostics": blocking,
        "next_steps": next_steps,
    }


def run(executor: Any, optimize_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        optimize_bundle: optimize_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["validate"]
    diagnostics: list[dict[str, Any]] = []

    cert_bundle = _PIPELINE.run(executor.runtime, executor.asset, artifacts={})
    semantic_entry = cert_bundle["validators"]["semantic_quality"]
    visual_entry = cert_bundle["validators"]["visual_quality"]
    flow_entry = cert_bundle["validators"]["flow_quality"]
    integrity_entry = cert_bundle["validators"]["geometry_integrity"]
    urdf_entry = cert_bundle["validators"].get(
        "urdf_validation",
        {
            "evidence": {},
            "diagnostics": [],
            "passes": True,
            "score": 1.0,
        },
    )
    gameplay_tag_entry = cert_bundle["validators"].get(
        "gameplay_tags",
        {
            "evidence": {},
            "diagnostics": [],
            "passes": True,
            "score": 1.0,
        },
    )
    quality_diagnostics_entry = cert_bundle["validators"].get(
        "quality_diagnostics",
        {
            "evidence": {
                "version": "asset_quality_diagnostics_v1",
                "metrics": {},
                "warnings": [],
                "recommendations": [],
                "findings": [],
            },
            "diagnostics": [],
            "passes": True,
            "score": 1.0,
        },
    )
    design_brief_entry = cert_bundle["validators"].get(
        "design_brief",
        {
            "evidence": {
                "version": "design_brief_v1",
                "brief": {},
                "family_inference": {
                    "matched_family": "generic",
                    "match_signal": "default",
                    "match_token": "",
                },
            },
            "diagnostics": [],
            "passes": True,
            "score": 1.0,
        },
    )
    family_grammar_entry = cert_bundle["validators"].get(
        "family_grammar",
        {
            "evidence": {
                "version": "family_grammar_v1",
                "family": "generic",
                "coverage": 1.0,
                "satisfied_count": 0,
                "partial_count": 0,
                "missing_count": 0,
                "requirement_results": [],
                "recommendations": [],
            },
            "diagnostics": [],
            "passes": True,
            "score": 1.0,
        },
    )
    construction_graph_entry = cert_bundle["validators"].get(
        "construction_graph",
        {
            "evidence": {
                "version": "construction_graph_v1",
                "family": "generic",
                "asset_name": "unnamed_asset",
                "nodes": [],
                "edges": [],
                "node_count": 0,
                "edge_count": 0,
                "node_types_present": [],
                "edge_types_present": [],
            },
            "diagnostics": [],
            "passes": True,
            "score": 1.0,
        },
    )
    grammar_lowering_entry = cert_bundle["validators"].get(
        "grammar_lowering",
        {
            "evidence": {
                "version": "grammar_lowering_v1",
                "family": "generic",
                "shape_program": {
                    "version": "shape_ir_v2",
                    "asset_name": "unnamed_asset",
                    "family": "generic",
                    "ops": [],
                },
                "shape_program_summary": {
                    "op_count": 0,
                    "ops_by_family": {
                        "solid_ops": 0,
                        "boolean_ops": 0,
                        "edge_ops": 0,
                        "repetition_ops": 0,
                        "integration_ops": 0,
                        "wear_ops": 0,
                    },
                    "ops_by_requirement": {},
                },
                "synthesized_graph_nodes": [],
                "synthesized_node_count": 0,
                "v1_lowering": {
                    "v1_record_count": 0,
                    "diagnostics": [],
                    "unsupported_ops": [],
                },
            },
            "diagnostics": [],
            "passes": True,
            "score": 1.0,
        },
    )
    highlow_relation_entry = cert_bundle["validators"].get(
        "highlow_relation",
        {
            "evidence": {
                "version": "highlow_relation_v1",
                "is_real_highlow": False,
                "realness_score": 0.0,
                "high_mesh_uri": None,
                "low_mesh_uri": None,
                "runtime_low_uri": None,
                "high_triangle_count": None,
                "low_triangle_count": None,
                "triangle_delta_ratio": 0.0,
                "distinct_uris": False,
                "distinct_triangle_counts": False,
                "bake_maps": [],
                "bake_map_count_present": 0,
                "bake_map_count_expected": 4,
                "skipped_reasons": [],
                "warnings": [],
                "diagnostics": [],
            },
            "diagnostics": [],
            "passes": True,
            "score": 1.0,
        },
    )
    semantic_report = semantic_entry["evidence"]
    visual_report = visual_entry["evidence"]
    flow_report = flow_entry["evidence"]
    integrity_report = integrity_entry["evidence"]
    urdf_report = urdf_entry.get("evidence", {})
    quality_diagnostics_report = quality_diagnostics_entry.get("evidence", {})
    design_brief_report = design_brief_entry.get("evidence", {})
    family_grammar_report = family_grammar_entry.get("evidence", {})
    construction_graph_report = construction_graph_entry.get("evidence", {})
    grammar_lowering_report = grammar_lowering_entry.get("evidence", {})
    highlow_relation_report = highlow_relation_entry.get("evidence", {})
    executor.runtime["semantic_quality"] = semantic_report
    executor.runtime["visual_quality"] = visual_report
    executor.runtime["flow_quality"] = flow_report
    executor.runtime["geometry_integrity"] = integrity_report
    executor.runtime["urdf_validation"] = urdf_report
    executor.runtime["quality_diagnostics"] = quality_diagnostics_report
    executor.runtime["design_brief"] = design_brief_report
    executor.runtime["construction_graph"] = construction_graph_report
    executor.runtime["family_grammar"] = family_grammar_report
    executor.runtime["grammar_lowering"] = grammar_lowering_report
    executor.runtime["highlow_relation"] = highlow_relation_report
    diagnostics.extend(semantic_entry["diagnostics"])
    diagnostics.extend(visual_entry["diagnostics"])
    diagnostics.extend(flow_entry["diagnostics"])
    diagnostics.extend(integrity_entry["diagnostics"])
    diagnostics.extend(urdf_entry.get("diagnostics", []))
    diagnostics.extend(gameplay_tag_entry.get("diagnostics", []))
    diagnostics.extend(highlow_relation_entry.get("diagnostics", []))
    diagnostics.extend(executor.runtime.get("execution", {}).get("bundle", {}).get("diagnostics", []))
    rule_results = []
    for rule in executor.asset["validate"].get("rules", []):
        if rule.get("kind") == "ensure":
            passed, detail = evaluate_rule(rule["expr"], executor.asset, executor.runtime)
            rule_results.append({"kind": "ensure", "expr": rule["expr"], "passed": passed, "detail": detail})
            if not passed:
                diagnostics.append(
                    {
                        "code": "L6100",
                        "name": "ensure_failed",
                        "severity": "error",
                        "phase": "validate",
                        "asset": executor.asset_name,
                        "stage": detail.get("stage"),
                        "path": detail.get("path"),
                        "message": detail.get(
                            "message",
                            f"Validation rule failed: {rule['expr']}",
                        ),
                        "details": detail,
                        "suggested_repairs": detail.get("suggested_repairs", []),
                    }
                )
        else:
            score = evaluate_metric(rule["expr"], executor.asset, executor.runtime)
            rule_results.append(
                {
                    "kind": "prefer",
                    "expr": rule["expr"],
                    "score": score,
                    "weight": rule.get("weight", 1.0),
                }
            )

    threshold = float(executor.asset["validate"].get("threshold", 0.80))
    score = evaluate_critic(
        executor.asset["validate"].get("score"),
        executor.asset,
        executor.runtime,
        executor.critics,
        executor.asset["validate"].get("rules", []),
    )
    certified = not any(item.get("severity") == "error" for item in diagnostics) and score >= threshold
    repair_suggestions = sorted(
        {repair for diag in diagnostics for repair in diag.get("suggested_repairs", [])}
    )
    report = {
        "certified": certified,
        "threshold": threshold,
        "score": round(score, 6),
        "semantic_quality": {**semantic_report, "diagnostics": semantic_entry["diagnostics"]},
        "visual_quality": {**visual_report, "diagnostics": visual_entry["diagnostics"]},
        "flow_quality": {**flow_report, "diagnostics": flow_entry["diagnostics"]},
        "geometry_integrity": {**integrity_report, "diagnostics": integrity_entry["diagnostics"]},
        "urdf_validation": {**urdf_report, "diagnostics": urdf_entry.get("diagnostics", [])},
        "quality_diagnostics": quality_diagnostics_report,
        "design_brief": design_brief_report,
        "construction_graph": construction_graph_report,
        "family_grammar": family_grammar_report,
        "grammar_lowering": grammar_lowering_report,
        "highlow_relation": highlow_relation_report,
        "rule_results": rule_results,
        "diagnostics": diagnostics,
        "repair_policy": executor.asset["validate"].get("repair", {}),
        "repair_suggestions": repair_suggestions,
        "failure_summary": _failure_summary(
            certified=certified,
            score=score,
            threshold=threshold,
            diagnostics=diagnostics,
            repair_suggestions=repair_suggestions,
        ),
        "semantic_repairs_applied": next(
            (
                candidate.get("repairs_applied", [])
                for candidate in executor.runtime.get("shape", {}).get("bundle", {}).get("candidates", [])
                if candidate.get("candidate_id")
                == executor.runtime.get("shape", {}).get("bundle", {}).get("selected_candidate_id")
            ),
            [],
        ),
        "reselection_attempts": list(executor.runtime.get("shape", {}).get("reselection_attempts", [])),
    }
    executor.runtime["validate"] = {"bundle": report}
    dump_json(stage_dir / "report.json", report)
    return report
