---
okf_version: "0.1"
type: "Reference"
title: "Control Layer Architecture — Price Observations"
description: "Proposed classes, suffixes, file placement, and call graph for the price observation system, following the project's OOP control patterns and layer rules."
tags: [reference, procurement, architecture, control-layer, backend]
context_tier: 2
personas: [backend]
---

# Control Layer Architecture — Price Observations

The backend persona's brief. Every class below follows
[`harness/Architecture/patterns/oop_control_patterns.md`](../harness/Architecture/patterns/oop_control_patterns.md)
suffix vocabulary, and every file sits where
[`harness/Architecture/layer_rules.md`](../harness/Architecture/layer_rules.md) puts its kind.

> **⚠ Not yet reconciled with D87–D92.** This document still describes the three-rung ladder and its
> `rung` / `autofills` / nullable-domain shape. The business review of 2026-08-09 replaced that with
> two point lookups (most recent recorded, most recent verified — both vendor-scoped), made `domain`
> required, added a confidence band, and split price authority three ways. The affected pieces are
> `PartPricePolicy`, `PartPriceSuggestionStruct`, `PartPriceObservationGuard`, and the test list.
> Read [README.md](README.md) D87–D92 first, then rewrite this document before building from it —
> a backend-persona job, deliberately not done by the business review.

---

## File plan

```
app/procurement/
  models/pricing/
    __init__.py
    part_price_observation.py           NEW — the table
    enums.py                            NEW — PriceSourceType, UnitCostSource
  control_layer/
    domain_structs/
      part_price_suggestion_struct.py   NEW — frozen result of the ladder
    guards/
      part_price_observation_guard.py   NEW — write-time validation
    factories/
      part_price_observation_factory.py       NEW — one row
      part_price_observation_bulk_factory.py  NEW — the grid commit
    policies/
      part_price_policy.py              NEW — the resolution ladder
    adapters/
      part_price_grid_adaptor.py        NEW — grid POST -> bulk factory input
    narrators/
      part_price_narrator.py            NEW — provenance/staleness phrasing
  presentation_layer/
    tools/
      recent_part_creations.py          NEW — the session breadcrumb (D81)
      price_grid_draft.py               NEW — the grid's session draft
    search/
      unpriced_part_search.py           NEW — the D86 backstop query
    entrypoints/
      prices.py                         NEW — grid, history, HTMX fragments
```

`policies/` does not exist under `app/procurement/control_layer/` yet — it is a new package. The
suffix is in the project vocabulary; the folder simply has not been needed before.

---

## The classes

### `PartPricePolicy` — decides

`control_layer/policies/part_price_policy.py`

The resolution ladder (D84). This is a **Policy**, not a Struct: it issues queries and makes a
ranking decision. Putting this logic on struct `__init__` would put database access in a data
carrier and break the layer rules.

```python
class PartPricePolicy:
    @classmethod
    def suggest(cls, *, part_id, actor, vendor_id=None, domain_id=None)
        -> PartPriceSuggestionStruct | None: ...

    @classmethod
    def suggest_many(cls, *, part_ids, actor, vendor_id=None, domain_id=None)
        -> dict[int, PartPriceSuggestionStruct]: ...

    @staticmethod
    def _visible_domain_ids(actor) -> set[int | None]: ...
```

`_visible_domain_ids` returns the actor's assigned domains from
`administration.UserDomain` **plus `None`** (global observations). It is applied as a filter to
**every rung before ordering** — this is a security boundary, not a ranking preference, and it lives
in one helper precisely so it cannot be forgotten in one branch.

`suggest_many` exists because the PO wizard needs the ladder for every line at once. It must be
**one query per rung, not one per part** — a 40-line PO running three queries per line is the exact
mistake D53 already caught on `PurchaseOrderLineStruct`. Implementation: window function over the
composite index (`ROW_NUMBER() OVER (PARTITION BY part_id ORDER BY observed_at DESC)`) or three
bulk fetches resolved in Python, whichever profiles better on SQLite and Postgres both.

### `PartPriceSuggestionStruct` — carries

`control_layer/domain_structs/part_price_suggestion_struct.py`

Frozen dataclass, same shape as the existing
[`PurchaseOrderLineStruct`](../app/procurement/control_layer/domain_structs/purchase_order_line_struct.py).

```python
@dataclass(frozen=True)
class PartPriceSuggestionStruct:
    part_id: int
    unit_cost: Decimal
    quantity: Decimal | None
    vendor_id: int
    vendor_name: str
    domain_id: int | None
    domain_name: str            # "Global" when domain_id is None
    observed_at: date
    source_type: str
    rung: int                   # 1, 2, or 3
    is_exact_vendor_match: bool
    autofills: bool             # False on rung 3 (D84)
    def to_dict(self) -> dict: ...
```

`autofills` is a property of the *suggestion*, not of the template. A rung-3 match is displayed but
never written into the field, and encoding that here means no caller can get it wrong.

### `PartPriceObservationGuard` — validates

`control_layer/guards/part_price_observation_guard.py`

Per project convention, guard files end in `_guard.py`. Raises the app's validation error type with
a list of messages, matching `PartValidationError` usage in the parts app.

