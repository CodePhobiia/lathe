"""``lathe plan`` subcommand: emit the effective build plan."""

from __future__ import annotations

from pathlib import Path

from ._common import _dump


def run_plan(args) -> None:
    """Run plan.

    Args:
        args: args argument.
    """
    from ..parser import parse_file
    from ..planner import build_plan

    program = parse_file(Path(args.file))
    _dump(build_plan(program, args.name, execution_profile_override=args.execution_profile))


def run_surface_plan(args) -> None:
    """Run surface plan.

    Args:
        args: args argument.
    """
    from ..parser import parse_file
    from ..planner import build_plan
    from ..resolver import materialize_asset

    program = parse_file(Path(args.file))
    asset = materialize_asset(program, args.name)
    plan = build_plan(program, args.name)
    surface = asset.get("surface", {})
    build_surface = asset.get("build", {}).get("surface", {})
    authoring = surface.get("authoring", {}) if isinstance(surface.get("authoring"), dict) else {}
    policy_values = surface.get("resolved_surface_policy", {}).get("values", {})
    _dump(
        {
            "asset": args.name,
            "backend": authoring.get("backend") or surface.get("backend") or build_surface.get("authoring_backend") or build_surface.get("backend"),
            "resolved_backend_id": surface.get("resolved_surface_backend", {}).get("values", {}).get("id", ""),
            "policy": surface.get("policy", ""),
            "resolved_policy": plan["v1_2_surface"].get("resolved_surface_policy", ""),
            "zones": list(surface.get("material_zones", [])),
            "maps_to_generate": list(authoring.get("generate", [])),
            "maps_to_derive": list(authoring.get("derive", [])),
            "required_maps": list(policy_values.get("maps", build_surface.get("maps", []))),
            "control_images": ["uv_layout", "padded_island_mask", "material_zone_mask", "ao", "curvature", "normal_reference", "preview"],
            "validation_gates": [
                "surface_authoring_quality",
                "material_zone_coherence",
                "seam_continuity",
                "padding_safety",
                "normal_richness",
                "roughness_variation",
                "texture_entropy",
                "decal_coherence",
                "trim_coherence",
                "mip_safety",
                "bake_alignment_quality",
                "surface_render_plausibility",
            ],
            "v1_2_surface": plan["v1_2_surface"],
        }
    )


def run_fit(args) -> None:
    """Run fit.

    Args:
        args: args argument.
    """
    from ..parser import parse_file
    from ..resolver import materialize_asset

    program = parse_file(Path(args.file))
    asset = materialize_asset(program, args.name)
    _dump(
        {
            "asset": args.name,
            "mode": asset.get("build", {}).get("shape", {}).get("mode"),
            "refs": asset.get("refs", {}),
            "fit": asset.get("fit", {}),
            "transfer": asset.get("transfer", {}),
            "reuse": asset.get("reuse", {}),
            "constraints": asset.get("constraints", {}),
            "assembly": asset.get("assembly", {}),
        }
    )
