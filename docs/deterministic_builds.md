# Deterministic Builds

Lathe's reference pipeline is designed so the same source, runtime config,
checked-in refs, and toolchain emit the same selector and package hashes from a
fresh build.

The build contract is:

- `selector_manifest.json.buildHash` is derived from normalized source, the
  selected asset, runtime config, backend contract fingerprints, and provider
  registry metadata.
- `selector_manifest.json.packageHash` is derived from the emitted package
  artifacts, preferring the main GLB hash when present.
- Package manifest `output_hashes` records a SHA-256 for each exported artifact.
- `lathe build --report json --deterministic` canonicalizes report output by
  sorting keys, normalizing paths, and removing timestamp jitter.
- `lathe snapshot <build_dir> --deterministic` emits a stable sidecar snapshot
  with a zeroed timestamp for diffing release candidates.

The guarantee assumes deterministic or seeded backends. If an external learned
provider is enabled, pin the provider, seed, runtime config, and source refs
before treating hash differences as regressions.

Local smoke check:

```powershell
python -m lathe.cli build examples/api/socket.lth api_socket --out dist/a --report json --deterministic
python -m lathe.cli build examples/api/socket.lth api_socket --out dist/b --report json --deterministic
python -m pytest -q tests/unit/test_deterministic_build_mode.py
```

Canonical gallery release check:

```powershell
python -m pytest -q -m slow tests/unit/test_deterministic_build_mode.py
```
