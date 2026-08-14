---
okf_version: "0.1"
type: "Process Guide"
title: "Basic Package Manager — Front-End Plan"
description: "The fast-path, session-backed portal for building a PO's expected 2-3 non-overlapping packages by drag-and-drop. Delivered or split packages are locked out of this tool entirely (D69) and edited on package_edit_and_linkage.md instead."
tags: [front-end-kit, procurement, package, workflows, session-draft]
context_tier: 2
personas: [frontend, business]
---

# Basic Package Manager — Front-End Plan

**Page:** `/procurement/purchase-orders/<id>/basic-package-manager`
**Session key:** `basic_package_session`

## Why this page exists, separately from the full linkage tools

The overwhelming common case (per the requester) is: **one PO generates two or three packages, and
their lines don't overlap** — a vendor ships a straightforward order in a couple of boxes, each
box's contents map cleanly onto this PO's own lines. That case needs a fast, visual, all-on-one-page
tool: drag lines into package buckets, done.

The **complex** cases — a line split across a *different* PO's lines, resolving a line that matches
nothing — already have a dedicated tool: the line-splitting wizard, now folded into
[package_edit_and_linkage.md](package_edit_and_linkage.md)'s `packages/<id>/edit` page. This page
deliberately does **not** attempt that job. Every drag-and-drop move here stays within **this PO's
own lines** — there is no cross-PO search apparatus on this page. A package that needs a line from a
different PO is finished here for its straightforward lines, then handed to
`packages/<id>/edit` for the remainder. Trying to make one page do both jobs is how the legacy
"do everything in one arrival portal" design got complicated; keeping the fast path fast is the
point.

**Source documents:** [../../../procurement_starter_kit/control/package_lifecycle.md](../../../procurement_starter_kit/control/package_lifecycle.md),
[../../../procurement_starter_kit/models/package.md](../../../procurement_starter_kit/models/package.md),
[../../../procurement_starter_kit/decisions.md](../../../procurement_starter_kit/decisions.md) D57
(the audit-snapshot pattern that made this page's original design complicated), D68 (Package's own
Event — see [package_comments_and_files.md](package_comments_and_files.md)), **D69 (the lock rule
this page now builds around — read this one first)**.

---

## 1. Page layout

**Page type:** Focused session-draft portal — not a work portal, not a plain wizard. Structurally
closest to the PO create wizard's session-draft pattern (`multi_step_flows.md`), but laid out as a
persistent workspace rather than a linear scroll, because the task (sort N lines into 2-3 buckets)
is inherently spatial, not sequential.

| Region | Placement | Contents |
| :--- | :--- | :--- |
| PO information | Full width, top | PO number, vendor, status, order/expected dates — read-only context strip, same idea as the Linkage Portal's top row |
| PO lines column | Left, 1/3, full height | Every `PurchaseOrderLine` on this PO as a draggable chip/card: part, qty ordered, qty already packaged (running total across all packages in the current session state), qty remaining. A line at zero remaining is visually deprioritized (muted, not hidden — it can still be dragged back out of a package) |
| Package workspace | Right, 2/3 | Create-package form (top) + one card per package, session-new and loaded-existing side by side |

### Create-package form (top of the 2/3 column)

A small, always-present form: tracking number, carrier, shipped date, expected arrival date, notes.
Submitting it does **not** hit the database — it appends a new **session-only** package card to the
workspace below, with a temporary session-local id. This is the "temporarily fill in details to
create a form header" the requester asked for — a provisional header, not a real `Package` row,
until final submit.

### Package cards (the drop targets)

Each package — session-new or loaded-existing — renders as a card: its header fields (editable
inline for session-new packages; loaded-existing ones are editable too, **unless locked**, see §2)
and a drop zone listing its currently assigned lines as chips (part, quantity assigned — quantity is
editable on the chip, a plain number input, not a separate form).

**Locked package cards render read-only** — no drop zone, no draggable chips, no inline field
edits — with a single action: "Edit this package" → `packages/<id>/edit`
([package_edit_and_linkage.md](package_edit_and_linkage.md)). They still occupy their normal spot in
the workspace and their lines still count toward "already packaged" on the left column, so the
Buyer sees the whole PO's picture — they just aren't a place this page lets you drop anything.

