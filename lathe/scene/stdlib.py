"""Curated Wonder standard-library component catalog."""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping
from typing import Any

STDLIB_COMPONENT_VERSION = "lathe.scene_stdlib_component.v1"
STDLIB_CATALOG_VERSION = "lathe.scene_stdlib_catalog.v1"

STDLIB_MATERIALS: tuple[dict[str, Any], ...] = (
    {
        "material_id": "mat_stdlib_architecture",
        "name": "Stdlib Architecture Stone",
        "role": "architecture",
        "palette_refs": ["warm stone", "aged plaster"],
        "pbr": {"basecolor": "#8f897c", "metallic": 0.0, "roughness": 0.82},
    },
    {
        "material_id": "mat_stdlib_dressing",
        "name": "Stdlib Dressing Wood",
        "role": "surface",
        "palette_refs": ["simple wood", "painted trim"],
        "pbr": {"basecolor": "#9a6f46", "metallic": 0.0, "roughness": 0.72},
    },
    {
        "material_id": "mat_stdlib_natural",
        "name": "Stdlib Natural Form",
        "role": "terrain",
        "palette_refs": ["weathered green", "mineral gray"],
        "pbr": {"basecolor": "#6f7f62", "metallic": 0.0, "roughness": 0.88},
    },
    {
        "material_id": "mat_stdlib_hero",
        "name": "Stdlib Hero Metal",
        "role": "mechanism",
        "palette_refs": ["aged brass", "dark iron"],
        "pbr": {"basecolor": "#9a7a45", "metallic": 0.65, "roughness": 0.48},
    },
    {
        "material_id": "mat_stdlib_light",
        "name": "Stdlib Soft Emissive",
        "role": "accent",
        "palette_refs": ["soft emissive", "moon blue"],
        "pbr": {"basecolor": "#f2c36b", "metallic": 0.0, "roughness": 0.35, "emissive": "#f2c36b"},
    },
)

_MATERIAL_BY_CATEGORY = {
    "architecture": "mat_stdlib_architecture",
    "environmental_dressing": "mat_stdlib_dressing",
    "natural_form": "mat_stdlib_natural",
    "hero_prop": "mat_stdlib_hero",
    "lighting_fixture": "mat_stdlib_light",
}

_ROLE_BY_CATEGORY = {
    "architecture": "architecture",
    "environmental_dressing": "dressing_prop",
    "natural_form": "environment_structure",
    "hero_prop": "hero_prop",
    "lighting_fixture": "light_fixture",
}

_SOURCE_FAMILY_BY_CATEGORY = {
    "architecture": "environment_architecture",
    "environmental_dressing": "dressing_prop",
    "natural_form": "natural_form",
    "hero_prop": "hero_prop",
    "lighting_fixture": "practical_light",
}

