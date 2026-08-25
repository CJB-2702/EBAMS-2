---
okf_version: "0.1"
type: "Process Guide"
title: "Phase 2 — The Buying Loop"
description: "Build brief for the purchase order sector: the create-PO wizard (highest-traffic screen in the app), PO list and detail, Edit & Linkage, the new pre-purchase approval gate, and the D28 allocation-cap decision."
tags: [front-end-kit, procurement, build-plan, phase-2, purchase-order, wizard]
context_tier: 2
personas: [frontend, backend]
---

# Phase 2 — The Buying Loop

**Prerequisite: [Phase 0](phase_0_schema_and_shell.md) merged and migrated.** Runs in parallel with
Phases 1 and 3. Owns `app/procurement/presentation_layer/entrypoints/purchase_orders.py` and
`urls_purchase_orders.py`.

## Goal

A Buyer turns approved demand into a commercial order, gets it approved by a purchasing manager, and
places it. Per D44 this sector carries the **highest-traffic Buyer surfaces in the application** —
build these with the most care.

## Definition of done

- Four routes live (the fifth, `basic_package_manager`, belongs to Phase 3).
- The wizard commits nothing to the database until final submit.
- Approval gate enforced: `place` refuses unless `approval_state == Approved`.
- Self-approval permitted **and narrated**.
- Every page survives a plain reload; the wizard survives it with its draft intact.

---

## 1. Context to load

### The plan this implements

| Document | What to take from it |
| :--- | :--- |
| [../purchase_order_workflows.md](../purchase_order_workflows.md) | **Primary spec.** Actions (§1), four pages (§2), search apparatus (§3), card layout (§4) |
| [../shared_workflows.md](../shared_workflows.md) | §1 layout fractions (the 3/4+1/4 vs 2/3+1/3 distinction matters here), §2 attribution badges, §3 permissions, §4 reusable reads |
| [phase_0_schema_and_shell.md](phase_0_schema_and_shell.md) | **§4 the approval axis — new, not in the sector doc**; §5 permissions; §6 route names |

### Business rules

| Document | What it settles |
| :--- | :--- |
| [../../../procurement_starter_kit/purchase_ordering_system.md](../../../procurement_starter_kit/purchase_ordering_system.md) | PO/allocation mechanics. **Revision banner: its receiving mechanics are superseded by D55/D59** |
| [../../../procurement_starter_kit/control/create_purchase_order_wizard.md](../../../procurement_starter_kit/control/create_purchase_order_wizard.md) | Why it is a wizard; the session draft; vendor selection |
| [../../../procurement_starter_kit/control/purchase_order_line_editing.md](../../../procurement_starter_kit/control/purchase_order_line_editing.md) | Post-creation line edits with audit snapshots, allocation, de-linking |
| [../../../procurement_starter_kit/control/purchase_order_lifecycle.md](../../../procurement_starter_kit/control/purchase_order_lifecycle.md) | `place`, `close_out_shipment`, `cancel`, the typed event emitter |
| [../../../procurement_starter_kit/models/purchase_order.md](../../../procurement_starter_kit/models/purchase_order.md) · [purchase_order_line.md](../../../procurement_starter_kit/models/purchase_order_line.md) · [purchase_order_demand_link.md](../../../procurement_starter_kit/models/purchase_order_demand_link.md) | Columns; vendor is a `PartManufacturer` (D45); why there is no line status (D51) |
| [../../../procurement_starter_kit/decisions.md](../../../procurement_starter_kit/decisions.md) | D14, D28, D29, D42, D44, D45, D51–D53, D57, D58, D61, D67 |

### Code to read before writing

