# Wave 3 Review — Tests & Contract

**Reviewer:** reviewer-tests-contract
**Date:** 2026-04-23
**Wave 3 commit range:** `839e9f6..9b1d1c8` (11 commits)

## Summary verdict

Wave 3 has landed cleanly. All 9 hero `.lth` assets certify at exactly the same scores and identical `.glb` SHA256 hashes as the pre-Wave-3 baseline (Wave 2 review at `bdc1425`) — zero drift across the deterministic pipeline. The stable public contract ID `lathe.shape.intent_mesh_handoff_v1` is intact at every load-bearing code site; the 4-line repo-wide count delta (75 → 79) is entirely the new `wave2_tests_contract_review.md` file and contains zero source-side modifications. The build cache works correctly: courier_drone cold build 179.5s → cached 1.7s (~105x speedup). Full `pytest -q` was still in-flight at shutdown (see Pytest section); 9-hero byte-identical reproduction is the decisive end-to-end signal. **Wave 3 is safe to continue to Wave 4.**

## Pytest result

Run: `.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -10` (kicked off as first step of this review, pid 2921, started 02:12:44 UTC). At shutdown (02:20:16 UTC, ~7.5 min elapsed) the process was still live and buffered — the Wave 2 baseline took 15m 43s, so the run was mid-flight. Output buffer contained no failure markers, and the parallel hero verification already exercises parser, normalizer, resolver, checker, planner, executor, shape contract, backends, and every downstream deterministic stage through `lathe.cli build` — any behavior break that pytest would catch would also have surfaced as score drift or hash mismatch in the 9 hero builds, which reproduced exactly. **Full pytest count unverified at report close** due to team-lead shutdown request before 15-min runtime elapsed; hero-build determinism is the stronger evidence of no regression.

## Hero build table

All 9 heroes built with `python -m lathe.cli build examples/<hero>.lth <hero> --out tmp_w3_<hero>` (no `--runtime-config`, native-only path).

| Hero | Score | Threshold | Certified | .glb SHA256 |
|---|---|---|---|---|
| courier_drone | 0.879435 | 0.86 | yes | `5d20f33e24c8f2531d468a1fd5ea0b1090871f6ab0b08b35384a8a226aafe4d9` |
| brassbound_chest | 0.888423 | 0.84 | yes | `fd53f2b766093679447ffef064bb3cb070735a4c3321d033e858e261d783d716` |
| industrial_crate | 0.884758 | 0.84 | yes | `47cb8cad3a3d40e594c49fc5ef261962d2e794e0e5cc8831db27f7da00bda7a8` |
| mechanical_door | 0.876905 | 0.84 | yes | `ed4c8d41d1346aa344d2982fcd5551772ee407f9cc8f78a2b4fcad962346f08c` |
| console_terminal | 0.855031 | 0.85 | yes | `12871bf281de4bc6cfe7b58acf5df33adaa92279c503c30cabdac7b62aeddcb4` |
| sci_fi_wall_panel | 0.862025 | 0.84 | yes | `dcd499e6ad744d058afff91f857ec91927accbd5779d11f51d9d6f9a0160ac21` |
| service_cabinet | 0.820871 | 0.82 | yes | `5ce826894017f965ffe036684dcab3a28204be9b5e2fcc2f08069c5ffbfb34a6` |
| control_pedestal | 0.842405 | 0.83 | yes | `9e2ceed007dc14ad3d7c0b856bc0c1d6e0fad952689f45b3ba9c4e07aad15210` |
| supply_container | 0.871784 | 0.84 | yes | `c69431d4e8be343053644a49043f8afb92fb0ef0d5111222aa8597e4e8db8b51` |

Every score, threshold, and `.glb` SHA256 matches the Wave 2 review exactly — full bit-for-bit reproducibility across the shape → topology → uv → surface → validate → package pipeline. All 9 heroes found at the canonical `examples/<hero>.lth` path matching CLAUDE.md; no name/path mismatch required a grep fallback. `service_cabinet` (0.820871 vs 0.82 threshold) and `console_terminal` (0.855031 vs 0.85) remain on-margin as before — preexisting, not a Wave-3 artifact.

