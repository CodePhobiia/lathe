"""Publish stage step body — scaffolded only.

The ``publish`` stage is not run as part of ``BuildExecutor.build`` today;
Plan 08 Phase 1 will flesh out the publish runner. This module exists so the
per-stage directory covers every entry of ``STAGE_ORDER`` even though the
dispatcher currently skips it.
"""

from __future__ import annotations

from typing import Any


def run(executor: Any) -> dict[str, Any]:  # pragma: no cover - scaffolded
    """Placeholder for the publish runner (Plan 08 Phase 1)."""
    raise NotImplementedError("publish stage is scaffolded; Plan 08 Phase 1 will implement it")
