---
okf_version: "0.1"
type: "Process Guide"
title: "Phase 1 — The Demand Loop"
description: "Build brief for the part demand sector: list, create, edit, and detail pages, the four-axis display, the derived purchasing-coverage formula, and the first real permission gates."
tags: [front-end-kit, procurement, build-plan, phase-1, part-demand]
context_tier: 2
personas: [frontend, backend]
---

# Phase 1 — The Demand Loop

**Prerequisite: [Phase 0](phase_0_schema_and_shell.md) merged and migrated.** Runs in parallel with
Phases 2 and 3. Owns `app/procurement/presentation_layer/entrypoints/demands.py` and
`urls_demands.py` — no other wave's files.

## Goal

A Requester can ask for material and track it. A floor manager can approve, reject, and correct.
Everyone with domain access can see where a demand stands across all four axes.

Useful standalone: this wave depends on nothing from Phases 2 or 3, and its pages degrade honestly
when no PO or package exists yet.

## Definition of done

- Four routes live, replacing their `NotBuiltYetView` placeholders.
- Every page works on a plain full-page reload with JavaScript disabled (F5 rule).
- Permission gates from Phase 0 §5 enforced at the entrypoint, not the template alone.
- Every list query is domain-scoped.
- Cross-domain PO references render as plain text with no link through.

---

## 1. Context to load

### The plan this implements

| Document | What to take from it |
| :--- | :--- |
| [../part_demand_workflows.md](../part_demand_workflows.md) | **Primary spec.** Actions table (§1), all four pages (§2), search apparatus (§3), card-by-card layout (§4) |
| [../shared_workflows.md](../shared_workflows.md) | §1 layout fractions, §2 the shared-demand-session component, §3 permission enforcement, §4 reusable reads |
| [phase_0_schema_and_shell.md](phase_0_schema_and_shell.md) | §5 permission vocabulary, §6 the route names this wave fills in |

### Business rules — do not re-derive these

| Document | What it settles |
| :--- | :--- |
| [../../../procurement_starter_kit/part_demand_system.md](../../../procurement_starter_kit/part_demand_system.md) | **Authoritative** four-axis state model |
| [../../../procurement_starter_kit/control/create_demand.md](../../../procurement_starter_kit/control/create_demand.md) | Why creation is a simple form and not a wizard |
| [../../../procurement_starter_kit/control/part_demand_lifecycle.md](../../../procurement_starter_kit/control/part_demand_lifecycle.md) | `approve`, `reject`, `cancel`, `delete`, the three gates |
| [../../../procurement_starter_kit/models/part_demand.md](../../../procurement_starter_kit/models/part_demand.md) | Columns, enums, indexes |
| [../../../procurement_starter_kit/models/part_demand_update.md](../../../procurement_starter_kit/models/part_demand_update.md) | The append-only journal — never editable |
| [../../../procurement_starter_kit/shared_demand_sessions.md](../../../procurement_starter_kit/shared_demand_sessions.md) | **Read before rendering any arrival quantity.** When per-demand arrival has an answer and when it does not |
| [../../../procurement_starter_kit/po_demand_association_graph.md](../../../procurement_starter_kit/po_demand_association_graph.md) | §2 — the corrected per-link purchasing-coverage formula |
| [../../../procurement_starter_kit/decisions.md](../../../procurement_starter_kit/decisions.md) | D6, D9–D11, D15, D28, D42, D44, D70 |

### Code to read before writing

| Path | Why |
| :--- | :--- |
| [../../../app/procurement/control_layer/part_demand_context.py](../../../app/procurement/control_layer/part_demand_context.py) | Every write verb this wave calls |
| [../../../app/procurement/control_layer/domain_structs/part_demand_struct.py](../../../app/procurement/control_layer/domain_structs/part_demand_struct.py) | The read this wave extends |
| [../../../app/procurement/presentation_layer/search/open_demand_search.py](../../../app/procurement/presentation_layer/search/open_demand_search.py) | Already takes `domain_ids` — start calling it |
| [../../../app/procurement/control_layer/domain_structs/purchase_order_fulfillment_struct.py](../../../app/procurement/control_layer/domain_structs/purchase_order_fulfillment_struct.py) | The only legitimate source of any "how much arrived" figure |
| [../../../app/parts/presentation_layer/entrypoints/parts.py](../../../app/parts/presentation_layer/entrypoints/parts.py) | Reference entrypoint style for this project |
| [../../../app/parts/templates/parts/](../../../app/parts/templates/parts/) | Reference template structure, list/detail/form shells |

