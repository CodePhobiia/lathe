# Semantic Construction Graph v1

> **Phase 4 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the internal `SemanticConstructionGraph` representation that
> records the construction relationships (nodes and edges) implied by an
> asset's intent and runtime data — without changing the public `.lth`
> syntax.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 7
> (DesignBrief / family alignment),
> `docs/asset-quality/improvement-tasklist.md` Section 4 (Phase 4 task list),
> `docs/asset-quality/family-grammar-v1.md` (Phase 3 — receives the graph
> as fallback evidence to elevate `missing` to `partial`),
> `docs/asset-quality/design-brief-ir.md` (Phase 2 — provides the
> `family` field consumed by the graph),
> `docs/asset-quality/quality-diagnostics-v1.md` (Phase 1 — the
> `family_grammar_coverage` metric reflects graph-elevated coverage).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/construction_graph.py`
**Validator name:** `construction_graph`
**Payload version field:** `construction_graph_v1`

---

## 1. Overview

`SemanticConstructionGraph` is an internal IR that records the
construction nodes and edges implied by an asset's parts list and
runtime data. It is published to `runtime["construction_graph"]` and
emitted as an additive `construction_graph` key on the validate-stage
report.

### What this layer does

- Defines three immutable dataclasses: `ConstructionNode`,
  `ConstructionEdge`, `SemanticConstructionGraph`.
- Encodes the canonical 15 node types and 10 edge types so future
  phases (ShapeIR v2, grammar lowering, material/wear graph) write
  into a stable shape.
- Performs deterministic best-effort extraction from
  `asset["intent"]["parts"]` (case-insensitive substring map) plus
  optional structural hints from
  `runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]`.
- Reads `runtime["design_brief"]["brief"]["family"]` for the graph's
  `family` slot (falls back to `"generic"` when absent).
- Publishes the result to `runtime["construction_graph"]` so the
  Phase 3 `family_grammar` validator can consume it as additive
  fallback evidence.

### What this layer does *not* do

- Touch `.lth` source syntax. The Phase 4 contract is internal-only.
- Modify, rename, or remove any existing report field — only the new
  additive `construction_graph` key is added.
- Touch `lathe.shape.intent_mesh_handoff_v1`.
- Run any geometry, mesh, or ShapeIR operations. The graph records
  *intent* relationships; lowering them into geometry is Phase 6's
  responsibility.
- Populate node `attributes` with operation hints — that is Phase 5
  (ShapeIR v2 adapter)'s responsibility. The field is reserved here so
  the JSON shape stays stable across the upgrade.
- Emit anything beyond the conservative `attached_to` and `mirrors`
  edge set — richer edges (`inset_into`, `wraps_around`, `cuts`, etc.)
  are reserved for Phase 6's grammar lowering.
- Block certification. Like Phases 1, 2 and 3, the validator is
  registered with `weight=0.0` and returns no `diagnostics` field.

---

## 2. Payload schema

The validator returns this additive payload, which is exposed under
`report["construction_graph"]` on the validate-stage report:

```json
{
  "version": "construction_graph_v1",
  "family": "industrial_crate",
  "asset_name": "industrial_crate",
  "nodes": [
    {"node_id": "body", "node_type": "primary_volume", "attributes": {}},
    {"node_id": "latch_plate", "node_type": "inset", "attributes": {}},
    {"node_id": "handle_l", "node_type": "handle", "attributes": {}},
    {"node_id": "handle_r", "node_type": "handle", "attributes": {}},
    {"node_id": "foot_l", "node_type": "mount", "attributes": {}},
    {"node_id": "foot_r", "node_type": "mount", "attributes": {}}
  ],
  "edges": [
    {"source_id": "latch_plate", "target_id": "body", "edge_type": "attached_to", "attributes": {}},
    {"source_id": "handle_l", "target_id": "body", "edge_type": "attached_to", "attributes": {}},
    {"source_id": "handle_r", "target_id": "body", "edge_type": "attached_to", "attributes": {}},
    {"source_id": "foot_l", "target_id": "body", "edge_type": "attached_to", "attributes": {}},
    {"source_id": "foot_r", "target_id": "body", "edge_type": "attached_to", "attributes": {}},
    {"source_id": "foot_l", "target_id": "foot_r", "edge_type": "mirrors", "attributes": {}},
    {"source_id": "handle_l", "target_id": "handle_r", "edge_type": "mirrors", "attributes": {}}
  ],
  "node_count": 6,
  "edge_count": 7,
  "node_types_present": ["handle", "inset", "mount", "primary_volume"],
  "edge_types_present": ["attached_to", "mirrors"]
}
```

The graph is always complete: every node and edge field is populated
deterministically. `attributes` is reserved as an open `dict[str, Any]`
so Phase 5+ can add operation hints, dimensions, and bevel settings
without breaking the JSON shape.

### 2.1 Entry shapes

| Field | Type | Notes |
|---|---|---|
| `node_id` | string | Stable identifier (typically the part name from `asset["intent"]["parts"]`). |
| `node_type` | string | One of the 15 canonical node types — see Section 3. |
| `source_id` / `target_id` | string | References to `node_id` values. |
| `edge_type` | string | One of the 10 canonical edge types — see Section 4. |
| `attributes` | object | Open-ended; empty at Phase 4. Phase 5 (ShapeIR v2) populates. |

---

## 3. Node types

`NODE_TYPES` is a `frozenset[str]` with exactly 15 members. Future
phases must use one of these tokens.

| # | Token | Description |
|---:|---|---|
| 1 | `primary_volume` | The structural body of the asset (e.g. crate shell, door leaf, cabinet frame). |
| 2 | `frame` | A surrounding frame element that wraps a panel or volume. |
| 3 | `panel` | A flat or near-flat surface element (lid panels, door panels, sheet metal). Default fallback for unrecognised part names. |
| 4 | `inset` | A recessed element seated into a parent surface (latch plates, recessed wells, button pads). |
| 5 | `trim` | A thin band or strip running along the surface (trim bands, edge pieces). |
| 6 | `guard` | A reinforcement piece protecting an exposed edge or corner (corner guards, edge protectors). |
| 7 | `rail` | A long support running along the asset (foot rails, mounting rails, conveyor rails). |
| 8 | `socket` | A receptacle where another element plugs in (mount sockets, attachment receivers). |
| 9 | `mount` | A bracket or foot that grounds the asset against another surface (feet, brackets, mounting plates). |
| 10 | `handle` | A grip or pull element used for manipulation (door handles, drawer pulls). |
| 11 | `hinge` | A pivot or rotational joint between two structural elements. |
| 12 | `fastener` | A discrete fastening element (bolts, rivets, screws). |
| 13 | `decal_zone` | A surface region reserved for a decal, label, or warning text. |
| 14 | `wear_zone` | A surface region annotated for edge-wear or damage masks. |
| 15 | `material_zone` | A region annotated with a distinct material binding. |

---

## 4. Edge types

`EDGE_TYPES` is a `frozenset[str]` with exactly 10 members. Phase 4
emits only `attached_to` and `mirrors` deterministically; the remaining
edge types are reserved for Phase 6's grammar lowering.

| # | Token | Description | Phase 4 emits? |
|---:|---|---|---|
| 1 | `attached_to` | A node is attached to a parent node (typically the `primary_volume`). | yes |
| 2 | `inset_into` | A node is set into a parent surface, leaving a flush or recessed face. | reserved (Phase 6) |
| 3 | `wraps_around` | A node wraps around an edge or corner of another node. | reserved (Phase 6) |
| 4 | `mirrors` | Two nodes form a mirrored pair (typically `_l` / `_r` suffixes). | yes |
| 5 | `aligned_with` | Two nodes share an axis or surface plane. | reserved (Phase 6) |
| 6 | `supports` | A node bears the weight of another node (rails, mounts). | reserved (Phase 6) |
| 7 | `cuts` | A node subtracts material from another node (boolean cut, slot). | reserved (Phase 6) |
| 8 | `contains` | A node spatially contains another node (container/contained). | reserved (Phase 6) |
| 9 | `wears_on` | A wear zone is bound to an edge or surface of another node. | reserved (Phase 6) |
| 10 | `material_bound_to` | A material zone is bound to a region of another node. | reserved (Phase 6) |

---

## 5. Best-effort extraction rules

### 5.1 Node-id collection

Every entry in `asset["intent"]["parts"]` becomes a node, in
declaration order. The `node_id` is the original part name (case
preserved). Then, optional structural hints from
`runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]["nodes"]`
(or `…asset_graph["parts"]`) are appended for any id not already
covered. Missing/malformed structures are tolerated and never raise.

### 5.2 Substring-to-node-type map

Detection is case-insensitive and runs in declaration order; the first
matching token wins. If no token matches, the part falls back to the
`panel` node type.

| Substring tokens | Node type |
|---|---|
| `body` | `primary_volume` |
| `lid` | `panel` |
| `frame` | `frame` |
| `panel` | `panel` |
| `trim`, `band` | `trim` |
| `corner_guard`, `corner`, `guard` | `guard` |
| `rail` | `rail` |
| `socket` | `socket` |
| `mount`, `bracket` | `mount` |
| `handle` | `handle` |
| `hinge` | `hinge` |
| `fastener`, `bolt`, `rivet`, `screw` | `fastener` |
| `decal`, `label`, `warning` | `decal_zone` |
| `wear` | `wear_zone` |
| `material` | `material_zone` |
| `latch` | `inset` |
| `foot`, `feet` | `mount` |
| (default) | `panel` |

### 5.3 Edge synthesis

Phase 4 emits two deterministic edge classes:

- **`attached_to`** — for every non-`primary_volume` node, an
  `attached_to` edge is added pointing to the *first* node whose type
  is `primary_volume`. If no `primary_volume` node exists, no
  `attached_to` edges are emitted.
- **`mirrors`** — when two or more nodes share a base name with `_l` /
  `_r` suffixes (e.g. `handle_l` and `handle_r`), a `mirrors` edge is
  added between every alphabetically-ordered pair. Long suffixes such
  as `_left` / `_right` do **not** trigger mirror detection — the rest
  of the toolchain uses the canonical short suffixes.

All other edge types are reserved for Phase 6 grammar lowering.

---

## 6. Graph-aware family grammar elevation

The Phase 3 `family_grammar` validator is updated to consume
`runtime["construction_graph"]["nodes"]` as additive fallback evidence.
Each `FamilyRequirement` now also carries a `graph_node_types` tuple of
allowlisted node-type tokens.

Detection precedence:

1. **Parts match** -> status `"satisfied"`, evidence
   `matched_parts`.
2. **Otherwise, graph-only match** (any graph node has `node_type` in
   the requirement's `graph_node_types`) -> status `"partial"`,
   evidence includes both `matched_parts` (empty) and
   `matched_graph_nodes`.
3. **Otherwise** -> status `"missing"`.

Parts evidence dominates because parts represent explicit authoring
intent; graph evidence is derived. When `runtime["construction_graph"]`
is absent or malformed, the graph-elevation path is skipped entirely
and Phase 3 behaviour is preserved exactly.

### 6.1 Industrial-crate requirement allowlists

| Requirement | `graph_node_types` |
|---|---|
| `body_shell` | `("primary_volume",)` |
| `lid_seam` | `("panel",)` |
| `corner_guards` | `("guard",)` |
| `latch_or_latch_plate` | `("inset",)` |
| `recessed_or_bracketed_handles` | `("handle",)` |
| `foot_rails_or_feet` | `("mount", "rail")` |
| `trim_bands` | `("trim",)` |
| `fasteners` | `("fastener",)` |
| `warning_or_decal_zones` | `("decal_zone",)` |
| `edge_wear_masks` | `("wear_zone",)` |

### 6.2 Industrial-crate baseline coverage with graph

For the hero `examples/industrial_crate.lth` parts list
`[body, latch_plate, handle_l, handle_r, foot_l, foot_r]`, the
construction graph extracts node types `{primary_volume, inset, handle,
mount}`. Those are the same node types the parts list already covers,
so no requirement is elevated from `missing` to `partial` and the
**coverage stays 0.40** — the graph wiring is informational at the
baseline. Future asset authoring (e.g. adding a `corner_guard_a` node
to the scaffold_report graph without adding it to the parts list) will
trigger graph-only elevation.

---

## 7. Pipeline placement

The validator is registered in
`lathe/core/stages/validate.py:_PIPELINE` **immediately after**
`design_brief` and **before** `family_grammar`, all three with
`stage_dependencies=[]` and `weight=0.0`. Because `ValidatorPipeline`
orders by stage dependencies and breaks ties on registration order
(`lathe/validators/composition.py:_topological_order`), this guarantees:

1. `design_brief` runs first and publishes the inferred family.
2. `construction_graph` runs second, reads the brief, and publishes the
   graph result.
3. `family_grammar` runs third, reads both the brief and the graph,
   and publishes the coverage result.
4. `quality_diagnostics` runs later (after `shape`/`topology`/`uv`/
   `surface` are present) and reads the family-grammar coverage.

Final pipeline order:

```
design_brief -> construction_graph -> family_grammar -> gameplay_tags ->
semantic_quality -> visual_quality -> flow_quality -> geometry_integrity ->
quality_diagnostics -> urdf_validation
```

`gameplay_tags` is hoisted between `family_grammar` and `semantic_quality`
by the topological orderer because it also declares
`stage_dependencies=[]` (and was registered after `family_grammar` in
`_PIPELINE`). The interleaving is incidental and predates Phase 4 — it
does not affect the asset-quality flow because `gameplay_tags` neither
reads `runtime["construction_graph"]` nor publishes evidence the family
grammar consumes.

The pipeline composition layer
(`lathe/validators/composition.py:287-291`) publishes each validator's
evidence into `runtime[validator.name]`, so downstream phases consume
`runtime["construction_graph"]` directly.

The validate stage step (`lathe/core/stages/validate.py:run`) extracts
the result, mirrors it onto `executor.runtime["construction_graph"]`,
and adds a top-level `construction_graph` key to `report.json`. The
validator never contributes to the aggregate certification score
(`weight=0.0`) and never produces blocking diagnostics — Phase 4 is
informational evidence only.

---

## 8. Forward references

| Phase | Consumes | Use |
|---|---|---|
| Phase 5 — ShapeIR v2 | `nodes[*].attributes` | Populates per-node operation hints, dimensions, bevel settings, and ShapeIR v2 op references. |
| Phase 6 — Grammar lowering | the entire graph | Lowers grammar requirements into actual ShapeIR v2 operations and emits richer `inset_into`, `wraps_around`, `cuts`, `aligned_with`, `supports` edges. |
| Phase 7 — High-poly producer | `nodes[*].node_type == "decal_zone"` / `"wear_zone"` / `"material_zone"` | Decides which surface zones receive bake masks vs. authored high-poly geometry. |
| Phase 8 — Material/Wear graph | `nodes[*].node_type == "wear_zone"` / `"material_zone"`, `edges[*].edge_type == "wears_on"` / `"material_bound_to"` | Drives wear-mask authoring intent and per-zone material policies. |
| Phase 11 — References | `family`, `node_types_present` | Filters reference selection to fixtures that exemplify the requested family + node-type signature. |
| Phase 12 — Kit | the entire graph | Each kit asset declares its node and edge contributions for assembly-level coverage. |

---

## 9. Verification

```bash
# Per-node, per-edge, per-payload-shape, and graph-extraction tests
python -m pytest tests/unit/test_asset_quality_construction_graph.py -v

