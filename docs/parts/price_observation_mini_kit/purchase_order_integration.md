---
okf_version: "0.1"
type: "Explanation"
title: "How Price Observations Inform the Purchase Order Process"
description: "The suggestion chip on PO lines, the divergence prompt, pricing basis as a header state, receipt reconciliation, and the variance check that catches drift."
tags: [explanation, procurement, purchase-orders, pricing]
context_tier: 2
personas: [backend, frontend, business]
---

# How Price Observations Inform the Purchase Order Process

Observations exist to change what happens on a purchase order. This document is the payoff.

The through-line: **a price is never presented as a bare number again.** Every price on a PO line
carries where it came from and how old it is, and every divergence from expectation is either
recorded or explicitly waved through.

---

## 1. Part selection on a PO line

When a Buyer selects a part on a PO line, an HTMX fragment renders a suggestion chip beside the cost
field. Per **D91** it shows **two facts and a doorway**, both scoped to the PO's vendor and to the
actor's visible domains:

```
Part  [ AB-1042  Bearing 6205        ▾ ]    Unit cost  [        ]

      ⓘ $14.20  recorded by J. Alvarez, 2 days ago
        $12.50  verified · East Coast · 12 Mar 2026     [ Use this ]
        4 prices on record for this part →
```

| State | Chip reads | Fills the field? |
| :--- | :--- | :--- |
| Recorded and verified differ | both lines, as above | verified on click; recorded on click |
| They are the same row | **one** line, badged verified | on click |
| Vendor has verified only | that line | on click |
| Vendor has recorded only | that line, marked unverified | on click |
| Nothing from this vendor | *No price from Acme — 4 prices from other vendors →* | doorway only |
| Nothing at all | *No price on record* | — |

Three properties do the work:

- **Both numbers are the PO's vendor's.** That is what keeps **Use this** always safe to click. A
  cross-vendor price is never one click from a cost field; it is behind the doorway, where taking it
  is a deliberate act (D92).
- **Collapse when they agree.** A chip that always shows two numbers trains people to stop reading
  it.
- **The gap is the signal.** When recorded and verified disagree, someone in the field is seeing
  something the established price does not reflect. That is the drift this kit exists to catch,
  visible at a glance rather than buried inside a ranking function.

Even here, filling is only **on click**. Silent autofill was the original temptation and is the
thing this design refuses: a number that appears by itself looks exactly as authoritative as one
someone verified, which is the mechanism that produces stale PO prices in the first place.

Clicking **Use this** copies the value and stamps `unit_cost_source` (`LAST_PAID` for an `INVOICED`
source, `LAST_ORDERED` for an `ORDERED` one), `unit_cost_asserted_at` from the observation's
`observed_at` — **not** today's date — and prefills `unit_cost_confidence` from the observation's
own band. That is what lets the line later render *"$12.50 — last paid 14 months ago, ±10%"* rather
than pretending the price is fresh and exact.

The Buyer may lower that confidence before saving; the system never lowers it for them (D88).

### The doorway — cross-vendor prices

*"4 prices on record for this part →"* opens the **price picker** (D92): a condensed, client-side
searchable fragment of the part history page, capped at 50 rows, most-recent-first with verified
rows badged, opening unfiltered across vendors and every domain the actor can see. Picking a row
returns the **value only**, landing as `ESTIMATED` with today's date and the Buyer's own confidence
— because the picker is cross-vendor and a provenance stamp there would assert a relationship that
never existed.

Full shape in [page_set.md](page_set.md).

### Who may do what

Per **D89**, the chip renders the same for everyone, but the field does not:

- **Use**-level actors may click **Use this**, and may type a price only when the chip shows none
  (the soft lock, D90).
- **Record**-level actors may type any number.
- Nobody edits an established price from a PO line. That happens by appending, below.

### Triggers

- Part selected or changed → resolve that line.
- **The PO's vendor changed → re-resolve every line.** Both of the chip's facts are vendor-scoped,
  so changing vendor invalidates the whole order at once, and a chip still showing the old vendor's
  price is worse than no chip.
- Plain page load → resolve server-side for every line already present. The chip must render
  without HTMX; per the F5 rule it is decoration, never the only path to a price.

`PartPricePolicy.suggest_many()` exists for exactly the second and third cases.

---

## 2. The divergence prompt

When a Buyer saves a line at a price different from the suggestion that was showing, an inline
fragment appears beneath the line:

> You entered **$14.20**; the last Acme price was **$12.50** (+13.6%).
> `[ Record $14.20 as the current Acme price ]` `[ Just this order ]`

- **Record** appends a `MANUAL` observation — part, the PO's vendor, the PO's domain, `observed_at`
  = today, the Buyer's confidence band, notes referencing the PO number — and sets
  `unit_cost_source = QUOTED`. Per D80 there is no stored price to update; appending *is* the
  update, and the history survives.
- **Just this order** sets `unit_cost_source = ESTIMATED` and writes nothing else.

**The two buttons are the two acts of D89**, and this is where the authority split becomes visible:

| Level | Sees |
| :--- | :--- |
| **Use** | No prompt. They cannot diverge from an existing price in the first place (D90) |
| **Record** | Both buttons. **Record** writes an *unverified* observation — permanent, and ranked below the established price rather than replacing it |
| **Establish** | Both buttons, and **Record** writes a verified row for their domain |

That a Record-level Buyer's assertion does not silently become everyone's price is the entire point
of the split — and that it is still *written* is why the knowledge is not lost at the desk of the
person who had it.

Details that decide whether this is useful or hated:

- **Threshold.** Do not prompt under ~1%, or under ten cents absolute drift. Rounding noise
  trains people to click through without reading, which destroys the value of every prompt after it.
