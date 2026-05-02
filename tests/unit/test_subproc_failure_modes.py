"""Sandboxed subprocess failure-mode coverage."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lathe.sandbox.blender import _apply_rlimits
from lathe.subproc import run_sandboxed


PYTHON = str(Path(sys.executable).resolve())


def test_run_sandboxed_rejects_non_list_argv() -> None:
    with pytest.raises(TypeError, match="argv must be a list"):
        run_sandboxed((PYTHON, "-c", "pass"), timeout_s=5)  # type: ignore[arg-type]


def test_run_sandboxed_nonzero_returncode_is_result_not_exception() -> None:
    result = run_sandboxed(
        [PYTHON, "-c", "import sys; sys.stderr.write('soft failure'); sys.exit(7)"],
        timeout_s=5,
    )

    assert result.ok is False
    assert result.returncode == 7
    assert result.stderr_tail == "soft failure"


def test_run_sandboxed_stderr_deny_pattern_marks_failure() -> None:
    result = run_sandboxed(
        [
            PYTHON,
            "-c",
            "import sys; sys.stderr.write('Traceback (most recent call last):\\nnope')",
        ],
        timeout_s=5,
    )

    assert result.returncode == 0
    assert result.stderr_signaled_error is True
    assert result.ok is False
    assert result.matched_stderr_patterns == ["Traceback (most recent call last):"]


def test_run_sandboxed_timeout_returns_typed_failure() -> None:
    result = run_sandboxed(
        [PYTHON, "-c", "import time; time.sleep(10)"],
        timeout_s=0.1,
    )

    assert result.ok is False
    assert result.timed_out is True
    assert result.returncode == -1


def test_run_sandboxed_expected_file_outside_cwd_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside", encoding="utf-8")
    result = run_sandboxed(
        [PYTHON, "-c", "print('ok')"],
        timeout_s=5,
        cwd=tmp_path,
        expect_files=[outside],
    )

    assert result.ok is False
    assert result.expected_files_ok is False
    assert result.expected_files_missing == [outside]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink artifact escape coverage only")
def test_run_sandboxed_rejects_expected_file_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-artifact.txt"
    outside.write_text("outside", encoding="utf-8")
    escape_link = tmp_path / "artifact.glb"
    try:
        escape_link.symlink_to(outside)
    except (NotImplementedError, OSError):
        outside.unlink(missing_ok=True)
        pytest.skip("symlinks are unavailable in this environment")
    try:
        result = run_sandboxed(
            [PYTHON, "-c", "print('ok')"],
            timeout_s=5,
            cwd=tmp_path,
            expect_files=[escape_link],
        )
    finally:
        escape_link.unlink(missing_ok=True)
        outside.unlink(missing_ok=True)

    assert result.ok is False
    assert result.expected_files_ok is False
    assert result.expected_files_missing == [escape_link]


def test_run_sandboxed_expected_missing_file_is_reported(tmp_path: Path) -> None:
    missing = tmp_path / "missing.glb"

    result = run_sandboxed(
        [PYTHON, "-c", "print('ok')"],
        timeout_s=5,
        cwd=tmp_path,
        expect_files=[missing],
    )

    assert result.ok is False
    assert result.expected_files_missing == [missing]


def test_run_sandboxed_scrubs_forbidden_inherited_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LD_PRELOAD", "bad")
    monkeypatch.setenv("PYTHONPATH", "bad")
    result = run_sandboxed(
        [
            PYTHON,
            "-c",
            (
                "import os; "
                "print(os.environ.get('LD_PRELOAD')); "
                "print(os.environ.get('PYTHONPATH')); "
                "print(os.environ.get('SAFE_FLAG'))"
            ),
        ],
        timeout_s=5,
        env_allowlist=("PATH",),
        extra_env={"SAFE_FLAG": "1"},
    )

    assert result.ok is True
    assert result.stdout.splitlines() == ["None", "None", "1"]


def test_run_sandboxed_does_not_inherit_blender_user_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLENDER_USER_CONFIG", "host-config")
    monkeypatch.setenv("BLENDER_USER_SCRIPTS", "host-scripts")
    result = run_sandboxed(
        [
            PYTHON,
            "-c",
            (
                "import os; "
                "print(os.environ.get('BLENDER_USER_CONFIG')); "
                "print(os.environ.get('BLENDER_USER_SCRIPTS'))"
            ),
        ],
        timeout_s=5,
    )

    assert result.ok is True
    assert result.stdout.splitlines() == ["None", "None"]


def test_run_sandboxed_rejects_forbidden_extra_env() -> None:
    with pytest.raises(ValueError, match="extra_env cannot include forbidden keys"):
        run_sandboxed(
            [PYTHON, "-c", "pass"],
            timeout_s=5,
            extra_env={"PYTHONPATH": "bad"},
        )


def test_run_sandboxed_rejects_forbidden_env_keys_case_insensitively() -> None:
    with pytest.raises(ValueError, match="env_allowlist cannot include forbidden keys"):
        run_sandboxed([PYTHON, "-c", "pass"], timeout_s=5, env_allowlist=("pythonpath",))

    with pytest.raises(ValueError, match="extra_env cannot include forbidden keys"):
        run_sandboxed([PYTHON, "-c", "pass"], timeout_s=5, extra_env={"pythonpath": "bad"})


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink executable rejection only")
def test_run_sandboxed_rejects_symlink_executable(tmp_path: Path) -> None:
    link = tmp_path / "python-link"
    try:
        link.symlink_to(Path(PYTHON))
    except (NotImplementedError, OSError):
        pytest.skip("symlinks are unavailable in this environment")

    with pytest.raises(ValueError, match="argv\\[0\\] is a symlink"):
        run_sandboxed([str(link), "-c", "pass"], timeout_s=5)


@pytest.mark.skipif(sys.platform == "win32", reason="resource.setrlimit is POSIX-only")
def test_posix_resource_limit_hook_terminates_cpu_heavy_child() -> None:
    result = run_sandboxed(
        [PYTHON, "-c", "while True: pass"],
        timeout_s=5,
        preexec_fn=lambda: _apply_rlimits(1, 256 * 1024 * 1024),
    )

    assert result.ok is False
    assert result.returncode != 0 or result.timed_out
    assert result.duration_s < 5


def test_run_sandboxed_does_not_use_shell_for_metacharacters() -> None:
    result = run_sandboxed(
        [PYTHON, "-c", "import sys; print(sys.argv[1])", "literal && echo nope"],
        timeout_s=5,
        env_allowlist=("PATH",),
    )

    assert result.ok is True
    assert result.stdout.strip() == "literal && echo nope"
