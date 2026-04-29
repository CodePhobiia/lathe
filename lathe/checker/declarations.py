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
        check_surface_v12_refs(
            checker, family.get("surface", {}), f"family.{family['name']}.surface", family["name"]
        )
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

    _check_scenes(checker)


def _check_scene_id_prefix(
    checker: Any,
    *,
    scene_name: str,
    collection: str,
    item_name: str,
    prefix: str,
    code: str,
) -> None:
    if item_name.startswith(prefix):
        return
    checker.diagnostics.append(
        diag(
            code,
            "invalid_scene_local_id",
            "error",
            "typecheck",
            f"Scene '{scene_name}' {collection} id '{item_name}' must start with '{prefix}'",
            path=f"scene.{scene_name}.{collection}.{item_name}",
        )
    )


def _scene_local_ids(scene: dict[str, Any]) -> set[str]:
    ids = {scene["name"]}
    for collection in (
        "regions",
        "objects",
        "relationships",
        "cameras",
        "lights",
        "curiosity_anchors",
        "hidden_state",
    ):
        ids.update(item["name"] for item in scene.get(collection, []))
    return ids


def _scene_region_ids(scene: dict[str, Any]) -> set[str]:
    return {item["name"] for item in scene.get("regions", [])}


def _known_style_pack_ids(checker: Any) -> set[str]:
    from ..scene.style import builtin_style_pack_ids

    return {*checker.resolver.style_pack_map, *builtin_style_pack_ids()}


def _check_scene_style_pack_reference(checker: Any, scene: dict[str, Any], style: dict[str, Any]) -> None:
    values = style.get("values", {})
    if "style_pack" not in values:
        return
    target = values["style_pack"]
    if target == "" or target is None or not isinstance(target, str):
        checker.diagnostics.append(
            diag(
                "L5414",
                "invalid_scene_style_pack_reference_type",
                "error",
                "typecheck",
                f"Scene '{scene['name']}' style '{style['name']}' field 'style_pack' must be an identifier",
                path=f"scene.{scene['name']}.styles.{style['name']}.style_pack",
            )
        )
        return
    if target in _known_style_pack_ids(checker):
        return
    checker.diagnostics.append(
        diag(
            "L5413",
            "unknown_scene_style_pack_reference",
            "error",
            "resolve",
            f"Scene '{scene['name']}' style '{style['name']}' references unknown style_pack '{target}'",
            path=f"scene.{scene['name']}.styles.{style['name']}.style_pack",
        )
    )


def _check_scene_duplicate_child_names(checker: Any, scene: dict[str, Any]) -> None:
    seen: set[str] = set()
    for collection in (
        "styles",
        "regions",
        "objects",
        "relationships",
        "cameras",
        "lights",
        "curiosity_anchors",
        "hidden_state",
        "exports",
    ):
        for item in scene.get(collection, []):
            name = item["name"]
            if name in seen:
                checker.diagnostics.append(
                    diag(
                        "L5401",
                        "duplicate_scene_local_id",
                        "error",
                        "resolve",
                        f"Scene '{scene['name']}' contains duplicate local id '{name}'",
                        path=f"scene.{scene['name']}.{collection}.{name}",
                    )
                )
            seen.add(name)


def _check_scene_reference(
    checker: Any,
    *,
    scene: dict[str, Any],
    collection: str,
    item: dict[str, Any],
    field: str,
    valid_ids: set[str],
    code: str,
) -> None:
    values = item.get("values", {})
    if field not in values:
        return
    target = values[field]
    if target == "" or target is None:
        return
    if not isinstance(target, str):
        checker.diagnostics.append(
            diag(
                "L5412",
                "invalid_scene_reference_type",
                "error",
                "typecheck",
                f"Scene '{scene['name']}' {collection} '{item['name']}' field '{field}' must be an identifier",
                path=f"scene.{scene['name']}.{collection}.{item['name']}.{field}",
            )
        )
        return
    if target in valid_ids:
        return
    checker.diagnostics.append(
        diag(
            code,
            "unknown_scene_reference",
            "error",
            "resolve",
            f"Scene '{scene['name']}' {collection} '{item['name']}' references unknown id '{target}'",
            path=f"scene.{scene['name']}.{collection}.{item['name']}.{field}",
        )
    )


