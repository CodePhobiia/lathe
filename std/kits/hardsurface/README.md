# Standard Hard-Surface Kit Library (Phase 12 internal)

This directory holds the Phase 12 deterministic hard-surface kit
library used by `lathe.asset_quality.kit_library.load_kit_library`. It
is NOT a user-facing language surface — there is no `kit { }` block in
`.lth` in v0.2. User-facing kit syntax is reserved for Phase 13. The
JSON files here conform to `schema/kit_part.schema.json` and are loaded
by the executor before the validate stage runs.

The MVP covers five categories: `fasteners/`, `corner_guards/`,
`handles/`, `rails/`, and `warning_labels/`. Every fixture in Phase 12
uses `"kind": "procedural"` — Phase 12 ships descriptor-only data, no
real meshes.
