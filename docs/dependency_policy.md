# Dependency policy

Lathe uses [`uv`](https://docs.astral.sh/uv/) as the authoritative lock tool; `uv.lock` is the source of truth for reproducible installs. `requirements-docs.txt` is a loose-pin convenience file for contributors not using `uv`.

## Upgrade cadence

- **Monthly baseline upgrade.** Once per month, run `uv lock --upgrade` on a fresh branch and commit the resulting lock changes as a dedicated PR. Include a brief summary of notable version jumps in the PR description.
- **Security upgrades are not bound to the monthly cadence.** When `pip-audit` or GitHub Advisory data flags a vulnerable dependency, upgrade immediately on its own PR per the [Security policy](../SECURITY.md).
- **Transitive-only bumps** can be rolled into the monthly baseline PR; **direct-dependency major bumps** should get their own PR with a targeted test run.

## Adding a new dependency

1. Add it to the appropriate `[project]` table in `pyproject.toml` (runtime, `[project.optional-dependencies].dev`, or the `docs` extra).
2. Run `uv lock` to regenerate `uv.lock`.
3. Justify the addition in the PR description: why a stdlib alternative is insufficient, and what the maintenance cost is.

## Cross-links

- [Security policy](../SECURITY.md) — vulnerability reporting and response SLAs.
- Plan 06 (Maintenance) — the operational security / dependency workflow that this policy aligns with.
- [Versioning](versioning.md) — how dependency bumps translate into package version bumps.
