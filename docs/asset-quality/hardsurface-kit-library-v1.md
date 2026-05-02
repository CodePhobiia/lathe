# Standard Hard-Surface Kit Library v1 (Phase 12)

Phase 12 of the Lathe Asset Quality Upgrade introduces an additive
hard-surface kit-part library. The layer captures reusable detail
intent (fasteners, corner guards, handles, rails, warning labels)
and surfaces it as deterministic evidence on the validate-stage
report.

## Overview

Phase 12 adds:

- A pure validator `evaluate_kit_library(asset, runtime)` registered
  in the validate pipeline and writing its evidence under the new
  top-level `kit_library` key (the 26th key on the validate-stage
  report).
- A separately-tested disk loader `load_kit_library()` that walks
  the internal filesystem convention `std/kits/hardsurface/` and
  returns a populated `KitLibrary`.
- Three deterministic lookup helpers — `lookup_kit_part`,
  `kit_parts_by_category`, and `kit_parts_for_family` — that operate
  on the loaded library.
- An internal JSON schema `schema/kit_part.schema.json` that pins the
  on-disk shape of each kit-part data file.
- Executor wiring that calls the loader before the validate stage and
  publishes the result under `runtime["_kit_library"]`. The same hook
  publishes `None` when no fixtures exist on disk so the validator
  emits a structured `kit_library_not_loaded` skipped reason.

Phase 12 does NOT add public `.lth` syntax. There is no
`kit { ... }` or `library { ... }` block in the grammar, parser,
normalizer, resolver, or checker. Kit-part loading is internal: the
executor drives it via filesystem convention plus runtime
publication. Phase 13 is the only phase allowed to expose this
surface to `.lth`.

## Filesystem layout

```
std/kits/hardsurface/
├── README.md
├── fasteners/
│   ├── hex_bolt_m6.json
│   └── flat_rivet_4mm.json
├── corner_guards/
│   ├── welded_steel_l_bracket.json
│   └── stamped_corner_cap.json
├── handles/
│   └── recessed_inset_grip.json
├── rails/
│   ├── foot_rail_bar.json
│   └── trim_band_strip.json
└── warning_labels/
    ├── caution_yellow_strip.json
    └── biohazard_orange_decal.json
```

Phase 12 ships exactly these five categories. Every fixture is
`"kind": "procedural"` — no real meshes ship in this phase. Future
phases may add `"kind": "mesh_stub"` parts; the schema reserves the
slot today.

## Per-part schema

The canonical schema lives in `schema/kit_part.schema.json` and is
authoritative. Required top-level fields:

- `name` (string, globally unique within the library)
- `category` (enum: `fasteners`, `corner_guards`, `handles`, `rails`,
  `warning_labels`)
- `kind` (enum: `procedural`, `mesh_stub`)
- `procedural_recipe` (object, required when `kind == "procedural"`,
  free-form recipe descriptor)
- `mesh_stub_uri` (string, required when `kind == "mesh_stub"`,
  relative path under `std/kits/hardsurface/`)
- `material_zones` (array of strings — should align with Phase 8
  material/wear-graph zone vocabulary where possible)
- `sockets` (array of `{name, anchor_axis, default_position}` objects;
  empty array allowed)
- `placement_constraints` (`{face, normal_axis, requires_flat_surface}`)
- `scale_range` (`{min, max}` with both > 0 and `max >= min`)
- `allowed_families` (array of family names; `["*"]` means all)
- `lod_behavior` (`{strategy, retained_for_collision}` — strategy
  enum is `always_present`, `drop_at_lod1`, `drop_at_lod2`,
  `drop_at_lod3`)
- `bake_group` (string)
- `preview_thumbnail` (optional string URI; when omitted the loader
  emits a deterministic `kit://hardsurface/<category>/<name>/preview_thumbnail`
  metadata fallback)
- `provenance` (`{source, version, license}` — license enum is
  `internal`, `CC0`, `MIT`)

`additionalProperties: false` is enforced at the top level so
authors get a hard signal when the schema and the data drift.

### Example (fastener)

```json
{
  "name": "hex_bolt_m6",
  "category": "fasteners",
  "kind": "procedural",
  "procedural_recipe": {
    "primitive": "hex_prism_with_threaded_shank",
    "head_diameter_mm": 10.0,
    "head_height_mm": 4.0,
    "shank_diameter_mm": 6.0,
    "shank_length_mm": 18.0,
    "thread_pitch_mm": 1.0
  },
  "material_zones": ["bare_metal_fastener"],
  "sockets": [
    {
      "name": "shank_anchor",
      "anchor_axis": "-z",
      "default_position": [0.0, 0.0, 0.0]
    }
  ],
  "placement_constraints": {
    "face": "any",
    "normal_axis": "any",
    "requires_flat_surface": true
  },
  "scale_range": {"min": 0.8, "max": 1.4},
  "allowed_families": ["industrial_crate", "service_cabinet", "control_pedestal"],
  "lod_behavior": {
    "strategy": "drop_at_lod2",
    "retained_for_collision": false
  },
  "bake_group": "trim_metal",
  "provenance": {
    "source": "std/kits/hardsurface (Phase 12 internal)",
    "version": "v1",
    "license": "internal"
  }
}
```

