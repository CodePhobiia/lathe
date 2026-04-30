# LLM authoring: Phase 13 experimental syntax

## When to use

Use this guide when generating `.lth` source that needs author-level
control over the Phase 2 design brief, the Phase 11 reference board
override, or the Phase 12 kit-library declaration. The wrapper is
optional — assets that omit `experimental { }` keep the Phase 12
defaults.

## Authoring rules

1. **Wrap everything** under exactly one `experimental { ... }` block at
   the asset level. Sibling sub-blocks (`art_direction`, `references`,
   `kit`) are opt-in and may appear in any order. There is no other
   place in the asset where these blocks parse.

2. **Stable surface unchanged.** Do not move stable blocks
   (`intent`, `geometry`, `surface`, `build`, `validate`, `package`,
   `publish`, ...) inside `experimental { }`. The wrapper is purely
   additive on top of the existing asset shape.

3. **Use `=` for assignments.** All Phase 13 fields follow Lathe's
   normal assignment syntax (`field = value`). Strings use double
   quotes; lists use `[...]`.

4. **Stay in the whitelist.** Only the four MVP `art_direction` fields
   parse and check cleanly:
   - `style_tags = [<string>, ...]`
   - `wear = "<string>"`
   - `material_age = "<string>"`
   - `detail_density = "<string>"`
   Unknown fields surface as `L7101` errors, even though the parser
   tolerates them.

5. **Use `<category>.<name>` for kit parts.** The MVP kit categories
   are `fasteners`, `corner_guards`, `handles`, `rails`,
   `warning_labels`. Each entry must match an existing part file under
   `std/kits/hardsurface/<category>/<name>.json`.

6. **Resolve `references.use` relative to the source.** The path lives
   alongside the `.lth` file. The loader probes a single directory; do
   not include trailing slashes or filenames.

## Good output

```lathe
asset industrial_crate: hard_surface_prop from industrial_crate_family uses shipping_prop {
  intent {
    role = "reinforced industrial cargo crate"
    style = ["utility", "industrial", "shipping"]
  }

  // ... stable asset blocks ...

  experimental {
    art_direction {
      style_tags = ["weathered_industrial", "well_used"]
      wear = "heavy"
      material_age = "aged"
      detail_density = "high"
    }
    references {
      use = "refs/asset_quality/industrial_crate"
    }
    kit {
      use = ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]
    }
  }
}
```

## Bad-output examples and repair playbook

The repair-playbook entries are keyed to the `L7100`-`L7105`
diagnostic codes. Each entry shows the bad output, the expected error,
and the minimal fix.

### L7100 — unknown sub-block

Bad output:

```lathe
experimental {
  construction {
    build = "modular"
  }
}
```

Diagnostic: `L7100 experimental_unknown_subblock — Asset 'crate' experimental sub-block 'construction' is not recognized in the Phase 13 MVP`.

Repair: remove the `construction { ... }` block, or move its content
into a stable asset block. Phase 13 only accepts `art_direction`,
`references`, and `kit`.

### L7101 — `art_direction` unknown field

Bad output:

```lathe
experimental {
  art_direction {
    silhouette = "bold"
  }
}
```

Diagnostic: `L7101 experimental_art_direction_unknown_field — Asset 'crate' experimental.art_direction field 'silhouette' is not in the Phase 13 MVP whitelist`.

Repair: drop the field or replace it with one of the four whitelist
fields (`style_tags`, `wear`, `material_age`, `detail_density`).

### L7102 — `art_direction` invalid value

Bad output:

```lathe
experimental {
  art_direction {
    wear = 42
    style_tags = "weathered_industrial"
  }
}
```

Diagnostics:
- `L7102 — Asset 'crate' experimental.art_direction.wear must be a string`.
- `L7102 — Asset 'crate' experimental.art_direction.style_tags must be a list of strings`.

Repair: quote the string and wrap the tag in a list.

```lathe
experimental {
  art_direction {
    wear = "heavy"
    style_tags = ["weathered_industrial"]
  }
}
```

### L7103 — `references.use` invalid path

Bad output:

```lathe
experimental {
  references {
    use = "refs/missing"
  }
}
```

Diagnostic: `L7103 experimental_references_invalid_path — Asset 'crate' experimental.references.use path 'refs/missing' does not resolve to an existing directory`.

Repair: confirm the path resolves relative to the source `.lth`.
Phase 11 fixtures live under `examples/refs/asset_quality/<name>`.

### L7104 — `kit.use` unknown part

Bad output:

```lathe
experimental {
  kit {
    use = ["fasteners.does_not_exist"]
  }
}
```

Diagnostic: `L7104 experimental_kit_unknown_part — Asset 'crate' experimental.kit.use entry 'fasteners.does_not_exist' is not present in the loaded kit library`.

Repair: drop the entry or replace it with a name that exists under
`std/kits/hardsurface/<category>/`.

### L7105 — `kit.use` invalid format

Bad output:

```lathe
experimental {
  kit {
    use = "fasteners.hex_bolt_m6"
  }
}
```

Diagnostic: `L7105 experimental_kit_invalid_format — Asset 'crate' experimental.kit.use must be a list of strings`.

Repair: wrap the value in a list, even when there is only one entry.

```lathe
experimental {
  kit {
    use = ["fasteners.hex_bolt_m6"]
  }
}
```

Bad output (entry without dot):

```lathe
experimental {
  kit {
    use = ["hex_bolt_m6"]
  }
}
```

Diagnostic: `L7105 — Asset 'crate' experimental.kit.use entry 'hex_bolt_m6' must use the '<category>.<name>' format`.

Repair: prefix the entry with its category, e.g.
`"fasteners.hex_bolt_m6"`.

## Checklist before emitting

- Is the `experimental` wrapper at the ASSET level (not nested in
  `intent` / `surface` / `build`)?
- Is each sub-block one of `art_direction`, `references`, `kit`?
- Are all `art_direction` fields in the four-field whitelist?
- Are all string values double-quoted? Are all lists wrapped in `[...]`?
- Does each `kit.use` entry follow `<category>.<name>` format?
- Does the `references.use` path exist relative to the source `.lth`?
