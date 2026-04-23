# Review: `plans/07_security.md`

## Summary verdict
The plan is comprehensive, well-sequenced, and the cited code lines hold up under verification — every CRITICAL gap (unvalidated JSON, late content-type check, unhardened subprocess, path traversal) maps to real code. It will plausibly reach ~9/10 as written, but two gaps block a true 10/10: the plan misses a second `urlopen` call site (`capabilities.py:395–397`, same SSRF vector as Hunyuan) and a second unvalidated `subprocess.run` (`executor.py:1548`, same Blender topology attack surface), and Phase 5's "containerize Blender" step is materially harder than a single bullet suggests.

## Line-citation verification

| Plan claim | Verified? | Actual code |
|---|---|---|
| `runtime_config.py:66` — `json.loads(Path(path).read_text(...))` no validation | YES | `raw = json.loads(Path(path).read_text(encoding="utf-8"))` (line 66). The only guard is `isinstance(raw, dict)` on line 67. No try/except, no size cap, no schema. |
| `shape_providers.py:567` — reads binary body BEFORE content-type check | YES, essentially | `raw = resp.read()` is line 554; the `content_type` check that would reject JSON-instead-of-mesh is line 567 — body is fully consumed before that gate. Worse: no size cap on `resp.read()`, so a malicious server can OOM the process. |
| `blender_execution.py:210–228` — `subprocess.run(..., check=False)` only inspects returncode | YES | Lines 210–229; `check=False`, `capture_output=True`, `timeout=300`. Return dict at 230 only looks at `proc.returncode == 0 and output_blend.exists()` — stderr is tailed but not scanned for `Traceback`/`Fatal`/`Segmentation fault`. Env is inherited wholesale (no `env=` kwarg). |
| Hunyuan `url_construction` is `base_url + "/generate"` | YES | `shape_providers.py:650` — direct string concat of user-supplied `base_url` with a fixed suffix. No scheme check, no host allowlist, no DNS-pin. |
| `--factory-startup` in use | YES | `blender_execution.py:214`, `executor.py:1552` |
| `allow_autoexec=False` default | YES | `runtime_config.py:42` (`DEFAULT_RUNTIME_CONFIG`) |
| `--python` script path under `Path(__file__).resolve().parents[1] / "scripts"` | YES, but unenforced | Both `blender_execution.py:209` and `executor.py:1545` compute this, but nothing rejects a different value if a refactor ever lets a config override it. |

## Coverage vs original findings

| Finding | Addressed? | Phase |
|---|---|---|
| Unvalidated `json.loads` in runtime_config | YES | 1 |
| Hunyuan reads body before content-type | YES | 3 |
| `subprocess.run(check=False)` stderr unscanned | YES | 4 |
| No path-traversal guards on `--out`/refs | YES | 2 |
| `>=` pins without lockfile | YES | 7 |
| SSRF / no URL allowlist / no outbound timeout audit | YES | 3 |
| No SBOM | YES | 9 |
| No SECURITY.md | YES | 8, 12 |
| No pip-audit / Dependabot / CodeQL / Trivy | YES | 7, 10 |
| No gitleaks | YES | 8 |
| Trimesh parsing from untrusted sources (no size/format validation) | YES | 6 |
| Blender subprocess RCE via refs | YES | 5 |
| Codex ImageGen external-service audit | Partial | 3 mentions it in passing; no dedicated auth/ratelimit phase |

## Existing defenses (already in place)

Verified from code, so the plan's "starting posture" claim holds:

- No `yaml`, `pickle.load`, `marshal.loads`, `eval`, `exec`, `shell=True`, or `tempfile.mktemp` anywhere in `lathe/` (grepped, zero matches).
- Blender: `--factory-startup` + `--background` on both invocations; `allow_autoexec` defaults false; `--python` points at a repo-owned script, never at user-supplied content; no `--python-expr`.
- Runtime config rejects non-object JSON (`isinstance(raw, dict)` at `runtime_config.py:67`) — tiny, but it's a guard.
- `_hunyuan_safe_text` (line 533) truncates response bodies in error traces to 400 bytes, which is a partial secrets-leak mitigation.
- No `jsonschema` usage today (confirmed: only referenced in `cli.py`/`doctor.py` via imports that don't validate runtime_config). Plan's Phase 1 premise is correct.

## Gaps the plan misses

1. **Second `urlopen` call site not migrated.** `capabilities.py:395–397` (`probe_hunyuan_endpoint`) does a `urllib.request.urlopen(req, timeout=timeout_s)` against the user-supplied `base_url` with the same SSRF surface as `_hunyuan_request`. Phase 3 only names `shape_providers.py:538–608`; the doctor-path probe reaches RFC1918 and cloud-metadata endpoints with identical ease. **Add to Phase 3 step 2.**
2. **Second unhardened `subprocess.run`.** `executor.py:1548` (`_run_blender_topology`) is structurally identical to `blender_execution.py:210` — same `check=False`, same env inheritance, same unscanned stderr, same 300s timeout. Phase 4 step 3 ("audit every `subprocess.run`") will catch it, but it should be named explicitly alongside `blender_execution.py`.
3. **JSON-bomb / deep-nesting on every other `json.loads` ingress.** The plan lists 10 files with `json.loads` (26 occurrences); Phase 1 step 4 names three. `eval_harness.py:9`, `bench_runtime.py`, `executor.py`, `geometry_kernel.py`, `schema.py` all call `json.loads` on disk/untrusted bytes — most are on build-produced artifacts, but during a resume-from-cache or resolver round-trip, a poisoned prior build can reinfect. Plan should say "audit all 26" explicitly.
4. **Windows-specific path hazards.** Phase 2 mentions NTFS ADS and UNC but not: 8.3 short names (`PROGRA~1`), case-insensitive collisions, trailing-dot/space stripping (Windows silently normalizes `foo.` → `foo`), `\\?\` long-path disables normalization, `NTUSER.DAT` reserved on HKCU roots. `safe_resolve` needs to reject these on Windows specifically.
5. **Symlink TOCTOU.** Phase 2's "reject if `is_symlink()` along any component" is the correct instinct, but `is_symlink()` → `resolve()` → `open()` has a race window. `O_NOFOLLOW`-equivalent on Windows is `FILE_FLAG_OPEN_REPARSE_POINT`; Python's stdlib doesn't expose it. Call this residual risk out in Phase 2 or accept it.
6. **`.lth` prompt injection into learned providers.** `.lth` comments and free-text fields (e.g. `intent.role`, authoring text) flow into Hunyuan/Codex prompts via `shape_providers.py` and `codex_imagegen_bridge.py:84–98`. A third-party `.lth` from `std/libraries/` or a shared kit could prompt-inject the learned backend to exfiltrate via the generated mesh/texture. Plan's Phase 11 threat model names "malicious .lth author" but doesn't enumerate prompt injection as a mitigation target.
7. **`Image.MAX_IMAGE_PIXELS` is a global.** Phase 6 step 3 sets it, but PIL resets it per-process and libraries (including trimesh's GLTF loader) may re-raise it. Need to set it at import time in `lathe/__init__.py`, not inside `safe_load_mesh`.
8. **No mention of `tarfile`/`zipfile` traversal.** `.glb` is a container format; trimesh/pygltflib unpacks it. If any code path unpacks user-supplied zips (USD assets, .blend autosaves) via stdlib `zipfile.extractall` or `tarfile.extractall`, CVE-2007-4559 applies. Worth a grep + explicit Phase 6 bullet.
9. **Temp-file naming.** Plan doesn't cover `work_dir / f"hunyuan_candidate_{index:02d}.{out_type}"` (`shape_providers.py:657`) predictability — if `work_dir` is world-writable or a symlink target, an attacker can plant a file or race the write. Low severity on Windows single-user, but worth naming.
10. **`direct_url.json` parsing in `capabilities.py:48`.** `json.loads(raw)` on pip distribution metadata — trusted, but worth noting Phase 1 covers ALL `json.loads`, not just user-facing.

## Feasibility

- **Sequencing.** CRITICAL (Phases 1–3) before HIGH (4–6) before supply-chain/SBOM/CI is correct. Phase 2 (paths) before Phase 4 (subprocess) is important because `run_sandboxed` reuses `safe_resolve`.
- **Phase 5 realism.** The Docker/`--network=none`/seccomp bullet is a 2–4 week project on its own, not a step; Blender in-container still needs GPU passthrough for bake/render which breaks `--network=none` assumptions. The documentation + policy-refuse parts (steps 1–3) are realistic; step 4 (`LATHE_BLENDER_CONTAINER` flag + Dockerfile) should be a separate plan or marked as Phase 5b stretch.
- **Exit criterion "100% of user-ingress bytes flow through `lathe/validation.py` ..."** — enforcing this via a test that imports every module and greps AST for `json.loads`/`urlopen`/`subprocess.run` is doable but brittle; AST-scan via a CI script is more reliable than a pytest.
- **Exit criterion "stage IDs preserved end-to-end; no contract drift"** is a strong requirement but correctly protects the CLAUDE.md invariant `lathe.shape.intent_mesh_handoff_v1`.
- **Budget.** 12 phases with tests + CI wiring is ~6–10 engineer-weeks. No budget is stated in the plan; should be.

## 10/10 verdict

**Not yet — estimated 8.5/10 as written.** Blockers:

1. Name the second SSRF site (`capabilities.py:395`) and the second subprocess site (`executor.py:1548`) explicitly, not via "audit every call site."
2. Split Phase 5 step 4 (containerization) into its own phase or mark stretch — as written it inflates the plan's apparent completeness.
3. Add explicit coverage for `.lth` prompt injection into learned providers (Phase 11 threat model row + a Phase 3 mitigation: strip/length-cap free-text fields before they reach outbound HTTP).
4. Add Windows-specific path rules (8.3, trailing dot/space, `\\?\`) to Phase 2 step 1, and accept-document the symlink TOCTOU residual.
5. Expand Phase 1 step 4 from 3 ingresses to "all 26 `json.loads` sites, with validation at trust-boundary sites and assertion-mode at internal sites."

With those added, the plan is a credible 10/10 path.

## Relevant files

- `D:\lathe_v0_1\lathe\runtime_config.py` (lines 63–70, 102–176)
- `D:\lathe_v0_1\lathe\shape_providers.py` (lines 538–608, 611–661, 650 url concat)
- `D:\lathe_v0_1\lathe\blender_execution.py` (lines 208–235)
- `D:\lathe_v0_1\lathe\executor.py` (lines 1539–1582) — **missed in plan**
- `D:\lathe_v0_1\lathe\capabilities.py` (lines 388–420) — **missed in plan**
- `D:\lathe_v0_1\lathe\codex_imagegen_bridge.py` (lines 52–98)
- `D:\lathe_v0_1\lathe\bridge\blender_plan.py` (contracts only, no exec)
