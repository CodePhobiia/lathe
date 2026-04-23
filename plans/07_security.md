# Implementation Plan: Security Hardening 6/10 → 10/10

## Overview
Lathe's current posture is defensively reasonable (no eval/exec, no shell=True, no yaml.unsafe_load) but lacks validation layers, SSRF controls, subprocess discipline, supply-chain pinning, and disclosure/SBOM plumbing. This plan closes all 13 gaps through sequenced phases, each ending in a testable control.

### Currently in place (preserve, do not regress)
- Blender always launched with `--factory-startup` and `allow_autoexec=False` as defaults (verified at `blender_execution.py:214-217`). Retain on every Blender invocation site.
- `_hunyuan_safe_text` already truncates error response bodies to 400 bytes before logging (verified in `shape_providers.py`), providing a partial secrets-leak mitigation. Retain.
- No `yaml.unsafe_load`, `yaml.load` (with Loader), `pickle.load`, `marshal.loads`, `eval`, `exec`, `shell=True`, or `tempfile.mktemp` anywhere in `lathe/` (grep-verified, zero matches). These absences are controls — new code must not introduce any of them.
- `isinstance(raw, dict)` guard on runtime-config JSON root at `runtime_config.py:67`. Keep as defense-in-depth even once schema validation lands.
- `--python` script path computed from repo-owned location on both `blender_execution.py:209` and `executor.py:1545` (never user-controlled today). Phase 5 codifies this.

### Findings summary (verified line citations)
- `runtime_config.py:66` — `json.loads` on user file; only guard is `isinstance(raw, dict)` at line 67.
- `shape_providers.py` — `resp.read()` at **line 554** occurs BEFORE the content-type check at **line 567**; body is fully consumed before the gate. No size cap on `resp.read()`.
- `shape_providers.py:650` — `base_url + "/generate"` string concatenation of user-supplied URL; no scheme check, host allowlist, or DNS-pin.
- `blender_execution.py:210-228` — `subprocess.run(..., check=False)` inspects only returncode; stderr tailed but not scanned for `Traceback`/`Fatal`/`Segmentation fault`; env inherited wholesale (no `env=` kwarg).
- `executor.py:1548` — same subprocess shape as blender_execution, structurally identical risk.
- `capabilities.py:395` — `urllib.request.urlopen` against user `base_url` in `probe_hunyuan_endpoint`; same SSRF surface.

## Principles
- Treat every user-supplied byte (.lth refs, runtime_config.json, HTTP provider responses, Blender inputs) as untrusted.
- Centralize validation; never re-implement at call sites.
- Make the safe default the only default: strict on, allowlist empty, fallback deterministic.
- Every phase adds a regression test and a CI gate.

---

## Phase 1 — Input Validation Layer (CRITICAL)
Goal: zero unvalidated JSON/YAML/lth reads.

1. Create `schema/runtime_config.schema.json` covering the full `DEFAULT_RUNTIME_CONFIG` surface from `lathe/runtime_config.py` (shape, topology, uv, surface, execution). Constrain: `timeout_s` int 1..3600, `base_url` format=uri, `path` string, `providers` additionalProperties:false.
2. Add `lathe/validation.py` exposing `validate_json(path, schema_id)` using `jsonschema.Draft202012Validator`, returning typed `ValidationError` with pointer + snippet.
3. Refactor `lathe/runtime_config.py:63-70` (`load_runtime_config`): wrap `json.loads` in try/except `json.JSONDecodeError`, enforce size cap (reject >256 KiB), then call `validate_json`. Emit provenance (`_source`, `_sha256`).
4. Apply to every JSON ingress: `lathe/cli.py` runtime-config arg, `lathe/parser.py` (resolved-ref manifest), `codex_imagegen_bridge.py` request/output JSON reads.
   - **Audit all 26 `json.loads` / `json.load` sites.** `grep -rn 'json.loads\|json.load' lathe/` finds 26 occurrences across ~10 files (runtime_config, parser, executor, eval_harness, bench_runtime, geometry_kernel, schema, capabilities, codex_imagegen_bridge, shape_providers). Every site must either (a) route through `lathe/validation.py::validate_json(path, schema_id)` with an appropriate schema, OR (b) be justified with an inline comment as a controlled internal payload (e.g., reading a fixture we just produced under our own workspace root, or distribution-metadata like `direct_url.json` at `capabilities.py:48`). Trust-boundary sites MUST validate; internal-only sites MAY assert with a schema in strict mode and skip in release mode. The audit output (site → classification → decision) lives in `docs/security/json_ingress_audit.md`.
