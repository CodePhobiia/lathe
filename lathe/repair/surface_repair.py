from __future__ import annotations

from typing import Any


def build_surface_repair_ir(backend_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "lathe.surface_repair_ir.v1",
        "preferred_scope": "zone_local",
        "allowed_repairs": [
            "reauthor_zone_basecolor",
            "reauthor_zone_wear_mask",
            "reauthor_zone_decal_mask",
            "rederive_zone_roughness",
            "rederive_zone_normal_detail",
            "reassemble_atlas",
            "increase_padding",
            "repair_seam_bleed",
            "repair_zone_coherence",
            "fallback_zone_deterministic",
        ],
        "codex_imagegen_available": bool(backend_report.get("codex_imagegen_ran")),
    }
