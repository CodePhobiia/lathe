"""``lathe scene`` subcommands for scene packages and World Memory."""

from __future__ import annotations

import argparse
import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lathe.errors import LatheError
from lathe.paths import PathGuardError, safe_resolve

from ..scene import SCENE_PACKAGE_MANIFEST_FILENAME
from ..scene.io import write_json_atomic, write_text_atomic
from ..wonder.contracts import MAX_CONTRACT_BYTES
from ._common import _dump

WORLD_MEMORY_FILENAME = "world_memory.json"
SCENE_GRAPH_FILENAME = "scene_graph.json"
PACKAGE_WORLD_MEMORY_PATH = f"graph/{WORLD_MEMORY_FILENAME}"
PACKAGE_SCENE_GRAPH_PATH = f"graph/{SCENE_GRAPH_FILENAME}"


@dataclass(frozen=True)
class _PackageTarget:
    package_dir: Path
    manifest_path: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class _MemoryTarget:
    memory_path: Path
    package: _PackageTarget | None
    scene_graph_path: Path | None


def register(sub: argparse._SubParsersAction) -> None:
    """Register the ``scene`` command family."""
    p_scene = sub.add_parser(
        "scene",
        help="Operate on scene packages and World Memory",
        description="Operate on folder-based Scene Packages and World Memory JSON contracts.",
    )
    scene_sub = p_scene.add_subparsers(dest="scene_cmd", required=True)

    p_check = scene_sub.add_parser("check", help="Run schema and semantic checks for a Scene Graph JSON file")
    p_check.add_argument("scene")

    p_plan = scene_sub.add_parser("plan", help="Emit a deterministic Scene Plan for a Scene Graph JSON file")
    p_plan.add_argument("scene")
    p_plan.add_argument("--mode", choices=["preview", "final"], default="preview")
    p_plan.add_argument("--out", default=None, help="Optional output path for the Scene Plan JSON")
    p_plan.add_argument(
        "--reuse-from-plan",
        default=None,
        help="Optional base Scene Plan JSON used to report branch-safe asset cache reuse",
    )

    p_materialize = scene_sub.add_parser(
        "materialize",
        help="Lower a Scene Graph into generated Lathe asset source files",
    )
    p_materialize.add_argument("scene")
    p_materialize.add_argument("--out", required=True, help="Output directory for generated asset sources")
    p_materialize.add_argument("--mode", choices=["preview", "final"], default="preview")
    p_materialize.add_argument(
        "--build-assets",
        action="store_true",
        help="Run the Lathe asset build pipeline for generated sources and record build results",
    )

    p_build = scene_sub.add_parser("build", help="Build a deterministic offline Scene Package preview")
    p_build.add_argument("scene")
    p_build.add_argument("--out", required=True, help="Output directory root for the Scene Package")
    p_build.add_argument("--mode", choices=["preview", "final"], default="preview")
    p_build.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_build.add_argument(
        "--deterministic",
        action="store_true",
        help="Record deterministic scene-build policy in emitted reports and manifests",
    )
    p_build.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Explicitly allow deterministic proxy/fallback policy where the scene executor supports it",
    )
    p_build.add_argument(
        "--strict",
        action="store_true",
        help="Fail on scene validation warnings and supported provider/fallback diagnostics",
    )
    p_build.add_argument(
        "--build-assets",
        action="store_true",
        help="Materialize generated scene asset sources and run the Lathe asset build pipeline before packaging",
    )

    p_render = scene_sub.add_parser("render", help="Render deterministic proxy PNG passes for a Scene Graph")
    p_render.add_argument("scene")
    p_render.add_argument("--out", required=True, help="Output directory for render artifacts")
    p_render.add_argument("--camera", default=None, help="Optional camera_id to render")
    p_render.add_argument(
        "--all-cameras",
        action="store_true",
        help=(
            "Render every authored camera plus the generated topdown debug camera; "
            "this is the default when --camera is omitted"
        ),
    )
    p_render.add_argument("--mode", choices=["preview", "final"], default="preview")
    p_render.add_argument(
        "--passes",
        default=None,
        help="Comma-separated render passes; defaults to the selected mode",
    )
    p_render.add_argument("--width", type=int, default=None, help="Optional render width")
    p_render.add_argument("--height", type=int, default=None, help="Optional render height")
    p_render.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Optional wall-clock timeout for deterministic proxy render artifact generation",
    )

    p_export = scene_sub.add_parser("export", help="Export deterministic proxy scene artifacts")
    p_export.add_argument("scene")
    p_export.add_argument("--out", required=True, help="Output directory for export artifacts")
    p_export.add_argument("--target", choices=["glb", "usd", "blender"], default="glb")
    p_export.add_argument("--mode", choices=["preview", "final"], default="preview")
    p_export.add_argument(
        "--include-collision-proxies",
        action="store_true",
        help="Include deterministic simple-box collision proxy nodes in supported scene exports",
    )
    p_export.add_argument(
        "--include-id-mask-bundle",
        action="store_true",
        help="Include export-side object ID mask PNGs and object-index sidecars",
    )

    p_validate = scene_sub.add_parser("validate", help="Run scene quality validators for a Scene Graph JSON file")
    p_validate.add_argument("scene")
    p_validate.add_argument(
        "--require-export-artifacts",
        action="store_true",
        help="Require referenced export artifacts to exist",
    )
    p_validate.add_argument("--platform", default=None, help="Optional platform validator target, for example roblox")

    p_bench = scene_sub.add_parser("bench", help="Emit a deterministic Wonder Scene Benchmark Report")
    p_bench.add_argument("scene")
    p_bench.add_argument("--timings", required=True, help="JSON file with measured stage timings")
    p_bench.add_argument("--scores", required=True, help="JSON file with measured benchmark scores")
    p_bench.add_argument("--out", default=None, help="Optional output path for the benchmark report JSON")

    p_style_pack = scene_sub.add_parser("style-pack", help="Extract and validate a Style Pack from a Scene Graph")
    p_style_pack.add_argument("scene", nargs="?", help="Scene Graph JSON file; omit when using --builtin")
    p_style_pack.add_argument("--builtin", default=None, help="Curated built-in Style Pack id to emit")
    p_style_pack.add_argument("--style-pack-id", default=None)
    p_style_pack.add_argument("--display-name", default=None)
    p_style_pack.add_argument("--out", required=True, help="Output path for the Style Pack JSON")

    p_layout = scene_sub.add_parser("layout", help="Emit deterministic Layout Plan JSON for a Scene Graph")
    p_layout.add_argument("scene")
    p_layout.add_argument("--style-pack", default=None, help="Optional Style Pack JSON for instance reuse policy")
    p_layout.add_argument("--out", required=True, help="Output path for the Layout Plan JSON")

    p_camera_lighting = scene_sub.add_parser("camera-lighting", help="Emit deterministic camera/lighting plan JSON")
    p_camera_lighting.add_argument("scene")
    p_camera_lighting.add_argument("--layout-plan", default=None, help="Optional Layout Plan JSON for resolved positions")
    p_camera_lighting.add_argument("--out", required=True, help="Output path for the camera/lighting plan JSON")

    p_assemble = scene_sub.add_parser("assemble", help="Emit deterministic Scene Assembly IR for a Scene Graph")
    p_assemble.add_argument("scene")
    p_assemble.add_argument("--out", required=True, help="Output path for the Scene Assembly IR JSON")

    p_roblox_manifest = scene_sub.add_parser("roblox-manifest", help="Emit a Roblox profile validation manifest")
    p_roblox_manifest.add_argument("scene")
    p_roblox_manifest.add_argument(
        "--profile",
        default=None,
        help="Roblox profile JSON path; defaults to the built-in roblox_lowpoly profile",
    )
    p_roblox_manifest.add_argument("--out", default=None, help="Optional output path for the Roblox manifest JSON")

    p_roblox_export = scene_sub.add_parser("roblox-export", help="Export a Roblox asset-kit GLB folder")
    p_roblox_export.add_argument("scene")
    p_roblox_export.add_argument("--out", required=True, help="Output directory for the Roblox asset-kit bundle")
    p_roblox_export.add_argument("--mode", choices=["preview", "final"], default="preview")
    p_roblox_export.add_argument(
        "--profile",
        default=None,
        help="Roblox profile JSON path; defaults to the built-in roblox_lowpoly profile",
    )
    p_roblox_export.add_argument(
        "--no-collision-proxies",
        action="store_true",
        help="Do not include deterministic simple-box collision proxy nodes in the GLB",
    )

    p_patch = scene_sub.add_parser("patch", help="Apply a Scene Patch JSON file to a Scene Graph JSON file")
    p_patch.add_argument("scene")
    p_patch.add_argument("patch_json")
    p_patch.add_argument("--out", required=True, help="Output path for the updated Scene Graph JSON")
    p_patch.add_argument("--preview", action="store_true", help="Emit the patch result without writing --out")

    p_branch = scene_sub.add_parser("branch", help="Create deterministic scene branch/version metadata")
    p_branch.add_argument("scene")
    p_branch.add_argument("--name", required=True, help="Branch display name")
    p_branch.add_argument("--parent", default="main", help="Parent branch id")
    p_branch.add_argument("--out", required=True, help="Output path for the Scene Branch JSON")

    p_diff = scene_sub.add_parser("diff", help="Diff two Scene Graph JSON files")
    p_diff.add_argument("left")
    p_diff.add_argument("right")
    p_diff.add_argument("--out", default=None, help="Optional output path for the Scene Diff JSON")

    p_merge = scene_sub.add_parser("merge", help="Merge non-overlapping Scene Graph changes")
    p_merge.add_argument("source")
    p_merge.add_argument("--into", required=True, dest="target", help="Target Scene Graph JSON")
    p_merge.add_argument("--out", required=True, help="Output path for the merged Scene Graph JSON")

    p_rollback = scene_sub.add_parser("rollback", help="Rollback a Scene Graph using hash-guarded Scene History")
    p_rollback.add_argument("scene")
    p_rollback.add_argument("--history", required=True, help="Scene History JSON path")
    p_rollback.add_argument("--to", required=True, dest="to_event", help="Scene History event_id or version marker")
    p_rollback.add_argument("--out", required=True, help="Output path for the rolled-back Scene Graph JSON")

    p_inspect_render = scene_sub.add_parser("inspect-render", help="Validate Render Inspection JSON against a scene")
    p_inspect_render.add_argument("scene")
    p_inspect_render.add_argument("render_inspection")

    p_propose_repairs = scene_sub.add_parser("propose-repairs", help="Convert Render Inspection JSON to Scene Patch proposals")
    p_propose_repairs.add_argument("scene")
    p_propose_repairs.add_argument("render_inspection")
    p_propose_repairs.add_argument("--goal", choices=["wonder_preview", "export_ready", "roblox_ready"], default="wonder_preview")
    p_propose_repairs.add_argument("--out", default=None, help="Optional output path for the Scene Repair Report JSON")

    p_repair = scene_sub.add_parser("repair", help="Run deterministic offline repair proposals")
    p_repair.add_argument("scene")
    p_repair.add_argument("render_inspection")
    p_repair.add_argument("--goal", choices=["wonder_preview", "export_ready", "roblox_ready"], default="wonder_preview")
    p_repair.add_argument("--max-rounds", type=int, default=3)
    p_repair.add_argument("--out", required=True, help="Output path for the repaired Scene Graph JSON")
    p_repair.add_argument("--report-out", default=None, help="Optional output path for the Scene Repair Report JSON")

    p_curiosity = scene_sub.add_parser("curiosity", help="Summarize curiosity anchors as deterministic cards")
    p_curiosity.add_argument("scene")

    p_expand_anchor = scene_sub.add_parser("expand-anchor", help="Expand a curiosity anchor option into a Scene Graph copy")
    p_expand_anchor.add_argument("scene")
    p_expand_anchor.add_argument("anchor_id")
    p_expand_anchor.add_argument("--option", required=True, dest="option_id")
    p_expand_anchor.add_argument("--out", required=True, help="Output path for the expanded Scene Graph JSON")

    p_scene_graph_to_source = scene_sub.add_parser(
        "scene-graph-to-source",
        help="Convert Scene Graph JSON into generated scene source",
    )
    p_scene_graph_to_source.add_argument("scene_graph")
    p_scene_graph_to_source.add_argument("--out", required=True, help="Output generated .lth scene source path")

    p_source_to_scene_graph = scene_sub.add_parser(
        "source-to-scene-graph",
        help="Extract Scene Graph JSON from generated scene source",
    )
    p_source_to_scene_graph.add_argument("scene_source")
    p_source_to_scene_graph.add_argument("--out", required=True, help="Output Scene Graph JSON path")

    p_package = scene_sub.add_parser("package", help="Inspect, initialize, and validate scene packages")
    package_sub = p_package.add_subparsers(dest="scene_package_cmd", required=True)

    p_package_init = package_sub.add_parser("init", help="Create a folder-based Scene Package skeleton")
    p_package_init.add_argument("package_dir")
    p_package_init.add_argument("--scene-id", required=True)
    p_package_init.add_argument("--package-id", default=None)
    p_package_init.add_argument(
        "--force",
        action="store_true",
        help=f"Overwrite an existing {SCENE_PACKAGE_MANIFEST_FILENAME}",
    )

    p_package_inspect = package_sub.add_parser("inspect", help="Inspect a Scene Package manifest")
    p_package_inspect.add_argument("package_dir")

    p_package_validate = package_sub.add_parser(
        "validate",
        help="Validate a Scene Package directory or manifest",
    )
    p_package_validate.add_argument("package_dir_or_manifest")
    p_package_validate.add_argument(
        "--allow-missing-paths",
        action="store_true",
        help="Validate schema and path safety without requiring referenced package paths to exist",
    )

    p_memory = scene_sub.add_parser("memory", help="Inspect and append World Memory events")
    memory_sub = p_memory.add_subparsers(dest="scene_memory_cmd", required=True)

    p_memory_inspect = memory_sub.add_parser("inspect", help="Inspect a World Memory JSON file")
    p_memory_inspect.add_argument("package_dir_or_memory_json")
    p_memory_inspect.add_argument(
        "--scene-graph",
        default=None,
        help="Optional Scene Graph JSON file for affected_id continuity checks",
    )

    p_memory_append = memory_sub.add_parser("append", help="Append one event to a World Memory JSON file")
    p_memory_append.add_argument("package_dir_or_memory_json")
    p_memory_append.add_argument("event_json")
    p_memory_append.add_argument(
        "--scene-graph",
        default=None,
        help="Optional Scene Graph JSON file for affected_id continuity checks",
    )


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    contract: str | None = None,
    phase: str = "scene_cli",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "phase": phase,
        "path": path,
        "message": message,
    }
    if contract is not None:
        payload["contract"] = contract
    if details is not None:
        payload["details"] = dict(details)
    return payload


