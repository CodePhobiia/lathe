# Project Wonder Readiness Task List

Created: 2026-04-28

Purpose: make Lathe ready to serve as the execution substrate for Project
Wonder.

This is not a launch checklist for the current asset compiler. It is the
step-by-step implementation plan for evolving Lathe from an asset/family
compiler into a persistent multi-object scene runtime that can represent,
mutate, render, inspect, remember, branch, validate, and export Wonder scenes.

A task is complete only when it has durable evidence: committed code, tests,
docs, schemas, example artifacts, benchmark results, CI output, or an explicit
decision record. Do not check a task because the idea exists in prose.

## Current Status

Wonder readiness score: **4/10 for full Wonder runtime readiness; core/proxy
alpha gate passed locally**.

Current milestone: **deterministic core/proxy alpha gate is locally
decision-ready; full Wonder runtime/export readiness remains blocked by
external runtime evidence and optional lane scope decisions**.

Current blocker: the deterministic Wonder contract, scene package, proxy
render/export, patch, repair, curiosity, example catalog, before/after proxy
comparison, local CI scripts, alpha-gate report bundle, and Roblox manifest
lanes are green in the local working tree. The core/proxy alpha decision still
needs human approval and hosted CI confirmation. POSIX helper validation,
fresh-clone or hosted CI confirmation, Blender-backed scene rendering, Roblox
execution, and external-viewer validation remain open for full Wonder runtime
readiness when those lanes are in scope.

Status rules:

- `[x]` means implemented, tested, and evidenced.
- `[ ]` means not done, not verified, or implemented without durable evidence.
- If a task has local code but no clean validation evidence, leave the task
  unchecked and add an evidence note instead of marking it complete.

## Current Recommended Next PR

Goal: make the current deterministic Wonder proxy path truthful from a clean
checkout and a POSIX-capable environment before expanding final renderer/export
claims.

Recommended scope:

- [x] Ensure `lathe wonder` validation commands do not require optional mesh,
  Blender, provider, or learned-shape dependencies such as `trimesh`.
- [x] Refactor or lazily import `lathe.cli` command modules so lightweight
  contract commands can run in minimal environments.
- [x] Add `docs/wonder-readiness/evidence.md`.
- [x] Add `docs/wonder-readiness/status.md` with current readiness score,
  implemented capabilities, known blockers, and next milestone.
- [x] Add `docs/wonder-readiness/glossary.md` defining Dream Brief, Scene Graph,
  scene object, asset, family, kit, region, world memory, scene package, branch,
  render inspection, and Wonder report.
- [x] Add `lathe wonder capabilities` or `lathe wonder status` with
  machine-readable capability flags.
- [x] Add semantic Scene Graph validation skeleton.
- [x] Add `lathe wonder check-scene-graph <scene_graph.json>`.
- [x] Add tests for duplicate object IDs, missing region references, invalid
  relationship endpoints, missing required elements, and unsafe artifact paths.
- [x] Run `python -m pytest -q tests/unit/test_wonder_contracts.py` and record
  the command output in `docs/wonder-readiness/evidence.md`.
- [x] Run every `lathe wonder validate-*` command against the alchemist
  observatory example and record the command output in evidence.

Recommended-next-PR evidence note, 2026-04-29: a Git-backed review snapshot of
the current working tree passed the Wonder contract tests, docs/security hygiene
tests, semantic Scene Graph tests, every Alchemist Observatory `lathe wonder`
validator, `lathe wonder capabilities`, and `lathe wonder status`. See
`docs/wonder-readiness/evidence.md`.

Worker C evidence note, 2026-04-28: this docs-only pass adds local readiness
tracking files under `docs/wonder-readiness/` for evidence, status, and
glossary. It did not check any Milestone A task boxes at the time of that pass.
Superseded for the recommended-next-PR scope by the 2026-04-29 review-snapshot
evidence above.

Milestone A implementation note, 2026-04-28: local focused tests now cover the
exception inventory fix, Wonder contract validators, optional-dependency import
guard, `lathe wonder check-scene-graph`, docs static audit, and marker inventory.
Superseded for the recommended-next-PR scope by the 2026-04-29 review-snapshot
evidence above.

Phase 0 evidence note, 2026-04-28: the full local test suite, doctor,
shape-provider listing/probing, Windows smoke script, canonical courier drone
commands, one generate build, and one reconstruct build all passed locally.
`lathe wonder capabilities` also exists locally. Superseded for Phase 0 by the
2026-04-29 review-snapshot evidence below.

Phase 1/2 evidence note, 2026-04-28: generated Wonder schema reference docs,
broader Scene Graph semantic checks, and PowerShell Wonder validation helper
scripts pass locally. The Bash helper still needs a POSIX runtime check, and
brief-to-scene consistency checks now pass locally through the helper.

Phase 33-36 evidence note, 2026-04-28: local PowerShell
`scripts/demo_wonder_seed_scene.ps1` passed against the Alchemist Observatory
seed and recorded the current proxy path through contracts, brief lowering,
source bridge roundtrip, scene plan, scene assembly, proxy package build,
proxy PNG renders, declared proxy GLB export, render-inspection contract repair,
`more_sacred` patch application, curiosity expansion, package validation, and
proxy artifact magic-byte evidence. No Phase 33-36 boxes are checked because the
Bash demo, fresh-clone or CI confirmation, before/after image comparison,
Blender-backed scene rendering, Roblox export gates, and external-viewer
validation remain open.

Task audit note, 2026-04-29: task boxes were re-audited against the current
working tree. Checked items now mean the repo has concrete implementation plus
test, command, doc, schema, example, or evidence coverage for the exact task
wording. Minimal Phase 6B `.lth` scene syntax and Phase 9 scene
materialization are now checked; advanced scene syntax beyond the Phase 6B
subset, full generated-asset certification, POSIX helper proof, Blender-backed
scene rendering, Roblox execution, external viewer validation, and Wonder
alpha-gate confirmations remain unchecked.

Heartbeat evidence note, 2026-04-29: local `lathe wonder status` now emits
machine-readable readiness score, evidence state, alpha-gate blockers, open
evidence gaps, and capability flags. This improves the "capabilities or status"
task surface. Superseded for the recommended-next-PR scope by the 2026-04-29
review-snapshot evidence above.

Heartbeat validation note, 2026-04-29: local
`powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1`
passed after adding `lathe wonder status` to the helper. A follow-up run with
`-WorkDir .tmp_tests\wonder_validate_heartbeat_final` passed after adding
per-run helper output isolation, unique atomic scene artifact writes, and
broader lightweight CLI import guards. The helper reported 190 focused tests
passed and exercised the deterministic proxy render/export, scene package,
repair, curiosity, source roundtrip, benchmark, style/layout,
provenance/game-readiness, and Roblox manifest lanes. This is still local
evidence, not POSIX evidence. The full local test suite also passed after these
changes: 1660 passed, 10 skipped, 127 deselected, 2 warnings.

## Milestones

### Milestone A - Wonder Contracts Green

Phases: 0-2.

Exit criteria:

- Existing Lathe baseline is stable enough for Wonder work.
- Wonder schemas validate from a clean checkout.
- `lathe wonder` commands run without optional heavy dependencies.
- Alchemist Observatory example contracts validate.
- Semantic Scene Graph checks catch duplicate IDs, missing references, and unsafe paths.
- Evidence exists under `docs/wonder-readiness/evidence.md`.

### Milestone B - Scene Package Prototype

Phases: 3-5.

Exit criteria:

- Dream Brief can lower to an initial Scene Graph through a deterministic offline fallback.
- Scene package layout exists and validates.
- World memory schema and append/inspect flow exist.
- Object IDs survive package write/read.

### Milestone C - Scene Source Alpha

Phases: 6-8.

Exit criteria:

- Minimal additive `.lth` scene syntax is accepted behind an experimental boundary.
- Scene Graph -> source -> Scene Graph roundtrips preserve stable IDs.
- Multi-asset scene plans can be generated deterministically.

### Milestone D - Preview Build And Render

Phases: 9-13.

Exit criteria:

- Alchemist Observatory builds in preview mode.
- Preview mode can use deterministic proxy geometry when full asset generation is unavailable.
- Reveal and topdown renders are produced.
- GLB/Blender/USD export path is at least partially proven with object metadata.

### Milestone E - Wonder Loop

Phases: 14-22.

Exit criteria:

