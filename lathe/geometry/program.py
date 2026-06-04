"""Compatibility shim for the renamed kernel-program module.

The canonical module is :mod:`lathe.geometry.kernel_program`. This file keeps
older direct imports such as ``lathe.geometry.program`` working while callers
migrate to the new name.
"""

from __future__ import annotations

from . import kernel_program as _kernel_program
from .kernel_program import *  # noqa: F403

__all__ = [name for name in dir(_kernel_program) if not name.startswith("__")]
globals().update({name: getattr(_kernel_program, name) for name in __all__})
