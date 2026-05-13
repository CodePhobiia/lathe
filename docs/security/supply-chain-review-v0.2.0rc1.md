# Supply-Chain Review — Lathe v0.2.0rc1

> Phase 9 P0. Self-assessment. Reviewer: Tal Merri (@talmerri).
> Date: 2026-04-28.
>
> This review uses the SBOM at
> `docs/release/evidence-bundle-v0.2.0rc1/sbom.json` as the source of
> truth for component count + identity, and cross-references the
> dependency-sync invariant captured at
> `docs/release/evidence-bundle-v0.2.0rc1/dep-sync.txt`.

## Component count

- **Total components in SBOM:** 211 (per `sbom.json`).
- **Top-level runtime declarations** (from `pyproject.toml:27-33`): 5 —
  `lark>=1.1`, `jsonschema>=4.0`, `numpy>=1.26`, `Pillow>=10.0`,
  `trimesh>=4.0`.
- **Top-level extras declarations** (from `pyproject.toml:42-87`): the
  `dev`, `docs`, `hunyuan_http`, `vggt`, `xatlas`, `geometry`, `export`,
  and `publish` extras gate the rest.
- **Transitive count** (211 minus the 5 top-level runtime deps minus
  Lathe itself) ≈ 205 (extras + transitives). The SBOM is generated via
  the `cdxgen` toolchain and includes both runtime and dev/test
  components — that is intentional for the readiness packet.

## Unexpected dependencies

I scanned the SBOM `name` fields against the declared dependency surface
in `pyproject.toml`. The expected categories are:

1. **Direct runtime deps** (`pyproject.toml:27-33`): lark, jsonschema,
   numpy, Pillow, trimesh.
2. **Dev/test extras** (`pyproject.toml:43-58`): pytest, pytest-cov,
   ruff, mypy, pre-commit, types-jsonschema, types-Pillow, hypothesis,
   syrupy, mutmut, pip-tools, build, pip-audit, bump-my-version,
   import-linter.
3. **Docs extras** (`pyproject.toml:60-67`): mkdocs-material,
   mkdocstrings[python], mkdocs-mermaid2-plugin, mkdocs-gen-files,
   mkdocs-literate-nav, mkdocs-section-index.
4. **Optional learned-provider extras**:
   - `hunyuan_http` — empty extra (HTTP client uses stdlib only).
   - `vggt` — torch>=2.11, torchvision>=0.26.
   - `xatlas` — xatlas>=0.0.11.
   - `geometry` — scikit-image>=0.25, manifold3d>=2.5.
   - `export` — scipy>=1.16.
   - `publish` — cryptography>=43, boto3>=1.34.
5. **Build-system requires** (`pyproject.toml:1-3`): setuptools, wheel.

All component names visible in `sbom.json` (sample: CacheControl,
Deprecated, EditorConfig, …) trace to one of the categories above as
either a direct dep, a transitive of a direct dep (e.g. `Deprecated` is
a transitive of `boto3`), or a dev tool (e.g. `EditorConfig` is a
formatter integration of pre-commit). Spot checks did not surface any
component that looks externally injected or unrelated to the declared
surface.

**`requires-human:` triage** for any genuinely surprising entry that the
self-assessment may have missed. The self-assessment scans by name and
PURL prefix; a deliberate adversarial review would compare PURLs against
PyPI provenance records, which is `requires-human` until the security
review (per
`docs/security/security-review-scope-v0.2.0rc1.md` decision).

## Runtime dep license summary

The runtime extras + their transitives are dominated by permissive
licenses (MIT, BSD-3-Clause, Apache-2.0). Heavy hitters:

- **lark** — MIT.
- **jsonschema** — MIT.
- **numpy** — BSD-3-Clause.
- **Pillow** — HPND (PIL legacy; OSI approved).
- **trimesh** — MIT.
- **boto3** (publish extra) — Apache-2.0.
- **cryptography** (publish extra) — Apache-2.0 OR BSD-3-Clause (dual
  licensed).
- **torch / torchvision** (vggt extra) — BSD-3-Clause.
- **scipy** (export extra) — BSD-3-Clause.
- **xatlas** — MIT.
- **manifold3d** — Apache-2.0.

