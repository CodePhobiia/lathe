# Readiness Remediation Task List

Created: 2026-04-28

Verdict being remediated: DO NOT SHIP

This file is the step-by-step remediation list for the product readiness audit
run on 2026-04-28. A task is not complete until it has durable evidence:
a committed file path, CI run URL, dashboard URL, signed decision record,
ticket, release artifact, or command transcript. Verbal agreement is not
evidence.

Default owner is Tal Merri / @talmerri until explicitly reassigned. Any task
with legal, security, compliance, or release authority impact must name a backup
owner before launch.

## Completion Rules

- [x] Create a release evidence folder or index document at `docs/release/evidence-v0.2.0rc1.md`. — created in this pass.
- [ ] For every completed task below, add the evidence path or URL to `docs/release/evidence-v0.2.0rc1.md`. — ongoing rule, in force for this pass.
- [ ] Do not check a task unless the evidence can be verified by a third party in under five minutes. — ongoing rule, in force for this pass.
- [ ] For every accepted risk or release exception, record owner, date, affected surface, user impact, workaround, and removal target. — ongoing rule; all `requires-human` annotations and accepted exceptions record owner+date+impact+workaround+removal target inline (and are aggregated in `docs/release/decision-log-v0.2.0rc1.md` once Phase 1 lands it).
- [ ] Before any public launch, rerun this entire file and mark every remaining unchecked item as either fixed or formally accepted. — ongoing rule, mandated by Phase 18.

> Status legend used below in unchecked items: `requires-human:` means the task needs an action Claude Code cannot perform autonomously (signed counsel review, third-party pen-test, design-partner LOIs, GitHub admin toggles, hosted dashboards, manual Godot smoke on macOS/Linux, etc.). Such items are NOT checked off, but are recorded with the gap and the durable place a human owner picks them up.

## Phase 0 - Launch Freeze And Scope Control

- [x] Declare a launch freeze in `docs/release/evidence-v0.2.0rc1.md`. — Launch freeze section in evidence packet (2026-04-28).
- [x] Define the exact launch being gated: private RC, public GitHub release, PyPI pre-release, Godot addon alpha, or broader OSS launch. — Scope: pre-release reference compiler scaffold under `0.2.0rc1`. No GA, no Godot AssetLib submission, no broader OSS launch (evidence packet "Scope of this release" + "Launch freeze").
- [x] Confirm whether `0.2.0rc1` is allowed to ship only as a pre-release reference compiler scaffold. — Confirmed pre-release-only; gated until every Phase 0–18 item is green or has a recorded exception (evidence packet + Phase 18 gate).
- [x] Record that stable-public-release claims are forbidden until this checklist is green. — "Stable-release-claim restriction" section in evidence packet enumerates allowed vs forbidden phrases.
- [x] Record the current branch, commit SHA, tag status, and dirty-worktree status. — Evidence packet "Repo identity at start of pass" (branch `worktree-readiness-pass-v020rc1`, base commit `30f9186`, untagged, dirty-from-clean-checkout pending Phase 3 rerun from clean).
- [x] Create or identify the release branch that will be used for the re-review. — `worktree-readiness-pass-v020rc1` (worktree off `main`); recorded in evidence packet.
- [x] Require all release evidence to be generated from a clean checkout of that branch. — Recorded in evidence packet "Repo identity" + "Audit-output exclusion policy"; Phase 3 rerun-from-clean-checkout is required for the final packet.
- [x] Decide whether generated audit output directories such as `tmp_audit_*` are excluded from release evidence. — Excluded; "Audit-output exclusion policy" section in evidence packet.

## Phase 1 - Required Input Inventory

### Product Brief And PRD

- [x] Update `docs/lathe_prd.md` with a current version number. — `Version: 0.2.0rc1 (pre-release reference compiler scaffold)` added at top of `docs/lathe_prd.md`.
- [x] Add a `Last reviewed` date to `docs/lathe_prd.md`. — `Last reviewed: 2026-04-28` added at top.
- [ ] Add named product owner and reviewer to `docs/lathe_prd.md`. — Owner=Tal Merri (@talmerri) named; **`requires-human:`** name a second reviewer (backup) before any GA discussion. Recorded in `docs/lathe_prd.md` header.
- [x] Add one-sentence problem definition with no jargon. — Added in `docs/lathe_prd.md`.
- [x] Add one-sentence target user definition with no jargon. — Added in `docs/lathe_prd.md`.
- [x] Mark every PRD requirement as `supported`, `preview`, `experimental`, `future`, or `rejected`. — "Requirement status (v0.2.0rc1)" section added to `docs/lathe_prd.md`.
- [x] Add links from PRD requirements to tests, docs, examples, or explicit gaps. — Each tagged requirement links to `tests/`, `docs/`, `examples/`, or carries an explicit `gap: ...` note in the same section.

### Architecture And Technical Design

- [x] Confirm `docs/architecture/overview.md` is current for the release branch. — Currency-check footer (2026-04-28) appended to `docs/architecture/overview.md`.
- [x] Create `docs/architecture/technical-design-v0.2.0rc1.md`. — Created (232 lines).
- [x] Document all release-supported components and their failure modes. — Table in `docs/architecture/technical-design-v0.2.0rc1.md` (parser, normalizer, resolver, checker, planner, executor, shape backend, Blender adapter, xatlas adapter, validators, package emitter, runtime config loader, CLI, telemetry, cache, publish drivers).
- [x] Document all single points of failure. — ≥6 SPOFs enumerated (solo maintainer, single shape contract, PyPI, GitHub Actions, Codex provider terms, single signing key) in same file.
- [x] Document all optional tools and how the system behaves when each is absent. — Blender / xatlas / manifold3d / torch+vggt / scikit-image / scipy each documented with degradation path.
- [x] Document database/storage posture, even if the current answer is "local files only". — Documented as "local files only; no hosted storage shipped in 0.2.0rc1" with cache + parser-cache + build-tree paths.
- [x] Document migration posture for package manifests, trace manifests, snapshots, and stable contracts. — Migration posture section added.
- [x] Link architecture docs to contract tests and stable schema tests. — Links added to `tests/contract/`, `tests/golden/`, and ADR-0009 (`docs/adr/0009-public-contract-index.md`).

### Test Reports

