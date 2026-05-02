# Asset Quality Upgrade Evidence

## Summary

Phase 14 proves deterministic quality-pipeline evidence for a golden industrial crate and three hard-surface smoke families. Phase 14B adds deterministic proxy preview PNGs for the golden crate. Phase 14C adds a hero sword art-direction fixture and a universal quality engine with four family-spanning proof fixtures. Phase 16 adds deterministic semantic patching for asset-quality fixtures. It does not claim final production-game certification because real DCC high/low baking and external renderer/game-engine verification remain outside this lane unless those artifacts are actually present.

## Golden Example Path

`examples/asset_quality/golden_industrial_crate/`

The golden fixture includes:

- `design_brief.json`
- `family_grammar_coverage.json`
- `construction_graph.json`
- `shape_ir_v2.json`
- `high_low_relation.json`
- `material_wear_graph.json`
- `reference_board.json`
- `preview_evidence.json`
- `vision_critique.example.json`
- `quality_certificate.json`
- `quality_report.md`
- deterministic proxy previews under `previews/`
- deterministic snapshot hashes under `snapshots/`

## Certification Result

- Golden warning mode: PASS
- Golden strict mode: FAIL
- Golden score: 96 / 100
- Strict blockers: `real_bake_not_executed`
- Hero sword warning mode: PASS
- Hero sword strict mode: FAIL
- Hero sword score: 95 / 100
- Hero sword art-direction score: 91 / 100
- Hero sword strict blockers: `real_bake_not_executed`
- Phase 16 sample patch warning validation: PASS
- Phase 16 patched strict mode: FAIL
- Phase 16 patched strict blockers: `real_bake_not_executed`

Warning mode passes because the fixture contains complete deterministic evidence and every skipped external lane is documented. Strict mode still fails because there is no real high/low bake. It no longer fails for missing preview imagery because deterministic proxy preview PNGs are checked in.

## Evidence Artifacts

The golden certificate maps every pass/fail claim to a checked-in artifact:

- design brief: `design_brief.json`
- family grammar: `family_grammar_coverage.json`
- construction graph: `construction_graph.json`
- shape/detail hierarchy: `shape_ir_v2.json`
- high/low relation: `high_low_relation.json`
- material/wear graph: `material_wear_graph.json`
- references: `reference_board.json`
- preview truthfulness: `preview_evidence.json`
- preview final beauty: `previews/final_beauty.png`
- preview material IDs: `previews/material_ids.png`
- preview wireframe: `previews/wireframe.png`
- preview comparison sheet: `previews/comparison_sheet.png`
- report: `quality_report.md`

## Warning Vs Strict Thresholds

Warning certification requires score >= 70 and no critical missing artifact. Strict certification requires score >= 90, warning pass, no strict blockers, stable snapshots, and non-skipped strict preview/bake lanes.

The golden crate exceeds the strict score threshold but still fails strict mode because named gates are not hidden by the aggregate score.

## Phase 14C Hero Art Direction

`examples/asset_quality/hero_sword/`

The hero sword fixture adds the first visible art-direction lane. It records a design brief, a silhouette plan, a semantic construction graph, material/wear intent, proxy high/low evidence, deterministic previews, a certificate, a report, and snapshot hashes.

New validator dimensions:

- `silhouette_strength`
- `proportion_quality`
- `material_separation`
- `focal_point_readability`
- `ornament_intentionality`
- `procedural_noise_penalty`
- `thumbnail_readability`

The hero art-direction gate passes warning and strict art-direction thresholds, but the overall strict certificate remains blocked by `real_bake_not_executed`. This is intentional: Phase 14C improves taste and evidence, not the real high/low bake lane.

## Phase 14C Universal Quality Engine

`examples/asset_quality/quality_engine/`

Phase 14C generalizes the hero art-direction lane into a reusable quality engine. The proof fixtures are:

- `fantasy_weapon`
- `sci_fi_crate`
- `roblox_tycoon_machine`
- `environment_shop_counter`

Each fixture includes:

- `design_brief.json`
- `art_direction.json`
- `quality_plan.json`
- `family_grammar_coverage.json`
- `construction_graph.json`
- `material_wear_graph.json`
- `high_low_relation.json`
- `preview_evidence.json`
- `semantic_critique.example.json`
- `quality_certificate.json`
- `quality_report.md`
- deterministic proxy previews under `previews/`
- deterministic snapshot hashes under `snapshots/`

Universal quality dimensions:

- `silhouette_strength`
- `proportion_intent`
- `material_contrast`
- `detail_hierarchy`
- `motif_coherence`
- `surface_storytelling`
- `functional_readability`
- `style_consistency`
- `procedural_noise_penalty`

The planner is family-agnostic: it classifies broad object families and produces quality targets for weapons, containers, machines, furniture, architecture, environment pieces, and generic props. The proof fixtures validate that the same planner can score a fantasy weapon, sci-fi crate, Roblox tycoon machine, and shop counter without hardcoding a sword generator.

The dedicated universal-quality scorer records per-dimension scores, diagnostics, and semantic repair suggestions. The scorecard is planning/certification evidence; it does not replace real renderer, bake, or export gates.

All four proof fixtures pass warning mode and have strict blockers limited to `real_bake_not_executed`.

## Phase 16 Semantic Patching

Phase 16 proves fixture-level semantic editing for `examples/asset_quality/hero_sword/`.

Sample patches:

- `examples/asset_quality/hero_sword/patches/wider_blade.json`
- `examples/asset_quality/hero_sword/patches/gold_guard_trim.json`
- `examples/asset_quality/hero_sword/patches/edge_battle_damage.json`
- `examples/asset_quality/hero_sword/patches/roblox_safe_profile.json`

