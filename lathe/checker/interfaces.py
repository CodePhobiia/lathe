"""Interfaces-block checks (STAGE-3/4/5, V0.2 E3).

Validates the `build.interfaces` block:

* Sockets and pivots declared in structured form must use a known
  `socket_type` / `pivot_type` (catalogued in ``docs/anchor_catalog.md``).
* Anchor ids (sockets + pivots + legacy anchors) must be unique across all
  three lists — an anchor ref token like ``@lathe[asset#socket.foo]`` vs
  ``@lathe[asset#pivot.foo]`` must resolve to a single declaration.
"""

from __future__ import annotations

from typing import Any

from lathe.interface_entries import coerce_interface_entry, interface_constructor

from .utils import diag

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


def _entry_id(entry: Any, fallback: str) -> str:
    coerced = coerce_interface_entry(entry)
    return str(coerced.get("id") or coerced.get("name") or fallback)


def _entry_type(entry: Any) -> str | None:
    coerced = coerce_interface_entry(entry)
    raw = coerced.get("socket_type") or coerced.get("pivot_type") or coerced.get("type")
    if raw is None:
        return None
    return str(raw)


def _check_constructor(
    checker: Any,
    *,
    asset_name: str | None,
    entry: Any,
    expected: str,
    path: str,
) -> bool:
    constructor = interface_constructor(entry)
    if constructor is None or constructor == expected:
        return True
    checker.diagnostics.append(
        diag(
            "L4704",
            "interface_constructor_mismatch",
            "error",
            "typecheck",
            (
                f"Interface entry uses constructor '{constructor}' in a {expected}s "
                f"list. Use {expected}(...) here."
            ),
            asset=asset_name,
            path=path,
            details={"constructor": constructor, "expected": expected},
        )
    )
    return False


def check_interfaces(
    checker: Any,
    asset: dict[str, Any],
) -> None:
    """Validate sockets + pivots + anchor-id uniqueness."""
    asset_name = asset.get("name")
    build = asset.get("build") or {}
    interfaces = build.get("interfaces") or {}
    sockets = interfaces.get("sockets") or []
    pivots = interfaces.get("pivots") or []
    anchors = interfaces.get("anchors") or []

    # Unknown socket_type
    for idx, entry in enumerate(sockets):
        if not _check_constructor(
            checker,
            asset_name=asset_name,
            entry=entry,
            expected="socket",
            path=f"build.interfaces.sockets[{idx}]",
        ):
            continue
        t = _entry_type(entry)
        if t is not None and t not in SOCKET_TYPES:
            sid = _entry_id(entry, f"sockets[{idx}]")
            checker.diagnostics.append(
                diag(
                    "L4701",
                    "unknown_socket_type",
                    "error",
                    "typecheck",
                    (
                        f"Socket '{sid}' has unknown socket_type '{t}'. "
                        f"Valid types: {', '.join(SOCKET_TYPES)}."
                    ),
                    asset=asset_name,
                    path=f"build.interfaces.sockets[{idx}].socket_type",
                    details={"valid_types": list(SOCKET_TYPES)},
                )
            )

    # Unknown pivot_type
    for idx, entry in enumerate(pivots):
        if not _check_constructor(
            checker,
            asset_name=asset_name,
            entry=entry,
            expected="pivot",
            path=f"build.interfaces.pivots[{idx}]",
        ):
            continue
        t = _entry_type(entry)
        if t is not None and t not in PIVOT_TYPES:
            pid = _entry_id(entry, f"pivots[{idx}]")
            checker.diagnostics.append(
                diag(
                    "L4702",
                    "unknown_pivot_type",
                    "error",
                    "typecheck",
                    (f"Pivot '{pid}' has unknown pivot_type '{t}'. Valid types: {', '.join(PIVOT_TYPES)}."),
                    asset=asset_name,
                    path=f"build.interfaces.pivots[{idx}].pivot_type",
                    details={"valid_types": list(PIVOT_TYPES)},
                )
            )

    # Anchor id uniqueness (sockets + pivots + legacy anchors must not collide)
    seen: dict[str, str] = {}
    buckets = (
        (sockets, "socket"),
        (pivots, "pivot"),
        (anchors, "anchor"),
    )
    for bucket, label in buckets:
        for idx, entry in enumerate(bucket):
            aid = _entry_id(entry, f"{label}s[{idx}]")
            if not aid:
                continue
            if aid in seen:
                prior = seen[aid]
                checker.diagnostics.append(
                    diag(
                        "L4703",
                        "duplicate_anchor_id",
                        "error",
                        "typecheck",
                        (
                            f"Anchor id '{aid}' is declared in both "
                            f"{prior} and {label}s[{idx}]. Anchor ids must be "
                            f"globally unique across sockets, pivots, and anchors."
                        ),
                        asset=asset_name,
                        path=f"build.interfaces.{label}s[{idx}]",
                        details={
                            "id": aid,
                            "first_declaration": prior,
                            "second_declaration": f"{label}s[{idx}]",
                        },
                    )
                )
            else:
                seen[aid] = f"{label}s[{idx}]"
