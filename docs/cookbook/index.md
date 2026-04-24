# Cookbook

Runnable, end-to-end recipes for the most common Lathe authoring flows. Each recipe references a real `.lth` source in [`examples/`](https://github.com/talmerri/lathe/tree/main/examples) or `std/`, walks through the commands needed to exercise it, and highlights the knobs worth tweaking.

If you are brand new to Lathe, start with the [Quickstart](../quickstart.md) and [Author your first `.lth` asset](../tutorial/first_asset.md) tutorial, then come back here.

## Primary recipes

| # | Recipe | Flow | Example used |
|---|---|---|---|
| 1 | [Generate flow](01_generate_flow.md) | `mode = generate` | `examples/courier_drone.lth` |
| 2 | [Reconstruct flow](02_reconstruct_flow.md) | `mode = reconstruct` + `reference_set` | `examples/reconstruct_courier_from_views.lth` |
| 3 | [Kit assembly](03_kit_assembly.md) | `mode = assemble` + `library` + `kit` | `examples/service_corridor_wall.lth` |
| 4 | [Mobile adapt](04_mobile_adapt.md) | `mode = adapt` + `adapt_policy` | `examples/console_terminal_mobile_adapt.lth` |
| 5 | [Surface control (V1.2)](05_surface_control.md) | `surface_backend` + decals + masks + trims | `examples/console_terminal_v12_surface.lth` |
| 6 | [Variant patching](06_variant_patching.md) | `variant` + semantic patches | `examples/courier_drone.lth` |
| 7 | [Custom backend](07_custom_backend.md) | register a new backend | `lathe/backends.py` |
| 8 | [Runtime config](08_runtime_config.md) | Hunyuan / VGGT / auto_learned | `examples/runtime_configs/*.json` |
| 9 | [Certification debug](09_certification_debug.md) | reading validator reports | `dist/*/build_report.json` |
| 10 | [Blender bridge (V1.3.1)](10_blender_bridge.md) | `lathe bridge plan` + `inspect-blend` | `examples/brassbound_chest_v13_1_codex_blender.lth` |

## Reference pages

| # | Page | Covers |
|---|---|---|
| 11 | [Runtime config schema](runtime_config_schema.md) | fields of `schema/runtime_config.schema.json` |
| 12 | [Reading a trace](reading_a_trace.md) | `build_report.json`, attempted-vs-actual, IR fields |
| 13 | [Per-validator index](per_validator.md) | links to each `lathe/validators/*.md` page |

## How to read a recipe

Every recipe has the same shape:

1. **Goal** — one sentence on what the recipe demonstrates.
2. **Prerequisites** — Lathe version, a working `.venv`, any runtime config.
3. **Walkthrough** — copy-paste commands plus the interesting `.lth` snippets.
4. **Output** — what to expect in `dist/` (or wherever you pointed `--out`).
5. **Variations** — safe knobs to tweak and what changes.
6. **See also** — links into the spec, architecture, and tutorial pages.

All code blocks assume you have bootstrapped a local venv (see the [Quickstart](../quickstart.md)) and are running commands from the repo root. `python` in the examples means `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python` (Linux/macOS).
