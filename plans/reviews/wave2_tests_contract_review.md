# Wave 2 Review — Tests & Contract

**Reviewer:** reviewer-tests-contract  
**Date:** 2026-04-23  
**Wave 2 commit range:** `54b8ae8..61aab04` (8 commits)

## Summary

Wave 2 has landed cleanly. Full pytest suite is **70 passed, 0 failed in 943.64s (15:43)** — exact match to the pre-Wave-2 70/70 baseline. All 9 hero `.lth` examples certify above their thresholds with no regressions; the stable contract ID `lathe.shape.intent_mesh_handoff_v1` is intact across 75 occurrences in 47 files (no drift); the shape decomposition commit `035a45f` matches current `lathe/shape/` layout; the build cache engages on second run (45+s -> 3s observed for `courier_drone`). **Wave 2 is safe to continue to Wave 3.**

## Pytest result

Run: `.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -15`  
Started 2026-04-23 03:59:41 AST, PID 728. Exit code 0.

```
......................................................................   [100%]
70 passed in 943.64s (0:15:43)
```

- **Passed:** 70
- **Failed:** 0
- **Errors:** 0
- **Duration:** 943.64s (15m 43s)
- Matches pre-Wave-2 baseline (70/70). No regressions from the 8 Wave-2 commits.

## Hero build table

All 9 heroes built with `python -m lathe.cli build examples/<hero>.lth <hero> --out tmp_review_<hero>` — no `--runtime-config` (native-only path). Shape `bundle.json` does NOT carry a top-level hash field; reporting `.glb` SHA256 from build output instead.

| Hero | Score | Threshold | Certified | Wall (s) | .glb SHA256 |
|---|---|---|---|---|---|
| courier_drone | 0.879435 | 0.86 | yes | 45+ (1st) / 3 (2nd, cached) | `5d20f33e24c8f2531d468a1fd5ea0b1090871f6ab0b08b35384a8a226aafe4d9` |
| brassbound_chest | 0.888423 | 0.84 | yes | 3 | `fd53f2b766093679447ffef064bb3cb070735a4c3321d033e858e261d783d716` |
| industrial_crate | 0.884758 | 0.84 | yes | 3 | `47cb8cad3a3d40e594c49fc5ef261962d2e794e0e5cc8831db27f7da00bda7a8` |
| mechanical_door | 0.876905 | 0.84 | yes | 2 | `ed4c8d41d1346aa344d2982fcd5551772ee407f9cc8f78a2b4fcad962346f08c` |
| console_terminal | 0.855031 | 0.85 | yes | 3 | `12871bf281de4bc6cfe7b58acf5df33adaa92279c503c30cabdac7b62aeddcb4` |
| sci_fi_wall_panel | 0.862025 | 0.84 | yes | 3 | `dcd499e6ad744d058afff91f857ec91927accbd5779d11f51d9d6f9a0160ac21` |
| service_cabinet | 0.820871 | 0.82 | yes | 2 | `5ce826894017f965ffe036684dcab3a28204be9b5e2fcc2f08069c5ffbfb34a6` |
| control_pedestal | 0.842405 | 0.83 | yes | 2 | `9e2ceed007dc14ad3d7c0b856bc0c1d6e0fad952689f45b3ba9c4e07aad15210` |
| supply_container | 0.871784 | 0.84 | yes | 2 | `c69431d4e8be343053644a49043f8afb92fb0ef0d5111222aa8597e4e8db8b51` |

All 9 heroes were found at the canonical `examples/<hero>.lth` path matching CLAUDE.md.

`courier_drone` baseline 0.879435 (per task brief) reproduced exactly — no shape drift after Wave 2. All other heroes also exceed threshold; service_cabinet and control_pedestal are near margin (0.82/0.82 and 0.842/0.83) but that's pre-existing, not a Wave-2 regression.

## Contract-ID occurrences

`intent_mesh_handoff_v1`: **75 total occurrences across 47 files**. Code-side (load-bearing) references are all in `lathe/`:

| File | Count | Role |
|---|---|---|
| `lathe/backends.py` | 3 | Stack registration (`shape` slot) |
| `lathe/executor.py` | 1 | Module docstring "do NOT change" |
| `lathe/core/stages/shape.py` | 1 | Stage docstring |
| `lathe/shape/__init__.py` | 1 | Subpackage docstring |
| `lathe/shape/backend.py` | 2 | Module docstring + `if backend_id != "lathe.shape.intent_mesh_handoff_v1"` guard |
| `lathe/shape/geometry/conditioning.py` | 1 | Docstring |
| `lathe/shape/geometry/candidates.py` | 2 | Docstring + upstream-contract reference |

All references use the exact literal `lathe.shape.intent_mesh_handoff_v1` (also `intent_mesh_handoff_v1` bare-suffix in a few docstrings). The dispatch guard at `lathe/shape/backend.py:35` rejects anything else. Tests reference it at `tests/test_backends.py`, `tests/conftest.py`, `tests/contract/__init__.py`. **The ID is stable and not accidentally changed.**

## Intermediate commit verification — `035a45f`

`git show --stat 035a45f` confirms shape subsystem decomposition:
- New: `lathe/shape/__init__.py` (13), `lathe/shape/backend.py` (96), `lathe/shape/geometry/{__init__,primitives,conditioning,candidates}.py` (1/102/240/315)
- `lathe/shape_backend.py` shrunk from 665 LOC to 4-line shim
- Currently on disk (`ls lathe/shape/`): `__init__.py`, `backend.py`, `geometry/`, `__pycache__/` — matches commit.

## Cache behavior

- `lathe/executor.py:67-68` defines `BUILD_CACHE_ROOT = Path(tempfile.gettempdir()) / "lathe_build_cache"` and `BUILD_CACHE_VERSION = "v10_rc2"`. (Note: brief mentioned `BUILD_CACHE_KEY` — actual constant is `BUILD_CACHE_ROOT`; `VERSION` matches.)
- 1st `courier_drone` build: ~45+ seconds (full pipeline run, including provider/material/bake work).
- 2nd `courier_drone` build (immediately after, different `--out`): **3 seconds**, identical score `0.879435` and identical `.glb` SHA256.
- Cache engaged: yes. Subsequent hero builds (different assets) all completed in 2–3s, indicating warmed shape/topology caches across the suite (shared cache in `tempfile.gettempdir()`).

## Regressions flagged

**None.**
- Baseline `courier_drone` 0.879435 reproduced exactly.
- All 9 heroes certify above their thresholds.
- Stable contract ID intact in dispatch guard + 11 source-tree references.
- Shape subpackage layout matches commit `035a45f`.

## Overall verdict

**Wave 2 safe to continue to Wave 3: y** (pending pytest tail confirmation — see "Pytest result" above; the report will be updated once pytest finishes and inserted in place of `__PYTEST_TAIL__`).

The 8-commit refactor (parser split, errors hierarchy, executor decomposition, shape/providers subpackages, SSRF + Blender-stderr hardening) preserves the public surface: stable contract ID, hero certifications, and cache semantics. No source code was modified during this review.
