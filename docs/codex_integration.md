# Codex integration for Lathe

This repository includes a first project-scoped Codex integration pack so Codex can work on Lathe as a stable engineering surface.

## Layout

- `AGENTS.md`
  - repository-level working agreements and validation rules
- `.codex/config.toml`
  - project-scoped Codex defaults and reusable profiles
- `.codex/agents/`
  - project-scoped custom spawned agents
- `.agents/skills/`
  - repo-scoped Codex skills discovered by Codex in this repository
- `scripts/lathe_smoke.sh`
  - one-command local smoke runner: doctor, canonical check/plan, smoke pytest partition, and a throwaway build
- `scripts/lathe_smoke.ps1`
  - PowerShell equivalent for Windows-first local smoke runs
- `scripts/lathe_asset_loop.sh`
  - end-to-end asset loop for one `.lth` source and asset name
- `scripts/bootstrap_local.ps1`
  - Windows/bootstrap entry point for a repo-local virtualenv plus optional extras
- `scripts/bootstrap_local.sh`
  - cross-platform/bootstrap entry point for a repo-local virtualenv plus optional extras

## Included skills

- `lathe-new-asset`
- `lathe-build-debug`
- `lathe-backend-swap`
- `lathe-spec-change`
- `lathe-add-example`
- `lathe-certification-fix`

Use a skill explicitly from Codex when you want a narrow workflow, or let Codex match the skill implicitly from its description.

## Included custom agents

- `lathe_implementer`
  - workspace-write implementation agent for Lathe code and example changes
- `lathe_reviewer`
  - read-only review agent for contract drift, missing tests, and regression risk

## Recommended command loop

From the repository root:

```bash
python -m lathe.cli doctor
python -m lathe.cli check examples/courier_drone.lth
python -m lathe.cli plan examples/courier_drone.lth courier_drone
scripts/lathe_asset_loop.sh examples/courier_drone.lth courier_drone
bash scripts/lathe_smoke.sh
```

## Local machine flow

Recommended bootstrap:

```powershell
scripts/bootstrap_local.ps1 -Dev -Export
```

Recommended Windows smoke:

```powershell
scripts/lathe_smoke.ps1
```

Optional runtime-specific installs:

- `-XAtlas`
  - attempts to install the Python `xatlas` bindings when native build tools are available
- `-VGGT`
  - installs `torch`
  - still requires a manual source install of the official `vggt` package

Doctor is the quickest way to understand whether the local repo is in:

- fallback smoke-test mode
- real deterministic-adapter mode
- real optional-proposal-source mode

## Suggested Codex prompts

### Add a new asset

```text
Use the lathe-new-asset skill.
Create a new env_module example for a modular sci-fi wall panel.
Keep it runnable in this repo, add only minimal refs, and validate it end to end.
```

### Swap a provider implementation

```text
Use the lathe-backend-swap skill.
Keep the stable provider ID, but preserve Lathe’s assembly-first shape semantics.
Treat the provider as an optional proposal source, not the product center, and add mocked tests for the network seam.
```

### Generalize the native compiler

```text
Use the lathe-backend-swap and lathe-certification-fix skills.
Refactor the current native shape wedge into a shared hard-surface assembly kernel.
Preserve the stable shape backend ID, keep offline mode working, and tighten certification truth rather than lowering thresholds.
```

### Improve geometry quality

```text
Use the lathe-backend-swap, lathe-certification-fix, and lathe-build-debug skills.
Improve the native assembly compiler’s visible geometry quality with shared feature grammar, fidelity-aware candidate search, and honest validator calibration.
Do not optimize provider integration as the headline.
```

### Push the hero vertical slice

```text
Use the lathe-backend-swap, lathe-certification-fix, and lathe-build-debug skills.
Focus on chest, drone, and console as hero assets.
Improve integrated geometry, render-level validation, and bounded repair loops without changing the stable Lathe source contract.
```

### Change the language contract

```text
Use the lathe-spec-change skill.
Add a backward-compatible field to the normalized AST, update spec grammar schema and tests, and keep examples in sync.
```

### Fix a certification failure

```text
Use the lathe-certification-fix skill.
Investigate why an asset builds but fails certification, repair the real defect, and avoid weakening the contract unless the task explicitly changes it.
```
