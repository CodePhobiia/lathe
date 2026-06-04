"""Cross-generator helper: thread ``position_cm`` from raw_attributes into kernel ``center`` params.

The auto-graph (see ``lathe.shape.procedural_program_path._auto_graph_from_parts``)
injects a heuristic ``position_cm: (x, y, z)`` into the raw attribute
mapping of each non-primary node so visible secondary features land
on the body's bounding faces rather than buried at the origin.

Typed attribute dataclasses don't model ``position_cm`` (it is a
purely-spatial concern, orthogonal to the per-NODE_TYPE schema), so
generators read it via ``node.raw_attributes`` and pass it through
this helper. The kernel primitive builders already accept ``center``
on every supported primitive (cube, cylinder, sphere, capsule, box,
torus, etc.; see ``lathe.adapters.manifold_kernel``), so this is a
single-line wiring change per generator at the ShapeOp params dict.

Call site::

    params = {...}
    _apply_position_cm(node, params)  # mutates params in place

If no ``position_cm`` is present, the params dict is unchanged and
the primitive ends up at the kernel default (origin).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _apply_position_cm(node: Any, params: dict[str, Any]) -> None:
    """Add ``center`` to ``params`` if the node carries a ``position_cm``.

    Mutates ``params`` in place. Idempotent — if ``params`` already
    has an explicit ``center`` (from the generator's own internal
    placement logic), it is left untouched.
    """
    if "center" in params:
        return
    raw = getattr(node, "raw_attributes", None)
    if not isinstance(raw, Mapping):
        return
    pos = raw.get("position_cm")
    if pos is None:
        return
    try:
        coords = tuple(float(v) for v in pos)
    except (TypeError, ValueError):
        return
    if len(coords) != 3:
        return
    params["center"] = coords


__all__ = ["_apply_position_cm"]
