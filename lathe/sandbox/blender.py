"""Blender subprocess sandbox (SEC-7, V0.2 P0).

Wraps :func:`lathe.subproc.run_sandboxed` with three additional
guarantees aimed specifically at the Blender subprocess:

1. **Per-host resource caps.** On Linux we apply ``RLIMIT_CPU`` +
   ``RLIMIT_AS`` via ``resource.setrlimit`` in the child's preexec_fn.
   On Windows we assign the spawned PID to a Job Object with matching
   limits. macOS falls through to RLIMITs. If the configured cap hook
   cannot be installed, the run fails closed instead of silently running
   Blender without caps.
2. **Per-run log files.** stdout/stderr are mirrored to sibling log
   files under the caller-supplied ``log_dir`` (defaults to ``cwd``)
   so operators can inspect a completed run even if the caller
   discards the in-memory result.
3. **Structured return value.** :class:`BlenderSandboxResult` exposes
   ``exit_code``, ``duration_s``, ``stdout_tail``, ``stderr_tail`` plus
   the underlying :class:`~lathe.subproc.SandboxResult` for call-sites
   that need the full detail.

The module intentionally does **not** inherit the ``run_sandboxed``
implementation — it invokes it — to keep the security-critical primitive
auditable in a single place.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..logging_utils import warning as log_warning
from ..subproc import DEFAULT_STDERR_DENY_PATTERNS, SandboxResult, run_sandboxed

DEFAULT_BLENDER_TIMEOUT_S: float = 600.0
"""Default per-call Blender timeout (seconds). Matches SEC-6 threat model.

Blender runs in the build pipeline are typically <60s; the 600s cap is
sized for generous headroom without letting a runaway process pin the
build forever.
"""

_DEFAULT_MEM_LIMIT_BYTES: int = 8 * 1024 * 1024 * 1024
"""Default address-space ceiling per Blender call (8 GiB)."""

_DEFAULT_CPU_SECONDS: int = 1800
"""Default RLIMIT_CPU in seconds (wall-clock is covered by the timeout)."""

_LOG_TAIL_CHARS: int = 4000

_LOG = logging.getLogger(__name__)


@dataclass
class BlenderSandboxResult:
    """Structured return value for ``run_blender_sandboxed``."""

    exit_code: int
    duration_s: float
    stdout_tail: str
    stderr_tail: str
    timed_out: bool
    stderr_signaled_error: bool
    stdout_log_path: Path | None
    stderr_log_path: Path | None
    raw: SandboxResult

    @property
    def ok(self) -> bool:
        """True iff the base sandbox considered the run successful."""
        return self.raw.ok


def _write_log(log_path: Path, payload: str) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(payload, encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover - disk errors are operator-visible
        log_warning(
            _LOG,
            "lathe.sandbox.blender.log_write_failed",
            "run_blender_sandboxed: failed to write log {path}: {error}",
            path=log_path,
            error=exc,
        )


def _apply_rlimits(cpu_s: int, mem_bytes: int) -> None:
    """Install CPU + address-space rlimits on POSIX hosts.

    Called from the child process via ``subprocess.Popen(preexec_fn=...)``.
    On Windows this is a no-op; the job-object path handles caps there.
    """
    # Only imported on POSIX; ``resource`` does not exist on Windows.
    import resource

    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ValueError, OSError) as exc:  # pragma: no cover - host-policy dependent
        raise RuntimeError("failed to apply Blender subprocess resource limits") from exc


_WINDOWS_JOB_HANDLES: list[int] = []


def _assign_windows_job_object(pid: int, cpu_s: int, mem_bytes: int) -> bool:
    """Assign the spawned process to a capped Windows Job Object.

    Returns True if the job was created and the PID was assigned; False
    if the underlying API was unavailable or the assignment failed. The
    caller treats False as a hard error so Blender never runs uncapped.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:  # pragma: no cover
        return False

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except OSError:  # pragma: no cover - only on broken Windows hosts
        return False

    # JOBOBJECT_EXTENDED_LIMIT_INFORMATION / BASIC_LIMIT_INFORMATION structures.
    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _BASIC_LIMIT(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_void_p),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _EXT_LIMIT(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BASIC_LIMIT),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_TERMINATE = 0x0001

    CreateJobObjectW = kernel32.CreateJobObjectW
    CreateJobObjectW.restype = wintypes.HANDLE
    CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    SetInformationJobObject = kernel32.SetInformationJobObject
    SetInformationJobObject.restype = wintypes.BOOL
    SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    AssignProcessToJobObject = kernel32.AssignProcessToJobObject
    AssignProcessToJobObject.restype = wintypes.BOOL
    AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    OpenProcess = kernel32.OpenProcess
    OpenProcess.restype = wintypes.HANDLE
    OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    CloseHandle = kernel32.CloseHandle
    CloseHandle.restype = wintypes.BOOL
    CloseHandle.argtypes = [wintypes.HANDLE]

    job = CreateJobObjectW(None, None)
    if not job:
        return False

    info = _EXT_LIMIT()
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_PROCESS_TIME | JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    # LARGE_INTEGER is in 100-ns units; cpu_s seconds → cpu_s * 10_000_000.
    info.BasicLimitInformation.PerProcessUserTimeLimit = int(cpu_s * 10_000_000)
    info.ProcessMemoryLimit = int(mem_bytes)

    if not SetInformationJobObject(
        job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
    ):
        CloseHandle(job)
        return False

    proc_handle = OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
    if not proc_handle:
        CloseHandle(job)
        return False
    assigned = bool(AssignProcessToJobObject(job, proc_handle))
    CloseHandle(proc_handle)
    if assigned:
        # Keep the job alive for the duration of the Python host process. Closing
        # it immediately would trigger JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
        _WINDOWS_JOB_HANDLES.append(int(job))
    else:
        CloseHandle(job)
    return assigned


