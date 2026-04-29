# Project Wonder Blocker Removal Diagnosis

Created: 2026-04-29

Purpose: convert the current Wonder blocker list into concrete Lathe patches that remove the blockers for real. "Remove" means the repository gains code, schemas, tests, docs, example artifacts, and evidence-producing commands so the blocker cannot reappear as an ambiguous checklist item.

This document is intended as the starting context for an implementation chat/agent inside the Lathe repository.

---

## Executive Diagnosis

Lathe already has much of the Wonder substrate in place: `lathe wonder` validators, deterministic proxy scene paths, scene patching, world memory validation, Wonder docs, example fixtures, and validation helpers. The remaining blockers are not one missing feature; they are mostly missing **hard gates** around evidence, rollback, comparison, authoring, examples, CI, and final reporting.

The strategic fix is to add a single machine-readable Wonder alpha gate harness that gathers all of those lanes:

```bash
python -m lathe.cli wonder alpha-gate \
  examples/wonder/alchemist_observatory \
  --out .tmp_tests/wonder_alpha_gate
```

That command should produce durable reports and exit successfully when all deterministic core gates pass. External runtimes such as POSIX shell, Blender, Roblox Studio, and external viewers must become optional/strict lanes rather than default blockers.

Core principle:

> If an item can block the alpha gate, it must be represented by a contract, a CLI command, a test, and an evidence artifact.

---

## Current Repo Anchors

Known relevant files and areas:

- `wonder-tasks.md` — master readiness checklist and status notes.
- `docs/wonder-readiness/evidence.md` — existing evidence log.
- `docs/wonder-readiness/status.md` — current readiness status.
- `lathe/cli/wonder_cmd.py` — Wonder CLI surface.
- `lathe/scene/memory.py` — World Memory validation/helpers.
- `lathe/scene/patch.py` — Scene Patch application and rejected operations.
- `tests/unit/test_wonder_memory.py` — World Memory tests.
- `tests/unit/test_scene_patch.py` — Scene Patch tests.
- `tests/unit/test_wonder_llm.py` — LLM-facing diagnostics/contracts.
- `tests/unit/test_wonder_examples_catalog.py` — example catalog tests.
- `scripts/lathe_wonder_validate.ps1` — Windows validation helper.
- `scripts/lathe_wonder_validate.sh` — POSIX validation helper.
- `scripts/demo_wonder_seed_scene.ps1` / `.sh` — demo path helpers.
- `examples/wonder/` — Wonder golden/example fixture roots.

Observed example gap:

- Some examples have `dream_brief.json` and `scene_graph.json` but lack `prompt.txt`, patch JSON, expected reports, render inspection, and preview evidence.
- `alchemist_observatory` is currently the richest fixture and should remain the first golden alpha gate target.

---

## Target End State

The implementation should make this true:

```bash
python -m lathe.cli wonder env-probe --out .tmp_tests/wonder_env_probe.json
python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out .tmp_tests/wonder_alpha_gate
```

Expected output layout:

```text
.tmp_tests/wonder_alpha_gate/
  reports/
    final_readiness_report.md
    final_readiness_report.json
    evidence_traceability.json
    benchmark_report.json
    security_report.json
    performance_report.json
    contract_catalog.json
    cli_catalog.json
    example_catalog.json
    env_probe.json
  before/
  after/
  comparisons/
  history/
```

The alpha gate JSON should be able to say:

```json
{
  "core_alpha_gate": "passed",
  "blocking_missing_runtimes": [],
  "optional_lanes": {
    "posix": "passed_or_skipped_nonblocking",
    "blender": "passed_or_skipped_nonblocking",
    "roblox": "passed_or_skipped_nonblocking",
    "external_viewer": "passed_or_skipped_nonblocking"
  },
  "alpha_decision_ready": true,
  "remaining_human_decision": "Approve Project Wonder alpha gate."
}
```

---

## Blocker 1: Completion Rules Are Still Open

### Diagnosis

The checklist rules are correct, but the repo needs machine-checkable traceability for every checked task. Otherwise completed items can drift into prose-only status.

### Patch

Create:

