from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lathe.wonder.readiness import WONDER_ALPHA_GATE_REPORT_VERSION, build_alpha_gate_report

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _write_trace_inputs(tmp_path: Path) -> tuple[Path, Path]:
    marker = tmp_path / "alpha_gate_marker.json"
    marker.write_text("{}", encoding="utf-8")
    tasks_path = tmp_path / "wonder-tasks.md"
    evidence_path = tmp_path / "evidence.md"
    tasks_path.write_text("# Tasks\n\n- [x] Validate alpha gate skeleton.\n", encoding="utf-8")
    evidence_path.write_text(
        "# Evidence\n\n"
        "| Date | Task | Type | Path | Status | Result |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"| 2026-04-29 | Validate alpha gate skeleton. | report | {marker} | passed | Passed. |\n",
        encoding="utf-8",
    )
    return tasks_path, evidence_path


def test_alpha_gate_skeleton_writes_core_reports(tmp_path: Path) -> None:
    tasks_path, evidence_path = _write_trace_inputs(tmp_path)
    out = tmp_path / "wonder_alpha_gate"

    report = build_alpha_gate_report(
        EXAMPLE_DIR,
        out,
        tasks_path=tasks_path,
        evidence_path=evidence_path,
    )

    assert report["schema_version"] == WONDER_ALPHA_GATE_REPORT_VERSION
    assert report["core_alpha_gate"] == "passed"
    assert report["blocking_missing_runtimes"] == []
    assert report["alpha_decision_ready"] is True
    assert (out / "reports" / "env_probe.json").exists()
    assert (out / "reports" / "evidence_traceability.json").exists()
    assert (out / "reports" / "final_readiness_report.json").exists()
    assert (out / "reports" / "final_readiness_report.md").exists()
    assert (out / "reports" / "benchmark_report.json").exists()
    assert (out / "reports" / "security_report.json").exists()
    assert (out / "reports" / "performance_report.json").exists()
    assert (out / "reports" / "contract_catalog.json").exists()
    assert (out / "reports" / "cli_catalog.json").exists()
    assert (out / "reports" / "example_catalog.json").exists()
    assert (out / "before").is_dir()
    assert (out / "after").is_dir()
    assert (out / "comparisons").is_dir()
    assert (out / "history").is_dir()
    assert report["optional_lanes"]["blender"] in {"passed", "skipped_nonblocking"}
    assert report["optional_lanes"]["roblox"] in {"passed", "skipped_nonblocking"}
    assert report["report_bundle"]["final_readiness_report_md"].endswith("final_readiness_report.md")
    assert report["reports"]["example_catalog_summary"]["failed"] == 0
    assert any(lane["lane"] == "human_alpha_decision" for lane in report["known_deferred_lanes"])


def test_alpha_gate_cli_writes_final_readiness_report(tmp_path: Path) -> None:
    tasks_path, evidence_path = _write_trace_inputs(tmp_path)
    out = tmp_path / "wonder_alpha_gate"

    result = _cli(
        "wonder",
        "alpha-gate",
        str(EXAMPLE_DIR),
        "--out",
        str(out),
        "--tasks",
        str(tasks_path),
        "--evidence",
        str(evidence_path),
    )

    assert result.returncode == 0, result.stderr or result.stdout
    stdout_payload = json.loads(result.stdout)
    report_path = out / "reports" / "final_readiness_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert stdout_payload == report
    assert report["core_alpha_gate"] == "passed"
    assert report["lanes"]
    assert report["alpha_decision_ready"] is True
    assert report["remaining_human_decision"] == "Approve Project Wonder alpha gate."
