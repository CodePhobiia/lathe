"""Tests for :mod:`lathe.sandbox.blender` (SEC-7, V0.2 P0).

Uses a dummy executable (Python itself) and mocks ``run_sandboxed`` so
the suite can run without Blender installed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

from lathe.sandbox.blender import (
    BlenderSandboxResult,
    DEFAULT_BLENDER_TIMEOUT_S,
    run_blender_sandboxed,
)
from lathe.subproc import SandboxResult


def _fake_result(
    *,
    returncode: int = 0,
    stdout: str = "ok",
    stderr_tail: str = "",
    timed_out: bool = False,
    stderr_signaled_error: bool = False,
) -> SandboxResult:
    return SandboxResult(
        argv=[sys.executable, "-c", "pass"],
        returncode=returncode,
        stdout=stdout,
        stderr_tail=stderr_tail,
        stderr_signaled_error=stderr_signaled_error,
        timed_out=timed_out,
        killed_by_signal=None,
        expected_files_ok=True,
        expected_files_missing=[],
        duration_s=0.5,
    )


def test_run_blender_sandboxed_returns_structured_result(tmp_path: Path) -> None:
    with mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=_fake_result()) as run:
        result = run_blender_sandboxed(
            [sys.executable, "-c", "pass"],
            cwd=tmp_path,
            log_dir=tmp_path,
        )
    assert run.called
    kwargs = run.call_args.kwargs
    assert kwargs["timeout_s"] == DEFAULT_BLENDER_TIMEOUT_S
    assert isinstance(result, BlenderSandboxResult)
    assert result.exit_code == 0
    assert result.duration_s == pytest.approx(0.5)
    assert result.ok is True


def test_run_blender_sandboxed_timeout_surfaces_as_timed_out(tmp_path: Path) -> None:
    fake = _fake_result(returncode=-1, timed_out=True, stderr_tail="killed")
    with mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake):
        result = run_blender_sandboxed([sys.executable], cwd=tmp_path, log_dir=tmp_path, timeout_s=1.0)
    assert result.timed_out is True
    assert result.ok is False


def test_run_blender_sandboxed_writes_log_files(tmp_path: Path) -> None:
    fake = _fake_result(stdout="hello world", stderr_tail="a warning")
    with mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake):
        result = run_blender_sandboxed(
            [sys.executable],
            cwd=tmp_path,
            log_dir=tmp_path,
            log_prefix="probe",
        )
    assert result.stdout_log_path is not None and result.stdout_log_path.exists()
    assert result.stderr_log_path is not None and result.stderr_log_path.exists()
    assert result.stdout_log_path.read_text(encoding="utf-8") == "hello world"
    assert result.stderr_log_path.read_text(encoding="utf-8") == "a warning"


def test_run_blender_sandboxed_passes_timeout_and_extra_env(tmp_path: Path) -> None:
    fake = _fake_result()
    with mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake) as run:
        run_blender_sandboxed(
            [sys.executable],
            cwd=tmp_path,
            log_dir=tmp_path,
            timeout_s=42.0,
            extra_env={"LATHE_BLENDER_PATH": sys.executable},
        )
    kwargs = run.call_args.kwargs
    assert kwargs["timeout_s"] == 42.0
    assert kwargs["extra_env"] == {"LATHE_BLENDER_PATH": sys.executable}
    # Env allowlist + forbidden-key rejection is enforced inside run_sandboxed
    # (verified by its own tests); we just assert we route through it.


def test_run_blender_sandboxed_forwards_expect_files(tmp_path: Path) -> None:
    fake = _fake_result()
    artifact = tmp_path / "out.blend"
    with mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake) as run:
        run_blender_sandboxed(
            [sys.executable],
            cwd=tmp_path,
            log_dir=tmp_path,
            expect_files=[artifact],
        )
    kwargs = run.call_args.kwargs
    assert kwargs["expect_files"] == [artifact]


def test_run_blender_sandboxed_stderr_signal_propagates(tmp_path: Path) -> None:
    fake = _fake_result(
        returncode=0,
        stdout="",
        stderr_tail="Traceback (most recent call last):\n  ...",
        stderr_signaled_error=True,
    )
    with mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake):
        result = run_blender_sandboxed([sys.executable], cwd=tmp_path, log_dir=tmp_path)
    assert result.stderr_signaled_error is True
    assert result.ok is False


def test_run_blender_sandboxed_uses_default_timeout_constant(tmp_path: Path) -> None:
    assert DEFAULT_BLENDER_TIMEOUT_S >= 60
    fake = _fake_result()
    with mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake) as run:
        run_blender_sandboxed([sys.executable], cwd=tmp_path, log_dir=tmp_path)
    assert run.call_args.kwargs["timeout_s"] == DEFAULT_BLENDER_TIMEOUT_S
