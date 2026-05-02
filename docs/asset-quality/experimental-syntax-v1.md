# Experimental syntax v1 — Phase 13

## Overview

Phase 13 of the asset-quality upgrade exposes selected internals as
public `.lth` controls behind a single, explicit `experimental { ... }`
wrapper. The stable public surface — `profile`, `contract`, `critic`,
`asset`, `variant`, plus the build-stage names — is unchanged. The
wrapper is additive: omitting it keeps Phase 12 behavior identical.

This document is the per-feature reference for the three Phase 13 MVP
sub-blocks, the diagnostic codes (`L7100`-`L7105`), and the migration
expectations from pre-Phase-13 sources.

## Stability promise

- The stable public surface (`profile`, `contract`, `critic`, `asset`,
  `variant`, build-stage names) does NOT change as a side effect of
  Phase 13.
- Existing examples and tests pass without modification.
- Sub-blocks inside `experimental { }` are NOT defaulted by the
  normalizer — only present when the user wrote them.
- Phase 13 sub-blocks may evolve between minor versions.
- Total of 26 top-level validate report keys is preserved. User opt-in
  surfaces as `user_provided_via_experimental` annotations inside the
  existing `design_brief`, `reference_board`, and `kit_library` evidence
  sections.

## Gating model

```lathe
asset crate: hard_surface_prop {
  // ... stable asset blocks (intent, geometry, build, validate, ...)

  experimental {
    // OPT-IN sub-blocks live here.
  }
}
```

The `experimental` wrapper is OPTIONAL. Without it, the asset behaves
exactly as in Phase 12. Only `art_direction`, `references`, and `kit`
sub-blocks are recognized in the MVP; any other identifier inside
`experimental { ... }` is tolerated by the parser but flagged by the
checker as `L7100`. Variants that patch `experimental.*` are checked
after materialization and receive the same diagnostics as authored
assets.

## MVP sub-blocks

### `art_direction { ... }`

Overrides the Phase 2 design-brief defaults for the four whitelisted
fields. Unspecified fields keep the family-default value.

```lathe
experimental {
  art_direction {
    style_tags = ["weathered_industrial", "well_used"]
    wear = "heavy"
    material_age = "aged"
    detail_density = "high"
  }
}
```

Whitelist (MVP): `style_tags`, `wear`, `material_age`, `detail_density`.
Other Phase 2 brief fields are NOT exposed; the checker reports
`L7101` for unknown fields.

When provided, the design-brief evidence carries
`user_provided_via_experimental: { "fields": [...] }` listing the fields
that were overridden.

### `references { use = "<path>" }`

Overrides the executor's reference-board base path. The path is
resolved relative to the source `.lth` file (mirrors `import` resolution).

```lathe
experimental {
  references {
    use = "refs/asset_quality/industrial_crate"
  }
}
```

The reference-board evidence carries
`user_provided_via_experimental: true` whenever the override drives the
loader, independent of whether the load succeeded. `references` only
accepts `use` plus the internal `_resolved_path`; extra fields are
reported as `L7103`.

### `kit { use = [<part>, ...] }`

Author-declared hard-surface kit parts. Each entry uses the
`<category>.<name>` format and is validated against the loaded kit
library at check time.

```lathe
experimental {
  kit {
    use = ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]
  }
}
```

The kit-library evidence carries
`user_provided_via_experimental: { "declared_parts": [...] }`. Phase 13
does NOT filter the loaded library by the declared list — the
declaration is informational evidence only. Each declared part must be
allowed for the materialized asset family: a part whose
`allowed_families` lacks that family and lacks `"*"` reports `L7106`.
`kit` only accepts `use`; extra fields report `L7105`.

## Diagnostic codes

| Code   | Name                                             | Severity | Trigger                                                                              |
|--------|--------------------------------------------------|----------|--------------------------------------------------------------------------------------|
| L7100  | experimental_unknown_subblock                    | error    | A sub-block other than `art_direction`/`references`/`kit` appeared inside `experimental { }`. |
| L7101  | experimental_art_direction_unknown_field         | error    | A field outside the four-field MVP whitelist appeared in `art_direction`.            |
| L7102  | experimental_art_direction_invalid_value         | error    | A field's value type is wrong (e.g. `wear: 42`, `style_tags: "weathered"`).          |
| L7103  | experimental_references_invalid_path             | error    | `references.use` is not a string, or it does not resolve to an existing directory.   |
| L7104  | experimental_kit_unknown_part                    | error    | A kit-use entry is not present in the loaded kit library. Warning when the library cannot load. |
| L7105  | experimental_kit_invalid_format                  | error    | A kit-use entry is malformed (non-string, missing dot, not exactly `<category>.<name>`). |
| L7106  | experimental_kit_disallowed_family               | error    | A kit-use entry exists but its `allowed_families` excludes the materialized asset family. |

Every diagnostic carries `suggested_repairs` — at least one short
actionable string per code — so authors and LLM-based authors can
repair from evidence alone.

## Forward references (reserved)

The following sub-blocks are reserved for forward phases. They will
land additively under the same `experimental { }` wrapper without
changing the stable public surface:

- `construction { ... }` — explicit semantic construction graph hints.
- `material_graph { ... }` — overrides for the Phase 7 wear/material graph.

## See also

- `docs/asset-quality/llm-authoring-experimental-syntax.md` — LLM
  authoring guidance with bad-output examples.
- `docs/asset-quality/phase13-experimental-syntax-migration.md` —
  migration notes for pre-Phase-13 sources.
