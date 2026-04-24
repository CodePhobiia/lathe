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
