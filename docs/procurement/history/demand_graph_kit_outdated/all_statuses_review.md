---
okf_version: "0.1"
type: "Kit Document"
title: "All Statuses Review — Complete Reference"
description: "Consolidated reference for every status axis in the system: individual demand statuses (existing), graph-level statuses (new), and imbalance states."
tags: [starter-kit, reference, procurement, statuses]
context_tier: 2
---

# All Statuses Review — Complete Reference

This document maps every status axis across PartDemand and GraphSummary to show how they work together and independently.

---

## Part 1: PartDemand — Four Independent State Axes (Existing)

**PartDemand has FOUR independent, orthogonal dimensions** (D32). A demand can be in any combination of these states — they are not mutually exclusive across axes.

### 1. DemandState — *Is this need real and authorized?* (Pre-PO-allocation only)

Tracks approval workflow. Does **not** track completion — completion is now determined by `linear_status` + `issuance_state`.

| State | Meaning | Typical trigger |
| :--- | :--- | :--- |
| `PROJECTED` | Anticipated need, not yet authorized | Initial creation |
| `REQUIRED` | Need is confirmed and real | Requester formally raises it |
| `APPROVED` | Management approved the need | Approval workflow completed |
| `REJECTED` | Need was denied | Approval workflow rejected it |
| `CANCELLED` | Need was withdrawn | Requester cancelled it |

**Note on `COMPLETED`:** Removed from this axis. A demand is now marked complete by automatic transition (D23) when `linear_status` reaches `DELIVERED` AND `issuance_state` is set (not NOT_ISSUED). Once complete, the demand's state is locked and cannot be edited, even if the parent graph's linear_status changes. This is accepted tech debt.

### 2. PurchasingState — *Has money been authorized to move?*

| State | Meaning | Typical trigger |
| :--- | :--- | :--- |
| `(unset/blank)` | No purchasing decision made yet | Initial creation; awaiting PO approval |
| `APPROVED` | PO can be placed | Finance approved budget/spend authorization |
| `PURCHASED` | Money has moved; PO is placed | PurchaseOrder transitioned to `Placed`+ |
| `DENIED` | Funding was declined | Finance denied the spend request |
| `CANCELLED` | Purchase was cancelled | Buyer or finance cancelled the PO |

### 3. ShipmentState — *Where is the material physically?*

Tracks progression through vendor production and shipping pipeline to local receipt.

| State | Meaning | Typical trigger |
| :--- | :--- | :--- |
| `REQUEST_NOT_SENT` | No PO placed yet | Initial state; purchasing_state is unset/DENIED |
| `REQUEST_RECEIVED_BY_VENDOR` | Vendor acknowledged the order | Vendor confirmed receipt of PO |
| `PRODUCTION_IN_PROGRESS` | Vendor is making the part | Vendor reports production started |
| `VENDOR_PREPARED_TO_SHIP` | Vendor has packed, ready to ship | Vendor reports ready for pickup |
| `SHIPPED` | Material is in transit | Shipment line created; in-route |
| `BACKORDERED` | Vendor cannot fulfill on time | Vendor reports delay/backorder |
| `LOST` | Material was lost in transit | Carrier reports loss; no recovery |
| `DELIVERED_TO_DEPOT` | Arrived at receiving dock | Shipment line accepted at facility |
| `DELIVERED_TO_LOCAL` | Delivered to local consuming location | Transferred from depot to end-user location |
| `IN_STOCK` | Stored for future use | Later Inventory build; not written here |

### 4. IssuanceState — *Has the material been physically handed to the requester?*

Tracks whether the need-raiser actually has the part.

| State | Meaning | Typical trigger |
| :--- | :--- | :--- |
| `NOT_ISSUED` | Material not yet released | In receiving; awaiting inspection/QC |
| `PARTIALLY_ISSUED` | Some of the needed qty handed over | First partial distribution |
| `ISSUED` | Full quantity in requester's hands | Fully distributed to end-user |
| `ISSUED_PENDING_RECONCILIATION` | Issued as loan; expected to return | Borrowing workflow active; tracking out-and-back |
| `ISSUED_RECONCILIATION_REQUIRED` | Issued but inventory system behind | Physical movement happened; books not updated yet |

---

## Part 2: PartDemand — The New Linear Status

**Added as a single "at a glance" overall status**, independent from the four axes above. This is the one status a user sees when they need to know *"where is this in the pipeline?"* without diving into individual axes.

### LinearStatus — *Overall progress through pipeline*

**Derived from:** the parent GraphSummary's `linear_status`. A demand inherits its graph's overall progression.