- Scene-level validators produce machine-readable and human-readable reports.
- Render inspection can produce patch proposals.
- A semantic scene patch can be applied while preserving continuity.
- One curiosity anchor can be expanded into a new branch or scene version.
- Style packs, instance reuse, layout, lighting, camera, curiosity, and hidden-state
  capabilities are validated as part of the scene loop.

### Milestone F - Roblox Lane

Phases: 23-25.

Exit criteria:

- One Roblox-compatible kit or scene passes Roblox profile validators.
- Roblox manifest/export instructions exist.
- Roblox constraints are represented in contracts and validation output.
- Standard library expansion includes enough kits, props, fixtures, and style packs
  to prove the Roblox lane with reusable assets.

### Milestone G - Authoring, Safety, And Runtime Boundaries

Phases: 26-30.

Exit criteria:

- Environment modules and terrain chunks are available for scene composition.
- LLM authoring APIs and diagnostics are structured, testable, and bounded.
- Security, safety, and provenance metadata are represented in contracts and reports.
- Service API contracts are documented without turning Lathe into the Project Wonder app.
- Performance and cost budgets are defined and measured for preview workflows.

### Milestone H - Wonder Alpha Gate

Phases: 31-36 and Final Task.

Exit criteria:

- The one-command golden path passes from a clean checkout.
- At least one scene builds, renders, patches, expands curiosity, and exports.
- Project Wonder can call Lathe through JSON contracts and CLI outputs without bypassing Lathe contracts.

## Explicit Deferrals Before Milestone A Is Green

Do not implement these until the contract layer and semantic validation are clean,
evidenced, and reviewed:

- advanced `.lth` scene grammar beyond the Phase 6B subset
- scene variants
- branch/merge system
- Blender render passes
- Roblox `.rbxmx` writer
- Roblox Studio plugin
- SaaS/API server implementation
- accounts, payments, galleries, chat UX, or other Project Wonder product concerns
- open-world terrain generation
- gameplay scripting
- character animation, rigs, cloth, fluids, or destruction simulation

Service API contracts may be documented later, but REST services are not required
for the first local Project Wonder alpha if CLI/file-based orchestration is stable.

## Readiness Definition

Lathe is Project Wonder-ready when a clean checkout can run one golden path:

```text
user prompt
-> Dream Brief JSON
-> Scene Graph JSON
-> checked and normalized scene source
-> multi-asset scene plan
-> preview scene build
-> canonical renders and render passes
-> render inspection report
-> semantic scene patch
-> continuity-preserving rebuild
-> curiosity expansion
-> final scene package and exports
```

The minimum proven scene is a persistent single-scene world seed such as a room,
courtyard, shrine, lab, street corner, or Roblox shop interior. Lathe does not
need to become a game engine or open-world simulator before Project Wonder can
start.

## Completion Rules

- [x] Maintain this file as the source of truth for Wonder-readiness work.
- [x] Every completed task must cite evidence in a future `docs/wonder-readiness/evidence.md`.
- [x] Every schema change must include schema tests and at least one example.
- [x] Every `.lth` language change must update spec, grammar, schema, parser,
  normalizer, resolver, checker, planner, examples, and tests together.
- [x] Every scene build feature must include a deterministic offline path.
- [x] Every provider-backed feature must include mocked tests and failure-mode tests.
- [x] Every public CLI command must be documented and covered by CLI tests.
- [x] Every generated artifact format must have a schema or contract test.
- [x] Every validation claim must be backed by an actual command result.
- [x] Keep Lathe/Project Wonder boundaries explicit: Lathe owns contracts,
  compiler/runtime, validation, render/export artifacts, and manifests;
  Project Wonder owns chat UX, user accounts, product memory, model routing,
  galleries, payments, and cloud product experience.

Completion-rules audit note, 2026-04-29: the rules above are satisfied for the
current checked task set by local full-suite validation, focused Wonder
example/source validation, and evidence-trace coverage. External runtime and
human-decision gates remain unchecked below.

## Phase 0 - Stabilize The Current Lathe Baseline

Goal: make the existing asset compiler trustworthy before expanding it.

- [x] Record current branch, commit, Python version, OS, and dirty tree state.
- [x] Classify all existing untracked and modified files as owned, generated,
  user work, or obsolete.
- [x] Resolve the existing `tests/unit/test_exception_inventory.py` pass-line
  mismatch without hiding the inventory check.
- [x] Re-run `python -m pytest -q` after inventory cleanup and record results.
- [x] Run `python -m lathe.cli doctor --json` from a clean environment.
- [x] Confirm `trimesh` is installed through the normal project dependency path.
- [x] Confirm `python -m lathe.cli doctor` does not fail with
  `ModuleNotFoundError: No module named 'trimesh'`.
- [x] Run `python -m lathe.cli shape-providers`.
- [x] Run `python -m lathe.cli probe-providers --runtime-config examples/runtime_configs/auto_learned.json`.
- [x] Run `scripts/lathe_smoke.sh` on Linux or `scripts/lathe_smoke.ps1` on Windows.
- [x] Run `python -m lathe.cli normalize examples/courier_drone.lth`.
- [x] Run `python -m lathe.cli check examples/courier_drone.lth`.
- [x] Run `python -m lathe.cli plan examples/courier_drone.lth courier_drone`.
- [x] Run `python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist`.
- [x] Run at least one canonical `generate` example.
- [x] Run at least one canonical `reconstruct` example.
- [x] Verify canonical examples still pass checker and build path.
- [x] Verify docs do not claim Project Wonder readiness yet.
- [x] Add `docs/wonder-readiness/evidence.md` for all future evidence.
- [x] Add `docs/wonder-readiness/status.md` with current readiness score and known gaps.
- [x] Add an ADR for the Wonder Layer boundary.
- [x] Freeze the current stable asset-stage contract as
  `lathe.shape.intent_mesh_handoff_v1`.
- [x] Confirm no Wonder work breaks existing asset source compatibility.
- [x] Add CI job or local script for Wonder-specific validation commands.
- [x] Add a "pre-Wonder baseline" changelog entry or release note.

Phase 0 evidence note, 2026-04-29: a Git-backed review snapshot passed the full
test suite, doctor, dependency import, provider listing/probing, Windows smoke,
canonical courier normalize/check/plan/build, one generate build, one
reconstruct build, and Wonder validation helper. The POSIX helpers remain open
because this Windows environment routes `bash` to unavailable WSL.

## Phase 1 - Schema-First Wonder Contracts

Goal: define strict JSON bridges before changing core `.lth` syntax.

- [x] Add `schema/dream_brief.schema.json`.
- [x] Add `schema/scene_graph.schema.json`.
- [x] Add `schema/scene_patch.schema.json`.
- [x] Add `schema/render_inspection.schema.json`.
- [x] Add `lathe.wonder` contract loading and validation helpers.
- [x] Add `lathe wonder schemas`.
- [x] Add `lathe wonder schema <contract>`.
- [x] Add `lathe wonder validate-brief <file>`.
- [x] Add `lathe wonder validate-scene <file>`.
- [x] Add `lathe wonder validate-patch <file>`.
- [x] Add `lathe wonder validate-render-inspection <file>`.
- [x] Add Wonder contract trust-boundary metadata.
- [x] Add unit tests for schemas and the alchemist observatory examples.
- [x] Add `examples/wonder/alchemist_observatory/prompt.txt`.
- [x] Add `examples/wonder/alchemist_observatory/dream_brief.json`.
- [x] Add `examples/wonder/alchemist_observatory/scene_graph.json`.
- [x] Add `examples/wonder/alchemist_observatory/scene_patch_more_sacred.json`.
- [x] Add `examples/wonder/alchemist_observatory/render_inspection.example.json`.
- [x] Add expected scene manifest and Wonder report example artifacts.
- [x] Add first Wonder readiness docs.

Implementation note: several Phase 1 items exist locally, but they remain
unchecked until `docs/wonder-readiness/evidence.md` records matching
task-specific validation output.

Worker C evidence note, 2026-04-28: Phase 1 contract schemas, local Wonder
helpers, local CLI commands, and Alchemist Observatory examples are documented
as present in the working tree. They remain unchecked here until matching
validation commands are recorded in the evidence ledger.

