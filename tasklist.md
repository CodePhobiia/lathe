# Lathe 10/10 Repository Task List

This checklist defines the work required to bring Lathe to a 10/10 state across code quality, documentation, architecture, test coverage, developer experience, maintenance, security, product quality, product value and vision, and known bugs/errors/issues.

The bar for completion is intentionally high: no shortcuts, no placeholder fixes, no hidden failures, and no claims of completion without passing validation.

## Scoring Target

Lathe reaches a 10/10 repository state only when all of the following are true:

- Code is correct, minimal, maintainable, typed where useful, consistently linted, and free of known correctness bugs.
- Documentation matches current behavior, contains complete setup/run/release guidance, and is useful to both users and contributors.
- Architecture boundaries are enforced by tests or tooling, not just convention.
- Test coverage is high, meaningful, deterministic, and covers failure paths, edge cases, providers, CLI behavior, and release workflows.
- Developer setup is reproducible from a clean clone on supported platforms.
- Maintenance signals are public, current, traceable, and release-ready.
- Security controls are active, tested, documented, and verified in CI.
- Product workflows produce polished, stable, inspectable, and useful assets.
- Product direction is clear, compelling, and backed by examples, benchmarks, and user-facing value.
- Every known bug listed here has a regression test and verified fix.

## Global Completion Gates

- [ ] All task sections in this file are complete.
- [x] `python -m pytest -q` passes in the documented developer environment.
- [x] `python -m pytest --cov=lathe --cov-report=term --cov-report=xml` passes the configured coverage threshold.
- [ ] `ruff check .` passes with the expanded project lint rules.
- [x] Type checking passes for the supported typed surface.
- [x] Security checks pass: Bandit, pip-audit, Gitleaks, Semgrep, CodeQL, and any repo-specific security tests.
- [x] All canonical examples pass `normalize`, `check`, `plan`, `materialize`, and `build`.
- [x] Public docs are regenerated or verified against current CLI output and build artifacts.
- [x] CI runs the same gates locally documented for contributors.
- [ ] A release candidate is built from a clean checkout and verified by a release checklist.
- [ ] No known major or critical issue remains open without an explicit documented release exception.

## Phase 0: Baseline, Ownership, and Release Definition

- [x] Create a tracked quality dashboard that records current scores, target scores, owners, and status for every dimension in this task list.
- [x] Convert this file into issues or milestones so progress is visible and reviewable.
- [x] Define "10/10" release acceptance criteria in `docs/release/quality-bar.md`.
- [x] Record supported platforms, Python versions, optional tools, and provider modes in one canonical support matrix.
- [x] Decide whether Lathe 0.2 is still an alpha, beta, release candidate, or stable release, then align README, package metadata, changelog, and docs.
- [x] Add a release exception process for known limitations that are intentionally deferred.
- [x] Establish a policy that every fixed bug in this file must add or update a regression test.
- [x] Add a "known limitations" document that distinguishes deliberate alpha limits from defects.
- [x] Verify the repo has a configured public remote or explicitly document that it is private/local-only.
- [x] Clean or classify generated build output directories so source files, cache artifacts, and scratch artifacts are not mixed together.

## Phase 1: Fix Known Bugs, Errors, and Issues

### Blender Sandbox Resource Limits

- [x] Reproduce the current sandbox behavior on Windows and POSIX, including CPU and memory limit enforcement.
- [x] Add tests proving Blender child processes receive resource limits rather than the parent process.
- [x] Wire the Windows Job Object assignment into the actual subprocess launch path.
- [x] Add a POSIX child-process limit hook or safe subprocess wrapper that applies limits only in the child.
- [x] Ensure failed limit application is surfaced as a hard error, not silently ignored.
- [x] Document sandbox limitations per platform.
- [x] Validate with an intentionally resource-heavy Blender fixture.

### Telemetry Privacy and Correctness

- [x] Remove persistent salt values from outbound telemetry payloads.
- [x] Replace any linkable telemetry identifiers with one-way, locally salted hashes that cannot be recomputed by ingest without the salt.
- [x] Update telemetry docs so privacy claims match implementation.
- [x] Update telemetry tests to assert that raw salts, paths, prompts, and local identifiers are never sent.
- [x] Fix build metadata extraction so telemetry correctly reports build kind, backend stack, certification outcome, and non-linkable build identity.
- [x] Add negative tests for malformed reports, missing metadata, and disabled telemetry.
- [x] Add a golden telemetry payload fixture for every supported telemetry event.

