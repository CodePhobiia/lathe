# ADR 0012: Keep the Wonder service boundary outside Lathe core

- **Status:** Accepted
- **Date:** 2026-04-28
- **Ticket:** Phase 29 Service API Contract Boundary
- **Related:** ADR-0009, ADR-0010, `docs/api/wonder_service_contracts.md`,
  `docs/wonder-readiness/18_service_boundary.md`,
  `schema/service_wonder_api.schema.json`

## Context

Project Wonder needs a service-facing contract so an application can submit
Dream Briefs, Scene Graphs, patches, build requests, render requests, artifact
queries, and status checks. Lathe already has JSON contracts and CLI output
shapes for the compiler side of that exchange, but it does not have or need an
application server in core.

Without a documented boundary, app concerns could drift into Lathe schemas as
fields for accounts, payments, galleries, chat threads, product plans, or other
customer-facing workflow state. That would make Lathe harder to use as a
standalone compiler and would blur the public contract index recorded in
ADR-0009.

## Decision

Lathe core will define only schema-versioned service request and response
envelopes around existing Wonder and Scene contract payloads. Lathe core must
not implement or own accounts, payments, galleries, chat UX, product plans, or
subscription behavior.

## Rationale

The service boundary needs transport metadata: `correlation_id`, `job_id`,
`status`, diagnostics, and artifact references. Those fields are operational
metadata, not product behavior. The payloads inside the envelopes remain Dream
Brief, Scene Graph, Scene Patch, Render Inspection, Scene Plan, Scene Assembly,
Scene Quality Report, Scene Repair Report, and Scene Package Manifest records.

Keeping this boundary schema-only lets Project Wonder build an app service
around Lathe while preserving Lathe's role as a declarative asset and scene
compiler. It also gives tests a precise way to reject app-owned fields before
they become accidental core surface.

## Consequences

### Positive

- Project Wonder gets stable integration envelopes without requiring a Lathe
  server implementation.
- Lathe keeps existing CLI and JSON contract payloads as the source of truth.
- Account, payment, gallery, chat, and product workflow concerns stay in the
  application layer.
- Artifact listing and job status can be documented without changing compiler
  modules.

### Negative / accepted risks

- The contract does not prove that a deployed service exists; adapters still
  need their own implementation, auth, rate limiting, and operations checks.
- The render endpoint is contract-ready before Lathe core has render execution,
  so callers must read capability flags and status responses rather than assume
  render artifacts exist.
- Service consumers must map app-specific state to `correlation_id` and
  `job_id` outside Lathe.

## Alternatives considered

- **Build a Lathe service server now.** Rejected: Phase 29 is a contract
  boundary task, and server ownership would introduce app and operations
  concerns into core.
- **Put app fields directly into Wonder contracts.** Rejected: account,
  payment, gallery, chat, and product fields are not compiler data.
- **Leave the service boundary undocumented.** Rejected: downstream adapters
  would invent incompatible wrappers around the same CLI and JSON contracts.

## Re-evaluation criteria

Re-open this decision if:

1. Lathe intentionally ships an official hosted service in this repository.
2. Project Wonder needs a new compiler-owned contract payload that cannot be
   represented by the existing nested schemas.
3. The public contract index in ADR-0009 moves service envelopes into a broader
   versioning policy.
