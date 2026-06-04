# Lathe Web Studio (web/)

Browser-side product surface for Lathe. Two workspaces:

- `web/lathe-three/` — `@lathe/three` npm package. Loads `.lthpkg`
  packages produced by `lathe.asset_foundry.package_writer` and
  decorates a Three.js `Object3D` with Lathe's semantic sidecars
  (parts, sockets, materials, diagnostics, provenance, certificate,
  runtime evidence).
- `web/lathe-web-viewer/` — Vite-based browser viewer that uses
  `@lathe/three` to render and inspect packages.

## Status

`v0.1.0` — minimal viable surface per
`docs/product/three-lth-lathe-web-studio-v1-product-path.md` Phase B + C.

What's wired:

- `@lathe/three` parses every `.lthpkg` sidecar with strict version
  + type checking.
- The loader returns a Three.js `Object3D` plus the full semantic
  sidecar set as a typed `LatheThreeResult`.
- The web viewer renders the asset + side panel showing asset meta,
  semantic parts, material slots, diagnostics, quality certificate.
- Drag/drop a URL string pointing at a hosted `.lthpkg` directory.
- View-mode toggles (Render / Wireframe / Material IDs / Normals)
  are wired at the UI level; mode switching is currently a no-op
  pending material-override pass on the loaded Three.js mesh.

What's deferred:

- Phase D (repair loop): semantic-patch action → rebuild → before/
  after diff. Requires server-side build orchestration that the
  Foundry's `write_lthpkg` produces but no in-browser trigger yet.
- Phase E (Playground/Studio): in-browser `.lth` editor + compile/
  build trigger.
- Kit browser, micro-scene inspector, hero diorama review,
  playability overlay — the Phase 2-5 viewer modes from
  `North Star/lathe-floating-fantasy-world-northstar.md`.

## Build

```bash
cd web/lathe-three
npm install
npm run build

cd ../lathe-web-viewer
npm install
npm run dev
```

The viewer expects `.lthpkg` packages served from a static directory.
The Foundry's `write_lthpkg` produces the package layout the loader
consumes.

## Contract versions

| Layer | Version |
|---|---|
| `.lthpkg` | `lathe.asset_foundry.lthpkg_v1` |
| `@lathe/three` | `0.1.0` |
| `lathe-web-viewer` | `0.1.0` |

When the Python contract version bumps, the TypeScript packages bump
in lockstep.

## Non-goals

- Do not fork three.js. We import from `three` peer dependency only.
- Do not invent semantics. Everything in `userData.lathe` came from
  the Lathe-side `.lthpkg`.
- Do not hide weak geometry with renderer tricks. When `mesh.glb` is
  unbuilt, the loader produces a labeled proxy and the diagnostics
  panel surfaces the reason.
