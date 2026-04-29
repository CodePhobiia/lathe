# Lathe Asset Quality Upgrade — Improvement Tasklist

> **Execution companion to:** `docs/asset-quality/lathe-asset-quality-upgrade-spec.md`  
> **Strategic roadmap:** `docs/asset-quality/lathe-next-level-asset-quality-roadmap.md`  
> **Goal:** Convert Lathe from “technically certified procedural asset generator” into a controllable, art-directed, production-quality hard-surface asset compiler.

**Status:** Draft v0.1  
**Date:** 2026-04-29  
**Primary target asset family:** `industrial_crate`  
**First principle:** Preserve existing `.lth` compatibility and the stable `lathe.shape.intent_mesh_handoff_v1` contract unless a task explicitly says otherwise.

---

## Ground Rules

- [ ] Preserve public Lathe source compatibility by default.
- [ ] Preserve `lathe.shape.intent_mesh_handoff_v1` by default.
- [ ] Prefer additive report/schema fields over breaking changes.
- [ ] Keep external runtime gates truthful; never fake Blender/Roblox/external-viewer evidence.
- [ ] Start deterministic and local; make vision/external review optional.
- [ ] Update tests with every behavior change.
- [ ] Update docs with every public behavior or report-shape change.
- [ ] Do not commit private absolute evidence paths into reusable fixtures unless explicitly documented as local-only examples.
- [ ] Keep changes small enough for targeted review.

---

## Phase 0 — Baseline Capture and Safety Rails

**Purpose:** Freeze what Lathe does today so quality work does not break the existing pipeline.

### 0.1 Verify repo baseline

- [ ] Run `git status --short` and record current modified/untracked files before implementation.
- [ ] Run `python -m lathe.cli check examples/industrial_crate.lth`.
- [ ] Run `python -m lathe.cli check examples/mechanical_door.lth`.
- [ ] Run `python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/baseline_industrial_crate --deterministic`.
- [ ] Run `python -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/baseline_mechanical_door --deterministic`.
- [ ] Save baseline report paths in `docs/asset-quality/baseline-evidence.md`.

### 0.2 Document current visual gaps from latest evidence

- [ ] Create or update `docs/asset-quality/baseline-evidence.md`.
- [ ] Link inspected previews:
  - [ ] service cabinet turntable preview.
  - [ ] industrial crate turntable preview.
  - [ ] mechanical door turntable preview.
- [ ] Summarize known failure modes:
  - [ ] random triangulation/faceting.
  - [ ] debug-material look.
  - [ ] weak primary/secondary/tertiary hierarchy.
  - [ ] stuck-on attachments.
  - [ ] fake or weak high/low distinction.
  - [ ] weak material/wear storytelling.
- [ ] Record current certification scores for those assets.

### 0.3 Add regression expectations

- [ ] Identify current tests covering visual quality and certification reports.
- [ ] Add snapshot/fixture tests for current report compatibility if missing.
- [ ] Ensure new report fields can be additive without breaking old consumers.

**Exit criteria:** Baseline builds/checks run locally, current outputs are documented, and implementation has a safe comparison point.

---

## Phase 1 — Deterministic Visual-Quality Diagnosis Layer

**Purpose:** Make Lathe able to say, in machine-readable and human-readable terms, why an asset still looks prototype-level even when old certification passes.

### 1.1 Inspect existing validator structure

- [ ] Read `lathe/validators/visual_quality.py`.
- [ ] Read any tests covering visual quality/certification reports.
- [ ] Identify where certification report fields are assembled.
- [ ] Identify existing mesh/topology/surface stats available to validators.

### 1.2 Define additive report schema for quality diagnostics

- [ ] Add a `quality_diagnostics` object to certification reports.
- [ ] Include deterministic version field, e.g. `quality_diagnostics.version = "asset_quality_diagnostics_v1"`.
- [ ] Include `metrics` dictionary.
- [ ] Include `warnings` array.
- [ ] Include `recommendations` array.
- [ ] Include `blocking` boolean or `severity` classification without changing existing pass/fail behavior initially.

Example target shape:

