# Grammar Lowering v1

> **Phase 6 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the deterministic recipe layer that lowers a family grammar
> into ShapeIR v2 operations and synthesized semantic-construction-graph
> nodes — without changing public `.lth` syntax or the v1 shape bundle.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 7
> (DesignBrief / family alignment),
> `docs/asset-quality/improvement-tasklist.md` Section 6 (Phase 6 task list),
> `docs/asset-quality/family-grammar-v1.md` (Phase 3 — the family
> requirements this layer lowers),
> `docs/asset-quality/semantic-construction-graph.md` (Phase 4 — the
> graph slot the recipe synthesizes nodes for),
> `docs/architecture/shape-ir-v2.md` (Phase 5 — the v2 op model the
> recipe emits and the v1 adapter it uses).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/grammar_lowering.py`
**Validator name:** `grammar_lowering`
**Payload version field:** `grammar_lowering_v1`

---

## 1. Overview

The grammar-lowering layer is the first concrete consumer of Phases 3
(family grammar), 4 (construction graph), and 5 (ShapeIR v2). Each
recipe is a pure function from `(brief, parts, graph_nodes)` to a
`RecipeResult` carrying:

- a deterministic `ShapeProgram` of v2 ops, each tagged with a stable
  `purpose` string keyed off the triggering grammar requirement;
- a tuple of synthesized graph-node dicts compatible with Phase 4's
  construction graph.

Phase 6 ships one recipe — `industrial_crate` — covering all 10 family
grammar requirements. Other families fall back to an empty program and
zero synthesized nodes.

### What this layer does

- Defines `RecipeResult`, an immutable dataclass that records the v2
  program plus the synthesized graph nodes for one family.
- Encodes the canonical `industrial_crate` recipe — 13 v2 ops + 19
  synthesized graph nodes.
- Surfaces the v1-adapter result (Phase 5) under a nested
  `v1_lowering` evidence block so consumers can see which ops were
  lowered to v1 records and which were emitted as
  `no_v1_equivalent` for forward phases.
- Publishes the result on `runtime["grammar_lowering"]` and emits an
  additive `grammar_lowering` key on the validate-stage report (the
  20th top-level key, on top of the 19 from Phases 0 through 5).

### What this layer does *not* do

- Touch `.lth` source syntax. The Phase 6 contract is internal-only.
- Modify, rename, or remove any existing report field.
- Touch `lathe.shape.intent_mesh_handoff_v1`, `lathe/shape_backend.py`,
  `lathe/shape_providers.py`, or `lathe/shape_ir.py`.
- Mutate `runtime["construction_graph"]["nodes"]`. The recipe's
  synthesized graph nodes live under
  `runtime["grammar_lowering"]["synthesized_graph_nodes"]`. The
  family-grammar validator merges them into a read-only evidence view,
  so live coverage improves without rewriting the construction graph
  bundle.
- Generate real high-poly geometry. v2 ops are an authoring layer; the
  `solid.box` body and two `solid.rail` feet lower to v1 primitives at
  Phase 6. The other 10 ops remain as semantic authoring intent until a
  later construction/high-poly producer makes them real.
- Block certification. Like Phases 1 through 5, the validator is
  registered with `weight=0.0` and emits no top-level `diagnostics`
  field.

---

## 2. Industrial-crate recipe table

The recipe lowers all 10 industrial-crate grammar requirements in
declaration order. Each row in the table maps one requirement to the
v2 ops it emits and the synthesized graph nodes it adds.

| # | Requirement | v2 ops | Synthesized graph nodes | Notes |
|---:|---|---|---|---|
| 1 | `body_shell` | 1x `solid.box` (92cm x 58cm x 64cm) | 1x `primary_volume` (`recipe.body_shell`) | Spec §7.3 canonical industrial-crate dimensions. Lowers to a v1 `box`. |
| 2 | `lid_seam` | 1x `op.inset` (depth=0.4cm) + 1x `op.cut_panel_line` | 1x `panel` (`recipe.lid_seam`) | Inset followed by a panel cut produces the visible top-band lid seam. |
| 3 | `corner_guards` | 1x `op.corner_guard_set` (size=4cm, count=8) | 8x `guard` (`recipe.corner_guard_0` ... `recipe.corner_guard_7`) | One node per body corner so the construction graph reflects per-corner authoring intent. |
| 4 | `latch_or_latch_plate` | 1x `op.mount_plate` (8cm x 6cm) | 1x `inset` (`recipe.latch_plate`) | Mount plate on the body's front face; node tagged `inset` so latch sits in a recessed surface. |
| 5 | `recessed_or_bracketed_handles` | 2x `op.socket` (mount=`recessed_bracket`) | 2x `handle` (`recipe.handle_l`, `recipe.handle_r`) | Two recessed brackets — left and right — match the canonical part-list naming convention. |
| 6 | `foot_rails_or_feet` | 2x `solid.rail` (60cm length, 4cm profile) | 2x `rail` (`recipe.foot_rail_front`, `recipe.foot_rail_back`) | Two rails span the bottom of the body and lower to v1 box approximations. |
| 7 | `trim_bands` | 1x `op.trim_band` (width=2cm) | 1x `trim` (`recipe.trim_band_mid`) | Single mid-plane band breaks up the body shell. |
| 8 | `fasteners` | 1x `op.fastener_grid` (rows=2, cols=2, spacing=8cm) | 1x `fastener` (`recipe.fastener_grid_front`) | A 2x2 grid on the front face. |
| 9 | `warning_or_decal_zones` | 1x `op.repeat` (count=1, axis=z) | 1x `decal_zone` (`recipe.warning_decal_zone`) | ShapeIR v2 has no first-class decal-zone op at Phase 5; `op.repeat` carries the intent (one repetition along z) and is paired with the graph node so Phase 8's material/wear graph can locate the zone. A future ShapeIR layer may add `op.decal_zone` and replace this slot. |
| 10 | `edge_wear_masks` | 1x `op.chip_edges` (amount=0.28) | 1x `wear_zone` (`recipe.edge_wear_zone`) | Drives Phase 8's material/wear graph and matches the design brief's `wear = "medium_edge_wear"` default. |

**Totals:** 13 v2 ops, 19 synthesized graph nodes.

---

## 3. Payload schema

The validator returns this additive payload, which is exposed under
`report["grammar_lowering"]` on the validate-stage report:

```json
{
  "version": "grammar_lowering_v1",
  "family": "industrial_crate",
  "shape_program": {
    "version": "shape_ir_v2",
    "asset_name": "industrial_crate",
    "family": "industrial_crate",
    "ops": [
      {
        "op": "solid.box",
        "target": "body",
        "parameters": {"width_cm": 92.0, "height_cm": 58.0, "depth_cm": 64.0},
        "purpose": "body_shell.primary_volume"
      },
      {
        "op": "op.inset",
        "target": "body.top_band",
        "parameters": {"depth_cm": 0.4},
        "purpose": "lid_seam.inset"
      }
    ]
  },
  "shape_program_summary": {
    "op_count": 13,
    "ops_by_family": {
      "solid_ops": 3,
      "boolean_ops": 2,
      "edge_ops": 0,
      "repetition_ops": 4,
      "integration_ops": 3,
      "wear_ops": 1
    },
    "ops_by_requirement": {
      "body_shell": 1,
      "corner_guard_set": 1,
      "edge_wear_masks": 1,
      "fasteners": 1,
      "foot_rails": 2,
      "handles": 2,
      "latch_plate": 1,
      "lid_seam": 2,
      "trim_bands": 1,
      "warning_decal_zone": 1
    }
  },
  "synthesized_graph_nodes": [
    {"node_id": "recipe.body_shell", "node_type": "primary_volume", "attributes": {}},
    {"node_id": "recipe.lid_seam", "node_type": "panel", "attributes": {}}
  ],
  "synthesized_node_count": 19,
  "v1_lowering": {
    "v1_record_count": 3,
    "diagnostics": [
      {"code": "no_v1_equivalent", "op": "op.inset", "reason": "..."}
    ],
    "unsupported_ops": []
  }
}
```

### 3.1 Payload field shape

| Field | Type | Notes |
|---|---|---|
| `version` | string | Always `"grammar_lowering_v1"`. |
| `family` | string | The family the recipe applied to. `"generic"` when the design brief is missing. |
| `shape_program` | object | The Phase 5 `ShapeProgram` dict (`version`, `asset_name`, `family`, `ops`). |
| `shape_program_summary.op_count` | int | Always equals `len(shape_program.ops)`. |
| `shape_program_summary.ops_by_family` | object | Counts of ops by Phase 5 op family (six keys: `solid_ops`, `boolean_ops`, `edge_ops`, `repetition_ops`, `integration_ops`, `wear_ops`). |
| `shape_program_summary.ops_by_requirement` | object | Counts of ops by triggering requirement, keyed off the leading token of each op's `purpose` (`<requirement>.<suffix>`). |
| `synthesized_graph_nodes` | array | Construction-graph node dicts compatible with Phase 4 (`node_id`, `node_type`, `attributes`). |
| `synthesized_node_count` | int | `len(synthesized_graph_nodes)`. |
| `v1_lowering.v1_record_count` | int | Number of v1 records emitted by Phase 5's adapter (3 for the body box plus two rail approximations). |
| `v1_lowering.diagnostics` | array | Per-op `no_v1_equivalent` diagnostics for the 10 ops not yet covered by `_V1_LOWERERS`. |
| `v1_lowering.unsupported_ops` | array | Empty for the recipe (every op is a member of `ALL_OPS`). |

No top-level `diagnostics` field — like Phases 1 through 5, this
validator is informational only and never blocks certification.

---

## 4. v2-to-v1 adapter behavior on the recipe

Phase 5's `lower_to_v1` walks the recipe's 13-op program and:

- emits **3 v1 records** for the `solid.box` body and the two
  `solid.rail` foot rails (rail records are v1 box approximations
  tagged `rail_approx`);
- emits a **`no_v1_equivalent`** diagnostic for each of the other 10 ops
  (`op.inset`, `op.cut_panel_line`, `op.corner_guard_set`,
  `op.mount_plate`, `op.socket` x2, `op.trim_band`,
  `op.fastener_grid`, `op.repeat`, `op.chip_edges`).

`v1_lowering.unsupported_ops` is empty: every recipe op is a member of
`ALL_OPS`. The `no_v1_equivalent` diagnostics are evidence for
forward phases; a later construction/high-poly producer turns those v2
ops into real construction.

---

## 5. Coverage-lift mechanics

The Phase 4 family-grammar validator detects requirements via:

1. parts-list substring match -> `"satisfied"`;
2. otherwise, construction-graph `node_type` match -> `"partial"`;
3. otherwise -> `"missing"`.

The recipe's synthesized graph nodes use `node_type` values drawn from
Phase 4's `NODE_TYPES` frozenset (`primary_volume`, `panel`, `guard`,
`inset`, `handle`, `rail`, `trim`, `fastener`, `decal_zone`,
`wear_zone`). When published under `runtime["grammar_lowering"]`, these nodes
elevate **five** baseline-missing requirements to `"partial"`:

- `corner_guards` (via `guard` nodes);
- `trim_bands` (via `trim` node);
- `fasteners` (via `fastener` node);
- `warning_or_decal_zones` (via `decal_zone` node);
- `edge_wear_masks` (via `wear_zone` node).

`lid_seam` also elevates from `missing` to `partial`. The
`lid_seam` requirement's `graph_node_types` allowlist accepts `panel`
(per Phase 4), and the recipe synthesizes a `panel` node
(`recipe.lid_seam`). The baseline parts list contains no part matching
the `lid` token, so without the recipe the status would stay
`missing`; with the grammar-lowered `panel` node Phase 4's elevation logic
flips it to `partial`.

**Predicted coverage with grammar-lowered nodes:** 0.40 baseline ->
**0.70 merged** (4 satisfied + 6 partial = 4.0 + 3.0 / 10 = 0.70).

The verification suite's `test_recipe_synthesized_nodes_lift_family_grammar_coverage`
asserts this exact lift. The live pipeline runs `grammar_lowering`
before `family_grammar`, and `family_grammar` merges these nodes into
its read-only evidence view while leaving the construction graph bundle
unchanged.

---

## 6. Pipeline placement

The validator is registered in `lathe/core/stages/validate.py:_PIPELINE`
**immediately after** `construction_graph` and **before**
`family_grammar`, all with `stage_dependencies=[]` and
`weight=0.0`. Topological order plus FIFO tie-break preserves the
registration-order placement, so:

1. `design_brief` runs first and publishes the inferred family.
2. `construction_graph` runs second and publishes the parts-derived
   graph.
3. `grammar_lowering` runs third, reads the brief + parts + current
   graph, and publishes the recipe result.
4. `family_grammar` runs fourth, reads the brief + graph plus the
   grammar-lowered synthesized nodes, and publishes the lifted coverage
   result.
5. `quality_diagnostics` runs later (after `shape`/`topology`/`uv`/
   `surface` are present) and can read the lifted
   `family_grammar.coverage` metric. Phase 6 does not add a new metric
   to `quality_diagnostics`.

The pipeline composition layer (`lathe/validators/composition.py:287-291`)
publishes each validator's evidence into `runtime[validator.name]`,
so downstream phases can consume `runtime["grammar_lowering"]`
directly without re-deriving anything.

The validate stage step (`lathe/core/stages/validate.py:run`) extracts
the result, mirrors it onto `executor.runtime["grammar_lowering"]`,
and adds a top-level `grammar_lowering` key to `report.json`. The
validator never contributes to the aggregate certification score
(`weight=0.0`) and never produces blocking diagnostics — Phase 6 is
informational evidence only.

---

## 7. Forward references

| Phase | Consumes | Use |
|---|---|---|
| Phase 8+ — Construction/high-poly producer | `shape_program.ops` + `v1_lowering.diagnostics` | Turns each `no_v1_equivalent` op into a real construction step. The recipe defines *what* should exist; the producer makes it *real*. |
| Phase 8 — Material/Wear graph | `synthesized_graph_nodes` (filtered by `node_type == "wear_zone"` / `"decal_zone"` / `"material_zone"`) | Drives wear-mask authoring intent and per-zone material policies from the recipe's wear/decal nodes. |
| Phase 11 — References | `shape_program_summary.ops_by_requirement` | Filters reference selection to fixtures that exemplify each grammar requirement covered by the recipe. |
| Phase 12 — Kit | the entire recipe layer | Each kit asset declares which recipe variants it satisfies for assembly-level coverage. |
| Phase 13 — Public syntax | `industrial_crate_recipe` signature | A new `.lth` syntax (e.g. `recipe override { ... }`) lowers user-authored op overrides into a custom `RecipeResult` that replaces the per-family default. |

The `industrial_crate_recipe` function takes `brief`, `parts`, and
`graph_nodes` parameters today but does not consume them — the recipe
is currently a deterministic function of family alone. The signature
is reserved for forward-compat: when Phase 13's public syntax lands,
or when a future recipe variant needs to read the brief or scan the
parts list to disambiguate, the parameters are already in place. The
contract is locked by
`test_recipe_brief_parts_and_graph_arguments_are_currently_ignored`
so a future change that introduces input-dependence without a
deliberate opt-in will fail loudly.

---

## 8. Verification

```bash
# Per-recipe and per-requirement unit tests
python -m pytest tests/unit/test_asset_quality_grammar_lowering.py -v