The patch lane copies a fixture to an output directory, applies validated JSON evidence changes, writes `patch_result.json`, regenerates deterministic proxy previews, recomputes certification/report artifacts, and refreshes snapshots. It rejects raw mesh edits, public `.lth` surface edits, and shape handoff contract changes.

## Smoke Examples

Smoke warning validation passes for:

- `examples/asset_quality/smoke_mechanical_door/`
- `examples/asset_quality/smoke_service_cabinet/`
- `examples/asset_quality/smoke_terminal_or_supply_chest/`

Smoke examples prove breadth of the evidence shape across hard-surface families. They are not hero certificates and do not claim final production readiness.

## Preview And Render Truthfulness

External renderer used: no.

The golden crate and hero sword preview evidence mark final beauty, material IDs, wireframe, and comparison sheet as `present` with paths under `previews/`. These files are deterministic proxy PNGs produced by `lathe.asset_quality.preview_render.deterministic_proxy_v1`; they are not Blender, Roblox, USD viewer, game-engine, or external renderer output.

## High/Low And Bake Truthfulness

Real high/low bake used: no.

The golden crate and hero sword use `mode = "proxy_bake"`. AO and curvature are represented as proxy evidence, while normal baking is explicitly skipped. The strict blocker is `real_bake_not_executed`.

## Material/Wear Proof

The golden material/wear graph binds material zones and wear masks to semantic construction nodes and edge targets. It records painted steel, rubber/contact regions, exposed edge metal, warning decal accent, and contact grime zones. Uniform-noise detection is false, and unresolved node/edge binding lists are empty.

## Known Limitations

- No real DCC high-poly source is produced.
- No real bake maps are generated.
- Preview images are deterministic proxy evidence only, not final renderer output.
- No external renderer or game-engine viewer is executed.
- Smoke fixtures validate warning-mode evidence structure only.
- The hero sword fixture validates art direction and deterministic proxy visual evidence, but does not certify the asset for production-game use.
- Semantic patches operate on checked-in evidence fixtures first; they are not live mesh regeneration.
- Phase 14C universal quality planning is evidence and certification logic first; it does not yet drive real mesh regeneration.
- Phase 15 CI/regression gates are intentionally not implemented here.

## Commands Run

Commands run during Phase 14 implementation:

```bash
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode warning
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode strict  # expected non-zero: strict blockers remain
python -m lathe.cli asset-quality certify examples/asset_quality/golden_industrial_crate --out .tmp_tests/asset_quality/golden_crate_cert
python -m lathe.cli asset-quality catalog-examples examples/asset_quality --out .tmp_tests/asset_quality/example_catalog.json
python -m lathe.cli check examples/industrial_crate_experimental.lth
python -m lathe.cli check examples/industrial_crate.lth
```

Focused tests:

```bash
python -m ruff check lathe/asset_quality/certification.py lathe/cli/asset_quality_cmd.py tests/unit/test_asset_quality_certification.py tests/unit/test_asset_quality_phase14_examples.py tests/unit/test_cli_errors.py
python -m pytest -q tests/unit/test_asset_quality_phase14_examples.py tests/unit/test_asset_quality_certification.py
python -m pytest -q tests/unit/test_asset_quality_phase14_examples.py tests/unit/test_asset_quality_certification.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command
python -m pytest -q tests/unit/test_cli_errors.py
$files = Get-ChildItem tests\unit -Filter test_asset_quality_*.py | ForEach-Object { $_.FullName }; python -m pytest -q @files
python scripts/generate_cli_reference.py
python -m pytest -q tests/test_architecture.py::test_importlinter_contracts_pass tests/unit/test_cli_reference_docs.py tests/unit/test_exception_inventory.py tests/golden/test_cli_help_snapshots.py
python -m ruff check lathe\asset_quality\certification.py lathe\cli\asset_quality_cmd.py lathe\cli\__init__.py lathe\resolver.py lathe\checker\experimental.py tests\unit\test_asset_quality_certification.py tests\unit\test_asset_quality_phase14_examples.py tests\unit\test_cli_errors.py tests\unit\test_exception_inventory.py
python -m pytest -q
git diff --check
```

Commands run during Phase 14B implementation:

```bash
python -m lathe.asset_quality.preview_render examples\asset_quality\golden_industrial_crate
python -m lathe.asset_quality.preview_render examples\asset_quality\hero_sword
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode warning
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode strict
python -m lathe.cli asset-quality validate-example examples/asset_quality/hero_sword --mode warning
python -m lathe.cli asset-quality validate-example examples/asset_quality/hero_sword --mode strict
python -m lathe.cli asset-quality patch examples/asset_quality/hero_sword examples/asset_quality/hero_sword/patches/wider_blade.json --out .tmp_tests/hero_sword_patch_wider_blade
python -m lathe.cli asset-quality compare-before-after examples/asset_quality/hero_sword .tmp_tests/hero_sword_patch_wider_blade --out .tmp_tests/hero_sword_patch_wider_blade/comparison.json
python -m lathe.cli asset-quality validate-example .tmp_tests/hero_sword_patch_wider_blade --mode warning
python -m lathe.cli asset-quality validate-example .tmp_tests/hero_sword_patch_wider_blade --mode strict
python -m pytest -q tests/unit/test_asset_quality_phase14_examples.py tests/unit/test_asset_quality_certification.py
python -m pytest -q tests/unit/test_asset_quality_semantic_patch.py tests/unit/test_asset_quality_certification.py tests/unit/test_asset_quality_phase14_examples.py
git diff --check
```

## Next Phase Handoff

Phase 15 can promote these fixtures into CI/regression gates. Strict certification should remain opt-in until a real high/low bake producer generates the missing bake artifacts and the final strict blocker disappears. Future live-editing phases can use Phase 16's patch schema as the evidence contract while adding real rebuild and bake producers.