```json
{
  "quality_diagnostics": {
    "version": "asset_quality_diagnostics_v1",
    "metrics": {
      "random_triangulation_penalty": 0.42,
      "debug_material_preview_penalty": 0.31,
      "highlow_fake_detail_penalty": 0.55,
      "attachment_seating_quality": 0.48,
      "primary_secondary_tertiary_balance": 0.37
    },
    "warnings": [
      "large flat face is split by noisy diagonal topology",
      "hero asset lacks meaningful high-poly/low-poly distinction"
    ],
    "recommendations": [
      "add controlled panel lines or simplify topology on large flat faces",
      "add real high-poly bevel/detail source before baking runtime low mesh"
    ]
  }
}
```

### 1.3 Implement `random_triangulation_penalty`

- [ ] Create deterministic proxy metric using available mesh/topology stats.
- [ ] Penalize large flat/near-flat regions with many diagonal or tiny triangles when no semantic panel/trim reason exists.
- [ ] Add a clear warning string when threshold is exceeded.
- [ ] Add unit tests for:
  - [ ] clean rectangular panel fixture.
  - [ ] noisy triangulated panel fixture.
  - [ ] intentionally faceted/stylized fixture if supported.

### 1.4 Implement `debug_material_preview_penalty`

- [ ] Detect final preview/material evidence that looks like raw material-ID/debug colors.
- [ ] Use available material-zone count, albedo variance, roughness/normal/AO evidence, and final-preview metadata.
- [ ] Warn when asset has final preview but insufficient authored PBR evidence.
- [ ] Add tests for:
  - [ ] flat primary-color material IDs.
  - [ ] authored material with roughness/normal/AO evidence.

### 1.5 Implement `highlow_fake_detail_penalty`

- [ ] Compare high/low relation fields already present in build/certification output.
- [ ] Penalize hero assets where high/low distinction is near-zero, identical, absent, or not reflected in maps.
- [ ] Add warning: `hero asset lacks meaningful high-poly/low-poly distinction`.
- [ ] Add tests for fake relation and valid relation.

### 1.6 Implement `attachment_seating_quality` proxy

- [ ] Use part graph/assembly metadata to find attached small parts relative to primary body.
- [ ] Reward sockets, brackets, inset relationships, mount plates, or explicit integration metadata.
- [ ] Penalize unintegrated attached primitives.
- [ ] Add tests for:
  - [ ] handle directly attached to body.
  - [ ] handle seated in bracket/socket metadata.

### 1.7 Implement `primary_secondary_tertiary_balance` proxy

- [ ] Classify parts/features by scale and semantic tag where available.
- [ ] Detect “one primary body + tiny noise only” cases.
- [ ] Reward medium-scale construction features: rails, frames, corner guards, panels, trim, sockets.
- [ ] Add tests for weak vs healthy hierarchy.

### 1.8 Integrate diagnostics into certification output

- [ ] Add diagnostics generation to certification path.
- [ ] Preserve all existing fields.
- [ ] Ensure missing optional stats degrade to warnings, not crashes.
- [ ] Add integration test for report compatibility.

### 1.9 Documentation

- [ ] Create `docs/asset-quality/quality-diagnostics-v1.md`.
- [ ] Explain every metric, thresholds, limitations, and how to improve an asset.
- [ ] State this is a diagnosis gate, not full ShapeIR v2.

### 1.10 Verification commands

- [ ] Run targeted visual-quality tests.
- [ ] Run build for `industrial_crate` and inspect `quality_diagnostics` in report.
- [ ] Run build for `mechanical_door` and inspect `quality_diagnostics` in report.
- [ ] Run `python -m pytest -q` if behavior changed broadly.

**Exit criteria:** Current prototype-like problems are visible in reports with actionable diagnostics, without breaking existing certification consumers.

---

## Phase 2 — Design Brief IR Defaults

**Purpose:** Give Lathe an explicit internal representation of artistic intent before geometry is generated.

### 2.1 Design the internal dataclass/schema

