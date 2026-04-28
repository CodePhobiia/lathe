# Lathe V1.2 Specification

## Working title
**Lathe 1.2: Codex-Governed Surface Authoring and Texture Compilation**

## Status
Draft specification

## Assumptions
This specification assumes:
- V1.0 exists as the first self-reliant production hard-surface asset compiler.
- V1.1 exists as the deterministic ingestion, adaptation, assembly, and structured reconstruction release.
- Lathe remains intentionally **free of asset-generation AI in the 3D critical path**.
- Geometry, topology, UVs, packaging, validation, and repair remain Lathe-owned.
- V1.2 is the first release that treats **surface authoring as a first-class programmable domain** while allowing an optional Codex image-generation coprocessor for 2D map synthesis.

---

## 1. Executive summary

Lathe V1.2 is the release where surface authoring becomes a real product surface.

The central idea is simple:

> Lathe stays authoritative for what the asset is, how it is partitioned into material zones, what maps are required, how UVs are laid out, what bakes exist, what quality bars must pass, and what the final package must contain.
>
> Codex image generation may assist with 2D texture-map authoring, but only under a Lathe-controlled contract.

V1.2 does **not** make Codex image generation the product. It makes Lathe the product and Codex image generation an optional, governed stage inside the Lathe runtime.

This is consistent with the core product direction in the Concept Showcase, Product Vision, and PRD: Lathe must be a programming language, compiler, and runtime for production 3D assets; the certified packaged asset is the product; and the build signal must remain "the build passed," not "the model made something interesting." fileciteturn23file2 fileciteturn23file3 fileciteturn23file4

---

## 2. Why V1.2 exists

Earlier milestone lessons already established two important truths:

1. Lathe became more valuable when it owned semantic truth instead of letting an external generator define the asset. That was the core gain of the scaffold-first native wedge. fileciteturn23file1
2. Lathe improved semantic correctness faster than true geometry/surface quality whenever validators over-rewarded structural proxies. That was the core lesson of the geometry-quality and validator-calibration milestones. fileciteturn23file0

V1.2 applies those lessons to surfacing.

If Codex image generation is allowed to “texture the model however it wants,” Lathe becomes a wrapper again.
If Lathe defines zones, UVs, bake inputs, required outputs, validation rules, repair policies, and final assembly — and Codex image generation only fills controlled 2D authoring slots — then Lathe becomes stronger.

That is the V1.2 thesis.

---

## 3. Product statement

Lathe V1.2 is:

**A production asset compiler with a first-class programmable surface pipeline and an optional Codex-governed image-authoring backend for 2D map generation.**

Lathe V1.2 is not:
- an image-to-texture toy
- a prompt wrapper for image generation
- a replacement for Lathe-owned geometry, UV, bake, or package truth
- a retreat from the self-reliant thesis

The user promise becomes:

> A user writes Lathe source. Lathe compiles geometry, UVs, bakes, surface-control artifacts, surface maps, validation, repair, and packages. Codex image generation may be used for selected map-authoring steps, but the asset remains a Lathe-compiled artifact.

---

## 4. Scope

## 4.1 In scope
V1.2 adds first-class support for:
- programmable surface authoring in Lathe source
- zone-first material and surface compilation
- Surface Control Packs
- optional Codex image-generation surface authoring
- deterministic map derivation and atlas assembly
- evidence-based surface validation
- zone-local surface repair and re-authoring

## 4.2 Hero families
V1.2 surface hero focus is limited to:
- `brassbound_chest`
- `console_terminal`
- `mechanical_door`
- `industrial_crate`

## 4.3 Regression families
These must remain functional but are not the main surface showcase:
- `sci_fi_wall_panel`
- `courier_drone`
- `service_cabinet`
- `control_pedestal`

## 4.4 Out of scope
V1.2 does not attempt:
- image-generated 3D geometry
- AI-generated topology
- AI-generated UV layout
- AI-generated collision, pivots, or LOD logic
- generalized photoreal hero materials for every family
- a full shader-graph language as the public surface

---

## 5. Strategic decisions

### 5.1 No asset-generation AI in the 3D path
V1.2 keeps the existing rule:
- no asset-generation AI in the critical geometry path
- no image generation may define final mesh truth
- no image generation may bypass Lathe validation or repair

### 5.2 Codex image generation is optional, not mandatory
V1.2 must support two surface modes:

1. **Deterministic Lathe surface mode**
   - fully self-reliant
   - no external image-generation dependency
   - lower ceiling, reliable baseline

2. **Codex-assisted hero surface mode**
   - Codex image generation assists with selected texture/map authoring tasks
   - Lathe still governs control inputs, output contracts, validation, repair, and final map assembly

### 5.3 Zone-first, not atlas-first
Codex image generation MUST NOT be treated as a “paint the whole UV atlas in one shot” system.

V1.2 uses a **zone-first** design:
- author per material zone or per controlled sub-atlas
- derive/composite full atlases deterministically afterward

This is the only reliable way to preserve repeatability, seam safety, and material semantics.

---

## 6. Core goals

V1.2 must:
1. Make surface programs first-class Lathe source.
2. Make texture authoring a governed compiler stage instead of a post-process afterthought.
3. Let Codex image generation improve surface quality without weakening Lathe’s authority.
4. Add evidence-based surface validation that judges actual outputs, not bundle presence.
5. Support local re-authoring and repair of weak zones without rebuilding the whole asset.
6. Preserve deterministic fallback surfacing for offline/self-reliant builds.

---

## 7. User promise

A V1.2 user should be able to write:

```lathe
material oak_waxed {
  base = wood(species: oak, grain: longitudinal, tone: medium_dark)
  roughness = varied(base: 0.52, board_variation: 0.08)
  wear = edge_softening(amount: 0.22)
}

material aged_brass {
  base = metal(kind: brass, tone: dark_warm)
  roughness = varied(base: 0.38, oxidation: 0.12)
  wear = high_touch_edges(amount: 0.18)
}

surface_program chest_hero_surface {
  zones {
    wood -> oak_waxed
    hardware -> aged_brass
    liner -> velvet_red
  }

  authoring {
    backend = codex_imagegen
    mode = zone_first
    generate = [basecolor, wear_mask, decal_mask, detail_overlay]
    derive = [roughness, orm, normal_detail]
  }

  outputs {
    maps = [basecolor, normal, orm, ao, curvature, id]
    resolution = 4096px
  }
}
```

and then run:

```bash
lathe build brassbound_chest.lth ornate_loot_chest --out dist
```

and receive:
- high/low meshes
- UVs and lightmap UVs
- a Surface Control Pack
- baked maps
- authored surface maps
- seam-safe atlases
- validation report
- trace showing exactly which surface authoring stages ran
- certified package outputs

---

## 8. Language additions

V1.2 expands the public language in six areas.

## 8.1 New declaration kinds
V1.2 adds:
- `surface_backend`
- `surface_policy`
- `decal_library`
- `mask_program`
- `trim_sheet`
- `palette`

## 8.2 New or expanded blocks
V1.2 adds or formalizes:
- `surface`
- `zones`
- `authoring`
- `controls`
- `derive`
- `compose`
- `maps`
- `surface_validate`
- `surface_repair`

## 8.3 New public source concepts

### `surface_backend`
Declares the surface authoring backend and its guarantees.

Examples:
- `lathe.surface.deterministic_pbr_v1`
- `lathe.surface.codex_imagegen_v1`

### `surface_policy`
Defines required maps, allowed authoring backends, validation thresholds, resolution rules, and repair behavior.

### `mask_program`
Defines how masks are generated or interpreted for wear, decals, dirt, trim, panel lines, and other layered surfacing behavior.

### `decal_library`
Defines reusable decals, emblems, labels, warnings, serials, insignia, ornament layers, and trim overlays.

### `trim_sheet`
Defines reusable edge, band, frame, and ornamental trim textures and assembly rules.

### `palette`
Defines reusable constrained color/material palettes that can guide surface authoring.

---

## 9. Surface authoring semantics

## 9.1 Surface source of truth
In V1.2, surface truth comes from Lathe, not from Codex image generation.

The surface source of truth includes:
- material zones
- UV sets
- padded island masks
- bake maps
- required outputs
- resolution and texel density targets
- per-zone prompts or semantic descriptors
- deterministic derivation rules
- validation rules
- repair rules

Codex image generation may only author maps **inside** that contract.

## 9.2 Zone-first authoring
Required authoring modes:
- `zone_first`
- `subatlas_first`
- `deterministic_only`

`zone_first` is the required hero mode for V1.2.

## 9.3 Map classes
V1.2 distinguishes between:

### Image-authored maps
Suitable for Codex image generation or deterministic synthesis:
- `basecolor`
- `wear_mask`
- `decal_mask`
- `detail_overlay`
- `trim_overlay`
- `emissive_art`

### Deterministically derived maps
Must be derived or post-processed under Lathe control:
- `roughness`
- `metallic`
- `ao`
- `curvature`
- `id`
- `orm`
- `normal_detail`

### Bake-grounded maps
Must be anchored in actual geometry or bake truth:
- `normal`
- `ao`
- `curvature`
- `id`
- optional `thickness`
- optional `cavity`

---

## 10. New intermediate representations

V1.2 requires the following new IRs.

### `SurfaceIR`
Defines the semantic surface program, zones, materials, and target outputs.

### `SurfaceControlPack`
A structured artifact emitted by Lathe before external or optional image authoring.

It MUST contain:
- UV layout image
- padded island mask
- material-zone mask
- object/zone IDs
- AO
- curvature
- bake normals or normal reference
- optional thickness/cavity proxies
- preview renders
- required map list
- per-zone output constraints
- per-zone semantic descriptors
- target resolution
- mip/padding requirements

### `AtlasAssemblyIR`
Defines deterministic composition of zone-authored maps into full atlases.

### `SurfaceValidationIR`
Defines evidence-based checks on actual emitted texture maps and assembled atlases.

### `SurfaceRepairIR`
Defines zone-local repair and re-authoring tasks.

---

## 11. Runtime architecture

V1.2 requires the following runtime modules or equivalent roles:
- `lathe/surface_ir.py`
- `lathe/texture_control_pack.py`
- `lathe/atlas_assembler.py`
- `lathe/pbr_deriver.py`
- `lathe/surface_runtime.py`
- `lathe/validators/surface_quality.py`
- `lathe/repair/surface_repair.py`
- `lathe/codex_imagegen_bridge.py`

### 11.1 Required backend IDs
V1.2 standardizes these surface backends:
- `lathe.surface.deterministic_pbr_v1`
- `lathe.surface.codex_imagegen_v1`

### 11.2 Required trace behavior
Trace MUST record:
- selected surface backend
- attempted surface backend
- whether Codex image generation actually ran
- which zones were image-authored vs deterministic
- which maps were derived vs authored
- repair attempts and outcomes
- atlas composition details

---

## 12. Codex ImageGen bridge requirements

## 12.1 Role of Codex image generation
Codex image generation is allowed to author or assist with:
- zone-level basecolor
- hero wear masks
- decal sheets
- trim details
- detail overlays
- optional emissive art

It MUST NOT be the sole source of truth for:
- UV layout
- zone assignment
- exact material classification
- normal-map authority
- final ORM packing
- seam padding
- package correctness

## 12.2 Invocation model
The bridge must support:
- zone-by-zone authoring
- per-zone prompt assembly from Lathe source
- control-image injection from Surface Control Pack assets
- deterministic file naming and staging
- re-authoring of failed zones only

## 12.3 Failure behavior
If Codex image generation is unavailable or fails:
- the build MUST not silently pretend it succeeded
- trace MUST show failure explicitly
- policy MUST determine whether to fail, fall back, or continue deterministically

---

## 13. Surface validation

V1.2 must add evidence-based surface validators.

Required metrics:
- `surface_authoring_quality`
- `material_zone_coherence`
- `seam_continuity`
- `padding_safety`
- `normal_richness`
- `roughness_variation`
- `texture_entropy`
- `decal_coherence`
- `trim_coherence`
- `mip_safety`
- `bake_alignment_quality`
- `surface_render_plausibility`

Forbidden shortcuts:
- surface quality MUST NOT be granted merely because a hero surface bundle exists
- surface quality MUST NOT be granted merely because named files exist
- surface quality MUST NOT be granted merely because `codex_imagegen` was selected

---

## 14. Surface repair semantics

V1.2 surface repair must support:
- `reauthor_zone_basecolor`
- `reauthor_zone_wear_mask`
- `reauthor_zone_decal_mask`
- `rederive_zone_roughness`
- `rederive_zone_normal_detail`
- `reassemble_atlas`
- `increase_padding`
- `repair_seam_bleed`
- `repair_zone_coherence`
- `fallback_zone_deterministic`

Repairs must be:
- bounded
- zone-local where possible
- traceable
- compatible with global build policy

---

## 15. Build policy updates

V1.2 extends the executor loop:

1. build geometry and UV/bake prerequisites
2. emit Surface Control Pack
3. author zone maps (deterministic or Codex-assisted)
4. derive PBR-sensitive maps
5. assemble atlases
6. validate surface outputs
7. re-author or repair failed zones
8. re-evaluate
9. continue to package only on pass or bounded exhaustion

The executor must prefer **local zone repair** over full asset rebuild when failures are purely surface-local.

---

## 16. Packaging requirements

V1.2 packages must include, for hero surface builds:
- full texture atlases
- per-zone source artifacts where policy allows
- Surface Control Pack manifest
- high/low relation metadata
- baked map outputs
- surface validation report
- trace of zone authoring and repair

Optional but recommended:
- beauty renders
- turntable renders
- material-zone preview sheets

---

## 17. CLI additions

V1.2 adds or formalizes:
- `lathe surface-plan`
- `lathe surface-build`
- `lathe surface-validate`
- `lathe surface-repair`

### `lathe surface-plan`
Explains how Lathe will author surfaces:
- backend
- zones
- maps to generate
- maps to derive
- control images to emit
- validation gates

### `lathe surface-build`
Runs the surface stage in isolation when desired.

### `lathe surface-validate`
Evaluates only the surface outputs.

### `lathe surface-repair`
Attempts zone-local repair or re-authoring.

---

## 18. Standard library additions

V1.2 MUST add first-party surface programs and assets for at least:
- chest wood + brass hero materials
- painted industrial metal
- console housing + bezel + display + warning labels
- worn steel door with trim and handle system
- crate wood/metal hybrid

It MUST also add:
- decal libraries for industrial labels, warnings, serial marks, and fantasy ornamental motifs
- trim-sheet definitions for banding, frame edges, and ornamental borders
- reusable wear-mask programs

---

## 19. Benchmark requirements

V1.2 benchmarks must include:

### Gold surface set
Clearly good hero surfacing outputs for target families.

### Near-miss surface set
Maps that are structurally present but visually weak or incoherent.

### Legacy-failure set
Prior outputs that passed because bundle presence was over-rewarded.

### Zone-failure corpus
Examples of:
- seam bleed
- weak roughness variation
- flat normal detail
- incoherent decal placement
- poor material separation
- mip-unsafe padding

Success criteria:
- high positive pass rate
- high near-miss fail rate
- high legacy-failure fail rate
- honest score distributions

---

## 20. Hero acceptance criteria

V1.2 hero surface support counts as successful only if all of these are true:
- at least three hero families have materially better visible surfaces than V1.1/V1.0 equivalents
- Codex-assisted outputs are visibly stronger than deterministic fallback on at least one family
- deterministic fallback still produces certifiable baseline outputs
- weak Codex-authored surface zones fail under evidence-based validation
- failed zones can be repaired without rebuilding the whole asset
- final packaged outputs remain deterministic once the authoritative zone maps are selected

---

## 21. Non-goals

V1.2 is not trying to:
- replace Lathe’s self-reliant geometry core with image generation
- make image generation mandatory for success
- solve all materials for all asset families in one release
- expose raw image-prompt engineering as the public UX
- weaken certification just because image-authored maps look visually rich

---

## 22. Release criteria

V1.2 ships only if:
1. `codex_imagegen` surface backend works as an optional governed stage.
2. Surface Control Packs are real and reproducible.
3. Zone-first atlas assembly is real and deterministic.
4. Evidence-based surface validation is in place.
5. Deterministic fallback surfacing remains functional.
6. At least three hero families show meaningful visible improvement.
7. Old “surface bundle exists” near-miss outputs now fail.
8. Trace and diagnostics clearly show what happened.

---

## 23. Final statement

Lathe V1.2 is the release where surface authoring becomes a first-class compiler problem.

It does not hand texture truth over to Codex image generation.
It does not retreat from the self-reliant thesis.
It makes Lathe stronger by letting Lathe define:
- what surface outputs are needed,
- where they belong,
- how they are validated,
- how they are repaired,
- and how they are packaged.

Codex image generation becomes an optional coprocessor for 2D map authoring inside that governed system.

That is consistent with the product direction laid out in the Concept Showcase, Product Vision, and PRD: Lathe must remain the programming language and compiler for production 3D assets, where the certified build artifact is the true product. fileciteturn23file2 fileciteturn23file3 fileciteturn23file4 fileciteturn23file5