_SPECS: tuple[tuple[str, str, str, str, str, tuple[str, ...]], ...] = (
    ("architecture_wall", "architecture", "kit", "Wall Module", "architecture_wall_kit", ("wall", "boundary")),
    ("architecture_floor", "architecture", "kit", "Floor Module", "architecture_floor_kit", ("floor", "walkable")),
    ("architecture_ceiling", "architecture", "kit", "Ceiling Module", "architecture_ceiling_kit", ("ceiling", "overhead")),
    ("architecture_arch", "architecture", "kit", "Arch Module", "architecture_arch_kit", ("arch", "threshold")),
    ("architecture_column", "architecture", "kit", "Column Module", "architecture_column_kit", ("column", "support")),
    ("architecture_stair", "architecture", "kit", "Stair Module", "architecture_stair_kit", ("stair", "navigation")),
    ("architecture_door", "architecture", "kit", "Door Module", "architecture_door_kit", ("door", "threshold")),
    ("architecture_window", "architecture", "kit", "Window Module", "architecture_window_kit", ("window", "opening")),
    ("architecture_bridge", "architecture", "kit", "Bridge Module", "architecture_bridge_kit", ("bridge", "navigation")),
    ("architecture_railing", "architecture", "kit", "Railing Module", "architecture_railing_kit", ("railing", "safety")),
    ("architecture_platform", "architecture", "kit", "Platform Module", "architecture_platform_kit", ("platform", "walkable")),
    ("architecture_tunnel", "architecture", "kit", "Tunnel Module", "architecture_tunnel_kit", ("tunnel", "passage")),
    ("architecture_room_shell", "architecture", "kit", "Modular Room Shell", "modular_room_shell_kit", ("room", "shell")),
    ("dressing_crate", "environmental_dressing", "family", "Crate", "dressing_crate_family", ("crate", "storage")),
    ("dressing_barrel", "environmental_dressing", "family", "Barrel", "dressing_barrel_family", ("barrel", "storage")),
    ("dressing_book", "environmental_dressing", "family", "Book", "dressing_book_family", ("book", "knowledge")),
    ("dressing_candle", "environmental_dressing", "family", "Candle", "dressing_candle_family", ("candle", "ritual")),
    ("dressing_chain", "environmental_dressing", "family", "Chain", "dressing_chain_family", ("chain", "hanging")),
    ("dressing_pipe", "environmental_dressing", "family", "Pipe", "dressing_pipe_family", ("pipe", "utility")),
    ("dressing_vent", "environmental_dressing", "family", "Vent", "dressing_vent_family", ("vent", "utility")),
    ("dressing_panel", "environmental_dressing", "family", "Panel", "dressing_panel_family", ("panel", "surface")),
    ("dressing_debris", "environmental_dressing", "family", "Debris", "dressing_debris_family", ("debris", "scatter")),
    ("dressing_rug", "environmental_dressing", "family", "Rug", "dressing_rug_family", ("rug", "soft")),
    ("dressing_banner", "environmental_dressing", "family", "Banner", "dressing_banner_family", ("banner", "signage")),
    ("dressing_sign", "environmental_dressing", "family", "Sign", "dressing_sign_family", ("sign", "wayfinding")),
    ("natural_rock", "natural_form", "family", "Rock Cluster", "natural_rock_family", ("rock", "terrain")),
    ("natural_root", "natural_form", "family", "Root Cluster", "natural_root_family", ("root", "organic")),
    ("natural_vine", "natural_form", "family", "Vine Cluster", "natural_vine_family", ("vine", "organic")),
    ("natural_crystal", "natural_form", "family", "Crystal Cluster", "natural_crystal_family", ("crystal", "mineral")),
    ("natural_mushroom", "natural_form", "family", "Mushroom Cluster", "natural_mushroom_family", ("mushroom", "organic")),
    ("natural_dead_tree", "natural_form", "family", "Dead Tree", "natural_dead_tree_family", ("dead_tree", "silhouette")),
    ("natural_bone", "natural_form", "family", "Bone Cluster", "natural_bone_family", ("bone", "organic")),
    ("natural_coral_form", "natural_form", "family", "Coral Form", "natural_coral_form_family", ("coral", "organic")),
    ("natural_terrain_chunk", "natural_form", "kit", "Terrain Chunk", "natural_terrain_chunk_kit", ("terrain", "ground")),
    ("hero_altar", "hero_prop", "family", "Altar", "hero_altar_family", ("altar", "ritual")),
    ("hero_machine", "hero_prop", "family", "Machine", "hero_machine_family", ("machine", "mechanism")),
    ("hero_console", "hero_prop", "family", "Console", "hero_console_family", ("console", "interface")),
    ("hero_relic", "hero_prop", "family", "Relic", "hero_relic_family", ("relic", "artifact")),
    ("hero_portal", "hero_prop", "family", "Portal", "hero_portal_family", ("portal", "threshold")),
    ("hero_vehicle", "hero_prop", "family", "Vehicle", "hero_vehicle_family", ("vehicle", "transport")),
    ("hero_weapon", "hero_prop", "family", "Weapon", "hero_weapon_family", ("weapon", "tool")),
    ("hero_tool", "hero_prop", "family", "Tool", "hero_tool_family", ("tool", "craft")),
    ("hero_furniture", "hero_prop", "family", "Furniture", "hero_furniture_family", ("furniture", "interior")),
    ("light_torch", "lighting_fixture", "family", "Torch", "light_torch_family", ("torch", "flame")),
    ("light_lamp", "lighting_fixture", "family", "Lamp", "light_lamp_family", ("lamp", "practical")),
    ("light_neon_tube", "lighting_fixture", "family", "Neon Tube", "light_neon_tube_family", ("neon", "emissive")),
    ("light_moon_window", "lighting_fixture", "kit", "Moon Window", "light_moon_window_kit", ("moon_window", "moonlight")),
    ("light_glowing_crystal", "lighting_fixture", "family", "Glowing Crystal", "light_glowing_crystal_family", ("glowing_crystal", "emissive")),
    ("light_hologram", "lighting_fixture", "family", "Hologram", "light_hologram_family", ("hologram", "projection")),
)


