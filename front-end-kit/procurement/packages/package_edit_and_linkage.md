---
okf_version: "0.1"
type: "Process Guide"
title: "Package Edit & Linkage — Front-End Plan"
description: "The packages/<id>/edit page: header edit plus a master-detail PO-line assignment tool mirroring the PO Linkage Portal, and why it supersedes the standalone line-splitting wizard route."
tags: [front-end-kit, procurement, package, workflows, linkage]
context_tier: 2
personas: [frontend, business]
---

# Package Edit & Linkage — Front-End Plan

**Page:** `/procurement/packages/<id>/edit`

This is the package sector's mirror of
[purchase_order_workflows.md's PO Linkage Portal](../purchase_order_workflows.md#24-procurementpurchase-ordersidedit--po-edit--linkage)
— same master-detail shape, same underlying job (assign one side of a relationship to the other),
inverted: the Linkage Portal links **demands to a PO line**; this page links **this package's own
lines to PO lines**, potentially across several vendors' open orders. Read the Linkage Portal
section first — this page follows its conventions rather than restating them.

## Relationship to the old line-splitting wizard

`package_workflows.md` §2.3 originally specced `/procurement/packages/<package_id>/lines/<line_id>/split`
as a standalone focused tool. **This page absorbs that job.** Instead of a separate route per line,
selecting a line in this page's left column drives the same search-and-assign tool in the right
column — one page handles every line on the package instead of one URL per line. The old route is
superseded, not kept alongside it (two ways to do the same assignment would drift).

**The deep-link is preserved as a URL parameter, not a separate route** — per the Tier 1 rule in
[UX_UI.md](../../../harness/UX_UI.md) and [searchbars.md](../../../harness/UX_UI/search/searchbars.md):
`/procurement/packages/<id>/edit?line_id=<line_id>` lands on this page with that line pre-selected,
exactly reproducing what the old wizard route did, without a second URL for the same job. Update
every existing inbound link (package detail's per-line "Split / Reassign" action) to this form.

---

## 1. Page layout

| Region | Placement | Contents |
| :--- | :--- | :--- |
| Header edit form | Full width, top (3/3) | Tracking number, carrier, shipped date, expected arrival date, notes — plain edit form, standard card-footer save. **Not status** — status advance stays an action on the package view page (`package_comments_and_files.md`), same edit-vs-detail split already established for demands |
| Items | Left, 1/3 | Every `PackageLine` on this package, selectable (click to drive the right column) — part, quantity, current PO-line assignment (or "unassigned"), split-lineage indicator, a small **Delete** action per row (§2). A **"+ Add line"** button above the list opens the create-line popup (§2) |
| PO search & select | Right, 2/3, populated on line selection | Search tool for candidate PO lines: filters (vendor implied by context if arriving from a known PO, otherwise open across vendors; part locked to the selected line's part; PO status = open), results table, each candidate showing `qty_ordered`, `qty_from_accepted_packages` so far, and outstanding balance — the exact context `package_lifecycle.md`'s splitting wizard already specified. An **Assign** action per result calls `PackageLineSplitHandler` (split, if a partial quantity; reassign, if the full remaining quantity) |

**URL parameters** (Tier 1 rule):

| Param | Effect on load |
| :--- | :--- |
| `?line_id=<id>` | Pre-selects that `PackageLine` in the left column, populating the right column exactly as a click would |
| Standard `PurchaseOrderLineSearch` filter params (`?part_id=`, `?vendor_id=`, `?status=`, …) | Pre-fill the right column's search tool |

Selecting a line is a client-side interaction that must round-trip through the URL
(`hx-push-url` on select), same as the Linkage Portal — a reload or a bookmark must reproduce the
same selected line, not lose it.

**Control layer hit:** `PackageContext` (read, header + lines) for page load; the header form posts
to a plain edit entrypoint; `PurchaseOrderLineSearch` for the right column's search;
`PackageLineSplitHandler` for the Assign action; `PackageLineManager` for the create/delete actions
in §2; `PackageContext.delete(...)` (proposed) for the whole-package delete in §2 — all but the last
already specified in `package_workflows.md` §1, this page just relocates where they're triggered
from.

---

## 2. Line and package CRUD

This page originally only covered **Update** (header fields, PO-line assignment). Rounding it out:

### Create a line — popup

**"+ Add line"** (above the Items column) opens a modal — a single-field-capture, appropriate per
[modals.md](../../../harness/UX_UI/design_patterns/modals.md) — for a part not already reflected on
this package (a vendor bonus item, a substitution, something the packing slip missed): part
(`<search-dropdown>`), quantity, and an optional "assign to PO line" search right in the same popup
(the same search this page already has in its right column — reuse the component, don't build a
second one) so a Buyer who already knows the target line doesn't have to create-then-immediately-
reselect. Leaving it unassigned is valid — the line lands `purchase_order_line = null`, same as any
copy-on-create miss, resolved later via the normal right-column flow. Calls
`PackageLineManager.add_line(...)` (the same verb `create_package` uses per line, §1).

### Delete a line

A small **Delete** action per row in the Items column, confirmed (small, confirmed, never primary —
[UX_UI.md](../../../harness/UX_UI.md)). Soft delete
(`SoftDeleteMixin`, per `models/package.md`). If this line has split children (`splits.exists()`) or
is itself a split product (`split_from` set), show a stronger warning in the confirmation — deleting
it removes the origin (or a sibling) of a split lineage — but don't block it; the row is soft-deleted,
not destroyed, so the audit trail survives regardless.

### Delete a package

A small, secondary **"Delete package"** action on the header edit card's footer (`form_style_guide.md`
— delete is always small, never primary). Confirmed via a modal requiring a **mandatory reason** —
unlike a single line edit (which only needs the note when the package is delivered, per D68), a
whole-package delete always requires one, regardless of delivery status: this is a bigger,
rarer, more consequential action than a line edit, and D57's own "cancellation is a soft delete plus
that comment" pattern for PO lines isn't gated on PO status either. Soft delete
(`SoftDeleteMixin`) — the row and its history are never destroyed.

**Cascade note (implementation detail worth flagging now, not discovering later):**
`PackageLine.package` is `on_delete=CASCADE` in the schema, but that's a **hard-delete** cascade —
it does nothing when `Package` is soft-deleted. `PackageContext.delete(...)` must explicitly
soft-delete every active line on the package as part of the same call; nothing does this for free.

**Warn, don't block, when real receiving history exists.** If any line on the package carries a
non-null `quantity_accepted`, the confirmation modal should say so plainly ("this package has
accepted lines — deleting removes it from active views, but its receiving history is preserved") —
consistent with soft delete never actually losing the record, this is about making sure the user
understands the consequence, not a permission gate.

### CRUD audit — is anything else missing?

| Entity | Create | Read | Update | Delete |
| :--- | :--- | :--- | :--- | :--- |
| `Package` | Elsewhere (`/procurement/packages/create` or the Basic Package Manager) — out of scope for this page by design | Header form load | Header edit form (§1) | **New, above** |
| `PackageLine` | **New, above** | Items column (§1) | PO-line reassignment/split via the right column (§1) | **New, above** |

Nothing else is missing for this page's actual job. Two things deliberately **excluded**, not
overlooked:
- **`quantity_accepted` (inspection/acceptance)** stays on the package **view** page
  ([package_comments_and_files.md](package_comments_and_files.md)), not here — inspecting what
  arrived is a different action than editing what's recorded, same reasoning that already keeps
  status-advance off this page.
- **A plain "edit this line's quantity in place," without touching its PO-line assignment or
  deleting/recreating it,** isn't built. Delete-then-recreate (both now available) covers the
  correction case without a third code path for the same outcome — add a lighter inline-quantity-
  edit action later only if real usage shows the delete/recreate round trip is actually a friction
  point, rather than building it preemptively.

---

## 3. Create → edit, and the preferred-creation-path banner

**Package creation redirects straight into this page.** `/procurement/packages/create`'s submit
action (`package_workflows.md` §2.1) lands on `/procurement/packages/<new_id>/edit`, not the
detail/view page — a freshly created package is, by definition, mid-setup (header fields just
entered, lines likely still need PO-line resolution), which is exactly this page's job. The view
page (`package_comments_and_files.md`) is where you go once a package is in a stable, "tracking its
real-world journey" state, not immediately after typing in its header.

**The standalone create-package page should steer people toward the preferred path.** Per the
requester: the *preferred* way to create a package is from
[basic_package_manager.md](basic_package_manager.md) — the PO's own package-manager portal — not
this standalone form. `/procurement/packages/create` still needs to exist (there's no other entry
point for a package whose originating PO isn't already open in front of the user), but it should
carry a visible hint steering traffic to the better path when a PO context is available:

- **At the top of the page**, a small notice: "Building packages for a specific purchase order? The
  [Basic Package Manager](basic_package_manager.md) lets you sort a PO's expected packages by
  drag-and-drop." (Link target: that PO's `/procurement/purchase-orders/<id>/basic-package-manager`,
  when a PO is already selected/known on this page — otherwise link to the PO list/search.)
- **Next to the submit button**, a smaller repeat of the same nudge, since a user who scrolled past
  the top notice without reading it is about to commit to the slower path right there.

This is a nudge, not a gate — the standalone form must still fully work end to end (it's the only
option for someone who hasn't identified the PO context, or who is intentionally creating one
package rather than sorting several).

---

## 4. Key things to note

- No drag-and-drop here — unlike `basic_package_manager.md`, this page resolves **one line at a
  time** against a search tool, the same interaction model as the original splitting wizard. Drag-
  and-drop belongs to the multi-line, multi-package sorting job; this page's job is "find the right
  PO line for this one arriving line," which is a search problem, not a sorting problem.
- **This page is reachable for any package regardless of delivery or split status — and per
  `decisions.md` D69, it is now the *only* page that can mutate a package once it's delivered or has
  `has_splits = True`.** `basic_package_manager.md` locks such packages out entirely rather than
  handling them inline (D69's simplification), so every delivered/split-package edit funnels here.
  This page still needs D68's audit-snapshot-plus-human-comment requirement whenever the package has
  already been delivered (unchanged rule, `has_splits` alone doesn't trigger the note — only
  delivery status does, per D68's original wording): each Assign action, Create-line, or Delete-line
  against a delivered package opens the same single popup capturing the mandatory human comment, and
  the write posts both that comment and a JSON pre-state snapshot (empty/absent for a newly created
  line, since there is no prior state) as machine/human comments on the package's own Event, in the
  same request — this page has no session draft to defer through, so capture and write happen
  together, one mutation at a time. No batching, no pending-note tracking, no supersession logic —
  those only existed in `basic_package_manager.md`'s earlier design and were removed by D69, not
  moved here.
- **Deleting the whole package always requires a note**, even on an undelivered package — stricter
  than the per-line gate, which only fires when delivered. See §2.
