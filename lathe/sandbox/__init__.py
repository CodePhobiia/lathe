"""Process sandbox wrappers (SEC-7, V0.2 P0).

Thin API built on top of :mod:`lathe.subproc`. Each submodule targets a
specific external subprocess (Blender today, more to follow) and layers
per-host resource caps and structured logging on top of the base env
scrubbing + stderr scanning provided by ``run_sandboxed``.
"""

from __future__ import annotations

from .blender import (
    DEFAULT_BLENDER_TIMEOUT_S,
    BlenderSandboxResult,
    run_blender_sandboxed,
)

__all__ = [
    "DEFAULT_BLENDER_TIMEOUT_S",
    "BlenderSandboxResult",
    "run_blender_sandboxed",
]
