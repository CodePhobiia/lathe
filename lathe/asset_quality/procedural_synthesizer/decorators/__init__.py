"""Procedural synthesizer edge decorators — one subpackage per domain.

Like generators, decorators register through their owning domain's
DomainExtension.
"""

from __future__ import annotations

# Built-in domain decorators register via the corresponding domain's
# __init__ module in ``generators/<domain>``.
from . import hard_surface  # noqa: F401


__all__: list[str] = []