- [ ] Add an internal `DesignBrief` representation in an appropriate module, e.g. `lathe/asset_quality/design_brief.py` or adjacent existing asset graph code.
- [ ] Include fields:
  - [ ] asset name.
  - [ ] family.
  - [ ] role.
  - [ ] style tags.
  - [ ] silhouette intent.
  - [ ] bevel language.
  - [ ] shape language.
  - [ ] detail density.
  - [ ] wear level.
  - [ ] material age.
  - [ ] greeble style.
  - [ ] negative constraints.
- [ ] Add deterministic defaults for missing fields.

### 2.2 Populate brief from current inputs

- [ ] Infer family from asset name/tags/profile where currently available.
- [ ] Map known examples:
  - [ ] `industrial_crate` -> industrial crate brief.
  - [ ] `mechanical_door` -> mechanical door brief.
  - [ ] service cabinet asset -> service cabinet brief if discoverable.
- [ ] Include brief in build/certification metadata.

### 2.3 Tests

- [ ] Add tests for default brief creation.
- [ ] Add tests for family inference.
- [ ] Add tests that existing assets get deterministic briefs.

### 2.4 Docs

- [ ] Document `DesignBrief` in `docs/asset-quality/design-brief-ir.md`.
- [ ] Explain that this is internal first and does not require `.lth` syntax changes.

**Exit criteria:** Every hero asset can carry a deterministic design brief into validation/reporting.

---

## Phase 3 — Family Grammar IR MVP: Industrial Crate

**Purpose:** Teach Lathe what a crate is supposed to be, structurally and visually.

### 3.1 Create family grammar module

- [ ] Add a grammar registry module, e.g. `lathe/asset_quality/family_grammar.py`.
- [ ] Define `FamilyGrammar` structure.
- [ ] Define `FamilyRequirement` structure.
- [ ] Add severity levels: `required`, `recommended`, `optional`.
- [ ] Add deterministic validation result type.

### 3.2 Implement `industrial_crate` grammar

- [ ] Required: body shell.
- [ ] Required: lid seam.
- [ ] Required: corner guards.
- [ ] Required: latch or latch plate.
- [ ] Required/recommended: recessed or bracketed handles.
- [ ] Recommended: foot rails or feet.
- [ ] Recommended: trim bands.
- [ ] Recommended: fasteners.
- [ ] Recommended: warning/decal zones.
- [ ] Recommended: edge wear masks.

### 3.3 Add grammar coverage metric

- [ ] Add `family_grammar_coverage` to quality diagnostics.
- [ ] Include missing/partial/satisfied requirements.
- [ ] Include human-readable recommendations.

### 3.4 Tests

- [ ] Test a crate with only a body fails/reports missing grammar requirements.
- [ ] Test a crate with body + lid + guards + handles + latch improves score.
- [ ] Test unknown family gracefully uses generic grammar.

### 3.5 Docs

- [ ] Create `docs/asset-quality/family-grammar-v1.md`.
- [ ] Include industrial crate requirement table.
- [ ] Include examples of good and bad grammar coverage.

**Exit criteria:** Industrial crate assets can be graded for family-specific construction coverage.

---

## Phase 4 — Semantic Construction Graph

**Purpose:** Represent construction decisions as a graph that validators, ShapeIR, surface maps, and future vision patches can all understand.

### 4.1 Define graph structures

- [ ] Add `ConstructionNode` type.
- [ ] Add `ConstructionEdge` type.
- [ ] Add `SemanticConstructionGraph` type.
- [ ] Support node types: primary volume, panel, trim, guard, rail, socket, mount, handle, hinge, fastener, decal zone, wear zone, material zone.
- [ ] Support edge types: attached_to, inset_into, wraps_around, mirrors, aligned_with, supports, cuts, contains, wears_on, material_bound_to.

### 4.2 Build graph from current asset/assembly metadata

- [ ] Implement best-effort extraction from existing asset graph and assembly blueprint.
- [ ] Add deterministic fallback for missing semantics.
- [ ] Emit graph metadata into build evidence/report.

### 4.3 Validate graph against family grammar

- [ ] Map industrial crate grammar requirements to graph patterns.
- [ ] Reward explicit seating relationships such as `inset_into`, `mounted_on`, `bracketed_by`.
- [ ] Penalize unattached/untyped details.

