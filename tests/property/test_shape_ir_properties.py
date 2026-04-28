"""Property-based tests for ``lathe.shape_ir`` dataclasses.

Invariants covered:

- Construction + ``to_dict`` + reconstruction yields an equal object
  (serialization round-trip preserves value semantics) for
  ``ShapePrimitive`` across a variety of valid field combinations.
- ``ShapeIR`` with empty primitives is equal to another ``ShapeIR``
  constructed with empty primitives — value equality does not require
  object identity (dataclass-auto-generated ``__eq__``).
- ``ShapeIR`` field-wise equality is sensitive to ``primitives`` order
  (the contract is order-SENSITIVE: ``asdict`` preserves list order,
  so two IRs with the same primitive set in different order are NOT
  equal). This locks in the current handoff contract.

Hypothesis is not available; ``pytest.mark.parametrize`` is used instead.
"""

from __future__ import annotations

import pytest
from lathe.shape_ir import ShapeIR, ShapePrimitive, ShapeRegion

pytestmark = pytest.mark.property


def _make_shape_ir(primitives: list[ShapePrimitive], regions: list[ShapeRegion] | None = None) -> ShapeIR:
    return ShapeIR(
        asset_name="demo",
        family="industrial_crate",
        blueprint_id="bp",
        symmetry_axis=None,
        units="m",
        primitives=list(primitives),
        regions=list(regions or []),
        primitives_used=[],
        part_graph=[],
        signature={"blueprint_notes": []},
    )


PRIMITIVE_CASES = [
    pytest.param(
        ShapePrimitive(
            primitive_type="box",
            part="body",
            center=(0.0, 0.0, 0.0),
            extents=(2.0, 2.0, 2.0),
        ),
        id="plain_box",
    ),
    pytest.param(
        ShapePrimitive(
            primitive_type="box",
            part="lid",
            center=(1.0, 2.0, 3.0),
            extents=(4.0, 5.0, 6.0),
            tags=["seam", "sealed"],
        ),
        id="box_with_tags",
    ),
    pytest.param(
        ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.0, 0.0, 0.0),
            radius=1.0,
            height=2.0,
            axis="y",
        ),
        id="cyl_y",
    ),
    pytest.param(
        ShapePrimitive(
            primitive_type="cylinder",
            part="stem",
            center=(0.5, -0.5, 1.5),
            radius=0.75,
            height=3.0,
            axis="z",
            tags=["shaft"],
            component="hinge",
            region="r1",
        ),
        id="cyl_full_fields",
    ),
    pytest.param(
        ShapePrimitive(
            primitive_type="box",
            part="overlay",
            center=(0.0, 0.0, 0.0),
            extents=(1.0, 1.0, 1.0),
            blend_mode="subtract",
            rounding=0.1,
        ),
        id="box_subtract_with_rounding",
    ),
]


@pytest.mark.parametrize("primitive", PRIMITIVE_CASES)
def test_shape_primitive_to_dict_roundtrip_preserves_equality(primitive: ShapePrimitive) -> None:
    """ShapePrimitive(**primitive.to_dict()) == primitive for all valid
    field combinations. Serialization is lossless at the value level.
    """
    payload = primitive.to_dict()
    restored = ShapePrimitive(**payload)
    assert restored == primitive
    # and transitively
    assert restored.to_dict() == payload


EMPTY_IR_CASES = [
    pytest.param(
        {"asset_name": "a", "family": "crate", "blueprint_id": "bp1", "units": "m"},
        id="default_metadata",
    ),
    pytest.param(
        {"asset_name": "a", "family": "crate", "blueprint_id": "bp1", "units": "m"},
        id="default_metadata_repeated",
    ),
    pytest.param(
        {"asset_name": "door", "family": "mechanical_door", "blueprint_id": "bp2", "units": "cm"},
        id="alt_metadata",
    ),
    pytest.param(
        {"asset_name": "console", "family": "console_terminal", "blueprint_id": "bp3", "units": "m"},
        id="console_metadata",
    ),
    pytest.param(
        {"asset_name": "chest", "family": "brassbound_chest", "blueprint_id": "bp4", "units": "m"},
        id="chest_metadata",
    ),
]


