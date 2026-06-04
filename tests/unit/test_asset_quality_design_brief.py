"""Phase 2 tests for ``lathe.asset_quality.design_brief``.

Covers per task #2.3 of ``docs/asset-quality/improvement-tasklist.md``:

- ``DesignBrief`` dataclass creation and ``to_dict`` round-trip;
- family inference for the supported families
  (industrial_crate, mechanical_door, service_cabinet, weapon_prop,
  vehicle_prop, furniture_prop, natural_form, environment_architecture,
  lighting_prop, machine_console, portal_relic, tool_prop, generic);
- inference signals (name vs role vs kind);
- per-family default brief contents;
- payload shape (``version`` / ``brief`` / ``family_inference``);
- robustness to missing ``intent``, missing ``name``, empty asset;
- absence of a ``diagnostics`` field so the FunctionValidator wrapper
  treats the validator as passing.
"""

from __future__ import annotations

from typing import Any

from lathe.asset_quality.design_brief import (
    VERSION,
    DesignBrief,
    evaluate_design_brief,
)

_EXPECTED_BRIEF_FIELDS: frozenset[str] = frozenset(
    {
        "asset_name",
        "family",
        "role",
        "style_tags",
        "silhouette",
        "bevel_language",
        "shape_language",
        "detail_density",
        "wear",
        "material_age",
        "greeble_style",
        "negative_constraints",
    }
)


def _evaluate(asset: dict[str, Any]) -> dict[str, Any]:
    """Helper: run ``evaluate_design_brief`` with an empty runtime."""
    return evaluate_design_brief(asset, {})


def test_dataclass_round_trip_via_to_dict() -> None:
    brief = DesignBrief(
        asset_name="example_asset",
        family="industrial_crate",
        role="reinforced industrial cargo crate",
        style_tags=("utility", "industrial"),
        silhouette="bold",
        bevel_language="chunky_industrial",
        shape_language="rectangular_with_45deg_cuts",
        detail_density="hero",
        wear="medium_edge_wear",
        material_age="used_not_destroyed",
        greeble_style="functional_only",
        negative_constraints=("toy_like", "ornate"),
    )
    payload = brief.to_dict()

    assert set(payload.keys()) == _EXPECTED_BRIEF_FIELDS
    assert payload["asset_name"] == "example_asset"
    assert payload["family"] == "industrial_crate"
    assert payload["style_tags"] == ["utility", "industrial"]
    assert payload["negative_constraints"] == ["toy_like", "ornate"]
    assert isinstance(payload["style_tags"], list)
    assert isinstance(payload["negative_constraints"], list)


def test_payload_shape_and_version() -> None:
    asset = {"name": "industrial_crate", "intent": {"role": "cargo"}}
    payload = _evaluate(asset)

    assert payload["version"] == VERSION
    assert VERSION == "design_brief_v1"
    # Phase 13 added an additive ``user_provided_via_experimental`` key.
    # The Phase 2 baseline keys must remain a subset of the payload.
    assert {"version", "brief", "family_inference"}.issubset(payload.keys())
    assert isinstance(payload["brief"], dict)
    assert set(payload["brief"].keys()) == _EXPECTED_BRIEF_FIELDS
    assert set(payload["family_inference"].keys()) == {
        "matched_family",
        "match_signal",
        "match_token",
    }


def test_no_diagnostics_field_so_validator_pipeline_treats_as_passing() -> None:
    """Mirrors Phase 1's contract — ``FunctionValidator`` only flips
    ``passes`` to ``False`` when a diagnostics entry has ``severity == 'error'``.
    Returning no ``diagnostics`` field at all keeps the validator passing."""
    payload = _evaluate({"name": "industrial_crate"})

    assert "diagnostics" not in payload


def test_industrial_crate_inferred_from_asset_name() -> None:
    payload = _evaluate({"name": "industrial_crate"})

    assert payload["family_inference"] == {
        "matched_family": "industrial_crate",
        "match_signal": "name",
        "match_token": "crate",
    }
    assert payload["brief"]["family"] == "industrial_crate"
    assert payload["brief"]["role"] == "reinforced industrial cargo crate"


def test_mechanical_door_inferred_from_asset_name_case_insensitively() -> None:
    payload = _evaluate({"name": "Cargo_DOOR_v2"})

    assert payload["family_inference"]["matched_family"] == "mechanical_door"
    assert payload["family_inference"]["match_signal"] == "name"
    assert payload["family_inference"]["match_token"] == "door"
    assert payload["brief"]["bevel_language"] == "crisp_industrial"


