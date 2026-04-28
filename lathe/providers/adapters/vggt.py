"""VGGT local shape-provider adapter.

Runs the facebookresearch/VGGT package locally for multi-view geometric
reconstruction, then falls into a deterministic point-grid triangulation to
produce mesh candidates.  ``torch`` and ``vggt`` are imported lazily so
merely importing this adapter does not drag the ML stack into the default
runtime.
"""

from __future__ import annotations

import importlib
import math
from contextlib import nullcontext, suppress
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import trimesh
from PIL import Image

from ..errors import ShapeProviderExecutionError, ShapeProviderUnavailable
from ..mesh_ops import _mesh_quality_score, _runtime_from_mesh

PROVIDER_ID = "lathe.provider.shape.vggt_local_v1"
_MIN_VGGT_VIEWS = 2
_CUDA_BFLOAT16_MAJOR = 8
_POINT_MAP_BATCH_DIM = 5
_POINT_MAP_GRID_DIM = 4
_POINT_COORDS = 3
_CONF_BATCH_DIM = 5
_CONF_CHANNEL_DIM = 4
_CONF_GRID_DIM = 3
_MIN_GRID_POINTS = 4
_MIN_EDGE_LENGTH = 1e-8
_MIN_TRIANGLE_AREA = 1e-8
_OPAQUE_ALPHA = 255


class _VggtRuntime(NamedTuple):
    torch: Any
    model_cls: Any
    unproject_depth_map_to_point_map: Any
    load_and_preprocess_images: Any
    pose_encoding_to_extri_intri: Any


class _VggtInference(NamedTuple):
    point_map: Any
    point_conf: Any
    point_map_alt: Any | None
    point_conf_alt: Any | None
    weights: str
    device: str
    autocast_dtype: Any


class _MeshVariant(NamedTuple):
    label: str
    point_map: np.ndarray
    confidence: np.ndarray
    stride: int
    min_confidence: float


class _MissingPointMapError(ValueError):
    def __init__(self) -> None:
        super().__init__("Missing point map value")


class _PointMapShapeError(ValueError):
    def __init__(self, shape: tuple[int, ...]) -> None:
        super().__init__(f"Unsupported point map shape {shape!r}")


class _ConfidenceShapeError(ValueError):
    def __init__(self, shape: tuple[int, ...]) -> None:
        super().__init__(f"Unsupported confidence shape {shape!r}")


class _PointMapsContractError(ValueError):
    def __init__(self) -> None:
        super().__init__("point_maps must have shape [V, H, W, 3]")


class _ConfidencesContractError(ValueError):
    def __init__(self) -> None:
        super().__init__("confidences must have shape [V, H, W]")


def vggt_provider() -> dict[str, str]:
    """Entry-point shim for ``lathe.providers.shape``.

    Returns the provider id so the plugin-discovery code can resolve
    the full descriptor from :mod:`lathe.providers.registry`.
    """
    return {"id": PROVIDER_ID}


def _non_material_image_refs(conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in conditioning.get("image_refs", []) if item.get("kind") != "material"]