@pytest.mark.parametrize("meta", EMPTY_IR_CASES)
def test_empty_shape_ir_instances_with_same_fields_are_equal(meta: dict) -> None:
    """Two ShapeIR objects with empty primitives and identical metadata
    compare equal despite being different object identities. Dataclass
    ``__eq__`` is value-based, not identity-based.
    """
    left = ShapeIR(
        asset_name=meta["asset_name"],
        family=meta["family"],
        blueprint_id=meta["blueprint_id"],
        symmetry_axis=None,
        units=meta["units"],
        primitives=[],
        regions=[],
        primitives_used=[],
        part_graph=[],
        signature={},
    )
    right = ShapeIR(
        asset_name=meta["asset_name"],
        family=meta["family"],
        blueprint_id=meta["blueprint_id"],
        symmetry_axis=None,
        units=meta["units"],
        primitives=[],
        regions=[],
        primitives_used=[],
        part_graph=[],
        signature={},
    )
    assert left is not right
    assert left == right


ORDER_SENSITIVE_PAIRS = [
    pytest.param(
        [
            ShapePrimitive(primitive_type="box", part="a", center=(0.0, 0.0, 0.0), extents=(1.0, 1.0, 1.0)),
            ShapePrimitive(primitive_type="box", part="b", center=(2.0, 0.0, 0.0), extents=(1.0, 1.0, 1.0)),
        ],
        id="two_boxes_ab",
    ),
    pytest.param(
        [
            ShapePrimitive(
                primitive_type="box", part="body", center=(0.0, 0.0, 0.0), extents=(2.0, 2.0, 2.0)
            ),
            ShapePrimitive(
                primitive_type="cylinder",
                part="stem",
                center=(0.0, 2.0, 0.0),
                radius=0.5,
                height=1.0,
                axis="y",
            ),
        ],
        id="box_and_cyl",
    ),
    pytest.param(
        [
            ShapePrimitive(primitive_type="box", part="x", center=(0.0, 0.0, 0.0), extents=(1.0, 1.0, 1.0)),
            ShapePrimitive(primitive_type="box", part="y", center=(1.0, 0.0, 0.0), extents=(1.0, 1.0, 1.0)),
            ShapePrimitive(primitive_type="box", part="z", center=(2.0, 0.0, 0.0), extents=(1.0, 1.0, 1.0)),
        ],
        id="three_boxes",
    ),
    pytest.param(
        [
            ShapePrimitive(primitive_type="box", part="p1", center=(0.0, 0.0, 0.0), extents=(1.0, 1.0, 1.0)),
            ShapePrimitive(primitive_type="box", part="p2", center=(5.0, 5.0, 5.0), extents=(2.0, 2.0, 2.0)),
        ],
        id="distant_boxes",
    ),
    pytest.param(
        [
            ShapePrimitive(
                primitive_type="box", part="a", center=(0.0, 0.0, 0.0), extents=(1.0, 1.0, 1.0), tags=["t1"]
            ),
            ShapePrimitive(
                primitive_type="box", part="b", center=(0.0, 0.0, 0.0), extents=(1.0, 1.0, 1.0), tags=["t2"]
            ),
        ],
        id="same_position_different_tags",
    ),
]


@pytest.mark.parametrize("primitives", ORDER_SENSITIVE_PAIRS)
def test_shape_ir_equality_is_order_sensitive(primitives: list[ShapePrimitive]) -> None:
    """ShapeIR equality is order-sensitive on ``primitives``: swapping
    two distinct primitives in the list produces an UNEQUAL ShapeIR.
    This locks in the contract that ``primitives`` is an ordered
    sequence, not a set — downstream stages rely on insertion order
    for cache keys, face-label tiebreaking, and trace reporting.
    """
    forward = _make_shape_ir(primitives)
    reversed_ir = _make_shape_ir(list(reversed(primitives)))
    # The forward and reversed lists carry the same SET of primitives,
    # but ShapeIR equality compares the primitives list by position.
    assert forward != reversed_ir
    # But the to_dict payload still serializes each primitive the same
    # way regardless of placement — order only matters as a list.
    assert {p["part"] for p in forward.to_dict()["primitives"]} == {
        p["part"] for p in reversed_ir.to_dict()["primitives"]
    }


@pytest.mark.parametrize("primitives", ORDER_SENSITIVE_PAIRS)
def test_shape_ir_to_dict_emits_primitives_as_list_of_dicts(primitives: list[ShapePrimitive]) -> None:
    """to_dict() converts each ShapePrimitive in the primitives list
    into a plain dict, preserves order, and the dict length matches.
    This supports the cache-key hashing path in fuse_shape_ir which
    JSON-dumps shape_ir.primitives via to_dict().
    """
    ir = _make_shape_ir(primitives)
    payload = ir.to_dict()
    assert isinstance(payload["primitives"], list)
    assert len(payload["primitives"]) == len(primitives)
    for item in payload["primitives"]:
        assert isinstance(item, dict)
        assert "primitive_type" in item
        assert "part" in item
