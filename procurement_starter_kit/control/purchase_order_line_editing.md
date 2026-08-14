---
okf_version: "0.1"
type: "Process Guide"
title: "Workflow — Purchase Order Line Editing"
description: "Post-creation line and allocation work: editing lines with a mandatory audit snapshot, cancelling a line and what it does to linked demands, allocating and de-linking demands, and where receiving went."
tags: [process-guide, demand-and-purchasing, control-layer, workflow, allocation]
context_tier: 2
personas: [backend, business]
---

# Workflow — Purchase Order Line Editing

Everything a Buyer does to an existing PO's lines and allocations. Daily, high frequency (D44) —
second only to the wizard.

Creation is in [create_purchase_order_wizard.md](create_purchase_order_wizard.md); status movement
is in [purchase_order_lifecycle.md](purchase_order_lifecycle.md); receiving is in
[package_lifecycle.md](package_lifecycle.md).

---

## Editing after placement: allowed, and audited (D57)

Lines stay editable after a PO reaches `Placed`. Vendors substitute, short-ship, and re-price after
an order goes out, and the record should say what actually happened rather than what was
originally typed.

The cost of that permissiveness is paid in audit, not in restriction:

> **Every mutation to a line or allocation on a `Placed`-or-later PO posts a machine comment on the
> PO's `Event`, carrying a JSON snapshot of the row as it stood immediately before the change.**

This applies to edits and to deletions alike — a deleted row's final state is captured in the
comment before it goes. Nothing is lost, nothing is silently rewritten, and the PO's Event reads as
a complete history of the order's mutations without needing a second journal table.

`PurchaseOrderNarrator` composes the comment; the snapshot is `model_to_dict(...)` of the row
before mutation, embedded in the comment payload. It is the pre-state that matters — the post-state
is queryable from the row itself.

### Warnings, not blocks

Editing a placed order is unusual and should look unusual. The UI raises a **soft warning**; the
control layer does not refuse. This follows the standing principle: the system's job is to let
people record what actually happened, not to dictate what must be true (D29, D30).

The one hard stop: a line's `quantity_ordered` cannot be reduced below what has already been
accepted against it in packages. That is not a policy — the smaller number would be false.

---

## `cancel_purchase_order_line`

**Business goal.** Remove a line from an order that has already gone out, without destroying the
record that it was once on it.

**Actor.** Buyer.

### Steps

1. `PurchaseOrderLineManager.cancel(line_id, actor)`.
2. Machine comment on the Event with the pre-state JSON snapshot (above).
3. Soft-delete the line. **There is no line status column and no `is_cancelled` flag** — the
   cancellation lives in the audit trail (D57). A cancelled line is a soft-deleted line whose
   Event comment explains it.
4. **Soft-delete every `PurchaseOrderDemandLink` on the line.**
5. **Set each affected demand's `purchasing_state` back to `null`** (D56) — accurate, since the
   thing that was going to buy them is gone.
6. Refresh each affected demand's `purchased_qty`.

### `demand_state` is deliberately left alone

The demands go back to having no purchasing decision; they are **not** cancelled. The need may well
still be real and buyable from someone else. A Requester or Approver cancels them manually later if
the need itself has also gone away — that is their call (D4), not a side effect of a Buyer's line
edit.

This is why `purchasing_state: Purchased → null` is a legal transition. It is the only backward
move in that axis, and this is the only path that produces it.

### Replacing a line

Cancel, then add a new line. Both rows exist — one soft-deleted with its snapshot comment, one
live — which is the honest record of a substitution or re-price. Because the one-line-per-part rule
is scoped to **active** lines (D58), the replacement does not trip the guard.

---

## `allocate_demand_to_po_line`

**Business goal.** Claim part of a PO line as fulfilling a specific demand — the thing that
connects procurement to the need behind it.

**Actor.** Buyer only (D3). No other persona writes this row.

### Steps

1. `PurchaseOrderDemandLinkManager.allocate(line_id, demand_id, quantity, actor)`.
2. `PurchaseOrderDemandLinkValidator` runs:
   - **Part match** — demand's part equals line's part.
   - **No duplicate pairing** — `UniqueConstraint(part_demand, purchase_order_line)`. Increasing an
     existing claim edits that row; it never creates a second.
   - **The D28 cap decision** — see the wizard doc. Allocating beyond the demand's outstanding
     `quantity_requested − purchased_qty` returns a choice (raise the request, with a strong
     warning / leave the excess unallocated), never a silent success and never a flat refusal.
3. `INSERT` or `UPDATE` the `PurchaseOrderDemandLink`.
4. **Auto-approve** the demand (D42) unless the Buyer opted out — `PartDemandContext.approve(...)`.
5. `PartDemandQuantityManager.refresh_purchased_qty(demand_id)` — the sum of `quantity_allocated`
   across the demand's **active** links.
6. If the PO is already `Placed`, propagate: `purchasing_state → Purchased`, `shipment_state →
   Request Received by Vendor` (D40). A demand linked to an already-placed PO is, by definition,
   already bought.

