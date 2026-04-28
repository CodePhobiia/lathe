"""Helpers for Lathe interface socket/pivot declarations.

The source grammar represents constructor-style entries such as
``socket(id: cargo_anchor, socket_type: attach)`` as generic call
expressions. Runtime stages and checkers need the same normalized mapping
shape whether the entry came from legacy strings, Python tests, or source
calls.
"""

from __future__ import annotations

from typing import Any

INTERFACE_CONSTRUCTORS = {"socket", "pivot", "anchor"}


def interface_constructor(entry: Any) -> str | None:
    """Return the source constructor name for a parser call expression."""
    if isinstance(entry, dict) and entry.get("type") == "call":
        name = entry.get("name")
        if isinstance(name, str) and name:
            return name
    return None


def coerce_interface_entry(entry: Any) -> dict[str, Any]:
    """Coerce legacy strings, structured dicts, and call entries to mappings."""
    if isinstance(entry, str):
        return {"name": entry, "id": entry}
    if isinstance(entry, dict):
        constructor = interface_constructor(entry)
        if constructor in INTERFACE_CONSTRUCTORS:
            out: dict[str, Any] = {}
            positional: list[Any] = []
            for arg in entry.get("args") or []:
                if not isinstance(arg, dict) or "value" not in arg:
                    continue
                arg_name = arg.get("name")
                if arg_name is None:
                    positional.append(arg["value"])
                else:
                    out[str(arg_name)] = arg["value"]
            if positional and "id" not in out and "name" not in out:
                out["id"] = positional[0]
            if "name" not in out and "id" in out:
                out["name"] = out["id"]
            if "id" not in out and "name" in out:
                out["id"] = out["name"]
            return out
        out = dict(entry)
        if "name" not in out and "id" in out:
            out["name"] = out["id"]
        if "id" not in out and "name" in out:
            out["id"] = out["name"]
        return out
    return {"name": str(entry), "id": str(entry)}


def interface_entry_id(entry: Any, fallback: str) -> str:
    """Return the stable id/name for any supported interface entry form."""
    coerced = coerce_interface_entry(entry)
    return str(coerced.get("id") or coerced.get("name") or fallback)
