"""Phase 3 deterministic ``FamilyGrammar`` IR.

Adds an internal ``FamilyGrammar`` representation that captures the
required, recommended, and optional construction concepts every hero
asset family must contain. The MVP started with ``industrial_crate`` and
now also covers the inferred ``mechanical_door``, ``service_cabinet``,
``weapon_prop``, ``vehicle_prop``, ``furniture_prop``, ``natural_form``,
``environment_architecture``, ``lighting_prop``, ``machine_console``,
``portal_relic``, ``tool_prop``, ``modular_kit``, and
``character_creature``, ``set_dressing_prop``, and
``surface_material_sample``, ``terrain_vegetation_variant``, and
``environment_effect``, ``settlement_district``, and
``gameplay_object``, ``encounter_flow``, and
``inventory_economy_object``, ``rig_animation_proxy``, and
``stateful_destructible_prop``, ``cloth_attachment_form``, and
``domain_kit_bundle``, ``world_system_assembly``, and
``simulation_environment_system``, ``authored_multi_asset_bundle``, and
``live_procedural_runtime_bundle``, ``cross_domain_composition_pack``, and
``style_stack_visual_band``, ``typed_data_kernel_bundle``, and
``attribute_surface_graph_program``, ``vegetation_library_system``, and
``terrain_heightfield_system``, ``wfc_tile_solver_system``, and
``cga_building_grammar_system``, ``volume_effects_data_system``, and
``instance_pattern_scatter_system``, ``f_rep_sdf_composition_system``, and
``subdivision_finishing_system``, ``humanoid_anatomy_preset_system``, and
``face_sdf_cel_shading_system``, ``rig_component_library_system``, and
``morph_target_database_system``, ``animation_library_binding_system``, and
``retargeting_pack_system``, ``character_equipment_binding_system``, and
``gameplay_animation_controller_system``, ``procedural_facial_rig_pack_system``,
``hair_program_system``, ``cloth_fabric_simulation_program_system``, and
``fluid_forward_volume_program_system``, ``construction_grammar_kit_system``,
``creature_appendage_program_system``, ``body_part_procedural_library_system``,
``material_primitive_library_system``, ``engine_facing_runtime_bundle_system``,
``procedural_prefab_binding_system``, ``scene_system_authoring_bundle``, and
``behavior_logic_graph_bundle``, ``world_streaming_runtime_partition_bundle``,
``save_state_persistence_bundle``, ``quest_dialogue_authoring_bundle``, and
``camera_cinematic_direction_bundle``, ``procedural_audio_cue_bundle``, and
``localization_text_table_bundle``, ``accessibility_ux_affordance_bundle``,
``economy_simulation_tuning_bundle``, and
``multiplayer_session_replication_bundle`` families, plus a ``generic`` fallback
grammar so unknown families degrade gracefully.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 7.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 3.
Per-requirement reference: ``docs/asset-quality/family-grammar-v1.md``.

Detection model
---------------

Phase 3 detection used parts-list substring matching only. Phase 4
extends the model with the semantic construction graph: each
requirement now also carries a ``graph_node_types`` allowlist of node
types from ``lathe.asset_quality.construction_graph.NODE_TYPES``.

Detection precedence is:

1. If any entry in ``asset["intent"]["parts"]`` contains one of the
   requirement's ``detection_signals`` (case-insensitive), the
   requirement is ``"satisfied"`` and ``evidence`` includes
   ``matched_parts``.
2. Otherwise, if ``runtime["construction_graph"]["nodes"]`` contains a
   node whose ``node_type`` is in the requirement's
   ``graph_node_types`` allowlist, the requirement is ``"partial"``
   and ``evidence`` additionally includes ``matched_graph_nodes``.
3. Otherwise, the requirement is ``"missing"``.

Parts evidence dominates because parts represent explicit authoring
intent while graph evidence is derived. ``"not_applicable"`` is still
reserved for forward phases (e.g. a mechanical-door grammar might mark
``foot_rails`` as not-applicable when the brief disables them).
Backward compatibility: when ``runtime["construction_graph"]`` is
absent or malformed, the graph-elevation path is skipped and Phase 3
behaviour is preserved exactly.

Generic fallback
----------------

Unknown families fall through to the ``generic`` grammar, which has an
empty ``requirements`` tuple. ``coverage`` defaults to ``1.0`` (no
requirements means trivially satisfied), the per-status counts are
zero, and the recommendations array is empty. Phase 4+ will introduce
graph-derived requirements for the generic family; until then, the
fallback is informational only and never warns.

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``design_brief`` and before
``quality_diagnostics`` so that the family lookup uses the brief's
inferred family and the additive ``family_grammar_coverage`` metric in
``quality_diagnostics`` can read this validator's evidence.

Output additively appears under the top-level ``family_grammar`` key of
the validate-stage report. Existing report fields are preserved and the
validator never produces blocking diagnostics — like Phases 1 and 2,
this layer is informational evidence for downstream classifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FAMILY_GRAMMAR_VERSION = "family_grammar_v1"


_SEVERITY_REQUIRED = "required"
_SEVERITY_RECOMMENDED = "recommended"
_SEVERITY_OPTIONAL = "optional"

_STATUS_SATISFIED = "satisfied"
_STATUS_PARTIAL = "partial"
_STATUS_MISSING = "missing"
_STATUS_NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class FamilyRequirement:
    """One construction concept the family grammar expects.

    ``detection_signals`` is a tuple of lowercase substring tokens the
    MVP matches against ``asset["intent"]["parts"]`` (case-insensitive).
    Phase 4 extends detection to also consume the semantic construction
    graph (see ``graph_node_types``); Phase 6+ will lower these into
    ShapeIR v2 operations. The field name is intentionally generic so
    the same dataclass survives those transitions.

    ``graph_node_types`` is a tuple of construction-graph node-type
    tokens (see ``lathe.asset_quality.construction_graph.NODE_TYPES``).
    When parts-list detection misses but the construction graph contains
    a node whose ``node_type`` matches any token here, the requirement
    is elevated from ``"missing"`` to ``"partial"`` (Phase 4 semantics).
    Default is the empty tuple, which preserves Phase 3 behaviour for
    requirements that opt out of graph-based elevation.

    ``recommendation_template`` is the human-readable repair string
    surfaced in ``FamilyGrammarResult.recommendations`` when the
    requirement's status is ``"missing"`` or ``"partial"``. Co-locating
    the template with the requirement (rather than a parallel dict)
    keeps each requirement a single source of truth.
    """

    name: str
    description: str
    severity: str
    detection_signals: tuple[str, ...]
    recommendation_template: str
    graph_node_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class FamilyGrammar:
    """A frozen registry of requirements for one asset family."""

    family: str
    version: str
    requirements: tuple[FamilyRequirement, ...]


@dataclass(frozen=True)
class FamilyGrammarResult:
    """The outcome of evaluating one ``FamilyGrammar`` against an asset.

    ``coverage`` is the weighted satisfaction in ``[0.0, 1.0]``; see
    :func:`_compute_coverage` for the exact formula. ``recommendations``
    contains one human-readable repair suggestion per missing or partial
    requirement (in declaration order).
    """

    family: str
    version: str
    requirement_results: tuple[dict[str, Any], ...]
    coverage: float
    satisfied_count: int
    partial_count: int
    missing_count: int
    recommendations: tuple[str, ...]


_INDUSTRIAL_CRATE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="body_shell",
        description=(
            "A primary box-shell body forms the structural volume of the "
            "crate."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body",),
        recommendation_template=(
            "Add a primary body shell: the industrial crate grammar requires "
            "a structural box volume the rest of the construction hangs from."
        ),
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="lid_seam",
        description=(
            "A visible lid break wraps the top of the body, distinguishing "
            "the lid from the shell."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("lid",),
        recommendation_template=(
            "Add a lid seam: the industrial crate grammar requires a visible "
            "lid break wrapping the top of the body."
        ),
        graph_node_types=("panel",),
    ),
    FamilyRequirement(
        name="corner_guards",
        description=(
            "Reinforcement corner guards wrap the eight body corners and "
            "give the crate its industrial silhouette."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("corner_guard", "corner", "guard"),
        recommendation_template=(
            "Add corner guards: the industrial crate grammar requires "
            "reinforcement corners on the eight body corners."
        ),
        graph_node_types=("guard",),
    ),
    FamilyRequirement(
        name="latch_or_latch_plate",
        description=(
            "A latch or latch plate sits at the lid/body seam and grants "
            "the crate a clear front face."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("latch",),
        recommendation_template=(
            "Add a latch or latch plate at the lid/body seam so the crate has "
            "a clear front face."
        ),
        graph_node_types=("inset",),
    ),
    FamilyRequirement(
        name="recessed_or_bracketed_handles",
        description=(
            "Handles are seated into recessed wells or bracket plates "
            "rather than glued onto the shell as separate primitives."
        ),
        severity=_SEVERITY_REQUIRED,
        detection_signals=("handle",),
        recommendation_template=(
            "Seat handles into recessed wells or bracket plates rather than "
            "placing them as floating primitives on the shell."
        ),
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="foot_rails_or_feet",
        description=(
            "Foot rails or discrete feet lift the body off the ground "
            "plane and read as functional."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("foot", "feet", "rail"),
        recommendation_template=(
            "Add foot rails or discrete feet to lift the body off the ground "
            "plane."
        ),
        graph_node_types=("mount", "rail"),
    ),
    FamilyRequirement(
        name="trim_bands",
        description=(
            "Horizontal or vertical trim bands break up the body shell "
            "and add medium-scale construction hierarchy."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("trim", "band"),
        recommendation_template=(
            "Add horizontal or vertical trim bands to break up the body shell "
            "with medium-scale construction hierarchy."
        ),
        graph_node_types=("trim",),
    ),
    FamilyRequirement(
        name="fasteners",
        description=(
            "Fasteners (bolts, rivets, screws) are visible at structural "
            "junctions and reinforce the industrial brief."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "rivet", "screw"),
        recommendation_template=(
            "Add visible fasteners (bolts, rivets, or screws) at structural "
            "junctions to reinforce the industrial brief."
        ),
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="warning_or_decal_zones",
        description=(
            "Warning text, stencils, or decal zones provide surface "
            "storytelling on the body."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("warning", "decal", "label"),
        recommendation_template=(
            "Add warning text, stencils, or decal zones to provide surface "
            "storytelling on the body."
        ),
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="edge_wear_masks",
        description=(
            "Edge wear masks expose paint chips and metal at high-traffic "
            "edges, breaking the debug-material look."
        ),
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear"),
        recommendation_template=(
            "Add edge wear masks so paint chips and metal show at high-traffic "
            "edges instead of a uniform debug-material look."
        ),
        graph_node_types=("wear_zone",),
    ),
)


_MECHANICAL_DOOR_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="door_frame",
        description="A rigid outer frame anchors the access door in the wall.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("frame", "jamb"),
        recommendation_template=(
            "Add an outer door frame or jamb so the mechanical door reads as "
            "installed infrastructure."
        ),
        graph_node_types=("frame",),
    ),
    FamilyRequirement(
        name="inset_door_leaf",
        description="A recessed door leaf sits inside the frame.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("leaf", "panel", "door"),
        recommendation_template=(
            "Add an inset door leaf panel inside the frame so the access door "
            "has a clear operable slab."
        ),
        graph_node_types=("panel",),
    ),
    FamilyRequirement(
        name="hinge_stack",
        description="A visible hinge stack communicates swing mechanics.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("hinge",),
        recommendation_template=(
            "Add a visible hinge stack along one side so the door's movement "
            "mechanism is legible."
        ),
        graph_node_types=("hinge",),
    ),
    FamilyRequirement(
        name="lock_or_actuator",
        description="A lock, actuator, or access plate marks interaction.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("lock", "actuator", "latch", "access"),
        recommendation_template=(
            "Add a lock, actuator, or access plate so the door has an obvious "
            "interaction/control zone."
        ),
        graph_node_types=("inset", "mount"),
    ),
    FamilyRequirement(
        name="guide_or_threshold_rails",
        description="Guide rails or a threshold ground the door mechanically.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("rail", "threshold", "track"),
        recommendation_template=(
            "Add guide rails or a threshold rail to ground the door in a "
            "mechanical frame."
        ),
        graph_node_types=("rail",),
    ),
    FamilyRequirement(
        name="panel_grooves",
        description="Panel grooves break up the door leaf surface.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("groove", "rib", "trim"),
        recommendation_template=(
            "Add panel grooves, ribs, or trim to break up the door leaf surface."
        ),
        graph_node_types=("trim",),
    ),
    FamilyRequirement(
        name="access_handle",
        description="A handle, pull, or grab point gives human scale.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("handle", "pull", "grab"),
        recommendation_template=(
            "Add a handle, pull, or grab point to give the mechanical door "
            "human-scale affordance."
        ),
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="fasteners",
        description="Bolts or rivets tie the frame and hinges together.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "rivet", "screw"),
        recommendation_template=(
            "Add visible fasteners at frame and hinge junctions."
        ),
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="warning_or_decal_zones",
        description="Door signage or hazard decals clarify use and scale.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("warning", "decal", "label", "signage"),
        recommendation_template=(
            "Add warning labels or decal zones to clarify door use and scale."
        ),
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="edge_wear_masks",
        description="Wear masks mark rubbed hinges, handle zones, and thresholds.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear"),
        recommendation_template=(
            "Add edge wear masks around hinges, handles, and thresholds."
        ),
        graph_node_types=("wear_zone",),
    ),
)


_SERVICE_CABINET_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="cabinet_shell",
        description="A compact cabinet shell forms the mounted utility volume.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body", "shell", "case", "cabinet"),
        recommendation_template=(
            "Add a compact cabinet shell so the service cabinet has a clear "
            "utility volume."
        ),
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="front_door_panel",
        description="A front access panel gives the cabinet a serviceable face.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("door", "panel", "front"),
        recommendation_template=(
            "Add a front access panel so the service cabinet has a serviceable face."
        ),
        graph_node_types=("panel",),
    ),
    FamilyRequirement(
        name="hinge_line",
        description="A hinge line or hinge barrels define how the panel opens.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("hinge",),
        recommendation_template=(
            "Add a hinge line or hinge barrels to define how the cabinet opens."
        ),
        graph_node_types=("hinge",),
    ),
    FamilyRequirement(
        name="pull_handle",
        description="A pull handle marks the user interaction point.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("handle", "pull", "grab"),
        recommendation_template=(
            "Add a pull handle so the cabinet has an obvious interaction point."
        ),
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="latch_or_lock_plate",
        description="A latch or lock plate reinforces service access.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("latch", "lock", "access"),
        recommendation_template=(
            "Add a latch or lock plate to reinforce the cabinet's service access."
        ),
        graph_node_types=("inset",),
    ),
    FamilyRequirement(
        name="vent_slats",
        description="Vent slats communicate utility/electrical function.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("vent", "slat", "grille"),
        recommendation_template=(
            "Add vent slats or a grille so the cabinet reads as a utility object."
        ),
        graph_node_types=("trim",),
    ),
    FamilyRequirement(
        name="mounting_brackets",
        description="Mounting brackets show how the cabinet attaches to a wall.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("mount", "bracket"),
        recommendation_template=(
            "Add mounting brackets or back plates to show wall attachment."
        ),
        graph_node_types=("mount",),
    ),
    FamilyRequirement(
        name="fasteners",
        description="Fasteners bind hinges, brackets, and panel hardware.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "rivet", "screw"),
        recommendation_template=(
            "Add visible fasteners at hinge, bracket, and panel hardware points."
        ),
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="label_or_decal_zone",
        description="A label zone communicates service identity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("label", "decal", "warning", "stencil"),
        recommendation_template=(
            "Add a label, stencil, or decal zone to communicate service identity."
        ),
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="edge_wear_masks",
        description="Wear masks mark handled edges and service-panel corners.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear"),
        recommendation_template=(
            "Add edge wear masks around handled edges and service-panel corners."
        ),
        graph_node_types=("wear_zone",),
    ),
)


_WEAPON_PROP_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="primary_weapon_body",
        description="A readable primary receiver, blade, or tool body establishes the weapon silhouette.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body", "receiver", "blade", "head"),
        recommendation_template=(
            "Add a readable primary weapon body, receiver, blade, or head so the prop has a clear silhouette."
        ),
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="grip_or_handle",
        description="A grip or handle defines how the weapon is held.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("grip", "handle"),
        recommendation_template="Add a grip or handle so the weapon has a clear held affordance.",
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="guard_or_hand_stop",
        description="A guard, hand stop, or collar separates the user contact zone from the active end.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("guard", "stop", "collar"),
        recommendation_template=(
            "Add a guard, hand stop, or collar to separate the grip from the active end."
        ),
        graph_node_types=("guard",),
    ),
    FamilyRequirement(
        name="active_edge_or_barrel",
        description="A blade edge, muzzle, emitter, or barrel states the functional direction.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("edge", "barrel", "muzzle", "emitter", "tip"),
        recommendation_template=(
            "Add a blade edge, muzzle, emitter, or barrel so the weapon has a clear functional direction."
        ),
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="centerline_detail",
        description="A ridge, fuller, rail, or sight line emphasizes the weapon axis.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("ridge", "fuller", "rail", "sight"),
        recommendation_template="Add centerline detail such as a ridge, fuller, rail, or sight line.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="pommel_or_end_cap",
        description="A pommel, end cap, or butt cap finishes the held end.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("pommel", "cap", "butt"),
        recommendation_template="Add a pommel, end cap, or butt cap to finish the held end.",
        graph_node_types=("mount",),
    ),
    FamilyRequirement(
        name="socket_or_hardpoint",
        description="Sockets or hardpoints support modular attachments.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("socket", "hardpoint", "mount"),
        recommendation_template="Add sockets or hardpoints for modular attachment readability.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="fasteners",
        description="Fasteners connect guards, rails, plates, and fittings.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "rivet", "screw"),
        recommendation_template="Add fasteners where guards, rails, plates, and fittings attach.",
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="marking_or_decal_zone",
        description="Marking zones carry faction, serial, or safety identity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("marking", "decal", "label", "serial"),
        recommendation_template="Add a marking, serial, or decal zone for identity.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="edge_wear_masks",
        description="Wear masks mark contact edges, grips, muzzles, and guards.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear"),
        recommendation_template="Add wear masks around contact edges, grips, muzzles, and guards.",
        graph_node_types=("wear_zone",),
    ),
)


_VEHICLE_PROP_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="primary_chassis_or_hull",
        description="A chassis or hull establishes transport mass and direction.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("chassis", "hull", "body", "frame"),
        recommendation_template="Add a primary chassis or hull to establish the vehicle mass.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="cabin_or_control_zone",
        description="A cabin, cockpit, or control zone communicates scale and use.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("cabin", "cockpit", "control", "crew"),
        recommendation_template="Add a cabin, cockpit, or control zone to communicate scale and use.",
        graph_node_types=("panel",),
    ),
    FamilyRequirement(
        name="motion_system",
        description="Wheels, pontoons, tracks, rotors, or thrusters show how the vehicle moves.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("wheel", "pontoon", "track", "rotor", "thruster", "sail"),
        recommendation_template=(
            "Add wheels, pontoons, tracks, rotors, thrusters, or sails so the motion system is legible."
        ),
        graph_node_types=("rail", "mount"),
    ),
    FamilyRequirement(
        name="front_back_orientation",
        description="A bow, nose, grille, tail, or rudder clarifies travel direction.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("front", "nose", "bow", "tail", "rudder", "grille"),
        recommendation_template="Add front/back orientation cues such as a bow, nose, grille, tail, or rudder.",
        graph_node_types=("trim", "panel"),
    ),
    FamilyRequirement(
        name="cargo_or_payload_zone",
        description="Cargo bays or payload zones provide practical vehicle purpose.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cargo", "payload", "hold", "bay"),
        recommendation_template="Add a cargo bay, hold, or payload zone to clarify vehicle purpose.",
        graph_node_types=("panel", "inset"),
    ),
    FamilyRequirement(
        name="access_steps_or_handles",
        description="Steps, rails, or handles provide human-scale access.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("step", "ladder", "handle", "rail"),
        recommendation_template="Add steps, rails, ladders, or handles for human-scale access.",
        graph_node_types=("handle", "rail"),
    ),
    FamilyRequirement(
        name="lights_or_sensors",
        description="Lights or sensors communicate navigation and control.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("light", "sensor", "lamp", "beacon"),
        recommendation_template="Add lights, sensors, lamps, or beacons for navigation/control identity.",
        graph_node_types=("mount", "decal_zone"),
    ),
    FamilyRequirement(
        name="mechanical_fasteners",
        description="Fasteners connect panels, suspension, thrusters, and access hardware.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "rivet", "screw"),
        recommendation_template="Add fasteners at panels, suspension, thrusters, and access hardware.",
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="marking_or_decal_zone",
        description="Marking zones carry fleet, cargo, or hazard identity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("marking", "decal", "label", "warning"),
        recommendation_template="Add markings, fleet labels, cargo labels, or warning decal zones.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="edge_wear_masks",
        description="Wear masks mark access edges, hull/chassis corners, and motion-system contact.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear"),
        recommendation_template="Add wear masks around access edges, chassis/hull corners, and motion contact points.",
        graph_node_types=("wear_zone",),
    ),
)


_FURNITURE_PROP_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="primary_contact_surface",
        description="A seat, tabletop, shelf, mattress, or bench surface establishes use.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("seat", "top", "surface", "shelf", "mattress", "bench"),
        recommendation_template="Add a primary contact surface such as a seat, tabletop, shelf, or bench.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="support_structure",
        description="Legs, side panels, or supports hold the surface at usable height.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("leg", "support", "side", "base"),
        recommendation_template="Add legs, side panels, or supports so the furniture reads as usable.",
        graph_node_types=("rail", "mount"),
    ),
    FamilyRequirement(
        name="back_or_storage_volume",
        description="A back, drawer, cabinet bay, or storage shelf gives function beyond a slab.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("back", "drawer", "cabinet", "storage", "bay"),
        recommendation_template="Add a back, drawer, cabinet bay, or storage volume.",
        graph_node_types=("panel", "inset"),
    ),
    FamilyRequirement(
        name="trim_or_edge_band",
        description="Trim or edge bands clarify scale and construction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("trim", "band", "edge", "lip"),
        recommendation_template="Add trim or edge bands to clarify scale and construction.",
        graph_node_types=("trim",),
    ),
    FamilyRequirement(
        name="handle_or_pull",
        description="Handles or pulls mark drawer/cabinet interaction points.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("handle", "pull", "knob"),
        recommendation_template="Add handles, pulls, or knobs for interaction points.",
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="fasteners_or_joinery",
        description="Fasteners or joinery details explain how pieces connect.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "peg", "joinery", "rivet"),
        recommendation_template="Add fasteners, pegs, or joinery details at furniture connections.",
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="cushion_or_soft_volume",
        description="A cushion or softened volume adds ergonomic read where appropriate.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cushion", "pillow", "soft", "pad"),
        recommendation_template="Add a cushion, pad, or softened volume where the furniture needs comfort.",
        graph_node_types=("panel", "primary_volume"),
    ),
    FamilyRequirement(
        name="floor_contact_or_feet",
        description="Feet or floor-contact pads ground the furniture.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("foot", "feet", "glide", "pad"),
        recommendation_template="Add feet, glides, or floor-contact pads to ground the furniture.",
        graph_node_types=("mount",),
    ),
    FamilyRequirement(
        name="label_or_decal_zone",
        description="A small label or maker mark can identify the object.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("label", "decal", "marking"),
        recommendation_template="Add a small label, maker mark, or decal zone.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="edge_wear_masks",
        description="Wear masks mark handled edges, contact surfaces, and feet.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear"),
        recommendation_template="Add wear masks around handled edges, contact surfaces, and feet.",
        graph_node_types=("wear_zone",),
    ),
)


_NATURAL_FORM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="organic_primary_mass",
        description="An asymmetric terrain, rock, trunk, or growth mass establishes the natural read.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("terrain", "rock", "trunk", "mass", "ground"),
        recommendation_template="Add an asymmetric terrain, rock, trunk, or growth mass.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="swept_growth_or_rooting",
        description="Roots, branches, vines, stems, or runners express organic growth direction.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("root", "branch", "vine", "stem", "runner"),
        recommendation_template="Add roots, branches, vines, stems, or runners for organic growth direction.",
        graph_node_types=("rail",),
    ),
    FamilyRequirement(
        name="clustered_secondary_forms",
        description="Secondary stones, leaves, caps, or growth clusters break up the primary mass.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("cluster", "leaf", "cap", "stone", "mushroom"),
        recommendation_template="Add clustered secondary forms such as stones, leaves, caps, or growth clusters.",
        graph_node_types=("mount", "panel"),
    ),
    FamilyRequirement(
        name="surface_strata_or_bark",
        description="Strata, bark ridges, rings, or contour bands create natural detail hierarchy.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("strata", "bark", "ridge", "ring", "contour"),
        recommendation_template="Add strata, bark ridges, rings, or contour bands.",
        graph_node_types=("trim",),
    ),
    FamilyRequirement(
        name="ground_contact_transition",
        description="A skirt, roots, talus, or soil transition grounds the natural form.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("soil", "talus", "skirt", "ground", "base"),
        recommendation_template="Add a soil, talus, root, or ground-contact transition.",
        graph_node_types=("mount", "primary_volume"),
    ),
    FamilyRequirement(
        name="asymmetric_silhouette_breaks",
        description="Off-axis protrusions prevent a mechanical silhouette.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("asymmetry", "lobe", "protrusion", "lean"),
        recommendation_template="Add asymmetric lobes or protrusions to avoid a mechanical silhouette.",
        graph_node_types=("panel", "mount"),
    ),
    FamilyRequirement(
        name="small_detail_scatter",
        description="Pebbles, leaves, sprouts, or detail scatter adds scale.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("pebble", "sprout", "leaf", "scatter"),
        recommendation_template="Add pebbles, leaves, sprouts, or small detail scatter for scale.",
        graph_node_types=("fastener", "mount"),
    ),
    FamilyRequirement(
        name="material_zone_variation",
        description="Material zones distinguish soil, bark, moss, leaf, stone, or exposed faces.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("material", "moss", "soil", "leaf", "stone"),
        recommendation_template="Add material-zone variation for soil, bark, moss, leaves, stone, or exposed faces.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="weathering_or_erosion_masks",
        description="Weathering or erosion masks mark exposed edges and growth contact.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("weather", "erosion", "wear", "mask"),
        recommendation_template="Add weathering or erosion masks for exposed edges and growth contact.",
        graph_node_types=("wear_zone",),
    ),
    FamilyRequirement(
        name="scale_anchor",
        description="A seed, cap, root, pebble, or leaf scale anchor helps read size.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("seed", "cap", "pebble", "leaf", "root"),
        recommendation_template="Add a seed, cap, pebble, leaf, or root scale anchor.",
        graph_node_types=("decal_zone", "mount"),
    ),
)


_ENVIRONMENT_ARCHITECTURE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="floor_or_foundation",
        description="A floor, slab, deck, or foundation establishes the occupied footprint.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("floor", "foundation", "slab", "deck", "footprint"),
        recommendation_template="Add a floor, slab, deck, or foundation to establish the footprint.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="wall_or_enclosure",
        description="Walls, partitions, or enclosure surfaces define the space.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("wall", "partition", "enclosure", "facade"),
        recommendation_template="Add walls, partitions, or enclosure surfaces to define the space.",
        graph_node_types=("panel",),
    ),
    FamilyRequirement(
        name="opening_system",
        description="Doors, windows, arches, or portals create traversable/readable openings.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("door", "window", "opening", "arch", "portal"),
        recommendation_template="Add doors, windows, arches, or portals for readable openings.",
        graph_node_types=("inset", "panel"),
    ),
    FamilyRequirement(
        name="roof_or_cover",
        description="A roof, canopy, ceiling, or cap creates the top boundary.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("roof", "canopy", "ceiling", "cap"),
        recommendation_template="Add a roof, canopy, ceiling, or cap for the top boundary.",
        graph_node_types=("frame", "panel"),
    ),
    FamilyRequirement(
        name="vertical_supports",
        description="Columns, posts, buttresses, or piers communicate structure.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("column", "post", "buttress", "pier", "support"),
        recommendation_template="Add columns, posts, buttresses, or piers to communicate structure.",
        graph_node_types=("rail", "mount"),
    ),
    FamilyRequirement(
        name="circulation_or_access",
        description="Stairs, ramps, rails, bridges, or thresholds show how the space is used.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("stair", "ramp", "rail", "bridge", "threshold"),
        recommendation_template="Add stairs, ramps, rails, bridges, or thresholds for circulation.",
        graph_node_types=("rail", "handle"),
    ),
    FamilyRequirement(
        name="facade_trim_or_banding",
        description="Trim, bands, cornices, sills, or parapets give architectural rhythm.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("trim", "band", "cornice", "sill", "parapet"),
        recommendation_template="Add trim, bands, cornices, sills, or parapets for facade rhythm.",
        graph_node_types=("trim",),
    ),
    FamilyRequirement(
        name="modular_bays",
        description="Repeated bays, cells, alcoves, or frames make the module expandable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("bay", "cell", "alcove", "module", "frame"),
        recommendation_template="Add repeated bays, cells, alcoves, or frames for modular expansion.",
        graph_node_types=("frame", "panel"),
    ),
    FamilyRequirement(
        name="lighting_or_signage_zone",
        description="Lighting, signage, or decal zones add readable environment function.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("light", "sign", "label", "decal", "marker"),
        recommendation_template="Add lighting, signage, marker, or decal zones for environment function.",
        graph_node_types=("decal_zone", "mount"),
    ),
    FamilyRequirement(
        name="weathering_or_edge_wear",
        description="Weathering masks mark exposed edges, foot traffic, and exterior contact.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("weather", "wear", "dirt", "grime", "mask"),
        recommendation_template="Add weathering or edge-wear masks at exposed edges and traffic zones.",
        graph_node_types=("wear_zone",),
    ),
)


_LIGHTING_PROP_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="base_or_mount",
        description="A base, wall mount, bracket, or footing anchors the lighting prop.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("base", "mount", "bracket", "foot", "anchor"),
        recommendation_template="Add a base, mount, bracket, or footing to anchor the lighting prop.",
        graph_node_types=("mount", "primary_volume"),
    ),
    FamilyRequirement(
        name="support_or_armature",
        description="Posts, arms, frames, or hangers hold the emitter in space.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("post", "arm", "frame", "hanger", "support"),
        recommendation_template="Add posts, arms, frames, or hangers to hold the emitter.",
        graph_node_types=("rail", "frame"),
    ),
    FamilyRequirement(
        name="emitter_or_lens",
        description="A lens, bulb, strip, tube, or luminous face states the light source.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("lens", "bulb", "emitter", "strip", "tube", "light"),
        recommendation_template="Add a lens, bulb, strip, tube, or luminous face for the light source.",
        graph_node_types=("material_zone", "mount"),
    ),
    FamilyRequirement(
        name="housing_or_shade",
        description="A housing, shade, visor, or rim protects and directs the emitter.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("housing", "shade", "visor", "rim", "bezel"),
        recommendation_template="Add a housing, shade, visor, rim, or bezel around the emitter.",
        graph_node_types=("panel", "guard"),
    ),
    FamilyRequirement(
        name="power_or_cable_route",
        description="A cable, conduit, socket, or power route explains how the light is fed.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cable", "conduit", "socket", "power", "wire"),
        recommendation_template="Add a cable, conduit, socket, or power route.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="control_or_service_plate",
        description="Switches, access plates, or service panels make the prop maintainable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("switch", "service", "panel", "access", "control"),
        recommendation_template="Add a switch, access plate, or service panel.",
        graph_node_types=("panel", "inset"),
    ),
    FamilyRequirement(
        name="signage_or_marker_face",
        description="Signs, labels, arrows, hazard faces, or marker panels add readable function.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sign", "label", "arrow", "marker", "hazard"),
        recommendation_template="Add signage, labels, arrows, hazard faces, or marker panels.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="fasteners",
        description="Fasteners connect housings, mounts, shades, and service plates.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "rivet", "screw"),
        recommendation_template="Add fasteners around housings, mounts, shades, and service plates.",
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="protective_guard_or_cage",
        description="A guard, cage, grille, or bumper protects the emitter.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "cage", "grille", "bumper"),
        recommendation_template="Add a protective guard, cage, grille, or bumper around the emitter.",
        graph_node_types=("guard", "rail"),
    ),
    FamilyRequirement(
        name="soot_or_edge_wear_masks",
        description="Soot, heat tint, handled edges, and exposed corners need material masks.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("soot", "heat", "wear", "mask", "edge_wear"),
        recommendation_template="Add soot, heat-tint, handled-edge, or exposed-corner masks.",
        graph_node_types=("wear_zone",),
    ),
)


_MACHINE_CONSOLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="primary_machine_body",
        description="A primary chassis, pedestal, or cabinet establishes the machine mass.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body", "chassis", "pedestal", "cabinet", "machine"),
        recommendation_template="Add a primary chassis, pedestal, or cabinet for the machine mass.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="control_face_or_panel",
        description="A sloped or front control face communicates interactivity.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("control", "panel", "face", "deck", "interface"),
        recommendation_template="Add a control face or panel to communicate interaction.",
        graph_node_types=("panel",),
    ),
    FamilyRequirement(
        name="display_or_readout",
        description="Screens, gauges, dials, or readouts provide machine feedback.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("screen", "display", "gauge", "dial", "readout"),
        recommendation_template="Add screens, gauges, dials, or readouts for machine feedback.",
        graph_node_types=("decal_zone", "material_zone"),
    ),
    FamilyRequirement(
        name="input_controls",
        description="Buttons, toggles, handles, sliders, or keypads define control affordances.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("button", "toggle", "handle", "slider", "keypad"),
        recommendation_template="Add buttons, toggles, handles, sliders, or keypads.",
        graph_node_types=("fastener", "handle"),
    ),
    FamilyRequirement(
        name="service_access_panel",
        description="Hatches, doors, seams, or removable plates make the machine serviceable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("hatch", "door", "seam", "service", "plate"),
        recommendation_template="Add hatches, doors, seams, or removable service plates.",
        graph_node_types=("inset", "panel"),
    ),
    FamilyRequirement(
        name="ports_or_sockets",
        description="Ports, sockets, plugs, or jacks connect the machine to other systems.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("port", "socket", "plug", "jack", "connector"),
        recommendation_template="Add ports, sockets, plugs, or jacks.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="cooling_or_ventilation",
        description="Vents, slats, grilles, or fans communicate cooling and airflow.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("vent", "slat", "grille", "fan", "cooling"),
        recommendation_template="Add vents, slats, grilles, or fans for cooling.",
        graph_node_types=("inset", "guard"),
    ),
    FamilyRequirement(
        name="cable_or_pipe_connections",
        description="Cables, conduits, hoses, or pipe runs show system connections.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cable", "conduit", "hose", "pipe", "wire"),
        recommendation_template="Add cables, conduits, hoses, or pipe connections.",
        graph_node_types=("rail",),
    ),
    FamilyRequirement(
        name="status_or_warning_markings",
        description="Status labels, hazard stripes, serials, or warning plates clarify use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("status", "warning", "label", "serial", "marking"),
        recommendation_template="Add status labels, hazard stripes, serials, or warning plates.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="service_wear_masks",
        description="Wear masks mark handled controls, service edges, vents, and cable contact.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear", "grime", "service"),
        recommendation_template="Add wear masks around controls, service edges, vents, and cable contact.",
        graph_node_types=("wear_zone",),
    ),
)


_PORTAL_RELIC_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="anchor_base_or_plinth",
        description="A base, plinth, altar, or foundation anchors the relic or portal.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("base", "plinth", "altar", "foundation", "anchor"),
        recommendation_template="Add a base, plinth, altar, or foundation to anchor the relic.",
        graph_node_types=("primary_volume", "mount"),
    ),
    FamilyRequirement(
        name="frame_or_vertical_core",
        description="A frame, arch, obelisk, pillar, or vertical core defines the silhouette.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("frame", "arch", "obelisk", "pillar", "core"),
        recommendation_template="Add a frame, arch, obelisk, pillar, or vertical core.",
        graph_node_types=("frame", "rail"),
    ),
    FamilyRequirement(
        name="threshold_or_active_center",
        description="A threshold, ring, aperture, crystal, or active center states the focal function.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("threshold", "ring", "aperture", "crystal", "core"),
        recommendation_template="Add a threshold, ring, aperture, crystal, or active center.",
        graph_node_types=("material_zone", "socket"),
    ),
    FamilyRequirement(
        name="power_nodes_or_keystones",
        description="Keystones, pylons, nodes, or caps imply energy routing.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("keystone", "pylon", "node", "cap", "crystal"),
        recommendation_template="Add keystones, pylons, nodes, or caps around the portal/relic.",
        graph_node_types=("mount", "socket"),
    ),
    FamilyRequirement(
        name="radial_or_symmetric_layout",
        description="Radial or mirrored layout makes the object feel intentional rather than random.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("radial", "mirror", "symmetric", "array", "ring"),
        recommendation_template="Add radial or mirrored layout cues.",
        graph_node_types=("frame", "trim"),
    ),
    FamilyRequirement(
        name="runes_or_inscriptions",
        description="Runes, inscriptions, glyphs, or bands communicate artifact identity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("rune", "glyph", "inscription", "band", "marking"),
        recommendation_template="Add runes, inscriptions, glyphs, or marking bands.",
        graph_node_types=("decal_zone", "trim"),
    ),
    FamilyRequirement(
        name="offering_or_attachment_mounts",
        description="Offering trays, sockets, hooks, or attachment mounts support interaction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("offering", "tray", "socket", "hook", "mount"),
        recommendation_template="Add offering trays, sockets, hooks, or attachment mounts.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="conduits_or_energy_paths",
        description="Conduits, veins, cables, or carved paths connect nodes and the active center.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("conduit", "vein", "cable", "path", "channel"),
        recommendation_template="Add conduits, veins, cables, or carved paths between power nodes.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="environment_contact",
        description="Roots, rubble, clamps, dust, or ground contact integrate the relic into place.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("root", "rubble", "clamp", "dust", "ground"),
        recommendation_template="Add roots, rubble, clamps, dust, or ground-contact forms.",
        graph_node_types=("mount", "primary_volume"),
    ),
    FamilyRequirement(
        name="age_or_aura_wear_masks",
        description="Age, aura, patina, chipped edges, and contact masks carry material story.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("age", "aura", "patina", "wear", "mask"),
        recommendation_template="Add age, aura, patina, chipped-edge, or contact masks.",
        graph_node_types=("wear_zone",),
    ),
)


_TOOL_PROP_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="primary_tool_body",
        description="A primary body, handle body, or casing establishes the tool mass.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body", "casing", "tool", "housing"),
        recommendation_template="Add a primary body, handle body, or casing.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="grip_or_handle",
        description="A grip, handle, wrap, or held section makes the tool usable.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("grip", "handle", "wrap", "held"),
        recommendation_template="Add a grip, handle, wrap, or held section.",
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="working_head_or_bit",
        description="A hammer head, wrench jaw, drill bit, blade, or scanner face defines function.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("head", "jaw", "bit", "blade", "face"),
        recommendation_template="Add a working head, jaw, bit, blade, or scanner face.",
        graph_node_types=("guard", "panel"),
    ),
    FamilyRequirement(
        name="shaft_or_spine",
        description="A shaft, spine, rail, or neck connects grip and working head.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("shaft", "spine", "rail", "neck"),
        recommendation_template="Add a shaft, spine, rail, or neck between grip and working head.",
        graph_node_types=("rail",),
    ),
    FamilyRequirement(
        name="guard_or_stop",
        description="A guard, stop, flange, or collar protects the hand or stops motion.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "stop", "flange", "collar"),
        recommendation_template="Add a guard, stop, flange, or collar.",
        graph_node_types=("guard",),
    ),
    FamilyRequirement(
        name="adjustment_or_joint",
        description="A knob, hinge, ratchet, joint, or slider communicates adjustability.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("knob", "hinge", "ratchet", "joint", "slider"),
        recommendation_template="Add a knob, hinge, ratchet, joint, or slider.",
        graph_node_types=("mount", "hinge"),
    ),
    FamilyRequirement(
        name="sockets_or_attachment_points",
        description="Sockets, ports, hooks, or attachment points make the tool modular.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("socket", "port", "hook", "attachment", "mount"),
        recommendation_template="Add sockets, ports, hooks, or attachment points.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="fasteners",
        description="Fasteners connect plates, heads, guards, and handles.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "bolt", "rivet", "screw"),
        recommendation_template="Add fasteners around plates, heads, guards, and handles.",
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="marking_or_scale_zone",
        description="Scale marks, labels, decals, or serial plates clarify tool identity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("marking", "scale", "label", "decal", "serial"),
        recommendation_template="Add scale marks, labels, decals, or serial plates.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="contact_wear_masks",
        description="Wear masks mark grips, working edges, sockets, and rubbed contact zones.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "edge_wear", "rubbed"),
        recommendation_template="Add wear masks around grips, working edges, sockets, and contact zones.",
        graph_node_types=("wear_zone",),
    ),
)


_MODULAR_KIT_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="canonical_tile_body",
        description="A canonical tile, block, panel, or module body defines the kit unit.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("tile", "block", "panel", "module", "body"),
        recommendation_template="Add a canonical tile, block, panel, or module body.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="snap_edges_or_bounds",
        description="Snap edges, bounds, grid lines, or footprints make placement deterministic.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("snap", "edge", "bound", "grid", "footprint"),
        recommendation_template="Add snap edges, bounds, grid lines, or footprints.",
        graph_node_types=("trim", "rail"),
    ),
    FamilyRequirement(
        name="connector_ports",
        description="Ports, sockets, pegs, slots, or anchors make pieces connect.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("port", "socket", "peg", "slot", "anchor"),
        recommendation_template="Add ports, sockets, pegs, slots, or anchors.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="orientation_markers",
        description="Arrows, notches, labels, or asymmetry clarify forward/up orientation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("arrow", "notch", "label", "orientation", "marker"),
        recommendation_template="Add arrows, notches, labels, or asymmetry for orientation.",
        graph_node_types=("decal_zone", "inset"),
    ),
    FamilyRequirement(
        name="seam_or_panel_breaks",
        description="Seams, grooves, panel breaks, or reveal lines make repeated joins readable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("seam", "groove", "break", "reveal", "joint"),
        recommendation_template="Add seams, grooves, panel breaks, or reveal lines.",
        graph_node_types=("inset", "trim"),
    ),
    FamilyRequirement(
        name="variant_attachment_zones",
        description="Mount zones or sockets allow alternate trims, props, doors, and add-ons.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("variant", "attachment", "addon", "mount", "trim"),
        recommendation_template="Add variant attachment zones for trims, props, doors, or add-ons.",
        graph_node_types=("mount", "socket"),
    ),
    FamilyRequirement(
        name="structural_frame_or_ribs",
        description="Frames, ribs, braces, or rails keep the module readable at distance.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("frame", "rib", "brace", "rail", "support"),
        recommendation_template="Add frames, ribs, braces, or rails.",
        graph_node_types=("frame", "rail"),
    ),
    FamilyRequirement(
        name="fasteners_or_locator_pins",
        description="Fasteners or locator pins reinforce assembly logic.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "pin", "bolt", "rivet", "locator"),
        recommendation_template="Add fasteners or locator pins.",
        graph_node_types=("fastener",),
    ),
    FamilyRequirement(
        name="material_or_theme_zone",
        description="A material zone, trim sheet region, or theme band keeps variants coherent.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("material", "theme", "trim", "zone", "band"),
        recommendation_template="Add a material zone, trim-sheet region, or theme band.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="repeat_wear_masks",
        description="Wear masks mark repeat edges, snap contacts, foot traffic, and exposed corners.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "contact", "traffic", "edge_wear"),
        recommendation_template="Add repeat-edge, snap-contact, traffic, or exposed-corner wear masks.",
        graph_node_types=("wear_zone",),
    ),
)


_CHARACTER_CREATURE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="primary_body_mass",
        description="A torso, body mass, shell, or core volume establishes anatomy.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("torso", "body", "shell", "core", "mass"),
        recommendation_template="Add a torso, body mass, shell, or core volume.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="head_or_sensor_cluster",
        description="A head, face, sensor cluster, or focal node gives the form identity.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("head", "face", "sensor", "eye", "mask"),
        recommendation_template="Add a head, face, sensor cluster, or focal node.",
        graph_node_types=("mount", "material_zone"),
    ),
    FamilyRequirement(
        name="limbs_or_appendages",
        description="Limbs, arms, legs, wings, tendrils, or appendages communicate motion.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("limb", "arm", "leg", "wing", "tendril"),
        recommendation_template="Add limbs, arms, legs, wings, tendrils, or appendages.",
        graph_node_types=("rail", "handle"),
    ),
    FamilyRequirement(
        name="joints_or_articulation",
        description="Joints, hinges, sockets, shoulders, hips, or knees make pose readable.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("joint", "hinge", "socket", "shoulder", "knee"),
        recommendation_template="Add joints, hinges, sockets, shoulders, hips, or knees.",
        graph_node_types=("hinge", "socket"),
    ),
    FamilyRequirement(
        name="hands_feet_or_contact_points",
        description="Hands, feet, claws, pads, or contact points anchor the form.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("hand", "foot", "feet", "claw", "pad"),
        recommendation_template="Add hands, feet, claws, pads, or contact points.",
        graph_node_types=("mount", "guard"),
    ),
    FamilyRequirement(
        name="feature_marks_or_face_details",
        description="Eyes, mouth, markings, plates, or facial details support identity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("eye", "mouth", "marking", "plate", "detail"),
        recommendation_template="Add eyes, mouth, markings, plates, or facial details.",
        graph_node_types=("decal_zone", "material_zone"),
    ),
    FamilyRequirement(
        name="silhouette_breaks_or_accessories",
        description="Crests, ears, horns, gear, packs, or accessories break the outline.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("crest", "ear", "horn", "gear", "pack"),
        recommendation_template="Add crests, ears, horns, gear, packs, or accessories.",
        graph_node_types=("guard", "mount"),
    ),
    FamilyRequirement(
        name="pose_line_or_balance",
        description="A pose line, tail, spine, counterweight, or lean gives balance.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("pose", "tail", "spine", "balance", "lean"),
        recommendation_template="Add a pose line, tail, spine, counterweight, or lean.",
        graph_node_types=("rail",),
    ),
    FamilyRequirement(
        name="scale_anchor",
        description="A belt, collar, tool, base pad, or surface contact helps read size.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("belt", "collar", "tool", "base", "scale"),
        recommendation_template="Add a belt, collar, tool, base pad, or contact scale anchor.",
        graph_node_types=("trim", "mount"),
    ),
    FamilyRequirement(
        name="contact_or_surface_wear_masks",
        description="Wear or material masks mark joints, hands/feet, contact points, and features.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "joint", "contact", "surface"),
        recommendation_template="Add wear/material masks around joints, contact points, and features.",
        graph_node_types=("wear_zone",),
    ),
)


_SET_DRESSING_PROP_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="primary_prop_volume",
        description="A primary barrel, sack, basket, jar, bundle, or object body anchors the prop.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body", "barrel", "sack", "basket", "jar", "bundle"),
        recommendation_template="Add a primary barrel, sack, basket, jar, bundle, or object body.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="secondary_scale_forms",
        description="Secondary items, caps, lids, rolled goods, or contents add scale.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("secondary", "cap", "lid", "roll", "contents"),
        recommendation_template="Add secondary forms such as caps, lids, rolled goods, or contents.",
        graph_node_types=("mount", "panel"),
    ),
    FamilyRequirement(
        name="floor_contact_or_base",
        description="Feet, base pads, rims, or flattened contact areas ground the object.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("foot", "base", "pad", "rim", "contact"),
        recommendation_template="Add feet, base pads, rims, or contact areas.",
        graph_node_types=("mount", "trim"),
    ),
    FamilyRequirement(
        name="handles_straps_or_ties",
        description="Handles, straps, ropes, ties, or bindings communicate how the prop is moved.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("handle", "strap", "rope", "tie", "binding"),
        recommendation_template="Add handles, straps, ropes, ties, or bindings.",
        graph_node_types=("handle", "rail"),
    ),
    FamilyRequirement(
        name="openings_or_lids",
        description="Openings, lids, seams, corks, or caps clarify container function.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("opening", "lid", "seam", "cork", "cap"),
        recommendation_template="Add openings, lids, seams, corks, or caps.",
        graph_node_types=("inset", "panel"),
    ),
    FamilyRequirement(
        name="label_or_marking_zone",
        description="Labels, painted marks, stamped signs, or tags add world identity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("label", "mark", "tag", "stamp", "decal"),
        recommendation_template="Add labels, painted marks, stamped signs, or tags.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="fasteners_or_stitches",
        description="Fasteners, stitches, knots, rivets, or seams explain construction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fastener", "stitch", "knot", "rivet", "seam"),
        recommendation_template="Add fasteners, stitches, knots, rivets, or construction seams.",
        graph_node_types=("fastener", "trim"),
    ),
    FamilyRequirement(
        name="small_detail_scatter",
        description="Small attached props, pebbles, chips, tags, or loose contents add set dressing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("scatter", "chip", "tag", "loose", "detail"),
        recommendation_template="Add small attached props, chips, tags, or loose contents.",
        graph_node_types=("mount", "fastener"),
    ),
    FamilyRequirement(
        name="material_zone_variation",
        description="Material zones separate fabric, wood, metal, ceramic, rope, or contents.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("material", "fabric", "wood", "metal", "ceramic"),
        recommendation_template="Add material-zone variation for fabric, wood, metal, ceramic, rope, or contents.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="handled_wear_masks",
        description="Wear masks mark handles, floor contact, lids, straps, and exposed corners.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "mask", "handled", "floor", "edge_wear"),
        recommendation_template="Add wear masks around handles, floor contact, lids, straps, and exposed corners.",
        graph_node_types=("wear_zone",),
    ),
)


_SURFACE_MATERIAL_SAMPLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="sample_tile_or_swatch",
        description="A sample tile, swatch board, or material plane defines the surface domain.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("tile", "swatch", "sample", "plane", "board"),
        recommendation_template="Add a sample tile, swatch board, or material plane.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="base_material_zone",
        description="A base color/material zone gives the sample a primary identity.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("base", "material", "color", "zone", "albedo"),
        recommendation_template="Add a base material or color zone.",
        graph_node_types=("material_zone",),
    ),
    FamilyRequirement(
        name="roughness_or_finish_zone",
        description="Gloss, roughness, matte, varnish, or finish bands communicate response.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("roughness", "finish", "gloss", "matte", "varnish"),
        recommendation_template="Add roughness, gloss, matte, varnish, or finish zones.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="normal_or_relief_detail",
        description="Raised relief, grooves, pores, scratches, or embossing show surface depth.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("normal", "relief", "groove", "scratch", "emboss"),
        recommendation_template="Add raised relief, grooves, pores, scratches, or embossing.",
        graph_node_types=("trim", "inset"),
    ),
    FamilyRequirement(
        name="trim_or_border",
        description="Borders, frame strips, trim bands, or margins make the sample readable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("border", "frame", "trim", "band", "margin"),
        recommendation_template="Add borders, frame strips, trim bands, or margins.",
        graph_node_types=("trim", "frame"),
    ),
    FamilyRequirement(
        name="decal_or_label_zone",
        description="Labels, swatch names, channel markers, or decals identify the sample.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("label", "decal", "marker", "swatch", "channel"),
        recommendation_template="Add labels, swatch names, channel markers, or decals.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="scale_or_frequency_reference",
        description="Scale bars, ticks, grids, or frequency strips calibrate detail size.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("scale", "tick", "grid", "frequency", "reference"),
        recommendation_template="Add scale bars, ticks, grids, or frequency strips.",
        graph_node_types=("fastener", "trim"),
    ),
    FamilyRequirement(
        name="edge_chips_or_wear",
        description="Chips, rubbed edges, grime lines, or wear masks exercise material response.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("chip", "rubbed", "grime", "wear", "mask"),
        recommendation_template="Add chips, rubbed edges, grime lines, or wear masks.",
        graph_node_types=("wear_zone",),
    ),
    FamilyRequirement(
        name="variant_patch_or_secondary_material",
        description="A secondary patch, material variant, or inlay shows contrast and composition.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("variant", "patch", "secondary", "inlay", "contrast"),
        recommendation_template="Add a secondary patch, material variant, or inlay.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="uv_or_tileability_cues",
        description="UV arrows, repeat seams, corner markers, or tileability cues clarify repetition.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("uv", "repeat", "seam", "corner", "tileable"),
        recommendation_template="Add UV arrows, repeat seams, corner markers, or tileability cues.",
        graph_node_types=("decal_zone", "socket"),
    ),
)


_TERRAIN_VEGETATION_VARIANT_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="terrain_base_or_height_plate",
        description="A ground plate, heightfield patch, slope, or terrain mass anchors the variant.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("ground", "heightfield", "terrain", "slope", "base"),
        recommendation_template="Add a ground plate, heightfield patch, slope, or terrain mass.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="height_variation_or_strata",
        description="Ridges, terraces, strata, shelves, or mounds give topographic read.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("ridge", "terrace", "strata", "shelf", "mound"),
        recommendation_template="Add ridges, terraces, strata, shelves, or mounds.",
        graph_node_types=("trim", "panel"),
    ),
    FamilyRequirement(
        name="growth_clusters",
        description="Grass, foliage, flowers, shrubs, or canopy clusters express biome identity.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("grass", "foliage", "flower", "shrub", "canopy"),
        recommendation_template="Add grass, foliage, flowers, shrubs, or canopy clusters.",
        graph_node_types=("mount", "material_zone"),
    ),
    FamilyRequirement(
        name="root_or_path_flow",
        description="Roots, trails, erosion paths, streams, or growth flow lines guide composition.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("root", "trail", "path", "stream", "flow"),
        recommendation_template="Add roots, trails, erosion paths, streams, or growth flow lines.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="small_natural_scatter",
        description="Pebbles, leaves, sprouts, sticks, or small stones provide scale.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("pebble", "leaf", "sprout", "stick", "stone"),
        recommendation_template="Add pebbles, leaves, sprouts, sticks, or small stones.",
        graph_node_types=("fastener", "mount"),
    ),
    FamilyRequirement(
        name="biome_material_zones",
        description="Soil, moss, leaf, stone, mud, sand, or snow zones define the biome.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("soil", "moss", "leaf", "mud", "sand", "snow"),
        recommendation_template="Add biome material zones such as soil, moss, leaf, mud, sand, or snow.",
        graph_node_types=("material_zone",),
    ),
    FamilyRequirement(
        name="edge_transition_or_blend",
        description="Blend skirts, edge fades, roots, talus, or boundary shapes help tile the patch.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("blend", "edge", "fade", "talus", "boundary"),
        recommendation_template="Add blend skirts, edge fades, roots, talus, or boundary shapes.",
        graph_node_types=("panel", "mount"),
    ),
    FamilyRequirement(
        name="scale_anchors",
        description="Logs, caps, leaves, seed pods, or stones anchor visual scale.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("log", "cap", "leaf", "seed", "stone"),
        recommendation_template="Add logs, caps, leaves, seed pods, or stones for scale.",
        graph_node_types=("mount", "decal_zone"),
    ),
    FamilyRequirement(
        name="erosion_or_weathering_masks",
        description="Erosion, dampness, exposed-edge, or growth-contact masks carry terrain history.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("erosion", "damp", "exposed", "wear", "mask"),
        recommendation_template="Add erosion, dampness, exposed-edge, or growth-contact masks.",
        graph_node_types=("wear_zone",),
    ),
    FamilyRequirement(
        name="variant_or_tileability_cues",
        description="Variant markers, repetition seams, or biome tags support kit usage.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("variant", "repeat", "seam", "tile", "biome"),
        recommendation_template="Add variant markers, repetition seams, or biome tags.",
        graph_node_types=("decal_zone", "socket"),
    ),
)


_ENVIRONMENT_EFFECT_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="emitter_or_source",
        description="A source, emitter, nozzle, cloud seed, water edge, or weather origin anchors the effect.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("source", "emitter", "nozzle", "seed", "origin"),
        recommendation_template="Add a source, emitter, nozzle, cloud seed, water edge, or weather origin.",
        graph_node_types=("primary_volume", "mount"),
    ),
    FamilyRequirement(
        name="flow_surface_or_volume",
        description="A water surface, fog volume, smoke puff, rain field, or effect body defines coverage.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("surface", "volume", "puff", "field", "body"),
        recommendation_template="Add a water surface, fog volume, smoke puff, rain field, or effect body.",
        graph_node_types=("material_zone", "primary_volume"),
    ),
    FamilyRequirement(
        name="direction_or_motion_lines",
        description="Flow lines, streaks, trails, wind direction, or cascade paths show motion.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("flow", "streak", "trail", "wind", "cascade"),
        recommendation_template="Add flow lines, streaks, trails, wind direction, or cascade paths.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="contact_or_interaction_zone",
        description="Wet edges, splash zones, deposition, fog banks, or ground contact integrate the effect.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("wet", "splash", "deposition", "bank", "contact"),
        recommendation_template="Add wet edges, splash zones, deposition, fog banks, or ground contact.",
        graph_node_types=("wear_zone", "material_zone"),
    ),
    FamilyRequirement(
        name="secondary_particles_or_ripples",
        description="Particles, droplets, ripples, flakes, sparks, or wisps add detail hierarchy.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("particle", "droplet", "ripple", "flake", "wisp"),
        recommendation_template="Add particles, droplets, ripples, flakes, sparks, or wisps.",
        graph_node_types=("fastener", "mount"),
    ),
    FamilyRequirement(
        name="density_or_gradient_bands",
        description="Density bands, gradient markers, rings, or soft falloff shapes clarify intensity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("density", "gradient", "ring", "falloff", "band"),
        recommendation_template="Add density bands, gradient markers, rings, or falloff shapes.",
        graph_node_types=("trim", "decal_zone"),
    ),
    FamilyRequirement(
        name="boundary_or_clip_shape",
        description="Bounds, clip frames, basins, banks, or blockers contain the effect.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("bound", "clip", "basin", "bank", "blocker"),
        recommendation_template="Add bounds, clip frames, basins, banks, or blockers.",
        graph_node_types=("frame", "panel"),
    ),
    FamilyRequirement(
        name="material_response_zone",
        description="Foam, frost, soot, condensation, wetness, or residue zones show material response.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("foam", "frost", "soot", "condensation", "residue"),
        recommendation_template="Add foam, frost, soot, condensation, wetness, or residue zones.",
        graph_node_types=("material_zone",),
    ),
    FamilyRequirement(
        name="scale_or_readability_markers",
        description="Scale markers, reference droplets, foam flecks, or edge highlights help read size.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("scale", "reference", "fleck", "highlight", "marker"),
        recommendation_template="Add scale markers, reference droplets, foam flecks, or edge highlights.",
        graph_node_types=("decal_zone", "fastener"),
    ),
    FamilyRequirement(
        name="effect_masks",
        description="Wetness, deposition, opacity, heat, or dissipation masks carry runtime/surface intent.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wetness", "opacity", "heat", "dissipation", "mask"),
        recommendation_template="Add wetness, deposition, opacity, heat, or dissipation masks.",
        graph_node_types=("wear_zone",),
    ),
)


_SETTLEMENT_DISTRICT_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="primary_layout_footprint",
        description="A base footprint, district plate, settlement block, or terrain pad establishes layout scale.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("footprint", "layout", "district", "settlement", "pad"),
        recommendation_template="Add a base footprint, district plate, settlement block, or terrain pad.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="circulation_paths",
        description="Roads, paths, alleys, bridges, or walkways make the district traversable.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("road", "path", "alley", "bridge", "walkway"),
        recommendation_template="Add roads, paths, alleys, bridges, or walkways.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="plot_or_block_cells",
        description="Plots, blocks, lots, pads, or buildable cells divide the settlement.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("plot", "block", "lot", "cell", "pad"),
        recommendation_template="Add plots, blocks, lots, pads, or buildable cells.",
        graph_node_types=("panel", "primary_volume"),
    ),
    FamilyRequirement(
        name="landmark_or_anchor",
        description="A landmark, tower, plaza, statue, or central anchor gives the district identity.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("landmark", "tower", "plaza", "statue", "anchor"),
        recommendation_template="Add a landmark, tower, plaza, statue, or central anchor.",
        graph_node_types=("mount", "primary_volume"),
    ),
    FamilyRequirement(
        name="thresholds_or_gateways",
        description="Gates, thresholds, bridges, portals, or entry markers define transitions.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("gate", "threshold", "entry", "portal", "gateway"),
        recommendation_template="Add gates, thresholds, bridges, portals, or entry markers.",
        graph_node_types=("frame", "guard"),
    ),
    FamilyRequirement(
        name="activity_zones",
        description="Market, work, rest, combat, service, or gathering zones clarify gameplay use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("market", "work", "rest", "combat", "service", "gather"),
        recommendation_template="Add market, work, rest, combat, service, or gathering zones.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="vertical_or_height_variation",
        description="Stairs, terraces, raised blocks, towers, or height markers create readable elevation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("stair", "terrace", "raised", "height", "elevation"),
        recommendation_template="Add stairs, terraces, raised blocks, towers, or height markers.",
        graph_node_types=("mount", "primary_volume"),
    ),
    FamilyRequirement(
        name="edge_boundaries",
        description="Walls, fences, rails, curbs, cliffs, or borders contain the district.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wall", "fence", "rail", "curb", "border"),
        recommendation_template="Add walls, fences, rails, curbs, cliffs, or borders.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="signage_or_wayfinding",
        description="Signs, arrows, color bands, markers, or labels support navigation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sign", "arrow", "marker", "label", "wayfinding"),
        recommendation_template="Add signs, arrows, color bands, markers, or labels.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="traffic_wear_masks",
        description="Road wear, path dirt, chipped thresholds, or edge masks show use and flow.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("traffic", "wear", "dirt", "chip", "mask"),
        recommendation_template="Add road wear, path dirt, chipped thresholds, or edge masks.",
        graph_node_types=("wear_zone",),
    ),
)


_GAMEPLAY_OBJECT_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="interaction_body",
        description="A clear interactable body, pedestal, crate, device, or marker carries the object.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body", "pedestal", "device", "object", "marker"),
        recommendation_template="Add a clear interactable body, pedestal, crate, device, or marker.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="state_indicator",
        description="Lights, icons, gauges, color panels, or status plates communicate state.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("state", "status", "light", "icon", "gauge"),
        recommendation_template="Add lights, icons, gauges, color panels, or status plates.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="trigger_or_activation_zone",
        description="A trigger plate, radius, button field, sensor area, or activation ring shows how to use it.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("trigger", "activation", "button", "sensor", "radius"),
        recommendation_template="Add a trigger plate, radius, button field, sensor area, or activation ring.",
        graph_node_types=("material_zone", "socket"),
    ),
    FamilyRequirement(
        name="reward_or_payload_zone",
        description="A pickup bay, payload socket, loot slot, prize pocket, or output tray clarifies payoff.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("reward", "payload", "pickup", "loot", "output"),
        recommendation_template="Add a pickup bay, payload socket, loot slot, prize pocket, or output tray.",
        graph_node_types=("socket", "inset"),
    ),
    FamilyRequirement(
        name="access_or_affordance_handle",
        description="Handles, grips, levers, switches, pulls, or knobs expose the affordance.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("handle", "grip", "lever", "switch", "knob"),
        recommendation_template="Add handles, grips, levers, switches, pulls, or knobs.",
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="feedback_emitter",
        description="Emitters, lenses, speakers, particles, or pulse markers show feedback.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("emitter", "lens", "speaker", "particle", "pulse"),
        recommendation_template="Add emitters, lenses, speakers, particles, or pulse markers.",
        graph_node_types=("mount", "fastener"),
    ),
    FamilyRequirement(
        name="safety_or_bounds_marker",
        description="Bounds, caution rails, hazard bands, safe zones, or warning marks frame interaction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("bound", "caution", "hazard", "safe", "warning"),
        recommendation_template="Add bounds, caution rails, hazard bands, safe zones, or warning marks.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="attachment_or_link_ports",
        description="Ports, sockets, plugs, cable links, or snap nodes connect the object to systems.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("port", "socket", "plug", "cable", "link"),
        recommendation_template="Add ports, sockets, plugs, cable links, or snap nodes.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="label_or_objective_marker",
        description="Objective marks, labels, quest icons, arrows, or signage identify purpose.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("objective", "label", "quest", "arrow", "sign"),
        recommendation_template="Add objective marks, labels, quest icons, arrows, or signage.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="interaction_wear_masks",
        description="Handled edges, foot marks, scorch, scratches, or use masks show repeated interaction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("handled", "foot", "scorch", "scratch", "wear"),
        recommendation_template="Add handled edges, foot marks, scorch, scratches, or use masks.",
        graph_node_types=("wear_zone",),
    ),
)


_ENCOUNTER_FLOW_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="encounter_footprint",
        description="An arena pad, room, field, lane, or encounter footprint establishes playable bounds.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("arena", "room", "field", "lane", "footprint"),
        recommendation_template="Add an arena pad, room, field, lane, or encounter footprint.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="spawn_or_entry_points",
        description="Spawn sockets, entry gates, wave doors, ambush points, or arrival pads define starts.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("spawn", "entry", "gate", "ambush", "arrival"),
        recommendation_template="Add spawn sockets, entry gates, wave doors, ambush points, or arrival pads.",
        graph_node_types=("socket", "frame"),
    ),
    FamilyRequirement(
        name="patrol_or_route_lines",
        description="Patrol paths, route arrows, spline lanes, or flow tracks make movement readable.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("patrol", "route", "arrow", "lane", "flow"),
        recommendation_template="Add patrol paths, route arrows, spline lanes, or flow tracks.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="cover_or_safety_zones",
        description="Cover blocks, safety pockets, fallback zones, or shield lines support tactics.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("cover", "safety", "fallback", "shield", "pocket"),
        recommendation_template="Add cover blocks, safety pockets, fallback zones, or shield lines.",
        graph_node_types=("guard", "panel"),
    ),
    FamilyRequirement(
        name="objective_or_pressure_point",
        description="Objectives, control points, boss anchors, capture plates, or defense nodes focus play.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("objective", "control", "boss", "capture", "defense"),
        recommendation_template="Add objectives, control points, boss anchors, capture plates, or defense nodes.",
        graph_node_types=("mount", "decal_zone"),
    ),
    FamilyRequirement(
        name="escalation_or_wave_markers",
        description="Wave markers, escalation ticks, phase plates, timers, or threat pips show pacing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wave", "phase", "timer", "threat", "escalation"),
        recommendation_template="Add wave markers, escalation ticks, phase plates, timers, or threat pips.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="reward_or_exit_zone",
        description="Reward pads, exit gates, extraction zones, loot bays, or completion markers close the loop.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("reward", "exit", "extract", "loot", "complete"),
        recommendation_template="Add reward pads, exit gates, extraction zones, loot bays, or completion markers.",
        graph_node_types=("socket", "material_zone"),
    ),
    FamilyRequirement(
        name="hazard_or_boundary_markers",
        description="Hazards, boundaries, danger bands, no-go lines, or arena edges prevent ambiguous play.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("hazard", "boundary", "danger", "edge", "no-go"),
        recommendation_template="Add hazards, boundaries, danger bands, no-go lines, or arena edges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="readability_or_signage_cues",
        description="Signs, color cues, icons, labels, or arrows clarify encounter intent.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sign", "color", "icon", "label", "arrow"),
        recommendation_template="Add signs, color cues, icons, labels, or arrows.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="pacing_or_wear_masks",
        description="Foot traffic, scorch, impact, route wear, or pressure masks show repeated play.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("traffic", "scorch", "impact", "wear", "pressure"),
        recommendation_template="Add foot traffic, scorch, impact, route wear, or pressure masks.",
        graph_node_types=("wear_zone",),
    ),
)


_INVENTORY_ECONOMY_OBJECT_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="item_body_or_container",
        description="A clear item body, crate, pouch, chest, capsule, or vendor container anchors the object.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body", "crate", "pouch", "chest", "container"),
        recommendation_template="Add a clear item body, crate, pouch, chest, capsule, or vendor container.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="value_or_currency_marker",
        description="Coins, value plates, price tags, currency pips, or resource icons communicate worth.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("coin", "value", "price", "currency", "resource"),
        recommendation_template="Add coins, value plates, price tags, currency pips, or resource icons.",
        graph_node_types=("decal_zone", "fastener"),
    ),
    FamilyRequirement(
        name="quantity_or_stack_indicator",
        description="Stack ticks, quantity beads, bundle bands, fill marks, or count chips show amount.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("stack", "quantity", "bundle", "fill", "count"),
        recommendation_template="Add stack ticks, quantity beads, bundle bands, fill marks, or count chips.",
        graph_node_types=("fastener", "trim"),
    ),
    FamilyRequirement(
        name="rarity_or_tier_band",
        description="Rarity bands, tier plates, color strips, gem sockets, or grade marks show class.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("rarity", "tier", "grade", "gem", "class"),
        recommendation_template="Add rarity bands, tier plates, color strips, gem sockets, or grade marks.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="access_or_lock_affordance",
        description="Locks, clasps, lids, pull tabs, keys, or open handles define access.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("lock", "clasp", "lid", "tab", "key"),
        recommendation_template="Add locks, clasps, lids, pull tabs, keys, or open handles.",
        graph_node_types=("handle", "socket"),
    ),
    FamilyRequirement(
        name="storage_slots_or_grid",
        description="Slots, dividers, grid cells, pockets, or sockets organize inventory contents.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("slot", "divider", "grid", "pocket", "socket"),
        recommendation_template="Add slots, dividers, grid cells, pockets, or sockets.",
        graph_node_types=("inset", "panel"),
    ),
    FamilyRequirement(
        name="pickup_or_use_handle",
        description="Pickup handles, grip bands, use levers, buttons, or carrying loops expose interaction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("pickup", "grip", "use", "button", "carry"),
        recommendation_template="Add pickup handles, grip bands, use levers, buttons, or carrying loops.",
        graph_node_types=("handle",),
    ),
    FamilyRequirement(
        name="ownership_or_vendor_label",
        description="Vendor labels, ownership plates, faction marks, stamps, or item names identify source.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("vendor", "owner", "faction", "stamp", "label"),
        recommendation_template="Add vendor labels, ownership plates, faction marks, stamps, or item names.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="resource_connection_ports",
        description="Ports, plugs, pour spouts, feed sockets, or transfer links connect resource objects.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("port", "plug", "spout", "feed", "transfer"),
        recommendation_template="Add ports, plugs, pour spouts, feed sockets, or transfer links.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="handled_wear_masks",
        description="Handled edges, rubbed labels, pocket wear, chipped corners, or pickup marks show use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("handled", "rubbed", "pocket", "chipped", "wear"),
        recommendation_template="Add handled edges, rubbed labels, pocket wear, chipped corners, or pickup marks.",
        graph_node_types=("wear_zone",),
    ),
)


_RIG_ANIMATION_PROXY_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="rig_root_or_control_body",
        description="A root control, pelvis, chassis, base plate, or animation control body anchors the rig.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("root", "control", "pelvis", "base", "chassis"),
        recommendation_template="Add a root control, pelvis, chassis, base plate, or animation control body.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="bone_or_joint_chain",
        description="Bones, joint chains, spine links, hinges, or articulation rails define hierarchy.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("bone", "joint", "spine", "hinge", "chain"),
        recommendation_template="Add bones, joint chains, spine links, hinges, or articulation rails.",
        graph_node_types=("rail", "hinge"),
    ),
    FamilyRequirement(
        name="limb_or_segment_markers",
        description="Limb segments, digit markers, wing links, tentacle sections, or mech limbs show structure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("limb", "digit", "wing", "tentacle", "segment"),
        recommendation_template="Add limb segments, digit markers, wing links, tentacle sections, or mech limbs.",
        graph_node_types=("mount", "fastener"),
    ),
    FamilyRequirement(
        name="ik_or_target_handles",
        description="IK targets, handles, poles, control knobs, or target pads expose rig controls.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("ik", "target", "pole", "handle", "control"),
        recommendation_template="Add IK targets, handles, poles, control knobs, or target pads.",
        graph_node_types=("handle", "socket"),
    ),
    FamilyRequirement(
        name="pose_or_motion_arc",
        description="Pose lines, motion arcs, ghost paths, stride curves, or swing trails show animation intent.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("pose", "arc", "motion", "stride", "swing"),
        recommendation_template="Add pose lines, motion arcs, ghost paths, stride curves, or swing trails.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="skin_or_weight_zone",
        description="Skin zones, weight bands, deformation regions, envelopes, or influence fields clarify binding.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("skin", "weight", "deform", "envelope", "influence"),
        recommendation_template="Add skin zones, weight bands, deformation regions, envelopes, or influence fields.",
        graph_node_types=("material_zone",),
    ),
    FamilyRequirement(
        name="attachment_or_socket_ports",
        description="Accessory sockets, weapon ports, cloth hooks, mount points, or link nodes expose attachments.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("socket", "port", "hook", "mount", "attach"),
        recommendation_template="Add accessory sockets, weapon ports, cloth hooks, mount points, or link nodes.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="morph_or_expression_markers",
        description="Morph targets, expression plates, face marks, blend labels, or pose labels show variation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("morph", "expression", "face", "blend", "label"),
        recommendation_template="Add morph targets, expression plates, face marks, blend labels, or pose labels.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="range_or_limit_guards",
        description="Rotation limits, hinge guards, stop plates, range rings, or constraint bands show safe motion.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("limit", "guard", "stop", "range", "constraint"),
        recommendation_template="Add rotation limits, hinge guards, stop plates, range rings, or constraint bands.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="animation_state_cues",
        description="Idle/walk/run markers, state tags, frame ticks, timing marks, or cycle cues identify states.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("idle", "walk", "run", "state", "cycle"),
        recommendation_template="Add idle/walk/run markers, state tags, frame ticks, timing marks, or cycle cues.",
        graph_node_types=("decal_zone", "wear_zone"),
    ),
)


_RIG_COMPONENT_LIBRARY_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="component_catalog",
        description="A named rig-component catalog, module list, component IDs, or library index defines available pieces.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("catalog", "library", "component", "module", "id"),
        recommendation_template="Add a named rig-component catalog, module list, component IDs, or library index.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="spine_component_chain",
        description="Spine components, vertebra links, torso chain segments, curve controls, or bend modules define axial motion.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("spine", "vertebra", "torso", "curve", "bend"),
        recommendation_template="Add spine components, vertebra links, torso chain segments, curve controls, or bend modules.",
        graph_node_types=("rail", "hinge"),
    ),
    FamilyRequirement(
        name="limb_component_chain",
        description="Limb components, arm/leg modules, upper/lower segments, twist links, or paired side variants define appendages.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("limb", "arm", "leg", "twist", "side"),
        recommendation_template="Add limb components, arm/leg modules, upper/lower segments, twist links, or paired side variants.",
        graph_node_types=("rail", "mount"),
    ),
    FamilyRequirement(
        name="digit_component_chain",
        description="Digit components, finger/toe chains, phalanx links, claw variants, or repeat counts define small appendages.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("digit", "finger", "toe", "phalanx", "repeat"),
        recommendation_template="Add digit components, finger/toe chains, phalanx links, claw variants, or repeat counts.",
        graph_node_types=("fastener", "rail"),
    ),
    FamilyRequirement(
        name="mechanical_joint_components",
        description="Mechanical joints, hinges, pistons, servo pivots, actuator ports, or hard-limit collars support machines.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("mech", "hinge", "piston", "servo", "actuator"),
        recommendation_template="Add mechanical joints, hinges, pistons, servo pivots, actuator ports, or hard-limit collars.",
        graph_node_types=("hinge", "socket"),
    ),
    FamilyRequirement(
        name="wing_or_tentacle_chains",
        description="Wing chains, tentacle chains, fin bones, membrane anchors, spline links, or flexible segments support non-humanoids.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wing", "tentacle", "fin", "membrane", "spline"),
        recommendation_template="Add wing chains, tentacle chains, fin bones, membrane anchors, spline links, or flexible segments.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="connector_socket_contracts",
        description="Connector sockets, parent/child ports, orientation axes, attach rules, or module contracts make composition deterministic.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("connector", "socket", "parent", "axis", "contract"),
        recommendation_template="Add connector sockets, parent/child ports, orientation axes, attach rules, or module contracts.",
        graph_node_types=("socket", "guard"),
    ),
    FamilyRequirement(
        name="ik_fk_control_templates",
        description="IK/FK templates, pole-vector handles, control shapes, constraint presets, or target ports expose control rigs.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("ik", "fk", "pole", "constraint", "target"),
        recommendation_template="Add IK/FK templates, pole-vector handles, control shapes, constraint presets, or target ports.",
        graph_node_types=("handle", "socket"),
    ),
    FamilyRequirement(
        name="typed_rig_output_slots",
        description="Typed Rig outputs, skeleton ports, skin-weight channels, component exports, or TypedBundle slots define deliverables.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("rig", "skeleton", "skin", "export", "typedbundle"),
        recommendation_template="Add Typed Rig outputs, skeleton ports, skin-weight channels, component exports, or TypedBundle slots.",
        graph_node_types=("material_zone", "socket"),
    ),
    FamilyRequirement(
        name="component_cycle_guards",
        description="Cycle guards, compatibility checks, version locks, invalid-link badges, or recursion limits reject bad modules.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cycle", "compat", "version", "invalid", "recursion"),
        recommendation_template="Add cycle guards, compatibility checks, version locks, invalid-link badges, or recursion limits.",
        graph_node_types=("guard", "trim"),
    ),
)


_MORPH_TARGET_DATABASE_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="morph_target_catalog",
        description="A morph target catalog, target IDs, shape-key list, blendshape table, or morph index defines available deltas.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("catalog", "target", "shape", "blendshape", "index"),
        recommendation_template="Add a morph target catalog, target IDs, shape-key list, blendshape table, or morph index.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="facial_expression_set",
        description="Expression targets, brows, eyelids, mouth shapes, cheek puffs, or emotion slots define face variation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("expression", "brow", "eyelid", "mouth", "emotion"),
        recommendation_template="Add expression targets, brows, eyelids, mouth shapes, cheek puffs, or emotion slots.",
        graph_node_types=("decal_zone", "material_zone"),
    ),
    FamilyRequirement(
        name="viseme_or_lipsync_set",
        description="Visemes, lip-sync shapes, phoneme slots, jaw opens, or mouth-pose rows support dialogue.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("viseme", "lip", "phoneme", "jaw", "dialogue"),
        recommendation_template="Add visemes, lip-sync shapes, phoneme slots, jaw opens, or mouth-pose rows.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="body_shape_delta_set",
        description="Body deltas, muscle/fat/height variants, silhouette sliders, proportion offsets, or age deltas define body variation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("body", "muscle", "height", "proportion", "age"),
        recommendation_template="Add body deltas, muscle/fat/height variants, silhouette sliders, proportion offsets, or age deltas.",
        graph_node_types=("material_zone", "rail"),
    ),
    FamilyRequirement(
        name="corrective_shape_set",
        description="Corrective shapes, joint correctives, pose-space deltas, shoulder/knee fixes, or deformation repairs preserve motion.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("corrective", "joint", "pose", "shoulder", "knee"),
        recommendation_template="Add corrective shapes, joint correctives, pose-space deltas, shoulder/knee fixes, or deformation repairs.",
        graph_node_types=("panel", "guard"),
    ),
    FamilyRequirement(
        name="region_mask_bindings",
        description="Region masks, face/body zones, vertex groups, influence masks, or material IDs bind deltas to anatomy.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("region", "mask", "vertex", "influence", "material"),
        recommendation_template="Add region masks, face/body zones, vertex groups, influence masks, or material IDs.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="delta_vector_channels",
        description="Delta vectors, tangent channels, normal offsets, sparse deltas, or compression channels store morph data.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("delta", "vector", "normal", "sparse", "compress"),
        recommendation_template="Add delta vectors, tangent channels, normal offsets, sparse deltas, or compression channels.",
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="symmetry_mirror_rules",
        description="Mirror rules, left/right pairs, symmetry locks, split targets, or side selectors define mirrored authoring.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("mirror", "left", "right", "symmetry", "side"),
        recommendation_template="Add mirror rules, left/right pairs, symmetry locks, split targets, or side selectors.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="rig_anatomy_compatibility",
        description="Rig/anatomy compatibility, topology version locks, binding guards, retarget labels, or invalid-delta badges reject bad morphs.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("rig", "anatomy", "topology", "retarget", "invalid"),
        recommendation_template="Add rig/anatomy compatibility, topology version locks, binding guards, retarget labels, or invalid-delta badges.",
        graph_node_types=("guard", "socket"),
    ),
    FamilyRequirement(
        name="morph_iteration_wear_masks",
        description="Sculpt revisions, expression review marks, mask paint, delta cleanup, or blendshape iteration wear show authoring.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "review", "paint", "cleanup", "wear"),
        recommendation_template="Add sculpt revisions, expression review marks, mask paint, delta cleanup, or blendshape iteration wear.",
        graph_node_types=("wear_zone",),
    ),
)


_ANIMATION_LIBRARY_BINDING_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="clip_catalog",
        description="Clip catalogs, animation IDs, named clips, source files, or library rows define available motion.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("clip", "catalog", "animation", "source", "library"),
        recommendation_template="Add clip catalogs, animation IDs, named clips, source files, or library rows.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="pose_library",
        description="Pose libraries, key poses, holds, stances, weapon poses, or expression poses define static anchors.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("pose", "hold", "stance", "weapon", "expression"),
        recommendation_template="Add pose libraries, key poses, holds, stances, weapon poses, or expression poses.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="locomotion_state_set",
        description="Idle, walk, run, strafe, jump, land, or locomotion states define movement coverage.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("idle", "walk", "run", "strafe", "jump"),
        recommendation_template="Add idle, walk, run, strafe, jump, land, or locomotion states.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="blend_tree_or_transition_graph",
        description="Blend trees, transition graphs, state links, thresholds, or crossfade rules connect clips.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("blend", "transition", "state", "threshold", "crossfade"),
        recommendation_template="Add blend trees, transition graphs, state links, thresholds, or crossfade rules.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="event_marker_tracks",
        description="Event tracks, footstep markers, hit frames, notifies, sound cues, or gameplay tags bind timing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("event", "footstep", "hit", "notify", "cue"),
        recommendation_template="Add event tracks, footstep markers, hit frames, notifies, sound cues, or gameplay tags.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="root_motion_channels",
        description="Root motion channels, velocity curves, trajectory paths, facing data, or stride vectors describe displacement.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("root", "motion", "velocity", "trajectory", "stride"),
        recommendation_template="Add root motion channels, velocity curves, trajectory paths, facing data, or stride vectors.",
        graph_node_types=("rail", "material_zone"),
    ),
    FamilyRequirement(
        name="rig_binding_slots",
        description="Rig binding slots, skeleton IDs, retarget profiles, bone ports, or clip-to-rig maps attach motion.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("rig", "skeleton", "retarget", "bone", "bind"),
        recommendation_template="Add rig binding slots, skeleton IDs, retarget profiles, bone ports, or clip-to-rig maps.",
        graph_node_types=("socket", "guard"),
    ),
    FamilyRequirement(
        name="additive_layer_stack",
        description="Additive layers, aim offsets, upper-body overlays, facial layers, or motion masks compose animation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("additive", "aim", "overlay", "facial", "mask"),
        recommendation_template="Add additive layers, aim offsets, upper-body overlays, facial layers, or motion masks.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="preview_or_timing_outputs",
        description="Preview outputs, timing strips, frame ticks, loop badges, or duration markers expose results.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("preview", "timing", "frame", "loop", "duration"),
        recommendation_template="Add preview outputs, timing strips, frame ticks, loop badges, or duration markers.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="animation_iteration_wear_masks",
        description="Timing edits, binding revisions, curve cleanup, marker paint, or animation review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("edit", "revision", "cleanup", "paint", "wear"),
        recommendation_template="Add timing edits, binding revisions, curve cleanup, marker paint, or animation review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_RETARGETING_PACK_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="source_target_skeletons",
        description="Source and target skeletons, canonical rigs, rest skeletons, or source/target IDs define endpoints.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("source", "target", "skeleton", "canonical", "rig"),
        recommendation_template="Add source and target skeletons, canonical rigs, rest skeletons, or source/target IDs.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="bone_mapping_table",
        description="Bone maps, name pairs, parent links, chain maps, or unmapped-bone lists define correspondence.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("bone", "map", "pair", "parent", "unmapped"),
        recommendation_template="Add bone maps, name pairs, parent links, chain maps, or unmapped-bone lists.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="rest_pose_alignment",
        description="Rest pose alignment, T/A-pose offsets, orientation axes, bind-pose deltas, or neutral pose markers align rigs.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("rest", "pose", "axis", "bind", "neutral"),
        recommendation_template="Add rest pose alignment, T/A-pose offsets, orientation axes, bind-pose deltas, or neutral pose markers.",
        graph_node_types=("rail", "guard"),
    ),
    FamilyRequirement(
        name="scale_proportion_compensation",
        description="Scale compensation, limb ratios, stride scaling, height offsets, or proportion remaps preserve motion.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("scale", "ratio", "stride", "height", "proportion"),
        recommendation_template="Add scale compensation, limb ratios, stride scaling, height offsets, or proportion remaps.",
        graph_node_types=("material_zone", "rail"),
    ),
    FamilyRequirement(
        name="coordinate_space_conversion",
        description="Coordinate spaces, handedness, local/world transforms, forward/up axes, or quaternion conversion define math.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("coordinate", "handedness", "local", "forward", "quaternion"),
        recommendation_template="Add coordinate spaces, handedness, local/world transforms, forward/up axes, or quaternion conversion.",
        graph_node_types=("guard", "panel"),
    ),
    FamilyRequirement(
        name="ik_pole_remap",
        description="IK pole remaps, arm/leg targets, pole-vector swaps, control handles, or solver hints transfer controls.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("ik", "pole", "target", "control", "solver"),
        recommendation_template="Add IK pole remaps, arm/leg targets, pole-vector swaps, control handles, or solver hints.",
        graph_node_types=("handle", "socket"),
    ),
    FamilyRequirement(
        name="root_motion_retargeting",
        description="Root motion transfer, trajectory remap, stride locks, floor contact, or pelvis offsets preserve displacement.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("root", "trajectory", "stride", "floor", "pelvis"),
        recommendation_template="Add root motion transfer, trajectory remap, stride locks, floor contact, or pelvis offsets.",
        graph_node_types=("rail", "material_zone"),
    ),
    FamilyRequirement(
        name="constraint_or_limit_transfer",
        description="Constraint transfer, joint limits, rotation clamps, twist ranges, or motion envelopes preserve validity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("constraint", "limit", "rotation", "twist", "envelope"),
        recommendation_template="Add constraint transfer, joint limits, rotation clamps, twist ranges, or motion envelopes.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="compatibility_validation_guards",
        description="Compatibility guards, missing-bone errors, topology checks, version locks, or validation badges reject bad maps.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("compat", "missing", "topology", "version", "validation"),
        recommendation_template="Add compatibility guards, missing-bone errors, topology checks, version locks, or validation badges.",
        graph_node_types=("guard", "socket"),
    ),
    FamilyRequirement(
        name="retarget_iteration_wear_masks",
        description="Mapping revisions, foot-slide fixes, pose corrections, contact paint, or retarget review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "slide", "correction", "contact", "wear"),
        recommendation_template="Add mapping revisions, foot-slide fixes, pose corrections, contact paint, or retarget review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_CHARACTER_EQUIPMENT_BINDING_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="body_slot_map",
        description="Body slot maps, named slots, armor regions, attach IDs, or loadout channels define where equipment binds.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("slot", "armor", "attach", "loadout", "body"),
        recommendation_template="Add body slot maps, named slots, armor regions, attach IDs, or loadout channels.",
        graph_node_types=("panel", "material_zone"),
    ),
    FamilyRequirement(
        name="weapon_or_tool_sockets",
        description="Weapon sockets, tool ports, hand grips, holster pivots, or aim offsets bind carried items.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("weapon", "tool", "hand", "holster", "aim"),
        recommendation_template="Add weapon sockets, tool ports, hand grips, holster pivots, or aim offsets.",
        graph_node_types=("socket", "handle"),
    ),
    FamilyRequirement(
        name="armor_or_outfit_layers",
        description="Armor layers, outfit shells, garment slots, body overlays, or clothing order define wearable structure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("armor", "outfit", "garment", "overlay", "clothing"),
        recommendation_template="Add armor layers, outfit shells, garment slots, body overlays, or clothing order.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="attachment_offset_frames",
        description="Attachment offsets, local frames, rotation pivots, scale anchors, or bind transforms position equipment.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("offset", "frame", "pivot", "anchor", "transform"),
        recommendation_template="Add attachment offsets, local frames, rotation pivots, scale anchors, or bind transforms.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="clearance_or_collision_volumes",
        description="Clearance volumes, collision guards, clipping masks, shoulder/hip envelopes, or swing bounds prevent intersections.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("clearance", "collision", "clip", "envelope", "bounds"),
        recommendation_template="Add clearance volumes, collision guards, clipping masks, shoulder/hip envelopes, or swing bounds.",
        graph_node_types=("guard", "primary_volume"),
    ),
    FamilyRequirement(
        name="loadout_variant_sets",
        description="Loadout variants, equipment sets, alternate skins, style variants, or upgrade slots define options.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("variant", "set", "skin", "upgrade", "alternate"),
        recommendation_template="Add loadout variants, equipment sets, alternate skins, style variants, or upgrade slots.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="rig_anatomy_binding_rules",
        description="Rig/anatomy binding rules, bone sockets, body-region refs, retarget labels, or topology locks ensure compatibility.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("rig", "bone", "anatomy", "retarget", "topology"),
        recommendation_template="Add rig/anatomy binding rules, bone sockets, body-region refs, retarget labels, or topology locks.",
        graph_node_types=("socket", "guard"),
    ),
    FamilyRequirement(
        name="visibility_or_state_masks",
        description="Visibility masks, equip states, hide rules, swap tags, or damage visibility define runtime toggles.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("visibility", "state", "hide", "swap", "damage"),
        recommendation_template="Add visibility masks, equip states, hide rules, swap tags, or damage visibility.",
        graph_node_types=("decal_zone", "material_zone"),
    ),
    FamilyRequirement(
        name="compatibility_or_failure_guards",
        description="Compatibility guards, missing-slot warnings, invalid loadout badges, clipping warnings, or fit checks reject bad equipment.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("compat", "missing", "invalid", "warning", "fit"),
        recommendation_template="Add compatibility guards, missing-slot warnings, invalid loadout badges, clipping warnings, or fit checks.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="equipment_iteration_wear_masks",
        description="Fit revisions, socket paint, strap rub, holster wear, or loadout review marks show equipment iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "paint", "rub", "holster", "wear"),
        recommendation_template="Add fit revisions, socket paint, strap rub, holster wear, or loadout review marks.",
        graph_node_types=("wear_zone",),
    ),
)


_GAMEPLAY_ANIMATION_CONTROLLER_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="input_action_map",
        description="Input action maps, command IDs, gameplay tags, input axes, or trigger events drive controller state.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("input", "action", "command", "tag", "trigger"),
        recommendation_template="Add input action maps, command IDs, gameplay tags, input axes, or trigger events.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="controller_state_graph",
        description="Controller states, state machines, locomotion/combat nodes, ability states, or graph hubs define logic.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("state", "machine", "locomotion", "combat", "ability"),
        recommendation_template="Add controller states, state machines, locomotion/combat nodes, ability states, or graph hubs.",
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="animation_parameter_set",
        description="Animation parameters, speed/turn values, booleans, enums, weights, or curve inputs drive blending.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("parameter", "speed", "turn", "boolean", "weight"),
        recommendation_template="Add animation parameters, speed/turn values, booleans, enums, weights, or curve inputs.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="transition_rule_table",
        description="Transition rules, guards, thresholds, cooldowns, priorities, or crossfade settings connect states.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("transition", "guard", "threshold", "cooldown", "priority"),
        recommendation_template="Add transition rules, guards, thresholds, cooldowns, priorities, or crossfade settings.",
        graph_node_types=("guard", "rail"),
    ),
    FamilyRequirement(
        name="locomotion_blend_controls",
        description="Locomotion blends, strafing controls, turn-in-place, acceleration curves, or gait selectors tune movement.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("blend", "strafe", "turn", "acceleration", "gait"),
        recommendation_template="Add locomotion blends, strafing controls, turn-in-place, acceleration curves, or gait selectors.",
        graph_node_types=("rail", "material_zone"),
    ),
    FamilyRequirement(
        name="combat_or_ability_layers",
        description="Combat layers, ability states, montage slots, upper-body masks, attack chains, or cancel windows define actions.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("combat", "ability", "montage", "attack", "cancel"),
        recommendation_template="Add combat layers, ability states, montage slots, upper-body masks, attack chains, or cancel windows.",
        graph_node_types=("material_zone", "socket"),
    ),
    FamilyRequirement(
        name="event_output_bindings",
        description="Event outputs, gameplay notifies, hit windows, footstep events, SFX/VFX cues, or callback ports expose timing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("event", "notify", "hit", "footstep", "callback"),
        recommendation_template="Add event outputs, gameplay notifies, hit windows, footstep events, SFX/VFX cues, or callback ports.",
        graph_node_types=("socket", "fastener"),
    ),
    FamilyRequirement(
        name="motion_matching_slots",
        description="Motion matching slots, pose queries, trajectory samples, feature vectors, or search windows support advanced selection.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("matching", "query", "trajectory", "vector", "search"),
        recommendation_template="Add motion matching slots, pose queries, trajectory samples, feature vectors, or search windows.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="reachability_or_dead_state_guards",
        description="Reachability checks, dead-state guards, invalid transition markers, cycle limits, or missing clip warnings reject bad controllers.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("reachable", "dead", "invalid", "cycle", "missing"),
        recommendation_template="Add reachability checks, dead-state guards, invalid transition markers, cycle limits, or missing clip warnings.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="controller_iteration_wear_masks",
        description="Tuning revisions, transition edits, state review marks, curve paint, or controller wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("tuning", "revision", "edit", "paint", "wear"),
        recommendation_template="Add tuning revisions, transition edits, state review marks, curve paint, or controller wear.",
        graph_node_types=("wear_zone",),
    ),
)


_PROCEDURAL_FACIAL_RIG_PACK_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="facial_control_board",
        description="A facial control board, UI plate, control groups, named channels, or rig panel defines the face rig surface.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("control", "board", "channel", "panel", "rig"),
        recommendation_template="Add a facial control board, UI plate, control groups, named channels, or rig panel.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="jaw_and_mouth_controls",
        description="Jaw controls, mouth open/close, lip corners, mouth width, or smile/frown handles drive the mouth.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("jaw", "mouth", "lip", "smile", "frown"),
        recommendation_template="Add jaw controls, mouth open/close, lip corners, mouth width, or smile/frown handles.",
        graph_node_types=("handle", "socket"),
    ),
    FamilyRequirement(
        name="eye_aim_and_lid_controls",
        description="Eye aim controls, eyelids, blinks, squints, pupil targets, or gaze handles drive eyes.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("eye", "lid", "blink", "squint", "gaze"),
        recommendation_template="Add eye aim controls, eyelids, blinks, squints, pupil targets, or gaze handles.",
        graph_node_types=("socket", "handle"),
    ),
    FamilyRequirement(
        name="brow_and_cheek_controls",
        description="Brow controls, cheek puffs, nose wrinkles, forehead sliders, or expression handles drive upper face.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("brow", "cheek", "nose", "forehead", "expression"),
        recommendation_template="Add brow controls, cheek puffs, nose wrinkles, forehead sliders, or expression handles.",
        graph_node_types=("handle", "decal_zone"),
    ),
    FamilyRequirement(
        name="viseme_expression_links",
        description="Viseme links, phoneme channels, expression links, emotion sets, or lipsync drivers connect morph data.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("viseme", "phoneme", "expression", "emotion", "lipsync"),
        recommendation_template="Add viseme links, phoneme channels, expression links, emotion sets, or lipsync drivers.",
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="morph_driver_bindings",
        description="Morph driver bindings, blendshape slots, shape-key ports, corrective hooks, or delta links bind deformations.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("morph", "blendshape", "shape", "corrective", "delta"),
        recommendation_template="Add morph driver bindings, blendshape slots, shape-key ports, corrective hooks, or delta links.",
        graph_node_types=("socket", "material_zone"),
    ),
    FamilyRequirement(
        name="face_sdf_mask_bindings",
        description="Face-SDF masks, ID regions, shadow masks, cheek/nose regions, or cel-shading bindings align style data.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sdf", "mask", "shadow", "cheek", "cel"),
        recommendation_template="Add Face-SDF masks, ID regions, shadow masks, cheek/nose regions, or cel-shading bindings.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="range_limit_guards",
        description="Range limits, clamp guards, asymmetry guards, invalid expression badges, or overstretch markers reject bad controls.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("range", "limit", "clamp", "invalid", "overstretch"),
        recommendation_template="Add range limits, clamp guards, asymmetry guards, invalid expression badges, or overstretch markers.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="preview_pose_outputs",
        description="Preview poses, expression thumbnails, test poses, neutral/extreme outputs, or face tiles show results.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("preview", "thumbnail", "neutral", "extreme", "tile"),
        recommendation_template="Add preview poses, expression thumbnails, test poses, neutral/extreme outputs, or face tiles.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="facial_rig_iteration_wear_masks",
        description="Control tuning, expression review marks, mask paint, lipsync edits, or facial-rig wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("tuning", "review", "paint", "edit", "wear"),
        recommendation_template="Add control tuning, expression review marks, mask paint, lipsync edits, or facial-rig wear.",
        graph_node_types=("wear_zone",),
    ),
)


_HAIR_PROGRAM_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="scalp_or_groom_regions",
        description="Scalp regions, groom masks, parting zones, hairline bands, or growth regions anchor roots.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("scalp", "groom", "parting", "hairline", "growth"),
        recommendation_template="Add scalp regions, groom masks, parting zones, hairline bands, or growth regions.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="strand_grammar",
        description="Strand grammar, guide curves, strand groups, clumps, or procedural hair rules define structure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("strand", "guide", "group", "clump", "rule"),
        recommendation_template="Add strand grammar, guide curves, strand groups, clumps, or procedural hair rules.",
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="root_density_masks",
        description="Root density masks, follicle maps, emission points, density fields, or sparse regions control placement.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("root", "density", "follicle", "emission", "sparse"),
        recommendation_template="Add root density masks, follicle maps, emission points, density fields, or sparse regions.",
        graph_node_types=("decal_zone", "material_zone"),
    ),
    FamilyRequirement(
        name="length_distribution_controls",
        description="Length distributions, min/max lengths, taper curves, bang lengths, or cut guides shape silhouette.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("length", "distribution", "taper", "bang", "cut"),
        recommendation_template="Add length distributions, min/max lengths, taper curves, bang lengths, or cut guides.",
        graph_node_types=("rail", "guard"),
    ),
    FamilyRequirement(
        name="wave_or_curl_controls",
        description="Wave amplitude, frequency, curls, noise, frizz, or clump twist controls shape strands.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wave", "amplitude", "frequency", "curl", "frizz"),
        recommendation_template="Add wave amplitude, frequency, curls, noise, frizz, or clump twist controls.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="hair_card_outputs",
        description="Hair cards, card ribbons, alpha planes, LOD cards, or billboard strips define card output.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("card", "ribbon", "alpha", "lod", "billboard"),
        recommendation_template="Add hair cards, card ribbons, alpha planes, LOD cards, or billboard strips.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="strand_output_ports",
        description="Strand outputs, curve ports, groom exports, typed data slots, or simulation ports define strand output.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("output", "curve", "export", "typed", "simulation"),
        recommendation_template="Add strand outputs, curve ports, groom exports, typed data slots, or simulation ports.",
        graph_node_types=("socket", "rail"),
    ),
    FamilyRequirement(
        name="color_gradient_controls",
        description="Color gradients, root/tip colors, melanin ramps, dye zones, or material bands define appearance.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("color", "gradient", "root", "tip", "dye"),
        recommendation_template="Add color gradients, root/tip colors, melanin ramps, dye zones, or material bands.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="collision_or_clearance_guards",
        description="Collision guards, scalp offsets, shoulder clearance, hat masks, or penetration warnings reject bad grooms.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("collision", "clearance", "offset", "hat", "penetration"),
        recommendation_template="Add collision guards, scalp offsets, shoulder clearance, hat masks, or penetration warnings.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="hair_iteration_wear_masks",
        description="Groom revisions, comb marks, card edits, density paint, or hair-review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "comb", "edit", "paint", "wear"),
        recommendation_template="Add groom revisions, comb marks, card edits, density paint, or hair-review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_CLOTH_FABRIC_SIMULATION_PROGRAM_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="fabric_domain_or_panel_set",
        description="Fabric domains, cloth panels, garment sheets, cape surfaces, or simulation patches define the cloth body.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("fabric", "cloth", "panel", "sheet", "patch"),
        recommendation_template="Add fabric domains, cloth panels, garment sheets, cape surfaces, or simulation patches.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="mass_stiffness_damping_params",
        description="Mass, stiffness, damping, stretch/bend settings, or XPBD parameter rows define simulation behavior.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("mass", "stiffness", "damping", "stretch", "bend"),
        recommendation_template="Add mass, stiffness, damping, stretch/bend settings, or XPBD parameter rows.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="pin_or_anchor_constraints",
        description="Pins, anchors, fixed vertices, seam attachments, or tether constraints hold cloth in place.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("pin", "anchor", "fixed", "seam", "tether"),
        recommendation_template="Add pins, anchors, fixed vertices, seam attachments, or tether constraints.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="collision_or_body_volumes",
        description="Collision bodies, anatomy volumes, armor blockers, floor planes, or clearance shells prevent intersection.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("collision", "body", "armor", "floor", "clearance"),
        recommendation_template="Add collision bodies, anatomy volumes, armor blockers, floor planes, or clearance shells.",
        graph_node_types=("guard", "primary_volume"),
    ),
    FamilyRequirement(
        name="gravity_wind_force_fields",
        description="Gravity vectors, wind fields, force arrows, pressure zones, or airflow masks direct settling.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("gravity", "wind", "force", "pressure", "airflow"),
        recommendation_template="Add gravity vectors, wind fields, force arrows, pressure zones, or airflow masks.",
        graph_node_types=("rail", "material_zone"),
    ),
    FamilyRequirement(
        name="settling_or_solve_passes",
        description="Settling passes, solve iterations, substeps, rest-state outputs, or deterministic bake markers define simulation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("settle", "solve", "substep", "rest", "bake"),
        recommendation_template="Add settling passes, solve iterations, substeps, rest-state outputs, or deterministic bake markers.",
        graph_node_types=("fastener", "panel"),
    ),
    FamilyRequirement(
        name="wrinkle_fold_outputs",
        description="Wrinkle fields, fold curves, tension lines, sag bands, or crease outputs show simulated fabric response.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wrinkle", "fold", "tension", "sag", "crease"),
        recommendation_template="Add wrinkle fields, fold curves, tension lines, sag bands, or crease outputs.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="material_pattern_zones",
        description="Fabric material zones, weave masks, pattern IDs, thickness rows, or anisotropy bands define surface.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("material", "weave", "pattern", "thickness", "anisotropy"),
        recommendation_template="Add fabric material zones, weave masks, pattern IDs, thickness rows, or anisotropy bands.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="solver_validation_guards",
        description="Solver guards, overstretch warnings, collision miss badges, invalid pin markers, or exploding-cloth guards reject bad sims.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "overstretch", "warning", "invalid", "explode"),
        recommendation_template="Add solver guards, overstretch warnings, collision miss badges, invalid pin markers, or exploding-cloth guards.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="cloth_iteration_wear_masks",
        description="Fit revisions, cloth paint, seam rub, fold edits, or simulation review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "paint", "rub", "edit", "wear"),
        recommendation_template="Add fit revisions, cloth paint, seam rub, fold edits, or simulation review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_FLUID_FORWARD_VOLUME_PROGRAM_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="fluid_volume_domain",
        description="Fluid volume domains, sparse grids, VDB bounds, simulation boxes, or clip extents define the field.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("volume", "grid", "vdb", "bounds", "extent"),
        recommendation_template="Add fluid volume domains, sparse grids, VDB bounds, simulation boxes, or clip extents.",
        graph_node_types=("primary_volume", "guard"),
    ),
    FamilyRequirement(
        name="density_temperature_velocity_channels",
        description="Density, temperature, velocity, fuel, color, or named fluid channels define volume data.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("density", "temperature", "velocity", "fuel", "channel"),
        recommendation_template="Add density, temperature, velocity, fuel, color, or named fluid channels.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="emitter_or_source_set",
        description="Emitters, sources, injectors, inflow ports, splash origins, or burn sources add fluid.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("emitter", "source", "inject", "inflow", "splash"),
        recommendation_template="Add emitters, sources, injectors, inflow ports, splash origins, or burn sources.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="advection_or_force_fields",
        description="Advection vectors, force fields, turbulence, vortices, wind, or buoyancy controls drive flow.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("advection", "force", "turbulence", "vortex", "buoyancy"),
        recommendation_template="Add advection vectors, force fields, turbulence, vortices, wind, or buoyancy controls.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="surface_or_isosurface_controls",
        description="Surface thresholds, isosurface controls, water levels, foam bands, or contour tags define extraction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("surface", "iso", "threshold", "foam", "contour"),
        recommendation_template="Add surface thresholds, isosurface controls, water levels, foam bands, or contour tags.",
        graph_node_types=("panel", "material_zone"),
    ),
    FamilyRequirement(
        name="particle_or_mesh_outputs",
        description="Particle outputs, mesh outputs, spray points, volume-to-mesh ports, or render outputs define deliverables.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("particle", "mesh", "spray", "output", "render"),
        recommendation_template="Add particle outputs, mesh outputs, spray points, volume-to-mesh ports, or render outputs.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="cache_or_sample_tiles",
        description="Cache tiles, sample planes, resolution tags, time slices, or debug slices expose field state.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cache", "sample", "resolution", "time", "debug"),
        recommendation_template="Add cache tiles, sample planes, resolution tags, time slices, or debug slices.",
        graph_node_types=("panel", "fastener"),
    ),
    FamilyRequirement(
        name="collision_boundary_guards",
        description="Collision boundaries, domain guards, outflow edges, clamp planes, or invalid volume badges constrain the field.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("collision", "boundary", "outflow", "clamp", "invalid"),
        recommendation_template="Add collision boundaries, domain guards, outflow edges, clamp planes, or invalid volume badges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="fluid_style_material_regions",
        description="Fluid material regions, smoke/fire/water labels, opacity bands, color ramps, or foam masks define appearance.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("material", "smoke", "fire", "water", "opacity"),
        recommendation_template="Add fluid material regions, smoke/fire/water labels, opacity bands, color ramps, or foam masks.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="fluid_iteration_wear_masks",
        description="Solve revisions, advection edits, cache residue, splash paint, or fluid review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "advection", "residue", "paint", "wear"),
        recommendation_template="Add solve revisions, advection edits, cache residue, splash paint, or fluid review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_CONSTRUCTION_GRAMMAR_KIT_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="module_catalog",
        description="Module catalogs, kit pieces, block libraries, facade units, or structural parts define available construction atoms.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("module", "catalog", "piece", "block", "part"),
        recommendation_template="Add module catalogs, kit pieces, block libraries, facade units, or structural parts.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="snap_grid_or_axes",
        description="Snap grids, unit axes, cell sizes, construction planes, or origin markers define assembly coordinates.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("snap", "grid", "axis", "cell", "origin"),
        recommendation_template="Add snap grids, unit axes, cell sizes, construction planes, or origin markers.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="connector_socket_rules",
        description="Connector sockets, plug types, socket colors, tabs, or joint rules define how modules connect.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("connector", "socket", "plug", "tab", "joint"),
        recommendation_template="Add connector sockets, plug types, socket colors, tabs, or joint rules.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="allowed_adjacency_rules",
        description="Allowed adjacencies, neighbor tables, edge rules, forbidden pairs, or compatibility matrices constrain composition.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("adjacency", "neighbor", "edge", "forbidden", "compat"),
        recommendation_template="Add allowed adjacencies, neighbor tables, edge rules, forbidden pairs, or compatibility matrices.",
        graph_node_types=("panel", "guard"),
    ),
    FamilyRequirement(
        name="repeat_split_assembly_rules",
        description="Repeat rules, split rules, stack rules, grammar productions, or assembly recipes grow structures.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("repeat", "split", "stack", "production", "recipe"),
        recommendation_template="Add repeat rules, split rules, stack rules, grammar productions, or assembly recipes.",
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="kitbash_variant_slots",
        description="Kitbash variants, optional trims, alternate modules, facade swaps, or style slots support variation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("variant", "optional", "trim", "alternate", "swap"),
        recommendation_template="Add kitbash variants, optional trims, alternate modules, facade swaps, or style slots.",
        graph_node_types=("socket", "material_zone"),
    ),
    FamilyRequirement(
        name="structural_validation_guards",
        description="Structural guards, unsupported-span warnings, collision checks, overhang limits, or rule-cycle markers reject bad builds.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("structural", "unsupported", "collision", "overhang", "cycle"),
        recommendation_template="Add structural guards, unsupported-span warnings, collision checks, overhang limits, or rule-cycle markers.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="buildable_output_ports",
        description="Buildable outputs, prefab ports, mesh assembly outputs, tile outputs, or export slots define deliverables.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("buildable", "prefab", "mesh", "tile", "export"),
        recommendation_template="Add buildable outputs, prefab ports, mesh assembly outputs, tile outputs, or export slots.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="scale_metric_markers",
        description="Scale metrics, unit rulers, human-scale gauges, brick dimensions, or clearance rulers define physical scale.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("scale", "unit", "ruler", "brick", "clearance"),
        recommendation_template="Add scale metrics, unit rulers, human-scale gauges, brick dimensions, or clearance rulers.",
        graph_node_types=("decal_zone", "rail"),
    ),
    FamilyRequirement(
        name="grammar_iteration_wear_masks",
        description="Rule revisions, kit marks, rejected pieces, adjacency edits, or grammar review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "mark", "reject", "edit", "wear"),
        recommendation_template="Add rule revisions, kit marks, rejected pieces, adjacency edits, or grammar review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_CREATURE_APPENDAGE_PROGRAM_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="appendage_socket_map",
        description="Appendage sockets, shoulder/hip mounts, spine anchors, root frames, or attachment pads place appendages.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("socket", "mount", "anchor", "root", "attachment"),
        recommendation_template="Add appendage sockets, shoulder/hip mounts, spine anchors, root frames, or attachment pads.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="joint_chain_or_segments",
        description="Joint chains, bones, phalanxes, segments, or articulation links define movement structure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("joint", "bone", "phalanx", "segment", "articulation"),
        recommendation_template="Add joint chains, bones, phalanxes, segments, or articulation links.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="segment_profile_controls",
        description="Segment profiles, taper curves, radius ramps, length controls, or generalized cylinders define appendage shape.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("profile", "taper", "radius", "length", "cylinder"),
        recommendation_template="Add segment profiles, taper curves, radius ramps, length controls, or generalized cylinders.",
        graph_node_types=("primary_volume", "rail"),
    ),
    FamilyRequirement(
        name="wing_tail_tentacle_variants",
        description="Wing, tail, tentacle, horn, claw, fin, or antenna variants broaden appendage families.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("wing", "tail", "tentacle", "horn", "claw"),
        recommendation_template="Add wing, tail, tentacle, horn, claw, fin, or antenna variants.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="surface_feature_maps",
        description="Scales, feathers, membranes, ridges, spikes, suckers, or shell plates define appendage surface detail.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("scale", "feather", "membrane", "ridge", "spike"),
        recommendation_template="Add scales, feathers, membranes, ridges, spikes, suckers, or shell plates.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="symmetry_mirror_rules",
        description="Symmetry pairs, mirror rules, left/right bindings, radial repeats, or handedness tags coordinate appendages.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("symmetry", "mirror", "left", "right", "radial"),
        recommendation_template="Add symmetry pairs, mirror rules, left/right bindings, radial repeats, or handedness tags.",
        graph_node_types=("rail", "guard"),
    ),
    FamilyRequirement(
        name="articulation_range_controls",
        description="Rotation limits, bend ranges, IK goals, flap arcs, curl controls, or pose limits define motion range.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("rotation", "bend", "ik", "flap", "curl"),
        recommendation_template="Add rotation limits, bend ranges, IK goals, flap arcs, curl controls, or pose limits.",
        graph_node_types=("guard", "rail"),
    ),
    FamilyRequirement(
        name="muscle_or_volume_bands",
        description="Muscle bands, tendon lines, volume bulges, cartilage pads, or knuckle masses preserve organic anatomy.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("muscle", "tendon", "volume", "cartilage", "knuckle"),
        recommendation_template="Add muscle bands, tendon lines, volume bulges, cartilage pads, or knuckle masses.",
        graph_node_types=("primary_volume", "trim"),
    ),
    FamilyRequirement(
        name="attachment_clearance_guards",
        description="Attachment guards, body clearance, penetration checks, socket mismatch warnings, or fit limits reject bad appendages.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("clearance", "penetration", "mismatch", "warning", "fit"),
        recommendation_template="Add attachment guards, body clearance, penetration checks, socket mismatch warnings, or fit limits.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="appendage_iteration_wear_masks",
        description="Variant revisions, anatomy paint, fit scuffs, surface edits, or appendage review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "paint", "scuff", "edit", "wear"),
        recommendation_template="Add variant revisions, anatomy paint, fit scuffs, surface edits, or appendage review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_BODY_PART_PROCEDURAL_LIBRARY_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="body_part_catalog",
        description="Body-part catalogs, head/torso/hand/foot sets, organ cards, or anatomy modules define available parts.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("catalog", "head", "torso", "hand", "foot"),
        recommendation_template="Add body-part catalogs, head/torso/hand/foot sets, organ cards, or anatomy modules.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="anatomy_region_map",
        description="Anatomy regions, body zones, face regions, limb regions, or tissue labels map part domains.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("anatomy", "region", "zone", "face", "tissue"),
        recommendation_template="Add anatomy regions, body zones, face regions, limb regions, or tissue labels.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="organ_or_socket_map",
        description="Organ sockets, eye/mouth/ear ports, joint sockets, attachment points, or cavity markers define interfaces.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("organ", "socket", "eye", "mouth", "cavity"),
        recommendation_template="Add organ sockets, eye/mouth/ear ports, joint sockets, attachment points, or cavity markers.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="muscle_group_or_volume_bands",
        description="Muscle groups, volume bands, fat pads, tendon paths, or anatomical masses preserve form.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("muscle", "volume", "fat", "tendon", "mass"),
        recommendation_template="Add muscle groups, volume bands, fat pads, tendon paths, or anatomical masses.",
        graph_node_types=("primary_volume", "trim"),
    ),
    FamilyRequirement(
        name="landmark_loop_markers",
        description="Landmark loops, edge loops, facial landmarks, knuckle rings, or topology markers guide deformation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("landmark", "loop", "edge", "knuckle", "topology"),
        recommendation_template="Add landmark loops, edge loops, facial landmarks, knuckle rings, or topology markers.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="proportion_range_controls",
        description="Proportion ranges, scale sliders, age/sex/body-type spans, or measurement ticks define variation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("proportion", "scale", "age", "measurement", "range"),
        recommendation_template="Add proportion ranges, scale sliders, age/sex/body-type spans, or measurement ticks.",
        graph_node_types=("panel", "fastener"),
    ),
    FamilyRequirement(
        name="symmetry_and_pair_rules",
        description="Symmetry rules, paired parts, left/right bindings, mirror planes, or handedness constraints coordinate parts.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("symmetry", "pair", "left", "right", "mirror"),
        recommendation_template="Add symmetry rules, paired parts, left/right bindings, mirror planes, or handedness constraints.",
        graph_node_types=("rail", "guard"),
    ),
    FamilyRequirement(
        name="surface_zone_bindings",
        description="Skin zones, nail zones, sclera/iris masks, lip material bands, or surface bindings define appearance.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("skin", "nail", "sclera", "iris", "lip"),
        recommendation_template="Add skin zones, nail zones, sclera/iris masks, lip material bands, or surface bindings.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="compatibility_validation_guards",
        description="Compatibility guards, topology mismatch warnings, socket fit checks, scale limits, or invalid pair badges reject bad parts.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("compat", "mismatch", "fit", "limit", "invalid"),
        recommendation_template="Add compatibility guards, topology mismatch warnings, socket fit checks, scale limits, or invalid pair badges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="body_part_iteration_wear_masks",
        description="Sculpt revisions, anatomy paint, fit scuffs, landmark edits, or body-part review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "paint", "scuff", "edit", "wear"),
        recommendation_template="Add sculpt revisions, anatomy paint, fit scuffs, landmark edits, or body-part review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_MATERIAL_PRIMITIVE_LIBRARY_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="material_primitive_catalog",
        description="Material primitive catalogs, preset libraries, substance cards, swatch sets, or shader atoms define materials.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("material", "primitive", "catalog", "preset", "swatch"),
        recommendation_template="Add material primitive catalogs, preset libraries, substance cards, swatch sets, or shader atoms.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="physical_substance_taxonomy",
        description="Physical substances, metals, woods, stones, fabrics, liquids, or biological materials classify behavior.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("substance", "metal", "wood", "stone", "fabric"),
        recommendation_template="Add physical substances, metals, woods, stones, fabrics, liquids, or biological materials.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="pbr_channel_ranges",
        description="Basecolor, roughness, metallic, normal, ORM, height, or opacity channel ranges define PBR validity.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("basecolor", "roughness", "metallic", "normal", "orm"),
        recommendation_template="Add basecolor, roughness, metallic, normal, ORM, height, or opacity channel ranges.",
        graph_node_types=("panel", "material_zone"),
    ),
    FamilyRequirement(
        name="metal_dielectric_emissive_classes",
        description="Metal, dielectric, emissive, translucent, subsurface, or clearcoat classes define material families.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("metal", "dielectric", "emissive", "translucent", "clearcoat"),
        recommendation_template="Add metal, dielectric, emissive, translucent, subsurface, or clearcoat classes.",
        graph_node_types=("socket", "material_zone"),
    ),
    FamilyRequirement(
        name="procedural_parameter_ports",
        description="Procedural parameters, exposed knobs, seed ports, scale controls, or variation sliders author materials.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("parameter", "knob", "seed", "scale", "variation"),
        recommendation_template="Add procedural parameters, exposed knobs, seed ports, scale controls, or variation sliders.",
        graph_node_types=("socket", "fastener"),
    ),
    FamilyRequirement(
        name="smart_mask_bindings",
        description="Smart masks, curvature masks, AO masks, edge wear masks, or dirt selectors bind material layers.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("mask", "curvature", "ao", "edge", "dirt"),
        recommendation_template="Add smart masks, curvature masks, AO masks, edge wear masks, or dirt selectors.",
        graph_node_types=("decal_zone", "wear_zone"),
    ),
    FamilyRequirement(
        name="materialx_output_ports",
        description="MaterialX outputs, shader ports, texture set exports, renderer targets, or USD bindings define portability.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("materialx", "shader", "texture", "renderer", "usd"),
        recommendation_template="Add MaterialX outputs, shader ports, texture set exports, renderer targets, or USD bindings.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="pbr_validation_guards",
        description="PBR guards, invalid range warnings, energy-conservation checks, chart limits, or channel clamps reject bad materials.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "invalid", "energy", "chart", "clamp"),
        recommendation_template="Add PBR guards, invalid range warnings, energy-conservation checks, chart limits, or channel clamps.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="substance_variant_slots",
        description="Substance variants, age states, wet/dry states, clean/dirty alternates, or style swatches support variation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("variant", "age", "wet", "dirty", "style"),
        recommendation_template="Add substance variants, age states, wet/dry states, clean/dirty alternates, or style swatches.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="material_iteration_wear_masks",
        description="Material revisions, chart marks, bake residue, swatch scratches, or review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "chart", "bake", "scratch", "wear"),
        recommendation_template="Add material revisions, chart marks, bake residue, swatch scratches, or review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_STATEFUL_DESTRUCTIBLE_PROP_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="intact_primary_shell",
        description="An intact shell, casing, structure, hull, or full-health body defines the base state.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("intact", "shell", "casing", "structure", "health"),
        recommendation_template="Add an intact shell, casing, structure, hull, or full-health body.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="damage_state_markers",
        description="State plates, damage lights, health pips, stage markers, or condition labels show state.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("state", "damage", "health", "stage", "condition"),
        recommendation_template="Add state plates, damage lights, health pips, stage markers, or condition labels.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="fracture_or_break_lines",
        description="Fracture seams, break lines, crack paths, split grooves, or fault edges indicate failure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("fracture", "break", "crack", "split", "fault"),
        recommendation_template="Add fracture seams, break lines, crack paths, split grooves, or fault edges.",
        graph_node_types=("trim", "inset"),
    ),
    FamilyRequirement(
        name="detachable_or_fragment_zones",
        description="Fragments, detachable panels, shard clusters, chunk sockets, or debris pads define pieces.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("fragment", "detach", "shard", "chunk", "debris"),
        recommendation_template="Add fragments, detachable panels, shard clusters, chunk sockets, or debris pads.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="impact_or_weak_points",
        description="Weak points, impact plates, target nodes, damage sockets, or strike marks guide interaction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("weak", "impact", "target", "strike", "hit"),
        recommendation_template="Add weak points, impact plates, target nodes, damage sockets, or strike marks.",
        graph_node_types=("mount", "decal_zone"),
    ),
    FamilyRequirement(
        name="repair_or_rebuild_affordance",
        description="Repair ports, rebuild handles, weld pads, patch plates, or service sockets support recovery.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("repair", "rebuild", "weld", "patch", "service"),
        recommendation_template="Add repair ports, rebuild handles, weld pads, patch plates, or service sockets.",
        graph_node_types=("handle", "socket"),
    ),
    FamilyRequirement(
        name="state_transition_cues",
        description="Transition arrows, phase ticks, exposed layers, progress bands, or triggered plates show change.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("transition", "phase", "progress", "trigger", "change"),
        recommendation_template="Add transition arrows, phase ticks, exposed layers, progress bands, or triggered plates.",
        graph_node_types=("decal_zone", "material_zone"),
    ),
    FamilyRequirement(
        name="hazard_or_failure_boundary",
        description="Hazard bands, blast limits, warning rails, danger borders, or failure envelopes define risk.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("hazard", "blast", "warning", "danger", "failure"),
        recommendation_template="Add hazard bands, blast limits, warning rails, danger borders, or failure envelopes.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="debris_or_secondary_scatter",
        description="Loose debris, chips, bolts, splinters, dust piles, or shard scatter give scale.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("debris", "chip", "bolt", "splinter", "dust"),
        recommendation_template="Add loose debris, chips, bolts, splinters, dust piles, or shard scatter.",
        graph_node_types=("fastener", "mount"),
    ),
    FamilyRequirement(
        name="damage_wear_masks",
        description="Scorch, cracks, exposed cores, chipped paint, stress marks, or repair wear show history.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("scorch", "exposed", "chipped", "stress", "wear"),
        recommendation_template="Add scorch, cracks, exposed cores, chipped paint, stress marks, or repair wear.",
        graph_node_types=("wear_zone",),
    ),
)


_CLOTH_ATTACHMENT_FORM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="anchor_or_mount_points",
        description="Anchors, hooks, rings, pins, mounts, or tie points hold the cloth or attachment.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("anchor", "hook", "ring", "pin", "mount"),
        recommendation_template="Add anchors, hooks, rings, pins, mounts, or tie points.",
        graph_node_types=("mount", "socket"),
    ),
    FamilyRequirement(
        name="fabric_panel_or_drape",
        description="A fabric panel, drape, flag, cape sheet, banner field, or strap surface carries the form.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("fabric", "drape", "flag", "cape", "banner"),
        recommendation_template="Add a fabric panel, drape, flag, cape sheet, banner field, or strap surface.",
        graph_node_types=("panel", "primary_volume"),
    ),
    FamilyRequirement(
        name="seam_or_hem_lines",
        description="Seams, hems, stitch lines, edge binding, or reinforced edges make the cloth readable.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("seam", "hem", "stitch", "binding", "edge"),
        recommendation_template="Add seams, hems, stitch lines, edge binding, or reinforced edges.",
        graph_node_types=("trim", "inset"),
    ),
    FamilyRequirement(
        name="fold_or_tension_lines",
        description="Folds, wrinkles, tension paths, sag lines, or pleats show flexible material behavior.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("fold", "wrinkle", "tension", "sag", "pleat"),
        recommendation_template="Add folds, wrinkles, tension paths, sag lines, or pleats.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="attachment_hardware",
        description="Buckles, clips, straps, tethers, loops, or ties expose attachment logic.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("buckle", "clip", "strap", "tether", "loop"),
        recommendation_template="Add buckles, clips, straps, tethers, loops, or ties.",
        graph_node_types=("handle", "fastener"),
    ),
    FamilyRequirement(
        name="trim_or_border_detail",
        description="Borders, tassels, ropes, tabs, patches, or trim strips frame the cloth.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("border", "tassel", "rope", "tab", "patch"),
        recommendation_template="Add borders, tassels, ropes, tabs, patches, or trim strips.",
        graph_node_types=("trim", "decal_zone"),
    ),
    FamilyRequirement(
        name="motion_or_wind_cues",
        description="Wind arcs, trailing lines, flutter marks, motion ribs, or ghost edges show movement.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wind", "trail", "flutter", "motion", "ghost"),
        recommendation_template="Add wind arcs, trailing lines, flutter marks, motion ribs, or ghost edges.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="material_or_pattern_zone",
        description="Weave zones, color panels, pattern fields, material patches, or faction marks identify material.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("weave", "color", "pattern", "material", "faction"),
        recommendation_template="Add weave zones, color panels, pattern fields, material patches, or faction marks.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="collision_or_clearance_cues",
        description="Clearance arcs, safe gaps, collision pads, tied-back regions, or guide marks prevent ambiguity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("clearance", "gap", "collision", "tied", "guide"),
        recommendation_template="Add clearance arcs, safe gaps, collision pads, tied-back regions, or guide marks.",
        graph_node_types=("guard", "socket"),
    ),
    FamilyRequirement(
        name="cloth_wear_masks",
        description="Fraying, dirt, rubbed folds, torn hems, faded marks, or attachment wear show use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fray", "dirt", "rubbed", "torn", "faded"),
        recommendation_template="Add fraying, dirt, rubbed folds, torn hems, faded marks, or attachment wear.",
        graph_node_types=("wear_zone",),
    ),
)


_DOMAIN_KIT_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="kit_root_identity",
        description="A root tile, badge, base plate, category marker, or identity slab names the kit.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("root", "badge", "base", "category", "identity"),
        recommendation_template="Add a root tile, badge, base plate, category marker, or identity slab.",
        graph_node_types=("primary_volume", "decal_zone"),
    ),
    FamilyRequirement(
        name="canonical_part_set",
        description="Canonical pieces, parts, modules, archetypes, or kit members define the bundle.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("piece", "part", "module", "archetype", "member"),
        recommendation_template="Add canonical pieces, parts, modules, archetypes, or kit members.",
        graph_node_types=("panel", "mount"),
    ),
    FamilyRequirement(
        name="snap_ports_or_connectors",
        description="Snap ports, sockets, plugs, rails, or connector edges describe assembly.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("snap", "socket", "plug", "rail", "connector"),
        recommendation_template="Add snap ports, sockets, plugs, rails, or connector edges.",
        graph_node_types=("socket", "rail"),
    ),
    FamilyRequirement(
        name="variant_slots",
        description="Variant slots, swappable panels, option sockets, alternate caps, or branch pads show breadth.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("variant", "swap", "option", "alternate", "branch"),
        recommendation_template="Add variant slots, swappable panels, option sockets, alternate caps, or branch pads.",
        graph_node_types=("inset", "socket"),
    ),
    FamilyRequirement(
        name="scale_or_grid_reference",
        description="Scale markers, grid ticks, rulers, reference blocks, or unit labels keep pieces consistent.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("scale", "grid", "ruler", "reference", "unit"),
        recommendation_template="Add scale markers, grid ticks, rulers, reference blocks, or unit labels.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="style_or_material_rules",
        description="Style bands, material zones, palette strips, theme plates, or rule labels define consistency.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("style", "material", "palette", "theme", "rule"),
        recommendation_template="Add style bands, material zones, palette strips, theme plates, or rule labels.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="assembly_guides",
        description="Assembly arrows, path rails, ordering labels, alignment guides, or build tracks guide use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("assembly", "arrow", "order", "align", "track"),
        recommendation_template="Add assembly arrows, path rails, ordering labels, alignment guides, or build tracks.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="compatibility_or_dependency_markers",
        description="Compatibility tags, dependency links, version markers, blockers, or allowed-pair cues constrain use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("compat", "dependency", "version", "blocker", "pair"),
        recommendation_template="Add compatibility tags, dependency links, version markers, blockers, or allowed-pair cues.",
        graph_node_types=("decal_zone", "guard"),
    ),
    FamilyRequirement(
        name="library_labels",
        description="Labels, names, IDs, category plates, or index chips keep the kit browseable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("label", "name", "id", "category", "index"),
        recommendation_template="Add labels, names, IDs, category plates, or index chips.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="kit_usage_wear_masks",
        description="Repeated-edge wear, handled marks, socket rub, test-fit scuffs, or sample wear show usage.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "handled", "rub", "scuff", "sample"),
        recommendation_template="Add repeated-edge wear, handled marks, socket rub, test-fit scuffs, or sample wear.",
        graph_node_types=("wear_zone",),
    ),
)


_WORLD_SYSTEM_ASSEMBLY_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="root_world_footprint",
        description="A root world plate, map footprint, region bounds, or system canvas defines scope.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("root", "world", "map", "region", "canvas"),
        recommendation_template="Add a root world plate, map footprint, region bounds, or system canvas.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="layer_or_region_stack",
        description="Layers, regions, biomes, districts, strata, or nested zones show world composition.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("layer", "region", "biome", "district", "zone"),
        recommendation_template="Add layers, regions, biomes, districts, strata, or nested zones.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="connection_or_route_graph",
        description="Routes, graph edges, roads, links, nav paths, or corridors connect the system.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("route", "graph", "road", "link", "nav"),
        recommendation_template="Add routes, graph edges, roads, links, nav paths, or corridors.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="faction_or_rule_zones",
        description="Faction zones, rule areas, ownership plates, influence fields, or permissions define behavior.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("faction", "rule", "owner", "influence", "permission"),
        recommendation_template="Add faction zones, rule areas, ownership plates, influence fields, or permissions.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="objective_or_progression_chain",
        description="Quest chains, progression nodes, unlock paths, milestones, or beats make the system playable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("quest", "progression", "unlock", "milestone", "beat"),
        recommendation_template="Add quest chains, progression nodes, unlock paths, milestones, or beats.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="resource_or_spawn_distribution",
        description="Resources, spawn groups, population nodes, loot fields, or ecology points distribute content.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("resource", "spawn", "population", "loot", "ecology"),
        recommendation_template="Add resources, spawn groups, population nodes, loot fields, or ecology points.",
        graph_node_types=("fastener", "mount"),
    ),
    FamilyRequirement(
        name="landmarks_or_anchor_nodes",
        description="Landmarks, hubs, capitals, anchors, or central nodes give the system memory.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("landmark", "hub", "capital", "anchor", "node"),
        recommendation_template="Add landmarks, hubs, capitals, anchors, or central nodes.",
        graph_node_types=("mount", "primary_volume"),
    ),
    FamilyRequirement(
        name="boundary_or_transition_gates",
        description="Boundaries, gates, portals, thresholds, or transition bands define system edges.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("boundary", "gate", "portal", "threshold", "transition"),
        recommendation_template="Add boundaries, gates, portals, thresholds, or transition bands.",
        graph_node_types=("guard", "frame"),
    ),
    FamilyRequirement(
        name="labels_or_debug_cues",
        description="Labels, IDs, debug cues, legends, or color keys make the system inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("label", "id", "debug", "legend", "key"),
        recommendation_template="Add labels, IDs, debug cues, legends, or color keys.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="system_wear_or_usage_masks",
        description="Route wear, influence marks, traffic masks, heat, or occupancy wear show usage.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "traffic", "heat", "occupancy", "usage"),
        recommendation_template="Add route wear, influence marks, traffic masks, heat, or occupancy wear.",
        graph_node_types=("wear_zone",),
    ),
)


_SIMULATION_ENVIRONMENT_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="simulation_domain_bounds",
        description="Domain bounds, solver volume, fluid box, wind field, or simulation frame defines extent.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("domain", "solver", "volume", "field", "frame"),
        recommendation_template="Add domain bounds, solver volume, fluid box, wind field, or simulation frame.",
        graph_node_types=("primary_volume", "frame"),
    ),
    FamilyRequirement(
        name="emitter_or_force_sources",
        description="Emitters, sources, forces, vents, pumps, or origins inject energy into the system.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("emitter", "source", "force", "vent", "origin"),
        recommendation_template="Add emitters, sources, forces, vents, pumps, or origins.",
        graph_node_types=("mount", "socket"),
    ),
    FamilyRequirement(
        name="vector_or_flow_lines",
        description="Vectors, flow lines, streamlines, wind trails, or direction arrows show motion.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("vector", "flow", "stream", "wind", "direction"),
        recommendation_template="Add vectors, flow lines, streamlines, wind trails, or direction arrows.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="field_gradient_zones",
        description="Gradient bands, heat zones, pressure fields, density contours, or falloff regions show intensity.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("gradient", "heat", "pressure", "density", "falloff"),
        recommendation_template="Add gradient bands, heat zones, pressure fields, density contours, or falloff regions.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="solver_constraint_markers",
        description="Constraints, pins, blockers, colliders, limits, or fixed regions stabilize the simulation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("constraint", "pin", "blocker", "collider", "limit"),
        recommendation_template="Add constraints, pins, blockers, colliders, limits, or fixed regions.",
        graph_node_types=("guard", "socket"),
    ),
    FamilyRequirement(
        name="sample_or_probe_points",
        description="Samples, probes, sensors, debug points, or measurement ticks make the field inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sample", "probe", "sensor", "debug", "measure"),
        recommendation_template="Add samples, probes, sensors, debug points, or measurement ticks.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="collision_or_obstacle_boundaries",
        description="Colliders, obstacles, banks, walls, terrain contacts, or no-flow edges constrain the system.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("collider", "obstacle", "bank", "wall", "terrain"),
        recommendation_template="Add colliders, obstacles, banks, walls, terrain contacts, or no-flow edges.",
        graph_node_types=("guard", "panel"),
    ),
    FamilyRequirement(
        name="temporal_state_markers",
        description="Time ticks, frame markers, phase bands, cycle cues, or decay labels show temporal behavior.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("time", "frame", "phase", "cycle", "decay"),
        recommendation_template="Add time ticks, frame markers, phase bands, cycle cues, or decay labels.",
        graph_node_types=("decal_zone", "fastener"),
    ),
    FamilyRequirement(
        name="material_response_outputs",
        description="Erosion, wetness, scorch, deposition, foam, or residue outputs show simulation effects.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("erosion", "wetness", "scorch", "deposition", "foam"),
        recommendation_template="Add erosion, wetness, scorch, deposition, foam, or residue outputs.",
        graph_node_types=("material_zone", "wear_zone"),
    ),
    FamilyRequirement(
        name="simulation_wear_masks",
        description="Stress, flow wear, impact marks, edge deposits, or heat masks carry simulation history.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("stress", "flow_wear", "impact", "deposit", "mask"),
        recommendation_template="Add stress, flow wear, impact marks, edge deposits, or heat masks.",
        graph_node_types=("wear_zone",),
    ),
)


_AUTHORED_MULTI_ASSET_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="bundle_root_manifest",
        description="A root manifest, base plaque, collection plate, or bundle identity marker defines the set.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("manifest", "root", "collection", "bundle", "identity"),
        recommendation_template="Add a root manifest, base plaque, collection plate, or bundle identity marker.",
        graph_node_types=("primary_volume", "decal_zone"),
    ),
    FamilyRequirement(
        name="member_asset_slots",
        description="Member slots, asset bays, prefab seats, collection sockets, or part wells identify contents.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("member", "slot", "asset", "prefab", "part"),
        recommendation_template="Add member slots, asset bays, prefab seats, collection sockets, or part wells.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="dependency_or_link_graph",
        description="Dependency rails, link lines, parent-child arrows, grouping paths, or association edges show relationships.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("dependency", "link", "parent", "group", "association"),
        recommendation_template="Add dependency rails, link lines, parent-child arrows, grouping paths, or association edges.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="layout_or_scene_anchors",
        description="Scene anchors, placement pads, transform markers, snap guides, or origin points define layout.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("layout", "placement", "transform", "snap", "origin"),
        recommendation_template="Add scene anchors, placement pads, transform markers, snap guides, or origin points.",
        graph_node_types=("mount", "socket"),
    ),
    FamilyRequirement(
        name="variant_or_lod_entries",
        description="Variant entries, LOD ticks, quality bands, alternate slots, or platform markers define branches.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("variant", "lod", "quality", "alternate", "platform"),
        recommendation_template="Add variant entries, LOD ticks, quality bands, alternate slots, or platform markers.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="shared_material_or_style_zones",
        description="Shared material strips, style zones, palette swatches, theme plates, or shader labels unify members.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("shared", "material", "style", "palette", "shader"),
        recommendation_template="Add shared material strips, style zones, palette swatches, theme plates, or shader labels.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="export_or_package_markers",
        description="Export badges, package tags, file markers, version plates, or build labels show shipping intent.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("export", "package", "file", "version", "build"),
        recommendation_template="Add export badges, package tags, file markers, version plates, or build labels.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="assembly_or_order_guides",
        description="Assembly arrows, ordering rails, sequence ticks, reveal paths, or staging guides tell build order.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("assembly", "order", "sequence", "reveal", "stage"),
        recommendation_template="Add assembly arrows, ordering rails, sequence ticks, reveal paths, or staging guides.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="bounds_or_footprint_reference",
        description="Bundle bounds, footprint frames, collision pads, preview boxes, or scale rulers contain the set.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("bounds", "footprint", "collision", "preview", "scale"),
        recommendation_template="Add bundle bounds, footprint frames, collision pads, preview boxes, or scale rulers.",
        graph_node_types=("guard", "frame"),
    ),
    FamilyRequirement(
        name="bundle_usage_wear_masks",
        description="Handled edges, repeated socket rub, test-fit marks, layout dust, or packaging wear show use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("handled", "rub", "test", "dust", "wear"),
        recommendation_template="Add handled edges, repeated socket rub, test-fit marks, layout dust, or packaging wear.",
        graph_node_types=("wear_zone",),
    ),
)


_LIVE_PROCEDURAL_RUNTIME_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="runtime_core_or_hda_body",
        description="A runtime core, procedural body, HDA block, live module, or engine node anchors evaluation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("runtime", "core", "hda", "module", "engine"),
        recommendation_template="Add a runtime core, procedural body, HDA block, live module, or engine node.",
        graph_node_types=("primary_volume",),
    ),
    FamilyRequirement(
        name="input_parameter_ports",
        description="Input ports, parameter sockets, override knobs, seed slots, or control pads define inputs.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("input", "parameter", "override", "seed", "control"),
        recommendation_template="Add input ports, parameter sockets, override knobs, seed slots, or control pads.",
        graph_node_types=("socket", "handle"),
    ),
    FamilyRequirement(
        name="dependency_or_engine_hooks",
        description="Engine hooks, dependency links, plugin rails, adapter ports, or host connectors expose integration.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("hook", "dependency", "plugin", "adapter", "host"),
        recommendation_template="Add engine hooks, dependency links, plugin rails, adapter ports, or host connectors.",
        graph_node_types=("rail", "mount"),
    ),
    FamilyRequirement(
        name="runtime_output_slots",
        description="Output slots, bake ports, asset sinks, bundle targets, or stream connectors show results.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("output", "bake", "sink", "target", "stream"),
        recommendation_template="Add output slots, bake ports, asset sinks, bundle targets, or stream connectors.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="version_or_contract_badges",
        description="Version badges, contract IDs, compatibility tags, ABI labels, or schema plates pin behavior.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("version", "contract", "compat", "abi", "schema"),
        recommendation_template="Add version badges, contract IDs, compatibility tags, ABI labels, or schema plates.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="hot_reload_or_live_update_cues",
        description="Hot-reload arrows, live-update ticks, sync marks, refresh bands, or heartbeat cues show liveness.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("hot", "live", "sync", "refresh", "heartbeat"),
        recommendation_template="Add hot-reload arrows, live-update ticks, sync marks, refresh bands, or heartbeat cues.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="validation_or_guard_markers",
        description="Validation rails, safety guards, error bands, warning markers, or constraint frames show limits.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("validation", "guard", "error", "warning", "constraint"),
        recommendation_template="Add validation rails, safety guards, error bands, warning markers, or constraint frames.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="state_or_cache_indicators",
        description="Cache plates, state LEDs, dirty flags, stamp ticks, or memo markers show runtime state.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cache", "state", "dirty", "stamp", "memo"),
        recommendation_template="Add cache plates, state LEDs, dirty flags, stamp ticks, or memo markers.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="runtime_metrics_or_debug_ports",
        description="Metrics ports, debug probes, profile ticks, timing bars, or trace sockets make runtime inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("metric", "debug", "profile", "timing", "trace"),
        recommendation_template="Add metrics ports, debug probes, profile ticks, timing bars, or trace sockets.",
        graph_node_types=("fastener", "socket"),
    ),
    FamilyRequirement(
        name="iteration_or_override_wear_masks",
        description="Override wear, handled knobs, repeated-update scuffs, hot-swap marks, or debug residue show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("iteration", "override", "scuff", "hotswap", "residue"),
        recommendation_template="Add override wear, handled knobs, repeated-update scuffs, hot-swap marks, or debug residue.",
        graph_node_types=("wear_zone",),
    ),
)


_ENGINE_FACING_RUNTIME_BUNDLE_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="host_runtime_targets",
        description="Unity, Unreal, USD Hydra, Maya, Blender, or DCC target badges define runtime hosts.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("unity", "unreal", "hydra", "maya", "dcc"),
        recommendation_template="Add Unity, Unreal, USD Hydra, Maya, Blender, or DCC target badges.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="plugin_adapter_contracts",
        description="Plugin adapters, host bridges, SDK contracts, adapter ports, or engine connectors define integration.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("plugin", "adapter", "sdk", "bridge", "connector"),
        recommendation_template="Add plugin adapters, host bridges, SDK contracts, adapter ports, or engine connectors.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="lathe_bundle_manifest",
        description=".lathe.bundle manifests, bundle IDs, compiled kits, parameter sets, or LOD manifests define payloads.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("bundle", "manifest", "compiled", "parameter", "lod"),
        recommendation_template="Add .lathe.bundle manifests, bundle IDs, compiled kits, parameter sets, or LOD manifests.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="parameter_override_schema",
        description="Host parameter overrides, exposed knobs, ranges, seed values, or per-instance controls define variation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("override", "knob", "range", "seed", "instance"),
        recommendation_template="Add host parameter overrides, exposed knobs, ranges, seed values, or per-instance controls.",
        graph_node_types=("socket", "handle"),
    ),
    FamilyRequirement(
        name="live_evaluation_hooks",
        description="Live evaluation hooks, load-time evaluation, hot reload, cook triggers, or dirty-state marks define execution.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("live", "load", "hot", "cook", "dirty"),
        recommendation_template="Add live evaluation hooks, load-time evaluation, hot reload, cook triggers, or dirty-state marks.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="engine_asset_output_sinks",
        description="Engine asset sinks, prefab outputs, USD outputs, GLB outputs, package slots, or scene nodes define results.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sink", "prefab", "usd", "glb", "package"),
        recommendation_template="Add engine asset sinks, prefab outputs, USD outputs, GLB outputs, package slots, or scene nodes.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="usd_hydra_procedural_target",
        description="USD Hydra procedural targets, stage bindings, Hydra API badges, prim paths, or procedural prim tags define DCC interop.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("usd", "hydra", "stage", "prim", "procedural"),
        recommendation_template="Add USD Hydra procedural targets, stage bindings, Hydra API badges, prim paths, or procedural prim tags.",
        graph_node_types=("decal_zone", "rail"),
    ),
    FamilyRequirement(
        name="version_abi_guards",
        description="Version guards, ABI checks, schema pins, host compatibility badges, or plugin refusal rules prevent drift.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("version", "abi", "schema", "compat", "refusal"),
        recommendation_template="Add version guards, ABI checks, schema pins, host compatibility badges, or plugin refusal rules.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="runtime_diagnostics_ports",
        description="Runtime diagnostics, profiling ports, error channels, trace sockets, or cook metrics make hosts inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("diagnostic", "profile", "error", "trace", "metric"),
        recommendation_template="Add runtime diagnostics, profiling ports, error channels, trace sockets, or cook metrics.",
        graph_node_types=("socket", "fastener"),
    ),
    FamilyRequirement(
        name="host_iteration_wear_masks",
        description="Host iteration wear, adapter scuffs, recook residue, override marks, or plugin debug wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("iteration", "adapter", "recook", "mark", "wear"),
        recommendation_template="Add host iteration wear, adapter scuffs, recook residue, override marks, or plugin debug wear.",
        graph_node_types=("wear_zone",),
    ),
)


_PROCEDURAL_PREFAB_BINDING_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="prefab_root_binding",
        description="Prefab roots, engine roots, asset roots, scene object anchors, or prefab identity plates define the binding.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("prefab", "root", "asset", "scene", "identity"),
        recommendation_template="Add prefab roots, engine roots, asset roots, scene object anchors, or prefab identity plates.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="source_asset_slots",
        description="Source asset slots, mesh slots, material slots, collider slots, script slots, or child object ports define inputs.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("source", "mesh", "material", "collider", "script"),
        recommendation_template="Add source asset slots, mesh slots, material slots, collider slots, script slots, or child object ports.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="parameter_binding_table",
        description="Parameter binding tables, exposed values, property paths, override rows, or data bindings map controls.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("parameter", "property", "override", "binding", "value"),
        recommendation_template="Add parameter binding tables, exposed values, property paths, override rows, or data bindings.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="variant_override_map",
        description="Variant maps, override presets, skin swaps, optional children, or prefab modes define alternates.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("variant", "preset", "skin", "optional", "mode"),
        recommendation_template="Add variant maps, override presets, skin swaps, optional children, or prefab modes.",
        graph_node_types=("material_zone", "socket"),
    ),
    FamilyRequirement(
        name="lod_streaming_bindings",
        description="LOD bindings, streaming groups, distance tiers, impostor links, or memory budgets define runtime scale.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("lod", "stream", "distance", "impostor", "memory"),
        recommendation_template="Add LOD bindings, streaming groups, distance tiers, impostor links, or memory budgets.",
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="material_surface_bindings",
        description="Material bindings, surface slots, texture sets, MaterialX links, or shader assignments bind appearance.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("material", "surface", "texture", "materialx", "shader"),
        recommendation_template="Add material bindings, surface slots, texture sets, MaterialX links, or shader assignments.",
        graph_node_types=("material_zone", "socket"),
    ),
    FamilyRequirement(
        name="collision_physics_bindings",
        description="Collision bindings, physics bodies, nav blockers, trigger volumes, or socket colliders bind simulation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("collision", "physics", "nav", "trigger", "collider"),
        recommendation_template="Add collision bindings, physics bodies, nav blockers, trigger volumes, or socket colliders.",
        graph_node_types=("guard", "primary_volume"),
    ),
    FamilyRequirement(
        name="engine_export_targets",
        description="Engine export targets, Unity prefab paths, Unreal blueprint paths, USD prim paths, or GLB package names define outputs.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("export", "unity", "unreal", "blueprint", "path"),
        recommendation_template="Add engine export targets, Unity prefab paths, Unreal blueprint paths, USD prim paths, or GLB package names.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="dependency_update_guards",
        description="Dependency guards, stale binding warnings, missing asset checks, version pins, or invalid path badges prevent broken prefabs.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("dependency", "stale", "missing", "version", "invalid"),
        recommendation_template="Add dependency guards, stale binding warnings, missing asset checks, version pins, or invalid path badges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="prefab_iteration_wear_masks",
        description="Prefab iteration wear, override scratches, binding edits, export residue, or placement test marks show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("iteration", "scratch", "edit", "export", "wear"),
        recommendation_template="Add prefab iteration wear, override scratches, binding edits, export residue, or placement test marks.",
        graph_node_types=("wear_zone",),
    ),
)


_SCENE_SYSTEM_AUTHORING_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="scene_root_or_hierarchy",
        description="Scene roots, hierarchy trees, collection roots, layer roots, or transform parents organize the authored scene.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("scene", "root", "hierarchy", "collection", "parent"),
        recommendation_template="Add scene roots, hierarchy trees, collection roots, layer roots, or transform parents.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="transform_or_placement_anchors",
        description="Transform anchors, placement pads, origin markers, snap guides, or attachment pivots position scene content.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("transform", "placement", "origin", "snap", "pivot"),
        recommendation_template="Add transform anchors, placement pads, origin markers, snap guides, or attachment pivots.",
        graph_node_types=("mount", "decal_zone"),
    ),
    FamilyRequirement(
        name="spawn_or_population_layers",
        description="Spawn layers, population zones, actor pools, density fields, or encounter placements define runtime occupants.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("spawn", "population", "actor", "density", "encounter"),
        recommendation_template="Add spawn layers, population zones, actor pools, density fields, or encounter placements.",
        graph_node_types=("socket", "material_zone"),
    ),
    FamilyRequirement(
        name="lighting_camera_bookmarks",
        description="Lighting layers, camera bookmarks, cinematic marks, reflection probes, or exposure zones define view state.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("lighting", "camera", "cinematic", "probe", "exposure"),
        recommendation_template="Add lighting layers, camera bookmarks, cinematic marks, reflection probes, or exposure zones.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="navigation_regions",
        description="Navmesh regions, path corridors, traversal gates, cover nodes, or blocker volumes define navigation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("navmesh", "path", "traversal", "cover", "blocker"),
        recommendation_template="Add navmesh regions, path corridors, traversal gates, cover nodes, or blocker volumes.",
        graph_node_types=("rail", "guard"),
    ),
    FamilyRequirement(
        name="environment_volume_layers",
        description="Environment volumes, weather zones, audio zones, fog bounds, or postprocess regions layer atmosphere.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("volume", "weather", "audio", "fog", "postprocess"),
        recommendation_template="Add environment volumes, weather zones, audio zones, fog bounds, or postprocess regions.",
        graph_node_types=("material_zone", "guard"),
    ),
    FamilyRequirement(
        name="streaming_or_occlusion_tags",
        description="Streaming tags, occlusion cells, visibility sets, sector IDs, or load groups define large-scene partitioning.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("streaming", "occlusion", "visibility", "sector", "load"),
        recommendation_template="Add streaming tags, occlusion cells, visibility sets, sector IDs, or load groups.",
        graph_node_types=("panel", "trim"),
    ),
    FamilyRequirement(
        name="scene_export_targets",
        description="Scene export targets, engine scene paths, prefab roots, USD stage paths, or package slots define outputs.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("export", "engine", "prefab", "usd", "package"),
        recommendation_template="Add scene export targets, engine scene paths, prefab roots, USD stage paths, or package slots.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="scene_validation_guards",
        description="Scene validation guards, missing-reference warnings, overlap checks, invalid transform badges, or bounds checks reject broken scenes.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("validation", "missing", "overlap", "invalid", "bounds"),
        recommendation_template="Add scene validation guards, missing-reference warnings, overlap checks, invalid transform badges, or bounds checks.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="scene_iteration_wear_masks",
        description="Layout revisions, placement scuffs, spawn edits, lighting notes, or scene review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "placement", "edit", "note", "wear"),
        recommendation_template="Add layout revisions, placement scuffs, spawn edits, lighting notes, or scene review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_BEHAVIOR_LOGIC_GRAPH_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="state_or_behavior_nodes",
        description="State nodes, behavior nodes, selector nodes, sequence nodes, or task nodes define logic graph structure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("state", "behavior", "selector", "sequence", "task"),
        recommendation_template="Add state nodes, behavior nodes, selector nodes, sequence nodes, or task nodes.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="event_signal_edges",
        description="Event edges, signal wires, triggers, listeners, or broadcast links connect graph execution.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("event", "signal", "trigger", "listener", "broadcast"),
        recommendation_template="Add event edges, signal wires, triggers, listeners, or broadcast links.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="condition_rule_tables",
        description="Condition rules, guard clauses, predicates, comparisons, or threshold rows gate behavior.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("condition", "guard", "predicate", "compare", "threshold"),
        recommendation_template="Add condition rules, guard clauses, predicates, comparisons, or threshold rows.",
        graph_node_types=("panel", "guard"),
    ),
    FamilyRequirement(
        name="action_output_ports",
        description="Action outputs, command ports, animation calls, spawn commands, or gameplay effects perform behavior.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("action", "command", "animation", "spawn", "effect"),
        recommendation_template="Add action outputs, command ports, animation calls, spawn commands, or gameplay effects.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="blackboard_or_memory_bindings",
        description="Blackboard keys, memory bindings, variables, context slots, or fact stores define behavior state.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("blackboard", "memory", "variable", "context", "fact"),
        recommendation_template="Add blackboard keys, memory bindings, variables, context slots, or fact stores.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="timer_or_cooldown_tracks",
        description="Timers, cooldown tracks, delays, tick rates, or duration bands define temporal logic.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("timer", "cooldown", "delay", "tick", "duration"),
        recommendation_template="Add timers, cooldown tracks, delays, tick rates, or duration bands.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="priority_or_utility_weights",
        description="Priority weights, utility scores, selector weights, scoring curves, or arbitration rules choose behavior.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("priority", "utility", "score", "weight", "arbitration"),
        recommendation_template="Add priority weights, utility scores, selector weights, scoring curves, or arbitration rules.",
        graph_node_types=("fastener", "material_zone"),
    ),
    FamilyRequirement(
        name="failure_or_fallback_paths",
        description="Failure paths, fallback states, timeout routes, recovery edges, or abort links handle bad logic.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("failure", "fallback", "timeout", "recovery", "abort"),
        recommendation_template="Add failure paths, fallback states, timeout routes, recovery edges, or abort links.",
        graph_node_types=("guard", "rail"),
    ),
    FamilyRequirement(
        name="debug_trace_ports",
        description="Debug ports, trace taps, log hooks, probe sockets, or replay markers make behavior inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("debug", "trace", "log", "probe", "replay"),
        recommendation_template="Add debug ports, trace taps, log hooks, probe sockets, or replay markers.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="behavior_iteration_wear_masks",
        description="Logic revisions, tuning scuffs, graph edits, failed path marks, or behavior review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "tuning", "edit", "failed", "wear"),
        recommendation_template="Add logic revisions, tuning scuffs, graph edits, failed path marks, or behavior review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_WORLD_STREAMING_RUNTIME_PARTITION_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="world_partition_root",
        description="World partition roots, streaming roots, sector manifests, chunk roots, or runtime partition headers define the system.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("world", "partition", "streaming", "sector", "chunk"),
        recommendation_template="Add world partition roots, streaming roots, sector manifests, chunk roots, or runtime partition headers.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="sector_or_cell_grid",
        description="Sector grids, streaming cells, tile coordinates, chunk IDs, or region cells define spatial partitioning.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("sector", "cell", "tile", "chunk", "region"),
        recommendation_template="Add sector grids, streaming cells, tile coordinates, chunk IDs, or region cells.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="streaming_volume_bounds",
        description="Streaming volumes, activation bounds, trigger volumes, load boxes, or distance shells define activation areas.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("volume", "bounds", "trigger", "load", "distance"),
        recommendation_template="Add streaming volumes, activation bounds, trigger volumes, load boxes, or distance shells.",
        graph_node_types=("guard", "primary_volume"),
    ),
    FamilyRequirement(
        name="load_group_dependencies",
        description="Load groups, dependency links, parent-child chunks, prerequisite sectors, or order rails define streaming order.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("load", "dependency", "parent", "prereq", "order"),
        recommendation_template="Add load groups, dependency links, parent-child chunks, prerequisite sectors, or order rails.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="lod_distance_rings",
        description="LOD rings, distance tiers, impostor bands, far-field shells, or degradation thresholds define scaling.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("lod", "distance", "impostor", "far", "threshold"),
        recommendation_template="Add LOD rings, distance tiers, impostor bands, far-field shells, or degradation thresholds.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="occlusion_visibility_regions",
        description="Occlusion regions, visibility sets, portal cells, culling masks, or blocker bounds reduce work.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("occlusion", "visibility", "portal", "culling", "blocker"),
        recommendation_template="Add occlusion regions, visibility sets, portal cells, culling masks, or blocker bounds.",
        graph_node_types=("material_zone", "guard"),
    ),
    FamilyRequirement(
        name="memory_budget_markers",
        description="Memory budgets, residency classes, asset counts, stream weights, or pool limits constrain runtime cost.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("memory", "budget", "residency", "weight", "pool"),
        recommendation_template="Add memory budgets, residency classes, asset counts, stream weights, or pool limits.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="asset_residency_ports",
        description="Asset residency ports, package references, bundle links, prefab seats, or mesh/material slots define streamed content.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("asset", "residency", "package", "bundle", "prefab"),
        recommendation_template="Add asset residency ports, package references, bundle links, prefab seats, or mesh/material slots.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="partition_validation_guards",
        description="Partition guards, missing chunk warnings, circular dependency checks, overlap guards, or orphan cell badges reject bad streaming.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "missing", "circular", "overlap", "orphan"),
        recommendation_template="Add partition guards, missing chunk warnings, circular dependency checks, overlap guards, or orphan cell badges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="streaming_iteration_wear_masks",
        description="Streaming revisions, cell edits, load-test scuffs, residency marks, or partition review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "edit", "test", "mark", "wear"),
        recommendation_template="Add streaming revisions, cell edits, load-test scuffs, residency marks, or partition review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_SAVE_STATE_PERSISTENCE_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="save_root_or_manifest",
        description="Save roots, persistence manifests, slot headers, profile roots, or snapshot manifests define save scope.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("save", "persistence", "slot", "profile", "snapshot"),
        recommendation_template="Add save roots, persistence manifests, slot headers, profile roots, or snapshot manifests.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="checkpoint_slot_map",
        description="Checkpoint slots, autosave slots, restore points, bookmark rows, or checkpoint IDs define restore anchors.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("checkpoint", "autosave", "restore", "bookmark", "slot"),
        recommendation_template="Add checkpoint slots, autosave slots, restore points, bookmark rows, or checkpoint IDs.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="persistent_actor_state",
        description="Persistent actors, entity state rows, component state, transform snapshots, or health/state tables preserve actors.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("actor", "entity", "component", "transform", "health"),
        recommendation_template="Add persistent actors, entity state rows, component state, transform snapshots, or health/state tables.",
        graph_node_types=("panel", "material_zone"),
    ),
    FamilyRequirement(
        name="inventory_quest_state_tables",
        description="Inventory state, quest state, flags, counters, objectives, or progression tables preserve gameplay.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("inventory", "quest", "flag", "counter", "objective"),
        recommendation_template="Add inventory state, quest state, flags, counters, objectives, or progression tables.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="world_state_delta_log",
        description="World-state deltas, changed cells, dirty actors, patch records, or diff streams preserve authored changes.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("delta", "dirty", "patch", "diff", "changed"),
        recommendation_template="Add world-state deltas, changed cells, dirty actors, patch records, or diff streams.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="schema_version_badges",
        description="Schema versions, migration IDs, compatibility badges, save format pins, or build numbers define compatibility.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("schema", "version", "migration", "format", "build"),
        recommendation_template="Add schema versions, migration IDs, compatibility badges, save format pins, or build numbers.",
        graph_node_types=("decal_zone", "guard"),
    ),
    FamilyRequirement(
        name="restore_path_edges",
        description="Restore paths, load order rails, hydration edges, dependency links, or apply-order tracks define reconstruction.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("restore", "load", "hydrate", "dependency", "apply"),
        recommendation_template="Add restore paths, load order rails, hydration edges, dependency links, or apply-order tracks.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="conflict_resolution_rules",
        description="Conflict rules, merge policy, overwrite guards, stale-state warnings, or authority tags handle mismatches.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("conflict", "merge", "overwrite", "stale", "authority"),
        recommendation_template="Add conflict rules, merge policy, overwrite guards, stale-state warnings, or authority tags.",
        graph_node_types=("guard", "panel"),
    ),
    FamilyRequirement(
        name="corruption_validation_guards",
        description="Corruption checks, checksum badges, missing-field guards, invalid slot warnings, or recovery markers reject bad saves.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("corruption", "checksum", "missing", "invalid", "recovery"),
        recommendation_template="Add corruption checks, checksum badges, missing-field guards, invalid slot warnings, or recovery markers.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="persistence_iteration_wear_masks",
        description="Save-test scuffs, migration notes, restore edits, slot wear, or persistence review marks show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("test", "migration", "edit", "wear", "review"),
        recommendation_template="Add save-test scuffs, migration notes, restore edits, slot wear, or persistence review marks.",
        graph_node_types=("wear_zone",),
    ),
)


_QUEST_DIALOGUE_AUTHORING_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="quest_root_or_arc",
        description="Quest roots, story arcs, chapter nodes, episode cards, or narrative roots define quest scope.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("quest", "arc", "chapter", "episode", "narrative"),
        recommendation_template="Add quest roots, story arcs, chapter nodes, episode cards, or narrative roots.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="objective_graph_nodes",
        description="Objective nodes, task cards, goals, steps, or completion markers define progression.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("objective", "task", "goal", "step", "complete"),
        recommendation_template="Add objective nodes, task cards, goals, steps, or completion markers.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="dialogue_branch_tree",
        description="Dialogue branches, conversation trees, line nodes, speaker turns, or branch rails define conversation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("dialogue", "conversation", "line", "speaker", "branch"),
        recommendation_template="Add dialogue branches, conversation trees, line nodes, speaker turns, or branch rails.",
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="choice_condition_gates",
        description="Choice gates, condition checks, required flags, reputation gates, or skill checks control branches.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("choice", "condition", "flag", "reputation", "skill"),
        recommendation_template="Add choice gates, condition checks, required flags, reputation gates, or skill checks.",
        graph_node_types=("guard", "socket"),
    ),
    FamilyRequirement(
        name="reward_or_outcome_tables",
        description="Reward tables, outcome rows, item grants, reputation deltas, or unlock markers define consequences.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("reward", "outcome", "grant", "delta", "unlock"),
        recommendation_template="Add reward tables, outcome rows, item grants, reputation deltas, or unlock markers.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="npc_actor_bindings",
        description="NPC bindings, actor ports, speaker IDs, faction links, or portrait slots attach dialogue to actors.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("npc", "actor", "speaker", "faction", "portrait"),
        recommendation_template="Add NPC bindings, actor ports, speaker IDs, faction links, or portrait slots.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="localization_key_slots",
        description="Localization keys, text IDs, subtitle rows, VO keys, or translation slots make narrative portable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("localization", "text", "subtitle", "vo", "translation"),
        recommendation_template="Add localization keys, text IDs, subtitle rows, VO keys, or translation slots.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="conversation_state_flags",
        description="Conversation state flags, seen-line bits, cooldown state, repeat limits, or memory variables track dialogue.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("state", "seen", "cooldown", "repeat", "memory"),
        recommendation_template="Add conversation state flags, seen-line bits, cooldown state, repeat limits, or memory variables.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="narrative_validation_guards",
        description="Narrative guards, unreachable-branch warnings, missing reward checks, dangling speaker guards, or invalid flag badges reject broken quests.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "unreachable", "missing", "dangling", "invalid"),
        recommendation_template="Add narrative guards, unreachable-branch warnings, missing reward checks, dangling speaker guards, or invalid flag badges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="quest_dialogue_iteration_wear_masks",
        description="Quest revisions, script notes, branch edits, table scuffs, or narrative review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "script", "edit", "scuff", "wear"),
        recommendation_template="Add quest revisions, script notes, branch edits, table scuffs, or narrative review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_CAMERA_CINEMATIC_DIRECTION_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="camera_rig_roots",
        description="Camera rig roots, dolly rigs, crane rigs, shoulder rigs, or virtual camera anchors define capture setup.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("camera", "rig", "dolly", "crane", "anchor"),
        recommendation_template="Add camera rig roots, dolly rigs, crane rigs, shoulder rigs, or virtual camera anchors.",
        graph_node_types=("primary_volume", "mount"),
    ),
    FamilyRequirement(
        name="shot_sequence_graph",
        description="Shot sequence graphs, shot cards, cut nodes, storyboard beats, or shot order rails define structure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("shot", "sequence", "cut", "storyboard", "order"),
        recommendation_template="Add shot sequence graphs, shot cards, cut nodes, storyboard beats, or shot order rails.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="camera_path_tracks",
        description="Camera paths, spline tracks, dolly paths, orbit arcs, or handheld curves define movement.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("path", "spline", "track", "orbit", "handheld"),
        recommendation_template="Add camera paths, spline tracks, dolly paths, orbit arcs, or handheld curves.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="lens_or_fov_bindings",
        description="Lens bindings, FOV keys, focal length rows, aperture marks, or depth-of-field bands define optics.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("lens", "fov", "focal", "aperture", "depth"),
        recommendation_template="Add lens bindings, FOV keys, focal length rows, aperture marks, or depth-of-field bands.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="timeline_beat_markers",
        description="Timeline beats, frame markers, cue points, timing bars, or edit ticks define time.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("timeline", "frame", "cue", "timing", "beat"),
        recommendation_template="Add timeline beats, frame markers, cue points, timing bars, or edit ticks.",
        graph_node_types=("fastener", "rail"),
    ),
    FamilyRequirement(
        name="look_at_target_tracks",
        description="Look-at targets, focus targets, actor targets, aim rails, or tracking constraints bind framing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("look", "focus", "target", "aim", "tracking"),
        recommendation_template="Add look-at targets, focus targets, actor targets, aim rails, or tracking constraints.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="blend_or_transition_stack",
        description="Blend stacks, transition curves, easing bands, cut rules, or dissolve rows define shot transitions.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("blend", "transition", "ease", "dissolve", "curve"),
        recommendation_template="Add blend stacks, transition curves, easing bands, cut rules, or dissolve rows.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="framing_safe_regions",
        description="Framing guides, safe regions, rule-of-thirds marks, headroom bands, or occlusion guards protect composition.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("framing", "safe", "thirds", "headroom", "occlusion"),
        recommendation_template="Add framing guides, safe regions, rule-of-thirds marks, headroom bands, or occlusion guards.",
        graph_node_types=("guard", "decal_zone"),
    ),
    FamilyRequirement(
        name="cinematic_trigger_outputs",
        description="Cinematic triggers, event outputs, cutscene ports, camera state outputs, or sequence export slots connect runtime.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("trigger", "event", "cutscene", "output", "export"),
        recommendation_template="Add cinematic triggers, event outputs, cutscene ports, camera state outputs, or sequence export slots.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="cinematic_iteration_wear_masks",
        description="Shot revisions, timing scuffs, framing edits, slate marks, or cinematic review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "timing", "edit", "slate", "wear"),
        recommendation_template="Add shot revisions, timing scuffs, framing edits, slate marks, or cinematic review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_PROCEDURAL_AUDIO_CUE_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="audio_cue_roots",
        description="Audio cue roots, sound cue graphs, event roots, mix roots, or runtime audio roots define cue scope.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("audio", "sound", "cue", "mix", "runtime"),
        recommendation_template="Add audio cue roots, sound cue graphs, event roots, mix roots, or runtime audio roots.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="sfx_or_music_event_nodes",
        description="SFX nodes, music stems, ambience layers, stingers, or event cards define audible content.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("sfx", "music", "ambience", "stinger", "event"),
        recommendation_template="Add SFX nodes, music stems, ambience layers, stingers, or event cards.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="timing_trigger_markers",
        description="Timing triggers, beat markers, cue points, sync ticks, or transition markers define playback timing.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("timing", "beat", "sync", "trigger", "transition"),
        recommendation_template="Add timing triggers, beat markers, cue points, sync ticks, or transition markers.",
        graph_node_types=("fastener", "rail"),
    ),
    FamilyRequirement(
        name="attenuation_spatial_zones",
        description="Attenuation zones, falloff bands, listener radius rings, occlusion zones, or spatial regions define 3D audio.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("attenuation", "falloff", "listener", "occlusion", "spatial"),
        recommendation_template="Add attenuation zones, falloff bands, listener radius rings, occlusion zones, or spatial regions.",
        graph_node_types=("guard", "material_zone"),
    ),
    FamilyRequirement(
        name="reverb_or_mixer_sends",
        description="Reverb sends, mixer routes, bus sends, ducking lanes, or snapshot rows define mix routing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("reverb", "mixer", "bus", "ducking", "snapshot"),
        recommendation_template="Add reverb sends, mixer routes, bus sends, ducking lanes, or snapshot rows.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="voiceover_trigger_bindings",
        description="VO triggers, bark cues, speaker bindings, subtitle links, or dialogue event ports attach voice playback.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("vo", "voice", "bark", "speaker", "subtitle"),
        recommendation_template="Add VO triggers, bark cues, speaker bindings, subtitle links, or dialogue event ports.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="loop_or_layer_controls",
        description="Loop controls, layer weights, crossfade bands, stem gates, or intensity ramps shape adaptive playback.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("loop", "layer", "crossfade", "stem", "intensity"),
        recommendation_template="Add loop controls, layer weights, crossfade bands, stem gates, or intensity ramps.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="runtime_audio_outputs",
        description="Runtime output buses, callback ports, event outputs, middleware slots, or engine sink ports connect playback.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("output", "callback", "middleware", "engine", "sink"),
        recommendation_template="Add runtime output buses, callback ports, event outputs, middleware slots, or engine sink ports.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="loudness_validation_guards",
        description="Loudness guards, peak checks, clipping warnings, missing route badges, or invalid loop guards reject bad audio graphs.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("loudness", "peak", "clipping", "missing", "invalid"),
        recommendation_template="Add loudness guards, peak checks, clipping warnings, missing route badges, or invalid loop guards.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="audio_iteration_wear_masks",
        description="Mix revisions, waveform scuffs, timing edits, review marks, or audition wear show audio iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "waveform", "edit", "review", "wear"),
        recommendation_template="Add mix revisions, waveform scuffs, timing edits, review marks, or audition wear.",
        graph_node_types=("wear_zone",),
    ),
)


_LOCALIZATION_TEXT_TABLE_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="locale_table_roots",
        description="Localization table roots, string table manifests, locale table headers, text database roots, or content roots define scope.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("localization", "string", "locale", "text", "content"),
        recommendation_template="Add localization table roots, string table manifests, locale table headers, text database roots, or content roots.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="string_key_rows",
        description="String keys, text IDs, token rows, namespace keys, or content IDs address localized entries.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("key", "id", "token", "namespace", "row"),
        recommendation_template="Add string keys, text IDs, token rows, namespace keys, or content IDs.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="translation_value_columns",
        description="Locale columns, translation cells, value columns, language variants, or regional rows hold text values.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("translation", "column", "language", "regional", "value"),
        recommendation_template="Add locale columns, translation cells, value columns, language variants, or regional rows.",
        graph_node_types=("panel", "material_zone"),
    ),
    FamilyRequirement(
        name="pluralization_or_gender_rules",
        description="Pluralization rules, gender rules, grammar variants, token formatters, or ICU forms handle language grammar.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("plural", "gender", "grammar", "formatter", "icu"),
        recommendation_template="Add pluralization rules, gender rules, grammar variants, token formatters, or ICU forms.",
        graph_node_types=("guard", "panel"),
    ),
    FamilyRequirement(
        name="fallback_locale_chains",
        description="Fallback chains, default locale links, missing text routes, inheritance rails, or regional fallback maps ensure resilience.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("fallback", "default", "missing", "inherit", "regional"),
        recommendation_template="Add fallback chains, default locale links, missing text routes, inheritance rails, or regional fallback maps.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="subtitle_timing_rows",
        description="Subtitle timings, caption rows, reading-speed bands, line-break marks, or duration ticks support subtitles.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("subtitle", "caption", "reading", "line", "duration"),
        recommendation_template="Add subtitle timings, caption rows, reading-speed bands, line-break marks, or duration ticks.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="voiceover_text_bindings",
        description="Voiceover bindings, VO keys, speaker IDs, recording IDs, or audio text links bind voice assets.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("voiceover", "vo", "speaker", "recording", "audio"),
        recommendation_template="Add voiceover bindings, VO keys, speaker IDs, recording IDs, or audio text links.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="glyph_or_font_coverage",
        description="Glyph coverage tiles, font fallback slots, character set badges, script coverage, or missing glyph guards ensure display.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("glyph", "font", "character", "script", "coverage"),
        recommendation_template="Add glyph coverage tiles, font fallback slots, character set badges, script coverage, or missing glyph guards.",
        graph_node_types=("decal_zone", "guard"),
    ),
    FamilyRequirement(
        name="localization_validation_guards",
        description="Missing translation guards, stale key checks, overflow warnings, invalid token badges, or locale validation ports reject bad tables.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "stale", "overflow", "invalid", "validation"),
        recommendation_template="Add missing translation guards, stale key checks, overflow warnings, invalid token badges, or locale validation ports.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="localization_iteration_wear_masks",
        description="Translation revisions, review marks, editor scuffs, proofreading notes, or localization wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "review", "proof", "edit", "wear"),
        recommendation_template="Add translation revisions, review marks, editor scuffs, proofreading notes, or localization wear.",
        graph_node_types=("wear_zone",),
    ),
)


_ACCESSIBILITY_UX_AFFORDANCE_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="affordance_roots",
        description="Accessibility roots, UX affordance maps, inclusive design roots, option roots, or user support manifests define scope.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("accessibility", "ux", "affordance", "option", "support"),
        recommendation_template="Add accessibility roots, UX affordance maps, inclusive design roots, option roots, or user support manifests.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="input_or_control_maps",
        description="Input remaps, control maps, controller states, keybinding rows, or alternate input paths expose controls.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("input", "control", "controller", "keybinding", "remap"),
        recommendation_template="Add input remaps, control maps, controller states, keybinding rows, or alternate input paths.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="readable_state_cues",
        description="Readable state cues, icon states, status labels, shape-coded signals, or redundant cues communicate state.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("readable", "state", "icon", "label", "redundant"),
        recommendation_template="Add readable state cues, icon states, status labels, shape-coded signals, or redundant cues.",
        graph_node_types=("decal_zone", "fastener"),
    ),
    FamilyRequirement(
        name="contrast_or_color_safe_regions",
        description="Contrast-safe regions, colorblind-safe swatches, luminance bands, palette guards, or readability zones protect visibility.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("contrast", "colorblind", "luminance", "palette", "visibility"),
        recommendation_template="Add contrast-safe regions, colorblind-safe swatches, luminance bands, palette guards, or readability zones.",
        graph_node_types=("material_zone", "guard"),
    ),
    FamilyRequirement(
        name="subtitle_or_caption_panels",
        description="Subtitle panels, caption rows, speaker labels, text scale markers, or timing bands support readable text.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("subtitle", "caption", "speaker", "scale", "timing"),
        recommendation_template="Add subtitle panels, caption rows, speaker labels, text scale markers, or timing bands.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="audio_visual_haptic_cues",
        description="Audio cues, visual flashes, haptic patterns, cue alternatives, or feedback ports provide redundant feedback.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("audio", "visual", "haptic", "feedback", "alternative"),
        recommendation_template="Add audio cues, visual flashes, haptic patterns, cue alternatives, or feedback ports.",
        graph_node_types=("socket", "rail"),
    ),
    FamilyRequirement(
        name="focus_navigation_paths",
        description="Focus paths, tab order rails, navigation graphs, selection rings, or screen-reader routes define navigation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("focus", "tab", "navigation", "selection", "reader"),
        recommendation_template="Add focus paths, tab order rails, navigation graphs, selection rings, or screen-reader routes.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="accessibility_option_ports",
        description="Accessibility option ports, toggles, sliders, preset slots, or profile outputs expose user choices.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("option", "toggle", "slider", "preset", "profile"),
        recommendation_template="Add accessibility option ports, toggles, sliders, preset slots, or profile outputs.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="usability_validation_guards",
        description="Usability guards, contrast checks, missing cue warnings, blocked focus badges, or unreadable-state guards reject inaccessible flows.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("usability", "check", "missing", "blocked", "unreadable"),
        recommendation_template="Add usability guards, contrast checks, missing cue warnings, blocked focus badges, or unreadable-state guards.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="accessibility_iteration_wear_masks",
        description="Accessibility review marks, usability notes, user-test scuffs, remap edits, or affordance wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("review", "usability", "test", "edit", "wear"),
        recommendation_template="Add accessibility review marks, usability notes, user-test scuffs, remap edits, or affordance wear.",
        graph_node_types=("wear_zone",),
    ),
)


_ECONOMY_SIMULATION_TUNING_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="economy_simulation_roots",
        description="Economy roots, simulation tuning roots, balance manifests, systems roots, or market roots define scope.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("economy", "simulation", "balance", "system", "market"),
        recommendation_template="Add economy roots, simulation tuning roots, balance manifests, systems roots, or market roots.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="resource_flow_nodes",
        description="Resource flow nodes, production chains, consumption paths, resource pools, or conversion nodes define flow.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("resource", "production", "consumption", "pool", "conversion"),
        recommendation_template="Add resource flow nodes, production chains, consumption paths, resource pools, or conversion nodes.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="currency_sink_source_pairs",
        description="Currency sources, currency sinks, faucet/drain pairs, spend loops, or earning paths bound currency.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("currency", "source", "sink", "spend", "earn"),
        recommendation_template="Add currency sources, currency sinks, faucet/drain pairs, spend loops, or earning paths.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="loot_reward_tables",
        description="Loot tables, reward rows, drop weights, rarity bands, or grant curves define rewards.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("loot", "reward", "drop", "rarity", "grant"),
        recommendation_template="Add loot tables, reward rows, drop weights, rarity bands, or grant curves.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="price_or_market_curves",
        description="Price curves, market rules, exchange rates, inflation bands, or vendor modifiers define market behavior.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("price", "market", "exchange", "inflation", "vendor"),
        recommendation_template="Add price curves, market rules, exchange rates, inflation bands, or vendor modifiers.",
        graph_node_types=("rail", "panel"),
    ),
    FamilyRequirement(
        name="progression_balance_tracks",
        description="Progression tracks, difficulty curves, level bands, unlock pacing, or cost ramps define balance.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("progression", "difficulty", "level", "unlock", "cost"),
        recommendation_template="Add progression tracks, difficulty curves, level bands, unlock pacing, or cost ramps.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="spawn_rate_modulators",
        description="Spawn rates, demand knobs, supply controls, simulation weights, or pacing modulators tune live values.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("spawn", "demand", "supply", "weight", "pacing"),
        recommendation_template="Add spawn rates, demand knobs, supply controls, simulation weights, or pacing modulators.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="telemetry_tuning_inputs",
        description="Telemetry inputs, metric rows, cohort slices, experiment IDs, or observation ports feed tuning.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("telemetry", "metric", "cohort", "experiment", "observation"),
        recommendation_template="Add telemetry inputs, metric rows, cohort slices, experiment IDs, or observation ports.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="simulation_validation_guards",
        description="Runaway loop guards, impossible economy warnings, invalid curve badges, missing sink checks, or overflow guards reject bad tuning.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("runaway", "impossible", "invalid", "missing", "overflow"),
        recommendation_template="Add runaway loop guards, impossible economy warnings, invalid curve badges, missing sink checks, or overflow guards.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="economy_iteration_wear_masks",
        description="Balance revisions, tuning scuffs, economy review marks, spreadsheet edits, or simulation wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "tuning", "review", "spreadsheet", "wear"),
        recommendation_template="Add balance revisions, tuning scuffs, economy review marks, spreadsheet edits, or simulation wear.",
        graph_node_types=("wear_zone",),
    ),
)


_MULTIPLAYER_SESSION_REPLICATION_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="session_replication_roots",
        description="Session roots, replication manifests, network session maps, lobby roots, or room roots define scope.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("session", "replication", "network", "lobby", "room"),
        recommendation_template="Add session roots, replication manifests, network session maps, lobby roots, or room roots.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="authority_ownership_maps",
        description="Authority maps, ownership tracks, host/client roles, server authority bands, or owner transfer rules define control.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("authority", "ownership", "host", "server", "owner"),
        recommendation_template="Add authority maps, ownership tracks, host/client roles, server authority bands, or owner transfer rules.",
        graph_node_types=("rail", "guard"),
    ),
    FamilyRequirement(
        name="replicated_state_nodes",
        description="Replicated state nodes, property rows, dirty flags, state snapshots, or sync fields define shared state.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("state", "property", "dirty", "snapshot", "sync"),
        recommendation_template="Add replicated state nodes, property rows, dirty flags, state snapshots, or sync fields.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="rpc_event_channels",
        description="RPC channels, event buses, command ports, reliable lanes, or multicast paths define events.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("rpc", "event", "command", "reliable", "multicast"),
        recommendation_template="Add RPC channels, event buses, command ports, reliable lanes, or multicast paths.",
        graph_node_types=("socket", "rail"),
    ),
    FamilyRequirement(
        name="sync_tick_timelines",
        description="Sync ticks, net frame markers, replication intervals, snapshot beats, or send-rate bands define timing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("tick", "frame", "interval", "snapshot", "rate"),
        recommendation_template="Add sync ticks, net frame markers, replication intervals, snapshot beats, or send-rate bands.",
        graph_node_types=("fastener", "rail"),
    ),
    FamilyRequirement(
        name="prediction_reconciliation_paths",
        description="Prediction paths, reconciliation rails, client correction links, interpolation bands, or extrapolation guards stabilize motion.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("prediction", "reconciliation", "correction", "interpolation", "extrapolation"),
        recommendation_template="Add prediction paths, reconciliation rails, client correction links, interpolation bands, or extrapolation guards.",
        graph_node_types=("rail", "guard"),
    ),
    FamilyRequirement(
        name="rollback_state_buffers",
        description="Rollback buffers, history slots, replay windows, frame caches, or correction buffers support recovery.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("rollback", "history", "replay", "cache", "buffer"),
        recommendation_template="Add rollback buffers, history slots, replay windows, frame caches, or correction buffers.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="matchmaking_session_rules",
        description="Matchmaking rules, party slots, region filters, skill bands, or join policy rows define sessions.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("matchmaking", "party", "region", "skill", "join"),
        recommendation_template="Add matchmaking rules, party slots, region filters, skill bands, or join policy rows.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="replication_validation_guards",
        description="Desync guards, missing owner warnings, invalid RPC badges, stale snapshot checks, or bandwidth guards reject broken replication.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("desync", "missing", "invalid", "stale", "bandwidth"),
        recommendation_template="Add desync guards, missing owner warnings, invalid RPC badges, stale snapshot checks, or bandwidth guards.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="multiplayer_iteration_wear_masks",
        description="Netcode revisions, sync scuffs, replication review marks, load-test edits, or multiplayer wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("revision", "sync", "review", "test", "wear"),
        recommendation_template="Add netcode revisions, sync scuffs, replication review marks, load-test edits, or multiplayer wear.",
        graph_node_types=("wear_zone",),
    ),
)


_CROSS_DOMAIN_COMPOSITION_PACK_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="domain_pillars",
        description="World, asset, gameplay, style, runtime, or simulation pillars establish the pack's domains.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("world", "asset", "gameplay", "style", "runtime"),
        recommendation_template="Add world, asset, gameplay, style, runtime, or simulation pillars.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="bridge_or_handoff_links",
        description="Bridge links, handoff rails, adapters, converters, or contracts connect domains.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("bridge", "handoff", "adapter", "converter", "contract"),
        recommendation_template="Add bridge links, handoff rails, adapters, converters, or contracts.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="shared_rule_layer",
        description="Shared rules, invariants, constraints, tags, or policy bands keep the pack coherent.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("rule", "invariant", "constraint", "tag", "policy"),
        recommendation_template="Add shared rules, invariants, constraints, tags, or policy bands.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="interface_or_port_map",
        description="Interfaces, ports, sockets, API markers, or IO labels show how parts compose.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("interface", "port", "socket", "api", "io"),
        recommendation_template="Add interfaces, ports, sockets, API markers, or IO labels.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="domain_boundary_markers",
        description="Boundary frames, separators, guard rails, ownership edges, or section gates prevent ambiguity.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("boundary", "separator", "guard", "ownership", "section"),
        recommendation_template="Add boundary frames, separators, guard rails, ownership edges, or section gates.",
        graph_node_types=("guard", "frame"),
    ),
    FamilyRequirement(
        name="conflict_or_refusal_cues",
        description="Conflict badges, refusal marks, warning bands, incompatible-pair markers, or blocker chips show invalid mixes.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("conflict", "refusal", "warning", "incompatible", "blocker"),
        recommendation_template="Add conflict badges, refusal marks, warning bands, incompatible-pair markers, or blocker chips.",
        graph_node_types=("decal_zone", "guard"),
    ),
    FamilyRequirement(
        name="preview_or_sample_outputs",
        description="Preview outputs, sample pads, thumbnails, representative tiles, or test fixtures show the pack's result.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("preview", "sample", "thumbnail", "tile", "fixture"),
        recommendation_template="Add preview outputs, sample pads, thumbnails, representative tiles, or test fixtures.",
        graph_node_types=("panel", "mount"),
    ),
    FamilyRequirement(
        name="dependency_or_order_guides",
        description="Dependency paths, ordering arrows, phase rails, priority ticks, or sequencing marks guide execution.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("dependency", "order", "phase", "priority", "sequence"),
        recommendation_template="Add dependency paths, ordering arrows, phase rails, priority ticks, or sequencing marks.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="integration_labels",
        description="Labels, legends, domain names, IDs, or integration notes make the pack inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("label", "legend", "domain", "id", "note"),
        recommendation_template="Add labels, legends, domain names, IDs, or integration notes.",
        graph_node_types=("decal_zone",),
    ),
    FamilyRequirement(
        name="handoff_wear_masks",
        description="Handoff wear, bridge rub, integration scuffs, repeated-test marks, or transfer masks show usage.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("handoff", "rub", "scuff", "test", "transfer"),
        recommendation_template="Add handoff wear, bridge rub, integration scuffs, repeated-test marks, or transfer masks.",
        graph_node_types=("wear_zone",),
    ),
)


_STYLE_STACK_VISUAL_BAND_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="style_axis_stack",
        description="Style axes, stack rows, visual-band lanes, or art-direction columns define the target.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("axis", "stack", "band", "lane", "column"),
        recommendation_template="Add style axes, stack rows, visual-band lanes, or art-direction columns.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="palette_or_material_model",
        description="Palette swatches, material models, shader chips, color ramps, or surface tokens establish look.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("palette", "material", "shader", "color", "surface"),
        recommendation_template="Add palette swatches, material models, shader chips, color ramps, or surface tokens.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="surface_authoring_mode",
        description="Designer graph, photo-fit mode, layer stack, procedural surface, or painter mode states authoring.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("designer", "photo", "layer", "surface", "painter"),
        recommendation_template="Add designer graph, photo-fit mode, layer stack, procedural surface, or painter mode.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="outline_or_lighting_strategy",
        description="Outline mode, lighting rig, cel band, rim light, or shadow strategy sets rendering behavior.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("outline", "lighting", "cel", "rim", "shadow"),
        recommendation_template="Add outline mode, lighting rig, cel band, rim light, or shadow strategy.",
        graph_node_types=("trim", "rail"),
    ),
    FamilyRequirement(
        name="detail_layer_composition",
        description="Detail layers, noise bands, greeble density, decals, or frequency strips define detail rhythm.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("detail", "noise", "greeble", "decal", "frequency"),
        recommendation_template="Add detail layers, noise bands, greeble density, decals, or frequency strips.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="animation_rate_or_motion_style",
        description="Animation rate, smear cues, stepped timing, frame marks, or motion bands define movement style.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("animation", "smear", "timing", "frame", "motion"),
        recommendation_template="Add animation rate, smear cues, stepped timing, frame marks, or motion bands.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="construction_grammar_marker",
        description="Construction grammar tags, primitive rules, allowed forms, or shape idiom plates define geometry style.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("construction", "primitive", "allowed", "form", "idiom"),
        recommendation_template="Add construction grammar tags, primitive rules, allowed forms, or shape idiom plates.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="compatibility_or_bridge_rules",
        description="Compatibility bridges, sanctioned mixes, bridge tags, allowed-pair markers, or blend rules show safe combinations.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("compat", "bridge", "mix", "pair", "blend"),
        recommendation_template="Add compatibility bridges, sanctioned mixes, bridge tags, allowed-pair markers, or blend rules.",
        graph_node_types=("socket", "guard"),
    ),
    FamilyRequirement(
        name="refusal_or_negative_constraints",
        description="Refusal marks, negative constraints, forbidden pairs, warning badges, or redlines prevent bad style mixes.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("refusal", "negative", "forbidden", "warning", "redline"),
        recommendation_template="Add refusal marks, negative constraints, forbidden pairs, warning badges, or redlines.",
        graph_node_types=("guard", "decal_zone"),
    ),
    FamilyRequirement(
        name="style_iteration_wear_masks",
        description="Sample wear, iteration ticks, test swatches, revision scuffs, or style-pick marks show exploration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sample", "iteration", "test", "revision", "style"),
        recommendation_template="Add sample wear, iteration ticks, test swatches, revision scuffs, or style-pick marks.",
        graph_node_types=("wear_zone",),
    ),
)


_TYPED_DATA_KERNEL_BUNDLE_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="typed_bundle_bus",
        description="A typed bundle bus, kernel spine, data backbone, or transport rail carries artifacts.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("typed", "bundle", "bus", "kernel", "backbone"),
        recommendation_template="Add a typed bundle bus, kernel spine, data backbone, or transport rail.",
        graph_node_types=("primary_volume", "rail"),
    ),
    FamilyRequirement(
        name="mesh_points_volume_slots",
        description="Mesh, point, volume, voxel, or cloud slots cover core geometry/data artifacts.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("mesh", "point", "volume", "voxel", "cloud"),
        recommendation_template="Add mesh, point, volume, voxel, or cloud data slots.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="heightfield_spline_sdf_slots",
        description="Heightfield, terrain, spline, curve, SDF, or distance-field slots cover procedural domains.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("heightfield", "terrain", "spline", "curve", "sdf"),
        recommendation_template="Add heightfield, terrain, spline, curve, SDF, or distance-field slots.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="image_and_rig_slots",
        description="Image, texture, mask, rig, skeleton, or skin-weight slots complete the typed bundle.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("image", "texture", "mask", "rig", "skeleton"),
        recommendation_template="Add image, texture, mask, rig, skeleton, or skin-weight slots.",
        graph_node_types=("socket", "material_zone"),
    ),
    FamilyRequirement(
        name="slot_contract_badges",
        description="Contract IDs, version badges, schema tags, capability stamps, or type labels identify slots.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("contract", "version", "schema", "capability", "type"),
        recommendation_template="Add contract IDs, version badges, schema tags, capability stamps, or type labels.",
        graph_node_types=("decal_zone", "guard"),
    ),
    FamilyRequirement(
        name="transform_or_conversion_links",
        description="Transform arrows, conversion links, adapters, casts, or projection rails connect artifact types.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("transform", "conversion", "adapter", "cast", "projection"),
        recommendation_template="Add transform arrows, conversion links, adapters, casts, or projection rails.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="dependency_and_order_markers",
        description="Dependency rails, ordering ticks, evaluation steps, stage markers, or phase chips show flow.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("dependency", "order", "evaluation", "stage", "phase"),
        recommendation_template="Add dependency rails, ordering ticks, evaluation steps, stage markers, or phase chips.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="cache_or_delta_state",
        description="Cache panels, dirty flags, delta marks, memo stamps, or snapshot tags expose state.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cache", "dirty", "delta", "memo", "snapshot"),
        recommendation_template="Add cache panels, dirty flags, delta marks, memo stamps, or snapshot tags.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="validation_or_guard_edges",
        description="Validation guards, type fences, refusal rails, error bands, or mismatch markers block invalid data.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("validation", "guard", "refusal", "error", "mismatch"),
        recommendation_template="Add validation guards, type fences, refusal rails, error bands, or mismatch markers.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="data_flow_wear_masks",
        description="Flow wear, port rub, hot-path scuffs, migration marks, or conversion residue show use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("flow", "rub", "scuff", "migration", "residue"),
        recommendation_template="Add flow wear, port rub, hot-path scuffs, migration marks, or conversion residue.",
        graph_node_types=("wear_zone",),
    ),
)


_ATTRIBUTE_SURFACE_GRAPH_PROGRAM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="attribute_streams",
        description="Attribute streams, bindings, channels, variables, or field lanes carry procedural data.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("attribute", "binding", "channel", "variable", "field"),
        recommendation_template="Add attribute streams, bindings, channels, variables, or field lanes.",
        graph_node_types=("rail", "primary_volume"),
    ),
    FamilyRequirement(
        name="surface_node_graph",
        description="Surface nodes, shader nodes, procedural graph blocks, material nodes, or evaluation tiles define material logic.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("surface", "shader", "graph", "material", "node"),
        recommendation_template="Add surface nodes, shader nodes, procedural graph blocks, material nodes, or evaluation tiles.",
        graph_node_types=("panel", "material_zone"),
    ),
    FamilyRequirement(
        name="designer_photo_layer_modes",
        description="Designer graph, photo-fit, layer stack, painter, or procedural modes are explicit.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("designer", "photo", "layer", "painter", "mode"),
        recommendation_template="Add designer graph, photo-fit, layer stack, painter, or procedural mode markers.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="mask_program_layers",
        description="Mask layers, smart masks, curvature masks, AO masks, or region selectors drive composition.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("mask", "curvature", "ao", "region", "selector"),
        recommendation_template="Add mask layers, smart masks, curvature masks, AO masks, or region selectors.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="materialx_output_ports",
        description="MaterialX ports, PBR outputs, texture outputs, channel maps, or export badges show outputs.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("materialx", "pbr", "texture", "output", "export"),
        recommendation_template="Add MaterialX ports, PBR outputs, texture outputs, channel maps, or export badges.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="attribute_math_or_rules",
        description="Attribute math, remap rules, ramps, filters, conditionals, or expressions define logic.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("math", "remap", "ramp", "filter", "expression"),
        recommendation_template="Add attribute math, remap rules, ramps, filters, conditionals, or expressions.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="texture_frequency_controls",
        description="Frequency bands, scale controls, tiling guides, octave markers, or texel-density ticks control texture rhythm.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("frequency", "scale", "tiling", "octave", "texel"),
        recommendation_template="Add frequency bands, scale controls, tiling guides, octave markers, or texel-density ticks.",
        graph_node_types=("fastener", "trim"),
    ),
    FamilyRequirement(
        name="preview_or_bake_targets",
        description="Preview swatches, bake targets, thumbnail pads, sample spheres, or output tiles make results inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("preview", "bake", "thumbnail", "sample", "tile"),
        recommendation_template="Add preview swatches, bake targets, thumbnail pads, sample spheres, or output tiles.",
        graph_node_types=("panel", "mount"),
    ),
    FamilyRequirement(
        name="unbound_or_invalid_guards",
        description="Unbound-attribute guards, invalid-mode warnings, mismatch rails, refusal chips, or redlines reject bad graphs.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("unbound", "invalid", "mismatch", "refusal", "redline"),
        recommendation_template="Add unbound-attribute guards, invalid-mode warnings, mismatch rails, refusal chips, or redlines.",
        graph_node_types=("guard", "decal_zone"),
    ),
    FamilyRequirement(
        name="surface_iteration_wear_masks",
        description="Iteration wear, mask edits, paint scuffs, graph revision marks, or bake residue show authoring history.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("iteration", "edit", "paint", "revision", "residue"),
        recommendation_template="Add iteration wear, mask edits, paint scuffs, graph revision marks, or bake residue.",
        graph_node_types=("wear_zone",),
    ),
)


_VEGETATION_LIBRARY_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="species_catalog",
        description="Species cards, archetype slots, growth presets, cultivar labels, or plant IDs define the library.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("species", "archetype", "preset", "cultivar", "plant_id"),
        recommendation_template="Add species cards, archetype slots, growth presets, cultivar labels, or plant IDs.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="trunk_branch_grammar",
        description="Trunk spines, branching curves, split rules, internodes, or bough hierarchies define structure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("trunk", "branch", "split", "internode", "bough"),
        recommendation_template="Add trunk spines, branching curves, split rules, internodes, or bough hierarchies.",
        graph_node_types=("rail", "primary_volume"),
    ),
    FamilyRequirement(
        name="leaf_cluster_rules",
        description="Leaf clusters, canopy cards, fronds, needles, or blossom groups define foliage output.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("leaf", "canopy", "frond", "needle", "blossom"),
        recommendation_template="Add leaf clusters, canopy cards, fronds, needles, or blossom groups.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="root_anchor_system",
        description="Root anchors, ground contact pads, soil grip markers, or root spread curves attach vegetation to terrain.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("root", "ground", "soil", "anchor", "spread"),
        recommendation_template="Add root anchors, ground contact pads, soil grip markers, or root spread curves.",
        graph_node_types=("socket", "rail"),
    ),
    FamilyRequirement(
        name="lod_billboard_set",
        description="LOD entries, billboard cards, impostor planes, distance tiers, or simplification tags define runtime scaling.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("lod", "billboard", "impostor", "distance", "simplification"),
        recommendation_template="Add LOD entries, billboard cards, impostor planes, distance tiers, or simplification tags.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="wind_motion_markers",
        description="Wind vectors, bend zones, sway arcs, stiffness bands, or motion channels drive animation-ready vegetation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wind", "bend", "sway", "stiffness", "motion"),
        recommendation_template="Add wind vectors, bend zones, sway arcs, stiffness bands, or motion channels.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="season_variant_slots",
        description="Season slots, growth stages, age variants, leaf-loss markers, or blossom states define variation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("season", "growth", "age", "leaf_loss", "blossom"),
        recommendation_template="Add season slots, growth stages, age variants, leaf-loss markers, or blossom states.",
        graph_node_types=("socket", "material_zone"),
    ),
    FamilyRequirement(
        name="growth_parameter_ports",
        description="Height, spread, density, seed, age, or pruning ports expose authored variation controls.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("height", "spread", "density", "seed", "pruning"),
        recommendation_template="Add height, spread, density, seed, age, or pruning ports.",
        graph_node_types=("socket", "fastener"),
    ),
    FamilyRequirement(
        name="biome_distribution_masks",
        description="Biome masks, scatter weights, slope filters, wetness bands, or density fields place vegetation in worlds.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("biome", "scatter", "slope", "wetness", "density"),
        recommendation_template="Add biome masks, scatter weights, slope filters, wetness bands, or density fields.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="vegetation_usage_wear_masks",
        description="Growth wear, pruning marks, path rub, biome edits, or authoring scuffs show usage and iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "pruning", "rub", "edit", "scuff"),
        recommendation_template="Add growth wear, pruning marks, path rub, biome edits, or authoring scuffs.",
        graph_node_types=("wear_zone",),
    ),
)


_TERRAIN_HEIGHTFIELD_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="heightfield_domain",
        description="Heightfield domains, terrain extents, grid bounds, resolution tiles, or world cells define the terrain surface.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("heightfield", "extent", "grid", "resolution", "cell"),
        recommendation_template="Add heightfield domains, terrain extents, grid bounds, resolution tiles, or world cells.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="elevation_layers",
        description="Elevation layers, strata steps, contour bands, terraces, or height ramps define vertical structure.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("elevation", "strata", "contour", "terrace", "height"),
        recommendation_template="Add elevation layers, strata steps, contour bands, terraces, or height ramps.",
        graph_node_types=("panel", "trim"),
    ),
    FamilyRequirement(
        name="erosion_flow_network",
        description="Hydraulic flows, thermal erosion paths, stream lines, sediment routes, or runoff arrows define erosion.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("hydraulic", "thermal", "stream", "sediment", "runoff"),
        recommendation_template="Add hydraulic flows, thermal erosion paths, stream lines, sediment routes, or runoff arrows.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="slope_deposition_masks",
        description="Slope masks, deposition fields, talus bands, flow accumulation, or stability zones drive materials.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("slope", "deposition", "talus", "accumulation", "stability"),
        recommendation_template="Add slope masks, deposition fields, talus bands, flow accumulation, or stability zones.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="biome_material_zones",
        description="Biome zones, material bands, wetness masks, vegetation masks, or surface-graph outputs define look.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("biome", "material", "wetness", "vegetation", "surface"),
        recommendation_template="Add biome zones, material bands, wetness masks, vegetation masks, or surface-graph outputs.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="water_drainage_channels",
        description="Drainage channels, river paths, catchments, lake basins, or water-level marks define hydrology.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("drainage", "river", "catchment", "lake", "water"),
        recommendation_template="Add drainage channels, river paths, catchments, lake basins, or water-level marks.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="terrain_to_mesh_exports",
        description="Mesh export ports, collider outputs, LOD tiles, normal maps, or height maps connect terrain to assets.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("mesh", "collider", "lod", "normal", "export"),
        recommendation_template="Add mesh export ports, collider outputs, LOD tiles, normal maps, or height maps.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="sample_probe_grid",
        description="Probe grids, sample points, debug pins, inspection ticks, or slope markers make terrain inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("probe", "sample", "debug", "inspection", "marker"),
        recommendation_template="Add probe grids, sample points, debug pins, inspection ticks, or slope markers.",
        graph_node_types=("fastener", "panel"),
    ),
    FamilyRequirement(
        name="boundary_tileability_edges",
        description="Tileability edges, seam guards, chunk borders, blend skirts, or neighbor ports support world stitching.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("tile", "seam", "chunk", "blend", "neighbor"),
        recommendation_template="Add tileability edges, seam guards, chunk borders, blend skirts, or neighbor ports.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="terrain_iteration_wear_masks",
        description="Erosion wear, sculpt edits, repeated solves, flow residue, or biome-paint scuffs show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("erosion", "sculpt", "solve", "residue", "paint"),
        recommendation_template="Add erosion wear, sculpt edits, repeated solves, flow residue, or biome-paint scuffs.",
        graph_node_types=("wear_zone",),
    ),
)


_WFC_TILE_SOLVER_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="tileset_catalog",
        description="Tile catalogs, module palettes, piece IDs, variant entries, or kit cards define available tiles.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("tileset", "catalog", "module", "variant", "piece"),
        recommendation_template="Add tile catalogs, module palettes, piece IDs, variant entries, or kit cards.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="socket_edge_definitions",
        description="Socket edges, connector codes, port tags, open sides, or match keys define tile compatibility.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("socket", "connector", "port", "side", "match"),
        recommendation_template="Add socket edges, connector codes, port tags, open sides, or match keys.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="adjacency_rule_matrix",
        description="Adjacency matrices, neighbor rules, legal pairs, directional constraints, or banned pairs drive WFC.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("adjacency", "neighbor", "legal", "direction", "banned"),
        recommendation_template="Add adjacency matrices, neighbor rules, legal pairs, directional constraints, or banned pairs.",
        graph_node_types=("material_zone", "guard"),
    ),
    FamilyRequirement(
        name="constraint_grid",
        description="Constraint grids, cells, chunks, bounds, or domain footprints define the solve area.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("constraint", "grid", "cell", "chunk", "domain"),
        recommendation_template="Add constraint grids, cells, chunks, bounds, or domain footprints.",
        graph_node_types=("primary_volume", "rail"),
    ),
    FamilyRequirement(
        name="entropy_or_weight_markers",
        description="Entropy values, weights, probabilities, priority tags, or rarity bands steer collapse.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("entropy", "weight", "probability", "priority", "rarity"),
        recommendation_template="Add entropy values, weights, probabilities, priority tags, or rarity bands.",
        graph_node_types=("fastener", "decal_zone"),
    ),
    FamilyRequirement(
        name="seed_and_region_ports",
        description="Seed ports, region anchors, pinned cells, boundary inputs, or start/end markers shape the result.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("seed", "region", "pin", "boundary", "start"),
        recommendation_template="Add seed ports, region anchors, pinned cells, boundary inputs, or start/end markers.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="solver_iteration_path",
        description="Collapse paths, propagation arrows, iteration ticks, queue markers, or solve traces make WFC inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("collapse", "propagation", "iteration", "queue", "trace"),
        recommendation_template="Add collapse paths, propagation arrows, iteration ticks, queue markers, or solve traces.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="failure_or_backtrack_guards",
        description="Failure guards, contradiction markers, backtrack rails, dead-end chips, or retry badges show invalid solves.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("failure", "contradiction", "backtrack", "dead", "retry"),
        recommendation_template="Add failure guards, contradiction markers, backtrack rails, dead-end chips, or retry badges.",
        graph_node_types=("guard", "decal_zone"),
    ),
    FamilyRequirement(
        name="solved_layout_output",
        description="Solved layouts, output paths, placed modules, room graphs, or dungeon strips show result geometry.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("solved", "layout", "placed", "room", "dungeon"),
        recommendation_template="Add solved layouts, output paths, placed modules, room graphs, or dungeon strips.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="tile_usage_wear_masks",
        description="Tile wear, solver scuffs, repeated-collapse marks, connector rub, or layout edits show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "scuff", "collapse", "rub", "edit"),
        recommendation_template="Add tile wear, solver scuffs, repeated-collapse marks, connector rub, or layout edits.",
        graph_node_types=("wear_zone",),
    ),
)


_CGA_BUILDING_GRAMMAR_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="root_massing_volume",
        description="Root massing volumes, lots, envelopes, parcels, or building blocks seed grammar derivation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("root", "mass", "lot", "envelope", "parcel"),
        recommendation_template="Add root massing volumes, lots, envelopes, parcels, or building blocks.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="rule_stack",
        description="Rule stacks, production rules, named grammar steps, derivation chains, or operator lists define generation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("rule", "production", "step", "derivation", "operator"),
        recommendation_template="Add rule stacks, production rules, named grammar steps, derivation chains, or operator lists.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="split_repeat_extrude_ops",
        description="Split, repeat, extrude, offset, or choose operators express CGA-style refinement.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("split", "repeat", "extrude", "offset", "choose"),
        recommendation_template="Add split, repeat, extrude, offset, or choose operators.",
        graph_node_types=("rail", "socket"),
    ),
    FamilyRequirement(
        name="facade_floor_bands",
        description="Facade bands, floor strips, bay rhythms, window rows, or cornice belts define building faces.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("facade", "floor", "bay", "window", "cornice"),
        recommendation_template="Add facade bands, floor strips, bay rhythms, window rows, or cornice belts.",
        graph_node_types=("material_zone", "trim"),
    ),
    FamilyRequirement(
        name="terminal_module_set",
        description="Terminal modules, wall tiles, window units, door units, roof caps, or detail pieces end derivation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("terminal", "wall", "window", "door", "roof"),
        recommendation_template="Add terminal modules, wall tiles, window units, door units, roof caps, or detail pieces.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="derivation_flow_lines",
        description="Derivation arrows, refinement paths, parent-child links, or graph traces explain rule expansion.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("arrow", "refinement", "parent", "child", "trace"),
        recommendation_template="Add derivation arrows, refinement paths, parent-child links, or graph traces.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="variation_parameter_ports",
        description="Height, frontage, depth, style, seed, or zoning ports expose authored building variation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("height", "frontage", "depth", "style", "zoning"),
        recommendation_template="Add height, frontage, depth, style, seed, or zoning ports.",
        graph_node_types=("socket", "fastener"),
    ),
    FamilyRequirement(
        name="constraint_or_guard_rules",
        description="Setback guards, zoning rules, collision checks, illegal splits, or max-height badges protect output.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("setback", "zoning", "collision", "illegal", "max"),
        recommendation_template="Add setback guards, zoning rules, collision checks, illegal splits, or max-height badges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="output_assembly_markers",
        description="Output markers, generated shells, assembly IDs, export tags, or building-lot labels show result surfaces.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("output", "generated", "assembly", "export", "label"),
        recommendation_template="Add output markers, generated shells, assembly IDs, export tags, or building-lot labels.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="grammar_iteration_wear_masks",
        description="Rule-edit wear, derivation scuffs, facade revisions, split residue, or authored override marks show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("edit", "scuff", "revision", "residue", "override"),
        recommendation_template="Add rule-edit wear, derivation scuffs, facade revisions, split residue, or authored override marks.",
        graph_node_types=("wear_zone",),
    ),
)


_VOLUME_EFFECTS_DATA_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="volume_domain_bounds",
        description="Volume domains, sparse grids, VDB bounds, voxel extents, or simulation boxes define the field.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("volume", "grid", "vdb", "voxel", "bounds"),
        recommendation_template="Add volume domains, sparse grids, VDB bounds, voxel extents, or simulation boxes.",
        graph_node_types=("primary_volume", "guard"),
    ),
    FamilyRequirement(
        name="density_temperature_velocity_channels",
        description="Density, temperature, velocity, fuel, smoke, or pressure channels define field data.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("density", "temperature", "velocity", "fuel", "pressure"),
        recommendation_template="Add density, temperature, velocity, fuel, smoke, or pressure channels.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="emitters_and_sources",
        description="Emitters, sources, injectors, vents, flame roots, or fluid inlets seed the volume.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("emitter", "source", "injector", "vent", "inlet"),
        recommendation_template="Add emitters, sources, injectors, vents, flame roots, or fluid inlets.",
        graph_node_types=("socket", "mount"),
    ),
    FamilyRequirement(
        name="force_or_flow_vectors",
        description="Force vectors, flow arrows, wind fields, vortices, or advection paths drive motion.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("force", "flow", "wind", "vortex", "advection"),
        recommendation_template="Add force vectors, flow arrows, wind fields, vortices, or advection paths.",
        graph_node_types=("rail", "decal_zone"),
    ),
    FamilyRequirement(
        name="slice_or_sample_planes",
        description="Slice planes, sample slabs, debug cuts, section views, or probe layers expose internals.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("slice", "sample", "debug", "section", "probe"),
        recommendation_template="Add slice planes, sample slabs, debug cuts, section views, or probe layers.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="threshold_or_isosurface_controls",
        description="Thresholds, isosurfaces, contour values, density cutoffs, or marching settings define meshing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("threshold", "isosurface", "contour", "cutoff", "marching"),
        recommendation_template="Add thresholds, isosurfaces, contour values, density cutoffs, or marching settings.",
        graph_node_types=("trim", "fastener"),
    ),
    FamilyRequirement(
        name="mesh_or_particle_outputs",
        description="Mesh outputs, particle outputs, cache exports, flipbook planes, or render ports connect the result.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("mesh", "particle", "cache", "flipbook", "render"),
        recommendation_template="Add mesh outputs, particle outputs, cache exports, flipbook planes, or render ports.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="cache_tile_markers",
        description="Cache tiles, bricks, sparse blocks, page markers, or clipmap levels show volume storage.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("cache", "tile", "brick", "page", "clipmap"),
        recommendation_template="Add cache tiles, bricks, sparse blocks, page markers, or clipmap levels.",
        graph_node_types=("panel", "fastener"),
    ),
    FamilyRequirement(
        name="field_boundary_guards",
        description="Boundary guards, collision masks, blockers, containment rails, or kill planes constrain the field.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("boundary", "collision", "blocker", "containment", "kill"),
        recommendation_template="Add boundary guards, collision masks, blockers, containment rails, or kill planes.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="volume_iteration_wear_masks",
        description="Solve wear, repeated-cache marks, field edits, residue, or iteration scuffs show authoring history.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("solve", "cache", "edit", "residue", "scuff"),
        recommendation_template="Add solve wear, repeated-cache marks, field edits, residue, or iteration scuffs.",
        graph_node_types=("wear_zone",),
    ),
)


_INSTANCE_PATTERN_SCATTER_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="source_part_library",
        description="Source parts, greeble kits, rivet caps, vegetation tufts, prop modules, or prefab cards define what is scattered.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("source", "greeble", "rivet", "tuft", "prefab"),
        recommendation_template="Add source parts, greeble kits, rivet caps, vegetation tufts, prop modules, or prefab cards.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="point_cloud_or_samples",
        description="Point clouds, sample points, seeds, pins, or distribution anchors define instance positions.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("point", "sample", "seed", "pin", "anchor"),
        recommendation_template="Add point clouds, sample points, seeds, pins, or distribution anchors.",
        graph_node_types=("fastener", "rail"),
    ),
    FamilyRequirement(
        name="surface_projection_target",
        description="Surface targets, face selectors, projection rays, normals, or attachment planes define placement.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("surface", "face", "projection", "normal", "plane"),
        recommendation_template="Add surface targets, face selectors, projection rays, normals, or attachment planes.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="density_or_mask_controls",
        description="Density masks, weight maps, slope filters, curvature masks, or region gates control scatter.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("density", "weight", "slope", "curvature", "region"),
        recommendation_template="Add density masks, weight maps, slope filters, curvature masks, or region gates.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="poisson_or_spacing_rules",
        description="Poisson spacing, minimum distance, blue-noise rules, grid spacing, or avoidance radii prevent clumps.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("poisson", "spacing", "distance", "noise", "avoidance"),
        recommendation_template="Add Poisson spacing, minimum distance, blue-noise rules, grid spacing, or avoidance radii.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="orient_scale_jitter_controls",
        description="Orientation, normal alignment, scale ranges, random jitter, or roll/yaw bands vary instances.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("orient", "align", "scale", "jitter", "yaw"),
        recommendation_template="Add orientation, normal alignment, scale ranges, random jitter, or roll/yaw bands.",
        graph_node_types=("socket", "fastener"),
    ),
    FamilyRequirement(
        name="collision_or_exclusion_guards",
        description="Collision checks, exclusion zones, overlap guards, keepout masks, or clearance bands keep output usable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("collision", "exclusion", "overlap", "keepout", "clearance"),
        recommendation_template="Add collision checks, exclusion zones, overlap guards, keepout masks, or clearance bands.",
        graph_node_types=("guard", "decal_zone"),
    ),
    FamilyRequirement(
        name="instance_output_markers",
        description="Instance outputs, placed IDs, generated clusters, export tags, or count labels show result instances.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("instance", "placed", "cluster", "export", "count"),
        recommendation_template="Add instance outputs, placed IDs, generated clusters, export tags, or count labels.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="scatter_debug_traces",
        description="Debug traces, rejected points, sampling rays, pass ticks, or solver paths make scatter inspectable.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("debug", "rejected", "ray", "pass", "trace"),
        recommendation_template="Add debug traces, rejected points, sampling rays, pass ticks, or solver paths.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="scatter_usage_wear_masks",
        description="Scatter wear, projection rub, repeated-solve scuffs, point edits, or kit usage masks show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("wear", "rub", "scuff", "edit", "usage"),
        recommendation_template="Add scatter wear, projection rub, repeated-solve scuffs, point edits, or kit usage masks.",
        graph_node_types=("wear_zone",),
    ),
)


_F_REP_SDF_COMPOSITION_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="implicit_primitive_set",
        description="SDF primitives, implicit spheres, capsules, boxes, gyroids, or field sources define the composition atoms.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("sdf", "implicit", "sphere", "capsule", "field"),
        recommendation_template="Add SDF primitives, implicit spheres, capsules, boxes, gyroids, or field sources.",
        graph_node_types=("primary_volume", "socket"),
    ),
    FamilyRequirement(
        name="expression_tree",
        description="Expression trees, named lets, nodes, operands, or graph branches define implicit evaluation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("expression", "tree", "let", "operand", "branch"),
        recommendation_template="Add expression trees, named lets, nodes, operands, or graph branches.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="smooth_boolean_ops",
        description="Smooth union, smooth subtract, intersect, blend, or difference operators compose fields.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("union", "subtract", "intersect", "blend", "difference"),
        recommendation_template="Add smooth union, smooth subtract, intersect, blend, or difference operators.",
        graph_node_types=("rail", "guard"),
    ),
    FamilyRequirement(
        name="blend_radius_controls",
        description="Blend radii, falloff knobs, softness bands, k-values, or smoothing controls tune transitions.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("radius", "falloff", "softness", "k", "smoothing"),
        recommendation_template="Add blend radii, falloff knobs, softness bands, k-values, or smoothing controls.",
        graph_node_types=("fastener", "socket"),
    ),
    FamilyRequirement(
        name="field_sample_bounds",
        description="Sample bounds, evaluation boxes, voxel domains, resolution tags, or clipping extents bound the field.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sample", "bounds", "voxel", "resolution", "clip"),
        recommendation_template="Add sample bounds, evaluation boxes, voxel domains, resolution tags, or clipping extents.",
        graph_node_types=("guard", "primary_volume"),
    ),
    FamilyRequirement(
        name="material_region_fields",
        description="Material fields, region masks, inside/outside tags, distance bands, or color fields support surfacing.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("material", "region", "inside", "distance", "color"),
        recommendation_template="Add material fields, region masks, inside/outside tags, distance bands, or color fields.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="extraction_or_meshing_ports",
        description="Marching-cubes ports, dual-contouring tags, mesh outputs, iso ports, or contour extractors emit geometry.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("marching", "contouring", "mesh", "iso", "extract"),
        recommendation_template="Add marching-cubes ports, dual-contouring tags, mesh outputs, iso ports, or contour extractors.",
        graph_node_types=("socket", "decal_zone"),
    ),
    FamilyRequirement(
        name="failure_or_bounds_guards",
        description="Bounds guards, field warnings, NaN markers, open-surface guards, or invalid blend badges reject bad fields.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "warning", "nan", "open", "invalid"),
        recommendation_template="Add bounds guards, field warnings, NaN markers, open-surface guards, or invalid blend badges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="organic_silhouette_markers",
        description="Organic silhouettes, creature lobes, alien forms, soft organs, or blobby contours show intended use.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("organic", "creature", "alien", "soft", "blobby"),
        recommendation_template="Add organic silhouettes, creature lobes, alien forms, soft organs, or blobby contours.",
        graph_node_types=("primary_volume", "material_zone"),
    ),
    FamilyRequirement(
        name="implicit_iteration_wear_masks",
        description="Field-edit wear, extraction scuffs, blend residue, repeated solve marks, or sculpt edits show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("edit", "scuff", "residue", "solve", "sculpt"),
        recommendation_template="Add field-edit wear, extraction scuffs, blend residue, repeated solve marks, or sculpt edits.",
        graph_node_types=("wear_zone",),
    ),
)


_SUBDIVISION_FINISHING_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="control_cage",
        description="Control cages, coarse meshes, cage vertices, base shells, or low-poly controls define the source surface.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("cage", "coarse", "vertex", "base", "control"),
        recommendation_template="Add control cages, coarse meshes, cage vertices, base shells, or low-poly controls.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="subdivision_scheme",
        description="Catmull-Clark, Loop, OpenSubDiv, scheme tags, or subdivision level markers define the algorithm.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("catmull", "loop", "opensubdiv", "scheme", "level"),
        recommendation_template="Add Catmull-Clark, Loop, OpenSubDiv, scheme tags, or subdivision level markers.",
        graph_node_types=("decal_zone", "panel"),
    ),
    FamilyRequirement(
        name="crease_or_sharpness_tags",
        description="Crease tags, sharpness weights, edge creases, corner pins, or hard-boundary marks preserve features.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("crease", "sharpness", "edge", "corner", "pin"),
        recommendation_template="Add crease tags, sharpness weights, edge creases, corner pins, or hard-boundary marks.",
        graph_node_types=("trim", "rail"),
    ),
    FamilyRequirement(
        name="boundary_or_uv_rules",
        description="Boundary rules, UV interpolation tags, seam handling, edge modes, or open-boundary controls define continuity.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("boundary", "uv", "seam", "edge", "continuity"),
        recommendation_template="Add boundary rules, UV interpolation tags, seam handling, edge modes, or open-boundary controls.",
        graph_node_types=("guard", "decal_zone"),
    ),
    FamilyRequirement(
        name="remesh_or_quad_targets",
        description="Remesh targets, quad goals, edge-length controls, valence guides, or topology cleanup settings improve mesh flow.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("remesh", "quad", "edge_length", "valence", "topology"),
        recommendation_template="Add remesh targets, quad goals, edge-length controls, valence guides, or topology cleanup settings.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="smoothing_or_relax_passes",
        description="Smoothing passes, relax passes, Taubin filters, shrink guards, or normal smoothing tags finish surfaces.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("smooth", "relax", "taubin", "shrink", "normal"),
        recommendation_template="Add smoothing passes, relax passes, Taubin filters, shrink guards, or normal smoothing tags.",
        graph_node_types=("rail", "fastener"),
    ),
    FamilyRequirement(
        name="displacement_or_detail_layers",
        description="Displacement layers, detail maps, micro-noise, sculpt bands, or high-frequency overlays add finish.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("displacement", "detail", "noise", "sculpt", "overlay"),
        recommendation_template="Add displacement layers, detail maps, micro-noise, sculpt bands, or high-frequency overlays.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="quality_probe_markers",
        description="Quality probes, silhouette checks, curvature ticks, self-intersection guards, or thin-feature warnings inspect results.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("quality", "silhouette", "curvature", "intersection", "thin"),
        recommendation_template="Add quality probes, silhouette checks, curvature ticks, self-intersection guards, or thin-feature warnings.",
        graph_node_types=("fastener", "guard"),
    ),
    FamilyRequirement(
        name="output_lod_markers",
        description="Output LODs, high/low meshes, cage exports, preview surfaces, or bake targets show deliverables.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("lod", "high", "low", "export", "bake"),
        recommendation_template="Add output LODs, high/low meshes, cage exports, preview surfaces, or bake targets.",
        graph_node_types=("decal_zone", "socket"),
    ),
    FamilyRequirement(
        name="finishing_iteration_wear_masks",
        description="Review wear, polish scuffs, subdivision revisions, smoothing residue, or topology edits show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("review", "polish", "revision", "residue", "edit"),
        recommendation_template="Add review wear, polish scuffs, subdivision revisions, smoothing residue, or topology edits.",
        graph_node_types=("wear_zone",),
    ),
)


_HUMANOID_ANATOMY_PRESET_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="canonical_topology",
        description="Canonical topology, base mesh IDs, vertex regions, topology version tags, or mesh contracts define the anatomy.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("topology", "mesh", "vertex", "version", "contract"),
        recommendation_template="Add canonical topology, base mesh IDs, vertex regions, topology version tags, or mesh contracts.",
        graph_node_types=("primary_volume", "panel"),
    ),
    FamilyRequirement(
        name="body_proportion_set",
        description="Body proportions, height ratios, head counts, shoulder/hip widths, or chibi/realistic scale guides define silhouette.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("proportion", "height", "head", "shoulder", "hip"),
        recommendation_template="Add body proportions, height ratios, head counts, shoulder/hip widths, or scale guides.",
        graph_node_types=("panel", "rail"),
    ),
    FamilyRequirement(
        name="anatomy_region_map",
        description="Head, torso, limb, hand, foot, face, or region maps divide the body into authorable zones.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("head", "torso", "limb", "hand", "foot"),
        recommendation_template="Add head, torso, limb, hand, foot, face, or region maps.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="landmark_loop_set",
        description="Landmark loops, facial loops, joint loops, shoulder loops, mouth/eye loops, or edge rings preserve deformation.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("landmark", "loop", "joint", "mouth", "eye"),
        recommendation_template="Add landmark loops, facial loops, joint loops, shoulder loops, mouth/eye loops, or edge rings.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="joint_and_rig_anchors",
        description="Joint anchors, spine anchors, limb sockets, IK anchors, or attachment pivots connect anatomy to rigging.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("joint", "spine", "socket", "ik", "pivot"),
        recommendation_template="Add joint anchors, spine anchors, limb sockets, IK anchors, or attachment pivots.",
        graph_node_types=("socket", "fastener"),
    ),
    FamilyRequirement(
        name="morph_target_database",
        description="Morph targets, expressions, body-shape deltas, visemes, or corrective shapes define variation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("morph", "expression", "delta", "viseme", "corrective"),
        recommendation_template="Add morph targets, expressions, body-shape deltas, visemes, or corrective shapes.",
        graph_node_types=("panel", "material_zone"),
    ),
    FamilyRequirement(
        name="skin_weight_zones",
        description="Skin-weight zones, bone influences, deformation masks, envelope bands, or weight-paint guides support animation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("skin", "weight", "bone", "deformation", "envelope"),
        recommendation_template="Add skin-weight zones, bone influences, deformation masks, envelope bands, or weight-paint guides.",
        graph_node_types=("material_zone", "decal_zone"),
    ),
    FamilyRequirement(
        name="style_variant_slots",
        description="Realistic, chibi, anime, stylized, child/adult, or body-type variant slots define anatomy families.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("realistic", "chibi", "anime", "stylized", "adult"),
        recommendation_template="Add realistic, chibi, anime, stylized, child/adult, or body-type variant slots.",
        graph_node_types=("socket", "panel"),
    ),
    FamilyRequirement(
        name="anatomy_validation_guards",
        description="Topology guards, symmetry checks, range limits, invalid-proportion markers, or rig fit badges reject bad presets.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("guard", "symmetry", "range", "invalid", "fit"),
        recommendation_template="Add topology guards, symmetry checks, range limits, invalid-proportion markers, or rig fit badges.",
        graph_node_types=("guard", "trim"),
    ),
    FamilyRequirement(
        name="anatomy_iteration_wear_masks",
        description="Sculpt edits, morph revisions, topology review marks, rig-fit scuffs, or anatomy-authoring wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("sculpt", "revision", "review", "scuff", "wear"),
        recommendation_template="Add sculpt edits, morph revisions, topology review marks, rig-fit scuffs, or anatomy-authoring wear.",
        graph_node_types=("wear_zone",),
    ),
)


_FACE_SDF_CEL_SHADING_SYSTEM_REQUIREMENTS: tuple[FamilyRequirement, ...] = (
    FamilyRequirement(
        name="face_region_sdf",
        description="Face SDF regions, cheek/nose/mouth fields, facial ID masks, or expression fields define shading anchors.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("face", "sdf", "cheek", "nose", "mouth"),
        recommendation_template="Add face SDF regions, cheek/nose/mouth fields, facial ID masks, or expression fields.",
        graph_node_types=("primary_volume", "material_zone"),
    ),
    FamilyRequirement(
        name="shadow_band_fields",
        description="Shadow SDFs, band thresholds, cheek shadows, nose ramps, or eyelid shadow fields define anime lighting.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("shadow", "band", "threshold", "cheek", "eyelid"),
        recommendation_template="Add shadow SDFs, band thresholds, cheek shadows, nose ramps, or eyelid shadow fields.",
        graph_node_types=("material_zone", "panel"),
    ),
    FamilyRequirement(
        name="ramp_lut_stack",
        description="Ramp LUTs, color ramps, light bands, shade tables, or palette cells define cel response.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("ramp", "lut", "color", "shade", "palette"),
        recommendation_template="Add ramp LUTs, color ramps, light bands, shade tables, or palette cells.",
        graph_node_types=("panel", "decal_zone"),
    ),
    FamilyRequirement(
        name="outline_or_inverted_hull",
        description="Inverted hull outlines, Sobel channels, line width controls, rim bands, or outline masks define silhouette.",
        severity=_SEVERITY_REQUIRED,
        detection_signals=("outline", "inverted", "sobel", "line", "rim"),
        recommendation_template="Add inverted hull outlines, Sobel channels, line width controls, rim bands, or outline masks.",
        graph_node_types=("rail", "trim"),
    ),
    FamilyRequirement(
        name="light_direction_controls",
        description="Light direction controls, up vectors, key light ports, shadow pivots, or view-dependent markers steer shading.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("light", "direction", "up", "key", "view"),
        recommendation_template="Add light direction controls, up vectors, key light ports, shadow pivots, or view-dependent markers.",
        graph_node_types=("socket", "fastener"),
    ),
    FamilyRequirement(
        name="id_mask_channels",
        description="ID masks, material IDs, face zones, hair/skin/eye masks, or region labels bind stylized channels.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("id", "mask", "material", "hair", "skin"),
        recommendation_template="Add ID masks, material IDs, face zones, hair/skin/eye masks, or region labels.",
        graph_node_types=("decal_zone", "material_zone"),
    ),
    FamilyRequirement(
        name="style_bridge_guards",
        description="Style bridge guards, PBR/cel compatibility marks, forbidden mixes, bridge labels, or mismatch warnings reject bad styles.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("bridge", "pbr", "compat", "forbidden", "mismatch"),
        recommendation_template="Add style bridge guards, PBR/cel compatibility marks, forbidden mixes, bridge labels, or mismatch warnings.",
        graph_node_types=("guard", "decal_zone"),
    ),
    FamilyRequirement(
        name="preview_render_outputs",
        description="Preview outputs, ramp swatches, face thumbnails, outline previews, or light-turntable tiles show the result.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("preview", "swatch", "thumbnail", "turntable", "output"),
        recommendation_template="Add preview outputs, ramp swatches, face thumbnails, outline previews, or light-turntable tiles.",
        graph_node_types=("panel", "socket"),
    ),
    FamilyRequirement(
        name="expression_or_morph_hooks",
        description="Expression hooks, morph links, mouth/eye deformation inputs, blink states, or face-rig sockets connect animation.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("expression", "morph", "mouth", "eye", "blink"),
        recommendation_template="Add expression hooks, morph links, mouth/eye deformation inputs, blink states, or face-rig sockets.",
        graph_node_types=("socket", "rail"),
    ),
    FamilyRequirement(
        name="cel_iteration_wear_masks",
        description="Ramp edits, mask paint, outline revisions, face-shadow scuffs, or style-review wear show iteration.",
        severity=_SEVERITY_RECOMMENDED,
        detection_signals=("edit", "paint", "revision", "scuff", "review"),
        recommendation_template="Add ramp edits, mask paint, outline revisions, face-shadow scuffs, or style-review wear.",
        graph_node_types=("wear_zone",),
    ),
)


_GRAMMARS: dict[str, FamilyGrammar] = {
    "industrial_crate": FamilyGrammar(
        family="industrial_crate",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_INDUSTRIAL_CRATE_REQUIREMENTS,
    ),
    "mechanical_door": FamilyGrammar(
        family="mechanical_door",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_MECHANICAL_DOOR_REQUIREMENTS,
    ),
    "service_cabinet": FamilyGrammar(
        family="service_cabinet",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_SERVICE_CABINET_REQUIREMENTS,
    ),
    "weapon_prop": FamilyGrammar(
        family="weapon_prop",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_WEAPON_PROP_REQUIREMENTS,
    ),
    "vehicle_prop": FamilyGrammar(
        family="vehicle_prop",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_VEHICLE_PROP_REQUIREMENTS,
    ),
    "furniture_prop": FamilyGrammar(
        family="furniture_prop",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_FURNITURE_PROP_REQUIREMENTS,
    ),
    "natural_form": FamilyGrammar(
        family="natural_form",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_NATURAL_FORM_REQUIREMENTS,
    ),
    "environment_architecture": FamilyGrammar(
        family="environment_architecture",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_ENVIRONMENT_ARCHITECTURE_REQUIREMENTS,
    ),
    "lighting_prop": FamilyGrammar(
        family="lighting_prop",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_LIGHTING_PROP_REQUIREMENTS,
    ),
    "machine_console": FamilyGrammar(
        family="machine_console",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_MACHINE_CONSOLE_REQUIREMENTS,
    ),
    "portal_relic": FamilyGrammar(
        family="portal_relic",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_PORTAL_RELIC_REQUIREMENTS,
    ),
    "tool_prop": FamilyGrammar(
        family="tool_prop",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_TOOL_PROP_REQUIREMENTS,
    ),
    "modular_kit": FamilyGrammar(
        family="modular_kit",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_MODULAR_KIT_REQUIREMENTS,
    ),
    "character_creature": FamilyGrammar(
        family="character_creature",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CHARACTER_CREATURE_REQUIREMENTS,
    ),
    "set_dressing_prop": FamilyGrammar(
        family="set_dressing_prop",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_SET_DRESSING_PROP_REQUIREMENTS,
    ),
    "surface_material_sample": FamilyGrammar(
        family="surface_material_sample",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_SURFACE_MATERIAL_SAMPLE_REQUIREMENTS,
    ),
    "terrain_vegetation_variant": FamilyGrammar(
        family="terrain_vegetation_variant",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_TERRAIN_VEGETATION_VARIANT_REQUIREMENTS,
    ),
    "environment_effect": FamilyGrammar(
        family="environment_effect",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_ENVIRONMENT_EFFECT_REQUIREMENTS,
    ),
    "settlement_district": FamilyGrammar(
        family="settlement_district",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_SETTLEMENT_DISTRICT_REQUIREMENTS,
    ),
    "gameplay_object": FamilyGrammar(
        family="gameplay_object",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_GAMEPLAY_OBJECT_REQUIREMENTS,
    ),
    "encounter_flow": FamilyGrammar(
        family="encounter_flow",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_ENCOUNTER_FLOW_REQUIREMENTS,
    ),
    "inventory_economy_object": FamilyGrammar(
        family="inventory_economy_object",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_INVENTORY_ECONOMY_OBJECT_REQUIREMENTS,
    ),
    "rig_animation_proxy": FamilyGrammar(
        family="rig_animation_proxy",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_RIG_ANIMATION_PROXY_REQUIREMENTS,
    ),
    "rig_component_library_system": FamilyGrammar(
        family="rig_component_library_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_RIG_COMPONENT_LIBRARY_SYSTEM_REQUIREMENTS,
    ),
    "morph_target_database_system": FamilyGrammar(
        family="morph_target_database_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_MORPH_TARGET_DATABASE_SYSTEM_REQUIREMENTS,
    ),
    "animation_library_binding_system": FamilyGrammar(
        family="animation_library_binding_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_ANIMATION_LIBRARY_BINDING_SYSTEM_REQUIREMENTS,
    ),
    "retargeting_pack_system": FamilyGrammar(
        family="retargeting_pack_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_RETARGETING_PACK_SYSTEM_REQUIREMENTS,
    ),
    "character_equipment_binding_system": FamilyGrammar(
        family="character_equipment_binding_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CHARACTER_EQUIPMENT_BINDING_SYSTEM_REQUIREMENTS,
    ),
    "gameplay_animation_controller_system": FamilyGrammar(
        family="gameplay_animation_controller_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_GAMEPLAY_ANIMATION_CONTROLLER_SYSTEM_REQUIREMENTS,
    ),
    "procedural_facial_rig_pack_system": FamilyGrammar(
        family="procedural_facial_rig_pack_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_PROCEDURAL_FACIAL_RIG_PACK_SYSTEM_REQUIREMENTS,
    ),
    "hair_program_system": FamilyGrammar(
        family="hair_program_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_HAIR_PROGRAM_SYSTEM_REQUIREMENTS,
    ),
    "cloth_fabric_simulation_program_system": FamilyGrammar(
        family="cloth_fabric_simulation_program_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CLOTH_FABRIC_SIMULATION_PROGRAM_SYSTEM_REQUIREMENTS,
    ),
    "fluid_forward_volume_program_system": FamilyGrammar(
        family="fluid_forward_volume_program_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_FLUID_FORWARD_VOLUME_PROGRAM_SYSTEM_REQUIREMENTS,
    ),
    "construction_grammar_kit_system": FamilyGrammar(
        family="construction_grammar_kit_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CONSTRUCTION_GRAMMAR_KIT_SYSTEM_REQUIREMENTS,
    ),
    "creature_appendage_program_system": FamilyGrammar(
        family="creature_appendage_program_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CREATURE_APPENDAGE_PROGRAM_SYSTEM_REQUIREMENTS,
    ),
    "body_part_procedural_library_system": FamilyGrammar(
        family="body_part_procedural_library_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_BODY_PART_PROCEDURAL_LIBRARY_SYSTEM_REQUIREMENTS,
    ),
    "material_primitive_library_system": FamilyGrammar(
        family="material_primitive_library_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_MATERIAL_PRIMITIVE_LIBRARY_SYSTEM_REQUIREMENTS,
    ),
    "stateful_destructible_prop": FamilyGrammar(
        family="stateful_destructible_prop",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_STATEFUL_DESTRUCTIBLE_PROP_REQUIREMENTS,
    ),
    "cloth_attachment_form": FamilyGrammar(
        family="cloth_attachment_form",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CLOTH_ATTACHMENT_FORM_REQUIREMENTS,
    ),
    "domain_kit_bundle": FamilyGrammar(
        family="domain_kit_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_DOMAIN_KIT_BUNDLE_REQUIREMENTS,
    ),
    "world_system_assembly": FamilyGrammar(
        family="world_system_assembly",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_WORLD_SYSTEM_ASSEMBLY_REQUIREMENTS,
    ),
    "simulation_environment_system": FamilyGrammar(
        family="simulation_environment_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_SIMULATION_ENVIRONMENT_SYSTEM_REQUIREMENTS,
    ),
    "authored_multi_asset_bundle": FamilyGrammar(
        family="authored_multi_asset_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_AUTHORED_MULTI_ASSET_BUNDLE_REQUIREMENTS,
    ),
    "live_procedural_runtime_bundle": FamilyGrammar(
        family="live_procedural_runtime_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_LIVE_PROCEDURAL_RUNTIME_BUNDLE_REQUIREMENTS,
    ),
    "engine_facing_runtime_bundle_system": FamilyGrammar(
        family="engine_facing_runtime_bundle_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_ENGINE_FACING_RUNTIME_BUNDLE_SYSTEM_REQUIREMENTS,
    ),
    "procedural_prefab_binding_system": FamilyGrammar(
        family="procedural_prefab_binding_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_PROCEDURAL_PREFAB_BINDING_SYSTEM_REQUIREMENTS,
    ),
    "scene_system_authoring_bundle": FamilyGrammar(
        family="scene_system_authoring_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_SCENE_SYSTEM_AUTHORING_BUNDLE_REQUIREMENTS,
    ),
    "behavior_logic_graph_bundle": FamilyGrammar(
        family="behavior_logic_graph_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_BEHAVIOR_LOGIC_GRAPH_BUNDLE_REQUIREMENTS,
    ),
    "world_streaming_runtime_partition_bundle": FamilyGrammar(
        family="world_streaming_runtime_partition_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_WORLD_STREAMING_RUNTIME_PARTITION_BUNDLE_REQUIREMENTS,
    ),
    "save_state_persistence_bundle": FamilyGrammar(
        family="save_state_persistence_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_SAVE_STATE_PERSISTENCE_BUNDLE_REQUIREMENTS,
    ),
    "quest_dialogue_authoring_bundle": FamilyGrammar(
        family="quest_dialogue_authoring_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_QUEST_DIALOGUE_AUTHORING_BUNDLE_REQUIREMENTS,
    ),
    "camera_cinematic_direction_bundle": FamilyGrammar(
        family="camera_cinematic_direction_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CAMERA_CINEMATIC_DIRECTION_BUNDLE_REQUIREMENTS,
    ),
    "procedural_audio_cue_bundle": FamilyGrammar(
        family="procedural_audio_cue_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_PROCEDURAL_AUDIO_CUE_BUNDLE_REQUIREMENTS,
    ),
    "localization_text_table_bundle": FamilyGrammar(
        family="localization_text_table_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_LOCALIZATION_TEXT_TABLE_BUNDLE_REQUIREMENTS,
    ),
    "accessibility_ux_affordance_bundle": FamilyGrammar(
        family="accessibility_ux_affordance_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_ACCESSIBILITY_UX_AFFORDANCE_BUNDLE_REQUIREMENTS,
    ),
    "economy_simulation_tuning_bundle": FamilyGrammar(
        family="economy_simulation_tuning_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_ECONOMY_SIMULATION_TUNING_BUNDLE_REQUIREMENTS,
    ),
    "multiplayer_session_replication_bundle": FamilyGrammar(
        family="multiplayer_session_replication_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_MULTIPLAYER_SESSION_REPLICATION_BUNDLE_REQUIREMENTS,
    ),
    "cross_domain_composition_pack": FamilyGrammar(
        family="cross_domain_composition_pack",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CROSS_DOMAIN_COMPOSITION_PACK_REQUIREMENTS,
    ),
    "style_stack_visual_band": FamilyGrammar(
        family="style_stack_visual_band",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_STYLE_STACK_VISUAL_BAND_REQUIREMENTS,
    ),
    "typed_data_kernel_bundle": FamilyGrammar(
        family="typed_data_kernel_bundle",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_TYPED_DATA_KERNEL_BUNDLE_REQUIREMENTS,
    ),
    "attribute_surface_graph_program": FamilyGrammar(
        family="attribute_surface_graph_program",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_ATTRIBUTE_SURFACE_GRAPH_PROGRAM_REQUIREMENTS,
    ),
    "vegetation_library_system": FamilyGrammar(
        family="vegetation_library_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_VEGETATION_LIBRARY_SYSTEM_REQUIREMENTS,
    ),
    "terrain_heightfield_system": FamilyGrammar(
        family="terrain_heightfield_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_TERRAIN_HEIGHTFIELD_SYSTEM_REQUIREMENTS,
    ),
    "wfc_tile_solver_system": FamilyGrammar(
        family="wfc_tile_solver_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_WFC_TILE_SOLVER_SYSTEM_REQUIREMENTS,
    ),
    "cga_building_grammar_system": FamilyGrammar(
        family="cga_building_grammar_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_CGA_BUILDING_GRAMMAR_SYSTEM_REQUIREMENTS,
    ),
    "volume_effects_data_system": FamilyGrammar(
        family="volume_effects_data_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_VOLUME_EFFECTS_DATA_SYSTEM_REQUIREMENTS,
    ),
    "instance_pattern_scatter_system": FamilyGrammar(
        family="instance_pattern_scatter_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_INSTANCE_PATTERN_SCATTER_SYSTEM_REQUIREMENTS,
    ),
    "f_rep_sdf_composition_system": FamilyGrammar(
        family="f_rep_sdf_composition_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_F_REP_SDF_COMPOSITION_SYSTEM_REQUIREMENTS,
    ),
    "subdivision_finishing_system": FamilyGrammar(
        family="subdivision_finishing_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_SUBDIVISION_FINISHING_SYSTEM_REQUIREMENTS,
    ),
    "humanoid_anatomy_preset_system": FamilyGrammar(
        family="humanoid_anatomy_preset_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_HUMANOID_ANATOMY_PRESET_SYSTEM_REQUIREMENTS,
    ),
    "face_sdf_cel_shading_system": FamilyGrammar(
        family="face_sdf_cel_shading_system",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=_FACE_SDF_CEL_SHADING_SYSTEM_REQUIREMENTS,
    ),
    "generic": FamilyGrammar(
        family="generic",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=(),
    ),
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalised_parts(asset: dict[str, Any]) -> list[str]:
    """Return ``asset["intent"]["parts"]`` lowercased, tolerating shape drift."""
    intent = _as_dict(asset.get("intent"))
    raw_parts = _as_list(intent.get("parts"))
    parts: list[str] = []
    for part in raw_parts:
        if isinstance(part, str):
            parts.append(part.lower())
    return parts


def _detect_requirement(
    requirement: FamilyRequirement,
    parts: list[str],
    graph_nodes: tuple[dict[str, Any], ...] = (),
) -> tuple[str, list[str], list[str]]:
    """Return ``(status, matched_parts, matched_graph_nodes)`` for one requirement.

    Phase 4 detection precedence:

    1. Substring match against ``asset["intent"]["parts"]`` -> ``"satisfied"``.
    2. Otherwise, ``node_type`` match against the construction graph
       (``runtime["construction_graph"]["nodes"]``) -> ``"partial"``.
    3. Otherwise -> ``"missing"``.

    Parts wins over graph evidence because parts are explicit authoring
    intent, while graph evidence is derived. ``graph_nodes`` is a tuple
    of node dicts (each with at least ``node_id`` and ``node_type``) and
    defaults to the empty tuple, preserving Phase 3 behaviour for
    callers that don't pass graph evidence.
    """
    matched_parts: list[str] = []
    for part in parts:
        for token in requirement.detection_signals:
            if token in part:
                matched_parts.append(part)
                break
    if matched_parts:
        return _STATUS_SATISFIED, matched_parts, []

    matched_graph_nodes: list[str] = []
    if requirement.graph_node_types and graph_nodes:
        allowlist = set(requirement.graph_node_types)
        for entry in graph_nodes:
            if not isinstance(entry, dict):
                continue
            node_type = entry.get("node_type")
            if not isinstance(node_type, str) or node_type not in allowlist:
                continue
            node_id = entry.get("node_id")
            if isinstance(node_id, str) and node_id:
                matched_graph_nodes.append(node_id)
    if matched_graph_nodes:
        return _STATUS_PARTIAL, matched_parts, matched_graph_nodes
    return _STATUS_MISSING, matched_parts, matched_graph_nodes


def _compute_coverage(
    requirements: tuple[FamilyRequirement, ...],
    statuses: tuple[str, ...],
) -> float:
    """Return weighted coverage in ``[0.0, 1.0]``.

    Optional requirements do not count toward the denominator.
    Satisfied requirements contribute 1.0, partial contributes 0.5,
    missing contributes 0.0. ``not_applicable`` is excluded entirely
    (it neither helps nor hurts).
    """
    total_applicable = 0
    earned = 0.0
    for requirement, status in zip(requirements, statuses, strict=True):
        if requirement.severity == _SEVERITY_OPTIONAL:
            continue
        if status == _STATUS_NOT_APPLICABLE:
            continue
        total_applicable += 1
        if status == _STATUS_SATISFIED:
            earned += 1.0
        elif status == _STATUS_PARTIAL:
            earned += 0.5
    # Trivially satisfied: covers the empty-requirements path (generic
    # family fallback) today and the Phase 4+ case where every
    # requirement is "not_applicable" for a particular asset.
    if total_applicable == 0:
        return 1.0
    return round(earned / total_applicable, 6)


def _construction_graph_nodes(runtime: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return construction-graph nodes plus grammar-lowered recipe nodes.

    Tolerates an absent or malformed ``runtime["construction_graph"]``
    block by returning the empty tuple. Phase 3 callers that do not
    populate ``runtime["construction_graph"]`` therefore retain their
    original parts-only detection.

    Phase 6 publishes synthesized nodes under
    ``runtime["grammar_lowering"]["synthesized_graph_nodes"]``. They
    are merged into this read-only evidence view, with existing graph
    node IDs taking precedence, so the live construction-graph bundle is
    not mutated while family grammar coverage can reflect the recipe.
    """
    construction_graph = runtime.get("construction_graph")
    raw_nodes = construction_graph.get("nodes") if isinstance(construction_graph, dict) else []
    if not isinstance(raw_nodes, list):
        raw_nodes = []
    grammar_lowering = runtime.get("grammar_lowering")
    raw_synthesized = (
        grammar_lowering.get("synthesized_graph_nodes")
        if isinstance(grammar_lowering, dict)
        else []
    )
    if not isinstance(raw_synthesized, list):
        raw_synthesized = []

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entry in [*raw_nodes, *raw_synthesized]:
        if not isinstance(entry, dict):
            continue
        node_id = entry.get("node_id")
        if isinstance(node_id, str) and node_id:
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
        merged.append(entry)
    return tuple(merged)