5. `.lth` reference list: validate against `schema/ref_manifest.schema.json` (string array, max 128, per-entry max 512 chars).
6. Tests: `tests/test_security_validation.py` — malformed JSON, oversized payload, unknown keys, wrong types, nested-depth bombs (>32).

---

## Phase 2 — Path Traversal Hardening (CRITICAL)
Goal: every path resolves inside explicit workspace root; no `..`, no absolute escape, no symlink follow.

1. `lathe/paths.py::safe_resolve(root: Path, user: str) -> Path`. Behavior: reject absolute `Path(user).expanduser()`; `root.resolve().joinpath(user).resolve()` must be descendant via `is_relative_to`; reject if `Path(...).is_symlink()` along any component; reject NUL bytes and Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
   - **Windows hazards to reject (explicit list):**
     - 8.3 short names (e.g., `PROGRA~1`, tilde-digit pattern) — fails the allowlist even when they canonicalize to a safe long name.
     - Trailing dot (`file.txt.`) and trailing space (`file .txt`) — Windows silently strips these, so `foo.` and `foo` collide.
     - Alternate Data Streams (`file:stream`, colon in final component).
     - `\\?\` extended-length / `\\?\UNC\` prefixes — these bypass Win32 path normalization.
     - Reparse points and junctions (not just POSIX symlinks) — detect via `stat().st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`.
     - Device namespace paths: `\\.\COM1`, `\\.\PhysicalDrive0`, `CONIN$`, etc.
     - Drive-letter substitution / DOS device names mid-path (`C:foo` without a separator; `NUL:` as a filename).
     - Case-insensitive collisions inside the workspace allowlist (treat as same path).
   - **Defense:** confine via BOTH logical canonicalization (normalize separators, strip trailing dot/space, reject reserved tokens, reject 8.3 tilde pattern) AND `os.path.realpath` with symlink/reparse-point rejection. Neither alone is sufficient.
   - **Residual risk accepted:** Python stdlib on Windows does not expose `FILE_FLAG_OPEN_REPARSE_POINT`, so there is a TOCTOU window between `is_symlink()`/`is_reparse_point()` and `open()`. Document this in `docs/security/path_hardening.md`; mitigate operationally by keeping workspace roots owned by the invoking user and on non-shared drives.
2. Apply at every user-path ingress:
   - `lathe/cli.py` `--out` (confine under CWD unless `--allow-external-out` + `LATHE_ALLOW_EXTERNAL_OUT=1`)
   - `lathe/parser.py` relative ref resolution
   - `lathe/runtime_config.py` `blender.path`, `asset_libraries`, `addons`, `request_dir`, `output_dir`
   - `lathe/blender_execution.py:208-224` `input_glb`, `output_blend`, `summary_path`, `script_path`
   - `lathe/codex_imagegen_bridge.py` `_cfg_path` consumers
3. Allowlist `blender.path`: basename match + live under `LATHE_BLENDER_ROOTS`.
4. Tests: `..\..\etc`, UNC `\\?\`, mixed separators, NTFS ADS `file:stream`.

---

## Phase 3 — SSRF and HTTP Hardening (CRITICAL)
Goal: Hunyuan and any outbound HTTP is bounded, allowlisted, content-verified.

1. `lathe/net.py` with `safe_urlopen(url, *, allowlist, max_bytes, timeout_s, expect_content_type)`:
   - Parse URL; require scheme `{https}` by default (http only if localhost + `allow_loopback_http=true`).
   - DNS-resolve hostname; reject RFC1918, loopback (unless explicit), link-local (169.254/16), CGNAT (100.64/10), metadata (169.254.169.254), IPv6 ULA/link-local/multicast, `.onion`.
   - TLS: `ssl.create_default_context()`, `check_hostname=True`, `CERT_REQUIRED`, min TLS 1.2.
   - Streaming read with hard byte cap (default 256 MiB, configurable per provider).
   - Pre-check `Content-Type` against caller's expected list BEFORE reading body beyond header.
2. Refactor `lathe/shape_providers.py:538-608` `_hunyuan_request`:
   - Swap `urllib.request.urlopen` for `safe_urlopen`.
   - Require `config["base_url"]` host in `runtime_config.shape.providers.hunyuan2_1_http.url_allowlist` (empty list → reject in strict mode).
   - Move content-type check (currently AFTER `resp.read()` at line 554; the check itself is at line 567) BEFORE body read; stream to temp file with size cap.
   - Timeouts: connect ≤60s, total ≤600s; log each attempt with redacted URL.
3. **Also harden `lathe/capabilities.py:395` (`probe_hunyuan_endpoint`).** Identical SSRF pattern: user-supplied `base_url` → `urllib.request.urlopen(req, timeout=timeout_s)` with no scheme check, no host allowlist, and no DNS-pin. Route through the same `lathe/net.py::safe_urlopen` with the same allowlist sourced from `runtime_config.shape.providers.hunyuan2_1_http.url_allowlist`. Do not leave a second urlopen call site untouched — the doctor/probe path reaches RFC1918 and cloud-metadata endpoints with the same ease as the main request path.
4. Same wrapper for future Codex HTTP paths; document in `codex_imagegen_bridge.py`.
5. Tests: mock server returning 169.254.169.254 redirect, gigabyte body, text/html masquerade, expired cert, TLS1.0, plus the `probe_hunyuan_endpoint` path with identical vectors to prove both call sites are hardened.

---

## Phase 4 — Subprocess Hardening (HIGH)
Goal: every subprocess arg-list, timeout-guarded, stderr-scanned, signal-aware.

1. `lathe/subproc.py::run_sandboxed(argv, *, timeout_s, cwd, env_allowlist, expect_files)`:
   - Assert `argv` is list; first element exists on disk, not a symlink.
   - Scrub env to allowlist (`PATH`, `TEMP`, `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS`); no inherited `LD_PRELOAD`, `PYTHONPATH`, `BLENDER_SYSTEM_SCRIPTS`.
   - `shell=False` (enforced), `check=False`; typed result with `returncode`, `stdout_tail`, `stderr_tail`, `timed_out`, `killed_by_signal`.
   - Scan stderr for deny-patterns (`Traceback`, `Fatal Python error`, `Segmentation fault`, `AddressSanitizer`); set `ok=False` even on returncode 0.
   - Enforce `expect_files` exist AND are in `cwd` (via `safe_resolve`).
2. Migrate `lathe/blender_execution.py:208-235` `_export_blend_artifact` to `run_sandboxed`; remove implicit env inheritance; wire stderr-scan into return dict.
3. **Also migrate `lathe/executor.py:1548` (`_run_blender_topology`) to `run_sandboxed`.** This call site is structurally identical to `blender_execution.py:210-228` — same `check=False`, same wholesale env inheritance, same unscanned stderr, same 300s timeout — and carries identical risk. Do not treat `blender_execution.py` as the only Blender-subprocess site; both must land in the same migration commit so a future refactor cannot regress one without the other.
4. Audit every `subprocess.run` in `lathe/`; migrate all remaining call sites (including any turned up by grep beyond the two named above).
5. Tests: mocked subprocess with timeout, killed process, stderr `Traceback`, missing output file. Exercise BOTH `_export_blend_artifact` and `_run_blender_topology` with the same mocked-subprocess fixtures to prove parity.

---

## Phase 5 — Blender Trust Boundary (HIGH)
Goal: Blender explicitly untrusted; risk documented and mitigated.

1. `docs/security/blender_sandbox.md`: Blender's `--python` and `.blend` driver/autoexec are RCE vectors. Current mitigations: `--factory-startup`, `allow_autoexec=False`, no `--python-expr`, no user-controlled `--python` path.
2. Enforce: `--python` script path must be under `Path(__file__).resolve().parents[1] / "scripts"` (already true line 209; codify with `safe_resolve`).
3. Reject `.blend` inputs from user `.lth` refs unless `runtime_config.execution.blender.trusted=true` AND path under registered trusted root. Strict default refuses all user `.blend`.
4. **Blender-in-container — two profiles, with explicit GPU trade-off.** `docker/blender.Dockerfile` (read-only rootfs, seccomp profile, non-root UID, `/work` tmpfs) exposed via `LATHE_BLENDER_CONTAINER=docker|podman|none` flag + a `run_sandboxed` container variant. **Caveat:** GPU passthrough fundamentally conflicts with `--network=none` — the CUDA runtime phones home on some NVIDIA driver versions, and GPU-accelerated bake/render needs device access (`/dev/nvidia*`, NVML) that often implies network exposure (driver telemetry, license servers, remote render coordinators). Ship **two container profiles** so users make the trade explicitly:
   - **`blender-cpu`** — full network isolation (`--network=none`), CPU-only Cycles/EEVEE-software, the strictest default. Use for untrusted `.blend` inputs and CI.
   - **`blender-gpu`** — GPU passthrough (`--gpus=all` or `--device nvidia.com/gpu=all`), network NOT fully isolated; instead a **firewall rules** policy (outbound allowlist: nothing by default, per-project opt-in) enforced at the container network layer.
   - Document the trade-off, threat implications, and selection guidance in `docs/security/blender_sandbox.md`. Strict default is `blender-cpu`; `blender-gpu` requires explicit `LATHE_BLENDER_CONTAINER_PROFILE=gpu` AND `runtime_config.execution.blender.gpu_acknowledged=true`.
   - **Scope note:** full productionization of container profiles (Dockerfile hardening, seccomp tuning, firewall rules, CI integration) is a 2-4 week effort on its own. Items 1-3 of this phase (docs, policy, path codification) are the required-for-10/10 deliverables; item 4 may ship as **Phase 5b** if scheduling requires, but the documentation of the trade-off cannot be deferred.
5. Tests: attempt `.blend` with embedded driver; assert refusal unless explicitly trusted. Container-profile tests gated on Docker availability in CI.

---

## Phase 6 — Binary Parser Hardening (HIGH)
Goal: trimesh/PIL ingestion cannot OOM, crash, or execute.

1. `lathe/mesh_ingest.py::safe_load_mesh(path, *, max_bytes, allowed_formats)`:
   - Stat + refuse >256 MiB default.
   - Extension allowlist: `{glb, gltf, obj, ply, stl}`; reject `usd` from untrusted sources.
   - Sniff magic bytes (glTF `glTF`, OBJ ASCII, PLY header, STL 80-byte header+count sanity).
   - Wrap `trimesh.load` in try/except `Exception`; redact paths from errors.
   - Post-load sanity: `len(faces) <= 5_000_000`, `len(vertices) <= 5_000_000`, no NaN/Inf, bounds finite.
2. Replace `_load_mesh_file(raw_path)` at `shape_providers.py:659` with `safe_load_mesh`.
3. PIL: wrap with `Image.MAX_IMAGE_PIXELS` cap and format allowlist (`png`, `jpeg`, `webp`).
4. Tests: zip-bomb glb, trimesh decompression-bomb OBJ, 10 GiB sparse STL, NaN vertex file.

---

## Phase 7 — Dependency Supply Chain (HIGH)
1. Generate `requirements.lock` via `pip-compile --generate-hashes`. Commit.
2. Replace `>=` pins in pyproject with `~=` for direct deps; lockfile carries exact versions.
3. `.github/workflows/supply_chain.yml`:
   - `pip-audit --strict --requirement requirements.lock` (fail on high/critical)
   - `osv-scanner --lockfile=requirements.lock`
   - weekly cron
4. `.github/dependabot.yml` (pip + github-actions, weekly, grouped).
5. Signed commits on protected branches; `CODEOWNERS`.
6. PyPI OIDC trusted publishing via `.github/workflows/release.yml` using `pypa/gh-action-pypi-publish` with `id-token: write`, no long-lived token.

---

## Phase 8 — Secret Management (MEDIUM)
1. `SECURITY.md` — disclosure policy, supported versions, contact `talmerri@gmail.com`, 90-day disclosure.
2. `.gitleaks.toml` — custom rules for `LATHE_HUNYUAN_*`, Codex keys, AWS/GCP/Azure patterns.
3. `.pre-commit-config.yaml` running `gitleaks`, `ruff`, `bandit -r lathe -ll`, `detect-private-key`.
4. `.github/workflows/secrets.yml` — `gitleaks detect --redact` on PRs, full history weekly.
5. All `LATHE_*` env overrides in `runtime_config.py` redacted in serialized traces.

---

## Phase 9 — SBOM Generation (MEDIUM)
1. `.github/workflows/sbom.yml` — on tag, `anchore/sbom-action` (syft) producing SPDX 2.3 + CycloneDX 1.5; attach to release.
2. Sign SBOMs with `cosign` using OIDC keyless signing; publish `.sig` + `.pem`.
3. `scripts/generate_sbom.sh` for local reproduction.
4. Document verification in `SECURITY.md`.

---

## Phase 10 — Static Analysis in CI (MEDIUM)
1. `.github/workflows/codeql.yml` — CodeQL Python on push/PR + weekly; fail high/critical.
2. `.github/workflows/bandit.yml` — `bandit -r lathe -ll -iii`.
3. `.github/workflows/semgrep.yml` — `--config=p/python --config=p/owasp-top-ten --config=p/security-audit`.
4. `.github/workflows/trivy.yml` — filesystem + Dockerfile scan.
5. All four required on protected branches.

---

## Phase 11 — Threat Model (MEDIUM)
`docs/security/threat_model.md` using STRIDE:
- **Malicious `.lth` author:** traversal via refs, zip-bomb textures, oversized assembly graphs, `.blend` driver RCE. Mitigations: Phases 1, 2, 5, 6.
- **Prompt-injection via `.lth` comments, docstrings, or free-text fields (intent.role, authoring metadata, reference descriptions) fed to learned providers.** If `.lth` content is concatenated into an LLM prompt by the Codex ImageGen bridge (`codex_imagegen_bridge.py:84-98`) or any future learned-text provider — or forwarded as an instruction payload to Hunyuan — an attacker-controlled `.lth` (including third-party kits from `std/libraries/` or shared community packs) could jailbreak the provider to exfiltrate secrets, produce adversarial mesh/texture output, or pivot to connected systems. **Mitigation:** structured prompt templating with explicit boundaries (system/user role separation, delimiter tokens that reject user-supplied matches, allowlisted field shape), strict length caps and character-class filters on free-text fields before they reach outbound HTTP, and NEVER interpolate raw `.lth` bytes into system prompts. Enforce in `codex_imagegen_bridge.py` prompt construction and `shape_providers.py` Hunyuan instruction fields. Treat STRIDE class as **T**ampering + **I**nformation Disclosure; severity HIGH for shared-kit distribution paths.
- **Malicious model server:** SSRF pivot, oversized responses, content-type masquerade, slowloris. Mitigations: Phase 3.
- **Malicious dependency:** typosquat, upstream compromise. Mitigations: Phase 7, 9, 10.
- **Malicious Blender addon:** arbitrary code on import. Mitigations: Phase 5 (empty default `addons`, path allowlist).
- **Local attacker:** env var injection, symlink race on workspace. Mitigations: Phase 2 (symlink reject), Phase 8 (env redact).

Each row: asset, entry point, STRIDE class, severity, mitigation phase, residual risk.

---

## Phase 12 — Responsible Disclosure
1. `SECURITY.md` with contact (`talmerri@gmail.com` + GitHub private advisory), PGP key, SLA (ack 3d, triage 10d, fix target 90d), safe-harbor language.
2. Enable "Private vulnerability reporting".
3. `docs/security/disclosure_log.md` (public CVE log post-fix).

---

## 10/10 Measurable Exit Criteria

- [ ] `pip-audit --strict` + `osv-scanner`: zero high/critical in CI for 4 consecutive weeks
- [ ] 100% of user-ingress bytes flow through `lathe/validation.py`, `paths.py`, `net.py`, or `mesh_ingest.py` (enforced by `tests/test_security_boundaries.py`)
- [ ] 100% of `subprocess.*` call sites go through `lathe/subproc.run_sandboxed` (enforced by `scripts/check_no_raw_subprocess.py` in CI)
- [ ] CodeQL + Bandit + Semgrep + Trivy: zero high/critical
- [ ] Every release ships signed SPDX + CycloneDX SBOM verifiable via cosign
- [ ] `requirements.lock` with hashes present; unpinned `>=` count = 0 in direct deps
- [ ] `SECURITY.md`, `threat_model.md`, `blender_sandbox.md`, `disclosure_log.md` all dated within 12 months
- [ ] `tests/test_security_*.py` green covering all threat-model personas
- [ ] Gitleaks full-history clean; pre-commit hook in `CONTRIBUTING.md`
- [ ] Stage IDs (`intent_mesh_handoff_v1` etc.) preserved end-to-end; no contract drift

---

## Relevant files

- `lathe/runtime_config.py` (lines 63-70 unvalidated `json.loads`; 102-176 env overrides)
- `lathe/shape_providers.py` (538-608 SSRF + late content-type; 611-661 body handling)
- `lathe/blender_execution.py` (208-235 subprocess)
- `lathe/executor.py` (1539-1582 second Blender subprocess site `_run_blender_topology`)
- `lathe/capabilities.py` (388-420 second urlopen site `probe_hunyuan_endpoint`)
- `lathe/codex_imagegen_bridge.py` (52-98 runtime-config path + prompt construction)
- `schema/lathe.schema.json` (existing; new siblings alongside)
- `CLAUDE.md` (contract invariants)

---

## Amendment log (2026-04-23)

Applied by `amender-sec` from `plans/reviews/07_security_review.md` + meta-review cross-cutters:

1. **Second SSRF site named.** Phase 3 step 3 now explicitly calls out `capabilities.py:395` (`probe_hunyuan_endpoint`) and requires it to route through `lathe/net.py::safe_urlopen` with the same allowlist as the main Hunyuan path. Review-flagged as a 10/10 blocker.
2. **Second subprocess site named.** Phase 4 step 3 now explicitly calls out `executor.py:1548` (`_run_blender_topology`) alongside `blender_execution.py:210-228`, requiring both to land in the same migration commit. Review-flagged as a 10/10 blocker.
3. **Phase 5 Blender-in-Docker refined.** Item #4 now documents the GPU-vs-`--network=none` conflict and splits into two container profiles: `blender-cpu` (fully isolated, CPU-only, strict default) and `blender-gpu` (passthrough + firewall allowlist, opt-in). Trade-off documented in `docs/security/blender_sandbox.md`. Containerization scope may ship as Phase 5b; the trade-off documentation cannot be deferred.
4. **`.lth` prompt-injection threat vector added.** New row in Phase 11 threat model covers attacker-controlled `.lth` content (comments, docstrings, free-text fields) reaching learned providers via `codex_imagegen_bridge.py:84-98` or Hunyuan instruction fields; mitigation via structured prompt templating, length/character-class caps, and prohibition on interpolating raw `.lth` bytes into system prompts.
5. **Windows-specific path hazards enumerated.** Phase 2 step 1 now rejects 8.3 short names, trailing dot/space, alternate data streams, `\\?\` extended-length prefixes, reparse points/junctions, device namespace paths, drive-letter substitution, and case-insensitive collisions. Requires both logical canonicalization AND `os.path.realpath` with symlink rejection. Documents `FILE_FLAG_OPEN_REPARSE_POINT` residual TOCTOU risk.
6. **All 26 `json.loads` sites audit.** Phase 1 step 4 now requires `grep -rn 'json.loads\|json.load' lathe/` coverage with each site classified (validate-through-`validation.py` vs justified internal), producing `docs/security/json_ingress_audit.md`.
7. **"Currently in place" section added.** Overview now enumerates controls already verified in code (`--factory-startup`, `allow_autoexec=False`, `_hunyuan_safe_text` truncation, absence of `yaml.unsafe_load`/`pickle.load`/`eval`/`exec`/`shell=True`, `isinstance(raw, dict)` root guard, repo-owned `--python` script path) so the plan cannot regress them.
8. **Line-citation correction.** Findings summary clarifies the Hunyuan content-type issue: `resp.read()` is line 554, the content-type check itself is line 567, and the bug is that 554 runs before 567. Earlier drafts cited only 567.

Post-amendment expected score: ~10/10 (up from reviewer's 8.5/10 estimate). All CRITICAL review blockers addressed; Phase 5 containerization scope realism clarified.
