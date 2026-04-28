# Review requirements

Lathe changes are reviewed by risk surface. Use this page with
`.github/CODEOWNERS` and the pull-request template.

## Required specialist review

| Change type | Required reviewer focus | Required evidence |
|---|---|---|
| Language contract | Grammar, spec, schema, parser, normalizer, resolver, checker, examples, and compatibility. | Updated `spec/lathe-v0.1.md`, `grammar/lathe.lark`, `schema/lathe.schema.json`, source behavior, examples, and tests when public behavior changes. |
| Stable shape handoff | `lathe.shape.intent_mesh_handoff_v1` compatibility, shape bundle fields, provider handoff, downstream topology/UV/package expectations. | Contract tests plus at least one generate and one reconstruct path when the handoff is affected. |
| Provider/runtime config | Provider URL validation, allowlists, timeouts, fallback truthfulness, mocked external-service tests. | No live-service dependency in normal tests; strict-mode and fallback diagnostics covered. |
| Security-sensitive code | Path, network, subprocess, archive/package writing, telemetry, secrets, sandboxing, prompt-injection, and untrusted input handling. | Negative tests for reject paths, docs/threat-model updates when boundaries change, and security scanner review when relevant. |
| Release process | Versioning, changelog, SBOM, signing, package metadata, release exceptions, support matrix, and promotion criteria. | Release checklist evidence and updated docs for any changed release promise. |

## Review rules

- A reviewer for the affected owner area must approve changes that alter public
  behavior, security boundaries, release promises, or stable contracts.
- Language-contract migrations must land as coordinated changes across every
  affected layer, not as parser-only or docs-only updates.
- Provider integrations should use mocked tests unless a marked integration
  lane is explicitly required.
- Security exceptions must identify the rule, affected path, rationale, owner,
  and follow-up review date.
- Release exceptions must be documented before promotion and linked from the
  release checklist or known-limitations docs.

## Local evidence to include in PRs

Every PR should state the exact commands run. For high-risk areas, include the
smallest relevant check first, then broader gates:

- Language/provider/runtime behavior: focused tests plus `python -m pytest -q`
  when behavior changes.
- Docs/release behavior: `mkdocs build --strict`.
- Security behavior: relevant negative tests and the matching scanner command
  from `docs/security/ci_gates.md`.
- Example changes: `check`, `plan`, `materialize`, and the narrow build path
  for the changed example.
