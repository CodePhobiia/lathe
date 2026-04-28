# ForgeCAD Research for Lathe

Date: 2026-04-24

Repository under research: https://github.com/KoStard/ForgeCAD

Live docs: https://forgecad.io/docs

Local research clone: `%TEMP%/lathe_repo_research/ForgeCAD`

Inspected ForgeCAD commit: `0360c37`

## Executive Summary

ForgeCAD is one of the most relevant comparators for Lathe because it is not framed as a low-level geometry library. It is framed as a complete code-first CAD product loop: authoring language, browser studio, CLI, live parameters, multi-backend geometry, constraints, assemblies, examples, reports, benchmarks, and AI-agent documentation.

The most important thing Lathe can learn from ForgeCAD is the product loop:

1. Write a source model.
2. See it immediately.
3. Manipulate parameters live.
4. Preserve semantic feature identity.
5. Validate/export through the same engine from CLI and browser.
6. Package examples, docs, and AI context as first-class developer experience.

Lathe should not copy ForgeCAD's exact language choice. ForgeCAD treats JavaScript/TypeScript as the file format; Lathe's advantage is a declarative asset language with an explicit compiler pipeline, semantic checks, stage contracts, and certification. The right move is to borrow ForgeCAD's workflow architecture, not replace `.lth` with general-purpose code.

The strongest upgrades for Lathe are:

- A `lathe studio` or `lathe serve` browser loop over the existing compiler pipeline.
- First-class live parameters derived from `profile`, `asset`, `variant`, and future param metadata.
- A multi-kernel backend strategy: fast preview, robust exact geometry, and game/export packaging.
- Durable semantic references for features, faces, sockets, collision, LODs, and generated artifacts.
- Constraint/sketch semantics as a v0.2 language layer for precision hard-surface modeling.
- A parameter robustness scanner inspired by ForgeCAD's param-check workflow.
- A richer certification report with dimensions, cut planes, LOD/collision/material inventory, and visual evidence.
- A benchmark corpus for AI-authored Lathe assets.
- One-file agent docs and official Lathe skills.

## Research Method

I inspected the live ForgeCAD docs site, the public ForgeCAD GitHub repository, and a local clone of the public repository.

Important source observations:

- The live docs page identifies ForgeCAD as "Code-First Parametric CAD."
- The public README describes ForgeCAD as a multi-backend JavaScript/TypeScript CAD system with live parameters, constraints, assemblies, reports, and exact STEP/BREP export.
- The README says interactive browser modeling uses Manifold for fast geometry work while exact export runs through CadQuery/OpenCascade.
- The public repository is now a community home with examples, documentation, issues, and benchmarks; active development happens in a private repository.
- The examples corpus is broad and includes API examples, compiler corpus examples, constraint examples, benchmark prompts, G-code examples, generative art, showcase models, and toolbox models.
- The docs navigation covers core modeling, sketches, curves/surfaces, assembly, output, libraries, sheet metal, viewport, SDF, concepts, and CLI.

Source links:

- ForgeCAD docs: https://forgecad.io/docs
- ForgeCAD repository: https://github.com/KoStard/ForgeCAD
- ForgeCAD examples: https://github.com/KoStard/ForgeCAD/tree/mainline/examples
- ForgeCAD API examples: https://github.com/KoStard/ForgeCAD/tree/mainline/examples/api
- ForgeCAD benchmark examples: https://github.com/KoStard/ForgeCAD/tree/mainline/examples/bench-v2

## What ForgeCAD Is

ForgeCAD is a code-first parametric CAD environment for JavaScript/TypeScript. It positions the browser as the CAD system and also exposes CLI workflows for validation, rendering, export, report generation, and parameter checks.

The public README describes these capabilities:

- JavaScript/TypeScript modeling API.
- Live parameters.
- Constraint-based sketching.
- Assemblies.
- Reports and drawing-style output.
- Exact STEP/BREP export.
- Browser modeling with a fast geometry backend.
- Exact export through a CAD kernel path.
- Backend-aware public modeling layer.
- CLI and browser runtime parity.
- Agent-friendly docs and skills.
- LLM benchmark results.

The most important pattern is that ForgeCAD treats the source file, viewport, parameters, export formats, examples, benchmarks, and agent context as parts of one coherent system.

