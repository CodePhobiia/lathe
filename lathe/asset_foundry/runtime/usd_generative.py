"""USD generative procedural path.

Per northstar §11 Phase 5. OpenUSD's procedural prim API
(``UsdProcAPI`` / ``GenerativeProcedural``) lets DCCs invoke a
procedural recipe at evaluation time rather than baking the mesh.

This module declares typed spec records the external USD writer
consumes. We do not depend on USD C++ here; the writer emits
USDA / USDZ via an external tool when present.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

USD_GENERATIVE_VERSION = "lathe.asset_foundry.usd_generative_v1"


@dataclass(frozen=True)
class UsdPrimSpec:
    """One USD prim in the generative stage."""

    prim_path: str
    """Absolute USD path: ``/World/Asset/Crystal``."""

    prim_type: str
    """``Xform`` | ``Mesh`` | ``GenerativeProcedural`` | ``Scope``."""

    attributes: Mapping[str, Any] = field(default_factory=dict)
    """USD attributes (``primvars:displayColor``, ``points``,
    ``faceVertexIndices``, ``faceVertexCounts``, ...). Values are
    typed by USD; we keep them as Python primitives."""

    metadata: Mapping[str, Any] = field(default_factory=dict)
    """USD metadata (``customData``, ``kind``, ``purpose``)."""

    children: tuple["UsdPrimSpec", ...] = ()


@dataclass(frozen=True)
class UsdStageSpec:
    """Full USD stage descriptor."""

    stage_path: str
    """Path the stage will write to (``.usda`` or ``.usdz``)."""

    default_prim_path: str
    """Stage default prim (typically ``/World``)."""

    up_axis: str = "Y"
    """``Y`` (USD default) | ``Z`` (Blender/Unreal native)."""

    meters_per_unit: float = 0.01
    """0.01 = cm units (Foundry default)."""

    root_prim: UsdPrimSpec = field(
        default_factory=lambda: UsdPrimSpec(
            prim_path="/World",
            prim_type="Xform",
        )
    )
    procedural_recipe_uri: str | None = None
    """When set, the stage's default prim is a GenerativeProcedural
    that invokes this recipe path at evaluation time."""


def build_usd_generative_stage(
    *,
    asset_id: str,
    stage_path: str,
    procedural_recipe_uri: str | None = None,
    semantic_index: Mapping[str, Any] | None = None,
) -> UsdStageSpec:
    """Build a USD stage spec from Foundry semantic data.

    When ``procedural_recipe_uri`` is provided, the stage is
    generative — engines that support USD generative prims will
    invoke the recipe at evaluation time rather than baking the mesh.
    """
    children: list[UsdPrimSpec] = []
    if semantic_index is not None:
        parts = semantic_index.get("semantic_parts", []) if isinstance(semantic_index, Mapping) else []
        for part_name in parts:
            children.append(
                UsdPrimSpec(
                    prim_path=f"/World/Asset/{part_name}",
                    prim_type="Mesh",
                    metadata={"kind": "subcomponent", "lathe_part_id": part_name},
                )
            )
    if procedural_recipe_uri:
        root = UsdPrimSpec(
            prim_path="/World/Asset",
            prim_type="GenerativeProcedural",
            attributes={
                "lathe:recipe_uri": procedural_recipe_uri,
                "lathe:asset_id": asset_id,
            },
            metadata={"kind": "component"},
            children=tuple(children),
        )
    else:
        root = UsdPrimSpec(
            prim_path="/World/Asset",
            prim_type="Xform",
            metadata={"kind": "component", "lathe_asset_id": asset_id},
            children=tuple(children),
        )
    world_prim = UsdPrimSpec(
        prim_path="/World",
        prim_type="Xform",
        children=(root,),
    )
    return UsdStageSpec(
        stage_path=stage_path,
        default_prim_path="/World",
        up_axis="Z",
        meters_per_unit=0.01,
        root_prim=world_prim,
        procedural_recipe_uri=procedural_recipe_uri,
    )


__all__ = [
    "USD_GENERATIVE_VERSION",
    "UsdPrimSpec",
    "UsdStageSpec",
    "build_usd_generative_stage",
]
