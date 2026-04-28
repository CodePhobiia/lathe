# Anti-pattern doc sweep — v0.2.0rc1

**Version:** 0.2.0rc1 (pre-release reference compiler scaffold)
**Captured:** 2026-04-28
**Owner:** Tal Merri (@talmerri)
**Worktree:** `.claude/worktrees/readiness-pass-v020rc1/`
**Branch:** `worktree-readiness-pass-v020rc1`
**Scope:** Phase 17 of the v0.2.0rc1 readiness remediation pass — read-only sweep of `docs/`, `README.md`, `CHANGELOG.md`, `spec/`, and in-repo marketing copy for the ten launch-anti-pattern claim families. Findings recorded as file:line + disposition; no doc text was edited in this pass (the lead aggregates rewrites).

This document is the canonical Phase-17 sweep record. The aggregator doc
(`docs/release/evidence-v0.2.0rc1.md` Phase 17 section) cross-links to it.

Pre-release-only language is used throughout: the project is a release candidate, not a stable / production / GA release.

---

### Anti-pattern: "after launch" used to defer monitoring or rigor

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `docs/release/rollback-plan-v0.2.0rc1.md:292` | `## What is irreversible after launch` | keep-with-caveat | Section names *what becomes irreversible at the moment of launch* — that is rigor (a list of things that cannot be undone), not deferral. Caveat: section is intrinsic to a rollback plan and does not promise post-launch monitoring. |
| `docs/ops/on-call.md:80` | `## Post-launch operating cadence (first 14 days)` | keep-with-caveat | Title introduces a cadence table that names owner, content, and cadence per day for 14 days — concrete, not deferred. Caveat: cadence is gated on the first public-launch milestone (not v0.2.0rc1). |
| `docs/ops/on-call.md:106-112` | `### Post-launch sprint plan (skeleton)` and the hotfix-/stabilization-/forward-progress-lane bullets | keep-with-caveat | Skeleton has 40/40/20 capacity allocation, named owner (Tal Merri), Day 7 + Day 14 review checkpoints. Caveat: 0% reservation for v0.2.0rc1 itself per `raci-v0.2.0rc1.md:72`. |
| `docs/security/threat_model.md:217` | `Next review: 2026-05-28 or T+30 post-launch (whichever later)` | keep-with-caveat | Names a date and a trigger; not deferral. Caveat: the date is concrete (2026-05-28) and the post-launch trigger only widens the window. Same pattern at `docs/security/supply-chain-review-v0.2.0rc1.md:237`, `docs/security/security-review-scope-v0.2.0rc1.md:399`, `docs/security/secret-hygiene-v0.2.0rc1.md:114`, `docs/security/owasp-mapping-v0.2.0rc1.md:404`. |
| `docs/community/early_access.md:3` | `weekly cadence looks like after launch` | keep-with-caveat | Phrase introduces a cadence that is then concretely scoped to the V0.5 public launch (Month 4) per `docs/roadmap_public.md`. Not v0.2.0rc1 launch; not deferral. |
| `docs/business/design_partners.md:74` | `**Month 5 (post-launch)**: design-partner retro` | keep-with-caveat | Specific event tied to a specific month after the V0.5 OSS launch. Concrete. |
| `docs/Specs/Lathe-V1.0-Spec.md:468` | `V1.0 MUST ship first-party hero programs for:` | keep-with-caveat | "ship first" is the verb "ship" + "first-party"; not the anti-pattern phrase "ship first, fix later". Caveat: this is V1.0 spec, not v0.2.0rc1 copy. |
| `readiness-tasks.md:155, 418, 420, 780, 781, 826` | tracking entries for "after launch" / "post-launch" | keep-with-caveat | These are the readiness-pass tracking lines that *exist to find this anti-pattern*; they reference docs already audited above. Read-only; not public copy. |

No `requires-fix-before-launch:` items in this anti-pattern.

---

