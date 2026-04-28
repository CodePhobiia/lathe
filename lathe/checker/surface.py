"""Surface-authoring checks.

Validates V1.2 surface blocks: ``surface_backend``, ``surface_policy``,
``decal_library``, ``mask_program`` and ``trim_sheet`` wiring and
cross-references.
"""

from __future__ import annotations

from typing import Any

from .utils import diag


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