| State | Condition | Meaning |
| :--- | :--- | :--- |
| `UNLINKED` | `po_qty_allocated == 0` AND `shipment_qty_allocated == 0` on graph | No commitment and no receipt tracking yet |
| `PO_ALLOCATED_NOT_PURCHASED` | `po_qty_allocated > 0` AND `po_qty_purchased == 0` on graph | Spoken for on a draft PO, not yet placed |
| `PO_PURCHASED_NOT_SHIPPED` | `po_qty_purchased > 0` AND `shipment_qty_accepted == 0` on graph | Order placed, awaiting delivery |
| `PARTIALLY_DELIVERED` | `0 < shipment_qty_accepted < demand_qty` on graph | Some arrived, more coming |
| `DELIVERED` | `shipment_qty_accepted >= demand_qty` on graph | All units received |

**Why separate from the four axes?** The axes are about *approval workflow, funding, physical logistics, and distribution*. The linear status is about *fulfillment progress* — a simpler question: *"where in the pipeline?"* A demand can be APPROVED but UNLINKED, or ISSUED but PARTIALLY_DELIVERED (borrowed partial qty before full arrival).

---

## Part 3: GraphSummary — Imbalance States (New)

A graph is an aggregate of multiple PartDemands, PurchaseOrderLines, and ShipmentLines. At the graph level, we track **problems with commitment and delivery**, not approval/authorization.

### POImbalanceState — *PO-side: Are demands fully committed to orders?*

**Independent axis focused on:** demand vs. allocated quantities on purchase orders.

| State | Condition | Meaning | Admin action |
| :--- | :--- | :--- | :--- |
| `DEMAND_EXCEEDS_ALLOCATION` | `demand_qty > po_qty_allocated` | Some demand has no PO commitment yet | Allocate to existing PO or raise new PO |
| `ALLOCATION_EXCEEDS_PURCHASED` | `po_qty_allocated >= demand_qty` AND `po_qty_purchased < demand_qty` | Allocations exist but orders not placed | Place the purchase orders |
| `PO_QUANTITY_EXCEEDS_DEMAND` | `po_qty_purchased > demand_qty` | More ordered than demanded | Raise demand to match, or adjust allocations down |
| `DEMAND_SATISFIED_EXCESS_ALLOCATED` | `po_qty_purchased >= demand_qty` AND `po_qty_allocated > po_qty_purchased` | Demand fully purchased, extra allocated (but allocated does not exceed purchased) | Intentional overstocking; no action needed |
| `BALANCED` | `po_qty_purchased >= demand_qty` AND `po_qty_allocated == po_qty_purchased` | Demand fully purchased, no excess | Ideal state |

**Precedence order:** Evaluated top-to-bottom; first match wins.

### ShipmentImbalanceState — *Shipment-side: Did we receive what we ordered?*

**Independent axis focused on:** what was ordered (po_qty_purchased), what's allocated to shipments (shipment_qty_allocated), and what actually arrived (shipment_qty_accepted).

| State | Condition | Meaning | Admin action |
| :--- | :--- | :--- | :--- |
| `PO_ORDERED_NOT_ALLOCATED_TO_SHIPMENTS` | `po_qty_purchased > shipment_qty_allocated` | Orders exist, shipment lines haven't mapped them yet | Allocate incoming/expected shipments to PO lines |
| `SHIPMENT_ALLOCATION_EXCEEDS_PO` | `shipment_qty_allocated > po_qty_purchased` | More allocated to shipments than we ordered — allocation mismatch | Fix shipment allocations to match POs, or add demand/raise new PO |
| `OVER_DELIVERED` | `shipment_qty_accepted > po_qty_purchased` | More arrived than ordered | Accept surplus, return to vendor, or reconcile |
| `PARTIAL_DELIVERY_RECEIVED` | `0 < shipment_qty_accepted < po_qty_purchased` | Some items arrived, some still in flight | Wait for remainder or follow up |
| `SHIPMENTS_ALLOCATED_AWAITING_DELIVERY` | `shipment_qty_allocated > 0` AND `shipment_qty_accepted == 0` | Shipments tracked but nothing arrived yet | Wait for delivery |
| `BALANCED` | `shipment_qty_accepted >= po_qty_purchased` AND none above | All ordered items received and tracked | Complete |

**Precedence order:** Evaluated top-to-bottom; first match wins.

### LinearStatus on GraphSummary — *Overall progression*

**Answers:** *"Where in the pipeline is this cluster?"* Shared with member demands.

| State | Condition | Meaning |
| :--- | :--- | :--- |
| `UNLINKED` | `po_qty_allocated == 0` AND `shipment_qty_allocated == 0` | Nothing committed, nothing received |
| `PO_ALLOCATED_NOT_PURCHASED` | `po_qty_allocated > 0` AND `po_qty_purchased == 0` | Allocations made, awaiting PO placement |
| `PO_PURCHASED_NOT_SHIPPED` | `po_qty_purchased > 0` AND `shipment_qty_accepted == 0` | Orders placed, awaiting shipment |
| `PARTIALLY_DELIVERED` | `shipment_qty_accepted > 0` AND `shipment_qty_accepted < demand_qty` | Partial arrival; more expected |
| `DELIVERED` | `shipment_qty_accepted >= demand_qty` | All demanded units received |

