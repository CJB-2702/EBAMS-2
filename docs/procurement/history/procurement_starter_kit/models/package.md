---
okf_version: "0.1"
type: "Reference"
title: "Model — Package and PackageLine"
description: "Schema for the shipment-tracking system: a package as a child of a purchase order, package lines as children of PO lines, the copied-PO-link drift flag, and acceptance quantities."
tags: [reference, procurement, data-model, packages]
context_tier: 2
personas: [backend]
---

# Model — `Package` and `PackageLine`

`app/procurement/models/packages/`

What the vendor actually shipped against a purchase order. In scope for this build (revises D47's
"inert stub" scoping) — packages are the shipment-tracking system, and the thing that drives
`shipment_state`.

**Intake remains out of scope.** A package says *what arrived*. Intake — accepting into stock,
put-away, bin assignment, stock levels — is still the later Inventory build. The line between them
is exactly where `PackageLine.quantity_accepted` stops.

---

## Placement — decided

These tables are built in `app/procurement/` where they belong. A package in transit from a vendor
is **pre-possession**: it is the purchase order's own story of what the vendor did about it.

The shape confirms it: a package is a child of a PO, a package line is a child of a PO line —
every FK points into procurement, and nothing about a package references a storeroom, a bin, or a
stock level. Intake is the moment possession transfers, and intake stays in `app/inventory/`.

This placement also **eliminates the cross-app read** that would have been needed if packages sat
in inventory — the procurement app can now construct fulfillment reports without exceptions.

---

## `Package`

`app/procurement/models/packages/package.py` — inherits `AuditFieldsMixin`, `SoftDeleteMixin`.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `purchase_order` | FK → `PurchaseOrder`, `PROTECT`, `related_name="packages"` | The **primary** PO. One PO has many packages |
| `package_number` | `CharField(unique=True, db_index=True)` | Generated at create |
| `tracking_number` | `CharField(blank=True)` | |
| `carrier` | `CharField(blank=True)` | |
| `status` | `TextChoices` — see below | Shipment tracking |
| `mixed_po_assignments` | `BooleanField(default=False)` | Drift flag — see below |
| `shipped_date` | `DateField(null=True)` | |
| `expected_arrival_date` | `DateField(null=True)` | |
| `received_date` | `DateField(null=True)` | When it physically showed up |
| `notes` | `TextField(blank=True)` | |

### `Package.status`

```
Awaiting Shipment → Shipped → Delivered to Depot →
Delivered to Local Receiving Location → Accepted

Shipped → Lost
```

This is what drives `PartDemand.shipment_state` on the demands behind the package's lines — the
role D35/D40 always intended for it. `Accepted` is the package-level counterpart of the Buyer's
close-out; it does **not** mean stocked, which is intake's word.

### `mixed_po_assignments` — the drift flag

A package's lines **copy** their PO link from the header at creation (below). Lines can then be
reassigned to a PO line on a *different* PO — which is legitimate: one physical box routinely
contains items from several orders to the same vendor.

`mixed_po_assignments` is set `True` whenever any line's `purchase_order_line.purchase_order`
differs from the header's `purchase_order`. It is maintained by `PackageLineManager` on every line
write, never set by a caller.

It is a **flag, not a constraint.** Nothing is blocked. It exists so the condition is visible and
queryable rather than discovered by someone puzzling over why a PO's package rollup does not add
up. The header PO stays the package's primary identity regardless.

### Indexes

- `(purchase_order, status)` — the PO's package list.
- `mixed_po_assignments` (partial, `WHERE mixed_po_assignments`) — the drift review queue.

### `event` — pending, see D68

`Package` is decided to get its own `event` column: `OneToOne → events.Event, PROTECT, nullable` —
the same shape as `PurchaseOrder.event` (see `purchase_order.md` §"The Event"). Domain is copied
from `purchase_order.domain` at creation; `Package` does not get its own `domain` column. **Not yet
added to this table** — `decisions.md` D68 records the decision and reasoning; this doc needs a
follow-up pass to add the column once implemented.

### `has_splits` — pending, see D69

A second pending column: `BooleanField(default=False)`, same maintenance shape as
`mixed_po_assignments` above — `PackageLineSplitHandler` sets it `True` the moment any of this
package's lines is split (a sibling row created with `split_from` set). Drives the bulk
drag-and-drop package manager's lock rule alongside delivery status (`decisions.md` D69). **Not yet
added to this table.**

---

## `PackageLine`

`app/procurement/models/packages/package_line.py` — inherits `AuditFieldsMixin`, `SoftDeleteMixin`.
(An earlier draft gave this an `app/inventory/` path, contradicting the placement section above;
corrected per D63.)

