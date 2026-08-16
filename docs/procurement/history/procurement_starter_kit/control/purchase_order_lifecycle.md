---
okf_version: "0.1"
type: "Process Guide"
title: "Workflow — Purchase Order Lifecycle"
description: "PO status movement and everything it drives: placing an order, closing out shipment, cancelling and releasing allocations, and the event emitter stub."
tags: [process-guide, demand-and-purchasing, control-layer, workflow, purchase-order, state-machine]
context_tier: 2
personas: [backend, business]
---

# Workflow — Purchase Order Lifecycle

A PO's own status is the thing that drives every linked demand's `purchasing_state` and
`shipment_state` (D40). This document is where that propagation is defined.

---

## The status model (D27)

```
Draft → Placed → Partially Received → Received
Draft → Cancelled
Placed → Cancelled
```

`PurchaseOrderStateMachine` holds these transitions as a plain dict — the same discipline as the
demand-side axes, a separate class because the two lifecycles are genuinely independent.

### What each status drives on linked demands (D40)

| PO status | `purchasing_state` | `shipment_state` |
| :--- | :--- | :--- |
| `Draft` | stays `null` | `Request Not Sent` |
| `Placed` | → `Purchased` | → `Request Received by Vendor` |
| `Partially Received` | unchanged | unchanged — packages drive `shipment_state` directly, per package |
| `Received` | unchanged | → `Delivered to Local Receiving Location` (explicit Buyer act) |
| `Cancelled` | → `Cancelled` | unchanged |

`PurchaseOrderPropagationHandler` performs every one of these, calling
`PartDemandStateManager.transition(...)` per linked demand with `is_system_generated = True` and
`actor` set to whoever moved the PO. It never assigns a snapshot column directly.

A demand linked to more than one PO takes the propagation from whichever PO moved. `Purchased`
means money moved for this demand somewhere — it is not a per-PO fact.

---

## `place_purchase_order`

**Business goal.** Send the order to the vendor. This is the money-moved boundary.

**Actor.** Buyer (`buy`), or an Approver holding only `approve` (D2) — an Approver may transition
a PO without being able to create or edit one.

### Steps

1. `PurchaseOrderContext.place(actor)`.
2. Validate: status is `Draft`, and the PO has **at least one line**. Both carried forward from the
   legacy `submit_order`, which got this right.
