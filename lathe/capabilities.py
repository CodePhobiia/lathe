from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
from pathlib import Path
from typing import Any

from lathe.errors import LatheConfigError
from lathe.net import NetGuardError, safe_urlopen
from lathe.validation import validate_json_bytes


_HUNYUAN_PROBE_MAX_BODY_BYTES = 64 * 1024
_HUNYUAN_PROBE_MAX_TIMEOUT_S = 5.0

_NETGUARD_TO_PROBE_CODE: dict[str, str] = {
    "invalid_url": "invalid_url",
    "scheme_insecure": "scheme_insecure",
    "host_not_allowlisted": "scheme_insecure",
    "dns_resolution_failed": "dns_resolution_failed",
    "private_ip_rejected": "private_ip_rejected",
    "unexpected_media_type": "unexpected_content_type",
    "response_too_large": "response_too_large",
}


DEFAULT_HUNYUAN_BASE_URL = "http://localhost:8081"
DEFAULT_VGGT_WEIGHTS = "facebook/VGGT-1B"
DEFAULT_VSWHERE_PATH = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
DEFAULT_VS_ROOT = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools")
DEFAULT_BLENDER_PATHS = [
    Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"),
]


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _read_direct_url(dist_name: str) -> dict[str, Any] | None:
    try:
        dist = importlib.metadata.distribution(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return None
    raw = dist.read_text("direct_url.json")
    if not raw:
        return None
    try:
        # JSON ingress — internal controlled payload from importlib.metadata distribution metadata (direct_url.json written by pip at install time); safe without schema validation.
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _run_command(args: list[str], *, timeout_s: int = 10) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "code": "not_found"}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": f"Timed out after {timeout_s}s", "code": "timeout", "stdout": exc.stdout, "stderr": exc.stderr}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _find_vswhere() -> str | None:
    direct = shutil.which("vswhere")
    if direct:
        return direct
    if DEFAULT_VSWHERE_PATH.exists():
        return str(DEFAULT_VSWHERE_PATH)
    return None


def _find_vs_tool(relative_path: str) -> str | None:
    candidate = DEFAULT_VS_ROOT / relative_path
    if candidate.exists():
        return str(candidate)
    return None


def _find_vs_msvc_tool(tool_name: str) -> str | None:
    base = DEFAULT_VS_ROOT / "VC" / "Tools" / "MSVC"
    if not base.exists():
        return None
    matches = sorted(base.glob(f"*/bin/Hostx64/x64/{tool_name}"), reverse=True)
    if matches:
        return str(matches[0])
    return None


def package_report(import_name: str, distribution_name: str | None = None) -> dict[str, Any]:
    distribution_name = distribution_name or import_name
    return {
        "import_name": import_name,
        "distribution_name": distribution_name,
        "available": _module_available(import_name),
        "version": _distribution_version(distribution_name),
    }


def editable_install_report(dist_name: str = "lathe") -> dict[str, Any]:
    direct_url = _read_direct_url(dist_name)
    editable = bool(direct_url and direct_url.get("dir_info", {}).get("editable"))
    url = direct_url.get("url") if direct_url else None
    return {
        "detected": direct_url is not None,
        "editable": editable,
        "url": url,
    }


def repo_install_report() -> dict[str, Any]:
    module_spec = importlib.util.find_spec("lathe")
    module_origin = module_spec.origin if module_spec else None
    source_root = None
    if module_origin:
        origin_path = Path(module_origin).resolve()
        for parent in [origin_path.parent, *origin_path.parents]:
            if (parent / "pyproject.toml").exists() and (parent / "lathe").exists():
                source_root = str(parent)
                break
    editable = editable_install_report("lathe")
    if source_root and not editable["editable"]:
        editable = {
            **editable,
            "detected": True,
            "editable": True,
            "url": source_root,
        }
    return {
        "importable": module_spec is not None,
        "module_origin": module_origin,
        "editable_install": editable,
    }