- [x] Add schema docs generated from the Wonder schemas.
- [ ] Add Phase 1 evidence note proving every checked task above passed from a clean checkout.
- [x] If clean validation evidence is missing, keep Phase 1 `[x]` items explicitly scoped to local/review-snapshot evidence and leave the clean-checkout evidence gate unchecked.
- [x] Ensure `lathe wonder` validation commands do not require optional mesh, Blender, provider, or learned-shape dependencies such as `trimesh`.
- [x] Refactor or lazily import `lathe.cli` command modules so lightweight Wonder contract commands can run in minimal environments.
- [x] Add `docs/wonder-readiness/evidence.md`.
- [x] Add `docs/wonder-readiness/status.md`.
- [x] Add `docs/wonder-readiness/glossary.md`.
- [x] Add `lathe wonder capabilities` or `lathe wonder status`.
- [x] Add schema versioning rules for all `lathe.*.v1` Wonder contracts.
- [x] Add compatibility policy for schema additions, removals, and migrations.
- [x] Add schema-version compatibility tests that reject unsupported future
  Scene Graph versions with a clear diagnostic.
- [x] Add `schema/world_memory.schema.json`.
- [x] Add `schema/scene_manifest.schema.json`.
- [x] Add `schema/wonder_report.schema.json`.
- [x] Add `schema/scene_package_manifest.schema.json`.
- [x] Add `schema/scene_branch.schema.json`.
- [x] Add `schema/scene_diff.schema.json`.
- [x] Add `schema/scene_repair_report.schema.json`.
- [x] Add `schema/scene_quality_report.schema.json`.
- [x] Add `schema/asset_provenance_scene.schema.json`.
- [x] Add `schema/roblox_profile.schema.json`.
- [x] Add schema tests for all new Wonder schemas.
- [x] Add CLI validators for all new Wonder schemas.
- [x] Add negative schema fixtures for invalid IDs, missing objects, and bad patch scopes.
- [x] Add schema roundtrip fixtures for valid JSON serialization.
- [x] Add docs explaining why JSON-first authoring precedes `.lth` scene syntax.
- [x] Define MVP Scene Graph subset for `single_room` scenes: one scene, one region, 4-10 objects, one style bible, material list, reveal camera, light, two curiosity anchors, and one export target.
- [x] Ensure the Wonder golden path can run without external LLM/provider credentials.

## Phase 2 - Scene Graph Semantic Validation

Goal: move beyond JSON shape validation into scene-aware contract checks.

- [x] Create `lathe/scene/` package.
- [x] Create `lathe/scene/ids.py` for stable scene ID helpers.
- [x] Create `lathe/scene/graph.py` for typed Scene Graph accessors.
- [x] Create `lathe/scene/diagnostics.py` for scene diagnostic payloads.
- [x] Add scene diagnostic code namespace, for example `S1001`.
- [x] Validate `scene_id` uniqueness within a scene package.
- [x] Validate every `region_id` is unique.
- [x] Validate every `object_id` is unique.
- [x] Validate every `camera_id` is unique.
- [x] Validate every `light_id` is unique.
- [x] Validate every `material_id` is unique.
- [x] Validate every `curiosity_anchor.anchor_id` is unique.
- [x] Validate every `hidden_state.hidden_id` is unique.
- [x] Validate every object region exists.
- [x] Validate every material binding references an existing material.
- [x] Validate every relationship endpoint exists.
- [x] Validate every camera target exists.
- [x] Validate every light target exists when present.
- [x] Validate every curiosity anchor attachment exists.
- [x] Validate every hidden state attachment exists.
- [x] Validate every affordance `reveals` target exists.
- [x] Validate every build artifact path is relative and safe.
- [x] Validate every export path is relative and safe.
- [x] Validate required Dream Brief elements are represented in Scene Graph.
- [x] Validate Scene Graph `brief_id` matches the input Dream Brief when provided.
- [x] Validate stable IDs are not regenerated during normalization.
- [x] Add `lathe wonder check-scene-graph <scene_graph.json>`.
- [x] Add `lathe wonder check-brief-scene <brief.json> <scene_graph.json>`.
- [x] Add machine-readable diagnostics for all semantic validator failures.
- [x] Add human-readable summary output for scene semantic validation.
- [x] Add tests for missing region references.
- [x] Add tests for duplicate object IDs.
- [x] Add tests for invalid relationship endpoints.
- [x] Add tests for missing required elements.
- [x] Add tests for unsafe artifact paths.
- [x] Add docs for scene semantic diagnostics.

## Phase 3 - Dream Brief To Scene Graph Lowering

Goal: provide a deterministic offline fallback and contract-compatible lowering
path from structured creative briefs into initial Scene Graphs. Project Wonder
may later use frontier models to author richer Scene Graphs directly; Lathe must
validate those LLM-authored graphs and keep the deterministic fallback reliable
for tests, demos, and CI.

- [x] Create `lathe/wonder/brief.py`.
- [x] Create `lathe/wonder/decompose.py`.
- [x] Define deterministic decomposition output model.
- [x] Add `lathe wonder decompose-brief <brief.json>`.
- [x] Add `lathe wonder brief-to-scene <brief.json> --out <scene_graph.json>`.
- [x] Generate stable `region_*` IDs from brief elements.
- [x] Generate stable `obj_*` IDs from required objects.
- [x] Generate stable camera IDs from camera intents.
- [x] Generate style bible from brief style fields.
- [x] Generate initial material list from brief palette/materials.
- [x] Generate at least one reveal camera when no camera is supplied.
- [x] Generate at least one debug/topdown camera.
- [x] Generate at least two curiosity anchors when brief supports them.
- [x] Generate hidden state entries for curiosity anchors.
- [x] Generate initial layout bounds for `single_room`.
- [x] Generate initial layout bounds for `small_courtyard`.
- [x] Generate initial layout bounds for `street_corner`.
- [x] Generate initial layout bounds for `modular_kit`.
- [x] Add deterministic fallback asset-family selection.
- [x] Add asset role classification for architecture.
- [x] Add asset role classification for hero props.
- [x] Add asset role classification for dressing props.
- [x] Add asset role classification for light fixtures.
- [x] Add asset role classification for interactive objects.
- [x] Add `avoid` propagation into scene style bible.
- [x] Add export-target propagation into Scene Graph exports.
- [x] Add tests for alchemist observatory brief lowering.
- [x] Add tests for underwater train station brief lowering.
- [x] Add tests for abandoned Roblox mall brief lowering.
- [x] Add tests for prompt changes producing deterministic IDs.
- [x] Add docs for Dream Brief authoring rules.
- [x] Add docs for decomposition heuristics and limitations.

## Phase 4 - Scene Package Format

Goal: define the folder/package layout Project Wonder can store, reload, branch,
and share.

- [x] Define canonical `.lathepkg` scene package directory layout.
- [x] Add schema for `manifest.json` inside scene package.
- [x] Add `source/` layout with Dream Brief, Scene Graph, scene source, and generated asset sources.
- [x] Add `graph/` layout with normalized Scene Graph and world memory.
- [x] Add `builds/preview/` layout.
- [x] Add `builds/final/` layout.
- [x] Add `renders/` layout for beauty renders.
- [x] Add `render_passes/` layout for depth, normal, object ID, material ID, and wireframe.
- [x] Add `exports/` layout.
- [x] Add `reports/` layout.
- [x] Add `cache/` layout for per-asset reuse metadata.
- [x] Add `lathe scene package init`.
- [x] Add `lathe scene package inspect`.
- [x] Add `lathe scene package validate`.
- [x] Add package manifest writer.
- [x] Add package manifest reader.
- [x] Add package path safety checks.
- [x] Add package schema validation tests.
- [x] Add tests that object IDs survive package write/read.
- [x] Add tests that package validation rejects missing required files.
- [x] Add docs for `.lathepkg`.
- [x] Add example package manifest under alchemist observatory.

## Phase 5 - World Memory Model

Goal: preserve scene facts, user decisions, hidden lore, branches, patches, and
validation history.

- [x] Add `schema/world_memory.schema.json`.
- [x] Create `lathe/scene/memory.py`.
- [x] Define memory event kinds: fact, decision, hidden_state, branch, patch,
  validation, render, export, rejection.
- [x] Define memory scope values: scene, region, object, camera, material,
  curiosity_anchor, export.
- [x] Validate memory event IDs.
- [x] Validate memory event affected IDs exist in Scene Graph.
- [x] Add `lathe scene memory inspect <package>`.
- [x] Add `lathe scene memory append <package> <event.json>`.
- [x] Add memory append idempotency checks.
- [x] Add memory redaction checks for secrets and PII.
- [x] Add memory event provenance fields.
- [x] Add world memory output to scene package builds.
- [x] Add tests for hidden-state memory preservation.
- [x] Add tests for user decision recording.
- [x] Add tests for rejected patch recording.
- [x] Add docs for what Lathe memory owns versus Project Wonder app memory.