```text
schema/wonder_evidence_trace.schema.json
lathe/wonder/evidence.py
tests/unit/test_wonder_evidence_traceability.py
docs/wonder-readiness/evidence_traceability.md
```

Add CLI:

```bash
python -m lathe.cli wonder evidence-trace \
  --tasks wonder-tasks.md \
  --evidence docs/wonder-readiness/evidence.md \
  --out .tmp_tests/wonder/evidence_traceability.json
```

### Required Behavior

Every checked task in `wonder-tasks.md` must map to at least one durable evidence item:

- test path and command
- CLI command output
- schema path
- docs path
- example artifact
- report path
- explicit decision record

Every schema/CLI/artifact/language change must be backed by at least one test/doc/evidence entry.

### Tests

- checked task without evidence fails.
- referenced evidence path must exist.
- command evidence must include command, result, output path/date, and status.
- docs-only items may pass only if the task is truly documentation-only.

---

## Blocker 2: World Memory Needs Final Hardening

### Diagnosis

`lathe/scene/memory.py` already validates world memory structure and scene binding. Remaining hardening is about safety and repeatability: idempotent append, secret/PII redaction, and recording rejected patch attempts.

### Patch

Modify/create:

```text
lathe/scene/memory.py
lathe/scene/patch.py
schema/world_memory.schema.json
tests/unit/test_wonder_memory.py
tests/unit/test_scene_patch.py
docs/security/wonder_provenance_safety.md
docs/wonder-readiness/13_branching.md
```

Add helpers:

```python
append_memory_event_idempotent(world_memory, event, idempotency_key: str) -> dict
redact_memory_payload(payload) -> dict
record_rejected_patch(world_memory, patch, diagnostics, reason) -> dict
```

Add CLI:

```bash
python -m lathe.cli wonder append-memory-event world_memory.json \
  --event event.json \
  --idempotency-key patch-001 \
  --out world_memory.updated.json

python -m lathe.cli wonder redact-memory memory.raw.json \
  --out memory.redacted.json
```

### Required Behavior

- Same idempotency key must not duplicate an event.
- Redaction must cover emails, phone numbers, bearer/API tokens, GitHub/OpenAI/Anthropic-like keys, and sensitive field names such as `password`, `secret`, `token`, `api_key`.
- Rejected Scene Patch operations must be persisted as memory events with diagnostics and reason.

### Tests

- appending the same event twice is stable.
- redaction catches nested secret fields and free-text secrets.
- rejected patch result becomes a durable memory event.
- world memory still validates after rejected patch recording.

---

## Blocker 3: Rollback / History Is Incomplete

### Diagnosis

Patch application exists, but the system needs explicit inverse patch/history contracts. Rollback must be hash-guarded so we do not roll back the wrong scene state.

### Patch

Create:

```text
lathe/scene/history.py
lathe/scene/rollback.py
schema/scene_history.schema.json
tests/unit/test_scene_history.py
tests/unit/test_scene_rollback.py
docs/wonder-readiness/branch_history.md
```

Add CLI:

```bash
python -m lathe.cli wonder apply-patch scene_graph.json patch.json \
  --out patched.scene_graph.json \
  --history history.json

python -m lathe.cli wonder rollback-scene patched.scene_graph.json \
  --history history.json \
  --to-event mem_patch_001 \
  --out rolled_back.scene_graph.json

python -m lathe.cli wonder branch-history \
  --memory world_memory.json \
  --branch main \
  --out branch_history.json
```

### Required Behavior

Each patch application records:

```json
{
  "event_id": "mem_patch_001",
  "forward_patch": "patches/patch_001.json",
  "inverse_patch": "patches/patch_001.rollback.json",
  "before_scene_hash": "...",
  "after_scene_hash": "...",
  "render_reports": [],
  "validation_reports": []
}
```

### Tests

- apply patch then rollback returns normalized scene graph to original.
- rollback refuses when current scene hash does not match `after_scene_hash`.
- branch history includes validation and render report refs.
- rejected patches are recorded but not rollback-applicable.

---

## Blocker 4: Before/After Comparison Is Incomplete

### Diagnosis

Before/after must not depend on Blender. The deterministic proxy render path should be enough for core gate comparison; Blender can remain an optional strict lane.

### Patch

