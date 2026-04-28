# Technical design — v0.2.0rc1

**Version:** 0.2.0rc1 (pre-release reference compiler scaffold)
**Last reviewed:** 2026-04-28
**Owner:** Tal Merri (@talmerri)
**Reviewer:** requires-human (no second reviewer named yet)

This document is the release-window technical design for the v0.2.0rc1
pre-release. It is deliberately scoped to *what is shipping in this release
candidate* — not the long-horizon vision in `docs/lathe_prd.md`, not the
roadmap in `docs/roadmap_public.md`. The goal is to make the failure modes,
single points of failure, optional-tool degradation, storage posture, and
migration posture honest and inspectable before release.

For the version-neutral architecture, see
[`docs/architecture/overview.md`](overview.md).

## Release-supported components and their failure modes

The table below covers every component on the v0.2.0rc1 conservative build
path plus the publish runner and optional external touchpoints. "Failure
mode" describes the most common way the component can fail in the field.
"Observable signal" is what an operator or user sees. "Recovery path" is
what to do without contacting a maintainer.

| Component | Role | Failure mode | Observable signal | Recovery path |
|---|---|---|---|---|
| Parser (`lathe/parser.py`, `grammar/lathe.lark`) | `.lth` text → raw AST | Malformed source; grammar drift | `lark.exceptions.UnexpectedToken` / `UnexpectedCharacters` with line/column | Fix source; if grammar drift suspected, delete `.lathe_lark_cache` and re-run |
| Normalizer (`lathe/normalizer.py`) | Insert canonical defaults | Unknown declaration kinds; missing canonical default for new field | `KeyError` on default lookup; checker complaint about a normalized field | File issue; pin to last known-good commit |
| Resolver (`lathe/resolver.py`) | `uses` chains, profiles, contracts, variants | Cycles; missing profile/contract; conflicting variant patches | Resolver error citing the offending block | Inspect `uses` graph; remove cycle or restore missing block |
| Checker (`lathe/checker.py`) | Semantic + backend-compatibility validation | Backend ID typos; incompatible stack/contract bindings | Pre-build failure with backend ID and reason | Correct binding; consult `docs/architecture/backends.md` |
| Planner (`lathe/planner.py`) | Effective build plan emission | Plan inconsistency between resolved AST and stack | Plan-emit error before executor runs | Re-run with `lathe plan` for human-readable plan; report bug if plan disagrees with declarations |
| Executor (`lathe/executor.py`) | Drives `STAGE_ORDER` | Stage-body raise; per-stage timeout; trace-write failure | Stage-level error with stage name and stage contract ID; partial trace artifact | Re-run with logging; inspect `dist/<asset>/trace/` for partial artifacts |
| Shape backend (`lathe/shape_backend.py`, `lathe.shape.intent_mesh_handoff_v1`) | Authoritative mesh under stable contract | Provider raise / candidate-rejection cascade | Trace records `attempted` provider and `actual` fallback (`reference_conditioned_v1`) | Default fallback runs automatically; inspect provider report; opt out of learned providers via runtime config |
| Blender topology adapter (`lathe.topology.blender_hard_surface_v1`) | Topology cleanup | Blender absent; Blender subprocess fails quality gate | Trace records `attempted=blender_hard_surface_v1`, `actual=reference topology` with reason | Deterministic ref path runs automatically; install Blender or accept fallback |
| xatlas UV adapter (`lathe.uv.xatlas_v1`) | UV unwrap | xatlas Python binding absent or raise | Trace records `attempted=xatlas_v1`, `actual=deterministic box atlas` | Box-atlas fallback runs automatically; `pip install xatlas` to enable real adapter |
| Validators (`lathe/validators/`) | Certification gates (semantic, visual, flow, surface, silhouette) | Output below threshold; validator dependency missing | Certification-failed result with per-validator scores; missing-dep warning | Inspect validator report; fix source or accept failure under expected-failure entry in `docs/examples_catalog.md` |
| Package emitter (`lathe.package.openusd_gltf_v1`) | usd / glb / gltf / obj emission | Output dir not writable; missing upstream artifact | Package-stage error with target path | Use `--out` to a writable location; verify upstream stage succeeded |
| Runtime config loader | Reads `--runtime-config` JSON | Malformed JSON; unknown provider key | JSON decode error or unknown-provider error before run | Validate JSON; consult `examples/runtime_configs/` for shape |
| CLI (`python -m lathe.cli`) | User entry point: doctor, check, plan, materialize, build, test, bench, publish, bridge, inspect, export-blend | Subcommand misuse; environment unavailable | Non-zero exit + stderr message | `lathe doctor` to diagnose env; `--help` per subcommand |
| Telemetry | Disabled-by-default opt-in event collection | N/A in default install | No signal in default install | See `docs/telemetry.md`; live dashboards `requires-human` per evidence packet |
| Cache (`.lathe_lark_cache`, build cache) | Parser cache and stage memoization | Stale or corrupt cache after grammar/code change | Confusing parse error; stale build output | Delete cache directory and re-run; CLAUDE.md notes parser cache is safe to regenerate |
| Publish runner (`lathe/publish/`) | Optional post-build upload + signed manifest | Driver target unreachable; missing ed25519 key/library | Publish manifest records `signature.skipped_reason`; driver error from `local_fs` / `s3` / `supabase` / `git_lfs` | Re-run with reachable target; install `cryptography` and configure key path; signing skip is intentional in default smoke env |

