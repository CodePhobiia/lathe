"""Phase 6 deterministic grammar-lowering recipes.

Lowers a family grammar's construction requirements into ShapeIR v2
operations + synthesized semantic-construction-graph nodes. The private
recipe registry consumes Phases 3 (family grammar), 4 (construction
graph), and 5 (ShapeIR v2 + v1 adapter) without expanding public
``.lth`` syntax.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 7.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 6.
Per-requirement reference: ``docs/asset-quality/grammar-lowering-v1.md``.

Design summary
--------------

Phase 6 is **internal IR + recipe + adapter wiring** plus live
family-grammar evidence. It does not
touch ``.lth`` syntax, ``lathe.shape.intent_mesh_handoff_v1``, the
public schema, or the v1 shape bundle. The recipe is a pure function
that takes a design brief, a parts list, and the current
construction-graph nodes and returns a frozen :class:`RecipeResult`
with a :class:`ShapeProgram` and a tuple of synthesized graph nodes.

The recipe's synthesized graph nodes live under
``runtime["grammar_lowering"]["synthesized_graph_nodes"]``. The live
validator pipeline runs grammar lowering before family grammar, and
``family_grammar`` merges those synthesized nodes into its read-only
evidence view so coverage reflects the recipe without mutating
``runtime["construction_graph"]["nodes"]``.

The validator never produces blocking diagnostics. v2-adapter
diagnostics for ops that have no v1 equivalent are surfaced under the
nested ``v1_lowering`` payload — they are evidence for forward phases
(Phase 7's high-poly producer turns those into v1-supported records),
not validator-pipeline blockers.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately before ``family_grammar`` and before
``quality_diagnostics``, both with ``stage_dependencies=[]`` and
``weight=0.0``. Topological order plus FIFO tie-break preserves the
registration-order placement.

Output additively appears under the top-level ``grammar_lowering`` key
of the validate-stage report (the 20th top-level key, on top of the 19
that Phases 0 through 5 publish).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .construction_graph import NODE_TYPES, _classify_part
from .shape_ir_v2 import (
    BOOLEAN_OPS,
    EDGE_OPS,
    INTEGRATION_OPS,
    REPETITION_OPS,
    SHAPE_IR_V2_VERSION,
    SOP_OPS,
    SOLID_OPS,
    WEAR_OPS,
    ShapeOp,
    ShapeProgram,
    lower_to_v1,
)


GRAMMAR_LOWERING_VERSION = "grammar_lowering_v1"


# Canonical industrial_crate body dimensions taken from the upgrade spec
# Section 7.3 (`primary_form = crate_squat_box(width: 92cm, height: 58cm,
# depth: 64cm)`).
_INDUSTRIAL_CRATE_BODY_WIDTH_CM: float = 92.0
_INDUSTRIAL_CRATE_BODY_HEIGHT_CM: float = 58.0
_INDUSTRIAL_CRATE_BODY_DEPTH_CM: float = 64.0

_MECHANICAL_DOOR_WIDTH_CM: float = 96.0
_MECHANICAL_DOOR_HEIGHT_CM: float = 144.0
_MECHANICAL_DOOR_DEPTH_CM: float = 10.0

_SERVICE_CABINET_WIDTH_CM: float = 46.0
_SERVICE_CABINET_HEIGHT_CM: float = 72.0
_SERVICE_CABINET_DEPTH_CM: float = 18.0

_WEAPON_LENGTH_CM: float = 96.0
_WEAPON_BODY_WIDTH_CM: float = 12.0
_WEAPON_BODY_DEPTH_CM: float = 5.0

_VEHICLE_WIDTH_CM: float = 86.0
_VEHICLE_HEIGHT_CM: float = 36.0
_VEHICLE_DEPTH_CM: float = 132.0

_FURNITURE_WIDTH_CM: float = 84.0
_FURNITURE_HEIGHT_CM: float = 54.0
_FURNITURE_DEPTH_CM: float = 44.0

_NATURAL_MASS_WIDTH_CM: float = 92.0
_NATURAL_MASS_HEIGHT_CM: float = 38.0
_NATURAL_MASS_DEPTH_CM: float = 72.0

_ARCH_WIDTH_CM: float = 128.0
_ARCH_HEIGHT_CM: float = 84.0
_ARCH_DEPTH_CM: float = 92.0

_LIGHTING_HEIGHT_CM: float = 92.0
_LIGHTING_WIDTH_CM: float = 34.0
_LIGHTING_DEPTH_CM: float = 24.0

_MACHINE_WIDTH_CM: float = 72.0
_MACHINE_HEIGHT_CM: float = 74.0
_MACHINE_DEPTH_CM: float = 42.0

_PORTAL_WIDTH_CM: float = 92.0
_PORTAL_HEIGHT_CM: float = 124.0
_PORTAL_DEPTH_CM: float = 28.0

_TOOL_LENGTH_CM: float = 82.0
_TOOL_WIDTH_CM: float = 18.0
_TOOL_DEPTH_CM: float = 8.0

_KIT_TILE_WIDTH_CM: float = 64.0
_KIT_TILE_HEIGHT_CM: float = 16.0
_KIT_TILE_DEPTH_CM: float = 64.0

_CHARACTER_HEIGHT_CM: float = 76.0
_CHARACTER_WIDTH_CM: float = 30.0
_CHARACTER_DEPTH_CM: float = 18.0

_SET_DRESSING_WIDTH_CM: float = 42.0
_SET_DRESSING_HEIGHT_CM: float = 50.0
_SET_DRESSING_DEPTH_CM: float = 32.0

_SURFACE_SAMPLE_WIDTH_CM: float = 72.0
_SURFACE_SAMPLE_HEIGHT_CM: float = 4.0
_SURFACE_SAMPLE_DEPTH_CM: float = 48.0

_TERRAIN_VARIANT_WIDTH_CM: float = 96.0
_TERRAIN_VARIANT_HEIGHT_CM: float = 18.0
_TERRAIN_VARIANT_DEPTH_CM: float = 72.0

_EFFECT_WIDTH_CM: float = 84.0
_EFFECT_HEIGHT_CM: float = 36.0
_EFFECT_DEPTH_CM: float = 52.0

_SETTLEMENT_WIDTH_CM: float = 160.0
_SETTLEMENT_HEIGHT_CM: float = 12.0
_SETTLEMENT_DEPTH_CM: float = 128.0

_GAMEPLAY_WIDTH_CM: float = 38.0
_GAMEPLAY_HEIGHT_CM: float = 44.0
_GAMEPLAY_DEPTH_CM: float = 30.0

_ENCOUNTER_WIDTH_CM: float = 128.0
_ENCOUNTER_HEIGHT_CM: float = 10.0
_ENCOUNTER_DEPTH_CM: float = 104.0

_INVENTORY_WIDTH_CM: float = 32.0
_INVENTORY_HEIGHT_CM: float = 28.0
_INVENTORY_DEPTH_CM: float = 24.0

_RIG_PROXY_WIDTH_CM: float = 48.0
_RIG_PROXY_HEIGHT_CM: float = 72.0
_RIG_PROXY_DEPTH_CM: float = 28.0

_STATEFUL_WIDTH_CM: float = 54.0
_STATEFUL_HEIGHT_CM: float = 42.0
_STATEFUL_DEPTH_CM: float = 36.0

_CLOTH_WIDTH_CM: float = 64.0
_CLOTH_HEIGHT_CM: float = 54.0
_CLOTH_DEPTH_CM: float = 8.0

_DOMAIN_KIT_WIDTH_CM: float = 120.0
_DOMAIN_KIT_HEIGHT_CM: float = 20.0
_DOMAIN_KIT_DEPTH_CM: float = 80.0

_WORLD_SYSTEM_WIDTH_CM: float = 150.0
_WORLD_SYSTEM_HEIGHT_CM: float = 16.0
_WORLD_SYSTEM_DEPTH_CM: float = 120.0

_SIM_SYSTEM_WIDTH_CM: float = 112.0
_SIM_SYSTEM_HEIGHT_CM: float = 24.0
_SIM_SYSTEM_DEPTH_CM: float = 88.0

_MULTI_ASSET_WIDTH_CM: float = 126.0
_MULTI_ASSET_HEIGHT_CM: float = 18.0
_MULTI_ASSET_DEPTH_CM: float = 84.0

_RUNTIME_WIDTH_CM: float = 84.0
_RUNTIME_HEIGHT_CM: float = 44.0
_RUNTIME_DEPTH_CM: float = 36.0

_ENGINE_RUNTIME_WIDTH_CM: float = 128.0
_ENGINE_RUNTIME_HEIGHT_CM: float = 42.0
_ENGINE_RUNTIME_DEPTH_CM: float = 86.0

_PREFAB_BINDING_WIDTH_CM: float = 118.0
_PREFAB_BINDING_HEIGHT_CM: float = 34.0
_PREFAB_BINDING_DEPTH_CM: float = 78.0

_SCENE_AUTHORING_WIDTH_CM: float = 136.0
_SCENE_AUTHORING_HEIGHT_CM: float = 38.0
_SCENE_AUTHORING_DEPTH_CM: float = 96.0

_BEHAVIOR_LOGIC_WIDTH_CM: float = 124.0
_BEHAVIOR_LOGIC_HEIGHT_CM: float = 32.0
_BEHAVIOR_LOGIC_DEPTH_CM: float = 82.0

_WORLD_STREAMING_WIDTH_CM: float = 148.0
_WORLD_STREAMING_HEIGHT_CM: float = 30.0
_WORLD_STREAMING_DEPTH_CM: float = 112.0

_SAVE_STATE_WIDTH_CM: float = 112.0
_SAVE_STATE_HEIGHT_CM: float = 34.0
_SAVE_STATE_DEPTH_CM: float = 78.0

_QUEST_DIALOGUE_WIDTH_CM: float = 126.0
_QUEST_DIALOGUE_HEIGHT_CM: float = 34.0
_QUEST_DIALOGUE_DEPTH_CM: float = 86.0

_CAMERA_CINEMATIC_WIDTH_CM: float = 128.0
_CAMERA_CINEMATIC_HEIGHT_CM: float = 42.0
_CAMERA_CINEMATIC_DEPTH_CM: float = 88.0

_AUDIO_CUE_WIDTH_CM: float = 118.0
_AUDIO_CUE_HEIGHT_CM: float = 30.0
_AUDIO_CUE_DEPTH_CM: float = 78.0

_LOCALIZATION_TEXT_WIDTH_CM: float = 132.0
_LOCALIZATION_TEXT_HEIGHT_CM: float = 28.0
_LOCALIZATION_TEXT_DEPTH_CM: float = 88.0

_ACCESSIBILITY_UX_WIDTH_CM: float = 120.0
_ACCESSIBILITY_UX_HEIGHT_CM: float = 28.0
_ACCESSIBILITY_UX_DEPTH_CM: float = 82.0

_ECONOMY_TUNING_WIDTH_CM: float = 124.0
_ECONOMY_TUNING_HEIGHT_CM: float = 30.0
_ECONOMY_TUNING_DEPTH_CM: float = 84.0

_MULTIPLAYER_REPLICATION_WIDTH_CM: float = 132.0
_MULTIPLAYER_REPLICATION_HEIGHT_CM: float = 34.0
_MULTIPLAYER_REPLICATION_DEPTH_CM: float = 92.0

_CROSS_DOMAIN_WIDTH_CM: float = 132.0
_CROSS_DOMAIN_HEIGHT_CM: float = 22.0
_CROSS_DOMAIN_DEPTH_CM: float = 90.0

_STYLE_STACK_WIDTH_CM: float = 100.0
_STYLE_STACK_HEIGHT_CM: float = 18.0
_STYLE_STACK_DEPTH_CM: float = 70.0

_TYPED_KERNEL_WIDTH_CM: float = 118.0
_TYPED_KERNEL_HEIGHT_CM: float = 26.0
_TYPED_KERNEL_DEPTH_CM: float = 76.0

_ATTR_SURFACE_WIDTH_CM: float = 112.0
_ATTR_SURFACE_HEIGHT_CM: float = 20.0
_ATTR_SURFACE_DEPTH_CM: float = 78.0

_VEG_LIBRARY_WIDTH_CM: float = 120.0
_VEG_LIBRARY_HEIGHT_CM: float = 42.0
_VEG_LIBRARY_DEPTH_CM: float = 82.0

_TERRAIN_SYSTEM_WIDTH_CM: float = 144.0
_TERRAIN_SYSTEM_HEIGHT_CM: float = 18.0
_TERRAIN_SYSTEM_DEPTH_CM: float = 108.0

_WFC_SOLVER_WIDTH_CM: float = 128.0
_WFC_SOLVER_HEIGHT_CM: float = 20.0
_WFC_SOLVER_DEPTH_CM: float = 92.0

_CGA_GRAMMAR_WIDTH_CM: float = 116.0
_CGA_GRAMMAR_HEIGHT_CM: float = 58.0
_CGA_GRAMMAR_DEPTH_CM: float = 74.0

_VOLUME_EFFECT_WIDTH_CM: float = 108.0
_VOLUME_EFFECT_HEIGHT_CM: float = 56.0
_VOLUME_EFFECT_DEPTH_CM: float = 72.0

_SCATTER_SYSTEM_WIDTH_CM: float = 126.0
_SCATTER_SYSTEM_HEIGHT_CM: float = 24.0
_SCATTER_SYSTEM_DEPTH_CM: float = 88.0

_FREP_SDF_WIDTH_CM: float = 104.0
_FREP_SDF_HEIGHT_CM: float = 54.0
_FREP_SDF_DEPTH_CM: float = 76.0

_SUBDIV_FINISH_WIDTH_CM: float = 116.0
_SUBDIV_FINISH_HEIGHT_CM: float = 34.0
_SUBDIV_FINISH_DEPTH_CM: float = 78.0

_HUMANOID_ANATOMY_WIDTH_CM: float = 72.0
_HUMANOID_ANATOMY_HEIGHT_CM: float = 172.0
_HUMANOID_ANATOMY_DEPTH_CM: float = 36.0

_FACE_SDF_WIDTH_CM: float = 96.0
_FACE_SDF_HEIGHT_CM: float = 42.0
_FACE_SDF_DEPTH_CM: float = 62.0

_RIG_COMPONENT_WIDTH_CM: float = 112.0
_RIG_COMPONENT_HEIGHT_CM: float = 74.0
_RIG_COMPONENT_DEPTH_CM: float = 64.0

_MORPH_DB_WIDTH_CM: float = 118.0
_MORPH_DB_HEIGHT_CM: float = 36.0
_MORPH_DB_DEPTH_CM: float = 72.0

_ANIM_BIND_WIDTH_CM: float = 124.0
_ANIM_BIND_HEIGHT_CM: float = 34.0
_ANIM_BIND_DEPTH_CM: float = 80.0

_RETARGET_PACK_WIDTH_CM: float = 118.0
_RETARGET_PACK_HEIGHT_CM: float = 58.0
_RETARGET_PACK_DEPTH_CM: float = 74.0

_EQUIPMENT_BIND_WIDTH_CM: float = 108.0
_EQUIPMENT_BIND_HEIGHT_CM: float = 66.0
_EQUIPMENT_BIND_DEPTH_CM: float = 72.0

_GAMEPLAY_CTRL_WIDTH_CM: float = 126.0
_GAMEPLAY_CTRL_HEIGHT_CM: float = 30.0
_GAMEPLAY_CTRL_DEPTH_CM: float = 86.0

_FACIAL_RIG_WIDTH_CM: float = 104.0
_FACIAL_RIG_HEIGHT_CM: float = 52.0
_FACIAL_RIG_DEPTH_CM: float = 62.0

_HAIR_PROGRAM_WIDTH_CM: float = 108.0
_HAIR_PROGRAM_HEIGHT_CM: float = 48.0
_HAIR_PROGRAM_DEPTH_CM: float = 78.0

_CLOTH_SIM_WIDTH_CM: float = 104.0
_CLOTH_SIM_HEIGHT_CM: float = 42.0
_CLOTH_SIM_DEPTH_CM: float = 66.0

_FLUID_FORWARD_WIDTH_CM: float = 112.0
_FLUID_FORWARD_HEIGHT_CM: float = 58.0
_FLUID_FORWARD_DEPTH_CM: float = 78.0

_CONSTRUCTION_KIT_WIDTH_CM: float = 126.0
_CONSTRUCTION_KIT_HEIGHT_CM: float = 46.0
_CONSTRUCTION_KIT_DEPTH_CM: float = 84.0

_CREATURE_APPENDAGE_WIDTH_CM: float = 112.0
_CREATURE_APPENDAGE_HEIGHT_CM: float = 66.0
_CREATURE_APPENDAGE_DEPTH_CM: float = 72.0

_BODY_PART_LIBRARY_WIDTH_CM: float = 108.0
_BODY_PART_LIBRARY_HEIGHT_CM: float = 74.0
_BODY_PART_LIBRARY_DEPTH_CM: float = 70.0

_MATERIAL_PRIMITIVE_WIDTH_CM: float = 118.0
_MATERIAL_PRIMITIVE_HEIGHT_CM: float = 34.0
_MATERIAL_PRIMITIVE_DEPTH_CM: float = 82.0


@dataclass(frozen=True)
class RecipeResult:
    """Result of lowering one family grammar into v2 ops + graph nodes.

    ``shape_program`` is the :class:`ShapeProgram` (Phase 5) the recipe
    emitted — its ops carry stable ``purpose`` strings keyed off the
    triggering grammar requirement. ``synthesized_graph_nodes`` is the
    tuple of graph-node dicts the family-grammar validator merges into
    its read-only evidence view.
    """

    family: str
    shape_program: ShapeProgram
    synthesized_graph_nodes: tuple[dict[str, Any], ...]


def _purpose(requirement: str, suffix: str) -> str:
    """Return the canonical ``purpose`` string for a recipe op.

    Format: ``<requirement>.<suffix>`` (e.g. ``"body_shell.primary_volume"``).
    The format is stable across phases so trace consumers can join op
    purpose to grammar requirement without re-keying.
    """
    return f"{requirement}.{suffix}"


def _node(
    node_id: str,
    node_type: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one synthesized construction-graph node dict.

    The dict shape mirrors :func:`lathe.asset_quality.construction_graph.evaluate_construction_graph`
    so a downstream phase can merge synthesized nodes into the live
    graph without translation. Most recipe nodes keep ``attributes``
    empty; source-authored nodes preserve their source path and value so
    downstream phases can distinguish authored hints from recipe output.
    """
    return {
        "node_id": node_id,
        "node_type": node_type,
        "attributes": dict(attributes) if attributes else {},
    }


def _source_op(
    op: str,
    target: str | None,
    parameters: dict[str, Any],
    purpose: str,
) -> dict[str, Any]:
    """Return a JSON-shaped nested ShapeOp source for source-aware SOPs."""
    return {
        "op": op,
        "target": target,
        "parameters": dict(parameters),
        "purpose": purpose,
    }


def _rect_profile(width_cm: float, height_cm: float) -> tuple[tuple[float, float], ...]:
    half_width = width_cm * 0.5
    half_height = height_cm * 0.5
    return (
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    )


def _body_box_source(purpose: str) -> dict[str, Any]:
    return _source_op(
        "solid.box",
        "body",
        {
            "width_cm": _INDUSTRIAL_CRATE_BODY_WIDTH_CM,
            "height_cm": _INDUSTRIAL_CRATE_BODY_HEIGHT_CM,
            "depth_cm": _INDUSTRIAL_CRATE_BODY_DEPTH_CM,
        },
        purpose,
    )


def _panel_source(
    *,
    target: str,
    width_cm: float,
    height_cm: float,
    thickness_cm: float,
    center: tuple[float, float, float],
    purpose: str,
) -> dict[str, Any]:
    return _source_op(
        "solid.panel",
        target,
        {
            "width_cm": width_cm,
            "height_cm": height_cm,
            "thickness_cm": thickness_cm,
            "center": center,
        },
        purpose,
    )


def _polybeveled_source(
    source: dict[str, Any],
    *,
    width_cm: float,
    segments: int,
    target: str,
    purpose: str,
) -> dict[str, Any]:
    return _source_op(
        "sop.polybevel",
        target,
        {
            "source": source,
            "width_cm": width_cm,
            "segments": segments,
        },
        purpose,
    )


def _crate_corner_points() -> tuple[tuple[float, float, float], ...]:
    x = _INDUSTRIAL_CRATE_BODY_WIDTH_CM * 0.5 - 3.0
    y = _INDUSTRIAL_CRATE_BODY_HEIGHT_CM * 0.5 - 3.0
    z = _INDUSTRIAL_CRATE_BODY_DEPTH_CM * 0.5 - 3.0
    return tuple(
        (sx * x, sy * y, sz * z)
        for sx in (-1.0, 1.0)
        for sy in (-1.0, 1.0)
        for sz in (-1.0, 1.0)
    )


def _rivet_profile() -> tuple[tuple[float, float], ...]:
    return (
        (0.0, -0.8),
        (1.4, -0.55),
        (1.8, 0.0),
        (1.4, 0.55),
        (0.0, 0.8),
    )


def _hinge_profile() -> tuple[tuple[float, float], ...]:
    return (
        (0.0, -3.0),
        (1.7, -2.8),
        (2.0, 0.0),
        (1.7, 2.8),
        (0.0, 3.0),
    )


def _capped_hinge_barrel_profile() -> tuple[tuple[float, float], ...]:
    return (
        (-3.0, 1.4),
        (-2.8, 2.0),
        (2.8, 2.0),
        (3.0, 1.4),
    )


def _weapon_blade_profile() -> tuple[tuple[float, float], ...]:
    return (
        (-_WEAPON_BODY_WIDTH_CM * 0.5, -2.4),
        (_WEAPON_BODY_WIDTH_CM * 0.5, -2.4),
        (_WEAPON_BODY_WIDTH_CM * 0.38, 1.8),
        (0.0, 4.6),
        (-_WEAPON_BODY_WIDTH_CM * 0.38, 1.8),
    )


def _wheel_points() -> tuple[tuple[float, float, float], ...]:
    x = _VEHICLE_WIDTH_CM * 0.5 - 8.0
    z = _VEHICLE_DEPTH_CM * 0.5 - 18.0
    return (
        (-x, -_VEHICLE_HEIGHT_CM * 0.35, -z),
        (x, -_VEHICLE_HEIGHT_CM * 0.35, -z),
        (-x, -_VEHICLE_HEIGHT_CM * 0.35, z),
        (x, -_VEHICLE_HEIGHT_CM * 0.35, z),
    )


def _furniture_leg_points() -> tuple[tuple[float, float, float], ...]:
    x = _FURNITURE_WIDTH_CM * 0.5 - 7.0
    z = _FURNITURE_DEPTH_CM * 0.5 - 7.0
    return ((-x, -24.0, -z), (x, -24.0, -z), (-x, -24.0, z), (x, -24.0, z))


def _leaf_profile() -> tuple[tuple[float, float], ...]:
    return (
        (0.0, -4.0),
        (5.0, -1.4),
        (6.2, 1.4),
        (0.0, 5.2),
        (-6.2, 1.4),
        (-5.0, -1.4),
    )


def _natural_scatter_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-32.0, 12.0, -20.0),
        (-12.0, 18.0, 18.0),
        (18.0, 14.0, -10.0),
        (34.0, 9.0, 22.0),
        (3.0, 20.0, 31.0),
    )


def _arch_column_points() -> tuple[tuple[float, float, float], ...]:
    x = _ARCH_WIDTH_CM * 0.5 - 8.0
    z = _ARCH_DEPTH_CM * 0.5 - 8.0
    return ((-x, 12.0, -z), (x, 12.0, -z), (-x, 12.0, z), (x, 12.0, z))


def _lighting_guard_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-14.0, _LIGHTING_HEIGHT_CM - 22.0, -1.0),
        (-7.0, _LIGHTING_HEIGHT_CM - 19.0, -1.0),
        (7.0, _LIGHTING_HEIGHT_CM - 19.0, -1.0),
        (14.0, _LIGHTING_HEIGHT_CM - 22.0, -1.0),
    )


def _console_button_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-20.0, 42.0, -22.5),
        (-10.0, 43.0, -22.5),
        (0.0, 43.5, -22.5),
        (10.0, 43.0, -22.5),
        (20.0, 42.0, -22.5),
    )


def _portal_node_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-_PORTAL_WIDTH_CM * 0.38, 28.0, -_PORTAL_DEPTH_CM * 0.5),
        (_PORTAL_WIDTH_CM * 0.38, 28.0, -_PORTAL_DEPTH_CM * 0.5),
        (-_PORTAL_WIDTH_CM * 0.32, 86.0, -_PORTAL_DEPTH_CM * 0.5),
        (_PORTAL_WIDTH_CM * 0.32, 86.0, -_PORTAL_DEPTH_CM * 0.5),
        (0.0, 112.0, -_PORTAL_DEPTH_CM * 0.5),
    )


def _tool_fastener_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-5.5, 0.0, -30.0),
        (5.5, 0.0, -30.0),
        (-5.5, 0.0, 0.0),
        (5.5, 0.0, 0.0),
        (-7.0, 0.0, 30.0),
        (7.0, 0.0, 30.0),
    )


def _kit_connector_points() -> tuple[tuple[float, float, float], ...]:
    x = _KIT_TILE_WIDTH_CM * 0.5 - 5.0
    z = _KIT_TILE_DEPTH_CM * 0.5 - 5.0
    return ((-x, 7.0, 0.0), (x, 7.0, 0.0), (0.0, 7.0, -z), (0.0, 7.0, z))


def _character_limb_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-_CHARACTER_WIDTH_CM * 0.42, 34.0, 0.0),
        (_CHARACTER_WIDTH_CM * 0.42, 34.0, 0.0),
        (-_CHARACTER_WIDTH_CM * 0.22, 8.0, 0.0),
        (_CHARACTER_WIDTH_CM * 0.22, 8.0, 0.0),
    )


def _set_dressing_scatter_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-18.0, 3.0, -13.0),
        (-7.0, 4.0, 15.0),
        (10.0, 3.5, -12.0),
        (19.0, 2.5, 9.0),
    )


def _surface_tick_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-30.0 + index * 10.0, 3.2, -22.5) for index in range(7))


def _terrain_growth_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-34.0, 12.0, -22.0),
        (-12.0, 14.0, -10.0),
        (8.0, 13.0, 18.0),
        (28.0, 11.0, -2.0),
        (36.0, 10.0, 24.0),
    )


def _effect_particle_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-28.0, 18.0, -18.0),
        (-16.0, 24.0, -6.0),
        (0.0, 28.0, 0.0),
        (18.0, 22.0, 8.0),
        (30.0, 16.0, 18.0),
    )


def _settlement_plot_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-54.0, 8.0, -40.0),
        (-18.0, 8.5, -36.0),
        (24.0, 8.0, -42.0),
        (52.0, 8.5, -12.0),
        (-46.0, 8.0, 18.0),
        (-6.0, 8.5, 28.0),
        (34.0, 8.0, 32.0),
    )


def _gameplay_port_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-_GAMEPLAY_WIDTH_CM * 0.36, 18.0, -_GAMEPLAY_DEPTH_CM * 0.52),
        (_GAMEPLAY_WIDTH_CM * 0.36, 18.0, -_GAMEPLAY_DEPTH_CM * 0.52),
        (-_GAMEPLAY_WIDTH_CM * 0.34, 30.0, -_GAMEPLAY_DEPTH_CM * 0.52),
        (_GAMEPLAY_WIDTH_CM * 0.34, 30.0, -_GAMEPLAY_DEPTH_CM * 0.52),
    )


def _encounter_spawn_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-_ENCOUNTER_WIDTH_CM * 0.42, 8.0, -_ENCOUNTER_DEPTH_CM * 0.36),
        (_ENCOUNTER_WIDTH_CM * 0.42, 8.0, -_ENCOUNTER_DEPTH_CM * 0.34),
        (-_ENCOUNTER_WIDTH_CM * 0.36, 8.0, _ENCOUNTER_DEPTH_CM * 0.38),
        (_ENCOUNTER_WIDTH_CM * 0.34, 8.0, _ENCOUNTER_DEPTH_CM * 0.36),
    )


def _inventory_slot_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-10.0, 20.0, -_INVENTORY_DEPTH_CM * 0.52),
        (0.0, 20.0, -_INVENTORY_DEPTH_CM * 0.52),
        (10.0, 20.0, -_INVENTORY_DEPTH_CM * 0.52),
        (-10.0, 12.0, -_INVENTORY_DEPTH_CM * 0.52),
        (0.0, 12.0, -_INVENTORY_DEPTH_CM * 0.52),
        (10.0, 12.0, -_INVENTORY_DEPTH_CM * 0.52),
    )


def _rig_joint_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (0.0, 58.0, 0.0),
        (-16.0, 44.0, 0.0),
        (16.0, 44.0, 0.0),
        (-10.0, 24.0, 0.0),
        (10.0, 24.0, 0.0),
        (0.0, 8.0, 0.0),
    )


def _rig_socket_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-_RIG_PROXY_WIDTH_CM * 0.42, 36.0, -_RIG_PROXY_DEPTH_CM * 0.45),
        (_RIG_PROXY_WIDTH_CM * 0.42, 36.0, -_RIG_PROXY_DEPTH_CM * 0.45),
        (-_RIG_PROXY_WIDTH_CM * 0.24, 10.0, -_RIG_PROXY_DEPTH_CM * 0.45),
        (_RIG_PROXY_WIDTH_CM * 0.24, 10.0, -_RIG_PROXY_DEPTH_CM * 0.45),
    )


def _stateful_fragment_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-22.0, 18.0, -18.0),
        (-8.0, 28.0, -19.0),
        (10.0, 24.0, -18.0),
        (24.0, 12.0, -17.0),
    )


def _cloth_anchor_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-_CLOTH_WIDTH_CM * 0.44, _CLOTH_HEIGHT_CM * 0.44, -_CLOTH_DEPTH_CM * 0.5),
        (_CLOTH_WIDTH_CM * 0.44, _CLOTH_HEIGHT_CM * 0.44, -_CLOTH_DEPTH_CM * 0.5),
        (-_CLOTH_WIDTH_CM * 0.36, -_CLOTH_HEIGHT_CM * 0.34, -_CLOTH_DEPTH_CM * 0.5),
        (_CLOTH_WIDTH_CM * 0.36, -_CLOTH_HEIGHT_CM * 0.34, -_CLOTH_DEPTH_CM * 0.5),
    )


def _domain_kit_part_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-42.0, 13.0, -24.0),
        (-14.0, 13.0, -24.0),
        (14.0, 13.0, -24.0),
        (42.0, 13.0, -24.0),
        (-28.0, 13.0, 18.0),
        (0.0, 13.0, 18.0),
        (28.0, 13.0, 18.0),
    )


def _world_system_node_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-52.0, 18.0, -42.0),
        (-18.0, 19.0, -30.0),
        (24.0, 18.0, -36.0),
        (54.0, 19.0, -6.0),
        (-42.0, 18.0, 24.0),
        (2.0, 19.0, 30.0),
        (42.0, 18.0, 34.0),
    )


def _simulation_probe_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-42.0, 22.0, -30.0),
        (-20.0, 26.0, -12.0),
        (0.0, 30.0, 0.0),
        (22.0, 26.0, 12.0),
        (44.0, 22.0, 30.0),
    )


def _multi_asset_member_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-48.0, 20.0, -26.0),
        (-16.0, 20.0, -26.0),
        (16.0, 20.0, -26.0),
        (48.0, 20.0, -26.0),
        (-32.0, 20.0, 18.0),
        (0.0, 20.0, 18.0),
        (32.0, 20.0, 18.0),
    )


def _runtime_port_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-_RUNTIME_WIDTH_CM * 0.52, 28.0, -_RUNTIME_DEPTH_CM * 0.28),
        (-_RUNTIME_WIDTH_CM * 0.52, 18.0, 0.0),
        (-_RUNTIME_WIDTH_CM * 0.52, 8.0, _RUNTIME_DEPTH_CM * 0.28),
        (_RUNTIME_WIDTH_CM * 0.52, 28.0, -_RUNTIME_DEPTH_CM * 0.28),
        (_RUNTIME_WIDTH_CM * 0.52, 18.0, 0.0),
        (_RUNTIME_WIDTH_CM * 0.52, 8.0, _RUNTIME_DEPTH_CM * 0.28),
    )


def _engine_host_target_points() -> tuple[tuple[float, float, float], ...]:
    return ((-48.0, 28.0, -28.0), (-16.0, 32.0, -34.0), (16.0, 32.0, -34.0), (48.0, 28.0, -28.0), (0.0, 38.0, 24.0))


def _engine_adapter_port_points() -> tuple[tuple[float, float, float], ...]:
    return ((-_ENGINE_RUNTIME_WIDTH_CM * 0.52, 30.0, -28.0), (-_ENGINE_RUNTIME_WIDTH_CM * 0.52, 20.0, 0.0), (-_ENGINE_RUNTIME_WIDTH_CM * 0.52, 10.0, 28.0), (_ENGINE_RUNTIME_WIDTH_CM * 0.52, 30.0, -28.0), (_ENGINE_RUNTIME_WIDTH_CM * 0.52, 20.0, 0.0), (_ENGINE_RUNTIME_WIDTH_CM * 0.52, 10.0, 28.0))


def _prefab_source_slot_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 22.0 - row * 10.0, -28.0 + row * 28.0) for row in range(2) for column in range(5))


def _prefab_binding_points() -> tuple[tuple[float, float, float], ...]:
    return ((-42.0, 30.0, 28.0), (-21.0, 34.0, 34.0), (0.0, 36.0, 36.0), (21.0, 34.0, 34.0), (42.0, 30.0, 28.0))


def _scene_anchor_points() -> tuple[tuple[float, float, float], ...]:
    return ((-54.0, 20.0, -32.0), (-27.0, 24.0, -38.0), (0.0, 26.0, -40.0), (27.0, 24.0, -38.0), (54.0, 20.0, -32.0))


def _scene_layer_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 30.0 - row * 10.0, 28.0 + row * 10.0) for row in range(2) for column in range(5))


def _behavior_node_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 26.0 - row * 10.0, -26.0 + row * 28.0) for row in range(2) for column in range(5))


def _behavior_port_points() -> tuple[tuple[float, float, float], ...]:
    return ((-44.0, 12.0, 32.0), (-22.0, 16.0, 38.0), (0.0, 18.0, 40.0), (22.0, 16.0, 38.0), (44.0, 12.0, 32.0))


def _streaming_cell_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-54.0 + column * 27.0, 18.0, -36.0 + row * 24.0) for row in range(4) for column in range(5))


def _streaming_volume_points() -> tuple[tuple[float, float, float], ...]:
    return ((-52.0, 26.0, 34.0), (-18.0, 30.0, 42.0), (18.0, 30.0, 42.0), (52.0, 26.0, 34.0))


def _save_slot_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + column * 28.0, 22.0 - row * 10.0, -28.0 + row * 28.0) for row in range(2) for column in range(4))


def _save_state_table_points() -> tuple[tuple[float, float, float], ...]:
    return ((-42.0, 32.0, 30.0), (-14.0, 36.0, 36.0), (14.0, 36.0, 36.0), (42.0, 32.0, 30.0))


def _quest_objective_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 22.0 - row * 10.0, -30.0 + row * 28.0) for row in range(2) for column in range(5))


def _dialogue_choice_points() -> tuple[tuple[float, float, float], ...]:
    return ((-42.0, 32.0, 30.0), (-14.0, 36.0, 36.0), (14.0, 36.0, 36.0), (42.0, 32.0, 30.0))


def _camera_shot_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 28.0 - row * 10.0, -28.0 + row * 28.0) for row in range(2) for column in range(5))


def _camera_target_points() -> tuple[tuple[float, float, float], ...]:
    return ((-48.0, 10.0, 34.0), (-24.0, 16.0, 42.0), (0.0, 12.0, 46.0), (24.0, 16.0, 42.0), (48.0, 10.0, 34.0))


def _audio_event_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-45.0 + column * 22.5, 22.0 - row * 9.0, -26.0 + row * 26.0) for row in range(2) for column in range(5))


def _audio_bus_points() -> tuple[tuple[float, float, float], ...]:
    return ((-42.0, 8.0, 32.0), (-14.0, 12.0, 38.0), (14.0, 12.0, 38.0), (42.0, 8.0, 32.0))


def _localization_key_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-54.0 + column * 27.0, 22.0 - row * 9.0, -32.0 + row * 28.0) for row in range(2) for column in range(5))


def _locale_column_points() -> tuple[tuple[float, float, float], ...]:
    return ((-48.0, 30.0, 30.0), (-24.0, 34.0, 38.0), (0.0, 36.0, 42.0), (24.0, 34.0, 38.0), (48.0, 30.0, 30.0))


def _accessibility_cue_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-45.0 + column * 22.5, 22.0 - row * 9.0, -28.0 + row * 28.0) for row in range(2) for column in range(5))


def _accessibility_focus_points() -> tuple[tuple[float, float, float], ...]:
    return ((-48.0, 9.0, 34.0), (-24.0, 15.0, 42.0), (0.0, 11.0, 46.0), (24.0, 15.0, 42.0), (48.0, 9.0, 34.0))


def _economy_flow_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 24.0 - row * 10.0, -30.0 + row * 28.0) for row in range(2) for column in range(5))


def _economy_curve_points() -> tuple[tuple[float, float, float], ...]:
    return ((-46.0, 30.0, 32.0), (-16.0, 36.0, 42.0), (16.0, 36.0, 42.0), (46.0, 30.0, 32.0))


def _replication_state_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-54.0 + column * 27.0, 24.0 - row * 10.0, -32.0 + row * 30.0) for row in range(2) for column in range(5))


def _replication_channel_points() -> tuple[tuple[float, float, float], ...]:
    return ((-50.0, 8.0, 38.0), (-17.0, 12.0, 46.0), (17.0, 12.0, 46.0), (50.0, 8.0, 38.0))


def _cross_domain_pillar_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-48.0, 24.0, -24.0),
        (-16.0, 24.0, -24.0),
        (16.0, 24.0, -24.0),
        (48.0, 24.0, -24.0),
        (-32.0, 24.0, 20.0),
        (0.0, 24.0, 20.0),
        (32.0, 24.0, 20.0),
    )


def _style_axis_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + index * 14.0, 20.0, -_STYLE_STACK_DEPTH_CM * 0.34) for index in range(7))


def _typed_primary_slot_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-42.0, 29.0, -18.0),
        (-14.0, 29.0, -18.0),
        (14.0, 29.0, -18.0),
        (42.0, 29.0, -18.0),
    )


def _typed_secondary_slot_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-42.0, 29.0, 18.0),
        (-14.0, 29.0, 18.0),
        (14.0, 29.0, 18.0),
        (42.0, 29.0, 18.0),
    )


def _attribute_surface_node_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-42.0, 24.0, -22.0),
        (-14.0, 24.0, -26.0),
        (14.0, 24.0, -26.0),
        (42.0, 24.0, -22.0),
        (-28.0, 24.0, 8.0),
        (0.0, 24.0, 12.0),
        (28.0, 24.0, 8.0),
    )


def _vegetation_species_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-46.0, 28.0, -26.0),
        (-18.0, 28.0, -30.0),
        (10.0, 28.0, -30.0),
        (38.0, 28.0, -26.0),
        (-32.0, 28.0, 18.0),
        (0.0, 28.0, 22.0),
        (32.0, 28.0, 18.0),
    )


def _terrain_probe_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-54.0 + column * 18.0, 21.5, -30.0 + row * 20.0) for row in range(4) for column in range(7))


def _wfc_tile_catalog_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 24.0, -30.0 + row * 24.0) for row in range(3) for column in range(5))


def _wfc_grid_cell_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-45.0 + column * 15.0, 23.0, -18.0 + row * 15.0) for row in range(4) for column in range(7))


def _cga_floor_band_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((0.0, 18.0 + index * 7.0, -_CGA_GRAMMAR_DEPTH_CM * 0.38) for index in range(6))


def _cga_terminal_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-40.0, 30.0, 26.0),
        (-20.0, 38.0, 28.0),
        (0.0, 46.0, 26.0),
        (20.0, 38.0, 28.0),
        (40.0, 30.0, 26.0),
    )


def _volume_channel_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-38.0, 31.0, -20.0),
        (-14.0, 36.0, -24.0),
        (14.0, 34.0, -22.0),
        (38.0, 30.0, -18.0),
        (-26.0, 42.0, 18.0),
        (0.0, 46.0, 24.0),
        (26.0, 42.0, 18.0),
    )


def _scatter_sample_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-54.0 + column * 18.0, 28.0, -30.0 + row * 18.0) for row in range(4) for column in range(7))


def _sdf_primitive_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-36.0, 30.0, -24.0),
        (-12.0, 36.0, -8.0),
        (12.0, 34.0, 10.0),
        (36.0, 30.0, 24.0),
        (-24.0, 44.0, 18.0),
        (0.0, 48.0, 26.0),
        (24.0, 42.0, 18.0),
    )


def _subdivision_cage_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + column * 21.0, 28.0, -24.0 + row * 18.0) for row in range(3) for column in range(5))


def _humanoid_landmark_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (0.0, 166.0, 0.0),
        (-18.0, 142.0, 0.0),
        (18.0, 142.0, 0.0),
        (0.0, 122.0, 0.0),
        (-16.0, 102.0, 0.0),
        (16.0, 102.0, 0.0),
        (-20.0, 86.0, 0.0),
        (20.0, 86.0, 0.0),
        (-10.0, 50.0, 0.0),
        (10.0, 50.0, 0.0),
        (-8.0, 8.0, 0.0),
        (8.0, 8.0, 0.0),
    )


def _morph_target_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-30.0 + column * 12.0, 28.0 + row * 7.0, 28.0) for row in range(3) for column in range(6))


def _face_sdf_mask_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-28.0, 42.0, -18.0),
        (-10.0, 44.0, -22.0),
        (10.0, 44.0, -22.0),
        (28.0, 42.0, -18.0),
        (-18.0, 34.0, -20.0),
        (0.0, 32.0, -24.0),
        (18.0, 34.0, -20.0),
        (-16.0, 24.0, -18.0),
        (0.0, 22.0, -20.0),
        (16.0, 24.0, -18.0),
    )


def _rig_component_catalog_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + column * 21.0, 48.0 - row * 12.0, -26.0) for row in range(2) for column in range(5))


def _morph_catalog_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 16.0, 34.0 - row * 7.0, -26.0) for row in range(4) for column in range(7))


def _corrective_shape_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-42.0, 30.0, 18.0),
        (-24.0, 34.0, 22.0),
        (-6.0, 30.0, 24.0),
        (12.0, 34.0, 22.0),
        (30.0, 30.0, 18.0),
        (48.0, 26.0, 14.0),
    )


def _animation_clip_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-50.0 + column * 20.0, 30.0 - row * 7.0, -30.0) for row in range(3) for column in range(6))


def _animation_event_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-44.0 + index * 11.0, 12.0, 28.0) for index in range(9))


def _retarget_bone_map_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + column * 14.0, 46.0 - row * 8.0, -26.0) for row in range(4) for column in range(7))


def _retarget_guard_points() -> tuple[tuple[float, float, float], ...]:
    return ((-46.0, 18.0, 28.0), (-16.0, 22.0, 32.0), (16.0, 22.0, 32.0), (46.0, 18.0, 28.0))


def _equipment_slot_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (0.0, 62.0, -22.0),
        (-28.0, 48.0, -20.0),
        (28.0, 48.0, -20.0),
        (0.0, 38.0, -24.0),
        (-22.0, 26.0, -20.0),
        (22.0, 26.0, -20.0),
        (-16.0, 12.0, -18.0),
        (16.0, 12.0, -18.0),
    )


def _equipment_loadout_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + column * 21.0, 54.0 - row * 9.0, 26.0) for row in range(3) for column in range(5))


def _controller_state_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 26.0 - row * 8.0, -28.0) for row in range(3) for column in range(5))


def _controller_parameter_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-52.0 + index * 13.0, 10.0, 30.0) for index in range(9))


def _facial_control_points() -> tuple[tuple[float, float, float], ...]:
    return (
        (-36.0, 38.0, -24.0),
        (-18.0, 42.0, -28.0),
        (0.0, 40.0, -30.0),
        (18.0, 42.0, -28.0),
        (36.0, 38.0, -24.0),
        (-28.0, 26.0, -26.0),
        (-10.0, 24.0, -30.0),
        (10.0, 24.0, -30.0),
        (28.0, 26.0, -26.0),
    )


def _hair_root_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + column * 14.0, 40.0 - row * 6.0, -24.0 + row * 3.0) for row in range(4) for column in range(7))


def _hair_card_points() -> tuple[tuple[float, float, float], ...]:
    return ((-44.0, 18.0, 28.0), (-22.0, 24.0, 34.0), (0.0, 26.0, 36.0), (22.0, 24.0, 34.0), (44.0, 18.0, 28.0))


def _cloth_pin_points() -> tuple[tuple[float, float, float], ...]:
    return ((-46.0, 38.0, -26.0), (-18.0, 42.0, -30.0), (18.0, 42.0, -30.0), (46.0, 38.0, -26.0), (-36.0, 16.0, -24.0), (36.0, 16.0, -24.0))


def _cloth_param_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + index * 14.0, 8.0, 26.0) for index in range(7))


def _fluid_channel_points() -> tuple[tuple[float, float, float], ...]:
    return ((-36.0, 42.0, -20.0), (-12.0, 46.0, -24.0), (12.0, 46.0, -24.0), (36.0, 42.0, -20.0), (-24.0, 30.0, -26.0), (0.0, 32.0, -30.0), (24.0, 30.0, -26.0))


def _fluid_emitter_points() -> tuple[tuple[float, float, float], ...]:
    return ((-42.0, 20.0, 28.0), (-14.0, 24.0, 34.0), (14.0, 24.0, 34.0), (42.0, 20.0, 28.0))


def _construction_module_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 30.0 - row * 14.0, -28.0 + row * 18.0) for row in range(2) for column in range(5))


def _construction_socket_points() -> tuple[tuple[float, float, float], ...]:
    return ((-54.0, 18.0, 28.0), (-27.0, 24.0, 34.0), (0.0, 26.0, 36.0), (27.0, 24.0, 34.0), (54.0, 18.0, 28.0))


def _appendage_socket_points() -> tuple[tuple[float, float, float], ...]:
    return ((-48.0, 36.0, -24.0), (-24.0, 44.0, -30.0), (0.0, 48.0, -32.0), (24.0, 44.0, -30.0), (48.0, 36.0, -24.0))


def _appendage_variant_points() -> tuple[tuple[float, float, float], ...]:
    return ((-42.0, 18.0, 28.0), (-14.0, 24.0, 34.0), (14.0, 24.0, 34.0), (42.0, 18.0, 28.0), (0.0, 10.0, 38.0))


def _body_part_catalog_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-42.0 + column * 28.0, 36.0 - row * 16.0, -26.0 + row * 24.0) for row in range(2) for column in range(4))


def _body_part_socket_points() -> tuple[tuple[float, float, float], ...]:
    return ((-42.0, 28.0, 28.0), (-14.0, 34.0, 34.0), (14.0, 34.0, 34.0), (42.0, 28.0, 28.0), (0.0, 48.0, -30.0))


def _material_primitive_points() -> tuple[tuple[float, float, float], ...]:
    return tuple((-48.0 + column * 24.0, 20.0 - row * 10.0, -28.0 + row * 28.0) for row in range(2) for column in range(5))


def _material_channel_points() -> tuple[tuple[float, float, float], ...]:
    return ((-42.0, 30.0, 30.0), (-21.0, 34.0, 34.0), (0.0, 36.0, 36.0), (21.0, 34.0, 34.0), (42.0, 30.0, 30.0))


def _industrial_crate_body_shell() -> tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]:
    """Return the v2 ops + graph nodes for the ``body_shell`` requirement.

    Emits a source-aware ``sop.polybevel`` over the spec-canonical
    industrial crate body dimensions (92cm x 58cm x 64cm) and one
    ``primary_volume`` graph node. The private authoring op lowers to a
    stable ``subdivision_box`` instead of exposing the crate body as a
    plain v1 box.
    """
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="body",
            parameters={
                "source": _body_box_source(_purpose("body_shell", "body_box_source")),
                "width_cm": 2.4,
                "segments": 5,
            },
            purpose=_purpose("body_shell", "polybeveled_primary_volume"),
        ),
    )
    nodes = (_node("recipe.body_shell", "primary_volume"),)
    return ops, nodes


def _industrial_crate_lid_seam() -> tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]:
    """Return the v2 ops + graph nodes for the ``lid_seam`` requirement.

    Emits one subtractive ``sop.boolean`` seam groove and one
    ``sop.polybevel`` lid lip, plus one ``panel`` graph node tagged as
    the lid seam.
    """
    ops = (
        ShapeOp(
            op="sop.boolean",
            target="body.top_band",
            parameters={
                "operation": "subtract",
                "source": _panel_source(
                    target="lid_seam_cut",
                    width_cm=78.0,
                    height_cm=0.9,
                    thickness_cm=1.2,
                    center=(0.0, 24.5, -32.2),
                    purpose=_purpose("lid_seam", "front_cut_source"),
                ),
            },
            purpose=_purpose("lid_seam", "front_cut"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="body.top_band",
            parameters={
                "source": _panel_source(
                    target="lid_lip",
                    width_cm=84.0,
                    height_cm=5.0,
                    thickness_cm=1.4,
                    center=(0.0, 29.5, 0.0),
                    purpose=_purpose("lid_seam", "lid_lip_source"),
                ),
                "width_cm": 0.45,
                "segments": 3,
            },
            purpose=_purpose("lid_seam", "polybeveled_lid_lip"),
        ),
    )
    nodes = (_node("recipe.lid_seam", "panel"),)
    return ops, nodes


def _industrial_crate_corner_guards() -> tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]:
    """Return the v2 ops + graph nodes for the ``corner_guards`` requirement.

    Emits one ``sop.copy_to_points`` carrying a beveled guard source plus
    eight ``guard`` graph nodes (one per body corner).
    """
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="body.corners",
            parameters={
                "source": _polybeveled_source(
                    _source_op(
                        "solid.box",
                        "corner_guard",
                        {
                            "width_cm": 6.0,
                            "height_cm": 8.0,
                            "depth_cm": 6.0,
                        },
                        _purpose("corner_guard_set", "guard_block_source"),
                    ),
                    width_cm=0.75,
                    segments=3,
                    target="corner_guard",
                    purpose=_purpose("corner_guard_set", "polybeveled_guard_source"),
                ),
                "points": _crate_corner_points(),
            },
            purpose=_purpose("corner_guard_set", "copy_to_eight_corners"),
        ),
    )
    nodes = tuple(_node(f"recipe.corner_guard_{index}", "guard") for index in range(8))
    return ops, nodes


def _industrial_crate_latch_or_latch_plate() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``latch_or_latch_plate`` requirement.

    Emits one beveled panel source on the body's front face plus one
    ``inset`` graph node so downstream graph consumers see a recessed
    latch surface.
    """
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="body.front_face",
            parameters={
                "source": _panel_source(
                    target="latch_plate",
                    width_cm=8.0,
                    height_cm=6.0,
                    thickness_cm=1.1,
                    center=(0.0, 2.0, -32.6),
                    purpose=_purpose("latch_plate", "panel_source"),
                ),
                "width_cm": 0.35,
                "segments": 3,
            },
            purpose=_purpose("latch_plate", "polybeveled_mount_plate"),
        ),
    )
    nodes = (_node("recipe.latch_plate", "inset"),)
    return ops, nodes


def _industrial_crate_recessed_or_bracketed_handles() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``recessed_or_bracketed_handles`` requirement.

    Emits two ``sop.polywire`` handle arcs (left + right) and two
    ``handle`` graph nodes matching the part-list naming convention
    (``handle_l`` / ``handle_r``).
    """
    ops = (
        ShapeOp(
            op="sop.polywire",
            target="body.left_face",
            parameters={
                "radius_cm": 0.9,
                "path": (
                    (-46.6, -4.0, -12.0),
                    (-49.0, 0.0, 0.0),
                    (-46.6, -4.0, 12.0),
                ),
            },
            purpose=_purpose("handles", "left_polywire_arc"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="body.right_face",
            parameters={
                "radius_cm": 0.9,
                "path": (
                    (46.6, -4.0, -12.0),
                    (49.0, 0.0, 0.0),
                    (46.6, -4.0, 12.0),
                ),
            },
            purpose=_purpose("handles", "right_polywire_arc"),
        ),
    )
    nodes = (
        _node("recipe.handle_l", "handle"),
        _node("recipe.handle_r", "handle"),
    )
    return ops, nodes


def _industrial_crate_foot_rails_or_feet() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``foot_rails_or_feet`` requirement.

    Emits two beveled rail sources spanning the bottom of the body plus
    two ``rail`` graph nodes (front + back).
    """
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="body.bottom_front",
            parameters={
                "source": _source_op(
                    "solid.rail",
                    "foot_rail_front",
                    {
                        "length_cm": 60.0,
                        "profile_cm": 4.0,
                        "center": (0.0, -31.5, -24.0),
                    },
                    _purpose("foot_rails", "front_source"),
                ),
                "width_cm": 0.45,
                "segments": 3,
            },
            purpose=_purpose("foot_rails", "front_polybeveled"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="body.bottom_back",
            parameters={
                "source": _source_op(
                    "solid.rail",
                    "foot_rail_back",
                    {
                        "length_cm": 60.0,
                        "profile_cm": 4.0,
                        "center": (0.0, -31.5, 24.0),
                    },
                    _purpose("foot_rails", "back_source"),
                ),
                "width_cm": 0.45,
                "segments": 3,
            },
            purpose=_purpose("foot_rails", "back_polybeveled"),
        ),
    )
    nodes = (
        _node("recipe.foot_rail_front", "rail"),
        _node("recipe.foot_rail_back", "rail"),
    )
    return ops, nodes


def _industrial_crate_trim_bands() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``trim_bands`` requirement.

    Emits one ``sop.copy_to_points`` over a beveled panel-strip source
    running across the body's mid-plane and one ``trim`` graph node.
    """
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="body.mid_plane",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="trim_band",
                        width_cm=86.0,
                        height_cm=2.0,
                        thickness_cm=1.0,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("trim_bands", "band_source"),
                    ),
                    width_cm=0.25,
                    segments=2,
                    target="trim_band",
                    purpose=_purpose("trim_bands", "polybeveled_band_source"),
                ),
                "points": (
                    (0.0, 5.0, -32.4),
                    (0.0, 5.0, 32.4),
                ),
            },
            purpose=_purpose("trim_bands", "copy_front_back"),
        ),
    )
    nodes = (_node("recipe.trim_band_mid", "trim"),)
    return ops, nodes


def _industrial_crate_fasteners() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``fasteners`` requirement.

    Emits one generic ``op.distribute`` grid over a lathed rivet source
    on the body's front face plus one ``fastener`` graph node.
    """
    ops = (
        ShapeOp(
            op="op.distribute",
            target="body.front_face",
            parameters={
                "pattern": "grid",
                "source": _source_op(
                    "solid.revolved_profile",
                    "fastener",
                    {
                        "profile_points": _rivet_profile(),
                        "axis": "z",
                    },
                    _purpose("fasteners", "domed_rivet_source"),
                ),
                "rows": 2,
                "columns": 2,
                "row_axis": "y",
                "column_axis": "x",
                "row_spacing_cm": 14.0,
                "column_spacing_cm": 16.0,
                "center": (0.0, 0.0, -33.0),
            },
            purpose=_purpose("fasteners", "distributed_front_grid"),
        ),
    )
    nodes = (_node("recipe.fastener_grid_front", "fastener"),)
    return ops, nodes


def _industrial_crate_warning_or_decal_zones() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``warning_or_decal_zones`` requirement.

    Emits one shallow ``sop.polyextrude`` panel marker on the front face
    and one ``decal_zone`` graph node. This gives the recipe a concrete
    geometric zone for future material binding without adding public
    syntax.
    """
    ops = (
        ShapeOp(
            op="sop.polyextrude",
            target="body.front_face",
            parameters={
                "profile_polygon": _rect_profile(14.0, 6.0),
                "extrude_height_cm": 0.35,
                "axis": "z",
                "center": (20.0, 8.0, -33.2),
            },
            purpose=_purpose("warning_decal_zone", "front_polyextruded_zone"),
        ),
    )
    nodes = (_node("recipe.warning_decal_zone", "decal_zone"),)
    return ops, nodes


def _industrial_crate_edge_wear_masks() -> (
    tuple[tuple[ShapeOp, ...], tuple[dict[str, Any], ...]]
):
    """Return the v2 ops + graph nodes for the ``edge_wear_masks`` requirement.

    Emits one ``op.chip_edges`` carrying the spec's medium-edge-wear
    intent (amount=0.28) plus one ``wear_zone`` graph node so Phase 8's
    material/wear graph can drive the wear-mask authoring.
    """
    ops = (
        ShapeOp(
            op="op.chip_edges",
            target="body.outer_edges",
            parameters={"amount": 0.28},
            purpose=_purpose("edge_wear_masks", "chip_edges"),
        ),
    )
    nodes = (_node("recipe.edge_wear_zone", "wear_zone"),)
    return ops, nodes


# Per-requirement lowering functions in industrial_crate grammar's
# canonical declaration order. Each entry returns a (ops, nodes) tuple;
# the recipe stitches them together deterministically.
_INDUSTRIAL_CRATE_LOWERERS: tuple[
    tuple[
        str,
        Any,
    ],
    ...,
] = (
    ("body_shell", _industrial_crate_body_shell),
    ("lid_seam", _industrial_crate_lid_seam),
    ("corner_guards", _industrial_crate_corner_guards),
    ("latch_or_latch_plate", _industrial_crate_latch_or_latch_plate),
    ("recessed_or_bracketed_handles", _industrial_crate_recessed_or_bracketed_handles),
    ("foot_rails_or_feet", _industrial_crate_foot_rails_or_feet),
    ("trim_bands", _industrial_crate_trim_bands),
    ("fasteners", _industrial_crate_fasteners),
    ("warning_or_decal_zones", _industrial_crate_warning_or_decal_zones),
    ("edge_wear_masks", _industrial_crate_edge_wear_masks),
)


def _mechanical_door_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="op.mirror",
            target="door.frame",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="door_frame_horizontal",
                        width_cm=_MECHANICAL_DOOR_WIDTH_CM + 14.0,
                        height_cm=8.0,
                        thickness_cm=8.0,
                        center=(0.0, _MECHANICAL_DOOR_HEIGHT_CM * 0.5, 0.0),
                        purpose=_purpose("door_frame", "horizontal_source"),
                    ),
                    width_cm=0.75,
                    segments=3,
                    target="door_frame_horizontal",
                    purpose=_purpose("door_frame", "polybeveled_horizontal_source"),
                ),
                "axis": "y",
                "include_source": True,
            },
            purpose=_purpose("door_frame", "mirror_horizontal_frame"),
        ),
        ShapeOp(
            op="op.mirror",
            target="door.frame",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="door_frame_vertical",
                        width_cm=8.0,
                        height_cm=_MECHANICAL_DOOR_HEIGHT_CM,
                        thickness_cm=8.0,
                        center=(_MECHANICAL_DOOR_WIDTH_CM * 0.5, 0.0, 0.0),
                        purpose=_purpose("door_frame", "vertical_source"),
                    ),
                    width_cm=0.75,
                    segments=3,
                    target="door_frame_vertical",
                    purpose=_purpose("door_frame", "polybeveled_vertical_source"),
                ),
                "axis": "x",
                "include_source": True,
            },
            purpose=_purpose("door_frame", "mirror_vertical_frame"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="door.leaf",
            parameters={
                "source": _panel_source(
                    target="door_leaf",
                    width_cm=_MECHANICAL_DOOR_WIDTH_CM - 18.0,
                    height_cm=_MECHANICAL_DOOR_HEIGHT_CM - 24.0,
                    thickness_cm=_MECHANICAL_DOOR_DEPTH_CM * 0.45,
                    center=(0.0, 0.0, -2.5),
                    purpose=_purpose("inset_door_leaf", "panel_source"),
                ),
                "width_cm": 1.1,
                "segments": 4,
            },
            purpose=_purpose("inset_door_leaf", "polybeveled_leaf"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="door.hinges",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "hinge_barrel",
                    {
                        "profile_points": _capped_hinge_barrel_profile(),
                        "axis": "y",
                        "revolve_degrees": 300.0,
                        "revolve_start_degrees": 30.0,
                    },
                    _purpose("hinge_stack", "barrel_source"),
                ),
                "points": (
                    (-52.0, -45.0, -5.0),
                    (-52.0, 0.0, -5.0),
                    (-52.0, 45.0, -5.0),
                ),
            },
            purpose=_purpose("hinge_stack", "copy_three_hinges"),
        ),
        ShapeOp(
            op="sop.transform",
            target="door.actuator",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="door_actuator",
                        width_cm=12.0,
                        height_cm=18.0,
                        thickness_cm=1.2,
                        center=(30.0, 2.0, -6.2),
                        purpose=_purpose("lock_or_actuator", "plate_source"),
                    ),
                    width_cm=0.45,
                    segments=3,
                    target="door_actuator",
                    purpose=_purpose("lock_or_actuator", "polybeveled_plate_source"),
                ),
                "origin": (30.0, 2.0, -6.2),
                "rotation_axis": "z",
                "rotation_degrees": -4.0,
            },
            purpose=_purpose("lock_or_actuator", "rotated_plate_transform"),
        ),
        ShapeOp(
            op="op.mirror",
            target="door.threshold_rails",
            parameters={
                "source": _source_op(
                    "solid.rail",
                    "door_guide_rail",
                    {
                        "length_cm": 108.0,
                        "profile_cm": 3.0,
                        "center": (0.0, 74.5, -6.0),
                    },
                    _purpose("guide_or_threshold_rails", "rail_source"),
                ),
                "axis": "y",
                "include_source": True,
            },
            purpose=_purpose("guide_or_threshold_rails", "mirror_top_bottom"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="door.panel_grooves",
            parameters={
                "source": _source_op(
                    "sop.boolean",
                    "door_leaf_groove",
                    {
                        "operation": "subtract",
                        "source": _panel_source(
                            target="door_leaf_groove_cut",
                            width_cm=3.0,
                            height_cm=104.0,
                            thickness_cm=0.7,
                            center=(0.0, 0.0, -6.5),
                            purpose=_purpose("panel_grooves", "groove_source"),
                        ),
                    },
                    _purpose("panel_grooves", "subtractive_groove_source"),
                ),
                "points": (
                    (-24.0, 0.0, -6.5),
                    (0.0, 0.0, -6.5),
                    (24.0, 0.0, -6.5),
                ),
            },
            purpose=_purpose("panel_grooves", "copy_vertical_grooves"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="door.handle",
            parameters={
                "radius_cm": 0.9,
                "path": (
                    (34.0, -12.0, -7.0),
                    (39.0, 0.0, -8.0),
                    (34.0, 12.0, -7.0),
                ),
            },
            purpose=_purpose("access_handle", "curved_pull"),
        ),
        ShapeOp(
            op="op.distribute",
            target="door.frame_fasteners",
            parameters={
                "pattern": "grid",
                "source": _source_op(
                    "solid.revolved_profile",
                    "door_fastener",
                    {
                        "profile_points": _rivet_profile(),
                        "axis": "z",
                    },
                    _purpose("fasteners", "rivet_source"),
                ),
                "rows": 2,
                "columns": 2,
                "row_axis": "y",
                "column_axis": "x",
                "row_spacing_cm": 120.0,
                "column_spacing_cm": 88.0,
                "center": (0.0, 0.0, -6.5),
            },
            purpose=_purpose("fasteners", "distributed_frame_rivets"),
        ),
        ShapeOp(
            op="op.distribute",
            target="door.hinge_fasteners",
            parameters={
                "pattern": "linear",
                "source": _source_op(
                    "solid.revolved_profile",
                    "door_hinge_fastener",
                    {
                        "profile_points": _rivet_profile(),
                        "axis": "z",
                    },
                    _purpose("fasteners", "hinge_rivet_source"),
                ),
                "count": 3,
                "axis": "y",
                "spacing_cm": 45.0,
                "center": (-52.0, 0.0, -6.8),
            },
            purpose=_purpose("fasteners", "distributed_hinge_rivets"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="door.decal_zone",
            parameters={
                "profile_polygon": _rect_profile(18.0, 7.0),
                "extrude_height_cm": 0.3,
                "axis": "z",
                "center": (-20.0, 46.0, -7.2),
            },
            purpose=_purpose("warning_or_decal_zones", "front_polyextruded_zone"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="door.outer_edges",
            parameters={"amount": 0.22},
            purpose=_purpose("edge_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.door_frame", "frame"),
        _node("recipe.door_leaf", "panel"),
        _node("recipe.hinge_stack", "hinge"),
        _node("recipe.lock_actuator", "inset"),
        _node("recipe.threshold_rails", "rail"),
        _node("recipe.panel_grooves", "trim"),
        _node("recipe.access_handle", "handle"),
        _node("recipe.door_fasteners", "fastener"),
        _node("recipe.door_warning_decal", "decal_zone"),
        _node("recipe.door_edge_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="mechanical_door",
        family="mechanical_door",
        ops=ops,
    )
    return RecipeResult(
        family="mechanical_door",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _service_cabinet_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="cabinet.shell",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "cabinet_shell",
                    {
                        "width_cm": _SERVICE_CABINET_WIDTH_CM,
                        "height_cm": _SERVICE_CABINET_HEIGHT_CM,
                        "depth_cm": _SERVICE_CABINET_DEPTH_CM,
                    },
                    _purpose("cabinet_shell", "box_source"),
                ),
                "width_cm": 1.2,
                "segments": 4,
            },
            purpose=_purpose("cabinet_shell", "polybeveled_shell"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="cabinet.front_panel",
            parameters={
                "source": _panel_source(
                    target="cabinet_front_panel",
                    width_cm=38.0,
                    height_cm=58.0,
                    thickness_cm=1.1,
                    center=(0.0, 0.0, -9.6),
                    purpose=_purpose("front_door_panel", "panel_source"),
                ),
                "width_cm": 0.55,
                "segments": 3,
            },
            purpose=_purpose("front_door_panel", "polybeveled_front_panel"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cabinet.hinge_line",
            parameters={
                "radius_cm": 0.7,
                "path": (
                    (-21.0, -24.0, -10.2),
                    (-22.4, 0.0, -10.6),
                    (-21.0, 24.0, -10.2),
                ),
            },
            purpose=_purpose("hinge_line", "continuous_polywire_hinge"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cabinet.handle",
            parameters={
                "radius_cm": 0.65,
                "path": (
                    (15.0, -7.5, -10.4),
                    (18.0, 0.0, -11.5),
                    (15.0, 7.5, -10.4),
                ),
            },
            purpose=_purpose("pull_handle", "curved_pull"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="cabinet.latch_plate",
            parameters={
                "source": _panel_source(
                    target="cabinet_latch_plate",
                    width_cm=7.0,
                    height_cm=9.0,
                    thickness_cm=1.0,
                    center=(13.0, 0.0, -10.8),
                    purpose=_purpose("latch_or_lock_plate", "plate_source"),
                ),
                "width_cm": 0.35,
                "segments": 2,
            },
            purpose=_purpose("latch_or_lock_plate", "polybeveled_plate"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cabinet.vents",
            parameters={
                "source": _source_op(
                    "sop.boolean",
                    "cabinet_vent_cut",
                    {
                        "operation": "subtract",
                        "source": _panel_source(
                            target="cabinet_vent_slot",
                            width_cm=18.0,
                            height_cm=1.3,
                            thickness_cm=0.7,
                            center=(0.0, 0.0, -10.9),
                            purpose=_purpose("vent_slats", "slot_source"),
                        ),
                    },
                    _purpose("vent_slats", "subtractive_slot_source"),
                ),
                "points": (
                    (-8.0, 18.0, -10.9),
                    (-8.0, 22.0, -10.9),
                    (-8.0, 26.0, -10.9),
                    (-8.0, 30.0, -10.9),
                ),
            },
            purpose=_purpose("vent_slats", "copy_upper_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cabinet.mounts",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="cabinet_mount_bracket",
                        width_cm=8.0,
                        height_cm=5.0,
                        thickness_cm=2.0,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("mounting_brackets", "bracket_source"),
                    ),
                    width_cm=0.35,
                    segments=2,
                    target="cabinet_mount_bracket",
                    purpose=_purpose("mounting_brackets", "polybeveled_bracket_source"),
                ),
                "points": (
                    (-17.0, -32.0, 8.5),
                    (17.0, -32.0, 8.5),
                    (-17.0, 32.0, 8.5),
                    (17.0, 32.0, 8.5),
                ),
            },
            purpose=_purpose("mounting_brackets", "copy_four_brackets"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cabinet.fasteners",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "cabinet_fastener",
                    {
                        "profile_points": _rivet_profile(),
                        "axis": "z",
                    },
                    _purpose("fasteners", "rivet_source"),
                ),
                "points": (
                    (-18.0, -26.0, -11.2),
                    (18.0, -26.0, -11.2),
                    (-18.0, 26.0, -11.2),
                    (18.0, 26.0, -11.2),
                    (-22.0, -20.0, -10.9),
                    (-22.0, 20.0, -10.9),
                ),
            },
            purpose=_purpose("fasteners", "copy_panel_and_hinge_rivets"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="cabinet.label_zone",
            parameters={
                "profile_polygon": _rect_profile(14.0, 5.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (5.0, -22.0, -11.2),
            },
            purpose=_purpose("label_or_decal_zone", "front_polyextruded_zone"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="cabinet.handled_edges",
            parameters={"amount": 0.16},
            purpose=_purpose("edge_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.cabinet_shell", "primary_volume"),
        _node("recipe.cabinet_front_panel", "panel"),
        _node("recipe.cabinet_hinge_line", "hinge"),
        _node("recipe.cabinet_pull_handle", "handle"),
        _node("recipe.cabinet_latch_plate", "inset"),
        _node("recipe.cabinet_vent_slats", "trim"),
        _node("recipe.cabinet_mounting_brackets", "mount"),
        _node("recipe.cabinet_fasteners", "fastener"),
        _node("recipe.cabinet_label_zone", "decal_zone"),
        _node("recipe.cabinet_edge_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="service_cabinet",
        family="service_cabinet",
        ops=ops,
    )
    return RecipeResult(
        family="service_cabinet",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _weapon_prop_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="weapon.primary_body",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "weapon_primary_body",
                    {
                        "profile_polygon": _weapon_blade_profile(),
                        "extrude_height_cm": _WEAPON_LENGTH_CM,
                        "axis": "z",
                        "center": (0.0, 8.0, 8.0),
                        "extrude_end_scale": 0.72,
                        "extrude_twist_degrees": 6.0,
                        "extrude_segments": 8,
                    },
                    _purpose("primary_weapon_body", "extruded_profile_source"),
                ),
                "width_cm": 0.65,
                "segments": 3,
            },
            purpose=_purpose("primary_weapon_body", "polybeveled_linear_body"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="weapon.grip",
            parameters={
                "radius_cm": 1.35,
                "path": (
                    (0.0, -4.0, -44.0),
                    (0.0, -18.0, -38.0),
                    (0.0, -25.0, -28.0),
                ),
            },
            purpose=_purpose("grip_or_handle", "curved_grip"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="weapon.guard",
            parameters={
                "source": _panel_source(
                    target="weapon_guard",
                    width_cm=28.0,
                    height_cm=5.0,
                    thickness_cm=3.0,
                    center=(0.0, -2.0, -34.0),
                    purpose=_purpose("guard_or_hand_stop", "guard_source"),
                ),
                "width_cm": 0.55,
                "segments": 3,
            },
            purpose=_purpose("guard_or_hand_stop", "polybeveled_cross_guard"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="weapon.active_edge",
            parameters={
                "profile_polygon": (
                    (-1.1, -36.0),
                    (1.1, -36.0),
                    (0.0, 45.0),
                ),
                "extrude_height_cm": 0.55,
                "axis": "y",
                "center": (0.0, 12.8, 6.0),
            },
            purpose=_purpose("active_edge_or_barrel", "raised_center_edge"),
        ),
        ShapeOp(
            op="sop.carve",
            target="weapon.centerline_detail",
            parameters={
                "source": _source_op(
                    "solid.swept_profile",
                    "weapon_centerline",
                    {
                        "cross_section": _rect_profile(1.4, 0.9),
                        "sweep_path": (
                            (0.0, 14.2, -28.0),
                            (0.0, 15.0, 28.0),
                            (0.0, 13.4, 44.0),
                        ),
                    },
                    _purpose("centerline_detail", "swept_source"),
                ),
                "u_start": 0.08,
                "u_end": 0.92,
            },
            purpose=_purpose("centerline_detail", "carved_centerline_sweep"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="weapon.end_cap",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "weapon_pommel",
                    {
                        "profile_points": (
                            (0.0, -2.8),
                            (3.8, -2.2),
                            (4.4, 0.0),
                            (3.8, 2.2),
                            (0.0, 2.8),
                        ),
                        "axis": "z",
                        "center": (0.0, -25.0, -30.0),
                    },
                    _purpose("pommel_or_end_cap", "lathed_source"),
                ),
                "width_cm": 0.25,
                "segments": 2,
            },
            purpose=_purpose("pommel_or_end_cap", "polybeveled_lathed_cap"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="weapon.hardpoints",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="weapon_socket_plate",
                        width_cm=5.0,
                        height_cm=3.0,
                        thickness_cm=1.2,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("socket_or_hardpoint", "socket_plate_source"),
                    ),
                    width_cm=0.25,
                    segments=2,
                    target="weapon_socket_plate",
                    purpose=_purpose("socket_or_hardpoint", "polybeveled_socket_source"),
                ),
                "points": (
                    (-6.5, 8.0, -12.0),
                    (6.5, 8.0, -12.0),
                    (-5.0, 10.0, 22.0),
                    (5.0, 10.0, 22.0),
                ),
            },
            purpose=_purpose("socket_or_hardpoint", "copy_socket_plates"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="weapon.fasteners",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "weapon_fastener",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("fasteners", "rivet_source"),
                ),
                "points": (
                    (-10.0, -2.0, -34.5),
                    (10.0, -2.0, -34.5),
                    (-5.0, 8.5, -16.0),
                    (5.0, 8.5, -16.0),
                    (-4.0, 9.5, 16.0),
                    (4.0, 9.5, 16.0),
                ),
            },
            purpose=_purpose("fasteners", "copy_weapon_rivets"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="weapon.marking_zone",
            parameters={
                "profile_polygon": _rect_profile(12.0, 3.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 15.2, -4.0),
            },
            purpose=_purpose("marking_or_decal_zone", "raised_marking_plate"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="weapon.contact_edges",
            parameters={"amount": 0.2},
            purpose=_purpose("edge_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.weapon_primary_body", "primary_volume"),
        _node("recipe.weapon_grip", "handle"),
        _node("recipe.weapon_guard", "guard"),
        _node("recipe.weapon_active_edge", "rail"),
        _node("recipe.weapon_centerline_detail", "trim"),
        _node("recipe.weapon_end_cap", "mount"),
        _node("recipe.weapon_hardpoints", "socket"),
        _node("recipe.weapon_fasteners", "fastener"),
        _node("recipe.weapon_marking_zone", "decal_zone"),
        _node("recipe.weapon_edge_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="weapon_prop",
        family="weapon_prop",
        ops=ops,
    )
    return RecipeResult(
        family="weapon_prop",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _vehicle_prop_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="op.hull",
            target="vehicle.chassis",
            parameters={
                "sources": (
                    _source_op(
                        "solid.box",
                        "vehicle_chassis_lower",
                        {
                            "width_cm": _VEHICLE_WIDTH_CM,
                            "height_cm": _VEHICLE_HEIGHT_CM * 0.72,
                            "depth_cm": _VEHICLE_DEPTH_CM,
                            "center": (0.0, -2.0, 0.0),
                        },
                        _purpose("primary_chassis_or_hull", "lower_hull_source"),
                    ),
                    _source_op(
                        "solid.box",
                        "vehicle_chassis_front_shoulder",
                        {
                            "width_cm": _VEHICLE_WIDTH_CM * 0.72,
                            "height_cm": _VEHICLE_HEIGHT_CM * 0.88,
                            "depth_cm": _VEHICLE_DEPTH_CM * 0.32,
                            "center": (0.0, 4.0, -_VEHICLE_DEPTH_CM * 0.34),
                        },
                        _purpose("primary_chassis_or_hull", "front_shoulder_source"),
                    ),
                    _source_op(
                        "solid.box",
                        "vehicle_chassis_rear_shoulder",
                        {
                            "width_cm": _VEHICLE_WIDTH_CM * 0.82,
                            "height_cm": _VEHICLE_HEIGHT_CM * 0.80,
                            "depth_cm": _VEHICLE_DEPTH_CM * 0.30,
                            "center": (0.0, 2.0, _VEHICLE_DEPTH_CM * 0.32),
                        },
                        _purpose("primary_chassis_or_hull", "rear_shoulder_source"),
                    ),
                ),
            },
            purpose=_purpose("primary_chassis_or_hull", "kernel_hulled_chassis"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="vehicle.cabin",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "vehicle_cabin",
                    {
                        "width_cm": 46.0,
                        "height_cm": 30.0,
                        "depth_cm": 34.0,
                        "center": (0.0, 28.0, -20.0),
                    },
                    _purpose("cabin_or_control_zone", "box_source"),
                ),
                "width_cm": 1.8,
                "segments": 4,
            },
            purpose=_purpose("cabin_or_control_zone", "polybeveled_cabin"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="vehicle.motion_system",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "vehicle_wheel",
                    {
                        "major_radius_cm": 9.0,
                        "minor_radius_cm": 2.6,
                        "axis": "x",
                    },
                    _purpose("motion_system", "wheel_source"),
                ),
                "points": _wheel_points(),
            },
            purpose=_purpose("motion_system", "copy_four_wheels"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="vehicle.orientation",
            parameters={
                "profile_polygon": (
                    (-20.0, -6.0),
                    (20.0, -6.0),
                    (12.0, 6.0),
                    (-12.0, 6.0),
                ),
                "extrude_height_cm": 3.0,
                "axis": "z",
                "center": (0.0, 5.0, -68.0),
            },
            purpose=_purpose("front_back_orientation", "front_grille_plate"),
        ),
        ShapeOp(
            op="sop.boolean",
            target="vehicle.payload_zone",
            parameters={
                "operation": "subtract",
                "source": _panel_source(
                    target="vehicle_payload_bay_cut",
                    width_cm=50.0,
                    height_cm=18.0,
                    thickness_cm=4.0,
                    center=(0.0, 16.0, 30.0),
                    purpose=_purpose("cargo_or_payload_zone", "bay_cut_source"),
                ),
            },
            purpose=_purpose("cargo_or_payload_zone", "subtractive_bay"),
        ),
        ShapeOp(
            op="op.mirror",
            target="vehicle.access_rail",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "vehicle_side_access_rail",
                    {
                        "radius_cm": 1.0,
                        "path": (
                            (-36.0, 18.0, -36.0),
                            (-38.0, 20.0, 0.0),
                            (-36.0, 18.0, 36.0),
                        ),
                    },
                    _purpose("access_steps_or_handles", "side_access_rail_source"),
                ),
                "axis": "x",
                "include_source": True,
            },
            purpose=_purpose("access_steps_or_handles", "mirrored_side_access_rails"),
        ),
        ShapeOp(
            op="op.mirror",
            target="vehicle.lights",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "vehicle_light",
                    {"radius_cm": 3.0, "center": (22.0, 10.0, -69.5)},
                    _purpose("lights_or_sensors", "light_source"),
                ),
                "axis": "x",
                "include_source": True,
            },
            purpose=_purpose("lights_or_sensors", "mirror_front_lights"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="vehicle.fasteners",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "vehicle_fastener",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("mechanical_fasteners", "rivet_source"),
                ),
                "points": (
                    (-32.0, 20.0, -42.0),
                    (32.0, 20.0, -42.0),
                    (-32.0, 20.0, 42.0),
                    (32.0, 20.0, 42.0),
                    (-18.0, 34.0, -36.0),
                    (18.0, 34.0, -36.0),
                ),
            },
            purpose=_purpose("mechanical_fasteners", "copy_vehicle_rivets"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="vehicle.marking_zone",
            parameters={
                "profile_polygon": _rect_profile(20.0, 6.0),
                "extrude_height_cm": 0.35,
                "axis": "x",
                "center": (-43.5, 13.0, 12.0),
            },
            purpose=_purpose("marking_or_decal_zone", "side_marking_plate"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="vehicle.access_edges",
            parameters={"amount": 0.24},
            purpose=_purpose("edge_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.vehicle_chassis", "primary_volume"),
        _node("recipe.vehicle_cabin", "panel"),
        _node("recipe.vehicle_motion_system", "rail"),
        _node("recipe.vehicle_front_orientation", "trim"),
        _node("recipe.vehicle_payload_zone", "inset"),
        _node("recipe.vehicle_access_rail", "handle"),
        _node("recipe.vehicle_lights", "mount"),
        _node("recipe.vehicle_fasteners", "fastener"),
        _node("recipe.vehicle_marking_zone", "decal_zone"),
        _node("recipe.vehicle_edge_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="vehicle_prop",
        family="vehicle_prop",
        ops=ops,
    )
    return RecipeResult(
        family="vehicle_prop",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _furniture_prop_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="furniture.contact_surface",
            parameters={
                "source": _panel_source(
                    target="furniture_top",
                    width_cm=_FURNITURE_WIDTH_CM,
                    height_cm=_FURNITURE_DEPTH_CM,
                    thickness_cm=4.0,
                    center=(0.0, 2.0, 0.0),
                    purpose=_purpose("primary_contact_surface", "top_source"),
                ),
                "width_cm": 1.0,
                "segments": 4,
            },
            purpose=_purpose("primary_contact_surface", "polybeveled_top"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="furniture.supports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "furniture_leg",
                    {
                        "profile_points": (
                            (0.0, -18.0),
                            (2.2, -16.0),
                            (1.7, 16.0),
                            (0.0, 18.0),
                        ),
                        "axis": "y",
                    },
                    _purpose("support_structure", "lathed_leg_source"),
                ),
                "points": _furniture_leg_points(),
            },
            purpose=_purpose("support_structure", "copy_four_legs"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="furniture.back_or_storage",
            parameters={
                "source": _panel_source(
                    target="furniture_back_panel",
                    width_cm=_FURNITURE_WIDTH_CM - 10.0,
                    height_cm=28.0,
                    thickness_cm=3.0,
                    center=(0.0, 22.0, _FURNITURE_DEPTH_CM * 0.5 + 2.0),
                    purpose=_purpose("back_or_storage_volume", "back_source"),
                ),
                "width_cm": 0.65,
                "segments": 3,
            },
            purpose=_purpose("back_or_storage_volume", "polybeveled_back_panel"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="furniture.trim",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="furniture_edge_band",
                        width_cm=_FURNITURE_WIDTH_CM,
                        height_cm=2.2,
                        thickness_cm=1.2,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("trim_or_edge_band", "band_source"),
                    ),
                    width_cm=0.25,
                    segments=2,
                    target="furniture_edge_band",
                    purpose=_purpose("trim_or_edge_band", "polybeveled_band_source"),
                ),
                "points": (
                    (0.0, 5.0, -_FURNITURE_DEPTH_CM * 0.5 - 1.0),
                    (0.0, 5.0, _FURNITURE_DEPTH_CM * 0.5 + 1.0),
                ),
            },
            purpose=_purpose("trim_or_edge_band", "copy_front_back_bands"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="furniture.handle",
            parameters={
                "radius_cm": 0.6,
                "path": ((-10.0, 8.0, -23.5), (0.0, 11.0, -25.0), (10.0, 8.0, -23.5)),
            },
            purpose=_purpose("handle_or_pull", "curved_pull"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="furniture.fasteners",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "furniture_fastener",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("fasteners_or_joinery", "peg_source"),
                ),
                "points": (
                    (-34.0, 5.0, -22.8),
                    (34.0, 5.0, -22.8),
                    (-34.0, 5.0, 22.8),
                    (34.0, 5.0, 22.8),
                ),
            },
            purpose=_purpose("fasteners_or_joinery", "copy_joinery_pegs"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="furniture.soft_volume",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "furniture_cushion",
                    {
                        "width_cm": _FURNITURE_WIDTH_CM - 12.0,
                        "height_cm": 7.0,
                        "depth_cm": _FURNITURE_DEPTH_CM - 8.0,
                        "center": (0.0, 8.0, 0.0),
                    },
                    _purpose("cushion_or_soft_volume", "box_source"),
                ),
                "width_cm": 2.5,
                "segments": 6,
            },
            purpose=_purpose("cushion_or_soft_volume", "softened_cushion"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="furniture.feet",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "furniture_foot_pad",
                    {"radius_cm": 3.0},
                    _purpose("floor_contact_or_feet", "foot_source"),
                ),
                "points": _furniture_leg_points(),
            },
            purpose=_purpose("floor_contact_or_feet", "copy_foot_pads"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="furniture.label_zone",
            parameters={
                "profile_polygon": _rect_profile(10.0, 3.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (24.0, 9.0, -24.5),
            },
            purpose=_purpose("label_or_decal_zone", "maker_mark_plate"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="furniture.contact_edges",
            parameters={"amount": 0.12},
            purpose=_purpose("edge_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.furniture_contact_surface", "primary_volume"),
        _node("recipe.furniture_supports", "rail"),
        _node("recipe.furniture_back_or_storage", "panel"),
        _node("recipe.furniture_trim", "trim"),
        _node("recipe.furniture_handle", "handle"),
        _node("recipe.furniture_fasteners", "fastener"),
        _node("recipe.furniture_soft_volume", "panel"),
        _node("recipe.furniture_feet", "mount"),
        _node("recipe.furniture_label_zone", "decal_zone"),
        _node("recipe.furniture_edge_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="furniture_prop",
        family="furniture_prop",
        ops=ops,
    )
    return RecipeResult(
        family="furniture_prop",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _natural_form_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="natural.primary_mass",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "natural_primary_mass",
                    {
                        "width_cm": _NATURAL_MASS_WIDTH_CM,
                        "height_cm": _NATURAL_MASS_HEIGHT_CM,
                        "depth_cm": _NATURAL_MASS_DEPTH_CM,
                    },
                    _purpose("organic_primary_mass", "box_source"),
                ),
                "width_cm": 6.5,
                "segments": 8,
            },
            purpose=_purpose("organic_primary_mass", "soft_asymmetric_mass"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="natural.growth_runners",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "natural_root_runner",
                    {
                        "radius_cm": 1.5,
                        "path": ((-24.0, 2.0, -24.0), (-8.0, 5.0, -6.0), (16.0, 3.0, 22.0)),
                    },
                    _purpose("swept_growth_or_rooting", "runner_source"),
                ),
                "points": ((0.0, 0.0, 0.0), (18.0, 4.0, -18.0), (-20.0, 3.0, 14.0)),
            },
            purpose=_purpose("swept_growth_or_rooting", "copy_growth_runners"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="natural.secondary_clusters",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "natural_lobe",
                    {"radius_cm": 7.0},
                    _purpose("clustered_secondary_forms", "lobe_source"),
                ),
                "points": _natural_scatter_points(),
            },
            purpose=_purpose("clustered_secondary_forms", "copy_lobed_clusters"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="natural.strata",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "natural_strata_line",
                    {
                        "radius_cm": 0.45,
                        "path": ((-36.0, 12.0, -22.0), (-4.0, 15.0, -26.0), (34.0, 11.0, -18.0)),
                    },
                    _purpose("surface_strata_or_bark", "strata_source"),
                ),
                "points": ((0.0, 0.0, 0.0), (0.0, 7.0, 18.0), (0.0, -5.0, 26.0)),
            },
            purpose=_purpose("surface_strata_or_bark", "copy_contour_lines"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="natural.ground_transition",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "natural_ground_skirt",
                    {
                        "width_cm": _NATURAL_MASS_WIDTH_CM + 16.0,
                        "height_cm": 5.0,
                        "depth_cm": _NATURAL_MASS_DEPTH_CM + 12.0,
                        "center": (0.0, -20.0, 0.0),
                    },
                    _purpose("ground_contact_transition", "skirt_source"),
                ),
                "width_cm": 4.0,
                "segments": 6,
            },
            purpose=_purpose("ground_contact_transition", "soft_ground_skirt"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="natural.asymmetric_break",
            parameters={
                "profile_polygon": _leaf_profile(),
                "extrude_height_cm": 1.0,
                "axis": "y",
                "center": (30.0, 18.0, -8.0),
            },
            purpose=_purpose("asymmetric_silhouette_breaks", "leafy_side_lobe"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="natural.detail_scatter",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "natural_pebble",
                    {"radius_cm": 2.2},
                    _purpose("small_detail_scatter", "pebble_source"),
                ),
                "points": (
                    (-42.0, -14.0, -24.0),
                    (-20.0, -15.0, 28.0),
                    (18.0, -13.0, 32.0),
                    (38.0, -15.0, -12.0),
                    (2.0, -12.0, -34.0),
                ),
            },
            purpose=_purpose("small_detail_scatter", "copy_pebbles"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="natural.material_zone",
            parameters={
                "profile_polygon": _rect_profile(22.0, 8.0),
                "extrude_height_cm": 0.35,
                "axis": "y",
                "center": (-16.0, 20.0, 10.0),
            },
            purpose=_purpose("material_zone_variation", "moss_patch"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="natural.eroded_edges",
            parameters={"amount": 0.3},
            purpose=_purpose("weathering_or_erosion_masks", "erosion_edges"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="natural.scale_anchors",
            parameters={
                "source": _source_op(
                    "sop.polyextrude",
                    "natural_leaf_anchor",
                    {
                        "profile_polygon": _leaf_profile(),
                        "extrude_height_cm": 0.35,
                        "axis": "y",
                    },
                    _purpose("scale_anchor", "leaf_source"),
                ),
                "points": ((-30.0, -11.0, 18.0), (24.0, -10.0, -22.0), (4.0, -8.0, 34.0)),
            },
            purpose=_purpose("scale_anchor", "copy_leaf_anchors"),
        ),
    )
    nodes = (
        _node("recipe.natural_primary_mass", "primary_volume"),
        _node("recipe.natural_growth_runners", "rail"),
        _node("recipe.natural_secondary_clusters", "mount"),
        _node("recipe.natural_strata", "trim"),
        _node("recipe.natural_ground_transition", "mount"),
        _node("recipe.natural_asymmetric_break", "panel"),
        _node("recipe.natural_detail_scatter", "fastener"),
        _node("recipe.natural_material_zone", "material_zone"),
        _node("recipe.natural_erosion_wear", "wear_zone"),
        _node("recipe.natural_scale_anchor", "decal_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="natural_form",
        family="natural_form",
        ops=ops,
    )
    return RecipeResult(
        family="natural_form",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _environment_architecture_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="architecture.foundation",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "architecture_foundation",
                    {
                        "width_cm": _ARCH_WIDTH_CM,
                        "height_cm": 8.0,
                        "depth_cm": _ARCH_DEPTH_CM,
                        "center": (0.0, -4.0, 0.0),
                    },
                    _purpose("floor_or_foundation", "slab_source"),
                ),
                "width_cm": 1.2,
                "segments": 3,
            },
            purpose=_purpose("floor_or_foundation", "polybeveled_slab"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="architecture.walls",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="architecture_wall_panel",
                        width_cm=_ARCH_WIDTH_CM,
                        height_cm=_ARCH_HEIGHT_CM,
                        thickness_cm=4.0,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("wall_or_enclosure", "wall_source"),
                    ),
                    width_cm=0.55,
                    segments=3,
                    target="architecture_wall_panel",
                    purpose=_purpose("wall_or_enclosure", "polybeveled_wall_source"),
                ),
                "points": (
                    (0.0, 36.0, -_ARCH_DEPTH_CM * 0.5),
                    (0.0, 36.0, _ARCH_DEPTH_CM * 0.5),
                ),
            },
            purpose=_purpose("wall_or_enclosure", "copy_front_back_walls"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="architecture.openings",
            parameters={
                "source": _source_op(
                    "sop.boolean",
                    "architecture_opening_cut",
                    {
                        "operation": "subtract",
                        "source": _panel_source(
                            target="architecture_opening_panel",
                            width_cm=18.0,
                            height_cm=28.0,
                            thickness_cm=1.2,
                            center=(0.0, 0.0, 0.0),
                            purpose=_purpose("opening_system", "opening_source"),
                        ),
                    },
                    _purpose("opening_system", "subtractive_opening_source"),
                ),
                "points": ((-32.0, 34.0, -47.0), (0.0, 34.0, -47.0), (32.0, 34.0, -47.0)),
            },
            purpose=_purpose("opening_system", "copy_front_openings"),
        ),
        ShapeOp(
            op="sop.loft",
            target="architecture.roof",
            parameters={
                "sections": (
                    {
                        "center": (0.0, 76.0, -_ARCH_DEPTH_CM * 0.5),
                        "profile_polygon": ((-_ARCH_WIDTH_CM * 0.5, 0.0), (0.0, 20.0), (_ARCH_WIDTH_CM * 0.5, 0.0)),
                    },
                    {
                        "center": (0.0, 76.0, _ARCH_DEPTH_CM * 0.5),
                        "profile_polygon": ((-_ARCH_WIDTH_CM * 0.5, 0.0), (0.0, 20.0), (_ARCH_WIDTH_CM * 0.5, 0.0)),
                    },
                ),
            },
            purpose=_purpose("roof_or_cover", "lofted_roof_envelope"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="architecture.vertical_supports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "architecture_column",
                    {
                        "profile_points": ((0.0, -34.0), (3.8, -30.0), (3.2, 30.0), (0.0, 34.0)),
                        "axis": "y",
                    },
                    _purpose("vertical_supports", "column_source"),
                ),
                "points": _arch_column_points(),
            },
            purpose=_purpose("vertical_supports", "copy_corner_columns"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="architecture.access",
            parameters={
                "radius_cm": 1.2,
                "path": ((-_ARCH_WIDTH_CM * 0.45, 12.0, -52.0), (0.0, 14.0, -54.0), (_ARCH_WIDTH_CM * 0.45, 12.0, -52.0)),
            },
            purpose=_purpose("circulation_or_access", "front_access_rail"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="architecture.facade_trim",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="architecture_trim_band",
                        width_cm=_ARCH_WIDTH_CM,
                        height_cm=3.0,
                        thickness_cm=1.1,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("facade_trim_or_banding", "band_source"),
                    ),
                    width_cm=0.25,
                    segments=2,
                    target="architecture_trim_band",
                    purpose=_purpose("facade_trim_or_banding", "polybeveled_band_source"),
                ),
                "points": ((0.0, 28.0, -47.0), (0.0, 60.0, -47.0), (0.0, 28.0, 47.0), (0.0, 60.0, 47.0)),
            },
            purpose=_purpose("facade_trim_or_banding", "copy_trim_bands"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="architecture.modular_bays",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="architecture_bay_frame",
                        width_cm=20.0,
                        height_cm=42.0,
                        thickness_cm=1.4,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("modular_bays", "bay_frame_source"),
                    ),
                    width_cm=0.35,
                    segments=2,
                    target="architecture_bay_frame",
                    purpose=_purpose("modular_bays", "polybeveled_bay_frame_source"),
                ),
                "points": ((-42.0, 38.0, -48.0), (0.0, 38.0, -48.0), (42.0, 38.0, -48.0)),
            },
            purpose=_purpose("modular_bays", "copy_front_bay_frames"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="architecture.signage_zone",
            parameters={
                "profile_polygon": _rect_profile(26.0, 7.0),
                "extrude_height_cm": 0.35,
                "axis": "z",
                "center": (0.0, 66.0, -48.5),
            },
            purpose=_purpose("lighting_or_signage_zone", "front_signage_plate"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="architecture.weathered_edges",
            parameters={"amount": 0.2},
            purpose=_purpose("weathering_or_edge_wear", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.architecture_foundation", "primary_volume"),
        _node("recipe.architecture_walls", "panel"),
        _node("recipe.architecture_openings", "inset"),
        _node("recipe.architecture_roof", "frame"),
        _node("recipe.architecture_columns", "rail"),
        _node("recipe.architecture_access", "handle"),
        _node("recipe.architecture_trim", "trim"),
        _node("recipe.architecture_bays", "frame"),
        _node("recipe.architecture_signage", "decal_zone"),
        _node("recipe.architecture_weathering", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="environment_architecture",
        family="environment_architecture",
        ops=ops,
    )
    return RecipeResult(
        family="environment_architecture",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _lighting_prop_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="lighting.base",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "lighting_base",
                    {
                        "width_cm": _LIGHTING_WIDTH_CM,
                        "height_cm": 8.0,
                        "depth_cm": _LIGHTING_DEPTH_CM,
                        "center": (0.0, 4.0, 0.0),
                    },
                    _purpose("base_or_mount", "box_source"),
                ),
                "width_cm": 1.2,
                "segments": 4,
            },
            purpose=_purpose("base_or_mount", "polybeveled_mount"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="lighting.armature",
            parameters={
                "radius_cm": 1.25,
                "path": (
                    (0.0, 8.0, 0.0),
                    (0.0, _LIGHTING_HEIGHT_CM - 24.0, 0.0),
                    (0.0, _LIGHTING_HEIGHT_CM - 16.0, -8.0),
                ),
            },
            purpose=_purpose("support_or_armature", "bent_support_arm"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="lighting.emitters",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "lighting_emitter_lens",
                    {"radius_cm": 4.0},
                    _purpose("emitter_or_lens", "lens_source"),
                ),
                "points": (
                    (-8.0, _LIGHTING_HEIGHT_CM - 15.5, -10.0),
                    (0.0, _LIGHTING_HEIGHT_CM - 14.0, -10.5),
                    (8.0, _LIGHTING_HEIGHT_CM - 15.5, -10.0),
                ),
            },
            purpose=_purpose("emitter_or_lens", "copy_lenses"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="lighting.housing",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "lighting_emitter_rim",
                    {
                        "major_radius_cm": 13.0,
                        "minor_radius_cm": 1.6,
                        "axis": "z",
                        "center": (0.0, _LIGHTING_HEIGHT_CM - 16.0, -10.0),
                    },
                    _purpose("housing_or_shade", "torus_source"),
                ),
                "width_cm": 0.2,
                "segments": 2,
            },
            purpose=_purpose("housing_or_shade", "polybeveled_lens_rim"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="lighting.power_route",
            parameters={
                "radius_cm": 0.55,
                "path": (
                    (-4.0, 7.0, 4.0),
                    (-7.0, 34.0, 5.0),
                    (-5.0, 64.0, -4.0),
                    (0.0, _LIGHTING_HEIGHT_CM - 17.0, -8.0),
                ),
            },
            purpose=_purpose("power_or_cable_route", "visible_power_cable"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="lighting.service_plate",
            parameters={
                "source": _panel_source(
                    target="lighting_service_plate",
                    width_cm=14.0,
                    height_cm=8.0,
                    thickness_cm=0.7,
                    center=(0.0, 30.0, -12.5),
                    purpose=_purpose("control_or_service_plate", "plate_source"),
                ),
                "width_cm": 0.35,
                "segments": 2,
            },
            purpose=_purpose("control_or_service_plate", "polybeveled_service_plate"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="lighting.signage",
            parameters={
                "profile_polygon": _rect_profile(24.0, 7.0),
                "extrude_height_cm": 0.35,
                "axis": "z",
                "center": (0.0, _LIGHTING_HEIGHT_CM - 34.0, -13.0),
            },
            purpose=_purpose("signage_or_marker_face", "raised_marker_face"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="lighting.fasteners",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "lighting_fastener",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("fasteners", "rivet_source"),
                ),
                "points": (
                    (-12.0, 5.0, -8.0),
                    (12.0, 5.0, -8.0),
                    (-8.0, 30.0, -13.0),
                    (8.0, 30.0, -13.0),
                    (-11.0, _LIGHTING_HEIGHT_CM - 31.0, -13.4),
                    (11.0, _LIGHTING_HEIGHT_CM - 31.0, -13.4),
                ),
            },
            purpose=_purpose("fasteners", "copy_lighting_fasteners"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="lighting.protective_guard",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "lighting_guard_rib",
                    {
                        "radius_cm": 0.42,
                        "path": (
                            (0.0, _LIGHTING_HEIGHT_CM - 25.0, -11.2),
                            (0.0, _LIGHTING_HEIGHT_CM - 16.0, -14.0),
                            (0.0, _LIGHTING_HEIGHT_CM - 7.0, -11.2),
                        ),
                    },
                    _purpose("protective_guard_or_cage", "rib_source"),
                ),
                "points": _lighting_guard_points(),
            },
            purpose=_purpose("protective_guard_or_cage", "copy_guard_ribs"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="lighting.handled_edges",
            parameters={"amount": 0.16, "soot_bias": 0.35},
            purpose=_purpose("soot_or_edge_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.lighting_base", "mount"),
        _node("recipe.lighting_armature", "rail"),
        _node("recipe.lighting_emitters", "material_zone"),
        _node("recipe.lighting_housing", "guard"),
        _node("recipe.lighting_power_route", "socket"),
        _node("recipe.lighting_service_plate", "panel"),
        _node("recipe.lighting_signage", "decal_zone"),
        _node("recipe.lighting_fasteners", "fastener"),
        _node("recipe.lighting_protective_guard", "guard"),
        _node("recipe.lighting_edge_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="lighting_prop",
        family="lighting_prop",
        ops=ops,
    )
    return RecipeResult(
        family="lighting_prop",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _machine_console_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="machine.body",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "machine_body",
                    {
                        "width_cm": _MACHINE_WIDTH_CM,
                        "height_cm": _MACHINE_HEIGHT_CM,
                        "depth_cm": _MACHINE_DEPTH_CM,
                    },
                    _purpose("primary_machine_body", "box_source"),
                ),
                "width_cm": 2.4,
                "segments": 5,
            },
            purpose=_purpose("primary_machine_body", "polybeveled_chassis"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="machine.control_face",
            parameters={
                "source": _panel_source(
                    target="machine_control_face",
                    width_cm=58.0,
                    height_cm=24.0,
                    thickness_cm=1.6,
                    center=(0.0, 42.0, -22.0),
                    purpose=_purpose("control_face_or_panel", "panel_source"),
                ),
                "width_cm": 0.8,
                "segments": 3,
            },
            purpose=_purpose("control_face_or_panel", "polybeveled_control_face"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="machine.display",
            parameters={
                "profile_polygon": _rect_profile(30.0, 11.0),
                "extrude_height_cm": 0.35,
                "axis": "z",
                "center": (0.0, 51.0, -23.0),
            },
            purpose=_purpose("display_or_readout", "raised_screen_readout"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="machine.input_controls",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "machine_button",
                    {
                        "profile_points": (
                            (0.0, -1.2),
                            (2.0, -0.9),
                            (2.3, 0.0),
                            (2.0, 0.9),
                            (0.0, 1.2),
                        ),
                        "axis": "z",
                    },
                    _purpose("input_controls", "button_source"),
                ),
                "points": _console_button_points(),
            },
            purpose=_purpose("input_controls", "copy_buttons"),
        ),
        ShapeOp(
            op="sop.boolean",
            target="machine.service_access",
            parameters={
                "operation": "subtract",
                "source": _panel_source(
                    target="machine_service_hatch_cut",
                    width_cm=26.0,
                    height_cm=20.0,
                    thickness_cm=3.0,
                    center=(0.0, 14.0, -23.0),
                    purpose=_purpose("service_access_panel", "hatch_cut_source"),
                ),
            },
            purpose=_purpose("service_access_panel", "subtractive_service_hatch"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="machine.ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "machine_socket",
                    {
                        "profile_points": (
                            (0.0, -1.8),
                            (3.2, -1.4),
                            (3.6, 0.0),
                            (3.2, 1.4),
                            (0.0, 1.8),
                        ),
                        "axis": "z",
                    },
                    _purpose("ports_or_sockets", "socket_source"),
                ),
                "points": (
                    (-30.0, 12.0, -21.5),
                    (-30.0, 22.0, -21.5),
                    (30.0, 12.0, -21.5),
                    (30.0, 22.0, -21.5),
                ),
            },
            purpose=_purpose("ports_or_sockets", "copy_side_ports"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="machine.cooling",
            parameters={
                "source": _source_op(
                    "sop.boolean",
                    "machine_vent_slot",
                    {
                        "operation": "subtract",
                        "source": _panel_source(
                            target="machine_vent_slot_cut",
                            width_cm=20.0,
                            height_cm=1.4,
                            thickness_cm=2.6,
                            center=(0.0, 0.0, 0.0),
                            purpose=_purpose("cooling_or_ventilation", "slot_source"),
                        ),
                    },
                    _purpose("cooling_or_ventilation", "subtractive_slot_source"),
                ),
                "points": (
                    (0.0, 20.0, -23.0),
                    (0.0, 24.0, -23.0),
                    (0.0, 28.0, -23.0),
                    (0.0, 32.0, -23.0),
                ),
            },
            purpose=_purpose("cooling_or_ventilation", "copy_vent_slots"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="machine.cable_connections",
            parameters={
                "radius_cm": 1.05,
                "path": (
                    (-24.0, -16.0, 20.0),
                    (-36.0, -22.0, 32.0),
                    (-44.0, -26.0, 44.0),
                ),
            },
            purpose=_purpose("cable_or_pipe_connections", "service_cable"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="machine.warning_marking",
            parameters={
                "profile_polygon": _rect_profile(22.0, 5.0),
                "extrude_height_cm": 0.3,
                "axis": "z",
                "center": (0.0, 4.0, -23.2),
            },
            purpose=_purpose("status_or_warning_markings", "status_plate"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="machine.service_edges",
            parameters={"amount": 0.22},
            purpose=_purpose("service_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.machine_body", "primary_volume"),
        _node("recipe.machine_control_face", "panel"),
        _node("recipe.machine_display", "material_zone"),
        _node("recipe.machine_input_controls", "fastener"),
        _node("recipe.machine_service_access", "inset"),
        _node("recipe.machine_ports", "socket"),
        _node("recipe.machine_cooling", "guard"),
        _node("recipe.machine_cable_connections", "rail"),
        _node("recipe.machine_warning_marking", "decal_zone"),
        _node("recipe.machine_service_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="machine_console",
        family="machine_console",
        ops=ops,
    )
    return RecipeResult(
        family="machine_console",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _portal_relic_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="portal.base",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "portal_plinth",
                    {
                        "width_cm": _PORTAL_WIDTH_CM,
                        "height_cm": 12.0,
                        "depth_cm": _PORTAL_DEPTH_CM,
                        "center": (0.0, 6.0, 0.0),
                    },
                    _purpose("anchor_base_or_plinth", "box_source"),
                ),
                "width_cm": 2.2,
                "segments": 5,
            },
            purpose=_purpose("anchor_base_or_plinth", "polybeveled_plinth"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="portal.frame",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "portal_side_frame",
                    {
                        "radius_cm": 2.2,
                        "path": (
                            (0.0, 12.0, 0.0),
                            (0.0, _PORTAL_HEIGHT_CM * 0.55, -3.0),
                            (0.0, _PORTAL_HEIGHT_CM - 16.0, 0.0),
                        ),
                    },
                    _purpose("frame_or_vertical_core", "side_frame_source"),
                ),
                "points": (
                    (-_PORTAL_WIDTH_CM * 0.38, 0.0, 0.0),
                    (_PORTAL_WIDTH_CM * 0.38, 0.0, 0.0),
                ),
            },
            purpose=_purpose("frame_or_vertical_core", "copy_vertical_frames"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="portal.active_threshold",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "portal_active_ring",
                    {
                        "major_radius_cm": 28.0,
                        "minor_radius_cm": 2.8,
                        "axis": "z",
                        "center": (0.0, 66.0, -_PORTAL_DEPTH_CM * 0.5),
                    },
                    _purpose("threshold_or_active_center", "torus_source"),
                ),
                "width_cm": 0.25,
                "segments": 3,
            },
            purpose=_purpose("threshold_or_active_center", "polybeveled_active_ring"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="portal.power_nodes",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "portal_keystone",
                    {
                        "profile_points": (
                            (0.0, -4.0),
                            (4.0, -3.0),
                            (5.2, 0.0),
                            (4.0, 3.0),
                            (0.0, 4.0),
                        ),
                        "axis": "z",
                    },
                    _purpose("power_nodes_or_keystones", "keystone_source"),
                ),
                "points": _portal_node_points(),
            },
            purpose=_purpose("power_nodes_or_keystones", "copy_keystones"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="portal.symmetry_bands",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "portal_radial_band",
                    {
                        "radius_cm": 0.7,
                        "path": ((-18.0, 0.0, 0.0), (0.0, 0.0, -2.0), (18.0, 0.0, 0.0)),
                    },
                    _purpose("radial_or_symmetric_layout", "band_source"),
                ),
                "points": (
                    (0.0, 46.0, -_PORTAL_DEPTH_CM * 0.5),
                    (0.0, 66.0, -_PORTAL_DEPTH_CM * 0.5),
                    (0.0, 86.0, -_PORTAL_DEPTH_CM * 0.5),
                ),
            },
            purpose=_purpose("radial_or_symmetric_layout", "copy_radial_bands"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="portal.rune_band",
            parameters={
                "profile_polygon": _rect_profile(54.0, 5.0),
                "extrude_height_cm": 0.35,
                "axis": "z",
                "center": (0.0, 18.0, -_PORTAL_DEPTH_CM * 0.5 - 0.6),
            },
            purpose=_purpose("runes_or_inscriptions", "raised_rune_band"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="portal.attachment_mounts",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="portal_offering_mount",
                        width_cm=10.0,
                        height_cm=5.0,
                        thickness_cm=2.0,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("offering_or_attachment_mounts", "mount_source"),
                    ),
                    width_cm=0.45,
                    segments=2,
                    target="portal_offering_mount",
                    purpose=_purpose("offering_or_attachment_mounts", "polybeveled_mount_source"),
                ),
                "points": ((-34.0, 22.0, -16.0), (34.0, 22.0, -16.0)),
            },
            purpose=_purpose("offering_or_attachment_mounts", "copy_mounts"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="portal.energy_conduit",
            parameters={
                "radius_cm": 0.9,
                "path": (
                    (-34.0, 22.0, -15.5),
                    (-20.0, 45.0, -17.5),
                    (0.0, 66.0, -18.0),
                    (20.0, 45.0, -17.5),
                    (34.0, 22.0, -15.5),
                ),
            },
            purpose=_purpose("conduits_or_energy_paths", "swept_energy_path"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="portal.environment_contact",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "portal_rubble",
                    {
                        "width_cm": 8.0,
                        "height_cm": 3.0,
                        "depth_cm": 6.0,
                        "corner_radii_cm": (1.2, 0.8, 1.6, 0.9, 1.0, 1.4, 0.7, 1.1),
                    },
                    _purpose("environment_contact", "rubble_source"),
                ),
                "points": ((-40.0, 2.0, 16.0), (-18.0, 1.5, 18.0), (22.0, 2.2, 17.0), (42.0, 1.4, 12.0)),
            },
            purpose=_purpose("environment_contact", "copy_ground_rubble"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="portal.aged_edges",
            parameters={"amount": 0.28, "patina_bias": 0.4},
            purpose=_purpose("age_or_aura_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.portal_plinth", "primary_volume"),
        _node("recipe.portal_frame", "frame"),
        _node("recipe.portal_active_threshold", "material_zone"),
        _node("recipe.portal_power_nodes", "socket"),
        _node("recipe.portal_symmetry_bands", "trim"),
        _node("recipe.portal_rune_band", "decal_zone"),
        _node("recipe.portal_attachment_mounts", "mount"),
        _node("recipe.portal_energy_conduit", "rail"),
        _node("recipe.portal_environment_contact", "mount"),
        _node("recipe.portal_age_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="portal_relic",
        family="portal_relic",
        ops=ops,
    )
    return RecipeResult(
        family="portal_relic",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _tool_prop_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="tool.body",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "tool_body",
                    {
                        "width_cm": _TOOL_WIDTH_CM,
                        "height_cm": _TOOL_DEPTH_CM,
                        "depth_cm": _TOOL_LENGTH_CM,
                    },
                    _purpose("primary_tool_body", "box_source"),
                ),
                "width_cm": 1.1,
                "segments": 4,
            },
            purpose=_purpose("primary_tool_body", "polybeveled_body"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="tool.grip",
            parameters={
                "radius_cm": 2.2,
                "path": ((0.0, -2.0, -38.0), (0.0, -3.0, -24.0), (0.0, -2.0, -10.0)),
            },
            purpose=_purpose("grip_or_handle", "swept_grip"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="tool.working_head",
            parameters={
                "profile_polygon": (
                    (-15.0, -5.0),
                    (15.0, -5.0),
                    (18.0, 0.0),
                    (10.0, 7.0),
                    (-10.0, 7.0),
                    (-18.0, 0.0),
                ),
                "extrude_height_cm": 7.0,
                "axis": "y",
                "center": (0.0, 0.0, 36.0),
            },
            purpose=_purpose("working_head_or_bit", "shaped_working_head"),
        ),
        ShapeOp(
            op="sop.carve",
            target="tool.spine",
            parameters={
                "source": _source_op(
                    "solid.swept_profile",
                    "tool_spine",
                    {
                        "cross_section": _rect_profile(3.0, 2.0),
                        "sweep_path": ((0.0, 3.0, -36.0), (0.0, 3.5, 0.0), (0.0, 3.0, 38.0)),
                    },
                    _purpose("shaft_or_spine", "swept_source"),
                ),
                "u_start": 0.04,
                "u_end": 0.96,
            },
            purpose=_purpose("shaft_or_spine", "carved_spine"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="tool.guard",
            parameters={
                "source": _panel_source(
                    target="tool_hand_stop",
                    width_cm=24.0,
                    height_cm=5.0,
                    thickness_cm=2.4,
                    center=(0.0, 0.0, -8.0),
                    purpose=_purpose("guard_or_stop", "guard_source"),
                ),
                "width_cm": 0.45,
                "segments": 3,
            },
            purpose=_purpose("guard_or_stop", "polybeveled_hand_stop"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="tool.adjustment_joint",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "tool_adjustment_knob",
                    {
                        "profile_points": (
                            (0.0, -2.8),
                            (3.5, -2.2),
                            (4.2, 0.0),
                            (3.5, 2.2),
                            (0.0, 2.8),
                        ),
                        "axis": "y",
                        "center": (0.0, 5.2, 12.0),
                    },
                    _purpose("adjustment_or_joint", "knob_source"),
                ),
                "width_cm": 0.2,
                "segments": 2,
            },
            purpose=_purpose("adjustment_or_joint", "polybeveled_knob"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="tool.attachment_sockets",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "tool_socket",
                    {
                        "profile_points": (
                            (0.0, -1.6),
                            (2.8, -1.2),
                            (3.2, 0.0),
                            (2.8, 1.2),
                            (0.0, 1.6),
                        ),
                        "axis": "z",
                    },
                    _purpose("sockets_or_attachment_points", "socket_source"),
                ),
                "points": ((-8.5, 0.0, 18.0), (8.5, 0.0, 18.0)),
            },
            purpose=_purpose("sockets_or_attachment_points", "copy_sockets"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="tool.fasteners",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "tool_fastener",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("fasteners", "rivet_source"),
                ),
                "points": _tool_fastener_points(),
            },
            purpose=_purpose("fasteners", "copy_tool_fasteners"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="tool.marking_zone",
            parameters={
                "profile_polygon": _rect_profile(18.0, 3.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 4.6, -18.0),
            },
            purpose=_purpose("marking_or_scale_zone", "raised_scale_plate"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="tool.contact_edges",
            parameters={"amount": 0.24},
            purpose=_purpose("contact_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.tool_body", "primary_volume"),
        _node("recipe.tool_grip", "handle"),
        _node("recipe.tool_working_head", "guard"),
        _node("recipe.tool_spine", "rail"),
        _node("recipe.tool_guard", "guard"),
        _node("recipe.tool_adjustment_joint", "mount"),
        _node("recipe.tool_attachment_sockets", "socket"),
        _node("recipe.tool_fasteners", "fastener"),
        _node("recipe.tool_marking_zone", "decal_zone"),
        _node("recipe.tool_contact_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="tool_prop",
        family="tool_prop",
        ops=ops,
    )
    return RecipeResult(
        family="tool_prop",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _modular_kit_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="kit.tile_body",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "kit_tile_body",
                    {
                        "width_cm": _KIT_TILE_WIDTH_CM,
                        "height_cm": _KIT_TILE_HEIGHT_CM,
                        "depth_cm": _KIT_TILE_DEPTH_CM,
                    },
                    _purpose("canonical_tile_body", "box_source"),
                ),
                "width_cm": 1.6,
                "segments": 4,
            },
            purpose=_purpose("canonical_tile_body", "polybeveled_tile_body"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="kit.snap_edges",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "kit_snap_edge",
                    {
                        "radius_cm": 0.55,
                        "path": ((-24.0, 9.0, 0.0), (24.0, 9.0, 0.0)),
                    },
                    _purpose("snap_edges_or_bounds", "edge_source"),
                ),
                "points": ((0.0, 0.0, -32.0), (0.0, 0.0, 32.0), (-32.0, 0.0, 0.0), (32.0, 0.0, 0.0)),
            },
            purpose=_purpose("snap_edges_or_bounds", "copy_snap_edges"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="kit.connector_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "kit_connector_socket",
                    {
                        "profile_points": (
                            (0.0, -1.8),
                            (3.0, -1.4),
                            (3.4, 0.0),
                            (3.0, 1.4),
                            (0.0, 1.8),
                        ),
                        "axis": "z",
                    },
                    _purpose("connector_ports", "socket_source"),
                ),
                "points": _kit_connector_points(),
            },
            purpose=_purpose("connector_ports", "copy_connector_sockets"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="kit.orientation_marker",
            parameters={
                "profile_polygon": ((-6.0, -3.0), (3.0, -3.0), (8.0, 0.0), (3.0, 3.0), (-6.0, 3.0)),
                "extrude_height_cm": 0.3,
                "axis": "y",
                "center": (0.0, 8.5, -18.0),
            },
            purpose=_purpose("orientation_markers", "raised_direction_marker"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="kit.panel_breaks",
            parameters={
                "source": _source_op(
                    "sop.boolean",
                    "kit_reveal_cut",
                    {
                        "operation": "subtract",
                        "source": _panel_source(
                            target="kit_reveal_slot",
                            width_cm=42.0,
                            height_cm=1.2,
                            thickness_cm=2.0,
                            center=(0.0, 0.0, 0.0),
                            purpose=_purpose("seam_or_panel_breaks", "slot_source"),
                        ),
                    },
                    _purpose("seam_or_panel_breaks", "subtractive_slot_source"),
                ),
                "points": ((0.0, 10.0, -14.0), (0.0, 10.0, 14.0)),
            },
            purpose=_purpose("seam_or_panel_breaks", "copy_reveal_cuts"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="kit.variant_mounts",
            parameters={
                "source": _polybeveled_source(
                    _panel_source(
                        target="kit_variant_mount",
                        width_cm=12.0,
                        height_cm=6.0,
                        thickness_cm=1.4,
                        center=(0.0, 0.0, 0.0),
                        purpose=_purpose("variant_attachment_zones", "mount_source"),
                    ),
                    width_cm=0.35,
                    segments=2,
                    target="kit_variant_mount",
                    purpose=_purpose("variant_attachment_zones", "polybeveled_mount_source"),
                ),
                "points": ((-20.0, 10.0, -20.0), (20.0, 10.0, -20.0), (-20.0, 10.0, 20.0), (20.0, 10.0, 20.0)),
            },
            purpose=_purpose("variant_attachment_zones", "copy_mount_zones"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="kit.structural_ribs",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "kit_structural_rib",
                    {
                        "profile_points": _rect_profile(3.0, 10.0),
                        "height_cm": 48.0,
                        "axis": "z",
                    },
                    _purpose("structural_frame_or_ribs", "rib_source"),
                ),
                "points": ((-26.0, 8.5, 0.0), (26.0, 8.5, 0.0)),
            },
            purpose=_purpose("structural_frame_or_ribs", "copy_structural_ribs"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="kit.locator_pins",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "kit_locator_pin",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("fasteners_or_locator_pins", "pin_source"),
                ),
                "points": ((-26.0, 11.0, -26.0), (26.0, 11.0, -26.0), (-26.0, 11.0, 26.0), (26.0, 11.0, 26.0)),
            },
            purpose=_purpose("fasteners_or_locator_pins", "copy_locator_pins"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="kit.material_zone",
            parameters={
                "profile_polygon": _rect_profile(44.0, 7.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 10.0, 25.5),
            },
            purpose=_purpose("material_or_theme_zone", "theme_band"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="kit.repeat_edges",
            parameters={"amount": 0.18},
            purpose=_purpose("repeat_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.kit_tile_body", "primary_volume"),
        _node("recipe.kit_snap_edges", "trim"),
        _node("recipe.kit_connector_ports", "socket"),
        _node("recipe.kit_orientation_marker", "decal_zone"),
        _node("recipe.kit_panel_breaks", "inset"),
        _node("recipe.kit_variant_mounts", "mount"),
        _node("recipe.kit_structural_ribs", "frame"),
        _node("recipe.kit_locator_pins", "fastener"),
        _node("recipe.kit_material_zone", "material_zone"),
        _node("recipe.kit_repeat_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="modular_kit",
        family="modular_kit",
        ops=ops,
    )
    return RecipeResult(
        family="modular_kit",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _character_creature_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="character.body_mass",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "character_torso",
                    {
                        "width_cm": _CHARACTER_WIDTH_CM,
                        "height_cm": 34.0,
                        "depth_cm": _CHARACTER_DEPTH_CM,
                        "center": (0.0, 34.0, 0.0),
                    },
                    _purpose("primary_body_mass", "box_source"),
                ),
                "width_cm": 5.0,
                "segments": 8,
            },
            purpose=_purpose("primary_body_mass", "softened_torso"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="character.head",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "character_head",
                    {"radius_cm": 11.0, "center": (0.0, 60.0, 0.0)},
                    _purpose("head_or_sensor_cluster", "head_source"),
                ),
                "width_cm": 0.35,
                "segments": 3,
            },
            purpose=_purpose("head_or_sensor_cluster", "softened_head"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="character.limbs",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "character_limb",
                    {
                        "radius_cm": 2.2,
                        "path": ((0.0, 0.0, 0.0), (0.0, -15.0, 2.0), (0.0, -28.0, 0.0)),
                    },
                    _purpose("limbs_or_appendages", "limb_source"),
                ),
                "points": _character_limb_points(),
            },
            purpose=_purpose("limbs_or_appendages", "copy_limb_curves"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="character.joints",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "character_joint",
                    {"radius_cm": 3.2},
                    _purpose("joints_or_articulation", "joint_source"),
                ),
                "points": ((-13.0, 36.0, 0.0), (13.0, 36.0, 0.0), (-7.0, 16.0, 0.0), (7.0, 16.0, 0.0)),
            },
            purpose=_purpose("joints_or_articulation", "copy_joint_spheres"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="character.contact_points",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "character_contact_pad",
                    {
                        "width_cm": 8.0,
                        "height_cm": 3.0,
                        "depth_cm": 5.5,
                        "corner_radii_cm": (1.5, 1.2, 1.5, 1.2, 1.0, 1.4, 1.0, 1.4),
                    },
                    _purpose("hands_feet_or_contact_points", "pad_source"),
                ),
                "points": ((-8.0, -20.0, 1.0), (8.0, -20.0, 1.0), (-18.0, 8.0, 1.0), (18.0, 8.0, 1.0)),
            },
            purpose=_purpose("hands_feet_or_contact_points", "copy_contact_pads"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="character.face_details",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "character_eye",
                    {"radius_cm": 1.6},
                    _purpose("feature_marks_or_face_details", "eye_source"),
                ),
                "points": ((-3.8, 63.0, -9.6), (3.8, 63.0, -9.6)),
            },
            purpose=_purpose("feature_marks_or_face_details", "copy_eye_marks"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="character.silhouette_break",
            parameters={
                "profile_polygon": ((-5.0, -1.0), (0.0, 8.0), (5.0, -1.0)),
                "extrude_height_cm": 2.2,
                "axis": "z",
                "center": (0.0, 72.0, -1.0),
            },
            purpose=_purpose("silhouette_breaks_or_accessories", "crest_profile"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="character.pose_line",
            parameters={
                "radius_cm": 1.15,
                "path": ((0.0, 52.0, 8.0), (0.0, 32.0, 12.0), (0.0, 14.0, 18.0)),
            },
            purpose=_purpose("pose_line_or_balance", "spine_or_tail_curve"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="character.scale_anchor",
            parameters={
                "source": _panel_source(
                    target="character_belt_anchor",
                    width_cm=26.0,
                    height_cm=4.0,
                    thickness_cm=1.0,
                    center=(0.0, 33.0, -9.5),
                    purpose=_purpose("scale_anchor", "belt_source"),
                ),
                "width_cm": 0.25,
                "segments": 2,
            },
            purpose=_purpose("scale_anchor", "polybeveled_belt"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="character.contact_surfaces",
            parameters={"amount": 0.14},
            purpose=_purpose("contact_or_surface_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.character_body_mass", "primary_volume"),
        _node("recipe.character_head", "material_zone"),
        _node("recipe.character_limbs", "rail"),
        _node("recipe.character_joints", "hinge"),
        _node("recipe.character_contact_points", "mount"),
        _node("recipe.character_face_details", "decal_zone"),
        _node("recipe.character_silhouette_break", "guard"),
        _node("recipe.character_pose_line", "rail"),
        _node("recipe.character_scale_anchor", "trim"),
        _node("recipe.character_contact_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="character_creature",
        family="character_creature",
        ops=ops,
    )
    return RecipeResult(
        family="character_creature",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _set_dressing_prop_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="set_dressing.primary_volume",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "set_dressing_body",
                    {
                        "width_cm": _SET_DRESSING_WIDTH_CM,
                        "height_cm": _SET_DRESSING_HEIGHT_CM,
                        "depth_cm": _SET_DRESSING_DEPTH_CM,
                    },
                    _purpose("primary_prop_volume", "box_source"),
                ),
                "width_cm": 4.0,
                "segments": 7,
            },
            purpose=_purpose("primary_prop_volume", "softened_primary_prop"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="set_dressing.secondary_forms",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "set_dressing_secondary_bundle",
                    {"radius_cm": 5.0},
                    _purpose("secondary_scale_forms", "bundle_source"),
                ),
                "points": ((-13.0, 31.0, -8.0), (9.0, 34.0, 10.0), (0.0, 39.0, -2.0)),
            },
            purpose=_purpose("secondary_scale_forms", "copy_secondary_bundles"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="set_dressing.floor_contact",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "set_dressing_foot",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("floor_contact_or_base", "foot_source"),
                ),
                "points": ((-16.0, -24.0, -12.0), (16.0, -24.0, -12.0), (-16.0, -24.0, 12.0), (16.0, -24.0, 12.0)),
            },
            purpose=_purpose("floor_contact_or_base", "copy_contact_feet"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="set_dressing.handle_strap",
            parameters={
                "radius_cm": 0.9,
                "path": ((-18.0, 12.0, -17.0), (-7.0, 22.0, -20.0), (7.0, 22.0, -20.0), (18.0, 12.0, -17.0)),
            },
            purpose=_purpose("handles_straps_or_ties", "curved_front_strap"),
        ),
        ShapeOp(
            op="sop.boolean",
            target="set_dressing.lid_opening",
            parameters={
                "operation": "subtract",
                "source": _panel_source(
                    target="set_dressing_lid_cut",
                    width_cm=26.0,
                    height_cm=7.0,
                    thickness_cm=3.0,
                    center=(0.0, 25.0, -16.5),
                    purpose=_purpose("openings_or_lids", "lid_cut_source"),
                ),
            },
            purpose=_purpose("openings_or_lids", "subtractive_lid_seam"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="set_dressing.label_zone",
            parameters={
                "profile_polygon": _rect_profile(18.0, 6.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, 10.0, -17.2),
            },
            purpose=_purpose("label_or_marking_zone", "raised_world_label"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="set_dressing.stitches",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "set_dressing_stitch",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("fasteners_or_stitches", "stitch_source"),
                ),
                "points": ((-19.0, 0.0, -17.0), (-19.0, 10.0, -17.0), (-19.0, 20.0, -17.0), (19.0, 0.0, -17.0), (19.0, 10.0, -17.0), (19.0, 20.0, -17.0)),
            },
            purpose=_purpose("fasteners_or_stitches", "copy_side_stitches"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="set_dressing.small_scatter",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "set_dressing_small_chip",
                    {
                        "width_cm": 5.0,
                        "height_cm": 2.0,
                        "depth_cm": 4.0,
                        "corner_radii_cm": (0.8, 0.5, 0.9, 0.6, 0.7, 0.8, 0.5, 0.6),
                    },
                    _purpose("small_detail_scatter", "chip_source"),
                ),
                "points": _set_dressing_scatter_points(),
            },
            purpose=_purpose("small_detail_scatter", "copy_small_scatter"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="set_dressing.material_zone",
            parameters={
                "source": _panel_source(
                    target="set_dressing_material_band",
                    width_cm=36.0,
                    height_cm=5.0,
                    thickness_cm=0.8,
                    center=(0.0, 2.0, -17.5),
                    purpose=_purpose("material_zone_variation", "band_source"),
                ),
                "width_cm": 0.25,
                "segments": 2,
            },
            purpose=_purpose("material_zone_variation", "polybeveled_material_band"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="set_dressing.handled_edges",
            parameters={"amount": 0.2},
            purpose=_purpose("handled_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.set_dressing_primary_volume", "primary_volume"),
        _node("recipe.set_dressing_secondary_forms", "mount"),
        _node("recipe.set_dressing_floor_contact", "mount"),
        _node("recipe.set_dressing_handle_strap", "handle"),
        _node("recipe.set_dressing_lid_opening", "inset"),
        _node("recipe.set_dressing_label_zone", "decal_zone"),
        _node("recipe.set_dressing_stitches", "fastener"),
        _node("recipe.set_dressing_small_scatter", "mount"),
        _node("recipe.set_dressing_material_zone", "material_zone"),
        _node("recipe.set_dressing_handled_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="set_dressing_prop",
        family="set_dressing_prop",
        ops=ops,
    )
    return RecipeResult(
        family="set_dressing_prop",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _surface_material_sample_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="surface.sample_tile",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "surface_sample_tile",
                    {
                        "width_cm": _SURFACE_SAMPLE_WIDTH_CM,
                        "height_cm": _SURFACE_SAMPLE_HEIGHT_CM,
                        "depth_cm": _SURFACE_SAMPLE_DEPTH_CM,
                    },
                    _purpose("sample_tile_or_swatch", "box_source"),
                ),
                "width_cm": 0.8,
                "segments": 3,
            },
            purpose=_purpose("sample_tile_or_swatch", "polybeveled_sample_tile"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="surface.base_material_zone",
            parameters={
                "profile_polygon": _rect_profile(30.0, 16.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-18.0, 3.0, 3.0),
            },
            purpose=_purpose("base_material_zone", "raised_base_zone"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="surface.finish_zone",
            parameters={
                "profile_polygon": _rect_profile(30.0, 16.0),
                "extrude_height_cm": 0.2,
                "axis": "y",
                "center": (18.0, 3.0, 3.0),
            },
            purpose=_purpose("roughness_or_finish_zone", "raised_finish_zone"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="surface.relief_lines",
            parameters={
                "source": _source_op(
                    "sop.boolean",
                    "surface_relief_line",
                    {
                        "operation": "subtract",
                        "source": _panel_source(
                            target="surface_relief_cut",
                            width_cm=54.0,
                            height_cm=0.8,
                            thickness_cm=1.0,
                            center=(0.0, 0.0, 0.0),
                            purpose=_purpose("normal_or_relief_detail", "line_source"),
                        ),
                    },
                    _purpose("normal_or_relief_detail", "subtractive_line_source"),
                ),
                "points": ((0.0, 3.5, -14.0), (0.0, 3.5, -7.0), (0.0, 3.5, 14.0)),
            },
            purpose=_purpose("normal_or_relief_detail", "copy_relief_lines"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="surface.border_trim",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "surface_border_wire",
                    {"radius_cm": 0.45, "path": ((-32.0, 3.6, 0.0), (32.0, 3.6, 0.0))},
                    _purpose("trim_or_border", "border_source"),
                ),
                "points": ((0.0, 0.0, -23.0), (0.0, 0.0, 23.0)),
            },
            purpose=_purpose("trim_or_border", "copy_border_trim"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="surface.label_zone",
            parameters={
                "profile_polygon": _rect_profile(20.0, 4.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 3.8, -19.0),
            },
            purpose=_purpose("decal_or_label_zone", "raised_channel_label"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="surface.scale_ticks",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "surface_tick",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("scale_or_frequency_reference", "tick_source"),
                ),
                "points": _surface_tick_points(),
            },
            purpose=_purpose("scale_or_frequency_reference", "copy_scale_ticks"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="surface.edge_wear",
            parameters={"amount": 0.18, "grime_bias": 0.2},
            purpose=_purpose("edge_chips_or_wear", "chip_edges"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="surface.variant_patch",
            parameters={
                "source": _panel_source(
                    target="surface_variant_patch",
                    width_cm=16.0,
                    height_cm=12.0,
                    thickness_cm=0.5,
                    center=(25.0, 3.2, 15.0),
                    purpose=_purpose("variant_patch_or_secondary_material", "patch_source"),
                ),
                "width_cm": 0.25,
                "segments": 2,
            },
            purpose=_purpose("variant_patch_or_secondary_material", "polybeveled_variant_patch"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="surface.tileability_cues",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "surface_corner_marker",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("uv_or_tileability_cues", "corner_marker_source"),
                ),
                "points": ((-34.0, 3.5, -22.0), (34.0, 3.5, -22.0), (-34.0, 3.5, 22.0), (34.0, 3.5, 22.0)),
            },
            purpose=_purpose("uv_or_tileability_cues", "copy_corner_markers"),
        ),
    )
    nodes = (
        _node("recipe.surface_sample_tile", "primary_volume"),
        _node("recipe.surface_base_material_zone", "material_zone"),
        _node("recipe.surface_finish_zone", "material_zone"),
        _node("recipe.surface_relief_lines", "inset"),
        _node("recipe.surface_border_trim", "trim"),
        _node("recipe.surface_label_zone", "decal_zone"),
        _node("recipe.surface_scale_ticks", "fastener"),
        _node("recipe.surface_edge_wear", "wear_zone"),
        _node("recipe.surface_variant_patch", "material_zone"),
        _node("recipe.surface_tileability_cues", "socket"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="surface_material_sample",
        family="surface_material_sample",
        ops=ops,
    )
    return RecipeResult(
        family="surface_material_sample",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _terrain_vegetation_variant_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="terrain_variant.ground_plate",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "terrain_variant_ground",
                    {
                        "width_cm": _TERRAIN_VARIANT_WIDTH_CM,
                        "height_cm": _TERRAIN_VARIANT_HEIGHT_CM,
                        "depth_cm": _TERRAIN_VARIANT_DEPTH_CM,
                    },
                    _purpose("terrain_base_or_height_plate", "box_source"),
                ),
                "width_cm": 5.0,
                "segments": 8,
            },
            purpose=_purpose("terrain_base_or_height_plate", "soft_eroded_ground"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_variant.strata",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "terrain_strata_ridge",
                    {
                        "profile_points": _rect_profile(38.0, 2.0),
                        "height_cm": 2.5,
                        "axis": "z",
                    },
                    _purpose("height_variation_or_strata", "ridge_source"),
                ),
                "points": ((-20.0, 10.0, -18.0), (12.0, 13.0, 4.0), (24.0, 9.0, 24.0)),
            },
            purpose=_purpose("height_variation_or_strata", "copy_strata_ridges"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_variant.growth_clusters",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "terrain_growth_cluster",
                    {"radius_cm": 4.5},
                    _purpose("growth_clusters", "cluster_source"),
                ),
                "points": _terrain_growth_points(),
            },
            purpose=_purpose("growth_clusters", "copy_growth_clusters"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="terrain_variant.flow_path",
            parameters={
                "radius_cm": 0.85,
                "path": (
                    (-42.0, 11.0, 24.0),
                    (-18.0, 13.0, 8.0),
                    (12.0, 12.0, -4.0),
                    (40.0, 10.0, -26.0),
                ),
            },
            purpose=_purpose("root_or_path_flow", "swept_growth_or_erosion_path"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_variant.small_scatter",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "terrain_pebble",
                    {
                        "width_cm": 4.0,
                        "height_cm": 1.8,
                        "depth_cm": 3.2,
                        "corner_radii_cm": (0.7, 0.5, 0.8, 0.6, 0.6, 0.9, 0.4, 0.5),
                    },
                    _purpose("small_natural_scatter", "pebble_source"),
                ),
                "points": ((-30.0, 10.5, 18.0), (-6.0, 12.0, 25.0), (17.0, 11.0, -21.0), (35.0, 9.5, 5.0)),
            },
            purpose=_purpose("small_natural_scatter", "copy_pebble_scatter"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="terrain_variant.material_zone",
            parameters={
                "profile_polygon": _rect_profile(32.0, 18.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-16.0, 10.5, -8.0),
            },
            purpose=_purpose("biome_material_zones", "raised_moss_or_soil_zone"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="terrain_variant.edge_blend",
            parameters={
                "source": _panel_source(
                    target="terrain_edge_blend_skirt",
                    width_cm=_TERRAIN_VARIANT_WIDTH_CM,
                    height_cm=5.0,
                    thickness_cm=1.0,
                    center=(0.0, 8.0, _TERRAIN_VARIANT_DEPTH_CM * 0.5 + 1.0),
                    purpose=_purpose("edge_transition_or_blend", "skirt_source"),
                ),
                "width_cm": 0.8,
                "segments": 3,
            },
            purpose=_purpose("edge_transition_or_blend", "polybeveled_blend_skirt"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_variant.scale_anchors",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "terrain_log_anchor",
                    {"radius_cm": 1.4, "path": ((-8.0, 0.0, 0.0), (8.0, 0.0, 1.5))},
                    _purpose("scale_anchors", "log_source"),
                ),
                "points": ((-26.0, 14.0, -28.0), (24.0, 12.0, 28.0)),
            },
            purpose=_purpose("scale_anchors", "copy_log_anchors"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="terrain_variant.erosion_masks",
            parameters={"amount": 0.26, "damp_bias": 0.25},
            purpose=_purpose("erosion_or_weathering_masks", "chip_edges"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="terrain_variant.variant_marker",
            parameters={
                "profile_polygon": _rect_profile(14.0, 4.0),
                "extrude_height_cm": 0.2,
                "axis": "y",
                "center": (34.0, 11.0, -30.0),
            },
            purpose=_purpose("variant_or_tileability_cues", "raised_biome_marker"),
        ),
    )
    nodes = (
        _node("recipe.terrain_variant_ground", "primary_volume"),
        _node("recipe.terrain_variant_strata", "trim"),
        _node("recipe.terrain_variant_growth", "material_zone"),
        _node("recipe.terrain_variant_flow_path", "rail"),
        _node("recipe.terrain_variant_scatter", "fastener"),
        _node("recipe.terrain_variant_material_zone", "material_zone"),
        _node("recipe.terrain_variant_edge_blend", "panel"),
        _node("recipe.terrain_variant_scale_anchors", "mount"),
        _node("recipe.terrain_variant_erosion", "wear_zone"),
        _node("recipe.terrain_variant_marker", "decal_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="terrain_vegetation_variant",
        family="terrain_vegetation_variant",
        ops=ops,
    )
    return RecipeResult(
        family="terrain_vegetation_variant",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _environment_effect_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="effect.emitter",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "effect_source_emitter",
                    {
                        "profile_points": (
                            (0.0, -4.0),
                            (5.0, -3.0),
                            (6.0, 0.0),
                            (5.0, 3.0),
                            (0.0, 4.0),
                        ),
                        "axis": "z",
                        "center": (-_EFFECT_WIDTH_CM * 0.35, 6.0, -_EFFECT_DEPTH_CM * 0.35),
                    },
                    _purpose("emitter_or_source", "emitter_source"),
                ),
                "width_cm": 0.25,
                "segments": 2,
            },
            purpose=_purpose("emitter_or_source", "polybeveled_emitter"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="effect.flow_volume",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "effect_flow_volume",
                    {
                        "width_cm": _EFFECT_WIDTH_CM,
                        "height_cm": _EFFECT_HEIGHT_CM,
                        "depth_cm": _EFFECT_DEPTH_CM,
                        "center": (0.0, 18.0, 0.0),
                    },
                    _purpose("flow_surface_or_volume", "box_source"),
                ),
                "width_cm": 8.0,
                "segments": 10,
            },
            purpose=_purpose("flow_surface_or_volume", "soft_effect_volume"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="effect.motion_lines",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "effect_motion_line",
                    {
                        "radius_cm": 0.55,
                        "path": ((-24.0, 10.0, -10.0), (0.0, 18.0, 0.0), (24.0, 22.0, 10.0)),
                    },
                    _purpose("direction_or_motion_lines", "motion_line_source"),
                ),
                "points": ((0.0, -4.0, -12.0), (0.0, 0.0, 0.0), (0.0, 4.0, 12.0)),
            },
            purpose=_purpose("direction_or_motion_lines", "copy_motion_lines"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="effect.contact_zone",
            parameters={
                "profile_polygon": _rect_profile(58.0, 18.0),
                "extrude_height_cm": 0.2,
                "axis": "y",
                "center": (6.0, 1.0, 10.0),
            },
            purpose=_purpose("contact_or_interaction_zone", "wet_contact_zone"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="effect.secondary_particles",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "effect_particle",
                    {"radius_cm": 1.6},
                    _purpose("secondary_particles_or_ripples", "particle_source"),
                ),
                "points": _effect_particle_points(),
            },
            purpose=_purpose("secondary_particles_or_ripples", "copy_particles"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="effect.density_bands",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "effect_density_ring",
                    {"major_radius_cm": 12.0, "minor_radius_cm": 0.35, "axis": "y"},
                    _purpose("density_or_gradient_bands", "ring_source"),
                ),
                "points": ((-12.0, 14.0, 0.0), (12.0, 22.0, 0.0)),
            },
            purpose=_purpose("density_or_gradient_bands", "copy_density_rings"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="effect.boundary",
            parameters={
                "source": _panel_source(
                    target="effect_basin_or_clip",
                    width_cm=_EFFECT_WIDTH_CM,
                    height_cm=4.0,
                    thickness_cm=2.0,
                    center=(0.0, 2.0, _EFFECT_DEPTH_CM * 0.5 + 1.0),
                    purpose=_purpose("boundary_or_clip_shape", "boundary_source"),
                ),
                "width_cm": 0.6,
                "segments": 2,
            },
            purpose=_purpose("boundary_or_clip_shape", "polybeveled_boundary"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="effect.material_response",
            parameters={
                "profile_polygon": _rect_profile(36.0, 7.0),
                "extrude_height_cm": 0.18,
                "axis": "y",
                "center": (-10.0, 2.2, -20.0),
            },
            purpose=_purpose("material_response_zone", "foam_or_residue_zone"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="effect.readability_markers",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "effect_marker_fleck",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("scale_or_readability_markers", "fleck_source"),
                ),
                "points": ((-34.0, 2.5, -18.0), (-20.0, 2.5, -21.0), (8.0, 2.5, -18.0), (28.0, 2.5, -12.0)),
            },
            purpose=_purpose("scale_or_readability_markers", "copy_foam_flecks"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="effect.dynamic_masks",
            parameters={"amount": 0.18, "opacity_bias": 0.4},
            purpose=_purpose("effect_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.effect_emitter", "primary_volume"),
        _node("recipe.effect_flow_volume", "material_zone"),
        _node("recipe.effect_motion_lines", "rail"),
        _node("recipe.effect_contact_zone", "wear_zone"),
        _node("recipe.effect_particles", "fastener"),
        _node("recipe.effect_density_bands", "trim"),
        _node("recipe.effect_boundary", "frame"),
        _node("recipe.effect_material_response", "material_zone"),
        _node("recipe.effect_readability_markers", "decal_zone"),
        _node("recipe.effect_dynamic_masks", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="environment_effect",
        family="environment_effect",
        ops=ops,
    )
    return RecipeResult(
        family="environment_effect",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _settlement_district_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="settlement.footprint",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "settlement_layout_footprint",
                    {
                        "width_cm": _SETTLEMENT_WIDTH_CM,
                        "height_cm": _SETTLEMENT_HEIGHT_CM,
                        "depth_cm": _SETTLEMENT_DEPTH_CM,
                    },
                    _purpose("primary_layout_footprint", "box_source"),
                ),
                "width_cm": 3.5,
                "segments": 5,
            },
            purpose=_purpose("primary_layout_footprint", "polybeveled_layout_plate"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="settlement.circulation_paths",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "settlement_path_spine",
                    {
                        "radius_cm": 2.2,
                        "path": ((-42.0, 0.0, -22.0), (-8.0, 0.0, -2.0), (30.0, 0.0, 18.0)),
                    },
                    _purpose("circulation_paths", "path_source"),
                ),
                "points": ((-28.0, 9.0, -20.0), (12.0, 9.0, 18.0), (38.0, 9.0, -26.0)),
            },
            purpose=_purpose("circulation_paths", "copy_path_spines"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="settlement.plot_cells",
            parameters={
                "source": _source_op(
                    "sop.polybevel",
                    "settlement_plot_cell",
                    {
                        "source": _source_op(
                            "solid.extruded_profile",
                            "settlement_plot_cell_plate",
                            {
                                "profile_points": _rect_profile(22.0, 16.0),
                                "height_cm": 1.5,
                                "axis": "y",
                            },
                            _purpose("plot_or_block_cells", "cell_plate_source"),
                        ),
                        "width_cm": 0.6,
                        "segments": 2,
                    },
                    _purpose("plot_or_block_cells", "polybeveled_cell_source"),
                ),
                "points": _settlement_plot_points(),
            },
            purpose=_purpose("plot_or_block_cells", "copy_plot_cells"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="settlement.landmark",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "settlement_landmark_tower",
                    {
                        "profile_points": (
                            (0.0, 0.0),
                            (6.0, 1.5),
                            (8.0, 26.0),
                            (4.0, 38.0),
                            (0.0, 40.0),
                        ),
                        "axis": "y",
                        "center": (0.0, _SETTLEMENT_HEIGHT_CM, 0.0),
                    },
                    _purpose("landmark_or_anchor", "tower_source"),
                ),
                "width_cm": 0.8,
                "segments": 3,
            },
            purpose=_purpose("landmark_or_anchor", "polybeveled_landmark"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="settlement.thresholds",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "settlement_gateway_arch",
                    {
                        "radius_cm": 1.6,
                        "path": ((-7.0, 0.0, 0.0), (-4.0, 10.0, 0.0), (0.0, 14.0, 0.0), (4.0, 10.0, 0.0), (7.0, 0.0, 0.0)),
                    },
                    _purpose("thresholds_or_gateways", "gateway_source"),
                ),
                "points": ((-68.0, 11.0, -2.0), (70.0, 11.0, 6.0), (0.0, 11.0, 58.0)),
            },
            purpose=_purpose("thresholds_or_gateways", "copy_gateways"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="settlement.activity_zone",
            parameters={
                "profile_polygon": _rect_profile(42.0, 24.0),
                "extrude_height_cm": 0.35,
                "axis": "y",
                "center": (-30.0, 12.5, 30.0),
            },
            purpose=_purpose("activity_zones", "raised_activity_zone"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="settlement.height_markers",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "settlement_height_marker",
                    {
                        "width_cm": 10.0,
                        "height_cm": 18.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (1.5, 1.0, 1.2, 1.4, 0.8, 1.1, 0.9, 1.3),
                    },
                    _purpose("vertical_or_height_variation", "height_marker_source"),
                ),
                "points": ((-18.0, 18.0, -44.0), (48.0, 18.0, 30.0), (-50.0, 18.0, 36.0)),
            },
            purpose=_purpose("vertical_or_height_variation", "copy_height_markers"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="settlement.edge_boundaries",
            parameters={
                "radius_cm": 1.1,
                "path": (
                    (-_SETTLEMENT_WIDTH_CM * 0.5, _SETTLEMENT_HEIGHT_CM + 1.0, -_SETTLEMENT_DEPTH_CM * 0.5),
                    (_SETTLEMENT_WIDTH_CM * 0.5, _SETTLEMENT_HEIGHT_CM + 1.0, -_SETTLEMENT_DEPTH_CM * 0.5),
                    (_SETTLEMENT_WIDTH_CM * 0.5, _SETTLEMENT_HEIGHT_CM + 1.0, _SETTLEMENT_DEPTH_CM * 0.5),
                    (-_SETTLEMENT_WIDTH_CM * 0.5, _SETTLEMENT_HEIGHT_CM + 1.0, _SETTLEMENT_DEPTH_CM * 0.5),
                    (-_SETTLEMENT_WIDTH_CM * 0.5, _SETTLEMENT_HEIGHT_CM + 1.0, -_SETTLEMENT_DEPTH_CM * 0.5),
                ),
            },
            purpose=_purpose("edge_boundaries", "swept_boundary_loop"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="settlement.wayfinding",
            parameters={
                "profile_polygon": _rect_profile(16.0, 5.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (48.0, 13.0, -48.0),
            },
            purpose=_purpose("signage_or_wayfinding", "raised_wayfinding_marker"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="settlement.traffic_wear",
            parameters={"amount": 0.22, "traffic_bias": 0.55},
            purpose=_purpose("traffic_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.settlement_footprint", "primary_volume"),
        _node("recipe.settlement_paths", "rail"),
        _node("recipe.settlement_plot_cells", "panel"),
        _node("recipe.settlement_landmark", "mount"),
        _node("recipe.settlement_thresholds", "frame"),
        _node("recipe.settlement_activity_zone", "material_zone"),
        _node("recipe.settlement_height_markers", "primary_volume"),
        _node("recipe.settlement_boundaries", "guard"),
        _node("recipe.settlement_wayfinding", "decal_zone"),
        _node("recipe.settlement_traffic_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="settlement_district",
        family="settlement_district",
        ops=ops,
    )
    return RecipeResult(
        family="settlement_district",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _gameplay_object_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="gameplay_object.body",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "gameplay_interaction_body",
                    {
                        "width_cm": _GAMEPLAY_WIDTH_CM,
                        "height_cm": _GAMEPLAY_HEIGHT_CM,
                        "depth_cm": _GAMEPLAY_DEPTH_CM,
                        "corner_radii_cm": (3.5, 2.8, 3.1, 2.6, 2.2, 3.0, 2.4, 3.2),
                    },
                    _purpose("interaction_body", "body_source"),
                ),
                "width_cm": 1.2,
                "segments": 4,
            },
            purpose=_purpose("interaction_body", "polybeveled_interaction_body"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="gameplay_object.state_indicator",
            parameters={
                "profile_polygon": _rect_profile(18.0, 7.0),
                "extrude_height_cm": 0.35,
                "axis": "z",
                "center": (0.0, 32.0, -_GAMEPLAY_DEPTH_CM * 0.5 - 0.5),
            },
            purpose=_purpose("state_indicator", "raised_status_panel"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="gameplay_object.trigger_zone",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "gameplay_trigger_zone",
                    {
                        "width_cm": _GAMEPLAY_WIDTH_CM + 18.0,
                        "height_cm": 1.2,
                        "depth_cm": _GAMEPLAY_DEPTH_CM + 16.0,
                        "center": (0.0, -1.0, 0.0),
                    },
                    _purpose("trigger_or_activation_zone", "zone_source"),
                ),
                "width_cm": 2.0,
                "segments": 5,
            },
            purpose=_purpose("trigger_or_activation_zone", "polybeveled_activation_zone"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="gameplay_object.payload_zone",
            parameters={
                "source": _panel_source(
                    target="gameplay_payload_compartment",
                    width_cm=20.0,
                    height_cm=10.0,
                    thickness_cm=2.5,
                    center=(0.0, 18.0, -_GAMEPLAY_DEPTH_CM * 0.5 - 1.0),
                    purpose=_purpose("reward_or_payload_zone", "payload_source"),
                ),
                "width_cm": 0.7,
                "segments": 2,
            },
            purpose=_purpose("reward_or_payload_zone", "polybeveled_payload_zone"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="gameplay_object.affordance_handle",
            parameters={
                "radius_cm": 1.1,
                "path": ((-9.0, 19.0, -17.0), (-9.0, 26.0, -20.0), (9.0, 26.0, -20.0), (9.0, 19.0, -17.0)),
            },
            purpose=_purpose("access_or_affordance_handle", "swept_handle"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_object.feedback_emitters",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "gameplay_feedback_emitter",
                    {"radius_cm": 2.0},
                    _purpose("feedback_emitter", "emitter_source"),
                ),
                "points": ((-10.0, 36.0, -16.5), (0.0, 38.0, -17.0), (10.0, 36.0, -16.5)),
            },
            purpose=_purpose("feedback_emitter", "copy_feedback_emitters"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_object.bounds_markers",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "gameplay_bounds_marker",
                    {
                        "profile_points": _rect_profile(12.0, 2.0),
                        "height_cm": 0.5,
                        "axis": "y",
                    },
                    _purpose("safety_or_bounds_marker", "marker_source"),
                ),
                "points": ((-22.0, 1.0, -22.0), (22.0, 1.0, -22.0), (-22.0, 1.0, 22.0), (22.0, 1.0, 22.0)),
            },
            purpose=_purpose("safety_or_bounds_marker", "copy_bounds_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_object.link_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "gameplay_link_port",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("attachment_or_link_ports", "port_source"),
                ),
                "points": _gameplay_port_points(),
            },
            purpose=_purpose("attachment_or_link_ports", "copy_link_ports"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="gameplay_object.objective_marker",
            parameters={
                "profile_polygon": ((-7.0, 0.0), (0.0, 7.0), (7.0, 0.0), (0.0, -7.0)),
                "extrude_height_cm": 0.3,
                "axis": "z",
                "center": (0.0, 42.0, -_GAMEPLAY_DEPTH_CM * 0.5 - 0.6),
            },
            purpose=_purpose("label_or_objective_marker", "raised_objective_marker"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="gameplay_object.interaction_wear",
            parameters={"amount": 0.16, "interaction_bias": 0.6},
            purpose=_purpose("interaction_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.gameplay_body", "primary_volume"),
        _node("recipe.gameplay_state_indicator", "panel"),
        _node("recipe.gameplay_trigger_zone", "material_zone"),
        _node("recipe.gameplay_payload_zone", "socket"),
        _node("recipe.gameplay_affordance_handle", "handle"),
        _node("recipe.gameplay_feedback_emitters", "mount"),
        _node("recipe.gameplay_bounds_markers", "guard"),
        _node("recipe.gameplay_link_ports", "socket"),
        _node("recipe.gameplay_objective_marker", "decal_zone"),
        _node("recipe.gameplay_interaction_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="gameplay_object",
        family="gameplay_object",
        ops=ops,
    )
    return RecipeResult(
        family="gameplay_object",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _encounter_flow_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="encounter.footprint",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "encounter_arena_footprint",
                    {
                        "width_cm": _ENCOUNTER_WIDTH_CM,
                        "height_cm": _ENCOUNTER_HEIGHT_CM,
                        "depth_cm": _ENCOUNTER_DEPTH_CM,
                    },
                    _purpose("encounter_footprint", "box_source"),
                ),
                "width_cm": 3.0,
                "segments": 5,
            },
            purpose=_purpose("encounter_footprint", "polybeveled_arena_bounds"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="encounter.spawn_points",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "encounter_spawn_socket",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("spawn_or_entry_points", "spawn_socket_source"),
                ),
                "points": _encounter_spawn_points(),
            },
            purpose=_purpose("spawn_or_entry_points", "copy_spawn_sockets"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="encounter.route_lines",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "encounter_patrol_route",
                    {
                        "radius_cm": 0.9,
                        "path": ((-38.0, 0.0, -26.0), (-8.0, 0.0, -2.0), (22.0, 0.0, 20.0), (44.0, 0.0, 34.0)),
                    },
                    _purpose("patrol_or_route_lines", "route_source"),
                ),
                "points": ((0.0, 8.5, 0.0), (0.0, 8.5, -18.0), (0.0, 8.5, 20.0)),
            },
            purpose=_purpose("patrol_or_route_lines", "copy_route_lines"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="encounter.cover_zones",
            parameters={
                "source": _source_op(
                    "sop.polybevel",
                    "encounter_cover_block",
                    {
                        "source": _source_op(
                            "solid.subdivision_box",
                            "encounter_cover_volume",
                            {
                                "width_cm": 18.0,
                                "height_cm": 14.0,
                                "depth_cm": 8.0,
                                "corner_radii_cm": (1.4, 1.1, 1.6, 1.2, 1.0, 1.5, 1.3, 1.2),
                            },
                            _purpose("cover_or_safety_zones", "cover_source"),
                        ),
                        "width_cm": 0.8,
                        "segments": 2,
                    },
                    _purpose("cover_or_safety_zones", "polybeveled_cover_source"),
                ),
                "points": ((-34.0, 15.0, -6.0), (0.0, 15.0, 24.0), (36.0, 15.0, -18.0)),
            },
            purpose=_purpose("cover_or_safety_zones", "copy_cover_blocks"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="encounter.objective_point",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "encounter_objective_anchor",
                    {
                        "profile_points": ((0.0, 0.0), (5.0, 1.0), (7.0, 6.0), (3.0, 11.0), (0.0, 12.0)),
                        "axis": "y",
                        "center": (0.0, _ENCOUNTER_HEIGHT_CM, 0.0),
                    },
                    _purpose("objective_or_pressure_point", "anchor_source"),
                ),
                "width_cm": 0.5,
                "segments": 2,
            },
            purpose=_purpose("objective_or_pressure_point", "polybeveled_objective_anchor"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="encounter.wave_markers",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "encounter_wave_tick",
                    {"radius_cm": 1.8},
                    _purpose("escalation_or_wave_markers", "wave_tick_source"),
                ),
                "points": ((-12.0, 11.0, -42.0), (-4.0, 11.0, -42.0), (4.0, 11.0, -42.0), (12.0, 11.0, -42.0)),
            },
            purpose=_purpose("escalation_or_wave_markers", "copy_wave_ticks"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="encounter.reward_exit_zone",
            parameters={
                "profile_polygon": _rect_profile(28.0, 12.0),
                "extrude_height_cm": 0.3,
                "axis": "y",
                "center": (0.0, _ENCOUNTER_HEIGHT_CM + 0.6, _ENCOUNTER_DEPTH_CM * 0.42),
            },
            purpose=_purpose("reward_or_exit_zone", "raised_reward_exit_zone"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="encounter.hazard_boundary",
            parameters={
                "radius_cm": 1.0,
                "path": (
                    (-_ENCOUNTER_WIDTH_CM * 0.5, _ENCOUNTER_HEIGHT_CM + 1.2, -_ENCOUNTER_DEPTH_CM * 0.5),
                    (_ENCOUNTER_WIDTH_CM * 0.5, _ENCOUNTER_HEIGHT_CM + 1.2, -_ENCOUNTER_DEPTH_CM * 0.5),
                    (_ENCOUNTER_WIDTH_CM * 0.5, _ENCOUNTER_HEIGHT_CM + 1.2, _ENCOUNTER_DEPTH_CM * 0.5),
                    (-_ENCOUNTER_WIDTH_CM * 0.5, _ENCOUNTER_HEIGHT_CM + 1.2, _ENCOUNTER_DEPTH_CM * 0.5),
                    (-_ENCOUNTER_WIDTH_CM * 0.5, _ENCOUNTER_HEIGHT_CM + 1.2, -_ENCOUNTER_DEPTH_CM * 0.5),
                ),
            },
            purpose=_purpose("hazard_or_boundary_markers", "swept_hazard_boundary"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="encounter.readability_cue",
            parameters={
                "profile_polygon": ((-6.0, -3.0), (5.0, -3.0), (8.0, 0.0), (5.0, 3.0), (-6.0, 3.0)),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-_ENCOUNTER_WIDTH_CM * 0.34, _ENCOUNTER_HEIGHT_CM + 0.8, 38.0),
            },
            purpose=_purpose("readability_or_signage_cues", "raised_flow_arrow"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="encounter.pacing_wear",
            parameters={"amount": 0.2, "route_bias": 0.65},
            purpose=_purpose("pacing_or_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.encounter_footprint", "primary_volume"),
        _node("recipe.encounter_spawn_points", "socket"),
        _node("recipe.encounter_routes", "rail"),
        _node("recipe.encounter_cover", "guard"),
        _node("recipe.encounter_objective", "mount"),
        _node("recipe.encounter_wave_markers", "fastener"),
        _node("recipe.encounter_reward_exit", "material_zone"),
        _node("recipe.encounter_hazard_boundary", "guard"),
        _node("recipe.encounter_readability", "decal_zone"),
        _node("recipe.encounter_pacing_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="encounter_flow",
        family="encounter_flow",
        ops=ops,
    )
    return RecipeResult(
        family="encounter_flow",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _inventory_economy_object_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="inventory.body",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "inventory_container_body",
                    {
                        "width_cm": _INVENTORY_WIDTH_CM,
                        "height_cm": _INVENTORY_HEIGHT_CM,
                        "depth_cm": _INVENTORY_DEPTH_CM,
                        "corner_radii_cm": (2.2, 1.8, 2.0, 1.6, 1.4, 2.1, 1.7, 1.9),
                    },
                    _purpose("item_body_or_container", "body_source"),
                ),
                "width_cm": 1.0,
                "segments": 3,
            },
            purpose=_purpose("item_body_or_container", "polybeveled_container_body"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="inventory.value_markers",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "inventory_currency_pip",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("value_or_currency_marker", "currency_pip_source"),
                ),
                "points": ((-8.0, 23.0, -13.0), (0.0, 24.0, -13.0), (8.0, 23.0, -13.0)),
            },
            purpose=_purpose("value_or_currency_marker", "copy_currency_pips"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="inventory.quantity_ticks",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "inventory_stack_tick",
                    {"profile_points": _rect_profile(2.0, 5.0), "height_cm": 0.4, "axis": "z"},
                    _purpose("quantity_or_stack_indicator", "stack_tick_source"),
                ),
                "points": ((-12.0, 5.0, -13.0), (-7.0, 5.0, -13.0), (-2.0, 5.0, -13.0), (3.0, 5.0, -13.0), (8.0, 5.0, -13.0), (13.0, 5.0, -13.0)),
            },
            purpose=_purpose("quantity_or_stack_indicator", "copy_stack_ticks"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="inventory.rarity_band",
            parameters={
                "profile_polygon": _rect_profile(_INVENTORY_WIDTH_CM + 2.0, 3.5),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, 16.0, -_INVENTORY_DEPTH_CM * 0.5 - 0.4),
            },
            purpose=_purpose("rarity_or_tier_band", "raised_rarity_band"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="inventory.access_handle",
            parameters={
                "radius_cm": 0.75,
                "path": ((-8.0, 15.0, -13.5), (-8.0, 20.0, -15.5), (8.0, 20.0, -15.5), (8.0, 15.0, -13.5)),
            },
            purpose=_purpose("access_or_lock_affordance", "swept_access_handle"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="inventory.storage_slots",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "inventory_slot_inset",
                    {"profile_points": _rect_profile(6.0, 4.0), "height_cm": 0.3, "axis": "z"},
                    _purpose("storage_slots_or_grid", "slot_source"),
                ),
                "points": _inventory_slot_points(),
            },
            purpose=_purpose("storage_slots_or_grid", "copy_slot_grid"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="inventory.pickup_handle",
            parameters={
                "radius_cm": 0.9,
                "path": ((-_INVENTORY_WIDTH_CM * 0.32, 28.0, 0.0), (-5.0, 33.0, 0.0), (5.0, 33.0, 0.0), (_INVENTORY_WIDTH_CM * 0.32, 28.0, 0.0)),
            },
            purpose=_purpose("pickup_or_use_handle", "swept_pickup_handle"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="inventory.vendor_label",
            parameters={
                "profile_polygon": _rect_profile(13.0, 4.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, 9.5, -_INVENTORY_DEPTH_CM * 0.5 - 0.45),
            },
            purpose=_purpose("ownership_or_vendor_label", "raised_vendor_label"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="inventory.resource_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "inventory_resource_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("resource_connection_ports", "port_source"),
                ),
                "points": ((-_INVENTORY_WIDTH_CM * 0.5 - 0.4, 14.0, 0.0), (_INVENTORY_WIDTH_CM * 0.5 + 0.4, 14.0, 0.0)),
            },
            purpose=_purpose("resource_connection_ports", "copy_resource_ports"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="inventory.handled_wear",
            parameters={"amount": 0.14, "pickup_bias": 0.7},
            purpose=_purpose("handled_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.inventory_body", "primary_volume"),
        _node("recipe.inventory_value_markers", "decal_zone"),
        _node("recipe.inventory_quantity_ticks", "fastener"),
        _node("recipe.inventory_rarity_band", "material_zone"),
        _node("recipe.inventory_access_handle", "handle"),
        _node("recipe.inventory_storage_slots", "inset"),
        _node("recipe.inventory_pickup_handle", "handle"),
        _node("recipe.inventory_vendor_label", "decal_zone"),
        _node("recipe.inventory_resource_ports", "socket"),
        _node("recipe.inventory_handled_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="inventory_economy_object",
        family="inventory_economy_object",
        ops=ops,
    )
    return RecipeResult(
        family="inventory_economy_object",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _rig_animation_proxy_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="rig_proxy.root_control",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "rig_root_control_body",
                    {
                        "width_cm": _RIG_PROXY_WIDTH_CM,
                        "height_cm": 10.0,
                        "depth_cm": _RIG_PROXY_DEPTH_CM,
                        "center": (0.0, 4.0, 0.0),
                        "corner_radii_cm": (2.0, 1.6, 2.2, 1.8, 1.4, 2.1, 1.7, 1.9),
                    },
                    _purpose("rig_root_or_control_body", "root_source"),
                ),
                "width_cm": 1.0,
                "segments": 3,
            },
            purpose=_purpose("rig_root_or_control_body", "polybeveled_root_control"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="rig_proxy.joint_chain",
            parameters={
                "radius_cm": 0.9,
                "path": ((0.0, 8.0, 0.0), (0.0, 24.0, 0.0), (0.0, 44.0, 0.0), (0.0, 62.0, 0.0)),
            },
            purpose=_purpose("bone_or_joint_chain", "swept_spine_chain"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_proxy.limb_markers",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "rig_joint_marker",
                    {"radius_cm": 2.1},
                    _purpose("limb_or_segment_markers", "joint_marker_source"),
                ),
                "points": _rig_joint_points(),
            },
            purpose=_purpose("limb_or_segment_markers", "copy_joint_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_proxy.ik_targets",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "rig_ik_target",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("ik_or_target_handles", "target_source"),
                ),
                "points": ((-22.0, 42.0, -18.0), (22.0, 42.0, -18.0), (-16.0, 6.0, -18.0), (16.0, 6.0, -18.0)),
            },
            purpose=_purpose("ik_or_target_handles", "copy_ik_targets"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="rig_proxy.motion_arc",
            parameters={
                "radius_cm": 0.55,
                "path": ((-24.0, 14.0, 8.0), (-8.0, 34.0, 14.0), (10.0, 48.0, 12.0), (28.0, 60.0, 4.0)),
            },
            purpose=_purpose("pose_or_motion_arc", "swept_motion_arc"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="rig_proxy.weight_zone",
            parameters={
                "profile_polygon": _rect_profile(20.0, 30.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, 34.0, -_RIG_PROXY_DEPTH_CM * 0.5 - 0.5),
            },
            purpose=_purpose("skin_or_weight_zone", "raised_weight_zone"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_proxy.attachment_sockets",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "rig_attachment_socket",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("attachment_or_socket_ports", "socket_source"),
                ),
                "points": _rig_socket_points(),
            },
            purpose=_purpose("attachment_or_socket_ports", "copy_attachment_sockets"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="rig_proxy.morph_marker",
            parameters={
                "profile_polygon": _rect_profile(16.0, 5.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, 64.0, -_RIG_PROXY_DEPTH_CM * 0.5 - 0.5),
            },
            purpose=_purpose("morph_or_expression_markers", "raised_expression_marker"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_proxy.limit_guards",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "rig_limit_ring",
                    {"major_radius_cm": 4.0, "minor_radius_cm": 0.35, "axis": "z"},
                    _purpose("range_or_limit_guards", "limit_ring_source"),
                ),
                "points": ((-14.0, 44.0, -2.0), (14.0, 44.0, -2.0), (-9.0, 24.0, -2.0), (9.0, 24.0, -2.0)),
            },
            purpose=_purpose("range_or_limit_guards", "copy_limit_rings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_proxy.animation_state_cues",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "rig_state_tick",
                    {"profile_points": _rect_profile(2.0, 4.0), "height_cm": 0.25, "axis": "z"},
                    _purpose("animation_state_cues", "state_tick_source"),
                ),
                "points": ((-10.0, 2.0, -15.0), (-5.0, 2.0, -15.0), (0.0, 2.0, -15.0), (5.0, 2.0, -15.0), (10.0, 2.0, -15.0)),
            },
            purpose=_purpose("animation_state_cues", "copy_state_ticks"),
        ),
    )
    nodes = (
        _node("recipe.rig_root_control", "primary_volume"),
        _node("recipe.rig_joint_chain", "rail"),
        _node("recipe.rig_limb_markers", "mount"),
        _node("recipe.rig_ik_targets", "handle"),
        _node("recipe.rig_motion_arc", "rail"),
        _node("recipe.rig_weight_zone", "material_zone"),
        _node("recipe.rig_attachment_sockets", "socket"),
        _node("recipe.rig_morph_marker", "decal_zone"),
        _node("recipe.rig_limit_guards", "guard"),
        _node("recipe.rig_animation_state_cues", "decal_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="rig_animation_proxy",
        family="rig_animation_proxy",
        ops=ops,
    )
    return RecipeResult(
        family="rig_animation_proxy",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _rig_component_library_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_component_library.component_catalog",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "rig_component_catalog_card",
                    {"profile_points": _rect_profile(14.0, 8.0), "height_cm": 0.35, "axis": "y"},
                    _purpose("component_catalog", "catalog_card_source"),
                ),
                "points": _rig_component_catalog_points(),
            },
            purpose=_purpose("component_catalog", "copy_component_catalog_cards"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="rig_component_library.spine_component",
            parameters={
                "radius_cm": 0.8,
                "path": ((0.0, 10.0, 0.0), (0.0, 24.0, 4.0), (0.0, 40.0, 0.0), (0.0, 56.0, -4.0), (0.0, 70.0, 0.0)),
            },
            purpose=_purpose("spine_component_chain", "swept_spine_component_chain"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_component_library.limb_components",
            parameters={
                "source": _source_op(
                    "solid.swept_profile",
                    "rig_limb_component",
                    {"cross_section": _rect_profile(2.2, 1.4), "path": ((0.0, 0.0, 0.0), (0.0, 18.0, 2.0), (0.0, 36.0, 0.0))},
                    _purpose("limb_component_chain", "limb_component_source"),
                ),
                "points": ((-38.0, 22.0, 0.0), (38.0, 22.0, 0.0), (-28.0, 54.0, 0.0), (28.0, 54.0, 0.0)),
            },
            purpose=_purpose("limb_component_chain", "copy_limb_component_chains"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_component_library.digit_components",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "rig_digit_phalanx",
                    {"radius_cm": 1.35},
                    _purpose("digit_component_chain", "digit_phalanx_source"),
                ),
                "points": tuple((-34.0 + column * 8.0, 14.0 + row * 4.0, 28.0) for row in range(3) for column in range(9)),
            },
            purpose=_purpose("digit_component_chain", "copy_digit_phalanx_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_component_library.mechanical_joints",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "rig_mech_joint_collar",
                    {"major_radius_cm": 3.4, "minor_radius_cm": 0.35, "axis": "y"},
                    _purpose("mechanical_joint_components", "mech_joint_collar_source"),
                ),
                "points": ((-44.0, 38.0, 18.0), (-18.0, 42.0, 22.0), (18.0, 42.0, 22.0), (44.0, 38.0, 18.0)),
            },
            purpose=_purpose("mechanical_joint_components", "copy_mechanical_joint_collars"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="rig_component_library.wing_tentacle_chains",
            parameters={
                "radius_cm": 0.65,
                "path": ((-_RIG_COMPONENT_WIDTH_CM * 0.44, 18.0, -8.0), (-28.0, 38.0, 12.0), (0.0, 46.0, 22.0), (28.0, 38.0, 12.0), (_RIG_COMPONENT_WIDTH_CM * 0.44, 18.0, -8.0)),
            },
            purpose=_purpose("wing_or_tentacle_chains", "swept_flexible_chain_template"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_component_library.connector_contracts",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "rig_connector_socket",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("connector_socket_contracts", "connector_socket_source"),
                ),
                "points": ((-_RIG_COMPONENT_WIDTH_CM * 0.5, 30.0, -16.0), (_RIG_COMPONENT_WIDTH_CM * 0.5, 30.0, -16.0), (-24.0, 8.0, -22.0), (24.0, 8.0, -22.0), (0.0, 72.0, -18.0)),
            },
            purpose=_purpose("connector_socket_contracts", "copy_connector_socket_contracts"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="rig_component_library.ik_fk_templates",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "rig_ik_fk_control",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("ik_fk_control_templates", "ik_fk_control_source"),
                ),
                "points": ((-42.0, 62.0, 28.0), (-14.0, 66.0, 30.0), (14.0, 66.0, 30.0), (42.0, 62.0, 28.0)),
            },
            purpose=_purpose("ik_fk_control_templates", "copy_ik_fk_control_templates"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="rig_component_library.typed_outputs",
            parameters={
                "profile_polygon": _rect_profile(48.0, 8.0),
                "extrude_height_cm": 0.3,
                "axis": "y",
                "center": (0.0, 8.0, _RIG_COMPONENT_DEPTH_CM * 0.46),
            },
            purpose=_purpose("typed_rig_output_slots", "raised_typed_rig_output_slot"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="rig_component_library.cycle_guards",
            parameters={
                "radius_cm": 0.6,
                "path": ((-_RIG_COMPONENT_WIDTH_CM * 0.5, 6.0, -_RIG_COMPONENT_DEPTH_CM * 0.5), (_RIG_COMPONENT_WIDTH_CM * 0.5, 6.0, -_RIG_COMPONENT_DEPTH_CM * 0.5), (_RIG_COMPONENT_WIDTH_CM * 0.5, 74.0, -_RIG_COMPONENT_DEPTH_CM * 0.5), (-_RIG_COMPONENT_WIDTH_CM * 0.5, 74.0, -_RIG_COMPONENT_DEPTH_CM * 0.5), (-_RIG_COMPONENT_WIDTH_CM * 0.5, 6.0, -_RIG_COMPONENT_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("component_cycle_guards", "swept_component_cycle_guard_frame"),
        ),
    )
    nodes = (
        _node("recipe.rig_component_catalog", "panel"),
        _node("recipe.rig_component_spine", "rail"),
        _node("recipe.rig_component_limbs", "rail"),
        _node("recipe.rig_component_digits", "fastener"),
        _node("recipe.rig_component_mech_joints", "hinge"),
        _node("recipe.rig_component_wing_tentacle", "rail"),
        _node("recipe.rig_component_connectors", "socket"),
        _node("recipe.rig_component_ik_fk", "handle"),
        _node("recipe.rig_component_typed_outputs", "material_zone"),
        _node("recipe.rig_component_cycle_guards", "guard"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="rig_component_library_system",
        family="rig_component_library_system",
        ops=ops,
    )
    return RecipeResult(
        family="rig_component_library_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _morph_target_database_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="morph_database.target_catalog",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "morph_target_catalog_cell",
                    {"profile_points": _rect_profile(10.0, 4.5), "height_cm": 0.28, "axis": "y"},
                    _purpose("morph_target_catalog", "catalog_cell_source"),
                ),
                "points": _morph_catalog_points(),
            },
            purpose=_purpose("morph_target_catalog", "copy_morph_target_catalog_cells"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="morph_database.facial_expressions",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "morph_expression_marker",
                    {"radius_cm": 1.7},
                    _purpose("facial_expression_set", "expression_marker_source"),
                ),
                "points": ((-38.0, 22.0, 20.0), (-22.0, 26.0, 24.0), (-6.0, 22.0, 26.0), (10.0, 26.0, 24.0), (26.0, 22.0, 20.0), (42.0, 18.0, 16.0)),
            },
            purpose=_purpose("facial_expression_set", "copy_facial_expression_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="morph_database.viseme_lipsync",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "morph_viseme_slot",
                    {"profile_points": _rect_profile(7.0, 3.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("viseme_or_lipsync_set", "viseme_slot_source"),
                ),
                "points": tuple((-42.0 + index * 12.0, 14.0, 26.0) for index in range(8)),
            },
            purpose=_purpose("viseme_or_lipsync_set", "copy_viseme_slots"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="morph_database.body_shape_deltas",
            parameters={
                "radius_cm": 0.55,
                "path": ((-_MORPH_DB_WIDTH_CM * 0.42, 30.0, 2.0), (-28.0, 24.0, 12.0), (0.0, 30.0, 18.0), (28.0, 24.0, 12.0), (_MORPH_DB_WIDTH_CM * 0.42, 30.0, 2.0)),
            },
            purpose=_purpose("body_shape_delta_set", "swept_body_shape_delta_curve"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="morph_database.corrective_shapes",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "morph_corrective_shape_patch",
                    {
                        "width_cm": 8.0,
                        "height_cm": 3.5,
                        "depth_cm": 5.0,
                        "corner_radii_cm": (0.8, 0.6, 1.0, 0.7, 0.5, 0.9, 0.6, 0.8),
                    },
                    _purpose("corrective_shape_set", "corrective_patch_source"),
                ),
                "points": _corrective_shape_points(),
            },
            purpose=_purpose("corrective_shape_set", "copy_corrective_shape_patches"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="morph_database.region_masks",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "morph_region_mask_chip",
                    {"profile_points": _rect_profile(9.0, 6.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("region_mask_bindings", "region_mask_chip_source"),
                ),
                "points": ((-48.0, 8.0, -2.0), (-30.0, 8.0, 2.0), (-12.0, 8.0, -2.0), (12.0, 8.0, 2.0), (30.0, 8.0, -2.0), (48.0, 8.0, 2.0)),
            },
            purpose=_purpose("region_mask_bindings", "copy_region_mask_bindings"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="morph_database.delta_vectors",
            parameters={
                "radius_cm": 0.45,
                "path": ((-46.0, 36.0, -6.0), (-24.0, 42.0, 2.0), (0.0, 36.0, 8.0), (24.0, 42.0, 2.0), (46.0, 36.0, -6.0)),
            },
            purpose=_purpose("delta_vector_channels", "swept_delta_vector_channels"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="morph_database.symmetry_rules",
            parameters={
                "radius_cm": 0.5,
                "path": ((0.0, 4.0, -_MORPH_DB_DEPTH_CM * 0.48), (0.0, 38.0, -_MORPH_DB_DEPTH_CM * 0.48)),
            },
            purpose=_purpose("symmetry_mirror_rules", "swept_mirror_axis_rule"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="morph_database.compatibility_guards",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "morph_topology_guard_ring",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.22, "axis": "y"},
                    _purpose("rig_anatomy_compatibility", "topology_guard_source"),
                ),
                "points": ((-44.0, 42.0, 30.0), (-14.0, 44.0, 32.0), (14.0, 44.0, 32.0), (44.0, 42.0, 30.0)),
            },
            purpose=_purpose("rig_anatomy_compatibility", "copy_rig_anatomy_compatibility_guards"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="morph_database.iteration_wear",
            parameters={"amount": 0.08, "morph_review_bias": 0.84},
            purpose=_purpose("morph_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.morph_target_catalog", "panel"),
        _node("recipe.morph_expression_set", "decal_zone"),
        _node("recipe.morph_viseme_set", "decal_zone"),
        _node("recipe.morph_body_deltas", "rail"),
        _node("recipe.morph_corrective_shapes", "panel"),
        _node("recipe.morph_region_masks", "material_zone"),
        _node("recipe.morph_delta_vectors", "rail"),
        _node("recipe.morph_symmetry_rules", "guard"),
        _node("recipe.morph_compatibility", "guard"),
        _node("recipe.morph_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="morph_target_database_system",
        family="morph_target_database_system",
        ops=ops,
    )
    return RecipeResult(
        family="morph_target_database_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _animation_library_binding_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="animation_binding.clip_catalog",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "animation_clip_card",
                    {"profile_points": _rect_profile(13.0, 5.0), "height_cm": 0.3, "axis": "y"},
                    _purpose("clip_catalog", "clip_card_source"),
                ),
                "points": _animation_clip_points(),
            },
            purpose=_purpose("clip_catalog", "copy_animation_clip_catalog"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="animation_binding.pose_library",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "animation_pose_anchor",
                    {"radius_cm": 1.6},
                    _purpose("pose_library", "pose_anchor_source"),
                ),
                "points": ((-44.0, 20.0, 18.0), (-26.0, 24.0, 22.0), (-8.0, 20.0, 24.0), (10.0, 24.0, 22.0), (28.0, 20.0, 18.0), (46.0, 16.0, 14.0)),
            },
            purpose=_purpose("pose_library", "copy_pose_library_anchors"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="animation_binding.locomotion_states",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "locomotion_state_ring",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.22, "axis": "y"},
                    _purpose("locomotion_state_set", "locomotion_state_source"),
                ),
                "points": ((-50.0, 36.0, 22.0), (-25.0, 40.0, 26.0), (0.0, 42.0, 28.0), (25.0, 40.0, 26.0), (50.0, 36.0, 22.0)),
            },
            purpose=_purpose("locomotion_state_set", "copy_locomotion_state_rings"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="animation_binding.blend_tree",
            parameters={
                "radius_cm": 0.55,
                "path": ((-_ANIM_BIND_WIDTH_CM * 0.42, 26.0, 0.0), (-28.0, 36.0, 10.0), (0.0, 28.0, 20.0), (28.0, 36.0, 10.0), (_ANIM_BIND_WIDTH_CM * 0.42, 26.0, 0.0)),
            },
            purpose=_purpose("blend_tree_or_transition_graph", "swept_blend_tree_transition_graph"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="animation_binding.event_tracks",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "animation_event_marker",
                    {"profile_points": _rect_profile(4.0, 7.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("event_marker_tracks", "event_marker_source"),
                ),
                "points": _animation_event_points(),
            },
            purpose=_purpose("event_marker_tracks", "copy_event_marker_track"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="animation_binding.root_motion",
            parameters={
                "radius_cm": 0.65,
                "path": ((-50.0, 8.0, -2.0), (-24.0, 12.0, 8.0), (0.0, 8.0, 16.0), (24.0, 12.0, 8.0), (50.0, 8.0, -2.0)),
            },
            purpose=_purpose("root_motion_channels", "swept_root_motion_trajectory"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="animation_binding.rig_slots",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "animation_rig_binding_socket",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("rig_binding_slots", "rig_binding_socket_source"),
                ),
                "points": ((-_ANIM_BIND_WIDTH_CM * 0.5, 18.0, -12.0), (_ANIM_BIND_WIDTH_CM * 0.5, 18.0, -12.0), (-18.0, 34.0, -18.0), (18.0, 34.0, -18.0)),
            },
            purpose=_purpose("rig_binding_slots", "copy_rig_binding_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="animation_binding.additive_layers",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "animation_additive_layer",
                    {"profile_points": _rect_profile(28.0, 3.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("additive_layer_stack", "additive_layer_source"),
                ),
                "points": ((-30.0, 44.0, -36.0), (0.0, 48.0, -36.0), (30.0, 44.0, -36.0)),
            },
            purpose=_purpose("additive_layer_stack", "copy_additive_layer_stack"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="animation_binding.preview_timing",
            parameters={
                "profile_polygon": _rect_profile(54.0, 7.0),
                "extrude_height_cm": 0.28,
                "axis": "y",
                "center": (0.0, 4.0, _ANIM_BIND_DEPTH_CM * 0.46),
            },
            purpose=_purpose("preview_or_timing_outputs", "raised_timing_preview_strip"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="animation_binding.iteration_wear",
            parameters={"amount": 0.08, "animation_binding_review_bias": 0.82},
            purpose=_purpose("animation_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.animation_clip_catalog", "panel"),
        _node("recipe.animation_pose_library", "decal_zone"),
        _node("recipe.animation_locomotion_states", "rail"),
        _node("recipe.animation_blend_tree", "rail"),
        _node("recipe.animation_event_tracks", "fastener"),
        _node("recipe.animation_root_motion", "rail"),
        _node("recipe.animation_rig_bindings", "socket"),
        _node("recipe.animation_additive_layers", "material_zone"),
        _node("recipe.animation_preview_timing", "panel"),
        _node("recipe.animation_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="animation_library_binding_system",
        family="animation_library_binding_system",
        ops=ops,
    )
    return RecipeResult(
        family="animation_library_binding_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _retargeting_pack_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="retargeting_pack.source_target_skeletons",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "retarget_skeleton_endpoint",
                    {
                        "width_cm": 18.0,
                        "height_cm": 32.0,
                        "depth_cm": 12.0,
                        "corner_radii_cm": (2.0, 1.5, 2.2, 1.7, 1.0, 1.8, 1.2, 1.6),
                    },
                    _purpose("source_target_skeletons", "skeleton_endpoint_source"),
                ),
                "points": ((-_RETARGET_PACK_WIDTH_CM * 0.36, 28.0, 0.0), (_RETARGET_PACK_WIDTH_CM * 0.36, 28.0, 0.0)),
            },
            purpose=_purpose("source_target_skeletons", "copy_source_target_skeleton_endpoints"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="retargeting_pack.bone_mapping",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "retarget_bone_map_cell",
                    {"profile_points": _rect_profile(8.0, 3.5), "height_cm": 0.28, "axis": "y"},
                    _purpose("bone_mapping_table", "bone_map_cell_source"),
                ),
                "points": _retarget_bone_map_points(),
            },
            purpose=_purpose("bone_mapping_table", "copy_bone_mapping_cells"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="retargeting_pack.rest_pose_alignment",
            parameters={
                "radius_cm": 0.55,
                "path": ((-_RETARGET_PACK_WIDTH_CM * 0.42, 18.0, -8.0), (-18.0, 40.0, -2.0), (0.0, 46.0, 4.0), (18.0, 40.0, -2.0), (_RETARGET_PACK_WIDTH_CM * 0.42, 18.0, -8.0)),
            },
            purpose=_purpose("rest_pose_alignment", "swept_rest_pose_alignment_axes"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="retargeting_pack.scale_compensation",
            parameters={
                "radius_cm": 0.5,
                "path": ((-50.0, 8.0, 12.0), (-24.0, 14.0, 22.0), (0.0, 8.0, 28.0), (24.0, 14.0, 22.0), (50.0, 8.0, 12.0)),
            },
            purpose=_purpose("scale_proportion_compensation", "swept_scale_compensation_curve"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="retargeting_pack.coordinate_space",
            parameters={
                "profile_polygon": _rect_profile(42.0, 8.0),
                "extrude_height_cm": 0.26,
                "axis": "y",
                "center": (-_RETARGET_PACK_WIDTH_CM * 0.28, 54.0, _RETARGET_PACK_DEPTH_CM * 0.46),
            },
            purpose=_purpose("coordinate_space_conversion", "raised_coordinate_space_badge"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="retargeting_pack.ik_pole_remaps",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "retarget_ik_pole_handle",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("ik_pole_remap", "ik_pole_handle_source"),
                ),
                "points": ((-42.0, 30.0, 28.0), (-14.0, 36.0, 32.0), (14.0, 36.0, 32.0), (42.0, 30.0, 28.0)),
            },
            purpose=_purpose("ik_pole_remap", "copy_ik_pole_remap_handles"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="retargeting_pack.root_motion",
            parameters={
                "radius_cm": 0.65,
                "path": ((-48.0, 4.0, -28.0), (-18.0, 10.0, -18.0), (0.0, 6.0, -8.0), (18.0, 10.0, -18.0), (48.0, 4.0, -28.0)),
            },
            purpose=_purpose("root_motion_retargeting", "swept_root_motion_retarget_path"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="retargeting_pack.constraint_transfer",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "retarget_constraint_limit_ring",
                    {"major_radius_cm": 3.2, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("constraint_or_limit_transfer", "constraint_limit_source"),
                ),
                "points": ((-34.0, 50.0, -32.0), (-10.0, 52.0, -34.0), (10.0, 52.0, -34.0), (34.0, 50.0, -32.0)),
            },
            purpose=_purpose("constraint_or_limit_transfer", "copy_constraint_limit_rings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="retargeting_pack.compatibility_guards",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "retarget_validation_guard",
                    {"major_radius_cm": 3.4, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("compatibility_validation_guards", "validation_guard_source"),
                ),
                "points": _retarget_guard_points(),
            },
            purpose=_purpose("compatibility_validation_guards", "copy_compatibility_validation_guards"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="retargeting_pack.iteration_wear",
            parameters={"amount": 0.08, "retargeting_review_bias": 0.83},
            purpose=_purpose("retarget_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.retarget_source_target_skeletons", "primary_volume"),
        _node("recipe.retarget_bone_mapping", "panel"),
        _node("recipe.retarget_rest_pose_alignment", "rail"),
        _node("recipe.retarget_scale_compensation", "material_zone"),
        _node("recipe.retarget_coordinate_space", "guard"),
        _node("recipe.retarget_ik_poles", "handle"),
        _node("recipe.retarget_root_motion", "rail"),
        _node("recipe.retarget_constraints", "guard"),
        _node("recipe.retarget_validation", "guard"),
        _node("recipe.retarget_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="retargeting_pack_system",
        family="retargeting_pack_system",
        ops=ops,
    )
    return RecipeResult(
        family="retargeting_pack_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _character_equipment_binding_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="equipment_binding.body_slot_map",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "equipment_body_slot",
                    {"profile_points": _rect_profile(12.0, 6.0), "height_cm": 0.3, "axis": "y"},
                    _purpose("body_slot_map", "body_slot_source"),
                ),
                "points": _equipment_slot_points(),
            },
            purpose=_purpose("body_slot_map", "copy_body_slot_map"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="equipment_binding.weapon_sockets",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "equipment_weapon_socket",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("weapon_or_tool_sockets", "weapon_socket_source"),
                ),
                "points": ((-42.0, 38.0, -30.0), (42.0, 38.0, -30.0), (-34.0, 16.0, -28.0), (34.0, 16.0, -28.0)),
            },
            purpose=_purpose("weapon_or_tool_sockets", "copy_weapon_tool_sockets"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="equipment_binding.armor_layers",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "equipment_armor_layer",
                    {
                        "width_cm": 18.0,
                        "height_cm": 5.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (1.2, 0.9, 1.3, 1.0, 0.7, 1.1, 0.8, 1.0),
                    },
                    _purpose("armor_or_outfit_layers", "armor_layer_source"),
                ),
                "points": ((0.0, 52.0, 0.0), (-18.0, 42.0, 2.0), (18.0, 42.0, 2.0), (0.0, 30.0, 4.0), (-14.0, 18.0, 2.0), (14.0, 18.0, 2.0)),
            },
            purpose=_purpose("armor_or_outfit_layers", "copy_armor_outfit_layers"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="equipment_binding.offset_frames",
            parameters={
                "radius_cm": 0.5,
                "path": ((-_EQUIPMENT_BIND_WIDTH_CM * 0.42, 8.0, -6.0), (-26.0, 26.0, 8.0), (0.0, 34.0, 14.0), (26.0, 26.0, 8.0), (_EQUIPMENT_BIND_WIDTH_CM * 0.42, 8.0, -6.0)),
            },
            purpose=_purpose("attachment_offset_frames", "swept_attachment_offset_frames"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="equipment_binding.clearance_volumes",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "equipment_clearance_volume",
                    {
                        "width_cm": _EQUIPMENT_BIND_WIDTH_CM,
                        "height_cm": _EQUIPMENT_BIND_HEIGHT_CM,
                        "depth_cm": _EQUIPMENT_BIND_DEPTH_CM,
                        "center": (0.0, _EQUIPMENT_BIND_HEIGHT_CM * 0.5, 0.0),
                    },
                    _purpose("clearance_or_collision_volumes", "clearance_volume_source"),
                ),
                "width_cm": 1.2,
                "segments": 4,
            },
            purpose=_purpose("clearance_or_collision_volumes", "polybeveled_clearance_volume"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="equipment_binding.loadout_variants",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "equipment_loadout_card",
                    {"profile_points": _rect_profile(14.0, 5.0), "height_cm": 0.26, "axis": "y"},
                    _purpose("loadout_variant_sets", "loadout_card_source"),
                ),
                "points": _equipment_loadout_points(),
            },
            purpose=_purpose("loadout_variant_sets", "copy_loadout_variant_cards"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="equipment_binding.rig_anatomy_rules",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "equipment_rig_anatomy_rule",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.22, "axis": "y"},
                    _purpose("rig_anatomy_binding_rules", "rig_anatomy_rule_source"),
                ),
                "points": ((-42.0, 60.0, 28.0), (-14.0, 62.0, 32.0), (14.0, 62.0, 32.0), (42.0, 60.0, 28.0)),
            },
            purpose=_purpose("rig_anatomy_binding_rules", "copy_rig_anatomy_binding_rules"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="equipment_binding.visibility_masks",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "equipment_visibility_mask",
                    {"profile_points": _rect_profile(9.0, 4.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("visibility_or_state_masks", "visibility_mask_source"),
                ),
                "points": ((-48.0, 8.0, 22.0), (-30.0, 8.0, 24.0), (-12.0, 8.0, 22.0), (12.0, 8.0, 24.0), (30.0, 8.0, 22.0), (48.0, 8.0, 24.0)),
            },
            purpose=_purpose("visibility_or_state_masks", "copy_visibility_state_masks"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="equipment_binding.failure_guards",
            parameters={
                "radius_cm": 0.6,
                "path": ((-_EQUIPMENT_BIND_WIDTH_CM * 0.5, 4.0, -_EQUIPMENT_BIND_DEPTH_CM * 0.5), (_EQUIPMENT_BIND_WIDTH_CM * 0.5, 4.0, -_EQUIPMENT_BIND_DEPTH_CM * 0.5), (_EQUIPMENT_BIND_WIDTH_CM * 0.5, 68.0, -_EQUIPMENT_BIND_DEPTH_CM * 0.5), (-_EQUIPMENT_BIND_WIDTH_CM * 0.5, 68.0, -_EQUIPMENT_BIND_DEPTH_CM * 0.5), (-_EQUIPMENT_BIND_WIDTH_CM * 0.5, 4.0, -_EQUIPMENT_BIND_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("compatibility_or_failure_guards", "swept_equipment_fit_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="equipment_binding.iteration_wear",
            parameters={"amount": 0.08, "equipment_fit_review_bias": 0.82},
            purpose=_purpose("equipment_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.equipment_body_slots", "panel"),
        _node("recipe.equipment_weapon_sockets", "socket"),
        _node("recipe.equipment_armor_layers", "material_zone"),
        _node("recipe.equipment_offset_frames", "rail"),
        _node("recipe.equipment_clearance", "guard"),
        _node("recipe.equipment_loadout_variants", "decal_zone"),
        _node("recipe.equipment_rig_anatomy_rules", "socket"),
        _node("recipe.equipment_visibility_masks", "decal_zone"),
        _node("recipe.equipment_failure_guards", "guard"),
        _node("recipe.equipment_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="character_equipment_binding_system",
        family="character_equipment_binding_system",
        ops=ops,
    )
    return RecipeResult(
        family="character_equipment_binding_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _gameplay_animation_controller_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_animation_controller.input_actions",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "controller_input_action",
                    {"profile_points": _rect_profile(11.0, 5.0), "height_cm": 0.28, "axis": "y"},
                    _purpose("input_action_map", "input_action_source"),
                ),
                "points": tuple((-52.0 + index * 13.0, 26.0, -36.0) for index in range(9)),
            },
            purpose=_purpose("input_action_map", "copy_input_action_map"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_animation_controller.state_graph",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "controller_state_node",
                    {"major_radius_cm": 3.1, "minor_radius_cm": 0.22, "axis": "y"},
                    _purpose("controller_state_graph", "controller_state_source"),
                ),
                "points": _controller_state_points(),
            },
            purpose=_purpose("controller_state_graph", "copy_controller_state_nodes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_animation_controller.parameters",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "controller_parameter_knob",
                    {"radius_cm": 1.45},
                    _purpose("animation_parameter_set", "parameter_knob_source"),
                ),
                "points": _controller_parameter_points(),
            },
            purpose=_purpose("animation_parameter_set", "copy_animation_parameter_knobs"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="gameplay_animation_controller.transition_rules",
            parameters={
                "radius_cm": 0.52,
                "path": ((-_GAMEPLAY_CTRL_WIDTH_CM * 0.42, 18.0, -8.0), (-30.0, 28.0, 4.0), (0.0, 20.0, 18.0), (30.0, 28.0, 4.0), (_GAMEPLAY_CTRL_WIDTH_CM * 0.42, 18.0, -8.0)),
            },
            purpose=_purpose("transition_rule_table", "swept_transition_rule_graph"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="gameplay_animation_controller.locomotion_blends",
            parameters={
                "radius_cm": 0.6,
                "path": ((-52.0, 6.0, 10.0), (-26.0, 12.0, 22.0), (0.0, 6.0, 30.0), (26.0, 12.0, 22.0), (52.0, 6.0, 10.0)),
            },
            purpose=_purpose("locomotion_blend_controls", "swept_locomotion_blend_curve"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_animation_controller.combat_layers",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "controller_combat_layer",
                    {"profile_points": _rect_profile(24.0, 4.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("combat_or_ability_layers", "combat_layer_source"),
                ),
                "points": ((-36.0, 32.0, 28.0), (-12.0, 36.0, 32.0), (12.0, 36.0, 32.0), (36.0, 32.0, 28.0)),
            },
            purpose=_purpose("combat_or_ability_layers", "copy_combat_ability_layers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_animation_controller.event_outputs",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "controller_event_output",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("event_output_bindings", "event_output_source"),
                ),
                "points": ((-48.0, 10.0, -2.0), (-24.0, 12.0, 2.0), (0.0, 10.0, 4.0), (24.0, 12.0, 2.0), (48.0, 10.0, -2.0)),
            },
            purpose=_purpose("event_output_bindings", "copy_event_output_bindings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="gameplay_animation_controller.motion_matching",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "controller_motion_matching_slot",
                    {"profile_points": _rect_profile(10.0, 6.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("motion_matching_slots", "motion_matching_slot_source"),
                ),
                "points": ((-44.0, 4.0, -26.0), (-22.0, 4.0, -30.0), (0.0, 4.0, -32.0), (22.0, 4.0, -30.0), (44.0, 4.0, -26.0)),
            },
            purpose=_purpose("motion_matching_slots", "copy_motion_matching_slots"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="gameplay_animation_controller.reachability_guards",
            parameters={
                "radius_cm": 0.6,
                "path": ((-_GAMEPLAY_CTRL_WIDTH_CM * 0.5, 2.0, -_GAMEPLAY_CTRL_DEPTH_CM * 0.5), (_GAMEPLAY_CTRL_WIDTH_CM * 0.5, 2.0, -_GAMEPLAY_CTRL_DEPTH_CM * 0.5), (_GAMEPLAY_CTRL_WIDTH_CM * 0.5, 32.0, -_GAMEPLAY_CTRL_DEPTH_CM * 0.5), (-_GAMEPLAY_CTRL_WIDTH_CM * 0.5, 32.0, -_GAMEPLAY_CTRL_DEPTH_CM * 0.5), (-_GAMEPLAY_CTRL_WIDTH_CM * 0.5, 2.0, -_GAMEPLAY_CTRL_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("reachability_or_dead_state_guards", "swept_controller_reachability_guard"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="gameplay_animation_controller.iteration_wear",
            parameters={"amount": 0.08, "controller_tuning_review_bias": 0.84},
            purpose=_purpose("controller_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.controller_input_actions", "panel"),
        _node("recipe.controller_state_graph", "rail"),
        _node("recipe.controller_parameters", "fastener"),
        _node("recipe.controller_transition_rules", "guard"),
        _node("recipe.controller_locomotion_blends", "rail"),
        _node("recipe.controller_combat_layers", "material_zone"),
        _node("recipe.controller_event_outputs", "socket"),
        _node("recipe.controller_motion_matching", "panel"),
        _node("recipe.controller_reachability_guards", "guard"),
        _node("recipe.controller_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="gameplay_animation_controller_system",
        family="gameplay_animation_controller_system",
        ops=ops,
    )
    return RecipeResult(
        family="gameplay_animation_controller_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _procedural_facial_rig_pack_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polyextrude",
            target="facial_rig.control_board",
            parameters={
                "profile_polygon": _rect_profile(_FACIAL_RIG_WIDTH_CM, 16.0),
                "extrude_height_cm": 0.32,
                "axis": "y",
                "center": (0.0, 8.0, -_FACIAL_RIG_DEPTH_CM * 0.42),
            },
            purpose=_purpose("facial_control_board", "raised_facial_control_board"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="facial_rig.jaw_mouth_controls",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "facial_jaw_mouth_control",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("jaw_and_mouth_controls", "jaw_mouth_control_source"),
                ),
                "points": ((-24.0, 20.0, -30.0), (-8.0, 16.0, -34.0), (8.0, 16.0, -34.0), (24.0, 20.0, -30.0)),
            },
            purpose=_purpose("jaw_and_mouth_controls", "copy_jaw_mouth_controls"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="facial_rig.eye_lid_controls",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "facial_eye_lid_control",
                    {"major_radius_cm": 2.7, "minor_radius_cm": 0.22, "axis": "y"},
                    _purpose("eye_aim_and_lid_controls", "eye_lid_control_source"),
                ),
                "points": ((-22.0, 34.0, -32.0), (-10.0, 38.0, -34.0), (10.0, 38.0, -34.0), (22.0, 34.0, -32.0)),
            },
            purpose=_purpose("eye_aim_and_lid_controls", "copy_eye_lid_controls"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="facial_rig.brow_cheek_controls",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "facial_brow_cheek_control",
                    {"radius_cm": 1.75},
                    _purpose("brow_and_cheek_controls", "brow_cheek_control_source"),
                ),
                "points": _facial_control_points(),
            },
            purpose=_purpose("brow_and_cheek_controls", "copy_brow_cheek_controls"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="facial_rig.viseme_expression_links",
            parameters={
                "radius_cm": 0.5,
                "path": ((-_FACIAL_RIG_WIDTH_CM * 0.42, 28.0, 4.0), (-24.0, 36.0, 16.0), (0.0, 30.0, 24.0), (24.0, 36.0, 16.0), (_FACIAL_RIG_WIDTH_CM * 0.42, 28.0, 4.0)),
            },
            purpose=_purpose("viseme_expression_links", "swept_viseme_expression_links"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="facial_rig.morph_driver_bindings",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "facial_morph_driver_binding",
                    {"profile_points": _rect_profile(10.0, 4.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("morph_driver_bindings", "morph_driver_binding_source"),
                ),
                "points": tuple((-42.0 + index * 12.0, 46.0, 26.0) for index in range(8)),
            },
            purpose=_purpose("morph_driver_bindings", "copy_morph_driver_bindings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="facial_rig.face_sdf_masks",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "facial_face_sdf_mask_binding",
                    {"profile_points": _rect_profile(9.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("face_sdf_mask_bindings", "face_sdf_mask_binding_source"),
                ),
                "points": ((-36.0, 10.0, 28.0), (-18.0, 12.0, 32.0), (0.0, 10.0, 34.0), (18.0, 12.0, 32.0), (36.0, 10.0, 28.0)),
            },
            purpose=_purpose("face_sdf_mask_bindings", "copy_face_sdf_mask_bindings"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="facial_rig.range_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_FACIAL_RIG_WIDTH_CM * 0.5, 6.0, -_FACIAL_RIG_DEPTH_CM * 0.5), (_FACIAL_RIG_WIDTH_CM * 0.5, 6.0, -_FACIAL_RIG_DEPTH_CM * 0.5), (_FACIAL_RIG_WIDTH_CM * 0.5, 54.0, -_FACIAL_RIG_DEPTH_CM * 0.5), (-_FACIAL_RIG_WIDTH_CM * 0.5, 54.0, -_FACIAL_RIG_DEPTH_CM * 0.5), (-_FACIAL_RIG_WIDTH_CM * 0.5, 6.0, -_FACIAL_RIG_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("range_limit_guards", "swept_facial_range_guard_frame"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="facial_rig.preview_poses",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "facial_preview_pose_tile",
                    {"profile_points": _rect_profile(12.0, 7.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("preview_pose_outputs", "preview_pose_tile_source"),
                ),
                "points": ((-36.0, 4.0, 24.0), (-12.0, 4.0, 28.0), (12.0, 4.0, 28.0), (36.0, 4.0, 24.0)),
            },
            purpose=_purpose("preview_pose_outputs", "copy_preview_pose_outputs"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="facial_rig.iteration_wear",
            parameters={"amount": 0.08, "facial_rig_review_bias": 0.84},
            purpose=_purpose("facial_rig_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.facial_control_board", "panel"),
        _node("recipe.facial_jaw_mouth", "handle"),
        _node("recipe.facial_eye_lids", "socket"),
        _node("recipe.facial_brow_cheek", "handle"),
        _node("recipe.facial_viseme_links", "rail"),
        _node("recipe.facial_morph_bindings", "socket"),
        _node("recipe.facial_sdf_masks", "material_zone"),
        _node("recipe.facial_range_guards", "guard"),
        _node("recipe.facial_preview_poses", "panel"),
        _node("recipe.facial_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="procedural_facial_rig_pack_system",
        family="procedural_facial_rig_pack_system",
        ops=ops,
    )
    return RecipeResult(
        family="procedural_facial_rig_pack_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _hair_program_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="hair_program.scalp_groom_regions",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "hair_scalp_groom_region",
                    {"profile_points": _rect_profile(12.0, 6.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("scalp_or_groom_regions", "scalp_groom_region_source"),
                ),
                "points": ((-36.0, 40.0, -24.0), (-18.0, 44.0, -28.0), (0.0, 46.0, -30.0), (18.0, 44.0, -28.0), (36.0, 40.0, -24.0)),
            },
            purpose=_purpose("scalp_or_groom_regions", "copy_scalp_groom_regions"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="hair_program.strand_grammar",
            parameters={
                "radius_cm": 0.38,
                "path": ((-_HAIR_PROGRAM_WIDTH_CM * 0.42, 22.0, -8.0), (-30.0, 42.0, 8.0), (0.0, 48.0, 20.0), (30.0, 42.0, 8.0), (_HAIR_PROGRAM_WIDTH_CM * 0.42, 22.0, -8.0)),
            },
            purpose=_purpose("strand_grammar", "swept_strand_grammar_guide"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="hair_program.root_density",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "hair_root_density_sample",
                    {"radius_cm": 1.05},
                    _purpose("root_density_masks", "root_density_sample_source"),
                ),
                "points": _hair_root_points(),
            },
            purpose=_purpose("root_density_masks", "copy_root_density_samples"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="hair_program.length_distribution",
            parameters={
                "radius_cm": 0.48,
                "path": ((-46.0, 10.0, 16.0), (-24.0, 18.0, 28.0), (0.0, 10.0, 36.0), (24.0, 18.0, 28.0), (46.0, 10.0, 16.0)),
            },
            purpose=_purpose("length_distribution_controls", "swept_length_distribution_curve"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="hair_program.wave_curl_controls",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "hair_wave_curl_control",
                    {"major_radius_cm": 2.6, "minor_radius_cm": 0.2, "axis": "y"},
                    _purpose("wave_or_curl_controls", "wave_curl_control_source"),
                ),
                "points": ((-44.0, 30.0, 26.0), (-18.0, 34.0, 32.0), (18.0, 34.0, 32.0), (44.0, 30.0, 26.0)),
            },
            purpose=_purpose("wave_or_curl_controls", "copy_wave_curl_controls"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="hair_program.hair_cards",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "hair_card_output",
                    {"profile_points": _rect_profile(8.0, 22.0), "height_cm": 0.18, "axis": "y"},
                    _purpose("hair_card_outputs", "hair_card_source"),
                ),
                "points": _hair_card_points(),
            },
            purpose=_purpose("hair_card_outputs", "copy_hair_card_outputs"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="hair_program.strand_outputs",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "hair_strand_output_port",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("strand_output_ports", "strand_output_port_source"),
                ),
                "points": ((-42.0, 6.0, -30.0), (-14.0, 6.0, -34.0), (14.0, 6.0, -34.0), (42.0, 6.0, -30.0)),
            },
            purpose=_purpose("strand_output_ports", "copy_strand_output_ports"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="hair_program.color_gradient",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "hair_color_gradient_cell",
                    {"profile_points": _rect_profile(10.0, 4.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("color_gradient_controls", "color_gradient_cell_source"),
                ),
                "points": tuple((-42.0 + index * 12.0, 50.0, 30.0) for index in range(8)),
            },
            purpose=_purpose("color_gradient_controls", "copy_color_gradient_cells"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="hair_program.collision_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_HAIR_PROGRAM_WIDTH_CM * 0.5, 4.0, -_HAIR_PROGRAM_DEPTH_CM * 0.5), (_HAIR_PROGRAM_WIDTH_CM * 0.5, 4.0, -_HAIR_PROGRAM_DEPTH_CM * 0.5), (_HAIR_PROGRAM_WIDTH_CM * 0.5, 50.0, -_HAIR_PROGRAM_DEPTH_CM * 0.5), (-_HAIR_PROGRAM_WIDTH_CM * 0.5, 50.0, -_HAIR_PROGRAM_DEPTH_CM * 0.5), (-_HAIR_PROGRAM_WIDTH_CM * 0.5, 4.0, -_HAIR_PROGRAM_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("collision_or_clearance_guards", "swept_hair_collision_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="hair_program.iteration_wear",
            parameters={"amount": 0.08, "hair_groom_review_bias": 0.83},
            purpose=_purpose("hair_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.hair_scalp_groom_regions", "material_zone"),
        _node("recipe.hair_strand_grammar", "rail"),
        _node("recipe.hair_root_density", "decal_zone"),
        _node("recipe.hair_length_distribution", "rail"),
        _node("recipe.hair_wave_curl", "fastener"),
        _node("recipe.hair_card_outputs", "panel"),
        _node("recipe.hair_strand_outputs", "socket"),
        _node("recipe.hair_color_gradient", "material_zone"),
        _node("recipe.hair_collision_guards", "guard"),
        _node("recipe.hair_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="hair_program_system",
        family="hair_program_system",
        ops=ops,
    )
    return RecipeResult(
        family="hair_program_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _cloth_fabric_simulation_program_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="cloth_fabric_sim.fabric_domain",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "cloth_fabric_domain_panel",
                    {
                        "width_cm": _CLOTH_SIM_WIDTH_CM,
                        "height_cm": 4.0,
                        "depth_cm": _CLOTH_SIM_DEPTH_CM,
                        "center": (0.0, 34.0, 0.0),
                        "corner_radii_cm": (2.0, 1.6, 2.2, 1.8, 1.4, 2.0, 1.5, 1.9),
                    },
                    _purpose("fabric_domain_or_panel_set", "fabric_domain_panel_source"),
                ),
                "width_cm": 0.6,
                "segments": 4,
            },
            purpose=_purpose("fabric_domain_or_panel_set", "polybeveled_fabric_domain_panel"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_fabric_sim.params",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cloth_param_cell",
                    {"profile_points": _rect_profile(9.0, 4.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("mass_stiffness_damping_params", "cloth_param_cell_source"),
                ),
                "points": _cloth_param_points(),
            },
            purpose=_purpose("mass_stiffness_damping_params", "copy_mass_stiffness_damping_params"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_fabric_sim.pin_constraints",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "cloth_pin_constraint",
                    {"major_radius_cm": 2.8, "minor_radius_cm": 0.22, "axis": "y"},
                    _purpose("pin_or_anchor_constraints", "pin_constraint_source"),
                ),
                "points": _cloth_pin_points(),
            },
            purpose=_purpose("pin_or_anchor_constraints", "copy_pin_anchor_constraints"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_fabric_sim.collision_volumes",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "cloth_collision_body",
                    {
                        "width_cm": 18.0,
                        "height_cm": 14.0,
                        "depth_cm": 12.0,
                        "corner_radii_cm": (2.0, 1.4, 2.4, 1.6, 1.2, 2.0, 1.3, 1.8),
                    },
                    _purpose("collision_or_body_volumes", "collision_body_source"),
                ),
                "points": ((-36.0, 20.0, 0.0), (-12.0, 18.0, 6.0), (12.0, 18.0, 6.0), (36.0, 20.0, 0.0)),
            },
            purpose=_purpose("collision_or_body_volumes", "copy_collision_body_volumes"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cloth_fabric_sim.force_fields",
            parameters={
                "radius_cm": 0.5,
                "path": ((-_CLOTH_SIM_WIDTH_CM * 0.42, 16.0, -10.0), (-28.0, 30.0, 2.0), (0.0, 22.0, 16.0), (28.0, 30.0, 2.0), (_CLOTH_SIM_WIDTH_CM * 0.42, 16.0, -10.0)),
            },
            purpose=_purpose("gravity_wind_force_fields", "swept_gravity_wind_force_fields"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_fabric_sim.solve_passes",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "cloth_solve_iteration_tick",
                    {"radius_cm": 1.25},
                    _purpose("settling_or_solve_passes", "solve_iteration_tick_source"),
                ),
                "points": tuple((-48.0 + index * 12.0, 4.0, -30.0) for index in range(9)),
            },
            purpose=_purpose("settling_or_solve_passes", "copy_settling_solve_pass_ticks"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cloth_fabric_sim.wrinkle_folds",
            parameters={
                "radius_cm": 0.36,
                "path": ((-48.0, 38.0, 10.0), (-24.0, 30.0, 24.0), (0.0, 36.0, 30.0), (24.0, 30.0, 24.0), (48.0, 38.0, 10.0)),
            },
            purpose=_purpose("wrinkle_fold_outputs", "swept_wrinkle_fold_outputs"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_fabric_sim.material_zones",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cloth_material_pattern_zone",
                    {"profile_points": _rect_profile(14.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("material_pattern_zones", "material_pattern_zone_source"),
                ),
                "points": ((-42.0, 48.0, 28.0), (-14.0, 50.0, 32.0), (14.0, 50.0, 32.0), (42.0, 48.0, 28.0)),
            },
            purpose=_purpose("material_pattern_zones", "copy_material_pattern_zones"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cloth_fabric_sim.solver_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_CLOTH_SIM_WIDTH_CM * 0.5, 4.0, -_CLOTH_SIM_DEPTH_CM * 0.5), (_CLOTH_SIM_WIDTH_CM * 0.5, 4.0, -_CLOTH_SIM_DEPTH_CM * 0.5), (_CLOTH_SIM_WIDTH_CM * 0.5, 48.0, -_CLOTH_SIM_DEPTH_CM * 0.5), (-_CLOTH_SIM_WIDTH_CM * 0.5, 48.0, -_CLOTH_SIM_DEPTH_CM * 0.5), (-_CLOTH_SIM_WIDTH_CM * 0.5, 4.0, -_CLOTH_SIM_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("solver_validation_guards", "swept_cloth_solver_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="cloth_fabric_sim.iteration_wear",
            parameters={"amount": 0.08, "cloth_sim_review_bias": 0.83},
            purpose=_purpose("cloth_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.cloth_fabric_domain", "primary_volume"),
        _node("recipe.cloth_params", "decal_zone"),
        _node("recipe.cloth_pin_constraints", "socket"),
        _node("recipe.cloth_collision_volumes", "guard"),
        _node("recipe.cloth_force_fields", "rail"),
        _node("recipe.cloth_solve_passes", "fastener"),
        _node("recipe.cloth_wrinkle_folds", "rail"),
        _node("recipe.cloth_material_zones", "material_zone"),
        _node("recipe.cloth_solver_guards", "guard"),
        _node("recipe.cloth_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="cloth_fabric_simulation_program_system",
        family="cloth_fabric_simulation_program_system",
        ops=ops,
    )
    return RecipeResult(
        family="cloth_fabric_simulation_program_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _fluid_forward_volume_program_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="fluid_forward.volume_domain",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "fluid_volume_domain",
                    {
                        "width_cm": _FLUID_FORWARD_WIDTH_CM,
                        "height_cm": _FLUID_FORWARD_HEIGHT_CM,
                        "depth_cm": _FLUID_FORWARD_DEPTH_CM,
                        "center": (0.0, _FLUID_FORWARD_HEIGHT_CM * 0.5, 0.0),
                    },
                    _purpose("fluid_volume_domain", "fluid_volume_domain_source"),
                ),
                "width_cm": 1.3,
                "segments": 4,
            },
            purpose=_purpose("fluid_volume_domain", "polybeveled_fluid_volume_domain"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="fluid_forward.channels",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "fluid_channel_lobe",
                    {"radius_cm": 2.0},
                    _purpose("density_temperature_velocity_channels", "channel_lobe_source"),
                ),
                "points": _fluid_channel_points(),
            },
            purpose=_purpose("density_temperature_velocity_channels", "copy_density_temperature_velocity_channels"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="fluid_forward.emitters",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "fluid_emitter_source",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("emitter_or_source_set", "emitter_source"),
                ),
                "points": _fluid_emitter_points(),
            },
            purpose=_purpose("emitter_or_source_set", "copy_fluid_emitters"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="fluid_forward.advection_fields",
            parameters={
                "radius_cm": 0.6,
                "path": ((-_FLUID_FORWARD_WIDTH_CM * 0.42, 18.0, -10.0), (-30.0, 38.0, 4.0), (0.0, 28.0, 20.0), (30.0, 38.0, 4.0), (_FLUID_FORWARD_WIDTH_CM * 0.42, 18.0, -10.0)),
            },
            purpose=_purpose("advection_or_force_fields", "swept_advection_force_fields"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="fluid_forward.isosurface_controls",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "fluid_isosurface_threshold_band",
                    {"profile_points": _rect_profile(54.0, 4.0), "height_cm": 0.3, "axis": "y"},
                    _purpose("surface_or_isosurface_controls", "isosurface_threshold_band_source"),
                ),
                "distance_cm": 1.8,
                "axis": "z",
            },
            purpose=_purpose("surface_or_isosurface_controls", "raised_surface_threshold_band"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="fluid_forward.outputs",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "fluid_output_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("particle_or_mesh_outputs", "fluid_output_port_source"),
                ),
                "points": ((-48.0, 6.0, -34.0), (-16.0, 6.0, -38.0), (16.0, 6.0, -38.0), (48.0, 6.0, -34.0)),
            },
            purpose=_purpose("particle_or_mesh_outputs", "copy_particle_mesh_outputs"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="fluid_forward.cache_tiles",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "fluid_cache_tile",
                    {"profile_points": _rect_profile(12.0, 6.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("cache_or_sample_tiles", "cache_tile_source"),
                ),
                "points": tuple((-48.0 + index * 16.0, 12.0, 32.0) for index in range(7)),
            },
            purpose=_purpose("cache_or_sample_tiles", "copy_cache_sample_tiles"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="fluid_forward.boundary_guards",
            parameters={
                "radius_cm": 0.62,
                "path": ((-_FLUID_FORWARD_WIDTH_CM * 0.5, 4.0, -_FLUID_FORWARD_DEPTH_CM * 0.5), (_FLUID_FORWARD_WIDTH_CM * 0.5, 4.0, -_FLUID_FORWARD_DEPTH_CM * 0.5), (_FLUID_FORWARD_WIDTH_CM * 0.5, 60.0, -_FLUID_FORWARD_DEPTH_CM * 0.5), (-_FLUID_FORWARD_WIDTH_CM * 0.5, 60.0, -_FLUID_FORWARD_DEPTH_CM * 0.5), (-_FLUID_FORWARD_WIDTH_CM * 0.5, 4.0, -_FLUID_FORWARD_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("collision_boundary_guards", "swept_fluid_boundary_guard_frame"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="fluid_forward.material_regions",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "fluid_material_region",
                    {"profile_points": _rect_profile(14.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("fluid_style_material_regions", "fluid_material_region_source"),
                ),
                "points": ((-36.0, 54.0, -34.0), (-12.0, 56.0, -36.0), (12.0, 56.0, -36.0), (36.0, 54.0, -34.0)),
            },
            purpose=_purpose("fluid_style_material_regions", "copy_fluid_material_regions"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="fluid_forward.iteration_wear",
            parameters={"amount": 0.08, "fluid_solve_review_bias": 0.82},
            purpose=_purpose("fluid_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.fluid_volume_domain", "primary_volume"),
        _node("recipe.fluid_channels", "material_zone"),
        _node("recipe.fluid_emitters", "socket"),
        _node("recipe.fluid_advection_fields", "rail"),
        _node("recipe.fluid_isosurface_controls", "panel"),
        _node("recipe.fluid_outputs", "socket"),
        _node("recipe.fluid_cache_tiles", "panel"),
        _node("recipe.fluid_boundary_guards", "guard"),
        _node("recipe.fluid_material_regions", "material_zone"),
        _node("recipe.fluid_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="fluid_forward_volume_program_system",
        family="fluid_forward_volume_program_system",
        ops=ops,
    )
    return RecipeResult(
        family="fluid_forward_volume_program_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _construction_grammar_kit_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="construction_kit.module_catalog",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "construction_module_piece",
                    {
                        "width_cm": 14.0,
                        "height_cm": 10.0,
                        "depth_cm": 12.0,
                        "corner_radii_cm": (1.2, 0.8, 1.0, 0.9, 0.7, 1.1, 0.8, 1.0),
                    },
                    _purpose("module_catalog", "module_piece_source"),
                ),
                "points": _construction_module_points(),
            },
            purpose=_purpose("module_catalog", "copy_module_catalog"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="construction_kit.snap_grid",
            parameters={
                "radius_cm": 0.38,
                "path": ((-_CONSTRUCTION_KIT_WIDTH_CM * 0.5, 2.0, -32.0), (-32.0, 2.0, -32.0), (0.0, 2.0, -32.0), (32.0, 2.0, -32.0), (_CONSTRUCTION_KIT_WIDTH_CM * 0.5, 2.0, -32.0)),
            },
            purpose=_purpose("snap_grid_or_axes", "swept_snap_grid_axis"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="construction_kit.connector_sockets",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "construction_connector_socket",
                    {"major_radius_cm": 2.8, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("connector_socket_rules", "connector_socket_source"),
                ),
                "points": _construction_socket_points(),
            },
            purpose=_purpose("connector_socket_rules", "copy_connector_socket_rules"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="construction_kit.adjacency_matrix",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "construction_adjacency_rule_panel",
                    {"profile_points": _rect_profile(58.0, 8.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("allowed_adjacency_rules", "adjacency_rule_panel_source"),
                ),
                "distance_cm": 1.6,
                "axis": "z",
            },
            purpose=_purpose("allowed_adjacency_rules", "raised_allowed_adjacency_rules"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="construction_kit.assembly_rules",
            parameters={
                "radius_cm": 0.52,
                "path": ((-54.0, 18.0, 2.0), (-30.0, 32.0, 10.0), (0.0, 24.0, 18.0), (30.0, 38.0, 10.0), (54.0, 22.0, 2.0)),
            },
            purpose=_purpose("repeat_split_assembly_rules", "swept_repeat_split_assembly_rules"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="construction_kit.variant_slots",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "construction_variant_slot",
                    {"profile_points": _rect_profile(10.0, 5.0), "height_cm": 0.28, "axis": "y"},
                    _purpose("kitbash_variant_slots", "variant_slot_source"),
                ),
                "points": ((-44.0, 40.0, 30.0), (-22.0, 44.0, 34.0), (0.0, 46.0, 36.0), (22.0, 44.0, 34.0), (44.0, 40.0, 30.0)),
            },
            purpose=_purpose("kitbash_variant_slots", "copy_kitbash_variant_slots"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="construction_kit.structural_guards",
            parameters={
                "radius_cm": 0.62,
                "path": ((-_CONSTRUCTION_KIT_WIDTH_CM * 0.5, 4.0, -_CONSTRUCTION_KIT_DEPTH_CM * 0.5), (_CONSTRUCTION_KIT_WIDTH_CM * 0.5, 4.0, -_CONSTRUCTION_KIT_DEPTH_CM * 0.5), (_CONSTRUCTION_KIT_WIDTH_CM * 0.5, 52.0, -_CONSTRUCTION_KIT_DEPTH_CM * 0.5), (-_CONSTRUCTION_KIT_WIDTH_CM * 0.5, 52.0, -_CONSTRUCTION_KIT_DEPTH_CM * 0.5), (-_CONSTRUCTION_KIT_WIDTH_CM * 0.5, 4.0, -_CONSTRUCTION_KIT_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("structural_validation_guards", "swept_structural_validation_guard_frame"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="construction_kit.output_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "construction_output_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("buildable_output_ports", "buildable_output_port_source"),
                ),
                "points": ((-48.0, 8.0, -36.0), (-16.0, 8.0, -40.0), (16.0, 8.0, -40.0), (48.0, 8.0, -36.0)),
            },
            purpose=_purpose("buildable_output_ports", "copy_buildable_output_ports"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="construction_kit.scale_metrics",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "construction_scale_tick",
                    {"profile_points": _rect_profile(3.0, 8.0), "height_cm": 0.2, "axis": "y"},
                    _purpose("scale_metric_markers", "scale_tick_source"),
                ),
                "points": tuple((-54.0 + index * 12.0, 12.0, 36.0) for index in range(10)),
            },
            purpose=_purpose("scale_metric_markers", "copy_scale_metric_markers"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="construction_kit.iteration_wear",
            parameters={"amount": 0.07, "grammar_kit_review_bias": 0.84},
            purpose=_purpose("grammar_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.construction_module_catalog", "primary_volume"),
        _node("recipe.construction_snap_grid", "rail"),
        _node("recipe.construction_connector_sockets", "socket"),
        _node("recipe.construction_adjacency_rules", "panel"),
        _node("recipe.construction_assembly_rules", "rail"),
        _node("recipe.construction_variant_slots", "material_zone"),
        _node("recipe.construction_structural_guards", "guard"),
        _node("recipe.construction_output_ports", "socket"),
        _node("recipe.construction_scale_metrics", "decal_zone"),
        _node("recipe.construction_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="construction_grammar_kit_system",
        family="construction_grammar_kit_system",
        ops=ops,
    )
    return RecipeResult(
        family="construction_grammar_kit_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _creature_appendage_program_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="creature_appendage.socket_map",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "appendage_socket_ring",
                    {"major_radius_cm": 3.2, "minor_radius_cm": 0.28, "axis": "y"},
                    _purpose("appendage_socket_map", "socket_ring_source"),
                ),
                "points": _appendage_socket_points(),
            },
            purpose=_purpose("appendage_socket_map", "copy_appendage_socket_map"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="creature_appendage.joint_chains",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "appendage_joint_chain",
                    {
                        "radius_cm": 1.2,
                        "path": ((0.0, 0.0, 0.0), (8.0, -10.0, 4.0), (18.0, -18.0, 2.0), (30.0, -24.0, 8.0)),
                    },
                    _purpose("joint_chain_or_segments", "joint_chain_source"),
                ),
                "points": ((-42.0, 32.0, 8.0), (-14.0, 36.0, 14.0), (14.0, 36.0, 14.0), (42.0, 32.0, 8.0)),
            },
            purpose=_purpose("joint_chain_or_segments", "copy_joint_chain_segments"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="creature_appendage.segment_profiles",
            parameters={
                "radius_cm": 2.8,
                "path": ((-_CREATURE_APPENDAGE_WIDTH_CM * 0.42, 20.0, -12.0), (-24.0, 38.0, 0.0), (0.0, 44.0, 12.0), (24.0, 38.0, 0.0), (_CREATURE_APPENDAGE_WIDTH_CM * 0.42, 20.0, -12.0)),
            },
            purpose=_purpose("segment_profile_controls", "swept_segment_profile_controls"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="creature_appendage.variant_slots",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "appendage_variant_blade",
                    {"profile_points": _leaf_profile(), "height_cm": 0.32, "axis": "y"},
                    _purpose("wing_tail_tentacle_variants", "appendage_variant_source"),
                ),
                "points": _appendage_variant_points(),
            },
            purpose=_purpose("wing_tail_tentacle_variants", "copy_appendage_variant_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="creature_appendage.surface_features",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "appendage_surface_feature",
                    {"profile_points": _rect_profile(5.0, 2.4), "height_cm": 0.22, "axis": "y"},
                    _purpose("surface_feature_maps", "surface_feature_source"),
                ),
                "points": tuple((-44.0 + index * 11.0, 50.0, 28.0 + (index % 2) * 4.0) for index in range(9)),
            },
            purpose=_purpose("surface_feature_maps", "copy_surface_feature_maps"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="creature_appendage.symmetry_rules",
            parameters={
                "radius_cm": 0.46,
                "path": ((-48.0, 14.0, -28.0), (-24.0, 24.0, -34.0), (0.0, 18.0, -38.0), (24.0, 24.0, -34.0), (48.0, 14.0, -28.0)),
            },
            purpose=_purpose("symmetry_mirror_rules", "swept_symmetry_mirror_rules"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="creature_appendage.articulation_ranges",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "appendage_articulation_limit",
                    {"major_radius_cm": 2.4, "minor_radius_cm": 0.18, "axis": "x"},
                    _purpose("articulation_range_controls", "articulation_limit_source"),
                ),
                "points": ((-36.0, 8.0, 30.0), (-12.0, 10.0, 36.0), (12.0, 10.0, 36.0), (36.0, 8.0, 30.0)),
            },
            purpose=_purpose("articulation_range_controls", "copy_articulation_range_controls"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="creature_appendage.muscle_bands",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "appendage_muscle_volume",
                    {"radius_cm": 3.2},
                    _purpose("muscle_or_volume_bands", "muscle_volume_source"),
                ),
                "points": ((-42.0, 28.0, -2.0), (-21.0, 34.0, 6.0), (0.0, 38.0, 10.0), (21.0, 34.0, 6.0), (42.0, 28.0, -2.0)),
            },
            purpose=_purpose("muscle_or_volume_bands", "copy_muscle_volume_bands"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="creature_appendage.attachment_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_CREATURE_APPENDAGE_WIDTH_CM * 0.5, 4.0, -_CREATURE_APPENDAGE_DEPTH_CM * 0.5), (_CREATURE_APPENDAGE_WIDTH_CM * 0.5, 4.0, -_CREATURE_APPENDAGE_DEPTH_CM * 0.5), (_CREATURE_APPENDAGE_WIDTH_CM * 0.5, 60.0, -_CREATURE_APPENDAGE_DEPTH_CM * 0.5), (-_CREATURE_APPENDAGE_WIDTH_CM * 0.5, 60.0, -_CREATURE_APPENDAGE_DEPTH_CM * 0.5), (-_CREATURE_APPENDAGE_WIDTH_CM * 0.5, 4.0, -_CREATURE_APPENDAGE_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("attachment_clearance_guards", "swept_attachment_clearance_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="creature_appendage.iteration_wear",
            parameters={"amount": 0.08, "appendage_review_bias": 0.86},
            purpose=_purpose("appendage_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.appendage_socket_map", "socket"),
        _node("recipe.appendage_joint_chains", "rail"),
        _node("recipe.appendage_segment_profiles", "primary_volume"),
        _node("recipe.appendage_variant_slots", "panel"),
        _node("recipe.appendage_surface_features", "material_zone"),
        _node("recipe.appendage_symmetry_rules", "rail"),
        _node("recipe.appendage_articulation_ranges", "guard"),
        _node("recipe.appendage_muscle_bands", "primary_volume"),
        _node("recipe.appendage_attachment_guards", "guard"),
        _node("recipe.appendage_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="creature_appendage_program_system",
        family="creature_appendage_program_system",
        ops=ops,
    )
    return RecipeResult(
        family="creature_appendage_program_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _body_part_procedural_library_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="body_part_library.catalog",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "body_part_catalog_card",
                    {
                        "width_cm": 14.0,
                        "height_cm": 10.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (1.4, 1.0, 1.2, 0.9, 0.8, 1.3, 1.0, 1.1),
                    },
                    _purpose("body_part_catalog", "body_part_catalog_card_source"),
                ),
                "points": _body_part_catalog_points(),
            },
            purpose=_purpose("body_part_catalog", "copy_body_part_catalog"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="body_part_library.anatomy_regions",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "body_part_anatomy_region",
                    {"profile_points": _rect_profile(13.0, 5.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("anatomy_region_map", "anatomy_region_source"),
                ),
                "points": ((-42.0, 54.0, -28.0), (-14.0, 58.0, -32.0), (14.0, 58.0, -32.0), (42.0, 54.0, -28.0)),
            },
            purpose=_purpose("anatomy_region_map", "copy_anatomy_region_map"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="body_part_library.organ_sockets",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "body_part_organ_socket",
                    {"major_radius_cm": 2.6, "minor_radius_cm": 0.22, "axis": "y"},
                    _purpose("organ_or_socket_map", "organ_socket_source"),
                ),
                "points": _body_part_socket_points(),
            },
            purpose=_purpose("organ_or_socket_map", "copy_organ_socket_map"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="body_part_library.muscle_bands",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "body_part_muscle_volume",
                    {"radius_cm": 3.4},
                    _purpose("muscle_group_or_volume_bands", "muscle_volume_source"),
                ),
                "points": ((-40.0, 36.0, 4.0), (-20.0, 42.0, 10.0), (0.0, 46.0, 14.0), (20.0, 42.0, 10.0), (40.0, 36.0, 4.0)),
            },
            purpose=_purpose("muscle_group_or_volume_bands", "copy_muscle_group_volume_bands"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="body_part_library.landmark_loops",
            parameters={
                "radius_cm": 0.42,
                "path": ((-42.0, 22.0, -10.0), (-20.0, 34.0, 2.0), (0.0, 28.0, 12.0), (20.0, 34.0, 2.0), (42.0, 22.0, -10.0)),
            },
            purpose=_purpose("landmark_loop_markers", "swept_landmark_loop_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="body_part_library.proportion_ranges",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "body_part_proportion_tick",
                    {"profile_points": _rect_profile(3.0, 8.0), "height_cm": 0.2, "axis": "y"},
                    _purpose("proportion_range_controls", "proportion_tick_source"),
                ),
                "points": tuple((-42.0 + index * 12.0, 8.0, 32.0) for index in range(8)),
            },
            purpose=_purpose("proportion_range_controls", "copy_proportion_range_controls"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="body_part_library.symmetry_rules",
            parameters={
                "radius_cm": 0.46,
                "path": ((-48.0, 14.0, -32.0), (-24.0, 22.0, -38.0), (0.0, 18.0, -42.0), (24.0, 22.0, -38.0), (48.0, 14.0, -32.0)),
            },
            purpose=_purpose("symmetry_and_pair_rules", "swept_symmetry_pair_rules"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="body_part_library.surface_zones",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "body_part_surface_zone",
                    {"profile_points": _leaf_profile(), "height_cm": 0.22, "axis": "y"},
                    _purpose("surface_zone_bindings", "surface_zone_source"),
                ),
                "points": ((-36.0, 62.0, 26.0), (-12.0, 66.0, 32.0), (12.0, 66.0, 32.0), (36.0, 62.0, 26.0)),
            },
            purpose=_purpose("surface_zone_bindings", "copy_surface_zone_bindings"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="body_part_library.compatibility_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_BODY_PART_LIBRARY_WIDTH_CM * 0.5, 4.0, -_BODY_PART_LIBRARY_DEPTH_CM * 0.5), (_BODY_PART_LIBRARY_WIDTH_CM * 0.5, 4.0, -_BODY_PART_LIBRARY_DEPTH_CM * 0.5), (_BODY_PART_LIBRARY_WIDTH_CM * 0.5, 68.0, -_BODY_PART_LIBRARY_DEPTH_CM * 0.5), (-_BODY_PART_LIBRARY_WIDTH_CM * 0.5, 68.0, -_BODY_PART_LIBRARY_DEPTH_CM * 0.5), (-_BODY_PART_LIBRARY_WIDTH_CM * 0.5, 4.0, -_BODY_PART_LIBRARY_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("compatibility_validation_guards", "swept_body_part_compatibility_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="body_part_library.iteration_wear",
            parameters={"amount": 0.08, "body_part_review_bias": 0.85},
            purpose=_purpose("body_part_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.body_part_catalog", "primary_volume"),
        _node("recipe.body_part_anatomy_regions", "material_zone"),
        _node("recipe.body_part_organ_sockets", "socket"),
        _node("recipe.body_part_muscle_bands", "primary_volume"),
        _node("recipe.body_part_landmark_loops", "rail"),
        _node("recipe.body_part_proportion_ranges", "panel"),
        _node("recipe.body_part_symmetry_rules", "rail"),
        _node("recipe.body_part_surface_zones", "material_zone"),
        _node("recipe.body_part_compatibility_guards", "guard"),
        _node("recipe.body_part_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="body_part_procedural_library_system",
        family="body_part_procedural_library_system",
        ops=ops,
    )
    return RecipeResult(
        family="body_part_procedural_library_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _material_primitive_library_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="material_primitive.catalog",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "material_primitive_swatch",
                    {"profile_points": _rect_profile(14.0, 8.0), "height_cm": 0.34, "axis": "y"},
                    _purpose("material_primitive_catalog", "material_primitive_swatch_source"),
                ),
                "points": _material_primitive_points(),
            },
            purpose=_purpose("material_primitive_catalog", "copy_material_primitive_catalog"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="material_primitive.substance_taxonomy",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "physical_substance_badge",
                    {"radius_cm": 2.4},
                    _purpose("physical_substance_taxonomy", "substance_badge_source"),
                ),
                "points": ((-42.0, 28.0, -30.0), (-21.0, 32.0, -34.0), (0.0, 34.0, -36.0), (21.0, 32.0, -34.0), (42.0, 28.0, -30.0)),
            },
            purpose=_purpose("physical_substance_taxonomy", "copy_physical_substance_taxonomy"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="material_primitive.pbr_channels",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "pbr_channel_range",
                    {"profile_points": _rect_profile(10.0, 4.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("pbr_channel_ranges", "pbr_channel_range_source"),
                ),
                "points": _material_channel_points(),
            },
            purpose=_purpose("pbr_channel_ranges", "copy_pbr_channel_ranges"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="material_primitive.material_classes",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "material_class_socket",
                    {"major_radius_cm": 2.6, "minor_radius_cm": 0.2, "axis": "y"},
                    _purpose("metal_dielectric_emissive_classes", "material_class_socket_source"),
                ),
                "points": ((-40.0, 14.0, 28.0), (-13.0, 18.0, 34.0), (13.0, 18.0, 34.0), (40.0, 14.0, 28.0)),
            },
            purpose=_purpose("metal_dielectric_emissive_classes", "copy_material_class_sockets"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="material_primitive.parameter_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "material_parameter_knob",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("procedural_parameter_ports", "parameter_knob_source"),
                ),
                "points": tuple((-48.0 + index * 16.0, 6.0, -36.0) for index in range(7)),
            },
            purpose=_purpose("procedural_parameter_ports", "copy_procedural_parameter_ports"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="material_primitive.smart_masks",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "smart_mask_chip",
                    {"profile_points": _rect_profile(8.0, 3.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("smart_mask_bindings", "smart_mask_chip_source"),
                ),
                "points": ((-42.0, 30.0, 36.0), (-21.0, 34.0, 40.0), (0.0, 36.0, 42.0), (21.0, 34.0, 40.0), (42.0, 30.0, 36.0)),
            },
            purpose=_purpose("smart_mask_bindings", "copy_smart_mask_bindings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="material_primitive.materialx_outputs",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "materialx_output_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("materialx_output_ports", "materialx_output_port_source"),
                ),
                "points": ((-48.0, 4.0, 34.0), (-16.0, 4.0, 38.0), (16.0, 4.0, 38.0), (48.0, 4.0, 34.0)),
            },
            purpose=_purpose("materialx_output_ports", "copy_materialx_output_ports"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="material_primitive.validation_guards",
            parameters={
                "radius_cm": 0.56,
                "path": ((-_MATERIAL_PRIMITIVE_WIDTH_CM * 0.5, 4.0, -_MATERIAL_PRIMITIVE_DEPTH_CM * 0.5), (_MATERIAL_PRIMITIVE_WIDTH_CM * 0.5, 4.0, -_MATERIAL_PRIMITIVE_DEPTH_CM * 0.5), (_MATERIAL_PRIMITIVE_WIDTH_CM * 0.5, 38.0, -_MATERIAL_PRIMITIVE_DEPTH_CM * 0.5), (-_MATERIAL_PRIMITIVE_WIDTH_CM * 0.5, 38.0, -_MATERIAL_PRIMITIVE_DEPTH_CM * 0.5), (-_MATERIAL_PRIMITIVE_WIDTH_CM * 0.5, 4.0, -_MATERIAL_PRIMITIVE_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("pbr_validation_guards", "swept_pbr_validation_guard_frame"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="material_primitive.variant_slots",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "substance_variant_slot",
                    {"profile_points": _rect_profile(12.0, 5.0), "height_cm": 0.26, "axis": "y"},
                    _purpose("substance_variant_slots", "substance_variant_slot_source"),
                ),
                "points": ((-36.0, 38.0, -34.0), (-12.0, 40.0, -38.0), (12.0, 40.0, -38.0), (36.0, 38.0, -34.0)),
            },
            purpose=_purpose("substance_variant_slots", "copy_substance_variant_slots"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="material_primitive.iteration_wear",
            parameters={"amount": 0.07, "material_primitive_review_bias": 0.84},
            purpose=_purpose("material_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.material_primitive_catalog", "primary_volume"),
        _node("recipe.material_substance_taxonomy", "material_zone"),
        _node("recipe.material_pbr_channels", "panel"),
        _node("recipe.material_class_sockets", "socket"),
        _node("recipe.material_parameter_ports", "fastener"),
        _node("recipe.material_smart_masks", "decal_zone"),
        _node("recipe.materialx_output_ports", "socket"),
        _node("recipe.material_pbr_validation_guards", "guard"),
        _node("recipe.material_substance_variants", "material_zone"),
        _node("recipe.material_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="material_primitive_library_system",
        family="material_primitive_library_system",
        ops=ops,
    )
    return RecipeResult(
        family="material_primitive_library_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _stateful_destructible_prop_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="stateful_prop.intact_shell",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "stateful_intact_shell",
                    {
                        "width_cm": _STATEFUL_WIDTH_CM,
                        "height_cm": _STATEFUL_HEIGHT_CM,
                        "depth_cm": _STATEFUL_DEPTH_CM,
                        "corner_radii_cm": (2.4, 1.5, 2.1, 1.8, 1.2, 2.5, 1.7, 2.0),
                    },
                    _purpose("intact_primary_shell", "shell_source"),
                ),
                "width_cm": 1.4,
                "segments": 4,
            },
            purpose=_purpose("intact_primary_shell", "polybeveled_intact_shell"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="stateful_prop.damage_state_markers",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "stateful_health_pip",
                    {"radius_cm": 1.5},
                    _purpose("damage_state_markers", "health_pip_source"),
                ),
                "points": ((-12.0, 32.0, -19.0), (-6.0, 32.0, -19.0), (0.0, 32.0, -19.0), (6.0, 32.0, -19.0), (12.0, 32.0, -19.0)),
            },
            purpose=_purpose("damage_state_markers", "copy_health_pips"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="stateful_prop.fracture_lines",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "stateful_fracture_line",
                    {"radius_cm": 0.35, "path": ((-10.0, 0.0, 0.0), (-2.0, 5.0, 0.0), (8.0, 2.0, 0.0))},
                    _purpose("fracture_or_break_lines", "fracture_source"),
                ),
                "points": ((-12.0, 18.0, -19.5), (8.0, 25.0, -19.5), (18.0, 10.0, -19.5)),
            },
            purpose=_purpose("fracture_or_break_lines", "copy_fracture_lines"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="stateful_prop.fragment_zones",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "stateful_fragment_plate",
                    {"profile_points": _leaf_profile(), "height_cm": 0.55, "axis": "z"},
                    _purpose("detachable_or_fragment_zones", "fragment_source"),
                ),
                "points": _stateful_fragment_points(),
            },
            purpose=_purpose("detachable_or_fragment_zones", "copy_fragment_zones"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="stateful_prop.weak_points",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "stateful_weak_point",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("impact_or_weak_points", "weak_point_source"),
                ),
                "points": ((-18.0, 26.0, -20.0), (0.0, 20.0, -20.0), (18.0, 14.0, -20.0)),
            },
            purpose=_purpose("impact_or_weak_points", "copy_weak_points"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="stateful_prop.repair_handle",
            parameters={
                "radius_cm": 0.8,
                "path": ((-11.0, 8.0, -20.0), (-11.0, 14.0, -22.0), (11.0, 14.0, -22.0), (11.0, 8.0, -20.0)),
            },
            purpose=_purpose("repair_or_rebuild_affordance", "swept_repair_handle"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="stateful_prop.transition_cue",
            parameters={
                "profile_polygon": _rect_profile(30.0, 3.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, 4.0, -_STATEFUL_DEPTH_CM * 0.5 - 0.5),
            },
            purpose=_purpose("state_transition_cues", "raised_transition_band"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="stateful_prop.hazard_boundary",
            parameters={
                "radius_cm": 0.85,
                "path": (
                    (-_STATEFUL_WIDTH_CM * 0.5 - 5.0, 0.0, -_STATEFUL_DEPTH_CM * 0.5 - 5.0),
                    (_STATEFUL_WIDTH_CM * 0.5 + 5.0, 0.0, -_STATEFUL_DEPTH_CM * 0.5 - 5.0),
                    (_STATEFUL_WIDTH_CM * 0.5 + 5.0, 0.0, _STATEFUL_DEPTH_CM * 0.5 + 5.0),
                    (-_STATEFUL_WIDTH_CM * 0.5 - 5.0, 0.0, _STATEFUL_DEPTH_CM * 0.5 + 5.0),
                    (-_STATEFUL_WIDTH_CM * 0.5 - 5.0, 0.0, -_STATEFUL_DEPTH_CM * 0.5 - 5.0),
                ),
            },
            purpose=_purpose("hazard_or_failure_boundary", "swept_failure_boundary"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="stateful_prop.debris_scatter",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "stateful_debris_chip",
                    {
                        "width_cm": 4.0,
                        "height_cm": 1.4,
                        "depth_cm": 3.0,
                        "corner_radii_cm": (0.6, 0.4, 0.7, 0.5, 0.4, 0.8, 0.5, 0.6),
                    },
                    _purpose("debris_or_secondary_scatter", "debris_source"),
                ),
                "points": ((-26.0, -2.0, -16.0), (-12.0, -2.0, 20.0), (10.0, -2.0, -22.0), (28.0, -2.0, 14.0)),
            },
            purpose=_purpose("debris_or_secondary_scatter", "copy_debris_scatter"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="stateful_prop.damage_wear",
            parameters={"amount": 0.32, "damage_bias": 0.75},
            purpose=_purpose("damage_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.stateful_intact_shell", "primary_volume"),
        _node("recipe.stateful_damage_markers", "decal_zone"),
        _node("recipe.stateful_fracture_lines", "trim"),
        _node("recipe.stateful_fragment_zones", "panel"),
        _node("recipe.stateful_weak_points", "mount"),
        _node("recipe.stateful_repair_handle", "handle"),
        _node("recipe.stateful_transition_cue", "decal_zone"),
        _node("recipe.stateful_hazard_boundary", "guard"),
        _node("recipe.stateful_debris", "fastener"),
        _node("recipe.stateful_damage_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="stateful_destructible_prop",
        family="stateful_destructible_prop",
        ops=ops,
    )
    return RecipeResult(
        family="stateful_destructible_prop",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _cloth_attachment_form_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_attachment.anchors",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "cloth_anchor_ring",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("anchor_or_mount_points", "anchor_source"),
                ),
                "points": _cloth_anchor_points(),
            },
            purpose=_purpose("anchor_or_mount_points", "copy_anchor_points"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="cloth_attachment.fabric_panel",
            parameters={
                "source": _panel_source(
                    target="cloth_drape_panel",
                    width_cm=_CLOTH_WIDTH_CM,
                    height_cm=_CLOTH_HEIGHT_CM,
                    thickness_cm=0.7,
                    center=(0.0, 0.0, 0.0),
                    purpose=_purpose("fabric_panel_or_drape", "panel_source"),
                ),
                "width_cm": 0.35,
                "segments": 3,
            },
            purpose=_purpose("fabric_panel_or_drape", "softened_fabric_panel"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_attachment.seams",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cloth_seam_line",
                    {"profile_points": _rect_profile(2.0, _CLOTH_HEIGHT_CM * 0.82), "height_cm": 0.2, "axis": "z"},
                    _purpose("seam_or_hem_lines", "seam_source"),
                ),
                "points": ((-_CLOTH_WIDTH_CM * 0.5 + 4.0, 0.0, -4.5), (_CLOTH_WIDTH_CM * 0.5 - 4.0, 0.0, -4.5)),
            },
            purpose=_purpose("seam_or_hem_lines", "copy_vertical_seams"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_attachment.fold_lines",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "cloth_fold_curve",
                    {"radius_cm": 0.28, "path": ((-20.0, 18.0, -4.8), (-6.0, 4.0, -5.2), (8.0, -8.0, -4.9), (20.0, -20.0, -5.3))},
                    _purpose("fold_or_tension_lines", "fold_source"),
                ),
                "points": ((0.0, 0.0, 0.0), (8.0, -2.0, 0.0), (-8.0, 2.0, 0.0)),
            },
            purpose=_purpose("fold_or_tension_lines", "copy_fold_curves"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cloth_attachment.hardware",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "cloth_buckle_loop",
                    {"major_radius_cm": 3.2, "minor_radius_cm": 0.35, "axis": "z"},
                    _purpose("attachment_hardware", "buckle_source"),
                ),
                "points": ((-_CLOTH_WIDTH_CM * 0.22, _CLOTH_HEIGHT_CM * 0.5 + 2.0, -4.8), (_CLOTH_WIDTH_CM * 0.22, _CLOTH_HEIGHT_CM * 0.5 + 2.0, -4.8)),
            },
            purpose=_purpose("attachment_hardware", "copy_buckles"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="cloth_attachment.border_trim",
            parameters={
                "profile_polygon": _rect_profile(_CLOTH_WIDTH_CM + 4.0, 4.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, -_CLOTH_HEIGHT_CM * 0.5 - 1.5, -_CLOTH_DEPTH_CM * 0.5 - 0.4),
            },
            purpose=_purpose("trim_or_border_detail", "raised_lower_border"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cloth_attachment.motion_cue",
            parameters={
                "radius_cm": 0.35,
                "path": ((-_CLOTH_WIDTH_CM * 0.55, 20.0, 4.0), (-10.0, 28.0, 8.0), (_CLOTH_WIDTH_CM * 0.48, 12.0, 5.0)),
            },
            purpose=_purpose("motion_or_wind_cues", "swept_wind_arc"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="cloth_attachment.material_zone",
            parameters={
                "profile_polygon": _rect_profile(_CLOTH_WIDTH_CM * 0.46, _CLOTH_HEIGHT_CM * 0.26),
                "extrude_height_cm": 0.18,
                "axis": "z",
                "center": (0.0, 6.0, -_CLOTH_DEPTH_CM * 0.5 - 0.5),
            },
            purpose=_purpose("material_or_pattern_zone", "raised_pattern_field"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cloth_attachment.clearance_cue",
            parameters={
                "radius_cm": 0.45,
                "path": ((-_CLOTH_WIDTH_CM * 0.5 - 4.0, -_CLOTH_HEIGHT_CM * 0.5, 0.0), (0.0, -_CLOTH_HEIGHT_CM * 0.5 - 6.0, 0.0), (_CLOTH_WIDTH_CM * 0.5 + 4.0, -_CLOTH_HEIGHT_CM * 0.5, 0.0)),
            },
            purpose=_purpose("collision_or_clearance_cues", "swept_clearance_arc"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="cloth_attachment.wear_masks",
            parameters={"amount": 0.18, "fray_bias": 0.72},
            purpose=_purpose("cloth_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.cloth_anchors", "mount"),
        _node("recipe.cloth_panel", "panel"),
        _node("recipe.cloth_seams", "trim"),
        _node("recipe.cloth_folds", "rail"),
        _node("recipe.cloth_hardware", "handle"),
        _node("recipe.cloth_border", "trim"),
        _node("recipe.cloth_motion", "rail"),
        _node("recipe.cloth_material_zone", "material_zone"),
        _node("recipe.cloth_clearance", "guard"),
        _node("recipe.cloth_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="cloth_attachment_form",
        family="cloth_attachment_form",
        ops=ops,
    )
    return RecipeResult(
        family="cloth_attachment_form",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _domain_kit_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="domain_kit.root_identity",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "domain_kit_root_plate",
                    {
                        "width_cm": _DOMAIN_KIT_WIDTH_CM,
                        "height_cm": _DOMAIN_KIT_HEIGHT_CM,
                        "depth_cm": _DOMAIN_KIT_DEPTH_CM,
                    },
                    _purpose("kit_root_identity", "root_source"),
                ),
                "width_cm": 2.2,
                "segments": 4,
            },
            purpose=_purpose("kit_root_identity", "polybeveled_root_plate"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="domain_kit.canonical_parts",
            parameters={
                "source": _source_op(
                    "sop.polybevel",
                    "domain_kit_part_tile",
                    {
                        "source": _source_op(
                            "solid.subdivision_box",
                            "domain_kit_part_volume",
                            {
                                "width_cm": 16.0,
                                "height_cm": 8.0,
                                "depth_cm": 12.0,
                                "corner_radii_cm": (1.2, 0.8, 1.1, 0.9, 0.7, 1.3, 0.8, 1.0),
                            },
                            _purpose("canonical_part_set", "part_source"),
                        ),
                        "width_cm": 0.5,
                        "segments": 2,
                    },
                    _purpose("canonical_part_set", "polybeveled_part_source"),
                ),
                "points": _domain_kit_part_points(),
            },
            purpose=_purpose("canonical_part_set", "copy_canonical_parts"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="domain_kit.snap_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "domain_kit_snap_port",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("snap_ports_or_connectors", "snap_port_source"),
                ),
                "points": ((-54.0, 23.0, -34.0), (54.0, 23.0, -34.0), (-54.0, 23.0, 34.0), (54.0, 23.0, 34.0)),
            },
            purpose=_purpose("snap_ports_or_connectors", "copy_snap_ports"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="domain_kit.variant_slots",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "domain_kit_variant_slot",
                    {"profile_points": _rect_profile(14.0, 8.0), "height_cm": 0.4, "axis": "y"},
                    _purpose("variant_slots", "slot_source"),
                ),
                "points": ((-36.0, 24.0, 34.0), (-12.0, 24.0, 34.0), (12.0, 24.0, 34.0), (36.0, 24.0, 34.0)),
            },
            purpose=_purpose("variant_slots", "copy_variant_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="domain_kit.scale_reference",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "domain_kit_scale_tick",
                    {"profile_points": _rect_profile(2.0, 6.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("scale_or_grid_reference", "scale_tick_source"),
                ),
                "points": tuple((-48.0 + index * 12.0, 24.0, -40.0) for index in range(9)),
            },
            purpose=_purpose("scale_or_grid_reference", "copy_scale_ticks"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="domain_kit.style_rules",
            parameters={
                "profile_polygon": _rect_profile(44.0, 9.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 24.0, -2.0),
            },
            purpose=_purpose("style_or_material_rules", "raised_style_rule_band"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="domain_kit.assembly_guides",
            parameters={
                "radius_cm": 0.65,
                "path": ((-46.0, 24.5, 0.0), (-18.0, 25.0, 12.0), (18.0, 25.0, 12.0), (46.0, 24.5, 0.0)),
            },
            purpose=_purpose("assembly_guides", "swept_assembly_path"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="domain_kit.compatibility_markers",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "domain_kit_compatibility_ring",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.28, "axis": "y"},
                    _purpose("compatibility_or_dependency_markers", "compatibility_source"),
                ),
                "points": ((-50.0, 25.0, 10.0), (-25.0, 25.0, 18.0), (25.0, 25.0, 18.0), (50.0, 25.0, 10.0)),
            },
            purpose=_purpose("compatibility_or_dependency_markers", "copy_compatibility_rings"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="domain_kit.library_label",
            parameters={
                "profile_polygon": _rect_profile(26.0, 7.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-_DOMAIN_KIT_WIDTH_CM * 0.34, 24.5, -_DOMAIN_KIT_DEPTH_CM * 0.28),
            },
            purpose=_purpose("library_labels", "raised_library_label"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="domain_kit.usage_wear",
            parameters={"amount": 0.16, "socket_bias": 0.55},
            purpose=_purpose("kit_usage_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.domain_kit_root", "primary_volume"),
        _node("recipe.domain_kit_parts", "panel"),
        _node("recipe.domain_kit_snap_ports", "socket"),
        _node("recipe.domain_kit_variant_slots", "inset"),
        _node("recipe.domain_kit_scale_reference", "fastener"),
        _node("recipe.domain_kit_style_rules", "material_zone"),
        _node("recipe.domain_kit_assembly_guides", "rail"),
        _node("recipe.domain_kit_compatibility", "decal_zone"),
        _node("recipe.domain_kit_label", "decal_zone"),
        _node("recipe.domain_kit_usage_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="domain_kit_bundle",
        family="domain_kit_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="domain_kit_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _world_system_assembly_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="world_system.footprint",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "world_system_root_footprint",
                    {
                        "width_cm": _WORLD_SYSTEM_WIDTH_CM,
                        "height_cm": _WORLD_SYSTEM_HEIGHT_CM,
                        "depth_cm": _WORLD_SYSTEM_DEPTH_CM,
                    },
                    _purpose("root_world_footprint", "root_source"),
                ),
                "width_cm": 3.0,
                "segments": 5,
            },
            purpose=_purpose("root_world_footprint", "polybeveled_world_plate"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_system.region_layers",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "world_region_layer",
                    {"profile_points": _rect_profile(24.0, 16.0), "height_cm": 0.35, "axis": "y"},
                    _purpose("layer_or_region_stack", "region_source"),
                ),
                "points": _world_system_node_points(),
            },
            purpose=_purpose("layer_or_region_stack", "copy_region_layers"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="world_system.route_graph",
            parameters={
                "radius_cm": 1.0,
                "path": ((-58.0, 19.0, -42.0), (-24.0, 20.0, -18.0), (8.0, 20.0, -4.0), (38.0, 19.0, 18.0), (58.0, 18.0, 38.0)),
            },
            purpose=_purpose("connection_or_route_graph", "swept_route_graph"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="world_system.rule_zone",
            parameters={
                "profile_polygon": _rect_profile(48.0, 26.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-30.0, _WORLD_SYSTEM_HEIGHT_CM + 0.8, 18.0),
            },
            purpose=_purpose("faction_or_rule_zones", "raised_influence_zone"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_system.progression_chain",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "world_progression_node",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("objective_or_progression_chain", "progression_node_source"),
                ),
                "points": ((-44.0, 22.0, -48.0), (-18.0, 22.0, -28.0), (10.0, 22.0, -8.0), (38.0, 22.0, 14.0), (58.0, 22.0, 36.0)),
            },
            purpose=_purpose("objective_or_progression_chain", "copy_progression_nodes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_system.resource_distribution",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "world_resource_point",
                    {"radius_cm": 1.8},
                    _purpose("resource_or_spawn_distribution", "resource_source"),
                ),
                "points": ((-62.0, 20.0, 10.0), (-36.0, 20.0, 44.0), (4.0, 20.0, 48.0), (32.0, 20.0, -46.0), (64.0, 20.0, -18.0)),
            },
            purpose=_purpose("resource_or_spawn_distribution", "copy_resource_points"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_system.landmarks",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "world_landmark_anchor",
                    {
                        "profile_points": ((0.0, 0.0), (5.0, 1.2), (6.0, 14.0), (2.5, 21.0), (0.0, 22.0)),
                        "axis": "y",
                    },
                    _purpose("landmarks_or_anchor_nodes", "landmark_source"),
                ),
                "points": ((0.0, 24.0, 0.0), (-48.0, 24.0, 38.0), (52.0, 24.0, -34.0)),
            },
            purpose=_purpose("landmarks_or_anchor_nodes", "copy_landmarks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_system.transition_gates",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "world_transition_gate",
                    {"radius_cm": 1.0, "path": ((-7.0, 0.0, 0.0), (-3.5, 10.0, 0.0), (0.0, 12.5, 0.0), (3.5, 10.0, 0.0), (7.0, 0.0, 0.0))},
                    _purpose("boundary_or_transition_gates", "gate_source"),
                ),
                "points": ((-_WORLD_SYSTEM_WIDTH_CM * 0.5, 19.0, 0.0), (_WORLD_SYSTEM_WIDTH_CM * 0.5, 19.0, 0.0), (0.0, 19.0, _WORLD_SYSTEM_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("boundary_or_transition_gates", "copy_transition_gates"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="world_system.labels",
            parameters={
                "profile_polygon": _rect_profile(20.0, 6.0),
                "extrude_height_cm": 0.2,
                "axis": "y",
                "center": (_WORLD_SYSTEM_WIDTH_CM * 0.32, _WORLD_SYSTEM_HEIGHT_CM + 1.0, -_WORLD_SYSTEM_DEPTH_CM * 0.36),
            },
            purpose=_purpose("labels_or_debug_cues", "raised_system_label"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="world_system.usage_masks",
            parameters={"amount": 0.18, "route_bias": 0.62},
            purpose=_purpose("system_wear_or_usage_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.world_system_footprint", "primary_volume"),
        _node("recipe.world_system_regions", "material_zone"),
        _node("recipe.world_system_routes", "rail"),
        _node("recipe.world_system_rules", "material_zone"),
        _node("recipe.world_system_progression", "socket"),
        _node("recipe.world_system_resources", "fastener"),
        _node("recipe.world_system_landmarks", "mount"),
        _node("recipe.world_system_gates", "frame"),
        _node("recipe.world_system_labels", "decal_zone"),
        _node("recipe.world_system_usage", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="world_system_assembly",
        family="world_system_assembly",
        ops=ops,
    )
    return RecipeResult(
        family="world_system_assembly",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _simulation_environment_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="simulation_system.domain_bounds",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "simulation_domain_bounds",
                    {
                        "width_cm": _SIM_SYSTEM_WIDTH_CM,
                        "height_cm": _SIM_SYSTEM_HEIGHT_CM,
                        "depth_cm": _SIM_SYSTEM_DEPTH_CM,
                        "center": (0.0, _SIM_SYSTEM_HEIGHT_CM * 0.5, 0.0),
                    },
                    _purpose("simulation_domain_bounds", "domain_source"),
                ),
                "width_cm": 2.0,
                "segments": 4,
            },
            purpose=_purpose("simulation_domain_bounds", "polybeveled_domain_bounds"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="simulation_system.emitters",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "simulation_force_emitter",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("emitter_or_force_sources", "emitter_source"),
                ),
                "points": ((-_SIM_SYSTEM_WIDTH_CM * 0.42, 12.0, -_SIM_SYSTEM_DEPTH_CM * 0.35), (_SIM_SYSTEM_WIDTH_CM * 0.4, 18.0, -_SIM_SYSTEM_DEPTH_CM * 0.24), (0.0, 22.0, _SIM_SYSTEM_DEPTH_CM * 0.42)),
            },
            purpose=_purpose("emitter_or_force_sources", "copy_force_emitters"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="simulation_system.flow_lines",
            parameters={
                "source": _source_op(
                    "sop.polywire",
                    "simulation_flow_line",
                    {"radius_cm": 0.55, "path": ((-36.0, 10.0, -24.0), (-8.0, 18.0, -4.0), (18.0, 22.0, 8.0), (42.0, 20.0, 28.0))},
                    _purpose("vector_or_flow_lines", "flow_source"),
                ),
                "points": ((0.0, 0.0, 0.0), (0.0, 4.0, -10.0), (0.0, -4.0, 10.0)),
            },
            purpose=_purpose("vector_or_flow_lines", "copy_flow_lines"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="simulation_system.gradient_zone",
            parameters={
                "profile_polygon": _rect_profile(54.0, 24.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (8.0, 25.0, 4.0),
            },
            purpose=_purpose("field_gradient_zones", "raised_gradient_zone"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="simulation_system.constraints",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "simulation_constraint_marker",
                    {"major_radius_cm": 3.8, "minor_radius_cm": 0.3, "axis": "y"},
                    _purpose("solver_constraint_markers", "constraint_source"),
                ),
                "points": ((-38.0, 24.0, 30.0), (0.0, 24.0, -32.0), (38.0, 24.0, 30.0)),
            },
            purpose=_purpose("solver_constraint_markers", "copy_constraint_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="simulation_system.probes",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "simulation_probe",
                    {"radius_cm": 1.4},
                    _purpose("sample_or_probe_points", "probe_source"),
                ),
                "points": _simulation_probe_points(),
            },
            purpose=_purpose("sample_or_probe_points", "copy_probe_points"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="simulation_system.obstacle_boundary",
            parameters={
                "radius_cm": 0.9,
                "path": ((-_SIM_SYSTEM_WIDTH_CM * 0.48, 2.0, -_SIM_SYSTEM_DEPTH_CM * 0.5), (_SIM_SYSTEM_WIDTH_CM * 0.48, 2.0, -_SIM_SYSTEM_DEPTH_CM * 0.5), (_SIM_SYSTEM_WIDTH_CM * 0.48, 2.0, _SIM_SYSTEM_DEPTH_CM * 0.5), (-_SIM_SYSTEM_WIDTH_CM * 0.48, 2.0, _SIM_SYSTEM_DEPTH_CM * 0.5), (-_SIM_SYSTEM_WIDTH_CM * 0.48, 2.0, -_SIM_SYSTEM_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("collision_or_obstacle_boundaries", "swept_obstacle_boundary"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="simulation_system.time_ticks",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "simulation_time_tick",
                    {"profile_points": _rect_profile(2.0, 5.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("temporal_state_markers", "tick_source"),
                ),
                "points": tuple((-24.0 + index * 8.0, 27.0, -_SIM_SYSTEM_DEPTH_CM * 0.48) for index in range(7)),
            },
            purpose=_purpose("temporal_state_markers", "copy_time_ticks"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="simulation_system.response_output",
            parameters={
                "profile_polygon": _rect_profile(44.0, 10.0),
                "extrude_height_cm": 0.2,
                "axis": "y",
                "center": (-12.0, 25.5, _SIM_SYSTEM_DEPTH_CM * 0.36),
            },
            purpose=_purpose("material_response_outputs", "raised_response_output"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="simulation_system.wear_masks",
            parameters={"amount": 0.2, "field_bias": 0.7},
            purpose=_purpose("simulation_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.simulation_domain", "primary_volume"),
        _node("recipe.simulation_emitters", "mount"),
        _node("recipe.simulation_flow_lines", "rail"),
        _node("recipe.simulation_gradient", "material_zone"),
        _node("recipe.simulation_constraints", "guard"),
        _node("recipe.simulation_probes", "fastener"),
        _node("recipe.simulation_obstacles", "guard"),
        _node("recipe.simulation_time_ticks", "decal_zone"),
        _node("recipe.simulation_response", "material_zone"),
        _node("recipe.simulation_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="simulation_environment_system",
        family="simulation_environment_system",
        ops=ops,
    )
    return RecipeResult(
        family="simulation_environment_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _authored_multi_asset_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="multi_asset_bundle.root_manifest",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "multi_asset_bundle_root",
                    {
                        "width_cm": _MULTI_ASSET_WIDTH_CM,
                        "height_cm": _MULTI_ASSET_HEIGHT_CM,
                        "depth_cm": _MULTI_ASSET_DEPTH_CM,
                    },
                    _purpose("bundle_root_manifest", "root_source"),
                ),
                "width_cm": 2.0,
                "segments": 4,
            },
            purpose=_purpose("bundle_root_manifest", "polybeveled_manifest_plate"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="multi_asset_bundle.member_slots",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "multi_asset_member_slot",
                    {
                        "width_cm": 18.0,
                        "height_cm": 6.0,
                        "depth_cm": 14.0,
                        "corner_radii_cm": (1.0, 0.8, 1.2, 0.9, 0.7, 1.1, 0.8, 1.0),
                    },
                    _purpose("member_asset_slots", "member_slot_source"),
                ),
                "points": _multi_asset_member_points(),
            },
            purpose=_purpose("member_asset_slots", "copy_member_slots"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="multi_asset_bundle.dependency_graph",
            parameters={
                "radius_cm": 0.55,
                "path": ((-48.0, 24.0, -26.0), (-16.0, 25.0, -26.0), (16.0, 25.0, -26.0), (48.0, 24.0, -26.0), (32.0, 24.0, 18.0), (0.0, 25.0, 18.0), (-32.0, 24.0, 18.0)),
            },
            purpose=_purpose("dependency_or_link_graph", "swept_dependency_graph"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="multi_asset_bundle.layout_anchors",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "multi_asset_layout_anchor",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("layout_or_scene_anchors", "anchor_source"),
                ),
                "points": ((-54.0, 23.0, 34.0), (54.0, 23.0, 34.0), (-54.0, 23.0, -38.0), (54.0, 23.0, -38.0)),
            },
            purpose=_purpose("layout_or_scene_anchors", "copy_layout_anchors"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="multi_asset_bundle.variant_lod_entries",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "multi_asset_lod_tick",
                    {"radius_cm": 1.5},
                    _purpose("variant_or_lod_entries", "lod_tick_source"),
                ),
                "points": tuple((-24.0 + index * 8.0, 24.0, -_MULTI_ASSET_DEPTH_CM * 0.5 - 1.0) for index in range(7)),
            },
            purpose=_purpose("variant_or_lod_entries", "copy_lod_ticks"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="multi_asset_bundle.shared_material_zone",
            parameters={
                "profile_polygon": _rect_profile(50.0, 10.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 22.0, 0.0),
            },
            purpose=_purpose("shared_material_or_style_zones", "raised_shared_material_band"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="multi_asset_bundle.export_marker",
            parameters={
                "profile_polygon": _rect_profile(22.0, 7.0),
                "extrude_height_cm": 0.2,
                "axis": "y",
                "center": (-_MULTI_ASSET_WIDTH_CM * 0.34, 22.5, -_MULTI_ASSET_DEPTH_CM * 0.34),
            },
            purpose=_purpose("export_or_package_markers", "raised_export_badge"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="multi_asset_bundle.assembly_order",
            parameters={
                "radius_cm": 0.45,
                "path": ((-50.0, 23.0, 28.0), (-24.0, 24.0, 8.0), (0.0, 24.5, 28.0), (26.0, 24.0, 8.0), (50.0, 23.0, 28.0)),
            },
            purpose=_purpose("assembly_or_order_guides", "swept_assembly_order"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="multi_asset_bundle.bounds_reference",
            parameters={
                "radius_cm": 0.8,
                "path": ((-_MULTI_ASSET_WIDTH_CM * 0.5, 20.5, -_MULTI_ASSET_DEPTH_CM * 0.5), (_MULTI_ASSET_WIDTH_CM * 0.5, 20.5, -_MULTI_ASSET_DEPTH_CM * 0.5), (_MULTI_ASSET_WIDTH_CM * 0.5, 20.5, _MULTI_ASSET_DEPTH_CM * 0.5), (-_MULTI_ASSET_WIDTH_CM * 0.5, 20.5, _MULTI_ASSET_DEPTH_CM * 0.5), (-_MULTI_ASSET_WIDTH_CM * 0.5, 20.5, -_MULTI_ASSET_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("bounds_or_footprint_reference", "swept_bundle_bounds"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="multi_asset_bundle.usage_wear",
            parameters={"amount": 0.15, "socket_bias": 0.6},
            purpose=_purpose("bundle_usage_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.multi_asset_root", "primary_volume"),
        _node("recipe.multi_asset_members", "socket"),
        _node("recipe.multi_asset_dependencies", "rail"),
        _node("recipe.multi_asset_layout_anchors", "mount"),
        _node("recipe.multi_asset_lod_entries", "fastener"),
        _node("recipe.multi_asset_shared_materials", "material_zone"),
        _node("recipe.multi_asset_export_marker", "decal_zone"),
        _node("recipe.multi_asset_assembly_order", "rail"),
        _node("recipe.multi_asset_bounds", "guard"),
        _node("recipe.multi_asset_usage_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="authored_multi_asset_bundle",
        family="authored_multi_asset_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="authored_multi_asset_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _live_procedural_runtime_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="runtime_bundle.core",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "runtime_core_body",
                    {
                        "width_cm": _RUNTIME_WIDTH_CM,
                        "height_cm": _RUNTIME_HEIGHT_CM,
                        "depth_cm": _RUNTIME_DEPTH_CM,
                        "corner_radii_cm": (2.4, 1.8, 2.2, 2.0, 1.5, 2.5, 1.7, 2.1),
                    },
                    _purpose("runtime_core_or_hda_body", "core_source"),
                ),
                "width_cm": 1.2,
                "segments": 4,
            },
            purpose=_purpose("runtime_core_or_hda_body", "polybeveled_runtime_core"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="runtime_bundle.input_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "runtime_parameter_port",
                    {"profile_points": _rivet_profile(), "axis": "x"},
                    _purpose("input_parameter_ports", "input_port_source"),
                ),
                "points": _runtime_port_points()[:3],
            },
            purpose=_purpose("input_parameter_ports", "copy_input_ports"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="runtime_bundle.engine_hooks",
            parameters={
                "radius_cm": 0.65,
                "path": ((-_RUNTIME_WIDTH_CM * 0.5 - 10.0, 22.0, 0.0), (-_RUNTIME_WIDTH_CM * 0.25, 30.0, -8.0), (_RUNTIME_WIDTH_CM * 0.25, 30.0, 8.0), (_RUNTIME_WIDTH_CM * 0.5 + 10.0, 22.0, 0.0)),
            },
            purpose=_purpose("dependency_or_engine_hooks", "swept_engine_hook"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="runtime_bundle.output_slots",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "runtime_output_slot",
                    {"profile_points": _hinge_profile(), "axis": "x"},
                    _purpose("runtime_output_slots", "output_slot_source"),
                ),
                "points": _runtime_port_points()[3:],
            },
            purpose=_purpose("runtime_output_slots", "copy_output_slots"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="runtime_bundle.version_badge",
            parameters={
                "profile_polygon": _rect_profile(18.0, 6.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, 38.0, -_RUNTIME_DEPTH_CM * 0.5 - 0.5),
            },
            purpose=_purpose("version_or_contract_badges", "raised_contract_badge"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="runtime_bundle.live_ticks",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "runtime_live_tick",
                    {"radius_cm": 1.2},
                    _purpose("hot_reload_or_live_update_cues", "live_tick_source"),
                ),
                "points": ((-18.0, 4.0, -19.0), (-9.0, 4.0, -19.0), (0.0, 4.0, -19.0), (9.0, 4.0, -19.0), (18.0, 4.0, -19.0)),
            },
            purpose=_purpose("hot_reload_or_live_update_cues", "copy_live_ticks"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="runtime_bundle.validation_guard",
            parameters={
                "radius_cm": 0.75,
                "path": ((-_RUNTIME_WIDTH_CM * 0.5, 1.5, -_RUNTIME_DEPTH_CM * 0.5), (_RUNTIME_WIDTH_CM * 0.5, 1.5, -_RUNTIME_DEPTH_CM * 0.5), (_RUNTIME_WIDTH_CM * 0.5, 1.5, _RUNTIME_DEPTH_CM * 0.5), (-_RUNTIME_WIDTH_CM * 0.5, 1.5, _RUNTIME_DEPTH_CM * 0.5), (-_RUNTIME_WIDTH_CM * 0.5, 1.5, -_RUNTIME_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("validation_or_guard_markers", "swept_validation_guard"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="runtime_bundle.cache_state_panel",
            parameters={
                "profile_polygon": _rect_profile(26.0, 7.0),
                "extrude_height_cm": 0.25,
                "axis": "z",
                "center": (0.0, 20.0, -_RUNTIME_DEPTH_CM * 0.5 - 0.55),
            },
            purpose=_purpose("state_or_cache_indicators", "raised_cache_state_panel"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="runtime_bundle.debug_ports",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "runtime_metric_tick",
                    {"profile_points": _rect_profile(2.0, 5.0), "height_cm": 0.25, "axis": "z"},
                    _purpose("runtime_metrics_or_debug_ports", "metric_tick_source"),
                ),
                "points": tuple((-20.0 + index * 8.0, 10.0, -_RUNTIME_DEPTH_CM * 0.5 - 0.7) for index in range(6)),
            },
            purpose=_purpose("runtime_metrics_or_debug_ports", "copy_metric_ticks"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="runtime_bundle.iteration_wear",
            parameters={"amount": 0.13, "override_bias": 0.7},
            purpose=_purpose("iteration_or_override_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.runtime_core", "primary_volume"),
        _node("recipe.runtime_input_ports", "socket"),
        _node("recipe.runtime_engine_hooks", "rail"),
        _node("recipe.runtime_output_slots", "socket"),
        _node("recipe.runtime_version_badge", "decal_zone"),
        _node("recipe.runtime_live_ticks", "fastener"),
        _node("recipe.runtime_validation_guard", "guard"),
        _node("recipe.runtime_cache_state", "panel"),
        _node("recipe.runtime_debug_ports", "fastener"),
        _node("recipe.runtime_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="live_procedural_runtime_bundle",
        family="live_procedural_runtime_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="live_procedural_runtime_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _engine_facing_runtime_bundle_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="engine_runtime.host_targets",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "engine_host_target_badge",
                    {
                        "width_cm": 16.0,
                        "height_cm": 9.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (1.2, 0.8, 1.1, 0.9, 0.7, 1.2, 0.8, 1.0),
                    },
                    _purpose("host_runtime_targets", "host_target_badge_source"),
                ),
                "points": _engine_host_target_points(),
            },
            purpose=_purpose("host_runtime_targets", "copy_host_runtime_targets"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="engine_runtime.plugin_adapters",
            parameters={
                "radius_cm": 0.64,
                "path": ((-_ENGINE_RUNTIME_WIDTH_CM * 0.54, 22.0, -16.0), (-32.0, 36.0, -4.0), (0.0, 30.0, 12.0), (32.0, 36.0, -4.0), (_ENGINE_RUNTIME_WIDTH_CM * 0.54, 22.0, -16.0)),
            },
            purpose=_purpose("plugin_adapter_contracts", "swept_plugin_adapter_contracts"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="engine_runtime.bundle_manifest",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "lathe_bundle_manifest_plate",
                    {"profile_points": _rect_profile(62.0, 10.0), "height_cm": 0.28, "axis": "y"},
                    _purpose("lathe_bundle_manifest", "bundle_manifest_plate_source"),
                ),
                "distance_cm": 1.6,
                "axis": "z",
            },
            purpose=_purpose("lathe_bundle_manifest", "raised_lathe_bundle_manifest"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="engine_runtime.parameter_overrides",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "host_parameter_override_knob",
                    {"profile_points": _rivet_profile(), "axis": "x"},
                    _purpose("parameter_override_schema", "override_knob_source"),
                ),
                "points": _engine_adapter_port_points()[:3],
            },
            purpose=_purpose("parameter_override_schema", "copy_parameter_override_schema"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="engine_runtime.live_evaluation_hooks",
            parameters={
                "radius_cm": 0.48,
                "path": ((-48.0, 8.0, 30.0), (-24.0, 18.0, 38.0), (0.0, 12.0, 42.0), (24.0, 18.0, 38.0), (48.0, 8.0, 30.0)),
            },
            purpose=_purpose("live_evaluation_hooks", "swept_live_evaluation_hooks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="engine_runtime.asset_output_sinks",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "engine_asset_output_sink",
                    {"profile_points": _hinge_profile(), "axis": "x"},
                    _purpose("engine_asset_output_sinks", "asset_sink_source"),
                ),
                "points": _engine_adapter_port_points()[3:],
            },
            purpose=_purpose("engine_asset_output_sinks", "copy_engine_asset_output_sinks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="engine_runtime.usd_hydra_targets",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "usd_hydra_prim_badge",
                    {"profile_points": _rect_profile(12.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("usd_hydra_procedural_target", "usd_hydra_badge_source"),
                ),
                "points": ((-42.0, 40.0, 30.0), (-14.0, 44.0, 36.0), (14.0, 44.0, 36.0), (42.0, 40.0, 30.0)),
            },
            purpose=_purpose("usd_hydra_procedural_target", "copy_usd_hydra_procedural_targets"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="engine_runtime.abi_guards",
            parameters={
                "radius_cm": 0.6,
                "path": ((-_ENGINE_RUNTIME_WIDTH_CM * 0.5, 4.0, -_ENGINE_RUNTIME_DEPTH_CM * 0.5), (_ENGINE_RUNTIME_WIDTH_CM * 0.5, 4.0, -_ENGINE_RUNTIME_DEPTH_CM * 0.5), (_ENGINE_RUNTIME_WIDTH_CM * 0.5, 48.0, -_ENGINE_RUNTIME_DEPTH_CM * 0.5), (-_ENGINE_RUNTIME_WIDTH_CM * 0.5, 48.0, -_ENGINE_RUNTIME_DEPTH_CM * 0.5), (-_ENGINE_RUNTIME_WIDTH_CM * 0.5, 4.0, -_ENGINE_RUNTIME_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("version_abi_guards", "swept_version_abi_guard_frame"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="engine_runtime.diagnostics_ports",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "runtime_diagnostic_tick",
                    {"profile_points": _rect_profile(2.2, 6.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("runtime_diagnostics_ports", "diagnostic_tick_source"),
                ),
                "points": tuple((-48.0 + index * 12.0, 10.0, -36.0) for index in range(9)),
            },
            purpose=_purpose("runtime_diagnostics_ports", "copy_runtime_diagnostics_ports"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="engine_runtime.host_iteration_wear",
            parameters={"amount": 0.08, "host_runtime_review_bias": 0.86},
            purpose=_purpose("host_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.engine_host_targets", "primary_volume"),
        _node("recipe.engine_plugin_adapters", "rail"),
        _node("recipe.engine_bundle_manifest", "panel"),
        _node("recipe.engine_parameter_overrides", "socket"),
        _node("recipe.engine_live_hooks", "rail"),
        _node("recipe.engine_asset_output_sinks", "socket"),
        _node("recipe.engine_usd_hydra_targets", "decal_zone"),
        _node("recipe.engine_abi_guards", "guard"),
        _node("recipe.engine_diagnostics_ports", "fastener"),
        _node("recipe.engine_host_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="engine_facing_runtime_bundle_system",
        family="engine_facing_runtime_bundle_system",
        ops=ops,
    )
    return RecipeResult(
        family="engine_facing_runtime_bundle_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _procedural_prefab_binding_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="prefab_binding.root",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "prefab_root_binding",
                    {
                        "width_cm": _PREFAB_BINDING_WIDTH_CM,
                        "height_cm": _PREFAB_BINDING_HEIGHT_CM,
                        "depth_cm": _PREFAB_BINDING_DEPTH_CM,
                        "corner_radii_cm": (1.8, 1.2, 1.6, 1.4, 1.0, 1.9, 1.2, 1.5),
                    },
                    _purpose("prefab_root_binding", "prefab_root_source"),
                ),
                "width_cm": 1.0,
                "segments": 4,
            },
            purpose=_purpose("prefab_root_binding", "polybeveled_prefab_root_binding"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="prefab_binding.source_slots",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "prefab_source_asset_slot",
                    {"profile_points": _rect_profile(10.0, 5.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("source_asset_slots", "source_slot_source"),
                ),
                "points": _prefab_source_slot_points(),
            },
            purpose=_purpose("source_asset_slots", "copy_source_asset_slots"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="prefab_binding.parameter_table",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "prefab_parameter_binding_table",
                    {"profile_points": _rect_profile(54.0, 8.0), "height_cm": 0.26, "axis": "y"},
                    _purpose("parameter_binding_table", "parameter_table_source"),
                ),
                "distance_cm": 1.4,
                "axis": "z",
            },
            purpose=_purpose("parameter_binding_table", "raised_parameter_binding_table"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="prefab_binding.variant_overrides",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "prefab_variant_override",
                    {"profile_points": _rect_profile(12.0, 5.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("variant_override_map", "variant_override_source"),
                ),
                "points": _prefab_binding_points(),
            },
            purpose=_purpose("variant_override_map", "copy_variant_override_map"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="prefab_binding.lod_streaming",
            parameters={
                "radius_cm": 0.5,
                "path": ((-48.0, 10.0, -32.0), (-24.0, 18.0, -38.0), (0.0, 14.0, -42.0), (24.0, 18.0, -38.0), (48.0, 10.0, -32.0)),
            },
            purpose=_purpose("lod_streaming_bindings", "swept_lod_streaming_bindings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="prefab_binding.material_surfaces",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "prefab_material_binding_chip",
                    {"profile_points": _rect_profile(11.0, 4.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("material_surface_bindings", "material_binding_chip_source"),
                ),
                "points": ((-42.0, 36.0, -34.0), (-14.0, 40.0, -38.0), (14.0, 40.0, -38.0), (42.0, 36.0, -34.0)),
            },
            purpose=_purpose("material_surface_bindings", "copy_material_surface_bindings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="prefab_binding.collision_physics",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "prefab_collision_binding",
                    {
                        "width_cm": 12.0,
                        "height_cm": 8.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (1.0, 0.8, 1.1, 0.9, 0.7, 1.0, 0.8, 0.9),
                    },
                    _purpose("collision_physics_bindings", "collision_binding_source"),
                ),
                "points": ((-36.0, 8.0, 32.0), (-12.0, 10.0, 38.0), (12.0, 10.0, 38.0), (36.0, 8.0, 32.0)),
            },
            purpose=_purpose("collision_physics_bindings", "copy_collision_physics_bindings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="prefab_binding.engine_exports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "prefab_engine_export_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("engine_export_targets", "engine_export_port_source"),
                ),
                "points": ((-48.0, 4.0, -36.0), (-16.0, 4.0, -40.0), (16.0, 4.0, -40.0), (48.0, 4.0, -36.0)),
            },
            purpose=_purpose("engine_export_targets", "copy_engine_export_targets"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="prefab_binding.dependency_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_PREFAB_BINDING_WIDTH_CM * 0.5, 4.0, -_PREFAB_BINDING_DEPTH_CM * 0.5), (_PREFAB_BINDING_WIDTH_CM * 0.5, 4.0, -_PREFAB_BINDING_DEPTH_CM * 0.5), (_PREFAB_BINDING_WIDTH_CM * 0.5, 38.0, -_PREFAB_BINDING_DEPTH_CM * 0.5), (-_PREFAB_BINDING_WIDTH_CM * 0.5, 38.0, -_PREFAB_BINDING_DEPTH_CM * 0.5), (-_PREFAB_BINDING_WIDTH_CM * 0.5, 4.0, -_PREFAB_BINDING_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("dependency_update_guards", "swept_dependency_update_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="prefab_binding.iteration_wear",
            parameters={"amount": 0.08, "prefab_binding_review_bias": 0.84},
            purpose=_purpose("prefab_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.prefab_root_binding", "primary_volume"),
        _node("recipe.prefab_source_slots", "socket"),
        _node("recipe.prefab_parameter_table", "panel"),
        _node("recipe.prefab_variant_overrides", "material_zone"),
        _node("recipe.prefab_lod_streaming", "rail"),
        _node("recipe.prefab_material_bindings", "material_zone"),
        _node("recipe.prefab_collision_bindings", "guard"),
        _node("recipe.prefab_engine_exports", "socket"),
        _node("recipe.prefab_dependency_guards", "guard"),
        _node("recipe.prefab_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="procedural_prefab_binding_system",
        family="procedural_prefab_binding_system",
        ops=ops,
    )
    return RecipeResult(
        family="procedural_prefab_binding_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _scene_system_authoring_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="scene_authoring.root_hierarchy",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "scene_root_hierarchy",
                    {
                        "width_cm": _SCENE_AUTHORING_WIDTH_CM,
                        "height_cm": _SCENE_AUTHORING_HEIGHT_CM,
                        "depth_cm": _SCENE_AUTHORING_DEPTH_CM,
                        "corner_radii_cm": (1.8, 1.2, 1.6, 1.4, 1.0, 1.8, 1.2, 1.5),
                    },
                    _purpose("scene_root_or_hierarchy", "scene_root_source"),
                ),
                "width_cm": 1.0,
                "segments": 4,
            },
            purpose=_purpose("scene_root_or_hierarchy", "polybeveled_scene_root_hierarchy"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scene_authoring.placement_anchors",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "scene_transform_anchor",
                    {"major_radius_cm": 2.6, "minor_radius_cm": 0.2, "axis": "y"},
                    _purpose("transform_or_placement_anchors", "transform_anchor_source"),
                ),
                "points": _scene_anchor_points(),
            },
            purpose=_purpose("transform_or_placement_anchors", "copy_transform_placement_anchors"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scene_authoring.spawn_layers",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "scene_spawn_layer_chip",
                    {"profile_points": _rect_profile(11.0, 5.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("spawn_or_population_layers", "spawn_layer_source"),
                ),
                "points": _scene_layer_points(),
            },
            purpose=_purpose("spawn_or_population_layers", "copy_spawn_population_layers"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="scene_authoring.lighting_camera",
            parameters={
                "radius_cm": 0.48,
                "path": ((-54.0, 34.0, 28.0), (-27.0, 44.0, 36.0), (0.0, 38.0, 42.0), (27.0, 44.0, 36.0), (54.0, 34.0, 28.0)),
            },
            purpose=_purpose("lighting_camera_bookmarks", "swept_lighting_camera_bookmarks"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="scene_authoring.navigation_regions",
            parameters={
                "radius_cm": 0.52,
                "path": ((-_SCENE_AUTHORING_WIDTH_CM * 0.42, 8.0, -8.0), (-32.0, 18.0, 4.0), (0.0, 12.0, 18.0), (32.0, 18.0, 4.0), (_SCENE_AUTHORING_WIDTH_CM * 0.42, 8.0, -8.0)),
            },
            purpose=_purpose("navigation_regions", "swept_navigation_regions"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scene_authoring.environment_volumes",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "scene_environment_volume",
                    {
                        "width_cm": 13.0,
                        "height_cm": 8.0,
                        "depth_cm": 10.0,
                        "corner_radii_cm": (1.0, 0.8, 1.2, 0.9, 0.7, 1.1, 0.8, 1.0),
                    },
                    _purpose("environment_volume_layers", "environment_volume_source"),
                ),
                "points": ((-42.0, 28.0, 34.0), (-14.0, 32.0, 40.0), (14.0, 32.0, 40.0), (42.0, 28.0, 34.0)),
            },
            purpose=_purpose("environment_volume_layers", "copy_environment_volume_layers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scene_authoring.streaming_tags",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "scene_streaming_tag",
                    {"profile_points": _rect_profile(10.0, 4.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("streaming_or_occlusion_tags", "streaming_tag_source"),
                ),
                "points": ((-48.0, 6.0, -38.0), (-24.0, 6.0, -42.0), (0.0, 6.0, -44.0), (24.0, 6.0, -42.0), (48.0, 6.0, -38.0)),
            },
            purpose=_purpose("streaming_or_occlusion_tags", "copy_streaming_occlusion_tags"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scene_authoring.export_targets",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "scene_export_target_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("scene_export_targets", "scene_export_target_source"),
                ),
                "points": ((-54.0, 4.0, 34.0), (-18.0, 4.0, 40.0), (18.0, 4.0, 40.0), (54.0, 4.0, 34.0)),
            },
            purpose=_purpose("scene_export_targets", "copy_scene_export_targets"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="scene_authoring.validation_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_SCENE_AUTHORING_WIDTH_CM * 0.5, 4.0, -_SCENE_AUTHORING_DEPTH_CM * 0.5), (_SCENE_AUTHORING_WIDTH_CM * 0.5, 4.0, -_SCENE_AUTHORING_DEPTH_CM * 0.5), (_SCENE_AUTHORING_WIDTH_CM * 0.5, 44.0, -_SCENE_AUTHORING_DEPTH_CM * 0.5), (-_SCENE_AUTHORING_WIDTH_CM * 0.5, 44.0, -_SCENE_AUTHORING_DEPTH_CM * 0.5), (-_SCENE_AUTHORING_WIDTH_CM * 0.5, 4.0, -_SCENE_AUTHORING_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("scene_validation_guards", "swept_scene_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="scene_authoring.iteration_wear",
            parameters={"amount": 0.08, "scene_authoring_review_bias": 0.84},
            purpose=_purpose("scene_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.scene_root_hierarchy", "primary_volume"),
        _node("recipe.scene_placement_anchors", "mount"),
        _node("recipe.scene_spawn_layers", "socket"),
        _node("recipe.scene_lighting_camera", "rail"),
        _node("recipe.scene_navigation_regions", "rail"),
        _node("recipe.scene_environment_volumes", "material_zone"),
        _node("recipe.scene_streaming_tags", "panel"),
        _node("recipe.scene_export_targets", "socket"),
        _node("recipe.scene_validation_guards", "guard"),
        _node("recipe.scene_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="scene_system_authoring_bundle",
        family="scene_system_authoring_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="scene_system_authoring_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _behavior_logic_graph_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="behavior_logic.state_nodes",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "behavior_logic_node",
                    {
                        "width_cm": 12.0,
                        "height_cm": 8.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (1.2, 0.8, 1.1, 0.9, 0.7, 1.1, 0.8, 1.0),
                    },
                    _purpose("state_or_behavior_nodes", "logic_node_source"),
                ),
                "points": _behavior_node_points(),
            },
            purpose=_purpose("state_or_behavior_nodes", "copy_state_behavior_nodes"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="behavior_logic.event_edges",
            parameters={
                "radius_cm": 0.48,
                "path": ((-52.0, 28.0, -8.0), (-26.0, 38.0, 4.0), (0.0, 30.0, 16.0), (26.0, 38.0, 4.0), (52.0, 28.0, -8.0)),
            },
            purpose=_purpose("event_signal_edges", "swept_event_signal_edges"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="behavior_logic.condition_rules",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "behavior_condition_rule_table",
                    {"profile_points": _rect_profile(52.0, 8.0), "height_cm": 0.26, "axis": "y"},
                    _purpose("condition_rule_tables", "condition_rule_table_source"),
                ),
                "distance_cm": 1.4,
                "axis": "z",
            },
            purpose=_purpose("condition_rule_tables", "raised_condition_rule_tables"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="behavior_logic.action_outputs",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "behavior_action_output_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("action_output_ports", "action_output_source"),
                ),
                "points": _behavior_port_points(),
            },
            purpose=_purpose("action_output_ports", "copy_action_output_ports"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="behavior_logic.blackboard_bindings",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "blackboard_memory_binding",
                    {"profile_points": _rect_profile(10.0, 4.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("blackboard_or_memory_bindings", "blackboard_binding_source"),
                ),
                "points": ((-42.0, 34.0, 34.0), (-14.0, 38.0, 40.0), (14.0, 38.0, 40.0), (42.0, 34.0, 34.0)),
            },
            purpose=_purpose("blackboard_or_memory_bindings", "copy_blackboard_memory_bindings"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="behavior_logic.timer_tracks",
            parameters={
                "radius_cm": 0.42,
                "path": ((-48.0, 8.0, -34.0), (-24.0, 16.0, -40.0), (0.0, 12.0, -44.0), (24.0, 16.0, -40.0), (48.0, 8.0, -34.0)),
            },
            purpose=_purpose("timer_or_cooldown_tracks", "swept_timer_cooldown_tracks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="behavior_logic.utility_weights",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "behavior_priority_weight",
                    {"radius_cm": 1.8},
                    _purpose("priority_or_utility_weights", "priority_weight_source"),
                ),
                "points": tuple((-42.0 + index * 14.0, 6.0, 30.0) for index in range(7)),
            },
            purpose=_purpose("priority_or_utility_weights", "copy_priority_utility_weights"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="behavior_logic.failure_paths",
            parameters={
                "radius_cm": 0.5,
                "path": ((-52.0, 18.0, 22.0), (-26.0, 8.0, 34.0), (0.0, 16.0, 42.0), (26.0, 8.0, 34.0), (52.0, 18.0, 22.0)),
            },
            purpose=_purpose("failure_or_fallback_paths", "swept_failure_fallback_paths"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="behavior_logic.debug_ports",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "behavior_debug_trace_port",
                    {"major_radius_cm": 2.2, "minor_radius_cm": 0.18, "axis": "y"},
                    _purpose("debug_trace_ports", "debug_trace_port_source"),
                ),
                "points": ((-42.0, 30.0, -36.0), (-14.0, 34.0, -40.0), (14.0, 34.0, -40.0), (42.0, 30.0, -36.0)),
            },
            purpose=_purpose("debug_trace_ports", "copy_debug_trace_ports"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="behavior_logic.iteration_wear",
            parameters={"amount": 0.08, "behavior_logic_review_bias": 0.85},
            purpose=_purpose("behavior_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.behavior_state_nodes", "primary_volume"),
        _node("recipe.behavior_event_edges", "rail"),
        _node("recipe.behavior_condition_rules", "panel"),
        _node("recipe.behavior_action_outputs", "socket"),
        _node("recipe.behavior_blackboard_bindings", "decal_zone"),
        _node("recipe.behavior_timer_tracks", "rail"),
        _node("recipe.behavior_utility_weights", "fastener"),
        _node("recipe.behavior_failure_paths", "guard"),
        _node("recipe.behavior_debug_ports", "socket"),
        _node("recipe.behavior_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="behavior_logic_graph_bundle",
        family="behavior_logic_graph_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="behavior_logic_graph_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _world_streaming_runtime_partition_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="world_streaming.partition_root",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "world_partition_root",
                    {
                        "width_cm": _WORLD_STREAMING_WIDTH_CM,
                        "height_cm": _WORLD_STREAMING_HEIGHT_CM,
                        "depth_cm": _WORLD_STREAMING_DEPTH_CM,
                        "corner_radii_cm": (1.6, 1.1, 1.4, 1.3, 1.0, 1.6, 1.2, 1.4),
                    },
                    _purpose("world_partition_root", "partition_root_source"),
                ),
                "width_cm": 1.0,
                "segments": 4,
            },
            purpose=_purpose("world_partition_root", "polybeveled_world_partition_root"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_streaming.sector_grid",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "streaming_sector_cell",
                    {"profile_points": _rect_profile(10.0, 7.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("sector_or_cell_grid", "sector_cell_source"),
                ),
                "points": _streaming_cell_points(),
            },
            purpose=_purpose("sector_or_cell_grid", "copy_sector_cell_grid"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_streaming.volume_bounds",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "streaming_volume_bound",
                    {
                        "width_cm": 16.0,
                        "height_cm": 10.0,
                        "depth_cm": 14.0,
                        "corner_radii_cm": (1.0, 0.8, 1.2, 0.9, 0.7, 1.1, 0.8, 1.0),
                    },
                    _purpose("streaming_volume_bounds", "streaming_volume_source"),
                ),
                "points": _streaming_volume_points(),
            },
            purpose=_purpose("streaming_volume_bounds", "copy_streaming_volume_bounds"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="world_streaming.load_dependencies",
            parameters={
                "radius_cm": 0.5,
                "path": ((-60.0, 16.0, -10.0), (-30.0, 28.0, 0.0), (0.0, 20.0, 12.0), (30.0, 28.0, 0.0), (60.0, 16.0, -10.0)),
            },
            purpose=_purpose("load_group_dependencies", "swept_load_group_dependencies"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="world_streaming.lod_rings",
            parameters={
                "radius_cm": 0.46,
                "path": ((-62.0, 8.0, 36.0), (-31.0, 16.0, 46.0), (0.0, 10.0, 52.0), (31.0, 16.0, 46.0), (62.0, 8.0, 36.0)),
            },
            purpose=_purpose("lod_distance_rings", "swept_lod_distance_rings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_streaming.occlusion_regions",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "occlusion_visibility_region",
                    {"profile_points": _rect_profile(12.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("occlusion_visibility_regions", "occlusion_region_source"),
                ),
                "points": ((-48.0, 28.0, -46.0), (-16.0, 32.0, -52.0), (16.0, 32.0, -52.0), (48.0, 28.0, -46.0)),
            },
            purpose=_purpose("occlusion_visibility_regions", "copy_occlusion_visibility_regions"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_streaming.memory_budgets",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "streaming_memory_budget_marker",
                    {"radius_cm": 1.7},
                    _purpose("memory_budget_markers", "memory_budget_marker_source"),
                ),
                "points": tuple((-54.0 + index * 12.0, 6.0, -50.0) for index in range(10)),
            },
            purpose=_purpose("memory_budget_markers", "copy_memory_budget_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="world_streaming.asset_residency",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "asset_residency_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("asset_residency_ports", "asset_residency_port_source"),
                ),
                "points": ((-54.0, 4.0, 44.0), (-18.0, 4.0, 50.0), (18.0, 4.0, 50.0), (54.0, 4.0, 44.0)),
            },
            purpose=_purpose("asset_residency_ports", "copy_asset_residency_ports"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="world_streaming.partition_guards",
            parameters={
                "radius_cm": 0.6,
                "path": ((-_WORLD_STREAMING_WIDTH_CM * 0.5, 4.0, -_WORLD_STREAMING_DEPTH_CM * 0.5), (_WORLD_STREAMING_WIDTH_CM * 0.5, 4.0, -_WORLD_STREAMING_DEPTH_CM * 0.5), (_WORLD_STREAMING_WIDTH_CM * 0.5, 36.0, -_WORLD_STREAMING_DEPTH_CM * 0.5), (-_WORLD_STREAMING_WIDTH_CM * 0.5, 36.0, -_WORLD_STREAMING_DEPTH_CM * 0.5), (-_WORLD_STREAMING_WIDTH_CM * 0.5, 4.0, -_WORLD_STREAMING_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("partition_validation_guards", "swept_partition_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="world_streaming.iteration_wear",
            parameters={"amount": 0.08, "streaming_partition_review_bias": 0.85},
            purpose=_purpose("streaming_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.world_partition_root", "primary_volume"),
        _node("recipe.streaming_sector_grid", "panel"),
        _node("recipe.streaming_volume_bounds", "guard"),
        _node("recipe.streaming_load_dependencies", "rail"),
        _node("recipe.streaming_lod_rings", "rail"),
        _node("recipe.streaming_occlusion_regions", "material_zone"),
        _node("recipe.streaming_memory_budgets", "fastener"),
        _node("recipe.streaming_asset_residency", "socket"),
        _node("recipe.streaming_partition_guards", "guard"),
        _node("recipe.streaming_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="world_streaming_runtime_partition_bundle",
        family="world_streaming_runtime_partition_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="world_streaming_runtime_partition_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _save_state_persistence_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="save_state.root_manifest",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "save_state_root_manifest",
                    {
                        "width_cm": _SAVE_STATE_WIDTH_CM,
                        "height_cm": _SAVE_STATE_HEIGHT_CM,
                        "depth_cm": _SAVE_STATE_DEPTH_CM,
                        "corner_radii_cm": (1.6, 1.0, 1.4, 1.2, 0.9, 1.7, 1.1, 1.3),
                    },
                    _purpose("save_root_or_manifest", "save_manifest_source"),
                ),
                "width_cm": 1.0,
                "segments": 4,
            },
            purpose=_purpose("save_root_or_manifest", "polybeveled_save_root_manifest"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="save_state.checkpoint_slots",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "checkpoint_slot",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("checkpoint_slot_map", "checkpoint_slot_source"),
                ),
                "points": _save_slot_points(),
            },
            purpose=_purpose("checkpoint_slot_map", "copy_checkpoint_slot_map"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="save_state.actor_state",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "persistent_actor_state_row",
                    {"profile_points": _rect_profile(12.0, 5.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("persistent_actor_state", "actor_state_row_source"),
                ),
                "points": _save_state_table_points(),
            },
            purpose=_purpose("persistent_actor_state", "copy_persistent_actor_state"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="save_state.inventory_quest_tables",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "inventory_quest_state_table",
                    {"profile_points": _rect_profile(50.0, 8.0), "height_cm": 0.26, "axis": "y"},
                    _purpose("inventory_quest_state_tables", "inventory_quest_table_source"),
                ),
                "distance_cm": 1.4,
                "axis": "z",
            },
            purpose=_purpose("inventory_quest_state_tables", "raised_inventory_quest_state_tables"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="save_state.delta_log",
            parameters={
                "radius_cm": 0.44,
                "path": ((-44.0, 10.0, -34.0), (-22.0, 18.0, -40.0), (0.0, 12.0, -44.0), (22.0, 18.0, -40.0), (44.0, 10.0, -34.0)),
            },
            purpose=_purpose("world_state_delta_log", "swept_world_state_delta_log"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="save_state.schema_badges",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "save_schema_version_badge",
                    {"profile_points": _rect_profile(9.0, 4.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("schema_version_badges", "schema_badge_source"),
                ),
                "points": ((-42.0, 32.0, -34.0), (-14.0, 36.0, -40.0), (14.0, 36.0, -40.0), (42.0, 32.0, -34.0)),
            },
            purpose=_purpose("schema_version_badges", "copy_schema_version_badges"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="save_state.restore_paths",
            parameters={
                "radius_cm": 0.46,
                "path": ((-46.0, 8.0, 32.0), (-23.0, 18.0, 40.0), (0.0, 12.0, 44.0), (23.0, 18.0, 40.0), (46.0, 8.0, 32.0)),
            },
            purpose=_purpose("restore_path_edges", "swept_restore_path_edges"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="save_state.conflict_rules",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "conflict_resolution_rule",
                    {"major_radius_cm": 2.3, "minor_radius_cm": 0.18, "axis": "y"},
                    _purpose("conflict_resolution_rules", "conflict_rule_source"),
                ),
                "points": ((-36.0, 6.0, 34.0), (-12.0, 8.0, 40.0), (12.0, 8.0, 40.0), (36.0, 6.0, 34.0)),
            },
            purpose=_purpose("conflict_resolution_rules", "copy_conflict_resolution_rules"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="save_state.corruption_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_SAVE_STATE_WIDTH_CM * 0.5, 4.0, -_SAVE_STATE_DEPTH_CM * 0.5), (_SAVE_STATE_WIDTH_CM * 0.5, 4.0, -_SAVE_STATE_DEPTH_CM * 0.5), (_SAVE_STATE_WIDTH_CM * 0.5, 38.0, -_SAVE_STATE_DEPTH_CM * 0.5), (-_SAVE_STATE_WIDTH_CM * 0.5, 38.0, -_SAVE_STATE_DEPTH_CM * 0.5), (-_SAVE_STATE_WIDTH_CM * 0.5, 4.0, -_SAVE_STATE_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("corruption_validation_guards", "swept_corruption_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="save_state.iteration_wear",
            parameters={"amount": 0.08, "persistence_review_bias": 0.85},
            purpose=_purpose("persistence_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.save_root_manifest", "primary_volume"),
        _node("recipe.save_checkpoint_slots", "socket"),
        _node("recipe.save_actor_state", "panel"),
        _node("recipe.save_inventory_quest_tables", "panel"),
        _node("recipe.save_world_delta_log", "rail"),
        _node("recipe.save_schema_badges", "decal_zone"),
        _node("recipe.save_restore_paths", "rail"),
        _node("recipe.save_conflict_rules", "guard"),
        _node("recipe.save_corruption_guards", "guard"),
        _node("recipe.save_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="save_state_persistence_bundle",
        family="save_state_persistence_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="save_state_persistence_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _quest_dialogue_authoring_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="quest_dialogue.root_arc",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "quest_dialogue_root_arc",
                    {
                        "width_cm": _QUEST_DIALOGUE_WIDTH_CM,
                        "height_cm": _QUEST_DIALOGUE_HEIGHT_CM,
                        "depth_cm": _QUEST_DIALOGUE_DEPTH_CM,
                        "corner_radii_cm": (1.6, 1.0, 1.4, 1.2, 0.9, 1.6, 1.1, 1.3),
                    },
                    _purpose("quest_root_or_arc", "quest_root_source"),
                ),
                "width_cm": 1.0,
                "segments": 4,
            },
            purpose=_purpose("quest_root_or_arc", "polybeveled_quest_root_arc"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="quest_dialogue.objectives",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "quest_objective_node",
                    {"profile_points": _rect_profile(11.0, 5.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("objective_graph_nodes", "objective_node_source"),
                ),
                "points": _quest_objective_points(),
            },
            purpose=_purpose("objective_graph_nodes", "copy_objective_graph_nodes"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="quest_dialogue.dialogue_tree",
            parameters={
                "radius_cm": 0.46,
                "path": ((-54.0, 28.0, -8.0), (-27.0, 40.0, 4.0), (0.0, 32.0, 16.0), (27.0, 40.0, 4.0), (54.0, 28.0, -8.0)),
            },
            purpose=_purpose("dialogue_branch_tree", "swept_dialogue_branch_tree"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="quest_dialogue.choice_gates",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "dialogue_choice_condition_gate",
                    {"major_radius_cm": 2.4, "minor_radius_cm": 0.18, "axis": "y"},
                    _purpose("choice_condition_gates", "choice_gate_source"),
                ),
                "points": _dialogue_choice_points(),
            },
            purpose=_purpose("choice_condition_gates", "copy_choice_condition_gates"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="quest_dialogue.reward_tables",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "quest_reward_outcome_table",
                    {"profile_points": _rect_profile(52.0, 8.0), "height_cm": 0.26, "axis": "y"},
                    _purpose("reward_or_outcome_tables", "reward_table_source"),
                ),
                "distance_cm": 1.4,
                "axis": "z",
            },
            purpose=_purpose("reward_or_outcome_tables", "raised_reward_outcome_tables"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="quest_dialogue.npc_bindings",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "npc_dialogue_binding_port",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("npc_actor_bindings", "npc_binding_source"),
                ),
                "points": ((-48.0, 6.0, 34.0), (-16.0, 6.0, 40.0), (16.0, 6.0, 40.0), (48.0, 6.0, 34.0)),
            },
            purpose=_purpose("npc_actor_bindings", "copy_npc_actor_bindings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="quest_dialogue.localization_keys",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "dialogue_localization_key",
                    {"profile_points": _rect_profile(10.0, 4.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("localization_key_slots", "localization_key_source"),
                ),
                "points": ((-42.0, 32.0, -38.0), (-14.0, 36.0, -44.0), (14.0, 36.0, -44.0), (42.0, 32.0, -38.0)),
            },
            purpose=_purpose("localization_key_slots", "copy_localization_key_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="quest_dialogue.conversation_state",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "conversation_state_flag",
                    {"radius_cm": 1.6},
                    _purpose("conversation_state_flags", "conversation_state_flag_source"),
                ),
                "points": tuple((-42.0 + index * 14.0, 6.0, -38.0) for index in range(7)),
            },
            purpose=_purpose("conversation_state_flags", "copy_conversation_state_flags"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="quest_dialogue.validation_guards",
            parameters={
                "radius_cm": 0.58,
                "path": ((-_QUEST_DIALOGUE_WIDTH_CM * 0.5, 4.0, -_QUEST_DIALOGUE_DEPTH_CM * 0.5), (_QUEST_DIALOGUE_WIDTH_CM * 0.5, 4.0, -_QUEST_DIALOGUE_DEPTH_CM * 0.5), (_QUEST_DIALOGUE_WIDTH_CM * 0.5, 38.0, -_QUEST_DIALOGUE_DEPTH_CM * 0.5), (-_QUEST_DIALOGUE_WIDTH_CM * 0.5, 38.0, -_QUEST_DIALOGUE_DEPTH_CM * 0.5), (-_QUEST_DIALOGUE_WIDTH_CM * 0.5, 4.0, -_QUEST_DIALOGUE_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("narrative_validation_guards", "swept_narrative_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="quest_dialogue.iteration_wear",
            parameters={"amount": 0.08, "quest_dialogue_review_bias": 0.86},
            purpose=_purpose("quest_dialogue_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.quest_root_arc", "primary_volume"),
        _node("recipe.quest_objectives", "panel"),
        _node("recipe.dialogue_branch_tree", "rail"),
        _node("recipe.dialogue_choice_gates", "guard"),
        _node("recipe.quest_reward_tables", "material_zone"),
        _node("recipe.npc_dialogue_bindings", "socket"),
        _node("recipe.dialogue_localization_keys", "decal_zone"),
        _node("recipe.conversation_state_flags", "fastener"),
        _node("recipe.narrative_validation_guards", "guard"),
        _node("recipe.quest_dialogue_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="quest_dialogue_authoring_bundle",
        family="quest_dialogue_authoring_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="quest_dialogue_authoring_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _camera_cinematic_direction_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="camera_cinematic.rig_roots",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "camera_rig_root",
                    {"profile_points": _hinge_profile(), "axis": "y"},
                    _purpose("camera_rig_roots", "camera_rig_root_source"),
                ),
                "points": ((-48.0, 24.0, -30.0), (-16.0, 30.0, -36.0), (16.0, 30.0, -36.0), (48.0, 24.0, -30.0)),
            },
            purpose=_purpose("camera_rig_roots", "copy_camera_rig_roots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="camera_cinematic.shot_sequence",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cinematic_shot_card",
                    {"profile_points": _rect_profile(11.0, 6.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("shot_sequence_graph", "shot_card_source"),
                ),
                "points": _camera_shot_points(),
            },
            purpose=_purpose("shot_sequence_graph", "copy_shot_sequence_graph"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="camera_cinematic.camera_paths",
            parameters={
                "radius_cm": 0.5,
                "path": ((-54.0, 20.0, 2.0), (-27.0, 38.0, 12.0), (0.0, 28.0, 24.0), (27.0, 38.0, 12.0), (54.0, 20.0, 2.0)),
            },
            purpose=_purpose("camera_path_tracks", "swept_camera_path_tracks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="camera_cinematic.lens_bindings",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "lens_fov_binding",
                    {"major_radius_cm": 2.4, "minor_radius_cm": 0.18, "axis": "y"},
                    _purpose("lens_or_fov_bindings", "lens_binding_source"),
                ),
                "points": ((-42.0, 36.0, 34.0), (-14.0, 40.0, 40.0), (14.0, 40.0, 40.0), (42.0, 36.0, 34.0)),
            },
            purpose=_purpose("lens_or_fov_bindings", "copy_lens_fov_bindings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="camera_cinematic.timeline_beats",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "timeline_beat_marker",
                    {"radius_cm": 1.5},
                    _purpose("timeline_beat_markers", "timeline_beat_source"),
                ),
                "points": tuple((-48.0 + index * 12.0, 6.0, -38.0) for index in range(9)),
            },
            purpose=_purpose("timeline_beat_markers", "copy_timeline_beat_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="camera_cinematic.look_at_targets",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "camera_look_at_target",
                    {"major_radius_cm": 2.2, "minor_radius_cm": 0.16, "axis": "z"},
                    _purpose("look_at_target_tracks", "look_at_target_source"),
                ),
                "points": _camera_target_points(),
            },
            purpose=_purpose("look_at_target_tracks", "copy_look_at_target_tracks"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="camera_cinematic.blend_stack",
            parameters={
                "radius_cm": 0.44,
                "path": ((-50.0, 12.0, 36.0), (-25.0, 22.0, 44.0), (0.0, 16.0, 48.0), (25.0, 22.0, 44.0), (50.0, 12.0, 36.0)),
            },
            purpose=_purpose("blend_or_transition_stack", "swept_blend_transition_stack"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="camera_cinematic.safe_regions",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "framing_safe_region",
                    {"profile_points": _rect_profile(52.0, 9.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("framing_safe_regions", "framing_safe_region_source"),
                ),
                "distance_cm": 1.3,
                "axis": "z",
            },
            purpose=_purpose("framing_safe_regions", "raised_framing_safe_regions"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="camera_cinematic.trigger_outputs",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "cinematic_trigger_output",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("cinematic_trigger_outputs", "cinematic_trigger_source"),
                ),
                "points": ((-48.0, 4.0, 38.0), (-16.0, 4.0, 44.0), (16.0, 4.0, 44.0), (48.0, 4.0, 38.0)),
            },
            purpose=_purpose("cinematic_trigger_outputs", "copy_cinematic_trigger_outputs"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="camera_cinematic.iteration_wear",
            parameters={"amount": 0.08, "cinematic_review_bias": 0.85},
            purpose=_purpose("cinematic_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.camera_rig_roots", "primary_volume"),
        _node("recipe.cinematic_shot_sequence", "panel"),
        _node("recipe.camera_path_tracks", "rail"),
        _node("recipe.lens_fov_bindings", "socket"),
        _node("recipe.timeline_beat_markers", "fastener"),
        _node("recipe.look_at_targets", "socket"),
        _node("recipe.blend_transition_stack", "rail"),
        _node("recipe.framing_safe_regions", "guard"),
        _node("recipe.cinematic_trigger_outputs", "socket"),
        _node("recipe.cinematic_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="camera_cinematic_direction_bundle",
        family="camera_cinematic_direction_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="camera_cinematic_direction_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _procedural_audio_cue_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="audio_cue.root_graph",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "procedural_audio_cue_root",
                    {
                        "width_cm": _AUDIO_CUE_WIDTH_CM,
                        "height_cm": _AUDIO_CUE_HEIGHT_CM,
                        "depth_cm": _AUDIO_CUE_DEPTH_CM,
                        "corner_radii_cm": (1.2, 1.4, 0.9, 1.5, 1.1, 1.3, 1.6, 1.0),
                    },
                    _purpose("audio_cue_roots", "audio_cue_root_source"),
                ),
                "width_cm": 0.9,
                "segments": 4,
            },
            purpose=_purpose("audio_cue_roots", "polybeveled_audio_cue_root"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="audio_cue.sfx_music_events",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "sfx_music_event_node",
                    {"profile_points": _rect_profile(10.0, 5.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("sfx_or_music_event_nodes", "audio_event_node_source"),
                ),
                "points": _audio_event_points(),
            },
            purpose=_purpose("sfx_or_music_event_nodes", "copy_sfx_music_event_nodes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="audio_cue.timing_triggers",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "audio_timing_trigger_marker",
                    {"radius_cm": 1.45},
                    _purpose("timing_trigger_markers", "timing_trigger_source"),
                ),
                "points": tuple((-48.0 + index * 12.0, 6.0, -34.0) for index in range(9)),
            },
            purpose=_purpose("timing_trigger_markers", "copy_timing_trigger_markers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="audio_cue.attenuation_zones",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "audio_attenuation_zone",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.18, "axis": "y"},
                    _purpose("attenuation_spatial_zones", "attenuation_zone_source"),
                ),
                "points": ((-42.0, 24.0, 30.0), (-14.0, 28.0, 38.0), (14.0, 28.0, 38.0), (42.0, 24.0, 30.0)),
            },
            purpose=_purpose("attenuation_spatial_zones", "copy_attenuation_spatial_zones"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="audio_cue.reverb_mixer_sends",
            parameters={
                "radius_cm": 0.42,
                "path": ((-50.0, 18.0, 6.0), (-25.0, 30.0, 16.0), (0.0, 24.0, 24.0), (25.0, 30.0, 16.0), (50.0, 18.0, 6.0)),
            },
            purpose=_purpose("reverb_or_mixer_sends", "swept_reverb_mixer_send_paths"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="audio_cue.voiceover_triggers",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "voiceover_trigger_binding",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("voiceover_trigger_bindings", "voiceover_trigger_source"),
                ),
                "points": ((-44.0, 6.0, 36.0), (-14.0, 6.0, 42.0), (14.0, 6.0, 42.0), (44.0, 6.0, 36.0)),
            },
            purpose=_purpose("voiceover_trigger_bindings", "copy_voiceover_trigger_bindings"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="audio_cue.loop_layer_controls",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "audio_loop_layer_control",
                    {"profile_points": _rect_profile(50.0, 7.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("loop_or_layer_controls", "loop_layer_control_source"),
                ),
                "distance_cm": 1.2,
                "axis": "z",
            },
            purpose=_purpose("loop_or_layer_controls", "raised_loop_layer_controls"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="audio_cue.runtime_outputs",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "runtime_audio_output_bus",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("runtime_audio_outputs", "runtime_audio_bus_source"),
                ),
                "points": _audio_bus_points(),
            },
            purpose=_purpose("runtime_audio_outputs", "copy_runtime_audio_outputs"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="audio_cue.loudness_guards",
            parameters={
                "radius_cm": 0.54,
                "path": ((-_AUDIO_CUE_WIDTH_CM * 0.5, 4.0, -_AUDIO_CUE_DEPTH_CM * 0.5), (_AUDIO_CUE_WIDTH_CM * 0.5, 4.0, -_AUDIO_CUE_DEPTH_CM * 0.5), (_AUDIO_CUE_WIDTH_CM * 0.5, 34.0, -_AUDIO_CUE_DEPTH_CM * 0.5), (-_AUDIO_CUE_WIDTH_CM * 0.5, 34.0, -_AUDIO_CUE_DEPTH_CM * 0.5), (-_AUDIO_CUE_WIDTH_CM * 0.5, 4.0, -_AUDIO_CUE_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("loudness_validation_guards", "swept_loudness_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="audio_cue.iteration_wear",
            parameters={"amount": 0.07, "audio_review_bias": 0.84},
            purpose=_purpose("audio_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.audio_cue_root", "primary_volume"),
        _node("recipe.sfx_music_events", "panel"),
        _node("recipe.audio_timing_triggers", "fastener"),
        _node("recipe.audio_attenuation_zones", "guard"),
        _node("recipe.reverb_mixer_sends", "rail"),
        _node("recipe.voiceover_trigger_bindings", "socket"),
        _node("recipe.loop_layer_controls", "panel"),
        _node("recipe.runtime_audio_outputs", "socket"),
        _node("recipe.loudness_validation_guards", "guard"),
        _node("recipe.audio_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="procedural_audio_cue_bundle",
        family="procedural_audio_cue_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="procedural_audio_cue_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _localization_text_table_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="localization_text.table_root",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "localization_text_table_root",
                    {
                        "width_cm": _LOCALIZATION_TEXT_WIDTH_CM,
                        "height_cm": _LOCALIZATION_TEXT_HEIGHT_CM,
                        "depth_cm": _LOCALIZATION_TEXT_DEPTH_CM,
                        "corner_radii_cm": (1.1, 1.5, 1.0, 1.4, 1.3, 0.9, 1.6, 1.2),
                    },
                    _purpose("locale_table_roots", "localization_table_root_source"),
                ),
                "width_cm": 0.9,
                "segments": 4,
            },
            purpose=_purpose("locale_table_roots", "polybeveled_localization_table_root"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="localization_text.string_keys",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "string_key_row",
                    {"profile_points": _rect_profile(12.0, 4.5), "height_cm": 0.22, "axis": "y"},
                    _purpose("string_key_rows", "string_key_row_source"),
                ),
                "points": _localization_key_points(),
            },
            purpose=_purpose("string_key_rows", "copy_string_key_rows"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="localization_text.translation_columns",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "translation_value_column",
                    {"profile_points": _rect_profile(8.0, 12.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("translation_value_columns", "translation_column_source"),
                ),
                "points": _locale_column_points(),
            },
            purpose=_purpose("translation_value_columns", "copy_translation_value_columns"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="localization_text.pluralization_rules",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "pluralization_gender_rule",
                    {"major_radius_cm": 2.4, "minor_radius_cm": 0.18, "axis": "y"},
                    _purpose("pluralization_or_gender_rules", "pluralization_rule_source"),
                ),
                "points": ((-46.0, 8.0, -38.0), (-15.0, 8.0, -44.0), (15.0, 8.0, -44.0), (46.0, 8.0, -38.0)),
            },
            purpose=_purpose("pluralization_or_gender_rules", "copy_pluralization_gender_rules"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="localization_text.fallback_chains",
            parameters={
                "radius_cm": 0.44,
                "path": ((-54.0, 16.0, 8.0), (-27.0, 30.0, 18.0), (0.0, 24.0, 28.0), (27.0, 30.0, 18.0), (54.0, 16.0, 8.0)),
            },
            purpose=_purpose("fallback_locale_chains", "swept_fallback_locale_chains"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="localization_text.subtitle_timing",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "subtitle_timing_tick",
                    {"radius_cm": 1.35},
                    _purpose("subtitle_timing_rows", "subtitle_timing_tick_source"),
                ),
                "points": tuple((-54.0 + index * 13.5, 6.0, 38.0) for index in range(9)),
            },
            purpose=_purpose("subtitle_timing_rows", "copy_subtitle_timing_rows"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="localization_text.voiceover_bindings",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "voiceover_text_binding",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("voiceover_text_bindings", "voiceover_text_binding_source"),
                ),
                "points": ((-48.0, 4.0, 42.0), (-16.0, 4.0, 48.0), (16.0, 4.0, 48.0), (48.0, 4.0, 42.0)),
            },
            purpose=_purpose("voiceover_text_bindings", "copy_voiceover_text_bindings"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="localization_text.glyph_coverage",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "glyph_font_coverage_tile",
                    {"profile_points": _rect_profile(50.0, 8.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("glyph_or_font_coverage", "glyph_coverage_tile_source"),
                ),
                "distance_cm": 1.2,
                "axis": "z",
            },
            purpose=_purpose("glyph_or_font_coverage", "raised_glyph_font_coverage_tiles"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="localization_text.validation_guards",
            parameters={
                "radius_cm": 0.54,
                "path": ((-_LOCALIZATION_TEXT_WIDTH_CM * 0.5, 4.0, -_LOCALIZATION_TEXT_DEPTH_CM * 0.5), (_LOCALIZATION_TEXT_WIDTH_CM * 0.5, 4.0, -_LOCALIZATION_TEXT_DEPTH_CM * 0.5), (_LOCALIZATION_TEXT_WIDTH_CM * 0.5, 34.0, -_LOCALIZATION_TEXT_DEPTH_CM * 0.5), (-_LOCALIZATION_TEXT_WIDTH_CM * 0.5, 34.0, -_LOCALIZATION_TEXT_DEPTH_CM * 0.5), (-_LOCALIZATION_TEXT_WIDTH_CM * 0.5, 4.0, -_LOCALIZATION_TEXT_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("localization_validation_guards", "swept_localization_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="localization_text.iteration_wear",
            parameters={"amount": 0.07, "localization_review_bias": 0.86},
            purpose=_purpose("localization_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.localization_table_root", "primary_volume"),
        _node("recipe.string_key_rows", "panel"),
        _node("recipe.translation_value_columns", "material_zone"),
        _node("recipe.pluralization_gender_rules", "guard"),
        _node("recipe.fallback_locale_chains", "rail"),
        _node("recipe.subtitle_timing_rows", "fastener"),
        _node("recipe.voiceover_text_bindings", "socket"),
        _node("recipe.glyph_font_coverage", "decal_zone"),
        _node("recipe.localization_validation_guards", "guard"),
        _node("recipe.localization_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="localization_text_table_bundle",
        family="localization_text_table_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="localization_text_table_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _accessibility_ux_affordance_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="accessibility_ux.affordance_root",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "accessibility_affordance_root",
                    {
                        "width_cm": _ACCESSIBILITY_UX_WIDTH_CM,
                        "height_cm": _ACCESSIBILITY_UX_HEIGHT_CM,
                        "depth_cm": _ACCESSIBILITY_UX_DEPTH_CM,
                        "corner_radii_cm": (1.4, 1.1, 1.5, 0.9, 1.6, 1.2, 1.3, 1.0),
                    },
                    _purpose("affordance_roots", "accessibility_affordance_root_source"),
                ),
                "width_cm": 0.9,
                "segments": 4,
            },
            purpose=_purpose("affordance_roots", "polybeveled_accessibility_affordance_root"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="accessibility_ux.input_maps",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "input_control_map_row",
                    {"profile_points": _rect_profile(11.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("input_or_control_maps", "input_control_map_source"),
                ),
                "points": _accessibility_cue_points(),
            },
            purpose=_purpose("input_or_control_maps", "copy_input_control_maps"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="accessibility_ux.readable_state_cues",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "readable_state_cue",
                    {"radius_cm": 1.45},
                    _purpose("readable_state_cues", "readable_state_cue_source"),
                ),
                "points": tuple((-48.0 + index * 12.0, 6.0, -36.0) for index in range(9)),
            },
            purpose=_purpose("readable_state_cues", "copy_readable_state_cues"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="accessibility_ux.contrast_regions",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "contrast_color_safe_region",
                    {"profile_points": _rect_profile(52.0, 8.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("contrast_or_color_safe_regions", "contrast_safe_region_source"),
                ),
                "distance_cm": 1.2,
                "axis": "z",
            },
            purpose=_purpose("contrast_or_color_safe_regions", "raised_contrast_color_safe_regions"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="accessibility_ux.caption_panels",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "subtitle_caption_panel",
                    {"profile_points": _rect_profile(18.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("subtitle_or_caption_panels", "subtitle_caption_panel_source"),
                ),
                "points": ((-44.0, 32.0, 32.0), (-14.0, 36.0, 40.0), (14.0, 36.0, 40.0), (44.0, 32.0, 32.0)),
            },
            purpose=_purpose("subtitle_or_caption_panels", "copy_subtitle_caption_panels"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="accessibility_ux.redundant_feedback",
            parameters={
                "radius_cm": 0.42,
                "path": ((-50.0, 18.0, 8.0), (-25.0, 30.0, 18.0), (0.0, 24.0, 28.0), (25.0, 30.0, 18.0), (50.0, 18.0, 8.0)),
            },
            purpose=_purpose("audio_visual_haptic_cues", "swept_audio_visual_haptic_cue_paths"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="accessibility_ux.focus_navigation",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "focus_navigation_ring",
                    {"major_radius_cm": 2.3, "minor_radius_cm": 0.16, "axis": "z"},
                    _purpose("focus_navigation_paths", "focus_navigation_source"),
                ),
                "points": _accessibility_focus_points(),
            },
            purpose=_purpose("focus_navigation_paths", "copy_focus_navigation_paths"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="accessibility_ux.option_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "accessibility_option_port",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("accessibility_option_ports", "accessibility_option_port_source"),
                ),
                "points": ((-44.0, 4.0, 38.0), (-14.0, 4.0, 44.0), (14.0, 4.0, 44.0), (44.0, 4.0, 38.0)),
            },
            purpose=_purpose("accessibility_option_ports", "copy_accessibility_option_ports"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="accessibility_ux.usability_guards",
            parameters={
                "radius_cm": 0.54,
                "path": ((-_ACCESSIBILITY_UX_WIDTH_CM * 0.5, 4.0, -_ACCESSIBILITY_UX_DEPTH_CM * 0.5), (_ACCESSIBILITY_UX_WIDTH_CM * 0.5, 4.0, -_ACCESSIBILITY_UX_DEPTH_CM * 0.5), (_ACCESSIBILITY_UX_WIDTH_CM * 0.5, 34.0, -_ACCESSIBILITY_UX_DEPTH_CM * 0.5), (-_ACCESSIBILITY_UX_WIDTH_CM * 0.5, 34.0, -_ACCESSIBILITY_UX_DEPTH_CM * 0.5), (-_ACCESSIBILITY_UX_WIDTH_CM * 0.5, 4.0, -_ACCESSIBILITY_UX_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("usability_validation_guards", "swept_usability_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="accessibility_ux.iteration_wear",
            parameters={"amount": 0.07, "accessibility_review_bias": 0.86},
            purpose=_purpose("accessibility_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.accessibility_affordance_root", "primary_volume"),
        _node("recipe.input_control_maps", "panel"),
        _node("recipe.readable_state_cues", "decal_zone"),
        _node("recipe.contrast_color_safe_regions", "material_zone"),
        _node("recipe.subtitle_caption_panels", "panel"),
        _node("recipe.audio_visual_haptic_cues", "rail"),
        _node("recipe.focus_navigation_paths", "rail"),
        _node("recipe.accessibility_option_ports", "socket"),
        _node("recipe.usability_validation_guards", "guard"),
        _node("recipe.accessibility_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="accessibility_ux_affordance_bundle",
        family="accessibility_ux_affordance_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="accessibility_ux_affordance_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _economy_simulation_tuning_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="economy_tuning.simulation_root",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "economy_simulation_root",
                    {
                        "width_cm": _ECONOMY_TUNING_WIDTH_CM,
                        "height_cm": _ECONOMY_TUNING_HEIGHT_CM,
                        "depth_cm": _ECONOMY_TUNING_DEPTH_CM,
                        "corner_radii_cm": (1.3, 1.0, 1.4, 1.1, 1.6, 1.2, 0.9, 1.5),
                    },
                    _purpose("economy_simulation_roots", "economy_simulation_root_source"),
                ),
                "width_cm": 0.9,
                "segments": 4,
            },
            purpose=_purpose("economy_simulation_roots", "polybeveled_economy_simulation_root"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="economy_tuning.resource_flows",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "resource_flow_node",
                    {"profile_points": _rect_profile(10.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("resource_flow_nodes", "resource_flow_node_source"),
                ),
                "points": _economy_flow_points(),
            },
            purpose=_purpose("resource_flow_nodes", "copy_resource_flow_nodes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="economy_tuning.currency_pairs",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "currency_sink_source_pair",
                    {"major_radius_cm": 2.6, "minor_radius_cm": 0.18, "axis": "y"},
                    _purpose("currency_sink_source_pairs", "currency_pair_source"),
                ),
                "points": ((-44.0, 8.0, -38.0), (-14.0, 8.0, -44.0), (14.0, 8.0, -44.0), (44.0, 8.0, -38.0)),
            },
            purpose=_purpose("currency_sink_source_pairs", "copy_currency_sink_source_pairs"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="economy_tuning.loot_rewards",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "loot_reward_table",
                    {"profile_points": _rect_profile(52.0, 8.0), "height_cm": 0.24, "axis": "y"},
                    _purpose("loot_reward_tables", "loot_reward_table_source"),
                ),
                "distance_cm": 1.3,
                "axis": "z",
            },
            purpose=_purpose("loot_reward_tables", "raised_loot_reward_tables"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="economy_tuning.price_curves",
            parameters={
                "radius_cm": 0.44,
                "path": ((-50.0, 16.0, 8.0), (-25.0, 28.0, 18.0), (0.0, 22.0, 30.0), (25.0, 30.0, 22.0), (50.0, 18.0, 34.0)),
            },
            purpose=_purpose("price_or_market_curves", "swept_price_market_curves"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="economy_tuning.progression_balance",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "progression_balance_tick",
                    {"radius_cm": 1.45},
                    _purpose("progression_balance_tracks", "progression_balance_tick_source"),
                ),
                "points": tuple((-48.0 + index * 12.0, 6.0, 36.0) for index in range(9)),
            },
            purpose=_purpose("progression_balance_tracks", "copy_progression_balance_tracks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="economy_tuning.spawn_modulators",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "spawn_rate_modulator",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("spawn_rate_modulators", "spawn_rate_modulator_source"),
                ),
                "points": _economy_curve_points(),
            },
            purpose=_purpose("spawn_rate_modulators", "copy_spawn_rate_modulators"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="economy_tuning.telemetry_inputs",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "telemetry_tuning_input",
                    {"profile_points": _hinge_profile(), "axis": "z"},
                    _purpose("telemetry_tuning_inputs", "telemetry_input_source"),
                ),
                "points": ((-48.0, 4.0, 40.0), (-16.0, 4.0, 46.0), (16.0, 4.0, 46.0), (48.0, 4.0, 40.0)),
            },
            purpose=_purpose("telemetry_tuning_inputs", "copy_telemetry_tuning_inputs"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="economy_tuning.validation_guards",
            parameters={
                "radius_cm": 0.54,
                "path": ((-_ECONOMY_TUNING_WIDTH_CM * 0.5, 4.0, -_ECONOMY_TUNING_DEPTH_CM * 0.5), (_ECONOMY_TUNING_WIDTH_CM * 0.5, 4.0, -_ECONOMY_TUNING_DEPTH_CM * 0.5), (_ECONOMY_TUNING_WIDTH_CM * 0.5, 34.0, -_ECONOMY_TUNING_DEPTH_CM * 0.5), (-_ECONOMY_TUNING_WIDTH_CM * 0.5, 34.0, -_ECONOMY_TUNING_DEPTH_CM * 0.5), (-_ECONOMY_TUNING_WIDTH_CM * 0.5, 4.0, -_ECONOMY_TUNING_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("simulation_validation_guards", "swept_simulation_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="economy_tuning.iteration_wear",
            parameters={"amount": 0.07, "economy_tuning_review_bias": 0.85},
            purpose=_purpose("economy_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.economy_simulation_root", "primary_volume"),
        _node("recipe.resource_flow_nodes", "panel"),
        _node("recipe.currency_sink_source_pairs", "socket"),
        _node("recipe.loot_reward_tables", "material_zone"),
        _node("recipe.price_market_curves", "rail"),
        _node("recipe.progression_balance_tracks", "fastener"),
        _node("recipe.spawn_rate_modulators", "socket"),
        _node("recipe.telemetry_tuning_inputs", "socket"),
        _node("recipe.simulation_validation_guards", "guard"),
        _node("recipe.economy_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="economy_simulation_tuning_bundle",
        family="economy_simulation_tuning_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="economy_simulation_tuning_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _multiplayer_session_replication_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="multiplayer_replication.session_root",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "multiplayer_session_root",
                    {
                        "width_cm": _MULTIPLAYER_REPLICATION_WIDTH_CM,
                        "height_cm": _MULTIPLAYER_REPLICATION_HEIGHT_CM,
                        "depth_cm": _MULTIPLAYER_REPLICATION_DEPTH_CM,
                        "corner_radii_cm": (1.4, 1.0, 1.5, 1.2, 0.9, 1.6, 1.1, 1.3),
                    },
                    _purpose("session_replication_roots", "multiplayer_session_root_source"),
                ),
                "width_cm": 0.9,
                "segments": 4,
            },
            purpose=_purpose("session_replication_roots", "polybeveled_multiplayer_session_root"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="multiplayer_replication.authority_ownership",
            parameters={
                "radius_cm": 0.46,
                "path": ((-56.0, 14.0, -10.0), (-28.0, 32.0, 2.0), (0.0, 24.0, 14.0), (28.0, 32.0, 2.0), (56.0, 14.0, -10.0)),
            },
            purpose=_purpose("authority_ownership_maps", "swept_authority_ownership_maps"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="multiplayer_replication.replicated_state",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "replicated_state_node",
                    {"profile_points": _rect_profile(11.0, 5.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("replicated_state_nodes", "replicated_state_node_source"),
                ),
                "points": _replication_state_points(),
            },
            purpose=_purpose("replicated_state_nodes", "copy_replicated_state_nodes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="multiplayer_replication.rpc_channels",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "rpc_event_channel",
                    {"profile_points": _rivet_profile(), "axis": "z"},
                    _purpose("rpc_event_channels", "rpc_event_channel_source"),
                ),
                "points": _replication_channel_points(),
            },
            purpose=_purpose("rpc_event_channels", "copy_rpc_event_channels"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="multiplayer_replication.sync_ticks",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "sync_tick_marker",
                    {"radius_cm": 1.45},
                    _purpose("sync_tick_timelines", "sync_tick_marker_source"),
                ),
                "points": tuple((-54.0 + index * 13.5, 6.0, -40.0) for index in range(9)),
            },
            purpose=_purpose("sync_tick_timelines", "copy_sync_tick_timelines"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="multiplayer_replication.prediction_reconciliation",
            parameters={
                "radius_cm": 0.42,
                "path": ((-54.0, 18.0, 12.0), (-27.0, 30.0, 24.0), (0.0, 22.0, 34.0), (27.0, 30.0, 24.0), (54.0, 18.0, 12.0)),
            },
            purpose=_purpose("prediction_reconciliation_paths", "swept_prediction_reconciliation_paths"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="multiplayer_replication.rollback_buffers",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "rollback_state_buffer",
                    {"profile_points": _rect_profile(52.0, 8.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("rollback_state_buffers", "rollback_buffer_source"),
                ),
                "distance_cm": 1.2,
                "axis": "z",
            },
            purpose=_purpose("rollback_state_buffers", "raised_rollback_state_buffers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="multiplayer_replication.matchmaking_rules",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "matchmaking_session_rule",
                    {"major_radius_cm": 2.5, "minor_radius_cm": 0.18, "axis": "y"},
                    _purpose("matchmaking_session_rules", "matchmaking_rule_source"),
                ),
                "points": ((-46.0, 32.0, 36.0), (-15.0, 36.0, 44.0), (15.0, 36.0, 44.0), (46.0, 32.0, 36.0)),
            },
            purpose=_purpose("matchmaking_session_rules", "copy_matchmaking_session_rules"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="multiplayer_replication.validation_guards",
            parameters={
                "radius_cm": 0.54,
                "path": ((-_MULTIPLAYER_REPLICATION_WIDTH_CM * 0.5, 4.0, -_MULTIPLAYER_REPLICATION_DEPTH_CM * 0.5), (_MULTIPLAYER_REPLICATION_WIDTH_CM * 0.5, 4.0, -_MULTIPLAYER_REPLICATION_DEPTH_CM * 0.5), (_MULTIPLAYER_REPLICATION_WIDTH_CM * 0.5, 38.0, -_MULTIPLAYER_REPLICATION_DEPTH_CM * 0.5), (-_MULTIPLAYER_REPLICATION_WIDTH_CM * 0.5, 38.0, -_MULTIPLAYER_REPLICATION_DEPTH_CM * 0.5), (-_MULTIPLAYER_REPLICATION_WIDTH_CM * 0.5, 4.0, -_MULTIPLAYER_REPLICATION_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("replication_validation_guards", "swept_replication_validation_guard_frame"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="multiplayer_replication.iteration_wear",
            parameters={"amount": 0.07, "multiplayer_review_bias": 0.86},
            purpose=_purpose("multiplayer_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.multiplayer_session_root", "primary_volume"),
        _node("recipe.authority_ownership_maps", "rail"),
        _node("recipe.replicated_state_nodes", "panel"),
        _node("recipe.rpc_event_channels", "socket"),
        _node("recipe.sync_tick_timelines", "fastener"),
        _node("recipe.prediction_reconciliation_paths", "rail"),
        _node("recipe.rollback_state_buffers", "panel"),
        _node("recipe.matchmaking_session_rules", "material_zone"),
        _node("recipe.replication_validation_guards", "guard"),
        _node("recipe.multiplayer_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="multiplayer_session_replication_bundle",
        family="multiplayer_session_replication_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="multiplayer_session_replication_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _cross_domain_composition_pack_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="cross_domain.domain_pillars",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "cross_domain_pillar",
                    {
                        "width_cm": 15.0,
                        "height_cm": _CROSS_DOMAIN_HEIGHT_CM,
                        "depth_cm": 12.0,
                        "corner_radii_cm": (1.5, 1.2, 1.6, 1.3, 1.0, 1.7, 1.1, 1.4),
                    },
                    _purpose("domain_pillars", "pillar_source"),
                ),
                "points": _cross_domain_pillar_points(),
            },
            purpose=_purpose("domain_pillars", "copy_domain_pillars"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cross_domain.handoff_links",
            parameters={
                "radius_cm": 0.65,
                "path": ((-48.0, 36.0, -24.0), (-16.0, 38.0, -24.0), (16.0, 38.0, -24.0), (48.0, 36.0, -24.0), (32.0, 36.0, 20.0), (0.0, 38.0, 20.0), (-32.0, 36.0, 20.0)),
            },
            purpose=_purpose("bridge_or_handoff_links", "swept_handoff_graph"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="cross_domain.shared_rules",
            parameters={
                "profile_polygon": _rect_profile(62.0, 12.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 24.0, 0.0),
            },
            purpose=_purpose("shared_rule_layer", "raised_rule_band"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cross_domain.interface_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "cross_domain_interface_port",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("interface_or_port_map", "interface_port_source"),
                ),
                "points": ((-56.0, 25.0, 32.0), (-28.0, 25.0, 36.0), (0.0, 25.0, 38.0), (28.0, 25.0, 36.0), (56.0, 25.0, 32.0)),
            },
            purpose=_purpose("interface_or_port_map", "copy_interface_ports"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cross_domain.boundaries",
            parameters={
                "radius_cm": 0.9,
                "path": ((-_CROSS_DOMAIN_WIDTH_CM * 0.5, 23.0, -_CROSS_DOMAIN_DEPTH_CM * 0.5), (_CROSS_DOMAIN_WIDTH_CM * 0.5, 23.0, -_CROSS_DOMAIN_DEPTH_CM * 0.5), (_CROSS_DOMAIN_WIDTH_CM * 0.5, 23.0, _CROSS_DOMAIN_DEPTH_CM * 0.5), (-_CROSS_DOMAIN_WIDTH_CM * 0.5, 23.0, _CROSS_DOMAIN_DEPTH_CM * 0.5), (-_CROSS_DOMAIN_WIDTH_CM * 0.5, 23.0, -_CROSS_DOMAIN_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("domain_boundary_markers", "swept_boundary_frame"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="cross_domain.refusal_cues",
            parameters={
                "profile_polygon": _rect_profile(22.0, 7.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (_CROSS_DOMAIN_WIDTH_CM * 0.33, 24.0, -_CROSS_DOMAIN_DEPTH_CM * 0.38),
            },
            purpose=_purpose("conflict_or_refusal_cues", "raised_refusal_badge"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cross_domain.preview_outputs",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cross_domain_preview_tile",
                    {"profile_points": _rect_profile(12.0, 8.0), "height_cm": 0.35, "axis": "y"},
                    _purpose("preview_or_sample_outputs", "preview_source"),
                ),
                "points": ((-40.0, 25.0, -42.0), (-14.0, 25.0, -42.0), (14.0, 25.0, -42.0), (40.0, 25.0, -42.0)),
            },
            purpose=_purpose("preview_or_sample_outputs", "copy_preview_tiles"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cross_domain.order_guides",
            parameters={
                "radius_cm": 0.45,
                "path": ((-52.0, 25.0, 8.0), (-28.0, 27.0, -2.0), (0.0, 27.0, 8.0), (28.0, 27.0, -2.0), (52.0, 25.0, 8.0)),
            },
            purpose=_purpose("dependency_or_order_guides", "swept_order_guide"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="cross_domain.integration_label",
            parameters={
                "profile_polygon": _rect_profile(24.0, 6.0),
                "extrude_height_cm": 0.2,
                "axis": "y",
                "center": (-_CROSS_DOMAIN_WIDTH_CM * 0.36, 24.2, _CROSS_DOMAIN_DEPTH_CM * 0.36),
            },
            purpose=_purpose("integration_labels", "raised_integration_label"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="cross_domain.handoff_wear",
            parameters={"amount": 0.14, "handoff_bias": 0.65},
            purpose=_purpose("handoff_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.cross_domain_pillars", "primary_volume"),
        _node("recipe.cross_domain_handoffs", "rail"),
        _node("recipe.cross_domain_rules", "material_zone"),
        _node("recipe.cross_domain_interfaces", "socket"),
        _node("recipe.cross_domain_boundaries", "guard"),
        _node("recipe.cross_domain_refusals", "decal_zone"),
        _node("recipe.cross_domain_previews", "panel"),
        _node("recipe.cross_domain_order", "rail"),
        _node("recipe.cross_domain_labels", "decal_zone"),
        _node("recipe.cross_domain_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="cross_domain_composition_pack",
        family="cross_domain_composition_pack",
        ops=ops,
    )
    return RecipeResult(
        family="cross_domain_composition_pack",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _style_stack_visual_band_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="style_stack.axes",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "style_axis_lane",
                    {"profile_points": _rect_profile(10.0, 42.0), "height_cm": 0.35, "axis": "y"},
                    _purpose("style_axis_stack", "axis_source"),
                ),
                "points": _style_axis_points(),
            },
            purpose=_purpose("style_axis_stack", "copy_style_axes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="style_stack.palette",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "style_palette_swatch",
                    {
                        "width_cm": 8.0,
                        "height_cm": 2.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (0.8, 0.6, 0.7, 0.5, 0.4, 0.8, 0.5, 0.7),
                    },
                    _purpose("palette_or_material_model", "swatch_source"),
                ),
                "points": tuple((-36.0 + index * 12.0, 22.0, 12.0) for index in range(7)),
            },
            purpose=_purpose("palette_or_material_model", "copy_palette_swatches"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="style_stack.surface_mode",
            parameters={
                "profile_polygon": _rect_profile(36.0, 10.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-22.0, 22.0, -2.0),
            },
            purpose=_purpose("surface_authoring_mode", "raised_surface_mode"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="style_stack.outline_lighting",
            parameters={
                "radius_cm": 0.55,
                "path": ((-_STYLE_STACK_WIDTH_CM * 0.45, 24.0, _STYLE_STACK_DEPTH_CM * 0.32), (-10.0, 27.0, _STYLE_STACK_DEPTH_CM * 0.42), (12.0, 27.0, _STYLE_STACK_DEPTH_CM * 0.42), (_STYLE_STACK_WIDTH_CM * 0.45, 24.0, _STYLE_STACK_DEPTH_CM * 0.32)),
            },
            purpose=_purpose("outline_or_lighting_strategy", "swept_outline_lighting_band"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="style_stack.detail_layers",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "style_detail_tick",
                    {"radius_cm": 1.25},
                    _purpose("detail_layer_composition", "detail_tick_source"),
                ),
                "points": tuple((-30.0 + index * 10.0, 23.5, -_STYLE_STACK_DEPTH_CM * 0.46) for index in range(7)),
            },
            purpose=_purpose("detail_layer_composition", "copy_detail_ticks"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="style_stack.motion_style",
            parameters={
                "radius_cm": 0.45,
                "path": ((-42.0, 20.0, 24.0), (-18.0, 28.0, 28.0), (12.0, 22.0, 24.0), (42.0, 30.0, 28.0)),
            },
            purpose=_purpose("animation_rate_or_motion_style", "swept_motion_style"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="style_stack.construction_grammar",
            parameters={
                "profile_polygon": _rect_profile(26.0, 8.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (28.0, 22.0, -2.0),
            },
            purpose=_purpose("construction_grammar_marker", "raised_construction_grammar"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="style_stack.compatibility_bridges",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "style_bridge_ring",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.28, "axis": "y"},
                    _purpose("compatibility_or_bridge_rules", "bridge_source"),
                ),
                "points": ((-34.0, 24.0, 30.0), (-12.0, 24.0, 32.0), (12.0, 24.0, 32.0), (34.0, 24.0, 30.0)),
            },
            purpose=_purpose("compatibility_or_bridge_rules", "copy_style_bridges"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="style_stack.refusal_marker",
            parameters={
                "profile_polygon": _rect_profile(20.0, 6.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (_STYLE_STACK_WIDTH_CM * 0.34, 22.0, -_STYLE_STACK_DEPTH_CM * 0.38),
            },
            purpose=_purpose("refusal_or_negative_constraints", "raised_refusal_marker"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="style_stack.iteration_wear",
            parameters={"amount": 0.12, "sample_bias": 0.68},
            purpose=_purpose("style_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.style_axes", "primary_volume"),
        _node("recipe.style_palette", "material_zone"),
        _node("recipe.style_surface_mode", "panel"),
        _node("recipe.style_outline_lighting", "rail"),
        _node("recipe.style_detail_layers", "fastener"),
        _node("recipe.style_motion", "rail"),
        _node("recipe.style_construction_grammar", "socket"),
        _node("recipe.style_compatibility", "socket"),
        _node("recipe.style_refusal", "guard"),
        _node("recipe.style_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="style_stack_visual_band",
        family="style_stack_visual_band",
        ops=ops,
    )
    return RecipeResult(
        family="style_stack_visual_band",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _typed_data_kernel_bundle_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polywire",
            target="typed_kernel.bundle_bus",
            parameters={
                "radius_cm": 1.0,
                "path": ((-_TYPED_KERNEL_WIDTH_CM * 0.48, 26.0, 0.0), (-24.0, 31.0, 0.0), (0.0, 28.0, 0.0), (24.0, 31.0, 0.0), (_TYPED_KERNEL_WIDTH_CM * 0.48, 26.0, 0.0)),
            },
            purpose=_purpose("typed_bundle_bus", "swept_typed_bus"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="typed_kernel.mesh_points_volume_slots",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "typed_primary_slot",
                    {
                        "width_cm": 15.0,
                        "height_cm": _TYPED_KERNEL_HEIGHT_CM * 0.55,
                        "depth_cm": 14.0,
                        "corner_radii_cm": (1.2, 1.0, 1.4, 1.0, 0.8, 1.3, 0.9, 1.2),
                    },
                    _purpose("mesh_points_volume_slots", "primary_slot_source"),
                ),
                "points": _typed_primary_slot_points(),
            },
            purpose=_purpose("mesh_points_volume_slots", "copy_mesh_points_volume_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="typed_kernel.heightfield_spline_sdf_slots",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "typed_secondary_slot",
                    {"profile_points": _rect_profile(14.0, 12.0), "height_cm": 1.1, "axis": "y"},
                    _purpose("heightfield_spline_sdf_slots", "secondary_slot_source"),
                ),
                "points": _typed_secondary_slot_points(),
            },
            purpose=_purpose("heightfield_spline_sdf_slots", "copy_heightfield_spline_sdf_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="typed_kernel.image_rig_slots",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "typed_image_rig_port",
                    {"major_radius_cm": 4.0, "minor_radius_cm": 0.35, "axis": "y"},
                    _purpose("image_and_rig_slots", "image_rig_slot_source"),
                ),
                "points": ((-52.0, 30.0, 32.0), (-18.0, 30.0, 34.0), (18.0, 30.0, 34.0), (52.0, 30.0, 32.0)),
            },
            purpose=_purpose("image_and_rig_slots", "copy_image_rig_ports"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="typed_kernel.contract_badges",
            parameters={
                "profile_polygon": _rect_profile(32.0, 7.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-_TYPED_KERNEL_WIDTH_CM * 0.32, 31.0, -_TYPED_KERNEL_DEPTH_CM * 0.42),
            },
            purpose=_purpose("slot_contract_badges", "raised_contract_badges"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="typed_kernel.transform_links",
            parameters={
                "radius_cm": 0.55,
                "path": ((-48.0, 32.0, -18.0), (-24.0, 35.0, 3.0), (0.0, 32.0, 18.0), (24.0, 35.0, 3.0), (48.0, 32.0, -18.0)),
            },
            purpose=_purpose("transform_or_conversion_links", "swept_transform_links"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="typed_kernel.dependency_order",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "typed_order_tick",
                    {"radius_cm": 1.35},
                    _purpose("dependency_and_order_markers", "order_tick_source"),
                ),
                "points": tuple((-45.0 + index * 15.0, 31.5, -_TYPED_KERNEL_DEPTH_CM * 0.5) for index in range(7)),
            },
            purpose=_purpose("dependency_and_order_markers", "copy_order_ticks"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="typed_kernel.cache_state",
            parameters={
                "profile_polygon": _rect_profile(26.0, 9.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (_TYPED_KERNEL_WIDTH_CM * 0.32, 31.0, -_TYPED_KERNEL_DEPTH_CM * 0.42),
            },
            purpose=_purpose("cache_or_delta_state", "raised_cache_state_panel"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="typed_kernel.validation_guards",
            parameters={
                "radius_cm": 0.75,
                "path": ((-_TYPED_KERNEL_WIDTH_CM * 0.5, 27.0, -_TYPED_KERNEL_DEPTH_CM * 0.5), (_TYPED_KERNEL_WIDTH_CM * 0.5, 27.0, -_TYPED_KERNEL_DEPTH_CM * 0.5), (_TYPED_KERNEL_WIDTH_CM * 0.5, 27.0, _TYPED_KERNEL_DEPTH_CM * 0.5), (-_TYPED_KERNEL_WIDTH_CM * 0.5, 27.0, _TYPED_KERNEL_DEPTH_CM * 0.5), (-_TYPED_KERNEL_WIDTH_CM * 0.5, 27.0, -_TYPED_KERNEL_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("validation_or_guard_edges", "swept_type_guard_edges"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="typed_kernel.data_flow_wear",
            parameters={"amount": 0.13, "data_flow_bias": 0.72},
            purpose=_purpose("data_flow_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.typed_kernel_bus", "primary_volume"),
        _node("recipe.typed_mesh_points_volume", "socket"),
        _node("recipe.typed_heightfield_spline_sdf", "socket"),
        _node("recipe.typed_image_rig", "socket"),
        _node("recipe.typed_contracts", "decal_zone"),
        _node("recipe.typed_transforms", "rail"),
        _node("recipe.typed_order", "fastener"),
        _node("recipe.typed_cache", "panel"),
        _node("recipe.typed_guards", "guard"),
        _node("recipe.typed_flow_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="typed_data_kernel_bundle",
        family="typed_data_kernel_bundle",
        ops=ops,
    )
    return RecipeResult(
        family="typed_data_kernel_bundle",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _attribute_surface_graph_program_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polywire",
            target="attribute_surface.attribute_streams",
            parameters={
                "radius_cm": 0.6,
                "path": ((-_ATTR_SURFACE_WIDTH_CM * 0.48, 22.0, -30.0), (-28.0, 27.0, -12.0), (0.0, 23.0, 2.0), (28.0, 27.0, -12.0), (_ATTR_SURFACE_WIDTH_CM * 0.48, 22.0, -30.0)),
            },
            purpose=_purpose("attribute_streams", "swept_attribute_streams"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="attribute_surface.surface_nodes",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "surface_graph_node",
                    {
                        "width_cm": 12.0,
                        "height_cm": _ATTR_SURFACE_HEIGHT_CM * 0.55,
                        "depth_cm": 10.0,
                        "corner_radii_cm": (1.0, 1.3, 0.9, 1.4, 0.7, 1.2, 0.8, 1.1),
                    },
                    _purpose("surface_node_graph", "surface_node_source"),
                ),
                "points": _attribute_surface_node_points(),
            },
            purpose=_purpose("surface_node_graph", "copy_surface_nodes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="attribute_surface.authoring_modes",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "surface_mode_tile",
                    {"profile_points": _rect_profile(18.0, 9.0), "height_cm": 0.35, "axis": "y"},
                    _purpose("designer_photo_layer_modes", "mode_tile_source"),
                ),
                "points": ((-34.0, 25.0, 28.0), (0.0, 25.0, 32.0), (34.0, 25.0, 28.0)),
            },
            purpose=_purpose("designer_photo_layer_modes", "copy_designer_photo_layer_modes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="attribute_surface.mask_layers",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "smart_mask_layer",
                    {"profile_points": _rect_profile(15.0, 4.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("mask_program_layers", "mask_layer_source"),
                ),
                "points": tuple((-45.0 + index * 15.0, 26.0, -_ATTR_SURFACE_DEPTH_CM * 0.45) for index in range(7)),
            },
            purpose=_purpose("mask_program_layers", "copy_mask_layers"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="attribute_surface.materialx_ports",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "materialx_output_port",
                    {"major_radius_cm": 3.2, "minor_radius_cm": 0.3, "axis": "y"},
                    _purpose("materialx_output_ports", "materialx_port_source"),
                ),
                "points": ((-48.0, 25.0, 38.0), (-16.0, 25.0, 40.0), (16.0, 25.0, 40.0), (48.0, 25.0, 38.0)),
            },
            purpose=_purpose("materialx_output_ports", "copy_materialx_ports"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="attribute_surface.attribute_math",
            parameters={
                "profile_polygon": _rect_profile(34.0, 8.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-_ATTR_SURFACE_WIDTH_CM * 0.28, 25.0, 4.0),
            },
            purpose=_purpose("attribute_math_or_rules", "raised_attribute_math_rules"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="attribute_surface.frequency_controls",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "frequency_control_tick",
                    {"radius_cm": 1.15},
                    _purpose("texture_frequency_controls", "frequency_tick_source"),
                ),
                "points": tuple((-36.0 + index * 12.0, 26.5, 16.0) for index in range(7)),
            },
            purpose=_purpose("texture_frequency_controls", "copy_frequency_ticks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="attribute_surface.preview_targets",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "surface_preview_tile",
                    {
                        "width_cm": 12.0,
                        "height_cm": 2.2,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (0.8, 0.6, 0.9, 0.7, 0.5, 0.8, 0.6, 0.9),
                    },
                    _purpose("preview_or_bake_targets", "preview_tile_source"),
                ),
                "points": ((-38.0, 25.0, -2.0), (-12.0, 25.0, 2.0), (12.0, 25.0, 2.0), (38.0, 25.0, -2.0)),
            },
            purpose=_purpose("preview_or_bake_targets", "copy_preview_bake_targets"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="attribute_surface.invalid_guards",
            parameters={
                "profile_polygon": _rect_profile(28.0, 7.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (_ATTR_SURFACE_WIDTH_CM * 0.34, 25.0, -_ATTR_SURFACE_DEPTH_CM * 0.36),
            },
            purpose=_purpose("unbound_or_invalid_guards", "raised_unbound_guard"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="attribute_surface.iteration_wear",
            parameters={"amount": 0.12, "surface_authoring_bias": 0.74},
            purpose=_purpose("surface_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.attr_streams", "rail"),
        _node("recipe.surface_nodes", "panel"),
        _node("recipe.surface_modes", "socket"),
        _node("recipe.mask_layers", "material_zone"),
        _node("recipe.materialx_ports", "socket"),
        _node("recipe.attribute_math", "panel"),
        _node("recipe.frequency_controls", "fastener"),
        _node("recipe.preview_targets", "panel"),
        _node("recipe.invalid_guards", "guard"),
        _node("recipe.surface_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="attribute_surface_graph_program",
        family="attribute_surface_graph_program",
        ops=ops,
    )
    return RecipeResult(
        family="attribute_surface_graph_program",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _vegetation_library_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="solid.branching_tree",
            target="vegetation_library.executable_branching_tree",
            parameters={
                "height_cm": _VEG_LIBRARY_HEIGHT_CM * 1.28,
                "trunk_radius_cm": 3.4,
                "branch_count": 12,
                "branch_levels": 3,
                "canopy_cluster_count": 16,
                "canopy_radius_cm": 5.4,
                "root_count": 6,
                "center": (0.0, _VEG_LIBRARY_HEIGHT_CM * 0.34, 0.0),
                "vertical_axis": "y",
                "seed": 7,
            },
            purpose=_purpose("executable_branching_tree", "branching_tree_solid"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="vegetation_library.species_catalog",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "vegetation_species_card",
                    {
                        "width_cm": 13.0,
                        "height_cm": 18.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (1.2, 0.9, 1.4, 1.0, 0.7, 1.3, 0.8, 1.1),
                    },
                    _purpose("species_catalog", "species_card_source"),
                ),
                "points": _vegetation_species_points(),
            },
            purpose=_purpose("species_catalog", "copy_species_cards"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="vegetation_library.branch_grammar",
            parameters={
                "radius_cm": 0.75,
                "path": ((-48.0, 26.0, 0.0), (-28.0, 42.0, -8.0), (-8.0, 50.0, 2.0), (12.0, 44.0, 14.0), (34.0, 52.0, 6.0), (50.0, 40.0, -8.0)),
            },
            purpose=_purpose("trunk_branch_grammar", "swept_branching_grammar"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="vegetation_library.leaf_clusters",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "vegetation_leaf_cluster",
                    {"radius_cm": 4.2},
                    _purpose("leaf_cluster_rules", "leaf_cluster_source"),
                ),
                "points": ((-34.0, 45.0, -18.0), (-14.0, 54.0, -2.0), (10.0, 50.0, 18.0), (34.0, 46.0, 4.0), (48.0, 38.0, -18.0)),
            },
            purpose=_purpose("leaf_cluster_rules", "copy_leaf_clusters"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="vegetation_library.root_anchors",
            parameters={
                "radius_cm": 0.55,
                "path": ((-36.0, 20.0, 24.0), (-18.0, 22.0, 10.0), (0.0, 20.0, 26.0), (18.0, 22.0, 10.0), (36.0, 20.0, 24.0)),
            },
            purpose=_purpose("root_anchor_system", "swept_root_anchors"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="vegetation_library.lod_billboards",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "vegetation_lod_billboard",
                    {"profile_points": _rect_profile(12.0, 18.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("lod_billboard_set", "lod_billboard_source"),
                ),
                "points": ((-46.0, 28.0, _VEG_LIBRARY_DEPTH_CM * 0.42), (-18.0, 28.0, _VEG_LIBRARY_DEPTH_CM * 0.46), (10.0, 28.0, _VEG_LIBRARY_DEPTH_CM * 0.46), (38.0, 28.0, _VEG_LIBRARY_DEPTH_CM * 0.42)),
            },
            purpose=_purpose("lod_billboard_set", "copy_lod_billboards"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="vegetation_library.wind_motion",
            parameters={
                "radius_cm": 0.45,
                "path": ((-_VEG_LIBRARY_WIDTH_CM * 0.44, 50.0, -_VEG_LIBRARY_DEPTH_CM * 0.38), (-18.0, 57.0, -_VEG_LIBRARY_DEPTH_CM * 0.28), (18.0, 49.0, -_VEG_LIBRARY_DEPTH_CM * 0.34), (_VEG_LIBRARY_WIDTH_CM * 0.44, 56.0, -_VEG_LIBRARY_DEPTH_CM * 0.22)),
            },
            purpose=_purpose("wind_motion_markers", "swept_wind_motion"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="vegetation_library.season_slots",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "vegetation_season_slot",
                    {"profile_points": _rect_profile(10.0, 8.0), "height_cm": 0.3, "axis": "y"},
                    _purpose("season_variant_slots", "season_slot_source"),
                ),
                "points": tuple((-45.0 + index * 15.0, 29.0, -_VEG_LIBRARY_DEPTH_CM * 0.5) for index in range(7)),
            },
            purpose=_purpose("season_variant_slots", "copy_season_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="vegetation_library.growth_ports",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "vegetation_growth_port",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.25, "axis": "y"},
                    _purpose("growth_parameter_ports", "growth_port_source"),
                ),
                "points": ((-50.0, 30.0, 0.0), (-25.0, 30.0, 5.0), (0.0, 30.0, 0.0), (25.0, 30.0, 5.0), (50.0, 30.0, 0.0)),
            },
            purpose=_purpose("growth_parameter_ports", "copy_growth_ports"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="vegetation_library.biome_distribution",
            parameters={
                "profile_polygon": _rect_profile(78.0, 11.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 27.0, -_VEG_LIBRARY_DEPTH_CM * 0.38),
            },
            purpose=_purpose("biome_distribution_masks", "raised_biome_distribution_mask"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="vegetation_library.usage_wear",
            parameters={"amount": 0.12, "growth_authoring_bias": 0.7},
            purpose=_purpose("vegetation_usage_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.vegetation_executable_tree", "primary_volume"),
        _node("recipe.vegetation_species", "primary_volume"),
        _node("recipe.vegetation_branching", "rail"),
        _node("recipe.vegetation_leaf_clusters", "material_zone"),
        _node("recipe.vegetation_roots", "socket"),
        _node("recipe.vegetation_lods", "panel"),
        _node("recipe.vegetation_wind", "rail"),
        _node("recipe.vegetation_seasons", "socket"),
        _node("recipe.vegetation_growth_ports", "socket"),
        _node("recipe.vegetation_biome_masks", "material_zone"),
        _node("recipe.vegetation_usage_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="vegetation_library_system",
        family="vegetation_library_system",
        ops=ops,
    )
    return RecipeResult(
        family="vegetation_library_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _terrain_heightfield_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="solid.terrain_patch",
            target="terrain_heightfield.executable_terrain_patch",
            parameters={
                "width_cm": _TERRAIN_SYSTEM_WIDTH_CM,
                "depth_cm": _TERRAIN_SYSTEM_DEPTH_CM,
                "height_cm": _TERRAIN_SYSTEM_HEIGHT_CM * 1.4,
                "resolution": 32,
                "biome": "alpine",
                "terrace_count": 4,
                "border_taper_cm": 8.0,
                "center": (0.0, 0.0, 0.0),
                "vertical_axis": "y",
                "seed": 11,
            },
            purpose=_purpose("executable_heightfield_terrain", "terrain_patch_solid"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="terrain_heightfield.domain",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "terrain_heightfield_domain",
                    {
                        "width_cm": _TERRAIN_SYSTEM_WIDTH_CM,
                        "height_cm": _TERRAIN_SYSTEM_HEIGHT_CM,
                        "depth_cm": _TERRAIN_SYSTEM_DEPTH_CM,
                        "center": (0.0, _TERRAIN_SYSTEM_HEIGHT_CM * 0.5, 0.0),
                    },
                    _purpose("heightfield_domain", "domain_box_source"),
                ),
                "width_cm": 2.4,
                "segments": 5,
            },
            purpose=_purpose("heightfield_domain", "beveled_heightfield_domain"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_heightfield.elevation_layers",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "terrain_elevation_layer",
                    {"profile_points": _rect_profile(96.0, 5.0), "height_cm": 0.35, "axis": "y"},
                    _purpose("elevation_layers", "elevation_layer_source"),
                ),
                "points": tuple((0.0, 20.0 + index * 2.0, -42.0 + index * 14.0) for index in range(7)),
            },
            purpose=_purpose("elevation_layers", "copy_elevation_layers"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="terrain_heightfield.erosion_flows",
            parameters={
                "radius_cm": 0.55,
                "path": ((-_TERRAIN_SYSTEM_WIDTH_CM * 0.44, 26.0, -_TERRAIN_SYSTEM_DEPTH_CM * 0.38), (-34.0, 21.0, -18.0), (-8.0, 24.0, 0.0), (18.0, 19.0, 18.0), (_TERRAIN_SYSTEM_WIDTH_CM * 0.43, 22.0, _TERRAIN_SYSTEM_DEPTH_CM * 0.36)),
            },
            purpose=_purpose("erosion_flow_network", "swept_erosion_flow_network"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_heightfield.slope_deposition",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "terrain_slope_mask",
                    {"profile_points": _rect_profile(15.0, 8.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("slope_deposition_masks", "slope_mask_source"),
                ),
                "points": ((-48.0, 24.0, -4.0), (-24.0, 24.0, 10.0), (0.0, 24.0, -6.0), (24.0, 24.0, 12.0), (48.0, 24.0, -2.0)),
            },
            purpose=_purpose("slope_deposition_masks", "copy_slope_deposition_masks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_heightfield.biome_zones",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "terrain_biome_zone",
                    {
                        "width_cm": 18.0,
                        "height_cm": 1.8,
                        "depth_cm": 12.0,
                        "corner_radii_cm": (1.0, 0.8, 1.1, 0.9, 0.6, 1.0, 0.7, 1.1),
                    },
                    _purpose("biome_material_zones", "biome_zone_source"),
                ),
                "points": ((-52.0, 22.0, 34.0), (-26.0, 22.0, 40.0), (0.0, 22.0, 36.0), (26.0, 22.0, 40.0), (52.0, 22.0, 34.0)),
            },
            purpose=_purpose("biome_material_zones", "copy_biome_material_zones"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="terrain_heightfield.drainage_channels",
            parameters={
                "radius_cm": 0.7,
                "path": ((-58.0, 23.0, 44.0), (-34.0, 20.0, 22.0), (-8.0, 18.0, 8.0), (18.0, 20.0, -12.0), (52.0, 21.0, -40.0)),
            },
            purpose=_purpose("water_drainage_channels", "swept_drainage_channels"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_heightfield.mesh_exports",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "terrain_export_port",
                    {"major_radius_cm": 3.5, "minor_radius_cm": 0.28, "axis": "y"},
                    _purpose("terrain_to_mesh_exports", "export_port_source"),
                ),
                "points": ((-60.0, 23.0, -48.0), (-20.0, 23.0, -50.0), (20.0, 23.0, -50.0), (60.0, 23.0, -48.0)),
            },
            purpose=_purpose("terrain_to_mesh_exports", "copy_mesh_export_ports"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="terrain_heightfield.probe_grid",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "terrain_probe_pin",
                    {"radius_cm": 0.9},
                    _purpose("sample_probe_grid", "probe_pin_source"),
                ),
                "points": _terrain_probe_points(),
            },
            purpose=_purpose("sample_probe_grid", "copy_probe_grid"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="terrain_heightfield.tile_edges",
            parameters={
                "radius_cm": 0.85,
                "path": ((-_TERRAIN_SYSTEM_WIDTH_CM * 0.5, 22.0, -_TERRAIN_SYSTEM_DEPTH_CM * 0.5), (_TERRAIN_SYSTEM_WIDTH_CM * 0.5, 22.0, -_TERRAIN_SYSTEM_DEPTH_CM * 0.5), (_TERRAIN_SYSTEM_WIDTH_CM * 0.5, 22.0, _TERRAIN_SYSTEM_DEPTH_CM * 0.5), (-_TERRAIN_SYSTEM_WIDTH_CM * 0.5, 22.0, _TERRAIN_SYSTEM_DEPTH_CM * 0.5), (-_TERRAIN_SYSTEM_WIDTH_CM * 0.5, 22.0, -_TERRAIN_SYSTEM_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("boundary_tileability_edges", "swept_tileability_edges"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="terrain_heightfield.iteration_wear",
            parameters={"amount": 0.14, "erosion_iteration_bias": 0.75},
            purpose=_purpose("terrain_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.terrain_executable_patch", "primary_volume"),
        _node("recipe.terrain_domain", "primary_volume"),
        _node("recipe.terrain_elevation", "panel"),
        _node("recipe.terrain_erosion_flow", "rail"),
        _node("recipe.terrain_slope_masks", "material_zone"),
        _node("recipe.terrain_biome_zones", "material_zone"),
        _node("recipe.terrain_drainage", "rail"),
        _node("recipe.terrain_exports", "socket"),
        _node("recipe.terrain_probes", "fastener"),
        _node("recipe.terrain_tile_edges", "guard"),
        _node("recipe.terrain_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="terrain_heightfield_system",
        family="terrain_heightfield_system",
        ops=ops,
    )
    return RecipeResult(
        family="terrain_heightfield_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _wfc_tile_solver_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="solid.wfc_modular_assembly",
            target="wfc.executable_modular_layout",
            parameters={
                "width_cells": 7,
                "depth_cells": 4,
                "cell_size_cm": 12.0,
                "wall_height_cm": 10.0,
                "wall_thickness_cm": 1.2,
                "pillar_radius_cm": 1.5,
                "palette": "dungeon",
                "include_boundary_walls": True,
                "center": (0.0, _WFC_SOLVER_HEIGHT_CM * 0.5, 0.0),
                "vertical_axis": "y",
                "seed": 42,
            },
            purpose=_purpose("executable_wfc_modular_layout", "wfc_modular_assembly_solid"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="wfc.tileset_catalog",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "wfc_tile_catalog_card",
                    {
                        "width_cm": 14.0,
                        "height_cm": 3.0,
                        "depth_cm": 14.0,
                        "corner_radii_cm": (1.0, 0.8, 1.1, 0.9, 0.6, 1.0, 0.7, 1.1),
                    },
                    _purpose("tileset_catalog", "tile_catalog_source"),
                ),
                "points": _wfc_tile_catalog_points(),
            },
            purpose=_purpose("tileset_catalog", "copy_tileset_catalog"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="wfc.socket_edges",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "wfc_socket_edge",
                    {"major_radius_cm": 2.2, "minor_radius_cm": 0.22, "axis": "y"},
                    _purpose("socket_edge_definitions", "socket_edge_source"),
                ),
                "points": ((-58.0, 27.0, -38.0), (-30.0, 27.0, -42.0), (0.0, 27.0, -44.0), (30.0, 27.0, -42.0), (58.0, 27.0, -38.0), (-58.0, 27.0, 38.0), (58.0, 27.0, 38.0)),
            },
            purpose=_purpose("socket_edge_definitions", "copy_socket_edges"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="wfc.adjacency_matrix",
            parameters={
                "profile_polygon": _rect_profile(64.0, 18.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (0.0, 26.0, _WFC_SOLVER_DEPTH_CM * 0.42),
            },
            purpose=_purpose("adjacency_rule_matrix", "raised_adjacency_matrix"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="wfc.constraint_grid",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "wfc_grid_cell",
                    {"profile_points": _rect_profile(9.0, 9.0), "height_cm": 0.22, "axis": "y"},
                    _purpose("constraint_grid", "grid_cell_source"),
                ),
                "points": _wfc_grid_cell_points(),
            },
            purpose=_purpose("constraint_grid", "copy_constraint_grid"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="wfc.entropy_weights",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "wfc_entropy_tick",
                    {"radius_cm": 1.0},
                    _purpose("entropy_or_weight_markers", "entropy_tick_source"),
                ),
                "points": tuple((-42.0 + index * 14.0, 28.0, -_WFC_SOLVER_DEPTH_CM * 0.48) for index in range(7)),
            },
            purpose=_purpose("entropy_or_weight_markers", "copy_entropy_ticks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="wfc.seed_region_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "wfc_seed_region_port",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("seed_and_region_ports", "seed_port_source"),
                ),
                "points": ((-54.0, 28.0, 0.0), (-18.0, 28.0, 12.0), (18.0, 28.0, 12.0), (54.0, 28.0, 0.0)),
            },
            purpose=_purpose("seed_and_region_ports", "copy_seed_region_ports"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="wfc.solver_iteration_path",
            parameters={
                "radius_cm": 0.5,
                "path": ((-_WFC_SOLVER_WIDTH_CM * 0.45, 29.0, -10.0), (-36.0, 33.0, 8.0), (-12.0, 28.0, 20.0), (12.0, 33.0, 8.0), (36.0, 28.0, 20.0), (_WFC_SOLVER_WIDTH_CM * 0.45, 31.0, -8.0)),
            },
            purpose=_purpose("solver_iteration_path", "swept_solver_iteration_path"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="wfc.failure_guards",
            parameters={
                "profile_polygon": _rect_profile(28.0, 8.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (_WFC_SOLVER_WIDTH_CM * 0.35, 27.0, _WFC_SOLVER_DEPTH_CM * 0.42),
            },
            purpose=_purpose("failure_or_backtrack_guards", "raised_failure_guard"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="wfc.solved_layout_output",
            parameters={
                "radius_cm": 0.65,
                "path": ((-52.0, 27.0, 30.0), (-32.0, 27.0, 12.0), (-8.0, 27.0, 22.0), (16.0, 27.0, 10.0), (38.0, 27.0, 26.0), (56.0, 27.0, 4.0)),
            },
            purpose=_purpose("solved_layout_output", "swept_solved_layout_path"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="wfc.tile_usage_wear",
            parameters={"amount": 0.13, "solver_iteration_bias": 0.73},
            purpose=_purpose("tile_usage_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.wfc_executable_layout", "primary_volume"),
        _node("recipe.wfc_tileset", "primary_volume"),
        _node("recipe.wfc_sockets", "socket"),
        _node("recipe.wfc_adjacency", "material_zone"),
        _node("recipe.wfc_constraint_grid", "rail"),
        _node("recipe.wfc_entropy", "fastener"),
        _node("recipe.wfc_seed_ports", "socket"),
        _node("recipe.wfc_iteration_path", "rail"),
        _node("recipe.wfc_failure_guard", "guard"),
        _node("recipe.wfc_solved_layout", "panel"),
        _node("recipe.wfc_tile_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="wfc_tile_solver_system",
        family="wfc_tile_solver_system",
        ops=ops,
    )
    return RecipeResult(
        family="wfc_tile_solver_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _cga_building_grammar_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="solid.cga_facade",
            target="cga.executable_facade",
            parameters={
                "width_cm": _CGA_GRAMMAR_WIDTH_CM,
                "height_cm": _CGA_GRAMMAR_HEIGHT_CM,
                "depth_cm": 8.0,
                "floors": 5,
                "bays": 6,
                "pattern": "office",
                "relief_depth_cm": 1.4,
                "pane_depth_cm": 0.45,
                "center": (0.0, _CGA_GRAMMAR_HEIGHT_CM * 0.5, 0.0),
                "vertical_axis": "y",
            },
            purpose=_purpose("executable_cga_facade", "cga_facade_solid"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="cga.root_massing",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "cga_root_massing",
                    {
                        "width_cm": _CGA_GRAMMAR_WIDTH_CM * 0.55,
                        "height_cm": _CGA_GRAMMAR_HEIGHT_CM,
                        "depth_cm": _CGA_GRAMMAR_DEPTH_CM * 0.45,
                        "center": (0.0, _CGA_GRAMMAR_HEIGHT_CM * 0.5, 0.0),
                    },
                    _purpose("root_massing_volume", "root_massing_source"),
                ),
                "width_cm": 1.8,
                "segments": 4,
            },
            purpose=_purpose("root_massing_volume", "beveled_root_massing"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cga.rule_stack",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cga_rule_card",
                    {"profile_points": _rect_profile(24.0, 6.0), "height_cm": 0.28, "axis": "y"},
                    _purpose("rule_stack", "rule_card_source"),
                ),
                "points": tuple((-_CGA_GRAMMAR_WIDTH_CM * 0.46, 18.0 + index * 7.0, -_CGA_GRAMMAR_DEPTH_CM * 0.44) for index in range(7)),
            },
            purpose=_purpose("rule_stack", "copy_rule_stack"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cga.split_repeat_extrude_ops",
            parameters={
                "radius_cm": 0.5,
                "path": ((-_CGA_GRAMMAR_WIDTH_CM * 0.42, 23.0, -18.0), (-30.0, 30.0, -8.0), (-6.0, 38.0, 2.0), (18.0, 44.0, -6.0), (_CGA_GRAMMAR_WIDTH_CM * 0.42, 51.0, 12.0)),
            },
            purpose=_purpose("split_repeat_extrude_ops", "swept_split_repeat_extrude_path"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cga.facade_floor_bands",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cga_facade_floor_band",
                    {"profile_points": _rect_profile(56.0, 2.6), "height_cm": 0.3, "axis": "y"},
                    _purpose("facade_floor_bands", "facade_band_source"),
                ),
                "points": _cga_floor_band_points(),
            },
            purpose=_purpose("facade_floor_bands", "copy_facade_floor_bands"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cga.terminal_modules",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "cga_terminal_module",
                    {
                        "width_cm": 11.0,
                        "height_cm": 8.0,
                        "depth_cm": 5.0,
                        "corner_radii_cm": (0.7, 0.5, 0.8, 0.6, 0.4, 0.7, 0.5, 0.8),
                    },
                    _purpose("terminal_module_set", "terminal_module_source"),
                ),
                "points": _cga_terminal_points(),
            },
            purpose=_purpose("terminal_module_set", "copy_terminal_modules"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cga.derivation_flow",
            parameters={
                "radius_cm": 0.45,
                "path": ((-50.0, 56.0, -24.0), (-25.0, 49.0, -8.0), (0.0, 57.0, 4.0), (25.0, 49.0, -8.0), (50.0, 56.0, -24.0)),
            },
            purpose=_purpose("derivation_flow_lines", "swept_derivation_flow"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="cga.variation_ports",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "cga_variation_port",
                    {"major_radius_cm": 2.8, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("variation_parameter_ports", "variation_port_source"),
                ),
                "points": ((-48.0, 28.0, 34.0), (-24.0, 36.0, 36.0), (0.0, 44.0, 34.0), (24.0, 36.0, 36.0), (48.0, 28.0, 34.0)),
            },
            purpose=_purpose("variation_parameter_ports", "copy_variation_ports"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="cga.constraint_guards",
            parameters={
                "radius_cm": 0.7,
                "path": ((-_CGA_GRAMMAR_WIDTH_CM * 0.5, 18.0, -_CGA_GRAMMAR_DEPTH_CM * 0.5), (_CGA_GRAMMAR_WIDTH_CM * 0.5, 18.0, -_CGA_GRAMMAR_DEPTH_CM * 0.5), (_CGA_GRAMMAR_WIDTH_CM * 0.5, 18.0, _CGA_GRAMMAR_DEPTH_CM * 0.5), (-_CGA_GRAMMAR_WIDTH_CM * 0.5, 18.0, _CGA_GRAMMAR_DEPTH_CM * 0.5), (-_CGA_GRAMMAR_WIDTH_CM * 0.5, 18.0, -_CGA_GRAMMAR_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("constraint_or_guard_rules", "swept_constraint_guard_frame"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="cga.output_assembly",
            parameters={
                "profile_polygon": _rect_profile(32.0, 8.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (_CGA_GRAMMAR_WIDTH_CM * 0.32, 21.0, -_CGA_GRAMMAR_DEPTH_CM * 0.42),
            },
            purpose=_purpose("output_assembly_markers", "raised_output_assembly_marker"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="cga.grammar_iteration_wear",
            parameters={"amount": 0.12, "rule_authoring_bias": 0.72},
            purpose=_purpose("grammar_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.cga_executable_facade", "primary_volume"),
        _node("recipe.cga_root_massing", "primary_volume"),
        _node("recipe.cga_rule_stack", "panel"),
        _node("recipe.cga_ops", "rail"),
        _node("recipe.cga_facade_bands", "material_zone"),
        _node("recipe.cga_terminals", "panel"),
        _node("recipe.cga_derivation_flow", "rail"),
        _node("recipe.cga_variation_ports", "socket"),
        _node("recipe.cga_constraint_guards", "guard"),
        _node("recipe.cga_output_markers", "decal_zone"),
        _node("recipe.cga_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="cga_building_grammar_system",
        family="cga_building_grammar_system",
        ops=ops,
    )
    return RecipeResult(
        family="cga_building_grammar_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _volume_effects_data_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="volume_effects.domain_bounds",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "volume_domain_bounds",
                    {
                        "width_cm": _VOLUME_EFFECT_WIDTH_CM,
                        "height_cm": _VOLUME_EFFECT_HEIGHT_CM,
                        "depth_cm": _VOLUME_EFFECT_DEPTH_CM,
                        "center": (0.0, _VOLUME_EFFECT_HEIGHT_CM * 0.5, 0.0),
                    },
                    _purpose("volume_domain_bounds", "domain_box_source"),
                ),
                "width_cm": 1.8,
                "segments": 4,
            },
            purpose=_purpose("volume_domain_bounds", "beveled_volume_domain"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="volume_effects.channels",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "volume_channel_lobe",
                    {"radius_cm": 4.4},
                    _purpose("density_temperature_velocity_channels", "channel_lobe_source"),
                ),
                "points": _volume_channel_points(),
            },
            purpose=_purpose("density_temperature_velocity_channels", "copy_field_channels"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="volume_effects.emitters",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "volume_emitter_port",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("emitters_and_sources", "emitter_source"),
                ),
                "points": ((-44.0, 22.0, -34.0), (-12.0, 22.0, -38.0), (12.0, 22.0, -38.0), (44.0, 22.0, -34.0)),
            },
            purpose=_purpose("emitters_and_sources", "copy_emitters"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="volume_effects.flow_vectors",
            parameters={
                "radius_cm": 0.6,
                "path": ((-_VOLUME_EFFECT_WIDTH_CM * 0.45, 24.0, 24.0), (-28.0, 42.0, 8.0), (-4.0, 30.0, -8.0), (24.0, 48.0, 10.0), (_VOLUME_EFFECT_WIDTH_CM * 0.45, 34.0, -24.0)),
            },
            purpose=_purpose("force_or_flow_vectors", "swept_force_flow_vectors"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="volume_effects.slice_planes",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "volume_slice_plane",
                    {"profile_points": _rect_profile(22.0, 12.0), "height_cm": 0.2, "axis": "y"},
                    _purpose("slice_or_sample_planes", "slice_plane_source"),
                ),
                "points": ((-32.0, 28.0, 0.0), (0.0, 35.0, 0.0), (32.0, 28.0, 0.0)),
            },
            purpose=_purpose("slice_or_sample_planes", "copy_slice_planes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="volume_effects.threshold_controls",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "volume_threshold_ring",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("threshold_or_isosurface_controls", "threshold_ring_source"),
                ),
                "points": ((-42.0, 44.0, 32.0), (-14.0, 48.0, 34.0), (14.0, 48.0, 34.0), (42.0, 44.0, 32.0)),
            },
            purpose=_purpose("threshold_or_isosurface_controls", "copy_threshold_rings"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="volume_effects.outputs",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "volume_output_port",
                    {"profile_points": _rect_profile(12.0, 7.0), "height_cm": 0.3, "axis": "y"},
                    _purpose("mesh_or_particle_outputs", "output_port_source"),
                ),
                "points": ((-44.0, 24.0, _VOLUME_EFFECT_DEPTH_CM * 0.5), (-14.0, 24.0, _VOLUME_EFFECT_DEPTH_CM * 0.52), (14.0, 24.0, _VOLUME_EFFECT_DEPTH_CM * 0.52), (44.0, 24.0, _VOLUME_EFFECT_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("mesh_or_particle_outputs", "copy_output_ports"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="volume_effects.cache_tiles",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "volume_cache_tile",
                    {
                        "width_cm": 8.0,
                        "height_cm": 3.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (0.6, 0.4, 0.7, 0.5, 0.3, 0.6, 0.4, 0.7),
                    },
                    _purpose("cache_tile_markers", "cache_tile_source"),
                ),
                "points": tuple((-36.0 + index * 12.0, 18.0, -_VOLUME_EFFECT_DEPTH_CM * 0.52) for index in range(7)),
            },
            purpose=_purpose("cache_tile_markers", "copy_cache_tiles"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="volume_effects.boundary_guards",
            parameters={
                "radius_cm": 0.75,
                "path": ((-_VOLUME_EFFECT_WIDTH_CM * 0.5, 20.0, -_VOLUME_EFFECT_DEPTH_CM * 0.5), (_VOLUME_EFFECT_WIDTH_CM * 0.5, 20.0, -_VOLUME_EFFECT_DEPTH_CM * 0.5), (_VOLUME_EFFECT_WIDTH_CM * 0.5, 20.0, _VOLUME_EFFECT_DEPTH_CM * 0.5), (-_VOLUME_EFFECT_WIDTH_CM * 0.5, 20.0, _VOLUME_EFFECT_DEPTH_CM * 0.5), (-_VOLUME_EFFECT_WIDTH_CM * 0.5, 20.0, -_VOLUME_EFFECT_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("field_boundary_guards", "swept_field_boundary_guards"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="volume_effects.iteration_wear",
            parameters={"amount": 0.13, "field_solve_bias": 0.76},
            purpose=_purpose("volume_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.volume_domain", "primary_volume"),
        _node("recipe.volume_channels", "material_zone"),
        _node("recipe.volume_emitters", "socket"),
        _node("recipe.volume_flow", "rail"),
        _node("recipe.volume_slices", "panel"),
        _node("recipe.volume_thresholds", "fastener"),
        _node("recipe.volume_outputs", "socket"),
        _node("recipe.volume_cache_tiles", "panel"),
        _node("recipe.volume_boundary_guards", "guard"),
        _node("recipe.volume_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="volume_effects_data_system",
        family="volume_effects_data_system",
        ops=ops,
    )
    return RecipeResult(
        family="volume_effects_data_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _instance_pattern_scatter_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="scatter.source_library",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "scatter_source_part",
                    {
                        "width_cm": 12.0,
                        "height_cm": 5.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (0.8, 0.6, 0.9, 0.7, 0.5, 0.8, 0.6, 0.9),
                    },
                    _purpose("source_part_library", "source_part_source"),
                ),
                "points": ((-52.0, 27.0, -34.0), (-24.0, 27.0, -38.0), (4.0, 27.0, -38.0), (32.0, 27.0, -34.0), (54.0, 27.0, -24.0)),
            },
            purpose=_purpose("source_part_library", "copy_source_part_library"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scatter.point_cloud_samples",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "scatter_sample_point",
                    {"radius_cm": 0.9},
                    _purpose("point_cloud_or_samples", "sample_point_source"),
                ),
                "points": _scatter_sample_points(),
            },
            purpose=_purpose("point_cloud_or_samples", "copy_sample_points"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="scatter.surface_projection_target",
            parameters={
                "profile_polygon": _rect_profile(_SCATTER_SYSTEM_WIDTH_CM * 0.72, _SCATTER_SYSTEM_DEPTH_CM * 0.55),
                "extrude_height_cm": 0.2,
                "axis": "y",
                "center": (0.0, 24.0, 0.0),
            },
            purpose=_purpose("surface_projection_target", "raised_projection_surface"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scatter.density_masks",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "scatter_density_mask",
                    {"profile_points": _rect_profile(16.0, 6.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("density_or_mask_controls", "density_mask_source"),
                ),
                "points": ((-46.0, 25.0, 34.0), (-18.0, 25.0, 38.0), (10.0, 25.0, 38.0), (38.0, 25.0, 34.0)),
            },
            purpose=_purpose("density_or_mask_controls", "copy_density_masks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scatter.spacing_rules",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "scatter_spacing_guard",
                    {"major_radius_cm": 3.2, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("poisson_or_spacing_rules", "spacing_guard_source"),
                ),
                "points": ((-48.0, 28.0, 8.0), (-16.0, 28.0, 14.0), (16.0, 28.0, 14.0), (48.0, 28.0, 8.0)),
            },
            purpose=_purpose("poisson_or_spacing_rules", "copy_spacing_guards"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scatter.orient_scale_jitter",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "scatter_jitter_knob",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("orient_scale_jitter_controls", "jitter_knob_source"),
                ),
                "points": tuple((-42.0 + index * 14.0, 29.0, -_SCATTER_SYSTEM_DEPTH_CM * 0.5) for index in range(7)),
            },
            purpose=_purpose("orient_scale_jitter_controls", "copy_jitter_controls"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="scatter.collision_exclusion_guards",
            parameters={
                "radius_cm": 0.7,
                "path": ((-_SCATTER_SYSTEM_WIDTH_CM * 0.5, 26.0, -_SCATTER_SYSTEM_DEPTH_CM * 0.5), (_SCATTER_SYSTEM_WIDTH_CM * 0.5, 26.0, -_SCATTER_SYSTEM_DEPTH_CM * 0.5), (_SCATTER_SYSTEM_WIDTH_CM * 0.5, 26.0, _SCATTER_SYSTEM_DEPTH_CM * 0.5), (-_SCATTER_SYSTEM_WIDTH_CM * 0.5, 26.0, _SCATTER_SYSTEM_DEPTH_CM * 0.5), (-_SCATTER_SYSTEM_WIDTH_CM * 0.5, 26.0, -_SCATTER_SYSTEM_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("collision_or_exclusion_guards", "swept_collision_exclusion_guards"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="scatter.instance_outputs",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "scatter_instance_output",
                    {"profile_points": _rect_profile(10.0, 5.0), "height_cm": 0.3, "axis": "y"},
                    _purpose("instance_output_markers", "instance_output_source"),
                ),
                "points": ((-54.0, 27.0, 44.0), (-27.0, 27.0, 46.0), (0.0, 27.0, 48.0), (27.0, 27.0, 46.0), (54.0, 27.0, 44.0)),
            },
            purpose=_purpose("instance_output_markers", "copy_instance_output_markers"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="scatter.debug_traces",
            parameters={
                "radius_cm": 0.4,
                "path": ((-58.0, 29.0, 22.0), (-32.0, 33.0, 8.0), (-8.0, 29.0, -8.0), (18.0, 33.0, 6.0), (46.0, 29.0, -18.0)),
            },
            purpose=_purpose("scatter_debug_traces", "swept_scatter_debug_traces"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="scatter.usage_wear",
            parameters={"amount": 0.12, "scatter_projection_bias": 0.74},
            purpose=_purpose("scatter_usage_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.scatter_sources", "primary_volume"),
        _node("recipe.scatter_samples", "fastener"),
        _node("recipe.scatter_projection", "material_zone"),
        _node("recipe.scatter_density", "material_zone"),
        _node("recipe.scatter_spacing", "guard"),
        _node("recipe.scatter_jitter", "socket"),
        _node("recipe.scatter_collision", "guard"),
        _node("recipe.scatter_outputs", "panel"),
        _node("recipe.scatter_debug", "rail"),
        _node("recipe.scatter_usage_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="instance_pattern_scatter_system",
        family="instance_pattern_scatter_system",
        ops=ops,
    )
    return RecipeResult(
        family="instance_pattern_scatter_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _f_rep_sdf_composition_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="solid.sdf_metaball_cluster",
            target="f_rep_sdf.executable_metaball_cluster",
            parameters={
                "blob_count": 6,
                "radius_cm": 4.5,
                "field_radius_cm": 14.0,
                "smooth_radius_cm": 3.0,
                "resolution": 36,
                "extraction_backend": "dual_contouring",
                "center": (0.0, _FREP_SDF_HEIGHT_CM * 0.54, 0.0),
                "seed": 5,
            },
            purpose=_purpose("executable_sdf_metaball_cluster", "sdf_metaball_cluster_solid"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="f_rep_sdf.implicit_primitives",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "sdf_implicit_lobe",
                    {"radius_cm": 5.0},
                    _purpose("implicit_primitive_set", "implicit_lobe_source"),
                ),
                "points": _sdf_primitive_points(),
            },
            purpose=_purpose("implicit_primitive_set", "copy_implicit_primitives"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="f_rep_sdf.expression_tree",
            parameters={
                "radius_cm": 0.55,
                "path": ((-_FREP_SDF_WIDTH_CM * 0.42, 32.0, -_FREP_SDF_DEPTH_CM * 0.35), (-24.0, 44.0, -12.0), (0.0, 36.0, 4.0), (24.0, 46.0, 18.0), (_FREP_SDF_WIDTH_CM * 0.42, 34.0, _FREP_SDF_DEPTH_CM * 0.32)),
            },
            purpose=_purpose("expression_tree", "swept_expression_tree"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="f_rep_sdf.smooth_booleans",
            parameters={
                "radius_cm": 0.75,
                "path": ((-40.0, 28.0, 24.0), (-18.0, 38.0, 6.0), (4.0, 30.0, -8.0), (26.0, 40.0, 6.0), (48.0, 28.0, -24.0)),
            },
            purpose=_purpose("smooth_boolean_ops", "swept_smooth_boolean_chain"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="f_rep_sdf.blend_radius_controls",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "sdf_blend_radius_ring",
                    {"major_radius_cm": 3.4, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("blend_radius_controls", "blend_radius_source"),
                ),
                "points": ((-42.0, 42.0, 32.0), (-14.0, 48.0, 34.0), (14.0, 48.0, 34.0), (42.0, 42.0, 32.0)),
            },
            purpose=_purpose("blend_radius_controls", "copy_blend_radius_controls"),
        ),
        ShapeOp(
            op="sop.polybevel",
            target="f_rep_sdf.sample_bounds",
            parameters={
                "source": _source_op(
                    "solid.box",
                    "sdf_sample_bounds",
                    {
                        "width_cm": _FREP_SDF_WIDTH_CM,
                        "height_cm": _FREP_SDF_HEIGHT_CM,
                        "depth_cm": _FREP_SDF_DEPTH_CM,
                        "center": (0.0, _FREP_SDF_HEIGHT_CM * 0.5, 0.0),
                    },
                    _purpose("field_sample_bounds", "sample_bounds_source"),
                ),
                "width_cm": 1.6,
                "segments": 4,
            },
            purpose=_purpose("field_sample_bounds", "beveled_sample_bounds"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="f_rep_sdf.material_region_fields",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "sdf_material_region",
                    {"profile_points": _rect_profile(16.0, 7.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("material_region_fields", "material_region_source"),
                ),
                "points": ((-38.0, 30.0, -36.0), (-12.0, 30.0, -38.0), (12.0, 30.0, -38.0), (38.0, 30.0, -36.0)),
            },
            purpose=_purpose("material_region_fields", "copy_material_regions"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="f_rep_sdf.extraction_ports",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "sdf_extraction_port",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("extraction_or_meshing_ports", "extraction_port_source"),
                ),
                "points": ((-_FREP_SDF_WIDTH_CM * 0.45, 28.0, _FREP_SDF_DEPTH_CM * 0.44), (-18.0, 28.0, _FREP_SDF_DEPTH_CM * 0.48), (18.0, 28.0, _FREP_SDF_DEPTH_CM * 0.48), (_FREP_SDF_WIDTH_CM * 0.45, 28.0, _FREP_SDF_DEPTH_CM * 0.44)),
            },
            purpose=_purpose("extraction_or_meshing_ports", "copy_extraction_ports"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="f_rep_sdf.failure_guards",
            parameters={
                "radius_cm": 0.7,
                "path": ((-_FREP_SDF_WIDTH_CM * 0.5, 24.0, -_FREP_SDF_DEPTH_CM * 0.5), (_FREP_SDF_WIDTH_CM * 0.5, 24.0, -_FREP_SDF_DEPTH_CM * 0.5), (_FREP_SDF_WIDTH_CM * 0.5, 24.0, _FREP_SDF_DEPTH_CM * 0.5), (-_FREP_SDF_WIDTH_CM * 0.5, 24.0, _FREP_SDF_DEPTH_CM * 0.5), (-_FREP_SDF_WIDTH_CM * 0.5, 24.0, -_FREP_SDF_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("failure_or_bounds_guards", "swept_failure_bounds_guards"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="f_rep_sdf.organic_silhouette",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "sdf_organic_silhouette_marker",
                    {
                        "width_cm": 10.0,
                        "height_cm": 6.0,
                        "depth_cm": 8.0,
                        "corner_radii_cm": (1.5, 1.0, 1.8, 1.2, 0.8, 1.6, 0.9, 1.4),
                    },
                    _purpose("organic_silhouette_markers", "organic_marker_source"),
                ),
                "points": ((-34.0, 52.0, -4.0), (-10.0, 58.0, 8.0), (16.0, 54.0, 10.0), (38.0, 50.0, -6.0)),
            },
            purpose=_purpose("organic_silhouette_markers", "copy_organic_silhouette_markers"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="f_rep_sdf.iteration_wear",
            parameters={"amount": 0.12, "implicit_authoring_bias": 0.74},
            purpose=_purpose("implicit_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.sdf_executable_metaballs", "primary_volume"),
        _node("recipe.sdf_primitives", "primary_volume"),
        _node("recipe.sdf_expression_tree", "rail"),
        _node("recipe.sdf_smooth_booleans", "rail"),
        _node("recipe.sdf_blend_controls", "fastener"),
        _node("recipe.sdf_sample_bounds", "guard"),
        _node("recipe.sdf_material_regions", "material_zone"),
        _node("recipe.sdf_extraction_ports", "socket"),
        _node("recipe.sdf_failure_guards", "guard"),
        _node("recipe.sdf_organic_markers", "primary_volume"),
        _node("recipe.sdf_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="f_rep_sdf_composition_system",
        family="f_rep_sdf_composition_system",
        ops=ops,
    )
    return RecipeResult(
        family="f_rep_sdf_composition_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _subdivision_finishing_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.copy_to_points",
            target="subdivision_finishing.control_cage",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "subdivision_cage_tile",
                    {
                        "width_cm": 12.0,
                        "height_cm": 6.0,
                        "depth_cm": 10.0,
                        "corner_radii_cm": (0.8, 0.6, 0.9, 0.7, 0.5, 0.8, 0.6, 0.9),
                    },
                    _purpose("control_cage", "control_cage_tile_source"),
                ),
                "points": _subdivision_cage_points(),
            },
            purpose=_purpose("control_cage", "copy_control_cage_tiles"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="subdivision_finishing.scheme",
            parameters={
                "profile_polygon": _rect_profile(42.0, 9.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (-_SUBDIV_FINISH_WIDTH_CM * 0.28, 34.0, _SUBDIV_FINISH_DEPTH_CM * 0.42),
            },
            purpose=_purpose("subdivision_scheme", "raised_scheme_badge"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="subdivision_finishing.crease_tags",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "subdivision_crease_tag",
                    {"profile_points": _rect_profile(14.0, 3.0), "height_cm": 0.3, "axis": "y"},
                    _purpose("crease_or_sharpness_tags", "crease_tag_source"),
                ),
                "points": tuple((-42.0 + index * 14.0, 35.0, -_SUBDIV_FINISH_DEPTH_CM * 0.48) for index in range(7)),
            },
            purpose=_purpose("crease_or_sharpness_tags", "copy_crease_tags"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="subdivision_finishing.boundary_rules",
            parameters={
                "radius_cm": 0.7,
                "path": ((-_SUBDIV_FINISH_WIDTH_CM * 0.5, 28.0, -_SUBDIV_FINISH_DEPTH_CM * 0.5), (_SUBDIV_FINISH_WIDTH_CM * 0.5, 28.0, -_SUBDIV_FINISH_DEPTH_CM * 0.5), (_SUBDIV_FINISH_WIDTH_CM * 0.5, 28.0, _SUBDIV_FINISH_DEPTH_CM * 0.5), (-_SUBDIV_FINISH_WIDTH_CM * 0.5, 28.0, _SUBDIV_FINISH_DEPTH_CM * 0.5), (-_SUBDIV_FINISH_WIDTH_CM * 0.5, 28.0, -_SUBDIV_FINISH_DEPTH_CM * 0.5)),
            },
            purpose=_purpose("boundary_or_uv_rules", "swept_boundary_rule_frame"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="subdivision_finishing.remesh_targets",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "subdivision_quad_target",
                    {"major_radius_cm": 3.0, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("remesh_or_quad_targets", "quad_target_source"),
                ),
                "points": ((-48.0, 36.0, 28.0), (-18.0, 38.0, 32.0), (18.0, 38.0, 32.0), (48.0, 36.0, 28.0)),
            },
            purpose=_purpose("remesh_or_quad_targets", "copy_remesh_targets"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="subdivision_finishing.smoothing_passes",
            parameters={
                "radius_cm": 0.5,
                "path": ((-_SUBDIV_FINISH_WIDTH_CM * 0.42, 37.0, -12.0), (-24.0, 43.0, 8.0), (0.0, 37.0, 18.0), (24.0, 43.0, 8.0), (_SUBDIV_FINISH_WIDTH_CM * 0.42, 37.0, -12.0)),
            },
            purpose=_purpose("smoothing_or_relax_passes", "swept_smoothing_passes"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="subdivision_finishing.detail_layers",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "subdivision_detail_tick",
                    {"radius_cm": 1.1},
                    _purpose("displacement_or_detail_layers", "detail_tick_source"),
                ),
                "points": tuple((-36.0 + index * 12.0, 39.0, 0.0) for index in range(7)),
            },
            purpose=_purpose("displacement_or_detail_layers", "copy_detail_ticks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="subdivision_finishing.quality_probes",
            parameters={
                "source": _source_op(
                    "solid.revolved_profile",
                    "subdivision_quality_probe",
                    {"profile_points": _rivet_profile(), "axis": "y"},
                    _purpose("quality_probe_markers", "quality_probe_source"),
                ),
                "points": ((-50.0, 32.0, -30.0), (-20.0, 34.0, -34.0), (20.0, 34.0, -34.0), (50.0, 32.0, -30.0)),
            },
            purpose=_purpose("quality_probe_markers", "copy_quality_probes"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="subdivision_finishing.output_lods",
            parameters={
                "profile_polygon": _rect_profile(34.0, 8.0),
                "extrude_height_cm": 0.25,
                "axis": "y",
                "center": (_SUBDIV_FINISH_WIDTH_CM * 0.3, 34.0, _SUBDIV_FINISH_DEPTH_CM * 0.42),
            },
            purpose=_purpose("output_lod_markers", "raised_output_lod_marker"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="subdivision_finishing.iteration_wear",
            parameters={"amount": 0.12, "finishing_review_bias": 0.72},
            purpose=_purpose("finishing_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.subdivision_control_cage", "primary_volume"),
        _node("recipe.subdivision_scheme", "decal_zone"),
        _node("recipe.subdivision_creases", "trim"),
        _node("recipe.subdivision_boundaries", "guard"),
        _node("recipe.subdivision_remesh_targets", "socket"),
        _node("recipe.subdivision_smoothing", "rail"),
        _node("recipe.subdivision_detail_layers", "material_zone"),
        _node("recipe.subdivision_quality_probes", "fastener"),
        _node("recipe.subdivision_outputs", "decal_zone"),
        _node("recipe.subdivision_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="subdivision_finishing_system",
        family="subdivision_finishing_system",
        ops=ops,
    )
    return RecipeResult(
        family="subdivision_finishing_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _humanoid_anatomy_preset_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="humanoid_anatomy.canonical_topology",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "humanoid_canonical_body_cage",
                    {
                        "width_cm": _HUMANOID_ANATOMY_WIDTH_CM,
                        "height_cm": _HUMANOID_ANATOMY_HEIGHT_CM,
                        "depth_cm": _HUMANOID_ANATOMY_DEPTH_CM,
                        "center": (0.0, _HUMANOID_ANATOMY_HEIGHT_CM * 0.5, 0.0),
                        "corner_radii_cm": (8.0, 7.0, 8.5, 7.5, 5.0, 6.5, 5.5, 6.0),
                    },
                    _purpose("canonical_topology", "canonical_body_cage_source"),
                ),
                "width_cm": 1.2,
                "segments": 5,
            },
            purpose=_purpose("canonical_topology", "polybeveled_canonical_body_cage"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="humanoid_anatomy.body_proportions",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "humanoid_measurement_tick",
                    {"profile_points": _rect_profile(10.0, 2.0), "height_cm": 0.3, "axis": "z"},
                    _purpose("body_proportion_set", "measurement_tick_source"),
                ),
                "points": tuple((-_HUMANOID_ANATOMY_WIDTH_CM * 0.48, y, -_HUMANOID_ANATOMY_DEPTH_CM * 0.46) for y in (18.0, 42.0, 66.0, 90.0, 114.0, 138.0, 162.0)),
            },
            purpose=_purpose("body_proportion_set", "copy_body_measurement_ticks"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="humanoid_anatomy.region_map",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "humanoid_region_landmark",
                    {"radius_cm": 2.1},
                    _purpose("anatomy_region_map", "region_landmark_source"),
                ),
                "points": _humanoid_landmark_points(),
            },
            purpose=_purpose("anatomy_region_map", "copy_body_region_landmarks"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="humanoid_anatomy.landmark_loops",
            parameters={
                "radius_cm": 0.75,
                "path": ((-28.0, 134.0, -18.0), (-14.0, 148.0, -20.0), (0.0, 152.0, -22.0), (14.0, 148.0, -20.0), (28.0, 134.0, -18.0)),
            },
            purpose=_purpose("landmark_loop_set", "swept_face_and_shoulder_loop"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="humanoid_anatomy.joint_rig_anchors",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "humanoid_joint_anchor",
                    {"major_radius_cm": 2.4, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("joint_and_rig_anchors", "joint_anchor_source"),
                ),
                "points": ((0.0, 150.0, 0.0), (-26.0, 134.0, 0.0), (26.0, 134.0, 0.0), (-15.0, 92.0, 0.0), (15.0, 92.0, 0.0), (-12.0, 48.0, 0.0), (12.0, 48.0, 0.0)),
            },
            purpose=_purpose("joint_and_rig_anchors", "copy_joint_anchor_map"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="humanoid_anatomy.morph_targets",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "humanoid_morph_target_slot",
                    {"profile_points": _rect_profile(7.0, 5.0), "height_cm": 0.45, "axis": "y"},
                    _purpose("morph_target_database", "morph_slot_source"),
                ),
                "points": _morph_target_points(),
            },
            purpose=_purpose("morph_target_database", "copy_morph_target_slots"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="humanoid_anatomy.skin_weight_zones",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "humanoid_skin_weight_band",
                    {
                        "width_cm": 16.0,
                        "height_cm": 4.0,
                        "depth_cm": 3.0,
                        "corner_radii_cm": (0.8, 0.7, 0.8, 0.7, 0.5, 0.6, 0.5, 0.6),
                    },
                    _purpose("skin_weight_zones", "skin_weight_band_source"),
                ),
                "points": ((0.0, 126.0, 18.5), (0.0, 104.0, 18.5), (-14.0, 72.0, 18.0), (14.0, 72.0, 18.0), (-8.0, 34.0, 17.5), (8.0, 34.0, 17.5)),
            },
            purpose=_purpose("skin_weight_zones", "copy_skin_weight_zones"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="humanoid_anatomy.style_variant_slots",
            parameters={
                "profile_polygon": _rect_profile(48.0, 10.0),
                "extrude_height_cm": 0.35,
                "axis": "y",
                "center": (0.0, 176.0, _HUMANOID_ANATOMY_DEPTH_CM * 0.46),
            },
            purpose=_purpose("style_variant_slots", "raised_anatomy_preset_band"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="humanoid_anatomy.validation_guards",
            parameters={
                "radius_cm": 0.65,
                "path": ((-_HUMANOID_ANATOMY_WIDTH_CM * 0.52, 4.0, -_HUMANOID_ANATOMY_DEPTH_CM * 0.52), (_HUMANOID_ANATOMY_WIDTH_CM * 0.52, 4.0, -_HUMANOID_ANATOMY_DEPTH_CM * 0.52), (_HUMANOID_ANATOMY_WIDTH_CM * 0.52, 176.0, -_HUMANOID_ANATOMY_DEPTH_CM * 0.52), (-_HUMANOID_ANATOMY_WIDTH_CM * 0.52, 176.0, -_HUMANOID_ANATOMY_DEPTH_CM * 0.52)),
            },
            purpose=_purpose("anatomy_validation_guards", "swept_symmetry_and_range_guard"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="humanoid_anatomy.iteration_wear",
            parameters={"amount": 0.09, "anatomy_authoring_bias": 0.82},
            purpose=_purpose("anatomy_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.humanoid_canonical_topology", "primary_volume"),
        _node("recipe.humanoid_body_proportions", "panel"),
        _node("recipe.humanoid_region_map", "material_zone"),
        _node("recipe.humanoid_landmark_loops", "rail"),
        _node("recipe.humanoid_joint_anchors", "socket"),
        _node("recipe.humanoid_morph_database", "panel"),
        _node("recipe.humanoid_skin_weights", "material_zone"),
        _node("recipe.humanoid_style_variants", "socket"),
        _node("recipe.humanoid_validation_guards", "guard"),
        _node("recipe.humanoid_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="humanoid_anatomy_preset_system",
        family="humanoid_anatomy_preset_system",
        ops=ops,
    )
    return RecipeResult(
        family="humanoid_anatomy_preset_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def _face_sdf_cel_shading_system_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    del brief, parts, graph_nodes
    ops = (
        ShapeOp(
            op="sop.polybevel",
            target="face_sdf_cel.face_region_sdf",
            parameters={
                "source": _source_op(
                    "solid.subdivision_box",
                    "face_sdf_domain",
                    {
                        "width_cm": _FACE_SDF_WIDTH_CM,
                        "height_cm": _FACE_SDF_HEIGHT_CM,
                        "depth_cm": _FACE_SDF_DEPTH_CM,
                        "center": (0.0, _FACE_SDF_HEIGHT_CM * 0.5, 0.0),
                        "corner_radii_cm": (7.0, 6.0, 7.5, 6.5, 4.0, 5.5, 4.5, 5.0),
                    },
                    _purpose("face_region_sdf", "face_sdf_domain_source"),
                ),
                "width_cm": 1.1,
                "segments": 5,
            },
            purpose=_purpose("face_region_sdf", "polybeveled_face_sdf_domain"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="face_sdf_cel.shadow_band_fields",
            parameters={
                "radius_cm": 0.8,
                "path": ((-36.0, 36.0, -26.0), (-18.0, 30.0, -30.0), (0.0, 34.0, -32.0), (18.0, 30.0, -30.0), (36.0, 36.0, -26.0)),
            },
            purpose=_purpose("shadow_band_fields", "swept_face_shadow_sdf_band"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="face_sdf_cel.ramp_lut_stack",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cel_ramp_lut_cell",
                    {"profile_points": _rect_profile(9.0, 5.0), "height_cm": 0.32, "axis": "y"},
                    _purpose("ramp_lut_stack", "ramp_lut_cell_source"),
                ),
                "points": tuple((-36.0 + column * 12.0, 48.0 + row * 6.0, 26.0) for row in range(3) for column in range(7)),
            },
            purpose=_purpose("ramp_lut_stack", "copy_ramp_lut_cells"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="face_sdf_cel.outline_hull",
            parameters={
                "radius_cm": 1.0,
                "path": ((-_FACE_SDF_WIDTH_CM * 0.48, 20.0, -_FACE_SDF_DEPTH_CM * 0.48), (-24.0, 52.0, -_FACE_SDF_DEPTH_CM * 0.5), (0.0, 58.0, -_FACE_SDF_DEPTH_CM * 0.52), (24.0, 52.0, -_FACE_SDF_DEPTH_CM * 0.5), (_FACE_SDF_WIDTH_CM * 0.48, 20.0, -_FACE_SDF_DEPTH_CM * 0.48)),
            },
            purpose=_purpose("outline_or_inverted_hull", "swept_inverted_hull_outline"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="face_sdf_cel.light_direction_controls",
            parameters={
                "source": _source_op(
                    "solid.torus",
                    "cel_light_direction_port",
                    {"major_radius_cm": 3.2, "minor_radius_cm": 0.24, "axis": "y"},
                    _purpose("light_direction_controls", "light_direction_port_source"),
                ),
                "points": ((-42.0, 36.0, 32.0), (-14.0, 44.0, 34.0), (14.0, 44.0, 34.0), (42.0, 36.0, 32.0)),
            },
            purpose=_purpose("light_direction_controls", "copy_light_direction_controls"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="face_sdf_cel.id_mask_channels",
            parameters={
                "source": _source_op(
                    "solid.sphere",
                    "face_sdf_id_mask_region",
                    {"radius_cm": 2.0},
                    _purpose("id_mask_channels", "id_mask_region_source"),
                ),
                "points": _face_sdf_mask_points(),
            },
            purpose=_purpose("id_mask_channels", "copy_face_id_mask_regions"),
        ),
        ShapeOp(
            op="sop.polyextrude",
            target="face_sdf_cel.style_bridge_guards",
            parameters={
                "profile_polygon": _rect_profile(46.0, 8.0),
                "extrude_height_cm": 0.28,
                "axis": "y",
                "center": (-_FACE_SDF_WIDTH_CM * 0.24, 18.0, _FACE_SDF_DEPTH_CM * 0.48),
            },
            purpose=_purpose("style_bridge_guards", "raised_pbr_cel_bridge_guard"),
        ),
        ShapeOp(
            op="sop.copy_to_points",
            target="face_sdf_cel.preview_outputs",
            parameters={
                "source": _source_op(
                    "solid.extruded_profile",
                    "cel_preview_tile",
                    {"profile_points": _rect_profile(12.0, 8.0), "height_cm": 0.25, "axis": "y"},
                    _purpose("preview_render_outputs", "preview_tile_source"),
                ),
                "points": ((-34.0, 12.0, 34.0), (-10.0, 12.0, 36.0), (14.0, 12.0, 36.0), (38.0, 12.0, 34.0)),
            },
            purpose=_purpose("preview_render_outputs", "copy_preview_output_tiles"),
        ),
        ShapeOp(
            op="sop.polywire",
            target="face_sdf_cel.expression_morph_hooks",
            parameters={
                "radius_cm": 0.55,
                "path": ((-28.0, 28.0, -34.0), (-12.0, 22.0, -36.0), (0.0, 24.0, -38.0), (12.0, 22.0, -36.0), (28.0, 28.0, -34.0)),
            },
            purpose=_purpose("expression_or_morph_hooks", "swept_expression_shadow_hooks"),
        ),
        ShapeOp(
            op="op.chip_edges",
            target="face_sdf_cel.iteration_wear",
            parameters={"amount": 0.1, "cel_style_review_bias": 0.8},
            purpose=_purpose("cel_iteration_wear_masks", "chip_edges"),
        ),
    )
    nodes = (
        _node("recipe.face_sdf_regions", "primary_volume"),
        _node("recipe.face_shadow_fields", "material_zone"),
        _node("recipe.cel_ramp_lut_stack", "panel"),
        _node("recipe.cel_outline_hull", "rail"),
        _node("recipe.cel_light_controls", "socket"),
        _node("recipe.face_id_masks", "decal_zone"),
        _node("recipe.cel_style_bridge_guards", "guard"),
        _node("recipe.cel_preview_outputs", "panel"),
        _node("recipe.cel_expression_hooks", "socket"),
        _node("recipe.cel_iteration_wear", "wear_zone"),
    )
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="face_sdf_cel_shading_system",
        family="face_sdf_cel_shading_system",
        ops=ops,
    )
    return RecipeResult(
        family="face_sdf_cel_shading_system",
        shape_program=program,
        synthesized_graph_nodes=nodes,
    )


def industrial_crate_recipe(
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    """Lower the industrial_crate family grammar into v2 ops + graph nodes.

    Args:
        brief: design-brief dict (Phase 2). Reserved for future recipes
            that select between sub-variants (squat / tall / wide); the
            Phase 6 industrial-crate recipe ignores its contents but the
            parameter is carried so the signature is stable across
            future variant work.
        parts: parts list from ``asset["intent"]["parts"]``. Reserved
            for future recipes that emit additional ops only when a
            specific part exists (e.g. an ``op.weld_seam`` only when a
            weld_seam part is declared); the Phase 6 industrial-crate
            recipe emits the full 10-requirement program unconditionally
            so the synthesized ShapeProgram is a deterministic function
            of the family alone.
        graph_nodes: current ``runtime["construction_graph"]["nodes"]``
            tuple. Reserved for future recipes that consume existing
            graph evidence to vary the program; the Phase 6
            industrial-crate recipe ignores it but the parameter is
            carried so a later phase can opt in without changing the
            signature.

    Returns:
        A frozen :class:`RecipeResult` carrying the
        :class:`ShapeProgram` and a tuple of synthesized graph-node
        dicts. Determinism: identical inputs always yield identical
        outputs, including op order, parameter dicts, and node ids.
    """
    del brief, parts, graph_nodes
    ops: list[ShapeOp] = []
    nodes: list[dict[str, Any]] = []
    for _requirement_name, lowerer in _INDUSTRIAL_CRATE_LOWERERS:
        requirement_ops, requirement_nodes = lowerer()
        ops.extend(requirement_ops)
        nodes.extend(requirement_nodes)
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name="industrial_crate",
        family="industrial_crate",
        ops=tuple(ops),
    )
    return RecipeResult(
        family="industrial_crate",
        shape_program=program,
        synthesized_graph_nodes=tuple(nodes),
    )


def _empty_recipe(family: str, asset_name: str) -> RecipeResult:
    """Return a :class:`RecipeResult` with an empty program for ``family``.

    Used when the family is unknown or not yet covered by a Phase 6
    recipe (every family other than ``industrial_crate``). The Phase 5
    v1 adapter handles an empty program cleanly: no v1 records, no
    diagnostics.
    """
    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name=asset_name,
        family=family,
        ops=(),
    )
    return RecipeResult(
        family=family,
        shape_program=program,
        synthesized_graph_nodes=(),
    )


_RECIPES: dict[str, Any] = {
    "industrial_crate": industrial_crate_recipe,
    "mechanical_door": _mechanical_door_recipe,
    "service_cabinet": _service_cabinet_recipe,
    "weapon_prop": _weapon_prop_recipe,
    "vehicle_prop": _vehicle_prop_recipe,
    "furniture_prop": _furniture_prop_recipe,
    "natural_form": _natural_form_recipe,
    "environment_architecture": _environment_architecture_recipe,
    "lighting_prop": _lighting_prop_recipe,
    "machine_console": _machine_console_recipe,
    "portal_relic": _portal_relic_recipe,
    "tool_prop": _tool_prop_recipe,
    "modular_kit": _modular_kit_recipe,
    "character_creature": _character_creature_recipe,
    "set_dressing_prop": _set_dressing_prop_recipe,
    "surface_material_sample": _surface_material_sample_recipe,
    "terrain_vegetation_variant": _terrain_vegetation_variant_recipe,
    "environment_effect": _environment_effect_recipe,
    "settlement_district": _settlement_district_recipe,
    "gameplay_object": _gameplay_object_recipe,
    "encounter_flow": _encounter_flow_recipe,
    "inventory_economy_object": _inventory_economy_object_recipe,
    "rig_animation_proxy": _rig_animation_proxy_recipe,
    "rig_component_library_system": _rig_component_library_system_recipe,
    "morph_target_database_system": _morph_target_database_system_recipe,
    "animation_library_binding_system": _animation_library_binding_system_recipe,
    "retargeting_pack_system": _retargeting_pack_system_recipe,
    "character_equipment_binding_system": _character_equipment_binding_system_recipe,
    "gameplay_animation_controller_system": _gameplay_animation_controller_system_recipe,
    "procedural_facial_rig_pack_system": _procedural_facial_rig_pack_system_recipe,
    "hair_program_system": _hair_program_system_recipe,
    "cloth_fabric_simulation_program_system": _cloth_fabric_simulation_program_system_recipe,
    "fluid_forward_volume_program_system": _fluid_forward_volume_program_system_recipe,
    "construction_grammar_kit_system": _construction_grammar_kit_system_recipe,
    "creature_appendage_program_system": _creature_appendage_program_system_recipe,
    "body_part_procedural_library_system": _body_part_procedural_library_system_recipe,
    "material_primitive_library_system": _material_primitive_library_system_recipe,
    "stateful_destructible_prop": _stateful_destructible_prop_recipe,
    "cloth_attachment_form": _cloth_attachment_form_recipe,
    "domain_kit_bundle": _domain_kit_bundle_recipe,
    "world_system_assembly": _world_system_assembly_recipe,
    "simulation_environment_system": _simulation_environment_system_recipe,
    "authored_multi_asset_bundle": _authored_multi_asset_bundle_recipe,
    "live_procedural_runtime_bundle": _live_procedural_runtime_bundle_recipe,
    "engine_facing_runtime_bundle_system": _engine_facing_runtime_bundle_system_recipe,
    "procedural_prefab_binding_system": _procedural_prefab_binding_system_recipe,
    "scene_system_authoring_bundle": _scene_system_authoring_bundle_recipe,
    "behavior_logic_graph_bundle": _behavior_logic_graph_bundle_recipe,
    "world_streaming_runtime_partition_bundle": _world_streaming_runtime_partition_bundle_recipe,
    "save_state_persistence_bundle": _save_state_persistence_bundle_recipe,
    "quest_dialogue_authoring_bundle": _quest_dialogue_authoring_bundle_recipe,
    "camera_cinematic_direction_bundle": _camera_cinematic_direction_bundle_recipe,
    "procedural_audio_cue_bundle": _procedural_audio_cue_bundle_recipe,
    "localization_text_table_bundle": _localization_text_table_bundle_recipe,
    "accessibility_ux_affordance_bundle": _accessibility_ux_affordance_bundle_recipe,
    "economy_simulation_tuning_bundle": _economy_simulation_tuning_bundle_recipe,
    "multiplayer_session_replication_bundle": _multiplayer_session_replication_bundle_recipe,
    "cross_domain_composition_pack": _cross_domain_composition_pack_recipe,
    "style_stack_visual_band": _style_stack_visual_band_recipe,
    "typed_data_kernel_bundle": _typed_data_kernel_bundle_recipe,
    "attribute_surface_graph_program": _attribute_surface_graph_program_recipe,
    "vegetation_library_system": _vegetation_library_system_recipe,
    "terrain_heightfield_system": _terrain_heightfield_system_recipe,
    "wfc_tile_solver_system": _wfc_tile_solver_system_recipe,
    "cga_building_grammar_system": _cga_building_grammar_system_recipe,
    "volume_effects_data_system": _volume_effects_data_system_recipe,
    "instance_pattern_scatter_system": _instance_pattern_scatter_system_recipe,
    "f_rep_sdf_composition_system": _f_rep_sdf_composition_system_recipe,
    "subdivision_finishing_system": _subdivision_finishing_system_recipe,
    "humanoid_anatomy_preset_system": _humanoid_anatomy_preset_system_recipe,
    "face_sdf_cel_shading_system": _face_sdf_cel_shading_system_recipe,
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


_AUTHORED_SOURCE_NODE_FIELDS: tuple[tuple[tuple[str, ...], str | None], ...] = (
    (("intent", "parts"), None),
    (("intent", "materials"), "material_zone"),
    (("intent", "interactions"), "socket"),
    (("features", "allow"), None),
    (("assembly", "components"), None),
    (("assembly", "mechanisms"), "socket"),
    (("assembly", "traits"), None),
    (("surface", "materials"), "material_zone"),
    (("surface", "patterns"), "decal_zone"),
)

_MAX_AUTHORED_SOURCE_NODES = 32
_REPAIR_POLICY_HARDSURFACE_DEFAULT_FEATURES = (
    "edge_break",
    "trim_band",
    "fastener_grid",
    "panel_frame",
    "support_bracket",
)
_REPAIR_POLICY_ACTION_FEATURES: dict[str, tuple[str, ...]] = {
    "add_secondary_features": ("trim_band", "fastener_grid"),
    "restore_edge_treatment": ("edge_break",),
    "increase_panel_depth": ("panel_frame", "trim_band", "inset_panel"),
    "improve_attachment_integration": ("socket_point", "support_bracket", "mount_plate"),
    "refine_support_layout": ("support_bracket", "mount_plate"),
    "restore_hinge_alignment": ("hinge", "support_bracket"),
    "shroud_exposed_frame": ("tube_shroud",),
}
_REPAIR_POLICY_FEATURE_NODE_TYPES: dict[str, tuple[str, ...]] = {
    "edge_break": ("trim",),
    "trim_band": ("trim",),
    "fastener_grid": ("fastener",),
    "panel_frame": ("panel",),
    "inset_panel": ("inset",),
    "support_bracket": ("bracket",),
    "socket_point": ("socket",),
    "mount_plate": ("mount",),
    "hinge": ("hinge",),
    "tube_shroud": ("conduit",),
}


def _value_at_path(source: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _iter_text_fragments(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        fragment = value.strip()
        return (fragment,) if fragment else ()
    if isinstance(value, list):
        fragments: list[str] = []
        for entry in value:
            fragments.extend(_iter_text_fragments(entry))
        return tuple(fragments)
    if isinstance(value, dict):
        fragments = []
        for key in sorted(value.keys(), key=str):
            key_fragment = str(key).strip()
            if key_fragment:
                fragments.append(key_fragment)
            fragments.extend(_iter_text_fragments(value[key]))
        return tuple(fragments)
    return ()


def _slug_fragment(value: str) -> str:
    lowered = value.lower()
    chars: list[str] = []
    previous_was_separator = False
    for char in lowered:
        if char.isalnum():
            chars.append(char)
            previous_was_separator = False
            continue
        if not previous_was_separator:
            chars.append("_")
            previous_was_separator = True
    slug = "".join(chars).strip("_")
    return slug[:48] if slug else "value"


def _source_node_type(fragment: str, fallback_node_type: str | None) -> str:
    if fallback_node_type is not None:
        return fallback_node_type
    return _classify_part(fragment)


def _source_authored_graph_nodes(asset: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return semantic graph nodes implied by already-public authoring fields.

    These nodes are additive evidence only. They let ordinary source
    authoring fields influence family grammar coverage and future
    producers without adding grammar/schema surface or mutating the live
    construction graph.
    """
    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path, fallback_node_type in _AUTHORED_SOURCE_NODE_FIELDS:
        raw_value = _value_at_path(asset, path)
        source_path = ".".join(path)
        for fragment in _iter_text_fragments(raw_value):
            if len(nodes) >= _MAX_AUTHORED_SOURCE_NODES:
                return tuple(nodes)
            slug = _slug_fragment(fragment)
            node_id = f"source.{source_path}.{slug}"
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            node_type = _source_node_type(fragment, fallback_node_type)
            nodes.append(
                _node(
                    node_id,
                    node_type,
                    {
                        "source": "authored_source_field",
                        "source_path": source_path,
                        "source_value": fragment,
                    },
                )
            )
    return tuple(nodes)


def _repair_policy_slugs(value: Any) -> frozenset[str]:
    return frozenset(_slug_fragment(fragment) for fragment in _iter_text_fragments(value))


def _repair_policy_feature_kinds(asset: dict[str, Any]) -> tuple[str, ...]:
    policy = _as_dict(asset.get("repair_policy"))
    if not policy:
        return ()
    request_slugs = set(_repair_policy_slugs(policy.get("use")))
    request_slugs.update(_repair_policy_slugs(policy.get("mode")))
    request_slugs.update(_repair_policy_slugs(policy.get("allow")))
    deny_slugs = _repair_policy_slugs(policy.get("deny"))
    selected: list[str] = []
    seen: set[str] = set()

    def denies(kind: str, action: str = "") -> bool:
        kind_slug = _slug_fragment(kind)
        action_slug = _slug_fragment(action) if action else ""
        if kind_slug in deny_slugs or (action_slug and action_slug in deny_slugs):
            return True
        deny_tokens = {token for slug in deny_slugs for token in slug.split("_") if token}
        kind_tokens = {token for token in kind_slug.split("_") if token}
        action_tokens = {token for token in action_slug.split("_") if token}
        return bool((kind_tokens and kind_tokens & deny_tokens) or (action_tokens and action_tokens & deny_tokens))

    def add_kind(kind: str, action: str = "") -> None:
        kind_slug = _slug_fragment(kind)
        if kind_slug not in _REPAIR_POLICY_FEATURE_NODE_TYPES or kind_slug in seen:
            return
        if denies(kind_slug, action):
            return
        seen.add(kind_slug)
        selected.append(kind_slug)

    if request_slugs & {
        "hero_hardsurface_repair",
        "hero_hard_surface_repair",
        "hardsurface_repair",
        "hard_surface_repair",
    }:
        for kind in _REPAIR_POLICY_HARDSURFACE_DEFAULT_FEATURES:
            add_kind(kind, "hero_hardsurface_repair")

    for action_slug in sorted(request_slugs):
        for kind in _REPAIR_POLICY_ACTION_FEATURES.get(action_slug, ()):
            add_kind(kind, action_slug)
        if action_slug in _REPAIR_POLICY_FEATURE_NODE_TYPES:
            add_kind(action_slug, action_slug)
    return tuple(selected)


def _source_repair_policy_graph_nodes(asset: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for kind in _repair_policy_feature_kinds(asset):
        for node_type in _REPAIR_POLICY_FEATURE_NODE_TYPES.get(kind, ()):
            if len(nodes) >= _MAX_AUTHORED_SOURCE_NODES:
                return tuple(nodes)
            node_id = f"source.repair_policy.{kind}.{node_type}"
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            nodes.append(
                _node(
                    node_id,
                    node_type,
                    {
                        "source": "repair_policy",
                        "source_path": "repair_policy",
                        "repair_policy_feature": kind,
                    },
                )
            )
    return tuple(nodes)


def _resolve_brief(runtime: dict[str, Any]) -> dict[str, Any]:
    """Return the design-brief dict published by Phase 2, or empty."""
    design_brief = _as_dict(runtime.get("design_brief"))
    return _as_dict(design_brief.get("brief"))


def _resolve_family(brief: dict[str, Any]) -> str:
    """Return the family token from the (already-resolved) design brief,
    or ``"generic"``."""
    family = brief.get("family")
    if isinstance(family, str) and family:
        return family
    return "generic"


def _resolve_parts(asset: dict[str, Any]) -> tuple[str, ...]:
    """Return the parts list from ``asset["intent"]["parts"]`` as a tuple."""
    intent = _as_dict(asset.get("intent"))
    raw_parts = _as_list(intent.get("parts"))
    return tuple(part for part in raw_parts if isinstance(part, str))


def _resolve_graph_nodes(runtime: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return ``runtime["construction_graph"]["nodes"]`` as a tuple of dicts."""
    construction_graph = _as_dict(runtime.get("construction_graph"))
    raw_nodes = construction_graph.get("nodes")
    if not isinstance(raw_nodes, list):
        return ()
    return tuple(node for node in raw_nodes if isinstance(node, dict))


def _resolve_asset_name(asset: dict[str, Any], brief: dict[str, Any]) -> str:
    """Return the asset name, falling back through the (already-resolved)
    design brief."""
    name = asset.get("name")
    if isinstance(name, str) and name:
        return name
    brief_name = brief.get("asset_name")
    if isinstance(brief_name, str) and brief_name:
        return brief_name
    return "unnamed_asset"


_OP_FAMILY_BUCKETS: tuple[tuple[frozenset[str], str], ...] = (
    (SOLID_OPS, "solid_ops"),
    (BOOLEAN_OPS, "boolean_ops"),
    (EDGE_OPS, "edge_ops"),
    (SOP_OPS, "sop_ops"),
    (REPETITION_OPS, "repetition_ops"),
    (INTEGRATION_OPS, "integration_ops"),
    (WEAR_OPS, "wear_ops"),
)


_OP_TO_FAMILY_BUCKET: dict[str, str] = {
    op_name: bucket for family, bucket in _OP_FAMILY_BUCKETS for op_name in family
}


def _summarise_program(program: ShapeProgram) -> dict[str, Any]:
    """Return ``shape_program_summary`` for the validator payload.

    Counts ops by Phase 5 family (single dict lookup per op) and by
    triggering grammar requirement (extracted from the leading
    ``<requirement>.`` token of each op's ``purpose`` string).
    """
    family_counts: dict[str, int] = {bucket: 0 for _, bucket in _OP_FAMILY_BUCKETS}
    requirement_counts: dict[str, int] = {}
    for op in program.ops:
        bucket = _OP_TO_FAMILY_BUCKET.get(op.op)
        if bucket is not None:
            family_counts[bucket] += 1
        if op.purpose and "." in op.purpose:
            requirement_token = op.purpose.split(".", 1)[0]
            requirement_counts[requirement_token] = (
                requirement_counts.get(requirement_token, 0) + 1
            )
    return {
        "op_count": len(program.ops),
        "ops_by_family": family_counts,
        "ops_by_requirement": dict(sorted(requirement_counts.items())),
    }


def _runtime_config_for_geometry_kernel(runtime: dict[str, Any]) -> dict[str, Any] | None:
    runtime_config = _as_dict(runtime.get("_runtime_config"))
    if runtime_config:
        return runtime_config
    if isinstance(runtime.get("runtime"), dict):
        return runtime
    return None


def _resolve_v1_lowering_geometry_kernel(runtime: dict[str, Any]) -> tuple[Any | None, dict[str, Any]]:
    runtime_config = _runtime_config_for_geometry_kernel(runtime)
    if runtime_config is None:
        return None, {
            "geometry_kernel_selection": "not_configured",
            "geometry_kernel": None,
        }
    # The live validate stage is informational for grammar lowering. Replaying
    # the geometry kernel here duplicates the shape-stage kernel work and can
    # dominate end-to-end builds for dense assets. Keep lowering semantic and
    # report the skipped replay honestly; direct lower_to_v1(...) callers can
    # still pass a geometry kernel when materialized adapter output is desired.
    return None, {
        "geometry_kernel_selection": "skipped_validator_kernel_replay",
        "geometry_kernel": None,
        "geometry_kernel_materialization_skipped": True,
    }


def _record_has_kernel_program(record: dict[str, Any]) -> bool:
    tags = record.get("tags")
    if isinstance(tags, list) and any("kernel_program" in str(tag) for tag in tags):
        return True
    for value in record.values():
        if isinstance(value, dict) and isinstance(value.get("kernel_program"), dict):
            return True
    return False


def _kernel_program_record_metrics(records: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    kernel_records = tuple(record for record in records if _record_has_kernel_program(record))
    face_count = 0
    for record in kernel_records:
        faces = record.get("mesh_faces")
        if isinstance(faces, list):
            face_count += len(faces)
    return {
        "kernel_program_record_count": len(kernel_records),
        "kernel_program_face_count": face_count,
    }


def _select_recipe_result(
    family: str,
    asset_name: str,
    brief: dict[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> RecipeResult:
    """Run the matching recipe, falling back to an empty program."""
    recipe = _RECIPES.get(family)
    if recipe is None:
        return _empty_recipe(family=family, asset_name=asset_name)
    result = recipe(brief=brief, parts=parts, graph_nodes=graph_nodes)
    if result.shape_program.asset_name == asset_name:
        return result
    rebuilt_program = ShapeProgram(
        version=result.shape_program.version,
        asset_name=asset_name,
        family=result.shape_program.family,
        ops=result.shape_program.ops,
    )
    return RecipeResult(
        family=result.family,
        shape_program=rebuilt_program,
        synthesized_graph_nodes=result.synthesized_graph_nodes,
    )


def _merge_synthesized_nodes(
    *node_groups: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for nodes in node_groups:
        for node in nodes:
            node_id = node.get("node_id") if isinstance(node, dict) else None
            if isinstance(node_id, str) and node_id:
                if node_id in seen_ids:
                    continue
                seen_ids.add(node_id)
            merged.append(node)
    return tuple(merged)


def evaluate_grammar_lowering(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive grammar-lowering payload for the validate stage.

    Args:
        asset: normalized asset dict. May omit ``intent`` or ``parts``;
            the function tolerates partial/empty input.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["design_brief"]["brief"]["family"]`` (Phase 2),
            ``runtime["construction_graph"]["nodes"]`` (Phase 4), and the
            asset's parts list. The recipe is currently a function of
            family alone; the parts and graph parameters are reserved
            for future variant recipes.

    Returns:
        Additive payload with ``version`` (``"grammar_lowering_v1"``),
        ``family``, ``shape_program`` (Phase 5 ShapeProgram dict),
        ``shape_program_summary`` (op_count + ops_by_family +
        ops_by_requirement), ``synthesized_graph_nodes`` (list of
        node-dicts compatible with Phase 4's construction graph),
        ``synthesized_node_count``, and ``v1_lowering`` (nested
        v2-to-v1 adapter result with ``v1_record_count``,
        ``diagnostics``, ``unsupported_ops``). No top-level
        ``diagnostics`` key — like Phases 1 through 5, this validator
        is informational only and never blocks certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    brief = _resolve_brief(safe_runtime)
    parts = _resolve_parts(safe_asset)
    graph_nodes = _resolve_graph_nodes(safe_runtime)
    family = _resolve_family(brief)
    asset_name = _resolve_asset_name(safe_asset, brief)
    result = _select_recipe_result(
        family=family,
        asset_name=asset_name,
        brief=brief,
        parts=parts,
        graph_nodes=graph_nodes,
    )
    program = result.shape_program
    synthesized_nodes = _merge_synthesized_nodes(
        result.synthesized_graph_nodes,
        _source_authored_graph_nodes(safe_asset),
        _source_repair_policy_graph_nodes(safe_asset),
    )
    geometry_kernel, geometry_kernel_report = _resolve_v1_lowering_geometry_kernel(safe_runtime)
    adapter = lower_to_v1(program, geometry_kernel=geometry_kernel)
    kernel_metrics = _kernel_program_record_metrics(adapter.v1_records)
    return {
        "version": GRAMMAR_LOWERING_VERSION,
        "family": result.family,
        "shape_program": program.to_dict(),
        "shape_program_summary": _summarise_program(program),
        "synthesized_graph_nodes": [dict(node) for node in synthesized_nodes],
        "synthesized_node_count": len(synthesized_nodes),
        "v1_lowering": {
            "v1_record_count": len(adapter.v1_records),
            **geometry_kernel_report,
            **kernel_metrics,
            "diagnostics": [dict(item) for item in adapter.diagnostics],
            "unsupported_ops": list(adapter.unsupported_ops),
        },
    }


# Anchors the synthesized-node-types contract: every recipe node must use
# a ``node_type`` from Phase 4's NODE_TYPES frozenset so a future opt-in
# merger can drop the synthesized nodes into the live construction graph
# without translation.
_SYNTHESIZED_NODE_TYPES_USED: frozenset[str] = frozenset(
    {
        "primary_volume",
        "frame",
        "panel",
        "guard",
        "inset",
        "handle",
        "hinge",
        "mount",
        "rail",
        "socket",
        "trim",
        "fastener",
        "decal_zone",
        "wear_zone",
        "material_zone",
    }
)


def _verify_node_type_contract() -> None:
    """Assert at import time that recipe node types are members of NODE_TYPES."""
    unknown = _SYNTHESIZED_NODE_TYPES_USED - NODE_TYPES
    if unknown:
        raise AssertionError(
            f"grammar_lowering recipe uses node types not in construction_graph.NODE_TYPES: "
            f"{sorted(unknown)}"
        )


_verify_node_type_contract()