def _result_for(
    grammar: FamilyGrammar,
    asset: dict[str, Any],
    runtime: dict[str, Any],
) -> FamilyGrammarResult:
    parts = _normalised_parts(asset)
    graph_nodes = _construction_graph_nodes(runtime)
    statuses: list[str] = []
    requirement_results: list[dict[str, Any]] = []
    recommendations: list[str] = []
    satisfied_count = 0
    partial_count = 0
    missing_count = 0

    for requirement in grammar.requirements:
        status, matched_parts, matched_graph_nodes = _detect_requirement(
            requirement, parts, graph_nodes
        )
        statuses.append(status)
        evidence: dict[str, Any] = {"matched_parts": list(matched_parts)}
        if matched_graph_nodes:
            evidence["matched_graph_nodes"] = list(matched_graph_nodes)
        requirement_results.append(
            {
                "name": requirement.name,
                "severity": requirement.severity,
                "status": status,
                "evidence": evidence,
            }
        )
        if status == _STATUS_SATISFIED:
            satisfied_count += 1
        elif status == _STATUS_PARTIAL:
            partial_count += 1
            recommendations.append(requirement.recommendation_template)
        elif status == _STATUS_MISSING:
            missing_count += 1
            recommendations.append(requirement.recommendation_template)

    coverage = _compute_coverage(grammar.requirements, tuple(statuses))

    return FamilyGrammarResult(
        family=grammar.family,
        version=grammar.version,
        requirement_results=tuple(requirement_results),
        coverage=coverage,
        satisfied_count=satisfied_count,
        partial_count=partial_count,
        missing_count=missing_count,
        recommendations=tuple(recommendations),
    )


