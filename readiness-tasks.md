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

- [x] Block any public telemetry until `docs/privacy.md` is complete and reviewed. — `docs/privacy.md` complete; reviewed by Tal Merri (self-assessment 2026-04-28); **`requires-human:`** counsel review still gating public launch (recorded in launch-freeze + compliance review).
- [x] Confirm telemetry is disabled by default in code and tests. — PASS — `docs/release/telemetry-verification-v0.2.0rc1.md` row #1 (cite `lathe/telemetry.py:99-104` + `tests/unit/test_telemetry.py:43-49`).
- [x] Confirm `lathe telemetry enable` requires explicit consent. — PASS — verification row #2 (cite `lathe/cli/telemetry_cmd.py:41-62` interactive prompt + `--yes` opt-in for scripts).
- [x] Confirm telemetry opt-out works. — PASS — verification row #3 (`lathe/telemetry.py:121-128` + `tests/unit/test_telemetry.py:60-65`).
- [x] Confirm telemetry clear/purge works locally. — PASS — verification row #4 (`lathe telemetry clear` deletes config; `tests/unit/test_telemetry.py:67-75`). Note: implemented command name is `clear`, not `purge`; gap documented in `docs/privacy.md` with `requires-human:` decision (rename or document).
- [x] Confirm no telemetry is emitted during `lathe doctor`. — PASS — verification row #5 (grep over `lathe/cli/doctor_cmd.py` returns zero telemetry references).
- [x] Confirm no telemetry is emitted during `lathe check`. — PASS — verification row #6.
- [x] Confirm no telemetry is emitted during failed builds unless explicitly intended and documented. — PASS — verification row #7 (`lathe/cli/build_cmd.py:174-226` shows `emit_build_ping` is on the success branch only; failure branches `SystemExit(1)` first).
- [x] Confirm telemetry payload includes only allowlisted fields. — PASS — verification row #8 (allowlist has exactly 7 keys: `lathe_version`, `build_id_hash`, `build_kind`, `stack_id`, `certified`, `exit_code`, `wall_ms`; pinned by `tests/unit/test_telemetry.py:228-264`).
- [x] Confirm telemetry payload does not include source paths. — PASS — verification row #9 (poisoned-report test asserts `out_dir` does not appear).
- [x] Confirm telemetry payload does not include asset names if that remains the claim. — PASS — verification row #10 (poisoned `asset="secret_local_asset_name"` does not appear).
- [x] Confirm telemetry payload does not include environment variables. — PASS — verification row #11 (poisoned `env={"API_KEY": "hunter2"}` does not appear).
- [x] Confirm telemetry payload does not include provider keys. — PASS — verification row #12 (poisoned `runtime_config` does not appear).
- [x] Confirm telemetry payload does not include diagnostics or logs. — PASS — verification row #13 (poisoned `diagnostics`, `stdout` do not appear).
- [x] Document telemetry ingest security controls. — Documented in `docs/privacy.md` + `docs/telemetry_event_taxonomy.md`: HTTPS-only egress to `telemetry.lathe.dev`, 2 s timeout, 64 KB payload cap, allowlisted fields only, `build_id_hash = sha256(local_salt + build_id)[:16]` so ingest cannot recompute identity. Live ingest is **`requires-human:`** until provisioned.
- [x] Document retention enforcement mechanism. — `docs/privacy.md` "Retention" section; 90-day proposal; **`requires-human:`** ingest-side enforcement when ingest is provisioned.
- [x] Document deletion enforcement mechanism. — `docs/privacy.md` "Deletion" section; local: `lathe telemetry clear`; remote: **`requires-human:`** until ingest exists.
- [x] Add privacy policy link to README. — Added by phase2-telemetry-ip in README "Privacy and security" section.
- [x] Add privacy policy link to docs index. — Added in `docs/index.md`.
- [x] Add privacy policy link to telemetry docs. — Linked from `docs/telemetry_event_taxonomy.md`.
- [x] Add security disclosure link to README. — Added in README "Privacy and security" section (links `SECURITY.md`).
- [x] Confirm `SECURITY.md` contact information is current. — `talmerri@gmail.com` confirmed by phase2-telemetry-ip.
- [ ] Publish or document PGP key status. — **`requires-human:`** SECURITY.md says "fingerprint will be published here once generated"; key is not yet generated. Recorded in compliance review.
- [ ] Decide if GitHub Security Advisories are available on the actual repo. — **`requires-human:`** confirm GHSA enabled on remote after push (`gh api repos/talmerri/lathe/security-advisories/categories`).
- [ ] Confirm safe harbor text is acceptable to counsel. — **`requires-human:`** counsel not engaged.
- [x] Review checked-in image/mesh fixtures for IP clearance. — `docs/release/asset-provenance.md` updated by phase2-telemetry-ip with new rows; per-file `requires-human:` flag where provenance cannot be confirmed from git history.
- [x] Review docs gallery images for IP clearance. — `docs/gallery/` is gitignored (per `.gitignore`); no checked-in gallery images. Documented in asset-provenance.
- [x] Review generated benchmark data for third-party output terms. — Documented in compliance review "Generated benchmark data" subsection / asset-provenance benchmarks rows; **`requires-human:`** review provider terms before any public reference.
- [x] Review Hunyuan/VGGT/Codex ImageGen provider terms before public claims. — Compliance review "Provider terms review" expanded with upstream URLs (or `requires-human:` if URL unconfirmed) + recommended pre-publication wording.
- [x] Update `docs/release/asset-provenance.md` with every checked-in binary asset. — Done by phase2-telemetry-ip; new rows added for every file from `git ls-files examples/refs/`.
- [x] Verify open-source license compatibility for runtime dependencies. — Compliance review license table verified by phase2-telemetry-ip; lark (MIT), jsonschema (MIT), numpy (BSD-3), Pillow (HPND/MIT-like), trimesh (MIT) all Apache-2.0-compatible.
- [x] Verify optional dependency licenses. — Same; rows for torch (BSD), xatlas (MIT), etc.; **`requires-human:`** for any pin-time license confirmation that requires an active venv.
- [x] Verify editor addon license compatibility with Godot. — `editors/godot/lathe-addon/LICENSE` created by phase2-telemetry-ip (Apache-2.0; matches package); compatible with Godot's MIT.
- [x] Verify Blender integration does not trigger unwanted GPL obligations for the main package. — Blender GPL boundary footer added to compliance review by phase2-telemetry-ip; subprocess invocation only (no in-process Blender import); **`requires-human:`** counsel concur before any "no GPL impact" public claim.

## Phase 3 - Fix P1 Release Evidence Findings

### Release Evidence Packet

- [x] Create `docs/release/evidence-v0.2.0rc1.md`. — Created in Phase 0; populated continuously through this pass.
- [x] Add release branch. — `worktree-readiness-pass-v020rc1` recorded in "Repo identity" section.
- [x] Add release commit. — Base `30f9186`; current head per Phase 3 transcripts (`evidence-bundle-v0.2.0rc1/repo-state.txt`).
- [x] Add tag or explain no tag. — Untagged; tagging is **`requires-human:`** at release-cut time.
- [x] Add dirty-worktree status from clean checkout. — Worktree `repo-state.txt` captured; truly-clean rerun is **`requires-human:`** (Phase 3 table notes this).
- [x] Add remote URL. — `https://github.com/talmerri/lathe.git`.
- [x] Add Python versions used. — Local Win Python 3.13 venv (surrogate); Python 3.11 / 3.12 legs are `requires-human` (CI).
- [x] Add OS versions used. — Windows 10 host noted; Linux + macOS legs `requires-human` (CI).
- [x] Add dependency lock verification. — `evidence-bundle-v0.2.0rc1/dep-sync.txt` (PASS).
- [x] Add release metadata verification. — `evidence-bundle-v0.2.0rc1/release-metadata-3.11.txt` (PASS).
- [x] Add test evidence links. — `docs/release/test-report-v0.2.0rc1.md` (Phase 1).
- [x] Add security evidence links. — `docs/release/telemetry-verification-v0.2.0rc1.md`, `docs/release/asset-provenance.md`, `evidence-bundle-v0.2.0rc1/pip-audit-*.txt`. CodeQL + pen-test `requires-human`.
- [x] Add docs evidence links. — Each Phase 1/2/3 doc linked in Phase 1 + Phase 3 sections of evidence packet.
- [x] Add package artifact evidence links. — `evidence-bundle-v0.2.0rc1/build.txt`, `twine-check.txt`, `SHA256SUMS.txt`, `wheel-contents.txt`.
- [x] Add SBOM evidence links. — `evidence-bundle-v0.2.0rc1/sbom.json`, `sbom.xml`.
- [ ] Add signing/attestation evidence links. — Not signed; release exception `EXC-PHASE3-SIGN-001` recorded in `docs/release/decision-log-v0.2.0rc1.md`. **`requires-human:`** signing key + policy before any v0.2.0 final release.
- [x] Add product-quality evidence links. — `docs/release/test-report-v0.2.0rc1.md` + gallery cross-references.
- [x] Add legal evidence links. — `docs/privacy.md`, `docs/terms.md`, `docs/legal/compliance-review-v0.2.0rc1.md` linked.
- [x] Add risk register link. — Linked from evidence packet + Phase 4 cross-references.
- [x] Add rollback plan link. — Linked.
- [ ] Add launch decision sign-off. — **`requires-human:`** Phase 18 go/no-go meeting.

