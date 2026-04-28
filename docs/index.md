# Lathe

**Lathe** is a declarative language and reference compiler/runtime for 3D asset intent. Source `.lth` files describe *what* an asset is, *how* to build it, and *what counts as passing*. The compiler produces certified production-ready asset packages (`usd` / `glb` / `gltf` / `obj`).

Scaffolded nav:

- [Quickstart](quickstart.md) — 60-second first build (filled in Wave 3).
- [Canonical commands](canonical_commands.md) - normalize, check, plan,
  materialize, build, cache, provider, and diagnostic commands.
- [Troubleshooting](troubleshooting.md) - common parse, ref, provider,
  Blender, xatlas, cache, artifact, and certification failures.
- [Product value](product_value.md) - positioning, user journeys, smallest
  lovable workflow, roadmap priority, extension story, and success metrics.
- [Canonical gallery](gallery.md) - flagship product workflow, canonical
  assets, acceptance criteria, and limitations.
- [Tutorial](tutorial/index.md) — author your first `.lth` asset (filled in Wave 3).
- [Architecture overview](architecture/overview.md) — system context + container view.
- [Pipeline](architecture/pipeline.md) — stage-by-stage flow.
- [Shape stage](architecture/shape_stage.md) — the single probabilistic stage.
- [Backends](architecture/backends.md) — stack bindings and fallback semantics.
- [API Reference](api/cli.md) — generated from docstrings.
- [Versioning](versioning.md) — semver + stable contract IDs.
- [Dependency policy](dependency_policy.md) — `uv lock` cadence.
- [Language reference](language_reference.md) - generated from the current
  grammar, schema, and defaults.
- [Schema reference](schema_reference.md) - normalized AST fields, defaults,
  and validation rules.
- [Quality dashboard](quality_dashboard.md) - current 10/10 scores, owners,
  evidence, and release blockers.
- [Maintenance and triage](maintenance.md) - labels, milestones, stale policy,
  dependency updates, and release metrics.
- [Review requirements](review_requirements.md) - required review evidence for
  language, provider, security, and release changes.
- [Security policy](https://github.com/talmerri/lathe/blob/main/SECURITY.md) - vulnerability reporting, response SLA,
  safe harbor, and supported versions.
- [Release quality](release/index.md) - release gates, support matrix,
  exceptions, limitations, and regression-test policy.
