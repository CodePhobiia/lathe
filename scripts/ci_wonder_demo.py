"""Run the deterministic Wonder demo CI lane and write a JSON summary."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPORT_VERSION = "lathe.wonder_demo_ci_report.v1"
DEFAULT_OUT = Path(".tmp_tests/wonder_ci_demo/report.json")
DEFAULT_DEMO_OUT = Path(".tmp_tests/wonder_ci_demo/before_after")


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
    parser.add_argument("--demo-out", default=str(DEFAULT_DEMO_OUT), help="Output before/after demo directory")
    args = parser.parse_args(argv)

    root = _repo_root()
    out_path = Path(args.out)
    demo_out = Path(args.demo_out)
    comparison_path = demo_out / "comparisons" / "render_comparison.json"
    history_path = demo_out / "history" / "scene_history.json"
    steps = [
        _run_step(
            "before_after_pytest",
            [sys.executable, "-m", "pytest", "-q", "tests/unit/test_wonder_before_after_cli.py"],
            cwd=root,
        ),
        _run_step(
            "demo_before_after",
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "wonder",
                "demo-before-after",
                "examples/wonder/alchemist_observatory",
                "--out",
                str(demo_out),
                "--patch",
                "examples/wonder/alchemist_observatory/scene_patch_more_sacred.json",
                "--camera-id",
                "camera_reveal",
            ],
            cwd=root,
        ),
        _run_step(
            "validate_render_comparison",
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "wonder",
                "validate-render-comparison",
                str(comparison_path),
            ],
            cwd=root,
        ),
        _run_step(
            "validate_scene_history",
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "wonder",
                "validate-scene-history",
                str(history_path),
            ],
            cwd=root,
        ),
    ]
    failed = [step for step in steps if step["status"] != "passed"]
    report = {
        "schema_version": REPORT_VERSION,
        "lane": "wonder_demo",
        "status": "failed" if failed else "passed",
        "blocking": True,
        "report_path": str(out_path),
        "demo_out": str(demo_out),
        "artifacts": {
            "render_comparison": str(comparison_path),
            "scene_history": str(history_path),
            "before_after_report": str(demo_out / "reports" / "before_after_report.json"),
        },
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
