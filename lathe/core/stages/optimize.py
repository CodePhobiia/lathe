"""Optimize stage step body (LODs + convex collision + draw-call accounting).

Extracted from ``lathe/executor.py`` during Stage 2.IV.

V0.2 E3 (STAGE-1/2): Real QEM decimation + per-part convex collision hulls
replace the previous "cloned LODs + AABB collision" placeholders. All
artifacts are deterministic.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import trimesh

from ...asset_class_profiles import resolve_asset_class_profile
from ...highlow import HighLowRelation
from ...stages import budgets as budgets_mod
from ...stages import collision as collision_mod
from ...stages import lod as lod_mod
from ...topology_runtime import export_multi_part_scene_glb
from ..common import dump_json, relpath
from ..io import (
    export_glb,
    export_runtime_scene_glb,
    export_scene_glb_from_named_meshes,
)
from ..mesh import RuntimeMesh

DEFAULT_LOD_RATIOS: tuple[float, ...] = (1.0, 0.5, 0.25, 0.1)
MAX_PROCEDURAL_HIGHLOW_FACES = 120_000

# Default lod0 face budget when no asset_class profile drives the decision.
DEFAULT_LOD0_FACE_BUDGET = 4_000

# Per-part importance weights keyed by component_type / part-name token.
# Used to apportion the global lod0 face budget across preserved parts.
# Tokens are matched against (a) the part name (lowercased), (b) any tag,
# and (c) the asset_graph component_type. First match wins, with tie-break
# falling through the dict's insertion order. Generalises beyond chest by
# keying on generic component tokens (body/lid/hinge/...).
_PART_IMPORTANCE_WEIGHTS: dict[str, float] = {
    "body": 0.50,
    "shell": 0.50,
    "lid": 0.15,
    "hatch": 0.15,
    "door": 0.15,
    "panel": 0.12,
    "frame": 0.10,
    "bezel": 0.08,
    "screen": 0.08,
    "lock_plate": 0.05,
    "lockplate": 0.05,
    "lock": 0.05,
    "latch": 0.05,
    "plate": 0.05,
    "band": 0.05,
    "brass_band": 0.05,
    "hinge": 0.05,
    "handle": 0.05,
    "grip": 0.05,
    "foot": 0.03,
    "leg": 0.03,
    "stand": 0.03,
    "vent": 0.02,
    "grille": 0.02,
    "rivet": 0.005,
    "fastener": 0.005,
    "stud": 0.005,
}
_DEFAULT_PART_WEIGHT = 0.04

_HERO_FAMILY_TOKENS: frozenset[str] = frozenset(
    {
        "brassbound_chest",
        "courier_drone",
        "console_terminal",
        "industrial_crate",
        "mechanical_door",
        "service_cabinet",
        "control_pedestal",
        "supply_container",
        "hero_sword",
        "sci_fi_wall_panel",
    }
)
_HERO_DENSITY_TOKENS: frozenset[str] = frozenset({"hero", "aaa_hero"})


def _count_lod_levels(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, round(value))
    token = str(value).lower().replace("-", "_").strip()
    levels = {
        "off": 0,
        "none": 0,
        "low": 2,
        "medium": 3,
        "standard": 3,
        "high": 4,
        "hero": 5,
    }
    if token in levels:
        return levels[token]
    try:
        return max(0, round(float(token)))
    except ValueError:
        return 0


def _resolve_lod_ratios(
    asset_cfg: dict[str, Any], runtime_cfg: dict[str, Any], shape_cfg: dict[str, Any] | None = None
) -> list[float]:
    """Resolve LOD ratios with precedence: runtime_config > asset build > defaults."""
    shape_cfg = shape_cfg if isinstance(shape_cfg, dict) else {}
    runtime_opt = runtime_cfg.get("optimize") if isinstance(runtime_cfg, dict) else None
    if isinstance(runtime_opt, dict):
        ratios = runtime_opt.get("lod_ratios")
        if isinstance(ratios, (list, tuple)) and ratios:
            return [float(r) for r in ratios]
    asset_ratios = asset_cfg.get("lod_ratios")
    if isinstance(asset_ratios, (list, tuple)) and asset_ratios:
        return [float(r) for r in asset_ratios]
    shape_ratios = shape_cfg.get("lod_ratios")
    if isinstance(shape_ratios, (list, tuple)) and shape_ratios:
        return [float(r) for r in shape_ratios]
    lods_count = asset_cfg.get("lods")
    authored_lod_levels = _count_lod_levels(shape_cfg.get("lod_levels"))
    if isinstance(lods_count, int) and authored_lod_levels:
        lods_count = max(lods_count, authored_lod_levels)
    elif authored_lod_levels:
        lods_count = authored_lod_levels
    if isinstance(lods_count, int) and lods_count > 0:
        base = list(DEFAULT_LOD_RATIOS)
        if lods_count <= len(base):
            return base[:lods_count]
        tail = [base[-1] * (0.5 ** (i + 1)) for i in range(lods_count - len(base))]
        return base + tail
    return list(DEFAULT_LOD_RATIOS)


def _resolve_lod_config(
    asset_cfg: dict[str, Any], shape_cfg: dict[str, Any] | None = None
) -> list[dict[str, Any]] | None:
    """Resolve the STAGE-9 ``lod_config`` block (per-level distance + coverage hints).

    Expected shape: ``[{level, ratio?, distance_min, distance_max, screen_coverage}, ...]``.
    Missing keys on any entry fall back to the LOD module's defaults inferred
    from ``DEFAULT_DISTANCE_BANDS`` / ``DEFAULT_SCREEN_COVERAGE``.
    """
    shape_cfg = shape_cfg if isinstance(shape_cfg, dict) else {}
    raw = asset_cfg.get("lod_config")
    if not isinstance(raw, list):
        raw = shape_cfg.get("lod_config")
    if not isinstance(raw, list):
        return None
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        lvl = entry.get("level")
        if not isinstance(lvl, int) or lvl < 0:
            continue
        out.append(entry)
    return out or None


def _token(value: Any) -> str:
    return str(value or "").lower().replace("-", "_").replace(" ", "_").strip()


def _count(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, round(value))
    try:
        return max(0, round(float(str(value).strip())))
    except ValueError:
        return default


def _level(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    token = _token(value)
    levels = {
        "none": 0.0,
        "off": 0.0,
        "low": 0.6,
        "medium": 1.0,
        "standard": 1.0,
        "high": 1.35,
        "hero": 1.75,
    }
    if token in levels:
        return levels[token]
    try:
        return max(0.0, float(token))
    except ValueError:
        return default


def _normalize_family_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip().lower().replace("-", "_").replace(" ", "_")
    if token.endswith("_family"):
        token = token[: -len("_family")]
    return token


_PLANK_DISPLACEMENT_FAMILIES: frozenset[str] = frozenset({"brassbound_chest"})
_PLANK_DISPLACEMENT_MATERIAL_TOKENS: frozenset[str] = frozenset(
    {"oak_planks", "wood_planks", "plank_wood", "wooden_planks"}
)


def _is_plank_displacement_target(asset: dict[str, Any]) -> bool:
    """Return True when this asset should receive plank micro-displacement.

    Triggered for chest-family assets, or any asset whose
    ``intent.materials`` declare a plank-wood material token. The
    displacement is applied only on the high-poly source path so the
    runtime mesh stays smooth and the bake transfer captures the
    displacement as normal detail.
    """
    candidates = (
        asset.get("name"),
        asset.get("family"),
        (asset.get("assembly") or {}).get("family") if isinstance(asset.get("assembly"), dict) else None,
    )
    for candidate in candidates:
        token = _normalize_family_token(candidate)
        if token in _PLANK_DISPLACEMENT_FAMILIES:
            return True
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if isinstance(intent, dict):
        materials = intent.get("materials")
        if isinstance(materials, list):
            for entry in materials:
                token = str(entry or "").lower().replace("-", "_").replace(" ", "_").strip()
                if token in _PLANK_DISPLACEMENT_MATERIAL_TOKENS:
                    return True
    return False


def _is_hero_asset(asset: dict[str, Any]) -> bool:
    """Return True when this asset is a hero/aaa_hero family build.

    Hero detection is deliberately broad so the high-poly path fires
    for any asset that carries hero-family tokens or hero feature
    density, even when the source omits ``highlow_mode``.
    """
    features = asset.get("features", {}) if isinstance(asset, dict) else {}
    density = _token(features.get("density")) if isinstance(features, dict) else ""
    if density in _HERO_DENSITY_TOKENS:
        return True
    candidates = (
        asset.get("name"),
        asset.get("family"),
        (asset.get("assembly") or {}).get("family") if isinstance(asset.get("assembly"), dict) else None,
    )
    return any(_normalize_family_token(candidate) in _HERO_FAMILY_TOKENS for candidate in candidates)


def _resolve_target_quads(
    shape_cfg: dict[str, Any], topology_cfg: dict[str, Any]
) -> int:
    """Return the authored ``target_quads`` value (topology block first).

    The grammar puts ``target_quads`` under ``build.topology``; legacy
    code paths read from ``build.shape``. We honour both, preferring
    the topology block.
    """
    if isinstance(topology_cfg, dict):
        topology_target = _count(topology_cfg.get("target_quads"), 0)
        if topology_target:
            return topology_target
    return _count(shape_cfg.get("target_quads"), 0)


def _procedural_high_target_faces(
    shape_cfg: dict[str, Any],
    current_faces: int,
    *,
    topology_cfg: dict[str, Any] | None = None,
    hero_mode: bool = False,
) -> int:
    target_quads = _resolve_target_quads(shape_cfg, topology_cfg or {})
    authored_target_tris = target_quads * 2 if target_quads else 0
    if hero_mode:
        # Hero builds aim for ~3-5x runtime density so bake transfers
        # have meaningful displacement to project. The 4x multiplier
        # against runtime faces keeps the budget tied to actual
        # geometry rather than authored quad targets that may already
        # match the runtime mesh.
        hero_floor = max(current_faces * 4, authored_target_tris * 2)
        baseline = max(hero_floor, current_faces + 1)
    else:
        baseline = max(current_faces * 2, authored_target_tris, current_faces + 1)
    return min(MAX_PROCEDURAL_HIGHLOW_FACES, baseline)


def _edge_length_target_for_face_budget(mesh: trimesh.Trimesh, target_faces: int) -> float | None:
    if target_faces <= len(mesh.faces) or len(mesh.edges_unique_length) == 0:
        return None
    bounds = getattr(mesh, "bounds", None)
    if bounds is None or len(bounds) != 2:
        return None
    diagonal = float(((bounds[1] - bounds[0]) ** 2).sum() ** 0.5)
    if diagonal <= 0.0:
        return None
    scale = (max(1, target_faces) / max(1, len(mesh.faces))) ** 0.5
    longest_edge = float(max(mesh.edges_unique_length))
    return max(diagonal / 320.0, longest_edge / max(1.0, scale))


def _hash_seed_int(*tokens: object) -> int:
    """Deterministic 32-bit FNV-1a hash for plank displacement seeds."""
    state = 0x811C9DC5
    for token in tokens:
        text = repr(token)
        for ch in text:
            state ^= ord(ch) & 0xFF
            state = (state * 0x01000193) & 0xFFFFFFFF
    return state or 1


def _value_noise_3d_vec(
    x: np.ndarray, y: np.ndarray, z: np.ndarray, seed: int
) -> np.ndarray:
    """Vectorised deterministic 3D value noise in ``[-1, +1]``.

    Trilinear interpolation of integer-lattice random values, smoothed
    with the classic ``3t^2 - 2t^3`` curve. Pure numpy; no external
    Perlin dependency. Sufficient for low-amplitude wood-grain detail.
    """

    def _rand(ix: np.ndarray, iy: np.ndarray, iz: np.ndarray) -> np.ndarray:
        ix32 = ix.astype(np.uint32)
        iy32 = iy.astype(np.uint32)
        iz32 = iz.astype(np.uint32)
        h = (ix32 * np.uint32(0x9E3779B1)) ^ (iy32 * np.uint32(0x85EBCA6B)) ^ (
            iz32 * np.uint32(0xC2B2AE35)
        ) ^ np.uint32(seed & 0xFFFFFFFF)
        h ^= h >> np.uint32(16)
        h = h * np.uint32(0x7FEB352D)
        h ^= h >> np.uint32(15)
        h = h * np.uint32(0x846CA68B)
        h ^= h >> np.uint32(16)
        return (h.astype(np.float64) / float(0xFFFFFFFF)) * 2.0 - 1.0

    ix0 = np.floor(x).astype(np.int64)
    iy0 = np.floor(y).astype(np.int64)
    iz0 = np.floor(z).astype(np.int64)
    fx = x - ix0
    fy = y - iy0
    fz = z - iz0
    sx = fx * fx * (3.0 - 2.0 * fx)
    sy = fy * fy * (3.0 - 2.0 * fy)
    sz = fz * fz * (3.0 - 2.0 * fz)
    c000 = _rand(ix0, iy0, iz0)
    c100 = _rand(ix0 + 1, iy0, iz0)
    c010 = _rand(ix0, iy0 + 1, iz0)
    c110 = _rand(ix0 + 1, iy0 + 1, iz0)
    c001 = _rand(ix0, iy0, iz0 + 1)
    c101 = _rand(ix0 + 1, iy0, iz0 + 1)
    c011 = _rand(ix0, iy0 + 1, iz0 + 1)
    c111 = _rand(ix0 + 1, iy0 + 1, iz0 + 1)
    x00 = c000 + (c100 - c000) * sx
    x10 = c010 + (c110 - c010) * sx
    x01 = c001 + (c101 - c001) * sx
    x11 = c011 + (c111 - c011) * sx
    y0 = x00 + (x10 - x00) * sy
    y1 = x01 + (x11 - x01) * sy
    return y0 + (y1 - y0) * sz


def _apply_plank_displacement(
    mesh: trimesh.Trimesh,
    *,
    body_axis: str = "y",
    num_planks: int = 12,
    seam_depth_cm: float = 0.05,
    bow_depth_cm: float = 0.10,
    grain_amplitude_cm: float = 0.02,
    grain_frequency: float = 50.0,
    seed: int = 1,
    body_bounds: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Apply plank micro-displacement to a chest body mesh.

    Three deterministic contributions, all directed inward along the
    cylindrical normal (so seams form valleys, planks bow inward):

    1. Plank seams: a smoothstep valley at every ``2π/num_planks`` angle
       around the body axis. Depth ``seam_depth_cm`` (~0.5mm default).
    2. Plank curvature: each stave bows inward as a sin-curve along its
       arc, peak depth ``bow_depth_cm`` at the stave midpoint.
    3. Wood-grain noise: low-amplitude value noise modulated along the
       grain (vertical for chest staves) at frequency ``grain_frequency``.

    Mesh is modified in place (returned for convenience). Faces touched
    are tallied in the report. The displacement only affects vertices
    inside the supplied mesh's bounds — caller is expected to pass a
    body-only mesh, or the full asset mesh restricted by gating before
    invocation.
    """
    if len(mesh.vertices) == 0:
        return mesh, {"applied": False, "reason": "empty_mesh"}

    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    bounds = mesh.bounds
    if bounds is None or len(bounds) != 2:
        return mesh, {"applied": False, "reason": "no_bounds"}

    if body_bounds is not None:
        bmin = np.asarray(body_bounds[0], dtype=np.float64)
        bmax = np.asarray(body_bounds[1], dtype=np.float64)
    else:
        bmin, bmax = bounds
    center = (bmin + bmax) * 0.5

    if body_axis == "y":
        axis_idx = 1
        plane_indices = (0, 2)
    elif body_axis == "x":
        axis_idx = 0
        plane_indices = (1, 2)
    else:
        axis_idx = 2
        plane_indices = (0, 1)

    plane_a, plane_b = plane_indices
    da = vertices[:, plane_a] - center[plane_a]
    db = vertices[:, plane_b] - center[plane_b]
    radius = np.hypot(da, db)
    valid_radius = radius > 1e-6

    if body_bounds is not None:
        margin = 0.5
        in_body = np.all(
            (vertices >= (bmin - margin)) & (vertices <= (bmax + margin)),
            axis=1,
        )
        valid_radius = valid_radius & in_body

    if not np.any(valid_radius):
        return mesh, {"applied": False, "reason": "degenerate_radial"}

    theta = np.arctan2(db, da)

    plank_index = ((theta + math.pi) / (2.0 * math.pi)) * num_planks
    seam_phase = plank_index - np.floor(plank_index)

    seam_distance = np.minimum(seam_phase, 1.0 - seam_phase)
    seam_width = 0.10
    seam_window = np.clip(1.0 - seam_distance / seam_width, 0.0, 1.0)
    seam_smooth = seam_window * seam_window * (3.0 - 2.0 * seam_window)
    seam_offset = -seam_smooth * seam_depth_cm

    bow_phase = (seam_phase - 0.5) * math.pi
    bow_offset = -np.cos(bow_phase) * bow_depth_cm * 0.5 - bow_depth_cm * 0.5

    diagonal = float(np.linalg.norm(bmax - bmin))
    if diagonal < 1e-6:
        diagonal = 1.0
    grain_axis_pos = vertices[:, axis_idx] / max(diagonal, 1e-6)
    noise_x = grain_axis_pos * grain_frequency
    noise_y = theta * 1.2
    noise_z = grain_axis_pos * grain_frequency * 0.31
    grain_noise = _value_noise_3d_vec(noise_x, noise_y, noise_z, seed)
    grain_offset = grain_noise * grain_amplitude_cm
    grain_offset = np.where(valid_radius, grain_offset, 0.0)

    total_offset = seam_offset + bow_offset + grain_offset
    total_offset[~valid_radius] = 0.0

    safe_radius = np.where(valid_radius, radius, 1.0)
    radial_dir_a = da / safe_radius
    radial_dir_b = db / safe_radius

    vertices[:, plane_a] += radial_dir_a * total_offset
    vertices[:, plane_b] += radial_dir_b * total_offset

    new_mesh = trimesh.Trimesh(vertices=vertices, faces=mesh.faces, process=False)
    new_mesh.remove_infinite_values()
    new_mesh.merge_vertices()
    new_mesh.fix_normals()

    report = {
        "applied": True,
        "vertex_count": len(vertices),
        "num_planks": int(num_planks),
        "seam_depth_cm": float(seam_depth_cm),
        "bow_depth_cm": float(bow_depth_cm),
        "grain_amplitude_cm": float(grain_amplitude_cm),
        "grain_frequency": float(grain_frequency),
        "max_offset_cm": float(np.max(np.abs(total_offset))),
        "mean_offset_cm": float(np.mean(np.abs(total_offset))),
        "seed": int(seed),
    }
    return new_mesh, report


