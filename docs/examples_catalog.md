# Examples catalog

Index of every runnable `.lth` source under `examples/`. Every file parses via
`lathe check`; certification (`lathe build ... --out ...` + `validate/report.json`
`certified == True`) is tracked per-row.

Build times assume a local `.venv` with xatlas/manifold3d installed, native
shape provider, no remote runtime config.

Complexity tiers:

- **T0** — canonical hero (8+ parts, full surface program, full assembly).
- **T1** — compact variant of a hero (renamed asset, same part graph).
- **T2** — feature-focused API demo (highlights a specific language surface).

## Hero examples (top-level `examples/`)

Cert column reflects the `validate/report.json` `certified` value on a
clean local `.venv` build. Heroes marked `x` currently score below their
own threshold — they are tracked so regressions surface, but are not
expected to pass certification today.

| File | Family | Tier | Features | Build | Cert |
|------|--------|------|----------|-------|------|
| `examples/brassbound_chest.lth` | `brassbound_chest` | T0 | hero loot chest, wood+brass PBR, lid mechanism | ~45s | o |
| `examples/industrial_crate.lth` | `industrial_crate` | T0 | steel shipping crate, warning paint, latch | ~2s | o |
| `examples/mechanical_door.lth` | `mechanical_door` | T0 | env module, hinged door w/ handle | ~37s | o |
| `examples/courier_drone.lth` | `courier_drone` | T0 | quad rotor, cargo hatch, battery sockets | ~2s | o |
| `examples/console_terminal.lth` | `console_terminal` | T0 | wall console, screen + keypad | ~75s | x |
| `examples/control_pedestal.lth` | `control_pedestal` | T0 | operator pedestal, levers | ~95s | x |
| `examples/sci_fi_wall_panel.lth` | `sci_fi_wall_panel` | T0 | env wall panel + vents | ~7s | x |
| `examples/service_cabinet.lth` | `service_cabinet` | T0 | wall service cabinet w/ hinged doors | ~30s | x |
| `examples/supply_container.lth` | `supply_container` | T0 | strapped field supply box | ~42s | o |
| `examples/tutorial_bookshelf.lth` | generic | T2 | docs walkthrough — minimal features | ~3s | x |

## API examples (`examples/api/`)

One file per public-surface concept. Each is built on
`industrial_crate_family` so it certifies without configuration.

| File | Concept | Highlights | Build |
|------|---------|------------|-------|
| `examples/api/primitives.lth` | part graph + feature density | `intent.parts`, `features.density`, `assembly.components` | ~2s |
| `examples/api/csg_boolean.lth` | boolean / integration rules | `geometry.integration_rules`, `seam_classes`, `edge_classes` | ~2s |
| `examples/api/socket.lth` | typed interface sockets | `build.interfaces.sockets`, `anchors`, `clearance` | ~2s |
| `examples/api/lod_config.lth` | LOD + runtime budgets | `build.optimize.{lods, atlas, draw_calls, texture_budget}` | ~2s |
| `examples/api/material_pbr.lth` | PBR material authoring | `surface.program`, `maps`, `bakes`, `material_zones` | ~2s |
| `examples/api/variant.lth` | variant patch/append ops | `variant ... on`, `set`/`append`, layered `profile uses` | ~2s |

## Compiler corpus (`examples/corpus/`)

Small asset zoo exercising every hero blueprint. Each is a tagged rename of
the matching `examples/<hero>.lth` so it certifies via the same blueprint but
lives under an independent registry path.

| File | Base family | Category | Build | Cert |
|------|-------------|----------|-------|------|
| `examples/corpus/corpus_crate.lth` | `industrial_crate` | container | ~2s | o |
| `examples/corpus/corpus_crate_compact.lth` | `industrial_crate` | container (0.6m scale) | ~2s | o |
| `examples/corpus/corpus_chest.lth` | `brassbound_chest` | container (wood/brass) | ~45s | o |
| `examples/corpus/corpus_door.lth` | `mechanical_door` | door | ~37s | o |
| `examples/corpus/corpus_drone.lth` | `courier_drone` | vehicle / mechanical | ~2s | o |
| `examples/corpus/corpus_supply.lth` | `supply_container` | container (strap) | ~42s | o |
| `examples/corpus/corpus_terminal.lth` | `console_terminal` | interactable | ~75s | x |
| `examples/corpus/corpus_pedestal.lth` | `control_pedestal` | interactable | ~95s | x |
| `examples/corpus/corpus_wall_panel.lth` | `sci_fi_wall_panel` | decoration / env | ~7s | x |
| `examples/corpus/corpus_cabinet.lth` | `service_cabinet` | container (wall-mount) | ~30s | x |

## CI coverage

`.github/workflows/examples.yml` has three jobs:

- **check** — `lathe check` every example on PR (fast, ~2s/file).
- **build-nightly** — full build + certification on every example, runs on
  the cron schedule (and manual dispatch).
- **corpus-pytest** — runs `tests/unit/test_example_corpus.py` on every PR so
  certification regressions show up before nightly.

Artifacts uploaded: `build_report.json`, `selector_manifest.json`, and
`stages/validate/report.json` for every asset built.

## Authoring a new example

1. Pick the closest hero family in `std/families/`.
2. Copy `examples/<hero>.lth` and rename the `module`, the top-level asset,
   and the registry path. Keep `parts`, `assembly.components`, and
   `seam_classes` aligned with the family blueprint — those drive
   `part_coverage` and `adjacency_score` during certification.
3. Run `python -m lathe.cli check <file>` — must return `ok=True`.
4. Run `python -m lathe.cli build <file> <asset> --out tmp_out` and inspect
   `tmp_out/<asset>/stages/validate/report.json`.
5. Add an entry to this catalog and to `EXPECTED_CERTIFY` in
   `tests/unit/test_example_corpus.py`.
