"""Mock Blender adapter fixtures.

The real executor path calls into ``lathe.blender_execution`` (and, in
newer paths, ``lathe.blender_execution.build_execution_bundle``) which in
turn shells out to a Blender binary. These fixtures monkeypatch both the
high-level entry points and the ``subprocess.run`` boundary so tests can
exercise the executor pipeline end-to-end without a real Blender.

Provides:
- ``mock_blender_adapter`` — patches ``build_execution_bundle`` (and the
  legacy ``run_plan`` symbol if it is introduced in Wave 2 splits) to
  return a canned bundle dict shaped like real output.
- ``blender_subprocess_stub`` — helper that patches ``subprocess.run``
  with a configurable stderr/returncode; useful for error-path tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable

import pytest


def _canned_bundle(asset_name: str = "stub_asset") -> dict[str, Any]:
    """Return a bundle dict shaped like ``build_execution_bundle`` output.

    Kept intentionally minimal — Wave 3 tests that rely on specific keys
    should extend this stub rather than assume the full real payload.
    """
    return {
        "asset": asset_name,
        "execution": {
            "backend": "lathe.exec.blender_mock_v1",
            "attempted": "lathe.exec.blender_mock_v1",
            "actual": "lathe.exec.blender_mock_v1",
            "status": "success",
            "executions": [],
        },
        "render": {"views": [], "manifest": {}},
        "bake": {"textures": [], "manifest": {}},
        "blend_artifact": None,
        "diagnostics": [],
    }


@dataclass
class MockBlenderAdapter:
    """State for the mock adapter — lets a test inspect/override behavior."""

    return_value: dict[str, Any] = field(default_factory=_canned_bundle)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"args": args, "kwargs": kwargs})
        return dict(self.return_value)


@pytest.fixture()
def mock_blender_adapter(monkeypatch: pytest.MonkeyPatch) -> MockBlenderAdapter:
    """Patch the Blender execution entry points with a mock adapter.

    Patches are best-effort: whichever of ``build_execution_bundle`` /
    ``run_plan`` exists at patch time is replaced. Wave 2 may rename or
    move these; update this fixture alongside the rename.
    """
    adapter = MockBlenderAdapter()
    try:
        import lathe.blender_execution as _blender_exec
    except ImportError:
        return adapter

    for symbol in ("build_execution_bundle", "run_plan"):
        if hasattr(_blender_exec, symbol):
            monkeypatch.setattr(_blender_exec, symbol, adapter, raising=True)

    return adapter


@dataclass
class BlenderSubprocessStub:
    """Configurable stand-in for ``subprocess.run`` when Blender is invoked."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    on_call: Callable[..., Any] | None = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.on_call is not None:
            return self.on_call(*args, **kwargs)
        return SimpleNamespace(
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
            args=args[0] if args else kwargs.get("args"),
        )


@pytest.fixture()
def blender_subprocess_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> BlenderSubprocessStub:
    """Patch ``subprocess.run`` inside ``lathe.blender_execution``.

    Tests may mutate ``returncode``/``stderr`` on the returned stub before
    invoking the function under test to simulate Blender launch failures.
    """
    stub = BlenderSubprocessStub()
    try:
        import lathe.blender_execution as _blender_exec

        monkeypatch.setattr(
            _blender_exec.subprocess, "run", stub, raising=True
        )
    except (ImportError, AttributeError):
        pass
    return stub
