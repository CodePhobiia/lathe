# Material/Wear Graph v1

> **Phase 8 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the deterministic Material/Wear Graph IR that binds wear
> masks and material zones to construction-graph nodes (Phase 4) and
> structural edge targets, plus a uniform-noise diagnostic that
> detects when the existing surface output looks like procedural noise
> rather than semantically driven storytelling.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 12
> (material/wear graph),
> `docs/asset-quality/improvement-tasklist.md` Section 8 (Phase 8 task list),
> `docs/asset-quality/semantic-construction-graph.md` (Phase 4 — the
> nodes wear masks bind to),
> `docs/asset-quality/grammar-lowering-v1.md` (Phase 6 — the recipe
> that synthesizes the bound nodes),
> `docs/asset-quality/high-low-relation-v1.md` (Phase 7 — the
> `bake_maps` evidence the uniform-noise score consumes for
> `skipped_reasons`).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/material_wear_graph.py`
**Validator name:** `material_wear_graph`
**Payload version field:** `material_wear_v1`

---

## 1. Overview

Phase 8 makes material/wear maps semantic instead of uniform procedural
noise. The Material/Wear Graph IR records two kinds of authoring intent:

- **Material zones** — base materials and underlayers (e.g.
  `painted_steel_body` over `dark_bare_metal`), each with a base color,
  roughness, metalness, and an optional binding to one of the asset's
  intent parts.
- **Wear masks** — semantic damage / contact / decal authorings (e.g.
  `convex_edge_wear` along `body_shell.outer_edges`, `lower_contact_scuff`
  on each foot node), each carrying an intensity in `[0.0, 1.0]` and a
  binding to either a construction-graph node id, a structural edge
  target, or both.

Per spec Section 12, the goal is **material storytelling, not just color
variation**. A uniform-noise diagnostic catches the failure case where
the surface output reads as procedural noise — flat zone diversity, no
mask bindings — and emits a warning so reviewers know the recipe needs
attention.

### What this layer does

- Defines `WearMask`, `MaterialZone`, and `MaterialWearGraph` frozen
  dataclasses and the immutable `WEAR_MASK_TYPES` (5) and `ZONE_TYPES`
  (2) registries.
- Encodes a per-family default graph for `industrial_crate` mirroring
  the spec Section 12.3 painted-steel example.
- Validates that every mask `bound_node_id` resolves against the live
  construction graph (synthesized + baseline), and emits structured
  orphan diagnostics under `binding_validation`.
- Computes a deterministic uniform-noise score from zone diversity and
  wear-binding ratio, with a warning at score `>= 0.50`.
- Records structured `skipped_reasons` when the bake-map evidence the
  graph relies on (Phase 7) is incomplete.
- Publishes the result on `runtime["material_wear_graph"]` and emits
  the additive `material_wear_graph` key on the validate-stage report
  (the 22nd top-level key, on top of the 21 from Phases 0 through 7).

### What this layer does *not* do

- Run a real material-authoring tool, drive Blender, or produce mask
  textures. Phase 8 is **evidence + diagnostic only**. The real bake
  producer is reserved for Phase 14 golden examples and any future
  surface-stage migration.
- Touch the surface stage (`lathe/surface_runtime.py` is unchanged).
- Touch `.lth` source syntax. The Phase 8 contract is internal-only;
  Phase 13 will add the public surface-program syntax that lets
  authors override the per-family defaults.
- Touch `lathe.shape.intent_mesh_handoff_v1`, `lathe/shape_backend.py`,
  `lathe/shape_providers.py`, or `lathe/shape_ir.py`.
- Add a 7th metric to `quality_diagnostics.metrics`. Per Phase 7's
  carry-forward constraint, the metric set stays at exactly 6.
- Modify, rename, or remove any existing report field. Phase 8 only
  adds the `material_wear_graph` key.
- Block certification. Like Phases 1 through 7, the validator is
  registered with `weight=0.0` and emits no top-level `diagnostics`
  field.
- Invent results when an external tool is unavailable. Per `AGENTS.md`,
  every gap records a structured `skipped_reason` instead.

---

## 2. Goals and non-goals

**Goals:**

- Encode authoring intent for materials and wear deterministically so
  Phase 14 golden examples can demonstrate convincing material
  storytelling without `.lth` syntax changes.
- Bind wear masks to construction-graph nodes (Phase 4) and structural
  edge targets so a downstream consumer can locate each mask in space
  without re-deriving geometry.
- Detect uniform-noise output (single zone, no bindings) as a
  warning-level diagnostic.

**Non-goals:**

- Generate any texture, drive Blender, or trigger a bake.
- Replace the surface stage's existing `material_zones` slot. Phase 8
  reads it as evidence; the surface stage continues to publish it
  unchanged.
- Add a new metric to `quality_diagnostics.metrics`. The 6-metric set
  is the carry-forward contract from Phase 7.

---

## 3. Schema

### 3.1 Frozen dataclasses

```python
@dataclass(frozen=True)
class WearMask:
    mask_id: str
    mask_type: str            # one of WEAR_MASK_TYPES
    intensity: float          # 0.0..1.0
    bound_node_id: str | None
    bound_edge_target: str | None
    parameters: dict[str, Any]

