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
from lathe.fidelity import FidelityProfile, infer_fidelity_profile


def _asset(*, threshold: float = 0.80, critic: str | None = None, parts: list[str] | None = None) -> dict:
    return {
        "name": "demo",
        "kind": "hard_surface_prop",
        "intent": {"role": "", "parts": list(parts or ["body"])},
        "build": {"shape": {"symmetry": "auto"}, "rig": {}, "interfaces": {}},
        "validate": {"threshold": threshold, **({"critic": critic} if critic else {})},
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
        hero = infer_fidelity_profile(_graph(validation_threshold=0.95))
        game = infer_fidelity_profile(_graph(validation_threshold=0.80))
        blockout = infer_fidelity_profile(_graph(validation_threshold=0.70))
        self.assertGreater(hero.detail_density, game.detail_density)
        self.assertGreater(game.detail_density, blockout.detail_density)
        self.assertGreaterEqual(hero.repair_budget, game.repair_budget)
        self.assertGreaterEqual(game.repair_budget, blockout.repair_budget)

    def test_missing_critic_and_default_threshold_returns_game(self) -> None:
        # critic_name=None, validation_threshold=None style: build_asset_graph
        # would normally fill these, so we drive the function directly with a
        # minimal real graph from a sparse asset dict.
        graph = build_asset_graph(_asset(threshold=0.80))
        profile = infer_fidelity_profile(graph)
        self.assertEqual(profile.tier, "game")

    def test_to_dict_round_trip_preserves_fields(self) -> None:
        profile = infer_fidelity_profile(_graph(critic_name="hero_x"))
        payload = profile.to_dict()
        self.assertEqual(payload["tier"], "hero")
        self.assertEqual(set(payload), set(FidelityProfile.__dataclass_fields__))
        self.assertIsInstance(payload["repair_budget"], int)
        self.assertIsInstance(payload["detail_density"], float)


if __name__ == "__main__":
    unittest.main()
