"""Deterministic proxy render and export artifacts for Wonder scenes.

These helpers intentionally build simple local artifacts from Scene Graph JSON:
PNG render passes and GLB proxy geometry. They are not a Blender replacement,
but they are real files that preserve scene/object identity and let the Wonder
loop validate package, render, patch, and export plumbing without external
runtime dependencies.
"""

from __future__ import annotations

import math
import re
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from lathe.errors import LatheConfigError
from lathe.paths import PathGuardError, safe_resolve
from lathe.scene.io import write_bytes_atomic, write_json_atomic, write_text_atomic
from lathe.scene.layout import instancing_metadata_by_object_id

SCENE_RENDER_ARTIFACTS_VERSION = "lathe.scene_render_artifacts.v1"
SCENE_EXPORT_ARTIFACTS_VERSION = "lathe.scene_export_artifacts.v1"
SCENE_ID_MASK_BUNDLE_VERSION = "lathe.scene_id_mask_export_bundle.v1"
PROXY_RENDERER_ID = "lathe.scene.proxy_renderer.v1"
PROXY_EXPORTER_ID = "lathe.scene.proxy_glb_exporter.v1"
PROXY_USD_EXPORTER_ID = "lathe.scene.proxy_usd_exporter.v1"
CONTACT_SHEET_CAMERA_ID = "camera_object_contact_sheet"

RenderPass = Literal["beauty", "object_id", "material_id", "depth", "normal", "wireframe"]
SceneArtifactMode = Literal["preview", "final"]

DEFAULT_PREVIEW_PASSES: tuple[RenderPass, ...] = ("beauty", "object_id")
DEFAULT_FINAL_PASSES: tuple[RenderPass, ...] = ("beauty", "object_id", "depth", "normal", "material_id")
SUPPORTED_RENDER_PASSES: tuple[RenderPass, ...] = (*DEFAULT_FINAL_PASSES, "wireframe")

_SAFE_FILE_RE = re.compile(r"[^a-z0-9_]+")
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


class SceneArtifactError(LatheConfigError):
    """Raised when proxy render/export artifacts cannot be produced."""

    def __init__(self, message: str, *, diagnostics: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class _RenderTimer:
    def __init__(self, timeout_seconds: float | None) -> None:
        self.timeout_seconds = None if timeout_seconds is None else float(timeout_seconds)
        self.start = time.monotonic()
        self.deadline = None if self.timeout_seconds is None else self.start + self.timeout_seconds
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            self._raise_timeout(phase="scene_render_start", path="/timeout")

    def elapsed_seconds(self) -> float:
        return round(time.monotonic() - self.start, 6)

    def check(self, *, phase: str, path: str) -> None:
        if self.deadline is not None and time.monotonic() > self.deadline:
            self._raise_timeout(phase=phase, path=path)

    def _raise_timeout(self, *, phase: str, path: str) -> None:
        timeout_value = 0.0 if self.timeout_seconds is None else self.timeout_seconds
        _raise_artifact_error(
            "Scene proxy render timed out.",
            [
                _diagnostic(
                    "SR1004",
                    "render_timeout_exceeded",
                    path,
                    f"Scene proxy render exceeded the {timeout_value:g}s timeout.",
                    phase=phase,
                    details={
                        "timeout_seconds": timeout_value,
                        "elapsed_seconds": self.elapsed_seconds(),
                    },
                )
            ],
        )


@dataclass(frozen=True)
class _ObjectRecord:
    object_id: str
    name: str
    role: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    scale: tuple[float, float, float]
    extents: tuple[float, float, float]
    material_id: str | None
    material_index: int | None
    render_index: int
    color: tuple[int, int, int, int]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class _RegionRecord:
    region_id: str
    name: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]


@dataclass(frozen=True)
class _CameraRecord:
    camera_id: str
    target: str | None
    framing: str
    purpose: str