## Public Repository Posture

ForgeCAD's public repository is not currently a fully open implementation repository. The README states that active development happens in a private repository and the public repo is the community home.

What is public:

- README and product positioning.
- Examples.
- Benchmark folders.
- Documentation links.
- Issues and community surface.
- License.

What is not generally available in the public repo:

- The active core implementation.
- The full browser studio source.
- The full geometry/backend internals.

Lathe takeaway:

Lathe should be careful not to treat ForgeCAD as code to port. The value is in the product architecture, example discipline, workflow design, and feature priorities.

## Key ForgeCAD Findings

### 1. Browser Studio as the Main Loop

ForgeCAD treats the browser as a real CAD system. The README describes a browser CAD IDE with Monaco editing and a real-time 3D viewport.

Why this matters:

Lathe currently has a CLI/compiler orientation. That is good for correctness and automation, but it makes iteration slower for humans and coding agents. A browser loop would make the existing Lathe pipeline more legible:

- Source file on the left.
- Normalized model and diagnostics beside it.
- Build stage graph.
- Shape provider trace.
- Preview viewport.
- Variant controls.
- Certification report.
- Artifact explorer.

Lathe integration:

- Add `lathe studio <file.lth>` as a thin wrapper over the existing parser, normalizer, checker, planner, and executor.
- Keep Python/compiler code canonical.
- Use the browser only as an interface over the same build engine.
- Display the stable shape-stage handoff contract, currently `lathe.shape.intent_mesh_handoff_v1`, as a debuggable artifact.

This does not require changing the language first. It can begin as a viewer/report server over existing build outputs.

### 2. Multi-Backend Geometry as a Product Principle

ForgeCAD explicitly separates public modeling from backend implementation. It uses a fast interactive geometry lane and an exact export lane.

Why this matters:

Lathe already has backend and provider abstractions, but it needs a more explicit kernel strategy. Right now, Lathe's downstream runtime is credible as a v0.1 scaffold, but some stages are still reference/fallback oriented. ForgeCAD validates the idea that mature code-first CAD needs multiple geometry lanes.

Lathe integration:

- Define backend capability classes instead of one generic "shape provider" mental model.
- Suggested lanes:
  - `preview`: fast, forgiving, viewport-oriented mesh generation.
  - `exact`: robust solids, booleans, fillets, chamfers, STEP/BREP-style provenance.
  - `game`: watertight/game-ready mesh, UVs, LODs, collisions, sockets, engine packaging.
  - `report`: deterministic snapshots, dimensions, section cuts, measurements.
- Keep the current backend registry, but make kernel capability declarations more visible to the checker and planner.
- Require the planner to explain why a backend was selected and what fallback path was used.

Relevant Lathe areas:

- `lathe/backends.py`
- `lathe/shape_backend.py`
- `lathe/shape_providers.py`
- `lathe/executor.py`
- `lathe/checker.py`
- `lathe/planner.py`

### 3. Live Parameters and Sliders

ForgeCAD's examples use explicit parameter declarations that become live UI controls.

Why this matters:

Lathe already has concepts that are close to parameters: `profile`, `asset`, `variant`, and variant patches. What Lathe lacks is a first-class parameter metadata model that tells tools how to expose, bound, sample, and validate those values.

Lathe integration:

- Add non-breaking metadata for editable parameter ranges before changing core grammar.
- Derive UI controls for variants and profile values in `lathe studio`.
- Add parameter provenance to build outputs.
- Add parameter sampling to certification.

Potential future language shape:

```lathe
profile game_ready {
  parameter wing_span = 2.4 {
    min: 1.6
    max: 3.2
    unit: "m"
    ui: slider
  }
}
```

This should be treated as a v0.2 language proposal, not a silent v0.1 addition. It would require coordinated updates to the spec, grammar, schema, parser, normalizer, resolver, checker, examples, and tests.

### 4. Parameter Robustness Scans

ForgeCAD advertises a CLI workflow for sampling parameter combinations.

Why this matters:

Procedural assets often pass at the default size but fail when a dimension changes. Lathe is especially exposed to this because variants are a first-class concept and game assets need reliable LOD/collision/material outputs across variants.

Lathe integration:

