"""Hard-surface edge decorators.

Decorators register themselves through the hard-surface
DomainExtension in ``generators/hard_surface/__init__.py``. This
module only exports the decorator symbols; registration happens via
the domain extension.
"""

from __future__ import annotations

from . import (  # noqa: F401
    aligned_with,
    attached_to,
    cuts,
    inset_into,
    mirrors,
    supports,
    wraps_around,
)

__all__: list[str] = []
