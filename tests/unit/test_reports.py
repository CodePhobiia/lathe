"""Unit tests for ``lathe.reports`` (BL-36, Plan 08 Phase 6).

Covers:
- terminal rendering for certified vs non-certified reports
- HTML rendering (parsed with ``html.parser``)
- ``write_report`` path handling
- TTY-forced color output
"""

from __future__ import annotations

import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from lathe.reports import render_html_report, render_terminal_report, write_report


def _fake_certified_report() -> dict:
    return {
        "asset": "courier_drone",
        "kind": "asset",
        "out_dir": "/tmp/build/courier_drone",
        "certified": True,
        "score": 0.912,
        "threshold": 0.85,
        "outputs": {"glb": "stages/package/courier_drone.glb"},
        "validate_detail": {
            "semantic_quality": {
                "metrics": {"semantic_preservation_quality": 0.91},
                "thresholds": {"semantic_preservation_quality": 0.85},
                "diagnostics": [],
            },
            "visual_quality": {
                "metrics": {"silhouette_match": 0.88},
                "thresholds": {"silhouette_match": 0.8},
                "diagnostics": [],
            },
        },
        "diagnostics": [],
        "repair_suggestions": [],
    }


def _fake_failed_report() -> dict:
    return {
        "asset": "courier_drone",
        "kind": "asset",
        "out_dir": "/tmp/build/courier_drone",
        "certified": False,
        "score": 0.42,
        "threshold": 0.85,
        "outputs": {},
        "validate_detail": {
            "semantic_quality": {
                "metrics": {"semantic_preservation_quality": 0.4},
                "thresholds": {"semantic_preservation_quality": 0.85},
                "diagnostics": [
                    {
                        "severity": "error",
                        "code": "semantic.preservation_below_threshold",
                        "message": "Semantic preservation quality below minimum.",
                    },
                ],
            },
        },
        "diagnostics": [
            {"severity": "warning", "code": "shape.fallback_used", "message": "Provider fallback applied."},
        ],
        "repair_suggestions": [
            {"target": "shape.params.thickness", "hint": "Increase to >=0.04."},
        ],
    }


class _SectionCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.section_classes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "section":
            for key, value in attrs:
                if key == "class" and value:
                    self.section_classes.append(value)


class TerminalReportTests(unittest.TestCase):
    def test_certified_renders_pass_banner(self) -> None:
        out = render_terminal_report(_fake_certified_report(), use_color=False)
        self.assertIn("PASS", out)
        self.assertIn("courier_drone", out)
        self.assertIn("0.912", out)
        self.assertIn("semantic_quality", out)
        self.assertNotIn("FAIL", out.split("\n")[0])

    def test_failed_renders_fail_banner_and_suggestion(self) -> None:
        out = render_terminal_report(_fake_failed_report(), use_color=False)
        self.assertIn("FAIL", out)
        self.assertIn("shape.params.thickness", out)
        self.assertIn("semantic.preservation_below_threshold", out)

    def test_color_applied_when_use_color_true(self) -> None:
        plain = render_terminal_report(_fake_certified_report(), use_color=False)
        colored = render_terminal_report(_fake_certified_report(), use_color=True)
        self.assertNotEqual(plain, colored)
        # Either rich-rendered output or hand-rolled ANSI must contain escape codes.
        self.assertIn("\x1b[", colored)


class HtmlReportTests(unittest.TestCase):
    def test_html_contains_summary_section_and_score(self) -> None:
        html = render_html_report(_fake_certified_report())
        self.assertIn("<!doctype html>", html)
        parser = _SectionCollector()
        parser.feed(html)
        self.assertTrue(
            any("summary" in cls for cls in parser.section_classes),
            f"missing <section class=\"summary ...\"> (got {parser.section_classes})",
        )
        self.assertIn("0.912", html)
        self.assertIn("courier_drone", html)

    def test_html_escapes_untrusted_values(self) -> None:
        report = _fake_failed_report()
        report["asset"] = "<script>alert(1)</script>"
        html = render_html_report(report)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_failed_report_has_fail_banner(self) -> None:
        html = render_html_report(_fake_failed_report())
        self.assertIn("summary fail", html)
        self.assertIn("FAIL", html)


class WriteReportTests(unittest.TestCase):
    def test_write_html_produces_expected_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_report(_fake_certified_report(), Path(tmp), "html")
            self.assertEqual(path.name, "report.html")
            self.assertTrue(path.exists())
            self.assertIn("<!doctype html>", path.read_text(encoding="utf-8"))

    def test_write_terminal_produces_plain_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_report(_fake_certified_report(), Path(tmp), "terminal")
            self.assertEqual(path.name, "report.txt")
            content = path.read_text(encoding="utf-8")
            self.assertIn("PASS", content)
            self.assertNotIn("\x1b[", content)

    def test_write_unknown_format_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write_report(_fake_certified_report(), Path(tmp), "pdf")


if __name__ == "__main__":
    unittest.main()
