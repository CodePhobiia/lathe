# Next-Version Roadmap — Research-Driven Ticket Backlog

Exhaustive ticketed expansion of every actionable recommendation across the three GPT/Codex research documents at the repo root:

- `cad-research-gpt.MD` — analysis of `earthtojake/text-to-cad`, argues for conversational geometry refs (`@lathe[...]`) + selector sidecars + ref-aware CLI + local viewer.
- `forgecad-research-gpt.MD` — analysis of `KoStard/ForgeCAD`, argues for browser studio + multi-backend geometry lanes + live parameters + parameter-robustness scans + constraint sketching + assemblies + LLM benchmarks.
- `research-findings-gpt.MD` — direct Lathe audit, argues for production-grade geometry kernel + real game-ready stages + certification reports as product surface + Godot-first engine handoff + standards packaging + provider harness.

**Coverage target:** 120% of the three source docs — every concrete recommendation becomes a ticket, plus obvious follow-ons the source docs imply but don't explicitly list.

## How this relates to existing backlogs

- `docs/plan_completeness.md` tracks remnants from the original 10 rating-based plans (44 tickets). **Read that first.**
- Per-wave `plans/WAVE{N}_BACKLOG.md` files are historical snapshots.
- **This doc** extends both with ~110 net-new tickets from the 3 research findings. Where a research recommendation is already tracked in `plan_completeness.md`, we cross-reference and don't duplicate.

## Epic map

| Epic | Title | Source docs | Ticket count | Priority | Rough effort |
|---|---|---|---|---|---|
| E1 | Semantic Reference System (`@lathe[...]`) | cad, forgecad | 16 | P1 | 3–5 weeks |
| E2 | Robust Geometry Core | research | 8 | **P0** | 3–6 weeks |
| E3 | Real Game-Ready Stages | research, cad | 12 | P0 | 3–5 weeks |
| E4 | Certification Reports + Studio + Viewer | all 3 | 10 | P1 | 2–4 weeks |
| E5 | Standards-Grade Packaging | research | 10 | P1 | 2–3 weeks |
| E6 | Engine Integration (Godot-first + others) | research, cad, forgecad | 7 | P1 | 2–3 weeks |
| E7 | Provider Proposal Harness | research, forgecad | 6 | P1 | 1–2 weeks |
| E8 | Parameter Robustness | forgecad | 5 | P2 | 1 week |
| E9 | v0.2 Language Extensions | forgecad | 8 | P2 | 6–10 weeks |
| E10 | Agent Workflow & Distribution | all 3 | 7 | P1 | 1–2 weeks |
| E11 | Example + Benchmark Corpus Discipline | forgecad | 7 | P1 | 1–2 weeks |
| E12 | SDF / Experimental Lane | forgecad | 4 | P3 | 2 weeks |
| E13 | DX & Tooling Polish | research, forgecad | 8 | P2 | 2–3 weeks |
| E14 | Security — cross-ref + 2 net-new | research | 2 | P1 | 3–5 days |
| E15 | Performance & Scalability | research | 5 | P2 | 1–2 weeks |
| E16 | Ops & GTM Cross-Ref (already in plan_completeness) | — | — | — | see OPS-*, GTM-* |

**Total net-new tickets: 115** across 13 substantive epics (E16 remains cross-reference only; ENG-1 removed — Godot AssetLib submission is tracked as `plan_completeness.md` GTM-5/BL-44 and not re-listed here).

---

## E1. Semantic Reference System (`@lathe[...]`)

