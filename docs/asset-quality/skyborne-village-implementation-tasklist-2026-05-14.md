# Skyborne Village Implementation Tasklist - 2026-05-14

Source goal:

- `docs/asset-quality/imagination-to-life-capstone-skyborne-village.md`

Purpose: convert the Skyborne Village capstone into a step-by-step implementation path from the current checkout to the full 100 percent acceptance bar: a deterministic, signed, inspectable, playable `.lthworld` archive that can be loaded in `@lathe/three` Phase 5 Playability mode and carries truthful engine/import/visual/repair evidence.

This is a build backlog, not a completion claim.

## 0. Current State Snapshot

Observed in the current checkout on 2026-05-14:

| Area | Current evidence | Status for Skyborne |
| --- | --- | --- |
| Capstone source doc | `docs/asset-quality/imagination-to-life-capstone-skyborne-village.md` exists and defines the terminal goal. | Source of truth for this tasklist. |
| Capability matrix | Probe reports 105 rows: 87 supported, 18 partial, 0 fallback, 0 unsupported, 0 not_started; claim levels: 6 typed_contract, 12 execution_partial, 87 artifact_real, 0 product_complete. | Capstone doc's 104/83/20/1 counts are stale and must be updated before final reporting. |
| Forge package | `lathe/forge/` does not exist. | Missing. SV-0 starts here. |
| Seven Golden generators | `lathe/asset_foundry/generators/` contains bridge, cottage, crystal_cluster, floating_island, lantern, pine_tree, and stone_path generators. | Present as generator specs; each still needs world-member package proof. |
| `.lthpkg` package writer | `lathe/asset_foundry/package_writer.py` exists and writes single-asset packages with repair-history support. | Useful base, but no `.lthworld` writer exists. |
| Signed package | `lathe/asset_foundry/runtime/signed_package.py` signs/verifies one `.lthpkg`. | Needs world-level envelope extension. |
| Wonder planner | `lathe/wonder/wonder_cli.py` has `WonderRequest`, `plan_wonder_build`, and `quick_wonder_request_from_prompt(prompt, asset_classes, ...)`. | Needs deterministic free-text prompt parser and real `wonder build` execution path. |
| Web viewer | `web/lathe-three` and `web/lathe-web-viewer` load one `.lthpkg`; browser proof exists for package evidence and blockers. | Needs `.lthworld`, micro-scene, hero diorama, and playability modes. |
| Current fixture evidence | Crate/door package-stage snapshots exist and are truthful `not_verified` for visual approval. | Useful evidence pattern, not Skyborne proof. |
| Repair evidence | `.tmp_repair_history_probe/.../repair-history.json` proves metadata/ShapeIR repair evidence. | Needs real rendered before/after Wonder critique round. |

## 1. Terminal Definition Of Done

Skyborne Village v1 is complete only when all of these are true:

1. One-line command works:
   `python -m lathe.cli wonder build "small floating fantasy village at sunset with waterfall, rope bridge, three cottages, hero inn" --out skyborne_village.lthworld`
2. Command completes under 5 minutes on the dev machine and emits `certified: True`.
3. Same prompt plus same seed produces deterministic archive contents, modulo allowed timestamp fields.
4. `.lthworld` contains world manifest, world graph, traversal evidence, visual quality gate, signature, repro evidence, hero render, minimap, engine import evidence, and per-asset `.lthpkg`s.
5. Viewer loads `.lthworld` and supports Phase 3 Micro-Scene Inspector, Phase 4 Hero Diorama Review, and Phase 5 Playability Overlay.
6. Player can spawn, walk the village path, reach ElderHouse, rope bridge, and waterfall overlook, and cannot walk off hazard edges.
7. Side panel shows the expected world inventory, style pack consistency, Level 6 world certificate, valid signature, and at least one real engine/import validation evidence file.
8. Seed variation works: seed 13 is visibly different, and a 10-seed sweep certifies Level 6 while preserving style compatibility.
9. Wonder critique trace records real rendered-pixel evidence, repair rounds, metric deltas, rollback protection, and at least one visible Level 4 to Level 5 asset improvement.
10. Hero render `hero_sunset.png` exists and is style-certified against the northstar reference.
11. At least one engine/import lane is real: Roblox, Unity, USD, or glTF validation evidence with tool log.
12. No evidence fakes success. Proxy, fallback, unsupported, blocked, and not_verified states remain visible.