### 4.4 Tests

- [ ] Test graph serialization.
- [ ] Test extraction from simple mocked asset graph.
- [ ] Test industrial crate grammar over graph nodes/edges.

### 4.5 Docs

- [ ] Create `docs/asset-quality/semantic-construction-graph.md`.
- [ ] Include node/edge vocabulary.
- [ ] Include crate example graph.

**Exit criteria:** Lathe emits and validates a semantic construction graph for at least `industrial_crate`.

---

## Phase 5 — ShapeIR v2 Design + Compatibility Adapter

**Purpose:** Define richer semantic operations without breaking existing shape handoff.

### 5.1 Draft architecture doc

- [ ] Create `docs/architecture/shape-ir-v2.md`.
- [ ] Explain why v1 primitives are insufficient.
- [ ] Define compatibility strategy with `lathe.shape.intent_mesh_handoff_v1`.
- [ ] Define operation families: solids, booleans, edge control, repetition/detail, integration, wear/damage.

### 5.2 Add internal model

- [ ] Add ShapeIR v2 structures in `lathe/shape_ir.py` or a new adjacent module.
- [ ] Add deterministic serialization.
- [ ] Add validation for required fields.
- [ ] Add clear unsupported-op diagnostics.

### 5.3 Add v2-to-v1 adapter

- [ ] Lower supported v2 solids to current primitives.
- [ ] Approximate supported v2 operations where possible.
- [ ] Preserve original v2 op metadata in trace/report.
- [ ] Produce warnings for unsupported operations.

### 5.4 Tests

- [ ] Test `solid.rounded_box` serialization.
- [ ] Test `op.bevel` metadata roundtrip.
- [ ] Test adapter lowers simple crate body to v1 primitives.
- [ ] Test unsupported operation produces actionable warning.
- [ ] Test existing v1 assets still build.

**Exit criteria:** ShapeIR v2 exists internally and can coexist with the current v1 handoff.

---

## Phase 6 — Industrial Crate Grammar Lowering

**Purpose:** Turn the crate grammar into actual construction operations that improve geometry control.

### 6.1 Define crate construction recipe

- [ ] Body shell operation.
- [ ] Inset lid seam operation.
- [ ] Corner guard set operation.
- [ ] Front latch plate operation.
- [ ] Recessed handle/socket operations.
- [ ] Foot rail operations.
- [ ] Trim band operations.
- [ ] Fastener repeat operations.
- [ ] Warning/decal zone operations.

### 6.2 Lower recipe to ShapeIR v2

- [ ] Emit v2 operations for every recipe element.
- [ ] Attach semantic purposes to operations.
- [ ] Attach material/wear hooks where relevant.

### 6.3 Lower v2 to current pipeline

- [ ] Implement enough adapter support for crate MVP.
- [ ] Use existing scaffold/fusion mechanisms where possible.
- [ ] Preserve deterministic output.

### 6.4 Tests

- [ ] Test crate recipe emits expected operation names.
- [ ] Test crate recipe has required construction graph nodes.
- [ ] Test build report shows improved grammar coverage.
- [ ] Test old `industrial_crate.lth` can opt into or receive crate grammar defaults without syntax change.

### 6.5 Evidence

- [ ] Build `industrial_crate` before and after.
- [ ] Save comparison report under `.tmp_tests/asset_quality_crate_mvp` or docs evidence path.
- [ ] Record whether visual preview actually improves.

**Exit criteria:** Industrial crate generation has explicit construction logic instead of generic primitive attachment.

---

## Phase 7 — High-Poly / Low-Poly Reality Gate

**Purpose:** Stop treating high/low distinction as a shallow metric; make it a real artifact relationship.

### 7.1 Define required hero outputs

- [ ] Define expected paths for high-poly mesh, low proxy, runtime low, normal, AO, curvature, ID maps.
- [ ] Add additive manifest fields for high/low relation.
- [ ] Add skipped/unsupported status where the pipeline cannot yet emit a file.

### 7.2 Improve generation or reporting

- [ ] Emit separate high-poly detail source where available.
- [ ] Emit runtime low-poly target where available.
- [ ] Track triangle/part/material differences between high and low.
- [ ] Track which detail came from high-poly and which was baked/generated.

