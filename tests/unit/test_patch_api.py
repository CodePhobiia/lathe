"""Unit tests for ``lathe.patch_api`` (BL-22e Tranche C tail).

The patch API exposes semantic mutators that variants and CLI commands use to
edit a normalized program in a controlled way. These tests pin the public
surface: each mutator deep-copies, normalizes, and raises ``PatchAPIError`` on
unknown declarations.
"""

from __future__ import annotations

import json
import unittest
from copy import deepcopy

from lathe.errors import PatchAPIError
from lathe.normalizer import normalize_program
from lathe.patch_api import (
    add_benchmark_fixture,
    add_component_to_family,
    change_repair_policy,
    freeze_dimension,
    update_material_palette,
    widen_search_bounds,
)


def _seed_program() -> dict[str, object]:
    """Build a minimal normalized program with one of each declaration kind
    the patch API touches. Construct via ``normalize_program`` so the result
    matches what callers receive from the parser pipeline."""
    raw = {
        "families": [{"name": "fam_a", "assembly": {"components": ["comp_x"]}}],
        "components": [
            {"name": "comp_x"},
            {"name": "comp_y"},
        ],
        "assets": [{"name": "asset_a"}],
        "spaces": [
            {
                "name": "space_a",
                "vary": [{"path": "size_cm", "domain": {"type": "range", "from": 1, "to": 2}}],
                "freeze": [],
            }
        ],
        "benchmarks": [{"name": "bench_a", "values": {"compare_against": ["fixture_existing"]}}],
        "palettes": [{"name": "pal_a"}],
        "repair_policies": [{"name": "policy_a"}],
    }
    return normalize_program(raw)


class PatchAPIApplyTests(unittest.TestCase):
    def test_update_material_palette_applies_patch(self) -> None:
        program = _seed_program()
        updated = update_material_palette(program, "asset_a", "pal_a")
        asset = next(item for item in updated["assets"] if item["name"] == "asset_a")
        self.assertEqual(asset["surface"]["palette"], "pal_a")

    def test_change_repair_policy_applies_patch(self) -> None:
        program = _seed_program()
        updated = change_repair_policy(program, "asset_a", "policy_a")
        asset = next(item for item in updated["assets"] if item["name"] == "asset_a")
        self.assertEqual(asset["repair_policy"]["use"], "policy_a")

    def test_freeze_dimension_appends_to_freeze_list(self) -> None:
        program = _seed_program()
        updated = freeze_dimension(program, "space_a", "size_cm")
        space = next(item for item in updated["spaces"] if item["name"] == "space_a")
        self.assertIn("size_cm", space["freeze"])


class PatchAPIErrorTests(unittest.TestCase):
    def test_patch_on_missing_target_raises(self) -> None:
        program = _seed_program()
        with self.assertRaises(PatchAPIError) as ctx:
            update_material_palette(program, "no_such_asset", "pal_a")
        self.assertIn("no_such_asset", str(ctx.exception))

    def test_change_repair_policy_on_missing_asset_raises(self) -> None:
        program = _seed_program()
        with self.assertRaises(PatchAPIError):
            change_repair_policy(program, "ghost_asset", "policy_a")

    def test_freeze_dimension_on_missing_space_raises(self) -> None:
        program = _seed_program()
        with self.assertRaises(PatchAPIError):
            freeze_dimension(program, "ghost_space", "size_cm")


class PatchAPINoOpAndIdempotencyTests(unittest.TestCase):
    def test_freeze_dimension_is_idempotent_when_already_frozen(self) -> None:
        program = _seed_program()
        once = freeze_dimension(program, "space_a", "size_cm")
        twice = freeze_dimension(once, "space_a", "size_cm")
        space_once = next(item for item in once["spaces"] if item["name"] == "space_a")
        space_twice = next(item for item in twice["spaces"] if item["name"] == "space_a")
        # No duplicate entries — patch is a no-op when target is already present.
        self.assertEqual(space_once["freeze"].count("size_cm"), 1)
        self.assertEqual(space_twice["freeze"].count("size_cm"), 1)

    def test_add_component_to_family_is_idempotent(self) -> None:
        program = _seed_program()
        once = add_component_to_family(program, "fam_a", "comp_y")
        twice = add_component_to_family(once, "fam_a", "comp_y")
        family_twice = next(item for item in twice["families"] if item["name"] == "fam_a")
        self.assertEqual(family_twice["assembly"]["components"].count("comp_y"), 1)

    def test_add_benchmark_fixture_is_idempotent(self) -> None:
        program = _seed_program()
        once = add_benchmark_fixture(program, "bench_a", "fixture_existing")
        bench = next(item for item in once["benchmarks"] if item["name"] == "bench_a")
        self.assertEqual(bench["values"]["compare_against"].count("fixture_existing"), 1)


class PatchAPIStructureTests(unittest.TestCase):
    def test_patch_does_not_mutate_input(self) -> None:
        program = _seed_program()
        snapshot = deepcopy(program)
        update_material_palette(program, "asset_a", "pal_a")
        # Source program must be untouched: deep_copy means callers can rely on
        # immutability of the input they passed in.
        self.assertEqual(program, snapshot)

    def test_patch_preserves_list_and_dict_types(self) -> None:
        program = _seed_program()
        updated = freeze_dimension(program, "space_a", "size_cm")
        space = next(item for item in updated["spaces"] if item["name"] == "space_a")
        # The patched ``freeze`` slot remains a list, not a tuple/set, so
        # downstream JSON serialization keeps working.
        self.assertIsInstance(space["freeze"], list)
        # And ``vary`` items remain dicts, not converted.
        for vary in space["vary"]:
            self.assertIsInstance(vary, dict)

    def test_widen_search_bounds_updates_existing_or_appends(self) -> None:
        program = _seed_program()
        # Update existing path.
        updated = widen_search_bounds(program, "space_a", "size_cm", 0, 100)
        space = next(item for item in updated["spaces"] if item["name"] == "space_a")
        match = next(v for v in space["vary"] if v["path"] == "size_cm")
        self.assertEqual(match["domain"]["from"], 0)
        self.assertEqual(match["domain"]["to"], 100)
        # Appends new path when not present.
        updated2 = widen_search_bounds(program, "space_a", "new_dim", -1, 1)
        space2 = next(item for item in updated2["spaces"] if item["name"] == "space_a")
        paths = [v["path"] for v in space2["vary"]]
        self.assertIn("new_dim", paths)

    def test_patches_are_deterministic_across_repeated_application(self) -> None:
        # Running the same patch sequence on equivalent inputs must produce
        # equivalent canonical-JSON serializations. This pins that the patch
        # API does not introduce nondeterminism (e.g. dict ordering, random
        # tie-breakers) into the program.
        program_a = _seed_program()
        program_b = _seed_program()
        for prog in (program_a, program_b):
            prog_state = update_material_palette(prog, "asset_a", "pal_a")
            prog_state = freeze_dimension(prog_state, "space_a", "size_cm")
            prog_state = add_component_to_family(prog_state, "fam_a", "comp_y")
            if prog is program_a:
                final_a = prog_state
            else:
                final_b = prog_state
        canon_a = json.dumps(final_a, sort_keys=True)
        canon_b = json.dumps(final_b, sort_keys=True)
        self.assertEqual(canon_a, canon_b)


if __name__ == "__main__":
    unittest.main()
