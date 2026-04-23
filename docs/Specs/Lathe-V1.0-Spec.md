# Lathe V1.0 Specification

## Working title
**Lathe 1.0: Self-Reliant Production Hard-Surface Asset Compiler**

## Status
Draft specification

## Assumptions
This specification assumes:
- V0.8 exists as the language-root expansion milestone.
- V0.9 exists as the self-reliant hero-prop compiler milestone.
- Lathe no longer depends on asset-generation AI in the critical path.
- Lathe is intentionally focused on **hard-surface, structurally programmable assets** rather than attempting to solve all of 3D at once.

---

## 1. Executive summary

Lathe V1.0 is the first release where Lathe can credibly claim to be a **standalone production asset compiler** for its target wedge.

A user writes Lathe source, runs one build command, and receives:
- an authoritative production mesh,
- a real high/low relationship,
- usable UVs,
- baked maps,
- authored PBR surfaces,
- pivots, sockets, anchors, collision, and LODs where relevant,
- deterministic package outputs,
- diagnostics, traces, and certification results.

V1.0 is not a prompt tool, model wrapper, or exporter script. It is a **programming language, compiler, and runtime** for production-ready hard-surface assets.

---

## 2. Product statement

Lathe V1.0 is the first **generalizable** release of the self-reliant Lathe thesis:

> A team should be able to specify hard-surface assets as code, build them through a governed compiler/runtime, validate them against explicit contracts, repair failures automatically when allowed, and package deterministic outputs for production use.

The public product identity is:

**Lathe is the programming language and compiler for production 3D assets.**

Not:
- a prompt wrapper
- a mesh toy
- a provider router
- a “generate and hope” pipeline

---

## 3. Strategic decision

### 3.1 No asset-generation AI in the critical path
For V1.0:
- `generate`, `assemble`, `adapt`, validation, repair, optimize, package, and publish MUST NOT require asset-generation AI.
- Lathe must remain self-reliant for its supported target wedge.
- Deterministic geometry, UV, bake, raster, and export infrastructure MAY be used internally.
- Classical deterministic vision or geometry fitting MAY be used where explicitly supported, but generative asset AI is not required.

### 3.2 Wedge discipline
V1.0 targets assets where code-defined structure is a genuine advantage:
- hard-surface hero props
- modular environment pieces
- mechanical assemblies
- structured containers, cabinets, doors, consoles, wall modules, crates, chests, and small rigid devices

V1.0 does not claim broad excellence on:
- organic characters
- sculptural creatures
- cloth-heavy assets
- hair/fur
- arbitrary irregular shapes

---

## 4. In-scope product surface

## 4.1 Asset kinds
V1.0 supports:
- `hard_surface_prop`
- `env_module`
- `mechanical_assembly`

## 4.2 Required build modes
V1.0 fully supports:
- `generate`
- `assemble`
- `adapt`

V1.0 includes limited support for:
- `reconstruct` as experimental, non-hero, non-core

## 4.3 Primary family coverage
V1.0 must ship a production-credible standard library for at least these families:
- `brassbound_chest`
- `industrial_crate`
- `mechanical_door`
- `console_terminal`
- `sci_fi_wall_panel`
- `service_cabinet`
- `control_pedestal`
- `supply_container`

At least **six** families MUST be hero-capable. Two more MAY be regression families if needed.

## 4.4 Output formats
Required package outputs:
- `usd`
- `glb`

Optional but supported where practical:
- `gltf`
- `fbx`
- `obj`

---

## 5. Core goals

V1.0 must:

1. Make Lathe source the primary authoring surface for the wedge.
2. Compile exact, crisp hard-surface geometry rather than approximate fused outputs as final truth.
3. Produce a real high/low + bake relationship for hero-capable families.
4. Produce real authored PBR surfaces for the supported family library.
5. Validate from evidence, not backend identity or bundle presence.
6. Support bounded repair and reselect loops that materially change outcomes.
7. Package deterministic outputs and traces.
8. Support CI-style, agent-friendly builds with no hidden state.

