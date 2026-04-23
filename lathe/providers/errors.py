"""Exception classes for the shape-provider subsystem.

Stage 2.V (see ``plans/10_bugs_errors.md`` Phase 4.5) will re-parent these
under a unified ``LatheError`` hierarchy; keeping them module-local here
until then preserves the existing ``RuntimeError`` MRO for callers that
catch ``RuntimeError``.
"""
from __future__ import annotations

from typing import Any


class ShapeProviderError(RuntimeError):
    def __init__(
        self,
        provider_id: str,
        message: str,
        *,
        code: str = "provider_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.code = code
        self.details = details or {}


class ShapeProviderUnavailable(ShapeProviderError):
    pass


class ShapeProviderExecutionError(ShapeProviderError):
    pass


class ShapeMeshLoadError(ShapeProviderError):
    """Raised when a provider artifact cannot be parsed into a valid mesh.

    Subclass of :class:`ShapeProviderError` so existing ``except
    ShapeProviderError`` branches in
    :func:`lathe.providers.selection.maybe_run_shape_provider` still catch
    these without modification.
    """

    pass