## 2. Operating Rules

1. Preserve public `.lth` compatibility and `lathe.shape.intent_mesh_handoff_v1`.
2. Keep the keyword prompt parser deterministic for v1; no frontier LLM dependency.
3. Do not claim `world_built` unless every required asset has a real package member.
4. Do not claim `world_traversable` unless traversal evidence proves spawn, walkable polygons, collision, hazard blocking, and quest anchors.
5. Do not claim `world_engine_imported` without a real import or validator log.
6. Do not hide kernel-performance gaps behind silent cache reuse. If cached packages are used, record `kernel_perf: pending`.
7. Do not use hero lighting, bloom, or post-processing to disguise weak geometry.
8. Every phase must emit an inspectable artifact before moving to the next phase.

## 3. Phase SV-0 - Forge Composition Skeleton

Goal: create the missing `lathe.forge` layer and prove deterministic world graph composition without building meshes.

### SV-0.1 Create Forge Package Boundary

Target files:

- `lathe/forge/__init__.py`
- `lathe/forge/world_graph.py`
- `lathe/forge/compose.py`

Steps:

1. Add `LTH_FORGE_VERSION`.
2. Define frozen dataclasses:
   - `WorldComposition`
   - `WorldAsset`
   - `WorldAssetPlacement`
   - `PathGraphNode`
   - `PathGraphEdge`
   - `HazardZone`
   - `QuestAnchor`
   - `StyleContext`
3. Include stable ids, seed, style pack id, transform, asset role, asset family, socket references, and evidence status fields.
4. Serialize to JSON without timestamps.

Acceptance evidence:

- Bounded import probe imports `lathe.forge`.
- Synthetic composition serializes to `world_graph.json`.
- No mesh generation occurs.

### SV-0.2 Deterministic Kit-To-World Composition

Target files:

- `lathe/forge/compose.py`
- `lathe/asset_foundry/authoring/cga_assembly.py`
- `lathe/asset_foundry/authoring/stdlib_registry.py` if kit lookup needs a bridge

Steps:

1. Define `SkyborneIntent` or reuse Wonder request fields.
2. Select required roles:
   - 1 floating island
   - 3 cottages
   - 1 elder house or hero inn
   - 12 pines
   - 3 crystal clusters
   - 1 rope bridge
   - 1 waterfall ribbon
   - about 5 stone path segments
   - about 6 lanterns
   - about 4 fence segments
3. Use deterministic seeded placement with village square, cottage pads, elder pad, bridge endpoints, waterfall overlook, and cliff crystal zone.
4. Emit `world_asset_count`, role counts, and style propagation evidence.

Acceptance evidence:

- `compose_world(intent, seed=0)` returns the expected role counts.
- `compose_world(intent, seed=13)` changes placement while preserving roles and style pack.

### SV-0.3 Path Graph And Traversal Skeleton

Target files:

- `lathe/forge/path_graph.py`
- `lathe/forge/traversal_extraction.py`

Steps:

1. Build path graph nodes for village square, all cottage doors, ElderHouse door, rope bridge ends, and waterfall overlook.
2. Build deterministic path edges with route ids and world-space control points.
3. Mark player spawn at village square.
4. Mark quest anchor at ElderHouse.
5. Mark cliff-edge hazard zones from island perimeter.
6. Emit traversal skeleton with `nav_status="planned"` until geometry-backed polygons exist.

Acceptance evidence:

- `traversal_evidence.json` can be written with spawn, quest marker, path edges, and hazards.
- Claims remain `planned`, not `real`, until collision/nav extraction exists.

## 4. Phase SV-1 - `.lthworld` Writer And Signed Envelope

Goal: define and write the multi-asset world package format.

### SV-1.1 Define LTHWORLD Contract

Target files:

- `lathe/asset_foundry/world_writer.py`
- `lathe/asset_foundry/world_manifest.py` if split is cleaner
- `schema/lthworld.schema.json` if schema conventions require it