---

## 6. User promise

A V1.0 user should be able to write:

```lathe
asset ornate_loot_chest: hard_surface_prop from brassbound_chest uses shipping_prop {
  params {
    lid_arch_ratio = 0.29
    band_count = 4
    band_width = 3.2cm
    rivet_spacing = 5.5cm
  }

  intent {
    role = "ornate brassbound treasure chest"
    style = ["fantasy", "hero_prop", "stylized_realism"]
    materials = ["oak", "aged_brass", "red_velvet"]
    scale = 0.9m
    interactions = [open_lid, hold_loot, place_in_world]
  }

  build {
    shape { mode = generate fidelity = hero }
    topology { target_quads = 18000 ngons = forbid }
    uv { sets = [base, lightmap] texel_density = 512px_per_m }
    optimize { lods = 4 draw_calls = 2 texture_budget = 16mb }
  }

  validate {
    threshold = 0.90
    repair_policy = hero_prop_policy
  }

  package {
    formats = [usd, glb]
  }
}
```

run:

```bash
lathe build ornate_loot_chest.lth ornate_loot_chest --out dist
```

and receive:
- a production-ready authoritative mesh,
- high and low meshes,
- valid UVs,
- normal / AO / curvature / ID / ORM outputs,
- material-zone aware PBR textures,
- collision, pivots, sockets, and LODs where required,
- package exports,
- previews,
- a validation report,
- a trace explaining exactly what happened.

---

## 7. Language surface requirements

V1.0 freezes the first stable, expressive Lathe authoring surface for the wedge.

## 7.1 Required top-level declarations
V1.0 must support:

- `profile`
- `contract`
- `critic`
- `pattern`
- `component`
- `mechanism`
- `material`
- `surface_program`
- `family`
- `asset`
- `variant`
- `fixture`
- `test`
- `benchmark`
- `repair_policy`

## 7.2 Required family authoring capabilities
A `family` in V1.0 must be able to declare:
- parameters and bounds
- reusable components
- mechanisms
- assembly rules
- geometry mode and fidelity
- surface program bindings
- design-space search
- quality assertions
- default repair policy
- standard variants

## 7.3 Required component authoring capabilities
A `component` must be able to declare:
- parameters
- interfaces
- sockets/anchors
- mount requirements
- exact geometry rules
- feature classes
- seam classes
- edge classes
- material zones
- bake groups

## 7.4 Required material and surface capabilities
A `material` and `surface_program` must be able to declare:
- per-zone assignment
- base color behavior
- roughness behavior
- metallic behavior
- wear behavior
- cavity behavior
- detail normal generation
- decal/mask logic
- output map requirements

## 7.5 Required search capabilities
V1.0 source must support:
- `vary`
- discrete options
- bounded numeric ranges
- coupled constraints
- objective selection
- candidate count
- seeded determinism

---

## 8. Public source stability

## 8.1 Stability rule
V1.0 is the first release where Lathe source semantics are considered stable enough for:
- real repositories,
- reusable family libraries,
- code review,
- CI,
- agent editing,
- backward-compatible compiler evolution.

## 8.2 Compatibility promise
V1.0 compiler upgrades MUST preserve:
- declaration meaning
- build stage meaning
- family/component/material semantics
- package and trace contract compatibility where practical

If an internal implementation changes, the public source contract must not break without a formal migration path.

---

## 9. Compiler architecture

## 9.1 Required IR chain
V1.0 requires these IR layers:

- `IntentIR`
- `AssetGraphIR`
- `AssemblyIR`
- `FeatureIR`
- `ExactSolidIR`
- `MeshIR`
- `HighLowIR`
- `UVIR`
- `BakeIR`
- `SurfaceIR`
- `ValidationIR`
- `PackageIR`
- `TraceIR`

## 9.2 Stage flow
Required build flow:

1. parse
2. normalize
3. resolve declarations and stdlib references
4. instantiate family and parameters
5. compile `AssetGraphIR`
6. compile `AssemblyIR`
7. compile `FeatureIR`
8. compile `ExactSolidIR`
9. generate candidate bank
10. finalize authoritative mesh
11. derive high/low relation
12. generate UVs
13. generate bakes
14. generate surfaces
15. optimize
16. validate
17. repair or reselect if needed
18. package
19. publish hooks
20. audit output

## 9.3 Critical architecture rule
Exact hard-surface geometry must define final hero truth.

Approximate or fused intermediate representations MAY exist for search or internal integration, but MUST NOT define final hero geometry.

---

## 10. Exact geometry requirements

## 10.1 Geometry kernel
V1.0 MUST ship an exact hard-surface geometry compiler capable of:
- exact unions
- exact subtractive cuts
- shelling
- recesses and insets
- persistent panel seams
- lips and trims
- chamfers
- bevel bands
- bracket, hinge, handle, shroud, bezel, vent, clasp, and lock integration
- interface-preserving mounts

## 10.2 Hero geometry preservation
The final authoritative mesh must preserve:
- part identities
- seam classes
- hard-edge classes
- feature classes
- material zones
- bake groups
- sockets/anchors
- mechanism interfaces

## 10.3 Hero geometry prohibitions
Hero certification MUST NOT pass if:
- final geometry is merely marching-cubes output with no exact finalization,
- visible constructive stair-step artifacts remain beyond allowed limits,
- handle/hinge/feature integration is only nominal,
- seam classes are lost,
- edge treatment collapses to blockout-like surfaces.

---

## 11. Candidate generation and search

## 11.1 Candidate bank
V1.0 `generate` is deterministic design-space compilation, not model invocation.

Candidate generation MUST support:
- repeatable seeded runs,
- candidate banks,
- objective-based ranking,
- family-constrained search,
- feature-density variation,
- proportion variation,
- support/layout variation,
- attachment placement variation,
- material-parameter variation where allowed.

## 11.2 Required built-in objectives
V1.0 must include:
- `hero_prop_quality`
- `shipping_prop_quality`
- `runtime_efficiency`
- `assembly_readability`
- `surface_readability`

## 11.3 Search evidence
Candidate ranking MUST be based on observed evidence from:
- geometry quality,
- surface quality,
- runtime compliance,
- fixture comparisons where relevant,
- benchmark-calibrated visual gates.

---

## 12. High/low and bake requirements

## 12.1 High/low truth
Hero-capable V1.0 families MUST produce:
- a distinct high mesh,
- a distinct low mesh,
- explicit high/low relation metadata,
- bake groups.

## 12.2 Required bakes
Required hero bake outputs:
- `normal`
- `ao`
- `curvature`
- `id`

Recommended:
- `thickness`
- `cavity`

## 12.3 Bake integrity
A V1.0 build MUST fail hero bake checks if:
- high and low are effectively identical when distinction is required,
- bake groups are absent,
- map outputs are present but uninformative,
- bake cleanliness fails the threshold,
- material-zone/bake-group correspondence breaks.

---

## 13. Surface compiler requirements

## 13.1 Surface is not metadata
V1.0 surface generation must be real authored output, not passthrough labels.

## 13.2 Required hero outputs
Hero-capable families MUST emit:
- `basecolor`
- `normal`
- `orm`
- `ao`
- `curvature`
- `id`
- `emissive` where relevant

## 13.3 Required surface capabilities
Surface programs MUST support:
- directional grain or brushed variation,
- roughness variation,
- edge wear,
- cavity darkening or accumulation,
- mask-driven breakup,
- per-zone material assignment,
- family-appropriate decals or trim masks,
- procedural detail normal generation,
- map-level diagnostics.

## 13.4 Required hero material programs
V1.0 MUST ship first-party hero programs for:
- wood + aged brass
- painted industrial metal
- brushed metal + display glass
- ruggedized polymer + fastener accents
- door frame wear zones
- panel grime / vent accumulation

