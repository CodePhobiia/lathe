"""Central sandboxed subprocess wrapper (Plan 07 Phase 4 — BL-11).

All subprocess invocations in the Lathe runtime should flow through
:func:`run_sandboxed`. The wrapper:

* scrubs the inherited environment down to an explicit allowlist so
  variables like ``LD_PRELOAD``, ``DYLD_INSERT_LIBRARIES``,
  ``PYTHONPATH``, and ``BLENDER_SYSTEM_SCRIPTS`` cannot leak into child
  processes,
* enforces ``shell=False`` and ``check=False`` so timeouts and non-zero
  returncodes are surfaced as typed result data, not exceptions,
* scans ``stderr`` for known fatal-error banners (``Traceback``,
  ``Fatal Python error``, ``Segmentation fault``, ``AddressSanitizer``,
  …) and treats matches as failure even on returncode 0,
* validates expected output files exist and are contained inside the
  subprocess's working directory.

The return type, :class:`SandboxResult`, exposes an ``ok`` property that
call-sites can use to decide success without re-implementing the scan.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_STDERR_DENY_PATTERNS: tuple[str, ...] = (
    "Error:",
    "Traceback (most recent call last):",
    "Python script failed",
    "Segmentation fault",
    "Fatal Python error:",
    "AddressSanitizer:",
)


_FORBIDDEN_ENV_KEYS: frozenset[str] = frozenset(
    {
        "LD_PRELOAD",
        "DYLD_INSERT_LIBRARIES",
        "BLENDER_SYSTEM_SCRIPTS",
        "PYTHONPATH",
    }
)


_DEFAULT_ENV_ALLOWLIST: tuple[str, ...] = (
    "PATH",
    "TEMP",
    "LATHE_BLENDER_PATH",
)
_FORBIDDEN_ENV_KEYS_NORMALIZED: frozenset[str] = frozenset(key.casefold() for key in _FORBIDDEN_ENV_KEYS)


@dataclass
class SandboxResult:
    """Typed result returned from :func:`run_sandboxed`."""

    argv: list[str]
    returncode: int
    stdout: str
    stderr_tail: str
    stderr_signaled_error: bool
    matched_stderr_patterns: list[str] = field(default_factory=list)
    timed_out: bool = False
    killed_by_signal: int | None = None
    expected_files_ok: bool = True
    expected_files_missing: list[Path] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        """Ok.

        Returns:
            The result.
        """
        return (
            not self.timed_out
            and self.returncode == 0
            and not self.stderr_signaled_error
            and self.expected_files_ok
        )


def _validate_argv(argv: Sequence[object]) -> list[str]:
    if not isinstance(argv, list):
        raise TypeError("run_sandboxed: argv must be a list")
    if not argv:
        raise ValueError("run_sandboxed: argv must be a non-empty list")
    first = argv[0]
    if not isinstance(first, (str, Path)):
        raise TypeError("run_sandboxed: argv[0] must be str or pathlib.Path")
    executable = Path(first)
    # On Windows, symlink semantics differ (Path.is_symlink often returns False
    # for reparse points and shortcuts), so we only enforce the symlink check on
    # POSIX platforms. is_file() is still required on every OS.
    if sys.platform != "win32" and executable.is_symlink():
        raise ValueError(f"run_sandboxed: argv[0] is a symlink: {executable}")
    if not executable.is_file():
        raise ValueError(f"run_sandboxed: argv[0] is not a regular file: {executable}")
    return [str(arg) for arg in argv]


def _build_env(env_allowlist: Sequence[str], extra_env: dict[str, str] | None) -> dict[str, str]:
    forbidden_in_allowlist = [
        str(key) for key in env_allowlist if str(key).casefold() in _FORBIDDEN_ENV_KEYS_NORMALIZED
    ]
    if forbidden_in_allowlist:
        raise ValueError(
            f"run_sandboxed: env_allowlist cannot include forbidden keys: {sorted(forbidden_in_allowlist)}"
        )
    clean: dict[str, str] = {}
    for key in env_allowlist:
        value = os.environ.get(key)
        if value is not None:
            clean[key] = value
    if extra_env:
        forbidden_in_extra = [
            str(key) for key in extra_env if str(key).casefold() in _FORBIDDEN_ENV_KEYS_NORMALIZED
        ]
        if forbidden_in_extra:
            raise ValueError(
                f"run_sandboxed: extra_env cannot include forbidden keys: {sorted(forbidden_in_extra)}"
            )
        clean.update({str(k): str(v) for k, v in extra_env.items()})
    return clean


def _check_expected_files(
    expect_files: Sequence[Path] | None,
    cwd: Path | None,
) -> tuple[bool, list[Path]]:
    if not expect_files:
        return True, []
    missing: list[Path] = []
    cwd_resolved: Path | None = None
    if cwd is not None:
        try:
            cwd_resolved = Path(cwd).resolve()
        except OSError:
            cwd_resolved = Path(cwd)
    for target in expect_files:
        path = Path(target)
        if not path.exists():
            missing.append(path)
            continue
        if cwd_resolved is not None:
            try:
                resolved = path.resolve()
            except OSError:
                missing.append(path)
                continue
            try:
                resolved.relative_to(cwd_resolved)
            except ValueError:
                # Path exists but lives outside the subprocess cwd — reject.
                missing.append(path)
    return (not missing), missing


def run_sandboxed(
    argv: list[str],
    *,
    timeout_s: float,
    cwd: Path | None = None,
    env_allowlist: Sequence[str] = _DEFAULT_ENV_ALLOWLIST,
    extra_env: dict[str, str] | None = None,
    expect_files: Sequence[Path] | None = None,
    input_bytes: bytes | None = None,
    stderr_deny_patterns: tuple[str, ...] = DEFAULT_STDERR_DENY_PATTERNS,
    preexec_fn: Callable[[], None] | None = None,
    on_spawn: Callable[[int], None] | None = None,
) -> SandboxResult:
    """Run ``argv`` as a subprocess with env scrubbing and stderr scanning.

    See module docstring for the security rationale.
    """
    normalized_argv = _validate_argv(argv)
    clean_env = _build_env(env_allowlist, extra_env)
    start = time.monotonic()
    proc: subprocess.Popen[bytes] | subprocess.Popen[str] | None = None
    try:
        if preexec_fn is not None and sys.platform == "win32":
            raise ValueError("run_sandboxed: preexec_fn is only supported on POSIX hosts")

        if preexec_fn is not None or on_spawn is not None:
            popen_kwargs = {
                "cwd": str(cwd) if cwd is not None else None,
                "env": clean_env,
                "shell": False,
                "stdin": subprocess.PIPE if input_bytes is not None else None,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": input_bytes is None,
            }
            if preexec_fn is not None:
                popen_kwargs["preexec_fn"] = preexec_fn
            proc = subprocess.Popen(normalized_argv, **popen_kwargs)
            if on_spawn is not None:
                try:
                    on_spawn(int(proc.pid))
                except Exception:
                    proc.kill()
                    proc.wait()
                    raise
            result_stdout, result_stderr = proc.communicate(input=input_bytes, timeout=timeout_s)
            stdout = (
                result_stdout.decode("utf-8", errors="replace")
                if isinstance(result_stdout, bytes)
                else (result_stdout or "")
            )
            stderr = (
                result_stderr.decode("utf-8", errors="replace")
                if isinstance(result_stderr, bytes)
                else (result_stderr or "")
            )
            returncode = proc.returncode
        elif input_bytes is not None:
            result = subprocess.run(
                normalized_argv,
                cwd=str(cwd) if cwd is not None else None,
                env=clean_env,
                input=input_bytes,
                timeout=timeout_s,
                shell=False,
                check=False,
                capture_output=True,
            )
            stdout = (
                result.stdout.decode("utf-8", errors="replace")
                if isinstance(result.stdout, bytes)
                else (result.stdout or "")
            )
            stderr = (
                result.stderr.decode("utf-8", errors="replace")
                if isinstance(result.stderr, bytes)
                else (result.stderr or "")
            )
            returncode = result.returncode
        else:
            result = subprocess.run(
                normalized_argv,
                cwd=str(cwd) if cwd is not None else None,
                env=clean_env,
                timeout=timeout_s,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            returncode = result.returncode
    except subprocess.TimeoutExpired as exc:
        if proc is not None:
            proc.kill()
            try:
                stdout_after_kill, stderr_after_kill = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                stdout_after_kill, stderr_after_kill = exc.stdout, exc.stderr
            if exc.stdout is None:
                exc.stdout = stdout_after_kill
            if exc.stderr is None:
                exc.stderr = stderr_after_kill
        duration = time.monotonic() - start
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        ) or ""
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        ) or ""
        return SandboxResult(
            argv=normalized_argv,
            returncode=-1,
            stdout=stdout,
            stderr_tail=stderr.strip()[-2000:],
            stderr_signaled_error=False,
            matched_stderr_patterns=[],
            timed_out=True,
            killed_by_signal=None,
            expected_files_ok=False,
            expected_files_missing=list(expect_files or []),
            duration_s=duration,
        )

    duration = time.monotonic() - start
    matched = [pat for pat in stderr_deny_patterns if pat in stderr]
    killed_by_signal: int | None = None
    if returncode is not None and returncode < 0:
        killed_by_signal = -returncode
    expected_ok, missing = _check_expected_files(expect_files, cwd)
    return SandboxResult(
        argv=normalized_argv,
        returncode=int(returncode),
        stdout=stdout,
        stderr_tail=stderr.strip()[-2000:],
        stderr_signaled_error=bool(matched),
        matched_stderr_patterns=matched,
        timed_out=False,
        killed_by_signal=killed_by_signal,
        expected_files_ok=expected_ok,
        expected_files_missing=missing,
        duration_s=duration,
    )


__all__ = [
    "DEFAULT_STDERR_DENY_PATTERNS",
    "SandboxResult",
    "run_sandboxed",
]
