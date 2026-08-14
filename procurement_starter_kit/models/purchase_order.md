---
okf_version: "0.1"
type: "Reference"
title: "Model — PurchaseOrder"
description: "Schema for the PO header: its own status lifecycle, the procurement.Vendor FK, cost columns, and the single Event row carrying comments and documents."
tags: [reference, demand-and-purchasing, data-model, purchase-order]
context_tier: 2
personas: [backend]
---

# Model — `PurchaseOrder`

`app/procurement/models/purchasing/purchase_order.py`

A commercial order placed with a vendor. A peer of `PartDemand`, never nested under it (D14, R1).
Inherits `AuditFieldsMixin` and `SoftDeleteMixin`.

---

## The vendor decision (D45, reversed 2026-08-09 — `procurement.Vendor` exists)

**There is a `Vendor` model, owned by `app/procurement/`.** D45 originally reused
`parts.PartManufacturer` as the PO's vendor FK, on the reasoning that one registry beats two
nearly-identical ones. That was a mistake: a vendor (e.g. a reseller like Walmart) has no
relationship to the parts it sells, and collapsing the two concepts made the data model lie about
that. `PurchaseOrder.vendor` now FKs to `procurement.Vendor`, decoupled entirely from
`parts.PartManufacturer`. This restores the original questionnaire intent (G4.2).

| Column | Type | Notes |
| :--- | :--- | :--- |
| `vendor` | FK → `procurement.Vendor`, `PROTECT` | Who the order is placed with |
| `vendor_contact` | `CharField(max_length=200, blank=True)` | Free string, filled per-PO by the Buyer |

`Vendor` (`app/procurement/models/purchasing/vendor.py`): `name` (unique), `code` (unique,
optional), `website`, `is_active` — the same field shape `PartManufacturer` has, with zero
relationship to parts or manufacturing. D41's vendor multi-point-of-contact tech debt remains open
and unaffected — `vendor_contact` stays on `PurchaseOrder`, not on `Vendor`.

---

## Columns

### Identity

| Column | Type | Notes |
| :--- | :--- | :--- |
| `po_number` | `CharField(max_length=100, unique=True, db_index=True)` | Human-readable, generated at create. Format `PO-<YYYY-MM-DD>-<8 hex>` — carried forward from the legacy generator, which worked |
| `vendor` | FK → `procurement.Vendor`, `PROTECT` | See above |
| `vendor_contact` | `CharField(blank=True)` | See above |

### Lifecycle (D27)

| Column | Type | Default |
| :--- | :--- | :--- |
| `status` | `TextChoices` — `Draft · Placed · Partially Received · Received · Cancelled` | `Draft` |

```
Draft → Placed → Partially Received → Received
Draft → Cancelled
Placed → Cancelled
```

This is the PO's own lifecycle as a commercial document, and it is the thing that *drives* every
linked demand's `purchasing_state` and `shipment_state` (D40). See
[../control/purchase_order_lifecycle.md](../control/purchase_order_lifecycle.md) for the exact
propagation.

### Dates and money

| Column | Type | Notes |
| :--- | :--- | :--- |
| `order_date` | `DateField` | Defaults to today at create |
| `expected_delivery_date` | `DateField(null=True)` | Header-level estimate; lines may carry their own |
| `shipping_cost` | `DecimalField(null=True)` | |
| `tax_amount` | `DecimalField(null=True)` | |
| `other_amount` | `DecimalField(null=True)` | Other fees, charges, or discounts |
| `total_cost` | `DecimalField(null=True)` | Denormalized: `sum(line totals) + shipping + tax + other`. Recomputed by `PurchaseOrderCostManager` on every line write, never set by a caller |
| `notes` | `TextField(blank=True)` | |

`total_cost` is denormalized for the same reason `purchased_qty` is — a PO list should not sum
lines per row. The legacy app's cancellation path appended the cancellation reason onto `notes` as
free text; this build does not, because the Event comment stream is the right home for that.

### The Event (D17–D19)

| Column | Type | Notes |
| :--- | :--- | :--- |
| `event` | OneToOne → `events.Event`, `PROTECT`, nullable | **One row per PO for its whole lifetime**, created alongside the PO — not one per status change |

`Event` is chosen over `ActivityThread` specifically because it carries the status/comments/
attachments trio this needs, while `ActivityThread` strips the event-specific columns. The Event
provides:

- **The status history** — each `status` change posts a machine comment (D18). There is
  deliberately no `PurchaseOrderUpdate` table.
- **The document library** — POs, quotes, invoices, packing slips ride the Event's existing
  attachment support (D19). No new document infrastructure.
- **Human comments** — Buyers annotating the order.

Use `EventType.INVENTORY` and the existing `InventoryDetail` detail table; no new detail type is
added for purchasing.

`null=True` because the Event is created in the same transaction but the FK is set after the Event
row exists. The factory guarantees a PO never escapes that transaction without one.

---

## Constraints and indexes

- `po_number` unique (above).
- Index on `(status, order_date)` — the Buyer's open-orders queue.
- Index on `vendor` — "everything we've bought from this manufacturer."

---

## Deliberately absent

- **No `major_location` / `storeroom` FKs.** The legacy header carried both. Both are inventory
  concepts and neither table exists in this build. A PO here says what was bought and from whom,
  not where it lands.
- **No approval columns on the PO itself.** Approve-and-buy permissions gate the *actions* (D2);
  who did what is in the Event comment stream.

---

## Updated by D71-D78 (Phase 0 build)

- **"No approval columns on the PO itself" above is superseded.** `approval_state` is now a new
  blank-default axis beside `status` (D76) — Unsubmitted -> Pending Approval -> Approved, with
  Denied/Cancelled reachable from either non-terminal state. `place()` refuses to run unless
  `approval_state == Approved`; D2's clause letting an Approver alone place an order is retired.
- **`vendor_po_id`** — new `CharField(max_length=200, blank=True)`, indexed, not unique — the
  buyer-entered, externally-sourced number a vendor's own paperwork carries, distinct from the
  system-generated `po_number` (D77).
