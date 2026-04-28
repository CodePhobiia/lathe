# Product experience — v0.2.0rc1

**Version:** 0.2.0rc1 (pre-release reference compiler scaffold)
**Last reviewed:** 2026-04-28
**Owner:** Tal Merri (@talmerri)
**Reviewer:** requires-human (no second reviewer named yet)
**Host:** Windows 10 Home Single Language 10.0.19045, Python 3.13.13, `.venv`
under `D:\lathe_v0_1\.venv`.

This document captures Phase-7 product-experience evidence for the
v0.2.0rc1 readiness remediation pass: time-to-first-value (TTFV),
first-run friction, unhappy-path diagnostic quality, gallery / canonical-build
verification, viewer / engine validation, and accessibility / i18n posture.

It pairs with:

- [`docs/release/evidence-v0.2.0rc1.md`](evidence-v0.2.0rc1.md) — release-evidence index
- [`docs/release/decision-log-v0.2.0rc1.md`](decision-log-v0.2.0rc1.md) — non-goals,
  forbidden public claims
- [`docs/release/known-bugs-v0.2.0rc1.md`](known-bugs-v0.2.0rc1.md)
- [`docs/error_codes.md`](../error_codes.md) — semantic CLI error-code table

All evidence transcripts and copied build reports live under
[`docs/release/evidence-bundle-v0.2.0rc1/`](evidence-bundle-v0.2.0rc1/).

## Activation moment (TTFV)

The TTFV activation moment for v0.2.0rc1 is defined as:

> A user runs `lathe build examples/courier_drone.lth courier_drone --out tmp_ttfv`
> and observes `certified=true` in `tmp_ttfv/courier_drone/build_report.json`.

It composes three commands: `doctor` (env probe), `check` (parse), `build`
(full pipeline). The single deciding signal is the boolean `certified`
field on the resulting `build_report.json`.

## TTFV measurement

Captured 2026-04-28 on the Windows host described above. Raw transcript
(stdout + `time` output) is in
[`evidence-bundle-v0.2.0rc1/ttfv-windows.txt`](evidence-bundle-v0.2.0rc1/ttfv-windows.txt).

| step | command | wall-clock | notes |
|------|---------|-----------:|-------|
| 1 | `python -m lathe.cli doctor` | 46.305s | first call exercises shape-provider probes (`hunyuan2_1_http_v1`, `vggt_local_v1`, `reference_conditioned_v1`), Blender `--version` invocation, xatlas import. Most of the wall-clock is provider probing and the Blender subprocess. |
| 2 | `python -m lathe.cli check examples/courier_drone.lth` | 1.937s | parse + semantic checks; `ok=true`, no diagnostics. |
| 3 | `python -m lathe.cli build examples/courier_drone.lth courier_drone --out tmp_ttfv` | 3.733s | `certified=true`, `score=0.879435 ≥ threshold=0.86`, all stages green. |
| **total** | — | **~51.97s** | activation reached on first try. |

| host | TTFV | source |
|------|------|--------|
| Windows 10 (this run) | ~52s | direct measurement |
| macOS | requires-human | not measured here |
| Linux | requires-human | not measured here |

`requires-human:` macOS + Linux TTFV measurement (CI or maintainer host).

The first-run cost is heavily dominated by `doctor`. Once doctor has been
run, subsequent builds are <5s. This is acceptable for a pre-release
reference scaffold.

## First-run friction inventory

Walked the README install steps end-to-end on this Windows host. The
following decisions / clicks / requirements stand between a fresh user
and a certified build:

| friction | severity | recommendation |
|---|---|---|
| Bootstrap requires running `scripts/bootstrap_local.ps1 -Dev -Export` (or the bash equivalent) — no one-line `pipx install` path is available pre-PyPI. | medium | Document — already covered in README install section. The pre-PyPI status is a deliberate non-goal (`EXC-PHASE3-PYPI-TP-002`). |
| Optional-extras (Blender, xatlas, vggt, geometry) selection. README documents these as optional but a fresh user must read the table to decide whether to install them. Without them, the conservative offline path runs (still certifies). | low | Document — already in README "Optional dependencies" matrix. Accept. |
| `python -m lathe.cli` vs. `lathe` console-script: the latter requires the editable install to be active (`pip install -e .`). New shells without the venv activated must use `python -m lathe.cli`. | low | Document — both forms are listed in `CLAUDE.md` and `docs/canonical_commands.md`. Accept. |
| Visual Studio Build Tools requirement. xatlas / manifold3d / Pillow on Windows can require MSVC build tools when no wheel is available. The current pin (`xatlas>=0.0.11`) ships wheels for 3.11 + 3.12 on Windows; the venv on this host runs 3.13 and pulled `xatlas==0.0.11` successfully — so Build Tools were not needed in practice. | low | Document — README "Optional dependencies" should call out which extras require Build Tools on which Python version. `requires-human: confirm wheel availability matrix on PyPI for 3.11 + 3.12 across xatlas / manifold3d / scikit-image / torch.` |
| Runtime-config decision: a fresh user does NOT need a runtime config to certify a hero example — the conservative path is the default. The runtime-config affordance is only required to opt into Hunyuan HTTP, VGGT, or auto-learned modes. | low | Already correct. README and `docs/cli_reference.md` make this clear. Accept. |
| `lathe doctor` first-run time (~46s) is dominated by provider probing. A user with no network or Hunyuan server running gets a `Hunyuan health: unavailable (http://localhost:8081)` line followed by a recommended action. | low | Accept — the diagnostic is correct and the `requires-human:` recommended-action is `Start or fix the configured Hunyuan HTTP server`. Consider documenting expected wall-clock so first-run users do not assume the doctor is hung. |
| Output-path safety guard: `--out` is rejected if it resolves outside the working tree, unless `LATHE_ALLOW_EXTERNAL_OUT=1`. New users with the habit of building into `~/Desktop/...` or `C:\Temp\...` will hit this. The diagnostic includes an actionable next step. | low | Accept — diagnostic is good. README "First build" example uses an in-tree `dist/` path which avoids the trap. |
| Python-version drift: this host runs Python 3.13.13 in the venv even though `pyproject.toml` classifiers list 3.11 + 3.12 only. `requires-python = ">=3.11"` allows 3.13, but the support matrix and decision log explicitly say "Python 3.13 / 3.14 not supported". | medium | `requires-fix-before-launch:` reconcile. Either (a) bring the support matrix in line with the broader pin (`>=3.11` already permits 3.13), or (b) tighten the pin to `>=3.11,<3.13` to match the support matrix's promise. The current state is misleading. |
| Doctor's `Setup checks` block reports every check as "ok" with the negative-form description still attached (`virtualenv_active: ok (No active virtual environment was detected.)`). The mismatch is a minor UX defect. | low | `requires-human:` confirm whether the cosmetic mismatch is intentional. Not launch-blocking. |

Summary: the pre-first-asset path is short for the conservative offline flow.
The two friction items worth preserving as findings are the Python-version
support drift (`requires-fix-before-launch`) and the doctor cosmetic-mismatch
in the setup-check block (`requires-human` to triage).

## Unhappy-path walks

Captured 2026-04-28; raw stdout / stderr in
[`evidence-bundle-v0.2.0rc1/unhappy-paths.txt`](evidence-bundle-v0.2.0rc1/unhappy-paths.txt).