### Anti-pattern: "probably fine" / "should be fine" / vague legal hand-waving

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `docs/godot_integration.md:196` | `polling (2s) via FileAccess.get_modified_time. Good enough for` | keep-with-caveat | Phrase is qualified by the v0.3 alpha scope of the Godot demo and the immediate next sentence describes when polling will be replaced. Caveat: technical scope, not legal. |
| `docs/blog/04_godot_integration_walkthrough.md:152` | `whether the build output is good enough to replace a` | keep-with-caveat | Qualified — sentence is asking whether the certified build clears the human-eyeball test, with the certification metrics defined elsewhere. Not vague; not a deferral. |
| `docs/blog/01_the_build_passed.md:89` | `not inspect a mesh in Blender to decide if it was "good enough."` | keep-with-caveat | Quoted — the post is critiquing the historical "good enough" eyeball check and replacing it with deterministic certification. Quotation marks make this explicit. |
| `docs/blog/01_the_build_passed.md:148` | `whether the certified build is good enough to ship` | keep-with-caveat | Same context as line 89 — explicitly defining what "good enough" means via certification. |
| `docs/integrations/godot.md:95` | `2s polling loop is good enough for the demo;` | keep-with-caveat | Time-bounded ("for the demo"); not load-bearing for production claims. |

No `requires-fix-before-launch:` items in this anti-pattern. No "probably fine" or vague legal hand-waving language was found in any release-window or public copy. `readiness-tasks.md:827` confirms the sweep was actively conducted.

---

### Anti-pattern: "works on my machine" or equivalent — no matrix evidence

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| (none found) | — | — | No matches in `docs/`, `README.md`, `CHANGELOG.md`, `spec/`, or in-repo marketing copy. `readiness-tasks.md:828` confirms the sweep was actively conducted. The supported test matrix is documented in `docs/release/support-matrix.md` and the CI matrix runs Python 3.11 + 3.12. |

No `requires-fix-before-launch:` items in this anti-pattern.

---

### Anti-pattern: "scales to N", "high throughput", "thousands of users" — scale claims without a load artifact

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `docs/release/decision-log-v0.2.0rc1.md:171-173` | `**Scale / load claims** — "scales to N assets", "thousands of users", "high throughput", etc.` | keep-with-caveat | This *is* the forbidden-claims gate (item 11 of the forbidden-claims list). It explicitly forbids scale claims pre-launch. Anti-pattern policy enforcement, not a violation. |
| `docs/release/launch-narrative-v0.2.0rc1.md:28` | `not benchmarked at scale, not security-audited by a third party` | keep-with-caveat | Phrase is a *negation* — explicitly disclaims scale benchmarking. Properly qualified. |
| `docs/release/decision-log-v0.2.0rc1.md:151` | `has not been deployed at scale by external users` | keep-with-caveat | Negation — explicitly disclaims field deployment scale. |
| `docs/blog/05_certification_as_the_product.md:123, 139, 141, 197` | "fleet of runners with learned-backend access already…", "scale bet, not a feature moat", "build-pass-at-scale" | rewrite (recommended; not blocker) | Blog post is a *forward-looking thesis* essay, not a v0.2.0rc1 capability claim. The "build-pass-at-scale" phrase at line 141 risks being read as a current capability if the post is republished publicly during the launch window. Recommended replacement: re-frame each "at scale" usage with explicit time gating ("when the V1.0 hosted SaaS lands"); flag the post itself with a "thesis essay, not v0.2.0rc1 capability claim" header before public republishing. |
| `docs/business/monetization.md:24` | `Studio support doesn't scale with one maintainer` | keep-with-caveat | Negation — disclaiming the scalability of an option that is *rejected*. Concrete. |
| `docs/business/unit_economics.md:53, 148` | `Scale | Active users | Maintainer h/week …`, `load scales with opt-in rate only` | keep-with-caveat | Both are internal capacity/cost models, not external claims. Caveat: these are scratch-pad sketches per `docs/business/monetization.md:43` and not pricing copy. |
| `docs/architecture/runtime-posture-v0.2.0rc1.md:40` | `RPS, load tests, and "sustained 30-minute test at target peak × 3" do not apply.` | keep-with-caveat | Explicit disclaimer that load testing does not apply to a local CLI release. Properly qualified. |
| `docs/security/security-review-scope-v0.2.0rc1.md:355` | `there race conditions … at scale. v0.2.0rc1 does NOT have a transparency log integration` | keep-with-caveat | Negation — explicitly disclaims a transparency-log capability. |
| `docs/lathe_prd.md:88` | `small teams needing asset throughput without large art pipelines` | keep-with-caveat | Persona description, not a claim about Lathe's throughput. Caveat: the line describes a *user need*, not a Lathe capability. |
| `docs/business/outreach_template.md:66` | `pipeline scale>` | keep-with-caveat | Inside an outreach-template placeholder; the placeholder asks the prospect to fill in *their* scale. |

