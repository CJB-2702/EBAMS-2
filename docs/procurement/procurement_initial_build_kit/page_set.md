---
okf_version: "0.1"
type: "Kit Document"
title: "Page Set — Procurement"
description: "Every route in the procurement application and the inventory mirror: what each page is for, who uses it, what it writes, and what it deliberately does not do."
tags: [procurement, routes, pages, reference, okf]
context_tier: 2
personas: [frontend, business]
---

# Page Set

> **Note on kit boundaries.** Route inventories normally live in a front-end kit, not a
> starter kit, because UI is disposable and business rules are durable. This document is
> here anyway because the UI already exists and the goal of this kit is to describe the
> built system. Treat it as a **map of what is built**, not as a specification to build
> against.

Seventeen routes across procurement, plus three in the inventory mirror.

---

## Rules that hold on every page

1. **The F5 rule.** Every state is reachable by a plain `GET` of a URL. Every write is
   POST → redirect → GET. Wizard state lives in the session, so refreshing mid-build
   restores it rather than losing it.
2. **The domain fence.** Every queryset filters on the viewer's accessible domains. A
   record outside the fence still renders where it is *referenced* — as plain text with no
   link through — but is never listed or reachable.
3. **Permission gates live at the entrypoint**, never in the template. A control the user
   may not use is not rendered at all, not merely disabled.
4. **One canonical URL per resource**, with `?format=` for density and HTMX fragments.
5. **Cards render even when empty** — with an explicit empty state, never hidden.

---

## Shell

### `/procurement/` — Hub
Entry-card grid plus a **one-query**, domain-scoped stat bar. The landing page for every
persona; each card leads into one sector.

---

## Demands — `/procurement/demands/`

| Route | Page | Goal |
| :--- | :--- | :--- |
| `` | **Demand index** | Search and list. **One canonical list serves every role** — the approver's queue is `?demand_state=required`, the buyer's "what needs buying" view is a sparse `purchasing_state` filter. No saved presets, deliberately |
| `create/` | **Create demand** | A simple single-card form. **Not a wizard** — PartDemand has zero qualifying reverse FKs a user would populate in the same sitting |
| `<pk>/` | **Demand detail** | A read-only work portal. Nothing writes here except Cancel and Delete on the header; every other mutation links out to the edit page. Shows the four-axis status card, the allocation slices, and the journal |
| `<pk>/edit/` | **Demand edit** | Full-width, and **the only place every status-changing action lives**. Four cards, each posting back to this same URL with a distinct `action` |

The detail/edit split is the shape used throughout the application: **detail is for
reading and for the one or two verbs that belong to the record as a whole; edit is where
state moves.**

---

## Purchase orders — `/procurement/purchase-orders/`

The highest-traffic screens in the application.

| Route | Page | Goal |
| :--- | :--- | :--- |
| `` | **PO index** | The buyer's list |
| `create/` | **Create PO wizard** | One route, vertical scroll, progressive enablement, session-backed draft. **Nothing touches the database until final submit** — a half-built PO would be visible to other buyers, would need a status meaning "not really a PO yet", and would leave orphans when abandoned. Searches open **part demands** and links them to the lines being built |
| `<pk>/` | **PO detail** | The work portal: header, lines, allocations, fulfillment rollups, and the lifecycle verbs (submit, approve/deny, place, cancel) |
| `<pk>/edit/` | **PO Edit & Linkage** | Header edit plus the allocation tool. Line selection **round-trips through the URL** (`?line_id=`) so demand pages can deep-link to a specific line and so a reload or bookmark reproduces the selection — a gap in the legacy portal, which used client-only selection |
| `<pk>/basic-shipment-manager/` | **Basic Shipment Manager** | PO-scoped, but a Phase 3 page. **Forward-looking**: a buyer planning expected boxes from a vendor's shipping confirmation, not a receiver with a carton. Drag-and-drop is the fast path and **never the only path** — every gesture has a plain form equivalent posting to the same action, which is what keeps F5 true. Committed all-or-nothing on submit |

---

## Shipments — `/procurement/shipments/`

