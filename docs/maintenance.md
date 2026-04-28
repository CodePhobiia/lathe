# Maintenance and Triage

This page is the operating guide for keeping Lathe maintainable between
releases. It covers labels, milestones, issue intake, stale handling,
dependency updates, and the metrics that decide whether a release is healthy.

## Canonical Repository

The intended public repository is `https://github.com/talmerri/lathe`, matching
`pyproject.toml`, `mkdocs.yml`, and the issue templates. A local checkout is not
considered fully configured until `git remote -v` includes that remote. Until
then, release tasks that require GitHub settings remain blocked.

## Issue Intake

Use the GitHub issue forms for public work:

| Template | Use for | Required triage label |
| --- | --- | --- |
| Bug report | Compiler, CLI, validator, provider, cache, or runtime defects. | `bug` |
| Feature request | New language, backend, provider, engine, or workflow capability. | `enhancement` |
| .lth authoring help | User needs help making an asset certify. | `help-wanted` |
| Release blocker | Anything that must stop a tagged release. | `release-blocker` |

Security vulnerabilities must follow `SECURITY.md`, not public issues.

## Labels

The canonical label source is `.github/labels.yml`.

| Area | Labels |
| --- | --- |
| Bugs and defects | `bug`, `needs-repro`, `release-blocker`, `flaky-test` |
| Security | `security`, `deps` |
| Documentation | `docs` |
| Architecture and contracts | `architecture`, `language-contract`, `shape-stage` |
| Providers and runtime | `backend`, `provider`, `cache` |
| Examples and product quality | `examples`, `product-quality` |
| Contributor flow | `good-first-issue`, `help-wanted`, `stale` |

Every issue should have exactly one primary area label and any needed
secondary labels. Release blockers must identify the blocking release in the
milestone field.

## Milestones

Use these milestone bands until GitHub milestones are created on the canonical
remote:

| Milestone | Horizon | Exit criteria |
| --- | --- | --- |
| `v0.2-rc-hardening` | Near term | Current release candidate gates, security scans, docs, and canonical examples are green. |
| `v0.3-alpha-godot` | Near term | Godot addon import path, certified-state UI, and flagship demo are polished. |
| `v0.5-public-oss` | Mid term | Public GitHub/PyPI launch, benchmark study, and design-partner evidence are ready. |
| `v0.8-provider-registry` | Mid term | Governed provider and registry workflows are usable by early adopters. |
| `v1.0-ga` | Long term | Standalone compiler, stable contracts, external references, and release support are complete. |

## Triage Rules

- Triage new issues within two business days when possible.
- Mark bugs `needs-repro` until the smallest failing `.lth`, command, and
  `lathe doctor` output are attached.
- Mark `release-blocker` only when the issue violates `docs/release/quality-bar.md`
  or an accepted release exception is missing.
- Security bugs stay private until coordinated disclosure permits public notes.
- Every fixed bug from `tasklist.md` must add or update a regression test.
- Every user-visible change must be mentioned in `CHANGELOG.md` under
  `[Unreleased]` until the release section is cut.

## Dependency Updates

Dependabot runs weekly for Python and GitHub Actions dependencies. Dependency
PRs must pass the normal PR gates plus `pip-audit`; security updates require a
maintainer review before merge. Grouped minor and patch updates are allowed,
but major version updates should stay isolated.

## Stale Policy

Issues are never auto-closed only because they are old. The stale workflow may
label idle issues and ask for fresh context, but a maintainer must close any
valid bug by hand. Security issues, release blockers, language-contract work,
dependency updates, help-wanted issues, and good-first issues are exempt.

PRs may be auto-closed after a stale warning when they are inactive and need a
rebase, because the code branch itself can become unreviewable.

## Maintenance Metrics

Review these metrics before every release candidate:

| Metric | Source | Release bar |
| --- | --- | --- |
| Open release blockers | GitHub issues with `release-blocker` label | Zero, or each has an approved release exception. |
| Mean time to resolve critical bugs | Issue labels and close timestamps | Trend stable or improving; no unresolved critical security bug. |
| Dependency age | Dependabot PRs, `uv.lock`, `pip-audit` | No critical or high vulnerability; stale major updates are documented. |
| Security scan status | Security, CodeQL, pip-audit, SBOM, Gitleaks workflows | Required checks green on the release branch or tag. |
| Doc freshness | MkDocs strict build, CLI/docs snapshot tests | No stale generated command output or artifact paths. |
| Flaky tests | CI reruns and `flaky-test` label | No release-blocking flaky test remains unexplained. |
