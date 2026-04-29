"""Validate all Wonder golden examples and write a JSON summary."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPORT_VERSION = "lathe.wonder_ci_report.v1"
DEFAULT_OUT = Path(".tmp_tests/wonder_ci_examples/report.json")


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
    parser.add_argument("--examples-root", default="examples/wonder", help="Wonder examples root")
    args = parser.parse_args(argv)

    root = _repo_root()
    out_path = Path(args.out)
    examples_root = root / args.examples_root
    catalog_path = out_path.parent / "example_catalog.json"
    steps = [
        _run_step(
            "catalog_examples",
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "wonder",
                "catalog-examples",
                args.examples_root,
                "--out",
                str(catalog_path),
            ],
            cwd=root,
        )
    ]
    for example_dir in sorted(path for path in examples_root.iterdir() if path.is_dir()):
        relative_scene = str((example_dir / "scene_graph.json").relative_to(root))
        proxy_root = out_path.parent / "proxy" / example_dir.name
        steps.append(
            _run_step(
                f"validate_example_{example_dir.name}",
                [
                    sys.executable,
                    "-m",
                    "lathe.cli",
                    "wonder",
                    "validate-example",
                    str(example_dir.relative_to(root)),
                ],
                cwd=root,
            )
        )
        steps.extend(
            [
                _run_step(
                    f"build_preview_{example_dir.name}",
                    [
                        sys.executable,
                        "-m",
                        "lathe.cli",
                        "scene",
                        "build",
                        relative_scene,
                        "--out",
                        str(proxy_root / "build"),
                        "--mode",
                        "preview",
                        "--deterministic",
                        "--allow-fallback",
                    ],
                    cwd=root,
                ),
                _run_step(
                    f"validate_preview_package_{example_dir.name}",
                    [
                        sys.executable,
                        "-m",
                        "lathe.cli",
                        "scene",
                        "package",
                        "validate",
                        str(proxy_root / "build" / example_dir.name),
                    ],
                    cwd=root,
                ),
                _run_step(
                    f"render_preview_{example_dir.name}",
                    [
                        sys.executable,
                        "-m",
                        "lathe.cli",
                        "scene",
                        "render",
                        relative_scene,
                        "--out",
                        str(proxy_root / "renders"),
                        "--all-cameras",
                        "--mode",
                        "preview",
                    ],
                    cwd=root,
                ),
                _run_step(
                    f"export_glb_{example_dir.name}",
                    [
                        sys.executable,
                        "-m",
                        "lathe.cli",
                        "scene",
                        "export",
                        relative_scene,
                        "--out",
                        str(proxy_root / "exports"),
                        "--target",
                        "glb",
                        "--mode",
                        "preview",
                        "--include-id-mask-bundle",
                    ],
                    cwd=root,
                ),
            ]
        )
    failed = [step for step in steps if step["status"] != "passed"]
    deferred_lanes: list[str] = []
    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        examples = catalog.get("examples", []) if isinstance(catalog, dict) else []
        deferred_lanes = sorted(
            {
                str(lane)
                for example in examples
                if isinstance(example, dict)
                for lane in example.get("deferred_lanes", [])
                if isinstance(lane, str)
            }
        )
    report = {
        "schema_version": REPORT_VERSION,
        "lane": "wonder_examples",
        "status": "failed" if failed else "passed",
        "blocking": True,
        "report_path": str(out_path),
        "catalog_path": str(catalog_path),
        "deferred_lanes_nonblocking": deferred_lanes,
        "proxy_runtime": {
            "builds": "lathe.scene.executor.offline_proxy_v1",
            "renderer": "lathe.scene.proxy_renderer.v1",
            "exporter": "lathe.scene.proxy_glb_exporter.v1",
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