Cross-reference to the legal compliance review:
`docs/legal/compliance-review-v0.2.0rc1.md` covers the Apache-2.0
distribution stance for Lathe itself (`pyproject.toml:11`) and the
dependency-license compatibility analysis. No GPL or AGPL dependencies
were observed in the runtime tree. **Full license attribution
generation** for distribution-time NOTICE.md is `requires-human` — see
the compliance review.

## Dev dep license summary

Dev/test/docs extras are almost entirely permissive (MIT / Apache-2.0 /
BSD). Notable items:

- **pytest** — MIT.
- **ruff** — MIT.
- **mypy** — MIT.
- **mkdocs-material** — MIT.
- **hypothesis** — MPL-2.0 (file-level copyleft; not a redistribution
  concern for a project that does not embed Hypothesis source).
- **pre-commit** — MIT.

The dev tree is not redistributed in the wheel/sdist (`pyproject.toml`
`[tool.setuptools.packages.find]` includes only `lathe*`), so dev
licenses are only relevant to the development workflow itself, not the
shipped artifact.

## Pinning policy

Three pinning artifacts are kept in sync:

- **`uv.lock`** — uv's authoritative resolution lock. Source of truth.
- **`requirements.txt`** — generated for legacy pip workflows.
- **`requirements-dev.txt`** — generated for dev-extras pip workflows.

Sync invariant verified by `scripts/check_dependency_sync.py`. The
Phase 3 capture is at
`docs/release/evidence-bundle-v0.2.0rc1/dep-sync.txt`:

```
uv.lock: ok
requirements.txt: ok
requirements-dev.txt: ok
exit_code: 0
```

The Phase 3 transcript was captured 2026-04-28 against
`/d/lathe_v0_1/.venv/Scripts/python.exe (Python 3.13.13)`. Note the
host interpreter is 3.13; Lathe's `requires-python = ">=3.11"` and the
support matrix lists 3.11 + 3.12 only — see
`docs/release/decision-log-v0.2.0rc1.md` "Non-goals" entry on Python
3.13/3.14 support. The dep-sync check itself is interpreter-agnostic,
so the 3.13 host is acceptable for this artifact.

## Dependabot

`.github/dependabot.yml:1-42` enables Dependabot for two ecosystems:

- **`pip`** — weekly Monday 06:00 UTC, max 10 open PRs, grouped by
  minor/patch, assigned to `talmerri`, labelled `deps`,
  `commit-message.prefix = "build(deps)"`.
- **`github-actions`** — same cadence + grouping, prefix
  `"ci(deps)"`.

**`requires-human:`** **confirm Dependabot is enabled at the GitHub
repository level.** The YAML file existence is necessary but not
sufficient — the repository's "Security & analysis" tab must show
"Dependabot version updates: Enabled". The maintainer (Tal Merri /
@talmerri) should confirm in the GitHub UI that Dependabot has actually
opened at least one PR or that the configuration is being read by
GitHub.

## Sync between `uv.lock`, `requirements.txt`, `requirements-dev.txt`

Cross-reference `docs/release/evidence-bundle-v0.2.0rc1/dep-sync.txt`:
all three are in sync as of 2026-04-28 (`exit_code: 0`).

## Release-artifact hashes

`docs/release/evidence-bundle-v0.2.0rc1/SHA256SUMS.txt` records the
canonical hashes for the wheel, sdist, and SBOM artifacts. Verification
flow:

1. Download `lathe-0.2.0rc1-py3-none-any.whl` from the GitHub Release.
2. Compute `sha256sum lathe-0.2.0rc1-py3-none-any.whl`.
3. Compare against the entry in `SHA256SUMS.txt`.

Until PyPI Trusted Publishing is configured
(`EXC-PHASE3-PYPI-TP-002`), the SHA256SUMS file plus the GitHub Release
HTTPS transport is the only integrity surface for downstream users.

## PyPI attestations

**Status:** Not configured. PyPI Trusted Publishing is recorded as
exception `EXC-PHASE3-PYPI-TP-002` in
`docs/release/decision-log-v0.2.0rc1.md`. The exception's removal target
is "before first public PyPI release" with `requires-human`: PyPI
account holder configures Trusted Publishing identity + completes a
dry-run workflow.

