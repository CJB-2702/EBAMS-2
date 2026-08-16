---
okf_version: "0.1"
type: "Procedure"
title: "Front-End Build Plan — Part Price Observations"
description: "Executable front-end instructions for the price observation kit: entrypoint contracts, the format= route table, every template with its context shape, the two-fact chip and picker insertion points, navigation wiring, the vanilla-JS inventory, and a verification checklist."
tags: [procedure, procurement, pricing, frontend, htmx, build-plan]
context_tier: 2
personas: [frontend, backend]
---

# Front-End Build Plan — Part Price Observations

**Audience:** an implementing agent building the *screens*. The schema and the write path already
exist; nothing in this document adds a column or a factory.

**Read before starting:** [README.md](README.md) (decisions D79–D92), then
[build_plan.md](build_plan.md) — **especially §1, the kit-drift corrections**, which override the
prose in `bulk_observation_screen.md` and `page_set.md` wherever they disagree. Then
[bulk_observation_screen.md](bulk_observation_screen.md), [page_set.md](page_set.md),
[purchase_order_integration.md](purchase_order_integration.md), and `harness/UX_UI.md`.

**This document overrides `page_set.md` where they differ.** `page_set.md` is design prose written
before the control layer existed; the signatures quoted in §2 below are read out of the working
tree.

---

## §0 — What is already built (2026-08-10)

Verified against the working tree. Do not rebuild any of it.

| Landed | Where |
| :--- | :--- |
| `PartPriceObservation`, `PriceSourceType`, `PriceConfidence`, `UnitCostSource` | `app/procurement/models/pricing/` |
| `unit_cost_source`, `unit_cost_asserted_at`, `unit_cost_confidence` on `PurchaseOrderLine` | `app/procurement/models/purchasing/purchase_order_line.py` |
| `PERM_PRICE_ESTABLISH`, `can_establish_price`, `require_buy_prices` | `presentation_layer/tools/procurement_access.py` |
| `PartPriceObservationValidator` (+ `DuplicateObservationWarning`) | `control_layer/guards/part_price_observation_guard.py` |
| `PartPriceObservationFactory`, `PartPriceObservationBulkFactory` (+ `PriceObservationInput`, `BulkObservationResult`) | `control_layer/factories/` |
| `PartPriceGridAdaptor` (+ `ParsedGrid`), money parsing, session handoff | `control_layer/adapters/part_price_grid_adaptor.py` |
| `PartPriceNarrator` | `control_layer/narrators/part_price_narrator.py` |
| 14 tests | `app/procurement/tests/test_price_observations.py` |

**Not built, and this plan builds it:** every session tool, every search module, every entrypoint,
every URL, every template, and the PO-line chip. `control_layer/policies/` exists as an empty
directory — `PartPricePolicy` is still to be written (§7).

---

## §1 — Ground rules

1. **The F5 rule is absolute.** Every state an HTMX interaction produces must also render on a plain
   GET of the same URL. The grid, the banner, the chip, and the picker each have a non-HTMX path;
   if you cannot describe it, you have designed it wrong.
2. **One canonical URL, `format=` chooses the representation.** No fragment-only routes. Never
   combine a density value (`condensed`/`medium`/`large`) and an `htmx-*` value in one request.
   The precedent to copy is `demands.py`'s `_left_heavy_pool_fragment` — one view, branching at the
   top on `request.GET.get("format")`.
3. **Permission gating lives in the entrypoint, not the template.** `require_buy(request)` first
   line of every price view. Templates use `can_establish` from context to decide whether to *draw*
   a control — they never decide whether it is *allowed*.
4. **Cards always render.** Zero-row grid, empty unpriced queue, a part with no observations, a
   picker with nothing in it — each renders its header and an explicit empty state. Never
   `{% if rows %}` around a card.
5. **Domain filtering is a security boundary.** `domain_ids = accessible_domain_ids(request)` is
   read in the entrypoint and passed down as `list[int]`. No template, search module, or control
   class ever touches `request` or the session to get it.
