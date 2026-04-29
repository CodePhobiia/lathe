# DesignBrief IR v1

> **Phase 2 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the internal `DesignBrief` representation introduced to capture
> art-direction intent for every hero asset *before* geometry generation —
> without changing the public `.lth` syntax.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 7 (spec),
> `docs/asset-quality/quality-diagnostics-v1.md` (Phase 1 reference for
> the additive-payload pattern this layer follows).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/design_brief.py`
**Validator name:** `design_brief`
**Payload version field:** `design_brief_v1`

---

## 1. Overview

`DesignBrief` is an internal IR that records artistic and production
intent for an asset. It is populated as the *first* validator in the
validate-stage pipeline (`lathe/core/stages/validate.py:_PIPELINE`),
publishes the brief into `runtime["design_brief"]`, and emits an
additive `design_brief` key on the validate-stage report.

### What this layer does

- Defines an immutable `DesignBrief` dataclass with twelve typed fields.
- Infers a family token (`industrial_crate`, `mechanical_door`,
  `service_cabinet`, or `generic`) from the asset name, intent role,
  or kind.
- Returns a deterministic per-family default brief so existing assets
  carry a complete brief into reporting on day one.
- Publishes the brief to `runtime["design_brief"]` so later phases
  (family grammar, semantic construction graph, material/wear graph)
  can consume it without re-deriving intent.

### What this layer does *not* do

- Touch `.lth` source syntax. Spec Section 7.4 calls for an internal-first
  rollout; the `.lth` opt-in path is reserved for Phase 13.
- Modify, rename, or remove any existing report field.
- Touch `lathe.shape.intent_mesh_handoff_v1`.
- Run any per-family grammar checks (Phase 3) or construction-graph
  verification (Phase 4).
- Block certification. Like Phase 1, the validator is registered with
  `weight=0.0` and returns no `diagnostics` field.

---

## 2. Payload schema

The validator returns this additive payload, which is exposed under
`report["design_brief"]` on the validate-stage report:

```json
{
  "version": "design_brief_v1",
  "brief": {
    "asset_name": "industrial_crate",
    "family": "industrial_crate",
    "role": "reinforced industrial cargo crate",
    "style_tags": ["utility", "industrial", "shipping"],
    "silhouette": "bold",
    "bevel_language": "chunky_industrial",
    "shape_language": "rectangular_with_45deg_cuts",
    "detail_density": "hero",
    "wear": "medium_edge_wear",
    "material_age": "used_not_destroyed",
    "greeble_style": "functional_only",
    "negative_constraints": ["toy_like", "random_faceting", "ornate"]
  },
  "family_inference": {
    "matched_family": "industrial_crate",
    "match_signal": "name",
    "match_token": "crate"
  }
}
```

The brief is always complete: every one of the twelve fields is
populated for every asset. The `family_inference` block exposes the
provenance of the family choice so downstream tooling can reason about
how the brief was synthesized.

### 2.1 `family_inference` entry shape

| Field | Type | Notes |
|---|---|---|
| `matched_family` | string | One of `industrial_crate`, `mechanical_door`, `service_cabinet`, `generic`. |
| `match_signal` | string | `"name"` (asset name match), `"role"` (intent role match), `"kind"` (asset kind match), or `"default"` (no match — fell through to generic). |
| `match_token` | string | The substring that matched (e.g. `"crate"`). Empty when `match_signal == "default"`. |

---

## 3. Field reference

Every brief carries the same twelve fields. Tuple-typed dataclass fields
serialize as JSON arrays via `DesignBrief.to_dict()`.

| Field | Type | Default origin | Purpose |
|---|---|---|---|
| `asset_name` | string | `asset["name"]` (or `"unnamed_asset"`) | Identifies the asset the brief describes; flows through to reports. |
| `family` | string | family inference | Selects the per-family grammar and threshold profile (Phase 3). |
| `role` | string | per-family default | One-line semantic description of the asset's purpose. |
| `style_tags` | list[str] | per-family default | Style descriptors (e.g. `utility`, `industrial`, `shipping`). |
| `silhouette` | string | per-family default | Silhouette intent: `bold` / `balanced` / `compact`. |
| `bevel_language` | string | per-family default | Bevel character: `chunky_industrial`, `crisp_industrial`, etc. |
| `shape_language` | string | per-family default | Primary shape vocabulary (e.g. `rectangular_with_45deg_cuts`). |
| `detail_density` | string | per-family default | Authoring detail target: `hero` / `standard`. |
| `wear` | string | per-family default | Edge-wear authoring intent (e.g. `medium_edge_wear`). |
| `material_age` | string | per-family default | Material authoring intent (e.g. `used_not_destroyed`). |
| `greeble_style` | string | per-family default | Greeble policy (e.g. `functional_only`). |
| `negative_constraints` | list[str] | per-family default | Forbidden visual styles (e.g. `toy_like`, `ornate`). |

All twelve fields are populated for every brief by construction; no
field is ever `None` or empty. This is verified by
`tests/unit/test_asset_quality_design_brief.py::test_each_family_default_brief_has_all_twelve_fields`.

---

## 4. Family inference rules

`_infer_family` in `lathe/asset_quality/design_brief.py` examines the
following sources in order. The first substring match wins:

1. `asset["name"]` (case-insensitive substring match);
2. `asset["intent"]["role"]` (case-insensitive substring match);
3. `asset["kind"]` (case-insensitive substring match) when present.

Substring tokens are tried deterministically in this order:

| Token | Family |
|---|---|
| `crate` | `industrial_crate` |
| `door` | `mechanical_door` |
| `cabinet` | `service_cabinet` |

If no token matches in any source, the asset falls back to the `generic`
family. Inference is purely deterministic — no random sampling, no
hashing — so the same input always yields the same family.

---

## 5. Per-family default briefs

These defaults are anchored in spec Section 7.3 (`industrial_crate`) and
extended deterministically for the remaining hero families. Threshold
tightening and family-specific grammar live in Phase 3.

### 5.1 `industrial_crate`

| Field | Default |
|---|---|
| role | reinforced industrial cargo crate |
| style_tags | utility, industrial, shipping |
| silhouette | bold |
| bevel_language | chunky_industrial |
| shape_language | rectangular_with_45deg_cuts |
| detail_density | hero |
| wear | medium_edge_wear |
| material_age | used_not_destroyed |
| greeble_style | functional_only |
| negative_constraints | toy_like, random_faceting, ornate |

### 5.2 `mechanical_door`

| Field | Default |
|---|---|
| role | industrial mechanical access door |
| style_tags | utility, industrial, access |
| silhouette | balanced |
| bevel_language | crisp_industrial |
| shape_language | framed_panel_with_inset_leaf |
| detail_density | hero |
| wear | medium_edge_wear |
| material_age | used_not_destroyed |
| greeble_style | functional_only |
| negative_constraints | toy_like, random_faceting, ornate |

### 5.3 `service_cabinet`

| Field | Default |
|---|---|
| role | wall-mounted service utility cabinet |
| style_tags | utility, industrial, service |
| silhouette | compact |
| bevel_language | crisp_industrial |
| shape_language | rectangular_panelled_box |
| detail_density | hero |
| wear | light_edge_wear |
| material_age | in_service |
| greeble_style | functional_only |
| negative_constraints | toy_like, random_faceting, ornate |

### 5.4 `generic` (fallback)

| Field | Default |
|---|---|
| role | hard-surface utility asset |
| style_tags | utility, industrial |
| silhouette | balanced |
| bevel_language | crisp_industrial |
| shape_language | rectangular_panelled |
| detail_density | standard |
| wear | light_edge_wear |
| material_age | in_service |
| greeble_style | functional_only |
| negative_constraints | toy_like, random_faceting |

---

## 6. Pipeline placement

The validator is registered **first** in
`lathe/core/stages/validate.py:_PIPELINE` with `stage_dependencies=[]`
and `weight=0.0`. Because `ValidatorPipeline` orders by stage
dependencies and breaks ties on registration order
(`lathe/validators/composition.py:_topological_order`), this guarantees
the brief is computed before any other validator runs.

The pipeline composition layer (`lathe/validators/composition.py:287-291`)
publishes each validator's evidence into `runtime[validator.name]`, so
downstream validators and phases can consume `runtime["design_brief"]`
directly — exactly the pattern Phase 1's `quality_diagnostics` layer
established.

The validate stage step (`lathe/core/stages/validate.py:run`) extracts
the brief, mirrors it onto `executor.runtime["design_brief"]`, and adds
a top-level `design_brief` key to `report.json`. The brief never
contributes to the aggregate certification score (`weight=0.0`) and
never produces blocking diagnostics — Phase 2 is informational evidence
only.

---

## 7. Forward references

| Phase | Consumes | Use |
|---|---|---|
| Phase 3 — Family Grammar IR | `brief.family` | Selects which `FamilyGrammar` to evaluate (industrial_crate first). |
| Phase 4 — Construction Graph | `brief.shape_language`, `brief.silhouette` | Sets allowed assembly relations and silhouette policy. |
| Phase 5 — ShapeIR v2 | `brief.bevel_language`, `brief.detail_density` | Drives bevel-feature defaults and detail tier selection. |
| Phase 7 — High-poly producer | `brief.detail_density == "hero"` | Determines whether strict mode requires a real high-poly source. |
| Phase 8 — Material/Wear graph | `brief.wear`, `brief.material_age` | Selects per-family wear masks and aging programs. |
| Phase 11 — References | `brief.style_tags`, `brief.negative_constraints` | Filters reference selection and emits negative-constraint test fixtures. |
| Phase 13 — `.lth` opt-in | the entire brief | Allows assets to override family defaults explicitly via authored fields. |

---

## 8. Verification

```bash
# Per-field, per-family, and payload-shape unit tests
python -m pytest tests/unit/test_asset_quality_design_brief.py -v

# Phase 1 still green (regression check)
python -m pytest tests/unit/test_asset_quality_diagnostics.py -q

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
python -c "import lathe.asset_quality.design_brief as db; print(db.VERSION)"

# End-to-end build — confirms `design_brief` lands in report.json
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
  --out .tmp_tests/phase2_industrial_crate --deterministic
# Inspect: .tmp_tests/phase2_industrial_crate/industrial_crate/stages/validate/report.json
# Top-level "design_brief" key exists with version, brief (12 fields), and family_inference.
```
