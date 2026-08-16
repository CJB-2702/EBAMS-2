---
okf_version: "0.1"
type: "Reference"
title: "Model — PartDemandUpdate"
description: "Schema for the append-only four-axis journal: the only legal writer of PartDemand's snapshot columns, and the uniform who/when/why record the legacy hub lacked."
tags: [reference, demand-and-purchasing, data-model, journal]
context_tier: 2
personas: [backend]
---

# Model — `PartDemandUpdate`

`app/procurement/models/demand/part_demand_update.py`

One row per transition, on any of the four axes. Append-only: rows are never updated, never
deleted, never soft-deleted. Inherits `AuditFieldsMixin` only — no soft delete, by design.

This table exists because of a specific failure in the legacy hub: `approval_status` got real audit
columns while `issue_status` and `order_status` got none, so there was no record of who marked
something issued or why an order status moved. Tracking state as bare columns makes that the
natural outcome — the first dimension gets audit columns and later ones get skipped. One uniform
journal for all four axes removes the choice.

---

## Columns

| Column | Type | Notes |
| :--- | :--- | :--- |
| `part_demand` | FK → `PartDemand`, `CASCADE` | The journal dies with a hard-deleted demand — which per D6 can only happen while the demand has zero journal rows anyway |
| `dimension` | `TextChoices` — `demand · purchasing · shipment · issuance` | Which axis moved |
| `stage` | `CharField` | The value the axis moved **to**. Not FK-constrained to an enum table — validated against the dimension's `TextChoices` in the guard, per D22's "fixed hardcoded enum" rule |
| `previous_stage` | `CharField(blank=True)` | The value it moved **from**. Blank on the initializing rows |
| `actor` | FK → user, `PROTECT`, nullable | Nullable because derived transitions (the D43 `Completed` rollup, PO-driven axis propagation) have no human actor |
| `is_system_generated` | `BooleanField(default=False)` | `True` for derived/propagated transitions. Lets a UI distinguish "Buyer marked this" from "this followed from a PO status change" |
| `notes` | `TextField(blank=True)` | Optional free text, **even for `Rejected`/`Cancelled`** (D15). No mandatory reason is enforced |
| `flagged_for_review` | `BooleanField(default=False)` | Set when a guard failed open (D13) — the transition went through but could not be verified |

`created_at` from the mixin is the transition timestamp. No separate `occurred_at` column.

---

## Constraints and indexes

- Index on `(part_demand, created_at)` — the demand-history read, which is the only common query.
- Index on `(dimension, stage)` — cross-demand reporting ("everything that hit Backordered").
- Index on `flagged_for_review` (partial, `WHERE flagged_for_review`) — the fail-open review queue.

No unique constraints. The same transition may legitimately recur (`Rejected → Required → Rejected`).

---

## The write contract

`PartDemandUpdate` and `PartDemand`'s four snapshot columns are written **together, in one
transaction, by one class** — `PartDemandStateManager`. There is no code path that writes one
without the other.

```
PartDemandStateManager.transition(axis, to_stage, actor, notes)
  ├─ PartDemandTransitionStateMachine  → legal? gated? (D9–D11, fail open per D13)
  ├─ INSERT PartDemandUpdate
  ├─ UPDATE PartDemand.<axis>_state    ← the snapshot refresh
  └─ DemandCompletionHandler.check()   → may recurse once for the D43 rollup
```

Snapshot columns are a cache. If they ever disagree with the journal, the journal wins and the
snapshot is rebuildable from it — which is the point of making them append-only.

---

## Deliberately absent

- **No `PurchaseOrderUpdate` counterpart.** The PO side uses machine comments on its `Event`
  instead (D18). The two sides are deliberately asymmetric, not inconsistent by accident: a demand's
  axes are structured, queryable state; a PO's status history is narrative.
- **No transition-legality table.** The legal-transition shape is a Python dict per dimension in
  the guard (D23), visible in one place, not database-driven. It is not the seed of a rules engine
  — the generalized version is deferred tech debt (D21).