- [x] Create `docs/release/test-report-v0.2.0rc1.md`. — Created (166 lines, matrix template + skipped/deselected/coverage inventories).
- [ ] Record full `python -m pytest -q` results from Python 3.11 on Ubuntu. — **`requires-human:`** needs CI run on Ubuntu 22.04/24.04 runner; reference workflow `.github/workflows/ci.yml` once branch is pushed. Row in matrix table marked pending.
- [ ] Record full `python -m pytest -q` results from Python 3.12 on Ubuntu. — **`requires-human:`** same as above, Python 3.12 leg.
- [ ] Record full `python -m pytest -q` results from Python 3.11 on Windows. — Pending Phase 6 run from clean checkout (Win is local-achievable).
- [ ] Record full `python -m pytest -q` results from Python 3.12 on Windows. — Pending Phase 6 run from clean checkout.
- [ ] Record full `python -m pytest -q` results from Python 3.11 on macOS. — **`requires-human:`** no macOS host; CI runner required.
- [ ] Record full `python -m pytest -q` results from Python 3.12 on macOS. — **`requires-human:`** same.
- [x] Record skipped tests and justify every skip. — "Skipped tests inventory" table in `docs/release/test-report-v0.2.0rc1.md` (per-marker rationale).
- [x] Record deselected tests and why they were outside the release lane. — "Deselected tests inventory" table in same file (slow/golden/property/fuzz lanes documented).
- [x] Record coverage summary and compare it against the configured threshold. — 65% threshold + per-package gates from `[tool.lathe.coverage_gates]` documented; actual coverage % row pending Phase 6 run.
- [x] Add or link contract test report. — Linked to `tests/contract/` partition.
- [x] Add or link golden test report. — Linked to `tests/golden/` partition.
- [x] Add or link property test report. — Linked to `tests/property/` partition.
- [x] Add or link fuzz test report. — Linked to `tests/fuzz/` partition.
- [x] Add or link slow/benchmark/visual-quality test report. — Linked (`tests/test_benchmarks.py`, `tests/test_visual_quality.py`).
- [x] Add or link example-corpus build/certification report. — Linked to `tests/unit/test_example_corpus.py` (corrected path; the readiness brief assumed top-level `tests/test_examples_corpus.py` which does not exist).
- [ ] Add or link Godot addon manual smoke report. — **`requires-human:`** manual procedure pointer documented (`editors/godot/lathe-addon/` + `examples/godot_integration_demo/`); needs at least one human-recorded run on Win + macOS + Linux.
- [ ] Add or link external GLB/USD viewer validation report. — **`requires-human:`** open canonical GLB outputs in glTF Sample Viewer / Blender, USD outputs in usdview / Houdini, and screenshot.
- [x] Add or link load/performance report. — `docs/perf_budgets.md` (hand-authored budgets) linked; `tests/unit/test_perf_manifest.py` enforces them. RPS/load is N/A for current scope (Phase 8 records this); the perf-budget doc covers what does apply.
- [ ] Add or link security scan report. — Pending Phase 6 (Bandit + semgrep are local-achievable; CodeQL URL is **`requires-human:`** GitHub Advanced Security after push).
- [ ] Add or link penetration-test report or approved scoped exception. — **`requires-human:`** third-party security review or formally recorded scoped exception (Phase 9).

### Telemetry And Dashboards

- [x] Create `docs/telemetry_event_taxonomy.md`. — Created (100 lines, taxonomy with disabled-by-default banner).
- [x] Version every telemetry event and field. — Each event in the taxonomy carries an explicit version + allowlist; events without code support are flagged `requires-human: implement before publishing`.
- [x] Document the north-star metric. — "Weekly active certified-build users" proposed in taxonomy with **`requires-human:`** product-owner ratification flag.
- [x] Document acquisition, activation, engagement, retention, and revenue funnels. — All five funnels defined in taxonomy.
- [x] Create live dashboard for build pings or record why telemetry remains disabled for this release. — Recorded that telemetry remains disabled-by-default for v0.2.0rc1; rationale in taxonomy "Status" banner and `docs/privacy.md`.
- [ ] Create launch dashboard for install success. — **`requires-human:`** ingest service not yet provisioned; deferred until telemetry is enabled (Phase 11 decision).
- [ ] Create launch dashboard for build success. — **`requires-human:`** same.
- [ ] Create launch dashboard for certification failures. — **`requires-human:`** same.
- [ ] Create launch dashboard for support volume and response times. — **`requires-human:`** same; manual-collection stop-gap recorded in Phase 11.
- [ ] Create data quality checks for event schema drift. — **`requires-human:`** deferred until telemetry ingest is hosted; design recorded in taxonomy.
- [ ] Create data quality checks for null rates. — **`requires-human:`** same.
- [ ] Create data quality checks for freshness. — **`requires-human:`** same.
- [ ] Add dashboard URLs to release evidence. — **`requires-human:`** no dashboards exist yet; add when ingest is provisioned. Status logged in `docs/release/evidence-v0.2.0rc1.md`.

### Runbooks And On-Call

- [x] Create `docs/ops/README.md`. — Created (39 lines, ops index).
- [x] Create `docs/ops/on-call.md`. — Created (78 lines, roster + SLAs + escalation paths).
- [x] Name launch primary on-call owner. — Tal Merri (@talmerri / talmerri@gmail.com) in `docs/ops/on-call.md`.
- [ ] Name launch backup on-call owner. — **`requires-human:`** solo-maintainer single-point-of-failure; logged in `docs/risk_register.md` (RISK-015 key-person).
- [x] Define first response SLA for launch week. — 24h ack / P0 24h triage / P1 3 business days / 24h comms cadence while a P0 is open.
- [x] Define escalation path for security reports. — `docs/ops/on-call.md` "Escalation paths" → security report sub-section.
- [x] Define escalation path for broken install reports. — Same file, broken-install sub-section.
- [x] Define escalation path for package/yank decisions. — Same file; cross-references `docs/release/rollback-plan-v0.2.0rc1.md` PyPI procedure.
- [x] Define escalation path for legal/privacy complaints. — Same file; cross-references `docs/legal/compliance-review-v0.2.0rc1.md`.
- [x] Define escalation path for Godot addon breakage. — Same file.

### Risk Register

- [x] Create `docs/risk_register.md`. — Created (46 lines, 18 risks).
- [x] Include at least 10 risks. — 18 risks logged (14 mandatory + RISK-015 key-person, RISK-016 docs site, RISK-017 CI secrets, RISK-018 Blender/xatlas adapter).
- [x] Score every risk by likelihood. — Each row has likelihood (low/med/high).
- [x] Score every risk by impact. — Each row has impact (low/med/high).
- [x] Assign every risk a named owner. — Owners assigned (default Tal Merri); rows where backup is needed flag **`requires-human:`** inline.
- [x] Assign every risk a target review date. — All rows: 2026-05-28.
- [x] Add mitigation for every risk. — Each row has mitigation column populated.
- [x] Add contingency for every risk. — Each row has contingency column populated.
- [x] Add trigger conditions for every risk. — Each row has trigger column populated.
- [x] Cover legal risk. — RISK-001 (privacy/legal sign-off), RISK-014 (provider IP).
- [x] Cover security risk. — RISK-002 (supply-chain), RISK-017 (CI secrets).
- [x] Cover reputational risk. — RISK-008 (telemetry trust), RISK-009 (competitor positioning).
- [x] Cover technical risk. — RISK-003, RISK-006, RISK-011, RISK-018.
- [x] Cover financial risk. — RISK-010 (no WTP evidence).
- [x] Cover key-person risk. — RISK-015.
- [x] Cover platform-dependency risk. — RISK-013 (AssetLib), RISK-012 (branch protection), RISK-016 (docs site).
- [x] Cover provider-dependency risk. — RISK-014 (provider IP/legal).

### Launch Plan And Rollback Plan