def test_service_cabinet_inferred_from_role_when_name_does_not_match() -> None:
    payload = _evaluate(
        {"name": "asset_42", "intent": {"role": "wall service cabinet"}}
    )

    assert payload["family_inference"] == {
        "matched_family": "service_cabinet",
        "match_signal": "role",
        "match_token": "cabinet",
    }
    assert payload["brief"]["family"] == "service_cabinet"


def test_weapon_prop_inferred_from_weapon_name() -> None:
    payload = _evaluate({"name": "astral_sentinel_weapon"})

    assert payload["family_inference"] == {
        "matched_family": "weapon_prop",
        "match_signal": "name",
        "match_token": "weapon",
    }
    assert payload["brief"]["family"] == "weapon_prop"
    assert payload["brief"]["shape_language"] == "linear_body_with_grip_guard_and_barrel_or_blade"


def test_vehicle_prop_inferred_from_boat_role() -> None:
    payload = _evaluate({"name": "asset_42", "intent": {"role": "cargo boat"}})

    assert payload["family_inference"] == {
        "matched_family": "vehicle_prop",
        "match_signal": "role",
        "match_token": "boat",
    }
    assert payload["brief"]["family"] == "vehicle_prop"


def test_furniture_prop_inferred_from_table_name() -> None:
    payload = _evaluate({"name": "market_table"})

    assert payload["family_inference"] == {
        "matched_family": "furniture_prop",
        "match_signal": "name",
        "match_token": "table",
    }
    assert payload["brief"]["family"] == "furniture_prop"


def test_natural_form_inferred_from_terrain_role() -> None:
    payload = _evaluate({"name": "asset_42", "intent": {"role": "terrain rock cluster"}})

    assert payload["family_inference"] == {
        "matched_family": "natural_form",
        "match_signal": "role",
        "match_token": "terrain",
    }
    assert payload["brief"]["family"] == "natural_form"


def test_environment_architecture_inferred_from_building_name() -> None:
    payload = _evaluate({"name": "market_building"})

    assert payload["family_inference"] == {
        "matched_family": "environment_architecture",
        "match_signal": "name",
        "match_token": "building",
    }
    assert payload["brief"]["family"] == "environment_architecture"


def test_lighting_prop_inferred_from_lantern_name() -> None:
    payload = _evaluate({"name": "dock_lantern"})

    assert payload["family_inference"] == {
        "matched_family": "lighting_prop",
        "match_signal": "name",
        "match_token": "lantern",
    }
    assert payload["brief"]["family"] == "lighting_prop"


def test_machine_console_inferred_from_terminal_role() -> None:
    payload = _evaluate({"name": "asset_42", "intent": {"role": "terminal console"}})

    assert payload["family_inference"] == {
        "matched_family": "machine_console",
        "match_signal": "role",
        "match_token": "console",
    }
    assert payload["brief"]["family"] == "machine_console"


def test_portal_relic_inferred_from_shrine_name() -> None:
    payload = _evaluate({"name": "ancient_shrine_portal"})

    assert payload["family_inference"] == {
        "matched_family": "portal_relic",
        "match_signal": "name",
        "match_token": "portal",
    }
    assert payload["brief"]["family"] == "portal_relic"


def test_tool_prop_inferred_from_scanner_kind() -> None:
    payload = _evaluate(
        {"name": "asset_42", "intent": {"role": "utility"}, "kind": "hand_scanner"}
    )

    assert payload["family_inference"] == {
        "matched_family": "tool_prop",
        "match_signal": "kind",
        "match_token": "scanner",
    }
    assert payload["brief"]["family"] == "tool_prop"


def test_kind_field_used_when_name_and_role_do_not_match() -> None:
    payload = _evaluate(
        {"name": "asset_42", "intent": {"role": "utility"}, "kind": "storage_crate"}
    )

    assert payload["family_inference"] == {
        "matched_family": "industrial_crate",
        "match_signal": "kind",
        "match_token": "crate",
    }


def test_token_priority_door_wins_over_cabinet_in_ambiguous_name() -> None:
    """``_FAMILY_TOKENS`` order is load-bearing: tokens are checked in
    declared order so an ambiguous name like ``cabinet_door`` resolves
    to the family of the first matching token (``door``), not the last.
    Phase 3+ may rely on this ordering when authoring family grammars.
    """
    payload = _evaluate({"name": "cabinet_door"})

    assert payload["family_inference"] == {
        "matched_family": "mechanical_door",
        "match_signal": "name",
        "match_token": "door",
    }


