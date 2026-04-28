# Decision log — v0.2.0rc1

**Version:** 0.2.0rc1 (pre-release reference compiler scaffold)
**Last reviewed:** 2026-04-28
**Owner:** Tal Merri (@talmerri)
**Reviewer:** requires-human (no second reviewer named yet)

This document records the explicit, time-boxed decisions made for the
v0.2.0rc1 release window: what is intentionally out of scope, what is
deferred and tracked, what release exceptions have been formally accepted,
and which public claims must NOT be made on or after release-candidate
publication.

It pairs with:

- [`docs/release/evidence-v0.2.0rc1.md`](evidence-v0.2.0rc1.md) — the
  release evidence index.
- [`docs/architecture/technical-design-v0.2.0rc1.md`](../architecture/technical-design-v0.2.0rc1.md) —
  release-window technical design, failure modes, single points of failure.
- [`docs/release/known-limitations.md`](known-limitations.md) — the
  ongoing known-limitations list (not release-version-specific).
- [`docs/release/support-matrix.md`](support-matrix.md) — what maintainers
  commit to testing.

## Non-goals for v0.2.0rc1

These are explicitly out of scope for this release. They are NOT bugs,
NOT release blockers, and NOT items the release-evidence packet must
demonstrate. They are listed here so that reviewers, contributors, and
external observers cannot mistake their absence for an oversight.

- **GA / stable / 1.0.** This release is a release candidate for `0.2.0`,
  not a stable or GA release. The full launch freeze in
  `docs/release/evidence-v0.2.0rc1.md` applies until every Phase 0–18 task
  in `readiness-tasks.md` is green or has a recorded exception.
- **Hosted asset registry.** No Lathe-operated registry, no account system,
  no auth surface. Tracked for V0.8 in `docs/roadmap_public.md`.
- **Paid CI / certification SaaS.** Tracked for V1.0 in
  `docs/roadmap_public.md`.
- **Godot AssetLib submission.** The Godot integration code (V0.3 alpha
  scope) ships in this release. Submission to and listing on AssetLib does
  NOT. Tracked as `plan_completeness.md` GTM-5 / BL-44.
- **Full multi-round autonomous repair loop.** Single-pass repair is in
  scope; multi-round bounded iterative repair driven by certification
  feedback is NOT. Explicitly listed as a scaffold in `CLAUDE.md`.
- **Pyodide / browser playground.** Browser-side compile, live playground,
  and shareable in-browser sessions are out of scope. Tracked as research
  in `docs/next_version_roadmap.md`.
- **Soft-surface backend stack (`soft_surface_prop_v1`).** The only
  first-party stack in v0.2.0rc1 is `lathe.stack.hard_surface_game_asset_v1`.
  Soft-surface UV+curvature parity is tracked for V1.0.
- **Full mypy strict across the codebase.** mypy runs in CI; promoting
  the entire codebase to strict mode is out of scope.
- **Python 3.13 / 3.14 support.** `requires-python = ">=3.11"` and the
  support matrix lists 3.11 and 3.12 only. 3.13+ are unsupported.
- **Hosted telemetry collection / live dashboards.** Telemetry remains
  opt-in and disabled by default. Live dashboards are `requires-human`
  per the evidence packet.
- **Discord launch.** No Discord server is launched in v0.2.0rc1. A
  moderation owner has not been named; pre-release does not require it.
- **Signed design partners.** Tracked for V0.5 in `docs/roadmap_public.md`.
  V0.2.0rc1 does not require signed partners; V0.3 requires LOIs in flight.
- **Public benchmark with raw data.** Internal benchmarks (`tests/test_benchmarks.py`,
  `lathe bench`) run in CI. Public publication of raw benchmark data and
  comparison numbers is V0.5.
- **Second-language support, IDE plugins beyond what already ships, marketing
  site, etc.** Out of scope.

## Intentionally deferred features

These are features the team intends to ship eventually, but not in v0.2.0rc1.
Each is tracked in the public roadmap. Linked anchors below point to
`docs/roadmap_public.md` and `docs/next_version_roadmap.md` where appropriate.