### 7.3 Validator gate

- [ ] Strengthen `highlow_distinction_quality` for hero families.
- [ ] Keep initial mode warning-only if strict failure would break current examples.
- [ ] Add strict mode later behind a flag/profile.

### 7.4 Tests

- [ ] Fake high/low pair should warn/fail depending on mode.
- [ ] Meaningful high/low fixture should pass.
- [ ] Missing external bake tools should produce truthful skipped evidence.

**Exit criteria:** Reports can distinguish true hero high/low workflow from fake or absent high/low evidence.

---

## Phase 8 — Material/Wear Graph v1

**Purpose:** Move surface generation from generic maps to semantic material storytelling.

### 8.1 Define material/wear graph model

- [ ] Add material graph structures.
- [ ] Support base material.
- [ ] Support underlayer.
- [ ] Support wear mask nodes.
- [ ] Support mask bindings to construction graph nodes/edges.

### 8.2 Implement MVP masks

- [ ] Convex edge wear.
- [ ] Concave grime.
- [ ] Lower/contact scuff.
- [ ] Handle/touch wear.
- [ ] Decal wear.

### 8.3 Integrate with surface runtime

- [ ] Add graph metadata to surface bundle.
- [ ] Drive existing map generation with semantic masks where possible.
- [ ] Keep fallback deterministic procedural maps.

### 8.4 Tests

- [ ] Test graph serialization.
- [ ] Test mask binding to crate corner guards/lid seam/handles.
- [ ] Test material/wear diagnostics detect uniform noise.

### 8.5 Docs

- [ ] Create `docs/asset-quality/material-wear-graph-v1.md`.
- [ ] Include painted steel crate example.

**Exit criteria:** Material/wear output is tied to semantic construction, not just random texture variation.

---

## Phase 9 — Preview and Evidence Upgrade

**Purpose:** Make evidence show final art quality, not just pipeline completion.

### 9.1 Preview modes

- [ ] Add/verify final beauty preview.
- [ ] Add/verify material-ID preview.
- [ ] Add/verify wireframe/topology preview.
- [ ] Add/verify normal/AO/curvature preview.
- [ ] Ensure final preview does not accidentally use debug material mode.

### 9.2 Comparison sheets

- [ ] Generate before/after sheets for crate MVP.
- [ ] Include fixed camera views: front, side, top, iso, hero.
- [ ] Include metric deltas and diagnostics deltas.

### 9.3 Report links

- [ ] Add preview paths to certification report.
- [ ] Add quality diagnostic links to evidence bundle.
- [ ] Add skipped reason if preview tool unavailable.

**Exit criteria:** Humans can quickly judge whether the upgrade actually improved visual quality.

---

## Phase 10 — Optional Vision Critique Loop

**Purpose:** Let rendered previews receive art-direction critique and convert that critique into semantic patches.

### 10.1 Define critique schema

- [ ] Create JSON schema or dataclass for critique.
- [ ] Include issue, severity, evidence view, recommendation, and semantic patch proposal.

### 10.2 Add deterministic fallback path

- [ ] Add no-network/no-vision deterministic critique path for tests.
- [ ] Ensure tests do not require external model calls.

### 10.3 Add optional vision provider path

- [ ] Wire optional vision critique only if configured.
- [ ] Never block deterministic builds when vision unavailable.
- [ ] Store provider/version/config in evidence.

### 10.4 Patch conversion

- [ ] Convert critique into design brief/grammar/ShapeIR v2 patch operations.
- [ ] Validate patch before applying.
- [ ] Store before/after metrics.

### 10.5 Tests

- [ ] Test critique schema validation.
- [ ] Test semantic patch application.
- [ ] Test unavailable provider produces skipped evidence.

**Exit criteria:** Vision can guide asset improvement through controlled semantic patches, not uncontrolled mesh mutation.

---

## Phase 11 — Reference/Moodboard Ingestion

**Purpose:** Ground asset generation in references, negative examples, silhouette targets, and material targets.

### 11.1 Internal reference board model

