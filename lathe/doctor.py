"""``lathe doctor`` runtime: environment and provider diagnostics.

Collects capability probes into the human-readable report the
``lathe doctor`` CLI prints.
"""

from __future__ import annotations

import json
import os
import sys
from importlib.metadata import entry_points
from typing import Any

from .capabilities import (
    deterministic_backend_reports,
    environment_report,
    package_report,
    probe_blender,
    probe_hunyuan_endpoint,
    probe_nvidia_smi,
    probe_torch,
    probe_vggt,
    probe_xatlas,
    repo_install_report,
)

_BASE_DEPS_REMEDIATION = r"Install the base repo dependencies: .\.venv\Scripts\python.exe -m pip install -e ."
_DEV_DEPS_REMEDIATION = r'Install developer tooling: .\.venv\Scripts\python.exe -m pip install -e ".[dev]"'
_EDITABLE_REMEDIATION = r"Install Lathe in editable mode: .\.venv\Scripts\python.exe -m pip install -e ."
_EDITABLE_DEV_REMEDIATION = (
    r"Install Lathe in editable mode for local development: "
    r".\.venv\Scripts\python.exe -m pip install -e ."
)
_BASE_REQUIRED_PACKAGES = (
    "lark",
    "jsonschema",
    "numpy",
    "Pillow",
    "trimesh",
    "scipy",
    "networkx",
)


def _package_reports() -> dict[str, dict[str, Any]]:
    return {
        "lark": package_report("lark"),
        "jsonschema": package_report("jsonschema"),
        "numpy": package_report("numpy"),
        "Pillow": package_report("PIL", "Pillow"),
        "trimesh": package_report("trimesh"),
        "scipy": package_report("scipy"),
        "networkx": package_report("networkx"),
        "pytest": package_report("pytest"),
        "xatlas": package_report("xatlas"),
        "torch": package_report("torch"),
        "torchvision": package_report("torchvision"),
        "vggt": package_report("vggt"),
    }


def _shape_provider_reports(runtime_config: dict[str, Any] | None) -> dict[str, Any]:
    try:
        from .shape_providers import probe_all_shape_providers
    except (ImportError, OSError, RuntimeError, AttributeError) as exc:
        # Broader than plain ImportError because optional deps pulled transitively
        # can raise OSError (shared-lib load), RuntimeError (C-extension init),
        # or AttributeError (partial-module states during import-time failures).
        return {
            "importable": False,
            "reports": [],
            "error": str(exc),
        }
    return {
        "importable": True,
        "reports": probe_all_shape_providers(runtime_config),
        "error": None,
    }


def _required_packages_available(packages: dict[str, dict[str, Any]]) -> bool:
    return all(packages[name]["available"] for name in _BASE_REQUIRED_PACKAGES)


def _base_dependencies_missing(packages: dict[str, dict[str, Any]]) -> bool:
    return any(
        not packages[name]["available"]
        for name in ("lark", "trimesh", "numpy", "Pillow", "scipy", "networkx")
    )


def _setup_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    env = report["environment"]
    packages = report["packages"]
    python = env["python"]
    commands = env["commands"]
    venv_active = bool(python["venv_active"] or python.get("conda_prefix"))
    return [
        {
            "id": "python_version",
            "ok": sys.version_info >= (3, 11),
            "severity": "error",
            "ok_message": f"Python {sys.version_info.major}.{sys.version_info.minor} satisfies the >=3.11 requirement.",
            "fail_message": "Lathe requires Python 3.11 or newer.",
            "remediation": (
                "Create a Python 3.11+ virtual environment and rerun Lathe from that interpreter."
            ),
        },
        {
            "id": "virtualenv_active",
            "ok": venv_active,
            "severity": "warning",
            "ok_message": "An active virtual environment was detected.",
            "fail_message": "No active virtual environment was detected.",
            "remediation": (
                r"Create and activate one: py -3.11 -m venv .venv; "
                r".\.venv\Scripts\Activate.ps1"
            ),
        },
        {
            "id": "pip_available",
            "ok": bool(commands.get("pip")),
            "severity": "error",
            "ok_message": "pip is on PATH.",
            "fail_message": "pip was not found on PATH.",
            "remediation": (
                "Use the Python interpreter that owns this checkout and run "
                "`python -m ensurepip --upgrade` if needed."
            ),
        },
        {
            "id": "git_available",
            "ok": bool(commands.get("git")),
            "severity": "warning",
            "ok_message": "git is on PATH.",
            "fail_message": "git was not found on PATH.",
            "remediation": (
                "Install Git and reopen the shell so repo metadata, plugins, and source installs "
                "work predictably."
            ),
        },
        {
            "id": "base_dependencies",
            "ok": _required_packages_available(packages),
            "severity": "error",
            "ok_message": "All required base Python packages are importable.",
            "fail_message": "One or more required Python packages are missing.",
            "remediation": _BASE_DEPS_REMEDIATION,
        },
        {
            "id": "editable_install",
            "ok": bool(report["lathe"]["editable_install"]["editable"]),
            "severity": "warning",
            "ok_message": "Lathe is installed in editable/source mode.",
            "fail_message": "Lathe is importable but not installed in editable/source mode.",
            "remediation": _EDITABLE_REMEDIATION,
        },
        {
            "id": "dev_dependencies",
            "ok": bool(packages["pytest"]["available"]),
            "severity": "warning",
            "ok_message": "Developer test tooling is available.",
            "fail_message": "Developer test tooling is missing.",
            "remediation": _DEV_DEPS_REMEDIATION,
        },
        {
            "id": "cwd_writable",
            "ok": bool(_cwd_writable()),
            "severity": "warning",
            "ok_message": "The current working directory is writable.",
            "fail_message": "The current working directory does not appear writable.",
            "remediation": (
                "Run Lathe from a writable checkout, or choose writable --out and cache directories."
            ),
        },
    ]


