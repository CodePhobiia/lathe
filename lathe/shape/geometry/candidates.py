"""Candidate mesh builders for the shape stage.

Mode-specific generators (generate/reconstruct/adapt/assemble) that
produce runtime-candidate dicts compatible with the
``lathe.shape.intent_mesh_handoff_v1`` handoff bundle. Retained intact
from the pre-decomposition ``shape_backend.py`` so downstream behavior
is byte-identical.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from ...constants import RNG_PRIME_OFFSET
from .conditioning import _conditioned_body_extents, _conditioned_part_colors
from .primitives import (
    _characteristic_scale_cm,
    _clamp,
    _concat_named_meshes,
    _load_mesh_file,
    _normalize_mesh_to_scale,
    _translated_box,
    _translated_cylinder,
)


def _candidate_rng(seed: int, index: int) -> np.random.Generator:
    return np.random.default_rng(seed + index * RNG_PRIME_OFFSET)


def _root_name(parts: list[str]) -> str:
    """Pick the structural root part name from an asset's parts list.

    Upstream contract (``intent.parts`` under ``lathe.shape.intent_mesh_handoff_v1``):
    a part whose name contains any of ``body``/``hull``/``core``/``base``
    tokens is treated as the root; otherwise the first declared part is
    the root. Kept as an explicit ``if/else`` (not a ternary) per
    Plan 10 Mi2 so later contract drift surfaces in code review rather
    than being buried inside an expression.
    """
    body_names = [
        name
        for name in parts
        if any(token in name for token in ("body", "hull", "core", "base"))
    ]
    if body_names:
        return body_names[0]
    return parts[0]


def _mechanical_named_meshes(asset: dict[str, Any], conditioning: dict[str, Any], rng: np.random.Generator) -> list[tuple[str, trimesh.Trimesh]]:
    parts = list(asset.get("intent", {}).get("parts", [])) or ["body"]
    root_name = _root_name(parts)
    extents = _conditioned_body_extents(asset, conditioning, rng)
    scale_cm = _characteristic_scale_cm(asset)
    named_meshes: list[tuple[str, trimesh.Trimesh]] = []

    root_meshes = [
        _translated_box(extents, [0.0, 0.0, 0.0]),
        _translated_box(extents * np.array([0.66, 0.45, 0.3]), [0.0, extents[1] * 0.32, 0.0]),
        _translated_box(extents * np.array([0.34, 0.22, 0.18]), [0.0, -extents[1] * 0.42, extents[2] * 0.18]),
    ]
    rotor_names = [name for name in parts if any(token in name.lower() for token in ("rotor", "fan", "prop"))]
    if rotor_names:
        arm_half_width = scale_cm * 0.024
        arm_height = scale_cm * 0.018
        arm_depth = extents[2] * 0.72
        arm_span = extents[0] * 1.55
        root_meshes.extend(
            [
                _translated_box([arm_span, arm_height, arm_half_width], [0.0, extents[1] * 0.18, arm_depth * 0.48]),
                _translated_box([arm_span, arm_height, arm_half_width], [0.0, extents[1] * 0.18, -arm_depth * 0.48]),
                _translated_box([arm_half_width, arm_height, arm_depth], [arm_span * 0.48, extents[1] * 0.18, 0.0]),
                _translated_box([arm_half_width, arm_height, arm_depth], [-arm_span * 0.48, extents[1] * 0.18, 0.0]),
            ]
        )
    named_meshes.append((root_name, trimesh.util.concatenate(root_meshes)))

    rotor_positions = [
        [extents[0] * 1.1, extents[1] * 0.58, extents[2] * 1.02],
        [-extents[0] * 1.1, extents[1] * 0.58, extents[2] * 1.02],
        [extents[0] * 1.1, extents[1] * 0.58, -extents[2] * 1.02],
        [-extents[0] * 1.1, extents[1] * 0.58, -extents[2] * 1.02],
    ]
    leg_positions = [
        [extents[0] * 0.65, -extents[1] * 0.95, extents[2] * 0.26],
        [-extents[0] * 0.65, -extents[1] * 0.95, -extents[2] * 0.26],
    ]
    rotor_idx = 0
    leg_idx = 0
    generic_idx = 0
    for name in parts:
        if name == root_name:
            continue
        lname = name.lower()
        if any(token in lname for token in ("rotor", "fan", "prop")):
            pos = rotor_positions[rotor_idx % len(rotor_positions)]
            rotor_idx += 1
            radius = scale_cm * _clamp(0.085 + float(rng.uniform(-0.008, 0.008)), 0.065, 0.11)
            height = scale_cm * 0.015
            named_meshes.append((name, _translated_cylinder(radius, height, pos, axis="y")))
        elif any(token in lname for token in ("leg", "foot")):
            pos = leg_positions[leg_idx % len(leg_positions)]
            leg_idx += 1
            named_meshes.append((name, _translated_box([scale_cm * 0.04, scale_cm * 0.2, scale_cm * 0.04], pos)))
        elif any(token in lname for token in ("door", "hatch", "cargo")):
            center = [0.0, -extents[1] * 0.54, extents[2] * 0.16]
            named_meshes.append((name, _translated_box([extents[0] * 0.72, scale_cm * 0.03, extents[2] * 0.34], center)))
        elif any(token in lname for token in ("camera", "gimbal", "sensor")):
            center = [0.0, -extents[1] * 0.74, extents[2] * 0.48]
            named_meshes.append((name, _translated_cylinder(scale_cm * 0.05, scale_cm * 0.08, center, axis="y")))
        else:
            angle = 2.0 * math.pi * generic_idx / max(1, len(parts) - 1)
            generic_idx += 1
            center = [math.cos(angle) * extents[0] * 0.82, 0.0, math.sin(angle) * extents[2] * 0.82]
            named_meshes.append((name, _translated_box([scale_cm * 0.12, scale_cm * 0.08, scale_cm * 0.18], center)))
    return named_meshes


def _env_module_named_meshes(asset: dict[str, Any], conditioning: dict[str, Any], rng: np.random.Generator) -> list[tuple[str, trimesh.Trimesh]]:
    parts = list(asset.get("intent", {}).get("parts", [])) or ["body"]
    scale_cm = _characteristic_scale_cm(asset)
    front_aspect = float(conditioning.get("front_aspect") or 1.3)
    side_aspect = float(conditioning.get("side_aspect") or 1.0)
    width = scale_cm * _clamp(1.15 + 0.26 * front_aspect + float(rng.uniform(-0.04, 0.04)), 1.0, 2.2)
    height = scale_cm * _clamp(0.95 + 0.18 / max(0.8, front_aspect) + float(rng.uniform(-0.03, 0.03)), 0.8, 1.5)
    depth = scale_cm * _clamp(0.85 + 0.2 * side_aspect + float(rng.uniform(-0.04, 0.04)), 0.8, 1.8)
    named_meshes: list[tuple[str, trimesh.Trimesh]] = []
    for idx, name in enumerate(parts):
        lname = name.lower()
        if "floor" in lname:
            named_meshes.append((name, _translated_box([width, 8.0, depth], [0.0, -height / 2.0 + 4.0, 0.0])))
        elif "ceiling" in lname or "roof" in lname:
            named_meshes.append((name, _translated_box([width, 8.0, depth], [0.0, height / 2.0 - 4.0, 0.0])))
        elif "wall" in lname:
            side = idx % 4
            thickness = 6.0
            if side == 0:
                center = [0.0, 0.0, depth / 2.0 - thickness / 2.0]
                extents = [width, height, thickness]
            elif side == 1:
                center = [0.0, 0.0, -depth / 2.0 + thickness / 2.0]
                extents = [width, height, thickness]
            elif side == 2:
                center = [width / 2.0 - thickness / 2.0, 0.0, 0.0]
                extents = [thickness, height, depth]
            else:
                center = [-width / 2.0 + thickness / 2.0, 0.0, 0.0]
                extents = [thickness, height, depth]
            named_meshes.append((name, _translated_box(extents, center)))
        elif "column" in lname or "pillar" in lname:
            angle = 2.0 * math.pi * idx / max(1, len(parts))
            named_meshes.append((name, _translated_box([10.0, height, 10.0], [math.cos(angle) * width * 0.35, 0.0, math.sin(angle) * depth * 0.35])))
        else:
            named_meshes.append((name, _translated_box([width * 0.2, height * 0.4, depth * 0.2], [0.0, 0.0, 0.0])))
    return named_meshes


def _score_candidate(asset: dict[str, Any], conditioning: dict[str, Any], *, mode: str, index: int, ref_bonus: float) -> float:
    role = str(asset.get("intent", {}).get("role", "")).lower()
    parts = list(asset.get("intent", {}).get("parts", []))
    score = 0.71 if mode == "generate" else 0.8
    if conditioning.get("image_refs"):
        score += 0.05
    if conditioning.get("mesh_refs"):
        score += 0.08
    if mode == "reconstruct" and conditioning.get("mesh_refs"):
        score += 0.05
    if mode == "adapt" and conditioning.get("mesh_refs"):
        score += 0.04
    if mode == "assemble" and conditioning.get("mesh_refs"):
        score += 0.05
    if "drone" in role and sum(1 for part in parts if "rotor" in part.lower()) >= 4:
        score += 0.08
    if asset.get("build", {}).get("shape", {}).get("symmetry") in {"x", "z"}:
        score += 0.03
    score += min(0.04, 0.008 * max(0, len(parts) - 1))
    score += ref_bonus
    score -= 0.01 * index
    return round(min(0.99, max(0.4, score)), 6)


def _generate_conditioned_candidates(asset: dict[str, Any], seed: int, candidates_count: int, conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    parts = list(asset.get("intent", {}).get("parts", [])) or ["body"]
    for index in range(candidates_count):
        rng = _candidate_rng(seed, index)
        named_meshes = _env_module_named_meshes(asset, conditioning, rng) if asset.get("kind") == "env_module" else _mechanical_named_meshes(asset, conditioning, rng)
        part_colors = _conditioned_part_colors(parts, conditioning)
        runtime = _concat_named_meshes(named_meshes, part_colors)
        runtime["meta"] = {
            "parts": parts,
            "coarse_material_slots": 1,
            "score": _score_candidate(asset, conditioning, mode="generate", index=index, ref_bonus=0.02),
            "selection_notes": [
                f"generated from intent with {len(conditioning.get('image_refs', []))} image refs",
                f"front_aspect={conditioning.get('front_aspect')}",
                f"side_aspect={conditioning.get('side_aspect')}",
                f"candidate_index={index}",
            ],
            "conditioning": {
                "mode": "generate",
                "reference_strength": conditioning.get("reference_strength", 0.0),
            },
        }
        out.append(runtime)
    return out


def _runtime_from_external_mesh(asset: dict[str, Any], mesh: trimesh.Trimesh, conditioning: dict[str, Any], *, mode: str, index: int, include_accessories: bool) -> dict[str, Any]:
    parts = list(asset.get("intent", {}).get("parts", [])) or ["body"]
    root_name = _root_name(parts)
    part_colors = _conditioned_part_colors(parts, conditioning)
    mesh = _normalize_mesh_to_scale(mesh, _characteristic_scale_cm(asset))
    named_meshes: list[tuple[str, trimesh.Trimesh]] = [(root_name, mesh)]
    if include_accessories and asset.get("kind") != "env_module":
        rng = _candidate_rng(17, index)
        extras = [pair for pair in _mechanical_named_meshes(asset, conditioning, rng) if pair[0] != root_name]
        named_meshes.extend(extras)
    runtime = _concat_named_meshes(named_meshes, part_colors)
    runtime["meta"] = {
        "parts": parts,
        "coarse_material_slots": 1,
        "score": _score_candidate(asset, conditioning, mode=mode, index=index, ref_bonus=0.05 if include_accessories else 0.03),
        "selection_notes": [
            f"{mode} candidate derived from external mesh",
            f"include_accessories={include_accessories}",
            f"candidate_index={index}",
        ],
        "conditioning": {"mode": mode, "reference_strength": conditioning.get("reference_strength", 0.0)},
    }
    return runtime


def _generate_reconstruct_candidates(asset: dict[str, Any], seed: int, candidates_count: int, conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    mesh_refs = [item for item in conditioning.get("mesh_refs", []) if item.get("path")]
    for index in range(min(candidates_count, len(mesh_refs))):
        path = Path(mesh_refs[index]["path"])
        mesh = _load_mesh_file(path)
        if mesh is None:
            continue
        runtime = _runtime_from_external_mesh(asset, mesh, conditioning, mode="reconstruct", index=index, include_accessories=False)
        runtime["meta"]["selection_notes"].insert(0, f"reconstructed from mesh ref '{path.name}'")
        out.append(runtime)
    if len(out) < candidates_count:
        generated = _generate_conditioned_candidates(asset, seed, candidates_count - len(out), conditioning)
        for item in generated:
            item["meta"]["selection_notes"].insert(0, "reconstructed from image conditioning fallback")
            item["meta"]["conditioning"]["mode"] = "reconstruct"
            item["meta"]["score"] = _score_candidate(asset, conditioning, mode="reconstruct", index=len(out), ref_bonus=0.02)
            out.append(item)
    return out[:candidates_count]


def _generate_adapt_candidates(asset: dict[str, Any], seed: int, candidates_count: int, conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    mesh_refs = [item for item in conditioning.get("mesh_refs", []) if item.get("path")]
    for index in range(min(candidates_count, len(mesh_refs))):
        path = Path(mesh_refs[index]["path"])
        mesh = _load_mesh_file(path)
        if mesh is None:
            continue
        runtime = _runtime_from_external_mesh(asset, mesh, conditioning, mode="adapt", index=index, include_accessories=True)
        runtime["meta"]["selection_notes"].insert(0, f"adapted from mesh ref '{path.name}'")
        out.append(runtime)
    if len(out) < candidates_count:
        generated = _generate_conditioned_candidates(asset, seed, candidates_count - len(out), conditioning)
        for item in generated:
            item["meta"]["selection_notes"].insert(0, "adapt fallback generated from refs and intent")
            item["meta"]["conditioning"]["mode"] = "adapt"
            item["meta"]["score"] = _score_candidate(asset, conditioning, mode="adapt", index=len(out), ref_bonus=0.01)
            out.append(item)
    return out[:candidates_count]


def _generate_assemble_candidates(asset: dict[str, Any], seed: int, candidates_count: int, conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    mesh_refs = [item for item in conditioning.get("mesh_refs", []) if item.get("path")]
    parts = list(asset.get("intent", {}).get("parts", [])) or ["body"]
    part_colors = _conditioned_part_colors(parts, conditioning)
    out: list[dict[str, Any]] = []
    if mesh_refs:
        base_meshes = []
        spacing = _characteristic_scale_cm(asset) * 0.8
        for idx, ref in enumerate(mesh_refs):
            path = Path(ref["path"])
            mesh = _load_mesh_file(path)
            if mesh is None:
                continue
            mesh = _normalize_mesh_to_scale(mesh, _characteristic_scale_cm(asset) * 0.55)
            mesh.apply_translation([spacing * (idx - (len(mesh_refs) - 1) / 2.0), 0.0, 0.0])
            base_meshes.append((parts[idx % len(parts)], mesh))
        if base_meshes:
            runtime = _concat_named_meshes(base_meshes, part_colors)
            runtime["meta"] = {
                "parts": parts,
                "coarse_material_slots": 1,
                "score": _score_candidate(asset, conditioning, mode="assemble", index=0, ref_bonus=0.05),
                "selection_notes": [f"assembled from {len(base_meshes)} mesh refs"],
                "conditioning": {"mode": "assemble", "reference_strength": conditioning.get("reference_strength", 0.0)},
            }
            out.append(runtime)
    if len(out) < candidates_count:
        generated = _generate_conditioned_candidates(asset, seed, candidates_count - len(out), conditioning)
        for item in generated:
            item["meta"]["selection_notes"].insert(0, "assemble fallback generated from refs and intent")
            item["meta"]["conditioning"]["mode"] = "assemble"
            item["meta"]["score"] = _score_candidate(asset, conditioning, mode="assemble", index=len(out), ref_bonus=0.01)
            out.append(item)
    return out[:candidates_count]