def environment_report() -> dict[str, Any]:
    venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    shell = os.environ.get("SHELL")
    if not shell and os.environ.get("PSModulePath"):
        shell = "powershell"
    if not shell:
        shell = os.environ.get("ComSpec")
    return {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "platform": platform.platform(),
        },
        "shell": shell,
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "prefix": sys.prefix,
            "base_prefix": getattr(sys, "base_prefix", sys.prefix),
            "venv_active": venv,
            "virtual_env": os.environ.get("VIRTUAL_ENV"),
            "conda_prefix": os.environ.get("CONDA_PREFIX"),
        },
        "commands": {
            "python": shutil.which("python"),
            "py": shutil.which("py"),
            "pip": shutil.which("pip"),
            "git": shutil.which("git"),
            "bash": shutil.which("bash"),
            "powershell": shutil.which("powershell"),
            "pwsh": shutil.which("pwsh"),
            "winget": shutil.which("winget"),
            "choco": shutil.which("choco"),
            "scoop": shutil.which("scoop"),
            "vswhere": _find_vswhere(),
            "cl": shutil.which("cl") or _find_vs_msvc_tool("cl.exe"),
            "nmake": shutil.which("nmake") or _find_vs_msvc_tool("nmake.exe"),
            "cmake": shutil.which("cmake") or _find_vs_tool(r"Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"),
            "vsdevcmd": _find_vs_tool(r"Common7\Tools\VsDevCmd.bat"),
            "nvidia-smi": shutil.which("nvidia-smi"),
        },
    }


