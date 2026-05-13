"""Phase 3 tests for ``lathe.asset_quality.family_grammar``.

Covers per task #3.4 of ``docs/asset-quality/improvement-tasklist.md``:

- ``FamilyRequirement`` / ``FamilyGrammar`` / ``FamilyGrammarResult``
  dataclasses construct correctly and stay frozen.
- The ``industrial_crate`` grammar has 10 requirements with 4 required +
  6 recommended severities.
- Coverage formula: empty asset -> 0.0; full coverage -> 1.0; the actual
  ``industrial_crate.lth`` baseline parts list -> 0.40.
- Per-requirement status is correct (satisfied vs missing) for
  representative inputs.
- Recommendations are emitted one per missing/partial requirement.
- Generic fallback grammar: unknown family -> coverage=1.0, no
  recommendations, no requirement_results.
- Missing ``runtime["design_brief"]`` falls back to generic gracefully.
- Missing ``intent`` / missing ``parts`` does not crash.
- Payload shape matches the master prompt exactly.
- Determinism: same input -> same output.
- Case-insensitive part matching.
- Absence of a ``diagnostics`` field so the FunctionValidator wrapper
  treats the validator as passing.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from lathe.asset_quality.family_grammar import (
    FAMILY_GRAMMAR_VERSION,
    FamilyGrammar,
    FamilyGrammarResult,
    FamilyRequirement,
    evaluate_family_grammar,
)

_EXPECTED_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "family",
        "coverage",
        "satisfied_count",
        "partial_count",
        "missing_count",
        "requirement_results",
        "recommendations",
    }
)


_INDUSTRIAL_CRATE_REQUIREMENT_NAMES: tuple[str, ...] = (
    "body_shell",
    "lid_seam",
    "corner_guards",
    "latch_or_latch_plate",
    "recessed_or_bracketed_handles",
    "foot_rails_or_feet",
    "trim_bands",
    "fasteners",
    "warning_or_decal_zones",
    "edge_wear_masks",
)


_MECHANICAL_DOOR_REQUIREMENT_NAMES: tuple[str, ...] = (
    "door_frame",
    "inset_door_leaf",
    "hinge_stack",
    "lock_or_actuator",
    "guide_or_threshold_rails",
    "panel_grooves",
    "access_handle",
    "fasteners",
    "warning_or_decal_zones",
    "edge_wear_masks",
)


_SERVICE_CABINET_REQUIREMENT_NAMES: tuple[str, ...] = (
    "cabinet_shell",
    "front_door_panel",
    "hinge_line",
    "pull_handle",
    "latch_or_lock_plate",
    "vent_slats",
    "mounting_brackets",
    "fasteners",
    "label_or_decal_zone",
    "edge_wear_masks",
)


_WEAPON_PROP_REQUIREMENT_NAMES: tuple[str, ...] = (
    "primary_weapon_body",
    "grip_or_handle",
    "guard_or_hand_stop",
    "active_edge_or_barrel",
    "centerline_detail",
    "pommel_or_end_cap",
    "socket_or_hardpoint",
    "fasteners",
    "marking_or_decal_zone",
    "edge_wear_masks",
)


_VEHICLE_PROP_REQUIREMENT_NAMES: tuple[str, ...] = (
    "primary_chassis_or_hull",
    "cabin_or_control_zone",
    "motion_system",
    "front_back_orientation",
    "cargo_or_payload_zone",
    "access_steps_or_handles",
    "lights_or_sensors",
    "mechanical_fasteners",
    "marking_or_decal_zone",
    "edge_wear_masks",
)


_FURNITURE_PROP_REQUIREMENT_NAMES: tuple[str, ...] = (
    "primary_contact_surface",
    "support_structure",
    "back_or_storage_volume",
    "trim_or_edge_band",
    "handle_or_pull",
    "fasteners_or_joinery",
    "cushion_or_soft_volume",
    "floor_contact_or_feet",
    "label_or_decal_zone",
    "edge_wear_masks",
)


_NATURAL_FORM_REQUIREMENT_NAMES: tuple[str, ...] = (
    "organic_primary_mass",
    "swept_growth_or_rooting",
    "clustered_secondary_forms",
    "surface_strata_or_bark",
    "ground_contact_transition",
    "asymmetric_silhouette_breaks",
    "small_detail_scatter",
    "material_zone_variation",
    "weathering_or_erosion_masks",
    "scale_anchor",
)


_ENVIRONMENT_ARCHITECTURE_REQUIREMENT_NAMES: tuple[str, ...] = (
    "floor_or_foundation",
    "wall_or_enclosure",
    "opening_system",
    "roof_or_cover",
    "vertical_supports",
    "circulation_or_access",
    "facade_trim_or_banding",
    "modular_bays",
    "lighting_or_signage_zone",
    "weathering_or_edge_wear",
)


_LIGHTING_PROP_REQUIREMENT_NAMES: tuple[str, ...] = (
    "base_or_mount",
    "support_or_armature",
    "emitter_or_lens",
    "housing_or_shade",
    "power_or_cable_route",
    "control_or_service_plate",
    "signage_or_marker_face",
    "fasteners",
    "protective_guard_or_cage",
    "soot_or_edge_wear_masks",
)


_MACHINE_CONSOLE_REQUIREMENT_NAMES: tuple[str, ...] = (
    "primary_machine_body",
    "control_face_or_panel",
    "display_or_readout",
    "input_controls",
    "service_access_panel",
    "ports_or_sockets",
    "cooling_or_ventilation",
    "cable_or_pipe_connections",
    "status_or_warning_markings",
    "service_wear_masks",
)


_PORTAL_RELIC_REQUIREMENT_NAMES: tuple[str, ...] = (
    "anchor_base_or_plinth",
    "frame_or_vertical_core",
    "threshold_or_active_center",
    "power_nodes_or_keystones",
    "radial_or_symmetric_layout",
    "runes_or_inscriptions",
    "offering_or_attachment_mounts",
    "conduits_or_energy_paths",
    "environment_contact",
    "age_or_aura_wear_masks",
)


_TOOL_PROP_REQUIREMENT_NAMES: tuple[str, ...] = (
    "primary_tool_body",
    "grip_or_handle",
    "working_head_or_bit",
    "shaft_or_spine",
    "guard_or_stop",
    "adjustment_or_joint",
    "sockets_or_attachment_points",
    "fasteners",
    "marking_or_scale_zone",
    "contact_wear_masks",
)


def _runtime_with_family(family: str) -> dict[str, Any]:
    """Build a runtime that publishes a Phase 2-style design_brief block."""
    return {"design_brief": {"brief": {"family": family}}}


def _crate_runtime() -> dict[str, Any]:
    return _runtime_with_family("industrial_crate")


def test_family_requirement_dataclass_is_frozen() -> None:
    req = FamilyRequirement(
        name="body_shell",
        description="primary body shell",
        severity="required",
        detection_signals=("body",),
        recommendation_template="Add a body shell.",
    )

    assert req.name == "body_shell"
    assert req.severity == "required"
    assert req.detection_signals == ("body",)
    assert req.recommendation_template == "Add a body shell."
    with pytest.raises(FrozenInstanceError):
        req.severity = "optional"  # type: ignore[misc]


def test_family_grammar_dataclass_is_frozen() -> None:
    requirement = FamilyRequirement(
        name="body_shell",
        description="primary body shell",
        severity="required",
        detection_signals=("body",),
        recommendation_template="Add a body shell.",
    )
    grammar = FamilyGrammar(
        family="industrial_crate",
        version=FAMILY_GRAMMAR_VERSION,
        requirements=(requirement,),
    )

    assert grammar.family == "industrial_crate"
    assert grammar.version == "family_grammar_v1"
    assert grammar.requirements == (requirement,)
    with pytest.raises(FrozenInstanceError):
        grammar.family = "mechanical_door"  # type: ignore[misc]


def test_family_grammar_result_dataclass_is_frozen() -> None:
    sample = FamilyGrammarResult(
        family="industrial_crate",
        version=FAMILY_GRAMMAR_VERSION,
        requirement_results=(
            {
                "name": "body_shell",
                "severity": "required",
                "status": "satisfied",
                "evidence": {"matched_parts": ["body"]},
            },
        ),
        coverage=1.0,
        satisfied_count=1,
        partial_count=0,
        missing_count=0,
        recommendations=(),
    )

    assert sample.coverage == 1.0
    assert sample.satisfied_count == 1
    with pytest.raises(FrozenInstanceError):
        sample.coverage = 0.0


def test_industrial_crate_grammar_has_ten_requirements_in_canonical_order() -> None:
    asset: dict[str, Any] = {"intent": {"parts": []}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _INDUSTRIAL_CRATE_REQUIREMENT_NAMES
    assert len(payload["requirement_results"]) == 10


def test_mechanical_door_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("mechanical_door"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _MECHANICAL_DOOR_REQUIREMENT_NAMES
    assert payload["family"] == "mechanical_door"
    assert len(payload["requirement_results"]) == 10


def test_service_cabinet_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("service_cabinet"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _SERVICE_CABINET_REQUIREMENT_NAMES
    assert payload["family"] == "service_cabinet"
    assert len(payload["requirement_results"]) == 10


def test_weapon_prop_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("weapon_prop"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _WEAPON_PROP_REQUIREMENT_NAMES
    assert payload["family"] == "weapon_prop"
    assert len(payload["requirement_results"]) == 10


def test_vehicle_prop_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("vehicle_prop"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _VEHICLE_PROP_REQUIREMENT_NAMES
    assert payload["family"] == "vehicle_prop"
    assert len(payload["requirement_results"]) == 10


def test_furniture_prop_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("furniture_prop"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _FURNITURE_PROP_REQUIREMENT_NAMES
    assert payload["family"] == "furniture_prop"
    assert len(payload["requirement_results"]) == 10


def test_natural_form_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("natural_form"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _NATURAL_FORM_REQUIREMENT_NAMES
    assert payload["family"] == "natural_form"
    assert len(payload["requirement_results"]) == 10


def test_environment_architecture_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("environment_architecture"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _ENVIRONMENT_ARCHITECTURE_REQUIREMENT_NAMES
    assert payload["family"] == "environment_architecture"
    assert len(payload["requirement_results"]) == 10


def test_lighting_prop_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("lighting_prop"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _LIGHTING_PROP_REQUIREMENT_NAMES
    assert payload["family"] == "lighting_prop"
    assert len(payload["requirement_results"]) == 10


def test_machine_console_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("machine_console"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _MACHINE_CONSOLE_REQUIREMENT_NAMES
    assert payload["family"] == "machine_console"
    assert len(payload["requirement_results"]) == 10


def test_portal_relic_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("portal_relic"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _PORTAL_RELIC_REQUIREMENT_NAMES
    assert payload["family"] == "portal_relic"
    assert len(payload["requirement_results"]) == 10


def test_tool_prop_grammar_has_ten_requirements_in_canonical_order() -> None:
    payload = evaluate_family_grammar(
        {"intent": {"parts": []}},
        _runtime_with_family("tool_prop"),
    )

    names = tuple(item["name"] for item in payload["requirement_results"])
    assert names == _TOOL_PROP_REQUIREMENT_NAMES
    assert payload["family"] == "tool_prop"
    assert len(payload["requirement_results"]) == 10


def test_industrial_crate_grammar_severity_split_matches_master_prompt() -> None:
    """Master-prompt Section 2 table: body_shell, lid_seam, corner_guards,
    latch_or_latch_plate, recessed_or_bracketed_handles are ``required``;
    foot_rails_or_feet, trim_bands, fasteners, warning_or_decal_zones,
    edge_wear_masks are ``recommended``. No ``optional`` requirements at
    Phase 3."""
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    severities = [item["severity"] for item in payload["requirement_results"]]
    assert severities.count("required") == 5
    assert severities.count("recommended") == 5
    assert severities.count("optional") == 0


def test_industrial_crate_required_set_matches_master_prompt() -> None:
    """Required = body_shell, lid_seam, corner_guards, latch_or_latch_plate,
    recessed_or_bracketed_handles. Locks the canonical encoding."""
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    required_names = {
        item["name"]
        for item in payload["requirement_results"]
        if item["severity"] == "required"
    }
    assert required_names == {
        "body_shell",
        "lid_seam",
        "corner_guards",
        "latch_or_latch_plate",
        "recessed_or_bracketed_handles",
    }


def test_payload_shape_matches_phase_3_contract() -> None:
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    assert payload["version"] == FAMILY_GRAMMAR_VERSION
    assert FAMILY_GRAMMAR_VERSION == "family_grammar_v1"
    assert set(payload.keys()) == _EXPECTED_PAYLOAD_KEYS
    assert isinstance(payload["coverage"], float)
    assert isinstance(payload["requirement_results"], list)
    assert isinstance(payload["recommendations"], list)
    assert isinstance(payload["satisfied_count"], int)
    assert isinstance(payload["partial_count"], int)
    assert isinstance(payload["missing_count"], int)


def test_no_diagnostics_field_so_validator_pipeline_treats_as_passing() -> None:
    """Mirrors Phase 1/2's contract: ``FunctionValidator`` only flips
    ``passes`` to ``False`` when a diagnostics entry has ``severity == 'error'``.
    Returning no ``diagnostics`` field keeps the validator passing."""
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    assert "diagnostics" not in payload


def test_empty_asset_yields_zero_coverage_for_industrial_crate() -> None:
    payload = evaluate_family_grammar({"intent": {"parts": []}}, _crate_runtime())

    assert payload["family"] == "industrial_crate"
    assert payload["coverage"] == 0.0
    assert payload["satisfied_count"] == 0
    assert payload["partial_count"] == 0
    assert payload["missing_count"] == 10


def test_full_coverage_when_every_requirement_is_satisfied() -> None:
    asset = {
        "intent": {
            "parts": [
                "body",
                "lid",
                "corner_guard_a",
                "latch_plate",
                "handle_l",
                "foot_l",
                "trim_band",
                "rivet_a",
                "warning_decal",
                "edge_wear_mask",
            ]
        }
    }
    payload = evaluate_family_grammar(asset, _crate_runtime())

    assert payload["coverage"] == 1.0
    assert payload["satisfied_count"] == 10
    assert payload["partial_count"] == 0
    assert payload["missing_count"] == 0
    assert payload["recommendations"] == []


def test_industrial_crate_baseline_parts_list_yields_coverage_zero_point_four() -> None:
    """The actual baseline ``examples/industrial_crate.lth`` parts list
    matches 4 of the 10 grammar requirements (body_shell, latch_or_latch_plate,
    recessed_or_bracketed_handles, foot_rails_or_feet) so coverage = 0.40."""
    asset = {
        "intent": {
            "parts": [
                "body",
                "latch_plate",
                "handle_l",
                "handle_r",
                "foot_l",
                "foot_r",
            ]
        }
    }
    payload = evaluate_family_grammar(asset, _crate_runtime())

    assert payload["satisfied_count"] == 4
    assert payload["missing_count"] == 6
    assert payload["coverage"] == 0.4

    statuses = {item["name"]: item["status"] for item in payload["requirement_results"]}
    assert statuses["body_shell"] == "satisfied"
    assert statuses["latch_or_latch_plate"] == "satisfied"
    assert statuses["recessed_or_bracketed_handles"] == "satisfied"
    assert statuses["foot_rails_or_feet"] == "satisfied"
    assert statuses["lid_seam"] == "missing"
    assert statuses["corner_guards"] == "missing"
    assert statuses["trim_bands"] == "missing"
    assert statuses["fasteners"] == "missing"
    assert statuses["warning_or_decal_zones"] == "missing"
    assert statuses["edge_wear_masks"] == "missing"


def test_recommendations_length_equals_missing_plus_partial_count() -> None:
    asset = {"intent": {"parts": ["body", "latch_plate", "handle_l"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    assert len(payload["recommendations"]) == (
        payload["missing_count"] + payload["partial_count"]
    )
    assert payload["satisfied_count"] == 3
    assert payload["missing_count"] == 7


def test_evidence_includes_matched_parts_for_satisfied_requirements() -> None:
    asset = {"intent": {"parts": ["body", "handle_l", "handle_r"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    handle_entry = next(
        item
        for item in payload["requirement_results"]
        if item["name"] == "recessed_or_bracketed_handles"
    )
    assert handle_entry["status"] == "satisfied"
    assert handle_entry["evidence"]["matched_parts"] == ["handle_l", "handle_r"]

    lid_entry = next(
        item for item in payload["requirement_results"] if item["name"] == "lid_seam"
    )
    assert lid_entry["status"] == "missing"
    assert lid_entry["evidence"]["matched_parts"] == []


def test_unknown_family_falls_back_to_generic_grammar() -> None:
    runtime = _runtime_with_family("unrecognized_family")
    payload = evaluate_family_grammar({"intent": {"parts": ["body"]}}, runtime)

    assert payload["family"] == "generic"
    assert payload["coverage"] == 1.0
    assert payload["requirement_results"] == []
    assert payload["recommendations"] == []
    assert payload["satisfied_count"] == 0
    assert payload["missing_count"] == 0


def test_missing_design_brief_falls_back_to_generic_gracefully() -> None:
    payload = evaluate_family_grammar({"intent": {"parts": ["body"]}}, {})

    assert payload["family"] == "generic"
    assert payload["coverage"] == 1.0
    assert payload["requirement_results"] == []
    assert payload["recommendations"] == []


def test_missing_intent_does_not_crash() -> None:
    payload = evaluate_family_grammar({}, _crate_runtime())

    assert payload["family"] == "industrial_crate"
    assert payload["satisfied_count"] == 0
    assert payload["missing_count"] == 10
    assert payload["coverage"] == 0.0


def test_missing_parts_list_does_not_crash() -> None:
    payload = evaluate_family_grammar({"intent": {}}, _crate_runtime())

    assert payload["family"] == "industrial_crate"
    assert payload["satisfied_count"] == 0
    assert payload["missing_count"] == 10


def test_part_matching_is_case_insensitive() -> None:
    asset = {"intent": {"parts": ["BODY", "Latch_Plate", "HANDLE_L", "FOOT_L"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    statuses = {item["name"]: item["status"] for item in payload["requirement_results"]}
    assert statuses["body_shell"] == "satisfied"
    assert statuses["latch_or_latch_plate"] == "satisfied"
    assert statuses["recessed_or_bracketed_handles"] == "satisfied"
    assert statuses["foot_rails_or_feet"] == "satisfied"


def test_evaluation_is_deterministic_across_runs() -> None:
    asset = {
        "intent": {
            "parts": [
                "body",
                "latch_plate",
                "handle_l",
                "handle_r",
                "foot_l",
                "foot_r",
            ]
        }
    }
    runtime = _crate_runtime()

    first = evaluate_family_grammar(asset, runtime)
    second = evaluate_family_grammar(asset, runtime)

    assert first == second


def test_recommendations_skip_satisfied_requirements() -> None:
    """Recommendations must reference only missing/partial requirements;
    satisfied requirements never produce a recommendation entry."""
    asset = {"intent": {"parts": ["body", "lid", "corner", "latch", "handle"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    satisfied_names = {
        item["name"]
        for item in payload["requirement_results"]
        if item["status"] == "satisfied"
    }
    for recommendation in payload["recommendations"]:
        for satisfied in satisfied_names:
            assert satisfied not in recommendation, (
                f"Recommendation should not reference satisfied requirement {satisfied!r}: {recommendation!r}"
            )


def test_recommendations_pair_to_unsatisfied_requirements_by_index() -> None:
    """``recommendations[i]`` must be the ``recommendation_template`` of the
    i-th unsatisfied requirement in declaration order. Catches a refactor
    that swaps recommendation strings between requirements — substring
    coupling alone (the previous test) would not detect that.
    """
    from lathe.asset_quality.family_grammar import (
        _GRAMMARS,
    )

    asset = {"intent": {"parts": ["body", "handle"]}}
    payload = evaluate_family_grammar(asset, _crate_runtime())

    unsatisfied_requirement_names = [
        result["name"]
        for result in payload["requirement_results"]
        if result["status"] in {"missing", "partial"}
    ]

    name_to_template = {
        req.name: req.recommendation_template
        for req in _GRAMMARS["industrial_crate"].requirements
    }

    assert len(payload["recommendations"]) == len(unsatisfied_requirement_names)
    for index, requirement_name in enumerate(unsatisfied_requirement_names):
        expected_template = name_to_template[requirement_name]
        assert payload["recommendations"][index] == expected_template, (
            f"recommendations[{index}] should be the template of "
            f"{requirement_name!r}; got mismatch."
        )


# --------------------------------------------------------------------------- #
# Phase 4 graph-elevation tests
# --------------------------------------------------------------------------- #


def _crate_runtime_with_construction_graph(
    nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a runtime that publishes both a Phase 2 design_brief and a
    Phase 4 construction_graph block, used to verify the additive
    graph-elevation path on top of the Phase 3 detector.
    """
    return {
        "design_brief": {"brief": {"family": "industrial_crate"}},
        "construction_graph": {"nodes": nodes},
    }


