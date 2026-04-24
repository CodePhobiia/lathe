"""Unit tests for ``lathe.paths.safe_resolve`` (SEC-1)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from lathe.paths import PathGuardError, safe_resolve


class SafeResolveHappyPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_relative_path_resolves_under_root(self) -> None:
        resolved = safe_resolve(self.root, "foo/bar.txt")
        self.assertTrue(
            str(resolved).startswith(str(Path(os.path.realpath(self.root))))
        )
        self.assertTrue(resolved.name == "bar.txt")

    def test_single_component_resolves(self) -> None:
        resolved = safe_resolve(self.root, "simple.txt")
        self.assertEqual(resolved.name, "simple.txt")

    def test_dot_components_collapse(self) -> None:
        resolved = safe_resolve(self.root, "./foo/./bar.txt")
        self.assertEqual(resolved.name, "bar.txt")


class SafeResolveRejectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rejects_absolute_posix(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "/etc/passwd")

    def test_rejects_absolute_windows_drive(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "C:\\Windows\\System32\\cmd.exe")

    def test_rejects_drive_relative_without_separator(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "C:foo")

    def test_rejects_traversal_escape(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "../../../etc/passwd")

    def test_rejects_nul_byte(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "foo\x00bar")

    def test_rejects_windows_reserved_bare(self) -> None:
        for name in ("CON", "prn", "Aux", "nul"):
            with self.assertRaises(PathGuardError):
                safe_resolve(self.root, name)

    def test_rejects_windows_reserved_com_lpt(self) -> None:
        for name in ("COM1", "com9", "LPT1", "lpt9", "PRN.txt", "con.log"):
            with self.assertRaises(PathGuardError):
                safe_resolve(self.root, name)

    def test_rejects_83_short_name(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "PROGRA~1/foo")

    def test_rejects_trailing_dot(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "foo.txt.")

    def test_rejects_trailing_space(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "foo ")

    def test_rejects_alternate_data_stream(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "foo.txt:stream")

    def test_rejects_extended_length_prefix(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "\\\\?\\C:\\foo")

    def test_rejects_device_namespace_prefix(self) -> None:
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "\\\\.\\PhysicalDrive0")


class SafeResolveSymlinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_allow_symlinks_true_accepts_symlink(self) -> None:
        target = self.root / "target.txt"
        target.write_text("ok", encoding="utf-8")
        link = self.root / "link.txt"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported in this environment")
        resolved = safe_resolve(self.root, "link.txt", allow_symlinks=True)
        self.assertTrue(resolved.exists())

    def test_disallow_symlinks_rejects(self) -> None:
        target = self.root / "target.txt"
        target.write_text("ok", encoding="utf-8")
        link = self.root / "link.txt"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported in this environment")
        with self.assertRaises(PathGuardError):
            safe_resolve(self.root, "link.txt")


if __name__ == "__main__":
    unittest.main()