def _procedural_high_source_mesh(
    mesh: trimesh.Trimesh,
    shape_cfg: dict[str, Any],
    *,
    topology_cfg: dict[str, Any] | None = None,
    hero_mode: bool = False,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    target_faces = _procedural_high_target_faces(
        shape_cfg, len(mesh.faces), topology_cfg=topology_cfg, hero_mode=hero_mode
    )
    high_mesh = mesh.copy()
    method = "copy"
    target_edge_length = _edge_length_target_for_face_budget(high_mesh, target_faces)
    if target_edge_length is not None:
        vertices, faces = trimesh.remesh.subdivide_to_size(
            high_mesh.vertices,
            high_mesh.faces,
            max_edge=target_edge_length,
            max_iter=6,
            return_index=False,
        )
        high_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        method = "target_edge_subdivide"
    if len(high_mesh.faces) <= len(mesh.faces) and target_faces > len(mesh.faces):
        high_mesh = mesh.subdivide()
        method = "uniform_subdivide"
    if hero_mode and len(high_mesh.faces) <= len(mesh.faces):
        # Hero builds always need a denser high source than the runtime
        # mesh so HighLowRelation can populate distinct triangle counts
        # and the bake transfer has real displacement to project. One
        # extra subdivision pass is cheap and deterministic.
        high_mesh = high_mesh.subdivide()
        method = method + "+hero_subdivide" if method != "copy" else "hero_subdivide"
    high_mesh.remove_infinite_values()
    high_mesh.remove_unreferenced_vertices()
    high_mesh.merge_vertices()
    high_mesh.fix_normals()
    report = {
        "source": "procedural_high_source_v1",
        "method": method,
        "target_faces": target_faces,
        "target_edge_length_cm": round(float(target_edge_length or 0.0), 6),
        "input_faces": len(mesh.faces),
        "output_faces": len(high_mesh.faces),
        "hero_mode": bool(hero_mode),
    }
    return high_mesh, report


def _decimate_to_target_quads(
    mesh: trimesh.Trimesh, target_quads: int
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Decimate ``mesh`` to roughly ``target_quads * 2`` triangles.

    Uses the deterministic QEM decimater from ``lathe.stages.lod`` so
    cache fingerprints stay stable. Returns the decimated mesh and a
    telemetry record. Caller decides whether to invoke this — typical
    rule: emitted faces > ``target_quads * 2``.
    """
    if target_quads <= 0 or len(mesh.faces) == 0:
        return mesh, {
            "decimater_used": False,
            "decimater": "none",
            "reason": "no_target_quads" if target_quads <= 0 else "empty_mesh",
            "input_faces": len(mesh.faces),
            "output_faces": len(mesh.faces),
            "reduction_ratio": 0.0,
        }
    target_tris = target_quads * 2
    current = len(mesh.faces)
    if current <= target_tris:
        return mesh, {
            "decimater_used": False,
            "decimater": "none",
            "reason": "under_budget",
            "input_faces": current,
            "output_faces": current,
            "target_faces": target_tris,
            "reduction_ratio": 0.0,
        }
    ratio = max(0.01, min(1.0, target_tris / current))
    try:
        decimated = lod_mod.decimate(mesh, ratio)
    except (ValueError, RuntimeError) as exc:
        return mesh, {
            "decimater_used": False,
            "decimater": "qem",
            "reason": f"decimater_error:{type(exc).__name__}",
            "input_faces": current,
            "output_faces": current,
            "target_faces": target_tris,
            "reduction_ratio": 0.0,
        }
    out_faces = len(decimated.faces)
    return decimated, {
        "decimater_used": True,
        "decimater": "lathe.stages.lod.decimate_qem_v1",
        "reason": "over_budget",
        "input_faces": current,
        "output_faces": out_faces,
        "target_faces": target_tris,
        "reduction_ratio": round(1.0 - (out_faces / max(1, current)), 6),
    }


def _asset_class_token(asset: dict[str, Any]) -> str:
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if not isinstance(intent, dict):
        return ""
    raw = intent.get("asset_class")
    if not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def _resolve_lod0_face_budget(
    asset: dict[str, Any],
    optimize_cfg: dict[str, Any],
    program: dict[str, Any] | None = None,
) -> tuple[int, str]:
    """Pick the lod0 face budget driving per-part decimation.

    Precedence (highest first):
      1. ``optimize.lods.lod_0.target_face_count`` declared on the asset.
      2. ``intent.asset_class`` profile ``poly_budget.tris_max`` — resolved
         through ``asset_class_profiles`` so user-declared profiles shadow
         built-ins and ``aaa_hero``/``hero``/``mid_ground``/... all map
         consistently.
      3. ``DEFAULT_LOD0_FACE_BUDGET`` — the legacy 4k floor.
    """
    lods_cfg = optimize_cfg.get("lods") if isinstance(optimize_cfg, dict) else None
    if isinstance(lods_cfg, dict):
        lod0 = lods_cfg.get("lod_0") or lods_cfg.get(0)
        if isinstance(lod0, dict):
            explicit = lod0.get("target_face_count")
            value = _count(explicit, 0)
            if value > 0:
                return value, "asset.optimize.lods.lod_0.target_face_count"

    asset_class = _asset_class_token(asset)
    if asset_class and asset_class != "generic":
        user_profiles_raw = (program or {}).get("asset_class_profiles") if isinstance(program, dict) else None
        user_profiles: dict[str, dict[str, Any]] = {}
        if isinstance(user_profiles_raw, list):
            for entry in user_profiles_raw:
                if isinstance(entry, dict) and entry.get("name"):
                    user_profiles[str(entry["name"])] = entry
        elif isinstance(user_profiles_raw, dict):
            user_profiles = {k: v for k, v in user_profiles_raw.items() if isinstance(v, dict)}
        body = resolve_asset_class_profile(asset_class, user_profiles)
        if isinstance(body, dict):
            tris_max = (body.get("poly_budget") or {}).get("tris_max")
            tris_value = _count(tris_max, 0)
            if tris_value > 0:
                return tris_value, f"intent.asset_class={asset_class}"

    return DEFAULT_LOD0_FACE_BUDGET, "default"


def _normalize_token(value: Any) -> str:
    return str(value or "").lower().replace("-", "_").replace(" ", "_").strip()


def _part_importance(
    part_name: str,
    component_type: str | None,
    tags: list[str] | None,
) -> float:
    """Return a relative importance weight for a part in [0, 1].

    Lookup probes (in order):
      1. exact match on ``component_type`` token,
      2. exact match on any tag token,
      3. substring scan on ``part_name`` against the weight dict,
      4. ``_DEFAULT_PART_WEIGHT`` fallback.

    Returning 0 would starve a part of all triangles; we never do that —
    even an unrecognised part gets the default weight so it survives
    decimation with proportional headroom.
    """
    candidates: list[str] = []
    if component_type:
        candidates.append(_normalize_token(component_type))
    if tags:
        candidates.extend(_normalize_token(t) for t in tags if t)
    name_token = _normalize_token(part_name)
    if name_token:
        candidates.append(name_token)

    for token in candidates:
        if not token:
            continue
        if token in _PART_IMPORTANCE_WEIGHTS:
            return _PART_IMPORTANCE_WEIGHTS[token]

    if name_token:
        for keyword, weight in _PART_IMPORTANCE_WEIGHTS.items():
            if keyword in name_token:
                return weight

    return _DEFAULT_PART_WEIGHT


def _build_part_metadata_lookup(
    asset: dict[str, Any],
    multi_part_manifest: Any = None,
) -> dict[str, dict[str, Any]]:
    """Build a {part_name: {component_type, tags}} index for the asset.

    Reads ``assembly.resolved_components`` (resolver output) for
    component_type. When a topology ``MultiPartScene`` manifest is
    supplied, its per-part ``tags`` and ``parent_blueprint_component``
    take precedence — that's the authoritative tag source for downstream
    decisions like plank-displacement targeting.
    """
    out: dict[str, dict[str, Any]] = {}
    assembly = asset.get("assembly") if isinstance(asset, dict) else None
    if isinstance(assembly, dict):
        for component in assembly.get("resolved_components", []) or []:
            if not isinstance(component, dict):
                continue
            values = component.get("values") or {}
            part = values.get("part")
            if not part:
                continue
            component_type = (
                (component.get("geometry") or {}).get("component_type")
                if isinstance(component.get("geometry"), dict)
                else None
            ) or values.get("component_type")
            tags = list(values.get("tags") or [])
            out[str(part)] = {
                "component_type": str(component_type) if component_type else None,
                "tags": [str(t) for t in tags if t],
            }

    # Multi-part manifest tags trump resolver tags. The manifest is built
    # from the blueprint at topology time and carries the canonical
    # ``plank_displacement`` flag plus seam/material tags downstream code
    # depends on.
    if multi_part_manifest is not None:
        for entry in multi_part_manifest:
            if hasattr(entry, "as_dict"):
                entry = entry.as_dict()
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not name:
                continue
            existing = out.setdefault(str(name), {"component_type": None, "tags": []})
            manifest_tags = list(entry.get("tags") or [])
            merged_tags = sorted(set(existing.get("tags") or []) | set(manifest_tags))
            existing["tags"] = [str(t) for t in merged_tags if t]
            parent = entry.get("parent_blueprint_component") or ""
            if parent and not existing.get("component_type"):
                existing["component_type"] = str(parent)

    return out


def _split_mesh_by_parts(
    mesh: trimesh.Trimesh, face_parts: list[str]
) -> dict[str, dict[str, Any]]:
    """Split ``mesh`` into per-part submeshes keyed by part name.

    Returns ``{part_name: {"mesh": Trimesh, "face_indices": ndarray}}``.
    Vertices are reindexed so each submesh stands alone. ``face_parts``
    longer/shorter than ``mesh.faces`` is treated as if the missing
    entries map to ``""`` (unlabeled bucket).
    """
    n_faces = len(mesh.faces)
    if n_faces == 0:
        return {}
    if not face_parts or len(face_parts) != n_faces:
        return {"": {"mesh": mesh.copy(), "face_indices": np.arange(n_faces)}}

    by_part: dict[str, list[int]] = {}
    for fi, name in enumerate(face_parts):
        by_part.setdefault(str(name or ""), []).append(fi)

    out: dict[str, dict[str, Any]] = {}
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    for name, idx_list in by_part.items():
        face_idx = np.asarray(idx_list, dtype=np.int64)
        sub_faces = faces[face_idx]
        used_verts, remap = np.unique(sub_faces, return_inverse=True)
        new_verts = vertices[used_verts]
        new_faces = remap.reshape(sub_faces.shape).astype(np.int64)
        sub_mesh = trimesh.Trimesh(vertices=new_verts, faces=new_faces, process=False)
        sub_mesh.merge_vertices()
        out[name] = {"mesh": sub_mesh, "face_indices": face_idx}
    return out


def _combine_part_meshes(
    part_meshes: list[tuple[str, trimesh.Trimesh]],
) -> tuple[trimesh.Trimesh, list[str]]:
    """Concatenate per-part submeshes into one mesh + per-face label list.

    Preserves part insertion order so downstream consumers see a stable
    face_parts vector. Returns ``(merged_mesh, face_parts)``.
    """
    if not part_meshes:
        return trimesh.Trimesh(process=False), []
    verts_chunks: list[np.ndarray] = []
    faces_chunks: list[np.ndarray] = []
    face_parts_out: list[str] = []
    vert_offset = 0
    for name, sub in part_meshes:
        sv = np.asarray(sub.vertices, dtype=np.float64)
        sf = np.asarray(sub.faces, dtype=np.int64)
        if len(sv) == 0 or len(sf) == 0:
            continue
        verts_chunks.append(sv)
        faces_chunks.append(sf + vert_offset)
        face_parts_out.extend([name] * len(sf))
        vert_offset += len(sv)
    if not verts_chunks:
        return trimesh.Trimesh(process=False), []
    merged_verts = np.concatenate(verts_chunks, axis=0)
    merged_faces = np.concatenate(faces_chunks, axis=0)
    merged = trimesh.Trimesh(vertices=merged_verts, faces=merged_faces, process=False)
    # Each per-part submesh was already welded individually upstream
    # (see ``_split_mesh_by_parts`` line 815). Welding the combined
    # mesh here would collapse part-boundary vertices and average
    # shading normals across part seams, killing normal_richness,
    # bake_cleanliness, and geometry_dihedral_continuity. Leave the
    # combined mesh un-welded so each part's boundary verts remain
    # distinct.
    return merged, face_parts_out


def _decimate_per_part(
    mesh: trimesh.Trimesh,
    face_parts: list[str],
    asset: dict[str, Any],
    target_total_faces: int,
    multi_part_manifest: Any = None,
) -> tuple[trimesh.Trimesh, list[str], dict[str, Any]]:
    """Decimate each part independently to a face budget proportional to weight.

    Returns ``(merged_mesh, merged_face_parts, report)``. When the input
    is single-part (no labels, or one bucket), falls through to a single
    ``lod_mod.decimate`` call equivalent to the legacy merged-mesh path
    so the function is back-compat for non-preserved scenes.

    ``multi_part_manifest`` (optional): the topology stage's
    ``MultiPartScene.manifest`` — when supplied, its tags drive the
    per-part importance lookup, taking precedence over assembly-derived
    component_type.
    """
    splits = _split_mesh_by_parts(mesh, face_parts)
    metadata = _build_part_metadata_lookup(asset, multi_part_manifest)
    part_names = list(splits.keys())
    real_parts = [p for p in part_names if p]

    if len(real_parts) <= 1:
        # Single-part / unlabeled scene: keep the legacy merged path.
        ratio = max(0.01, min(1.0, target_total_faces / max(1, len(mesh.faces))))
        if ratio >= _full_ratio_cutoff():
            return mesh.copy(), list(face_parts), {
                "mode": "single_part_passthrough",
                "input_faces": len(mesh.faces),
                "output_faces": len(mesh.faces),
                "target_total_faces": target_total_faces,
                "parts": [],
            }
        try:
            decimated = lod_mod.decimate(mesh, ratio)
        except (ValueError, RuntimeError) as exc:
            return mesh.copy(), list(face_parts), {
                "mode": "single_part_decimate_error",
                "error": f"{type(exc).__name__}: {exc}",
                "input_faces": len(mesh.faces),
                "output_faces": len(mesh.faces),
                "target_total_faces": target_total_faces,
                "parts": [],
            }
        # face_parts dropped; downstream needs a same-length list. Fall
        # back to the original label set padded/truncated to match.
        new_face_parts = list(face_parts[: len(decimated.faces)]) + [
            face_parts[0] if face_parts else ""
        ] * max(0, len(decimated.faces) - len(face_parts))
        return decimated, new_face_parts, {
            "mode": "single_part",
            "input_faces": len(mesh.faces),
            "output_faces": len(decimated.faces),
            "target_total_faces": target_total_faces,
            "parts": [],
        }

    # Multi-part scene: per-part budget via importance weights.
    weights: dict[str, float] = {}
    for name in real_parts:
        meta = metadata.get(name) or {}
        weights[name] = _part_importance(
            name,
            meta.get("component_type"),
            meta.get("tags"),
        )
    weight_sum = sum(weights.values()) or 1.0

    part_reports: list[dict[str, Any]] = []
    decimated_parts: list[tuple[str, trimesh.Trimesh]] = []
    for name in part_names:
        sub_info = splits[name]
        sub_mesh: trimesh.Trimesh = sub_info["mesh"]
        sub_face_count = len(sub_mesh.faces)
        if not name:
            # Unlabeled bucket (e.g. an empty "" face_parts entry):
            # preserve as-is. Rare in practice.
            decimated_parts.append((name, sub_mesh))
            part_reports.append(
                {
                    "part": name,
                    "weight": 0.0,
                    "target_faces": sub_face_count,
                    "input_faces": sub_face_count,
                    "output_faces": sub_face_count,
                    "decimater_used": False,
                    "reason": "unlabeled_passthrough",
                }
            )
            continue
        weight = weights.get(name, _DEFAULT_PART_WEIGHT)
        target_faces = max(_min_part_faces(), round(target_total_faces * weight / weight_sum))
        if sub_face_count <= target_faces:
            decimated_parts.append((name, sub_mesh))
            part_reports.append(
                {
                    "part": name,
                    "weight": round(weight, 6),
                    "target_faces": target_faces,
                    "input_faces": sub_face_count,
                    "output_faces": sub_face_count,
                    "decimater_used": False,
                    "reason": "under_budget",
                }
            )
            continue
        ratio = max(0.01, min(1.0, target_faces / sub_face_count))
        try:
            sub_decimated = lod_mod.decimate(sub_mesh, ratio)
            decimater_used = True
            reason = "over_budget"
        except (ValueError, RuntimeError) as exc:
            sub_decimated = sub_mesh
            decimater_used = False
            reason = f"decimater_error:{type(exc).__name__}"
        decimated_parts.append((name, sub_decimated))
        part_reports.append(
            {
                "part": name,
                "weight": round(weight, 6),
                "target_faces": target_faces,
                "input_faces": sub_face_count,
                "output_faces": len(sub_decimated.faces),
                "decimater_used": decimater_used,
                "reason": reason,
            }
        )

    merged, merged_face_parts = _combine_part_meshes(decimated_parts)
    if len(merged.faces) == 0:
        # Degenerate output — fall back to original mesh so downstream
        # stages don't choke on an empty scene.
        return mesh.copy(), list(face_parts), {
            "mode": "per_part_empty_fallback",
            "input_faces": len(mesh.faces),
            "output_faces": len(mesh.faces),
            "target_total_faces": target_total_faces,
            "parts": part_reports,
        }
    return merged, merged_face_parts, {
        "mode": "per_part",
        "input_faces": len(mesh.faces),
        "output_faces": len(merged.faces),
        "target_total_faces": target_total_faces,
        "parts": part_reports,
    }


def _full_ratio_cutoff() -> float:
    return 0.9999


def _min_part_faces() -> int:
    """Smallest face count to leave on any decimated part.

    Prevents a low-weight part (a foot, rivet) from collapsing to a
    degenerate triangle when the global budget tightens.
    """
    return 12


_DISPLACEMENT_PART_TOKENS: frozenset[str] = frozenset(
    {"body", "shell", "body_shell", "plank_displacement"}
)


def _part_is_displacement_target(
    part_name: str, metadata: dict[str, Any] | None
) -> bool:
    """Return True when ``part_name`` should receive plank displacement.

    Generalises beyond literal ``"body"``: matches by substring, by tag,
    or by component_type token. The per-part tag list (sourced from the
    resolved component) is the authoritative signal — substring matching
    is the fallback when an asset omits explicit tags.
    """
    name_token = _normalize_token(part_name)
    for token in _DISPLACEMENT_PART_TOKENS:
        if token and token in name_token:
            return True
    if not metadata:
        return False
    tags = metadata.get("tags") or []
    component_type = metadata.get("component_type")
    if component_type and _normalize_token(component_type) in _DISPLACEMENT_PART_TOKENS:
        return True
    return any(_normalize_token(tag) in _DISPLACEMENT_PART_TOKENS for tag in tags)


def _apply_plank_displacement_per_part(
    mesh: trimesh.Trimesh,
    face_parts: list[str] | None,
    asset: dict[str, Any],
    *,
    seed: int,
    seam_depth_cm: float,
    bow_depth_cm: float,
    grain_amplitude_cm: float,
    grain_frequency: float,
    multi_part_manifest: Any = None,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Apply plank displacement only on body-shell parts.

    When the input has multi-part labels, splits the mesh into parts,
    runs ``_apply_plank_displacement`` on each part flagged as a
    displacement target, and recombines. When the input is single-part
    or unlabeled, falls back to the legacy whole-mesh behaviour for
    backwards compatibility.
    """
    if len(mesh.faces) == 0:
        return mesh, {"applied": False, "reason": "empty_mesh"}

    real_parts: set[str] = set()
    if face_parts and len(face_parts) == len(mesh.faces):
        real_parts = {str(p) for p in face_parts if p}

    if len(real_parts) <= 1:
        # Single-part or unlabeled: legacy behaviour. Caller already
        # passed the gate via ``_is_plank_displacement_target``.
        return _apply_plank_displacement(
            mesh,
            body_axis="y",
            num_planks=12,
            seam_depth_cm=seam_depth_cm,
            bow_depth_cm=bow_depth_cm,
            grain_amplitude_cm=grain_amplitude_cm,
            grain_frequency=grain_frequency,
            seed=seed,
        )

    splits = _split_mesh_by_parts(mesh, list(face_parts or []))
    metadata = _build_part_metadata_lookup(asset, multi_part_manifest)

    part_reports: list[dict[str, Any]] = []
    out_parts: list[tuple[str, trimesh.Trimesh]] = []
    targeted_any = False
    for name, info in splits.items():
        sub_mesh: trimesh.Trimesh = info["mesh"]
        meta = metadata.get(name) if name else None
        if name and _part_is_displacement_target(name, meta):
            targeted_any = True
            displaced, sub_report = _apply_plank_displacement(
                sub_mesh,
                body_axis="y",
                num_planks=12,
                seam_depth_cm=seam_depth_cm,
                bow_depth_cm=bow_depth_cm,
                grain_amplitude_cm=grain_amplitude_cm,
                grain_frequency=grain_frequency,
                seed=seed,
            )
            out_parts.append((name, displaced))
            part_reports.append({"part": name, "targeted": True, "report": sub_report})
        else:
            out_parts.append((name, sub_mesh))
            part_reports.append({"part": name, "targeted": False})

    merged, _merged_face_parts = _combine_part_meshes(out_parts)
    if len(merged.faces) == 0 or not targeted_any:
        return mesh, {
            "applied": False,
            "reason": "no_displacement_targets" if not targeted_any else "merged_empty",
            "parts": part_reports,
        }
    return merged, {
        "applied": True,
        "mode": "per_part",
        "vertex_count": len(merged.vertices),
        "parts": part_reports,
    }


def _highlow_requested(shape_cfg: dict[str, Any]) -> bool:
    mode = _token(shape_cfg.get("highlow_mode"))
    return mode in {"lod_pair", "real_lod", "runtime_lod", "high_to_low"} or any(
        field in shape_cfg
        for field in (
            "highlow_low_lod",
            "highlow_bake_cage_offset_cm",
            "highlow_bake_max_ray_distance_cm",
            "highlow_bake_bidirectional",
        )
    )


def _publish_lod_highlow_relation(
    executor: Any,
    *,
    shape_cfg: dict[str, Any],
    lods: list[dict[str, Any]],
    high_mesh_uri: str | None = None,
    high_triangle_count: int = 0,
    high_source_report: dict[str, Any] | None = None,
    hero_mode: bool = False,
) -> dict[str, Any] | None:
    # Hero builds always publish a real high/low relation so the
    # validator's ``is_real_highlow`` check has truthful evidence even
    # when the source omits ``highlow_mode``. Non-hero builds keep the
    # original gate.
    if not (hero_mode or _highlow_requested(shape_cfg)) or len(lods) < 2:
        return None
    requested_level = _count(shape_cfg.get("highlow_low_lod"), len(lods) - 1)
    if requested_level <= 0:
        requested_level = len(lods) - 1
    low_entry = next((entry for entry in lods if int(entry.get("name", "lod0").removeprefix("lod") or 0) == requested_level), None)
    if low_entry is None:
        low_entry = lods[-1]
    surface_bundle = executor.runtime.get("surface", {}).get("bundle", {})
    previous_relation = surface_bundle.get("highlow_relation", {}) if isinstance(surface_bundle, dict) else {}
    high_mesh_uri = high_mesh_uri or previous_relation.get("high_mesh_uri")
    high_triangle_count = int(high_triangle_count or previous_relation.get("high_triangle_count", 0) or 0)
    low_triangle_count = int(low_entry.get("triangle_count", 0) or 0)
    if high_triangle_count > low_triangle_count >= 0:
        distinction_ratio = round((high_triangle_count - low_triangle_count) / max(1, high_triangle_count), 6)
    else:
        distinction_ratio = 0.0
    relation = HighLowRelation(
        high_mesh_uri=high_mesh_uri,
        low_mesh_uri=low_entry.get("mesh_uri"),
        bake_cage_offset_cm=_level(shape_cfg.get("highlow_bake_cage_offset_cm"), 1.25),
        source="procedural_high_to_lod_low_v1" if high_source_report else "optimize_lod_highlow_v1",
        high_triangle_count=high_triangle_count,
        low_triangle_count=low_triangle_count,
        distinction_ratio=distinction_ratio,
        bake_groups=previous_relation.get("bake_groups"),
        authoritative=True,
    ).to_dict()
    relation["low_lod_level"] = int(str(low_entry.get("name", "lod0")).removeprefix("lod") or 0)
    relation["highlow_mode"] = _token(shape_cfg.get("highlow_mode")) or "lod_pair"
    if high_source_report:
        relation["high_source_report"] = high_source_report
    for key in (
        "bake_transfer",
        "projection_quality",
        "transfer_decision",
        "transfer_policy",
        "projection_trust",
    ):
        if key in previous_relation:
            relation[key] = previous_relation[key]
    if isinstance(surface_bundle, dict):
        surface_bundle["highlow_relation"] = relation
        surface_dir = executor.stage_dirs.get("surface")
        surface_path = surface_dir / "bundle.json" if surface_dir is not None else None
        if surface_path is not None and surface_path.exists():
            dump_json(surface_path, surface_bundle)
    executor.runtime["highlow_relation"] = relation
    return relation


def run(executor: Any, physics_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        physics_bundle: physics_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["optimize"]
    cfg = executor.asset["build"]["optimize"]
    shape_cfg = executor.asset.get("build", {}).get("shape", {})
    topology_cfg = executor.asset.get("build", {}).get("topology", {}) or {}
    runtime_cfg = getattr(executor, "runtime_config", {}) or {}
    program = getattr(executor, "program", None) or {}
    uv_runtime: RuntimeMesh = executor.runtime["uv"]["runtime_mesh"]
    hero_mode = _is_hero_asset(executor.asset)
    target_quads_declared = _resolve_target_quads(shape_cfg, topology_cfg)
    lod0_face_budget, lod0_budget_source = _resolve_lod0_face_budget(
        executor.asset, cfg, program
    )
    uv_face_parts: list[str] = list(getattr(uv_runtime, "face_parts", []) or [])
    # Topology stage now publishes a multi-part scene + manifest. The
    # manifest carries authoritative per-part tags (``plank_displacement``,
    # seam_class, etc.) populated from the blueprint. We prefer it over
    # the per-face ``face_parts`` vector so the displacement re-target
    # and per-part importance lookup see the canonical labels even if
    # downstream stages re-fuse the mesh along the way.
    topology_runtime_block = executor.runtime.get("topology") if isinstance(executor.runtime, dict) else None
    multi_part_scene = (
        topology_runtime_block.get("multi_part_scene")
        if isinstance(topology_runtime_block, dict)
        else None
    )
    multi_part_manifest = (
        list(getattr(multi_part_scene, "manifest", []))
        if multi_part_scene is not None
        else None
    )
    high_source_uri: str | None = None
    high_source_report: dict[str, Any] | None = None
    high_source_triangle_count = 0
    if (hero_mode or _highlow_requested(shape_cfg)) and len(uv_runtime.mesh.faces) > 0:
        high_mesh, high_source_report = _procedural_high_source_mesh(
            uv_runtime.mesh,
            shape_cfg,
            topology_cfg=topology_cfg,
            hero_mode=hero_mode,
        )
        # Apply plank micro-displacement on the densified high-poly
        # mesh for chest-family assets. Runtime/low mesh stays smooth
        # so the bake transfer captures the displacement as normal
        # detail (Phase 0 §4.6 high-poly source path). When the input
        # carries multi-part labels, displacement is now applied only
        # to the body-shell part — hinges/handles/feet stay flat.
        plank_displacement_report: dict[str, Any] | None = None
        if _is_plank_displacement_target(executor.asset):
            # Pre-subdivide once more so displacement has enough vertices
            # to register at sub-cm scales. Each subdivide doubles tris.
            extra_subdivisions = 0
            while extra_subdivisions < 2 and len(high_mesh.faces) < 60_000:
                high_mesh = high_mesh.subdivide()
                extra_subdivisions += 1
            seed = _hash_seed_int(
                executor.asset.get("name") or "asset",
                executor.asset.get("family") or "family",
                "plank_displacement",
            )
            # The high-poly source path subdivides the merged mesh, so
            # face_parts no longer maps 1:1 to high_mesh.faces. We pass
            # the (possibly stale) labels and the helper falls back to
            # whole-mesh displacement when the label vector mismatches.
            high_face_parts = (
                uv_face_parts if len(uv_face_parts) == len(high_mesh.faces) else []
            )
            high_mesh, plank_displacement_report = _apply_plank_displacement_per_part(
                high_mesh,
                high_face_parts,
                executor.asset,
                seed=seed,
                seam_depth_cm=0.06,
                bow_depth_cm=0.12,
                grain_amplitude_cm=0.025,
                grain_frequency=50.0,
                multi_part_manifest=multi_part_manifest,
            )
            if plank_displacement_report:
                plank_displacement_report["extra_subdivisions"] = extra_subdivisions
        if plank_displacement_report:
            high_source_report["plank_displacement"] = plank_displacement_report
        # Hero builds always emit ``lod_high.glb`` so downstream
        # validators can see a distinct, denser high-poly source. The
        # ``high_source.glb`` legacy name is retained for non-hero
        # ``highlow_mode`` flows; both names point to the same artifact
        # for hero builds (single export, two pointers).
        high_artifact_name = "lod_high.glb" if hero_mode else "high_source.glb"
        high_source_path = stage_dir / high_artifact_name
        # Use scene-aware export when high-poly face_parts still align
        # 1:1 (no upstream subdivision broke alignment) and the scene is
        # genuinely multi-part. Otherwise fall back to single-mesh.
        if (
            len(uv_face_parts) == len(high_mesh.faces)
            and len({p for p in uv_face_parts if p}) > 1
        ):
            high_runtime = RuntimeMesh(
                mesh=high_mesh,
                face_parts=list(uv_face_parts),
                part_colors=dict(uv_runtime.part_colors),
                units=uv_runtime.units,
            )
            export_runtime_scene_glb(high_runtime, high_source_path)
        else:
            export_glb(high_mesh, high_source_path)
        high_source_uri = relpath(executor.out_dir, high_source_path)
        high_source_triangle_count = len(high_mesh.faces)

    lod_ratios = _resolve_lod_ratios(cfg, runtime_cfg, shape_cfg)
    lod_config = _resolve_lod_config(cfg, shape_cfg)
    lod_results = lod_mod.build_lods(uv_runtime.mesh, lod_ratios, lod_config)

    lods: list[dict[str, Any]] = []
    lod_manifest_entries: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    decimater_reports: list[dict[str, Any]] = []
    if len(uv_runtime.mesh.faces) == 0:
        diagnostics.append(
            {
                "code": "LOD_EMPTY_INPUT",
                "level": "warning",
                "message": "uv stage mesh is empty; only LOD0 emitted.",
            }
        )

    target_tris = target_quads_declared * 2 if target_quads_declared else 0
    per_part_lod0_report: dict[str, Any] | None = None
    for result in lod_results:
        emitted_mesh = result.mesh
        emitted_tris = result.tris
        emitted_verts = result.verts
        decimater_report: dict[str, Any] | None = None
        # Track per-emitted-LOD face_parts when alignment is preserved so
        # we can emit a multi-part Scene glb for engine importers.
        # ``lod_mod.build_lods`` does not preserve face_parts through QEM
        # decimation, so only LOD0's per-part decimation path produces a
        # reliable label vector below.
        emitted_face_parts: list[str] = (
            list(uv_face_parts)
            if result.level == 0 and len(uv_face_parts) == len(emitted_mesh.faces)
            else []
        )
        # Honour ``target_quads`` only on LOD0 (the runtime mesh). Lower
        # LODs are already aggressively decimated by ``build_lods``; we
        # do not want to over-decimate a 10% LOD just because the
        # author set a quad budget for the runtime mesh.
        if (
            result.level == 0
            and target_tris > 0
            and emitted_tris > target_tris * 2
        ):
            emitted_mesh, decimater_report = _decimate_to_target_quads(
                result.mesh, target_quads_declared
            )
            emitted_tris = len(emitted_mesh.faces)
            emitted_verts = len(emitted_mesh.vertices)
            if not decimater_report.get("decimater_used"):
                diagnostics.append(
                    {
                        "code": "LOD_TARGET_QUADS_MISS",
                        "level": "warning",
                        "message": (
                            f"target_quads={target_quads_declared} declared but "
                            f"decimater could not reduce LOD0 ({result.tris} tris) "
                            f"toward target ({target_tris} tris): "
                            f"{decimater_report.get('reason', 'unknown')}."
                        ),
                    }
                )
            decimater_reports.append({"level": result.level, **decimater_report})

        # Per-part decimation on LOD0: when the input has multi-part
        # labels (preserved through topology+uv), apportion ``lod0_face_budget``
        # across parts by importance weight and decimate each part
        # independently. This keeps small parts (hinges, handles, feet)
        # legible at runtime instead of getting starved by a global
        # collapse on the merged mesh.
        if (
            result.level == 0
            and lod0_face_budget > 0
            and emitted_tris > lod0_face_budget
        ):
            face_parts_for_pp = (
                uv_face_parts
                if len(uv_face_parts) == len(emitted_mesh.faces)
                else []
            )
            real_parts_count = len({p for p in face_parts_for_pp if p})
            pre_pp_tris = emitted_tris
            if real_parts_count > 1:
                emitted_mesh, new_face_parts, per_part_lod0_report = _decimate_per_part(
                    emitted_mesh,
                    face_parts_for_pp,
                    executor.asset,
                    lod0_face_budget,
                    multi_part_manifest=multi_part_manifest,
                )
                emitted_tris = len(emitted_mesh.faces)
                emitted_verts = len(emitted_mesh.vertices)
                emitted_face_parts = (
                    list(new_face_parts)
                    if len(new_face_parts) == emitted_tris
                    else []
                )
                decimater_reports.append(
                    {
                        "level": result.level,
                        "decimater_used": True,
                        "decimater": "lathe.optimize.per_part_qem_v1",
                        "reason": "asset_class_per_part",
                        "input_faces": pre_pp_tris,
                        "output_faces": emitted_tris,
                        "target_faces": lod0_face_budget,
                        "reduction_ratio": round(
                            1.0 - (emitted_tris / max(1, pre_pp_tris)), 6
                        ),
                        "budget_source": lod0_budget_source,
                        "parts": list(per_part_lod0_report.get("parts", [])),
                    }
                )
            elif decimater_report is None:
                # Single-part / unlabeled fallback: when the legacy
                # ``target_quads`` path didn't run (no quad budget
                # declared), still honour the asset_class face budget
                # so hero builds aren't stuck at the upstream face count.
                ratio = max(0.01, min(1.0, lod0_face_budget / max(1, emitted_tris)))
                try:
                    emitted_mesh = lod_mod.decimate(emitted_mesh, ratio)
                    decimater_used = True
                    reason = "asset_class_single_part"
                except (ValueError, RuntimeError) as exc:
                    decimater_used = False
                    reason = f"decimater_error:{type(exc).__name__}"
                emitted_tris = len(emitted_mesh.faces)
                emitted_verts = len(emitted_mesh.vertices)
                decimater_reports.append(
                    {
                        "level": result.level,
                        "decimater_used": decimater_used,
                        "decimater": "lathe.stages.lod.decimate_qem_v1",
                        "reason": reason,
                        "input_faces": pre_pp_tris,
                        "output_faces": emitted_tris,
                        "target_faces": lod0_face_budget,
                        "reduction_ratio": round(
                            1.0 - (emitted_tris / max(1, pre_pp_tris)), 6
                        ),
                        "budget_source": lod0_budget_source,
                    }
                )
        lod_path = stage_dir / f"lod_{result.level}.glb"
        # Emit a multi-part scene glb when face_parts align: each part
        # becomes a named glTF node so engine importers (Unity glTFast,
        # Godot native, Unreal) unpack the asset into a child hierarchy
        # rather than a single fused StaticMesh. Falls back to single-
        # mesh export when alignment is unreliable (lower LODs after
        # global QEM decimation) or only one part is present.
        if (
            len(emitted_face_parts) == len(emitted_mesh.faces)
            and len({p for p in emitted_face_parts if p}) > 1
        ):
            scene_runtime = RuntimeMesh(
                mesh=emitted_mesh,
                face_parts=list(emitted_face_parts),
                part_colors=dict(uv_runtime.part_colors),
                units=uv_runtime.units,
            )
            export_runtime_scene_glb(scene_runtime, lod_path)
        elif (
            result.level == 0
            and multi_part_scene is not None
            and getattr(multi_part_scene, "manifest", None)
            and len(multi_part_scene.manifest) > 1
            and len(emitted_face_parts) != len(emitted_mesh.faces)
        ):
            # Last-resort multi-part rescue for LOD0: when the per-face
            # label vector lost alignment somewhere upstream (e.g. xatlas
            # single-mesh path collapsed a multi-part mesh, or
            # subdivision in the high-poly path desynced labels), fall
            # back to exporting the topology stage's multi_part_scene
            # directly. This trades a stale label set for keeping the
            # named child hierarchy that engine importers depend on, so
            # the LOD0 still opens as 18 parts in Unity / Godot / Unreal
            # rather than as a single fused StaticMesh. Lower LODs stay
            # on the single-mesh path (their topology is rebuilt by QEM
            # and there's no clean multi-part source for them).
            export_multi_part_scene_glb(multi_part_scene, lod_path)
        else:
            export_glb(emitted_mesh, lod_path)
        rel = relpath(executor.out_dir, lod_path)
        entry = {
            "level": result.level,
            "ratio": result.ratio,
            "tris": emitted_tris,
            "verts": emitted_verts,
            "path": rel,
            "distance_min": result.distance_min,
            "distance_max": result.distance_max,
            "screen_coverage": result.screen_coverage,
        }
        lod_manifest_entries.append(entry)
        # Back-compat shape for downstream code expecting ``lods`` list entries.
        lod_decimation_label = "quadric_edge_collapse" if result.ratio < 1.0 else "source"
        if decimater_report and decimater_report.get("decimater_used"):
            lod_decimation_label = "target_quads_qem_v1"
        lods.append(
            {
                "name": f"lod{result.level}",
                "mesh_uri": rel,
                "triangle_count": emitted_tris,
                "vertex_count": emitted_verts,
                "decimation": lod_decimation_label,
                "distance_min": result.distance_min,
                "distance_max": result.distance_max,
                "screen_coverage": result.screen_coverage,
            }
        )

    # Hero / target_quads diagnostic: warn (not block) when we have a
    # target but the runtime mesh is over-budget by >2x and the
    # decimater also failed to land it inside budget. The validator
    # phase escalates this to a blocker for hero/aaa_hero.
    if (
        target_tris > 0
        and lods
        and lods[0].get("triangle_count", 0) > target_tris * 2
        and not any(r.get("decimater_used") for r in decimater_reports)
    ):
        diagnostics.append(
            {
                "code": "LOD_TARGET_QUADS_OVER_BUDGET",
                "level": "warning",
                "message": (
                    f"runtime LOD0 emitted {lods[0].get('triangle_count')} tris, "
                    f"more than 2x declared target_quads={target_quads_declared} "
                    f"({target_tris} tris). Consider lowering shape density or "
                    f"raising target_quads."
                ),
            }
        )

    lod_manifest = {
        "schemaVersion": 1,
        "lods": lod_manifest_entries,
    }
    lod_manifest_path = stage_dir / "lod_manifest.json"
    dump_json(lod_manifest_path, lod_manifest)

    # Convex collision proxies — single hull + per-part hulls.
    single = collision_mod.single_hull(uv_runtime.mesh)
    single_path = stage_dir / "collision_hull.glb"
    export_glb(single.mesh, single_path)

    part_proxies = collision_mod.per_part_hulls(uv_runtime.mesh, list(uv_runtime.face_parts))
    parts_mesh = collision_mod.combine_hulls(part_proxies)
    parts_path = stage_dir / "collision_parts.glb"
    # Each convex hull is already a separate Trimesh, so emit them as
    # named scene nodes. Game engines (Godot's CollisionShape3D, Unity
    # mesh colliders, Unreal complex collision) consume per-part
    # convex hulls naturally as a child hierarchy.
    if len(part_proxies) > 1:
        export_scene_glb_from_named_meshes(
            ((p.name, p.mesh) for p in part_proxies), parts_path
        )
    else:
        export_glb(parts_mesh, parts_path)

    collision_manifest = {
        "schemaVersion": 1,
        "proxies": [
            {
                "name": "hull",
                "tris": len(single.mesh.faces),
                "verts": len(single.mesh.vertices),
                "aabb": {"min": list(single.aabb_min), "max": list(single.aabb_max)},
                "path": relpath(executor.out_dir, single_path),
            },
            {
                "name": "parts",
                "path": relpath(executor.out_dir, parts_path),
                "subproxies": [
                    {
                        "name": p.name,
                        "tris": len(p.mesh.faces),
                        "verts": len(p.mesh.vertices),
                        "aabb": {"min": list(p.aabb_min), "max": list(p.aabb_max)},
                    }
                    for p in part_proxies
                ],
            },
        ],
    }
    collision_manifest_path = stage_dir / "collision_manifest.json"
    dump_json(collision_manifest_path, collision_manifest)
    highlow_relation = _publish_lod_highlow_relation(
        executor,
        shape_cfg=shape_cfg,
        lods=lods,
        high_mesh_uri=high_source_uri,
        high_triangle_count=high_source_triangle_count,
        high_source_report=high_source_report,
        hero_mode=hero_mode,
    )

    draw_calls = max(1, int(cfg.get("draw_calls") or 1)) if cfg.get("draw_calls") is not None else 1
    texture_memory_bytes = 0
    bundle = {
        "backend_id": "lathe.optimize.deterministic_lod_v1",
        "lods": lods,
        "lod_manifest_path": relpath(executor.out_dir, lod_manifest_path),
        "collision": {
            "hull_uri": relpath(executor.out_dir, single_path),
            "parts_uri": relpath(executor.out_dir, parts_path),
            "manifest_path": relpath(executor.out_dir, collision_manifest_path),
            "hull_tris": len(single.mesh.faces),
            "parts_count": len(part_proxies),
        },
        "draw_calls": draw_calls,
        "texture_memory_bytes": texture_memory_bytes,
        "mesh_compression": bool(cfg.get("mesh_compression", False)),
        "atlas": bool(cfg.get("atlas", False)),
        "authored_lod_controls": {
            "shape_lod_levels": shape_cfg.get("lod_levels"),
            "shape_lod_ratios": list(shape_cfg.get("lod_ratios", []))
            if isinstance(shape_cfg.get("lod_ratios"), list)
            else [],
            "resolved_ratios": list(lod_ratios),
        },
        "authored_highlow_controls": {
            "highlow_mode": shape_cfg.get("highlow_mode", ""),
            "highlow_low_lod": shape_cfg.get("highlow_low_lod", None),
            "highlow_bake_cage_offset_cm": shape_cfg.get("highlow_bake_cage_offset_cm", None),
        },
        "procedural_high_source": high_source_report or {},
        "high_source_uri": high_source_uri,
        "high_source_triangle_count": high_source_triangle_count,
        "hero_mode": bool(hero_mode),
        "lod0_face_budget": int(lod0_face_budget),
        "lod0_face_budget_source": lod0_budget_source,
        "per_part_lod0_report": per_part_lod0_report or {},
        "multi_part_scene_present": multi_part_scene is not None,
        "multi_part_part_count": (
            len(multi_part_manifest) if multi_part_manifest is not None else 0
        ),
        "target_quads_declared": int(target_quads_declared),
        "target_quads_actual": int(lods[0].get("triangle_count", 0) // 2) if lods else 0,
        "target_quads_source": (
            "build.topology.target_quads"
            if isinstance(topology_cfg, dict) and topology_cfg.get("target_quads") is not None
            else "build.shape.target_quads"
            if shape_cfg.get("target_quads") is not None
            else "unset"
        ),
        "decimater_reports": decimater_reports,
        "decimater_used": any(r.get("decimater_used") for r in decimater_reports),
        "decimater_reduction_ratio": (
            round(
                sum(float(r.get("reduction_ratio", 0.0) or 0.0) for r in decimater_reports)
                / max(1, sum(1 for r in decimater_reports if r.get("decimater_used"))),
                6,
            )
            if any(r.get("decimater_used") for r in decimater_reports)
            else 0.0
        ),
        "diagnostics": diagnostics,
    }
    if highlow_relation is not None:
        bundle["highlow_relation"] = highlow_relation
    # STAGE-7/8: evaluate budgets after LODs/collision so we can reference the
    # real runtime data (surface materials + emitted LODs). The report is
    # written to disk and embedded in the bundle for downstream consumers
    # (reports stage, selector manifest).
    # Hand the upstream UV runtime mesh through to downstream stages so
    # PBR atlas UVs survive into the package stage's main `<asset>.glb`.
    # The decimater rebuilds Trimeshes without UV channels so we cannot
    # use the LOD0 mesh directly for the main package export. The
    # package stage relies on this runtime mesh's `face_parts` (carried
    # over from the UV stage) to emit a multi-part scene glb when the
    # mesh is genuinely multi-part.
    executor.runtime["optimize"] = {"bundle": bundle, "runtime_mesh": uv_runtime}
    budget_report, budget_diagnostics = budgets_mod.evaluate(executor.asset, executor.runtime)
    budget_report_path = stage_dir / "budget_report.json"
    dump_json(budget_report_path, budget_report)
    bundle["budget_report"] = budget_report
    bundle["budget_report_path"] = relpath(executor.out_dir, budget_report_path)
    if budget_diagnostics:
        bundle["diagnostics"] = list(diagnostics) + list(budget_diagnostics)
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