@dataclass(frozen=True)
class MaterialZone:
    zone_id: str
    zone_type: str            # one of ZONE_TYPES
    base_color: str           # hex token like "#4f5668"
    roughness: float
    metalness: float
    bound_part: str | None
    parameters: dict[str, Any]

@dataclass(frozen=True)
class MaterialWearGraph:
    family: str
    version: str              # always MATERIAL_WEAR_VERSION
    materials: tuple[MaterialZone, ...]
    underlayers: tuple[MaterialZone, ...]
    wear_masks: tuple[WearMask, ...]
```

### 3.2 Registries

```python
WEAR_MASK_TYPES = frozenset({
    "convex_edge_wear",
    "concave_grime",
    "lower_contact_scuff",
    "handle_touch_wear",
    "decal_wear",
})  # 5

ZONE_TYPES = frozenset({
    "base_material",
    "underlayer",
})  # 2
```

Membership is exact and pinned by tests.

### 3.3 Payload (returned by `evaluate_material_wear_graph`)

```json
{
  "version": "material_wear_v1",
  "family": "industrial_crate",
  "graph": {
    "family": "industrial_crate",
    "version": "material_wear_v1",
    "materials": [
      {
        "zone_id": "painted_steel_body",
        "zone_type": "base_material",
        "base_color": "#4f5668",
        "roughness": 0.62,
        "metalness": 0.0,
        "bound_part": "body",
        "parameters": {}
      }
    ],
    "underlayers": [
      {
        "zone_id": "dark_bare_metal",
        "zone_type": "underlayer",
        "base_color": "#2a2a2a",
        "roughness": 0.5,
        "metalness": 1.0,
        "bound_part": "body",
        "parameters": {}
      }
    ],
    "wear_masks": [
      {
        "mask_id": "recipe.wear.convex_edges_body",
        "mask_type": "convex_edge_wear",
        "intensity": 0.28,
        "bound_node_id": null,
        "bound_edge_target": "body_shell.outer_edges",
        "parameters": {}
      }
    ]
  },
  "graph_summary": {
    "material_zone_count": 1,
    "underlayer_count": 1,
    "wear_mask_count": 7,
    "wear_masks_by_type": {
      "convex_edge_wear": 1,
      "concave_grime": 1,
      "lower_contact_scuff": 2,
      "handle_touch_wear": 2,
      "decal_wear": 1
    },
    "bound_to_construction_nodes": 5,
    "bound_to_edge_targets": 2,
    "bound_to_both": 0
  },
  "binding_validation": {
    "all_node_bindings_resolved": true,
    "orphan_node_bindings": [],
    "construction_graph_node_count": 25
  },
  "uniform_noise": {
    "is_uniform_noise": false,
    "uniform_noise_score": 0.171429,
    "zone_diversity": 0.666667,
    "wear_binding_ratio": 1.0,
    "warnings": []
  },
  "skipped_reasons": []
}
```

The 7 top-level keys returned by `evaluate_material_wear_graph` are
the stable Phase 8 contract: `version`, `family`, `graph`,
`graph_summary`, `binding_validation`, `uniform_noise`,
`skipped_reasons`. The validator omits a top-level `diagnostics` key
so the `FunctionValidator` wrapper treats the validator as passing.

---

## 4. Wear-mask type catalog

Five types are pinned in `WEAR_MASK_TYPES`. Each type has a canonical
binding pattern that the per-family default graph follows:

| Mask type | Default binding pattern | Industrial crate intensity | Use it for |
|---|---|---:|---|
| `convex_edge_wear` | `bound_edge_target = "body_shell.outer_edges"` | 0.28 | Paint chips and metal exposure on raised hard edges. |
| `concave_grime` | `bound_edge_target = "body_shell.recesses"` | 0.22 | Dirt and grease pooling in inset crevices. |
| `lower_contact_scuff` | `bound_node_id = "recipe.foot_rail_front"` / `"recipe.foot_rail_back"` (one mask per foot rail) | 0.35 | Scuffs and abrasions where the asset meets the ground plane. |
| `handle_touch_wear` | `bound_node_id = "recipe.handle_*"` (one mask per handle) | 0.18 | Polish-wear from repeated touch on grip surfaces. |
| `decal_wear` | `bound_node_id = "recipe.warning_decal_zone"` | 0.20 | Faded paint, lifted-edge effects on label / decal zones. |

A wear mask may set both `bound_node_id` and `bound_edge_target` if the
authoring intent applies to both (e.g. a decal wear mask anchored to a
node id but extending across the node's outer edges). The
`bound_to_both` count in `graph_summary` reports such cases.

---

## 5. Zone-type catalog

Two zone types are pinned in `ZONE_TYPES`:

| Zone type | Use it for |
|---|---|
| `base_material` | The dominant authored material covering most of the asset (paint, plastic, polished metal). |
| `underlayer` | The substrate revealed when wear masks expose the base material (raw metal, primer, foam). |

The industrial_crate default uses `painted_steel_body` (base) over
`dark_bare_metal` (underlayer) — convex_edge_wear and
lower_contact_scuff masks reveal the underlayer at edges and contact
points.

---

## 6. Industrial crate default graph

The per-family default for `industrial_crate` is the canonical
painted-steel example from spec Section 12.3:

| Slot | Entries |
|---|---|
| Materials | 1 × `painted_steel_body` (color `#4f5668`, roughness 0.62, metalness 0.0, bound to part `body`) |
| Underlayers | 1 × `dark_bare_metal` (color `#2a2a2a`, roughness 0.5, metalness 1.0, bound to part `body`) |
| Wear masks | 7 — one each for `convex_edge_wear`, `concave_grime`, `decal_wear`, plus two each for `lower_contact_scuff` (per foot) and `handle_touch_wear` (per handle) |

