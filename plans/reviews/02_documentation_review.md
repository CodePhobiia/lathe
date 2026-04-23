# Review: Plan 02 — Documentation

**Reviewer:** reviewer-docs | **Plan:** `D:\lathe_v0_1\plans\02_documentation.md` | **Score being closed:** 8/10 → 10/10

## Summary
Plan is comprehensive, well-sequenced, and addresses every flagged gap. Citation accuracy is good but contains two small inaccuracies worth fixing. The Apache-2.0 justification has a factual error. The plan is feasible at ~10 eng-days if Phase 7 scope is corrected and Phase 4 deployment dependency on the Maintenance CI plan is acknowledged.

## Coverage checklist (gap → plan item)

| Finding gap | Plan item | Covered |
|---|---|---|
| No LICENSE | Phase 1 #1 (Apache-2.0) | yes |
| No CHANGELOG.md | Phase 2 #6 | yes |
| No CONTRIBUTING.md | Phase 1 #2 | yes |
| No formal API reference | Phase 3 #10 (mkdocstrings per-module) | yes |
| No language reference site | Phase 3 #8–9 (mkdocs-material nav) | yes |
| stdlib `.lth` modules lack docs | Phase 7 #23–24 | yes (scope off, see below) |
| No 60-sec quickstart | Phase 5 #14 | yes |
| No architecture diagram | Phase 6 #18–22 | yes |
| No examples walkthroughs / cookbooks | Phase 8 #26 (10 recipes) | yes |

## Citations verified against repo
- LICENSE/CHANGELOG/CONTRIBUTING/CODE_OF_CONDUCT/SECURITY: **all truly absent** from `D:\lathe_v0_1\` (ls confirmed). `.github/` exists but is empty.
- README is **414 lines**, not 415 (finding stated 415). Minor.
- `docs/lathe_manifesto.md` = 165 lines, `docs/lathe_prd.md` = 429 lines, `spec/lathe-v0.1.md` = **1217 lines** (finding claimed "2,000+ line spec" — **inaccurate**; total across repo docs is ~2,400). The V1.0–V1.3.1 spec files under `docs/Specs/` add more; combined is still load-bearing.
- `grammar/lathe.lark` lines 257–263: `COMMENT_LINE: /\/\/[^\n]*/` and `COMMENT_BLOCK: /\/\*[\s\S]*?\*\//` both `%ignore`d. **Parser already accepts `//` and `/* */` comments** — plan item #25 ("extend grammar if needed") will be a no-op, which is correctly noted as conditional.
- std/ contains **21 `.lth` files** across 13 subdirs (not 29 as plan #23 states). Verified: families 9, components 9, plus 1 each in benchmarks/kits/libraries/materials/mechanisms/palettes/patterns/policies/repair/spaces; surface_programs has 2.
- `pyproject.toml` has **no `license` field** — plan should add `license = {text = "Apache-2.0"}` and a classifier when writing LICENSE.
- `external/vggt/LICENSE.txt` is a **custom "VGGT License" (Meta/research-use)**, NOT Apache-2.0. Plan's Phase 1 #1 justification "(d) matches `external/vggt/LICENSE.txt` precedent" is **factually wrong** — drop or rewrite this bullet. The other four justifications (patent grant, GPL compat, ecosystem norm, patent-sensitivity of learned providers) stand on their own and are sufficient.

## Already-done items (plan can de-scope)
- **Parser comment support (#25):** already present; only the grammar sync concern is relevant.
- **Quickstart content (#14 partial):** README §Install + §CLI (lines 53–143) already contain a usable 3-command path — plan's 60-sec quickstart should *link to and trim* README rather than duplicate.
- **CONTRIBUTING overlap (#2):** `AGENTS.md` (70 lines) covers the coordinated-change rule, test gates, and stable-contract-ID policy. Plan should explicitly reference AGENTS.md as the canonical source rather than restating — otherwise these drift.
- **Architecture diagrams (#18–22):** none in `docs/` (grep for "mermaid|diagram" returned 4 hits, all in `docs/Specs/Lathe-V1.*-Spec.md`, which are Gamma spec decks, not C4 diagrams). Plan correctly identifies this gap.

## Gaps I would add
1. **Runtime config schema reference.** `examples/runtime_configs/*.json` (Hunyuan/VGGT/auto-learned) has no documented schema. Add to Language Reference nav.
2. **Per-stage validator docs.** `lathe/validators/{semantic_quality,visual_quality,flow_quality,surface_quality,silhouette}.py` define certification pass/fail — deserve one page each under Language Reference, not just mkdocstrings dumps.
3. **Trace/bundle field reference.** Shape bundles, surface bundles, and traces (attempted-vs-actual provider, Reference/Fit/Transfer/Kit IR) are the main debugging surface — plan buries them in mkdocstrings. Add a dedicated "Reading a trace" page in Cookbook or Architecture.
4. **pyproject license field update** is missing from Phase 1.
5. **Deprecation of `docs/v08_*` files:** `docs/v08_language_reference.md` and `docs/v08_migration_guide.md` predate the mkdocs site; plan doesn't say whether they migrate or redirect. Clarify.

## Tool choice — mkdocs-material vs Sphinx
**Defensible.** Repo is 100% markdown (no existing `conf.py`, no `.rst` files anywhere), `docs/` and `spec/` are already MD, `docs/Specs/` uses mermaid already. Sphinx+rST conversion cost on ~2,400 lines is real. mkdocstrings handles Google/Numpy docstrings. Agree with the call.

## Feasibility
~10 engineer-days is **tight but plausible** if parallelized as stated. Risks:
- **Phase 4 depends on CI (Plan 06 Maintenance).** `docs.yml` workflow assumes GitHub Actions is set up. If Maintenance plan owns CI bootstrap, this needs a cross-plan dependency note. Add.
- **Phase 7 shrinks from 29 → 21 files** (~0.5d saving).
- **Phase 8 cookbook at 150–300 lines × 10 recipes is optimistic** at 1.5d; realistic is 2.5d, especially recipes 5/7/8/10 which require actually running V1.2 surface, custom backends, runtime configs, and V1.3.1 Blender bridge. Revised total ~11 eng-days.
- **Phase 9 interrogate + ruff D-codes** will initially fail loudly against existing lathe/ (~100 modules). Needs per-dir ignore bootstrap list, not just "enforce". Call this out.

## Does plan deliver 10/10?
**Yes, with the fixes above.** Coverage is complete, exit criteria are measurable (mkdocs --strict, interrogate ≥90, ruff D exit 0, 60s quickstart, auto-index for stdlib). Required edits before execution:
1. Drop/rewrite the Apache-2.0 "matches external/vggt precedent" bullet (factually wrong).
2. Correct stdlib file count 29 → 21 in Phase 7.
3. Add `pyproject.toml` license field to Phase 1.
4. Add cross-plan dependency note: Phase 4 deploy assumes Plan 06 CI exists.
5. Add runtime-config schema, validator docs, trace-reading cookbook as explicit items.
6. Reference AGENTS.md from CONTRIBUTING.md rather than duplicating its content.

With those, plan credibly closes all ten gaps and is buildable in ~11 eng-days.
