# `web/playground/` — Lathe in-browser playground (proof-of-concept)

This directory holds the Wave 4.IV.f static landing page for the
in-browser Lathe playground. The full Pyodide-hosted compiler is
**not yet built** — this is the architecture sketch + the static page
that will be replaced when the wheel-build lands.

## Current state (Wave 4.IV.f)

- `index.html` — static concept page. Describes what the playground is
  for, what is and is not yet shipped, and links to the live repo
  + docs. Self-contained (no external JS).

That is everything. There is no compiler, no editor, no model-viewer.

## What the full playground will be (Plan 08 Phase 12)

```
+-------------------------------------------------------------+
|  Monaco editor   |   Build console   |   model-viewer       |
|  (.lth source)   |   (lathe stdout)  |   (USDZ / GLB live)  |
+-------------------------------------------------------------+
|  Pyodide WebAssembly runtime (browser)                      |
|    - lathe wheel (pure-Python, vendored deps)               |
|    - micropip-installable on first load                     |
+-------------------------------------------------------------+
```

Concretely, landing the full playground requires:

1. **Pyodide-compatible wheel build** for `lathe`. Today's
   `pyproject.toml` pulls in `numpy`, `trimesh`, `scipy`, `xatlas`,
   `Pillow`, `lark` etc. — most have Pyodide-precompiled sidecars; a
   subset (e.g. `xatlas`, optionally `Blender bridge`) does not. The
   playground will run **in degraded mode**: shape + topology fallback
   paths only, no Blender execution, no Codex bridge. This matches the
   conservative path the CLI already takes when those tools are absent
   (see `CLAUDE.md` § "Provider/runtime wiring").
2. **Wheel hosting** — either GitHub Pages or a CDN, served with a
   `pyodide-pinned` `package.json` so version drift is impossible.
3. **Monaco editor** with a hand-rolled tokenizer for the Lathe grammar
   (the existing `grammar/lathe.lark` is the single source of truth;
   `lathe.lsp` already has the keyword set).
4. **`<model-viewer>`** for the GLB output. USD support in browsers
   ships through Apple's `<model-viewer>` USDZ pipeline.
5. **Static example library** populated from `examples/*.lth` so a
   first-time visitor sees a hero compile in <2s.

## Why deferred

Plan 08 Phase 12 budgets the playground at 2.5 weeks of focused work.
Wave 4.IV.f is a **single-day proof-of-concept slice**; it would be
dishonest to ship a half-working in-browser compiler under the same
banner. The static page is shipped now so the URL stops 404-ing in
docs links; the compiler arrives in Wave 5+.

## Refresh / preview

```bash
# Serve locally
python -m http.server --directory web/playground 8765
# then open http://localhost:8765
```

## Pointers

- Plan: `plans/08_product_quality.md` Phase 12 — full spec.
- Current Lathe CLI surface (mirrored by future browser host):
  `python -m lathe.cli check | plan | materialize | build`.
- Conservative-path stage fallbacks (the in-browser default):
  see `CLAUDE.md` for the runtime config matrix.
