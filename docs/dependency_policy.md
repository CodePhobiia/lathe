# Dependency policy

Lathe uses [`uv`](https://docs.astral.sh/uv/) as the authoritative lock tool; `uv.lock` is the source of truth for reproducible installs. `requirements.txt` and `requirements-dev.txt` are generated lock exports for audit and sync checks, not the recommended bootstrap input; use the bootstrap scripts or `pip install -e ".[dev,export]"` for contributor installs. `requirements-docs.txt` is a loose-pin convenience file for contributors not using `uv`.

Developer tooling that gates CI should be pinned, not lower-bounded. Ruff is pinned in `pyproject.toml` and mirrored by `.pre-commit-config.yaml` so local and CI diagnostics do not drift as new Ruff releases add or reinterpret rules.

The required Ruff rule set is currently a documented ratchet for parse/import-time failures and production `assert` usage. Broader style/import/doc/security lint rules remain backlog work until the existing tree is formatted and cleaned in dedicated PRs.

## Optional dependency extras

`pyproject.toml` is the source of truth for optional extras. Keep extras narrow:
base installs must remain usable for the conservative offline path, and heavy
provider/runtime dependencies must stay opt-in.

| Extra | Purpose | Notes |
| --- | --- | --- |
| `dev` | contributor test/lint/type/release tooling | Used by the bootstrap scripts when `-Dev` or `--dev` is passed. |
| `docs` | local documentation builds | Required for `mkdocs build --strict`. |
| `test-min` | intentionally empty minimal test surface | Preserved for minimal dependency checks. |
| `hunyuan_http` | Hunyuan HTTP provider mode | No Python package today; the real dependency is a reachable configured server. |
| `vggt` | VGGT provider prerequisites | Installs torch/torchvision only; install official VGGT from source when needed. |
| `xatlas` | real xatlas UV adapter | May require native build tools, especially Visual Studio Build Tools on Windows. |
| `geometry` | optional geometry kernel experiments | Includes heavier geometry packages and is not part of default bootstrap. |
| `export` | fuller mesh/export helper stack | Used by the default documented contributor bootstrap. |
| `publish` | local/cloud publish drivers | Adds signing/cloud SDK dependencies. |

Blender is intentionally not a Python extra because it is an external
application discovered by `lathe doctor` and the topology adapter. Install it
through the platform package manager or Blender's installer when you want real
Blender-backed topology behavior.

## Upgrade cadence

- **Monthly baseline upgrade.** Once per month, run `uv lock --upgrade` on a fresh branch and commit the resulting lock changes as a dedicated PR. Include a brief summary of notable version jumps in the PR description.
- **Security upgrades are not bound to the monthly cadence.** When `pip-audit` or GitHub Advisory data flags a vulnerable dependency, upgrade immediately on its own PR per the [Security policy](https://github.com/talmerri/lathe/blob/main/SECURITY.md).
- **Transitive-only bumps** can be rolled into the monthly baseline PR; **direct-dependency major bumps** should get their own PR with a targeted test run.

## Adding a new dependency

1. Add it to the appropriate `[project]` table in `pyproject.toml` (runtime, `[project.optional-dependencies].dev`, or the `docs` extra).
2. Run `uv lock` to regenerate `uv.lock`.
3. Regenerate the checked-in pip exports when the changed dependency is covered by them:
   `uv export --format requirements-txt --all-extras -o requirements.txt` and
   `uv export --format requirements-txt --group dev -o requirements-dev.txt`.
4. Run `python scripts/check_dependency_sync.py` or `just deps-check` before review.
5. Justify the addition in the PR description: why a stdlib alternative is insufficient, and what the maintenance cost is.

## Cross-links

- [Security policy](https://github.com/talmerri/lathe/blob/main/SECURITY.md) — vulnerability reporting and response SLAs.
- Plan 06 (Maintenance) — the operational security / dependency workflow that this policy aligns with.
- [Versioning](versioning.md) — how dependency bumps translate into package version bumps.
