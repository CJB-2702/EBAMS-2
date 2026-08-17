---
type: "Decision Pending"
title: "Where does the Reallocation Portal actually live? (Demand↔PO Domain)"
description: "A routing gap discovered while front-end-kitting the Reallocation Portal — explained plainly, with a Business Architect recommendation, awaiting your call before the front-end kit is staged."
tags: [reallocation-resolution-kit, decision-pending, routing]
context_tier: 1
---

# Where does the Reallocation Portal actually live?

**Status:** RESOLVED — **Option A** confirmed (2026-08-16). Add `edit_line`,
`record_receipt`, and the six `reallocation_*` actions to `purchase_order_edit`'s
own POST handler (`_edit_post` in `purchase_orders.py`), mirroring the pattern
`shipment_edit` already uses, so the quantity-edit control, the Portal, and
`record_receipt` all resolve back onto Edit & Linkage. This is a **backend
prerequisite** — it has not been implemented yet as of this note.

---

## 1. The problem, in plain terms

This app has **two screens for a purchase order**, and they do different jobs:

- **PO Detail** (`/purchase-orders/<id>/`) — an overview. Status, totals, a read-only
  line list, shipments, activity feed. You look here to see where an order stands.
- **Edit & Linkage** (`/purchase-orders/<id>/edit/`) — the working screen. You pick a
  line on the left, and the right side shows and edits that line's demand claims:
  link a demand, de-link a demand, add a line, cancel a line.

When we talked through where the new pieces should go — the "change this line's
ordered quantity" control, the Reallocation Portal itself, and "mark part of this
claim received" — you picked **Edit & Linkage** for all three. That's the intuitive
answer: it's the screen where a Buyer is already working with a line's claims, so
that's where "this line's quantity changed, now go fix the claims" should happen too.

**The problem:** the backend code that was already built for this feature does not
agree. All three of those actions — `edit_line`, `record_receipt`, and every
`reallocation_*` action (auto-allocate, manual entry, unlock, commit) — were wired
onto **PO Detail's** POST handler, not Edit & Linkage's. And critically, PO Detail's
handler always sends the browser back to PO Detail when it's done — that redirect
target is hardcoded, not something a form can override.

So if we build the quantity-edit control and the Portal on Edit & Linkage anyway,
here's what actually happens when a Buyer uses them:

1. Buyer is on Edit & Linkage, working line 3.
2. Buyer edits line 3's quantity in the new inline control.
3. The form submits to PO Detail's action (because that's the only place this logic
   exists).
4. The shortfall triggers `ReallocationRequired`. PO Detail's handler catches it,
   seeds the reallocation session draft, flashes a warning message — and redirects
   the Buyer to **PO Detail**, not back to Edit & Linkage.
5. The Buyer is now staring at the read-only overview page, with no Portal in
   sight, and has to find their way back to Edit & Linkage's line 3 manually before
   anything resembling the Portal you described ever appears.

The same thing happens for `record_receipt` and for every step inside the Portal
itself (auto-allocate, manual entry, unlocking a claim, committing) — each one is a
separate POST, and each one would kick the Buyer back to PO Detail mid-flow.

**Why this wasn't a problem on the Receiving side:** the Package↔PO mirror (shipment
line quantity edits, its own Portal) was built *inside* Shipment Edit's own handler
from the start, and that handler already remembers which line was selected and
returns to itself. It just works. The PO side was built as an extension of PO
Detail instead, and nobody has yet taught it to return anywhere else.

---

## 2. What it would take to fix

Add the same six action branches — `edit_line`, `record_receipt`,
`reallocation_auto_allocate`, `reallocation_manual_entry`,
`reallocation_unlock_claim`, `reallocation_commit`, `reallocation_cancel` — to Edit &
Linkage's own POST handler, the same way Shipment Edit already has its own copy of
the equivalent logic. This is a backend change (`purchase_orders.py`), not a
template change, and it isn't large — the underlying manager/context/guard calls
are identical; only the entrypoint wiring and the redirect target are new. It is,
however, still a piece of backend work that has to land before the front-end build
can put these controls where you actually want them.

---

## 3. The options

### Option A — Do the backend fix; build the UI where you actually want it

Add the missing action branches to Edit & Linkage's handler first (small, mechanical
backend task — copy the pattern already proven on the shipment side), then build the
quantity-edit control, the Portal overlay, and `record_receipt` on Edit & Linkage as
planned.

- **Pro:** Matches the mental model you already described — the screen where a Buyer
  is working a line's claims is the same screen where a quantity change and its
  fallout get resolved. Buying and Receiving end up with the same shape.
- **Con:** A backend task has to happen before (or alongside) the front-end build.
  Not a big one, but it's a dependency this kit can't absorb itself.

### Option B — Build against the backend exactly as it stands today

Put the quantity-edit control, the Portal, and `record_receipt` on **PO Detail**
instead of Edit & Linkage. No backend change needed — everything already redirects
there.

- **Pro:** Zero backend dependency. Front-end work can start immediately.
- **Con:** Splits the Buyer's workflow across two screens in a way that doesn't match
  how Edit & Linkage already works for every other claim action (link, de-link, add
  line, cancel line all live there). A Buyer resolving a shortfall would edit the
  line on one screen and manage every other claim detail on a different one. It also
  breaks symmetry with Receiving, where everything already lives on one screen.

---

## 4. Business Architect's read

The two screens exist for a reason: PO Detail is *"where does this order stand,"*
Edit & Linkage is *"let me work this order's lines and claims."* Everything this
kit adds — quantity edits, the Portal, marking a claim received — is squarely "let
me work this order's lines and claims" work. Option B doesn't just cost a redirect;
it puts a new category of claim-affecting action on the one screen that was
deliberately kept read-mostly, which is very likely to grow its own follow-on
requests later ("wait, why can't I de-link from here too, I'm already here") — the
kind of drift that turns a clean read/write split into two half-write screens.

Option A's backend cost is small and one-directional: it's copying a pattern that
already exists and is already proven correct on the Receiving side. There's no new
design to invent, just parity work.

**Recommendation: Option A.** Treat the backend addition as a short, well-scoped
prerequisite — not a redesign, not new business rules, just wiring the same six
actions onto the screen where they were always going to conceptually belong. It
keeps Buying and Receiving symmetric and keeps Edit & Linkage's job description
intact.

---

## 5. What I need from you

Confirm Option A or B (or a variant) so `front-end-kit/reallocation_resolution/` can
be staged against a routing story that's actually buildable. If Option A: I'll note
the backend prerequisite plainly in the kit's README and route skeleton as a
blocking dependency, without building it myself (backend work is outside this
persona's job) — you'd hand that off to `/backend-persona` before or alongside the
template build.
