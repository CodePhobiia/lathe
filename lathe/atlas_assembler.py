from __future__ import annotations

from typing import Any


def build_atlas_assembly_ir(
    surface_cfg: dict[str, Any], control_pack: dict[str, Any], outputs: dict[str, Any]
) -> dict[str, Any]:
    return {
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
