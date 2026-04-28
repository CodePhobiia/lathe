"""Budget evaluator (STAGE-7/8, V0.2 E3).

Evaluates three runtime budgets against the current runtime bundles and emits
a budget report + diagnostics. Three categories:

* texture memory   (STAGE-7, diagnostic L6301)
* material count   (STAGE-8, diagnostic L6302)
* draw calls       (STAGE-8, diagnostic L6303)

Severity escalates to ``error`` once the overage exceeds 25% of the budget;
smaller overages register as ``warning``. Under-budget usage reports
``status="pass"`` with no diagnostic.

The module is intentionally tolerant when upstream stages did not populate
material/texture data (e.g. semantic_passthrough surface path): it falls back
to heuristics (``material_slots``, ``surface_manifest.resolution``, unique
material names in ``material_zones``/``semantic_materials``) and, when none of
those are available, emits a ``status="skipped"`` sub-report rather than
crashing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_TEXTURE_MEMORY_BUDGET_MB: float = 128.0
DEFAULT_MATERIAL_COUNT_BUDGET: int = 16
DEFAULT_DRAW_CALL_BUDGET: int = 64

L_TEXTURE_MEMORY_OVER_BUDGET = "L6301"
L_MATERIAL_COUNT_OVER_BUDGET = "L6302"
L_DRAW_CALL_OVER_BUDGET = "L6303"

# Estimated bytes-per-pixel for each compressed format. KTX2/BC7 is the default
# for hero-quality output; normal (BC5), ORM (BC1), emissive (BC1) compress
# more aggressively so the per-channel estimate is channel-aware below.
_FORMAT_BPP: dict[str, float] = {
    "ktx2": 1.0,
    "bc7": 1.0,
    "bc5": 1.0,
    "bc3": 1.0,
    "bc1": 0.5,
    "astc": 1.0,
    "etc2": 0.5,
    "png": 4.0,
    "jpg": 4.0,
    "jpeg": 4.0,
    "raw": 4.0,
}

_DEFAULT_FORMAT = "ktx2"

# Per-channel realistic bpp after typical format selection (basecolor=BC7,
# normal=BC5, orm/emissive=BC1). Used only by the heuristic path when no
# explicit material/map table is present.
_CHANNEL_BPP: dict[str, float] = {
    "basecolor": 1.0,
    "albedo": 1.0,
    "diffuse": 1.0,
    "color": 1.0,
    "normal": 1.0,
    "orm": 0.5,
    "ao": 0.5,
    "roughness": 0.5,
    "metallic": 0.5,
    "emissive": 0.5,
    "opacity": 0.5,
    "height": 1.0,
    "curvature": 0.5,
    "id": 0.5,
    "mask": 0.5,
}


@dataclass
class BudgetReport:
    """In-memory representation of the budget report dict."""

    texture_memory: dict[str, Any]
    materials: dict[str, Any]
    draw_calls: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        overall = _overall_status(
            [
                self.texture_memory.get("status", "skipped"),
                self.materials.get("status", "skipped"),
                self.draw_calls.get("status", "skipped"),
            ]
        )
        return {
            "schemaVersion": 1,
            "texture_memory": self.texture_memory,
            "materials": self.materials,
            "draw_calls": self.draw_calls,
            "overall_status": overall,
        }


# ---------------------------------------------------------------------------
# Public API


def evaluate(
    asset: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Evaluate the three budgets, returning (report, diagnostics).

    ``asset`` is the materialized asset dict; ``runtime`` is the executor's
    per-stage runtime dict. Neither is mutated.
    """
    cfg = _optimize_cfg(asset)
    surface_bundle = _get_surface_bundle(runtime)
    optimize_bundle = _get_optimize_bundle(runtime)

    texture_report, texture_diag = _evaluate_texture_memory(cfg, surface_bundle)
    material_report, material_diag = _evaluate_material_count(cfg, surface_bundle)
    draw_report, draw_diag = _evaluate_draw_calls(cfg, surface_bundle, optimize_bundle)

    report = BudgetReport(
        texture_memory=texture_report,
        materials=material_report,
        draw_calls=draw_report,
    ).to_dict()
    diagnostics: list[dict[str, Any]] = []
    for diag in (texture_diag, material_diag, draw_diag):
        if diag is not None:
            diagnostics.append(diag)
    return report, diagnostics


# ---------------------------------------------------------------------------
# Helpers


