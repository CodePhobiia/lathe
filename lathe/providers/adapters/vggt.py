"""VGGT local shape-provider adapter.

Runs the facebookresearch/VGGT package locally for multi-view geometric
reconstruction, then falls into a deterministic point-grid triangulation to
produce mesh candidates.  ``torch`` and ``vggt`` are imported lazily so
merely importing this adapter does not drag the ML stack into the default
runtime.
"""
from __future__ import annotations

import math
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from PIL import Image

from ..errors import ShapeProviderExecutionError, ShapeProviderUnavailable
from ..mesh_ops import _mesh_quality_score, _runtime_from_mesh


PROVIDER_ID = "lathe.provider.shape.vggt_local_v1"


def _non_material_image_refs(conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in conditioning.get("image_refs", []) if item.get("kind") != "material"]


def run_vggt_local_provider(
    asset: dict[str, Any],
    *,
    candidates_count: int,
    conditioning: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    image_paths = [Path(item["path"]) for item in _non_material_image_refs(conditioning)]
    max_views = int(config.get("max_views", 8))
    image_paths = image_paths[:max_views]
    if len(image_paths) < 2:
        raise ShapeProviderExecutionError(PROVIDER_ID, "VGGT requires at least two non-material images", code="insufficient_views")

    try:
        import torch
        from vggt.models.vggt import VGGT
        from vggt.utils.geometry import unproject_depth_map_to_point_map
        from vggt.utils.load_fn import load_and_preprocess_images
        from vggt.utils.pose_enc import pose_encoding_to_extri_intri
    except ImportError as exc:
        raise ShapeProviderUnavailable(PROVIDER_ID, f"Failed to import VGGT runtime: {exc}", code="import_failed") from exc

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
                provider_id=PROVIDER_ID,
                notes=notes,
                candidate_index=used,
                score_override=score,
            )
        )
        used += 1
    if not candidates:
        raise ShapeProviderExecutionError(PROVIDER_ID, "VGGT reconstruction did not yield a mesh candidate", code="empty_reconstruction")
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
        except (ValueError, IndexError, RuntimeError):
            return None
        return mesh

    mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    try:
        mesh.update_faces(mesh.unique_faces())
    except (AttributeError, IndexError, ValueError):
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
