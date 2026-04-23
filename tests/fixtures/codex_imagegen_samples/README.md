# Codex ImageGen sample fixtures

Tiny placeholder PNG assets used by `mock_codex_imagegen.mock_codex_bridge`
to stand in for real Codex-generated textures.

These are **deliberately trivial** (4x4 gray or flat-color PNGs) — they
exist only so downstream bake/surface paths have a valid file to open.
Do **not** add large or content-heavy fixtures here; golden snapshots
live under `tests/golden/__snapshots__/` instead.

Files:

- `placeholder.png` — minimal 4x4 gray PNG, used as the default stub
  return for all ImageGen calls when a test does not override the map.

Wave 3 may add per-map-type placeholders (e.g. `basecolor.png`,
`normal.png`) with the matching channel semantics; keep them small.
