"""Unit tests for ``lathe.solid_ir`` dataclasses.

Covers ``SolidOp`` and ``SolidIR`` construction and the tailored
``SolidIR.to_dict`` implementation (which manually serializes ops rather
than relying on ``asdict`` round-tripping). The SolidIR is produced by
``geometry_kernel.solid_ir_from_shape`` and embedded in the integration
report, so the dict form is effectively part of the shape-stage handoff
contract.
"""

from __future__ import annotations

import unittest

from lathe.solid_ir import SolidIR, SolidOp


def _op(
    *,
    op: str = "union",
    primitive_type: str = "box",
    part: str = "body",
    region: str | None = "region_body",
    component: str | None = "hull",
    params: dict | None = None,
    tags: list[str] | None = None,
) -> SolidOp:
    return SolidOp(
        op=op,
        primitive_type=primitive_type,
        part=part,
        region=region,
        component=component,
        params=params if params is not None else {"center": [0.0, 0.0, 0.0], "extents": [2.0, 2.0, 2.0]},
        tags=tags if tags is not None else [],
    )


class SolidOpTests(unittest.TestCase):
    def test_basic_construction(self) -> None:
        op = _op()
        self.assertEqual(op.op, "union")
        self.assertEqual(op.primitive_type, "box")
        self.assertEqual(op.part, "body")
        self.assertEqual(op.region, "region_body")
        self.assertEqual(op.component, "hull")
        self.assertEqual(op.params["extents"], [2.0, 2.0, 2.0])

    def test_to_dict_preserves_all_fields(self) -> None:
        op = _op(op="subtract", tags=["seam", "hard_edge"])
        payload = op.to_dict()
        self.assertEqual(payload["op"], "subtract")
        self.assertEqual(payload["tags"], ["seam", "hard_edge"])
        self.assertIn("params", payload)
        self.assertEqual(payload["params"]["extents"], [2.0, 2.0, 2.0])

    def test_optional_region_and_component_can_be_none(self) -> None:
        op = _op(region=None, component=None)
        self.assertIsNone(op.region)
        self.assertIsNone(op.component)
        # to_dict should still carry the None values — downstream consumers
        # rely on the keys being present even when unset.
        payload = op.to_dict()
        self.assertIn("region", payload)
        self.assertIn("component", payload)
        self.assertIsNone(payload["region"])
        self.assertIsNone(payload["component"])

    def test_default_tags_list_not_shared(self) -> None:
        a = _op(tags=None)
        # forge fresh defaults via the dataclass (not the helper)
        a2 = SolidOp(
            op="union",
            primitive_type="box",
            part="body",
            region=None,
            component=None,
            params={},
        )
        b2 = SolidOp(
            op="union",
            primitive_type="box",
            part="body",
            region=None,
            component=None,
            params={},
        )
        a2.tags.append("x")
        self.assertEqual(b2.tags, [])
        # helper with explicit default is isolated too
        a.tags.append("y")
        self.assertEqual(b2.tags, [])


class SolidIRTests(unittest.TestCase):
    def test_basic_construction(self) -> None:
        ir = SolidIR(
            asset_name="demo",
            family="industrial_crate",
            operations=[_op()],
        )
        self.assertEqual(ir.asset_name, "demo")
        self.assertEqual(ir.family, "industrial_crate")
        self.assertEqual(len(ir.operations), 1)
        self.assertEqual(ir.notes, [])

    def test_empty_operations_list_allowed(self) -> None:
        ir = SolidIR(asset_name="demo", family="industrial_crate", operations=[])
        payload = ir.to_dict()
        self.assertEqual(payload["operations"], [])
        self.assertEqual(payload["notes"], [])

    def test_to_dict_serializes_nested_ops(self) -> None:
        ir = SolidIR(
            asset_name="demo",
            family="industrial_crate",
            operations=[_op(part="a"), _op(part="b", op="subtract")],
            notes=["seeded", "baseline"],
        )
        payload = ir.to_dict()
        self.assertEqual(payload["asset_name"], "demo")
        self.assertEqual(payload["family"], "industrial_crate")
        self.assertEqual(len(payload["operations"]), 2)
        # ops must be dicts, not SolidOp instances
        self.assertIsInstance(payload["operations"][0], dict)
        self.assertEqual(payload["operations"][0]["part"], "a")
        self.assertEqual(payload["operations"][1]["op"], "subtract")
        # notes is copied — not the same list object
        self.assertEqual(payload["notes"], ["seeded", "baseline"])
        self.assertIsNot(payload["notes"], ir.notes)

    def test_to_dict_notes_defensive_copy(self) -> None:
        ir = SolidIR(
            asset_name="demo",
            family="industrial_crate",
            operations=[],
            notes=["one"],
        )
        payload = ir.to_dict()
        payload["notes"].append("mutation")
        # mutating the payload list must not affect the source IR
        self.assertEqual(ir.notes, ["one"])

    def test_operations_preserve_ordering(self) -> None:
        ops = [_op(part=f"part_{i}") for i in range(5)]
        ir = SolidIR(asset_name="demo", family="industrial_crate", operations=ops)
        payload = ir.to_dict()
        parts = [entry["part"] for entry in payload["operations"]]
        self.assertEqual(parts, ["part_0", "part_1", "part_2", "part_3", "part_4"])


if __name__ == "__main__":
    unittest.main()
