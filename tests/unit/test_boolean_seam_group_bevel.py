"""Regression test for the boolean -> seam_group -> bevel chain (roadmap §5.1).

Lathe's hard-surface authoring idiom binds a ``boolean`` op to a named
``seam_group`` and then asks for a ``polybevel`` over edges classified by
that group. The two-step contract is:

  1. ``ShapePrimitive.boolean_seam_groups`` records the seam name on the
     boolean operand. After the boolean fuses, the post-boolean pass
     extracts result edges that border the operand's bbox and tags them
     with the seam name.
  2. ``ShapePrimitive.v2_polybevel_modifier`` (with
     ``target_seam_groups``) drives the cutback pass that inserts an
     edge-loop strip along those tagged edges, replacing sharp corners
     with a chamfered loop of ``segments`` faces of width ``width_cm``.

These tests pin the wire-up so future refactors of either side cannot
silently regress the chain to sharp corners. The visible signal is a
multiplicative growth in face/vertex count when the modifier is present
versus the same boolean without the modifier.
"""
from __future__ import annotations

import unittest

from lathe.exact_solids import compile_explicit_surface_mesh
from lathe.feature_ops import box_with_seam_group, fillet_edge, tag_boolean_seam_group
from lathe.fidelity import FidelityProfile
from lathe.shape_ir import ShapeIR, ShapePrimitive


def _hero_fidelity() -> FidelityProfile:
    return FidelityProfile(
        tier="hero",
        detail_density=1.35,
        edge_weight=1.25,
        panel_depth=1.30,
        trim_complexity=5,
        support_complexity=1.20,
        silhouette_refinement=1.18,
        repair_budget=4,
    )


def _make_panel_cut_ir(*, with_bevel: bool, width_cm: float = 1.0, segments: int = 4) -> ShapeIR:
    """Build a minimal ShapeIR equivalent to:

        body   = box(10cm cubed)
        cutout = box(8x8x4cm).translate((0,0,4cm))
        result = boolean(op: subtract, a: body, b: cutout, seam_group: "lip")
        if with_bevel:
            fillet_edge(target: result, edge_class: "lip", radius=width_cm, segments=segments)
    """
    body = ShapePrimitive(
        primitive_type="box",
        part="body",
        center=(0.0, 0.0, 0.0),
        extents=(10.0, 10.0, 10.0),
        blend_mode="union",
    )
    cutout_kwargs: dict = dict(
        primitive_type="box",
        part="body",
        center=(0.0, 0.0, 4.0),
        extents=(8.0, 8.0, 4.0),
        blend_mode="subtract",
    )
    if with_bevel:
        cutout_kwargs["boolean_seam_groups"] = [
            {"name": "lip", "operation": "subtract", "target": "body"}
        ]
        cutout_kwargs["bevel_seam_groups"] = [
            {"width_cm": width_cm, "segments": segments, "target_seam_groups": ["lip"]}
        ]
        cutout_kwargs["v2_polybevel_modifier"] = {
            "width_cm": width_cm,
            "segments": segments,
            "target_seam_groups": ["lip"],
            "source_boolean_seam_group_count": 1,
        }
    cutout = ShapePrimitive(**cutout_kwargs)
    return ShapeIR(
        asset_name="bevel_demo",
        family="hard_surface_prop",
        blueprint_id="bevel_demo_v1",
        symmetry_axis=None,
        units="cm",
        primitives=[body, cutout],
        regions=[],
        primitives_used=["box"],
        part_graph=[],
        signature={},
    )


