from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lathe.wonder.env import WONDER_ENV_PROBE_VERSION, probe_wonder_environment

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


def test_wonder_env_probe_reports_optional_runtimes_as_nonblocking() -> None:
    payload = probe_wonder_environment(mode="core")

    assert payload["schema_version"] == WONDER_ENV_PROBE_VERSION
    assert payload["ok"] is True
    assert payload["python"] == "available"
    assert payload["blocking_missing"] == []
    assert set(payload["optional_lanes"]) == {"posix", "blender", "roblox", "external_viewer"}
    for lane in payload["optional_lanes"].values():
        assert lane["blocking"] is False
        assert lane["status"] in {"passed", "skipped_nonblocking"}


def test_wonder_env_probe_cli_writes_report(tmp_path: Path) -> None:
    out = tmp_path / "wonder_env_probe.json"

    result = _cli("wonder", "env-probe", "--out", str(out))

    assert result.returncode == 0, result.stderr or result.stdout
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == json.loads(result.stdout)
    assert payload["schema_version"] == WONDER_ENV_PROBE_VERSION
    assert payload["blocking_missing"] == []
