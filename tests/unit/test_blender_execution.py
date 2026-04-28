"""Unit tests for the ``lathe.blender_execution`` shim.

The actual implementation lives in ``lathe.blender`` (the decomposed
subpackage). ``lathe.blender_execution`` is a 24-LOC backwards-compat
shim that re-exports the public surface. These tests assert identity of
the re-exported symbols against the underlying package, plus a happy-path
call through a monkeypatched ``build_execution_bundle`` and an error
path via the mock_blender fixture helpers. Real Blender is never
invoked.
"""

from __future__ import annotations

import json
from pathlib import Path

import lathe.blender as _blender_pkg
import lathe.blender_execution as _shim
import pytest
from lathe.blender_execution import (
    BlenderExecutionError,
    build_execution_bundle,
    build_library_sync_manifest,
    export_blend_artifact,
    inspect_blend_artifact,
)
from lathe.errors import LatheExecutionError

pytest_plugins = ("tests.fixtures.mock_blender",)


class TestShimReExports:
    """The shim must re-export the exact objects from ``lathe.blender``."""

    def test_build_execution_bundle_identity(self) -> None:
        assert build_execution_bundle is _blender_pkg.build_execution_bundle

    def test_blender_execution_error_identity(self) -> None:
        assert BlenderExecutionError is _blender_pkg.BlenderExecutionError
        assert issubclass(BlenderExecutionError, LatheExecutionError)

    def test_inspect_and_export_blend_identity(self) -> None:
        assert inspect_blend_artifact is _blender_pkg.inspect_blend_artifact
        assert export_blend_artifact is _blender_pkg.export_blend_artifact

    def test_build_library_sync_manifest_identity(self) -> None:
        assert build_library_sync_manifest is _blender_pkg.build_library_sync_manifest


class TestShimBuildExecutionBundle:
    def test_mock_adapter_returns_canned_bundle_happy_path(self, mock_blender_adapter) -> None:
        # The fixture monkeypatches ``build_execution_bundle`` on the shim
        # to a recording callable that returns the canned stub bundle.
        result = _shim.build_execution_bundle(
            asset={"name": "demo"},
            stage_dir=None,
            runtime={},
            runtime_config=None,
            out_dir=None,
        )
        assert mock_blender_adapter.calls, "adapter should have recorded a call"
        assert result["asset"] == "stub_asset"
        assert result["execution"]["status"] == "success"
        assert result["diagnostics"] == []


class TestShimErrorPath:
    def test_build_execution_bundle_propagates_blender_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Subprocess-stub style: the shim's public entry point raises
        # BlenderExecutionError when the underlying Blender invocation fails.
        def raiser(**_kwargs):
            raise BlenderExecutionError("blender: command not found")

        monkeypatch.setattr(_shim, "build_execution_bundle", raiser, raising=True)
        with pytest.raises(BlenderExecutionError) as excinfo:
            _shim.build_execution_bundle(
                asset={"name": "demo"},
                stage_dir=None,
                runtime={},
                runtime_config=None,
                out_dir=None,
            )
        assert "command not found" in str(excinfo.value)
        assert isinstance(excinfo.value, LatheExecutionError)


class TestBlendArtifactExportSafety:
    def _seed_build(self, tmp_path: Path, artifact_path: str = "stages/execution/demo.blend") -> Path:
        build_dir = tmp_path / "build"
        stage_dir = build_dir / "stages" / "execution"
        stage_dir.mkdir(parents=True)
        artifact = build_dir / artifact_path
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"blend")
        bundle = {"blend_artifact_ir": {"artifact_path": artifact_path, "artifact_hash": "abc"}}
        (stage_dir / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
        return build_dir

    def test_export_blend_refuses_recorded_traversal(self, tmp_path: Path) -> None:
        build_dir = tmp_path / "build"
        stage_dir = build_dir / "stages" / "execution"
        stage_dir.mkdir(parents=True)
        (stage_dir / "bundle.json").write_text(
            json.dumps({"blend_artifact_ir": {"artifact_path": "../escape.blend"}}),
            encoding="utf-8",
        )

        with pytest.raises(FileNotFoundError):
            export_blend_artifact(build_dir)

    def test_export_blend_refuses_destination_overwrite(self, tmp_path: Path) -> None:
        build_dir = self._seed_build(tmp_path)
        destination = tmp_path / "demo.blend"
        destination.write_bytes(b"existing")

        with pytest.raises(FileExistsError):
            export_blend_artifact(build_dir, destination)
