"""Geometry primitives and mesh repair/analysis helpers.

Extracted from ``lathe/executor.py`` during Stage 2.IV. All helpers here are
stateless utilities consumed by stage modules. ``run_reference_topology_cleanup``
is re-exported from ``lathe.executor`` as ``_run_reference_topology_cleanup``
because tests import it directly.

NOTE(Stage 2.IV): ``generate_candidate_mesh`` is preserved byte-for-byte even
though no current call site references it; follow-up cleanup should decide
whether to delete it entirely.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import trimesh

from .common import characteristic_scale_cm, make_color
from .mesh import RuntimeMesh
from .seeding import candidate_rng


def translated_box(extents: Iterable[float], center: Iterable[float]) -> trimesh.Trimesh:
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    return trimesh.creation.box(extents=np.array(list(extents), dtype=float), transform=matrix)


def translated_cylinder(radius: float, height: float, center: Iterable[float], axis: str = "y") -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=24)
    if axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
    elif axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]))
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    mesh.apply_transform(matrix)
    return mesh


def generate_candidate_mesh(asset: dict[str, Any], *, index: int, seed: int) -> tuple[RuntimeMesh, dict[str, Any]]:
    rng = candidate_rng(seed, index)
    scale_cm = characteristic_scale_cm(asset)
    role = asset.get("intent", {}).get("role", "")
    parts = list(asset.get("intent", {}).get("parts", []))
    if not parts:
        parts = ["body"]
    kind = asset.get("kind")
    part_meshes: list[trimesh.Trimesh] = []
    face_parts: list[str] = []
    part_colors = {part: make_color(part) for part in parts}

    def add_part(name: str, mesh: trimesh.Trimesh) -> None:
        part_meshes.append(mesh)
        face_parts.extend([name] * int(len(mesh.faces)))

    body_names = [name for name in parts if any(token in name for token in ("body", "hull", "core", "base"))]
    root_name = body_names[0] if body_names else parts[0]

    if kind == "env_module":
        width = scale_cm * float(1.6 + 0.1 * rng.uniform(-1, 1))
        height = scale_cm * float(1.2 + 0.05 * rng.uniform(-1, 1))
        depth = scale_cm * float(1.0 + 0.1 * rng.uniform(-1, 1))
        for idx, name in enumerate(parts):
            lname = name.lower()
            if "floor" in lname:
                add_part(name, translated_box([width, 8.0, depth], [0.0, -height / 2.0 + 4.0, 0.0]))
            elif "ceiling" in lname or "roof" in lname:
                add_part(name, translated_box([width, 8.0, depth], [0.0, height / 2.0 - 4.0, 0.0]))
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
                add_part(name, translated_box(extents, center))
            elif "column" in lname or "pillar" in lname:
                angle = 2.0 * math.pi * idx / max(1, len(parts))
                add_part(name, translated_box([10.0, height, 10.0], [math.cos(angle) * width * 0.35, 0.0, math.sin(angle) * depth * 0.35]))
            else:
                add_part(name, translated_box([width * 0.2, height * 0.4, depth * 0.2], [0.0, 0.0, 0.0]))
    else:
        body_extents = np.array([
            scale_cm * float(0.38 + 0.04 * rng.uniform(-1, 1)),
            scale_cm * float(0.14 + 0.02 * rng.uniform(-1, 1)),
            scale_cm * float(0.48 + 0.04 * rng.uniform(-1, 1)),
        ])
        root_mesh = translated_box(body_extents, [0.0, 0.0, 0.0])
        add_part(root_name, root_mesh)
        rotor_positions = [
            [body_extents[0] * 0.9, body_extents[1] * 0.55, body_extents[2] * 0.85],
            [-body_extents[0] * 0.9, body_extents[1] * 0.55, body_extents[2] * 0.85],
            [body_extents[0] * 0.9, body_extents[1] * 0.55, -body_extents[2] * 0.85],
            [-body_extents[0] * 0.9, body_extents[1] * 0.55, -body_extents[2] * 0.85],
        ]
        leg_positions = [
            [body_extents[0] * 0.55, -body_extents[1] * 0.75, body_extents[2] * 0.25],
            [-body_extents[0] * 0.55, -body_extents[1] * 0.75, -body_extents[2] * 0.25],
        ]
        generic_idx = 0
        rotor_idx = 0
        leg_idx = 0
        for name in parts:
            if name == root_name:
                continue
            lname = name.lower()
            if "rotor" in lname or "fan" in lname or "prop" in lname:
                pos = rotor_positions[rotor_idx % len(rotor_positions)]
                rotor_idx += 1
                radius = scale_cm * float(0.09 + 0.01 * rng.uniform(-1, 1))
                height = scale_cm * 0.015
                add_part(name, translated_cylinder(radius, height, pos, axis="y"))
            elif "leg" in lname or "foot" in lname:
                pos = leg_positions[leg_idx % len(leg_positions)]
                leg_idx += 1
                add_part(name, translated_box([scale_cm * 0.04, scale_cm * 0.18, scale_cm * 0.04], pos))
            elif "door" in lname or "hatch" in lname or "cargo" in lname:
                center = [0.0, -body_extents[1] * 0.55, body_extents[2] * 0.15]
                add_part(name, translated_box([body_extents[0] * 0.7, scale_cm * 0.03, body_extents[2] * 0.35], center))
            elif "camera" in lname or "gimbal" in lname or "sensor" in lname:
                center = [0.0, -body_extents[1] * 0.7, body_extents[2] * 0.45]
                add_part(name, translated_cylinder(scale_cm * 0.05, scale_cm * 0.08, center, axis="y"))
            else:
                angle = 2.0 * math.pi * generic_idx / max(1, len(parts) - 1)
                generic_idx += 1
                center = [math.cos(angle) * body_extents[0] * 0.8, 0.0, math.sin(angle) * body_extents[2] * 0.8]
                add_part(name, translated_box([scale_cm * 0.12, scale_cm * 0.08, scale_cm * 0.18], center))

    combined = trimesh.util.concatenate(part_meshes)
    score = 0.72
    if "drone" in role.lower() and sum(1 for part in parts if "rotor" in part.lower()) >= 4:
        score += 0.18
    if asset.get("build", {}).get("shape", {}).get("symmetry") in {"x", "z"}:
        score += 0.04
    score += min(0.06, 0.01 * max(0, len(parts) - 1))
    score = min(0.99, score)
    return RuntimeMesh(mesh=combined, face_parts=face_parts, part_colors=part_colors, units="cm"), {
        "parts": parts,
        "score": round(float(score), 6),
        "selection_notes": [
            f"generated procedurally from role='{role}'",
            f"parts={len(parts)}",
            f"candidate_index={index}",
        ],
    }


def seal_non_watertight_mesh(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, str | None]:
    if mesh.is_watertight:
        return mesh, None
    repaired = mesh.copy()
    try:
        repaired.fill_holes()
    except Exception:  # noqa: BLE001
        pass
    if repaired.is_watertight:
        return repaired, "fill_holes"
    try:
        hull = repaired.convex_hull
        if hull is not None and len(hull.faces) > 0 and hull.is_watertight:
            return hull, "convex_hull"
    except Exception:  # noqa: BLE001
        pass
    return repaired, None


def quadrant_tokens(part_name: str) -> tuple[int | None, int | None]:
    name = part_name.lower()
    if "_fl" in name or name.endswith("fl"):
        return 1, 1
    if "_fr" in name or name.endswith("fr"):
        return -1, 1
    if "_rl" in name or name.endswith("rl"):
        return 1, -1
    if "_rr" in name or name.endswith("rr"):
        return -1, -1
    return None, None


def assign_faces_by_score(assignments: np.ndarray, score: np.ndarray, part_name: str, face_count: int) -> None:
    if face_count <= 0:
        return
    order = np.argsort(score)[::-1]
    chosen = 0
    for face_index in order:
        if score[face_index] <= 0:
            continue
        assignments[face_index] = part_name
        chosen += 1
        if chosen >= face_count:
            break


def infer_face_parts_from_mesh(mesh: trimesh.Trimesh, expected_parts: list[str], default_name: str) -> list[str]:
    face_count = int(len(mesh.faces))
    if face_count == 0:
        return []
    centroids = np.asarray(mesh.triangles_center, dtype=np.float64)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    center = (bounds[0] + bounds[1]) / 2.0
    half_extents = np.maximum((bounds[1] - bounds[0]) / 2.0, 1e-6)
    normalized = (centroids - center) / half_extents
    x = normalized[:, 0]
    y = normalized[:, 1]
    z = normalized[:, 2]
    radial = np.sqrt(np.maximum(0.0, x * x + z * z))
    assignments = np.array([default_name] * face_count, dtype=object)

    rotor_parts = [part for part in expected_parts if any(token in part.lower() for token in ("rotor", "fan", "prop"))]
    rotor_target = max(4, face_count // max(12, len(rotor_parts) * 8)) if rotor_parts else 0
    for part_name in rotor_parts:
        x_sign, z_sign = quadrant_tokens(part_name)
        score = np.maximum(0.0, y) * 0.35 + np.maximum(0.0, radial - 0.2) * 0.65
        if x_sign is not None:
            score += 0.4 * np.maximum(0.0, x * x_sign)
        if z_sign is not None:
            score += 0.4 * np.maximum(0.0, z * z_sign)
        assign_faces_by_score(assignments, score, part_name, rotor_target)

    leg_parts = [part for part in expected_parts if any(token in part.lower() for token in ("leg", "foot"))]
    leg_target = max(3, face_count // max(18, len(leg_parts) * 10)) if leg_parts else 0
    for part_name in leg_parts:
        x_sign = 1 if any(token in part_name.lower() for token in ("_l", " left")) else -1 if any(token in part_name.lower() for token in ("_r", " right")) else 0
        score = np.maximum(0.0, -y) * 0.6 + np.maximum(0.0, np.abs(x) - 0.1) * 0.4
        if x_sign != 0:
            score += 0.35 * np.maximum(0.0, x * x_sign)
        assign_faces_by_score(assignments, score, part_name, leg_target)

    for part_name in expected_parts:
        lname = part_name.lower()
        if any(token in lname for token in ("door", "hatch", "cargo")):
            score = np.maximum(0.0, z) * 0.7 + np.maximum(0.0, -np.abs(y - (-0.1)) + 0.8) * 0.3
            assign_faces_by_score(assignments, score, part_name, max(4, face_count // 16))
        elif any(token in lname for token in ("camera", "gimbal", "sensor")):
            score = np.maximum(0.0, z) * 0.55 + np.maximum(0.0, -y) * 0.45
            assign_faces_by_score(assignments, score, part_name, max(4, face_count // 18))
        elif any(token in lname for token in ("wing", "arm")):
            score = np.maximum(0.0, np.abs(x) - 0.15) * 0.6 + np.maximum(0.0, np.abs(z) - 0.15) * 0.4
            assign_faces_by_score(assignments, score, part_name, max(4, face_count // 16))

    missing_parts = [part for part in expected_parts if part != default_name and part not in set(assignments.tolist())]
    if missing_parts:
        order = np.argsort(np.linalg.norm(normalized, axis=1))[::-1]
        cursor = 0
        for part_name in missing_parts:
            while cursor < len(order) and assignments[order[cursor]] != default_name:
                cursor += 1
            if cursor >= len(order):
                break
            assignments[order[cursor]] = part_name
            cursor += 1

    return [str(value) for value in assignments.tolist()]


def run_reference_topology_cleanup(runtime_mesh: RuntimeMesh, asset: dict[str, Any] | None = None) -> tuple[RuntimeMesh, dict[str, Any]]:
    mesh = runtime_mesh.mesh.copy()
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    initial_watertight = bool(mesh.is_watertight)
    if not initial_watertight:
        mesh.merge_vertices()
        mesh.fix_normals(multibody=False)
        mesh, seal_strategy = seal_non_watertight_mesh(mesh)
    else:
        seal_strategy = None
    face_parts = list(runtime_mesh.face_parts)
    inferred_parts = False
    if asset is not None:
        expected_parts = list(asset.get("intent", {}).get("parts", []))
        default_name = next((name for name in expected_parts if any(token in name.lower() for token in ("body", "hull", "core", "base"))), expected_parts[0] if expected_parts else "mesh")
        counts = Counter(face_parts) if face_parts else Counter()
        sparse_nondefault = sum(1 for name, count in counts.items() if name != default_name and count <= 2)
        part_distribution_unreliable = (
            len(face_parts) != len(mesh.faces)
            or len(set(face_parts)) <= 1
            or (expected_parts and len(set(face_parts)) < max(2, len(expected_parts) // 2))
            or sparse_nondefault >= max(2, min(len(expected_parts), 4))
        )
        if expected_parts and part_distribution_unreliable:
            face_parts = infer_face_parts_from_mesh(mesh, expected_parts, default_name)
            inferred_parts = True
    return (
        RuntimeMesh(
            mesh=mesh,
            face_parts=face_parts if len(face_parts) == len(mesh.faces) else [next(iter(runtime_mesh.part_colors), "mesh")] * int(len(mesh.faces)),
            part_colors=dict(runtime_mesh.part_colors),
            units=runtime_mesh.units,
        ),
        {
            "mode": "reference_cleanup",
            "seal_strategy": seal_strategy,
            "heuristic_part_groups": inferred_parts,
        },
    )


def runtime_scene_parts(runtime_mesh: RuntimeMesh) -> list[tuple[str, trimesh.Trimesh]]:
    if not runtime_mesh.face_parts or len(runtime_mesh.face_parts) != len(runtime_mesh.mesh.faces):
        return [("mesh", runtime_mesh.mesh.copy())]
    parts: list[tuple[str, trimesh.Trimesh]] = []
    for part in sorted(set(runtime_mesh.face_parts)):
        face_indices = [idx for idx, name in enumerate(runtime_mesh.face_parts) if name == part]
        submesh = runtime_mesh.mesh.submesh([face_indices], append=True, repair=False)
        parts.append((part, submesh))
    return parts


def load_runtime_mesh_from_scene(path: Path, source_runtime: RuntimeMesh) -> RuntimeMesh | None:
    try:
        loaded = trimesh.load(path, force="scene")
    except Exception:  # noqa: BLE001
        return None
    if isinstance(loaded, trimesh.Scene):
        meshes: list[trimesh.Trimesh] = []
        face_parts: list[str] = []
        known_parts = set(source_runtime.part_colors)
        for name, geom in loaded.geometry.items():
            if not isinstance(geom, trimesh.Trimesh):
                continue
            meshes.append(geom.copy())
            part_name = name if name in known_parts else (next(iter(known_parts)) if known_parts else "mesh")
            face_parts.extend([part_name] * int(len(geom.faces)))
        if not meshes:
            return None
        mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
        return RuntimeMesh(mesh=mesh, face_parts=face_parts, part_colors=dict(source_runtime.part_colors), units=source_runtime.units)
    if isinstance(loaded, trimesh.Trimesh):
        part_name = next(iter(source_runtime.part_colors), "mesh")
        return RuntimeMesh(
            mesh=loaded.copy(),
            face_parts=[part_name] * int(len(loaded.faces)),
            part_colors=dict(source_runtime.part_colors),
            units=source_runtime.units,
        )
    return None


def body_count(mesh: trimesh.Trimesh) -> int:
    try:
        return int(mesh.body_count)
    except Exception:  # noqa: BLE001
        faces = np.asarray(mesh.faces, dtype=np.int64)
        if len(faces) == 0:
            return 0
        vertex_to_faces: dict[int, list[int]] = {}
        for face_index, face in enumerate(faces):
            for vertex in face:
                vertex_to_faces.setdefault(int(vertex), []).append(face_index)
        visited = np.zeros(len(faces), dtype=bool)
        body = 0
        for start in range(len(faces)):
            if visited[start]:
                continue
            body += 1
            stack = [start]
            visited[start] = True
            while stack:
                face_index = stack.pop()
                for vertex in faces[face_index]:
                    for neighbor in vertex_to_faces[int(vertex)]:
                        if not visited[neighbor]:
                            visited[neighbor] = True
                            stack.append(neighbor)
        return int(body)


def mesh_stats(mesh: trimesh.Trimesh) -> dict[str, Any]:
    bounds = mesh.bounds
    extents = bounds[1] - bounds[0]
    return {
        "vertex_count": int(len(mesh.vertices)),
        "triangle_count": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "volume": float(mesh.volume) if mesh.is_volume else 0.0,
        "bounds_min": [round(float(v), 6) for v in bounds[0]],
        "bounds_max": [round(float(v), 6) for v in bounds[1]],
        "extents": [round(float(v), 6) for v in extents],
        "body_count": body_count(mesh),
    }


def part_groups_from_face_parts(mesh: trimesh.Trimesh, face_parts: list[str]) -> list[dict[str, Any]]:
    if len(face_parts) != len(mesh.faces):
        face_parts = ["mesh"] * int(len(mesh.faces))
    groups: list[dict[str, Any]] = []
    for part in sorted(set(face_parts)):
        face_indices = [idx for idx, name in enumerate(face_parts) if name == part]
        part_mesh = mesh.submesh([face_indices], append=True, repair=False)
        groups.append({
            "name": part,
            "face_count": len(face_indices),
            "vertex_count": int(len(part_mesh.vertices)),
            "bounds_min": [round(float(v), 6) for v in part_mesh.bounds[0]],
            "bounds_max": [round(float(v), 6) for v in part_mesh.bounds[1]],
        })
    return groups


def part_centroids(mesh: trimesh.Trimesh, face_parts: list[str]) -> dict[str, list[float]]:
    if len(face_parts) != len(mesh.faces):
        face_parts = ["mesh"] * int(len(mesh.faces))
    out: dict[str, list[float]] = {}
    for part in sorted(set(face_parts)):
        face_indices = [idx for idx, name in enumerate(face_parts) if name == part]
        part_mesh = mesh.submesh([face_indices], append=True, repair=False)
        centroid = part_mesh.bounding_box.centroid
        out[part] = [float(v) for v in centroid]
    return out


def estimate_mass_kg(mesh: trimesh.Trimesh) -> float:
    volume_cm3 = abs(float(mesh.volume)) if mesh.is_volume else float(np.prod(mesh.extents)) * 0.2
    density_g_cm3 = 0.8
    return (volume_cm3 * density_g_cm3) / 1000.0


def derived_lightmap_uv(uv: np.ndarray) -> np.ndarray:
    return np.clip(uv * 0.9 + 0.05, 0.0, 1.0)