def _emit_failure(payload: dict[str, Any], *, exit_code: int = 1) -> None:
    _dump(payload)
    raise SystemExit(exit_code)


def _direct_path(raw_path: str | Path) -> tuple[Path | None, list[dict[str, Any]]]:
    path = Path(raw_path)
    root = path.parent if path.parent != Path() else Path()
    try:
        return safe_resolve(root, path.name), []
    except PathGuardError as exc:
        return None, [
            _diagnostic(
                "SCENE_CLI_UNSAFE_PATH",
                "unsafe_cli_path",
                "/path",
                f"Path {str(raw_path)!r} is unsafe: {exc}",
                details={"path": str(raw_path)},
            )
        ]


def _package_manifest_path(target: str | Path) -> tuple[Path, Path, list[dict[str, Any]]]:
    path = Path(target)
    if path.is_file() or path.suffix.lower() == ".json":
        package_dir = path.parent
        manifest_user_path = path.name
    else:
        package_dir = path
        manifest_user_path = SCENE_PACKAGE_MANIFEST_FILENAME
    try:
        manifest_path = safe_resolve(package_dir, manifest_user_path)
    except PathGuardError as exc:
        manifest_path = package_dir / manifest_user_path
        return package_dir, manifest_path, [
            _diagnostic(
                "P4901",
                "unsafe_scene_package_manifest_path",
                "/scene_package_manifest",
                f"Scene Package manifest path is unsafe: {exc}",
                contract="scene_package_manifest",
                phase="scene_package_manifest_semantics",
                details={"path": str(manifest_path), "package_dir": str(package_dir)},
            )
        ]
    return package_dir, manifest_path, []


def _load_package_target(
    target: str | Path,
    *,
    require_exists: bool,
) -> tuple[_PackageTarget | None, list[dict[str, Any]]]:
    from ..scene import load_and_validate_scene_package_manifest

    package_dir, manifest_path, diagnostics = _package_manifest_path(target)
    if diagnostics:
        return None, diagnostics
    try:
        manifest, diagnostics = load_and_validate_scene_package_manifest(
            manifest_path,
            require_exists=require_exists,
        )
    except (LatheError, OSError) as exc:
        return None, [
            _diagnostic(
                "P4902",
                "scene_package_manifest_load_failed",
                "/scene_package_manifest",
                str(exc),
                contract="scene_package_manifest",
                phase="scene_package_manifest_load",
                details={"path": str(manifest_path), "package_dir": str(package_dir)},
            )
        ]
    return _PackageTarget(package_dir=package_dir, manifest_path=manifest_path, manifest=manifest), diagnostics


def _package_relative_path(
    package_dir: Path,
    relative_path: str,
    pointer: str,
    *,
    contract: str,
) -> tuple[Path | None, list[dict[str, Any]]]:
    try:
        return safe_resolve(package_dir, relative_path), []
    except PathGuardError as exc:
        return None, [
            _diagnostic(
                "P4001",
                "unsafe_package_path",
                pointer,
                f"Package path {relative_path!r} is not a safe package-relative path: {exc}",
                contract=contract,
                phase="scene_package_manifest_semantics",
                details={"path": relative_path, "root": str(package_dir)},
            )
        ]


def _package_scene_graph_path(package: _PackageTarget) -> tuple[Path | None, list[dict[str, Any]]]:
    graph = package.manifest.get("graph")
    if isinstance(graph, Mapping) and isinstance(graph.get("scene_graph"), str):
        return _package_relative_path(
            package.package_dir,
            graph["scene_graph"],
            "/graph/scene_graph",
            contract="scene_package_manifest",
        )
    conventional = package.package_dir / PACKAGE_SCENE_GRAPH_PATH
    if not conventional.exists():
        return None, []
    return _package_relative_path(
        package.package_dir,
        PACKAGE_SCENE_GRAPH_PATH,
        "/graph/scene_graph",
        contract="scene_package_manifest",
    )


