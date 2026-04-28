from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

CODEX_IMAGEGEN_BACKEND_ID = "lathe.surface.codex_imagegen_v1"
DETERMINISTIC_PBR_BACKEND_ID = "lathe.surface.deterministic_pbr_v1"


def resolve_surface_backend_report(
    source_surface: dict[str, Any], surface_cfg: dict[str, Any], hero_mode: bool
) -> dict[str, Any]:
    authoring = dict(source_surface.get("authoring", {}))
    requested = (
        authoring.get("backend")
        or source_surface.get("backend")
        or surface_cfg.get("authoring_backend")
        or surface_cfg.get("backend")
        or DETERMINISTIC_PBR_BACKEND_ID
    )
    backend_id = str(requested)
    aliases = {
        "deterministic_pbr": DETERMINISTIC_PBR_BACKEND_ID,
        "deterministic_pbr_v1": DETERMINISTIC_PBR_BACKEND_ID,
        "codex_imagegen": CODEX_IMAGEGEN_BACKEND_ID,
        "codex_imagegen_v1": CODEX_IMAGEGEN_BACKEND_ID,
    }
    backend_id = aliases.get(backend_id, backend_id)
    codex_requested = backend_id == CODEX_IMAGEGEN_BACKEND_ID
    policy_values = dict(source_surface.get("resolved_surface_policy", {}).get("values", {}))
    unavailable_policy = str(policy_values.get("on_backend_unavailable", "fallback_deterministic"))
    return {
        "requested_backend": str(requested),
        "selected_backend_id": backend_id,
        "surface_backend_decl": source_surface.get("resolved_surface_backend", {}),
        "surface_policy_decl": source_surface.get("resolved_surface_policy", {}),
        "authoring_mode": authoring.get(
            "mode",
            source_surface.get(
                "authoring_mode", "deterministic_only" if not codex_requested else "zone_first"
            ),
        ),
        "zone_first": bool(authoring.get("mode", "") == "zone_first" or codex_requested),
        "codex_imagegen_requested": codex_requested,
        "codex_imagegen_ran": False,
        "backend_unavailable_policy": unavailable_policy,
        "fallback_backend_id": DETERMINISTIC_PBR_BACKEND_ID
        if codex_requested and unavailable_policy != "fail"
        else "",
        "fallback_reason": "Codex ImageGen bridge is policy-modeled but not invoked by the reference runtime"
        if codex_requested
        else "",
        "hero_surface": hero_mode,
    }


def codex_imagegen_mode(runtime_config: dict[str, Any] | None) -> str:
    cfg = (
        (runtime_config or {}).get("surface", {}).get("codex_imagegen", {})
        if isinstance(runtime_config, dict)
        else {}
    )
    mode = str(cfg.get("mode", "fallback_deterministic"))
    aliases = {
        "auto": "fallback_deterministic",
        "fallback": "fallback_deterministic",
        "off": "fallback_deterministic",
        "emit": "emit_requests",
        "requests": "emit_requests",
        "consume": "consume_outputs",
    }
    return aliases.get(mode, mode)


def _cfg_path(runtime_config: dict[str, Any] | None, key: str, default: str) -> str:
    cfg = (
        (runtime_config or {}).get("surface", {}).get("codex_imagegen", {})
        if isinstance(runtime_config, dict)
        else {}
    )
    return str(cfg.get(key, default))


def _cfg_build_path(out_dir: Path, runtime_config: dict[str, Any] | None, key: str, default: str) -> Path:
    raw = _cfg_path(runtime_config, key, default)
    configured = Path(raw)
    if configured.is_absolute():
        raise ValueError(f"codex_imagegen.{key} must be relative to the build directory")
    base = out_dir.resolve()
    candidate = (base / configured).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError(f"codex_imagegen.{key} must stay inside the build directory")
    return candidate


def _rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("/", "\\")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zone_prompt(
    asset: dict[str, Any], source_surface: dict[str, Any], zone: dict[str, Any], generated_map: str
) -> str:
    authoring = (
        source_surface.get("authoring", {}) if isinstance(source_surface.get("authoring"), dict) else {}
    )
    return "\n".join(
        [
            "Use case: stylized-concept",
            "Asset type: Lathe hard-surface asset texture map",
            f"Primary request: Generate a {generated_map} texture for the material zone '{zone['part']}' on asset '{asset['name']}'.",
            f"Subject: {asset.get('intent', {}).get('role', asset['name'])}",
            "Style/medium: production-ready PBR texture authoring, zone-local, UV-atlas friendly",
            f"Materials/textures: material '{zone['material']}', surface profile '{zone.get('surface_profile', 'neutral_panel')}', base color {zone.get('basecolor')}, roughness {zone.get('roughness')}",
            "Color palette: respect the declared material and avoid changing semantic material identity",
            "Constraints: output a square texture tile; no text unless decal libraries require it; preserve clear material separation; avoid seams and border artifacts",
            f"Lathe authoring mode: {authoring.get('mode', 'zone_first')}",
            f"Surface program: {source_surface.get('program', '')}",
            f"Policy: {source_surface.get('policy', '')}",
        ]
    )


