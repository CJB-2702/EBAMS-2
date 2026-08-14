---
okf_version: "0.1"
type: "Process Guide"
title: "Part Demand Workflows — Front-End Plan"
description: "Actions, pages, control-layer targets, search apparatus, and card layout for the Part Demand sector of the procurement UI."
tags: [front-end-kit, procurement, part-demand, workflows]
context_tier: 2
personas: [frontend, business]
---

# Part Demand Workflows — Front-End Plan

**Sector:** requesting material and moving a demand through its four-axis lifecycle up to (but not
including) physical issuance, which is a later, separate kit.

## Source documents (read first)

| Document | What it defines |
| :--- | :--- |
| [../../procurement_starter_kit/part_demand_system.md](../../procurement_starter_kit/part_demand_system.md) | The four-axis state model (`demand_state`/`purchasing_state`/`shipment_state`/`issuance_state`) — authoritative |
| [../../procurement_starter_kit/control/create_demand.md](../../procurement_starter_kit/control/create_demand.md) | `create_demand` — why it's a simple form, not a wizard |
| [../../procurement_starter_kit/control/part_demand_lifecycle.md](../../procurement_starter_kit/control/part_demand_lifecycle.md) | `approve_reject_demand`, `cancel_demand`, `delete_or_deactivate_demand`, `record_issuance_and_return`, `complete_demand_rollup` |
| [../../procurement_starter_kit/models/part_demand.md](../../procurement_starter_kit/models/part_demand.md) | Columns, enums, indexes |
| [../../procurement_starter_kit/models/part_demand_update.md](../../procurement_starter_kit/models/part_demand_update.md) | The append-only journal — what the activity/history card reads |
| [../../procurement_starter_kit/decisions.md](../../procurement_starter_kit/decisions.md) | D1–D13, D25, D30–D44 govern this sector; D62 (no permission enforcement yet) is the standing caveat for every action below |

## Rules that must hold in the UI (do not re-derive, cite these)

- **D9/D10/D11 (the three gates)** are enforced server-side already, but the UI must render *why* a
  blocked action is blocked — e.g. cancel refused because a linked PO is still active must name
  that PO, not show a generic error (`part_demand_lifecycle.md`, `cancel_demand`).
- **D6 hard-vs-soft delete** — the delete action's confirmation copy must differ depending on
  whether the demand is untouched (real delete) or has history (deactivation). The page cannot
  assume which one will happen; ask the control layer first.
- **D15** — rejection/cancellation notes are optional. Do not add a client-side "required" mark that
  the backend doesn't enforce.
- **D42** — linking a demand to a PO line auto-approves it by default. The demand detail page must
  show *why* a demand moved to `Approved` without an Approver action (system-generated journal row,
  actor = the Buyer who linked it) — this is not a bug, don't hide or "fix" it in the UI.
- **D62 (permissions deferred)** — every action route below currently has zero server-side
  permission check. This kit's entrypoints are where D2 (Approve/Buy independently grantable), D3
  (allocation is Buyer-only — but that UI lives in the [purchase order sector](purchase_order_workflows.md)),
  and D4 (Buyer never cancels a demand) must actually get enforced for the first time.
