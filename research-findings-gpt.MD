# Lathe Research Findings

Prepared by: GPT/Codex
Research date: 2026-04-24
Repository: `D:\lathe_v0_1`

## Executive Summary

Lathe has a strong and unusual thesis: 3D assets should be compiled from a declarative source contract, then certified before use. That thesis is much stronger than "another text-to-3D wrapper." The current repository already contains a credible vertical slice: parser, resolver, checker, planner, backend registry, build executor, provider adapters, semantic/visual validation, and runnable examples.

The repo is not yet production-ready. The gap to "next level" is mostly not more syntax. The critical path is production asset reliability: robust geometry, real LOD/collision/socket/pivot semantics, standards-compliant packaging, deterministic certification reports, engine-native handoff, test/CI hardening, and a clear wedge workflow.

The strongest near-term positioning is:

> Lathe is a compiler and certification system for game-ready 3D assets, with learned 3D models used as proposal engines rather than trusted final authorities.

## Research Method

This report combines:

- Local repository inspection of source, specs, examples, tests, plans, and CLI behavior.
- Representative local validation commands.
- Build artifact inspection from a real `courier_drone` build.
- Current external research on OpenUSD, glTF/KTX2/meshopt, MaterialX/OpenPBR, Godot import workflows, robust manifold geometry, and learned 3D generation providers.

No source files were changed while researching. This report is the only new file.

## Current Repository Maturity

Assessment: core logic partially implemented; credible MVP vertical slice; not production-ready.

Confidence: high for local repository observations, medium for market/product prioritization, medium-high for standards recommendations.

### What Is Real Today

- CLI surface exists with parse, normalize, check, plan, materialize, build, doctor, provider probes, bridge tooling, surface tooling, inspect, bench, audit, explain, diff, and patch commands.
- Parser/resolver/checker/planner pipeline exists and handles public Lathe language concepts.
- A single production-shaped backend stack exists: `lathe.stack.hard_surface_game_asset_v1`.
- The stable shape contract `lathe.shape.intent_mesh_handoff_v1` is preserved.
- Build executor runs a full stage sequence: shape, topology, UV, surface, execution, rig, interfaces, physics, optimize, validate, package.
- Shape provider registry supports reference-conditioned, Hunyuan HTTP, and VGGT local provider paths.
- Semantic and visual quality validators exist and produce useful certification metrics.
- Example assets can pass `lathe check`, `lathe plan`, and at least one representative `lathe build`.
- Internal roadmap plans already identify the right product-quality and product-value gaps.

Relevant paths:

- `lathe/cli.py`
- `lathe/parser.py`
- `lathe/resolver.py`
- `lathe/checker.py`
- `lathe/planner.py`
- `lathe/backends.py`
- `lathe/executor.py`
- `lathe/shape_backend.py`
- `lathe/shape_providers.py`
- `lathe/visual_quality.py`
- `lathe/semantic_quality.py`
- `plans/08_product_quality.md`
- `plans/09_product_value_vision.md`

### What Is Still Narrow Or Scaffolded

- Only one backend stack is registered, so the backend abstraction has not yet been proven across materially different asset classes.
- `lathe fmt` is currently a parse/normalize stability check, not a canonical source formatter.
- Publish behavior is not a full signed release/publishing runner.
- Rig and interface stages emit stub backend IDs.
- Optimize stage clones LODs rather than generating real decimated or authored LODs.
- Texture memory accounting is effectively zero for the representative build path.
- Physics uses simple proxy behavior rather than a rich collision-generation pipeline.
- LSP support is a symbol index, not an editor-grade language server.
- Build cache is useful but implicit, temp-rooted, and not yet a user-facing content-addressed cache.
- CI appears incomplete: `.github` has a README but no obvious workflow suite.
- Full test suite did not complete within local timeouts during this study.

### Local Environment Observations

The repo has a working virtual environment, but the ambient `python` command points at system Python 3.14 while the venv uses Python 3.13. This matters because `python -m pytest` fails under the system interpreter due to missing dependencies, while the venv can run narrow tests.