## Phase 6A - Scene Source Language Design ADR

Goal: design first-class `.lth` scene syntax without destabilizing asset source.
This phase is documentation and decision-making only; do not change parser,
grammar, normalizer, resolver, checker, or formatter here.

- [x] Write `docs/wonder-readiness/06_scene_language_design.md`.
- [x] Add ADR for experimental scene source language.
- [x] Decide whether scene syntax is v0.3 experimental or behind a feature flag.
- [x] Define the minimum viable scene syntax subset.
- [x] Map every proposed source construct to Scene Graph fields.
- [x] Decide which fields remain JSON/metadata-only for v0.3.
- [x] Decide which constructs are deferred beyond the first scene syntax implementation.
- [x] Add syntax proposal for `scene`.
- [x] Add syntax proposal for `region`.
- [x] Add syntax proposal for scene-local `object`.
- [x] Add syntax proposal for `relationship`.
- [x] Add syntax proposal for camera and light references.
- [x] Add syntax proposal for style references.
- [x] Add syntax proposal for scene-level `export` target.
- [x] Add three complete scene syntax examples.
- [x] Add docs explaining scene source is additive and asset syntax remains stable.

## Phase 6B - Minimal Scene Source Language Implementation

Goal: implement only the minimum viable additive `.lth` scene syntax after the
ADR is accepted and Milestone A is green.

- [x] Update `spec/lathe-v0.1.md` with experimental scene declarations.
- [x] Add syntax for `scene`.
- [x] Add syntax for `region`.
- [x] Add syntax for scene-local `object`.
- [x] Add syntax for `relationship`.
- [x] Add syntax for minimal camera references.
- [x] Add syntax for minimal light references.
- [x] Add syntax for style references.
- [x] Add syntax for scene-level `export`.
- [x] Defer `scene_variant` syntax until branch/version model is implemented.
- [x] Defer full game-readiness metadata until Roblox/profile validators exist.
- [x] Defer sockets, snap points, and detailed collision metadata until instance/export flows exist.
- [x] Defer provenance source syntax until provenance schema and validators exist.
- [x] Defer advanced layout constraints until the deterministic layout solver exists.
- [x] Add syntax examples in spec.
- [x] Update `grammar/lathe.lark`.
- [x] Update parser transformer blocks.
- [x] Update parser fast path or document why disabled for scene syntax.
- [x] Update normalizer defaults.
- [x] Update normalized AST schema.
- [x] Update resolver for scene declarations.
- [x] Update checker for scene declarations.
- [x] Update planner to ignore scene declarations until scene planning is invoked.
- [x] Update formatter for scene syntax.
- [x] Add parser tests for minimal scene.
- [x] Add parser tests for full alchemist observatory scene.
- [x] Add normalizer tests for scene defaults.
- [x] Add resolver tests for scene references.
- [x] Add checker tests for scene semantic errors.
- [x] Add formatter snapshot tests.
- [x] Add docs explaining scene source is additive and asset syntax remains stable.

## Phase 7 - Scene Graph To Source And Source To Scene Graph

Goal: make JSON-first model authoring and human-editable `.lth` scenes roundtrip.

- [x] Add `lathe scene-graph-to-source <scene_graph.json> --out <scene.lth>`.
- [x] Add `lathe source-to-scene-graph <scene.lth> --out <scene_graph.json>`.
- [x] Preserve all stable IDs during Scene Graph to source lowering.
- [x] Preserve all stable IDs during source to Scene Graph extraction.
- [x] Preserve object transform precision.
- [x] Preserve material bindings.
- [x] Preserve curiosity anchors.
- [x] Preserve hidden state.
- [x] Preserve cameras and lighting plans.
- [x] Preserve platform constraints.
- [x] Preserve asset provenance.
- [x] Add roundtrip test: Scene Graph -> `.lth` -> Scene Graph.
- [x] Add roundtrip test: `.lth` -> Scene Graph -> `.lth`.
- [x] Add tests that comments are not required for semantic preservation.
- [x] Add diagnostics when Scene Graph contains fields not representable in source.
- [x] Add docs for JSON-first authoring flow.
- [x] Add model-facing examples of good Scene Graph JSON and generated `.lth`.

## Phase 8 - Multi-Asset Scene Planning

Goal: plan a scene as a graph of asset builds, cached assets, and assembly work.

- [x] Create `lathe/scene/planner.py`.
- [x] Define scene plan schema.
- [x] Add `lathe scene check <scene.lth or scene_graph.json>`.
- [x] Add `lathe scene plan <scene.lth or scene_graph.json>`.
- [x] Resolve all objects to asset, family, kit, or generated-asset tasks.
- [x] Detect missing asset/family/kit references.
- [x] Decide when an object instance can reuse an existing asset build.
- [x] Decide when instance overrides require a variant build.
- [x] Add dependency graph for asset builds.
- [x] Add dependency graph for materials.
- [x] Add dependency graph for scene assembly.
- [x] Add dependency graph for renders.
- [x] Add preview/final mode plan differences.
- [x] Add cache key strategy for assets in scenes.
- [x] Add asset build reuse across objects.
- [x] Add asset build reuse across scene branches.
- [x] Add deterministic ordering of scene plan tasks.
- [x] Add warnings for object count or complexity budget.
- [x] Add tests for a scene with four objects.
- [x] Add tests for repeated candle instances using one cached asset.
- [x] Add tests for per-instance overrides.
- [x] Add tests for missing asset reference diagnostics.
- [x] Add docs for scene plan output.

## Phase 9 - Scene Asset Generation And Lowering

Goal: use current Lathe asset capabilities to generate scene objects before
full procedural scene runtime exists.

- [x] Create generated asset source directory convention.
- [x] Add `lathe scene materialize <scene> --out <dir>`.
- [x] Lower each object into an asset source or asset reference.
- [x] Lower architecture objects into environment module assets.
- [x] Lower hero props into hard-surface prop assets.
- [x] Lower mechanical doors and mechanisms into mechanical assembly assets.
- [x] Lower repeated dressing props into instance-friendly asset sources.
- [x] Lower material bindings into existing material declarations when possible.
- [x] Add generated asset naming rules.
- [x] Add collision-safe generated source paths.
- [x] Add generated source provenance comments or metadata.
- [x] Add checker integration for generated asset sources.
- [x] Add plan integration for generated asset sources.
- [x] Add build integration for generated asset sources.
- [x] Add deterministic fallback geometry for scene objects.
- [x] Add tests for generated asset source validity.
- [x] Add tests that generated assets pass `lathe check`.
- [x] Add tests that generated assets produce build plans.
- [x] Add docs for scene-to-asset decomposition.

## Phase 10 - Scene Build Pipeline

Goal: build a full scene package, not just individual assets.

- [x] Create `lathe/scene/executor.py`.
- [x] Add `lathe scene build <scene> --out <dist_scene>`.
- [x] Add `--mode preview`.
- [x] Add `--mode final`.
- [x] Add `--runtime-config` support.
- [x] Add `--deterministic` support.
- [x] Add `--allow-fallback` support where provider calls are involved.
- [x] Add `--strict` support for provider and scene validation failures.
- [x] Build all missing assets in dependency order.
- [x] Reuse cached assets when inputs match.
- [x] Write per-object asset build records.
- [x] Assemble objects into scene manifest.
- [x] Write `scene_graph.normalized.json`.
- [x] Write `scene_manifest.json`.
- [x] Write `world_memory.json`.
- [x] Write `reports/validation_report.json`.
- [x] Write `reports/wonder_report.json`.
- [x] Write `build_report.json` for scene-level build.
- [x] Include downstream asset build reports.
- [x] Include scene plan in trace output.
- [x] Include provider/fallback decisions in trace output.
- [x] Fail loudly on missing asset build artifacts.
- [x] Fail loudly on invalid scene graph after build.
- [x] Add tests for successful offline preview scene build.
- [x] Add tests for asset build failure propagation.
- [x] Add tests for cache reuse.
- [x] Add tests for deterministic scene build output.
- [x] Add docs for scene build command.

## Phase 11 - Scene Assembly Runtime

Goal: assemble built objects into a spatial scene with transforms, hierarchy,
cameras, lights, and metadata.

