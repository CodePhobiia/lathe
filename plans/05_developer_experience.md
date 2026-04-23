# Implementation Plan: Developer Experience 7/10 → 10/10

## Overview
Transform Lathe from "works if you know the incantations" to "clone and build a hero asset in under 5 minutes on any platform." Covers reproducibility, containerization, task automation, diagnostics, editor integration, and onboarding polish. Current repo state: 94 transient `dist_*`/`cache_probe_*`/`tmp_*`/`warm_*`/`v05_*` directories at root plus `.venv_old_broken/` — clean-up is load-bearing.

---

## Phase 1 — Reproducibility Foundation (1.5 days)

1. **Adopt `uv` as canonical toolchain.** Rationale: 10–100× faster than pip-tools, native lockfile, unified venv+Python+extras install, first-class on Windows (critical per CLAUDE.md). Poetry rejected (heavy, opinionated layout). pip-tools rejected (no unified venv story). `bootstrap_local.{sh,ps1}` already accepts `--dev --hunyuan-http --vggt --xatlas --export --skip-doctor`; extend rather than rewrite — wire `uv sync` behind the existing flags and add any new extras flags as-needed.
2. **Tighten `pyproject.toml`** — replace `>=` with `~=` or pinned upper bounds for `lark`, `jsonschema`, `numpy`, `Pillow`, `trimesh`, `torch`, `torchvision`, `xatlas`, `scipy`, `scikit-image`, `pytest`. Add `[tool.uv]` + `[dependency-groups]` for `dev`, `docs`, `ml`.
3. **Generate `uv.lock`** via `uv lock --all-extras`. Export `requirements.txt` + `requirements-dev.txt` via `uv export` for pip users.
4. **Bump policy** — monthly `uv lock --upgrade` cadence documented in `docs/dependency_policy.md`. CI job `lock-drift-check` fails PRs modifying `pyproject.toml` without updating `uv.lock`.

---

## Phase 2 — Repo Hygiene (0.5 day)

5. **`.gitignore`** — Plan 06 (Maintenance) owns `.gitignore`. Confirm it covers the patterns listed there (including `.venv_old_broken/`, `.lathe_lark_cache`, `dist_*/`, `tmp_*/`, `warm_*/`, `v05_*/`, `cache_probe_*/`, `.env`, `.vscode/*` allowlist). This plan does not re-specify them.
6. **Purge transient roots.** `scripts/clean_workspace.{sh,ps1}` removes all 94 `dist_*`/`cache_probe_*`/`tmp_*`/`warm_*`/`v05_*` dirs + `.venv_old_broken/` + 25MB `.lathe_lark_cache`.
7. **`.env.example`** — document every `LATHE_*` env var. The authoritative list from `lathe/runtime_config.py:107-172` is 13 vars: `LATHE_SHAPE_PROVIDER`, `LATHE_SHAPE_STRICT`, `LATHE_HUNYUAN_BASE_URL`, `LATHE_VGGT_WEIGHTS`, `LATHE_VGGT_DEVICE`, `LATHE_TOPOLOGY_ADAPTER`, `LATHE_TOPOLOGY_STRICT`, `LATHE_BLENDER_PATH`, `LATHE_UV_ADAPTER`, `LATHE_UV_STRICT`, `LATHE_XATLAS_RESOLUTION`, `LATHE_CODEX_IMAGEGEN`, `LATHE_EXECUTION_BLENDER_STRICT`. Also add `.env.example` entries for any new vars introduced by this plan or Plan 07 (security).
7b. **`.env.example` drift test.** CI test enumerates `os.getenv("LATHE_*")` across `lathe/` and asserts each appears in `.env.example`.

---

## Phase 3 — Containerization (1 day)

8. **`Dockerfile`** — slim: `python:3.12-slim` + `uv sync --frozen`. Multi-stage; final <400MB; entrypoint `python -m lathe.cli`.
9. **`docker/Dockerfile.blender`** — heavy: extends slim + pinned Blender 4.5 LTS tarball + sets `LATHE_BLENDER_PATH`. Optional xatlas build-tools layer.
10. **`.devcontainer/devcontainer.json`** — references `Dockerfile.blender`, mounts workspace, runs `just bootstrap`, installs VS Code extensions (Python, Pylance, Lathe extension from Phase 7).
11. **`docker-compose.yml`** — services: `lathe`, `hunyuan-mock`, `blender-headless`. Enables `docker compose run lathe build ...`.

---

## Phase 4 — Task Runner (0.5 day)

