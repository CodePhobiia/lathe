"""Folder-based scene package manifest helpers for Wonder readiness."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from lathe.errors import LatheConfigError
from lathe.paths import PathGuardError, safe_resolve
from lathe.wonder import get_contract_schema, load_and_validate_contract, validate_contract

SCENE_PACKAGE_MANIFEST_VERSION = "lathe.scene_package_manifest.v1"
SCENE_PACKAGE_MANIFEST_CONTRACT = "scene_package_manifest"
SCENE_PACKAGE_MANIFEST_FILENAME = "scene_package_manifest.json"
PACKAGE_SECTIONS = ("source", "graph", "build", "renders", "exports", "reports")
DEFAULT_PACKAGE_LAYOUT: dict[str, str] = {section: section for section in PACKAGE_SECTIONS}
BUILD_PACKAGE_LAYOUT_DIRS = ("builds/preview", "builds/final")
RENDER_PASS_PACKAGE_LAYOUT_DIRS = (
    "render_passes/depth",
    "render_passes/normal",
    "render_passes/object_id",
    "render_passes/material_id",
    "render_passes/wireframe",
)
CACHE_PACKAGE_LAYOUT_DIRS = ("cache",)
ADDITIONAL_PACKAGE_LAYOUT_DIRS = (
    *BUILD_PACKAGE_LAYOUT_DIRS,
    *RENDER_PASS_PACKAGE_LAYOUT_DIRS,
    *CACHE_PACKAGE_LAYOUT_DIRS,
)
STANDARD_PACKAGE_LAYOUT_DIRS = (
    *DEFAULT_PACKAGE_LAYOUT.values(),
    *ADDITIONAL_PACKAGE_LAYOUT_DIRS,
)

_SNAKE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,79}$")


class ScenePackageError(LatheConfigError):
    """Raised when a scene package manifest cannot be initialized or checked."""


def get_scene_package_manifest_schema() -> dict[str, Any]:
    """Return the committed scene package manifest JSON Schema."""
    return get_contract_schema(SCENE_PACKAGE_MANIFEST_CONTRACT)


def initial_scene_package_manifest(scene_id: str, *, package_id: str | None = None) -> dict[str, Any]:
    """Build a minimal folder-based package manifest payload."""
    resolved_package_id = package_id or scene_id
    manifest: dict[str, Any] = {
        "schema_version": SCENE_PACKAGE_MANIFEST_VERSION,
        "package_id": resolved_package_id,
        "scene_id": scene_id,
        "version": 1,
        "layout": dict(DEFAULT_PACKAGE_LAYOUT),
        "source": [],
        "graph": {},
        "build": [],
        "renders": [],
        "exports": [],
        "reports": [],
    }
    diagnostics = validate_scene_package_manifest_payload(manifest)
    if diagnostics:
        first = diagnostics[0]
        raise ScenePackageError(f"invalid scene package manifest seed at {first['path']}: {first['message']}")
    return manifest


def init_scene_package(
    package_dir: str | Path,
    *,
    scene_id: str,
    package_id: str | None = None,
    overwrite: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Create the standard package folders and write a minimal manifest."""
    if not _SNAKE_ID_RE.fullmatch(scene_id):
        raise ScenePackageError(f"scene_id must match {_SNAKE_ID_RE.pattern!r}: {scene_id!r}")
    if package_id is not None and not _SNAKE_ID_RE.fullmatch(package_id):
        raise ScenePackageError(f"package_id must match {_SNAKE_ID_RE.pattern!r}: {package_id!r}")

    root = Path(package_dir)
    manifest_path = root / SCENE_PACKAGE_MANIFEST_FILENAME
    if manifest_path.exists() and not overwrite:
        raise ScenePackageError(f"scene package manifest already exists: {manifest_path}")

    root.mkdir(parents=True, exist_ok=True)
    for dirname in STANDARD_PACKAGE_LAYOUT_DIRS:
        (root / dirname).mkdir(parents=True, exist_ok=True)

    manifest = initial_scene_package_manifest(scene_id, package_id=package_id)
    diagnostics = check_scene_package_manifest(manifest, root=root, require_exists=True)
    if diagnostics:
        first = diagnostics[0]
        raise ScenePackageError(f"scene package seed failed path checks at {first['path']}: {first['message']}")

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path, manifest


def _format_pointer(path_parts: Any) -> str:
    parts = [str(part) for part in path_parts]
    return "/" + "/".join(parts) if parts else "/"


