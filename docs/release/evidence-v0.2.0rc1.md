# Release Evidence Packet — v0.2.0rc1

**Status:** IN PROGRESS — readiness remediation pass
**Started:** 2026-04-28
**Owner:** Tal Merri (@talmerri)
**Branch:** `worktree-readiness-pass-v020rc1` (worktree off `main`)
**Verdict being remediated:** DO NOT SHIP (per audit run 2026-04-28)
**Scope of this release:** pre-release reference compiler scaffold; pre-release on PyPI is allowed only after every Phase 0–18 item below is either green or has a recorded formal exception. Stable / "production-ready" public claims are forbidden until the entire `readiness-tasks.md` checklist is green.

This document is the single index for every piece of release evidence
referenced by `readiness-tasks.md`. Every checked task in that file MUST
add an entry here pointing at the durable artifact (committed file, command
transcript, dashboard URL, signed decision record, ticket, etc.). Verbal
agreement is not evidence.

## Launch freeze

A launch freeze is in effect for v0.2.0rc1 as of 2026-04-28. No public
release artifacts may be published from this branch until:

1. Every Phase 0–18 task in `readiness-tasks.md` is checked or has a
   formally recorded exception in this packet.
2. The Phase 18 go/no-go meeting has been held and the verdict recorded
   in this file.
3. Legal/privacy sign-off in `docs/legal/compliance-review-v0.2.0rc1.md`
   is complete OR an explicit launch blocker is recorded if review is
   unavailable.

## Repo identity at start of pass

- Remote: `https://github.com/talmerri/lathe.git`
- Branch under remediation: `worktree-readiness-pass-v020rc1`
- Base commit (pre-pass): `30f9186 chore: harden repository quality gates`
- Worktree location: `.claude/worktrees/readiness-pass-v020rc1/`
- Tag status at start: untagged
- Dirty worktree at start: gitignore amended; `readiness-tasks.md`
  copied into worktree
- Dirty-worktree check from clean checkout: pending — see Phase 3
  evidence section

## Audit-output exclusion policy

`tmp_audit_*`, `tmp_*`, `dist_*`, `warm_*`, `v05_*`, and `cache_probe_*`
directories at the repo root are explicitly NOT release evidence. They
are transient build/audit scratch dirs (CLAUDE.md repo conventions) and
must not be referenced from this packet. All evidence cited here lives
under `docs/`, `tests/`, configured CI, or under a stable `dist/` build
that is rebuilt from a clean checkout for the release-evidence run.

## Stable-release-claim restriction

Until this checklist is green:

- Public copy may use "v0.2.0 release candidate", "pre-release", or
  "early-access reference scaffold".
- Public copy may NOT use "production-ready", "stable", "1.0", "GA",
  or imply that downstream consumers should depend on the release for
  shipping work without their own evaluation.

This restriction is recorded in `docs/release/launch-narrative-v0.2.0rc1.md`
and `docs/release/decision-log-v0.2.0rc1.md` once those exist.

## Index

The headings below mirror the phases of `readiness-tasks.md`. Each
section is filled in as remediation lands. Items not yet remediated
are listed as `pending`. Items that require human action outside Claude
Code's reach (signed counsel review, design-partner LOIs, Godot manual
smoke tests on macOS, security-firm pen-test, PyPI Trusted Publishing
configuration, branch-protection toggles, etc.) are listed as
`requires-human` with a one-line description of what is missing.

### Phase 0 — Launch freeze and scope control

- Launch freeze declared above (this section, 2026-04-28).
- Launch scope: pre-release reference compiler scaffold under
  `0.2.0rc1`. No GA, no broader OSS launch, no Godot AssetLib
  submission yet. See `docs/release/launch-plan-v0.2.0rc1.md` once
  drafted.
- Repo identity captured above.
- Audit-output exclusion policy recorded above.

### Phase 1 — Required input inventory

All Phase 1 documents created or updated in commit landing this section.
Cross-references in `readiness-tasks.md` Phase 1 carry per-checkbox
evidence pointers.

**Completed (durable artifact landed in this branch):**

