# Imagination-to-Life Capstone — Skyborne Village v1

Date: 2026-05-14
Status: Next northstar — the proof-of-product goal after substrate completion
Placement in sequence: **after** the Foundry Lane A-J + Phase 3-5 closure (2026-05-14) and the @lathe/three viewer MVP (2026-05-13); **before** any further substrate work
Related documents:

- `docs/asset-quality/lathe-implementation-northstar.md`
- `docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md`
- `docs/asset-quality/foundry-completion-report-2026-05-13.md`
- `docs/asset-quality/foundry-completion-report-addendum-2026-05-14.md`
- `docs/product/three-lth-lathe-web-studio-v1-product-path.md`
- `North Star/lathe-floating-fantasy-world-northstar.md`
- `docs/research/newresearch.md`

---

## 0. Why this document exists

Today, every Lane A-J priority task + every Phase 3-5 deliverable + every Capability Parity Matrix row in `lathe-implementation-northstar.md` §10–§13 is landed at the typed-module level. The capability matrix records 104 operations across 11 op families; 83 are `supported`, 20 are `partial` with structured `fallback_reason` tokens naming the external backend that closes the gap, and 1 is `not_started`.

The substrate is not missing anything important.

What's missing is **the undeniable proof** — a single artifact that demonstrates the entire stack (Wonder → Lathe Forge → Foundry → kernel → @lathe/three → engine handoff) works together as a product. Until that exists, Lathe's thesis lives in modules, not in a thing a non-programmer can touch.

This document defines that proof.

---

## 1. The capstone goal

> One non-programmer types
>
> `"build me a small floating fantasy village at sunset with a waterfall, a rope bridge, three cottages, and a hero inn"`
>
> and Lathe produces a playable `.lthworld` they can walk around in,
> with real collision, real nav, real engine import evidence, real
> signed reproducibility, and a visible-quality certificate that
> survived autonomous Wonder critique.

This is the northstar's Phase 5 playable scene (`lathe-floating-fantasy-world-northstar.md` §5.5) + the Foundry masterplan's Forge layer (§5.2) + the Wonder Dream layer (§5.3) + the floating-fantasy reference image (§4.2) collapsed into one shippable demo.

It is the first time Lathe's full thesis lives in one artifact, exercised by every substrate piece landed across the last 30+ waves.

---

## 2. Strategic thesis

Skyborne Village v1 is not about adding more code. It is about **assembling everything into a single playable demonstration that proves the entire stack works as a product**.

Three things make this the right level of ambition right now:

1. **Substrate is ready.** The Foundry, the @lathe/three viewer, the capability matrix, the seven Golden Assets, the style packs, the engine adapters, the signed package envelope, and the repair loop with rollback are all wired. Skyborne Village exercises every one.

2. **Everything else is incrementalism.** "Add another lane" or "land another phase" is more module construction. Skyborne Village is the first proof that the modules compose into a product non-programmers can experience.

3. **It forces every remaining gap to close.** The 20 `partial` records in the capability matrix have to either flip to `supported` (because Skyborne Village exercised them end-to-end) or stay `partial` with a recorded reason that doesn't block the demo. That's how we know the substrate is done.

The Foundry masterplan said:

```text
Quality before intent.
Foundry before Forge.
Builder before Dream.
Real evidence before public magic.
```

Skyborne Village is the moment Foundry meets Forge meets Dream — with real evidence and no public magic faked along the way.

---

## 3. Acceptance criteria — undeniable in 30 seconds

A reviewer, given no prior context, must be able to:

### 3.1 One-line build

Run:

```powershell
python -m lathe.cli wonder build "small floating fantasy village at sunset with waterfall, rope bridge, three cottages, hero inn" --out skyborne_village.lthworld
```

The command returns `certified: True` and a path to the world archive in under 5 minutes wall-clock on the dev machine. The output is **deterministic** for the prompt + seed — re-running produces the same archive byte-for-byte (modulo timestamps in the manifest).

### 3.2 Playable

Drag `skyborne_village.lthworld` into `@lathe/three`'s Phase 5 Playability mode → a third-person view loads in a browser tab. Click-and-WASD around the island:

- Path connects to the ElderHouse door, the rope bridge, and the waterfall overlook.
- Cliff edges are flagged hazards; player cannot walk off the island.
- The minimap renders the village layout from the world graph.
- Quest marker glows at ElderHouse.
- Player spawns at the village square.
- Lanterns along the path emit warm light (vertex-color or emissive).
- Crystals at the cliff are interactable (collectible_crystal tag).

### 3.3 Inspectable

