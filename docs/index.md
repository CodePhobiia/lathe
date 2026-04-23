# Lathe

**Lathe** is a declarative language and reference compiler/runtime for 3D asset intent. Source `.lth` files describe *what* an asset is, *how* to build it, and *what counts as passing*. The compiler produces certified production-ready asset packages (`usd` / `glb` / `gltf` / `obj`).

Scaffolded nav:

- [Quickstart](quickstart.md) — 60-second first build (filled in Wave 3).
- [Tutorial](tutorial/index.md) — author your first `.lth` asset (filled in Wave 3).
- [Architecture overview](architecture/overview.md) — system context + container view.
- [Pipeline](architecture/pipeline.md) — stage-by-stage flow.
- [Shape stage](architecture/shape_stage.md) — the single probabilistic stage.
- [Backends](architecture/backends.md) — stack bindings and fallback semantics.
- [API Reference](api/cli.md) — generated from docstrings.
- [Versioning](versioning.md) — semver + stable contract IDs.
- [Dependency policy](dependency_policy.md) — `uv lock` cadence.
