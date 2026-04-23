# Meta-Review: Plans 01–10

Synthesis of 10 parallel reviewers against the plans, the original audit, and the actual repo state.

## Revised scores (reviewer verdicts)

| # | Plan | Original | Reviewer verdict | Delta |
|---|---|---|---|---|
| 01 | Code Quality | 7 → 10 | **~9/10 as written** | executor.py missing |
| 02 | Documentation | 8 → 10 | **~9.5/10 as written** | small factual drift |
| 03 | Architecture | 8 → 10 | **~8.5/10 as written** | executor god-class; thin 2nd stack |
| 04 | Test Coverage | 4 → 10 | **8.5/10 as written** | wrong subpackage paths; key modules missed |
| 05 | Developer Experience | 7 → 10 | **8.5/10 as written** | factual drift; LSP under-budgeted |
| 06 | Maintenance | 3 → 10 | **8.5/10 as written** | VGGT vendoring policy blocker |
| 07 | Security | 6 → 10 | **8.5/10 as written** | second SSRF + subprocess site missed |
| 08 | Product Quality | 6 → 10 | **8.5/10 as written** | Phase 4/12 under-budgeted |
| 09 | Product Value & Vision | 8 → 10 | **8.5/10 as written** | persona-C GTM missing; monetization sequencing |
| 10 | Bugs & Errors | 5 → 10 | **5.5/10 as written** | 3 of 15 findings wrong; hierarchy conflict |

No plan as-written reaches 10/10. Median gap ~1.5 points. Plan 10 has the largest credibility hole — three of its fifteen findings are false-positives or already-fixed.

---

## Cross-cutting themes

### 1. `executor.py` is the unacknowledged god-module

**The original audit missed this entirely.** Three reviewers independently flagged it:

- `lathe/executor.py` is **2,315 LOC** — larger than `parser.py` (1,666) and `shape_providers.py` (998).
- Contains a 940-line `BuildExecutor` god-class.
- Holds ≥8 of the repo's 27 `except Exception` sites.
- Contains a **second unhardened subprocess** at `executor.py:1548` (`_run_blender_topology`), identical pattern to `blender_execution.py:210-228`.

**Amendment required:** Code Quality (01) and Architecture (03) plans must both add `executor.py` decomposition. Bugs plan (10) must add the second subprocess site.

### 2. Bare-except undercount

Audit said "≥2 bare-excepts." Reviewers found **27 sites across 12 files**, with ~20 more comparable patterns in `executor.py`, `validators/`, and `exact_solids.py`. Plan 01's fix list must expand accordingly. Additionally, **17 production `assert` statements** exist (which are stripped with `python -O`) — not in any plan.

### 3. Audit citation errors

Reviewer-bugs verified every finding and found three are wrong:

- **C3 (shape_providers.py:~444):** **already fixed** — line 442 already raises `ShapeProviderExecutionError(code="missing_image_ref")`. Remove from plan.
- **Mi3 (magic `7919` in shape_providers.py):** **hallucinated** — constant does not appear in that file. (It does appear at `executor.py:1176`, `shape_backend.py:59`, `scaffold_compiler.py:29` — so the item is still real, just mis-cited.)
- **Mi5 (trimesh missing in venv):** **contradicted** — trimesh 4.11.5 is installed. Remove or re-scope.

**C2** description is also wrong: the bare-except is a BFS-fallback, not a silent-zero. Plan's fix should reflect that.

### 4. Count drift in the audit

- Transient dirs: **94 actual**, not "~30" (DX plan 05)
- Stdlib `.lth` files: **21 actual**, not "29" (Docs plan 02)
- Source LOC: **~17,061 actual**, not "15,663" (Tests plan 04)
- Files >500 LOC violating CQ plan's own exit criterion: **7** (executor.py 2315, parser.py 1666, shape_providers.py 998, checker.py 856, blueprints/__init__.py 717, shape_backend.py 665, cli.py 625, blender_execution.py 558)

### 5. Second SSRF site

