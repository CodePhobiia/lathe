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

import pytest

import lathe.blender as _blender_pkg
import lathe.blender_execution as _shim
from lathe.blender_execution import (
    BlenderExecutionError,
    build_execution_bundle,
    build_library_sync_manifest,
    export_blend_artifact,
    inspect_blend_artifact,
)
from lathe.errors import LatheExecutionError
from tests.fixtures.mock_blender import (  # noqa: F401 — re-exports pytest fixtures
    blender_subprocess_stub,
    mock_blender_adapter,
)


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
    def test_mock_adapter_returns_canned_bundle_happy_path(
        self, mock_blender_adapter  # noqa: F811 — pytest fixture
    ) -> None:
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
    def test_build_execution_bundle_propagates_blender_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
