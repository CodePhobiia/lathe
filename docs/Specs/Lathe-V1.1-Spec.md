# Lathe V1.1 Specification

## Working title
**Lathe 1.1: Deterministic Asset Ingestion, Reconstruction, Adaptation, and Assembly Runtime**

## Status
Draft specification

## Assumptions
This specification assumes:
- V1.0 exists as the self-reliant production hard-surface asset compiler.
- Lathe remains intentionally free of asset-generation AI in the critical path.
- V1.0 already proved a strong code-defined `generate` path for the target wedge.
- The next major value expansion is not “more novelty,” but **making Lathe practical across real production inputs**: existing meshes, modular kits, reference photos, scans, and platform retargeting.

---

## 1. Executive summary

Lathe V1.1 expands the V1.0 compiler from pure authored generation into a broader **deterministic asset operating system** for production teams.

V1.1 makes Lathe strong at:
- `adapt`
- `assemble`
- constrained `reconstruct`
- asset retargeting
- library-based reuse
- family-aware ingestion of existing production assets
- deterministic upgrade and downgrade flows
- scene-adjacent modular assembly for asset kits

V1.1 does **not** turn back toward asset-generation AI. Instead, it makes Lathe dramatically more useful by allowing teams to stay inside Lathe even when starting from:
- existing meshes,
- photo sets,
- scans,
- kit libraries,
- prior authored assets,
- platform/profile conversions.

---

## 2. Product statement

Lathe V1.1 is:

**A self-reliant production asset compiler that can generate, adapt, assemble, and reconstruct hard-surface assets from code and structured references without leaving the Lathe runtime.**

The central promise becomes:

> Whether a team is creating a new chest, adapting a cabinet to a mobile target, reconstructing a structured door from photos, or assembling a modular wall kit, the asset is still governed by Lathe source, Lathe contracts, Lathe repair policies, and Lathe certification.

---

## 3. Strategic goals

V1.1 has five top-level goals:

1. Make `adapt` a first-class production workflow.
2. Make `assemble` a first-class kit and modularity workflow.
3. Make `reconstruct` usable and honest for structured hard-surface assets without requiring generative AI.
4. Expand Lathe’s standard library from family authoring to **asset reuse and transformation**.
5. Keep the public language coherent while broadening practical runtime coverage.

---

## 4. Scope

## 4.1 In-scope build modes
V1.1 fully supports:
- `generate`
- `adapt`
- `assemble`

V1.1 upgrades `reconstruct` from experimental to **structured deterministic support** for target families.

## 4.2 In-scope reference types
V1.1 supports:
- Lathe-authored assets
- external meshes
- structured modular kits
- photo sets
- calibrated image sets
- simple scans / point clouds where they can be deterministically fitted
- material swatches / palettes
- family templates and library components

## 4.3 In-scope asset classes
V1.1 remains focused on:
- hard-surface props
- env modules
- mechanical assemblies
- modular kit pieces
- structured containers / doors / panels / consoles / cabinets / service devices

## 4.4 Out of scope
V1.1 does not attempt:
- freeform organic reconstruction
- arbitrary artistic sculpt fitting
- cloth reconstruction
- full scene generation
- unconstrained text-to-asset generation outside the family/compiler paradigm

---

## 5. Product promise

A V1.1 user should be able to do all of the following while staying in Lathe:

### Generate
Create a new chest or door from a family definition and get a certifiable build artifact.

### Adapt
Take an existing Lathe-authored cabinet and retarget it:
- from hero to mobile,
- from one material program to another,
- from one profile to another,
- from one family variant to another,
without leaving Lathe.

### Assemble
Build a modular wall panel set or industrial service kit from reusable components and certify that interfaces, clearances, pivots, and budgets are correct.

### Reconstruct
Take a small, structured hard-surface asset with photos or a scan, fit it into a known family or compatible component graph, and compile it into a certifiable Lathe asset.

---