| Deferred feature | Tracked in | Target window |
|---|---|---|
| Godot AssetLib listing | `docs/plan_completeness.md` (GTM-5 / BL-44), `docs/roadmap_public.md` (V0.3) | V0.3 |
| Public 5-asset benchmark with raw data | `docs/roadmap_public.md` (V0.5), `docs/benchmarks/` | V0.5 |
| OSS public launch (PyPI listing, Godot AssetLib listing, Discord open) | `docs/roadmap_public.md` (V0.5) | V0.5 |
| Signed design partners (≥3) | `docs/roadmap_public.md` (V0.5) | V0.5 |
| V1.2 surface lane public (governed surface authoring, Codex ImageGen backend) | `docs/roadmap_public.md` (V0.8), `docs/v08_language_reference.md` | V0.8 |
| Paid hosted registry beta | `docs/roadmap_public.md` (V0.8) | V0.8 |
| Standalone first-party generation parity | `docs/roadmap_public.md` (V1.0), PRD M5 | V1.0 |
| CI certification SaaS GA | `docs/roadmap_public.md` (V1.0) | V1.0 |
| Soft-surface backend stack (`soft_surface_prop_v1`) | `docs/roadmap_public.md` (V1.0), `docs/second_backend_stack.md` | V1.0 |
| Multi-round autonomous repair loop | `CLAUDE.md` ("intentionally still scaffolds"), PRD M4 | V0.8+ |
| Pyodide / browser playground | `docs/next_version_roadmap.md` (research lane) | unscheduled |
| Canonical `lathe fmt` formatter | `CLAUDE.md` ("intentionally still scaffolds") | unscheduled |
| Semantic reference system (`@lathe[...]`) | `docs/next_version_roadmap.md` E1 | post-V0.3 |
| Full mypy strict across codebase | `docs/next_version_roadmap.md` E13 (DX & Tooling Polish) | unscheduled |

If a roadmap document is renamed or split during the readiness pass, this
table must be re-checked. Anchors above are file-level; in-page anchors
within `docs/roadmap_public.md` are not pinned by this log because that
document is itself under review (`requires-human: confirm roadmap anchors
remain stable post-pass`).

## Release exceptions accepted in this pass

This is a structured registry of exceptions formally accepted during the
v0.2.0rc1 readiness remediation pass. An exception is appropriate when a
checklist item is not green, the team has decided not to block the release
candidate on it, and a workaround + removal target are recorded.

Populated by the lead as Phase 6 / 9 land their findings.