- Add `lathe scan-variants <file.lth> <asset> --samples N`.
- Add `lathe scan-params <file.lth> <asset> --profile PROFILE --samples N` if parameter metadata lands later.
- For each sampled configuration:
  - normalize
  - check
  - plan
  - shape
  - topology
  - uv
  - material
  - optimize
  - package
  - certify
- Emit a summary table with failures grouped by stage and diagnostic code.
- Store failed configurations as reproducible fixtures.

This can start without a grammar change by sampling declared variants and variant patches.

### 5. Constraint-Based Sketching

ForgeCAD's docs and examples emphasize sketches, constraints, path builders, mechanical sketch examples, sketch-on-face workflows, and extrusions.

Why this matters:

Lathe's declarative asset language is good for high-level intent, but precision mechanical forms need lower-level feature control. Without a sketch/constraint layer, Lathe will struggle with assets that require:

- exact hole spacing
- brackets
- plates
- hinges
- panels
- fastener patterns
- mechanical interfaces
- repeatable bevels/chamfers/fillets
- named faces for sockets or attachments

Lathe integration:

- Add a v0.2 `sketch` or `feature` block.
- Support 2D primitives, constraints, dimensions, offsets, patterns, and extrusion/revolve/sweep operations.
- Keep it declarative.
- Make the checker detect underconstrained or contradictory sketches where possible.
- Preserve named sketch entities into semantic refs.

Possible language direction:

```lathe
shape {
  sketch base_plate on xy {
    rect "outer" centered width: 2.0 depth: 1.2
    circle "mount_a" at [-0.7, -0.4] radius: 0.06
    circle "mount_b" at [ 0.7, -0.4] radius: 0.06
    constraint equal_radius ["mount_a", "mount_b"]
  }

  feature extrude "plate" sketch: "base_plate" height: 0.08
}
```

This should not be rushed into v0.1 because it touches public language surface.

### 6. Semantic Refs, Named Faces, and Feature History

ForgeCAD's example names include face transformation history, feature-created faces, geometry info, edge queries, and placement references.

Why this matters:

This reinforces the same lesson from the `text-to-cad` research: serious code-first CAD needs stable semantic identity. Mesh triangle indices are not enough. Lathe should preserve intent-level names through the build pipeline.

Lathe integration:

- Introduce stable refs such as `@lathe[asset.variant.stage.feature.face]`.
- Emit selector sidecars in build artifacts.
- Preserve provenance from source intent to mesh outputs.
- Let downstream stages refer to semantic refs for:
  - sockets
  - collision volumes
  - attachment planes
  - UV seams
  - material zones
  - decals
  - rig joints
  - validation probes

Suggested artifact:

```json
{
  "contract": "lathe.refs.selectors_v1",
  "asset": "courier_drone",
  "variant": "mobile",
  "refs": [
    {
      "id": "@lathe[courier_drone.mobile.body.top_face]",
      "stage": "shape",
      "kind": "face",
      "source_path": "shape.features.body",
      "selector": {
        "normal": [0, 0, 1],
        "area_rank": 1
      }
    }
  ]
}
```

This integrates naturally with the existing stable shape handoff instead of replacing it.

### 7. Assemblies, Joints, and Kinematics

ForgeCAD has assembly examples and describes revolute, prismatic, fixed joints, and joint couplings.

Why this matters:

Lathe has stage concepts that point toward rigging, interfaces, and physics, but those areas are currently less mature than the parser/checker/planner/build path. For game assets, assemblies are not just mechanical CAD features; they map to practical game semantics:

- attachment sockets
- modular parts
- turrets
- doors
- landing gear
- hinges
- sliders
- destructible subparts
- animation pivots
- prefab hierarchy

Lathe integration:

- Treat `interface` and future rig/physics blocks as an assembly graph, not loose metadata.
- Add joint types as explicit semantic constructs.
- Validate that moving parts have:
  - named pivots
  - axis definitions
  - collision behavior
  - socket compatibility
  - material inheritance
  - packaging/export mapping
- Add a motion preview in `lathe studio`.

Potential future block:

```lathe
assembly {
  part "body" from feature "body_shell"
  part "rotor_arm_l" from feature "left_arm"

  joint "left_arm_fold" {
    type: revolute
    parent: "body"
    child: "rotor_arm_l"
    axis_ref: "@lathe[courier_drone.arm_left.hinge_axis]"
    limits: [-90deg, 0deg]
  }
}
```