Create:

```text
lathe/scene/compare.py
lathe/scene/camera_lock.py
schema/render_comparison.schema.json
tests/unit/test_scene_compare.py
tests/unit/test_scene_camera_lock.py
docs/wonder-readiness/before_after_comparison.md
```

Add CLI:

```bash
python -m lathe.cli wonder lock-camera scene_graph.json \
  --camera-id camera_reveal \
  --out camera_lock.json

python -m lathe.cli wonder compare-renders \
  --before before/render_reveal.png \
  --after after/render_reveal.png \
  --camera-lock camera_lock.json \
  --out comparison.json

python -m lathe.cli wonder demo-before-after \
  examples/wonder/alchemist_observatory \
  --out .tmp_tests/wonder_before_after
```

### Required Behavior

Comparison report shape:

```json
{
  "schema_version": "lathe.render_comparison.v1",
  "camera_lock_status": "passed",
  "before_hash": "...",
  "after_hash": "...",
  "pixel_delta": {
    "changed_pixels": 1834,
    "changed_ratio": 0.071
  },
  "semantic_delta": {
    "expected_targets_changed": true,
    "protected_targets_unchanged": true
  },
  "status": "passed"
}
```

### Tests

- same image comparison passes with zero delta.
- modified target region produces nonzero delta.
- camera mismatch fails.
- demo command writes before, after, and comparison artifacts.

---

## Blocker 5: LLM Authoring Pack Is Incomplete

### Diagnosis

The LLM layer needs an explicit authoring contract. It must support generation, diagnosis, bad-output examples, schema links, and repair playbooks without bypassing Lathe validators.

### Patch

Modify/create:

```text
lathe/wonder/llm.py
lathe/scene/planner.py
lathe/scene/source_diagnostics.py
lathe/cli/wonder_cmd.py
docs/llm/generate_scene_plan.md
docs/llm/repair_playbook.md
docs/llm/schema_links.md
docs/llm/bad_outputs/
tests/unit/test_wonder_llm.py
tests/unit/test_scene_source_diagnostics.py
```

Add CLI:

```bash
python -m lathe.cli wonder generate-scene-plan \
  examples/wonder/alchemist_observatory/dream_brief.json \
  --scene-graph examples/wonder/alchemist_observatory/scene_graph.json \
  --out .tmp_tests/wonder_scene_plan.json

python -m lathe.cli wonder repair-playbook \
  --diagnostics diagnostics.json \
  --out repair_steps.json
```

### Required Behavior

LLM-facing diagnostics should include source-span and repair hints where possible:

```json
{
  "path": "/objects/3/style_tags/1",
  "source_span": {
    "file": "scene.lth",
    "line": 42,
    "column": 8,
    "end_line": 42,
    "end_column": 19
  },
  "message": "Unknown style tag.",
  "repair_hint": "Use one of: sacred, industrial, ancient, luminous."
}
```

Bad-output examples should include expected diagnostics for:

- invalid scene plan missing camera
- invalid patch unknown target
- invalid scene source bad ID
- invalid memory with secret

---

## Blocker 6: CI/Test Matrix Is Incomplete

### Diagnosis

The core test matrix should be runnable locally even before remote CI is fully trusted. Optional runtime lanes must report skipped/nonblocking when unavailable.

### Patch

Create:

```text
scripts/ci_wonder_fast.py
scripts/ci_wonder_examples.py
scripts/ci_wonder_optional_blender.py
scripts/ci_wonder_optional_roblox.py
.github/workflows/wonder-fast.yml
.github/workflows/wonder-examples.yml
.github/workflows/wonder-optional-blender.yml
.github/workflows/wonder-optional-roblox.yml
tests/fuzz/test_wonder_contract_fuzz.py
tests/snapshots/wonder/
```

### Required Behavior

Optional runtime result shape:

```json
{
  "lane": "blender",
  "status": "skipped",
  "reason": "blender executable not available",
  "blocking": false
}
```

### Commands

```bash
python scripts/ci_wonder_fast.py
python scripts/ci_wonder_examples.py
python scripts/ci_wonder_optional_blender.py
python scripts/ci_wonder_optional_roblox.py
```

### Fuzz Targets

