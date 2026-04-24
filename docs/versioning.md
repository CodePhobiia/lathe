# Versioning policy

Lathe follows [Semantic Versioning](https://semver.org/) with additional rules for its language surface and stable backend / contract identifiers.

## Version bumps

| Change | Bump |
|---|---|
| Additive language-surface change (new block type, new optional field) | **MINOR** |
| Breaking language-surface change (removed block, renamed keyword, changed semantics) | **MAJOR** |
| Any change to a stable backend or contract ID (`lathe.shape.intent_mesh_handoff_v1`, `lathe.stack.hard_surface_game_asset_v1`, etc.) | **MAJOR** or introduce a new ID with a higher suffix (`_v2`) |
| Additive backend / provider (new optional binding, new runtime config key) | **MINOR** |
| Bug fix that preserves all public contracts | **PATCH** |
| Internal refactor with no public-surface change | **PATCH** |

## Stable identifiers

The following identifiers are treated as public contracts. Any change requires either a MAJOR bump of the package **or** a new ID with an incremented suffix kept side-by-side with the old one for at least one MINOR release:

- Stack IDs: `lathe.stack.hard_surface_game_asset_v1` and any future stacks.
- Shape handoff: `lathe.shape.intent_mesh_handoff_v1`.
- Topology contracts: `lathe.topology.blender_hard_surface_v1`.
- UV contracts: `lathe.uv.xatlas_v1`.
- Package contracts: `lathe.package.openusd_gltf_v1`.
- Public language blocks: `profile`, `contract`, `critic`, `asset`, `variant`.

## Language surface

The additive-vs-breaking rule is enforced across a coordinated set of artifacts: any change must land as a single update to `spec/lathe-v0.1.md`, `grammar/lathe.lark`, `schema/lathe.schema.json`, parser / normalizer / resolver / checker behavior, and the matching examples + tests. This is documented in [`AGENTS.md`](AGENTS.md) and in [Contributing](CONTRIBUTING.md).

See [Dependency policy](dependency_policy.md) for how third-party dependency changes are versioned and upgraded.
