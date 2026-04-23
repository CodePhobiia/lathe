# Review: Plan 05 — Developer Experience

## Summary
Strong, well-sequenced plan with defensible tool choices. Addresses every gap in the findings and grounds each phase in concrete repo state (verified). A few small inaccuracies, a couple of missing DX knobs (first-run UX, logging/verbose flag, seed pinning, dry-run), and the ~9-day estimate is optimistic given Phase 7 (LSP + VS Code extension) alone is 2 days and realistically longer. Overall close to 10/10 with additions below.

## Coverage vs. findings (checklist)

| Gap | Addressed? | Where |
|---|---|---|
| No lockfile / loose `>=` constraints | Yes | Phase 1 (uv.lock, `~=`) |
| No `.env.example` / env var docs | Yes | Phase 2 item 7 |
| No devcontainer / Docker | Yes | Phase 3 (Dockerfile + Dockerfile.blender + devcontainer + compose) |
| Transient `dist_*` / `cache_probe_*` clutter | Yes | Phase 2 items 5–6 (gitignore + clean_workspace) |
| 25 MB `.lathe_lark_cache` at root | Yes | Phase 2 items 5–6 |
| Manual Blender/xatlas/Hunyuan/VGGT setup | Yes | Phase 8 (install_blender, install_xatlas, provider docs) |
| `lathe doctor` unclear scope | Yes | Phase 5 (categorized output, remediation, --fix/--strict) |
| No shell completion | Yes | Phase 6 (argcomplete + --print-completion) |
| `lathe/lsp/` unclear status | Yes | Phase 7 (pygls MVP + VS Code ext) |
| No task runner | Yes | Phase 4 (Justfile + Makefile wrapper) |

Coverage: 10/10 for the findings list.

## Citations verified against actual repo

- **Transient dir count:** 94 directories matching `dist_|cache_probe_|tmp_|warm_|v05_` at root (findings said ~30 — plan says ~30 too; actual is ~3× larger). Plan's remediation still works, but update the prose.
- **`.lathe_lark_cache`:** confirmed 25,429,145 bytes (~24.3 MB). Plan's "25MB" is correct.
- **`scripts/bootstrap_local.sh`:** verified — flags `--dev --hunyuan-http --vggt --xatlas --export --skip-doctor`, creates `.venv`, upgrades pip/setuptools/wheel, assembles extras, has inline MSVC `VsDevCmd.bat` invocation for xatlas (Phase 8 item 20 correctly flags this for extraction). Also prints a VGGT note with manual clone. Plan's claim that xatlas logic is "in bootstrap_local.sh" is accurate.
- **`lathe/doctor.py`:** probes environment/packages/blender/xatlas/torch/nvidia_smi/vggt/hunyuan/shape_providers/deterministic_backends and emits a `remediation` list. Already supports `--json` (cli.py:86). Plan should acknowledge `--json` already exists rather than implying a restructure from scratch.
- **`lathe/lsp/__init__.py`:** a 31-line stub with only `build_symbol_index(program)` — no pygls, no server entrypoint. Plan correctly calls this a "stub" and scopes Phase 7 accordingly.
- **`pyproject.toml`:** verified loose constraints (`lark>=1.1`, `numpy>=1.26`, `torch>=2.11.0`, `xatlas>=0.0.11`, etc.). No existing lockfile. Plan's tightening list is accurate.
- **Scripts dir:** `bootstrap_local.{sh,ps1}`, `first_vggt_test.{sh,ps1}`, `lathe_asset_loop.sh`, `lathe_smoke.sh`, `blender_export_blend.py`, `blender_topology_adapter.py`. No install_blender/install_xatlas yet.
- **`.venv_old_broken/`:** exists at root — plan's clean_workspace should cover this; add to gitignore explicitly.

## Already-done items (plan should acknowledge, not redo)

1. **`lathe doctor --json`** already exists (cli.py:86, doctor.py:`dump_doctor_json`). Phase 5 should say "extend", not "add JSON output".
2. **Bootstrap scripts** already have `--dev`/`--export`/`--hunyuan-http`/`--vggt`/`--xatlas`/`--skip-doctor`/`--export` flags and VsDevCmd.bat orchestration. Phase 8 item 20 is *extraction*, not green-field.
3. **Remediation text** is already in `doctor.py:_remediation_steps` — Phase 5 item 13's "restructure as {check_id, severity, message, fix_command, docs_url}" is the right upgrade, but should reference the existing strings as input.
4. **`lathe doctor` + env probes** already discovers ~13 `LATHE_*` env vars in `runtime_config.py` — Phase 2 item 7 should cite `runtime_config.py:107-172` as the authoritative list (LATHE_SHAPE_PROVIDER, LATHE_SHAPE_STRICT, LATHE_HUNYUAN_BASE_URL, LATHE_VGGT_WEIGHTS, LATHE_VGGT_DEVICE, LATHE_TOPOLOGY_ADAPTER, LATHE_TOPOLOGY_STRICT, LATHE_BLENDER_PATH, LATHE_UV_ADAPTER, LATHE_UV_STRICT, LATHE_XATLAS_RESOLUTION, LATHE_CODEX_IMAGEGEN, LATHE_EXECUTION_BLENDER_STRICT). The plan's example list (`LATHE_CACHE_DIR`, `LATHE_LOG_LEVEL`) invents vars that don't exist today.
5. **No Makefile / Justfile / Taskfile / .env.example / devcontainer / docker dir** — confirmed absent, green-field is correct for Phases 3, 4.