def _resolve_memory_target(raw_target: str | Path, *, require_package_paths: bool) -> tuple[_MemoryTarget | None, list[dict[str, Any]]]:
    target = Path(raw_target)
    if target.is_dir():
        package, diagnostics = _load_package_target(target, require_exists=require_package_paths)
        if diagnostics:
            return None, diagnostics
        if package is None:
            return None, []
        memory_path, diagnostics = _package_relative_path(
            package.package_dir,
            PACKAGE_WORLD_MEMORY_PATH,
            "/graph/world_memory",
            contract="world_memory",
        )
        if diagnostics:
            return None, diagnostics
        scene_graph_path, diagnostics = _package_scene_graph_path(package)
        if diagnostics:
            return None, diagnostics
        return _MemoryTarget(memory_path=memory_path, package=package, scene_graph_path=scene_graph_path), []

    memory_path, diagnostics = _direct_path(target)
    if diagnostics:
        return None, diagnostics
    return _MemoryTarget(memory_path=memory_path, package=None, scene_graph_path=None), []


def _load_scene_graph_payload(scene_graph_path: Path | None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if scene_graph_path is None:
        return None, []
    from ..scene import load_and_check_scene_graph

    try:
        scene_graph, diagnostics = load_and_check_scene_graph(scene_graph_path)
    except (LatheError, OSError) as exc:
        return None, [
            _diagnostic(
                "S1901",
                "scene_graph_load_failed",
                "/scene_graph",
                str(exc),
                contract="scene_graph",
                phase="scene_graph_load",
                details={"path": str(scene_graph_path)},
            )
        ]
    return scene_graph, diagnostics


def _load_world_memory_payload(
    memory_path: Path,
    *,
    scene_graph: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from ..scene.memory import load_and_validate_world_memory

    try:
        return load_and_validate_world_memory(memory_path, scene_graph=scene_graph)
    except (LatheError, OSError) as exc:
        return {}, [
            _diagnostic(
                "M1901",
                "world_memory_load_failed",
                "/world_memory",
                str(exc),
                contract="world_memory",
                phase="world_memory_load",
                details={"path": str(memory_path)},
            )
        ]


def _load_event_payload(event_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path, diagnostics = _direct_path(event_path)
    if diagnostics:
        return {}, diagnostics
    if path is None:
        return {}, [
            _diagnostic(
                "M1910",
                "memory_event_path_unresolved",
                "/event",
                f"Memory event path could not be resolved: {event_path}",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(event_path)},
            )
        ]
    try:
        stat_result = path.stat()
    except FileNotFoundError:
        return {}, [
            _diagnostic(
                "M1902",
                "memory_event_file_not_found",
                "/event",
                f"Memory event file not found: {path}",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(path)},
            )
        ]
    except OSError as exc:
        return {}, [
            _diagnostic(
                "M1907",
                "memory_event_stat_failed",
                "/event",
                f"Memory event file could not be inspected: {exc}",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(path)},
            )
        ]
    if stat_result.st_size > MAX_CONTRACT_BYTES:
        return {}, [
            _diagnostic(
                "M1908",
                "memory_event_too_large",
                "/event",
                f"Memory event file exceeds 2 MiB ({stat_result.st_size} bytes > {MAX_CONTRACT_BYTES}): {path}",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(path), "size_bytes": stat_result.st_size},
            )
        ]
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, [
            _diagnostic(
                "M1902",
                "memory_event_file_not_found",
                "/event",
                f"Memory event file not found: {path}",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(path)},
            )
        ]
    except OSError as exc:
        return {}, [
            _diagnostic(
                "M1909",
                "memory_event_read_failed",
                "/event",
                f"Memory event file could not be read: {exc}",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(path)},
            )
        ]
    except UnicodeDecodeError as exc:
        return {}, [
            _diagnostic(
                "M1903",
                "memory_event_not_utf8",
                "/event",
                f"Memory event file is not valid UTF-8: {exc}",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(path)},
            )
        ]
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        return {}, [
            _diagnostic(
                "M1904",
                "memory_event_invalid_json",
                "/event",
                f"Memory event file contains invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(path)},
            )
        ]
    if not isinstance(raw, dict):
        return {}, [
            _diagnostic(
                "M1905",
                "memory_event_root_not_object",
                "/event",
                f"Memory event root must be a JSON object, got {type(raw).__name__}.",
                contract="world_memory",
                phase="memory_event_load",
                details={"path": str(path)},
            )
        ]
    return raw, []


def _event_id(event: Mapping[str, Any]) -> str | None:
    value = event.get("event_id")
    return value if isinstance(value, str) else None


def _existing_event(world_memory: Mapping[str, Any], event_id: str) -> Mapping[str, Any] | None:
    events = world_memory.get("events", [])
    if not isinstance(events, list):
        return None
    for event in events:
        if isinstance(event, Mapping) and event.get("event_id") == event_id:
            return event
    return None


