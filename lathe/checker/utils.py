"""Shared helpers for the checker rule modules.

Small utilities for error accumulation, path rendering and AST
traversal used by the ``check_*`` functions in sibling modules.
"""

from __future__ import annotations

from typing import Any


BACKEND_PATHS = {
    "shape": "build.shape.backend",
    "topology": "build.topology.backend",
    "uv": "build.uv.backend",
    "package": "package.backend",
}

V13_1_EVIDENCE_CLASSES = {
    "geometry_evidence",
    "topology_evidence",
    "uv_evidence",
    "bake_evidence",
    "surface_evidence",
    "package_export_evidence",
}


def diag(
    code: str,
    name: str,
    severity: str,
    phase: str,
    message: str,
    *,
    asset: str | None = None,
    stage: str | None = None,
    path: str | None = None,
    details: dict[str, Any] | None = None,
    suggested_repairs: list[str] | None = None,
) -> dict[str, Any]:
    """Diag.

    Args:
        code: code argument.
        name: name argument.
        severity: severity argument.
        phase: phase argument.
        message: message argument.
        asset: asset argument.
        stage: stage argument.
        path: path argument.
        details: details argument.
        suggested_repairs: suggested_repairs argument.

    Returns:
        The result.
    """
    return {
        "code": code,
        "name": name,
        "severity": severity,
        "phase": phase,
        "asset": asset,
        "stage": stage,
        "path": path,
        "message": message,
        "details": details or {},
        "suggested_repairs": suggested_repairs or [],
    }