6. **Sharp corners, Bulma chrome, Material icons.** Copy the shapes already in
   `procurement/hub.html` and `procurement/demands/index.html`. No new colour scales, no pill
   buttons, no third-party JS.
7. **The narrator owns every price phrase.** No template does date maths or writes "14 months ago"
   itself. If a phrase is missing, add a method to `PartPriceNarrator` — do not inline it.
8. **`price_establish` changes what a control *means*, never where it is.** The grid looks identical
   for both authority levels; only the *Record as verified* checkbox appears or does not (D89).

---

## §2 — The contracts the templates consume

These are read out of the built code. Field names in the grid template must match exactly, or the
adaptor silently drops rows.

### 2.1 Grid POST field names — `PartPriceGridAdaptor.from_post`

| Field | Notes |
| :--- | :--- |
| `vendor_id`, `domain_id` | Batch header. `domain_id` is **required** (D87) — no "global" option |
| `observed_at` | `<input type="date">`, ISO |
| `source_type` | a `PriceSourceType` value (lowercase snake) |
| `confidence` | a `PriceConfidence` value. Required, **no default** (D88) |
| `notes` | batch-level; copied to every row |
| `record_as_verified` | checkbox, `on`. Render **only** when `can_establish` |
| `row_count` | hidden input; the adaptor iterates `range(row_count)` |
| `rows-<i>-part_id` | hidden. A row missing this is skipped entirely |
| `rows-<i>-quantity` | optional |
| `rows-<i>-unit_cost` | blank ⇒ row dropped, `part_id` returned in `dropped_part_ids` |

`row_count` must equal the number of rendered rows including any the user removed client-side —
easiest correct answer is to re-render the grid server-side from the draft after every add/remove,
which the HTMX design below does anyway.

### 2.2 What comes back

```python
ParsedGrid(rows, dropped_part_ids, errors)          # adaptor, parse-level errors
BulkObservationResult(created_ids, warnings, dropped_part_ids)   # factory, on success
ProcurementValidationError(errors: list[str])       # raised; messages are "Row 3: ..."-prefixed
DuplicateObservationWarning(part_id, existing_observation_id, message)
```

Warnings are **not** errors — the save succeeded. Render them as `is-warning is-light` beneath the
success notification, never as a blocking dialog.

### 2.3 `PartPriceNarrator`

`describe_recorded(vendor_name=, observed_at=)`, `describe_verified(vendor_name=, domain_name=,
observed_at=)`, `describe_absent(vendor_name)`, `staleness(observed_at)`.

---

## §3 — Prerequisites: two session tools and three search modules

These are backend files, but they are the front-end's inputs and nothing renders without them.
Build them first, in this order.

```
app/procurement/presentation_layer/tools/recent_part_creations.py       NEW
app/procurement/presentation_layer/tools/price_grid_draft.py            NEW
app/procurement/presentation_layer/search/part_visibility.py            NEW
app/procurement/presentation_layer/search/unpriced_part_search.py       NEW
app/procurement/presentation_layer/search/part_price_history_search.py  NEW
app/parts/presentation_layer/entrypoints/parts.py                       EDIT — one call
app/parts/presentation_layer/entrypoints/parts_bulk_upload.py           EDIT — one call
```

Build `recent_part_creations.py` exactly as [parts_creation_smuggling.md](parts_creation_smuggling.md)
specifies — the `# DELIBERATE ANTI-PATTERN (D81)` header verbatim, three public functions
(`record_created_parts`, `read_recent`, `consume`), a module-private `SESSION_KEY`, append-never-
replace with a 100-part cap and an `overflowed` flag, whole-key reassignment (never nested
mutation), and `transaction.on_commit` at both call sites. `read_recent` re-runs the visibility
predicate and drops missing parts **silently**.

