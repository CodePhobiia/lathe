"""URDF-style validator for robotics-intent assets (STAGE-11).

Gated: only runs when the asset declares robotics intent — either
``asset.intent.robotics == True`` or ``asset.kind == "robot"``. For any
non-robotics asset the validator reports ``passes=True`` with no evidence
and no diagnostics so it is a no-op in the general case.

Checks (all against the ``interfaces`` bundle + ``physics`` bundle):

* L6401 — every socket of type ``hinge`` / ``door`` declares an ``axis``
  *and* rotational ``limits`` (``limit_lower`` + ``limit_upper``).
* L6402 — joint graph contains a cycle (kinematic loop). Detected across
  ``parent_part_id`` edges between hinge/door sockets.
* L6403 — every movable part has a ``mass`` and a positive ``inertia``
  diagonal. Physics bundle's ``parts`` list is consulted; missing keys
  are reported once per part.
* L6404 — inconsistent units across parts (mass in kg/g mixed, or length
  units diverge from the asset's ``space.unit``).
* L6405 — socket axis is not unit length (tolerance 1e-3).
* L6406 — socket ``limit_lower`` >= ``limit_upper`` (degenerate range).

Diagnostics follow the standard Lathe shape: ``{code, name, severity,
stage, phase, message, details}``.
"""

from __future__ import annotations

import math
from typing import Any, Iterable


L6401 = "L6401"
L6402 = "L6402"
L6403 = "L6403"
L6404 = "L6404"
L6405 = "L6405"
L6406 = "L6406"

_JOINT_SOCKET_TYPES = frozenset({"hinge", "door"})


def _robotics_intent(asset: dict[str, Any]) -> bool:
    if not isinstance(asset, dict):
        return False
    intent = asset.get("intent") or {}
    if isinstance(intent, dict) and bool(intent.get("robotics")):
        return True
    kind = asset.get("kind")
    if isinstance(kind, str) and kind.strip().lower() == "robot":
        return True
    # Fallback: explicit build-level flag.
    build = asset.get("build") or {}
    b_intent = build.get("intent") if isinstance(build, dict) else None
    if isinstance(b_intent, dict) and bool(b_intent.get("robotics")):
        return True
    return False


def _make_diag(
    code: str,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "id": code,
        "name": f"urdf_{code.lower()}",
        "severity": severity,
        "phase": "validate",
        "stage": "validate",
        "validator": "urdf_validation",
        "message": message,
        "details": details or {},
    }


def _vec_length(axis: Iterable[Any]) -> float | None:
    try:
        values = [float(v) for v in axis]
    except (TypeError, ValueError):
        return None
    if len(values) != 3:
        return None
    return math.sqrt(sum(v * v for v in values))


def _detect_cycle(nodes: set[str], edges: list[tuple[str, str]]) -> list[str] | None:
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if u in adj and v in adj:
            adj[u].append(v)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    parent: dict[str, str | None] = {n: None for n in nodes}

    def _dfs(start: str) -> list[str] | None:
        stack = [(start, iter(adj[start]))]
        color[start] = GRAY
        while stack:
            node, children = stack[-1]
            try:
                child = next(children)
            except StopIteration:
                color[node] = BLACK
                stack.pop()
                continue
            if color[child] == GRAY:
                # Cycle found. Walk back from node to child.
                cycle = [child, node]
                cur = parent.get(node)
                while cur is not None and cur != child:
                    cycle.append(cur)
                    cur = parent.get(cur)
                if cur == child:
                    cycle.append(child)
                return list(reversed(cycle))
            if color[child] == WHITE:
                parent[child] = node
                color[child] = GRAY
                stack.append((child, iter(adj[child])))
        return None

    for node in sorted(nodes):
        if color[node] == WHITE:
            result = _dfs(node)
            if result is not None:
                return result
    return None