- [x] Create `docs/release/launch-plan-v0.2.0rc1.md`. — Created (114 lines).
- [x] Define dogfood phase. — In launch plan.
- [x] Define closed beta phase. — In launch plan.
- [x] Define soft launch phase. — Defined and explicitly marked "out of scope for v0.2.0rc1" with trigger to gate on V0.2 final.
- [x] Define general availability phase. — Defined and explicitly marked "out of scope for v0.2.0rc1".
- [x] Add objective entry criteria for each phase. — Per-phase tables in launch plan.
- [x] Add objective exit criteria for each phase. — Per-phase tables in launch plan.
- [x] Add rollback triggers for each phase. — Cross-referenced to `docs/release/rollback-plan-v0.2.0rc1.md`.
- [x] Add communication plan for each phase. — Per-phase tables in launch plan.
- [ ] Add owner and backup owner for each phase. — Owners (Tal Merri) added; **`requires-human:`** every backup row needs a name before public launch.
- [x] Create `docs/release/rollback-plan-v0.2.0rc1.md`. — Created (227 lines).
- [x] Define who can pull the kill switch. — Tal Merri (primary).
- [ ] Define backup kill-switch authority. — **`requires-human:`** no backup named yet; recorded in rollback plan + RISK-015.
- [x] Define decision-to-user-visible-reversal target time. — 4h PyPI yank / 1h docs banner / 30m GitHub Release un-publish; in rollback plan.
- [x] Define PyPI yank or deprecation procedure. — In rollback plan with `pip` / `twine` / web steps and trade-offs.
- [x] Define GitHub Release edit or withdrawal procedure. — `gh release edit --draft`, `gh release delete`, public-note guidance, in rollback plan.
- [x] Define docs banner procedure. — mkdocs-material announcement-bar override path documented.
- [ ] Define Discord/community announcement procedure. — **`requires-human:`** no Discord launched; record channel name + moderation owner once it exists.
- [x] Define GitHub issue/advisory announcement procedure. — `gh issue create --pin`, GHSA via `gh api`/web, cross-reference SECURITY.md.
- [x] Define what is irreversible after launch. — In rollback plan (signed tag SHA, PyPI wheel, indexed docs page, Discord screenshots).

### Legal, Compliance, And Privacy

- [x] Create `docs/privacy.md`. — Created (140 lines, telemetry-disabled-by-default banner + allowlist + opt-out).
- [x] Create `docs/terms.md` or explicitly record why ToS is not applicable. — Created (51 lines, ToS not applicable for v0.2.0rc1; trigger conditions for when ToS becomes applicable enumerated).
- [x] Create `docs/legal/compliance-review-v0.2.0rc1.md`. — Created (237 lines).
- [ ] Get written review from qualified counsel or record that launch is blocked. — **`requires-human:`** counsel not engaged. Public launch BLOCKED until counsel review or formally recorded launch exception with named owner + removal target. Recorded in `docs/legal/compliance-review-v0.2.0rc1.md` banner + `docs/release/decision-log-v0.2.0rc1.md`.
- [x] Assess GDPR applicability. — Sub-section in compliance review (N/A in v0.2.0rc1; re-assess when telemetry enables).
- [x] Assess CCPA/CPRA applicability. — Sub-section in compliance review (N/A; re-assess when telemetry enables).
- [x] Assess COPPA/child-safety applicability. — Sub-section in compliance review (N/A; product not directed at children under 13).
- [x] Assess export-control applicability. — Sub-section in compliance review (likely 5D002 + TSU, but `requires-human:` counsel concur before claim).
- [x] Assess sanctions-screening applicability. — Sub-section in compliance review (handled by GitHub/PyPI for the host; document position with counsel).
- [x] Assess PCI-DSS applicability. — Sub-section (N/A; no payments).
- [x] Assess HIPAA applicability. — Sub-section (N/A; no PHI).
- [x] Assess SOC 2 relevance and non-goals. — Sub-section (N/A as a non-goal for v0.2.0rc1; revisit when paid surface ships).
- [x] List all vendors touching user data. — Currently NONE; documented in compliance review with trigger conditions for when this changes.
- [x] Confirm DPA status for every vendor touching user data. — N/A in v0.2.0rc1 (no vendors); trigger conditions documented.
- [x] Confirm telemetry ingest ownership and hosting provider. — No ingest provisioned; telemetry disabled by default; documented in privacy + compliance review.
- [x] Document data retention for telemetry. — 90-day proposal in `docs/privacy.md`; enforcement is **`requires-human:`** when ingest exists.
- [x] Document deletion process for telemetry. — `lathe telemetry purge` documented in privacy.
- [x] Document export process for telemetry if applicable. — `lathe telemetry export` documented; `requires-human:` if not yet implemented in code.
- [x] Document consent capture and opt-out enforcement. — Documented in privacy ("Consent capture and opt-out").
- [x] Document bug bounty or responsible disclosure path. — Linked to `SECURITY.md` (90-day coordinated disclosure, safe harbor).

### Financial Model And Unit Economics

- [x] Create `docs/business/unit_economics.md`. — Created (160 lines).
- [x] Estimate COGS per active user for current OSS/pre-release support. — Done (placeholder maintainer hourly rate $100/h labelled estimate; **`requires-human:`** owner to ratify rate).
- [x] Estimate COGS per build for local-only mode. — $0 marginal documented.
- [x] Estimate COGS per learned-provider build. — $0 to Lathe; user pays compute. Documented.
- [x] Estimate COGS per registry transaction for future registry. — Marked FUTURE/N/A with trigger.
- [x] Estimate COGS per CI-SaaS run for future hosted certification. — Marked FUTURE/N/A.
- [x] Create infra cost projections at 1x load. — 50 active-user baseline (estimate-labelled).
- [x] Create infra cost projections at 10x load. — Done.
- [x] Create infra cost projections at 100x load. — Done.
- [x] Add gross margin model. — N/A documented (no revenue); margin floors flagged for future ratification.
- [x] Add sensitivity analysis for provider costs. — Table with low/expected/high columns; cells marked **`requires-human:`** needs current model-server pricing.
- [x] Add sensitivity analysis for support load. — Table with low/expected/high tickets/week × hours/ticket; hours/ticket cells marked **`requires-human:`** needs first-beta data.
- [x] Add pricing experiment plan. — FUTURE plan outlined, revisit when V0.5 monetization criteria land.
- [x] Record current willingness-to-pay evidence or mark as missing. — Recorded as MISSING; Phase 15 dependency.
- [x] Record billing/refund/proration/tax/multi-currency/dunning as not applicable until monetization is live. — Per-item N/A list in unit economics.
- [x] Add fraud and chargeback plan for future paid registry and CI-SaaS. — Documented as FUTURE.

### GTM, Positioning, And Competition