def _memory_counts(world_memory: Mapping[str, Any]) -> dict[str, int]:
    events = world_memory.get("events", [])
    branches = world_memory.get("branches", [])
    constraints = world_memory.get("continuity_constraints", [])
    return {
        "events": len(events) if isinstance(events, list) else 0,
        "branches": len(branches) if isinstance(branches, list) else 0,
        "continuity_constraints": len(constraints) if isinstance(constraints, list) else 0,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_json_atomic(path, payload)


def _write_text(path: Path, text: str) -> None:
    write_text_atomic(path, text)


def _display_path(path: str | Path | None) -> str | None:
    """Return a stable display path without leaking the local checkout root."""
    if path is None:
        return None
    path_obj = Path(path)
    try:
        relative = path_obj.resolve(strict=False).relative_to(Path.cwd().resolve(strict=False))
    except ValueError:
        return str(path_obj)
    return relative.as_posix()


def _load_checked_scene_graph(scene_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from ..scene import load_and_check_scene_graph

    try:
        return load_and_check_scene_graph(scene_path)
    except (LatheError, OSError) as exc:
        return {}, [
            _diagnostic(
                "S1901",
                "scene_graph_load_failed",
                "/scene_graph",
                str(exc),
                contract="scene_graph",
                phase="scene_graph_load",
                details={"path": str(scene_path)},
            )
        ]


def _has_error_diagnostic(diagnostics: list[dict[str, Any]]) -> bool:
    return any(diagnostic.get("severity") == "error" for diagnostic in diagnostics)


def _load_scene_patch_payload(patch_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from ..wonder import load_and_validate_contract

    try:
        return load_and_validate_contract("scene_patch", patch_path)
    except (LatheError, OSError) as exc:
        return {}, [
            _diagnostic(
                "SP1901",
                "scene_patch_load_failed",
                "/scene_patch",
                str(exc),
                contract="scene_patch",
                phase="scene_patch_load",
                details={"path": str(patch_path)},
            )
        ]


def _load_render_inspection_payload(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from ..wonder import load_and_validate_contract

    try:
        return load_and_validate_contract("render_inspection", path)
    except (LatheError, OSError) as exc:
        return {}, [
            _diagnostic(
                "RR1901",
                "render_inspection_load_failed",
                "/render_inspection",
                str(exc),
                contract="render_inspection",
                phase="render_inspection_load",
                details={"path": str(path)},
            )
        ]


def _load_json_mapping_payload(
    path: str | Path,
    *,
    contract: str,
    phase: str,
    code_prefix: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path_obj = Path(path)
    try:
        stat_result = path_obj.stat()
    except FileNotFoundError:
        return {}, [
            _diagnostic(
                f"{code_prefix}1901",
                "json_file_not_found",
                "/",
                f"JSON file not found: {path_obj}",
                contract=contract,
                phase=phase,
                details={"path": str(path_obj)},
            )
        ]
    except OSError as exc:
        return {}, [
            _diagnostic(
                f"{code_prefix}1902",
                "json_file_stat_failed",
                "/",
                f"JSON file could not be inspected: {exc}",
                contract=contract,
                phase=phase,
                details={"path": str(path_obj)},
            )
        ]
    if stat_result.st_size > MAX_CONTRACT_BYTES:
        return {}, [
            _diagnostic(
                f"{code_prefix}1903",
                "json_file_too_large",
                "/",
                f"JSON file exceeds 2 MiB ({stat_result.st_size} bytes > {MAX_CONTRACT_BYTES}): {path_obj}",
                contract=contract,
                phase=phase,
                details={"path": str(path_obj), "size_bytes": stat_result.st_size},
            )
        ]
    try:
        text = path_obj.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        return {}, [
            _diagnostic(
                f"{code_prefix}1904",
                "json_file_not_utf8",
                "/",
                f"JSON file is not valid UTF-8: {exc}",
                contract=contract,
                phase=phase,
                details={"path": str(path_obj)},
            )
        ]
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        return {}, [
            _diagnostic(
                f"{code_prefix}1905",
                "json_file_invalid_json",
                "/",
                f"JSON file contains invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}",
                contract=contract,
                phase=phase,
                details={"path": str(path_obj)},
            )
        ]
    if not isinstance(raw, dict):
        return {}, [
            _diagnostic(
                f"{code_prefix}1906",
                "json_file_root_not_object",
                "/",
                f"JSON root must be an object, got {type(raw).__name__}.",
                contract=contract,
                phase=phase,
                details={"path": str(path_obj)},
            )
        ]
    return raw, []


def _post_validation_rejected_patch_event(
    patch_event: Mapping[str, Any],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    event = copy.deepcopy(dict(patch_event))
    metadata = event.get("metadata")
    if isinstance(metadata, dict):
        metadata["status"] = "rejected"
        metadata["post_validation_failed"] = True
    patch_id = str(event.get("patch_id", metadata.get("patch_id") if isinstance(metadata, dict) else "patch_unknown"))
    event["text"] = f"Scene patch {patch_id} rejected: patched Scene Graph failed post-application validation."
    event["diagnostic_codes"] = [
        diagnostic["code"]
        for diagnostic in diagnostics
        if isinstance(diagnostic, Mapping) and isinstance(diagnostic.get("code"), str)
    ]
    return event


def _without_scene_memory_event(
    scene_graph: Mapping[str, Any],
    scene_memory_event: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if scene_memory_event is None:
        return copy.deepcopy(dict(scene_graph))
    event_id = scene_memory_event.get("event_id")
    updated = copy.deepcopy(dict(scene_graph))
    events = updated.get("memory_events")
    if isinstance(events, list):
        updated["memory_events"] = [
            event
            for event in events
            if not (isinstance(event, Mapping) and event.get("event_id") == event_id)
        ]
    return updated


def _run_check(args: argparse.Namespace) -> None:
    from ..scene import scene_graph_validation_summary

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    ok = not diagnostics
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.check",
        "contract": "scene_graph",
        "path": args.scene,
        "scene_id": scene_graph.get("scene_id"),
        "summary": scene_graph_validation_summary(scene_graph, diagnostics),
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_plan(args: argparse.Namespace) -> None:
    from ..scene import plan_scene, validate_scene_plan_payload

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.plan",
                "contract": "scene_graph",
                "path": args.scene,
                "mode": args.mode,
                "diagnostics": diagnostics,
            }
        )

    reuse_from_plan = None
    if args.reuse_from_plan is not None:
        reuse_from_plan, reuse_diagnostics = _load_json_mapping_payload(
            args.reuse_from_plan,
            contract="scene_plan",
            phase="scene_plan_reuse_load",
            code_prefix="SP",
        )
        reuse_diagnostics.extend(validate_scene_plan_payload(reuse_from_plan))
        if _has_error_diagnostic(reuse_diagnostics):
            _emit_failure(
                {
                    "ok": False,
                    "command": "scene.plan",
                    "contract": "scene_plan",
                    "path": args.scene,
                    "mode": args.mode,
                    "reuse_from_plan": args.reuse_from_plan,
                    "diagnostics": reuse_diagnostics,
                }
            )

    plan = plan_scene(scene_graph, mode=args.mode, reuse_from_plan=reuse_from_plan)
    plan_diagnostics = validate_scene_plan_payload(plan)
    diagnostics = [*plan.get("diagnostics", []), *plan_diagnostics]
    ok = not _has_error_diagnostic(diagnostics)
    if args.out is not None and ok:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, plan)

    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.plan",
        "contract": "scene_plan",
        "path": args.scene,
        "mode": args.mode,
        "out": args.out,
        "reuse_from_plan": args.reuse_from_plan,
        "plan": plan,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_materialize(args: argparse.Namespace) -> None:
    from ..scene import SceneMaterializeError, materialize_scene_assets

    try:
        payload = materialize_scene_assets(args.scene, args.out, mode=args.mode, build_assets=bool(args.build_assets))
    except SceneMaterializeError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.materialize",
                "contract": "scene_materialization_manifest",
                "path": args.scene,
                "out": args.out,
                "mode": args.mode,
                "build_assets": bool(args.build_assets),
                "diagnostics": exc.diagnostics,
            }
        )
    except (LatheError, OSError, ValueError) as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.materialize",
                "contract": "scene_materialization_manifest",
                "path": args.scene,
                "out": args.out,
                "mode": args.mode,
                "build_assets": bool(args.build_assets),
                "diagnostics": [
                    _diagnostic(
                        "SM1900",
                        "scene_materialization_failed",
                        "/scene_materialization",
                        str(exc),
                        contract="scene_materialization_manifest",
                        phase="scene_materialization",
                        details={"path": args.scene, "out": args.out, "mode": args.mode},
                    )
                ],
            }
        )
    payload["out"] = _display_path(payload.get("out"))
    if payload["ok"]:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_validate(args: argparse.Namespace) -> None:
    from ..scene import run_scene_validators

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.validate",
                "contract": "scene_graph",
                "path": args.scene,
                "diagnostics": diagnostics,
            }
        )

    report = run_scene_validators(
        scene_graph,
        root=Path(args.scene).parent,
        require_export_artifacts=args.require_export_artifacts,
        platform=args.platform,
    )
    ok = report.get("status") != "failed"
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.validate",
        "contract": "scene_quality_report",
        "path": args.scene,
        "report": report,
        "diagnostics": report.get("diagnostics", []),
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_bench(args: argparse.Namespace) -> None:
    from ..scene import benchmark_scene, validate_scene_benchmark_report_payload

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.bench",
                "contract": "scene_graph",
                "path": args.scene,
                "diagnostics": diagnostics,
            }
        )
    timings, diagnostics = _load_json_mapping_payload(
        args.timings,
        contract="scene_benchmark_report",
        phase="scene_benchmark_timings_load",
        code_prefix="SBENCH",
    )
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.bench",
                "contract": "scene_benchmark_report",
                "path": args.scene,
                "timings": args.timings,
                "scores": args.scores,
                "diagnostics": diagnostics,
            }
        )
    scores, diagnostics = _load_json_mapping_payload(
        args.scores,
        contract="scene_benchmark_report",
        phase="scene_benchmark_scores_load",
        code_prefix="SBENCH",
    )
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.bench",
                "contract": "scene_benchmark_report",
                "path": args.scene,
                "timings": args.timings,
                "scores": args.scores,
                "diagnostics": diagnostics,
            }
        )

    try:
        report = benchmark_scene(scene_graph, timings, scores)
    except ValueError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.bench",
                "contract": "scene_benchmark_report",
                "path": args.scene,
                "timings": args.timings,
                "scores": args.scores,
                "diagnostics": [
                    _diagnostic(
                        "SBENCH1907",
                        "scene_benchmark_input_invalid",
                        "/",
                        str(exc),
                        contract="scene_benchmark_report",
                        phase="scene_benchmark_inputs",
                    )
                ],
            }
        )

    diagnostics = validate_scene_benchmark_report_payload(report)
    if report.get("status") == "failed":
        diagnostics.append(
            _diagnostic(
                "SBENCH2001",
                "scene_benchmark_failed",
                "/status",
                "Scene benchmark report status is failed.",
                contract="scene_benchmark_report",
                phase="scene_benchmark_report",
                details={"status": report.get("status")},
            )
        )
    if args.out is not None and not diagnostics:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, report)
    ok = not diagnostics
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.bench",
        "contract": "scene_benchmark_report",
        "path": args.scene,
        "timings": args.timings,
        "scores": args.scores,
        "out": _display_path(args.out),
        "report": report,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_style_pack(args: argparse.Namespace) -> None:
    from ..scene import extract_style_pack, get_builtin_style_pack, validate_style_pack_payload

    if args.builtin is not None and args.scene is not None:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.style-pack",
                "contract": "style_pack",
                "path": args.scene,
                "out": args.out,
                "builtin": args.builtin,
                "diagnostics": [
                    _diagnostic(
                        "ST1901",
                        "style_pack_source_conflict",
                        "/style_pack",
                        "Use either a Scene Graph path or --builtin, not both.",
                        contract="style_pack",
                        phase="style_pack_cli",
                    )
                ],
            }
        )
    if args.builtin is not None:
        try:
            style_pack = get_builtin_style_pack(args.builtin)
        except KeyError as exc:
            _emit_failure(
                {
                    "ok": False,
                    "command": "scene.style-pack",
                    "contract": "style_pack",
                    "path": args.scene,
                    "out": args.out,
                    "builtin": args.builtin,
                    "diagnostics": [
                        _diagnostic(
                            "ST1902",
                            "unknown_builtin_style_pack",
                            "/builtin",
                            str(exc),
                            contract="style_pack",
                            phase="style_pack_cli",
                            details={"builtin": args.builtin},
                        )
                    ],
                }
            )
    else:
        if args.scene is None:
            _emit_failure(
                {
                    "ok": False,
                    "command": "scene.style-pack",
                    "contract": "style_pack",
                    "path": args.scene,
                    "out": args.out,
                    "builtin": args.builtin,
                    "diagnostics": [
                        _diagnostic(
                            "ST1903",
                            "style_pack_source_missing",
                            "/scene",
                            "A Scene Graph path is required unless --builtin is provided.",
                            contract="style_pack",
                            phase="style_pack_cli",
                        )
                    ],
                }
            )
        scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
        if diagnostics:
            _emit_failure(
                {
                    "ok": False,
                    "command": "scene.style-pack",
                    "contract": "scene_graph",
                    "path": args.scene,
                    "out": args.out,
                    "builtin": args.builtin,
                    "diagnostics": diagnostics,
                }
            )
        style_pack = extract_style_pack(
            scene_graph,
            style_pack_id=args.style_pack_id,
            display_name=args.display_name,
        )
    diagnostics = validate_style_pack_payload(style_pack)
    if not diagnostics:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, style_pack)
    ok = not diagnostics
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.style-pack",
        "contract": "style_pack",
        "path": args.scene,
        "out": _display_path(args.out),
        "builtin": args.builtin,
        "style_pack": style_pack,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_layout(args: argparse.Namespace) -> None:
    from ..scene import plan_layout, validate_layout_plan_payload

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.layout",
                "contract": "scene_graph",
                "path": args.scene,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )
    style_pack = None
    if args.style_pack is not None:
        style_pack, diagnostics = _load_json_mapping_payload(
            args.style_pack,
            contract="style_pack",
            phase="style_pack_load",
            code_prefix="ST",
        )
        if diagnostics:
            _emit_failure(
                {
                    "ok": False,
                    "command": "scene.layout",
                    "contract": "style_pack",
                    "path": args.scene,
                    "style_pack": args.style_pack,
                    "out": args.out,
                    "diagnostics": diagnostics,
                }
            )
    layout_plan = plan_layout(scene_graph, style_pack=style_pack)
    diagnostics = validate_layout_plan_payload(layout_plan)
    if not diagnostics:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, layout_plan)
    ok = not diagnostics
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.layout",
        "contract": "layout_plan",
        "path": args.scene,
        "style_pack": args.style_pack,
        "out": _display_path(args.out),
        "layout_plan": layout_plan,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_camera_lighting(args: argparse.Namespace) -> None:
    from ..scene import plan_camera_lighting

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.camera-lighting",
                "contract": "scene_graph",
                "path": args.scene,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )
    layout_plan = None
    if args.layout_plan is not None:
        layout_plan, diagnostics = _load_json_mapping_payload(
            args.layout_plan,
            contract="layout_plan",
            phase="layout_plan_load",
            code_prefix="LP",
        )
        if diagnostics:
            _emit_failure(
                {
                    "ok": False,
                    "command": "scene.camera-lighting",
                    "contract": "layout_plan",
                    "path": args.scene,
                    "layout_plan": args.layout_plan,
                    "out": args.out,
                    "diagnostics": diagnostics,
                }
            )
    plan = plan_camera_lighting(scene_graph, layout_plan=layout_plan)
    diagnostics = [diagnostic for diagnostic in plan.get("diagnostics", []) if diagnostic.get("severity") == "error"]
    if not diagnostics:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, plan)
    ok = not diagnostics
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.camera-lighting",
        "contract": "camera_lighting_plan",
        "path": args.scene,
        "layout_plan": args.layout_plan,
        "out": _display_path(args.out),
        "plan": plan,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_patch(args: argparse.Namespace) -> None:
    from ..scene import check_scene_graph
    from ..scene.patch import apply_scene_patch
    from ..wonder import validate_contract

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.patch",
                "contract": "scene_graph",
                "path": args.scene,
                "patch": args.patch_json,
                "out": args.out,
                "preview": args.preview,
                "diagnostics": diagnostics,
            }
        )

    patch_payload, diagnostics = _load_scene_patch_payload(args.patch_json)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.patch",
                "contract": "scene_patch",
                "path": args.scene,
                "patch": args.patch_json,
                "out": args.out,
                "preview": args.preview,
                "diagnostics": diagnostics,
            }
        )

    result = apply_scene_patch(scene_graph, patch_payload)
    out_path = Path(args.out)
    patch_diagnostics = list(result.diagnostics)
    diagnostics = list(patch_diagnostics)
    if not _has_error_diagnostic(diagnostics):
        diagnostics.extend(validate_contract("scene_graph", result.scene_graph))
    if not _has_error_diagnostic(diagnostics):
        diagnostics.extend(check_scene_graph(result.scene_graph, root=out_path.parent))
    ok = not _has_error_diagnostic(diagnostics)
    post_validation_failed = not _has_error_diagnostic(patch_diagnostics) and not ok

    written = False
    if ok and not args.preview:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, result.scene_graph)
        written = True

    patch_event = result.patch_event
    scene_memory_event = result.scene_memory_event
    scene_graph_for_payload = result.scene_graph
    if post_validation_failed:
        patch_event = _post_validation_rejected_patch_event(result.patch_event, diagnostics)
        scene_memory_event = None
        scene_graph_for_payload = _without_scene_memory_event(result.scene_graph, result.scene_memory_event)

    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.patch",
        "contract": "scene_patch",
        "path": args.scene,
        "patch": args.patch_json,
        "out": args.out,
        "preview": args.preview,
        "written": written,
        "patch_event": patch_event,
        "scene_memory_event": scene_memory_event,
        "applied_operations": result.applied_operations,
        "rejected_operations": result.rejected_operations,
        "scene_graph": scene_graph_for_payload,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_assemble(args: argparse.Namespace) -> None:
    from ..scene import assemble_scene, validate_scene_assembly_payload

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.assemble",
                "contract": "scene_graph",
                "path": args.scene,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )
    assembly = assemble_scene(scene_graph)
    out_path = Path(args.out)
    diagnostics = validate_scene_assembly_payload(assembly, package_root=out_path.parent)
    ok = not _has_error_diagnostic(diagnostics)
    written = False
    if ok:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, assembly)
        written = True
    payload = {
        "ok": ok,
        "command": "scene.assemble",
        "contract": "scene_assembly",
        "path": args.scene,
        "out": _display_path(out_path),
        "written": written,
        "assembly": assembly,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_roblox_manifest(args: argparse.Namespace) -> None:
    from ..scene import (
        ROBLOX_LOW_POLY_PROFILE,
        build_roblox_manifest,
        validate_roblox_manifest_payload,
        validate_roblox_profile,
        validate_roblox_profile_payload,
    )

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.roblox-manifest",
                "contract": "scene_graph",
                "path": args.scene,
                "profile": args.profile,
                "diagnostics": diagnostics,
            }
        )

    if args.profile is None:
        profile = copy.deepcopy(ROBLOX_LOW_POLY_PROFILE)
        profile_diagnostics: list[dict[str, Any]] = []
    else:
        profile, profile_diagnostics = _load_json_mapping_payload(
            args.profile,
            contract="roblox_profile",
            phase="roblox_profile_load",
            code_prefix="RB",
        )
    diagnostics = list(profile_diagnostics)
    if not diagnostics:
        diagnostics.extend(validate_roblox_profile_payload(profile))
    if not diagnostics:
        diagnostics.extend(validate_roblox_profile(scene_graph, profile))

    manifest = build_roblox_manifest(scene_graph, profile)
    manifest_diagnostics = validate_roblox_manifest_payload(manifest)
    diagnostics.extend(manifest_diagnostics)
    if args.out is not None and not manifest_diagnostics:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, manifest)

    ok = not diagnostics
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.roblox-manifest",
        "contract": "roblox_manifest",
        "path": args.scene,
        "profile": args.profile,
        "out": _display_path(args.out),
        "manifest": manifest,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_roblox_export(args: argparse.Namespace) -> None:
    from ..scene import ROBLOX_LOW_POLY_PROFILE, export_roblox_asset_kit
    from ..scene.artifacts import SceneArtifactError

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.roblox-export",
                "contract": "scene_graph",
                "path": args.scene,
                "profile": args.profile,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )

    if args.profile is None:
        profile = copy.deepcopy(ROBLOX_LOW_POLY_PROFILE)
        profile_diagnostics: list[dict[str, Any]] = []
    else:
        profile, profile_diagnostics = _load_json_mapping_payload(
            args.profile,
            contract="roblox_profile",
            phase="roblox_profile_load",
            code_prefix="RB",
        )
    if profile_diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.roblox-export",
                "contract": "roblox_profile",
                "path": args.scene,
                "profile": args.profile,
                "out": args.out,
                "diagnostics": profile_diagnostics,
            }
        )

    try:
        report = export_roblox_asset_kit(
            scene_graph,
            args.out,
            profile=profile,
            mode=args.mode,
            include_collision_nodes=not args.no_collision_proxies,
        )
    except SceneArtifactError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.roblox-export",
                "contract": "roblox_export",
                "path": args.scene,
                "profile": args.profile,
                "out": args.out,
                "diagnostics": exc.diagnostics,
            }
        )

    ok = not _has_error_diagnostic(report.get("diagnostics", []))
    payload = {
        "ok": ok,
        "command": "scene.roblox-export",
        "contract": "roblox_export",
        "path": args.scene,
        "profile": args.profile,
        "out": _display_path(args.out),
        "report": report,
        "diagnostics": report.get("diagnostics", []),
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_branch(args: argparse.Namespace) -> None:
    from ..scene import create_branch, validate_scene_branch_payload

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.branch",
                "contract": "scene_graph",
                "path": args.scene,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )
    try:
        branch = create_branch(scene_graph, args.name, parent=args.parent)
    except ValueError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.branch",
                "contract": "scene_branch",
                "path": args.scene,
                "out": args.out,
                "diagnostics": [
                    _diagnostic(
                        "SB1699",
                        "scene_branch_create_failed",
                        "/branch",
                        str(exc),
                        contract="scene_branch",
                        phase="scene_branch_create",
                    )
                ],
            }
        )
    diagnostics = validate_scene_branch_payload(branch)
    ok = not _has_error_diagnostic(diagnostics)
    out_path = Path(args.out)
    if ok:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, branch)
    payload = {
        "ok": ok,
        "command": "scene.branch",
        "contract": "scene_branch",
        "path": args.scene,
        "out": _display_path(out_path),
        "branch": branch,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_diff(args: argparse.Namespace) -> None:
    from ..scene import diff_scene_graphs, validate_scene_diff_payload

    left, diagnostics = _load_checked_scene_graph(args.left)
    if not diagnostics:
        right, diagnostics = _load_checked_scene_graph(args.right)
    else:
        right = {}
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.diff",
                "contract": "scene_graph",
                "left": args.left,
                "right": args.right,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )
    diff = diff_scene_graphs(left, right)
    diagnostics = validate_scene_diff_payload(diff)
    ok = not _has_error_diagnostic(diagnostics)
    if ok and args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, diff)
        out_display = _display_path(out_path)
    else:
        out_display = None
    payload = {
        "ok": ok,
        "command": "scene.diff",
        "contract": "scene_diff",
        "left": args.left,
        "right": args.right,
        "out": out_display,
        "diff": diff,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_merge(args: argparse.Namespace) -> None:
    from ..scene import check_scene_graph, merge_scene_graphs

    source, diagnostics = _load_checked_scene_graph(args.source)
    if not diagnostics:
        target, diagnostics = _load_checked_scene_graph(args.target)
    else:
        target = {}
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.merge",
                "contract": "scene_graph",
                "source": args.source,
                "target": args.target,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )
    result = merge_scene_graphs(source, target)
    out_path = Path(args.out)
    diagnostics = list(result.diagnostics)
    if not _has_error_diagnostic(diagnostics):
        diagnostics.extend(check_scene_graph(result.scene_graph, root=out_path.parent))
    ok = not _has_error_diagnostic(diagnostics)
    written = False
    if ok:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, result.scene_graph)
        written = True
    payload = {
        "ok": ok,
        "command": "scene.merge",
        "contract": "scene_merge",
        "source": args.source,
        "target": args.target,
        "out": _display_path(out_path),
        "written": written,
        "scene_graph": result.scene_graph,
        "diff": result.diff,
        "applied_changes": result.applied_changes,
        "skipped_changes": result.skipped_changes,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_rollback(args: argparse.Namespace) -> None:
    from ..scene import check_scene_graph
    from ..scene.history import validate_scene_history_payload
    from ..scene.rollback import RollbackHashMismatch, rollback_scene

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.rollback",
                "contract": "scene_graph",
                "path": args.scene,
                "history": args.history,
                "to": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )
    history_payload, diagnostics = _load_json_mapping_payload(
        args.history,
        contract="scene_history",
        phase="scene_history_load",
        code_prefix="SH",
    )
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.rollback",
                "contract": "scene_history",
                "path": args.scene,
                "history": args.history,
                "to": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )
    diagnostics = validate_scene_history_payload(history_payload)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.rollback",
                "contract": "scene_history",
                "path": args.scene,
                "history": args.history,
                "to": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )
    try:
        rolled_back = rollback_scene(scene_graph, history_payload, args.to_event)
    except RollbackHashMismatch as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.rollback",
                "contract": "scene_history",
                "path": args.scene,
                "history": args.history,
                "to": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": [
                    _diagnostic(
                        "SRB1601",
                        "scene_rollback_hash_mismatch",
                        "/history",
                        str(exc),
                        contract="scene_history",
                        phase="scene_rollback",
                    )
                ],
            }
        )
    except ValueError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.rollback",
                "contract": "scene_history",
                "path": args.scene,
                "history": args.history,
                "to": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": [
                    _diagnostic(
                        "SRB1602",
                        "scene_rollback_failed",
                        "/history",
                        str(exc),
                        contract="scene_history",
                        phase="scene_rollback",
                    )
                ],
            }
        )
    out_path = Path(args.out)
    diagnostics = check_scene_graph(rolled_back, root=out_path.parent)
    ok = not _has_error_diagnostic(diagnostics)
    if ok:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, rolled_back)
    payload = {
        "ok": ok,
        "command": "scene.rollback",
        "contract": "scene_history",
        "path": args.scene,
        "history": args.history,
        "to": args.to_event,
        "out": _display_path(out_path),
        "written": ok,
        "scene_graph": rolled_back,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _load_scene_and_inspection(args: argparse.Namespace, command: str) -> tuple[dict[str, Any], dict[str, Any]]:
    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": command,
                "contract": "scene_graph",
                "path": args.scene,
                "render_inspection": args.render_inspection,
                "diagnostics": diagnostics,
            }
        )
    inspection, diagnostics = _load_render_inspection_payload(args.render_inspection)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": command,
                "contract": "render_inspection",
                "path": args.scene,
                "render_inspection": args.render_inspection,
                "diagnostics": diagnostics,
            }
        )
    return scene_graph, inspection


