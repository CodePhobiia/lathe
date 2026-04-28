from __future__ import annotations

import unittest
from pathlib import Path

from lathe.bench_runtime import run_lathe_benchmarks
from lathe.normalizer import normalize_program
from lathe.parser import parse_file
from lathe.patch_api import freeze_dimension, update_material_palette
from lathe.resolver import materialize_asset
from lathe.test_runtime import run_lathe_tests

ROOT = Path(__file__).resolve().parents[1]
CHEST_EXAMPLE = ROOT / "examples" / "brassbound_chest.lth"
DRONE_EXAMPLE = ROOT / "examples" / "courier_drone.lth"


class LatheV08LanguageTests(unittest.TestCase):
    def test_imports_expose_v08_declaration_namespaces(self) -> None:
        program = parse_file(CHEST_EXAMPLE)
        self.assertTrue(any(item["name"] == "brassbound_chest_family" for item in program["families"]))
        self.assertTrue(any(item["name"] == "oak_body" for item in program["materials"]))
        self.assertTrue(any(item["name"] == "fantasy_brassbound" for item in program["palettes"]))
        self.assertTrue(any(item["name"] == "hero_hardsurface_repair" for item in program["repair_policies"]))
        self.assertTrue(any(item["name"] == "chest_hero_search" for item in program["spaces"]))
        self.assertTrue(
            any(item["name"] == "legacy_brassbound_chest_v06_fixture" for item in program["fixtures"])
        )

    def test_materialize_asset_lowers_source_family_surface_space_and_repair(self) -> None:
        program = parse_file(DRONE_EXAMPLE)
        asset = materialize_asset(program, "courier_drone")
        self.assertEqual(asset["assembly"]["family"], "courier_drone_family")
        self.assertEqual(asset["assembly"]["resolved_family"]["name"], "courier_drone_family")
        self.assertTrue(asset["assembly"]["resolved_components"])
        self.assertEqual(asset["surface"]["palette"], "courier_premium")
        self.assertTrue(asset["surface"]["resolved_palette"])
        self.assertTrue(asset["surface"]["resolved_materials"])
        self.assertEqual(asset["space"]["use"], "drone_hero_search")
        self.assertGreaterEqual(asset["space"]["select"]["best_of"], 12)
        self.assertEqual(asset["repair_policy"]["use"], "hero_hardsurface_repair")
        self.assertIn("generate_lods", asset["validate"]["repair"]["allow"])

    def test_lathe_test_executes_source_defined_tests(self) -> None:
        result = run_lathe_tests([str(CHEST_EXAMPLE)])
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["total"], 1)

    def test_lathe_bench_executes_source_defined_benchmarks(self) -> None:
        result = run_lathe_benchmarks([str(CHEST_EXAMPLE)])
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["total"], 1)

    def test_patch_api_updates_palette_and_search_space(self) -> None:
        program = parse_file(CHEST_EXAMPLE)
        updated = update_material_palette(program, "brassbound_chest", "fantasy_brassbound")
        frozen = freeze_dimension(updated, "chest_hero_search", "feature_density")
        normalized = normalize_program(frozen)
        asset = next(item for item in normalized["assets"] if item["name"] == "brassbound_chest")
        space = next(item for item in normalized["spaces"] if item["name"] == "chest_hero_search")
        self.assertEqual(asset["surface"]["palette"], "fantasy_brassbound")
        self.assertIn("feature_density", space["freeze"])


if __name__ == "__main__":
    unittest.main()