### Hunyuan Runtime Config Enforcement

- [x] Pass `providers.hunyuan2_1_http.url_allowlist` into every Hunyuan HTTP request.
- [x] Add tests that allowed URLs pass and disallowed URLs fail before network access.
- [x] Align timeout configuration names between schema, docs, and adapter implementation.
- [x] Validate runtime configs against schema before provider construction.
- [x] Add tests for missing URL, invalid scheme, loopback behavior, timeout behavior, and allowlist denial.
- [x] Update cookbook examples to match the actual accepted keys.

### Image Reference Safety

- [x] Define the allowed reference path model for image refs: project-relative only, explicit allowlist, or trusted absolute paths.
- [x] Apply safe path resolution to image refs with traversal protection.
- [x] Add maximum image byte size, dimensions, and decompression-bomb protections.
- [x] Reject unsupported image formats before decoding.
- [x] Ensure provider adapters never read or transmit image files outside the approved reference boundary.
- [x] Add tests for absolute path rejection, traversal rejection, oversized file rejection, decompression bomb rejection, and valid local refs.
- [x] Document image reference trust boundaries.

### Cache Metadata and Asset Attribution

- [x] Decide the canonical cache metadata file and schema.
- [x] Teach cache status to read current build artifacts instead of stale `manifest.json` assumptions.
- [x] Backfill or migrate old cache entries where feasible.
- [x] Ensure every cache entry records asset, variant, backend stack, cache version, source fingerprint, and created time.
- [x] Fix `lathe cache status --json` so entries are attributed to real assets instead of `<unknown>`.
- [x] Fix `lathe cache clean --asset` to operate only on matching asset entries.
- [x] Add tests for current cache layout, missing metadata, corrupt metadata, version mismatch, asset filtering, and dry-run cleanup.
- [x] Update docs and examples for cache commands.

### CLI Error Handling

- [x] Define a consistent public error contract for CLI commands.
- [x] Wrap parse, resolve, check, plan, materialize, build, cache, provider, and package failures in structured diagnostics.
- [x] Replace raw tracebacks for user-facing failures with actionable messages and non-zero exit codes.
- [x] Preserve opt-in debug traceback behavior behind a documented flag or environment setting.
- [x] Add tests for missing files, invalid syntax, bad refs, invalid runtime config, provider unavailable, unwritable output path, and corrupt cache.
- [x] Verify JSON report mode returns machine-readable errors.
- [x] Update README and CLI docs with error examples.

### Coverage and CI Ratchet Drift

- [x] Make `.coveragerc`, `pyproject.toml`, CI, and docs agree on one coverage threshold.
- [x] Raise coverage only after adding real tests, not by excluding live code.
- [x] Remove CI coverage overrides that bypass configured fail-under thresholds.
- [x] Add a coverage ratchet policy describing when and how thresholds increase.
- [x] Fix or document missing local dev dependencies that cause architecture tests to skip.
- [x] Ensure all required dev/test dependencies are installable from a clean clone.

### Quickstart and Artifact Documentation Drift

- [x] Regenerate quickstart output examples from a fresh build.
- [x] Replace stale references to root-level `manifest.json` and `trace.json`.
- [x] Document actual staged outputs: `build_report.json`, package manifest, trace manifest, previews, engine manifests, selector manifest, GLB/USD artifacts, and validation reports.
- [x] Add a docs test that verifies documented artifact paths exist after the quickstart build.
- [x] Add a docs review step to the release checklist.

## Phase 2: Code Quality to 10/10

- [x] Expand Ruff rules beyond the current minimal ratchet while keeping changes scoped and reviewed.
- [x] Enable import hygiene rules for unused imports, shadowing, complexity hot spots, and unsafe patterns.
- [ ] Add or strengthen type annotations for public APIs, providers, CLI command interfaces, stage contracts, and schema-facing data structures.
- [x] Introduce targeted mypy or pyright checking for stable modules before expanding to the whole repo.
- [x] Remove dead code, unused helpers, obsolete compatibility shims, and unreachable branches.
- [x] Replace broad `except Exception` blocks with typed exceptions unless explicitly justified and tested.
- [x] Audit all silent fallbacks and convert hidden failures into diagnostics or explicit degraded states.
- [x] Normalize logging so errors, warnings, and debug traces are structured and do not leak sensitive data.
- [ ] Review public dataclasses and dictionaries for schema drift and convert fragile untyped blobs into validated structures where appropriate.
- [ ] Reduce module complexity in any files that exceed agreed size or complexity thresholds.
- [ ] Add code comments only for non-obvious algorithms, contracts, and security-sensitive behavior.
- [x] Add contributor guidance for code style, error style, diagnostic style, and test expectations.
- [x] Run format/lint/type gates in pre-commit and CI.
- [ ] Track and drive static-analysis warnings to zero.