---

## Part 4: How They Work Together

### At the PartDemand Level

A single demand carries **five statuses** (the four axes PLUS linear):

```
PartDemand
├── demand_state          (approval axis: PROJECTED → REQUIRED → APPROVED)
├── purchasing_state      (funding axis: blank → APPROVED → PURCHASED)
├── shipment_state        (physical logistics: REQUEST_NOT_SENT → SHIPPED → DELIVERED_TO_DEPOT)
├── issuance_state        (hand-off axis: NOT_ISSUED → ISSUED)
└── linear_status         (overall progress: UNLINKED → ... → DELIVERED) [inherited from graph]
```

These are **independent**. Example combinations:
- APPROVED + PURCHASED + SHIPPED + NOT_ISSUED = approved, funded, in transit, not yet handed over
- APPROVED + DENIED + DELIVERED_TO_DEPOT + NOT_ISSUED = approved but funding denied; material arrived anyway (edge case)
- REJECTED + (blank) + REQUEST_NOT_SENT + NOT_ISSUED = need denied; nothing ordered

### At the GraphSummary Level

A graph carries **three statuses** (no axes; graph-level concerns only):

```
GraphSummary
├── linear_status              (progression: where in pipeline?)
├── po_imbalance_state         (commitment: demand vs. allocation on POs)
└── shipment_imbalance_state   (delivery: ordered vs. arrived)
```

These are also **independent**. A graph can be:
- `DELIVERED` (progress complete) BUT `OVER_DELIVERED` (more arrived than ordered) — vendor overship, legitimate
- `PO_PURCHASED_NOT_SHIPPED` (progress mid-pipeline) AND `DEMAND_EXCEEDS_ALLOCATION` (commitment incomplete) — weird but possible if demands were added after POs were placed

Plus two human columns (phase 3):
```
├── resolution_state    (OPEN / RESOLVED / ACCEPTED_AS_IS) — human judgment
└── manually_flagged    (bool) — needs eyes on it
```

### The Relationship

- **PartDemand statuses** describe approval, funding, logistics, and hand-off workflows
- **GraphSummary linear_status** is an *aggregate summary* of member demands' fulfillment progress (inherited by each demand)
- **GraphSummary imbalance states** are *graph-specific concerns* about commitment and delivery gaps — independent of demand approval/funding
- **GraphSummary resolution** is the *human override* layer — marking problems as dealt with

---

## Part 5: Quantitative Inputs for All States

All states are derived from these quantities on GraphSummary:

| Quantity | Source | Meaning |
| :--- | :--- | :--- |
| `demand_qty` | Σ `PartDemand.quantity_requested` on graph members | Total requested units |
| `po_qty_allocated` | Σ `PurchaseOrderDemandLink.quantity_allocated` for member lines | Units spoken for on any PO |
| `po_qty_purchased` | Σ allocations on lines where PO reached `Placed`+ | Units on real, placed orders |
| `shipment_qty_allocated` | Σ allocations on shipment lines | Units on incoming shipments |
| `shipment_qty_accepted` | Σ `ShipmentLine.quantity_accepted` | Units that actually arrived |

All state derivations use **precedence chains** — evaluated top-to-bottom, first match wins — never AND/OR combinations.

---

## Part 6: When Each Status Matters

### PartDemand Axes — Used for:
- **Approvals workflow** (demand_state): routing to approvers, showing approval queue
- **Spend authorization** (purchasing_state): showing what's been budgeted vs. rejected
- **Logistics** (shipment_state): showing where material is in the supply chain
- **Inventory hand-off** (issuance_state): showing who has the part and in what qty

### PartDemand LinearStatus — Used for:
- At-a-glance dashboard/list view: *"Where is this in the pipeline?"*
- Single status a non-procurement user can understand

### GraphSummary Statuses — Used for:
- **Worklist filtering** (linear_status, imbalance states): *"What needs attention and why?"*
- **Buyer view** (po_imbalance_state): *"Which demands lack PO coverage?"*
- **Shipment view** (shipment_imbalance_state): *"Which orders have delivery gaps?"*
- **Resolution tracking** (resolution_state, manually_flagged): *"What has been dealt with?"*

---

## Summary: The Status Hierarchy

```
PartDemand (the need)
  └─ has 5 statuses: 4 axes + 1 linear (inherited from graph)

GraphSummary (the cluster)
  └─ has 3 statuses: linear (top-level progress) + 2 imbalance axes
  └─ plus 2 human columns: resolution + flagging
  └─ synthesized from: demand_qty, po_qty_allocated, po_qty_purchased, 
                       shipment_qty_allocated, shipment_qty_accepted
```

No redundancy. Each status answers a different question. No status writes another.
