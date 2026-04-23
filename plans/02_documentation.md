# Implementation Plan: Documentation 8/10 → 10/10

## Overview
Close the ten documentation gaps by shipping repo-hygiene files, an auto-generated docs site, a tutorial ladder, architecture diagrams, stdlib doc blocks, a cookbook, and enforced docstring standards. Additive only; does not touch `lathe.shape.intent_mesh_handoff_v1`.

---

## Phase 1 — Repo hygiene baseline (0.5 day)

1. **LICENSE** — `D:\lathe_v0_1\LICENSE`. **Apache-2.0.** Justification: (a) MIT is too thin given patent-sensitive surface around learned 3D providers (Hunyuan, VGGT) and bake/render; (b) Apache's explicit patent grant + termination clause protects contributors; (c) compatible with any GPL-3 dependencies; (e) industry standard for compiler/runtime projects. **Also:** add `license = { text = "Apache-2.0" }` (or `license-files = ["LICENSE"]` per PEP 639) to the `[project]` table in `pyproject.toml`, plus the matching `License :: OSI Approved :: Apache Software License` classifier.
2. **CONTRIBUTING.md** — bootstrap pointer, branch/PR conventions, test gates (`pytest -q` + `lathe test` + `lathe bench`), the coordinated-change rule from AGENTS.md, stable-contract-ID policy, commit format, DCO sign-off. Contains explicit pointers to `AGENTS.md` for the coordinated-change rule across spec/grammar/schema/parser/normalizer/resolver/checker/examples/tests — do not duplicate that policy, link it.
3. **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1; contact `talmerri@gmail.com`.
4. **SECURITY.md** — private disclosure, supported versions (v0.1.x), learned-provider sandbox caveats.
5. **.github/** — PR template, issue templates (bug, feature, spec-change, backend-add), CODEOWNERS.

## Phase 2 — CHANGELOG + versioning (0.5 day)

6. **CHANGELOG.md** — Keep-a-Changelog 1.1 + SemVer. Seed `[Unreleased]` + `[0.1.0]`. Subsections: Added / Changed / Deprecated / Removed / Fixed / Security / Contract-stability.
7. **docs/versioning.md** — Language-surface additive = MINOR; breaking = MAJOR; stable backend/contract IDs require MAJOR bump or new ID suffix.

## Phase 3 — Docs site (1.5 days)

8. **Tool: mkdocs-material + mkdocstrings[python].** Rationale: (a) existing docs are markdown-native (`docs/`, `spec/`, `docs/Specs/`) — Sphinx+rST conversion cost prohibitive for ~4000 lines; (b) mkdocstrings ingests Google/Numpy docstrings directly; (c) mkdocs-material has first-class mermaid, admonitions, tabbed code; (d) simpler GitHub Pages deploy; (e) matches scaffold ethos.
9. **mkdocs.yml** — Nav: Home / Quickstart / Tutorial / Language Reference / Cookbook / Architecture / API Reference / Specs / Contributing. **Ownership:** this plan owns `mkdocs.yml`. Plan 06 Maintenance workflow `docs.yml` consumes it.
10. **docs/api/** — one generated page per top-level module: parser, normalizer, resolver, checker, planner, executor, backends, shape_backend, shape_providers, asset_graph, assembly_kernel, shape_ir, mesh_finalize, conformance, feature_grammar, feature_fusion, validators/*, bridge/blender_plan. Each uses `::: lathe.<module>`.
11. **requirements-docs.txt** — `mkdocs-material>=9.5`, `mkdocstrings[python]>=0.26`, `mkdocs-mermaid2-plugin`, `mkdocs-gen-files`, `mkdocs-literate-nav`, `mkdocs-section-index`. Add `docs` extra to pyproject.

## Phase 4 — Deployment (0.5 day)

12. **.github/workflows/docs.yml** — on push to main: `pip install -e .[docs]`, `mkdocs build --strict`, `mkdocs gh-deploy --force`. **GitHub Pages over ReadTheDocs**: single-repo ownership, no secondary config, faster CI. **Cross-plan dependency:** `docs.yml` depends on Plan 06 (Maintenance) having provided the base CI infrastructure and the `.github/workflows/` skeleton. Coordinate so `docs.yml` is the second workflow to land, directly after `ci.yml`.
13. **README badges** — docs status, license, Python version, PyPI placeholder.

## Phase 5 — Tutorial ladder (2 days)

14. **docs/quickstart.md** — **60-second quickstart**. Three commands: bootstrap, `lathe doctor`, `lathe build examples/courier_drone.lth courier_drone --out dist`. Screenshot of `dist/` tree.
15. **docs/tutorial/first_asset.md** — **~15 min "Author your first .lth asset"**. Builds `bookshelf.lth` from scratch: profile → contract → asset → variant → check → plan → build. New `examples/tutorial_bookshelf.lth`.
16. **docs/tutorial/second_asset_reconstruct.md** — ~20 min reconstruct flow with `reference_set` + `reconstruct_policy`.
17. **docs/tutorial/deep_dive.md** — Links into `spec/lathe-v0.1.md` and `docs/Specs/Lathe-V1.*-Spec.md` with reading order.

## Phase 6 — Architecture diagrams (1 day)

18. **docs/architecture/overview.md** — C4 Level 1 (context) + Level 2 (container) in mermaid.
19. **docs/architecture/pipeline.md** — Mermaid flowchart of `STAGE_ORDER` (refs → intent → shape → topology → uv → surface → execution → rig → interfaces → physics → optimize → validate → package → publish). Annotate probabilistic vs deterministic.
20. **docs/architecture/shape_stage.md** — Mermaid sequence: intent → AssetGraph → assembly blueprint → ShapeIR → fused search → authoritative mesh → provider proposals → conformance fit.
21. **docs/architecture/backends.md** — Component diagram of `hard_surface_game_asset_v1` with attempted-vs-actual arrows.
22. **Embed overview in README** above "What is implemented".

## Phase 7 — stdlib documentation audit (1.5 days)

23. **Add `# doc:` comment block to every `.lth` in `std/`** (21 files). Each: purpose, exported symbols, dependencies, used-by examples, stability. Priority: `std/families/*` (9), `std/components/*` (9), and one each in benchmarks, kits, libraries, materials, mechanisms, palettes, patterns, policies, repair, spaces, plus `std/surface_programs/*` (2).
24. **docs/stdlib/index.md** — Auto-index via `mkdocs-gen-files` script `docs/gen_stdlib_index.py`.
25. Grammar already supports `//` and `/* */` comments (`grammar/lathe.lark:257-263`) — no parser change needed.

## Phase 8 — Cookbook (1.5 days)

26. **docs/cookbook/** — thirteen runnable recipes (150–300 lines each):
    1. `01_generate_flow.md`
    2. `02_reconstruct_flow.md`
    3. `03_kit_assembly.md`
    4. `04_mobile_adapt.md`
    5. `05_surface_control.md` (V1.2)
    6. `06_variant_patching.md`
    7. `07_custom_backend.md`
    8. `08_runtime_config.md` (Hunyuan/VGGT/auto)
    9. `09_certification_debug.md`
    10. `10_blender_bridge.md` (V1.3.1)
    11. `runtime_config_schema.md` — reference docs for `examples/runtime_configs/*.json`; mirrors the JSON schema introduced in Plan 07.
    12. `reading_a_trace.md` — how to interpret `build_report.json` output, attempted-vs-actual provider records, and Reference/Fit/Transfer/Kit IR fields.
    13. Per-validator reference pages under `docs/api/validators/` — one page per `lathe/validators/*.py` (semantic_quality, visual_quality, flow_quality, surface_quality, silhouette) covering pass/fail criteria and metric definitions.

## Phase 9 — Inline docstring standard (1 day)

27. **docs/contributing/docstrings.md** — Google-style. **Required on** every public function/class in `_LAZY_EXPORTS`, every CLI command handler, every module with public surface (parser, normalizer, resolver, checker, planner, executor, backends, shape_backend, shape_providers, asset_graph, assembly_kernel, scaffold_compiler, shape_ir, feature_grammar, feature_fusion, mesh_finalize, conformance, `*_ir.py`, validators/*, bridge/blender_plan), every class in `__all__`. Exempt: private helpers, `tests/`, `scaffolds/`.
28. **Enforcement** — ruff `D100,D101,D102,D103,D205,D400` with per-dir ignores; CI step `ruff check --select D lathe/`.
29. **Module-level docstrings** — mandatory first.

## Phase 10 — Measurable 10/10 exit criteria

- [ ] `LICENSE` (Apache-2.0), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md` at repo root.
- [ ] `mkdocs build --strict` passes with zero warnings.
- [ ] Docs site live at `https://<user>.github.io/lathe/` with green CI.
- [ ] 100% of `_LAZY_EXPORTS` have Google-style docstrings; `ruff check --select D lathe/` exits 0.
- [ ] Every `.lth` under `std/` has a `# doc:` block; `docs/stdlib/index.md` auto-generates.
- [ ] Quickstart reproducible in ≤60s on fresh clone (timed via `scripts/lathe_smoke.sh`).
- [ ] First-asset tutorial reproducible end-to-end; `examples/tutorial_bookshelf.lth` builds in CI.
- [ ] ≥1 mermaid diagram in README, ≥4 in `docs/architecture/`.
- [ ] All 10 cookbook recipes execute in dedicated `cookbook-smoke.yml`.
- [ ] CHANGELOG gated in PR template.
- [ ] README badges: docs-build, license, python-version, tests.
- [ ] `interrogate lathe/ --fail-under 90` enforced in CI.

**Total effort: ~11 engineer-days.** Phases 1–4 unblock; 5–8 parallelize; 9 runs continuously. Cookbook recipes 5/7/8/10 are runtime-heavy (V1.2 surface, custom backends, runtime configs, V1.3.1 Blender bridge) and account for the extra day over the original ~10-day estimate.

---

**Relevant paths:**
- `D:\lathe_v0_1\README.md`, `CLAUDE.md`, `AGENTS.md`, `spec/lathe-v0.1.md`
- `D:\lathe_v0_1\docs\Specs\Lathe-V1.0-Spec.md` through `Lathe-V1.3.1-Spec.md`
- `D:\lathe_v0_1\std\` (21 `.lth` files)
- `D:\lathe_v0_1\lathe\__init__.py` (public API)
- `D:\lathe_v0_1\lathe\cli.py` (tutorial surface)
- `D:\lathe_v0_1\grammar\lathe.lark`
- `D:\lathe_v0_1\examples\courier_drone.lth` (quickstart subject)

---

## Amendment log (2026-04-23)

Amendments applied by `amender-docs` based on `plans/reviews/02_documentation_review.md` and cross-cutting items in `plans/reviews/00_meta_review.md`:

1. Phase 1 item #1 — dropped the factually incorrect "(d) matches `external/vggt/LICENSE.txt` precedent" sub-point from the Apache-2.0 justification. `external/vggt/LICENSE.txt` is Meta's custom VGGT license, not Apache-2.0. Other justifications (patent grant, GPL-3 compat, ecosystem norm, patent-sensitivity of learned providers) stand unchanged.
2. Phase 1 item #1 — added `pyproject.toml` license-field update (`license = { text = "Apache-2.0" }` or PEP 639 `license-files = ["LICENSE"]`) plus OSI classifier.
3. Phase 1 item #2 — added explicit instruction to link `AGENTS.md` for the coordinated-change rule rather than restating it, to prevent drift.
4. Phase 3 item #9 — clarified ownership: this plan owns `mkdocs.yml`; Plan 06 workflow `docs.yml` consumes it.
5. Phase 4 item #12 — added cross-plan dependency note: `docs.yml` depends on Plan 06 (Maintenance) providing the base `.github/workflows/` skeleton; it should land as the second workflow after `ci.yml`.
6. Phase 7 item #23 — corrected stdlib `.lth` count from 29 to 21 (reviewer-verified breakdown: families 9, components 9, surface_programs 2, and one each in benchmarks/kits/libraries/materials/mechanisms/palettes/patterns/policies/repair/spaces). "Relevant paths" footer updated to match.
7. Phase 7 item #25 — dropped the grammar-comment-support check (no-op: `grammar/lathe.lark:257-263` already defines `//` and `/* */` tokens). Replaced with a one-line note.
8. Phase 8 item #26 — added three recipes: (11) `runtime_config_schema.md` reference docs mirroring the Plan 07 JSON schema; (12) `reading_a_trace.md` covering `build_report.json` / attempted-vs-actual provider records / IR fields; (13) per-validator reference pages under `docs/api/validators/` (one per `lathe/validators/*.py`). Recipe count updated from ten to thirteen.
9. Effort estimate raised from ~10 to ~11 engineer-days to account for runtime-heavy cookbook recipes 5/7/8/10.