def validate_scene_package_manifest_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return schema diagnostics for a scene package manifest payload."""
    return validate_contract(SCENE_PACKAGE_MANIFEST_CONTRACT, payload)


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "contract": SCENE_PACKAGE_MANIFEST_CONTRACT,
        "phase": "scene_package_manifest_semantics",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _is_within(child: Path, root: Path) -> bool:
    try:
        child.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_path(root: Path, raw_path: str, pointer: str) -> tuple[Path | None, dict[str, Any] | None]:
    try:
        return safe_resolve(root, raw_path), None
    except PathGuardError as exc:
        return None, _diagnostic(
            "P4001",
            "unsafe_package_path",
            pointer,
            f"Package path {raw_path!r} is not a safe package-relative path: {exc}",
            details={"path": raw_path, "root": str(root)},
        )


def _expected_path_kind(path: Path, expected_kind: str) -> bool:
    if expected_kind == "file":
        return path.is_file()
    if expected_kind == "directory":
        return path.is_dir()
    return path.exists()


def _wrong_kind_name(expected_kind: str) -> str:
    if expected_kind == "directory":
        return "expected_package_directory"
    if expected_kind == "file":
        return "expected_package_file"
    return "expected_package_path"


def _check_scene_graph_scene_id(
    manifest: Mapping[str, Any],
    graph_path: Path,
    pointer: str,
) -> list[dict[str, Any]]:
    manifest_scene_id = manifest.get("scene_id")
    if not isinstance(manifest_scene_id, str):
        return []
    try:
        scene_graph, graph_diagnostics = load_and_validate_contract("scene_graph", graph_path)
    except LatheConfigError as exc:
        return [
            _diagnostic(
                "P4011",
                "package_scene_graph_load_failed",
                pointer,
                f"Package Scene Graph could not be loaded for scene_id consistency checks: {exc}",
                details={"path": str(graph_path)},
            )
        ]
    if graph_diagnostics:
        return []
    graph_scene_id = scene_graph.get("scene_id")
    if graph_scene_id == manifest_scene_id:
        return []
    return [
        _diagnostic(
            "P4010",
            "package_scene_id_mismatch",
            pointer,
            (
                f"Package scene_id {manifest_scene_id!r} must match referenced "
                f"Scene Graph scene_id {graph_scene_id!r}."
            ),
            details={
                "manifest_scene_id": manifest_scene_id,
                "scene_graph_scene_id": graph_scene_id,
                "path": str(graph_path),
            },
        )
    ]


def _layout_dirs(
    manifest: Mapping[str, Any],
    root: Path,
    *,
    require_exists: bool,
) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    resolved: dict[str, Path] = {}
    layout = manifest.get("layout")
    if not isinstance(layout, Mapping):
        return resolved, diagnostics
    for section in PACKAGE_SECTIONS:
        raw_path = layout.get(section)
        if not isinstance(raw_path, str):
            continue
        pointer = f"/layout/{section}"
        path, diagnostic = _safe_path(root, raw_path, pointer)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        if path is None:
            continue
        resolved[section] = path
        if not require_exists:
            continue
        if not path.exists():
            diagnostics.append(
                _diagnostic(
                    "P4002",
                    "missing_package_path",
                    pointer,
                    f"Package layout directory {raw_path!r} does not exist.",
                    details={"path": raw_path},
                )
            )
        elif not path.is_dir():
            diagnostics.append(
                _diagnostic(
                    "P4003",
                    "expected_package_directory",
                    pointer,
                    f"Package layout path {raw_path!r} must be a directory.",
                    details={"path": raw_path},
                )
            )
    return resolved, diagnostics


def _additional_layout_dirs(
    root: Path,
    *,
    require_exists: bool,
) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    resolved: dict[str, Path] = {}
    for raw_path in ADDITIONAL_PACKAGE_LAYOUT_DIRS:
        pointer = f"/layout/{raw_path}"
        path, diagnostic = _safe_path(root, raw_path, pointer)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        if path is None:
            continue
        resolved[raw_path] = path
        if not require_exists:
            continue
        if not path.exists():
            diagnostics.append(
                _diagnostic(
                    "P4002",
                    "missing_package_path",
                    pointer,
                    f"Package layout directory {raw_path!r} does not exist.",
                    details={"path": raw_path},
                )
            )
        elif not path.is_dir():
            diagnostics.append(
                _diagnostic(
                    "P4003",
                    "expected_package_directory",
                    pointer,
                    f"Package layout path {raw_path!r} must be a directory.",
                    details={"path": raw_path},
                )
            )
    return resolved, diagnostics


def _section_roots(section: str, layout_dirs: Mapping[str, Path], additional_dirs: Mapping[str, Path]) -> list[Path]:
    roots: list[Path] = []
    section_root = layout_dirs.get(section)
    if section_root is not None:
        roots.append(section_root)
    if section == "build":
        roots.extend(path for key, path in additional_dirs.items() if key in BUILD_PACKAGE_LAYOUT_DIRS)
    elif section == "renders":
        roots.extend(path for key, path in additional_dirs.items() if key in RENDER_PASS_PACKAGE_LAYOUT_DIRS)
    return roots


def _iter_package_refs(manifest: Mapping[str, Any]) -> Iterator[tuple[str, str, str, str]]:
    source = manifest.get("source")
    if isinstance(source, list):
        for index, item in enumerate(source):
            if isinstance(item, Mapping) and isinstance(item.get("path"), str):
                yield "source", f"/source/{index}/path", item["path"], "file"

    graph = manifest.get("graph")
    if isinstance(graph, Mapping):
        scene_graph = graph.get("scene_graph")
        if isinstance(scene_graph, str):
            yield "graph", "/graph/scene_graph", scene_graph, "file"
        normalized_scene_graph = graph.get("scene_graph_normalized")
        if isinstance(normalized_scene_graph, str):
            yield "graph", "/graph/scene_graph_normalized", normalized_scene_graph, "file"
        patches = graph.get("patches")
        if isinstance(patches, list):
            for index, path in enumerate(patches):
                if isinstance(path, str):
                    yield "graph", f"/graph/patches/{index}", path, "file"

    for section in ("build", "renders", "exports", "reports"):
        items = manifest.get(section)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
                continue
            expected_kind = "path" if section == "build" else "file"
            yield section, f"/{section}/{index}/path", item["path"], expected_kind


def check_scene_package_manifest(
    manifest: Mapping[str, Any],
    *,
    root: str | Path,
    require_exists: bool = True,
) -> list[dict[str, Any]]:
    """Return semantic and path-safety diagnostics for a package manifest."""
    package_root = Path(root)
    layout_dirs, diagnostics = _layout_dirs(manifest, package_root, require_exists=require_exists)
    additional_dirs, additional_diagnostics = _additional_layout_dirs(package_root, require_exists=require_exists)
    diagnostics.extend(additional_diagnostics)
    for section, pointer, raw_path, expected_kind in _iter_package_refs(manifest):
        path, diagnostic = _safe_path(package_root, raw_path, pointer)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        if path is None:
            continue

        section_roots = _section_roots(section, layout_dirs, additional_dirs)
        if section_roots and not any(_is_within(path, section_root) or path == section_root for section_root in section_roots):
            diagnostics.append(
                _diagnostic(
                    "P4004",
                    "package_path_outside_section",
                    pointer,
                    f"Package path {raw_path!r} must stay under the {section!r} section folder.",
                    details={
                        "path": raw_path,
                        "section": section,
                        "section_roots": [str(section_root) for section_root in section_roots],
                    },
                )
            )

        if not require_exists:
            continue
        path_ready = True
        if not path.exists():
            diagnostics.append(
                _diagnostic(
                    "P4002",
                    "missing_package_path",
                    pointer,
                    f"Package path {raw_path!r} does not exist.",
                    details={"path": raw_path},
                )
            )
            path_ready = False
        elif not _expected_path_kind(path, expected_kind):
            diagnostics.append(
                _diagnostic(
                    "P4003",
                    _wrong_kind_name(expected_kind),
                    pointer,
                    f"Package path {raw_path!r} is not the expected {expected_kind}.",
                    details={"path": raw_path, "expected_kind": expected_kind},
                )
            )
            path_ready = False
        if path_ready and section == "graph" and pointer == "/graph/scene_graph":
            diagnostics.extend(_check_scene_graph_scene_id(manifest, path, pointer))
    return diagnostics


def load_and_validate_scene_package_manifest(
    path: str | Path,
    *,
    require_exists: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load a package manifest and return schema plus path-safety diagnostics."""
    manifest_path = Path(path)
    payload, diagnostics = load_and_validate_contract(SCENE_PACKAGE_MANIFEST_CONTRACT, manifest_path)
    if diagnostics:
        return payload, diagnostics
    diagnostics.extend(check_scene_package_manifest(payload, root=manifest_path.parent, require_exists=require_exists))
    return payload, diagnostics


__all__ = [
    "ADDITIONAL_PACKAGE_LAYOUT_DIRS",
    "BUILD_PACKAGE_LAYOUT_DIRS",
    "CACHE_PACKAGE_LAYOUT_DIRS",
    "DEFAULT_PACKAGE_LAYOUT",
    "PACKAGE_SECTIONS",
    "RENDER_PASS_PACKAGE_LAYOUT_DIRS",
    "SCENE_PACKAGE_MANIFEST_CONTRACT",
    "SCENE_PACKAGE_MANIFEST_FILENAME",
    "SCENE_PACKAGE_MANIFEST_VERSION",
    "STANDARD_PACKAGE_LAYOUT_DIRS",
    "ScenePackageError",
    "check_scene_package_manifest",
    "get_scene_package_manifest_schema",
    "init_scene_package",
    "initial_scene_package_manifest",
    "load_and_validate_scene_package_manifest",
    "validate_scene_package_manifest_payload",
]