- [x] Define scene assembly IR.
- [x] Add assembly IR docs.
- [x] Add transform math helpers.
- [x] Add unit conversion helpers.
- [x] Add object hierarchy generation.
- [x] Add material assignment mapping.
- [x] Add camera creation mapping.
- [x] Add light creation mapping.
- [x] Add region collection/group mapping.
- [x] Add scene metadata mapping.
- [x] Add object ID metadata mapping.
- [x] Add custom property mapping for Blender.
- [x] Add GLB extras mapping.
- [x] Add object index generation.
- [x] Define object selection payload contract using `object_id`, render ID map, and scene package path.
- [x] Add tests that selected render/object IDs resolve back to Scene Graph objects.
- [x] Add ID map material generation.
- [x] Add transform validation.
- [x] Add bounding-box estimation.
- [x] Add contact/resting-surface hints.
- [x] Add tests for object transforms.
- [x] Add tests for hierarchy output.
- [x] Add tests for object ID metadata preservation.
- [x] Add docs for assembly IR.

## Phase 12 - Blender Scene Assembly And Preview Rendering

Goal: create a concrete preview scene with canonical cameras and render passes.

- [x] Extend Blender bridge for scene assembly.
- [x] Add Blender collection naming convention.
- [x] Add Blender custom properties for `scene_id`.
- [x] Add Blender custom properties for `object_id`.
- [x] Add Blender custom properties for `region_id`.
- [x] Add Blender custom properties for provenance.
- [x] Add camera creation from Scene Graph cameras.
- [x] Add light creation from Scene Graph lights.
- [x] Add material assignment from Scene Graph materials.
- [x] Add fallback proxy mesh for missing object asset in preview mode.
- [x] Add deterministic proxy geometry mode for all scene objects when full asset generation is unavailable.
- [x] Add proxy material/style hints so preview renders still communicate scene intent.
- [x] Add scene bounds helper.
- [x] Add reveal camera auto-fit.
- [x] Add topdown/debug camera generation.
- [x] Add object contact sheet render.
- [x] Add beauty render pass.
- [x] Add depth render pass.
- [x] Add normal render pass.
- [x] Add object ID mask render pass.
- [x] Add material ID mask render pass.
- [x] Add wireframe/debug render pass.
- [x] Add `lathe scene render <scene> --camera <camera_id>`.
- [x] Add `lathe scene render <scene> --all-cameras`.
- [x] Add render timeout handling.
- [x] Add render artifact manifest.
- [x] Add tests with mocked Blender.
- [x] Add smoke test gated on Blender availability.
- [x] Add docs for scene rendering.

## Phase 13 - GLB, USD, And Blender Exports

Goal: produce product-grade scene exports with identity and metadata intact.

- [x] Add `lathe scene export <scene> --target glb`.
- [x] Add `lathe scene export <scene> --target blender`.
- [x] Add `lathe scene export <scene> --target usd`.
- [x] Add clean GLB node hierarchy.
- [x] Add GLB extras metadata for scene ID.
- [x] Add GLB extras metadata for object IDs.
- [x] Add GLB extras metadata for region IDs.
- [x] Add optional collision node export.
- [x] Add optional object index export.
- [x] Add optional ID mask export bundle.
- [x] Add Blender `.blend` export with named collections.
- [x] Add Blender cameras and lights preservation.
- [x] Add Blender material preservation.
- [x] Add Blender custom property preservation.
- [x] Add USD export layout convention.
- [x] Add export validation that GLB opens with `trimesh`.
- [x] Add export validation that Blender file can be probed when Blender exists.
- [x] Add export validation for clean names.
- [x] Add export validation for scale sanity.
- [x] Add export validation for missing materials.
- [x] Add tests for GLB metadata.
- [x] Add tests for export manifest schema.
- [x] Add docs for export targets.

## Phase 14 - Scene-Level Validators

Goal: make Lathe's validation moat operate at world/scene level.

- [x] Create `lathe/scene/validators/`.
- [x] Add validator composition for scene validators.
- [x] Add `spatial` validator.
- [x] Check objects are not floating unexpectedly.
- [x] Check objects do not intersect beyond tolerance.
- [x] Check props rest on intended surfaces.
- [x] Check paths are not blocked.
- [x] Check doors align with walls or thresholds.
- [x] Check scale consistency across object roles.
- [x] Add `semantic` validator.
- [x] Check required Dream Brief elements exist.
- [x] Check object roles match scene purpose.
- [x] Check avoided elements are absent.
- [x] Check affordances reference actual objects or hidden state.
- [x] Add `style` validator.
- [x] Check palette coherence.
- [x] Check material language consistency.
- [x] Check lighting style matches brief.
- [x] Check object families do not clash with style pack.
- [x] Add `composition` validator.
- [x] Check focal point exists.
- [x] Check reveal camera targets readable object.
- [x] Check scene is not empty.
- [x] Check object density matches brief.
- [x] Check silhouette variety.
- [x] Add `curiosity` validator.
- [x] Check at least two curiosity anchors for Wonder-ready scenes.
- [x] Check curiosity anchors attach to existing targets.
- [x] Check hidden facts do not contradict visible state.
- [x] Check expansion options have target scopes.
- [x] Add `continuity` validator.
- [x] Check preserved objects remain stable after patch.
- [x] Check preserved transforms remain stable within tolerance.
- [x] Check stable IDs are not regenerated.
- [x] Check prior memory facts are not contradicted.
- [x] Add `export` validator.
- [x] Check export artifacts exist.
- [x] Check formats match requested targets.
- [x] Check object IDs survive export metadata.
- [x] Add `platform` validator.
- [x] Check platform-specific triangle budgets.
- [x] Check platform-specific texture budgets.
- [x] Check platform-specific naming conventions.
- [x] Add scene quality score aggregation.
- [x] Add `lathe scene validate <scene_or_package>`.
- [x] Add machine-readable `scene_quality_report.json`.
- [x] Add human-readable scene quality summary.
- [x] Add tests for each validator.
- [x] Add docs for each validator and scoring policy.

## Phase 15 - Semantic Scene Patching

Goal: support stateful revision at asset, object, region, scene, and branch
levels.

- [x] Create `lathe/scene/patch.py`.
- [x] Add `lathe scene patch <scene> <patch.json>`.
- [x] Add patch scope `asset`.
- [x] Add patch scope `object`.
- [x] Add patch scope `region`.
- [x] Add patch scope `scene`.
- [x] Add patch scope `camera`.
- [x] Add patch scope `light`.
- [x] Add patch scope `curiosity_anchor`.
- [x] Add patch scope `hidden_state`.
- [x] Add continuity-preserving patch mode.
- [x] Add patch preview mode.
- [x] Add patch rollback mode.
- [x] Add JSON Patch operation support where explicit operations exist.
- [x] Add semantic instruction preservation in patch history.
- [x] Add allowed-change enforcement.
- [x] Add preserve-list enforcement.
- [x] Add patch conflict detection.
- [x] Add patch diagnostics for missing target IDs.
- [x] Add patch diagnostics for forbidden transforms.
- [x] Add patch diagnostics for invalid operations.
- [x] Add memory event recording for patch application.
- [x] Add tests for object patch.
- [x] Add tests for region patch.
- [x] Add tests for scene patch preserving layout.
- [x] Add tests for forbidden change rejection.
- [x] Add tests for rollback.
- [x] Add docs for scene patching.

## Phase 16 - Branching, Versioning, Diff, And Merge

Goal: let Wonder explore alternate versions without losing continuity.

- [x] Define scene version graph schema.
- [x] Add branch metadata to scene packages.
- [x] Add `lathe scene branch <scene> --name <branch>`.
- [x] Add `lathe scene diff <left> <right>`.
- [x] Add `lathe scene merge <source> --into <target>`.
- [x] Add `lathe scene rollback <scene> --to <version>`.
- [x] Track parent version IDs.
- [x] Track branch names.
- [x] Track patch IDs per branch.
- [x] Track render history per branch.
- [x] Track validation history per branch.
- [x] Preserve object IDs across branch creation.
- [x] Add diff output for object additions.
- [x] Add diff output for object removals.
- [x] Add diff output for transform changes.
- [x] Add diff output for material changes.
- [x] Add diff output for state changes.
- [x] Add diff output for hidden-state changes.
- [x] Add diff output for curiosity changes.
- [x] Add merge conflict detection.
- [x] Add merge strategy for non-overlapping object changes.
- [x] Add merge strategy for material-only changes.
- [x] Add tests for branch creation.
- [x] Add tests for diff output.
- [x] Add tests for merge conflict.
- [x] Add docs for branch/version model.

## Phase 17 - Render Inspection And Repair Loop

Goal: make the build-render-inspect-patch-rebuild loop first-class.

