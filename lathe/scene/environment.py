"""Environment module contracts for Wonder scene composition."""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping
from typing import Any

from .stdlib import STDLIB_MATERIALS

ENVIRONMENT_MODULE_VERSION = "lathe.environment_module.v1"
ENVIRONMENT_MODULE_CATALOG_VERSION = "lathe.environment_module_catalog.v1"

_SPECS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        "env_room_shell",
        "architecture_room_shell",
        "Room Boundary Shell",
        "scene_boundary",
        ("env_module", "room_shell", "scene_boundary", "snap_profile_grid_1m"),
    ),
    (
        "env_floor_tile",
        "architecture_floor",
        "Modular Floor Tile",
        "floor",
        ("env_module", "floor_tile", "walkable", "snap_profile_grid_1m"),
    ),
    (
        "env_wall_segment",
        "architecture_wall",
        "Modular Wall Segment",
        "wall",
        ("env_module", "wall_segment", "boundary", "snap_profile_grid_1m"),
    ),
    (
        "env_ceiling_segment",
        "architecture_ceiling",
        "Modular Ceiling Segment",
        "ceiling",
        ("env_module", "ceiling_segment", "overhead", "snap_profile_grid_1m"),
    ),
    (
        "env_arch_segment",
        "architecture_arch",
        "Modular Arch Segment",
        "threshold",
        ("env_module", "arch_segment", "threshold", "snap_profile_grid_1m"),
    ),
    (
        "env_platform_module",
        "architecture_platform",
        "Modular Platform",
        "platform",
        ("env_module", "platform", "walkable", "snap_profile_grid_1m"),
    ),
    (
        "env_stair_module",
        "architecture_stair",
        "Modular Stair",
        "stair",
        ("env_module", "stair", "navigation", "snap_profile_grid_1m"),
    ),
    (
        "env_background_silhouette",
        "environment_structure",
        "Background Silhouette",
        "background",
        ("env_module", "background_silhouette", "vista_blocker", "snap_profile_grid_2m"),
    ),
    (
        "env_terrain_chunk",
        "natural_terrain_chunk",
        "Terrain Chunk",
        "terrain",
        ("env_module", "terrain_chunk", "ground", "snap_profile_grid_1m"),
    ),
)


def iter_environment_modules() -> Iterator[dict[str, Any]]:
    """Yield curated environment module records in stable order."""
    for module_id, lathe_asset, display_name, module_kind, tags in _SPECS:
        snap_grid = 2.0 if "snap_profile_grid_2m" in tags else 1.0
        yield {
            "schema_version": ENVIRONMENT_MODULE_VERSION,
            "module_id": module_id,
            "display_name": display_name,
            "lathe_asset": lathe_asset,
            "source_family": "environment_architecture"
            if module_kind not in {"terrain", "background"}
            else "environment_structure",
            "source_kit": lathe_asset if lathe_asset.endswith("_kit") else f"{lathe_asset}_kit",
            "role": "architecture" if module_kind not in {"terrain", "background"} else "environment_structure",
            "module_kind": module_kind,
            "snap_profile": f"grid_{snap_grid:g}m",
            "snap_grid": snap_grid,
            "snap_point_count": 4 if module_kind not in {"background"} else 2,
            "semantic_tags": sorted(tags),
            "boundary_role": "required" if module_kind == "scene_boundary" else "member",
            "readiness": {
                "contract": "scene_graph_environment_module",
                "mesh_runtime": "not_claimed",
            },
        }


def environment_module_ids() -> tuple[str, ...]:
    """Return environment module IDs in stable order."""
    return tuple(module["module_id"] for module in iter_environment_modules())


def get_environment_module(module_id: str) -> dict[str, Any]:
    """Return one environment module record by ID."""
    for module in iter_environment_modules():
        if module["module_id"] == module_id:
            return module
    raise KeyError(f"unknown environment module: {module_id}")


def environment_module_catalog() -> dict[str, Any]:
    """Return the machine-readable Wonder environment module catalog."""
    modules = list(iter_environment_modules())
    return {
        "schema_version": ENVIRONMENT_MODULE_CATALOG_VERSION,
        "summary": {
            "modules": len(modules),
            "snap_profiles": sorted({str(module["snap_profile"]) for module in modules}),
            "boundary_modules": sum(1 for module in modules if module["boundary_role"] == "required"),
        },
        "modules": modules,
    }


