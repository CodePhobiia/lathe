"""Subdivision scheme enumeration."""

from __future__ import annotations

from enum import Enum


class SubdivisionScheme(str, Enum):
    """Supported subdivision schemes."""

    CATMULL_CLARK = "catmull_clark"
    LOOP = "loop"

    @classmethod
    def from_text(cls, text: str) -> "SubdivisionScheme":
        """Parse a scheme name from authored text."""
        normalised = text.lower().strip().replace("-", "_").replace(" ", "_")
        aliases = {
            "catmull_clark": cls.CATMULL_CLARK,
            "catmullclark": cls.CATMULL_CLARK,
            "cc": cls.CATMULL_CLARK,
            "loop": cls.LOOP,
            "loop_subdivision": cls.LOOP,
        }
        if normalised not in aliases:
            raise ValueError(f"unknown subdivision scheme: {text!r}")
        return aliases[normalised]


def parse_scheme(value: SubdivisionScheme | str) -> SubdivisionScheme:
    """Coerce ``value`` to a :class:`SubdivisionScheme`."""
    if isinstance(value, SubdivisionScheme):
        return value
    return SubdivisionScheme.from_text(str(value))


__all__ = ["SubdivisionScheme", "parse_scheme"]
