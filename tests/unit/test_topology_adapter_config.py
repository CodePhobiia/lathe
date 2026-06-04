"""Pin Phase 1 §5.6 fidelity-tier defaults for the Blender topology adapter.

The topology stage assembles a sidecar JSON config consumed by
``scripts/blender_topology_adapter.py``. Authors get visual quality for
free as long as ``intent.asset_class`` / ``validate.threshold`` imply a
hero or cinematic tier -- this test pins that default cascade so a
future refactor cannot silently regress to the legacy weld+triangulate
behavior on demos that don't author a ``build.topology.subsurf_level``.
"""
from __future__ import annotations

import unittest

import trimesh
from lathe.core.mesh import RuntimeMesh
from lathe.core.stages.topology import (
    _asset_class_budget_target_quads,
    _build_topology_adapter_config,
    _infer_fidelity_tier_from_asset,
    _shape_bundle_has_terrain_heightfield,
)


def _runtime_mesh() -> RuntimeMesh:
    box = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    return RuntimeMesh(mesh=box, face_parts=["body"] * len(box.faces), part_colors={}, units="cm")


class FidelityTierInferenceTests(unittest.TestCase):
    def test_hero_asset_class(self) -> None:
        asset = {"intent": {"asset_class": "hero"}}
        self.assertEqual(_infer_fidelity_tier_from_asset(asset), "hero")

    def test_aaa_hero_promotes_to_cinematic(self) -> None:
        asset = {"intent": {"asset_class": "aaa_hero"}}
        self.assertEqual(_infer_fidelity_tier_from_asset(asset), "cinematic")

    def test_mobile_collapses_to_blockout(self) -> None:
        asset = {"intent": {"asset_class": "mobile"}}
        self.assertEqual(_infer_fidelity_tier_from_asset(asset), "blockout")

    def test_validate_threshold_picks_cinematic(self) -> None:
        asset = {"intent": {}, "validate": {"threshold": 0.95}}
        self.assertEqual(_infer_fidelity_tier_from_asset(asset), "cinematic")

    def test_default_falls_back_to_game(self) -> None:
        self.assertEqual(_infer_fidelity_tier_from_asset({}), "game")


class AssetClassBudgetTests(unittest.TestCase):
    def test_hero_quads_target(self) -> None:
        asset = {"intent": {"asset_class": "hero"}}
        # hero builtin profile has poly_budget.quads_target = 20000
        self.assertEqual(_asset_class_budget_target_quads(asset), 20000)

    def test_aaa_hero_quads_target(self) -> None:
        asset = {"intent": {"asset_class": "aaa_hero"}}
        self.assertEqual(_asset_class_budget_target_quads(asset), 30000)

    def test_unknown_asset_class_returns_zero(self) -> None:
        asset = {"intent": {"asset_class": "totally_made_up"}}
        self.assertEqual(_asset_class_budget_target_quads(asset), 0)

    def test_generic_returns_zero(self) -> None:
        asset = {"intent": {"asset_class": "generic"}}
        self.assertEqual(_asset_class_budget_target_quads(asset), 0)


class TerrainHeightfieldDetectionTests(unittest.TestCase):
    def test_heightfield_primitive_detected(self) -> None:
        bundle = {
            "shape_ir": [
                {
                    "primitives": [
                        {"primitive_type": "heightfield"},
                    ]
                }
            ]
        }
        self.assertTrue(_shape_bundle_has_terrain_heightfield(bundle))

    def test_box_primitive_not_heightfield(self) -> None:
        bundle = {"shape_ir": [{"primitives": [{"primitive_type": "box"}]}]}
        self.assertFalse(_shape_bundle_has_terrain_heightfield(bundle))

    def test_empty_bundle_safe(self) -> None:
        self.assertFalse(_shape_bundle_has_terrain_heightfield({}))


class BuildAdapterConfigTests(unittest.TestCase):
    def test_hero_tier_drives_subsurf_and_bevel_segments(self) -> None:
        asset = {"intent": {"asset_class": "hero"}, "build": {}}
        cfg = _build_topology_adapter_config(_runtime_mesh(), {}, asset, None)
        self.assertEqual(cfg.get("subsurf_level"), 1)
        self.assertEqual(cfg.get("bevel_segments"), 2)
        self.assertEqual(cfg.get("fidelity_tier"), "hero")
        # Asset-class budget cascades into decimate target.
        self.assertEqual(cfg.get("decimate_target_quads"), 20000)

    def test_cinematic_tier_drives_subsurf_2(self) -> None:
        asset = {"intent": {"asset_class": "aaa_hero"}, "build": {}}
        cfg = _build_topology_adapter_config(_runtime_mesh(), {}, asset, None)
        self.assertEqual(cfg.get("subsurf_level"), 2)
        self.assertEqual(cfg.get("bevel_segments"), 3)
        self.assertEqual(cfg.get("fidelity_tier"), "cinematic")

    def test_blockout_tier_disables_subsurf(self) -> None:
        asset = {"intent": {"asset_class": "mobile"}, "build": {}}
        cfg = _build_topology_adapter_config(_runtime_mesh(), {}, asset, None)
        self.assertNotIn("subsurf_level", cfg)
        self.assertEqual(cfg.get("fidelity_tier"), "blockout")

    def test_explicit_target_quads_wins_over_asset_class_budget(self) -> None:
        asset = {
            "intent": {"asset_class": "hero"},
            "build": {"topology": {"target_quads": 5000}},
        }
        cfg = _build_topology_adapter_config(_runtime_mesh(), {}, asset, None)
        self.assertEqual(cfg.get("decimate_target_quads"), 5000)

    def test_explicit_subsurf_level_zero_overrides_tier(self) -> None:
        asset = {
            "intent": {"asset_class": "hero"},
            "build": {"topology": {"subsurf_level": 0}},
        }
        cfg = _build_topology_adapter_config(_runtime_mesh(), {}, asset, None)
        self.assertNotIn("subsurf_level", cfg)

    def test_runtime_config_overrides_asset(self) -> None:
        asset = {"intent": {"asset_class": "hero"}}
        runtime_config = {"topology": {"subsurf_level": 3, "bevel_segments": 5}}
        cfg = _build_topology_adapter_config(_runtime_mesh(), {}, asset, runtime_config)
        self.assertEqual(cfg.get("subsurf_level"), 3)
        self.assertEqual(cfg.get("bevel_segments"), 5)

    def test_terrain_heightfield_sets_skip_flag(self) -> None:
        asset = {"intent": {"asset_class": "hero"}, "build": {}}
        bundle = {"shape_ir": [{"primitives": [{"primitive_type": "heightfield"}]}]}
        cfg = _build_topology_adapter_config(_runtime_mesh(), bundle, asset, None)
        self.assertTrue(cfg.get("skip_subsurf_for_terrain"))

    def test_lod0_target_face_count_takes_precedence(self) -> None:
        asset = {
            "intent": {"asset_class": "hero"},
            "build": {"optimize": {"lods": {"lod_0": {"target_face_count": 12000}}}},
        }
        cfg = _build_topology_adapter_config(_runtime_mesh(), {}, asset, None)
        # 12000 tris => 6000 quads; smaller than hero's 20000 default.
        self.assertEqual(cfg.get("decimate_target_quads"), 6000)


if __name__ == "__main__":
    unittest.main()
