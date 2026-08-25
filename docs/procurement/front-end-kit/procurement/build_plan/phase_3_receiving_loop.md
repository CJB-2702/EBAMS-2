---
okf_version: "0.1"
type: "Process Guide"
title: "Phase 3 — The Receiving Loop"
description: "Build brief for the package sector: the forward-looking Basic Package Manager, the new PO-less reactive receive path, package detail with its own Event, Edit & Linkage with the absorbed splitting tool, and the package list."
tags: [front-end-kit, procurement, build-plan, phase-3, package, receiving]
context_tier: 2
personas: [frontend, backend]
---

# Phase 3 — The Receiving Loop

**Prerequisite: [Phase 0](phase_0_schema_and_shell.md) merged and migrated** — this wave depends on
five of its nine schema changes and cannot start without them. Runs in parallel with Phases 1 and 2.
Owns `app/procurement/presentation_layer/entrypoints/packages.py` and `urls_packages.py`, plus the
`basic_package_manager` route declared in `urls_purchase_orders.py`.

## Goal

A Buyer plans a PO's expected shipments before they arrive. Receiving staff log what actually turned
up — **with or without a purchase order** — and record what survived inspection.

Per D44 this is the **highest-volume surface overall**, ideally machine-fed rather than typed. Build
for speed of entry.

## Definition of done

- Five routes live.
- The Basic Package Manager's lock rule (D69) enforced in the UI **and** re-checked in the submit
  handler.
- A package can be received with no PO, carrying a domain, and attached to a PO later with automatic
  line linking.
- Package comments, files, and photos render from the package's **own** Event.
- Intake never appears anywhere: no bin, no location, no put-away, no stock level.

---

## 1. Context to load

### The plan this implements

Read the `packages/` subfolder **first** — where it disagrees with `package_workflows.md`, the
subfolder is newer and wins.

| Document | What to take from it |
| :--- | :--- |
| [../packages/basic_package_manager.md](../packages/basic_package_manager.md) | §2.5's full spec — drag-and-drop, session seeding, **the D69 lock rule**, the all-or-nothing submit handler, five worked scenarios |
| [../packages/package_edit_and_linkage.md](../packages/package_edit_and_linkage.md) | `packages/<id>/edit` — header edit, master-detail assignment, line and package CRUD, the create→edit redirect |
| [../packages/package_comments_and_files.md](../packages/package_comments_and_files.md) | §2 narration rules, §3 the revised detail-page card layout, §"Reference implementation" |
| [../package_workflows.md](../package_workflows.md) | Sector actions (§1), the list page (§2.4), search apparatus (§3). **Its §2.1–§2.3 are superseded by the three above** |
| [../shared_workflows.md](../shared_workflows.md) | §1 layout fractions, §2 the arrival component, §3 permissions |
| [phase_0_schema_and_shell.md](phase_0_schema_and_shell.md) | §3 schema (five changes land here), §5 permissions, §6 route names |

### Business rules

| Document | What it settles |
| :--- | :--- |
| [../../../procurement_starter_kit/control/package_lifecycle.md](../../../procurement_starter_kit/control/package_lifecycle.md) | `create_package`, `advance_package_status`, `inspect_and_accept_package_line`, splitting, `derive_demand_arrival`. **Its "machine comment on the PO's Event" language is retargeted by D68** |
| [../../../procurement_starter_kit/models/package.md](../../../procurement_starter_kit/models/package.md) | Columns, `mixed_po_assignments`, what replaced the legacy link table |
| [../../../procurement_starter_kit/shared_demand_sessions.md](../../../procurement_starter_kit/shared_demand_sessions.md) | **Read before rendering any "how much arrived" figure** |
| [../gap_analysis.md](../gap_analysis.md) | What the legacy `ArrivalHeader`/`ArrivalLine` did and why the link table is gone |
| [../../../procurement_starter_kit/decisions.md](../../../procurement_starter_kit/decisions.md) | D55, D57, D58, **D59 (reversed by Phase 0)**, D60, D67, **D68, D69** |

### Code to read before writing