| Path | Why |
| :--- | :--- |
| [../../../app/procurement/control_layer/purchase_order_context.py](../../../app/procurement/control_layer/purchase_order_context.py) | Status verbs, plus Phase 0's new approval verbs |
| [../../../app/procurement/control_layer/adapters/purchase_order_draft_adaptor.py](../../../app/procurement/control_layer/adapters/purchase_order_draft_adaptor.py) | **The session draft — the wizard's entire state model** |
| [../../../app/procurement/control_layer/factories/purchase_order_factory.py](../../../app/procurement/control_layer/factories/purchase_order_factory.py) | `create_from_draft` — the single-transaction commit |
| [../../../app/procurement/control_layer/managers/purchase_order_line_manager.py](../../../app/procurement/control_layer/managers/purchase_order_line_manager.py) · [purchase_order_demand_link_manager.py](../../../app/procurement/control_layer/managers/purchase_order_demand_link_manager.py) · [purchase_order_cost_manager.py](../../../app/procurement/control_layer/managers/purchase_order_cost_manager.py) | Line editing, allocation, cost recompute |
| [../../../app/procurement/control_layer/domain_structs/purchase_order_fulfillment_struct.py](../../../app/procurement/control_layer/domain_structs/purchase_order_fulfillment_struct.py) | **One annotated read for the whole PO.** D67: every derived aggregate is a `Subquery` — never add a `Sum()` beside another multi-row join |
| [../../../app/procurement/presentation_layer/search/open_demand_search.py](../../../app/procurement/presentation_layer/search/open_demand_search.py) | The allocation pool, `domain_ids`-scoped |
| [../../../app/procurement/presentation_layer/tools/po_events/](../../../app/procurement/presentation_layer/tools/po_events/) | Emit on place. Nothing listens — that is intended |

### UX rules

[../../../harness/UX_UI/design_patterns/multi_step_flows.md](../../../harness/UX_UI/design_patterns/multi_step_flows.md) — **the wizard shape to apply, not redesign** ·
[search/left_heavy_assignment_card_pair.md](../../../harness/UX_UI/search/left_heavy_assignment_card_pair.md) ·
[search/list_management_patterns.md](../../../harness/UX_UI/search/list_management_patterns.md) ·
[design_patterns/modals.md](../../../harness/UX_UI/design_patterns/modals.md) ·
[navigation/tabs.md](../../../harness/UX_UI/navigation/tabs.md) ·
[form_style_guide.md](../../../harness/UX_UI/form_style_guide.md)

### Legacy visual reference — layout only, not data model

The prior Flask app at `/home/cb/REPOS/asset_management` shipped working versions of both hard
screens. Its **interaction layout** is useful; its **data model is not** (no line/allocation split,
no D28 cap, no permission gating).

| Old screen | Route | Templates |
| :--- | :--- | :--- |
| Purchasing portal | `GET /inventory/create-po` | `inventory/purchase_orders/create_from_part_demands.html` + `components/po_header_form.html`, `filters_section.html`, `search_results_table.html`, `parts_summary.html`, `add_unlinked_part_modal.html` |
| Linkage portal | `GET /inventory/purchase-order/<id>/link` | `inventory/purchase_orders/linkage_portal.html` |

---

## 2. Pages

### 2.1 `purchase_order_create` — the wizard

**One route, vertical scroll, progressive enablement, session-backed draft.** Nothing touches the
database until final submit. `PurchaseOrderDraftAdaptor` owns vendor, header fields, and a list of
lines each carrying its own `(demand_id, quantity_allocated)` pairs, entirely in `request.session`.

**Commit sequence, one transaction:** `PurchaseOrderFactory.create_from_draft` →
`PurchaseOrderLineManager.add_line` per line → `PurchaseOrderDemandLinkManager.allocate` per
allocation → `PurchaseOrderCostManager.recompute` → emit `PO_CREATED`.

**Cards, in scroll order:**

1. **Vendor & header** — vendor (`<search-dropdown>` over `parts.PartManufacturer`),
   `vendor_contact`, **`vendor_po_id`** (new, optional, buyer-entered), order date, expected delivery
   date, notes. Always enabled. **No create-vendor action** — a missing vendor is a `parts` app
   problem; link out (D45).