### 8. Reports, Dimensions, BOM, and Section Cuts

ForgeCAD includes drawing/report concepts, dimensions, BOMs, cut planes, rendered views, and report export.

Why this matters:

Lathe should not only produce a mesh. It should produce evidence that the asset is valid. This is especially important if Lathe is meant to support AI-authored assets. A generated asset must be inspectable and certifiable.

Lathe integration:

- Extend certification output into a human-readable HTML/Markdown/PDF report.
- Add deterministic screenshots:
  - front
  - side
  - top
  - three-quarter
  - wireframe
  - collision overlay
  - LOD comparison
  - UV layout
  - section cut
- Add numeric inventories:
  - triangle count per LOD
  - material slots
  - texture memory
  - sockets
  - collision volumes
  - scale/dimensions
  - bounding box
  - warnings and fallback paths
- Add a BOM-like "asset inventory" for game production.

This can build on current certification rather than creating a separate subsystem.

### 9. CLI and Browser Runtime Parity

ForgeCAD emphasizes that browser and CLI run the same engine.

Why this matters:

Lathe should avoid a split where the browser preview has its own behavior and the CLI has the "real" behavior. That would make diagnostics, AI workflows, and user trust worse.

Lathe integration:

- `lathe studio` should call the same Python library entry points used by `python -m lathe.cli`.
- Browser state should be a view over compiler outputs, not a second compiler.
- Every UI action should map to a reproducible CLI command.
- Every failed build in the UI should produce a command users and agents can rerun.

Good command mapping:

```bash
python -m lathe.cli normalize examples/courier_drone.lth
python -m lathe.cli check examples/courier_drone.lth
python -m lathe.cli plan examples/courier_drone.lth courier_drone
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
python -m lathe.cli report examples/courier_drone.lth courier_drone --out dist/report
```

### 10. LLM Benchmarks as a Core Asset

ForgeCAD's public README and repository make model benchmark results visible. The benchmark folders include task-style examples.

Why this matters:

Lathe's likely users include coding agents. It should measure how well agents can author valid `.lth` assets. This is not a marketing side quest; it is a compiler/product quality signal.

Lathe integration:

- Add `examples/bench-v1/`.
- Each benchmark should include:
  - prompt
  - constraints
  - expected capabilities
  - reference solution
  - scoring script
  - generated outputs
  - certification report
- Score assets on:
  - parse success
  - semantic check success
  - build success
  - certification score
  - prompt compliance
  - geometry validity
  - game-readiness
  - source simplicity
  - use of stable refs

Example benchmark tasks:

- modular sci-fi crate with sockets
- courier drone with LODs and collision
- hinge assembly with motion limits
- low-poly vehicle wheel assembly
- wall-mounted control panel with labeled material zones
- stylized doorway kit with snap points
- weapon attachment rail with sockets and collision

### 11. Agent Skills and One-File Context

ForgeCAD exposes agent skill installation and a one-file context workflow.

Why this matters:

Lathe should be designed for coding agents from the start. A large repo is not enough; agents need concise, current, authoritative context.

Lathe integration:

- Add `lathe docs one-file --out lathe-context.md`.
- Generate a compact agent manual from:
  - `spec/lathe-v0.1.md`
  - grammar summary
  - schema summary
  - canonical commands
  - examples
  - backend capabilities
  - common diagnostics
  - artifact layout
- Keep official Codex/Claude/OpenCode skills in sync with the generated context.
- Add a CI check that generated agent context is current.

This aligns with the existing `.agents/skills` structure already present in the Lathe workspace.

### 12. Documentation Information Architecture

ForgeCAD docs are organized by product concepts: core, sketch, curves/surfaces, assembly, output, library, sheet metal, viewport, SDF, concepts, and CLI.

Why this matters:

Lathe's docs should not only describe syntax. They should teach the mental model of the compiler and asset pipeline.

Lathe documentation sections should become:

- Start Here
- Language Concepts
- Profiles and Contracts
- Assets and Variants
- Shape Intent
- Backends and Providers
- Build Stages
- Certification
- Stable Refs
- Examples
- CLI
- Agent Authoring Guide
- Backend Authoring Guide
- Troubleshooting
- Roadmap / Experimental Features

