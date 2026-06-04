# Cycle 3 generator + decorator inventory

Plan v2 §6.3 generator/decorator completion stream targets:

- **20 hard-surface NODE_TYPE generators** (≤300 lines each, no stubs)
- **7 EDGE_TYPE decorators**

## Current state (2026-05-11 audit)

### Generators (`lathe/asset_quality/procedural_synthesizer/generators/hard_surface/`)

| NODE_TYPE | File | Lines | Status |
|---|---|---:|---|
| `primary_volume` | `primary_volume.py` | 140 | ✅ Production (Cycle 1) |
| `panel` | `panel.py` | 72 | ✅ Production (Cycle 1) |
| `frame` | — | — | ❌ Not implemented |
| `inset` | — | — | ❌ Not implemented |
| `trim` | — | — | ❌ Not implemented |
| `guard` | — | — | ❌ Not implemented |
| `rail` | — | — | ❌ Not implemented |
| `bracket` | — | — | ❌ Not implemented |
| `vent` | — | — | ❌ Not implemented |
| `conduit` | — | — | ❌ Not implemented |
| `latch` | — | — | ❌ Not implemented |
| `weld` | — | — | ❌ Not implemented |
| `socket` | — | — | ❌ Not implemented |
| `mount` | — | — | ❌ Not implemented |
| `handle` | — | — | ❌ Not implemented |
| `hinge` | — | — | ❌ Not implemented |
| `fastener` | — | — | ❌ Not implemented |
| `decal_zone` | — | — | ❌ Not implemented |
| `wear_zone` | — | — | ❌ Not implemented |
| `material_zone` | — | — | ❌ Not implemented |

**To implement: 18 generators.** None shipped as stubs; each new generator commit ships production-complete.

### Decorators (`lathe/asset_quality/procedural_synthesizer/decorators/hard_surface/`)

| EDGE_TYPE | File | Lines | Status |
|---|---|---:|---|
| `attached_to` | `attached_to.py` | 67 | ✅ Production (Cycle 1) |
| `inset_into` | — | — | ❌ Not implemented |
| `wraps_around` | — | — | ❌ Not implemented |
| `mirrors` | — | — | ❌ Not implemented |
| `aligned_with` | — | — | ❌ Not implemented |
| `supports` | — | — | ❌ Not implemented |
| `cuts` | — | — | ❌ Not implemented |

**To implement: 6 decorators.**

### DomainExtensionManifest registration

The hard-surface domain registers via `DomainExtensionManifest` in `generators/hard_surface/__init__.py:51` (Cycle 1's plumbing). Adding a new generator requires three updates per the existing module docstring:

1. Export a `GENERATOR` symbol from the new file.
2. Add the module to `HARD_SURFACE_GENERATORS`.
3. Add a typed attribute schema under `..attributes`.

`HARD_SURFACE_NODE_SCHEMAS` and `_MANIFEST.emitted_shape_ir_ops` also need to grow as generators land.

## Implementation order

Generators land in the order their Round 2/3 family migrations demand them. Composition policies from Round 0 dictate which NODE_TYPEs each policy references. Per the audit (§6.3 of `cycle-3-migration-inventory.md`), the canonical panelized policy uses `primary_volume + panel + frame + trim + fastener` — so `frame`, `trim`, `fastener` are the next three generators that unblock the most family migrations.

Suggested first-five batch (unblocks 10 of the Round 2 families): `frame`, `trim`, `fastener`, `handle`, `material_zone`.