def _optimize_cfg(asset: Mapping[str, Any]) -> Mapping[str, Any]:
    build = asset.get("build") if isinstance(asset, Mapping) else None
    if isinstance(build, Mapping):
        cfg = build.get("optimize")
        if isinstance(cfg, Mapping):
            return cfg
    return {}


def _get_surface_bundle(runtime: Mapping[str, Any]) -> Mapping[str, Any]:
    surface = runtime.get("surface") if isinstance(runtime, Mapping) else None
    if isinstance(surface, Mapping):
        bundle = surface.get("bundle")
        if isinstance(bundle, Mapping):
            return bundle
    return {}


def _get_optimize_bundle(runtime: Mapping[str, Any]) -> Mapping[str, Any]:
    optimize = runtime.get("optimize") if isinstance(runtime, Mapping) else None
    if isinstance(optimize, Mapping):
        bundle = optimize.get("bundle")
        if isinstance(bundle, Mapping):
            return bundle
    return {}


def _status_for(estimated: float, budget: float) -> str:
    if budget <= 0:
        return "skipped"
    if estimated <= budget:
        return "pass"
    overage = (estimated - budget) / budget
    if overage > 0.25:
        return "error"
    return "warning"


def _severity_for_status(status: str) -> str:
    if status == "error":
        return "error"
    if status == "warning":
        return "warning"
    return "info"


def _overall_status(statuses: list[str]) -> str:
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    if all(s == "skipped" for s in statuses):
        return "skipped"
    return "pass"


def _resolution_px(surface_bundle: Mapping[str, Any]) -> int | None:
    manifest = surface_bundle.get("surface_manifest") if isinstance(surface_bundle, Mapping) else None
    if not isinstance(manifest, Mapping):
        return None
    res = manifest.get("resolution")
    if isinstance(res, Mapping):
        value = res.get("value")
        if isinstance(value, int) and value > 0:
            return value
    if isinstance(res, int) and res > 0:
        return res
    return None


def _infer_format(surface_bundle: Mapping[str, Any]) -> str:
    workflow = None
    manifest = surface_bundle.get("surface_manifest") if isinstance(surface_bundle, Mapping) else None
    if isinstance(manifest, Mapping):
        fmt = manifest.get("format")
        if isinstance(fmt, str) and fmt.lower() in _FORMAT_BPP:
            return fmt.lower()
        workflow = manifest.get("workflow")
    _ = workflow
    return _DEFAULT_FORMAT


def _bpp_for(fmt: str) -> float:
    return _FORMAT_BPP.get(fmt.lower(), _FORMAT_BPP[_DEFAULT_FORMAT])


def _unique_material_names(surface_bundle: Mapping[str, Any]) -> list[str]:
    """Derive the unique, deterministic material-name list from a surface bundle."""
    zones = surface_bundle.get("material_zones") if isinstance(surface_bundle, Mapping) else None
    seen: list[str] = []
    if isinstance(zones, list):
        for entry in zones:
            if not isinstance(entry, Mapping):
                continue
            name = entry.get("material") or entry.get("name") or entry.get("id")
            if isinstance(name, str) and name and name not in seen:
                seen.append(name)
    if seen:
        return seen
    manifest = surface_bundle.get("surface_manifest") if isinstance(surface_bundle, Mapping) else None
    if isinstance(manifest, Mapping):
        sem = manifest.get("semantic_materials")
        if isinstance(sem, list):
            for name in sem:
                if isinstance(name, str) and name and name not in seen:
                    seen.append(name)
    if seen:
        return seen
    # Fall back to materials list shape ``[{id, name, maps: [...]}, ...]`` if
    # upstream ever provides it.
    materials = surface_bundle.get("materials") if isinstance(surface_bundle, Mapping) else None
    if isinstance(materials, list):
        for mat in materials:
            if not isinstance(mat, Mapping):
                continue
            name = mat.get("id") or mat.get("name")
            if isinstance(name, str) and name and name not in seen:
                seen.append(name)
    return seen


# ---------------------------------------------------------------------------
# Sub-evaluators