def run_vggt_local_provider(
    asset: dict[str, Any],
    *,
    candidates_count: int,
    conditioning: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Run the local VGGT bridge and return Lathe runtime mesh candidates."""
    image_paths = [Path(item["path"]) for item in _non_material_image_refs(conditioning)]
    max_views = int(config.get("max_views", 8))
    image_paths = image_paths[:max_views]
    if len(image_paths) < _MIN_VGGT_VIEWS:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "VGGT requires at least two non-material images",
            code="insufficient_views",
        )

    inference = _run_vggt_inference(config, image_paths)
    variant_specs = _build_mesh_variants(config, inference)
    candidates, attempted_variants = _mesh_candidates_from_variants(
        asset,
        conditioning,
        image_paths,
        candidates_count,
        config,
        variant_specs,
    )
    if not candidates:
        raise ShapeProviderExecutionError(
            PROVIDER_ID,
            "VGGT reconstruction did not yield a mesh candidate",
            code="empty_reconstruction",
        )
    return {
        "candidates": candidates[:candidates_count],
        "execution": {
            "mode": "local_vggt",
            "weights": inference.weights,
            "selected_device": inference.device,
            "dtype": str(inference.autocast_dtype).replace("torch.", ""),
            "views": len(image_paths),
            "attempted_variants": attempted_variants,
        },
    }


def _load_vggt_runtime() -> _VggtRuntime:
    try:
        torch = importlib.import_module("torch")
        vggt_model = importlib.import_module("vggt.models.vggt")
        geometry = importlib.import_module("vggt.utils.geometry")
        load_fn = importlib.import_module("vggt.utils.load_fn")
        pose_enc = importlib.import_module("vggt.utils.pose_enc")
    except ImportError as exc:
        raise ShapeProviderUnavailable(
            PROVIDER_ID,
            f"Failed to import VGGT runtime: {exc}",
            code="import_failed",
        ) from exc
    return _VggtRuntime(
        torch=torch,
        model_cls=vggt_model.VGGT,
        unproject_depth_map_to_point_map=geometry.unproject_depth_map_to_point_map,
        load_and_preprocess_images=load_fn.load_and_preprocess_images,
        pose_encoding_to_extri_intri=pose_enc.pose_encoding_to_extri_intri,
    )


def _resolve_device_and_dtype(config: dict[str, Any], torch: Any) -> tuple[str, Any]:
    device = str(config.get("device", "auto"))
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype_name = str(config.get("dtype", "auto"))

    if dtype_name == "auto":
        if device == "cuda":
            major = torch.cuda.get_device_capability()[0]
            autocast_dtype = torch.bfloat16 if major >= _CUDA_BFLOAT16_MAJOR else torch.float16
        else:
            autocast_dtype = torch.float32
    elif dtype_name == "bfloat16":
        autocast_dtype = torch.bfloat16
    elif dtype_name == "float16":
        autocast_dtype = torch.float16
    else:
        autocast_dtype = torch.float32
    return device, autocast_dtype


def _run_vggt_inference(config: dict[str, Any], image_paths: list[Path]) -> _VggtInference:
    runtime = _load_vggt_runtime()
    device, autocast_dtype = _resolve_device_and_dtype(config, runtime.torch)
    weights = str(config.get("weights", "facebook/VGGT-1B"))

    model = runtime.model_cls.from_pretrained(weights).to(device)
    model.eval()
    images = runtime.load_and_preprocess_images([str(path) for path in image_paths]).to(device)
    images_batch = images[None]

    amp_ctx = runtime.torch.cuda.amp.autocast(dtype=autocast_dtype) if device == "cuda" else nullcontext()
    with runtime.torch.no_grad(), amp_ctx:
        aggregated_tokens_list, ps_idx = model.aggregator(images_batch)
        pose_enc = model.camera_head(aggregated_tokens_list)[-1]
        extrinsic, intrinsic = runtime.pose_encoding_to_extri_intri(
            pose_enc,
            images_batch.shape[-2:],
        )
        depth_map, depth_conf = model.depth_head(aggregated_tokens_list, images_batch, ps_idx)
        point_map = runtime.unproject_depth_map_to_point_map(
            depth_map.squeeze(0),
            extrinsic.squeeze(0),
            intrinsic.squeeze(0),
        )
        point_conf = depth_conf.squeeze(0)
        point_map_alt, point_conf_alt = _maybe_run_point_head(
            config,
            model,
            aggregated_tokens_list,
            images_batch,
            ps_idx,
        )

    return _VggtInference(
        point_map=point_map,
        point_conf=point_conf,
        point_map_alt=point_map_alt,
        point_conf_alt=point_conf_alt,
        weights=weights,
        device=device,
        autocast_dtype=autocast_dtype,
    )


def _maybe_run_point_head(
    config: dict[str, Any],
    model: Any,
    aggregated_tokens_list: Any,
    images_batch: Any,
    ps_idx: Any,
) -> tuple[Any | None, Any | None]:
    if not bool(config.get("use_point_head", False)) or not hasattr(model, "point_head"):
        return None, None
    point_map_alt, point_conf_alt = model.point_head(aggregated_tokens_list, images_batch, ps_idx)
    return point_map_alt.squeeze(0), point_conf_alt.squeeze(0)


def _build_mesh_variants(config: dict[str, Any], inference: _VggtInference) -> list[_MeshVariant]:
    point_map_np = _to_point_map_numpy(inference.point_map)
    point_conf_np = _to_conf_numpy(inference.point_conf)
    point_map_alt_np = (
        _to_point_map_numpy(inference.point_map_alt) if inference.point_map_alt is not None else None
    )
    point_conf_alt_np = (
        _to_conf_numpy(inference.point_conf_alt) if inference.point_conf_alt is not None else None
    )
    stride = max(1, int(config.get("stride", 8)))
    min_conf = float(config.get("min_confidence", 0.20))
    variant_specs = [
        _MeshVariant("depth_unprojection", point_map_np, point_conf_np, stride, min_conf),
    ]
    if point_map_alt_np is not None and point_conf_alt_np is not None:
        variant_specs.append(
            _MeshVariant(
                "point_head",
                point_map_alt_np,
                point_conf_alt_np,
                max(1, stride // 2),
                max(0.05, min_conf * 0.9),
            )
        )
    variant_specs.append(
        _MeshVariant(
            "dense_unprojection",
            point_map_np,
            point_conf_np,
            max(1, stride // 2),
            max(0.05, min_conf * 0.8),
        )
    )
    return variant_specs


def _mesh_candidates_from_variants(
    asset: dict[str, Any],
    conditioning: dict[str, Any],
    image_paths: list[Path],
    candidates_count: int,
    config: dict[str, Any],
    variant_specs: list[_MeshVariant],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    variant_count = max(1, int(config.get("candidate_variants", 2)))
    max_edge_ratio = float(config.get("max_edge_ratio", 6.0))
    candidates: list[dict[str, Any]] = []
    attempted_variants: list[dict[str, Any]] = []
    used = 0
    for variant in variant_specs:
        if used >= max(candidates_count, variant_count):
            break
        mesh = mesh_from_point_maps(
            variant.point_map,
            variant.confidence,
            image_paths=image_paths,
            stride=variant.stride,
            min_confidence=variant.min_confidence,
            max_edge_ratio=max_edge_ratio,
        )
        attempted_variants.append(
            {
                "label": variant.label,
                "stride": variant.stride,
                "min_confidence": variant.min_confidence,
                "produced_mesh": bool(mesh is not None and len(mesh.faces) > 0),
            }
        )
        if mesh is None or len(mesh.faces) == 0:
            continue
        score = round(min(0.99, _mesh_quality_score(mesh) + 0.08 - used * 0.015), 6)
        notes = [
            "reconstructed by VGGT local provider",
            f"views={len(image_paths)}",
            f"variant={variant.label}",
            f"stride={variant.stride}",
            f"min_confidence={variant.min_confidence}",
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
    return candidates, attempted_variants


def _to_point_map_numpy(value: Any) -> np.ndarray:
    if value is None:
        raise _MissingPointMapError
    if hasattr(value, "detach"):
        value = value.detach().float().cpu().numpy()
    arr = np.asarray(value)
    if arr.ndim == _POINT_MAP_BATCH_DIM and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim == _POINT_MAP_GRID_DIM and arr.shape[1] == _POINT_COORDS:  # [V,3,H,W]
        arr = np.transpose(arr, (0, 2, 3, 1))
    if arr.ndim != _POINT_MAP_GRID_DIM or arr.shape[-1] != _POINT_COORDS:
        raise _PointMapShapeError(arr.shape)
    return arr.astype(np.float32, copy=False)


def _to_conf_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().float().cpu().numpy()
    arr = np.asarray(value)
    if arr.ndim == _CONF_BATCH_DIM and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim == _CONF_CHANNEL_DIM and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim == _CONF_CHANNEL_DIM and arr.shape[-1] == 1:
        arr = arr[..., 0]
    if arr.ndim != _CONF_GRID_DIM:
        raise _ConfidenceShapeError(arr.shape)
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
    """Build a deterministic mesh from VGGT point maps and confidence grids."""
    if point_maps.ndim != _POINT_MAP_GRID_DIM or point_maps.shape[-1] != _POINT_COORDS:
        raise _PointMapsContractError
    if confidences.ndim != _CONF_GRID_DIM or confidences.shape[:3] != point_maps.shape[:3]:
        raise _ConfidencesContractError
    stride = max(1, int(stride))

    resized_images = _resized_images(
        image_paths,
        target_h=int(point_maps.shape[1]),
        target_w=int(point_maps.shape[2]),
    )

    meshes: list[trimesh.Trimesh] = []
    fallback_points: list[np.ndarray] = []
    for view_idx in range(point_maps.shape[0]):
        points = point_maps[view_idx, ::stride, ::stride]
        conf = confidences[view_idx, ::stride, ::stride]
        valid = np.isfinite(points).all(axis=2) & np.isfinite(conf) & (conf >= float(min_confidence))
        if valid.sum() < _MIN_GRID_POINTS:
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
        return _convex_hull_mesh(pts)

    mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    with suppress(AttributeError, IndexError, ValueError):
        mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals(multibody=False)
    return mesh


def _resized_images(
    image_paths: list[Path] | None,
    *,
    target_h: int,
    target_w: int,
) -> list[np.ndarray]:
    if not image_paths:
        return []
    resized_images: list[np.ndarray] = []
    for path in image_paths:
        image = Image.open(path).convert("RGB").resize((target_w, target_h), Image.Resampling.BILINEAR)
        resized_images.append(np.asarray(image, dtype=np.uint8))
    return resized_images


def _convex_hull_mesh(points: np.ndarray) -> trimesh.Trimesh | None:
    if len(points) < _MIN_GRID_POINTS:
        return None
    cloud = trimesh.points.PointCloud(points)
    try:
        return cloud.convex_hull
    except (ValueError, IndexError, RuntimeError):
        return None


def _triangulate_point_grid(
    points: np.ndarray,
    valid: np.ndarray,
    *,
    colors: np.ndarray | None = None,
    max_edge_ratio: float = 6.0,
) -> trimesh.Trimesh | None:
    idx_map, vertices, vertex_colors = _grid_vertices(points, valid, colors)
    if len(vertices) < _MIN_GRID_POINTS:
        return None

    edge_lengths = _grid_edge_lengths(points, valid)
    median_edge = float(np.median(edge_lengths)) if edge_lengths else 1.0
    edge_threshold = median_edge * max(1.5, float(max_edge_ratio))
    faces = _grid_faces(points, valid, idx_map, edge_threshold)
    if not faces:
        return None
    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float32),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    if vertex_colors:
        mesh.visual.vertex_colors = np.asarray(vertex_colors, dtype=np.uint8)
    return mesh


def _grid_vertices(
    points: np.ndarray,
    valid: np.ndarray,
    colors: np.ndarray | None,
) -> tuple[np.ndarray, list[list[float]], list[list[int]]]:
    h, w, _ = points.shape
    idx_map = -np.ones((h, w), dtype=np.int64)
    vertices: list[list[float]] = []
    vertex_colors: list[list[int]] = []
    for y, x in zip(*np.where(valid), strict=False):
        idx_map[y, x] = len(vertices)
        vertices.append(points[y, x].tolist())
        if colors is not None:
            rgb = colors[y, x].tolist()
            vertex_colors.append([int(rgb[0]), int(rgb[1]), int(rgb[2]), _OPAQUE_ALPHA])
    return idx_map, vertices, vertex_colors


def _grid_edge_lengths(points: np.ndarray, valid: np.ndarray) -> list[float]:
    h, w, _ = points.shape
    edge_lengths: list[float] = []
    for y in range(h):
        for x in range(w - 1):
            if valid[y, x] and valid[y, x + 1]:
                edge_lengths.append(float(np.linalg.norm(points[y, x] - points[y, x + 1])))
    for y in range(h - 1):
        for x in range(w):
            if valid[y, x] and valid[y + 1, x]:
                edge_lengths.append(float(np.linalg.norm(points[y, x] - points[y + 1, x])))
    return edge_lengths


def _grid_faces(
    points: np.ndarray,
    valid: np.ndarray,
    idx_map: np.ndarray,
    edge_threshold: float,
) -> list[list[int]]:
    h, w, _ = points.shape
    faces: list[list[int]] = []
    for y in range(h - 1):
        for x in range(w - 1):
            quad = [(y, x), (y, x + 1), (y + 1, x), (y + 1, x + 1)]
            if not all(valid[i, j] for i, j in quad):
                continue
            i00, i10, i01, i11 = (
                int(idx_map[y, x]),
                int(idx_map[y, x + 1]),
                int(idx_map[y + 1, x]),
                int(idx_map[y + 1, x + 1]),
            )
            p00, p10, p01, p11 = points[y, x], points[y, x + 1], points[y + 1, x], points[y + 1, x + 1]
            if _triangle_ok([p00, p10, p01], edge_threshold):
                faces.append([i00, i10, i01])
            if _triangle_ok([p11, p01, p10], edge_threshold):
                faces.append([i11, i01, i10])
    return faces


def _triangle_ok(points: list[np.ndarray], edge_threshold: float) -> bool:
    lengths = [
        float(np.linalg.norm(points[0] - points[1])),
        float(np.linalg.norm(points[1] - points[2])),
        float(np.linalg.norm(points[2] - points[0])),
    ]
    if any((not math.isfinite(length)) or length <= _MIN_EDGE_LENGTH for length in lengths):
        return False
    if max(lengths) > edge_threshold:
        return False
    area = float(np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) * 0.5)
    return area > _MIN_TRIANGLE_AREA