## Phase 3: Documentation to 10/10

- [x] Make README accurately describe the current version, stability level, core workflows, provider modes, and limitations.
- [x] Add a one-command clean-clone bootstrap path for Windows, macOS, and Linux.
- [x] Document the canonical commands for normalize, check, plan, materialize, build, cache, providers, and diagnostics.
- [x] Add end-to-end tutorials for generate, reconstruct, learned-provider, fallback-provider, and engine-export workflows.
- [x] Add a CLI reference generated from actual parser/help output.
- [x] Add a language reference generated or validated against grammar and schema.
- [x] Add a schema reference that explains every public field, default, and validation rule.
- [x] Add backend/provider documentation covering contracts, runtime config, offline behavior, network policy, and test doubles.
- [x] Add architecture docs for parser, normalizer, resolver, checker, planner, shape handoff, executor, validators, and packaging.
- [x] Add troubleshooting docs for common failures: parse errors, missing refs, provider unavailable, Blender issues, xatlas missing, cache corruption, and certification failures.
- [x] Add release docs covering versioning, changelog generation, artifact signing, SBOM, security scan review, and promotion criteria.
- [x] Add docs for privacy and telemetry with exact payload examples.
- [x] Add docs for security boundaries and trusted/untrusted inputs.
- [x] Add docs linting for links, stale command output, code blocks, and artifact paths.
- [x] Ensure every example in docs is executable or explicitly marked illustrative.
- [x] Add screenshots or rendered artifact previews for the flagship examples.

## Phase 4: Architecture to 10/10

- [x] Make architecture boundaries explicit in docs and tests.
- [x] Ensure import-linter or an equivalent boundary checker is installed and enforced in CI.
- [x] Define stable public contracts for language, shape handoff, providers, stages, validation, reports, and engine manifests.
- [x] Add compatibility tests for every stable contract.
- [x] Identify internal-only modules and prevent downstream examples/docs from depending on them.
- [x] Separate trusted compiler internals from untrusted asset input handling.
- [x] Isolate provider transport, provider auth/config, provider payload building, and provider result normalization.
- [x] Ensure every stage has a clear input schema, output schema, trace record, and failure mode.
- [x] Create migration guidance for future contract changes.
- [x] Add contract version checks and clear diagnostics for unsupported versions.
- [x] Audit global state, caches, temp directories, and runtime config for concurrency safety.
- [x] Add deterministic build mode guarantees and tests.
- [x] Review dependency direction so core language code does not depend on optional heavy runtime/provider packages.
- [x] Add architecture decision records for major design choices not already covered.
- [x] Remove or quarantine experimental modules from the stable public package surface.

## Phase 5: Test Coverage to 10/10

- [x] Set a realistic staged coverage target that reaches at least 85% overall and higher thresholds for critical modules.
- [x] Add per-package coverage gates for parser, resolver, checker, planner, provider config, sandboxing, cache, CLI, telemetry, and security-sensitive utilities.
- [ ] Add regression tests for every bug listed in this task list.
- [x] Add negative CLI tests for every command.
- [x] Add property-based parser and normalizer tests that run reliably in CI.
- [x] Add fuzz tests for `.lth` parsing, refs, runtime configs, provider payloads, and cache metadata.
- [x] Add golden tests for build reports, package manifests, trace manifests, engine manifests, telemetry payloads, and diagnostics.
- [x] Add mocked provider tests for success, timeout, malformed response, unsafe URL, oversized payload, and retry behavior.
- [x] Add sandbox tests for resource limits and subprocess failure handling.
- [x] Add filesystem tests for traversal, symlinks, permissions, stale cache, and concurrent cache writes.
- [x] Add cross-platform tests or platform-specific CI jobs for Windows, macOS, and Linux.
- [x] Add slow integration tests for canonical examples and mark them clearly.
- [x] Add performance regression tests for representative builds.
- [x] Add snapshot tests for docs-visible CLI output.
- [x] Add mutation or fault-injection testing for critical validation paths.
- [x] Remove unintended skips and require explicit reasons for every skip.
- [x] Ensure tests are deterministic, parallel-safe, and do not depend on generated local leftovers.