- `docs/lathe_prd.md` — refreshed: version, last-reviewed 2026-04-28,
  owner, problem/target-user one-liners, requirement-status tagging
  with linked tests/docs/examples or explicit `gap:` annotations.
  Reviewer slot still `requires-human` (no backup named).
- `docs/architecture/overview.md` — currency-check footer
  (2026-04-28) appended.
- `docs/architecture/technical-design-v0.2.0rc1.md` — created
  (release-supported components + failure modes; ≥6 SPOFs;
  optional-tool absence behavior; storage posture; migration posture;
  links to `tests/contract/`, `tests/golden/`, ADR-0009).
- `docs/release/test-report-v0.2.0rc1.md` — created (matrix template
  with rows for Win/Linux/macOS × Python 3.11/3.12; skipped tests;
  deselected tests; coverage 65% threshold + per-package gates;
  partition links).
- `docs/telemetry_event_taxonomy.md` — created (telemetry remains
  disabled-by-default for v0.2.0rc1; per-event versioning;
  north-star metric proposal; 5-funnel definitions; dashboards and
  data-quality checks deferred until ingest is provisioned).
- `docs/ops/README.md`, `docs/ops/on-call.md` — created (ops index;
  roster; first-response SLAs; escalation paths for security /
  install / yank / legal-privacy / Godot).
- `docs/risk_register.md` — created (18 risks: 14 mandatory + 4
  extra; per-row likelihood, impact, owner, review date 2026-05-28,
  mitigation, contingency, trigger).
- `docs/release/launch-plan-v0.2.0rc1.md` — created (4-phase plan;
  soft-launch and GA explicitly out of scope for rc1; per-phase
  entry/exit/rollback/comms; backup owners flagged
  `requires-human`).
- `docs/release/rollback-plan-v0.2.0rc1.md` — created (kill-switch
  authority; PyPI yank/deprecate; GitHub Release edit/withdraw;
  docs banner via mkdocs-material override; pinned issue + GHSA;
  irreversibles).
- `docs/privacy.md` — created (telemetry-disabled-by-default banner;
  field allowlist; consent capture; opt-out; purge; retention;
  vendors-touching-user-data = NONE; safe-harbor pointer).
- `docs/terms.md` — created (ToS not applicable for v0.2.0rc1;
  trigger conditions for when ToS becomes applicable).
- `docs/legal/compliance-review-v0.2.0rc1.md` — created (counsel
  review banner: launch BLOCKED until counsel review or recorded
  exception; per-regulation applicability sub-sections; license
  compatibility table; Blender GPL subprocess-boundary reasoning;
  provider terms `requires-human`).
- `docs/business/unit_economics.md` — created (no-billing surface;
  COGS estimates with explicit "estimate" labels; 1×/10×/100× infra
  projections; sensitivity tables with `requires-human` cells; WTP
  marked MISSING; sustainability thresholds flagged for ratification).
- `docs/release/launch-narrative-v0.2.0rc1.md` — created (3 launch
  messages; press list `requires-human`; 30-day calendar; community
  moderation `requires-human`; 5 crisis-comms drafts).
- `docs/research/interviews/README.md` — created (template + tracking
  index for the 5 + 2 + 1 interview commitment).
- `docs/research/beta-feedback-v0.2.0rc1.md` — created (tracking
  sheet skeleton; rows are `requires-human` until beta runs).
- `docs/support/readiness-checklist.md` — created (real top-20 FAQ
  answers; 6 support macros; intake labels and issue-template review
  posture; response-time targets; escalation triggers).
- `docs/release/known-bugs-v0.2.0rc1.md` — created (per-row severity,
  owner, target-fix-or-exception, regression-test linkage; ADR
  currency check including 0004/0005/0006 Proposed→Accepted
  recommendation).
- `docs/release/decision-log-v0.2.0rc1.md` — created (≥9 non-goals;
  intentionally deferred features; release-exception skeleton; ≥8
  forbidden public claims).

**Phase 1 `requires-human` inventory (durable list):**