def _cwd_writable() -> bool:
    # SEC: probe writability by attempting to create a file under cwd, not by
    # writing into ``dir="."`` (which is symlink-bait if cwd contains a
    # hostile pre-existing path). ``os.access`` is good enough for the doctor
    # check — if it lies, the actual ``lathe build --out`` invocation will
    # still surface the OSError.
    try:
        return os.access(".", os.W_OK)
    except OSError:
        return False


def _append_unique(steps: list[str], step: str) -> None:
    if step not in steps:
        steps.append(step)


def _append_xatlas_remediation(
    steps: list[str],
    env: dict[str, Any],
    report: dict[str, Any],
) -> None:
    if report["xatlas"]["available"]:
        return
    nmake = env["commands"].get("nmake")
    if not nmake:
        _append_unique(
            steps,
            "Install Visual Studio Build Tools with the Desktop C++ workload so "
            "`pip install xatlas` can compile on Windows, or keep using the explicit "
            "reference-box fallback.",
        )
    _append_unique(
        steps,
        r"Try the optional UV extra after build tools are present: "
        r'.\.venv\Scripts\python.exe -m pip install -e ".[xatlas]"',
    )


def _append_provider_remediation(steps: list[str], report: dict[str, Any]) -> None:
    if report["hunyuan"]["configured"] and not report["hunyuan"]["available"]:
        _append_unique(
            steps,
            "Start or fix the configured Hunyuan HTTP server and verify that GET /health "
            "responds before requesting the real provider.",
        )
    if not report["shape_providers"]["importable"]:
        _append_unique(
            steps,
            "Fix the base Python dependencies first so Lathe can import shape provider probes.",
        )


def _append_ml_remediation(steps: list[str], report: dict[str, Any]) -> None:
    if not report["torch"]["available"]:
        _append_unique(
            steps,
            r"Install PyTorch only if you want local ML runtimes: "
            r'.\.venv\Scripts\python.exe -m pip install -e ".[vggt]"',
        )
    if not report["vggt"]["available"]:
        _append_unique(
            steps,
            r"Install the official VGGT package manually from source after torch: "
            r"git clone https://github.com/facebookresearch/vggt.git external\vggt && "
            r".\.venv\Scripts\python.exe -m pip install -e .\external\vggt",
        )


