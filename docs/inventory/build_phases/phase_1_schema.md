---
okf_version: "0.1"
type: "Build Prompt"
title: "Intake Portal — Phase 1: Schema"
description: "The models, enums, and constraints that carry the intake rewrite. Five tables become three. Completed 2026-08-20."
tags: [inventory, intake, build-prompt, schema, phase-1]
context_tier: 2
personas: [backend]
created: 2026-08-21
created_by: Christian Bissett
updated: 2026-08-21
updated_by: Christian Bissett
---

# Phase 1 — Schema

**Status: complete (2026-08-20).** Recorded here so the sequence is legible.

## The prompt

Read these two documents in full before writing anything:

- `docs/inventory/intake_portal_workflow.md` (the spec — 24 resolved decisions)
- `docs/inventory/tech_debt/intake_shipment_graph_closure.md` (deferred, context only)

They supersede the current single-page intake session surface. Where the spec
and the existing code disagree, the spec wins.

**BUILD PHASE 1 ONLY: schema.**

1. `app/inventory/models/intake/` — apply §12.1, §12.2, §12.3, §12.4, §12.5, §12.7.
   - `IntakeSession`: add `recording_locked_at/_by`, `stock_posted_at/_by`,
     `activity_thread`, `active_shipment`, `continues_session`. Retire
     `closed_at` and `has_unlinked_allocations`.
   - `ItemAllocation`: add `link_source`, `linked_at/_by`, `raw_payload`,
     `notes`. Add the constraint `serial_number = '' OR quantity = 1`.
   - **Delete** `PartReconciliationSession` and `PartReconciliationLine`
     entirely. Nothing replaces them. Five tables become three.
   - Enums: delete `ReconciliationResolutionType` and `ReconciliationStatus`,
     remove `RECONCILING` from `IntakeSessionStatus`, add `AllocationLinkSource`.
2. Update anything importing the deleted models/enums so the project still
   checks clean. Don't redesign — get it importing and passing.
3. Full DB reset per the always-apply migration rule: `python refresh_project.py`.

**Two things that are easy to get wrong:**

- The over-allocation ban (§7.2) is an aggregate across rows, so it CANNOT be
  a `Meta.CheckConstraint`. Phase 1 adds columns only.
- Carry this sentence into the code where it matters: *"The shipment line is
  the unit of truth. The session is a lens onto it."*

## Decisions taken during the build

| Question | Decision |
| :--- | :--- |
| `activity_thread` nullability | **Nullable + lazy** via `events.ActivityThreadManager`, matching Part/PartRevision/SupplierItem/DispatchExpense rather than Asset's eager non-null pattern |
| Reconciliation control layer | **Deleted wholesale**, including `reassign_allocation` and `pull_external_allocation` — Phase 2 rewrites linking under the over-allocation ban |
| Reconciliation surface, seed, tests | Routes/entrypoint/templates deleted; seed's reconciliation half trimmed; tests asserting on deleted tables removed |
| What `close()` stamps | **`stock_posted_at/_by` only.** `recording_locked_at` stays null until Phase 2 builds the explicit lock action |

## Outcome

- Migrations regenerated from scratch; all fixtures and all six seeds succeeded.
- Inventory tests: 105/105 (baseline 119/119; the delta is deleted
  reconciliation coverage, not regressions).
- Full suite: 427 tests, 5 pre-existing `maintenance_create` errors unrelated
  to intake.
