"""Unit tests for ``lathe.assembly_kernel``.

Covers the blueprint-to-ShapeIR compilation path: ``BlueprintComponent``
/ ``AssemblyBlueprint`` dataclasses, ``_component_primitives`` dispatch,
``compile_assembly_blueprint``, ``refresh_shape_ir``, and the small
geometry helpers ``mirrored`` and ``polar_offset``. The assembly kernel
is part of the stable ``lathe.shape.intent_mesh_handoff_v1`` contract
so we pin the shape of its output (signature keys, assessment keys,
primitive counts) without asserting exact byte-level values where
re-scaling would be overly brittle.
"""

from __future__ import annotations

import unittest

import numpy as np
from lathe.assembly_kernel import (
    AssemblyBlueprint,
    BlueprintComponent,
    compile_assembly_blueprint,
    mirrored,
    polar_offset,
    refresh_shape_ir,
)
from lathe.asset_graph import build_asset_graph
from lathe.blueprints import resolve_blueprint
from lathe.shape_ir import ShapeIR


def _asset_graph(parts: list[str] | None = None, *, role: str = "crate", kind: str = "prop"):
    return build_asset_graph(
        {
            "name": "demo",
            "kind": kind,
            "intent": {"role": role, "parts": list(parts or ["body", "lid"])},
            "build": {"shape": {"symmetry": "auto"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        }
    )


def _component(
    *,
    name: str = "body_core",
    component_type: str = "shell",
    part: str = "body",
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    extents: tuple[float, float, float] = (10.0, 6.0, 4.0),
    **kwargs,
) -> BlueprintComponent:
    return BlueprintComponent(
        name=name,
        component_type=component_type,
        part=part,
        center=center,
        extents=extents,
        **kwargs,
    )


def _simple_blueprint(components: list[BlueprintComponent] | None = None) -> AssemblyBlueprint:
    return AssemblyBlueprint(
        blueprint_id="lathe.blueprint.test_v1",
        family="industrial_crate",
        components=list(components or [_component()]),
        notes=["seeded"],
    )


class BlueprintDataclassTests(unittest.TestCase):
    def test_blueprint_component_to_dict_round_trip(self) -> None:
        component = _component(tags=["feature"], adjacency=["lid"])
        payload = component.to_dict()
        restored = BlueprintComponent(**payload)
        self.assertEqual(restored, component)

    def test_assembly_blueprint_to_dict_nests_components(self) -> None:
        blueprint = _simple_blueprint(
            [_component(), _component(name="lid_top", part="lid", component_type="lid")]
        )
        payload = blueprint.to_dict()
        self.assertEqual(payload["blueprint_id"], "lathe.blueprint.test_v1")
        self.assertEqual(len(payload["components"]), 2)
        self.assertIsInstance(payload["components"][0], dict)


class CompileAssemblyBlueprintTests(unittest.TestCase):
    def test_standard_blueprint_produces_shape_ir_with_regions_and_primitives(self) -> None:
        asset_graph = _asset_graph(["body", "lid"])
        blueprint = _simple_blueprint(
            [
                _component(name="body_core", component_type="shell", part="body"),
                _component(
                    name="lid_top",
                    component_type="lid",
                    part="lid",
                    center=(0.0, 3.5, 0.0),
                    extents=(10.0, 1.5, 4.0),
                ),
            ]
        )
        shape_ir = compile_assembly_blueprint(asset_graph, blueprint)

        self.assertIsInstance(shape_ir, ShapeIR)
        self.assertEqual(shape_ir.asset_name, "demo")
        self.assertEqual(shape_ir.blueprint_id, "lathe.blueprint.test_v1")
        self.assertEqual(len(shape_ir.regions), 2)
        # shell + lid builders each emit 2 primitives → 4 total
        self.assertGreaterEqual(len(shape_ir.primitives), 4)
        self.assertIn("required_part_coverage", shape_ir.assessment)
        self.assertIn("expected_extents", shape_ir.signature)
        self.assertEqual(shape_ir.signature["blueprint_notes"], ["seeded"])

    def test_empty_blueprint_produces_empty_shape_ir(self) -> None:
        asset_graph = _asset_graph(["body", "lid"])
        empty = AssemblyBlueprint(
            blueprint_id="lathe.blueprint.test_v1",
            family="industrial_crate",
            components=[],
        )
        shape_ir = compile_assembly_blueprint(asset_graph, empty)

        self.assertEqual(shape_ir.primitives, [])
        self.assertEqual(shape_ir.regions, [])
        # assessment still present — required_part_coverage = 0 when no regions
        self.assertEqual(shape_ir.assessment["region_count"], 0)
        self.assertEqual(shape_ir.assessment["primitive_count"], 0)
        self.assertEqual(shape_ir.assessment["required_part_coverage"], 0.0)

    def test_primitive_count_sanity_for_vent_slats(self) -> None:
        # The vent builder fans out into 4 slat primitives regardless of
        # component extents — this anchors the expected count.
        asset_graph = _asset_graph(["vent"])
        blueprint = _simple_blueprint([_component(name="vent_face", component_type="vent", part="vent")])
        shape_ir = compile_assembly_blueprint(asset_graph, blueprint)
        self.assertEqual(len(shape_ir.primitives), 4)
        self.assertEqual(len(shape_ir.regions), 1)

    def test_sword_blueprint_produces_weapon_regions(self) -> None:
        asset_graph = build_asset_graph(
            {
                "name": "hero_sword",
                "kind": "hard_surface_prop",
                "intent": {
                    "role": "hero medieval sword",
                    "parts": [
                        "long_tapered_blade",
                        "central_fuller",
                        "sharp_tip",
                        "crossguard",
                        "leather_wrapped_grip",
                        "round_pommel",
                    ],
                    "scale": {"type": "unit", "value": 1.25, "unit": "m"},
                },
                "assembly": {
                    "resolved_family": {
                        "values": {
                            "runtime_family": "hero_sword",
                            "blueprint_id": "lathe.blueprint.hero_sword_v1",
                        }
                    },
                    "resolved_components": [],
                },
                "build": {"shape": {"symmetry": "x"}, "rig": {}, "interfaces": {}},
                "validate": {"threshold": 0.74},
            }
        )
        blueprint = resolve_blueprint(asset_graph, {}, np.random.default_rng(113), 0)
        shape_ir = compile_assembly_blueprint(asset_graph, blueprint)

        self.assertEqual(blueprint.blueprint_id, "lathe.blueprint.hero_sword_v1")
        self.assertEqual(
            {region.component for region in shape_ir.regions},
            {"blade", "fuller", "blade_tip", "guard", "grip", "pommel"},
        )
        self.assertIn("long_tapered_blade", {primitive.part for primitive in shape_ir.primitives})
        self.assertGreaterEqual(shape_ir.assessment["feature_count"], 24)
        self.assertGreaterEqual(shape_ir.assessment["primitive_count"], 32)
        self.assertGreater(shape_ir.signature["expected_extents"][1], 120.0)

    def test_unsupported_component_type_raises_value_error(self) -> None:
        asset_graph = _asset_graph(["body"])
        blueprint = _simple_blueprint(
            [_component(name="mystery", component_type="mystery_builder", part="body")]
        )
        with self.assertRaises(ValueError):
            compile_assembly_blueprint(asset_graph, blueprint)

    def test_nested_composition_multi_component_regions_preserve_names(self) -> None:
        # Many component types emitted together — verify each region keeps
        # its identifier and component type.
        asset_graph = _asset_graph(["body", "lid", "hinge", "handle"])
        blueprint = _simple_blueprint(
            [
                _component(name="body_core", component_type="shell", part="body"),
                _component(name="lid_top", component_type="lid", part="lid"),
                _component(
                    name="hinge_left",
                    component_type="hinge",
                    part="hinge",
                    radius=0.5,
                    height=2.0,
                ),
                _component(
                    name="handle_front",
                    component_type="handle",
                    part="handle",
                    radius=0.25,
                    height=3.0,
                ),
            ]
        )
        shape_ir = compile_assembly_blueprint(asset_graph, blueprint)
        names = [region.name for region in shape_ir.regions]
        self.assertEqual(names, ["body_core", "lid_top", "hinge_left", "handle_front"])
        components = {region.component for region in shape_ir.regions}
        self.assertEqual(components, {"shell", "lid", "hinge", "handle"})

    def test_deterministic_identical_inputs_produce_identical_ir(self) -> None:
        # No RNG in compile_assembly_blueprint — identical blueprints must
        # yield identical serialized output.
        asset_graph = _asset_graph(["body", "lid"])
        blueprint_a = _simple_blueprint(
            [
                _component(name="body_core", component_type="shell", part="body"),
                _component(
                    name="lid_top",
                    component_type="lid",
                    part="lid",
                    center=(0.0, 3.5, 0.0),
                    extents=(10.0, 1.5, 4.0),
                ),
            ]
        )
        blueprint_b = _simple_blueprint(
            [
                _component(name="body_core", component_type="shell", part="body"),
                _component(
                    name="lid_top",
                    component_type="lid",
                    part="lid",
                    center=(0.0, 3.5, 0.0),
                    extents=(10.0, 1.5, 4.0),
                ),
            ]
        )
        ir_a = compile_assembly_blueprint(asset_graph, blueprint_a)
        ir_b = compile_assembly_blueprint(asset_graph, blueprint_b)
        self.assertEqual(ir_a.to_dict(), ir_b.to_dict())


class RefreshShapeIRTests(unittest.TestCase):
    def test_refresh_rebuilds_signature_and_assessment(self) -> None:
        asset_graph = _asset_graph(["body", "lid"])
        blueprint = _simple_blueprint(
            [
                _component(name="body_core", component_type="shell", part="body"),
                _component(
                    name="lid_top",
                    component_type="lid",
                    part="lid",
                    center=(0.0, 3.5, 0.0),
                    extents=(10.0, 1.5, 4.0),
                ),
            ]
        )
        shape_ir = compile_assembly_blueprint(asset_graph, blueprint)
        refreshed = refresh_shape_ir(asset_graph, shape_ir, notes=["re-run"])

        self.assertEqual(refreshed.blueprint_id, shape_ir.blueprint_id)
        self.assertEqual(refreshed.signature["blueprint_notes"], ["re-run"])
        # same primitive count → same expected_extents & same assessment keys
        self.assertEqual(
            refreshed.signature["expected_extents"],
            shape_ir.signature["expected_extents"],
        )
        self.assertEqual(
            set(refreshed.assessment.keys()),
            set(shape_ir.assessment.keys()),
        )


class ChestBevelAndBandTests(unittest.TestCase):
    """Tests for chest-specific brass band and edge-class bevel wiring."""

    def test_brass_band_emits_three_torus_primitives(self) -> None:
        from lathe.assembly_kernel import _chest_brass_band_primitives

        body = BlueprintComponent(
            name="chest_body",
            component_type="shell",
            part="body",
            center=(0.0, 50.0, 0.0),
            extents=(80.0, 60.0, 50.0),
            tags=["body", "shell"],
        )
        blueprint = AssemblyBlueprint(
            blueprint_id="lathe.blueprint.hard_surface_chest_v2",
            family="brassbound_chest",
            components=[body],
        )
        primitives, regions = _chest_brass_band_primitives(blueprint)

        self.assertEqual(len(primitives), 3)
        self.assertEqual(len(regions), 3)
        for primitive in primitives:
            self.assertEqual(primitive.primitive_type, "torus")
            self.assertEqual(primitive.component, "band")
            self.assertIn("brass_band", primitive.tags)
            self.assertIn("aged_brass_trim", primitive.tags)
            self.assertIsNotNone(primitive.major_radius)
            self.assertIsNotNone(primitive.minor_radius)

    def test_brass_band_returns_empty_without_body(self) -> None:
        from lathe.assembly_kernel import _chest_brass_band_primitives

        blueprint = AssemblyBlueprint(
            blueprint_id="lathe.blueprint.hard_surface_chest_v2",
            family="brassbound_chest",
            components=[],
        )
        primitives, regions = _chest_brass_band_primitives(blueprint)
        self.assertEqual(primitives, [])
        self.assertEqual(regions, [])

    def test_edge_class_bevel_tags_hero_components_with_hero_bevel(self) -> None:
        from lathe.assembly_kernel import _apply_chest_edge_class_bevels
        from lathe.shape_ir import ShapePrimitive

        primitives = [
            ShapePrimitive(
                primitive_type="subdivision_box",
                part="body",
                center=(0, 0, 0),
                extents=(80, 60, 50),
                component="shell",
                tags=["body", "shell"],
            ),
            ShapePrimitive(
                primitive_type="extruded_profile",
                part="lock_plate",
                center=(0, 0, 0),
                extrude_height=2.0,
                profile_polygon=[(0, 0), (1, 0), (1, 1), (0, 1)],
                component="lock_plate",
                tags=["lock_plate"],
            ),
            ShapePrimitive(
                primitive_type="subdivision_box",
                part="foot_l",
                center=(0, 0, 0),
                extents=(8, 12, 8),
                component="foot",
                tags=["foot"],
            ),
        ]
        tagged = _apply_chest_edge_class_bevels(
            primitives,
            edge_classes=["hero_bevel", "support_bevel", "trim_edge"],
            seam_classes=["panel_seam", "lid_break", "clasp_cut"],
        )
        self.assertEqual(tagged, 3)

        shell, lock, foot = primitives
        self.assertIsNotNone(shell.v2_polybevel_modifier)
        self.assertEqual(shell.v2_polybevel_modifier["width_cm"], 0.30)
        self.assertIn("lid_break", shell.v2_polybevel_modifier["target_seam_groups"])
        self.assertIn("panel_seam", shell.v2_polybevel_modifier["target_seam_groups"])

        self.assertIsNotNone(lock.v2_polybevel_modifier)
        self.assertEqual(lock.v2_polybevel_modifier["width_cm"], 0.05)
        self.assertEqual(lock.v2_polybevel_modifier["target_seam_groups"], ["clasp_cut"])

        self.assertIsNotNone(foot.v2_polybevel_modifier)
        self.assertEqual(foot.v2_polybevel_modifier["width_cm"], 0.15)
        self.assertEqual(foot.v2_polybevel_modifier["target_seam_groups"], ["panel_seam"])

    def test_edge_class_bevel_no_op_when_no_edge_classes(self) -> None:
        from lathe.assembly_kernel import _apply_chest_edge_class_bevels
        from lathe.shape_ir import ShapePrimitive

        primitive = ShapePrimitive(
            primitive_type="subdivision_box",
            part="body",
            center=(0, 0, 0),
            extents=(10, 10, 10),
            component="shell",
        )
        tagged = _apply_chest_edge_class_bevels(
            [primitive], edge_classes=[], seam_classes=[]
        )
        self.assertEqual(tagged, 0)
        self.assertIsNone(primitive.v2_polybevel_modifier)

    def test_edge_class_bevel_does_not_clobber_existing_modifier(self) -> None:
        from lathe.assembly_kernel import _apply_chest_edge_class_bevels
        from lathe.shape_ir import ShapePrimitive

        primitive = ShapePrimitive(
            primitive_type="subdivision_box",
            part="body",
            center=(0, 0, 0),
            extents=(10, 10, 10),
            component="shell",
            v2_polybevel_modifier={"width_cm": 1.0, "segments": 1, "target_seam_groups": ["custom"]},
        )
        tagged = _apply_chest_edge_class_bevels(
            [primitive],
            edge_classes=["hero_bevel"],
            seam_classes=["lid_break", "panel_seam"],
        )
        self.assertEqual(tagged, 0)
        self.assertEqual(primitive.v2_polybevel_modifier["width_cm"], 1.0)


class GeometryHelperTests(unittest.TestCase):
    def test_mirrored_x_flips_x_only(self) -> None:
        self.assertEqual(mirrored((1.0, 2.0, 3.0), axis="x"), (-1.0, 2.0, 3.0))

    def test_mirrored_z_flips_z_only(self) -> None:
        self.assertEqual(mirrored((1.0, 2.0, 3.0), axis="z"), (1.0, 2.0, -3.0))

    def test_mirrored_unsupported_axis_raises(self) -> None:
        with self.assertRaises(ValueError):
            mirrored((1.0, 2.0, 3.0), axis="y")

    def test_polar_offset_zero_degrees_is_x_axis(self) -> None:
        x, y, z = polar_offset(5.0, 0.0, 1.0)
        self.assertAlmostEqual(x, 5.0, places=5)
        self.assertEqual(y, 1.0)
        self.assertAlmostEqual(z, 0.0, places=5)

    def test_polar_offset_ninety_degrees_is_z_axis(self) -> None:
        x, y, z = polar_offset(5.0, 90.0, 2.0)
        self.assertAlmostEqual(x, 0.0, places=5)
        self.assertEqual(y, 2.0)
        self.assertAlmostEqual(z, 5.0, places=5)


if __name__ == "__main__":
    unittest.main()