## Single points of failure

Honest list. The intent of this section is to make these visible, not to
hide them.

1. **Solo maintainer.** The product owner (Tal Merri, @talmerri) is the
   only named human responsible for v0.2.0rc1. There is no named backup
   reviewer, no on-call rotation, and no second human with commit
   authority. Bus factor: 1. `requires-human` to name a backup before
   any GA discussion.
2. **Stable shape contract `lathe.shape.intent_mesh_handoff_v1`.**
   Treated as public per `CLAUDE.md`. Every backend stack and every
   downstream consumer assumes this contract. Breaking it would invalidate
   all existing `.lth` source, all hero examples, and all packaged
   bundles. Mitigation: contract test (`tests/contract/test_shape_handoff_v1.py`)
   and explicit ADR (`docs/adr/0001-shape-handoff-contract.md`).
3. **PyPI.** When PyPI publishing is configured (currently `requires-human`),
   PyPI itself is the only distribution surface contemplated for the
   pre-release. PyPI outages or account compromise would block install. No
   mirror, no backup index. Mitigation: source install from GitHub remains
   possible.
4. **GitHub Actions.** All CI gates — fast tests, examples, docs build,
   coverage, security scans, release build — run on GitHub-hosted
   runners. A GitHub Actions outage blocks both contributor PRs and the
   release-evidence run. No self-hosted runner fallback documented.
5. **GitHub itself (repository host).** The canonical remote in `mkdocs.yml`
   is `https://github.com/talmerri/lathe`. A GitHub outage blocks issue
   triage, PR review, and release-tag creation. The repo is small enough
   to mirror, but no mirror is documented.
6. **The single backend stack `lathe.stack.hard_surface_game_asset_v1`.**
   It is the only first-party stack shipping in 0.2.0rc1. Soft-surface
   stack is `future` (V1.0). A defect in this stack affects every supported
   asset family.
7. **The single shape provider fallback `reference_conditioned_v1`.**
   When learned providers fail, this is the only conservative path. A
   defect here breaks the offline build path that the entire smoke-test
   ergonomics depend on.
8. **The single hero example owner.** Hero families
   (`brassbound_chest`, `industrial_crate`, `mechanical_door`,
   `console_terminal`, `sci_fi_wall_panel`, `service_cabinet`,
   `control_pedestal`, `supply_container`) are all owned by the solo
   maintainer. There is no external contributor with maintainer-level
   familiarity with these families.

## Optional tools and absence behavior

This section enumerates every optional dependency on the v0.2.0rc1 build
path, what degrades when it is absent, and what fallback runs. The general
rule is "explicit, never hidden" — every fallback is recorded in the
attempted-vs-actual trace fields.

