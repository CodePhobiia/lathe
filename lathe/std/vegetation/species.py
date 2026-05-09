"""VegetationSpecies + canonical species presets.

A ``VegetationSpecies`` carries every parameter needed to regenerate a
species deterministically: branch-grammar knobs, leaf-grammar knobs,
silhouette extents, palette/season hooks, and an LOD policy.

Three foundation species ship fully realized (oak, pine, grass_temperate);
seven additional placeholders inherit from a base preset with a one-line
override, giving authors a working catalog out of the gate while
deferring fine-tuning to follow-up work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VegetationSpecies:
    """A compiled vegetation species record.

    ``branch_grammar`` and ``leaf_grammar`` are kwargs blobs forwarded
    verbatim into ``branches.generate_branch_skeleton`` and
    ``leaves.scatter_leaf_cards`` respectively, so every parameter is
    one introspection step away.
    """

    name: str
    base_preset: str = ""
    silhouette_extents_cm: tuple[float, float, float] = (200.0, 600.0, 200.0)
    branch_grammar: dict[str, Any] = field(default_factory=dict)
    leaf_grammar: dict[str, Any] = field(default_factory=dict)
    frond_grammar: dict[str, Any] | None = None
    trunk_profile: list[tuple[float, float]] = field(default_factory=list)
    palette_summer: list[tuple[int, int, int]] = field(default_factory=list)
    foliage_kind: str = "broadleaf"  # broadleaf|needle|frond|grass|moss
    lod_count: int = 4
    seed: int = 1234
    schema: str = "lathe.vegetation_species.v1"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["silhouette_extents_cm"] = list(self.silhouette_extents_cm)
        payload["palette_summer"] = [list(c) for c in self.palette_summer]
        payload["trunk_profile"] = [list(p) for p in self.trunk_profile]
        return payload


# --- Canonical foundation presets ---


_OAK = VegetationSpecies(
    name="oak",
    base_preset="",
    silhouette_extents_cm=(550.0, 850.0, 550.0),
    branch_grammar={
        "trunk_height_cm": 700.0,
        "trunk_radius_cm": 28.0,
        "max_depth": 4,
        "branching_factor": 4,
        "length_decay": 0.62,
        "radius_decay": 0.55,
        "angle_jitter_rad": 0.45,
        "branch_pitch_rad": 0.95,
        "bend_amount_rad": 0.22,
        "nodes_per_segment": 5,
        "seed": 1001,
    },
    leaf_grammar={
        "min_depth": 2,
        "leaf_size_cm": 14.0,
        "leaf_aspect": 1.3,
        "leaves_per_anchor": 4,
        "min_spacing_cm": 5.5,
        "palette_size": 4,
        "extrude_height_cm": 0.05,
        "seed": 2001,
    },
    trunk_profile=[
        (0.0, 28.0),
        (200.0, 24.0),
        (450.0, 20.0),
        (700.0, 15.0),
    ],
    palette_summer=[
        (60, 140, 50),
        (90, 160, 70),
        (50, 120, 40),
        (110, 175, 80),
    ],
    foliage_kind="broadleaf",
    lod_count=4,
    seed=1001,
)


_PINE = VegetationSpecies(
    name="pine",
    base_preset="",
    silhouette_extents_cm=(450.0, 1200.0, 450.0),
    branch_grammar={
        "trunk_height_cm": 1100.0,
        "trunk_radius_cm": 24.0,
        "max_depth": 3,
        "branching_factor": 7,  # whorls of horizontal branches
        "length_decay": 0.5,
        "radius_decay": 0.45,
        "angle_jitter_rad": 0.18,
        "branch_pitch_rad": 1.35,  # near-horizontal whorls
        "bend_amount_rad": 0.12,
        "nodes_per_segment": 4,
        "seed": 1002,
    },
    leaf_grammar={
        "min_depth": 1,
        "leaf_size_cm": 4.5,
        "leaf_aspect": 7.0,  # long thin needles
        "leaves_per_anchor": 8,
        "min_spacing_cm": 1.8,
        "palette_size": 3,
        "extrude_height_cm": 0.04,
        "seed": 2002,
    },
    trunk_profile=[
        (0.0, 26.0),
        (300.0, 22.0),
        (700.0, 16.0),
        (1100.0, 8.0),
    ],
    palette_summer=[
        (40, 95, 55),
        (60, 115, 70),
        (35, 80, 45),
    ],
    foliage_kind="needle",
    lod_count=4,
    seed=1002,
)


_GRASS_TEMPERATE = VegetationSpecies(
    name="grass_temperate",
    base_preset="",
    silhouette_extents_cm=(40.0, 30.0, 40.0),
    branch_grammar={
        "trunk_height_cm": 30.0,
        "trunk_radius_cm": 0.6,
        "max_depth": 1,
        "branching_factor": 12,  # cluster of blades from a base point
        "length_decay": 0.95,
        "radius_decay": 0.6,
        "angle_jitter_rad": 0.55,
        "branch_pitch_rad": 0.35,
        "bend_amount_rad": 0.6,
        "nodes_per_segment": 4,
        "seed": 1003,
    },
    leaf_grammar={
        "min_depth": 1,
        "leaf_size_cm": 1.0,
        "leaf_aspect": 18.0,  # blade-shaped
        "leaves_per_anchor": 1,
        "min_spacing_cm": 1.2,
        "palette_size": 3,
        "extrude_height_cm": 0.04,
        "seed": 2003,
    },
    trunk_profile=[
        (0.0, 0.6),
        (15.0, 0.4),
        (30.0, 0.1),
    ],
    palette_summer=[
        (110, 165, 70),
        (140, 185, 90),
        (95, 145, 60),
    ],
    foliage_kind="grass",
    lod_count=3,
    seed=1003,
)


# --- Stub presets — inherit from a base, expose for follow-up tuning. ---


def _derive(preset: VegetationSpecies, *, name: str, **overrides: Any) -> VegetationSpecies:
    """Shallow-copy a preset, override fields, re-tag name and base_preset."""
    payload = asdict(preset)
    payload["name"] = name
    payload["base_preset"] = preset.name
    for key, value in overrides.items():
        if key in {"branch_grammar", "leaf_grammar", "frond_grammar"} and isinstance(value, dict):
            base = dict(payload.get(key) or {})
            base.update(value)
            payload[key] = base
        else:
            payload[key] = value
    payload["silhouette_extents_cm"] = tuple(payload["silhouette_extents_cm"])
    payload["palette_summer"] = [tuple(c) for c in payload.get("palette_summer", [])]
    payload["trunk_profile"] = [tuple(p) for p in payload.get("trunk_profile", [])]
    return VegetationSpecies(**payload)


_WILLOW = _derive(
    _OAK,
    name="willow",
    branch_grammar={"branch_pitch_rad": 1.6, "bend_amount_rad": 0.5, "length_decay": 0.7},
    leaf_grammar={"leaf_aspect": 4.0},
    foliage_kind="broadleaf",
)
_BIRCH = _derive(
    _OAK,
    name="birch",
    branch_grammar={"trunk_radius_cm": 14.0, "branching_factor": 3, "max_depth": 4},
    leaf_grammar={"leaf_size_cm": 8.0},
    foliage_kind="broadleaf",
)
_PALM = _derive(
    _PINE,
    name="palm",
    silhouette_extents_cm=(400.0, 900.0, 400.0),
    branch_grammar={"max_depth": 1, "branching_factor": 9, "branch_pitch_rad": 1.2},
    foliage_kind="frond",
    frond_grammar={
        "length_cm": 220.0,
        "droop_amount": 0.5,
        "leaflet_count": 22,
        "leaflet_length_cm": 30.0,
        "leaflet_width_cm": 5.0,
    },
)
_FERN = _derive(
    _GRASS_TEMPERATE,
    name="fern",
    silhouette_extents_cm=(80.0, 60.0, 80.0),
    branch_grammar={"trunk_height_cm": 10.0, "branching_factor": 7},
    foliage_kind="frond",
    frond_grammar={
        "length_cm": 60.0,
        "droop_amount": 0.7,
        "leaflet_count": 24,
        "leaflet_length_cm": 8.0,
        "leaflet_width_cm": 1.5,
    },
)
_GRASS_TROPICAL = _derive(
    _GRASS_TEMPERATE,
    name="grass_tropical",
    silhouette_extents_cm=(60.0, 80.0, 60.0),
    branch_grammar={"trunk_height_cm": 80.0, "branching_factor": 10},
    leaf_grammar={"leaf_aspect": 22.0, "leaf_size_cm": 1.5},
    foliage_kind="grass",
)
_IVY = _derive(
    _GRASS_TEMPERATE,
    name="ivy",
    silhouette_extents_cm=(120.0, 12.0, 120.0),
    branch_grammar={"trunk_height_cm": 8.0, "branching_factor": 14, "max_depth": 2},
    leaf_grammar={"leaf_size_cm": 4.0, "leaf_aspect": 1.0},
    foliage_kind="broadleaf",
)
_MOSS = _derive(
    _GRASS_TEMPERATE,
    name="moss",
    silhouette_extents_cm=(40.0, 4.0, 40.0),
    branch_grammar={"trunk_height_cm": 2.0, "branching_factor": 18, "max_depth": 1},
    leaf_grammar={"leaf_size_cm": 0.6, "leaf_aspect": 1.0},
    foliage_kind="moss",
)


SPECIES_PRESETS: dict[str, VegetationSpecies] = {
    "oak": _OAK,
    "pine": _PINE,
    "grass_temperate": _GRASS_TEMPERATE,
    "willow": _WILLOW,
    "birch": _BIRCH,
    "palm": _PALM,
    "fern": _FERN,
    "grass_tropical": _GRASS_TROPICAL,
    "ivy": _IVY,
    "moss": _MOSS,
}


# --- Decl-to-record lowering ---


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, dict) and value.get("type") == "unit":
        try:
            return float(value.get("value", default))
        except (TypeError, ValueError):
            return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def compile_vegetation_species(decl: dict[str, Any]) -> VegetationSpecies:
    """Lower a normalized ``vegetation_species`` decl into a record.

    A decl with a ``base`` value names a preset to inherit from; per-field
    overrides in ``branch_grammar``/``leaf_grammar`` blobs merge on top.
    Decls without a ``base`` start from a generic broadleaf preset
    (oak) so authors don't have to specify everything from scratch.
    """
    name = decl.get("name", "")
    values = decl.get("values", {}) or {}
    base_name = values.get("base") or values.get("preset") or "oak"
    base = SPECIES_PRESETS.get(base_name, _OAK)
    overrides: dict[str, Any] = {}
    if "branch_grammar" in values and isinstance(values["branch_grammar"], dict):
        overrides["branch_grammar"] = values["branch_grammar"]
    if "leaf_grammar" in values and isinstance(values["leaf_grammar"], dict):
        overrides["leaf_grammar"] = values["leaf_grammar"]
    if "frond_grammar" in values and isinstance(values["frond_grammar"], dict):
        overrides["frond_grammar"] = values["frond_grammar"]
    if "silhouette_extents_cm" in values:
        ext = values["silhouette_extents_cm"]
        if isinstance(ext, (list, tuple)) and len(ext) == 3:
            overrides["silhouette_extents_cm"] = tuple(_coerce_float(v, 100.0) for v in ext)
    if "lod_count" in values:
        overrides["lod_count"] = _coerce_int(values["lod_count"], base.lod_count)
    if "foliage_kind" in values:
        overrides["foliage_kind"] = str(values["foliage_kind"])
    if "seed" in values:
        overrides["seed"] = _coerce_int(values["seed"], base.seed)
    return _derive(base, name=name, **overrides)


def compile_vegetation_kit(
    decl: dict[str, Any],
    species_map: dict[str, VegetationSpecies],
) -> dict[str, Any]:
    """Lower a normalized ``vegetation_kit`` decl into a forest/garden bundle.

    Resolves the kit's ``species`` list against the program's species
    catalogue (plus the built-in ``SPECIES_PRESETS`` as a fallback) and
    records per-species density weights, scattering hints, and an
    overall biome label. Returns a dict shaped for the
    ``vegetation_library_ir`` payload.
    """
    name = decl.get("name", "")
    values = decl.get("values", {}) or {}
    raw_species = values.get("species", []) or []
    biome = values.get("biome", "temperate")
    density_per_m2 = _coerce_float(values.get("density_per_m2"), 0.25)
    distribution = values.get("distribution", "poisson")

    resolved: list[dict[str, Any]] = []
    available = {**SPECIES_PRESETS, **species_map}
    if isinstance(raw_species, dict):
        # Allow `species { oak: 0.6, pine: 0.4 }` style.
        items = raw_species.items()
    elif isinstance(raw_species, (list, tuple)):
        items = []
        for entry in raw_species:
            if isinstance(entry, str):
                items.append((entry, 1.0))
            elif isinstance(entry, dict):
                sname = entry.get("name") or entry.get("species")
                weight = entry.get("weight", 1.0)
                if sname:
                    items.append((sname, weight))
    else:
        items = []

    for sname, weight in items:
        sp = available.get(str(sname))
        if sp is None:
            resolved.append(
                {
                    "name": str(sname),
                    "weight": _coerce_float(weight, 1.0),
                    "resolved": False,
                }
            )
            continue
        resolved.append(
            {
                "name": sp.name,
                "weight": _coerce_float(weight, 1.0),
                "resolved": True,
                "lod_count": sp.lod_count,
                "foliage_kind": sp.foliage_kind,
            }
        )

    return {
        "name": name,
        "biome": biome,
        "density_per_m2": density_per_m2,
        "distribution": distribution,
        "species": resolved,
        "schema": "lathe.vegetation_kit.v1",
    }