def _resolve_family(runtime: dict[str, Any]) -> str:
    """Return the family token published by Phase 2's design_brief, or ``"generic"``."""
    design_brief = _as_dict(runtime.get("design_brief"))
    brief = _as_dict(design_brief.get("brief"))
    family = brief.get("family")
    if isinstance(family, str) and family:
        return family
    return "generic"


def _grammar_for(family: str) -> FamilyGrammar:
    return _GRAMMARS.get(family, _GRAMMARS["generic"])  # no-family-dispatch: family-grammar registry powering the family_grammar validator; migrate per-family rules to CompositionPolicy packs (Round 0 prototypes shipped: panelized_hard_surface_object, radial_mechanical_assembly, l_system_branching, wfc_modular_layout, scatter_distribution)


def evaluate_family_grammar(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive family-grammar payload for the validate stage.

    Args:
        asset: normalized asset dict. May omit ``intent`` or ``parts``;
            the function tolerates partial/empty input.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["design_brief"]["brief"]["family"]`` (populated by
            the Phase 2 design_brief validator running first in
            ``_PIPELINE``); falls back to ``"generic"`` when the brief
            is absent. Also reads ``runtime["construction_graph"]["nodes"]``
            (Phase 4) and uses the graph as fallback evidence: a
            requirement whose parts-list signals do not match but whose
            ``graph_node_types`` allowlist matches a graph node is
            elevated from ``"missing"`` to ``"partial"``. Absent or
            malformed graph data preserves the parts-only Phase 3 path.

    Returns:
        Additive payload with ``version`` (``"family_grammar_v1"``),
        ``family``, ``coverage``, per-status counts, ``requirement_results``
        (list of dicts with ``name``, ``severity``, ``status``, ``evidence``;
        ``evidence`` carries ``matched_parts`` always and additionally
        ``matched_graph_nodes`` when a graph-only elevation fired), and
        ``recommendations`` (one entry per missing/partial requirement in
        declaration order). No top-level ``diagnostics`` field — like
        Phases 1 and 2, this validator is informational only and never
        blocks certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    family = _resolve_family(safe_runtime)
    grammar = _grammar_for(family)
    result = _result_for(grammar, safe_asset, safe_runtime)
    return {
        "version": result.version,
        "family": result.family,
        "coverage": result.coverage,
        "satisfied_count": result.satisfied_count,
        "partial_count": result.partial_count,
        "missing_count": result.missing_count,
        "requirement_results": list(result.requirement_results),
        "recommendations": list(result.recommendations),
    }
