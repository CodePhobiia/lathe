from __future__ import annotations

import unittest
from pathlib import Path

from lathe.checker import check_program
from lathe.parser import parse_file
from lathe.resolver import materialize_asset

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "courier_drone.lth"
CHEST_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "brassbound_chest.lth"
WALL_PANEL_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sci_fi_wall_panel.lth"
CRATE_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "industrial_crate.lth"
DOOR_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "mechanical_door.lth"
CONSOLE_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "console_terminal.lth"


class LatheScaffoldTests(unittest.TestCase):
    def test_example_parses(self) -> None:
        program = parse_file(EXAMPLE)
        self.assertEqual(program["module"], "studio.props.drones")
        self.assertEqual(len(program["assets"]), 1)
        self.assertEqual(len(program["variants"]), 1)

    def test_example_checks_clean(self) -> None:
        program = parse_file(EXAMPLE)
        diagnostics = check_program(program)
        self.assertEqual(diagnostics, [])

    def test_variant_materialization(self) -> None:
        program = parse_file(EXAMPLE)
        asset = materialize_asset(program, "courier_drone_mobile")
        self.assertEqual(asset["name"], "courier_drone_mobile")
        self.assertEqual(asset["build"]["optimize"]["draw_calls"], 2)
        self.assertEqual(asset["build"]["surface"]["resolution"]["value"], 2048)
        self.assertIn("mobile_runtime", asset["uses"])

    def test_chest_example_checks_clean(self) -> None:
        program = parse_file(CHEST_EXAMPLE)
        diagnostics = check_program(program)
        self.assertEqual(diagnostics, [])

    def test_wall_panel_example_checks_clean(self) -> None:
        program = parse_file(WALL_PANEL_EXAMPLE)
        diagnostics = check_program(program)
        self.assertEqual(diagnostics, [])

    def test_crate_example_checks_clean(self) -> None:
        program = parse_file(CRATE_EXAMPLE)
        diagnostics = check_program(program)
        self.assertEqual(diagnostics, [])

    def test_door_example_checks_clean(self) -> None:
        program = parse_file(DOOR_EXAMPLE)
        diagnostics = check_program(program)
        self.assertEqual(diagnostics, [])

    def test_console_example_checks_clean(self) -> None:
        program = parse_file(CONSOLE_EXAMPLE)
        diagnostics = check_program(program)
        self.assertEqual(diagnostics, [])


if __name__ == "__main__":
    unittest.main()
