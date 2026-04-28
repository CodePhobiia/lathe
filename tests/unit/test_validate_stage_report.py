from __future__ import annotations

import json
from types import SimpleNamespace

from lathe.core.stages.validate import _failure_summary
from lathe.core.stages.validate import run as run_validate_stage


def test_failure_summary_makes_certification_failures_actionable() -> None:
    summary = _failure_summary(
        certified=False,
        score=0.61,
        threshold=0.8,
        diagnostics=[
            {
                "code": "L6100",
                "name": "ensure_failed",
                "severity": "error",
                "stage": "surface",
                "path": "validate.rules[0]",
                "message": "Surface quality is below the required minimum.",
                "suggested_repairs": ["surface_enhance_v1"],
            },
            {
                "code": "L0001",
                "name": "warning_only",
                "severity": "warning",
                "message": "Informational note.",
            },
        ],
        repair_suggestions=["surface_enhance_v1"],
    )

    assert summary["status"] == "failed"
    assert summary["score_deficit"] == 0.19
    assert summary["error_count"] == 1
    assert summary["blocking_diagnostics"] == [
        {
            "code": "L6100",
            "name": "ensure_failed",
            "stage": "surface",
            "path": "validate.rules[0]",
            "message": "Surface quality is below the required minimum.",
            "suggested_repairs": ["surface_enhance_v1"],
            "next_step": "Apply or inspect suggested repair `surface_enhance_v1`.",
        }
    ]
    assert summary["next_steps"] == [
        "Raise validation score by at least 0.190 to meet threshold.",
        "Run or apply repair `surface_enhance_v1`.",
    ]


def test_failure_summary_passed_reports_are_empty_of_remediation() -> None:
    summary = _failure_summary(
        certified=True,
        score=0.91,
        threshold=0.8,
        diagnostics=[],
        repair_suggestions=[],
    )

    assert summary == {
        "status": "passed",
        "score": 0.91,
        "threshold": 0.8,
        "score_deficit": 0.0,
        "error_count": 0,
        "blocking_diagnostics": [],
        "next_steps": [],
    }


def test_validate_stage_fails_closed_when_stage_bundles_are_missing(tmp_path) -> None:
    executor = SimpleNamespace(
        stage_dirs={"validate": tmp_path},
        runtime={},
        asset={
            "name": "faulty_asset",
            "validate": {"rules": [], "threshold": 0.8, "repair": {}},
        },
        asset_name="faulty_asset",
        critics={},
    )

    report = run_validate_stage(executor, optimize_bundle={})

    assert report["certified"] is False
    missing_dependency_diags = [
        diag for diag in report["diagnostics"] if diag["name"] == "missing_stage_dependency"
    ]
    assert missing_dependency_diags
    assert {diag["severity"] for diag in missing_dependency_diags} == {"error"}
    assert report["failure_summary"]["status"] == "failed"
    assert report["failure_summary"]["error_count"] == len(missing_dependency_diags)

    persisted = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert persisted["certified"] is False
