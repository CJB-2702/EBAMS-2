---
okf_version: "0.1"
type: "Kit Document"
title: "Status Reference — every axis in one place"
description: "All nine status enums across PartDemand, PurchaseOrder, Shipment, and GraphSummary, verified against the code, with what each one answers and who writes it."
tags: [starter-kit, procurement, statuses, reference, okf]
context_tier: 2
---

# Status Reference

Nine status enums live in this application. This document is the consolidated view,
**verified against `app/procurement/models/*/enums.py` and the guard dicts**.

Where it differs from the older `all_statuses_review.md`, this document is the correct
one — the notable corrections are called out at the bottom.

---

## The map

```
PartDemand      4 axes  + 1 inherited label
PurchaseOrder   2 axes
Shipment        1 axis
GraphSummary    3 derived axes + 1 error key + 1 legacy label + 3 human columns
```

**No status writes another status.** Everything cross-axis happens through explicit
propagation handlers, and every such write is journaled as system-generated.

---

## PartDemand

### `demand_state` — is the need real and authorized?

`projected` → `required` → `approved` → `completed`, with `rejected` (loops back to
`required`) and `cancelled`.

Written by: the requester/approver via `PartDemandContext`; `completed` is written only
by `DemandCompletionHandler`.

### `purchasing_state` — has money been cleared to move?

`""` (unset, the default and a **real value**) → `approved` → `purchased`, plus `denied`
and `cancelled`. All non-unset values can return to unset; `purchased → ""` exists only
for line cancellation.

Written by: mostly `PurchaseOrderPropagationHandler`, occasionally a human.

### `shipment_state` — where is the material?

`request_not_sent` → `request_received_by_vendor` → `production_in_progress` →
`vendor_prepared_to_ship` → `shipped` → `delivered_to_depot` → `delivered_to_local` →
`in_stock`, plus `backordered` and `lost`, both of which re-enter the chain.

`in_stock` is never written by this application — it is a surface for Inventory.

Written by: `PurchaseOrderPropagationHandler` (placement, close-out),
`ShipmentStatusManager` (arrival), and humans for the middle vendor stretch.

### `issuance_state` — has the requester got it?

`not_issued` → `partially_issued` → `issued`, plus `issued_pending_reconciliation` (an
active loan, expected back) and `issued_reconciliation_required` (a physical movement the
books have not caught up with). Both resolve back to `issued` or `partially_issued`.

Written by: `PartDemandIssuanceManager`, driven from `app/inventory/`.

### `linear_status` — the glanceable label

Not an axis. A copy of the parent graph's `linear_status`, so a demand list can show
pipeline position without a join. See the graph section below.

---

## PurchaseOrder

### `status`

`draft` → `placed` → `partially_received` → `received`; `cancelled` reachable from draft,
placed, and partially received but **not** from received.

`partially_received` is computed from any accepted shipment quantity existing; only the
terminal close-out is a human act, and it is never a quantity match.

### `approval_state`

`""` (unsubmitted) → `pending_approval` → `approved`; `denied` (resubmittable) and
`cancelled` reachable from either non-terminal state. `approved` is terminal on this axis
— an approved order is cancelled through `status`.

---

## Shipment

### `status`

`awaiting_shipment` → `shipped` → `delivered_to_depot` → `delivered_to_local` →
`accepted`, plus `backordered` and `lost` (both re-enter at `shipped`) and `cancelled`.

`accepted` means inspected and intact. It does **not** mean stocked.

---

## GraphSummary

### `linear_status` — where in the pipeline? (precedence, first match wins)

| Value | Condition |
| :--- | :--- |
| `unlinked` | `po_qty_allocated == 0` and `shipment_qty_allocated == 0` |
| `po_allocated_not_purchased` | `po_qty_allocated > 0` and `po_qty_purchased == 0` |
| `po_purchased_not_shipped` | `po_qty_purchased > 0` and `shipment_qty_accepted == 0` |
| `partially_delivered` | `0 < shipment_qty_accepted < demand_qty` |
| `delivered` | `shipment_qty_accepted >= demand_qty` |

### `po_imbalance_state` — is demand committed to orders?

`demand_exceeds_allocation` → `allocation_exceeds_purchased` → `po_quantity_exceeds_demand`
→ `demand_satisfied_excess_allocated` → `balanced`. Measured on **allocation**, not
ordered quantity, for the first two.

### `shipment_imbalance_state` — did we get what we ordered?

`po_ordered_not_allocated_to_shipments` → `shipment_allocation_exceeds_po` →
`over_delivered` → `partial_delivery_received` → `shipments_allocated_awaiting_delivery`
→ `balanced`. Measured against **`po_qty_purchased`**, never `demand_qty`.

### `error_code` — only where axes contradict

`DELIVERED_WITH_UNCOMMITTED_DEMAND`, `DELIVERY_EXCEEDS_PURCHASE_ORDER`,
`SHIPMENT_ALLOCATION_EXCEEDS_ORDER`, or `""`.

### `status` — legacy

`balanced` / `awaiting_purchase` / `awaiting_shipment` / `awaiting_acceptance`. Superseded
by `linear_status`. Do not add values.

### The human columns

`resolution_state` (`open` / `resolved` / `accepted_as_is`), `manually_flagged`,
`priority`. Written **only** by `GraphResolutionManager`; cleared to `open` on merge and
split.

---

## Non-status enums worth knowing

| Enum | Values |
| :--- | :--- |
| `DemandPriority` | low / medium / high / critical — intrinsic to the need |
| `DemandSourceModule` | maintenance / dispatching / general — display convenience, **never a source of truth for origin** |
| `DemandDimension` | demand / purchasing / shipment / issuance — which axis a journal row describes |
| `PriceSourceType` | part_create / quote / manual / ordered / invoiced / catalog |
| `PriceConfidence` | quoted / p10 / p50 / p100 / unknown |
| `UnitCostSource` | quoted / last_paid / last_ordered / estimated / unknown |

---

## Corrections against the older `all_statuses_review.md`

That document is broadly accurate on the demand axes and the graph imbalance axes. Four
things it does not say, or says differently:

1. **`GraphSummaryStatus` is not mentioned at all.** It still exists as `status`, it is
   still written by `recalculate()`, and it is still read by the graph detail template and
   the narrators. It is legacy but live.
2. **`error_code` is not mentioned.** It is a real column with three keys.
3. **`priority` on GraphSummary is not mentioned.** The human-judgment set is *three*
   columns, not two.
4. **`DemandState.COMPLETED` is still a value on the axis**, not removed — what changed is
   that nothing transitions into it by hand. The older document's phrasing ("removed from
   this axis") reads as if the enum value is gone; it is not.

Everything else in that file matches the code, including the four-axis independence
argument, the precedence chains, and the quantity inputs.
