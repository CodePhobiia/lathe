"""Expression/critic/rule evaluators for the validate stage.

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

import re
from typing import Any

from .common import unit_to_bytes, unit_to_px_per_m
from .errors import BuildError

IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def evaluate_rule(expr: Any, asset: dict[str, Any], runtime: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Evaluate rule.

    Args:
        expr: expr argument.
        asset: asset argument.
        runtime: runtime argument.

    Returns:
        The result.
    """
    value = evaluate_expression(expr, asset, runtime)
    if isinstance(value, bool):
        return value, {"message": f"Rule {'passed' if value else 'failed'}", "value": value}
    if isinstance(value, (int, float)):
        passed = float(value) >= 0.5
        return passed, {"message": f"Numeric rule {'passed' if passed else 'failed'}", "value": value}
    return False, {"message": f"Unsupported rule result: {value!r}"}


def evaluate_expression(expr: Any, asset: dict[str, Any], runtime: dict[str, Any]) -> Any:
    """Evaluate expression.

    Args:
        expr: expr argument.
        asset: asset argument.
        runtime: runtime argument.

    Returns:
        The result.
    """
    if isinstance(expr, (bool, int, float, str)):
        if isinstance(expr, str):
            if expr in _predicate_dispatch():
                return _predicate_dispatch()[expr](asset, runtime, {})
            if expr in _metric_dispatch():
                return _metric_dispatch()[expr](asset, runtime)
        return expr
    if isinstance(expr, dict):
        etype = expr.get("type")
        if etype == "call":
            name = expr["name"]
            kwargs = {
                item["name"] if item.get("name") is not None else f"_{idx}": item["value"]
                for idx, item in enumerate(expr.get("args", []))
            }
            if name in _predicate_dispatch():
                return _predicate_dispatch()[name](asset, runtime, kwargs)
            if name in _metric_dispatch():
                return _metric_dispatch()[name](asset, runtime)
            raise BuildError(f"Unsupported builtin '{name}' in runtime evaluator")
        if etype == "range":
            return expr
        if etype == "unary":
            value = evaluate_expression(expr["value"], asset, runtime)
            if expr["op"] == "not":
                return not bool(value)
            if expr["op"] == "-":
                return -float(value)
        if etype == "binary":
            left = evaluate_expression(expr["left"], asset, runtime)
            right = evaluate_expression(expr["right"], asset, runtime)
            op = expr["op"]
            if op == "and":
                return bool(left) and bool(right)
            if op == "or":
                return bool(left) or bool(right)
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                return left / right
            if op == "in":
                return left in right
    raise BuildError(f"Unsupported expression: {expr!r}")


def _predicate_dispatch() -> dict[str, Any]:
    return {
        "manifold": lambda asset, runtime, kwargs: bool(
            runtime["topology"]["bundle"]["mesh_stats"]["watertight"]
        ),
        "watertight": lambda asset, runtime, kwargs: bool(
            runtime["topology"]["bundle"]["mesh_stats"]["watertight"]
        ),
        "lightmap_uvs": lambda asset, runtime, kwargs: any(
            item["name"] == "lightmap" for item in runtime["uv"]["bundle"]["uv_sets"]
        ),
        "collision_proxy": lambda asset, runtime, kwargs: bool(
            runtime["physics"]["bundle"]["collision_proxy"]
        ),
        "material_slots": lambda asset, runtime, kwargs: (
            int(runtime["surface"]["bundle"]["material_slots"]) <= int(kwargs.get("max", 999999))
        ),
        "uv_range": _predicate_uv_range,
        "texel_density": _predicate_texel_density,
        "runtime_budget": _predicate_runtime_budget,
        "pivots": _predicate_pivots,
        "names": _predicate_names,
        "units": lambda asset, runtime, kwargs: kwargs.get("_0") == "cm" or kwargs.get("unit") == "cm",
        "lods": lambda asset, runtime, kwargs: (
            len(runtime["optimize"]["bundle"]["lods"]) >= int(kwargs.get("min", 1))
        ),
        "triangles": lambda asset, runtime, kwargs: (
            int(runtime["topology"]["bundle"]["mesh_stats"]["triangle_count"])
            <= int(kwargs.get("max", 99999999))
        ),
        "texture_budget": lambda asset, runtime, kwargs: (
            int(runtime["optimize"]["bundle"]["texture_memory_bytes"]) <= unit_to_bytes(kwargs.get("max"))
        ),
        "socket_count": lambda asset, runtime, kwargs: (
            len(runtime["interfaces"]["bundle"].get("sockets", [])) >= int(kwargs.get("min", 0))
        ),
        "riggable": _predicate_riggable,
    }


