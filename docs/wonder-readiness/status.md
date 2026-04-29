# Wonder Readiness Status

Last updated: 2026-04-29

Wonder readiness score: **4/10 for full Wonder runtime readiness**.

Current milestone: **the deterministic Project Wonder core/proxy alpha gate is
decision-ready locally; full Wonder runtime/export readiness remains blocked by
external evidence and optional runtime lanes**.

Lathe is still primarily an asset compiler. The Wonder layer is being added as a
schema-first contract boundary so Project Wonder can describe scenes through
durable JSON contracts, with minimal experimental `.lth` scene syntax now
available as an additive authoring surface rather than the runtime source of
truth.

## What Exists Locally

- Wonder schemas for Dream Brief, Scene Graph, Scene Patch, Render Inspection,
  World Memory, Scene Package Manifest, and Scene Plan.
- Local Wonder contract loading and validation helpers under `lathe/wonder/`.
- Local `lathe wonder` commands for schema listing, schema emission, and JSON
  validation.
- Local `lathe wonder check-scene-graph` command for first-pass Scene Graph
  semantic checks.
- Local `lathe wonder decompose-brief`, `brief-to-scene`, and
  `check-brief-scene` commands for deterministic Dream Brief decomposition,
  lowering, and brief/scene consistency checks.
- Local `lathe wonder capabilities` and `lathe wonder status` commands with
  machine-readable capability flags, explicit future-phase false values,
  readiness blockers, and evidence pointers.
- Local Scene Graph semantic diagnostics for duplicate object IDs, missing object
  regions, invalid relationship endpoints, unsafe artifact/export paths, ID
  duplicates across core scene entities, material bindings, camera/light targets,
  curiosity/hidden attachments, affordance reveal targets, layout references,
  curiosity expansion targets, and memory event affected IDs.
- Local `lathe scene` commands for scene checking, planning, quality validation,
  patch application, source bridge conversion, preview package build, package
  init/inspect/validate, and World Memory inspect/append.
- Deterministic Scene Plan generation for existing Scene Graph JSON, including
  asset tasks, assembly tasks, render tasks, export tasks, warnings, diagnostics,
  and cache keys.
- Local scene quality validators for spatial, semantic, style, composition,
  curiosity, continuity, export, and platform checks.
- Local World Memory validation with branch continuity checks.
- Folder-based Scene Package Manifest helpers and CLI surface.
- Generated Wonder schema reference docs.
- PowerShell and Bash local Wonder validation helper scripts. The PowerShell
  helper is validated locally and in the review snapshot and currently reports
  261 focused tests passing; the Bash helper still needs a POSIX-capable runtime
  check.
- Alchemist Observatory contract examples under
  `examples/wonder/alchemist_observatory/`.
- Local Wonder fast and examples CI scripts now exist under `scripts/`, passed
  locally, and write machine-readable reports under `.tmp_tests/`.
- All seven Wonder examples now include generated `scene_source.lth` files.
  Example validation treats those files as required fixtures and verifies they
  roundtrip back to the committed Scene Graph JSON through
  `lathe scene source-to-scene-graph`.
- Optional Blender and Roblox local lanes now report pass/skip status without
  blocking the deterministic core gate. Local Blender probing passed in this
  environment; Roblox tooling was unavailable and skipped nonblocking.
- `lathe wonder alpha-gate` now writes the deterministic core/proxy alpha-gate
  report bundle under
  `.tmp_tests/wonder_alpha_gate/reports/`, including final readiness,
  evidence-traceability, benchmark, security, performance, contract catalog,
  CLI catalog, example catalog, and environment probe reports.
- `lathe wonder readiness-report --out docs/wonder-readiness/final_readiness_report.md`
  writes the public Markdown/JSON readiness handoff from the alpha-gate bundle.
