"""Lathe Python-side stdlib (``lathe.std``).

The user-facing authoring stdlib in `.lth` form lives in the repo-root
``std/`` directory. This Python package mirrors the same idea for
producers that the `.lth` runtime invokes via the build pipeline
(currently: terrain heightfield + erosion solvers under
``lathe.std.terrain``).
"""

from __future__ import annotations
