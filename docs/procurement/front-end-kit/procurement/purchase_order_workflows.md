---
okf_version: "0.1"
type: "Process Guide"
title: "Purchase Order Workflows — Front-End Plan"
description: "Actions, pages, control-layer targets, search apparatus, and card layout for the Purchase Order sector of the procurement UI, including the create-PO wizard — the highest-traffic screen in the app."
tags: [front-end-kit, procurement, purchase-order, workflows, wizard]
context_tier: 2
personas: [frontend, business]
---

# Purchase Order Workflows — Front-End Plan

**Sector:** turning approved (or informally-approved, per D42) demand into a commercial order,
editing that order's lines and allocations, and moving it through its own status lifecycle. Per
D44, the PO wizard and line editing are the **highest-traffic Buyer surfaces** in the whole
application — build these with the most care.

## Source documents (read first)

| Document | What it defines |
| :--- | :--- |
| [../../procurement_starter_kit/purchase_ordering_system.md](../../procurement_starter_kit/purchase_ordering_system.md) | PO/allocation mechanics — authoritative (revision banner: receiving mechanics superseded by D55/D59, see [package_workflows.md](package_workflows.md)) |
| [../../procurement_starter_kit/control/create_purchase_order_wizard.md](../../procurement_starter_kit/control/create_purchase_order_wizard.md) | `create_purchase_order` — why it's a wizard, the session-backed draft, vendor selection |
| [../../procurement_starter_kit/control/purchase_order_line_editing.md](../../procurement_starter_kit/control/purchase_order_line_editing.md) | Post-creation line edits with audit snapshots, `cancel_purchase_order_line`, `allocate_demand_to_po_line`, de-linking |
| [../../procurement_starter_kit/control/purchase_order_lifecycle.md](../../procurement_starter_kit/control/purchase_order_lifecycle.md) | `place_purchase_order`, `close_out_shipment`, `cancel_purchase_order`, the event emitter |
| [../../procurement_starter_kit/models/purchase_order.md](../../procurement_starter_kit/models/purchase_order.md), [purchase_order_line.md](../../procurement_starter_kit/models/purchase_order_line.md), [purchase_order_demand_link.md](../../procurement_starter_kit/models/purchase_order_demand_link.md) | Columns, the vendor-is-`PartManufacturer` decision (D45), why there's no line status (D51) |
| [../../harness/UX_UI/design_patterns/multi_step_flows.md](../../harness/UX_UI/design_patterns/multi_step_flows.md) | The wizard shape this section applies, not redesigns |

### Legacy reference (old Flask app)

The prior application (`/home/cb/REPOS/asset_management`) shipped a working version of both the
create-PO flow and the PO-to-demand linking tool. Its **interaction layout** is a useful visual
reference; its **data model is not** — the old app links a demand batch straight to a part with no
separate line/allocation split, no `PurchaseOrderDemandLink` cap (D28), and no permission gating
(D2/D3). Treat these as UX inspiration only, reconciled against this kit's model docs above.