def environment_module_scene_object(
    module_id: str,
    *,
    index: int = 1,
    region_id: str = "region_environment_module_room",
    position: list[float] | None = None,
) -> dict[str, Any]:
    """Return a Scene Graph object instance for an environment module."""
    module = get_environment_module(module_id)
    object_id = f"obj_{module_id}_{index:03d}"
    role = "interactive" if module_id == "env_arch_segment" else module["role"]
    return {
        "object_id": object_id,
        "name": module["display_name"],
        "role": role,
        "region": region_id,
        "lathe_asset": module["lathe_asset"],
        "source_family": module["source_family"],
        "source_kit": module["source_kit"],
        "variant": "module_default",
        "transform": {
            "position": position or [0.0, 0.0, 0.5],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
        "material_bindings": [{"slot": "body", "material": _material_for_module(module)}],
        "semantic_tags": list(module["semantic_tags"]),
        "state": {
            "module_kind": module["module_kind"],
            "snap_profile": module["snap_profile"],
            "snap_grid": module["snap_grid"],
            "snap_point_count": module["snap_point_count"],
            "boundary_role": module["boundary_role"],
            "mesh_runtime": "not_claimed",
        },
        "affordances": [],
        "provenance": {"source": "deterministic_lathe", "commercial_use": True},
    }


def environment_module_showcase_scene_graph() -> dict[str, Any]:
    """Return a schema-valid Scene Graph exercising the environment module catalog."""
    module_ids = environment_module_ids()
    objects = [
        environment_module_scene_object(module_id, index=index, position=_module_position(index))
        for index, module_id in enumerate(module_ids, start=1)
    ]
    return {
        "schema_version": "lathe.scene_graph.v1",
        "scene_id": "environment_module_showcase",
        "version": 1,
        "prompt": "A modular room shell assembled from Wonder environment modules and terrain chunks.",
        "style_bible": {
            "mood": ["readable", "modular", "place like"],
            "palette": ["warm stone", "weathered green", "soft emissive"],
            "materials": ["painted stone", "natural mineral", "soft emissive"],
            "forms": ["room shell", "snap grid", "clear silhouettes"],
            "lighting": ["soft key", "debug fill"],
            "avoid": [],
        },
        "layout": {
            "room_size": [14.0, 10.0, 6.0],
            "main_path": {"from": "region_entry", "to": "obj_env_arch_segment_005", "width": 1.5},
            "focal_point": "obj_env_arch_segment_005",
            "density": "medium",
            "avoid_intersections": True,
            "modular_walls": {
                "enabled": True,
                "regions": ["region_environment_module_room"],
                "sides": ["north", "south", "east", "west"],
                "module_length": 2.0,
                "snap_grid": 1.0,
                "height": 3.0,
                "thickness": 0.25,
            },
        },
        "regions": [
            {
                "region_id": "region_environment_module_room",
                "name": "Environment Module Room",
                "type": "interior",
                "purpose": "Validate modular room shell, snap-grid modules, and terrain chunks.",
                "mood": "readable",
                "bounds": {"center": [0.0, 0.0, 2.0], "size": [14.0, 10.0, 6.0]},
                "semantic_tags": ["env_module", "room_shell"],
            },
            {
                "region_id": "region_entry",
                "name": "Entry",
                "type": "threshold",
                "purpose": "Start of the modular room path.",
                "mood": "neutral",
                "bounds": {"center": [0.0, -4.0, 0.5], "size": [2.0, 1.0, 1.0]},
                "semantic_tags": ["entry"],
            },
        ],
        "objects": objects,
        "relationships": [
            {
                "relationship_id": "rel_env_floor_supports_wall",
                "from": "obj_env_floor_tile_002",
                "to": "obj_env_wall_segment_003",
                "type": "supports",
                "description": "Floor tiles provide the snap plane for wall segments.",
            },
            {
                "relationship_id": "rel_env_shell_contains_modules",
                "from": "obj_env_room_shell_001",
                "to": "obj_env_floor_tile_002",
                "type": "contains",
                "description": "The boundary shell contains the modular floor, wall, arch, platform, stair, and terrain modules.",
            },
        ],
        "materials": copy.deepcopy(list(STDLIB_MATERIALS)),
        "lights": [
            {
                "light_id": "light_env_module_key",
                "type": "area",
                "target": "obj_env_arch_segment_005",
                "color": "soft emissive",
                "intensity": 0.7,
                "purpose": "Readable debug light for modular room assembly.",
            }
        ],
        "cameras": [
            {
                "camera_id": "camera_reveal",
                "target": "obj_env_arch_segment_005",
                "framing": "cinematic_wide",
                "purpose": "Reveal the modular environment shell.",
                "transform": {"position": [-6.0, -8.0, 4.0], "rotation": [58.0, 0.0, -32.0], "scale": [1.0, 1.0, 1.0]},
                "fov_degrees": 50.0,
            }
        ],
        "curiosity_anchors": [
            {
                "anchor_id": "curiosity_env_boundary_shell",
                "visible_clue": "The boundary shell shows where future rooms can attach.",
                "hidden_fact": "The room shell stores the continuity boundary for future scene expansion.",
                "attached_to": "obj_env_room_shell_001",
                "suggested_user_actions": ["inspect shell", "expand room"],
                "expansion_options": [
                    {
                        "id": "expand_adjacent_room",
                        "label": "Add an adjacent room using the same snap grid.",
                        "target_scope": "region_environment_module_room",
                        "required_assets": ["env_room_shell", "env_wall_segment", "env_floor_tile"],
                        "continuity_constraints": ["preserve snap grid", "preserve boundary shell"],
                    }
                ],
            },
            {
                "anchor_id": "curiosity_env_terrain_transition",
                "visible_clue": "A terrain chunk breaks the clean floor grid near the room edge.",
                "hidden_fact": "The terrain chunk marks where exterior generation can begin.",
                "attached_to": "obj_env_terrain_chunk_009",
                "suggested_user_actions": ["inspect terrain edge", "open exterior"],
                "expansion_options": [
                    {
                        "id": "open_exterior_edge",
                        "label": "Generate an exterior terrain transition.",
                        "target_scope": "obj_env_terrain_chunk_009",
                        "required_assets": ["env_terrain_chunk", "env_background_silhouette"],
                        "continuity_constraints": ["preserve room shell"],
                    }
                ],
            },
        ],
        "hidden_state": [
            {
                "hidden_id": "hidden_env_boundary_shell",
                "attached_to": "obj_env_room_shell_001",
                "fact": "The room shell stores the continuity boundary for future scene expansion.",
                "reveal_condition": "User inspects the boundary shell.",
                "visible": False,
            },
            {
                "hidden_id": "hidden_env_terrain_transition",
                "attached_to": "obj_env_terrain_chunk_009",
                "fact": "The terrain chunk marks where exterior generation can begin.",
                "reveal_condition": "User inspects the terrain chunk.",
                "visible": False,
            },
        ],
        "exports": [{"target": "scene_graph", "format": "json", "path": "exports/environment_module_showcase.scene_graph.json"}],
        "build_artifacts": [],
        "memory_events": [
            {
                "event_id": "mem_env_module_showcase_created",
                "type": "fact",
                "text": "The environment module showcase validates room shells, snap-grid modules, background silhouettes, and terrain chunks.",
                "affected_ids": ["region_environment_module_room"],
                "source": "lathe.scene.environment",
            }
        ],
    }


def validate_environment_module_scene(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return environment module diagnostics for a Scene Graph mapping."""
    diagnostics: list[dict[str, Any]] = []
    modules = [item for item in _objects(scene_graph) if _is_environment_module(item)]
    if not modules:
        return diagnostics
    if not any("scene_boundary" in _tags(item) for item in modules):
        diagnostics.append(
            _diagnostic(
                "EV2001",
                "/objects",
                "Environment-module scenes require a scene boundary shell module.",
                details={"module_count": len(modules)},
            )
        )
    for item in modules:
        object_id = str(item.get("object_id") or "")
        state = item.get("state") if isinstance(item.get("state"), Mapping) else {}
        snap_point_count = state.get("snap_point_count") if isinstance(state, Mapping) else None
        if not isinstance(snap_point_count, int | float) or snap_point_count <= 0:
            diagnostics.append(
                _diagnostic(
                    "EV2002",
                    f"/objects/{object_id}/state/snap_point_count",
                    f"Environment module {object_id!r} must declare at least one snap point.",
                    details={"object_id": object_id},
                )
            )
        snap_grid = state.get("snap_grid") if isinstance(state, Mapping) else None
        position = _position(item)
        if (
            isinstance(snap_grid, int | float)
            and snap_grid > 0
            and position is not None
            and (not _aligned(position[0], float(snap_grid)) or not _aligned(position[1], float(snap_grid)))
        ):
            diagnostics.append(
                _diagnostic(
                    "EV2003",
                    f"/objects/{object_id}/transform/position",
                    f"Environment module {object_id!r} is not aligned to snap grid {snap_grid:g}.",
                    severity="warning",
                    details={"object_id": object_id, "snap_grid": snap_grid, "position": position},
                )
            )
    return diagnostics


def render_environment_module_docs() -> str:
    """Render the environment module catalog as Markdown."""
    catalog = environment_module_catalog()
    lines = [
        "# Environment Modules",
        "",
        "Environment modules are Scene Graph source vocabulary for place-making:",
        "room shells, floor tiles, wall and ceiling segments, arches, platforms,",
        "stairs, background silhouettes, and terrain chunks. They are validated",
        "for snap-grid metadata and boundary-shell presence before downstream",
        "mesh/runtime work claims final assets.",
        "",
        "## Catalog",
        "",
        "| Module | Asset | Kind | Snap Profile | Snap Points | Boundary |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for module in catalog["modules"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{module['module_id']}`",
                    f"`{module['lathe_asset']}`",
                    str(module["module_kind"]),
                    str(module["snap_profile"]),
                    str(module["snap_point_count"]),
                    str(module["boundary_role"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Validation",
            "",
            "- Environment modules are Scene Graph objects tagged with `env_module`.",
            "- `state.snap_grid` controls deterministic x/y placement alignment.",
            "- `state.snap_point_count` records authored connection points for downstream module assembly.",
            "- A room-like environment module scene must include a `scene_boundary` module.",
            "- The committed `environment_module_showcase` example validates these contracts without claiming final mesh runtime proof.",
            "",
        ]
    )
    return "\n".join(lines)


def _material_for_module(module: Mapping[str, Any]) -> str:
    if module["module_kind"] == "terrain":
        return "mat_stdlib_natural"
    return "mat_stdlib_architecture"


def _module_position(index: int) -> list[float]:
    positions = {
        1: [0.0, 0.0, 0.5],
        2: [-4.0, -2.0, 0.5],
        3: [-4.0, 2.0, 0.5],
        4: [0.0, 4.0, 3.0],
        5: [0.0, -2.0, 0.5],
        6: [4.0, -2.0, 0.5],
        7: [4.0, 2.0, 0.5],
        8: [0.0, 4.0, 1.5],
        9: [0.0, 2.0, 0.5],
    }
    return list(positions[index])


def _objects(scene_graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = scene_graph.get("objects", [])
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def _tags(item: Mapping[str, Any]) -> set[str]:
    raw = item.get("semantic_tags", [])
    return {str(tag) for tag in raw if isinstance(tag, str)} if isinstance(raw, list) else set()


def _is_environment_module(item: Mapping[str, Any]) -> bool:
    return "env_module" in _tags(item)


def _position(item: Mapping[str, Any]) -> list[float] | None:
    transform = item.get("transform")
    if not isinstance(transform, Mapping):
        return None
    position = transform.get("position")
    if not isinstance(position, list) or len(position) != 3:
        return None
    if not all(isinstance(value, int | float) for value in position):
        return None
    return [float(value) for value in position]


def _aligned(value: float, grid: float) -> bool:
    nearest = round(value / grid) * grid
    return abs(value - nearest) <= 1e-6


def _diagnostic(
    code: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": "environment_module_contract",
        "severity": severity,
        "contract": "environment_module",
        "phase": "environment_module_validation",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


__all__ = [
    "ENVIRONMENT_MODULE_CATALOG_VERSION",
    "ENVIRONMENT_MODULE_VERSION",
    "environment_module_catalog",
    "environment_module_ids",
    "environment_module_scene_object",
    "environment_module_showcase_scene_graph",
    "get_environment_module",
    "iter_environment_modules",
    "render_environment_module_docs",
    "validate_environment_module_scene",
]