| # | What | Where | Trigger to clear |
|---|------|-------|-----------------|
| H1 | Backup product reviewer | `docs/lathe_prd.md` | Before any GA discussion |
| H2 | Linux/macOS pytest matrix runs | `docs/release/test-report-v0.2.0rc1.md` | Push branch, GitHub Actions on Ubuntu/macOS runners |
| H3 | Win Python 3.11 + 3.12 pytest results | same | Phase 6 from clean checkout (local-achievable) |
| H4 | Godot addon manual smoke (Win+mac+Linux) | same | Run procedure in `editors/godot/lathe-addon/` |
| H5 | External GLB/USD viewer screenshots | same | Run viewers on canonical outputs |
| H6 | CodeQL URL | same | GitHub Advanced Security after push |
| H7 | Pen-test / security review | same / Phase 9 | Engage third-party or record formal exception |
| H8 | Telemetry dashboards (5) | `docs/telemetry_event_taxonomy.md` | Telemetry decision in Phase 11; dashboards only when ingest is provisioned |
| H9 | Telemetry data-quality checks (3) | same | Same trigger as H8 |
| H10 | Backup launch-day on-call owner | `docs/ops/on-call.md` + RISK-015 | Before public launch |
| H11 | Backup security contact | same | Before public launch |
| H12 | Legal/compliance contact | same | Engage counsel |
| H13 | PyPI release authority backup | same | Before public launch |
| H14 | GitHub release authority backup | same | Before public launch |
| H15 | Community moderation owner | same | When Discord launches |
| H16 | Counsel sign-off (privacy + compliance + crisis comms) | `docs/legal/compliance-review-v0.2.0rc1.md` | Engage counsel |
| H17 | Launch-phase backup owners | `docs/release/launch-plan-v0.2.0rc1.md` | Before public launch |
| H18 | Backup kill-switch authority | `docs/release/rollback-plan-v0.2.0rc1.md` | Before public launch |
| H19 | Discord channel + procedure | `docs/release/rollback-plan-v0.2.0rc1.md` | When Discord launches |
| H20 | Maintainer hourly rate ratification | `docs/business/unit_economics.md` | Owner sign-off |
| H21 | Provider cost cells (Hunyuan, VGGT) | same | Confirmed model-server pricing |
| H22 | Support hours/ticket | same | First beta data |
| H23 | Sustainability threshold ratification (3 rows) | same | Owner sign-off |
| H24 | Competitor pricing re-check | `docs/release/launch-narrative-v0.2.0rc1.md` | Before any public soft-launch |
| H25 | Press/influencer contact list | same | Before any soft-launch |
| H26 | 30-day content calendar weeks 2–4 | same | Before public launch |
| H27 | Community moderation plan + CONTRIBUTING.md | same + repo root | When community channel opens |
| H28 | Crisis-comms counsel review | same | Engage counsel |
| H29 | 5 + 2 + 1 persona interviews | `docs/research/interviews/README.md` | Schedule + run |
| H30 | Beta-user records (dogfood, closed beta, blockers, severity, persona, would-adopt) | `docs/research/beta-feedback-v0.2.0rc1.md` | Run beta |
| H31 | ADR 0004 / 0005 / 0006 Proposed→Accepted moves | `docs/release/known-bugs-v0.2.0rc1.md` ADR section | Act on per-ADR recommendation |
| H32 | Bugs without regression test | `docs/release/known-bugs-v0.2.0rc1.md` | Add regression tests under `tests/bugs/` and `@pytest.mark.bug_regression` |

### Phase 2 — P0 legal, privacy, compliance

- Telemetry-disabled-by-default behavioral confirmation: pending
  evidence transcript.
- Privacy policy text + consent/retention/deletion documentation:
  pending.
- IP-clearance review for checked-in fixtures and gallery images:
  pending review.

### Phase 3 — P1 release evidence

Local-Windows transcripts captured 2026-04-28 in
`docs/release/evidence-bundle-v0.2.0rc1/`. Host-side limits — the
worktree-resident venv is Python 3.13.13, the host has neither
Python 3.11 nor Python 3.12 installed, and the bundle is built from
a worktree (not a fresh `git clone` of a tagged commit). Every row
therefore carries a `requires-human` follow-up for the truly clean
clean-checkout / multi-Python rerun a CI runner provides.

