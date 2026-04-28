"""Unit tests for the geometry kernel registry and resolver (GEO-2)."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from lathe.geometry import (
    GeometryKernel,
    GeometryKernelUnavailable,
    UnknownGeometryKernel,
    list_registered_kernels,
    register_geometry_kernel,
    resolve_geometry_kernel,
)
from lathe.geometry import (
    kernel as k_mod,
)
from lathe.geometry.kernel import (
    MANIFOLD_KERNEL_ID,
    REFERENCE_KERNEL_ID,
)
from lathe.geometry.manifold_kernel import manifold_available, manifold_kernel
from lathe.geometry.reference_kernel import ReferenceKernel, reference_kernel

MANIFOLD_AVAILABLE = manifold_available()


# ---------------------------------------------------------------------------
# Registry basics
# ---------------------------------------------------------------------------


def test_builtin_kernels_are_registered() -> None:
    registered = list_registered_kernels()
    assert MANIFOLD_KERNEL_ID in registered
    assert REFERENCE_KERNEL_ID in registered


def test_reference_kernel_is_always_available() -> None:
    kernel = reference_kernel()
    assert kernel.name == REFERENCE_KERNEL_ID
    probe = kernel.probe()
    assert probe["available"] is True
    assert probe["name"] == REFERENCE_KERNEL_ID


# ---------------------------------------------------------------------------
# Default selection
# ---------------------------------------------------------------------------


def test_default_selection_prefers_manifold_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LATHE_GEOMETRY_BACKEND", raising=False)
    kernel = resolve_geometry_kernel(None)
    if MANIFOLD_AVAILABLE:
        assert kernel.name == MANIFOLD_KERNEL_ID
    else:
        assert kernel.name == REFERENCE_KERNEL_ID


def test_default_falls_back_to_reference_when_manifold_factory_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("LATHE_GEOMETRY_BACKEND", raising=False)

    def _raise() -> GeometryKernel:
        raise GeometryKernelUnavailable(kernel=MANIFOLD_KERNEL_ID, source="test")

    register_geometry_kernel(MANIFOLD_KERNEL_ID, _raise)
    try:
        with caplog.at_level(logging.INFO, logger="lathe.geometry.kernel"):
            kernel = resolve_geometry_kernel(None)
        assert kernel.name == REFERENCE_KERNEL_ID
        assert any("falling back" in rec.message for rec in caplog.records)
    finally:
        # Restore the real manifold factory so later tests see the normal registry.
        register_geometry_kernel(MANIFOLD_KERNEL_ID, manifold_kernel)


# ---------------------------------------------------------------------------
# Env / runtime_config precedence
# ---------------------------------------------------------------------------


def test_env_forces_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LATHE_GEOMETRY_BACKEND", "reference")
    kernel = resolve_geometry_kernel(None)
    assert kernel.name == REFERENCE_KERNEL_ID


def test_runtime_config_forces_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LATHE_GEOMETRY_BACKEND", raising=False)
    runtime_config = {"runtime": {"geometry": {"backend": REFERENCE_KERNEL_ID}}}
    kernel = resolve_geometry_kernel(runtime_config)
    assert kernel.name == REFERENCE_KERNEL_ID


def test_env_takes_precedence_over_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LATHE_GEOMETRY_BACKEND", REFERENCE_KERNEL_ID)
    runtime_config = {"runtime": {"geometry": {"backend": MANIFOLD_KERNEL_ID}}}
    kernel = resolve_geometry_kernel(runtime_config)
    assert kernel.name == REFERENCE_KERNEL_ID


def test_unknown_backend_via_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LATHE_GEOMETRY_BACKEND", "lathe.geometry.does_not_exist_v1")
    with pytest.raises(UnknownGeometryKernel) as excinfo:
        resolve_geometry_kernel(None)
    # The helpful error must list what IS registered so the operator can fix the typo.
    assert REFERENCE_KERNEL_ID in str(excinfo.value)


def test_unknown_backend_via_runtime_config_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LATHE_GEOMETRY_BACKEND", raising=False)
    runtime_config = {"runtime": {"geometry": {"backend": "nope"}}}
    with pytest.raises(UnknownGeometryKernel):
        resolve_geometry_kernel(runtime_config)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_reference_kernel_satisfies_protocol() -> None:
    kernel: Any = reference_kernel()
    # runtime_checkable duck-type check
    assert isinstance(kernel, GeometryKernel)
    # Spot-check each method is callable and has the right shape.
    box = kernel.build_primitive("box", extents=(1.0, 1.0, 1.0))
    assert kernel.is_watertight(box) is True
    assert kernel.body_count(box) == 1
    tri = kernel.to_trimesh(box)
    assert len(tri.faces) >= 1


@pytest.mark.skipif(not MANIFOLD_AVAILABLE, reason="manifold3d not installed")
def test_manifold_kernel_satisfies_protocol() -> None:
    kernel: Any = manifold_kernel()
    assert isinstance(kernel, GeometryKernel)
    box = kernel.build_primitive("box", extents=(1.0, 1.0, 1.0))
    assert kernel.is_watertight(box) is True
    assert kernel.body_count(box) == 1


# ---------------------------------------------------------------------------
# Registry round-trip
# ---------------------------------------------------------------------------


def test_register_and_resolve_custom_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LATHE_GEOMETRY_BACKEND", "lathe.geometry.test_stub_v1")

    def _factory() -> GeometryKernel:
        return ReferenceKernel()  # type: ignore[return-value]

    register_geometry_kernel("lathe.geometry.test_stub_v1", _factory)
    try:
        kernel = resolve_geometry_kernel(None)
        # The custom factory reuses the reference kernel's impl; the test is that
        # the resolver honored the env setting and returned a working kernel.
        assert kernel.name == REFERENCE_KERNEL_ID
    finally:
        # Deregister the stub so later tests see a clean registry surface.
        k_mod._REGISTRY.pop("lathe.geometry.test_stub_v1", None)
