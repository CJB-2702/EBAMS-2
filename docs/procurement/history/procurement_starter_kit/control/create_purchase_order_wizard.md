---
okf_version: "0.1"
type: "Process Guide"
title: "Workflow — Create Purchase Order (Wizard)"
description: "The highest-traffic Buyer workflow: building a PO from a pool of open demands, the session-backed draft, vendor selection without a Vendor table, and the allocation decisions made at create time."
tags: [process-guide, demand-and-purchasing, control-layer, workflow, purchase-order]
context_tier: 2
personas: [backend, business]
---

# Workflow — Create Purchase Order (Wizard)

The single most important workflow in this build. A Buyer turns a pool of open demands into a
commercial order. Daily, high frequency (D44).

Post-creation editing is in
[purchase_order_line_editing.md](purchase_order_line_editing.md); status movement is in
[purchase_order_lifecycle.md](purchase_order_lifecycle.md).

---

## Why this is a wizard

A `PurchaseOrder` has two reverse FKs a Buyer populates in the same sitting — `PurchaseOrderLine`,
and `PurchaseOrderDemandLink` under each line. That is the project's stated wizard trigger, and it
is a real one here: the Buyer is making a sequence of dependent decisions (which vendor, therefore
which parts, therefore which demands, therefore how much) where each step changes what the next one
should show.

Per project convention this is **one long scrolling page on one route** with progressive
enablement and a session-backed draft — not `/step-1`, `/step-2`. The route shape is the front-end
kit's problem; what matters here is that the control layer must support a draft that accumulates
across many requests and commits **once, atomically, at the end**.

### The draft is not a database row

`PurchaseOrderDraftAdaptor` owns a session-backed structure — vendor, header fields, and a list of
lines each carrying its own list of `(demand_id, quantity_allocated)` pairs. Nothing is written
until submit.

This matters: a half-built PO in the database would be visible to other Buyers, would need a status
value meaning "not really a PO yet," and would leave orphans when abandoned. `Draft` status means
"a real PO not yet sent to the vendor," which is a different and legitimate thing.

---

## `create_purchase_order`

**Business goal.** Turn approved need into a placed order with a vendor.

**Actor.** Buyer — the `buy` permission (D2).

### Steps

1. **Select the vendor.** See below — there is no `create_vendor` step.

2. **Assemble lines.** For each part being bought: `part`, `quantity_ordered`, `unit_cost`,
   optional `expected_delivery_date` and `notes`. Line numbers are assigned in order.

3. **Attach demands to each line.** For each line, the Buyer sees open demands for **that part**,
   ordered by `priority` then `needed_by`, and chooses which to allocate and how much of each. See
   `allocate_demand_to_po_line` below. Attaching zero is fully valid (D14).

4. **Submit.** `PurchaseOrderFactory.create_from_draft(draft, actor)` runs the whole thing in one
   transaction:

   ```
   PurchaseOrderFactory.create_from_draft(...)
     ├─ create events.Event                      (D17 — one per PO, for its lifetime)
     ├─ INSERT PurchaseOrder (status=Draft, event=…)
     ├─ for each line:
     │    ├─ PurchaseOrderLineManager.add_line(commit=False)
     │    └─ for each allocation:
     │         └─ PurchaseOrderDemandLinkManager.allocate(commit=False)
     ├─ PurchaseOrderCostManager.recompute(commit=False)
     ├─ PurchaseOrderEventEmitter.emit(PO_CREATED)      (D48)
     └─ commit
   ```

5. **The PO opens as `Draft`, not `Placed`.** Creating the paperwork is not sending it. The Buyer
   places it as a separate, deliberate act — see
   [purchase_order_lifecycle.md](purchase_order_lifecycle.md).

   The legacy `from_dict` factory created POs directly as `Ordered`, skipping `Draft` entirely,
   which meant there was no state in which a PO could be reviewed before the vendor was told. Not
   repeated.

---

## Vendor selection — replacing `create_vendor` (D45)

**There is no `create_vendor` task and no `Vendor` table.** The wizard's vendor step is a picker
over the existing `parts.PartManufacturer` registry, plus a free-text `vendor_contact` the Buyer
fills in per PO.

Consequences for this workflow:

- **A missing vendor is a `parts` problem, not a purchasing one.** If the distributor is not in
  the registry, someone adds it there — through the parts app's existing manufacturer-create path,
  which already has its own uniqueness guard. The wizard links out to it rather than growing a
  create-vendor step of its own.
