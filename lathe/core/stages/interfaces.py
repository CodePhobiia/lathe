"""Interfaces stage step body (typed sockets + typed pivots + legacy anchors).

Extracted from ``lathe/executor.py`` during Stage 2.IV. Extended for STAGE-3/4/5
(V0.2 E3) with typed sockets, typed pivots, AABBs, and 4x4 transforms.
"""

from __future__ import annotations

import warnings
from typing import Any

from lathe.interface_connections import resolve_interface_connections
from lathe.interface_entries import coerce_interface_entry

from ..common import dump_json

SOCKET_TYPES = (
    "attach",
    "hand",
    "mount",
    "port",
    "attachment_point",
    "hinge",
    "door",
    "slot",
    "grip",
    "muzzle",
    "rail",
)

PIVOT_TYPES = (
    "world",
    "center",
    "bottom",
    "contact",
    "hand_hold",
    "sight_line",
)

DEFAULT_SOCKET_TYPE = "attach"
DEFAULT_PIVOT_TYPE = "center"


def _identity_transform() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _translation_transform(tx: float, ty: float, tz: float) -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, float(tx)],
        [0.0, 1.0, 0.0, float(ty)],
        [0.0, 0.0, 1.0, float(tz)],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _round_vec3(v: list[float]) -> list[float]:
    return [round(float(v[0]), 6), round(float(v[1]), 6), round(float(v[2]), 6)]


def _round_transform(m: list[list[float]]) -> list[list[float]]:
    return [[round(float(m[r][c]), 6) for c in range(4)] for r in range(4)]


def _aabb_around(pos: list[float], radius: float) -> dict[str, list[float]]:
    x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
    return {
        "min": [round(x - radius, 6), round(y - radius, 6), round(z - radius, 6)],
        "max": [round(x + radius, 6), round(y + radius, 6), round(z + radius, 6)],
    }


def _coerce_entry(entry: Any) -> dict[str, Any]:
    """Coerce an interfaces block entry to a dict form.

    Accepts:
      - str  — legacy form, ``sockets = [name1, name2]``.
      - dict — structured form with id/name/socket_type/pivot_type/etc.
      - call — source form, ``socket(id: foo, socket_type: attach)``.
    """
    return coerce_interface_entry(entry)


def _resolve_socket_type(entry: dict[str, Any], *, source_label: str) -> str:
    raw = entry.get("socket_type") or entry.get("type")
    if raw is None:
        warnings.warn(
            f"Socket '{source_label}' declared without socket_type; "
            f"defaulting to '{DEFAULT_SOCKET_TYPE}'. Declare an explicit "
            f"socket_type; see docs/anchor_catalog.md.",
            DeprecationWarning,
            stacklevel=3,
        )
        return DEFAULT_SOCKET_TYPE
    return str(raw)


def _resolve_pivot_type(entry: dict[str, Any], *, source_label: str) -> str:
    raw = entry.get("pivot_type") or entry.get("type")
    if raw is None:
        warnings.warn(
            f"Pivot '{source_label}' declared without pivot_type; "
            f"defaulting to '{DEFAULT_PIVOT_TYPE}'. Declare an explicit "
            f"pivot_type; see docs/anchor_catalog.md.",
            DeprecationWarning,
            stacklevel=3,
        )
        return DEFAULT_PIVOT_TYPE
    return str(raw)