class BooleanSeamGroupBevelTests(unittest.TestCase):
    def test_baseline_boolean_subtract_has_sharp_corners(self) -> None:
        """Without the bevel modifier the boolean output must stay sharp."""
        ir = _make_panel_cut_ir(with_bevel=False)
        mesh, _parts, report = compile_explicit_surface_mesh(ir, _hero_fidelity())
        self.assertEqual(report["mode"], "exact_boolean_difference")
        self.assertEqual(report["post_boolean_polybevel_face_count"], 0)
        self.assertEqual(report["post_boolean_polybevel_bevel_face_count"], 0)
        self.assertEqual(report["post_boolean_polybevel_group_count"], 0)
        self.assertGreater(len(mesh.faces), 0)

    def test_bevel_modifier_inserts_edge_loop_strip(self) -> None:
        """With seam_group + polybevel modifier the chain must emit bevel faces."""
        ir = _make_panel_cut_ir(with_bevel=True, width_cm=1.0, segments=4)
        _mesh, _parts, report = compile_explicit_surface_mesh(ir, _hero_fidelity())
        self.assertEqual(report["mode"], "exact_boolean_difference")
        # The seam-group extraction must find at least one group with edges.
        self.assertGreaterEqual(report["post_boolean_seam_group_count"], 1)
        self.assertGreaterEqual(report["post_boolean_polybevel_group_count"], 1)
        self.assertGreaterEqual(report["post_boolean_polybevel_edge_count"], 1)
        # Bevel must add real faces, not just rewire vertex data.
        self.assertGreater(report["post_boolean_polybevel_bevel_face_count"], 0)
        self.assertEqual(
            report["post_boolean_polybevel_method"], "edge_loop_cutback_strip_v1"
        )

    def test_bevel_grows_face_and_vertex_count(self) -> None:
        """The visible 'before/after': bevel must multiply face count, not nudge it."""
        baseline_mesh, _b_parts, _b_report = compile_explicit_surface_mesh(
            _make_panel_cut_ir(with_bevel=False), _hero_fidelity()
        )
        beveled_mesh, _v_parts, _v_report = compile_explicit_surface_mesh(
            _make_panel_cut_ir(with_bevel=True, width_cm=1.0, segments=4),
            _hero_fidelity(),
        )
        # A 4-segment bevel on a panel-cut loop should add tens of faces, not
        # a couple. We pin a lower bound that's well above any rounding-noise.
        self.assertGreater(len(beveled_mesh.faces), len(baseline_mesh.faces) + 24)
        self.assertGreater(len(beveled_mesh.vertices), len(baseline_mesh.vertices) + 16)

    def test_segment_count_scales_bevel_geometry(self) -> None:
        """Higher 'segments' should not produce fewer bevel faces than lower."""
        report_low = compile_explicit_surface_mesh(
            _make_panel_cut_ir(with_bevel=True, width_cm=1.0, segments=2),
            _hero_fidelity(),
        )[2]
        report_high = compile_explicit_surface_mesh(
            _make_panel_cut_ir(with_bevel=True, width_cm=1.0, segments=6),
            _hero_fidelity(),
        )[2]
        self.assertGreaterEqual(
            report_high["post_boolean_polybevel_bevel_face_count"],
            report_low["post_boolean_polybevel_bevel_face_count"],
        )


class FeatureOpsBevelHelperTests(unittest.TestCase):
    """The author-facing helpers at lathe.feature_ops.bevel_real must
    produce primitives equivalent to the raw IR-v2 records."""

    def test_box_with_seam_group_authors_full_chain(self) -> None:
        body = ShapePrimitive(
            primitive_type="box",
            part="body",
            center=(0.0, 0.0, 0.0),
            extents=(10.0, 10.0, 10.0),
            blend_mode="union",
        )
        cutout = box_with_seam_group(
            part="body",
            center=(0.0, 0.0, 4.0),
            extents=(8.0, 8.0, 4.0),
            blend_mode="subtract",
            seam_group="lip",
            bevel_radius_cm=1.0,
            bevel_segments=4,
        )
        ir = ShapeIR(
            asset_name="bevel_demo",
            family="hard_surface_prop",
            blueprint_id="bevel_demo_v1",
            symmetry_axis=None,
            units="cm",
            primitives=[body, cutout],
            regions=[],
            primitives_used=["box"],
            part_graph=[],
            signature={},
        )
        _mesh, _parts, report = compile_explicit_surface_mesh(ir, _hero_fidelity())
        self.assertGreater(report["post_boolean_polybevel_bevel_face_count"], 0)
        self.assertEqual(
            report["post_boolean_polybevel_method"], "edge_loop_cutback_strip_v1"
        )

    def test_tag_boolean_seam_group_then_fillet_edge_chains(self) -> None:
        cutout = ShapePrimitive(
            primitive_type="box",
            part="body",
            center=(0.0, 0.0, 4.0),
            extents=(8.0, 8.0, 4.0),
            blend_mode="subtract",
        )
        tag_boolean_seam_group(cutout, seam_group="lip")
        fillet_edge(cutout, edge_class="lip", radius_cm=1.0, segments=4)
        self.assertEqual(len(cutout.boolean_seam_groups), 1)
        self.assertEqual(cutout.boolean_seam_groups[0]["name"], "lip")
        self.assertIsNotNone(cutout.v2_polybevel_modifier)
        self.assertEqual(cutout.v2_polybevel_modifier["target_seam_groups"], ["lip"])

    def test_helper_rejects_invalid_inputs(self) -> None:
        cutout = ShapePrimitive(
            primitive_type="box",
            part="body",
            center=(0.0, 0.0, 0.0),
            extents=(1.0, 1.0, 1.0),
            blend_mode="subtract",
        )
        with self.assertRaises(ValueError):
            tag_boolean_seam_group(cutout, seam_group="")
        with self.assertRaises(ValueError):
            fillet_edge(cutout, edge_class=[], radius_cm=1.0, segments=4)
        with self.assertRaises(ValueError):
            fillet_edge(cutout, edge_class="lip", radius_cm=0.0, segments=4)
        with self.assertRaises(ValueError):
            fillet_edge(cutout, edge_class="lip", radius_cm=1.0, segments=0)


if __name__ == "__main__":
    unittest.main()
