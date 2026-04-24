"""Unit tests for ``lathe.snapshot`` and ``lathe snapshot`` CLI (RPT-4, V0.2 E4)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lathe.snapshot import (
    SNAPSHOT_FILENAME,
    SNAPSHOT_SCHEMA_VERSION,
    STAGE_ORDER,
    collect_snapshot,
    write_snapshot,
)


def _populate_build(root: Path, *, include_validate: bool = True) -> None:
    (root / "stages" / "shape").mkdir(parents=True)
    (root / "stages" / "optimize").mkdir(parents=True)
    if include_validate:
        (root / "stages" / "validate").mkdir(parents=True)
    (root / "stages" / "package").mkdir(parents=True)

    (root / "selector_manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "latheVersion": "0.1.0",
                "sourcePath": "examples/courier_drone.lth",
                "asset": "courier_drone",
                "buildHash": "deadbeef" * 8,
            }
        ),
        encoding="utf-8",
    )
    (root / "stages" / "shape" / "bundle.json").write_text(
        json.dumps({"backend_id": "lathe.shape.intent_mesh_handoff_v1", "seed": 1}),
        encoding="utf-8",
    )
    (root / "stages" / "optimize" / "bundle.json").write_text(
        json.dumps({"lods": 4, "collision": "ok"}),
        encoding="utf-8",
    )
    (root / "stages" / "package" / "bundle.json").write_text(
        json.dumps({"glb": "courier_drone.glb"}),
        encoding="utf-8",
    )
    if include_validate:
        (root / "stages" / "validate" / "report.json").write_text(
            json.dumps({"certified": True, "score": 0.880373, "threshold": 0.85}),
            encoding="utf-8",
        )


def _validate_against_schema(snapshot: dict) -> None:
    schema_path = (
        Path(__file__).resolve().parents[2] / "schema" / "lathe_snapshot.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover - mirror upstream style
        raise unittest.SkipTest("jsonschema not installed")
    jsonschema.validate(instance=snapshot, schema=schema)


class SnapshotRoundTripTests(unittest.TestCase):
    def test_snapshot_round_trips_against_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            _populate_build(build)
            path = write_snapshot(build, deterministic=True)
            self.assertTrue(path.exists())
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["schemaVersion"], SNAPSHOT_SCHEMA_VERSION)
            self.assertIn("shape", snapshot["stages"])
            self.assertIn("optimize", snapshot["stages"])
            self.assertIn("validate", snapshot["stages"])
            self.assertEqual(snapshot["score"], 0.880373)
            self.assertTrue(snapshot["certified"])
            self.assertEqual(snapshot["buildHash"], "deadbeef" * 8)
            _validate_against_schema(snapshot)

    def test_deterministic_bytes_match_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            _populate_build(build)
            a = write_snapshot(build, deterministic=True, out_path=Path(tmp) / "a.json")
            b = write_snapshot(build, deterministic=True, out_path=Path(tmp) / "b.json")
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_missing_validate_stage_is_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            _populate_build(build, include_validate=False)
            snapshot = collect_snapshot(build, deterministic=True)
            self.assertNotIn("validate", snapshot["stages"])
            # score/certified keys omitted when validate report is absent
            self.assertNotIn("score", snapshot)
            self.assertNotIn("certified", snapshot)
            _validate_against_schema(snapshot)

    def test_stage_order_constant_covers_all_stages(self) -> None:
        # Sanity guard: CLAUDE.md STAGE_ORDER should contain 13 stages.
        self.assertEqual(len(STAGE_ORDER), 13)
        self.assertEqual(STAGE_ORDER[0], "refs")
        self.assertEqual(STAGE_ORDER[-1], "package")


class SnapshotCliTests(unittest.TestCase):
    def test_missing_build_dir_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does_not_exist"
            proc = subprocess.run(
                [sys.executable, "-m", "lathe.cli", "snapshot", str(missing)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("build directory does not exist", proc.stderr)

    def test_cli_smoke_emits_snapshot_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp) / "courier_drone"
            build.mkdir()
            _populate_build(build)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lathe.cli",
                    "snapshot",
                    str(build),
                    "--deterministic",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            out_file = build / SNAPSHOT_FILENAME
            self.assertTrue(out_file.exists())
            snapshot = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["timestamp"], "0000-00-00T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