The side panel shows:

- 22 assets total (1 island + 3 cottages + 1 elder house + 12 pines + 3 crystal clusters + 1 rope bridge + 1 waterfall ribbon + ~5 stone path segments + ~6 lanterns + ~4 fence segments).
- All assets share `style_pack_id = lowpoly_fantasy_sunset_crystal_v1`.
- World certificate: **Level 6 (Scene Ready)** with zero visual-quality findings.
- Signed envelope verifies; `signature.json` valid against the asset manifest hashes.
- At least one engine has captured import evidence (Roblox Studio import log path, or Unity FBX import success path, or USD validation report).

### 3.4 Variation

Re-run with `--seed 13` and the same prompt → a visibly different but stylistically coherent village. Run 10 seeds → 10 distinct dioramas that all certify Level 6 and pass the `validator.style_stack_compatibility` check.

### 3.5 Wonder-critique trace

The world's `evidence.json` records:

- N canonical-view renders per asset (front, three-quarter, hero).
- Vision-model critique JSON per asset (deterministic fingerprint, not raw vision-model probabilities).
- Per-asset repair rounds executed via `repair_loop_gate` + `repair_rollback`.
- Per-round metric delta (silhouette / facet / material-zone / runtime-readiness).
- At least one asset has a visible Level 4 → Level 5 climb attributable to a Wonder repair round.

### 3.6 Hero render

A `hero_sunset.png` at the package root. Composed procedurally by Forge + camera-locked by Wonder + visible-quality-certified. It should look recognizably like the `ChatGPT Image May 6, 2026, 12_54_03 PM.png` reference in `North Star/`.

### 3.7 Engine handoff

`engine_import_evidence/` directory contains at least one of:

- `roblox_import_evidence.json` with `status: "imported"`, asset count, MeshPart count, mesh.glb hash matched.
- `unity_fbx_import_evidence.json` with `status: "imported"`, prefab count, material assignment count.
- `usd_validation_evidence.json` with `usdchecker` output + manifold + watertight checks.
- `gltf_validation_evidence.json` with KhronosGroup glTF-Validator output.

The word `"proxy"` may appear in evidence, but only honestly tagged. No claim of import success without a corresponding import-tool log.

---

## 4. Why this is the right level of ambition

It is not "ship the next module." It is the first time Lathe's full thesis lives in one artifact a non-programmer can touch. Everything that has been hard for two years — visible quality, kernel performance, repair loops, scene composition, engine handoff, the Wonder ↔ Lathe boundary — must work simultaneously for this to ship. Anything less is incrementalism.

It reuses every substrate landed in the last weeks:

| Substrate | Role in Skyborne Village |
|---|---|
| Foundry generators (`crystal_cluster`, `pine_tree`, `cottage`, `lantern_post`, `rope_bridge`, `stone_path_segment`, `floating_island_small`) | Asset kit; one of each species per role-slot in the village. |
| `kernel_ops.minkowski` | Crystal cluster bounding proxies + cliff-edge offset shrink-wrap. |
| `kernel_ops.partial_revolve` | Waterfall ribbon, lantern housing sections. |
| `kernel_ops.deformers.{bend,twist,taper}` | Rope-bridge sag, foliage stack natural variation. |
| `kernel_ops.helical_sweep` | Lantern post wrap detail. |
| `kernel_ops.involute_gear` | (Optional) waterworks accent on hero inn. |
| `kernel_ops.nurbs_curve` | Smooth path spline + waterfall arc. |
| `kernel_ops.half_edge_bevel` | Hero-cottage edge treatment, lantern housing chunky bevels. |
| `kernel_ops.tessellation_policy` | `low_poly_fantasy` profile applied across the whole village for consistency. |
| `oklab` | Sunset palette ramp (peach → lavender → violet → indigo) generated in OKLab for perceptually-smooth gradients. |
| `materialx_lowering` | Per-asset MaterialX document + colorspace sidecars; engine adapters consume. |
| `constrained_packing` | One trim-sheet shared across cottage walls / rope bridge planks; per-part importance weights ensure hero inn gets the most texel density. |
| `repair_rollback` | Every Wonder repair round protected from regressing the certificate. |
| `distribution.distribute_along_path` | Lantern placement along the main path; stone slab placement; fence post placement at cliff edges. |
| `distribution.distribute_arc` | Crystal cluster radial distribution. |
| `authoring.stdlib_registry` | `lowpoly_fantasy@1.0.0` kit looked up by Forge for asset selection. |
| `authoring.director_vocabulary` | `stylized_low_poly_fantasy` + `faceted_cliffside` + `sunset_crystal_palette` terms resolve to executable compositions. |
| `authoring.field_attrs` | Mask expressions for grass exclusion zones, hazard-edge tagging, scatter density falloffs. |
| `authoring.cga_assembly` | Village block layout (split island top → village_zone / overlook / waterfall_zone → cottage_pad × 3 + elder_pad × 1). |
| `authoring.reference_extraction` | The northstar reference PNG drives palette + composition signature (stub mode acceptable for v1; vision pipeline later). |
| `validators.silhouette_multi_angle` | Per-asset + per-scene silhouette readability gate. |
| `validators.frequency_energy` | Style-band compliance (LowPolyFantasy expects low+mid band energy). |
| `validators.topology_class_compliance` | Per-family topology rule sets enforce per-asset budgets. |
| `validators.pbr_chart` | Materials respect dielectric/metalness ranges; emissives tagged. |
| `validators.style_stack_compatibility` | Forge refuses to compose a non-Band-A asset into the village. |
| `domain.vegetation` | TreeStructure → AlpinePine generator parameter seed. |
| `domain.terrain` | Island top heightfield + thermal erosion + grass/cliff band zones. |
| `domain.wfc` | Path tile adjacency solver (optional v1; CGA suffices). |
| `domain.scatter` | Grass / mushroom / pebble surface scatter on the island top. |
| `domain.trim_sheets` | Cottage wall + bridge plank + lantern housing share one trim sheet. |
| `domain.sdf_extraction` | (Future) cliff-side facet refinement; v1 uses faceted prisms only. |
| `rig.canonical_topology.crystal_pulse_template` | Crystal pulse morph slot for emissive animation in @lathe/three. |
| `rig.animation_compat.build_idle_breathing_clip` | (Optional) ambient animation on lanterns / waterfall. |
| `runtime.usd_generative` | World stage with one GenerativeProcedural per asset family. |
| `runtime.live_overrides` | Editor sliders in `@lathe/three` re-bake one asset without re-baking the world. |
| `runtime.signed_package` | World envelope: HMAC over every `.lthpkg` + the `world_graph.json`. |
| `package.lthpkg` + `package.lthpkg_signed` | Per-asset package output; world envelope wraps them. |
| `strict_geometry_mode` | Enabled for hero inn + island to refuse any silent boolean fallback. |
| `mesh_levelset_repair` | Available as last-resort fallback for island cliff repair; degraded status surfaced honestly. |
| `wonder.wonder_cli.plan_wonder_build` | Existing planner extended to accept the natural-language prompt path. |
| `@lathe/three` loader + viewer | Phase 3 + 4 + 5 modes light up because the world archive carries the right sidecars. |

If Skyborne Village ships, every one of the above has been exercised end-to-end at least once.

---

## 5. The seven substrate gaps Skyborne Village forces to close

Each of the following is currently a `partial` or scaffold-only in the capability matrix or in the broader stack. Skyborne Village does not ship without all seven actually working.

### 5.1 Boolean kernel performance — Foundry F2 follow-on

**Current state.** The procedural-synthesizer 52-op program for `industrial_crate.lth` hangs in the shape stage's boolean compile for >30 minutes. Sprint 0 closed at the legacy-scaffold path via the `synthesizer_disabled` runtime flag. The 50+ op kernel-perf gap is carved off to Foundry F2.

**What Skyborne Village needs.** A small island + cottages + rope bridge + waterfall + path network is realistically 200+ ops per `.lthpkg` plus another ~80 ops for world-scale composition. The kernel must complete a 200-op program in seconds, not minutes.

**How to close it.** Implement the variadic-cluster batched boolean compile per `newresearch.md` §1.4:

```text
1. Build the FeatureDAG (already implemented in Wave 12 — lathe/feature_dag.py).
2. Spatial broadphase: cluster ops by bounding-box overlap (already implemented in Wave 12 — spatial cluster broadphase).
3. Per-cluster, build ONE libigl-style arrangement, classify by winding number, extract once.
4. Defer bevels — never bevel primitive edges before booleans.
5. Carry provenance through the arrangement: every output face records source_part_id, material_zone, seam_class.
6. Cache primitive tessellations and analytic descriptors so cylinders/cones don't regenerate per op.
```

The `op_graph_plan.spatial_clusters` + `boolean_clusters` records that just landed in the .lthpkg `operations.json` sidecar are the entry points. The shape backend must consume them instead of executing serial binary booleans.

**Acceptance.** `python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out dist` completes in < 30 seconds via the procedural-synthesizer path (currently 30+ minute hang).

