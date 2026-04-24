# ADR 0004: Plugin extension points via `importlib.metadata.entry_points`

- **Status:** Proposed
- **Date:** 2026-04-23
- **Ticket:** Plan 03 Phase 2 (surgeon-plugins task #1, Wave 5.II)
- **Related:** ADR-0001 (frozen shape contract); ADR-0003 (provider
  mux); Plan 03 Phase 6 (second backend stack as the plugin-model
  proof); `lathe/backends.py` (built-in cache);
  `lathe/providers/registry.py` (built-in provider cache).

## Context

Lathe today registers backends, stacks, providers, and validators via
module-level dicts and adapter imports. That works for the reference
scaffold but blocks the plugin goal: third parties cannot add a new
backend, stack, provider, or validator without editing `lathe/` source.

The industry-standard extension mechanism for Python is setuptools
entry points (`importlib.metadata.entry_points`). Four extension
groups are needed, matching the four protocol surfaces the compiler
exposes:

- backends (per-stage adapters)
- stacks (backend bundles)
- shape providers (proposal sources under the shape handoff)
- validators (certification gates)

The decision is not whether to support plugins (Plan 03 requires it)
but how plugins interact with the existing built-in dicts and with
the `runtime_config.json` selection mechanism.

## Decision

1. **Four entry-point groups**, registered in `pyproject.toml`:
   ```
   [project.entry-points."lathe.backends"]
   [project.entry-points."lathe.stacks"]
   [project.entry-points."lathe.providers.shape"]
   [project.entry-points."lathe.validators"]
   ```
2. **Discovery** happens in `lathe/contracts/registry.py` via
   `importlib.metadata.entry_points(group=<name>)`. The registry
   lazy-loads, caches per-process, and exposes each discovered
   extension under the same protocol shape as the built-ins.
3. **Built-ins dogfood the mechanism.** The existing `BACKENDS` and
   `STACKS` dicts in `lathe/backends.py` and the `PROVIDERS` dict in
   `lathe/providers/registry.py` are retained as a zero-install
   cache: they are authoritative when entry-point discovery returns
   empty, and are overridden on ID match when an installed plugin
   claims the same ID.
4. **Precedence rule: `runtime_config.json` wins.** Entry points
   register *availability* (discoverable + probeable via
   `lathe doctor --plugins`). `runtime_config.json` chooses *what
   actually runs*. When both an installed entry point and a runtime
   config name a provider/backend for the same stage, the runtime
   config wins. The entry point merely confirms the ID is resolvable.
5. **Unknown IDs fail fast in `checker.py`.** If a runtime config
   names an ID that is neither in the built-in dicts nor discovered
   via entry points, the run fails with a clear error listing all
   known IDs for that stage. This is intentional: a typo in a
   runtime config must not silently fall back to a default.
6. **Migration for existing JSON runtime configs.** The shipping
   configs (`hunyuan_http.json`, `vggt_local.json`, `auto_learned.json`)
   keep working unchanged. Their IDs (`lathe.provider.shape.hunyuan2_1_http_v1`
   etc.) are the same strings whether they are resolved through the
   built-in dict or through an entry point.

## Rationale

### Why entry points and not a config-file plugin manifest

Entry points are the ecosystem-standard. `pip install <plugin>` is
the obvious user flow. A custom manifest format would require every
plugin author to learn it and would reinvent `importlib.metadata`'s
caching, uninstall handling, and distribution discovery.

### Why four groups instead of one

Each protocol has different typing and a different probe/run contract.
A single group would force the loader to introspect the imported
object to decide what it is; four groups make the intent explicit and
let `lathe doctor --plugins` render them in separate sections.

### Why keep the built-in dicts

Zero-install behaviour matters for the smoke loop. A developer who
clones the repo and runs `python -m lathe.cli build examples/courier_drone.lth`
expects it to work without an editable install or a plugin
registration step. The dicts provide that. They are also the fast
path for cold-start — no entry-point scan is needed to resolve the
built-ins.

### Why `runtime_config` wins over entry points

Entry points describe the *inventory* of a machine. Runtime configs
describe the *intent* of a build. A reader of `runtime_config.json`
should be able to predict exactly what runs without also consulting
the installed plugin list. If an entry point could override a runtime
config, the reader would need both pieces of information to understand
a build — exactly the invisibility problem ADR-0002 argues against
for fallback.

### Why unknown IDs fail fast

Silent fallback on typo'd IDs would produce bundles that claim to have
used a plugin and actually used the default. That is a certification
lie. The failure must be loud and must list alternatives so the user
can correct the typo without grepping source.

## Consequences

### Positive

- Third parties can ship `lathe-myprovider` on PyPI and have it work
  with a stock Lathe install.
- `lathe doctor --plugins` gives operators a single-command view of
  what extensions are installed and whether they probe.
- Built-in behaviour is unchanged on `pip install -e .` alone, so
  the smoke loop stays frictionless.
- Runtime configs remain the single source of truth for "what ran".

### Negative / accepted risks

- Entry-point discovery has a cold-start cost (walking installed
  dist-info). Mitigated by per-process caching; a future optimisation
  (plan notes) is a persistent `~/.lathe/plugin_cache.json` keyed on
  installed-distribution hash.
- A plugin that claims a built-in ID can override the built-in
  silently (by design, for vendor overrides). Mitigated by
  `lathe doctor --plugins` which must surface this as a warning —
  the built-in entry is visible in the discovery output so an operator
  can see the override.
- Two registration mechanisms (dicts + entry points) is more surface
  than one. The alternative (rip the dicts) was rejected for
  zero-install reasons above; the trade-off is documented here so a
  future maintainer reading this ADR understands the dicts are
  not legacy to be removed.

## Alternatives considered

- **Only entry points, remove the built-in dicts.** Rejected:
  breaks zero-install smoke loop and adds cold-start latency for
  every invocation.
- **Only the dicts, no entry points.** Rejected: makes third-party
  extension impossible without patching source; fails the Plan 03
  "≥ 4 documented extension points" exit criterion.
- **Entry point wins over runtime config.** Rejected: hides what
  ran from readers of the runtime config.
- **Single unified group (`lathe.plugins`) with runtime type
  dispatch.** Rejected: protocol surfaces differ enough that
  introspection would be more code than four explicit groups.

## Re-evaluation criteria

Re-open this decision if:

1. Cold-start latency from entry-point scanning becomes visible in
   profile (e.g. `lathe doctor` or `lathe check` shows >50ms in
   discovery). Add the persistent plugin cache at that point.
2. A fifth extension kind emerges (e.g. custom bake backends,
   publish registries) and the four-group layout no longer
   describes the extension surface.
3. The precedence rule bites users — operators report that they
   expected their installed plugin to win over a stale runtime
   config. The current rule says "runtime config is authoritative";
   if that turns out to be the wrong default, introduce an explicit
   `runtime_config.plugin_precedence: "plugins"` override rather
   than flipping the default.

## Cross-references

- Plugin registry implementation: surgeon-plugins task #1 (Wave 5.II).
  Once that task lands, this ADR flips to **Accepted** and a commit
  SHA is recorded here.
- ADR-0005 documents the import-linter contracts that enforce the
  layering the entry-point system assumes (plugins depend on
  `lathe.contracts`, not on `lathe.backends` or `lathe.providers`
  internals).