| Old screen | Route | Templates | Maps to |
| :--- | :--- | :--- | :--- |
| Purchasing portal (create PO from demands) | `GET /inventory/create-po` (`po_portal.py`) | `inventory/purchase_orders/create_from_part_demands.html` + `components/po_header_form.html`, `components/filters_section.html`, `components/search_results_table.html`, `components/parts_summary.html`, `components/part_summary_item.html`, `components/add_unlinked_part_modal.html` | [§2.1 Create PO wizard](#21-procurementpurchase-orderscreate--create-po-wizard) |
| PO linkage portal | `GET /inventory/purchase-order/<id>/link` (`po_linkage_portal.py`) | `inventory/purchase_orders/linkage_portal.html` | [§2.4 PO Edit & Linkage](#24-procurementpurchase-ordersidedit--po-edit--linkage) |

## Rules that must hold in the UI

- **This is the one sector with a real wizard.** `PurchaseOrder` has two reverse FKs a Buyer
  populates in one sitting — `PurchaseOrderLine` and, under each line, `PurchaseOrderDemandLink`.
  That is a textbook wizard trigger (`create_purchase_order_wizard.md`, "Why this is a wizard").
- **One route, vertical scroll, session-backed draft** (`multi_step_flows.md`). Nothing commits to
  the database until final submit — `PurchaseOrderDraftAdaptor` owns vendor, header fields, and a
  list of lines each carrying its own `(demand_id, quantity_allocated)` pairs, entirely in
  `request.session`.
- **The PO opens as `Draft`, never `Placed`** (D52). The wizard's final submit action must be
  labeled and behave as "save draft," not "place order" — placing is [a separate, deliberate
  action](#22-po-detail--procurementpurchase-ordersid) on the detail page.
- **D28's allocation cap is per demand, never per line**, and exceeding it is neither a silent
  success nor a flat refusal — it surfaces an explicit choice ("raise the request" vs. "leave the
  excess unallocated") that the Buyer must resolve inline, with a strong warning on the raise-request
  option. This is not a validation error banner; it needs its own inline decision UI.
- **D42's auto-approve** happens silently unless the Buyer opts out via a checkbox — the wizard
  needs that opt-out control on the allocation step, and the resulting approval should be visible
  (as a system-generated journal entry) on the demand side, not hidden.
- **D57 — editing a placed order is a soft warning, never a block.** The PO detail page's line-edit
  controls stay fully interactive after `Placed`; show a warning banner, don't disable inputs.
- **D62 (permissions deferred)** — D2 (Buy permission for PO CRUD, Approve permission can transition
  status without Buy), D3 (allocation is Buyer-only) are unenforced server-side today. This kit's
  entrypoints must add the first real checks.

---

## 1. Actions that need to exist

| Action | Control-layer verb | Actor | Frequency |
| :--- | :--- | :--- | :--- |
| Create a purchase order (wizard) | `PurchaseOrderFactory.create_from_draft(draft, actor)` | Buyer | High, daily |
| Edit a line (qty, cost, dates, notes) | `PurchaseOrderLineManager.edit(...)` + audit snapshot | Buyer | High, daily |
| Cancel a line | `PurchaseOrderLineManager.cancel(line_id, actor)` | Buyer | Moderate |
| Allocate a demand to a line | `PurchaseOrderDemandLinkManager.allocate(...)` | Buyer only (D3) | High, daily |
| De-link a demand from a line | `PurchaseOrderDemandLinkManager.delink(link_id, actor)` | Buyer only | Moderate — the Buyer's alternative to cancelling a demand (D4) |
| Place the order | `PurchaseOrderContext.place(actor)` | Buyer, or Approver holding only `approve` | Daily |
| Advance shipment status manually | `PartDemandContext.advance_shipment(...)` | Buyer | Very high, ideally machine-fed later (D16) |
| Close out shipment (mark received) | `PurchaseOrderContext.mark_received(actor)` | Buyer | Moderate — explicit human act, never a quantity match (D29) |
| Cancel the order | `PurchaseOrderContext.cancel(actor, notes)` | Buyer | Rare — design for correctness |
| View PO list / detail | `PurchaseOrderStruct`, `PurchaseOrderFulfillmentStruct` (read) | Everyone with domain access | Constant |

---

## 2. Pages

### 2.1 `/procurement/purchase-orders/create` — Create PO wizard

**Page type:** Multi-card wizard, one route, vertical scroll, progressive enablement, session
draft. **Promote this to its own `key-workflows/` document** in a future pass — it has 3+ cards,
branching (the D28 cap decision), and is central to the app's purpose (see
`how_to_write_a_key_workflow.md`'s promotion criteria). This section gives the outline; the
full card-by-card spec (enablement conditions, draft keys, commit sequence, abandonment) belongs
in that promoted document.

**Control layer hit:** `PurchaseOrderDraftAdaptor` (session draft) → on submit,
`PurchaseOrderFactory.create_from_draft` → `PurchaseOrderLineManager.add_line` (per line) →
`PurchaseOrderDemandLinkManager.allocate` (per allocation) → `PurchaseOrderCostManager.recompute` →
`PurchaseOrderEventEmitter.emit(PO_CREATED)` — one transaction.

**Card sketch (scroll order):**

1. **Vendor & header** — vendor (`procurement.Vendor`), `vendor_contact` (free text), order date,
   expected delivery date, notes. Always enabled — first card. (Legacy: `po_header_form.html`.)
2. **Item selection** — a header-level two-option toggle (tabs or segmented control, not a modal)
   over one shared running-lines table, mirroring the old app's two ways into the same list
   (`filters_section.html` / `add_unlinked_part_modal.html`):
   - **From demands** — a **top-heavy search** apparatus: filter row on top (part, status,
     priority, domain, date range — same filter set as `OpenDemandSearch`) driving a **multi-select
     results table** underneath (legacy: `search_results_table.html`), each row an open `PartDemand`
     with an `Add selected to lines` action button. Selecting demands for a part and adding them
     both creates/updates that part's line **and** pre-populates card 3's allocation for exactly the
     demands picked here — the Buyer doesn't re-pick them in card 3, only confirms quantity/cap.
   - **Unlinked** — a plain single-line add form (part search, quantity, unit cost, optional
     delivery date/notes) for lines with no demand behind them yet (legacy: the
     `add_unlinked_part_modal.html` fields, without the modal — per this kit's modal rule, keep this
     inline in the card, not a popup). Zero demands on a line is valid (D14); this is the intended
     path for that case.
   - Enabled once the vendor is picked. Both options append to the **same** running lines table
     (legacy: `parts_summary.html`), so the Buyer can mix from-demand and unlinked lines freely.
3. **Allocate demands** (repeats per line added) — for each line, show open demands for that
   line's part, let the Buyer pick which to allocate and how much. Enabled once at least one line
   exists. Lines added via "From demands" arrive here pre-populated with their picked
   demand/quantity pairs (still editable); lines added via "Unlinked" arrive empty. This is the
   card that renders the D28 cap decision inline when triggered.
4. **Review & submit** — read-only summary of vendor, lines, allocations, and running `total_cost`
   before the draft becomes a real `Draft`-status PO. Enabled once every line has been resolved
   (allocated or explicitly left with excess). ("Review classic" — legacy `parts_summary.html`'s
   confirm-pricing pass plays the same role, minus its inline price-edit fields, which this kit's
   card 2 already owns.)

**Key things to note:**
- Card 3 is not one card — it's one **per line**, appearing as lines are added (progressive
  disclosure within the scroll, not a fixed count).
- The vendor step links out to a minimal `procurement.Vendor` create route (D45, reversed
  2026-08-09) rather than the parts-app manufacturer registry — vendors are no longer manufacturers.
- Zero demands allocated to a line is valid (D14) — don't force at least one pick before allowing
  the wizard to proceed.
- Unlike the legacy portal, there is no per-part "confirm price" checkbox gate — unit cost is a
  normal required field on the line-add step (card 2), not a separate confirmation ritual.

### 2.2 `/procurement/purchase-orders/<id>` — PO detail

**Page type:** Work portal (3/4 + 1/4 shell). Per-line editing (add/edit/cancel a line) and every
status action live in place on this page, per D57's "stays editable" rule — **revised:** header
fields (vendor contact, dates, notes) and demand linkage now have their own dedicated route, §2.4
`purchase-orders/<id>/edit` (formerly the Linkage Portal, renamed and extended — see §2.4). This
page still owns the quick, single-line allocation editor for touch-ups; anything header-level or a
full linking session belongs on §2.4.

**Control layer hit:** `PurchaseOrderFulfillmentStruct` (the whole-PO read: lines, allocations,
packages, the four quantities, per-line attribution mode — one annotated query, not one per line)
for page load; individual action buttons hit the verbs in §1.

### 2.3 `/procurement/purchase-orders` — PO list

**Page type:** Search / list page. Filters: status, vendor, domain, date range, part. Results
table with linkage-status badge per row (unlinked / partially linked / fully linked — computed
from `qty_allocated` vs. `qty_ordered`, same idea the legacy app had, now sourced from the struct
instead of a per-row query).

### 2.4 `/procurement/purchase-orders/<id>/edit` — PO Edit & Linkage

**Renamed from the PO Linkage Portal** (was `/link`) — the original "there is no separate edit PO
route" framing in §2.2 was wrong: header fields need somewhere to live, and this page's top row was
already a natural fit once it stops being read-only. **The route and the page's job both change**:
`/procurement/purchase-orders/<id>/link` → `/procurement/purchase-orders/<id>/edit`, and the top row
becomes a real edit form instead of a read-only summary strip. Everything else about this page —
the master-detail linking workspace — is unchanged from the original Linkage Portal design; update
every existing inbound link (part_demand_workflows.md's "Edit linkage" link, PO detail's "Open in
Edit & Linkage" link, the package sector's cross-references) to the new URL and title.

**Page type:** Dedicated PO-header-edit-plus-master-detail-linking workspace — a full-page, deep-
linking alternative to PO detail's inline per-line allocation editor (§2.2), for the Buyer running a
focused linking session across every line of a single PO, or touching up header fields (legacy
precedent: `linkage_portal.html`, `/inventory/purchase-order/<id>/link`, extended with an actual
edit form the legacy page didn't have). PO detail's inline allocation editor stays for quick
single-line touch-ups; this page is where the Buyer goes to edit the PO's own fields or work through
a whole PO's outstanding links in one sitting. Link from PO detail's allocation editor out to this
page rather than duplicating its layout there.

**Control layer hit:** `PurchaseOrderFulfillmentStruct` for the header form's current values and the
left-column line list (same read as PO detail); the header form posts to a plain PO-edit entrypoint;
`OpenDemandSearch` for the right-column search tool; `PurchaseOrderDemandLinkManager.allocate` /
`.delink` for the linking action buttons — same verbs as §1, same D3 (Buyer-only) and D28 (cap)
rules apply here, this is not a separate authorization surface.

**Layout:**
- **Top row, full width — now an edit form, not a read-only strip:** vendor, `vendor_contact`,
  order date, expected delivery date, notes — the same field set as the wizard's Vendor & header
  card (§2.1), pre-filled, with a standard card-footer save action. PO number and status badge
  still render here too, read-only (status changes through their own dedicated actions on PO
  detail, not this form — same edit-vs-status-action split D57 already draws for lines). Per D57's
  "permissive, paid for in audit" philosophy, a header edit on a placed-or-later PO posts a machine
  comment carrying the pre-edit snapshot, same shape as a line edit, on the PO's own Event.
- **Left column (1/3)** — every `PurchaseOrderLine` on the PO as a selectable row/card (part,
  qty ordered, allocated/qty-pending, linkage badge). Clicking a line selects it and drives the
  right column; nothing else on the page is interactive until a line is selected.
- **Right column (2/3)**, populated on line selection:
  - **Current links** for the selected line — each linked demand with its quantity and a
    **De-link** action (`PurchaseOrderDemandLinkManager.delink`).
  - **Demand search tool**, laid out **top-bottom** (not left-heavy like the wizard's pair): a
    filter/search bar across the top, matching open-demand results in a list beneath it, each
    result row carrying a **Link** action button that calls
    `PurchaseOrderDemandLinkManager.allocate` for the selected line. Search apparatus and filter
    set are the same `OpenDemandSearch` used everywhere else in this sector (§3) — only the
    spatial arrangement differs, because here the "pool" and "target" don't need to be visible
    side by side (the target is just the current-links list above it, not a running quantity
    build-up like the wizard's per-pick allocation).
- The D28 cap decision (raise-request vs. leave-unallocated) surfaces here exactly as it does on
  the wizard's allocation card and PO detail's inline editor — same component, three call sites.
  **Resolved (§5 Q1 — was open):** a modal is fine for this decision, despite the general "assignment
  relations never go in a modal" rule — it's a one-shot confirmation/choice on a single pending
  allocation, not the assignment interaction itself, which fits modals.md's "single-field capture /
  confirmation" carve-out rather than the excluded case.

**URL parameters (Tier 1 rule — [UX_UI.md](../../harness/UX_UI.md), [searchbars.md](../../harness/UX_UI/search/searchbars.md)):**
This page is a search-and-select surface, so it must accept its state as query parameters, not only
push them after a click:

| Param | Effect on load |
| :--- | :--- |
| `?line_id=<id>` | Pre-selects that `PurchaseOrderLine` in the left column and populates the right column exactly as a click would — this is the mechanism [part_demand_workflows.md](part_demand_workflows.md#23-procurementdemandsidedit--edit-demand)'s edit page uses to deep-link "edit linkage" straight to the relevant line, and how PO detail's "Open in Edit & Linkage" link (§4, PO detail table) lands pre-selected instead of forcing a re-find |
| `?part_id=<id>` | Pre-fills the demand-search tool's part filter (normally implied by the selected line's part, but useful if arriving before a line is chosen) |
| `?q=…`, other `OpenDemandSearch` filter params | Standard list-filter params on the demand search tool, per `searchbars.md`'s plain-HTMX-input contract |

Selecting a line is a client-side interaction, not a navigation, but it must **round-trip through
the URL** (`hx-push-url` on select) so a reload or a bookmark reproduces the same selected state —
the legacy app used a client-only JS selection with no URL sync; don't repeat that gap here.

**Key things to note:**
- No line is "unselectable" — even a fully-linked line stays clickable, so the Buyer can review or
  de-link an already-complete line without leaving the portal.

---

## 3. FK relationships → search apparatus

| FK | On | Rough pool size | Pattern | Why |
| :--- | :--- | :--- | :--- | :--- |
| `vendor` → `procurement.Vendor` | Wizard header card | Tens–low hundreds | `<search-dropdown>` | Single picked value for a form field |
| `part` (per line) → `parts.Part` | Wizard lines card, each add-line row | Hundreds–thousands | `<search-dropdown>` | Single value per row-add, pool exceeds typeahead threshold |
| Demand allocation → `PartDemand` (via `OpenDemandSearch`) | Wizard's "from demands" line-add tab; wizard per-line allocation card; PO detail's allocation editor | Tens–low hundreds *per part* (systemwide open-demand pool can be in the hundreds) | **Left-heavy assignment card pair (§3)** — 2/3-width pool with its own filters (priority, needed_by, domain), assigning into a 1/3-width "allocated to this line" list where each pick gets a quantity input | The pool needs its own filters/sort and the Buyer is picking several at once with a per-pick quantity — exactly §3's use case, not a 0–3-item picker (§4/§5) |
| Demand allocation → `PartDemand` (via `OpenDemandSearch`) | PO Edit & Linkage's right-column search tool (§2.4) | Same as above, scoped to the selected line's part | **Top-bottom search tool** — filter bar over a results list, each result a Link action — not the left-heavy pair, because the "target" side is just a current-links list rather than a running multi-pick build-up | The portal links one demand at a time against an already-selected line; there's no need to hold a side-by-side pool/target split for a single-pick action |
| Domain filter on `OpenDemandSearch` | Same card | 1 per PO (D61) | N/A — the PO's own `domain` scopes the search, not a separate picker | The PO's buying domain is set once at wizard start, not re-picked per allocation |

No dual listbox here — the candidate demand pool is expected to run into the hundreds systemwide,
past the "few dozen" ceiling where dual listbox degrades (`list_management_patterns.md`, Common
mistakes). Left-heavy assignment card pair is the only pattern in the family built for a large,
independently-filterable pool with per-pick metadata (the quantity), which this allocation step
needs on every pick.

---

## 4. Card layout

### 2.1 Create PO wizard — `/procurement/purchase-orders/create`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Vendor & header | Full width (wizard scroll, no side rail) | Vendor picker, contact, dates, notes |
| Item selection | Full width, two-option toggle over one shared running table | **From demands** tab: top-heavy — filter row over a multi-select open-demand results table, "Add selected to lines" button. **Unlinked** tab: plain single-line add form (part, qty, unit cost, dates/notes). Both feed the same running lines table below the toggle |
| Allocate demands (per line) | **Left-heavy pair, nested within the full-width wizard card**: pool 2/3, allocated-to-this-line list 1/3 | Left: filterable open-demand pool for the line's part. Right: picked demands with quantity inputs, running total vs. `quantity_ordered`. Pre-populated for lines added via the "From demands" tab |
| Review & submit | Full width | Read-only summary, `total_cost`, submit button labeled "Save as Draft" |

### 2.2 PO detail — `/procurement/purchase-orders/<id>`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Header / hero | Full width | PO number, vendor, status badge, primary actions (Place / Mark Received / Cancel, permission-gated) |
| Lines table | Left, main column (2/3) | Every line: part, qty ordered, unit cost, line total, allocation summary, attribution-mode badge (unlinked / attributable / shared session — see [shared_workflows.md](shared_workflows.md)), edit/cancel row actions |
| Packages | Left, main column (2/3) | This PO's packages: number, tracking, status badge, received date. "Manage packages" action links to [package_workflows.md §2.5](package_workflows.md#25-procurementpurchase-ordersidbasic-package-manager--basic-package-manager) — the preferred, drag-and-drop entry point for building this PO's expected packages |
| Allocation editor (expands per line) | Left, main column (2/3) | Same left-heavy assignment pair as the wizard's per-line card, reused here for post-creation allocate/de-link; includes an "Open in Edit & Linkage" link out to §2.4 for header edits or a full-PO linking session |
| Placed-order warning banner | Left, main column (2/3), above the lines table, only when `status != Draft` | Soft warning per D57 — never disables the table below it |
| Cost summary | Right, detail rail (1/3) | Line total, shipping, tax, other, `total_cost` |
| Status & quick facts | Right, detail rail (1/3) | Status, order date, expected delivery, domain, vendor contact; a "View full association network" link seeded `?po_id=<id>` into [graph_association_visualizer.md](graph_association_visualizer.md) |
| Event / activity thread | Right, detail rail (1/3) | Machine comments (status changes, audit snapshots per D57) + human comments + document attachments — this is `events.Event`'s comment/attachment surface (D17–D19), always renders even with zero comments |

### 2.3 PO list — `/procurement/purchase-orders`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Filters | Full width | Status, vendor, domain, date range, part |
| Stat bar | Full width | Counts: draft, placed, partially received, received this period |
| Results table | Full width | PO number, vendor, status, order date, total cost, linkage-status badge |

### 2.4 PO Edit & Linkage — `/procurement/purchase-orders/<id>/edit`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Header edit form | Full width, top row | PO number, status badge (read-only); vendor, `vendor_contact`, order date, expected delivery date, notes (editable, standard card-footer save) |
| Line list | Left column (1/3) | Selectable `PurchaseOrderLine` rows: part, qty ordered, allocated/pending, linkage badge |
| Current links + demand search | Right column (2/3), populated on line select | Top: current links for the selected line, each with a De-link action. Below: top-bottom demand search tool (filter bar over results list) with a per-result Link action |

---

## 5. Open questions for the developer

- ~~Should the D28 "raise the request vs. leave unallocated" decision render as an inline expandable
  panel...~~ **Resolved:** a modal is fine for this one — see §2.4's note where the decision is
  specced. Treated as a confirmation/choice moment, not the assignment interaction itself, so it
  doesn't trip the "assignment relations never go in a modal" rule.
- ~~The manual shipment-state advance...~~ **Resolved:** the verb is
  `PartDemandContext.advance_shipment(...)` — per-demand, not per-PO — so the control lives on the
  demand's own [edit page](part_demand_workflows.md#23-procurementdemandsidedit--edit-demand), as
  the "shipment" option in its generic status-update popup, not on the PO detail hero. D40's
  auto-propagation (`Shipped`/`Backordered`/`Lost` off `PurchaseOrder.status`) still fires
  independently and needs no control anywhere — this manual action only covers the granular
  pre-`Shipped` steps and the explicit close-out stage D40 doesn't drive. Confirm this still holds
  once D16's machine feed exists.
