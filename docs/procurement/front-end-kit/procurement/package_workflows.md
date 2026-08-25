---
okf_version: "0.1"
type: "Process Guide"
title: "Package Workflows — Front-End Plan"
description: "Actions, pages, control-layer targets, search apparatus, and card layout for the Package sector of the procurement UI, including the line-splitting wizard that replaced the legacy arrival-linkage link table."
tags: [front-end-kit, procurement, package, workflows]
context_tier: 2
personas: [frontend, business]
---

# Package Workflows — Front-End Plan

**Sector:** shipment tracking — what a vendor actually shipped against a PO, and what survived
inspection. Per D44 this is the **highest-volume surface overall**, ideally machine-fed rather than
typed. **Intake (put-away, stock levels, bins) is out of scope** — this sector ends at
`quantity_accepted`.

## Source documents (read first)

| Document | What it defines |
| :--- | :--- |
| [../../procurement_starter_kit/control/package_lifecycle.md](../../procurement_starter_kit/control/package_lifecycle.md) | `create_package`, `advance_package_status`, `inspect_and_accept_package_line`, the line-splitting wizard, `derive_demand_arrival` |
| [../../procurement_starter_kit/models/package.md](../../procurement_starter_kit/models/package.md) | `Package`/`PackageLine` columns, the `mixed_po_assignments` drift flag, what replaced the legacy `PurchaseOrderPackageLink` table |
| [../../procurement_starter_kit/shared_demand_sessions.md](../../procurement_starter_kit/shared_demand_sessions.md) | Why per-demand arrival is sometimes undefined, and the struct that computes it — read before building any "how much arrived" display |
| [gap_analysis.md](gap_analysis.md) | §"What changed" — the legacy `ArrivalHeader`/`ArrivalLine` shape this sector replaces, and why the link table is gone |
| [packages/basic_package_manager.md](packages/basic_package_manager.md) | The fast-path, session-backed, drag-and-drop portal for the common "one PO → 2-3 non-overlapping packages" case — supersedes this doc's §2.1 as the preferred creation entry point |
| [packages/package_edit_and_linkage.md](packages/package_edit_and_linkage.md) | The revised `packages/<id>/edit` page — supersedes this doc's §2.3 line-splitting wizard route |
| [packages/package_comments_and_files.md](packages/package_comments_and_files.md) | Package gets its own `Event` (D68) — revises this doc's §2.2 detail-page card layout and the "machine comment on the PO's Event" language throughout |

**Read the three documents above first if you're building any of the pages they cover** — this file
still describes the sector's original shape and is being revised incrementally rather than rewritten
wholesale; where the two disagree, the `packages/` subfolder documents are newer and win.

## Rules that must hold in the UI

- **Intake is a hard boundary.** No storeroom, bin, location, or "put into stock" control belongs
  anywhere in this sector's UI — that's a separate, later kit. This sector's last verb is
  "accept," full stop.
- **`quantity_accepted` is a quantity, not a checkbox** (`models/package.md`). The accept UI needs a
  number input capable of recording partial acceptance (8 good, 2 damaged), not an
  accepted/rejected toggle. `null` (uninspected) must be visually distinct from `0` (inspected, all
  rejected) — don't default the input to 0.
- **The copy-on-create default, not a binding.** A package line's PO-line link is auto-resolved at
  creation when exactly one active line matches the part (`create_package`, step 4). The UI should
  show this as already-assigned, editable via the splitting wizard — not as an empty field waiting
  to be filled.
- **`mixed_po_assignments` is a flag, not a constraint** — surface it as a queryable/visible
  condition (a banner, a filter on the package list), never block an action because of it.
- **A demand behind several packages takes the least-advanced status.** If building any rollup
  display of "where is my stuff," this rule must be implemented exactly as specified — the
  temptation to show the most-advanced status (looks more optimistic) is the wrong answer.
- **Splitting is not a link-table edit.** Each split creates a new `PackageLine` row with its own
  `quantity` and reduces the original — there's no "quantity linked" field to edit, only rows to
  create. This shapes the wizard's interaction model: it produces rows, it doesn't adjust a join.

---

## 1. Actions that need to exist