- Phase 36 local handoff artifacts are refreshed: final readiness report,
  architecture boundary ADR, schema reference, CLI reference, example catalog,
  benchmark report, security/provenance report, performance report, and known
  limitations doc. This is local deterministic core/proxy evidence, not a full
  runtime approval.
- Initial readiness docs under `docs/wonder-readiness/`.
- Phase 6A local documentation for experimental v0.3 scene source syntax in
  `docs/wonder-readiness/06_scene_language_design.md`, with ADR 0010 recording
  the compatibility boundary. This is design evidence only and does not change
  parser, grammar, normalizer, resolver, checker, formatter, CLI, or runtime
  behavior.
- Phase 6B minimal experimental `.lth` scene syntax now exists locally for
  top-level `scene` declarations and scene-local style, region, object,
  relationship, camera, light, and export blocks. The implementation updates
  grammar, parser fast path, transformer, normalizer, normalized AST schema,
  resolver indexing, checker diagnostics, planner compatibility tests, and
  formatter snapshots while keeping asset planning unchanged.
- Phase 7 JSON-first scene source bridge exists locally. It emits
  `.lth`-flavored review text with an embedded Scene Graph JSON payload as the
  durable truth, and it roundtrips back to Scene Graph JSON.
- Phase 10 preview package build exists locally. It writes checked Scene Graph,
  World Memory, Scene Plan, Scene Assembly IR, Scene Quality Report, Wonder
  Report, Scene Manifest, Scene Package Manifest, deterministic proxy PNG
  renders, a deterministic proxy GLB export, and planned asset proxy records.
  The opt-in `lathe scene build --build-assets` lane also materializes
  generated Scene Plan asset sources inside the package and invokes the existing
  Lathe asset build pipeline before final packaging. Generated asset build
  failures currently stop the scene build with `SB1014` and preserve the
  materialization manifest for repair rather than being treated as proxy
  success.
- Phase 18 built-in curated Style Packs now exist locally for
  `dead_god_observatory`, `dark_fantasy_ruin`, `cozy_fantasy_workshop`,
  `sci_fi_industrial`, `roblox_lowpoly_cute`, and
  `roblox_horror_lowpoly`, with CLI emission through
  `lathe scene style-pack --builtin`. The experimental `.lth` language surface
  also accepts top-level `style_pack` declarations and validates scene-local
  `style_pack = <id>` references against in-file packs or curated built-ins.
- Phase 19 instance override support now treats Scene Graph object
  `surface_overrides` and `affordances` as per-instance metadata, keeps shared
  family assets reusable across damaged variants, records instancing metadata in
  Scene Assembly IR, writes the same metadata to proxy GLB object extras and
  object indices, and passes reuse-group custom properties into Blender export
  metadata.
- Phase 20 modular wall placement constraints now accept
  `layout.modular_walls` in Scene Graph JSON, validate referenced wall regions,
  emit deterministic Layout Plan `wall_segments` on region perimeter center
  lines, and warn when generated segments are not snap-grid aligned.
- Phase 21 camera and lighting source aliases now accept `camera_intent` and
  `lighting_plan` in experimental `.lth` scene source, lower them into the
  existing `scene_camera` and `scene_light` IR, keep `camera` and `light` as
  compatibility aliases, and prove camera locks survive non-camera semantic
  patches.
- Phase 22 curiosity source syntax now accepts `curiosity_anchor` and
  `hidden_state` blocks in experimental `.lth` scene source, normalizes them as
  `scene_curiosity_anchor` and `scene_hidden_state` children, validates ID
  prefixes and `attached_to` references, and shows the same blocks in generated
  JSON-first scene source previews.
- Phase 23 gameplay metadata syntax now accepts object-local `gameplay { ... }`
  blocks in experimental `.lth` scene source, lowers them into normalized
  scene-object `values.gameplay`, and shows Scene Graph affordances through
  `gameplay.affordances.<id>.*` lines in generated JSON-first source previews.
