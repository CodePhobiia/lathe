# Lathe CLI error codes

BL-36 (Plan 08 Phase 6d). Every user-facing CLI failure is annotated with a
semantic error code so that scripts, CI pipelines, and humans can triage
without parsing free-form English. Codes follow
`lathe.<subsystem>.<command>.<condition>`.

Exit-code contract (from `lathe/cli/build_cmd.py` + siblings):

| exit | meaning                                                                   |
| ---: | ------------------------------------------------------------------------- |
|  `0` | success                                                                   |
|  `1` | build, provider, or runtime error (the pipeline ran but failed)           |
|  `2` | CLI usage error (bad flags, missing files, unknown subcommand)            |
|  `3` | optional-dependency or environment gap (e.g. `--view` without `trimesh`) |

## Error codes

| error_code                                      | exit | description                                                                                 | next_step                                                                              | raised_at                          |
| ----------------------------------------------- | ---: | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------- |
| `lathe.cli.build.build_failed`                  |  `1` | `build_asset` raised `BuildError` (semantic or runtime).                                    | Inspect `diagnostics` in the emitted JSON; fix upstream asset or config.               | `lathe/cli/build_cmd.py` (BuildError handler) |
| `lathe.cli.build.provider_fallback_blocked`     |  `1` | Strict shape-provider mode blocked a learned-provider fallback.                             | Re-run with the required provider available, or drop `--strict-shape-provider`.        | `lathe/cli/build_cmd.py` (ShapeProviderError handler) |
| `lathe.cli.build.invalid_report_format`         |  `2` | `--report <value>` is not one of `terminal`/`html`/`json`.                                 | Pass `--report terminal`, `--report html`, or `--report json`.                         | `lathe/cli/build_cmd.py` (`_resolve_report_format`) |
| `lathe.cli.build.mode_mismatch`                 |  `1` | Asset's resolved `shape.mode` doesn't match the invoked subcommand (`adapt`/`assemble`/`reconstruct`). | Invoke the subcommand matching the asset's `shape.mode`, or patch the asset.           | `lathe/cli/build_cmd.py:run_mode_build` |
| `lathe.cli.render_eval.build_failed`            |  `1` | `build_asset` raised `BuildError` during `render-eval`.                                     | Inspect diagnostics in the JSON payload; fix upstream asset or config.                 | `lathe/cli/build_cmd.py:run_render_eval` |
| `lathe.cli.inspect.trimesh_missing`             |  `3` | `lathe inspect --view` requires the optional `trimesh` package.                             | `pip install trimesh` (or add it to your dev extras).                                  | `lathe/cli/inspect_cmd.py` |
| `lathe.cli.inspect.no_glb`                      |  `3` | No packaged `.glb` was found under the build directory.                                     | Run `lathe build <file> <asset>` first, or point to a build that emitted a `.glb`.     | `lathe/cli/inspect_cmd.py` |
| `lathe.cli.serve.missing_build_dir`             |  `2` | The positional `<build_dir>` does not exist or isn't a directory.                           | Run `lathe build <file> <asset>` first, or pass a valid `--out` directory.             | `lathe/cli/inspect_cmd.py:run_serve` |
| `lathe.cli.bridge.unknown_command`              |  `2` | `lathe bridge <subcmd>` dispatched to an unknown handler.                                   | See `lathe bridge --help` for the supported subcommands.                               | `lathe/cli/bridge_cmd.py` |
| `lathe.cli.fmt.check_would_change`              |  `1` | `lathe fmt --check` found files that are not canonical.                                     | Re-run `lathe fmt` (no flag) to rewrite them, then commit.                             | `lathe/cli/fmt_cmd.py` |
| `lathe.cli.fmt.invalid_stdin`                   |  `2` | `lathe fmt --stdout` passed more than one source or bad stdin.                              | Pass a single file, or pipe exactly one Lathe source into stdin.                       | `lathe/cli/fmt_cmd.py` |
| `lathe.cli.fmt.parse_failed`                    |  `1` | Formatter could not parse the input source.                                                 | Fix the syntax error reported; run `lathe parse` for a pinpointed trace.              | `lathe/cli/fmt_cmd.py` |
| `lathe.cli.library.unknown_command`             |  `2` | `lathe library <subcmd>` dispatched to an unknown handler.                                  | See `lathe library --help`.                                                            | `lathe/cli/library_cmd.py` |
| `lathe.cli.test.failed`                         |  `1` | Lathe-defined source tests failed.                                                          | Inspect the failing declarations and their expected vs observed metrics.               | `lathe/cli/test_cmd.py` |
| `lathe.cli.bench.failed`                        |  `1` | Lathe-defined source benchmarks failed.                                                     | Inspect the failing declarations and their expected vs observed metrics.               | `lathe/cli/test_cmd.py` |
| `lathe.cli.patch.missing_value2`                |  `2` | `widen_search_bounds` requires `--value2 LOWER:UPPER`.                                      | Re-run with `--value2 LOWER:UPPER` (e.g. `--value2 0.8:1.2`).                          | `lathe/cli/patch_cmd.py` |
| `lathe.cli.patch.invalid_value2`                |  `2` | `--value2` for `widen_search_bounds` must be `LOWER:UPPER`.                                 | Re-run with `--value2 LOWER:UPPER` (numeric).                                          | `lathe/cli/patch_cmd.py` |
| `lathe.cli.patch.unknown_op`                    |  `2` | Unsupported `--op` passed to `lathe patch`.                                                 | See `lathe patch --help` for the allowed operations.                                   | `lathe/cli/patch_cmd.py` |
| `lathe.cli.publish.invalid_target`              |  `1` | The named publish driver is not registered.                                                 | Use `lathe publish --help` (or `doctor`) to list available drivers.                    | `lathe/cli/publish_cmd.py` |
| `lathe.cli.publish.missing_manifest`            |  `2` | The build directory does not contain a manifest to publish.                                 | Run `lathe build <file> <asset>` first.                                                | `lathe/cli/publish_cmd.py` |
| `lathe.cli.publish.driver_failed`               |  `1` | The publish driver reported an error.                                                       | Inspect the `message` field and driver-specific config in `--runtime-config`.          | `lathe/cli/publish_cmd.py` |
| `lathe.cli.surface.build_failed`                |  `1` | `surface-build`/`surface-validate`/`surface-repair` raised `BuildError`.                    | Inspect `diagnostics` in the emitted JSON; fix upstream asset or config.               | `lathe/cli/surface_cmd.py` |
| `lathe.cli.unknown_command`                     |  `2` | `argparse` dispatched to an unregistered subcommand.                                        | See `lathe --help` for the supported subcommands.                                      | `lathe/cli/__init__.py:main` |

## Guidance for contributors

- New `raise SystemExit(...)` sites **must** come with a semantic code in this
  table. Prefer `lathe.cli._common._emit_error(...)` so the error output is
  consistent (TTY-aware coloring, citation line, `Next step:` hint).
- Keep `exit_code` stable for a given error. Changing an exit code is a
  breaking change to CI pipelines.
- When deprecating a code, leave it in this table with a `deprecated: since
  Vx.y` note rather than removing the row; downstream scripts may still
  grep for it.