## Tool-choice assessment

- **`uv` over Poetry/pip-tools:** defensible and correct. No `poetry.lock`, no `Pipfile`, no conflicting tooling in repo. `uv` handles Windows venv layout (`.venv/Scripts/python.exe`) cleanly — matches CLAUDE.md's Windows-first stance. Faster lockfile on CI. `uv export` fallback for pip users is the right hedge.
- **`just` over make:** good call for Windows (no tab-sensitivity, recipe args), but requires a separate install. The Makefile wrapper in item 12 is a reasonable fallback. Consider `taskfile.dev` as an alternative note; not a blocker.
- **`pygls` for LSP:** industry standard, fine.
- **`argcomplete`:** correct for argparse (current CLI is argparse, confirmed cli.py:64). Note: `argcomplete` does **not** handle PowerShell natively — the plan claims "verified on bash, zsh, fish, PowerShell" (Phase 10), but PowerShell completion needs a separate `Register-ArgumentCompleter` shim. Flag this.

## Missing DX knobs

1. **First-run onboarding UX.** No mention of: banner when `uv.lock` absent or `.env` missing (item 24 is buried; promote). Better: `lathe init` or `lathe quickstart` command that runs doctor + prints the next 3 commands.
2. **`--verbose` / `--debug` / logging defaults.** Item 23 mentions the toggle for stacktraces, but not structured logging, log levels, or a `LATHE_LOG_LEVEL` env var (which the plan invents in item 7 but never wires up). Add: `logging` config with `--verbose` and `--quiet`, JSON log mode for CI.
3. **Dry-run / plan preview.** `lathe build --dry-run` (print plan, skip IO) is missing. Useful for CI and for onboarding to understand what will happen.
4. **Reproducibility knobs (seed pinning).** CLAUDE.md says shape is the only probabilistic stage — a `--seed` flag (or `LATHE_SEED`) documented and surfaced in doctor would be a DX win and a natural fit under "reproducibility foundation."
5. **CLI help strings / `lathe <cmd> --help` UX.** No audit planned. Help strings today are terse; the `designing-clis` skill applies. Add a sub-phase: consistent help copy, examples in each `--help`, a `lathe help <topic>` meta-command.
6. **Error message inventory scope.** Item 23 greps `raise` across `lathe/`, but that's hundreds of sites. Scope it: (a) CLI boundary wrap only, (b) top-20 most-hit errors by test output. Otherwise this sub-phase dominates.
7. **Drift test for `.env.example`.** Claim is in Phase 10, but not in Phase 2. Add item 7b: CI test enumerates `os.getenv("LATHE_*")` and asserts each appears in `.env.example`.
8. **`.lathe_lark_cache` location.** Phase 2 only gitignores it. Better: move to `LATHE_CACHE_DIR` (default `${XDG_CACHE_HOME:-~/.cache}/lathe`) so it never lands at repo root.
9. **Shell completion for PowerShell.** See tool note above.
10. **`just` on Windows install guidance** (scoop/winget) missing from Phase 4.

## Feasibility (~9 days)

Optimistic. Breakdown:

- Phase 1 (1.5d) — reasonable.
- Phase 2 (0.5d) — reasonable.
- Phase 3 (1d) — tight. Blender Dockerfile + devcontainer + compose with mock service + CI green is 1.5–2d realistically, especially with Windows-host devcontainer quirks.
- Phase 4 (0.5d) — reasonable.
- Phase 5 (1d) — reasonable given doctor already has JSON.
- Phase 6 (0.5d) — possible if CLI stays argparse; migration to `click`/`typer` (item 16) is a 1–2d refactor with test churn across every subcommand. The plan conditions it on "if hand-rolled argparse" — it **is** argparse (cli.py:64). Call out the branch explicitly: either add argcomplete to existing argparse (0.5d), or migrate (2d).
- Phase 7 (2d) — optimistic. pygls server + TextMate grammar translation from Lark + VS Code extension packaging + Marketplace publish + README+gif is realistically 3–4d.
- Phase 8 (1d) — reasonable, since bootstrap already has xatlas MSVC logic.
- Phase 9 (1d) — reasonable only if error-message audit is scoped (see gap 6).

**Realistic total: ~12–13 engineer-days** for the full scope as written. The 3-parallel-track structure is sound (reproducibility+hygiene | containers+tasks | LSP+docs), but each track is slightly under-budgeted.

## 10/10 verdict

**Not quite 10/10 as written. ~8.5/10.** Blockers to lift to 10:

1. Acknowledge already-done items (doctor `--json`, existing bootstrap flags, existing env vars in `runtime_config.py`) — don't re-plan them.
2. Correct the transient-dir count (94, not ~30) and add `.venv_old_broken/` to the clean list.
3. Use the actual `LATHE_*` var list from `runtime_config.py`, not invented vars.
4. Add the missing DX knobs: first-run banner/`lathe init`, `--verbose`/logging, `--dry-run`, `--seed`, CLI help audit, `.env.example` drift test in Phase 2, move `.lathe_lark_cache` under `LATHE_CACHE_DIR`.
5. Honest PowerShell completion story (not argcomplete-native).
6. Branch Phase 6 on argparse-stay vs click-migrate with explicit day cost.
7. Rebudget to ~12 engineer-days or descope Phase 7 to LSP-only (defer VS Code extension to a v0.2 follow-up).

With those fixes, this plan is a solid path from 7/10 to 10/10 DX.
