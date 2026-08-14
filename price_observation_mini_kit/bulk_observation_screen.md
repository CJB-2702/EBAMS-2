---
okf_version: "0.1"
type: "Explanation"
title: "The Bulk Price Observation Screen"
description: "The paste grid: three entry doors, batch-level vendor/domain/date header, a single pasteable cost column, and how it consumes the parts-creation breadcrumb."
tags: [explanation, procurement, pricing, ux, htmx]
context_tier: 2
personas: [frontend, backend]
---

# The Bulk Price Observation Screen

`/procurement/prices/bulk/`

One page where a user turns a quote into price history. It is the **only** write path for
`PART_CREATE`, `QUOTE`, and manually entered `MANUAL` observations.

Its design premise: the data already exists, in a spreadsheet, in one column. The screen's job is to
accept a paste, not to make someone retype twenty numbers into twenty form fields.

---

## Three doors in

Ranked by how precisely the user has told us what they want:

| Door | Precision | When it fires |
| :--- | :--- | :--- |
| **Recent-creations banner** | recent, confirmed | The user just created parts and wandered in |
| **Unpriced-parts filter** | everything outstanding | The standing work queue |
| **Direct part search** | exact | "I have a quote for these three specific parts" |

### Door 1 — the recent-creations banner

Read from the session breadcrumb (see
[parts_creation_smuggling.md](parts_creation_smuggling.md)). **Never auto-seed the grid.** Render a
banner and wait for a click:

> **You created 3 parts in the last hour.** — `[Load them into this grid]` `[Dismiss]`

Not auto-seeding is what makes the breadcrumb's three failure modes harmless. Wrong-tab contribution
becomes a dismissible banner instead of a wrong grid; a stale batch is visibly labelled with its age
before anything happens; double-seeding is clicking an idempotent button twice.

Dismissal is per-session and sticky. Nobody should be nagged about the same batch twice.

The banner also carries the overflow state when `overflowed` is set:

> **Recent-creation list is full (100 parts).** Newer parts are not listed here — use
> **Unpriced parts** to find them.

### Door 2 — the unpriced-parts filter

A real query, not session state: parts within the actor's visible domains with **zero**
`PartPriceObservation` rows. This is D86 — the correctness backstop that makes every session-path
failure mode a non-event. It is always available from the page's own filter bar, and it is what a
user reaches for when the banner is empty because they are on a different device, or because a race
dropped a row, or because the cap overflowed.

### Door 3 — direct search

The ordinary case of "I got a quote, let me find these parts." Standard part search
(`app/parts/presentation_layer/search/part_search.py` already exists), adding rows to the grid.

All three doors add rows to the **same grid**. They are additive, not modes — a user can load the
banner batch, then search up two more parts, and commit all of it together.

---

## Layout

Batch-level fields sit in a header bar above the grid (**D83**), because the realistic case is one
quote, from one vendor, on one day:

```
┌─ Price observations ──────────────────────────────────────────────┐
│  Vendor  [ Acme Industrial      ▾ ] [+ new]                       │
│  Domain  [ Fleet Operations     ▾ ]   Observed  [ 2026-08-09 ]    │
│  Source  [ Quote               ▾ ]   Confidence [ Quoted      ▾ ] │
├───────────────────────────────────────────────────────────────────┤
│  Part                        Qty        Unit cost                 │
│  AB-1042  Bearing 6205      [     ]    [   12.50 ]           [×]  │
│  AB-1043  Bearing 6206      [     ]    [    8.00 ]           [×]  │
│  AB-1044  Seal, 40mm        [     ]    [        ]            [×]  │
├───────────────────────────────────────────────────────────────────┤
│  3 rows · 2 priced                    [ Add parts ] [ Save all ]  │
└───────────────────────────────────────────────────────────────────┘
```

That collapses the paste target to **one column of numbers**, which is the shape of what is sitting
in the user's spreadsheet. Per-row vendor/domain/date override is explicitly not in the first cut;
two batches means two saves, which is fine.

