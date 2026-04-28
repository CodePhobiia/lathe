"""Unit tests for ``lathe.surface_ir.SurfaceIR``.

``SurfaceIR`` is a V1.2 extractor dataclass that lifts surface authoring
state (program, policy, backend, palette, patterns, decal libraries,
mask programs, trim sheets) from a materialized asset. It performs no
validation — the resolver/checker enforce semantic rules upstream — so
these tests focus on construction, defaulting, dict round-trip, and
V1.2 policy integration.
"""

from __future__ import annotations

import unittest

from lathe.surface_ir import SurfaceIR


class SurfaceIRConstructionTests(unittest.TestCase):
    def test_default_construction_all_empty(self) -> None:
        ir = SurfaceIR()
        self.assertEqual(ir.program, "")
        self.assertEqual(ir.material_graph, "")
        self.assertEqual(ir.backend, "")
        self.assertEqual(ir.policy, "")
        self.assertEqual(ir.patterns, [])
        self.assertEqual(ir.decal_libraries, [])
        self.assertEqual(ir.mask_programs, [])
        self.assertEqual(ir.trim_sheets, [])
        self.assertEqual(ir.authoring, {})
        self.assertEqual(ir.resolved_surface_policy, {})

    def test_construction_with_values(self) -> None:
        ir = SurfaceIR(
            program="hard_surface_stylized",
            material_graph="brass_panel_graph",
            backend="lathe.surface.deterministic_pbr_v1",
            policy="hero_surface_policy",
            patterns=["rivets", "trim"],
            palette="warm_industrial",
            material_zones=["body", "lid"],
        )
        self.assertEqual(ir.program, "hard_surface_stylized")
        self.assertEqual(ir.material_graph, "brass_panel_graph")
        self.assertEqual(ir.patterns, ["rivets", "trim"])
        self.assertEqual(ir.material_zones, ["body", "lid"])

    def test_default_factory_lists_are_independent(self) -> None:
        a = SurfaceIR()
        b = SurfaceIR()
        a.patterns.append("seam")
        a.material_zones.append("body")
        self.assertEqual(b.patterns, [])
        self.assertEqual(b.material_zones, [])


