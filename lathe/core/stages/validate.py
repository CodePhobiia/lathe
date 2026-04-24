"""Validate stage step body.

Runs the five validators (semantic, visual, flow, plus runtime rule
evaluation), computes the critic score, and decides certification.
Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ...validators.flow_quality import evaluate_flow_quality
from ...validators.semantic_quality import evaluate_semantic_quality
from ...validators.visual_quality import evaluate_visual_quality
from ..common import dump_json
from ..evaluators import evaluate_critic, evaluate_metric, evaluate_rule


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
    semantic_report = evaluate_semantic_quality(executor.asset, executor.runtime)
    executor.runtime["semantic_quality"] = semantic_report
    diagnostics.extend(semantic_report["diagnostics"])
    visual_report = evaluate_visual_quality(executor.asset, executor.runtime)
    executor.runtime["visual_quality"] = visual_report
    diagnostics.extend(visual_report["diagnostics"])
    flow_report = evaluate_flow_quality(executor.asset, executor.runtime)
    executor.runtime["flow_quality"] = flow_report
    diagnostics.extend(flow_report["diagnostics"])
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
        "semantic_quality": semantic_report,
        "visual_quality": visual_report,
        "flow_quality": flow_report,
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
