---
okf_version: "0.1"
type: "Process Guide"
title: "Package Comments & Files — Front-End Plan"
description: "Event vs. ActivityThread for Package (recommendation: Event, per decisions.md D68), the narration rules for status updates and line reassignments, and the package view page's comment/file/photo card layout."
tags: [front-end-kit, procurement, package, workflows, events]
context_tier: 2
personas: [frontend, business]
---

# Package Comments & Files — Front-End Plan

## 1. Event or ActivityThread? — recommendation: Event

**Recommendation: `Event`, not `ActivityThread`.** Recorded formally as
[`decisions.md` D68](../../../procurement_starter_kit/decisions.md) — this section explains the
reasoning; that document is the authoritative record.

### The actual differentiator

Both surface classes support what a package needs on their face — checked against the real feature
matrix on the live `events/kitchen-sink` page (`app/events/templates/events/kitchen_sink.html`,
"Feature matrix" section):

| Capability | `Event` | `ActivityThread` |
| :--- | :--- | :--- |
| Comments (human + machine) | Yes | Yes |
| Direct attachments (files, photos) | Yes (optional flag, on for `Event`) | Yes |
| Domain-scoped, independently visible/listable | **Yes** — `domain` is a required FK, `Event.objects.visible_to(user)` filters by it | **No** — "subordinate to the owning item; the item's own access rules govern visibility, not this row" |
| Type/status/priority metadata | Yes | No (sentinel-filled) |

Comments and attachments are a wash. The decision comes down to **domain scoping and independent
visibility** — exactly the reasoning the requester's own instinct named.

### Why a package needs that

A package is the kind of thing someone browses across a domain — "what shipped against my domain
this week," a receiving-staff worklist, a future events/activity feed filtered to package-type rows
— the same way `PurchaseOrder.event` already supports for POs (D17). `ActivityThread`'s model is a
thread *hanging off* something else, visible only through that something else's own page — fine for
a Part's document library, wrong for a package that itself needs to be found and filtered
independently of always going through its PO first.

### The domain question, resolved

The requester's instinct — "it should have a domain, copied from the PO's" — is right, but the
mechanism doesn't need a new column on `Package` itself. `Package.purchase_order` is **non-nullable**
(`decisions.md` D59, "never free-floating"), so a package's domain is never ambiguous or
independently choosable — it is always its PO's domain. `PackageFactory.create` reads
`purchase_order.domain` once and writes it onto the new `Package.event` row at creation, the same
one-time copy `PurchaseOrder.event.domain` already does from... nowhere, actually (D61 had to *add*
`PurchaseOrder.domain` because nothing upstream supplied it). A package doesn't have that problem —
its PO already has a domain, so no new column is needed, only the copy.

### The edge case the requester flagged, and why it doesn't apply

"A package might arrive before the PO is made, and its domain might not be clear" was raised as a
future concern. Under the **current** model it cannot happen: `create_package` requires
`purchase_order_id` (D59) — there is no code path that creates a `Package` without a PO already
existing to copy the domain from. This isn't a gap to design around now; it only becomes relevant if
a future kit allows a package to exist ahead of its PO, which nothing in this kit's scope proposes.

---

## 2. Narration rules

Everything that happens to a package narrates on **its own** Event (D68) — not the PO's, which is
what `package_lifecycle.md` currently specifies and is being revised:

| Event | Narrates as | Where |
| :--- | :--- | :--- |
| Package created | Machine comment | Package's own Event |
| Status advanced (`Awaiting Shipment → Shipped → …`) | Machine comment | Package's own Event |
| Line inspected/accepted, especially when `quantity_accepted` differs from `quantity` | Machine comment | Package's own Event |
| Line split or reassigned onto **this package's own header PO** | Machine comment | Package's own Event only |
| Line split or reassigned onto a **different** PO's line | Machine comment (both sides) | Package's own Event **and** that other PO's Event — the receiving PO is genuinely affected, mirroring `package_lifecycle.md`'s existing "every affected PO's Event" rule for splits |
| Line added/removed/reassigned against a package already at `Delivered to Local Receiving Location` or `Accepted` | Machine comment (JSON pre-state snapshot) **plus mandatory human comment** | Package's own Event — D68 extending D57. Per D69, a delivered (or split) package is locked out of [basic_package_manager.md](basic_package_manager.md) entirely, so this only ever happens on [package_edit_and_linkage.md](package_edit_and_linkage.md) §3, one mutation at a time |
| A human annotating the package (a note about a call with the vendor, a delay explanation) | Human comment | Package's own Event |
| A shipping PDF, customs form, or other document attached | Direct attachment | Package's own Event, via its existing document-library support (D19's mechanism, same infrastructure) |
| In-transit photos uploaded | Direct attachment (image) | Package's own Event — rendered via the gallery card, same component `parts/detail.html` and `assets/assets/detail.html` already use |