| id | what | why accepted | owner | date | impact | workaround | removal target |
|---|---|---|---|---|---|---|---|
| `EXC-PHASE3-SIGN-001` | Wheel/sdist/tag signing not performed for v0.2.0rc1 (no release-artifact GPG/sigstore signature, no signed git tag). | No production signing key + key-management posture is in place. Signing without a documented key-rotation, revocation, and attestation policy would create stronger confidentiality claims than we can defend, and signing keys committed/uploaded ad-hoc would be a worse problem than skipping signatures. Affected surface: release artifacts (wheel, sdist, git tag). | Tal Merri | 2026-04-28 | Third parties cannot cryptographically verify artifact authenticity beyond GitHub Release SHA + (eventual) PyPI provenance. Without signatures, downstream users must trust transport-level integrity (HTTPS to GitHub/PyPI) only. | Rely on PyPI Trusted Publishing once configured (see `EXC-PHASE3-PYPI-TP-002`) + GitHub Release SHA256SUMS for byte-level integrity. Document that verification is by SHA only in the release notes. | Before any v0.2.0 final release. `requires-human`: legal/security counsel review for safe-harbor implications (low risk for a pre-release scaffold; non-zero for a tagged stable release). |
| `EXC-PHASE3-PYPI-TP-002` | PyPI Trusted Publishing not configured for v0.2.0rc1. | The project has not been pushed to a public-PyPI-aware GitHub remote with the required workflow + identity binding. PyPI Trusted Publishing requires an OIDC-enabled `release.yml` GitHub Actions job paired with a PyPI-side trust policy bound to `talmerri/lathe`'s workflow + environment. Neither side is set up. | Tal Merri | 2026-04-28 | Publication path to PyPI is `requires-human` until configured. v0.2.0rc1 cannot be published to PyPI under the recommended (OIDC, no long-lived API tokens) posture. | Do NOT publish to PyPI for v0.2.0rc1. The "Available on PyPI" claim is already on the forbidden-claims list above (item 6). This exception is the effective gate for `EXC-PHASE3-SIGN-001`'s sigstore/PyPI-provenance workaround. | Before first public PyPI release. `requires-human`: PyPI account holder (Tal Merri) configures Trusted Publishing identity + completes a dry-run workflow. |
| `EXC-PHASE9-PENTEST-001` | No third-party security pen-test / external security review for v0.2.0rc1. | v0.2.0rc1 is a pre-release reference compiler scaffold. The project is run by a single solo maintainer; engaging a paid third-party security review at this pre-release stage is disproportionate to the operational footprint (local CLI, no auth surface, no hosted service, telemetry disabled by default). The in-tree controls — STRIDE threat model (`docs/security/threat_model.md`), OWASP Top 10 mapping (`docs/security/owasp-mapping-v0.2.0rc1.md`), supply-chain review (`docs/security/supply-chain-review-v0.2.0rc1.md`), CI scanner gates (Bandit, gitleaks, pip-audit, CodeQL, Semgrep, SBOM), and the Phase 2 telemetry verification (15/15 PASS) — are the v0.2.0rc1 baseline. | Tal Merri | 2026-04-28 | A third-party reviewer might find vulnerabilities the self-assessment missed. Severity expectation: residual risks tracked as `SEC-FUTURE-1..7` in the threat model are well-known; the highest-likelihood unknown finding is in the parser / mesh-ingest fuzz surface or the Blender subprocess sandbox on Windows. Mitigated by the conservative offline default path (no learned providers, no network) which does not exercise the highest-risk surfaces. | Use the in-tree threat model + scanner-based gates as the v0.2.0rc1 baseline. Forbidden-claims item 12 in this decision log already prohibits "secure" / "hardened" / "audited" claims until a documented third-party review is signed and dated. The "Security / hardening claims" gate exists precisely to prevent over-claiming until this exception is closed. | Before any v0.2.0 final release or any GA discussion. `requires-human`: third-party security review engagement (scope: `docs/security/security-review-scope-v0.2.0rc1.md`); any CVSS ≥ 7.0 (P0/P1) finding must be fixed before public launch. |
| `EXC-PHASE6-MYPY-001` | Full `python -m mypy lathe/` is not a blocking gate for v0.2.0rc1. The 2026-04-28 run reports 217 errors in 81 of 219 source files (`disallow_untyped_defs = true`, `strict = false` per `pyproject.toml [tool.mypy]`). | Pre-release scaffold; full strict typing across the codebase is intentionally tracked as a long-term plan in `docs/next_version_roadmap.md` E13. Blocking on full mypy here would force significant out-of-scope work for an RC. The non-goals list above already records "Full mypy strict across the codebase" as out of scope for v0.2.0rc1. The actual error transcript and a wave-1 gradual-typing plan (`lathe/parser/`, `lathe/runtime_config.py`, `lathe/net.py`, `lathe/telemetry.py`, `lathe/publish/` first) are recorded in `docs/release/release-gates-v0.2.0rc1.md` § 1. | Tal Merri | 2026-04-28 | Contributors must accept type-confidence gaps in the listed files. CI does not gate on mypy errors for this RC. New code in the wave-1 packages SHOULD pass `mypy` against the unchanged pyproject config. | The list of files with active type errors is in `evidence-bundle-v0.2.0rc1/mypy.txt`. Reviewers should diff-check `mypy lathe/` output before/after a PR to ensure the count does not go up in scope-relevant files. Phase 18 re-review records the gradual-typing plan and tracks progress. | Before v0.2.0 final, OR before any "type-checked" / "fully typed" public claim is made — whichever comes first. `requires-human` to file the wave-1 tracking issue and reword `tasklist.md:28`. |
| `EXC-PHASE6-PIPCVE-001` | `pip 26.0.1` is flagged by pip-audit as having `CVE-2026-3219`. No Fix Versions field is published in the pip-audit advisory database consulted on 2026-04-28; `pip 26.1` exists but does not carry an advisory-fix marker for this CVE. | pip is build/install tooling local to the developer venv, not a runtime dependency of the published `lathe` package. A clean `pip install lathe==0.2.0rc1` is unaffected. There is no fixed version to upgrade to that demonstrably closes the CVE; opportunistic upgrade to `pip 26.1` is not curative. Holding the venv at `pip 26.0.1` keeps the release-window evidence reproducible. | Tal Merri | 2026-04-28 | Local-developer-only exposure. Users of `pip install lathe==0.2.0rc1` are not affected. The CVE is visible in the SBOM / pip-audit transcript and not hidden. | None required for end users. Developers may upgrade to `pip 26.1` at their own discretion (see `evidence-bundle-v0.2.0rc1/pip-version.txt`). | Re-run pip-audit when the upstream advisory database publishes a Fix Versions field for `CVE-2026-3219`; if a curative version is available, upgrade and remove this exception. Otherwise carry forward to v0.2.0 final and record in the next release's evidence bundle. |