Mirrored masks (foot scuffs, handle touches) follow Phase 6's grammar
lowering naming convention: foot scuffs bind to
`recipe.foot_rail_front` / `recipe.foot_rail_back` (the recipe emits
two `solid.rail` ops along the bottom of the body), and handle
touches bind to `recipe.handle_l` / `recipe.handle_r`. That keeps
the binding one-to-one with the synthesized graph nodes.

Other families fall back to a `generic` empty graph (no materials, no
underlayers, no wear masks) and fire the uniform-noise warning by
construction. The fallback is intentional: Phase 8 deliberately does
not auto-author wear for unknown families. Phase 13 will add the
public syntax that lets authors opt their family in.

---

## 7. Mask-binding rules

### 7.1 Resolution

For every wear mask:

1. If `bound_node_id` is non-null, look it up in the union of
   `runtime["construction_graph"]["nodes"]` and the recipe-synthesized
   nodes published under `runtime["grammar_lowering"]
   ["synthesized_graph_nodes"]`. If the id is absent from both,
   `binding_validation.orphan_node_bindings` records the mask id and
   `all_node_bindings_resolved` flips to `false`.
2. `bound_edge_target` is a free-form structural anchor (e.g.
   `body_shell.outer_edges`); Phase 8 does not validate it because the
   structural-edge taxonomy is reserved for Phase 6+ extensions.