# Phase 3 still green + new graph-elevation tests
python -m pytest tests/unit/test_asset_quality_family_grammar.py -q

# Phase 1 + Phase 2 still green (regression check)
python -m pytest tests/unit/test_asset_quality_design_brief.py \
                 tests/unit/test_asset_quality_diagnostics.py -q

# Baseline contract (top-level keys preserved + additive growth allowed)
python -m pytest tests/unit/test_asset_quality_baseline_report_shape.py -q

# Targeted regression — validator pipeline + report fields + marker policy
python -m pytest tests/unit/test_validators_visual_surface_fast.py \
                 tests/unit/test_validate_stage_report.py \
                 tests/unit/test_reports.py \
                 tests/unit/test_reports_extended.py \
                 tests/unit/test_quality_gate_wiring.py \
                 tests/unit/test_marker_inventory.py -q

# Smoke import — confirms the module loads under the package
python -c "from lathe.asset_quality.construction_graph import CONSTRUCTION_GRAPH_VERSION, NODE_TYPES, EDGE_TYPES; print(CONSTRUCTION_GRAPH_VERSION, len(NODE_TYPES), len(EDGE_TYPES))"

# End-to-end build — confirms `construction_graph` lands in report.json
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
  --out .tmp_tests/phase4_industrial_crate --deterministic
# Inspect: .tmp_tests/phase4_industrial_crate/industrial_crate/stages/validate/report.json
# Top-level "construction_graph" key exists with version, family, asset_name,
# nodes (6), edges (7), node_count, edge_count, node_types_present, edge_types_present.
```
