# Blender Subprocess Sandbox

Lathe runs Blender through `lathe.sandbox.blender.run_blender_sandboxed`, which layers Blender-specific controls on top of `lathe.subproc.run_sandboxed`.

## Guarantees

- The subprocess inherits only the allowlisted environment keys accepted by `run_sandboxed`.
- Blender is invoked by argv with `shell=False`; command strings are never passed through a shell.
- stdout and stderr are captured, scanned for known fatal signatures, and mirrored to per-run log files.
- Expected output files must exist after success and must remain inside the subprocess working directory.
- A wall-clock timeout applies to every invocation.
- Resource caps are requested for CPU time and address space.

## Platform Behavior

| Platform | CPU and memory cap mechanism | Failure behavior |
| --- | --- | --- |
| Linux and other POSIX hosts | `subprocess.Popen(preexec_fn=...)` applies `RLIMIT_CPU` and `RLIMIT_AS` in the child process before Blender starts. | If either limit cannot be installed, the child launch fails and the build surfaces a hard error. |
| macOS | Uses the same POSIX `preexec_fn` path. `RLIMIT_AS` behavior is kernel-dependent, so the wall-clock timeout remains the reliable outer guard. | Limit installation failure is surfaced as a hard error. |
| Windows | The spawned PID is assigned to a Windows Job Object with process CPU time, process memory, and kill-on-job-close limits. | If assignment fails, the subprocess is killed and the build surfaces a hard error. |

## Known Limits

- The sandbox is a subprocess hardening layer, not an OS-level container.
- It does not virtualize the filesystem. Blender still runs with the current user's filesystem permissions, so only trusted Blender binaries and Lathe-generated driver scripts should be used.
- Windows Job Object handles are kept open by the Python host process so `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` does not terminate Blender immediately.
- POSIX `RLIMIT_AS` can be conservative for programs with large virtual-address reservations. If a platform rejects the configured cap, Lathe fails closed rather than silently running without limits.
- Resource-exhaustion coverage uses deterministic Python-as-Blender fixtures
  through `run_blender_sandboxed`: CPU-heavy fixtures run on POSIX hosts, and
  memory-heavy fixtures run on Linux where `RLIMIT_AS` is deterministic. Real
  Blender availability is still optional for this guard; the wrapper behavior is
  what the fixture certifies.