| Route | Page | Goal |
| :--- | :--- | :--- |
| `` | **Shipment index** | The receiving queue. Two filters are first-class because each maps to a real standing job: `mixed_po_assignments` **is** the drift review queue, and `shipment_id` is how a receiver with a box in hand finds its record — they search by what is printed on the label, not by our number |
| `create/` | **Create shipment wizard** | The PO wizard's mirror one level down the chain: it searches open **purchase order lines** and links them to the arriving lines being built. Same cards, same gates, same session-only-until-submit rule |
| `receive/` | **Reactive receive** | A box arrived and there is no purchase order. **There is no PO field on this form** — offering a picker would just recreate the create wizard and lose the one thing this route exists to say: *you do not need the paperwork to record the box.* Lines land with no allocations at all, which is correct, not an error state |
| `<pk>/` | **Shipment detail** | Work portal. **Two verbs: `advance` and `accept`.** Everything else — reassignment, splitting, header edits, deletions — is a link to the edit page |
| `<pk>/edit/` | **Shipment edit** | The PO Edit & Linkage inverted: links **this shipment's** lines to PO lines, potentially across several vendors' open orders. **Absorbs the old line-splitting wizard entirely** — there is no `/lines/<id>/split` route, because splitting is simply what Assign does when the quantity is partial. One decision instead of choosing a verb before choosing a target. `?line_id=` pre-selects and round-trips |

---

## Prices — `/procurement/prices/`

| Route | Page | Goal |
| :--- | :--- | :--- |
| `` | **Price hub** | Entry point to the pricing surfaces |
| `bulk/` | **Bulk paste grid** | Paste a vendor's quote sheet; parse, review, commit as many observations at once. Identical for both authority levels — only the "Record as verified" checkbox appears or does not |
| `unpriced/` | **Unpriced parts** | The backstop list: parts nobody has ever priced |
| `parts/<part_id>/` | **Part price history** | One part's full observation history, plus the chip / picker / card format variants other pages embed |

---

## Vendors — `/procurement/vendors/`

| Route | Page | Goal |
| :--- | :--- | :--- |
| `` | **Vendor list** | The registry with htmx search |
| `create/` | **Vendor create** | A lookup-table create form. Owned by procurement; unrelated to parts |

---

## Graph — `/procurement/graph/`

| Route | Page | Goal |
| :--- | :--- | :--- |
| `` | **Graph index** | Domain-scoped list of every cluster, filterable by resolution state and manual flag. **There is no create action** — a graph forms, merges, and splits only as a side effect of other writes |
| `<graph_id>/` | **Graph visualizer** | The ten metrics and the status axes at the top, the cached mermaid swimlane diagram of members and edges in the middle, a three-column member summary below. **A graph is identified by its own id**, not by an entity id — entity detail pages link in through their own `graph_id`. No 404 for out-of-fence members; they render as plain text |

---

## Inventory mirror — `/inventory/shipments/`

A thin duplicate surface over procurement's own shipment rows. No `inventory.Shipment`
model exists; every write goes through `ShipmentContext`.

| Route | Page | Goal |
| :--- | :--- | :--- |
| `shipments/` | **Inventory shipment index** | The receiving queue, read-only, from inventory's side |
| `shipments/<pk>/` | **Inventory shipment detail** | Narrowed to the two verbs that belong to the physical/received side: `advance_status` and `accept_line`. All order-linkage links out to procurement |
| `shipments/<pk>/edit/` | **Inventory shipment edit** | Header edit, physical/received fields only |

**Deliberately absent here:** create, receive, PO attach, line reassignment, line delete,
shipment delete. Recording a new shipment and resolving order linkage stay procurement's
job.

---

## Page-shape patterns used throughout

| Pattern | Where | Why |
| :--- | :--- | :--- |
| **Detail = read + record-level verbs; Edit = state changes** | demands, POs, shipments | keeps the work portal glanceable and puts every mutation in one predictable place |
| **One long scrolling wizard, session-backed, DB-untouched until submit** | PO create, shipment create, basic shipment manager | a half-built record in the shared database is worse than a lost draft |
| **Selection round-trips through the URL (`?line_id=`)** | PO edit, shipment edit | deep links from other pages, and reload/bookmark reproducibility |
| **One canonical list per entity, driven by query filters** | demands, POs, shipments, graphs | avoids per-role page proliferation and saved-preset drift |
| **Drag-and-drop always has a plain form twin** | basic shipment manager | the F5 rule |
| **Out-of-fence records render as plain text, never vanish** | everywhere | a page that silently drops rows looks broken |
