from __future__ import annotations

import base64
import importlib.util
import json
import math
import time
import urllib.error
import urllib.request
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import trimesh
from PIL import Image

from .capabilities import probe_hunyuan_endpoint as _probe_hunyuan_endpoint
from .capabilities import probe_vggt as _probe_vggt


PROVIDER_ALIASES = {
    "auto": "auto",
    "reference_conditioned": "lathe.provider.shape.reference_conditioned_v1",
    "hunyuan2_1_http": "lathe.provider.shape.hunyuan2_1_http_v1",
    "vggt_local": "lathe.provider.shape.vggt_local_v1",
}


PROVIDERS: dict[str, dict[str, Any]] = {
    "lathe.provider.shape.reference_conditioned_v1": {
        "id": "lathe.provider.shape.reference_conditioned_v1",
        "version": "1.0.0",
        "learned": False,
        "modes": ["generate", "reconstruct", "adapt", "assemble"],
        "summary": "Built-in heuristic fallback shape provider.",
    },
    "lathe.provider.shape.hunyuan2_1_http_v1": {
        "id": "lathe.provider.shape.hunyuan2_1_http_v1",
        "version": "1.0.0",
        "learned": True,
        "modes": ["generate", "reconstruct"],
        "summary": "Official Hunyuan3D-2.1 FastAPI server bridge for image-conditioned mesh generation.",
        "config": {
            "base_url": "http://localhost:8081",
            "remove_background": True,
            "texture": False,
            "octree_resolution": 256,
            "num_inference_steps": 5,
            "guidance_scale": 5.0,
            "num_chunks": 8000,
            "face_count": 40000,
            "type": "glb",
            "request_timeout_s": 600,
            "health_timeout_s": 5,
            "max_retries": 2,
            "retry_backoff_s": 1.0,
        },
    },
    "lathe.provider.shape.vggt_local_v1": {
        "id": "lathe.provider.shape.vggt_local_v1",
        "version": "1.0.0",
        "learned": True,
        "modes": ["reconstruct"],
        "summary": "Official local VGGT package bridge for multiview geometric reconstruction followed by deterministic meshing.",
        "config": {
            "weights": "facebook/VGGT-1B",
            "device": "auto",
            "dtype": "auto",
            "max_views": 8,
            "stride": 8,
            "min_confidence": 0.20,
            "max_edge_ratio": 6.0,
            "candidate_variants": 2,
            "use_point_head": False,
        },
    },
}