| Optional tool | What uses it | Behavior when absent | Trace evidence |
|---|---|---|---|
| Blender executable | `lathe.topology.blender_hard_surface_v1` topology adapter | Falls back to deterministic reference topology cleanup. Quality is lower; shape and downstream stages still complete. | Stage trace records `attempted=blender_hard_surface_v1`, `actual=reference topology`, with reason `blender_unavailable` or quality-gate failure. |
| xatlas (Python binding) | `lathe.uv.xatlas_v1` UV adapter | Falls back to deterministic box-atlas UVs. Texel density and seam quality drop; lightmap UV slot still emits. | Stage trace records `attempted=xatlas_v1`, `actual=deterministic_box_atlas`, with reason `xatlas_unavailable`. |
| `manifold3d` (CSG kernel) | Constructive solid geometry inside the assembly kernel | Falls back to internal CSG path with reduced robustness. Hero examples that exercise CSG-heavy assembly may show seam artifacts. | Geometry-kernel selection is logged in build trace; `docs/geometry_kernel_eval.md` documents the policy. |
| `torch` + VGGT (`vggt` extra + source install) | Learned reconstruction provider, opt-in via `examples/runtime_configs/vggt_local.json` | Provider unavailable. Shape mux falls back to `reference_conditioned_v1`. Reconstruction example becomes a fallback run, not a learned run. | Trace records `attempted=vggt_local`, `actual=reference_conditioned_v1`, with reason `provider_unavailable` or specific import error. |
| Hunyuan HTTP runtime | Learned generation provider, opt-in via `examples/runtime_configs/hunyuan_http.json` | Same as above — falls back to `reference_conditioned_v1`. Network errors are surfaced explicitly via `safe_urlopen` / `NetGuardError`. | Trace records `attempted=hunyuan_http`, `actual=reference_conditioned_v1`, with HTTP-status or network-guard reason. |
| `scikit-image` | Subset of validators (visual quality / silhouette) | Affected validators degrade or skip, with explicit warning. Certification result includes `skipped` markers per validator. | Validator report records skip reason. |
| `scipy` | Subset of validators and conformance fitting | Affected paths fall back to internal numeric routines or skip with warning. | Validator report / conformance log records skip reason. |
| `cryptography` | Publish runner ed25519 signing | Publish runner returns a manifest with `signature.skipped_reason`. Build/publish still completes; manifest is unsigned. | Publish manifest's `signature` block records the skip and reason. |

## Storage posture

**Answer for v0.2.0rc1: local files only; no hosted storage shipped.**

Lathe v0.2.0rc1 does not ship with hosted storage, hosted registry, hosted
account/auth, hosted telemetry collection, or any default network sink. The
optional Hunyuan HTTP and Hyper3D / Polyhaven / Sketchfab integrations are
*provider* surfaces; they are not Lathe storage and are opt-in via runtime
config or external MCP servers, not enabled by default.

Storage surfaces actually used:

- **Build output tree.** `--out <dir>` (commonly `dist/`, but the name is a
  convention, not a fixture — see `CLAUDE.md`). Per-asset subdirectories
  hold the package, trace, manifests, previews, and validator reports.
  The `dist_*`, `tmp_*`, `warm_*`, `v05_*`, `cache_probe_*` directories at
  the repo root are transient build outputs and are explicitly excluded
  as release evidence (see `docs/release/evidence-v0.2.0rc1.md`).
- **Parser cache.** `.lathe_lark_cache/` at the repo root. Holds Lark
  parser tables. Safe to delete and regenerate.
- **Build / stage cache.** Internal memoization of stage outputs by content
  hash. See `docs/cache.md`. Local-only. Bounded by disk; no eviction
  policy beyond manual delete.
- **Publish targets (optional).** `lathe/publish/` ships drivers for
  `local_fs`, `s3`, `supabase`, and `git_lfs`. None are configured by
  default. When invoked, the runner uploads + records a signed (or
  signing-skipped) manifest.
- **Telemetry.** Disabled by default. See `docs/telemetry.md`.

There is no Lathe-operated cloud, no Lathe-operated database, no Lathe
account system, and no Lathe-operated network endpoint in v0.2.0rc1.
Operators using `s3` or `supabase` publish drivers are responsible for
their own credentials, retention, and access policy.

## Migration posture

This section documents what the v0.2.0rc1 release commits to keeping stable
versus what may evolve, for each long-lived artifact users may write
against.

