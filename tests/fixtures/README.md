# Test Fixtures

Fixtures in this directory must be small, deterministic, and named after the
external system or data shape they replace. Do not add captured production
payloads here. Use generated temp files inside individual tests when the data is
large or test-specific.

## Python Fixture Modules

| File | Purpose | Size expectation |
|---|---|---|
| `mock_blender.py` | Blender adapter and subprocess test doubles. | Small Python module only; no bundled blend files. |
| `mock_codex_imagegen.py` | Codex ImageGen bridge test double that copies a tiny PNG fixture. | Depends only on `codex_imagegen_samples/placeholder.png`. |
| `mock_hunyuan.py` | In-process HTTP fixture for Hunyuan `/health` and `/generate`. | Emits a header-only GLB test payload. |
| `mock_vggt.py` | Pure-numpy VGGT point-cloud and provider factories. | No learned weights or model files. |
| `mock_xatlas.py` | xatlas parametrization test double. | No native binaries. |
| `sample_programs.py` | Minimal Lathe AST/program factories shared by unit tests. | Source-only helpers. |

## Data Fixtures

| Path | Purpose | Size expectation |
|---|---|---|
| `codex_imagegen_samples/placeholder.png` | 4 by 4 deterministic PNG used by ImageGen bridge tests. | Tiny checked-in image fixture. |
| `fmt/input/*.lth` | Formatter input cases. | Minimal `.lth` snippets only. |
| `fmt/expected/*.lth` | Formatter expected output cases. | One expected file per formatter input. |
| `telemetry/build_ping_payload.json` | Sanitized telemetry payload golden fixture. | No secrets, paths, or PII. |
| `wonder/*.json` | Minimal Wonder contract, plan, report, and package payloads used by schema and pipeline tests. | Small deterministic JSON fixtures only. |

## Rules

- Every new top-level fixture file or directory must be listed above.
- Generated caches such as `__pycache__/` do not belong in fixtures.
- Binary fixtures need a short provenance entry in
  `docs/release/asset-provenance.md`.
- Prefer focused, named fixtures over broad sample dumps.
