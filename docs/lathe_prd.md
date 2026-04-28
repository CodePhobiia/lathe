# Product Requirements Document

**Version:** 0.2.0rc1 (pre-release reference compiler scaffold)
**Last reviewed:** 2026-04-28
**Product owner:** Tal Merri (@talmerri)
**Reviewer:** requires-human (no second reviewer named yet — backup needed before any GA discussion)

## Problem in one sentence

Current AI-driven 3D pipelines produce visually plausible meshes that game engines and asset pipelines cannot directly use, because topology, UVs, sockets, collision, budgets, and certification are afterthoughts.

## Target user in one sentence

Indie game developers and small-team technical artists who need predictable, reviewable, certifiable 3D assets without running a full art pipeline.

## Product

Lathe

## Working title

Lathe 1.0: Standalone Production 3D Asset Compiler

## Document purpose

This PRD defines the target product shape for Lathe as a standalone system capable of compiling Lathe programs into production-ready 3D assets. It is intended for research, product, and platform engineering teams working on long-horizon capability development.

The current shipping version (`0.2.0rc1`) is a pre-release reference compiler scaffold. It is NOT production-ready, NOT stable, and NOT GA. Where this PRD describes longer-horizon goals (1.0, standalone, learned parity), those are aspirations against the M1–M5 engineering milestones in `docs/roadmap_public.md`, not commitments for the 0.2.0rc1 release. The "Requirement status (v0.2.0rc1)" section near the end is the single source of truth for what 0.2.0rc1 actually does today.

## Executive summary

Lathe should become the programming language and compiler/runtime for production 3D asset creation.

The product should allow a user to declare an asset in Lathe, compile it, and receive a validated, packaged, production-ready result. The system must treat learned generation as one stage inside a broader compiler, not as the whole product. Success is defined by certified asset outputs, not by model novelty alone.

Lathe must eventually stand alone in the sense that a user can remain entirely inside the Lathe language and Lathe runtime to author, build, validate, repair, optimize, and package assets.

## Problem statement

Current AI-driven 3D workflows suffer from recurring weaknesses:

- prompts are ambiguous and difficult to diff, review, and reuse
- generated meshes are often visually plausible but structurally unusable
- topology, UVs, pivots, collision, materials, and budgets are treated as afterthoughts
- deterministic repair work is external and manual
- provenance and reproducibility are weak
- switching providers breaks workflows and assumptions
- teams cannot easily encode or enforce asset contracts
- “done” is not well-defined

Lathe should solve these problems by making asset creation programmable, contract-driven, reproducible, and certifiable.

## Product vision

Lathe should let a user write a Lathe program such as:

```lathe
asset brassbound_chest: hard_surface_prop uses shipping_prop {
  intent {
    role = "ornate brassbound treasure chest"
    style = ["fantasy", "hero_prop", "stylized_realism"]
    parts = [body, lid, lock_plate, latch, handle_l, handle_r, foot_l, foot_r]
    materials = ["oak", "aged_brass", "red_velvet"]
    scale = 0.9m
    interactions = [open_lid, hold_loot, place_in_world]
  }
}
```

and compile it into:

- shape candidates
- an authoritative production mesh
- UVs and surface outputs
- pivots, sockets, anchors, collision, and LODs where relevant
- runtime and platform-compliant packages
- previews, manifests, traces, diagnostics, and certification results

The user experience should feel like software compilation, not prompt wrangling.

## Target users

Primary users:

- technical artists
- gameplay/content engineers
- AI coding agents operating on game/content repositories
- small teams needing asset throughput without large art pipelines

Secondary users:

- R&D teams exploring text-to-asset and image-to-asset workflows
- larger studios seeking reproducible, reviewable asset build systems
- toolchain teams integrating asset generation into CI/CD

## Jobs to be done

Users need to:

- define assets declaratively
- build assets repeatedly and predictably
- enforce platform and studio constraints
- inspect what happened during a build
- repair failures without starting over manually
- switch between fallback, local, and hosted generation backends without rewriting source

## Product goals

Lathe 1.0 goals:

- make Lathe source the primary authoring surface for assets
- compile Lathe source into certifiable production artifacts
- keep the public language contract stable while internal backends evolve
- support both offline fallback builds and higher-quality learned builds
- provide clear diagnostics, provenance, and repair semantics
- enable trustworthy automation by humans and agents

## Non-goals

