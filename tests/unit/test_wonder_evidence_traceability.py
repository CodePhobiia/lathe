from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
from lathe.wonder.evidence import WONDER_EVIDENCE_TRACE_VERSION, build_evidence_trace

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _write_trace_inputs(
    tmp_path: Path,
    *,
    tasks: str,
    evidence: str,
) -> tuple[Path, Path]:
    tasks_path = tmp_path / "wonder-tasks.md"
    evidence_path = tmp_path / "evidence.md"
    tasks_path.write_text(tasks, encoding="utf-8")
    evidence_path.write_text(evidence, encoding="utf-8")
    return tasks_path, evidence_path


def test_evidence_trace_schema_accepts_current_repo_report() -> None:
    schema = json.loads((REPO_ROOT / "schema" / "wonder_evidence_trace.schema.json").read_text(encoding="utf-8"))
    report = build_evidence_trace(
        REPO_ROOT / "wonder-tasks.md",
        REPO_ROOT / "docs" / "wonder-readiness" / "evidence.md",
        repo_root=REPO_ROOT,
    )

    assert report["schema_version"] == WONDER_EVIDENCE_TRACE_VERSION
    assert report["ok"] is True
    jsonschema.Draft202012Validator(schema).validate(report)


def test_checked_task_without_evidence_fails(tmp_path: Path) -> None:
    tasks_path, evidence_path = _write_trace_inputs(
        tmp_path,
        tasks="# Tasks\n\n- [x] Validate alpha gate skeleton.\n",
        evidence="# Evidence\n\nNo matching durable evidence yet.\n",
    )

    report = build_evidence_trace(tasks_path, evidence_path, repo_root=tmp_path)

    assert report["ok"] is False
    assert report["missing_evidence"][0]["text"] == "Validate alpha gate skeleton."
    assert report["diagnostics"][0]["code"] == "WET1001"


def test_referenced_evidence_path_must_exist(tmp_path: Path) -> None:
    missing = tmp_path / "missing_report.json"
    tasks_path, evidence_path = _write_trace_inputs(
        tmp_path,
        tasks="# Tasks\n\n- [x] Validate alpha gate skeleton.\n",
        evidence=(
            "# Evidence\n\n"
            "| Date | Task | Type | Path | Status | Result |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            f"| 2026-04-29 | Validate alpha gate skeleton. | report | {missing} | passed | Passed. |\n"
        ),
    )

    report = build_evidence_trace(tasks_path, evidence_path, repo_root=tmp_path)

    assert report["ok"] is False
    assert any(diagnostic["code"] == "WET1002" for diagnostic in report["diagnostics"])


def test_command_evidence_requires_trace_fields(tmp_path: Path) -> None:
    tasks_path, evidence_path = _write_trace_inputs(
        tmp_path,
        tasks="# Tasks\n\n- [x] Run focused validation command.\n",
        evidence=(
            "# Evidence\n\n"
            "| Date | Task | Type | Command | Status | Result |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| 2026-04-29 | Run focused validation command. | command | "
            "`python -m pytest tests/unit/test_demo.py -q` | passed | Passed. |\n"
        ),
    )

    report = build_evidence_trace(tasks_path, evidence_path, repo_root=tmp_path)

    assert report["ok"] is False
    assert any(diagnostic["code"] == "WET1003" for diagnostic in report["diagnostics"])


def test_evidence_trace_cli_writes_passing_report(tmp_path: Path) -> None:
    output = tmp_path / "trace_command_output.json"
    output.write_text("{}", encoding="utf-8")
    tasks_path, evidence_path = _write_trace_inputs(
        tmp_path,
        tasks="# Tasks\n\n- [x] Run focused validation command.\n",
        evidence=(
            "# Evidence\n\n"
            "| Date | Task | Type | Command | Output | Status | Result |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            "| 2026-04-29 | Run focused validation command. | command | "
            f"`python -m pytest tests/unit/test_demo.py -q` | {output} | passed | Passed. |\n"
        ),
    )
    out = tmp_path / "evidence_traceability.json"

    result = _cli(
        "wonder",
        "evidence-trace",
        "--tasks",
        str(tasks_path),
        "--evidence",
        str(evidence_path),
        "--out",
        str(out),
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["summary"]["covered_checked_tasks"] == 1
