from __future__ import annotations

import json
import os
import warnings
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema


_MAX_CONFIG_BYTES = 256 * 1024
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "runtime_config.schema.json"
_SCHEMA_CACHE: dict[str, Any] | None = None
_VALIDATOR_CACHE: jsonschema.Draft202012Validator | None = None


class RuntimeConfigError(RuntimeError):
    """Raised when a user-supplied runtime config is malformed or fails schema validation.

    Re-homed under LatheError in Stage 2.V.
    """


def _load_schema() -> jsonschema.Draft202012Validator:
    global _SCHEMA_CACHE, _VALIDATOR_CACHE
    if _VALIDATOR_CACHE is not None:
        return _VALIDATOR_CACHE
    try:
        schema_text = _SCHEMA_PATH.read_text(encoding="utf-8")
        _SCHEMA_CACHE = json.loads(schema_text)
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeConfigError(
            f"runtime_config schema at {_SCHEMA_PATH} could not be loaded: {exc}"
        ) from exc
    _VALIDATOR_CACHE = jsonschema.Draft202012Validator(_SCHEMA_CACHE)
    return _VALIDATOR_CACHE


def _format_pointer(path_deque: Any) -> str:
    parts = [str(p) for p in path_deque]
    return "/" + "/".join(parts) if parts else "/"


def _collect_unknown_keys(raw: Any, schema: Any, prefix: str = "") -> list[str]:
    # Walk raw against schema, collecting keys not declared in `properties` for objects whose
    # schema documents a properties block. We treat missing schema sub-nodes as "unconstrained"
    # and do not report under them.
    unknown: list[str] = []
    if not isinstance(raw, dict) or not isinstance(schema, dict):
        return unknown
    properties = schema.get("properties") or {}
    if properties:
        for key, value in raw.items():
            path = f"{prefix}/{key}" if prefix else f"/{key}"
            if key not in properties:
                unknown.append(path)
            else:
                unknown.extend(_collect_unknown_keys(value, properties[key], path))
    else:
        for key, value in raw.items():
            path = f"{prefix}/{key}" if prefix else f"/{key}"
            unknown.extend(_collect_unknown_keys(value, {}, path))
    return unknown


