"""MaterialX stdlib lowering + colorspace map sidecars.

Per northstar §10 Lane D priority tasks #9 + #10. MaterialX is the
emerging cross-DCC material standard. The Foundry lowers its
style-pack + material-zone manifest into a MaterialX nodegraph
descriptor that engines/DCCs (Blender, Houdini, Unreal MaterialX
input) can ingest.

The implementation emits a typed dict ready for MaterialX 1.39
serialization. We do not depend on the MaterialX C++ library —
when MaterialX is available the external builder serializes; when
not, the JSON form remains useful as a portable material spec.

Colorspace sidecars (#10) map each texture file to its colorspace
tag (``srgb_texture``, ``lin_rec709``, ``raw``) so engine importers
do not double-correct PBR maps.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

MATERIALX_LOWERING_VERSION = "lathe.asset_foundry.materialx_lowering_v1"


@dataclass(frozen=True)
class MaterialxNode:
    """One MaterialX nodedef instance."""

    name: str
    nodedef: str
    """e.g. ``ND_image_color3``, ``ND_standard_surface_surfaceshader``,
    ``ND_mix_color3``."""

    inputs: Mapping[str, Any]
    """Input bindings (constants or upstream-node references)."""

    output: str = "out"


@dataclass(frozen=True)
class MaterialxNodeGraph:
    """A standalone MaterialX nodegraph (a reusable subnet)."""

    name: str
    nodes: tuple[MaterialxNode, ...]
    output_node_name: str
    output_kind: str = "color3"


@dataclass(frozen=True)
class MaterialxMaterial:
    """A surface material binding."""

    name: str
    surface_nodedef: str = "ND_standard_surface_surfaceshader"
    inputs: Mapping[str, Any] = field(default_factory=dict)
    """Surface inputs — constants or references to nodegraphs."""


@dataclass(frozen=True)
class MaterialxDocument:
    """The full MaterialX descriptor."""

    version: str
    materialx_version: str = "1.39"
    nodegraphs: tuple[MaterialxNodeGraph, ...] = ()
    materials: tuple[MaterialxMaterial, ...] = ()
    color_space: str = "lin_rec709"
    """Working color space for non-texture inputs."""


@dataclass(frozen=True)
class TextureMapSidecar:
    """Sidecar describing a texture's colorspace + intended use."""

    texture_path: str
    colorspace: str
    """``srgb_texture`` | ``lin_rec709`` | ``raw``."""

    role: str
    """``basecolor`` | ``normal`` | ``orm`` | ``ao`` | ``roughness`` |
    ``metalness`` | ``emissive`` | ``height`` | ``mask``."""

    wrap_u: str = "repeat"
    wrap_v: str = "repeat"
    filter_type: str = "linear"
    mip_count: int | None = None


# Material-class -> standard_surface input mapping. Used by the
# lowering function to bind style-pack material classes to PBR
# parameter defaults.
_MATERIAL_DEFAULTS: Mapping[str, Mapping[str, Any]] = {
    "wall_plaster": {
        "base_color": "#ead7b4",
        "roughness": 0.72,
        "metalness": 0.0,
    },
    "roof_thatch_golden": {
        "base_color": "#d99933",
        "roughness": 0.85,
        "metalness": 0.0,
    },
    "wood_warm_brown": {
        "base_color": "#6b4226",
        "roughness": 0.55,
        "metalness": 0.0,
    },
    "wood_reddish_brown": {
        "base_color": "#8a3a20",
        "roughness": 0.55,
        "metalness": 0.0,
    },
    "window_emissive_warm": {
        "base_color": "#f5b03d",
        "roughness": 0.3,
        "metalness": 0.0,
        "emission_color": "#f5b03d",
        "emission": 1.5,
    },
    "lantern_emissive_warm": {
        "base_color": "#ffba5a",
        "roughness": 0.3,
        "metalness": 0.0,
        "emission_color": "#ffba5a",
        "emission": 1.5,
    },
    "crystal_violet_emissive": {
        "base_color": "#7b3fd2",
        "roughness": 0.2,
        "metalness": 0.0,
        "emission_color": "#a070ff",
        "emission": 0.8,
    },
    "crystal_magenta": {
        "base_color": "#c43fa5",
        "roughness": 0.25,
        "metalness": 0.0,
    },
    "crystal_cyan_dim": {
        "base_color": "#3fd2c4",
        "roughness": 0.3,
        "metalness": 0.0,
    },
    "tree_teal": {
        "base_color": "#226c5a",
        "roughness": 0.75,
        "metalness": 0.0,
    },
    "tree_deep_green": {
        "base_color": "#1e4a36",
        "roughness": 0.75,
        "metalness": 0.0,
    },
    "tree_olive": {
        "base_color": "#92a02b",
        "roughness": 0.7,
        "metalness": 0.0,
    },
    "stone_warm_gray": {
        "base_color": "#a89a86",
        "roughness": 0.7,
        "metalness": 0.0,
    },
    "cliff_purple": {
        "base_color": "#5e3a8a",
        "roughness": 0.75,
        "metalness": 0.0,
    },
    "cliff_lavender": {
        "base_color": "#9f80c2",
        "roughness": 0.75,
        "metalness": 0.0,
    },
    "grass_emerald": {
        "base_color": "#3fa55a",
        "roughness": 0.85,
        "metalness": 0.0,
    },
    "water_cyan": {
        "base_color": "#4ac2d2",
        "roughness": 0.05,
        "metalness": 0.0,
    },
    "metal_warm": {
        "base_color": "#8c7445",
        "roughness": 0.4,
        "metalness": 0.9,
    },
    "metal_bare": {
        "base_color": "#a8a8a8",
        "roughness": 0.45,
        "metalness": 1.0,
    },
    "rope_fiber": {
        "base_color": "#9a7a55",
        "roughness": 0.95,
        "metalness": 0.0,
    },
    "path_dirt_compacted": {
        "base_color": "#7a6048",
        "roughness": 0.9,
        "metalness": 0.0,
    },
    "painted_steel": {
        "base_color": "#4f5668",
        "roughness": 0.62,
        "metalness": 0.0,
    },
    "rubber_trim": {
        "base_color": "#1a1a1a",
        "roughness": 0.92,
        "metalness": 0.0,
    },
}


