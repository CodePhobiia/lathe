# Troubleshooting

Use this page when a normal Lathe command fails but the local environment is
mostly installed. For first-run setup problems, start with
[Quickstart](quickstart.md).

## Common failures

| Symptom | Likely cause | How to confirm | Next step |
|---|---|---|---|
| `lathe usage error [lathe.cli.usage]` | The command line is missing a required argument, has an unsupported option, or picked an invalid subcommand. | The error footer prints the exact `lathe ... --help` command for that parser. | Run the suggested help command, fix the flags/positionals, then rerun. |
| `lathe error [lathe.cli.parse_error]` | The `.lth` file has invalid syntax or an incomplete block. | Run `python -m lathe.cli parse <file>` or rerun with `--debug-traceback` only when debugging Lathe itself. | Fix the line reported by the parse diagnostic, then run `check` before `build`. |
| `Unknown asset or variant` | The asset name passed to `plan`, `materialize`, or `build` does not exist in the source file. | Run `python -m lathe.cli normalize <file>` and inspect the `assets` and `variants` names. | Use the declared asset/variant name or update the source declaration. |
| Missing source, mesh, image, or runtime-config path | A file path is wrong, outside the allowed root, unreadable, or blocked by the path guard. | Check the `at <path>` line in the CLI error and run from the repository root. | Use repo-relative paths for source refs and write generated outputs under ignored roots such as `dist/`, `dist_*`, or `tmp_*`. |
| Provider unavailable | A learned provider was requested but its server, package, model, allowlist, or timeout config is invalid. | Run `python -m lathe.cli doctor --runtime-config <config>` and `python -m lathe.cli probe-providers --runtime-config <config>`. | Fix the runtime config or use the default offline reference-conditioned provider. In strict mode, unavailable providers fail instead of falling back. |
| Doctor reports failed setup checks | The shell, interpreter, install mode, base dependencies, dev dependencies, or repository permissions are incomplete. | Run `python -m lathe.cli doctor --json` and inspect `setup_checks[]` plus `remediation[]`. | Apply the matching remediation entry first; rerun doctor before debugging providers or builds. |
| Hunyuan HTTP request denied before network access | `base_url`, `url_allowlist`, scheme, or timeout settings violate runtime-config validation. | Run the same build with `--report json` and inspect the diagnostic code/details. | Use `timeout_s`, configure `url_allowlist`, and keep non-loopback HTTP disabled unless the server is local. |
| Blender unavailable or failed | Blender is not installed, not on `PATH`, rejected by sandbox limits, or the subprocess returned an error. | Run `python -m lathe.cli doctor` and inspect the topology backend section. | Install Blender or allow the deterministic fallback. For strict Blender runs, fix the executable path and sandbox resource limits first. |
| xatlas unavailable | The optional `xatlas` Python binding is missing or failed to import. | Run `python -m lathe.cli doctor` and inspect the UV backend section. | Install `.[xatlas]`; on Windows, install Visual Studio Build Tools with Desktop C++ if the wheel cannot be installed. The reference UV fallback remains explicit. |
| Cache status shows corrupt or missing metadata | A historical cache entry predates the current metadata layout or a manifest was interrupted. | Run `python -m lathe.cli cache status --json` and check `metadata_source`, `asset`, and `cache_version`. | Use `lathe cache clean --asset <asset> --dry-run`, then rerun with `--yes` only for entries you intend to remove. |
| `cache clean` refuses to delete | The safety gate requires confirmation. | The CLI emits `lathe.cli.cache.confirm_required`. | Rerun with `--dry-run` to preview or `--yes` to delete. |
| Certification fails | The build completed, but validation metrics did not meet the asset contract. | Open `build_report.json` and `stages/validate/report.json`; inspect diagnostic `code`, `value`, `threshold`, and stage evidence. | Fix the source contract, geometry, refs, provider mode, or budget that caused the failing diagnostic. Do not treat uncertified outputs as release-ready. |
| A docs-visible artifact path is missing | The docs are stale or the build used a different package config. | Compare `build_report.json` `manifest_path` and `trace_path` to the docs. | Current packaged outputs live under `stages/package/package_manifest.json` and `stages/package/trace_manifest.json`. |

## Debug mode

Normal CLI errors hide Python tracebacks and emit stable diagnostic codes. Use:

```bash
python -m lathe.cli --debug-traceback <command> ...
```

or:

```bash
LATHE_DEBUG_TRACEBACK=1 python -m lathe.cli <command> ...
```

only when debugging Lathe internals. User-facing bug reports should include the
normal diagnostic code, command, runtime config if relevant, and the smallest
source file that reproduces the failure.

## Machine-readable failures

For build automation, use JSON report mode:

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist --report json
```

On failure, the command writes `ok: false`, a stable `code`, an actionable
`next_step`, and `diagnostics[]` to stdout. CI should key off those fields
rather than parsing prose.
