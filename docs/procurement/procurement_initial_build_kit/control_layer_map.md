---
okf_version: "0.1"
type: "Kit Document"
title: "Control Layer Map — Procurement"
description: "Every control-layer class in the procurement app, what it owns, and the sole-writer rules that keep the derived columns honest."
tags: [starter-kit, procurement, control-layer, architecture, okf]
context_tier: 2
personas: [backend]
---

# Control Layer Map

`app/procurement/control_layer/` — every class, grouped by suffix, with what it owns.

---

## Sole-writer rules

These are the invariants the whole layer is arranged around. Breaking one produces silent
data corruption rather than an error.

| Column(s) | Sole writer |
| :--- | :--- |
| `PartDemand`'s four axis columns **and** their journal rows | `PartDemandStateManager` (both, in one transaction, always) |
| `PartDemand.purchased_qty`, `.issued_qty`, `.quantity_requested` | `PartDemandQuantityManager` |
| `PurchaseOrder.total_cost` | `PurchaseOrderCostManager` |
| `graph_id` on all three member models, **and every derived `GraphSummary` column** | `GraphSummaryManager` |
| `GraphSummary.resolution_state`, `.manually_flagged`, `.priority` | `GraphResolutionManager` — and `recalculate()` must never touch them |
| `Shipment.mixed_po_assignments` | `ShipmentStatusManager` |

---

## Contexts — the public entry points

One per aggregate root. Everything a caller outside the control layer should need.

| Class | Owns |
| :--- | :--- |
| `PartDemandContext(demand_id)` | approve / reject / resubmit / mark_required / cancel, the purchasing and shipment and issuance verbs, `record_issuance` (the inward seam from Inventory), field updates, quantities, delete |
| `PurchaseOrderContext(po_id)` | place / mark_partially_received / mark_received / cancel, submit_for_approval / approve / deny, line add / edit / cancel, allocate / delink, cost recompute |
| `ShipmentContext(shipment_id)` | advance, update_header, add / delete / accept line, assign_line, release_allocation, attach_purchase_order, delete |

---

## Guards

Validators refuse or warn; StateMachines decide legality; Policies decide business
outcomes.

| Class | Type | Owns |
| :--- | :--- | :--- |
| `PartDemandTransitionStateMachine` | StateMachine | the four transition dicts and the three cross-axis gates; **fails open** on undecidable |
| `PartDemandDeletionPolicy` | Policy | hard-delete-while-untouched vs soft delete. Checks only this app's tables |
| `PurchaseOrderStateMachine` | StateMachine | PO `status` transitions |
| `PurchaseOrderApprovalStateMachine` | StateMachine | PO `approval_state` transitions |
| `PurchaseOrderLineValidator` | Validator | soft duplicate-part warning; **hard** accepted-quantity floor; new-line sanity |
| `PurchaseOrderDemandLinkValidator` | Validator | per-demand cap (raises the choice-carrying `AllocationCapExceeded`), part match, one-row-per-pairing |
| `ShipmentStateMachine` | StateMachine | shipment `status`; **fails open** |
| `ShipmentLineValidator` | Validator | quantity sanity, part match, and the **hard** allocation cap |
| `PartPriceObservationValidator` | Validator | soft duplicate-observation warning |
| `VendorValidator` | Validator | vendor uniqueness |

### Errors

| Exception | Meaning |
| :--- | :--- |
| `ProcurementValidationError` | an input or invariant check failed at a boundary |
| `TransitionRefused` | a gate refused, and the message **names the next action** — never a generic failure |
| `AllocationCapExceeded` | not a failure: a choice the caller must present (raise the request, or leave the excess unallocated), carrying the numbers needed to present it |

---

## Managers — the writers

| Class | Owns |
| :--- | :--- |
| `PartDemandStateManager` | the only axis+journal writer; `initialize()` writes the four opening rows |
| `PartDemandQuantityManager` | `purchased_qty` (recomputed), `issued_qty` (applied), `quantity_requested` (raised) |
| `PartDemandIssuanceManager` | the inward seam: applies a caller-supplied net quantity and moves the issuance axis |
| `PurchaseOrderLineManager` | line add / edit / cancel / reorder + the audit snapshot |
| `PurchaseOrderDemandLinkManager` | allocate / de-link / release, and the graph merge and split calls |
| `PurchaseOrderCostManager` | `total_cost`, in one query |
| `ShipmentLineManager` | line add / accept, PO-line allocate / deallocate, part→line resolution |
| `ShipmentStatusManager` | status advance, shipment_state propagation (least-advanced rule), the drift flag |
| `GraphSummaryManager` | node-init, merge, split, recalculate. No `commit` parameter anywhere, deliberately |
| `GraphResolutionManager` | the three human columns, and nothing else |
| `VendorManager` | vendor create/update |