Lathe 1.0 is not trying to be:

- a general DCC replacement for arbitrary manual sculpting workflows
- a scene/layout generator for full worlds
- a gameplay scripting language
- a shader graph language
- a prompt-only creative toy

## Core product requirements

### 1. Language and source model

Lathe must provide:

- a stable textual language
- a normalized machine-readable AST
- deterministic parsing and normalization
- stable declaration kinds for assets, variants, profiles, contracts, critics, and build stages

Requirements:

- source must remain diffable and reviewable
- language semantics must be preserved across backend changes
- canonical defaults must reduce ambiguity

### 2. Standalone asset compilation

Lathe must support end-to-end compilation of assets through:

- intent
- shape
- topology
- UV
- surface
- rig/interfaces/physics as applicable
- optimize
- validate
- repair
- package
- publish hooks

Requirements:

- each stage must have explicit inputs/outputs
- each stage must emit traceable artifacts
- builds must return a clear pass/fail result

### 3. Shape generation and reconstruction

Lathe must support:

- `generate`
- `reconstruct`
- `adapt`
- `assemble`

Requirements:

- multiple candidates when appropriate
- controllable fidelity and repair posture
- support for text-only, image-conditioned, mesh-conditioned, and hybrid modes
- preservation of parts, symmetry, proportions, and interfaces where requested

### 4. Deterministic downstream quality

Lathe must provide robust deterministic downstream stages for:

- topology cleanup and retopology
- UV generation including lightmap UVs
- collision generation
- pivots, sockets, and anchors
- optimization and LOD derivation
- packaging/export

Requirements:

- downstream stages must preserve backward-compatible bundle contracts
- fallback behavior must be explicit, never hidden
- quality gates must reject outputs that violate the contract

### 5. Validation and repair

Validation is core product surface, not optional tooling.

Lathe must support:

- explicit `ensure` constraints
- critic/prefer scoring
- certification thresholds
- repair policy and permitted repairs

Requirements:

- repairs must be concrete and traceable
- the system must distinguish between reselect, repair, and regenerate
- a certified build must mean contract-compliant output

### 6. Packaging and exports

Lathe must emit:

- target formats such as `usd` and `glb`
- manifests
- traces
- previews
- normalized-source references

Requirements:

- package outputs must be deterministic once authoritative upstream artifacts are selected
- build outputs must be reviewable and reproducible

### 7. Provenance and reproducibility

Lathe must track:

- source hashes
- normalized hashes
- refs consumed
- selected and attempted providers/backends
- stage execution metadata
- repairs applied
- output hashes

Requirements:

- provenance must survive fallback paths
- users must be able to tell what actually ran

### 8. Runtime accessibility

Lathe must support multiple runtime modes:

- offline fallback
- local learned providers
- hosted or external providers
- hybrid flows

Requirements:

- capability detection must be explicit
- runtime availability must be diagnosable
- inaccessible runtimes must not be represented as functioning

## User stories

### Story 1: Offline local build

As a solo developer, I want to write a Lathe file and build it locally without any hosted AI dependency so I can iterate anywhere.

Acceptance:

- default build works offline
- fallback generation remains available
- outputs package and certify where expected

### Story 2: High-quality learned reconstruction

As a user with a local reconstruction runtime, I want Lathe to use it explicitly and show me whether it truly ran, so I can trust the outputs and traces.

Acceptance:

- provider selected explicitly by config
- actual provider recorded in trace
- fallback, if any, is explicit

### Story 3: Enforced production constraints

As a technical art lead, I want asset contracts encoded in source so all builds are checked against the same standards.

Acceptance:

- validation rules are declared in Lathe
- failures are machine-readable
- repairs follow declared policy

### Story 4: Backend swap with stable source

As a platform owner, I want to upgrade the internal shape or deterministic backends without rewriting Lathe source.

Acceptance:

- public source semantics remain stable
- internal backend changes preserve bundle contracts

## Functional requirements

### Compiler and CLI

- parse, normalize, check, plan, materialize, build, doctor, and provider/backend probing
- machine-readable CLI outputs
- stable runtime configuration handling

### Shape runtime

- candidate generation and selection
- explicit provider selection
- actual versus attempted provider reporting
- safe retries and diagnostics where network or hosted paths are used

### Topology runtime

- deterministic cleanup
- topology quality gates
- watertight/manifold repair strategies
- part-group preservation or recovery

### UV runtime