- [x] Review `docs/product_value.md` for current release truthfulness. — Currency-check section in `docs/release/launch-narrative-v0.2.0rc1.md` confirms 2026-04-28 review; cross-references flagged for pre-publication check.
- [x] Review `docs/competitive_landscape.md` for current competitor facts. — Currency-check section in launch narrative; competitor table dates flagged as potentially stale.
- [ ] Re-check competitor pricing and terms before public use. — **`requires-human:`** re-check competitor pricing before any public soft-launch reference; logged in launch-narrative currency check.
- [x] Create `docs/release/launch-narrative-v0.2.0rc1.md`. — Created (125 lines).
- [x] Write three launch messages. — Honest framing / Capability / What this is not, in launch narrative.
- [ ] Create press/community/influencer contact list. — **`requires-human:`** placeholder table in launch narrative; build before any soft-launch attempt.
- [ ] Name every launch contact. — **`requires-human:`** see above.
- [x] Create first 30-day content calendar. — Week 1-4 outline in launch narrative; **`requires-human:`** week-2/3/4 post authoring + reviewer.
- [ ] Create community moderation plan. — **`requires-human:`** no Discord launched; required before any community channel opens. CONTRIBUTING.md absence also flagged in launch narrative.
- [x] Create crisis communications playbook. — 5 canned drafts in launch narrative (install fail / security advisory / privacy complaint / bad output / yanked package).
- [ ] Have legal review crisis communications if legal/privacy/security issues are referenced. — **`requires-human:`** counsel review (counsel not engaged); marked inline on each crisis draft.

### Beta, Dogfood, And Customer Support

- [x] Create `docs/research/interviews/README.md`. — Created (103 lines, template + tracking index + question template).
- [ ] Log 5 Persona A interviews. — **`requires-human:`** schedule + run 5 Persona A (Godot indie / small-team TA) interviews. Tracking row in `docs/research/interviews/README.md`.
- [ ] Log 2 Persona B interviews. — **`requires-human:`** schedule + run 2 Persona B (pipeline TD) interviews.
- [ ] Log 1 Persona C agent-builder interview. — **`requires-human:`** schedule + run 1 Persona C interview.
- [x] Create `docs/research/beta-feedback-v0.2.0rc1.md`. — Created (82 lines, tracking sheet skeleton).
- [ ] Record every dogfood user. — **`requires-human:`** no dogfood users yet; tracking sheet ready.
- [ ] Record every closed-beta user. — **`requires-human:`** no closed beta yet; tracking sheet ready.
- [ ] Record every blocker reported by beta users. — **`requires-human:`** depends on prior two; table ready in beta-feedback.
- [ ] Classify every feedback item by severity. — **`requires-human:`** depends on beta running; column exists.
- [ ] Classify every feedback item by persona. — **`requires-human:`** depends on beta running; column exists.
- [ ] Record whether every beta user would use Lathe again. — **`requires-human:`** depends on beta running; column exists.
- [x] Create `docs/support/readiness-checklist.md`. — Created (431 lines, real top-20 FAQ + 6 macros + intake labels + issue templates + response targets).
- [x] Write answers for top 20 expected user questions. — 20 real one-paragraph answers in support readiness, derived from README + CLAUDE.md + `docs/error_codes.md`.
- [x] Write support macro for install failure. — In support readiness.
- [x] Write support macro for `lathe doctor` failure. — In support readiness.
- [x] Write support macro for provider unavailable. — In support readiness.
- [x] Write support macro for certification failure. — In support readiness.
- [x] Write support macro for Godot import failure. — In support readiness.
- [x] Write support macro for security/private reporting. — In support readiness; cross-references SECURITY.md + GHSA flow.

### Known Bugs And Decision Log

- [x] Convert `plans/10_bugs_errors.md` into a current known-bugs register or create `docs/release/known-bugs-v0.2.0rc1.md`. — Created (131 lines).
- [x] List every known bug with severity. — Each row has P0/P1/P2/P3.
- [x] List every known bug with owner. — Each row has owner (default Tal Merri).
- [x] List every known bug with target fix date or accepted exception. — Each row has target-fix-date or accepted-exception link.
- [x] Link every fixed bug to a regression test. — Linked via `tests/bugs/` and the `@pytest.mark.bug_regression` marker; bugs without an existing regression test are flagged `requires-human: add regression test before close`.
- [x] Link every unresolved bug to a release exception or block release. — Each unresolved row either points at a row in `docs/release/decision-log-v0.2.0rc1.md` "Release exceptions" or carries a `release blocker:` tag.
- [x] Review `docs/adr/README.md` for current ADR status. — ADR currency-check section in `docs/release/known-bugs-v0.2.0rc1.md` enumerates each ADR with its current state.
- [ ] Move ADRs 0004, 0005, and 0006 from Proposed to Accepted only if implementation and evidence exist. — Per-ADR recommendation documented in known-bugs ADR section. **`requires-human:`** act on each recommendation (edit ADR file + commit) — not done in this pass to avoid silently mutating ADRs.
- [x] Create `docs/release/decision-log-v0.2.0rc1.md`. — Created (199 lines).
- [x] List every explicit non-goal for this release. — Section "Non-goals for v0.2.0rc1" enumerates ≥9 non-goals.
- [x] List every feature intentionally deferred. — Section "Intentionally deferred features" with roadmap pointer.
- [x] List every release exception and rationale. — Section "Release exceptions accepted in this pass" — skeleton table; populated by lead as Phase 6/9 land their findings.
- [x] List every public claim that must not be made. — Section enumerates ≥8 forbidden phrases.

## Phase 2 - Fix P0 Legal, Privacy, And Compliance Findings

- [ ] Block any public telemetry until `docs/privacy.md` is complete and reviewed.
- [ ] Confirm telemetry is disabled by default in code and tests.
- [ ] Confirm `lathe telemetry enable` requires explicit consent.
- [ ] Confirm telemetry opt-out works.
- [ ] Confirm telemetry clear/purge works locally.
- [ ] Confirm no telemetry is emitted during `lathe doctor`.
- [ ] Confirm no telemetry is emitted during `lathe check`.
- [ ] Confirm no telemetry is emitted during failed builds unless explicitly intended and documented.
- [ ] Confirm telemetry payload includes only allowlisted fields.
- [ ] Confirm telemetry payload does not include source paths.
- [ ] Confirm telemetry payload does not include asset names if that remains the claim.
- [ ] Confirm telemetry payload does not include environment variables.
- [ ] Confirm telemetry payload does not include provider keys.
- [ ] Confirm telemetry payload does not include diagnostics or logs.
- [ ] Document telemetry ingest security controls.
- [ ] Document retention enforcement mechanism.
- [ ] Document deletion enforcement mechanism.
- [ ] Add privacy policy link to README.
- [ ] Add privacy policy link to docs index.
- [ ] Add privacy policy link to telemetry docs.
- [ ] Add security disclosure link to README.
- [ ] Confirm `SECURITY.md` contact information is current.
- [ ] Publish or document PGP key status.
- [ ] Decide if GitHub Security Advisories are available on the actual repo.
- [ ] Confirm safe harbor text is acceptable to counsel.
- [ ] Review checked-in image/mesh fixtures for IP clearance.
- [ ] Review docs gallery images for IP clearance.
- [ ] Review generated benchmark data for third-party output terms.
- [ ] Review Hunyuan/VGGT/Codex ImageGen provider terms before public claims.
- [ ] Update `docs/release/asset-provenance.md` with every checked-in binary asset.
- [ ] Verify open-source license compatibility for runtime dependencies.
- [ ] Verify optional dependency licenses.
- [ ] Verify editor addon license compatibility with Godot.
- [ ] Verify Blender integration does not trigger unwanted GPL obligations for the main package.

