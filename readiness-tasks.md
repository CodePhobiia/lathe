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

- [ ] Update `docs/lathe_prd.md` with a current version number.
- [ ] Add a `Last reviewed` date to `docs/lathe_prd.md`.
- [ ] Add named product owner and reviewer to `docs/lathe_prd.md`.
- [ ] Add one-sentence problem definition with no jargon.
- [ ] Add one-sentence target user definition with no jargon.
- [ ] Mark every PRD requirement as `supported`, `preview`, `experimental`, `future`, or `rejected`.
- [ ] Add links from PRD requirements to tests, docs, examples, or explicit gaps.

### Architecture And Technical Design

- [ ] Confirm `docs/architecture/overview.md` is current for the release branch.
- [ ] Create `docs/architecture/technical-design-v0.2.0rc1.md`.
- [ ] Document all release-supported components and their failure modes.
- [ ] Document all single points of failure.
- [ ] Document all optional tools and how the system behaves when each is absent.
- [ ] Document database/storage posture, even if the current answer is "local files only".
- [ ] Document migration posture for package manifests, trace manifests, snapshots, and stable contracts.
- [ ] Link architecture docs to contract tests and stable schema tests.

### Test Reports

- [ ] Create `docs/release/test-report-v0.2.0rc1.md`.
- [ ] Record full `python -m pytest -q` results from Python 3.11 on Ubuntu.
- [ ] Record full `python -m pytest -q` results from Python 3.12 on Ubuntu.
- [ ] Record full `python -m pytest -q` results from Python 3.11 on Windows.
- [ ] Record full `python -m pytest -q` results from Python 3.12 on Windows.
- [ ] Record full `python -m pytest -q` results from Python 3.11 on macOS.
- [ ] Record full `python -m pytest -q` results from Python 3.12 on macOS.
- [ ] Record skipped tests and justify every skip.
- [ ] Record deselected tests and why they were outside the release lane.
- [ ] Record coverage summary and compare it against the configured threshold.
- [ ] Add or link contract test report.
- [ ] Add or link golden test report.
- [ ] Add or link property test report.
- [ ] Add or link fuzz test report.
- [ ] Add or link slow/benchmark/visual-quality test report.
- [ ] Add or link example-corpus build/certification report.
- [ ] Add or link Godot addon manual smoke report.
- [ ] Add or link external GLB/USD viewer validation report.
- [ ] Add or link load/performance report.
- [ ] Add or link security scan report.
- [ ] Add or link penetration-test report or approved scoped exception.

### Telemetry And Dashboards

- [ ] Create `docs/telemetry_event_taxonomy.md`.
- [ ] Version every telemetry event and field.
- [ ] Document the north-star metric.
- [ ] Document acquisition, activation, engagement, retention, and revenue funnels.
- [ ] Create live dashboard for build pings or record why telemetry remains disabled for this release.
- [ ] Create launch dashboard for install success.
- [ ] Create launch dashboard for build success.
- [ ] Create launch dashboard for certification failures.
- [ ] Create launch dashboard for support volume and response times.
- [ ] Create data quality checks for event schema drift.
- [ ] Create data quality checks for null rates.
- [ ] Create data quality checks for freshness.
- [ ] Add dashboard URLs to release evidence.

### Runbooks And On-Call

- [ ] Create `docs/ops/README.md`.
- [ ] Create `docs/ops/on-call.md`.
- [ ] Name launch primary on-call owner.
- [ ] Name launch backup on-call owner.
- [ ] Define first response SLA for launch week.
- [ ] Define escalation path for security reports.
- [ ] Define escalation path for broken install reports.
- [ ] Define escalation path for package/yank decisions.
- [ ] Define escalation path for legal/privacy complaints.
- [ ] Define escalation path for Godot addon breakage.

### Risk Register

- [ ] Create `docs/risk_register.md`.
- [ ] Include at least 10 risks.
- [ ] Score every risk by likelihood.
- [ ] Score every risk by impact.
- [ ] Assign every risk a named owner.
- [ ] Assign every risk a target review date.
- [ ] Add mitigation for every risk.
- [ ] Add contingency for every risk.
- [ ] Add trigger conditions for every risk.
- [ ] Cover legal risk.
- [ ] Cover security risk.
- [ ] Cover reputational risk.
- [ ] Cover technical risk.
- [ ] Cover financial risk.
- [ ] Cover key-person risk.
- [ ] Cover platform-dependency risk.
- [ ] Cover provider-dependency risk.

### Launch Plan And Rollback Plan

- [ ] Create `docs/release/launch-plan-v0.2.0rc1.md`.
- [ ] Define dogfood phase.
- [ ] Define closed beta phase.
- [ ] Define soft launch phase.
- [ ] Define general availability phase.
- [ ] Add objective entry criteria for each phase.
- [ ] Add objective exit criteria for each phase.
- [ ] Add rollback triggers for each phase.
- [ ] Add communication plan for each phase.
- [ ] Add owner and backup owner for each phase.
- [ ] Create `docs/release/rollback-plan-v0.2.0rc1.md`.
- [ ] Define who can pull the kill switch.
- [ ] Define backup kill-switch authority.
- [ ] Define decision-to-user-visible-reversal target time.
- [ ] Define PyPI yank or deprecation procedure.
- [ ] Define GitHub Release edit or withdrawal procedure.
- [ ] Define docs banner procedure.
- [ ] Define Discord/community announcement procedure.
- [ ] Define GitHub issue/advisory announcement procedure.
- [ ] Define what is irreversible after launch.

