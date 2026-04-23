# Lathe V1.3.1 Specification

## Working title
**Lathe V1.3.1: Codex-Controlled Blender Execution Plane**

## Status
Draft specification

## Assumptions
This spec assumes:
- V1.3 exists and has already established the core Blender integration model.
- Lathe remains the public language, compiler, and source of truth.
- Blender is already accepted as an internal deterministic execution VM, not the public authoring surface.
- The product decision to avoid asset-generation AI in the core geometry path remains in force.
- Codex is now elevated from an optional helper to the primary authoring and execution agent for Lathe in supported workflows.

## 1. Executive summary

Lathe V1.3.1 formalizes a new operating model:

**Codex writes the Lathe, executes the Lathe, inspects the resulting build through Blender via MCP, patches the Lathe, and iterates until the asset certifies or the declared repair/build policy is exhausted.**

V1.3.1 is not a Blender automation experiment. It is a product and platform milestone that turns Lathe into a closed-loop asset engineering system.

The user-facing identity remains unchanged:
- the user writes or supervises Lathe programs,
- Lathe is the language and build contract,
- Blender is an internal execution substrate,
- the certified packaged asset remains the product.

The major change is at the control plane:
- Codex becomes the primary active operator,
- MCP becomes the tool protocol between Codex and deterministic runtimes,
- the Lathe–Blender bridge becomes a typed compiler target,
- generated `.blend` files become build artifacts rather than authored truth.

## 2. Product statement

Lathe V1.3.1 is a **Codex-operable, Lathe-governed, Blender-executed asset compiler runtime** for the hard-surface wedge.

It is designed to let Codex:
- author and patch Lathe source,
- execute builds,
- inspect geometry, topology, UV, bake, surface, and export evidence,
- perform bounded repair/reselect/regenerate loops,
- and drive assets toward certification without breaking the Lathe source contract.

## 3. Goals

V1.3.1 must:
- make Codex a first-class authoring and execution agent for Lathe,
- expose a typed MCP tool surface for both Lathe and Blender,
- preserve Lathe source as the sole semantic source of truth,
- preserve `.blend` files as generated execution artifacts only,
- increase the strength of inspection, validation, and repair loops,
- make Codex-driven iteration materially faster and more grounded in visible evidence,
- remain compatible with the long-term Lathe product identity.

## 4. Non-goals

V1.3.1 is not intended to:
- replace Lathe source with Blender graphs or `.blend` editing,
- allow arbitrary, unsandboxed Blender Python as the default autonomous path,
- make Codex-specific semantics part of the public Lathe language surface,
- broaden the product into full-scene or character pipelines,
- use asset-generation AI as the geometry path,
- reposition Lathe as “a Blender automation script.”

## 5. Core thesis

The correct V1.3.1 system model is:

- **Codex** = operator / planner / patcher / execution brain
- **Lathe** = public language, compiler, source of truth, contract system
- **Lathe-MCP** = typed compiler and build tool interface
- **Blender-MCP** = typed deterministic geometry/surface/render inspection interface
- **Lathe–Blender bridge** = compiler backend translating Lathe IR into Blender-executable jobs
- **Blender** = deterministic execution VM and evidence generator
- **`.blend` files** = generated artifacts for execution, debugging, and trace, never the semantic source of truth

## 6. High-level architecture

### 6.1 System layers

#### Layer A — User / repository surface
- `.lth` source files
- normalized AST / schema outputs
- profiles, contracts, families, components, materials, tests, benchmarks
- repo docs, AGENTS.md, skills, and project configuration

#### Layer B — Codex control plane
- Codex CLI / app / IDE
- project config and MCP config
- repo skills and custom agents
- Codex-authored source patches
- Codex-run build/test/benchmark commands

#### Layer C — Typed tool plane
- `lathe-mcp`
- `blender-mcp`
- optional observability/telemetry endpoints

#### Layer D — Compiler/runtime plane
- parser / normalizer / checker / planner
- family/component/material stdlib
- candidate generation and build policy
- validation and repair planner
- packaging and trace

#### Layer E — Blender execution plane
- geometry execution
- modifier / Geometry Nodes execution
- UV execution
- bake execution
- material graph execution
- render fixtures
- export jobs

### 6.2 Source-of-truth rule

**The only semantic source of truth is Lathe source plus its normalized machine-readable form.**