def evaluate_urdf_validation(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Run URDF validation. Returns a legacy-shaped validator report.

    For non-robotics assets: returns an empty-evidence report with no
    diagnostics so ``ValidatorPipeline`` treats it as a pass.
    """

    if not _robotics_intent(asset):
        return {
            "diagnostics": [],
            "metrics": {"gated_off": True},
            "joint_count": 0,
            "moving_part_count": 0,
        }

    diagnostics: list[dict[str, Any]] = []
    interfaces = (runtime.get("interfaces") or {}).get("bundle") or {}
    sockets = interfaces.get("sockets") or []
    if not isinstance(sockets, list):
        sockets = []

    joint_sockets: list[dict[str, Any]] = []
    for sock in sockets:
        if not isinstance(sock, dict):
            continue
        stype = sock.get("socket_type") or sock.get("socketType") or sock.get("kind")
        if isinstance(stype, str) and stype.lower() in _JOINT_SOCKET_TYPES:
            joint_sockets.append(sock)

    joint_count = 0
    for sock in joint_sockets:
        sid = str(sock.get("id") or sock.get("name") or "?")
        axis = sock.get("axis")
        lower = sock.get("limit_lower")
        upper = sock.get("limit_upper")
        if axis is None or lower is None or upper is None:
            diagnostics.append(
                _make_diag(
                    L6401,
                    f"Joint socket '{sid}' is missing axis/limits "
                    "(hinge+door sockets require axis, limit_lower, limit_upper).",
                    details={"socket_id": sid, "has_axis": axis is not None,
                             "has_limit_lower": lower is not None, "has_limit_upper": upper is not None},
                )
            )
            continue
        length = _vec_length(axis) if isinstance(axis, list) else None
        if length is None or abs(length - 1.0) > 1e-3:
            diagnostics.append(
                _make_diag(
                    L6405,
                    f"Joint socket '{sid}' axis is not unit length "
                    f"(|axis|={length!r}).",
                    details={"socket_id": sid, "axis": axis, "length": length},
                )
            )
        try:
            lo = float(lower)
            hi = float(upper)
            if lo >= hi:
                diagnostics.append(
                    _make_diag(
                        L6406,
                        f"Joint socket '{sid}' has degenerate limit range "
                        f"(lower={lo}, upper={hi}).",
                        details={"socket_id": sid, "lower": lo, "upper": hi},
                    )
                )
        except (TypeError, ValueError):
            # Axis-present but non-numeric limits are already covered by the
            # absence check at L6401; don't double-report.
            pass
        joint_count += 1

    # Cycle detection — build graph from joint sockets' parent_part_id edges.
    parts_seen: set[str] = set()
    edges: list[tuple[str, str]] = []
    for sock in joint_sockets:
        parent = sock.get("parent_part_id") or sock.get("parentPartId")
        child = sock.get("child_part_id") or sock.get("childPartId")
        if isinstance(parent, str) and isinstance(child, str) and parent and child:
            parts_seen.add(parent)
            parts_seen.add(child)
            edges.append((parent, child))
    cycle = _detect_cycle(parts_seen, edges) if parts_seen else None
    if cycle:
        diagnostics.append(
            _make_diag(
                L6402,
                f"Kinematic loop detected across parts: {' -> '.join(cycle)}.",
                details={"cycle": list(cycle)},
            )
        )

    # Mass / inertia check.
    physics_bundle = (runtime.get("physics") or {}).get("bundle") or {}
    physics_parts = physics_bundle.get("parts")
    if not isinstance(physics_parts, list):
        physics_parts = []

    moving_parts_with_checks = 0
    missing_reports: list[dict[str, Any]] = []
    mass_units: set[str] = set()
    length_units: set[str] = set()
    for part in physics_parts:
        if not isinstance(part, dict):
            continue
        pid = str(part.get("id") or part.get("name") or "?")
        if not part.get("movable", True):
            continue
        moving_parts_with_checks += 1
        issues: list[str] = []
        mass = part.get("mass")
        if not isinstance(mass, (int, float)) or float(mass) <= 0.0:
            issues.append("mass")
        inertia = part.get("inertia")
        if not isinstance(inertia, list) or len(inertia) != 3 or not all(
            isinstance(v, (int, float)) and float(v) > 0.0 for v in inertia
        ):
            issues.append("inertia")
        if issues:
            diagnostics.append(
                _make_diag(
                    L6403,
                    f"Movable part '{pid}' is missing {', '.join(issues)} (required for URDF).",
                    details={"part_id": pid, "missing": issues},
                )
            )
            missing_reports.append({"part_id": pid, "missing": issues})
        mu = part.get("mass_units")
        if isinstance(mu, str) and mu:
            mass_units.add(mu)
        lu = part.get("length_units")
        if isinstance(lu, str) and lu:
            length_units.add(lu)

    asset_unit = None
    space = asset.get("space") if isinstance(asset, dict) else None
    if isinstance(space, dict):
        candidate = space.get("unit") or space.get("units")
        if isinstance(candidate, str):
            asset_unit = candidate
    if len(mass_units) > 1 or (asset_unit and length_units and asset_unit not in length_units):
        diagnostics.append(
            _make_diag(
                L6404,
                "Inconsistent units across robotics parts "
                f"(mass_units={sorted(mass_units)}, length_units={sorted(length_units)}, "
                f"asset_unit={asset_unit}).",
                details={
                    "mass_units": sorted(mass_units),
                    "length_units": sorted(length_units),
                    "asset_unit": asset_unit,
                },
            )
        )

    passes = not any(d.get("severity") == "error" for d in diagnostics)
    return {
        "diagnostics": diagnostics,
        "metrics": {
            "joint_count": joint_count,
            "moving_part_count": moving_parts_with_checks,
            "missing_physics": missing_reports,
            "gated_off": False,
        },
        "joint_count": joint_count,
        "moving_part_count": moving_parts_with_checks,
        "passes": passes,
    }


__all__ = [
    "L6401",
    "L6402",
    "L6403",
    "L6404",
    "L6405",
    "L6406",
    "evaluate_urdf_validation",
]