**Source:** cad-research + forgecad (both independently converge on this as their #1 recommendation).

**Problem.** Lathe build outputs aren't addressable in conversation. Users and agents can't point to "this specific face" or "that socket" or "the diagnostic that fired on part X." Every follow-up edit becomes vague ("make the front panel wider") or screenshot-driven (lossy, non-reproducible). Selectors exist internally (parts, sockets, collisions) but have no public ref grammar or inspectable sidecar.

**Target outcome.** Every certified build emits a selector manifest. Every entity — asset, variant, stage, part, face, edge, vertex, socket, pivot, collision, LOD, material, diagnostic — has a stable `@lathe[...]` ref. Refs can be inspected, diff'd, copied from the viewer, and embedded in diagnostics + reports + agent prompts.

**Reference grammar (initial):**

```
@lathe[<build-or-source-path>]
@lathe[<build-or-source-path>#asset.<name>]
@lathe[<build-or-source-path>#variant.<name>]
@lathe[<build-or-source-path>#stage.<stage-name>]
@lathe[<build-or-source-path>#part.<part-id>]
@lathe[<build-or-source-path>#part.<part-id>.face<n>]
@lathe[<build-or-source-path>#part.<part-id>.edge<n>]
@lathe[<build-or-source-path>#part.<part-id>.vertex<n>]
@lathe[<build-or-source-path>#socket.<socket-id>]
@lathe[<build-or-source-path>#pivot.<pivot-id>]
@lathe[<build-or-source-path>#collision.<collision-id>]
@lathe[<build-or-source-path>#lod<n>.<part-id>]
@lathe[<build-or-source-path>#material.<material-id>]
@lathe[<build-or-source-path>#diagnostic.<diagnostic-id>]
```

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| REF-1 | `lathe/ref.py` — grammar + parser | `parse_ref(token) -> RefNode`; rejects invalid tokens; tests for valid/invalid/stale/path-traversal | M | — |
| REF-2 | Whole-build refs (`@lathe[<build>]`) | Resolves against existing `build_report.json` | S | REF-1 |
| REF-3 | Asset/variant/stage/diagnostic refs | Each resolves to concrete facts via existing bundles | S | REF-1 |
| REF-4 | Selector manifest JSON schema | `schema/lathe.selector.schema.json` (Draft 2020-12); schemaVersion=1 | S | — |
| REF-5 | Selector manifest writer | `lathe/selector_manifest.py` emits parts, sockets, collisions, materials, LODs, diagnostics after optimize stage; validates against schema | M | REF-4 |
| REF-6 | Face/edge/vertex extractor | `lathe/selector_extract.py` extracts from final mesh; emits compact `selectors.bin` (proxy geometry + relations) | L | REF-5 |
| REF-7 | Ref resolution with stale-ref warnings | Emits warning when source hash / build hash / selector-manifest hash / face-count changed | M | REF-5 |
| REF-8 | `lathe ref parse` CLI | Prints parsed ref as JSON | XS | REF-1 |
| REF-9 | `lathe ref inspect` CLI | Returns fact payload (bbox, normal, part, material, UV island, collision membership, adjacent refs, diagnostics) | M | REF-5, REF-6 |
| REF-10 | `lathe ref planes` CLI | Groups major planar surfaces by dominant normal | M | REF-6 |
| REF-11 | `lathe ref diff` CLI | Selector + geometry + diagnostic + cert delta between two builds | M | REF-5 |
| REF-12 | `lathe ref copy` CLI | Clipboard integration for copying ref tokens | XS | REF-1 |
| REF-13 | Diagnostic-to-ref linking | Every diagnostic carries optional `refs: [...]` + `suggestedCommands: [...]` | S | REF-5 |
| REF-14 | `docs/refs.md` public reference docs | Grammar + resolution rules + stale-ref behavior + examples | S | REF-1 |
| REF-15 | Viewer ref integration | URL state `?ref=`; click-to-copy buttons on every selectable entity (ties to E4 RPT-9, RPT-10) | M | REF-6 |
| REF-16 | Godot addon: manifest maps sockets via ref IDs | `Marker3D.name` embeds `@lathe[...]` selector ID for later inspection | S | REF-5, ENG-2 |

**Phased rollout within E1.** REF-1..5 + REF-8 + REF-14 land first (Phase 1 non-geometric refs). REF-6 + REF-9..12 land after Phase 1 proves stable (Phase 2 geometry extraction). REF-15 + REF-16 are downstream integrations (Phase 3).

---

## E2. Robust Geometry Core

**Source:** research-findings (P0 recommendation).

**Problem.** Today's hero `courier_drone` build certifies, but the artifact evidence shows "constructive fallback because the geometry kernel was unavailable" and "topology selected Blender subprocess but fell back to reference cleanup because Blender output was non-watertight." In other words: we certify through fallbacks, not through real robust geometry. Cloned LODs, body-count instability, and silent topology fallback are all symptoms.

**Target outcome.** A robust manifold/boolean kernel (e.g. `elalish/manifold`) is the production path. Non-watertight output is a hard failure in strict mode. Body count and part identity are stable across identical rebuilds. Golden geometry fixtures pin topology invariants per hero.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| GEO-1 | Evaluate `elalish/manifold` integration | Prototype behind optional adapter; measure perf on 3 heroes; report watertightness + body-count stability | L | — |
| GEO-2 | Feature/CSG/BRep IR before mesh realization | New `lathe/csg_ir.py` captures primitive + boolean history; realization is a late stage | XL | GEO-1 |
| GEO-3 | Adapter pattern: robust kernel → Blender → reference fallback | `lathe/backends.py` capability registration; attempted-vs-actual tracing surface | M | GEO-1 |
| GEO-4 | Strict-mode watertightness gate | `strict=true` raises `GeometryValidationError("non_watertight")` instead of falling back | S | GEO-1 |
| GEO-5 | Body count + part identity preservation | IR tracks part IDs through booleans; final mesh has stable `face_parts` array; identity preserved across 3 rebuilds | M | GEO-2 |
| GEO-6 | Self-intersection detection + repair | Strict mode: detect self-intersection via the kernel, emit diagnostic, attempt repair, fail if unrepairable | M | GEO-1 |
| GEO-7 | Normal-consistency + winding-order gate | Strict mode: all face normals consistent, winding CCW from outside; gate failure on inconsistency | S | GEO-1 |
| GEO-8 | Golden geometry fixtures with topology invariants | Pin manifold-status, body-count, genus, Euler char, triangle count, bbox extents for each hero | M | GEO-5 |

**Dependency note.** E2 blocks E3 (real game-ready stages) because LOD decimation and collision decomposition need watertight input. E2 also blocks strong E6 (Godot) because engine import is more useful when assets are certifiably clean.

---

## E3. Real Game-Ready Stages

**Source:** research-findings + cad-research (URDF/kinematic validation lessons).

**Problem.** Our rig / interfaces / physics / optimize stages have stub backend IDs. Optimize clones LODs rather than generating decimated LODs. Texture memory accounting is ~0. Physics uses simple proxy rather than convex-decomposition collision. Sockets/pivots/anchors exist as metadata but aren't first-class with engine-facing semantics.

**Target outcome.** Every hero emits real LODs, real collision hulls, real sockets/pivots/anchors with axis info, real texture memory budgets, and real engine-specific manifests. A downstream Godot/Unreal/Unity consumer gets nodes + resources wired correctly without manual cleanup.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| STAGE-1 | Real LOD decimation with screen-size thresholds | LOD0/1/2/3 produce distinct triangle budgets (e.g. 100% / 50% / 25% / 10%); screen-size thresholds in manifest | M | GEO-1 |
| STAGE-2 | Convex decomposition collision | V-HACD or similar; per-part collision with configurable concavity; emit collision hull count + volume | M | GEO-1 |
| STAGE-3 | Socket first-class metadata with axis | Socket = origin + axis + kind; preserve through refs (REF-5) | S | REF-5 |
| STAGE-4 | Pivot first-class metadata with axis | Pivot = origin + axis; used for animation + gameplay | S | REF-5 |
| STAGE-5 | Anchor (socket compatibility) typing | Sockets declare compat-kind; engine importer can match | S | STAGE-3 |
| STAGE-6 | Rig semantics: hinge/slider/revolute joints | Mechanical assets declare joint types + limits + axis_ref | M | REF-5, LANG-6 |
| STAGE-7 | Texture memory accounting | Per-material texture set × resolution × format → memory in MB; budget gate | S | — |
| STAGE-8 | Material slot / draw-call budgets | Per-profile budget; fail certification when exceeded | S | STAGE-7 |
| STAGE-9 | LOD per-stage triangle count targets | Profile declares LOD ladder; LOD stage enforces | S | STAGE-1 |
| STAGE-10 | Engine-specific package manifest emission | Godot / Unreal / Unity-shaped import hints in `manifest.json` | M | STAGE-2, STAGE-3 |
| STAGE-11 | URDF-style validation | Unique socket/pivot IDs, parent/child refs resolve, graph acyclic, limits valid, referenced meshes exist | S | STAGE-3, STAGE-4 |
| STAGE-12 | Gameplay tag catalog | Standardized tags for sockets ("grip", "mount", "attachment"), pivots ("hinge", "slider"), rigs; enum gate in checker | S | STAGE-3, STAGE-4 |

---

## E4. Certification Reports + Studio + Viewer

**Source:** all three docs converge here.

**Problem.** BL-36 (Wave 4.IV.d, commit `8b650df`) shipped a working terminal + HTML report at `lathe/reports/` + a static artifact viewer at `lathe/viewer/` + `--report {terminal,html,json}` flag + `docs/error_codes.md` (22 rows). Those are MVP-grade: the HTML report lacks dimension callouts, cut-plane/section renders, LOD/collision/material inventory, and ref-aware navigation. The terminal report is a one-shot render, not interactive. The viewer is static-file serving with no part tree, no diagnostic panel, no URL state. There's no browser-native iteration loop (editor + viewport + variant controls + live rebuild). This epic **extends** the BL-36 foundation rather than rebuilding it.

**Target outcome.** `report.html` adds ref-aware navigation, dimension callouts, section-cut renders, LOD/collision/material/socket inventory tables, and reproduction commands. Terminal report gains interactive expand/collapse + jump-to-ref. A `lathe studio` browser IDE (net-new, not in BL-36) wraps the compiler pipeline with source pane + normalized pane + diagnostics + preview viewport + variant sliders. URL state makes every view shareable.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| RPT-1 | **Extend** BL-36 HTML report with ref-aware navigation + dimension callouts + section views + inventory tables | New sections added to existing `lathe/reports/html.py`: Geometry Metrics / LODs / Materials / Collision / Sockets / Refs table / Reproduction Commands / Section-cut renders. Existing sections retained. | M | REF-5 |
| RPT-2 | **Extend** BL-36 terminal report with interactive expand/collapse + jump-to-ref | Current `lathe/reports/terminal.py` is a one-shot render; add interactive mode via `rich.live` (or fallback) with collapsible sections and ref jumps | S | REF-5 |
| RPT-3 | Report determinism | Generated from machine-readable cert data; stable across rebuilds; presentation layer only | S | RPT-1 |
| RPT-4 | Deterministic snapshots | `front / side / top / iso / wireframe / collision_overlay / LOD_comparison / UV_layout / section_cut` | M | STAGE-10 |
| RPT-5 | `lathe snapshot` CLI command | `lathe snapshot <build_dir> --view iso --out ./foo.png` | S | RPT-4 |
| RPT-6 | `lathe snapshot --align-ref` | Auto-pick orthographic view from ref's dominant normal (face) or edge direction (edge) | M | REF-9 |
| RPT-7 | `lathe studio` browser IDE | Served by `lathe serve --studio`; React+three.js or similar; read-only over build dir | XL | RPT-1, REF-15 |
| RPT-8 | Studio panels | Source / Normalized / Plan / Diagnostics / Preview / Variants / Cert / Artifacts / Stage bundles | L | RPT-7 |
| RPT-9 | Studio URL state | `?asset=` `?variant=` `?stage=` `?ref=` `?diagnostic=` | S | RPT-7 |
| RPT-10 | Studio copy-ref buttons | Every selectable entity (part, socket, face, diagnostic) has a copy-`@lathe[...]`-to-clipboard button | S | RPT-7, REF-15 |

**Note.** RPT-7 is the largest single ticket in this doc. Can be scoped as MVP (read-only, single build) first, then iterated.

---

## E5. Standards-Grade Packaging

**Source:** research-findings.

**Problem.** We emit `.glb` + `.usda` but don't run validators against either. Production adoption requires validator green-runs + advanced extensions (KTX2/Basis, meshopt) + standardized material export (MaterialX/OpenPBR).

**Target outcome.** Every package output is validated against its format's validator. Optional advanced extensions land behind explicit profile flags. MaterialX + OpenPBR are a first-class export lane. Per-engine compatibility matrix documented.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| STD-NEW-1 | glTF Validator integration | Package stage runs `gltf-validator` on every `.glb`; errors → cert fail, warnings → report | S | — |
| STD-NEW-2 | `usdchecker` integration | Same for `.usda` / `.usd` / `.usdz` | S | — |
| STD-NEW-3 | `usdzip` for portable USDZ packaging | Optional output format | S | STD-NEW-2 |
| STD-NEW-4 | `KHR_texture_basisu` extension | Optional KTX2/Basis texture delivery behind `--ktx2` flag | M | STAGE-7 |
| STD-NEW-5 | `EXT_meshopt_compression` extension | Optional meshopt compression for game/runtime delivery | M | STAGE-1 |
| STD-NEW-6 | MaterialX graph export lane | Compile surface programs to MaterialX graphs | L | — |
| STD-NEW-7 | OpenPBR surface shading model | MaterialX graphs use OpenPBR node network | M | STD-NEW-6 |
| STD-NEW-8 | Per-engine package compatibility matrix | `docs/engine_compat.md` + manifest field `engine_compatibility: {godot: "native", unreal: "import+manual", unity: "import+manual"}` | S | STAGE-10 |
| STD-NEW-9 | Color-space + roughness/metalness convention conformance | Packed-map layout checker (ORM: ambient-occlusion-roughness-metalness in R/G/B channels) | S | — |
| STD-NEW-10 | Packed-map layout conformance | Per-target engine map-packing format gate | S | STD-NEW-9 |

**Note on ticket IDs.** Prefixed `STD-NEW-*` to avoid collision with `plan_completeness.md` STD-1..4.

---

## E6. Engine Integration

**Source:** research-findings (Godot-first thesis) + cad-research + forgecad.

**Problem.** BL-44 **Godot AssetLib submission is tracked in `plan_completeness.md` as GTM-5/BL-44** and is not re-listed here (the epic-map rule forbids duplicating). Current addon (commit `e4f4a96`, Wave 5.I) is MVP-grade: runtime GLTFDocument + 2s polling watcher + basic enrichment. Real engine integration needs a Godot EditorImportPlugin + thumbnail regen + build-trace viewer integration + certified-state indicator + fsnotify watcher, plus eventual Unreal/Unity parity.

**Target outcome.** Users install `lathe-godot` via AssetLib (GTM-5) → open a demo project → run `lathe build` → asset appears enriched (sockets as Marker3D, collision as CollisionShape3D, LODs wired, cert panel visible). 90-second screen-capture flow reproducible. Eventual Unreal/Unity plugins with the same import surface.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| ENG-2 | `EditorImportPlugin` replacement | Replace runtime GLTFDocument with native Godot ImportPlugin | M | — |
| ENG-3 | Godot thumbnail regen | Auto-generate Godot-facing thumbnails per asset | S | ENG-2 |
| ENG-4 | Build-trace viewer integration | Dock button → opens `lathe inspect <build_dir>` in external shell | S | — |
| ENG-5 | fsnotify-based file watcher | Replace 2s polling with OS-level file events | S | — |
| ENG-6 | Certified-state indicator per scene | Badge on nodes imported from Lathe: ✓ certified / ⚠ outdated / ✗ failed | M | ENG-2 |
| ENG-7 | Unreal integration (later scope) | Unreal plugin with equivalent import surface | XXL | STAGE-10 |
| ENG-8 | Unity integration (later scope) | Unity package with equivalent import surface | XXL | STAGE-10 |

**Note.** ENG-1 slot is intentionally skipped — the "Godot AssetLib submission" deliverable lives at `plan_completeness.md` GTM-5/BL-44. Keeping two ownership locations would violate this doc's "cross-reference and don't duplicate" rule.

---

## E7. Provider Proposal Harness

**Source:** research-findings + cad-research (comparable evaluation heuristic).

**Problem.** Provider adapters exist (Hunyuan HTTP, VGGT local, Codex ImageGen, reference_conditioned) but there's no disciplined way to compare provider candidates. `scripts/run_benchmark.py` has competitor stubs but doesn't run same-asset comparisons across providers.

**Target outcome.** A benchmark suite compares providers on the same asset corpus with Lathe cert-score as the judgment metric. Strict learned-provider mode fails when fallback engages. Candidate visualizer shows accept/reject deltas. Provider cards document license / hardware / seed / known failure modes.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| PROV-1 | Benchmark corpus: same-asset × N providers | `scripts/run_provider_benchmark.py`; per-provider JSON with runtime, hardware, seed, license, output stats, cert score | M | — |
| PROV-2 | Provider result metadata enrichment | Every provider run records: wall-clock, peak mem, seed, config hash, weights hash, license string, output tri count, bbox | S | — |
| PROV-3 | Strict learned-provider mode | `shape.strict=true` + explicit provider → fallback raises `ShapeProviderExecutionError("learned_fallback_blocked")` (extends BL-37) | S | — |
| PROV-4 | Candidate visualizer | `lathe providers diff <asset> --runtime-configs A,B` → side-by-side mesh comparison with accept/reject deltas | M | REF-11 |
| PROV-5 | Native trust-anchor enforcement | Default runtime config selects native; learned is opt-in; documented as design principle | XS | — |
| PROV-6 | Provider cards | `docs/providers/cards/<name>.md` with license / hardware / seed / known-failure-modes / reproducibility steps | S | PROV-2 |

---

## E8. Parameter Robustness

**Source:** forgecad.

**Problem.** Procedural assets often pass at default dimensions but fail when a parameter changes. Variants are first-class in `.lth` but aren't systematically sampled. A 20%-larger `courier_drone` may silently lose certification.

**Target outcome.** `lathe scan-variants` runs the full pipeline on N sampled variant configurations and reports per-stage failure grouping. `lathe scan-params` (after LANG-1 parameter metadata lands) does the same across declared parameter ranges.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| PARAM-1 | `lathe scan-variants <file> <asset> --samples N` | Runs normalize/check/plan/build/certify per variant; summary table grouped by stage + diagnostic | M | — |
| PARAM-2 | `lathe scan-params <file> <asset> --profile P --samples N` | Same but sampling parameter ranges (needs LANG-NEW-1) | S | LANG-NEW-1 |
| PARAM-3 | Per-sample pipeline run harness | Shared infra for PARAM-1 + PARAM-2 | S | — |
| PARAM-4 | Failure grouping by stage + diagnostic code | Output: markdown table with stage × diagnostic → count of failed variants | S | PARAM-3 |
| PARAM-5 | Failed-config reproducible fixture emit | Each failed config written as `tests/fixtures/scan_failures/<hash>.lth` | S | PARAM-4 |

---

## E9. v0.2 Language Extensions

**Source:** forgecad.

**Problem.** Current `.lth` is good for high-level intent but lacks precision mechanical modeling (sketches, constraints, dimensions), parametric metadata (live UI sliders), and kinematic semantics (assembly graphs, joints with limits).

**Target outcome.** v0.2 `.lth` supports:

- `parameter` declarations inside `profile` with `min / max / unit / ui` hints.
- `sketch` blocks with 2D primitives + constraints + dimensions.
- `feature` blocks with `extrude / revolve / sweep / pattern` operations.
- `assembly` + `joint` blocks for kinematics.

These are breaking language changes; require coordinated update across spec + grammar + schema + parser + normalizer + resolver + checker + examples + tests per AGENTS.md coordinated-change rule.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| LANG-NEW-1 | `parameter` metadata in `profile` | Grammar + schema + example: `parameter wing_span = 2.4 { min: 1.6, max: 3.2, unit: "m", ui: slider }` | M | — |
| LANG-NEW-2 | Parameter provenance in build outputs | `build_report.json.parameters[]` records resolved values + their source parameter | S | LANG-NEW-1 |
| LANG-NEW-3 | `sketch` block with 2D primitives + constraints | Grammar support for `rect / circle / line / polygon` + `coincident / parallel / equal_radius / distance / angle` constraints | L | — |
| LANG-NEW-4 | `feature` block with extrude/revolve/sweep | Grammar + kernel ops: extrude sketch to height, revolve around axis, sweep along path, pattern (linear/circular/mirror) | L | LANG-NEW-3, GEO-2 |
| LANG-NEW-5 | Named-face semantics preserved through refs | Sketch entity names → feature faces → `@lathe[#part.foo.face_top]` refs | M | LANG-NEW-4, REF-6 |
| LANG-NEW-6 | `assembly` block with parts + joints | Grammar: `assembly { part "body" from feature "body_shell"; ... }` | M | LANG-NEW-4 |
| LANG-NEW-7 | `joint` types (revolute/prismatic/fixed/coupling) | Grammar: `joint "hinge" { type: revolute; parent: "body"; child: "arm"; axis_ref: "@lathe[...]"; limits: [-90deg, 0deg] }` | M | LANG-NEW-6 |
| LANG-NEW-8 | v0.2 coordinated migration | Update spec/grammar/schema/parser/normalizer/resolver/checker/examples/tests in one PR per AGENTS.md rule | XL | LANG-NEW-1 through LANG-NEW-7 |

**Note.** `LANG-NEW-*` are net-new tickets. `plan_completeness.md` does **not** define `LANG-1..3`; the `-NEW-` suffix is retained to signal "full coordinated language migration" scope and to avoid ambiguity if a future minor language tweak gets a plain `LANG-1` ID.

---

## E10. Agent Workflow & Distribution

**Source:** all 3 docs.

**Problem.** Lathe is designed for agents but lacks packaged agent context, packaged agent skills, and ref-aware workflow docs. Agents rediscover the system on every new session.

**Target outcome.** `lathe docs one-file --out lathe-context.md` produces a compact agent manual. Official skills (`lathe-author`, `lathe-build-debug`, `lathe-ref-workflow`, `lathe-godot`) distribute via Claude Code skills marketplace / Continue / Cursor / OpenHands / Devin (Persona-C channels from Plan 09). AGENTS.md documents the ref workflow.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| AGENT-1 | `lathe docs one-file` CLI | Generates a compact agent manual from spec + grammar + schema + canonical commands + examples + common diagnostics + artifact layout; ≤5000 words | M | — |
| AGENT-2 | CI check agent context stays current | Rebuilds lathe-context.md in CI; fails PR if stale | S | AGENT-1 |
| AGENT-3 | `lathe-author` official skill | Skill package: edit `.lth`, preserve public surface, coordinate changes per AGENTS.md | S | AGENT-1 |
| AGENT-4 | `lathe-build-debug` official skill | Skill package: run check/plan/build, inspect diagnostics, apply targeted repairs | S | AGENT-1 |
| AGENT-5 | `lathe-ref-workflow` official skill | Skill package: use `@lathe[...]` refs, inspect facts, make targeted edits | S | AGENT-1, REF-9 |
| AGENT-6 | `lathe-godot` official skill | Skill package: build certified asset + import into Godot demo project | S | AGENT-1, ENG-1 |
| AGENT-7 | AGENTS.md refresh | Add ref-workflow rules + "never hand-edit generated artifacts" policy | S | REF-14 |

---

## E11. Example + Benchmark Corpus Discipline

**Source:** forgecad.

**Problem.** Examples exist but aren't organized by feature and aren't regression-tested systematically. There's no AI-authoring benchmark (distinct from the competitor-comparison benchmark landed in BL-35 / Plan 09 Phase 4).

**Target outcome.** Three example tracks:

- `examples/api/<feature>/` — tiny focused examples per public feature.
- `examples/compiler-corpus/` — edge-case fixtures for checker/parser/normalizer regression.
- `examples/bench-v1/` — AI-authoring benchmark with prompts + rubrics + reference solutions + scoring scripts.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| BENCH-NEW-1 | `examples/api/<feature>/` mini-examples per public feature | 1 minimal + 1 realistic + 1 failing-diagnostic fixture per feature (shape_intent, materials, LODs, collision, sockets, variants, backend_selection, certification) | M | — |
| BENCH-NEW-2 | `examples/compiler-corpus/` focused fixtures | Edge cases for checker/parser/normalizer/resolver (cyclic uses, missing profile, conflicting variants, etc.) | M | — |
| BENCH-NEW-3 | `examples/bench-v1/` AI-authoring corpus | 7+ task-based benchmarks: modular crate, drone variants, hinge assembly, vehicle wheel, wall panel, doorway kit, weapon rail | L | — |
| BENCH-NEW-4 | Per-benchmark metadata | Each bench-v1 item: `prompt.md / constraints.yaml / reference.lth / rubric.json / expected_artifacts.json` | M | BENCH-NEW-3 |
| BENCH-NEW-5 | LLM scorecard publication | `docs/benchmarks/llm_scorecard.md` — parse success / check success / build success / cert score / prompt compliance across models | M | BENCH-NEW-4 |
| BENCH-NEW-6 | Benchmark regression CI | New workflow runs bench-v1 on every PR; score delta reported | S | BENCH-NEW-4 |
| BENCH-NEW-7 | Example corpus CI | Every `examples/api/*` builds cleanly; every `examples/compiler-corpus/*` matches expected diagnostic codes | S | BENCH-NEW-1, BENCH-NEW-2 |

---

## E12. SDF / Experimental Lane

**Source:** forgecad.

**Problem.** BL-40 (full soft-surface stack) is deferred. For organic/soft-surface assets, CSG doesn't fit — need signed-distance-function lane. Currently no experimental SDF backend.

**Target outcome.** `lathe.topology.sdf_lane_v1` registered as opt-in experimental backend. SDF → mesh lowering via marching cubes or similar. Experimental-only contract gate prevents promotion to strict mode.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| SDF-NEW-1 | SDF backend capability class | Extend `lathe/backends.py` with experimental capability tier | S | — |
| SDF-NEW-2 | `lathe.topology.sdf_lane_v1` adapter | Behind `--experimental sdf` flag; registered as opt-in | M | SDF-NEW-1 |
| SDF-NEW-3 | SDF → mesh lowering | Marching cubes (or similar) converts SDF field to mesh; feeds downstream pipeline | L | SDF-NEW-2 |
| SDF-NEW-4 | Experimental-only contract gate | Certification fails if strict mode + experimental SDF; warning on warning mode | S | SDF-NEW-2 |

---

## E13. DX & Tooling Polish

**Source:** research-findings + forgecad.

**Problem.** Several DX gaps the research docs call out specifically, beyond what's in `plan_completeness.md` (DX-1..8).

**Target outcome.** Cache is first-class. Python bootstrap is deterministic. Test infrastructure respects fast/slow split. LSP is editor-grade. Formatter handles multi-line comments. Error messages include dependency/env diagnosis.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| DXPOL-1 | `lathe cache status\|clean\|warm` CLI | Promote implicit cache to first-class; cache moves from `%TEMP%` to `~/.cache/lathe` | S | PERF-1 |
| DXPOL-2 | Python interpreter bootstrap consistency | Document that `.venv/Scripts/python.exe` is the canonical interpreter; error if system `python` is >= venv version (research-findings found 3.14 system vs 3.13 venv mismatch) | S | — |
| DXPOL-3 | Test infrastructure: fast/slow split | `pytest -m fast` runs <30s; `pytest -m slow` runs full suite; CI splits accordingly | S | — |
| DXPOL-4 | Full LSP upgrade | Diagnostics + hover + completion + go-to-def + document symbols; not just the Wave 1 symbol-index stub | L | — |
| DXPOL-5 | `.lth` syntax highlighting packages | VS Code (textmate grammar), Neovim (treesitter), IntelliJ (plugin) | M | — |
| DXPOL-6 | Formatter polish: multi-line `/* */` internal indent | Current BL-32 gap: internal whitespace of multi-line block comments is normalized; fix | S | — |
| DXPOL-7 | Error message audit with dep/env diagnosis | Every CLI error includes: what went wrong / why / remediation / dep-probe suggestion | M | — |
| DXPOL-8 | Every UI action maps to a reproducible CLI command | Studio emits exact `lathe ...` command for every action; displays in bottom-bar | S | RPT-7 |

---

## E14. Security — cross-ref + 2 net-new

See `docs/plan_completeness.md` SEC-1..8 for path hardening, binary parser hardening, gitleaks, SBOM, CodeQL/Bandit/Semgrep/Trivy, threat model, Blender sandbox, and `.lth` prompt-injection. Those 8 are already tracked there as P0-before-public and are **not** re-listed here.

Two additional items implied by the research docs that are **not** in `plan_completeness.md` and count as net-new tickets for this roadmap:

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| SEC-NEW-1 | Provider-output sandbox | Learned-provider mesh output is treated as untrusted until size / format / sanity checks pass; extends `plan_completeness.md` SEC-2 binary-parser-hardening specifically for provider-produced artifacts | M | — |
| SEC-NEW-2 | Signed build reproducibility | Every certified build signed with ed25519 + reproducibility hash published; ties to BL-31 publish runner | M | — |

---

## E15. Performance & Scalability

**Source:** research-findings.

**Problem.** Build cache is implicit and temp-rooted. No batch-build worker pool. Perf budgets in `perf/budgets.json` are auto-generated (BL-43) rather than hand-authored per asset class.

**Target outcome.** Content-addressed cache at `~/.cache/lathe`. Inspection + invalidation commands. Worker pool for parallel asset builds. Hand-authored per-class perf budgets. Real-user monitoring via BL-37 telemetry aggregation.

**Tickets.**

| ID | Title | Acceptance | Effort | Deps |
|---|---|---|---|---|
| PERF-1 | Content-addressed cache at `~/.cache/lathe` | Move off `%TEMP%`; key by `hash({program, asset, runtime_config, cache_version})` | S | — |
| PERF-2 | Cache inspection + invalidation CLI | `lathe cache status` (entries, size); `lathe cache clean [--asset X]`; `lathe cache warm <file> <asset>` | S | PERF-1, DXPOL-1 |
| PERF-3 | Worker pool for parallel asset builds | `lathe build-many <file> --jobs 4` builds all assets in parallel | M | — |
| PERF-4 | Hand-authored perf budgets per asset class | Replace auto-generated `perf/budgets.json` with per-class targets; categorized by family (mechanical / container / panel / organic) | S | — |
| PERF-5 | Real User Monitoring via telemetry aggregation | BL-37 opt-in telemetry aggregates into perf histograms at `telemetry.lathe.dev` dashboard | L | GTM-8 |

---

## E16. Ops & GTM Cross-Ref

See `docs/plan_completeness.md` OPS-1..6 and GTM-1..8 for push-to-GitHub, first PyPI release, GitHub Pages, issue triage, Dependabot cadence, branch protection, Discord seeding, first blog post, AssetLib submission, design-partner outreach. All already tracked.

---

## Cross-epic dependency graph

```
E2 (geometry) ─┬→ E3 (game-ready stages)
               └→ E6 (engine integration strong path)

E1 (refs) ────┬→ E4 (studio/viewer/reports)
              ├→ E6 (engine metadata via ref IDs)
              ├→ E10 (ref-workflow agent skill)
              └→ E15 (ref-addressable perf events)

E3 (stages) ──┬→ E5 (standards packaging with real LODs/materials)
              ├→ E6 (real game-engine metadata)
              └→ E11 (per-feature example corpus needs stages working)

E9 (v0.2 lang) ─┬→ E3 (joint/assembly semantics)
                ├→ E8 (parameter robustness scans parameters)
                └→ E11 (new language features need examples + bench entries)

E4 (studio) ──── RPT-7 requires E1 ref integration for useful UX

E7 (providers) ─ PROV-4 candidate visualizer benefits from E1 ref diff
```

Cleanest critical path:
`E2 → E3 → E1 → E4 → E5 → E6 → E7 → E11 → E10 → (E8 + E9) → E13 → E15 → E12`

---

## Phased rollout — V0.2 → V0.5 → V1.0

### V0.2 release — target 2–3 months

**Theme.** Production-grade geometry + real game-ready stages + reports + Phase-1 refs (the non-geometric slice).

Dependency audit against the epic ticket rows:

- `STAGE-3` (socket) + `STAGE-4` (pivot) depend on `REF-5` (selector manifest writer).
- `RPT-1` (HTML report expansion) depends on `REF-5`.
- `STAGE-6` (rig: hinge / slider / revolute joints) depends on `REF-5` **and** `LANG-NEW-6` (assembly block) — the latter is v0.2 language work scheduled for V0.5.
- `RPT-6` (`snapshot --align-ref`) depends on `REF-9` (ref inspect with face normals), which depends on `REF-6` (face/edge extraction, heavy, deferred to V0.3).

To make V0.2 executable without waiting on V0.3/V0.5:

- **Pull a Phase-1 refs slice into V0.2.** The non-geometric refs (REF-1, REF-2, REF-3, REF-4, REF-5, REF-7, REF-8, REF-13, REF-14) are cheap (~2–3 weeks) and unblock STAGE-3, STAGE-4, and RPT-1. Phase-2 refs (face/edge extraction, REF-6 + REF-9..12 + REF-15 + REF-16) stay in V0.3.
- **Defer STAGE-6 full rig/joint semantics to V0.5.** It legitimately needs LANG-NEW-6.
- **Defer RPT-6 `--align-ref` to V0.3.** It legitimately needs REF-9.

Tickets in scope for V0.2:

- `plan_completeness.md` P0: `OPS-1`, `SEC-1`, `SEC-2`, `SEC-3`.
- **E1 Phase-1 refs slice** (non-geometric): `REF-1`, `REF-2`, `REF-3`, `REF-4`, `REF-5`, `REF-7`, `REF-8`, `REF-13`, `REF-14` — 9 tickets.
- **E2 robust geometry**: `GEO-1..8` — 8 tickets.
- **E3 real stages minus STAGE-6**: `STAGE-1..5` + `STAGE-7..12` — 11 tickets. STAGE-6 moves to V0.5.
- **E4 reports-only slice**: `RPT-1..5`. RPT-6 moves to V0.3; RPT-7..10 studio moves to V0.3. 5 tickets.
- **E6 Godot maturity**: `ENG-2..6` — 5 tickets. (ENG-1 AssetLib submission is `plan_completeness.md` GTM-5.)
- **E11 partial**: `BENCH-NEW-1`, `BENCH-NEW-2`, `BENCH-NEW-7` — 3 tickets.
- **E14 security net-new**: `SEC-NEW-1`, `SEC-NEW-2` + `plan_completeness.md` `SEC-4..8`.
- **E15 cache**: `PERF-1`, `PERF-2`, `PERF-4` — 3 tickets.

Effort estimate: **14–18 engineer-weeks** (was 12–16; the Phase-1 refs slice adds ~2 weeks net after the STAGE-6 and RPT-6 removals offset some).

Acceptance: Every hero certifies without hidden fallback. 10th hero (satchel) on soft stack. HTML report gains ref-aware navigation + inventory tables. `@lathe[...]` refs resolvable for non-geometric entities (build/asset/variant/stage/part/socket/collision/material/diagnostic). `lathe-godot` on AssetLib (via GTM-5). PyPI first release (V0.2.0 tag). Blog post #1 published.

### V0.3 release — target +3 months (5–6 months cumulative)

**Theme.** Phase-2 refs (geometry extraction) + full studio + standards + agent-first.

Tickets in scope:

- **E1 Phase-2+3 refs**: `REF-6`, `REF-9`, `REF-10`, `REF-11`, `REF-12`, `REF-15`, `REF-16` — 7 tickets.
- **E4 full studio + align-ref**: `RPT-6`, `RPT-7`, `RPT-8`, `RPT-9`, `RPT-10` — 5 tickets.
- **E5 standards packaging**: `STD-NEW-1..10` — 10 tickets.
- **E7 provider harness**: `PROV-1..6` — 6 tickets.
- **E10 agent workflow**: `AGENT-1..7` — 7 tickets.
- **E11 remainder**: `BENCH-NEW-3..6` — 4 tickets.
- **E13 partial**: `DXPOL-1`, `DXPOL-6`, `DXPOL-8` — 3 tickets.
- **E15 perf**: `PERF-3`, `PERF-5` — 2 tickets.

Effort estimate: **12–15 engineer-weeks**.

Acceptance: Every build addressable via `@lathe[...]` including faces/edges. Studio in browser with part-tree + diagnostic panel + URL state. glTF Validator + usdchecker green on all heroes. Provider benchmark published with same-asset × N-provider comparison. Agent skills live on Claude Code / Continue / Cursor. LLM scorecard published. Blog post #3 (benchmark) published. 3 design-partner LOIs signed.

### V0.5 release — target +3 months (8–9 months cumulative)

**Theme.** v0.2 language extensions + parameter robustness + LSP + deferred STAGE-6.

Tickets in scope:

- **E9 v0.2 language**: `LANG-NEW-1..8` full coordinated migration — 8 tickets.
- **E8 parameter robustness**: `PARAM-1..5` — 5 tickets. (PARAM-2 unblocks once LANG-NEW-1 lands.)
- **STAGE-6** full rig/joint semantics deferred from V0.2 — 1 ticket. Unblocks once LANG-NEW-6 lands.
- **E13 DX polish**: `DXPOL-4`, `DXPOL-5`, `DXPOL-7` — 3 tickets.

Effort estimate: **10–14 engineer-weeks** (LANG-NEW-8 dominates).

Acceptance: v0.2 language shipped with sketches, features, parameters, assemblies, joints. Parameter robustness scans run in CI for every hero. LSP lands in VS Code Marketplace. Public launch post on Hacker News + Godot Discord. 1000+ GitHub stars. 100+ assets certified by external users (via opt-in telemetry).

### V1.0 release — target +3 months (11–12 months cumulative)

**Theme.** Experimental lanes + commercial readiness.

Tickets in scope: E12 (SDF-NEW-1..4), remaining plan_completeness items (BL-40 full soft-surface, BL-41 Pyodide playground), monetization launch (hosted registry beta), Unreal/Unity integrations starting (ENG-7, ENG-8).

Effort estimate: **10–16 engineer-weeks**.

Acceptance: SDF experimental lane live. Pyodide playground on web. Hosted registry beta with paying design partners. Unreal plugin alpha. Public keynote delivered at ≥1 venue. 3+ design-partner case studies published.

---

## Ticket totals

| Epic | Tickets | Est. weeks |
|---|---|---|
| E1 Refs | 16 | 3–5 |
| E2 Geometry | 8 | 3–6 |
| E3 Game-ready stages | 12 | 3–5 |
| E4 Reports/Studio | 10 | 2–4 |
| E5 Standards | 10 | 2–3 |
| E6 Engine integration | 7 | 2–3 (+6+ for Unreal/Unity) |
| E7 Providers | 6 | 1–2 |
| E8 Parameter robustness | 5 | 1 |
| E9 v0.2 language | 8 | 6–10 |
| E10 Agent workflow | 7 | 1–2 |
| E11 Corpus discipline | 7 | 1–2 |
| E12 SDF experimental | 4 | 2 |
| E13 DX polish | 8 | 2–3 |
| E14 Security net-new | 2 | <1 |
| E15 Performance | 5 | 1–2 |
| **Net-new total** | **115** | **30–51 engineer-weeks** |

Plus `plan_completeness.md` carries an additional 44 tickets for original-plan residuals. Combined grand total: **159 tickets**, roughly 45–65 engineer-weeks of work from current state to full V1.0.

---

## Source-doc traceability

Which research doc motivates which ticket (quick-scan table). "C" = cad-research, "F" = forgecad, "R" = research-findings.

| Epic | Tickets | C | F | R |
|---|---|---|---|---|
| E1 Refs | REF-1..16 | ✓ | ✓ |  |
| E2 Geometry | GEO-1..8 |  |  | ✓ |
| E3 Stages | STAGE-1..12 | ✓ |  | ✓ |
| E4 Reports/Studio | RPT-1..10 | ✓ | ✓ | ✓ |
| E5 Standards | STD-NEW-1..10 |  |  | ✓ |
| E6 Engines | ENG-1..8 | ✓ | ✓ | ✓ |
| E7 Providers | PROV-1..6 |  | ✓ | ✓ |
| E8 Params | PARAM-1..5 |  | ✓ |  |
| E9 v0.2 lang | LANG-NEW-1..8 |  | ✓ |  |
| E10 Agents | AGENT-1..7 | ✓ | ✓ | ✓ |
| E11 Corpus | BENCH-NEW-1..7 |  | ✓ |  |
| E12 SDF | SDF-NEW-1..4 |  | ✓ |  |
| E13 DX | DXPOL-1..8 |  | ✓ | ✓ |
| E14 Security-NEW | SEC-NEW-1..2 |  |  | ✓ |
| E15 Perf | PERF-1..5 |  |  | ✓ |

---

## Open design questions

From the research docs' "open questions" sections, consolidated:

1. **Refs path:** Should refs use source paths, build dirs, or both? (cad-research §Open Questions)
2. **Ref prefix split:** `@lathe[...]` unified vs `@lathe-src[...]` + `@lathe-build[...]`? (cad-research)
3. **Face/edge stability:** How stable can face/edge ordinals be after topology repair? (cad-research)
4. **Selector manifest stability:** Public contract or experimental in V0.2? (cad-research)
5. **Refs → source spans:** Should refs map back to `.lth` source spans? (cad-research)
6. **Godot node naming:** Should Godot node names preserve `@lathe` selector IDs? (cad-research) — likely yes per REF-16.
7. **Selector in packages:** Should selector sidecars ship inside package outputs or only build outputs? (cad-research)
8. **Kernel choice:** Manifold library vs OCP/OpenCascade vs CGAL for GEO-1? (research-findings)
9. **Language migration:** Is v0.2 a major-version bump requiring `profile v0.2 {...}` opt-in, or additive? (forgecad)
10. **Parameter UI taxonomy:** What UI widget types to support — slider, toggle, enum, vector3, file? (forgecad)
11. **Studio distribution:** Pyodide in-browser vs Electron app vs `lathe serve` localhost? (forgecad + research-findings)
12. **Benchmark scoring:** How to weight cert score vs wall-clock vs reproducibility in the AI-authoring LLM scorecard? (forgecad + research-findings)

Each should be resolved with a short ADR (`docs/adr/000N-<topic>.md`) before the ticket that depends on it begins.

---

## How to use this doc

1. When starting a new wave, pick an epic from the **critical path** (E2 → E3 → E1 → E4 ...) or a parallel epic that doesn't block.
2. Promote ticket IDs from this doc into per-wave `plans/WAVE{N}_BACKLOG.md` when scheduling.
3. When a ticket lands, mark status here: `→ DONE (commit SHA)`.
4. When an open design question is resolved, link to the resolving ADR.
5. Revisit priorities quarterly — the research-doc recommendations may age as V0.2 lands.

## Companion docs

- `docs/plan_completeness.md` — original-10-plans residuals (44 tickets).
- `plans/WAVE{N}_BACKLOG.md` — per-wave historical.
- `docs/adr/README.md` — architecture decision records (authoritative design reasoning).
- `cad-research-gpt.MD` / `forgecad-research-gpt.MD` / `research-findings-gpt.MD` — source research at repo root.

---

*Authored 2026-04-24; revised with dependency-respecting V0.2/V0.3/V0.5 slice + corrected counts. Source research: three GPT/Codex studies on text-to-cad, ForgeCAD, and direct Lathe audit. **115** net-new tickets across **13** substantive epics + 1 cross-reference epic (E16). Total Lathe backlog across all sources: **159** tickets → 45–65 engineer-weeks to V1.0. V0.2 critical-path starts with a Phase-1 refs slice (REF-1..5, REF-7, REF-8, REF-13, REF-14) alongside E2 + E3 so STAGE-3/4 and RPT-1 aren't blocked on V0.3 work.*
