# ShapeIR v2 — Internal Semantic Operation Model

**Status:** Phase 5 (internal IR + adapter only)
**Date:** 2026-04-30
**Module:** `lathe/asset_quality/shape_ir_v2.py`
**Spec:** `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 10
**Tasklist:** `docs/asset-quality/improvement-tasklist.md` Phase 5

---

## 1. Overview

ShapeIR v1 (`lathe/shape_ir.py`) models shape construction as a flat list of axis-aligned `ShapePrimitive` records — `box` and `cylinder` only, with `center`, `extents`, optional `radius`/`height`, and a small set of attributes (`tags`, `blend_mode`, `rounding`). The v1 IR is the runtime hand-off shape under the stable `lathe.shape.intent_mesh_handoff_v1` contract; downstream stages (topology, UV, surface, validate, package) all read it.

ShapeIR v2 introduces a richer **semantic** authoring layer expressed as an ordered list of operations (`ShapeOp`). Where v1 says "place a box at position X with extents Y", v2 says "this is the body shell solid, then bevel its outer edges, then inset the lid seam, then add a fastener grid on the front face". The same boxes can come out the other end, but now the construction decisions are first-class data.

Phase 5 is **internal IR + adapter only**. Phase 5:

- adds the v2 dataclasses, op family registry, validation, and the v2-to-v1 adapter;
- does **not** add a top-level key to the validate-stage report;
- does **not** change `.lth` syntax, `schema/lathe.schema.json`, `spec/lathe-v0.1.md`, or anything in `lathe/parser/`, `lathe/normalizer.py`, `lathe/resolver.py`, `lathe/checker/`;
- does **not** edit `lathe/shape_backend.py`, `lathe/shape_providers.py`, or anything that produces the v1 shape bundle.

Phase 6 will use this infrastructure to lower the industrial_crate grammar into v2 operations and adapt them down to v1 records for the existing scaffold/fusion mechanisms.

## 2. Goals and Non-Goals

### Goals

1. Capture richer construction intent than v1 boxes/cylinders allow (bevels, sockets, fastener grids, weld seams, wear masks).
2. Provide a deterministic serialization (`to_dict`) so v2 programs can be embedded in trace/report metadata.
3. Provide a v2-to-v1 adapter so any v2 op that maps to a v1 primitive can be lowered today.
4. Surface clear diagnostics for v2 ops that have no v1 equivalent — Phase 6/7+ will pick them up; we never silently drop intent.

### Non-Goals (Phase 5)

1. Public `.lth` syntax. v2 is internal-only at Phase 5.
2. Pipeline integration. The validate-stage report keeps its 19 top-level keys; v2 does not register a validator.
3. Modifying the v1 contract. The v1 shape bundle, hand-off ID, and downstream stage contracts are unchanged.
4. New runtime behaviour. v2 ops are data; the runtime still consumes v1.

## 3. Operation Families

Six families, 30 operations total. Each family is exposed as a `frozenset[str]` constant; `ALL_OPS` is the union and is used by `validate_op` and `lower_to_v1` to gate op-name membership. The families are disjoint — every op name appears in exactly one family.

### 3.1 Solids (`SOLID_OPS`, 6)

Primitives that introduce new geometry. Each requires extents.

| Op | Required parameters | Notes |
|---|---|---|
| `solid.box` | `width_cm`, `height_cm`, `depth_cm` | Lowers cleanly to v1 `box`. |
| `solid.rounded_box` | `width_cm`, `height_cm`, `depth_cm`, `radius_cm` | Lowers to v1 `box` + `rounding=radius_cm`. |
| `solid.cylinder` | `radius_cm`, `height_cm` | Lowers cleanly to v1 `cylinder`. |
| `solid.prism` | `width_cm`, `height_cm`, `depth_cm` | Lowered as a v1 `box` approximation tagged `prism_approx`. |
| `solid.rail` | `length_cm`, `profile_cm` | No v1 equivalent; recorded for Phase 6/7+. |
| `solid.panel` | `width_cm`, `height_cm`, `thickness_cm` | No v1 equivalent today. |

Example:

```json
{
  "op": "solid.rounded_box",
  "target": "body_shell",
  "parameters": {"width_cm": 92.0, "height_cm": 58.0, "depth_cm": 64.0, "radius_cm": 1.5},
  "purpose": "primary_volume"
}
```

### 3.2 Boolean and Construction (`BOOLEAN_OPS`, 7)

Modify or combine existing geometry. v1 has no boolean primitives so all of these emit `no_v1_equivalent` until Phase 6+ writes downstream support.

| Op | Required parameters |
|---|---|
| `op.union` | (none) |
| `op.subtract` | (none) |
| `op.intersect` | (none) |
| `op.inset` | `depth_cm` |
| `op.extrude` | `depth_cm` |
| `op.shell` | `thickness_cm` |
| `op.cut_panel_line` | `width_cm` |

### 3.3 Edge Control (`EDGE_OPS`, 4)

Hard-surface readability.

| Op | Required parameters |
|---|---|
| `op.bevel` | `width_cm`, `segments` |
| `op.chamfer` | `width_cm` |
| `op.weighted_normals` | (none) |
| `op.mark_hard_edge` | (none) |

Example:

```json
{
  "op": "op.bevel",
  "target": "body_shell.outer_edges",
  "parameters": {"width_cm": 1.2, "segments": 3},
  "purpose": "catch_light_and_support_hard_surface_readability"
}
```

### 3.4 Repetition / Detail (`REPETITION_OPS`, 5)

Semantic repetition — fastener grids, vent slats, trim bands, corner guards.

| Op | Required parameters |
|---|---|
| `op.repeat` | `count`, `axis` |
| `op.fastener_grid` | `rows`, `columns`, `spacing_cm` |
| `op.vent_slats` | `count`, `spacing_cm` |
| `op.trim_band` | `width_cm` |
| `op.corner_guard_set` | `size_cm` |

### 3.5 Integration (`INTEGRATION_OPS`, 4)

Attachment / seating ops that fix the "stuck-on greeble" failure mode.

| Op | Required parameters |
|---|---|
| `op.socket` | `clearance_cm` |
| `op.bracket` | `clearance_cm`, `mount_type` |
| `op.mount_plate` | `width_cm`, `height_cm` |
| `op.weld_seam` | `width_cm` |

### 3.6 Wear / Damage (`WEAR_OPS`, 4)

Semantic wear masks that Phase 8's material/wear graph will consume.

| Op | Required parameters |
|---|---|
| `op.chip_edges` | `amount` |
| `op.scratch_mask` | `amount` |
| `op.dent_mask` | `amount` |
| `op.grime_mask` | `amount` |

## 4. Validation Rules

`validate_op(op)` returns `(is_valid, diagnostics)`:

1. **Op-name check.** If `op.op` is not a member of `ALL_OPS`, return `(False, ["unsupported_v2_op"])` and short-circuit. No further checks run.
2. **Required-parameter check.** For each key in `_REQUIRED_PARAMS[op.op]` that is not present in `op.parameters`, append `f"missing_required_param: {key}"` to the diagnostics list. The list preserves declaration order from the required-parameter table.
3. The op is valid iff the diagnostics list is empty after step 2.

`validate_op` does not type-check parameter values today. Type checking is reserved for a later phase if a need arises; the corresponding diagnostic code (`parameter_type_mismatch`) is documented in the module docstring for forward compatibility.

## 5. v2-to-v1 Adapter

`lower_to_v1(program)` walks `program.ops` in declaration order and produces a `V1AdapterResult` with three deterministic tuple fields:

- `v1_records` — dicts shaped to be compatible with the v1 `ShapePrimitive` payload. Each lowered record carries two extra keys, `v2_op` and `v2_purpose`, so the v2 origin is preserved through the trace/report.
- `diagnostics` — list of `{"code", "op", "reason"}` dicts. Each missing required parameter emits its own diagnostic.
- `unsupported_ops` — deduplicated tuple of op names that were not members of `ALL_OPS`, in first-occurrence order.

Per-op behaviour:

| v2 op family | Adapter behaviour |
|---|---|
| `solid.box` | Lowered to v1 `box` (extents from `width_cm`/`height_cm`/`depth_cm`). |
| `solid.rounded_box` | Lowered to v1 `box` with `rounding=radius_cm` and `tags=["rounded"]`. |
| `solid.cylinder` | Lowered to v1 `cylinder` (`axis="y"`, `radius`, `height`). |
| `solid.prism` | Lowered to v1 `box` tagged `prism_approx` (best-effort approximation; v1 has no prism primitive). |
| All other valid ops | Emit `no_v1_equivalent` diagnostic; no v1 record. |
| Op not in `ALL_OPS` | Emit `unsupported_v2_op` diagnostic; no v1 record. |
| Missing required param | Emit one `missing_required_param` per missing key; no v1 record. |

### Diagnostic codes

- `unsupported_v2_op` — op name is not a member of any family in `ALL_OPS`.
- `missing_required_param` — a required parameter (per `_REQUIRED_PARAMS`) is absent.
- `no_v1_equivalent` — op is valid in v2 but the v1 IR does not model it.
- `parameter_type_mismatch` — reserved for a future type-checking pass.

## 6. Compatibility Guarantees

Phase 5 makes the following guarantees against the v0.2.0rc1 baseline:

1. **`lathe.shape.intent_mesh_handoff_v1` is untouched.** No edits to `lathe/shape_backend.py`, `lathe/shape_providers.py`, or any module that produces the v1 shape bundle.
2. **`.lth` syntax is unchanged.** No edits to `grammar/lathe.lark`, `schema/lathe.schema.json`, `spec/lathe-v0.1.md`, `lathe/parser/`, `lathe/normalizer.py`, `lathe/resolver.py`, or `lathe/checker/`.
3. **The validate-stage report shape is unchanged.** Phase 5 does not add a new top-level key. The 19-key contract pinned by `_VALIDATE_REPORT_REQUIRED_KEYS` in `tests/unit/test_asset_quality_baseline_report_shape.py` is preserved.
4. **Existing v1 assets still build.** `python -m lathe.cli check examples/industrial_crate.lth` still returns `{"ok": true, "diagnostics": []}` after Phase 5.
5. **Marker-word hygiene.** New files contain no provisional-implementation marker words; `tests/unit/test_marker_inventory.py` continues to pass against the Phase 5 additions.

## 7. Forward References

Phase 6 (industrial_crate grammar lowering) is the first consumer of v2:

- It will translate the family grammar IR (Phase 3) and semantic construction graph (Phase 4) into a `ShapeProgram` whose ops cover the crate construction recipe (body shell, lid seam, corner guards, latch plate, recessed handles, foot rails, trim bands, fastener grids, decal zones).
- It will pass the program through `lower_to_v1` to produce v1 records consumable by the existing scaffold/fusion mechanisms.
- v2 ops with no v1 equivalent (e.g. `op.bevel`, `op.fastener_grid`, `op.weld_seam`) will be picked up by Phase 7+ when high-poly authoring lands.

Phase 8 (material/wear graph) will read the `WEAR_OPS` annotations attached to a program to drive convex-edge / contact / interaction masks.

## 8. Verification Commands

```bash
python -m pytest tests/unit/test_shape_ir_v2.py -v
python -m pytest tests/unit/test_asset_quality_baseline_report_shape.py -q
python -m pytest tests/unit/test_marker_inventory.py -q
python -m lathe.cli check examples/industrial_crate.lth
python -c "from lathe.asset_quality.shape_ir_v2 import SHAPE_IR_V2_VERSION, ALL_OPS, lower_to_v1, validate_op; print(SHAPE_IR_V2_VERSION, len(ALL_OPS))"
```

Expected:

- 25 unit tests pass.
- Baseline-report-shape and marker-inventory tests pass unchanged.
- CLI `check` returns `{"ok": true, "diagnostics": []}` on `industrial_crate.lth`.
- Final smoke prints `shape_ir_v2 30`.
