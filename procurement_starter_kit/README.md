# Procurement — Starter Kit

**Status: models and control layer BUILT (2026-08-09).** `app/procurement/` and `app/inventory/`
exist, migrate, and are exercised end-to-end by `python manage.py seed_procurement_dev`. What is
**not** built: no entrypoints, no `urls.py`, no templates (the UI is the front-end kit's job), no
tests, and — importantly — **no permission enforcement anywhere** (D62). Every contradiction the kit
had accumulated is resolved in decisions **D61–D67**; read those before trusting any earlier
statement about package placement, quantity types, or the `# DELIBERATE ANTI-PATTERN` that no longer
exists.

See
[decisions.md](decisions.md) for confirmed decisions (D1–D41) and
[open_questions.md](open_questions.md) for what's still open (just P2, persona volume). Two items
were deferred to tech debt in their entirety and relocated out of this kit — see
[../docs/procurement/tech_debt/](../docs/procurement/tech_debt/): the
per-organization process-template/workflow engine, and the external (non-Django) PO integration
API. Both docs explain the underlying problem, not just the design that was shelved, so they're
usable if revisited later. A vendor multi-point-of-contact problem surfaced during design review
was logged as parts-app tech debt instead (D41) — see
[../docs/parts/tech_debt/20260808 vendor multiple points of contact per category.md](../docs/parts/tech_debt/20260808%20vendor%20multiple%20points%20of%20contact%20per%20category.md).

For the system design itself: [part_demand_system.md](part_demand_system.md) is the authoritative
reference for the **four-axis** state model on `PartDemand` (`demand_state`/`purchasing_state`/
`shipment_state`/`issuance_state` — revised 2026-08-08 from an earlier three-axis model, see D32),
and [purchase_ordering_system.md](purchase_ordering_system.md) covers `PurchaseOrder`/`Vendor`, the
demand↔PO linking rules, and the exact partial-fulfillment mechanics.

**Scope note:** this kit designs the Part Demand, Purchase Order, and Package applications under
Procurement. Part issuance is a separate, later build under Inventory — `issuance_state`'s
reconciliation workflow and the full issuance path are defined as enum surfaces here but their
transition logic is deliberately left open for that kit.

A backend-only starter kit for the Procurement application: requesting material, approving
requests, ordering from vendors, and tracking shipments — the first app in a proposed build order
that ends with an Inventory app, then Maintenance, then Dispatching. See
[initial_prompt.md](initial_prompt.md) for the full seed context and
[procurement_inventory_boundaries.md](procurement_inventory_boundaries.md)
for the design-review discussion this kit is built from.

## Build scope (2026-08-08)

The kit now carries a resolution-level build plan in two folders:

- **[models/](models/index.md)** — one document per table, plus the app-boundary contract. Eight
  tables in `app/procurement/` (`PartDemand`, `PartDemandUpdate`, `PurchaseOrder`,
  `PurchaseOrderLine`, `PurchaseOrderDemandLink`, `Package`, `PackageLine`) and one stub table in
  `app/inventory/` (`PartIssue`).
- **[control/](control/index.md)** — six workflow documents (business goal, ordered steps,
  classes touched) plus the full class inventory for both apps.
- **[shared_demand_sessions.md](shared_demand_sessions.md)** — a third system-concept document
  alongside `part_demand_system.md` and `purchase_ordering_system.md`. **Read it before touching
  anything to do with arrival quantities.** It defines when "how much of my demand arrived" has an
  answer and when the only truthful response is a session total.

Decisions taken while writing them are recorded as D45–D60 in [decisions.md](decisions.md). The
significant ones: no `Vendor` table (D45, **later reversed 2026-08-09** — see decisions.md — a
real `procurement.Vendor` table now exists, decoupled from `parts.PartManufacturer`), `PartIssue`
moves to `app/inventory` (D46), a typed PO
event emitter replacing D20's signal (D48), the app label `procurement` (D49), **`Package` and
`PackageLine` move to `app/procurement` (boundary refinement)**, `DemandSetLine → PurchaseOrderDemandLink`
(D50), **`quantity_received` removed in favor of derived arrival and shared demand sessions (D55)**,
line cancellation resetting demands to unpurchased (D56), edit-with-audit-snapshot replacing edit
locks (D57), and **packages built this cycle with a line-splitting wizard, intake still deferred (D59)**.

`purchase_ordering_system.md` carries a revision banner marking its receiving mechanics as
superseded by D55/D59.

No phase table yet — phases are proposed after the questionnaire is answered and interrogated.