def _component_from_spec(spec: tuple[str, str, str, str, str, tuple[str, ...]]) -> dict[str, Any]:
    component_id, category, kind, display_name, source_ref, tags = spec
    payload: dict[str, Any] = {
        "schema_version": STDLIB_COMPONENT_VERSION,
        "component_id": component_id,
        "category": category,
        "kind": kind,
        "display_name": display_name,
        "role": _ROLE_BY_CATEGORY[category],
        "lathe_asset": component_id,
        "source_family": source_ref if kind == "family" else _SOURCE_FAMILY_BY_CATEGORY[category],
        "material_id": _MATERIAL_BY_CATEGORY[category],
        "semantic_tags": sorted({category, *tags}),
        "readiness": {
            "contract": "scene_graph_object_source",
            "mesh_runtime": "not_claimed",
            "supported_modes": ["preview", "final"],
        },
    }
    if kind == "kit":
        payload["source_kit"] = source_ref
    return payload


def iter_stdlib_components() -> Iterator[dict[str, Any]]:
    """Yield curated Wonder standard-library components in stable order."""
    for spec in _SPECS:
        yield _component_from_spec(spec)


def stdlib_component_ids() -> tuple[str, ...]:
    """Return standard-library component IDs in stable order."""
    return tuple(component["component_id"] for component in iter_stdlib_components())


def get_stdlib_component(component_id: str) -> dict[str, Any]:
    """Return one standard-library component by ID."""
    for component in iter_stdlib_components():
        if component["component_id"] == component_id:
            return component
    raise KeyError(f"unknown Wonder stdlib component: {component_id}")


def stdlib_catalog() -> dict[str, Any]:
    """Return the machine-readable curated Wonder standard-library catalog."""
    components = list(iter_stdlib_components())
    categories = sorted({str(component["category"]) for component in components})
    return {
        "schema_version": STDLIB_CATALOG_VERSION,
        "summary": {
            "components": len(components),
            "categories": categories,
            "materials": len(STDLIB_MATERIALS),
        },
        "materials": copy.deepcopy(list(STDLIB_MATERIALS)),
        "components": components,
    }


