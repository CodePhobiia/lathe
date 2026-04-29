from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lathe.wonder import build_alpha_gate_report, write_readiness_report_files

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


def test_readiness_report_files_include_required_sections_and_json(tmp_path: Path) -> None:
    alpha_report = build_alpha_gate_report(EXAMPLE_DIR, tmp_path / "alpha_gate")
    out = tmp_path / "final_readiness_report.md"

    result = write_readiness_report_files(out, alpha_report)

    assert result["ok"] is True
    markdown = out.read_text(encoding="utf-8")
    sibling_json = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert "## Status Summary" in markdown
    assert "## Core Gates" in markdown
    assert "## Optional Gates" in markdown
    assert "## Evidence Bundle Paths" in markdown
    assert "## Known Deferred Lanes" in markdown
    assert "## Final Alpha Decision" in markdown
    assert sibling_json["core_alpha_gate"] == "passed"
    assert sibling_json["blocking_missing_runtimes"] == []
    assert sibling_json["alpha_decision_ready"] is True
    assert sibling_json["remaining_human_decision"] == "Approve Project Wonder alpha gate."


def test_readiness_report_cli_uses_existing_alpha_report(tmp_path: Path) -> None:
    alpha_out = tmp_path / "alpha_gate"
    build_alpha_gate_report(EXAMPLE_DIR, alpha_out)
    alpha_report = alpha_out / "reports" / "final_readiness_report.json"
    out = tmp_path / "docs" / "final_readiness_report.md"

    result = _cli(
        "wonder",
        "readiness-report",
        "--alpha-report",
        str(alpha_report),
        "--out",
        str(out),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["core_alpha_gate"] == "passed"
    assert out.exists()
    assert out.with_suffix(".json").exists()