Implications:
- `.blend` files MUST NOT be user-authored truth for normal workflows.
- direct Blender edits MUST NOT silently modify the semantic build result.
- any persistent change intended to survive rebuilds MUST round-trip through Lathe source or an explicit `adapt` / import pathway.

## 7. Codex role model

V1.3.1 defines Codex as the primary supported active operator for Lathe builds.

### 7.1 Codex responsibilities
Codex MUST be able to:
- write new Lathe source,
- patch existing Lathe source,
- invoke Lathe check/plan/build/test/bench operations,
- request Blender-backed inspections through MCP,
- interpret diagnostics and traces,
- choose repair, reselect, regenerate, or source-patch actions,
- explain why a build passed or failed,
- keep the repo aligned with contracts, tests, and benchmarks.

### 7.2 Codex boundaries
Codex MUST NOT:
- treat `.blend` files as the semantic source of truth,
- bypass Lathe contracts and validators when producing final outputs,
- use arbitrary Blender scripting as the default path when a typed bridge tool exists,
- silently mutate assets outside Lathe source.

### 7.3 Codex operating modes
V1.3.1 supports three Codex modes:

1. **Author mode**
   - create or refactor Lathe programs, families, materials, tests
2. **Build mode**
   - run check/plan/build/bench/audit flows
3. **Repair mode**
   - inspect evidence, patch source, rerun bounded loops

## 8. MCP architecture

V1.3.1 requires two typed MCP servers.

## 8.1 `lathe-mcp`

Purpose:
Expose the compiler/runtime control plane to Codex.

Required tools:
- `lathe.parse`
- `lathe.normalize`
- `lathe.check`
- `lathe.plan`
- `lathe.build`
- `lathe.audit`
- `lathe.bench`
- `lathe.test`
- `lathe.explain`
- `lathe.patch_source`
- `lathe.materialize_variant`
- `lathe.diff_builds`
- `lathe.list_backends`
- `lathe.list_benchmarks`
- `lathe.inspect_trace`
- `lathe.inspect_package`
- `lathe.run_doctor`

All tools MUST return structured machine-readable results.

## 8.2 `blender-mcp`

Purpose:
Expose deterministic Blender execution and inspection tools to Codex.

Required tools:
- `blender.execute_build_plan`
- `blender.open_artifact`
- `blender.render_preview`
- `blender.render_wireframe`
- `blender.render_normals`
- `blender.render_depth`
- `blender.render_uv_overlay`
- `blender.inspect_mesh_stats`
- `blender.inspect_topology`
- `blender.inspect_nonmanifold_regions`
- `blender.inspect_hard_edges`
- `blender.inspect_material_slots`
- `blender.inspect_uv_sets`
- `blender.inspect_bake_outputs`
- `blender.inspect_scene_hierarchy`
- `blender.inspect_geometry_nodes`
- `blender.export_package`
- `blender.snapshot_artifact`

Optional but recommended tools:
- `blender.render_turntable`
- `blender.render_fixture`
- `blender.inspect_collision`
- `blender.inspect_animation_constraints`

### 8.3 Prohibited default MCP behavior
The autonomous default path MUST NOT expose a generic “run arbitrary Python in Blender” tool as a first-class standard tool.

If such a tool exists for expert debugging, it MUST:
- be separate,
- require explicit approval,
- be excluded from normal autonomous build loops,
- be clearly marked unsafe or non-deterministic.

## 9. Tool contract requirements

### 9.1 Typed inputs and outputs
Every MCP tool MUST define:
- input schema
- output schema
- determinism class
- side-effect class
- required approvals
- artifact paths created or modified

### 9.2 Determinism classes
Allowed classes:
- `deterministic`
- `seeded`
- `best_effort`

### 9.3 Side-effect classes
Allowed classes:
- `read_only`
- `artifact_write`
- `source_write`
- `external_export`

### 9.4 Approval classes
Allowed classes:
- `none`
- `workspace_write`
- `artifact_write`
- `unsafe_execution`
- `external_network`

## 10. Lathe–Blender bridge

The bridge is the heart of V1.3.1.

### 10.1 Definition
The Lathe–Blender bridge is the compiler backend that lowers Lathe IR into Blender execution plans and lifts Blender artifacts/evidence back into Lathe build, trace, validation, and repair flows.

### 10.2 Required bridge properties
The bridge MUST:
- preserve Lathe semantics,
- preserve stable backend contracts,
- generate deterministic or seeded execution plans,
- emit structured `.blend` artifacts,
- expose evidence back to the validator,
- remain replaceable as an internal implementation detail.