| Action | Control-layer verb | Actor | Frequency |
| :--- | :--- | :--- | :--- |
| Create a package against a PO | `PackageFactory.create(purchase_order_id, actor, ...)` | Buyer, receiving staff | High |
| Advance package status | `PackageContext.advance(to_status, actor)` | Receiving staff, Buyer — ideally machine-fed | Very high, everyday |
| Inspect and accept a line | `PackageLineManager.accept(line_id, quantity_accepted, actor, rejection_notes)` | Receiving staff | Very high, everyday |
| Split a package line across PO lines | `PackageLineSplitHandler` | Receiving staff | Common enough to need a wizard, not rare |
| Reassign a line to a different PO line (no split) | Same handler, full quantity, no new row | Receiving staff | Common — "the degenerate case" of splitting |
| View derived demand arrival | `PurchaseOrderFulfillmentStruct` (read) | Everyone with domain access | Constant, embedded on demand/PO pages — see [shared_workflows.md](shared_workflows.md#shared-demand-session-display) |

---

## 2. Pages

### 2.1 `/procurement/packages/create` — Create package

**Page type:** Simple form with an embedded line-item table — **not promoted to a multi-card
wizard.** Applying the trigger rule: `Package` has exactly one reverse FK a user populates at
creation (`PackageLine`), and no secondary signal (no file upload, no inline-created related
record, no status choice — status defaults to `Awaiting Shipment`) pushes it over the line. This
mirrors the PO wizard's "Lines" card in shape, but stands alone because there's no second relation
(demand allocation) to attach — that's derived automatically from the copied PO-line link.

**Control layer hit:** `PackageFactory.create` → per line, `PackageLineManager` resolves the
PO-line link automatically.

**Key things to note:**
- **Superseded as the preferred entry point** by
  [packages/basic_package_manager.md](packages/basic_package_manager.md) — that page is now the
  recommended way to build a PO's packages, reached from PO detail. This page stays as a fallback
  for creating one package without the drag-and-drop workspace, and carries a banner steering users
  toward the better path — see `basic_package_manager.md`'s companion doc,
  [packages/package_edit_and_linkage.md](packages/package_edit_and_linkage.md) §2, for the exact
  banner placement and copy.
- **Submit now redirects to `packages/<id>/edit`**, not this page's own detail view — see
  `packages/package_edit_and_linkage.md` §2 for why.
- No line-level demand picker on this page — that's the point of the copy-on-create default.

### 2.2 `/procurement/packages/<id>` — Package detail

**Page type:** Work portal (3/4 + 1/4 shell). Where status is advanced and lines are inspected/
accepted; line reassignment now links out to §2.3's replacement rather than launching per-line.
**Card layout revised** by [packages/package_comments_and_files.md](packages/package_comments_and_files.md) §3 —
comments, files, and photos move onto this page as their own cards, replacing the old "PO event
thread (filtered)" card, once the package gets its own `Event` (D68). The card table in §4 below
still shows the pre-D68 shape; treat that linked document as current.

**Control layer hit:** `PackageContext` (read + status advance), `PackageLineManager` (accept),
`PurchaseOrderFulfillmentStruct` (the arrival-attribution rollup for lines on this package).

### 2.3 `/procurement/packages/<package_id>/lines/<line_id>/split` — Line-splitting wizard (superseded)

**Superseded by [packages/package_edit_and_linkage.md](packages/package_edit_and_linkage.md)** —
folded into `packages/<id>/edit`'s 1/3 items + 2/3 search-and-assign layout instead of a
standalone per-line route. The URL survives only as the query-parameter form
`packages/<id>/edit?line_id=<line_id>`, per this kit's Tier 1 URL-parameter rule. The description
below documents the interaction model that page reuses — it is not a second, separate page to
build.

**Page type (as absorbed):** Focused in-page tool, **not a modal** — resolving an unassigned or
misassigned line is a consequential multi-field decision (search, pick a line, assign a quantity,
repeat), which falls outside what a modal is for (destructive confirmation, read-only browsing,
single-field capture). Search-select-producing-wide-cards shape (§7 of the list-management
patterns) — see card layout below.

**Control layer hit:** `PurchaseOrderLineSearch` (the lookup, in `presentation_layer/search/`) →
`PackageLineSplitHandler` per assignment.

### 2.4 `/procurement/packages` — Package list

**Page type:** Search / list page. Filters: status, vendor (via PO), `mixed_po_assignments`
(the drift review queue — a first-class filter, not buried), date range.

### 2.5 `/procurement/purchase-orders/<id>/basic-package-manager` — Basic Package Manager

**Page type:** Session-backed sorting portal — see
[packages/basic_package_manager.md](packages/basic_package_manager.md) for the full spec. Listed
here for the sector's page inventory/reachability gate; PO-scoped in its URL because it's reached
from a PO, but it's a package-sector concern and its own document lives under `packages/`, not in
`purchase_order_workflows.md`. **Reached from:** PO detail's package entry point (a "Manage
packages" action — add this to `purchase_order_workflows.md` §2.2/§4's PO detail card table, not yet
present there).

---

## 3. FK relationships → search apparatus