Steps:

1. Define `LTHWORLD_VERSION = "lathe.asset_foundry.lthworld_v1"`.
2. Define required layout:
   - `world_manifest.json`
   - `world_graph.json`
   - `traversal_evidence.json`
   - `visual_quality_gate.json`
   - `signature.json`
   - `repro_evidence.json`
   - `hero_sunset.png`
   - `minimap.png`
   - `engine_import_evidence/`
   - `assets/*.lthpkg/`
3. Implement `write_lthworld(composition, out_dir, assets=..., evidence=...)`.
4. Missing optional files must become sidecar statuses, not absent success.

Acceptance evidence:

- Empty-island fixture writes a valid `.lthworld` directory with sidecars.
- Missing hero render is recorded as `not_verified`.

### SV-1.2 Extend Signed Package To World Envelope

Target files:

- `lathe/asset_foundry/runtime/signed_package.py`
- `lathe/asset_foundry/world_writer.py`

Steps:

1. Add `SIGNED_WORLD_VERSION`.
2. Hash every world-level file and every nested `.lthpkg` manifest/sidecar.
3. Write `signature.json` at world root.
4. Add `verify_lthworld(world_dir_or_archive) -> tuple[bool, str]`.
5. Keep HMAC deterministic and timestamp-tolerant through explicit ignored fields.

Acceptance evidence:

- Signature verifies on a fixture world.
- Mutating any nested file returns a named drift reason.

### SV-1.3 Repro Evidence

Target files:

- `lathe/asset_foundry/world_writer.py`
- `lathe/asset_foundry/runtime/signed_package.py`

Steps:

1. Record Python version, Lathe versions, Foundry versions, capability matrix hash, generator ids, and dependency versions.
2. Record prompt, seed, kit id, and style pack id.
3. Record current capability matrix counts.

Acceptance evidence:

- `repro_evidence.json` is path-backed and parseable.

## 5. Phase SV-2 - Wonder Prompt Parser And CLI

Goal: turn the capstone sentence into a deterministic Wonder request and world build command.

### SV-2.1 Deterministic Prompt Keyword Tables

Target files:

- `lathe/wonder/prompt_keywords.py`
- `lathe/wonder/prompt_parser.py`

Steps:

1. Add archetype keywords: village, vista, outpost, temple.
2. Add asset count parsing:
   - "three cottages" -> `cottage: 3`
   - "hero inn" -> `elder_house: 1`
   - "waterfall" -> `waterfall_ribbon: 1`
   - "rope bridge" -> `rope_bridge: 1`
3. Add default village fill:
   - island, pines, crystals, lanterns, stone path, fences.
4. Add style keyword mapping:
   - "sunset" + "fantasy" -> `lowpoly_fantasy_sunset_crystal_v1`.
5. Add director terms:
   - `stylized_low_poly_fantasy`
   - `sunset_crystal_palette`
   - `faceted_cliffside`

Acceptance evidence:

- Parser returns a typed request with correct counts, style, kit, seed, and director terms for the exact capstone prompt.

### SV-2.2 Extend Wonder CLI

Target files:

- `lathe/wonder/wonder_cli.py`
- `lathe/cli/*` where Wonder subcommands are registered

Steps:

1. Add `wonder build "<prompt>" --out skyborne_village.lthworld`.
2. Add `--seed`, `--dry-run`, `--deterministic`, and `--evidence-only` flags.
3. Dry run prints resolved request, role counts, style, and planned world graph.
4. Build path calls prompt parser -> Forge composition -> world writer.

Acceptance evidence:

- Dry run for the capstone prompt emits the expected request without building assets.
- Build emits a skeleton `.lthworld` with planned evidence.

## 6. Phase SV-3 - Real World Member Packages

Goal: every world member becomes a real `.lthpkg` package, not only a planned role.

### SV-3.1 Package Each Golden Generator Species

Target files:

- `lathe/asset_foundry/generators/*.py`
- `lathe/asset_foundry/runtime_cook.py`
- `lathe/asset_foundry/package_writer.py`
- `lathe/asset_foundry/world_writer.py`

