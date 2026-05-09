from __future__ import annotations

from typing import Any


def build_atlas_assembly_ir(
    surface_cfg: dict[str, Any],
    control_pack: dict[str, Any],
    outputs: dict[str, Any],
    *,
    uv_organization: dict[str, Any] | None = None,
    chart_manifest: list[dict[str, Any]] | None = None,
    material_id_layout: dict[str, Any] | None = None,
    generated_surface_charts: dict[str, Any] | None = None,
    surface_story_placement_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ir = {
        "schema": "lathe.atlas_assembly_ir.v1",
        "mode": "zone_first",
        "control_pack": control_pack.get("manifest_uri"),
        "compose": {
            "maps": list(surface_cfg.get("maps", [])),
            "padding": surface_cfg.get("padding", {"type": "unit", "value": 8, "unit": "px"}),
            "mip_safe": True,
        },
        "outputs": {name: entry["uri"] for name, entry in outputs.items()},
    }
    if uv_organization:
        ir["uv_organization"] = dict(uv_organization)
    if chart_manifest:
        ir["chart_manifest"] = list(chart_manifest)
    if material_id_layout:
        ir["material_id_layout"] = dict(material_id_layout)
    if generated_surface_charts:
        ir["generated_surface_charts"] = dict(generated_surface_charts)
    if control_pack.get("generated_surface_chart_maps"):
        ir["generated_surface_chart_maps"] = dict(control_pack.get("generated_surface_chart_maps") or {})
    if control_pack.get("generated_surface_chart_atlas"):
        ir["generated_surface_chart_atlas"] = dict(control_pack.get("generated_surface_chart_atlas") or {})
    if surface_story_placement_plan:
        ir["surface_story_placement_plan"] = dict(surface_story_placement_plan)
    return ir