def test_graph_only_evidence_promotes_missing_to_partial() -> None:
    """When a requirement's parts-list signals don't match but a
    construction-graph node of the requirement's allowlisted node type
    is present, the status is elevated from ``"missing"`` to
    ``"partial"`` and ``evidence.matched_graph_nodes`` records the
    contributing node ids."""
    runtime = _crate_runtime_with_construction_graph(
        [
            {"node_id": "body", "node_type": "primary_volume"},
            {"node_id": "guard_corner_a", "node_type": "guard"},
        ]
    )
    asset = {"intent": {"parts": ["body"]}}

    payload = evaluate_family_grammar(asset, runtime)

    statuses = {item["name"]: item["status"] for item in payload["requirement_results"]}
    assert statuses["corner_guards"] == "partial"

    corner_entry = next(
        item
        for item in payload["requirement_results"]
        if item["name"] == "corner_guards"
    )
    assert corner_entry["evidence"]["matched_parts"] == []
    assert corner_entry["evidence"]["matched_graph_nodes"] == ["guard_corner_a"]
    assert payload["partial_count"] >= 1


def test_parts_match_dominates_graph_match_for_satisfied_status() -> None:
    """When both parts and graph match, the status is ``"satisfied"`` —
    parts evidence wins because parts represent explicit authoring
    intent. The ``matched_graph_nodes`` evidence key is omitted because
    the graph-elevation path was not taken."""
    runtime = _crate_runtime_with_construction_graph(
        [
            {"node_id": "body", "node_type": "primary_volume"},
            {"node_id": "guard_corner_a", "node_type": "guard"},
        ]
    )
    asset = {"intent": {"parts": ["body", "corner_guard_a"]}}

    payload = evaluate_family_grammar(asset, runtime)

    corner_entry = next(
        item
        for item in payload["requirement_results"]
        if item["name"] == "corner_guards"
    )
    assert corner_entry["status"] == "satisfied"
    assert corner_entry["evidence"]["matched_parts"] == ["corner_guard_a"]
    assert "matched_graph_nodes" not in corner_entry["evidence"]


