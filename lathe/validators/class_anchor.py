"""Class Anchor Validator — category-conditioned visible-quality rubric.

Per ``docs/research/newresearch.md`` §15: a flat-shaded watertight
cube can be geometrically valid and still fail as an asset. The
``class_anchor`` validator checks structural evidence for the class
(crate / door / panel / terminal / weapon) — bounded volume, required
parts present, material separation, scale plausibility, silhouette
non-trivial — before any CLIP/VLM scoring kicks in.

Each rubric is a declarative JSON pack at
``std/procedural/knowledge/rubric/<class>.json``. The validator emits
a diagnostic with a structured ``evidence`` dict + ``repair_actions``
list that the repair_loop classifier consumes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VERSION = "lathe.validate.class_anchor_v1"

_RUBRIC_ROOT = Path(__file__).resolve().parents[2] / "std" / "procedural" / "knowledge" / "rubric"


@dataclass(frozen=True)
class RubricCheck:
    """One row in a class anchor rubric.

    - ``evidence_key``: the boolean-ish field this check produces.
    - ``check_kind``: how the validator computes the value
      (``synthesized_role_present``, ``bounding_volume_in_range``,
      ``mesh_extents_exceed_intent``, ``material_zone_count_at_least``,
      ``face_count_at_least``).
    - ``parameters``: per-kind parameters (e.g. role name, min count).
    - ``severity``: ``required`` (fail-on-miss) or ``soft``.
    - ``repair_action``: what to do if the check fails — name maps to
      the repair_executor allowlist + the repair_loop's shape repair
      route action set.
    """

    evidence_key: str
    check_kind: str
    parameters: Mapping[str, Any]
    severity: str = "required"
    repair_action: str = ""


@dataclass(frozen=True)
class ClassAnchorRubric:
    """A class anchor rubric — declarative + family-blind."""

    rubric_id: str
    asset_class: str
    description: str
    checks: tuple[RubricCheck, ...]
    minimum_pass_fraction: float = 0.7

    def required_checks(self) -> tuple[RubricCheck, ...]:
        return tuple(c for c in self.checks if c.severity == "required")


def _check_from_dict(d: Mapping[str, Any]) -> RubricCheck:
    return RubricCheck(
        evidence_key=str(d.get("evidence_key") or d.get("name") or ""),
        check_kind=str(d.get("check_kind") or d.get("kind") or "synthesized_role_present"),
        parameters=dict(d.get("parameters") or {}),
        severity=str(d.get("severity") or "required"),
        repair_action=str(d.get("repair_action") or ""),
    )


def rubric_from_dict(payload: Mapping[str, Any]) -> ClassAnchorRubric:
    checks = tuple(
        _check_from_dict(c) for c in (payload.get("checks") or []) if isinstance(c, Mapping)
    )
    return ClassAnchorRubric(
        rubric_id=str(payload.get("id") or payload.get("rubric_id") or ""),
        asset_class=str(payload.get("asset_class") or ""),
        description=str(payload.get("description") or ""),
        checks=checks,
        minimum_pass_fraction=float(payload.get("minimum_pass_fraction", 0.7)),
    )


_RUBRIC_CACHE: dict[str, ClassAnchorRubric] | None = None


def load_all_rubrics(root: Path | None = None) -> Mapping[str, ClassAnchorRubric]:
    global _RUBRIC_CACHE
    if _RUBRIC_CACHE is not None:
        return _RUBRIC_CACHE
    knowledge_root = root or _RUBRIC_ROOT
    if not knowledge_root.exists():
        _RUBRIC_CACHE = {}
        return _RUBRIC_CACHE
    rubrics: dict[str, ClassAnchorRubric] = {}
    for json_path in sorted(knowledge_root.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        rubric = rubric_from_dict(payload)
        if rubric.rubric_id:
            rubrics[rubric.rubric_id] = rubric
    _RUBRIC_CACHE = rubrics
    return rubrics


def reset_rubric_cache() -> None:
    global _RUBRIC_CACHE
    _RUBRIC_CACHE = None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _runtime_assessment(runtime: dict[str, Any]) -> dict[str, Any]:
    shape = _as_dict(runtime.get("shape"))
    bundle = _as_dict(shape.get("bundle"))
    candidates = bundle.get("runtime_candidates") or []
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            meta = _as_dict(first.get("meta"))
            return _as_dict(meta.get("shape_assessment"))
    return _as_dict(bundle.get("shape_assessment"))


def _runtime_synthesized_roles(runtime: dict[str, Any]) -> set[str]:
    shape = _as_dict(runtime.get("shape"))
    bundle = _as_dict(shape.get("bundle"))
    scaffold_report = _as_dict(bundle.get("scaffold_report"))
    candidates = bundle.get("runtime_candidates") or []
    roles: set[str] = set()
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            meta = _as_dict(first.get("meta"))
            ir = _as_dict(meta.get("shape_ir"))
            for node in ir.get("synthesized_graph_nodes") or []:
                if isinstance(node, Mapping):
                    role = node.get("node_type") or node.get("role")
                    if isinstance(role, str):
                        roles.add(role)
    for node in (bundle.get("synthesized_graph_nodes") or scaffold_report.get("synthesized_graph_nodes") or []):
        if isinstance(node, Mapping):
            role = node.get("node_type") or node.get("role")
            if isinstance(role, str):
                roles.add(role)
            node_id = node.get("node_id")
            if isinstance(node_id, str):
                for token in node_id.replace("_", ".").split("."):
                    if token:
                        roles.add(token)
    # Also scan the program ops for role mentions.
    program = _as_dict(bundle.get("shape_program") or scaffold_report.get("shape_program"))
    for op in program.get("ops") or []:
        if isinstance(op, Mapping):
            purpose = op.get("purpose")
            if isinstance(purpose, str):
                # purposes look like "procedural_handle.bar"
                tokens = purpose.split(".")
                for t in tokens:
                    if t.startswith("procedural_"):
                        roles.add(t[len("procedural_"):])
    return roles


def _runtime_face_count(runtime: dict[str, Any]) -> int:
    topology = _as_dict(runtime.get("topology"))
    bundle = _as_dict(topology.get("bundle"))
    stats = _as_dict(bundle.get("mesh_stats"))
    raw = stats.get("triangle_count") or stats.get("face_count")
    return int(raw or 0)


def _runtime_mesh_extents(runtime: dict[str, Any]) -> dict[str, float] | None:
    topology = _as_dict(runtime.get("topology"))
    bundle = _as_dict(topology.get("bundle"))
    stats = _as_dict(bundle.get("mesh_stats"))
    extents = stats.get("extents")
    if isinstance(extents, list) and len(extents) >= 3:
        try:
            return {"x": float(extents[0]), "y": float(extents[1]), "z": float(extents[2])}
        except (TypeError, ValueError):
            return None
    return None


def _runtime_material_zone_count(runtime: dict[str, Any]) -> int:
    shape = _as_dict(runtime.get("shape"))
    bundle = _as_dict(shape.get("bundle"))
    scaffold_report = _as_dict(bundle.get("scaffold_report"))
    program = _as_dict(bundle.get("shape_program") or scaffold_report.get("shape_program"))
    zones = 0
    for op in program.get("ops") or []:
        if isinstance(op, Mapping) and op.get("op") == "op.material_zone":
            zones += 1
    return zones


def _evaluate_check(check: RubricCheck, asset: dict[str, Any], runtime: dict[str, Any]) -> bool:
    kind = check.check_kind
    params = check.parameters
    if kind == "synthesized_role_present":
        roles = _runtime_synthesized_roles(runtime)
        # Accept either exact match or substring match against role names.
        target = str(params.get("role") or "")
        if not target:
            return False
        if target in roles:
            return True
        for r in roles:
            if target in r or r in target:
                return True
        return False
    if kind == "face_count_at_least":
        min_count = int(params.get("min", 200))
        return _runtime_face_count(runtime) >= min_count
    if kind == "bounding_volume_in_range":
        extents = _runtime_mesh_extents(runtime)
        if extents is None:
            return False
        for axis in ("x", "y", "z"):
            bounds = params.get(f"{axis}_range_cm")
            if isinstance(bounds, list) and len(bounds) == 2:
                v = extents.get(axis, 0.0)
                if not (float(bounds[0]) <= v <= float(bounds[1])):
                    return False
        return True
    if kind == "material_zone_count_at_least":
        min_count = int(params.get("min", 1))
        return _runtime_material_zone_count(runtime) >= min_count
    if kind == "mesh_extents_exceed_intent":
        # At least one axis exceeds intent by > threshold_cm
        threshold = float(params.get("threshold_cm", 1.0))
        extents = _runtime_mesh_extents(runtime)
        if extents is None:
            return False
        # Best-effort intent dims via asset.intent.scale.
        intent = asset.get("intent") if isinstance(asset, dict) else None
        if not isinstance(intent, Mapping):
            return False
        scale = intent.get("scale")
        if isinstance(scale, Mapping) and scale.get("type") == "unit":
            try:
                value = float(scale.get("value", 0.0))
                unit = str(scale.get("unit", "cm")).lower()
                d = value * 100.0 if unit == "m" else value
            except (TypeError, ValueError):
                d = 0.0
            if d <= 0:
                return True
            for axis in ("x", "y", "z"):
                if extents.get(axis, 0.0) > d + threshold:
                    return True
            return False
        return True
    return False


def evaluate_class_anchor(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Run the appropriate class anchor rubric for the asset's class.

    The class is taken from ``asset.intent.kind`` or ``asset.kind``.
    Falls back to no-op if no rubric is registered.
    """
    asset_kind = ""
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if isinstance(intent, Mapping):
        raw = intent.get("kind") or asset.get("kind")
        if isinstance(raw, str):
            asset_kind = raw.strip().lower()
    elif isinstance(asset.get("kind"), str):
        asset_kind = asset["kind"].strip().lower()

    # Map asset_kind → rubric_id.
    kind_to_rubric = {
        "hard_surface_prop": "crate_v1",
        "shipping_prop": "crate_v1",
        "container": "crate_v1",
        "industrial_prop": "crate_v1",
        "env_module": "door_v1",
        "wall_module": "panel_v1",
        "mechanical_prop": "panel_v1",
        "interactable": "terminal_v1",
        "weapon_prop": "weapon_v1",
    }
    rubric_id = kind_to_rubric.get(asset_kind)
    if rubric_id is None:
        return {"version": VERSION, "metrics": {"asset_kind": asset_kind, "rubric_id": None}, "diagnostics": []}

    rubrics = load_all_rubrics()
    rubric = rubrics.get(rubric_id)
    if rubric is None:
        return {"version": VERSION, "metrics": {"asset_kind": asset_kind, "rubric_id": rubric_id, "loaded": False}, "diagnostics": []}

    evidence: dict[str, bool] = {}
    check_severity_by_evidence: dict[str, str] = {}
    repair_actions_by_evidence: dict[str, str] = {}
    failed_required: list[RubricCheck] = []
    for check in rubric.checks:
        passed = _evaluate_check(check, asset, runtime)
        evidence[check.evidence_key] = passed
        check_severity_by_evidence[check.evidence_key] = check.severity
        if check.repair_action:
            repair_actions_by_evidence[check.evidence_key] = check.repair_action
        if not passed and check.severity == "required":
            failed_required.append(check)

    pass_fraction = (
        sum(1 for v in evidence.values() if v) / len(evidence) if evidence else 0.0
    )
    metrics: dict[str, Any] = {
        "asset_kind": asset_kind,
        "rubric_id": rubric_id,
        "evidence": evidence,
        "check_severity_by_evidence": check_severity_by_evidence,
        "failed_required_evidence": [check.evidence_key for check in failed_required],
        "repair_actions_by_evidence": repair_actions_by_evidence,
        "pass_fraction": round(pass_fraction, 3),
        "minimum_pass_fraction": rubric.minimum_pass_fraction,
        "failed_required_count": len(failed_required),
    }

    diagnostics: list[dict[str, Any]] = []
    if failed_required or pass_fraction < rubric.minimum_pass_fraction:
        repair_actions = [c.repair_action for c in failed_required if c.repair_action]
        diagnostics.append(
            {
                "code": "L6500",
                "name": f"class_anchor_fail.{rubric_id}",
                "severity": "warning",
                "phase": "validate",
                "stage": "validate",
                "asset": asset.get("name"),
                "path": f"validate.class_anchor.{rubric_id}",
                "message": (
                    f"Class anchor rubric {rubric_id!r} failed: "
                    f"{len(failed_required)} required checks did not pass "
                    f"(pass_fraction={pass_fraction:.2f} < "
                    f"{rubric.minimum_pass_fraction})"
                ),
                "details": metrics,
                "repair_actions": list(dict.fromkeys(repair_actions)),
            }
        )
    return {"version": VERSION, "metrics": metrics, "diagnostics": diagnostics}


__all__ = [
    "VERSION",
    "RubricCheck",
    "ClassAnchorRubric",
    "rubric_from_dict",
    "load_all_rubrics",
    "reset_rubric_cache",
    "evaluate_class_anchor",
]
