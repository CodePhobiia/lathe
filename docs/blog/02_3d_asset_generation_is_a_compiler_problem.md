# 3D Asset Generation Is a Compiler Problem

**Working title:** *3D Asset Generation Is a Compiler Problem: Why Lathe
Is a Language, Not a Prompt Wrapper*

**One-sentence hook:** The reason AI asset tools keep failing studios is
not the model — it is the absence of a compiler around the model.

**Target audience:** Engine and tools engineers, programming-language
enthusiasts, infrastructure-minded tech artists, and researchers building
3D generation systems who are looking for an architectural frame.

**Distribution channel (primary):** Hacker News, lobste.rs. A technical
audience that reads compiler blog posts and will argue about stage
boundaries in the comments.

**Distribution channel (secondary):** The graphics programming subreddit,
the Three.js / Babylon.js Discords, the Godot renderer channel, targeted
shares to the Blender developer list. Follow-up post to "The Build
Passed" 7-10 days later so readers who wanted the technical argument
have a natural second entry point.

**Length target:** 2200-2800 words. This is the deep-dive post; it can
afford length.

**Tone:** Engineering-confident, not polemical. Cite specific modules by
path. Treat the reader as a peer who has built a compiler or a renderer
before.

**Status:** Outline for Plan 09 Phase 11. Not yet written.

---

## Outline

### Section 1 — What a compiler actually is, and why the analogy fits

- Open with the boring, accurate definition: a compiler is a
  staged program that transforms source in a high-level language into
  a target artifact, preserving meaning across explicit intermediate
  representations, with each stage obeying a contract on its inputs
  and outputs.
- Argue that every piece of that definition applies to asset
  production:
  - source in a high-level language: `.lth` files describing asset intent
  - staged transformation: `refs → intent → shape → topology → uv →
    surface → (execution) → rig → interfaces → physics → optimize →
    validate → package → publish`
  - explicit intermediate representations: `AssetGraph`,
    `assembly_blueprint`, `ShapeIR`, `fit_ir`, `transfer_ir`,
    `surface_control_pack`, `atlas_assembly_ir`, and so on
  - contracts between stages: `lathe.shape.intent_mesh_handoff_v1` is
    the headliner, but every stage has a contract
  - a target artifact: a certified, packaged `.usd` / `.glb` / `.gltf`
    / `.obj` bundle with manifests and traces
- Contrast with "prompt wrapper" tools. They skip the IR layer entirely;
  prompt-in, mesh-out, no contract. When something goes wrong, there is
  nothing to debug because there are no stages, no types, and no
  guarantees.
- Companion asset: annotated diagram of Lathe's stages, with
  probabilistic stages shaded differently from deterministic ones.

### Section 2 — The stage pipeline, stage by stage

- Walk through `STAGE_ORDER` in `lathe/executor.py`. Explain each stage
  in one paragraph.
- `refs` — collect and resolve references; file paths, image paths, and
  imported kits/libraries get anchored against the source file.
- `intent` — the declarative block: role, style, parts, materials,
  scale, interactions. This is the user's side of the contract.
- `shape` — the only probabilistic stage. Runs under the
  `lathe.shape.intent_mesh_handoff_v1` contract. Internally:
  `intent → AssetGraph → assembly blueprint → ShapeIR → fused search
  geometry → authoritative mesh → optional provider proposals →
  conformance fit → deterministic downstream`. See `asset_graph.py`,
  `assembly_kernel.py`, `scaffold_compiler.py`, `shape_ir.py`,
  `feature_grammar.py`, `feature_fusion.py`, `mesh_finalize.py`,
  `conformance.py`, `shape_backend.py`, `shape_providers.py`.
- `topology` — deterministic. Uses
  `lathe.topology.blender_hard_surface_v1` when Blender is present,
  falls back to a reference path when it isn't. Either way, contract
  is stable.
- `uv` — deterministic. xatlas-backed primary, explicit fallback when
  xatlas is unavailable.
- `surface` — deterministic bakes plus the V1.2 governed surface
  authoring layer (`surface_backend`, `surface_policy`,
  `decal_library`, `mask_program`, `trim_sheet`). Codex ImageGen is a
  governed backend with explicit fallback, not an unchecked escape
  hatch.
- `execution` — the V1.3 Blender-backed execution planning stage. See
  `lathe/bridge/blender_plan.py`.
- `rig`, `interfaces`, `physics`, `optimize` — deterministic.
- `validate` — the certification stage. Runs the validator suite in
  `lathe/validators/` (`semantic_quality`, `visual_quality`,
  `flow_quality`, `surface_quality`, `silhouette`). A failure here
  triggers repair or aborts the build.
- `package` — writes `.usd` / `.glb` / `.gltf` / `.obj` plus
  manifests. `lathe.package.openusd_gltf_v1` is the Day-1 packager.
- `publish` — intentionally still a scaffold. Called out honestly
  rather than implied complete.
- Companion asset: the same diagram from Section 1, but with a zoom
  panel showing the shape stage sub-pipeline.

### Section 3 — Stable contract IDs and why they are load-bearing

- A stable contract ID is a commitment to future selves and to users.
  `lathe.shape.intent_mesh_handoff_v1` says: whatever the model
  underneath is, the bundle handed to topology has these named
  fields with these semantics.
