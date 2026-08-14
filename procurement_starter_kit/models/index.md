---
okf_version: "0.1"
type: "Reference"
title: "Model Layer — Procurement and Inventory"
description: "Index of every table this build creates, which app owns it, and the dependency direction between the procurement app and the inventory stubs."
tags: [reference, procurement, data-model, index]
context_tier: 2
personas: [backend]
---

# Model Layer — Procurement and Inventory

Every table this build creates. Two apps are touched: **`app/procurement/`** (the real
build) and **`app/inventory/`** (one stub table for issuance, D46).

Read [../part_demand_system.md](../part_demand_system.md) for the four-axis state model and
[../purchase_ordering_system.md](../purchase_ordering_system.md) for the PO/allocation mechanics.
The docs in this folder are the schema-level restatement of those two documents, plus the
inventory boundary.

---

## Tables

### `app/procurement/models/`

| Model | Doc | Role |
| :--- | :--- | :--- |
| `PartDemand` | [part_demand.md](part_demand.md) | The hub (G3). Four state axes, three quantity columns, mandatory domain scope |
| `PartDemandUpdate` | [part_demand_update.md](part_demand_update.md) | Append-only journal; the only legal writer of the four snapshot columns |
| `PurchaseOrder` | [purchase_order.md](purchase_order.md) | Commercial order header + own `status` lifecycle + one `events.Event` row |
| `PurchaseOrderLine` | [purchase_order_line.md](purchase_order_line.md) | One line item on a PO |
| `PurchaseOrderDemandLink` | [purchase_order_demand_link.md](purchase_order_demand_link.md) | The demand ↔ PO-line allocation peer join. **No `quantity_received`** — see D55 |
| `Package` | [package.md](package.md) | What the vendor shipped against a PO. Child of a `PurchaseOrder` |
| `PackageLine` | [package.md](package.md) | Child of both a `Package` and a `PurchaseOrderLine`. Carries `quantity_accepted` |

**No `Vendor` table (D45).** A PO's vendor is an FK to the existing `parts.PartManufacturer`
registry; the point of contact is a plain string column on the PO itself.

### `app/inventory/`

| Model | Doc | Role |
| :--- | :--- | :--- |
| `PartIssue` | [part_issue.md](part_issue.md) | Signed quantity handed to a person against a demand |

**Nothing else is built in `inventory`.** No stock levels, no storerooms, no bins, no locations,
no inventory movements, **no intake or put-away**, no serial tracking. Part issuance is the
write seam for the demand system; intake and stocking are the next builds.

---

## Dependency direction — the one rule

```
        parts  ◄─────────────┐
          ▲                  │
          │                  │
  procurement ◄────┴──── inventory
          │                  │
          ▼                  ▼
  administration / events
```

- `inventory` imports `procurement` freely — models, contexts, managers, anything.
- **`procurement` never imports `inventory`** — no FK in that direction, no `try/except ImportError`,
  no reverse relation traversal. The old system's `DemandOriginResolver` pattern violates this and
  is not repeated. **As built there are zero exceptions to this**: packages living in `procurement`
  (D63) removed the only read that would have needed one.
- Both may import `parts`, `events`, and `administration`.

`PurchaseOrder` also carries a mandatory `domain` FK (D61) — the **buying** domain, distinct from
each demand's **receiving** domain. It was not in the original kit, and without it a PO could not be
created at all, because `events.Event` requires a domain and D17 requires every PO to have an Event.

### The write seam from Inventory → Procurement

`PartDemand` carries columns whose *meaning* is owned by Inventory —
`issued_qty`, `issuance_state`, the late stages of `shipment_state`, and
`serial_number_tracking_required`. They exist as denormalized glanceable columns so a demand list
never joins outward.

The cost, stated plainly: **those columns are maintained by their callers, not derived.** A
`PartIssue` row created outside `PartDemandContext.record_issuance(...)` silently drifts
`issued_qty`, and `procurement` has no way to detect it because it cannot look. The manager call
is the only supported write path (D12).
