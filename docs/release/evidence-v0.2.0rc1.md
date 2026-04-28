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

- `docs/lathe_prd.md`: pending refresh (version, last-reviewed date,
  named owner/reviewer, problem/target-user one-liners, requirement
  status tagging).
- `docs/architecture/overview.md`: pending currency check.
- `docs/architecture/technical-design-v0.2.0rc1.md`: pending creation.
- `docs/release/test-report-v0.2.0rc1.md`: pending creation; Linux/
  macOS rows are `requires-human` until matrix CI runs are attached.
- `docs/telemetry_event_taxonomy.md`: pending creation; live dashboards
  are `requires-human`.
- `docs/ops/README.md`, `docs/ops/on-call.md`: pending creation.
- `docs/risk_register.md`: pending creation.
- `docs/release/launch-plan-v0.2.0rc1.md`,
  `docs/release/rollback-plan-v0.2.0rc1.md`: pending creation.
- `docs/privacy.md`, `docs/terms.md`,
  `docs/legal/compliance-review-v0.2.0rc1.md`: pending creation;
  signed counsel review is `requires-human`.
- `docs/business/unit_economics.md`: pending creation.
- `docs/release/launch-narrative-v0.2.0rc1.md`: pending creation.
- `docs/research/interviews/README.md`,
  `docs/research/beta-feedback-v0.2.0rc1.md`,
  `docs/support/readiness-checklist.md`: pending creation; recorded
  user interviews and beta-user feedback are `requires-human`.
- `docs/release/known-bugs-v0.2.0rc1.md`,
  `docs/release/decision-log-v0.2.0rc1.md`: pending creation.

### Phase 2 — P0 legal, privacy, compliance

- Telemetry-disabled-by-default behavioral confirmation: pending
  evidence transcript.
- Privacy policy text + consent/retention/deletion documentation:
  pending.
- IP-clearance review for checked-in fixtures and gallery images:
  pending review.

### Phase 3 — P1 release evidence

- Evidence packet (this file).
- Version/metadata script run transcripts: pending.
- Dependency lock + SBOM evidence: pending.
- Wheel/sdist signing or recorded exception: pending.

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