`price_grid_draft.py` copies `po_wizard_draft.py`'s shape — `empty_draft()`, `load(session)`,
`save(session, draft)`, `clear(session)`, plus `add_rows`, `remove_row`, `set_header` — and uses a
**separate session key from the breadcrumb**. The dict shape is `PartPriceGridAdaptor.to_session()`'s
output, so the handoff is a plain `from_session(raw)`.

`part_visibility.visible_parts_qs(*, domain_ids)` is build_plan.md §2.4, written **once**.
`UnpricedPartSearch` is build_plan.md §6.2. `PartPriceHistorySearch` returns one part's observations
across all vendors and the actor's visible domains, `select_related("vendor", "domain",
"created_by", "source_po_line")`, newest first, with optional `vendor_id` / `domain_id` filters and
a `limit`.

---

## §4 — Routes and fragments

```
app/procurement/urls_prices.py    NEW
app/procurement/urls.py           EDIT — path("prices/", include("app.procurement.urls_prices"))
```

Follow the wave pattern (`demands/`, `purchase-orders/`, `packages/`), **not** the flat
`vendor_index` / `vendor_create` lines, which predate the convention.

| URL | Name | Methods | Purpose |
| :--- | :--- | :--- | :--- |
| `/procurement/prices/` | `price_hub` | GET | Counts, recent activity, entry points |
| `/procurement/prices/bulk/` | `price_bulk_grid` | GET, POST | The paste grid |
| `/procurement/prices/unpriced/` | `unpriced_parts` | GET | D86 backstop — ships now |
| `/procurement/prices/parts/<int:part_id>/` | `part_price_history` | GET, POST | History; POST is *verify* |

### `format=` values

| URL | `format=` | Returns |
| :--- | :--- | :--- |
| `price_bulk_grid` | `htmx-grid` | The grid card, re-rendered from the draft (add/remove row, header change) |
| `price_bulk_grid` | `htmx-part-results` | `<search-dropdown>` results for door 3 |
| `price_bulk_grid` | `htmx-vendor-results` | `<search-dropdown>` results for the vendor field |
| `part_price_history` | `htmx-picker` | D92's modal picker fragment |
| `part_price_history` | `htmx-chip` | The two-fact chip for one PO line — requires `vendor_id=` |
| `part_price_history` | `htmx-card` | The part-detail pricing card (option B, §8.4) |
| `unpriced_parts` | `htmx-results` | The results table only, for the filter bar |

The chip and the picker are **format variants of the history resource**, not routes of their own —
that is what makes them satisfy the F5 rule: their non-HTMX fallback is the history page itself.

---

## §5 — Entrypoints

```
app/procurement/presentation_layer/entrypoints/prices.py   NEW
app/procurement/presentation_layer/entrypoints/shell.py    EDIT — unpriced count on the hub
```

Every view opens the same way:

```python
@require_http_methods(["GET"])
def price_hub(request: HttpRequest) -> HttpResponse:
    require_buy(request)
    domain_ids = accessible_domain_ids(request)
    ...
