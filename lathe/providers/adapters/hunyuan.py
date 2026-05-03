"""Hunyuan3D-2.1 HTTP shape-provider adapter.

Calls a user-configured Hunyuan FastAPI server to generate image-conditioned
mesh candidates.  Network I/O goes through
:mod:`lathe.providers.transport.http` (which itself sits on top of
:mod:`lathe.net`) so SSRF guards, TLS defaults, and content-type pre-checks
are centralized.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..errors import ShapeProviderExecutionError
from ..mesh_ops import _load_mesh_file, _runtime_from_mesh
from ..transport.http import hunyuan_post_json

PROVIDER_ID = "lathe.provider.shape.hunyuan2_1_http_v1"


def hunyuan_provider() -> dict[str, str]:
    """Entry-point shim for ``lathe.providers.shape``.

    Returns the provider id so the plugin-discovery code can resolve
    the full descriptor from :mod:`lathe.providers.registry`.
    """
    return {"id": PROVIDER_ID}


# GLB containers start with the ASCII magic ``glTF``; used for a cheap sniff
# before the mesh loader in case the transport-level content-type check was
# lenient (e.g. ``application/octet-stream``).
_GLB_MAGIC = b"glTF"
_GLB_MAGIC_SIZE = len(_GLB_MAGIC)

_MESH_CONTENT_TYPES: tuple[str, ...] = (
    "model/gltf-binary",
    "model/gltf+json",
    "application/octet-stream",
    "application/wavefront-obj",
    "text/plain",
    "text/*",
)
_ALLOWED_IMAGE_EXTS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_MAX_IMAGE_BYTES: int = 16 * 1024 * 1024
_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class _HunyuanAuthConfig:
    headers: dict[str, str]


@dataclass(frozen=True)
class _HunyuanProviderConfig:
    base_url: str
    generate_url: str
    out_type: str
    timeout_s: int
    max_retries: int
    retry_backoff_s: float
    allowlist: list[str] | None
    remove_background: bool
    texture: bool
    octree_resolution: int
    num_inference_steps: int
    guidance_scale: float
    num_chunks: int
    face_count: int
    build_id: str
    auth: _HunyuanAuthConfig


def _non_material_image_refs(conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in conditioning.get("image_refs", []) if item.get("kind") != "material"]


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_loopback_host(host: str) -> bool:
    return host.strip("[]").lower() in _LOOPBACK_HOSTS


def _select_primary_image(conditioning: dict[str, Any]) -> Path:
    image_refs = _non_material_image_refs(conditioning)
    if not image_refs:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "No non-material reference image is available",
            code="missing_image_ref",
        )
    source_root_value = conditioning.get("source_root")
    if not isinstance(source_root_value, str) or not source_root_value:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "Hunyuan provider requires image conditioning with a source_root safety boundary",
            code="unsafe_image_ref",
        )
    try:
        source_root = Path(source_root_value).resolve()
        image_path = Path(str(image_refs[0]["path"])).resolve()
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "Invalid Hunyuan image reference path",
            code="unsafe_image_ref",
        ) from exc
    if not _path_within_root(image_path, source_root):
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "Hunyuan image reference escapes the source root",
            code="unsafe_image_ref",
        )
    if image_path.suffix.lower() not in _ALLOWED_IMAGE_EXTS:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "Unsupported Hunyuan image reference format",
            code="unsupported_image_format",
        )
    try:
        size = image_path.stat().st_size
    except OSError as exc:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "Hunyuan image reference could not be read",
            code="missing_image_ref",
        ) from exc
    if size > _MAX_IMAGE_BYTES:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "Hunyuan image reference exceeds the configured byte limit",
            code="image_file_too_large",
        )
    return image_path


def _resolve_hunyuan_auth_config(config: dict[str, Any]) -> _HunyuanAuthConfig:
    """Resolve provider auth material.

    The current Hunyuan HTTP runtime schema defines no credential fields, so
    resolution is intentionally empty instead of inferring secrets from unknown
    config keys.
    """
    _ = config
    return _HunyuanAuthConfig(headers={})


def _resolve_hunyuan_config(config: dict[str, Any]) -> _HunyuanProviderConfig:
    base_url = str(config.get("base_url", "")).rstrip("/")
    if not base_url:
        raise ShapeProviderExecutionError(
            PROVIDER_ID, "Missing base_url for Hunyuan HTTP provider", code="missing_base_url"
        )
    out_type = str(config.get("type", "glb")).lower()
    if out_type not in {"glb", "obj"}:
        raise ShapeProviderExecutionError(
            PROVIDER_ID, f"Unsupported output type '{out_type}'", code="unsupported_output_type"
        )
    raw_allowlist = config.get("url_allowlist")
    allowlist = (
        [str(item) for item in raw_allowlist] if isinstance(raw_allowlist, list) and raw_allowlist else None
    )
    if allowlist is None:
        hostname = urlsplit(base_url).hostname or ""
        if _is_loopback_host(hostname):
            allowlist = [hostname]
    return _HunyuanProviderConfig(
        base_url=base_url,
        generate_url=f"{base_url}/generate",
        out_type=out_type,
        timeout_s=int(config.get("timeout_s", config.get("request_timeout_s", 600))),
        max_retries=max(0, int(config.get("max_retries", 2))),
        retry_backoff_s=max(0.0, float(config.get("retry_backoff_s", 1.0))),
        allowlist=allowlist,
        remove_background=bool(config.get("remove_background", True)),
        texture=bool(config.get("texture", False)),
        octree_resolution=int(config.get("octree_resolution", 256)),
        num_inference_steps=int(config.get("num_inference_steps", 5)),
        guidance_scale=float(config.get("guidance_scale", 5.0)),
        num_chunks=int(config.get("num_chunks", 8000)),
        face_count=int(config.get("face_count", 40000)),
        build_id=str(config.get("_build_id") or uuid.uuid4().hex[:8]),
        auth=_resolve_hunyuan_auth_config(config),
    )


def _build_hunyuan_payload(
    provider_config: _HunyuanProviderConfig,
    *,
    image_b64: str,
    seed: int,
) -> dict[str, Any]:
    return {
        "image": image_b64,
        "remove_background": provider_config.remove_background,
        "texture": provider_config.texture,
        "seed": seed,
        "octree_resolution": provider_config.octree_resolution,
        "num_inference_steps": provider_config.num_inference_steps,
        "guidance_scale": provider_config.guidance_scale,
        "num_chunks": provider_config.num_chunks,
        "face_count": provider_config.face_count,
        "type": provider_config.out_type,
    }


def _hunyuan_request(
    provider_id: str,
    *,
    url: str,
    payload: dict[str, Any],
    timeout_s: int,
    max_retries: int,
    retry_backoff_s: float,
    allowlist: Iterable[str] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Back-compat wrapper used by existing tests that patch this symbol.

    Delegates to :func:`lathe.providers.transport.http.hunyuan_post_json`
    with the mesh content-type allowlist applied.
    """
    return hunyuan_post_json(
        provider_id,
        url=url,
        payload=payload,
        timeout_s=timeout_s,
        max_retries=max_retries,
        retry_backoff_s=retry_backoff_s,
        expect_content_type=_MESH_CONTENT_TYPES,
        allowlist=allowlist,
    )