## Phase 6: Developer Experience to 10/10

- [x] Provide one documented bootstrap command for a full dev environment.
- [x] Provide one documented smoke-test command for a fresh contributor.
- [x] Ensure `python -m pytest -q` works after documented setup without missing optional test dependencies.
- [x] Make optional dependencies discoverable with clear extras such as dev, docs, providers, blender, and full.
- [x] Add `doctor` checks for every common setup issue and map failures to remediation steps.
- [x] Improve CLI help text, examples, and error messages for all commands.
- [x] Add shell completions if appropriate.
- [x] Add Makefile/Justfile targets that mirror CI gates exactly.
- [x] Ensure generated artifacts default to ignored output directories and do not pollute source status.
- [x] Add sample runtime configs for offline, reference-only, mocked learned provider, and real learned provider modes.
- [x] Add devcontainer validation or remove unsupported devcontainer claims.
- [x] Add contributor onboarding docs with first issue workflow, test expectations, and review process.
- [x] Add a clean-clone verification CI job that follows README setup instructions literally.
- [x] Add clear guidance for Windows-specific PowerShell commands and path behavior.
- [x] Add a troubleshooting matrix for dependency, Blender, provider, cache, and permissions failures.

## Phase 7: Maintenance and Activity to 10/10

- [x] Configure and document the canonical remote repository.
- [x] Ensure issue templates, PR templates, and discussion or support channels are current.
- [x] Add labels, milestones, and triage rules for bugs, security, docs, providers, examples, architecture, and release blockers.
- [x] Add a maintained roadmap with near-term, mid-term, and long-term milestones.
- [x] Keep CHANGELOG entries tied to releases and user-visible changes.
- [x] Add release automation that verifies tests, docs, security scans, SBOM, package metadata, and artifacts before publishing.
- [x] Add dependency update automation with review gates.
- [x] Add stale issue policy that does not close valid bug reports prematurely.
- [x] Add CODEOWNERS or ownership docs for core areas.
- [x] Define review requirements for language contract, security, provider, and release changes.
- [x] Track flaky tests and require fixes before release promotion.
- [x] Add maintenance metrics: open release blockers, mean time to resolve critical bugs, dependency age, security scan status, and doc freshness.
- [x] Document support windows for versions and public contracts.
- [x] Ensure tags, package versions, docs versions, and changelog versions agree.

## Phase 8: Security to 10/10

- [x] Threat-model untrusted `.lth` files, refs, provider configs, network calls, archives, generated artifacts, and telemetry.
- [x] Add a security architecture document with trust boundaries and data-flow diagrams.
- [x] Make network egress deny-by-default except for explicitly configured provider allowlists.
- [x] Ensure all provider URLs use centralized safe URL validation.
- [x] Add size, type, and path limits for every file read from asset sources.
- [x] Harden archive, package, and export writing against traversal and overwrite risks.
- [x] Ensure secrets are never logged, serialized, included in traces, or written to build artifacts.
- [x] Add secret scanning to local pre-commit and CI.
- [x] Ensure pip-audit runs successfully in the documented dev environment and CI.
- [x] Keep Bandit, Semgrep, Gitleaks, CodeQL, and dependency scans required for protected branches.
- [x] Add tests for prompt-injection handling where prompts or provider responses can influence behavior.
- [x] Add tests for SSRF, localhost/private-network denial, redirect behavior, and DNS rebinding assumptions.
- [x] Add tests for telemetry privacy and opt-in/opt-out behavior.
- [x] Add sandbox escape tests where feasible.
- [x] Document how users should report vulnerabilities and how maintainers respond.
- [x] Review license and provenance of generated/reference assets and dependencies.
- [x] Generate and publish SBOMs for releases.
- [x] Add signed release artifacts or document why signing is not yet supported.

## Phase 9: Product Quality to 10/10