2. **Item selection** — a header-level two-option toggle (tabs or segmented control, **not a modal**)
   over **one shared running-lines table**:
   - **From demands** — top-heavy: filter row over a multi-select results table of open demands
     (`OpenDemandSearch`, domain-scoped), with "Add selected to lines". Selecting demands for a part
     both creates/updates that part's line **and** pre-populates card 3's allocation for exactly
     those demands.
   - **Unlinked** — a plain inline single-line add form (part, quantity, unit cost, optional dates
     and notes). **Not a modal** — the legacy app used one; this kit's modal rule forbids it here.
     Zero demands on a line is valid (D14); this is the intended path for it.
   - Enabled once a vendor is picked. Both tabs append to the same running table.
3. **Allocate demands** — **one card per line**, appearing as lines are added, not a fixed count.
   Left-heavy assignment pair: 2/3 filterable pool, 1/3 "allocated to this line" list with a quantity
   input per pick and a running total against `quantity_ordered`. Lines from the "From demands" tab
   arrive pre-populated and still editable; unlinked lines arrive empty. **Do not force at least one
   pick** (D14).
4. **Review & submit** — read-only summary, running `total_cost`. Submit is labeled
   **"Save as Draft"** — the PO opens as `Draft`, never `Placed` (D52), and now also opens as
   `approval_state = Unsubmitted`.

**The D28 cap decision.** The allocation cap is **per demand, never per line**. Exceeding it is
neither a silent success nor a flat refusal — it surfaces an explicit inline choice: *raise the
request* (with a strong warning) or *leave the excess unallocated*. **Build it once as a modal
component and reuse it at all three call sites** (wizard card 3, PO detail's inline editor, Edit &
Linkage). A modal is correct here — it is a one-shot confirmation on a single pending allocation,
not the assignment interaction itself.

**D42's auto-approve** happens silently unless the Buyer opts out via a checkbox on card 3. Build
that opt-out.

**Promotion note:** the sector doc flags this wizard for promotion to its own `key-workflows/`
document. If enablement conditions, draft keys, abandonment, or failure handling turn out
under-specified while building, write that document rather than improvising — see
[../../../harness/front_end_kit_process/](../../../harness/front_end_kit_process/index.md).

### 2.2 `purchase_order_detail` — `/procurement/purchase-orders/<id>`

Work portal (3/4 + 1/4). Owns **per-line editing** and **every status action**. Header fields and
full linking sessions belong to §2.4.

One read: `PurchaseOrderFulfillmentStruct` — lines, allocations, packages, the four quantities,
per-line attribution mode. **One annotated query, not one per line.**

**Status and approval actions on the hero:**

| Action | Permission | Guard |
| :--- | :--- | :--- |
| Submit for approval | `buy` | `approval_state == Unsubmitted` |
| Approve / Deny | `purchase_approve` | `approval_state == Pending Approval` |
| Place | `buy` | **`approval_state == Approved`** |
| Mark received | `buy` | Explicit human act, never a quantity match (D29) |
| Cancel order | `buy` | Rare — design for correctness |

Deny and Cancel are reachable directly from either non-terminal approval state. `Approved` is not
revocable through this axis — cancel through `status` instead.

**Self-approval is legal.** When the approving actor is the PO's creator, the narrator posts a
machine comment recording it. Permit, record, never block.

**D57 — editing a placed order is a soft warning, never a block.** Line-edit controls stay fully
interactive after `Placed`. Show a warning banner above the lines table; **never disable inputs**.
Every mutation writes an audit-snapshot machine comment.

Cards: Header/hero · Lines table (2/3) · Packages (2/3, with "Manage packages" → Phase 3's
`basic_package_manager`) · Allocation editor expanding per line (2/3) · Placed-order warning banner ·
Cost summary (1/3) · Status & quick facts (1/3, with a `?po_id=` link to Phase 4) · Event/activity
thread (1/3, always renders). Full contents in
[../purchase_order_workflows.md](../purchase_order_workflows.md) §4.

