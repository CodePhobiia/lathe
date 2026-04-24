"""Unit tests for ``lathe.formatter``.

Covers canonical output (golden pairs), idempotence across every hero
``.lth`` file, comment preservation, empty/whitespace input, malformed
input, the ``--check`` mode exit code, and a whitespace-only fuzz that
collapses back to the canonical form.
"""

from __future__ import annotations

import io
import random
import unittest
from pathlib import Path
from unittest import mock

from lathe.errors import LatheError, LatheParseError
from lathe.formatter import (
    _tokenize,
    check_formatted,
    format_file,
    format_source,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "fmt"
EXAMPLES = REPO_ROOT / "examples"

HERO_EXAMPLES = [
    "brassbound_chest.lth",
    "industrial_crate.lth",
    "mechanical_door.lth",
    "console_terminal.lth",
    "courier_drone.lth",
    "sci_fi_wall_panel.lth",
    "service_cabinet.lth",
    "control_pedestal.lth",
    "supply_container.lth",
]


class FormatSourceHappyPathTests(unittest.TestCase):
    def test_empty_source_returns_empty(self) -> None:
        self.assertEqual(format_source(""), "")

    def test_whitespace_only_source_returns_empty(self) -> None:
        self.assertEqual(format_source("\n\n   \t\n"), "")

    def test_messy_source_canonicalized(self) -> None:
        messy = (
            "profile   p1{\n"
            "  defaults{build.optimize.lods=4}\n"
            "ensure units(cm)\n"
            "}\n"
        )
        out = format_source(messy)
        # Canonical form has 2-space indent, spaces around `=`,
        # blocks on their own lines, etc.
        self.assertIn("profile p1 {", out)
        self.assertIn("  defaults {", out)
        self.assertIn("    build.optimize.lods = 4", out)
        self.assertTrue(out.endswith("\n"))

    def test_list_gets_trailing_comma_when_multiline(self) -> None:
        source = (
            "asset a: hard_surface_prop {\n"
            "  intent {\n"
            "    parts = [\n"
            "      one,\n"
            "      two\n"
            "    ]\n"
            "  }\n"
            "}\n"
        )
        out = format_source(source)
        self.assertIn("      one,\n      two,\n", out)

    def test_inline_list_stays_inline(self) -> None:
        source = (
            "profile p {\n"
            "  defaults {\n"
            "    package.formats = [usd, glb]\n"
            "  }\n"
            "}\n"
        )
        out = format_source(source)
        self.assertIn("package.formats = [usd, glb]", out)
        self.assertNotIn("[\n", out)


class IdempotenceTests(unittest.TestCase):
    def test_every_hero_example_is_idempotent(self) -> None:
        for name in HERO_EXAMPLES:
            path = EXAMPLES / name
            if not path.exists():
                continue
            with self.subTest(example=name):
                source = path.read_text(encoding="utf-8")
                once = format_source(source)
                twice = format_source(once)
                self.assertEqual(once, twice)

    def test_every_example_is_idempotent(self) -> None:
        for path in sorted(EXAMPLES.glob("*.lth")):
            with self.subTest(example=path.name):
                source = path.read_text(encoding="utf-8")
                once = format_source(source)
                twice = format_source(once)
                self.assertEqual(once, twice)


class CommentPreservationTests(unittest.TestCase):
    def test_line_comment_preserved(self) -> None:
        source = (
            "// file banner\n"
            "module foo.bar\n"
        )
        out = format_source(source)
        self.assertIn("// file banner", out)

    def test_block_comment_preserved(self) -> None:
        source = (
            "/* note */\n"
            "module foo.bar\n"
        )
        out = format_source(source)
        self.assertIn("/* note */", out)

    def test_trailing_line_comment_preserved(self) -> None:
        source = (
            "profile p {\n"
            "  defaults {\n"
            "    package.manifest = true   // important\n"
            "  }\n"
            "}\n"
        )
        out = format_source(source)
        self.assertIn("package.manifest = true", out)
        self.assertIn("// important", out)

    def test_comment_preservation_is_idempotent(self) -> None:
        source = (
            "// top\n"
            "module foo.bar\n"
            "\n"
            "// before profile\n"
            "profile p {\n"
            "  // inside\n"
            "  defaults {\n"
            "    package.manifest = true  // trailing\n"
            "  }\n"
            "}\n"
        )
        once = format_source(source)
        twice = format_source(once)
        self.assertEqual(once, twice)


class GoldenPairTests(unittest.TestCase):
    def test_input_matches_expected(self) -> None:
        input_dir = FIXTURES / "input"
        expected_dir = FIXTURES / "expected"
        input_files = sorted(input_dir.glob("*.lth"))
        self.assertGreater(len(input_files), 0, "expected at least one fixture pair")
        for input_path in input_files:
            expected_path = expected_dir / input_path.name
            self.assertTrue(
                expected_path.exists(),
                f"missing expected fixture for {input_path.name}",
            )
            with self.subTest(fixture=input_path.name):
                source = input_path.read_text(encoding="utf-8")
                expected = expected_path.read_text(encoding="utf-8")
                got = format_source(source)
                self.assertEqual(got, expected)


class CheckFormattedTests(unittest.TestCase):
    def test_returns_false_on_messy_source(self) -> None:
        messy = "profile   p1{  }\n"
        is_canonical, canonical = check_formatted(messy)
        self.assertFalse(is_canonical)
        self.assertNotEqual(canonical, messy)
        self.assertEqual(format_source(canonical), canonical)

    def test_returns_true_on_canonical_source(self) -> None:
        canonical = format_source("profile p1 {}\n")
        is_canonical, output = check_formatted(canonical)
        self.assertTrue(is_canonical)
        self.assertEqual(output, canonical)


class MalformedSourceTests(unittest.TestCase):
    def test_unclosed_brace_raises(self) -> None:
        with self.assertRaises(LatheParseError):
            format_source("profile p {\n")

    def test_unmatched_closer_raises(self) -> None:
        with self.assertRaises(LatheParseError):
            format_source("profile p }\n")

    def test_unknown_character_raises(self) -> None:
        with self.assertRaises(LatheParseError):
            format_source("profile $bad {}")


class FormatFileTests(unittest.TestCase):
    def test_in_place_rewrite_reports_changed(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.lth"
            path.write_text("profile   p{  }\n", encoding="utf-8")
            changed = format_file(path, in_place=True)
            self.assertTrue(changed)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                format_source("profile p {}\n"),
            )

    def test_in_place_noop_when_already_canonical(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.lth"
            canonical = format_source("profile p {}\n")
            path.write_text(canonical, encoding="utf-8")
            changed = format_file(path, in_place=True)
            self.assertFalse(changed)
            self.assertEqual(path.read_text(encoding="utf-8"), canonical)

    def test_dry_run_does_not_write(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.lth"
            original = "profile   p{  }\n"
            path.write_text(original, encoding="utf-8")
            would_change = format_file(path, in_place=False)
            self.assertTrue(would_change)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


class FuzzCanonicalizationTests(unittest.TestCase):
    """Apply whitespace-only perturbations to the canonical form and
    assert that the formatter collapses every variant back to the
    canonical text.

    We perturb only the tokenizer's ``hspace`` regions so that strings
    and other multi-character tokens are left byte-exact.
    """

    def _perturb_hspace(self, text: str, seed: int) -> str:
        rng = random.Random(seed)
        pieces: list[str] = []
        for tok in _tokenize(text):
            if tok.kind == "hspace":
                pieces.append(" " * rng.randint(1, 5))
            else:
                pieces.append(tok.value)
        return "".join(pieces)

    def test_five_variants_collapse_to_canonical(self) -> None:
        source = (EXAMPLES / "courier_drone.lth").read_text(encoding="utf-8")
        canonical = format_source(source)
        for seed in range(5):
            with self.subTest(seed=seed):
                perturbed = self._perturb_hspace(canonical, seed)
                self.assertEqual(format_source(perturbed), canonical)


if __name__ == "__main__":
    unittest.main()