- [ ] Define reference board metadata.
- [ ] Support mood, silhouette, material, negative examples.
- [ ] Support provenance and local paths.

### 11.2 Parser/language strategy

- [ ] First implement internal/reference metadata without public syntax change.
- [ ] Draft experimental `.lth` syntax only after internal model works.
- [ ] If public syntax changes, update spec, grammar, schema, parser, normalizer, checker, examples, and tests together.

### 11.3 Tests

- [ ] Test missing reference warnings.
- [ ] Test local minimal reference fixtures.
- [ ] Test negative reference constraints appear in design brief.

**Exit criteria:** Lathe can carry reference intent through generation and reporting.

---

## Phase 12 — Standard Hard-Surface Kit Library

**Purpose:** Use reusable, curated procedural parts to raise quality without reinventing every bolt/hinge/vent.

### 12.1 Define kit metadata model

- [ ] Part name.
- [ ] Category.
- [ ] Mesh/procedural recipe.
- [ ] Material zones.
- [ ] Sockets.
- [ ] Placement constraints.
- [ ] Scale range.
- [ ] Allowed families.
- [ ] LOD behavior.
- [ ] Bake group.
- [ ] Preview/provenance.

### 12.2 Build MVP kit

- [ ] Fasteners.
- [ ] Corner guards.
- [ ] Handles.
- [ ] Rails.
- [ ] Warning labels/decals.

### 12.3 Integrate with crate grammar

- [ ] Use kit fasteners along trim/latch plates.
- [ ] Use kit corner guards on crate corners.
- [ ] Use kit handles in recessed/bracketed sockets.
- [ ] Use kit warning decals on semantic panels.

### 12.4 Tests

- [ ] Test deterministic kit lookup.
- [ ] Test allowed-family validation.
- [ ] Test missing kit part diagnostics.

**Exit criteria:** The crate MVP can use standard hard-surface parts deterministically and traceably.

---

## Phase 13 — Public `.lth` Controls / Experimental Syntax

**Purpose:** Expose the new power to creators and LLM authoring once internals are proven.

### 13.1 Decide stable vs experimental

- [ ] Keep new controls behind `experimental construction_grammar_v1` until proven.
- [ ] Decide which controls are ready for public docs.

### 13.2 Add syntax only if approved

If adding syntax:

- [ ] Update `spec/lathe-v0.1.md` or next spec.
- [ ] Update `grammar/lathe.lark`.
- [ ] Update `schema/lathe.schema.json`.
- [ ] Update parser.
- [ ] Update normalizer.
- [ ] Update resolver/checker.
- [ ] Update examples.
- [ ] Update tests.

### 13.3 Candidate syntax blocks

- [ ] `art_direction { ... }`
- [ ] `construction { ... }`
- [ ] `material_graph { ... }`
- [ ] `references { ... }`
- [ ] `kit { ... }`

### 13.4 LLM authoring docs

- [ ] Add prompt guidance for writing high-quality asset controls.
- [ ] Add bad-output examples.
- [ ] Add repair playbook for quality diagnostics.

**Exit criteria:** Public author controls exist only after internal pipeline support is proven and tested.

---

## Phase 14 — Golden Examples and Quality Certification

**Purpose:** Prove the upgrade with representative assets and stable evidence.

### 14.1 Golden industrial crate

- [ ] Create/upgrade golden crate example.
- [ ] Include design brief.
- [ ] Include family grammar coverage.
- [ ] Include semantic construction graph.
- [ ] Include high/low evidence.
- [ ] Include material/wear graph.
- [ ] Include final preview sheet.

### 14.2 Additional family smoke examples

- [ ] Mechanical door smoke example.
- [ ] Service cabinet smoke example.
- [ ] Terminal or supply chest smoke example.

### 14.3 Quality certification thresholds

- [ ] Define warning thresholds.
- [ ] Define strict thresholds.
- [ ] Keep strict mode opt-in until golden examples pass.

### 14.4 Evidence report

- [ ] Create `docs/asset-quality/quality-upgrade-evidence.md`.
- [ ] Include command results.
- [ ] Include report paths.
- [ ] Include preview paths.
- [ ] Include remaining limitations.