Searchable docs would matter once Lathe gains more examples and diagnostics.

### 13. Example Corpus Discipline

ForgeCAD's `examples/api` includes focused files for booleans, sketches, constraints, assemblies, gears, reports, imports, SDF, curves, viewport scenes, and verification. It also has `examples/compiler-corpus`.

Why this matters:

Examples are not just demos. They are regression coverage, agent training data, documentation, and product proof.

Lathe integration:

- Add `examples/corpus/` or `examples/compiler-corpus/`.
- Keep each example small and targeted.
- For every public feature, require:
  - one minimal example
  - one realistic example
  - one failing diagnostic fixture where appropriate
  - one certification fixture if it affects build output
- Use examples as docs and tests.

Suggested Lathe example groups:

- `examples/api/shape_intent/`
- `examples/api/materials/`
- `examples/api/lods/`
- `examples/api/collision/`
- `examples/api/sockets/`
- `examples/api/variants/`
- `examples/api/backend_selection/`
- `examples/api/certification/`
- `examples/compiler-corpus/`
- `examples/bench-v1/`

### 14. Experimental SDF Lane

ForgeCAD includes an experimental SDF area for organic forms, smooth booleans, and TPMS-like geometry.

Why this matters:

Lathe should eventually support organic or soft-surface procedural assets, but this should not distract from game-ready hard-surface correctness.

Lathe integration:

- Add SDF as an explicit experimental backend capability.
- Keep it behind opt-in contract/profile flags.
- Do not let experimental SDF behavior weaken the stable mesh handoff contract.
- Certify generated meshes with the same downstream pipeline.

Potential long-term uses:

- rocks
- terrain chunks
- organic sci-fi details
- smooth damage/deformation masks
- stylized vegetation

### 15. Manufacturing Features as a Pattern, Not a Priority

ForgeCAD covers sheet metal, G-code, STEP, BREP, flat patterns, and manufacturing-adjacent outputs.

Why this matters:

Lathe is currently framed around 3D asset generation, not manufacturing CAD. The useful idea is not "add G-code now." The useful idea is that a single source model can produce multiple downstream deliverables.

Lathe integration:

For Lathe, equivalent deliverables are:

- mesh bundle
- GLB/engine package
- LODs
- collision
- UVs
- material set
- sockets
- prefab metadata
- certification report
- semantic refs
- preview images
- source map/provenance

## What Lathe Should Copy

Lathe should copy these ideas directly:

- One source model drives all outputs.
- Browser and CLI share one engine.
- Live parameter controls.
- Parameter robustness checks.
- Multi-backend geometry architecture.
- Backend capability declarations.
- Example corpus organized by feature.
- Compiler corpus for regression behavior.
- Rich reports with dimensions and visual evidence.
- AI-agent context generation.
- Benchmark prompts and scoring for generated models.
- Stable semantic references across transformations.
- Named features and queryable generated geometry.

## What Lathe Should Not Copy

Lathe should not copy these parts:

- TypeScript as the asset file format.
- General-purpose scripting as the primary authoring surface.
- Private-core dependency as a trust model.
- Too many manufacturing-specific features before game asset basics are solid.
- Browser-only source of truth.
- A huge public API surface before diagnostics and compatibility rules mature.

## How This Integrates Into Lathe

### Current Lathe Strengths to Preserve

Lathe already has several advantages that ForgeCAD-style workflows can build on:

- A declarative language contract.
- Parser, normalizer, resolver, checker, planner, and executor separation.
- Explicit `profile`, `contract`, `critic`, `asset`, and `variant` concepts.
- Stable shape-stage contract: `lathe.shape.intent_mesh_handoff_v1`.
- CLI commands for normalize, check, plan, materialize, build, shape provider listing, and provider probing.
- A backend registry concept.
- Example assets.
- Regression tests.

The goal is not to replace this foundation. The goal is to make it more interactive, inspectable, robust, and agent-friendly.

### Integration Map

