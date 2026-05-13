"""Trim sheets + UDIM authoring.

Per northstar §11 Phase 3 + §10 Lane F later-tasks. A trim sheet
packs multiple authored detail strips into one texture; per-part UV
charts bind to a specific slot. This module declares the typed
contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

TRIM_SHEETS_VERSION = "lathe.asset_foundry.trim_sheets_v1"


@dataclass(frozen=True)
class TrimSheetSlot:
    """One slot on a trim sheet."""

    slot_id: str
    u_min: float
    v_min: float
    u_max: float
    v_max: float
    slot_kind: str
    """``trim`` | ``decal`` | ``label`` | ``edge_wear`` | ``noise``."""

    seamless_horizontal: bool = False
    seamless_vertical: bool = False
    description: str = ""


@dataclass(frozen=True)
class TrimSheet:
    """A trim sheet: name + slots."""

    sheet_id: str
    texture_path: str
    slots: tuple[TrimSheetSlot, ...]
    resolution_px: tuple[int, int] = (2048, 2048)
    style_pack_id: str | None = None


def bind_part_to_trim_slot(
    *,
    part_id: str,
    slot_id: str,
    sheet: TrimSheet,
) -> Mapping[str, Any]:
    """Build a per-part trim binding record.

    Returns a dict consumed by the UV stage to place the part's UV
    chart inside the slot's rectangle.
    """
    slot = next((s for s in sheet.slots if s.slot_id == slot_id), None)
    if slot is None:
        return {
            "part_id": part_id,
            "sheet_id": sheet.sheet_id,
            "slot_id": slot_id,
            "status": "unsupported",
            "status_reason": f"slot_{slot_id!r}_not_found",
        }
    return {
        "part_id": part_id,
        "sheet_id": sheet.sheet_id,
        "slot_id": slot_id,
        "uv_rect": [slot.u_min, slot.v_min, slot.u_max, slot.v_max],
        "slot_kind": slot.slot_kind,
        "seamless_horizontal": slot.seamless_horizontal,
        "seamless_vertical": slot.seamless_vertical,
        "status": "real",
    }


__all__ = [
    "TRIM_SHEETS_VERSION",
    "TrimSheet",
    "TrimSheetSlot",
    "bind_part_to_trim_slot",
]