Steps:

1. Define a packaging function for each generator:
   - floating island
   - cottage
   - elder house or hero inn variant
   - alpine pine
   - violet crystal cluster
   - rope bridge
   - waterfall ribbon
   - lantern post
   - stone path segment
   - fence segment if needed
2. Ensure each member writes:
   - `manifest.json`
   - `semantic-index.json`
   - `materials.json`
   - `operations.json`
   - `diagnostics.json`
   - `evidence.json`
   - `runtime.json`
3. Use `render_mesh.status=real` only when a real artifact path exists.
4. Carry placement id and world asset id into package evidence.

Acceptance evidence:

- `assets/` contains every expected `.lthpkg` directory.
- Each package has a parseable manifest and runtime sidecar.

### SV-3.2 World Inventory Gate

Target files:

- `lathe/forge/world_graph.py`
- `lathe/asset_foundry/world_writer.py`

Steps:

1. Count world assets by role.
2. Enforce capstone inventory:
   - island: 1
   - cottages: 3
   - elder house: 1
   - pines: 12
   - crystals: 3
   - rope bridge: 1
   - waterfall: 1
   - stone path segments: approximately 5
   - lanterns: approximately 6
   - fence segments: approximately 4
3. Record exact count in `world_manifest.json`.

Acceptance evidence:

- Viewer side panel and `world_manifest.json` agree on asset count.

### SV-3.3 Style Compatibility Gate

Target files:

- `lathe/asset_foundry/validators/style_stack_compatibility.py` if absent
- `lathe/asset_foundry/world_writer.py`
- `lathe/asset_foundry/certificates.py`

Steps:

1. Verify every asset uses `lowpoly_fantasy_sunset_crystal_v1`.
2. Reject or mark incompatible assets before signing.
3. Emit per-asset style evidence and world-level compatibility summary.

Acceptance evidence:

- Style gate returns compatible for all members.
- Any off-style asset is blocked or clearly marked.

## 7. Phase SV-4 - Traversal, Collision, Nav, And Minimap

Goal: make the world traversable, not just composed.

### SV-4.1 Walkable Polygon Extraction

Target files:

- `lathe/forge/traversal_extraction.py`
- `lathe/asset_foundry/runtime_cook.py`

Steps:

1. Extract island top walkable polygon.
2. Extract rope bridge walkable strip.
3. Extract path segment polygons.
4. Merge into traversal graph.
5. Record `walkable_surface_status`.

Acceptance evidence:

- `traversal_evidence.json` includes walkable polygons and graph connectivity.

### SV-4.2 Collision Compound And Hazard Blocking

Target files:

- `lathe/forge/traversal_extraction.py`
- `lathe/asset_foundry/world_writer.py`

Steps:

1. Build compound collision from member collision specs.
2. Add cliff-edge hazard zones.
3. Add waterfall hazard volume.
4. Add player bounds blockers so the player cannot walk off the island.
5. Record attempted vs actual collision strategy.

Acceptance evidence:

- `traversal_evidence.json` shows collision compound, hazard zones, and spawn safety check.

### SV-4.3 Minimap

Target files:

- `lathe/forge/minimap.py`
- `lathe/asset_foundry/world_writer.py`

Steps:

1. Render or rasterize top-down layout from world graph.
2. Draw paths, cottage pads, elder house, bridge, waterfall, player spawn, and quest marker.
3. Write `minimap.png`.
4. Include minimap hash in signature envelope.

Acceptance evidence:

- `minimap.png` exists and world signature includes it.

## 8. Phase SV-5 - World Certificate And Render Evidence

Goal: prove scene-ready quality without fake visual approval.

### SV-5.1 World Certificate

Target files:

- `lathe/asset_foundry/world_certificate.py`
- `lathe/asset_foundry/world_writer.py`

Steps:

1. Aggregate per-asset certificate metrics.
2. Add scene metrics:
   - traversal readiness
   - style compatibility
   - path connectivity
   - role inventory completeness
   - signed package validity
   - import evidence status
   - visual finding count
3. Target Level 6 Scene Ready.
4. Require every asset certificate >= Level 5 before Level 6 world claim.

