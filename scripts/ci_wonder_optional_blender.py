"""Run the optional Wonder Blender lane when Blender is available."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPORT_VERSION = "lathe.wonder_optional_lane_report.v1"
DEFAULT_OUT = Path(".tmp_tests/wonder_ci_optional_blender/report.json")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _candidate_blender() -> str | None:
    explicit = os.environ.get("LATHE_BLENDER_PATH", "").strip()
    if explicit:
        return explicit if Path(explicit).exists() else None
    return shutil.which("blender")


def _tail(text: str, *, max_chars: int = 4000) -> str:
    return text[-max_chars:] if len(text) > max_chars else text


def _run(command: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    return {
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
    parser.add_argument("--strict", action="store_true", help="Fail if Blender is unavailable")
    args = parser.parse_args(argv)

    root = _repo_root()
    out_path = Path(args.out)
    steps = [
        {
            "id": "mocked_blender_bridge_pytest",
            **_run([sys.executable, "-m", "pytest", "-q", "tests/unit/test_scene_blender_export.py"], cwd=root),
        }
    ]
    failed = [step for step in steps if step["status"] != "passed"]
    blender = _candidate_blender()
    if blender is None:
        report = {
            "schema_version": REPORT_VERSION,
            "lane": "blender",
            "status": "failed" if failed else "skipped",
            "reason": "blender executable not available; mocked bridge tests still ran",
            "blocking": bool(failed),
            "steps": steps,
            "render_smoke": {
                "status": "skipped",
                "reason": "Blender-backed scene rendering is not available in the current core/proxy runtime.",
            },
        }
        _write_report(out_path, report)
        print(json.dumps(report, indent=2, sort_keys=False))
        if failed:
            return 1
        return 1 if args.strict else 0

    steps.extend(
        [
            {"id": "blender_version", **_run([blender, "--version"], cwd=root)},
            {"id": "probe_blender", **_run([sys.executable, "-m", "lathe.cli", "probe-blender"], cwd=root)},
            {
                "id": "scene_export_blender_smoke",
                **_run(
                    [
                        sys.executable,
                        "-m",
                        "lathe.cli",
                        "scene",
                        "export",
                        "examples/wonder/alchemist_observatory/scene_graph.json",
                        "--out",
                        ".tmp_tests/wonder_ci_optional_blender/export",
                        "--target",
                        "blender",
                    ],
                    cwd=root,
                ),
            },
        ]
    )
    failed = [step for step in steps if step["status"] != "passed"]
    report = {
        "schema_version": REPORT_VERSION,
        "lane": "blender",
        "status": "failed" if failed else "passed",
        "reason": (
            "Blender bridge/export smoke executed when Blender was available; "
            "Blender-backed scene rendering remains a separate full-runtime gate."
        ),
        "blocking": bool(failed),
        "path": blender,
        "render_smoke": {
            "status": "skipped",
            "reason": "Blender-backed scene rendering is not available in the current core/proxy runtime.",
        },
        "steps": steps,
    }
    _write_report(out_path, report)
    print(json.dumps(report, indent=2, sort_keys=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