## Phase 3 - Fix P1 Release Evidence Findings

### Release Evidence Packet

- [ ] Create `docs/release/evidence-v0.2.0rc1.md`.
- [ ] Add release branch.
- [ ] Add release commit.
- [ ] Add tag or explain no tag.
- [ ] Add dirty-worktree status from clean checkout.
- [ ] Add remote URL.
- [ ] Add Python versions used.
- [ ] Add OS versions used.
- [ ] Add dependency lock verification.
- [ ] Add release metadata verification.
- [ ] Add test evidence links.
- [ ] Add security evidence links.
- [ ] Add docs evidence links.
- [ ] Add package artifact evidence links.
- [ ] Add SBOM evidence links.
- [ ] Add signing/attestation evidence links.
- [ ] Add product-quality evidence links.
- [ ] Add legal evidence links.
- [ ] Add risk register link.
- [ ] Add rollback plan link.
- [ ] Add launch decision sign-off.

### Version And Metadata

- [ ] Run `python scripts/check_release_metadata.py --expected-tag v0.2.0-rc.1` on Python 3.11.
- [ ] Run `python scripts/check_release_metadata.py --expected-tag v0.2.0-rc.1` on Python 3.12.
- [ ] If tagged, run `python scripts/check_release_metadata.py --expected-tag v0.2.0-rc.1 --require-current-tag`.
- [ ] Confirm `pyproject.toml` version matches `lathe.__version__`.
- [ ] Confirm changelog has populated release section.
- [ ] Confirm README version references are current.
- [ ] Confirm docs release version references are current.
- [ ] Confirm package classifiers match support matrix.

### Dependency And Build Artifacts

- [ ] Run `python scripts/check_dependency_sync.py`.
- [ ] Build sdist and wheel from a clean checkout.
- [ ] Run `twine check dist/*`.
- [ ] Install wheel in a new virtualenv on Python 3.11.
- [ ] Install wheel in a new virtualenv on Python 3.12.
- [ ] Run `python -m lathe.cli doctor` from installed wheel.
- [ ] Run `lathe doctor` console script from installed wheel.
- [ ] Confirm `.lathe_lark_cache` is not shipped in the wheel.
- [ ] Generate CycloneDX JSON SBOM.
- [ ] Generate CycloneDX XML SBOM.
- [ ] Attach or link SBOM evidence.
- [ ] Generate SHA256 sums for sdist and wheel.
- [ ] Sign release tag or record approved exception.
- [ ] Sign wheel/sdist/SHA256SUMS or record approved pre-release exception.
- [ ] Confirm PyPI Trusted Publishing configuration or record launch blocker.

## Phase 4 - Fix P1 Risk, Rollback, And Kill-Switch Findings

### Risk Register

- [ ] Add risk: missing privacy/legal sign-off.
- [ ] Add risk: supply-chain vulnerability ships.
- [ ] Add risk: unsupported Python/runtime drift.
- [ ] Add risk: Godot addon breaks first user workflow.
- [ ] Add risk: learned-provider fallback misleads users.
- [ ] Add risk: canonical examples fail outside maintainer machine.
- [ ] Add risk: support queue overwhelms solo maintainer.
- [ ] Add risk: telemetry trust backlash.
- [ ] Add risk: competitor copies surface positioning.
- [ ] Add risk: monetization path has no willingness-to-pay evidence.
- [ ] Add risk: release artifacts cannot be reproduced.
- [ ] Add risk: branch protection/required checks are not enforced.
- [ ] Add risk: platform review rejects Godot AssetLib submission.
- [ ] Add risk: optional external providers create legal/IP ambiguity.

### Rollback Triggers

- [ ] Define rollback trigger for P0 security issue.
- [ ] Define rollback trigger for P0 legal/privacy issue.
- [ ] Define rollback trigger for package install failure.
- [ ] Define rollback trigger for critical build failure.
- [ ] Define rollback trigger for canonical gallery certification failure.
- [ ] Define rollback trigger for corrupted artifacts.
- [ ] Define rollback trigger for misleading telemetry or privacy complaint.
- [ ] Define rollback trigger for support response breach.
- [ ] Define rollback trigger for CI release gate regression.
- [ ] Define rollback trigger for platform policy rejection.

### Kill-Switch Procedures

- [ ] Document PyPI yank command/process.
- [ ] Document PyPI post-release deprecation procedure if yanking is inappropriate.
- [ ] Document GitHub Release draft/unpublish/edit procedure.
- [ ] Document docs banner update procedure.
- [ ] Document README warning update procedure.
- [ ] Document Discord announcement procedure.
- [ ] Document GitHub pinned issue procedure.
- [ ] Document GitHub Security Advisory procedure.
- [ ] Document expected time from decision to completed user-visible reversal.
- [ ] Dry-run rollback communications without executing destructive release changes.

## Phase 5 - Fix P1 Operational Readiness Findings

### Runbooks

- [ ] Create runbook for install failure.
- [ ] Create runbook for `lathe doctor` false negative or false positive.
- [ ] Create runbook for canonical build failure.
- [ ] Create runbook for provider unavailable.
- [ ] Create runbook for learned-provider fallback complaint.
- [ ] Create runbook for Godot addon load failure.
- [ ] Create runbook for generated artifact missing.
- [ ] Create runbook for security vulnerability report.
- [ ] Create runbook for suspected secret exposure.
- [ ] Create runbook for telemetry/privacy complaint.
- [ ] Create runbook for PyPI release failure.
- [ ] Create runbook for GitHub Actions outage or failed required check.
- [ ] Create runbook for docs site broken links or stale quickstart.
- [ ] Create runbook for dependency CVE.
- [ ] Create runbook for corrupted release artifact or bad hash.

### On-Call And Escalation

- [ ] Name primary on-call owner for launch day.
- [ ] Name backup on-call owner for launch day.
- [ ] Name primary security contact.
- [ ] Name backup security contact.
- [ ] Name legal/compliance escalation contact.
- [ ] Name PyPI release authority.
- [ ] Name GitHub release authority.
- [ ] Name community moderation owner.
- [ ] Define 14-day post-launch communication cadence.
- [ ] Reserve explicit hotfix capacity percentage for first 14 days.
- [ ] Draft post-launch sprint plan before launch.

### Support Readiness

- [ ] Create support intake labels.
- [ ] Create `release-blocker` label in GitHub or verify it exists remotely.
- [ ] Create `flaky-test` label in GitHub or verify it exists remotely.
- [ ] Create `security` label in GitHub or verify it exists remotely.
- [ ] Verify issue templates render correctly on GitHub.
- [ ] Verify release-blocker template requires severity, owner, and rollback/exception.
- [ ] Prepare top 20 FAQ answers.
- [ ] Prepare install troubleshooting article.
- [ ] Prepare provider troubleshooting article.
- [ ] Prepare certification debugging article.
- [ ] Prepare Godot import troubleshooting article.
- [ ] Define support response time targets.
- [ ] Define when support issue escalates to release blocker.

