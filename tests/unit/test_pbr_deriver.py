"""Unit tests for ``lathe.pbr_deriver``.

The pbr_deriver is a thin facade — currently a single
``derive_orm_map`` that composes AO / roughness / metallic into the
canonical ORM RGB packing (R=AO, G=Roughness, B=Metallic). These tests
pin the channel order, the pass-through to ``combine_orm``, the
clamp-on-extremes behavior, and a simple "large batch" sanity check
that exercises the deriver across many synthetic material payloads
without crashing.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from lathe.bake_runtime import combine_orm
from lathe.pbr_deriver import derive_orm_map


SIZE = 32


def _const_l(value: int) -> Image.Image:
    return Image.new("L", (SIZE, SIZE), value)


class TestDeriveOrmMap:
    def test_returns_rgb_image_of_input_size(self) -> None:
        orm = derive_orm_map(_const_l(180), _const_l(120), _const_l(40))
        assert orm.mode == "RGB"
        assert orm.size == (SIZE, SIZE)

    def test_channel_order_is_ao_rough_metal(self) -> None:
        orm = derive_orm_map(_const_l(200), _const_l(128), _const_l(64))
        arr = np.asarray(orm, dtype=np.uint8)
        assert (arr[..., 0] == 200).all()  # AO in R
        assert (arr[..., 1] == 128).all()  # Roughness in G
        assert (arr[..., 2] == 64).all()  # Metallic in B

    def test_zero_inputs_produce_black(self) -> None:
        orm = derive_orm_map(_const_l(0), _const_l(0), _const_l(0))
        arr = np.asarray(orm, dtype=np.uint8)
        assert arr.sum() == 0

    def test_max_inputs_produce_white(self) -> None:
        orm = derive_orm_map(_const_l(255), _const_l(255), _const_l(255))
        arr = np.asarray(orm, dtype=np.uint8)
        assert (arr == 255).all()

    def test_matches_combine_orm_directly(self) -> None:
        ao, rough, metal = _const_l(170), _const_l(90), _const_l(20)
        a = np.asarray(derive_orm_map(ao, rough, metal), dtype=np.uint8)
        b = np.asarray(combine_orm(ao, rough, metal), dtype=np.uint8)
        assert np.array_equal(a, b)

    def test_batched_derive_does_not_crash(self) -> None:
        # Many synthetic combinations sweeping the per-channel value space.
        for ao_val in (0, 64, 128, 200, 255):
            for rough_val in (16, 96, 160, 240):
                for metal_val in (0, 128, 255):
                    orm = derive_orm_map(_const_l(ao_val), _const_l(rough_val), _const_l(metal_val))
                    arr = np.asarray(orm, dtype=np.uint8)
                    assert arr.shape == (SIZE, SIZE, 3)
                    assert arr[0, 0, 0] == ao_val
                    assert arr[0, 0, 1] == rough_val
                    assert arr[0, 0, 2] == metal_val
