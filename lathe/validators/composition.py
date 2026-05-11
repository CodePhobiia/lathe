"""Validator composition contract.

Defines the :class:`Validator` protocol, the :class:`ValidatorReport`
shape, and the :class:`ValidatorPipeline` that runs a set of validators
in topological order (by ``stage_dependencies``) and aggregates their
reports into a single certification bundle.

This module formalises the ad-hoc sequential composition that previously
lived inline in ``lathe/core/stages/validate.py``. It does not change
validator behaviour: each wrapped validator still sees the same
``(asset, runtime)`` inputs and returns the same report shape, only now
routed through a uniform ``evaluate`` entry point.

Registered built-in validators (wired in ``lathe/core/stages/validate.py``):
``semantic_quality``, ``visual_quality``, ``flow_quality``, and
``geometry_integrity`` (post-topology, evaluated against the
authoritative runtime mesh — not a shape-stage hook).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypedDict, runtime_checkable

from ..selector_manifest import GAMEPLAY_TAG_CATALOG
from .urdf_validation import evaluate_urdf_validation


class ValidatorReport(TypedDict, total=False):
    """Uniform validator report shape.

    The ``name``, ``score``, ``passes``, ``diagnostics`` and ``evidence``
    fields are required; ``subreports`` is optional and holds nested
    sub-validator reports keyed by name.
    """

    name: str
    score: float
    passes: bool
    diagnostics: list[dict[str, Any]]
    evidence: dict[str, Any]
    subreports: dict[str, ValidatorReport]


@runtime_checkable
class Validator(Protocol):
    """Validator protocol.

    Implementations expose a human-readable ``name``, a list of build
    ``stage_dependencies`` (stage names whose runtime bundles must exist
    before this validator can run), and an ``evaluate`` method that
    produces a :class:`ValidatorReport`.
    """

    name: str
    stage_dependencies: list[str]

    def evaluate(
        self,
        runtime: dict[str, Any],
        asset: dict[str, Any],
        artifacts: dict[str, Any],
    ) -> ValidatorReport:
        """Validate ``asset`` against the current build ``runtime``."""
        ...


class FunctionValidator:
    """Adapter that wraps a legacy ``evaluate_*(asset, runtime)`` function.

    The legacy validators in ``lathe/validators/*.py`` are module-level
    functions with a ``(asset, runtime) -> dict`` signature. This adapter
    presents them to the pipeline as protocol-conforming objects without
    rewriting their internals.
    """

    def __init__(
        self,
        name: str,
        fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        stage_dependencies: list[str] | None = None,
        weight: float = 1.0,
        score_key: str | None = None,
    ) -> None:
        """Create an adapter for a legacy validator function."""
        self.name = name
        self._fn = fn
        self.stage_dependencies = list(stage_dependencies or [])
        self.weight = float(weight)
        self._score_key = score_key

    def evaluate(
        self,
        runtime: dict[str, Any],
        asset: dict[str, Any],
        artifacts: dict[str, Any],
    ) -> ValidatorReport:
        """Run the wrapped validator and normalize its report shape."""
        raw = self._fn(asset, runtime) or {}
        diagnostics = list(raw.get("diagnostics", []))
        passes = not any(diag.get("severity") == "error" for diag in diagnostics)
        score = _extract_score(raw, self._score_key, passes)
        evidence = {key: value for key, value in raw.items() if key != "diagnostics"}
        return ValidatorReport(
            name=self.name,
            score=round(float(score), 6),
            passes=bool(passes),
            diagnostics=diagnostics,
            evidence=evidence,
            subreports={},
        )


def _extract_score(raw: dict[str, Any], score_key: str | None, passes: bool) -> float:
    """Extract a numeric score from a legacy validator report.

    Legacy reports do not carry a single ``score`` field; we derive one
    by looking at the explicit ``score_key`` if provided, otherwise fall
    back to ``1.0`` when all diagnostics pass and ``0.0`` otherwise. The
    aggregate pipeline score is computed from these per-validator scores
    in :meth:`ValidatorPipeline.run`.
    """
    if score_key and score_key in raw:
        try:
            return float(raw[score_key])
        except (TypeError, ValueError):
            pass
    metrics = raw.get("metrics")
    if isinstance(metrics, dict) and score_key and score_key in metrics:
        try:
            return float(metrics[score_key])
        except (TypeError, ValueError):
            pass
    return 1.0 if passes else 0.0


def build_urdf_validator() -> FunctionValidator:
    """Return the STAGE-11 URDF validator wrapped as a pipeline validator.

    Kept in ``composition.py`` (alongside the other built-in registrations)
    so the canonical list of validators lives in one file. The validator is
    gated internally: for non-robotics assets it returns an empty-evidence
    report with no diagnostics and so acts as a no-op for the aggregate
    certification score.
    """
    return FunctionValidator(
        name="urdf_validation",
        fn=evaluate_urdf_validation,
        stage_dependencies=["interfaces", "physics"],
        weight=1.0,
    )


def build_gameplay_tag_validator() -> FunctionValidator:
    """Return the STAGE-12 gameplay-tag catalog validator.

    Verifies every tag declared in ``asset.publish.tags`` is a member of
    ``GAMEPLAY_TAG_CATALOG`` (see ``lathe/selector_manifest.py``). Any
    unknown tag is surfaced as a validate-stage error (``L6410``) carrying
    the offending tag name and the allowed catalog for operator feedback.
    Assets with no tags are silently a no-op.
    """

    def _evaluate(asset: dict[str, Any], _runtime: dict[str, Any]) -> dict[str, Any]:
        diagnostics: list[dict[str, Any]] = []
        publish = (asset or {}).get("publish") or {}
        raw_tags = publish.get("tags") or []
        if not isinstance(raw_tags, list):
            raw_tags = []
        unknown: list[str] = []
        valid: list[str] = []
        for tag in raw_tags:
            if not isinstance(tag, str):
                continue
            if tag in GAMEPLAY_TAG_CATALOG:
                valid.append(tag)
            else:
                unknown.append(tag)
        # V0.2 rollout: unknown tags are warnings by default to avoid
        # breaking assets authored pre-catalog. Assets opt in to strict
        # enforcement via asset.build.strict_gameplay_tags=true (planned
        # flip in V0.3). Without the opt-in, L6410 fires at warning
        # severity and does not block certification.
        strict_tags = bool(asset.get("build", {}).get("strict_gameplay_tags", False))
        severity = "error" if strict_tags else "warning"
        for tag in unknown:
            diagnostics.append(
                {
                    "code": "L6410",
                    "id": "L6410",
                    "name": "unknown_gameplay_tag",
                    "severity": severity,
                    "phase": "validate",
                    "stage": "validate",
                    "validator": "gameplay_tags",
                    "message": (f"Unknown gameplay tag '{tag}'. Allowed: {sorted(GAMEPLAY_TAG_CATALOG)}."),
                    "details": {"tag": tag, "allowed": sorted(GAMEPLAY_TAG_CATALOG)},
                }
            )
        return {
            "diagnostics": diagnostics,
            "metrics": {"valid": valid, "unknown": unknown},
            "valid_tags": valid,
            "unknown_tags": unknown,
        }

    return FunctionValidator(
        name="gameplay_tags",
        fn=_evaluate,
        stage_dependencies=[],
        weight=0.0,
    )


class ValidatorPipeline:
    """Topologically-ordered validator pipeline.

    The pipeline runs validators in an order consistent with their
    declared ``stage_dependencies``: a validator whose dependencies are
    a subset of an already-satisfied set runs before ones whose
    dependencies require later stages. Ties are broken by original
    registration order so that deterministic replay matches the legacy
    sequential behaviour.
    """

    def __init__(self, validators: list[Validator]) -> None:
        """Create a pipeline from validators in dependency order."""
        self._validators: list[Validator] = self._topological_order(validators)

    @property
    def validators(self) -> list[Validator]:
        """Return the ordered validators as a defensive copy."""
        return list(self._validators)

    @staticmethod
    def _topological_order(validators: list[Validator]) -> list[Validator]:
        remaining: list[tuple[int, Validator]] = list(enumerate(validators))
        ordered: list[Validator] = []
        satisfied: set[str] = set()
        while remaining:
            progressed = False
            for position, (index, validator) in enumerate(remaining):
                deps = set(getattr(validator, "stage_dependencies", []) or [])
                if deps.issubset(satisfied):
                    ordered.append(validator)
                    satisfied.update(deps)
                    satisfied.add(getattr(validator, "name", f"validator_{index}"))
                    remaining.pop(position)
                    progressed = True
                    break
            if not progressed:
                # Unresolvable dependencies → fall back to original order
                # for the tail. This keeps the pipeline total and avoids
                # silently dropping validators when a dep is not produced
                # by a peer (legacy validators cite upstream *build* stages,
                # not peer validator names).
                ordered.extend(validator for _, validator in remaining)
                break
        return ordered

    def run(
        self,
        runtime: dict[str, Any],
        asset: dict[str, Any],
        artifacts: dict[str, Any],
    ) -> dict[str, Any]:
        """Run all validators and build a certification bundle.

        Aggregation follows a min-of-gates + weighted-sum-of-scores
        policy: any failing validator flips ``certified`` to ``False``,
        and the aggregate ``score`` is a weight-normalised sum of the
        per-validator scores. The caller can still override ``certified``
        with stage-level gating (e.g. ``score >= threshold``) by
        inspecting the returned bundle.
        """
        progress_path_value = artifacts.get("validate_progress_path")
        progress_path = Path(str(progress_path_value)) if progress_path_value else None

        def _progress(event: str, **payload: Any) -> None:
            if progress_path is None:
                return
            record = {
                "event": event,
                "time": time.time(),
                **payload,
            }
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            with progress_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")

        reports: dict[str, ValidatorReport] = {}
        all_pass = True
        total_weight = 0.0
        weighted_sum = 0.0
        for validator in self._validators:
            _progress("validator_start", validator=validator.name)
            missing_deps = _missing_stage_dependencies(validator, runtime, reports)
            if missing_deps:
                report = _dependency_failure_report(validator, missing_deps, asset)
            else:
                report = validator.evaluate(runtime, asset, artifacts)
            _progress(
                "validator_end",
                validator=validator.name,
                passes=bool(report.get("passes", False)),
                diagnostic_count=len(report.get("diagnostics", []) or []),
            )
            reports[validator.name] = report
            # Publish this validator's evidence into runtime under its name so
            # downstream validators (flow reads semantic+visual, visual reads
            # semantic) observe the same state the legacy sequential caller
            # prepared. Idempotent rewrite: every pipeline run overwrites.
            runtime[validator.name] = report.get("evidence", {})
            if not report.get("passes", False):
                all_pass = False
            weight = float(getattr(validator, "weight", 1.0))
            total_weight += weight
            weighted_sum += weight * float(report.get("score", 0.0))
        if not self._validators:
            score = 1.0
            all_pass = True
        else:
            score = weighted_sum / total_weight if total_weight > 0 else 0.0
        return {
            "validators": reports,
            "certified": bool(all_pass),
            "score": round(float(score), 6),
            "threshold": 0.0,
        }


def _missing_stage_dependencies(
    validator: Validator,
    runtime: dict[str, Any],
    reports: dict[str, ValidatorReport],
) -> list[str]:
    missing: list[str] = []
    for dependency in getattr(validator, "stage_dependencies", []) or []:
        if dependency in reports:
            continue
        stage_state = runtime.get(dependency)
        if not isinstance(stage_state, dict) or not isinstance(stage_state.get("bundle"), dict):
            missing.append(str(dependency))
    return missing


def _dependency_failure_report(
    validator: Validator,
    missing_deps: list[str],
    asset: dict[str, Any],
) -> ValidatorReport:
    validator_name = getattr(validator, "name", "validator")
    missing = sorted(missing_deps)
    return ValidatorReport(
        name=validator_name,
        score=0.0,
        passes=False,
        diagnostics=[
            {
                "code": "L6001",
                "name": "missing_stage_dependency",
                "severity": "error",
                "phase": "validate",
                "asset": asset.get("name"),
                "stage": "validate",
                "validator": validator_name,
                "path": f"runtime.{missing[0]}.bundle",
                "message": (
                    f"Validator '{validator_name}' cannot run because required stage "
                    f"bundle(s) are missing or invalid: {missing}."
                ),
                "details": {"missing_dependencies": missing},
                "suggested_repairs": ["rerun_required_stage"],
            }
        ],
        evidence={},
        subreports={},
    )