This should be fixed through docs, scripts, `Justfile`, Makefile, CI, or a bootstrap command that always routes users to the expected interpreter.

## Validation Performed

Commands run from `D:\lathe_v0_1`:

```powershell
python -m pytest -q
```

Result: failed during collection under system Python because dependencies such as `trimesh` were missing.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Result: timed out after about 184 seconds with no useful progress output.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --durations=10
```

Result: timed out after about 604 seconds with no useful progress output.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_lathe.py tests/test_backends.py tests/test_doctor.py
```

Result: passed, `13 passed`.

```powershell
.\.venv\Scripts\python.exe -m lathe.cli check examples/courier_drone.lth
```

Result: passed with `ok: true` and no diagnostics.

```powershell
.\.venv\Scripts\python.exe -m lathe.cli plan examples/courier_drone.lth courier_drone
```

Result: produced a valid build plan using `lathe.stack.hard_surface_game_asset_v1`.

```powershell
.\.venv\Scripts\python.exe -m lathe.cli doctor --json
```

Result: venv dependencies were available, Blender was available through a WindowsApps shim, xatlas was available, Torch was CPU-only, VGGT was available but CPU-bound, and Hunyuan HTTP was configured but unavailable/refused.

```powershell
.\.venv\Scripts\python.exe -m lathe.cli build examples/courier_drone.lth courier_drone --out tmp_repo_study_build
```

Result: build passed and certified. The report produced `.usda` and `.glb` package outputs. The generated `tmp_repo_study_build` directory is a local research artifact and matches the repo's ignored `tmp_*` pattern.

## Build Artifact Findings

The representative `courier_drone` build is important because it shows both real value and current fragility.

Positive evidence:

- Build certified successfully.
- Package stage produced `.usda` and `.glb`.
- Validation score exceeded threshold.
- UV stage used xatlas successfully.
- Semantic metrics were strong for part coverage and silhouette fidelity.
- Visual metrics were sufficient to pass current thresholds.

Critical evidence:

- Shape provider path selected native-only/reference-conditioned behavior under the self-reliant policy, not a live learned generation path.
- Shape integration reported a constructive fallback because the geometry kernel was unavailable.
- Topology selected Blender subprocess but fell back to reference cleanup because Blender output was non-watertight.
- Optimize stage cloned LODs instead of producing distinct LODs.

Conclusion: the repo can certify a controlled hero build, but "real production asset compiler" requires much stronger geometry, topology, and downstream game-readiness guarantees.

## Strategic Positioning

Lathe should not compete head-on with Meshy, Hunyuan, Luma, or TRELLIS on raw visual novelty. That is a difficult race and changes too quickly. Lathe should compete on:

- Declarative asset source.
- Reproducibility.
- Contract checking.
- Certification.
- Provenance.
- Engine handoff.
- Automated repair.
- CI suitability.
- Agent usability.

The best slogan-level product promise is:

> The asset is not done when it looks good. It is done when the build passes.

## External Research Findings

### OpenUSD

OpenUSD is the right high-end interchange target for asset composition, variants, metadata, validation, and future pipeline integration. The official OpenUSD documentation exposes core concepts, tutorials, schemas, asset resolution, variants, and toolset entries such as `usdchecker`, `usdcat`, `usdview`, `usdzip`, and related utilities.

Recommendation:

- Treat OpenUSD as a first-class package target, not merely a text `.usda` emitter.
- Add USD validation as part of package certification.
- Use USD variants to represent Lathe variants where appropriate.
- Preserve Lathe certification metadata as custom layer/prim metadata.
- Consider `usdzip`/USDZ packaging once texture/material output matures.

