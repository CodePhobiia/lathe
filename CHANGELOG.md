# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

### Contract-stability

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
