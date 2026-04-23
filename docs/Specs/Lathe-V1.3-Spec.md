# Lathe V1.3 Specification

## Working title
**Lathe V1.3: Blender Execution VM and Deterministic Authoring Backplane**

## Status
Draft specification

## Assumptions
This specification assumes:
- V1.2 exists and introduced a real surface compiler plus an optional Codex ImageGen bridge.
- V1.0 and V1.1 established Lathe as a self-reliant hard-surface asset compiler.
- The product decision is firm: **Lathe is the language, compiler, and runtime**; Blender is an internal execution substrate, not the user-facing authoring surface.
- No asset-generation AI is required in the critical path for geometry, topology, UVs, baking, validation, repair, optimization, packaging, or certification.

---

## 1. Executive summary

Lathe V1.3 integrates Blender as a **deterministic execution backend** for geometry, UVs, baking, surface graph realization, render evaluation, and export, while preserving Lathe as the public source of truth.

The purpose of V1.3 is not to turn Lathe into a Blender automation script. The purpose is to make Lathe **materially more powerful** for the hard-surface product wedge by compiling Lathe programs into a controlled Blender execution graph that can:
- realize higher-quality geometry and feature integration,
- improve UV, bake, and surface quality,
- support stronger render-based evaluation,
- use reusable node/component/material libraries,
- emit reproducible `.blend` artifacts for trace/debug,
- preserve stable Lathe source semantics.

V1.3 makes Blender part of the runtime implementation, not part of the product identity.

The user experience remains:
1. write Lathe,
2. run `lathe build`,
3. receive a certified packaged asset.

Not:
1. open Blender,
2. tweak node graphs by hand,
3. hope the output matches the contract.

---

## 2. Product statement

Lathe V1.3 is:
- a programming language,
- a compiler,
- a runtime,
- with Blender available as an internal deterministic authoring VM.

Lathe V1.3 is not:
- a Blender-first product,
- a `.blend` editing workflow,
- a Geometry Nodes authoring tool with a thin DSL on top,
- a DCC macro system,
- a Blender automation brand.

Lathe source remains the authoritative specification of:
- asset intent,
- assembly and family structure,
- quality bars,
- repair policy,
- search space,
- packaging contract,
- provenance.

Blender becomes a powerful way to execute parts of that contract.

---

## 3. Strategic rationale

V1.3 exists because Lathe’s bottleneck has moved.

Earlier milestones showed the same pattern repeatedly:
- Lathe improved semantic correctness faster than visible asset quality.
- The system became better at family structure, part graphs, and validation before it became truly good at crisp integrated hero geometry and surface quality.
- The remaining gap was no longer mainly “smarter generation.” It was “better execution of authored geometry, surfacing, baking, evaluation, and reusable component logic.”

Blender is a strong candidate execution substrate for exactly those gaps because it offers:
- headless/background execution,
- Python programmability,
- Geometry Nodes,
- mesh modifiers and booleans,
- UV tooling,
- Cycles baking,
- Principled BSDF-based material graphs,
- asset libraries,
- library overrides,
- broad interchange/export support.

The product opportunity is therefore:
- keep Lathe as the contract and language,
- use Blender to raise the quality ceiling of the deterministic runtime,
- never let Blender replace Lathe as the source of truth.

---

## 4. Scope

## 4.1 In scope

### Primary hero families
- `brassbound_chest`
- `console_terminal`
- `mechanical_door`
- `industrial_crate`

### Secondary regression families
- `sci_fi_wall_panel`
- `courier_drone`

### Asset kinds
- `hard_surface_prop`
- `env_module`
- `mechanical_assembly`

### Blender-backed runtime stages
- geometry realization
- modifier- and node-based feature integration
- topology-aware mesh realization where applicable
- UV generation and packing
- bake generation
- material graph realization
- render evaluation
- export/package realization

### Optional debug/authoring artifacts
- generated `.blend` files
- generated geometry-node groups
- generated material node groups
- generated asset-library datablocks
- render evidence packages

## 4.2 Out of scope
- making Blender the public authoring surface
- requiring users to hand-edit `.blend` files to complete a Lathe build
- broad organic-character support
- scene-layout generation as a primary target
- full manual rigging workflows
- replacing all of Blender’s UX with Lathe UX
- supporting arbitrary user Python embedded in Lathe source

---

## 5. Goals