def run_blender_sandboxed(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
    timeout_s: float = DEFAULT_BLENDER_TIMEOUT_S,
    cpu_seconds: int = _DEFAULT_CPU_SECONDS,
    mem_limit_bytes: int = _DEFAULT_MEM_LIMIT_BYTES,
    expect_files: Sequence[Path] | None = None,
    log_dir: Path | None = None,
    log_prefix: str = "blender",
) -> BlenderSandboxResult:
    """Run ``command`` (a Blender invocation) under the Lathe sandbox.

    Args:
        command: argv list whose first element is the Blender binary.
        cwd: working directory for the subprocess.
        extra_env: additional environment entries (merged into the
            allowlisted base; forbidden keys are rejected upstream).
        timeout_s: wall-clock timeout in seconds (default 600).
        cpu_seconds: POSIX RLIMIT_CPU / Windows Job Object CPU cap.
        mem_limit_bytes: POSIX RLIMIT_AS / Windows Job Object memory cap.
        expect_files: artifacts that must exist after a successful run.
        log_dir: directory where per-run stdout/stderr logs are written
            (defaults to ``cwd`` or the parent of the Blender binary).
        log_prefix: filename prefix for the per-run log files.

    Returns:
        :class:`BlenderSandboxResult`.
    """
    argv = [str(item) for item in command]
    if argv:
        # The core sandbox intentionally rejects argv[0] symlinks so it executes
        # an explicitly selected binary, not a mutable link. Blender launchers
        # and test stand-ins (for example uv's .venv/bin/python3) are commonly
        # symlinks, so the adapter canonicalizes only the executable before
        # handing the command to the stricter subprocess layer.
        argv[0] = str(Path(argv[0]).resolve())
    cwd_path = Path(cwd) if cwd is not None else None
    log_root = Path(log_dir) if log_dir is not None else (cwd_path or Path.cwd())
    stdout_log = log_root / f"{log_prefix}.stdout.log"
    stderr_log = log_root / f"{log_prefix}.stderr.log"

    preexec_fn = None
    on_spawn = None
    if sys.platform != "win32":

        def _apply_child_limits() -> None:
            _apply_rlimits(cpu_seconds, mem_limit_bytes)

        preexec_fn = _apply_child_limits
    else:

        def _assign_job_or_fail(pid: int) -> None:
            if not _assign_windows_job_object(pid, cpu_seconds, mem_limit_bytes):
                raise RuntimeError("failed to assign Blender subprocess to Windows Job Object")

        on_spawn = _assign_job_or_fail

    result = run_sandboxed(
        argv,
        timeout_s=timeout_s,
        cwd=cwd_path,
        extra_env=extra_env,
        expect_files=expect_files,
        stderr_deny_patterns=DEFAULT_STDERR_DENY_PATTERNS,
        preexec_fn=preexec_fn,
        on_spawn=on_spawn,
    )

    stdout_log_written: Path | None = None
    stderr_log_written: Path | None = None
    if result.stdout:
        _write_log(stdout_log, result.stdout)
        stdout_log_written = stdout_log
    if result.stderr_tail:
        _write_log(stderr_log, result.stderr_tail)
        stderr_log_written = stderr_log

    return BlenderSandboxResult(
        exit_code=int(result.returncode),
        duration_s=float(result.duration_s),
        stdout_tail=result.stdout[-_LOG_TAIL_CHARS:] if result.stdout else "",
        stderr_tail=result.stderr_tail[-_LOG_TAIL_CHARS:] if result.stderr_tail else "",
        timed_out=bool(result.timed_out),
        stderr_signaled_error=bool(result.stderr_signaled_error),
        stdout_log_path=stdout_log_written,
        stderr_log_path=stderr_log_written,
        raw=result,
    )


__all__ = [
    "DEFAULT_BLENDER_TIMEOUT_S",
    "BlenderSandboxResult",
    "run_blender_sandboxed",
]

# The unused helper below exists so test harnesses can assert the Windows
# branch was wired without actually creating a Job Object on non-Win hosts.
_WINDOWS_JOB_HOOK = _assign_windows_job_object
