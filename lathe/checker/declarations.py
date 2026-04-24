"""Declaration-scope checks.

Validates ``profile``, ``contract``, ``critic``, ``library``,
``kit`` and other top-level declarations outside of ``asset``.
"""

from __future__ import annotations

from typing import Any

from .surface import check_surface_v12_refs
from .utils import V13_1_EVIDENCE_CLASSES, diag


def check_new_declarations(checker: Any) -> None:
    """Check new declarations.

    Args:
        checker: checker argument.
    """
    for family in checker.program.get("families", []):
        for component_name in family.get("assembly", {}).get("components", []):
            if component_name not in checker.resolver.component_map:
                checker.diagnostics.append(
                    diag(
                        "L5201",
                        "unknown_component_reference",
                        "error",
                        "resolve",
                        f"Family '{family['name']}' references unknown component '{component_name}'",
                        path=f"family.{family['name']}.assembly.components",
                    )
                )
        palette_name = family.get("surface", {}).get("palette")
        if palette_name and palette_name not in checker.resolver.palette_map:
            checker.diagnostics.append(
                diag(
                    "L5202",
                    "unknown_palette_reference",
                    "error",
                    "resolve",
                    f"Family '{family['name']}' references unknown palette '{palette_name}'",
                    path=f"family.{family['name']}.surface.palette",
                )
            )
        surface_program_name = family.get("surface", {}).get("program")
        if surface_program_name and surface_program_name not in checker.resolver.surface_program_map:
            checker.diagnostics.append(
                diag(
                    "L5209",
                    "unknown_surface_program_reference",
                    "error",
                    "resolve",
                    f"Family '{family['name']}' references unknown surface_program '{surface_program_name}'",
                    path=f"family.{family['name']}.surface.program",
                )
            )
        check_surface_v12_refs(checker, family.get("surface", {}), f"family.{family['name']}.surface", family["name"])
        for pattern_name in family.get("surface", {}).get("patterns", []):
            if pattern_name not in checker.resolver.pattern_map:
                checker.diagnostics.append(
                    diag(
                        "L5210",
                        "unknown_pattern_reference",
                        "error",
                        "resolve",
                        f"Family '{family['name']}' references unknown pattern '{pattern_name}'",
                        path=f"family.{family['name']}.surface.patterns",
                    )
                )
        repair_policy_name = family.get("repair_policy", {}).get("use")
        if repair_policy_name and repair_policy_name not in checker.resolver.repair_policy_map:
            checker.diagnostics.append(
                diag(
                    "L5203",
                    "unknown_repair_policy_reference",
                    "error",
                    "resolve",
                    f"Family '{family['name']}' references unknown repair policy '{repair_policy_name}'",
                    path=f"family.{family['name']}.repair_policy.use",
                )
            )

    for palette in checker.program.get("palettes", []):
        material_names = list(palette.get("values", {}).get("materials", []) or palette.get("values", {}).get("slots", []))
        for material_name in material_names:
            if material_name not in checker.resolver.material_map:
                checker.diagnostics.append(
                    diag(
                        "L5204",
                        "unknown_material_reference",
                        "error",
                        "resolve",
                        f"Palette '{palette['name']}' references unknown material '{material_name}'",
                        path=f"palette.{palette['name']}.values",
                    )
                )

    for profile in checker.program.get("execution_profiles", []):
        values = profile.get("values", {})
        engine = values.get("engine")
        mode = values.get("mode")
        inspection_policy_name = values.get("inspection_policy")
        if engine and engine != "blender":
            checker.diagnostics.append(
                diag(
                    "L5230",
                    "unsupported_execution_engine",
                    "error",
                    "typecheck",
                    f"Execution profile '{profile['name']}' uses unsupported engine '{engine}'",
                    path=f"execution_profile.{profile['name']}.engine",
                )
            )
        if mode and mode not in {"background_cli", "python_module"}:
            checker.diagnostics.append(
                diag(
                    "L5231",
                    "unsupported_execution_mode",
                    "error",
                    "typecheck",
                    f"Execution profile '{profile['name']}' uses unsupported mode '{mode}'",
                    path=f"execution_profile.{profile['name']}.mode",
                )
            )
        if inspection_policy_name and inspection_policy_name not in checker.resolver.inspection_policy_map:
            checker.diagnostics.append(
                diag(
                    "L5238",
                    "unknown_inspection_policy_reference",
                    "error",
                    "resolve",
                    f"Execution profile '{profile['name']}' references unknown inspection policy '{inspection_policy_name}'",
                    path=f"execution_profile.{profile['name']}.inspection_policy",
                )
            )

    for binding in checker.program.get("library_bindings", []):
        target = str(binding.get("values", {}).get("target", "") or "")
        if target and target != "blender_assets":
            checker.diagnostics.append(
                diag(
                    "L5232",
                    "unsupported_library_binding_target",
                    "error",
                    "typecheck",
                    f"Library binding '{binding['name']}' uses unsupported target '{target}'",
                    path=f"library_binding.{binding['name']}.target",
                )
            )

    for policy in checker.program.get("inspection_policies", []):
        values = policy.get("values", {})
        required = values.get("require", values.get("required_evidence", values.get("evidence", [])))
        if isinstance(required, str):
            required = [required]
        for evidence_class in required or []:
            if evidence_class not in V13_1_EVIDENCE_CLASSES:
                checker.diagnostics.append(
                    diag(
                        "L5239",
                        "unknown_inspection_evidence_class",
                        "error",
                        "typecheck",
                        f"Inspection policy '{policy['name']}' requires unknown evidence class '{evidence_class}'",
                        path=f"inspection_policy.{policy['name']}.require",
                    )
                )
