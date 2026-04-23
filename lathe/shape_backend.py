from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import trimesh
from PIL import Image

from .asset_graph import build_asset_graph
from .conformance import fit_provider_proposals
from .scaffold_compiler import compile_scaffold_candidates
from .shape_providers import maybe_run_shape_provider


SUPPORTED_MESH_EXTS = {".glb", ".gltf", ".obj", ".ply", ".stl", ".off"}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _unit_to_cm(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "mm":
        return amount / 10.0
    if unit == "cm":
        return amount
    if unit == "m":
        return amount * 100.0
    return amount


def _characteristic_scale_cm(asset: dict[str, Any]) -> float:
    intent = asset.get("intent", {})
    if "dimensions" in intent and isinstance(intent["dimensions"], dict) and intent["dimensions"].get("type") == "call":
        args = intent["dimensions"].get("args", [])
        values = [_unit_to_cm(item["value"]) for item in args if isinstance(item, dict) and item.get("value") is not None]
        if values:
            return max(values)
    if "scale" in intent:
        return max(1.0, _unit_to_cm(intent["scale"]))
    return 200.0 if asset.get("kind") == "env_module" else 100.0


def _make_color(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)


def _candidate_rng(seed: int, index: int) -> np.random.Generator:
    return np.random.default_rng(seed + index * 7919)


def _translated_box(extents: Iterable[float], center: Iterable[float]) -> trimesh.Trimesh:
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    return trimesh.creation.box(extents=np.array(list(extents), dtype=float), transform=matrix)


def _translated_cylinder(radius: float, height: float, center: Iterable[float], axis: str = "y") -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=24)
    if axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
    elif axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]))
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    mesh.apply_transform(matrix)
    return mesh


def _resolve_ref_path(source_root: Path, value: Any) -> Path | None:
    if isinstance(value, dict) and value.get("type") == "call":
        args = value.get("args", [])
        if args:
            value = args[0].get("value")
    try:
        path = Path(str(value))
    except Exception:  # noqa: BLE001
        return None
    if not path.is_absolute():
        path = source_root / path
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if resolved.exists() and resolved.is_file():
        return resolved
    return None


def _image_kind_hint(path: Path) -> str:
    stem = path.stem.lower()
    if "front" in stem:
        return "front"
    if "side" in stem:
        return "side"
    if "top" in stem:
        return "top"
    if "mat" in stem or "material" in stem or "palette" in stem or "albedo" in stem:
        return "material"
    return "reference"


def _image_mask(image: Image.Image) -> np.ndarray:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3].astype(np.float32)
    if alpha.min() != alpha.max():
        mask = alpha > 24
    else:
        gray = rgb.mean(axis=2)
        mask = gray < 245
        if mask.sum() < 16:
            mask = gray < 250
    if mask.sum() < 16:
        mask = np.ones(mask.shape, dtype=bool)
    return mask