3. Transition `status → Placed`.
4. `PurchaseOrderPropagationHandler` per linked demand:
   - `purchasing_state → Purchased`. **Gate 1 (D9) is checked here** — a demand still unapproved
     (the Buyer opted out of D42's auto-approve) will not move, and the propagation skips it
     without failing the placement. The PO is placed; that demand's purchasing axis waits for its
     Approver. This is exactly the case the opt-out exists to create.
   - `shipment_state → Request Received by Vendor`, an optimistic default.
5. `DemandCompletionHandler.check()` fires per demand — a demand already `Issued` from stock
   completes here (D43).
6. `PurchaseOrderEventEmitter.emit(PO_STATUS_CHANGED)`; machine comment on the Event.

### Manual shipment advancement

`Production in Progress → Vendor Prepared to Ship → Shipped`, and `Backordered`/`Lost` off
`Shipped`, are advanced **manually** by the Buyer as vendor updates arrive
(`PartDemandContext.advance_shipment(...)`). Nothing computes this middle stretch in this build.

`Backordered` is an everyday occurrence, not an edge case (D44). This whole stretch is very
high-frequency and ideally machine-driven — that is the concrete motivating case for the deferred
integration API (D16), and the reason `PurchaseOrderEventEmitter` exists now.

`Delivered to Depot` and `In Stock` are enum values this build never writes. `In Stock` belongs to
the later Inventory kit; `Delivered to Depot` awaits the package/intake split.

---

## `close_out_shipment`

**Business goal.** Declare receiving effectively complete for this order, whatever the quantities
say.

**Actor.** Buyer.

### Steps

1. `PurchaseOrderContext.mark_received(actor)`.
2. Transition `status → Received`.
3. Propagate `shipment_state → Delivered to Local Receiving Location` on every linked demand.
4. Machine comment on the Event.

### This is explicitly not a quantity match (D29, D40)

`Received` is **never** reached by computing
`sum(quantity_accepted) >= sum(quantity_ordered)` across the PO's packages.
A Buyer can close out an order that received 6 of a purchased 10, because that is what happened and
the remaining 4 are not coming — the vendor discontinued the item, the short shipment was accepted,
the backorder was written off.

Business processes are messy, and this system's job is to let people record what actually happened,
not to dictate what must be true before something can be marked done. `purchased_qty`,
`issued_qty`, and every `quantity_accepted` value are informational inputs to a human judgment,
never a gate on it. The same principle governs `issuance_state → Issued` (D30).

`Partially Received` **is** computed — it follows from any accepted package quantity existing
against the PO at all. Only the terminal close-out is human.

---

## `cancel_purchase_order`

**Business goal.** Call off an order, and free what it had claimed so it can be bought elsewhere.

**Actor.** Buyer. Rare (D44) — design for correctness, not throughput.

### Steps

1. `PurchaseOrderContext.cancel(actor, notes)`.
2. Validate: status is `Draft` or `Placed`. A `Received` PO cannot be cancelled.
3. Transition `status → Cancelled`.
4. **Release every allocation** (see below).
5. Propagate `purchasing_state → Cancelled` on every linked demand.
6. Machine comment on the Event carrying the reason.

   The legacy `cancel_order` appended the cancellation reason onto the PO's `notes` as free text.
   Here it is a comment on the Event, which is what the Event is for.

### Releasing an allocation

For each `PurchaseOrderDemandLink` on the cancelled PO:

- The row goes `is_active = False`. The claim on a cancelled order is no longer a claim.
- **Nothing physical is reversed.** Package lines already accepted against the PO's lines keep
  their `quantity_accepted` — what arrived, arrived, regardless of what happens to the PO
  administratively afterward. The fulfillment struct still reports it.
- The demand's `purchased_qty` recomputes to reflect only what is still validly on order or already
  received — freeing the Buyer to allocate the remainder to a new PO line.

### What is left to the Buyer

Whether the demand's `shipment_state` is then closed out at `Delivered to Local Receiving Location`
(accepting the 6 that arrived as final) or left mid-chain pending a new PO for the remaining 4 is
**the Buyer's call, not automatic either way** (D29, D40).

### The knock-on for demand cancellation

Gate 2 (D10) is what makes this order matter: a demand cannot reach `Cancelled` while a linked PO
is still active. Cancelling the PO here is what unblocks cancelling the demand behind it — the
same order real purchasing follows.

---

## The purchase order event emitter (D48)

**Business goal.** Have a stable, already-wired seam for future outbound transmissions — webhooks,
emails, ERP pushes — so adding one later requires no change to any write path.

**Status: interface defined, not implemented.** No listener ships. This is scaffolding placed
deliberately, and the shape is what matters.

```
app/procurement/presentation_layer/tools/po_events/
  __init__.py
  events.py      ← PurchaseOrderEventType: PO_CREATED, PO_STATUS_CHANGED,
                   PO_LINE_CHANGED, PO_ALLOCATION_CHANGED, PO_RECEIPT_RECORDED
  payload.py     ← PurchaseOrderEventPayload — frozen dataclass:
                   event_type, purchase_order_id, po_number, status,
                   previous_status, actor_id, occurred_at, affected_demand_ids
  emitter.py     ← PurchaseOrderEventEmitter.emit(payload)
  listener.py    ← PurchaseOrderEventListener — abstract base, unimplemented
  registry.py    ← in-process listener registry
```

### The listener interface

`PurchaseOrderEventListener` is an abstract base declaring `handle(payload)` and a
`handles(event_type)` predicate. Concrete listeners register themselves; the emitter dispatches to
every registered listener that claims the type. Zero are registered in this build, so `emit()` is a
no-op that costs one empty loop.

### Rules

- **Emission is fire-and-forget.** A listener raising must never fail the write that emitted it.
  The emitter catches, logs, and continues. A PO does not fail to be placed because an email
  server is down.
- **Emit after commit**, not inside the transaction — a listener must never observe a PO that then
  rolls away.
- **The payload carries IDs and scalars only**, never model instances. A future out-of-process
  listener must be able to consume it unchanged.
- **This is not the deferred integration API** (D16). That is *inbound* — an external system
  pushing status into this app, which needs a payload contract, a status vocabulary, and a
  service-account auth model, none of which exist. This emitter is *outbound* only. They will meet
  eventually; they are not the same seam.

D20 originally specified a Django signal for this. A typed emitter is chosen instead: Django
signals are stringly-typed, hard to enumerate, and hide their subscribers, while an explicit
registry makes "what listens to POs" answerable by reading one file.

---

## Classes touched

| Class | Role here |
| :--- | :--- |
| `PurchaseOrderContext` | `place` · `mark_received` · `cancel` |
| `PurchaseOrderStateMachine` | Legal PO status transitions |
| `PurchaseOrderPropagationHandler` | D40's status → demand-axes propagation |
| `PurchaseOrderDemandLinkManager` | `release` on cancellation |
| `PartDemandStateManager` | Every propagated axis write |
| `PartDemandTransitionStateMachine` | Gate 1 check during propagation |
| `PartDemandQuantityManager` | `purchased_qty` after release |
| `DemandCompletionHandler` | D43 rollup after `purchasing_state` moves |
| `PurchaseOrderNarrator` | Machine-comment text |
| `PurchaseOrderEventEmitter` | D48 emission |