V1.3 goals:
- raise the practical quality ceiling of Lathe’s hard-surface wedge,
- use Blender as a deterministic execution substrate without compromising Lathe’s identity,
- improve geometry integration, surface authoring, baking, and render-level evaluation,
- make reusable component/material libraries much deeper much faster,
- improve traceability by recording how Lathe mapped source intent into Blender execution,
- keep offline/local builds viable,
- preserve stable Lathe public semantics.

---

## 6. Non-goals

V1.3 is not trying to:
- make Blender optional for every build outcome immediately,
- solve all asset families,
- replace the need for Lathe’s own IRs and validators,
- move users from code into interactive node editing,
- market Lathe as “Blender automation for AI.”

---

## 7. Design principles

### 7.1 Lathe remains authoritative
Lathe source and Lathe IR remain the source of truth.

### 7.2 Blender is an execution VM
Blender is treated like an execution target or runtime VM for deterministic asset stages.

### 7.3 `.blend` files are artifacts, not source
Generated `.blend` files are build artifacts. They may be retained for trace/debug, but they are never the authoritative authoring layer.

### 7.4 Public semantics stay stable
Backend changes must not require source rewrites.

### 7.5 Deterministic where possible
Once a candidate is selected, Blender-backed stages should be deterministic under pinned versions and settings.

### 7.6 Evidence-based certification
The validator must judge geometry and surface quality from actual outputs, not from backend identity.

### 7.7 Safe execution by default
Blender scripting, extensions, and `.blend` execution must be governed by explicit trust and reproducibility policy.

---

## 8. Product positioning

Lathe should still be positioned as:

**“The programming language and compiler for production 3D assets.”**

Not:
- “a Blender automation script,”
- “a Geometry Nodes DSL,”
- “a DCC macro generator.”

Blender is a large and powerful internal substrate. It is not the product identity.

---

## 9. High-level architecture

V1.3 introduces a formal split:

### 9.1 Public layer
- `.lth` source
- normalized AST
- Lathe IR chain
- contracts / profiles / tests / benchmarks / repair policies
- CLI and automation surface

### 9.2 Runtime orchestration layer
- backend planner
- execution planner
- cache manager
- trace manager
- validator / repair loop controller

### 9.3 Blender execution layer
- Blender bridge
- background/headless launcher
- optional `bpy`-module execution path
- node-graph/material-graph generator
- bake/render/export drivers
- artifact capture and evidence packaging

### 9.4 Artifact layer
- package outputs
- trace and manifests
- render evidence
- optional `.blend` artifact
- optional library snapshots

---

## 10. Blender capability model

V1.3 treats Blender as capable of these runtime roles:
- headless execution,
- scriptable geometry processing,
- Geometry Nodes assembly,
- asset library hosting,
- material graph realization,
- Cycles-based baking,
- render-based evidence generation,
- USD/glTF/other export realization.

### 10.1 Required supported integration surfaces
V1.3 must support at least one of:
- background process execution via the Blender CLI,
- Python-module execution via `bpy`.

### 10.2 Required execution modes
- `background_cli`
- `python_module`

The implementation MAY support both. It MUST support at least one robustly.

### 10.3 Required Blender backend IDs
V1.3 defines these canonical backend IDs:
- `lathe.exec.blender_v1`
- `lathe.geometry.blender_gnodes_v1`
- `lathe.geometry.blender_modstack_v1`
- `lathe.topology.blender_mesh_v1`
- `lathe.uv.blender_uv_v1`
- `lathe.bake.blender_cycles_v1`
- `lathe.surface.blender_materials_v1`
- `lathe.render.blender_eval_v1`
- `lathe.package.blender_export_v1`
- `lathe.library.blender_assets_v1`

These are internal runtime contract IDs. They are not the primary authoring surface.

---

## 11. Language changes

V1.3 adds a small number of public constructs and fields. Most Blender-specific detail remains runtime/internal.

## 11.1 New declaration kinds
- `execution_profile`
- `render_fixture`
- `bake_profile`
- `library_binding`
- `material_graph`

## 11.2 `execution_profile`
Defines how a build should target an execution substrate.

Illustrative example:

```lathe
execution_profile hero_blender {
  engine = blender
  mode = background_cli
  deterministic = true
  preserve_blend = on_failure
  geometry_backend = blender_gnodes
  uv_backend = blender_uv
  bake_backend = blender_cycles
  surface_backend = blender_materials
  render_backend = blender_eval
  package_backend = blender_export
}
```

## 11.3 `bake_profile`
Defines bake intent and quality targets.

Illustrative example:

