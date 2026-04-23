"""Build-stage error classes and diagnostic helpers.

Extracted from ``lathe/executor.py`` during Stage 2.IV. ``BuildError`` is
re-exported from ``lathe.executor`` so all existing imports continue to work.
"""

from __future__ import annotations

from typing import Any


class BuildError(Exception):
    def __init__(self, message: str, diagnostics: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or []


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
