"""Run the deterministic Wonder fast CI lane and write a JSON summary."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPORT_VERSION = "lathe.wonder_ci_report.v1"
DEFAULT_OUT = Path(".tmp_tests/wonder_ci_fast/report.json")

FOCUSED_TESTS = [
    "tests/unit/test_wonder_contracts.py",
    "tests/unit/test_wonder_env_probe.py",
    "tests/unit/test_wonder_evidence_traceability.py",
    "tests/unit/test_wonder_alpha_gate.py",
    "tests/unit/test_wonder_readiness_report.py",
    "tests/unit/test_wonder_memory.py",
    "tests/unit/test_scene_patch.py",
    "tests/unit/test_scene_history.py",
    "tests/unit/test_scene_rollback.py",
    "tests/unit/test_scene_camera_lock.py",
    "tests/unit/test_scene_compare.py",
    "tests/unit/test_wonder_llm.py",
    "tests/unit/test_scene_planner.py",
    "tests/unit/test_scene_source_diagnostics.py",
    "tests/unit/test_wonder_examples_catalog.py",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _tail(text: str, *, max_chars: int = 4000) -> str:
    return text[-max_chars:] if len(text) > max_chars else text


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


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON report path")
    args = parser.parse_args(argv)

    root = _repo_root()
    out_path = Path(args.out)
    steps = [
        _run_step("focused_pytest", [sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS], cwd=root),
        _run_step(
            "alpha_gate",
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "wonder",
                "alpha-gate",
                "examples/wonder/alchemist_observatory",
                "--out",
                ".tmp_tests/wonder_ci_fast/alpha_gate",
            ],
            cwd=root,
        ),
    ]
    failed = [step for step in steps if step["status"] != "passed"]
    report = {
        "schema_version": REPORT_VERSION,
        "lane": "wonder_fast",
        "status": "failed" if failed else "passed",
        "blocking": True,
        "report_path": str(out_path),
        "steps": steps,
        "summary": {
            "total": len(steps),
            "passed": len(steps) - len(failed),
            "failed": len(failed),
        },
    }
    _write_report(out_path, report)
    print(json.dumps(report, indent=2, sort_keys=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