# Phase 1-5 regressions still green
python -m pytest tests/unit/test_asset_quality_diagnostics.py \
                  tests/unit/test_asset_quality_design_brief.py \
                  tests/unit/test_asset_quality_family_grammar.py \
                  tests/unit/test_asset_quality_construction_graph.py \
                  tests/unit/test_asset_quality_baseline_report_shape.py \
                  tests/unit/test_shape_ir_v2.py -q

# Targeted regression — validator pipeline + report fields + marker policy
python -m pytest tests/unit/test_validators_visual_surface_fast.py \
                  tests/unit/test_validate_stage_report.py \
                  tests/unit/test_reports.py \
                  tests/unit/test_reports_extended.py \
                  tests/unit/test_quality_gate_wiring.py \
                  tests/unit/test_marker_inventory.py -q

# Smoke import — confirms the module loads under the package
python -c "from lathe.asset_quality.grammar_lowering import GRAMMAR_LOWERING_VERSION, industrial_crate_recipe; print(GRAMMAR_LOWERING_VERSION)"

# v1 still builds clean
python -m lathe.cli check examples/industrial_crate.lth

# End-to-end build — confirms `grammar_lowering` lands in report.json
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
  --out .tmp_tests/baseline_industrial_crate --deterministic

# Inspect: .tmp_tests/baseline_industrial_crate/industrial_crate/stages/validate/report.json
# Top-level "grammar_lowering" key exists with version, family, shape_program,
# shape_program_summary, synthesized_graph_nodes, synthesized_node_count, v1_lowering.
```
