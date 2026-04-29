# Wonder Alpha Gate

Last updated: 2026-04-29

Current decision state: **deterministic core gate passed locally; final human
alpha approval remains pending**.

The core alpha gate is now the machine-readable harness:

```powershell
python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out .tmp_tests/wonder_alpha_gate
```

It does not require Blender, Roblox Studio, POSIX shell, or an external viewer
in core mode. Optional runtime evidence is reported as passed or skipped
nonblocking instead of hidden or treated as a core failure.

## Final Bundle

The command writes:

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

The public handoff report can be refreshed with:

```powershell
python -m lathe.cli wonder readiness-report --out docs/wonder-readiness/final_readiness_report.md
```

## Core Gate Matrix

| Gate | Current state |
| --- | --- |
| Environment probe | Passed locally with no blocking missing runtimes. |
| Evidence traceability | Passed locally against `wonder-tasks.md` and this evidence ledger. |
| Dream Brief contract | Passed locally for Alchemist Observatory. |
| Scene Graph contract | Passed locally for Alchemist Observatory. |
| Brief/scene consistency | Passed locally. |
| Scene Graph semantics | Passed locally. |
| Scene Patch contract | Passed locally using `scene_patch.example.json`. |
| Render Inspection contract | Passed locally. |
| World Memory contract | Passed locally against the Scene Graph. |
| Scene Plan contract | Passed locally through deterministic planning. |
| Scene Assembly contract | Passed locally through deterministic assembly. |
| Scene quality validators | Passed locally. |
| Final readiness bundle | Passed locally and wrote JSON/Markdown plus supporting reports. |

## Optional Gates

| Lane | Local Wave 6 status | Blocking in core mode |
| --- | --- | --- |
| POSIX shell | Skipped nonblocking in this Windows environment. | No |
| Blender | Probe passed locally; no Blender render/export evidence is claimed. | No |
| Roblox Studio/tooling | Skipped nonblocking because tooling was unavailable. | No |
| External viewer | Skipped nonblocking. | No |

## Deferred Lanes

- Full `.lth` scene source is still deferred truthfully by golden examples.
- Blender-backed scene rendering remains outside the deterministic core gate
  unless explicitly requested in a strict optional lane. Sandboxed Blender scene
  export now has local fixture evidence, but external viewer validation remains
  separate.
- Roblox Studio import/export execution remains outside the deterministic core
  gate unless explicitly requested in a strict optional lane.
- The final human decision remains pending:
  **Approve Project Wonder alpha gate.**

## Required Before Marking Human Alpha Approval Complete

1. Review `.tmp_tests/wonder_alpha_gate/reports/final_readiness_report.json`.
2. Review `docs/wonder-readiness/final_readiness_report.md`.
3. Decide whether to approve Project Wonder alpha based on the deterministic
   core evidence and any optional runtime evidence the release owner requires.

The report may say `alpha_decision_ready: true`; it must not be read as the
human approval itself.