A package line is a child of **two** parents: the package it physically arrived in, and the PO line
it fulfills.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `package` | FK → `Package`, `CASCADE`, `related_name="lines"` | |
| `purchase_order_line` | FK → `PurchaseOrderLine`, `PROTECT`, `related_name="package_lines"`, **nullable** | Copied from the header's PO at create; reassignable |
| `part` | FK → `parts.Part`, `PROTECT` | What is in the box |
| `quantity` | `DecimalField` | As shipped / as claimed by the packing slip |
| `quantity_accepted` | `DecimalField(null=True)` | As accepted after inspection. `null` until inspected |
| `rejection_notes` | `TextField(blank=True)` | Why the difference, when there is one |
| `split_from` | FK → `self`, `SET_NULL`, nullable, `related_name="splits"` | Set on lines produced by the splitting wizard |

- `CheckConstraint`: `quantity > 0`.
- `CheckConstraint`: `quantity_accepted IS NULL OR quantity_accepted >= 0`.
- Index on `(purchase_order_line, package)` — the fulfillment struct's key read.
- Index on `(package, part)`.

### Acceptance is a quantity, not a boolean

`quantity` is what the vendor says is in the box; `quantity_accepted` is what survived inspection.
Partial acceptance — 8 good, 2 damaged — is the normal outcome of a damaged shipment, and a boolean
would force someone to record a whole shipment as accepted or rejected when neither is true.

`quantity_accepted` is `null` until someone inspects, which is meaningfully different from `0`
(inspected, all rejected). **Only `quantity_accepted` counts toward
`qty_from_accepted_packages`** — an uninspected line contributes nothing, because nothing has been
accepted yet.

*Confirmed in the build: acceptance is per package line rather than per package. Partial acceptance
within a single line is the reason — `PackageLineManager.accept()` takes one line.*

### `purchase_order_line` is nullable

A line can arrive that matches nothing on any PO — a vendor substitution, a wrong shipment, a
bonus item. It is recorded with `purchase_order_line = null` and surfaced by the fulfillment struct
as an unassigned line, rather than being dropped or forced onto an ill-fitting PO line. The
splitting wizard is how someone resolves it.

### `split_from`

The splitting wizard divides one arriving line across several PO lines by creating sibling rows,
each pointing at its own PO line. `split_from` preserves the lineage so the original physical line
item remains reconstructible. See
[../control/package_lifecycle.md](../control/package_lifecycle.md).

---

## What replaced the link table

An earlier draft of this design used a `PurchaseOrderPackageLink` many-to-many between package
lines and PO lines, mirroring the legacy `ArrivalPurchaseOrderLink`. It is gone.

A package line points at exactly **one** PO line, by FK. A physical line item spanning several PO
lines is handled by **splitting it into several rows**, not by a link table with quantities on it.

This is better for a specific reason: with a link table, an arriving line's quantity and the sum of
its links can disagree, so there are two numbers for one physical fact and a reconciliation problem
between them. With splitting, each row's `quantity` **is** the fact, and the rows sum to the
shipment by construction. The legacy design carried exactly that reconciliation problem in
`ArrivalLine.quantity_available_for_linking`.

The cost is that splitting is an explicit user action rather than an incremental one — which is why
it gets a wizard.

---

## Deliberately absent

- **No storeroom, location, or bin FKs.** Those are intake's, and intake is not built.
- **No `condition` enum.** `quantity_accepted` plus `rejection_notes` covers what a receiver needs
  to record; a `Good/Damaged/Mixed` enum on a line that can be partially accepted is redundant.
- **No inventory movement.** Accepting a package line does not create stock. Nothing in this build
  tracks stock.
- **No serial capture.** `PartDemand.serial_number_tracking_required` is declared and unread
  (D38); the mechanics belong to intake.

---

## Updated by D71-D78 (Phase 0 build)

- **`purchase_order` is now nullable** (D74) — reverses this document's earlier "never
  free-floating" framing. A package can be received before its PO exists via the reactive
  `packages/receive/` entry point; `PackageContext.attach_purchase_order()` links one on later.
- **`domain` is a new required `ForeignKey(administration.Domain)`** (D74) — the fence a PO-less
  package still needs. Copied from the PO's domain when one is supplied, chosen by the receiver
  otherwise.
- **`event` is a new `OneToOneField(events.Event, PROTECT, null=True)`** (D72) — a package finally
  gets its own Event/comment history instead of borrowing the header PO's. `PackageNarrator` (new)
  owns this text; package-lifecycle comments no longer post to `PurchaseOrderNarrator`.
- **`has_splits` is a new `BooleanField(default=False)`** (D73), maintained by
  `PackageLineSplitHandler`, mirroring `mixed_po_assignments`'s shape.
- **`tracking_number` is renamed `shipment_id`** (D75) — same shape, not unique, string on purpose.