### 10.3 Bridge IR handoff
Required flow:

1. Lathe source
2. normalized AST
3. `IntentIR`
4. `AssetGraphIR`
5. `AssemblyIR`
6. `FeatureIR`
7. `MeshIR` / `SurfaceIR` / `PackageIR` planning
8. `BlenderExecutionPlan`
9. Blender execution artifacts (`.blend`, images, bake outputs, exports)
10. `ValidationEvidenceIR`
11. `TraceIR`

### 10.4 Bridge output artifacts
The bridge MUST be able to emit:
- `.blend` build file
- structured object/collection manifest
- node-group manifest
- material-graph manifest
- UV manifest
- bake manifest
- render evidence manifest
- export manifest

## 11. Public language implications

V1.3.1 is primarily a runtime/control-plane milestone, but it may expose a small number of new Lathe declarations where doing so materially improves bridge control while preserving product identity.

Recommended public additions:
- `execution_profile`
- `library_binding`
- `render_fixture`
- `bake_profile`
- `inspection_policy`

These declarations must remain tool-agnostic in naming and semantics.

### 11.1 `execution_profile`
Defines runtime/backend posture for a class of assets.

Example concerns:
- offline-only
- blender-required
- hero-surface-enabled
- bake-quality tier
- render-fixture set

### 11.2 `library_binding`
Binds Lathe components/families/materials to reusable backend library assets while preserving Lathe source semantics.

### 11.3 `render_fixture`
Defines deterministic camera/light/render setups for inspection, validation, and benchmark evidence.

### 11.4 `bake_profile`
Defines bake map sets, resolutions, sample policies, dilation/padding policies, and acceptance thresholds.

### 11.5 `inspection_policy`
Defines what evidence must be gathered before a build may certify.

## 12. Example language usage

```lathe
execution_profile hero_blender_runtime {
  require backend(blender)
  require render_fixture(hero_prop_views)
  require bake_profile(hero_pbr_bakes)
  require inspection_policy(hero_visual_gate)
}

render_fixture hero_prop_views {
  views = [front_3q, side_3q, top, detail_close]
  shading = [beauty, wireframe, normals, uv_overlay]
}

bake_profile hero_pbr_bakes {
  maps = [normal, ao, curvature, id]
  resolution = 4096px
  padding = 16px
}

inspection_policy hero_visual_gate {
  require geometry_evidence
  require surface_evidence
  require bake_evidence
}

asset brassbound_chest: hard_surface_prop from brassbound_chest uses shipping_prop {
  build {
    shape {
      mode = generate
      fidelity = hero
      execution_profile = hero_blender_runtime
    }
  }
}
```

## 13. Backend IDs

V1.3.1 standardizes the following internal backend IDs.

### 13.1 Geometry
- `lathe.geometry.blender_modifiers_v1`
- `lathe.geometry.blender_gnodes_v1`
- `lathe.geometry.blender_exact_mesh_v1`

### 13.2 Topology
- `lathe.topology.blender_mesh_v1`

### 13.3 UV
- `lathe.uv.blender_uv_v1`

### 13.4 Bake
- `lathe.bake.blender_cycles_v1`

### 13.5 Surface
- `lathe.surface.blender_materials_v1`
- `lathe.surface.codex_imagegen_v1` (optional, subordinate, not required)

### 13.6 Render evaluation
- `lathe.render.blender_eval_v1`

### 13.7 Packaging
- `lathe.package.blender_export_v1`

### 13.8 Bridge
- `lathe.bridge.blender_execution_v1`

## 14. `.blend` artifact policy

### 14.1 Generated artifact rule
A `.blend` file produced by V1.3.1 is:
- a generated execution artifact,
- a debug artifact,
- a trace artifact,
- optionally a cache artifact.

It is NOT:
- the semantic source of truth,
- the canonical user-authored representation,
- a stable substitute for Lathe source.

### 14.2 Storage policy
Implementations MAY:
- store `.blend` files in build directories,
- cache them keyed by source/config/backend hash,
- retain them for benchmarks and evidence,
- discard them for clean CI or cache eviction.

### 14.3 Manual editing rule
Manual `.blend` edits MUST NOT automatically flow back into Lathe source.

If imports from `.blend` are ever supported, they must go through an explicit `adapt` or `import` pathway with traceable diffs.