def validate_stdlib_catalog(catalog: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return diagnostics for the curated standard-library catalog."""
    payload = catalog or stdlib_catalog()
    diagnostics: list[dict[str, Any]] = []
    components = payload.get("components", [])
    if not isinstance(components, list) or not components:
        return [_diag("SL1001", "/components", "Wonder standard-library catalog has no components.")]

    seen_ids: dict[str, int] = {}
    material_ids = {
        str(material.get("material_id"))
        for material in payload.get("materials", [])
        if isinstance(material, Mapping) and isinstance(material.get("material_id"), str)
    }
    for index, component in enumerate(components):
        if not isinstance(component, Mapping):
            diagnostics.append(_diag("SL1002", f"/components/{index}", "Catalog component must be an object."))
            continue
        component_id = component.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            diagnostics.append(_diag("SL1003", f"/components/{index}/component_id", "Catalog component needs an ID."))
            continue
        first_index = seen_ids.get(component_id)
        if first_index is not None:
            diagnostics.append(
                _diag(
                    "SL1004",
                    f"/components/{index}/component_id",
                    f"Catalog component {component_id!r} duplicates /components/{first_index}.",
                )
            )
        seen_ids[component_id] = index
        for field in ("category", "kind", "display_name", "role", "lathe_asset", "source_family"):
            if not isinstance(component.get(field), str) or not component.get(field):
                diagnostics.append(
                    _diag(
                        "SL1005",
                        f"/components/{index}/{field}",
                        f"Catalog component {component_id!r} must define {field}.",
                    )
                )
        if component.get("kind") == "kit" and not isinstance(component.get("source_kit"), str):
            diagnostics.append(
                _diag(
                    "SL1007",
                    f"/components/{index}/source_kit",
                    f"Catalog kit component {component_id!r} must define source_kit.",
                )
            )
        material_id = component.get("material_id")
        if material_id not in material_ids:
            diagnostics.append(
                _diag(
                    "SL1006",
                    f"/components/{index}/material_id",
                    f"Catalog component {component_id!r} references unknown material {material_id!r}.",
                )
            )
    return diagnostics


def component_scene_object(
    component_id: str,
    *,
    index: int = 1,
    region_id: str = "region_stdlib_gallery",
    position: list[float] | None = None,
) -> dict[str, Any]:
    """Return a Scene Graph object instance for a standard-library component."""
    component = get_stdlib_component(component_id)
    object_id = f"obj_{component_id}_{index:03d}"
    affordances = []
    if component["role"] in {"hero_prop", "interactive", "light_fixture"}:
        affordances.append({"id": f"inspect_{component_id}", "action": "inspect"})
    scene_object = {
        "object_id": object_id,
        "name": component["display_name"],
        "role": component["role"],
        "region": region_id,
        "lathe_asset": component["lathe_asset"],
        "source_family": component["source_family"],
        "variant": "stdlib_default",
        "transform": {
            "position": position or [0.0, 0.0, 0.5],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
        "material_bindings": [{"slot": "body", "material": component["material_id"]}],
        "semantic_tags": list(component["semantic_tags"]),
        "state": {
            "catalog_ready": True,
            "mesh_runtime": "not_claimed",
        },
        "affordances": affordances,
        "provenance": {"source": "deterministic_lathe", "commercial_use": True},
    }
    if isinstance(component.get("source_kit"), str):
        scene_object["source_kit"] = component["source_kit"]
    return scene_object


def stdlib_showcase_scene_graph() -> dict[str, Any]:
    """Return a schema-valid Scene Graph exercising every stdlib component."""
    objects = [
        component_scene_object(component_id, position=_grid_position(index))
        for index, component_id in enumerate(stdlib_component_ids(), start=1)
    ]
    return {
        "schema_version": "lathe.scene_graph.v1",
        "scene_id": "stdlib_component_showcase",
        "version": 1,
        "prompt": "A deterministic Wonder standard-library component showcase.",
        "style_bible": {
            "mood": ["readable", "modular", "catalog"],
            "palette": ["warm stone", "simple wood", "weathered green", "aged brass", "soft emissive"],
            "materials": ["painted stone", "simple wood", "natural mineral", "aged brass", "soft emissive"],
            "forms": ["modular kits", "clear silhouettes", "scene-scale props"],
            "lighting": ["soft key", "catalog fill"],
            "avoid": [],
        },
        "layout": {
            "room_size": [28.0, 18.0, 8.0],
            "main_path": {"from": "region_entry", "to": "obj_hero_altar_001", "width": 1.5},
            "focal_point": "obj_hero_altar_001",
            "density": "dense",
            "avoid_intersections": True,
            "modular_walls": {
                "enabled": True,
                "regions": ["region_stdlib_gallery"],
                "sides": ["north", "south", "east", "west"],
                "module_length": 2.0,
                "snap_grid": 1.0,
                "height": 4.0,
                "thickness": 0.25,
            },
        },
        "regions": [
            {
                "region_id": "region_stdlib_gallery",
                "name": "Stdlib Gallery",
                "type": "interior",
                "purpose": "Show every Wonder standard-library component contract.",
                "mood": "clear",
                "bounds": {"center": [0.0, 0.0, 2.0], "size": [28.0, 18.0, 8.0]},
                "semantic_tags": ["catalog", "stdlib"],
            },
            {
                "region_id": "region_entry",
                "name": "Entry",
                "type": "threshold",
                "purpose": "Start of the showcase path.",
                "mood": "neutral",
                "bounds": {"center": [0.0, -8.0, 0.5], "size": [4.0, 1.0, 1.0]},
                "semantic_tags": ["entry"],
            },
        ],
        "objects": objects,
        "relationships": [
            {
                "relationship_id": "rel_stdlib_wall_supports_shell",
                "from": "obj_architecture_wall_001",
                "to": "obj_architecture_room_shell_001",
                "type": "supports",
                "description": "Wall modules are the primary boundary pieces for room shells.",
            },
            {
                "relationship_id": "rel_stdlib_moon_window_lights_altar",
                "from": "obj_light_moon_window_001",
                "to": "obj_hero_altar_001",
                "type": "lit_by",
                "description": "Lighting fixtures can be linked to hero props for reveal composition.",
            },
        ],
        "materials": copy.deepcopy(list(STDLIB_MATERIALS)),
        "lights": [
            {
                "light_id": "light_stdlib_key",
                "type": "area",
                "target": "obj_hero_altar_001",
                "color": "soft emissive",
                "intensity": 0.8,
                "purpose": "Readable catalog key light.",
            }
        ],
        "cameras": [
            {
                "camera_id": "camera_reveal",
                "target": "obj_hero_altar_001",
                "framing": "cinematic_wide",
                "purpose": "Reveal the standard-library component gallery.",
                "transform": {"position": [-10.0, -10.0, 5.0], "rotation": [60.0, 0.0, -35.0], "scale": [1.0, 1.0, 1.0]},
                "fov_degrees": 55.0,
            }
        ],
        "curiosity_anchors": [
            {
                "anchor_id": "curiosity_stdlib_wall_index",
                "visible_clue": "The wall index labels which modules can grow into larger room shells.",
                "hidden_fact": "The kit wall index marks which modules can expand into a larger room shell.",
                "attached_to": "obj_architecture_wall_001",
                "suggested_user_actions": ["inspect wall index", "expand room shell"],
                "expansion_options": [
                    {
                        "id": "expand_room_shell",
                        "label": "Generate a larger modular room shell.",
                        "target_scope": "region_stdlib_gallery",
                        "required_assets": ["architecture_wall", "architecture_floor", "architecture_ceiling"],
                        "continuity_constraints": ["preserve component ids"],
                    }
                ],
            },
            {
                "anchor_id": "curiosity_stdlib_light_modes",
                "visible_clue": "The moon window and torch sit side by side with distinct light colors.",
                "hidden_fact": "The moon window and torch entries demonstrate alternate lighting fixtures for mood changes.",
                "attached_to": "obj_light_moon_window_001",
                "suggested_user_actions": ["inspect lighting modes", "switch mood"],
                "expansion_options": [
                    {
                        "id": "switch_catalog_mood",
                        "label": "Show the same component set under a darker lighting plan.",
                        "target_scope": "obj_light_moon_window_001",
                        "required_assets": ["light_moon_window", "light_torch"],
                        "continuity_constraints": ["preserve object layout"],
                    }
                ],
            },
        ],
        "hidden_state": [
            {
                "hidden_id": "hidden_stdlib_wall_index",
                "attached_to": "obj_architecture_wall_001",
                "fact": "The kit wall index marks which modules can expand into a larger room shell.",
                "reveal_condition": "User inspects the wall index labels.",
                "visible": False,
            },
            {
                "hidden_id": "hidden_stdlib_light_modes",
                "attached_to": "obj_light_moon_window_001",
                "fact": "The moon window and torch entries demonstrate alternate lighting fixtures for mood changes.",
                "reveal_condition": "User inspects the lighting fixture row.",
                "visible": False,
            },
        ],
        "exports": [{"target": "scene_graph", "format": "json", "path": "exports/stdlib_component_showcase.scene_graph.json"}],
        "build_artifacts": [],
        "memory_events": [
            {
                "event_id": "mem_stdlib_catalog_created",
                "type": "fact",
                "text": "The showcase scene exercises every committed Wonder standard-library component contract.",
                "affected_ids": ["region_stdlib_gallery"],
                "source": "lathe.scene.stdlib",
            }
        ],
    }


def render_stdlib_catalog_markdown(catalog: Mapping[str, Any] | None = None) -> str:
    """Render a Markdown catalog for Wonder standard-library components."""
    payload = catalog or stdlib_catalog()
    lines = [
        "# Wonder Stdlib Catalog",
        "",
        "This catalog names reusable Wonder component contracts. Entries are stable",
        "Scene Graph source references for planning and materialization; final meshes,",
        "engine imports, and external viewer proof require separate build evidence.",
        "",
        "## Summary",
        "",
        "| Components | Categories | Materials |",
        "| --- | --- | --- |",
    ]
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), Mapping) else {}
    categories = ", ".join(str(item) for item in summary.get("categories", []) if isinstance(item, str))
    lines.append(f"| {summary.get('components', 0)} | {categories} | {summary.get('materials', 0)} |")
    lines.extend(["", "## Components", "", "| Component | Category | Source | Role | Material |", "| --- | --- | --- | --- | --- |"])
    for component in payload.get("components", []):
        if not isinstance(component, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{component.get('component_id', '')}`",
                    str(component.get("category", "")),
                    f"`{component.get('source_kit') or component.get('source_family', '')}`",
                    str(component.get("role", "")),
                    f"`{component.get('material_id', '')}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Scene Example",
            "",
            "The in-memory `stdlib_component_showcase` Scene Graph emitted by",
            "`lathe.scene.stdlib.stdlib_showcase_scene_graph()` references every",
            "component in this catalog. Unit tests validate that it passes Scene Graph",
            "schema checks, scene validators, scene planning, and generated Lathe",
            "asset-source materialization.",
            "",
        ]
    )
    return "\n".join(lines)


def _grid_position(index: int) -> list[float]:
    zero_based = index - 1
    column = zero_based % 7
    row = zero_based // 7
    return [-12.0 + column * 4.0, -6.0 + row * 2.0, 0.5]


def _diag(code: str, path: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "name": "stdlib_catalog_diagnostic",
        "severity": "error",
        "contract": "scene_stdlib_catalog",
        "phase": "scene_stdlib_catalog",
        "path": path,
        "message": message,
    }


__all__ = [
    "STDLIB_CATALOG_VERSION",
    "STDLIB_COMPONENT_VERSION",
    "STDLIB_MATERIALS",
    "component_scene_object",
    "get_stdlib_component",
    "iter_stdlib_components",
    "render_stdlib_catalog_markdown",
    "stdlib_catalog",
    "stdlib_component_ids",
    "stdlib_showcase_scene_graph",
    "validate_stdlib_catalog",
]
