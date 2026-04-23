# Lathe repository guidance

## What this repository is
Lathe is a declarative, end-to-end 3D asset language. The repository contains the v0.1 language contract, the reference compiler scaffold, the backend registry, and the first runnable asset pipeline.

## Working agreements
- Preserve public Lathe source compatibility unless the task explicitly requests a language change.
- Keep the stable shape-stage contract at `lathe.shape.intent_mesh_handoff_v1` unless the task explicitly requests a migration plan.
- Treat `profile`, `contract`, `critic`, `asset`, `variant`, and the build-stage names as public language surface.
- Prefer small, localized changes over broad rewrites.
- When a change affects public behavior, update the most relevant docs and add or update tests.

## Change rules by area
### Language contract changes
If you change the language contract, update all relevant layers together:
- `spec/lathe-v0.1.md`
- `grammar/lathe.lark`
- `schema/lathe.schema.json`
- parser / normalizer / resolver / checker behavior
- examples and tests

### Backend and provider changes
If you change backend or provider behavior:
- preserve stable backend IDs unless the task explicitly requests a migration
- preserve the shape bundle contract and trace fields
- keep downstream topology, UV, and packaging contracts stable unless the task explicitly broadens them
- prefer mocked tests for external services

### Example asset changes
When editing examples:
- keep at least one runnable `generate` example
- keep at least one runnable `reconstruct` example
- keep example refs minimal and checked into `examples/refs/`
- ensure examples still pass the current checker and build path

## Canonical commands
Use `python -m lathe.cli` from the repository root unless the editable install is already active.

Primary commands:
- `python -m lathe.cli normalize examples/courier_drone.lth`
- `python -m lathe.cli check examples/courier_drone.lth`
- `python -m lathe.cli plan examples/courier_drone.lth courier_drone`
- `python -m lathe.cli materialize examples/courier_drone.lth courier_drone_mobile`
- `python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist`
- `python -m lathe.cli shape-providers`
- `python -m lathe.cli probe-providers --runtime-config examples/runtime_configs/auto_learned.json`
- `python -m pytest -q`

Helper scripts:
- `scripts/lathe_asset_loop.sh <file.lth> <asset_name> [out_dir]`
- `scripts/lathe_smoke.sh`

## Repository map
- `lathe/parser.py` parses source and resolves relative refs
- `lathe/normalizer.py` inserts canonical defaults
- `lathe/resolver.py` applies `uses` chains and variant patches
- `lathe/checker.py` enforces semantic rules and backend compatibility
- `lathe/planner.py` emits effective build plans
- `lathe/backends.py` defines backend contracts, stacks, and provider registry hooks
- `lathe/shape_backend.py` owns the stable shape-stage contract
- `lathe/shape_providers.py` holds learned and fallback provider adapters
- `lathe/executor.py` runs the deterministic downstream runtime
- `tests/` contains regression coverage for language, backends, build, and provider seams

## Review checklist
Before finishing a change:
- run the narrowest relevant check first
- then run `python -m pytest -q` if behavior changed
- confirm examples or fixtures still reflect current behavior
- call out any remaining scaffold limitations rather than implying they are complete
