# Preview Evidence v1

> **Phase 9 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the deterministic preview-evidence layer that
> categorizes the previews requested by `asset.package.previews`,
> records their expected paths, attaches bake-map evidence
> sourced from the surface bundle, and emits structured skipped
> reasons whenever a category is intentionally absent.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 11
> (preview and evidence),
> `docs/asset-quality/improvement-tasklist.md` Section 9 (Phase 9 task list),
> `docs/asset-quality/high-low-relation-v1.md` (Phase 7 — the
> bake-map evidence the layer reads),
> `docs/asset-quality/material-wear-graph-v1.md` (Phase 8 — the
> 22nd validate-report key, immediately preceding `preview_evidence`).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/preview_evidence.py`
**Validator name:** `preview_evidence`
**Payload version field:** `preview_evidence_v1`

---

## 1. Overview

Phase 9 makes build evidence useful for judging final art quality
rather than pipeline completion. The package stage has long
emitted up to six preview images (turntable, wireframe,
material_ids, uv_layout, collision, lod_sheet) plus per-map bake
outputs (normal / ao / curvature / id) under the surface bundle,
but the validate-stage report stopped at `previews: list[str]`
inside the package manifest — there was no way for a reviewer to
distinguish the *final beauty* preview from the *material-ID*
debug render, no structured catalog of bake-map URIs, and no
truthful record when a comparison sheet was unavailable.

Per spec Section 11, the goal is:

- distinguish final beauty from debug previews,
- attach additive report links to every preview path,
- record truthful skipped evidence when a renderer or
  comparison-sheet tool is unavailable.

Phase 9 is **evidence + diagnostic only**. It does not run a
renderer, drive Blender, or produce a comparison sheet — those
producers belong to the package stage (which runs *after*
validate in `lathe.executor.STAGE_ORDER`) and to forward phases
that add a real before / after pipeline.

### What this layer does

- Defines `PreviewEntry`, `BakeMapEntry`, and `SkippedReason`
  frozen dataclasses with `to_dict()` round-trips.
- Maps the six standard preview names declared by
  `lathe/core/stages/package.py` to six top-level renderable
  categories (`final_beauty`, `material_ids`, `wireframe`,
  `uv_layout`, `collision`, `lod_sheet`) plus the bake-map and
  comparison-sheet categories.
- Emits a deterministic per-preview path under
  `stages/package/previews/<name>.png` (relative to the asset
  out_dir) for each category that is requested in
  `package.previews`.
- Reads `runtime["surface"]["bundle"]["maps"]` and
  `runtime["surface"]["bundle"]["outputs"]` /
  `runtime["surface"]["bundle"]["bake_outputs"]` to populate the
  `bake_maps` category with per-role evidence (`normal_map`,
  `ao_map`, `curvature_map`, `id_map`). Surface-stage local
  `maps/<name>.png` links are lifted to asset-root
  `stages/surface/maps/<name>.png` report links.
- Records structured `skipped_reasons` for every absent category,
  including unrecognised preview names (`unknown_preview_<name>`),
  bake maps without a published URI, and the comparison sheet
  (always — Phase 9 intentionally does not yet ship a renderer
  for it).
- Computes declared-vs-present preview summary fields. During
  validate, renderable previews are expected but not present yet
  because package runs later.
- Computes the `distinct_final_from_material_ids` flag from
  conservative declared evidence: final and material-ID entries
  must have distinct names, modes, and expected paths.
- Publishes the result on `runtime["preview_evidence"]` and emits
  the additive `preview_evidence` key on the validate-stage
  report (the 23rd top-level key, on top of the 22 from Phases 0
  through 8).

### What this layer does *not* do

- Run a renderer, drive Blender, or produce a comparison sheet.
- Touch the package stage (`lathe/core/stages/package.py` is
  unchanged). The package stage continues to render its previews
  unchanged after validate completes.
- Verify package-rendered preview files on disk. Validate runs
  before package, so the layer emits *declared/expected* paths
  only and keeps `*_present=False` for renderable previews.
- Touch `.lth` source syntax. The Phase 9 contract is internal —
  Phase 13 will add the public surface-program syntax that lets
  authors override defaults; until then, the layer reads the
  existing `package.previews` list and an optional internal
  `package.comparison_sheet` boolean (defaults to False).
- Touch `lathe.shape.intent_mesh_handoff_v1` or any shape-stage
  module.
- Block certification. Like Phases 1 through 8, the validator is
  registered with `weight=0.0` and emits no `diagnostics` entries.
- Invent results when an external tool is unavailable. Per
  `AGENTS.md`, every gap records a structured `skipped_reason`
  instead.

---

## 2. Goals and non-goals

**Goals:**

- Make the validate report the canonical source for *what
  previews exist* and *what each preview means*.
- Distinguish final beauty (`turntable` rendered shaded) from the
  material-ID debug preview so reviewers cannot mistake a debug
  render for the final art preview.
- Record bake-map URIs (normal / ao / curvature / id) alongside
  the preview catalog so Phase 10's vision critique loop has a
  single read-only source for evidence imagery.
- Emit truthful skipped reasons whenever a category is absent so
  reviewers know whether a missing preview is intentional, a
  config gap, or a tool-unavailable case.

**Non-goals:**

- Render any new image. Phase 9 reads the package config
  declaration and the surface bundle; the package stage still
  produces the bytes.
- Add a preview-quality metric to
  `quality_diagnostics.metrics`. The 6-metric set is the
  carry-forward contract from Phase 7.
- Touch existing top-level keys. Phase 9 only adds the
  `preview_evidence` key.

---

## 3. Schema

### 3.1 Frozen dataclasses

```python
@dataclass(frozen=True)
class PreviewEntry:
    role: str           # one of the six renderable categories
    mode: str           # render mode hint: "shaded", "wireframe", "material_ids",
                        # "uv_layout", "lod_sheet"
    name: str           # the preview name as declared in package.previews
    path: str           # deterministic relpath under stages/package/previews/
    status: str         # always "declared" in Phase 9