## MVP categories

| Category          | Purpose                                                      |
|-------------------|--------------------------------------------------------------|
| `fasteners`       | Bolts, rivets, screws — small high-frequency repeating parts |
| `corner_guards`   | L-brackets, stamped caps — protective corner detailing       |
| `handles`         | Recessed grips, latch handles — interaction-affordance parts |
| `rails`           | Foot rails, trim bands — long thin linear detailing          |
| `warning_labels`  | Decals — flat surface annotations for safety / role iconogr. |

## Loader behavior

- Missing base directory → empty `KitLibrary` plus a single
  `("kit_library", "kit_library_directory_missing")` skipped record.
- Missing category subdirectory → one
  `("category_<name>", "category_directory_missing")` per missing
  category.
- Non-JSON file in a category directory → silently ignored (the
  loader only consumes `*.json` files).
- Unreadable JSON file →
  `("kit_part_<filename>", "kit_part_unreadable")`.
- Malformed JSON (parse failure) →
  `("kit_part_<filename>", "kit_part_malformed")`.
- Schema violation (missing or wrong-typed field) →
  `("kit_part_<filename>", "kit_part_schema_violation:<detail>")`
  where `<detail>` carries the offending field (e.g.
  `missing_field_category`, `invalid_field_scale_range_order`).
- Duplicate part name:
  `("kit_part_<filename>", "kit_part_duplicate_name:<name>")`.
  Kit-part names are globally unique across categories; the first
  valid part wins and later duplicates are skipped.

Failures are non-fatal — the loader returns whatever parts DID parse.

## Validator API

Three lookup helpers operate on a loaded `KitLibrary`:

- `lookup_kit_part(library, name)` — exact-name lookup. Returns
  `None` for missing names or empty input.
- `kit_parts_by_category(library, category)` — every part in a
  category, sorted by name. Returns `()` for unknown categories.
- `kit_parts_for_family(library, family)` — every part whose
  `allowed_families` contains the literal family name OR the
  wildcard `"*"`. Sorted by `(category, name)` for stability.

These helpers are pure and deterministic. They do not consult
`runtime` — that is the validator's responsibility.

## Family resolution

The validator resolves the active asset family in this order:

1. `runtime["design_brief"]["family_inference"]["matched_family"]`
   (Phase 2 inferred family — preferred when the design brief has
   already run).
2. `asset["family"]` (defensive fallback; not part of v0.1 syntax).
3. `"generic"` (last-resort default).

The same precedence ladder appears in
`reference_board.py::_resolve_family` so cross-validator family
resolution stays consistent.

## Skipped-evidence contract

Per `AGENTS.md`, every category emits exactly one structured record
with one of the fixed reason tokens:

- `kit_library_not_loaded` — `runtime["_kit_library"]` is absent.
- `kit_library_directory_missing` — the base directory does not
  exist on disk.
- `category_directory_missing` — a category subdirectory is absent.
- `kit_part_unreadable` — a candidate JSON file cannot be read.
- `kit_part_malformed` — a candidate JSON file fails parse.
- `kit_part_schema_violation:<detail>` — a candidate JSON file
  parses but fails schema validation.
- `kit_part_duplicate_name:<name>`: a candidate JSON file reuses a
  name already loaded from an earlier valid part.

Skipped reasons are deduplicated and sorted by `(category, reason)`.
The loader never fabricates a part for a missing or malformed
fixture.

## Pipeline placement

The validator is registered in
`lathe/core/stages/validate.py`'s `_PIPELINE` immediately after
`reference_board` and before `geometry_integrity`. Output additively
appears under the top-level `kit_library` key of the validate-stage
report.

The executor (`lathe/executor.py`) publishes
`runtime["_kit_library"]` BEFORE `stage_validate.run` is called —
mirroring the Phase 11 `runtime["_reference_board"]` convention.
`BUILD_CACHE_VERSION` was bumped from `"v11_rc1"` to `"v12_rc1"`
because the validate-stage report shape changed (added a 26th
top-level key); the bump invalidates stale build caches that pre-date
this change.

## Crate grammar integration note

Phase 12 deliberately does NOT mutate
`lathe/asset_quality/grammar_lowering.py` or change the Phase 6
industrial_crate recipe behaviour. The original tasklist phrase
"integrate with crate grammar if safe" only allows pure annotation /
lookup integration — the kit_library validator merely supplies a
deterministic lookup surface. Wiring kit parts into the recipe so
the lowered shape program references real kit-part nodes is reserved
for **Phase 14 (golden examples)**, where authored crate fixtures
will explicitly reference parts from this library.

## Forward references

- **Phase 13** is the only phase allowed to expose this surface to
  `.lth` (potential `kit { }` and `library { }` blocks). Phase 12
  reserves vocabulary by keeping every per-part field name in the
  internal schema clearly authoring-friendly so a future grammar can
  parse the same field set without rename pressure.
- **Phase 14 (golden examples)** will pull from this library when
  authoring full reference outputs.