| # | path | command | exit | diagnostic-quality | recommendation |
|--:|------|---------|-----:|--------------------|----------------|
| 1 | Invalid `.lth` syntax | `lathe check tmp_uh/invalid.lth` | 1 | **good** — `lathe.cli.parse_error` code, `Unexpected token near: '!!! @@@ ###'`, source path, next-step. | PASS. |
| 2 | Certification failure | tried `examples/tutorial_bookshelf.lth bookshelf` | 0 | n/a — actually CERTIFIED (score=0.859565 ≥ threshold=0.82). | `requires-fix-before-launch:` `docs/examples_catalog.md` row marks `tutorial_bookshelf` cert column `x`, but the asset certifies. Catalog and reality disagree. **Also** `requires-human:` identify a stable intentional-cert-failure example for ongoing diagnostic-quality regression coverage — the repo currently has none under a documented "expected-to-fail" label. |
| 3 | Missing optional provider (Hunyuan HTTP server not running) | `lathe build … --runtime-config examples/runtime_configs/hunyuan_http.json --out tmp_uh/no_provider` | 1 | **good** — `lathe.cli.build.provider_fallback_blocked` code, full nested `diagnostics[0].details.probe` payload with `provider_id`, `base_url`, OS-level error (`WinError 10061`), and `underlying_code='request_failed'`. Output is JSON-shaped on stdout (machine-readable). | PASS. |
| 4 | Missing Blender | preflight: `where blender` returns `C:\…\WindowsApps\blender.cmd` and `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe`. Cannot remove for testing on this host. Ran `lathe build … --runtime-config examples/runtime_configs/offline.json --out tmp_uh/topology_default` to exercise the documented topology-fallback path. | 0 | **good** — `build_report.json.runtime_config.topology.adapter='reference_cleanup'` records the fallback adapter; `selected_backends.topology.id` keeps the stable contract `lathe.topology.blender_hard_surface_v1`. Build still certified=true. | PASS for graceful degradation. `requires-human:` rerun on a host where Blender is not on PATH to verify the diagnostic when the user did NOT explicitly opt into the reference fallback (i.e. wanted the real Blender adapter). |
| 5 | Missing xatlas | preflight: `import xatlas` succeeds (0.0.11). Cannot remove for testing on this host. Ran the same offline.json build to exercise UV-fallback path. | 0 | **good** — uv stage `provenance.runtime_adapter='reference_box'` alongside stable `backend_id='lathe.uv.xatlas_v1'`. Build certified=true. | PASS for graceful degradation. `requires-human:` rerun on a host without xatlas. |
| 6 | Provider timeout | (skipped per scope) | — | — | `requires-human:` provider-timeout requires a controlled environment with intentional latency (e.g. HTTP server that holds the connection open past the configured timeout). Not exercised in this pass. |
| 7 | Output path rejected by safety guard | `lathe build … --out C:/Windows/temp_uh_unsafe` | 2 | **good** — `lathe.cli.build.unsafe_out_path` code, message names the rejected path, next-step describes both remediations (move under cwd OR set `LATHE_ALLOW_EXTERNAL_OUT=1`). | PASS. |

Tally: **4 PASS** (UH-1, UH-3, UH-4, UH-5/UH-7 — counting fallback-quality
PASS), **0 improvable**, **0 poor**, **2 requires-human** (UH-2, UH-6) plus
the UH-2 `requires-fix-before-launch` catalog discrepancy.

`tmp_uh/` and `tmp_ttfv/` were removed after capture. `tmp_gallery_phase7/`
is left in place for the lead's inspection.

## CLI exit codes

[`docs/error_codes.md`](../error_codes.md) is comprehensive. Confirmed
coverage for the cases this phase requires:

| case | covered? | code |
|------|----------|------|
| success | yes | `0` (implicit; documented in exit-code table) |
| parse error | yes | `lathe.cli.parse_error` (exit 1) |
| check failure | yes | folded under `lathe.cli.error` (exit 1) — semantic checks raise `LatheError` which the top-level handler maps to this code |
| certification failure | yes — folded under `lathe.cli.build.build_failed` when the build reports `certified=false` AND repair rounds exhaust | `lathe.cli.build.build_failed` (exit 1). `requires-human:` confirm whether a `certified=false` outcome should keep exit 0 (build succeeded but did not certify) or exit 1 — `docs/error_codes.md` does NOT pin this distinction. |
| provider unavailable (strict) | yes | `lathe.cli.build.provider_fallback_blocked`, `lathe.cli.build.provider_failed` (both exit 1) |
| file not found | yes | `lathe.cli.file_not_found` (exit 2) |
| output safety reject | yes | `lathe.cli.build.unsafe_out_path` (exit 2) |
| usage error | yes | `lathe.cli.usage`, `lathe.cli.unknown_command` (both exit 2) |
| optional dep missing | yes | `lathe.cli.inspect.trimesh_missing` (exit 3) — exit 3 is the "optional-dep gap" lane |

`requires-human:` document the boundary case "build succeeded but did not
certify" — does the CLI exit 0 (build was honest) or exit 1 (cert is a hard
gate)? The current code path runs `lathe.cli.build.build_failed` only when
`BuildError` is raised, so a cert miss without exception is silent on exit
code. Pin this in `docs/error_codes.md` before launch.

### Machine-readable output schema

`lathe doctor --json` and the `--report json` build mode produce stable
top-level shapes, but **NO** explicit `schema_version` field is present:

- `build_report.json` top-level: `asset, kind, out_dir, certified,
  backend_stack, selected_backends, runtime_config, stage_bundles, outputs,
  manifest_path, trace_path, score, threshold, repair_rounds, optimize`.
  No `schema_version` / `version` key.
- `package_manifest.json` top-level: includes `version: "0.1.0"` (likely
  meant to be the manifest schema), but it is not labeled `schema_version`
  and the same key name is overloaded by other documents in the bundle.
- `lathe doctor --json` top-level: no `schema_version`.

`requires-human:` add an explicit `schema_version` (e.g.
`"lathe.build_report.v1"`) to `build_report.json`, `package_manifest.json`,
`trace_manifest.json`, and `lathe doctor --json` output **before**
agent-builder Persona C ratification. Stable schemas with no version field
are a compatibility risk for downstream agents that will pin against them.

## Gallery archive

Five canonical builds, all run from the worktree's `examples/` against a
clean `tmp_gallery_phase7/` output dir. Per-asset stdout / stderr / exit
captured into `evidence-bundle-v0.2.0rc1/gallery-build-NN.txt`.

| # | asset | command tail | exit | certified | score / threshold | full bundle? |
|--:|-------|--------------|-----:|-----------|-------------------|--------------|
| 1 | `industrial_crate` | `lathe build examples/industrial_crate.lth industrial_crate --out tmp_gallery_phase7/01-industrial_crate` | 0 | yes | 0.884666 / 0.84 | yes — all required artifacts present (build_report, selector_manifest, validate/report, package/{package_manifest, trace_manifest}, GLB, USD, 4 LODs, collision, previews, lathe-for-godot/-unity/-unreal sidecars). |
| 2 | `courier_drone` | `lathe build examples/courier_drone.lth courier_drone --out tmp_gallery_phase7/02-courier_drone` | 0 | yes | 0.879435 / 0.86 | yes — full bundle. |
| 3 | `courier_drone_mobile` | `lathe build examples/courier_drone.lth courier_drone_mobile --out tmp_gallery_phase7/03-courier_drone_mobile` | 0 | yes | 0.882625 / 0.82 | yes — full bundle. |
| 4 | `reconstruct_courier_from_views` | `lathe build examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views --out tmp_gallery_phase7/04-reconstruct` | 0 | yes | 0.878730 / 0.86 | yes — full bundle (reconstruct mode). |
| 5 | `console_terminal_mobile` | `lathe build examples/console_terminal_mobile_adapt.lth console_terminal_mobile --out tmp_gallery_phase7/05-console_terminal_mobile_adapt` | 0 | yes | 0.870164 / 0.82 | yes — full bundle (3 LODs, mobile-adapt budget). |

Durable evidence for each asset is copied to
`docs/release/evidence-bundle-v0.2.0rc1/gallery/<NN-asset>/`:
`build_report.json`, `package_manifest.json`, `trace_manifest.json`,
`validate-report.json`. GLB/USD/preview binaries are NOT copied — only the
JSON evidence is small enough to commit.

`requires-human:` archive gallery binaries (GLB, USD, lod_*, collision_*,
previews/, lathe-for-godot/-unity/-unreal sidecars) to a release-asset
bucket before public launch. The current evidence proves the JSON
artifact shape; binary playback / engine-import verification is downstream.

### Examples-catalog labeling drift

`docs/examples_catalog.md` has at least one row that does not match
observed cert behavior:

- `examples/tutorial_bookshelf.lth` — catalog row "Hero examples" marks
  `Cert='x'`. Observed: `bookshelf` certified=true (score 0.859565,
  threshold 0.82) on this host. **`requires-fix-before-launch:`** flip the
  catalog row to `Cert='o'` OR add a comment explaining why this asset is
  intentionally tracked as expected-to-fail despite passing.

Other rows marked `x` (`brassbound_chest_v13_blender.lth`,
`brassbound_chest_v13_1_codex_blender.lth`,
`console_terminal_v12_surface.lth`, `reconstruct_courier_from_views.lth`,
`satchel_bag.lth`, `service_corridor_wall.lth`) were not exercised in
this pass. `requires-human:` audit each row's cert column on a clean
build before launch.