def lower_material_zone_manifest_to_materialx(
    material_zone_manifest: Mapping[str, str],
    *,
    asset_id: str,
) -> MaterialxDocument:
    """Lower the Foundry's material_zone_manifest into a MaterialxDocument.

    Each zone -> material_class pairing produces one MaterialxMaterial
    instance with PBR defaults pulled from ``_MATERIAL_DEFAULTS``.
    Materials whose class is unknown emit a ``status: "unsupported"``
    placeholder rather than fabricating values.
    """
    materials: list[MaterialxMaterial] = []
    for zone_prefix, material_class in material_zone_manifest.items():
        defaults = _MATERIAL_DEFAULTS.get(material_class)
        material_name = f"{asset_id}.{zone_prefix}.{material_class}".replace(".", "_")
        if defaults is None:
            materials.append(
                MaterialxMaterial(
                    name=material_name,
                    surface_nodedef="ND_standard_surface_surfaceshader",
                    inputs={
                        "base_color": "#888888",
                        "roughness": 0.5,
                        "metalness": 0.0,
                        "_lathe_status": "unsupported_material_class",
                        "_lathe_material_class": material_class,
                    },
                )
            )
            continue
        materials.append(
            MaterialxMaterial(
                name=material_name,
                surface_nodedef="ND_standard_surface_surfaceshader",
                inputs={**defaults, "_lathe_material_class": material_class},
            )
        )
    return MaterialxDocument(
        version=MATERIALX_LOWERING_VERSION,
        materialx_version="1.39",
        nodegraphs=(),
        materials=tuple(materials),
        color_space="lin_rec709",
    )


def build_colorspace_sidecars(
    texture_paths_by_role: Mapping[str, str],
) -> tuple[TextureMapSidecar, ...]:
    """Build TextureMapSidecar records keyed by role.

    Role -> colorspace defaults:
      - basecolor / emissive               -> srgb_texture
      - normal / orm / roughness / metalness / ao / height / mask -> lin_rec709 / raw
    """
    colorspace_for_role = {
        "basecolor": "srgb_texture",
        "emissive": "srgb_texture",
        "normal": "lin_rec709",
        "orm": "lin_rec709",
        "roughness": "lin_rec709",
        "metalness": "lin_rec709",
        "ao": "lin_rec709",
        "height": "raw",
        "mask": "raw",
        "curvature": "raw",
        "wear_mask": "raw",
        "material_layer_mask": "raw",
    }
    out: list[TextureMapSidecar] = []
    for role, path in texture_paths_by_role.items():
        cs = colorspace_for_role.get(role, "lin_rec709")
        out.append(
            TextureMapSidecar(
                texture_path=path,
                colorspace=cs,
                role=role,
            )
        )
    return tuple(out)


def document_to_dict(doc: MaterialxDocument) -> dict[str, Any]:
    """JSON-serialize a MaterialxDocument."""
    return {
        "version": doc.version,
        "materialx_version": doc.materialx_version,
        "color_space": doc.color_space,
        "nodegraphs": [
            {
                "name": g.name,
                "output_node_name": g.output_node_name,
                "output_kind": g.output_kind,
                "nodes": [
                    {
                        "name": n.name,
                        "nodedef": n.nodedef,
                        "output": n.output,
                        "inputs": dict(n.inputs),
                    }
                    for n in g.nodes
                ],
            }
            for g in doc.nodegraphs
        ],
        "materials": [
            {
                "name": m.name,
                "surface_nodedef": m.surface_nodedef,
                "inputs": dict(m.inputs),
            }
            for m in doc.materials
        ],
    }


def sidecars_to_dict(sidecars: Sequence[TextureMapSidecar]) -> dict[str, Any]:
    """JSON-serialize a list of texture sidecars."""
    return {
        "version": MATERIALX_LOWERING_VERSION,
        "sidecars": [
            {
                "texture_path": s.texture_path,
                "colorspace": s.colorspace,
                "role": s.role,
                "wrap_u": s.wrap_u,
                "wrap_v": s.wrap_v,
                "filter_type": s.filter_type,
                "mip_count": s.mip_count,
            }
            for s in sidecars
        ],
    }


__all__ = [
    "MATERIALX_LOWERING_VERSION",
    "MaterialxDocument",
    "MaterialxMaterial",
    "MaterialxNode",
    "MaterialxNodeGraph",
    "TextureMapSidecar",
    "build_colorspace_sidecars",
    "document_to_dict",
    "lower_material_zone_manifest_to_materialx",
    "sidecars_to_dict",
]
