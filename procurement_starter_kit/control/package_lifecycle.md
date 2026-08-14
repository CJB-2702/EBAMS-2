---
okf_version: "0.1"
type: "Process Guide"
title: "Workflow — Package Lifecycle and Line Splitting"
description: "Creating a package against a PO with copied line links, advancing shipment status, inspecting and accepting quantities, and the line-splitting wizard that reassigns arriving lines across purchase orders."
tags: [process-guide, demand-and-purchasing, inventory, control-layer, workflow, packages]
context_tier: 2
personas: [backend, business]
---

# Workflow — Package Lifecycle and Line Splitting

Packages are the shipment-tracking system: what the vendor actually shipped against an order, and
what survived inspection. Very high frequency, and ideally machine-fed rather than typed (D44).

Schema in [../models/package.md](../models/package.md). Attribution rules in
[../shared_demand_sessions.md](../shared_demand_sessions.md).

**Intake stays out of scope.** This workflow ends at `quantity_accepted`. Putting accepted material
into stock is the later Inventory build.

**Pending revision — D68.** Every "machine comment on the PO's Event" below is being retargeted to
**the package's own Event** once `Package.event` is added (`decisions.md` D68) — packages get their
own domain-scoped Event for the same reason POs did (D17). The splitting wizard's "every affected
PO's Event" step is the one exception that stays PO-side, in addition to a comment on the package's
own Event. Not yet implemented; noted here so this document isn't read as still-current once that
lands.

---

## `create_package`

**Business goal.** Record that a shipment exists against an order, so its progress is trackable
before it arrives.

**Actor.** Buyer, or receiving staff.

### Steps

1. `PackageFactory.create(purchase_order_id, actor, ...)` — the package is created **against a
   purchase order**, never free-floating. That PO is its primary identity.
2. Header fields: `tracking_number`, `carrier`, `shipped_date`, `expected_arrival_date`.
3. Add lines. For each: `part`, `quantity`.
4. **Each line copies its PO link from the header.** `PackageLineManager` resolves the header PO's
   line for that part and sets `purchase_order_line` automatically.
   - Exactly one active PO line for that part → assigned. This is the normal case, and it is why
     one-line-per-part-per-PO matters (below).
   - No matching line → `purchase_order_line = null`. Recorded, not refused. The splitting wizard
     resolves it later.
5. `PackageStatusManager` refreshes `mixed_po_assignments` and propagates `shipment_state`.
6. Machine comment on the PO's Event.

### The copy is a default, not a binding

Copying the header's PO link is what makes the common case zero-effort: a box from one vendor
against one order needs no per-line assignment at all. Lines are reassignable afterward, and
reassignment is expected — see the wizard.

### Why one active line per part per PO matters here

The copy step resolves *part → PO line*. With two active lines for the same part on one PO, that
resolution is ambiguous and the line lands unassigned, forcing manual work on every arrival.

Per the standing rule, that cannot happen — a PO carries at most one **active** line per part
(scoped to non-deleted lines, since cancel-and-replace legitimately leaves a deleted line behind).
Enforced in the control layer as a **soft UI error**, not a database constraint: the Buyer is told
the part is already on the order and pointed at the existing line. Nothing hard-blocks, and a
duplicate that gets through leaves its package lines unassigned rather than mis-assigned.

---

## `advance_package_status`

**Business goal.** Track where the shipment is, and move the demands behind it without anyone
touching a demand.

