# Lathe 10/10 Readiness Milestones

This file converts `tasklist.md` into reviewable release milestones. The
current checkout's `origin` points at `https://github.com/talmerri/lathe.git`,
but `gh repo view` cannot resolve that repository for the authenticated
account, so remote GitHub issues cannot be created safely from this checkout.
Until the remote is corrected, this document is the issue-ready milestone
source of truth.

## Milestone 1: Local Quality Gates

- `ruff check .` passes with the expanded project lint rules.
- Expand Ruff rules beyond the current minimal ratchet while keeping changes
  scoped and reviewed.
- Enable import hygiene rules for unused imports, shadowing, complexity hot
  spots, and unsafe patterns.
- Track and drive static-analysis warnings to zero.
- Reduce module complexity in any files that exceed agreed size or complexity
  thresholds.
- Add or strengthen type annotations for public APIs, providers, CLI command
  interfaces, stage contracts, and schema-facing data structures.
- Add code comments only for non-obvious algorithms, contracts, and
  security-sensitive behavior.

## Milestone 2: Security And Trust Boundaries

- Security checks pass: Bandit, pip-audit, Gitleaks, Semgrep, CodeQL, and any
  repo-specific security tests.
- Keep Bandit, Semgrep, Gitleaks, CodeQL, and dependency scans required for
  protected branches.
- Separate trusted compiler internals from untrusted asset input handling.
- Normalize logging so errors, warnings, and debug traces are structured and
  do not leak sensitive data.
- Review public dataclasses and dictionaries for schema drift and convert
  fragile untyped blobs into validated structures where appropriate.

## Milestone 3: Cross-Platform Sandbox And Dependency Proof

- Reproduce the current sandbox behavior on Windows and POSIX, including CPU
  and memory limit enforcement.
- Validate with an intentionally resource-heavy Blender fixture.
- Ensure all required dev/test dependencies are installable from a clean clone.
- Add cross-platform tests or platform-specific CI jobs for Windows, macOS,
  and Linux.

## Milestone 4: Test Depth And Regression Closure

- Add regression tests for every bug listed in `tasklist.md`.
- Add mutation or fault-injection testing for critical validation paths.
- Ensure every canonical asset builds from a clean clone in deterministic mode.
- Validate engine manifests against real target import workflows where
  possible.

## Milestone 5: Product Evidence And Demos

- Gather feedback from at least a few target users and record findings.
- Add polished demo scripts or videos for the core workflow.
- No known major or critical issue remains open without an explicit documented
  release exception.

## Milestone 6: Release Candidate Verification

- A release candidate is built from a clean checkout and verified by a release
  checklist.
- Run the clean-clone bootstrap on Windows.
- Run the clean-clone bootstrap on macOS.
- Run the clean-clone bootstrap on Linux.
- Run the full local quality gate from a clean checkout.
- Run all CI workflows on the release candidate branch.
- Verify docs build and publish preview.
- Verify changelog and version tags.
- Verify SBOM generation and security scan outputs.
- Verify source distribution and wheel install in a fresh environment.
- Verify canonical examples from installed package, not only editable checkout.
- Verify artifact outputs in at least one external consumer/viewer.
- Confirm no release-blocking bugs remain open.
- Publish the release only after all gates are green.

## Milestone 7: Independent 10/10 Reassessment

- Code Quality score is reassessed as 10/10 with evidence.
- Documentation score is reassessed as 10/10 with evidence.
- Architecture score is reassessed as 10/10 with evidence.
- Test Coverage score is reassessed as 10/10 with evidence.
- Developer Experience score is reassessed as 10/10 with evidence.
- Maintenance and Activity score is reassessed as 10/10 with evidence.
- Security score is reassessed as 10/10 with evidence.
- Product Quality score is reassessed as 10/10 with evidence.
- Product Value and Vision score is reassessed as 10/10 with evidence.
- Bugs, Errors, and Issues score is reassessed as 10/10 with evidence.
- Overall score is reassessed as 10/10 by someone who did not implement the
  final fixes.

## Import Notes

When the remote is corrected, each bullet above can be imported as a GitHub
issue under its milestone. Keep the exact checklist text in issue titles so
future automation can reconcile `tasklist.md`, this milestone plan, and GitHub
issue state without fuzzy matching.
