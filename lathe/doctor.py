from __future__ import annotations

import json
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


def _package_reports() -> dict[str, dict[str, Any]]:
    return {
        "lark": package_report("lark"),
        "jsonschema": package_report("jsonschema"),
        "numpy": package_report("numpy"),
        "Pillow": package_report("PIL", "Pillow"),
        "trimesh": package_report("trimesh"),
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


def _remediation_steps(report: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    packages = report["packages"]
    env = report["environment"]
    if not packages["lark"]["available"] or not packages["trimesh"]["available"] or not packages["numpy"]["available"] or not packages["Pillow"]["available"]:
        steps.append(r'Install the base repo dependencies: .\.venv\Scripts\python.exe -m pip install -e .')
    if not packages["pytest"]["available"]:
        steps.append(r'Install developer tooling: .\.venv\Scripts\python.exe -m pip install -e ".[dev]"')
    if not report["lathe"]["editable_install"]["editable"]:
        steps.append(r'Install Lathe in editable mode for local development: .\.venv\Scripts\python.exe -m pip install -e .')
    if not report["blender"]["available"]:
        steps.append("Install Blender or set LATHE_BLENDER_PATH / runtime_config.topology.blender.path so lathe.topology.blender_hard_surface_v1 can use the real adapter.")
    if not report["xatlas"]["available"]:
        nmake = env["commands"].get("nmake")
        if not nmake:
            steps.append("Install Visual Studio Build Tools with the Desktop C++ workload so `pip install xatlas` can compile on Windows, or keep using the explicit reference-box fallback.")
        steps.append(r'Try the optional UV extra after build tools are present: .\.venv\Scripts\python.exe -m pip install -e ".[xatlas]"')
    if not report["torch"]["available"]:
        steps.append(r'Install PyTorch only if you want local ML runtimes: .\.venv\Scripts\python.exe -m pip install -e ".[vggt]"')
    if not report["vggt"]["available"]:
        steps.append(r'Install the official VGGT package manually from source after torch: git clone https://github.com/facebookresearch/vggt.git external\vggt && .\.venv\Scripts\python.exe -m pip install -e .\external\vggt')
    if report["hunyuan"]["configured"] and not report["hunyuan"]["available"]:
        steps.append("Start or fix the configured Hunyuan HTTP server and verify that GET /health responds before requesting the real provider.")
    if not report["shape_providers"]["importable"]:
        steps.append("Fix the base Python dependencies first so Lathe can import shape provider probes.")
    return steps


def collect_doctor_report(runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
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
    report["remediation"] = _remediation_steps(report)
    return report


def format_doctor_report(report: dict[str, Any]) -> str:
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

    blender = report["blender"]
    xatlas = report["xatlas"]
    torch = report["torch"]
    vggt = report["vggt"]
    hunyuan = report["hunyuan"]

    lines.extend(
        [
            "",
            f"Blender: {'ok' if blender['available'] else 'missing'} ({blender.get('path')})",
            f"xatlas: {'ok' if xatlas['available'] else 'missing'} ({xatlas.get('version') or xatlas.get('code')})",
            f"torch/CUDA: {'ok' if torch['available'] else 'missing'} (cuda_available={torch.get('cuda_available')})",
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
            f"(selected={item['selected_adapter']}, real_available={item['real_adapter_available']}, fallback_available={item['fallback_available']})"
        )

    if report["remediation"]:
        lines.extend(["", "Recommended actions:"])
        for step in report["remediation"]:
            lines.append(f"- {step}")

    return "\n".join(lines)


def dump_doctor_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=False)
