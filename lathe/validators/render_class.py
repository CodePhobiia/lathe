"""Roadmap §5.9 — real-render-class validators aggregator.

Runs the eight §5.9 validators (5 mesh-only, 3 renderer-dependent)
against the runtime and returns a uniform findings list suitable for
merging into ``quality_diagnostics.findings``.

Each child validator returns its own report:
``{version, score, status, severity, evidence}``. This aggregator
flattens those into ``findings`` records and a per-metric ``metrics``
dict so they appear alongside the existing Phase 1 deterministic
diagnostics.

Members:

* ``box_stack_detector`` — mesh-only, hard-rejects under hero/aaa_hero.
* ``edge_density_variance`` — mesh-only.
* ``curvature_distribution`` — mesh-only.
* ``topology_class_compliance`` — mesh-only (quad-domination, n-gon
  block, pole-vertex valence in deformation zones).
* ``texel_density_consistency`` — mesh-only (consumes UV runtime mesh).
* ``silhouette_multi_angle`` — renderer-dependent, framework + skip.
* ``frequency_energy`` — renderer-dependent, framework + skip.
* ``pbr_chart_compliance`` — renderer-dependent, framework + skip.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .box_stack_detector import evaluate_box_stack_detector
from .curvature_distribution import evaluate_curvature_distribution
from .edge_density import evaluate_edge_density_variance
from .frequency_energy import evaluate_frequency_energy
from .pbr_chart import evaluate_pbr_chart_compliance
from .silhouette_multi_angle import evaluate_silhouette_multi_angle
from .texel_density import evaluate_texel_density_consistency
from .topology_class import evaluate_topology_class_compliance

VERSION = "lathe.validate.render_class_v1"

_RECOMMENDATIONS: dict[str, str] = {
    "box_stack_detector": (
        "Break up axis-aligned face dominance with bevels, panel breaks, "
        "or chamfered edges. Add features that produce non-axis face "
        "normals so the silhouette reads as designed rather than stacked."
    ),
    "edge_density_variance": (
        "Vary edge density across the mesh. Add small features (greebles, "
        "vents, panel seams) that introduce shorter edges without "
        "shrinking the larger structural faces."
    ),
    "curvature_distribution": (
        "Add bevels and rounded transitions so curvature distributes "
        "across mid-range bins rather than concentrating only at sharp "
        "corners or perfectly flat areas."
    ),
    "topology_class_compliance": (
        "Eliminate n-gons in deformation zones; reduce pole-vertex valence; "
        "promote quad-dominated topology where possible."
    ),
    "texel_density_consistency": (
        "Re-pack UVs with consistent texel density. Avoid one large island "
        "consuming most of the chart while small features compete for "
        "leftover space."
    ),
    "silhouette_multi_angle": (
        "Render the asset at the declared angles and ensure the silhouette "
        "shows visible break-up (perimeter complexity, asymmetry, high-"
        "frequency energy)."
    ),
    "frequency_energy": (
        "Render the asset's silhouette and add features that contribute "
        "diagonal spectral energy (chamfers, angled greebles, pose breaks)."
    ),
    "pbr_chart_compliance": (
        "Author PBR materials that respect canonical channel ranges: "
        "metallic ∈ {0,1}, dielectric F0 ≈ 0.04, albedo within sRGB safe."
    ),
}


_VALIDATORS: tuple[tuple[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]], ...] = (
    ("box_stack_detector", evaluate_box_stack_detector),
    ("edge_density_variance", evaluate_edge_density_variance),
    ("curvature_distribution", evaluate_curvature_distribution),
    ("topology_class_compliance", evaluate_topology_class_compliance),
    ("texel_density_consistency", evaluate_texel_density_consistency),
    ("silhouette_multi_angle", evaluate_silhouette_multi_angle),
    ("frequency_energy", evaluate_frequency_energy),
    ("pbr_chart_compliance", evaluate_pbr_chart_compliance),
)

_RENDERER_DEPENDENT: frozenset[str] = frozenset(
    {"silhouette_multi_angle", "frequency_energy", "pbr_chart_compliance"}
)


def evaluate_render_class_validators(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Run the §5.9 validator suite and return aggregate findings.

    Args:
        asset: resolved asset dict.
        runtime: executor runtime after at least the topology stage.

    Returns:
        ``{version, validators, metrics, findings}`` where:
            * ``validators`` is ``{name: report}`` per child;
            * ``metrics`` is ``{name: score}`` for dashboard surfaces;
            * ``findings`` is a flat list of records suitable to merge
              into ``quality_diagnostics.findings``. Each finding carries
              ``metric``, ``severity``, ``status``, ``warning``, and
              ``recommendation``.
    """
    validators: dict[str, Any] = {}
    metrics: dict[str, float] = {}
    findings: list[dict[str, Any]] = []

    for name, fn in _VALIDATORS:
        try:
            report = fn(asset, runtime)
        except (ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            report = {
                "version": "lathe.validate.error_v1",
                "score": 0.0,
                "status": "error",
                "severity": "warning",
                "evidence": {"error": f"{type(exc).__name__}: {exc}"},
            }
        validators[name] = report
        metrics[name] = float(report.get("score", 0.0))

        status = str(report.get("status", "pass"))
        severity = str(report.get("severity", "info"))
        if status in {"pass", "skipped"} and severity in {"info"} and status != "renderer_unavailable":
            continue
        if status == "renderer_unavailable" and name in _RENDERER_DEPENDENT:
            findings.append(
                {
                    "metric": name,
                    "severity": "info",
                    "status": status,
                    "warning": f"{name} skipped: renderer output unavailable",
                    "recommendation": _RECOMMENDATIONS.get(name, ""),
                    "score": float(report.get("score", 0.0)),
                }
            )
            continue
        if status in {"warn", "fail", "error"}:
            warning_text = (
                f"{name} {status} (score={float(report.get('score', 0.0)):.3f})"
            )
            findings.append(
                {
                    "metric": name,
                    "severity": severity,
                    "status": status,
                    "warning": warning_text,
                    "recommendation": _RECOMMENDATIONS.get(name, ""),
                    "score": float(report.get("score", 0.0)),
                }
            )

    return {
        "version": VERSION,
        "validators": validators,
        "metrics": metrics,
        "findings": findings,
    }
