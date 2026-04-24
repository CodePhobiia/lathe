"""Unit tests for ``lathe.shape_ir`` dataclasses.

Covers ``ShapePrimitive``, ``ShapeRegion``, and ``ShapeIR`` construction,
default field population, and serialization round-trips. These IRs carry
no runtime logic — the contract is purely structural — so the tests focus
on field shapes, dict round-trips, and the assessment access patterns the
downstream stages depend on (``required_part_coverage``, ``feature_density``,
and friends).
"""

from __future__ import annotations

import unittest

from lathe.shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


def _box_primitive(
    *, part: str = "body", center: tuple[float, float, float] = (0.0, 0.0, 0.0)
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="box",
        part=part,
        center=center,
        extents=(2.0, 2.0, 2.0),
    )


def _cylinder_primitive(
    *, part: str = "stem", axis: str = "y"
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="cylinder",
        part=part,
        center=(0.0, 0.0, 0.0),
        radius=0.5,
        height=2.0,
        axis=axis,
    )


def _region(
    *, name: str = "region_body", part: str = "body"
) -> ShapeRegion:
    return ShapeRegion(
        name=name,
        part=part,
        component="hull",
        center=(0.0, 0.0, 0.0),
        extents=(2.0, 2.0, 2.0),
    )


def _empty_shape_ir() -> ShapeIR:
    return ShapeIR(
        asset_name="demo",
        family="industrial_crate",
        blueprint_id="bp1",
        symmetry_axis=None,
        units="m",
        primitives=[],
        regions=[],
        primitives_used=[],
        part_graph=[],
        signature={},
    )


class ShapePrimitiveTests(unittest.TestCase):
    def test_box_primitive_basic_fields(self) -> None:
        p = _box_primitive()
        self.assertEqual(p.primitive_type, "box")
        self.assertEqual(p.extents, (2.0, 2.0, 2.0))
        self.assertIsNone(p.radius)
        self.assertIsNone(p.height)
        # default axis + blend
        self.assertEqual(p.axis, "y")
        self.assertEqual(p.blend_mode, "union")
        self.assertEqual(p.rounding, 0.0)
        self.assertEqual(p.tags, [])

    def test_cylinder_primitive_requires_radius_and_height(self) -> None:
        p = _cylinder_primitive(axis="z")
        self.assertEqual(p.primitive_type, "cylinder")
        self.assertEqual(p.radius, 0.5)
        self.assertEqual(p.height, 2.0)
        self.assertEqual(p.axis, "z")
        self.assertIsNone(p.extents)

    def test_primitive_to_dict_roundtrip(self) -> None:
        p = _box_primitive()
        payload = p.to_dict()
        restored = ShapePrimitive(**payload)
        self.assertEqual(restored, p)
        # tuple/list equivalence: dataclass stores extents as tuple at construction;
        # asdict preserves the stored type — verify the key is present and populated.
        self.assertIn("extents", payload)
        self.assertEqual(tuple(payload["extents"]), (2.0, 2.0, 2.0))

    def test_primitive_distinct_default_tags(self) -> None:
        # default_factory=list must produce a fresh list per instance
        a = _box_primitive(part="a")
        b = _box_primitive(part="b")
        a.tags.append("seam")
        self.assertEqual(b.tags, [])


class ShapeRegionTests(unittest.TestCase):
    def test_region_basic_fields(self) -> None:
        r = _region()
        self.assertEqual(r.part, "body")
        self.assertEqual(r.component, "hull")
        self.assertTrue(r.required)
        self.assertIsNone(r.symmetry_mate)
        self.assertEqual(r.adjacency, [])

    def test_region_to_dict_roundtrip(self) -> None:
        r = _region()
        payload = r.to_dict()
        restored = ShapeRegion(**payload)
        self.assertEqual(restored, r)


class ShapeIRTests(unittest.TestCase):
    def test_empty_primitives_list_allowed(self) -> None:
        s = _empty_shape_ir()
        self.assertEqual(s.primitives, [])
        self.assertEqual(s.regions, [])
        self.assertEqual(s.assessment, {})

    def test_to_dict_serializes_nested_primitives_and_regions(self) -> None:
        s = _empty_shape_ir()
        s.primitives.append(_box_primitive())
        s.primitives.append(_cylinder_primitive())
        s.regions.append(_region())
        payload = s.to_dict()
        self.assertEqual(len(payload["primitives"]), 2)
        self.assertEqual(len(payload["regions"]), 1)
        # Nested items are dicts, not dataclass instances.
        self.assertIsInstance(payload["primitives"][0], dict)
        self.assertIsInstance(payload["regions"][0], dict)
        self.assertEqual(payload["primitives"][0]["primitive_type"], "box")
        self.assertEqual(payload["primitives"][1]["primitive_type"], "cylinder")

    def test_assessment_access_patterns(self) -> None:
        # Downstream (repair_planner) reads these keys via .get(); ShapeIR
        # must accept an assessment dict populated with any of them.
        s = _empty_shape_ir()
        s.assessment.update(
            {
                "required_part_coverage": 0.95,
                "feature_density": 0.62,
                "edge_treatment_count": 5,
                "panel_feature_count": 4,
                "support_feature_count": 2,
                "feature_types": ["rotor_shroud", "panel"],
                "feature_coherence": 0.71,
                "richness_floor": 0.58,
            }
        )
        # .get() must return stored values
        self.assertEqual(s.assessment.get("required_part_coverage"), 0.95)
        self.assertEqual(s.assessment.get("feature_density"), 0.62)
        # .get() defaults for absent keys match repair_planner expectations
        self.assertEqual(s.assessment.get("missing_key", 0.0), 0.0)
        self.assertEqual(s.assessment.get("feature_types", []), ["rotor_shroud", "panel"])

    def test_signature_blueprint_notes_key_supported(self) -> None:
        # geometry_kernel.solid_ir_from_shape reads shape_ir.signature["blueprint_notes"].
        s = ShapeIR(
            asset_name="demo",
            family="industrial_crate",
            blueprint_id="bp1",
            symmetry_axis=None,
            units="m",
            primitives=[_box_primitive()],
            regions=[_region()],
            primitives_used=["box"],
            part_graph=[{"parent": "root", "child": "body"}],
            signature={"blueprint_notes": ["seeded", "baseline"]},
        )
        self.assertEqual(s.signature["blueprint_notes"], ["seeded", "baseline"])
        self.assertEqual(len(s.part_graph), 1)

    def test_missing_required_box_extents_raises_on_geometry_use(self) -> None:
        # ShapePrimitive dataclass itself allows missing extents (they're
        # Optional), but geometry kernel rejects with ContractViolation.
        from lathe.errors import ContractViolation
        from lathe.geometry_kernel import _primitive_bounds

        bad = ShapePrimitive(primitive_type="box", part="body", center=(0.0, 0.0, 0.0))
        with self.assertRaises(ContractViolation):
            _primitive_bounds(bad)

    def test_missing_required_cylinder_fields_raises_on_geometry_use(self) -> None:
        from lathe.errors import ContractViolation
        from lathe.geometry_kernel import _primitive_bounds

        bad = ShapePrimitive(
            primitive_type="cylinder", part="stem", center=(0.0, 0.0, 0.0)
        )
        with self.assertRaises(ContractViolation):
            _primitive_bounds(bad)


if __name__ == "__main__":
    unittest.main()
