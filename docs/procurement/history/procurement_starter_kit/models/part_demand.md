---
okf_version: "0.1"
type: "Reference"
title: "Model — PartDemand"
description: "Schema for the hub record: four state axes, three quantity columns, origin/tracking flags, domain scoping, and the enum definitions."
tags: [reference, demand-and-purchasing, data-model, part-demand]
context_tier: 2
personas: [backend]
---

# Model — `PartDemand`

`app/procurement/models/demand/part_demand.py`

The hub (G3). A material need moving from request through approval, purchasing, shipping, and
physical hand-off. The rest of this app and every consumer app knows **only** `PartDemand.id`.

Inherits `AuditFieldsMixin` (`created_at`/`updated_at`/`created_by`/`updated_by`) and
`SoftDeleteMixin` (`deleted_at`) — soft delete is required by D6.

---

## Columns

### Identity and subject

| Column | Type | Notes |
| :--- | :--- | :--- |
| `part` | FK → `parts.Part`, `PROTECT` | Many demands per part. Never nullable |
| `notes` | `TextField(blank=True)` | Free-form. One of only two free-text surfaces on the demand side (M6) |
| `priority` | `CharField` choices `Low/Medium/High/Critical` | Intrinsic to the need (M4) |
| `needed_by` | `DateTimeField(null=True)` | Intrinsic to the need (M4) |
| `requested_by` | FK → user, `PROTECT`, nullable | Who asked. Distinct from `created_by`, which may be a consumer app's service actor |
| `expected_cost` | `DecimalField(null=True)` | Carried forward from the legacy hub; informational only |

### The four state axes (D32)

All four are `TextChoices` snapshot columns. **None is ever written directly** — every change goes
through `PartDemandUpdate` and the state manager refreshes the snapshot alongside the journal
insert (§4 of `part_demand_system.md`).

| Column | Default | Enum |
| :--- | :--- | :--- |
| `demand_state` | `Projected` | `Projected · Required · Approved · Rejected · Cancelled · Completed` (D33) |
| `purchasing_state` | `null` | `null · Approved · Denied · Purchased · Cancelled` (D34) |
| `shipment_state` | `Request Not Sent` | `Request Not Sent · Request Received by Vendor · Production in Progress · Vendor Prepared to Ship · Shipped · Backordered · Lost · Delivered to Depot · Delivered to Local Receiving Location · In Stock` (D35) |
| `issuance_state` | `Not Issued` | `Not Issued · Partially Issued · Issued · Issued Pending Reconciliation` (D36) |

`purchasing_state` is the one nullable axis — `null` is a real, meaningful default meaning "no
purchasing decision has been made," not missing data.

**Enum surfaces this build does not drive:** `shipment_state.In Stock` and the
`Issued ↔ Issued Pending Reconciliation` transitions. The values exist so a later Inventory app has
something to target; nothing in this build writes them.

### Quantities (§5 of `part_demand_system.md`)

| Column | Type | Default | Maintained by |
| :--- | :--- | :--- | :--- |
| `quantity_requested` | `DecimalField` | — | Requester at create; a Buyer may raise it via D28's explicit-choice path |
| `purchased_qty` | `DecimalField` | `0` | Sum of `PurchaseOrderDemandLink.quantity_allocated` across active allocations. Refreshed on every allocation write |
| `issued_qty` | `DecimalField` | `0` | **Net**, not a running total. Refreshed only by `PartDemandContext.record_issuance(...)` |

Named `quantity_requested` deliberately, never bare `quantity` (D31) — four quantity-flavored
fields exist across two models and a bare name is too easy to misread.

`issued_qty` may legitimately be `0` after a full return (D39), and may exceed or fall short of
both `purchased_qty` and `quantity_requested` with no validation blocking it (D30).

### Origin and tracking flags (D38)

| Column | Type | Notes |
| :--- | :--- | :--- |
| `source_module` | `CharField` choices `Maintenance/Dispatching/General` | Renamed from the legacy `part_demand_type`. A denormalized filter/display convenience **only** — never a source of truth for origin detail |
| `serial_number_tracking_required` | `BooleanField(default=False)` | Declared upstream, consumed by a future Inventory app. Nothing in this build reads it |

### Domain scoping (D5)

Exactly one domain assignment, **mandatory**. Unlike `parts.Part`, there is no
`is_domain_limited` escape hatch and no `PartDemandDomainAccessMapping` many-to-many — a demand
identifies who is meant to receive the part, and that is always exactly one answer.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `domain` | FK → `administration.Domain`, `PROTECT` | Not nullable. Auto-assigned by whoever creates the demand |

The factory carries a docstring stating this contract explicitly, for the benefit of future
consumer-app authors who will call it (per the P4 note).

---

## Constraints and indexes

- `CheckConstraint`: `quantity_requested > 0`.
- `CheckConstraint`: `purchased_qty >= 0`.
- Index on `(demand_state, domain)` — the Approver queue read.
- Index on `(purchasing_state, demand_state)` — the Buyer's "what needs buying" read.
- Index on `(part, demand_state)` — the wizard's "find demands for this part" read.
- Index on `needed_by` — priority ordering in the Buyer's queue.

No unique constraints. Demands are not versioned and have no user-facing identifier (M5).

---

## Deliberately absent

- **No `Event`/`ActivityThread` FK.** The two `notes` fields are considered sufficient for the
  demand side (M6). Only `PurchaseOrder` gets an Event.
- **No reverse pointer to any consumer app.** No `action_id`, no `dispatch_id`, no
  `maintenance_demand_link`. Consumer apps own their own link tables pointing inward (D7).
- **No backward-compat properties.** The legacy hub's `.status`, `.action`, `.action_id` shims
  were migration residue and are not carried forward.
- **No per-axis audit column pairs.** The legacy hub gave `approval_status` four audit columns
  (`maintenance_approval_by_id`/`_date`, `supply_approval_by_id`/`_date`) and gave `issue_status`
  and `order_status` none — that inconsistency is exactly what `PartDemandUpdate` exists to fix.
  Who/when/why lives in the journal, uniformly, for all four axes.
- **No `was_borrow_and_return` / `quantity_returned` columns.** The legacy pair was never
  populated; returns are a second negative `PartIssue` row instead (D39).
- **No `issued_from_stock` / `stock_reimbursed` flags.** Those are inventory's concern, and
  reading them would require this app to care about where material came from.

---

## Updated by D71-D78 (Phase 0 build)

- **`IssuanceState` gains `ISSUED_RECONCILIATION_REQUIRED`** (D77), distinct from
  `ISSUED_PENDING_RECONCILIATION`: the existing value is the active borrow/return loan state, the
  new one means a physical hand-off already happened and the inventory system's books have not
  caught up yet. The backwards `Issued -> Reconciliation Required` transition is now legal.
- **New `Meta.permissions`: `request` and `demand_manage`** (D78) — see
  [../control/index.md](../control/index.md) and the permission vocabulary table in D78.
