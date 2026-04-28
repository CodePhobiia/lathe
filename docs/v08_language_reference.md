# Lathe V0.8 Language Reference

V0.8 expands Lathe from an asset-only declaration surface into a reusable authoring language.

## New top-level declarations

- `family`
- `component`
- `assembly`
- `trait`
- `mechanism`
- `material`
- `palette`
- `repair_policy`
- `fixture`
- `test`
- `benchmark`
- `space`

## New asset-level blocks

- `geometry`
- `features`
- `surface`
- `assembly`
- `space`
- `repair_policy`

These blocks are additive. Existing pre-V0.8 `asset { intent/build/validate/package/publish }` source still works.

## Reusable declarations

`family` is the primary reusable authoring surface for hero hard-surface assets today. A family can carry:

- runtime family / blueprint hints
- geometry defaults
- feature grammar defaults
- surface palette/material defaults
- assembly component defaults
- default search space
- default repair policy

`component` declarations map semantic parts into source-visible authoring metadata such as:

- `part`
- `tags`
- `material_zone`
- `interface_role`
- `articulation`
- `geometry.component_type`

`material` and `palette` declarations feed the hero surface lane through resolved material definitions and palette membership.

## Search spaces

`space` declarations make candidate search visible in source. The current runtime supports:

- `vary <dimension> in <range>`
- `freeze <dimension>`
- `objective maximize|minimize <metric> weight <n>`
- `select best_of <n>`

The current native compiler lowers these into the existing V0.7/V0.8 candidate search layer.

Current directly-lowered dimensions include:

- `width_scale`
- `height_scale`
- `depth_scale`
- `feature_density`
- `panel_depth`
- `edge_weight`
- `support_spread`
- `attachment_spread`
- `trim_scale`
- `silhouette_bias`
- `rotor_guard_scale`

## Repair policy

`repair_policy` declarations are source-visible wrappers over the existing repair runtime contract:

- `mode`
- `max_rounds`
- `allow`
- `deny`

Assets can reference them through an asset-level `repair_policy` block, and the resolver lowers them into `validate.repair` for runtime compatibility.

## Tests and benchmarks

`test` declarations provide source-level assertions over materialized asset state.

`benchmark` declarations provide source-level runtime evaluation scenarios, including:

- target `asset`
- `must_pass`
- `compare_against`
- inline `assert`

`fixture` declarations are reusable inputs for benchmarks, including legacy near-miss build directories.

## CLI support

- `lathe fmt --check`
- `lathe test`
- `lathe bench`
- `lathe patch`

`lathe fmt --check` is currently a canonical parse/normalize/schema stability check, not a full text pretty-printer.

## Current examples

- [examples/brassbound_chest.lth](https://github.com/talmerri/lathe/blob/main/examples/brassbound_chest.lth)
- [examples/courier_drone.lth](https://github.com/talmerri/lathe/blob/main/examples/courier_drone.lth)
- [examples/console_terminal.lth](https://github.com/talmerri/lathe/blob/main/examples/console_terminal.lth)

These examples import reusable source declarations from the repo stdlib under [`std/`](https://github.com/talmerri/lathe/tree/main/std).