- Walk through how this enables provider substitution. Configure
  Hunyuan HTTP via `--runtime-config examples/runtime_configs/hunyuan_http.json`
  and the contract-consuming stages do not know or care.
  Configure VGGT via `vggt_local.json`; same story. No provider
  configured; fallback to `lathe.provider.shape.reference_conditioned_v1`;
  still same story.
- Discuss `attempted` vs `actual` provider fields in the trace. This
  is honesty-by-default: when a fallback triggers, the user sees
  exactly which provider was requested and which one ran. Applies
  identically to the Blender topology adapter and xatlas UV adapter.
- Argue that this is the thing most "AI 3D" products do not have.
  Without a stable contract, upgrading a model is a studio-breaking
  event. With one, it is an implementation detail.
- Link to `docs/codex_integration.md` and `docs/first_backend_stack.md`
  for the technical details on how backend substitution is wired.

### Section 4 — Validator-gated certification

- The validator suite is what converts "a mesh that looks right" into
  "an asset that is right."
- Walk through the five validators:
  - `semantic_quality` — the named parts in `intent.parts` are
    actually present as identifiable geometry clusters.
  - `visual_quality` — render-level checks: no obvious holes, no
    z-fighting interiors, no gaping normal seams.
  - `flow_quality` — flow-specific metrics like
    `semantic_preservation_quality`, `join_legality`, and
    `reconstruct_honesty_score`. These matter most for the
    reconstruct flows where an input reference must be faithfully
    honored.
  - `surface_quality` — the V1.2 governed surface checks. Atlas
    integrity, mask coverage, decal placement legality.
  - `silhouette` — render-level silhouette matching against the
    declared intent. A chest that does not read as a chest in
    silhouette fails here.
- Emphasize: these validators are deliberately not weak. Weak
  validators would pass toy-like outputs and destroy the value of the
  "build passed" signal. Don't weaken them without explicit intent.
- Repair-as-a-stage: when validation fails, Lathe can re-enter
  earlier stages under repair policy. Fully autonomous multi-round
  repair is still a scaffold at v0.1 — called out honestly.
- Companion asset: a real `certification.json` output from a hero
  example, syntax-highlighted, with three pass rows and one
  near-miss annotated.

### Section 5 — Why this matters for studios (and what it unlocks)

- Studios already run CI. Lathe makes assets part of CI. A `.lth`
  file in a PR compiles to a certified artifact on the CI runner; a
  failing build blocks merge the same way a failing unit test does.
- Reproducibility falls out of the compiler-shaped architecture.
  Pin the Lathe version and the runtime config, and a build is
  deterministic except at the probabilistic shape stage — and even
  there, the traced seed and provider make re-runs comparable.
- Backend independence means a studio does not buy into a vendor.
  If Hunyuan shuts down, if a better model arrives, if regulatory
  policy rules out external APIs — the `.lth` sources do not
  change. Source semantics survive provider swaps.
- Touch briefly on the monetization path: the validator reports
  and certification artifacts are what studios actually want to
  buy on CI. Defer the deep argument to
  `docs/blog/05_certification_as_the_product.md`.
- Companion asset: a screenshot of a GitHub PR with the Lathe
  certification check in the status-checks widget, green-ticked.

### Calls to action

1. Read `docs/first_backend_stack.md` and `docs/second_backend_stack.md`.
2. Run the full pipeline on an example with `--runtime-config` set to
   a provider you already have access to; inspect the resulting
   `trace.json` for the `attempted` vs `actual` fields.
3. Open an issue proposing a new contract or adapter if our stack
   does not cover your pipeline.
4. Cite the stable contract ID in your own tooling if you integrate
   Lathe — it is the versioning handle we are committing to.

### Companion assets checklist

- Stage-pipeline diagram (reuse from post 01, zoomed).
- Annotated `certification.json` screenshot.
- GitHub PR status-check screenshot. Use a public sample repo.
- Code snippets block (three snippets: an `.lth` intent block, a
  `runtime_config.json` file, and a `trace.json` excerpt). Render as
  syntax-highlighted images for HN, raw code in the markdown source.

### Cross-links

- `docs/lathe_manifesto.md`
- `docs/blog/01_the_build_passed.md` — the intro post.
- `docs/blog/03_five_asset_benchmark.md` — the evidence.
- `docs/blog/05_certification_as_the_product.md` — the CI argument.
- `docs/first_backend_stack.md` — the technical backend detail.
- `docs/architecture/` — the architectural deep-dives, once they
  land.
- `docs/codex_integration.md` — how the Codex-operated bridge
  slots into this model.

### Publishing checklist

- [ ] Every file path cited is verified against `main` at publish
      time (compiler post decays fastest when modules move).
- [ ] Stage list matches `STAGE_ORDER` in `lathe/executor.py` as of
      the pinned release.
- [ ] Contract IDs cited verbatim (`lathe.shape.intent_mesh_handoff_v1`,
      `lathe.topology.blender_hard_surface_v1`, `lathe.uv.xatlas_v1`,
      `lathe.package.openusd_gltf_v1`).
- [ ] Scaffold-limitations section is honest: `publish` runner,
      canonical `fmt`, and multi-round autonomous repair are still
      scaffolds.
- [ ] Cross-links to sibling posts are valid.