def _run_inspect_render(args: argparse.Namespace) -> None:
    from ..scene import inspect_render

    scene_graph, inspection = _load_scene_and_inspection(args, "scene.inspect-render")
    diagnostics = inspect_render(scene_graph, inspection)
    ok = not _has_error_diagnostic(diagnostics)
    payload = {
        "ok": ok,
        "command": "scene.inspect-render",
        "contract": "render_inspection",
        "path": args.scene,
        "render_inspection": args.render_inspection,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_propose_repairs(args: argparse.Namespace) -> None:
    from ..scene import propose_repairs, validate_scene_repair_report_payload

    scene_graph, inspection = _load_scene_and_inspection(args, "scene.propose-repairs")
    result = propose_repairs(scene_graph, inspection, goal=args.goal)
    diagnostics = validate_scene_repair_report_payload(result.report)
    diagnostics.extend(result.report.get("diagnostics", []))
    ok = not _has_error_diagnostic(diagnostics)
    out_display = None
    if ok and args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, result.report)
        out_display = _display_path(out_path)
    payload = {
        "ok": ok,
        "command": "scene.propose-repairs",
        "contract": "scene_repair_report",
        "path": args.scene,
        "render_inspection": args.render_inspection,
        "goal": args.goal,
        "out": out_display,
        "proposals": result.proposals,
        "report": result.report,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_repair(args: argparse.Namespace) -> None:
    from ..scene import repair_scene_offline, validate_scene_repair_report_payload

    scene_graph, inspection = _load_scene_and_inspection(args, "scene.repair")
    result = repair_scene_offline(scene_graph, inspection, goal=args.goal, max_rounds=args.max_rounds)
    diagnostics = validate_scene_repair_report_payload(result.report)
    diagnostics.extend(result.report.get("diagnostics", []))
    ok = not _has_error_diagnostic(diagnostics)
    out_path = Path(args.out)
    written = False
    if ok:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, result.scene_graph)
        written = True
    report_out = None
    if ok and args.report_out:
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(report_path, result.report)
        report_out = _display_path(report_path)
    payload = {
        "ok": ok,
        "command": "scene.repair",
        "contract": "scene_repair_report",
        "path": args.scene,
        "render_inspection": args.render_inspection,
        "goal": args.goal,
        "max_rounds": args.max_rounds,
        "out": _display_path(out_path),
        "report_out": report_out,
        "written": written,
        "scene_graph": result.scene_graph,
        "proposals": result.proposals,
        "report": result.report,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_curiosity(args: argparse.Namespace) -> None:
    from ..scene import summarize_curiosity

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.curiosity",
                "contract": "scene_graph",
                "path": args.scene,
                "diagnostics": diagnostics,
            }
        )
    summary = summarize_curiosity(scene_graph)
    diagnostics = list(summary.get("diagnostics", []))
    ok = not _has_error_diagnostic(diagnostics)
    payload = {
        "ok": ok,
        "command": "scene.curiosity",
        "contract": "curiosity_summary",
        "path": args.scene,
        "summary": summary,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_expand_anchor(args: argparse.Namespace) -> None:
    from ..scene import expand_anchor

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.expand-anchor",
                "contract": "scene_graph",
                "path": args.scene,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )
    result = expand_anchor(scene_graph, args.anchor_id, args.option_id)
    diagnostics = list(result.diagnostics)
    ok = not _has_error_diagnostic(diagnostics)
    out_path = Path(args.out)
    written = False
    if ok:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, result.scene_graph)
        written = True
    payload = {
        "ok": ok,
        "command": "scene.expand-anchor",
        "contract": "scene_graph",
        "path": args.scene,
        "anchor_id": args.anchor_id,
        "option_id": args.option_id,
        "out": _display_path(out_path),
        "written": written,
        "added_ids": result.added_ids,
        "memory_events": result.memory_events,
        "scene_graph": result.scene_graph,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_build(args: argparse.Namespace) -> None:
    from ..scene.executor import SceneBuildError, build_scene_preview

    try:
        payload = build_scene_preview(
            args.scene,
            args.out,
            mode=args.mode,
            runtime_config_path=args.runtime_config,
            deterministic=bool(args.deterministic),
            allow_fallback=bool(args.allow_fallback),
            strict=bool(args.strict),
            build_assets=bool(args.build_assets),
        )
    except SceneBuildError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.build",
                "contract": "scene_build",
                "path": args.scene,
                "out": args.out,
                "mode": args.mode,
                "runtime_config": args.runtime_config,
                "deterministic": bool(args.deterministic),
                "allow_fallback": bool(args.allow_fallback),
                "strict": bool(args.strict),
                "build_assets": bool(args.build_assets),
                "diagnostics": exc.diagnostics,
            }
        )
    _dump(payload)


