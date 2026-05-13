"""Contract test: strict geometry mode refuses silent Manifold fallback.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §5.3 Lane A priority task 4 and §5.4 acceptance:

> Strict geometry mode test: a hero-quality claim with strict mode
> on, where Manifold falls back, must surface a failure rather than
> certify.

Strict mode is opt-in via two channels:

  1. Env var: ``LATHE_STRICT_GEOMETRY=1``
  2. Runtime config: ``runtime.geometry.strict_mode = True``

When on, ``resolve_geometry_kernel`` refuses to silently fall back
from Manifold to the reference kernel — instead it raises
``StrictGeometryModeError`` so downstream certification cannot stamp
a hero-quality claim on output produced by the wrong backend.

This test simulates Manifold unavailability by monkeypatching the
Manifold factory to always return None (the "unavailable" signal the
resolver already understands). With strict mode **off**, the resolver
silently falls back to the reference kernel — the existing behavior.
With strict mode **on** (via either channel), the resolver raises
``StrictGeometryModeError`` naming the attempted/fallback kernels
and the source that enabled strict mode.
"""

from __future__ import annotations

import pytest
from lathe.geometry.kernel import (
    _REGISTRY,
    MANIFOLD_KERNEL_ID,
    REFERENCE_KERNEL_ID,
    STRICT_GEOMETRY_ENV_VAR,
    StrictGeometryModeError,
    resolve_geometry_kernel,
)


@pytest.fixture
def manifold_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force Manifold factory to report unavailable for the duration of a test.

    Substitutes the Manifold factory with one that returns ``None`` —
    the signal ``_instantiate`` already maps to "unavailable" and that
    triggers the resolver's fallback branch. The fixture is the seam
    the strict-mode check fires through.
    """
    from lathe.geometry import kernel as kernel_mod

    kernel_mod._ensure_builtins_registered()
    kernel_mod._load_entry_point_kernels()

    def _unavailable_factory() -> object:
        raise kernel_mod.GeometryKernelUnavailable(
            "test fixture forcing manifold unavailable"
        )

    monkeypatch.setitem(_REGISTRY, MANIFOLD_KERNEL_ID, _unavailable_factory)


@pytest.fixture
def strict_mode_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the env-var channel is off so a single source drives the test."""
    monkeypatch.delenv(STRICT_GEOMETRY_ENV_VAR, raising=False)


def test_resolver_falls_back_when_strict_mode_off(
    manifold_unavailable: None,
    strict_mode_disabled: None,
) -> None:
    """Without strict mode, the resolver silently falls back to reference.

    Pins existing behavior so this test catches any accidental
    side-effect of strict-mode wiring.
    """
    kernel = resolve_geometry_kernel()
    assert kernel.name == REFERENCE_KERNEL_ID, (
        f"strict mode is off; resolver should fall back to "
        f"{REFERENCE_KERNEL_ID!r} but returned {kernel.name!r}"
    )


def test_resolver_raises_on_env_strict_mode_when_manifold_unavailable(
    manifold_unavailable: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LATHE_STRICT_GEOMETRY=1 + Manifold unavailable → StrictGeometryModeError."""
    monkeypatch.setenv(STRICT_GEOMETRY_ENV_VAR, "1")

    with pytest.raises(StrictGeometryModeError) as excinfo:
        resolve_geometry_kernel()

    err = excinfo.value
    assert err.attempted == MANIFOLD_KERNEL_ID
    assert err.fallback == REFERENCE_KERNEL_ID
    assert err.source == f"env:{STRICT_GEOMETRY_ENV_VAR}"
    assert "manifold3d not importable" in err.reason


def test_resolver_raises_on_runtime_config_strict_mode_when_manifold_unavailable(
    manifold_unavailable: None,
    strict_mode_disabled: None,
) -> None:
    """runtime.geometry.strict_mode=True + Manifold unavailable → StrictGeometryModeError."""
    runtime_config = {"runtime": {"geometry": {"strict_mode": True}}}

    with pytest.raises(StrictGeometryModeError) as excinfo:
        resolve_geometry_kernel(runtime_config)

    err = excinfo.value
    assert err.attempted == MANIFOLD_KERNEL_ID
    assert err.fallback == REFERENCE_KERNEL_ID
    assert err.source == "runtime_config.runtime.geometry.strict_mode"


def test_resolver_strict_mode_truthy_string_accepted(
    manifold_unavailable: None,
    strict_mode_disabled: None,
) -> None:
    """Truthy string values (``"true"``, ``"yes"``, ``"on"``) also enable strict mode.

    Catches config files that round-trip booleans through YAML/JSON as
    strings — strict_mode = "true" must behave identically to True.
    """
    for raw in ("true", "yes", "on", "1"):
        runtime_config = {"runtime": {"geometry": {"strict_mode": raw}}}
        with pytest.raises(StrictGeometryModeError):
            resolve_geometry_kernel(runtime_config)


def test_resolver_strict_mode_falsy_values_disable(
    manifold_unavailable: None,
    strict_mode_disabled: None,
) -> None:
    """Falsy / unset strict_mode values keep the silent-fallback behavior.

    Empty string, ``"false"``, ``False``, and missing keys all leave
    strict mode off so the resolver returns the reference fallback.
    """
    for falsy in (False, "false", "no", "off", "", None):
        runtime_config: dict = {"runtime": {"geometry": {"strict_mode": falsy}}}
        kernel = resolve_geometry_kernel(runtime_config)
        assert kernel.name == REFERENCE_KERNEL_ID, (
            f"strict_mode={falsy!r} should keep strict mode off, "
            f"but resolver raised or returned {kernel.name!r}"
        )


def test_resolver_strict_mode_inert_when_manifold_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict mode never fires when Manifold is actually available.

    Asserts strict mode is **exclusively** a guard against silent
    fallback — it does not block valid Manifold selection.
    """
    from lathe.adapters.manifold_kernel import manifold_available

    if not manifold_available():
        pytest.skip("manifold3d not importable; nothing to assert about its presence")

    monkeypatch.setenv(STRICT_GEOMETRY_ENV_VAR, "1")
    kernel = resolve_geometry_kernel()
    assert kernel.name == MANIFOLD_KERNEL_ID, (
        f"strict mode incorrectly diverted from {MANIFOLD_KERNEL_ID!r} to "
        f"{kernel.name!r} despite Manifold being importable"
    )


def test_strict_geometry_mode_error_message_names_both_kernels() -> None:
    """The error message has enough specificity to be actionable.

    The user-facing string must name both kernels and the source so
    the reader can find the right knob (env var or runtime config) to
    flip without guessing.
    """
    err = StrictGeometryModeError(
        attempted=MANIFOLD_KERNEL_ID,
        fallback=REFERENCE_KERNEL_ID,
        reason="manifold3d not importable",
        source="env:LATHE_STRICT_GEOMETRY",
    )
    message = str(err)
    assert MANIFOLD_KERNEL_ID in message
    assert REFERENCE_KERNEL_ID in message
    assert "env:LATHE_STRICT_GEOMETRY" in message
    assert "manifold3d not importable" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
