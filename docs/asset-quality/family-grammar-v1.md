# Family Grammar IR v1

> **Phase 3 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the internal `FamilyGrammar` representation introduced to capture
> the construction concepts every hero asset family must contain — without
> changing the public `.lth` syntax.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 7
> (DesignBrief / family alignment),
> `docs/asset-quality/improvement-tasklist.md` Section 3 (Phase 3 task list),
> `docs/asset-quality/design-brief-ir.md` (Phase 2 reference for the
> additive-payload pattern this layer follows),
> `docs/asset-quality/quality-diagnostics-v1.md` (Phase 1 — `family_grammar_coverage`
> is exposed as an additive metric there).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/family_grammar.py`
**Validator name:** `family_grammar`
**Payload version field:** `family_grammar_v1`

---

## 1. Overview

`FamilyGrammar` is an internal IR that records the construction concepts a
hero asset family is expected to contain. The MVP encodes the
`industrial_crate` grammar (10 requirements split across `required` and
`recommended` severities) and a `generic` fallback grammar so unknown
families degrade gracefully.

### What this layer does

- Defines three immutable dataclasses: `FamilyRequirement`,
  `FamilyGrammar`, `FamilyGrammarResult`.
- Encodes the canonical industrial-crate grammar.
- Computes a deterministic `coverage` score in `[0.0, 1.0]` per asset.
- Reads `runtime["design_brief"]["brief"]["family"]` (populated by
  Phase 2's `design_brief` validator running first in the pipeline) and
  selects the matching grammar; falls back to `generic` if the brief is
  absent.
- Publishes the result to `runtime["family_grammar"]` and emits an
  additive `family_grammar` key on the validate-stage report.
- Exposes `family_grammar_coverage` as an additive metric on the
  Phase 1 `quality_diagnostics` payload so a single warning fires when
  coverage drops below `0.50`.

### What this layer does *not* do

- Touch `.lth` source syntax. The Phase 3 contract is internal-only.
- Modify, rename, or remove any existing report field.
- Touch `lathe.shape.intent_mesh_handoff_v1`.
- Lower grammar requirements into ShapeIR or actual geometry — that is
  Phase 6's responsibility.
- Build the semantic construction graph that supersedes token-based
  detection — that is Phase 4's responsibility.
- Run any per-family threshold tightening on existing metrics — Phase 3
  is purely additive.
- Block certification. Like Phases 1 and 2, the validator is registered
  with `weight=0.0` and returns no `diagnostics` field.

---

## 2. Payload schema

The validator returns this additive payload, which is exposed under
`report["family_grammar"]` on the validate-stage report:

```json
{
  "version": "family_grammar_v1",
  "family": "industrial_crate",
  "coverage": 0.4,
  "satisfied_count": 4,
  "partial_count": 0,
  "missing_count": 6,
  "requirement_results": [
    {
      "name": "body_shell",
      "severity": "required",
      "status": "satisfied",
      "evidence": {"matched_parts": ["body"]}
    },
    {
      "name": "lid_seam",
      "severity": "required",
      "status": "missing",
      "evidence": {"matched_parts": []}
    }
  ],
  "recommendations": [
    "Add a lid seam: the industrial crate grammar requires a visible lid break wrapping the top of the body."
  ]
}
```

`requirement_results` is index-aligned by *requirement declaration
order* (not by status). Recommendations are emitted in the same order
as the underlying missing/partial requirements so a downstream consumer
can correlate the two without re-keying.

### 2.1 `requirement_results` entry shape

| Field | Type | Notes |
|---|---|---|
| `name` | string | Stable requirement identifier (e.g. `body_shell`). |
| `severity` | string | One of `required`, `recommended`, `optional`. Phase 3 emits no `optional` entries. |
| `status` | string | `satisfied`, `partial`, `missing`, or `not_applicable`. The MVP only emits `satisfied` and `missing`; `partial` is reserved for Phase 4's graph-edge detection and `not_applicable` for forward phases. |
| `evidence` | object | At MVP, always `{"matched_parts": [...]}` listing the asset parts that triggered the match. |

---

## 3. Severity model

Three severity levels are accepted on `FamilyRequirement`:

| Severity | Counts toward coverage? | Phase 3 use |
|---|---|---|
| `required` | yes | Mandatory construction concepts. |
| `recommended` | yes | Strong-preference concepts that lift the asset above blockout quality. |
| `optional` | no | Reserved for forward phases (e.g. family variants); the MVP encodes none. |

### 3.1 Coverage formula

```
total_applicable = count of requirements whose severity is "required" or "recommended"
                   and whose status is not "not_applicable"
earned           = sum over requirements:
                     1.0 when status == "satisfied"
                     0.5 when status == "partial"
                     0.0 when status == "missing"
                     (skipped when status == "not_applicable" or severity == "optional")
coverage         = earned / total_applicable    if total_applicable > 0
                 = 1.0                          otherwise