- Scene Patch operations.
- World Memory append/idempotency.
- JSON pointer handling.
- ID normalization.
- path safety.
- redaction.
- inverse patch rollback.

### Golden Snapshot Targets

- generated scene plan.
- alpha gate report.
- before/after comparison report.
- evidence traceability report.
- example catalog.

---

## Blocker 7: Golden Examples Are Incomplete

### Diagnosis

Examples need a uniform fixture contract. They should be regression assets, not loose demos.

### Patch

Normalize each folder under `examples/wonder/<example_name>/` to include:

```text
prompt.txt
dream_brief.json
scene_graph.json
scene_source.lth              # optional/deferred until scene syntax is real
world_memory.json
scene_patch.example.json
render_inspection.example.json
expected/
  scene_plan.example.json
  wonder_report.example.json
  scene_manifest.example.json
  render_comparison.example.json
  evidence_traceability.example.json
```

Add CLI:

```bash
python -m lathe.cli wonder validate-example examples/wonder/alchemist_observatory
python -m lathe.cli wonder catalog-examples examples/wonder \
  --out docs/wonder-readiness/20_example_catalog.json
```

### Required Behavior

If `.lth` scene source is still experimental, do not fake it. Record:

```json
{
  "scene_source": {
    "status": "deferred",
    "reason": "experimental scene syntax not complete",
    "blocking": false,
    "tracked_by": "docs/adr/0010-experimental-scene-source-language.md"
  }
}
```

---

## Blocker 8: Final Handoff Docs/Reports Are Missing

### Diagnosis

The alpha gate needs final reports produced by code, not manually written prose.

### Patch

Create:

```text
lathe/wonder/readiness.py
lathe/wonder/reports.py
tests/unit/test_wonder_readiness_report.py
docs/wonder-readiness/final_readiness_report.md
```

Add CLI:

```bash
python -m lathe.cli wonder readiness-report \
  --evidence .tmp_tests/wonder_alpha_gate/reports/evidence_traceability.json \
  --benchmarks .tmp_tests/wonder_alpha_gate/reports/benchmark_report.json \
  --security .tmp_tests/wonder_alpha_gate/reports/security_report.json \
  --performance .tmp_tests/wonder_alpha_gate/reports/performance_report.json \
  --out docs/wonder-readiness/final_readiness_report.md
```

### Required Reports

- final readiness report
- final readiness JSON
- benchmark report
- security report
- performance report
- contract catalog confirmation
- CLI catalog confirmation
- example catalog confirmation
- final alpha decision readiness marker

The human alpha decision itself should remain a decision, not an auto-checked implementation box.

---

## Blocker 9: Practical Flow-State Risk From External Runtimes

### Diagnosis

The biggest implementation risk is that the session gets interrupted by missing POSIX shell, Blender, external viewer/probe, or Roblox tooling. This should not block the deterministic core path.

### Patch

Add environment probing and validation modes.

Add CLI:

```bash
python -m lathe.cli wonder env-probe --out .tmp_tests/wonder_env_probe.json
```

Expected shape:

```json
{
  "python": "available",
  "posix_shell": "available_or_missing",
  "powershell": "available_or_missing",
  "blender": "available_or_missing",
  "roblox_studio": "available_or_missing",
  "external_viewer": "available_or_missing",
  "blocking_missing": [],
  "optional_missing": ["blender", "roblox_studio", "external_viewer"]
}
```

Update helper scripts to support:

```bash
--mode core
--mode optional
--mode strict
--evidence-dir <path>
```

Meaning:

- `core`: deterministic local alpha substrate, no Blender/Roblox required.
- `optional`: run optional runtimes if present and record skipped otherwise.
- `strict`: fail if optional runtimes are missing.

Modify:

```text
scripts/lathe_wonder_validate.ps1
scripts/lathe_wonder_validate.sh
scripts/demo_wonder_seed_scene.ps1
scripts/demo_wonder_seed_scene.sh
```

---

## Recommended Execution Order

### Wave 1: Make Truth Measurable

1. Add `env-probe`.
2. Add evidence traceability contract/CLI.
3. Add example catalog validator/CLI.
4. Add alpha-gate skeleton command that calls existing validations and writes a partial report.