**Drag-and-drop is the primary interaction (unlocked packages only):**
- Drag a line chip from the left column into a package card → assigns it (prompts for quantity if
  the full remaining amount isn't intended — default to full remaining).
- Drag a line chip from one package card to another → moves it (removed from source, added to
  target, one gesture).
- Drag a line chip out of a package card and drop it back on the left column (or a small "unassign"
  zone) → removes it from that package.
- Keyboard/no-JS fallback (F5 rule): every drag action has an equivalent explicit control — a
  `<select>` on each line chip ("Assign to: [dropdown of current session packages]") that performs
  the same move via a plain form post. Drag-and-drop is the fast path, not the only path.

---

## 2. Loading existing packages into the session, and the lock rule

On page load, before rendering anything, the session is seeded from the database — this page is
never a blank slate if the PO already has packages:

1. Query every real `Package` on this PO (`PackageContext` / `PurchaseOrderFulfillmentStruct`),
   including `status` and `has_splits` (`decisions.md` D69).
2. For each, write a session entry carrying its real `id`, current header fields, and current lines
   (each with its real `PackageLine.id`).
3. Render each as a package card exactly like a session-new one, **except** it carries a colored
   outline reflecting whether this page is allowed to touch it:

| Outline | Condition | Meaning |
| :--- | :--- | :--- |
| **Green** | `status` is before `Delivered to Local Receiving Location`, **and** `has_splits` is `False` | Edit freely — drag in, out, and between packages, same as a session-new package |
| **Red — locked** | `status` is `Delivered to Local Receiving Location`/`Accepted`, **or** `has_splits` is `True` (either condition alone is enough) | Not editable on this page at all. Read-only card, "Edit this package" link out to [package_edit_and_linkage.md](package_edit_and_linkage.md) |

A `Lost` package is not itself a lock trigger (never delivered, so the first condition doesn't
apply) — it's green unless it independently has splits.

A session-only package (created via the top form, this visit) has **no outline** — it isn't real
yet, there's no lock question to ask.

**This replaces the earlier draft of this page**, which allowed editing a delivered package inline
via a per-move audit-note popup captured during the session and committed at submit. `decisions.md`
D69 simplifies that: this tool now only ever mutates packages that are both undelivered and unsplit,
so **no audit-note capture, no pending-note session state, no submit-time diffing against a red
package's prior state, and no dual-Event posting** need to exist on this page at all — every one of
those concerns still exists, just entirely on
[package_edit_and_linkage.md](package_edit_and_linkage.md), where it's simpler because that page
commits one mutation at a time instead of batching a session.

---

## 3. Why locking beats an inline audit flow here

The original design (still worth understanding, since it's the shape the *edit* page still uses one
mutation at a time) tried to let this page freely mutate a delivered package's lines, deferring
D57/D68's mandatory JSON-snapshot-plus-human-comment requirement into the session and reconciling it
at submit. That worked, but bought real complexity for a case this tool's own common path barely
touches: most packages sorted here are fresh and both undelivered and unsplit (§"Why this page
exists" above) — a session-draft tool paying for same-line-move supersession tracking,
submit-time diffing against pre-loaded state, and cross-package dual-Event posting, entirely to
serve the *rare* case for this specific tool, was solving the wrong problem in the wrong place.

Locking removes all of it: a locked package simply cannot be a drop target, so there is nothing to
diff, nothing to defer, and nothing to reconcile at submit. The audit requirement doesn't go away —
it still applies in full — it just always happens on `package_edit_and_linkage.md`, which was
already going to need it (that page is reachable regardless of delivery status) and already commits
per-mutation rather than per-session, which is the natural place for a "capture the note right now,
write it right now" interaction anyway.

---

## 4. Submit — a single backend class owns the whole decision

One button, end of session (`page_grid_values.md`-appropriate card-footer placement, primary
action). Submission is not a thin view function stitching together calls to `PackageFactory` and
`PackageLineManager` — it's owned end to end by one proposed class,
**`BasicPackageManagerSubmitHandler`**, so the "read the whole page, decide, commit-or-reject-all"
logic exists in exactly one place instead of being reconstructed per entrypoint.

### Contract

```
BasicPackageManagerSubmitHandler(purchase_order_id, actor).submit(payload: dict) -> SubmitResult
```

- **Input is the full dict the page posts** — every session-only package (header fields + line
  list), every unlocked loaded-existing package's current line composition (to diff against what
  §2 seeded), and nothing about locked packages at all (the page never lets them change, so there's
  nothing for the payload to carry about them). One call, one payload, not a sequence of per-package
  requests — this is what makes "reject all" possible in the first place: there is one decision to
  make, not N independent ones that could each partially succeed.
- **Internally, in order:**
  1. Re-derive the seeded state for every referenced existing package from the database (never trust
     the client-echoed "original" state — the session could be stale if something else touched the
     package since page load) and diff it against the payload.
  2. Validate every implied write **before** issuing any of them: quantities positive, no line
     referencing a part not on this PO, no attempt to touch a package the payload's own accompanying
     lock flags say is locked (defense in depth — the UI shouldn't allow this, the handler checks
     anyway), no duplicate line-part collisions this PO's D58 soft-uniqueness rule would reject.
  3. Only if every check across the **entire** payload passes does it open the transaction and
     perform the writes: `PackageFactory.create(...)` per session-only package,
     `PackageLineManager` adds/removes/quantity-changes per unlocked existing package's diff.
- **Output:** a small `SubmitResult` — success with a summary (packages created, packages modified,
  lines moved) for the redirect's flash message, or failure with the specific validation errors,
  keyed to the package/line they belong to so the page can highlight exactly what's wrong when it
  re-renders the still-live session.

### All-or-nothing, explicitly

**If validation fails anywhere in the payload, or the transaction fails for any reason, the entire
submission is rejected — nothing is written, not even the packages/lines that were individually
fine.** The session draft is preserved untouched (this was already true before, restated here
because it's now this class's explicit responsibility, not an incidental side effect of "the
transaction failed so Django rolled back"), and the user is sent back to the still-live page with a
clear notice naming what failed and why — not a generic "something went wrong," since the handler
already knows exactly which package or line tripped which check. This matters specifically because
the page represents a whole multi-decision sorting session: a partial commit would leave the Buyer
unsure which of their several decisions actually landed, which is worse than losing none of them and
trying again with the error in view.

### On success

Redirect to the PO detail page with the `SubmitResult` summary as a flash message — packages
created, packages modified, lines moved — not silently back to a blank state, since this was a
multi-decision session and the user should see what actually happened.

---

## 5. Scenarios (worked examples)

**Scenario A — the common case.** PO with 3 lines, no existing packages. Buyer opens the page,
fills the create-package form twice (Box 1, Box 2), drags all 3 lines across the two boxes (2 lines
in Box 1, 1 in Box 2, no overlap), hits submit. Two `Package` rows are created, no audit prompts
ever appear (nothing pre-existing, nothing red).

**Scenario B — page opened on a PO with packages already in flight, one of them locked.** PO has 2
real packages: one `Shipped` (green, editable), one `Delivered to Local Receiving Location` (locked
— red). Buyer notices a line was miscounted on the delivered package. This page can't help — there's
no drop zone on that card, only an "Edit this package" link. Buyer follows it to
`package_edit_and_linkage.md`, resolves the quantity there (that page's per-mutation flow captures
the required snapshot + human comment immediately), and can return to this page afterward to keep
sorting the still-editable `Shipped` package if there's more to do.

**Scenario C — a line doesn't fit the fast path.** Buyer drags a line into a box, but that line is
actually going to arrive split across this PO and a different PO's line (the vendor consolidated two
orders into one box). This page has no tool for that — the Buyer packages what it can here (or
leaves that line unassigned) and finishes the split in `packages/<id>/edit` after this session's
submit, using that page's PO search tool.

**Scenario D — abandoned session.** Buyer sorts several lines, gets pulled away, session expires
before submit. Nothing was written — reopening the page reseeds from the real database state (§2)
as if the session never happened. No orphaned packages, no partial writes.

**Scenario E — a package that's locked for splits, not delivery.** PO has a package still
`Awaiting Shipment` (never delivered), but a Buyer already ran one of its lines through
`package_edit_and_linkage.md`'s split tool last week to correct a vendor consolidation. That
package's `has_splits` is `True`, so this page renders it locked (red) even though it hasn't shipped
yet — `decisions.md` D69's two lock triggers are independent, and either one alone is enough. The
Buyer can still freely create and sort *other* packages on this page; only the split one is
off-limits here.
