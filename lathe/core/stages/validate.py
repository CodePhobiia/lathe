"""Validate stage step body.

Runs the validator pipeline (semantic, visual, flow) plus runtime
rule evaluation, computes the critic score, and decides certification.
Extracted from ``lathe/executor.py`` during Stage 2.IV; formalised into
a :class:`ValidatorPipeline` during Plan 03 Phase 5.
"""

from __future__ import annotations

from typing import Any

from ...validators.composition import FunctionValidator, ValidatorPipeline
from ...validators.flow_quality import evaluate_flow_quality
from ...validators.geometry_integrity import evaluate_geometry_integrity
from ...validators.semantic_quality import evaluate_semantic_quality
from ...validators.visual_quality import evaluate_visual_quality
from ..common import dump_json
from ..evaluators import evaluate_critic, evaluate_metric, evaluate_rule


_PIPELINE = ValidatorPipeline(
    [
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
            name="geometry_integrity",
            fn=evaluate_geometry_integrity,
            stage_dependencies=["topology"],
        ),
    ]
)


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
    semantic_report = semantic_entry["evidence"]
    visual_report = visual_entry["evidence"]
    flow_report = flow_entry["evidence"]
    integrity_report = integrity_entry["evidence"]
    executor.runtime["semantic_quality"] = semantic_report
    executor.runtime["visual_quality"] = visual_report
    executor.runtime["flow_quality"] = flow_report
    executor.runtime["geometry_integrity"] = integrity_report
    diagnostics.extend(semantic_entry["diagnostics"])
    diagnostics.extend(visual_entry["diagnostics"])
    diagnostics.extend(flow_entry["diagnostics"])
    diagnostics.extend(integrity_entry["diagnostics"])
    diagnostics.extend(executor.runtime.get("execution", {}).get("bundle", {}).get("diagnostics", []))
    rule_results = []
    for rule in executor.asset["validate"].get("rules", []):
        if rule.get("kind") == "ensure":
            passed, detail = evaluate_rule(rule["expr"], executor.asset, executor.runtime)
            rule_results.append({"kind": "ensure", "expr": rule["expr"], "passed": passed, "detail": detail})
            if not passed:
                diagnostics.append({
                    "code": "L6100",
                    "name": "ensure_failed",
                    "severity": "error",
                    "phase": "validate",
                    "asset": executor.asset_name,
                    "stage": detail.get("stage"),
                    "path": detail.get("path"),
                    "message": detail.get("message", f"Validation rule failed: {rule['expr']}"),
                    "details": detail,
                    "suggested_repairs": detail.get("suggested_repairs", []),
                })
        else:
            score = evaluate_metric(rule["expr"], executor.asset, executor.runtime)
            rule_results.append({"kind": "prefer", "expr": rule["expr"], "score": score, "weight": rule.get("weight", 1.0)})

    threshold = float(executor.asset["validate"].get("threshold", 0.80))
    score = evaluate_critic(
        executor.asset["validate"].get("score"),
        executor.asset,
        executor.runtime,
        executor.critics,
        executor.asset["validate"].get("rules", []),
    )
    certified = not any(item.get("severity") == "error" for item in diagnostics) and score >= threshold
    report = {
        "certified": certified,
        "threshold": threshold,
        "score": round(score, 6),
        "semantic_quality": {**semantic_report, "diagnostics": semantic_entry["diagnostics"]},
        "visual_quality": {**visual_report, "diagnostics": visual_entry["diagnostics"]},
        "flow_quality": {**flow_report, "diagnostics": flow_entry["diagnostics"]},
        "geometry_integrity": {**integrity_report, "diagnostics": integrity_entry["diagnostics"]},
        "rule_results": rule_results,
        "diagnostics": diagnostics,
        "repair_policy": executor.asset["validate"].get("repair", {}),
        "repair_suggestions": sorted({repair for diag in diagnostics for repair in diag.get("suggested_repairs", [])}),
        "semantic_repairs_applied": next(
            (
                candidate.get("repairs_applied", [])
                for candidate in executor.runtime["shape"]["bundle"].get("candidates", [])
                if candidate.get("candidate_id") == executor.runtime["shape"]["bundle"].get("selected_candidate_id")
            ),
            [],
        ),
        "reselection_attempts": list(executor.runtime.get("shape", {}).get("reselection_attempts", [])),
    }
    executor.runtime["validate"] = {"bundle": report}
    dump_json(stage_dir / "report.json", report)
    return report
