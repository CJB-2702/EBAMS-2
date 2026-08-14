---
okf_version: "0.1"
type: "Reference"
title: "Model — PurchaseOrderLine"
description: "Schema for one line item on a purchase order: no status column, the one-active-line-per-part rule, and the quantities derived from it."
tags: [reference, demand-and-purchasing, data-model, purchase-order]
context_tier: 2
personas: [backend]
---

# Model — `PurchaseOrderLine`

`app/procurement/models/purchasing/purchase_order_line.py`

One line item on a `PurchaseOrder`. One-to-many from the header. Inherits `AuditFieldsMixin` and
`SoftDeleteMixin`.

---

## Columns

| Column | Type | Notes |
| :--- | :--- | :--- |
| `purchase_order` | FK → `PurchaseOrder`, `CASCADE`, `related_name="lines"` | Lines have no meaning apart from their header |
| `part` | FK → `parts.Part`, `PROTECT` | What is being bought |
| `line_number` | `PositiveIntegerField` | Auto-assigned as `max(existing) + 1` at create; reorderable by the Buyer |
| `quantity_ordered` | `DecimalField` | How much of `part` this line buys |
| `unit_cost` | `DecimalField` | Price per unit at order time |
| `expected_delivery_date` | `DateField(null=True)` | Line-level override of the header estimate |
| `notes` | `TextField(blank=True)` | |

### No line-level status

The legacy line carried its own `status` (`Pending/Ordered/Shipped/Complete/Cancelled`) cascaded
from the header, which meant three tables (`header`, `line`, `demand`) all held a partial copy of
the same fact and could disagree. This build drops it: a line's state is its header's `status`, and
arrival progress is physical — `PackageLine.quantity_accepted` against this line.

**Cancellation is a soft delete plus an audit comment, not a status value** (D57). A cancelled line
is `deleted_at`-stamped; the record of the cancellation — who, when, and a JSON snapshot of the row
as it stood — lives as a machine comment on the PO's `Event`. Cancelling also removes the line's
demand links and resets those demands' `purchasing_state` to `null`
(see [purchase_order_demand_link.md](purchase_order_demand_link.md)).

### No `is_fake_for_inventory_adjustments`

The legacy line had a boolean marking synthetic lines created purely to book an inventory
adjustment. Inventory adjustments are not in this build's scope, and a flag that makes a
commercial document sometimes not a commercial document is exactly the kind of overload to leave
behind.

---

## Derived, never stored

| Value | How | Where it lives |
| :--- | :--- | :--- |
| `line_total` | `quantity_ordered × unit_cost` | `PurchaseOrderLineStruct` |
| `quantity_allocated_total` | `sum(PurchaseOrderDemandLink.quantity_allocated)` for this line | `PurchaseOrderLineStruct` |
| `quantity_unallocated` | `quantity_ordered − quantity_allocated_total` | `PurchaseOrderLineStruct` |
| `qty_from_accepted_packages` | `sum(PackageLine.quantity_accepted)` pointing at this line | `PurchaseOrderFulfillmentStruct` |
| `qty_issued` | `sum(PartDemand.issued_qty)` across linked demands | `PurchaseOrderFulfillmentStruct` |

The legacy model put every one of these on the model as a `@property` that issued its own query —
so rendering a 40-line PO fired well over a hundred queries. They belong on the struct, computed
once with an annotated queryset. No business logic on models.

---

## The key asymmetry: allocation is capped, ordering is not

`quantity_ordered` may exceed the sum of what is allocated to demands. That is not a defect state
to be reconciled — it is three legitimate cases at once (D14, D28):

1. **Proactive/bulk restocking** — the line has zero linked demands.
2. **Minimum order quantity / bulk pricing** — the Buyer must buy 10 to satisfy a demand for 5.
3. **Reserve for later** — the unallocated remainder stays available to link to a future demand.

So the cap in D28 is enforced **per demand**, never per line: a `PurchaseOrderDemandLink` cannot allocate
more than its demand's outstanding `quantity_requested − purchased_qty`, but a line is always free
to carry more than the sum of its allocations.

The legacy `PurchaseOrderLinkManager.link_demand` had this backwards — it checked
`demand_quantity > (quantity_ordered − already_allocated)` and refused the link, capping against
the *line's* remaining quantity and silently allocating the demand's full quantity with no partial
option. That made splitting one demand across two POs impossible, which is the exact case the
many-to-many join exists for.

---

## Constraints and indexes

- `CheckConstraint`: `quantity_ordered > 0`.
- `CheckConstraint`: `unit_cost >= 0`.
- `UniqueConstraint(purchase_order, line_number)`.
- Index on `(part, purchase_order)` — "which open POs cover this part," the wizard's key read.

### One active line per part, per PO — control layer only (D58)

A PO carries at most one **non-deleted** line per part. Two consequences of scoping it to active
lines: cancel-and-replace legitimately leaves a deleted line for the same part behind, and a
re-priced item becomes two rows where only the live one counts.

Enforced as a **soft UI error**, never a database constraint: the Buyer is told the part is already
on this order and pointed at the existing line. Nothing hard-blocks. A duplicate that gets through
degrades gracefully — arriving package lines for that part land unassigned rather than
mis-assigned, and the fulfillment struct flags them.

Two reasons it is not a DB constraint. First, the rule is about pricing simplicity — one part, one
price, one line — not about data integrity, and the day split delivery dates or tiered pricing
justify relaxing it, that should be a guard change rather than a migration against live data.
Second, package-line assignment resolves *part → PO line*, and that resolution is only unambiguous
while the rule holds; the soft version keeps the failure visible instead of impossible.