```lathe
bake_profile hero_pbr_bakes {
  maps = [normal, ao, curvature, id]
  target_resolution = 4096px
  normal_space = tangent
  cage_policy = auto
  require_highlow = true
}
```

## 11.4 `render_fixture`
Defines repeatable render-based evaluation context.

Illustrative example:

```lathe
render_fixture hero_prop_eval {
  views = [front_34, front, side, rear_34]
  shading = studio_neutral
  passes = [beauty, normal, depth]
  resolution = 1024px
}
```

## 11.5 `material_graph`
Defines a backend-agnostic material-graph program that may be realized as a Blender node graph.

Illustrative example:

```lathe
material_graph aged_brass_graph {
  base = aged_brass
  layers = [patina, edge_wear, cavity_oxidation]
  outputs = [basecolor, roughness, metallic, normal_detail]
}
```

## 11.6 `library_binding`
Allows stdlib authors or toolchain authors to bind abstract components/materials to execution-layer reusable assets.

Illustrative example:

```lathe
library_binding chest_hardware_blender {
  target = blender_assets
  catalog = "lathe/std/chest_hardware"
  maps {
    lock_plate -> lock_plate_asset
    clasp -> clasp_asset
    side_handle -> side_handle_asset
  }
}
```

## 11.7 Asset-level execution block
Assets MAY opt into or override an execution profile.

```lathe
asset brassbound_chest: hard_surface_prop from brassbound_chest_family uses shipping_prop {
  execution {
    profile = hero_blender
  }
}
```

---

## 12. Grammar additions

Illustrative grammar additions:

```ebnf
decl                 ::= ...
                       | execution_profile_decl
                       | render_fixture_decl
                       | bake_profile_decl
                       | library_binding_decl
                       | material_graph_decl

execution_profile_decl ::= "execution_profile" ident "{" assign_stmt* "}"
render_fixture_decl    ::= "render_fixture" ident "{" assign_stmt* "}"
bake_profile_decl      ::= "bake_profile" ident "{" assign_stmt* "}"
library_binding_decl   ::= "library_binding" ident "{" assign_stmt* mapping_block? "}"
material_graph_decl    ::= "material_graph" ident "{" assign_stmt* "}"

asset_decl             ::= "asset" ident ":" kind from_clause? use_clause? "{"
                             refs_block?
                             params_block?
                             intent_block?
                             execution_block?
                             build_block?
                             validate_block?
                             package_block?
                             publish_block?
                           "}"

execution_block        ::= "execution" "{" assign_stmt* "}"
```

---

## 13. IR additions

V1.3 requires these new IR layers or equivalents:
- `ExecutionIR`
- `BlenderExecutionIR`
- `NodeGraphIR`
- `MaterialGraphIR`
- `BakePlanIR`
- `RenderEvalIR`
- `BlendArtifactIR`
- `LibraryAssetIR`

### 13.1 `BlenderExecutionIR`
Must capture:
- pinned Blender version intent
- execution mode
- selected backend IDs
- node-group generation plan
- material-graph generation plan
- asset-library references
- bake plan
- render-eval plan
- export plan
- safety policy

### 13.2 `BlendArtifactIR`
Must capture:
- whether `.blend` is generated
- artifact path
- artifact hash
- asset collections
- node groups generated
- materials generated
- linked libraries used
- overrides created

---

## 14. Build semantics

## 14.1 High-level flow
The V1.3 build flow is:

1. parse and normalize Lathe source
2. resolve families, components, materials, profiles, tests, benchmarks
3. lower to Lathe IR chain
4. select execution profile
5. lower into `BlenderExecutionIR`
6. materialize an execution workspace
7. generate or update a `.blend` artifact
8. run geometry realization
9. run topology realization/cleanup where needed
10. run UV realization
11. run high/low and bake stages
12. run surface graph realization
13. run render-eval evidence passes
14. run validation
15. run repair/reselect/regenerate loop if allowed
16. package and export
17. emit trace, evidence, package, and diagnostics

## 14.2 Blender execution is internal
The user does not invoke Blender manually as part of the normal V1.3 experience.

## 14.3 `.blend` artifact policy
Generated `.blend` files are:
- transient by default,
- retained on failure,
- optionally retained for hero builds,
- never the primary source of truth.

---

## 15. Geometry backend requirements

## 15.1 Geometry Nodes backend
`lathe.geometry.blender_gnodes_v1` MUST support:
- parameterized family/component realization,
- procedural assembly from reusable node groups,
- deterministic parameter injection from Lathe,
- repeatable outputs under pinned versions/settings.