- **Sticky dismissal.** Per line, per session. Nobody gets nagged twice about the same line.
- **Never blocking.** The line saves either way. The prompt is an offer to capture knowledge, not a
  gate on doing work.

This is the highest-leverage part of the whole kit: it turns the moment a Buyer *notices* a price is
wrong into the moment the system *learns* the right one, at the cost of one click, inside work they
were already doing.

---

## 3. Pricing basis — derived, never declared

Sometimes a PO genuinely is "tell this person to go buy these things." Pretending its totals are
contractual is a fiction the system currently enforces, and it is why the numbers drift.

The original proposal was a `FIRM` / `ESTIMATED` header field on `PurchaseOrder`. **D88 replaces
it.** A header field is something a human sets once and then forgets, and a stale "FIRM" flag on an
order full of guesses is worse than no flag at all — it is a second thing that can lie.

Instead the basis falls out of the lines. Every line carries a confidence band, so:

- All lines `QUOTED` → the order is firm. Its total is a commitment.
- Any line at `P100` or `UNKNOWN` → the order is a shopping list, and says so **without anyone
  having declared it**.

A draft PO renders an honest total:

> **$4,210.00** — could be $3,400 to $5,600. 6 of 9 lines are estimates.

instead of presenting a fiction as a figure. That is a range an approver can actually reason about,
which a single `ESTIMATED` badge never was.

This still plugs into the existing approval axis (`approval_state`, D71/D76): approving an order
whose total carries a range is approving a **ceiling**, not line prices. Which is honestly how small
operations already work — the control that matters is variance against a budget, not per-line price
approval.

**Scoped as a follow-on, not first-cut.** It needs `unit_cost_confidence` (D88) to exist and to have
real data in it. Sequence it after the suggestion chip lands.

---

## 4. Writing observations back from the PO lifecycle

Two automatic writers, both later phases, both closing the loop that makes the ladder improve on its
own:

### `ORDERED` — at placement

`PurchaseOrderContext.place()` appends one observation per line: part, the PO's vendor, the PO's
domain, `unit_cost`, `quantity_ordered`, `observed_at` = `order_date`, `source_po_line` set, and
`confidence` carried across from the line's `unit_cost_confidence` — an order placed on a guess
records a guess, not a fact. Written **unverified**: placing an order is not an act of establishing
a price (D89).

Cheap, and it means the ladder starts working for a part the first time anyone buys it, with no
extra data entry at all. This is the single highest-value automatic writer and should land as soon
as the table exists.

### `INVOICED` — at receipt

When a package arrives with an invoice or packing slip, a human is holding the real number. A
reconciliation step at receipt:

> Line 3 ordered at **$0.00 (unknown)**; invoice says **$14.20**. `[ Accept ]` `[ Correct ]`

Accepting writes an `INVOICED` observation at `QUOTED` confidence — the person has the paper in
their hand, which is the only moment that band is honestly earned — and trues up the line on an
order whose total was a range.

This is what dissolves the cold-start problem properly. The first PO for a new part can honestly say
"price unknown," and the system learns the real number a week later from the person who has the
paper in their hand — the only place a price is ever reliably accurate. Cold start stops being "we
must know the price up front" and becomes "we will know it shortly."

**Blocked on the package-receipt UI, which does not exist yet.** Design it now, build it when
receiving does.

### Ranking, once both exist

`INVOICED` is strictly better evidence than `ORDERED`. The first cut picks "most recent recorded"
and "most recent verified" by date alone (D91), which means a recent `ORDERED` row can be shown over
an older `INVOICED` one. Acceptable while `INVOICED` rows do not exist. Once receipt reconciliation
ships, weight `source_type` when choosing which row is the *recorded* fact — a small, contained
change to `PartPricePolicy` and nothing else. The *verified* fact is unaffected: verification is an
explicit human act, not something inferred from source.

---

## 5. Variance detection — where drift finally gets caught

With ordered and invoiced prices both on record, the check that has never been possible becomes
trivial: if a received unit cost exceeds the ordered one by more than a threshold (percentage or
absolute), post a machine comment on the PO's `Event` and require acknowledgement before the line
closes.

The PO already has exactly the right machinery — one `Event` per PO for its whole lifetime, carrying
status history as machine comments (D17–D19). A variance note is one more machine comment on a
thread that already exists. Nothing new to build but the comparison.

This is the actual answer to "purchase orders get grossly out of sync." Today nothing ever compares
the ordered price to the paid price, so the drift is invisible **by construction** — not because
anyone is careless. Once the comparison exists and lands somewhere a human reads, drift becomes an
exception queue rather than an accumulating silent error.

---

## Sequencing

| Phase | Contents | Blocked on |
| :--- | :--- | :--- |
| 1 | Table, guard, factories, bulk grid, breadcrumb, unpriced filter, confidence bands | nothing |
| 2 | Provenance + confidence columns on the line, `PartPricePolicy`, suggestion chip, **part history page and picker** | phase 1 |
| 3 | Divergence prompt, the use/record/establish split (D89–D90) | phase 2 |
| 4 | `ORDERED` writer at `place()` | phase 1 (can run parallel to 2–3) |
| 5 | Derived pricing basis, ranged-total rendering | phase 2 |
| 6 | Receipt reconciliation, `INVOICED` writer, source ranking, variance check | package-receipt UI |

The history page and its picker move **into phase 2** (D91). They are not an audit nicety — they are
the pressure valve absorbing the display complexity taken out of the chip, and the chip's doorway
points nowhere without them.

Phases 1 and 4 are independently useful and together produce a system that gets better every time
someone places an order, before any of the UI polish in 2–3 exists.