def _run_render(args: argparse.Namespace) -> None:
    from ..scene.artifacts import SceneArtifactError, render_scene_graph

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.render",
                "contract": "scene_graph",
                "path": args.scene,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )
    if args.camera is not None and args.all_cameras:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.render",
                "contract": "scene_render",
                "path": args.scene,
                "out": args.out,
                "mode": args.mode,
                "camera": args.camera,
                "all_cameras": bool(args.all_cameras),
                "diagnostics": [
                    _diagnostic(
                        "SR1902",
                        "conflicting_render_camera_selection",
                        "/camera",
                        "Use either --camera <camera_id> or --all-cameras, not both.",
                        contract="scene_render",
                        phase="scene_render_cli",
                    )
                ],
            }
        )
    resolution = None
    if args.width is not None or args.height is not None:
        if args.width is None or args.height is None:
            _emit_failure(
                {
                    "ok": False,
                    "command": "scene.render",
                    "contract": "scene_render",
                    "path": args.scene,
                    "out": args.out,
                    "diagnostics": [
                        _diagnostic(
                            "SR1901",
                            "partial_render_resolution",
                            "/resolution",
                            "Both --width and --height are required when overriding render resolution.",
                            contract="scene_render",
                            phase="scene_render_cli",
                        )
                    ],
                }
            )
        resolution = [args.width, args.height]
    passes = None
    if args.passes is not None:
        passes = [item.strip() for item in str(args.passes).split(",") if item.strip()]
    camera_id = None if args.all_cameras else args.camera
    all_cameras = camera_id is None
    try:
        report = render_scene_graph(
            scene_graph,
            args.out,
            mode=args.mode,
            camera_id=camera_id,
            passes=passes,
            resolution=resolution,
            include_topdown=True,
            include_contact_sheet=all_cameras,
            timeout_seconds=args.timeout_seconds,
        )
    except SceneArtifactError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.render",
                "contract": "scene_render",
                "path": args.scene,
                "out": args.out,
                "mode": args.mode,
                "timeout_seconds": args.timeout_seconds,
                "diagnostics": exc.diagnostics,
            }
        )
    _dump(
        {
            "ok": True,
            "command": "scene.render",
            "contract": "scene_render_artifacts",
            "path": args.scene,
            "out": _display_path(args.out),
            "mode": args.mode,
            "camera": camera_id,
            "all_cameras": all_cameras,
            "timeout_seconds": args.timeout_seconds,
            "report": report,
            "diagnostics": [],
        }
    )


