"""Unit tests for ``lathe.materials``.

The materials module is the deterministic palette + zone resolver used
by the V1.2 surface stage: ``palette_for_material`` returns a PBR
descriptor for a string name, ``assign_material_zones`` projects an
asset's parts to those descriptors and lets surface programs / palettes
/ component bindings override the defaults.
"""

from __future__ import annotations

from typing import Any

from lathe.materials import assign_material_zones, palette_for_material


def _payload_keys() -> set[str]:
    return {
        "basecolor",
        "metallic",
        "roughness",
        "roughness_range",
        "emissive",
        "surface_profile",
        "wear",
        "normal_intensity",
    }


class TestPaletteForMaterial:
    def test_known_wood_returns_wood_grain_profile(self) -> None:
        payload = palette_for_material("oak")
        assert payload["surface_profile"] == "wood_grain"
        assert _payload_keys() <= set(payload)

    def test_known_brass_is_metallic(self) -> None:
        payload = palette_for_material("worn_brass")
        assert payload["metallic"] == 1.0
        assert payload["surface_profile"] == "worn_brass"

    def test_unknown_material_falls_back_to_neutral(self) -> None:
        payload = palette_for_material("totally_unknown_material_xyz")
        assert payload["surface_profile"] == "neutral_panel"
        assert _payload_keys() <= set(payload)

    def test_glass_has_emissive_component(self) -> None:
        payload = palette_for_material("display_glass")
        assert payload["surface_profile"] == "screen_glass"
        assert sum(payload["emissive"]) > 0

    def test_palette_payload_is_serializable(self) -> None:
        import json

        payload = palette_for_material("aluminum")
        serialized = json.dumps(payload)
        round_trip = json.loads(serialized)
        assert round_trip["surface_profile"] == "brushed_metal"
        assert round_trip["metallic"] == 1.0


def _asset(materials: list[str], parts: list[str], **overrides: Any) -> dict[str, Any]:
    asset: dict[str, Any] = {
        "intent": {"materials": list(materials), "parts": list(parts)},
        "surface": {"materials": list(materials)},
        "assembly": {"resolved_components": []},
    }
    if overrides:
        for key, value in overrides.items():
            asset[key] = value
    return asset


class TestAssignMaterialZones:
    def test_simple_assignment_uses_primary_material(self) -> None:
        asset = _asset(["aluminum"], ["body"])
        zones = assign_material_zones(asset, ["body"])
        assert len(zones) == 1
        assert zones[0]["part"] == "body"
        assert zones[0]["material"] == "aluminum"
        assert _payload_keys() <= set(zones[0])

    def test_secondary_material_used_for_handle_like_parts(self) -> None:
        asset = _asset(["aluminum", "brass"], ["body", "handle"])
        zones = assign_material_zones(asset, ["body", "handle"])
        zones_by_part = {z["part"]: z for z in zones}
        # handle should pick up the secondary brass
        assert zones_by_part["handle"]["material"] == "brass"

    def test_zone_override_takes_precedence(self) -> None:
        asset = _asset(["aluminum", "brass"], ["body", "panel"])
        asset["surface"]["zones"] = {"body": "oak"}
        zones = assign_material_zones(asset, ["body", "panel"])
        zones_by_part = {z["part"]: z for z in zones}
        assert zones_by_part["body"]["material"] == "oak"
        assert zones_by_part["body"]["surface_profile"] == "wood_grain"

    def test_component_material_survives_broad_substring_zone_override(self) -> None:
        asset = _asset(["painted_steel_body", "smoked_glass_screen"], ["screen_panel"])
        asset["surface"]["zones"] = {"panel": "painted_steel_body", "screen": "smoked_glass_screen"}
        asset["assembly"]["resolved_components"] = [
            {"values": {"part": "screen_panel", "material_zone": "smoked_glass_screen"}}
        ]

        zones = assign_material_zones(asset, ["screen_panel"])

        assert zones[0]["material"] == "smoked_glass_screen"
        assert zones[0]["surface_profile"] == "screen_glass"

    def test_empty_materials_falls_back_to_default_body(self) -> None:
        asset = _asset([], ["body"])
        zones = assign_material_zones(asset, ["body"])
        assert zones[0]["material"] == "default_body"
        assert zones[0]["surface_profile"] == "neutral_panel"

    def test_palette_resolved_palette_extends_materials(self) -> None:
        asset = _asset(["aluminum"], ["body", "frame"])
        asset["surface"]["resolved_palette"] = {"values": {"materials": ["brass"]}}
        zones = assign_material_zones(asset, ["body", "frame"])
        # palette materials extend the surface materials list; "frame"
        # is in the secondary-token set so it picks up the second entry.
        zones_by_part = {z["part"]: z for z in zones}
        assert zones_by_part["frame"]["material"] == "brass"