def _candidate_blender_paths(runtime_config: dict[str, Any] | None = None) -> list[Path]:
    topology_cfg = ((runtime_config or {}).get("topology", {}).get("blender", {}))
    execution_cfg = ((runtime_config or {}).get("execution", {}).get("blender", {}))
    override = execution_cfg.get("path") or topology_cfg.get("path")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(str(override)))
    which_blender = shutil.which("blender")
    if which_blender:
        candidates.append(Path(which_blender))
    candidates.extend(DEFAULT_BLENDER_PATHS)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def probe_blender(runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    execution_cfg = ((runtime_config or {}).get("execution", {}).get("blender", {}))
    python_module_available = _module_available("bpy")
    asset_libraries = [
        {"path": str(p), "available": Path(p).exists()}
        for p in execution_cfg.get("asset_libraries", [])
    ]
    addons = [{"name": str(name), "declared": True} for name in execution_cfg.get("addons", [])]
    supported_modes = ["background_cli"] + (["python_module"] if python_module_available else [])
    base = {
        "python_module_available": python_module_available,
        "supported_modes": supported_modes,
        "asset_libraries": asset_libraries,
        "addons": addons,
    }
    for candidate in _candidate_blender_paths(runtime_config):
        if not candidate.exists():
            continue
        result = _run_command([str(candidate), "--version"], timeout_s=15)
        if not result["ok"]:
            return {
                **base,
                "available": False,
                "path": str(candidate),
                "code": result.get("code", "version_failed"),
                "message": result.get("error") or result.get("stderr") or "Failed to query Blender version",
            }
        first_line = next((line.strip() for line in result.get("stdout", "").splitlines() if line.strip()), "")
        version = first_line.replace("Blender", "", 1).strip() if first_line.lower().startswith("blender") else first_line
        return {
            **base,
            "available": True,
            "path": str(candidate),
            "version": version or None,
            "gpu_cpu_render_capability": execution_cfg.get("render_device", "cpu"),
            "export_capabilities": {"usd": True, "glb": True, "gltf": True, "obj": True},
            "code": "ok",
        }
    return {
        **base,
        "available": False,
        "path": None,
        "code": "not_found",
        "message": "Blender executable not found on PATH or common install locations",
    }


def probe_xatlas() -> dict[str, Any]:
    env_commands = environment_report()["commands"]
    report = package_report("xatlas")
    if report["available"]:
        return {
            "available": True,
            "version": report["version"],
            "code": "ok",
        }
    return {
        "available": False,
        "version": None,
        "code": "not_installed",
        "message": "Python xatlas bindings are not installed",
        "build_tools": {
            "nmake": env_commands.get("nmake"),
            "cmake": env_commands.get("cmake"),
            "cl": env_commands.get("cl"),
            "vsdevcmd": env_commands.get("vsdevcmd"),
        },
    }


def probe_torch() -> dict[str, Any]:
    base_unavailable = {"available": False, "cuda_available": False, "cuda_version": None, "devices": []}
    if not _module_available("torch"):
        return {**base_unavailable, "version": None, "code": "not_installed", "message": "torch is not installed"}
    try:
        import torch
    except (ImportError, OSError, RuntimeError) as exc:
        # OSError covers DLL/shared-lib load failures; RuntimeError covers torch's
        # C-extension init errors (e.g., CUDA init) that surface at import.
        return {**base_unavailable, "version": _distribution_version("torch"), "code": "import_failed", "message": str(exc)}

    cuda_available = bool(torch.cuda.is_available())
    devices: list[dict[str, Any]] = []
    if cuda_available:
        for index in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(index)
            devices.append({
                "index": index,
                "name": props.name,
                "total_memory_bytes": int(props.total_memory),
                "compute_capability": f"{props.major}.{props.minor}",
            })
    return {
        "available": True,
        "version": getattr(torch, "__version__", _distribution_version("torch")),
        "cuda_available": cuda_available,
        "cuda_version": getattr(getattr(torch, "version", None), "cuda", None),
        "devices": devices,
        "code": "ok",
    }


def probe_nvidia_smi() -> dict[str, Any]:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {"available": False, "code": "not_found"}
    result = _run_command([nvidia_smi], timeout_s=15)
    if not result["ok"]:
        return {"available": False, "code": result.get("code", "failed"), "message": result.get("error") or result.get("stderr")}
    lines = [line.rstrip() for line in result.get("stdout", "").splitlines() if line.strip()]
    return {
        "available": True,
        "code": "ok",
        "summary": lines[0] if lines else None,
    }


def probe_vggt(runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    torch_report = probe_torch()
    cfg = ((runtime_config or {}).get("shape", {}).get("providers", {}).get("vggt_local", {}))
    weights = str(cfg.get("weights", DEFAULT_VGGT_WEIGHTS))
    device_requested = str(cfg.get("device", "auto"))
    vggt_available = _module_available("vggt")
    torchvision_available = _module_available("torchvision")
    issues: list[str] = []
    warnings: list[str] = []

    if not torch_report["available"]:
        issues.append("torch is not installed")
    if not torchvision_available:
        issues.append("torchvision is not installed")
    if not vggt_available:
        issues.append("vggt package is not installed")

    weights_path = Path(weights)
    if any(sep in weights for sep in ("/", "\\")) and weights_path.suffix and not weights_path.exists():
        issues.append(f"weights path does not exist: {weights}")

    selected_device = device_requested
    if device_requested == "auto":
        selected_device = "cuda" if torch_report.get("cuda_available") else "cpu"
    if selected_device == "cuda" and not torch_report.get("cuda_available"):
        issues.append("CUDA device requested but torch.cuda.is_available() is false")
    if selected_device == "cpu":
        warnings.append("VGGT can run on CPU but will be significantly slower")

    available = not issues
    return {
        "available": available,
        "version": _distribution_version("vggt"),
        "weights": weights,
        "device_requested": device_requested,
        "selected_device": selected_device,
        "cuda_available": bool(torch_report.get("cuda_available")),
        "torchvision_available": torchvision_available,
        "issues": issues,
        "warnings": warnings,
        "code": "ok" if available else "unavailable",
    }


def probe_hunyuan_endpoint(runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    provider_cfg = ((runtime_config or {}).get("shape", {}).get("providers", {}).get("hunyuan2_1_http", {}))
    base_url = str(provider_cfg.get("base_url", DEFAULT_HUNYUAN_BASE_URL)).rstrip("/")
    configured_timeout = float(provider_cfg.get("health_timeout_s", 5))
    timeout_s = min(configured_timeout if configured_timeout > 0 else _HUNYUAN_PROBE_MAX_TIMEOUT_S, _HUNYUAN_PROBE_MAX_TIMEOUT_S)
    if not base_url:
        return {"configured": False, "available": False, "code": "missing_base_url"}

    base = {"configured": True, "available": False, "base_url": base_url}
    try:
        response = safe_urlopen(
            base_url + "/health",
            method="GET",
            timeout_s=timeout_s,
            max_bytes=_HUNYUAN_PROBE_MAX_BODY_BYTES,
            expect_content_type=("application/json", "text/json"),
        )
    except NetGuardError as exc:
        probe_code = _NETGUARD_TO_PROBE_CODE.get(exc.code, "request_failed")
        result: dict[str, Any] = {**base, "code": probe_code, "message": str(exc)}
        if probe_code == "unexpected_content_type" and isinstance(exc.details, dict):
            status = exc.details.get("status")
            if status is not None:
                result["status"] = status
        return result
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read(_HUNYUAN_PROBE_MAX_BODY_BYTES).decode("utf-8", errors="replace")
        except (OSError, AttributeError, ValueError):
            error_body = ""
        return {**base, "status": exc.code, "code": "http_error", "message": error_body}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {**base, "code": "request_failed", "message": str(exc)}

    body = response.body.decode("utf-8", errors="replace")
    if body.strip().startswith(("{", "[")):
        try:
            payload = validate_json_bytes(
                body,
                "hunyuan_probe",
                source=base_url + "/health",
                max_bytes=_HUNYUAN_PROBE_MAX_BODY_BYTES,
            )
        except LatheConfigError as exc:
            return {**base, "status": response.status, "code": "invalid_health_payload", "message": str(exc)}
        if not isinstance(payload, dict):
            payload = {"raw": body[:_HUNYUAN_PROBE_MAX_BODY_BYTES]}
    else:
        payload = {"raw": body}
    return {**base, "available": True, "status": response.status, "code": "ok", "health": payload}


def _backend_report(
    runtime_config: dict[str, Any] | None,
    cfg_key: str,
    backend_id: str,
    real: str,
    real_aliases: set[str],
    fallback: str,
    fallback_aliases: set[str],
    probe: dict[str, Any],
) -> dict[str, Any]:
    cfg = (runtime_config or {}).get(cfg_key, {})
    requested = str(cfg.get("adapter", "auto") or "auto")
    strict = bool(cfg.get("strict", False))
    if requested in fallback_aliases:
        selected = fallback
    elif requested in ({"auto"} | real_aliases) and probe["available"]:
        selected = real
    else:
        selected = fallback
    return {
        "backend_id": backend_id,
        "requested_adapter": requested,
        "selected_adapter": selected,
        "strict": strict,
        "available": selected != real or probe["available"] or not strict,
        "real_adapter_available": bool(probe["available"]),
        "fallback_available": True,
        "probe": probe,
    }


def probe_topology_backend(runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return _backend_report(
        runtime_config, "topology", "lathe.topology.blender_hard_surface_v1",
        "blender_subprocess", {"blender"},
        "reference_cleanup", {"cleanup", "reference_cleanup"},
        probe_blender(runtime_config),
    )


def probe_uv_backend(runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return _backend_report(
        runtime_config, "uv", "lathe.uv.xatlas_v1",
        "xatlas", {"xatlas"},
        "reference_box", {"box", "reference_box"},
        probe_xatlas(),
    )


def deterministic_backend_reports(runtime_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [
        probe_topology_backend(runtime_config),
        probe_uv_backend(runtime_config),
        {
            "backend_id": "lathe.package.openusd_gltf_v1",
            "requested_adapter": "builtin",
            "selected_adapter": "reference_package",
            "strict": False,
            "available": True,
            "real_adapter_available": True,
            "fallback_available": False,
            "probe": {"available": True, "code": "ok"},
        },
    ]
