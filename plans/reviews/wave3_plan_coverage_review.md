# Wave 3 — Plan Coverage Review

Reviewer: reviewer-plan-audit. Inputs: `plans/WAVE3_BACKLOG.md` (BL-1..BL-16), `plans/reviews/wave2_synthesis.md`, 11 Wave 3 commits `839e9f6..9b1d1c8`.

## Summary verdict — ACCEPT Wave 3 as delivered

All 16 backlog tickets are closed or justifiably deferred. Every stated acceptance criterion is verifiable in-tree: zero `except Exception` sites, zero production `assert` statements, zero `Stage 2.V` TODOs, all five P1 decomposition targets at or under their split plan, `safe_urlopen` unified, `run_sandboxed` live on both Blender sites, json-ingress audit documented, 9 dead symbols removed, trace manifest indentation normalized, and the `torch>=2.11.0` pin confirmed genuine (torch 2.11.0 is the current PyPI latest and installed in the venv). One scope surprise worth flagging (see below); no rework needed.

## Per-ticket matrix

| Ticket | Commit | Status | Evidence |
|---|---|---|---|
| BL-1 bare-except narrow | `23f8620` | **Closed** | `grep -rn "except Exception" lathe/` → 0 matches (verified). 18 files touched per commit body. |
| BL-2 assert conversion | `23f8620` | **Closed** | `grep -rn "^\s*assert " lathe/` → 0 matches. 16 sites converted to `raise LatheError(...)` subclasses. Combined with BL-1 due to file overlap — acceptable. |
| BL-3 Stage 2.V TODO removal | `839e9f6` | **Closed** | `grep -rn "Stage 2\.V" lathe/` → 0 matches. 6 files, -14/+12. |
| BL-4 checker.py decompose | `11a974e` | **Closed** | 856 LOC → 7-module package, max 397 (`assets.py`). Public `check_program` preserved. Rules mapped by ID. |
| BL-5 blueprints decompose | `49b8eb3` | **Closed** | 717 LOC → 6 modules (common/containers/panels/mechanical/generic + thin `__init__`), max 245. Courier-drone score 0.879435 byte-preserved. |
| BL-6 cli.py decompose | `ff3be49` | **Closed** | 626 LOC → 16-module `cli/` package, max 261 (dispatcher `__init__`). `python -m lathe.cli` works via `cli/__main__.py`. |
| BL-7 capabilities ≤500 | `0121bbd` | **Closed** | 623 → 492 LOC. SSRF helpers deleted locally, sourced from `net.py`. |
| BL-8 resolver.py | *deferred* | **Justified deferral** | `resolver.py` still 540 LOC (40 over cap). Backlog explicitly scoped BL-8 as "split only if Phase 7 audit shows multi-concern"; no surgeon found multi-concern split, so deferral is consistent with the original acceptance clause. Recommend confirming this explicitly in Wave 4 entrance or lifting the cap for this file as single-concern. |
| BL-9 json.loads audit | `17bb3aa` | **Closed (scope as defined)** | `docs/security/json_ingress_audit.md` created, 10 sites annotated inline with TODO(security) at trust-boundary sites. Schemas are scoped to Wave 4 explicitly, so "audit" is complete per Plan 07 Phase 1 step 4. |
| BL-10 Blender env-allowlist | `4c37d49` | **Closed** | Both Blender sites (`blender_execution.py`, `core/stages/topology.py`) route through `subproc.run_sandboxed` with the specified allowlist and forbidden-key rejection (`LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, `BLENDER_SYSTEM_SCRIPTS`, `PYTHONPATH`). |
| BL-11 subproc wrapper | `4c37d49` | **Closed** | `lathe/subproc.py` (250 LOC) exposes `run_sandboxed`, `SandboxResult`, `DEFAULT_STDERR_DENY_PATTERNS`. Combined with BL-10; natural pairing. |
| BL-12 capabilities SSRF unify | `0121bbd` | **Closed** | `probe_hunyuan_endpoint` now calls `net.safe_urlopen`; `_is_loopback_host` / `_is_private_address` / `_resolve_host_addresses` removed from `capabilities.py`; `_NETGUARD_TO_PROBE_CODE` preserves the dict shape. |
| BL-13 dead-code deletion | `6e5a144` | **Closed** | `lathe/shape/geometry/candidates.py` removed (315 LOC); `core/geometry.generate_candidate_mesh` + 2 now-dead helpers removed (-142 LOC). 9/9 symbols gone. |
| BL-14 conditioning.py bare-except | `23f8620` | **Rolled into BL-1** | Commit body lists `shape/geometry/conditioning` among BL-1's 18 touched files. Verified: file contains no `except Exception` clauses post-commit. |
| BL-15 trace_manifest indent | `daf75fc` | **Closed** | 6-line cosmetic fix in `core/stages/package.py::_build_trace`; byte-identical trace_manifest.json confirmed. |
| BL-16 torch pin verification | `9b1d1c8` | **Closed** | Wave 1 TODO removed. Independently verified: `pip index versions torch` → torch 2.11.0 is current PyPI latest and installed in `.venv` as `torch==2.11.0+cpu`. Pin is genuine, not hallucinated. No loosening needed. |

## Scope creep / surprises to flag

**1. `blender_execution.py` LOC trajectory — FAVORABLE, but cap still breached.** The backlog cited the pre-Wave-3 size as 558. Actual measurement: 578 LOC at `61aab04` (end of Wave 2). After BL-10/BL-11 it is **567 LOC** (net −11). The sandbox wrapper extraction did what it was supposed to — moved stderr-scan / env-scrub / expect_files logic out — but the file still exceeds the 500 cap. **This is not a Wave 3 regression** (it went down), but it is a pre-existing Plan 01 ceiling miss that neither Wave 2 nor Wave 3 closed. Recommend a dedicated BL-17 for Wave 4 (see below).

**2. `torch>=2.11.0` pin — verified genuine.** Surgeon's claim is supported by external state: PyPI currently lists 2.11.0 as the latest torch release; the local venv has `torch 2.11.0+cpu` installed. This is not a hallucinated version string. The Wave 1 TODO was resolved correctly.

**3. Cluster-boundary check** — spot-checked each commit's `git show --stat` against its ticket scope:
  - `23f8620` (BL-1+BL-2): 18 files, all inside ticket scope (producers listed in commit body match acceptance).
  - `11a974e` / `49b8eb3` / `ff3be49`: only touch their own decomposition targets plus the split modules. No cross-cluster drift.
  - `0121bbd`: only `capabilities.py` (-133 LOC). Did not modify `net.py` — good discipline, since net.py already had the helpers.
  - `4c37d49`: only `blender_execution.py`, `core/stages/topology.py`, `subproc.py` (new). No drift.
  - `17bb3aa`: 10 files, all are genuine `json.loads`/`json.load` sites annotated with justification comments; 1 new doc file. Clean.
  - `6e5a144`: only the two files whose symbols were declared dead. Clean.
  - `daf75fc`: single file (`core/stages/package.py`). Clean.
  - `9b1d1c8`: single file (`pyproject.toml`). Clean.

No cross-cluster contamination observed.

**4. BL-8 deferral rationale.** The backlog text reads "Borderline; split only if Phase 7 audit shows multi-concern." No surgeon report claims multi-concern, so the deferral is defensible under the original acceptance clause — but Plan 01's hard exit criterion is "every `lathe/**/*.py` file ≤500 LOC." Strict interpretation says BL-8 is not closed; liberal interpretation says the clause overrides the cap for single-concern files. Recommend **an explicit Wave 4 entrance decision**: either (a) lift the cap to 600 for approved single-concern files via a documented waiver in Plan 01, or (b) split resolver.py into `resolver/` package (resolution + variant patches + profile/contract inheritance are plausible axes). Do not leave this implicit.

## New Wave 4 backlog (enumerated)

- **BL-17 (NEW) — `blender_execution.py` decompose.** Still 567 LOC after Wave 3; Plan 01 ≤500 ceiling remains breached. Natural split axes: `_export_blend_artifact` + companion (subprocess call site), `_render_intent_bake_plan` (bake planning), and report-dict builders. Effort ~0.5 day.
- **BL-18 (NEW) — `resolver.py` disposition.** Either decompose or record a documented cap waiver in Plan 01. Effort 0.25–1 day depending on path.
- **BL-19 (NEW) — Trust-boundary schemas for `json_ingress_audit.md` sites.** Plan 07 completion — write schemas + route through `validation.validate_json` for every site currently marked `TODO(security)` in the audit doc. Effort 1–2 days depending on site count.
- **Plan 04 test backfill (Tranches A-C) + golden snapshots.** Independent Wave 3+/4 track; not scope creep. Anchor owner.
- **Plan 02 docs content** (tutorials, cookbook, stdlib doc blocks). Independent parallel track.
- **Plan 08 product quality** (publish runner, `lathe fmt`, second stack). Wave 4 anchor.
- **CI enforcement for Wave 3 invariants.** Ruff `BLE001` and `S101` enablement was promised in the BL-1/BL-2 commit body "landed separately in Wave 3 tooling track" but I did not verify it here. Wave 4 entrance should confirm the rules are wired into the ruff config or add them.

## Recommendation

**Accept Wave 3.** Substantive Plan 01 / Plan 07 / Plan 10 completeness achieved; contract stable; scope discipline held across 11 commits. Open BL-17, BL-18, BL-19 as Wave 4 seed items, and force a documented decision on resolver.py at Wave 4 entrance rather than letting the deferral persist silently. Verify the ruff `BLE001` / `S101` CI rules are active before closing Wave 3.
