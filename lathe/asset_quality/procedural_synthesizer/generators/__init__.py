"""Procedural synthesizer generators — one subpackage per domain.

Importing this package triggers registration of every built-in
domain. Phase 3 domains (vegetation, terrain, WFC, CGA, F-Rep/SDF,
scatter, animation) add their subpackage here and the same import-
time registration pattern applies.
"""

from __future__ import annotations

# Built-in domains register at import time via their __init__ modules.
from . import hard_surface  # noqa: F401

__all__: list[str] = []
