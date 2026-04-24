"""Pluggable stage adapters registered against backend IDs.

Adapters are the concrete runtime bodies that honor a declared backend
contract (see ``lathe/backends.py``). The core runtime in
``lathe/core/stages/`` dispatches by backend ID metadata and falls back
to deterministic reference paths when a requested adapter is
unavailable.

This package is intentionally lightweight -- adapters may register
themselves as side-effect imports or be referenced by module path.

See :mod:`lathe.adapters.blender_subdiv` for the first non-default
topology adapter plugged in via the BL-34 second-stack proof.
"""

from __future__ import annotations

from . import blender_subdiv  # noqa: F401  -- register side effects

__all__ = ["blender_subdiv"]