`requires-fix-before-launch:` — `docs/blog/05_certification_as_the_product.md:141` ("build-pass-at-scale, not") if this blog post is republished as a public v0.2.0rc1 launch artifact. The phrase needs an explicit "future" or "V1.0+" qualifier or removal before public republishing. Tracked under `decision-log-v0.2.0rc1.md` forbidden claim #11.

---

### Anti-pattern: "secure", "hardened", "audited", "production-ready" security claims without threat-model + scan evidence

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `docs/release/decision-log-v0.2.0rc1.md:174-178` | `**Security / hardening claims** — "secure", "hardened", "enterprise-grade security", "audited" — until a documented security scan + threat model + mitigation list is published…` | keep-with-caveat | This is the forbidden-claims gate (item 12). Anti-pattern policy enforcement. |
| `docs/contributing.md:23` | `Public docs and source are statically audited for common leaks.` | keep-with-caveat | "statically audited" refers to gitleaks + Bandit + CI-gate scans (`docs/security/ci_gates.md`); the qualifier "for common leaks" is honest scope. Caveat: not a third-party-audit claim; reads as automated scanning, which is true. |
| `docs/risk_register.md:22` | `gitleaks in CI; hardened repository quality gates (commit 30f9186)` | keep-with-caveat | Phrase "hardened repository quality gates" refers to a specific commit — `git show 30f9186` is the artifact. Specific claim with evidence. |
| `docs/security/owasp-mapping-v0.2.0rc1.md:185` | `**Default state hardened.** Telemetry off by default` | keep-with-caveat | "hardened" is qualified to *default-state* (telemetry-off + LATHE_ALLOW_EXTERNAL_OUT=0); the artifacts are listed inline. Caveat: scoped to defaults, not the package overall. |
| `docs/release/release-gates-v0.2.0rc1.md:226` | `the project's secure subprocess wrapper lives in lathe/subproc.py` | keep-with-caveat | "secure subprocess wrapper" describes a specific module (`lathe/subproc.py`); coverage gates "sandboxing" and "security" are named. Caveat: claim is module-scoped, not product-wide. |
| `docs/telemetry.md:102` | `Network traffic can be audited by any mitmproxy-class tool` | keep-with-caveat | "can be audited" — describes user/operator capability, not a vendor audit. Caveat: passive verb, not a "we are audited" claim. |
| `docs/security/ci_gates.md:96` | `Dismissals are audited — prefer a fix.` | keep-with-caveat | "audited" describes the dismissal-review process, not a vendor audit. Internal-process scope. |
| `docs/security/owasp-mapping-v0.2.0rc1.md:134` | `## A04 — Insecure Design` | keep-with-caveat | OWASP category title (literal). Not a claim. |
| `docs/research/beta-feedback-v0.2.0rc1.md:73` | `requires-human: secure ≥3 LOIs or mark public launch blocked` | keep-with-caveat | Verb "secure" (acquire) — not a security claim. |
| `README.md:3` | `Lathe is a declarative programming language and compiler/runtime for turning 3D asset intent into certified production-ready asset packages.` | keep-with-caveat | Decision-log forbidden claim #1 forbids "production-ready" *as a v0.2.0rc1 self-description*. This line describes the *output category* (asset packages) — not the v0.2.0rc1 release itself. Caveat: the surrounding paragraph at `README.md:5,18` immediately qualifies the package itself as "alpha/pre-release reference compiler scaffold". Borderline; recommended secondary action: tighten phrasing to "certified asset packages aimed at production use" or similar to remove the ambiguity, but the file is still pre-release-truthful when read whole. |
| `docs/index.md:3` | Same wording as README.md:3 — "certified production-ready asset packages" | rewrite (recommended; not blocker) | Same disposition as `README.md:3`. The docs landing page does not have the "alpha/pre-release" qualifier within the next paragraph that README has — the qualifier is on a different page (`docs/release/known-limitations.md`). Recommended replacement: append a status line "v0.2.0rc1 is a pre-release reference compiler scaffold; see [release notes](release/index.md)" immediately after the lede. |
| `docs/architecture/overview.md:3` | `emits a certified bundle of production-ready assets` | rewrite (recommended; not blocker) | Same vocabulary as README.md:3. Architecture overview has no surrounding pre-release qualifier. Recommended replacement: re-word to "certified asset bundles aimed at production use" or add a "v0.2.0rc1 status" callout at the top of the page. |
| `docs/lathe_manifesto.md:7` | `compile it into a production-ready 3D asset package` | keep-with-caveat | Manifesto is explicitly a forward-looking vision document ("Lathe should become…", "What success looks like", "North star"). The phrase "production-ready" describes the eventual product, not v0.2.0rc1. Caveat: the manifesto has no v0.2.0rc1-specific claims to gate. |
| `docs/lathe_prd.md:26, 28, 34, 422` | PRD describes "production-ready 3D assets" | keep-with-caveat | PRD line 28 explicitly qualifies: "The current shipping version (0.2.0rc1) is a pre-release reference compiler scaffold. It is NOT production-ready, NOT stable, and NOT GA." Forward-looking PRD vocabulary is then properly gated. |
| `docs/Specs/Lathe-V1.0-Spec.md:32, 182` | `production-ready hard-surface assets`, `a production-ready authoritative mesh` | keep-with-caveat | V1.0 spec describes V1.0, not v0.2.0rc1. Spec is forward-looking. |
| `docs/release/launch-narrative-v0.2.0rc1.md:20` | `not a production-ready service` | keep-with-caveat | Negation — explicit disclaimer. |
| `docs/release/raci-v0.2.0rc1.md:7` | `Version | v0.2.0rc1 (pre-release; not production-ready)` | keep-with-caveat | Negation — explicit disclaimer. |
| `docs/release/evidence-v0.2.0rc1.md:8, 56` | `Stable / "production-ready" public claims are forbidden`, `Public copy may NOT use "production-ready"…` | keep-with-caveat | Forbidden-claim references / quoted-as-forbidden language. |
| `docs/support/readiness-checklist.md:83` | `### 1. What is Lathe? Is it production-ready?` | keep-with-caveat | FAQ heading; the answer at lines 85-94 explicitly rejects production-ready and labels v0.2.0rc1 as "alpha". |
| `CLAUDE.md:7` | `produces certified production-ready asset packages (usd/glb/gltf/obj)` | keep-with-caveat | CLAUDE.md is internal-agent context. Not public copy. |
| `spec/lathe-v0.1.md:7` | `Lathe is a declarative, end-to-end build language for production-ready 3D assets.` | rewrite (recommended; not blocker) | Spec lede uses unqualified "production-ready" without an inline pre-release qualifier. Recommended replacement: append "(v0.2.0rc1 release status: pre-release reference compiler scaffold)" or similar to the lede; or add a status callout at the top of the spec. |