def _remediation_steps(report: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    packages = report["packages"]
    env = report["environment"]
    for check in report.get("setup_checks", []):
        if not check.get("ok") and check.get("remediation"):
            _append_unique(steps, str(check["remediation"]))
    if _base_dependencies_missing(packages):
        _append_unique(steps, _BASE_DEPS_REMEDIATION)
    if not packages["pytest"]["available"]:
        _append_unique(steps, _DEV_DEPS_REMEDIATION)
    if not report["lathe"]["editable_install"]["editable"]:
        _append_unique(steps, _EDITABLE_DEV_REMEDIATION)
    if not report["blender"]["available"]:
        _append_unique(
            steps,
            "Install Blender or set LATHE_BLENDER_PATH / runtime_config.topology.blender.path "
            "so lathe.topology.blender_hard_surface_v1 can use the real adapter.",
        )
    _append_xatlas_remediation(steps, env, report)
    _append_ml_remediation(steps, report)
    _append_provider_remediation(steps, report)
    return steps


def collect_doctor_report(runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Collect doctor report.

    Args:
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    report = {
        "environment": environment_report(),
        "lathe": repo_install_report(),
        "packages": _package_reports(),
        "blender": probe_blender(runtime_config),
        "xatlas": probe_xatlas(),
        "torch": probe_torch(),
        "nvidia_smi": probe_nvidia_smi(),
        "vggt": probe_vggt(runtime_config),
        "hunyuan": probe_hunyuan_endpoint(runtime_config),
        "shape_providers": _shape_provider_reports(runtime_config),
        "deterministic_backends": deterministic_backend_reports(runtime_config),
    }
    report["setup_checks"] = _setup_checks(report)
    report["remediation"] = _remediation_steps(report)
    return report


def format_doctor_report(report: dict[str, Any]) -> str:
    """Format doctor report.

    Args:
        report: report argument.

    Returns:
        The result.
    """
    env = report["environment"]
    python = env["python"]
    lines = [
        "Lathe Doctor",
        f"OS: {env['os']['platform']}",
        f"Shell: {env['shell']}",
        f"Python: {python['version'].splitlines()[0]}",
        f"Interpreter: {python['executable']}",
        f"Virtualenv active: {python['venv_active']}",
        f"Lathe editable install: {report['lathe']['editable_install']['editable']}",
        "",
        "Packages:",
    ]
    for name, pkg in report["packages"].items():
        status = "ok" if pkg["available"] else "missing"
        version = pkg["version"] or "n/a"
        lines.append(f"- {name}: {status} ({version})")

    lines.extend(["", "Setup checks:"])
    for check in report.get("setup_checks", []):
        ok = check.get("ok")
        status = "ok" if ok else str(check.get("severity", "warning"))
        message = check.get("ok_message" if ok else "fail_message", check.get("message", ""))
        lines.append(f"- {check.get('id')}: {status} ({message})")

    blender = report["blender"]
    xatlas = report["xatlas"]
    torch = report["torch"]
    vggt = report["vggt"]
    hunyuan = report["hunyuan"]

    lines.extend(
        [
            "",
            f"Blender: {'ok' if blender['available'] else 'missing'} ({blender.get('path')})",
            (
                f"xatlas: {'ok' if xatlas['available'] else 'missing'} "
                f"({xatlas.get('version') or xatlas.get('code')})"
            ),
            (
                f"torch/CUDA: {'ok' if torch['available'] else 'missing'} "
                f"(cuda_available={torch.get('cuda_available')})"
            ),
            f"VGGT: {'ok' if vggt['available'] else 'unavailable'} (device={vggt.get('selected_device')})",
            f"Hunyuan health: {'ok' if hunyuan['available'] else 'unavailable'} ({hunyuan.get('base_url')})",
            "",
            "Shape providers:",
        ]
    )
    if report["shape_providers"]["importable"]:
        for item in report["shape_providers"]["reports"]:
            provider_id = item.get("provider_id")
            status = "ok" if item.get("available") else "unavailable"
            message = item.get("message") or item.get("code") or "ok"
            lines.append(f"- {provider_id}: {status} ({message})")
    else:
        lines.append(f"- probe import failed: {report['shape_providers']['error']}")

    lines.extend(["", "Deterministic backends:"])
    for item in report["deterministic_backends"]:
        status = "ok" if item.get("available") else "unavailable"
        lines.append(
            f"- {item['backend_id']}: {status} "
            f"(selected={item['selected_adapter']}, "
            f"real_available={item['real_adapter_available']}, "
            f"fallback_available={item['fallback_available']})"
        )

    if report["remediation"]:
        lines.extend(["", "Recommended actions:"])
        for step in report["remediation"]:
            lines.append(f"- {step}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plugin registry report (Plan 03 Phase 2)
# ---------------------------------------------------------------------------


_PLUGIN_GROUPS: tuple[str, ...] = (
    "lathe.backends",
    "lathe.stacks",
    "lathe.providers.shape",
    "lathe.validators",
)


def collect_plugin_report() -> dict[str, Any]:
    """Enumerate entry-point-discovered Lathe plugins.

    Returns a map keyed by entry-point group, each pointing at a list of
    ``{name, value, resolvable, error}`` records. ``resolvable=False``
    with an ``error`` string means the entry point is declared but its
    target cannot be imported -- the common "broken third-party plugin"
    signal for ``lathe doctor --plugins``.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for group in _PLUGIN_GROUPS:
        try:
            eps = entry_points(group=group)
        except TypeError:  # pragma: no cover - Python <3.10 API
            eps = entry_points().get(group, [])  # type: ignore[attr-defined]
        records: list[dict[str, Any]] = []
        for ep in eps:
            record: dict[str, Any] = {
                "name": ep.name,
                "value": ep.value,
                "resolvable": False,
                "error": None,
            }
            try:
                ep.load()
                record["resolvable"] = True
            except Exception as exc:
                record["error"] = str(exc)
            records.append(record)
        groups[group] = sorted(records, key=lambda item: item["name"])
    return {"groups": groups}


def format_plugin_report(report: dict[str, Any]) -> str:
    """Format plugin report.

    Args:
        report: report argument.

    Returns:
        The result.
    """
    lines = ["Lathe Plugins (entry points)"]
    for group, records in report["groups"].items():
        lines.append("")
        lines.append(f"[{group}]")
        if not records:
            lines.append("  (none discovered)")
            continue
        for item in records:
            status = "ok" if item["resolvable"] else "unresolvable"
            suffix = f" ({item['error']})" if item["error"] else ""
            lines.append(f"  - {item['name']} -> {item['value']}: {status}{suffix}")
    return "\n".join(lines)


def dump_doctor_json(report: dict[str, Any]) -> str:
    """Dump doctor json.

    Args:
        report: report argument.

    Returns:
        The result.
    """
    return json.dumps(report, indent=2, sort_keys=False)
