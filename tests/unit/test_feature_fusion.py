"""Unit tests for ``lathe.feature_fusion``.

``feature_fusion`` exposes three deterministic helpers used by the mesh
finalizer: ``integration_config_for_family`` (family-specific fusion
tuning), ``primitive_rounding`` (per-primitive corner-round radii), and
``primitive_blend_mode``. None of them have any I/O — they're pure
projections of the inputs. These tests pin the per-family pitch/blur
contract, the hero-family exact-mesh flag, the rounding fallback ladder,
and idempotence (determinism) across repeated calls.
"""

from __future__ import annotations

import unittest

from lathe.feature_fusion import (
    integration_config_for_family,
    primitive_blend_mode,
    primitive_rounding,
)
from lathe.fidelity import FidelityProfile
from lathe.shape_ir import ShapePrimitive


def _fidelity(tier: str) -> FidelityProfile:
    table = {
        "hero": (1.35, 1.25, 1.30, 5, 1.20, 1.18, 4),
        "game": (1.0, 1.0, 1.0, 3, 1.0, 1.0, 3),
        "blockout": (0.70, 0.75, 0.72, 1, 0.80, 0.86, 1),
    }
    dd, ew, pd, tc, sc, sr, rb = table[tier]
    return FidelityProfile(
        tier=tier,
        detail_density=dd,
        edge_weight=ew,
        panel_depth=pd,
        trim_complexity=tc,
        support_complexity=sc,
        silhouette_refinement=sr,
        repair_budget=rb,
    )


def _box(*, component: str | None = None, rounding: float = 0.0, blend_mode: str | None = None) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="box",
        part="body",
        center=(0.0, 0.0, 0.0),
        extents=(1.0, 1.0, 1.0),
        component=component,
        rounding=rounding,
        **({"blend_mode": blend_mode} if blend_mode is not None else {}),
    )


class IntegrationConfigTests(unittest.TestCase):
    def test_hero_family_enables_exact_finalize(self) -> None:
        cfg = integration_config_for_family("brassbound_chest", _fidelity("hero"))
        self.assertTrue(cfg["enabled"])
        self.assertTrue(cfg["hero_family"])
        self.assertTrue(cfg["exact_finalize"])
        self.assertEqual(cfg["exact_mode"], "explicit_mesh")

    def test_non_hero_family_falls_back_to_sdf_fusion(self) -> None:
        cfg = integration_config_for_family("hard_surface_prop_generic", _fidelity("game"))
        self.assertFalse(cfg["enabled"])
        self.assertFalse(cfg["hero_family"])
        self.assertFalse(cfg["exact_finalize"])
        self.assertEqual(cfg["exact_mode"], "sdf_voxel_fusion")

    def test_console_family_uses_component_assembly_exact_mode(self) -> None:
        cfg = integration_config_for_family("console_terminal", _fidelity("game"))
        self.assertTrue(cfg["hero_family"])
        self.assertEqual(cfg["exact_mode"], "component_assembly")
        # control_pedestal + service_cabinet share that branch.
        for family in ("control_pedestal", "service_cabinet"):
            self.assertEqual(
                integration_config_for_family(family, _fidelity("game"))["exact_mode"],
                "component_assembly",
            )

    def test_pitch_and_blur_scale_with_fidelity_tier(self) -> None:
        # hero tier => finest pitch (smallest spacing) + largest blur sigma;
        # blockout tier => coarsest pitch + smallest blur. The function
        # maps fidelity → fusion resolution, so finer detail needs
        # smaller pitch.
        fam = "industrial_crate"
        hero = integration_config_for_family(fam, _fidelity("hero"))
        game = integration_config_for_family(fam, _fidelity("game"))
        block = integration_config_for_family(fam, _fidelity("blockout"))
        self.assertLess(hero["pitch"], game["pitch"])
        self.assertLess(game["pitch"], block["pitch"])
        self.assertGreater(hero["blur_sigma"], game["blur_sigma"])
        self.assertGreater(game["blur_sigma"], block["blur_sigma"])

    def test_courier_drone_applies_pitch_multiplier(self) -> None:
        # courier_drone is not in the hero family set but has a 5% pitch
        # boost applied after the tier ladder.
        fidelity = _fidelity("game")
        drone = integration_config_for_family("courier_drone", fidelity)
        crate = integration_config_for_family("industrial_crate", fidelity)
        self.assertAlmostEqual(drone["pitch"], round(2.35 * 1.05, 4))
        # courier_drone is not a hero family — no exact_finalize
        self.assertFalse(drone["hero_family"])
        self.assertGreater(drone["pitch"], crate["pitch"])

    def test_integration_config_is_deterministic(self) -> None:
        fidelity = _fidelity("hero")
        first = integration_config_for_family("brassbound_chest", fidelity)
        second = integration_config_for_family("brassbound_chest", fidelity)
        self.assertEqual(first, second)


class PrimitiveRoundingTests(unittest.TestCase):
    def test_explicit_rounding_takes_precedence(self) -> None:
        prim = _box(component="shell", rounding=2.5)
        # hero tier would normally return 0.7 for shells, but explicit wins
        self.assertEqual(primitive_rounding(prim, _fidelity("hero")), 2.5)

    def test_shell_component_rounding_ladder(self) -> None:
        prim = _box(component="shell", rounding=0.0)
        self.assertAlmostEqual(primitive_rounding(prim, _fidelity("hero")), 0.7)
        self.assertAlmostEqual(primitive_rounding(prim, _fidelity("game")), 0.45)

    def test_mechanism_component_rounding_ladder(self) -> None:
        prim = _box(component="rotor_pod", rounding=0.0)
        self.assertAlmostEqual(primitive_rounding(prim, _fidelity("hero")), 0.4)
        self.assertAlmostEqual(primitive_rounding(prim, _fidelity("game")), 0.25)

    def test_unknown_component_rounds_to_zero(self) -> None:
        prim = _box(component="__unknown__", rounding=0.0)
        self.assertEqual(primitive_rounding(prim, _fidelity("hero")), 0.0)

    def test_rounding_none_coerces_to_zero_fallback(self) -> None:
        # Some code paths may set rounding=None; the helper should treat
        # that as "unset" and fall into the component ladder.
        prim = _box(component="shell", rounding=0.0)
        prim.rounding = None  # type: ignore[assignment]
        self.assertAlmostEqual(primitive_rounding(prim, _fidelity("game")), 0.45)

    def test_primitive_rounding_is_idempotent(self) -> None:
        prim = _box(component="body", rounding=0.0)
        fidelity = _fidelity("game")
        self.assertEqual(primitive_rounding(prim, fidelity), primitive_rounding(prim, fidelity))


class PrimitiveBlendModeTests(unittest.TestCase):
    def test_default_blend_mode_is_union(self) -> None:
        prim = _box()
        self.assertEqual(primitive_blend_mode(prim), "union")

    def test_explicit_blend_mode_preserved(self) -> None:
        prim = _box(blend_mode="subtract")
        self.assertEqual(primitive_blend_mode(prim), "subtract")

    def test_empty_string_blend_mode_falls_back_to_union(self) -> None:
        prim = _box()
        prim.blend_mode = ""  # falsy => union
        self.assertEqual(primitive_blend_mode(prim), "union")


if __name__ == "__main__":
    unittest.main()