## 15. Build loop semantics

V1.3.1 defines the supported Codex-controlled build loop.

### 15.1 Author loop
1. Codex reads or creates Lathe source.
2. Codex runs `lathe.check` and `lathe.plan`.
3. Codex patches source until the plan is structurally valid.

### 15.2 Execution loop
1. Codex runs `lathe.build`.
2. Lathe compiles to a Blender execution plan.
3. Blender executes geometry/UV/bake/material/render/export jobs.
4. Bridge returns artifacts and evidence.

### 15.3 Inspection loop
1. Codex queries Blender via MCP for previews and diagnostics.
2. Codex compares evidence to contracts, tests, and benchmarks.
3. Codex decides between:
   - source patch
   - reselect candidate
   - repair candidate
   - regenerate
   - stop/fail

### 15.4 Stop rule
The loop stops when:
- certification passes,
- a declared repair/build policy is exhausted,
- or a hard non-recoverable failure occurs.

## 16. Build policy upgrade

V1.3.1 requires the executor to support explicit branching among:
- `reselect_candidate`
- `repair_candidate`
- `regenerate_candidate`
- `patch_source`

The system MUST record which branch was chosen and why.

## 17. Codex skills and agent model

V1.3.1 SHOULD include repo-native skills and agents aligned to the new architecture.

### 17.1 Required skills
- `lathe-author-family`
- `lathe-build-debug`
- `lathe-bridge-debug`
- `lathe-blender-inspect`
- `lathe-repair-loop`
- `lathe-benchmark-calibrate`
- `lathe-surface-authoring`

### 17.2 Recommended custom agents
- `lathe_implementer`
- `lathe_reviewer`
- `blender_inspector`
- `lathe_validator`
- `surface_author`

### 17.3 Agent responsibilities
- `lathe_implementer`: source changes, grammar/runtime evolution
- `blender_inspector`: visual/geometry evidence gathering
- `lathe_validator`: certification analysis
- `surface_author`: bake/material/surface loop support
- `lathe_reviewer`: read-only quality and contract review

## 18. Validation and evidence

V1.3.1 requires stronger evidence-based validation.

### 18.1 Required evidence classes
- geometry evidence
- topology evidence
- UV evidence
- bake evidence
- surface evidence
- package/export evidence

### 18.2 Required render evidence
For hero or inspection-enabled profiles, the system MUST be able to produce:
- shaded preview renders
- wireframe renders
- normal or depth renders
- UV overlay renders when relevant
- material-zone isolated renders when relevant

### 18.3 Validation truth rule
Certification MUST depend on evidence, not merely:
- backend identity
- bundle presence
- file presence
- declared-but-unobserved relationships

## 19. Determinism and caching

### 19.1 Deterministic posture
V1.3.1 MUST support deterministic or seeded replay for all Blender-backed stages that claim determinism.

### 19.2 Cache keys
Cache keys MUST include:
- source hash
- normalized hash
- execution profile hash
- backend identity and version
- Blender version
- relevant library asset versions
- seed where applicable

### 19.3 Artifact reuse
The bridge MAY reuse `.blend` artifacts when cache-equivalent and semantically safe.

## 20. Security model

### 20.1 Security stance
Because Blender supports embedded Python and advanced automation, V1.3.1 MUST treat execution safety as first-class.

### 20.2 Required safeguards
- typed tool surfaces by default
- no arbitrary script execution on the default autonomous path
- explicit approval gates for unsafe execution
- isolated build directories
- clear provenance of all generated artifacts
- warning or rejection when opening untrusted `.blend` files with executable payload risks

### 20.3 MCP trust zones
Implementations SHOULD distinguish:
- trusted project tools
- trusted local runtime tools
- external-network tools
- unsafe execution tools

## 21. Local/CI/runtime modes

V1.3.1 MUST support:
- local interactive Codex mode
- local unattended Codex mode with bounded approvals
- CI/headless build mode
- review/audit mode

### 21.1 CI requirement
CI mode MUST be able to:
- run check/plan/build/test/bench,
- use headless Blender execution,
- emit machine-readable reports,
- fail loudly when required capabilities are absent.

## 22. Diagnostics

New required diagnostic families:
- `bridge_plan_generation_failed`
- `bridge_execution_failed`
- `blender_capability_missing`
- `blender_artifact_invalid`
- `render_fixture_failed`
- `uv_evidence_missing`
- `bake_evidence_missing`
- `surface_evidence_missing`
- `unsafe_blender_tool_blocked`
- `mcp_tool_contract_violation`