| Path | Why |
| :--- | :--- |
| [../../../app/procurement/control_layer/package_context.py](../../../app/procurement/control_layer/package_context.py) | Read + status advance, plus Phase 0's new `attach_purchase_order` and `delete` |
| [../../../app/procurement/control_layer/factories/package_factory.py](../../../app/procurement/control_layer/factories/package_factory.py) | Phase 0 made `purchase_order_id` optional and `domain` required |
| [../../../app/procurement/control_layer/managers/package_line_manager.py](../../../app/procurement/control_layer/managers/package_line_manager.py) | Add, accept, quantity changes |
| [../../../app/procurement/control_layer/managers/package_status_manager.py](../../../app/procurement/control_layer/managers/package_status_manager.py) | Status advance |
| [../../../app/procurement/control_layer/handlers/package_line_split_handler.py](../../../app/procurement/control_layer/handlers/package_line_split_handler.py) | Splitting — and it now maintains `has_splits` |
| [../../../app/procurement/control_layer/guards/package_state_guard.py](../../../app/procurement/control_layer/guards/package_state_guard.py) · [package_line_guard.py](../../../app/procurement/control_layer/guards/package_line_guard.py) | The refusal reasons the UI must render |
| [../../../app/procurement/presentation_layer/search/purchase_order_line_search.py](../../../app/procurement/presentation_layer/search/purchase_order_line_search.py) | The candidate-line lookup for assignment |
| [../../../app/procurement/control_layer/domain_structs/purchase_order_fulfillment_struct.py](../../../app/procurement/control_layer/domain_structs/purchase_order_fulfillment_struct.py) | Arrival attribution. **D67 — correlated subqueries, never a `Sum()` beside another join** |
| [../../../app/events/templates/events/fragments/](../../../app/events/templates/events/fragments/) | `event_card.html`, `comments_card.html`, `files_card.html`, `gallery_card.html` — **do not reimplement these** |
| `/events/kitchen-sink` (running app) | All four fragments exercised against real data |

### UX rules

[../../../harness/UX_UI/search/list_management_patterns.md](../../../harness/UX_UI/search/list_management_patterns.md) — §7 search-row-cards, the assignment tool's shape ·
[search/search_row_cards_pattern.md](../../../harness/UX_UI/search/search_row_cards_pattern.md) ·
[design_patterns/modals.md](../../../harness/UX_UI/design_patterns/modals.md) ·
[design_patterns/multi_step_flows.md](../../../harness/UX_UI/design_patterns/multi_step_flows.md) — the session-draft pattern the manager borrows ·
[file_management/file_upload_markup.md](../../../harness/UX_UI/file_management/file_upload_markup.md) ·
[components/file_upload.md](../../../harness/UX_UI/components/file_upload.md)

---

## 2. Rules that must hold

- **Intake is a hard boundary.** No storeroom, bin, location, or "put into stock" control belongs
  anywhere in this sector. The last verb here is **accept**.
- **`quantity_accepted` is a quantity, not a checkbox.** Partial acceptance (8 good, 2 damaged) is a
  number. **`null` (uninspected) must be visually distinct from `0` (inspected, all rejected)** — do
  not default the input to 0.
- **The copy-on-create link is a default, not a binding.** When exactly one active PO line matches a
  part, the link is auto-resolved at creation. Render it as **already assigned and editable**, not as
  an empty field awaiting input.
- **`mixed_po_assignments` is a flag, not a constraint.** Surface it as a banner and a first-class
  list filter. **Never block an action because of it.** On a PO-less package it stays `False`.
- **A demand behind several packages takes the least-advanced status.** The temptation to show the
  most advanced (it looks more optimistic) is the wrong answer.
- **Splitting produces rows, it does not adjust a join.** Each split creates a new `PackageLine` with
  its own quantity and reduces the original. There is no "quantity linked" field to edit.

---

## 3. Pages

### 3.1 `basic_package_manager` — `/procurement/purchase-orders/<id>/basic-package-manager`

**Forward-looking.** This is a Buyer planning a PO's *expected* boxes from a vendor's shipping
confirmation — not a receiver with a carton in hand. That job is §3.3.

Session key: `basic_package_session`. Full spec in
[../packages/basic_package_manager.md](../packages/basic_package_manager.md); the essentials:

- **Layout:** PO info strip (full width) · PO lines column (left 1/3, draggable chips showing qty
  ordered / already packaged / remaining) · package workspace (right 2/3, create-package form on top
  then one card per package).
- **The create-package form writes nothing** — it appends a session-only card with a temporary id.
- **Drag-and-drop is the fast path, never the only path.** Every gesture has an explicit equivalent:
  a per-chip `<select>` ("Assign to: …") posting a plain form. F5 rule.
