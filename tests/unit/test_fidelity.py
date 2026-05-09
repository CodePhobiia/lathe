"""Unit tests for ``lathe.fidelity.infer_fidelity_profile``.

Exercises the tier ladder (hero > game > blockout), explicit override
via critic naming, threshold-based fallback, and ``FidelityProfile``
serialization. The function is a pure mapping over an
:class:`AssetGraph`, so we synthesise minimal asset dicts and reuse the
real ``build_asset_graph`` to keep the contract honest.
"""

from __future__ import annotations

import unittest

from lathe.asset_graph import AssetGraph, PartNode, build_asset_graph
from lathe.fidelity import FidelityProfile, _tier_multipliers, infer_fidelity_profile


def _asset(*, threshold: float = 0.80, critic: str | None = None, parts: list[str] | None = None) -> dict:
    return {
        "name": "demo",
        "kind": "hard_surface_prop",
        "intent": {"role": "", "parts": list(parts or ["body"])},
        "build": {"shape": {"symmetry": "auto"}, "rig": {}, "interfaces": {}},
        "validate": {"threshold": threshold, **({"score": critic} if critic else {})},
    }


def _graph(**overrides) -> AssetGraph:
    base = AssetGraph(
        name="demo",
        kind="hard_surface_prop",
        family="hard_surface_prop_generic",
        blueprint_id="lathe.blueprint.hard_surface_prop_generic_v1",
        role="",
        scale_cm=100.0,
        symmetry_axis=None,
        validation_threshold=0.80,
        critic_name=None,
        parts=[PartNode(name="body")],
        joints=[],
        sockets=[],
        anchors=[],
        connections=[],
        connection_layout={},
        materials=[],
        styles=[],
        interactions=[],
        part_graph=[],
        semantic_requirements={},
        authoring={},
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class InferFidelityProfileTests(unittest.TestCase):
    def test_hero_critic_selects_hero_tier(self) -> None:
        profile = infer_fidelity_profile(_graph(critic_name="hero_chest_critic"))
        self.assertEqual(profile.tier, "hero")
        self.assertEqual(profile.repair_budget, 4)
        self.assertGreater(profile.detail_density, 1.0)

    def test_high_threshold_promotes_to_hero(self) -> None:
        profile = infer_fidelity_profile(_graph(validation_threshold=0.90))
        self.assertEqual(profile.tier, "hero")

    def test_cinematic_critic_selects_cinematic_tier(self) -> None:
        profile = infer_fidelity_profile(_graph(critic_name="cinematic_hero_prop"))
        self.assertEqual(profile.tier, "cinematic")
        self.assertEqual(profile.detail_density, 2.20)
        self.assertEqual(profile.edge_weight, 1.65)
        self.assertEqual(profile.panel_depth, 1.80)
        self.assertEqual(profile.trim_complexity, 8)
        self.assertEqual(profile.support_complexity, 1.45)
        self.assertEqual(profile.silhouette_refinement, 1.40)
        self.assertEqual(profile.repair_budget, 6)

    def test_cinematic_threshold_promotes_to_cinematic(self) -> None:
        profile = infer_fidelity_profile(_graph(validation_threshold=0.93))
        self.assertEqual(profile.tier, "cinematic")
        self.assertEqual(profile.detail_density, 2.20)

    def test_threshold_at_cinematic_boundary(self) -> None:
        boundary = infer_fidelity_profile(_graph(validation_threshold=0.92))
        self.assertEqual(boundary.tier, "cinematic")
        below = infer_fidelity_profile(_graph(validation_threshold=0.919))
        self.assertEqual(below.tier, "hero")

    def test_cinematic_critic_overrides_low_threshold(self) -> None:
        profile = infer_fidelity_profile(
            _graph(critic_name="cinematic_close_up", validation_threshold=0.80)
        )
        self.assertEqual(profile.tier, "cinematic")

    def test_default_threshold_returns_game_tier(self) -> None:
        profile = infer_fidelity_profile(_graph(validation_threshold=0.80))
        self.assertEqual(profile.tier, "game")
        self.assertEqual(profile.detail_density, 1.0)
        self.assertEqual(profile.repair_budget, 3)

    def test_low_threshold_drops_to_blockout(self) -> None:
        profile = infer_fidelity_profile(_graph(validation_threshold=0.70))
        self.assertEqual(profile.tier, "blockout")
        self.assertLess(profile.detail_density, 1.0)
        self.assertEqual(profile.repair_budget, 1)

    def test_tier_ladder_is_strictly_ordered(self) -> None:
        cinematic = infer_fidelity_profile(_graph(validation_threshold=0.95))
        hero = infer_fidelity_profile(_graph(critic_name="hero_x", validation_threshold=0.88))
        game = infer_fidelity_profile(_graph(validation_threshold=0.80))
        blockout = infer_fidelity_profile(_graph(validation_threshold=0.70))
        self.assertGreater(cinematic.detail_density, hero.detail_density)
        self.assertGreater(hero.detail_density, game.detail_density)
        self.assertGreater(game.detail_density, blockout.detail_density)
        self.assertGreaterEqual(cinematic.repair_budget, hero.repair_budget)
        self.assertGreaterEqual(hero.repair_budget, game.repair_budget)
        self.assertGreaterEqual(game.repair_budget, blockout.repair_budget)

    def test_tier_multipliers_helper_exposes_all_tiers(self) -> None:
        for tier in ("blockout", "game", "hero", "cinematic"):
            mult = _tier_multipliers(tier)
            self.assertIn("detail_density", mult)
            self.assertIn("edge_weight", mult)
            self.assertIn("panel_depth", mult)
            self.assertIn("trim_complexity", mult)
            self.assertIn("support_complexity", mult)
            self.assertIn("silhouette_refinement", mult)
            self.assertIn("repair_budget", mult)

    def test_tier_multipliers_helper_returns_independent_copies(self) -> None:
        mult = _tier_multipliers("cinematic")
        mult["detail_density"] = 999.0
        again = _tier_multipliers("cinematic")
        self.assertEqual(again["detail_density"], 2.20)

    def test_tier_multipliers_helper_rejects_unknown_tier(self) -> None:
        with self.assertRaises(KeyError):
            _tier_multipliers("ultra")

    def test_missing_critic_and_default_threshold_returns_game(self) -> None:
        # critic_name=None, validation_threshold=None style: build_asset_graph
        # would normally fill these, so we drive the function directly with a
        # minimal real graph from a sparse asset dict.
        graph = build_asset_graph(_asset(threshold=0.80))
        profile = infer_fidelity_profile(graph)
        self.assertEqual(profile.tier, "game")

    def test_real_builder_cinematic_threshold_dispatches_cinematic(self) -> None:
        # End-to-end: an authored asset with threshold=0.93 should resolve to
        # the cinematic tier through the real ``build_asset_graph`` flow.
        graph = build_asset_graph(_asset(threshold=0.93))
        profile = infer_fidelity_profile(graph)
        self.assertEqual(profile.tier, "cinematic")
        self.assertEqual(profile.detail_density, 2.20)
        self.assertEqual(profile.repair_budget, 6)

    def test_real_builder_cinematic_critic_dispatches_cinematic(self) -> None:
        graph = build_asset_graph(_asset(critic="cinematic_hero_prop"))
        profile = infer_fidelity_profile(graph)
        self.assertEqual(profile.tier, "cinematic")

    def test_to_dict_round_trip_preserves_fields(self) -> None:
        profile = infer_fidelity_profile(_graph(critic_name="hero_x"))
        payload = profile.to_dict()
        self.assertEqual(payload["tier"], "hero")
        self.assertEqual(set(payload), set(FidelityProfile.__dataclass_fields__))
        self.assertIsInstance(payload["repair_budget"], int)
        self.assertIsInstance(payload["detail_density"], float)


if __name__ == "__main__":
    unittest.main()