def run(executor: Any, rig_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        rig_bundle: rig_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["interfaces"]
    cfg = executor.asset["build"]["interfaces"]
    mesh = executor.runtime["topology"]["runtime_mesh"].mesh
    bounds = mesh.bounds
    center = mesh.bounding_box.centroid
    z_extent = float(bounds[1, 2] - bounds[0, 2])
    # 1% of Z extent as socket AABB half-width — small, symmetric, deterministic.
    socket_aabb_radius = max(abs(z_extent) * 0.01, 1e-4)

    raw_sockets = cfg.get("sockets", []) or []
    sockets: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_sockets):
        entry = _coerce_entry(raw)
        name = str(entry.get("name") or entry.get("id") or f"socket_{idx}")
        sid = str(entry.get("id") or name)
        n_sockets = max(1, len(raw_sockets))
        z_offset = (-0.2 + 0.4 * idx / n_sockets) * z_extent
        position = [
            round(float(center[0]), 6),
            round(float(center[1]), 6),
            round(float(center[2] + z_offset), 6),
        ]
        socket_type = _resolve_socket_type(entry, source_label=name)
        transform = _round_transform(_translation_transform(position[0], position[1], position[2]))
        aabb = _aabb_around(position, socket_aabb_radius)
        socket: dict[str, Any] = {
            "id": sid,
            "name": name,
            "socket_type": socket_type,
            "position": position,
            "transform": transform,
            "aabb": aabb,
        }
        if "kind" in entry and isinstance(entry["kind"], str):
            socket["kind"] = entry["kind"]
        if "compat_kind" in entry and isinstance(entry["compat_kind"], str):
            socket["compat_kind"] = entry["compat_kind"]
        if "parent_part_id" in entry and isinstance(entry["parent_part_id"], str):
            socket["parent_part_id"] = entry["parent_part_id"]
        if "metadata" in entry and isinstance(entry["metadata"], dict):
            socket["metadata"] = dict(entry["metadata"])
        sockets.append(socket)

    # Pivots — derived from explicit `pivots = [...]` if present (V0.2+), and
    # also from the legacy `anchors = [...]` list (V0.1 sources continue to
    # compile). Plus an implicit world pivot if no pivots are declared at all.
    raw_pivots = cfg.get("pivots", []) or []
    raw_anchors = cfg.get("anchors", []) or []
    pivots: list[dict[str, Any]] = []
    seen_pivot_ids: set[str] = set()

    for idx, raw in enumerate(raw_pivots):
        entry = _coerce_entry(raw)
        name = str(entry.get("name") or entry.get("id") or f"pivot_{idx}")
        pid = str(entry.get("id") or name)
        if pid in seen_pivot_ids:
            continue
        seen_pivot_ids.add(pid)
        pivot_type = _resolve_pivot_type(entry, source_label=name)
        origin_raw = entry.get("origin") or entry.get("position")
        if isinstance(origin_raw, (list, tuple)) and len(origin_raw) == 3:
            origin = _round_vec3(list(origin_raw))
        elif pivot_type == "contact":
            origin = [
                round(float(center[0]), 6),
                round(float(bounds[0, 1]), 6),
                round(float(center[2]), 6),
            ]
        else:
            origin = [
                round(float(center[0]), 6),
                round(float(center[1]), 6),
                round(float(center[2]), 6),
            ]
        transform = _round_transform(_translation_transform(origin[0], origin[1], origin[2]))
        pivot: dict[str, Any] = {
            "id": pid,
            "name": name,
            "pivot_type": pivot_type,
            "position": origin,
            "origin": origin,
            "transform": transform,
        }
        if "parent_part_id" in entry and isinstance(entry["parent_part_id"], str):
            pivot["parent_part_id"] = entry["parent_part_id"]
        if "metadata" in entry and isinstance(entry["metadata"], dict):
            pivot["metadata"] = dict(entry["metadata"])
        pivots.append(pivot)

    # Legacy anchors → contact pivots for backwards compatibility with V0.1
    # sources (courier_drone still declares `anchors = [floor_contact]`). The
    # legacy anchors list is preserved verbatim so older evaluators keep
    # working; new consumers should read `pivots`.
    anchors: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_anchors):
        entry = _coerce_entry(raw)
        name = str(entry.get("name") or entry.get("id") or f"anchor_{idx}")
        aid = str(entry.get("id") or name)
        position = [
            round(float(center[0]), 6),
            round(float(bounds[0, 1]), 6),
            round(float(center[2]), 6),
        ]
        anchors.append({"name": name, "position": position})
        if aid in seen_pivot_ids:
            # An explicit pivot with the same id was already emitted — don't
            # duplicate. This lets a .lth source migrate from anchors→pivots
            # incrementally without tripping the uniqueness checker.
            continue
        seen_pivot_ids.add(aid)
        pivot_type = _resolve_pivot_type(entry, source_label=name)
        # Default pivot_type for legacy anchors is "contact" (they sit on the
        # ground by the evaluator's convention), but the warning surfaces the
        # migration path.
        if entry.get("pivot_type") is None and entry.get("type") is None:
            pivot_type = "contact"
        transform = _round_transform(_translation_transform(position[0], position[1], position[2]))
        pivots.append(
            {
                "id": aid,
                "name": name,
                "pivot_type": pivot_type,
                "position": position,
                "origin": position,
                "transform": transform,
            }
        )

    # Every asset inherits a `world` pivot at identity if the source declared
    # no pivots at all (so STAGE-4 is guaranteed to populate the manifest).
    if not pivots:
        pivots.append(
            {
                "id": "world",
                "name": "world",
                "pivot_type": "world",
                "position": [0.0, 0.0, 0.0],
                "origin": [0.0, 0.0, 0.0],
                "transform": _identity_transform(),
            }
        )

    connection_bundle = resolve_interface_connections(
        sockets=sockets,
        pivots=pivots,
        anchors=anchors,
        raw_connections=cfg.get("connections") or [],
        clearance=cfg.get("clearance"),
        snap_grid=cfg.get("snap_grid"),
        auto_connect=bool(cfg.get("auto_connect")),
    )

    bundle = {
        "backend_id": "lathe.interfaces.socket_stub_v1",
        "sockets": sockets,
        "pivots": pivots,
        "anchors": anchors,
        "connections": connection_bundle["connections"],
        "connection_slots": connection_bundle["connection_slots"],
        "clearance": cfg.get("clearance"),
        "snap_grid": cfg.get("snap_grid"),
    }
    executor.runtime["interfaces"] = {"bundle": bundle}
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
