# Risk Register — Lathe v0.2.0rc1

**Review date:** 2026-05-28  
**Owner (default):** Tal Merri  
**Status:** pre-release — all risks rated against a closed-beta population

---

| ID | Risk | Category | Likelihood | Impact | Owner | Review date | Mitigation | Contingency | Trigger condition |
|---|---|---|---|---|---|---|---|---|---|
| RISK-001 | Missing privacy/legal sign-off | Legal | High | High | Tal Merri — **requires-human: no counsel engaged; legal backup needed before GA** | 2026-05-28 | Telemetry is off by default; no PII collected in default config; SECURITY.md published; privacy notice tracked in readiness-tasks.md Phase 2 | Pull PyPI wheel; add docs banner; engage counsel before re-publish | Legal complaint received, or counsel retained and identifies gap |
| RISK-002 | Supply-chain vulnerability ships | Security | Medium | High | Tal Merri | 2026-05-28 | pip-audit in CI; Dependabot enabled; pinned lockfile (uv.lock); CycloneDX SBOM on release tags; gitleaks in CI | Yank affected wheel; issue GHSA; publish patched release | pip-audit alert, Dependabot critical alert, or GHSA notification from upstream |
| RISK-003 | Unsupported Python/runtime drift | Technical | Medium | Medium | Tal Merri | 2026-05-28 | CI matrix covers supported Python versions; support-matrix.md documents EOL dates; Dependabot tracks runtime deps | Pin known-good version in release notes; add compatibility warning to `lathe doctor` | CI matrix failure on new Python minor, or user report of import error on supported version |
| RISK-004 | Godot addon breaks first user workflow | Platform dependency | High | High | Tal Merri — **requires-human: Godot smoke tests require macOS/Linux human tester** | 2026-05-28 | Smoke test script exists; fsnotify watcher and certified-state indicator shipped (ENG-5/6); known-limitations.md documents manual-only smoke tests | Request AssetLib removal; publish hotfix; pin GitHub issue | GitHub issue tagged `godot-addon`; AssetLib review rejection |
| RISK-005 | Learned-provider fallback misleads users | Reputational | Medium | High | Tal Merri | 2026-05-28 | Trace records attempted-vs-actual provider; fallback is explicit in build output; docs state providers are optional proposal sources; `lathe doctor` reports provider availability | Add warning banner to provider docs; increase fallback visibility in CLI output | User files issue claiming output was presented as learned-provider result when fallback was used |
| RISK-006 | Canonical examples fail outside maintainer machine | Technical | Medium | High | Tal Merri | 2026-05-28 | CI runs full example corpus; examples/refs/ checked into repo; `lathe doctor` smoke test; conservative path requires no external services | Immediately open release-blocker issue; assess yank if majority of examples fail | CI example-corpus job red; user report of example failure on clean install |
| RISK-007 | Support queue overwhelms solo maintainer | Key-person | High | Medium | Tal Merri — **requires-human: no backup maintainer; single-point-of-failure logged** | 2026-05-28 | Pre-prepared FAQ; install/provider/certification troubleshooting articles (tracked in Phase 5); response-time SLAs defined in on-call.md; soft-launch before GA caps initial user count | Triage to known-issues pinned issue; mark non-critical issues for batch response; request community help | Response SLA breach; more than 20 open issues simultaneously |
| RISK-008 | Telemetry trust backlash | Reputational | Low | Medium | Tal Merri | 2026-05-28 | Telemetry disabled by default; docs/telemetry.md published; no opt-in prompt at install; no PII in default config | Immediate public statement; docs update; confirm no data was collected | Public thread criticizing telemetry; GitHub issue with significant traction |
| RISK-009 | Competitor copies surface positioning | Financial | Low | Low | Tal Merri | 2026-05-28 | Apache-2.0 license; competitive landscape doc exists (docs/competitive_landscape.md); product differentiation documented in manifesto | Update positioning; accelerate differentiating features | Competitor announces feature parity or copies language spec |
| RISK-010 | Monetization path has no willingness-to-pay evidence | Financial | High | Medium | Tal Merri | 2026-05-28 | v0.2.0rc1 is pre-revenue; JTBD and ICP docs exist; closed beta is intended to collect evidence | Revisit pricing/packaging assumptions before v0.2.0 final; treat absence of evidence as risk not blocker for rc1 | Zero paid-intent signals after 30 days of closed beta |
| RISK-011 | Release artifacts cannot be reproduced | Technical | Low | High | Tal Merri | 2026-05-28 | uv.lock pins all deps; deterministic build docs; CycloneDX SBOM; Trusted Publishing on PyPI; deterministic_builds.md | Yank artifact; rebuild from pinned lockfile in clean environment; publish reproduction instructions | Hash mismatch between local build and published wheel; SBOM diff detected |
| RISK-012 | Branch protection / required checks not enforced | Security | Medium | High | Tal Merri | 2026-05-28 | Pre-commit hooks; gitleaks in CI; hardened repository quality gates (commit 30f9186); enforce branch protection rules before public launch | Re-enable protection; audit recent merges for policy violations | Force-push to main succeeds; required check bypassed on a merged PR |
| RISK-013 | Platform review rejects Godot AssetLib submission | Platform dependency | Medium | Medium | Tal Merri — **requires-human: Godot AssetLib submission requires human review response** | 2026-05-28 | Review AssetLib submission guidelines before submitting; test addon against latest stable Godot; document manual smoke test results | Address reviewer feedback; resubmit; distribute via GitHub release as fallback | AssetLib rejection notice received |
| RISK-014 | Optional external providers create legal/IP ambiguity | Legal | Medium | High | Tal Merri — **requires-human: no counsel engaged; legal review of provider integrations needed before GA** | 2026-05-28 | Providers are opt-in via `--runtime-config`; no provider API keys ship in default install; provider integrations documented as optional in architecture docs; out-of-scope upstream issues noted in SECURITY.md | Remove affected provider integration pending legal review | Counsel flags IP concern; provider TOS update prohibits current integration pattern |
| RISK-015 | Key-person dependency — sole maintainer | Key-person | High | High | Tal Merri — **requires-human: no backup maintainer or bus-factor mitigation exists** | 2026-05-28 | All code in public GitHub; Apache-2.0 allows forks; CONTRIBUTING.md exists | Community fork; trusted contributor escalation | Maintainer unavailable for 7+ days during critical incident |
| RISK-016 | Docs site unavailable at launch | Technical | Low | Medium | Tal Merri | 2026-05-28 | Docs built from repo; mkdocs-material; static hosting (GitHub Pages or equivalent); README contains minimum quickstart | Direct users to GitHub README; announce via pinned issue | Docs site returns 5xx; DNS failure at launch |
| RISK-017 | CI/CD secrets compromised or rotated incorrectly | Security | Low | High | Tal Merri | 2026-05-28 | Trusted Publishing eliminates long-lived PyPI token; gitleaks scans for accidental secret exposure; secrets stored in GitHub Actions secrets only | Rotate affected credentials; audit recent release artifacts; issue GHSA if release integrity is in question | Gitleaks alert; unauthorized PyPI publish; CI secret access log anomaly |
| RISK-018 | Blender/xatlas adapter unavailable in user environment | Technical | High | Low | Tal Merri | 2026-05-28 | Graceful degradation to deterministic reference paths documented; `lathe doctor` reports adapter availability; known-limitations.md notes adapter requirements | Improve `lathe doctor` output; add FAQ entry | User confusion about degraded output quality when adapter absent |

---

## Categorical summary

| Category | Risk IDs |
|---|---|
| Legal | RISK-001, RISK-014 |
| Security | RISK-002, RISK-012, RISK-017 |
| Reputational | RISK-005, RISK-008 |
| Technical | RISK-003, RISK-006, RISK-011, RISK-016, RISK-018 |
| Financial | RISK-009, RISK-010 |
| Key-person | RISK-007, RISK-015 |
| Platform dependency | RISK-004, RISK-013 |
| Provider dependency | RISK-005, RISK-014 |

All risks with `requires-human` in the Owner column are **single-points-of-failure** for this pre-release.
None of these blocks closed-beta publication, but all must be resolved before general availability.