def _budget_mb_to_bytes(value: Any, default_mb: float) -> int:
    """Resolve a megabyte budget to bytes, defaulting to ``default_mb``.

    Accepts either a scalar (interpreted as MiB) or a unit dict of the form
    ``{"value": N, "unit": "mb"|"mib"|"kb"|"kib"|"gb"|"gib"}`` as emitted by
    the Lathe normalizer for asset fields like ``texture_budget``.
    """
    if isinstance(value, Mapping):
        raw = value.get("value")
        unit = str(value.get("unit") or "mb").lower()
        if isinstance(raw, (int, float)) and raw > 0:
            scale = {
                "kb": 1000,
                "kib": 1024,
                "mb": 1024 * 1024,
                "mib": 1024 * 1024,
                "gb": 1024 * 1024 * 1024,
                "gib": 1024 * 1024 * 1024,
            }.get(unit, 1024 * 1024)
            return int(float(raw) * scale)
    if isinstance(value, (int, float)) and value > 0:
        return int(float(value) * 1024 * 1024)
    return int(default_mb * 1024 * 1024)


def _evaluate_texture_memory(
    cfg: Mapping[str, Any],
    surface_bundle: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    # STAGE-7 introduces ``texture_memory_budget_mb`` for runtime GPU memory.
    # The pre-existing ``texture_budget`` field captures pre-compressed on-disk
    # size targets under a different pipeline semantic and is intentionally
    # not consumed here.
    budget_mb_override = cfg.get("texture_memory_budget_mb")
    budget_bytes = _budget_mb_to_bytes(
        budget_mb_override,
        DEFAULT_TEXTURE_MEMORY_BUDGET_MB,
    )

    # Prefer explicit per-material data if present ({materials:[{maps:[{W,H,format}]}]}).
    materials_explicit = surface_bundle.get("materials") if isinstance(surface_bundle, Mapping) else None
    per_material: list[dict[str, Any]] = []
    estimated_total = 0
    considered = False

    if isinstance(materials_explicit, list) and materials_explicit:
        considered = True
        for mat in materials_explicit:
            if not isinstance(mat, Mapping):
                continue
            name = mat.get("name") or mat.get("id") or "unnamed"
            maps = mat.get("maps")
            mat_bytes = 0
            if isinstance(maps, list):
                for m in maps:
                    if not isinstance(m, Mapping):
                        continue
                    w = int(m.get("width") or m.get("w") or 0)
                    h = int(m.get("height") or m.get("h") or 0)
                    fmt = str(m.get("format") or _DEFAULT_FORMAT)
                    bpp = _bpp_for(fmt)
                    mat_bytes += int(w * h * bpp)
            per_material.append({"name": str(name), "bytes": int(mat_bytes)})
            estimated_total += mat_bytes

    if not considered:
        # Heuristic path: resolution x channel-aware bpp x distinct materials.
        resolution = _resolution_px(surface_bundle)
        maps = surface_bundle.get("maps") if isinstance(surface_bundle, Mapping) else None
        if not isinstance(maps, list):
            maps = []
        default_bpp = _bpp_for(_infer_format(surface_bundle))
        materials = _unique_material_names(surface_bundle)
        material_slots = surface_bundle.get("material_slots") if isinstance(surface_bundle, Mapping) else None
        slot_count = len(materials) or (
            int(material_slots) if isinstance(material_slots, int) and material_slots > 0 else 0
        )
        if resolution is None or not maps or slot_count == 0:
            return (
                {
                    "budget_bytes": int(budget_bytes),
                    "estimated_bytes": 0,
                    "per_material": [],
                    "status": "skipped",
                    "reason": "surface bundle lacks resolution/maps/materials to estimate",
                },
                None,
            )
        total_bpp = 0.0
        for channel in maps:
            if isinstance(channel, str):
                total_bpp += _CHANNEL_BPP.get(channel.lower(), default_bpp)
            else:
                total_bpp += default_bpp
        per_slot_bytes = int(resolution * resolution * total_bpp)
        names = materials if materials else [f"slot_{i}" for i in range(slot_count)]
        for name in names:
            per_material.append({"name": name, "bytes": per_slot_bytes})
            estimated_total += per_slot_bytes

    status = _status_for(float(estimated_total), float(budget_bytes))
    report = {
        "budget_bytes": int(budget_bytes),
        "estimated_bytes": int(estimated_total),
        "per_material": per_material,
        "status": status,
    }
    if status in {"warning", "error"}:
        diag = {
            "code": L_TEXTURE_MEMORY_OVER_BUDGET,
            "name": "texture_memory_over_budget",
            "severity": _severity_for_status(status),
            "phase": "optimize",
            "stage": "optimize",
            "message": (f"texture memory {estimated_total} bytes exceeds budget {budget_bytes} bytes"),
            "details": {
                "budget_bytes": int(budget_bytes),
                "estimated_bytes": int(estimated_total),
                "per_material": list(per_material),
            },
        }
        return report, diag
    return report, None


def _evaluate_material_count(
    cfg: Mapping[str, Any],
    surface_bundle: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    budget_override = cfg.get("material_count_budget")
    if isinstance(budget_override, int) and budget_override > 0:
        budget = budget_override
    else:
        budget = DEFAULT_MATERIAL_COUNT_BUDGET

    materials = _unique_material_names(surface_bundle)
    if not materials:
        slots = surface_bundle.get("material_slots") if isinstance(surface_bundle, Mapping) else None
        if isinstance(slots, int) and slots > 0:
            materials = [f"slot_{i}" for i in range(slots)]

    if not materials:
        return (
            {
                "budget": int(budget),
                "count": 0,
                "status": "skipped",
                "materials": [],
                "reason": "surface bundle has no material data",
            },
            None,
        )

    count = len(materials)
    status = _status_for(float(count), float(budget))
    report = {
        "budget": int(budget),
        "count": int(count),
        "status": status,
        "materials": list(materials),
    }
    if status in {"warning", "error"}:
        diag = {
            "code": L_MATERIAL_COUNT_OVER_BUDGET,
            "name": "material_count_over_budget",
            "severity": _severity_for_status(status),
            "phase": "optimize",
            "stage": "optimize",
            "message": f"material count {count} exceeds budget {budget}",
            "details": {
                "budget": int(budget),
                "count": int(count),
                "materials": list(materials),
            },
        }
        return report, diag
    return report, None


def _evaluate_draw_calls(
    cfg: Mapping[str, Any],
    surface_bundle: Mapping[str, Any],
    optimize_bundle: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    budget_override = cfg.get("draw_call_budget")
    if isinstance(budget_override, int) and budget_override > 0:
        budget = budget_override
    else:
        budget = DEFAULT_DRAW_CALL_BUDGET

    materials = _unique_material_names(surface_bundle)
    if not materials:
        slots = surface_bundle.get("material_slots") if isinstance(surface_bundle, Mapping) else None
        if isinstance(slots, int) and slots > 0:
            materials = [f"slot_{i}" for i in range(slots)]

    lods_list: list[Any] = []
    if isinstance(optimize_bundle, Mapping):
        candidate = optimize_bundle.get("lods")
        if isinstance(candidate, list):
            lods_list = candidate
    lod_count = len(lods_list) if lods_list else 0
    if lod_count == 0:
        # Fall back to asset config.
        cfg_lods = cfg.get("lods")
        if isinstance(cfg_lods, int) and cfg_lods > 0:
            lod_count = cfg_lods

    if not materials or lod_count == 0:
        return (
            {
                "budget": int(budget),
                "estimated": 0,
                "status": "skipped",
                "breakdown": [],
                "reason": "missing materials or LODs to estimate draw calls",
            },
            None,
        )

    mat_count = len(materials)
    breakdown = [{"lod": i, "count": int(mat_count)} for i in range(lod_count)]
    estimated = int(mat_count * lod_count)
    status = _status_for(float(estimated), float(budget))
    report = {
        "budget": int(budget),
        "estimated": int(estimated),
        "status": status,
        "breakdown": breakdown,
    }
    if status in {"warning", "error"}:
        diag = {
            "code": L_DRAW_CALL_OVER_BUDGET,
            "name": "draw_call_over_budget",
            "severity": _severity_for_status(status),
            "phase": "optimize",
            "stage": "optimize",
            "message": f"draw-call estimate {estimated} exceeds budget {budget}",
            "details": {
                "budget": int(budget),
                "estimated": int(estimated),
                "breakdown": list(breakdown),
            },
        }
        return report, diag
    return report, None


__all__ = [
    "DEFAULT_DRAW_CALL_BUDGET",
    "DEFAULT_MATERIAL_COUNT_BUDGET",
    "DEFAULT_TEXTURE_MEMORY_BUDGET_MB",
    "L_DRAW_CALL_OVER_BUDGET",
    "L_MATERIAL_COUNT_OVER_BUDGET",
    "L_TEXTURE_MEMORY_OVER_BUDGET",
    "BudgetReport",
    "evaluate",
]
