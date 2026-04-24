"""Backend / stack registry and compatibility checks.

Registers stable stack IDs (``lathe.stack.hard_surface_game_asset_v1``
and friends) and provides the compatibility matrix the checker uses
to reject mis-wired plans before runtime.

Second stack scope note (BL-34, Plan 08 Phase 4, Wave 4.IV.e scope-down):
``lathe.stack.soft_surface_prop_v1`` is registered as a *proof of the
plugin model*. The topology adapter ``lathe.topology.blender_subdiv_v1``
delegates to the hard-surface Blender adapter today and the UV stage
reuses xatlas in a soft-padding mode hook. Real subdivision-surface
topology with curvature continuity and full soft-padding UV is deferred
to a future ticket; see ``docs/second_backend_stack.md`` for the gap
analysis.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

# re-export — authoritative definition lives in lathe/errors.py
from .errors import BackendResolutionError

_LOGGER = logging.getLogger(__name__)


PACKAGE_FORMATS = ["usd", "usdz", "glb", "gltf", "fbx", "obj"]
BACKEND_SELECTION_STAGES = ["shape", "topology", "uv", "package"]


BACKENDS: dict[str, dict[str, Any]] = {
    "lathe.shape.intent_mesh_handoff_v1": {
        "id": "lathe.shape.intent_mesh_handoff_v1",
        "version": "2.0.0",
        "stage": "shape",
        "toolchain": ["reference_runtime", "trimesh", "Pillow"],
        "runtime_executor": "lathe.runtime.shape.provider_mux_v2",
        "determinism_class": "seeded",
        "supported_asset_kinds": ["hard_surface_prop", "env_module", "mechanical_assembly"],
        "supported_shape_modes": ["generate", "reconstruct", "adapt", "assemble"],
        "supported_preserve": ["silhouette", "part_graph", "symmetry", "proportions", "interfaces"],
        "provider_slots": [
            "lathe.provider.shape.reference_conditioned_v1",
            "lathe.provider.shape.hunyuan2_1_http_v1",
            "lathe.provider.shape.vggt_local_v1",
        ],
        "contract": {
            "summary": "Reference-conditioned AI handoff boundary that turns Lathe intent and available refs into one or more mesh candidates for generate, reconstruct, adapt, or assemble modes.",
            "inputs": {
                "required": ["kind", "intent.role", "build.shape.mode"],
                "optional": [
                    "refs.images",
                    "refs.meshes",
                    "refs.assets",
                    "intent.parts",
                    "intent.materials",
                    "intent.negatives",
                    "build.shape.candidates",
                    "build.shape.seed",
                    "build.shape.symmetry",
                    "build.shape.preserve",
                ],
                "mode_requirements": {
                    "generate": ["intent.role"],
                    "reconstruct": ["one_of(refs.images, refs.meshes)"],
                    "adapt": ["one_of(refs.meshes, refs.assets)"],
                    "assemble": ["refs.assets"],
                },
            },
            "outputs": {
                "artifact": "shape_bundle",
                "required_fields": [
                    "candidates[].mesh_uri",
                    "candidates[].units",
                    "candidates[].frame",
                    "candidates[].candidate_id",
                    "provenance.backend_id",
                    "provenance.backend_version",
                ],
                "optional_fields": [
                    "candidates[].part_labels",
                    "candidates[].coarse_material_slots",
                    "candidates[].preview_images",
                    "provenance.seed",
                    "provenance.external_job_id",
                    "provenance.consumed_refs",
                    "conditioning_report",
                ],
                "guarantees": [
                    "returns at least one mesh candidate",
                    "declares source units and frame for every candidate",
                    "retains mapping back to source refs and seed when available",
                ],
            },
        },
    },
    "lathe.topology.blender_hard_surface_v1": {
        "id": "lathe.topology.blender_hard_surface_v1",
        "version": "1.0.0",
        "stage": "topology",
        "toolchain": ["reference_runtime", "trimesh"],
        "runtime_executor": "lathe.runtime.topology.cleanup_v1",
        "determinism_class": "deterministic",
        "supported_asset_kinds": ["hard_surface_prop", "env_module", "mechanical_assembly"],
        "supported_retopo": ["auto", "none", "reference"],
        "supported_preserve": ["hard_edges", "seams", "part_borders"],
        "contract": {
            "summary": "Headless Blender cleanup and hard-surface retopo pass for a single authoritative production mesh.",
            "inputs": {
                "required": ["shape_bundle", "build.topology.retopo", "build.topology.ngons"],
                "optional": [
                    "build.topology.target_quads",
                    "build.topology.target_tris",
                    "build.topology.preserve",
                ],
            },
            "outputs": {
                "artifact": "topology_bundle",
                "required_fields": [
                    "mesh_uri",
                    "mesh_stats.vertex_count",
                    "mesh_stats.triangle_count",
                    "normals",
                    "part_groups",
                    "provenance.backend_id",
                ],
                "guarantees": [
                    "one authoritative post-cleanup mesh",
                    "part names preserved where possible",
                    "topology report available for downstream validation",
                ],
            },
        },
    },
    "lathe.topology.blender_subdiv_v1": {
        "id": "lathe.topology.blender_subdiv_v1",
        "version": "0.1.0",
        "stage": "topology",
        "toolchain": ["reference_runtime", "trimesh"],
        "runtime_executor": "lathe.runtime.topology.cleanup_v1",
        "determinism_class": "deterministic",
        "supported_asset_kinds": ["hard_surface_prop", "env_module", "mechanical_assembly"],
        "supported_retopo": ["auto", "none", "reference"],
        "supported_preserve": ["soft_folds", "seams", "part_borders"],
        "contract": {
            "summary": (
                "Subdivision-surface topology adapter for soft-surface props. "
                "Proof-of-plugin-model under BL-34 (Plan 08 Phase 4, scoped). "
                "Delegates to the hard-surface Blender adapter today; the full "
                "curvature-continuity subdiv pass is deferred."
            ),
            "inputs": {
                "required": ["shape_bundle", "build.topology.retopo", "build.topology.ngons"],
                "optional": [
                    "build.topology.target_quads",
                    "build.topology.target_tris",
                    "build.topology.preserve",
                ],
            },
            "outputs": {
                "artifact": "topology_bundle",
                "required_fields": [
                    "mesh_uri",
                    "mesh_stats.vertex_count",
                    "mesh_stats.triangle_count",
                    "normals",
                    "part_groups",
                    "provenance.backend_id",
                ],
                "guarantees": [
                    "one authoritative post-cleanup mesh",
                    "part names preserved where possible",
                    "topology report available for downstream soft-silhouette validation",
                ],
            },
        },
    },
    "lathe.uv.xatlas_v1": {
        "id": "lathe.uv.xatlas_v1",
        "version": "1.0.0",
        "stage": "uv",
        "toolchain": ["reference_runtime", "trimesh"],
        "runtime_executor": "lathe.runtime.uv.box_atlas_v1",
        "determinism_class": "deterministic",
        "supported_asset_kinds": ["hard_surface_prop", "env_module", "mechanical_assembly"],
        "supported_tile_modes": ["zero_to_one"],
        "supported_unwrap": ["auto"],
        "supported_sets": ["base", "lightmap"],
        "contract": {
            "summary": "Atlas generation and unique UV unwrapping for game-ready texture and lightmap channels.",
            "inputs": {
                "required": ["topology_bundle", "build.uv.sets", "build.uv.tile_mode", "build.uv.padding"],
                "optional": ["build.uv.texel_density", "build.uv.pack_rotate"],
            },
            "outputs": {
                "artifact": "uv_bundle",
                "required_fields": [
                    "mesh_uri",
                    "uv_sets[].name",
                    "uv_sets[].coverage",
                    "packing_report.chart_count",
                    "provenance.backend_id",
                ],
                "guarantees": [
                    "base UVs are uniquely unwrapped into 0..1 space",
                    "lightmap UV set is emitted when requested",
                    "packing report is available for diagnostics",
                ],
            },
        },
    },
    "lathe.package.openusd_gltf_v1": {
        "id": "lathe.package.openusd_gltf_v1",
        "version": "1.0.0",
        "stage": "package",
        "toolchain": ["trimesh", "Pillow", "openusd_text"],
        "runtime_executor": "lathe.runtime.package.bundle_v1",
        "determinism_class": "deterministic",
        "supported_asset_kinds": ["hard_surface_prop", "env_module", "mechanical_assembly"],
        "supported_formats": ["usd", "glb", "gltf", "obj"],
        "format_routes": {
            "usd": "openusd_text",
            "glb": "trimesh_glb",
            "gltf": "trimesh_gltf",
            "obj": "trimesh_obj",
        },
        "contract": {
            "summary": "Authoritative packaging pass that emits interchange USD plus runtime-oriented glTF/GLB/OBJ deliverables and manifests.",
            "inputs": {
                "required": [
                    "optimized_asset",
                    "package.formats",
                    "package.manifest",
                    "package.include_trace",
                ],
                "optional": [
                    "package.previews",
                    "package.embed_textures",
                    "publish.registry",
                    "publish.version",
                ],
            },
            "outputs": {
                "artifact": "package_bundle",
                "required_fields": [
                    "outputs[].format",
                    "outputs[].uri",
                    "manifest_path",
                    "normalized_source_path",
                    "trace_path",
                ],
                "guarantees": [
                    "USD package root is written when usd is requested",
                    "GLB/glTF exports are generated with runtime delivery metadata",
                    "package manifest and trace manifest are always emitted when enabled",
                ],
            },
        },
    },
}


STACKS: dict[str, dict[str, Any]] = {
    "lathe.stack.hard_surface_game_asset_v1": {
        "id": "lathe.stack.hard_surface_game_asset_v1",
        "name": "Hard-surface game asset v1",
        "description": "Single probabilistic shape handoff followed by deterministic hard-surface cleanup, UVing, and packaging.",
        "supported_asset_kinds": ["hard_surface_prop", "env_module", "mechanical_assembly"],
        "supported_package_formats": ["usd", "glb", "gltf", "obj"],
        "stage_backends": {
            "shape": "lathe.shape.intent_mesh_handoff_v1",
            "topology": "lathe.topology.blender_hard_surface_v1",
            "uv": "lathe.uv.xatlas_v1",
            "package": "lathe.package.openusd_gltf_v1",
        },
        "constraints": [
            "uv.tile_mode must be zero_to_one",
            "uv.unwrap must be auto",
            "package.formats must be subset of [usd, glb, gltf, obj]",
        ],
        "selection_reason": "Best first stack for hard-surface props because it isolates the AI-native step to shape generation and keeps productionization deterministic downstream.",
    },
    "lathe.stack.soft_surface_prop_v1": {
        "id": "lathe.stack.soft_surface_prop_v1",
        "name": "Soft-surface prop v1",
        "description": (
            "Second backend stack registered as a proof of the plugin model "
            "(BL-34 / Plan 08 Phase 4, scoped). Reuses the shape handoff "
            "contract and UV/package backends; binds a subdivision-topology "
            "adapter for soft-surface silhouettes."
        ),
        "supported_asset_kinds": ["hard_surface_prop", "env_module", "mechanical_assembly"],
        "supported_package_formats": ["usd", "glb", "gltf", "obj"],
        "stage_backends": {
            "shape": "lathe.shape.intent_mesh_handoff_v1",
            "topology": "lathe.topology.blender_subdiv_v1",
            "uv": "lathe.uv.xatlas_v1",
            "package": "lathe.package.openusd_gltf_v1",
        },
        "constraints": [
            "uv.tile_mode must be zero_to_one",
            "uv.unwrap must be auto",
            "package.formats must be subset of [usd, glb, gltf, obj]",
        ],
        "selection_reason": (
            "Selected when the asset opts into a subdivision-style topology "
            "backend (``build.topology.backend = lathe.topology.blender_subdiv_v1``). "
            "Proof-of-plugin-model; the soft-silhouette validator and "
            "soft-padding UV mode are intentionally scaffolded -- see "
            "docs/second_backend_stack.md for the gap analysis."
        ),
        "scope_status": "proof_of_plugin_model",
    },
}


def _deepcopy(obj: Any) -> Any:
    return deepcopy(obj)


def list_backends() -> list[dict[str, Any]]:
    """List backends.

    Returns:
        The result.
    """
    return [_deepcopy(BACKENDS[key]) for key in sorted(BACKENDS)]


def list_stacks() -> list[dict[str, Any]]:
    """List stacks.

    Returns:
        The result.
    """
    return [_deepcopy(STACKS[key]) for key in sorted(STACKS)]


def get_backend(backend_id: str) -> dict[str, Any]:
    """Get backend.

    Args:
        backend_id: backend_id argument.

    Returns:
        The result.
    """
    if backend_id not in BACKENDS:
        raise BackendResolutionError(f"Unknown backend '{backend_id}'")
    return _deepcopy(BACKENDS[backend_id])


def _get_stage_config(asset: dict[str, Any], stage: str) -> dict[str, Any]:
    if stage == "package":
        return asset.get("package", {})
    return asset.get("build", {}).get(stage, {})


def _get_explicit_backend_id(asset: dict[str, Any], stage: str) -> str:
    config = _get_stage_config(asset, stage)
    value = config.get("backend", "auto")
    if value in (None, ""):
        return "auto"
    return value


def evaluate_backend(backend_id: str, asset: dict[str, Any], stage: str) -> tuple[bool, list[str]]:
    """Evaluate backend.

    Args:
        backend_id: backend_id argument.
        asset: asset argument.
        stage: stage argument.

    Returns:
        The result.
    """
    backend = get_backend(backend_id)
    reasons: list[str] = []
    if backend["stage"] != stage:
        reasons.append(f"backend stage mismatch: expected {stage}, got {backend['stage']}")
    if asset.get("kind") not in backend.get("supported_asset_kinds", []):
        reasons.append(f"asset kind '{asset.get('kind')}' is not supported")

    if stage == "shape":
        mode = asset.get("build", {}).get("shape", {}).get("mode", "generate")
        if mode not in backend.get("supported_shape_modes", []):
            reasons.append(f"shape mode '{mode}' is not supported")
    elif stage == "topology":
        retopo = asset.get("build", {}).get("topology", {}).get("retopo", "auto")
        if retopo not in backend.get("supported_retopo", []):
            reasons.append(f"topology.retopo '{retopo}' is not supported")
    elif stage == "uv":
        uv = asset.get("build", {}).get("uv", {})
        tile_mode = uv.get("tile_mode", "zero_to_one")
        unwrap = uv.get("unwrap", "auto")
        sets = uv.get("sets", ["base"])
        if tile_mode not in backend.get("supported_tile_modes", []):
            reasons.append(f"uv.tile_mode '{tile_mode}' is not supported")
        if unwrap not in backend.get("supported_unwrap", []):
            reasons.append(f"uv.unwrap '{unwrap}' is not supported")
        unsupported_sets = [name for name in sets if name not in backend.get("supported_sets", [])]
        if unsupported_sets:
            reasons.append(f"uv.sets contains unsupported entries: {unsupported_sets}")
    elif stage == "package":
        formats = asset.get("package", {}).get("formats", [])
        unsupported = [fmt for fmt in formats if fmt not in backend.get("supported_formats", [])]
        if unsupported:
            reasons.append(f"package.formats contains unsupported entries: {unsupported}")

    return (not reasons), reasons


def evaluate_stack(stack_id: str, asset: dict[str, Any]) -> tuple[bool, list[str]]:
    """Evaluate stack.

    Args:
        stack_id: stack_id argument.
        asset: asset argument.

    Returns:
        The result.
    """
    if stack_id not in STACKS:
        raise BackendResolutionError(f"Unknown backend stack '{stack_id}'")
    stack = STACKS[stack_id]
    reasons: list[str] = []
    if asset.get("kind") not in stack.get("supported_asset_kinds", []):
        reasons.append(f"asset kind '{asset.get('kind')}' is not supported by stack '{stack_id}'")
    formats = asset.get("package", {}).get("formats", [])
    unsupported_formats = [fmt for fmt in formats if fmt not in stack.get("supported_package_formats", [])]
    if unsupported_formats:
        reasons.append(f"package.formats contains unsupported entries: {unsupported_formats}")

    for stage in BACKEND_SELECTION_STAGES:
        explicit = _get_explicit_backend_id(asset, stage)
        backend_id = explicit if explicit != "auto" else stack["stage_backends"][stage]
        try:
            ok, stage_reasons = evaluate_backend(backend_id, asset, stage)
        except BackendResolutionError as exc:
            reasons.append(f"{stage}: {exc}")
            continue
        if not ok:
            reasons.extend([f"{stage}: {reason}" for reason in stage_reasons])

    return (not reasons), reasons


def _explicit_stage_bindings(asset: dict[str, Any]) -> dict[str, str]:
    """Return explicit ``build.<stage>.backend`` / ``package.backend`` overrides.

    Used by :func:`select_stack` to prefer stacks whose default stage
    bindings match the asset's explicit overrides. This is what lets an
    asset opt into a non-default stack (e.g. ``soft_surface_prop_v1``)
    without a language-surface change.
    """
    explicit: dict[str, str] = {}
    for stage in BACKEND_SELECTION_STAGES:
        value = _get_explicit_backend_id(asset, stage)
        if value != "auto":
            explicit[stage] = value
    return explicit


def _stack_match_score(stack: dict[str, Any], explicit: dict[str, str]) -> int:
    """Rank a stack by how many explicit bindings align with its defaults.

    Higher is better. Ties are broken alphabetically by stack id (see
    :func:`select_stack`), which keeps the legacy hard-surface stack as
    the default when no explicit bindings are set.
    """
    bindings = stack.get("stage_backends", {})
    return sum(1 for stage, backend_id in explicit.items() if bindings.get(stage) == backend_id)


def select_stack(asset: dict[str, Any]) -> dict[str, Any]:
    """Select stack.

    Order of preference (BL-34, Plan 08 Phase 4):

    1. Compatible stacks whose default stage bindings match the asset's
       explicit ``build.<stage>.backend`` overrides score higher. This
       is how an asset opts into the second stack without a language
       surface change.
    2. Ties fall back to alphabetical stack id (legacy behavior --
       ``hard_surface_game_asset_v1`` wins when no explicit overrides
       are set).

    Args:
        asset: asset argument.

    Returns:
        The result.
    """
    explicit = _explicit_stage_bindings(asset)
    compatible: list[tuple[int, str]] = []
    for stack_id in sorted(STACKS):
        ok, _reasons = evaluate_stack(stack_id, asset)
        if ok:
            score = _stack_match_score(STACKS[stack_id], explicit)
            compatible.append((score, stack_id))
    if not compatible:
        raise BackendResolutionError(
            "No builtin backend stack matches the asset configuration"
        )
    # Sort by -score, then stack_id (alphabetical). The first stack wins.
    compatible.sort(key=lambda item: (-item[0], item[1]))
    chosen_id = compatible[0][1]
    stack = _deepcopy(STACKS[chosen_id])
    stack["resolved"] = True
    return stack


# ---------------------------------------------------------------------------
# Plugin registry (Plan 03 Phase 2)
# ---------------------------------------------------------------------------
#
# Third-party packages register extra backends, stacks, providers, or
# validators via ``[project.entry-points]`` in their pyproject.toml. The
# four groups are:
#
#   - ``lathe.backends``          -> dict registered into BACKENDS
#   - ``lathe.stacks``            -> dict registered into STACKS
#   - ``lathe.providers.shape``   -> dict descriptor registered into the
#                                    shape-provider registry
#   - ``lathe.validators``        -> callable evaluator
#
# Built-in backends/stacks are also exported through entry points so
# third-party plugins have a reference implementation. The module-level
# constants below are the stable importable names that entry points
# resolve to.
#
# See ``docs/extending.md`` for author-facing guidance.

# Module-level shims used by [project.entry-points."lathe.backends"] /
# "lathe.stacks". Entry points can only reference importable symbols,
# so we expose each built-in registry row as a top-level constant.
hard_surface_topology_backend: dict[str, Any] = BACKENDS["lathe.topology.blender_hard_surface_v1"]
subdiv_topology_backend: dict[str, Any] = BACKENDS["lathe.topology.blender_subdiv_v1"]
xatlas_uv_backend: dict[str, Any] = BACKENDS["lathe.uv.xatlas_v1"]
openusd_gltf_package_backend: dict[str, Any] = BACKENDS["lathe.package.openusd_gltf_v1"]
intent_mesh_handoff_shape_backend: dict[str, Any] = BACKENDS["lathe.shape.intent_mesh_handoff_v1"]

hard_surface_stack: dict[str, Any] = STACKS["lathe.stack.hard_surface_game_asset_v1"]
soft_surface_stack: dict[str, Any] = STACKS["lathe.stack.soft_surface_prop_v1"]


_PLUGIN_BACKENDS_LOADED = False


def load_plugin_backends(*, force: bool = False) -> dict[str, list[str]]:
    """Discover backends/stacks registered via entry points.

    Scans the ``lathe.backends`` and ``lathe.stacks`` entry-point groups
    exposed by installed distributions and merges the resolved descriptor
    dicts into :data:`BACKENDS` / :data:`STACKS`. IDs that already exist
    are *not* overridden (the built-in definition wins); duplicates are
    logged at ``DEBUG`` level so plugin authors can notice collisions.

    The function is idempotent: subsequent calls are a no-op unless
    ``force=True`` is passed (mainly for tests). Missing or non-importable
    entry points are logged and skipped so a broken third-party plugin
    cannot prevent Lathe from starting.

    Returns:
        A ``{"backends": [...], "stacks": [...]}`` map of *added* IDs.
    """
    global _PLUGIN_BACKENDS_LOADED
    added: dict[str, list[str]] = {"backends": [], "stacks": []}
    if _PLUGIN_BACKENDS_LOADED and not force:
        return added

    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        _PLUGIN_BACKENDS_LOADED = True
        return added

    for group, registry, bucket in (
        ("lathe.backends", BACKENDS, "backends"),
        ("lathe.stacks", STACKS, "stacks"),
    ):
        try:
            eps = entry_points(group=group)
        except TypeError:  # pragma: no cover - Python <3.10 API
            eps = entry_points().get(group, [])  # type: ignore[attr-defined]
        for ep in eps:
            try:
                descriptor = ep.load()
            except Exception as exc:  # noqa: BLE001 - plugin failures are non-fatal
                _LOGGER.warning(
                    "lathe plugin entry-point %r (%s) failed to load: %s",
                    ep.name,
                    group,
                    exc,
                )
                continue
            if not isinstance(descriptor, dict) or "id" not in descriptor:
                _LOGGER.warning(
                    "lathe plugin entry-point %r (%s) is not a descriptor dict with an 'id' field; skipping",
                    ep.name,
                    group,
                )
                continue
            plugin_id = descriptor["id"]
            if plugin_id in registry:
                _LOGGER.debug(
                    "lathe plugin %r from %s collides with built-in %r; built-in wins",
                    ep.name,
                    group,
                    plugin_id,
                )
                continue
            registry[plugin_id] = descriptor
            added[bucket].append(plugin_id)

    _PLUGIN_BACKENDS_LOADED = True
    return added


def resolve_selected_backends(asset: dict[str, Any]) -> dict[str, Any]:
    """Resolve selected backends.

    Args:
        asset: asset argument.

    Returns:
        The result.
    """
    stack = select_stack(asset)
    selected: dict[str, Any] = {}
    for stage in BACKEND_SELECTION_STAGES:
        explicit = _get_explicit_backend_id(asset, stage)
        backend_id = explicit if explicit != "auto" else stack["stage_backends"][stage]
        backend = get_backend(backend_id)
        selected[stage] = {
            "id": backend["id"],
            "version": backend["version"],
            "determinism_class": backend["determinism_class"],
            "toolchain": backend["toolchain"],
            "runtime_executor": backend.get("runtime_executor"),
            "selected_via": "explicit" if explicit != "auto" else "stack",
            "contract": backend["contract"],
        }
        if stage == "package":
            selected[stage]["format_routes"] = backend.get("format_routes", {})
    return {
        "stack": {
            "id": stack["id"],
            "name": stack["name"],
            "description": stack["description"],
            "selection_reason": stack["selection_reason"],
        },
        "selected": selected,
    }