| FK | On | Rough pool size | Pattern | Why |
| :--- | :--- | :--- | :--- | :--- |
| `purchase_order` → `PurchaseOrder` | Standalone create-package entry point only | Hundreds of open POs | `<search-dropdown>`, filtered to open statuses | Single value; the common path skips this entirely by arriving pre-filled from the PO detail page |
| `part` (per line) → `parts.Part` | Create-package line rows | Hundreds–thousands | `<search-dropdown>` | Same reasoning as every other part pick in this app |
| `purchase_order_line` reassignment target | Splitting wizard | Tens of candidate lines per vendor/part | **Top and bottom search select wide cards pair (§7)** — top card is a search-select (filters: part locked to the arriving line, PO status = open, vendor implied by the package's PO) against a results table; each pick appends a **wide card** below showing `qty_ordered`, `qty_from_accepted_packages` so far, and outstanding balance | Each candidate needs enough context (three quantities, not just a name) to judge before assigning — a compact table row isn't enough, but the pool is too large and needs filters for a `<search-dropdown>` typeahead. This is the wizard's real work per `package_lifecycle.md`: "finding the right line across a vendor's open orders is the hard part, not the arithmetic" |

No left-heavy assignment pair here — that pattern assigns *many* picks into one running list (like
demand allocation). The splitting wizard's job is closer to "search, then commit one assignment,
then possibly repeat for the remainder," which is exactly §7's shape: a search-select producing
appended wide-card records, not a bidirectional pool/target split.

---

## 4. Card layout

### 2.1 Create package — `/procurement/packages/create`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Header | Full width | PO (pre-filled or `<search-dropdown>`), tracking number, carrier, shipped/expected dates, notes |
| Lines | Full width | Add-line mini-form (part + quantity) + running table; each add auto-resolves its PO-line link and shows the result inline (assigned line number, or "unassigned — resolve after creation" if no unique match) |

### 2.2 Package detail — `/procurement/packages/<id>`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Header / hero | Full width | Package number, tracking, carrier, status badge, "Advance status" action |
| Mixed-assignment banner | Full width, above the lines table, only when `mixed_po_assignments` is true | Non-blocking notice naming which lines point at a different PO than the header |
| Lines table | Left, main column (2/3) | Part, quantity shipped, `quantity_accepted` (inline accept input + rejection notes), assigned PO line (or "unassigned"), split-lineage indicator, per-line "Split / Reassign" action linking to §2.3 |
| Demand arrival for this package's lines | Left, main column (2/3) | Renders the [shared demand session component](shared_workflows.md#shared-demand-session-display) per line — attributable figure or session total |
| Primary PO / quick facts | Right, detail rail (1/3) | Primary PO link, vendor, dates (shipped / expected / received) |
| Status history | Right, detail rail (1/3) | `Awaiting Shipment → Shipped → Delivered to Depot → Delivered to Local Receiving Location → Accepted` as a stepper, current stage highlighted, `Lost` shown as a terminal branch if reached |
| PO event thread (filtered) | Right, detail rail (1/3) | Machine comments this package generated on its PO's `Event` (package status changes, line acceptance) — packages don't get their own `Event` row (`package_lifecycle.md` step 6: "Machine comment on the PO's Event"), so this is a filtered view into the PO's thread, not a separate feed |

### 2.3 Line-splitting wizard — `/procurement/packages/<package_id>/lines/<line_id>/split`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Arriving line summary | Full width | The line being resolved: part, quantity, current assignment (if any), remaining unassigned quantity |
| Search & assign (top card of the §7 pair) | Full width | Search-select: filters (PO status, vendor pre-scoped), results table of candidate PO lines |
| Assigned splits (bottom card of the §7 pair) | Full width | Each committed split as a wide card: target PO/line, quantity assigned, `qty_ordered`/`qty_from_accepted_packages`/outstanding balance at assignment time, `split_from` lineage back to the original row |

### 2.4 Package list — `/procurement/packages`

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Filters | Full width | Status, vendor, `mixed_po_assignments`, date range |
| Stat bar | Full width | Counts: awaiting shipment, in transit, delivered, drift-flagged |
| Results table | Full width | Package number, PO, vendor, status, `mixed_po_assignments` indicator, received date |

---

## 5. Open questions for the developer — both resolved

- ~~Should "Advance status" be a single dropdown-driven action, or a stepper?~~ **Resolved: a
  dropdown, constrained to one stage at a time.** Not a full stepper visual, and not a jump-to-
  any-stage control either — the dropdown only ever offers the currently legal next stage(s) (in
  practice one option, plus `Lost` when the branch applies), so advancing is always a single-stage
  move even though the control is a `<select>` rather than a row of clickable steps.
- ~~Should there be a bulk entry point for resolving many unassigned lines on one package?~~
  **Resolved: yes, this is what [packages/basic_package_manager.md](packages/basic_package_manager.md)
  is** — the drag-and-drop portal is the bulk resolution tool for the common, straightforward case;
  `packages/<id>/edit` ([packages/package_edit_and_linkage.md](packages/package_edit_and_linkage.md))
  stays the one-line-at-a-time tool for what doesn't fit there. No separate bulk mode needed inside
  the per-line search-and-assign tool itself.