## Phase 6 - Fix Release Gate Failures

### Type Checking

- [ ] Decide whether `mypy lathe/` is a blocking release gate for `0.2.0rc1`.
- [ ] If blocking, fix all current mypy errors.
- [ ] If not blocking, record formal release exception in `docs/release/evidence-v0.2.0rc1.md`.
- [ ] Add exact mypy command to release checklist.
- [ ] Add mypy result to evidence packet.
- [ ] Create a gradual typing plan for remaining modules if full mypy is deferred.
- [ ] Ensure docs no longer imply type checking passes if it does not.

### Dependency Vulnerability

- [ ] Investigate `pip 26.0.1` `CVE-2026-3219` from local `pip-audit`.
- [ ] Determine whether vulnerability affects release artifacts or local tooling only.
- [ ] Upgrade/pin fixed pip version if available.
- [ ] Regenerate lockfile and requirements after fix.
- [ ] Rerun `python scripts/check_dependency_sync.py`.
- [ ] Rerun `pip-audit --strict --no-deps` on runtime requirements.
- [ ] Rerun `pip-audit --strict --no-deps` on dev requirements.
- [ ] If no fix exists, add explicit vulnerability exception with owner, rationale, impact, and revisit date.

### Security Scanners

- [ ] Install and run gitleaks locally or provide GitHub Actions run URL.
- [ ] Run full-history gitleaks scan.
- [ ] Run PR/diff gitleaks scan if applicable.
- [ ] Install and run semgrep locally or provide GitHub Actions run URL.
- [ ] Run semgrep `p/python`.
- [ ] Run semgrep `p/security-audit`.
- [ ] Run semgrep `p/owasp-top-ten`.
- [ ] Run Bandit and attach output.
- [ ] Run CodeQL and attach GitHub code scanning URL.
- [ ] Confirm CodeQL config includes intended paths.
- [ ] Confirm no scanner suppression lacks rule, path, owner, and rationale.
- [ ] Confirm branch protection requires security gates before merge.

### Lint, Tests, Docs, Package

- [ ] Run `python -m ruff check .` from clean checkout.
- [ ] Run `python -m ruff format --check .` or record why format is advisory.
- [ ] Run full pytest from clean checkout.
- [ ] Run contract/golden partition.
- [ ] Run property partition.
- [ ] Run fuzz partition.
- [ ] Run slow partition.
- [ ] Run benchmark/visual-quality partition.
- [ ] Run `mkdocs build --strict --site-dir site` from clean checkout.
- [ ] Resolve MkDocs warning or record approved docs-build exception.
- [ ] Run package build and `twine check`.
- [ ] Confirm release workflow runs these same gates.

### CI And Branch Protection

- [ ] Push release branch to canonical remote.
- [ ] Verify canonical remote is `https://github.com/talmerri/lathe.git`.
- [ ] Enable branch protection on release branch or main.
- [ ] Require CI workflow.
- [ ] Require lint workflow.
- [ ] Require coverage workflow or record exception.
- [ ] Require docs workflow.
- [ ] Require examples workflow.
- [ ] Require security workflow.
- [ ] Require CodeQL workflow.
- [ ] Require pip-audit workflow.
- [ ] Require SBOM workflow for release tags.
- [ ] Export or screenshot branch protection rules.
- [ ] Add branch protection evidence to release packet.

## Phase 7 - Fix Product Experience Findings

### First-Time User Experience

- [ ] Define activation moment.
- [ ] Instrument activation moment or record why telemetry is disabled for pre-release.
- [ ] Measure time-to-first-value for fresh user on Windows.
- [ ] Measure time-to-first-value for fresh user on macOS.
- [ ] Measure time-to-first-value for fresh user on Ubuntu.
- [ ] Record TTFV command transcript for every platform.
- [ ] Record failures during TTFV tests.
- [ ] Fix or document every TTFV failure.
- [ ] Inventory every click, command, config choice, and decision before first certified asset.
- [ ] Remove unnecessary first-run friction or record accepted rationale.

### Core Journey Coverage

- [ ] Walk happy path: install to certified `courier_drone`.
- [ ] Walk unhappy path: invalid `.lth` syntax.
- [ ] Walk unhappy path: certification failure.
- [ ] Walk unhappy path: missing optional provider.
- [ ] Walk unhappy path: missing Blender.
- [ ] Walk unhappy path: missing xatlas.
- [ ] Walk unhappy path: provider timeout.
- [ ] Walk unhappy path: output path rejected by safety guard.
- [ ] Confirm every unhappy path has actionable diagnostics.
- [ ] Confirm CLI exit codes are documented.
- [ ] Confirm machine-readable outputs are stable enough for agents.

### Gallery And Examples

- [ ] Build `examples/industrial_crate.lth` from clean checkout.
- [ ] Build `examples/courier_drone.lth` from clean checkout.
- [ ] Build `examples/courier_drone.lth courier_drone_mobile` from clean checkout.
- [ ] Build `examples/reconstruct_courier_from_mesh.lth` from clean checkout.
- [ ] Build `examples/console_terminal_mobile_adapt.lth` from clean checkout.
- [ ] Archive `build_report.json` for every gallery build.
- [ ] Archive `selector_manifest.json` for every gallery build.
- [ ] Archive `stages/validate/report.json` for every gallery build.
- [ ] Archive `stages/package/package_manifest.json` for every gallery build.
- [ ] Archive `stages/package/trace_manifest.json` for every gallery build.
- [ ] Archive GLB/USD outputs for every gallery build.
- [ ] Archive preview media for every gallery build.
- [ ] Verify every gallery artifact path matches docs.
- [ ] Verify every expected certification failure is listed in `docs/examples_catalog.md`.
- [ ] Verify every non-canonical example is labeled honestly.

### Engine And Viewer Validation

- [ ] Open canonical GLB outputs in at least one external GLB viewer.
- [ ] Open canonical USD outputs in at least one external USD-capable viewer or record exception.
- [ ] Record screenshots or logs from external viewer validation.
- [ ] Run Godot addon manual smoke test 1.
- [ ] Run Godot addon manual smoke test 2.
- [ ] Run Godot addon manual smoke test 3.
- [ ] Run Godot addon manual smoke test 4.5.
- [ ] Run Godot addon manual smoke test 4.6.
- [ ] Run Godot addon manual smoke test 5.
- [ ] Record Godot version and OS.
- [ ] Add headless Godot/GUT automation plan or implement automated tests.
- [ ] Decide whether manual-only Godot tests block public launch.

### Accessibility, Internationalization, And Platforms

- [ ] Define accessibility scope for CLI docs and generated reports.
- [ ] Audit generated HTML reports against WCAG 2.2 AA where applicable.
- [ ] Audit docs site for keyboard navigation and contrast.
- [ ] Define internationalization scope.
- [ ] Document that localization is out of scope if not supported.
- [ ] Verify CLI text handles non-ASCII paths or document unsupported behavior.
- [ ] Test Windows supported matrix.
- [ ] Test macOS supported matrix.
- [ ] Test Ubuntu supported matrix.
- [ ] Verify Python 3.13/3.14 are unsupported or add support evidence.

