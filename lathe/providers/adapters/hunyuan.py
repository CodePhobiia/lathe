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
from pathlib import Path
from typing import Any

from ..errors import ShapeProviderExecutionError
from ..mesh_ops import _load_mesh_file, _runtime_from_mesh
from ..transport.http import (
    hunyuan_post_json,
    hunyuan_safe_text as _hunyuan_safe_text,
    hunyuan_transient_status as _hunyuan_transient_status,
)


PROVIDER_ID = "lathe.provider.shape.hunyuan2_1_http_v1"

# GLB containers start with the ASCII magic ``glTF``; used for a cheap sniff
# before the mesh loader in case the transport-level content-type check was
# lenient (e.g. ``application/octet-stream``).
_GLB_MAGIC = b"glTF"

_MESH_CONTENT_TYPES: tuple[str, ...] = (
    "model/gltf-binary",
    "model/gltf+json",
    "application/octet-stream",
    "application/wavefront-obj",
    "text/plain",
    "text/*",
)


def _non_material_image_refs(conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in conditioning.get("image_refs", []) if item.get("kind") != "material"]


def _select_primary_image(conditioning: dict[str, Any]) -> Path:
    image_refs = _non_material_image_refs(conditioning)
    if not image_refs:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "No non-material reference image is available",
            code="missing_image_ref",
        )
    return Path(image_refs[0]["path"])


def _hunyuan_request(
    provider_id: str,
    *,
    url: str,
    payload: dict[str, Any],
    timeout_s: int,
    max_retries: int,
    retry_backoff_s: float,
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
    )


def run_hunyuan_http_provider(
    asset: dict[str, Any],
    *,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    work_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    base_url = str(config.get("base_url", "")).rstrip("/")
    if not base_url:
        raise ShapeProviderExecutionError(PROVIDER_ID, "Missing base_url for Hunyuan HTTP provider", code="missing_base_url")
    source_image = _select_primary_image(conditioning)
    image_b64 = base64.b64encode(source_image.read_bytes()).decode("ascii")
    out_type = str(config.get("type", "glb")).lower()
    if out_type not in {"glb", "obj"}:
        raise ShapeProviderExecutionError(PROVIDER_ID, f"Unsupported output type '{out_type}'", code="unsupported_output_type")
    timeout = int(config.get("request_timeout_s", 600))
    max_retries = max(0, int(config.get("max_retries", 2)))
    retry_backoff_s = max(0.0, float(config.get("retry_backoff_s", 1.0)))

    # Plan 10 M5: prefix candidate filenames with a build id to prevent two
    # concurrent builds sharing ``work_dir`` from colliding on
    # ``hunyuan_candidate_00.glb``.  Caller can thread a deterministic
    # ``_build_id`` through ``config`` for reproducible test output.
    build_id = str(config.get("_build_id") or uuid.uuid4().hex[:8])

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
            PROVIDER_ID,
            url=base_url + "/generate",
            payload=payload,
            timeout_s=timeout,
            max_retries=max_retries,
            retry_backoff_s=retry_backoff_s,
        )

        if out_type == "glb" and len(raw) >= 4 and raw[:4] != _GLB_MAGIC:
            raise ShapeProviderExecutionError(
                PROVIDER_ID,
                "Provider returned non-GLB payload when GLB was requested",
                code="invalid_mesh",
                details={"sniffed_prefix_hex": raw[:16].hex()},
            )

        raw_path = work_dir / f"hunyuan_candidate_{build_id}_{index:02d}.{out_type}"
        raw_path.write_bytes(raw)
        mesh = _load_mesh_file(raw_path)
        if mesh is None or len(mesh.faces) == 0:
            raise ShapeProviderExecutionError(PROVIDER_ID, "Provider response did not contain a valid mesh", code="invalid_mesh")
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
                provider_id=PROVIDER_ID,
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
