---
okf_version: "0.1"
type: "Build Plan Index"
title: "Intake Portal — Build Phases"
description: "The three-phase build of the intake portal rewrite: schema, control layer, presentation layer. One prompt per phase, executable in order."
tags: [inventory, intake, build-plan, phases]
context_tier: 2
personas: [backend, frontend]
created: 2026-08-21
created_by: Christian Bissett
updated: 2026-08-21
updated_by: Christian Bissett
---

# Intake Portal — Build Phases

The spec is [intake_portal_workflow.md](../intake_portal_workflow.md) — 24
resolved decisions, no open questions. The deferred problem is
[intake_shipment_graph_closure.md](../tech_debt/intake_shipment_graph_closure.md).

Each phase below is a self-contained build prompt. Run them **in order**; each
assumes the previous one landed and the test suite was green.

| Phase | Prompt | Scope | Status |
| :-- | :--- | :--- | :--- |
| 1 | [phase_1_schema.md](phase_1_schema.md) | Models, enums, constraints, full DB reset | **Complete** — 2026-08-20 |
| 2 | [phase_2_control_layer.md](phase_2_control_layer.md) | Write verbs, the over-allocation ban, auto-association, derived reads | **Complete** — 2026-08-21 |
| 3 | [phase_3_presentation_layer.md](phase_3_presentation_layer.md) | The seven surfaces, the allocation portal, the printable receipt | **Complete** — 2026-08-21 |

## The rule that governs all three

> **The shipment line is the unit of truth. The session is a lens onto it.**

Every quantity question is answered from *all* live allocations against a
line, across every non-cancelled session. Any calculation scoped to a single
session is a bug (§5.5). This sentence is carried as a comment into every
module that does the arithmetic.

## What is deliberately NOT built

Carried forward from §15, unchanged across all three phases:

- Paperwork locking of any kind (§4.4).
- Editing a locked recording session (§4.5).
- Concurrent operators on one session (Q15).
- Box/carton-level tracking (§1.3).
- Notifications (Q6).
- Any approval, sign-off, or formal closure of a discrepancy (§7.1).
- Any logic built on `continues_session` (§7.5).
- Any system reading of the pen-and-paper print columns (§9.5).