`requires-fix-before-launch:` —
- `docs/index.md:3`: add inline pre-release status qualifier or page-level status callout (otherwise the docs landing page reads as an unqualified "production-ready" claim).
- `docs/architecture/overview.md:3`: add inline pre-release status qualifier or page-level status callout.
- `spec/lathe-v0.1.md:7`: add inline pre-release status qualifier or top-of-page status callout.
- `README.md:3`: optional tightening (lower priority — README has surrounding pre-release qualifier at lines 5 and 18).

No third-party security audit has been performed; `EXC-PHASE9-PENTEST-001` in `decision-log-v0.2.0rc1.md` formally accepts this gap and bars all "audited" / "hardened" / "secure" claims until closed. The in-tree threat model + OWASP mapping + supply-chain review + scanner gates are the v0.2.0rc1 baseline.

---

### Anti-pattern: "best practices" without naming the specific practice

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `plans/reviews/05_developer_experience_review.md:46` | `**pygls for LSP:** industry standard, fine.` | keep-with-caveat | "industry standard" attached to a named tool (`pygls`); the named-practice requirement is satisfied. Internal review doc, not public copy. |
| `plans/02_documentation.md:10` | (omitted long line) | keep-with-caveat | Internal plan doc, not public copy. (Long match line — recommend confirming next pass; first pass treats internal `plans/` as out of scope for the launch-anti-pattern bar.) |

No "best practices" hits in `docs/`, `README.md`, `CHANGELOG.md`, `spec/`, or release-window copy. `readiness-tasks.md:831` confirms the sweep was actively conducted.

---

### Anti-pattern: "production-ready" / "stable" / "GA" / "1.0" / "battle-tested"