3. A mask with `bound_node_id == None` and `bound_edge_target != None`
   counts toward `bound_to_edge_targets`; both non-null counts toward
   `bound_to_both`. The per-family default graphs are validated at
   module import time by `_verify_default_graph_contracts`, which
   asserts every mask's `mask_type` is a member of `WEAR_MASK_TYPES`
   and every zone's `zone_type` is a member of `ZONE_TYPES`. The check
   does not currently reject masks where both binding fields are
   `None`; user-constructed graphs are not validated until Phase 13's
   public surface-program syntax adds `__post_init__` guards on
   `WearMask` and `MaterialZone` (per Phase 8's review carry-forward).

### 7.2 Resolved-vs-orphan accounting

`graph_summary` exposes three counts:

- `bound_to_construction_nodes` — masks with a non-null `bound_node_id`
  whose id resolves against the live + synthesized graph.
- `bound_to_edge_targets` — masks with a non-null `bound_edge_target`.
- `bound_to_both` — masks with both fields non-null AND the node
  resolves.

The uniform-noise score's `wear_binding_ratio` consumes the count of
masks with **at least one resolved binding** (node-bound resolved OR
edge-target present).

---

## 8. Uniform-noise scoring formula

The score is a deterministic function of zone diversity and wear
binding ratio, clamped to `[0.0, 1.0]`:

```
existing_surface_zone_count = len(runtime["surface"]["bundle"]["material_zones"])
                              if present else 0

zone_diversity_input        = max(graph.materials.count, existing_surface_zone_count)
zone_diversity              = min(1.0, zone_diversity_input / 3.0)

wear_binding_ratio          = bound_resolved / max(1, wear_mask_count)
                              where bound_resolved counts masks with at
                              least one resolved binding (node or edge)

uniform_noise_score         = clamp(
    1.0 - (0.4 * zone_diversity + 0.6 * wear_binding_ratio),
    0.0, 1.0,
)

is_uniform_noise            = uniform_noise_score >= 0.50
```

`is_uniform_noise == True` adds a warning under
`uniform_noise.warnings`. No `severity="error"` diagnostic is emitted —
Phase 8 is informational only.

### Reference values

| Fixture | zone_diversity | wear_binding_ratio | score | warns |
|---|---:|---:|---:|---|
| Generic / empty graph | 0.0 | 0.0 | 1.000 | yes |
| Uniform fixture (1 zone, no bindings) | 0.333 | 0.0 | 0.867 | yes |
| Industrial crate, surface_zone_count=1 (synthetic test fixture) | 0.333 | 1.000 | **0.267** | no |
| Industrial crate, live build (surface stage publishes 3 material zones) | 1.000 | 1.000 | **0.000** | no |
| Clean fixture (3+ zones, all masks bound) | 1.000 | 1.000 | 0.000 | no |

The `industrial_crate` baseline lands at 0.000 in the live pipeline
because the surface stage publishes 3 material zones for painted
steel + dark bare metal + a third pass — `zone_diversity` is computed
as `min(1.0, max(graph.materials.count, surface_zone_count) / 3.0)`,
so the live surface output saturates the score even with a single
recipe-graph material. The unit test
`test_industrial_crate_baseline_score_lands_at_documented_value`
deliberately uses `surface_zone_count=1` to exercise the mid-tier
formula path; both scenarios resolve all 7 wear-mask bindings and
neither fires the uniform-noise warning. Phase 14 golden examples
can demonstrate that hand-authored multi-zone stories keep the live
score at 0.000 and the layer remains warning-free.

---

## 9. Skipped-evidence contract

When `runtime["highlow_relation"]["bake_map_count_present"]` is less
than 4, `skipped_reasons` records:

```json
{"tool": "bake_runtime", "reason": "incomplete_bake_maps"}
```

Phase 8 does not block on incomplete bake evidence — it surfaces the
gap so a downstream tool (or a reviewer) can decide whether to
re-bake. Per `AGENTS.md`, no bake outputs are invented.

---

## 10. Pipeline placement

The validator is registered in `lathe/core/stages/validate.py`'s
`_PIPELINE` immediately after `highlow_relation` and before
`geometry_integrity`:

```
design_brief -> construction_graph -> grammar_lowering -> family_grammar
  -> gameplay_tags -> semantic_quality -> visual_quality -> flow_quality
  -> highlow_relation -> material_wear_graph -> geometry_integrity
  -> quality_diagnostics -> urdf_validation
```

The validator carries `weight=0.0` and `stage_dependencies=["surface"]`.
The pipeline composition layer publishes each validator's evidence
into `runtime[validator.name]` (`lathe/validators/composition.py:287-291`),
so downstream phases consume `runtime["material_wear_graph"]` directly.

The validate stage step extracts the result, mirrors it onto
`executor.runtime["material_wear_graph"]`, and adds the top-level
`material_wear_graph` key to `report.json`. The validator never
contributes to the aggregate certification score (`weight=0.0`) and
never produces blocking diagnostics — Phase 8 is informational
evidence only.

---

## 11. Forward references

| Phase | Consumes | Use |
|---|---|---|
| Phase 9 — Preview / evidence upgrade | `graph_summary` + `uniform_noise.score` | Surfaces material/wear evidence on the per-asset preview sheet so reviewers see the storytelling at a glance. |
| Phase 11 — References / moodboard | `materials` + `underlayers` per family | Reference fixtures may supply alternative material zones (e.g. weathered_steel, painted_alloy) the recipe can opt into. |
| Phase 13 — Public syntax | `MaterialWearGraph` schema | A new `.lth` block (e.g. `material_graph { ... }`) lowers user-authored materials, underlayers, and wear masks into a custom `MaterialWearGraph` that replaces the per-family default. |
| Phase 14 — Golden examples | All Phase 8 evidence | Hand-authored material stories on golden assets demonstrate the layer's intent. The `is_uniform_noise == False` invariant becomes part of the golden contract. |

The Phase 1 `quality_diagnostics.metrics` set stays at 6 metrics
(carry-forward from Phase 7). Phase 8 does not add a 7th — uniform
noise is surfaced on the dedicated `material_wear_graph` key instead.

---

## 12. Verification

```bash
# Per-mask-type and per-zone-type unit tests + scoring
python -m pytest tests/unit/test_asset_quality_material_wear_graph.py -v

# Phase 1-7 regressions still green
python -m pytest tests/unit/test_asset_quality_diagnostics.py \
                  tests/unit/test_asset_quality_design_brief.py \
                  tests/unit/test_asset_quality_family_grammar.py \
                  tests/unit/test_asset_quality_construction_graph.py \
                  tests/unit/test_shape_ir_v2.py \
                  tests/unit/test_asset_quality_grammar_lowering.py \
                  tests/unit/test_asset_quality_highlow_relation.py \
                  tests/unit/test_asset_quality_baseline_report_shape.py \
                  tests/unit/test_marker_inventory.py \
                  tests/unit/test_test_hygiene.py -q

# Smoke import
python -c "from lathe.asset_quality.material_wear_graph import MATERIAL_WEAR_VERSION, WEAR_MASK_TYPES, ZONE_TYPES; print(MATERIAL_WEAR_VERSION, len(WEAR_MASK_TYPES), len(ZONE_TYPES))"

# v1 still builds
python -m lathe.cli check examples/industrial_crate.lth

# End-to-end build with material_wear_graph in report
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
    --out .tmp_tests/baseline_industrial_crate --deterministic

# Inspect: top-level "material_wear_graph" key exists with version,
# graph, graph_summary, binding_validation, uniform_noise, skipped_reasons.
python -c "import json; r=json.load(open('.tmp_tests/baseline_industrial_crate/industrial_crate/stages/validate/report.json')); print(len(r), r['material_wear_graph']['uniform_noise']['uniform_noise_score'])"
```