def test_no_graph_evidence_falls_back_to_phase_3_behaviour() -> None:
    """When ``runtime["construction_graph"]`` is absent, the validator
    must produce the exact Phase 3 result (parts-only detection, no
    ``matched_graph_nodes`` keys, identical statuses and counts)."""
    asset = {
        "intent": {
            "parts": [
                "body",
                "latch_plate",
                "handle_l",
                "handle_r",
                "foot_l",
                "foot_r",
            ]
        }
    }
    runtime_phase_3 = {"design_brief": {"brief": {"family": "industrial_crate"}}}

    payload = evaluate_family_grammar(asset, runtime_phase_3)

    assert payload["satisfied_count"] == 4
    assert payload["partial_count"] == 0
    assert payload["missing_count"] == 6
    assert payload["coverage"] == 0.4
    for entry in payload["requirement_results"]:
        assert "matched_graph_nodes" not in entry["evidence"]


def test_industrial_crate_baseline_coverage_unchanged_with_graph() -> None:
    """The actual industrial_crate.lth baseline parts list, plus a
    construction_graph extracted from those same parts, must still yield
    coverage = 0.40. The graph adds the same node types (primary_volume,
    inset, handle, mount) the parts list already covers, so no
    requirement is elevated from ``"missing"`` to ``"partial"``."""
    parts = ["body", "latch_plate", "handle_l", "handle_r", "foot_l", "foot_r"]
    nodes = [
        {"node_id": "body", "node_type": "primary_volume"},
        {"node_id": "latch_plate", "node_type": "inset"},
        {"node_id": "handle_l", "node_type": "handle"},
        {"node_id": "handle_r", "node_type": "handle"},
        {"node_id": "foot_l", "node_type": "mount"},
        {"node_id": "foot_r", "node_type": "mount"},
    ]
    runtime = _crate_runtime_with_construction_graph(nodes)
    asset = {"intent": {"parts": parts}}

    payload = evaluate_family_grammar(asset, runtime)

    assert payload["satisfied_count"] == 4
    assert payload["partial_count"] == 0
    assert payload["missing_count"] == 6
    assert payload["coverage"] == 0.4
