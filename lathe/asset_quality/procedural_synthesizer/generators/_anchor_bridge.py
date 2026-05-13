"""Direct-anchor-read bridge for generators (Wave 20 / P1).

Per-generator migration to consume ``Anchor.frame`` records directly
(instead of via the legacy ``raw_attributes.position_cm`` bridge).
Once Stage 6 resolves placement bindings, the chosen target anchor's
frame is the authoritative source for the generator's primitive
center + axis.

This bridge lets a generator query ``resolved_anchor_for(node)`` and
get back the chosen anchor's frame directly. Generators that still
read ``position_cm`` continue to work; the bridge is additive.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedAnchorFrame:
    """The chosen target anchor's frame as the source node sees it."""

    transform_world_cm: tuple[float, float, float]
    z_axis: tuple[float, float, float]
    source_anchor_id: str
    target_anchor_id: str
    relation: str


_ANCHOR_RESOLUTION_KEY = "_lathe_anchor_resolution"


def stash_anchor_resolution(
    raw_attrs: Mapping[str, Any], resolved: ResolvedAnchorFrame
) -> dict[str, Any]:
    """Embed a ResolvedAnchorFrame into a mutable raw_attributes dict.

    Stage 5b calls this for every successfully resolved edge so Stage
    6 generators can read the structured record via
    ``resolved_anchor_for(node)``.
    """
    payload = dict(raw_attrs)
    payload[_ANCHOR_RESOLUTION_KEY] = {
        "transform_world_cm": tuple(resolved.transform_world_cm),
        "z_axis": tuple(resolved.z_axis),
        "source_anchor_id": resolved.source_anchor_id,
        "target_anchor_id": resolved.target_anchor_id,
        "relation": resolved.relation,
    }
    # Mirror to legacy position_cm so existing generators still work.
    payload["position_cm"] = tuple(resolved.transform_world_cm)
    return payload


def resolved_anchor_for(node: Any) -> ResolvedAnchorFrame | None:
    """Read the embedded ResolvedAnchorFrame from a typed node, or None.

    Generators that want anchor-direct semantics call this; legacy
    generators ignore it and read ``position_cm`` via the existing
    bridge. Both paths produce the same transform.
    """
    raw = getattr(node, "raw_attributes", None)
    if not isinstance(raw, Mapping):
        return None
    record = raw.get(_ANCHOR_RESOLUTION_KEY)
    if not isinstance(record, Mapping):
        return None
    try:
        return ResolvedAnchorFrame(
            transform_world_cm=tuple(record.get("transform_world_cm", (0.0, 0.0, 0.0))),
            z_axis=tuple(record.get("z_axis", (0.0, 0.0, 1.0))),
            source_anchor_id=str(record.get("source_anchor_id", "")),
            target_anchor_id=str(record.get("target_anchor_id", "")),
            relation=str(record.get("relation", "")),
        )
    except (TypeError, ValueError):
        return None


__all__ = [
    "ResolvedAnchorFrame",
    "stash_anchor_resolution",
    "resolved_anchor_for",
]