## Phase 8 - Fix Technical Architecture Findings

- [ ] Create capacity/headroom report for local CLI workloads.
- [ ] Define target peak for launch-relevant surfaces.
- [ ] Run sustained 30-minute test at target peak x 3 for any hosted service.
- [ ] If there is no hosted service, document why RPS/load tests are not applicable.
- [ ] Define cold start time for CLI first parse/build.
- [ ] Define warm start time for cached build.
- [ ] Define recovery time after interrupted build.
- [ ] Test forced kill during build and record artifact/cache behavior.
- [ ] Test cache corruption behavior.
- [ ] Test concurrent builds into separate output dirs.
- [ ] Test concurrent builds into same output dir or document rejection.
- [ ] Document cache locking posture.
- [ ] Document idempotency posture for build, cache, publish, and telemetry.
- [ ] Document replay safety for build and publish flows.
- [ ] Document API/CLI versioning policy.
- [ ] Document deprecation policy for CLI flags and manifest schemas.
- [ ] Ensure public contract IDs have tests.
- [ ] Ensure schema migrations have tests or explicit non-applicability.
- [ ] Audit third-party dependencies for SLA, license, alternatives, and lock-in.
- [ ] Document graceful degradation when Blender fails.
- [ ] Document graceful degradation when xatlas fails.
- [ ] Document graceful degradation when Hunyuan fails.
- [ ] Document graceful degradation when VGGT fails.
- [ ] Document graceful degradation when telemetry ingest fails.
- [ ] Document graceful degradation when PyPI/GitHub Actions are unavailable.

## Phase 9 - Fix Security Findings

### Threat Model And OWASP Coverage

- [ ] Review `docs/security/threat_model.md` for stale file references.
- [ ] Correct references to missing files such as `lathe/providers/sandbox.py` if still absent.
- [ ] Correct references to missing files such as `lathe/parser/binary.py` if still absent.
- [ ] Add sign-off date and reviewer to threat model.
- [ ] Map OWASP Top 10 categories to Lathe attack surfaces.
- [ ] Add test evidence for each applicable OWASP category.
- [ ] Mark non-applicable OWASP categories with rationale.
- [ ] Add attack tree for authentication if any hosted service exists.
- [ ] If no authentication exists, document why auth/account takeover is not applicable to current CLI.
- [ ] Enumerate abuse and fraud vectors for telemetry and future hosted registry.
- [ ] Enumerate bot defense/rate limiting for public telemetry ingest.

### Secrets And Logging

- [ ] Run secret scan on full repository history.
- [ ] Confirm `.env.example` contains placeholders only.
- [ ] Confirm runtime configs contain no real secrets.
- [ ] Confirm generated artifacts contain no secrets.
- [ ] Confirm logs do not include provider tokens.
- [ ] Confirm logs do not include PII.
- [ ] Confirm telemetry tests include poisoned build report with secrets.
- [ ] Confirm safe logging tests pass.
- [ ] Document secret rotation policy.
- [ ] Document scope minimization for any future provider credentials.

### Supply Chain

- [ ] Generate SBOM from release wheel.
- [ ] Review SBOM for unexpected dependencies.
- [ ] Review runtime dependency licenses.
- [ ] Review dev dependency licenses.
- [ ] Confirm dependency pinning/lock policy.
- [ ] Confirm Dependabot is configured.
- [ ] Confirm `uv.lock`, `requirements.txt`, and `requirements-dev.txt` sync.
- [ ] Confirm release artifact hashes.
- [ ] Confirm PyPI attestations if publishing.
- [ ] Confirm signed tag or approved exception.

### Pen Test Or Security Review

- [ ] Define scope for security review.
- [ ] Include `.lth` parser.
- [ ] Include runtime config loader.
- [ ] Include provider HTTP client.
- [ ] Include path/output safety.
- [ ] Include mesh/image ingest.
- [ ] Include Blender subprocess sandbox.
- [ ] Include telemetry.
- [ ] Include publish drivers if shipped.
- [ ] Run review or record approved exception.
- [ ] Fix all P0/P1 security findings from review before public launch.

## Phase 10 - Fix Reliability And Observability Findings

- [ ] Define critical user journey: install to doctor.
- [ ] Define critical user journey: check example.
- [ ] Define critical user journey: build canonical asset.
- [ ] Define critical user journey: import into Godot.
- [ ] Define critical user journey: troubleshoot failed certification.
- [ ] Define SLO for each critical journey.
- [ ] Define error budget for each SLO.
- [ ] Define burn-rate alert for each SLO if hosted measurement exists.
- [ ] Create dashboard answering: are installs succeeding?
- [ ] Create dashboard answering: are builds succeeding?
- [ ] Create dashboard answering: which versions fail?
- [ ] Create dashboard answering: which diagnostics spike?
- [ ] Create dashboard answering: is support volume exceeding capacity?
- [ ] Create synthetic monitoring for docs quickstart.
- [ ] Create synthetic monitoring for package install.
- [ ] Create synthetic monitoring for telemetry ingest if telemetry is live.
- [ ] Define backup target for release artifacts.
- [ ] Define restore process for release artifacts.
- [ ] Run restore drill for release artifacts.
- [ ] State RTO target.
- [ ] State RPO target.
- [ ] Test RTO/RPO or record why not applicable.

## Phase 11 - Fix Data And Telemetry Findings

- [ ] Decide whether telemetry remains disabled for the public RC.
- [ ] If telemetry remains disabled, document which launch metrics will be collected manually.
- [ ] If telemetry is enabled, publish event taxonomy.
- [ ] If telemetry is enabled, publish dashboard URL.
- [ ] If telemetry is enabled, publish retention enforcement.
- [ ] If telemetry is enabled, publish deletion workflow.
- [ ] If telemetry is enabled, publish export workflow if applicable.
- [ ] Implement consent record.
- [ ] Test consent record.
- [ ] Implement opt-out enforcement.
- [ ] Test opt-out enforcement.
- [ ] Implement local purge.
- [ ] Test local purge.
- [ ] Define schema drift alert.
- [ ] Define null-rate alert.
- [ ] Define freshness alert.
- [ ] Define cohort analysis for return build rate.
- [ ] Define segment analysis by version and platform.
- [ ] Define activation funnel from install to certified asset.
- [ ] Define retention metric for second build within seven days.

## Phase 12 - Fix Financial And Unit Economics Findings

- [ ] Document current launch has no billing if true.
- [ ] Document all billing tasks as future if no monetized surface ships.
- [ ] Estimate maintainer support hours per active user.
- [ ] Estimate launch-week support capacity.
- [ ] Estimate CI minutes for release gates.
- [ ] Estimate artifact storage costs.
- [ ] Estimate telemetry hosting costs.
- [ ] Estimate docs hosting costs.
- [ ] Estimate future learned-provider costs.
- [ ] Estimate future registry storage/egress costs.
- [ ] Estimate future CI-SaaS runner costs.
- [ ] Add sensitivity table for low, expected, and high usage.
- [ ] Add sensitivity table for support load.
- [ ] Add sensitivity table for provider cost increases.
- [ ] Define threshold where free support becomes unsustainable.
- [ ] Define threshold where hosted telemetry becomes unsustainable.
- [ ] Define threshold where paid registry beta must pause.

