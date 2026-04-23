"""Back-compat shim — see ADR-0005 (``plans/03_architecture.md`` Phase 1).

The contents of this module were split into the ``lathe.providers``
subpackage in Wave 2.III.  This file re-exports the full public (and
test-patched) surface so existing imports — including
``unittest.mock.patch('lathe.shape_providers._probe_vggt')`` — continue to
work unchanged.

Remove after V1.4 when downstream callers have migrated to
``lathe.providers`` imports.
"""
from __future__ import annotations

from .providers import (  # noqa: F401
    PROVIDER_ALIASES,
    PROVIDERS,
    ShapeMeshLoadError,
    ShapeProviderError,
    ShapeProviderExecutionError,
    ShapeProviderUnavailable,
    _characteristic_scale_cm,
    _conditioned_part_colors,
    _hunyuan_request,
    _hunyuan_safe_text,
    _hunyuan_transient_status,
    _load_mesh_file,
    _make_color,
    _mesh_body_count,
    _mesh_quality_score,
    _non_material_image_refs,
    _normalize_mesh_to_scale,
    _probe_hunyuan_endpoint,
    _probe_vggt,
    _redact_provider_config,
    _root_name,
    _run_hunyuan_http_provider,
    _run_vggt_local_provider,
    _runtime_from_mesh,
    _select_primary_image,
    _short_provider_name,
    _to_conf_numpy,
    _to_point_map_numpy,
    _triangle_ok,
    _triangulate_point_grid,
    _unit_to_cm,
    get_provider,
    list_shape_providers,
    maybe_run_shape_provider,
    mesh_from_point_maps,
    normalize_provider_id,
    probe_all_shape_providers,
    probe_shape_provider,
    provider_config,
    resolve_shape_provider,
)


__all__ = [
    "PROVIDER_ALIASES",
    "PROVIDERS",
    "ShapeMeshLoadError",
    "ShapeProviderError",
    "ShapeProviderExecutionError",
    "ShapeProviderUnavailable",
    "get_provider",
    "list_shape_providers",
    "maybe_run_shape_provider",
    "mesh_from_point_maps",
    "normalize_provider_id",
    "probe_all_shape_providers",
    "probe_shape_provider",
    "provider_config",
    "resolve_shape_provider",
]