Acceptance evidence:

- `visual_quality_gate.json` records achieved level, target level, all metric values, findings, and repair recommendations.

### SV-5.2 Canonical Renders

Target files:

- `lathe/asset_quality/preview_evidence.py`
- `lathe/asset_foundry/world_writer.py`
- viewer render/export helpers if reused

Steps:

1. For each asset, render front, three-quarter, and hero views.
2. For the scene, render hero sunset and minimap.
3. Record renderer, camera, resolution, material mode, hash, and status.
4. Missing renders remain `not_verified`.

Acceptance evidence:

- `evidence.json` or world render evidence lists every required view and file status.

### SV-5.3 Hero Sunset Render

Target files:

- `lathe/forge/hero_render.py`
- `lathe/asset_foundry/world_writer.py`

Steps:

1. Place camera at vista point.
2. Apply sunset OKLab palette ramp.
3. Use warm directional and cool ambient light.
4. Export `hero_sunset.png`.
5. Record style-reference comparison status.

Acceptance evidence:

- `hero_sunset.png` exists at world root.
- It is included in signature and certificate evidence.

## 9. Phase SV-6 - Wonder Vision Critique And Repair

Goal: close the visible-quality loop using real rendered pixels and rollback.

### SV-6.1 Pixel-Based Critique Contract

Target files:

- `lathe/asset_quality/vision_critique.py`
- `lathe/wonder/critique.py`

Steps:

1. Define `WonderCritique` JSON:
   - observed silhouette readability
   - material-zone clarity
   - debug-material appearance
   - blockout appearance
   - proposed semantic patches
   - deterministic fingerprint
2. Inputs must be rendered image paths, not metadata-only certificates.
3. Deterministic local heuristic scorer is acceptable for v1.

Acceptance evidence:

- Critique fails if image paths are missing.
- Critique output includes image hashes.

### SV-6.2 Repair Loop Integration

Target files:

- `lathe/repair_loop.py`
- `lathe/asset_foundry/repair_rollback.py`
- `lathe/asset_foundry/package_writer.py`
- `lathe/asset_foundry/world_writer.py`

Steps:

1. Convert critique patches into existing repair actions.
2. Execute with rollback.
3. Re-render after each accepted repair.
4. Record per-round metric deltas.
5. Persist before/after PNGs under `previews/repair_rounds/`.

Acceptance evidence:

- At least one asset, preferably ElderHouse, records a Level 4 to Level 5 climb in `repair-history.json`.

### SV-6.3 World-Level Repair Summary

Target files:

- `lathe/asset_foundry/world_writer.py`

Steps:

1. Collect every member repair history.
2. Add world-level `wonder_critique_trace.json`.
3. Record accepted, rejected, rolled-back, and no-op repair rounds.

Acceptance evidence:

- `evidence.json` links per-asset repair histories and world summary.

## 10. Phase SV-7 - Kernel Performance And Capability Matrix Closure

Goal: remove the live-build blocker for 200-op worlds or label cache fallback honestly.

### SV-7.1 FeatureDAG To OpGraph Consumption

Target files:

- `lathe/feature_dag.py`
- `lathe/asset_foundry/op_graph.py`
- `lathe/geometry/kernel_program/*`
- shape backend handoff modules

Steps:

1. Feed `op_graph_plan.spatial_clusters` and `boolean_clusters` into the shape backend.
2. Stop executing serial binary booleans when a cluster plan exists.
3. Preserve source part, material zone, seam class, and fallback records.

Acceptance evidence:

- Synthetic 200-op program compiles without serial hang.

### SV-7.2 Batched Boolean Compiler

Target files:

- `lathe/geometry/kernel_program/boolean.py`
- `lathe/geometry/kernel_program/_semantic_handoff.py`

Steps:

1. Implement variadic cluster compile.
2. Cache primitive tessellations.
3. Defer bevels until after boolean extraction.
4. Emit provenance loss diagnostics.
5. Use arrangement backend when available; otherwise record current fallback mode.

Acceptance evidence:

- `industrial_crate` procedural-synth path completes under 30 seconds.
- Any unsupported backend is reported, not hidden.

