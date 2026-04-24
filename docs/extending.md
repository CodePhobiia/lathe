# Extending Lathe with third-party plugins

Plan 03 Phase 2 introduces an entry-point-based plugin registry so
third-party Python distributions can add their own backends, stacks,
shape providers, and validators without patching the Lathe source tree.

Lathe itself dogfoods the registry: all built-in backends, stacks,
providers, and validators are registered via the same entry-point
groups that third-party plugins use. Look at the `[project.entry-points]`
tables in Lathe's `pyproject.toml` for working reference examples.

## Entry-point groups

| Group                       | Purpose                                        | Expected value          |
|-----------------------------|------------------------------------------------|-------------------------|
| `lathe.backends`            | Register a new backend descriptor              | `dict` (module-level)   |
| `lathe.stacks`              | Register a new stack descriptor                | `dict` (module-level)   |
| `lathe.providers.shape`     | Register a shape-provider adapter              | `callable() -> dict`    |
| `lathe.validators`          | Register a validator callable                  | `callable(asset, runtime) -> dict` |

`dict` descriptors must at minimum carry an `id` field. Lathe's
plugin loader (`lathe.backends.load_plugin_backends`) merges the
descriptor into the matching in-process registry; on ID collisions the
*built-in* definition wins and the third-party entry is logged at
`DEBUG`.

## Minimal author recipe

`my_lathe_plugin/pyproject.toml`:

```toml
[project]
name = "my-lathe-plugin"
version = "0.1.0"
dependencies = ["lathe>=0.1"]

[project.entry-points."lathe.backends"]
"mycompany.topology.retopo_v1" = "my_lathe_plugin.backends:retopo_backend"
```

`my_lathe_plugin/backends.py`:

```python
retopo_backend = {
    "id": "mycompany.topology.retopo_v1",
    "version": "0.1.0",
    "stage": "topology",
    "toolchain": ["my-retopo-lib"],
    "runtime_executor": "my_lathe_plugin.runtime:run_retopo",
    "determinism_class": "deterministic",
    "supported_asset_kinds": ["hard_surface_prop"],
    "supported_retopo": ["auto"],
    "supported_preserve": ["hard_edges"],
    "contract": {
        "summary": "Retopo pass backed by my-retopo-lib.",
        "inputs": {"required": ["shape_bundle"]},
        "outputs": {"artifact": "topology_bundle"},
    },
}
```

Install into the same environment as Lathe (`pip install -e .`) and
verify the probe picks it up:

```
$ lathe doctor --plugins
Lathe Plugins (entry points)

[lathe.backends]
  - lathe.topology.blender_hard_surface_v1 -> lathe.backends:hard_surface_topology_backend: ok
  - mycompany.topology.retopo_v1 -> my_lathe_plugin.backends:retopo_backend: ok
  ...
```

`lathe doctor --plugins --json` emits the same report as structured
JSON for CI consumption.

## Runtime discovery

Plugins are discovered lazily. The compiler calls
`lathe.backends.load_plugin_backends()` once per process the first
time a stack or backend is resolved. Call it explicitly from a test if
you need deterministic ordering:

```python
from lathe.backends import BACKENDS, load_plugin_backends

added = load_plugin_backends()
assert "mycompany.topology.retopo_v1" in added["backends"]
assert "mycompany.topology.retopo_v1" in BACKENDS
```

`load_plugin_backends(force=True)` re-runs discovery (the default is
idempotent).

## Authoring a shape-provider plugin

The `lathe.providers.shape` group expects a callable that returns a
descriptor dict (the registry entry keys are owned by
`lathe/providers/registry.py`). The callable is a thin shim -- it lets
Lathe discover your adapter's provider ID without importing the heavy
runtime at interpreter start. Add the real execution entry point under
whatever name you prefer inside your package, and register the
provider ID with `lathe.providers.registry` once Lathe imports your
shim.

## Authoring a validator plugin

The `lathe.validators` group expects a callable of signature
`evaluate(asset: dict, runtime: dict) -> dict`. The returned dict
should include a `score` and `metrics` field consistent with the
validator composition contract (Plan 03 Phase 5, forthcoming).

## Troubleshooting

- `lathe doctor --plugins` lists each entry point with a
  `resolvable`/`unresolvable` status. `unresolvable` entries carry the
  original import error in the `error` field; the common cause is a
  typo in the entry-point target or a missing transitive dependency.
- The plugin loader deliberately *never* raises -- a broken
  third-party plugin must never prevent Lathe from starting. Check
  `logging.getLogger("lathe.backends")` at `DEBUG` for plugin
  collisions and `WARNING` for load failures.

## Related

- `.importlinter` declares the architecture contracts that keep the
  compiler's layering stable (Plan 03 Phase 3). Plugins are expected
  to depend on the stable contract surface (`lathe.backends`,
  `lathe.shape.*`, `lathe.providers.*`, `lathe.validators.*`) and to
  avoid the frontend / core layers.
- `docs/first_backend_stack.md` documents the first runnable stack
  (`lathe.stack.hard_surface_game_asset_v1`) and is the recommended
  starting template for a new third-party stack.
