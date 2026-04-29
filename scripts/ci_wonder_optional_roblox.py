"""Run the optional Wonder Roblox lane when local Roblox tooling is available."""

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
DEFAULT_OUT = Path(".tmp_tests/wonder_ci_optional_roblox/report.json")

_ROBLOX_COMMANDS = (
    "RobloxStudioBeta.exe",
    "RobloxStudio.exe",
    "roblox-studio",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _candidate_roblox() -> str | None:
    for env_name in ("LATHE_ROBLOX_STUDIO_PATH", "ROBLOX_STUDIO_PATH"):
        explicit = os.environ.get(env_name, "").strip()
        if explicit and Path(explicit).exists():
            return explicit
    for command in _ROBLOX_COMMANDS:
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return None


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
    parser.add_argument("--strict", action="store_true", help="Fail if Roblox tooling is unavailable")
    args = parser.parse_args(argv)

    root = _repo_root()
    out_path = Path(args.out)
    roblox = _candidate_roblox()
    if roblox is None:
        report = {
            "schema_version": REPORT_VERSION,
            "lane": "roblox",
            "status": "skipped",
            "reason": "Roblox tooling not available",
            "blocking": False,
        }
        _write_report(out_path, report)
        print(json.dumps(report, indent=2, sort_keys=False))
        return 1 if args.strict else 0

    manifest_path = out_path.parent / "roblox_manifest.json"
    steps = [
        _run(
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "wonder",
                "validate-roblox-profile",
                "examples/wonder/abandoned_roblox_mall/roblox_profile.json",
            ],
            cwd=root,
        ),
        _run(
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "scene",
                "roblox-manifest",
                "examples/wonder/abandoned_roblox_mall/scene_graph.json",
                "--profile",
                "examples/wonder/abandoned_roblox_mall/roblox_profile.json",
                "--out",
                str(manifest_path),
            ],
            cwd=root,
        ),
        _run(
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "wonder",
                "validate-roblox-manifest",
                str(manifest_path),
            ],
            cwd=root,
        ),
    ]
    failed = [step for step in steps if step["status"] != "passed"]
    report = {
        "schema_version": REPORT_VERSION,
        "lane": "roblox",
        "status": "failed" if failed else "passed",
        "reason": "Roblox profile and manifest validation executed; no Studio import/export evidence is claimed.",
        "blocking": bool(failed),
        "path": roblox,
        "manifest_path": str(manifest_path),
        "steps": steps,
    }
    _write_report(out_path, report)
    print(json.dumps(report, indent=2, sort_keys=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