---

## 14. Deterministic downstream requirements

## 14.1 Topology
V1.0 topology runtime MUST support:
- manifoldness checks
- watertightness checks
- part boundary preservation
- seam preservation
- hard-edge preservation
- topology repair
- target polycount / quad bias support
- bake-aware topology handling

## 14.2 UV
V1.0 UV runtime MUST support:
- base UVs
- lightmap UVs
- texel-density enforcement
- material-zone aware packing
- seam-aware packing
- explicit UV diagnostics
- pack quality reporting

## 14.3 Collision/interfaces
Where required by family/profile, V1.0 MUST support:
- simple or convex collision generation
- pivots
- sockets
- anchors
- mechanism clearances
- interface validation

## 14.4 Optimization
V1.0 optimize stage MUST support:
- LOD derivation
- draw-call control
- texture-budget control
- atlas support where allowed
- mesh compression flags
- regression-safe package outputs

---

## 15. Validation and certification

## 15.1 Certification rule
A V1.0 build is certified only if:
- all `ensure` rules pass,
- all required family visual gates pass,
- quality score meets threshold,
- runtime budgets pass,
- repair policy is satisfied or exhausted,
- package integrity passes.

## 15.2 Evidence-based validation
V1.0 certification MUST be evidence-based.

It MUST NOT directly award quality credit for:
- backend identity,
- named bundle existence,
- map presence without content checks,
- nominal high/low relationships,
- declared but unobserved surface layering.

## 15.3 Required metrics

### Structural
- `part_coverage`
- `symmetry_score`
- `adjacency_score`
- `interface_sanity`
- `structural_richness`

### Geometry
- `silhouette_fidelity`
- `geometry_integration_quality`
- `bevel_continuity`
- `seam_quality`
- `shading_continuity`
- `stair_step_penalty`
- `boolean_scar_penalty`

### Surface
- `surface_authoring_quality`
- `material_zone_coherence`
- `normal_richness`
- `roughness_variation`
- `texture_entropy`
- `decal_coherence`

### Bake
- `bake_cleanliness`
- `highlow_distinction_quality`

### Runtime
- `texel_density_compliance`
- `draw_call_compliance`
- `texture_budget_compliance`
- `lod_compliance`

---

## 16. Repair and build policy

## 16.1 Repair classes
V1.0 MUST support:
- `reselect_candidate`
- `regenerate_candidate`
- `refine_geometry`
- `increase_feature_density`
- `restore_edge_treatment`
- `deepen_recesses`
- `repair_seams`
- `rebuild_highlow`
- `rebake`
- `reauthor_surface_layer`
- `repack_uvs`
- `rederive_lods`
- `repair_collision`

## 16.2 Required executor loop
The executor MUST support:

1. candidate bank generation
2. candidate evaluation
3. best-candidate selection
4. targeted repair if needed
5. re-evaluation
6. reselect vs repair vs regenerate decision
7. bounded stop on pass or exhaustion

## 16.3 Repair truth
Repairs MUST be:
- traceable,
- bounded,
- policy-constrained,
- intent-preserving.

A build must not appear “stable” if it only passed because the validator was flattering.

---

## 17. Standard library

## 17.1 V1.0 stdlib is required product surface
V1.0 MUST ship a first-party standard library containing:

### Families
- `std.families.brassbound_chest`
- `std.families.industrial_crate`
- `std.families.mechanical_door`
- `std.families.console_terminal`
- `std.families.sci_fi_wall_panel`
- `std.families.service_cabinet`
- `std.families.control_pedestal`
- `std.families.supply_container`

### Components
At least:
- shells
- lids
- doors
- frames
- panels
- straps/bands
- rivet rows
- hinges
- brackets
- bezels
- vents
- handles
- feet/supports
- lock plates
- clasps
- shrouds
- fastener strips

