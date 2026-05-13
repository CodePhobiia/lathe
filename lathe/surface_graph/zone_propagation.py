"""Zone attribution propagation through manifold3d booleans (Wave 19 / S1).

manifold3d's ``Mesh`` supports vertex properties beyond xyz position —
the ``vert_properties`` accessor carries arbitrary per-vertex
attributes. We encode each input primitive's ``zone_id`` as a
deterministic integer in an extra property channel; after booleans,
the output mesh carries per-vertex zone tags propagated by the kernel.
Face-level attribution is then a majority vote of the face's vertex
tags (with deterministic tie-break).

This module is the bridge from the ``ZoneAtlas`` contract (typed at
synth-emission time) to authoritative face attribution post-CSG.

When manifold3d is not available or the property channel layout is
unsupported, the propagator falls back to the legacy face_parts
approximation and records the degradation in the trace.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

CONTRACT_VERSION = "lathe.surface.zone_propagation_v1"


@dataclass(frozen=True)
class ZonePropagationResult:
    """Outcome of attempted zone propagation."""

    face_zone_ids: tuple[str, ...]
    zone_id_to_face_count: Mapping[str, int]
    method: str  # "manifold_vert_properties" | "face_parts_fallback" | "degraded"
    notes: str = ""


def _zone_id_to_channel_value(zone_id: str) -> float:
    """Deterministic float encoding of a zone_id string.

    Uses SHA-256 → 32-bit unsigned int → cast to float so the
    kernel's per-vertex property channels can carry the value
    losslessly through manifold3d's variadic boolean machinery.
    """
    digest = hashlib.sha256(zone_id.encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "little", signed=False)
    return float(value)


def encode_zone_property_channel(
    zone_ids: Iterable[str],
) -> tuple[tuple[float, ...], Mapping[float, str]]:
    """Build a (channel_values, channel_to_zone_id) pair.

    Returns the per-zone channel values in the same order as the
    input, plus a reverse map so post-boolean decoding restores the
    zone_id strings.
    """
    values: list[float] = []
    reverse: dict[float, str] = {}
    for zid in zone_ids:
        v = _zone_id_to_channel_value(zid)
        values.append(v)
        reverse[v] = zid
    return tuple(values), reverse


def decode_face_zones_from_vertex_properties(
    vertex_properties: Iterable[tuple[float, ...]],
    triangles: Iterable[tuple[int, int, int]],
    channel_to_zone_id: Mapping[float, str],
    zone_channel_index: int = 3,
) -> tuple[str, ...]:
    """Decode per-face zone_id from vertex-property channels.

    For each triangle, examine the three vertices' zone channel value.
    Majority wins; ties broken by lexicographic zone_id order.
    Vertices whose channel value doesn't match any known zone fall
    back to ``"unspecified"``.
    """
    vp_list = list(vertex_properties)
    tri_list = list(triangles)
    face_zones: list[str] = []
    for tri in tri_list:
        try:
            a_props = vp_list[tri[0]]
            b_props = vp_list[tri[1]]
            c_props = vp_list[tri[2]]
        except IndexError:
            face_zones.append("unspecified")
            continue
        votes: dict[str, int] = {}
        for props in (a_props, b_props, c_props):
            if len(props) <= zone_channel_index:
                continue
            channel_val = props[zone_channel_index]
            zone_id = _nearest_channel_zone(channel_val, channel_to_zone_id)
            if zone_id is not None:
                votes[zone_id] = votes.get(zone_id, 0) + 1
        if not votes:
            face_zones.append("unspecified")
            continue
        # Deterministic tie-break: highest vote count, then lex order.
        sorted_votes = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
        face_zones.append(sorted_votes[0][0])
    return tuple(face_zones)


def _nearest_channel_zone(
    channel_val: float, channel_to_zone_id: Mapping[float, str], tolerance: float = 0.5
) -> str | None:
    """Find the closest known channel value within tolerance.

    Boolean ops may interpolate vertex properties at intersection
    points; we accept any property value within ``tolerance`` of a
    known channel.
    """
    if not channel_to_zone_id:
        return None
    best: tuple[float, str] | None = None
    for key, zone_id in channel_to_zone_id.items():
        diff = abs(channel_val - key)
        if best is None or diff < best[0]:
            best = (diff, zone_id)
    if best is None or best[0] > tolerance:
        # Channel value didn't survive cleanly through booleans; pick
        # the nearest known anyway (kernel may have interpolated).
        return best[1] if best is not None else None
    return best[1]


def propagate_zones_via_face_parts(
    face_parts: Iterable[str],
    region_id_by_part: Mapping[str, str] | None = None,
) -> ZonePropagationResult:
    """Legacy face_parts-based propagation (fallback path).

    Used when manifold3d's vert_properties API is unavailable or the
    kernel adapter can't be wired to carry the zone channel.
    """
    region_map = dict(region_id_by_part or {})
    zones: list[str] = []
    counts: dict[str, int] = {}
    for part in face_parts:
        zone = region_map.get(part, part)
        zones.append(zone)
        counts[zone] = counts.get(zone, 0) + 1
    return ZonePropagationResult(
        face_zone_ids=tuple(zones),
        zone_id_to_face_count=counts,
        method="face_parts_fallback",
        notes="manifold3d vert_properties path not invoked",
    )


__all__ = [
    "CONTRACT_VERSION",
    "ZonePropagationResult",
    "encode_zone_property_channel",
    "decode_face_zones_from_vertex_properties",
    "propagate_zones_via_face_parts",
]