## 15.2 Modifier-stack backend
`lathe.geometry.blender_modstack_v1` MUST support:
- exact or near-exact hard-surface feature integration where node graphs are insufficient,
- boolean-based integration,
- bevel/weighted-normal workflows,
- shelling and inset/seam realization.

## 15.3 Geometry contract
The geometry stage MUST preserve:
- part identities,
- seam classes,
- edge classes,
- bake groups,
- material zones,
- sockets/anchors/mechanism interfaces where relevant.

## 15.4 Geometry quality requirement
The hero wedge must visibly improve versus purely compiler-native approximation-only paths. The integration must reduce the “compiled blockout” read.

---

## 16. Asset-library substrate

## 16.1 Blender asset libraries
V1.3 MAY use Blender asset libraries as a runtime substrate for:
- reusable hardware,
- node groups,
- material graphs,
- procedural families,
- hero surface templates,
- hero component kits.

## 16.2 Library rules
- Lathe stdlib remains authoritative.
- Blender asset library entries are implementation artifacts.
- asset catalogs must be reproducible from source or versioned runtime packages.

## 16.3 Library overrides
Library overrides MAY be used internally where needed for variant realization or linked-asset specialization, but those overrides MUST be generated and traceable.

---

## 17. Topology requirements

## 17.1 Blender mesh runtime
`lathe.topology.blender_mesh_v1` MUST support:
- cleanup after geometry realization,
- manifoldness/watertightness remediation where legal,
- part-boundary preservation,
- hard-edge preservation,
- hero high/low relation support.

## 17.2 Topology truth
Topology stages MUST not silently collapse part semantics just to reach cleanliness metrics.

---

## 18. UV requirements

## 18.1 Blender UV backend
`lathe.uv.blender_uv_v1` MUST support:
- base UV generation,
- seam-aware packing,
- lightmap UV generation when requested,
- texel-density reporting,
- hero-zone-aware UV preservation,
- deterministic island padding/dilation inputs for baking and texture work.

## 18.2 UV evidence
The trace MUST capture:
- UV backend used,
- UV sets emitted,
- pack statistics,
- texel-density diagnostics,
- lightmap results if applicable.

---

## 19. High/low and bake requirements

## 19.1 Bake backend
`lathe.bake.blender_cycles_v1` MUST support:
- bake planning from Lathe bake profiles,
- high/low relationship realization,
- tangent-space normal baking,
- AO, curvature, ID baking,
- cage or offset policy where required,
- deterministic image naming and output packaging.

## 19.2 Required hero outputs
Hero-tier assets MUST produce:
- `normal`
- `ao`
- `curvature`
- `id`

Optional but recommended:
- thickness
- cavity
- bent-normal

## 19.3 Bake truth
The validator MUST fail hero assets that claim high/low support without meaningful high/low distinction or acceptable bake cleanliness.

---

## 20. Surface runtime requirements

## 20.1 Blender surface backend
`lathe.surface.blender_materials_v1` MUST support:
- realization of Lathe material and material-graph programs into Blender node graphs,
- Principled-BSDF-centered PBR material realization,
- combination with V1.2 surface control packs and optional Codex ImageGen outputs,
- deterministic export-friendly surface graph flattening where needed.

## 20.2 Surface backend relationship to V1.2
V1.3 does not replace V1.2’s optional Codex ImageGen bridge.

Instead:
- Lathe remains authoritative,
- Blender realizes or refines material graphs and baked outputs,
- optional image-authored layers may be consumed as controlled inputs,
- deterministic fallback surface generation remains required.

## 20.3 Hero surface requirement
Hero families MUST support:
- real basecolor,
- normal and normal-detail integration,
- ORM outputs,
- zone-aware material graph realization,
- decals/masks where relevant,
- evidence-based surface validation.

---

## 21. Render evaluation requirements

## 21.1 Blender render-eval backend
`lathe.render.blender_eval_v1` MUST support:
- multi-view render fixtures,
- beauty, normal, and depth passes at minimum,
- consistent hero evaluation lighting,
- evidence packaging for validator and human review.

## 21.2 Validation usage
Render evaluation MUST feed evidence-based validators for:
- silhouette fidelity,
- shading continuity,
- seam visibility,
- bevel readability,
- surface plausibility,
- compiled/constructive artifact penalties.

## 21.3 Offline capability
The default evaluation path MUST remain usable in offline/local mode.

---

## 22. Export and package requirements

## 22.1 Export backend
`lathe.package.blender_export_v1` MUST support:
- `usd`
- `glb`

