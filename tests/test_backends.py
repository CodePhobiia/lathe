from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lathe.backends import resolve_selected_backends
from lathe.checker import check_program
from lathe.parser import parse_file
from lathe.resolver import materialize_asset


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "courier_drone.lth"


class LatheBackendResolutionTests(unittest.TestCase):
    def test_default_backend_stack_selection(self) -> None:
        program = parse_file(EXAMPLE)
        asset = materialize_asset(program, "courier_drone")
        resolved = resolve_selected_backends(asset)
        self.assertEqual(resolved["stack"]["id"], "lathe.stack.hard_surface_game_asset_v1")
        self.assertEqual(resolved["selected"]["shape"]["id"], "lathe.shape.intent_mesh_handoff_v1")
        self.assertEqual(resolved["selected"]["uv"]["id"], "lathe.uv.xatlas_v1")
        self.assertEqual(resolved["selected"]["package"]["id"], "lathe.package.openusd_gltf_v1")

    def test_udim_rejected_by_first_stack(self) -> None:
        source = EXAMPLE.read_text(encoding="utf-8").replace("unwrap = auto", "unwrap = auto\n      tile_mode = udim\n      udims = [1001]")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "courier_drone.lth"
            path.write_text(source, encoding="utf-8")
            program = parse_file(path)
        diagnostics = check_program(program)
        error_codes = {item["code"] for item in diagnostics if item["severity"] == "error"}
        self.assertIn("L4604", error_codes)

    def test_unknown_backend_is_rejected(self) -> None:
        source = EXAMPLE.read_text(encoding="utf-8").replace("mode = generate", "backend = studio.unknown_backend\n      mode = generate", 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "courier_drone.lth"
            path.write_text(source, encoding="utf-8")
            program = parse_file(path)
        diagnostics = check_program(program)
        error_codes = {item["code"] for item in diagnostics if item["severity"] == "error"}
        self.assertIn("L4601", error_codes)


if __name__ == "__main__":
    unittest.main()
