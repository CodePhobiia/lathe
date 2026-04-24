"""Unit tests for ``lathe.assembly_ir.AssemblyIR``.

``AssemblyIR`` is a thin dataclass carrier that flattens the
``asset['assembly']`` block into a typed handle for downstream stages
to consume. These tests cover construction, ``from_asset`` dispatch,
serialization round-trip, default factories, and malformed-input
behaviour at the asset-dict boundary.
"""

from __future__ import annotations

import unittest

from lathe.assembly_ir import AssemblyIR


class AssemblyIRConstructionTests(unittest.TestCase):
    def test_default_construction_produces_empty_lists(self) -> None:
        ir = AssemblyIR(family="industrial_crate")
        self.assertEqual(ir.family, "industrial_crate")
        self.assertEqual(ir.components, [])
        self.assertEqual(ir.mechanisms, [])
        self.assertEqual(ir.traits, [])
        self.assertEqual(ir.resolved_components, [])
        self.assertEqual(ir.resolved_mechanisms, [])
        self.assertEqual(ir.resolved_traits, [])

    def test_default_factory_lists_are_distinct_per_instance(self) -> None:
        a = AssemblyIR(family="a")
        b = AssemblyIR(family="b")
        a.components.append("shell")
        self.assertEqual(b.components, [])

    def test_explicit_construction_with_all_fields(self) -> None:
        ir = AssemblyIR(
            family="courier_drone",
            components=["body", "rotor_arm", "rotor_pod"],
            mechanisms=["lift"],
            traits=["symmetric_quad"],
            resolved_components=[{"name": "body_core", "values": {"part": "body"}}],
            resolved_mechanisms=[{"name": "lift", "values": {}}],
            resolved_traits=[{"name": "symmetric_quad", "values": {}}],
        )
        self.assertEqual(len(ir.components), 3)
        self.assertEqual(ir.mechanisms, ["lift"])
        self.assertEqual(ir.resolved_components[0]["name"], "body_core")


class AssemblyIRFromAssetTests(unittest.TestCase):
    def test_from_asset_happy_path_populates_all_fields(self) -> None:
        asset = {
            "assembly": {
                "family": "brassbound_chest",
                "components": ["shell", "lid", "lock_plate"],
                "mechanisms": ["hinge"],
                "traits": ["reinforced"],
                "resolved_components": [
                    {"name": "shell_core", "values": {"part": "body"}},
                    {"name": "lid_top", "values": {"part": "lid"}},
                ],
                "resolved_mechanisms": [{"name": "hinge", "values": {}}],
                "resolved_traits": [{"name": "reinforced", "values": {}}],
            }
        }
        ir = AssemblyIR.from_asset(asset)
        self.assertEqual(ir.family, "brassbound_chest")
        self.assertEqual(ir.components, ["shell", "lid", "lock_plate"])
        self.assertEqual(ir.mechanisms, ["hinge"])
        self.assertEqual(ir.traits, ["reinforced"])
        self.assertEqual(len(ir.resolved_components), 2)

    def test_from_asset_empty_dict_defaults_to_empty_ir(self) -> None:
        ir = AssemblyIR.from_asset({})
        self.assertEqual(ir.family, "")
        self.assertEqual(ir.components, [])
        self.assertEqual(ir.resolved_components, [])

    def test_from_asset_missing_assembly_block_defaults_cleanly(self) -> None:
        # Some asset dicts never populate the assembly block at all — the
        # IR must still materialize with empty defaults, not raise.
        ir = AssemblyIR.from_asset({"name": "bare"})
        self.assertEqual(ir.family, "")
        self.assertEqual(ir.components, [])
        self.assertEqual(ir.mechanisms, [])

    def test_from_asset_coerces_non_string_family_to_str(self) -> None:
        # family stored as int — from_asset applies str() defensively.
        ir = AssemblyIR.from_asset({"assembly": {"family": 7}})
        self.assertEqual(ir.family, "7")

    def test_from_asset_non_iterable_components_raises_type_error(self) -> None:
        # components must be iterable; passing a non-iterable surfaces
        # TypeError from list(...) — downstream stages rely on this.
        with self.assertRaises(TypeError):
            AssemblyIR.from_asset({"assembly": {"components": 5}})


class AssemblyIRSerializationTests(unittest.TestCase):
    def test_to_dict_round_trip_preserves_all_fields(self) -> None:
        ir = AssemblyIR(
            family="courier_drone",
            components=["body", "rotor_arm"],
            mechanisms=["lift"],
            traits=[],
            resolved_components=[{"name": "body_core"}],
            resolved_mechanisms=[{"name": "lift"}],
            resolved_traits=[],
        )
        payload = ir.to_dict()
        self.assertEqual(payload["family"], "courier_drone")
        self.assertEqual(payload["components"], ["body", "rotor_arm"])
        self.assertEqual(payload["resolved_components"], [{"name": "body_core"}])
        # Round-trip through ``**payload`` reconstructs the same IR.
        restored = AssemblyIR(**payload)
        self.assertEqual(restored, ir)

    def test_ir_level_uniqueness_of_component_names(self) -> None:
        # Downstream stages treat resolved_components' ``name`` field as a
        # unique key. AssemblyIR does not enforce this, but we pin the
        # expectation here so tooling can detect collisions explicitly.
        ir = AssemblyIR(
            family="industrial_crate",
            resolved_components=[
                {"name": "body_core", "values": {"part": "body"}},
                {"name": "lid_top", "values": {"part": "lid"}},
            ],
        )
        names = [entry["name"] for entry in ir.resolved_components]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
