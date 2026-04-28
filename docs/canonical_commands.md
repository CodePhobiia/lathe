# Canonical Commands

Use `python -m lathe.cli` from the repository root unless an editable install
is already active and you intentionally want the `lathe` console script.

## Core Asset Loop

```bash
python -m lathe.cli normalize examples/courier_drone.lth
python -m lathe.cli check examples/courier_drone.lth
python -m lathe.cli plan examples/courier_drone.lth courier_drone
python -m lathe.cli materialize examples/courier_drone.lth courier_drone_mobile
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
```

`normalize` shows the canonical AST, `check` reports semantic diagnostics,
`plan` shows the effective build graph, `materialize` shows resolved asset or
variant data, and `build` writes the stage bundles plus package outputs.

## Cache

```bash
python -m lathe.cli cache status --json
python -m lathe.cli cache clean --asset courier_drone --dry-run
python -m lathe.cli cache warm examples/courier_drone.lth courier_drone
```

Run cache cleanup with `--dry-run` first. Add `--yes` only after reviewing the
entries that will be removed.

## Providers And Backends

```bash
python -m lathe.cli backends
python -m lathe.cli shape-providers
python -m lathe.cli probe-providers --runtime-config examples/runtime_configs/offline.json
python -m lathe.cli probe-blender
python -m lathe.cli doctor
```

Provider commands report what is selected, available, and explicitly falling
back. Runtime configs that use remote providers must include an explicit URL
allowlist.

## Diagnostics And Reports

```bash
python -m lathe.cli --debug-traceback check examples/courier_drone.lth
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist --report json
python -m lathe.cli explain dist/courier_drone
python -m lathe.cli explain-fit dist/courier_drone
```

Use `--debug-traceback` only when debugging Lathe internals. For automation,
prefer `--report json` and key off stable `code`, `diagnostics`, and
`next_step` fields instead of prose.