- [x] Define the flagship product workflow and the minimum polish bar for its outputs.
- [x] Select a small canonical gallery of assets that represent Lathe's value: generate, reconstruct, mobile, high-quality, and engine-targeted outputs.
- [x] Ensure every canonical asset builds from a clean clone in deterministic mode.
- [x] Add visual and structural acceptance criteria for generated artifacts.
- [x] Improve certification reports so failures are actionable to users.
- [x] Add artifact previews to build outputs and docs.
- [x] Validate GLB/USD outputs in external viewers or automated validators.
- [x] Validate engine manifests against real target import workflows where possible.
- [x] Add quality metrics for topology, UVs, material slots, collision, LODs, scale, naming, and package completeness.
- [x] Add performance budgets for common builds.
- [x] Ensure fallback providers produce honest, useful outputs and do not overclaim learned generation quality.
- [x] Improve provider unavailable flows so users can still complete offline examples.
- [x] Add acceptance tests for reconstruct examples and reference images.
- [x] Add release candidate artifact review before each release.
- [x] Create a public gallery or examples page showing expected outputs and limitations.
- [x] Remove or clearly label any examples that are experimental, brittle, or incomplete.

## Phase 10: Product Value and Vision to 10/10

- [x] Write a concise product positioning document: target users, core problem, alternatives, and why Lathe is better.
- [x] Define the primary user journeys: solo technical artist, game tools engineer, AI asset pipeline builder, and CI asset validation maintainer.
- [x] Identify the smallest lovable workflow that should feel excellent before expanding scope.
- [x] Add example-driven docs that show why declarative asset builds beat ad hoc scripts for repeatability and certification.
- [x] Add comparison notes against common alternatives such as Blender scripts, procedural generation libraries, and direct provider APIs.
- [x] Add real-world use cases with measurable benefits: deterministic builds, portable contracts, provider swapping, asset QA, and engine-ready packaging.
- [x] Define success metrics: successful clean-clone build rate, time to first asset, certification pass rate, provider failure recovery, and artifact quality.
- [ ] Gather feedback from at least a few target users and record findings.
- [x] Prioritize roadmap items based on user value, not only technical completeness.
- [x] Add polished demo scripts or videos for the core workflow.
- [x] Clarify which features are product-critical and which are research/experimental.
- [x] Define a stable extension story for providers, validators, and engine targets.
- [x] Ensure every release note explains user-visible value, not just internal changes.

## Phase 11: Documentation and Code Consistency Sweeps

- [x] Search all docs for stale artifact names and update them to current outputs.
- [x] Search all docs for stale version names and align them with package metadata.
- [x] Search all docs for deprecated config keys and replace or mark them.
- [x] Search all examples for obsolete language fields and update them.
- [x] Search tests for obsolete assumptions that no longer match public behavior.
- [x] Search source for TODO, FIXME, HACK, placeholder, stub, and NotImplemented markers; resolve or track each one.
- [x] Search source for broad catches, silent passes, and default-success fallbacks; resolve or justify each one.
- [x] Search source and docs for secrets, tokens, API keys, local absolute paths, and private data.
- [x] Remove generated build artifacts from tracked source unless intentionally part of fixtures.
- [x] Ensure all fixtures are minimal, named clearly, and documented.

## Phase 12: Release Readiness

- [ ] Run the clean-clone bootstrap on Windows.
- [ ] Run the clean-clone bootstrap on macOS.
- [ ] Run the clean-clone bootstrap on Linux.
- [ ] Run the full local quality gate from a clean checkout.
- [ ] Run all CI workflows on the release candidate branch.
- [x] Verify package metadata, dependencies, classifiers, license, and Python version support.
- [x] Verify docs build and publish preview.
- [ ] Verify changelog and version tags.
- [x] Verify SBOM generation and security scan outputs.
- [x] Verify source distribution and wheel install in a fresh environment.
- [x] Verify canonical examples from installed package, not only editable checkout.
- [x] Verify artifact outputs in at least one external consumer/viewer.
- [ ] Confirm no release-blocking bugs remain open.
- [ ] Publish the release only after all gates are green.

## Final 10/10 Review Checklist

- [ ] Code Quality score is reassessed as 10/10 with evidence.
- [ ] Documentation score is reassessed as 10/10 with evidence.
- [ ] Architecture score is reassessed as 10/10 with evidence.
- [ ] Test Coverage score is reassessed as 10/10 with evidence.
- [ ] Developer Experience score is reassessed as 10/10 with evidence.
- [ ] Maintenance and Activity score is reassessed as 10/10 with evidence.
- [ ] Security score is reassessed as 10/10 with evidence.
- [ ] Product Quality score is reassessed as 10/10 with evidence.
- [ ] Product Value and Vision score is reassessed as 10/10 with evidence.
- [ ] Bugs, Errors, and Issues score is reassessed as 10/10 with evidence.
- [ ] Overall score is reassessed as 10/10 by someone who did not implement the final fixes.