### SV-7.3 Capability Matrix Consequences

Target files:

- `lathe/asset_foundry/capability_matrix.py`
- Skyborne evidence docs

Steps:

1. Re-run matrix probe after Skyborne.
2. Flip rows to supported only when Skyborne exercised them end-to-end.
3. Keep unexercised rows partial with named reasons.
4. Target >=95 percent supported, <=5 partial.

Acceptance evidence:

- Capability matrix report names which rows Skyborne exercised.

## 11. Phase SV-8 - Viewer Phase 3, 4, And 5

Goal: make `.lthworld` inspectable and playable in the browser.

### SV-8.1 World Loader In `@lathe/three`

Target files:

- `web/lathe-three/src/types.ts`
- `web/lathe-three/src/parsers.ts`
- `web/lathe-three/src/LatheWorldLoader.ts`
- `web/lathe-three/src/index.ts`

Steps:

1. Add `.lthworld` manifest types.
2. Fetch world sidecars.
3. Fetch nested asset manifests.
4. Apply world transforms.
5. Surface signature, traversal, visual gate, and engine evidence.

Acceptance evidence:

- Loader parses a skeleton `.lthworld` and returns world object metadata.

### SV-8.2 Micro-Scene Inspector

Target files:

- `web/lathe-web-viewer/src/main.ts`
- new viewer modules if split

Steps:

1. Add mode selector: Asset, Micro-Scene, Hero, Playability.
2. Render all world assets in their placements.
3. Overlay path splines, anchors, and hazards.
4. Diagnostics panel shows floating/intersection/mis-scale warnings.

Acceptance evidence:

- Browser loads a `.lthworld` and shows world graph overlays.

### SV-8.3 Hero Diorama Review

Target files:

- `web/lathe-web-viewer/src/main.ts`

Steps:

1. Add vista camera.
2. Add sunset lighting.
3. Add composition role overlay.
4. Add before/after repair comparison.
5. Export `hero_sunset.png`.

Acceptance evidence:

- Hero mode reproduces the world root `hero_sunset.png` or updates it with recorded evidence.

### SV-8.4 Playability Overlay

Target files:

- `web/lathe-web-viewer/src/main.ts`

Steps:

1. Add third-person camera and WASD movement.
2. Add collision from traversal evidence.
3. Add walkable overlay toggle.
4. Add minimap HUD.
5. Add quest marker glow and spawn marker.
6. Show certificate, signature, and import evidence status.

Acceptance evidence:

- Reviewer can walk to ElderHouse, bridge, and waterfall overlook without leaving walkable bounds.

## 12. Phase SV-9 - Engine Import Certification

Goal: make at least one engine handoff real.

### SV-9.1 Choose Primary Import Lane

Target files:

- `lathe/engine_manifests/*`
- `lathe/asset_foundry/world_writer.py`
- scripts under `scripts/` if needed

Steps:

1. Prefer Roblox Studio import if MCP/CLI is reliable.
2. If Roblox is blocked, choose USD validation or glTF validation.
3. Record skipped lanes as `not_verified`.

Acceptance evidence:

- Plan names the selected engine lane and exact tool command.

### SV-9.2 Capture Import Evidence

Target files:

- `lathe/asset_foundry/engine_import_evidence.py`
- `engine_import_evidence/*.json` in world package

Steps:

1. Run chosen import/validator.
2. Capture status, counts, hashes, and tool log excerpt.
3. Verify exported mesh hashes match world package hashes.
4. Write evidence JSON.

Acceptance evidence:

- At least one file reports `status: "imported"` or validator success with a real tool log.

## 13. Phase SV-10 - Determinism, Variation, And Seed Sweep

Goal: prove the product is stable and varied.

### SV-10.1 Same-Seed Determinism

Target files:

- `lathe/asset_foundry/world_writer.py`
- `lathe/forge/compose.py`
- determinism helpers if needed

Steps:

1. Build same prompt + seed twice.
2. Normalize allowed timestamp fields.
3. Compare archive content hashes.
4. Record determinism evidence.

Acceptance evidence:

- `determinism_evidence.json` reports same-seed match.

### SV-10.2 Ten-Seed Variation Sweep

Target files:

- `scripts/skyborne_seed_sweep.py`
- docs evidence ledger

Steps:

1. Build seeds 0 through 9, or canonical 10-seed set.
2. Record composition signature per seed.
3. Verify no two worlds have identical layout signatures.
4. Verify all certify Level 6.
5. Verify style compatibility across all worlds.

Acceptance evidence:

- `variation_evidence.json` lists 10 passing seeds and layout hashes.

## 14. Phase SV-11 - Final One-Line Product Proof

Goal: pass the 30-second reviewer test.

### SV-11.1 One-Line Build Gate

Command:

```powershell
python -m lathe.cli wonder build "small floating fantasy village at sunset with waterfall, rope bridge, three cottages, hero inn" --out skyborne_village.lthworld
```

Acceptance evidence:

- Exit code 0.
- Reports `certified: True`.
- Outputs `.lthworld` path.
- Completes under 5 minutes wall-clock.

### SV-11.2 Viewer Gate

Steps:

1. Start web viewer.
2. Load `skyborne_village.lthworld`.
3. Verify Micro-Scene, Hero, and Playability modes.
4. Walk to required anchors.
5. Capture screenshot and optional short clip.

Acceptance evidence:

- Browser screenshot paths exist.
- Playability checklist passes.

### SV-11.3 Archive Inspection Gate

Steps:

1. Parse every world sidecar.
2. Verify signature.
3. Verify asset inventory.
4. Verify render evidence.
5. Verify repair trace.
6. Verify engine import evidence.
7. Verify no forbidden claims exist without evidence.

Acceptance evidence:

- `skyborne_village_final_acceptance_report.md` records PASS for every capstone section 3 criterion.

## 15. Prompt-To-Artifact Checklist

| Capstone requirement | Required artifact | Producing phase | Completion signal |
| --- | --- | --- | --- |
| One-line build | `skyborne_village.lthworld` | SV-2, SV-11 | CLI exit 0, `certified: True`, <5 min |
| Determinism | `determinism_evidence.json` | SV-10 | Same-seed content hash match |
| Playability | `traversal_evidence.json`, viewer Playability mode | SV-4, SV-8 | Spawn, paths, hazard collision, quest marker pass |
| Inspectability | viewer side panel + world sidecars | SV-1, SV-8 | 22-ish asset inventory, style pack, certificate, signature, import evidence visible |
| Variation | `variation_evidence.json` | SV-10 | 10 seeds pass Level 6 and style compatibility |
| Wonder critique | `wonder_critique_trace.json`, per-asset `repair-history.json` | SV-6 | At least one L4 to L5 improvement with before/after PNGs |
| Hero render | `hero_sunset.png` | SV-5, SV-8 | File exists, hash signed, style gate passes |
| Engine handoff | `engine_import_evidence/*.json` | SV-9 | At least one real tool/import success log |
| Signed reproducibility | `signature.json`, `repro_evidence.json` | SV-1 | Verify helper returns ok; tamper fails |
| Capability closure | capability matrix report | SV-7 | >=95 percent supported or named nonblocking partials |

## 16. Final Completion Audit Procedure

Before claiming Skyborne Village v1 is 100 percent achieved:

1. Restate every capstone section 3 acceptance criterion.
2. Run the one-line build command.
3. Inspect the resulting `.lthworld` directory or archive.
4. Verify all required world root files exist.
5. Verify every nested `.lthpkg` manifest and sidecar parses.
6. Verify signature and tamper failure.
7. Verify deterministic rebuild evidence.
8. Verify 10-seed variation evidence.
9. Open viewer and complete the playability checklist.
10. Inspect Wonder critique and repair-history evidence.
11. Inspect engine import evidence.
12. Confirm capability matrix consequences.
13. Confirm forbidden claims are absent.
14. Write final acceptance report with PASS/WARN/FAIL per criterion.

Only after that report is fully PASS may the project claim:

```text
world_composed + world_built + world_traversable + world_certified + world_signed + world_engine_imported
```

Anything less is a partial milestone, not the capstone.
