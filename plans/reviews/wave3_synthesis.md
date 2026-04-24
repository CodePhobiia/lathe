# Wave 3 — Post-Wave Review Synthesis

Three-reviewer consolidation against the 11 Wave 3 commits (`839e9f6` → `9b1d1c8`).

## Overall verdict: **GREEN — accept Wave 3.**

Wave 3's targets were the P0 hygiene sweep (BL-1/2/3), the P1 LOC decomposition of 4 remaining god-modules (BL-4..BL-7), the P2 security completeness (BL-9/10/11/12), and the P3 cleanups (BL-13/14/15/16). All 16 tickets closed or justifiably deferred. Bit-for-bit reproducibility preserved end-to-end — all 9 hero `.glb` SHA256 hashes match pre-Wave-3 baseline.

## Reviewer verdicts

| Reviewer | Verdict | Key signal |
|---|---|---|
| tests-contract | **Safe to continue** | All 9 heroes bit-identical `.glb` SHA256 to Wave 2; cache 104× speedup; contract ID surface unchanged |
| code-hygiene | **PASS with one flag** | BL-1/2/3 grep-clean; BL-4..BL-7 all ≤500; `blender_execution.py` 567 is a +9 drift vs BL-10 plan |
| plan-audit | **ACCEPT** | All 16 tickets closed or deferred; no cross-cluster drift; torch 2.11 pin verified genuine |

## What landed

| Ticket | Commit | What |
|---|---|---|
| BL-3 | `839e9f6` | Stale Stage 2.V TODOs removed (3 files, -14/+12) |
| BL-1+BL-2 | `23f8620` | Bare-except narrow (23 sites → 0) + production assert conversion (16 sites → 0); 18 files, +153/-40 |
| BL-4 | `11a974e` | `checker.py` 856 → 7-file package (max 397) |
| BL-5 | `49b8eb3` | `blueprints/__init__.py` 717 → 6 files (max 245); courier_drone score identical |
| BL-6 | `ff3be49` | `cli.py` 626 → 15-file per-command package (max 261); console entry still resolves |
| BL-7+BL-12 | `0121bbd` | `capabilities.py` 623 → 490; SSRF unified through `lathe/net.py::safe_urlopen` |
| BL-11+BL-10 | `4c37d49` | `lathe/subproc.py::run_sandboxed` (250 LOC) + env-allowlist migration at both Blender sites |
| BL-9 | `17bb3aa` | 26-site `json.loads` audit + `docs/security/json_ingress_audit.md` |
| BL-13 | `6e5a144` | 9 dead symbols deleted; `candidates.py` removed entirely (-457 LOC net) |
| BL-15 | `daf75fc` | `trace_manifest` indent normalized; byte-identical JSON output verified |
| BL-16 | `9b1d1c8` | `torch>=2.11.0` pin verified genuine; Wave 1 TODO comment removed |

**BL-14** rolled into BL-1 (the `_resolve_ref_path` bare except was part of the 23-site sweep).

## Contract + determinism (most important verdict)

Reviewer-tests-contract's 9-hero build matrix shows **every `.glb` SHA256 bit-identical** to the Wave 2 review:

| Hero | Score | Threshold | SHA match |
|---|---|---|---|
| courier_drone | 0.879435 | 0.86 | ✓ |
| brassbound_chest | 0.888423 | 0.84 | ✓ |
| industrial_crate | 0.884758 | 0.84 | ✓ |
| mechanical_door | 0.876905 | 0.84 | ✓ |
| console_terminal | 0.855031 | 0.85 | ✓ (on-margin, preexisting) |
| sci_fi_wall_panel | 0.862025 | 0.84 | ✓ |
| service_cabinet | 0.820871 | 0.82 | ✓ (on-margin, preexisting) |
| control_pedestal | 0.842405 | 0.83 | ✓ |
| supply_container | 0.871784 | 0.84 | ✓ |

Cache: cold 179.485s → warm 1.721s (~104×). Score + SHA identical across cache boundary.

Contract ID `lathe.shape.intent_mesh_handoff_v1`: 75 → 79 occurrences, every addition in review `.md` files (zero code-side additions). Load-bearing code references unchanged across `lathe/backends.py` (3), `lathe/executor.py` (1), `lathe/shape/backend.py` (2), `lathe/shape/__init__.py` (1), `lathe/shape/geometry/conditioning.py` (1), `lathe/core/stages/shape.py` (1), `spec/lathe-v0.1.md` (2).

## Flags for Wave 4

Three net-new tickets from the reviewers:

- **BL-17 — `lathe/blender_execution.py` 567 LOC.** Pre-Wave-3 was 578 (grew during Wave 2 security hardening). BL-10 migration to `run_sandboxed` shrunk it to 567, but still 67 over the 500 cap. Decompose further in Wave 4.
- **BL-18 — `lathe/resolver.py` 540 LOC decision.** BL-8 was deferred under the "split only if multi-concern" clause. Reviewer-plan-audit wants an explicit audit + decision: split or accept as exception with documented rationale.
- **BL-19 — schemas for trust-boundary JSON sites.** Per `docs/security/json_ingress_audit.md`, the trust-boundary sites carry TODO(security) markers pointing to Wave 4. Write the schemas, route each site through `lathe/validation.py::validate_json`.

Plus from the earlier Wave 2 synthesis (still open):

- **Plan 04 test backfill** — Tranches A-C + property tests + golden snapshots + contract tests + error-path coverage + mutation testing. This is a parallel Wave 3/4 track owned by a separate plan.
- **Plan 02 docs content** — tutorials, cookbook, stdlib doc blocks, inline docstring sweep. Parallel track.
- **Plan 08 product quality** — `publish` runner, `lathe fmt`, multi-round autonomous repair, second backend stack, gallery, playground. Wave 4 anchor.

## Recap of waves 0-3

| Wave | Commits | Duration | Outcome |
|---|---|---|---|
| 0 | 4 | 1 session | Foundation (git init, LICENSE, governance stubs) |
| 1 | 6 | 1 session | Tooling, CI, DX, test framework, docs scaffold, vision docs |
| 2 | 9 | 2 sessions | Constants + 4 decompositions + exception hierarchy + Plan 10 bug fixes + Plan 07 security + post-wave review |
| 3 | 11 | 1 session | P0/P1/P2/P3 sweeps + 4 more decompositions + SSRF unified + subproc wrapper + dead code removed + post-wave review |
| **Total** | **30 commits** | | — |

## Recommendation

1. **Accept Wave 3.** Tests + contract verify identically. Plan bullets closed cleanly. Escapes documented.
2. **Seed Wave 4 backlog** with BL-17/18/19 plus the carry-over Plan 02 / Plan 04 / Plan 08 tracks. This lives in `plans/WAVE4_BACKLOG.md`.
3. **Wave 4** should prioritize: (i) the 3 carry-over tickets, (ii) Plan 04 test backfill to 85% coverage so the ruff BLE001 / S101 gates can go live, (iii) Plan 02 tutorial + cookbook content so the public docs site is fillable, (iv) Plan 08 `publish` runner + `lathe fmt` to close README-flagged scaffolds.

Pipeline is on very solid footing. The refactor surface is now largely quiescent — Wave 4 can focus on *building* rather than *reshaping*.
