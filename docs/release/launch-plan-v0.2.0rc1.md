# Launch Plan — Lathe v0.2.0rc1

**Pre-release only.** This document describes the phased release plan for v0.2.0rc1.
Soft-launch and GA are explicitly out of scope for this release.

---

## Phases

### Phase 1 — Dogfood

**Objective:** verify release artifacts work end-to-end on the maintainer's own machine and
in CI before sharing with anyone external.

**Entry criteria:**
- `python -m pytest -q` passes on main branch with no skipped blocking tests.
- `lathe check examples/courier_drone.lth` exits 0.
- `lathe build examples/courier_drone.lth courier_drone --out dist` produces a certified artifact.
- CI release gate (GitHub Actions) passes on the release tag.
- CycloneDX SBOM attached to the GitHub Release draft.
- PyPI wheel installable from TestPyPI in a clean virtualenv.

**Exit criteria:**
- All entry criteria met and recorded in `docs/release/evidence-v0.2.0rc1.md`.
- No P0 issues open.
- Release checklist (`docs/release/release-checklist.md`) signed off.

**Rollback triggers:**
- Any entry criterion fails after tag is pushed — see `docs/release/rollback-plan-v0.2.0rc1.md`.

**Communication plan:**
- No external communication. Internal notes in `docs/release/evidence-v0.2.0rc1.md`.

**Owner:** Tal Merri  
**Backup:** requires-human: name a backup before public launch

---

### Phase 2 — Closed Beta

**Objective:** share with a small number of trusted users (target: ≤20) to validate install
and primary workflow on diverse environments before broader exposure.

**Entry criteria:**
- Phase 1 exit criteria met.
- Known-limitations.md reviewed and current.
- Minimum FAQ and install troubleshooting articles drafted (Phase 5 runbooks).
- On-call roster confirmed (`docs/ops/on-call.md`).
- Risk register reviewed (`docs/risk_register.md`) and no new P0-class risks open.

**Exit criteria:**
- At least 3 external testers confirm successful install and `lathe check` + `lathe build` run.
- No P0 issues outstanding.
- P1 issues triaged and either fixed or documented in known-limitations.md.
- Post-beta retrospective notes filed in `docs/release/evidence-v0.2.0rc1.md`.

**Rollback triggers:**
- Broken install reproduced across two or more tester environments — see `docs/release/rollback-plan-v0.2.0rc1.md`.
- Security issue reported by a beta tester.

**Communication plan:**
- Direct invite to selected testers via email / GitHub issue.
- Issue template: `beta-feedback` label; response SLA 3 business days.
- Status updates posted to the GitHub Discussion or pinned issue every 48 h while beta is open.

**Owner:** Tal Merri  
**Backup:** requires-human: name a backup before public launch

---

### Phase 3 — Soft Launch

**Out of scope for this release.** Required artifacts are tracked but launch will not
progress past closed beta until v0.2.0 final or later.

Artifacts to prepare (not blocking rc1):
- Public announcement draft.
- Godot AssetLib submission.
- Social/community posts (Discord, etc. — requires-human: community channels not yet open).
- PyPI public release (non-rc version).

**Owner:** Tal Merri  
**Backup:** requires-human: name a backup before soft launch

---

### Phase 4 — General Availability

**Out of scope for this release.** Required artifacts are tracked but launch will not
progress past closed beta until v0.2.0 final or later.

Artifacts to prepare (not blocking rc1):
- Legal/privacy sign-off (RISK-001 in risk register).
- Monetization path validated (RISK-010).
- Full runbook suite complete (Phase 5).
- Bus-factor mitigation in place (RISK-015).
- Backup on-call roster filled (all `requires-human` items resolved).

**Owner:** Tal Merri  
**Backup:** requires-human: name a backup before GA

---

## Re-review trigger

This plan must be reviewed no later than **2026-05-28** (T+30 post target launch date)
or on any of the following events:

- A P0 security or legal issue is identified.
- Closed beta exit criteria are not met within 14 days of beta start.
- A new requires-human gap is identified that has no named assignee.
- Risk register is updated with a new High/High risk.

Review owner: Tal Merri. Update `docs/release/evidence-v0.2.0rc1.md` with re-review outcome.
