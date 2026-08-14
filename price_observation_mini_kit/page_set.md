---
okf_version: "0.1"
type: "Reference"
title: "Recommended Page Set — Price Observations"
description: "Routes, templates, HTMX fragments, and navigation placement for the price observation system, plus the pages deliberately not built."
tags: [reference, procurement, pricing, routes, frontend]
context_tier: 2
personas: [frontend]
---

# Recommended Page Set — Price Observations

Four real pages, three HTMX fragments, two touched templates. Every route follows the project's
single-canonical-URL rule with `format=` for density and `htmx-*` for fragments, never both in one
request.

---

## Routes

| Route | Method | Purpose |
| :--- | :--- | :--- |
| `/procurement/prices/` | GET | Hub — recent activity, entry points, unpriced count |
| `/procurement/prices/bulk/` | GET, POST | **The main event.** The paste grid |
| `/procurement/prices/unpriced/` | GET | The D86 backstop queue, standalone and linkable |
| `/procurement/prices/parts/<part_id>/` | GET | One part's full price history. **Phase 2, load-bearing** (D91) |

### HTMX fragments

| Route | Returns |
| :--- | :--- |
| `/procurement/prices/suggestion/?part_id=&vendor_id=` | The two-fact chip for one PO line (D91) |
| `/procurement/prices/parts/<part_id>/?format=htmx-picker` | The condensed price picker (D92) — a fragment variant of the history page, not a route of its own |
| `/procurement/prices/divergence/?line_id=` | The divergence prompt beneath a saved PO line |
| `/procurement/prices/bulk/rows/` | Grid row add / remove, re-rendering from the session draft |

All degrade: every state they produce is also rendered server-side on a plain load. The picker's
non-HTMX path is the full history page itself, which is what makes D92 safe under the F5 rule.

Note the picker is **the same canonical URL as the history page** with an `htmx-*` format value,
per the project's one-URL-per-resource contract — never combined with a density value in one
request. Exact parameter naming is a frontend call.

---

## 1. `/procurement/prices/` — hub

Small landing page, following the pattern of the existing app hubs.

- **Unpriced parts** — count, with a link into the queue. The number is the page's whole reason to
  exist; a standing "47 parts have no price on record" is what makes the work visible. Note per D87
  this count is **viewer-relative** — a part priced only for East Coast is unpriced for a West-only
  actor. Correct, but expect to explain it.
- **Unverified assertions** — for actors holding establish authority, the count of recorded prices
  that disagree with the established price in their domains (D89). This is the whole of their
  review workload; no approval inbox is built, because the rows already exist and this is a filter
  over them.
- **Recent observations** — last ~10 across the actor's visible domains, showing part, vendor,
  price, and age.
- **Actions** — *Record prices* (into the bulk grid), *Browse unpriced*.

Skippable if it feels thin. If you drop it, the bulk grid becomes the entry point and the unpriced
count moves into the procurement nav as a badge. That is a defensible smaller build — but the hub is
where the unpriced count gets seen by someone who was not already looking for it, which is most of
its value.

### Template

`app/procurement/templates/procurement/prices/hub.html`

---

## 2. `/procurement/prices/bulk/` — the paste grid

Fully specified in [bulk_observation_screen.md](bulk_observation_screen.md). Summary of what the
template must carry:

- Batch-level header bar: vendor (searchable + inline create), domain, `observed_at`, source type.
- The grid: part identity read-only, quantity and unit cost editable, one row remove control.
- The three doors: recent-creations banner, unpriced filter, part search.
- Footer: row count, priced count, *Add parts*, *Save all*.
- Session-draft backed, so F5 re-renders identically.

Per the always-render rule the grid card renders with zero rows, showing its header, an explicit
empty state, and the three doors — never hidden behind `{% if rows %}`.

### Templates

```
procurement/prices/bulk.html                 page shell
procurement/prices/_grid.html                the grid card (HTMX target)
procurement/prices/_recent_banner.html       the breadcrumb offer
procurement/prices/_vendor_picker.html       reusable, mirrors _manufacturer_picker.html
```

`_vendor_picker.html` deliberately mirrors the existing
[`parts/manufacturers/_manufacturer_picker.html`](../app/parts/templates/parts/manufacturers/_manufacturer_picker.html)
— same interaction, same shape, and the two entities are near-identical anyway (which is the D79
argument in miniature).

---

## 3. `/procurement/prices/unpriced/` — the backstop queue

A real, standing, filterable list: parts in the actor's visible domains with zero observations.

Columns: part number, name, domain(s), created date, and a **Price it** action that adds the row
straight to the bulk grid. Multi-select with *Add selected to grid* for working a batch.

Filters: domain, created-since, part type. Sort by age descending — oldest unpriced first is the
right default, because those are the ones that have been invisible longest.

This page is load-bearing (D86), not a convenience. It is what makes the session breadcrumb's
failure modes — cross-device, the last-write-wins race, cap overflow — into non-events rather than
silent data loss. **Ship it in phase 1, in the same PR as the grid.**

### Template

`app/procurement/templates/procurement/prices/unpriced.html`

---

## 4. `/procurement/prices/parts/<part_id>/` — one part's price history

