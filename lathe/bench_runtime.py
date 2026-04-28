from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .eval_harness import _negative_scorecard
from .executor import build_asset
from .parser import parse_file
from .test_runtime import evaluate_test_expr


def _program_files(files: list[str] | None) -> list[Path]:
    if files:
        return [Path(item).resolve() for item in files]
    return sorted(Path("examples").glob("*.lth"))


def run_lathe_benchmarks(files: list[str] | None = None) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for file_path in _program_files(files):
        resolved_file = Path(file_path).resolve()
        program = parse_file(file_path)
        fixture_map = {item["name"]: item for item in program.get("fixtures", [])}
        for decl in program.get("benchmarks", []):
            values = decl.get("values", {})
            asset_name = str(values.get("asset", ""))
            with tempfile.TemporaryDirectory() as tmpdir:
                out_dir = Path(tmpdir) / asset_name
                report = build_asset(program, asset_name, out_dir)
                # JSON ingress — internal controlled payloads from our own validate/shape stage artifacts emitted by build_asset above into a tempdir; safe without schema validation.
                validate_report = json.loads(
                    (out_dir / "stages" / "validate" / "report.json").read_text(encoding="utf-8")
                )
                shape_bundle = json.loads(
                    (out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8")
                )
            comparisons: list[dict[str, Any]] = []
            compare_ok = True
            for fixture_name in values.get("compare_against", []):
                fixture = fixture_map.get(fixture_name)
                if not fixture:
                    comparisons.append({"fixture": fixture_name, "ok": False, "reason": "missing_fixture"})
                    compare_ok = False
                    continue
                fixture_values = fixture.get("values", {})
                benchmark_entry = {
                    "name": fixture_name,
                    "file": str(resolved_file.relative_to(Path.cwd())).replace("\\", "/"),
                    "asset": str(fixture_values.get("asset", asset_name)),
                    "build_dir": str(fixture_values.get("build_dir", "")),
                }
                negative = _negative_scorecard(Path.cwd(), benchmark_entry, expected_to_fail=True)
                fixture_ok = not negative["ok"]
                comparisons.append({"fixture": fixture_name, "ok": fixture_ok, "negative": negative})
                compare_ok = compare_ok and fixture_ok

            context = {
                "benchmark": values,
                "report": report,
                "validate": validate_report,
                "shape": shape_bundle,
                "score": report["score"],
                "threshold": report["threshold"],
            }
            assertion_results = []
            passed = True
            for assertion in decl.get("asserts", []):
                value = evaluate_test_expr(assertion["expr"], context)
                assertion_results.append({"expr": assertion["expr"], "passed": bool(value), "value": value})
                passed = passed and bool(value)
            if values.get("must_pass"):
                passed = passed and bool(report.get("certified"))
            passed = passed and compare_ok
            results.append(
                {
                    "file": str(file_path),
                    "resolved_file": str(resolved_file),
                    "name": decl["name"],
                    "asset": asset_name,
                    "passed": passed,
                    "report": report,
                    "validate": validate_report,
                    "shape": shape_bundle,
                    "comparisons": comparisons,
                    "assertions": assertion_results,
                }
            )
    passed = sum(1 for item in results if item["passed"])
    return {
        "ok": passed == len(results),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