- **Vendor and manufacturer are now the same registry.** A part is defined by who makes it; the PO
  is placed with whoever sells it; both are rows in `PartManufacturer`. Where those differ, the
  registry holds both entries and nothing connects them. That is accepted (see
  [../models/purchase_order.md](../models/purchase_order.md) for the full trade).
- **Contact lives on the PO.** Per-category contacts (turbine vs. avionics at the same vendor) are
  recorded naturally as different strings on different POs, without any model supporting the idea.

---

## `allocate_demand_to_po_line` — at create time

The same operation as the post-creation version in
[purchase_order_line_editing.md](purchase_order_line_editing.md), with one difference: inside the
wizard it runs against draft state and commits with everything else. The rules are identical.

### The cap and the explicit choice (D28)

A demand's outstanding need is `quantity_requested − purchased_qty`. Allocating more than that does
**not** silently succeed and does **not** flatly fail. `PurchaseOrderDemandLinkValidator` returns a
decision the Buyer must resolve:

- **Raise the request** — increase `PartDemand.quantity_requested` to cover the allocation. This
  carries a strong warning, because it is only appropriate if the originating task genuinely needs
  that much. Raising the request to make a bulk buy fit is falsifying what somebody asked for.
- **Leave the excess unallocated** — the PO line carries more than it allocates. Entirely normal:
  minimum order quantities, bulk pricing, and stock reserved for a demand that does not exist yet
  (D14, extended to partially-linked lines).

The cap is **per demand, never per line.** The legacy `link_demand` capped against the line's
remaining quantity and always allocated the demand's full amount, which made splitting one demand
across two POs impossible — the exact case the many-to-many exists for.

### Auto-approval on link (D42)

Creating a `PurchaseOrderDemandLink` **auto-promotes `demand_state → Approved` by default.**

This is not a shortcut around gate 1 — gate 1 (D9) is unchanged and still blocks `purchasing_state`
from leaving `null` without approval. What changes is how approval is usually reached: in real
usage Purchasing routinely acts before an Approver signs off, directed through outside channels.
Hard-blocking the Buyer's link would stop daily work waiting on a step the organization has already
decided informally.

The Buyer can check a box before submitting to **leave the demand unapproved**, preserving the
strict approve-first process for that item. In that case gate 1 holds and `purchasing_state` stays
`null` until an Approver actually acts.

The resulting `PartDemandUpdate` records the Buyer as actor with `is_system_generated = False` —
they did approve it, by linking it.

### Validations that do run

- **Part match.** The demand's part must equal the line's part. Carried forward from the legacy
  `add_link_to_line`, which got this right — allocating a demand for one part to a line buying
  another is never intentional.
- **No duplicate pairing.** One `PurchaseOrderDemandLink` per `(demand, line)`. Allocating more
  means editing the existing row.
- **Positive quantity.** `quantity_allocated > 0`.

### A legacy validation deliberately dropped

The legacy factory refused to link a demand whose `issue_status` was `Issued`/`Installed`. This
build does not: a demand can be issued from stock on hand and *then* have a PO cut to replace what
was taken. `issuance_state` gates nothing (D11).

---

## Classes touched

| Class | Role here |
| :--- | :--- |
| `PurchaseOrderDraftAdaptor` | Session-backed draft; wizard payload → typed input |
| `PurchaseOrderFactory` | `create_from_draft` — the whole atomic build |
| `PurchaseOrderLineManager` | Line creation inside the transaction |
| `PurchaseOrderDemandLinkManager` | Allocation creation inside the transaction |
| `PurchaseOrderDemandLinkValidator` | D28's cap decision, part match, duplicate check |
| `PurchaseOrderCostManager` | `total_cost` |
| `PurchaseOrderEventEmitter` | `PO_CREATED` (D48) |
| `PurchaseOrderNarrator` | Opening machine comment on the Event |
| `PartDemandContext` | `approve()` for the D42 auto-promotion |
| `PartDemandQuantityManager` | `purchased_qty` refresh per affected demand |

---

## Reads this workflow needs

These are complex multi-table reads and belong in `presentation_layer/search/`, not in an
entrypoint:

- **`OpenDemandSearch`** — demands allocatable to a given part: not cancelled, not fully allocated,
  within the Buyer's domain access, ordered by `priority` then `needed_by`. Must annotate
  outstanding quantity rather than computing it per row.
- **`PurchaseOrderStruct`** — the assembled PO with lines, allocations, and every derived total in
  one annotated query.

The legacy `get_po_lines_with_demands` built this by looping lines, constructing a context per
line, and issuing several queries inside each — then `DemandOriginResolver.resolve()` per demand on
top. Annotate once instead.