- [x] Add `lathe scene inspect-render <scene> <render_inspection.json>`.
- [x] Validate render inspection against scene graph.
- [x] Validate render inspection target IDs exist.
- [x] Convert recommended patches into scene patch proposals.
- [x] Add `lathe scene propose-repairs <scene> <inspection.json>`.
- [x] Add `lathe scene repair <scene> --goal wonder_preview --max-rounds 3`.
- [x] Define repair goals: `wonder_preview`, `export_ready`, `roblox_ready`.
- [x] Add bounded repair loop state machine.
- [x] Add repair round report.
- [x] Add repair acceptance criteria.
- [x] Add repair rejection criteria.
- [x] Add repair loop timeout.
- [x] Add repair loop deterministic offline mode.
- [x] Add repair memory events.
- [x] Add before/after render comparison hooks.
- [x] Add camera lock for before/after comparison.
- [x] Add tests for repair from style warning to patch.
- [x] Add tests for repair loop max rounds.
- [x] Add tests for failed repair reporting.
- [x] Add docs for agentic repair loop.

## Phase 18 - Style Packs And Style Coherence

Goal: keep multi-object scenes visually coherent.

- [x] Define `style_pack` schema.
- [x] Add style pack declarations in `.lth`.
- [x] Add style pack references in Dream Brief.
- [x] Add style pack references in Scene Graph.
- [x] Add palette roles: primary, secondary, accent, emissive.
- [x] Add form-language roles.
- [x] Add material-language roles.
- [x] Add lighting-language roles.
- [x] Add style inheritance for regions.
- [x] Add style inheritance for objects.
- [x] Add per-object style overrides.
- [x] Add style validation for palette drift.
- [x] Add style validation for material mismatch.
- [x] Add style validation for form-language mismatch.
- [x] Add built-in `dead_god_observatory` style pack.
- [x] Add built-in `dark_fantasy_ruin` style pack.
- [x] Add built-in `cozy_fantasy_workshop` style pack.
- [x] Add built-in `sci_fi_industrial` style pack.
- [x] Add built-in `roblox_lowpoly_cute` style pack.
- [x] Add built-in `roblox_horror_lowpoly` style pack.
- [x] Add tests for style inheritance.
- [x] Add docs for style packs.

## Phase 19 - Instance Overrides And Reuse

Goal: support many scene objects from a shared family without generating every
instance as a full unique asset.

- [x] Define object instance override schema.
- [x] Add transform overrides.
- [x] Add material overrides.
- [x] Add surface overrides.
- [x] Add variant overrides.
- [x] Add state overrides.
- [x] Add affordance overrides.
- [x] Add scale overrides.
- [x] Add generated variation seed.
- [x] Add instance reuse planner.
- [x] Add instancing metadata to scene assembly.
- [x] Add instancing metadata to GLB extras.
- [x] Add instancing metadata to Blender custom properties.
- [x] Add tests for 12 candles sharing one asset.
- [x] Add tests for four damaged doors sharing one family.
- [x] Add tests for per-instance material override.
- [x] Add tests for cache reuse with overrides.
- [x] Add docs for family to scene instance flow.

## Phase 20 - Layout Solver And Spatial Intelligence

Goal: prevent scenes from becoming random object dumps.

- [x] Define layout constraints model.
- [x] Add room bounds constraints.
- [x] Add object bounding box constraints.
- [x] Add main path constraints.
- [x] Add focal point constraints.
- [x] Add snap grid constraints.
- [x] Add modular wall placement constraints.
- [x] Add collision avoidance constraints.
- [x] Add radial layout constraints.
- [x] Add clustered prop placement constraints.
- [x] Add symmetry constraints.
- [x] Add density constraints.
- [x] Add path width validation.
- [x] Add simple deterministic layout solver.
- [x] Add layout solver seed control.
- [x] Add layout solver diagnostics.
- [x] Add tests for room layout.
- [x] Add tests for avoiding focal object intersections.
- [x] Add tests for blocked path detection.
- [x] Add tests for stable layout under unrelated style patch.
- [x] Add docs for layout constraints.

## Phase 21 - Lighting And Camera Systems

Goal: make every scene preview readable and product-grade.

- [x] Define lighting plan source syntax and IR.
- [x] Add key light model.
- [x] Add fill light model.
- [x] Add practical light model.
- [x] Add atmosphere/fog metadata.
- [x] Add exposure hints.
- [x] Add lighting validation for focal visibility.
- [x] Add lighting validation for overexposure.
- [x] Add lighting validation for underexposure.
- [x] Add camera intent source syntax and IR.
- [x] Add reveal camera.
- [x] Add inspection camera.
- [x] Add topdown/debug camera.
- [x] Add contact sheet camera.
- [x] Add before/after locked camera.
- [x] Add camera auto-fit.
- [x] Add camera target validation.
- [x] Add camera composition scoring.
- [x] Add tests for camera generation.
- [x] Add tests for camera lock through patch.
- [x] Add docs for camera and lighting authoring.

## Phase 22 - Curiosity Anchors And Hidden State

Goal: give Project Wonder structured expansion hooks.

- [x] Finalize curiosity anchor schema.
- [x] Finalize hidden state schema.
- [x] Add source syntax for curiosity anchors.
- [x] Add source syntax for hidden state.
- [x] Add expansion option model.
- [x] Add required generated assets list.
- [x] Add continuity constraints list.
- [x] Add suggested user action list.
- [x] Add visible clue field.
- [x] Add hidden fact field.
- [x] Add curiosity card summary output.
- [x] Add curiosity anchor validator.
- [x] Add hidden-state contradiction validator.
- [x] Add `lathe scene curiosity <scene>`.
- [x] Add `lathe scene expand-anchor <scene> <anchor_id> --option <id>`.
- [x] Add tests for curiosity anchor preservation.
- [x] Add tests for hidden state reveal conditions.
- [x] Add tests for expansion graph generation.
- [x] Add docs for curiosity anchors.

## Phase 23 - Game-Readiness Metadata

Goal: make scene exports useful to game engines, not just visual tools.

- [x] Add gameplay metadata syntax.
- [x] Add object static/dynamic metadata.
- [x] Add interactable metadata.
- [x] Add collision type metadata.
- [x] Add walkable/not-walkable metadata.
- [x] Add snap point metadata.
- [x] Add socket metadata.
- [x] Add pivot metadata.
- [x] Add LOD policy metadata.
- [x] Add physics profile metadata.
- [x] Add occlusion hint metadata.
- [x] Add mobile performance profile metadata.
- [x] Add gameplay tags.
- [x] Add validator for missing required collision on game targets.
- [x] Add validator for missing pivots on interactables.
- [x] Add validator for invalid snap-point names.
- [x] Add tests for sealed archive door gameplay metadata.
- [x] Add docs for game-readiness fields.

## Phase 24 - Roblox Profile And Export Lane

Goal: make Roblox a first-class vertical lane for Wonder.

- [x] Define `profile roblox_lowpoly` in stdlib or example.
- [x] Define `lathe.stack.roblox_asset_kit_v1`.
- [x] Add Roblox target metadata.
- [x] Add units `studs` handling.
- [x] Add Roblox-safe naming rules.
- [x] Add Roblox triangle budget validator.
- [x] Add Roblox texture resolution validator.
- [x] Add Roblox mesh count validator.
- [x] Add Roblox collision simplicity validator.
- [x] Add Roblox material compatibility validator.
- [x] Add Roblox pivot placement validator.
- [x] Add Roblox snap-grid alignment validator.
- [x] Add Roblox mobile performance score.
- [x] Add `roblox_manifest.json` schema.
- [x] Add GLB/FBX folder export with Roblox manifest.
- [x] Add Roblox thumbnail generation.
- [x] Add Roblox import instructions artifact.
- [x] Add initial Roblox style packs.
- [x] Add Roblox low-poly shop interior Wonder example.
- [x] Add Roblox asset kit example.
- [x] Add tests for Roblox profile validation.
- [x] Add tests for Roblox manifest generation.
- [x] Add docs for Roblox export workflow.
- [x] Decide whether `.rbxmx` export is in v0.3 or deferred.
- [x] Because `.rbxmx` is deferred, keep a minimal `.rbxmx` writer or plugin handoff out of v0.3 scope.
- [x] If Roblox Studio plugin is deferred, write explicit ADR.

## Phase 25 - Standard Library Expansion

Goal: give Wonder enough reusable content vocabulary to avoid samey scenes.