- **The D69 lock rule.** On load, seed the session from the database, then outline each card:

  | Outline | Condition | Meaning |
  | :--- | :--- | :--- |
  | **Green** | status before `Delivered to Local Receiving Location` **and** `has_splits` is `False` | Fully editable |
  | **Red — locked** | status is `Delivered to Local`/`Accepted` **or** `has_splits` is `True` (either alone) | Read-only. No drop zone, no chips, no inline edits. One action: "Edit this package" → §3.4 |
  | none | session-only, not yet real | Nothing to lock |

  `Lost` is **not** a lock trigger on its own. Locked cards still render, and their lines still count
  toward "already packaged" totals, so the Buyer sees the whole picture.

- **Submit is owned end to end by one proposed class, `BasicPackageManagerSubmitHandler`** — not a
  view function stitching calls together. It takes the whole payload, re-derives seeded state from
  the database (never trusts client-echoed "original" state), validates **everything** before writing
  **anything**, then commits in one transaction.
- **All-or-nothing, explicitly.** Any validation or transaction failure rejects the entire
  submission — nothing written, not even the individually-fine parts. The session draft survives
  untouched and the page re-renders with errors keyed to the package or line that tripped them. A
  partial commit would leave the Buyer unsure which of several decisions landed.
- **On success:** redirect to PO detail with a summary flash — packages created, packages modified,
  lines moved.

**Because of the lock rule, this page needs no audit-note capture, no pending-note session state, no
submit-time diffing against a locked package, and no dual-Event posting.** All of that lives on §3.4.

### 3.2 `package_create` — `/procurement/packages/create`

Simple form with an embedded line table. **Not a wizard** — `Package` has exactly one reverse FK a
user populates at creation and no secondary signal pushes it over the trigger.

- **Submit redirects to `package_edit`**, not detail — a fresh package is mid-setup, which is that
  page's job.
- **Steering banner, twice:** at the top and beside the submit button, nudging toward the Basic
  Package Manager when a PO context is available. A nudge, **not a gate** — this form must work end
  to end.
- No line-level demand picker. That is the point of the copy-on-create default.

### 3.3 `package_receive` — `/procurement/packages/receive` (new)

**The reactive path: a box arrived and there is no purchase order.** Nothing in the original kit
served this; Phase 0's nullable `purchase_order` makes it possible.

- **Domain is mandatory and is the point.** Whoever accepts a shipment has a domain to assign it to.
  Default to the receiver's own domain; render a picker only when they hold more than one.
- Fields: domain, `shipment_id`, carrier, shipped/expected dates, notes, plus the same line table as
  §3.2 (part + quantity).
- **No PO field.** Attachment happens later on §3.4.
- Lines land with `purchase_order_line = null`. That is correct, not an error state.
- Entry point: the hub's "Receive a shipment" card and the topnav's Receiving group.
- Requires `receive`.

### 3.4 `package_edit` — `/procurement/packages/<id>/edit`

The package sector's mirror of Phase 2's Edit & Linkage, inverted: it links **this package's lines**
to **PO lines**, potentially across several vendors' open orders. **This absorbs the old
line-splitting wizard route entirely** — do not build
`/packages/<id>/lines/<line_id>/split`.

- **Header edit form** (full width, top): `shipment_id`, carrier, shipped date, expected arrival
  date, notes. **Not status** — status advance lives on the view page.
- **Attach a purchase order** (new, this phase): for a PO-less package, a PO `<search-dropdown>` on
  the header form. On attach, **auto-link every unlinked line to the PO line whose part matches**.
  No match, **or more than one matching active line**, leaves that line unlinked. Safe failure —
  never guess.
- **Items column** (left 1/3): every `PackageLine`, selectable, with part, quantity, current
  assignment or "unassigned", split-lineage indicator, a small **Delete** per row, and **"+ Add
  line"** above the list.
- **PO search & select** (right 2/3, on selection): candidate PO lines with `qty_ordered`,
  `qty_from_accepted_packages`, and outstanding balance — enough context to judge before assigning.
  An **Assign** per result calls `PackageLineSplitHandler` (a split when partial, a reassignment when
  the full remaining quantity).
- **URL parameters:** `?line_id=<id>` pre-selects a line — this is how package detail's per-line
  "Edit assignment" deep-links in. Selection round-trips through the URL via `hx-push-url`.
- **CRUD:** add line (modal — single-field capture, with an optional inline assign reusing the
  right column's component); delete line (small, confirmed, soft delete — stronger warning when
  split lineage exists, but **never blocked**); delete package (small, secondary, on the header
  card's footer, **mandatory reason always**, soft delete, warn plainly when any line carries a
  non-null `quantity_accepted`).
- **This is the only page that can mutate a delivered or split package.** Every such mutation opens a
  single popup capturing a **mandatory human comment**, and the write posts that comment plus a JSON
  pre-state snapshot to the package's own Event **in the same request**. One mutation at a time — no
  batching, no deferral, no supersession logic.