Covered above under the security-claims anti-pattern (because the audit pattern overlaps significantly). Additional findings specific to "stable" / "GA" / "battle-tested":

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `docs/release/decision-log-v0.2.0rc1.md:142-152` | Forbidden claims #1-#5 enumerate "Production-ready", "Stable", "GA", "1.0", "Battle-tested" / "production-tested" / "field-tested" | keep-with-caveat | Forbidden-claims gate. Anti-pattern policy enforcement. |
| `README.md:18` | `Stability: alpha/pre-release reference compiler scaffold.` | keep-with-caveat | Self-classifies as alpha/pre-release. Concrete and pre-release-truthful. |

No "battle-tested" / "field-tested" / "production-tested" matches in `docs/`, `README.md`, `CHANGELOG.md`, or `spec/` outside the forbidden-claims list itself.

---

### Anti-pattern: "users won't do that" assumptions / "we trust users to" without a guard

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `docs/adr/0003-provider-mux-design.md:108` | `In V0.2, the same users will…` | keep-with-caveat | Phrase is a forward design note about future ADR behavior, not a "users won't do X" assumption. Specific user-behavior expectation paired with a feature design (`strict=false` capture). |

No "users won't do that" / "we trust users to" assumption phrases found. `readiness-tasks.md:833` confirms the sweep was actively conducted. Ingress hardening covered in `docs/security/json_ingress_audit.md` and `docs/security/threat_model.md` STRIDE table.

---

### Anti-pattern: "hotfix" mentioned as mitigation without rollback owner + date

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `docs/risk_register.md:14` (RISK-004) | `Request AssetLib removal; publish hotfix; pin GitHub issue` | keep-with-caveat | Owner: Tal Merri; Review date: 2026-05-28. Both columns populated; trigger condition specified. |
| `docs/ops/on-call.md:23` | `Next hotfix window` (P1 SLA cell) | keep-with-caveat | Surrounding table names owner ("On triage and on close" — `on-call.md` table, with on-call rotation = Tal Merri solo). Date implied by the 24h / 3-business-day SLAs in the same row. |
| `docs/ops/on-call.md:90` | `hotfix delivery` (Day 7 retrospective bullet) | keep-with-caveat | Owner column on same row: "Tal Merri / **requires-human:** content review". Date: Day 7. |
| `docs/ops/on-call.md:96-101, 110, 112` | Hotfix capacity reservation block; hotfix lane bullet | keep-with-caveat | Section "Hotfix capacity reservation" is the rollback owner + date artifact: 40% reservation, days 0–14, calendar-blocked, enforced by maintainer. |
| `docs/release/raci-v0.2.0rc1.md:70-72` | `### 7. Hotfix Capacity Reservation` | keep-with-caveat | Cross-references the on-call.md hotfix block; v0.2.0rc1 reservation explicitly 0% (no public launch window active). |

No `requires-fix-before-launch:` items. Every hotfix mention has both a named owner (Tal Merri) and a window/date.

---

### Anti-pattern: claims of PyPI / Godot AssetLib / Discord / signed partners / benchmark publication without evidence

| File:line | Current text (≤120 chars) | Disposition | Recommended action |
|-----------|----------------------------|-------------|--------------------|
| `docs/release/decision-log-v0.2.0rc1.md:153-170` | Forbidden claims #6 (PyPI), #7 (AssetLib), #8 (signed partners), #9 (Discord), #10 (benchmark numbers without raw data) | keep-with-caveat | Forbidden-claims gate enumerates each of these. Anti-pattern policy enforcement. |
| `docs/release/launch-narrative-v0.2.0rc1.md:28` | `not GA, not benchmarked at scale, not on Godot AssetLib, and does not yet have signed design partners` | keep-with-caveat | Negations — explicit disclaimers. |
| `docs/research/beta-feedback-v0.2.0rc1.md:8, 73` | "claim about beta users…" guarding language; `requires-human: secure ≥3 LOIs or mark public launch blocked` | keep-with-caveat | Operates as the gate for the LOI / partner claim — recorded as a launch-blocker. |
| `docs/walkthroughs/01_godot_indie_crate_family.md:3`, `02_studio_door_contract.md:3`, `03_agent_authored_panel.md:3` | `**Synthetic scenario — not a real user story.** This is a narrative walkthrough; replace with a real case study when a design partner signs.` | keep-with-caveat | Each walkthrough opens with explicit synthetic disclaimer. Properly qualified. |
| `docs/walkthroughs/README.md:7-17` | Synthetic-walkthrough policy block | keep-with-caveat | Defines when synthetic walkthroughs are replaced (LOI signed + logo + quotation rights). Concrete trigger. |
| `docs/business/design_partners.md` (file-wide) | `## What "design partner" means here` and the LOI definition | keep-with-caveat | Defines design-partner relationship structure; uses "signed design partners" language but never claims one exists. |
| `docs/community/early_access.md:54` | `45-minute 1:1 with each signed design partner (see docs/business/design_partners.md for the three prospects and target-of-three signed)` | keep-with-caveat | "target-of-three" is a target, not a claim. Surrounding context describes the recruitment pipeline. |
| `docs/business/monetization.md:54` | `from the signed design partners, see docs/business/design_partners.md` | rewrite (recommended; minor) | Phrase "from the signed design partners" reads as if partners are already signed. Recommended replacement: "from the design partners signed by V0.8 launch (target three; see…)". Not a v0.2.0rc1 launch claim — V0.8 scope — but tightening before public republishing reduces ambiguity. |
| `readiness-tasks.md:30, 110, 131, 149, 150, 153, 155, 741, 745, 796, 797` | tracking entries for PyPI / AssetLib / Discord / partner / benchmark gates | keep-with-caveat | Tracking lines, not public copy. Each forbidden claim has a tracking entry confirming it is gated. |