- [x] Inventory current stdlib assets, families, kits, materials, spaces, and patterns.
- [x] Add architecture kit: walls.
- [x] Add architecture kit: floors.
- [x] Add architecture kit: ceilings.
- [x] Add architecture kit: arches.
- [x] Add architecture kit: columns.
- [x] Add architecture kit: stairs.
- [x] Add architecture kit: doors.
- [x] Add architecture kit: windows.
- [x] Add architecture kit: bridges.
- [x] Add architecture kit: railings.
- [x] Add architecture kit: platforms.
- [x] Add architecture kit: tunnels.
- [x] Add modular room shell kit.
- [x] Add environmental dressing: crates.
- [x] Add environmental dressing: barrels.
- [x] Add environmental dressing: books.
- [x] Add environmental dressing: candles.
- [x] Add environmental dressing: chains.
- [x] Add environmental dressing: pipes.
- [x] Add environmental dressing: vents.
- [x] Add environmental dressing: panels.
- [x] Add environmental dressing: debris.
- [x] Add environmental dressing: rugs.
- [x] Add environmental dressing: banners.
- [x] Add environmental dressing: signs.
- [x] Add controlled natural forms: rocks.
- [x] Add controlled natural forms: roots.
- [x] Add controlled natural forms: vines.
- [x] Add controlled natural forms: crystals.
- [x] Add controlled natural forms: mushrooms.
- [x] Add controlled natural forms: dead trees.
- [x] Add controlled natural forms: bones.
- [x] Add controlled natural forms: coral-like forms.
- [x] Add controlled terrain chunks.
- [x] Add hero prop: altar.
- [x] Add hero prop: machine.
- [x] Add hero prop: console.
- [x] Add hero prop: relic.
- [x] Add hero prop: portal.
- [x] Add hero prop: vehicle.
- [x] Add hero prop: weapon.
- [x] Add hero prop: tool.
- [x] Add hero prop: furniture.
- [x] Add lighting fixture: torch.
- [x] Add lighting fixture: lamp.
- [x] Add lighting fixture: neon tube.
- [x] Add lighting fixture: moon window.
- [x] Add lighting fixture: glowing crystal.
- [x] Add lighting fixture: hologram.
- [x] Add docs cataloging stdlib Wonder components.
- [x] Add tests that stdlib entries parse and check.
- [x] Add scene examples that use stdlib kits.

## Phase 26 - Environment Modules And Terrain Chunks

Goal: make Wonder scenes feel like places, not prop collections.

- [x] Strengthen `env_module` support for room shells.
- [x] Add modular floor tile examples.
- [x] Add modular wall segment examples.
- [x] Add modular ceiling segment examples.
- [x] Add modular arch examples.
- [x] Add modular platform examples.
- [x] Add modular stair examples.
- [x] Add background silhouette examples.
- [x] Add scene boundary shell examples.
- [x] Add terrain chunk examples.
- [x] Add snap points for modular modules.
- [x] Add validator for module snap alignment.
- [x] Add validator for missing scene boundary.
- [x] Add tests for environment module scene assembly.
- [x] Add docs for environment modules in scenes.

## Phase 27 - LLM Authoring APIs And Diagnostics

Goal: make frontier models good at writing and repairing Lathe-adjacent JSON and
source.

- [x] Add `lathe wonder generate-scene-plan` contract or command.
- [x] Add `lathe wonder diagnose-for-llm <report>`.
- [x] Add `lathe wonder apply-semantic-patch`.
- [x] Add compact diagnostic summaries.
- [x] Add repair option payloads.
- [x] Add source spans in parse diagnostics where available.
- [x] Add schema pointers in JSON diagnostics.
- [x] Add "next action" hints for scene graph failures.
- [x] Add constrained output examples for Dream Brief.
- [x] Add constrained output examples for Scene Graph.
- [x] Add constrained output examples for Scene Patch.
- [x] Add constrained output examples for Render Inspection.
- [x] Add examples of bad model outputs and repair instructions.
- [x] Add diagnostics for invented unsupported declarations.
- [x] Add diagnostics for unstable or missing IDs.
- [x] Add diagnostics for missing preservation constraints.
- [x] Add tests for LLM-facing diagnosis output.
- [x] Add docs under `docs/llm/`.
- [x] Add `docs/llm/lathe_authoring_rules.md`.
- [x] Add `docs/llm/dream_brief_schema.json` or links to canonical schema.
- [x] Add `docs/llm/scene_graph_schema.json` or links to canonical schema.
- [x] Add `docs/llm/patch_schema.json` or links to canonical schema.
- [x] Add `docs/llm/repair_playbook.md`.

## Phase 28 - Security, Safety, And Provenance

Goal: keep public generation, provider use, and exports auditable.

- [x] Add scene asset provenance model.
- [x] Track deterministic Lathe-generated assets.
- [x] Track provider-generated assets.
- [x] Track user-supplied inputs.
- [x] Track licensed references.
- [x] Track commercial-use flag when known.
- [x] Track export permission status.
- [x] Add provenance into Scene Graph objects.
- [x] Add provenance into scene package manifest.
- [x] Add provenance into export manifests.
- [x] Add content safety metadata hooks.
- [x] Add brand/IP policy metadata hooks.
- [x] Add user-upload reference safety metadata.
- [x] Add validator for missing provenance on provider-generated content.
- [x] Add validator for unsafe external paths.
- [x] Add validator for forbidden secret-bearing metadata.
- [x] Add trust-boundary annotations for all new untrusted JSON inputs.
- [x] Update JSON ingress audit for all new JSON readers.
- [x] Add tests for secret redaction in Wonder reports.
- [x] Add docs for content safety boundary.
- [x] Add docs for provenance and rights.

## Phase 29 - Service API Contract Boundary

Goal: prepare for Project Wonder as a product without putting SaaS concerns into
Lathe core.

- [x] Define service contract docs without building full SaaS.
- [x] Define `POST /dream-brief/check` request/response schema.
- [x] Define `POST /scene-graph/check` request/response schema.
- [x] Define `POST /scene/build` request/response schema.
- [x] Define `POST /scene/render` request/response schema.
- [x] Define `POST /scene/patch` request/response schema.
- [x] Define `GET /scene/{id}/artifacts` response schema.
- [x] Define `GET /scene/{id}/status` response schema.
- [x] Ensure CLI outputs can be wrapped by service responses.
- [x] Add correlation ID field to scene build reports.
- [x] Add job status model.
- [x] Add cancellation model.
- [x] Add artifact listing model.
- [x] Add docs for Project Wonder orchestration boundary.
- [x] Add ADR forbidding accounts, payments, galleries, and chat UX in Lathe core.

## Phase 30 - Performance And Cost Budgets

Goal: keep the Wonder loop fast enough for product use.

- [x] Define preview mode budgets.
- [x] Define final mode budgets.
- [x] Add Dream Brief budget target under 10 seconds.
- [x] Add Scene Graph budget target under 20 seconds.
- [x] Add scene source generation budget target under 10 seconds.
- [x] Add check/plan budget target under 5 seconds.
- [x] Add preview build budget target under 60 seconds for benchmark scenes.
- [x] Add preview render budget target under 30 seconds.
- [x] Add patch preview budget target under 45 seconds.
- [x] Add final export budget target and allowed exceptions.
- [x] Add benchmark timing harness.
- [x] Add cache reuse metric.
- [x] Add cost estimate fields for provider-backed paths.
- [x] Add `lathe scene bench`.
- [x] Add performance report output.
- [x] Add CI or nightly benchmark job.
- [x] Add docs for preview/final mode tradeoffs.

## Phase 31 - Wonder Benchmark Suite

Goal: create the truth machine for Wonder readiness.

- [x] Create `benchmarks/wonder/`.
- [x] Add benchmark prompt: alchemist observatory.
- [x] Add benchmark prompt: mountain lightning city.
- [x] Add benchmark prompt: abandoned Roblox mall.
- [x] Add benchmark prompt: underwater train station.
- [x] Add benchmark prompt: desert oracle shrine.
- [x] Add benchmark prompt: cozy witch greenhouse.
- [x] Add benchmark prompt: cyberpunk noodle alley.
- [x] Add benchmark prompt: ancient moon elevator.
- [x] Add benchmark prompt: horror obby lobby.
- [x] Add benchmark prompt: luxury tycoon showroom.
- [x] Add three style variations for each prompt.
- [x] Add three patch operations for each prompt.
- [x] Score prompt-to-brief success.
- [x] Score brief-to-scene success.
- [x] Score parse/check success.
- [x] Score build success.
- [x] Score scene validation.
- [x] Score style consistency.
- [x] Score object count accuracy.
- [x] Score render quality.
- [x] Score patch success.
- [x] Score continuity preservation.
- [x] Score export validity.
- [x] Score time to first render.
- [x] Score cache reuse.
- [x] Add benchmark report docs.
- [x] Add minimum readiness thresholds.