Security plan 07 fixes `shape_providers.py:567` but misses `capabilities.py:395` — `probe_hunyuan_endpoint` uses the same user-supplied `base_url` via `urllib.request.urlopen` and needs the same SSRF guards.

### 6. Cross-plan ownership conflicts

- `.gitignore` — specified in both 05 (DX) and 06 (Maintenance). Single owner: **06**, DX plan links to it.
- `pyproject.toml` — touched by 01, 02, 05, 06, 07. Needs a coordination pass.
- `mkdocs.yml` in 02 (docs) deploys via a workflow owned by 06 (maint). Declare dependency.
- `lathe fmt` strict-mode flip in 08 skips the deprecation window 08 Phase 11 otherwise mandates. Fix 08.
- `external/vggt/` vendoring policy is undefined — **blocks** Plan 06 Phase 1 (first commit) until resolved.

### 7. Grammar already supports comments

Plan 02 Phase 7 item #25 worried about adding `# doc:` parser support. Grammar already allows `//` and `/* */` at `lathe.lark:257-263`. No-op.

### 8. Effort estimates systematically ~20-30% optimistic

Reviewers revised totals:
- Plan 01: 5–6d → ~10–12d (executor.py adds scope)
- Plan 02: 10d → ~11d
- Plan 04: 15d → ~18–20d
- Plan 05: 9d → ~12–13d (LSP + VS Code marketplace is heavier)
- Plan 08: 9–11w → ~12–13w (Pyodide + soft-surface stack)

### 9. Monetization sequencing (Plan 09)

CI-SaaS is premature for a 3-day-old repo. **Invert the order**: hosted registry (kits/libraries) first as a paid product; CI cert service second. Persona-C (AI coding agents) has no GTM at all — channels are agent-framework registries, not Discords.

### 10. Tool picks are defensible

Reviewers confirmed: mkdocs-material > Sphinx (repo is markdown-native); `uv` > Poetry/pip-tools; `just` > plain Make; pygls for LSP; syrupy/mutmut/hypothesis for tests; Apache-2.0 license. **Caveats:** argcomplete does not cover PowerShell natively (Plan 05 Phase 10 claim wrong); Apache-2.0 justification in Plan 02 wrongly cites VGGT license as precedent — VGGT ships under a custom Meta license, not Apache.

---

## Must-do amendments before executing any plan

1. **Add `executor.py` decomposition** to Plans 01 + 03 as a first-class target.
2. **Expand bare-except inventory** in Plan 01 from 2 sites to the full 27; add the 17 production `assert` statements.
3. **Delete / re-scope findings C3, Mi3, Mi5** in Plan 10. Rewrite C2 description. Re-cite Mi3 at the correct files.
4. **Add `capabilities.py:395` SSRF** to Plan 07. Add `executor.py:1548` subprocess to Plans 07 and 10.
5. **Resolve `external/vggt/` vendoring policy** before any git commit lands (Plan 06 Phase 1 blocker).
6. **Arbitrate cross-plan file ownership** for `.gitignore`, `pyproject.toml`, `mkdocs.yml`.
7. **Fix Apache-2.0 justification** in Plan 02 (drop VGGT precedent claim).
8. **Correct counts** across plans: 94 transient dirs, 21 stdlib files, 17k source LOC.
9. **Invert monetization order** in Plan 09: registry before CI-SaaS.
10. **Inflate effort estimates** by ~25% to match reviewer math.

## Execution order implication

Plans 06 → 05 → 01 → 10 → 07 → 04 → 03 → 02 → 08 → 09 makes more sense than plan-number order:

- 06 (maintenance) first — gives git/CI/LICENSE foundation others depend on.
- 05 (DX) next — lockfile, task runner, hygiene unblock CI stability.
- 01 (code quality) + 10 (bugs) land the critical fixes before refactors.
- 07 (security) hardens the code before it's published.
- 04 (tests) codifies the behavior once stable.
- 03 (architecture) restructures safely behind tests.
- 02 (docs) once API stabilized.
- 08 (product quality) + 09 (vision) for launch.

Rough total: **~90 engineer-days** (13 person-weeks) for 10/10 across all dimensions. Single maintainer → ~4 months.