def test_role_path_is_case_insensitive() -> None:
    """The role-signal path must match case-insensitively, just like the
    name path. Pinning this so a future edit cannot regress role lookup
    to case-sensitive matching."""
    payload = _evaluate(
        {"name": "asset_42", "intent": {"role": "WALL CABINET"}}
    )

    assert payload["family_inference"] == {
        "matched_family": "service_cabinet",
        "match_signal": "role",
        "match_token": "cabinet",
    }


def test_generic_fallback_when_nothing_matches() -> None:
    payload = _evaluate({"name": "abstract_widget", "intent": {"role": "tool"}})

    assert payload["family_inference"] == {
        "matched_family": "generic",
        "match_signal": "default",
        "match_token": "",
    }
    assert payload["brief"]["family"] == "generic"
    assert payload["brief"]["role"] == "hard-surface utility asset"


def test_each_family_default_brief_has_all_twelve_fields() -> None:
    """Per spec Section 7.4: existing assets must get a deterministic
    *complete* default brief — every family must populate all 12 fields."""
    cases = [
        ({"name": "industrial_crate"}, "industrial_crate"),
        ({"name": "mechanical_door"}, "mechanical_door"),
        ({"name": "service_cabinet"}, "service_cabinet"),
        ({"name": "hero_weapon"}, "weapon_prop"),
        ({"name": "cargo_vehicle"}, "vehicle_prop"),
        ({"name": "workbench"}, "furniture_prop"),
        ({"name": "terrain_rock"}, "natural_form"),
        ({"name": "tower_room"}, "environment_architecture"),
        ({"name": "dock_lantern"}, "lighting_prop"),
        ({"name": "power_generator"}, "machine_console"),
        ({"name": "ancient_relic"}, "portal_relic"),
        ({"name": "repair_tool"}, "tool_prop"),
        ({"name": "abstract_widget"}, "generic"),
    ]
    for asset, expected_family in cases:
        payload = _evaluate(asset)
        brief = payload["brief"]

        assert payload["family_inference"]["matched_family"] == expected_family
        assert set(brief.keys()) == _EXPECTED_BRIEF_FIELDS
        for field, value in brief.items():
            assert value not in (None, "", [], ()), (
                f"family={expected_family} field={field} default is empty"
            )
        assert isinstance(brief["style_tags"], list)
        assert isinstance(brief["negative_constraints"], list)
        assert "toy_like" in brief["negative_constraints"]


def test_industrial_crate_default_matches_spec_section_7_3() -> None:
    """Anchor industrial_crate values to Section 7.3 of the upgrade spec
    so a casual edit cannot drift the canonical brief."""
    payload = _evaluate({"name": "industrial_crate"})
    brief = payload["brief"]

    assert brief["asset_name"] == "industrial_crate"
    assert brief["family"] == "industrial_crate"
    assert brief["role"] == "reinforced industrial cargo crate"
    assert brief["style_tags"] == ["utility", "industrial", "shipping"]
    assert brief["silhouette"] == "bold"
    assert brief["bevel_language"] == "chunky_industrial"
    assert brief["shape_language"] == "rectangular_with_45deg_cuts"
    assert brief["detail_density"] == "hero"
    assert brief["wear"] == "medium_edge_wear"
    assert brief["material_age"] == "used_not_destroyed"
    assert brief["greeble_style"] == "functional_only"
    assert brief["negative_constraints"] == ["toy_like", "random_faceting", "ornate"]


def test_missing_intent_does_not_crash() -> None:
    payload = _evaluate({"name": "industrial_crate"})

    assert payload["brief"]["family"] == "industrial_crate"
    assert payload["brief"]["asset_name"] == "industrial_crate"


def test_missing_name_falls_back_to_unnamed_asset() -> None:
    payload = _evaluate({"intent": {"role": "utility"}})

    assert payload["brief"]["asset_name"] == "unnamed_asset"
    assert payload["family_inference"]["matched_family"] == "generic"


def test_empty_asset_uses_generic_defaults() -> None:
    payload = evaluate_design_brief({}, {})

    assert payload["version"] == VERSION
    assert payload["family_inference"]["matched_family"] == "generic"
    assert set(payload["brief"].keys()) == _EXPECTED_BRIEF_FIELDS
    assert payload["brief"]["asset_name"] == "unnamed_asset"


def test_evaluation_is_deterministic_across_runs() -> None:
    asset = {"name": "industrial_crate", "intent": {"role": "cargo"}}

    first = _evaluate(asset)
    second = _evaluate(asset)

    assert first == second