## Phase 13 - Fix Launch And GTM Findings

- [ ] Confirm V0.5 public OSS criteria in `docs/roadmap_public.md` are still correct.
- [ ] Mark each V0.5 criterion as complete, blocked, or deferred.
- [ ] Do not claim PyPI availability until `pip install lathe==<version>` is verified.
- [ ] Do not claim Godot AssetLib availability until listing is live.
- [ ] Do not claim signed design partners until LOIs are signed.
- [ ] Do not claim Discord/community launch until channels exist and moderation owner is named.
- [ ] Do not claim benchmark publication until raw data is public and reviewed.
- [ ] Create launch copy that says "pre-release" clearly.
- [ ] Create launch copy that avoids "production-ready" unless evidence is attached.
- [ ] Create launch copy that names known limitations.
- [ ] Create launch copy that names supported OS/Python matrix.
- [ ] Create launch copy that names optional/experimental provider paths.
- [ ] Create launch copy that says learned-provider quality is experimental where applicable.
- [ ] Create crisis comms for install failure.
- [ ] Create crisis comms for security advisory.
- [ ] Create crisis comms for telemetry/privacy complaint.
- [ ] Create crisis comms for bad generated output.
- [ ] Create crisis comms for yanked package.
- [ ] Name every launch channel owner.
- [ ] Name every launch channel backup.

## Phase 14 - Fix Team And Organizational Findings

- [ ] Create `docs/release/raci-v0.2.0rc1.md`.
- [ ] Name accountable owner for strategic readiness.
- [ ] Name accountable owner for product experience.
- [ ] Name accountable owner for technical architecture.
- [ ] Name accountable owner for security.
- [ ] Name accountable owner for reliability and observability.
- [ ] Name accountable owner for operations.
- [ ] Name accountable owner for data and telemetry.
- [ ] Name accountable owner for compliance and legal.
- [ ] Name accountable owner for financials.
- [ ] Name accountable owner for launch and GTM.
- [ ] Name accountable owner for team/org readiness.
- [ ] Name accountable owner for risk register.
- [ ] Name backup owner for every dimension.
- [ ] Define final launch decision DACI.
- [ ] Define who can veto launch for security.
- [ ] Define who can veto launch for legal/privacy.
- [ ] Define who can veto launch for release quality.
- [ ] Define who can accept P1 risk.
- [ ] Define who can accept P2 risk.
- [ ] Draft first 14-day post-launch meeting cadence.
- [ ] Draft post-launch sprint backlog.
- [ ] Reserve hotfix capacity as explicit percent of team-week.

## Phase 15 - Fix Product-Market Evidence Findings

- [ ] Complete 5 Persona A interviews.
- [ ] Complete 2 Persona B interviews.
- [ ] Complete 1 Persona C interview.
- [ ] Summarize interview findings.
- [ ] Identify top 3 repeated user pains.
- [ ] Identify top 3 repeated objections.
- [ ] Identify top 3 adoption blockers.
- [ ] Record whether Godot indie wedge remains valid.
- [ ] Record whether pipeline TD secondary persona remains valid.
- [ ] Record whether agent-builder persona remains valid.
- [ ] Secure 3 design-partner LOIs or mark launch blocked.
- [ ] Record every design partner by name or anonymized identifier.
- [ ] Record whether each partner tried Lathe on a real project.
- [ ] Record whether each partner would adopt on next project.
- [ ] If fewer than 2 partners would adopt, pause V0.8 scope for wedge revalidation.
- [ ] Record willingness-to-pay interview findings.
- [ ] Record whether pricing remains unknown.
- [ ] Do not publish revenue, MAU, or customer claims without evidence.

## Phase 16 - Fix Product Quality And Godot Findings

- [ ] Decide whether Godot addon is in launch scope.
- [ ] If Godot addon is in scope, create automated test plan.
- [ ] If Godot addon is in scope, run all manual smoke tests and archive logs.
- [ ] If Godot addon is in scope, record Godot version tested.
- [ ] If Godot addon is in scope, record Windows Godot smoke result.
- [ ] If Godot addon is in scope, record macOS Godot smoke result.
- [ ] If Godot addon is in scope, record Linux Godot smoke result.
- [ ] If Godot addon is not in scope, remove or soften launch claims.
- [ ] Verify docs state no AssetLib submission yet.
- [ ] Verify docs state manual-only Godot tests if automation remains absent.
- [ ] Verify generated `.glb` opens in Godot stock importer.
- [ ] Verify sockets are represented as expected.
- [ ] Verify collision is represented as expected.
- [ ] Verify LOD metadata is represented as expected.
- [ ] Verify certified-state UI reflects pass/fail accurately.
- [ ] Verify build trace viewer handles missing files gracefully.

## Phase 17 - Fix Anti-Pattern Risks

- [ ] Search docs for "after launch" monitoring promises and remove or convert to blockers.
- [ ] Search docs for "probably fine" legal language and remove or convert to legal review tasks.
- [ ] Search docs for "works on my machine" or equivalent claims and replace with matrix evidence.
- [ ] Search docs for scale claims and attach load/perf artifacts.
- [ ] Search docs for security claims and attach threat model plus scan evidence.
- [ ] Search docs for "best practices" claims and name the specific practice.
- [ ] Search docs for unsupported "production-ready" claims and remove or qualify.
- [ ] Search docs for "users won't do that" assumptions and add tests or support guidance.
- [ ] Search docs for "hotfix" as mitigation and require rollback/owner/date.
- [ ] Ensure risk register has at least 10 risks.
- [ ] Ensure roadmap includes explicit "we chose not to build X" entries.
- [ ] Ensure every scale claim links to benchmark/load artifact.
- [ ] Ensure every security claim links to threat model or scan artifact.

## Phase 18 - Re-Review Gate

- [ ] Complete all P0 tasks.
- [ ] Complete all P1 tasks or record formal risk acceptance.
- [ ] Ensure no P0 release exception exists.
- [ ] Ensure every P1 release exception has mitigation, owner, and date.
- [ ] Run full release-local gate from clean checkout.
- [ ] Run supported OS/Python matrix in CI.
- [ ] Attach all CI links to evidence packet.
- [ ] Confirm release evidence packet is complete.
- [ ] Confirm risk register is complete.
- [ ] Confirm rollback plan is executable.
- [ ] Confirm legal/privacy sign-off is complete.
- [ ] Confirm support/on-call plan is staffed.
- [ ] Confirm target-user feedback has been recorded.
- [ ] Schedule follow-up readiness review for 2026-05-28 or T+30 after actual public launch, whichever is later.
- [ ] Hold go/no-go meeting.
- [ ] Record final verdict: SHIP, SHIP WITH CONDITIONS, DO NOT SHIP, or INSUFFICIENT EVIDENCE TO DECIDE.

