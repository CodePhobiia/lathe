# Quality Dashboard

Last updated: 2026-04-25

This dashboard is the tracked scorecard for the 10/10 repository effort in
`tasklist.md`. Scores are working maintenance scores, not final release
certifications. The final 10/10 reassessment must be performed by someone who
did not implement the last fixes.

| Dimension | Current | Target | Owner | Status | Evidence to reach 10/10 |
| --- | ---: | ---: | --- | --- | --- |
| Code Quality | 7 | 10 | Core compiler owner | At risk | Expanded Ruff rules, typed public APIs, no broad silent fallbacks, zero static-analysis warnings. |
| Documentation | 8 | 10 | Docs owner | Improving | Generated CLI/language/schema docs, executable examples, current artifact paths, previews. |
| Architecture | 7 | 10 | Architecture owner | At risk | Enforced boundaries, stable contracts, migration guidance, concurrency audit. |
| Test Coverage | 7 | 10 | QA owner | At risk | Staged 85% target, package gates, fuzz/property/golden/security tests, no untracked skips. |
| Developer Experience | 8 | 10 | DX owner | Improving | Clean-clone CI, doctor coverage, sample configs, completions or documented non-goal. |
| Maintenance and Activity | 7 | 10 | Maintainer | Improving | Current issue templates, labels, milestones, roadmap, stale policy, release metrics. |
| Security | 7 | 10 | Security owner | At risk | Deny-by-default network, centralized URL validation, archive/path hardening, required protected-branch gates. |
| Product Quality | 5 | 10 | Product owner | Blocked | Canonical gallery, deterministic clean-clone builds, artifact previews, external viewer/import validation. |
| Product Value and Vision | 8 | 10 | Product owner | Improving | Target-user feedback and polished demo evidence. |
| Bugs, Errors, and Issues | 6 | 10 | Triage owner | At risk | Every listed bug fixed with a regression test or documented release exception. |
| Overall | 7 | 10 | Release owner | At risk | All global completion gates green from a clean checkout. |

## Update Rules

- Update the dashboard whenever `tasklist.md` items are checked, reopened, or
  converted into release exceptions.
- Do not raise a score without linking to evidence in docs, tests, CI, or a
  release checklist.
- A score of 10 requires passing validation, not only a written policy.
- Product Quality cannot exceed 8 until the canonical gallery builds from a
  clean clone and artifact outputs are externally validated.
- Security cannot exceed 8 until protected-branch required checks are verified
  on the canonical remote.

## Current Release Blockers

| Blocker | Dimension | Status | Next evidence needed |
| --- | --- | --- | --- |
| Canonical example build matrix is not fully green. | Product Quality | Open | Clean deterministic build evidence for every canonical asset. |
| CodeQL and protected-branch required checks are not locally verifiable. | Security | Open | GitHub branch-protection screenshot/export or repository ruleset. |
| Type checking is not yet a supported passing gate. | Code Quality | Open | Targeted mypy or pyright command with passing result. |
| Clean-clone verification has not run on all supported OSes. | DX / Release | Open | Windows, Linux, and macOS clean-clone logs. |
| Target-user feedback is not recorded. | Product Value | Open | Notes from at least three target users. |
