# Pre-Wonder Baseline

Recorded: 2026-04-29

This is the release note for the Phase 0 baseline before Lathe moves deeper
into Project Wonder readiness work.

## Baseline Decision

Lathe remains a production-oriented asset compiler first. The Wonder layer is
allowed to add JSON-first scene contracts, scene validation, scene package
helpers, deterministic proxy rendering/export, and orchestration-friendly CLI
commands, but it must not break existing asset source compatibility or mutate
the frozen shape handoff contract.

## Evidence Summary

A Git-backed review snapshot of the current working tree passed:

- Full test suite: `1651 passed, 19 skipped, 127 deselected, 1 warning, 62 subtests passed`.
- `python -m lathe.cli doctor --json`.
- `python -c "import trimesh; print(trimesh.__version__)"`.
- `python -m lathe.cli doctor`.
- `python -m lathe.cli shape-providers`.
- `python -m lathe.cli probe-providers --runtime-config examples/runtime_configs/auto_learned.json`.
- `powershell -ExecutionPolicy Bypass -File scripts/lathe_smoke.ps1`.
- `python -m lathe.cli normalize examples/courier_drone.lth`.
- `python -m lathe.cli check examples/courier_drone.lth`.
- `python -m lathe.cli plan examples/courier_drone.lth courier_drone`.
- `python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist`.
- One canonical generate build: `examples/tutorial_bookshelf.lth`.
- One canonical reconstruct build: `examples/reconstruct_courier_from_mesh.lth`.
- `powershell -ExecutionPolicy Bypass -File scripts/lathe_wonder_validate.ps1`.

## Still Not Claimed

This baseline does not claim Project Wonder alpha readiness. The remaining
gates are POSIX helper execution, fresh-clone or CI confirmation for alpha
promotion, Blender-backed scene rendering, external export validation,
Roblox export execution, and a real vision/evaluator render-inspection loop.