### Legal, Compliance, And Privacy

- [ ] Create `docs/privacy.md`.
- [ ] Create `docs/terms.md` or explicitly record why ToS is not applicable.
- [ ] Create `docs/legal/compliance-review-v0.2.0rc1.md`.
- [ ] Get written review from qualified counsel or record that launch is blocked.
- [ ] Assess GDPR applicability.
- [ ] Assess CCPA/CPRA applicability.
- [ ] Assess COPPA/child-safety applicability.
- [ ] Assess export-control applicability.
- [ ] Assess sanctions-screening applicability.
- [ ] Assess PCI-DSS applicability.
- [ ] Assess HIPAA applicability.
- [ ] Assess SOC 2 relevance and non-goals.
- [ ] List all vendors touching user data.
- [ ] Confirm DPA status for every vendor touching user data.
- [ ] Confirm telemetry ingest ownership and hosting provider.
- [ ] Document data retention for telemetry.
- [ ] Document deletion process for telemetry.
- [ ] Document export process for telemetry if applicable.
- [ ] Document consent capture and opt-out enforcement.
- [ ] Document bug bounty or responsible disclosure path.

### Financial Model And Unit Economics

- [ ] Create `docs/business/unit_economics.md`.
- [ ] Estimate COGS per active user for current OSS/pre-release support.
- [ ] Estimate COGS per build for local-only mode.
- [ ] Estimate COGS per learned-provider build.
- [ ] Estimate COGS per registry transaction for future registry.
- [ ] Estimate COGS per CI-SaaS run for future hosted certification.
- [ ] Create infra cost projections at 1x load.
- [ ] Create infra cost projections at 10x load.
- [ ] Create infra cost projections at 100x load.
- [ ] Add gross margin model.
- [ ] Add sensitivity analysis for provider costs.
- [ ] Add sensitivity analysis for support load.
- [ ] Add pricing experiment plan.
- [ ] Record current willingness-to-pay evidence or mark as missing.
- [ ] Record billing/refund/proration/tax/multi-currency/dunning as not applicable until monetization is live.
- [ ] Add fraud and chargeback plan for future paid registry and CI-SaaS.

### GTM, Positioning, And Competition

- [ ] Review `docs/product_value.md` for current release truthfulness.
- [ ] Review `docs/competitive_landscape.md` for current competitor facts.
- [ ] Re-check competitor pricing and terms before public use.
- [ ] Create `docs/release/launch-narrative-v0.2.0rc1.md`.
- [ ] Write three launch messages.
- [ ] Create press/community/influencer contact list.
- [ ] Name every launch contact.
- [ ] Create first 30-day content calendar.
- [ ] Create community moderation plan.
- [ ] Create crisis communications playbook.
- [ ] Have legal review crisis communications if legal/privacy/security issues are referenced.

### Beta, Dogfood, And Customer Support

- [ ] Create `docs/research/interviews/README.md`.
- [ ] Log 5 Persona A interviews.
- [ ] Log 2 Persona B interviews.
- [ ] Log 1 Persona C agent-builder interview.
- [ ] Create `docs/research/beta-feedback-v0.2.0rc1.md`.
- [ ] Record every dogfood user.
- [ ] Record every closed-beta user.
- [ ] Record every blocker reported by beta users.
- [ ] Classify every feedback item by severity.
- [ ] Classify every feedback item by persona.
- [ ] Record whether every beta user would use Lathe again.
- [ ] Create `docs/support/readiness-checklist.md`.
- [ ] Write answers for top 20 expected user questions.
- [ ] Write support macro for install failure.
- [ ] Write support macro for `lathe doctor` failure.
- [ ] Write support macro for provider unavailable.
- [ ] Write support macro for certification failure.
- [ ] Write support macro for Godot import failure.
- [ ] Write support macro for security/private reporting.

### Known Bugs And Decision Log

- [ ] Convert `plans/10_bugs_errors.md` into a current known-bugs register or create `docs/release/known-bugs-v0.2.0rc1.md`.
- [ ] List every known bug with severity.
- [ ] List every known bug with owner.
- [ ] List every known bug with target fix date or accepted exception.
- [ ] Link every fixed bug to a regression test.
- [ ] Link every unresolved bug to a release exception or block release.
- [ ] Review `docs/adr/README.md` for current ADR status.
- [ ] Move ADRs 0004, 0005, and 0006 from Proposed to Accepted only if implementation and evidence exist.
- [ ] Create `docs/release/decision-log-v0.2.0rc1.md`.
- [ ] List every explicit non-goal for this release.
- [ ] List every feature intentionally deferred.
- [ ] List every release exception and rationale.
- [ ] List every public claim that must not be made.

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

