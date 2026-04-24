"""Unit tests for ``lathe diff`` snapshot comparator (RPT-5, V0.2)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _snapshot(
    *,
    stages: dict | None = None,
    score: float | None = 0.88,
    certified: bool | None = True,
    lathe_version: str = "0.1.0",
    source_path: str = "examples/courier_drone.lth",
    build_hash: str = "deadbeef" * 8,
) -> dict:
    snap: dict = {
        "schemaVersion": 1,
        "latheVersion": lathe_version,
        "sourcePath": source_path,
        "buildHash": build_hash,
        "stages": stages if stages is not None else {
            "shape": "a" * 64,
            "topology": "b" * 64,
            "uv": "c" * 64,
            "optimize": "d" * 64,
            "validate": "e" * 64,
            "package": "f" * 64,
        },
        "timestamp": "0000-00-00T00:00:00Z",
    }
    if score is not None:
        snap["score"] = score
    if certified is not None:
        snap["certified"] = certified
    return snap


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    return path


def _run_diff(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", "diff", *argv],
        capture_output=True,
        text=True,
    )


class DiffIdenticalTests(unittest.TestCase):
    def test_identical_snapshots_emit_no_drift_and_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot())
            b = _write(tmpp / "b.json", _snapshot())
            proc = _run_diff(str(a), str(b))
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertIn("no drift", proc.stdout)


class DiffScoreTests(unittest.TestCase):
    def test_score_change_surfaces_delta_and_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot(score=0.880000))
            b = _write(tmpp / "b.json", _snapshot(score=0.920000))
            proc = _run_diff(str(a), str(b))
            self.assertEqual(proc.returncode, 1, msg=proc.stdout + proc.stderr)
            self.assertIn("score", proc.stdout)
            self.assertIn("0.04", proc.stdout)


class DiffStageHashTests(unittest.TestCase):
    def test_stage_hash_change_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot())
            drifted_stages = {
                "shape": "a" * 64,
                "topology": "NEW" + ("b" * 61),
                "uv": "c" * 64,
                "optimize": "d" * 64,
                "validate": "e" * 64,
                "package": "f" * 64,
            }
            b = _write(tmpp / "b.json", _snapshot(stages=drifted_stages))
            proc = _run_diff(str(a), str(b))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("topology", proc.stdout)
            self.assertIn("drifted", proc.stdout)


class DiffCertifiedFlipTests(unittest.TestCase):
    def test_certified_flip_is_prominent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot(certified=True))
            b = _write(tmpp / "b.json", _snapshot(certified=False))
            proc = _run_diff(str(a), str(b))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("certified flipped", proc.stdout)


class DiffMissingFileTests(unittest.TestCase):
    def test_missing_file_exits_two_with_helpful_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot())
            proc = _run_diff(str(a), str(tmpp / "does_not_exist.json"))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("snapshot not found", proc.stderr)


class DiffJsonOutputTests(unittest.TestCase):
    def test_json_output_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot())
            b = _write(tmpp / "b.json", _snapshot(score=0.9))
            proc = _run_diff(str(a), str(b), "--json")
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertIn("stages", payload)
            self.assertIn("has_drift", payload)
            self.assertTrue(payload["has_drift"])
            self.assertIn("score_delta", payload)

    def test_json_no_drift_has_drift_false_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot())
            b = _write(tmpp / "b.json", _snapshot())
            proc = _run_diff(str(a), str(b), "--json")
            self.assertEqual(proc.returncode, 0)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["has_drift"])


class DiffLatheVersionTests(unittest.TestCase):
    def test_latheVersion_mismatch_surfaces_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot(lathe_version="0.1.0"))
            b = _write(tmpp / "b.json", _snapshot(lathe_version="0.2.0"))
            proc = _run_diff(str(a), str(b))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("latheVersion mismatch", proc.stdout)


class DiffStageAddedRemovedTests(unittest.TestCase):
    def test_added_stage_shows_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a_stages = {"shape": "a" * 64, "package": "f" * 64}
            b_stages = {"shape": "a" * 64, "package": "f" * 64, "physics": "p" * 64}
            a = _write(tmpp / "a.json", _snapshot(stages=a_stages))
            b = _write(tmpp / "b.json", _snapshot(stages=b_stages))
            proc = _run_diff(str(a), str(b), "--json")
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            added_stage_names = [e["stage"] for e in payload["stages"]["added"]]
            self.assertIn("physics", added_stage_names)


class DiffVerboseTests(unittest.TestCase):
    def test_verbose_flag_lists_matching_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            a = _write(tmpp / "a.json", _snapshot())
            b = _write(tmpp / "b.json", _snapshot())
            proc = _run_diff(str(a), str(b), "--verbose")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("matching", proc.stdout)


class DiffSubcommandCollisionTests(unittest.TestCase):
    def test_lathe_diff_help_does_not_collide_with_ref_diff(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "lathe.cli", "diff", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("snapshot_a", proc.stdout)
        self.assertIn("snapshot_b", proc.stdout)
        # Confirm ref diff still resolves via its own subcommand group.
        proc2 = subprocess.run(
            [sys.executable, "-m", "lathe.cli", "ref", "diff", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc2.returncode, 0)
        self.assertIn("build_a", proc2.stdout)


if __name__ == "__main__":
    unittest.main()
