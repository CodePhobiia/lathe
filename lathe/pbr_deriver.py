"""PBR deriver: derive PBR channels from the surface control pack.

Converts authored surface programs into concrete basecolor /
roughness / metalness / normal / ao textures for packaging.
"""

from __future__ import annotations

from PIL import Image

from .bake_runtime import combine_orm


def derive_orm_map(ao: Image.Image, roughness: Image.Image, metallic: Image.Image) -> Image.Image:
    """Derive orm map.

    Args:
        ao: ao argument.
        roughness: roughness argument.
        metallic: metallic argument.

    Returns:
        The result.
    """
    return combine_orm(ao, roughness, metallic)