def _run_export(args: argparse.Namespace) -> None:
    from ..scene.artifacts import (
        SceneArtifactError,
        export_scene_glb,
        export_scene_id_mask_bundle,
        export_scene_usd,
    )
    from ..scene.blender_export import export_scene_blend

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.export",
                "contract": "scene_graph",
                "path": args.scene,
                "out": args.out,
                "target": args.target,
                "diagnostics": diagnostics,
            }
        )
    try:
        if args.target == "glb":
            report = export_scene_glb(
                scene_graph,
                args.out,
                mode=args.mode,
                include_collision_nodes=args.include_collision_proxies,
            )
        elif args.target == "usd":
            report = export_scene_usd(
                scene_graph,
                args.out,
                mode=args.mode,
                include_collision_nodes=args.include_collision_proxies,
            )
        elif args.target == "blender":
            report = export_scene_blend(
                scene_graph,
                args.out,
                mode=args.mode,
                include_collision_nodes=args.include_collision_proxies,
            )
        else:
            raise AssertionError(f"unsupported export target: {args.target}")
        if args.include_id_mask_bundle:
            id_mask_report = export_scene_id_mask_bundle(scene_graph, args.out, mode=args.mode)
            report.setdefault("artifacts", []).extend(id_mask_report["artifacts"])
            report["id_mask_bundle"] = id_mask_report["bundle"]
            report_path = report.get("report_path")
            if isinstance(report_path, str):
                persisted_report = {key: value for key, value in report.items() if key != "report_path"}
                write_json_atomic(Path(args.out) / report_path, persisted_report)
    except SceneArtifactError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.export",
                "contract": "scene_export",
                "path": args.scene,
                "out": args.out,
                "target": args.target,
                "mode": args.mode,
                "include_collision_proxies": bool(args.include_collision_proxies),
                "include_id_mask_bundle": bool(args.include_id_mask_bundle),
                "diagnostics": exc.diagnostics,
            }
        )
    _dump(
        {
            "ok": True,
            "command": "scene.export",
            "contract": "scene_export_artifacts",
            "path": args.scene,
            "out": _display_path(args.out),
            "target": args.target,
            "mode": args.mode,
            "include_collision_proxies": bool(args.include_collision_proxies),
            "include_id_mask_bundle": bool(args.include_id_mask_bundle),
            "report": report,
            "diagnostics": [],
        }
    )


def _run_scene_graph_to_source(args: argparse.Namespace) -> None:
    from ..scene.source import (
        SCENE_SOURCE_BRIDGE_VERSION,
        scene_graph_to_source,
        scene_graph_to_source_diagnostics,
    )

    scene_graph, diagnostics = _load_checked_scene_graph(args.scene_graph)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.scene-graph-to-source",
                "contract": "scene_graph",
                "path": args.scene_graph,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )

    bridge_diagnostics = scene_graph_to_source_diagnostics(scene_graph)
    source_text = scene_graph_to_source(scene_graph)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(out_path, source_text)
    _dump(
        {
            "ok": True,
            "command": "scene.scene-graph-to-source",
            "contract": "scene_source_bridge",
            "source_contract": "scene_graph",
            "bridge_format": SCENE_SOURCE_BRIDGE_VERSION,
            "path": args.scene_graph,
            "out": _display_path(out_path),
            "scene_id": scene_graph.get("scene_id"),
            "diagnostics": bridge_diagnostics,
        }
    )


def _run_source_to_scene_graph(args: argparse.Namespace) -> None:
    from ..scene.source import SCENE_SOURCE_BRIDGE_VERSION, source_to_scene_graph

    source_path = Path(args.scene_source)
    try:
        stat_result = source_path.stat()
    except OSError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.source-to-scene-graph",
                "contract": "scene_source_bridge",
                "path": args.scene_source,
                "out": args.out,
                "diagnostics": [
                    _diagnostic(
                        "SS1900",
                        "scene_source_load_failed",
                        "/source",
                        f"Scene source could not be loaded: {exc}",
                        contract="scene_source_bridge",
                        phase="scene_source_bridge_load",
                        details={"path": args.scene_source},
                    )
                ],
            }
        )
    if stat_result.st_size > MAX_CONTRACT_BYTES:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.source-to-scene-graph",
                "contract": "scene_source_bridge",
                "path": args.scene_source,
                "out": args.out,
                "diagnostics": [
                    _diagnostic(
                        "SS1902",
                        "scene_source_too_large",
                        "/source",
                        f"Scene source exceeds 2 MiB ({stat_result.st_size} bytes > {MAX_CONTRACT_BYTES}).",
                        contract="scene_source_bridge",
                        phase="scene_source_bridge_load",
                        details={"path": args.scene_source, "bytes": stat_result.st_size},
                    )
                ],
            }
        )
    try:
        source_text = source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.source-to-scene-graph",
                "contract": "scene_source_bridge",
                "path": args.scene_source,
                "out": args.out,
                "diagnostics": [
                    _diagnostic(
                        "SS1901",
                        "scene_source_not_utf8",
                        "/source",
                        f"Scene source is not valid UTF-8: {exc}",
                        contract="scene_source_bridge",
                        phase="scene_source_bridge_load",
                        details={"path": args.scene_source},
                    )
                ],
            }
        )

    scene_graph, diagnostics = source_to_scene_graph(source_text, root=source_path.parent, source_path=source_path)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.source-to-scene-graph",
                "contract": "scene_source_bridge",
                "path": args.scene_source,
                "out": args.out,
                "diagnostics": diagnostics,
            }
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(out_path, scene_graph)
    _dump(
        {
            "ok": True,
            "command": "scene.source-to-scene-graph",
            "contract": "scene_graph",
            "source_contract": "scene_source_bridge",
            "bridge_format": SCENE_SOURCE_BRIDGE_VERSION,
            "path": args.scene_source,
            "out": _display_path(out_path),
            "scene_id": scene_graph.get("scene_id"),
            "diagnostics": [],
        }
    )


def _run_package_init(args: argparse.Namespace) -> None:
    from ..scene import init_scene_package

    try:
        manifest_path, manifest = init_scene_package(
            args.package_dir,
            scene_id=args.scene_id,
            package_id=args.package_id,
            overwrite=args.force,
        )
    except (LatheError, OSError) as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.package.init",
                "contract": "scene_package_manifest",
                "package_dir": args.package_dir,
                "diagnostics": [
                    _diagnostic(
                        "P4903",
                        "scene_package_init_failed",
                        "/scene_package_manifest",
                        str(exc),
                        contract="scene_package_manifest",
                        phase="scene_package_init",
                    )
                ],
            },
            exit_code=1,
        )
    _dump(
        {
            "ok": True,
            "command": "scene.package.init",
            "contract": "scene_package_manifest",
            "package_dir": args.package_dir,
            "manifest_path": _display_path(manifest_path),
            "manifest": manifest,
            "diagnostics": [],
        }
    )