### 2.3 `purchase_order_index` — `/procurement/purchase-orders`

Search/list. Filters: **approval state** (new), status, vendor, domain, date range, part. Results
carry a linkage-status badge per row (unlinked / partially linked / fully linked), computed from the
struct — **never a per-row query**.

Stat bar: pending approval · draft · placed · partially received · received this period.

### 2.4 `purchase_order_edit` — PO Edit & Linkage

The renamed Linkage Portal (`/link` → `/edit`), now with a real header edit form on top.

**Layout:**
- **Top row, full width — an edit form:** vendor, `vendor_contact`, `vendor_po_id`, order date,
  expected delivery date, notes. Standard card-footer save. PO number and both status badges render
  read-only — **status changes happen through their own actions on §2.2, not this form.** A header
  edit on a placed-or-later PO posts a pre-edit snapshot machine comment, same shape as a line edit.
- **Left column (1/3):** every line as a selectable row — part, qty ordered, allocated/pending,
  linkage badge. Nothing on the right is interactive until a line is selected. **No line is ever
  unselectable**, including fully-linked ones.
- **Right column (2/3), on selection:** current links for that line, each with a **De-link** action ·
  then a **top-bottom** demand search tool (filter bar over a results list, each row carrying a
  **Link** action). Top-bottom, **not** the left-heavy pair — the target here is a current-links
  list, not a running multi-pick build-up.

**URL parameters — Tier 1 rule, not optional:**

| Param | Effect on load |
| :--- | :--- |
| `?line_id=<id>` | Pre-selects that line and populates the right column exactly as a click would. **This is how Phase 1's demand pages deep-link in** |
| `?part_id=<id>` | Pre-fills the search tool's part filter |
| `?q=`, other `OpenDemandSearch` params | Standard list filters |

Selecting a line is a client-side interaction but **must round-trip through the URL**
(`hx-push-url`) so a reload or bookmark reproduces the selection. The legacy app used client-only
selection with no URL sync — do not repeat that.

---

## 3. Search apparatus

| FK | Where | Pattern |
| :--- | :--- | :--- |
| `vendor` → `parts.PartManufacturer` | Wizard header | `<search-dropdown>` |
| `part` per line | Wizard line-add rows | `<search-dropdown>` |
| Demand allocation | Wizard card 3, PO detail's inline editor | **Left-heavy assignment card pair** — 2/3 pool with its own filters, 1/3 target with a quantity input per pick |
| Demand allocation | Edit & Linkage right column | **Top-bottom search tool** — one-at-a-time linking against a selected line |
| Domain | — | Not a picker. The PO's own `domain` (D61) scopes the search |

**No dual listbox.** The candidate pool runs into the hundreds systemwide, past the few-dozen ceiling
where dual listbox degrades. The left-heavy pair is the only pattern in the family built for a
large, independently-filterable pool with per-pick metadata.

---

## 4. Permission gates — this wave installs them for the first time

| Rule | Where |
| :--- | :--- |
| `buy` gates PO create, edit, line editing, submit-for-approval, place, cancel | Every entrypoint above |
| `purchase_approve` gates approve/deny | §2.2 hero only |
| D3 — allocation is Buyer-only | `allocate` and `delink`, all three call sites |
| D5 — domain scoping | Every list and every `OpenDemandSearch` call |
| **D2's clause is retired** | An `approve`-only holder can **no longer** place an order |

Cross-domain: a demand on this PO belonging to another domain renders its identifying data as plain
text with **no link through** to Phase 1's demand detail.

---

## 5. Out of scope

- Package creation and the Basic Package Manager (Phase 3), though PO detail links to both.
- Any PO document, PDF, print view, or vendor transmission. `place` emits a typed signal; nothing
  listens. Extensions come later.
- Cost-threshold approval rules — deferred tech debt.
- A per-part "confirm price" gate. Unit cost is a normal required field on card 2, not a ritual.
- Line-level status. There is none (D51).
</content>