- base UV generation
- lightmap UV support
- texel-density reporting
- explicit adapter reporting

### Validation runtime

- rule evaluation
- critic evaluation
- certification result
- diagnostics and suggested repairs

## Non-functional requirements

- builds must be inspectable
- diagnostics must be high-signal
- source and output semantics must be stable
- fallback behavior must be explicit
- local setups must be diagnosable and bootstrap-friendly
- the system must be automatable by agents without hidden state

## Research requirements

The research team should prioritize:

- learned shape generation that preserves semantic structure
- robust post-generation geometry repair
- part-aware topology recovery
- validation-guided iterative repair
- material and surface generation aligned with semantic intent
- reproducible and traceable candidate selection

The research mandate is not “make a model generate a mesh.”

It is “make Lathe compile assets that pass real production contracts.”

## Evaluation framework

Lathe should be evaluated on:

- certification pass rate
- topology validity rate
- UV validity rate
- runtime budget compliance
- repair success rate
- trace fidelity
- asset-family coverage
- reduction in manual cleanup
- acceptance in downstream pipelines

The key metric is not “looks cool.”

The key metric is “passes contract and is usable.”

## Release milestones

### Milestone 1: Reliable fallback compiler lane

- stable language surface
- deterministic fallback generation
- robust validation
- packaging and trace output

### Milestone 2: Real local deterministic stages

- strong topology cleanup
- real UV adapter
- reliable local doctor/bootstrap workflows

### Milestone 3: First true learned lanes

- explicit reconstruction provider that certifies on representative assets
- explicit generate provider path
- attempted versus actual runtime tracing

### Milestone 4: Autonomous repair loop

- repair planning
- bounded iterative repair execution
- certification-driven convergence

### Milestone 5: Standalone Lathe compiler

- first-party generation stack
- strong fallback and learned parity
- practical asset-family breadth
- CI-friendly production readiness

## Open questions

- What is the minimum first-party capability set needed for Lathe to be credibly standalone?
- How much of standalone generation should be learned versus procedural versus hybrid?
- What public language surface is stable enough to expose now versus later?
- Which asset families should define the initial “production-ready” benchmark set?
- What is the right balance between explicit user control and autonomous repair/reselection?

## Success criteria for the research team

The research team should consider Lathe successful when:

- a user can author assets as Lathe source
- the system can build and certify representative production assets
- the build trace truthfully captures what happened
- backend improvements do not require source rewrites
- manual cleanup is materially reduced
- teams can trust the build result as a real production signal

## Requirement status (v0.2.0rc1)

This section tags every requirement above against the actual state of the code on the v0.2.0rc1 release branch (base commit `30f9186`). Status legend:

- `supported` — code path is shipped, exercised by tests/CI, documented, and safe to recommend for the conservative offline build.
- `preview` — code path is shipped and tested at smoke-test depth; rough edges remain; suitable for early adopters who tolerate breakage and report bugs.
- `experimental` — code path is shipped behind opt-in runtime config; depends on optional tools / external services; failures are expected and traceable, not silent.
- `future` — not in 0.2.0rc1; tracked on the roadmap; do not claim or ship.
- `rejected` — explicitly out of scope; will not ship in this product.

If a requirement has no test or doc evidence, it is marked `gap:` and is currently a documentation hole that the readiness pass must close or accept as an exception.

### 1. Language and source model

| Sub-requirement | Status | Evidence |
|---|---|---|
| Stable textual language (`.lth`) | `supported` | `grammar/lathe.lark`, `spec/lathe-v0.1.md`, `tests/test_language_v08.py`, `tests/test_language_v13.py` |
| Normalized machine-readable AST | `supported` | `schema/lathe.schema.json`, `lathe/normalizer.py`, `tests/test_lathe.py` |
| Deterministic parsing and normalization | `supported` | `lathe/parser.py`, `lathe/normalizer.py`, `tests/test_roundtrip.py` |
| Stable declaration kinds (asset, variant, profile, contract, critic, stage) | `supported` | `docs/language_reference.md`, `tests/contract/test_stable_backend_contracts.py` |
| Diffable, reviewable source | `supported` | grammar is line-oriented; `examples/*.lth` checked into repo |
| Semantics preserved across backend changes | `supported` | `tests/contract/test_shape_handoff_v1.py`, `docs/adr/0001-shape-handoff-contract.md` |
| Canonical defaults reduce ambiguity | `supported` | `lathe/defaults.py`, `lathe/normalizer.py` |
| `fmt` canonical formatter | `future` | gap: no `lathe fmt` subcommand exists; tracked as scaffold limitation in `CLAUDE.md` |