- **Linkage editing is never built on this sector's pages.** Allocating or de-linking a demand
  against a PO line is Buyer-only (D3) and its UI already lives in the
  [purchase order sector](purchase_order_workflows.md#24-procurementpurchase-ordersidedit--po-edit--linkage).
  Every page in this file shows linkage **read-only** and links out to that portal — see the edit
  page (§2.3) for the exact deep-link contract.
- **Gap 7 is resolved, not just flagged — no manual "buy status" verb is needed.**
  [gap_analysis.md](gap_analysis.md) gap 7 originally read as a missing control-layer verb for a
  manual `purchasing_state` `Approved`/`Denied` decision. Resolved: this sector never needs that
  verb, because the *displayed* purchasing status is entirely **derived from PO linkage**, not
  separately decided. **Corrected per D70/[po_demand_association_graph.md](../../procurement_starter_kit/po_demand_association_graph.md) §2**
  — an earlier draft of this formula only handled a demand's *single* line, missing that a demand
  can hold several active `PurchaseOrderDemandLink` rows at once (split across vendors, re-sourced
  after a backorder). The corrected shape evaluates **per link**, then combines, exactly the
  pattern `shared_demand_sessions.md` already uses for arrival — this is not a new concept, only a
  fix to bring purchasing display in line with a rule this app already applies elsewhere:
  - **No active link** → show the stored `purchasing_state` as-is (normally unset/`null`, i.e. "not
    yet purchased").
  - **For each active link**, independently: compare that line's `quantity_ordered` against the
    **sum of `quantity_requested`** across every demand actively linked to *that line* (not this
    demand's other lines). If `quantity_ordered >= sum(quantity_requested)`, that line's contribution
    is the line's own PO status (translated the same way `purchasing_state` already is by existing
    propagation, `purchase_order_lifecycle.md`). If it's less, that link's contribution is
    **"Partial"** instead. **"Partial" is a display-only label, not a new `purchasing_state` enum
    value** — D22/D34's fixed enum is untouched.
  - **Combine:** one active link → show its contribution alone, framed as "mirrors PO `<number>`:
    `<status>`" (or "Partial on PO `<number>`"). Two or more active links → show each contribution
    separately, same sentence shape the arrival side already uses — *"PO 4021 (Purchased) covers one
    line; PO 4030 is Partial on the other"* — never collapsed into one misleading status for the
    whole demand.
  - **This never walks past the demand's own direct links** and those links' own direct co-demands —
    a bounded, one-hop-plus-one read, not a graph traversal, regardless of how large the wider
    PO/demand network gets.
  - **This formula only applies when `PartDemand.is_in_status_graph` is `False`.** That new column
    ([graph_association_visualizer.md](graph_association_visualizer.md) §5.2) is set proactively
    whenever an allocation makes any of this demand's lines shared by 2+ demands — the ordinary,
    common case. **When it's `True`, the one-hop formula above is not just incomplete, it can be
    outright wrong** — the demand's real status depends on the worst status and total quantity
    across the whole connected network (worked out in
    [graph_association_visualizer.md](graph_association_visualizer.md) §5.3–§5.5), which this card
    cannot compute itself. Flagged demands display their stored `purchasing_state` /
    `shipment_state` as-is — the resolver writes the graph-derived answer into those real columns
    (§5.6 there), so no local recomputation is wanted or correct — see the purchasing axis card
    (§2.4) for exactly what renders in each case.
  No popup, no Buy-permission-gated action, no placeholder verb — see §2.3/§2.4 below, which no
  longer carry the disabled Buy-status button an earlier draft of this document had.

---

## 1. Actions that need to exist

| Action | Control-layer verb | Actor | Frequency (D44) |
| :--- | :--- | :--- | :--- |
| Create a demand | `PartDemandFactory` via `create_demand` workflow | Requester | High, daily |
| Approve a demand | `PartDemandContext.approve(actor, notes=None)` | Approver | Low — often bypassed by D42 |
| Reject a demand | `PartDemandContext.reject(actor, notes=None)` | Approver | Low |
| Resubmit a rejected demand | Same row, `Rejected → Required` — no separate action, just re-save | Requester | Low |
| Cancel a demand | `PartDemandContext.cancel(actor, notes=None)` | Requester, Approver (never Buyer, D4) | Rare |
| Delete or deactivate a demand | `PartDemandContext.delete(actor)` | Requester, Approver | Rare |
| Edit basic demand fields (priority, needed-by, notes, quantity requested) | `PartDemandContext` field edit — same struct's write side, no state transition | Requester, Approver | Moderate |
| Advance shipment status manually | `PartDemandContext.advance_shipment(...)` | Buyer | High, ideally machine-fed later (D16) — see [purchase_order_workflows.md §5](purchase_order_workflows.md#5-open-questions-for-the-developer) for why this lives here and not on the PO |
| View lifecycle / journal | Read via `PartDemandStruct` | Everyone with domain access | Constant (this is the "check status" page) |
| View issuance history (read-only) | Read via `PartDemandStruct` — sourced from `inventory.PartIssue`, not writable here | Requester | High — this is their daily check-in, but the *write* path (`record_issuance_and_return`) belongs to `app/inventory`'s own **Inventory Issuance Portal**, not yet built. **Build the read view now, flag the write as out of scope.** |

**Deliberately no action for:** `complete_demand_rollup` (system-derived, no user trigger — show
the resulting `Completed` state, don't build a button for it); a manual `purchasing_state` decision
(resolved as a gap — see the Rules section above, the displayed purchasing status is derived from
linkage, not separately decided).

---

## 2. Pages

### 2.1 `/procurement/demands` — Demand list / search

**Page type:** Search / list page (`page_structure.md`) — full-width filters, full-width results
table, no right rail.

**Control layer hit:** `OpenDemandSearch` (read) — must annotate outstanding quantity and current
axis values in one query, not per-row (see `create_purchase_order_wizard.md`'s warning against the
legacy per-row query pattern).

**Key things to note:**
- This is also the Approver's queue (filter `demand_state=Required`) and the Buyer's "what needs
  buying" view (filter `purchasing_state` sparse/null) — one canonical list with saved/quick
  filters, not three separate pages.
- Default sort is `priority` then `needed_by` per every read spec in the control docs — don't let a
  generic "newest first" default creep in here.
- `Backordered`/`Partially Issued` are everyday states (D44) — the list's status badges need to
  read as normal, not alarming, for those.

### 2.2 `/procurement/demands/create` — Create demand

**Page type:** Simple form. `create_demand.md` is explicit that `PartDemand` has zero qualifying
reverse FKs — no wizard.

**Control layer hit:** `PartDemandCreateAdaptor` → `PartDemandFactory.create()` →
`PartDemandStateManager` (four initializing journal rows).

**Key things to note:**
- `domain` is **never a form field** in the normal case — it's resolved from the requester's own
  domain assignment (D5, step 2 of `create_demand.md`). Only render a domain picker if the
  requester holds more than one domain.
- No status/priority-gated fields at creation beyond `priority` itself — this stays a short form on
  purpose; resist adding sections.

### 2.3 `/procurement/demands/<id>/edit` — Edit demand

**Page type:** Basic form, full width, no side rail — this is a field-edit surface plus a read-only
audit trail underneath it, not a work portal. Editing basic fields and recording a status update are
two different kinds of write (a plain field patch vs. a gated state transition through
`PartDemandStateManager`), so this page keeps them visually distinct rather than blending them into
one save button.

**Control layer hit:** `PartDemandStruct` (read, for the form's current values and the history
table) for page load; the field-edit form posts to the plain edit entrypoint; each status-update
popup posts to its own verb from §1 (`advance_shipment`, the placeholder purchasing-decision verb,
`approve`/`reject` if surfaced here rather than only on detail — see open questions).

**Layout:**
1. **Demand fields card** — the editable fields: `priority`, `needed_by`, `quantity_requested`,
   `notes`, serial-tracking-required. Same field set as create (§2.2), pre-filled. Standard
   card-footer save action (`form_style_guide.md`) — no wizard, no session draft, this is a plain
   edit.
2. **Linkage — read only** — every active `PurchaseOrderDemandLink` for this demand: PO number, PO
   line, quantity allocated. Each row carries a single action: **"Edit linkage"**, a link to
   `/procurement/purchase-orders/<po_id>/edit?line_id=<line_id>` — PO Edit & Linkage
   (§2.4 of [purchase_order_workflows.md](purchase_order_workflows.md#24-procurementpurchase-ordersidedit--po-edit--linkage)),
   landing with that exact line pre-selected per its URL-parameter contract. **No link/de-link
   control exists on this page** — per the Rules section above, allocation is Buyer-only (D3) and
   lives only there. Empty state: "Not linked to a purchase order line yet."
3. **Status update actions** — a small action row, not a form: one button per axis the current
   actor is permitted to move, each opening a popup with a status-update form (target stage +
   optional notes) that on submit appends a row to the history table below. **No "buy status"
   button** — gap 7 is resolved, not blocked (see the Rules section above): purchasing status is
   entirely derived from PO linkage, so there is nothing here for a Buyer to manually set.
   - **Shipment ("advance shipment")** — visible to the Buy permission holder, calls
     `PartDemandContext.advance_shipment(...)`. This is the "type other" status update in the
     original ask: distinct from purchasing, it's the per-demand shipment-logistics axis, resolved
     to live here rather than on the PO detail page — see
     [purchase_order_workflows.md §5](purchase_order_workflows.md#5-open-questions-for-the-developer).
   - **Approve / Reject** — same `approve`/`reject` verbs as detail (§2.4); duplicating the entrypoint
     here means an Approver can act while already editing fields, without a round trip. Gated on the
     `approve` permission (D2). **This is the only place these actions live** — detail (§2.4) never
     duplicates them, per the requester's confirmation that all status-changing actions belong on
     the edit page, not scattered across both pages.
   - Issuance is **not** offered here, now or later — `record_issuance_and_return` is only ever
     called from `app/inventory`'s own **Inventory Issuance Portal** (not yet built), never from a
     form in this app (§1's "Deliberately no action for" note). Once that portal exists, this page's
     shipment/purchasing actions still won't include issuance — it stays a separate app's job.
4. **Status history — full width, table view** — every `PartDemandUpdate` row for this demand,
   across all four dimensions, oldest or newest first (match the detail page's journal ordering),
   columns: dimension, from → to, actor (or "System" when `is_system_generated`), notes, timestamp.
   **Read only — no row here is ever editable**, per the append-only journal (`part_demand_update.md`).
   This is the same data the detail page's per-axis cards and misc-updates card (§2.4) curate from,
   shown here in full and unfiltered so an editor has complete context while changing fields.

**Key things to note:**
- This page and detail (§2.4) intentionally overlap on the status-update actions and the raw
  history table — edit is where you go to *act*, detail is where you go to *understand the current
  state at a glance*. Don't try to merge them into one page; the two audiences (quick edit + act,
  vs. full situational read) want different densities.
- Popup status-update forms are the one place on this page a Bulma modal is appropriate — per
  [modals.md](../../harness/UX_UI/design_patterns/modals.md), a modal is fine for "a single-field
  capture" and this is exactly that (target stage + optional notes), unlike assignment relations
  which never go in one. Don't build this as an inline expanding card instead; the popup framing
  matches its transactional, one-shot nature.

### 2.4 `/procurement/demands/<id>` — Demand detail

**Page type:** Work portal (3/4 + 1/4 shell per `page_structure.md`) — this is where a Requester
checks "is my stuff coming," an Approver acts, and a Buyer sees demand-side context before pivoting
to the PO sector. Read-heavy, wide, situational — the opposite emphasis from edit (§2.3): nothing on
this page is a form field, every write is a button linking to an action or out to §2.3.

**Control layer hit:** A single aggregated read, proposed as `PartDemandDetailStruct` (extending the
existing `PartDemandStruct` used by the list view — same class family per
[shared_workflows.md §4](shared_workflows.md), not a second read path) assembling: the demand row
itself, current values of all four axes with last-transition timestamps, every active
`PurchaseOrderDemandLink` with its PO line's sibling-link and sibling-package context (§4 below),
and the full `PartDemandUpdate` journal. **Everything on this page comes from that one struct** —
no card issues its own query.

**Layout (2/3 + 1/3 top section, four cards below, one card at the bottom):**
- **Header card (2/3, left)** — every plain field on the row: part, quantity requested, priority,
  needed-by, requested by, domain, `source_module`, created/updated audit fields, primary actions
  (Cancel/Delete, permission-gated per D4; Edit button linking to §2.3 for anything else).
- **Four-axis status card (2/3, left, below header)** — all four axis values rendered large
  (current stage per dimension), each with its **last-update time small** beneath it. This is a
  glance card, not a history — one line per axis, no journal detail here (that's the four cards
  below).
- **Linked PO information (1/3, right)** — summary of every active allocation: PO number(s), line(s),
  quantity allocated, a link to each PO's detail page and to Edit & Linkage deep-linked to that
  line (same URL contract as §2.3's linkage row). Read only, same as §2.3.

**Four status-column cards, full width, one per axis (1/4 each side by side, collapsing to a 2×2
grid on narrow viewports):**

Each card shows the `PartDemandUpdate` history **for that one dimension only**, plus that
dimension's quantity indicator where one exists:

| Card | Qty indicator | Complexity to render |
| :--- | :--- | :--- |
| Demand | none | Plain history: `Projected`/`Required`/`Approved`/`Rejected`/`Cancelled`/`Completed` transitions |
| Purchasing | `purchased_qty` vs. `quantity_requested` | See shared-PO-line case below |
| Shipment | none directly (logistics stage, not a quantity) | Plain history of stage transitions |
| Issuance | `issued_qty` (net, D39) | Plain history — issuance has no cross-demand sharing concern |

**The shared-PO-line case (purchasing card):** per D28/`shared_demand_sessions.md`, if this
demand's PO line also carries other active `PurchaseOrderDemandLink` rows, the purchasing card must
show, not hide, that complexity — reuse the
[shared demand session component](shared_workflows.md#shared-demand-session-display) exactly as
specified there:
- The other demand IDs sharing the line, each with **its own** `quantity_requested` (what *they*
  demanded — a real number, distinct from what's allocated to them).
- The line's **total quantity demanded** across all active links (sum of `quantity_allocated`).
- The line's **total quantity purchased** — `quantity_ordered` on the line, the money-authorized
  figure everyone on the line shares.
- **Never** a per-demand purchased split when 2+ links are active — same rule as arrival, for the
  same reason: nobody decided whose money bought which unit.

**The shared-package case (also purchasing/shipment context):** if the PO line this demand is
allocated to has been shipped across multiple `Package`/`PackageLine` rows (partial shipments over
time, not multiple demands), show each package's line: package number, that `PackageLine`'s
quantity and status, and the **sum of `quantity_accepted` across every package line against this PO
line** as the line's total arrived — the same "least-advanced status wins" rule from
[package_workflows.md](package_workflows.md) governs which status the shipment card highlights as
current. This is orthogonal to the shared-demand-session case above — a PO line can have multiple
demands, multiple packages, or both at once, and both kinds of "more than one thing shares this
line" must render side by side, not merged into one number.

**Misc status updates — full width, table view, bottom of page:** the complete, unfiltered
`PartDemandUpdate` journal for this demand — every row, every dimension, chronological — as a plain
table (same shape as §2.3's history table). The four axis cards above are curated glance views
(current value + that axis's own history); this card is the ground truth they're drawn from, always
rendered in full so nothing the curated cards summarize or omit (e.g. `flagged_for_review` rows,
system-generated propagation rows) is ever hidden. Always renders, even with only the four creation
rows.

**Key things to note:**
- Nothing on this page writes. Every status change, every field edit, every linkage change is a
  link to §2.3 or Edit & Linkage — this page's job is showing the current, complete situation at
  a glance, including the cross-demand/cross-package complexity the legacy app's single-status view
  couldn't represent at all (gap_analysis.md gaps 5–6).
- The four-card-per-axis layout is a synthesis of this kit's request, not something specified in the
  starter kit's model docs — if the actual data shape makes one axis's card meaningfully emptier
  than the others (e.g. issuance before `app/inventory` ships), keep the card and its empty state
  per CLAUDE.md's "cards render even when empty" rule rather than collapsing the grid.

---

## 3. FK relationships → search apparatus

| FK | On | Rough pool size | Pattern | Why |
| :--- | :--- | :--- | :--- | :--- |
| `part` → `parts.Part` | Create-demand form | Hundreds–thousands | `<search-dropdown>` (searchbars.md: "pick one related record for a form field") | Single picked value, pool exceeds the >8-option threshold for a typeahead |
| `requested_by` → User | Create-demand form (only when reassigning on behalf of someone else — otherwise defaults to the logged-in user) | Tens–low hundreds | `<search-dropdown>` | Single value, form field |
| `domain` → `administration.Domain` | Create-demand form, edge case only | Usually 1, occasionally 2–3 for a multi-domain requester | Plain `<select>`, no search component | Well under the >8-option threshold that would justify a search-dropdown |

No dual listbox, no left-heavy assignment pair, and no wizard anywhere in this sector — `PartDemand`
has no reverse FK a user populates at creation (§ "Why this is a form and not a wizard" in
`create_demand.md`). Every search need here is a single-value pick into a form field.

**Deliberately no demand-search apparatus for PO linkage.** Even though allocation is conceptually
an FK relationship (`PartDemand` ↔ `PurchaseOrderLine` via `PurchaseOrderDemandLink`), no page in
this file builds a search/assign component for it — that apparatus (the left-heavy pair on the PO
wizard, the top-bottom tool on Edit & Linkage) lives entirely in
[purchase_order_workflows.md §3](purchase_order_workflows.md#3-fk-relationships--search-apparatus).
This sector only links out to it (§2.3, §2.4).

---

## 4. Card layout

### 2.1 Demand list — `/procurement/demands`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Filters | Full width | Priority, `demand_state`/`purchasing_state`/`shipment_state`/`issuance_state`, part, domain, needed-by date range. Plain HTMX inputs (`?format=htmx-search-results`), not search-dropdowns — this filters a list, it doesn't pick a value (`searchbars.md`) |
| Stat bar | Full width | Counts: open, pending approval, at-risk (`Backordered`), completed this period |
| Results table | Full width | One row per demand: part, qty requested, priority, needed-by, all four axis badges, quick link to detail |

### 2.2 Create demand — `/procurement/demands/create`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Demand identity | Full width (single-card form, no side rail — nothing to put there yet) | Part (`<search-dropdown>`), quantity requested, priority, needed-by, notes, serial-tracking-required checkbox |

### 2.3 Edit demand — `/procurement/demands/<id>/edit`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Demand fields | Full width | Same fields as create (§2.2), pre-filled: priority, needed-by, quantity requested, notes, serial-tracking-required. Standard card-footer save action |
| Linkage — read only | Full width | Active `PurchaseOrderDemandLink` rows: PO number, line, quantity allocated, "Edit linkage" link out to the [PO Edit & Linkage](purchase_order_workflows.md#24-procurementpurchase-ordersidedit--po-edit--linkage) pre-selected via `?line_id=<id>`. No link/de-link control here (D3) |
| Status update actions | Full width, small action row | One button per permitted axis, each opening a single-field-capture popup (target stage + notes): Advance shipment (Buyer), Approve/Reject (Approver, `approve` permission) — no purchasing action, per the Rules section (gap 7 resolved) |
| Status history | Full width, table | Every `PartDemandUpdate` row, all four dimensions, read-only |

### 2.4 Demand detail — `/procurement/demands/<id>`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Header | Left, main column (2/3) | Part, quantity requested, priority, needed-by, requested by, domain, audit fields, primary actions (Cancel/Delete permission-gated per D4; Edit → §2.3) |
| Four-axis status | Left, main column (2/3), below header | All four axis values, large, each with its last-update time small beneath — a glance row, no history detail. When `is_in_status_graph` is true, a small badge next to the purchasing/shipment values ("part of a linked network") signals that those two are graph-resolved, not locally computed — see the purchasing axis card |
| Linked PO information | Right, detail rail (1/3) | Active allocation summary: PO(s), line(s), qty allocated, links to PO detail and to Edit & Linkage (same deep-link contract as §2.3) |
| Demand axis card | Full width, 1 of 4 (1/4 width) | `PartDemandUpdate` history for `demand_state` only — no qty indicator |
| Purchasing axis card | Full width, 1 of 4 (1/4 width) | **Branches on `PartDemand.is_in_status_graph`** (`graph_association_visualizer.md` §5.2): **`False`** (the common case) → the per-link-then-combined one-hop formula from the Rules section — one line per active `PurchaseOrderDemandLink`, that link's PO status if its line covers everyone sharing it, else "Partial," shown singly or listed if there's more than one. **`True`** → the one-hop formula is not attempted at all; instead render the demand's stored `purchasing_state` as-is (the resolver writes the graph-derived value into that real column via `PartDemandStateManager.transition(...)` — [graph_association_visualizer.md](graph_association_visualizer.md) §5.6), labeled with `graph_resolved_at` ("network last resolved `<date>`") so staleness is visible, plus a prominent **"Resolve full network"** link into [graph_association_visualizer.md](graph_association_visualizer.md) seeded with this demand — clicking it re-runs the resolver and re-writes the state of every demand in the network, not only this one. Beneath either branch: `purchasing_state` history, `purchased_qty` vs. `quantity_requested`, and — per active link whose line is shared — that line's breakdown (other demand IDs, their qty requested, line's total qty demanded, line's total qty purchased) |
| Shipment axis card | Full width, 1 of 4 (1/4 width) | When `is_in_status_graph` is `False`: history for `shipment_state`; when the PO line has shipped across multiple packages, lists each `PackageLine`'s qty/status and the summed `quantity_accepted` (arrived) across them, per the "least-advanced status wins" rule. When `True`: the stored `shipment_state` rendered as-is with the same `graph_resolved_at` staleness framing as the purchasing card, its value written by the worst-of-every-package-in-the-network rollup ([graph_association_visualizer.md](graph_association_visualizer.md) §5.4) rather than only this demand's own packages |
| Issuance axis card | Full width, 1 of 4 (1/4 width) | History for `issuance_state`, `issued_qty` (net, D39) — no cross-demand sharing case |
| Misc status updates | Full width, below the four axis cards | The complete, unfiltered `PartDemandUpdate` table — every row, every dimension — always rendered even with only the four creation rows |

---

## 5. Open questions for the developer — all resolved

- ~~Saved-filter presets for the Approver's/Buyer's queues?~~ **Resolved: not right now.** A raw
  filter panel is sufficient for v1 — no named presets to build.
- ~~Does `record_issuance_and_return`'s read-only surface belong on this page before `app/inventory`
  ships?~~ **Resolved:** yes, build the read-only card now (empty state per CLAUDE.md's "cards
  render even when empty" rule); the eventual *write* path lives entirely on `app/inventory`'s
  future **Inventory Issuance Portal**, never on a form in this app.
- ~~gap 7 (no manual `purchasing_state` verb)~~ **Resolved, not blocking — see the Rules section
  above.** No verb is needed at all; purchasing status is fully derived from PO linkage, and the
  formula is specified there and in §2.4's purchasing axis card.
- ~~Should `approve`/`reject` be offered from both the edit page and a dedicated detail-page
  action?~~ **Resolved: edit page only.** Detail (§2.4) never carries its own approve/reject
  action — every status-changing action lives on the edit page, full stop; detail's header only
  keeps Cancel/Delete (D4) plus a link to Edit.
- ~~Is `PartDemandDetailStruct` actually a new class?~~ **Resolved: yes, a new struct** — build it
  as its own class rather than growing `PartDemandStruct` an optional detail projection.