### 5.2 Lathe Forge — the missing world-composition layer

**Current state.** Scene-composition pieces exist scattered across `lathe/scene/scene_compose.py`, `lathe/asset_foundry/authoring/cga_assembly.py`, `lathe/asset_foundry/domain/wfc.py`, `lathe/asset_foundry/domain/scatter.py`, and `lathe/wonder/`. None of them compose a multi-asset world end-to-end.

**What Skyborne Village needs.** A coherent `lathe.forge` module that:

```text
1. Accepts a KitGraph + a prompt-derived NL intent + a world seed.
2. Selects asset archetypes from the stdlib_registry (e.g. lowpoly_fantasy@1.0.0).
3. Resolves layout via CGA-style splits (island top -> zones) + WFC where modular + constraint solver where free-form.
4. Builds a path graph network connecting role-anchors (cottage doors, overlook, bridge endpoints, waterfall source).
5. Propagates style across asset placements (every asset declares lowpoly_fantasy_sunset_crystal_v1).
6. Extracts walkable surface polygons across all asset walkable_zones.
7. Tags hazard zones (cliff edges, waterfall volume, drop-off perimeter).
8. Emits a typed WorldGraph dataclass + world_graph.json sidecar.
9. Emits a traversal_evidence.json with the nav polygon set + collision compound + player spawn + quest markers.
```

**Acceptance.** `forge.compose_world(kit, intent, seed)` returns a `WorldComposition` record with N assets + path graph + nav extraction + hazard zones in pure-Python deterministic time.

### 5.3 Wonder vision-critique closing the visible-quality gap

**Current state.** The `lathe.asset_quality.vision_critique` module exists at the contract level. The repair loop (`repair_loop_gate` + `repair_rollback` + `repair_executor`) exists and is testable with mocks. The actual vision-model integration that drives the critique is not wired.

**What Skyborne Village needs.** Each asset, after first build, goes through:

```text
1. Render N canonical views (front, side, three-quarter, hero, top).
2. Run a vision-model critique that returns a structured WonderCritique JSON:
   - silhouette_readability_observed: float
   - material_zone_clarity_observed: float
   - debug_material_appearance_observed: float
   - blockout_appearance_observed: float
   - patches_proposed: list[SemanticPatch]
3. Convert each SemanticPatch into a repair action via the existing repair_loop_gate.
4. Drive a rebuild via run_repair_with_rollback so any worsening is undone.
5. Re-render + re-critique until convergence or budget exhaustion.
6. Persist the round history in repair-history.json (already a sidecar slot).
```

The vision model can be a small local CLIP-style scorer + a few rule-based heuristics; it does **not** require a frontier LLM for v1. What it requires is **honesty**: the critique JSON must come from real rendered pixels, not invented from metadata.

**Acceptance.** At least one Skyborne Village asset (suggest: the hero ElderHouse) climbs from initial L4 to final L5+ via a Wonder repair round, with the round recorded in `repair-history.json` and the before/after PNGs in `previews/repair_rounds/`.

### 5.4 `.lthworld` package format

**Current state.** The `.lthpkg` format is shipped for single assets. Multi-asset world packaging does not exist.

**What Skyborne Village needs.** A `.lthworld` archive (zip on disk; directory in dev) containing:

```text
skyborne_village.lthworld/
  world_manifest.json          (kit_id, prompt, world_seed, asset_count, asset_id_list, hashes, created_utc)
  world_graph.json             (WorldComposition serialized)
  traversal_evidence.json      (nav polygon set + collision compound + spawn/quest anchors)
  visual_quality_gate.json     (per-asset + per-scene visual-quality certificate)
  signature.json               (HMAC envelope over every contained file)
  repro_evidence.json          (Foundry version + dep versions + host)
  hero_sunset.png              (composed hero render)
  minimap.png                  (minimap-friendly top-down render)
  engine_import_evidence/      (per-engine import logs)
  assets/
    floating_island_small_a.lthpkg/
    elder_house_a.lthpkg/
    cottage_a.lthpkg/
    cottage_b.lthpkg/
    cottage_c.lthpkg/
    alpine_pine_001.lthpkg/  ...
    crystal_cluster_a.lthpkg/  ...
    rope_bridge_a.lthpkg/
    waterfall_ribbon_a.lthpkg/
    lantern_post_001.lthpkg/  ...
    stone_path_segment_001.lthpkg/  ...
```

The signature envelope extends the existing `runtime.signed_package` HMAC contract: one envelope hashes every `.lthpkg`'s manifest hash + every world-level sidecar.

