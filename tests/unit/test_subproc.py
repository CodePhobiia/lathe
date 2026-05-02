"""Unit tests for :mod:`lathe.subproc`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lathe.subproc import run_sandboxed


PYTHON = str(Path(sys.executable).resolve())


def test_run_sandboxed_calls_on_spawn_hook() -> None:
    seen: list[int] = []

    result = run_sandboxed(
        [PYTHON, "-c", "print('ok')"],
        timeout_s=5,
        on_spawn=seen.append,
    )

    assert result.ok is True
    assert result.stdout.strip() == "ok"
    assert seen and seen[0] > 0


def test_run_sandboxed_on_spawn_failure_is_hard_error() -> None:
    def fail_on_spawn(_pid: int) -> None:
        raise RuntimeError("hook failed")

    with pytest.raises(RuntimeError, match="hook failed"):
        run_sandboxed(
            [PYTHON, "-c", "import time; time.sleep(10)"],
            timeout_s=5,
            on_spawn=fail_on_spawn,
        )


def test_run_sandboxed_rejects_preexec_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lathe.subproc.sys.platform", "win32")

    with pytest.raises(ValueError, match="preexec_fn"):
        run_sandboxed(
            [PYTHON, "-c", "print('nope')"],
            timeout_s=5,
            preexec_fn=lambda: None,
        )
