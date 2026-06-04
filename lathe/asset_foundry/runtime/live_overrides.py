"""Live parameter overrides.

Per northstar §11 Phase 5. Live overrides let an engine plugin
adjust a procedural asset's parameters at runtime (e.g. an editor
slider that re-bakes the asset when the user drags it). Each
override carries an asset_id + parameter_path + new value + a
constraint check that rejects out-of-range / wrong-type values.

The session record tracks the override history so the engine can
audit + roll back.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

LIVE_OVERRIDES_VERSION = "lathe.asset_foundry.live_overrides_v1"


@dataclass(frozen=True)
class LiveOverrideBinding:
    """One override applied during a session."""

    asset_id: str
    parameter_path: str
    """Dot-separated path (e.g. ``primary_height_cm`` or
    ``foliage_layers``)."""
    new_value: Any
    previous_value: Any
    timestamp_unix: float
    accepted: bool
    rejection_reason: str = ""


@dataclass
class LiveOverrideSession:
    """A mutable session record holding override history."""

    session_id: str
    asset_id: str
    bindings: list[LiveOverrideBinding] = field(default_factory=list)
    started_unix: float = field(default_factory=time.time)

    def history(self) -> tuple[LiveOverrideBinding, ...]:
        return tuple(self.bindings)


def new_live_override_session(
    *,
    session_id: str,
    asset_id: str,
) -> LiveOverrideSession:
    return LiveOverrideSession(session_id=session_id, asset_id=asset_id)


def apply_live_override(
    session: LiveOverrideSession,
    *,
    current_parameters: Mapping[str, Any],
    parameter_path: str,
    new_value: Any,
    parameter_constraints: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], LiveOverrideBinding]:
    """Apply one override; return (new_parameters, binding).

    Constraints record per-parameter type + range; mismatches reject
    the override and the binding is tagged accordingly.
    """
    previous = current_parameters.get(parameter_path)
    rejection = ""
    accepted = True
    if parameter_constraints and parameter_path in parameter_constraints:
        c = parameter_constraints[parameter_path]
        expected_type = c.get("type")
        if expected_type and not isinstance(new_value, _resolve_type(expected_type)):
            accepted = False
            rejection = f"type_mismatch_expected_{expected_type}"
        elif isinstance(new_value, (int, float)):
            mn = c.get("min")
            mx = c.get("max")
            if mn is not None and new_value < mn:
                accepted = False
                rejection = f"value_below_min_{mn}"
            if mx is not None and new_value > mx:
                accepted = False
                rejection = f"value_above_max_{mx}"
    new_params = dict(current_parameters)
    if accepted:
        new_params[parameter_path] = new_value
    binding = LiveOverrideBinding(
        asset_id=session.asset_id,
        parameter_path=parameter_path,
        new_value=new_value if accepted else previous,
        previous_value=previous,
        timestamp_unix=time.time(),
        accepted=accepted,
        rejection_reason=rejection,
    )
    session.bindings.append(binding)
    return new_params, binding


def _resolve_type(name: str) -> type:
    if name == "int":
        return int
    if name == "float":
        return (int, float)  # accept ints for float params
    if name == "str":
        return str
    if name == "bool":
        return bool
    return object


__all__ = [
    "LIVE_OVERRIDES_VERSION",
    "LiveOverrideBinding",
    "LiveOverrideSession",
    "apply_live_override",
    "new_live_override_session",
]
