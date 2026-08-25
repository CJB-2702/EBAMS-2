---
okf_version: "0.1"
type: "Decisions"
title: "Dispatch UI — Decisions"
description: "The twelve decisions taken in the planning session that shape this kit, each with rationale, consequence, and the reversal cost."
tags: [front-end-kit, dispatching, decisions]
context_tier: 2
personas: [frontend, backend]
---

# Dispatch UI — Decisions

Taken with the developer during the planning session that produced this kit. A builder should treat
these as settled and implement them; if one turns out to be wrong mid-build, say so rather than
quietly re-deciding.

---

## D1 — Draft is removed. A dispatch is born **Requested**

`DispatchWorkflowStatus.DRAFT` and `.SUBMITTED` are both deleted and replaced by a single
`REQUESTED`. Creating the dispatch **is** the request; there is no separate submit act.

**Why.** A draft state buys a private scratchpad, which is exactly what the *template* editor needs
(a committed revision is immutable, so edits must accumulate somewhere). A dispatch has no such
constraint — its intent is editable in-place right up until it is planned. Draft plus Submitted was
two states doing one state's work, and the ceremony of a submit button bought nothing.

**Consequence.** No submit verb, no submission form, no auto-hold of requested assets on submission
(D5). `FIXES_REQUESTED → REQUESTED` via `resubmit()` is the only way back into the queue.
`submitted_at` is stamped at creation (D12).

**Reversal cost.** Moderate — the enum, the transition table, the factory, and any rendered state
tag. Cheapest before Phase 1 is built.

---

## D2 — Booking an asset against a **Requested** dispatch resolves it

`REQUESTED` joins `_DERIVABLE_STATUSES` in `DispatchStateDeriver`, alongside `UNDER_REVIEW`,
`PLANNED`, and `ALTERNATE_RESOLUTION`.

**Why.** The deriver flips a dispatch to Planned when it gains a live reservation, but it only
looks at dispatches already inside the resolved region. Without this change, a dispatcher who books
a truck straight off a Requested dispatch would watch nothing happen — the dispatch would sit in
Requested with a confirmed booking hanging off it, and they would have to go back and click "Take
under review" to make the state honest. Booking an asset is a stronger statement of intent than
clicking a review button, and with Draft gone the ceremony should shrink in the same direction.

**Consequence.** "Take under review" becomes an optional signal ("I own this"), not a required
gate. `REQUESTED → PLANNED` and `REQUESTED → ALTERNATE_RESOLUTION` must be added to
`DISPATCH_STATE_TRANSITIONS`, because the deriver routes its writes through the same table.

**Reversal cost.** One line — remove `REQUESTED` from `_DERIVABLE_STATUSES` and drop the two
transitions. If reversed, the Actions card must make "Take under review" visually mandatory.

---

## D3 — One list page, not a queue plus a dashboard

`/dispatching/dispatches` is a single search page whose visible set widens for dispatchers. There is
no separate `/dispatching/queue`.

**Why.** The developer's call: core functionality before utility pages. Two pages over one query
with one predicate difference is two pages to maintain.

**Consequence.** The visibility rule in [build_plan/phase_4_dispatch_index.md](build_plan/phase_4_dispatch_index.md)
§3 is load-bearing — it is the only thing standing between a requester and every dispatch in their
domains.

---

## D4 — No session draft anywhere in the dispatch surface

The dispatch edit page writes straight through to the database on every action. Nothing is held in
`request.session`.

**Why.** Follows from D1. The template draft editor's session mechanics exist to make several edits
produce one immutable revision; a dispatch has no revisions and no immutability, so the same
machinery would be pure cost.

**Consequence.** The dispatch edit page **looks** like
`templates/draft_editor.html` and **behaves** like an ordinary POST/redirect editor. Do not copy
`template_draft_session_adapter.py` or anything that touches it. The "Unsaved draft" warning banner
is replaced by the state banner ([status_vocabulary.md](status_vocabulary.md) §4).

---

## D5 — Requested assets is a reference picker, not a booking tool

The create page offers a left-heavy listbox of assets with simple filters. Selecting assets writes
their **names into the `requested_assets` free-text field**. No ids are stored, no reservations are
created, nothing is held.

**Why.** The developer reversed an earlier plan to auto-hold free assets on submission. It also
brings the UI back in line with what the model has always said: `requested_assets` is informational
and historical, "written once at request time and never updated again", and the reservations are
the sole authority on what is committed. A picker that created holds would have made that field
look like a reference, which is the exact bug the model's docstring warns about.

**Consequence.** `app/dispatching/control_layer/managers/requested_asset_auto_reserver.py` is
**deleted** in Phase 0 — with `submit()` gone (D1) it has no caller, and leaving a dormant
auto-reserver in the tree invites someone to wire it back up.

---

## D6 — The crew dual listbox lives on **edit**, not create

**Why.** The canonical `<dual-list-box>` posts each move to a server endpoint and re-renders itself
from the response — it needs a saved parent row to move things against. A dispatch is live the
moment it is created (D1), so redirecting from create straight to edit puts the user in front of the
canonical component one hop later, with no bespoke client-only variant to maintain.

**Consequence.** Create collects intent only. Its success message points at what comes next:
requirements and crew.

---

## D7 — No asset assignment on any dispatch page

Booking an asset for a dispatch always leaves the dispatch surface and goes to the existing
reservation create page, carrying context in URL parameters.

**Why.** That page already does the work — multi-field asset filtering, availability marking against
a window, double-booking detection, tentative-always semantics. Rebuilding a second, weaker asset
picker inside the dispatch editor would duplicate it and drift from it.

**Consequence.** See [build_plan/phase_5_reservation_handoff.md](build_plan/phase_5_reservation_handoff.md).
The dispatch pages own an *outbound link* and an *attach-existing* action, never a picker.

---

## D8 — A reservation created with a dispatch id returns to the dispatch edit page

**Why.** The developer's call, and the right one: booking one asset for a job usually means booking
another. Landing on the reservation's own detail page ends the loop and makes the user navigate back
manually.

**Consequence.** `reservation_create`'s redirect becomes conditional. Without a dispatch id, current
behaviour is unchanged — that path is already built and in use, and must not regress.

---

## D9 — Crew and expenses are cards on the detail page, not their own pages

**Why.** Both are small, both are read far more often than written, and expenses are one of the two
facts `DispatchStateDeriver` reads — seeing them next to the reservations that compete with them is
the whole point.

**Consequence.** No `/dispatch/<id>/expenses` page. The route of that name is POST-only.

---

## D10 — The template library is the "create from template" picker

A sidebar link **Create Dispatch from Template** points at `/dispatching/templates`; each row and the
detail page get a **Create dispatch** button carrying `?template=<id>` to the create page.

**Why.** The library already lists, filters, and explains templates. A second picker embedded in the
create page would be a worse version of a page that already exists.

**Consequence.** Two small edits to a built surface: the row button, and a search box the library
does not currently have (it ships with only a head/all toggle, which is thin for a picker).

---

## D11 — The detail page is GET-only

Every form rendered on detail posts to a sibling action route, never to detail itself. This mirrors
the reservation detail page, which states the same rule in its module docstring.

**Why.** It makes "no request to this URL can ever write" checkable by reading one decorator.

---

## D12 — `submitted_at` is stamped at creation

**Why.** With Draft gone, entering the queue and being created are the same instant. The field stays
meaningful ("when the process started") and every query written against it keeps working.

**Consequence.** It duplicates `created_at` for now. That is acceptable; the alternative is a nullable
column that nothing ever sets.