### Materials
At least:
- oak variants
- walnut variants
- painted steel variants
- brushed steel
- aged brass
- oxidized copper
- rubberized polymer
- display glass
- velvet or cloth liner where relevant

### Patterns
At least:
- plank spacing
- slat spacing
- fastener grids
- vent grilles
- trim bands
- rib arrays

### Repair policies
At least:
- `hero_prop_policy`
- `shipping_prop_policy`
- `mobile_prop_policy`
- `env_module_policy`

## 17.2 Family completeness requirement
Each hero-capable family MUST ship with:
- family declaration
- benchmark fixtures
- near-miss fixtures
- gold fixtures
- default repair policy
- at least three variants

---

## 18. Tooling and developer experience

## 18.1 Required CLI
V1.0 MUST ship:
- `lathe fmt`
- `lathe normalize`
- `lathe check`
- `lathe plan`
- `lathe build`
- `lathe doctor`
- `lathe test`
- `lathe bench`
- `lathe audit`
- `lathe patch`
- `lathe explain`

## 18.2 Agent and CI friendliness
V1.0 MUST support:
- machine-readable outputs,
- canonical formatting,
- semantic patching,
- deterministic normalization,
- repo-friendly diagnostics,
- auditable traces.

## 18.3 LSP and editor groundwork
V1.0 SHOULD ship an early but usable editor/tooling surface for:
- syntax highlighting
- AST-aware errors
- go-to declaration
- basic completion for stdlib symbols
- semantic hover info

---

## 19. Packaging and provenance

## 19.1 Required package contents
A certified V1.0 package MUST include:
- authoritative low mesh
- high mesh or high relation reference where appropriate
- required texture maps
- preview renders
- wireframe preview
- UV previews
- validation report
- manifest
- build trace
- normalized source reference
- output hashes

## 19.2 Trace requirements
Trace MUST capture:
- source hash
- normalized source hash
- family/component/material versions
- search seed
- candidate bank summary
- selected candidate
- rejected candidates and reasons
- repairs attempted/applied
- validator evidence
- package hashes

Trace MUST explain:
- what was built,
- why this candidate won,
- what repairs occurred,
- why the build passed or failed.

---

## 20. Benchmarks and evaluation

## 20.1 Required benchmark sets
V1.0 MUST ship:
- gold set
- near-miss set
- legacy-failure set
- regression set

## 20.2 Required evaluation goals
V1.0 MUST track:
- certification pass rate
- topology validity rate
- UV validity rate
- runtime budget compliance
- repair success rate
- trace fidelity
- asset-family coverage
- reduction in manual cleanup proxies
- human review acceptance rate on the hero wedge

## 20.3 Score distribution integrity
Scores MUST remain honest and non-collapsed.
If all strong outputs cluster near the ceiling, calibration is suspect and must be treated as a release blocker.

---

## 21. Non-goals

V1.0 is not trying to:
- solve organic asset creation,
- replace manual sculpting DCC workflows,
- become a general scene generator,
- support every imaginable asset family,
- rely on any asset-generation AI.

---

## 22. Release criteria

V1.0 ships only if all of the following are true:

1. At least six family libraries are production-credible.
2. At least three hero families produce visibly authored assets, not compiled-looking near-misses.
3. High/low + bake is real and validated.
4. Surface outputs are real and family-appropriate.
5. Evidence-based certification blocks weak compiled-looking results.
6. Repair materially affects outcomes on representative builds.
7. Offline self-reliant builds are fully functional.
8. Public Lathe source semantics are stable.
9. Packaging and traces are deterministic and reviewable.
10. No asset-generation AI is required anywhere in the critical path.

---

## 23. Final statement

Lathe V1.0 is the first release where Lathe can honestly say:

**“We do not prompt for these assets. We program them.”**

For the supported wedge, a user writes Lathe source and Lathe produces a certifiable build artifact: geometry, UVs, surface, runtime data, package, trace, and pass/fail result.

That is the V1.0 bar.