The cap is **per demand, never per line.** A line is always free to carry more `quantity_ordered`
than the sum of its allocations (D14, D28).

### Allocation changes attribution mode

Adding a second demand to a line moves it from **attributable** to a **shared demand session** —
after which no per-demand arrival figure exists for either demand on that line. That is a real
consequence of an ordinary Buyer action, and the UI should say so at the moment of the second
allocation, not leave someone to discover it in a report. See
[../shared_demand_sessions.md](../shared_demand_sessions.md).

---

## De-linking — the Buyer's alternative to cancellation

**Business goal.** Undo an allocation without touching the demand's own lifecycle.

**Actor.** Buyer only. This is the substitute for cancellation: **a Buyer never cancels a demand**
(D4). Cancellation is a Requester/Approver act, gated by D10 once a PO is in flight.

### Steps

1. `PurchaseOrderDemandLinkManager.delink(link_id, actor)`.
2. Machine comment with pre-state snapshot if the PO is `Placed` or later.
3. Soft-delete the link row.
4. Refresh the demand's `purchased_qty`.
5. `purchasing_state` does **not** roll backward on a plain de-link. `Purchased` means money moved,
   and de-linking does not un-move it. (Cancelling the whole *line* is the exception — D56 —
   because there the thing that spent the money is gone.)
6. **Graph re-resolution.** If the demand — or any demand left on the line — carries
   `is_in_status_graph`, run `PoDemandAssociationGraphResolver` over each affected demand's network
   in the same transaction: clear the flag on demands no longer sharing any line, and let the
   resolver re-write `purchasing_state`/`shipment_state` for those still in a graph, since a network
   that just lost a member may have a different worst-of status and quantity ceiling. Note this is
   the resolver's own graph-level write, distinct from step 5's rule about a plain de-link — a
   demand whose network genuinely no longer supports `Purchased` is corrected here. Spec:
   [../../front-end-kit/procurement/graph_association_visualizer.md](../../front-end-kit/procurement/graph_association_visualizer.md)
   §5.2b/§5.6.

`release(...)` carries the same obligation for every allocation it de-activates.

### De-link vs. release

- **De-link** — the Buyer changed their mind about this pairing. Soft delete.
- **Release** — the PO was cancelled and the vendor is not shipping. `is_active = False` across the
  PO's allocations. See [purchase_order_lifecycle.md](purchase_order_lifecycle.md).

---

## Where `record_receipt_against_allocation` went

**It no longer exists.** There is no per-demand receipt step and no `quantity_received` column on
the allocation row (D55).

Arrival is recorded once, physically: a `PackageLine` with a `quantity_accepted`, pointing at a PO
line. Per-demand arrival is **derived** from that, under the rule in
[../shared_demand_sessions.md](../shared_demand_sessions.md) — exact when a line serves one demand,
a session total when it serves several.

The reason is worth restating here, because this is where a future reader will look for the
receiving step: a receipt against a line shared by three demands **cannot** be attributed to one of
them. The units are fungible and nobody decided whose they were. A field asking a receiver to
attribute it would collect a guess and store it as an observation. Deriving instead means the
system says "shared session of 100, 60 arrived" — which is longer, and true.

Receiving now lives in [package_lifecycle.md](package_lifecycle.md).

---

## Classes touched

| Class | Role here |
| :--- | :--- |
| `PurchaseOrderContext` | Entry point for every verb here |
| `PurchaseOrderLineManager` | Line add / edit / cancel / reorder; the audit snapshot |
| `PurchaseOrderDemandLinkManager` | `allocate` · `delink` · `release` |
| `PurchaseOrderDemandLinkValidator` | Part match, duplicate, D28 cap |
| `PurchaseOrderLineValidator` | D58's soft duplicate-part check; the accepted-quantity floor |
| `PurchaseOrderCostManager` | `total_cost` on any line change |
| `PurchaseOrderPropagationHandler` | Axis propagation when allocating to a placed PO |
| `PartDemandContext` | `approve()` for D42; `purchasing_state → null` on line cancel |
| `PartDemandQuantityManager` | `purchased_qty` refresh |
| `PurchaseOrderNarrator` | Machine comments and pre-state snapshots |

---

## Reads this workflow needs

- **`PurchaseOrderFulfillmentStruct`** — the whole PO: lines, allocations, packages, and the four
  quantities (`qty_ordered`, `qty_allocated`, `qty_from_accepted_packages`, `qty_issued`) plus each
  line's attribution mode. **One annotated query**, not one per line.
- **`OpenDemandSearch`** — allocatable demands for a part: not cancelled, not fully allocated,
  within the Buyer's domain access, ordered by `priority` then `needed_by`, excluding demands
  already linked to this PO.

The legacy `PurchaseOrderLineContext` recomputed each of these with its own query, and the model
carried four more as `@property` methods that queried on access — plus a `line` property calling
`get_or_404` on *every* access. A 40-line PO cost well over a hundred queries to render. Annotate
once (D53).