The audit view, the page that makes the append-only design (D80) pay off, and — since **D91** — the
pressure valve that absorbs every piece of display complexity taken out of the suggestion chip. It
is no longer a nice-to-have opened when someone disputes a number; the chip's doorway points here,
so it **ships in phase 2 with the chip**.

- Header: part identity, and per vendor the two facts the chip shows — most recent recorded, most
  recent verified.
- Table: every observation the actor can see, across **all vendors and all their visible domains** —
  date, vendor, domain, quantity, unit cost, confidence band, verified badge, source type, who
  recorded it, notes. Sorted newest first.
- Filters on vendor and domain as first-class columns, not an afterthought. This is now a working
  screen, not a log dump.
- A sparkline or simple line chart per vendor over time, if it is cheap. Genuinely useful for
  spotting a vendor creeping upward, but do not let it hold up the table.
- Link back to the source PO line where `source_po_line` is set. That link is also how quantity-break
  pricing gets investigated after the fact — plotting line total against quantity ordered reveals a
  break curve that no per-row suggestion could have known about.
- For actors holding **establish** authority in a row's domain (D89): a *verify* action, which
  **appends a verified row** rather than editing the existing one.

### `format=htmx-picker` — the condensed variant (D92)

The same resource, rendered as a modal-ready selection list:

- Client-side searchable over vendor and domain. No server round-trip per keystroke.
- **50 rows maximum, most-recent-first, verified rows badged.** Recency is what a buyer scans for;
  the badge carries authority without reordering the list.
- **Honest about the cap** — *"Showing 50 of 128 — open full history →"*. A truncated list that
  hides its truncation teaches people the data is missing.
- Opens **unfiltered**. The chip already gave them the vendor's number; filtering back down to that
  vendor would make the button pointless.
- Selecting a row returns **the value only** — no provenance chain. The line records the Buyer's own
  confidence and today's date. See D92 for why a false provenance is worse than none.

This is legitimate modal use under the project's rule: nothing is being *assigned* to the record
under edit. It is read-only browsing plus a single-value capture, which is exactly what modals are
for.

Per the always-render rule, the picker renders with its search box and an explicit *"no prices on
record"* state rather than an empty box.

### Templates

```
procurement/prices/part_history.html          full page
procurement/prices/_price_picker.html         the htmx-picker fragment
```

---

## Touched templates

### PO line editing — the suggestion chip

`app/procurement/templates/` PO wizard and line-edit templates gain the chip beside each cost field,
plus the divergence prompt slot beneath each saved line. See
[purchase_order_integration.md](purchase_order_integration.md).

### Part detail — a pricing card

`app/parts/templates/parts/detail.html` wants a pricing summary. This runs into the same boundary
the whole kit is navigating, and there are two honest options:

| Option | Trade-off |
| :--- | :--- |
| **A. Link out.** A card with "View price history →" pointing at `/procurement/prices/parts/<id>/` | Zero coupling. The card shows no actual prices, which makes it close to useless |
| **B. `hx-get` include.** The card is an empty shell in the parts template that pulls a procurement fragment with `hx-trigger="load"` | Real data, and the coupling is one URL in a template — weaker than the session inversion already accepted in D81. But the card is empty for one paint, and it is decoration arriving after load rather than content rendered with the page |

**Recommendation: B**, and note it against the F5 rule explicitly — the page *works* on plain reload
(the fragment re-fires), the card just fills in a beat later. If that violation bothers you more
than the emptiness of A, take A and let the price history page carry the weight; the link is one
click and this is not a page anyone lives on.

Worth deciding deliberately rather than by accident, since whichever you pick sets the precedent for
every future cross-app card.

---

## Navigation

- **Procurement nav** gains a **Prices** item pointing at the hub (or straight at the bulk grid if
  the hub is dropped), with the unpriced count as a badge. The badge is the whole point — it makes
  outstanding work visible to people who were not looking for it.
- **Part detail** gains the pricing card above.
- **Vendor detail** gains a "Prices from this vendor" section, backed by the
  `ppo_vendor_recent_idx` index. Cheap, and it is the natural place to answer "what does Acme charge
  us for things."
- **Part-create success state** gains a secondary action — *"Add prices for these 3 parts →"* —
  next to *View part*. A **click, not a redirect**: auto-redirecting into a pricing grid hijacks the
  flow for everyone who does not have prices to enter.

---

## Deliberately not built

| Page | Why not |
| :--- | :--- |
| Vendor price list / catalog manager | D79's scope note. Unless vendors send machine-readable price files, a hand-maintained catalog rots worse than PO lines do — nothing forces anyone to touch it. Observations are self-maintaining because they only exist when something happened |
| Price approval workflow | Approval belongs on the PO (`approval_state`), not on an observation. An observation is a *record that something was true*, and records are not approved |
| Price editing UI | The table is append-only (D80). A wrong observation is corrected by appending a better one, which is exactly what the divergence prompt does. No edit screen, no delete screen |
| Per-row vendor override on the grid | D83. Two vendors means two saves. Add it only if someone actually asks |
| Cross-part bulk price adjustment ("+5% on everything from Acme") | A real request eventually, and a genuinely different feature — it writes many speculative observations at once with no human having observed any of them. Do not let it in through this door |
