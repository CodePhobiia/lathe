# Plan Completeness — Honest Backlog

As of 2026-04-24, 74 commits on `main` + tag `v0.1.0`. This document is the **honest state** of what's shipped vs what's open across the 10 original plans from the repository review.

"Touched" ≠ "done." Use this doc when planning future waves; don't trust the session-scale `WAVE{N}_BACKLOG.md` files alone.

## Per-plan completeness

| Plan | Status | Score |
|---|---|---|
| 01 Code Quality | Substantially done | ~95% |
| 02 Documentation | Substantially done | ~95% |
| 03 Architecture | Mostly done | ~85% |
| 04 Test Coverage | Below target | ~80% |
| 05 Developer Experience | **Partial** | ~55% |
| 06 Maintenance | Mechanisms yes, operations no | ~75% |
| 07 Security | **Significant gaps** | ~50% |
| 08 Product Quality | Substantially done (with scope-downs) | ~90% |
| 09 Product Value & Vision | Artifacts yes, execution no | ~70% |
| 10 Bugs & Issues | Done | ~100% |

## Plan 01 — Code Quality (~95%)

**Done.** 8 god-modules decomposed to ≤500 LOC (`parser/`, `shape/`, `providers/`, `core/` including per-stage split of `executor.py`, `checker/`, `blueprints/*`, `cli/`, `blender/`, + `capabilities.py` slimmed to 506, `resolver.py` 540 ADR-accepted). Exception hierarchy at `lathe/errors.py` (15 classes). 27 `except Exception` narrowed to zero. 17 production `assert` converted to explicit raises. Ruff `BLE001` + `S101` green. `[tool.ruff]` + `[tool.mypy]` config landed in `pyproject.toml`.

**Open.**
- **CQ-1.** Enable `mypy --strict` in CI on the strict-tier modules (`parser.*`, `normalizer`, `resolver`, `checker`, `planner`, `shape_ir`, `asset_graph`, `conformance`, `backends`, `cli`, `errors`). Config exists; gate not wired.
- **CQ-2.** `pre-commit install` in bootstrap scripts. Config exists at `.pre-commit-config.yaml`; hook not auto-installed.

## Plan 02 — Documentation (~95%)

**Done.** `LICENSE` (Apache-2.0). `CHANGELOG.md` / `CONTRIBUTING.md` / `CODE_OF_CONDUCT.md` (Covenant 2.1 by reference) / `SECURITY.md`. `mkdocs.yml` with nav for 4 tutorials + 13 cookbook recipes + 4 architecture diagrams + 36 API stubs + ADR index. `mkdocs build --strict` green. 30 stdlib `.lth` files with `// doc:` blocks. 473 Google-style docstrings across 103 `lathe/` modules. Ruff D100-D400 green on priority list.

**Open.**
- **DOC-1.** 102 ruff-D residuals on non-priority modules (scaffolds, adapters, transport, several runtimes).
- **DOC-2.** D104 (public package) + D107 (public `__init__`) — 18 sites total, untouched.
- **DOC-3.** API reference docs don't render because target modules have low docstring density — strengthen mkdocstrings output.

## Plan 03 — Architecture (~85%)

**Done.** 6 ADRs backfilled (`docs/adr/0001..0006.md`) + template + README index + pre-existing `0007-resolver-loc-exception.md`. Entry-point plugin registry with 4 groups (`lathe.backends`, `lathe.stacks`, `lathe.providers.shape`, `lathe.validators`). `import-linter` config at `.importlinter` with 4 contracts. Validator composition contract at `lathe/validators/composition.py` with `ValidatorPipeline` routing through the 5 existing validators. Second backend stack `lathe.stack.soft_surface_prop_v1` registered + satchel hero certifies.

**Open.**
- **ARCH-1.** **BL-40** — full Phase 6b deep-stack proof: real Catmull-Clark subdivision topology, non-planar soft-padding xatlas, per-vertex principal-curvature + per-edge C¹/C² continuity validators. Current BL-34 is MVP-only.
- **ARCH-2.** `.importlinter` seeded permissive with `ignore_imports` list. Progressive tightening strategy documented but not applied. Target: zero `ignore_imports` by V0.5.
- **ARCH-3.** `lathe/contracts/` package mentioned in ADR-0005 but never created; Protocol definitions for `StageBackend`/`ShapeProvider`/`BackendStack`/`Validator` live scattered across modules. Consolidate.

