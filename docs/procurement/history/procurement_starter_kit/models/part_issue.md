---
okf_version: "0.1"
type: "Reference"
title: "Model — PartIssue"
description: "The inventory-side issuance record: a signed quantity handed to a person against a demand, the write seam that keeps issued_qty honest, and the full list of what inventory does not get this build."
tags: [reference, procurement, inventory, data-model, boundaries]
context_tier: 2
personas: [backend]
---

# Model — `PartIssue`

`app/inventory/models/issuance/part_issue.py`

A quantity of material handed to a person against a demand. Inherits `AuditFieldsMixin` and
`SoftDeleteMixin`.

Packages are in [package.md](package.md) under `app/procurement/`.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `part_demand` | FK → `procurement.PartDemand`, `PROTECT` | Inventory pointing inward |
| `issued_to` | FK → user, `PROTECT` | The person receiving the material |
| `quantity` | `DecimalField` | **Signed.** Positive = issued out; negative = returned (D39) |
| `issued_at` | `DateTimeField` | Defaults to now |
| `notes` | `TextField(blank=True)` | |

- `CheckConstraint`: `quantity != 0`.
- Index on `(part_demand, issued_at)`.

`PROTECT` on `part_demand` is what makes D7 work: `procurement`'s delete guard never has
to know `inventory` exists, because the FK blocks the delete for free from the consumer side.

---

## Explicitly not on `PartIssue`

**No source-of-quantity tracking of any kind** — no storeroom, no location, no bin, no lot, no
serial, no `inventory_movement` FK, no `unit_cost_at_issue`, no `issue_type` discriminator, no
`asset_id` recipient. The legacy `PartIssue` carried every one of these; here they are deferred
whole to the later Inventory build.

There is also no direct-to-asset field. If material's context involves a specific asset, that
resolves through the demand's own origin, not redundantly on the issue row.

---

## The write path is the seam, not the table

Creating a `PartIssue` row is not, by itself, an issuance. The demand's `issued_qty` and
`issuance_state` only move when `PartIssuanceOrchestrator` calls
`PartDemandContext.record_issuance(...)` in the same transaction (D12).

```
inventory.PartIssuanceOrchestrator.issue(demand_id, issued_to, quantity, actor)
  ├─ INSERT inventory.PartIssue
  ├─ net = Σ PartIssue.quantity for this demand        ← computed in inventory
  └─ procurement.PartDemandContext.record_issuance(
         net_issued_qty=net, to_stage=…, actor=actor, commit=False)
       ├─ PartDemandQuantityManager sets issued_qty = net_issued_qty
       ├─ PartDemandStateManager.transition(issuance, …)
       └─ DemandCompletionHandler.check()              → may auto-complete (D43)
```

`record_issuance` takes the net quantity **as an argument**. It does not query `PartIssue` to
compute it — the write direction is inward only, and `procurement` holds no FK into
`inventory`. If a `PartIssue` row is ever created outside this call, `issued_qty` drifts silently.
The orchestrator is the only supported write path.

*(Nothing reads across the boundary the other way. `PurchaseOrderFulfillmentStruct` was once
specced as a cross-app read of packages; packages moved into `procurement` (D59/D60/D63), so it is
an ordinary within-app query and no exception exists. `procurement` never reads `inventory` at all.)*

---

## What `app/inventory/` does not get this build

No stock or on-hand levels · no storerooms · no locations · no bins or bin prototypes · no
inventory movements · no inventory summary · no active-inventory table · **no intake / put-away** ·
no serial-number tracking · no cycle counts · no adjustments · no reservations.

Packages are in scope (D59, revising D47) because they are shipment tracking — what the vendor
shipped, and what survived inspection. **Intake is the next thing and is not built:** the line
between them is exactly where `PackageLine.quantity_accepted` stops. Accepting a package line
records that goods arrived intact. It does not put them anywhere, because there is nowhere to put
them.