def _validate_runtime_config(raw: dict[str, Any], source: str) -> None:
    validator = _load_schema()
    errors = sorted(validator.iter_errors(raw), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        pointer = _format_pointer(first.absolute_path)
        snippet = repr(first.instance)
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        raise RuntimeConfigError(
            f"runtime_config {source} failed schema validation at {pointer}: "
            f"{first.message} (value={snippet})"
        )
    unknown_keys = _collect_unknown_keys(raw, _SCHEMA_CACHE or {})
    if unknown_keys:
        warnings.warn(
            f"runtime_config {source} contains unknown keys (ignored, will become errors in a "
            f"future release): {', '.join(unknown_keys)}",
            stacklevel=3,
        )


DEFAULT_RUNTIME_CONFIG: dict[str, Any] = {
    "shape": {
        "provider": "auto",
        "strict": False,
        "providers": {},
    },
    "topology": {
        "adapter": "auto",
        "strict": False,
        "blender": {
            "path": None,
            "timeout_s": 300,
        },
    },
    "uv": {
        "adapter": "auto",
        "strict": False,
        "xatlas": {
            "resolution": 2048,
        },
    },
    "surface": {
        "codex_imagegen": {
            "mode": "fallback_deterministic",
            "request_dir": "imagegen_requests",
            "output_dir": "imagegen_outputs",
        },
    },
    "execution": {
        "blender": {
            "path": None,
            "strict": False,
            "allow_autoexec": False,
            "trusted": False,
            "preserve_blend": "on_failure",
            "asset_libraries": [],
            "addons": [],
            "render_device": "cpu",
        },
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def load_runtime_config(path: str | Path | None = None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_RUNTIME_CONFIG)
    if path is not None:
        config_path = Path(path)
        try:
            stat_result = config_path.stat()
        except FileNotFoundError as exc:
            raise RuntimeConfigError(f"runtime_config file not found: {config_path}") from exc
        except OSError as exc:
            raise RuntimeConfigError(
                f"runtime_config file could not be stat'd ({config_path}): {exc}"
            ) from exc
        if stat_result.st_size > _MAX_CONFIG_BYTES:
            raise RuntimeConfigError(
                f"runtime_config file exceeds 256 KiB "
                f"({stat_result.st_size} bytes > {_MAX_CONFIG_BYTES}): {config_path}"
            )
        try:
            text = config_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RuntimeConfigError(f"runtime_config file not found: {config_path}") from exc
        except UnicodeDecodeError as exc:
            raise RuntimeConfigError(
                f"runtime_config file is not valid UTF-8 ({config_path}): {exc}"
            ) from exc
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeConfigError(
                f"runtime_config file contains invalid JSON ({config_path}): "
                f"{exc.msg} at line {exc.lineno}, column {exc.colno}"
            ) from exc
        if not isinstance(raw, dict):
            raise RuntimeConfigError(
                f"runtime_config root must be a JSON object, got {type(raw).__name__} "
                f"({config_path})"
            )
        _validate_runtime_config(raw, source=str(config_path))
        config = _deep_merge(config, raw)
    return apply_env_overrides(config)


def merge_runtime_config(base: dict[str, Any] | None, override: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_RUNTIME_CONFIG)
    if base:
        merged = _deep_merge(merged, base)
    if override:
        merged = _deep_merge(merged, override)
    return apply_env_overrides(merged)


def apply_cli_overrides(
    config: dict[str, Any] | None,
    *,
    shape_provider: str | None = None,
    shape_strict: bool | None = None,
    codex_imagegen: str | None = None,
) -> dict[str, Any]:
    merged = merge_runtime_config(config, None)
    shape = merged.setdefault("shape", {})
    if shape_provider:
        shape["provider"] = shape_provider
    if shape_strict is not None:
        shape["strict"] = bool(shape_strict)
    if codex_imagegen:
        surface = merged.setdefault("surface", {})
        imagegen = surface.setdefault("codex_imagegen", {})
        imagegen["mode"] = codex_imagegen
    return merged


def apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(config)
    shape = merged.setdefault("shape", {})
    providers = shape.setdefault("providers", {})

    provider = os.getenv("LATHE_SHAPE_PROVIDER")
    if provider:
        shape["provider"] = provider

    strict = os.getenv("LATHE_SHAPE_STRICT")
    if strict is not None:
        shape["strict"] = strict.lower() in {"1", "true", "yes", "on"}

    hunyuan_base = os.getenv("LATHE_HUNYUAN_BASE_URL")
    if hunyuan_base:
        provider_cfg = providers.setdefault("hunyuan2_1_http", {})
        provider_cfg["base_url"] = hunyuan_base

    vggt_weights = os.getenv("LATHE_VGGT_WEIGHTS")
    if vggt_weights:
        provider_cfg = providers.setdefault("vggt_local", {})
        provider_cfg["weights"] = vggt_weights

    vggt_device = os.getenv("LATHE_VGGT_DEVICE")
    if vggt_device:
        provider_cfg = providers.setdefault("vggt_local", {})
        provider_cfg["device"] = vggt_device

    topology = merged.setdefault("topology", {})
    blender_cfg = topology.setdefault("blender", {})
    execution = merged.setdefault("execution", {})
    execution_blender = execution.setdefault("blender", {})

    topology_adapter = os.getenv("LATHE_TOPOLOGY_ADAPTER")
    if topology_adapter:
        topology["adapter"] = topology_adapter

    topology_strict = os.getenv("LATHE_TOPOLOGY_STRICT")
    if topology_strict is not None:
        topology["strict"] = topology_strict.lower() in {"1", "true", "yes", "on"}

    blender_path = os.getenv("LATHE_BLENDER_PATH")
    if blender_path:
        blender_cfg["path"] = blender_path
        execution_blender["path"] = blender_path

    uv = merged.setdefault("uv", {})
    xatlas_cfg = uv.setdefault("xatlas", {})

    uv_adapter = os.getenv("LATHE_UV_ADAPTER")
    if uv_adapter:
        uv["adapter"] = uv_adapter

    uv_strict = os.getenv("LATHE_UV_STRICT")
    if uv_strict is not None:
        uv["strict"] = uv_strict.lower() in {"1", "true", "yes", "on"}

    xatlas_resolution = os.getenv("LATHE_XATLAS_RESOLUTION")
    if xatlas_resolution:
        try:
            xatlas_cfg["resolution"] = int(xatlas_resolution)
        except ValueError:
            pass

    surface = merged.setdefault("surface", {})
    imagegen = surface.setdefault("codex_imagegen", {})
    codex_imagegen_mode = os.getenv("LATHE_CODEX_IMAGEGEN")
    if codex_imagegen_mode:
        imagegen["mode"] = codex_imagegen_mode

    execution_strict = os.getenv("LATHE_EXECUTION_BLENDER_STRICT")
    if execution_strict is not None:
        execution_blender["strict"] = execution_strict.lower() in {"1", "true", "yes", "on"}

    return merged