`requires-fix-before-launch:` — `docs/business/monetization.md:54` if `business/monetization.md` is published before V0.8 launch (low priority — monetization page is internal-flavored and not on the v0.2.0rc1 launch path).

No claim of "Available on PyPI", "Listed on Godot AssetLib", "Discord community is open", or "≥N signed design partners" was found in any release-window or public-copy doc.

---

### Risk-register completeness check

- File: `docs/risk_register.md` (46 lines).
- Risks counted: **18** (RISK-001 through RISK-018) — exceeds the ≥10 floor.
- Categories represented (from the categorical-summary table at lines 32-43):
  - Legal — RISK-001, RISK-014 ✓
  - Security — RISK-002, RISK-012, RISK-017 ✓
  - Reputational — RISK-005, RISK-008 ✓
  - Technical — RISK-003, RISK-006, RISK-011, RISK-016, RISK-018 ✓
  - Financial — RISK-009, RISK-010 ✓
  - Key-person — RISK-007, RISK-015 ✓
  - Platform dependency — RISK-004, RISK-013 ✓
  - Provider dependency — RISK-005, RISK-014 ✓ (re-used; both rows have provider-dependency exposure)
- Every required category (legal, security, reputational, technical, financial, key-person, platform-dependency, provider-dependency) is covered.
- All risks include Owner, Review date (2026-05-28), Mitigation, Contingency, Trigger condition columns.
- `requires-human` annotations on RISK-001, RISK-004, RISK-007, RISK-013, RISK-014, RISK-015 are documented as single-points-of-failure at line 45.

**Risk register completeness: yes.**

---

### Roadmap "we chose not to build X" entries

- File: `docs/release/decision-log-v0.2.0rc1.md`, "Non-goals for v0.2.0rc1" section (lines 25-67).
- Non-goal entries counted: **14** explicit non-goals — exceeds the ≥9 floor:
  1. GA / stable / 1.0
  2. Hosted asset registry
  3. Paid CI / certification SaaS
  4. Godot AssetLib submission
  5. Full multi-round autonomous repair loop
  6. Pyodide / browser playground
  7. Soft-surface backend stack (`soft_surface_prop_v1`)
  8. Full mypy strict across the codebase
  9. Python 3.13 / 3.14 support
  10. Hosted telemetry collection / live dashboards
  11. Discord launch
  12. Signed design partners
  13. Public benchmark with raw data
  14. Second-language support, IDE plugins beyond what already ships, marketing site
- File: `docs/roadmap_public.md` exists (verified).
- **Cross-reference status:** `docs/roadmap_public.md` does NOT cross-reference the decision-log non-goals as of 2026-04-28. A grep for `decision-log` / `Non-goal` / `non-goal` in `docs/roadmap_public.md` returns zero matches.

**Decision-log non-goals completeness: yes** (14 explicit non-goals).
**Roadmap public cross-reference completeness: no** — `requires-fix-before-launch:` add a single section to `docs/roadmap_public.md` cross-referencing `docs/release/decision-log-v0.2.0rc1.md` "Non-goals for v0.2.0rc1" (the decision-log already references roadmap_public.md from inside its non-goals; the back-link is missing).

