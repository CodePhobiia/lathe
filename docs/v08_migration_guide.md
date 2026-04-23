# Lathe V0.8 Migration Guide

V0.8 is additive.

## Compatibility

Old source still works unchanged.

Pre-V0.8 assets that only use:

- `profile`
- `contract`
- `critic`
- `asset`
- `variant`

continue to parse, normalize, check, materialize, and build without migration.

## What changes in V0.8

You can now move stable product logic from hidden runtime code into source by adding:

- reusable `family` declarations
- reusable `component` declarations
- reusable `material` / `palette` declarations
- source-visible `space` declarations
- source-visible `repair_policy` declarations
- source-level `test` / `benchmark` declarations

## Recommended migration pattern

1. Keep the existing asset source valid.
2. Extract repeated family logic into `std/families/*.lth`.
3. Extract part semantics into `std/components/*.lth`.
4. Extract hero material definitions into `std/materials/*.lth` and `std/palettes/*.lth`.
5. Add a `space` declaration for search behavior instead of keeping search intent hidden in runtime code.
6. Add a `repair_policy` declaration for reusable repair posture.
7. Add at least one `test` and one `benchmark`.

## Example migration rule

Pre-V0.8:

```lathe
asset brassbound_chest: hard_surface_prop uses shipping_prop {
  intent {
    role = "ornate brassbound loot chest"
  }

  build {
    shape {
      mode = generate
      candidates = 6
    }
  }
}
```

V0.8 additive migration:

```lathe
import std.families.brassbound_chest

asset brassbound_chest: hard_surface_prop uses shipping_prop {
  intent {
    role = "ornate brassbound loot chest"
  }

  geometry {
    seam_classes = [panel_seam, lid_break, clasp_cut]
  }

  features {
    density = hero
  }

  surface {
    palette = fantasy_brassbound
  }

  assembly {
    family = brassbound_chest_family
  }

  space {
    use = chest_hero_search
  }

  repair_policy {
    use = hero_hardsurface_repair
  }

  build {
    shape {
      mode = generate
      candidates = 6
    }
  }
}
```

## Current limitations

- `lathe fmt` does not yet rewrite source text canonically.
- `lathe patch` currently emits normalized JSON after structural changes; it does not yet rewrite `.lth` text directly.
- the new declaration set is broader than the current runtime lowering. The strongest active lowering today is for:
  - `family`
  - `component`
  - `material`
  - `palette`
  - `space`
  - `repair_policy`
  - `fixture`
  - `test`
  - `benchmark`

The other declarations are present in the grammar/AST and ready for deeper lowering work in later milestones.
