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
    DEFAULT_BLENDER_TIMEOUT_S,
    BlenderSandboxResult,
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


def test_run_blender_sandboxed_passes_posix_limits_as_child_hook(tmp_path: Path) -> None:
    fake = _fake_result()
    with (
        mock.patch("lathe.sandbox.blender.sys.platform", "linux"),
        mock.patch("lathe.sandbox.blender._apply_rlimits") as apply_limits,
        mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake) as run,
    ):
        run_blender_sandboxed(
            [sys.executable],
            cwd=tmp_path,
            log_dir=tmp_path,
            cpu_seconds=7,
            mem_limit_bytes=1024,
        )

        kwargs = run.call_args.kwargs
        assert callable(kwargs["preexec_fn"])
        assert kwargs["on_spawn"] is None
        apply_limits.assert_not_called()

        kwargs["preexec_fn"]()
        apply_limits.assert_called_once_with(7, 1024)


def test_run_blender_sandboxed_passes_windows_job_hook(tmp_path: Path) -> None:
    fake = _fake_result()
    with (
        mock.patch("lathe.sandbox.blender.sys.platform", "win32"),
        mock.patch("lathe.sandbox.blender._assign_windows_job_object", return_value=True) as assign_job,
        mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake) as run,
    ):
        run_blender_sandboxed(
            [sys.executable],
            cwd=tmp_path,
            log_dir=tmp_path,
            cpu_seconds=8,
            mem_limit_bytes=2048,
        )

        kwargs = run.call_args.kwargs
        assert kwargs["preexec_fn"] is None
        assert callable(kwargs["on_spawn"])

        kwargs["on_spawn"](1234)
        assign_job.assert_called_once_with(1234, 8, 2048)


def test_run_blender_sandboxed_windows_job_failure_is_hard_error(tmp_path: Path) -> None:
    fake = _fake_result()
    with (
        mock.patch("lathe.sandbox.blender.sys.platform", "win32"),
        mock.patch("lathe.sandbox.blender._assign_windows_job_object", return_value=False),
        mock.patch("lathe.sandbox.blender.run_sandboxed", return_value=fake) as run,
    ):
        run_blender_sandboxed([sys.executable], cwd=tmp_path, log_dir=tmp_path)

        with pytest.raises(RuntimeError, match="Windows Job Object"):
            run.call_args.kwargs["on_spawn"](1234)


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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX resource-limit fixture uses RLIMIT_CPU in the child process",
)
def test_run_blender_sandboxed_posix_cpu_heavy_fixture_is_limited(tmp_path: Path) -> None:
    """Use Python as a deterministic Blender stand-in for CPU-heavy work."""
    result = run_blender_sandboxed(
        [sys.executable, "-c", "while True: pass"],
        cwd=tmp_path,
        log_dir=tmp_path,
        log_prefix="cpu_heavy_fixture",
        timeout_s=5,
        cpu_seconds=1,
        mem_limit_bytes=512 * 1024 * 1024,
    )

    assert result.ok is False
    assert result.exit_code != 0 or result.timed_out
    assert result.duration_s < 5


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="RLIMIT_AS memory fixture is deterministic only on Linux",
)
def test_run_blender_sandboxed_memory_heavy_fixture_hits_address_space_limit(
    tmp_path: Path,
) -> None:
    """Use Python as a deterministic Blender stand-in for memory-heavy work."""
    script = (
        "import sys\n"
        "try:\n"
        "    blocks = []\n"
        "    for _ in range(64):\n"
        "        blocks.append(bytearray(16 * 1024 * 1024))\n"
        "except MemoryError:\n"
        "    sys.stderr.write('memory-limited by sandbox\\n')\n"
        "    raise SystemExit(77)\n"
        "print('allocation unexpectedly succeeded')\n"
    )
    result = run_blender_sandboxed(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        log_dir=tmp_path,
        log_prefix="memory_heavy_fixture",
        timeout_s=5,
        cpu_seconds=10,
        mem_limit_bytes=256 * 1024 * 1024,
    )

    assert result.ok is False
    assert result.exit_code != 0
    assert result.duration_s < 5
    assert "memory-limited by sandbox" in result.stderr_tail or result.raw.killed_by_signal is not None
