from __future__ import annotations

from PIL import Image

from .bake_runtime import combine_orm


def derive_orm_map(ao: Image.Image, roughness: Image.Image, metallic: Image.Image) -> Image.Image:
    return combine_orm(ao, roughness, metallic)