def emit_codex_imagegen_requests(
    *,
    asset: dict[str, Any],
    out_dir: Path,
    runtime_config: dict[str, Any] | None,
    surface_cfg: dict[str, Any],
    source_surface: dict[str, Any],
    material_zones: list[dict[str, Any]],
    control_pack: dict[str, Any],
) -> dict[str, Any]:
    request_dir = _cfg_build_path(out_dir, runtime_config, "request_dir", "imagegen_requests")
    output_dir = _cfg_build_path(out_dir, runtime_config, "output_dir", "imagegen_outputs")
    request_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    authoring = (
        source_surface.get("authoring", {}) if isinstance(source_surface.get("authoring"), dict) else {}
    )
    generated_maps = list(authoring.get("generate", [])) or ["basecolor"]
    supported_maps = [
        item
        for item in generated_maps
        if item in {"basecolor", "detail_overlay", "decal_mask", "wear_mask", "trim_overlay", "emissive_art"}
    ]
    requests: list[dict[str, Any]] = []
    for zone in material_zones:
        for generated_map in supported_maps:
            filename = f"{zone['part']}_{generated_map}.png"
            request = {
                "schema": "lathe.codex_imagegen_request.v1",
                "asset": asset["name"],
                "zone": zone["part"],
                "material": zone["material"],
                "map": generated_map,
                "tool": "$imagegen",
                "mode": "built_in",
                "prompt": _zone_prompt(asset, source_surface, zone, generated_map),
                "control_pack": control_pack,
                "expected_output": _rel(out_dir, output_dir / filename),
                "integration_note": "Codex should generate this image with the built-in image_gen tool, then move/copy the selected PNG to expected_output.",
            }
            request_path = request_dir / f"{zone['part']}_{generated_map}.json"
            request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
            requests.append({**request, "request_uri": _rel(out_dir, request_path)})
    manifest = {
        "schema": "lathe.codex_imagegen_requests.v1",
        "asset": asset["name"],
        "status": "pending",
        "request_count": len(requests),
        "request_dir": _rel(out_dir, request_dir),
        "output_dir": _rel(out_dir, output_dir),
        "requests": [
            {
                "zone": item["zone"],
                "material": item["material"],
                "map": item["map"],
                "request_uri": item["request_uri"],
                "expected_output": item["expected_output"],
            }
            for item in requests
        ],
    }
    manifest_path = request_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {**manifest, "manifest_uri": _rel(out_dir, manifest_path)}


def _color_mask(id_source: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    return np.all(np.abs(id_source.astype(np.int16) - np.asarray(color, dtype=np.int16)) <= 2, axis=2)


def consume_codex_imagegen_outputs(
    *,
    out_dir: Path,
    runtime_config: dict[str, Any] | None,
    id_map: Image.Image,
    basecolor: Image.Image,
    material_zones: list[dict[str, Any]],
) -> tuple[Image.Image, dict[str, Any]]:
    output_dir = _cfg_build_path(out_dir, runtime_config, "output_dir", "imagegen_outputs")
    id_source = np.asarray(id_map.convert("RGB"), dtype=np.uint8)
    out = np.asarray(basecolor.convert("RGB"), dtype=np.float64)
    consumed: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for zone in material_zones:
        path = output_dir / f"{zone['part']}_basecolor.png"
        if not path.exists():
            missing.append({"zone": zone["part"], "map": "basecolor", "expected_output": _rel(out_dir, path)})
            continue
        with Image.open(path) as image:
            generated = np.asarray(image.convert("RGB").resize(basecolor.size), dtype=np.float64)
        mask = _color_mask(id_source, tuple(int(value) for value in zone["basecolor"]))
        if np.any(mask):
            out[mask] = generated[mask]
        consumed.append(
            {"zone": zone["part"], "map": "basecolor", "uri": _rel(out_dir, path), "sha256": _sha256(path)}
        )
    report = {
        "schema": "lathe.codex_imagegen_outputs.v1",
        "status": "complete" if consumed and not missing else "partial" if consumed else "missing",
        "output_dir": _rel(out_dir, output_dir),
        "consumed": consumed,
        "missing": missing,
    }
    manifest_path = output_dir / "manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["manifest_uri"] = _rel(out_dir, manifest_path)
    return Image.fromarray(np.clip(out, 0.0, 255.0).astype(np.uint8), mode="RGB"), report