class SurfaceIRFromAssetTests(unittest.TestCase):
    def test_from_asset_empty_surface(self) -> None:
        ir = SurfaceIR.from_asset({})
        self.assertEqual(ir.program, "")
        self.assertEqual(ir.backend, "")
        self.assertEqual(ir.patterns, [])
        self.assertEqual(ir.resolved_surface_policy, {})

    def test_from_asset_basic_fields(self) -> None:
        asset = {
            "surface": {
                "program": "hard_surface_stylized",
                "material_graph": "brass_panel_graph",
                "backend": "lathe.surface.deterministic_pbr_v1",
                "policy": "hero_surface_policy",
                "patterns": ["rivets", "trim"],
                "palette": "warm_industrial",
                "material_zones": ["body", "lid"],
                "materials": ["brass", "steel"],
                "decals": ["dec_a"],
                "bake": ["basecolor", "normal"],
            }
        }
        ir = SurfaceIR.from_asset(asset)
        self.assertEqual(ir.program, "hard_surface_stylized")
        self.assertEqual(ir.material_graph, "brass_panel_graph")
        self.assertEqual(ir.backend, "lathe.surface.deterministic_pbr_v1")
        self.assertEqual(ir.policy, "hero_surface_policy")
        self.assertEqual(ir.patterns, ["rivets", "trim"])
        self.assertEqual(ir.palette, "warm_industrial")
        self.assertEqual(ir.materials, ["brass", "steel"])
        self.assertEqual(ir.decals, ["dec_a"])
        self.assertEqual(ir.bake, ["basecolor", "normal"])

    def test_from_asset_v12_policy_integration(self) -> None:
        asset = {
            "surface": {
                "policy": "hero_surface_policy",
                "decal_libraries": ["lib_generic"],
                "mask_programs": ["wear_mask_program"],
                "trim_sheets": ["trim_hero"],
                "authoring": {"mode": "zone_first", "generate": ["basecolor"]},
                "resolved_surface_policy": {
                    "name": "hero_surface_policy",
                    "values": {"on_backend_unavailable": "fail"},
                },
                "resolved_surface_backend": {
                    "name": "lathe.surface.codex_imagegen_v1",
                    "values": {"mode": "zone_first"},
                },
                "resolved_patterns": [{"name": "rivets"}, {"name": "trim"}],
                "resolved_decal_libraries": [{"name": "lib_generic"}],
                "resolved_mask_programs": [{"name": "wear_mask_program"}],
                "resolved_trim_sheets": [{"name": "trim_hero"}],
            }
        }
        ir = SurfaceIR.from_asset(asset)
        self.assertEqual(ir.decal_libraries, ["lib_generic"])
        self.assertEqual(ir.mask_programs, ["wear_mask_program"])
        self.assertEqual(ir.trim_sheets, ["trim_hero"])
        self.assertEqual(ir.authoring["mode"], "zone_first")
        self.assertEqual(ir.resolved_surface_policy["values"]["on_backend_unavailable"], "fail")
        self.assertEqual(
            ir.resolved_surface_backend["name"],
            "lathe.surface.codex_imagegen_v1",
        )
        self.assertEqual(len(ir.resolved_patterns), 2)
        self.assertEqual(len(ir.resolved_decal_libraries), 1)
        self.assertEqual(len(ir.resolved_trim_sheets), 1)

    def test_from_asset_coerces_non_string_requireds(self) -> None:
        # ``from_asset`` uses str() coercion — int/None fed into scalar keys
        # should be stringified rather than raise.
        asset = {"surface": {"program": 123, "backend": None}}
        ir = SurfaceIR.from_asset(asset)
        self.assertEqual(ir.program, "123")
        # str(None) == "None" — the coercion accepts it. The point is no raise.
        self.assertIsInstance(ir.backend, str)


class SurfaceIRRoundTripTests(unittest.TestCase):
    def test_to_dict_round_trip(self) -> None:
        ir = SurfaceIR(
            program="p",
            backend="b",
            policy="pol",
            patterns=["x"],
            authoring={"mode": "zone_first"},
        )
        payload = ir.to_dict()
        restored = SurfaceIR(**payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.program, "p")
        self.assertEqual(restored.authoring["mode"], "zone_first")

    def test_to_dict_keys_are_full_field_set(self) -> None:
        ir = SurfaceIR()
        payload = ir.to_dict()
        for key in (
            "program",
            "material_graph",
            "backend",
            "policy",
            "patterns",
            "palette",
            "material_zones",
            "materials",
            "decals",
            "bake",
            "decal_libraries",
            "mask_programs",
            "trim_sheets",
            "authoring",
            "resolved_surface_program",
            "resolved_material_graph",
            "resolved_surface_backend",
            "resolved_surface_policy",
            "resolved_patterns",
            "resolved_palette",
            "resolved_materials",
            "resolved_decal_libraries",
            "resolved_mask_programs",
            "resolved_trim_sheets",
        ):
            self.assertIn(key, payload)


class SurfaceIRMalformedTests(unittest.TestCase):
    def test_from_asset_malformed_patterns_raises(self) -> None:
        # Non-iterable for a list-typed key must raise; list() coercion
        # will fail on a non-iterable value.
        asset = {"surface": {"patterns": 42}}
        with self.assertRaises(TypeError):
            SurfaceIR.from_asset(asset)

    def test_from_asset_malformed_authoring_raises(self) -> None:
        # ``authoring`` is coerced through dict(...); a non-mapping raises.
        asset = {"surface": {"authoring": ["not", "a", "mapping"]}}
        with self.assertRaises((TypeError, ValueError)):
            SurfaceIR.from_asset(asset)


if __name__ == "__main__":
    unittest.main()
