"""Machine-readable diagnostics for scene graph semantic checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SceneDiagnostic:
    """A single Scene Graph semantic diagnostic."""

    code: str
    name: str
    severity: str
    path: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON payload shape used by Wonder CLI commands."""
        payload: dict[str, Any] = {
            "code": self.code,
            "name": self.name,
            "severity": self.severity,
            "contract": "scene_graph",
            "phase": "scene_graph_semantics",
            "path": self.path,
            "message": self.message,
        }
        if self.details:
            payload["details"] = dict(self.details)
        return payload


def scene_diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Scene Graph semantic diagnostic as a JSON-ready dict."""
    return SceneDiagnostic(
        code=code,
        name=name,
        severity=severity,
        path=path,
        message=message,
        details=details or {},
    ).as_dict()


__all__ = ["SceneDiagnostic", "scene_diagnostic"]
