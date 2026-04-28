# 10/10 release quality bar

Lathe reaches a 10/10 release state only when the repository, shipped
artifacts, and public docs agree with observable behavior. The bar is evidence
based: a release is not ready because a checklist says so; it is ready when
the checks below have run and their outputs are reviewable.

Related release docs:

- [Support matrix](support-matrix.md)
- [Known limitations](known-limitations.md)

## Current release classification

`0.2.0rc1` is a pre-release reference compiler scaffold. It can be cut as a
release candidate for testing the packaging and certification flow, but it is
not a stable release until every required gate in this document is green or
has an approved release exception.

## Required gates

Before promotion, maintainers must verify:

| Area | Required evidence |
|---|---|
| Version and contracts | `pyproject.toml`, `lathe.__version__`, tags, changelog, docs, and package metadata agree. Public language and backend contracts follow [Versioning](../versioning.md). |
| Tests | The documented local test partition, full release pytest lane, contract/golden/property/fuzz lanes, and example checks pass with no unexplained skips or unresolved `flaky-test` release blockers. |
| Examples | Canonical examples run through `normalize`, `check`, `plan`, `materialize`, and expected build/certification paths. Expected failures are listed in [Known limitations](known-limitations.md). |
| Docs | README, quickstart, tutorials, CLI examples, release docs, and artifact-path docs match current command output and generated artifacts. |
| CI | Required GitHub Actions are green on the release branch, including fast tests, docs, lint, coverage, examples, security, SBOM, and release build dry run where available. |
| Security | Bandit, pip-audit, Gitleaks, Semgrep, CodeQL, and repo-specific security tests pass or have documented false-positive handling. |
| Artifacts | sdist/wheel build cleanly from a clean checkout; SBOM and hashes/signatures/attestations required by the release channel are attached or explicitly deferred by exception. |
| Product quality | Flagship assets are inspectable, deterministic for supported modes, and produce validation reports that honestly fail weak outputs instead of passing by proxy. |

## Release exception process

A release exception is allowed only for a known, bounded limitation that does
not hide a failing safety, security, data-loss, public-contract, or install
path issue.

Every exception must be recorded before release with:

1. A linked issue or milestone item.
2. The affected release version and support surface.
3. The user-visible impact and workaround.
4. The owner and target removal release.
5. The exact validation that still passed with the limitation present.
6. A changelog or release-note entry when users could hit it.

Exceptions are not allowed for:

- broken clean installs on the supported Python/platform matrix
- public contract breaks without the versioning process
- missing or failing security gates without maintainer-approved false-positive evidence
- hidden fallbacks that report success without trace evidence
- major or critical known bugs without a documented workaround and owner

## Regression-test policy

Every bug fixed from `tasklist.md`, an issue, a release blocker, or a user
report must add or update a regression test unless maintainers document why a
test is impossible or disproportionate.

Regression tests should be placed in the narrowest reliable layer:

| Bug surface | Preferred test home |
|---|---|
| Parser, resolver, checker, planner behavior | unit or property tests for the affected module |
| CLI diagnostics or exit behavior | CLI unit tests with exact code/message assertions |
| Build artifacts, traces, manifests, validators | build or golden tests using minimal fixtures |
| Provider and optional runtime behavior | mocked provider tests unless a marked integration lane is required |
| Security-sensitive path, subprocess, network, or input handling | negative tests for reject paths plus one valid-path test |

The test must fail against the buggy behavior, pass after the fix, and avoid
depending on generated local leftovers. If the fix changes public behavior,
update the relevant docs and examples in the same change.