12. **`Justfile`** (Just: cross-platform, no tab pitfalls, recipe args). Recipes: `bootstrap`, `bootstrap-full`, `doctor`, `check FILE`, `plan FILE ASSET`, `build FILE ASSET`, `build-heroes` (loops hero families per CLAUDE.md), `test`, `test-file FILE`, `test-one NAME`, `lathe-test`, `bench`, `lint`, `fmt`, `typecheck`, `docs`, `clean`, `lock`, `lock-upgrade`, `docker-build`, `ci`. Thin `Makefile` wrapper delegating to `just`.

---

## Phase 5 — Doctor Upgrades (1 day)

13. **Extend `lathe/doctor.py`** — categorized status table (Environment / Core / Optional / Providers / Backends) with color pass/warn/fail glyphs. Every failure emits remediation with exact command (platform-branched). Restructure existing `_remediation_steps` strings into `{check_id, severity, message, fix_command, docs_url}` records.
14. **Flags:** `doctor --json` (already exists at `cli.py:86` — extend coverage to new structured records), `doctor --fix` (new: interactive remediation), `doctor --check CHECK_ID` (new: single probe), `doctor --strict` (new: non-zero on warn). Wire `--strict` into CI.
15. **Add probes:** `uv` presence, `just` presence, lockfile freshness (hash check), git presence, disk free in repo, write-permissions on `LATHE_CACHE_DIR`, NVIDIA driver vs torch CUDA mismatch.

---

## Phase 6 — Shell Completion (0.5 day)

16. **Migrate CLI to `click`/`typer`** if hand-rolled argparse. Add `lathe/cli_completion.py` via `argcomplete` (zero extra dep for bash/zsh) and `--print-completion {bash,zsh,fish,powershell}`. Installer snippets in `docs/shell_completion.md`.

---

## Phase 7 — LSP + VS Code Extension (2 days)

17. **Flesh out `lathe/lsp/`** using `pygls`. MVP: syntax diagnostics (reuse `checker.py`), hover for stable backend/contract IDs, go-to-definition for `uses` (via `resolver.py`), document symbols for `profile|contract|critic|asset|variant`. Descoped: std/ completion, rename.
18. **`editors/vscode/`** — TextMate grammar `lathe.tmLanguage.json` (translate from `grammar/lathe.lark`), `package.json`, `extension.ts` launching `python -m lathe.lsp`. Publish to Marketplace as `lathe-lang`. Roadmap in `docs/lsp_roadmap.md`: v0.2 (std/ completion), v0.3 (inline validator results), v1.0 (Neovim + JetBrains).

---

## Phase 8 — Optional-Deps Automation (1 day)

19. **`scripts/install_blender.{sh,ps1}`** — downloads pinned Blender into `vendor/blender/`, verifies SHA256, writes `.env.local` with `LATHE_BLENDER_PATH`. Idempotent.
20. **`scripts/install_xatlas.ps1`** — detects VS Build Tools, invokes `VsDevCmd.bat` + `uv pip install -e ".[xatlas]"` (extracts logic from `bootstrap_local.sh`).
21. **`docs/providers/{hunyuan,vggt}.md`** — dockerized Hunyuan server, VGGT clone/install/weights, runtime-config templates.

---

## Phase 9 — Onboarding & Error Messages (1 day)

22. **`docs/quickstart.md`** — six-command path from `git clone` to rendered `courier_drone.glb`. Target: <5 min warm, <15 min cold. Validated by `scripts/ci_quickstart_timer.sh` in CI.
23. **Error-message audit** — **scoped**: (a) wrap CLI boundary in `cli.py` with `LatheUserError` mapping printing `problem / cause / fix / docs-link`, (b) fix the top-20 most-hit errors by test output. Do NOT rewrite all `raise` sites across `lathe/` (hundreds of sites — out of scope). Replace bare `KeyError`/`ValueError` at CLI boundary. `--verbose`/`--debug` stacktrace toggle.
24. **First-run banner** in `doctor` if `uv.lock` absent or `.env` missing → points to `just bootstrap`.

---

## Phase 9b — Onboarding & Error-Message Polish (1 day)

25. **First-run banner / `lathe init` scaffolder** — brand-new-project scaffolder that runs `doctor`, prints the next 3 commands, and optionally writes a starter `.lth` from a template (`--template hero|minimal`).
26. **`--verbose` / `-v` flag + stdlib `logging` config.** Levels: quiet (`-q`), default, verbose (`-v`), debug (`-vv`). JSON log mode for CI (`--log-format json`). Wire a `LATHE_LOG_LEVEL` env var and add it to `runtime_config.py` + `.env.example`.
27. **`--dry-run` flag** on `build`, `plan`, `materialize`, `publish` — prints effective plan + intended IO, skips writes. Useful for CI smoke and onboarding.
28. **`--seed` flag** for reproducibility — seeds provider RNG and any hypothesis strategies; also reads `LATHE_SEED`. Surfaced in `doctor` output. CLAUDE.md notes shape is the only probabilistic stage, so this is scoped to the shape provider mux and learned providers.
29. **CLI help-string audit** — every subcommand documents its exit codes, has a one-line example, and a consistent `--help` structure. Adds a `lathe help <topic>` meta-command. Applies the `designing-clis` skill.
30. **Move `.lathe_lark_cache` under `$LATHE_CACHE_DIR`** — default `${XDG_CACHE_HOME:-~/.cache}/lathe/grammar.cache` (Linux/macOS) and `%LOCALAPPDATA%\lathe\grammar.cache` (Windows). Never lands at repo root again. Add `LATHE_CACHE_DIR` to the env-var list and `.env.example`.