### UX rules

[../../../harness/UX_UI/page_structure.md](../../../harness/UX_UI/page_structure.md) ·
[form_style_guide.md](../../../harness/UX_UI/form_style_guide.md) ·
[design_patterns/modals.md](../../../harness/UX_UI/design_patterns/modals.md) ·
[search/searchbars.md](../../../harness/UX_UI/search/searchbars.md) ·
[components/search_dropdown.md](../../../harness/UX_UI/components/search_dropdown.md)

---

## 2. Pages

### 2.1 `demand_index` — `/procurement/demands`

Search/list shell: full-width filters, full-width results, no right rail.

- **One canonical list**, not three. The Approver's queue is `?demand_state=required`; the Buyer's
  "what needs buying" view is a sparse `purchasing_state` filter. Saved presets are explicitly **not**
  in scope.
- Default sort is `priority` then `needed_by`. Do not let a "newest first" default creep in.
- `Backordered` and `Partially Issued` are everyday states (D44) — their badges must read as normal,
  not alarming.
- Read through `OpenDemandSearch` with `domain_ids`, annotating outstanding quantity and all four
  axis values **in the query**. Never per row.

Cards: Filters · Stat bar · Results table. Full contents in
[../part_demand_workflows.md](../part_demand_workflows.md) §4.

### 2.2 `demand_create` — `/procurement/demands/create`

Simple form, single card. `PartDemand` has zero qualifying reverse FKs — **not** a wizard.

- `PartDemandCreateAdaptor` → `PartDemandFactory.create()` → `PartDemandStateManager` writes four
  initializing journal rows.
- **`domain` is not a form field** in the normal case — resolved from the requester's own assignment.
  Render a picker only when the requester holds more than one domain.
- Requires the `request` permission.
- Resist adding sections. This stays short on purpose.

### 2.3 `demand_edit` — `/procurement/demands/<id>/edit`

Full width, no rail. **This is where every status-changing action lives** — detail never duplicates
them.

Four cards:

1. **Demand fields** — same field set as create, pre-filled. Standard card-footer save. Requires
   `request` (own demand) or `demand_manage` (any demand in domain).
2. **Linkage — read only** — active `PurchaseOrderDemandLink` rows: PO number, line, quantity
   allocated. Each row's "Edit linkage" action deep-links to
   `purchase_order_edit` with `?line_id=<id>`. **No link/de-link control here** — allocation is
   Buyer-only (D3) and lives in Phase 2. **Cross-domain PO renders as plain text, no link.**
   Empty state: "Not linked to a purchase order line yet."
3. **Status update actions** — a small action row, not a form. One button per axis the actor may
   move, each opening a single-field-capture modal (target stage + optional notes):
   - **Approve / Reject** — `demand_manage`. Notes are optional (D15) — do not add a client-side
     required mark the backend does not enforce.
   - **Advance shipment** — `buy`.
   - **Issuance** — `request` (own) or `demand_manage`. Sets the new
     reconciliation-required state; the backwards `Issued → Pending` move is legal here too.
     **Records no quantity** — the point is that the movement is unreconciled, so any number would be
     a claim rather than a record. `issued_qty` stays untouched until the future Inventory Issuance
     Portal confirms it.
   - Modals are correct here per [modals.md](../../../harness/UX_UI/design_patterns/modals.md) —
     single-field capture. Do not build these as inline expanding cards.
4. **Status history** — full-width table, every `PartDemandUpdate` row, all four dimensions,
   read-only. Never editable.

**No purchasing-status action exists.** Purchasing status is derived entirely from PO linkage — see
§3 below.

### 2.4 `demand_detail` — `/procurement/demands/<id>`

Work portal (3/4 + 1/4). **Nothing on this page writes.** Every mutation is a link to §2.3.