---

## Handlers — cross-entity reactions

| Class | Fires when | Does |
| :--- | :--- | :--- |
| `DemandCompletionHandler` | after any write to purchasing or issuance state | auto-completes the demand when money moved **and** it reached the requester |
| `PurchaseOrderPropagationHandler` | PO placed / received / cancelled | moves every linked demand's axes; **reports skips, never swallows them** |
| `BasicShipmentManagerSubmitHandler` | the buyer submits the planning board | validates the whole session draft, then commits once, all or nothing |

---

## Factories

| Class | Creates |
| :--- | :--- |
| `PartDemandFactory` | the demand, its four journal rows, and its single-member graph. **The caller owns domain assignment and its own link row** — this factory does not know what a link row is |
| `PurchaseOrderFactory` | a PO with header and lines |
| `ShipmentFactory` | a shipment, its Event thread, its lines (with copied or explicit allocations), the drift flag, and propagation |
| `PartPriceObservationFactory` / `...BulkFactory` | one / many observations |

---

## Domain structs — read shapes

| Class | Shape |
| :--- | :--- |
| `PartDemandStruct`, `PartDemandDetailStruct`, `DemandAxisSnapshot`, `DemandJournalRow`, `DemandAllocationSlice`, `PurchasingCoverageLink` | the demand read family. `PartDemandDetailStruct` **extends** rather than duplicating, so detail and list read the same fields |
| `PurchaseOrderStruct`, `PurchaseOrderLineStruct`, `AllocationSlice` | order reads |
| `PurchaseOrderFulfillmentStruct` + `UnlinkedLineFulfillment` / `AttributableLineFulfillment` / `SharedSessionLineFulfillment` / `ShipmentRollup` | fulfillment, **typed by how answerable the question is**: unlinked, exactly-one-demand (a real per-demand number), or a shared session (deliberately carrying *no* per-demand arrival field) |
| `ShipmentDetailStruct`, `ShipmentLineSlice`, `ShipmentLineAllocationSlice`, `LineAttribution`, `ShipmentPlanningLine` | shipment reads. `LineAttribution` uses one class with a mode discriminator because a Django template cannot do an `isinstance` check |
| `PartPriceFactsStruct`, `PriceFact` | the two price facts |
| `MermaidSwimlaneBuilder` | the cached graph diagram source |
| `arrival_allocation` (module, not a class) | **the one place a quantity is ever divided** |

---

## Narrators, policies, adaptors

| Class | Owns |
| :--- | :--- |
| `PartDemandNarrator` | the sentence written into every journal row |
| `PurchaseOrderNarrator`, `ShipmentNarrator` | Event-thread messages and machine audit comments |
| `PartPricePolicy` | the two price facts, resolved in **three bulk queries**, never per part |
| `PartDemandCreateAdaptor`, `PurchaseOrderDraftAdaptor`, `PartPriceGridAdaptor`, `VendorCreateAdaptor` | POST/session → validated input structs. The draft adaptors are what let the wizards keep everything out of the database until submit |

---

## Presentation-layer support

| Module | Owns |
| :--- | :--- |
| `tools/procurement_access.py` | the permission vocabulary (`buy`, `purchase_approve`, `request`, `demand_manage`, `receive`, `price_establish`), the `require_*` gates, and `accessible_domain_ids` / `is_in_domain` |
| `tools/po_wizard_draft.py`, `shipment_wizard_draft.py`, `basic_shipment_session.py`, `price_grid_draft.py` | session-backed drafts — the reason nothing touches the database mid-wizard |
| `tools/po_events/` | emitter / listener / payload / registry for PO status events |
| `tools/recent_part_creations.py` | breadcrumbs scheduled with `transaction.on_commit`, so a rolled-back part creation leaves none |
| `search/*.py` | the searchable list queries, each taking `domain_ids` explicitly |
| `metrics/*.py` | the hub's stat aggregates |

---

## Tests

`app/procurement/tests/` covers the graph manager (including the identity/status columns
and the recalculate-must-not-touch rule), a persistence smoke test creating one object per
concept through its real class, price observations and the placed-PO observation write,
shipment allocation, the shipment create wizard, the shipment edit page, and the
`recent_part_creations` rollback boundary.