## Plan 04 — Test Coverage (~80%)

**Done.** Tests grew 70 → 847+ across ~60 new files. Tranches A/B/C complete. 126 property-based tests. 27 golden snapshots. Contract pin test. Ruff BLE001/S101 green. Coverage gate at 65% (ratchet against regression). Contract hash bit-stable: `51e02c6e…671b085`.

**Open.**
- **BL-39.** Coverage 69.66% → 85%. Target files below 70%: `validation.py` (51%), `executor.py` orchestration branches, provider fallback paths (not exercised by native-only tests), CLI error-paths per subcommand, parser/checker/resolver error-path coverage. Est 2–3 days.
- **TEST-1.** Mutation testing (mutmut) in `pyproject.toml` dev extras but never run. Target: mutation score ≥70% on `geometry_kernel`, `exact_solids`, `checker`, `resolver`, `conformance`.

## Plan 05 — Developer Experience (~55%) — biggest partial

**Done.** `Justfile` (24 recipes) + `Makefile` wrapper. `uv.lock` (hash-pinned). `requirements.txt` + `requirements-dev.txt` exports. Slim `Dockerfile` + `docker/Dockerfile.blender` + `.devcontainer/devcontainer.json` + `docker-compose.yml`. `.env.example` (13 real `LATHE_*` vars). `scripts/clean_workspace.{sh,ps1}`.

**Open.**
- **DX-1.** LSP + VS Code extension — `lathe/lsp/` is a stub; Plan 05 Phase 7 not executed.
- **DX-2.** Shell completion — argcomplete wiring not landed.
- **DX-3.** CLI flags — `--verbose`/`-v`, `--dry-run`, `--seed`, stdlib `logging` config with `LATHE_LOG_LEVEL`. All deferred from Plan 05 Phase 9b.
- **DX-4.** First-run banner / `lathe init` scaffolder.
- **DX-5.** `lathe doctor --fix` interactive remediation; `doctor --strict` CI gate.
- **DX-6.** `scripts/install_blender.{sh,ps1}` + `scripts/install_xatlas.ps1` installers for optional deps.
- **DX-7.** `.lathe_lark_cache` should move under `$LATHE_CACHE_DIR` (currently gitignored but still writes to repo root).
- **DX-8.** Error-message audit across the CLI boundary. Every raise gets a catalog entry beyond what `docs/error_codes.md` already covers.

## Plan 06 — Maintenance (~75%) — mechanisms yes, operations no

**Done.** Git repo exists with 74 commits + tag `v0.1.0`. `.github/workflows/` has ci, lint, coverage, release, docs, pip-audit, lathe-smoke, stale, fuzz, perf, gallery. Governance files: `CODEOWNERS`, `PULL_REQUEST_TEMPLATE`, 4 issue templates, `dependabot.yml`, `labels.yml`, `FUNDING.yml`, `CITATION.cff`.

**Open — operational side is untouched.**
- **OPS-1.** Push to GitHub remote. Repo is local-only; no one can see it.
- **OPS-2.** First PyPI release via trusted publishing. `release.yml` workflow exists; never triggered.
- **OPS-3.** GitHub Pages for docs site. `docs.yml` workflow exists; not deployed.
- **OPS-4.** Issue triage cadence. No issues filed, no triage happening.
- **OPS-5.** Dependabot PR response cadence — nothing to respond to yet.
- **OPS-6.** Branch protection rules. Workflows defined as required checks in plan; not actually enforced because no remote.

## Plan 07 — Security (~50%) — biggest gap

**Done.** `schema/runtime_config.schema.json` + `lathe/runtime_config.py::load_runtime_config` validates via `jsonschema.Draft202012Validator`. `lathe/net.py::safe_urlopen` with SSRF guards (scheme allowlist, private-IP rejection, TLS min 1.2, content-type pre-check, size cap). `lathe/subproc.py::run_sandboxed` with env-allowlist + stderr scan + timeout. Both Blender subprocess sites (`blender_execution.py` + `core/stages/topology.py`) migrated. `capabilities.py:395` SSRF site closed. JSON ingress audit at `docs/security/json_ingress_audit.md`.

