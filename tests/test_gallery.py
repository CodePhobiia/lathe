"""Tests for the hero gallery + scoreboard tooling (BL-35, Plan 08 Phase 5)."""
from __future__ import annotations

import importlib.util
import json
import string
import sys
from pathlib import Path

import pytest

from lathe.hero_manifest import HEROES, Hero, hero_by_name


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_gallery_tests_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestHeroManifest:
    def test_has_nine_heroes(self):
        assert len(HEROES) == 9

    def test_names_unique(self):
        names = [h.asset_name for h in HEROES]
        assert len(set(names)) == len(names)

    def test_sources_exist(self):
        for hero in HEROES:
            assert hero.source_path.exists(), f"missing source for {hero.asset_name}: {hero.source_path}"

    def test_thresholds_in_range(self):
        for hero in HEROES:
            assert 0.5 <= hero.threshold <= 1.0, f"{hero.asset_name} threshold {hero.threshold} out of [0.5, 1.0]"

    def test_expected_heroes_present(self):
        expected = {
            "courier_drone",
            "brassbound_chest",
            "industrial_crate",
            "mechanical_door",
            "console_terminal",
            "sci_fi_wall_panel",
            "service_cabinet",
            "control_pedestal",
            "supply_container",
        }
        assert {h.asset_name for h in HEROES} == expected

    def test_hero_by_name(self):
        h = hero_by_name("courier_drone")
        assert h.threshold == 0.86
        with pytest.raises(KeyError):
            hero_by_name("does_not_exist")


class TestScriptsImport:
    def test_render_gallery_importable(self):
        mod = _load_script("render_gallery")
        assert hasattr(mod, "main")
        assert hasattr(mod, "render_hero_page")
        assert hasattr(mod, "render_landing")

    def test_render_scoreboard_importable(self):
        mod = _load_script("render_scoreboard")
        assert hasattr(mod, "main")
        assert hasattr(mod, "render_markdown")
        assert hasattr(mod, "collect_row")


class TestGalleryTemplate:
    def test_template_renders(self, tmp_path: Path):
        template_path = REPO_ROOT / "docs" / "templates" / "gallery_index.html.j2"
        assert template_path.exists()
        template = string.Template(template_path.read_text(encoding="utf-8"))
        html = template.safe_substitute(
            asset_name="fake_hero",
            score="0.912345",
            threshold="0.84",
            certified="certified",
            certified_class="yes",
            glb_path="fake_hero.glb",
            renders_block='<div class="renders"></div>',
        )
        assert "fake_hero" in html
        assert "0.912345" in html
        assert "certified-yes" in html
        assert "fake_hero.glb" in html


class TestScoreboardRendering:
    def test_markdown_from_sample(self):
        import datetime as _dt

        mod = _load_script("render_scoreboard")
        sample_rows = [
            {
                "asset_name": "courier_drone",
                "family": "vehicle",
                "threshold": 0.86,
                "score": 0.879435,
                "certified": True,
                "build_time_s": 179.5,
                "glb_sha256": "5d20f33e24c8f2531d468a1fd5ea0b1090871f6ab0b08b35384a8a226aafe4d9",
                "source": "snapshot",
            },
            {
                "asset_name": "service_cabinet",
                "family": "architecture",
                "threshold": 0.82,
                "score": None,
                "certified": None,
                "build_time_s": None,
                "glb_sha256": None,
                "source": "none",
            },
        ]
        md = mod.render_markdown(sample_rows, _dt.datetime(2026, 4, 23, 12, 0, 0))
        assert "# Lathe hero scoreboard" in md
        assert "Last updated: 2026-04-23" in md
        assert "courier_drone" in md
        assert "0.879435" in md
        assert "0.86" in md
        assert "yes" in md
        assert "n/a" in md
        lines = [ln for ln in md.splitlines() if ln.startswith("|")]
        assert len(lines) >= 2 + len(sample_rows)

    def test_collect_row_from_sample_build_report(self, tmp_path: Path):
        mod = _load_script("render_scoreboard")
        hero = hero_by_name("courier_drone")
        asset_dir = tmp_path / hero.asset_name
        asset_dir.mkdir()
        (asset_dir / "build_report.json").write_text(
            json.dumps(
                {
                    "asset": hero.asset_name,
                    "certified": True,
                    "score": 0.879435,
                    "threshold": hero.threshold,
                    "outputs": [],
                }
            ),
            encoding="utf-8",
        )
        row = mod.collect_row(hero, tmp_path)
        assert row["score"] == pytest.approx(0.879435)
        assert row["certified"] is True
        assert row["source"] == "build_report"

    def test_collect_row_handles_missing(self, tmp_path: Path):
        mod = _load_script("render_scoreboard")
        hero = hero_by_name("mechanical_door")
        row = mod.collect_row(hero, tmp_path)
        assert row["score"] is None
        assert row["certified"] is None
        assert row["source"] == "none"


class TestGalleryLandingRendering:
    def test_render_hero_page_writes_html(self, tmp_path: Path, monkeypatch):
        mod = _load_script("render_gallery")
        hero = Hero(
            asset_name="fake_hero",
            source_path=REPO_ROOT / "examples" / "courier_drone.lth",
            family="container",
            threshold=0.84,
        )
        report = {"score": 0.9, "threshold": 0.84, "certified": True, "outputs": []}
        template_path = REPO_ROOT / "docs" / "templates" / "gallery_index.html.j2"
        template = string.Template(template_path.read_text(encoding="utf-8"))
        out_dir = tmp_path / hero.asset_name
        out_dir.mkdir()
        page = mod.render_hero_page(hero, report, None, [], template, out_dir)
        assert page.exists()
        assert "fake_hero" in page.read_text(encoding="utf-8")