Source: [OpenUSD documentation](https://openusd.org/release/index.html)

### glTF, KTX2, And Mesh Compression

glTF/GLB should remain the primary game-engine interchange format, especially for Godot and web preview. The Khronos registry is the right source for official extensions. The most relevant near-term standards are KTX2/Basis Universal texture delivery and meshopt compression.

Recommendation:

- Add glTF Validator to package certification.
- Add optional `KHR_texture_basisu` for compressed textures.
- Add optional `EXT_meshopt_compression` for game/runtime delivery.
- Track extension usage explicitly in package manifests.
- Emit engine compatibility notes when using extensions.

Sources:

- [Khronos glTF Registry](https://registry.khronos.org/glTF/)
- [KHR_texture_basisu](https://registry.khronos.org/glTF/extensions/2.0/Khronos/KHR_texture_basisu/)
- [EXT_meshopt_compression](https://registry.khronos.org/glTF/extensions/2.0/EXT/EXT_meshopt_compression/)

### MaterialX And OpenPBR

MaterialX is an open standard for material/look-development exchange, and recent MaterialX releases include OpenPBR support. OpenPBR is a standardized surface shading model hosted by the Academy Software Foundation.

Recommendation:

- Make Lathe surface programs compile to MaterialX graphs for advanced interchange.
- Use OpenPBR as the higher-fidelity material target.
- Keep simpler game-engine PBR maps as a derived output from the same material intent.
- Add material conformance checks: texture set completeness, color space, packed map layout, roughness/metalness conventions, and engine target compatibility.

Sources:

- [MaterialX](https://materialx.org/)
- [OpenPBR Surface specification](https://academysoftwarefoundation.github.io/OpenPBR/)

### Godot

Godot is a strong wedge because it is open-source, supports glTF/GLB well, and has workflows for imported scenes, inherited scenes, import configuration, and collision/import hints. Godot users also feel asset-pipeline friction acutely, which matches Lathe's certification value.

Recommendation:

- Build a first-party `lathe-godot` addon.
- Consume `.glb` plus Lathe `manifest.json`.
- Map Lathe anchors/sockets to `Marker3D`.
- Map collision output to `CollisionShape3D`.
- Expose certification status in the Godot editor.
- Provide a 90-second demo from `.lth` edit to certified in-engine asset.

Source: [Godot importing 3D scenes documentation](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/index.html)

### Robust Geometry

Robust topology is the heart of the product. If Lathe cannot reliably produce manifold, watertight, game-ready geometry, the rest of the compiler story weakens. The representative build already shows this: Blender topology produced non-watertight output and fell back to reference cleanup.

Recommendation:

- Promote robust manifold geometry to a P0 initiative.
- Evaluate Manifold or similar exact/robust boolean foundations.
- Store a feature/CSG/BRep-like intermediate representation before mesh realization.
- Keep feature edges, seams, pivots, anchors, and part semantics through topology.
- Make non-watertight output a hard failure in strict production mode.

Source: [Manifold geometry library](https://github.com/elalish/manifold)

### Learned 3D Providers

Hunyuan3D 2.1, VGGT, and TRELLIS are relevant provider targets, but they should not become Lathe's source of truth. Their outputs should be treated as candidate proposals that must pass Lathe contracts.

Recommendation:

- Keep deterministic native compilation as the trust anchor.
- Use Hunyuan-like systems for image/text-to-shape proposals and PBR texture proposals.
- Use VGGT-like systems for reconstruction and multiview geometry hints.
- Use TRELLIS-like systems as an additional proposal lane.
- Require provider cards, runtime diagnostics, hardware notes, licenses, and reproducibility metadata.
- Add benchmark harnesses that compare provider candidates by Lathe certification score, not only visual appeal.

Sources:

- [Hunyuan3D 2.1](https://github.com/tencent-hunyuan/hunyuan3d-2.1)
- [VGGT](https://github.com/facebookresearch/vggt)
- [TRELLIS](https://github.com/microsoft/TRELLIS)

## Highest-Leverage Upgrade Areas

### 1. Production Geometry Core

Priority: P0

Problem:

The current build can pass certification, but the artifact evidence shows fallback paths where robust geometry should be first-class.

Recommended work:

- Integrate or wrap a robust manifold/boolean geometry kernel.
- Define an internal feature graph or solid modeling IR.
- Preserve part identity across boolean/mesh realization.
- Add watertightness, body count, degeneracy, normal, and self-intersection checks as strict gates.
- Add golden geometry fixtures with expected topology invariants.
- Make Blender an adapter/export lane, not the only path to correctness.

Success criteria:

- Representative hard-surface heroes build without topology fallback.
- Watertightness is enforced in strict mode.
- Body count and part identity are stable across repeated builds.
- Geometry failures produce actionable diagnostics.

### 2. Real Game-Ready Stages

Priority: P0

Problem:

Lathe's current stage names promise a full game-asset pipeline, but several stages remain shallow or stub-like.

Recommended work:

- Rig: real pivots, hinges, transform origins, optional skeleton metadata for mechanical assets.
- Interfaces: sockets, anchors, snap points, connector orientation, gameplay tags.
- Physics: collision hulls, convex decomposition, simple/complex collision policy, mass/material hints.
- Optimize: real LOD generation, screen-size thresholds, texture memory accounting, draw-call/material-slot budgets.
- Package: per-engine manifests and import notes.

Success criteria:

- Godot import produces visible sockets, pivots, collisions, and LOD metadata.
- Certification report proves collision, pivot, and LOD readiness.
- Cloned LODs are eliminated from production profiles.

### 3. Certification Reports As A Product Surface

Priority: P0

Problem:

Certification is Lathe's core differentiator, but raw JSON is not enough for adoption.

Recommended work:

- Generate `report.html` beside `build_report.json`.
- Include pass/fail summary, score, thresholds, diagnostics, repair actions, package outputs, screenshots, mesh stats, material stats, and provider provenance.
- Add terminal report output for CLI users.
- Add links to artifacts and exact commands for reproduction.
- Add stable diagnostic/error codes.

Success criteria:

- A user can inspect why an asset passed or failed without reading raw bundles.
- Reports are deterministic enough for CI artifacts.
- Failed builds suggest concrete next actions.

### 4. Godot-First Engine Handoff

Priority: P1

Problem:

Lathe needs one engine workflow that feels magical and real. Godot is the most coherent wedge.

Recommended work:

- Create `lathe-godot` addon or in-repo integration package.
- Auto-import Lathe build folders.
- Convert manifest metadata into Godot nodes/resources.
- Expose certification state inside the editor.
- Ship one polished demo project.

Success criteria:

- User edits `.lth`, runs build, and sees a certified asset in Godot in under 10 minutes.
- Collision, pivots, sockets, and LODs arrive correctly.
- The demo can be recorded in a 90-second screen capture.

### 5. Standards-Grade Packaging

Priority: P1

Problem:

Lathe should become trustworthy by validating against external standards, not just internal expectations.

Recommended work:

- Add glTF Validator integration.
- Add USD validation where OpenUSD tooling is available.
- Add KTX2/Basis and meshopt support behind explicit package options.
- Add MaterialX/OpenPBR material export lane.
- Emit a package compatibility matrix per target engine.

Success criteria:

- Package certification includes external validator results.
- Manifest records standards extensions and target compatibility.
- Materials round-trip more predictably across DCC, USD, and engine targets.

### 6. Provider Proposal Harness

Priority: P1

Problem:

Provider adapters exist, but the product needs a disciplined way to compare and accept provider outputs.

Recommended work:

- Add provider benchmark suite across a fixed asset corpus.
- Record provider runtime, hardware, seed/config, license, output stats, and certification score.
- Add strict learned-provider mode that fails on fallback unless explicitly allowed.
- Build a candidate visualizer showing accepted/rejected deltas.
- Keep self-reliant native build path as the default trust anchor.

Success criteria:

- Hunyuan/VGGT/TRELLIS-like providers are evaluated by Lathe score.
- Provider failure cannot silently masquerade as success in strict mode.
- Users can understand when a learned model helped and when it was rejected.

### 7. Developer Experience And Reliability

Priority: P1

Problem:

The local repo works for a knowledgeable maintainer, but a new user may hit Python path issues, long silent test runs, and implicit cache behavior.

Recommended work:

- Add CI workflows for lint/type/test/build smoke.
- Split slow/integration tests from fast unit tests.
- Add test timeouts and progress output.
- Provide one blessed command for setup and validation.
- Promote cache to `lathe cache status|clean|warm`.
- Include dependency/environment diagnosis in error output.

Success criteria:

- Fresh clone setup is deterministic.
- Fast tests complete quickly.
- Full tests either pass or fail with visible progress.
- Cache invalidation is explainable.

### 8. Real Formatter And Language Tooling

Priority: P2

Problem:

Declarative source becomes more valuable when it is reviewable, format-stable, and editor-friendly.

Recommended work:

- Implement canonical formatter.
- Preserve comments.
- Add `lathe fmt --check`, `--stdout`, and in-place rewrite behavior.
- Expand LSP from symbol index to diagnostics, hover, completion, go-to definition, and document symbols.
- Add syntax highlighting packages for common editors.

Success criteria:

- `.lth` diffs become small and stable.
- CI can enforce formatting.
- Agent-authored Lathe source is easier to review.

### 9. Public Evidence And Benchmarks

Priority: P2

Problem:

The product claim needs external proof.

Recommended work:

- Publish a five-asset benchmark: industrial crate, wall panel, mechanical door, control pedestal, service cabinet.
- Compare Lathe native, Lathe learned, Meshy/Hunyuan standalone, Quixel closest match, and manual Blender pass.
- Measure wall-clock time, cost, tri budget, UV validity, collision, pivot correctness, Godot import success, reproducibility, and iteration speed.
- Publish raw data and methodology.

Success criteria:

- Users can see where Lathe wins and where it loses.
- Benchmarks reinforce the compiler/certification thesis.
- External reviewers can reproduce results.

## Recommended Roadmap

### Wave 0: Stabilize The Development Base

Time estimate: 1 to 2 weeks

- Fix Python/venv bootstrap.
- Add CI workflows.
- Split fast and slow tests.
- Add progress/timeouts for heavy tests.
- Document exact validation commands.
- Add cache status/clean visibility or at least cache diagnostics.

Why first:

Every later improvement needs a reliable development loop.

### Wave 1: Geometry And Topology Trust

Time estimate: 3 to 6 weeks

- Select robust geometry kernel strategy.
- Implement hard-surface feature/solid IR improvements.
- Eliminate non-watertight topology fallback on hero assets.
- Add strict geometry certification.
- Add regression fixtures and golden build checks.

Why next:

Lathe's promise collapses if geometry is unreliable.

### Wave 2: Game-Ready Asset Semantics

Time estimate: 3 to 5 weeks

- Real LODs.
- Real collision generation.
- Real pivots and sockets.
- Texture/material budgets.
- Engine-specific manifest fields.

Why next:

This turns "asset file exists" into "asset is usable in a game."

### Wave 3: Certification Report And Viewer

Time estimate: 2 to 3 weeks

- HTML report.
- Terminal report.
- Artifact viewer or `lathe serve`.
- Screenshot/evidence gallery.
- Stable diagnostic codes.

Why next:

This makes Lathe's value visible.

### Wave 4: Godot Integration

Time estimate: 3 to 5 weeks

- First-party Godot addon.
- Certified import folder workflow.
- Demo project.
- Editor certification panel.
- Manifest-to-node mapping.

Why next:

This gives Lathe a concrete wedge persona and a demo people can understand immediately.

### Wave 5: Standards And Provider Expansion

Time estimate: 4 to 8 weeks

- glTF Validator.
- USD validation.
- KTX2/Basis.
- meshopt.
- MaterialX/OpenPBR.
- Provider benchmark harness.
- Strict provider fallback policy.

Why next:

This makes Lathe credible in real pipelines and keeps learned models in a safe role.

### Wave 6: Public Proof

Time estimate: 4 to 8 weeks

- Five-asset benchmark.
- Gallery.
- Public roadmap.
- Design partner workflow.
- Agent integration docs.
- Hosted registry/CI-cert strategy.

Why next:

This converts technical progress into adoption.

## Suggested Immediate Sprint

If the goal is the highest return in the next 7 to 10 working days, do this:

1. Add CI and split fast/slow tests.
2. Fix environment bootstrap so the right Python is always used.
3. Add a `lathe report` or `--report html` path for current build reports.
4. Add explicit geometry/topology fallback diagnostics to the final build summary.
5. Add `lathe cache status` and document current cache behavior.
6. Create a design doc for the robust geometry kernel decision.
7. Turn the representative `courier_drone` fallback observations into regression tests or acceptance criteria.

This sprint does not overreach, but it makes every future claim easier to trust.

## High-Risk Areas

### Geometry Kernel Integration

Risk: adopting a robust geometry library may create dependency, build, or licensing complexity.

Mitigation:

- Prototype behind an optional adapter.
- Keep current deterministic fallback.
- Add clear kernel capability probes in `lathe doctor`.

### Learned Provider Expectations

Risk: users may expect learned providers to produce production assets directly.

Mitigation:

- Brand providers as proposal lanes.
- Make certification the acceptance mechanism.
- Document strict fallback behavior.

### Test Suite Runtime

Risk: slow/hanging tests will block contributors and CI adoption.

Mitigation:

- Mark integration tests.
- Add timeouts.
- Add progress output.
- Maintain a fast default suite.

### Scope Drift

Risk: Lathe could become a Blender wrapper, a model zoo, a game importer, and a SaaS all at once.

Mitigation:

- Keep compiler/certification as the center.
- Choose Godot as the first engine wedge.
- Keep learned providers replaceable.

### Standards Complexity

Risk: OpenUSD, glTF extensions, MaterialX, and engine import rules can sprawl.

Mitigation:

- Add one standard gate at a time.
- Record extension use in manifests.
- Maintain target compatibility profiles.

## Things Not To Prioritize Yet

- A broad marketplace before core asset quality is undeniable.
- Many engine integrations before Godot is excellent.
- More language features before formatter, diagnostics, and source stability.
- Learned-provider novelty races without certification gates.
- A paid CI product before validation thresholds are stable.
- Full web playground before reports and packaging are polished.

## North Star Acceptance Criteria

Lathe reaches a true next-level milestone when:

- Two backend stacks exist and pass representative builds.
- Full CI is green across supported platforms.
- Fast tests run quickly and full tests finish deterministically.
- Hero assets build without hidden topology fallback.
- Generated assets include real LODs, collisions, pivots, sockets, UVs, and material budgets.
- Package outputs pass external validators where applicable.
- Every build emits a human-readable certification report.
- A Godot user can import and use a certified asset with minimal manual cleanup.
- Learned providers can improve candidates but cannot bypass certification.
- Cache behavior is explicit and reproducible.
- `.lth` source is format-stable and editor-friendly.
- Public benchmarks show honest wins and losses.

## Final Recommendation

Lathe's next leap should be framed as "from compiler scaffold to certified asset pipeline." The most important work is not flashy; it is trust-building:

- robust geometry,
- real game metadata,
- strict certification,
- standards validation,
- engine-native import,
- reliable tests,
- visible reports.

If those land, Lathe becomes meaningfully different from both procedural DCC tooling and AI 3D generators. It becomes the thing that can tell an artist, developer, or coding agent: "This asset is safe to use because the build passed."

## Source Links

- [OpenUSD documentation](https://openusd.org/release/index.html)
- [Khronos glTF Registry](https://registry.khronos.org/glTF/)
- [KHR_texture_basisu](https://registry.khronos.org/glTF/extensions/2.0/Khronos/KHR_texture_basisu/)
- [EXT_meshopt_compression](https://registry.khronos.org/glTF/extensions/2.0/EXT/EXT_meshopt_compression/)
- [MaterialX](https://materialx.org/)
- [OpenPBR Surface specification](https://academysoftwarefoundation.github.io/OpenPBR/)
- [Godot importing 3D scenes documentation](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/index.html)
- [Manifold geometry library](https://github.com/elalish/manifold)
- [Hunyuan3D 2.1](https://github.com/tencent-hunyuan/hunyuan3d-2.1)
- [VGGT](https://github.com/facebookresearch/vggt)
- [TRELLIS](https://github.com/microsoft/TRELLIS)
