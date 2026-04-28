from __future__ import annotations

import unittest
from pathlib import Path

from lathe.normalizer import normalize_program
from lathe.parser import parse_file
from lathe.planner import build_plan
from lathe.resolver import materialize_asset

ROOT = Path(__file__).resolve().parents[1]
ADAPT_EXAMPLE = ROOT / "examples" / "console_terminal_mobile_adapt.lth"
ASSEMBLE_EXAMPLE = ROOT / "examples" / "service_corridor_wall.lth"
RECONSTRUCT_EXAMPLE = ROOT / "examples" / "reconstruct_courier_from_views.lth"


class LatheV11LanguageTests(unittest.TestCase):
    def test_new_v11_declarations_parse(self) -> None:
        adapt_program = parse_file(ADAPT_EXAMPLE)
        self.assertTrue(
            any(item["name"] == "mobile_console_policy" for item in adapt_program["adapt_policies"])
        )
        self.assertTrue(
            any(item["name"] == "preserve_console_surface" for item in adapt_program["transfer_rules"])
        )

        assemble_program = parse_file(ASSEMBLE_EXAMPLE)
        self.assertTrue(
            any(item["name"] == "industrial_hardsurface_library" for item in assemble_program["libraries"])
        )
        self.assertTrue(any(item["name"] == "industrial_wall_kit" for item in assemble_program["kits"]))
        self.assertTrue(
            any(item["name"] == "industrial_wall_policy" for item in assemble_program["assembly_policies"])
        )

        reconstruct_program = parse_file(RECONSTRUCT_EXAMPLE)
        self.assertTrue(
            any(item["name"] == "courier_views" for item in reconstruct_program["reference_sets"])
        )
        self.assertTrue(
            any(
                item["name"] == "courier_reconstruct_policy"
                for item in reconstruct_program["reconstruct_policies"]
            )
        )
        self.assertTrue(
            any(item["name"] == "courier_fit_default" for item in reconstruct_program["fit_profiles"])
        )

    def test_materialize_asset_resolves_kit_and_reference_sets(self) -> None:
        assembled = materialize_asset(parse_file(ASSEMBLE_EXAMPLE), "service_corridor_wall")
        self.assertEqual(assembled["from"], "industrial_wall_kit")
        self.assertEqual(assembled["assembly"]["kit"], "industrial_wall_kit")
        self.assertTrue(assembled["assembly"]["resolved_kit"])
        self.assertEqual(assembled["assembly"]["family"], "sci_fi_wall_panel_family")
        self.assertTrue(assembled["constraints"]["resolved_assembly_policy"])

        reconstructed = materialize_asset(parse_file(RECONSTRUCT_EXAMPLE), "reconstruct_courier_from_views")
        self.assertEqual(reconstructed["refs"]["reference_sets"], ["courier_views"])
        self.assertTrue(reconstructed["refs"]["resolved_reference_sets"])
        self.assertTrue(reconstructed["fit"]["resolved_fit_profile"])
        self.assertTrue(reconstructed["fit"]["resolved_reconstruct_policy"])

    def test_normalized_program_contains_v11_namespaces(self) -> None:
        normalized = normalize_program(parse_file(ASSEMBLE_EXAMPLE))
        for key in (
            "libraries",
            "kits",
            "reference_sets",
            "reconstruct_policies",
            "adapt_policies",
            "assembly_policies",
            "fit_profiles",
            "transfer_rules",
        ):
            self.assertIn(key, normalized)

    def test_plan_exposes_v11_flow_summary(self) -> None:
        adapt_plan = build_plan(parse_file(ADAPT_EXAMPLE), "console_terminal_mobile")
        self.assertEqual(adapt_plan["v1_1_flow"]["mode"], "adapt")
        self.assertEqual(adapt_plan["v1_1_flow"]["resolved_adapt_policy"], "mobile_console_policy")
        self.assertEqual(adapt_plan["v1_1_flow"]["resolved_transfer_rules"], ["preserve_console_surface"])

        assemble_plan = build_plan(parse_file(ASSEMBLE_EXAMPLE), "service_corridor_wall")
        self.assertEqual(assemble_plan["v1_1_flow"]["mode"], "assemble")
        self.assertEqual(assemble_plan["v1_1_flow"]["resolved_kit"], "industrial_wall_kit")
        self.assertEqual(assemble_plan["v1_1_flow"]["resolved_assembly_policy"], "industrial_wall_policy")


if __name__ == "__main__":
    unittest.main()