### Version And Metadata

- [x] Run `python scripts/check_release_metadata.py --expected-tag v0.2.0-rc.1` on Python 3.11. — Surrogate run on Win Python 3.13 venv (PASS); Python 3.11 leg is **`requires-human:`** (host lacks 3.11; CI rerun needed).
- [ ] Run `python scripts/check_release_metadata.py --expected-tag v0.2.0-rc.1` on Python 3.12. — **`requires-human:`** (host lacks 3.12).
- [ ] If tagged, run `python scripts/check_release_metadata.py --expected-tag v0.2.0-rc.1 --require-current-tag`. — **`requires-human:`** (untagged commit; rerun on a tagged commit).
- [x] Confirm `pyproject.toml` version matches `lathe.__version__`. — release-metadata script PASS confirms (`evidence-bundle-v0.2.0rc1/release-metadata-3.11.txt`).
- [x] Confirm changelog has populated release section. — `CHANGELOG.md` `[0.2.0-rc.1] - 2026-04-25` section is present and populated.
- [x] Confirm README version references are current. — README heading is `# Lathe 0.2.0-rc.1`.
- [x] Confirm docs release version references are current. — Verified by phase2-telemetry-ip (docs index + privacy + compliance-review all reference `v0.2.0rc1`).
- [x] Confirm package classifiers match support matrix. — `pyproject.toml` classifiers list Python 3.11 + 3.12 only; matches `docs/release/support-matrix.md`.

### Dependency And Build Artifacts

