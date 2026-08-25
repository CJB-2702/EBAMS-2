---
okf_version: "0.1"
type: "Reference"
title: "Gap Analysis — Legacy asset_management/inventory vs. procurement_starter_kit"
description: "What existed in the legacy Flask inventory routes, what changed in the new procurement design, and what's still missing before a UI can be built against it."
tags: [front-end-kit, procurement, gap-analysis]
context_tier: 2
personas: [frontend, backend, business]
---

# Gap Analysis — Legacy `asset_management/inventory` vs. `procurement_starter_kit`

Source material: `asset_management/app/presentation/routes/inventory/**/*.py` (legacy Flask app,
routes only — no templates reviewed) vs. `procurement_starter_kit/` (this repo's backend-built
replacement). Written at the start of this front-end kit so the UI plan below is built against the
*actual* delta, not assumptions carried over from the old app.

---

## What existed before (legacy Flask routes)

One `inventory` blueprint mashing together five concerns:

- **Arrivals** (`arrivals/`) — `ArrivalHeader`/`ArrivalLine`, a creation portal (select PO lines or
  add unlinked parts → submit), a detail view, and a **linkage portal**
  (`arrival_linkage_portal.py`) attaching/detaching arrival lines to PO lines via a many-to-many
  `PurchaseOrderLine` link table (`po_line_links`).
- **Purchasing** (`purchasing/`) — PO list/detail/edit (line add/remove/update, header edit,
  submit, cancel), a **PO-side linkage portal** (`po_linkage_portal.py`) linking part demands to PO
  lines, a "create PO from part demands" wizard, and a part picker.
- **Inventory** (`inventory/`) — active inventory view, movements, part issues, move/discard/
  issue-parts flows.
- **Storeroom** — storeroom/location/bin CRUD plus an SVG layout builder.
- **Part demand** — reduced to a redirect stub pointing at a separate module.

`ArrivalHeader`/`ArrivalLine` conflated **"a package arrived"** with **"the receiving/attribution
transaction"** — arrival lines linked to PO lines through `po_line_links`, and could attribute
receipt to a PO line but never to a specific *demand*. PO lines also carried computed `@property`
totals (`quantity_received_total`, `total_quantity_linked_from_arrivals`, `line_total`) queried
per-access — a documented N+1 problem on a 40-line PO (fixed in the new design, D53/D67).

---

## What changed in the new design

| Legacy | New (`procurement_starter_kit`) |
|---|---|
| `ArrivalHeader`/`ArrivalLine` (one concept, two jobs) | Split into **`Package`/`PackageLine`** (procurement — pre-possession, "what shipped") vs. future **intake** (inventory — "what to do once it arrives"). **Intake is not built.** |
| `po_line_links` many-to-many, attribution only to PO line | **No link table.** A `PackageLine` FKs to exactly **one** PO line. A line spanning multiple orders/lines is **split into sibling rows** (`split_from` lineage) via a dedicated **splitting wizard** — retires `ArrivalLine.quantity_available_for_linking` by name (`models/package.md`). |
| Arrival↔demand attribution: none (PO-line level only) | Per-demand arrival is **derived**: 1 active demand link on a PO line → attributable; 2+ → a **shared demand session** (session total only, never a fabricated per-demand split); 0 → unlinked/proactive stock. See `shared_demand_sessions.md`. |
| `condition` enum (Good/Damaged/Mixed) on arrival line | Dropped — replaced by `quantity_accepted` (nullable decimal) + `rejection_notes`. Partial acceptance is a quantity, not a category. |
| PO line `status` cascaded from header, plus computed `@property` totals | No line-level `status` (D51); all derived quantities computed via `Subquery` on a struct, never a model property (D53/D67). |
| Lines effectively frozen once purchased | Lines stay editable post-`Placed`; every mutation writes an audit-snapshot comment instead of locking (D57). |
| Single `order_status`/`workflow_state` conflating money + logistics | **Four-axis** model: `demand_state`, `purchasing_state`, `shipment_state`, `issuance_state` — explicitly because the legacy single status conflated "money authorized" with "physically in transit" (`decisions.md`, four-axis redesign section). |
| `PartDemandPurchaseOrderLink`, carried `quantity_received` | Renamed `PurchaseOrderDemandLink`; `quantity_received` **removed** (D55) — arrival is derived per the table above. |
| Part issuance lived in `inventory` routes alongside everything else | `PartIssue` stays in `app/inventory`, deliberately a thin stub. Full issuance mechanics are a separate, later kit. |
| Route-level role decorators (`@require_any_module_role`, `@require_module_role`) | **Explicitly deferred** (D62). No permission enforcement anywhere in the backend yet — enforcement is pushed entirely to the entrypoint/UI layer this front-end kit plans. |

---

## Gaps to design against

1. **No entrypoints/urls/templates exist.** Only models + control layer are built. The old route
   trees are a reference for *what users need to do*, not a porting target — the shapes changed too
   much (see table above).
2. **Permission enforcement is entirely this kit's job.** D2/D3/D4's persona rules (Approve vs. Buy
   independently grantable, Buyer-only allocation, Buyer-never-cancels-a-demand) are currently just
   documented conventions with nothing enforcing them server-side.
3. **The old "arrival linkage portal" interaction (search POs → link/unlink API calls) has no
   direct replacement.** Its equivalent is the **package line-splitting wizard** — a different
   interaction model (assign a quantity → split into a new row) rather than a link/unlink toggle.
4. **Intake is a hard stop.** Everything the legacy app did past "package accepted" — put-away, bin
   assignment, stock levels, `move_inventory`, `discard_inventory`, storeroom/location/bin UI — has
   **no corresponding backend yet**. Out of scope for this front-end kit.
5. **Package↔demand `shipment_state` propagation and the "least advanced status wins" rule**
   (`control/package_lifecycle.md`) need a UI treatment — a demand behind two packages should
   visibly explain why it isn't "delivered" yet.
6. **Shared demand sessions** (2+ demands on one PO line) need a UI treatment that shows a session
   total rather than fabricating a per-demand split — nothing in the legacy UI modeled this.
7. ~~No control-layer verb exists for a manual `purchasing_state` decision.~~ **Resolved, not a gap
   after all.** `part_demand_system.md` defines the enum (`null → Approved | Denied → Purchased →
   Cancelled`, D34), and it's true no `PartDemandContext` verb exists for a Buyer manually deciding
   `Approved`/`Denied` outside of linking a PO — but [part_demand_workflows.md](part_demand_workflows.md#23-procurementdemandsidedit--edit-demand)'s
   edit page no longer wants one. The displayed purchasing status is derived entirely from PO
   linkage (see that document's Rules section), so there's no manual decision for a verb to back.

These seven gaps are the reason the per-sector workflow documents in this folder (
[part_demand_workflows.md](part_demand_workflows.md),
[purchase_order_workflows.md](purchase_order_workflows.md),
[package_workflows.md](package_workflows.md),
[shared_workflows.md](shared_workflows.md)) exist — each names the pages, control-layer targets,
and search apparatus needed to close it.
