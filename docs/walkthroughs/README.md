# Walkthroughs

This directory contains **synthetic day-in-the-life scenarios** illustrating how Lathe is used by each persona.

> **These are synthetic. They are not case studies.** No real user has (yet) agreed to be quoted here. Every build trace, every timing, every failing-validator report in these docs is a plausible mock — constructed from the current reference scaffold's actual behavior, but not recorded from a live design-partner session.
>
> When a design partner signs under LOI (see `docs/business/design_partners.md` once authored; target Month 4 per `docs/roadmap_public.md`) and agrees to be quoted, their real story **replaces** the corresponding synthetic walkthrough here. Until then these scenarios exist to pressure-test the value proposition and to give Persona-A / Persona-B / Persona-C readers a narrative they can map themselves onto.

## Walkthroughs in this directory

1. [`01_godot_indie_crate_family.md`](01_godot_indie_crate_family.md) — **Persona A.** Solo Godot dev ships 12 crate variants in an afternoon.
2. [`02_studio_door_contract.md`](02_studio_door_contract.md) — **Persona B.** TD encodes a studio door contract; junior artist's PR fails certification on UV density; one-line fix.
3. [`03_agent_authored_panel.md`](03_agent_authored_panel.md) — **Persona C.** Coding agent takes a bug report, emits an `.lth` diff, lands a certified PR.

## When to replace a walkthrough with a real case study

- A design partner has signed an LOI and agreed to logo + quotation rights.
- The partner has actually run `lathe build` on their asset in their repo.
- The timing, source diff, and build trace are **lifted from their real session**, not constructed.
- The partner has reviewed the rewritten document and signed off in writing.

Until all four conditions are met, keep the synthetic marker at the top of the file intact. Calling a synthetic scenario a "case study" misleads readers and erodes trust in the ones that are real.
