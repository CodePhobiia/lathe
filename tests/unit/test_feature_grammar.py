"""Unit tests for ``lathe.feature_grammar.compile_feature_enhancements``.

``compile_feature_enhancements`` walks a ``ShapeIR``'s regions, dispatches
to feature-operator functions in ``lathe.feature_ops`` based on component
type, and returns an enriched ``ShapeIR`` plus a feature report that
includes the fidelity/params snapshots and the set of feature operators
exercised. The tests drive it end-to-end via a real :class:`AssetGraph`
+ compiled blueprint so we exercise the component dispatcher without
depending on hand-rolled IR mocks.
"""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace

import numpy as np
from lathe.assembly_kernel import compile_assembly_blueprint
from lathe.asset_graph import build_asset_graph
from lathe.blueprints import resolve_blueprint
from lathe.candidate_search import CandidateParams, generate_candidate_params
from lathe.feature_grammar import compile_feature_enhancements
from lathe.fidelity import infer_fidelity_profile
from lathe.shape_ir import ShapeIR


def _courier_graph():
    return build_asset_graph(
        {
            "name": "courier_drone",
            "kind": "mechanical_assembly",
            "intent": {
                "role": "drone",
                "parts": ["body", "rotor_fl", "rotor_fr", "rotor_rl", "rotor_rr"],
            },
            "build": {
                "shape": {"symmetry": "x", "mode": "generate"},
                "rig": {},
                "interfaces": {},
            },
            "validate": {"threshold": 0.80},
        }
    )


def _crate_graph():
    return build_asset_graph(
        {
            "name": "industrial_crate",
            "kind": "prop",
            "intent": {"role": "crate", "parts": ["body", "lid"]},
            "build": {
                "shape": {"symmetry": "auto", "mode": "generate"},
                "rig": {},
                "interfaces": {},
            },
            "validate": {"threshold": 0.80},
        }
    )


def _compile_shape_ir(graph) -> ShapeIR:
    rng = np.random.default_rng(0)
    blueprint = resolve_blueprint(graph, {}, rng, 0)
    return compile_assembly_blueprint(graph, blueprint)


def _params(graph, fidelity) -> CandidateParams:
    return generate_candidate_params(graph, seed=42, candidate_index=0, fidelity=fidelity)


class CompileFeatureEnhancementsTests(unittest.TestCase):
    def test_single_family_produces_enriched_shape_ir_and_report(self) -> None:
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        shape_ir = _compile_shape_ir(graph)
        original_primitive_count = len(shape_ir.primitives)

        enriched, report = compile_feature_enhancements(
            graph, shape_ir, fidelity=fidelity, params=_params(graph, fidelity)
        )

        self.assertIsInstance(enriched, ShapeIR)
        self.assertGreater(len(enriched.primitives), original_primitive_count)
        self.assertIn("fidelity", report)
        self.assertIn("candidate_params", report)
        self.assertIn("feature_ops_used", report)
        self.assertIn("feature_count_added", report)
        self.assertEqual(
            report["feature_count_added"],
            len(enriched.primitives) - original_primitive_count,
        )
        # feature_ops_used is a sorted list
        self.assertEqual(list(report["feature_ops_used"]), sorted(report["feature_ops_used"]))

    def test_compound_family_feature_ops_cover_multiple_components(self) -> None:
        # courier_drone exercises rotor_arm + rotor_pod + body → compound
        # feature grammar output: feature_ops_used must cover >= 2 ops.
        graph = _courier_graph()
        fidelity = infer_fidelity_profile(graph)
        shape_ir = _compile_shape_ir(graph)
        _, report = compile_feature_enhancements(
            graph, shape_ir, fidelity=fidelity, params=_params(graph, fidelity)
        )
        self.assertGreaterEqual(len(report["feature_ops_used"]), 2)
        # drone-specific: rotor_arm ops always run ribs + edge_break
        self.assertTrue(
            any("edge" in name or "rib" in name or "shroud" in name for name in report["feature_ops_used"])
        )

    def test_empty_regions_yield_zero_features(self) -> None:
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        shape_ir = _compile_shape_ir(graph)
        # strip regions so the grammar has nothing to attach features to
        empty_ir = copy.deepcopy(shape_ir)
        empty_ir.regions = []
        enriched, report = compile_feature_enhancements(
            graph, empty_ir, fidelity=fidelity, params=_params(graph, fidelity)
        )
        self.assertEqual(report["feature_count_added"], 0)
        self.assertEqual(report["feature_ops_used"], [])
        # enriched primitive list is unchanged
        self.assertEqual(len(enriched.primitives), len(empty_ir.primitives))

    def test_unknown_component_region_is_silently_skipped(self) -> None:
        # _component_from_region only returns BlueprintComponent for
        # regions whose .name matches; renaming the region to something
        # that has no corresponding blueprint component means the grammar
        # skips it rather than crashing.
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        shape_ir = _compile_shape_ir(graph)
        shape_ir.regions[0].name = "__no_such_region__"
        # still at least one real region remains; compile must succeed
        enriched, report = compile_feature_enhancements(
            graph, shape_ir, fidelity=fidelity, params=_params(graph, fidelity)
        )
        self.assertGreaterEqual(report["feature_count_added"], 0)
        self.assertIsInstance(enriched, ShapeIR)

    def test_malformed_shape_ir_missing_regions_attribute_raises(self) -> None:
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        with self.assertRaises(AttributeError):
            compile_feature_enhancements(
                graph,
                object(),
                fidelity=fidelity,
                params=_params(graph, fidelity),  # type: ignore[arg-type]
            )

    def test_fidelity_tier_affects_feature_count(self) -> None:
        # hero fidelity requests more features than blockout. Re-running
        # the grammar with each tier should produce a monotonic
        # relationship on at least one family.
        graph = _crate_graph()
        base_fidelity = infer_fidelity_profile(graph)
        params = _params(graph, base_fidelity)
        shape_ir = _compile_shape_ir(graph)

        blockout = replace(base_fidelity, tier="blockout")
        hero = replace(base_fidelity, tier="hero", trim_complexity=5)
        _, report_block = compile_feature_enhancements(graph, shape_ir, fidelity=blockout, params=params)
        _, report_hero = compile_feature_enhancements(graph, shape_ir, fidelity=hero, params=params)
        # hero tier's `feature_count = 6` branch includes additional
        # fastener strips on shells; blockout's `feature_count = 2`
        # branch skips them. Hero must be >= blockout.
        self.assertGreaterEqual(report_hero["feature_count_added"], report_block["feature_count_added"])


if __name__ == "__main__":
    unittest.main()