## 6. Language expansion

V1.1 extends the V1.0 language with constructs needed for ingestion, reuse, and transformation.

## 6.1 New top-level declaration kinds
V1.1 adds:

- `library`
- `kit`
- `reference_set`
- `reconstruct_policy`
- `adapt_policy`
- `assembly_policy`
- `fit_profile`
- `transfer_rule`

These are additive to the V1.0 declaration set.

## 6.2 New block kinds
V1.1 adds or formalizes blocks such as:
- `refs`
- `fit`
- `transfer`
- `reuse`
- `constraints`
- `ingest`
- `assembly_rules`

## 6.3 New source concepts

### `library`
A named reusable collection of families, components, materials, mechanisms, patterns, and kit rules.

### `kit`
A reusable modular asset system with snap, mount, clearance, and compatibility rules.

### `reference_set`
A structured declaration of inputs such as:
- images
- calibrated images
- meshes
- scans
- swatches
- existing asset packages

### `reconstruct_policy`
A policy controlling how references may be interpreted, fitted, simplified, or rejected.

### `adapt_policy`
A policy controlling what may change during asset transformation.

### `assembly_policy`
A policy controlling modular composition, mount legality, snap rules, and collision/interface requirements.

### `fit_profile`
A reusable fitting profile for reconstruct/adapt operations.

### `transfer_rule`
A reusable rule for geometry, surface, UV, or semantic transfer across assets or families.

---

## 7. Source-level examples

## 7.1 Adapt example

```lathe
adapt_policy mobile_console_policy {
  allow = [reduce_feature_density, rebuild_highlow, rebake, reauthor_surface_layer, rederive_lods]
  preserve = [part_graph, interfaces, material_zones, silhouette]
  target_profile = mobile_runtime
}
```

```lathe
asset console_terminal_mobile: hard_surface_prop from console_terminal uses mobile_runtime {
  refs {
    assets = [asset_ref("console_terminal_hero.usda")]
  }

  build {
    shape { mode = adapt }
    optimize { lods = 3 draw_calls = 2 texture_budget = 8mb }
  }

  validate {
    repair_policy = hero_to_mobile_policy
  }
}
```

## 7.2 Assemble example

```lathe
kit industrial_wall_kit {
  modules = [wall_panel_a, wall_panel_b, door_frame_module, vent_module, pipe_module]
  snap_grid = 10cm
  clearance = 1cm
  allowed_joins = [panel_to_panel, panel_to_frame, panel_to_vent]
}
```

```lathe
asset service_corridor_wall: env_module from industrial_wall_kit {
  build {
    shape { mode = assemble }
  }

  assembly {
    repeat wall_panel_a count: 3
    insert door_frame_module at slot(2)
    mount vent_module at upper_left
    mount pipe_module at lower_right
  }

  validate {
    ensure collision_proxy
    ensure assembly_clearance_ok
  }
}
```

## 7.3 Reconstruct example

```lathe
reference_set chest_views {
  images = ["refs/chest_front.png", "refs/chest_side.png", "refs/chest_open.png"]
  calibrated = false
}
```

```lathe
reconstruct_policy chest_fit_policy {
  family_bias = brassbound_chest
  allow = [family_fit, component_reuse, silhouette_fit, dimension_inference]
  deny = [freeform_shape_invention]
}
```

```lathe
asset recovered_loot_chest: hard_surface_prop from brassbound_chest {
  refs {
    reference_sets = [chest_views]
  }

  build {
    shape {
      mode = reconstruct
      fit_profile = chest_fit_default
      reconstruct_policy = chest_fit_policy
    }
  }

  validate {
    repair_policy = hero_prop_policy
  }
}
```

---

## 8. Core compiler/runtime model

## 8.1 Build modes

### `generate`
As in V1.0, compile a new asset from family, components, geometry, search space, and surface programs.

### `adapt`
Transform an existing asset while preserving declared semantics and enforcing target profiles.

