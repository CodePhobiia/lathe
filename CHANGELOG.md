# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added Project Wonder Phase 0 baseline evidence and the Wonder Layer boundary
  ADR, keeping Wonder contracts additive while preserving the current asset
  compiler compatibility contract.
- Added tracked maintenance docs for issue triage, labels, milestones, stale
  handling, dependency-update review gates, release metrics, and the 10/10
  quality dashboard.
- Added release-blocker issue intake and expanded the release workflow so
  publishing waits for tests, docs, lint, package metadata, security scans, and
  SBOM generation.
- Added a generated CLI reference that is checked against live
  `python -m lathe.cli ... --help` output.
- Added runtime-config examples for offline, reference-only, mocked learned,
  and real learned-provider modes, with tests that keep the examples loadable
  and documented.
- Hardened outbound HTTP so network egress requires an explicit host
  allowlist, including provider, telemetry, and Supabase publish paths.

## [0.2.0-rc.1] - 2026-04-25

21 commits across six sub-waves (Wave 6.I–VI) covering every V0.2 epic
from `docs/next_version_roadmap.md` except **OPS-1** (push to the public
GitHub remote, which requires a human credentialed action).

### Added

- **Robust CSG kernel (E2 GEO-1…8):** `lathe.geometry` subpackage with a
  `GeometryKernel` Protocol + registry. `lathe.geometry.manifold_v1` (via
  `manifold3d`) becomes the default CSG kernel; `lathe.geometry.reference_v1`
  is the deterministic fallback. Scaffold compiler re-fuses via Manifold
  CSG when SDF fusion falls back. `courier_drone` watertight_rate goes
  from 0.0 → 1.0. New `evaluate_geometry_integrity` validator wraps
  self-intersection (L6201), normal-consistency (L6202), and opt-in
  body-count-stability (L6203) checks, with 5 pinned synthetic scenes
  under `tests/golden/test_geometry_fixtures.py`.
- **Real game-ready stages (E3 STAGE-1…12):** QEM LOD decimation with
  `lod_manifest.json` (STAGE-1), trimesh convex-hull collision proxies
  for asset + parts (STAGE-2), typed sockets with `socket_type` enum
  (STAGE-3), typed pivots with `pivot_type` enum (STAGE-4), anchor
  catalog in `docs/anchor_catalog.md` + globally-unique `anchor_id`
  enforcement (STAGE-5), texture-memory + material-count + draw-call
  budget enforcement with L6301/L6302/L6303 diagnostics (STAGE-7/8),
  LOD distance thresholds + `screen_coverage` hints (STAGE-9), per-engine
  manifest emitters for Godot / Unity / Unreal (STAGE-10), opt-in URDF
  validator for robotics intent (STAGE-11), and the 16-entry gameplay-tag
  catalog in `docs/gameplay_tags.md` (STAGE-12).
- **`@lathe[…]` reference surface (E1 REF-1…14 + Phase 2):** grammar +
  parser + resolver for whole-build / asset / variant / stage / diagnostic
  / part selectors (Phase 1), plus face / edge / vertex selectors
  (Phase 2). `selector_manifest.json` sidecar written by the package
  stage (REF-5) with buildHash-based stale-ref warnings (REF-7).
  `lathe ref parse | inspect | planes | diff | copy` CLIs. Docs in
  `docs/refs.md`.
- **Reports v2 (E4 RPT-1…5):** HTML + terminal reports extended with
  Refs / Geometry Kernel / LOD Ladder / Collision Proxies sections.
  `--deterministic` flag yields byte-identical JSON output. `lathe
  snapshot` + `lathe diff` CLIs consume and compare a new
  `.lathe_snapshot.json` contract validated by
  `schema/lathe_snapshot.schema.json`.
- **Godot editor integration (E6 ENG-2…6):** `EditorImportPlugin` for
  `.lathe_snapshot.json` (ENG-2), thumbnail auto-regen on sidecar mtime
  (ENG-3), dockable Build-Trace Viewer (ENG-4), fsnotify watcher (ENG-5),
  certified-state indicator in the editor bottom bar (ENG-6). Addon lives
  in `editors/godot/lathe-addon/`.
- **Compiler corpus + example library (E11 BENCH-NEW-1/2/7):** `examples/
  api/` (6 files) + `examples/corpus/` (10 files) + nightly example-build
  CI matrix + `tests/unit/test_example_corpus.py` parametrized smoke.
- **User cache + CLI (E15 PERF-1/2/4):** build cache relocated from the
  system tmp directory to `~/.cache/lathe` (platformdirs + platform
  fallbacks). New `lathe cache status | clean | warm` CLI. Hand-authored
  per-hero per-stage perf budgets in `perf/manifest.json` consumed by
  `scripts/profile_heroes.py`.

### Security