```

`require_buy` raises `PermissionDenied` (403), never a silent no-op. `require_buy_prices` is the
alias named for the recording call sites — use it on `price_bulk_grid`'s POST so the intent reads
at the call site.

Format branching sits at the top of the view, before any expensive query, in a private
`_..._fragment(request, *, domain_ids)` helper per variant. Copy `demands.py`'s layout.

### Context contracts

| View | Context |
| :--- | :--- |
| `price_hub` | `unpriced_count`, `unverified_count` (only when `can_establish`), `recent_observations` (≤10), `can_establish` |
| `price_bulk_grid` GET | `draft`, `rows` (part-hydrated), `row_count`, `vendors`, `domains`, `source_types`, `confidences`, `selected_vendor`, `recent_banner` (`{parts, created_window, overflowed, dismissed}`), `can_establish` |
| `price_bulk_grid` POST | as GET, plus `result` (`BulkObservationResult`) or `errors: list[str]` |
| `unpriced_parts` | `page` (Paginator page), `filters`, `domains`, `part_types`, `total` |
| `part_price_history` | `part`, `observations`, `facts_by_vendor`, `filters`, `vendors`, `domains`, `can_establish` |

`recent_banner.dismissed` is per-session and sticky (D82/door 1) — dismissal writes a session flag
keyed on the batch, so nobody is nagged about the same parts twice.

---

## §6 — Templates

```
app/procurement/templates/procurement/prices/
  hub.html                  page — landing
  bulk.html                 page — grid shell
  _grid.html                fragment — the grid card, HTMX target (#price-grid)
  _recent_banner.html       fragment — door 1
  _vendor_picker.html       fragment — mirrors parts/manufacturers/_manufacturer_picker.html
  unpriced.html             page — D86 queue
  _unpriced_results.html    fragment — the results table
  part_history.html         page — full history
  _price_picker.html        fragment — format=htmx-picker
  _price_chip.html          fragment — format=htmx-chip
  _pricing_card.html        fragment — format=htmx-card, for parts detail
```

All pages `{% extends "procurement/base.html" %}` and fill `{% block breadcrumb %}` and
`{% block content %}`. `base.html` already includes HTMX, the CSRF snippet, and the sidebar.

### 6.1 `hub.html`

`page-hero` + `body-grid` of action cards + `stat-grid` of tiles, exactly the shape of
`procurement/hub.html`. Two cards: *Record prices* → `price_bulk_grid`, *Browse unpriced* →
`unpriced_parts`. Two tiles: **Unpriced parts** and, when `can_establish`, **Unverified
assertions**.

The unpriced tile's label carries the D87 caveat in one line of `is-size-7 has-text-grey` helper
text — *"parts with no price in a domain you can see"* — because someone will otherwise ask why
their count differs from a colleague's.

Recent observations render as a plain table: part, vendor, price, and `staleness(observed_at)` from
the narrator. Empty state: *"No prices recorded yet."*

### 6.2 `bulk.html` + `_grid.html` — the paste grid

The card is the spec in [bulk_observation_screen.md](bulk_observation_screen.md), with build_plan.md
§1's corrections applied: **domain is required** (no "blank means global" hint) and the header bar
carries a **confidence** select plus, for `can_establish` only, a *Record as verified* checkbox.

Layout, top to bottom inside one `<form method="post">`:

1. `_recent_banner.html` — door 1. Renders only when the breadcrumb has parts and is not dismissed.
   **Never auto-seeds.** Two buttons: `[Load them into this grid]` (`hx-post` to `price_bulk_grid`
   with `?format=htmx-grid`, idempotent) and `[Dismiss]`. When `overflowed`, the banner also says
   the list is full and points at *Unpriced parts*.
2. Header bar — `_vendor_picker.html`, domain select, `observed_at` date, source select, confidence
   select, optional notes, and the verify checkbox. All `is-small`.
3. The grid `<table>` inside `#price-grid`. Part identity is read-only text; `quantity` and
   `unit_cost` are inputs; each row has a `[×]` remove button (`hx-post` → `?format=htmx-grid`,
   `hx-target="#price-grid"`).
4. Doors 2 and 3 beneath the grid: a link into `unpriced_parts`, and a `<search-dropdown>` wired to
   `?format=htmx-part-results` that appends rows. All three doors are **additive, not modes**.
5. Footer: `N rows · M priced` on the left, `[ Add parts ]` and `[ Save all ]` on the right, per the
   form style guide.

`unit_cost` inputs are `type="number" step="0.01" min="0"`, matching the existing PO line fields
exactly (`class="input is-small is-family-monospace"`). A number input gives the numeric keypad on
mobile, arrow-key nudging, and browser-native rejection of nonsense — users can work out that a
price field wants a number.

**Prices render as raw decimals everywhere — no currency symbol, no thousands separators, no
`intcomma`.** `12.50` and `1234.56`. The column header says what the number is; the value does not
need to repeat it. This is not only a grid rule: it holds on the history table, the chip, the
picker, and the hub's recent list, so a number can be read off one screen and typed into another
without a translation step. It also means re-rendering the draft always round-trips cleanly, since
what we print into a value attribute is what a number input accepts.

Zero rows still renders the card, the header bar, all three doors, and *"No parts in the grid yet."*

**After a successful POST:** `consume(request, part_ids=...)`, then re-render with a success
notification (*"7 observations recorded for Acme Industrial."*), the duplicate warnings as
`is-warning is-light`, and `dropped_part_ids` resolved to part numbers under *"Skipped — no price
entered."* Redirect-after-POST is **not** used here: the summary is the payload, and a redirect
would throw it away. The draft is cleared on success, so an F5 lands on a clean grid.

### 6.3 `unpriced.html`

Filter bar (domain, created-since, part type) reusing
`shared_components/_htmx_browse_filter_form.html`, targeting `#unpriced-results` via
`?format=htmx-results`. Filter state lives in the query string and reproduces on a plain load.

Columns: part number, name, domain(s), created, and a **Price it** action posting the row into the
grid draft, plus row checkboxes with *Add selected to grid*. Default sort oldest-first. Paginate at
50 with Bulma's centred `pagination`.

Empty state: *"Nothing unpriced in your domains."* — a genuinely good outcome, so phrase it as one.

### 6.4 `part_history.html` + `_price_picker.html`

Full page: part identity header; per-vendor the two facts the chip shows; then the table — date,
vendor, domain, quantity, unit cost, confidence band, verified badge, source type, recorded by,
notes — newest first, filterable on vendor and domain as first-class controls. Link back to the
source PO line wherever `source_po_line` is set.

For `can_establish` holders, each row carries a *Verify* action. It **POSTs and appends a verified
row** (D89) — it never edits the row it was clicked on. Make that visible in the confirm copy:
*"Record $12.50 as the established price for Fleet Operations?"*

`_price_picker.html` (`format=htmx-picker`) is the same data, condensed for a modal:

- Client-side search over vendor and domain — a `keyup` filter over already-rendered rows, no
  server round-trip.
- **50 rows max, most-recent-first, verified rows badged.** Recency is what a buyer scans for; the
  badge carries authority without reordering.
- Honest about the cap: *"Showing 50 of 128 — open full history →"*.
- Opens **unfiltered**. The chip already gave them the vendor's number.
- Picking a row returns **the naked value** into the cost field and closes the modal — plus
  `unit_cost_source=estimated` and today's date. **No provenance stamp** (D92): the picked row may
  be another vendor's, and a false provenance is worse than none.
- Empty state: the search box plus *"No prices on record for this part."*

This is legitimate modal use — read-only browsing plus a single-value capture, not assignment.

---

## §7 — The chip on PO lines (D91)

```
app/procurement/control_layer/domain_structs/part_price_facts_struct.py  NEW
app/procurement/control_layer/policies/part_price_policy.py              NEW (dir exists, empty)
app/procurement/control_layer/policies/__init__.py                       NEW
```

`PartPriceFactsStruct` and `PartPricePolicy.facts_for` / `facts_for_many` are build_plan.md §7.1–7.2.
The one rule the front-end depends on: **`facts_for_many` is O(1) queries in the number of lines.**
A chip per line rendered by a per-line policy call is the mistake this kit was written to avoid.

### 7.1 What the chip renders

```
$14.20 — recorded by J. Alvarez, 2 days ago
$12.50 — verified, East Coast, 12 Mar 2026   [ Use this ]
4 prices on record for this part →
```

- Both numbers are the **PO's vendor's**, which is what makes `Use this` unconditionally safe.
- **Collapse when they agree.** If the most recent record *is* the verified one, one line. A chip
  that always shows two numbers trains people to stop reading it.
- With nothing from that vendor: `describe_absent(vendor_name)` plus the doorway —
  *"No price from Acme — 4 prices from other vendors →"*.
- The doorway opens the picker (`format=htmx-picker`).
- `Use this` copies the value and stamps `unit_cost_source` (`last_paid` from an `invoiced`
  observation, `last_ordered` from `ordered`, else `quoted`) and `unit_cost_asserted_at =
  observation.observed_at` — **never today**.

### 7.2 Insertion points

Rendered **server-side on plain GET** for every existing line via `facts_for_many`, and re-fetched
by HTMX when the line's part changes **or the PO's vendor changes** (a vendor change re-resolves
*every* line, not just the edited one).

| File | Line | Field |
| :--- | :--- | :--- |
| `purchase_orders/create.html` | 216 | `#unlinked-cost` — the unlinked-part add form |
| `purchase_orders/create.html` | 295 | `unit_cost_{{ demand.part_id }}` — demand-derived lines |
| `purchase_orders/create.html` | 369 | `#line-cost-{{ line.index }}` — draft line edit |
| `purchase_orders/detail.html` | 260 | `#add-line-cost` — add line on a saved PO |
| `purchase_orders/detail.html` | 374 | `#edit-cost-{{ line.struct.line_id }}` — saved line edit |

The chip slot is a `<div id="price-chip-{{ handle }}" class="is-size-7 mt-1">` directly beneath each
input, included from `_price_chip.html`. On the draft-line paths the handle is the line index; on
saved lines it is the line id. Keep the ids distinct — two chips sharing an id is how a vendor
change updates the wrong row.

A line whose part is not yet chosen renders the slot **empty but present**, so the HTMX swap has a
target on the first paint.

### 7.3 Deferred

D90's soft lock on override needs a *Use* authority level that has no mapping in the current
permission set. Leave `# TODO(D90)` where the override check would sit and log it in
`docs/procurement/tech_debt/`. Until then every `buy` holder may type any number on their own line.

---

## §8 — Navigation: a page nothing links to is not shipped

### 8.1 Sidebar — `procurement/base.html`

Add to the **Purchasing** section, after *Vendors*:

```django
<a href="{% url 'price_hub' %}" class="sidebar-link {% block nav_price_hub %}{% endblock %}">
  <span class="icon"><span class="material-icons" aria-hidden="true">sell</span></span> Prices
</a>
```

Every price page declares the matching `{% block nav_price_hub %}is-active{% endblock %}`.

### 8.2 Procurement hub — `procurement/hub.html`

One `body-grid` card matching the existing shape (icon span, `title is-6`, grey `is-size-7`
subtitle, `button is-small is-link mt-2`) pointing at `price_hub`, rendered **only for `can_buy`** —
a card leading to a guaranteed 403 is worse than no card. Plus one `stat-tile` carrying the unpriced
count, sourced from `UnpricedPartSearch`'s own count query in `shell.py::procurement_hub`. Do not
hand-roll a second `~Exists(...)` here.

### 8.3 Part-create success

A secondary action beside *View part*: *"Add prices for these 3 parts →"*. A **click, never a
redirect** — auto-redirecting into a pricing grid hijacks the flow for everyone who has no prices to
enter.

### 8.4 Part detail — `app/parts/templates/parts/detail.html`

Take **option B** from [page_set.md](page_set.md): an empty card shell that `hx-get`s
`part_price_history?format=htmx-card` with `hx-trigger="load"`. Note the F5 caveat in a template
comment — the page *works* on reload (the fragment re-fires), the card just fills a beat later.
This is the precedent for every future cross-app card, so write the comment explaining why.

### 8.5 Vendor detail

A *"Prices from this vendor"* section backed by the `ppo_vendor_recent_idx` index. Cheap, and it is
the natural place to answer "what does Acme charge us for things."

---

## §9 — JavaScript inventory

Vanilla only, no libraries, all of it progressive enhancement over a working server-rendered page.

| Script | Lives in | Does |
| :--- | :--- | :--- |
| Paste handler | `bulk.html` `{% block body_scripts %}` | Intercept `paste` on a grid cell, `split("\n")` then `split("\t")`, trim each value, fill down and across from the focused cell, **stop at the grid edge — never create rows implicitly**, report *"14 values pasted, 3 ignored — grid has 11 rows."* Two-column (`qty \t cost`) pastes fall out for free |
| Picker filter | `_price_picker.html` | `keyup` filter over rendered rows on vendor and domain text. No server round-trip |
| Picker return | `_price_picker.html` | Write the picked value into the opener's cost input, close the modal |
| Banner dismiss | `_recent_banner.html` | Nothing — dismissal is a server round-trip so it survives F5 |

The JS never reformats a value the user typed — a number that changes as you leave the field reads
as the system disagreeing with you. `_parse_money` on the server stays the real rule and still
tolerates a stray `$` or comma, which is why nothing on the client has to.

---

## §10 — Order of work

| Step | Contents | Ships |
| :--- | :--- | :--- |
| A | §3 session tools + search modules + the two `app/parts` call sites | nothing visible |
| B | `urls_prices.py`, `prices.py` entrypoints, `hub.html`, sidebar + hub card (§8.1–8.2) | the section exists and is reachable |
| C | `bulk.html`, `_grid.html`, `_recent_banner.html`, `_vendor_picker.html`, paste JS | **the main event** |
| D | `unpriced.html`, `_unpriced_results.html` | D86 backstop — **same PR as C**, not later |
| E | `part_history.html`, `_price_picker.html` + `PartPricePolicy` and the struct | the pressure valve |
| F | `_price_chip.html` and the five insertion points (§7.2) | the chip; requires E |
| G | `_pricing_card.html`, part-detail card, vendor-detail section, part-create success link | the cross-app surfaces |

C and D ship together. The breadcrumb without the queue is a convenience with three silent failure
modes; the queue is what makes all three harmless (D86).

---

## §11 — Definition of done

- [ ] A `buy` holder reaches *Prices* from the sidebar and the procurement hub; a non-holder sees
      neither card nor link, and gets a 403 on the URL.
- [ ] Creating parts, then opening the grid, shows the banner — and the grid stays **empty** until
      the button is clicked. Clicking it twice adds nothing the second time.
- [ ] Dismissing the banner survives a reload.
- [ ] Pasting a column of 14 numbers into an 11-row grid fills 11 and says so.
- [ ] Prices render as raw decimals — no `$`, no thousands separators — on the grid, the history
      table, the chip, and the picker.
- [ ] A saved grid re-rendered from the draft round-trips: every value comes back in its cell.
- [ ] A row left blank is dropped and **named** in the summary by part number.
- [ ] One invalid row saves zero rows, and the grid comes back with the user's typing intact.
- [ ] A duplicate warns, and the save still succeeds.
- [ ] The *Record as verified* checkbox is absent without `price_establish`, and a forged
      `record_as_verified=on` POST is refused by the guard.
- [ ] An observation in an invisible domain appears on no page, in no chip, in no picker.
- [ ] Deleting the session row and reloading: the parts are still findable via *Unpriced parts*.
- [ ] The chip renders on a plain GET of a PO with existing lines, **with JS disabled**.
- [ ] Changing the PO's vendor re-resolves every line's chip, not just one.
- [ ] `Use this` stamps the observation's `observed_at`, not today's date.
- [ ] The picker stamps no provenance and today's date.
- [ ] Every card renders with zero rows.
- [ ] `dev_tools/memory.md` gets one line per step landed.

---

## §12 — Not in scope

No price edit or delete screen (append-only, D80). No per-row vendor/domain/date override on the
grid (D83). No cross-part bulk adjustment. No vendor catalog manager. No price approval workflow —
approval belongs on the PO, not on a record that something was true. No currency conversion. No
quantity-break resolution. D90's soft lock and per-domain establish authority are both
`# TODO`-and-tech-debt, not build items.