Until configured:

- **PyPI provenance / attestations are not produced** for v0.2.0rc1.
- **The "Available on PyPI" claim is forbidden** until the
  configuration is complete and `pip install lathe==0.2.0rc1` succeeds
  from a clean environment on the supported matrix
  (`docs/release/decision-log-v0.2.0rc1.md` forbidden claims #6).

## Signed tag status

**Status:** Not signed. Wheel/sdist/tag signatures are recorded as
exception `EXC-PHASE3-SIGN-001` in
`docs/release/decision-log-v0.2.0rc1.md`. The exception's stated reason
is the absence of a documented key-rotation, revocation, and attestation
policy — signing without those would produce stronger confidentiality
claims than the project can defend, and ad-hoc keys committed to git
would be a worse problem than skipping signatures.

The exception's removal target is "before any v0.2.0 final release" with
`requires-human`: legal/security counsel review for safe-harbor
implications.

## Open `requires-human` items

- **Dependabot UI confirmation** (named in §Dependabot above).
  Existence of `.github/dependabot.yml` is necessary but not sufficient
  — the GitHub-side "Dependabot version updates: Enabled" toggle MUST
  be confirmed by the maintainer.
- **PyPI Trusted Publishing configuration** — `EXC-PHASE3-PYPI-TP-002`.
- **Release-artifact signing policy** — `EXC-PHASE3-SIGN-001`.
- **Adversarial PURL review** — see §Unexpected dependencies — the
  self-assessment scans by name + PURL prefix; an adversarial review
  comparing PURLs against PyPI provenance records is `requires-human`
  pending the third-party security review (`EXC-PHASE9-PENTEST-001` —
  see `docs/security/security-review-scope-v0.2.0rc1.md`).
- **Distribution-time license attribution (NOTICE.md generation)** —
  `docs/legal/compliance-review-v0.2.0rc1.md` (cross-ref).

## Cross-references

- [`docs/release/evidence-bundle-v0.2.0rc1/sbom.json`](../release/evidence-bundle-v0.2.0rc1/sbom.json) — 211 components.
- [`docs/release/evidence-bundle-v0.2.0rc1/dep-sync.txt`](../release/evidence-bundle-v0.2.0rc1/dep-sync.txt) — sync invariant (`exit_code: 0`).
- [`docs/release/evidence-bundle-v0.2.0rc1/SHA256SUMS.txt`](../release/evidence-bundle-v0.2.0rc1/SHA256SUMS.txt) — release artifact hashes.
- [`docs/release/evidence-bundle-v0.2.0rc1/pip-audit-runtime.txt`](../release/evidence-bundle-v0.2.0rc1/pip-audit-runtime.txt) — runtime CVE check.
- [`docs/release/evidence-bundle-v0.2.0rc1/pip-audit-dev.txt`](../release/evidence-bundle-v0.2.0rc1/pip-audit-dev.txt) — dev CVE check.
- [`docs/release/evidence-bundle-v0.2.0rc1/lxml-investigation.txt`](../release/evidence-bundle-v0.2.0rc1/lxml-investigation.txt) — Phase 3 lxml triage.
- `.github/dependabot.yml` — automated update config.
- `pyproject.toml` — declared deps + extras.
- [`docs/release/decision-log-v0.2.0rc1.md`](../release/decision-log-v0.2.0rc1.md) — `EXC-PHASE3-SIGN-001`, `EXC-PHASE3-PYPI-TP-002`.
- [`docs/legal/compliance-review-v0.2.0rc1.md`](../legal/compliance-review-v0.2.0rc1.md) — license compatibility.
- [`docs/security/owasp-mapping-v0.2.0rc1.md`](owasp-mapping-v0.2.0rc1.md) — A06 + A08 mapping.

## Sign-off
- Reviewed: 2026-04-28
- Reviewer: Tal Merri (self-assessment, solo maintainer)
- Counsel review: requires-human
- Next review: 2026-05-28 or T+30 post-launch (whichever later)
