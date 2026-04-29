from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PS1 = REPO_ROOT / "scripts" / "demo_wonder_seed_scene.ps1"
DEMO_SH = REPO_ROOT / "scripts" / "demo_wonder_seed_scene.sh"
DEMO_CI = REPO_ROOT / "scripts" / "ci_wonder_demo.py"
DEMO_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "wonder-demo.yml"


def test_seed_demo_scripts_include_before_after_comparison_lane() -> None:
    ps1 = DEMO_PS1.read_text(encoding="utf-8")
    sh = DEMO_SH.read_text(encoding="utf-8")

    for script in (ps1, sh):
        assert "demo-before-after" in script
        assert "validate-render-comparison" in script
        assert "before_after" in script
        assert "camera_reveal" in script


def test_wonder_demo_ci_lane_is_wired_to_proxy_before_after() -> None:
    script = DEMO_CI.read_text(encoding="utf-8")
    workflow = DEMO_WORKFLOW.read_text(encoding="utf-8")

    assert "tests/unit/test_wonder_before_after_cli.py" in script
    assert "demo-before-after" in script
    assert "validate-render-comparison" in script
    assert "validate-scene-history" in script
    assert "python scripts/ci_wonder_demo.py" in workflow
    assert "wonder-demo-report" in workflow
    assert "render_comparison.json" in workflow


def test_wonder_demo_ci_script_writes_report(tmp_path: Path) -> None:
    report_path = tmp_path / "demo_ci_report.json"
    demo_out = tmp_path / "before_after"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/ci_wonder_demo.py",
            "--out",
            str(report_path),
            "--demo-out",
            str(demo_out),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "lathe.wonder_demo_ci_report.v1"
    assert payload["status"] == "passed"
    assert payload["summary"]["failed"] == 0
    assert (demo_out / "comparisons" / "render_comparison.json").exists()
    assert (demo_out / "history" / "scene_history.json").exists()