- Phase 24 Roblox asset-kit export now defines
  `lathe.stack.roblox_asset_kit_v1` and writes a local GLB bundle with
  `roblox_manifest.json`, thumbnail PNGs, import instructions, and an explicit
  FBX handoff artifact through `lathe scene roblox-export`.
- Phase 15 semantic Scene Patch application exists locally for asset, object,
  region, scene, camera, light, curiosity anchor, and hidden-state scopes.
- Phase 33 local Wonder seed demo scripts now exist under `scripts/`. The
  PowerShell script passed locally and exercises the current deterministic
  path: contracts, brief lowering, source bridge roundtrip, scene plan, scene
  assembly, preview package build, render-inspection contract repair, semantic
  patch, curiosity expansion, package validation, and proxy PNG/GLB artifact
  evidence.
- Phase 34/36 docs now include an explicit limitations page and alpha-gate
  decision page for the current proxy artifact evidence path.

The recommended-next-PR scope, Phase 0 baseline, and later deterministic
core/proxy lanes have local or review-snapshot evidence in
`docs/wonder-readiness/evidence.md`. This does not equal full final Wonder
runtime readiness.

## Current Deferred Or Optional Lanes

- Advanced `.lth` scene grammar remains deferred for scene variants,
  branch/merge source syntax, provenance metadata, standalone game-readiness
  payload syntax, sockets/snap points beyond object gameplay metadata, and
  deterministic layout constraints. The current minimal source layer is
  additive and experimental.
- POSIX helper execution remains optional for the local core/proxy gate from
  this Windows environment. It still blocks full readiness if POSIX proof is
  required by the release scope.
- Blender is optional for the local core/proxy gate. Local probing and
  sandboxed scene export passed, but no Blender-backed scene render evidence is
  claimed by the core alpha gate.
- Roblox Studio import/upload execution is optional for the local core/proxy
  gate. Local tooling was not available and the lane was skipped nonblocking;
  Roblox profile, manifest, and local asset-kit bundle contracts remain covered
  by deterministic validators and proxy artifacts.
- External viewer execution remains optional for the local core/proxy gate and
  still blocks full readiness if external-viewer proof is required by scope.
- The core/proxy alpha human decision remains pending:
  **Approve Project Wonder core/proxy alpha gate.**

## Current Milestone A Exit Gap

Milestone A Phase 0 and the recommended-next-PR contract slice are evidenced.
The remaining Milestone A work is to continue checking task boxes only as their
detailed schema, CLI, and semantic-validation evidence is recorded.

Core/proxy alpha decision now requires:

- Human approval of the alpha gate.
- Hosted CI confirmation of the newly added Wonder workflows when those
  workflows run remotely.
- Optional Blender/Roblox/external-viewer execution evidence only if the alpha
  decision scope explicitly requires those lanes.

Full Wonder runtime readiness still requires clean checkout or hosted CI,
POSIX proof if in scope, Blender-backed scene render evidence, Roblox export
execution if in scope, and external-viewer validation if in scope. Sandboxed
Blender scene export is locally proven for the alchemist observatory fixture.

## Recommended Next Scope

1. Review `.tmp_tests/wonder_alpha_gate/reports/final_readiness_report.json`
   and `docs/wonder-readiness/final_readiness_report.md`.
2. Make the remaining human decision: approve or hold the Project Wonder
   core/proxy alpha gate.
3. Let the new Wonder GitHub workflows run remotely and record their results.
4. Run optional Blender/Roblox/external-viewer lanes only when the alpha scope
   requires runtime-backed evidence beyond the deterministic proxy gate.

## Still Deferred Or Incomplete

- Advanced `.lth` scene syntax beyond the minimal experimental Phase 6B subset.
- Full scene branch merge workflow.
- Blender-backed preview scene rendering beyond optional probing.
- External viewer validation for GLB/USD/Blender outputs beyond local artifact creation.
- Real-image render repair after generated renders exist.
- Roblox Studio import/upload automation and Project Wonder product features.