| ForgeCAD pattern | Lathe integration point | Compatibility level |
| --- | --- | --- |
| Browser CAD IDE | New `lathe studio` or `lathe serve` wrapper | Non-breaking |
| Live params | Profile/variant metadata and UI controls | Mostly non-breaking; richer params are v0.2 |
| Multi-backend CAD | `lathe/backends.py`, `shape_backend.py`, provider registry | Non-breaking if additive |
| Exact export lane | New backend capability class | Non-breaking if optional |
| Param scan CLI | New `lathe scan-variants` command | Non-breaking |
| Constraint sketches | New `sketch`/`feature` language blocks | v0.2 language change |
| Named faces/edges | Ref sidecars and provenance maps | Non-breaking if artifacts are additive |
| Reports/BOM | Certification report expansion | Non-breaking |
| Assembly joints | Rig/interface/physics semantics | Likely v0.2 if source syntax changes |
| Agent skill install | Generated docs and `.agents/skills` updates | Non-breaking |
| LLM benchmarks | `examples/bench-v1` and scorer scripts | Non-breaking |
| Compiler corpus | Focused example fixtures and tests | Non-breaking |

### Proposed Lathe Commands

These commands are inspired by ForgeCAD but shaped for Lathe:

```bash
python -m lathe.cli studio examples/courier_drone.lth
python -m lathe.cli serve examples/courier_drone.lth --asset courier_drone
python -m lathe.cli report examples/courier_drone.lth courier_drone --out dist/report
python -m lathe.cli scan-variants examples/courier_drone.lth courier_drone --samples 20
python -m lathe.cli snapshot examples/courier_drone.lth courier_drone --views front,side,top,iso
python -m lathe.cli refs inspect dist/courier_drone/refs/selectors.json
python -m lathe.cli docs one-file --out lathe-context.md
```

These should be implemented only after checking existing CLI patterns and test structure.

### Proposed Artifact Layout

ForgeCAD's report/export mindset maps well to richer Lathe build outputs:

```text
dist/
  courier_drone/
    source/
      normalized.json
      plan.json
    shape/
      intent_mesh_handoff.json
      provider_trace.json
    mesh/
      courier_drone.glb
      lod0.glb
      lod1.glb
      lod2.glb
    refs/
      selectors.json
      selectors.bin
      provenance.json
    certification/
      report.md
      report.html
      summary.json
      images/
        front.png
        side.png
        top.png
        iso.png
        collision_overlay.png
        uv_layout.png
```

### Proposed Certification Enhancements

Lathe certification should grow into a full production-readiness report.

Add checks for:

- stage fallbacks used
- provider selected
- geometry validity
- watertightness
- bounding box
- scale sanity
- origin/pivot sanity
- LOD triangle counts
- material slot count
- texture memory
- collision volume count
- socket count
- semantic ref coverage
- UV presence
- report screenshots

Add report sections:

- Build Summary
- Source and Variant
- Backend Selection
- Stage Trace
- Geometry Metrics
- LODs
- Materials
- Collision
- Sockets and Interfaces
- Semantic Refs
- Warnings
- Artifacts
- Reproduction Commands

### Proposed Benchmark Harness

Create a benchmark structure inspired by ForgeCAD's visible benchmark posture:

```text
examples/bench-v1/
  sci_fi_crate/
    prompt.md
    reference.lth
    rubric.json
    expected_artifacts.json
  hinge_panel/
    prompt.md
    reference.lth
    rubric.json
    expected_artifacts.json
  drone_variant_pack/
    prompt.md
    reference.lth
    rubric.json
    expected_artifacts.json
```

Scorer dimensions:

- Valid Lathe syntax.
- Semantic check success.
- Build success.
- Certification success.
- Variant robustness.
- Material/collision/socket completeness.
- Geometry budget compliance.
- Prompt compliance.
- Source readability.
- Deterministic artifact generation.

This would let Lathe measure whether AI agents are actually getting better at authoring `.lth` files.

## Roadmap

### Phase 1: Non-Breaking Product Loop

Goal: make Lathe easier to inspect without changing the public language.

Work:

- Add richer build reports.
- Add deterministic snapshots.
- Add artifact explorer metadata.
- Add `scan-variants` over existing variants.
- Add `examples/compiler-corpus`.
- Add `examples/bench-v1`.
- Add generated one-file agent docs.

Why first:

These changes improve usefulness immediately and do not require a language migration.

### Phase 2: Stable Refs and Provenance