Diagnostics MUST say:
- what failed,
- where it failed,
- whether it is structural, runtime, or evidence-related,
- what recovery branches are available.

## 23. CLI additions

V1.3.1 SHOULD add:
- `lathe bridge doctor`
- `lathe bridge plan`
- `lathe inspect`
- `lathe render-fixture`
- `lathe bake-audit`

### 23.1 `lathe bridge doctor`
Checks Blender bridge availability, version compatibility, MCP status, library bindings, and cache directories.

### 23.2 `lathe inspect`
Retrieves structured inspection evidence from completed builds.

## 24. Repo layout requirements

Recommended new modules:
- `lathe/bridge/blender_execution.py`
- `lathe/bridge/blender_plan.py`
- `lathe/bridge/blender_artifacts.py`
- `lathe/bridge/library_bindings.py`
- `lathe/bridge/fixtures.py`
- `lathe/mcp/lathe_server.py`
- `lathe/mcp/blender_server.py`
- `lathe/inspection/evidence.py`
- `lathe/inspection/render_views.py`
- `lathe/inspection/mesh_checks.py`
- `lathe/inspection/bake_checks.py`
- `lathe/inspection/surface_checks.py`
- `.agents/skills/lathe-blender-inspect/`
- `.agents/skills/lathe-repair-loop/`
- `.codex/agents/blender_inspector.toml`

## 25. Acceptance tests

V1.3.1 MUST include acceptance tests that prove:
- Codex can author a Lathe family or asset and build it end-to-end through typed tools.
- Blender MCP can execute the build plan and return structured evidence.
- `.blend` files are generated but not treated as source of truth.
- Typed render/UV/bake inspection works.
- Repair/reselect/regenerate/source-patch branches are traceable.
- bridge failures are explicit and diagnosable.

## 26. Primary hero workflows

V1.3.1 hero workflows should focus on the current wedge:
- `brassbound_chest`
- `console_terminal`
- `mechanical_door`
- `industrial_crate`

Regression only:
- `sci_fi_wall_panel`
- `courier_drone`

These assets MUST be usable as Codex-driven benchmark and repair-loop examples.

## 27. Milestone plan

### Phase 1 — Control plane foundation
- implement `lathe-mcp`
- implement `blender-mcp`
- add typed tool schemas
- add project config and approvals model

### Phase 2 — Bridge implementation
- compile Lathe IR into Blender execution plans
- generate `.blend` build artifacts
- map families/components/materials to collections, node groups, materials, bakes, exports

### Phase 3 — Inspection and evidence
- render fixtures
- mesh/topology/UV/bake/surface inspection tools
- evidence ingestion into validators and traces

### Phase 4 — Codex repair loop
- source patching flows
- reselect/repair/regenerate logic
- benchmark/test integration

### Phase 5 — Hardening
- CI/headless operation
- determinism checks
- security gates
- version pinning
- documentation and skills

## 28. Release criteria

V1.3.1 is complete only if:
- Codex can create or revise Lathe source and complete a build loop through MCP,
- Blender execution is performed through typed bridge tools,
- `.blend` artifacts are generated and inspectable but not authoritative,
- render/UV/bake/material evidence is available to validators,
- at least one hero-family build demonstrably improves through the Codex-driven repair loop,
- failure modes are explicit and diagnosable,
- public Lathe source semantics remain stable.

## 29. Open questions

- Which Blender capabilities should remain mandatory vs optional in the bridge?
- Should Geometry Nodes be an implementation detail only, or can some node-backed family artifacts be cached as bridge assets?
- How much of surface authoring should be delegated to optional Codex image-generation backends vs deterministic material programs?
- What is the right boundary between source patching and bridge-local repair actions?
- How strict should the unsafe-tool approval posture be in local vs CI environments?

## 30. Final statement

Lathe V1.3.1 is the milestone where Codex stops being a helper and becomes the primary supported operator of the Lathe compiler, while Blender becomes a typed deterministic execution VM reachable through MCP.

The identity remains unchanged:
- Lathe is still the language.
- Lathe is still the contract.
- Lathe is still the source of truth.
- Blender is still subordinate.
- Codex is the brain operating the system.

If V1.3 made Blender a powerful backend, V1.3.1 makes the whole stack operationally coherent.
