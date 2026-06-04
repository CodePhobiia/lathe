"""Foundry Lane A #6 — strict geometry mode.

Per northstar §10 Lane A priority task #6, hero-quality builds need
a strict mode that fails certification on invalid geometry claims
rather than silently degrading. Without strict mode, a build that
falls back to ``exact_boolean_fallback_concatenate`` could still
certify if other metrics compensate.

Strict mode mirrors the existing ``LATHE_STRICT_HIGHLOW`` pattern:
the gate is environment-variable + runtime-config controlled. When
enabled, the gate emits a blocking diagnostic on:

  - boolean kernel fallback to concatenate / cutter-omit;
  - watertightness failure on solid-claim assets;
  - body-count divergence from expected;
  - any operation with status ``unsupported`` or
    ``fallback`` that the asset's claim says should be ``real``.

Default is OFF (matches Sprint 0's certified-via-bounded-Manifold
path). Strict mode is opt-in.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

STRICT_GEOMETRY_MODE_VERSION = "lathe.asset_foundry.strict_geometry_mode_v1"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class StrictGeometryDiagnostic:
    """One strict-mode diagnostic record."""

    code: str
    severity: str
    """Always ``error`` in strict mode; ``warning`` outside."""

    op_id: str | None
    claim: str
    """The claim the strict gate enforced (e.g.
    ``hero_watertight_solid``, ``no_boolean_fallback``)."""

    actual: str
    """What actually happened (``concatenate_fallback``,
    ``body_count_2_vs_1``, ...)."""

    repair_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrictGeometryReport:
    """Result of running the strict gate against a build report."""

    version: str
    strict_mode_enabled: bool
    diagnostics: tuple[StrictGeometryDiagnostic, ...]
    passes: bool
    """True iff strict_mode_enabled is False OR no error-severity
    diagnostics were emitted."""


def strict_mode_enabled(
    runtime_config: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Resolve strict mode from runtime_config + env.

    Precedence:
      1. runtime_config.runtime.shape.strict_geometry_mode (bool/str)
      2. env[LATHE_STRICT_GEOMETRY]

    Truthy values: ``True``, ``"1"``, ``"true"``, ``"yes"``, ``"on"``.
    """
    if isinstance(runtime_config, Mapping):
        runtime_block = runtime_config.get("runtime")
        if isinstance(runtime_block, Mapping):
            shape_block = runtime_block.get("shape")
            if isinstance(shape_block, Mapping):
                flag = shape_block.get("strict_geometry_mode")
                if isinstance(flag, bool) and flag:
                    return True
                if isinstance(flag, str) and flag.strip().lower() in _TRUTHY:
                    return True
    src_env = env if env is not None else os.environ
    raw = src_env.get("LATHE_STRICT_GEOMETRY", "").strip().lower()
    return raw in _TRUTHY