- **Path hardening (SEC-1):** `lathe/paths.py::safe_resolve` rejects
  absolute paths, `..` traversal, symlinks (opt-in), NUL bytes, Windows
  reserved names (CON/PRN/AUX/NUL/COM1–9/LPT1–9), 8.3 short names,
  trailing-dot/space, alternate data streams, `\\?\`/`\\.\` extended-length
  prefixes, reparse points. Wired into `--out` (with
  `LATHE_ALLOW_EXTERNAL_OUT=1` escape hatch) and parser ref resolution.
- **Binary parser hardening (SEC-2):** `lathe/mesh_ingest.py::safe_load_mesh`
  enforces a 256 MiB default cap, format allowlist
  (`.glb/.gltf/.obj/.ply/.stl`), magic-byte sniff, post-load NaN/face-count
  sanity, and narrow exception remapping to `ShapeMeshLoadError`.
- **Provider-output sandbox (SEC-NEW-1):** provider-produced meshes now
  flow through `safe_load_mesh`.
- **CI security gates (SEC-3/4/5):** gitleaks (push + PR + weekly history
  sweep + issue-on-finding), CycloneDX SBOM on push-to-main + release tag,
  CodeQL Python (security-extended), Bandit (MEDIUM threshold + justified
  skip list), Semgrep (`p/python` + `p/security-audit` + `p/owasp-top-ten`).
  Bandit + gitleaks also run in pre-commit. Docs at
  `docs/security/ci_gates.md`.
- **Threat model + Blender sandbox (SEC-6/7):** STRIDE analysis over
  parse / runtime / provider / Blender / cache / publish in
  `docs/security/threat_model.md`. Blender invocations now route through
  `lathe/sandbox/blender.py` (per-host CPU + memory caps, structured
  result).
- **`.lth` prompt-injection scanner (SEC-8):** pre-parse regex sweep for
  injection patterns (ignore-previous, `<|im_start|>`, Unicode direction
  overrides, oversized literals) emitting L7001..L7005. Warnings by
  default; `--strict-prompt-injection` upgrades to errors.
- **Signed reproducibility receipts (SEC-NEW-2):** ed25519-signed
  `reproducibility_receipt.json` with signer + timestamp + env fingerprint
  (python/git/manifold3d versions). `lathe publish sign` + `lathe publish
  verify` CLIs.

### Changed

- Default CSG kernel flipped to `lathe.geometry.manifold_v1` (hero-wide
  watertight_rate jumps; fallback to reference kernel when `manifold3d`
  is unimportable).
- `validate_report` now carries per-validator diagnostics as a sibling
  (`report.validators[name].diagnostics`) *and* embedded in the flattened
  per-validator subtree for downstream compatibility.
- STAGE-12 unknown-gameplay-tag diagnostic (L6410) fires as a warning in
  V0.2 — upgrade to error via `asset.build.strict_gameplay_tags=true`
  (V0.3 default flip planned as a follow-up).

### Contract-stability

- Stable `lathe.shape.intent_mesh_handoff_v1` handoff preserved end-to-end
  (contract test pins the SHA-256). Selector manifest is `schemaVersion:
  1`. Snapshot is `schemaVersion: 1`. Budget manifest is `schemaVersion:
  1`. Reproducibility receipt is `schemaVersion: 1`. Collision manifest
  is `schemaVersion: 1`.

### Fixed

- `core/stages/validate.py` no longer raises `KeyError: 'diagnostics'` on
  hero builds (BL-45).
- GEO-5 self-intersection detector now uses position-based adjacency
  bucketing instead of index-based `face_adjacency`, eliminating spurious
  warnings from seam-split vertices.
- Texture memory budget defaults tuned (128 MiB) + channel-aware bpp
  estimation covers BC7 / BC5 / BC1 distinctions.

## [0.1.0] - 2026-04-24

Initial public scaffold of the Lathe reference compiler, landed as a four-commit
Wave 0 foundation on branch `main` and tagged `v0.1.0`.

### Added

- **chore: repo scaffolding, governance, and plans** — `.gitignore`,
  `.gitattributes`, `LICENSE` (Apache-2.0), stub `CHANGELOG.md`,
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CITATION.cff`,
  `pyproject.toml`, the `plans/` directory (10 amended implementation plans +
  execution waves), `.codex/`, `.agents/`. The `external/vggt/` directory is
  ignored rather than vendored; fetch instructions live in
  `docs/providers/vggt.md` per the custom Meta VGGT License.
- **feat: lathe v0.1 reference compiler** — `lathe/` (parser, normalizer,
  resolver, checker, planner, executor, shape/topology/uv/surface/validate/
  package stages, providers, backends, Blender bridge), `cli/` stub,
  `grammar/lathe.lark`, `schema/lathe.schema.json`, `spec/lathe-v0.1.md`,
  `AGENTS.md`, `CLAUDE.md`.
- **feat: stdlib, examples, and docs** — `std/` V0.8→V1.3.1 authoring layer
  (families, components, materials, patterns, surface_programs, palettes,
  repair, spaces, benchmarks, kits, libraries, mechanisms, policies),
  `examples/` (hero families plus generate + reconstruct runnable examples),
  `docs/`, `README.md`.
- **test: pytest suite, smoke scripts, CI seed** — `tests/` pytest suite,
  `scripts/` (bootstrap, smoke, asset loop, Blender adapters, VGGT probe),
  seeded `.github/` directory for the CI workflows landed in Wave 1.

### Security

- Stable shape-stage contract ID `lathe.shape.intent_mesh_handoff_v1` treated as
  public; any change requires a coordinated spec+grammar+schema+parser+
  normalizer+resolver+checker PR plus explicit migration notes.