def _predicate_uv_range(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    set_name = kwargs.get("set") or kwargs.get("_0")
    target_range = kwargs.get("range")
    if not isinstance(target_range, dict):
        return False
    for uv_set in runtime["uv"]["bundle"]["uv_sets"]:
        if uv_set["name"] != set_name:
            continue
        coverage = uv_set["coverage"]
        return (
            coverage["u_min"] >= float(target_range["from"]) - 1e-6
            and coverage["u_max"] <= float(target_range["to"]) + 1e-6
            and coverage["v_min"] >= float(target_range["from"]) - 1e-6
            and coverage["v_max"] <= float(target_range["to"]) + 1e-6
        )
    return False


def _predicate_texel_density(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    requested = kwargs.get("target")
    tolerance = float(kwargs.get("tolerance", 0.10))
    actual = runtime["uv"]["bundle"]["texel_density"].get("actual_px_per_m")
    if requested is None or actual is None:
        return False
    target_value = unit_to_px_per_m(requested)
    if target_value == 0:
        return False
    return abs(actual - target_value) / target_value <= tolerance + 1e-9


def _predicate_runtime_budget(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    draw_calls_ok = runtime["optimize"]["bundle"]["draw_calls"] <= int(kwargs.get("draw_calls", 99999999))
    texture_memory_ok = runtime["optimize"]["bundle"]["texture_memory_bytes"] <= unit_to_bytes(
        kwargs.get("texture_memory")
    )
    return draw_calls_ok and texture_memory_ok


def _predicate_names(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    names = [asset["name"]]
    names.extend(asset.get("intent", {}).get("parts", []))
    names.extend(item.get("name") for item in runtime["rig"]["bundle"].get("joints", []))
    names.extend(item.get("name") for item in runtime["interfaces"]["bundle"].get("sockets", []))
    names.extend(item.get("name") for item in runtime["interfaces"]["bundle"].get("pivots", []))
    names.extend(item.get("name") for item in runtime["interfaces"]["bundle"].get("anchors", []))
    return all(name is not None and IDENT_RE.match(str(name)) for name in names)


def _predicate_pivots(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    desired_policy = kwargs.get("policy") or kwargs.get("_0") or "auto"
    rig_bundle = runtime["rig"]["bundle"]
    actual_policy = rig_bundle.get("pivot_policy", "auto")
    joints = rig_bundle.get("joints", [])
    if joints:
        return actual_policy == desired_policy and all("pivot" in joint for joint in joints)
    # Static assets still have an object/world pivot even when they have no joint list.
    return actual_policy in {desired_policy, "auto"}


def _predicate_riggable(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    required_parts = kwargs.get("parts", [])
    if not isinstance(required_parts, list):
        return False
    joint_names = {item["name"] for item in runtime["rig"]["bundle"].get("joints", [])}
    return all(part in joint_names for part in required_parts)


def _metric_dispatch() -> dict[str, Any]:
    return {
        "prompt_match": _metric_prompt_match,
        "silhouette_readability": _metric_silhouette_readability,
        "topology_quality": _metric_topology_quality,
        "material_quality": _metric_material_quality,
        "runtime_efficiency": _metric_runtime_efficiency,
        "part_coherence": _metric_part_coherence,
        "uv_quality": _metric_uv_quality,
        "assembly_compatibility": _metric_assembly_compatibility,
        "surface_consistency": _metric_surface_consistency,
    }


def _metric_prompt_match(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    from ..validators.semantic_quality import _resolve_part_bboxes

    expected_parts = set(asset.get("intent", {}).get("parts", []))
    actual_parts = {group["name"] for group in _resolve_part_bboxes(runtime["topology"]["bundle"])}
    part_ratio = len(expected_parts & actual_parts) / max(1, len(expected_parts))
    visual = runtime.get("visual_quality", {}).get("metrics", {})
    return round(
        min(
            1.0,
            0.26
            + 0.22 * part_ratio
            + 0.16 * visual.get("silhouette_complexity", 0.0)
            + 0.12 * (1.0 - visual.get("primitive_likeness_penalty", 0.0))
            + 0.08 * visual.get("attachment_integration_quality", 0.0),
        ),
        6,
    )


def _metric_silhouette_readability(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    if runtime.get("semantic_quality"):
        visual = runtime.get("visual_quality", {}).get("metrics", {})
        return round(
            min(
                1.0,
                0.60 * float(runtime["semantic_quality"]["metrics"]["silhouette_fidelity"])
                + 0.25 * visual.get("silhouette_complexity", 0.0)
                + 0.15 * visual.get("edge_readability", 0.0),
            ),
            6,
        )
    extents = runtime["topology"]["bundle"]["mesh_stats"]["extents"]
    largest = max(extents)
    smallest = max(1e-6, min(extents))
    ratio = smallest / largest
    return round(max(0.7, min(0.98, 0.7 + 0.4 * ratio)), 6)


def _metric_topology_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    if runtime.get("semantic_quality"):
        metrics = runtime["semantic_quality"]["metrics"]
        visual = runtime.get("visual_quality", {}).get("metrics", {})
        score = (
            0.22 * metrics["structural_richness"]
            + 0.16 * metrics["component_score"]
            + 0.18 * metrics["symmetry_score"]
            + 0.14 * metrics["adjacency_score"]
            + 0.12 * (1.0 - metrics["fragmentation_penalty"])
            + 0.10 * visual.get("detail_density", 0.0)
            + 0.04 * visual.get("edge_readability", 0.0)
            + 0.14 * visual.get("geometry_integration_quality", 0.0)
        )
        if metrics["toy_detected"]:
            score -= 0.18
        score -= 0.10 * visual.get("primitive_likeness_penalty", 0.0)
        score -= 0.08 * visual.get("assembled_primitives_penalty", 0.0)
        return round(min(1.0, max(0.0, score)), 6)
    stats = runtime["topology"]["bundle"]["mesh_stats"]
    score = 0.6
    if stats["watertight"]:
        score += 0.25
    if stats["body_count"] >= 1:
        score += 0.1
    if stats["triangle_count"] > 0:
        score += 0.05
    return round(min(score, 1.0), 6)


def _metric_material_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    maps = runtime["surface"]["bundle"].get("maps", [])
    workflow = runtime["surface"]["bundle"]["surface_manifest"].get("workflow")
    visual = runtime.get("visual_quality", {}).get("metrics", {})
    score = 0.30
    if workflow in {"pbr_metal_rough", "pbr_spec_gloss"}:
        score += 0.08
    score += 0.012 * min(5, len(maps))
    score += 0.06 * visual.get("feature_coherence", 0.0)
    score += 0.22 * visual.get("surface_authoring_quality", 0.0)
    score += 0.10 * visual.get("surface_material_zone_coherence", 0.0)
    return round(min(score, 0.74), 6)


def _metric_runtime_efficiency(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    tris = runtime["topology"]["bundle"]["mesh_stats"]["triangle_count"]
    draw_calls = runtime["optimize"]["bundle"]["draw_calls"]
    score = 1.0
    score -= min(0.15, tris / 500000.0)
    score -= min(0.1, draw_calls * 0.03)
    return round(max(0.7, score), 6)


def _metric_part_coherence(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    if runtime.get("semantic_quality"):
        metrics = runtime["semantic_quality"]["metrics"]
        visual = runtime.get("visual_quality", {}).get("metrics", {})
        return round(
            min(
                1.0,
                0.28 * metrics["part_coverage"]
                + 0.16 * metrics["symmetry_score"]
                + 0.14 * metrics["interface_score"]
                + 0.14 * metrics["adjacency_score"]
                + 0.08 * (1.0 - metrics["fragmentation_penalty"])
                + 0.10 * visual.get("attachment_integration_quality", 0.0)
                + 0.10 * visual.get("support_plausibility", 0.0),
            ),
            6,
        )
    from ..validators.semantic_quality import _resolve_part_bboxes

    expected_parts = set(asset.get("intent", {}).get("parts", []))
    actual_parts = {group["name"] for group in _resolve_part_bboxes(runtime["topology"]["bundle"])}
    ratio = len(expected_parts & actual_parts) / max(1, len(expected_parts))
    return round(min(1.0, 0.8 + 0.2 * ratio), 6)


def _metric_uv_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    if not runtime["uv"]["bundle"]["uv_sets"]:
        return 0.0
    base = runtime["uv"]["bundle"]["uv_sets"][0]["coverage"]
    in_range = all(0.0 <= base[key] <= 1.0 for key in base)
    return 0.95 if in_range else 0.4


def _metric_assembly_compatibility(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    sockets = len(runtime["interfaces"]["bundle"].get("sockets", []))
    pivots = len(runtime["interfaces"]["bundle"].get("pivots", []))
    anchors = len(runtime["interfaces"]["bundle"].get("anchors", []))
    return round(min(1.0, 0.75 + 0.05 * (sockets + pivots + anchors)), 6)


def _metric_surface_consistency(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    semantic = len(runtime["surface"]["bundle"]["surface_manifest"].get("semantic_materials", []))
    visual = runtime.get("visual_quality", {}).get("metrics", {})
    return round(
        min(
            0.95,
            0.54
            + 0.03 * semantic
            + 0.18 * visual.get("surface_authoring_quality", 0.0)
            + 0.10 * visual.get("surface_material_zone_coherence", 0.0),
        ),
        6,
    )


def evaluate_metric(expr: Any, asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    """Evaluate metric.

    Args:
        expr: expr argument.
        asset: asset argument.
        runtime: runtime argument.

    Returns:
        The result.
    """
    value = evaluate_expression(expr, asset, runtime)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    raise BuildError(f"Metric expression did not resolve to score: {expr!r}")


def evaluate_critic(
    name: Any,
    asset: dict[str, Any],
    runtime: dict[str, Any],
    critics: dict[str, Any],
    rules: list[dict[str, Any]],
) -> float:
    """Evaluate critic.

    Args:
        name: name argument.
        asset: asset argument.
        runtime: runtime argument.
        critics: critics argument.
        rules: rules argument.

    Returns:
        The result.
    """
    if not name:
        prefer_rules = [rule for rule in rules if rule.get("kind") == "prefer"]
        if not prefer_rules:
            return 1.0
        total_weight = sum(float(rule.get("weight", 1.0)) for rule in prefer_rules)
        if total_weight <= 0:
            return 0.0
        total = 0.0
        for rule in prefer_rules:
            weight = float(rule.get("weight", 1.0)) / total_weight
            total += evaluate_metric(rule["expr"], asset, runtime) * weight
        return round(total, 6)
    if name not in critics:
        raise BuildError(f"Unknown critic '{name}'")
    critic = critics[name]
    body = critic.get("body")
    if isinstance(body, dict) and body.get("type") == "weighted":
        total_weight = sum(float(item.get("weight", 0.0)) for item in body.get("items", []))
        if total_weight <= 0:
            return 0.0
        total = 0.0
        for item in body.get("items", []):
            metric = item["metric"]
            score = _metric_dispatch()[metric](asset, runtime)
            total += score * (float(item.get("weight", 0.0)) / total_weight)
        return round(total, 6)
    return evaluate_metric(body, asset, runtime)