| Gate | Local-Win-3.13 status | Transcript | Clean-checkout rerun |
|------|------------------------|------------|----------------------|
| repo-state | captured | `evidence-bundle-v0.2.0rc1/repo-state.txt` | `requires-human` after release branch lands and `git tag v0.2.0-rc.1` |
| release-metadata (`--expected-tag`) | pass | `evidence-bundle-v0.2.0rc1/release-metadata-3.11.txt` | `requires-human` (Python 3.11 + Python 3.12 legs + tagged-commit rerun with `--require-current-tag`) |
| dependency-sync | pass | `evidence-bundle-v0.2.0rc1/dep-sync.txt` | `requires-human` (CI rerun on Linux) |
| pip-audit (runtime, `-r requirements.txt`) | partial — see notes | `evidence-bundle-v0.2.0rc1/pip-audit-runtime.txt` | `requires-human` (CI: `.github/workflows/pip-audit.yml`) |
| pip-audit (dev, `-r requirements-dev.txt`) | partial — see notes | `evidence-bundle-v0.2.0rc1/pip-audit-dev.txt` | `requires-human` (CI rerun) |
| build (sdist + wheel) | pass | `evidence-bundle-v0.2.0rc1/build.txt` | `requires-human` (clean-checkout rebuild for release artifacts) |
| twine check | pass | `evidence-bundle-v0.2.0rc1/twine-check.txt` | `requires-human` (rerun against post-clean-checkout artifacts) |
| SHA256 sums | captured | `evidence-bundle-v0.2.0rc1/SHA256SUMS.txt` | `requires-human` (post-clean-checkout rebuild) |
| wheel-contents (no `.lathe_lark_cache`, no `tests/`) | pass | `evidence-bundle-v0.2.0rc1/wheel-contents.txt` | `requires-human` (rerun against clean-checkout wheel) |
| SBOM (CycloneDX JSON + XML) | captured | `evidence-bundle-v0.2.0rc1/sbom.json`, `evidence-bundle-v0.2.0rc1/sbom.xml` | `requires-human` (CI: `.github/workflows/sbom.yml` against clean checkout) |
| wheel install — Python 3.11 | deferred (host lacks 3.11) | — | `requires-human` (Linux/macOS CI on Python 3.11) |
| wheel install — Python 3.13 surrogate | pass | `evidence-bundle-v0.2.0rc1/wheel-install-py311.txt` | `requires-human` (intended target is 3.11; this is a surrogate) |
| wheel install — Python 3.12 | deferred (host lacks 3.12) | — | `requires-human` (rerun on a Python 3.12 host) |
| signed wheel/sdist | not signed | — | `requires-human` OR record release exception `EXC-PHASE3-SIGN-001` (see decision log) |
| signed tag | not tagged | — | `requires-human` OR record release exception `EXC-PHASE3-SIGN-001` |
| PyPI Trusted Publishing | not configured | — | `requires-human` (PyPI account holder — see `EXC-PHASE3-PYPI-TP-002`) |

Notes:

- `pip-audit -r requirements*.txt --strict` cannot run inside this
  worktree because both requirements files start with `-e .` and
  pip-audit's hashes-required mode rejects an editable install with
  no single hashable file. The transcripts capture the failed
  primary command, then a documented fallback to
  `pip-audit --skip-editable` against the active venv. The
  fallback reports two known vulnerabilities: `pip 26.0.1
  CVE-2026-3219` (the Phase 6 gate) and `lxml 5.4.0 CVE-2026-41066`
  (new finding — see Phase 9 follow-up). Both transcripts skip the
  in-tree `lathe` and editable `vggt` packages.
- The wheel-install transcript was captured with Python 3.13
  (Windows Store) because Python 3.11 / 3.12 are not installed on
  this host. The wheel installs cleanly, `python -m lathe.cli
  doctor` and the `lathe` console script both succeed, and
  `.lathe_lark_cache` does NOT appear in the install venv's
  site-packages. The 3.11-specific and 3.12-specific legs are
  `requires-human`.
- The repo HEAD captured (`eb1cd49`) is on
  `worktree-readiness-pass-v020rc1`, NOT on a release tag. The
  release-metadata script accepted `--expected-tag v0.2.0-rc.1`
  with the looser check; `--require-current-tag` is
  `requires-human` because that flag only succeeds on a tagged
  commit.