### 2. Standalone asset compilation

| Sub-requirement | Status | Evidence |
|---|---|---|
| End-to-end compile through stage pipeline | `supported` (hero families) | `lathe/executor.py`, `STAGE_ORDER`, `tests/golden/test_hero_bundles.py` |
| Each stage has explicit inputs/outputs | `supported` | `docs/architecture/pipeline.md`, `docs/architecture/stage_contracts.md` |
| Each stage emits traceable artifacts | `supported` | `tests/golden/test_artifact_contract_snapshots.py`, build trace manifest |
| Builds return clear pass/fail | `supported` | `tests/test_build.py`, `lathe check`/`lathe build` exit codes |
| `publish` runner | `preview` | `lathe/publish/__init__.py` ships local_fs/s3/supabase/git_lfs drivers; CLAUDE.md lists publish as scaffold; signing skipped when key/lib absent |
| Multi-round autonomous repair loop | `future` | gap: CLAUDE.md explicitly notes "full multi-round autonomous repair loops are intentionally still scaffolds" |

### 3. Shape generation and reconstruction

| Sub-requirement | Status | Evidence |
|---|---|---|
| `generate` flow | `supported` (fallback) | `examples/courier_drone.lth`, hero examples, `lathe/shape_backend.py` |
| `reconstruct` flow | `preview` | reconstruct example exists; certification thresholds vary by example |
| `adapt` flow | `preview` | `lathe/fit_ir.py`, V1.1 docs; less test coverage than generate |
| `assemble` flow | `preview` | `lathe/assembly_kernel.py`, hero `brassbound_chest` exercises assembly |
| Multiple candidates when appropriate | `supported` | shape provider mux returns candidates, `tests/test_shape_providers.py` |
| Controllable fidelity and repair posture | `preview` | repair policy declarations parse and route; bounded loop is `future` |
| Text/image/mesh-conditioned modes | `preview` | reference-conditioned fallback ships; learned conditioning is `experimental` |
| Symmetry/proportions/interfaces preservation | `preview` | `lathe/conformance.py`, semantic validators; quality varies by family |

### 4. Deterministic downstream quality

| Sub-requirement | Status | Evidence |
|---|---|---|
| Topology cleanup / retopology | `supported` (with explicit fallback) | `lathe.topology.blender_hard_surface_v1` attempted; deterministic ref path actual when Blender absent; `docs/adr/0002-blender-and-xatlas-fallback-policy.md` |
| UV generation including lightmap UVs | `supported` (with explicit fallback) | `lathe.uv.xatlas_v1` attempted; deterministic box atlas actual when xatlas absent |
| Collision generation | `supported` | `lathe/validators/`, packaging emits collision metadata for hero examples |
| Pivots/sockets/anchors | `supported` | hero examples define and emit sockets; `tests/golden/test_hero_bundles.py` |
| Optimization and LOD derivation | `preview` | LOD derivation present but coverage is family-dependent |
| Packaging/export | `supported` | `lathe.package.openusd_gltf_v1`, `tests/golden/test_artifact_contract_snapshots.py` |
| Backward-compatible bundle contracts | `supported` | `docs/adr/0009-public-contract-index.md`, `tests/contract/` |
| Explicit fallback (never hidden) | `supported` | attempted-vs-actual recorded in trace; `docs/architecture/backends.md` |

### 5. Validation and repair

| Sub-requirement | Status | Evidence |
|---|---|---|
| Explicit `ensure` constraints | `supported` | parser/normalizer accept; checker enforces |
| Critic / `prefer` scoring | `supported` | `lathe/validators/`, `tests/test_semantic_quality.py`, `tests/test_visual_quality.py` |
| Certification thresholds | `supported` | per-family thresholds in `examples/*.lth`; visual/semantic/flow validators |
| Repair policy and permitted repairs | `preview` | repair declarations parse; bounded multi-round loop `future` |
| Repairs are concrete and traceable | `preview` | trace records single-pass repairs; multi-round trace is `future` |
| Distinguish reselect / repair / regenerate | `preview` | logic exists in shape mux; documentation thin |

### 6. Packaging and exports