Optional:
- `gltf`
- `fbx`
- `obj`

## 22.2 Package determinism
Once the authoritative candidate is selected, package outputs MUST be deterministic under pinned Blender/runtime versions.

## 22.3 Artifact contents
A V1.3 package MUST include:
- exported formats,
- validation report,
- trace,
- preview renders,
- UV previews,
- bake outputs,
- surface outputs,
- normalized-source reference,
- optional `.blend` artifact reference when retained.

---

## 23. Repair semantics

## 23.1 Blender-aware repair classes
V1.3 adds repair classes such as:
- `adjust_node_parameters`
- `swap_node_group_variant`
- `modify_modifier_stack`
- `rerun_boolean_integration`
- `repack_uvs_blender`
- `rebake_cycles`
- `rebuild_material_graph`
- `rerender_eval_fixture`

## 23.2 Repair policy loop
The executor MUST be able to:
1. generate candidate bank,
2. select candidate,
3. run Blender-backed realization,
4. validate,
5. choose repair vs reselect vs regenerate,
6. re-evaluate,
7. stop on pass or bounded exhaustion.

## 23.3 Repair truth
Repairs MUST be traceable and must not silently drift away from source-declared family or contract semantics.

---

## 24. Determinism and reproducibility

## 24.1 Version pinning
V1.3 MUST pin:
- Blender version,
- relevant add-on/extension versions,
- runtime settings affecting outputs,
- execution mode,
- render/bake fixtures.

## 24.2 Environment trace
The trace MUST capture:
- Blender executable path or module version,
- execution mode,
- GPU/CPU mode if relevant,
- render device info where relevant,
- add-ons/extensions enabled,
- library paths used.

## 24.3 Cache policy
The system MUST support stage-local caching for:
- generated `.blend` artifacts,
- bake outputs,
- render-eval passes,
- export bundles,
- asset-library resolutions.

---

## 25. Security requirements

## 25.1 Safe execution
V1.3 MUST define safe defaults for Blender execution, including:
- isolated working directories,
- explicit trust policy for any script execution,
- disabling automatic execution of untrusted embedded scripts by default,
- generated code/scripts kept under traceable build control.

## 25.2 User-authored arbitrary Python
Lathe V1.3 MUST NOT require arbitrary user-authored Blender Python as part of normal public language usage.

## 25.3 Trusted extensions
If add-ons/extensions are required, they MUST be pinned and declared in the environment manifest.

---

## 26. CLI requirements

V1.3 adds these required CLI capabilities:
- `lathe probe-blender`
- `lathe build --execution-profile hero_blender`
- `lathe export-blend`
- `lathe inspect-blend`
- `lathe render-eval`
- `lathe library sync`

### 26.1 `lathe probe-blender`
Reports:
- Blender availability,
- executable or module mode,
- version,
- relevant extension/add-on health,
- GPU/CPU render capability,
- export capability,
- asset-library availability,
- diagnostic remediation steps.

### 26.2 `lathe export-blend`
Exports a generated `.blend` artifact for inspection while preserving Lathe trace linkage.

### 26.3 `lathe inspect-blend`
Produces a machine-readable summary of the generated `.blend` artifact:
- objects,
- collections,
- materials,
- node groups,
- linked libraries,
- overrides,
- bake targets,
- render fixtures.

---

## 27. Diagnostics

New required diagnostic families include:
- `blender_not_found`
- `blender_version_mismatch`
- `blender_autoexec_blocked`
- `blender_asset_library_missing`
- `geometry_node_group_missing`
- `modifier_integration_failed`
- `bake_runtime_failed`
- `render_eval_failed`
- `export_runtime_failed`
- `blend_artifact_generation_failed`

Diagnostics MUST remain machine-readable and traceable to stage and artifact.

---

## 28. Standard library implications

V1.3 requires the Lathe stdlib to support runtime bindings for:
- hero hardware components,
- node-based procedural families,
- material-graph templates,
- bake profiles,
- render fixtures,
- asset-library-backed reusable components.

The stdlib remains a Lathe concept first. Blender asset libraries are implementation backing, not the public standard library surface.

---

## 29. Example V1.3 program

