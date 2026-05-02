"""Unit tests for ``lathe.viewer`` + ``lathe inspect --view`` (BL-36).

Covers:
- viewer static/index.html exists + parses as HTML
- ``serve`` handler class is importable and bound to ``build_dir``
- ``--view`` with ``trimesh`` present calls ``Scene.show`` via mock
- ``--view`` with ``trimesh`` missing emits a helpful error (exit 3)
"""

from __future__ import annotations

import argparse
import builtins
import sys
import tempfile
import types
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

from lathe.viewer import STATIC_DIR, build_handler_class


class _StrictHTMLValidator(HTMLParser):
    """Raises on clearly broken HTML (unbalanced / orphan tags)."""

    def __init__(self) -> None:
        super().__init__()
        self.title_seen = False
        self.has_model_viewer = False
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        if tag == "model-viewer":
            self.has_model_viewer = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.title_seen = True


class ViewerStaticTests(unittest.TestCase):
    def test_index_html_exists(self) -> None:
        path = STATIC_DIR / "index.html"
        self.assertTrue(path.exists(), f"missing static index: {path}")

    def test_index_html_parses_and_has_model_viewer(self) -> None:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        parser = _StrictHTMLValidator()
        parser.feed(html)
        self.assertTrue(parser.title_seen)
        self.assertTrue(parser.has_model_viewer)
        self.assertIn("/asset.glb", html)


class ServeHandlerTests(unittest.TestCase):
    def test_handler_class_importable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            cls = build_handler_class(build_dir)
            # Handler is a class (not instance) and is a BaseHTTPRequestHandler subclass.
            import http.server

            self.assertTrue(isinstance(cls, type))
            self.assertTrue(issubclass(cls, http.server.SimpleHTTPRequestHandler))
            self.assertEqual(Path(cls.build_dir), build_dir.resolve())

    def test_handler_finds_glb_under_stages_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            pkg = build_dir / "stages" / "package"
            pkg.mkdir(parents=True)
            glb = pkg / "asset.glb"
            glb.write_bytes(b"glTF-mock")
            cls = build_handler_class(build_dir)
            self.assertEqual(Path(cls.glb_path), glb.resolve())

    def test_handler_prefers_manifest_primary_glb_over_collision_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            pkg = build_dir / "stages" / "package"
            pkg.mkdir(parents=True)
            collision = pkg / "collision_hull.glb"
            primary = pkg / "industrial_crate.glb"
            collision.write_bytes(b"collision")
            primary.write_bytes(b"primary")
            (pkg / "package_manifest.json").write_text(
                """
{
  "outputs": [
    {"format": "collision_hull", "uri": "stages/package/collision_hull.glb"},
    {"format": "glb", "uri": "stages/package/industrial_crate.glb"}
  ]
}
""".strip(),
                encoding="utf-8",
            )

            cls = build_handler_class(build_dir)

            self.assertEqual(Path(cls.glb_path), primary.resolve())


class InspectViewModeTests(unittest.TestCase):
    def test_view_with_trimesh_present_calls_scene_show(self) -> None:
        from lathe.cli import inspect_cmd

        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            pkg = build_dir / "stages" / "package"
            pkg.mkdir(parents=True)
            (pkg / "asset.glb").write_bytes(b"glTF-mock")

            fake_scene = mock.MagicMock()
            fake_scene.show = mock.MagicMock()
            fake_trimesh = types.ModuleType("trimesh")
            fake_trimesh.load = mock.MagicMock(return_value=fake_scene)
            fake_trimesh.Scene = mock.MagicMock(return_value=fake_scene)

            with mock.patch.dict(sys.modules, {"trimesh": fake_trimesh}):
                args = argparse.Namespace(build_dir=str(build_dir), view=True)
                inspect_cmd.run_inspect(args)

            fake_trimesh.load.assert_called_once()
            fake_scene.show.assert_called_once()

    def test_view_without_trimesh_emits_helpful_error(self) -> None:
        from lathe.cli import inspect_cmd

        real_import = builtins.__import__

        def _fake_import(name: str, *args: object, **kwargs: object):
            if name == "trimesh":
                raise ImportError("no module named 'trimesh'")
            return real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(build_dir=tmp, view=True)
            with mock.patch("builtins.__import__", side_effect=_fake_import):
                with self.assertRaises(SystemExit) as ctx:
                    inspect_cmd.run_inspect(args)
            self.assertEqual(ctx.exception.code, 3)


class ServeCommandTests(unittest.TestCase):
    def test_serve_rejects_missing_build_dir(self) -> None:
        from lathe.cli import inspect_cmd

        args = argparse.Namespace(
            build_dir=str(Path(tempfile.gettempdir()) / "__lathe_nope__"),
            port=8765,
        )
        with self.assertRaises(SystemExit) as ctx:
            inspect_cmd.run_serve(args)
        self.assertEqual(ctx.exception.code, 2)

    def test_serve_help_runs(self) -> None:
        # Round-trips argparse to confirm the subcommand is registered.
        from lathe.cli import _build_parser

        parser = _build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["serve", "--help"])


if __name__ == "__main__":
    unittest.main()
