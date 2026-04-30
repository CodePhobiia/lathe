# Vision Critique Loop v1

> **Phase 10 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the optional vision-critique loop that converts
> rendered-preview critique into validated **semantic patch
> proposals** against the design brief, family grammar, and
> ShapeIR v2. Phase 10 is **evidence + diagnostic only** — patches
> are validated and recorded, never applied.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 11
> (preview and evidence) + Section 17 (governance),
> `docs/asset-quality/improvement-tasklist.md` Section 10 (Phase 10 task list),
> `docs/asset-quality/preview-evidence-v1.md` (Phase 9 — the 23rd
> validate-report key, immediately preceding `vision_critique`).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/vision_critique.py`
**Validator name:** `vision_critique`
**Payload version field:** `vision_critique_v1`

---

## 1. Overview

Phase 10 adds an optional **rendered-preview critique** layer on
top of the Phase 1-9 evidence views. Two providers participate:

- A **deterministic stub provider** (always available; pure
  function over `(asset, runtime)`) that translates Phase 1-9
  evidence into critique issues using fixed, threshold-based
  mapping.
- An **optional external vision provider hook** that activates
  only when the runtime config wires it. The provider mux returns
  a structured `vision_provider_unavailable` skipped reason when
  the provider is missing, misconfigured, unknown, or
  unreachable. It NEVER fabricates vision-model output (per
  `AGENTS.md`).

Each critique issue carries one or more **semantic patch
proposals** — never raw mesh edits. A patch validator checks
every proposal against a whitelist of targets, operations, and
field paths and explicitly forbids touches to the
`lathe.shape.intent_mesh_handoff_v1` contract or to public
`.lth` syntax keys. Approved patches are recorded as evidence;
rejected patches surface in `patch_validation.rejections` with
structured reason tokens.

### What this layer does

- Defines `PatchProposal`, `CritiqueIssue`, `CritiqueProvider`,
  and `SkippedReason` frozen dataclasses with `to_dict()`
  round-trips.
- Emits stable critique `issue_id` values via `blake2b((evidence_view, recommendation))`
  so identical inputs always produce identical critique payloads.
- Reads `runtime["quality_diagnostics"]`,
  `runtime["family_grammar"]`, `runtime["material_wear_graph"]`,
  `runtime["preview_evidence"]`, `runtime["highlow_relation"]`,
  and `runtime["design_brief"]` to synthesise issues.
- Reads the optional
  `runtime["_runtime_config"]["vision_critique"]` block to drive
  provider selection. The runtime config is published by the
  executor before validate runs through `redact_secrets()` so
  api keys / endpoints never land in the validate report.
- Validates every patch proposal against the whitelist and the
  shape-contract / public-surface guards; emits structured
  rejections.
- Sorts issues deterministically by
  `(severity_rank, issue_id)` and skipped reasons by
  `(category, reason)`.
- Publishes the result on `runtime["vision_critique"]` and emits
  the additive `vision_critique` key on the validate-stage
  report (the **24th top-level key**, on top of the 23 from
  Phases 0 through 9).

### What this layer does NOT do

- Run a real vision model, render a preview, or call any
  external service. Phase 10 ships a `mock_http_vision_provider`
  that always raises `ConnectionError`. Real provider
  integration is reserved for forward phases.
- Mutate the asset. Phase 10 records validated patches as
  evidence; their application is reserved for a forward phase.
- Touch the `lathe.shape.intent_mesh_handoff_v1` contract.
- Touch public `.lth` syntax (`profile`, `contract`, `critic`,
  `asset`, `variant`). Patches that propose changes to these
  keys are rejected with `touches_public_surface`.
- Block certification. Like Phases 1 through 9, the validator is
  registered with `weight=0.0` and emits no `diagnostics`
  entries.
- Invent vision-model output when the external provider is
  unavailable. Per `AGENTS.md`, the only acceptable behaviour is
  a structured `vision_provider_*` skipped reason.

---

## 2. Schema

### 2.1 Top-level payload

```jsonc
{
  "version": "vision_critique_v1",
  "asset_name": "industrial_crate",
  "provider": {
    "name": "deterministic_stub",
    "version": "v1",
    "configured": false
  },
  "issues": [
    {
      "issue_id": "<16-char hex>",
      "severity": "warning",
      "evidence_view": "quality_diagnostics",
      "recommendation": "...",
      "patch_proposals": [
        {
          "target": "design_brief",
          "field": "design_brief.wear",
          "operation": "set",
          "current_value": "moderate",
          "proposed_value": "heavy",
          "rationale": "..."
        }
      ]
    }
  ],
  "patch_validation": {
    "all_patches_valid": true,
    "approved_count": 3,
    "rejected_count": 0,
    "rejections": []
  },
  "summary": {
    "issue_count": 2,
    "issues_by_severity": {"info": 0, "warning": 2, "error": 0},
    "patch_count": 3,
    "approved_patches": 3
  },
  "skipped_reasons": [
    {"category": "vision_provider", "reason": "vision_provider_not_configured"}
  ],
  "warnings": [],
  "diagnostics": []
}
```

### 2.2 Frozen dataclasses

| Dataclass         | Fields |
|-------------------|--------|
| `PatchProposal`   | `target`, `field`, `operation`, `current_value`, `proposed_value`, `rationale` |
| `CritiqueIssue`   | `issue_id`, `severity`, `evidence_view`, `recommendation`, `patch_proposals` |
| `CritiqueProvider`| `name`, `version`, `configured` |
| `SkippedReason`   | `category`, `reason` |

All four dataclasses are `frozen=True` and expose a
`to_dict()` method that emits the JSON-serialisable payload
shape used in the report.

---

## 3. Provider catalog

| Provider id                  | Source                          | Behaviour                                  |
|------------------------------|---------------------------------|---------------------------------------------|
| `deterministic_stub`         | Phase 1-9 evidence views        | Always runs; pure function; no I/O          |
| `mock_http_vision_provider`  | `_PROVIDER_REGISTRY` (Phase 10) | Always raises `ConnectionError` (smoke-test only) |

Real external providers (HTTP / RPC integrations to vision
models) are intentionally out of scope for Phase 10. A forward
phase will register them in `_PROVIDER_REGISTRY` after the
network-egress security review.

---

## 4. Provider mux behaviour

The mux is governed by
`runtime["_runtime_config"]["vision_critique"]`:

```jsonc
{
  "vision_critique": {
    "enabled": true,
    "provider": "mock_http_vision_provider",
    "model": "vision-v0",
    "endpoint": "https://example.invalid/v1/critique"
  }
}
```

| Config state                            | Outcome |
|-----------------------------------------|---------|
| Block missing or `enabled: false`       | Stub only; emits `vision_provider_not_configured` |
| `enabled: true`, no `provider` id       | Stub only; emits `vision_provider_misconfigured`  |
| Provider id not in registry             | Stub only; emits `vision_provider_unknown`        |
| Provider raises `ConnectionError` / `TimeoutError` / `OSError` | Stub only; emits `vision_provider_unavailable` |
| Provider succeeds                       | External issues join stub issues; `provider.configured = True` |

In every case, the deterministic stub still runs and the
validator returns a well-formed payload.

---

## 5. Critique signals

The deterministic stub maps Phase 1-9 evidence views into
critique issues using fixed thresholds:

| Evidence view             | Trigger                                                        | Patch target(s)                  |
|---------------------------|----------------------------------------------------------------|----------------------------------|
| `quality_diagnostics`     | `metrics.debug_material_preview_penalty > 0.50`                | `design_brief.material_age`, `design_brief.wear` |
| `highlow_relation`        | `metrics.highlow_fake_detail_penalty > 0.40`                   | `design_brief.detail_density`    |
| `quality_diagnostics`     | `metrics.random_triangulation_penalty > 0.30`                  | `shape_ir_v2.ops.cut_panel_line`, `design_brief.shape_language` |
| `family_grammar`          | `family_grammar.coverage < 0.70`                               | `family_grammar.missing_requirements` |
| `material_wear_graph`     | `uniform_noise.is_uniform_noise == True`                       | `design_brief.wear`              |
| `preview_evidence`        | `preview_summary.distinct_final_from_material_ids == False`    | `design_brief.negative_constraints` |

Each signal emits a deterministic `issue_id` so identical
inputs always produce identical issue ids — the stub is a pure
function and the order of issues in the payload is stable
across runs.

---

## 6. Patch validation rules

A patch is approved iff all of the following hold:

| Rule                                                  | Rejection token              |
|-------------------------------------------------------|------------------------------|
| `target ∈ {"design_brief", "family_grammar", "shape_ir_v2"}` | `invalid_target`        |
| `operation ∈ {"set", "add", "remove", "increase", "decrease"}` | `invalid_operation`   |
| `field` is non-empty, dotted, and starts with `<target>.` | `field_path_malformed`    |
| `proposed_value` is JSON-serialisable                 | `non_serializable_value`     |
| Field path does NOT touch `lathe.shape.intent_mesh_handoff_v1` | `touches_shape_contract` |
| Field path does NOT touch `profile`, `contract`, `critic`, `asset`, `variant` | `touches_public_surface` |

Rejections are recorded in
`patch_validation.rejections` as
`{"issue_id": ..., "field": ..., "reason": ...}` records.
`patch_validation.all_patches_valid` is `True` iff
`rejections` is empty.

**Phase 10 NEVER applies patches.** Approved patches are
recorded as evidence; application is reserved for a forward
phase.

---

## 7. Skipped-evidence contract

Per `AGENTS.md`, every gap records a structured reason token
instead of a fabricated critique:

| Token                              | When |
|------------------------------------|------|
| `vision_provider_not_configured`   | No `vision_critique` block, or `enabled: false` |
| `vision_provider_misconfigured`    | Block enabled but no `provider` id |
| `vision_provider_unknown`          | Provider id not in `_PROVIDER_REGISTRY` |
| `vision_provider_unavailable`      | Registered provider raised `ConnectionError`, `TimeoutError`, or `OSError` |

All four tokens land under `category: "vision_provider"`. The
deterministic stub still runs in all four cases.

---

## 8. Pipeline placement

The validator is registered in
`lathe/core/stages/validate.py` `_PIPELINE` immediately after
`preview_evidence` and before `geometry_integrity`. Output
additively appears under the top-level `vision_critique` key of
the validate-stage report.

The executor publishes
`runtime["_runtime_config"] = redact_secrets(self.runtime_config)`
right before the validate stage runs (in
`lathe/executor.py::BuildExecutor.build()`), so api keys /
endpoints never leak into the validate report.

---

## 9. Forward references

- **Phase 14** (golden examples) consumes `vision_critique` in
  end-to-end golden snapshots so reviewers can spot regressions
  in the deterministic-stub critique signal mapping.
- **Patch application** (forward phase) will lift validated
  patches and apply them to the asset/runtime. Phase 10 records
  patches AS EVIDENCE only.

---

## 10. Configuration example

To enable the optional vision provider hook, supply a runtime
config JSON file:

```jsonc
// runtime_configs/vision_critique_smoke.json
{
  "vision_critique": {
    "enabled": true,
    "provider": "mock_http_vision_provider"
  }
}
```

Then build with:

```bash
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
  --out dist --runtime-config runtime_configs/vision_critique_smoke.json
```

The validate-stage report will record
`vision_provider_unavailable` under
`vision_critique.skipped_reasons` (the mock provider always
raises) and the deterministic stub will still emit issues.