**Acceptance.** `Foundry.write_lthworld(...)` emits the archive; `verify_lthworld(...)` returns `(valid, reason)`; tampering with any contained file breaks the signature.

### 5.5 @lathe/three Phase 3-5 viewer modes

**Current state.** Phase 1 Single Asset Inspector is shipped. The viewer's `index.html` has the Evidence panel + repair-request export (added in the latest pass). Phase 3-5 modes are not implemented.

**What Skyborne Village needs.**

```text
Phase 3 — Micro-Scene Inspector
  - Load a .lthworld instead of a single .lthpkg.
  - Render all assets in their world-graph placements.
  - Display path splines as overlay lines.
  - Display object anchors as gizmos.
  - Flag floating / intersecting / mis-scaled props in the diagnostics panel.

Phase 4 — Hero Diorama Review
  - Wide hero camera at the world's vista_point socket.
  - Sunset lighting rig (warm directional + cool ambient + sky gradient from oklab).
  - Composition role overlay (foreground / midground / background tagging).
  - Before/after comparison when a repair round runs.
  - Export hero PNG to the world archive root.

Phase 5 — Playability Overlay
  - Third-person camera + WASD controller + jump.
  - Collision compound from traversal_evidence.json.
  - Walkable polygon overlay toggle (debug viz).
  - Quest marker glow.
  - Spawn / NPC anchor gizmos.
  - Minimap polygon render.
  - HUD: certificate level + visual quality gate status + signed envelope status.
```

**Acceptance.** Drag `skyborne_village.lthworld` into the viewer; all three modes light up; "Playability" mode lets you walk around the village.

### 5.6 Engine import certification

**Current state.** Engine adapter manifests are emitted (Roblox, Unity, Unreal, USD, glTF). Engine import has never been driven; the signed envelope verifies the file hashes but not engine ingestion.

**What Skyborne Village needs.** At least **one** engine actually imports the world:

```text
Option A — Roblox Studio (preferred for prototype phase):
  1. Roblox-Studio CLI mode imports skyborne_village.lthworld via the Lathe plugin.
  2. Captures the Studio log to roblox_import_evidence.json:
     - imported_part_count
     - imported_mesh_part_count
     - material_assignment_count
     - studio_log_excerpt
     - rbxl_path_relative
  3. The signed envelope verifies after import (read-only inspection mode).

Option B — Unity headless:
  1. Unity in batch mode imports the world's FBX/glTF exports.
  2. Captures unity_fbx_import_evidence.json.

Option C — USD validation (lowest bar):
  1. `usdchecker` validates the generated USD stage.
  2. Captures usd_validation_evidence.json with watertight + manifold + primvar checks.
```

**Acceptance.** Skyborne Village ships with at least one of A/B/C; the rest are tagged `not_verified` honestly.

### 5.7 Natural-language intent → kit selection → Forge composition

**Current state.** `lathe.wonder.wonder_cli.plan_wonder_build` accepts a `WonderRequest` with explicit `asset_classes: dict[str, int]`. It does not accept a free-text prompt.

**What Skyborne Village needs.** A `parse_prompt_to_wonder_request(prompt: str) -> WonderRequest` function that:

```text
1. Tokenizes the prompt with a small deterministic parser
   (not a frontier LLM — keep it dependency-free for v1).
2. Identifies the world archetype: village / vista / outpost / temple
   from a deterministic keyword table.
3. Counts mentioned asset classes:
   "three cottages" -> {cottage: 3}
   "hero inn" -> {elder_house: 1}
   "a waterfall" -> {waterfall_ribbon: 1}
   "a rope bridge" -> {rope_bridge: 1}
   Add defaults: trees, crystals, lanterns, path, island per archetype.
4. Picks style pack from style keywords:
   "sunset" + "fantasy" -> lowpoly_fantasy_sunset_crystal_v1.
5. Selects director vocabulary terms:
   "fantasy" -> stylized_low_poly_fantasy
   "sunset" -> sunset_crystal_palette
   "waterfall" implies "faceted_cliffside" for the island.
6. Returns a WonderRequest pre-populated with all asset classes + style pack + director terms.
```

For v1 this is **deterministic keyword matching**, not a model. The keyword table lives in `lathe/wonder/prompt_keywords.py`. A future v2 adds LLM-based prompt parsing as an optional path, retaining the keyword path as the canonical deterministic fallback.

**Acceptance.** `parse_prompt_to_wonder_request("small floating fantasy village at sunset with waterfall, rope bridge, three cottages, hero inn")` returns a typed `WonderRequest` with the right kit, the right counts, the right style pack, and the right director terms.