## Phase 32 - Golden Wonder Examples

Goal: prove Wonder readiness through representative scenes.

- [x] Complete `examples/wonder/alchemist_observatory/` through actual scene build.
- [x] Add `examples/wonder/mountain_lightning_city/`.
- [x] Add `examples/wonder/abandoned_roblox_mall/`.
- [x] Add `examples/wonder/underwater_train_station/`.
- [x] Add `examples/wonder/desert_oracle_shrine/`.
- [x] Each example includes `prompt.txt`.
- [x] Each example includes `dream_brief.json`.
- [x] Each example includes `scene_graph.json`.
- [x] Each example includes `.lth` scene source after scene syntax exists.
- [x] Each example includes scene patch JSON.
- [x] Each example includes expected scene manifest.
- [x] Each example includes expected Wonder report.
- [x] Each example includes render inspection example.
- [x] Each example builds in preview mode.
- [x] Each example renders reveal and topdown cameras.
- [x] Each example exports at least GLB or package target.
- [x] Each example records validation evidence.
- [x] Add examples catalog entries.
- [x] Add tests that every Wonder example validates.
- [x] Add tests that every Wonder example builds or is clearly marked expected-only until its phase.

## Phase 33 - Demo Script And One-Command Golden Path

Goal: make the Wonder path visible and repeatable.

- [x] Add `scripts/demo_wonder_seed_scene.sh`.
- [x] Add `scripts/demo_wonder_seed_scene.ps1`.
- [x] The script validates Dream Brief.
- [x] The script validates Scene Graph.
- [x] The script lowers Scene Graph to source.
- [x] The script checks scene source.
- [x] The script plans scene build.
- [x] The script builds preview scene.
- [x] The script renders reveal camera.
- [x] The script validates render inspection.
- [x] The script applies `more_sacred` patch.
- [x] The script rebuilds preview.
- [x] The script renders before/after comparison.
- [x] The script expands one curiosity anchor.
- [x] The script exports GLB.
- [x] The script validates final scene package.
- [x] Add deterministic mode for demo.
- [x] Add CI smoke for demo where heavy tools are mocked.
- [x] Add docs explaining every output folder.
- [x] Add a short demo transcript.

## Phase 34 - Documentation Set

Goal: document the transition from Lathe asset compiler to Wonder scene
runtime.

- [x] Expand `docs/wonder-readiness/00_overview.md`.
- [x] Expand `docs/wonder-readiness/01_dream_brief.md`.
- [x] Expand `docs/wonder-readiness/02_scene_graph.md`.
- [x] Expand `docs/wonder-readiness/03_scene_patch.md`.
- [x] Expand `docs/wonder-readiness/04_render_inspection.md`.
- [x] Add `docs/wonder-readiness/06_scene_language.md`.
- [x] Add `docs/wonder-readiness/07_scene_build_pipeline.md`.
- [x] Add `docs/wonder-readiness/08_scene_package.md`.
- [x] Add `docs/wonder-readiness/09_scene_validation.md`.
- [x] Add `docs/wonder-readiness/10_render_repair_loop.md`.
- [x] Add `docs/wonder-readiness/11_curiosity_anchors.md`.
- [x] Add `docs/wonder-readiness/12_world_memory.md`.
- [x] Add `docs/wonder-readiness/13_branching.md`.
- [x] Add `docs/wonder-readiness/14_roblox_profile.md`.
- [x] Add `docs/wonder-readiness/15_mvp_demo.md`.
- [x] Add `docs/wonder-readiness/16_limitations.md`.
- [x] Add API docs for `lathe.scene`.
- [x] Add API docs for `lathe.wonder`.
- [x] Add CLI reference entries for all `lathe scene` commands.
- [x] Add architecture diagram for Wonder Layer.
- [x] Add docs warning that Lathe is not a product chat app.
- [x] Add docs warning that open-world generation is out of first readiness scope.

## Phase 35 - Test And CI Matrix

Goal: keep the whole Wonder layer from regressing.

- [x] Add unit tests for all scene modules.
- [x] Add contract tests for all schemas.
- [x] Add CLI tests for all `wonder` commands.
- [x] Add CLI tests for all `scene` commands.
- [x] Add parser/normalizer/resolver/checker tests for scene syntax.
- [x] Add planner tests for scene plans.
- [x] Add executor tests with mocked asset builds.
- [x] Add Blender bridge tests with mocked Blender.
- [x] Add export tests with lightweight artifacts.
- [x] Add validator tests for every scene validator.
- [x] Add patch tests for every patch scope.
- [x] Add branch/diff/merge tests.
- [x] Add world memory tests.
- [x] Add repair loop tests.
- [x] Add Roblox profile tests.
- [x] Add docs static audit coverage for Wonder docs.
- [x] Add example-corpus tests for `examples/wonder`.
- [x] Add golden snapshot tests for scene manifests.
- [x] Add golden snapshot tests for scene build reports.
- [x] Add property tests for ID stability.
- [x] Add fuzz tests for Dream Brief and Scene Graph JSON ingress.
- [x] Add CI job for Wonder fast tests.
- [x] Add CI job for Wonder examples.
- [x] Add optional CI job for Blender bridge/export smoke, with Blender scene
  render smoke explicitly reported unavailable until the render pipeline exists.
- [x] Add optional CI job for Roblox profile validation.
- [x] Update coverage gates if new packages need package-level thresholds.

## Phase 36 - Project Wonder Handoff Readiness

Goal: prove Lathe can be trusted by the Project Wonder app/runtime.

Phase 36 local handoff note, 2026-04-29: deterministic core/proxy handoff
evidence is recorded locally. Clean-checkout, hosted CI, POSIX, final
renderer/export, Roblox Studio, external viewer, Project Wonder app-layer, and
human approval gates remain unchecked below.

- [x] Produce final Wonder readiness report.
- [x] Produce final architecture boundary ADR.
- [x] Produce final contract reference docs.
- [x] Produce final CLI reference docs.
- [x] Produce final example catalog.
- [x] Produce final benchmark report.
- [x] Produce final security/provenance report.
- [x] Produce final performance report.
- [x] Produce final known limitations doc.
- [ ] Confirm golden demo runs from a clean checkout.
- [ ] Confirm full `python -m pytest -q` passes on supported Python versions.
- [ ] Confirm hosted Wonder fast CI passes.
- [ ] Confirm hosted Wonder example CI passes.
- [x] Confirm Blender optional smoke either passes or is clearly marked unavailable.
- [x] Confirm all Wonder schemas are stable for `v1`.
- [x] Confirm all object IDs survive deterministic proxy build, render, package, and export.
- [x] Confirm at least one scene supports patch and continuity-preserving rebuild.
- [x] Confirm at least one scene supports curiosity expansion.
- [x] Confirm at least one scene exports proxy GLB with object metadata.
- [x] Confirm at least one scene exports Blender package with custom properties.
- [x] Confirm at least one Roblox-compatible kit passes Roblox validators.
- [x] Confirm docs accurately state what is implemented and what is deferred.
- [x] Confirm Project Wonder can call Lathe through JSON contracts and CLI outputs.
- [ ] Record final readiness decision: `Lathe is ready for Project Wonder alpha`.

## Final Task - Wonder Alpha Gate

- [ ] From a clean checkout, run the Wonder golden path end to end:
  `scripts/demo_wonder_seed_scene.sh examples/wonder/alchemist_observatory`.
- [ ] Verify the output package contains:
  `scene_manifest.json`, `scene_graph.json`, `world_memory.json`, scene source,
  asset builds, reveal render, topdown render, object ID map, validation report,
  Wonder report, GLB export, and provenance report.
- [ ] Apply the `more sacred` scene patch and confirm preserved object IDs,
  preserved layout, updated style/materials, and successful rebuild.
- [ ] Expand one curiosity anchor and confirm the branch records hidden state,
  memory events, new assets, new render, and continuity report.
- [ ] Export a final scene package and open the GLB or Blender artifact in an
  external viewer.
- [ ] Hand the package plus contracts to the Project Wonder app layer and confirm
  the app can inspect, select, patch, render, and export the scene without
  bypassing Lathe contracts.
- [ ] Mark Lathe as Project Wonder alpha-ready only after every item above is
  complete with evidence.
