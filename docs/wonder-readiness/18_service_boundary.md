# Phase 29 Service Boundary

Phase 29 records the service API contract boundary for Project Wonder without
adding a server to Lathe core. The boundary is intentionally narrow: it wraps
existing Wonder and Scene JSON contracts in request and response envelopes with
correlation IDs, job status, diagnostics, and artifact references.

## Contract Assets

- API reference:
  [`docs/api/wonder_service_contracts.md`](../api/wonder_service_contracts.md)
- Service schema:
  [`schema/service_wonder_api.schema.json`](../../schema/service_wonder_api.schema.json)
- Boundary ADR:
  [`docs/adr/0012-wonder-service-boundary.md`](../adr/0012-wonder-service-boundary.md)
- Contract tests:
  `tests/unit/test_wonder_service_contracts.py`

## What This Enables

The Project Wonder app can call a future service adapter using stable envelope
shapes for:

- Dream Brief checks.
- Scene Graph checks.
- Scene package builds.
- Scene render requests and render inspection responses.
- Scene patch application.
- Artifact listing.
- Job status lookup.

The nested data remains the same JSON payloads that local Lathe commands and
validators already understand. This keeps the app boundary separate from the
compiler boundary and avoids turning app workflows into Lathe language surface.

## What Stays Outside Lathe Core

Lathe core does not implement accounts, payments, galleries, chat UX, product
plans, subscriptions, or customer-facing application state. The service
envelopes reject those app-owned fields at the contract boundary. Application
services may compose those concerns around Lathe, but they must not require
Lathe schemas, CLI commands, or scene contracts to know about them.

## Readiness Impact

This phase improves Wonder readiness by documenting how the app can integrate
with Lathe without adding runtime service code. It does not add a server. The
current local build path is the deterministic proxy Scene Package flow: it can
write proxy PNG renders and declared proxy GLB exports, while final
Blender/USD/Roblox execution remains outside the service contract proof.