| Sub-requirement | Status | Evidence |
|---|---|---|
| Target formats (`usd`, `glb`, `gltf`, `obj`) | `supported` | `lathe/package/`, `tests/golden/test_hero_bundles.py` |
| Manifests | `supported` | package + trace manifests; `schema/publish_manifest.schema.json` |
| Traces | `supported` | `lathe/executor.py` writes trace artifacts |
| Previews | `supported` | preview renders for hero families |
| Normalized-source references | `supported` | resolved AST + source hash in manifest |
| Deterministic outputs | `supported` (caveat: shape stage stochastic) | `docs/deterministic_builds.md`; downstream stages deterministic once shape selected |

### 7. Provenance and reproducibility

| Sub-requirement | Status | Evidence |
|---|---|---|
| Source/normalized hashes | `supported` | recorded in trace manifest |
| Refs consumed | `supported` | recorded in trace manifest; `examples/refs/` |
| Selected and attempted providers/backends | `supported` | attempted-vs-actual fields; `docs/architecture/backends.md` |
| Stage execution metadata | `supported` | per-stage trace entries |
| Repairs applied | `preview` | single-pass recorded; multi-round `future` |
| Output hashes | `supported` | manifest records artifact hashes |
| Provenance survives fallback paths | `supported` | by design; `docs/adr/0001-shape-handoff-contract.md` |
| Signed reproducibility receipts | `preview` | `lathe/publish/signed_repro.py` ships; signing skipped when key/library absent |

### 8. Runtime accessibility

| Sub-requirement | Status | Evidence |
|---|---|---|
| Offline fallback | `supported` | default path; no runtime config required |
| Local learned providers (VGGT) | `experimental` | `examples/runtime_configs/vggt_local.json`; requires local model/runtime install |
| Hosted/external providers (Hunyuan HTTP) | `experimental` | `examples/runtime_configs/hunyuan_http.json`; requires reachable HTTP service |
| Hybrid (auto-learned routing) | `preview` | `examples/runtime_configs/auto_learned.json` |
| Capability detection (`lathe doctor`) | `supported` | `lathe/cli/`, `tests/test_doctor.py` |
| Runtime availability diagnosable | `supported` | doctor output, attempted-vs-actual trace |
| Inaccessible runtimes not faked as functioning | `supported` | fallback is explicit; `docs/release/known-limitations.md` defects list forbids hidden fallback |

### Distribution, GTM, and surrounding capabilities

| Capability | Status | Evidence |
|---|---|---|
| PyPI package availability | `future` | `0.2.0rc1` bumped in `pyproject.toml`; PyPI Trusted Publishing not yet configured (`requires-human`) |
| Godot AssetLib listing | `future` | tracked as `plan_completeness.md` GTM-5 / BL-44; Godot integration code present, listing not submitted |
| Hosted asset registry | `future` | tracked for V0.8 in `docs/roadmap_public.md`; not in 0.2.0rc1 |
| CI certification SaaS | `future` | tracked for V1.0 in `docs/roadmap_public.md`; not in 0.2.0rc1 |
| Pyodide / browser playground | `future` | not in 0.2.0rc1 |
| Public benchmark with raw data | `future` | benchmarks exist (`tests/test_benchmarks.py`, `lathe bench`); public publication of raw data is V0.5 |
| Telemetry — opt-in event collection | `preview` | `docs/telemetry.md` exists; live dashboards `requires-human` per evidence packet |
| Discord community | `future` | not launched; moderation owner not named; tracked in GTM backlog |
| Design-partner LOIs | `future` (`requires-human`) | none signed; tracked for V0.3 in `docs/roadmap_public.md` |
| Soft-surface stack (`soft_surface_prop_v1`) | `future` | second backend stack tracked for V1.0; only `hard_surface_game_asset_v1` ships now |
| Full mypy strict | `future` | mypy runs in CI but not strict-mode across the codebase |
| Python 3.13 / 3.14 support | `rejected` | `requires-python = ">=3.11"`; 3.13+ unsupported per `docs/release/support-matrix.md` |

## Final product statement

Lathe should become the programming language and compiler for production 3D assets.

Not a prompt wrapper.
Not a model demo.
Not a mesh toy.

A real system that turns intent into certifiable asset builds.

For v0.2.0rc1, that mission is partially realized in the conservative offline lane on the hero families. Anything beyond that — learned parity, hosted services, GA claims — is roadmap, not release.
