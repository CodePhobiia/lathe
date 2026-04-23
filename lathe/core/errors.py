"""Build-stage error classes and diagnostic helpers.

Stage 2.V (Wave 2) moved the authoritative definition of ``BuildError`` into
``lathe/errors.py`` as part of the unified :class:`lathe.errors.LatheError`
hierarchy. This module re-exports it so all existing imports
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


__all__ = ["BuildError", "runtime_stage_error"]