### Stable contract IDs

Treated as **public** per `CLAUDE.md` and `docs/adr/0009-public-contract-index.md`.
Breaking these requires a coordinated migration with either a MAJOR version
bump or a new ID suffix (`_v2`, etc.):

- `lathe.shape.intent_mesh_handoff_v1`
- `lathe.topology.blender_hard_surface_v1`
- `lathe.uv.xatlas_v1`
- `lathe.package.openusd_gltf_v1`
- `lathe.stack.hard_surface_game_asset_v1`
- `lathe.provider.shape.reference_conditioned_v1` (the conservative fallback)

Test coverage: `tests/contract/test_stable_backend_contracts.py`,
`tests/contract/test_shape_handoff_v1.py`. See "Stable-contract test
coverage links" below.

### Package manifest (`package.manifest.json`)

Schema versioned; downstream consumers should read by schema version.
Additive fields are non-breaking; field removals or type changes are
breaking and require a manifest schema bump. The publish manifest schema
is pinned in `schema/publish_manifest.schema.json`.

### Trace manifest

Schema versioned. The attempted-vs-actual fields, per-stage entries, and
provider/backend ID slots are stable. Internal per-stage debug payloads
are NOT stable and may change between minor releases.

### Snapshot files (`tests/golden/__snapshots__/`)

Golden snapshots capture concrete byte-level output for hero bundles, CLI
help text, and artifact contracts. They are NOT a public surface — they
are an internal regression net. Snapshot updates are a normal part of
landing intentional behavior changes; consumers should not import or
diff against snapshot files.

### `.lth` source language

Stable blocks listed in `docs/versioning.md` and `spec/lathe-v0.1.md`:
`profile`, `contract`, `critic`, `asset`, `variant`, plus the build-stage
names. Additive language extensions (V0.8 → V1.3.1 layers) are designed to
be non-breaking; existing v0.1 source must continue to parse and resolve.

### Semver expectations

Current version: `0.2.0rc1`. Until `1.0.0`:

- MINOR bumps may include language additions, new backends, new providers,
  new validators, and bug fixes. They MUST NOT break stable contract IDs
  or the public language surface listed in `docs/versioning.md`.
- PATCH bumps are bug fixes and documentation only.
- Pre-release suffixes (`rcN`, `aN`, `bN`) signal "not yet GA". 0.2.0rc1
  is a release candidate for 0.2.0, NOT GA.
- `1.0.0` is gated on the engineering milestones in `docs/roadmap_public.md`
  and is `future`, not in scope for this release.

## Stable-contract test coverage links

The stable-contract surfaces above are pinned by tests in:

- `tests/contract/test_shape_handoff_v1.py` — the
  `lathe.shape.intent_mesh_handoff_v1` contract: input/output schema,
  attempted-vs-actual trace fields, fallback semantics.
- `tests/contract/test_stable_backend_contracts.py` — every public
  backend ID (`lathe.topology.blender_hard_surface_v1`,
  `lathe.uv.xatlas_v1`, `lathe.package.openusd_gltf_v1`,
  `lathe.stack.hard_surface_game_asset_v1`).
- `tests/golden/test_artifact_contract_snapshots.py` — byte-level
  artifact and manifest snapshots so contract-shape regressions are
  visible immediately.
- `tests/golden/test_hero_bundles.py` — end-to-end hero-family bundle
  output gated by snapshots.
- `tests/golden/test_cli_help_snapshots.py` — CLI surface (subcommand
  list, help text, exit codes) treated as a soft-stability boundary.

Index: [`docs/adr/0009-public-contract-index.md`](../adr/0009-public-contract-index.md)
is the canonical list of "what we treat as public." Anything not in that
index is internal and may change without notice.

For the policy behind shape handoff and provider mux, see also
[`docs/adr/0001-shape-handoff-contract.md`](../adr/0001-shape-handoff-contract.md)
and [`docs/adr/0003-provider-mux-design.md`](../adr/0003-provider-mux-design.md).
For the Blender / xatlas fallback policy, see
[`docs/adr/0002-blender-and-xatlas-fallback-policy.md`](../adr/0002-blender-and-xatlas-fallback-policy.md).