---

## 6. Phase rollout

Skyborne Village ships in five phases. Each phase ends with a concrete artifact a reviewer can inspect.

### Phase SV-0 — Forge composition skeleton

Time horizon: 1 week

Deliverables:

- `lathe/forge/__init__.py` package.
- `lathe/forge/world_graph.py`: typed `WorldComposition` + `WorldAsset` + `PathGraphEdge` + `HazardZone` + `QuestAnchor` records.
- `lathe/forge/compose.py`: `compose_world(kit, intent, seed)` pure function.
- `lathe/forge/path_graph.py`: deterministic path network builder using `kernel_ops.nurbs_curve` for smooth paths + `domain.wfc` for tile adjacency where needed.
- `lathe/forge/traversal_extraction.py`: walkable polygon extraction + hazard tagging from asset metadata.

Acceptance: `forge.compose_world` returns a typed record; py_compile-clean; module-import smoke succeeds.

### Phase SV-1 — `.lthworld` writer + signed envelope

Time horizon: 1 week

Deliverables:

- `lathe/asset_foundry/world_writer.py`: `write_lthworld(composition, out_dir)`.
- World manifest + signed envelope extension of `runtime.signed_package`.
- `verify_lthworld(archive_path)` helper.

Acceptance: empty-island fixture writes a valid `.lthworld` directory with all sidecars present; signature verifies; tampering breaks it.

### Phase SV-2 — Wonder prompt parser + plan_wonder_build extension

Time horizon: 3-5 days

Deliverables:

- `lathe/wonder/prompt_keywords.py`: deterministic keyword tables.
- `lathe/wonder/prompt_parser.py`: `parse_prompt_to_wonder_request`.
- `wonder build "..."` CLI subcommand: prompt → request → Forge.compose_world → write_lthworld.

Acceptance: the one-line build command from §3.1 runs end-to-end and emits a `.lthworld` archive (assets may still be empty placeholders at this stage).

### Phase SV-3 — Real assets + variation per seed

Time horizon: 2 weeks

Deliverables:

- All 7 Foundry generators output proper `.lthpkg`s as world members.
- Variation: 10 seeds produce 10 visibly-distinct compositions that all certify Level 5+.
- `validators.style_stack_compatibility` enforced across the world.
- Hero sunset PNG composed via Wonder's render rig.

Acceptance: 10-seed sweep all pass; hero PNG visibly recognizable as the northstar reference style.

### Phase SV-4 — Boolean kernel perf + Wonder vision critique

Time horizon: 3-4 weeks

Deliverables:

- Variadic batched boolean compile per `newresearch.md` §1.4 wired into the shape backend.
- The procedural synthesizer's 200-op programs complete in seconds.
- Real vision critique driving repair rounds for the hero inn.
- `repair-history.json` records the Level climb.

Acceptance: at least one Skyborne Village asset climbs L4 → L5 via a recorded Wonder round; world build completes under 5 minutes wall-clock.

### Phase SV-5 — Engine import certification + viewer Phase 5

Time horizon: 2 weeks

Deliverables:

- At least one engine (preferred: Roblox Studio) drives a headless import of the world.
- `engine_import_evidence/` directory captured.
- `@lathe/three` Phase 5 Playability mode: walkable controller + collision + minimap.

Acceptance: drag `.lthworld` → walk around → engine import evidence path exists. The 30-second reviewer test passes.

---

## 7. Capability matrix consequences

The 20 `partial` records currently in the matrix become a gate. After Skyborne Village ships, each must either:

- **Flip to `supported`** because the demo exercised it end-to-end and produced the required evidence, or
- **Stay `partial`** with a structured note that it was specifically not exercised by Skyborne Village (e.g. SDF extraction not used because cliff faceting is geometric).

Currently `partial` and expected to flip to `supported`:

```text
op.bevel                       (half-edge bevel wired)
op.chamfer                     (same)
solid.swept_profile            (waterfall ribbon, lantern arm)
solid.lofted_solid             (path stone transitions)
op.distribute                  (along_path lantern placement)
op.shell                       (cottage wall thickness)
op.weld_seam                   (rope bridge plank joins)
op.chip_edges                  (stone path wear)
authoring.reference_extraction (palette ref drives sunset palette)
domain.opensubdiv_refinement   (hero inn smoothing pass)
runtime.collision_proxy        (full traversal evidence)
runtime.nav_contribution       (walkable polygon extraction)
runtime.usd_generative_stage   (USD validation evidence)
op.half_edge_bevel             (cottage edge treatment)
kernel.brep_ir                 (optional — only if hero inn uses CAD-style filleting)
kernel.mesh_to_levelset_repair (only invoked if a cliff repair fails; degraded status surfaced)
op.minkowski                   (cliff offset / shrink-wrap)
```