```

The 1.0 default for empty grammars makes the `generic` fallback a
no-op: assets with no encoded family expectations cannot be penalised
by this layer.

---

## 4. Industrial-crate requirement table

Ten requirements, encoded in declaration order. Detection at MVP uses
case-insensitive substring matching against `asset["intent"]["parts"]`.

| # | Name | Severity | Detection tokens | Expected behavior |
|---:|---|---|---|---|
| 1 | `body_shell` | required | `body` | Primary box-shell volume of the crate. |
| 2 | `lid_seam` | required | `lid` | Visible lid break wrapping the top of the body. |
| 3 | `corner_guards` | required | `corner_guard`, `corner`, `guard` | Reinforcement guards on the eight body corners. |
| 4 | `latch_or_latch_plate` | required | `latch` | Latch or latch plate at the lid/body seam. |
| 5 | `recessed_or_bracketed_handles` | required | `handle` | Handles seated into recessed wells or bracket plates. |
| 6 | `foot_rails_or_feet` | recommended | `foot`, `feet`, `rail` | Foot rails or discrete feet that lift the body. |
| 7 | `trim_bands` | recommended | `trim`, `band` | Horizontal or vertical trim bands. |
| 8 | `fasteners` | recommended | `fastener`, `bolt`, `rivet`, `screw` | Visible fasteners at structural junctions. |
| 9 | `warning_or_decal_zones` | recommended | `warning`, `decal`, `label` | Warning text, stencils, or decal zones. |
| 10 | `edge_wear_masks` | recommended | `wear`, `mask`, `edge_wear` | Edge wear masks on high-traffic edges. |

### 4.1 Industrial crate baseline coverage

The hero `examples/industrial_crate.lth` carries the parts list
`[body, latch_plate, handle_l, handle_r, foot_l, foot_r]`, which
matches:

- `body_shell` (via `body`)
- `latch_or_latch_plate` (via `latch_plate`)
- `recessed_or_bracketed_handles` (via `handle_l`, `handle_r`)
- `foot_rails_or_feet` (via `foot_l`, `foot_r`)

`satisfied_count = 4`, `missing_count = 6`, `coverage = 0.4`. Because
`0.4 < 0.5`, the additive `family_grammar_coverage` warning fires under
Phase 1's `quality_diagnostics` layer, surfacing the missing
construction concepts (lid seam, corner guards, trim bands, fasteners,
warning decals, edge wear masks) without blocking certification.

---

## 5. Generic fallback rules

If the brief reports a family this MVP does not recognise (anything
other than `industrial_crate`), the validator falls through to the
`generic` grammar. That grammar has an empty requirements tuple, so:

- `coverage = 1.0` (no requirements means trivially satisfied);
- `satisfied_count`, `partial_count`, `missing_count` are all `0`;
- `requirement_results` is `[]`;
- `recommendations` is `[]`.

The same fallback applies when `runtime["design_brief"]` is missing or
malformed. The generic fallback never warns, never reduces the
`quality_diagnostics` `family_grammar_coverage` metric below `1.0`,
and never produces a recommendation. Phase 4+ will introduce
graph-derived requirements for the generic family; until then, the
fallback is informational only.

---

## 6. Pipeline placement

The validator is registered in `lathe/core/stages/validate.py:_PIPELINE`
**immediately after** `design_brief` and **before** `quality_diagnostics`,
both with `stage_dependencies=[]` and `weight=0.0`. Because
`ValidatorPipeline` orders by stage dependencies and breaks ties on
registration order
(`lathe/validators/composition.py:_topological_order`), this
guarantees:

1. `design_brief` runs first and publishes the inferred family.
2. `family_grammar` runs second, reads the brief, and publishes the
   coverage result.
3. `quality_diagnostics` runs later (after `shape`/`topology`/`uv`/
   `surface` are present) and reads the family-grammar coverage to
   compute its additive `family_grammar_coverage` metric and warning.

The pipeline composition layer (`lathe/validators/composition.py:287-291`)
publishes each validator's evidence into `runtime[validator.name]`, so
downstream phases can consume `runtime["family_grammar"]` directly
without re-deriving anything.

The validate stage step (`lathe/core/stages/validate.py:run`) extracts
the result, mirrors it onto `executor.runtime["family_grammar"]`, and
adds a top-level `family_grammar` key to `report.json`. The validator
never contributes to the aggregate certification score (`weight=0.0`)
and never produces blocking diagnostics — Phase 3 is informational
evidence only.

---

## 7. Forward references

| Phase | Consumes | Use |
|---|---|---|
| Phase 4 — Construction Graph | `requirement_results[*].name` | Replaces token-based part-list detection with graph-edge detection (e.g. `corner_guards` becomes a graph pattern over `wraps_around` edges, enabling `partial` status for in-graph but undeclared parts). |
| Phase 5 — ShapeIR v2 | `requirement_results[*].name` | Maps each requirement to a v2 operation family for adapter coverage. |
| Phase 6 — Grammar lowering | the entire grammar | Lowers each requirement into actual ShapeIR v2 operations so missing requirements become real geometry. |
| Phase 8 — Material/Wear graph | `edge_wear_masks` requirement | Drives wear-mask authoring intent and per-zone material policies. |
| Phase 11 — References | `requirement_results[*].status` | Filters reference selection to fixtures that exemplify each missing requirement. |
| Phase 12 — Kit | the entire grammar | Each kit asset declares which requirements it satisfies for assembly-level coverage. |

---

## 8. Verification

```bash
# Per-grammar and per-requirement unit tests
python -m pytest tests/unit/test_asset_quality_family_grammar.py -v

# Phase 1 still green (regression check — diagnostics adds family_grammar_coverage)
python -m pytest tests/unit/test_asset_quality_diagnostics.py -q

# Phase 2 still green (regression check)
python -m pytest tests/unit/test_asset_quality_design_brief.py -q

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
python -c "from lathe.asset_quality.family_grammar import FAMILY_GRAMMAR_VERSION, evaluate_family_grammar; print(FAMILY_GRAMMAR_VERSION)"

# End-to-end build — confirms `family_grammar` lands in report.json
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
  --out .tmp_tests/phase3_industrial_crate --deterministic
# Inspect: .tmp_tests/phase3_industrial_crate/industrial_crate/stages/validate/report.json
# Top-level "family_grammar" key exists with version, family, coverage,
# satisfied_count, partial_count, missing_count, requirement_results, recommendations.
```
