"""Geometry kernel Protocol, registry, and resolver (GEO-2).

The kernel is the single boolean/CSG backend the shape stage talks to.
Two kernels ship in-tree: ``lathe.geometry.manifold_v1`` (Google
manifold3d, watertight by construction) and ``lathe.geometry.reference_v1``
(trimesh + SDF-voxel fallback). Third parties register their own kernels
via the ``lathe.geometry_kernels`` entry-point group.

Selection precedence (highest to lowest):
  1. ``LATHE_GEOMETRY_BACKEND`` environment variable.
  2. ``runtime_config["runtime"]["geometry"]["backend"]``.
  3. Default: ``lathe.geometry.manifold_v1`` when manifold3d is
     importable, else ``lathe.geometry.reference_v1``.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable
from importlib import import_module
from importlib.metadata import entry_points
from typing import Any, Protocol, runtime_checkable

import trimesh

from ..logging_utils import info as log_info
from ..logging_utils import warning as log_warning

_LOGGER = logging.getLogger(__name__)

MANIFOLD_KERNEL_ID = "lathe.geometry.manifold_v1"
REFERENCE_KERNEL_ID = "lathe.geometry.reference_v1"


class GeometryKernelUnavailableError(RuntimeError):
    """Raised when a named kernel cannot be instantiated (deps missing)."""

    def __init__(
        self,
        message: str | None = None,
        *,
        kernel: str | None = None,
        source: str | None = None,
    ) -> None:
        """Build an unavailable-kernel message."""
        if message is None and kernel is not None and source is not None:
            message = (
                f"geometry kernel {kernel!r} requested via {source} but its backing library is not importable"
            )
        elif message is None:
            message = (
                "no geometry kernel could be instantiated; reference kernel factory failed "
                "(this should be unreachable - the reference kernel depends only on trimesh)"
            )
        super().__init__(message)


GeometryKernelUnavailable = GeometryKernelUnavailableError


class UnknownGeometryKernelError(KeyError):
    """Raised when the requested kernel name has no registered factory."""

    def __init__(self, source: str, kernel: str, registered: Iterable[str]) -> None:
        """Build an unknown-kernel message with the known registry entries."""
        super().__init__(
            f"{source}={kernel!r} is not a registered kernel. Registered: {sorted(registered)!r}"
        )


UnknownGeometryKernel = UnknownGeometryKernelError


@runtime_checkable
class GeometryKernel(Protocol):
    """Stable CSG surface the shape stage depends on.

    Implementations wrap a concrete boolean backend (manifold3d,
    trimesh, future candidates). Handles are opaque — the only
    guaranteed way to cross back into pipeline code is
    :meth:`to_trimesh`.
    """

    name: str
    version: str

    def probe(self) -> dict[str, Any]:
        """Availability + capability metadata. Must not raise."""

    def build_primitive(self, kind: str, **params: Any) -> Any:
        """Construct a primitive handle (``box``, ``cylinder``, ``sphere``)."""

    def union(self, a: Any, b: Any) -> Any:
        """Boolean union."""

    def difference(self, a: Any, b: Any) -> Any:
        r"""Boolean difference (``a \\ b``)."""

    def intersection(self, a: Any, b: Any) -> Any:
        """Boolean intersection."""

    def hull(self, meshes: Iterable[Any]) -> Any:
        """Convex hull of the supplied handles."""

    def to_trimesh(self, handle: Any) -> trimesh.Trimesh:
        """Convert an opaque handle into a :class:`trimesh.Trimesh`."""

    def is_watertight(self, handle: Any) -> bool:
        """Watertightness probe."""

    def body_count(self, handle: Any) -> int:
        """Disjoint-body count."""


KernelFactory = Callable[[], GeometryKernel]


_REGISTRY: dict[str, KernelFactory] = {}
_ENTRY_POINTS_LOADED: set[str] = set()


def register_geometry_kernel(name: str, factory: KernelFactory) -> None:
    """Register (or replace) a kernel factory under ``name``.

    The factory is a zero-arg callable returning a
    :class:`GeometryKernel` instance. It may raise
    :class:`GeometryKernelUnavailable` if its backing deps are missing;
    the resolver treats that as a fallback trigger.
    """
    _REGISTRY[name] = factory


def list_registered_kernels() -> list[str]:
    """Return names of all currently registered kernels, sorted."""
    _ensure_builtins_registered()
    _load_entry_point_kernels()
    return sorted(_REGISTRY)


def _ensure_builtins_registered() -> None:
    """Register the two built-in kernels lazily.

    Deferred import avoids a cycle with kernel modules that import this
    module at top level for the Protocol.
    """
    if MANIFOLD_KERNEL_ID not in _REGISTRY:
        _manifold_mod = import_module(".manifold_kernel", __package__)

        register_geometry_kernel(MANIFOLD_KERNEL_ID, _manifold_mod.manifold_kernel)
    if REFERENCE_KERNEL_ID not in _REGISTRY:
        _reference_mod = import_module(".reference_kernel", __package__)

        register_geometry_kernel(REFERENCE_KERNEL_ID, _reference_mod.reference_kernel)


def _load_entry_point_kernels() -> None:
    """Import any third-party kernels exposed through entry points.

    Runs once per process. Failures are logged and ignored so a broken
    plugin cannot take down the resolver.
    """
    if _ENTRY_POINTS_LOADED:
        return
    _ENTRY_POINTS_LOADED.add("loaded")
    try:
        eps = entry_points(group="lathe.geometry_kernels")
    except TypeError:
        # Python <3.10 entry_points() compatibility guard; Lathe targets 3.11+
        # but keep the defensive branch for forward-compat with future stdlib tweaks.
        eps = []
    for ep in eps:
        if ep.name in _REGISTRY:
            continue
        try:
            factory = ep.load()
        except (ImportError, AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
            log_warning(
                _LOGGER,
                "lathe.geometry.kernel.plugin_load_failed",
                "geometry kernel plugin {entry_point!r} failed to load: {error}",
                entry_point=ep.name,
                error=exc,
            )
            continue
        register_geometry_kernel(ep.name, factory)


def _instantiate(name: str) -> GeometryKernel | None:
    factory = _REGISTRY.get(name)
    if factory is None:
        return None
    try:
        return factory()
    except GeometryKernelUnavailable as exc:
        log_info(
            _LOGGER,
            "lathe.geometry.kernel.unavailable",
            "geometry kernel {kernel} unavailable: {error}",
            kernel=name,
            error=exc,
        )
        return None


def resolve_geometry_kernel(
    runtime_config: dict[str, Any] | None = None,
    *,
    logger: logging.Logger | None = None,
) -> GeometryKernel:
    """Select a geometry kernel honoring env > runtime_config > default.

    Args:
        runtime_config: merged runtime config mapping (may be ``None``).
            Read from ``runtime_config["runtime"]["geometry"]["backend"]``
            if present.
        logger: optional logger for fallback-chain messages. Falls back to
            this module's logger when ``None``.

    Returns:
        The resolved :class:`GeometryKernel`. Falls back to the reference
        kernel when the preferred kernel's backing library is missing.

    Raises:
        UnknownGeometryKernel: when an explicitly named kernel (via env
            or runtime_config) is not registered.
        GeometryKernelUnavailable: when the resolver cannot produce any
            working kernel at all (should be unreachable in practice —
            the reference kernel is pure trimesh and always available).
    """
    log = logger or _LOGGER
    _ensure_builtins_registered()
    _load_entry_point_kernels()

    env_choice = os.environ.get("LATHE_GEOMETRY_BACKEND")
    if env_choice:
        env_choice = env_choice.strip()
        if env_choice in {"reference", "reference_kernel"}:
            env_choice = REFERENCE_KERNEL_ID
        elif env_choice in {"manifold", "manifold3d"}:
            env_choice = MANIFOLD_KERNEL_ID
        if env_choice not in _REGISTRY:
            raise UnknownGeometryKernel(
                "LATHE_GEOMETRY_BACKEND",
                env_choice,
                _REGISTRY,
            )
        kernel = _instantiate(env_choice)
        if kernel is None:
            raise GeometryKernelUnavailable(
                kernel=env_choice,
                source="LATHE_GEOMETRY_BACKEND",
            )
        log_info(
            log,
            "lathe.geometry.kernel.selected_env",
            "geometry kernel selected via env LATHE_GEOMETRY_BACKEND: {kernel}",
            kernel=env_choice,
        )
        return kernel

    configured = None
    if runtime_config:
        geo_cfg = (runtime_config.get("runtime") or {}).get("geometry") or {}
        configured = geo_cfg.get("backend")
    if configured:
        if configured not in _REGISTRY:
            raise UnknownGeometryKernel(
                "runtime_config.runtime.geometry.backend",
                configured,
                _REGISTRY,
            )
        kernel = _instantiate(configured)
        if kernel is None:
            raise GeometryKernelUnavailable(
                kernel=configured,
                source="runtime_config",
            )
        log_info(
            log,
            "lathe.geometry.kernel.selected_runtime_config",
            "geometry kernel selected via runtime_config: {kernel}",
            kernel=configured,
        )
        return kernel

    # Default: manifold when available, reference otherwise.
    preferred = _instantiate(MANIFOLD_KERNEL_ID)
    if preferred is not None:
        return preferred
    log_info(
        log,
        "lathe.geometry.kernel.default_fallback",
        "geometry kernel {preferred} unavailable (manifold3d not importable); falling back to {fallback}",
        preferred=MANIFOLD_KERNEL_ID,
        fallback=REFERENCE_KERNEL_ID,
    )
    fallback = _instantiate(REFERENCE_KERNEL_ID)
    if fallback is None:
        raise GeometryKernelUnavailable()
    return fallback
