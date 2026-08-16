---
type: "Technical Decision"
title: "Tech Debt: A PO line records only the Part — not which supplier item or which revision was ordered"
description: "PurchaseOrderLine FKs to parts.Part, so the record cannot say which manufacturer's item was bought or which part revision was ordered against, even though parts already models both."
tags: [technical-decisions, technical-decision, tech-debt, part-demand-purchasing, parts]
context_tier: 2
---

# Tech Debt: A PO line records only the Part — not which supplier item or which revision was ordered

**Logged:** 2026-08-08
**Source:** `procurement_starter_kit` build-scoping session — `models/purchase_order_line.md`
and D45 (dropping the `Vendor` table in favor of `parts.PartManufacturer`).
**Status:** deliberately out of scope for the demand + purchasing build. Not a defect in that
build — a known, accepted gap.

## The problem

`PurchaseOrderLine` FKs to `parts.Part` and nothing else. `PurchaseOrder` FKs to
`parts.PartManufacturer` as its vendor (D45). So a placed order can say *"we bought 10 of internal
part P-1042 from Acme"* and cannot say either of the two things a buyer or engineer will
eventually want to know:

1. **Which supplier item was actually bought.** `parts.SupplierItem` already models exactly this —
   a purchasable vendor item (`part_manufacturer` + `manufacturer_part_number` + `name`) mapped
   forward to exactly one internal `Part`. One internal part commonly maps to several supplier
   items across manufacturers, and often several from the *same* manufacturer. The PO line records
   the internal part, so which of those was ordered is unrecoverable from the record.

2. **Which revision the order was placed against.** `parts.PartRevision` carries a flat
   major/minor revision history per part, and `SupplierItem` already carries a compatibility range
   against those numbers (`min_/max_major_revision_number`, `min_/max_minor_revision_number`). None
   of that is captured at order time, so a line ordered when the part was at rev 2.1 is
   indistinguishable from one ordered after it moved to 3.0.

**The capability exists in `parts` today.** This is not a missing model — it is two FKs (or a
denormalized revision-number pair) that the purchasing build chose not to add.

## Why it was left out

The demand + purchasing build's scope stops at "requisition and procurement": does someone need
this, and did we place an order for it. Adding supplier-item and revision selection to a PO line
pulls three things into a workflow explicitly kept lean:

- **A wizard step.** The Buyer would pick part → then supplier item → then confirm revision
  compatibility, on the highest-traffic screen in the app (D44). That is the create-PO wizard's
  most expensive possible addition.
- **A compatibility check.** `SupplierItem`'s min/max revision range exists to be *validated
  against*, which means a guard, which means deciding what happens when the range excludes the
  part's current revision — block, warn, or record. That is a real business-rule conversation, not
  a schema change.
- **A default-resolution rule.** `Part.primary_supplier_item` and `Part.is_simple_part` exist
  precisely so the common case needs no choice. Whether a PO line should auto-fill from those, and
  what it does for a non-simple part, is undecided.

None of that blocks placing orders today, so none of it was built.

## What it costs while deferred

- **Receiving cannot verify against what was ordered.** When packages and intake are built (D47),
  a package line records a `Part` and a quantity. There is no ordered supplier item to check the
  received item against, so vendor substitutions are invisible to the system.
- **No purchase history per supplier item.** "What have we paid Acme for their MPN 44-B over
  time" is unanswerable, even though `unit_cost` is on every line — the line cannot say the cost
  was for that item rather than a sibling item mapping to the same internal part.
- **Revision drift is silent.** A part revised after an order was placed leaves no record of which
  revision the order assumed. For anything where revision matters this is exactly the trace an
  engineer would go looking for.
- **`PurchaseOrder.vendor` and the line can disagree in principle.** Nothing checks that a
  supplier item for the ordered part exists at the PO's vendor at all, because no supplier item is
  named.

## Shape if revisited

Two columns on `PurchaseOrderLine`, both nullable so existing rows stay valid:

- `supplier_item` — FK → `parts.SupplierItem`, `PROTECT`, nullable. Validated in the control layer
  to belong to the PO's `vendor` and to map forward to the line's `part`.
- Revision capture — either an FK to `parts.PartRevision` or a denormalized
  `(major_revision_number, minor_revision_number)` pair snapshotted at order time. The
  denormalized pair is probably right: what matters is *what revision the order assumed*, which
  should not move when the revision record does. `SupplierItem` itself already prefers plain ints
  over an FK for the same reason (parts D13).

Defaulting: fill from `Part.primary_supplier_item` when `Part.is_simple_part` is true, so the
common case still needs no Buyer decision. The wizard step only appears for parts with genuine
choice.

Interaction to settle first: **whether a revision mismatch against `SupplierItem`'s compatibility
range blocks the order, warns, or is merely recorded.** Given this system's standing principle —
record what actually happened rather than dictate what must be true (D29/D30) — a warning that is
recorded and not blocking is the likely answer, but it has not been decided.

## Related

- [`../../parts/tech_debt/20260808 vendor multiple points of contact per category.md`](../../parts/tech_debt/20260808%20vendor%20multiple%20points%20of%20contact%20per%20category.md)
  — the other half of the vendor-modeling gap. Note that D45 changed its context: with no `Vendor`
  table and `vendor_contact` living on the `PurchaseOrder`, the multi-contact problem is sidestepped
  per-PO rather than solved, and that note now describes a future contact registry rather than a
  missing column on a table this build creates.
- `procurement_starter_kit/decisions.md` D45 — why there is no `Vendor` table.
- `procurement_starter_kit/models/purchase_order_line.md` — the line as built.