### Wave 2: Make Mutation Safe

5. Add World Memory idempotent append.
6. Add redaction.
7. Add rejected patch recording.
8. Add patch history.
9. Add rollback command.

### Wave 3: Make Visual Iteration Provable

10. Add camera lock.
11. Add deterministic before/after render comparison.
12. Add `demo-before-after`.
13. Store render/validation history per branch.

### Wave 4: Make LLM Authoring Usable

14. Add `generate-scene-plan` CLI.
15. Add repair playbook CLI/docs.
16. Add canonical schema links under `docs/llm/`.
17. Add bad-output examples.
18. Add source-span diagnostics.

### Wave 5: Make Examples Golden

19. Fill missing `prompt.txt` files.
20. Add patch JSON per example.
21. Add expected reports per example.
22. Add preview build/render/export evidence per example.
23. Truthfully mark `.lth` scene source deferred where syntax is not complete.

### Wave 6: Make CI/Reports Final

24. Add Wonder fast CI/local script.
25. Add Wonder examples CI/local script.
26. Add optional Blender lane.
27. Add optional Roblox lane.
28. Add fuzz tests.
29. Add golden snapshots.
30. Add final readiness/security/performance/benchmark reports.
31. Make `alpha-gate` produce the final report bundle.

---

## Minimal First Implementation Slice

To start without boiling the ocean, implement this first:

```text
lathe/wonder/env.py
lathe/wonder/evidence.py
lathe/wonder/readiness.py
lathe/cli/wonder_cmd.py additions
tests/unit/test_wonder_env_probe.py
tests/unit/test_wonder_evidence_traceability.py
tests/unit/test_wonder_alpha_gate.py
```

First three commands to make real:

```bash
python -m lathe.cli wonder env-probe --out .tmp_tests/wonder_env_probe.json
python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs/wonder-readiness/evidence.md --out .tmp_tests/wonder_evidence_traceability.json
python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out .tmp_tests/wonder_alpha_gate
```

This gives the Codex implementation chat a harness immediately. After that, every blocker plugs into the harness as a failing/passing lane.

---

## Definition of Done

The blocker-removal initiative is done when these pass locally:

```bash
python -m pytest -q \
  tests/unit/test_wonder_contracts.py \
  tests/unit/test_wonder_memory.py \
  tests/unit/test_scene_patch.py \
  tests/unit/test_scene_rollback.py \
  tests/unit/test_scene_compare.py \
  tests/unit/test_wonder_llm.py \
  tests/unit/test_wonder_examples_catalog.py \
  tests/unit/test_wonder_readiness_report.py
```

And:

```bash
python -m lathe.cli wonder alpha-gate \
  examples/wonder/alchemist_observatory \
  --out .tmp_tests/wonder_alpha_gate
```

And the final report contains:

```json
{
  "core_alpha_gate": "passed",
  "blocking_missing_runtimes": [],
  "alpha_decision_ready": true
}
```

---

## Non-Negotiables

- Do not mark tasks complete with prose-only evidence.
- Do not make Blender/Roblox/external viewer mandatory for the deterministic core alpha gate.
- Do not fake `.lth` scene source completeness. Mark it deferred with a reason until real.
- Do not allow rollback without scene hash guards.
- Do not allow World Memory to store raw secrets or PII.
- Do not allow LLM output to bypass schemas/validators.
- Every new CLI command needs tests and docs/evidence.

---

## Suggested First Prompt For Codex

Use this in the new Codex chat:

```text
Read docs/wonder-readiness/blocker-removal-diagnosis.md, wonder-tasks.md, lathe/cli/wonder_cmd.py, lathe/scene/memory.py, and lathe/scene/patch.py.

Implement Wave 1 only:
1. wonder env-probe
2. wonder evidence-trace
3. wonder alpha-gate skeleton that invokes existing deterministic validations and writes reports/env_probe.json, reports/evidence_traceability.json, and reports/final_readiness_report.json
4. focused tests for those commands

Do not implement Blender/Roblox execution. Missing external runtimes must be reported as optional skipped lanes, not failures in core mode.

Run the focused tests and update docs/wonder-readiness/evidence.md with command evidence.
```