### `assemble`
Compose from compatible families/components/kit pieces.

### `reconstruct`
Fit structured references into a known family/component space, compile the result, and certify or fail it honestly.

## 8.2 Required runtime principle
V1.1 build modes must all route back into the same Lathe truth model:
- asset graph
- assembly semantics
- exact geometry
- high/low + bake
- surface
- validation
- repair
- package
- trace

No build mode is allowed to bypass certification semantics.

---

## 9. New IR requirements

V1.1 extends the IR chain with:

- `ReferenceIR`
- `FitIR`
- `TransferIR`
- `ReuseIR`
- `AssemblyConstraintIR`
- `KitIR`

## 9.1 Required IR chain for ingest flows
For `adapt`, `assemble`, and `reconstruct`, the build may include:

1. `ReferenceIR`
2. `FitIR`
3. `ReuseIR`
4. `TransferIR`
5. `AssemblyConstraintIR`
6. normal V1.0 IR chain from `AssetGraphIR` onward

## 9.2 Truth rule
Even when references are used, the final authoritative asset MUST still be represented as a Lathe-governed asset with:
- family or family-compatible structure,
- explicit material zones,
- explicit seams / edge classes,
- explicit interfaces,
- explicit validation and trace.

---

## 10. Adapt requirements

## 10.1 Adapt must be first-class
V1.1 `adapt` must support:
- hero-to-mobile retargeting
- platform/profile retargeting
- material program swaps
- topology budget changes
- LOD changes
- interface-preserving modifications
- family-compatible variant transforms

## 10.2 Adapt preservation controls
`adapt_policy` MUST support:
- what can change,
- what must stay fixed,
- geometry tolerance bands,
- surface tolerance bands,
- runtime budget priorities,
- acceptable repair classes.

## 10.3 Adapt trace
Trace MUST record:
- source asset identity
- inherited family
- transferred geometry/surface/UV features
- preserved semantics
- changed semantics
- reason for every significant adaptation

---

## 11. Assembly requirements

## 11.1 Modular assembly as product surface
V1.1 MUST treat modular asset assembly as a first-class product capability.

Required support:
- snap grids
- mount rules
- socket matching
- anchor matching
- clearance checking
- join legality
- repeated module layouts
- symmetry-aware repetition
- collision-aware composition

## 11.2 Kit definition
A `kit` MUST be able to declare:
- module inventory
- compatible joins
- snap grid
- clearance rules
- required anchors/sockets
- allowed repetition rules
- material compatibility rules where relevant

## 11.3 Assembly certification
Assembled assets MUST be validated for:
- join legality
- clearance
- collision
- silhouette continuity where declared
- part graph coherence
- runtime budgets
- naming / interface correctness

---

## 12. Reconstruct requirements

## 12.1 Reconstruct philosophy
V1.1 reconstruction is **family-constrained and structure-aware**, not unconstrained mesh hallucination.

It is allowed to:
- infer family parameters
- fit silhouettes and dimensions
- infer missing compatible subparts
- reuse known components
- regularize symmetry
- clean geometry
- recompile into a certifiable asset

It is not allowed to:
- invent arbitrary freeform hero geometry outside the supported family space
- bypass family/component rules
- hide low-confidence fitting as certainty

## 12.2 Supported reconstruct inputs
V1.1 reconstruct MUST support some combination of:
- image sets
- calibrated image sets
- simple scans
- point samples
- prior meshes
- silhouette masks
- measurement hints

## 12.3 Required reconstruct outputs
A successful reconstruct build must still emit:
- authoritative mesh
- high/low or justified equivalent if profile allows
- UVs
- surface outputs
- validation report
- fit confidence report
- trace of what was inferred versus reused

## 12.4 Honest failure
Reconstruct MUST fail when:
- family fit confidence is too low,
- geometry is too ambiguous,
- missing semantics cannot be inferred within policy,
- certification cannot be reached.

