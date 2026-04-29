"""Deterministic Wonder scene benchmark report helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

SCENE_BENCHMARK_REPORT_VERSION = "lathe.scene_benchmark_report.v1"
SCENE_BENCHMARK_REPORT_SCHEMA_FILENAME = "scene_benchmark_report.schema.json"
SCENE_BENCHMARK_REPORT_CONTRACT = "scene_benchmark_report"

BRIEF_BUDGET_MS = 10_000
SCENE_GRAPH_BUDGET_MS = 20_000
SOURCE_GENERATION_BUDGET_MS = 10_000
CHECK_PLAN_BUDGET_MS = 5_000
PREVIEW_BUILD_BUDGET_MS = 60_000
PREVIEW_RENDER_BUDGET_MS = 30_000
PATCH_PREVIEW_BUDGET_MS = 45_000
FINAL_EXPORT_BUDGET_MS = 180_000

PREVIEW_BUDGETS_MS: dict[str, int] = {
    "brief": BRIEF_BUDGET_MS,
    "scene_graph": SCENE_GRAPH_BUDGET_MS,
    "source_generation": SOURCE_GENERATION_BUDGET_MS,
    "check_plan": CHECK_PLAN_BUDGET_MS,
    "preview_build": PREVIEW_BUILD_BUDGET_MS,
    "preview_render": PREVIEW_RENDER_BUDGET_MS,
    "patch_preview": PATCH_PREVIEW_BUDGET_MS,
}

FINAL_BUDGETS_MS: dict[str, int] = {
    "brief": BRIEF_BUDGET_MS,
    "scene_graph": SCENE_GRAPH_BUDGET_MS,
    "source_generation": SOURCE_GENERATION_BUDGET_MS,
    "check_plan": CHECK_PLAN_BUDGET_MS,
    "final_export": FINAL_EXPORT_BUDGET_MS,
}

TIME_TO_FIRST_RENDER_BUDGET_MS = (
    BRIEF_BUDGET_MS
    + SCENE_GRAPH_BUDGET_MS
    + SOURCE_GENERATION_BUDGET_MS
    + CHECK_PLAN_BUDGET_MS
    + PREVIEW_BUILD_BUDGET_MS
    + PREVIEW_RENDER_BUDGET_MS
)

CACHE_REUSE_RATIO_THRESHOLD = 0.25

FINAL_EXPORT_ALLOWED_EXCEPTIONS: tuple[str, ...] = (
    "external_exporter_unavailable",
    "manual_review_required",
    "target_runtime_unavailable",
)

SCORE_THRESHOLDS: dict[str, float] = {
    "prompt_to_brief": 0.80,
    "brief_to_scene": 0.80,
    "parse_check": 1.00,
    "build_success": 1.00,
    "scene_validation": 0.85,
    "style_consistency": 0.80,
    "object_count_accuracy": 0.80,
    "render_quality": 0.80,
    "patch_success": 1.00,
    "continuity_preservation": 0.85,
    "export_validity": 1.00,
}

_STAGE_LABELS: dict[str, str] = {
    "brief": "Dream Brief",
    "scene_graph": "Scene Graph",
    "source_generation": "Scene source generation",
    "check_plan": "Check and plan",
    "preview_build": "Preview build",
    "preview_render": "Preview render",
    "patch_preview": "Patch preview",
    "final_export": "Final export",
}

_SCORE_LABELS: dict[str, str] = {
    "prompt_to_brief": "Prompt to brief",
    "brief_to_scene": "Brief to scene",
    "parse_check": "Parse and check",
    "build_success": "Build success",
    "scene_validation": "Scene validation",
    "style_consistency": "Style consistency",
    "object_count_accuracy": "Object count accuracy",
    "render_quality": "Render quality",
    "patch_success": "Patch success",
    "continuity_preservation": "Continuity preservation",
    "export_validity": "Export validity",
}

_FIRST_RENDER_STAGES = (
    "brief",
    "scene_graph",
    "source_generation",
    "check_plan",
    "preview_build",
    "preview_render",
)

_SOURCE_FIELDS = ("source_asset", "lathe_asset", "source_family", "source_kit")
_CACHE_FIELDS = ("material_bindings", "state")

StageMode = Literal["shared", "preview", "final"]
StageStatus = Literal["passed", "failed", "missing", "excepted"]
ScoreStatus = Literal["passed", "failed", "missing"]
CacheStatus = Literal["passed", "failed", "missing", "skipped"]


@dataclass(frozen=True)
class StageBudget:
    """Ordered timing budget for one Wonder benchmark stage."""

    stage: str
    label: str
    mode: StageMode
    budget_ms: int


STAGE_BUDGETS: tuple[StageBudget, ...] = (
    StageBudget("brief", _STAGE_LABELS["brief"], "shared", BRIEF_BUDGET_MS),
    StageBudget("scene_graph", _STAGE_LABELS["scene_graph"], "shared", SCENE_GRAPH_BUDGET_MS),
    StageBudget("source_generation", _STAGE_LABELS["source_generation"], "shared", SOURCE_GENERATION_BUDGET_MS),
    StageBudget("check_plan", _STAGE_LABELS["check_plan"], "shared", CHECK_PLAN_BUDGET_MS),
    StageBudget("preview_build", _STAGE_LABELS["preview_build"], "preview", PREVIEW_BUILD_BUDGET_MS),
    StageBudget("preview_render", _STAGE_LABELS["preview_render"], "preview", PREVIEW_RENDER_BUDGET_MS),
    StageBudget("patch_preview", _STAGE_LABELS["patch_preview"], "preview", PATCH_PREVIEW_BUDGET_MS),
    StageBudget("final_export", _STAGE_LABELS["final_export"], "final", FINAL_EXPORT_BUDGET_MS),
)


def _schema_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / SCENE_BENCHMARK_REPORT_SCHEMA_FILENAME
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{SCENE_BENCHMARK_REPORT_SCHEMA_FILENAME}")


def get_scene_benchmark_report_schema() -> dict[str, Any]:
    """Return the committed Scene Benchmark Report JSON Schema."""
    return json.loads((_schema_root() / SCENE_BENCHMARK_REPORT_SCHEMA_FILENAME).read_text(encoding="utf-8"))


def validate_scene_benchmark_report_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a Scene Benchmark Report payload."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(get_scene_benchmark_report_schema())
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            {
                "code": "SCENE_BENCHMARK_REPORT_SCHEMA_VALIDATION",
                "severity": "error",
                "contract": SCENE_BENCHMARK_REPORT_CONTRACT,
                "path": _json_pointer(*error.absolute_path),
                "message": error.message,
            }
        )
    return diagnostics


def benchmark_scene(
    scene_graph: Mapping[str, Any],
    timings: Mapping[str, Any],
    scores: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a deterministic Wonder benchmark report from measured inputs.

    Bare numeric timing values are interpreted as seconds to match the existing
    benchmark harness. Mapping values may use ``duration_ms`` or ``duration_s``.
    """
    if not isinstance(scene_graph, Mapping):
        raise ValueError("scene_graph must be a mapping")
    if not isinstance(timings, Mapping):
        raise ValueError("timings must be a mapping")
    if not isinstance(scores, Mapping):
        raise ValueError("scores must be a mapping")

    timing_source = _nested_mapping(timings, "stages", fallback=timings)
    score_source = _nested_mapping(scores, "metrics", fallback=scores)
    stage_results = [_stage_result(budget, timing_source, timings) for budget in STAGE_BUDGETS]
    score_results = [_score_result(metric, threshold, score_source) for metric, threshold in SCORE_THRESHOLDS.items()]
    cache_reuse = _cache_reuse_report(scene_graph, timings)
    time_to_first_render = _time_to_first_render(stage_results)
    status = _overall_status(stage_results, score_results, cache_reuse, time_to_first_render)

    return {
        "schema_version": SCENE_BENCHMARK_REPORT_VERSION,
        "scene_id": _scene_id(scene_graph),
        "scene_version": _scene_version(scene_graph),
        "generated_by": "lathe.scene.bench",
        "status": status,
        "budgets": {
            "preview": dict(PREVIEW_BUDGETS_MS),
            "final": dict(FINAL_BUDGETS_MS),
            "cache_reuse_ratio": CACHE_REUSE_RATIO_THRESHOLD,
            "score_thresholds": dict(SCORE_THRESHOLDS),
            "final_export_allowed_exceptions": list(FINAL_EXPORT_ALLOWED_EXCEPTIONS),
        },
        "summary": {
            "timings": _status_counts(stage_results),
            "scores": _status_counts(score_results),
            "cache_reuse_status": cache_reuse["status"],
            "time_to_first_render": time_to_first_render,
        },
        "scene_metrics": _scene_metrics(scene_graph),
        "stage_results": stage_results,
        "score_results": score_results,
        "cache_reuse": cache_reuse,
    }


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _nested_mapping(source: Mapping[str, Any], key: str, *, fallback: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = source.get(key)
    return nested if isinstance(nested, Mapping) else fallback


def _scene_id(scene_graph: Mapping[str, Any]) -> str:
    scene_id = scene_graph.get("scene_id")
    return scene_id if isinstance(scene_id, str) and scene_id else "scene"


def _scene_version(scene_graph: Mapping[str, Any]) -> int:
    version = scene_graph.get("version")
    if isinstance(version, bool):
        return 1
    if isinstance(version, int) and version > 0:
        return version
    return 1


def _stage_result(
    budget: StageBudget,
    timing_source: Mapping[str, Any],
    raw_timings: Mapping[str, Any],
) -> dict[str, Any]:
    raw = timing_source.get(budget.stage)
    exception = _stage_exception(budget.stage, raw, raw_timings)
    if exception is not None:
        status: StageStatus = "excepted" if exception in FINAL_EXPORT_ALLOWED_EXCEPTIONS else "failed"
        return {
            "stage": budget.stage,
            "label": budget.label,
            "mode": budget.mode,
            "actual_ms": None,
            "budget_ms": budget.budget_ms,
            "ratio": None,
            "status": status,
            "passed": status == "excepted",
            "exception": exception,
        }

    actual_ms = _duration_ms(raw, f"timing {budget.stage}") if raw is not None else None
    if actual_ms is None:
        return {
            "stage": budget.stage,
            "label": budget.label,
            "mode": budget.mode,
            "actual_ms": None,
            "budget_ms": budget.budget_ms,
            "ratio": None,
            "status": "missing",
            "passed": False,
        }
    status = "passed" if actual_ms <= budget.budget_ms else "failed"
    return {
        "stage": budget.stage,
        "label": budget.label,
        "mode": budget.mode,
        "actual_ms": actual_ms,
        "budget_ms": budget.budget_ms,
        "ratio": _ratio(actual_ms, budget.budget_ms),
        "status": status,
        "passed": status == "passed",
    }


def _stage_exception(stage: str, raw: Any, raw_timings: Mapping[str, Any]) -> str | None:
    if stage != "final_export":
        return None
    if isinstance(raw, Mapping):
        exception = raw.get("exception") or raw.get("allowed_exception")
        if isinstance(exception, str) and exception:
            return exception
    exception = raw_timings.get("final_export_exception")
    return exception if isinstance(exception, str) and exception else None


def _duration_ms(raw: Any, label: str) -> int:
    if isinstance(raw, Mapping):
        for key in ("duration_ms", "elapsed_ms", "ms"):
            value = raw.get(key)
            if value is not None:
                return _nonnegative_milliseconds(value, label)
        for key in ("duration_s", "elapsed_s", "seconds", "s"):
            value = raw.get(key)
            if value is not None:
                return _nonnegative_seconds(value, label)
        raise ValueError(f"{label} must include duration_ms or duration_s")
    return _nonnegative_seconds(raw, label)


def _nonnegative_seconds(value: Any, label: str) -> int:
    numeric = _number(value, label)
    return round(numeric * 1000)


def _nonnegative_milliseconds(value: Any, label: str) -> int:
    return round(_number(value, label))


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a non-negative number")
    numeric = float(value)
    if numeric < 0:
        raise ValueError(f"{label} must be a non-negative number")
    return numeric


def _score_result(metric: str, threshold: float, score_source: Mapping[str, Any]) -> dict[str, Any]:
    raw = score_source.get(metric)
    if raw is None:
        return {
            "metric": metric,
            "label": _SCORE_LABELS[metric],
            "actual": None,
            "threshold": threshold,
            "status": "missing",
            "passed": False,
        }
    actual = _score_value(raw, metric)
    status = "passed" if actual >= threshold else "failed"
    return {
        "metric": metric,
        "label": _SCORE_LABELS[metric],
        "actual": actual,
        "threshold": threshold,
        "status": status,
        "passed": status == "passed",
    }


def _score_value(raw: Any, metric: str) -> float:
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    value = _number(raw, f"score {metric}")
    if value > 1.0:
        raise ValueError(f"score {metric} must be between 0.0 and 1.0")
    return round(value, 4)


def _cache_reuse_report(scene_graph: Mapping[str, Any], timings: Mapping[str, Any]) -> dict[str, Any]:
    cache = _cache_mapping(timings)
    hits = _optional_count(cache, timings, ("hits", "cache_hits", "reused"))
    misses = _optional_count(cache, timings, ("misses", "cache_misses"))
    writes = _optional_count(cache, timings, ("writes", "cache_writes"))
    eligible = _optional_count(cache, timings, ("eligible", "eligible_tasks", "lookups", "cache_lookups"))

    if eligible is None and hits is not None and misses is not None:
        eligible = hits + misses
    if misses is None and eligible is not None and hits is not None:
        misses = max(eligible - hits, 0)
    if writes is None:
        writes = 0
    if hits is not None and eligible is not None and hits > eligible:
        raise ValueError("cache hits must not exceed eligible cache lookups")

    potential = _cache_potential(scene_graph)
    if hits is None or eligible is None:
        return {
            "hits": hits,
            "misses": misses,
            "writes": writes,
            "eligible": eligible,
            "reuse_ratio": None,
            "threshold": CACHE_REUSE_RATIO_THRESHOLD,
            "status": "missing",
            "passed": False,
            "potential": potential,
        }
    if eligible == 0:
        return {
            "hits": hits,
            "misses": misses or 0,
            "writes": writes,
            "eligible": eligible,
            "reuse_ratio": None,
            "threshold": CACHE_REUSE_RATIO_THRESHOLD,
            "status": "skipped",
            "passed": True,
            "potential": potential,
        }

    reuse_ratio = round(hits / eligible, 4)
    status = "passed" if reuse_ratio >= CACHE_REUSE_RATIO_THRESHOLD else "failed"
    return {
        "hits": hits,
        "misses": misses or 0,
        "writes": writes,
        "eligible": eligible,
        "reuse_ratio": reuse_ratio,
        "threshold": CACHE_REUSE_RATIO_THRESHOLD,
        "status": status,
        "passed": status == "passed",
        "potential": potential,
    }


def _cache_mapping(timings: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("cache_reuse", "cache"):
        value = timings.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _optional_count(cache: Mapping[str, Any], timings: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for source in (cache, timings):
        for key in keys:
            if key in source:
                return _count(source[key], key)
    return None


def _count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _cache_potential(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    groups: dict[str, int] = {}
    objects = scene_graph.get("objects", [])
    if not isinstance(objects, list):
        objects = []
    for index, item in enumerate(objects):
        if not isinstance(item, Mapping):
            continue
        signature = _cache_signature(index, item)
        groups[signature] = groups.get(signature, 0) + 1

    object_count = sum(groups.values())
    reusable_objects = sum(count - 1 for count in groups.values() if count > 1)
    potential_reuse_ratio = round(reusable_objects / object_count, 4) if object_count else 0.0
    return {
        "objects": object_count,
        "cache_groups": len(groups),
        "reusable_objects": reusable_objects,
        "potential_reuse_ratio": potential_reuse_ratio,
    }


def _cache_signature(index: int, item: Mapping[str, Any]) -> str:
    source = _source_signature(index, item)
    variant = item.get("variant") if isinstance(item.get("variant"), str) else "default"
    cache_relevant = {field: _normal_json(item[field]) for field in _CACHE_FIELDS if field in item}
    payload = {"source": source, "variant": variant, "cache_relevant": cache_relevant}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _source_signature(index: int, item: Mapping[str, Any]) -> dict[str, Any]:
    for field in _SOURCE_FIELDS:
        value = item.get(field)
        if isinstance(value, str) and value:
            return {"kind": field, "ref": value}
    object_id = item.get("object_id")
    fallback = object_id if isinstance(object_id, str) and object_id else f"object_{index:03d}"
    return {"kind": "generated_fallback", "ref": fallback}


def _normal_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normal_json(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_normal_json(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_normal_json(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def _time_to_first_render(stage_results: list[dict[str, Any]]) -> dict[str, Any]:
    results_by_stage = {item["stage"]: item for item in stage_results}
    values: list[int] = []
    missing: list[str] = []
    for stage in _FIRST_RENDER_STAGES:
        actual = results_by_stage[stage]["actual_ms"]
        if isinstance(actual, int):
            values.append(actual)
        else:
            missing.append(stage)
    if missing:
        return {
            "actual_ms": None,
            "budget_ms": TIME_TO_FIRST_RENDER_BUDGET_MS,
            "ratio": None,
            "status": "missing",
            "passed": False,
            "missing_stages": missing,
        }
    actual_ms = sum(values)
    status = "passed" if actual_ms <= TIME_TO_FIRST_RENDER_BUDGET_MS else "failed"
    return {
        "actual_ms": actual_ms,
        "budget_ms": TIME_TO_FIRST_RENDER_BUDGET_MS,
        "ratio": _ratio(actual_ms, TIME_TO_FIRST_RENDER_BUDGET_MS),
        "status": status,
        "passed": status == "passed",
        "missing_stages": [],
    }


def _status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "missing": 0, "excepted": 0}
    for result in results:
        status = str(result.get("status", "missing"))
        if status in counts:
            counts[status] += 1
    return counts


def _overall_status(
    stage_results: list[dict[str, Any]],
    score_results: list[dict[str, Any]],
    cache_reuse: Mapping[str, Any],
    time_to_first_render: Mapping[str, Any],
) -> str:
    failing_statuses = {"failed", "missing"}
    if any(item["status"] in failing_statuses for item in stage_results):
        return "failed"
    if any(item["status"] in failing_statuses for item in score_results):
        return "failed"
    if cache_reuse.get("status") in failing_statuses:
        return "failed"
    if time_to_first_render.get("status") in failing_statuses:
        return "failed"
    if any(item["status"] == "excepted" for item in stage_results):
        return "passed_with_exceptions"
    return "passed"


def _scene_metrics(scene_graph: Mapping[str, Any]) -> dict[str, int]:
    return {
        "regions": _collection_count(scene_graph, "regions"),
        "objects": _collection_count(scene_graph, "objects"),
        "materials": _collection_count(scene_graph, "materials"),
        "lights": _collection_count(scene_graph, "lights"),
        "cameras": _collection_count(scene_graph, "cameras"),
        "curiosity_anchors": _collection_count(scene_graph, "curiosity_anchors"),
        "hidden_state": _collection_count(scene_graph, "hidden_state"),
        "exports": _collection_count(scene_graph, "exports"),
    }


def _collection_count(scene_graph: Mapping[str, Any], key: str) -> int:
    value = scene_graph.get(key, [])
    return len(value) if isinstance(value, list) else 0


__all__ = [
    "BRIEF_BUDGET_MS",
    "CACHE_REUSE_RATIO_THRESHOLD",
    "CHECK_PLAN_BUDGET_MS",
    "FINAL_BUDGETS_MS",
    "FINAL_EXPORT_ALLOWED_EXCEPTIONS",
    "FINAL_EXPORT_BUDGET_MS",
    "PATCH_PREVIEW_BUDGET_MS",
    "PREVIEW_BUDGETS_MS",
    "PREVIEW_BUILD_BUDGET_MS",
    "PREVIEW_RENDER_BUDGET_MS",
    "SCENE_BENCHMARK_REPORT_CONTRACT",
    "SCENE_BENCHMARK_REPORT_SCHEMA_FILENAME",
    "SCENE_BENCHMARK_REPORT_VERSION",
    "SCENE_GRAPH_BUDGET_MS",
    "SCORE_THRESHOLDS",
    "SOURCE_GENERATION_BUDGET_MS",
    "STAGE_BUDGETS",
    "TIME_TO_FIRST_RENDER_BUDGET_MS",
    "StageBudget",
    "benchmark_scene",
    "get_scene_benchmark_report_schema",
    "validate_scene_benchmark_report_payload",
]
