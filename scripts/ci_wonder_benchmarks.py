"""Run deterministic Wonder benchmark checks and write a CI report."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPORT_VERSION = "lathe.wonder_ci_report.v1"
DEFAULT_ROOT = Path(".tmp_tests/wonder_ci_benchmarks")
DEFAULT_OUT = DEFAULT_ROOT / "report.json"

PASSING_TIMINGS = {
    "stages": {
        "brief": {"duration_ms": 8_000},
        "scene_graph": {"duration_ms": 18_000},
        "source_generation": {"duration_ms": 8_000},
        "check_plan": {"duration_ms": 4_000},
        "preview_build": {"duration_ms": 50_000},
        "preview_render": {"duration_ms": 20_000},
        "patch_preview": {"duration_ms": 30_000},
        "final_export": {"duration_ms": 120_000},
    },
    "cache": {"hits": 2, "misses": 2, "writes": 1},
}

PASSING_SCORES = {
    "metrics": {
        "prompt_to_brief": 0.9,
        "brief_to_scene": 0.88,
        "parse_check": True,
        "build_success": True,
        "scene_validation": 0.9,
        "style_consistency": 0.85,
        "object_count_accuracy": 0.9,
        "render_quality": 0.82,
        "patch_success": True,
        "continuity_preservation": 0.9,
        "export_validity": True,
    }
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _tail(text: str, *, max_chars: int = 4000) -> str:
    return text[-max_chars:] if len(text) > max_chars else text


def _write_json(path: Path, payload: MappingLike) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _run_step(step_id: str, command: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    return {
        "id": step_id,
        "command": command,
        "returncode": result.returncode,
        "status": "passed" if result.returncode == 0 else "failed",
        "stdout_tail": _tail(result.stdout),
        "stderr_tail": _tail(result.stderr),
    }


def _benchmark_fixture_step(root: Path) -> tuple[Path, Path, Path]:
    out_root = root / "wonder_ci_benchmarks"
    timings_path = out_root / "timings.json"
    scores_path = out_root / "scores.json"
    report_path = out_root / "scene_benchmark_report.json"
    _write_json(timings_path, PASSING_TIMINGS)
    _write_json(scores_path, PASSING_SCORES)
    return timings_path, scores_path, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON report path")
    args = parser.parse_args(argv)

    root = _repo_root()
    out_path = Path(args.out)
    timings_path, scores_path, benchmark_report_path = _benchmark_fixture_step(root / ".tmp_tests")
    steps = [
        _run_step(
            "benchmark_pytest",
            [sys.executable, "-m", "pytest", "-q", "tests/unit/test_scene_bench.py"],
            cwd=root,
        ),
        _run_step(
            "scene_bench_cli",
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "scene",
                "bench",
                "examples/wonder/alchemist_observatory/scene_graph.json",
                "--timings",
                str(timings_path),
                "--scores",
                str(scores_path),
                "--out",
                str(benchmark_report_path),
            ],
            cwd=root,
        ),
        _run_step(
            "validate_scene_benchmark_report",
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "wonder",
                "validate-scene-benchmark-report",
                str(benchmark_report_path),
            ],
            cwd=root,
        ),
    ]
    failed = [step for step in steps if step["status"] != "passed"]
    report = {
        "schema_version": REPORT_VERSION,
        "lane": "wonder_benchmarks",
        "status": "failed" if failed else "passed",
        "blocking": True,
        "report_path": str(out_path),
        "benchmark_report": str(benchmark_report_path),
        "steps": steps,
        "summary": {"total": len(steps), "passed": len(steps) - len(failed), "failed": len(failed)},
    }
    _write_json(out_path, report)
    print(json.dumps(report, indent=2, sort_keys=False))
    return 1 if failed else 0


MappingLike = dict[str, Any]


if __name__ == "__main__":
    raise SystemExit(main())