Rules: non-negative cost, positive-or-null quantity, `observed_at` not in the future, vendor
present, part visible to the actor. Duplicate detection returns a **warning list** separate from
errors — duplicates are allowed (D80: no unique constraint), they just deserve a confirmation.

### `PartPriceObservationFactory` / `...BulkFactory` — writes

`control_layer/factories/`

`Factory` creates one row; `BulkFactory` creates many in one transaction, following the existing
`Factory`/`BulkFactory` split in the vocabulary. The bulk factory is what the grid commits through,
and it is **all-or-nothing** — a grid that half-saves is worse than one that fails.

Both call the guard first. Neither is called directly by an entrypoint without going through an
adaptor.

### `PartPriceGridAdaptor` — parses

`control_layer/adapters/part_price_grid_adaptor.py`

Grid POST → bulk factory input. Same shape as
[`PartCreationWizardAdaptor`](../app/parts/control_layer/adapters/part_creation_wizard_adaptor.py):
indexed row prefixes (`rows-<i>-`), rows with no cost dropped, batch header fields applied to every
surviving row.

Also owns `to_session()` / `from_session()` for the grid draft, mirroring the
`PurchaseOrderDraftAdaptor` ↔ `po_wizard_draft` handoff — the adaptor validates a *complete* grid at
submit, the session tool holds the *incomplete* one while the user types.

### `PartPriceNarrator` — phrases

`control_layer/narrators/part_price_narrator.py`

One place that turns a suggestion into words, so the PO line, the grid, and the price history page
never disagree:

- `"Last paid to Acme Industrial — Fleet Operations, 14 months ago"`
- `"Acme Industrial quoted this 3 days ago"`
- `"Grainger charged $40.00 in November 2025 — different vendor"`
- `"No price on record"`

Follows the existing
[`purchase_order_narrator.py`](../app/procurement/control_layer/narrators/purchase_order_narrator.py)
precedent. Staleness phrasing especially belongs in one place — it is the signal this whole kit
exists to deliver, and three templates rounding "14 months" three different ways would undercut it.

### `UnpricedPartSearch` — finds

`presentation_layer/search/unpriced_part_search.py`

Search modules live in the presentation layer per the project's structure. Parts in the actor's
visible domains with zero observations, paginated and filterable. This is D86's implementation —
the backstop that makes every session-path failure mode a non-event.

---

## Call graph

```
parts wizard entrypoint ──(on_commit)──> recent_part_creations.record_created_parts()
                                                       │  [session]
                                                       ▼
prices entrypoint (GET)  ──> recent_part_creations.read_recent()  ──> banner
                         ──> UnpricedPartSearch                   ──> filter results
                         ──> price_grid_draft                     ──> grid rows

prices entrypoint (POST) ──> PartPriceGridAdaptor.from_post()
                                  └──> PartPriceObservationBulkFactory.create_many()
                                            └──> PartPriceObservationGuard.validate()
                                  └──> recent_part_creations.consume()

PO wizard / line edit    ──> PartPricePolicy.suggest_many()
                                  └──> PartPriceSuggestionStruct
                                            └──> PartPriceNarrator.describe()
```

---

## Layer rules this respects

- **Reads go through search modules and policies; writes go through factories behind guards.** The
  entrypoint never touches `PartPriceObservation.objects` directly.
- **No business logic on the model.** No `@property` returning a computed price — D53 already
  established what that costs when a list view renders forty of them.
- **Structs are computed once and frozen.** No lazy query on attribute access.
- **The one inversion is presentation-layer only.** `recent_part_creations.py` is the sole file
  `app/parts` imports, and the parts *control layer* stays completely ignorant of pricing. That
  placement is what keeps D81 a wart rather than a wound.

---

## Permissions

Reuse `procurement.buy` for the first cut rather than minting a new permission. Price observation is
a Buyer activity, and the existing `buy` permission already covers "create/edit purchase orders and
lines."

If pricing later needs to be delegated to someone who may not place orders — a plausible split, a
stores clerk recording quotes — add `procurement.price_manage` then. Splitting a permission is
cheap; merging two that shipped separately is not, so err toward one now.

The grid, the history page, and the suggestion fragments all gate on it. The recent-creations banner
additionally must not render for a user without it — otherwise part creators without buying rights
get an offer they cannot accept.

---

## Testing notes

Per [`harness/Architecture/tests.md`](../harness/Architecture/tests.md), the pieces worth covering:

- **Ladder correctness** — each rung fires when it should, and rung 3 sets `autofills=False`.
- **The domain gate** — an actor without a domain assignment must not receive a suggestion sourced
  from it. This is the security test; write it first.
- **Breadcrumb writeback** — assert the session actually persists across a request boundary. A test
  that only checks the in-memory dict passes against the nested-mutation bug described in
  [parts_creation_smuggling.md](parts_creation_smuggling.md), which makes it worse than no test.
- **TTL and cap** — expired entries pruned on read, `overflowed` set at 100.
- **`on_commit` behaviour** — a rolled-back part creation leaves no breadcrumb.
- **Bulk factory atomicity** — one bad row saves nothing.
