# Runbook: lathe doctor False Result

`lathe doctor` reports a false negative (healthy when it's not) or false positive (broken when it isn't).

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- `lathe doctor` exits 0 but a subsequent `lathe build` fails with a missing-provider error.
- `lathe doctor` reports a provider as unavailable but the provider works via its own CLI.
- `lathe doctor --json` returns a provider key with `available: false` on a machine where the binary exists.

## First response (≤5 min)

1. Ask the user to run `lathe doctor --json` and paste the full JSON output.
2. Ask them to run `python -m platform` and paste the result (OS, arch, Python build string).

## Investigation

```bash
python -m lathe.cli doctor --json > /tmp/doctor_out.json
python -m platform
```

Compare `doctor_out.json` against the expected schema in `lathe/doctor.py`. Check:

- **Provider availability vs runtime config:** If the user is not passing `--runtime-config`, the doctor only probes the default provider set. A learned provider (Hunyuan, VGGT) that requires a runtime config will correctly show `available: false` in the default probe.
- **Blender path detection:** The doctor resolves Blender via `shutil.which("blender")` and the platform-specific search in `lathe/backends.py`. If Blender is installed but not on `PATH`, it will show unavailable. Ask the user to run `which blender` (Linux/macOS) or `where blender` (Windows).
- **xatlas detection:** Similar — `lathe/backends.py` probes `import xatlas`. If the venv's xatlas build is broken, the import will fail silently; `pip show xatlas` will reveal it.

For a false negative (doctor says OK but build fails), diff the doctor's environment probe against the actual error:

```bash
python -m lathe.cli doctor --json | python -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))"
python -m lathe.cli check examples/courier_drone.lth
```

## Mitigation

- If the doctor is missing a probe, open a bug labeled `bug` against `lathe/doctor.py`.
- If the discrepancy is due to PATH differences between the doctor's shell and the user's shell, update `lathe/backends.py` to expand PATH search.
- If a runtime-config-gated provider is incorrectly shown as required in the default probe, fix `lathe/doctor.py` to annotate those as opt-in.

## Communication

Apply Macro: `lathe doctor` failure (in `docs/support/readiness-checklist.md`). Respond on the issue with the `--json` diff.

## Escalation

Escalates to release blocker if the false result causes a clean install to appear broken (install-failure trigger) or if it masks a real provider-availability failure that degrades the hero-family build.

## Postmortem trigger

Any confirmed case where `doctor` gave green and a downstream stage produced a certification failure or silent fallback that the user did not expect.
