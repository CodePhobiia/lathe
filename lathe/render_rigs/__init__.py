"""Render evaluation subsystem (Wave 8).

Standardized lighting rigs + canonical view definitions + silhouette
matching. Per ``docs/research/newresearch.md`` §13+§7: procedural
assets must be evaluated under fixed cameras, fixed lights, fixed
exposure, fixed FOV, fixed tonemapping — not whatever scene happens
to be open.
"""

from .standard_rigs import LIGHTING_RIGS, LightRig, LightSource
from .canonical_views import CANONICAL_VIEWS, ViewSpec

__all__ = [
    "LIGHTING_RIGS",
    "LightRig",
    "LightSource",
    "CANONICAL_VIEWS",
    "ViewSpec",
]