- New `requires-human` items added by this run beyond the H1..H32
  inventory from Phase 1: H33 (rerun pip-audit on a non-worktree
  clone where `-e .` is not in requirements files), H34 (Python
  3.11 wheel-install leg), H35 (Python 3.12 wheel-install leg),
  H36 (clean-checkout rebuild for release SHA256SUMS), H37
  (`lxml 5.4.0` CVE-2026-41066 triage — Phase 9), H38 (CycloneDX
  CI-driven SBOM rerun against a non-editable install).

### Phase 4 — Risk, rollback, kill-switch

- `docs/risk_register.md`: pending.
- Rollback triggers + kill-switch procedures: pending; PyPI yank +
  GitHub release withdrawal walkthroughs are documented but not
  exercised — `requires-human` for any actual yank dry-run that
  affects upstream.

### Phase 5 — Operational readiness

- Runbooks under `docs/ops/`: pending.
- On-call/escalation roster: pending; primary/backup names are
  `requires-human` until staffing is confirmed.
- GitHub support labels + issue templates: `requires-human` for the
  remote enable; local templates can be drafted.

### Phase 6 — Release gate failures

- mypy decision (block vs exception): pending.
- pip CVE-2026-3219 investigation: pending.
- gitleaks/semgrep/Bandit/CodeQL evidence: pending; CodeQL URL is
  `requires-human` until run on GitHub.
- Lint/test/docs/package gate transcripts: pending.
- Branch protection screenshots: `requires-human`.

### Phase 7 — Product experience

- TTFV transcripts on Windows/macOS/Linux: Windows can be captured
  locally; macOS/Linux are `requires-human` without those hosts.
- Gallery build artifacts: pending.
- External GLB/USD viewer screenshots: pending.
- Godot addon manual smoke logs: `requires-human`.

### Phase 8 — Technical architecture

- Capacity/headroom report: pending.
- Cache/idempotency/replay/versioning posture docs: pending.

### Phase 9 — Security

- Threat model refresh: pending.
- Secret scan over full history: pending.
- SBOM + license review: pending.
- Pen-test or security review: `requires-human`.

### Phase 10 — Reliability and observability

- Critical journey + SLO definitions: pending.
- Synthetic monitors: `requires-human` until hosting decision lands.
- Backup/restore drill: pending.

### Phase 11 — Data and telemetry

- Telemetry-disabled-for-RC decision + manual metric plan: pending.
- Consent record + opt-out + local purge tests: pending.

### Phase 12 — Financial and unit economics

- COGS + sensitivity tables: pending.
- Threshold definitions for unsustainable surfaces: pending.

### Phase 13 — Launch and GTM

- V0.5 OSS criteria status: pending.
- Pre-release-only launch copy: pending.
- Crisis comms drafts: pending.

### Phase 14 — Team and organization

- `docs/release/raci-v0.2.0rc1.md`: pending; named owners are
  `requires-human`.

### Phase 15 — Product-market evidence

- 5 + 2 + 1 persona interviews and 3 design-partner LOIs:
  `requires-human`.

### Phase 16 — Product quality and Godot

- Godot addon launch-scope decision: pending.
- Godot Windows/macOS/Linux smoke evidence:
  `requires-human` for non-Windows hosts.
- GLB content checks (sockets, collision, LOD metadata): pending.

### Phase 17 — Anti-pattern risks

- Doc sweep for stale/aspirational claims: pending.

### Phase 18 — Re-review gate

- All P0 + P1 closure: pending.
- Final go/no-go verdict: pending.

## Decision-log seed

Every formal exception, scope-deferral, or release blocker recorded
during this pass MUST also be added to
`docs/release/decision-log-v0.2.0rc1.md` (created in Phase 1) so the
re-review packet has a single decision audit trail. This file simply
indexes the evidence; the *why* lives in the decision log.

## Re-review trigger

Phase 18 mandates a full rerun of `readiness-tasks.md` from a clean
checkout. The follow-up readiness review is scheduled for
**2026-05-28** or T+30 after actual public launch, whichever is later.
The schedule entry is recorded in
`docs/release/launch-plan-v0.2.0rc1.md` once that file exists.