No new comment/attachment infrastructure is needed anywhere in this — it's entirely the existing
`Event` capability, per package instead of per PO.

---

## 3. Package view page — where the interaction actually happens

**Page:** `/procurement/packages/<id>` (unchanged route from `package_workflows.md` §2.2 — this
section revises that page's card layout, it does not replace the page)

**Rule: comments, file upload, and photo upload happen on the view page, never on the edit page.**
`package_edit_and_linkage.md` is a header-fields-and-line-assignment tool; narration and documents
belong where someone goes to understand a package's story, which is the view page. This mirrors the
edit-vs-detail split already established for demands
([part_demand_workflows.md](../part_demand_workflows.md#23-procurementdemandsidedit--edit-demand)):
edit is where you *act on structure*, view is where you *understand and narrate*.

### Revised card layout

| Card | Placement | Contents |
| :--- | :--- | :--- |
| Header / hero | Full width | Package number, tracking, carrier, status badge, "Advance status" action (permission-gated — receiving staff / Buyer, `package_workflows.md` §1) |
| Mixed-assignment banner | Full width, above the lines table, only when `mixed_po_assignments` is true | Unchanged from `package_workflows.md` §2.2 |
| Lines table | Left, main column (2/3) | Part, quantity shipped, `quantity_accepted` (inline accept input + rejection notes), assigned PO line, split-lineage indicator, "Edit assignment" link → `package_edit_and_linkage.md`'s page, deep-linked via `?line_id=` |
| Demand arrival for this package's lines | Left, main column (2/3) | Unchanged — the [shared demand session component](../shared_workflows.md#shared-demand-session-display) |
| **Comments** | Right, detail rail (1/3) | The full `event_card.html`-family comment stream for this package's own Event — status-advance machine comments, line-mutation audit comments (including the JSON-snapshot ones, rendered collapsed/expandable — not raw JSON dumped in the feed), and human comments. Add-comment form included, same as any other Event. **This is where the mandatory human-comment popups from the edit-time flows ultimately land** — the popup captures the text, the write posts it here |
| **Files** | Right, detail rail (1/3) | `files_card.html` — shipping PDFs, customs forms, any non-image document, with upload |
| **Photos** | Right, detail rail (1/3) | `gallery_card.html` — in-transit/condition photos, image documents split out from the files card the same way `events/kitchen-sink` sections 3/4 demonstrate the split |
| Primary PO / quick facts | Right, detail rail (1/3) | Primary PO link, vendor, dates — unchanged; a "View full association network" link seeded `?package_id=<id>` into [../graph_association_visualizer.md](../graph_association_visualizer.md) |
| Status history | Right, detail rail (1/3) | Unchanged stepper — now redundant with the comments card's machine-comment trail for the same transitions; keep both (stepper for at-a-glance current position, comments for the narrated "why" and timestamps), don't try to merge them into one component |

**Removed:** the old "PO event thread (filtered)" card. That existed only because packages had no
Event of their own to show; with D68, the package's own Event is the primary feed, not a filtered
view into someone else's.

### Reference implementation

Build the Comments/Files/Photos cards directly from the existing, real fragments — don't
reimplement:

- `events/fragments/event_card.html` — the composite pattern (metadata + comments + attachments in
  one card), demonstrated live at `/events/kitchen-sink` §1 against a real `Event` row. This is the
  fastest path to the package view page's right rail: the package's own Event, rendered through this
  fragment, largely *is* the Comments+Files+Photos block, split into three cards per this page's
  layout rather than one composite card, using the same underlying `comments_card.html` /
  `files_card.html` / `gallery_card.html` partials `event_card.html` itself composes from.
- `events/fragments/comments_card.html`, `files_card.html`, `gallery_card.html` — the three
  independent fragments, demonstrated in isolation at `/events/kitchen-sink` §2–4, for exactly this
  page's three-separate-cards layout.

No new web component or card pattern needs to be built for this page — the "full event card"
already exists and is exercised against real data at `/events/kitchen-sink`.

---

## 4. Open questions for the developer

- Should JSON-snapshot machine comments render collapsed by default in the comments card (a
  "Line reassigned — details" disclosure) rather than as a full comment bubble, to keep the feed
  readable when a package has several such edits? Recommendation: yes, collapsed, consistent with
  how `purchase_order_workflows.md` treats `D57`'s PO-side snapshot comments, but not yet specified
  there either — worth deciding once, in the shared comment-row component, not per sector.
- `decisions.md` D68 is recorded but **not implemented** — `Package.event` doesn't exist in the
  models yet. This whole document (and `package_edit_and_linkage.md`'s narration references)
  describes the target state; building the view page's Comments/Files/Photos cards is blocked on
  that migration landing first.