Lathe must not pretend reconstruct succeeded if it only produced a plausible-looking but uncertifiable asset.

---

## 13. Transfer and reuse

## 13.1 Reuse as product surface
V1.1 MUST support reuse of:
- components
- material programs
- bake groups
- kit modules
- profile-targeted optimization rules
- validated geometry subassemblies

## 13.2 Transfer rules
`transfer_rule` MUST support:
- geometry transfer
- UV transfer
- surface transfer
- material-zone transfer
- seam/edge-class transfer
- bake-group transfer
- interface transfer

## 13.3 Transfer safety
Transferred content MUST remain subject to:
- target family legality,
- profile legality,
- evidence-based validation,
- explicit trace.

---

## 14. Surface and materials in V1.1

## 14.1 Surface continuity across flows
V1.1 extends surface generation so it works not only for `generate`, but also for:
- `adapt`
- `assemble`
- `reconstruct`

## 14.2 Surface transfer
V1.1 MUST support:
- preserving material zones during adapt,
- remapping material zones during assemble,
- reauthoring surface outputs during reconstruct,
- surface downgrades/upgrades across profiles,
- decal/mask preservation where allowed.

## 14.3 Surface validation
Surface validation MUST expand to check:
- transfer integrity,
- per-zone coherence after assembly,
- surface continuity across joins,
- profile-appropriate surface density,
- bake transfer cleanliness.

---

## 15. Validation and certification expansion

## 15.1 New metric families
V1.1 adds validation for:

### Adapt
- `semantic_preservation_quality`
- `profile_retarget_quality`
- `transfer_integrity`

### Assembly
- `join_legality`
- `assembly_clearance_quality`
- `module_coherence`
- `assembly_surface_continuity`

### Reconstruct
- `family_fit_confidence`
- `component_fit_confidence`
- `measurement_consistency`
- `reconstruct_honesty_score`

## 15.2 Evidence-based rule persists
As in V1.0, V1.1 MUST NOT directly award quality credit for:
- mode name alone,
- reference presence alone,
- inferred components without evidence,
- transfer declarations without observed success.

## 15.3 Certification extension
A V1.1 build is certified only if:
- V1.0 rules pass,
- flow-specific evidence gates pass,
- transfer/fit constraints pass,
- trace is complete,
- repair policy is satisfied or exhausted.

---

## 16. Repair and build policy

## 16.1 Flow-specific repair
V1.1 adds repair classes for:

### Adapt
- `restore_preserved_semantics`
- `repair_profile_retarget`
- `rebuild_surface_transfer`

### Assembly
- `resolve_mount_conflict`
- `increase_clearance`
- `repair_join_continuity`
- `repack_module_layout`

### Reconstruct
- `regularize_symmetry`
- `refit_family_parameters`
- `replace_ambiguous_subpart`
- `rebuild_from_component_library`
- `increase_fit_consistency`

## 16.2 Build policy loop
The executor MUST support:

1. candidate or fit bank generation
2. evaluation
3. targeted repair
4. re-evaluation
5. reselect vs repair vs regenerate / refit
6. bounded stop

## 16.3 Reconstruct honesty
For reconstruct, the executor MUST be able to conclude:
- pass,
- fail,
- or “fit rejected as uncertifiable.”

It must not collapse all ambiguous cases into a weak pass.

---

## 17. Standard library expansion

## 17.1 Libraries and kits
V1.1 MUST add first-party standard libraries for:
- chest hardware sets
- industrial hardware sets
- modular wall kits
- mechanical door kits
- console/control panel kits
- service cabinet kits

## 17.2 Reusable reference fixtures
The stdlib SHOULD include:
- calibrated fixture templates
- reconstruct reference-set templates
- fit profiles
- transfer rules
- assembly policies

## 17.3 Variant libraries
V1.1 SHOULD ship reusable variant libraries such as:
- hero
- gameplay
- mobile
- damaged
- worn
- sealed
- locked
- open-state geometry where relevant

