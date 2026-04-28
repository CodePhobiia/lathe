"""Unified Lathe exception hierarchy.

All Lathe-originating exceptions derive from :class:`LatheError`. Historical
per-module error classes (``BuildError`` in ``lathe/core/errors.py``,
``ShapeProviderError`` in ``lathe/providers/errors.py``, ``LatheParseError``
in ``lathe/parser/grammar.py``, etc.) are re-exported from their original
locations for backwards compatibility; the authoritative definitions live
here.

See ``plans/01_code_quality.md`` Phase 3 and
``plans/10_bugs_errors.md`` Phase 4.5 for context.

Hierarchy
---------

::

    LatheError(Exception)
    |-- LatheConfigError
    |   `-- RuntimeConfigError            (also RuntimeError for isinstance compat)
    |-- LatheParseError
    |   `-- DuplicateFieldError
    |-- NormalizationError
    |-- ResolutionError
    |   `-- UnresolvedNameError
    |-- CheckerError                      (reserved)
    |-- BackendError
    |   |-- BackendResolutionError
    |   |-- ShapeProviderError            (also RuntimeError for isinstance compat)
    |   |   |-- ShapeProviderUnavailable
    |   |   |-- ShapeProviderExecutionError
    |   |   `-- ShapeMeshLoadError
    |   |-- TopologyAdapterError          (reserved)
    |   `-- UVAdapterError                (reserved)
    |-- LatheExecutionError
    |   |-- BuildError
    |   `-- BlenderExecutionError
    |-- PatchAPIError
    `-- ContractViolation                 (reserved)

Multiple-inheritance notes
--------------------------

``ShapeProviderError`` inherits from both :class:`LatheError` and
:class:`RuntimeError` so existing ``except RuntimeError`` call sites keep
working. ``RuntimeConfigError`` does the same — historically it subclassed
``RuntimeError`` directly and we preserve that MRO.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class LatheError(Exception):
    """Base class for every Lathe-originating exception."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class LatheConfigError(LatheError):
    """Raised when Lathe configuration (runtime config, env, CLI flags) is invalid."""


class RuntimeConfigError(LatheConfigError, RuntimeError):
    """Raised when a user-supplied runtime config is malformed or fails schema validation.

    Inherits from :class:`RuntimeError` in addition to :class:`LatheConfigError`
    so existing ``except RuntimeError`` call sites continue to catch it.
    """


# ---------------------------------------------------------------------------
# Parse / normalize / resolve / check
# ---------------------------------------------------------------------------


class LatheParseError(LatheError):
    """Raised when ``.lth`` source cannot be parsed."""


class DuplicateFieldError(LatheParseError):
    """Raised when a block assigns the same field twice."""

    def __init__(self, path: str, context: str) -> None:
        super().__init__(f"Duplicate assignment to '{path}' in {context} block")
        self.path = path
        self.context = context


class NormalizationError(LatheError):
    """Raised when the normalizer rejects a program that the parser accepted."""


class ResolutionError(LatheError):
    """Raised when the resolver cannot materialize a program."""


class UnresolvedNameError(ResolutionError):
    """Raised when a required named declaration cannot be resolved."""


class CheckerError(LatheError):
    """Reserved for semantic-checker failures (Plan 03 contract work)."""


# ---------------------------------------------------------------------------
# Backend / provider
# ---------------------------------------------------------------------------


class BackendError(LatheError):
    """Base class for backend/provider failures."""


class BackendResolutionError(BackendError):
    """Raised when a required backend cannot be resolved for a build stage."""


class ShapeProviderError(BackendError, RuntimeError):
    """Raised for any shape-provider failure.

    Inherits from :class:`RuntimeError` in addition to :class:`BackendError`
    so existing ``except RuntimeError`` call sites continue to catch it.
    """

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
    """Raised when a shape provider's prerequisites (endpoint, deps, model) are missing."""


class ShapeProviderExecutionError(ShapeProviderError):
    """Raised when a shape provider fails at runtime despite being available."""


class ShapeMeshLoadError(ShapeProviderError):
    """Raised when a provider artifact cannot be parsed into a valid mesh.

    Subclass of :class:`ShapeProviderError` so existing
    ``except ShapeProviderError`` branches still catch these without modification.
    """


class ShapeBundleError(BackendError):
    """Raised when the shape-stage bundle fails a gate check (e.g. strict watertightness)."""

    def __init__(self, code: str, details: dict[str, Any] | None = None) -> None:
        details = details or {}
        message = f"shape bundle gate failed [{code}]: {details}"
        super().__init__(message)
        self.code = code
        self.details = details


class TopologyAdapterError(BackendError):
    """Reserved for topology-adapter failures (Blender, future adapters)."""


class UVAdapterError(BackendError):
    """Reserved for UV-adapter failures (xatlas, future adapters)."""


# ---------------------------------------------------------------------------
# Execution (runtime)
# ---------------------------------------------------------------------------


class LatheExecutionError(LatheError):
    """Base class for failures that happen while executing the build pipeline."""


class BuildError(LatheExecutionError):
    """Raised from build stages with a payload of diagnostics."""

    def __init__(self, message: str, diagnostics: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or []


class BlenderExecutionError(LatheExecutionError):
    """Raised when a Blender subprocess exits non-zero or signals an error on stderr."""

    def __init__(
        self,
        message: str,
        *,
        blender_path: str | None = None,
        returncode: int | None = None,
        stderr_tail: str | None = None,
        matched_patterns: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.blender_path = blender_path
        self.returncode = returncode
        self.stderr_tail = stderr_tail
        self.matched_patterns = list(matched_patterns or [])


# ---------------------------------------------------------------------------
# Patch / contract
# ---------------------------------------------------------------------------


class PatchAPIError(LatheError):
    """Raised when a programmatic patch against a Lathe program is invalid."""


class ContractViolation(LatheError):
    """Reserved for Plan 03 contract-test violations."""


__all__ = [
    "BackendError",
    "BackendResolutionError",
    "BlenderExecutionError",
    "BuildError",
    "CheckerError",
    "ContractViolation",
    "DuplicateFieldError",
    "LatheConfigError",
    "LatheError",
    "LatheExecutionError",
    "LatheParseError",
    "NormalizationError",
    "PatchAPIError",
    "ResolutionError",
    "RuntimeConfigError",
    "ShapeBundleError",
    "ShapeMeshLoadError",
    "ShapeProviderError",
    "ShapeProviderExecutionError",
    "ShapeProviderUnavailable",
    "TopologyAdapterError",
    "UVAdapterError",
    "UnresolvedNameError",
]
