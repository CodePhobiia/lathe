# Marker Inventory

This file tracks the remaining `TODO`, `FIXME`, `HACK`, `placeholder`, `stub`,
and `NotImplemented` markers in active repo surfaces. The companion test
`tests/unit/test_marker_inventory.py` fails if a new marker appears under
`.github/`, `docs/`, `lathe/`, `scripts/`, or `docker/` without being listed
here and in its allowlist.

Historical planning files under `plans/` and test fixtures under `tests/` are
excluded from the production marker gate. They intentionally preserve old review
notes, fake servers, and test doubles.

## Active Markers

| Path | Marker | Reason | Next action |
|---|---|---|---|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | `placeholder: "0.1.0"` | GitHub issue-form sample value. | Keep until issue forms are redesigned. |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | `placeholder: "3.11.9"` | GitHub issue-form sample value. | Keep until issue forms are redesigned. |
| `.github/ISSUE_TEMPLATE/release_blocker.yml` | `placeholder: "v0.2-rc-hardening"` | GitHub issue-form sample value. | Keep until issue forms are redesigned. |
| `docs/next_version_roadmap.md` | `stub backend IDs` | Honest roadmap limitation for rig/interfaces/physics/optimize semantics. | Replace when backend IDs migrate through a compatibility plan. |
| `docs/next_version_roadmap.md` | `symbol-index stub` | Honest roadmap limitation for the LSP. | Replace when full LSP support lands. |
| `docs/plan_completeness.md` | `lathe/lsp/ is a stub` | Honest status note for unfinished LSP work. | Replace when Plan 05 Phase 7 lands. |
| `docs/release/asset-provenance.md` | `placeholder.png` | Real test fixture name and provenance record. | Keep while fixture exists. |
| `docs/security/ci_gates.md` | `placeholder (e.g. your-api-key-here)` | Security docs explain secret-scanner examples to reject. | Keep. |
| `docs/templates/gallery_index.html.j2` | `.placeholder` | CSS class for the intentional no-render gallery state. | Keep unless gallery UX is renamed. |
| `lathe/mesh_ingest.py` | `NotImplementedError` | Explicitly caught third-party mesh-loader exception type, not unimplemented Lathe code. | Keep covered by mesh ingress tests. |
| `scripts/render_gallery.py` | `no_blender.txt placeholder` | Intentional fallback artifact when Blender is unavailable. | Keep unless gallery renderer gains a real non-Blender preview. |
| `scripts/render_gallery.py` | `<div class="placeholder">` | Intentional no-render gallery UI. | Keep unless gallery UX is renamed. |