**Domain defaults** to the part's creation domain when the breadcrumb carried one (`domain_ids`),
otherwise to the actor's primary domain. It is **required** — blank is not a choice (D87). There is
no global tier; a price observed for East Coast reaches a West Coast buyer who can see both domains,
carrying its origin with it, rather than being laundered into a placeless number.

**Confidence** is also batch-level and required (D88). A quote in hand is `Quoted`; a number someone
read off a two-year-old catalogue page is not, and the person pasting the column is the only one who
will ever know which. Defaulting it to `Quoted` would quietly manufacture certainty — default to
whatever the batch's `Source` implies, and make it a visible field they can see is set.

**Observations recorded here are unverified** unless the actor holds establish authority for the
chosen domain (D89), in which case they are written verified. Nothing about the screen changes; only
what the row means afterwards does.

Per the project's always-render rule, the grid card renders even with zero rows, showing its header
and an explicit empty state plus the three doors.

---

## Paste handling

Roughly fifteen lines of vanilla JS, no library:

1. Intercept `paste` on any cell in the grid.
2. `split("\n")` then `split("\t")`.
3. Walk down and across from the focused cell, filling as you go.
4. Stop at the grid edge — never create rows implicitly. A paste longer than the grid fills what
   fits and reports *"14 values pasted, 3 ignored — grid has 11 rows."*

Two-column pastes (`qty \t cost`) fall out of the same split for free.

Normalize aggressively on the way in: strip `$`, thousands separators, and whitespace; accept
`1,234.56` and `1234.56`. A user pasting from Excel has currency formatting and should not have to
care.

---

## Validation and commit

Client side is convenience only. The real rules live in `PartPriceObservationGuard`:

| Rule | Behaviour |
| :--- | :--- |
| Row with no `unit_cost` | **Dropped silently** — mirrors the `if not mpn: continue` pattern in [`PartCreationWizardAdaptor._supplier_item_rows`](../app/parts/control_layer/adapters/part_creation_wizard_adaptor.py) |
| Row with a cost | Vendor, domain, and confidence all required (batch-level satisfies them), `unit_cost >= 0`, `quantity > 0` or null |
| `observed_at` in the future | Rejected — you cannot observe tomorrow's price |
| Part not in the actor's visible domains | Rejected. Re-checked at commit, not just at load |
| Exact duplicate of an existing row | **Warn, allow.** Two people entering the same quote is legitimate; the table has no unique constraint by design |

Commit is one `PartPriceObservationBulkFactory.create_many()` call in a single transaction. All or
nothing — a grid that half-saves is worse than one that fails.

On success: `consume(request, part_ids=...)` clears those parts from the breadcrumb, and the page
re-renders with a summary — *"7 observations recorded for Acme Industrial."* Rows that were dropped
for having no price are listed by part number, so nobody silently loses work they thought they did.

---

## F5 behaviour

The grid is backed by a **session draft**, the same pattern as
[`po_wizard_draft.py`](../app/procurement/presentation_layer/tools/po_wizard_draft.py): a raw mutable
dict accumulated across requests, never validated, distinct from the one-shot adaptor that validates
at final submit.

That gives the F5 rule for free. Adding rows, removing rows, and changing the header bar are HTMX
interactions that mutate the draft and re-render the card; a plain reload re-reads the draft and
renders the identical page. HTMX is layered on top, never load-bearing.

The draft key is separate from the breadcrumb key — the breadcrumb is *what parts exist*, the draft
is *what the user is currently typing*. Conflating them would mean a half-typed grid could
resurrect parts the user had already priced.

---

## Where CSV would slot in later

[`part_bulk_upload_adaptor.py`](../app/parts/control_layer/adapters/part_bulk_upload_adaptor.py) has
no price columns today. When optional `unit_cost` / `vendor` columns are added, the bulk upload can
carry prices through the breadcrumb and the grid arrives **pre-filled** — the user just confirms.

That is also the one case where the rejected HTTP-handoff design (D81) would earn its keep, since
the payload would carry more than IDs. Worth revisiting *only* at that point; not now.
