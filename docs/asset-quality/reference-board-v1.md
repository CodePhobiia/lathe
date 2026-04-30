# Reference Board v1 (Phase 11)

Phase 11 of the Lathe Asset Quality Upgrade introduces an additive
reference / moodboard ingestion layer. The layer captures
art-direction intent that lives outside `.lth` (palette, lighting,
silhouette references, PBR material targets, negative constraints)
and surfaces it as deterministic evidence on the validate-stage
report.

## Overview

Phase 11 adds:

- A pure validator `evaluate_reference_board(asset, runtime)`
  registered in the validate pipeline and writing its evidence under
  the new top-level `reference_board` key (the 25th key on the
  validate-stage report).
- A separately-tested disk loader `load_reference_board(asset_name)`
  that reads small JSON fixtures from
  `examples/refs/asset_quality/<asset_name>/` and returns a raw dict.
- Executor wiring that calls the loader before the validate stage and
  publishes the raw dict under `runtime["_reference_board"]`. The
  same hook publishes nothing when no fixtures exist on disk.
- An additive `negative_constraints` merge in
  `lathe.asset_quality.design_brief.evaluate_design_brief` — when a
  reference board is present, its negative constraints are appended
  to the brief (deduplicated, with existing brief values first).

Phase 11 does NOT add public `.lth` syntax. There is no
`references { ... }` block in the grammar, parser, normalizer,
resolver, or checker. Reference loading is internal: the executor
drives it via filesystem convention plus runtime publication. Phase
13 is the only phase allowed to expose this surface to `.lth`.

## Schema

The validator emits the following payload under the `reference_board`
key of the validate-stage report:

```json
{
  "version": "reference_board_v1",
  "asset_name": "industrial_crate",
  "family": "industrial_crate",
  "board": {
    "mood": {
      "palette": ["weathered_steel", "oxidized_brass", "soot_smudge"],
      "lighting": "industrial_overhead_warm",
      "era": "post_industrial_workshop",
      "descriptors": ["utilitarian", "field_repaired", "well_used"]
    },
    "silhouettes": [
      {
        "intent": "rectangular_chest_with_corner_guards",
        "proportions": {"width_to_height": 1.44, "depth_to_width": 0.63},
        "descriptors": ["recessed_handles", "trim_band_centered"],
        "image_uri": null
      }
    ],
    "materials": [
      {
        "target": "painted_steel_body",
        "pbr_hints": {"roughness": 0.62, "metallic": 0.85, "albedo_value": 0.34},
        "descriptors": ["matte_industrial_paint", "edge_wear_breakthrough"]
      }
    ],
    "negatives": [
      {"constraint": "no_chrome_finishes", "rationale": "industrial crates are matte"}
    ]
  },
  "summary": {
    "has_mood": true,
    "silhouette_count": 1,
    "material_count": 1,
    "negative_count": 1,
    "all_required_present": true
  },
  "skipped_reasons": [],
  "warnings": [],
  "diagnostics": []
}
```

The dataclasses backing the payload (`MoodReference`,
`SilhouetteReference`, `MaterialReference`, `NegativeReference`,
`ReferenceBoard`, `SkippedReason`) are all `@dataclass(frozen=True)`
and live in `lathe/asset_quality/reference_board.py`.

`summary.all_required_present` is `True` iff:

1. a mood reference is present, AND
2. at least one silhouette is present, AND
3. at least one material is present.

Negatives are optional for the flag (they still merge into the
design brief when present).

## Filesystem layout

Each per-asset fixture directory is named after the asset:

```
examples/refs/asset_quality/<asset_name>/
    mood.json
    silhouette.json
    materials.json
    negative.json
```

All four sub-files are optional. A missing per-asset directory means
the loader returns `None`. A directory that exists but is missing a
sub-file emits a `reference_missing` skipped reason for the absent
category.

## Per-file schema

### `mood.json`

```json
{
  "palette": ["palette_token_1", "palette_token_2"],
  "lighting": "lighting_token",
  "era": "era_token",
  "descriptors": ["descriptor_1", "descriptor_2"]
}
```

### `silhouette.json`

Canonical (object) form:

```json
{
  "silhouettes": [
    {
      "intent": "intent_token",
      "proportions": {"key": 1.0},
      "descriptors": ["descriptor_1"],
      "image_uri": null
    }
  ]
}
```

The loader also tolerates a direct array form (`[{...}, ...]`).

### `materials.json`

```json
{
  "materials": [
    {
      "target": "material_target",
      "pbr_hints": {"roughness": 0.5, "metallic": 0.0},
      "descriptors": ["descriptor_1"]
    }
  ]
}
```

The loader also tolerates a direct array form.

### `negative.json`

```json
{
  "negatives": [
    {"constraint": "no_chrome_finishes", "rationale": "matte only"}
  ]
}
```

The loader also tolerates a direct array form.

## Loader behaviour

`load_reference_board(asset_name, base_path=None)` returns either a
raw dict carrying the four sub-fixture payloads plus a structured
`skipped` list, or `None` when the per-asset directory does not
exist. The default base path is
`examples/refs/asset_quality` (relative to the current working
directory).

The loader never raises. Behaviour is:

- Missing per-asset directory: return `None`.
- Directory exists but a sub-file is missing: include the category
  in `skipped` with `reason="reference_missing"`.
- Sub-file exists but cannot be parsed as JSON or has an
  unparseable top-level shape: include the category in `skipped`
  with `reason="reference_malformed"`.
- Extra unknown fields on any sub-file are tolerated and ignored.

## Design brief integration

When the executor publishes a reference board to
`runtime["_reference_board"]`, the design brief's
`negative_constraints` field is extended with each reference
negative constraint string. The merge:

1. Preserves existing brief values in their original order, placed
   first.
2. Appends reference values in fixture order.
3. Deduplicates while preserving first-occurrence order.

This is the only edit Phase 11 makes to `design_brief.py` — all
twelve other brief fields are unchanged.

## Skipped-evidence contract

Per `AGENTS.md`, every skipped category emits a single structured
record with one of the fixed reason tokens:

- `reference_board_not_loaded` — `runtime["_reference_board"]` is
  absent (no fixture directory or executor never called the loader).
  The validator returns a well-formed empty payload.
- `reference_missing` — the fixture directory exists but the
  sub-file for the named category is absent.
- `reference_malformed` — the sub-file exists but is not valid JSON
  or its top-level shape is unparseable.

Skipped reasons are deduplicated and sorted by `(category, reason)`
for determinism.

## Pipeline placement

The validator is registered in `lathe/core/stages/validate.py`'s
`_PIPELINE` immediately after `vision_critique` and before
`geometry_integrity`:

```
... -> vision_critique -> reference_board -> geometry_integrity ...
```

`weight=0.0` and `stage_dependencies=[]`, mirroring the Phase 1-10
validators that are evidence-only and do not consume stage runtime
bundles.

## Configuration

There is no Phase 11 runtime-config knob. The convention is
filesystem-driven: a fixture directory under
`examples/refs/asset_quality/<asset_name>/` is sufficient. The
runtime-config layer remains untouched at this phase.

## Forward references

- Phase 12 (kit / library subgraphs) will likely consume Phase 11's
  reference board to seed assembly intent without relying on
  filesystem-only fixtures.
- Phase 13 (governed `references { ... }` syntax) is the first
  phase allowed to expose this layer to `.lth` source. Until then,
  the reference board is internal-only.
- Phase 14 (golden examples) will introduce richer reference fixtures
  for the four hero assets on top of this layout. The Phase 11 fixture
  for `industrial_crate` is the seed.