---

### Scale + security claim audit

**Scale claims (per the sweep above):**

| Claim file:line | Required artifact | Artifact present? |
|------------------|-------------------|--------------------|
| `docs/release/decision-log-v0.2.0rc1.md:171-173` (forbidden-claims gate) | `docs/perf_budgets.md`, `tests/test_benchmarks.py` | yes — `docs/perf_budgets.md` exists; `tests/test_benchmarks.py` exists in repo. |
| `docs/release/launch-narrative-v0.2.0rc1.md:28` ("not benchmarked at scale") | n/a (negation) | n/a |
| `docs/blog/05_certification_as_the_product.md:123, 139, 141, 197` | A load artifact, OR explicit time-gating to V1.0 | partial — `docs/perf_budgets.md` covers per-asset budgets but not "fleet of runners" capacity claims. **`requires-fix-before-launch:`** if blog post is republished publicly during the v0.2.0rc1 launch window. |
| `docs/business/unit_economics.md:53, 148` | Internal capacity model, scoped to opt-in users | yes — same file is the artifact. |
| `docs/architecture/runtime-posture-v0.2.0rc1.md:40` ("RPS, load tests do not apply") | n/a (negation, scoped to local CLI release) | n/a |
| `docs/lathe_prd.md:88` ("small teams needing asset throughput") | n/a (persona description, not a Lathe capability claim) | n/a |

**Security claims (per the sweep above):**

| Claim file:line | Required artifact | Artifact present? |
|------------------|-------------------|--------------------|
| `docs/release/decision-log-v0.2.0rc1.md:174-178` (forbidden-claims gate, item 12) | `docs/security/threat_model.md`, `docs/release/evidence-bundle-v0.2.0rc1/sbom.json`, `docs/release/release-gates-v0.2.0rc1.md` § 3 | yes — all three artifacts exist. |
| `docs/contributing.md:23` ("statically audited for common leaks") | `docs/security/ci_gates.md` (gitleaks + Bandit) | yes. |
| `docs/risk_register.md:22` ("hardened repository quality gates (commit 30f9186)") | `git show 30f9186` artifact | yes — commit referenced explicitly. |
| `docs/security/owasp-mapping-v0.2.0rc1.md:185` ("Default state hardened") | `docs/release/telemetry-verification-v0.2.0rc1.md`, `.env.example:43-44` | yes — both artifacts cited inline. |
| `docs/release/release-gates-v0.2.0rc1.md:226` ("secure subprocess wrapper") | `lathe/subproc.py` source + sandbox/security coverage gates | yes — module exists. |
| `docs/telemetry.md:102` ("can be audited by any mitmproxy-class tool") | n/a (capability statement, not vendor audit) | n/a |
| `docs/security/ci_gates.md:96` ("Dismissals are audited") | n/a (internal process scope) | n/a |

**Claims lacking the required artifact link:**

- `docs/blog/05_certification_as_the_product.md:141` ("build-pass-at-scale") — no load artifact yet exists; the only path to publication is to add a "future / V1.0+" qualifier or remove the phrase before public republishing.
- `docs/index.md:3`, `docs/architecture/overview.md:3`, `spec/lathe-v0.1.md:7` ("production-ready" without inline pre-release qualifier) — production readiness has no third-party-audit artifact (`EXC-PHASE9-PENTEST-001`); the missing artifact is "page-level pre-release status callout" rather than a security artifact.

`requires-fix-before-launch:` — five items total:
1. `docs/index.md:3` — add page-level pre-release status qualifier.
2. `docs/architecture/overview.md:3` — add page-level pre-release status qualifier.
3. `spec/lathe-v0.1.md:7` — add inline / top-of-page pre-release status qualifier.
4. `docs/blog/05_certification_as_the_product.md:141` (and lines 123, 139, 197) — add a "thesis essay, not v0.2.0rc1 capability claim" header, or explicitly time-gate "at scale" usages, before any public republishing during the launch window.
5. `docs/roadmap_public.md` — add cross-reference to `docs/release/decision-log-v0.2.0rc1.md` "Non-goals for v0.2.0rc1" (currently missing).

All five are documentation-only fixes; none change product behavior or security posture. Lead aggregates the rewrites — this sweep is read-only.