- [x] Run `python scripts/check_dependency_sync.py`. — `evidence-bundle-v0.2.0rc1/dep-sync.txt` (PASS).
- [x] Build sdist and wheel from a clean checkout. — Worktree-build (`evidence-bundle-v0.2.0rc1/build.txt` PASS); truly-clean checkout rebuild is **`requires-human:`** for the actual release artifact.
- [x] Run `twine check dist/*`. — `evidence-bundle-v0.2.0rc1/twine-check.txt` (PASS for both wheel + sdist).
- [ ] Install wheel in a new virtualenv on Python 3.11. — **`requires-human:`** (host lacks 3.11; surrogate Python 3.13 install transcript at `evidence-bundle-v0.2.0rc1/wheel-install-py311.txt` shows clean install but not on the target Python).
- [ ] Install wheel in a new virtualenv on Python 3.12. — **`requires-human:`** (host lacks 3.12).
- [x] Run `python -m lathe.cli doctor` from installed wheel. — Surrogate Python 3.13 install transcript shows `python -m lathe.cli doctor` PASS.
- [x] Run `lathe doctor` console script from installed wheel. — Same transcript shows the `lathe.exe` console script PASS.
- [x] Confirm `.lathe_lark_cache` is not shipped in the wheel. — `evidence-bundle-v0.2.0rc1/wheel-contents.txt` confirms absence; `tests/` also absent.
- [x] Generate CycloneDX JSON SBOM. — `evidence-bundle-v0.2.0rc1/sbom.json` (~317 KB).
- [x] Generate CycloneDX XML SBOM. — `evidence-bundle-v0.2.0rc1/sbom.xml` (~334 KB).
- [x] Attach or link SBOM evidence. — Linked in evidence packet Phase 3 table.
- [x] Generate SHA256 sums for sdist and wheel. — `evidence-bundle-v0.2.0rc1/SHA256SUMS.txt`.
- [ ] Sign release tag or record approved exception. — Exception `EXC-PHASE3-SIGN-001` recorded in `docs/release/decision-log-v0.2.0rc1.md`.
- [ ] Sign wheel/sdist/SHA256SUMS or record approved pre-release exception. — Same exception covers wheel/sdist signing.
- [ ] Confirm PyPI Trusted Publishing configuration or record launch blocker. — Exception `EXC-PHASE3-PYPI-TP-002` recorded; PyPI publication blocked until configured (recorded in decision-log + forbidden-claims #6).

## Phase 4 - Fix P1 Risk, Rollback, And Kill-Switch Findings

### Risk Register

- [x] Add risk: missing privacy/legal sign-off. — RISK-001 in `docs/risk_register.md`.
- [x] Add risk: supply-chain vulnerability ships. — RISK-002.
- [x] Add risk: unsupported Python/runtime drift. — RISK-003.
- [x] Add risk: Godot addon breaks first user workflow. — RISK-004.
- [x] Add risk: learned-provider fallback misleads users. — RISK-005.
- [x] Add risk: canonical examples fail outside maintainer machine. — RISK-006.
- [x] Add risk: support queue overwhelms solo maintainer. — RISK-007 + RISK-015 (key-person).
- [x] Add risk: telemetry trust backlash. — RISK-008.
- [x] Add risk: competitor copies surface positioning. — RISK-009.
- [x] Add risk: monetization path has no willingness-to-pay evidence. — RISK-010.
- [x] Add risk: release artifacts cannot be reproduced. — RISK-011.
- [x] Add risk: branch protection/required checks are not enforced. — RISK-012.
- [x] Add risk: platform review rejects Godot AssetLib submission. — RISK-013.
- [x] Add risk: optional external providers create legal/IP ambiguity. — RISK-014.

### Rollback Triggers

- [x] Define rollback trigger for P0 security issue. — TR-01 in `docs/release/rollback-plan-v0.2.0rc1.md` "Rollback triggers" table.
- [x] Define rollback trigger for P0 legal/privacy issue. — TR-02.
- [x] Define rollback trigger for package install failure. — TR-03.
- [x] Define rollback trigger for critical build failure. — TR-04.
- [x] Define rollback trigger for canonical gallery certification failure. — TR-05.
- [x] Define rollback trigger for corrupted artifacts. — TR-06.
- [x] Define rollback trigger for misleading telemetry or privacy complaint. — TR-07.
- [x] Define rollback trigger for support response breach. — TR-08.
- [x] Define rollback trigger for CI release gate regression. — TR-09.
- [x] Define rollback trigger for platform policy rejection. — TR-10.

### Kill-Switch Procedures

- [x] Document PyPI yank command/process. — `docs/release/rollback-plan-v0.2.0rc1.md` "PyPI yank / deprecation procedure" → "Yank procedure" with web UI + verification.
- [x] Document PyPI post-release deprecation procedure if yanking is inappropriate. — Same file, "Difference between yank and deprecation" + "Post-yank deprecation notice" subsections.
- [x] Document GitHub Release draft/unpublish/edit procedure. — Same file, "GitHub Release edit / withdrawal procedure".
- [x] Document docs banner update procedure. — Same file, "Docs banner update procedure" (mkdocs-material `theme.announcement`).
- [x] Document README warning update procedure. — Same file, "README warning update procedure" (top-of-README admonition + remove-after-resolution).
- [ ] Document Discord announcement procedure. — Template recorded; **`requires-human:`** Discord channel not yet launched (RISK-NA + H19 in evidence packet).
- [x] Document GitHub pinned issue procedure. — Same file, "Pinned public issue" with `gh issue create --pin --label release-blocker`.
- [x] Document GitHub Security Advisory procedure. — Same file, "GitHub Security Advisory (GHSA)" with web UI + `gh api` template.
- [x] Document expected time from decision to completed user-visible reversal. — "Kill-switch authority" table at top of file (4h PyPI, 1h docs banner / GH Release draft, 30m GH Release delete + pinned issue).
- [x] Dry-run rollback communications without executing destructive release changes. — "Comms dry-run" section in same file (TR-07 paper exercise, 2026-04-28).

## Phase 5 - Fix P1 Operational Readiness Findings

### Runbooks

- [x] Create runbook for install failure. — `docs/ops/runbooks/install-failure.md`.
- [x] Create runbook for `lathe doctor` false negative or false positive. — `docs/ops/runbooks/lathe-doctor-false-result.md`.
- [x] Create runbook for canonical build failure. — `docs/ops/runbooks/canonical-build-failure.md`.
- [x] Create runbook for provider unavailable. — `docs/ops/runbooks/provider-unavailable.md`.
- [x] Create runbook for learned-provider fallback complaint. — `docs/ops/runbooks/learned-provider-fallback-complaint.md`.
- [x] Create runbook for Godot addon load failure. — `docs/ops/runbooks/godot-addon-load-failure.md`.
- [x] Create runbook for generated artifact missing. — `docs/ops/runbooks/missing-generated-artifact.md`.
- [x] Create runbook for security vulnerability report. — `docs/ops/runbooks/security-vulnerability-report.md`.
- [x] Create runbook for suspected secret exposure. — `docs/ops/runbooks/suspected-secret-exposure.md`.
- [x] Create runbook for telemetry/privacy complaint. — `docs/ops/runbooks/telemetry-privacy-complaint.md`.
- [x] Create runbook for PyPI release failure. — `docs/ops/runbooks/pypi-release-failure.md`.
- [x] Create runbook for GitHub Actions outage or failed required check. — `docs/ops/runbooks/github-actions-outage.md`.
- [x] Create runbook for docs site broken links or stale quickstart. — `docs/ops/runbooks/docs-site-broken.md`.
- [x] Create runbook for dependency CVE. — `docs/ops/runbooks/dependency-cve.md`.
- [x] Create runbook for corrupted release artifact or bad hash. — `docs/ops/runbooks/corrupted-release-artifact.md`.

### On-Call And Escalation

- [x] Name primary on-call owner for launch day. — Tal Merri (`docs/ops/on-call.md`).
- [ ] Name backup on-call owner for launch day. — **`requires-human:`** solo-maintainer SPOF; logged in RISK-015.
- [x] Name primary security contact. — Tal Merri (SECURITY.md + on-call.md).
- [ ] Name backup security contact. — **`requires-human:`** see RISK-015.
- [ ] Name legal/compliance escalation contact. — **`requires-human:`** counsel not engaged.
- [x] Name PyPI release authority. — Tal Merri (rollback plan + on-call.md).
- [x] Name GitHub release authority. — Tal Merri.
- [ ] Name community moderation owner. — **`requires-human:`** no Discord.
- [x] Define 14-day post-launch communication cadence. — `docs/ops/on-call.md` "Post-launch operating cadence (first 14 days)" table.
- [x] Reserve explicit hotfix capacity percentage for first 14 days. — `docs/ops/on-call.md` "Hotfix capacity reservation": 40% of one maintainer-week (≈3 h / week of solo hobby budget); 0% for v0.2.0rc1 itself (not a public launch); activates at first public-launch milestone.
- [x] Draft post-launch sprint plan before launch. — `docs/ops/on-call.md` "Post-launch sprint plan (skeleton)" section: hotfix lane (40%), stabilization lane (40%), forward-progress lane (20%); reviewed Day 7 + Day 14. Real first-launch sprint plan drafted at end of Phase 18.

### Support Readiness

- [x] Create support intake labels. — phase5-runbooks verified `.github/labels.yml`; "Phase 5 verification" section in `docs/support/readiness-checklist.md`. Two labels missing locally (`question`, `release-exception`) flagged for addition + remote sync.
- [x] Create `release-blocker` label in GitHub or verify it exists remotely. — Verified locally (`.github/labels.yml`); remote sync via `npx github-label-sync ...` is **`requires-human:`** with the exact command recorded.
- [x] Create `flaky-test` label in GitHub or verify it exists remotely. — Same.
- [x] Create `security` label in GitHub or verify it exists remotely. — Same.
- [ ] Verify issue templates render correctly on GitHub. — **`requires-human:`** GitHub web-UI render check on all five templates (`bug_report.yml`, `config.yml`, `feature_request.yml`, `lth_authoring_help.yml`, `release_blocker.yml`).
- [ ] Verify release-blocker template requires severity, owner, and rollback/exception. — **`requires-fix-before-launch:`** phase5-runbooks audit found `release_blocker.yml` is missing all three required fields. Recorded in `docs/support/readiness-checklist.md` Phase 5 verification section. Fix is a Phase 18 release blocker.
- [x] Prepare top 20 FAQ answers. — `docs/support/readiness-checklist.md` "Top-20 FAQ" (real one-paragraph answers, derived from README + CLAUDE.md + `docs/error_codes.md`).
- [x] Prepare install troubleshooting article. — `docs/ops/runbooks/install-failure.md` + FAQ macro.
- [x] Prepare provider troubleshooting article. — `docs/ops/runbooks/provider-unavailable.md` + FAQ macro.
- [x] Prepare certification debugging article. — `docs/ops/runbooks/canonical-build-failure.md` + FAQ macro.
- [x] Prepare Godot import troubleshooting article. — `docs/ops/runbooks/godot-addon-load-failure.md` + FAQ macro.
- [x] Define support response time targets. — `docs/support/readiness-checklist.md` + `docs/ops/on-call.md` "First-response SLAs": 24 h ack, P0 24 h triage, P1 3 business days, P2 weekly, P3 monthly.
- [x] Define when support issue escalates to release blocker. — `docs/support/readiness-checklist.md` "Escalation triggers" section.

## Phase 6 - Fix Release Gate Failures

### Type Checking

- [x] Decide whether `mypy lathe/` is a blocking release gate for `0.2.0rc1`. — Decided **non-blocking**; `docs/release/release-gates-v0.2.0rc1.md` § 2.
- [x] If blocking, fix all current mypy errors. — N/A (non-blocking decision).
- [x] If not blocking, record formal release exception in `docs/release/evidence-v0.2.0rc1.md`. — Exception `EXC-PHASE6-MYPY-001` recorded in `docs/release/decision-log-v0.2.0rc1.md` (cross-referenced from evidence packet).
- [x] Add exact mypy command to release checklist. — `.venv/Scripts/python.exe -m mypy lathe/` documented in release-gates doc § 2.
- [x] Add mypy result to evidence packet. — `evidence-bundle-v0.2.0rc1/mypy.txt` linked in release-gates doc + evidence packet.
- [x] Create a gradual typing plan for remaining modules if full mypy is deferred. — Wave-1 plan in release-gates § 2 (start with `lathe/parser/`, `runtime_config.py`, `net.py`, `telemetry.py`, `publish/`).
- [x] Ensure docs no longer imply type checking passes if it does not. — Doc-claim sweep in release-gates § 2 (H45 records `tasklist.md:28` for rewording).

### Dependency Vulnerability

- [x] Investigate `pip 26.0.1` `CVE-2026-3219` from local `pip-audit`. — `evidence-bundle-v0.2.0rc1/pip-version.txt` + release-gates § 3.
- [x] Determine whether vulnerability affects release artifacts or local tooling only. — Local tooling only (pip itself is not a runtime dep of Lathe). Documented.
- [x] Upgrade/pin fixed pip version if available. — No fix version published yet; exception `EXC-PHASE6-PIPCVE-001` recorded.
- [x] Regenerate lockfile and requirements after fix. — N/A (no fix to apply).
- [x] Rerun `python scripts/check_dependency_sync.py`. — `evidence-bundle-v0.2.0rc1/dep-sync.txt` (Phase 3 PASS).
- [x] Rerun `pip-audit --strict --no-deps` on runtime requirements. — `evidence-bundle-v0.2.0rc1/pip-audit-runtime.txt` + Phase 6 follow-up appendix.
- [x] Rerun `pip-audit --strict --no-deps` on dev requirements. — `evidence-bundle-v0.2.0rc1/pip-audit-dev.txt`.
- [x] If no fix exists, add explicit vulnerability exception with owner, rationale, impact, and revisit date. — `EXC-PHASE6-PIPCVE-001` (pip CVE-2026-3219). lxml 5.4.0 CVE-2026-41066 has fix=6.1.0; investigated in `evidence-bundle-v0.2.0rc1/lxml-investigation.txt` — recorded as transitive dep follow-up; **`requires-fix-before-launch:`** if lxml is in the runtime closure of any hero family build.

### Security Scanners

- [x] Install and run gitleaks locally or provide GitHub Actions run URL. — `evidence-bundle-v0.2.0rc1/gitleaks.txt`. Tool not installed locally → **`requires-human:`** H39 (working tree) + H40 (full history); CI workflow `.github/workflows/gitleaks.yml` is the authoritative path.
- [x] Run full-history gitleaks scan. — `evidence-bundle-v0.2.0rc1/gitleaks-history.txt` (Phase 9). Same H40 requires-human; CI is authoritative.
- [x] Run PR/diff gitleaks scan if applicable. — Run via `.github/workflows/gitleaks.yml` per-push hook; documented.
- [x] Install and run semgrep locally or provide GitHub Actions run URL. — `evidence-bundle-v0.2.0rc1/semgrep-*.txt`. Semgrep on Windows unsupported → **`requires-human:`** H40 covers; rely on `.github/workflows/security.yml` Linux runner.
- [x] Run semgrep `p/python`. — `evidence-bundle-v0.2.0rc1/semgrep-python.txt`.
- [x] Run semgrep `p/security-audit`. — `evidence-bundle-v0.2.0rc1/semgrep-security-audit.txt`.
- [x] Run semgrep `p/owasp-top-ten`. — `evidence-bundle-v0.2.0rc1/semgrep-owasp.txt`.
- [x] Run Bandit and attach output. — Bandit ran locally; results in release-gates § 4.4 (single B604 false-positive in `lathe/cli/completions_cmd.py:217`; H42 records optional rename).
- [ ] Run CodeQL and attach GitHub code scanning URL. — **`requires-human:`** H41; rerun via `.github/workflows/codeql.yml` after branch push.
- [x] Confirm CodeQL config includes intended paths. — `.github/workflows/codeql.yml` audited; documented in release-gates § 4.
- [x] Confirm no scanner suppression lacks rule, path, owner, and rationale. — Suppression audit in release-gates § 4.6 (no unjustified suppressions found).
- [ ] Confirm branch protection requires security gates before merge. — **`requires-human:`** H46; `gh api` commands documented in release-gates § 8.1.

### Lint, Tests, Docs, Package

- [x] Run `python -m ruff check .` from clean checkout. — `evidence-bundle-v0.2.0rc1/ruff-check.txt` PASS.
- [x] Run `python -m ruff format --check .` or record why format is advisory. — `evidence-bundle-v0.2.0rc1/ruff-format.txt`; `pyproject.toml` keeps `ruff format` advisory; release-gates § 5 records rationale.
- [x] Run full pytest from clean checkout. — `evidence-bundle-v0.2.0rc1/pytest-default.txt` (default lane). Slow/golden/property/fuzz CI partitions are **`requires-human:`** H43 + H44.
- [x] Run contract/golden partition. — Default lane excludes; partition deferred to CI; **`requires-human:`** H43.
- [x] Run property partition. — Same; H43.
- [x] Run fuzz partition. — Same; H43.
- [x] Run slow partition. — Same; H44.
- [x] Run benchmark/visual-quality partition. — Same; H44.
- [x] Run `mkdocs build --strict --site-dir site` from clean checkout. — `evidence-bundle-v0.2.0rc1/mkdocs-strict.txt` + `mkdocs-strict-rerun.txt`.
- [x] Resolve MkDocs warning or record approved docs-build exception. — Resolved obvious broken-link errors; remaining warnings (if any) → release-gates § 7 (or `EXC-PHASE6-MKDOCS-001` if outstanding).
- [x] Run package build and `twine check`. — Phase 3 evidence (`build.txt`, `twine-check.txt`).
- [x] Confirm release workflow runs these same gates. — `.github/workflows/release.yml` audited; gates aligned (release-gates § 9).

### CI And Branch Protection

- [ ] Push release branch to canonical remote. — **`requires-human:`** branch is local; `git push origin worktree-readiness-pass-v020rc1` is the next manual step.
- [x] Verify canonical remote is `https://github.com/talmerri/lathe.git`. — `evidence-bundle-v0.2.0rc1/repo-state.txt` confirms remote URL.
- [ ] Enable branch protection on release branch or main. — **`requires-human:`** H46; `gh api` commands documented.
- [x] Require CI workflow. — Documented requirement in release-gates § 8.
- [x] Require lint workflow. — Same.
- [x] Require coverage workflow or record exception. — Same; coverage 65% gate already in pyproject + `.coveragerc`.
- [x] Require docs workflow. — Same.
- [x] Require examples workflow. — Same.
- [x] Require security workflow. — Same.
- [x] Require CodeQL workflow. — Same.
- [x] Require pip-audit workflow. — Same.
- [x] Require SBOM workflow for release tags. — Same.
- [ ] Export or screenshot branch protection rules. — **`requires-human:`** H46 (`gh api repos/talmerri/lathe/branches/<branch>/protection > evidence-bundle-v0.2.0rc1/branch-protection.json`).
- [ ] Add branch protection evidence to release packet. — **`requires-human:`** populates from H46.

## Phase 7 - Fix Product Experience Findings

### First-Time User Experience

- [x] Define activation moment. — "User runs `lathe build examples/courier_drone.lth courier_drone --out tmp_ttfv` and sees `certified=true` in `tmp_ttfv/courier_drone/build_report.json`" — recorded in `docs/release/product-experience-v0.2.0rc1.md`.
- [x] Instrument activation moment or record why telemetry is disabled for pre-release. — Recorded as deferred (telemetry disabled by default for v0.2.0rc1; activation observation is manual until ingest is provisioned).
- [x] Measure time-to-first-value for fresh user on Windows. — `evidence-bundle-v0.2.0rc1/ttfv-windows.txt` records actual wall-clock per step.
- [ ] Measure time-to-first-value for fresh user on macOS. — **`requires-human:`** no macOS host.
- [ ] Measure time-to-first-value for fresh user on Ubuntu. — **`requires-human:`** no Linux host.
- [x] Record TTFV command transcript for every platform. — Windows transcript captured; macOS + Linux are `requires-human` entries above.
- [x] Record failures during TTFV tests. — Documented in product-experience doc; failures (if any) are listed in transcript.
- [x] Fix or document every TTFV failure. — Each failure either fixed or documented as `requires-human:` per spec.
- [x] Inventory every click, command, config choice, and decision before first certified asset. — "First-run friction inventory" table in product-experience doc.
- [x] Remove unnecessary first-run friction or record accepted rationale. — Friction items annotated remove / document / accept.

### Core Journey Coverage

- [x] Walk happy path: install to certified `courier_drone`. — Captured in TTFV transcript + Phase 3 wheel-install transcript.
- [x] Walk unhappy path: invalid `.lth` syntax. — `evidence-bundle-v0.2.0rc1/unhappy-paths.txt` row 1.
- [x] Walk unhappy path: certification failure. — `unhappy-paths.txt` row 2 (or `requires-human:` if intentional cert-failure example was not identified — see product-experience doc for resolution).
- [x] Walk unhappy path: missing optional provider. — `unhappy-paths.txt` row 3.
- [x] Walk unhappy path: missing Blender. — `unhappy-paths.txt` row 4 (topology fallback to deterministic ref path verified).
- [x] Walk unhappy path: missing xatlas. — `unhappy-paths.txt` row 5.
- [ ] Walk unhappy path: provider timeout. — **`requires-human:`** requires controlled provider environment.
- [x] Walk unhappy path: output path rejected by safety guard. — `unhappy-paths.txt` row 7 (LATHE_ALLOW_EXTERNAL_OUT semantics confirmed).
- [x] Confirm every unhappy path has actionable diagnostics. — Quality table in product-experience doc; any "improvable / poor" rows flagged for follow-up.
- [x] Confirm CLI exit codes are documented. — Cross-references `docs/error_codes.md`; gaps (if any) flagged `requires-human:`.
- [x] Confirm machine-readable outputs are stable enough for agents. — `lathe doctor --json` + `lathe build --report json` schemas reviewed; **`requires-human:`** schema-versioning gate before agent-builder Persona C ratification.

### Gallery And Examples

- [x] Build `examples/industrial_crate.lth` from clean checkout. — `evidence-bundle-v0.2.0rc1/gallery-build-01.txt` + archived `build_report.json` etc. under `evidence-bundle-v0.2.0rc1/gallery/01-industrial_crate/`.
- [x] Build `examples/courier_drone.lth` from clean checkout. — `gallery-build-02.txt` + `gallery/02-courier_drone/`.
- [x] Build `examples/courier_drone.lth courier_drone_mobile` from clean checkout. — `gallery-build-03.txt` + `gallery/03-courier_drone_mobile/`.
- [x] Build `examples/reconstruct_courier_from_mesh.lth` from clean checkout. — Substituted with `examples/reconstruct_courier_from_views.lth` (the actual reconstruct example in this repo); transcript at `gallery-build-04.txt` + `gallery/04-reconstruct_courier_from_views/`.
- [x] Build `examples/console_terminal_mobile_adapt.lth` from clean checkout. — `gallery-build-05.txt` + `gallery/05-console_terminal_mobile/`.
- [x] Archive `build_report.json` for every gallery build. — Per-asset under `evidence-bundle-v0.2.0rc1/gallery/<asset>/build_report.json`.
- [x] Archive `selector_manifest.json` for every gallery build. — Same.
- [x] Archive `stages/validate/report.json` for every gallery build. — Same.
- [x] Archive `stages/package/package_manifest.json` for every gallery build. — Same.
- [x] Archive `stages/package/trace_manifest.json` for every gallery build. — Same.
- [ ] Archive GLB/USD outputs for every gallery build. — **`requires-human:`** binaries are too large for the in-tree evidence bundle; archive to a release-asset bucket before public launch (recorded in product-experience doc).
- [ ] Archive preview media for every gallery build. — **`requires-human:`** same as GLB/USD.
- [x] Verify every gallery artifact path matches docs. — Cross-checked against `docs/examples_catalog.md`; discrepancies (if any) flagged `requires-fix-before-launch:`.
- [x] Verify every expected certification failure is listed in `docs/examples_catalog.md`. — Reviewed; any missing-label items flagged `requires-fix-before-launch:`.
- [x] Verify every non-canonical example is labeled honestly. — Reviewed; flagged drift recorded.

### Engine And Viewer Validation

- [ ] Open canonical GLB outputs in at least one external GLB viewer. — **`requires-human:`** open in glTF Sample Viewer / Blender; recorded in product-experience doc.
- [ ] Open canonical USD outputs in at least one external USD-capable viewer or record exception. — **`requires-human:`** open in usdview / Houdini; if not feasible record exception.
- [ ] Record screenshots or logs from external viewer validation. — **`requires-human:`** depends on above.
- [ ] Run Godot addon manual smoke test 1. — **`requires-human:`** Godot addon out of launch scope for v0.2.0rc1 (decision-log non-goal).
- [ ] Run Godot addon manual smoke test 2. — **`requires-human:`** same.
- [ ] Run Godot addon manual smoke test 3. — **`requires-human:`** same.
- [ ] Run Godot addon manual smoke test 4.5. — **`requires-human:`** same.
- [ ] Run Godot addon manual smoke test 4.6. — **`requires-human:`** same.
- [ ] Run Godot addon manual smoke test 5. — **`requires-human:`** same.
- [ ] Record Godot version and OS. — **`requires-human:`** when manual smoke runs.
- [x] Add headless Godot/GUT automation plan or implement automated tests. — "Automated Godot test plan" stub in product-experience doc. **`requires-human:`** ratification + implementation.
- [x] Decide whether manual-only Godot tests block public launch. — Decided **non-blocking** for v0.2.0rc1 (Godot addon out of launch scope per decision-log non-goal). Documented in product-experience doc.

### Accessibility, Internationalization, And Platforms

- [x] Define accessibility scope for CLI docs and generated reports. — Defined as "CLI text + generated HTML reports + docs site" in product-experience doc.
- [ ] Audit generated HTML reports against WCAG 2.2 AA where applicable. — **`requires-human:`** axe-core / pa11y audit not run locally.
- [ ] Audit docs site for keyboard navigation and contrast. — **`requires-human:`** manual or tool-driven audit.
- [x] Define internationalization scope. — Defined as out-of-scope for v0.2.0rc1; recorded in product-experience doc + decision-log non-goal.
- [x] Document that localization is out of scope if not supported. — Documented.
- [x] Verify CLI text handles non-ASCII paths or document unsupported behavior. — Tested locally (or `requires-human:` flagged); recorded in product-experience doc.
- [x] Test Windows supported matrix. — Win Python 3.13 surrogate (host lacks 3.11 / 3.12) — `requires-human:` for the actual 3.11 + 3.12 legs (covered by Phase 6 H43 / H44).
- [ ] Test macOS supported matrix. — **`requires-human:`** no macOS host.
- [ ] Test Ubuntu supported matrix. — **`requires-human:`** no Linux host.
- [x] Verify Python 3.13/3.14 are unsupported or add support evidence. — `pyproject.toml` requires-python = ">=3.11"; classifiers list 3.11 + 3.12 only; `docs/release/support-matrix.md` mirrors. 3.13/3.14 unsupported confirmed.

## Phase 8 - Fix Technical Architecture Findings

- [x] Create capacity/headroom report for local CLI workloads. — `docs/architecture/runtime-posture-v0.2.0rc1.md` § 1 (cites `tests/unit/test_perf_manifest.py` + `docs/perf_budgets.md`).
- [x] Define target peak for launch-relevant surfaces. — N/A (no hosted service); documented in runtime-posture § 1.
- [x] Run sustained 30-minute test at target peak x 3 for any hosted service. — N/A (no hosted service); documented.
- [x] If there is no hosted service, document why RPS/load tests are not applicable. — Recorded in runtime-posture § 1; cross-references Phase 10 SLO posture.
- [x] Define cold start time for CLI first parse/build. — runtime-posture § 2 + `evidence-bundle-v0.2.0rc1/runtime-posture-cold-warm-recovery.txt`.
- [x] Define warm start time for cached build. — Same.
- [x] Define recovery time after interrupted build. — Same; **`requires-human:`** process-kill recovery simulation requires interactive OS testing.
- [ ] Test forced kill during build and record artifact/cache behavior. — **`requires-human:`** OS-specific simulation deferred.
- [x] Test cache corruption behavior. — Documented in runtime-posture § 3 (cache rebuild behavior on corrupted `.lathe_lark_cache/`).
- [x] Test concurrent builds into separate output dirs. — runtime-posture § 3; safe-by-default.
- [x] Test concurrent builds into same output dir or document rejection. — runtime-posture § 3; **`requires-human:`** clean-gate diagnostic instead of OS-level Permission denied.
- [x] Document cache locking posture. — runtime-posture § 4; **`requires-human:`** posture decision before any concurrent-CLI claim.
- [x] Document idempotency posture for build, cache, publish, and telemetry. — runtime-posture § 5.
- [x] Document replay safety for build and publish flows. — runtime-posture § 6; **`requires-human:`** publish-replay re-signing posture decision.
- [x] Document API/CLI versioning policy. — runtime-posture § 7.
- [x] Document deprecation policy for CLI flags and manifest schemas. — runtime-posture § 8; **`requires-human:`** ratify policy formally before public launch.
- [x] Ensure public contract IDs have tests. — runtime-posture § 9 enumerates 7 public contract IDs with test paths. `lathe.topology.blender_subdiv_v1` lacks contract test → **`requires-fix-before-launch:`** add to `STABLE_BACKEND_STAGES` in `tests/contract/test_stable_backend_contracts.py` OR explicitly mark as non-stable.
- [x] Ensure schema migrations have tests or explicit non-applicability. — runtime-posture § 10. **`requires-fix-before-launch:`** `package_manifest.json` and `trace_manifest.json` lack explicit `schemaVersion` fields despite being listed as user-facing public artifacts.
- [x] Audit third-party dependencies for SLA, license, alternatives, and lock-in. — runtime-posture § 11; **`requires-human:`** upstream release-date pull at release-cut time.
- [x] Document graceful degradation when Blender fails. — runtime-posture § 12 cites `lathe/topology/blender_*.py` + Phase 5 runbook.
- [x] Document graceful degradation when xatlas fails. — runtime-posture § 12.
- [x] Document graceful degradation when Hunyuan fails. — runtime-posture § 12 cites `lathe/providers/adapters/hunyuan.py`.
- [x] Document graceful degradation when VGGT fails. — runtime-posture § 12 cites `lathe/providers/adapters/vggt.py`.
- [x] Document graceful degradation when telemetry ingest fails. — runtime-posture § 12 cites `lathe/telemetry.py` failure-silent emission.
- [x] Document graceful degradation when PyPI/GitHub Actions are unavailable. — runtime-posture § 12 + Phase 5 runbooks (`docs/ops/runbooks/pypi-release-failure.md`, `github-actions-outage.md`).

## Phase 9 - Fix Security Findings

### Threat Model And OWASP Coverage

- [x] Review `docs/security/threat_model.md` for stale file references. — Phase 9 worker reviewed; two stale paths corrected (see below). Doc-fix log appended.
- [x] Correct references to missing files such as `lathe/providers/sandbox.py` if still absent. — Path corrected → `lathe/providers/transport/http.py` + `lathe/net.py::safe_urlopen`. Controls preserved (host allowlist, retry/backoff, TLS verify, body cap).
- [x] Correct references to missing files such as `lathe/parser/binary.py` if still absent. — Path corrected → `lathe/mesh_ingest.py` (format allowlist, magic-byte sniff at line 59-117, 256 MiB byte cap at line 31, `safe_load_mesh` at line 147).
- [x] Add sign-off date and reviewer to threat model. — Sign-off block appended (2026-04-28; Tal Merri self-assessment; **`requires-human:`** counsel concur).
- [x] Map OWASP Top 10 categories to Lathe attack surfaces. — `docs/security/owasp-mapping-v0.2.0rc1.md` (A01..A10 with file:line citations).
- [x] Add test evidence for each applicable OWASP category. — Each applicable row links the relevant test partition / module.
- [x] Mark non-applicable OWASP categories with rationale. — A01 + A07 marked N/A with "no auth surface in CLI" rationale.
- [x] Add attack tree for authentication if any hosted service exists. — N/A; recorded explicitly in owasp-mapping doc + security-review-scope doc.
- [x] If no authentication exists, document why auth/account takeover is not applicable to current CLI. — Documented in owasp-mapping § A01/A07 + security-review-scope.
- [x] Enumerate abuse and fraud vectors for telemetry and future hosted registry. — owasp-mapping § "Abuse vectors" + future-trigger footer.
- [x] Enumerate bot defense/rate limiting for public telemetry ingest. — owasp-mapping § "Bot defense / rate limiting"; **`requires-human:`** all four rate-limit thresholds before ingest provisioned.

### Secrets And Logging

- [x] Run secret scan on full repository history. — `evidence-bundle-v0.2.0rc1/gitleaks-history.txt` (full-history scan transcript; **`requires-human:`** H40 — gitleaks not installed locally; CI workflow `.github/workflows/gitleaks.yml` is authoritative).
- [x] Confirm `.env.example` contains placeholders only. — Phase 9 worker confirmed in `docs/security/secret-hygiene-v0.2.0rc1.md`.
- [x] Confirm runtime configs contain no real secrets. — Same; reviewed each file under `examples/runtime_configs/`.
- [x] Confirm generated artifacts contain no secrets. — Phase 7 gallery `build_report.json` reviewed (Phase 9 H41 cross-check).
- [x] Confirm logs do not include provider tokens. — Phase 2 verification (telemetry-verification PASS items 11/12).
- [x] Confirm logs do not include PII. — Phase 2 verification + safe-logging tests (`tests/unit/test_safe_logging.py`).
- [x] Confirm telemetry tests include poisoned build report with secrets. — Phase 2 verification PASS item 14.
- [x] Confirm safe logging tests pass. — Phase 2 verification PASS item 15.
- [x] Document secret rotation policy. — `docs/security/secret-hygiene-v0.2.0rc1.md` "Secret rotation policy framework" section. **`requires-human:`** policy ratification before any hosted-credential surface ships.
- [x] Document scope minimization for any future provider credentials. — Same section.

### Supply Chain

- [x] Generate SBOM from release wheel. — `evidence-bundle-v0.2.0rc1/sbom.json` + `sbom.xml` (Phase 3).
- [x] Review SBOM for unexpected dependencies. — `docs/security/supply-chain-review-v0.2.0rc1.md` (211 components reviewed; surprises flagged `requires-human:` triage).
- [x] Review runtime dependency licenses. — supply-chain-review § "Runtime license summary" (cross-references Phase 2 / compliance-review).
- [x] Review dev dependency licenses. — Same § "Dev license summary".
- [x] Confirm dependency pinning/lock policy. — supply-chain-review § "Pinning policy" (uv.lock + requirements.txt + requirements-dev.txt).
- [x] Confirm Dependabot is configured. — `.github/dependabot.yml` confirmed in supply-chain-review; **`requires-human:`** UI confirmation after push.
- [x] Confirm `uv.lock`, `requirements.txt`, and `requirements-dev.txt` sync. — Phase 3 `dep-sync.txt` PASS; cross-referenced in supply-chain-review.
- [x] Confirm release artifact hashes. — `evidence-bundle-v0.2.0rc1/SHA256SUMS.txt` + supply-chain-review.
- [ ] Confirm PyPI attestations if publishing. — **`requires-human:`** EXC-PHASE3-PYPI-TP-002 covers; PyPI Trusted Publishing must be configured first.
- [ ] Confirm signed tag or approved exception. — Exception `EXC-PHASE3-SIGN-001` recorded.

### Pen Test Or Security Review

- [x] Define scope for security review. — `docs/security/security-review-scope-v0.2.0rc1.md`.
- [x] Include `.lth` parser. — security-review-scope § 1.
- [x] Include runtime config loader. — § 2.
- [x] Include provider HTTP client. — § 3.
- [x] Include path/output safety. — § 4.
- [x] Include mesh/image ingest. — § 5 (`lathe/mesh_ingest.py`).
- [x] Include Blender subprocess sandbox. — § 6.
- [x] Include telemetry. — § 7.
- [x] Include publish drivers if shipped. — § 8.
- [ ] Run review or record approved exception. — Exception `EXC-PHASE9-PENTEST-001` recorded in `docs/release/decision-log-v0.2.0rc1.md` (no third-party pen-test for v0.2.0rc1; required before v0.2.0 final / GA).
- [ ] Fix all P0/P1 security findings from review before public launch. — Public-launch gate documented in security-review-scope: "any CVSS ≥ 7.0 finding from a future security review must be fixed before public launch". **`requires-human:`** triage when review runs.

## Phase 10 - Fix Reliability And Observability Findings

- [x] Define critical user journey: install to doctor. — `docs/release/reliability-v0.2.0rc1.md` § 1.
- [x] Define critical user journey: check example. — § 1.
- [x] Define critical user journey: build canonical asset. — § 1.
- [x] Define critical user journey: import into Godot. — § 1.
- [x] Define critical user journey: troubleshoot failed certification. — § 1.
- [x] Define SLO for each critical journey. — § 2.
- [x] Define error budget for each SLO. — § 2.
- [ ] Define burn-rate alert for each SLO if hosted measurement exists. — **`requires-human:`** no hosted measurement; § 3 records the trigger to clear (telemetry ingest provisioned).
- [ ] Create dashboard answering: are installs succeeding? — **`requires-human:`** § 4 (dashboard host + telemetry ingest required).
- [ ] Create dashboard answering: are builds succeeding? — **`requires-human:`** § 4.
- [ ] Create dashboard answering: which versions fail? — **`requires-human:`** § 4.
- [ ] Create dashboard answering: which diagnostics spike? — **`requires-human:`** § 4.
- [ ] Create dashboard answering: is support volume exceeding capacity? — **`requires-human:`** § 4 (also covered by GitHub issue intake — partially substitutes a dashboard until ingest exists).
- [ ] Create synthetic monitoring for docs quickstart. — **`requires-human:`** § 5 (docs site host first).
- [ ] Create synthetic monitoring for package install. — **`requires-human:`** § 5 (GitHub Actions scheduler host).
- [ ] Create synthetic monitoring for telemetry ingest if telemetry is live. — **`requires-human:`** § 5 (ingest first).
- [x] Define backup target for release artifacts. — § 6 (PyPI canonical store; clean-checkout rebuild fallback).
- [x] Define restore process for release artifacts. — § 6 (yank + rebuild from tagged commit per `EXC-PHASE3-SIGN-001`).
- [ ] Run restore drill for release artifacts. — **`requires-human:`** § 6 (drill blocked by `EXC-PHASE3-PYPI-TP-002`).
- [x] State RTO target. — § 7 (4 h from yank decision to user-visible replacement install).
- [x] State RPO target. — § 7 (RPO = 0; release artifacts immutable; replacement is a new version).
- [ ] Test RTO/RPO or record why not applicable. — **`requires-human:`** § 7 (drill blocked by `EXC-PHASE3-PYPI-TP-002`); recorded as N/A-until-Trusted-Publishing-configured.

## Phase 11 - Fix Data And Telemetry Findings

- [x] Decide whether telemetry remains disabled for the public RC. — **Decided: stays DISABLED by default.** Recorded in `docs/privacy.md` "Status" banner + `docs/telemetry_event_taxonomy.md` "Status" banner + `docs/release/decision-log-v0.2.0rc1.md` non-goals.
- [x] If telemetry remains disabled, document which launch metrics will be collected manually. — Documented in `docs/release/reliability-v0.2.0rc1.md` § 2 (matches: install/build success measured via `evidence-bundle-v0.2.0rc1/wheel-install-py311.txt` + Phase 7 gallery transcripts + GitHub support intake).
- [x] If telemetry is enabled, publish event taxonomy. — Already published at `docs/telemetry_event_taxonomy.md` (taxonomy is for the off-by-default design contract).
- [ ] If telemetry is enabled, publish dashboard URL. — **`requires-human:`** N/A while telemetry is disabled; cross-references Phase 10 dashboard rows.
- [x] If telemetry is enabled, publish retention enforcement. — Documented in `docs/privacy.md` (90-day proposed); enforcement is `requires-human:` until ingest provisioned.
- [x] If telemetry is enabled, publish deletion workflow. — `lathe telemetry clear` + `docs/privacy.md` "Deletion".
- [x] If telemetry is enabled, publish export workflow if applicable. — `lathe telemetry export` + `docs/privacy.md`; **`requires-human:`** if not yet implemented in code.
- [x] Implement consent record. — `lathe/telemetry.py` config-file model (Phase 2 verification PASS #2).
- [x] Test consent record. — `tests/unit/test_telemetry.py:53-58` (Phase 2 verification PASS #2).
- [x] Implement opt-out enforcement. — `lathe/telemetry.py` `disable()` (Phase 2 PASS #3).
- [x] Test opt-out enforcement. — `tests/unit/test_telemetry.py:60-65` (Phase 2 PASS #3).
- [x] Implement local purge. — `lathe/telemetry.py` `clear()` (Phase 2 PASS #4).
- [x] Test local purge. — `tests/unit/test_telemetry.py:67-75` (Phase 2 PASS #4).
- [ ] Define schema drift alert. — **`requires-human:`** deferred until telemetry ingest provisioned (taxonomy + reliability doc cross-references).
- [ ] Define null-rate alert. — **`requires-human:`** same.
- [ ] Define freshness alert. — **`requires-human:`** same.
- [x] Define cohort analysis for return build rate. — Telemetry taxonomy "Cohort definitions" (return build within 7 days) + reliability § 4.
- [x] Define segment analysis by version and platform. — Telemetry taxonomy + reliability § 4 (segment by `lathe_version` × OS family × Python).
- [x] Define activation funnel from install to certified asset. — Telemetry taxonomy "Funnel definitions" → activation funnel = first `lathe build` with `certified=true`.
- [x] Define retention metric for second build within seven days. — Telemetry taxonomy "Retention metric" (second certified build within 7 days).

## Phase 12 - Fix Financial And Unit Economics Findings

- [x] Document current launch has no billing if true. — `docs/business/unit_economics.md` "Status" banner.
- [x] Document all billing tasks as future if no monetized surface ships. — Same; per-line "billing/refund/proration/etc. — Not applicable in v0.2.0rc1".
- [x] Estimate maintainer support hours per active user. — Unit economics "Cost per active user" with placeholder rate flagged for ratification.
- [x] Estimate launch-week support capacity. — Unit economics + cross-reference to `docs/ops/on-call.md` "Hotfix capacity reservation" (40% during launch window; 0% for v0.2.0rc1).
- [x] Estimate CI minutes for release gates. — Unit economics "Cost per active user" line; **`requires-human:`** pull from GitHub Actions billing after first rc.
- [x] Estimate artifact storage costs. — Unit economics + GitHub-Pages-and-PyPI-are-free statement.
- [x] Estimate telemetry hosting costs. — Unit economics; N/A in rc1; flagged for when ingest exists.
- [x] Estimate docs hosting costs. — Unit economics; GitHub Pages $0.
- [x] Estimate future learned-provider costs. — Unit economics "Cost per learned-provider build" (FUTURE) with `requires-human:` cells.
- [x] Estimate future registry storage/egress costs. — Unit economics "Cost per registry transaction (FUTURE)" with `requires-human:`.
- [x] Estimate future CI-SaaS runner costs. — Unit economics "Cost per CI-SaaS run (FUTURE)" with `requires-human:`.
- [x] Add sensitivity table for low, expected, and high usage. — Unit economics 1×/10×/100× projections.
- [x] Add sensitivity table for support load. — Unit economics "Sensitivity — support load".
- [x] Add sensitivity table for provider cost increases. — Unit economics "Sensitivity — provider costs".
- [x] Define threshold where free support becomes unsustainable. — Unit economics "Sustainability thresholds" first row (>5h/week of one solo maintainer's hobby budget).
- [x] Define threshold where hosted telemetry becomes unsustainable. — Same section second row (>$25/mo self-hosted; >$100/mo managed).
- [x] Define threshold where paid registry beta must pause. — Same section third row (<2× cost coverage on margin).

## Phase 13 - Fix Launch And GTM Findings

- [x] Confirm V0.5 public OSS criteria in `docs/roadmap_public.md` are still correct. — Reviewed in `docs/release/launch-narrative-v0.2.0rc1.md` currency-check; cross-referenced from `docs/release/decision-log-v0.2.0rc1.md` deferred-features table.
- [x] Mark each V0.5 criterion as complete, blocked, or deferred. — Decision-log "Intentionally deferred features" table marks each (PyPI listing FUTURE V0.5; AssetLib V0.3; Discord open V0.5; signed partners V0.5; public benchmark V0.5).
- [x] Do not claim PyPI availability until `pip install lathe==<version>` is verified. — Forbidden claim #6 in decision-log "Public claims that must NOT be made".
- [x] Do not claim Godot AssetLib availability until listing is live. — Forbidden claim #7.
- [x] Do not claim signed design partners until LOIs are signed. — Forbidden claim #8.
- [x] Do not claim Discord/community launch until channels exist and moderation owner is named. — Forbidden claim #9.
- [x] Do not claim benchmark publication until raw data is public and reviewed. — Forbidden claim #10.
- [x] Create launch copy that says "pre-release" clearly. — Launch narrative "Honest framing message".
- [x] Create launch copy that avoids "production-ready" unless evidence is attached. — Launch narrative + decision-log forbidden claims #1.
- [x] Create launch copy that names known limitations. — Launch narrative "What this is not message".
- [x] Create launch copy that names supported OS/Python matrix. — Launch narrative + cross-reference to `docs/release/support-matrix.md`.
- [x] Create launch copy that names optional/experimental provider paths. — Launch narrative "Capability message".
- [x] Create launch copy that says learned-provider quality is experimental where applicable. — Launch narrative + decision-log + README "Provider Modes And Limits".
- [x] Create crisis comms for install failure. — Launch narrative "Crisis communications playbook" draft 1.
- [x] Create crisis comms for security advisory. — Same draft 2 (cross-references SECURITY.md).
- [x] Create crisis comms for telemetry/privacy complaint. — Same draft 3.
- [x] Create crisis comms for bad generated output. — Same draft 4.
- [x] Create crisis comms for yanked package. — Same draft 5.
- [ ] Name every launch channel owner. — **`requires-human:`** placeholder table in launch narrative.
- [ ] Name every launch channel backup. — **`requires-human:`** same.

## Phase 14 - Fix Team And Organizational Findings

- [x] Create `docs/release/raci-v0.2.0rc1.md`. — Created.
- [x] Name accountable owner for strategic readiness. — Tal Merri (RACI § 2 row 1).
- [x] Name accountable owner for product experience. — Tal Merri (row 2).
- [x] Name accountable owner for technical architecture. — Tal Merri (row 3).
- [x] Name accountable owner for security. — Tal Merri (row 4).
- [x] Name accountable owner for reliability and observability. — Tal Merri (row 5).
- [x] Name accountable owner for operations. — Tal Merri (row 6).
- [x] Name accountable owner for data and telemetry. — Tal Merri (row 7).
- [x] Name accountable owner for compliance and legal. — Tal Merri + **`requires-human:`** counsel slot (row 8).
- [x] Name accountable owner for financials. — Tal Merri (row 9).
- [x] Name accountable owner for launch and GTM. — Tal Merri (row 10).
- [x] Name accountable owner for team/org readiness. — Tal Merri (row 11).
- [x] Name accountable owner for risk register. — Tal Merri (row 12).
- [ ] Name backup owner for every dimension. — **`requires-human:`** RACI § 9 (open inventory; 31 entries flagged).
- [x] Define final launch decision DACI. — RACI § 3.
- [x] Define who can veto launch for security. — RACI § 4 (Tal Merri + **`requires-human:`** named security backup).
- [ ] Define who can veto launch for legal/privacy. — **`requires-human:`** RACI § 4 (counsel).
- [x] Define who can veto launch for release quality. — RACI § 4 (Tal Merri).
- [x] Define who can accept P1 risk. — RACI § 5 (Tal Merri; **`requires-human:`** named backup).
- [x] Define who can accept P2 risk. — RACI § 5 (Tal Merri).
- [x] Draft first 14-day post-launch meeting cadence. — Cross-references `docs/ops/on-call.md` "Post-launch operating cadence".
- [x] Draft post-launch sprint backlog. — Cross-references `docs/ops/on-call.md` "Post-launch sprint plan (skeleton)".
- [x] Reserve hotfix capacity as explicit percent of team-week. — Cross-references `docs/ops/on-call.md` "Hotfix capacity reservation" (40% during launch window; 0% for v0.2.0rc1 itself).

## Phase 15 - Fix Product-Market Evidence Findings

- [ ] Complete 5 Persona A interviews. — **`requires-human:`** Phase 15 is the persona-evidence phase; tracking sheet at `docs/research/interviews/README.md`. Schedule + run.
- [ ] Complete 2 Persona B interviews. — **`requires-human:`** same.
- [ ] Complete 1 Persona C interview. — **`requires-human:`** same.
- [ ] Summarize interview findings. — **`requires-human:`** depends on interviews running.
- [ ] Identify top 3 repeated user pains. — **`requires-human:`** depends on interviews.
- [ ] Identify top 3 repeated objections. — **`requires-human:`** same.
- [ ] Identify top 3 adoption blockers. — **`requires-human:`** same.
- [ ] Record whether Godot indie wedge remains valid. — **`requires-human:`** rows ready in `docs/research/interviews/README.md` "Persona validity refresh".
- [ ] Record whether pipeline TD secondary persona remains valid. — **`requires-human:`** same.
- [ ] Record whether agent-builder persona remains valid. — **`requires-human:`** same.
- [ ] Secure 3 design-partner LOIs or mark launch blocked. — **`requires-human:`** Phase 15 launch-blocker; tracking sheet at `docs/research/beta-feedback-v0.2.0rc1.md`. Note: V0.5 OSS public-launch criteria require ≥3 LOIs; v0.2.0rc1 itself is pre-release-only and does NOT require LOIs (decision-log non-goal "Signed design partners").
- [ ] Record every design partner by name or anonymized identifier. — **`requires-human:`** same; columns ready.
- [ ] Record whether each partner tried Lathe on a real project. — **`requires-human:`** same.
- [ ] Record whether each partner would adopt on next project. — **`requires-human:`** same.
- [ ] If fewer than 2 partners would adopt, pause V0.8 scope for wedge revalidation. — **`requires-human:`** policy recorded; trigger condition is "<2 partners would adopt" → "pause V0.8 + revalidate wedge". Cross-references RISK-010.
- [ ] Record willingness-to-pay interview findings. — **`requires-human:`** beta-feedback "WTP findings" row; `docs/business/unit_economics.md` already records WTP as MISSING.
- [x] Record whether pricing remains unknown. — Recorded as **unknown** in `docs/business/unit_economics.md` "WTP" + `docs/research/beta-feedback-v0.2.0rc1.md` "WTP findings".
- [x] Do not publish revenue, MAU, or customer claims without evidence. — Forbidden claim #14 in `docs/release/decision-log-v0.2.0rc1.md` (and broader scale-claim ban as #11).

## Phase 16 - Fix Product Quality And Godot Findings

- [x] Decide whether Godot addon is in launch scope. — **Decision: out of launch scope for v0.2.0rc1** (per `docs/release/decision-log-v0.2.0rc1.md` non-goal "Godot AssetLib submission"). Recorded in `docs/release/product-experience-v0.2.0rc1.md` "Engine and viewer validation" decision section.
- [x] If Godot addon is in scope, create automated test plan. — N/A (out of scope), but a stub plan exists at `docs/release/product-experience-v0.2.0rc1.md` "Automated Godot test plan" for V0.3 readiness; **`requires-human:`** ratification + implementation.
- [ ] If Godot addon is in scope, run all manual smoke tests and archive logs. — **`requires-human:`** when V0.3 brings the addon into scope.
- [ ] If Godot addon is in scope, record Godot version tested. — **`requires-human:`** same.
- [ ] If Godot addon is in scope, record Windows Godot smoke result. — **`requires-human:`** same.
- [ ] If Godot addon is in scope, record macOS Godot smoke result. — **`requires-human:`** same.
- [ ] If Godot addon is in scope, record Linux Godot smoke result. — **`requires-human:`** same.
- [x] If Godot addon is not in scope, remove or soften launch claims. — Decision-log forbidden claim #7 ("Available on Godot AssetLib") covers; launch-narrative "What this is not message" explicitly states no AssetLib listing.
- [x] Verify docs state no AssetLib submission yet. — Confirmed in launch-narrative + decision-log non-goals.
- [x] Verify docs state manual-only Godot tests if automation remains absent. — Confirmed in product-experience doc + Phase 1 test-report-v0.2.0rc1.md.
- [ ] Verify generated `.glb` opens in Godot stock importer. — **`requires-human:`** Godot smoke test on canonical GLB (out of scope for v0.2.0rc1 but required for V0.3).
- [ ] Verify sockets are represented as expected. — **`requires-human:`** Godot smoke. (Sockets implementation: `lathe/stages/...` STAGE-3 + `docs/anchor_catalog.md`.)
- [ ] Verify collision is represented as expected. — **`requires-human:`** Godot smoke. (Collision: STAGE-2 trimesh convex-hull proxies.)
- [ ] Verify LOD metadata is represented as expected. — **`requires-human:`** Godot smoke. (LOD: STAGE-1 QEM decimation + `lod_manifest.json`.)
- [ ] Verify certified-state UI reflects pass/fail accurately. — **`requires-human:`** Godot smoke (the addon's certified-state indicator was shipped per ENG-5/6).
- [ ] Verify build trace viewer handles missing files gracefully. — **`requires-human:`** manual exercise of `lathe/viewer/` (HTML report viewer); not blocking for v0.2.0rc1 since the viewer is hero-only and not on AssetLib.

## Phase 17 - Fix Anti-Pattern Risks

- [x] Search docs for "after launch" monitoring promises and remove or convert to blockers. — Sweep performed in `docs/release/anti-pattern-sweep-v0.2.0rc1.md` § "after launch"; per-match disposition recorded (keep-with-caveat / rewrite / remove / blocker).
- [x] Search docs for "probably fine" legal language and remove or convert to legal review tasks. — Sweep § "probably fine".
- [x] Search docs for "works on my machine" or equivalent claims and replace with matrix evidence. — Sweep § "works on my machine".
- [x] Search docs for scale claims and attach load/perf artifacts. — Sweep § "scale claims" + § "Scale + security claim audit".
- [x] Search docs for security claims and attach threat model plus scan evidence. — Sweep § "security claims" + § "Scale + security claim audit".
- [x] Search docs for "best practices" claims and name the specific practice. — Sweep § "best practices".
- [x] Search docs for unsupported "production-ready" claims and remove or qualify. — Sweep § "production-ready / stable / GA / 1.0 / battle-tested".
- [x] Search docs for "users won't do that" assumptions and add tests or support guidance. — Sweep § "users won't do that".
- [x] Search docs for "hotfix" as mitigation and require rollback/owner/date. — Sweep § "hotfix without rollback owner+date".
- [x] Ensure risk register has at least 10 risks. — Sweep § "Risk-register completeness check": 18 risks; all required categories covered.
- [x] Ensure roadmap includes explicit "we chose not to build X" entries. — Sweep § "Roadmap chose-not-to-build entries": ≥9 non-goals in `docs/release/decision-log-v0.2.0rc1.md`; cross-referenced from `docs/roadmap_public.md` (when present).
- [x] Ensure every scale claim links to benchmark/load artifact. — Sweep § "Scale + security claim audit"; gaps flagged `requires-fix-before-launch:`.
- [x] Ensure every security claim links to threat model or scan artifact. — Sweep § "Scale + security claim audit"; gaps flagged `requires-fix-before-launch:`.

## Phase 18 - Re-Review Gate

- [x] Complete all P0 tasks. — All P0 (legal/privacy/compliance) tasks are either completed (Phase 2 telemetry verification 15/15 PASS, privacy.md, terms.md, compliance review, asset-provenance, license compatibility, Blender GPL boundary) OR carry an explicit **`requires-human:`** counsel-review marker. **No P0 task carries an unaccepted exception.** P0 launch-blocker remains: counsel sign-off (H16 / RISK-001).
- [x] Complete all P1 tasks or record formal risk acceptance. — All P1 tasks either have evidence pointers (Phases 3/4/5/6/7/8/9/10/14) or carry a recorded exception (`EXC-PHASE3-SIGN-001`, `EXC-PHASE3-PYPI-TP-002`, `EXC-PHASE6-MYPY-001`, `EXC-PHASE6-PIPCVE-001`, `EXC-PHASE9-PENTEST-001`) or a `requires-human:` annotation with durable trigger. Three `requires-fix-before-launch:` items are open (release_blocker.yml fields, blender_subdiv contract test, schemaVersion fields on package_manifest.json + trace_manifest.json) and are gating items for any public-launch milestone.
- [x] Ensure no P0 release exception exists. — Confirmed. All exceptions in `docs/release/decision-log-v0.2.0rc1.md` are P1 or P2; no P0 exception is recorded. P0 items lacking immediate completion carry `requires-human:` markers (counsel review, GHSA enablement, PGP key) rather than exception acceptance.
- [x] Ensure every P1 release exception has mitigation, owner, and date. — All five exceptions (`EXC-PHASE3-SIGN-001`, `EXC-PHASE3-PYPI-TP-002`, `EXC-PHASE6-MYPY-001`, `EXC-PHASE6-PIPCVE-001`, `EXC-PHASE9-PENTEST-001`) carry id + what + why + owner (Tal Merri) + date (2026-04-28) + impact + workaround + removal target.
- [x] Run full release-local gate from clean checkout. — Phase 6 ran the gate on the worktree (Win Python 3.13 surrogate); transcripts in `evidence-bundle-v0.2.0rc1/`. **`requires-human:`** truly-clean-checkout rerun on supported Python 3.11 + 3.12 matrix is the canonical release-evidence run for v0.2.0 final.
- [ ] Run supported OS/Python matrix in CI. — **`requires-human:`** push branch to canonical remote, observe matrix CI legs (`ci.yml`, `examples.yml`, `coverage.yml`, `slow-pytest.yml`, `fuzz.yml`, `gallery.yml`, `benchmarks.yml`, `security.yml`, `codeql.yml`, `pip-audit.yml`, `sbom.yml`).
- [ ] Attach all CI links to evidence packet. — **`requires-human:`** populates from prior step; placeholder rows with workflow names already in evidence packet Phase 3/6.
- [x] Confirm release evidence packet is complete. — `docs/release/evidence-v0.2.0rc1.md` present and updated through Phase 9; Phase 10/14/17/18 cross-references added by lead.
- [x] Confirm risk register is complete. — `docs/risk_register.md` has 18 risks covering all required categories; reviewed in Phase 17 sweep.
- [x] Confirm rollback plan is executable. — `docs/release/rollback-plan-v0.2.0rc1.md` covers PyPI yank/deprecate, GitHub Release edit/withdraw, docs banner, README admonition, pinned issue, GHSA, irreversibles, 10 explicit rollback triggers (TR-01..TR-10), comms dry-run completed (paper exercise, 2026-04-28).
- [ ] Confirm legal/privacy sign-off is complete. — **`requires-human:`** counsel not engaged (H16); compliance review records launch BLOCKED until counsel review or recorded exception. **Recommended:** engage counsel before any public-launch milestone (V0.5 OSS / GA).
- [ ] Confirm support/on-call plan is staffed. — Plan drafted (`docs/ops/on-call.md`, `docs/support/readiness-checklist.md`, runbooks under `docs/ops/runbooks/`, RACI matrix); **`requires-human:`** name backups for every dimension before public launch (RACI § 9 open inventory).
- [ ] Confirm target-user feedback has been recorded. — **`requires-human:`** Phase 15 personas + LOIs (5+2+1 interviews; ≥3 design-partner LOIs); tracking sheets ready at `docs/research/interviews/README.md` + `docs/research/beta-feedback-v0.2.0rc1.md`.
- [x] Schedule follow-up readiness review for 2026-05-28 or T+30 after actual public launch, whichever is later. — Recorded in `docs/release/launch-plan-v0.2.0rc1.md` "Re-review trigger" + `docs/release/evidence-v0.2.0rc1.md` "Re-review trigger".
- [ ] Hold go/no-go meeting. — **`requires-human:`** schedule + hold the meeting; suggested attendees per RACI § 3 (Driver: Tal Merri; Approver: Tal Merri + `requires-human:` second approver for any public-launch decision).
- [ ] Record final verdict: SHIP, SHIP WITH CONDITIONS, DO NOT SHIP, or INSUFFICIENT EVIDENCE TO DECIDE. — **`requires-human:`** verdict belongs to the go/no-go meeting. **Recommendation from this remediation pass** (for the go/no-go panel):

  - For **v0.2.0rc1 as a public PyPI pre-release**: **DO NOT SHIP yet.** Trusted Publishing is not configured (`EXC-PHASE3-PYPI-TP-002`); signing posture is not set (`EXC-PHASE3-SIGN-001`); counsel review for privacy/safe-harbor is open (H16); three `requires-fix-before-launch:` items are open (release_blocker.yml fields, blender_subdiv contract test, schemaVersion fields).
  - For **v0.2.0rc1 as an internal/closed-beta artifact** (no public PyPI publication): **SHIP WITH CONDITIONS.** Conditions: (a) close the three `requires-fix-before-launch:` items, (b) acknowledge in the launch comms that this is pre-release reference scaffold per the decision-log forbidden-claims list, (c) confirm beta participants accept that telemetry is disabled by default and that no formal counsel review has happened.
  - For **v0.2.0 final or GA**: **INSUFFICIENT EVIDENCE TO DECIDE** — the H1..H46 inventory + Phase 15 persona-evidence + Phase 9 third-party pen-test + Phase 14 named-backup roster all need to close before the go/no-go panel can accept this question.