def _dominant_palette(rgb_pixels: np.ndarray, count: int = 3) -> list[list[int]]:
    if len(rgb_pixels) == 0:
        return []
    if len(rgb_pixels) > 4096:
        idx = np.linspace(0, len(rgb_pixels) - 1, num=4096, dtype=int)
        rgb_pixels = rgb_pixels[idx]
    bins = (rgb_pixels // 32).astype(np.int16)
    uniq, counts = np.unique(bins, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:count]
    palette = []
    for bin_rgb in uniq[order]:
        palette.append([int(bin_rgb[0] * 32 + 16), int(bin_rgb[1] * 32 + 16), int(bin_rgb[2] * 32 + 16)])
    return palette


def _analyze_image_ref(path: Path) -> dict[str, Any]:
    image = Image.open(path).convert("RGBA")
    rgba = np.asarray(image, dtype=np.uint8)
    mask = _image_mask(image)
    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    box_w = max(1, x1 - x0 + 1)
    box_h = max(1, y1 - y0 + 1)
    pixels = rgba[:, :, :3][mask]
    mean_rgb = [int(v) for v in pixels.mean(axis=0)] if len(pixels) else [200, 200, 200]
    return {
        "path": str(path),
        "kind": _image_kind_hint(path),
        "width": int(image.width),
        "height": int(image.height),
        "bbox": [x0, y0, x1, y1],
        "aspect": round(float(box_w / max(1, box_h)), 6),
        "fill_ratio": round(float(mask.sum() / max(1, box_w * box_h)), 6),
        "mean_rgb": mean_rgb,
        "palette": _dominant_palette(pixels, count=3),
    }


def _load_mesh_file(path: Path) -> trimesh.Trimesh | None:
    loaded = trimesh.load(path, force="scene")
    if isinstance(loaded, trimesh.Scene):
        meshes = [geom.copy() for geom in loaded.geometry.values() if isinstance(geom, trimesh.Trimesh)]
        if not meshes:
            return None
        return trimesh.util.concatenate(meshes)
    if isinstance(loaded, trimesh.Trimesh):
        return loaded.copy()
    return None


def _analyze_mesh_ref(path: Path) -> dict[str, Any] | None:
    mesh = _load_mesh_file(path)
    if mesh is None or len(mesh.faces) == 0:
        return None
    bounds = mesh.bounds
    extents = bounds[1] - bounds[0]
    return {
        "path": str(path),
        "vertex_count": int(len(mesh.vertices)),
        "triangle_count": int(len(mesh.faces)),
        "extents": [round(float(v), 6) for v in extents],
        "watertight": bool(mesh.is_watertight),
    }


def collect_shape_conditioning(asset: dict[str, Any], source_root: Path) -> dict[str, Any]:
    refs = asset.get("refs", {})
    consumed_refs: list[dict[str, Any]] = []
    image_refs: list[dict[str, Any]] = []
    material_refs: list[dict[str, Any]] = []
    mesh_refs: list[dict[str, Any]] = []

    for group in ("images", "materials"):
        for value in refs.get(group, []):
            resolved = _resolve_ref_path(source_root, value)
            entry = {
                "group": group,
                "value": value,
                "resolved": str(resolved) if resolved else None,
                "exists": bool(resolved),
            }
            if resolved is not None:
                analysis = _analyze_image_ref(resolved)
                entry["kind"] = analysis["kind"]
                if group == "materials" or analysis["kind"] == "material":
                    material_refs.append(analysis)
                else:
                    image_refs.append(analysis)
            consumed_refs.append(entry)

    for group in ("meshes", "assets"):
        for value in refs.get(group, []):
            resolved = _resolve_ref_path(source_root, value)
            entry = {
                "group": group,
                "value": value,
                "resolved": str(resolved) if resolved else None,
                "exists": bool(resolved),
            }
            if resolved is not None and resolved.suffix.lower() in SUPPORTED_MESH_EXTS:
                analysis = _analyze_mesh_ref(resolved)
                if analysis is not None:
                    mesh_refs.append(analysis)
                    entry["kind"] = "mesh"
            consumed_refs.append(entry)

    front = next((item for item in image_refs if item["kind"] == "front"), image_refs[0] if image_refs else None)
    side = next((item for item in image_refs if item["kind"] == "side"), image_refs[1] if len(image_refs) > 1 else front)
    material = material_refs[0] if material_refs else next((item for item in image_refs if item["kind"] == "material"), None)

    combined_palette: list[list[int]] = []
    for source in [material, front, side, *image_refs]:
        if not source:
            continue
        for color in source.get("palette", []):
            if color not in combined_palette:
                combined_palette.append(color)
        if len(combined_palette) >= 4:
            break

    total_declared = sum(len(refs.get(key, [])) for key in ("images", "materials", "meshes", "assets"))
    reference_strength = round(float((len(image_refs) + len(material_refs) + len(mesh_refs)) / max(1, total_declared)), 6)
    return {
        "source_root": str(source_root),
        "consumed_refs": consumed_refs,
        "image_refs": image_refs,
        "material_refs": material_refs,
        "mesh_refs": mesh_refs,
        "front_aspect": front["aspect"] if front else None,
        "side_aspect": side["aspect"] if side else None,
        "front_fill_ratio": front["fill_ratio"] if front else None,
        "side_fill_ratio": side["fill_ratio"] if side else None,
        "material_brightness": round(sum(material["mean_rgb"]) / (3 * 255.0), 6) if material else None,
        "palette": combined_palette,
        "reference_strength": reference_strength,
    }


def run_shape_backend(
    backend_id: str,
    asset: dict[str, Any],
    *,
    source_root: Path,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    work_dir: Path,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if backend_id != "lathe.shape.intent_mesh_handoff_v1":
        raise ValueError(f"Unsupported runnable shape backend '{backend_id}'")

    asset_graph = build_asset_graph(asset)
    mode = asset.get("build", {}).get("shape", {}).get("mode", "generate")
    shape_cfg = (runtime_config or {}).get("shape", {})
    explicit_provider = str(shape_cfg.get("provider", "auto") or "auto") not in {"", "auto", "None", "null"}
    scaffold_result = compile_scaffold_candidates(
        asset_graph,
        seed=seed,
        candidates_count=candidates_count,
        conditioning=conditioning,
        mode=mode,
    )
    if asset_graph.authoring.get("self_reliant_target") and mode in {"generate", "assemble", "adapt"} and not explicit_provider:
        provider_result = {
            "provider_report": {
                "selected_provider_id": "lathe.provider.shape.reference_conditioned_v1",
                "selected_provider_version": "1.0.0",
                "actual_provider_id": "lathe.provider.shape.reference_conditioned_v1",
                "actual_provider_version": "1.0.0",
                "selected_via": "self_reliant_native_only",
                "strict": False,
                "learned": False,
                "status": "native_only",
                "probe": {"available": True, "provider_id": "lathe.provider.shape.reference_conditioned_v1", "details": {}},
                "config": {},
                "fallback_reason": "V0.9 self-reliant compiler policy removes asset-generation AI from the critical path for this asset family.",
            },
            "runtime_candidates": None,
        }
    else:
        provider_result = maybe_run_shape_provider(
            asset,
            source_root=source_root,
            seed=seed,
            candidates_count=candidates_count,
            conditioning=conditioning,
            work_dir=work_dir,
            runtime_config=runtime_config,
        )
    conformance_result = fit_provider_proposals(asset_graph, scaffold_result, provider_result)
    provider_result["runtime_candidates"] = conformance_result["runtime_candidates"]
    provider_result["asset_graph"] = scaffold_result["asset_graph"].to_dict()
    provider_result["shape_ir"] = scaffold_result["report"]["shape_irs"]
    provider_result["scaffold_report"] = {
        **scaffold_result["report"],
        "signature": scaffold_result["shape_irs"][0].signature if scaffold_result["shape_irs"] else {},
        "blueprint_id": scaffold_result["report"].get("blueprint_id"),
        "primitives_used": scaffold_result["report"].get("primitives_used", []),
        "shape_assessment": scaffold_result["report"].get("shape_assessment", {}),
    }
    provider_result["conformance_report"] = conformance_result["report"]
    return provider_result


def _root_name(parts: list[str]) -> str:
    body_names = [name for name in parts if any(token in name for token in ("body", "hull", "core", "base"))]
    return body_names[0] if body_names else parts[0]


def _conditioned_part_colors(parts: list[str], conditioning: dict[str, Any]) -> dict[str, tuple[int, int, int]]:
    palette = conditioning.get("palette", [])
    brightness = conditioning.get("material_brightness")
    out: dict[str, tuple[int, int, int]] = {}
    palette_index = 0
    for part in parts:
        lname = part.lower()
        if any(token in lname for token in ("glass", "camera", "sensor", "gimbal")):
            out[part] = (214, 148, 72)
            continue
        if any(token in lname for token in ("rotor", "fan", "prop")):
            out[part] = (72, 76, 84)
            continue
        if palette:
            rgb = palette[min(palette_index, len(palette) - 1)]
            palette_index += 1
            color = [int(v) for v in rgb]
            if brightness is not None and brightness < 0.45:
                color = [max(45, int(v * 0.9)) for v in color]
            out[part] = tuple(color)
            continue
        out[part] = _make_color(part)
    return out


def _concat_named_meshes(named_meshes: list[tuple[str, trimesh.Trimesh]], part_colors: dict[str, tuple[int, int, int]]) -> dict[str, Any]:
    meshes: list[trimesh.Trimesh] = []
    face_parts: list[str] = []
    for part_name, mesh in named_meshes:
        meshes.append(mesh)
        face_parts.extend([part_name] * int(len(mesh.faces)))
    combined = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    return {
        "mesh": combined,
        "face_parts": face_parts,
        "part_colors": part_colors,
        "units": "cm",
    }


def _conditioned_body_extents(asset: dict[str, Any], conditioning: dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    scale_cm = _characteristic_scale_cm(asset)
    front_aspect = float(conditioning.get("front_aspect") or 1.55)
    side_aspect = float(conditioning.get("side_aspect") or 1.75)
    fill = float(conditioning.get("front_fill_ratio") or conditioning.get("side_fill_ratio") or 0.58)
    style = [str(item).lower() for item in asset.get("intent", {}).get("style", [])]
    slim_bias = 0.04 if any(token in style for token in ("premium", "near-future")) else 0.0
    width = scale_cm * _clamp(0.22 + 0.12 * front_aspect - slim_bias + float(rng.uniform(-0.02, 0.02)), 0.22, 0.56)
    height = scale_cm * _clamp(0.11 + 0.14 / max(0.8, front_aspect) + 0.03 * (1.0 - fill) + float(rng.uniform(-0.015, 0.015)), 0.10, 0.28)
    depth = scale_cm * _clamp(0.28 + 0.12 * side_aspect - slim_bias + float(rng.uniform(-0.03, 0.03)), 0.28, 0.82)
    return np.array([width, height, depth], dtype=float)


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


def _normalize_mesh_to_scale(mesh: trimesh.Trimesh, target_extent_cm: float) -> trimesh.Trimesh:
    mesh = mesh.copy()
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    bounds = mesh.bounds
    center = (bounds[0] + bounds[1]) / 2.0
    mesh.apply_translation(-center)
    extents = mesh.extents
    max_extent = max(1e-6, float(max(extents)))
    mesh.apply_scale(float(target_extent_cm) / max_extent)
    return mesh


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
