"""Author-facing geometry detail controls for scaffold generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_LEVELS = {
    "off": 0.0,
    "none": 0.0,
    "low": 0.55,
    "light": 0.70,
    "standard": 1.0,
    "medium": 1.0,
    "game": 1.0,
    "high": 1.45,
    "dense": 1.65,
    "hero": 1.85,
    "ultra": 2.20,
}

_EDGE_TREATMENTS = {
    "soft": 0.75,
    "round": 0.85,
    "rounded": 0.85,
    "hard": 1.10,
    "crisp": 1.20,
    "chamfer": 1.35,
    "chamfered": 1.35,
    "bevel": 1.45,
    "beveled": 1.45,
    "guarded": 1.60,
}

_CONTROL_FIELDS = (
    "detail_density",
    "detail_motifs",
    "style_pack",
    "style_packs",
    "style_intensity",
    "silhouette_profile",
    "silhouette_motifs",
    "silhouette_intensity",
    "edge_complexity",
    "edge_treatment",
    "edge_hardness",
    "bevel_width",
    "chamfer_width",
    "panelization",
    "groove_density",
    "ridge_density",
    "greeble_density",
    "trim_density",
    "inset_depth",
    "outset_depth",
    "surface_layer_count",
    "modular_attachment_points",
    "module_sockets",
    "module_categories",
    "module_count",
    "attachment_motifs",
    "attachment_count",
    "linear_detail_repeats",
    "radial_detail_repeats",
    "detail_array_axis",
    "detail_zones",
    "style_modifiers",
    "lod_levels",
    "highlow_mode",
    "highlow_low_lod",
    "highlow_bake_cage_offset_cm",
    "collision_proxy",
    "export_profiles",
)

_STYLE_PACKS: dict[str, dict[str, Any]] = {
    "industrial_hero": {
        "style_modifiers": ("industrial", "brutalist", "modular"),
        "silhouette_profile": "wide_heavy",
        "silhouette_motifs": ("outrigger", "guard_cowl", "tower"),
        "detail_motifs": (
            "panel_seam",
            "groove_channel",
            "trim_strip",
            "bolt_grid",
            "socket_point",
            "linear_detail_array",
        ),
        "attachment_motifs": ("rail", "vent_stack", "guard_bar"),
        "module_categories": ("power_cell", "shield_plate", "antenna"),
        "detail_density": 1.65,
        "silhouette_intensity": 1.35,
        "edge_complexity": 1.35,
        "edge_treatment": "chamfered",
        "edge_hardness": "hard",
        "panelization": 1.35,
        "groove_density": 1.10,
        "trim_density": 1.25,
        "greeble_density": 1.20,
        "modular_attachment_points": 4,
        "attachment_count": 4,
        "module_count": 2,
        "linear_detail_repeats": 4,
        "surface_layer_count": 3,
        "surface": {
            "material_layers": ("painted_steel", "bare_metal", "rubber"),
            "wear_story": "field_used",
            "wear_level": "medium",
            "story_decals": ("service_number", "hazard_stripe", "edge_rub"),
        },
    },
    "sleek_sci_fi": {
        "style_modifiers": ("elegant", "prototype", "modular"),
        "silhouette_profile": "sleek_winged",
        "silhouette_motifs": ("wing", "spine", "sensor_mast"),
        "detail_motifs": (
            "raised_ridge",
            "layer_plate",
            "trim_strip",
            "radial_detail_array",
            "socket_point",
        ),
        "attachment_motifs": ("rail", "cable", "ornament"),
        "module_categories": ("sensor_pod", "wing", "antenna"),
        "detail_density": 1.35,
        "silhouette_intensity": 1.20,
        "edge_complexity": 1.05,
        "edge_treatment": "soft",
        "edge_hardness": "soft",
        "ridge_density": 1.15,
        "trim_density": 1.10,
        "surface_layer_count": 3,
        "module_count": 2,
        "radial_detail_repeats": 6,
        "surface": {
            "material_layers": ("ceramic_composite", "brushed_aluminum", "signal_glass"),
            "wear_story": "prototype",
            "wear_level": "light",
            "story_decals": ("calibration_id", "thin_color_bar"),
        },
    },
    "battle_worn_field": {
        "style_modifiers": ("battle_worn", "industrial", "modular"),
        "silhouette_profile": "reinforced_field",
        "silhouette_motifs": ("outrigger", "guard_cowl", "spine"),
        "detail_motifs": (
            "panel_seam",
            "groove_channel",
            "outset_panel",
            "bolt_grid",
            "trim_strip",
            "linear_detail_array",
        ),
        "attachment_motifs": ("strap", "cable", "rail", "guard_bar"),
        "module_categories": ("power_cell", "shield_plate", "leg"),
        "detail_density": 1.75,
        "silhouette_intensity": 1.45,
        "edge_complexity": 1.40,
        "edge_treatment": "guarded",
        "edge_hardness": "hard",
        "panelization": 1.35,
        "groove_density": 1.25,
        "outset_depth": 1.15,
        "trim_density": 1.10,
        "greeble_density": 1.30,
        "attachment_count": 5,
        "module_count": 2,
        "surface_layer_count": 3,
        "surface": {
            "material_layers": ("chipped_paint", "bare_metal", "grime"),
            "wear_story": "battle_worn",
            "wear_level": "heavy",
            "story_decals": ("scrape_cluster", "operator_label", "paint_chip_stripe"),
        },
    },
    "arcane_luxury": {
        "style_modifiers": ("luxury", "elegant", "organic"),
        "silhouette_profile": "ornate_spire",
        "silhouette_motifs": ("spire", "spine", "blade"),
        "detail_motifs": (
            "raised_ridge",
            "layer_plate",
            "trim_strip",
            "radial_detail_array",
            "ornament",
        ),
        "attachment_motifs": ("ornament", "strap", "cable"),
        "module_categories": ("blade", "sensor_pod", "antenna"),
        "detail_density": 1.45,
        "silhouette_intensity": 1.20,
        "edge_complexity": 0.95,
        "edge_treatment": "rounded",
        "edge_hardness": "soft",
        "ridge_density": 1.40,
        "trim_density": 1.25,
        "surface_layer_count": 4,
        "radial_detail_repeats": 8,
        "attachment_count": 4,
        "module_count": 2,
        "surface": {
            "material_layers": ("worn_brass", "dark_wood", "inset_glass"),
            "wear_story": "ancient",
            "wear_level": "medium",
            "story_decals": ("etched_runes", "edge_rub", "patina_marks"),
        },
    },
    "architectural_world": {
        "style_modifiers": ("architectural", "modular", "urban"),
        "silhouette_profile": "wide_heavy",
        "silhouette_motifs": ("tower", "spine"),
        "detail_motifs": (
            "arch_frame",
            "column_set",
            "stair_step",
            "structural_frame",
            "panel_seam",
            "trim_strip",
        ),
        "attachment_motifs": ("rail", "guard_bar"),
        "module_categories": ("shield_plate", "antenna"),
        "detail_density": 1.55,
        "silhouette_intensity": 1.25,
        "edge_complexity": 1.20,
        "edge_treatment": "chamfered",
        "panelization": 1.15,
        "trim_density": 1.10,
        "surface_layer_count": 3,
        "linear_detail_repeats": 3,
        "module_count": 2,
        "surface": {
            "material_layers": ("stone", "painted_metal", "glass"),
            "wear_story": "inhabited",
            "wear_level": "medium",
            "story_decals": ("wayfinding_mark", "painted_number", "edge_grime"),
        },
    },
    "vehicle_workshop": {
        "style_modifiers": ("vehicle", "industrial", "modular"),
        "silhouette_profile": "reinforced_field",
        "silhouette_motifs": ("outrigger", "guard_cowl"),
        "detail_motifs": (
            "wheel_pair",
            "hull_keel",
            "pipe_run",
            "structural_frame",
            "panel_seam",
            "raised_ridge",
        ),
        "attachment_motifs": ("rail", "cable", "strap"),
        "module_categories": ("power_cell", "barrel", "leg"),
        "detail_density": 1.60,
        "silhouette_intensity": 1.35,
        "edge_complexity": 1.30,
        "edge_treatment": "guarded",
        "ridge_density": 1.05,
        "trim_density": 1.10,
        "attachment_count": 4,
        "module_count": 3,
        "surface_layer_count": 3,
        "surface": {
            "material_layers": ("painted_steel", "rubber", "oil_dark_metal"),
            "wear_story": "worked_hard",
            "wear_level": "heavy",
            "story_decals": ("warning_label", "scrape_cluster", "service_stencil"),
        },
    },
}

_STYLE_PACK_LIST_FIELDS = {
    "style_modifiers",
    "detail_motifs",
    "silhouette_motifs",
    "attachment_motifs",
    "module_categories",
}

_STYLE_PACK_LEVEL_FIELDS = {
    "detail_density",
    "silhouette_intensity",
    "edge_complexity",
    "panelization",
    "groove_density",
    "ridge_density",
    "greeble_density",
    "trim_density",
    "inset_depth",
    "outset_depth",
}

_STYLE_PACK_COUNT_FIELDS = {
    "surface_layer_count",
    "modular_attachment_points",
    "attachment_count",
    "module_count",
    "linear_detail_repeats",
    "radial_detail_repeats",
}

_ZONE_PROPERTIES = (
    "attachment_motifs",
    "attachment_count",
    "modular_attachment_points",
    "module_categories",
    "module_count",
    "linear_detail_repeats",
    "radial_detail_repeats",
    "surface_layer_count",
    "detail_array_axis",
    "edge_complexity",
    "edge_treatment",
    "edge_hardness",
    "bevel_width",
    "chamfer_width",
    "groove_density",
    "ridge_density",
    "greeble_density",
    "trim_density",
    "inset_depth",
    "outset_depth",
    "panelization",
    "density",
    "motifs",
    "falloff",
)


@dataclass(frozen=True)
class DetailZoneSpec:
    """Per-zone controls for local geometry detail generation."""

    name: str
    density: float | None = None
    motifs: tuple[str, ...] = ()
    falloff: str = "uniform"
    edge_complexity: float | None = None
    edge_treatment: str | None = None
    edge_hardness: str | None = None
    bevel_width: float | None = None
    chamfer_width: float | None = None
    panelization: float | None = None
    groove_density: float | None = None
    ridge_density: float | None = None
    greeble_density: float | None = None
    trim_density: float | None = None
    inset_depth: float | None = None
    outset_depth: float | None = None
    surface_layer_count: int | None = None
    modular_attachment_points: int | None = None
    module_categories: tuple[str, ...] = ()
    module_count: int | None = None
    attachment_motifs: tuple[str, ...] = ()
    attachment_count: int | None = None
    linear_detail_repeats: int | None = None
    radial_detail_repeats: int | None = None
    detail_array_axis: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the zone spec for shape signatures and runtime reports."""
        payload: dict[str, Any] = {"name": self.name, "falloff": self.falloff}
        for key in (
            "density",
            "edge_complexity",
            "bevel_width",
            "chamfer_width",
            "panelization",
            "groove_density",
            "ridge_density",
            "greeble_density",
            "trim_density",
            "inset_depth",
            "outset_depth",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = round(float(value), 6)
        for key in (
            "surface_layer_count",
            "modular_attachment_points",
            "module_count",
            "attachment_count",
            "linear_detail_repeats",
            "radial_detail_repeats",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = int(value)
        for key in ("edge_treatment", "edge_hardness", "detail_array_axis"):
            value = getattr(self, key)
            if value:
                payload[key] = value
        if self.motifs:
            payload["motifs"] = list(self.motifs)
        if self.module_categories:
            payload["module_categories"] = list(self.module_categories)
        if self.attachment_motifs:
            payload["attachment_motifs"] = list(self.attachment_motifs)
        return payload


@dataclass(frozen=True)
class GeometryDetailControls:
    """Resolved user controls for additive scaffold detail generation."""

    detail_density: float = 1.0
    detail_motifs: tuple[str, ...] = ()
    style_packs: tuple[str, ...] = ()
    style_intensity: float = 1.0
    silhouette_profile: str = ""
    silhouette_motifs: tuple[str, ...] = ()
    silhouette_intensity: float = 1.0
    edge_complexity: float = 1.0
    edge_treatment: str = "standard"
    edge_hardness: str = "standard"
    bevel_width: float = 0.0
    chamfer_width: float = 0.0
    panelization: float = 0.0
    groove_density: float = 0.0
    ridge_density: float = 0.0
    greeble_density: float = 0.0
    trim_density: float = 0.0
    inset_depth: float = 0.0
    outset_depth: float = 0.0
    surface_layer_count: int = 0
    modular_attachment_points: int = 0
    module_sockets: tuple[str, ...] = ()
    module_categories: tuple[str, ...] = ()
    module_count: int = 0
    attachment_motifs: tuple[str, ...] = ()
    attachment_count: int = 0
    linear_detail_repeats: int = 0
    radial_detail_repeats: int = 0
    detail_array_axis: str = "x"
    detail_zones: tuple[str, ...] = ()
    style_modifiers: tuple[str, ...] = ()
    lod_levels: int = 0
    highlow_mode: str = ""
    highlow_low_lod: int = 0
    highlow_bake_cage_offset_cm: float = 0.0
    collision_proxy: str = ""
    export_profiles: tuple[str, ...] = ()
    zones: tuple[DetailZoneSpec, ...] = ()
    explicit_fields: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        """Return True when an author explicitly requested geometry detail."""
        return bool(self.explicit_fields) and (
            self.detail_density > 0.0
            or bool(self.detail_motifs)
            or bool(self.style_packs)
            or bool(self.silhouette_profile)
            or bool(self.silhouette_motifs)
            or self.edge_complexity > 0.0
            or self.panelization > 0.0
            or self.groove_density > 0.0
            or self.ridge_density > 0.0
            or self.greeble_density > 0.0
            or self.trim_density > 0.0
            or self.inset_depth > 0.0
            or self.outset_depth > 0.0
            or self.surface_layer_count > 0
            or self.modular_attachment_points > 0
            or bool(self.module_sockets)
            or bool(self.module_categories)
            or self.module_count > 0
            or bool(self.attachment_motifs)
            or self.attachment_count > 0
            or self.linear_detail_repeats > 0
            or self.radial_detail_repeats > 0
            or bool(self.style_modifiers)
            or bool(self.highlow_mode)
            or bool(self.zones)
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize controls into JSON-friendly runtime metadata."""
        return {
            "detail_density": round(self.detail_density, 6),
            "detail_motifs": list(self.detail_motifs),
            "style_packs": list(self.style_packs),
            "style_intensity": round(self.style_intensity, 6),
            "silhouette_profile": self.silhouette_profile,
            "silhouette_motifs": list(self.silhouette_motifs),
            "silhouette_intensity": round(self.silhouette_intensity, 6),
            "edge_complexity": round(self.edge_complexity, 6),
            "edge_treatment": self.edge_treatment,
            "edge_hardness": self.edge_hardness,
            "bevel_width": round(self.bevel_width, 6),
            "chamfer_width": round(self.chamfer_width, 6),
            "panelization": round(self.panelization, 6),
            "groove_density": round(self.groove_density, 6),
            "ridge_density": round(self.ridge_density, 6),
            "greeble_density": round(self.greeble_density, 6),
            "trim_density": round(self.trim_density, 6),
            "inset_depth": round(self.inset_depth, 6),
            "outset_depth": round(self.outset_depth, 6),
            "surface_layer_count": int(self.surface_layer_count),
            "modular_attachment_points": int(self.modular_attachment_points),
            "module_sockets": list(self.module_sockets),
            "module_categories": list(self.module_categories),
            "module_count": int(self.module_count),
            "attachment_motifs": list(self.attachment_motifs),
            "attachment_count": int(self.attachment_count),
            "linear_detail_repeats": int(self.linear_detail_repeats),
            "radial_detail_repeats": int(self.radial_detail_repeats),
            "detail_array_axis": self.detail_array_axis,
            "detail_zones": list(self.detail_zones),
            "style_modifiers": list(self.style_modifiers),
            "lod_levels": int(self.lod_levels),
            "highlow_mode": self.highlow_mode,
            "highlow_low_lod": int(self.highlow_low_lod),
            "highlow_bake_cage_offset_cm": round(self.highlow_bake_cage_offset_cm, 6),
            "collision_proxy": self.collision_proxy,
            "export_profiles": list(self.export_profiles),
            "zones": [zone.to_dict() for zone in self.zones],
            "explicit_fields": list(self.explicit_fields),
        }


def geometry_detail_controls_from_authoring(authoring: dict[str, Any]) -> GeometryDetailControls:
    """Resolve additive geometry controls from an AssetGraph authoring payload."""
    shape_controls = authoring.get("shape_controls", {})
    if not isinstance(shape_controls, dict):
        shape_controls = {}
    experimental = authoring.get("experimental", {})
    art_direction = experimental.get("art_direction", {}) if isinstance(experimental, dict) else {}
    if not isinstance(art_direction, dict):
        art_direction = {}

    explicit_fields = [field for field in _CONTROL_FIELDS if field in shape_controls]
    explicit_fields.extend(sorted(str(key) for key in shape_controls if str(key).startswith("zone_")))
    detail_density_source = shape_controls.get("detail_density")
    if detail_density_source is None and "detail_density" in art_direction:
        detail_density_source = art_direction.get("detail_density")
        explicit_fields.append("experimental.art_direction.detail_density")
    style_modifiers_source = shape_controls.get("style_modifiers")
    if style_modifiers_source is None and "style_tags" in art_direction:
        style_modifiers_source = art_direction.get("style_tags")
        explicit_fields.append("experimental.art_direction.style_tags")
    style_pack_source = shape_controls.get("style_pack", shape_controls.get("style_packs"))
    if style_pack_source is None and "style_pack" in art_direction:
        style_pack_source = art_direction.get("style_pack")
        explicit_fields.append("experimental.art_direction.style_pack")
    style_packs = _tokens(style_pack_source)
    style_intensity = _level(shape_controls.get("style_intensity"), 1.0)
    pack_defaults = _style_pack_defaults(style_packs, style_intensity)
    if style_packs:
        explicit_fields.extend([f"style_pack.{pack}" for pack in style_packs])

    edge_treatment = _token(_control_value(shape_controls, pack_defaults, "edge_treatment"), "standard")
    edge_complexity = _level(_control_value(shape_controls, pack_defaults, "edge_complexity"), 1.0)
    edge_complexity *= _EDGE_TREATMENTS.get(edge_treatment, 1.0)

    return GeometryDetailControls(
        detail_density=_level(
            detail_density_source if detail_density_source is not None else pack_defaults.get("detail_density"),
            1.0,
        ),
        detail_motifs=_merge_tokens(pack_defaults.get("detail_motifs"), shape_controls.get("detail_motifs")),
        style_packs=style_packs,
        style_intensity=style_intensity,
        silhouette_profile=_token(
            _control_value(shape_controls, pack_defaults, "silhouette_profile"), ""
        ),
        silhouette_motifs=_merge_tokens(
            pack_defaults.get("silhouette_motifs"), shape_controls.get("silhouette_motifs")
        ),
        silhouette_intensity=_level(
            _control_value(shape_controls, pack_defaults, "silhouette_intensity"), 1.0
        ),
        edge_complexity=edge_complexity,
        edge_treatment=edge_treatment,
        edge_hardness=_token(_control_value(shape_controls, pack_defaults, "edge_hardness"), "standard"),
        bevel_width=_level(shape_controls.get("bevel_width"), 0.0),
        chamfer_width=_level(shape_controls.get("chamfer_width"), 0.0),
        panelization=_level(_control_value(shape_controls, pack_defaults, "panelization"), 0.0),
        groove_density=_level(_control_value(shape_controls, pack_defaults, "groove_density"), 0.0),
        ridge_density=_level(_control_value(shape_controls, pack_defaults, "ridge_density"), 0.0),
        greeble_density=_level(_control_value(shape_controls, pack_defaults, "greeble_density"), 0.0),
        trim_density=_level(_control_value(shape_controls, pack_defaults, "trim_density"), 0.0),
        inset_depth=_level(_control_value(shape_controls, pack_defaults, "inset_depth"), 0.0),
        outset_depth=_level(_control_value(shape_controls, pack_defaults, "outset_depth"), 0.0),
        surface_layer_count=_count(_control_value(shape_controls, pack_defaults, "surface_layer_count"), 0),
        modular_attachment_points=_count(
            _control_value(shape_controls, pack_defaults, "modular_attachment_points"), 0
        ),
        module_sockets=_tokens(shape_controls.get("module_sockets")),
        module_categories=_merge_tokens(pack_defaults.get("module_categories"), shape_controls.get("module_categories")),
        module_count=_count(_control_value(shape_controls, pack_defaults, "module_count"), 0),
        attachment_motifs=_merge_tokens(
            pack_defaults.get("attachment_motifs"), shape_controls.get("attachment_motifs")
        ),
        attachment_count=_count(_control_value(shape_controls, pack_defaults, "attachment_count"), 0),
        linear_detail_repeats=_count(
            _control_value(shape_controls, pack_defaults, "linear_detail_repeats"), 0
        ),
        radial_detail_repeats=_count(
            _control_value(shape_controls, pack_defaults, "radial_detail_repeats"), 0
        ),
        detail_array_axis=_token(shape_controls.get("detail_array_axis"), "x"),
        detail_zones=_zones(shape_controls.get("detail_zones")),
        style_modifiers=_merge_tokens(pack_defaults.get("style_modifiers"), style_modifiers_source),
        lod_levels=_count(shape_controls.get("lod_levels"), 0),
        highlow_mode=_token(shape_controls.get("highlow_mode"), ""),
        highlow_low_lod=_count(shape_controls.get("highlow_low_lod"), 0),
        highlow_bake_cage_offset_cm=_level(shape_controls.get("highlow_bake_cage_offset_cm"), 0.0),
        collision_proxy=_token(shape_controls.get("collision_proxy"), ""),
        export_profiles=_tokens(shape_controls.get("export_profiles")),
        zones=_zone_specs(shape_controls),
        explicit_fields=tuple(dict.fromkeys(explicit_fields)),
    )


def style_pack_surface_defaults(style_packs: Any, style_intensity: Any = None) -> dict[str, Any]:
    """Return surface defaults implied by style packs without mutating author data."""
    packs = _tokens(style_packs)
    intensity = _level(style_intensity, 1.0)
    defaults = _style_pack_defaults(packs, intensity)
    surface = defaults.get("surface")
    return dict(surface) if isinstance(surface, dict) else {}


def _control_value(shape_controls: dict[str, Any], pack_defaults: dict[str, Any], field: str) -> Any:
    return shape_controls[field] if field in shape_controls else pack_defaults.get(field)


def _style_pack_defaults(style_packs: tuple[str, ...], style_intensity: float) -> dict[str, Any]:
    if not style_packs:
        return {}
    merged: dict[str, Any] = {}
    surface: dict[str, Any] = {}
    for style_pack in style_packs:
        pack = _STYLE_PACKS.get(style_pack)
        if not pack:
            continue
        for field, value in pack.items():
            if field == "surface" and isinstance(value, dict):
                _merge_surface_defaults(surface, value)
            elif field in _STYLE_PACK_LIST_FIELDS:
                merged[field] = _merge_tokens(merged.get(field), value)
            elif field in _STYLE_PACK_LEVEL_FIELDS:
                merged[field] = max(float(merged.get(field, 0.0)), float(value) * style_intensity)
            elif field in _STYLE_PACK_COUNT_FIELDS:
                scaled = max(0, int(round(float(value) * style_intensity)))
                merged[field] = max(int(merged.get(field, 0)), scaled)
            else:
                merged.setdefault(field, value)
    if surface:
        merged["surface"] = surface
    return merged


def _merge_surface_defaults(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key in {"material_layers", "story_decals", "faction_marks", "markings"}:
            target[key] = list(_merge_tokens(target.get(key), value))
        else:
            target.setdefault(key, value)


def _level(value: Any, default: float) -> float:
    if value is None:
        return float(default)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    if isinstance(value, str):
        lowered = value.lower().replace("-", "_").strip()
        if lowered in _LEVELS:
            return _LEVELS[lowered]
        try:
            return max(0.0, float(lowered))
        except ValueError:
            return float(default)
    return float(default)


def _count(value: Any, default: int) -> int:
    if value is None:
        return int(default)
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(round(value)))
    if isinstance(value, str):
        lowered = value.lower().replace("-", "_").strip()
        if lowered in _LEVELS:
            return max(0, int(round(_LEVELS[lowered] * 2.0)))
        try:
            return max(0, int(round(float(lowered))))
        except ValueError:
            return int(default)
    return int(default)


def _token(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).lower().replace("-", "_").replace(" ", "_").strip()
    return text or default


def _tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    raw_values = sorted(value) if isinstance(value, set) else value if isinstance(value, (list, tuple)) else [value]
    tokens: list[str] = []
    for item in raw_values:
        token = _token(item)
        if token:
            tokens.append(token)
    return tuple(dict.fromkeys(tokens))


def _merge_tokens(*values: Any) -> tuple[str, ...]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(_tokens(value))
    return tuple(dict.fromkeys(tokens))


def _zones(value: Any) -> tuple[str, ...]:
    return _tokens(value)


def _zone_specs(shape_controls: dict[str, Any]) -> tuple[DetailZoneSpec, ...]:
    raw_specs: dict[str, dict[str, Any]] = {}
    for raw_key, raw_value in shape_controls.items():
        key = _token(raw_key)
        if not key.startswith("zone_"):
            continue
        body = key.removeprefix("zone_")
        for prop in _ZONE_PROPERTIES:
            suffix = f"_{prop}"
            if not body.endswith(suffix):
                continue
            zone_name = body[: -len(suffix)]
            if zone_name:
                raw_specs.setdefault(zone_name, {})[prop] = raw_value
            break

    specs: list[DetailZoneSpec] = []
    for zone_name, values in raw_specs.items():
        specs.append(
            DetailZoneSpec(
                name=zone_name,
                density=_optional_level(values.get("density")),
                motifs=_tokens(values.get("motifs")),
                falloff=_token(values.get("falloff"), "uniform"),
                edge_complexity=_optional_level(values.get("edge_complexity")),
                edge_treatment=_optional_token(values.get("edge_treatment")),
                edge_hardness=_optional_token(values.get("edge_hardness")),
                bevel_width=_optional_level(values.get("bevel_width")),
                chamfer_width=_optional_level(values.get("chamfer_width")),
                panelization=_optional_level(values.get("panelization")),
                groove_density=_optional_level(values.get("groove_density")),
                ridge_density=_optional_level(values.get("ridge_density")),
                greeble_density=_optional_level(values.get("greeble_density")),
                trim_density=_optional_level(values.get("trim_density")),
                inset_depth=_optional_level(values.get("inset_depth")),
                outset_depth=_optional_level(values.get("outset_depth")),
                surface_layer_count=_optional_count(values.get("surface_layer_count")),
                modular_attachment_points=_optional_count(values.get("modular_attachment_points")),
                module_categories=_tokens(values.get("module_categories")),
                module_count=_optional_count(values.get("module_count")),
                attachment_motifs=_tokens(values.get("attachment_motifs")),
                attachment_count=_optional_count(values.get("attachment_count")),
                linear_detail_repeats=_optional_count(values.get("linear_detail_repeats")),
                radial_detail_repeats=_optional_count(values.get("radial_detail_repeats")),
                detail_array_axis=_optional_token(values.get("detail_array_axis")),
            )
        )
    return tuple(specs)


def _optional_level(value: Any) -> float | None:
    return None if value is None else _level(value, 0.0)


def _optional_count(value: Any) -> int | None:
    return None if value is None else _count(value, 0)


def _optional_token(value: Any) -> str | None:
    token = _token(value)
    return token or None
