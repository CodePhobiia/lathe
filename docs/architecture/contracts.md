# Public contracts and internal boundaries

This page is the reference map for what downstream users and out-of-tree
integrations may rely on. Anything listed as **public** needs a migration plan
before it changes. Anything listed as **internal** may be refactored as long as
the public contract above it stays compatible.

## Public contract surfaces

| Surface | Ground truth | Compatibility rule |
|---|---|---|
| Lathe source language | `spec/lathe-v0.1.md`, `grammar/lathe.lark`, `schema/lathe.schema.json`, parser, normalizer, resolver, checker | Keep existing `.lth` source valid unless a language-version migration explicitly breaks it. Changes to `profile`, `contract`, `critic`, `asset`, `variant`, and build-stage names must update all language layers together. |
| Backend and stack identifiers | `lathe/backends.py` `BACKENDS` and `STACKS` plus `pyproject.toml` entry points | Stable IDs are append-only within a major version. Breaking behavior gets a new ID such as `_v2`, with old and new IDs coexisting during migration. |
| Shape handoff | `lathe.shape.intent_mesh_handoff_v1` in `lathe/backends.py`, runner in `lathe/shape/backend.py`, contract pin in `tests/contract/test_shape_handoff_v1.py` | This is the single probabilistic handoff. Do not mutate v1 in place; add a new contract ID and a new contract test for a breaking change. |
| Shape providers | `lathe/providers/registry.py`, `lathe/providers/selection.py`, `schema/runtime_config.schema.json`, entry-point group `lathe.providers.shape` | Provider descriptors and runtime config keys are public selection inputs. Providers may fail or fall back, but attempted and actual provider IDs must be traceable. |
| Stage order and stage bundles | `lathe/executor.py` `STAGE_ORDER`, `lathe/core/stages/*`, package trace in `lathe/core/stages/package.py` | Stage names and handoff bundle files are observable through traces and reports. Additive fields are preferred; removals or semantic rewrites require a migration. |
| Validation reports | `lathe/core/stages/validate.py`, `lathe/validators/composition.py`, validator entry-point group `lathe.validators` | Report keys consumed by reports, package traces, and CLI output remain stable. New validators must preserve gate/score semantics and diagnostics shape. |
| Build and package reports | `build_report.json`, `stages/package/package_manifest.json`, `stages/package/trace_manifest.json`, `schema/publish_manifest.schema.json`, `schema/reproducibility_receipt.schema.json` | These artifacts are user-facing. Schema-versioned artifacts increment their schema version for breaking changes and stay readable during the deprecation window. |
| Selector, budget, collision manifests | `schema/lathe.selector.schema.json`, `schema/budget_manifest.schema.json`, `schema/collision_manifest.schema.json` | `schemaVersion` is the compatibility boundary. Breaking shape changes require a schema-version bump and fixture/schema validation updates. |
| Engine manifests | `lathe/engine_manifests/*`, entry-point group `lathe.engine_manifest`, package bundle `engine_manifests` entries | Sidecar filenames, engine IDs (`godot`, `unity`, `unreal`), and `schemaVersion: 1` payloads are public engine handoff. Breaking payload changes need a new schema version and docs. |
| Report renderers | `lathe/reports/__init__.py`, `lathe/reports/terminal.py`, `lathe/reports/html.py` | Renderers consume `build_report.json`; they must not require internal runtime-only fields that are absent from persisted reports. |

## Internal implementation boundaries

The following modules are implementation detail, not downstream API:

- `lathe/core/stages/*` function bodies. The stage names and emitted bundles are
  public; helper functions and local runtime dict structure are internal.
- `lathe/shape/geometry/*`, `lathe/scaffold_compiler.py`,
  `lathe/feature_fusion.py`, and other shape-kernel helpers. The public boundary
  is the shape bundle under `lathe.shape.intent_mesh_handoff_v1`.
- `lathe/providers/adapters/*` and `lathe/providers/transport/*`. The public
  boundary is the provider descriptor, runtime config schema, and provider
  report. Adapter call signatures may change.
- `lathe/reports/html.py` and `lathe/reports/terminal.py` rendering internals.
  The public API is `write_report`, `render_terminal_report`,
  `render_html_report`, and the persisted report files.
- `lathe/engine_manifests/godot.py`, `unity.py`, and `unreal.py` emitter
  internals. The public boundary is the registered engine ID, sidecar filename,
  and manifest payload version.

Docs outside `docs/architecture/` should describe user-facing behavior and link
to this page or to schema files. They should not instruct downstream consumers
to import private helpers, parse transient in-memory runtime dictionaries, or
depend on non-schema implementation details.

## Migration checklist

Use this checklist before changing any public contract surface:

1. Identify the public surface and decide whether the change is additive or
   breaking under `docs/versioning.md`.
2. For language changes, update `spec/lathe-v0.1.md`, `grammar/lathe.lark`,
   `schema/lathe.schema.json`, parser/normalizer/resolver/checker behavior,
   examples, and tests in the same change.
3. For backend, provider, stage, validation, report, or manifest changes, add a
   new versioned ID or `schemaVersion` when compatibility breaks.
4. Keep old and new contracts side by side for at least one minor release when a
   downstream migration is required.
5. Add or update a contract test that would fail if the old surface drifted
   accidentally.
6. Update the relevant architecture page, ADR, schema docs, and examples so
   downstream docs point at public surfaces only.

## Contract test coverage

The strongest current tripwire is
`tests/contract/test_shape_handoff_v1.py`, which pins the shape handoff field
set and canonical hash. Other public artifacts are covered by schema validation,
runtime-config docs checks, static docs checks, and focused unit tests. When a
new public contract becomes load-bearing for downstream users, add a contract
test next to `tests/contract/` rather than relying on broad integration tests
alone.