```lathe
execution_profile hero_blender {
  engine = blender
  mode = background_cli
  deterministic = true
  preserve_blend = on_failure
  geometry_backend = blender_gnodes
  uv_backend = blender_uv
  bake_backend = blender_cycles
  surface_backend = blender_materials
  render_backend = blender_eval
  package_backend = blender_export
}

bake_profile hero_pbr_bakes {
  maps = [normal, ao, curvature, id]
  target_resolution = 4096px
  normal_space = tangent
  require_highlow = true
}

render_fixture hero_prop_eval {
  views = [front_34, front, side, rear_34]
  shading = studio_neutral
  passes = [beauty, normal, depth]
  resolution = 1024px
}

material_graph aged_brass_graph {
  base = aged_brass
  layers = [patina, edge_wear, cavity_oxidation]
  outputs = [basecolor, roughness, metallic, normal_detail]
}

asset brassbound_chest: hard_surface_prop from brassbound_chest_family uses shipping_prop {
  execution {
    profile = hero_blender
  }

  intent {
    role = "ornate brassbound treasure chest"
    style = ["fantasy", "hero_prop", "stylized_realism"]
    scale = 0.9m
    interactions = [open_lid, hold_loot, place_in_world]
  }

  build {
    shape {
      mode = generate
      fidelity = hero
    }

    surface {
      program = chest_hero_surface
      bake_profile = hero_pbr_bakes
      render_fixture = hero_prop_eval
    }

    optimize {
      lods = 4
      draw_calls = 2
      texture_budget = 16mb
    }
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

---

## 30. Engineering workstreams

## Workstream A — Blender bridge
- executable/module probing
- execution planner
- artifact workspace manager
- version pinning and manifests
- security policy

## Workstream B — Geometry backend integration
- Geometry Nodes codegen
- modifier-stack codegen
- component/family parameter injection
- exact/clean hard-surface realization for hero wedge

## Workstream C — UV and bake integration
- UV codegen and bake planning
- Cycles bake execution
- high/low relation materialization
- bake diagnostics and caching

## Workstream D — Surface graph integration
- material graph lowering
- Principled/PBR node graph realization
- V1.2 control-pack consumption
- texture export flattening

## Workstream E — Render evidence and validator integration
- render fixtures
- evidence pass capture
- validator adapters
- benchmark integration

## Workstream F — Asset-library substrate
- stdlib-backed asset catalogs
- reusable node groups
- material libraries
- override-safe variant realization

## Workstream G — Export and package integration
- USD/glTF backend realization
- package determinism
- blend-artifact retention policy
- trace and manifest integration

---

## 31. Acceptance criteria

V1.3 is successful only if:
- hero families visibly improve in geometry/surface quality under the Blender-backed execution profile,
- Lathe source remains the only required authoring surface,
- `.blend` artifacts are reproducible and traceable,
- generated `.blend` files are not required to be hand-edited for successful builds,
- UV and bake outputs are materially stronger for the hero wedge,
- render-based validation becomes more trustworthy,
- package exports remain deterministic after candidate selection,
- regression families do not break.

---

## 32. Release criteria

V1.3 ships only if all of the following are true:
1. `lathe probe-blender` is robust and high-signal.
2. At least the hero wedge builds successfully with `hero_blender` execution.
3. Hero surface/bake outputs materially improve over the non-Blender deterministic lane.
4. Generated `.blend` artifacts are reproducible and inspectable.
5. The validator can use render evidence from Blender.
6. Public Lathe source semantics remain stable.
7. Product positioning and docs do not collapse into “Blender automation.”

---

## 33. Risks

### 33.1 Product identity drift
If users start thinking “Lathe = Blender script,” V1.3 weakens the product.

### 33.2 Version drift
Blender versions, add-ons, and runtime behavior can drift and affect determinism.

### 33.3 Overfitting to one runtime
If too much intelligence lives only in Blender-specific node graphs, backend independence can erode.

### 33.4 Hidden manual edits
If `.blend` artifacts begin to be patched manually, the trace and source-of-truth model breaks.

### 33.5 Over-rewarding backend presence
The validator must not reward the build simply because a Blender backend ran.

---

## 34. Mitigations

- keep Lathe source authoritative,
- keep Blender behind stable backend IDs,
- pin versions and add-ons,
- treat `.blend` as generated artifact,
- disallow silent manual `.blend` truth,
- keep validation evidence-based,
- preserve a non-Blender fallback lane,
- keep public language Blender-agnostic where possible.

---

## 35. Final statement

Lathe V1.3 makes Blender a serious execution substrate for the hard-surface wedge without conceding the product surface.

The user still writes Lathe.
Lathe still owns the contract.
Lathe still decides whether the build passed.

Blender simply makes the runtime much more capable.

That is the correct V1.3 move:
**more power, without losing the language.**