def evaluate_strict_geometry(
    shape_report: Mapping[str, Any] | None,
    *,
    runtime_config: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    hero_claim: bool = True,
) -> StrictGeometryReport:
    """Run the strict-mode gate against a shape-stage report.

    Args:
        shape_report: the report dict emitted by the shape backend
            (typically ``runtime["shape"]["bundle"]["report"]``).
        runtime_config: runtime config dict; if ``runtime.shape.strict_geometry_mode``
            is truthy, strict mode is enabled.
        env: optional env mapping (defaults to ``os.environ``).
        hero_claim: True when the asset claims hero-quality solid
            (e.g. industrial_crate certification). When False, the
            gate softens body-count + watertight checks.

    Returns:
        A StrictGeometryReport with deterministic diagnostic codes.
    """
    enabled = strict_mode_enabled(runtime_config, env)
    severity = "error" if enabled else "warning"
    diagnostics: list[StrictGeometryDiagnostic] = []
    if not isinstance(shape_report, Mapping):
        if enabled:
            diagnostics.append(
                StrictGeometryDiagnostic(
                    code="L7010",
                    severity=severity,
                    op_id=None,
                    claim="shape_report_present",
                    actual="missing_or_malformed",
                    repair_actions=("rerun_shape_stage",),
                )
            )
        return StrictGeometryReport(
            version=STRICT_GEOMETRY_MODE_VERSION,
            strict_mode_enabled=enabled,
            diagnostics=tuple(diagnostics),
            passes=not enabled,
        )

    mode = str(shape_report.get("mode", ""))
    fallback_reasons = shape_report.get("fallback_reason")
    if "fallback_concatenate" in mode or "omit_cutters" in mode:
        diagnostics.append(
            StrictGeometryDiagnostic(
                code="L7011",
                severity=severity,
                op_id=None,
                claim="no_boolean_fallback",
                actual=mode,
                repair_actions=("route_through_manifold_full_csg",),
            )
        )
    if isinstance(fallback_reasons, str) and fallback_reasons:
        diagnostics.append(
            StrictGeometryDiagnostic(
                code="L7012",
                severity=severity,
                op_id=None,
                claim="no_unexplained_fallback",
                actual=fallback_reasons[:160],
                repair_actions=("examine_fallback_reason_chain",),
            )
        )

    if hero_claim:
        watertight = shape_report.get("watertight")
        if watertight is False:
            diagnostics.append(
                StrictGeometryDiagnostic(
                    code="L7013",
                    severity=severity,
                    op_id=None,
                    claim="hero_watertight_solid",
                    actual="not_watertight",
                    repair_actions=(
                        "verify_manifold_kernel_path",
                        "inspect_subtract_cutters",
                    ),
                )
            )
        body_count = shape_report.get("body_count")
        body_count_expected = shape_report.get("body_count_expected")
        if (
            isinstance(body_count, int)
            and isinstance(body_count_expected, int)
            and body_count_expected > 0
            and body_count != body_count_expected
        ):
            diagnostics.append(
                StrictGeometryDiagnostic(
                    code="L7014",
                    severity=severity,
                    op_id=None,
                    claim="hero_body_count_match",
                    actual=f"actual_{body_count}_expected_{body_count_expected}",
                    repair_actions=("inspect_part_separation",),
                )
            )

    op_records = shape_report.get("op_records") or shape_report.get("operations")
    if isinstance(op_records, Iterable):
        for record in op_records:
            if not isinstance(record, Mapping):
                continue
            status = str(record.get("status", "")).lower()
            claim = str(record.get("claim", "")).lower()
            op_id = str(record.get("operation_id", "")) or None
            if status in {"unsupported", "fallback"} and claim == "real":
                diagnostics.append(
                    StrictGeometryDiagnostic(
                        code="L7015",
                        severity=severity,
                        op_id=op_id,
                        claim="op_real_when_claimed_real",
                        actual=f"status_{status}",
                        repair_actions=(
                            "route_through_supporting_kernel",
                            "downgrade_claim_or_mark_unsupported",
                        ),
                    )
                )

    passes = (not enabled) or not any(d.severity == "error" for d in diagnostics)
    return StrictGeometryReport(
        version=STRICT_GEOMETRY_MODE_VERSION,
        strict_mode_enabled=enabled,
        diagnostics=tuple(diagnostics),
        passes=passes,
    )


def strict_geometry_report_to_dict(report: StrictGeometryReport) -> dict[str, Any]:
    """JSON-serialize a StrictGeometryReport."""
    return {
        "version": report.version,
        "strict_mode_enabled": report.strict_mode_enabled,
        "passes": report.passes,
        "diagnostics": [
            {
                "code": d.code,
                "severity": d.severity,
                "op_id": d.op_id,
                "claim": d.claim,
                "actual": d.actual,
                "repair_actions": list(d.repair_actions),
            }
            for d in report.diagnostics
        ],
    }


__all__ = [
    "STRICT_GEOMETRY_MODE_VERSION",
    "StrictGeometryDiagnostic",
    "StrictGeometryReport",
    "evaluate_strict_geometry",
    "strict_geometry_report_to_dict",
    "strict_mode_enabled",
]