---

## 18. Tooling and workflow

## 18.1 Required CLI additions
V1.1 MUST add or strengthen:

- `lathe fit`
- `lathe reconstruct`
- `lathe adapt`
- `lathe assemble`
- `lathe explain-fit`
- `lathe diff-asset`

These may be implemented as submodes of `lathe build`, but the user-facing capability must exist.

## 18.2 Diffing
V1.1 MUST support useful diffs across:
- family variants
- adapted outputs
- assembly configurations
- reconstruct attempts
- profile retargets

## 18.3 CI and agent support
V1.1 MUST preserve:
- canonical normalization
- machine-readable diagnostics
- semantic patching
- deterministic build planning
- auditable traces across all flows

---

## 19. Packaging and provenance

## 19.1 Flow-specific trace additions
Trace for V1.1 MUST additionally include:
- reference hashes
- ingest summaries
- fit profiles used
- transfer rules used
- reused components
- assembly decisions
- rejected joins or fits
- reconstruct confidence breakdown
- adaptation delta summary

## 19.2 Package requirements
A V1.1 package MUST still include:
- authoritative outputs
- textures
- validation report
- trace
- normalized source reference
- previews

Additionally, when relevant, it SHOULD include:
- fit preview sheets
- join/assembly previews
- before/after diff previews
- transfer reports

---

## 20. Benchmarks and evaluation

## 20.1 New benchmark classes
V1.1 MUST add benchmark suites for:
- adaptation quality
- assembly correctness
- reconstruct honesty and fit quality
- profile retargeting
- transfer integrity

## 20.2 Required benchmark corpora
For each supported hero family, V1.1 SHOULD include:
- generate gold cases
- adapt gold cases
- assemble gold cases where relevant
- reconstruct gold cases where relevant
- near-miss cases
- legacy-failure cases

## 20.3 Evaluation targets
V1.1 must track:
- certification pass rate by flow
- adaptation success rate
- assembly legality pass rate
- reconstruct honest-pass rate
- reconstruct honest-fail rate
- manual cleanup reduction
- trace fidelity
- family coverage

---

## 21. Non-goals

V1.1 is not trying to:
- support arbitrary organic reconstruction,
- replace photogrammetry suites for all use cases,
- become a general scene tool,
- broaden into AI-first generation,
- sacrifice truthfulness for apparent convenience.

---

## 22. Release criteria

V1.1 ships only if:

1. `adapt` is production-credible for multiple families.
2. `assemble` is production-credible for modular kits.
3. `reconstruct` is honestly useful for structured hard-surface assets.
4. Family/component/material libraries support reuse across flows.
5. Flow-specific validation and repair materially affect pass/fail results.
6. Public source semantics remain stable.
7. No asset-generation AI is required anywhere in the critical path.
8. Traces explain ingestion, fitting, transfer, reuse, and repair decisions clearly.

---

## 23. Example rollout plan

### Phase 1 — Adapt depth
- hero-to-mobile retargeting
- material swaps
- platform/profile downgrades
- validation and repair for adapt

### Phase 2 — Modular assembly
- kit definition
- join legality
- clearance/collision validation
- kit package outputs

### Phase 3 — Structured reconstruct
- family-constrained reference fitting
- fit confidence
- component reuse
- honest pass/fail behavior

### Phase 4 — Shared reuse and transfer
- transfer rules
- diff tooling
- library-driven reuse
- benchmark expansion

---

## 24. Final statement

Lathe V1.1 is the release where Lathe stops being only a compiler for “newly generated” assets and becomes a true **asset-system compiler**.

A team should be able to:
- create new assets,
- adapt old ones,
- assemble modular kits,
- reconstruct structured hard-surface props from references,
- keep everything inside Lathe,
- and trust the same certification, repair, package, and trace model across all of it.

That is the V1.1 bar.