def _call_hunyuan_generate(
    provider_config: _HunyuanProviderConfig,
    payload: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    return _hunyuan_request(
        PROVIDER_ID,
        url=provider_config.generate_url,
        payload=payload,
        timeout_s=provider_config.timeout_s,
        max_retries=provider_config.max_retries,
        retry_backoff_s=provider_config.retry_backoff_s,
        allowlist=provider_config.allowlist,
    )


def _normalize_hunyuan_result(
    *,
    asset: dict[str, Any],
    conditioning: dict[str, Any],
    source_image: Path,
    payload: dict[str, Any],
    raw: bytes,
    response_meta: dict[str, Any],
    work_dir: Path,
    provider_config: _HunyuanProviderConfig,
    candidate_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if provider_config.out_type == "glb" and (
        len(raw) < _GLB_MAGIC_SIZE or raw[:_GLB_MAGIC_SIZE] != _GLB_MAGIC
    ):
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "Provider returned non-GLB payload when GLB was requested",
            code="invalid_mesh",
            details={"sniffed_prefix_hex": raw[:16].hex()},
        )

    raw_path = (
        work_dir
        / f"hunyuan_candidate_{provider_config.build_id}_{candidate_index:02d}.{provider_config.out_type}"
    )
    raw_path.write_bytes(raw)
    mesh = _load_mesh_file(raw_path)
    if mesh is None or len(mesh.faces) == 0:
        raise ShapeProviderExecutionError(
            PROVIDER_ID, "Provider response did not contain a valid mesh", code="invalid_mesh"
        )

    notes = [
        "generated by Hunyuan3D-2.1 HTTP provider",
        f"source_image={source_image.name}",
        f"seed={payload['seed']}",
        f"resolution={payload['octree_resolution']}",
        f"steps={payload['num_inference_steps']}",
    ]
    candidate = _runtime_from_mesh(
        asset,
        mesh,
        conditioning,
        provider_id=PROVIDER_ID,
        notes=notes,
        candidate_index=candidate_index,
        provider_bias=0.09,
    )
    execution = {
        "candidate_index": candidate_index,
        "request": {
            "source_image": source_image.name,
            "seed": payload["seed"],
            "output_type": provider_config.out_type,
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
    return candidate, execution


def run_hunyuan_http_provider(
    asset: dict[str, Any],
    *,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    work_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Run the configured Hunyuan HTTP provider and normalize its mesh candidates."""
    provider_config = _resolve_hunyuan_config(config)
    source_image = _select_primary_image(conditioning)
    image_b64 = base64.b64encode(source_image.read_bytes()).decode("ascii")

    # Plan 10 M5: prefix candidate filenames with a build id to prevent two
    # concurrent builds sharing ``work_dir`` from colliding on
    # ``hunyuan_candidate_00.glb``.  Caller can thread a deterministic
    # ``_build_id`` through ``config`` for reproducible test output.
    candidates: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    for index in range(candidates_count):
        payload = _build_hunyuan_payload(provider_config, image_b64=image_b64, seed=int(seed + index))
        raw, response_meta = _call_hunyuan_generate(provider_config, payload)
        candidate, execution = _normalize_hunyuan_result(
            asset=asset,
            conditioning=conditioning,
            source_image=source_image,
            payload=payload,
            raw=raw,
            response_meta=response_meta,
            work_dir=work_dir,
            provider_config=provider_config,
            candidate_index=index,
        )
        candidates.append(candidate)
        executions.append(execution)
    return {
        "candidates": candidates,
        "execution": {
            "mode": "http_generate",
            "base_url": provider_config.base_url,
            "executions": executions,
        },
    }
