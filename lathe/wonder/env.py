"""Environment probing for the deterministic Wonder alpha gate."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

WONDER_ENV_PROBE_VERSION = "lathe.wonder_env_probe.v1"

_OPTIONAL_RUNTIME_KEYS = (
    "posix_shell",
    "blender",
    "roblox_studio",
    "external_viewer",
)


def _first_nonempty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _run_probe(executable: str, args: Sequence[str]) -> tuple[bool, str | None]:
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=4,
        )
    except FileNotFoundError:
        return False, "executable disappeared before probing"
    except subprocess.TimeoutExpired:
        return False, "probe timed out"
    except OSError as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = _first_nonempty_line(result.stderr) or _first_nonempty_line(result.stdout)
        return False, detail or f"probe exited with {result.returncode}"
    return True, _first_nonempty_line(result.stdout) or _first_nonempty_line(result.stderr)


def _probe_command(
    runtime: str,
    candidates: Sequence[str],
    probe_args: Sequence[str],
    *,
    blocking: bool,
) -> dict[str, Any]:
    attempts: list[dict[str, str]] = []
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved is None:
            continue
        available, detail = _run_probe(resolved, probe_args)
        if available:
            return {
                "runtime": runtime,
                "status": "available",
                "path": resolved,
                "version": detail,
                "blocking": blocking,
            }
        attempts.append({"candidate": candidate, "path": resolved, "reason": detail or "probe failed"})
    reason = (
        "no candidate executable found"
        if not attempts
        else "; ".join(f"{item['candidate']}: {item['reason']}" for item in attempts)
    )
    return {
        "runtime": runtime,
        "status": "missing",
        "reason": reason,
        "blocking": blocking,
    }


def _python_probe() -> dict[str, Any]:
    return {
        "runtime": "python",
        "status": "available",
        "path": sys.executable,
        "version": platform.python_version(),
        "blocking": True,
    }


def _probe_powershell() -> dict[str, Any]:
    return _probe_command(
        "powershell",
        ("pwsh", "powershell"),
        ("-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"),
        blocking=False,
    )


def _optional_lane_status(probe: dict[str, Any], *, strict: bool) -> dict[str, Any]:
    available = probe.get("status") == "available"
    if available:
        return {
            "status": "passed",
            "blocking": False,
            "runtime_status": "available",
            "path": probe.get("path"),
        }
    return {
        "status": "failed" if strict else "skipped_nonblocking",
        "blocking": strict,
        "runtime_status": "missing",
        "reason": probe.get("reason", "runtime unavailable"),
    }


def probe_wonder_environment(*, mode: str = "core") -> dict[str, Any]:
    """Return machine-readable runtime availability for Wonder validation.

    ``core`` mode only treats Python as blocking. Optional runtimes are reported
    so humans can see what is missing, but they cannot fail the deterministic
    alpha gate unless a caller asks for ``strict`` mode.
    """
    if mode not in {"core", "strict"}:
        raise ValueError("mode must be 'core' or 'strict'")
    strict = mode == "strict"
    runtimes = {
        "python": _python_probe(),
        "posix_shell": _probe_command("posix_shell", ("bash", "sh"), ("--version",), blocking=strict),
        "powershell": _probe_powershell(),
        "blender": _probe_command(
            "blender",
            tuple(candidate for candidate in (os.environ.get("LATHE_BLENDER_PATH"), "blender") if candidate),
            ("--version",),
            blocking=strict,
        ),
        "roblox_studio": _probe_command(
            "roblox_studio",
            ("RobloxStudioBeta.exe", "RobloxStudio.exe", "roblox-studio"),
            ("--version",),
            blocking=strict,
        ),
        "external_viewer": _probe_command(
            "external_viewer",
            ("usdview", "gltf-viewer", "assimp_viewer"),
            ("--version",),
            blocking=strict,
        ),
    }
    optional_missing = [
        key
        for key in _OPTIONAL_RUNTIME_KEYS
        if runtimes[key].get("status") != "available"
    ]
    blocking_missing = [
        key
        for key, probe in runtimes.items()
        if probe.get("blocking") is True and probe.get("status") != "available"
    ]
    optional_lanes = {
        "posix": _optional_lane_status(runtimes["posix_shell"], strict=strict),
        "blender": _optional_lane_status(runtimes["blender"], strict=strict),
        "roblox": _optional_lane_status(runtimes["roblox_studio"], strict=strict),
        "external_viewer": _optional_lane_status(runtimes["external_viewer"], strict=strict),
    }
    return {
        "schema_version": WONDER_ENV_PROBE_VERSION,
        "ok": not blocking_missing,
        "mode": mode,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": runtimes["python"]["status"],
        "posix_shell": runtimes["posix_shell"]["status"],
        "powershell": runtimes["powershell"]["status"],
        "blender": runtimes["blender"]["status"],
        "roblox_studio": runtimes["roblox_studio"]["status"],
        "external_viewer": runtimes["external_viewer"]["status"],
        "blocking_missing": blocking_missing,
        "optional_missing": optional_missing,
        "optional_lanes": optional_lanes,
        "runtimes": runtimes,
    }


__all__ = [
    "WONDER_ENV_PROBE_VERSION",
    "probe_wonder_environment",
]