@dataclass(frozen=True)
class BakeMapEntry:
    role: str           # "normal_map", "ao_map", "curvature_map", "id_map"
    uri: str | None     # None when declared in surface.bundle.maps without a
                        # published URI in surface.bundle.outputs
    status: str         # always "declared" in Phase 9

@dataclass(frozen=True)
class SkippedReason:
    category: str       # the category that was skipped, or
                        # "unknown_preview_<name>" for unrecognised declared
                        # names
    reason: str         # one of the structured tokens documented in §6
```

### 3.2 Validator payload

The `evaluate_preview_evidence(asset, runtime) -> dict` function
returns a payload with the following exact eight top-level keys:

```python
{
    "version": "preview_evidence_v1",
    "asset_name": str,
    "previews": {
        "final_beauty":     [PreviewEntry, ...],
        "material_ids":     [PreviewEntry, ...],
        "wireframe":        [PreviewEntry, ...],
        "uv_layout":        [PreviewEntry, ...],
        "collision":        [PreviewEntry, ...],
        "lod_sheet":        [PreviewEntry, ...],
        "bake_maps":        [BakeMapEntry, ...],
        "comparison_sheet": [],     # always empty in Phase 9
    },
    "preview_summary": {
        "final_beauty_present":              bool,   # always False in Phase 9
        "material_ids_present":              bool,   # always False in Phase 9
        "wireframe_present":                 bool,   # always False in Phase 9
        "final_beauty_declared":             bool,
        "material_ids_declared":             bool,
        "wireframe_declared":                bool,
        "bake_map_count":                    int,    # entries with uri != None
        "comparison_sheet_present":          bool,   # always False in Phase 9
        "comparison_sheet_requested":        bool,
        "comparison_sheet_renderer_available": bool, # always False in Phase 9
        "distinct_final_from_material_ids":  bool,
        "total_preview_count":               int,    # sum across renderable categories
    },
    "report_links": [str, ...],     # additive flat list of every declared
                                    # preview path and published bake-map URI;
                                    # no duplicates
    "skipped_reasons": [SkippedReason, ...],   # sorted by (category, reason)
    "warnings": [str, ...],         # non-empty when material_ids is requested
                                    # without turntable
    "diagnostics": [],              # empty by default; reserved for forward phases
}
```

The `previews` dict keys are emitted in fixed order:
`final_beauty, material_ids, wireframe, uv_layout, collision,
lod_sheet, bake_maps, comparison_sheet`. Within each renderable
category, entries appear in the order they are declared in
`package.previews`.

---

## 4. Preview category catalog

The preview-name to category mapping mirrors the canonical
render dispatch in `lathe/core/stages/package.py` lines ~167-200.

| `package.previews` name | Category          | Render mode        |
|-------------------------|-------------------|--------------------|
| `turntable`             | `final_beauty`    | `shaded`           |
| `wireframe`             | `wireframe`       | `wireframe`        |
| `material_ids`          | `material_ids`    | `material_ids`     |
| `uv_layout`             | `uv_layout`       | `uv_layout`        |
| `collision`             | `collision`       | `wireframe`        |
| `lod_sheet`             | `lod_sheet`       | `lod_sheet`        |

Bake-map evidence comes from the surface bundle:

| `surface.bundle.maps` name | Category role     |
|----------------------------|-------------------|
| `normal`                   | `normal_map`      |
| `ao`                       | `ao_map`          |
| `curvature`                | `curvature_map`   |
| `id`                       | `id_map`          |

The comparison sheet is always emitted as an empty list — Phase 9
intentionally does not ship a comparison-sheet renderer (see §6).

---

## 5. Final beauty distinction rule

The conservative signal that a build's declared evidence expects
an art-quality preview distinct from the material-ID debug render
is the `distinct_final_from_material_ids` flag. It is `True` iff:

1. the final beauty preview is requested (`turntable` is in
   `package.previews`), AND
2. the material-ID preview is requested (`material_ids` is in
   `package.previews`), AND
3. the expected paths are distinct, AND
4. the declared names and modes are semantically distinct
   (`turntable` / `shaded` versus `material_ids` /
   `material_ids`).

The flag is a declared-evidence distinction, not an on-disk
rendered-file presence check. The rendered-file truth lives in
the `*_present` fields, which remain `False` during validate.

If only `material_ids` is requested without `turntable`, the
flag stays `False` *and* a warning fires:

```
package.previews requests 'material_ids' but not 'turntable' —
final beauty preview is missing.
```

The warning is informational only; it does not block
certification (Phase 9 emits `diagnostics: []`). Strict-mode
behaviour is reserved for a forward phase.

---

## 6. Skipped-evidence contract

Per `AGENTS.md`, the layer never invents results when a category
is absent. Every absence emits a structured record under
`skipped_reasons` with one of the following `reason` tokens:

| `reason` token                          | When it fires                                                         |
|-----------------------------------------|-----------------------------------------------------------------------|
| `preview_not_requested_by_package_config` | A renderable category is not present in `package.previews`.        |
| `preview_role_not_recognized`           | An unrecognised preview name appears in `package.previews`. The category is recorded as `unknown_preview_<name>` so the typo is visible. |
| `bake_map_not_produced`                 | A canonical bake map is not published under `surface.bundle.outputs` / `bake_outputs`. The role still appears in `bake_maps` with `uri=None` when the map is *declared* in `surface.bundle.maps` but missing from outputs. |
| `comparison_sheet_not_requested`        | `package.comparison_sheet` is absent or False.                        |
| `comparison_sheet_renderer_unavailable` | `package.comparison_sheet=True` but Phase 9 does not yet ship a renderer for it. The absence is recorded truthfully rather than faked. |

---

## 7. Pipeline placement

The validator is registered in
`lathe/core/stages/validate.py` `_PIPELINE`:

```
... -> material_wear_graph -> preview_evidence -> geometry_integrity -> ...
```

`stage_dependencies=["surface"]` because the bake-map evidence
reads `runtime["surface"]["bundle"]["maps"]` and `outputs`. The
`package` stage is *not* listed as a dependency — validate runs
before package in `STAGE_ORDER`, and the layer cannot read the
package bundle at validate time. Instead it derives expected
preview paths from the asset's `package.previews` config, which
is populated unconditionally by the resolver.

`weight=0.0` keeps the validator informational — its score does
not contribute to the aggregate certification score, mirroring
the carry-forward stance from Phases 1 through 8.

The composition layer's automatic per-validator publication
(`runtime[validator.name] = report.evidence` in
`lathe/validators/composition.py` lines 287-291) places the
evidence under `runtime["preview_evidence"]` so downstream
validators in the same pipeline run can read it.

The validate-stage report carries the same evidence under the
top-level `preview_evidence` key, taking the report from 22 to
**23 top-level keys**.

---

## 8. Forward references

- **Phase 10 — Optional Vision Critique Loop.** The vision
  critique consumer reads `preview_evidence.report_links` to
  locate the final beauty preview and the bake-map URIs without
  re-deriving paths. Per
  `docs/asset-quality/improvement-tasklist.md` §10.2, the
  deterministic-fallback path uses the
  `distinct_final_from_material_ids` flag and the
  `comparison_sheet_present` flag to gate which critique modes
  fire.
- **Phase 14 — Golden Examples.** The crate MVP golden example
  expects `final_beauty_declared=True`,
  `material_ids_declared=True`,
  `distinct_final_from_material_ids=True`, and four bake-map
  URIs — Phase 9 provides the contract those expectations land
  against.
- **Phase 15 — CI / quality gates.** The CI workflow consumes
  `preview_evidence.skipped_reasons` to decide whether a missing
  preview is a fail (config gap) or an accepted absence
  (comparison sheet renderer pending).

Phase 9 is intentionally additive: forward phases can extend the
schema (e.g. promote `status="declared"` to `"present"` or
`"missing"` once on-disk verification runs in a separate stage)
without breaking existing consumers.