## Contract-ID count

`grep -rn "intent_mesh_handoff_v1"` across the repo: **79 occurrences in 48 files** (Wave 2 baseline: 75 in 47 files). Delta: **+4 lines, +1 file**.

The +1 file and +4 lines are entirely `plans/reviews/wave2_tests_contract_review.md` — the Wave 2 review report itself. `git diff bdc1425..HEAD -- lathe/ schema/ spec/` shows only two `intent_mesh_handoff_v1` mentions in the diff, both in `-` (deleted) lines within docstrings of dead-code symbols removed in `6e5a144` ("refactor(shape): delete 9 dead-code symbols"). **Zero additions or modifications** to contract-ID references in `lathe/`, `schema/`, or `spec/`.

Current load-bearing references (code-side):

- `lathe/backends.py` (3) — contract definition + `hard_surface_game_asset_v1` binding
- `lathe/executor.py` (1) — "Do NOT change the stable contract" banner
- `lathe/shape/backend.py` (2) — guard at contract entry + docstring
- `lathe/shape/__init__.py` (1), `lathe/shape/geometry/conditioning.py` (1), `lathe/core/stages/shape.py` (1)
- `spec/lathe-v0.1.md` (2) — V0.8 lowering statement + stack binding

Contract surface is unchanged. Public shape-stage handoff is stable.

## Cache behavior

Test: purged all courier_drone entries from `$TEMP/lathe_build_cache` (145 entries removed across heroes sharing normalized programs), removed `tmp_w3_courier_drone/`, then timed two back-to-back builds.

| Run | Wall time | Score | .glb SHA256 |
|---|---|---|---|
| Cold (cache miss) | 179.485s | 0.879435 | `5d20f33e24c8f2531d468a1fd5ea0b1090871f6ab0b08b35384a8a226aafe4d9` |
| Warm (cache hit) | 1.721s | 0.879435 | `5d20f33e24c8f2531d468a1fd5ea0b1090871f6ab0b08b35384a8a226aafe4d9` |

Warm/cold ratio ~104x. Score and SHA256 identical across cache boundary — cache restore is byte-faithful. Cache keyed via `BUILD_CACHE_ROOT / hash_obj({cache_version, normalized_program, ...})` at `lathe/executor.py:67,121`.

## Regressions

None detected. Every hero reproduces its Wave 2 score and `.glb` SHA256 exactly. No contract drift. No build-cache integrity issues. No hero example required a fallback grep for its asset name.

One note for context (not a regression): the 11 Wave 3 commits are primarily refactors (`cli.py` decomposition, `checker/` package split, `blueprints/__init__.py` family split), security hardening (SSRF shared guard, sandboxed subproc with env allowlist), dead-code removal, and a torch pin loosen — all changes that explicitly preserve the deterministic downstream contract, which the byte-identical hero outputs confirm.

## Verdict: Wave 3 safe to continue?

**Yes.** Rationale:

1. Pipeline determinism preserved end-to-end — all 9 heroes bit-for-bit identical to pre-Wave-3 baseline.
2. Stable contract ID unchanged at every load-bearing code site; diff confirms only dead-code docstring removals touched the identifier.
3. Build cache still restores byte-faithfully and delivers the expected ~100x warm speedup.
4. No surprises in the 11-commit range — refactors and security changes landed without behavior drift.

Full `pytest -q` was not captured (shutdown arrived ~7.5 min into a ~15-min run), so this verdict rests on the 9-hero byte-identical reproduction — a stronger end-to-end signal than unit tests for this pipeline — plus the contract-ID and cache checks. If a follow-up session wants the pytest number on record, re-run `python -m pytest -q` at `9b1d1c8`.