Goal: make generated geometry addressable and inspectable.

Work:

- Add selector sidecars.
- Add provenance maps.
- Add `lathe refs inspect`.
- Add source-to-artifact mappings in reports.
- Add stable ref naming conventions.

Why second:

Refs become the foundation for sockets, attachments, UV zones, collision targeting, decals, and future sketch/feature semantics.

### Phase 3: Studio

Goal: give Lathe an interactive iteration loop.

Work:

- Add local web server.
- Render build plan and diagnostics.
- Preview generated artifacts.
- Show provider traces and fallbacks.
- Expose variants as controls.
- Link UI actions to exact CLI commands.

Why third:

The studio is more valuable once reports, refs, and artifacts are already structured.

### Phase 4: v0.2 Precision Modeling

Goal: add precision hard-surface modeling.

Work:

- Add `sketch` and `feature` language blocks.
- Add constraints and dimensions.
- Add named faces/edges/features.
- Add checker diagnostics for sketch errors.
- Add examples and tests.
- Update spec, grammar, schema, parser, normalizer, resolver, checker, planner, and docs together.

Why fourth:

This is the largest public language change and should be made only after the artifact/report/ref foundation exists.

### Phase 5: Assemblies and Motion

Goal: make Lathe asset behavior richer than static meshes.

Work:

- Add assembly graph semantics.
- Add joint types.
- Add motion limits.
- Add socket compatibility.
- Add motion preview.
- Add game-engine export mapping.

Why fifth:

This builds on stable refs, named features, and studio visualization.

## Risks and Tradeoffs

### Risk: Lathe Becomes Too Much Like CAD and Loses Game-Asset Focus

Mitigation:

Keep game production as the primary target. CAD-like features should serve LODs, collisions, sockets, materials, modularity, and engine export.

### Risk: Browser Preview Diverges From CLI

Mitigation:

Require browser actions to call the same Lathe compiler/runtime entry points as CLI commands.

### Risk: Parameter Metadata Becomes a Breaking Language Change

Mitigation:

Start with additive metadata and variant scanning. Move to v0.2 only when the grammar/schema/checker changes are coordinated.

### Risk: Stable Refs Are Hard to Preserve Across Fallback Backends

Mitigation:

Treat ref preservation as a backend capability. The planner and certification report should disclose when refs are exact, approximate, or unavailable.

### Risk: Reports Become Cosmetic

Mitigation:

Reports must be generated from machine-readable certification data. The HTML/Markdown/PDF view is presentation, not source of truth.

### Risk: Example Corpus Becomes Stale

Mitigation:

Wire examples into tests and CI. Every example should be either runnable, expected-failing, or explicitly experimental.

## Concrete Recommendations

1. Add `forgecad` lessons to Lathe's planning roadmap as product-loop upgrades, not source-porting tasks.
2. Prioritize `scan-variants`, richer reports, and examples before changing grammar.
3. Design stable refs and provenance sidecars as the next major artifact contract after `lathe.shape.intent_mesh_handoff_v1`.
4. Treat `lathe studio` as a viewer/controller over existing compiler outputs, not as a new compiler.
5. Add a benchmark corpus for AI-authored `.lth` files.
6. Generate one-file agent docs from the spec, schema, grammar summary, commands, examples, and diagnostics.
7. Use v0.2 for sketch/feature/constraint syntax, because it touches public language compatibility.
8. Make backend capabilities explicit: preview, exact, game, report, refs, assembly, experimental.
9. Expand certification from pass/fail into a production-readiness dossier.
10. Keep Lathe declarative and asset-focused.

## Bottom Line

ForgeCAD shows what Lathe can become when the language, compiler, viewer, examples, reports, and agent documentation are treated as one system. The right next level for Lathe is not "copy ForgeCAD's TypeScript API." It is:

- keep the `.lth` language,
- strengthen the backend and artifact contracts,
- make variants live and testable,
- preserve semantic refs,
- add visual/certification reports,
- build an interactive studio on top of the existing compiler,
- and create benchmarks that prove agents can reliably author production-ready assets.

ForgeCAD is a strong signal that code-first CAD products win through the full authoring loop, not just through shape generation. Lathe should apply that lesson directly to declarative, game-ready asset compilation.
