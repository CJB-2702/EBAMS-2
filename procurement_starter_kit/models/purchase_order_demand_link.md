---
okf_version: "0.1"
type: "Reference"
title: "Model — PurchaseOrderDemandLink"
description: "Schema for the demand ↔ PO-line allocation join: quantity_allocated, why there is no quantity_received column, and what line cancellation does to a demand."
tags: [reference, demand-and-purchasing, data-model, allocation]
context_tier: 2
personas: [backend]
---

# Model — `PurchaseOrderDemandLink`

`app/procurement/models/purchasing/purchase_order_demand_link.py`

The many-to-many allocation row between a `PartDemand` and a `PurchaseOrderLine`.

**Naming lineage:** the legacy app called this `PartDemandPurchaseOrderLink`; M1 renamed it
`DemandSetLine` to take the overloaded word "Order" out of the join's name; it is now
**`PurchaseOrderDemandLink`**. The reason for the final name is forward-looking: this will not be
the only table linking demands to something. Maintenance actions, dispatches, and later inventory
concepts each need their own demand-link table, so the family reads
`<thing>DemandLink` — `PurchaseOrderDemandLink`, and by the same rule whatever a future consumer
app names its own. `DemandSetLine` gave no such handle, and the word "set" implied a grouping
concept that does not exist.

Singular, per this codebase's model naming (`Part`, `PartDemand`, `PurchaseOrderLine`). Table
`purchase_order_demand_link`.

A **peer join row**, not a restricted view of either side (M2): it carries attributes that belong
to the *pairing* and to neither side alone. Inherits `AuditFieldsMixin` and `SoftDeleteMixin`.

---

## Columns

| Column | Type | Notes |
| :--- | :--- | :--- |
| `part_demand` | FK → `PartDemand`, `PROTECT` | `PROTECT`, not `CASCADE` — an allocation is exactly what D6 means by "touched" |
| `purchase_order_line` | FK → `PurchaseOrderLine`, `CASCADE`, `related_name="allocations"` | An allocation to a deleted draft line is meaningless |
| `quantity_allocated` | `DecimalField` | How much of this PO line is claimed by this demand (D28-capped) |
| `is_active` | `BooleanField(default=True)` | Released allocations — see the cancellation case below |
| `notes` | `TextField(blank=True)` | |

---

## There is no `quantity_received` (D55 — reverses D26)

An earlier draft carried `quantity_received` here, on the theory that recording receipt against the
*allocation* rather than the PO line was what made per-demand fulfillment answerable. That theory
was wrong, and the column is gone.

The problem is not where the number is stored — it is that **for a shared PO line the number does
not exist.** Three demands allocated against one line, sixty units arrive in a box: the units are
fungible, nobody at the vendor decided whose they were, and any attribution a receiver typed in
would be an invention recorded as though it were observed. A column invites exactly that invention,
and launders it into the audit trail.

So arrival is recorded once, physically, on `PackageLine.quantity_accepted`, and per-demand arrival
is **derived** under an explicit rule:

- A PO line with **exactly one** active link → that demand's arrival is the line's accepted total.
  A real, reportable number.
- A PO line with **two or more** → a **shared demand session**. The only truthful report is the
  session total and its membership; no per-demand figure is produced at all.

Full reasoning, and the remedy available to a Buyer who needs attributability, is in
[../shared_demand_sessions.md](../shared_demand_sessions.md).

The legacy app is instructive here in a way its authors probably did not intend: it built
`ArrivalLine` plus an `ArrivalPurchaseOrderLink` many-to-many carrying `quantity_linked`,
attributing receipts to *PO lines* and never to demands — so its demand-side `order_status` could
only say "Ordered" or "Arrived" for a whole demand. That looks like a gap. It is closer to an
accurate reflection of what the data can support; what was missing was a way to *say so*.

---

## Constraints and indexes

- `UniqueConstraint(part_demand, purchase_order_line)` — one allocation per pairing. A Buyer who
  wants more allocates more on the existing row, they do not create a second.
- `CheckConstraint`: `quantity_allocated > 0`.
- Index on `(part_demand, is_active)` — the `purchased_qty` recompute.
- Index on `(purchase_order_line, is_active)` — the line's allocation rollup.

### A validation the legacy app had, kept

`PurchaseOrderDemandLink.part_demand.part` must equal `PurchaseOrderDemandLink.purchase_order_line.part`. Enforced in
`PurchaseOrderDemandLinkValidator`, not as a DB constraint (it spans three tables). The legacy
`add_link_to_line` checked this and it is a genuinely good check — allocating a demand for one part
to a line buying a different part is never intentional.

---

## `is_active`, PO cancellation, and line cancellation

**PO cancelled mid-flight.** Every allocation on it is released: `is_active = False`.
`purchased_qty` recomputes across active rows only, freeing the Buyer to re-allocate to a new PO
line. Physical arrivals already recorded on package lines are untouched — what arrived, arrived,
regardless of what happens to the PO administratively afterward.

**Line cancelled** (D56). Cancelling a PO line **removes every demand link on it** — the links are
soft-deleted — and sets each affected demand's `purchasing_state` back to `null`. Those demands
return to "no purchasing decision has been made," which is accurate: the thing that was going to
buy them is gone. Their `demand_state` is left alone; a Requester or Approver cancels them manually
later if the need itself has also gone away. This is the default and it is not configurable.

`purchasing_state: Purchased → null` must therefore be a legal transition in the demand-side
transition dict. It is the one backward move in that axis, and it exists only for this path.

`is_active = False` rows are excluded from every `purchased_qty` sum but stay readable as history.
Distinct from soft delete: a de-linked allocation (a Buyer changing their mind, D4, or a cancelled
line) is soft-deleted; a *released* allocation is deactivated.

---

## Deliberately absent

- **No `quantity_received`** (D55, above). Arrival is physical, recorded once on `PackageLine`.
- **No `quantity_returned`.** Returns are demand-level, not allocation-level — a second negative
  `PartIssue` row (D39). Material returned by a requester does not un-receive from a vendor.
- **No status column.** An allocation's meaningful states are fully expressed by `quantity_allocated`
  plus `is_active`.
- **No FK to `Package` or `PackageLine`.** The FK goes the other way: `PackageLine` points at
  `PurchaseOrderLine`. Both tables are in `procurement` (D63), so this is an ordinary parent/child
  direction within one app — there is no cross-app crossing and no exception.
