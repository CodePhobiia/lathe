from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .checker import check_program
from .executor import BuildError, build_asset
from .parser import parse_file
from .resolver import Resolver
from .utils import get_by_path, has_path


def _lookup(context: dict[str, Any], name: str) -> Any:
    if "." in name and has_path(context, name):
        return get_by_path(context, name)
    if name in context:
        return context[name]
    return name


def evaluate_test_expr(expr: Any, context: dict[str, Any]) -> Any:
    if isinstance(expr, (bool, int, float)):
        return expr
    if isinstance(expr, str):
        return _lookup(context, expr)
    if isinstance(expr, list):
        return [evaluate_test_expr(item, context) for item in expr]
    if isinstance(expr, dict):
        etype = expr.get("type")
        if etype == "call":
            name = expr["name"]
            args = [evaluate_test_expr(item["value"], context) for item in expr.get("args", [])]
            kwargs = {
                item["name"]: evaluate_test_expr(item["value"], context)
                for item in expr.get("args", [])
                if item.get("name")
            }
            if name == "exists":
                target = kwargs.get("path", args[0] if args else "")
                return bool(isinstance(target, str) and has_path(context, target))
            if name == "len":
                target = args[0] if args else kwargs.get("value")
                return len(target)
            if name == "contains":
                haystack = kwargs.get("haystack", args[0] if args else [])
                needle = kwargs.get("needle", args[1] if len(args) > 1 else None)
                return needle in haystack
            raise ValueError(f"Unsupported test builtin '{name}'")
        if etype == "range":
            return {
                "from": evaluate_test_expr(expr["from"], context),
                "to": evaluate_test_expr(expr["to"], context),
            }
        if etype == "unary":
            value = evaluate_test_expr(expr["value"], context)
            if expr["op"] == "not":
                return not bool(value)
            if expr["op"] == "-":
                return -float(value)
        if etype == "binary":
            left = evaluate_test_expr(expr["left"], context)
            right = evaluate_test_expr(expr["right"], context)
            op = expr["op"]
            if op == "and":
                return bool(left) and bool(right)
            if op == "or":
                return bool(left) or bool(right)
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                return left / right
            if op == "in":
                return left in right
    raise ValueError(f"Unsupported test expression: {expr!r}")


def _program_files(files: list[str] | None) -> list[Path]:
    if files:
        return [Path(item).resolve() for item in files]
    return sorted(Path("examples").glob("*.lth"))


def run_lathe_tests(files: list[str] | None = None) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for file_path in _program_files(files):
        program = parse_file(file_path)
        diagnostics = check_program(program)
        errors = [item for item in diagnostics if item["severity"] == "error"]
        resolver = Resolver(program)
        for decl in program.get("tests", []):
            values = decl.get("values", {})
            asset_name = values.get("asset")
            context: dict[str, Any] = {"test": values}
            build_report = None
            build_error = None
            if asset_name:
                asset = resolver.materialize_asset(str(asset_name))
                context["asset"] = asset
                context.update(asset)
                if values.get("must_build") or values.get("must_certify"):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        out_dir = Path(tmpdir) / str(asset_name)
                        try:
                            build_report = build_asset(program, str(asset_name), out_dir)
                            context["build"] = build_report
                        except BuildError as exc:
                            build_error = {"message": str(exc), "diagnostics": exc.diagnostics}
                            context["build_error"] = build_error
            assertion_results = []
            passed = not errors
            for assertion in decl.get("asserts", []):
                value = evaluate_test_expr(assertion["expr"], context)
                assertion_results.append({"expr": assertion["expr"], "passed": bool(value), "value": value})
                passed = passed and bool(value)
            if values.get("must_build"):
                passed = passed and build_report is not None
            if values.get("must_certify"):
                passed = passed and bool(build_report and build_report.get("certified"))
            results.append(
                {
                    "file": str(file_path),
                    "name": decl["name"],
                    "asset": asset_name,
                    "passed": passed,
                    "diagnostics": errors,
                    "assertions": assertion_results,
                    "build": build_report,
                    "build_error": build_error,
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