The five canonical-build assets above are all marked supported (Cert='o')
in the catalog and pass on this host. Non-canonical examples are honestly
labeled "preview"/"experimental"/`x` per the table.

## Engine and viewer validation

External viewers and engines are out of scope for what this Phase-7 pass
can run on the local host. All entries below are `requires-human` for
manual verification on a host or pipeline appropriate to the tool.

### Mesh viewers

| viewer | scope | status |
|--------|-------|--------|
| glTF Sample Viewer (https://github.khronos.org/glTF-Sample-Viewer-Release/) | open `tmp_gallery_phase7/02-courier_drone/courier_drone/stages/package/courier_drone.glb` and the four LOD GLBs. Verify mesh / material / LOD render. | requires-human |
| Blender 4.x or 5.x | open the same GLBs via File → Import → glTF; verify materials and LOD groups. | requires-human |
| usdview (Pixar OpenUSD) | open `…/courier_drone.usda`. Verify hierarchy and bound materials. | requires-human |
| Houdini | open the same `.usda`. | requires-human |

### Godot smoke matrix

The Lathe Godot addon (`editors/godot/lathe-addon/`) and demo project
(`examples/godot_integration_demo/`) are documented as a manual-only
smoke. **The Godot addon is out of launch scope for v0.2.0rc1**, per
`docs/release/decision-log-v0.2.0rc1.md` non-goals: "Godot AssetLib
submission … does NOT [ship in this release]". This decision is
acknowledged here so reviewers do not mistake the manual-only matrix for
a launch blocker.

| os \ Godot version | Godot 4.3 | Godot 4.4 |
|---|---|---|
| Windows 10 / 11 | requires-human | requires-human |
| macOS 13+ | requires-human | requires-human |
| Linux (Ubuntu LTS) | requires-human | requires-human |

All 6 cells `requires-human:`. Manual procedure documented in
`editors/godot/lathe-addon/README.md` (or equivalent) and the demo project
under `examples/godot_integration_demo/`.

### Automated Godot test plan (stub)

`requires-human:` headless GUT (Godot Unit Test) automation plan. Open
items:

- pick a Godot binary distribution and pin its SHA in the dev-dependency
  matrix (Godot 4.3 LTS is the current stable target).
- write a `gut.cfg` that loads the addon, imports a known canonical GLB
  bundle (the `02-courier_drone` archive copied from
  `tmp_gallery_phase7/`), and asserts mesh / material / LOD invariants.
- wire a CI job that downloads the pinned Godot, runs `--headless --script
  res://addons/gut/gut_cmdln.gd -gtest=res://test/lathe_addon_test.gd`,
  and uploads the test report.
- gate the job on a label / dispatch (NOT every PR, since Godot is out of
  launch scope and the binary download is heavy).

This stub is written down only so the work is captured. It is not in the
v0.2.0rc1 launch path.

### Decision

**Manual-only Godot tests do NOT block public launch of v0.2.0rc1.**
Reason: the Godot addon ships in this release as alpha (V0.3 scope per
`docs/roadmap_public.md`) but submission to AssetLib is explicitly a
non-goal for v0.2.0rc1 (`docs/release/decision-log-v0.2.0rc1.md`).
Manual smoke quality is therefore not the launch quality bar; it is a
forward-looking-confidence signal for V0.3.

## Accessibility, internationalization, platforms

### Accessibility

Scope: CLI text + generated HTML reports + docs site (mkdocs-material).

- **CLI text accessibility** — text-only stderr / stdout, no ANSI
  required for content (color is TTY-aware via the standard library
  patterns in `lathe/cli/_common.py`). Screen readers should consume the
  output as plain text. `requires-human:` walk a screen-reader session
  through one full build invocation as a sanity check.
- **HTML report accessibility (axe-core / pa11y WCAG 2.2 AA audit)** —
  `lathe build … --report html` is the affected surface. Tool not
  installed on this host. **`requires-human:`** run `pa11y` or `axe`
  against a generated HTML report (e.g. `tmp_gallery_phase7/02-courier_drone/courier_drone/<report>.html`
  if the html report is captured) before public launch.
- **Docs site (mkdocs-material) keyboard-navigation + contrast audit** —
  not run in this pass. **`requires-human:`** keyboard-only navigation
  pass, contrast check (WCAG 2.2 AA) on the rendered docs site before
  public launch.

### Internationalization

Out of scope for v0.2.0rc1. Localization is not supported. Recorded as
non-goal-by-default — language surface, error messages, and docs are
English-only.

### Non-ASCII paths

Tested 2026-04-28 on this Windows host: created a directory named
`tmp_nonascii_тест` (Cyrillic), `cd`-ed into it, and ran
`python -m lathe.cli check ../examples/courier_drone.lth`. Result:
exit 0, `ok=true`, no diagnostics. Non-ASCII path support **works** for
the basic `check` command path. `requires-human:` repeat with a build
that writes outputs into a non-ASCII path (the `tmp_*` prefix in the
gitignore stripped, but the safety guard accepts any in-tree path), and
with a non-ASCII venv install location — those broader scenarios were
not exercised here.

### Platform matrix

| platform | tested in this pass? | source |
|----------|----------------------|--------|
| Windows 10 (3.13.13) | yes — TTFV + 7 unhappy paths + 5 gallery builds | direct |
| macOS 13+ | no | requires-human |
| Linux (Ubuntu LTS) | no | requires-human |

`requires-human:` macOS + Linux runs in CI before launch (the support
matrix promises 3.11 + 3.12 on Win/macOS/Linux).

### Python version support

`pyproject.toml` declares `requires-python = ">=3.11"`, classifiers list
`Programming Language :: Python :: 3.11` and `… 3.12` (3.13/3.14 are NOT
listed). `docs/release/decision-log-v0.2.0rc1.md` non-goals row says
"Python 3.13 / 3.14 not supported".

This host runs the venv on **Python 3.13.13** (because the `.venv/Scripts/python.exe`
points at the system Python 3.13 install). All evidence captured in this
pass therefore came from a Python version that the support matrix does
not promise. `requires-fix-before-launch:` reconcile by either tightening
the pin to `>=3.11,<3.13` (matches the support matrix) or by extending
classifiers + the support matrix to acknowledge 3.13 as a permitted
runtime. The current "permitted by `requires-python` but excluded by
classifiers + support matrix" state is misleading.

## Summary

- **TTFV (Windows):** ~52s for first-run; <5s for subsequent builds.
  certified=true on the courier_drone hero.
- **First-run friction:** 9 items inventoried; 1 `requires-fix-before-launch`
  (Python 3.13 support drift), 2 `requires-human` (cosmetic doctor mismatch,
  wheel-availability matrix audit). Remainder accept-as-documented.
- **Unhappy-path walks:** 4 PASS (good diagnostics), 2 `requires-human`
  (cert-failure example, provider-timeout host), 1 `requires-fix-before-launch`
  (catalog labeling drift on `tutorial_bookshelf`).
- **CLI exit codes:** comprehensive table in `docs/error_codes.md`, with
  one open question — exit-code semantics for "build succeeded but
  certified=false" — captured as `requires-human`.
- **Machine-readable output schema versioning:** no `schema_version` field
  on `build_report.json` / `package_manifest.json` / `lathe doctor --json`.
  `requires-human:` add before agent-builder Persona C ratification.
- **Gallery / canonical builds:** 5/5 PASS (cert=true, full artifact bundle).
  Durable JSON evidence copied to
  `docs/release/evidence-bundle-v0.2.0rc1/gallery/`; binaries left in
  `tmp_gallery_phase7/` for lead inspection. `requires-human:` archive
  binaries to release-asset bucket before public launch.
- **Engine + viewer validation:** all `requires-human` (need glTF Sample
  Viewer / usdview / Houdini / Godot host). Godot addon explicitly OUT
  of v0.2.0rc1 launch scope per decision-log; manual-only matrix does
  NOT block launch.
- **A11y / i18n / platforms:** docs-site WCAG audit, HTML-report axe/pa11y,
  macOS / Linux runs all `requires-human`. i18n is out of scope by
  decision. Non-ASCII path test PASS on Windows for `lathe check`.

## Pre-release language reminder

This document reflects v0.2.0rc1 readiness state on 2026-04-28. v0.2.0rc1
is a pre-release reference compiler scaffold. Forbidden public claims
(see `docs/release/decision-log-v0.2.0rc1.md` "Public claims that must
NOT be made") apply to all material derived from this evidence pack.