**Open — P0 BEFORE going public.**
- **SEC-1.** Path hardening — `lathe/paths.py::safe_resolve(root, user)` not landed. Plan 07 Phase 2 full surface: RFC1918 path-traversal rejection, Windows reserved names, 8.3 short names, trailing dot, ADS `file:stream`, `\\?\` extended-length, reparse points, case-insensitive collisions. Current state: path inputs accepted as-is.
- **SEC-2.** Binary parser hardening — `lathe/mesh_ingest.py::safe_load_mesh` not landed. Plan 07 Phase 6: size caps, format allowlist, magic-byte sniff, PIL size cap, NaN/Inf rejection. Current state: `trimesh.load` called with raw user bytes.
- **SEC-3.** Secret scanning — `.gitleaks.toml` + pre-commit hook not landed. Plan 07 Phase 8.
- **SEC-4.** SBOM generation — `syft` / `cyclonedx` + cosign keyless signing on release. Plan 07 Phase 9. `release.yml` publishes PyPI but not SBOM.
- **SEC-5.** Static-analysis CI — Bandit + Semgrep + CodeQL + Trivy workflows not landed. Plan 07 Phase 10.
- **SEC-6.** Threat model — `docs/security/threat_model.md` not landed. Plan 07 Phase 11 STRIDE table.
- **SEC-7.** Blender sandbox — `docs/security/blender_sandbox.md` is a design doc only; no sandboxing container profile (`docker/blender.Dockerfile` with `--network=none`) landed.
- **SEC-8.** `.lth` prompt-injection handling when user content flows into learned-provider prompts. Flagged in Plan 07 amendment; no mitigation implemented.

## Plan 08 — Product Quality (~90%)

**Done.** All 8 tickets shipped. Publish runner (local_fs / s3 / supabase / git_lfs + ed25519 signing). `lathe fmt` token-level reformatter. Autonomous multi-round repair loop. Second backend stack. Hero gallery + benchmark scoreboard. Rich reports + artifact viewer + CLI error polish. Strict-mode flip mechanism (V0.1.x opt-in, V0.2 flip). Fuzz (200 default / 10k nightly) + perf budgets + playground static concept.

**Open.**
- **BL-40.** Full soft-surface stack (BL-34 is MVP).
- **BL-41.** Pyodide playground wheel + Monaco + in-browser Lathe (BL-38 ships static concept only).
- **V0.2 flip.** Default strict-mode switch + DeprecationWarning removal; scheduled, not executed.

## Plan 09 — Product Value & Vision (~70%) — artifacts yes, execution no

**Done.** Docs: `personas.md`, `icp.md`, `jtbd.md`, `competitive_landscape.md`, `roadmap_public.md`, 3 synthetic walkthroughs, 6 Persona-C agent-channel docs, monetization strategy, 3 design-partner profiles + outreach template, distribution checklist, 5 blog outlines, 30-min keynote outline. Godot addon MVP + demo scaffold. Benchmark harness with real Lathe-fallback data for 5 reference assets (competitor rows stubbed). Opt-in telemetry (CLI + tests + design doc).

**Open — all GTM execution.**
- **GTM-1.** Push repo to GitHub (overlaps with OPS-1).
- **GTM-2.** Publish V0.5 launch blog post + submit to HN / Godot Discord / r/godot. No post published.
- **GTM-3.** Seed Discord. No Discord created.
- **GTM-4.** Real benchmark-vs-competitor numbers — requires Meshy, Hunyuan, Luma, Quixel accounts + Blender-by-hand contractor runs. Harness ready, data not collected.
- **GTM-5.** Godot AssetLib submission — **BL-44**. In-repo addon exists; not on AssetLib.
- **GTM-6.** Design partner outreach — 3 LOIs by Month 4 target. Template ready, outreach not sent.
- **GTM-7.** NeurIPS / ICLR / GDC Experimental submission — keynote outline ready, not submitted.
- **GTM-8.** `telemetry.lathe.dev/ingest` endpoint — CLI emits pings to this URL but the ingest service doesn't exist.

## Plan 10 — Bugs & Issues (~100%)

**Done.** All 15 findings addressed. 3 removed as false-positives verified (C3 already-fixed, Mi5 contradicted, Mi3 cited wrong files). Real fixes landed for C1/C2 bare-excepts, M1 content-type, M2 schema validation, M3 None/"None" conflation, M4 Blender stderr scan, M4b executor subprocess twin, M5 candidate filename race, M6 silent fallback, M7 dep pinning via lockfile, Mi1 resolver comprehensions, Mi2 nested ternary, Mi3 RNG constant. Plus new findings surfaced during Wave 2/3 reviews: capabilities.py:395 SSRF (closed), 27-site `except Exception` sweep + 17-assert cleanup (M8/M9).

**Open.** None tracked.

## Recommended next priorities

### Track A — security (P0 before public push)

Closes Plan 07. Est 5–7 days of focused work.

1. **SEC-1** path hardening.
2. **SEC-2** binary parser hardening.
3. **SEC-3** + **SEC-4** secret scanning + SBOM + signed releases.
4. **SEC-5** Bandit + Semgrep + CodeQL workflows.
5. **SEC-6** threat model authoring.
6. **SEC-7** Blender sandbox container + `--network=none` profile.

### Track B — operations / go-public

Closes Plan 06 OPS + unblocks Plan 09 execution. Est 2–3 days.

1. **OPS-1** push to GitHub + verify branch protection + all 11 workflows green.
2. **OPS-2** first PyPI release via trusted publishing.
3. **OPS-3** GitHub Pages deployment + custom domain optional.
4. **GTM-2/3** seed Discord + publish launch post.

### Track C — coverage + DX polish

Steady ship. Est 3–4 days.

1. **BL-39** push coverage 69.66 → 85%.
2. **DX-3** `--verbose`/`--dry-run`/`--seed` flags.
3. **DX-5** `lathe doctor --fix` + `--strict`.
4. **TEST-1** first mutation-testing run.

### Track D — advanced features (long scope)

1. **BL-40** full soft-surface stack (2 weeks).
2. **BL-41** Pyodide playground (1.5–2 weeks).
3. **DX-1** LSP + VS Code extension (3–4 days).

## Ticket index

| ID | Plan | Effort | Priority |
|---|---|---|---|
| CQ-1 | 01 | S | P2 |
| CQ-2 | 01 | S | P2 |
| DOC-1 | 02 | M | P3 |
| DOC-2 | 02 | S | P3 |
| DOC-3 | 02 | M | P3 |
| ARCH-1 (=BL-40) | 03 | XL | P2 |
| ARCH-2 | 03 | M | P2 |
| ARCH-3 | 03 | S | P2 |
| BL-39 | 04 | M | P1 |
| TEST-1 | 04 | S | P2 |
| DX-1 | 05 | L | P2 |
| DX-2 | 05 | S | P3 |
| DX-3 | 05 | M | P1 |
| DX-4 | 05 | S | P2 |
| DX-5 | 05 | S | P2 |
| DX-6 | 05 | M | P2 |
| DX-7 | 05 | S | P3 |
| DX-8 | 05 | M | P2 |
| OPS-1 | 06 | S | **P0** |
| OPS-2 | 06 | M | P1 |
| OPS-3 | 06 | S | P1 |
| OPS-4 | 06 | — | ongoing |
| OPS-5 | 06 | — | ongoing |
| OPS-6 | 06 | S | P1 |
| SEC-1 | 07 | M | **P0** |
| SEC-2 | 07 | M | **P0** |
| SEC-3 | 07 | S | **P0** |
| SEC-4 | 07 | M | P1 |
| SEC-5 | 07 | M | P1 |
| SEC-6 | 07 | M | P1 |
| SEC-7 | 07 | L | P1 |
| SEC-8 | 07 | M | P1 |
| BL-40 | 08 | XL | P2 |
| BL-41 | 08 | XL | P2 |
| V0.2 flip | 08 | S | P1 |
| GTM-1 | 09 | S | **P0** (=OPS-1) |
| GTM-2 | 09 | S | P1 |
| GTM-3 | 09 | S | P1 |
| GTM-4 | 09 | L | P2 |
| GTM-5 (=BL-44) | 09 | S | P2 |
| GTM-6 | 09 | M | P2 |
| GTM-7 | 09 | M | P3 |
| GTM-8 | 09 | M | P2 |

**Effort key:** S = <1 day, M = 1–3 days, L = 4–7 days, XL = >1 week.
**Priority key:** P0 = before-going-public; P1 = soon; P2 = next wave; P3 = polish/low-urgency.

---

*Updated 2026-04-24. Supersedes per-wave `plans/WAVE{N}_BACKLOG.md` files for long-lived tracking.*