Currently `partial` and likely to stay `partial`:

```text
domain.sdf_extraction          (no organic asset in v1 demo)
```

After Skyborne Village ships, capability matrix should be **≥95% supported**, with ≤5 records still `partial` (each with a named reason).

---

## 8. The "Rule of Truth" applied to Skyborne Village

Per `lathe-implementation-northstar.md` §4 + AGENTS.md, every claim about the demo must use the canonical vocabulary:

| Claim about Skyborne Village | Real only when |
|---|---|
| `village is playable` | Player controller can walk every walkable polygon; collision blocks hazard edges; player_spawn + at least one quest marker exist in `traversal_evidence.json`. |
| `world is signed` | `signature.json` verifies against every contained file's hash via the existing HMAC-SHA256 envelope. |
| `world certifies Level 6 (Scene Ready)` | The world certificate's `achieved_level == 6` with overall_score ≥ 0.78 across the 12-metric scorecard, AND every asset's individual certificate is ≥ L5. |
| `Wonder critique improved the asset` | `repair-history.json` records at least one round where post-score > pre-score AND a before/after PNG pair exists in `previews/repair_rounds/`. |
| `engine import works` | At least one `engine_import_evidence/*.json` exists with a `status: "imported"` field and a tool-log excerpt. Anything less is `not_verified`. |
| `deterministic` | Two runs with the same prompt + seed produce identical archive contents (modulo `created_utc`). The matrix must include this as a contract test. |
| `style is coherent` | `validator.style_stack_compatibility` returns `compatible: true` across all 22 assets. |

Forbidden:

- Claiming "Roblox-ready" without an `engine_import_evidence/roblox_import_evidence.json` file present.
- Claiming "production-ready" or "game-ready" without external engine validation.
- Faking the Wonder critique by reading the certificate metrics and writing a plausible-looking JSON.
- Hiding the kernel-perf gap by caching `.lthpkg`s from a prior build and re-using them silently.
- Using bloom / atmosphere / post-processing to disguise weak geometry in the hero render.

---

## 9. Decision filter applied per task

Before implementing any sub-task of Skyborne Village, the implementer answers:

1. What does this make visibly true about the village?
2. Which artifact (file path in the `.lthworld`) carries the evidence?
3. Which certificate metric or diagnostic judges it?
4. If the substrate doesn't exist yet, does it fall under one of the seven gaps in §5?
5. Does it preserve `.lth` compatibility + `lathe.shape.intent_mesh_handoff_v1`?
6. If it falls back, does the evidence surface attempted vs actual?
7. What claim about Skyborne Village remains explicitly `not_verified` after this task ships?

If any answer is weak, the task is not ready.

---

## 10. Non-goals for Skyborne Village v1

Skyborne Village v1 will NOT:

- Generate worlds from prompts in any language other than the keyword table (no LLM dependency).
- Render in any rendering pipeline other than `@lathe/three` (no Blender headless render).
- Ship a deployed editor/playground UI (the viewer is a developer tool, not a public app).
- Support arbitrary world archetypes (only "village" for v1; "vista", "outpost", "temple" come later).
- Support arbitrary style packs (only `lowpoly_fantasy_sunset_crystal_v1` for v1).
- Include character / NPC / creature assets (Phase 4 organic + animation is contract-only for v1).
- Stream world chunks (single-archive worlds only for v1).
- Re-export through every engine (one engine's import evidence is enough for v1; others are `not_verified`).
- Drive a frontier LLM critique (the vision critique is deterministic + small for v1).

These are explicitly out of scope so the demo can ship in 4-6 weeks rather than 4-6 months.

---

## 11. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Boolean kernel perf doesn't land in 3 weeks | High — blocks live builds | Cache `.lthpkg`s from offline builds; demo loads from cache; flag `kernel_perf: pending` in the world envelope so the demo isn't claimed faster than it is. |
| Vision critique fails to improve any asset | Medium — demoes a stagnant repair loop | Pre-author one Wonder-round scenario that clearly visibly improves (e.g. ElderHouse gets timber framing added); ship that as the canonical demo and label others "no improvement found this round". |
| `.lthworld` format becomes unstable | High — breaks viewer + signed envelope | Pin `LTHWORLD_VERSION = lathe.asset_foundry.lthworld_v1` early; treat every change as a coordinated rev. |
| Path graph generation produces unwalkable routes | Medium — gameplay breaks | Add a `walkability_certificate` validator that re-walks the nav polygons before signing. |
| Engine import fails for the chosen engine | Medium — no import evidence to ship | Fall back to USD validation via `usdchecker` (lowest bar, always available). |
| Prompt parser misinterprets the prompt | Low — wrong assets in the world | Add a `--dry-run` flag that prints the resolved WonderRequest before building; user reviews. |
| Variation produces visually-incoherent villages on some seeds | Medium — single-seed demo only | Hold seeds 0..9 as the canonical demo set; any seed that fails `style_stack_compatibility` is rejected at composition time. |
| Substrate has a latent bug that only Skyborne Village exposes | High — fix loop | Each Phase SV-N has a "smoke fixture": a 3-asset minimal scene that exercises the same code path; if smoke breaks, debug there before scaling. |

---

## 12. Allowed claims vocabulary (post-Skyborne)

The same six labels from the implementation northstar §15 apply. New vocabulary specific to Skyborne Village:

- `world_composed`: the WorldGraph is built; assets may or may not have real meshes yet.
- `world_built`: every asset has a real `mesh.glb` in its `.lthpkg`.
- `world_traversable`: walkable polygons + collision compound + player_spawn exist.
- `world_certified`: world certificate level ≥ target_level.
- `world_signed`: HMAC envelope verifies.
- `world_engine_imported`: at least one engine's import evidence present.

A reviewer at the playable demo bar requires all six labels simultaneously. Anything less is the typed substrate, not the playable demo.

---

## 13. Timeline

| Phase | Duration | End date target |
|---|---|---|
| SV-0 Forge skeleton | 1 week | 2026-05-21 |
| SV-1 `.lthworld` writer | 1 week | 2026-05-28 |
| SV-2 Wonder prompt parser | 3-5 days | 2026-06-02 |
| SV-3 Real assets + variation | 2 weeks | 2026-06-16 |
| SV-4 Kernel perf + vision critique | 3-4 weeks | 2026-07-14 |
| SV-5 Engine import + viewer Phase 5 | 2 weeks | 2026-07-28 |
| **First end-to-end demo** | — | **2026-07-28** |

Note: SV-4's kernel-perf work is the longest pole and the highest-risk item. If it slips past 3 weeks, the demo runs from a pre-cached asset directory while the perf work continues in parallel. SV-4's vision critique can ship before kernel-perf lands.

---

## 14. Strategic bottom line

Lathe spent the last two months building the substrate.

The substrate is good. The capability matrix records 104 operations across 11 op families. The Foundry, the @lathe/three viewer, the engine adapters, the signed envelopes, the repair loop with rollback, the seven Golden Asset generators, the LowPolyFantasy style pack, the WFC solver, the heightfield + erosion + scatter primitives — all of it exists.

But none of it is a thing a non-programmer has touched yet.

Skyborne Village v1 is the moment the substrate becomes a product. It is the moment somebody who has never read a line of Python types one sentence and gets back a walkable, exportable, certified, signed, repairable, deterministic, version-pinned, style-coherent, traversal-safe floating fantasy village. Until that ship, every claim about "imagination to life" is a roadmap.

Once it ships, Lathe is no longer a compiler scaffold under construction. It is the deterministic execution substrate underneath AI-native 3D creation — running.

The hard part is not the modules. The modules are done. The hard part is making the modules act like a product, together, on the kind of demand a real user would create.

Skyborne Village v1 is the proof.

---

## 15. What this document is not

This is not a feature spec. The seven gaps in §5 will each get their own detailed implementation doc as they kick off. This is the strategic frame that says **why** they kick off in that order and **what** the terminal acceptance is.

Implementers should read:

1. This document — for the strategic frame.
2. `lathe-implementation-northstar.md` §10–§16 — for the Lane discipline.
3. `lathe-frontier-asset-foundry-masterplan.md` — for the layered Foundry stack.
4. `North Star/lathe-floating-fantasy-world-northstar.md` — for the world quality bar.
5. `docs/research/newresearch.md` §1–§8 — for the kernel + composition architecture.
6. The Lane-specific module they're implementing (already landed in `lathe/asset_foundry/` and `lathe/forge/` when it lands).

Then start at Phase SV-0 §6.

---

## 16. Closing thought

```text
Quality before intent.
Foundry before Forge.
Builder before Dream.
Real evidence before public magic.
```

The substrate said Foundry first. The Foundry is done.

Skyborne Village is Forge meeting Dream — in one playable archive a non-programmer can walk around in.

That is the next ambitious thing.
