"""Surface-authoring checks.

Validates V1.2 surface blocks: ``surface_backend``, ``surface_policy``,
``decal_library``, ``mask_program``, ``trim_sheet`` wiring and
cross-references; and the V0.1 §6.3 PBR material-primitive constraints
(metalness valid, F0 / albedo / roughness within typed bounds).
"""

from __future__ import annotations

from typing import Any

from .utils import diag


_METALNESS_TOLERANCE = 0.05
_DIELECTRIC_F0_RANGE = (0.02, 0.08)
_METAL_F0_RANGE = (0.50, 1.00)
_ALBEDO_DIELECTRIC_RANGE = (30, 243)
_ROUGHNESS_RANGE = (0.0, 1.0)


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coerce_rgb(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return (int(value[0]), int(value[1]), int(value[2]))
    except (TypeError, ValueError):
        return None


def check_pbr_material_primitives(checker: Any) -> None:
    """Validate PBR constraints on every ``material`` declaration.

    Rejects materials whose ``metallic`` lies outside the {0, 1} dielectric
    /metal endpoints by more than ``_METALNESS_TOLERANCE``, whose albedo
    is outside the typed dielectric/metal ranges, and whose roughness
    lies outside [0, 1].
    """
    for material in checker.program.get("materials", []):
        name = material.get("name", "")
        values = material.get("values", {}) if isinstance(material, dict) else {}
        metallic = _coerce_float(values.get("metallic"))
        roughness = _coerce_float(values.get("roughness"))
        albedo = _coerce_rgb(values.get("basecolor"))
        f0_target = _coerce_float(values.get("f0_target"))
        pbr_class = str(values.get("pbr_class") or "").strip().lower()
        if metallic is None:
            continue  # legacy materials without explicit PBR fields skip the check
        is_metal_endpoint = abs(metallic - 1.0) <= _METALNESS_TOLERANCE
        is_dielectric_endpoint = abs(metallic - 0.0) <= _METALNESS_TOLERANCE
        if not (is_metal_endpoint or is_dielectric_endpoint):
            checker.diagnostics.append(
                diag(
                    "L5260",
                    "invalid_pbr_metalness",
                    "error",
                    "typecheck",
                    f"Material '{name}' metallic={metallic:.3f} must be ~0.0 (dielectric) or ~1.0 (metal); mixed values are not PBR-valid.",
                    path=f"material.{name}.metallic",
                )
            )
        if roughness is not None and not (_ROUGHNESS_RANGE[0] <= roughness <= _ROUGHNESS_RANGE[1]):
            checker.diagnostics.append(
                diag(
                    "L5261",
                    "invalid_pbr_roughness",
                    "error",
                    "typecheck",
                    f"Material '{name}' roughness={roughness:.3f} must lie in [0, 1].",
                    path=f"material.{name}.roughness",
                )
            )
        if albedo is not None and is_dielectric_endpoint:
            lo, hi = _ALBEDO_DIELECTRIC_RANGE
            if not all(lo <= channel <= hi for channel in albedo):
                checker.diagnostics.append(
                    diag(
                        "L5262",
                        "invalid_pbr_dielectric_albedo",
                        "warning",
                        "typecheck",
                        f"Material '{name}' dielectric basecolor {list(albedo)} is outside the recommended [{lo}, {hi}] sRGB range; PBR-valid dielectrics rarely sit at these extremes.",
                        path=f"material.{name}.basecolor",
                    )
                )
        if f0_target is not None and pbr_class:
            target_range = _DIELECTRIC_F0_RANGE if pbr_class == "dielectric" else _METAL_F0_RANGE
            if not (target_range[0] <= f0_target <= target_range[1]):
                checker.diagnostics.append(
                    diag(
                        "L5263",
                        "invalid_pbr_f0_target",
                        "warning",
                        "typecheck",
                        f"Material '{name}' pbr_class='{pbr_class}' f0_target={f0_target:.3f} is outside the typed range {list(target_range)}.",
                        path=f"material.{name}.f0_target",
                    )
                )


def check_surface_v12_refs(checker: Any, surface: dict[str, Any], path_prefix: str, owner_name: str) -> None:
    """Check surface v12 refs.

    Args:
        checker: checker argument.
        surface: surface argument.
        path_prefix: path_prefix argument.
        owner_name: owner_name argument.
    """
    checks = [
        ("policy", checker.resolver.surface_policy_map, "surface_policy", "L5221"),
        ("backend", checker.resolver.surface_backend_map, "surface_backend", "L5222"),
    ]
    authoring_backend = (
        surface.get("authoring", {}).get("backend") if isinstance(surface.get("authoring"), dict) else ""
    )
    if authoring_backend and authoring_backend in checker.resolver.surface_backend_map:
        surface = {**surface, "backend": authoring_backend}
    for field, namespace, label, code in checks:
        name = surface.get(field)
        if (
            name
            and name not in namespace
            and not (field == "backend" and str(name).startswith("lathe.surface."))
        ):
            checker.diagnostics.append(
                diag(
                    code,
                    f"unknown_{label}_reference",
                    "error",
                    "resolve",
                    f"'{owner_name}' references unknown {label} '{name}'",
                    asset=owner_name,
                    path=f"{path_prefix}.{field}",
                )
            )
    list_checks = [
        ("decal_libraries", checker.resolver.decal_library_map, "decal_library", "L5223"),
        ("mask_programs", checker.resolver.mask_program_map, "mask_program", "L5224"),
        ("trim_sheets", checker.resolver.trim_sheet_map, "trim_sheet", "L5225"),
    ]
    for field, namespace, label, code in list_checks:
        for name in surface.get(field, []):
            if name not in namespace:
                checker.diagnostics.append(
                    diag(
                        code,
                        f"unknown_{label}_reference",
                        "error",
                        "resolve",
                        f"'{owner_name}' references unknown {label} '{name}'",
                        asset=owner_name,
                        path=f"{path_prefix}.{field}",
                    )
                )