**Actor.** Receiving staff, Buyer — or, ideally, a machine feed (D16's motivating case).

### Steps

1. `PackageContext.advance(to_status, actor)`.
2. `PackageStateMachine` checks the transition (`Awaiting Shipment → Shipped → Delivered to Depot →
   Delivered to Local Receiving Location → Accepted`, plus `Shipped → Lost`). Fails open per D13.
3. Propagate to `PartDemand.shipment_state` for every demand behind the package's lines:

   | `Package.status` | `shipment_state` |
   | :--- | :--- |
   | `Awaiting Shipment` | `Vendor Prepared to Ship` |
   | `Shipped` | `Shipped` |
   | `Delivered to Depot` | `Delivered to Depot` |
   | `Delivered to Local Receiving Location` | `Delivered to Local Receiving Location` |
   | `Lost` | `Lost` |

4. Machine comment on the PO's Event.

The demand path is `package line → purchase_order_line → PurchaseOrderDemandLink → PartDemand`, and
every write goes through `PartDemandStateManager.transition(...)` with
`is_system_generated = True` — never a direct column assignment.

### A demand behind several packages

Backordered items ship in pieces, so a demand's line can have package lines in several packages at
different statuses. The demand takes the **least advanced** status among them: a demand with one
box delivered and one still in transit has not been delivered. Taking the most advanced would
report the demand as complete while material is still moving.

---

## `inspect_and_accept_package_line`

**Business goal.** Record what actually survived the trip, separately from what the packing slip
claimed.

**Actor.** Receiving staff.

### Steps

1. `PackageLineManager.accept(line_id, quantity_accepted, actor, rejection_notes="")`.
2. `quantity_accepted` may be less than, equal to, or **greater than** `quantity` — vendors
   over-ship, and the honest record says so. Only `>= 0` is enforced.
3. Refresh the package's rollup.
4. Machine comment on the PO's Event when accepted differs from shipped.

`quantity_accepted` is `null` until this runs, and `null` contributes nothing to
`qty_from_accepted_packages`. An uninspected box has accepted nothing.

### This does not touch `PurchaseOrderDemandLink`

There is no per-demand receipt attribution step, and there is no `quantity_received` column on the
allocation row any more. Per-demand arrival is **derived** — see below.

---

## The line-splitting wizard

**Business goal.** Resolve an arriving line that does not map cleanly to one PO line: it covers
several orders, it covers several lines, or it matches nothing.

**Actor.** Receiving staff.

**Frequency.** Common enough to deserve a wizard — one box holding items from several orders to the
same vendor is routine, which is exactly why the copied link is only a default.

### Steps

1. Open a package line in the wizard.
2. **Search for PO lines.** The wizard's core is a PO lookup: open POs for the same vendor,
   filtered to the arriving part, showing each candidate line's `qty_ordered`,
   `qty_from_accepted_packages` so far, and outstanding balance. This search is the reason the
   wizard exists — finding the right line across a vendor's open orders is the hard part, not the
   arithmetic.
3. **Split.** Assign a quantity to a chosen PO line. `PackageLineSplitHandler`:
   - Creates a new `PackageLine` with that quantity, pointing at the chosen PO line, `split_from`
     set to the original.
   - Reduces the original's `quantity` by the split amount.
   - If the original reaches zero, soft-deletes it.
4. Repeat until the arriving quantity is fully assigned. A remainder may legitimately be left
   unassigned.
5. `PackageStatusManager` refreshes `mixed_po_assignments` — a split onto another PO's line is
   precisely what sets it.
6. Machine comment on **every** affected PO's Event, not just the header's.

### Splitting instead of a link table

Each row's `quantity` **is** the physical fact, and the split rows sum to the original shipment by
construction. A link table with quantities creates two numbers for one fact and a reconciliation
problem between them — which the legacy design carried as
`ArrivalLine.quantity_available_for_linking`, a column that exists only to describe a discrepancy
the schema made possible.

`split_from` keeps the original line item reconstructible, so the audit trail survives the split.

### Reassignment without splitting

Pointing a whole line at a different PO line is the degenerate case — same handler, full quantity,
no new row.

---

## `derive_demand_arrival`

**Business goal.** Answer *"how much of my demand arrived"* — truthfully, including when the
truthful answer is "that question does not have an answer for this demand."

**Actor.** None. Derived, read-only.

### The rule

Per PO line, by its count of active `PurchaseOrderDemandLink` rows:

- **Exactly one** → attributable. That demand's arrived quantity is the sum of
  `quantity_accepted` across package lines pointing at the line.
- **Two or more** → a **shared demand session**. Report `session_allocated`, `session_arrived`, and
  the member list. **Never a per-demand figure.**
- **Zero** → unlinked. Proactive stock; the arrival is real and no demand claims it.

`PurchaseOrderFulfillmentStruct` computes this and exposes the per-demand field **only** on the
attributable branch — absent, not null, in the shared case, so a caller cannot default it to zero
and report a lie.

Full reasoning, including why proportional splitting is refused and what a Buyer can do about it,
is in [../shared_demand_sessions.md](../shared_demand_sessions.md).

---

## Classes touched

| Class | Role |
| :--- | :--- |
| `PackageFactory` | `create` — header + lines + copied PO links, one transaction |
| `PackageContext` | Entry point around one `package_id` |
| `PackageLineManager` | Line add / edit / accept / reassign; maintains `mixed_po_assignments` |
| `PackageLineSplitHandler` | The split operation |
| `PackageStatusManager` | Status advance + `shipment_state` propagation |
| `PackageStateMachine` | `guards/package_state_guard.py` — legal status transitions |
| `PackageLineValidator` | `guards/package_line_guard.py` — quantities, part match on assignment |
| `PurchaseOrderLineSearch` | The wizard's PO lookup (`presentation_layer/search/`) |
| `PurchaseOrderFulfillmentStruct` | The derived rollup — lives in `procurement`, reads here |
| `PartDemandStateManager` | Every propagated `shipment_state` write |
| `PurchaseOrderNarrator` | Machine comments on affected Events |
