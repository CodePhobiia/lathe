# Wonder Provenance And Safety Boundary

This note documents the security boundary for the Phase 23 and Phase 28
metadata helpers:

- `lathe.scene.game_readiness`
- `lathe.scene.provenance`
- `schema/game_readiness.schema.json`
- `schema/asset_provenance_scene.schema.json`

## Trust Boundary

Game-readiness and provenance payloads are untrusted Wonder JSON inputs when
they come from Project Wonder, an LLM authoring step, a provider adapter, a user
upload flow, or an external tool. Callers must validate those payloads with the
committed schemas before using their contents.

The helpers in this phase expose schema validators, but they do not add new CLI
or file-ingress commands. If a future command reads these JSON files from disk,
that command must use the same controls as other Wonder contract readers:
byte cap, UTF-8 decode, JSON parse, object-root enforcement, schema validation,
and deterministic diagnostics.

## Secret-Bearing Metadata

The validators reject metadata keys and common value patterns that look like
credentials. Diagnostics use `GR9001` for game-readiness metadata and `PR9001`
for provenance metadata.

The diagnostic payloads intentionally do not echo detected secret values. They
report the JSON pointer, the field name, and whether the finding came from a key
or value match.

The detector is scoped to metadata-like surfaces rather than creative prose. It
is designed to catch fields such as `api_key`, `authorization`,
`client_secret`, `private_key`, and token-looking values without treating
ordinary scene lore such as `secret_compartment` as a credential.

## World Memory Mutation Safety

World Memory mutation helpers redact before persistence. The public Wave 2
helpers are:

- `append_memory_event_idempotent(world_memory, event, idempotency_key)`
- `redact_memory_payload(payload)`
- `record_rejected_patch(world_memory, patch, diagnostics, reason)`

Idempotency keys are stored in event metadata as `metadata.idempotency_key`.
Repeating an append with the same key returns a World Memory copy without adding
a duplicate event.

Redaction is recursive over mapping and array values. Sensitive key names such
as `password`, `secret`, `token`, `api_key`, `authorization`, `bearer`, and
`credential` are replaced with `[REDACTED]`; free-text email addresses,
phone-like values, bearer tokens, GitHub-style tokens, and OpenAI/Anthropic-like
keys are also redacted where practical.

Rejected Scene Patch attempts can be recorded in World Memory as private patch
events. The record includes the reason, diagnostics, target or affected IDs when
available, and a redacted copy of the rejected patch. These records preserve the
World Memory schema contract and do not execute Blender, Roblox Studio, external
viewers, or provider runtimes.

## Provenance And Rights

The provenance contract records source and rights metadata. It does not prove
that the metadata is true.

The helper checks are intentionally mechanical:

- every Scene Graph object should have provenance metadata
- provider-generated objects should name the provider
- licensed-reference objects should name the license
- opaque metadata must not carry secrets

The helper does not decide whether an asset may ship, whether a license is valid,
whether a brand/IP claim is acceptable, or whether a content-safety review is
sufficient. Those are policy and human-review decisions outside Lathe core.

## Engine And Export Boundary

This phase does not create engine artifacts, export packages, signed manifests,
or provider calls. It only produces diagnostics over JSON dictionaries.

Future engine export lanes may consume these fields, but they must treat
`unknown`, `restricted`, `blocked`, `flagged`, and `unreviewed` as metadata
inputs to their own policy gate. They must not infer legal clearance from schema
validity alone.

## Residual Risks

Schema validation proves shape, not truth. A malicious or mistaken caller can
still label provider-generated content as deterministic Lathe output. That risk
requires provenance capture at the generation boundary, audit logs, and review
workflow outside this helper layer.

Secret detection is deterministic and conservative, but it is not a full secret
scanner. Repository-level and artifact-level secret scanning remain required for
release evidence.