- **No drag-and-drop here.** This page's job is "find the right PO line for this one arriving line" —
  a search problem, not a sorting problem.

### 3.5 `package_detail` — `/procurement/packages/<id>`

Work portal (3/4 + 1/4). Where status is advanced and lines are inspected and accepted.

**Advance status** is a `<select>` constrained to the **currently legal next stage(s)** — in practice
one option, plus `Lost` where the branch applies. Not a full stepper control, not jump-to-any-stage.

**Card layout** per [../packages/package_comments_and_files.md](../packages/package_comments_and_files.md) §3:

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Header / hero | Full width | Package number, `shipment_id`, carrier, status badge, Advance status (`receive`) |
| Mixed-assignment banner | Full width, conditional | Non-blocking notice naming the divergent lines |
| Lines table | Left 2/3 | Part, quantity, `quantity_accepted` (inline accept input + rejection notes), assigned PO line, split lineage, **"Attributed to" column** (see below), "Edit assignment" → §3.4 via `?line_id=` |
| Comments | Right 1/3 | The package's **own** Event stream — status machine comments, audit comments (JSON snapshots rendered collapsed, never raw in the feed), human comments, add-comment form |
| Files | Right 1/3 | `files_card.html` — shipping PDFs, customs forms |
| Photos | Right 1/3 | `gallery_card.html` — in-transit and condition photos |
| Primary PO / quick facts | Right 1/3 | PO link (or "No purchase order attached" with a link to §3.4), vendor, dates, `?package_id=` link to Phase 4 |
| Status history | Right 1/3 | Stepper. Keep it **alongside** the comments card — glance position vs. narrated why. Do not merge them |

**Build the three Event cards from the existing fragments.** `event_card.html` already composes
`comments_card.html`, `files_card.html`, and `gallery_card.html`; split them into three cards for
this layout rather than writing anything new.

**Removed:** the old "PO event thread (filtered)" card. The package has its own Event now.

**The arrival display is a column, not a card.** The sector doc specced a standalone "Demand arrival
for this package's lines" card. Fold it into the lines table as an **"Attributed to"** column
instead: the demand reference when the chain is 1:1:1, a "shared session (N)" chip that expands
otherwise, blank when unlinked. Same component, same rule
([../shared_workflows.md](../shared_workflows.md) §2), one less card — and on a PO-less package the
standalone card would be entirely empty on every row, which reads as broken rather than as
"nothing is claimed yet."

**Never fabricate a per-demand split when a PO line carries 2+ active demand links.** A session total
and member list, or nothing. Not even labeled as an estimate.

### 3.6 `package_index` — `/procurement/packages`

Search/list. Filters: status, vendor (via PO), **`mixed_po_assignments`** (the drift review queue — a
first-class filter, not buried), **`shipment_id`** (receivers search by what is printed on the box),
**"no purchase order"** (new), date range.

Stat bar: awaiting shipment · in transit · delivered · drift-flagged · **unattached**.

---

## 4. Search apparatus

| FK | Where | Pattern |
| :--- | :--- | :--- |
| `purchase_order` | Standalone create; the new attach action on §3.4 | `<search-dropdown>` filtered to open statuses |
| `part` per line | Create and receive line rows | `<search-dropdown>` |
| PO-line assignment target | §3.4 right column | **Top-and-bottom search-select wide cards (§7)** — each candidate needs three quantities to judge against, which a compact row cannot carry, but the pool is too large and too filter-dependent for a typeahead |

**No left-heavy pair here.** That pattern assigns many picks into one running list. This job is
"search, commit one assignment, possibly repeat for the remainder."

---

## 5. Permission gates

`receive` gates package creation (both paths), status advance, line acceptance, and every mutation on
§3.4. Domain scoping applies to every list. A package whose domain does not match the user renders as
plain text wherever it is referenced from another page, with no link through to its detail.

---

## 6. Out of scope

- **Intake, entirely** — put-away, bin assignment, stock levels, movements, discards, storeroom or
  location UI. A separate later kit. This sector ends at `accept`.
- `/packages/<id>/lines/<line_id>/split` as a route — absorbed into §3.4 as `?line_id=`.
- A plain inline "edit this line's quantity" action — delete-and-recreate covers the correction case.
  Add it later only if real usage shows the round trip is a genuine friction point.
- Any bulk mode inside the per-line assignment tool. The Basic Package Manager **is** the bulk tool.
</content>