def _run_package_validate(args: argparse.Namespace) -> None:
    require_exists = not args.allow_missing_paths
    package, diagnostics = _load_package_target(args.package_dir_or_manifest, require_exists=require_exists)
    ok = not diagnostics
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.package.validate",
        "contract": "scene_package_manifest",
        "path": args.package_dir_or_manifest,
        "require_exists": require_exists,
        "diagnostics": diagnostics,
    }
    if package is not None:
        payload["package_dir"] = _display_path(package.package_dir)
        payload["manifest_path"] = _display_path(package.manifest_path)
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_package_inspect(args: argparse.Namespace) -> None:
    package_dir = Path(args.package_dir)
    if not package_dir.is_dir():
        _emit_failure(
            {
                "ok": False,
                "command": "scene.package.inspect",
                "contract": "scene_package_manifest",
                "package_dir": args.package_dir,
                "diagnostics": [
                    _diagnostic(
                        "P4904",
                        "scene_package_directory_missing",
                        "/package_dir",
                        f"Scene Package directory does not exist: {package_dir}",
                        contract="scene_package_manifest",
                        phase="scene_package_load",
                        details={"package_dir": str(package_dir)},
                    )
                ],
            },
            exit_code=1,
        )
    package, diagnostics = _load_package_target(package_dir, require_exists=True)
    ok = not diagnostics
    manifest = package.manifest if package is not None else {}
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.package.inspect",
        "contract": "scene_package_manifest",
        "package_dir": _display_path(package_dir),
        "manifest_path": _display_path(package.manifest_path if package is not None else None),
        "manifest": manifest,
        "counts": {
            "source": len(manifest.get("source", [])) if isinstance(manifest.get("source"), list) else 0,
            "build": len(manifest.get("build", [])) if isinstance(manifest.get("build"), list) else 0,
            "renders": len(manifest.get("renders", [])) if isinstance(manifest.get("renders"), list) else 0,
            "exports": len(manifest.get("exports", [])) if isinstance(manifest.get("exports"), list) else 0,
            "reports": len(manifest.get("reports", [])) if isinstance(manifest.get("reports"), list) else 0,
        },
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _scene_graph_path_for_memory(args: argparse.Namespace, target: _MemoryTarget) -> Path | None:
    if args.scene_graph is None:
        return target.scene_graph_path
    path, diagnostics = _direct_path(args.scene_graph)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": f"scene.memory.{args.scene_memory_cmd}",
                "contract": "world_memory",
                "path": str(target.memory_path),
                "diagnostics": diagnostics,
            },
            exit_code=1,
        )
    return path


def _run_memory_inspect(args: argparse.Namespace) -> None:
    target, diagnostics = _resolve_memory_target(args.package_dir_or_memory_json, require_package_paths=True)
    if diagnostics or target is None:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.inspect",
                "contract": "world_memory",
                "path": args.package_dir_or_memory_json,
                "diagnostics": diagnostics,
            },
            exit_code=1,
        )
    scene_graph_path = _scene_graph_path_for_memory(args, target)
    scene_graph, diagnostics = _load_scene_graph_payload(scene_graph_path)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.inspect",
                "contract": "world_memory",
                "path": str(target.memory_path),
                "scene_graph": str(scene_graph_path) if scene_graph_path is not None else None,
                "diagnostics": diagnostics,
            },
            exit_code=1,
        )
    world_memory, diagnostics = _load_world_memory_payload(target.memory_path, scene_graph=scene_graph)
    ok = not diagnostics
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "scene.memory.inspect",
        "contract": "world_memory",
        "path": _display_path(target.memory_path),
        "package_dir": _display_path(target.package.package_dir if target.package is not None else None),
        "scene_graph": _display_path(scene_graph_path),
        "counts": _memory_counts(world_memory),
        "memory": world_memory,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_failure(payload)


def _run_memory_append(args: argparse.Namespace) -> None:
    from ..scene.memory import append_memory_event

    target, diagnostics = _resolve_memory_target(args.package_dir_or_memory_json, require_package_paths=True)
    if diagnostics or target is None:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.append",
                "contract": "world_memory",
                "path": args.package_dir_or_memory_json,
                "diagnostics": diagnostics,
            },
            exit_code=1,
        )
    scene_graph_path = _scene_graph_path_for_memory(args, target)
    scene_graph, diagnostics = _load_scene_graph_payload(scene_graph_path)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.append",
                "contract": "world_memory",
                "path": str(target.memory_path),
                "scene_graph": str(scene_graph_path) if scene_graph_path is not None else None,
                "diagnostics": diagnostics,
            },
            exit_code=1,
        )
    world_memory, diagnostics = _load_world_memory_payload(target.memory_path, scene_graph=scene_graph)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.append",
                "contract": "world_memory",
                "path": str(target.memory_path),
                "scene_graph": str(scene_graph_path) if scene_graph_path is not None else None,
                "diagnostics": diagnostics,
            },
            exit_code=1,
        )
    event, diagnostics = _load_event_payload(args.event_json)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.append",
                "contract": "world_memory",
                "path": str(target.memory_path),
                "event_path": args.event_json,
                "diagnostics": diagnostics,
            },
            exit_code=1,
        )

    event_id = _event_id(event)
    before_counts = _memory_counts(world_memory)
    existing = _existing_event(world_memory, event_id) if event_id is not None else None
    if existing is not None:
        if dict(existing) == event:
            _dump(
                {
                    "ok": True,
                    "command": "scene.memory.append",
                    "contract": "world_memory",
                    "path": _display_path(target.memory_path),
                    "package_dir": _display_path(target.package.package_dir if target.package is not None else None),
                    "scene_graph": _display_path(scene_graph_path),
                    "event_id": event_id,
                    "status": "skipped",
                    "idempotent": True,
                    "appended": False,
                    "counts": before_counts,
                    "diagnostics": [],
                }
            )
            return
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.append",
                "contract": "world_memory",
                "path": str(target.memory_path),
                "event_id": event_id,
                "status": "conflict",
                "idempotent": False,
                "appended": False,
                "diagnostics": [
                    _diagnostic(
                        "M1010",
                        "conflicting_memory_event_id",
                        "/event/event_id",
                        f"World Memory already contains a different event with event_id {event_id!r}.",
                        contract="world_memory",
                        phase="world_memory_semantics",
                        details={"event_id": event_id},
                    )
                ],
            },
            exit_code=1,
        )

    updated, diagnostics = append_memory_event(world_memory, event, scene_graph=scene_graph)
    if diagnostics:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.append",
                "contract": "world_memory",
                "path": str(target.memory_path),
                "event_id": event_id,
                "status": "invalid",
                "idempotent": False,
                "appended": False,
                "diagnostics": diagnostics,
            },
            exit_code=1,
        )

    try:
        _write_json(target.memory_path, updated)
    except OSError as exc:
        _emit_failure(
            {
                "ok": False,
                "command": "scene.memory.append",
                "contract": "world_memory",
                "path": str(target.memory_path),
                "event_id": event_id,
                "status": "write_failed",
                "idempotent": False,
                "appended": False,
                "diagnostics": [
                    _diagnostic(
                        "M1906",
                        "world_memory_write_failed",
                        "/world_memory",
                        str(exc),
                        contract="world_memory",
                        phase="world_memory_write",
                        details={"path": str(target.memory_path)},
                    )
                ],
            },
            exit_code=1,
        )

    _dump(
        {
            "ok": True,
            "command": "scene.memory.append",
            "contract": "world_memory",
            "path": _display_path(target.memory_path),
            "package_dir": _display_path(target.package.package_dir if target.package is not None else None),
            "scene_graph": _display_path(scene_graph_path),
            "event_id": event_id,
            "status": "appended",
            "idempotent": False,
            "appended": True,
            "counts_before": before_counts,
            "counts": _memory_counts(updated),
            "diagnostics": [],
        }
    )


def _run_package(args: argparse.Namespace) -> None:
    if args.scene_package_cmd == "init":
        _run_package_init(args)
        return
    if args.scene_package_cmd == "inspect":
        _run_package_inspect(args)
        return
    if args.scene_package_cmd == "validate":
        _run_package_validate(args)
        return
    raise SystemExit(2)


def _run_memory(args: argparse.Namespace) -> None:
    if args.scene_memory_cmd == "inspect":
        _run_memory_inspect(args)
        return
    if args.scene_memory_cmd == "append":
        _run_memory_append(args)
        return
    raise SystemExit(2)


def run_scene(args: argparse.Namespace) -> None:
    """Dispatch ``lathe scene`` subcommands."""
    if args.scene_cmd == "check":
        _run_check(args)
        return
    if args.scene_cmd == "plan":
        _run_plan(args)
        return
    if args.scene_cmd == "materialize":
        _run_materialize(args)
        return
    if args.scene_cmd == "build":
        _run_build(args)
        return
    if args.scene_cmd == "render":
        _run_render(args)
        return
    if args.scene_cmd == "export":
        _run_export(args)
        return
    if args.scene_cmd == "validate":
        _run_validate(args)
        return
    if args.scene_cmd == "bench":
        _run_bench(args)
        return
    if args.scene_cmd == "style-pack":
        _run_style_pack(args)
        return
    if args.scene_cmd == "layout":
        _run_layout(args)
        return
    if args.scene_cmd == "camera-lighting":
        _run_camera_lighting(args)
        return
    if args.scene_cmd == "assemble":
        _run_assemble(args)
        return
    if args.scene_cmd == "roblox-manifest":
        _run_roblox_manifest(args)
        return
    if args.scene_cmd == "roblox-export":
        _run_roblox_export(args)
        return
    if args.scene_cmd == "patch":
        _run_patch(args)
        return
    if args.scene_cmd == "branch":
        _run_branch(args)
        return
    if args.scene_cmd == "diff":
        _run_diff(args)
        return
    if args.scene_cmd == "merge":
        _run_merge(args)
        return
    if args.scene_cmd == "rollback":
        _run_rollback(args)
        return
    if args.scene_cmd == "inspect-render":
        _run_inspect_render(args)
        return
    if args.scene_cmd == "propose-repairs":
        _run_propose_repairs(args)
        return
    if args.scene_cmd == "repair":
        _run_repair(args)
        return
    if args.scene_cmd == "curiosity":
        _run_curiosity(args)
        return
    if args.scene_cmd == "expand-anchor":
        _run_expand_anchor(args)
        return
    if args.scene_cmd == "scene-graph-to-source":
        _run_scene_graph_to_source(args)
        return
    if args.scene_cmd == "source-to-scene-graph":
        _run_source_to_scene_graph(args)
        return
    if args.scene_cmd == "package":
        _run_package(args)
        return
    if args.scene_cmd == "memory":
        _run_memory(args)
        return
    raise SystemExit(2)
