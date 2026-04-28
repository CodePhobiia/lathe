"""Build-stage error classes and diagnostic helpers.

The authoritative definition of ``BuildError`` lives in ``lathe/errors.py``
as part of the unified :class:`lathe.errors.LatheError` hierarchy. This
module re-exports it so all existing imports
(``from lathe.core.errors import BuildError`` and — through the
``lathe.executor`` shim — ``from lathe.executor import BuildError``) keep
working.
"""

from __future__ import annotations

from typing import Any

from ..errors import BuildError  # re-export — authoritative definition lives in lathe/errors.py


def runtime_stage_error(
    asset_name: str,
    stage: str,
    backend_id: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> BuildError:
    """Runtime stage error.

    Args:
        asset_name: asset_name argument.
        stage: stage argument.
        backend_id: backend_id argument.
        message: message argument.
        details: details argument.

    Returns:
        The result.
    """
    return BuildError(
        message,
        diagnostics=[
            {
                "code": "L5101",
                "name": "runtime_stage_error",
                "severity": "error",
                "phase": "build",
                "asset": asset_name,
                "stage": stage,
                "path": f"build.{stage}.backend",
                "message": message,
                "details": {**(details or {}), "backend_id": backend_id},
                "suggested_repairs": [],
            }
        ],
    )


def contract_version_stage_error(
    asset_name: str,
    stage: str,
    backend_id: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> BuildError:
    """Return a build error for an unsupported stage/bundle contract version."""
    return BuildError(
        message,
        diagnostics=[
            {
                "code": "L5102",
                "name": "unsupported_stage_contract_version",
                "severity": "error",
                "phase": "build",
                "asset": asset_name,
                "stage": stage,
                "path": f"stages.{stage}.bundle",
                "message": message,
                "details": {**(details or {}), "backend_id": backend_id},
                "suggested_repairs": [],
            }
        ],
    )


def shape_handoff_contract_error(
    asset_name: str,
    backend_id: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> BuildError:
    """Return a build error for an unsupported shape handoff contract version."""
    return BuildError(
        message,
        diagnostics=[
            {
                "code": "L5103",
                "name": "unsupported_shape_handoff_contract_version",
                "severity": "error",
                "phase": "build",
                "asset": asset_name,
                "stage": "shape",
                "path": "build.shape.backend",
                "message": message,
                "details": {**(details or {}), "backend_id": backend_id},
                "suggested_repairs": [],
            }
        ],
    )


__all__ = [
    "BuildError",
    "contract_version_stage_error",
    "runtime_stage_error",
    "shape_handoff_contract_error",
]
