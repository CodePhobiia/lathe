"""Shape-provider subsystem.

Public surface re-exports kept stable for callers that import via
``lathe.providers.*`` or (through the ``lathe.shape_providers`` shim) via
the original flat module.  See ``ADR-0005`` / ``plans/03_architecture.md``
Phase 1.
"""

from __future__ import annotations

from ..capabilities import probe_hunyuan_endpoint as _probe_hunyuan_endpoint  # noqa: F401
from ..capabilities import probe_vggt as _probe_vggt  # noqa: F401
from .adapters.hunyuan import (
    _hunyuan_request,  # noqa: F401
    _non_material_image_refs,  # noqa: F401
    _select_primary_image,  # noqa: F401
)
from .adapters.hunyuan import run_hunyuan_http_provider as _run_hunyuan_http_provider  # noqa: F401
from .adapters.vggt import (  # noqa: F401
    _to_conf_numpy,
    _to_point_map_numpy,
    _triangle_ok,
    _triangulate_point_grid,
    mesh_from_point_maps,
)
from .adapters.vggt import run_vggt_local_provider as _run_vggt_local_provider  # noqa: F401
from .errors import (
    ShapeMeshLoadError,
    ShapeProviderError,
    ShapeProviderExecutionError,
    ShapeProviderUnavailable,
)
from .mesh_ops import (  # noqa: F401
    _characteristic_scale_cm,
    _conditioned_part_colors,
    _load_mesh_file,
    _make_color,
    _mesh_body_count,
    _mesh_quality_score,
    _normalize_mesh_to_scale,
    _root_name,
    _runtime_from_mesh,
    _unit_to_cm,
)
from .registry import (  # noqa: F401
    PROVIDER_ALIASES,
    PROVIDERS,
    _short_provider_name,
    get_provider,
    list_shape_providers,
    normalize_provider_id,
    provider_config,
)
from .selection import (  # noqa: F401
    _redact_provider_config,
    maybe_run_shape_provider,
    probe_all_shape_providers,
    probe_shape_provider,
    resolve_shape_provider,
)
from .transport.http import (  # noqa: F401
    hunyuan_safe_text as _hunyuan_safe_text,
)
from .transport.http import (
    hunyuan_transient_status as _hunyuan_transient_status,  # noqa: F401
)

__all__ = [
    "PROVIDERS",
    "PROVIDER_ALIASES",
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