def _check_scenes(checker: Any) -> None:
    for scene in checker.program.get("scenes", []):
        if not scene["name"]:
            continue
        if not isinstance(scene.get("version"), int) or scene["version"] < 1:
            checker.diagnostics.append(
                diag(
                    "L5402",
                    "invalid_scene_version",
                    "error",
                    "typecheck",
                    f"Scene '{scene['name']}' version must be a positive integer",
                    path=f"scene.{scene['name']}.version",
                )
            )
        _check_scene_duplicate_child_names(checker, scene)
        valid_ids = _scene_local_ids(scene)
        region_ids = _scene_region_ids(scene)
        for style in scene.get("styles", []):
            _check_scene_style_pack_reference(checker, scene, style)
        for region in scene.get("regions", []):
            _check_scene_id_prefix(
                checker,
                scene_name=scene["name"],
                collection="regions",
                item_name=region["name"],
                prefix="region_",
                code="L5403",
            )
        for obj in scene.get("objects", []):
            _check_scene_id_prefix(
                checker,
                scene_name=scene["name"],
                collection="objects",
                item_name=obj["name"],
                prefix="obj_",
                code="L5404",
            )
            _check_scene_reference(
                checker,
                scene=scene,
                collection="objects",
                item=obj,
                field="region",
                valid_ids=region_ids,
                code="L5405",
            )
        for relationship in scene.get("relationships", []):
            _check_scene_id_prefix(
                checker,
                scene_name=scene["name"],
                collection="relationships",
                item_name=relationship["name"],
                prefix="rel_",
                code="L5406",
            )
            _check_scene_reference(
                checker,
                scene=scene,
                collection="relationships",
                item=relationship,
                field="from",
                valid_ids=valid_ids,
                code="L5407",
            )
            _check_scene_reference(
                checker,
                scene=scene,
                collection="relationships",
                item=relationship,
                field="to",
                valid_ids=valid_ids,
                code="L5407",
            )
        for camera in scene.get("cameras", []):
            _check_scene_id_prefix(
                checker,
                scene_name=scene["name"],
                collection="cameras",
                item_name=camera["name"],
                prefix="camera_",
                code="L5408",
            )
            _check_scene_reference(
                checker,
                scene=scene,
                collection="cameras",
                item=camera,
                field="target",
                valid_ids=valid_ids,
                code="L5409",
            )
        for light in scene.get("lights", []):
            _check_scene_id_prefix(
                checker,
                scene_name=scene["name"],
                collection="lights",
                item_name=light["name"],
                prefix="light_",
                code="L5410",
            )
            _check_scene_reference(
                checker,
                scene=scene,
                collection="lights",
                item=light,
                field="target",
                valid_ids=valid_ids,
                code="L5411",
            )
        for anchor in scene.get("curiosity_anchors", []):
            _check_scene_id_prefix(
                checker,
                scene_name=scene["name"],
                collection="curiosity_anchors",
                item_name=anchor["name"],
                prefix="curiosity_",
                code="L5415",
            )
            _check_scene_reference(
                checker,
                scene=scene,
                collection="curiosity_anchors",
                item=anchor,
                field="attached_to",
                valid_ids=valid_ids,
                code="L5416",
            )
        for hidden in scene.get("hidden_state", []):
            _check_scene_id_prefix(
                checker,
                scene_name=scene["name"],
                collection="hidden_state",
                item_name=hidden["name"],
                prefix="hidden_",
                code="L5417",
            )
            _check_scene_reference(
                checker,
                scene=scene,
                collection="hidden_state",
                item=hidden,
                field="attached_to",
                valid_ids=valid_ids,
                code="L5418",
            )

    for palette in checker.program.get("palettes", []):
        material_names = list(
            palette.get("values", {}).get("materials", []) or palette.get("values", {}).get("slots", [])
        )
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
