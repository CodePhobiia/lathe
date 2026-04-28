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
| `lathe.cli.usage`                               |  `2` | `argparse` rejected command arguments before the handler ran.                               | Run `lathe <command> --help` for the supported arguments.                              | `lathe/cli/__init__.py:_LatheArgumentParser.error` |
| `lathe.cli.file_not_found`                      |  `2` | A source/config/artifact path required by a command does not exist.                         | Check the path and rerun the command from the repository root.                         | `lathe/cli/__init__.py:main` |
| `lathe.cli.expected_file`                       |  `2` | A command expected a file path but received a directory.                                    | Pass a `.lth` source file or a supported JSON sidecar path.                            | `lathe/cli/__init__.py:main` |
| `lathe.cli.permission_denied`                   |  `2` | The process cannot read or write the requested path.                                       | Check file permissions or choose a writable output/cache directory.                    | `lathe/cli/__init__.py:main` |
| `lathe.cli.parse_error`                         |  `1` | A `.lth` source file could not be parsed.                                                   | Fix the reported Lathe syntax issue and rerun the command.                             | `lathe/cli/__init__.py:main` |
| `lathe.cli.runtime_config_error`                |  `1` | A runtime-config JSON file is missing, malformed, or semantically invalid.                  | Fix the runtime config and rerun the command.                                          | `lathe/cli/__init__.py:main` |
| `lathe.cli.io_error`                            |  `1` | A filesystem operation failed after argument parsing.                                      | Check the referenced path, filesystem permissions, and available disk space.            | `lathe/cli/__init__.py:main` |
| `lathe.cli.error`                               |  `1` | A Lathe semantic error reached the top-level CLI boundary.                                  | Fix the reported Lathe input or configuration issue and rerun the command.             | `lathe/cli/__init__.py:main` |
| `lathe.cli.build.build_failed`                  |  `1` | `build_asset` raised `BuildError` (semantic or runtime).                                    | Inspect `diagnostics` in the emitted JSON; fix upstream asset or config.               | `lathe/cli/build_cmd.py` (BuildError handler) |
| `lathe.cli.build.provider_fallback_blocked`     |  `1` | Strict shape-provider mode blocked a learned-provider fallback.                             | Re-run with the required provider available, or disable strict provider mode only when fallback is acceptable. | `lathe/cli/build_cmd.py` (ShapeProviderError handler) |
| `lathe.cli.build.provider_failed`               |  `1` | A selected shape provider was unknown, unavailable, or failed before fallback could proceed. | Inspect the provider diagnostic, runtime config, and selected provider ID.             | `lathe/cli/build_cmd.py` (ShapeProviderError handler) |
| `lathe.cli.build.package_failed`                |  `1` | The package stage hit a package-artifact IO conflict while assembling outputs.              | Inspect the package output directory and remove stale/conflicting artifacts.           | `lathe/cli/build_cmd.py` (package IO handler) |
| `lathe.cli.build.invalid_report_format`         |  `2` | `--report <value>` is not one of `terminal`/`html`/`json`.                                 | Pass `--report terminal`, `--report html`, or `--report json`.                         | `lathe/cli/build_cmd.py` (`_resolve_report_format`) |
| `lathe.cli.build.unsafe_out_path`               |  `2` | `--out` resolved outside the current working tree and was rejected by the path guard.       | Pick a path under the current working directory, or set `LATHE_ALLOW_EXTERNAL_OUT=1`.  | `lathe/cli/build_cmd.py:_guarded_out_root` |
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
| `lathe.cli.cache.invalid_duration`              |  `2` | `lathe cache clean --older-than` received an invalid duration string.                       | Use a duration like `7d`, `24h`, `30m`, or `45s`.                                      | `lathe/cli/cache_cmd.py:_run_clean` |
| `lathe.cli.cache.confirm_required`              |  `2` | `lathe cache clean` was run without `--dry-run` or `--yes`.                                 | Re-run with `--dry-run` to preview matches, or `--yes` to delete them.                 | `lathe/cli/cache_cmd.py:_run_clean` |
| `lathe.cli.cache.warm_failed`                   |  `1` | `lathe cache warm` could not build or locate a warmed cache entry.                          | Inspect the source asset, runtime config, and cache directory, then rerun.             | `lathe/cli/cache_cmd.py:_run_warm` |
| `lathe.cli.cache.unknown_command`               |  `2` | `lathe cache <subcmd>` dispatched to an unknown handler.                                    | See `lathe cache --help`.                                                              | `lathe/cli/cache_cmd.py:run_cache` |
| `lathe.cli.diff.missing_snapshot`               |  `2` | A snapshot passed to `lathe diff` does not exist.                                           | Run `lathe snapshot <build_dir>` to produce one, then retry.                           | `lathe/cli/diff_cmd.py:run_diff` |
| `lathe.cli.diff.unreadable_snapshot`            |  `2` | A snapshot passed to `lathe diff` is not readable JSON.                                     | Regenerate with `lathe snapshot`.                                                      | `lathe/cli/diff_cmd.py:run_diff` |
| `lathe.cli.patch.missing_value2`                |  `2` | `widen_search_bounds` requires `--value2 LOWER:UPPER`.                                      | Re-run with `--value2 LOWER:UPPER` (e.g. `--value2 0.8:1.2`).                          | `lathe/cli/patch_cmd.py` |
| `lathe.cli.patch.invalid_value2`                |  `2` | `--value2` for `widen_search_bounds` must be `LOWER:UPPER`.                                 | Re-run with `--value2 LOWER:UPPER` (numeric).                                          | `lathe/cli/patch_cmd.py` |
| `lathe.cli.patch.unknown_op`                    |  `2` | Unsupported `--op` passed to `lathe patch`.                                                 | See `lathe patch --help` for the allowed operations.                                   | `lathe/cli/patch_cmd.py` |
| `lathe.cli.publish.invalid_target`              |  `1` | The named publish driver is not registered.                                                 | Use `lathe publish --help` (or `doctor`) to list available drivers.                    | `lathe/cli/publish_cmd.py` |
| `lathe.cli.publish.missing_manifest`            |  `2` | The build directory does not contain a manifest to publish.                                 | Run `lathe build <file> <asset>` first.                                                | `lathe/cli/publish_cmd.py` |
| `lathe.cli.publish.driver_failed`               |  `1` | The publish driver reported an error.                                                       | Inspect the `message` field and driver-specific config in `--runtime-config`.          | `lathe/cli/publish_cmd.py` |
| `lathe.cli.snapshot.missing_build_dir`          |  `2` | `lathe snapshot` was pointed at a missing or non-directory build path.                      | Run `lathe build` first, or point at a completed build directory.                      | `lathe/cli/snapshot_cmd.py` |
| `lathe.cli.surface.build_failed`                |  `1` | `surface-build`/`surface-validate`/`surface-repair` raised `BuildError`.                    | Inspect `diagnostics` in the emitted JSON; fix upstream asset or config.               | `lathe/cli/surface_cmd.py` |
| `lathe.cli.surface.provider_fallback_blocked`   |  `1` | Strict surface provider mode blocked a learned-provider fallback.                           | Re-run with the required provider available, or allow fallback where appropriate.      | `lathe/cli/surface_cmd.py` |
| `lathe.cli.surface.provider_failed`             |  `1` | A selected surface-stage provider was unknown, unavailable, or failed.                      | Inspect the provider diagnostic and runtime config.                                    | `lathe/cli/surface_cmd.py` |
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

## Output examples

Human-readable terminal errors go to stderr and keep tracebacks hidden unless
`--debug-traceback` or `LATHE_DEBUG_TRACEBACK=1` is set:

```text
lathe error [lathe.cli.file_not_found]: File not found: examples/missing.lth
  at examples/missing.lth
  Next step: Check the path and rerun the command from the repository root.
```

Commands with `--report json` return machine-readable failures on stdout using
the same semantic code and an actionable diagnostic record:

```json
{
  "ok": false,
  "code": "lathe.cli.file_not_found",
  "message": "File not found: examples/missing.lth",
  "severity": "error",
  "next_step": "Check the path and rerun the command from the repository root.",
  "diagnostics": [
    {
      "code": "lathe.cli.file_not_found",
      "severity": "error",
      "message": "File not found: examples/missing.lth",
      "path": "examples/missing.lth"
    }
  ],
  "source_path": "examples/missing.lth"
}
```