One aggregated read: build **`PartDemandDetailStruct`** as a new class in the `PartDemandStruct`
family — the row, all four axis values with last-transition timestamps, every active link with its
sibling-link and sibling-package context, and the full journal. **No card issues its own query.**

Layout: Header (2/3) · Four-axis glance card (2/3, below header) · Linked PO information (1/3 rail) ·
then four full-width axis cards at 1/4 each, collapsing to 2×2 on narrow viewports · then the
unfiltered journal table at the bottom.

Card-by-card contents: [../part_demand_workflows.md](../part_demand_workflows.md) §4.

**Header actions:** Cancel and Delete only, plus a link to Edit. Cancel must **not render** for a
`buy`-only holder (D4) — not disabled, absent. Delete's confirmation copy differs depending on
whether the row is a hard delete or a deactivation (D6) — **ask the control layer first**, the page
cannot assume which.

The issuance axis card renders and stays largely empty in this build — keep it with its empty state
per the cards-render-when-empty rule; do not collapse the grid.

---

## 3. The derived purchasing-coverage display

The single most error-prone thing in this wave. Do not invent it — implement exactly this.

**Never read `purchasing_state` and print it.** The displayed purchasing status is **derived from PO
linkage**, evaluated **per link, then combined**:

- **No active link** → show the stored state as-is (normally unset — "not yet purchased").
- **For each active link**, independently: compare that PO line's `quantity_ordered` against the
  **sum of `quantity_requested` across every demand actively linked to that same line**. If
  `quantity_ordered >= sum`, the contribution is that line's PO status. If less, the contribution is
  **"Partial"**.
- **"Partial" is a display label, never an enum value.** `PurchasingState` is untouched.
- **Combine:** one link → *"mirrors PO 4021: Purchased"*. Two or more → each shown separately —
  *"PO 4021 (Purchased) covers one line; PO 4030 is Partial on the other"*. **Never collapsed into
  one status for the whole demand.**
- **One hop plus one.** This reads the demand's own links and those links' direct co-demands. It
  never traverses further, no matter how large the network. The full transitive view is Phase 4's
  page only.

**The shared-PO-line case:** when a link's line carries other active links, the purchasing card must
show that complexity, not hide it — the other demands' own `quantity_requested`, the line's total
allocated, and the line's total ordered. **Never a per-demand purchased split when 2+ links are
active.** Reuse the component in [../shared_workflows.md](../shared_workflows.md) §2 verbatim.

**The shared-package case** is orthogonal and can co-occur: a line shipped across several packages
shows each package line's quantity and status plus the summed `quantity_accepted`, under the
least-advanced-status-wins rule. Both cases must render side by side, never merged into one number.

**D42's auto-approve must be visible, not hidden.** Linking a demand to a PO line auto-approves it
by default. The page shows *why* it moved to `Approved` without an Approver action — a
system-generated journal row with the linking Buyer as actor. This is not a bug; do not "fix" it in
the UI.

---

## 4. Search apparatus

| FK | Where | Pattern |
| :--- | :--- | :--- |
| `part` → `parts.Part` | Create form | `<search-dropdown>` |
| `requested_by` → User | Create form, only when raising on someone's behalf | `<search-dropdown>` |
| `domain` | Create form, multi-domain requester only | Plain `<select>` |

**No dual listbox, no assignment pair, no wizard anywhere in this wave.** Every search need is a
single-value pick into a form field. The demand-allocation apparatus belongs to Phase 2 — this wave
only links out to it.

---

## 5. Blocked-action messaging

The three gates (D9/D10/D11) are already enforced server-side. **The UI's job is rendering why.** A
cancel refused because a linked PO is still active must **name that PO**, not show a generic error.

---

## 6. Out of scope

- Any allocation or de-linking control (D3 — Phase 2).
- Any manual purchasing-status action (derived, see §3).
- Saved filter presets.
- `complete_demand_rollup` as a button — it is system-derived. Show the resulting state.
- The issuance **write** path beyond the reconciliation flag — `record_issuance_and_return` belongs
  to `app/inventory`'s future Issuance Portal, never to a form in this app.
- Notification or inbox behavior of any kind. The pull model is deliberate.
</content>