---

## Phase 10 — Measurable 10/10 Criteria

- [ ] `uv.lock` committed; `uv sync --frozen` deterministic on Win/Linux/macOS
- [ ] `git clone && just bootstrap && just build examples/courier_drone.lth courier_drone` <5 min warm, <15 min cold — CI-enforced
- [ ] `just` recipes cover every documented workflow; README has no raw `python -m lathe.cli` outside reference section
- [ ] `lathe doctor --strict` exits 0 on fresh devcontainer
- [ ] `docker compose run lathe just build-heroes` green with only Docker on host
- [ ] Shell completion verified on bash, zsh, fish (via `argcomplete`) **and** PowerShell (via a separate `Register-ArgumentCompleter` generator — `argcomplete` does not cover PowerShell natively). Ship both paths.
- [ ] VS Code extension installs from Marketplace, shows diagnostics on `examples/courier_drone.lth`
- [ ] Zero transient dirs tracked; `.gitignore` blocks all CLAUDE.md patterns
- [ ] Every CLI error includes fix hint (`tests/test_error_messages.py` asserts)
- [ ] `.env.example` enumerates 100% of `LATHE_*` vars (drift test in CI)

**Total effort: ~12–13 engineer-days** in 3 parallel tracks (reproducibility+hygiene, containers+tasks, LSP+docs). Phase 7 (LSP + VS Code extension + Marketplace publish + README/gif) is realistically 3–4d, not 2d. Phase 6 adds +1–2d if the CLI migrates from argparse to `click`/`typer` (cli.py:64 is currently argparse); add `argcomplete` to existing argparse for ~0.5d if migration is deferred. Phase 9b (onboarding & polish) adds ~1d.

---

## Relevant paths

- `scripts/bootstrap_local.sh`, `pyproject.toml`
- `lathe/doctor.py`, `lathe/capabilities.py`, `lathe/lsp/__init__.py` (stub)
- `lathe/runtime_config.py:107-172` (authoritative `LATHE_*` env-var list)
- `lathe/cli.py:64` (argparse entry point), `lathe/cli.py:86` (existing `--json`)
- `CLAUDE.md` (hero families, dist_* ignore rules)

---

## Amendment log (2026-04-23)

Applied review `plans/reviews/05_developer_experience_review.md` + meta-review cross-cutters:

- Corrected transient-dir count: ~30 → **94** (Overview + Phase 2 item #6); added `.venv_old_broken/` to clean list.
- Kept `.lathe_lark_cache` size at 25MB (verified 24.3MB, plan's number is correct).
- Replaced invented env vars (`LATHE_CACHE_DIR`, `LATHE_LOG_LEVEL`) in Phase 2 item #7 with the real 13 vars from `runtime_config.py:107-172`. Added item #7b: CI drift test for `.env.example`. Added pointer to new vars from this plan / Plan 07.
- Phase 5: acknowledged `doctor --json` already exists at `cli.py:86`; reworded item #14 to split existing (`--json` extension) from new flags (`--fix`, `--check`, `--strict`).
- Phase 1 item #2: noted `bootstrap_local.{sh,ps1}` already has `--dev --export` and other flags — extend rather than rewrite.
- Added Phase 9b (Onboarding & error-message polish, ~1d): `lathe init` scaffolder, `--verbose`/`-v` + stdlib `logging`, `--dry-run` on build/plan/materialize/publish, `--seed` + `LATHE_SEED`, CLI help-string audit with exit codes, move `.lathe_lark_cache` under `$LATHE_CACHE_DIR`.
- Phase 10 shell-completion bullet: clarified `argcomplete` covers bash/zsh/fish; PowerShell needs a separate `Register-ArgumentCompleter` generator — ship both.
- Phase 2 item #5: deferred `.gitignore` ownership to Plan 06 (Maintenance); this plan does not re-specify the patterns.
- Effort: ~9d → **~12–13d**. Phase 7 is 3–4d (LSP+VS Code+Marketplace); optional click/typer migration in Phase 6 is +1–2d; Phase 9b is +1d.