Rules for adding rows:

- `id` follows the pattern `EXC-RC1-NNN` (e.g. `EXC-RC1-001`).
- `why accepted` must cite the underlying constraint (time, scope,
  external dependency, etc.). "We don't have time" alone is insufficient;
  identify which downstream item it would have blocked.
- `owner` must be a named human, not a team or role.
- `date` is the date the exception is accepted (YYYY-MM-DD).
- `impact` describes the worst-case consequence for users if the gap is
  not closed before GA.
- `workaround` is the user-facing or operator-facing instruction that
  mitigates the gap until the exception is closed.
- `removal target` is a future release window or GitHub milestone where
  the exception is expected to be lifted.

Exceptions accepted here MUST also be cross-referenced in
`docs/release/evidence-v0.2.0rc1.md` under the matching phase.

## Public claims that must NOT be made for v0.2.0rc1

The following claims are forbidden in any public copy associated with
v0.2.0rc1: README, CHANGELOG, release notes, blog posts, social posts,
mailing list, Discord (when it launches later), conference talks,
package metadata, marketing site, and any partner-facing communication.

Forbidden claims:

1. **"Production-ready."** v0.2.0rc1 is a pre-release reference compiler
   scaffold. Not production-ready.
2. **"Stable."** Public language surface and stable contract IDs are
   designed for stability, but the package itself is pre-release. Do not
   describe the release as stable.
3. **"GA" / "Generally Available."** The release candidate is not GA.
4. **"1.0" or any 1.x version language.** Current version is `0.2.0rc1`.
   `1.0` is gated on PRD M5 and is `future`.
5. **"Battle-tested" / "production-tested" / "field-tested."** The product
   has not been deployed at scale by external users. There is no field
   evidence to support these claims.
6. **"Available on PyPI"** — until the PyPI Trusted Publishing
   configuration is verified, the artifact is uploaded, and a clean
   `pip install lathe==0.2.0rc1` succeeds from a clean environment on the
   supported matrix.
7. **"Available on Godot AssetLib"** — until the listing is submitted,
   approved, and visible publicly.
8. **"Signed design partners" / "studio adoption" / "studio case study"** —
   until LOIs are signed and the partners have approved their names being
   used publicly.
9. **"Discord community"** — until a Discord server is actually launched
   AND a moderation owner is publicly named AND a code of conduct is
   posted.
10. **Any benchmark numbers without raw data** — "X% faster", "Y% smaller
    files", "Z fewer manual fixes", and similar comparative claims. Until
    the public benchmark with raw data is published (V0.5), maintainers
    must not publish summary numbers in promotional copy. Internal
    benchmarks are acceptable to discuss in technical docs as long as the
    methodology and limitations are visible.
11. **Scale / load claims** — "scales to N assets", "thousands of users",
    "high throughput", etc. — until a load-testing artifact (raw run
    output, environment, methodology, observed limits) is published.
12. **Security / hardening claims** — "secure", "hardened",
    "enterprise-grade security", "audited" — until a documented security
    scan + threat model + mitigation list is published, and any
    third-party audit is signed and dated. SAST/DAST CI passes alone are
    not sufficient evidence for an "audited" claim.
13. **"Enterprise-grade" / "production infrastructure"** — same reason as
    "production-ready"; the operational footprint is local-only and the
    team is one person.
14. **"Reference customer" / quoted endorsements** — until the customer
    has signed off on the quote and its use.

Permitted alternatives (subject to ongoing review):

- "v0.2.0 release candidate"
- "pre-release"
- "early-access reference scaffold"
- "reference compiler scaffold"
- "deterministic offline build path on hero asset families"
- factual statements about what is implemented (e.g. "the conservative
  offline path runs without network access") without normative
  ("production-ready") qualifiers.

This list is intentionally more conservative than typical pre-release
copy. It exists because the audit of 2026-04-28 returned a DO NOT SHIP
verdict, and over-claiming was the dominant failure mode.

A maintainer who finds themselves wanting to make a forbidden claim
should instead file an exception in the table above with the proposed
substantiating evidence. If the evidence does not yet exist, the claim
must wait for the evidence.