def render_scene_graph(
    scene_graph: Mapping[str, Any],
    package_dir: str | Path,
    *,
    mode: SceneArtifactMode = "preview",
    camera_id: str | None = None,
    passes: Sequence[str] | None = None,
    resolution: Sequence[int] | None = None,
    include_topdown: bool = True,
    include_contact_sheet: bool = False,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Render deterministic proxy PNG passes for a Scene Graph.

    The renderer draws simple region bounds and object proxies from stable
    transforms/materials. Object and material ID passes are color-coded and come
    with JSON indices so UI and repair loops can refer back to exact IDs.
    """
    package_root = Path(package_dir)
    render_passes = _render_passes(mode=mode, passes=passes)
    width, height = _resolution(mode=mode, resolution=resolution)
    render_timer = _RenderTimer(timeout_seconds)
    scene_id = _scene_id(scene_graph)
    cameras = _cameras(scene_graph, include_topdown=include_topdown)
    if camera_id is not None:
        cameras = [camera for camera in cameras if camera.camera_id == camera_id]
        if not cameras:
            _raise_artifact_error(
                "Requested render camera does not exist.",
                [
                    _diagnostic(
                        "SR1001",
                        "render_camera_missing",
                        "/camera_id",
                        f"Scene camera {camera_id!r} does not exist.",
                        details={"camera_id": camera_id},
                    )
                ],
            )

    objects = _objects(scene_graph)
    regions = _regions(scene_graph)
    material_index = _material_index(scene_graph)
    artifacts: list[dict[str, Any]] = []
    object_indices: list[dict[str, Any]] = []
    material_indices: list[dict[str, Any]] = []
    contact_sheets: list[dict[str, Any]] = []

    for camera in cameras:
        render_timer.check(phase="scene_render_camera", path=f"/cameras/{camera.camera_id}")
        camera_dir = _safe_package_path(package_root, f"renders/{camera.camera_id}")
        camera_dir.mkdir(parents=True, exist_ok=True)
        object_index_payload = _object_index_payload(scene_graph, camera, objects)
        material_index_payload = _material_index_payload(scene_graph, camera, material_index)
        _write_json(camera_dir / "object_index.json", object_index_payload)
        _write_json(camera_dir / "material_index.json", material_index_payload)
        object_indices.append(
            {
                "camera_id": camera.camera_id,
                "path": _relative_to(package_root, camera_dir / "object_index.json"),
                "objects": len(object_index_payload["objects"]),
            }
        )
        material_indices.append(
            {
                "camera_id": camera.camera_id,
                "path": _relative_to(package_root, camera_dir / "material_index.json"),
                "materials": len(material_index_payload["materials"]),
            }
        )
        for render_pass in render_passes:
            render_timer.check(phase="scene_render_pass", path=f"/cameras/{camera.camera_id}/{render_pass}")
            image = _render_pass_image(
                scene_graph=scene_graph,
                camera=camera,
                layer=render_pass,
                objects=objects,
                regions=regions,
                width=width,
                height=height,
            )
            path = camera_dir / f"{render_pass}.png"
            image.save(path)
            render_timer.check(phase="scene_render_pass", path=f"/cameras/{camera.camera_id}/{render_pass}")
            artifacts.append(
                {
                    "camera_id": camera.camera_id,
                    "render_pass": render_pass,
                    "path": _relative_to(package_root, path),
                    "width": width,
                    "height": height,
                    "renderer": PROXY_RENDERER_ID,
                    "status": "built",
                }
            )

    if include_contact_sheet:
        render_timer.check(phase="scene_render_contact_sheet", path="/contact_sheets/0")
        contact_sheet = _render_contact_sheet(
            scene_graph=scene_graph,
            package_root=package_root,
            objects=objects,
            material_index=material_index,
            width=width,
            height=height,
        )
        artifacts.append(contact_sheet["artifact"])
        object_indices.append(contact_sheet["object_index"])
        material_indices.append(contact_sheet["material_index"])
        contact_sheets.append(contact_sheet["contact_sheet"])
        render_timer.check(phase="scene_render_contact_sheet", path="/contact_sheets/0")

    report = {
        "schema_version": SCENE_RENDER_ARTIFACTS_VERSION,
        "scene_id": scene_id,
        "mode": mode,
        "renderer": PROXY_RENDERER_ID,
        "resolution": [width, height],
        "cameras": [camera.camera_id for camera in cameras],
        "passes": list(render_passes),
        "artifacts": artifacts,
        "object_indices": object_indices,
        "material_indices": material_indices,
        "contact_sheets": contact_sheets,
        "diagnostics": [],
    }
    if timeout_seconds is not None:
        report["timeout_seconds"] = timeout_seconds
    report_path = _safe_package_path(package_root, "reports/scene_render_artifacts.json")
    _write_json(report_path, report)
    report["report_path"] = _relative_to(package_root, report_path)
    return report


def export_scene_glb(
    scene_graph: Mapping[str, Any],
    package_dir: str | Path,
    *,
    mode: SceneArtifactMode = "preview",
    filename: str | None = None,
    include_collision_nodes: bool = False,
) -> dict[str, Any]:
    """Export deterministic proxy GLB geometry and identity sidecars."""
    scene_id = _scene_id(scene_graph)
    declared_path = f"exports/{_safe_file(filename or f'{scene_id}.glb', suffix='.glb')}"
    return export_scene_glbs(
        scene_graph,
        package_dir,
        mode=mode,
        export_tasks=[
            {
                "task_id": "export_task_cli_glb",
                "target": "glb",
                "format": "glb",
                "path": declared_path,
            }
        ],
        include_collision_nodes=include_collision_nodes,
    )


def export_scene_usd(
    scene_graph: Mapping[str, Any],
    package_dir: str | Path,
    *,
    mode: SceneArtifactMode = "preview",
    filename: str | None = None,
    include_collision_nodes: bool = False,
) -> dict[str, Any]:
    """Export deterministic proxy USDA scene layout and identity sidecars."""
    package_root = Path(package_dir)
    scene_id = _scene_id(scene_graph)
    usd_path = _safe_package_path(
        package_root,
        f"exports/{_safe_file(filename or f'{scene_id}.usda', suffix='.usda')}",
    )
    export_report_path = _safe_package_path(package_root, "reports/scene_export_artifacts.json")
    artifacts = _export_one_proxy_usd(
        scene_graph,
        package_root,
        usd_path=usd_path,
        mode=mode,
        include_collision_nodes=include_collision_nodes,
        task={
            "task_id": "export_task_cli_usd",
            "target": "usd",
            "format": "usda",
            "path": _relative_to(package_root, usd_path),
        },
    )
    report = {
        "schema_version": SCENE_EXPORT_ARTIFACTS_VERSION,
        "scene_id": scene_id,
        "mode": mode,
        "exporter": PROXY_USD_EXPORTER_ID,
        "artifacts": artifacts,
        "diagnostics": [],
    }
    _write_json(export_report_path, report)
    report["report_path"] = _relative_to(package_root, export_report_path)
    return report


def export_scene_id_mask_bundle(
    scene_graph: Mapping[str, Any],
    package_dir: str | Path,
    *,
    mode: SceneArtifactMode = "preview",
) -> dict[str, Any]:
    """Export object-ID mask PNGs and index sidecars for scene exports."""
    package_root = Path(package_dir)
    scene_id = _scene_id(scene_graph)
    width, height = _resolution(mode=mode, resolution=None)
    objects = _objects(scene_graph)
    regions = _regions(scene_graph)
    cameras = _cameras(scene_graph, include_topdown=True)
    artifacts: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for camera in cameras:
        camera_dir = _safe_package_path(package_root, f"exports/id_masks/{camera.camera_id}")
        camera_dir.mkdir(parents=True, exist_ok=True)
        mask_path = camera_dir / "object_id.png"
        object_index_path = camera_dir / "object_index.json"
        image = _render_pass_image(
            scene_graph=scene_graph,
            camera=camera,
            layer="object_id",
            objects=objects,
            regions=regions,
            width=width,
            height=height,
        )
        image.save(mask_path)
        object_index = _object_index_payload(scene_graph, camera, objects)
        _write_json(object_index_path, object_index)
        mask_entry = {
            "target": "id_mask",
            "format": "png",
            "camera_id": camera.camera_id,
            "render_pass": "object_id",
            "path": _relative_to(package_root, mask_path),
            "status": "built",
            "width": width,
            "height": height,
            "object_count": len(objects),
            "mode": mode,
        }
        index_entry = {
            "target": "id_mask_object_index",
            "format": "json",
            "camera_id": camera.camera_id,
            "path": _relative_to(package_root, object_index_path),
            "status": "built",
            "object_count": len(objects),
            "mode": mode,
        }
        artifacts.extend([mask_entry, index_entry])
        entries.append(
            {
                "camera_id": camera.camera_id,
                "mask_path": mask_entry["path"],
                "object_index_path": index_entry["path"],
                "object_count": len(objects),
            }
        )
    bundle = {
        "schema_version": SCENE_ID_MASK_BUNDLE_VERSION,
        "scene_id": scene_id,
        "mode": mode,
        "encoding": "rgb_uint24_render_index",
        "cameras": [camera.camera_id for camera in cameras],
        "entries": entries,
        "artifacts": artifacts,
    }
    manifest_path = _safe_package_path(package_root, "exports/id_masks/id_mask_bundle.json")
    _write_json(manifest_path, bundle)
    artifacts.append(
        {
            "target": "id_mask_bundle",
            "format": "json",
            "path": _relative_to(package_root, manifest_path),
            "status": "built",
            "object_count": len(objects),
            "camera_count": len(cameras),
            "mode": mode,
        }
    )
    bundle["path"] = _relative_to(package_root, manifest_path)
    return {
        "schema_version": SCENE_ID_MASK_BUNDLE_VERSION,
        "scene_id": scene_id,
        "mode": mode,
        "bundle": bundle,
        "artifacts": artifacts,
        "diagnostics": [],
    }


def export_scene_glbs(
    scene_graph: Mapping[str, Any],
    package_dir: str | Path,
    *,
    mode: SceneArtifactMode = "preview",
    export_tasks: Sequence[Mapping[str, Any]] | None = None,
    include_collision_nodes: bool = False,
) -> dict[str, Any]:
    """Export deterministic proxy GLBs for declared GLB scene export tasks."""
    package_root = Path(package_dir)
    scene_id = _scene_id(scene_graph)
    export_report_path = _safe_package_path(package_root, "reports/scene_export_artifacts.json")
    tasks = _glb_export_tasks(export_tasks)
    artifacts: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for task in tasks:
        glb_path = _glb_path_for_task(package_root, scene_id=scene_id, task=task)
        relative_glb_path = _relative_to(package_root, glb_path)
        if relative_glb_path in seen_paths:
            _raise_artifact_error(
                "Multiple Scene Plan export tasks resolve to the same GLB path.",
                [
                    _diagnostic(
                        "SX1003",
                        "duplicate_proxy_export_path",
                        "/export_tasks",
                        f"Multiple GLB export tasks resolve to {relative_glb_path!r}.",
                        contract="scene_export",
                        phase="scene_export",
                        details={"path": relative_glb_path},
                    )
                ],
            )
        seen_paths.add(relative_glb_path)
        artifacts.extend(
            _export_one_proxy_glb(
                scene_graph,
                package_root,
                glb_path=glb_path,
                mode=mode,
                include_collision_nodes=include_collision_nodes,
                task=task,
            )
        )
    report = {
        "schema_version": SCENE_EXPORT_ARTIFACTS_VERSION,
        "scene_id": scene_id,
        "mode": mode,
        "exporter": PROXY_EXPORTER_ID,
        "artifacts": artifacts,
        "diagnostics": diagnostics,
    }
    _write_json(export_report_path, report)
    report["report_path"] = _relative_to(package_root, export_report_path)
    return report


def _glb_export_tasks(export_tasks: Sequence[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    if export_tasks is None:
        return []
    return [
        task
        for task in export_tasks
        if _string_field(task, "target") == "glb" or _string_field(task, "format") == "glb"
    ]


def _glb_path_for_task(package_root: Path, *, scene_id: str, task: Mapping[str, Any]) -> Path:
    raw_path = (_string_field(task, "path") or f"exports/{scene_id}.glb").replace("\\", "/").strip()
    source_path = Path(raw_path)
    filename = _safe_file(source_path.name or f"{scene_id}.glb", suffix=".glb")
    if raw_path.startswith("exports/"):
        parent = source_path.parent.as_posix()
        relative_path = f"{parent}/{filename}" if parent not in {"", "."} else f"exports/{filename}"
    else:
        relative_path = f"exports/{filename}"
    path = _safe_package_path(package_root, relative_path)
    relative = _relative_to(package_root, path)
    if not relative.startswith("exports/"):
        _raise_artifact_error(
            "Scene GLB export path must stay under the package exports folder.",
            [
                _diagnostic(
                    "SX1004",
                    "proxy_export_path_outside_exports",
                    "/exports/glb/path",
                    f"GLB export path {raw_path!r} resolves outside the package exports folder.",
                    contract="scene_export",
                    phase="scene_export",
                    details={"path": raw_path, "resolved_path": relative},
                )
            ],
        )
    return path


def _export_one_proxy_glb(
    scene_graph: Mapping[str, Any],
    package_root: Path,
    *,
    glb_path: Path,
    mode: SceneArtifactMode,
    include_collision_nodes: bool,
    task: Mapping[str, Any],
) -> list[dict[str, Any]]:
    try:
        import numpy as np
        import trimesh
        from trimesh.transformations import euler_matrix
    except ImportError as exc:  # pragma: no cover - covered by doctor/dependency gates.
        _raise_artifact_error(
            "Proxy GLB export requires the normal Lathe trimesh/numpy dependencies.",
            [
                _diagnostic(
                    "SX1001",
                    "proxy_export_dependency_missing",
                    "/dependencies",
                    f"Could not import proxy export dependency: {exc}",
                    contract="scene_export",
                    phase="scene_export",
                )
            ],
        )

    scene_id = _scene_id(scene_graph)
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    object_index_path = glb_path.with_name(f"{glb_path.stem}.object_index.json")

    scene = trimesh.Scene(metadata={"lathe_scene_id": scene_id, "lathe_exporter": PROXY_EXPORTER_ID})
    objects = _objects(scene_graph)
    material_index = _material_index(scene_graph)
    instancing_by_object_id = instancing_metadata_by_object_id(scene_graph)
    object_records: list[dict[str, Any]] = []
    collision_records: list[dict[str, Any]] = []
    for item in objects:
        instancing = instancing_by_object_id.get(item.object_id, {})
        glb_extras = _glb_object_extras(scene_id=scene_id, item=item, instancing=instancing)
        mesh = trimesh.creation.box(extents=item.extents)
        mesh.visual.face_colors = item.color
        transform = euler_matrix(
            math.radians(item.rotation[0]),
            math.radians(item.rotation[1]),
            math.radians(item.rotation[2]),
            "sxyz",
        )
        transform[:3, 3] = np.array(item.position, dtype=float)
        mesh.apply_transform(transform)
        mesh.metadata.update(
            {
                "lathe_object_id": item.object_id,
                "lathe_scene_id": scene_id,
                "lathe_material_id": item.material_id,
                "lathe_render_index": item.render_index,
                "lathe_reuse_group_id": instancing.get("reuse_group_id"),
                "lathe_shared_asset": instancing.get("shared_asset"),
                "extras": glb_extras,
            }
        )
        scene.add_geometry(mesh, node_name=item.object_id, geom_name=item.object_id)
        if include_collision_nodes:
            collision_name = f"collision_{item.object_id}"
            collision_mesh = trimesh.creation.box(extents=item.extents)
            collision_mesh.visual.face_colors = (0, 190, 255, 96)
            collision_mesh.apply_transform(transform.copy())
            collision_mesh.metadata.update(
                {
                    "lathe_collision_proxy": True,
                    "lathe_collision_type": "simple_box",
                    "lathe_object_id": item.object_id,
                    "lathe_scene_id": scene_id,
                }
            )
            scene.add_geometry(collision_mesh, node_name=collision_name, geom_name=collision_name)
            collision_records.append(
                {
                    "object_id": item.object_id,
                    "node_name": collision_name,
                    "geometry_name": collision_name,
                    "collision_type": "simple_box",
                    "position": list(item.position),
                    "extents": list(item.extents),
                }
            )
        object_records.append(
            {
                "object_id": item.object_id,
                "node_name": item.object_id,
                "geometry_name": item.object_id,
                "material_id": item.material_id,
                "material_index": item.material_index,
                "render_index": item.render_index,
                "position": list(item.position),
                "extents": list(item.extents),
                "instancing": instancing,
                "glb_extras": glb_extras,
            }
        )

    floor = _floor_mesh(scene_graph)
    if floor is not None:
        scene.add_geometry(floor, node_name="region_floor_proxy", geom_name="region_floor_proxy")

    glb_bytes = scene.export(file_type="glb")
    if not isinstance(glb_bytes, bytes):
        glb_bytes = bytes(glb_bytes)
    write_bytes_atomic(glb_path, glb_bytes)
    identity = _validate_glb_identity(glb_path, [item.object_id for item in objects])
    if identity.get("status") != "passed":
        _raise_artifact_error(
            "Proxy GLB export did not preserve all required object IDs.",
            [
                _diagnostic(
                    "SX1002",
                    "proxy_export_identity_failed",
                    "/exports/glb/identity",
                    "Proxy GLB identity validation failed after export.",
                    contract="scene_export",
                    phase="scene_export_identity",
                    details={"path": _relative_to(package_root, glb_path), "identity": identity},
                )
            ],
        )
    object_index = {
        "schema_version": "lathe.scene_export_object_index.v1",
        "scene_id": scene_id,
        "export_path": _relative_to(package_root, glb_path),
        "exporter": PROXY_EXPORTER_ID,
        "identity": identity,
        "collision_policy": "simple_box_proxy" if include_collision_nodes else "not_exported",
        "collision_nodes": collision_records,
        "objects": object_records,
        "materials": [
            {"material_id": material_id, "material_index": index}
            for material_id, index in sorted(material_index.items(), key=lambda item: item[1])
        ],
    }
    _write_json(object_index_path, object_index)
    task_id = _string_field(task, "task_id")
    declared_path = _string_field(task, "path")
    return [
        {
            "task_id": task_id,
            "target": "glb",
            "format": "glb",
            "path": _relative_to(package_root, glb_path),
            "declared_path": declared_path,
            "status": "built",
            "bytes": glb_path.stat().st_size,
            "object_count": len(objects),
            "collision_nodes": len(collision_records),
            "identity": identity,
            "mode": mode,
        },
        {
            "task_id": task_id,
            "target": "object_index",
            "format": "json",
            "path": _relative_to(package_root, object_index_path),
            "status": "built",
            "object_count": len(objects),
            "mode": mode,
        },
    ]


def _export_one_proxy_usd(
    scene_graph: Mapping[str, Any],
    package_root: Path,
    *,
    usd_path: Path,
    mode: SceneArtifactMode,
    include_collision_nodes: bool,
    task: Mapping[str, Any],
) -> list[dict[str, Any]]:
    scene_id = _scene_id(scene_graph)
    usd_path.parent.mkdir(parents=True, exist_ok=True)
    object_index_path = usd_path.with_name(f"{usd_path.stem}.usd_object_index.json")
    objects = _objects(scene_graph)
    regions = _regions(scene_graph)
    material_index = _material_index(scene_graph)
    object_records: list[dict[str, Any]] = []
    region_records: list[dict[str, Any]] = []
    collision_records: list[dict[str, Any]] = []

    for region in regions:
        prim_name = _usd_identifier(region.region_id, prefix="region")
        region_records.append(
            {
                "region_id": region.region_id,
                "prim_name": prim_name,
                "prim_path": f"/LatheScene/Regions/{prim_name}",
                "center": list(region.center),
                "size": list(region.size),
            }
        )
    for item in objects:
        prim_name = _usd_identifier(item.object_id, prefix="obj")
        object_records.append(
            {
                "object_id": item.object_id,
                "prim_name": prim_name,
                "prim_path": f"/LatheScene/Objects/{prim_name}",
                "material_id": item.material_id,
                "material_index": item.material_index,
                "render_index": item.render_index,
                "position": list(item.position),
                "rotation": list(item.rotation),
                "extents": list(item.extents),
            }
        )
        if include_collision_nodes:
            collision_records.append(
                {
                    "object_id": item.object_id,
                    "prim_name": f"collision_{prim_name}",
                    "prim_path": f"/LatheScene/Objects/{prim_name}/collision_proxy",
                    "collision_type": "simple_box",
                    "position": list(item.position),
                    "extents": list(item.extents),
                }
            )

    _write_text(
        usd_path,
        _proxy_usda_text(
            scene_graph=scene_graph,
            scene_id=scene_id,
            mode=mode,
            objects=objects,
            object_records=object_records,
            region_records=region_records,
            include_collision_nodes=include_collision_nodes,
        ),
    )
    identity = _validate_usd_identity(usd_path, [item.object_id for item in objects])
    if identity.get("status") != "passed":
        _raise_artifact_error(
            "Proxy USD export did not preserve all required object IDs.",
            [
                _diagnostic(
                    "SX1102",
                    "proxy_usd_export_identity_failed",
                    "/exports/usd/identity",
                    "Proxy USD identity validation failed after export.",
                    contract="scene_export",
                    phase="scene_export_identity",
                    details={"path": _relative_to(package_root, usd_path), "identity": identity},
                )
            ],
        )
    object_index = {
        "schema_version": "lathe.scene_export_object_index.v1",
        "scene_id": scene_id,
        "export_path": _relative_to(package_root, usd_path),
        "exporter": PROXY_USD_EXPORTER_ID,
        "identity": identity,
        "layout_convention": {
            "schema_version": "lathe.proxy_usd_layout.v1",
            "format": "usda",
            "default_prim": "/LatheScene",
            "region_root": "/LatheScene/Regions",
            "object_root": "/LatheScene/Objects",
            "object_prim_path_template": "/LatheScene/Objects/{object_prim_name}",
            "region_prim_path_template": "/LatheScene/Regions/{region_prim_name}",
        },
        "collision_policy": "simple_box_proxy" if include_collision_nodes else "not_exported",
        "collision_nodes": collision_records,
        "objects": object_records,
        "regions": region_records,
        "materials": [
            {"material_id": material_id, "material_index": index}
            for material_id, index in sorted(material_index.items(), key=lambda item: item[1])
        ],
    }
    _write_json(object_index_path, object_index)
    task_id = _string_field(task, "task_id")
    declared_path = _string_field(task, "path")
    return [
        {
            "task_id": task_id,
            "target": "usd",
            "format": "usda",
            "path": _relative_to(package_root, usd_path),
            "declared_path": declared_path,
            "status": "built",
            "bytes": usd_path.stat().st_size,
            "object_count": len(objects),
            "collision_nodes": len(collision_records),
            "identity": identity,
            "layout_convention": "lathe.proxy_usd_layout.v1",
            "mode": mode,
        },
        {
            "task_id": task_id,
            "target": "object_index",
            "format": "json",
            "path": _relative_to(package_root, object_index_path),
            "status": "built",
            "object_count": len(objects),
            "mode": mode,
        },
    ]


def _proxy_usda_text(
    *,
    scene_graph: Mapping[str, Any],
    scene_id: str,
    mode: SceneArtifactMode,
    objects: Sequence[_ObjectRecord],
    object_records: Sequence[Mapping[str, Any]],
    region_records: Sequence[Mapping[str, Any]],
    include_collision_nodes: bool,
) -> str:
    lines = [
        "#usda 1.0",
        "(",
        '    defaultPrim = "LatheScene"',
        "    metersPerUnit = 1",
        '    upAxis = "Z"',
        "    customData = {",
        f'        string lathe_scene_id = "{_usd_string(scene_id)}"',
        f'        string lathe_exporter = "{PROXY_USD_EXPORTER_ID}"',
        f'        string lathe_mode = "{mode}"',
        "    }",
        ")",
        "",
        'def Xform "LatheScene" (',
        "    customData = {",
        f'        string lathe_scene_id = "{_usd_string(scene_id)}"',
        f'        string lathe_prompt = "{_usd_string(_string_field(scene_graph, "prompt") or "")}"',
        "    }",
        ")",
        "{",
        '    def Xform "Regions"',
        "    {",
    ]
    for region in region_records:
        region_id = str(region["region_id"])
        prim_name = str(region["prim_name"])
        center = _float_tuple(region.get("center", [0, 0, 0]))
        size = _float_tuple(region.get("size", [1, 1, 1]))
        lines.extend(
            [
                f'        def Xform "{prim_name}" (',
                "            customData = {",
                f'                string lathe_region_id = "{_usd_string(region_id)}"',
                "            }",
                "        )",
                "        {",
                f"            double3 xformOp:translate = {center}",
                f"            double3 xformOp:scale = {size}",
                '            uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]',
                "        }",
            ]
        )
    lines.extend(
        [
            "    }",
            '    def Xform "Objects"',
            "    {",
        ]
    )
    objects_by_id = {item.object_id: item for item in objects}
    for record in object_records:
        object_id = str(record["object_id"])
        item = objects_by_id[object_id]
        prim_name = str(record["prim_name"])
        material_id = item.material_id or ""
        position = _float_tuple(item.position)
        rotation = _float_tuple(item.rotation)
        scale = _float_tuple(item.extents)
        lines.extend(
            [
                f'        def Xform "{prim_name}" (',
                "            customData = {",
                f'                string lathe_object_id = "{_usd_string(object_id)}"',
                f'                string lathe_scene_id = "{_usd_string(scene_id)}"',
                f'                string lathe_material_id = "{_usd_string(material_id)}"',
                f"                int lathe_render_index = {item.render_index}",
                "            }",
                "        )",
                "        {",
                f"            double3 xformOp:translate = {position}",
                f"            double3 xformOp:rotateXYZ = {rotation}",
                f"            double3 xformOp:scale = {scale}",
                (
                    '            uniform token[] xformOpOrder = ["xformOp:translate", '
                    '"xformOp:rotateXYZ", "xformOp:scale"]'
                ),
                '            def Cube "proxy_cube"',
                "            {",
                "                double size = 1",
                "            }",
            ]
        )
        if include_collision_nodes:
            lines.extend(
                [
                    '            def Cube "collision_proxy" (',
                    "                customData = {",
                    "                    bool lathe_collision_proxy = true",
                    '                    string lathe_collision_type = "simple_box"',
                    f'                    string lathe_object_id = "{_usd_string(object_id)}"',
                    "                }",
                    "            )",
                    "            {",
                    "                double size = 1",
                    "            }",
                ]
            )
        lines.append("        }")
    lines.extend(["    }", "}", ""])
    return "\n".join(lines)


def _render_contact_sheet(
    *,
    scene_graph: Mapping[str, Any],
    package_root: Path,
    objects: Sequence[_ObjectRecord],
    material_index: Mapping[str, int],
    width: int,
    height: int,
) -> dict[str, Any]:
    camera = _CameraRecord(
        camera_id=CONTACT_SHEET_CAMERA_ID,
        target=None,
        framing="contact_sheet",
        purpose="Deterministic object contact sheet for scene review and selection.",
    )
    contact_dir = _safe_package_path(package_root, f"renders/{CONTACT_SHEET_CAMERA_ID}")
    contact_dir.mkdir(parents=True, exist_ok=True)
    object_index_payload = _object_index_payload(scene_graph, camera, objects)
    material_index_payload = _material_index_payload(scene_graph, camera, material_index)
    object_index_path = contact_dir / "object_index.json"
    material_index_path = contact_dir / "material_index.json"
    _write_json(object_index_path, object_index_payload)
    _write_json(material_index_path, material_index_payload)
    image_path = contact_dir / "beauty.png"
    _contact_sheet_image(scene_graph=scene_graph, objects=objects, width=width, height=height).save(image_path)
    relative_image_path = _relative_to(package_root, image_path)
    return {
        "artifact": {
            "camera_id": CONTACT_SHEET_CAMERA_ID,
            "render_pass": "beauty",
            "path": relative_image_path,
            "width": width,
            "height": height,
            "renderer": PROXY_RENDERER_ID,
            "status": "built",
            "kind": "object_contact_sheet",
            "object_count": len(objects),
        },
        "object_index": {
            "camera_id": CONTACT_SHEET_CAMERA_ID,
            "path": _relative_to(package_root, object_index_path),
            "objects": len(object_index_payload["objects"]),
        },
        "material_index": {
            "camera_id": CONTACT_SHEET_CAMERA_ID,
            "path": _relative_to(package_root, material_index_path),
            "materials": len(material_index_payload["materials"]),
        },
        "contact_sheet": {
            "camera_id": CONTACT_SHEET_CAMERA_ID,
            "path": relative_image_path,
            "object_count": len(objects),
            "width": width,
            "height": height,
        },
    }


def _contact_sheet_image(
    *,
    scene_graph: Mapping[str, Any],
    objects: Sequence[_ObjectRecord],
    width: int,
    height: int,
):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (width, height), (24, 26, 32))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    title = f"{_scene_id(scene_graph)} object contact sheet"
    draw.text((18, 14), title, fill=(245, 245, 235), font=font)
    if not objects:
        draw.text((18, 38), "No scene objects.", fill=(190, 198, 210), font=font)
        return image

    count = len(objects)
    max_columns = max(1, width // 90)
    columns = max(1, min(max_columns, math.ceil(math.sqrt(count))))
    rows = max(1, math.ceil(count / columns))
    margin = 18
    header = 40
    gap = 10
    tile_width = max(56, int((width - margin * 2 - gap * (columns - 1)) / columns))
    tile_height = max(24, int((height - header - margin - gap * (rows - 1)) / rows))
    for index, item in enumerate(sorted(objects, key=lambda record: record.render_index)):
        col = index % columns
        row = index // columns
        left = margin + col * (tile_width + gap)
        top = header + row * (tile_height + gap)
        right = min(width - margin, left + tile_width)
        bottom = min(height - margin, top + tile_height)
        if right <= left or bottom <= top:
            continue
        draw.rounded_rectangle((left, top, right, bottom), radius=4, fill=(38, 42, 50), outline=(90, 98, 112))
        available_height = bottom - top
        if available_height >= 20:
            swatch_bottom = min(bottom - 8, top + max(10, min(30, available_height - 16)))
            swatch_right = min(right - 8, left + max(18, min(tile_width // 4, right - left - 16)))
            swatch = (left + 8, top + 8, swatch_right, swatch_bottom)
            if swatch[2] >= swatch[0] and swatch[3] >= swatch[1]:
                draw.rectangle(swatch, fill=item.color[:3], outline=_outline_color(item.color)[:3])
        label_x = left + max(34, min(tile_width // 4 + 16, tile_width - 36))
        label_y = top + 8
        if label_y < bottom - 8:
            draw.text((label_x, label_y), item.object_id[:28], fill=(245, 245, 235), font=font)
        if label_y + 14 < bottom - 8:
            draw.text((label_x, label_y + 14), item.role[:28], fill=(190, 198, 210), font=font)
        if item.material_id and label_y + 28 < bottom - 8:
            draw.text((label_x, label_y + 28), item.material_id[:28], fill=(168, 184, 220), font=font)
        if bottom - 18 > top:
            draw.text((left + 8, bottom - 18), f"#{item.render_index}", fill=(190, 198, 210), font=font)
    return image


def _render_pass_image(
    *,
    scene_graph: Mapping[str, Any],
    camera: _CameraRecord,
    layer: RenderPass,
    objects: Sequence[_ObjectRecord],
    regions: Sequence[_RegionRecord],
    width: int,
    height: int,
):
    from PIL import Image, ImageDraw, ImageFont

    if layer == "object_id":
        background = (0, 0, 0, 255)
    elif layer == "material_id":
        background = (12, 12, 18, 255)
    elif layer == "depth":
        background = (24, 24, 24, 255)
    elif layer == "normal":
        background = (127, 127, 255, 255)
    else:
        background = (18, 20, 26, 255)
    image = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(image)
    projection = _Projection.from_scene(regions, objects, camera=camera, width=width, height=height)
    if layer in {"beauty", "wireframe"}:
        _draw_regions(draw, projection, regions, layer=layer)
    sorted_objects = sorted(objects, key=lambda item: (item.position[1], item.position[2], item.object_id))
    for item in sorted_objects:
        polygon = projection.object_polygon(item)
        fill = _fill_for_pass(item, layer)
        outline = (236, 238, 240, 255) if layer == "wireframe" else _outline_color(fill)
        if layer == "wireframe":
            draw.polygon(polygon, outline=outline, fill=None)
        else:
            draw.polygon(polygon, fill=fill, outline=outline)
    if layer == "beauty":
        font = ImageFont.load_default()
        title = f"{_scene_id(scene_graph)} / {camera.camera_id}"
        draw.text((18, 16), title, fill=(245, 245, 235, 255), font=font)
        for item in objects:
            x, y = projection.point(item.position)
            label = item.object_id.replace("obj_", "")
            draw.text((x + 5, y - 6), label[:24], fill=(245, 245, 235, 230), font=font)
    return image.convert("RGB")


class _Projection:
    def __init__(
        self,
        *,
        bounds: tuple[float, float, float, float],
        width: int,
        height: int,
        topdown: bool,
    ) -> None:
        min_x, min_y, max_x, max_y = bounds
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        margin = 64.0
        scale = min((width - margin * 2) / span_x, (height - margin * 2) / span_y)
        self.min_x = min_x
        self.min_y = min_y
        self.width = width
        self.height = height
        self.scale = max(scale, 1.0)
        self.margin = margin
        self.topdown = topdown

    @classmethod
    def from_scene(
        cls,
        regions: Sequence[_RegionRecord],
        objects: Sequence[_ObjectRecord],
        *,
        camera: _CameraRecord,
        width: int,
        height: int,
    ) -> _Projection:
        topdown = camera.framing in {"topdown", "debug"} or camera.camera_id.endswith("topdown_debug")
        points: list[tuple[float, float]] = []
        for region in regions:
            corners = _rect_corners(region.center, region.size)
            points.extend(_project_raw(corner, topdown=topdown) for corner in corners)
        for item in objects:
            corners = _rect_corners(item.position, item.extents)
            points.extend(_project_raw(corner, topdown=topdown) for corner in corners)
        if not points:
            points = [(-1.0, -1.0), (1.0, 1.0)]
        min_x = min(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_x = max(point[0] for point in points)
        max_y = max(point[1] for point in points)
        return cls(bounds=(min_x, min_y, max_x, max_y), width=width, height=height, topdown=topdown)

    def point(self, position: Sequence[float]) -> tuple[float, float]:
        x, y = _project_raw(position, topdown=self.topdown)
        sx = self.margin + (x - self.min_x) * self.scale
        sy = self.height - self.margin - (y - self.min_y) * self.scale
        return (round(sx, 3), round(sy, 3))

    def object_polygon(self, item: _ObjectRecord) -> list[tuple[float, float]]:
        return [self.point(corner) for corner in _rect_corners(item.position, item.extents)]

    def region_polygon(self, item: _RegionRecord) -> list[tuple[float, float]]:
        return [self.point(corner) for corner in _rect_corners(item.center, item.size)]


def _draw_regions(
    draw: Any,
    projection: _Projection,
    regions: Sequence[_RegionRecord],
    *,
    layer: RenderPass,
) -> None:
    for region in regions:
        polygon = projection.region_polygon(region)
        fill = (54, 58, 66, 80) if layer == "beauty" else None
        outline = (118, 129, 145, 210)
        draw.polygon(polygon, fill=fill, outline=outline)


def _render_passes(*, mode: SceneArtifactMode, passes: Sequence[str] | None) -> tuple[RenderPass, ...]:
    default = DEFAULT_FINAL_PASSES if mode == "final" else DEFAULT_PREVIEW_PASSES
    raw_passes = default if passes is None else tuple(str(item).strip() for item in passes if str(item).strip())
    supported = set(SUPPORTED_RENDER_PASSES)
    invalid = [item for item in raw_passes if item not in supported]
    if invalid:
        _raise_artifact_error(
            "Unsupported render pass requested.",
            [
                _diagnostic(
                    "SR1002",
                    "unsupported_render_pass",
                    "/passes",
                    f"Unsupported render pass(es): {', '.join(invalid)}.",
                    details={"passes": invalid, "supported": list(SUPPORTED_RENDER_PASSES)},
                )
            ],
        )
    return tuple(raw_passes)  # type: ignore[return-value]


def _resolution(*, mode: SceneArtifactMode, resolution: Sequence[int] | None) -> tuple[int, int]:
    if resolution is None:
        return (2048, 1152) if mode == "final" else (1280, 720)
    if len(resolution) != 2:
        _raise_artifact_error(
            "Render resolution must contain width and height.",
            [
                _diagnostic(
                    "SR1003",
                    "invalid_render_resolution",
                    "/resolution",
                    "Render resolution must contain exactly two positive integers.",
                    details={"resolution": list(resolution)},
                )
            ],
        )
    width, height = int(resolution[0]), int(resolution[1])
    if width <= 0 or height <= 0:
        _raise_artifact_error(
            "Render resolution must be positive.",
            [
                _diagnostic(
                    "SR1003",
                    "invalid_render_resolution",
                    "/resolution",
                    "Render resolution must contain positive integers.",
                    details={"resolution": [width, height]},
                )
            ],
        )
    return width, height


def _regions(scene_graph: Mapping[str, Any]) -> list[_RegionRecord]:
    records: list[_RegionRecord] = []
    for index, region in _items(scene_graph, "regions"):
        region_id = _string_field(region, "region_id") or f"region_missing_{index:03d}"
        bounds = region.get("bounds") if isinstance(region.get("bounds"), Mapping) else {}
        records.append(
            _RegionRecord(
                region_id=region_id,
                name=_string_field(region, "name") or region_id,
                center=_vector3(bounds.get("center") if isinstance(bounds, Mapping) else None, default=(0, 0, 0)),
                size=_vector3(bounds.get("size") if isinstance(bounds, Mapping) else None, default=(4, 4, 2)),
            )
        )
    return records


def _objects(scene_graph: Mapping[str, Any]) -> list[_ObjectRecord]:
    material_index = _material_index(scene_graph)
    material_colors = _material_colors(scene_graph)
    records: list[_ObjectRecord] = []
    for render_index, (source_index, item) in enumerate(
        sorted(_items(scene_graph, "objects"), key=lambda entry: (_string_field(entry[1], "object_id") or "", entry[0])),
        start=1,
    ):
        object_id = _string_field(item, "object_id") or f"obj_missing_{source_index:03d}"
        transform = item.get("transform") if isinstance(item.get("transform"), Mapping) else {}
        role = _string_field(item, "role") or "dressing_prop"
        scale = _vector3(transform.get("scale") if isinstance(transform, Mapping) else None, default=(1, 1, 1))
        material_id = _primary_material_id(item)
        color = material_colors.get(material_id or "", _fallback_color(render_index))
        records.append(
            _ObjectRecord(
                object_id=object_id,
                name=_string_field(item, "name") or object_id,
                role=role,
                position=_vector3(transform.get("position") if isinstance(transform, Mapping) else None, default=(0, 0, 0)),
                rotation=_vector3(transform.get("rotation") if isinstance(transform, Mapping) else None, default=(0, 0, 0)),
                scale=scale,
                extents=_scaled_extents(item, role=role, scale=scale),
                material_id=material_id,
                material_index=material_index.get(material_id or ""),
                render_index=render_index,
                color=color,
                tags=tuple(tag for tag in item.get("semantic_tags", []) if isinstance(tag, str))
                if isinstance(item.get("semantic_tags"), list)
                else (),
            )
        )
    return records


def _cameras(scene_graph: Mapping[str, Any], *, include_topdown: bool) -> list[_CameraRecord]:
    records: list[_CameraRecord] = []
    has_topdown = False
    for index, camera in _items(scene_graph, "cameras"):
        camera_id = _string_field(camera, "camera_id") or f"camera_missing_{index:03d}"
        framing = _string_field(camera, "framing") or "debug"
        has_topdown = has_topdown or framing == "topdown" or camera_id.endswith("topdown_debug")
        records.append(
            _CameraRecord(
                camera_id=camera_id,
                target=_string_field(camera, "target"),
                framing=framing,
                purpose=_string_field(camera, "purpose") or camera_id,
            )
        )
    if include_topdown and not has_topdown:
        records.append(
            _CameraRecord(
                camera_id="camera_topdown_debug",
                target=_layout_focal_point(scene_graph),
                framing="topdown",
                purpose="Deterministic topdown debug render generated by the proxy renderer.",
            )
        )
    return records


def _material_index(scene_graph: Mapping[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, material in enumerate(
        sorted(
            (item for _source_index, item in _items(scene_graph, "materials")),
            key=lambda item: _string_field(item, "material_id") or "",
        ),
        start=1,
    ):
        material_id = _string_field(material, "material_id")
        if material_id is not None:
            result[material_id] = index
    return result


def _material_colors(scene_graph: Mapping[str, Any]) -> dict[str, tuple[int, int, int, int]]:
    result: dict[str, tuple[int, int, int, int]] = {}
    for index, material in enumerate(
        sorted(
            (item for _source_index, item in _items(scene_graph, "materials")),
            key=lambda item: _string_field(item, "material_id") or "",
        ),
        start=1,
    ):
        material_id = _string_field(material, "material_id")
        if material_id is None:
            continue
        pbr = material.get("pbr") if isinstance(material.get("pbr"), Mapping) else {}
        color = None
        if isinstance(pbr, Mapping):
            color = _parse_color(_string_field(pbr, "emissive") or _string_field(pbr, "basecolor"))
        result[material_id] = color or _fallback_color(index)
    return result


def _primary_material_id(item: Mapping[str, Any]) -> str | None:
    bindings = item.get("material_bindings")
    if not isinstance(bindings, list):
        return None
    for binding in bindings:
        if isinstance(binding, Mapping):
            material_id = _string_field(binding, "material")
            if material_id is not None:
                return material_id
    return None


def _normal_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normal_json(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_normal_json(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _glb_object_extras(
    *,
    scene_id: str,
    item: _ObjectRecord,
    instancing: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "lathe_schema_version": "lathe.scene_glb_extras.v1",
        "lathe_scene_id": scene_id,
        "lathe_object_id": item.object_id,
        "lathe_material_id": item.material_id,
        "lathe_render_index": item.render_index,
        "lathe_instancing": _normal_json(instancing),
    }


def _object_index_payload(
    scene_graph: Mapping[str, Any],
    camera: _CameraRecord,
    objects: Sequence[_ObjectRecord],
) -> dict[str, Any]:
    return {
        "schema_version": "lathe.scene_render_object_index.v1",
        "scene_id": _scene_id(scene_graph),
        "camera_id": camera.camera_id,
        "render_pass": "object_id",
        "encoding": "rgb_uint24_render_index",
        "objects": [
            {
                "object_id": item.object_id,
                "render_index": item.render_index,
                "color": _hex(_index_color(item.render_index)),
                "material_id": item.material_id,
            }
            for item in objects
        ],
    }


def _material_index_payload(
    scene_graph: Mapping[str, Any],
    camera: _CameraRecord,
    material_index: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "schema_version": "lathe.scene_render_material_index.v1",
        "scene_id": _scene_id(scene_graph),
        "camera_id": camera.camera_id,
        "render_pass": "material_id",
        "encoding": "rgb_uint24_material_index",
        "materials": [
            {"material_id": material_id, "material_index": index, "color": _hex(_index_color(index))}
            for material_id, index in sorted(material_index.items(), key=lambda item: item[1])
        ],
    }


def _fill_for_pass(item: _ObjectRecord, layer: RenderPass) -> tuple[int, int, int, int]:
    if layer == "object_id":
        return _index_color(item.render_index)
    if layer == "material_id":
        return _index_color(item.material_index or 0)
    if layer == "depth":
        value = max(20, min(235, int(235 - item.position[2] * 28)))
        return (value, value, value, 255)
    if layer == "normal":
        nx = max(0, min(255, int(128 + item.scale[0] * 36)))
        ny = max(0, min(255, int(128 + item.scale[1] * 28)))
        nz = max(0, min(255, int(160 + item.scale[2] * 24)))
        return (nx, ny, nz, 255)
    if layer == "wireframe":
        return (0, 0, 0, 0)
    return item.color


def _scaled_extents(
    item: Mapping[str, Any],
    *,
    role: str,
    scale: Sequence[float],
) -> tuple[float, float, float]:
    source = " ".join(
        str(item.get(field, "")) for field in ("object_id", "name", "lathe_asset", "source_family", "source_kit")
    ).lower()
    if "door" in source:
        base = (0.22, 1.35, 2.5)
    elif "candle" in source:
        base = (0.55, 0.55, 0.85)
    elif "table" in source or role == "hero_prop":
        base = (1.65, 1.15, 0.75)
    elif "arch" in source or "rib" in source or role in {"architecture", "environment_structure"}:
        base = (2.2, 0.55, 2.8)
    elif role == "light_fixture":
        base = (0.75, 0.75, 0.95)
    else:
        base = (1.0, 0.8, 0.8)
    return tuple(max(0.05, float(base[index]) * max(float(scale[index]), 0.05)) for index in range(3))


def _floor_mesh(scene_graph: Mapping[str, Any]):
    try:
        import trimesh
    except ImportError:
        return None
    regions = _regions(scene_graph)
    if not regions:
        return None
    min_x = min(region.center[0] - region.size[0] / 2 for region in regions)
    max_x = max(region.center[0] + region.size[0] / 2 for region in regions)
    min_y = min(region.center[1] - region.size[1] / 2 for region in regions)
    max_y = max(region.center[1] + region.size[1] / 2 for region in regions)
    mesh = trimesh.creation.box(extents=(max(max_x - min_x, 1.0), max(max_y - min_y, 1.0), 0.04))
    mesh.apply_translation(((min_x + max_x) / 2, (min_y + max_y) / 2, -0.04))
    mesh.visual.face_colors = (66, 70, 76, 255)
    mesh.metadata.update({"lathe_scene_floor_proxy": True})
    return mesh


def _validate_glb_identity(glb_path: Path, object_ids: Sequence[str]) -> dict[str, Any]:
    try:
        import trimesh

        loaded = trimesh.load(glb_path, force="scene")
        node_names = set(getattr(loaded.graph, "nodes", []))
        geometry_names = set(getattr(loaded, "geometry", {}).keys())
        found = sorted(object_id for object_id in object_ids if object_id in node_names or object_id in geometry_names)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return {
            "status": "failed",
            "object_ids_expected": list(object_ids),
            "object_ids_found": [],
            "loader_error": str(exc),
        }
    missing = sorted(set(object_ids) - set(found))
    return {
        "status": "passed" if not missing else "failed",
        "object_ids_expected": list(object_ids),
        "object_ids_found": found,
        "object_ids_missing": missing,
    }


def _validate_usd_identity(usd_path: Path, object_ids: Sequence[str]) -> dict[str, Any]:
    try:
        text = usd_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "status": "failed",
            "object_ids_expected": list(object_ids),
            "object_ids_found": [],
            "loader_error": str(exc),
        }
    found = sorted(
        object_id
        for object_id in object_ids
        if f'string lathe_object_id = "{_usd_string(object_id)}"' in text
    )
    missing = sorted(set(object_ids) - set(found))
    return {
        "status": "passed" if not missing else "failed",
        "object_ids_expected": list(object_ids),
        "object_ids_found": found,
        "object_ids_missing": missing,
    }


def _items(payload: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = payload.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _vector3(value: object, *, default: Sequence[float]) -> tuple[float, float, float]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray) and len(value) == 3:
        result: list[float] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int | float):
                return (float(default[0]), float(default[1]), float(default[2]))
            result.append(float(item))
        return (result[0], result[1], result[2])
    return (float(default[0]), float(default[1]), float(default[2]))


def _rect_corners(center: Sequence[float], size: Sequence[float]) -> list[tuple[float, float, float]]:
    x, y, z = float(center[0]), float(center[1]), float(center[2])
    sx, sy = max(float(size[0]) / 2, 0.08), max(float(size[1]) / 2, 0.08)
    return [(x - sx, y - sy, z), (x + sx, y - sy, z), (x + sx, y + sy, z), (x - sx, y + sy, z)]


def _project_raw(position: Sequence[float], *, topdown: bool) -> tuple[float, float]:
    x, y, z = float(position[0]), float(position[1]), float(position[2])
    if topdown:
        return (x, y)
    return ((x - y) * 0.78, (x + y) * 0.42 + z * 0.72)


def _parse_color(value: str | None) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    match = _HEX_RE.fullmatch(value.strip())
    if match is None:
        return None
    text = match.group(1)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), 255)


def _fallback_color(index: int) -> tuple[int, int, int, int]:
    palette = (
        (217, 203, 166, 255),
        (117, 98, 58, 255),
        (70, 95, 130, 255),
        (196, 128, 82, 255),
        (130, 158, 112, 255),
        (152, 116, 168, 255),
    )
    return palette[(index - 1) % len(palette)]


def _index_color(index: int) -> tuple[int, int, int, int]:
    safe_index = max(int(index), 0)
    return (safe_index & 255, (safe_index >> 8) & 255, (safe_index >> 16) & 255, 255)


def _outline_color(fill: Sequence[int]) -> tuple[int, int, int, int]:
    return tuple(max(0, int(channel) - 42) for channel in fill[:3]) + (255,)


def _hex(color: Sequence[int]) -> str:
    return f"#{int(color[0]):02x}{int(color[1]):02x}{int(color[2]):02x}"


def _safe_file(value: str, *, suffix: str) -> str:
    path = Path(value)
    stem = _SAFE_FILE_RE.sub("_", path.stem.lower()).strip("_") or "scene"
    return f"{stem[:80].rstrip('_')}{suffix}"


def _usd_identifier(value: str, *, prefix: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not identifier:
        identifier = prefix
    if not re.match(r"[A-Za-z_]", identifier[0]):
        identifier = f"{prefix}_{identifier}"
    return identifier[:120].rstrip("_") or prefix


def _usd_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _usd_number(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:.6g}"


def _float_tuple(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        values: Sequence[object] = (0.0, 0.0, 0.0)
    else:
        values = value
    padded = list(values[:3]) + [0.0, 0.0, 0.0]
    return f"({_usd_number(padded[0])}, {_usd_number(padded[1])}, {_usd_number(padded[2])})"


def _safe_package_path(package_dir: Path, relative_path: str) -> Path:
    try:
        return safe_resolve(package_dir, relative_path)
    except PathGuardError as exc:
        _raise_artifact_error(
            "Scene artifact package path is unsafe.",
            [
                _diagnostic(
                    "SAF1001",
                    "unsafe_scene_artifact_path",
                    f"/package/{relative_path}",
                    f"Scene artifact path {relative_path!r} is unsafe: {exc}",
                    contract="scene_artifact",
                    phase="scene_artifact_write",
                    details={"path": relative_path, "package_dir": str(package_dir)},
                )
            ],
        )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_json_atomic(path, payload)


def _write_text(path: Path, text: str) -> None:
    write_text_atomic(path, text)


def _relative_to(root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) and value else None


def _scene_id(scene_graph: Mapping[str, Any]) -> str:
    return _string_field(scene_graph, "scene_id") or "scene"


def _layout_focal_point(scene_graph: Mapping[str, Any]) -> str | None:
    layout = scene_graph.get("layout")
    if isinstance(layout, Mapping):
        focal_point = layout.get("focal_point")
        if isinstance(focal_point, str) and focal_point:
            return focal_point
    return next((_string_field(item, "object_id") for _index, item in _items(scene_graph, "objects")), None)


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    contract: str = "scene_render",
    phase: str = "scene_render",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "contract": contract,
        "phase": phase,
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _raise_artifact_error(message: str, diagnostics: list[dict[str, Any]]) -> None:
    raise SceneArtifactError(message, diagnostics=diagnostics)


__all__ = [
    "CONTACT_SHEET_CAMERA_ID",
    "DEFAULT_FINAL_PASSES",
    "DEFAULT_PREVIEW_PASSES",
    "PROXY_EXPORTER_ID",
    "PROXY_RENDERER_ID",
    "PROXY_USD_EXPORTER_ID",
    "SCENE_EXPORT_ARTIFACTS_VERSION",
    "SCENE_ID_MASK_BUNDLE_VERSION",
    "SCENE_RENDER_ARTIFACTS_VERSION",
    "SUPPORTED_RENDER_PASSES",
    "SceneArtifactError",
    "export_scene_glb",
    "export_scene_id_mask_bundle",
    "export_scene_usd",
    "render_scene_graph",
]