class ShapeProviderError(RuntimeError):
    def __init__(self, provider_id: str, message: str, *, code: str = "provider_error", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.code = code
        self.details = details or {}


class ShapeProviderUnavailable(ShapeProviderError):
    pass


class ShapeProviderExecutionError(ShapeProviderError):
    pass


def _deepcopy(obj: Any) -> Any:
    return deepcopy(obj)


def normalize_provider_id(provider: str | None) -> str:
    if not provider:
        return "auto"
    return PROVIDER_ALIASES.get(provider, provider)


def list_shape_providers() -> list[dict[str, Any]]:
    return [_deepcopy(PROVIDERS[key]) for key in sorted(PROVIDERS)]


def get_provider(provider_id: str) -> dict[str, Any]:
    provider_id = normalize_provider_id(provider_id)
    if provider_id not in PROVIDERS:
        raise ShapeProviderError(provider_id, f"Unknown shape provider '{provider_id}'", code="unknown_provider")
    return _deepcopy(PROVIDERS[provider_id])


def provider_config(runtime_config: dict[str, Any] | None, provider_id: str) -> dict[str, Any]:
    provider = get_provider(provider_id)
    defaults = provider.get("config", {})
    shape_cfg = (runtime_config or {}).get("shape", {})
    providers = shape_cfg.get("providers", {})
    merged = _deepcopy(defaults)
    for key in {provider_id, _short_provider_name(provider_id)}:
        if key in providers and isinstance(providers[key], dict):
            merged.update(_deepcopy(providers[key]))
    return merged


def resolve_shape_provider(asset: dict[str, Any], conditioning: dict[str, Any], runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    mode = asset.get("build", {}).get("shape", {}).get("mode", "generate")
    shape_cfg = (runtime_config or {}).get("shape", {})
    explicit = normalize_provider_id(shape_cfg.get("provider", "auto"))
    strict = bool(shape_cfg.get("strict", False))
    configured_providers = shape_cfg.get("providers", {})
    auto_learned_requested = bool(configured_providers)

    if explicit != "auto":
        provider = get_provider(explicit)
        return {
            "provider": provider,
            "config": provider_config(runtime_config, explicit),
            "selected_via": "explicit",
            "strict": strict,
        }

    if not auto_learned_requested:
        provider = get_provider("reference_conditioned")
        return {
            "provider": provider,
            "config": provider_config(runtime_config, provider["id"]),
            "selected_via": "default_fallback",
            "strict": strict,
        }

    image_refs = _non_material_image_refs(conditioning)
    if mode == "reconstruct" and len(image_refs) >= 2:
        provider = get_provider("vggt_local")
        return {
            "provider": provider,
            "config": provider_config(runtime_config, provider["id"]),
            "selected_via": "auto_multiview",
            "strict": strict,
        }
    if mode in {"generate", "reconstruct"} and image_refs:
        provider = get_provider("hunyuan2_1_http")
        return {
            "provider": provider,
            "config": provider_config(runtime_config, provider["id"]),
            "selected_via": "auto_image",
            "strict": strict,
        }
    provider = get_provider("reference_conditioned")
    return {
        "provider": provider,
        "config": provider_config(runtime_config, provider["id"]),
        "selected_via": "auto_fallback",
        "strict": strict,
    }


def probe_shape_provider(provider_id: str, runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    provider = get_provider(provider_id)
    config = provider_config(runtime_config, provider["id"])
    try:
        if provider["id"] == "lathe.provider.shape.hunyuan2_1_http_v1":
            probe = _probe_hunyuan_endpoint(
                {
                    "shape": {
                        "providers": {
                            "hunyuan2_1_http": config,
                        }
                    }
                }
            )
            if not probe.get("available", False):
                raise ShapeProviderUnavailable(
                    provider["id"],
                    probe.get("message", "Hunyuan health probe failed"),
                    code=probe.get("code", "probe_failed"),
                    details=probe,
                )
            return {"available": True, "provider_id": provider["id"], "details": probe}
        if provider["id"] == "lathe.provider.shape.vggt_local_v1":
            probe = _probe_vggt(
                {
                    "shape": {
                        "providers": {
                            "vggt_local": config,
                        }
                    }
                }
            )
            if not probe.get("available", False):
                raise ShapeProviderUnavailable(
                    provider["id"],
                    "; ".join(probe.get("issues", [])) or "VGGT runtime unavailable",
                    code=probe.get("code", "probe_failed"),
                    details=probe,
                )
            return {"available": True, "provider_id": provider["id"], "details": probe}
        return {"available": True, "provider_id": provider["id"], "details": {}}
    except ShapeProviderError as exc:
        return {"available": False, "provider_id": provider["id"], "code": exc.code, "message": str(exc), "details": exc.details}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {"available": False, "provider_id": provider["id"], "code": "probe_failed", "message": str(exc), "details": {}}


def probe_all_shape_providers(runtime_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    reports = []
    for provider in list_shape_providers():
        reports.append(probe_shape_provider(provider["id"], runtime_config))
    return reports


def maybe_run_shape_provider(
    asset: dict[str, Any],
    *,
    source_root: Path,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    work_dir: Path,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selection = resolve_shape_provider(asset, conditioning, runtime_config)
    provider = selection["provider"]
    provider_id = provider["id"]
    fallback_provider = get_provider("reference_conditioned")
    report = {
        "selected_provider_id": provider_id,
        "selected_provider_version": provider["version"],
        "actual_provider_id": provider_id,
        "actual_provider_version": provider["version"],
        "selected_via": selection["selected_via"],
        "strict": selection["strict"],
        "learned": bool(provider.get("learned", False)),
        "status": "selected",
        "probe": probe_shape_provider(provider_id, runtime_config),
        "config": _redact_provider_config(provider_id, selection["config"]),
    }
    if provider_id == "lathe.provider.shape.reference_conditioned_v1":
        report["status"] = "fallback"
        return {"provider_report": report, "runtime_candidates": None}

    if not report["probe"].get("available", False):
        message = f"Selected shape provider '{provider_id}' is unavailable: {report['probe'].get('message', 'unknown error')}"
        if selection["strict"]:
            raise ShapeProviderUnavailable(provider_id, message, code=report["probe"].get("code", "provider_unavailable"), details=report["probe"])
        report["status"] = "fallback"
        report["fallback_reason"] = message
        report["actual_provider_id"] = fallback_provider["id"]
        report["actual_provider_version"] = fallback_provider["version"]
        return {"provider_report": report, "runtime_candidates": None}

    try:
        if provider_id == "lathe.provider.shape.hunyuan2_1_http_v1":
            provider_result = _run_hunyuan_http_provider(
                asset,
                seed=seed,
                candidates_count=candidates_count,
                conditioning=conditioning,
                work_dir=work_dir,
                config=selection["config"],
            )
        elif provider_id == "lathe.provider.shape.vggt_local_v1":
            provider_result = _run_vggt_local_provider(
                asset,
                candidates_count=candidates_count,
                conditioning=conditioning,
                config=selection["config"],
            )
        else:
            raise ShapeProviderExecutionError(provider_id, f"No executor implemented for provider '{provider_id}'", code="not_implemented")
    except ShapeProviderError as exc:
        if selection["strict"]:
            raise
        report["status"] = "fallback"
        report["fallback_reason"] = str(exc)
        report["error"] = {"provider_id": exc.provider_id, "code": exc.code, "details": exc.details}
        report["actual_provider_id"] = fallback_provider["id"]
        report["actual_provider_version"] = fallback_provider["version"]
        return {"provider_report": report, "runtime_candidates": None}

    candidates = provider_result["candidates"]
    report["execution"] = provider_result.get("execution", {})
    report["status"] = "success"
    report["candidate_count"] = len(candidates)
    return {"provider_report": report, "runtime_candidates": candidates}


def _short_provider_name(provider_id: str) -> str:
    if provider_id.startswith("lathe.provider.shape.") and provider_id.endswith("_v1"):
        return provider_id[len("lathe.provider.shape.") : -len("_v1")]
    return provider_id


def _redact_provider_config(provider_id: str, config: dict[str, Any]) -> dict[str, Any]:
    allowed = _deepcopy(config)
    if provider_id == "lathe.provider.shape.hunyuan2_1_http_v1":
        return {
            k: allowed.get(k)
            for k in [
                "base_url",
                "remove_background",
                "texture",
                "octree_resolution",
                "num_inference_steps",
                "guidance_scale",
                "face_count",
                "type",
                "request_timeout_s",
                "max_retries",
                "retry_backoff_s",
            ]
            if k in allowed
        }
    if provider_id == "lathe.provider.shape.vggt_local_v1":
        return {k: allowed.get(k) for k in ["weights", "device", "dtype", "max_views", "stride", "min_confidence", "max_edge_ratio", "candidate_variants", "use_point_head"] if k in allowed}
    return allowed


def _unit_to_cm(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "mm":
        return amount / 10.0
    if unit == "cm":
        return amount
    if unit == "m":
        return amount * 100.0
    return amount


def _characteristic_scale_cm(asset: dict[str, Any]) -> float:
    intent = asset.get("intent", {})
    if "dimensions" in intent and isinstance(intent["dimensions"], dict) and intent["dimensions"].get("type") == "call":
        args = intent["dimensions"].get("args", [])
        values = [_unit_to_cm(item["value"]) for item in args if isinstance(item, dict) and item.get("value") is not None]
        if values:
            return max(values)
    if "scale" in intent:
        return max(1.0, _unit_to_cm(intent["scale"]))
    return 200.0 if asset.get("kind") == "env_module" else 100.0


def _make_color(name: str) -> tuple[int, int, int]:
    digest = np.frombuffer(np.frombuffer(name.encode("utf-8"), dtype=np.uint8).tobytes(), dtype=np.uint8)
    total = int(digest.sum()) if len(digest) else 0
    return (80 + total % 140, 80 + (total * 3) % 140, 80 + (total * 7) % 140)


def _root_name(parts: list[str]) -> str:
    body_names = [name for name in parts if any(token in name for token in ("body", "hull", "core", "base"))]
    return body_names[0] if body_names else (parts[0] if parts else "body")


def _conditioned_part_colors(parts: list[str], conditioning: dict[str, Any]) -> dict[str, tuple[int, int, int]]:
    palette = conditioning.get("palette", [])
    brightness = conditioning.get("material_brightness")
    out: dict[str, tuple[int, int, int]] = {}
    palette_index = 0
    for part in parts:
        lname = part.lower()
        if any(token in lname for token in ("glass", "camera", "sensor", "gimbal")):
            out[part] = (214, 148, 72)
            continue
        if any(token in lname for token in ("rotor", "fan", "prop")):
            out[part] = (72, 76, 84)
            continue
        if palette:
            rgb = palette[min(palette_index, len(palette) - 1)]
            palette_index += 1
            color = [int(v) for v in rgb]
            if brightness is not None and brightness < 0.45:
                color = [max(45, int(v * 0.9)) for v in color]
            out[part] = tuple(color)
            continue
        out[part] = _make_color(part)
    return out


def _normalize_mesh_to_scale(mesh: trimesh.Trimesh, target_extent_cm: float) -> trimesh.Trimesh:
    mesh = mesh.copy()
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    bounds = mesh.bounds
    center = (bounds[0] + bounds[1]) / 2.0
    mesh.apply_translation(-center)
    extents = mesh.extents
    max_extent = max(1e-6, float(max(extents)))
    mesh.apply_scale(float(target_extent_cm) / max_extent)
    return mesh


def _load_mesh_file(path: Path) -> trimesh.Trimesh | None:
    try:
        loaded = trimesh.load(path, force="scene")
    except Exception:  # noqa: BLE001
        return None
    if isinstance(loaded, trimesh.Scene):
        meshes = [geom.copy() for geom in loaded.geometry.values() if isinstance(geom, trimesh.Trimesh)]
        if not meshes:
            return None
        return trimesh.util.concatenate(meshes)
    if isinstance(loaded, trimesh.Trimesh):
        return loaded.copy()
    return None


def _non_material_image_refs(conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in conditioning.get("image_refs", []) if item.get("kind") != "material"]


def _select_primary_image(conditioning: dict[str, Any]) -> Path:
    image_refs = _non_material_image_refs(conditioning)
    if not image_refs:
        raise ShapeProviderExecutionError("lathe.provider.shape.hunyuan2_1_http_v1", "No non-material reference image is available", code="missing_image_ref")
    return Path(image_refs[0]["path"])


def _mesh_quality_score(mesh: trimesh.Trimesh) -> float:
    score = 0.78
    if mesh.is_watertight:
        score += 0.08
    if len(mesh.faces) > 0:
        score += 0.04
    if len(mesh.vertices) > 0:
        score += 0.04
    body_count = _mesh_body_count(mesh)
    if body_count >= 1:
        score += 0.03
    if len(mesh.faces) > 60000:
        score -= 0.05
    return max(0.35, min(0.98, round(score, 6)))


def _mesh_body_count(mesh: trimesh.Trimesh) -> int:
    try:
        return int(mesh.body_count)
    except Exception:  # noqa: BLE001
        faces = np.asarray(mesh.faces, dtype=np.int64)
        if len(faces) == 0:
            return 0
        vertex_to_faces: dict[int, list[int]] = {}
        for face_index, face in enumerate(faces):
            for vertex in face:
                vertex_to_faces.setdefault(int(vertex), []).append(face_index)
        visited = np.zeros(len(faces), dtype=bool)
        body_count = 0
        for start in range(len(faces)):
            if visited[start]:
                continue
            body_count += 1
            stack = [start]
            visited[start] = True
            while stack:
                face_index = stack.pop()
                for vertex in faces[face_index]:
                    for neighbor in vertex_to_faces[int(vertex)]:
                        if not visited[neighbor]:
                            visited[neighbor] = True
                            stack.append(neighbor)
        return int(body_count)


def _runtime_from_mesh(
    asset: dict[str, Any],
    mesh: trimesh.Trimesh,
    conditioning: dict[str, Any],
    *,
    provider_id: str,
    notes: list[str],
    candidate_index: int,
    provider_bias: float = 0.0,
    units: str = "cm",
    score_override: float | None = None,
) -> dict[str, Any]:
    parts = list(asset.get("intent", {}).get("parts", [])) or ["body"]
    root = _root_name(parts)
    mesh = _normalize_mesh_to_scale(mesh, _characteristic_scale_cm(asset))
    face_parts = [root] * int(len(mesh.faces))
    part_colors = _conditioned_part_colors(parts, conditioning)
    score = score_override if score_override is not None else round(min(0.99, _mesh_quality_score(mesh) + provider_bias - 0.01 * candidate_index), 6)
    return {
        "mesh": mesh,
        "face_parts": face_parts,
        "part_colors": part_colors,
        "units": units,
        "meta": {
            "parts": [root],
            "declared_parts": parts,
            "coarse_material_slots": 1,
            "score": score,
            "selection_notes": notes,
            "conditioning": {
                "provider": provider_id,
                "reference_strength": conditioning.get("reference_strength", 0.0),
            },
        },
    }


def _hunyuan_transient_status(status: int) -> bool:
    return status in {408, 425, 429, 500, 502, 503, 504}


def _hunyuan_safe_text(payload: bytes, *, limit: int = 400) -> str:
    text = payload.decode("utf-8", errors="replace")
    return text[:limit]


def _hunyuan_request(
    provider_id: str,
    *,
    url: str,
    payload: dict[str, Any],
    timeout_s: int,
    max_retries: int,
    retry_backoff_s: float,
) -> tuple[bytes, dict[str, Any]]:
    encoded = json.dumps(payload).encode("utf-8")
    attempts: list[dict[str, Any]] = []
    for attempt_index in range(max_retries + 1):
        start = time.perf_counter()
        req = urllib.request.Request(url, data=encoded, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read()
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                status = getattr(resp, "status", 200)
                content_type = resp.headers.get("Content-Type")
                attempt_meta = {
                    "attempt": attempt_index + 1,
                    "status": status,
                    "content_type": content_type,
                    "elapsed_ms": elapsed_ms,
                }
                attempts.append(attempt_meta)
                if not raw:
                    raise ShapeProviderExecutionError(provider_id, "Provider response body was empty", code="empty_response", details={"attempts": attempts})
                if content_type and "json" in content_type.lower():
                    raise ShapeProviderExecutionError(
                        provider_id,
                        "Provider returned JSON instead of a mesh artifact",
                        code="unexpected_json_response",
                        details={**attempt_meta, "body": _hunyuan_safe_text(raw)},
                    )
                return raw, {"attempts": attempts, "final_attempt": attempt_meta}
        except urllib.error.HTTPError as exc:  # noqa: PERF203
            body = exc.read()
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            attempt_meta = {
                "attempt": attempt_index + 1,
                "status": exc.code,
                "elapsed_ms": elapsed_ms,
                "body": _hunyuan_safe_text(body),
            }
            attempts.append(attempt_meta)
            if _hunyuan_transient_status(exc.code) and attempt_index < max_retries:
                time.sleep(retry_backoff_s * (2**attempt_index))
                continue
            error_code = "auth_failed" if exc.code in {401, 403} else "http_error"
            raise ShapeProviderExecutionError(
                provider_id,
                f"Hunyuan generate request failed: HTTP {exc.code}",
                code=error_code,
                details={"status": exc.code, "body": attempt_meta["body"], "attempts": attempts},
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            attempts.append({"attempt": attempt_index + 1, "elapsed_ms": elapsed_ms, "error": str(exc)})
            if attempt_index < max_retries:
                time.sleep(retry_backoff_s * (2**attempt_index))
                continue
            raise ShapeProviderExecutionError(
                provider_id,
                f"Hunyuan generate request failed: {exc}",
                code="request_failed",
                details={"attempts": attempts},
            ) from exc

    raise ShapeProviderExecutionError(provider_id, "Hunyuan request exhausted retries", code="request_failed")


def _run_hunyuan_http_provider(
    asset: dict[str, Any],
    *,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    work_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    provider_id = "lathe.provider.shape.hunyuan2_1_http_v1"
    base_url = str(config.get("base_url", "")).rstrip("/")
    if not base_url:
        raise ShapeProviderExecutionError(provider_id, "Missing base_url for Hunyuan HTTP provider", code="missing_base_url")
    source_image = _select_primary_image(conditioning)
    image_b64 = base64.b64encode(source_image.read_bytes()).decode("ascii")
    out_type = str(config.get("type", "glb")).lower()
    if out_type not in {"glb", "obj"}:
        raise ShapeProviderExecutionError(provider_id, f"Unsupported output type '{out_type}'", code="unsupported_output_type")
    timeout = int(config.get("request_timeout_s", 600))
    max_retries = max(0, int(config.get("max_retries", 2)))
    retry_backoff_s = max(0.0, float(config.get("retry_backoff_s", 1.0)))

    candidates: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    for index in range(candidates_count):
        payload = {
            "image": image_b64,
            "remove_background": bool(config.get("remove_background", True)),
            "texture": bool(config.get("texture", False)),
            "seed": int(seed + index),
            "octree_resolution": int(config.get("octree_resolution", 256)),
            "num_inference_steps": int(config.get("num_inference_steps", 5)),
            "guidance_scale": float(config.get("guidance_scale", 5.0)),
            "num_chunks": int(config.get("num_chunks", 8000)),
            "face_count": int(config.get("face_count", 40000)),
            "type": out_type,
        }
        raw, response_meta = _hunyuan_request(
            provider_id,
            url=base_url + "/generate",
            payload=payload,
            timeout_s=timeout,
            max_retries=max_retries,
            retry_backoff_s=retry_backoff_s,
        )

        raw_path = work_dir / f"hunyuan_candidate_{index:02d}.{out_type}"
        raw_path.write_bytes(raw)
        mesh = _load_mesh_file(raw_path)
        if mesh is None or len(mesh.faces) == 0:
            raise ShapeProviderExecutionError(provider_id, "Provider response did not contain a valid mesh", code="invalid_mesh")
        notes = [
            "generated by Hunyuan3D-2.1 HTTP provider",
            f"source_image={source_image.name}",
            f"seed={payload['seed']}",
            f"resolution={payload['octree_resolution']}",
            f"steps={payload['num_inference_steps']}",
        ]
        candidates.append(
            _runtime_from_mesh(
                asset,
                mesh,
                conditioning,
                provider_id=provider_id,
                notes=notes,
                candidate_index=index,
                provider_bias=0.09,
            )
        )
        executions.append(
            {
                "candidate_index": index,
                "request": {
                    "source_image": source_image.name,
                    "seed": payload["seed"],
                    "output_type": out_type,
                    "octree_resolution": payload["octree_resolution"],
                    "num_inference_steps": payload["num_inference_steps"],
                    "guidance_scale": payload["guidance_scale"],
                    "face_count": payload["face_count"],
                    "texture": payload["texture"],
                    "remove_background": payload["remove_background"],
                },
                "response": {
                    "artifact_path": str(raw_path),
                    "artifact_size_bytes": raw_path.stat().st_size,
                    "attempts": response_meta["attempts"],
                    "final_attempt": response_meta["final_attempt"],
                },
            }
        )
    return {
        "candidates": candidates,
        "execution": {
            "mode": "http_generate",
            "base_url": base_url,
            "executions": executions,
        },
    }


def _run_vggt_local_provider(
    asset: dict[str, Any],
    *,
    candidates_count: int,
    conditioning: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    provider_id = "lathe.provider.shape.vggt_local_v1"
    image_paths = [Path(item["path"]) for item in _non_material_image_refs(conditioning)]
    max_views = int(config.get("max_views", 8))
    image_paths = image_paths[:max_views]
    if len(image_paths) < 2:
        raise ShapeProviderExecutionError(provider_id, "VGGT requires at least two non-material images", code="insufficient_views")

    try:
        import torch
        from vggt.models.vggt import VGGT
        from vggt.utils.geometry import unproject_depth_map_to_point_map
        from vggt.utils.load_fn import load_and_preprocess_images
        from vggt.utils.pose_enc import pose_encoding_to_extri_intri
    except Exception as exc:  # noqa: BLE001
        raise ShapeProviderUnavailable(provider_id, f"Failed to import VGGT runtime: {exc}", code="import_failed") from exc

    device = str(config.get("device", "auto"))
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    weights = str(config.get("weights", "facebook/VGGT-1B"))
    dtype_name = str(config.get("dtype", "auto"))

    if dtype_name == "auto":
        if device == "cuda":
            major = torch.cuda.get_device_capability()[0]
            autocast_dtype = torch.bfloat16 if major >= 8 else torch.float16
        else:
            autocast_dtype = torch.float32
    elif dtype_name == "bfloat16":
        autocast_dtype = torch.bfloat16
    elif dtype_name == "float16":
        autocast_dtype = torch.float16
    else:
        autocast_dtype = torch.float32

    model = VGGT.from_pretrained(weights).to(device)
    model.eval()
    images = load_and_preprocess_images([str(path) for path in image_paths]).to(device)
    images_batch = images[None]

    amp_ctx = torch.cuda.amp.autocast(dtype=autocast_dtype) if device == "cuda" else nullcontext()
    with torch.no_grad():
        with amp_ctx:
            aggregated_tokens_list, ps_idx = model.aggregator(images_batch)
            pose_enc = model.camera_head(aggregated_tokens_list)[-1]
            extrinsic, intrinsic = pose_encoding_to_extri_intri(pose_enc, images_batch.shape[-2:])
            depth_map, depth_conf = model.depth_head(aggregated_tokens_list, images_batch, ps_idx)
            point_map = unproject_depth_map_to_point_map(depth_map.squeeze(0), extrinsic.squeeze(0), intrinsic.squeeze(0))
            point_conf = depth_conf.squeeze(0)
            if bool(config.get("use_point_head", False)) and hasattr(model, "point_head"):
                point_map_alt, point_conf_alt = model.point_head(aggregated_tokens_list, images_batch, ps_idx)
                point_map_alt = point_map_alt.squeeze(0)
                point_conf_alt = point_conf_alt.squeeze(0)
            else:
                point_map_alt, point_conf_alt = None, None

    point_map_np = _to_point_map_numpy(point_map)
    point_conf_np = _to_conf_numpy(point_conf)
    point_map_alt_np = _to_point_map_numpy(point_map_alt) if point_map_alt is not None else None
    point_conf_alt_np = _to_conf_numpy(point_conf_alt) if point_conf_alt is not None else None

    stride = max(1, int(config.get("stride", 8)))
    min_conf = float(config.get("min_confidence", 0.20))
    max_edge_ratio = float(config.get("max_edge_ratio", 6.0))
    variant_count = max(1, int(config.get("candidate_variants", 2)))
    variant_specs: list[tuple[str, np.ndarray, np.ndarray, int, float]] = [
        ("depth_unprojection", point_map_np, point_conf_np, stride, min_conf),
    ]
    if point_map_alt_np is not None and point_conf_alt_np is not None:
        variant_specs.append(("point_head", point_map_alt_np, point_conf_alt_np, max(1, stride // 2), max(0.05, min_conf * 0.9)))
    variant_specs.append(("dense_unprojection", point_map_np, point_conf_np, max(1, stride // 2), max(0.05, min_conf * 0.8)))

    candidates: list[dict[str, Any]] = []
    attempted_variants: list[dict[str, Any]] = []
    used = 0
    for label, pm, cf, stride_variant, conf_variant in variant_specs:
        if used >= max(candidates_count, variant_count):
            break
        mesh = mesh_from_point_maps(pm, cf, image_paths=image_paths, stride=stride_variant, min_confidence=conf_variant, max_edge_ratio=max_edge_ratio)
        attempted_variants.append(
            {
                "label": label,
                "stride": stride_variant,
                "min_confidence": conf_variant,
                "produced_mesh": bool(mesh is not None and len(mesh.faces) > 0),
            }
        )
        if mesh is None or len(mesh.faces) == 0:
            continue
        score = round(min(0.99, _mesh_quality_score(mesh) + 0.08 - used * 0.015), 6)
        notes = [
            "reconstructed by VGGT local provider",
            f"views={len(image_paths)}",
            f"variant={label}",
            f"stride={stride_variant}",
            f"min_confidence={conf_variant}",
        ]
        candidates.append(
            _runtime_from_mesh(
                asset,
                mesh,
                conditioning,
                provider_id=provider_id,
                notes=notes,
                candidate_index=used,
                score_override=score,
            )
        )
        used += 1
    if not candidates:
        raise ShapeProviderExecutionError(provider_id, "VGGT reconstruction did not yield a mesh candidate", code="empty_reconstruction")
    return {
        "candidates": candidates[:candidates_count],
        "execution": {
            "mode": "local_vggt",
            "weights": weights,
            "selected_device": device,
            "dtype": str(autocast_dtype).replace("torch.", ""),
            "views": len(image_paths),
            "attempted_variants": attempted_variants,
        },
    }


def _to_point_map_numpy(value: Any) -> np.ndarray:
    if value is None:
        raise ValueError("Missing point map value")
    if hasattr(value, "detach"):
        value = value.detach().float().cpu().numpy()
    arr = np.asarray(value)
    if arr.ndim == 5 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim == 4 and arr.shape[1] == 3:  # [V,3,H,W]
        arr = np.transpose(arr, (0, 2, 3, 1))
    if arr.ndim != 4 or arr.shape[-1] != 3:
        raise ValueError(f"Unsupported point map shape {arr.shape!r}")
    return arr.astype(np.float32, copy=False)


def _to_conf_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().float().cpu().numpy()
    arr = np.asarray(value)
    if arr.ndim == 5 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim == 4 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim == 4 and arr.shape[-1] == 1:
        arr = arr[..., 0]
    if arr.ndim != 3:
        raise ValueError(f"Unsupported confidence shape {arr.shape!r}")
    return arr.astype(np.float32, copy=False)


def mesh_from_point_maps(
    point_maps: np.ndarray,
    confidences: np.ndarray,
    *,
    image_paths: list[Path] | None = None,
    stride: int = 8,
    min_confidence: float = 0.2,
    max_edge_ratio: float = 6.0,
) -> trimesh.Trimesh | None:
    if point_maps.ndim != 4 or point_maps.shape[-1] != 3:
        raise ValueError("point_maps must have shape [V, H, W, 3]")
    if confidences.ndim != 3 or confidences.shape[:3] != point_maps.shape[:3]:
        raise ValueError("confidences must have shape [V, H, W]")
    stride = max(1, int(stride))

    resized_images: list[np.ndarray] = []
    if image_paths:
        target_h, target_w = int(point_maps.shape[1]), int(point_maps.shape[2])
        for path in image_paths:
            image = Image.open(path).convert("RGB").resize((target_w, target_h), Image.Resampling.BILINEAR)
            resized_images.append(np.asarray(image, dtype=np.uint8))

    meshes: list[trimesh.Trimesh] = []
    fallback_points: list[np.ndarray] = []
    for view_idx in range(point_maps.shape[0]):
        points = point_maps[view_idx, ::stride, ::stride]
        conf = confidences[view_idx, ::stride, ::stride]
        valid = np.isfinite(points).all(axis=2) & np.isfinite(conf) & (conf >= float(min_confidence))
        if valid.sum() < 4:
            continue
        fallback_points.append(points[valid])
        view_colors = None
        if resized_images and view_idx < len(resized_images):
            view_colors = resized_images[view_idx][::stride, ::stride]
        mesh = _triangulate_point_grid(points, valid, colors=view_colors, max_edge_ratio=max_edge_ratio)
        if mesh is not None and len(mesh.faces) > 0:
            meshes.append(mesh)

    if not meshes:
        if not fallback_points:
            return None
        pts = np.concatenate(fallback_points, axis=0)
        if len(pts) < 4:
            return None
        cloud = trimesh.points.PointCloud(pts)
        try:
            mesh = cloud.convex_hull
        except Exception:  # noqa: BLE001
            return None
        return mesh

    mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    try:
        mesh.update_faces(mesh.unique_faces())
    except Exception:  # noqa: BLE001
        pass
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals(multibody=False)
    return mesh


def _triangulate_point_grid(
    points: np.ndarray,
    valid: np.ndarray,
    *,
    colors: np.ndarray | None = None,
    max_edge_ratio: float = 6.0,
) -> trimesh.Trimesh | None:
    h, w, _ = points.shape
    idx_map = -np.ones((h, w), dtype=np.int64)
    vertices: list[list[float]] = []
    vertex_colors: list[list[int]] = []
    for y, x in zip(*np.where(valid)):
        idx_map[y, x] = len(vertices)
        vertices.append(points[y, x].tolist())
        if colors is not None:
            rgb = colors[y, x].tolist()
            vertex_colors.append([int(rgb[0]), int(rgb[1]), int(rgb[2]), 255])
    if len(vertices) < 4:
        return None

    edge_lengths: list[float] = []
    for y in range(h):
        for x in range(w - 1):
            if valid[y, x] and valid[y, x + 1]:
                edge_lengths.append(float(np.linalg.norm(points[y, x] - points[y, x + 1])))
    for y in range(h - 1):
        for x in range(w):
            if valid[y, x] and valid[y + 1, x]:
                edge_lengths.append(float(np.linalg.norm(points[y, x] - points[y + 1, x])))
    median_edge = float(np.median(edge_lengths)) if edge_lengths else 1.0
    edge_threshold = median_edge * max(1.5, float(max_edge_ratio))

    faces: list[list[int]] = []
    for y in range(h - 1):
        for x in range(w - 1):
            quad = [(y, x), (y, x + 1), (y + 1, x), (y + 1, x + 1)]
            if not all(valid[i, j] for i, j in quad):
                continue
            i00, i10, i01, i11 = (int(idx_map[y, x]), int(idx_map[y, x + 1]), int(idx_map[y + 1, x]), int(idx_map[y + 1, x + 1]))
            p00, p10, p01, p11 = points[y, x], points[y, x + 1], points[y + 1, x], points[y + 1, x + 1]
            if _triangle_ok([p00, p10, p01], edge_threshold):
                faces.append([i00, i10, i01])
            if _triangle_ok([p11, p01, p10], edge_threshold):
                faces.append([i11, i01, i10])
    if not faces:
        return None
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices, dtype=np.float32), faces=np.asarray(faces, dtype=np.int64), process=False)
    if vertex_colors:
        mesh.visual.vertex_colors = np.asarray(vertex_colors, dtype=np.uint8)
    return mesh


def _triangle_ok(points: list[np.ndarray], edge_threshold: float) -> bool:
    lengths = [
        float(np.linalg.norm(points[0] - points[1])),
        float(np.linalg.norm(points[1] - points[2])),
        float(np.linalg.norm(points[2] - points[0])),
    ]
    if any((not math.isfinite(length)) or length <= 1e-8 for length in lengths):
        return False
    if max(lengths) > edge_threshold:
        return False
    area = float(np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) * 0.5)
    return area > 1e-8