**Exit criteria:** Lathe has at least one clearly improved golden hard-surface asset with truthful evidence.

---

## Phase 15 — CI / Regression Gates

**Purpose:** Prevent the quality pipeline from drifting or silently degrading.

### 15.1 Fast tests

- [ ] Add fast unit tests for diagnostics/IR/grammar.
- [ ] Add fast CLI smoke for industrial crate check/build if runtime is reasonable.

### 15.2 Snapshot stability

- [ ] Add stable JSON snapshot tests for report additions.
- [ ] Avoid brittle image-pixel snapshots unless renderer is deterministic.

### 15.3 Optional lanes

- [ ] Add optional preview/render lane if dependencies exist.
- [ ] Add optional Blender/export lane only if truthful runtime exists.
- [ ] Add optional vision lane only if configured.

### 15.4 Docs

- [ ] Document CI lanes and skip reasons.

**Exit criteria:** Quality infrastructure stays stable through future changes.

---

## First Implementation Wave — Ready-to-Paste Codex Prompt

```text
You are working in the Lathe repository root.

Goal: begin the Lathe asset-quality upgrade by implementing Phase 1 from docs/asset-quality/improvement-tasklist.md: deterministic visual-quality diagnostics that catch prototype/blockout-looking hero assets without changing public .lth syntax.

Read first:
- AGENTS.md
- docs/asset-quality/lathe-asset-quality-upgrade-spec.md
- docs/asset-quality/improvement-tasklist.md
- docs/asset-quality/lathe-next-level-asset-quality-roadmap.md
- lathe/validators/visual_quality.py
- relevant existing tests under tests/

Constraints:
- Preserve existing .lth compatibility.
- Preserve lathe.shape.intent_mesh_handoff_v1.
- Add report fields additively; do not remove or rename existing fields.
- Do not fake Blender/Roblox/external runtime evidence.
- Do not require external services.
- Keep vision/external critique out of this first wave.

Implement:
1. Add an additive quality_diagnostics object to visual/certification reports.
2. Add deterministic metrics/proxies:
   - random_triangulation_penalty
   - debug_material_preview_penalty
   - highlow_fake_detail_penalty
   - attachment_seating_quality
   - primary_secondary_tertiary_balance
3. Add human-readable warnings/recommendations for current known failure modes:
   - noisy diagonal topology on large flat faces
   - final preview/materials look like debug or material-ID colors
   - hero high/low distinction is fake or weak
   - attachments appear stuck-on or under-integrated
   - asset lacks medium-scale construction hierarchy
4. Add unit tests with small fixtures/mocked reports for weak and healthy cases.
5. Add or update integration/report compatibility tests so existing consumers are not broken.
6. Add docs/asset-quality/quality-diagnostics-v1.md explaining metrics, thresholds, limitations, and improvement guidance.

Verification:
- Run the narrowest new tests.
- Run existing visual/certification tests.
- Run a deterministic build/check for examples/industrial_crate.lth if feasible.
- Report exact commands and results.

Do not proceed into ShapeIR v2, grammar syntax, material graphs, or vision loop in this wave.
```

---

## Progress Log

Use this section as implementation proceeds.

| Date | Phase | Change | Evidence | Notes |
|---|---|---|---|---|
| 2026-04-29 | Planning | Created upgrade spec and improvement tasklist | `docs/asset-quality/lathe-asset-quality-upgrade-spec.md`, `docs/asset-quality/improvement-tasklist.md` | Ready for Phase 1 implementation |
| 2026-04-29 | Phase 0 | Baseline captured, contract test added, blockers inventoried, `lathe/asset_quality/` package scaffolded | `docs/asset-quality/baseline-evidence.md`, `docs/asset-quality/phase0-blockers.md`, `tests/unit/test_asset_quality_baseline_report_shape.py`, `lathe/asset_quality/__init__.py` | Both hero baselines pass: industrial_crate 0.886/0.84, mechanical_door 0.884/0.84. 5 new contract tests + 24 existing report tests green. Critical user decision pending: B-05 commit-strategy (Wonder + readiness work uncommitted in same tree). |
