---
okf_version: "0.1"
type: "Reference"
title: "Model — PartPriceObservation, and the PurchaseOrderLine provenance columns"
description: "Schema for the append-only part price history table, its indexes tuned to the resolution ladder, and the two provenance columns added to PurchaseOrderLine."
tags: [reference, procurement, data-model, pricing]
context_tier: 2
personas: [backend]
---

# Model — `PartPriceObservation`

`app/procurement/models/pricing/part_price_observation.py` *(new package)*

One recorded assertion that a part cost a particular amount, from a particular vendor, at a
particular time. **Append-only** (D80) — rows are written once and never updated. There is no
"current price" anywhere in the schema; current price is derived as rung 1 of the resolution ladder
(D84).

Inherits `AuditFieldsMixin`. Deliberately **not** `SoftDeleteMixin`: an observation is a historical
fact, and a fact that can be retracted is a fact you cannot build a suggestion on. A wrong
observation is corrected by appending a newer, better one — which is exactly what the divergence
prompt does (D85).

---

## Columns

| Column | Type | Notes |
| :--- | :--- | :--- |
| `part` | FK → `parts.Part`, `PROTECT`, `related_name="price_observations"` | What was priced |
| `vendor` | FK → `procurement.Vendor`, `PROTECT`, `related_name="price_observations"` | Who quoted or charged it. See "Vendor is required" below |
| `domain` | FK → `administration.Domain`, `PROTECT`, **required** | The domain this price was observed *for*. Non-nullable — there is no global tier (D87) |
| `unit_cost` | `DecimalField(12, 2)` | Price per unit. `>= 0` |
| `quantity` | `DecimalField(12, 3)`, `null=True, blank=True` | Quantity the price applied at. Recorded so a suggestion can say "at qty 500"; no tier resolution is built |
| `currency` | `CharField(3)`, default `"USD"` | Single-currency system today. Present so adding a second one later is not a migration of every row |
| `observed_at` | `DateField` | When the price was true, **not** when the row was written (`created_at` covers that). A quote received last week and entered today is dated last week |
| `source_type` | `CharField(20)`, choices | See table below |
| `confidence` | `CharField(10)`, choices | How sure the asserter was (D88). See table below |
| `is_verified` | `BooleanField`, default `False` | Written `True` only by an actor holding **establish** authority for this domain (D89). Never updated — verifying someone else's observation appends a new verified row |
| `source_po_line` | FK → `procurement.PurchaseOrderLine`, `SET_NULL`, `null=True, blank=True` | Optional provenance back-pointer for `ORDERED` / `INVOICED` rows |
| `notes` | `TextField(blank=True)` | Free text — "phoned, spoke to Dana", "quote expires 30 Sep" |

### `source_type` values

| Value | Meaning | Written by |
| :--- | :--- | :--- |
| `PART_CREATE` | Captured alongside a newly defined part | Bulk observation screen, seeded from the creation breadcrumb |
| `QUOTE` | A vendor quoted this, unprompted by an order | Bulk screen, manual entry |
| `MANUAL` | A human asserted it — phone call, catalogue page, correction | Bulk screen; the PO divergence prompt (D85) |
| `ORDERED` | What a PO line was placed at. **Not proof of payment** | `PurchaseOrderContext.place()` — later phase |
| `INVOICED` | What was actually billed. The highest-trust value | Receipt reconciliation — later phase |
| `CATALOG` | Imported from a vendor price file | Not built; reserved so the enum does not need widening later |

Display does not rank by `source_type` — per D91 the chip shows the most recent recorded and the
most recent verified price for the PO's vendor, and everything else lives on the history page.
Weighting `INVOICED` above `ORDERED` when choosing "most recent verified" is an obvious later
refinement and is noted in [../purchase_order_integration.md](../purchase_order_integration.md).

### `confidence` values (D88)

| Value | Means |
| :--- | :--- |
| `QUOTED` | I have paper. This is the number |
| `P10` | Within about 10% |
| `P50` | Within about half |
| `P100` | Could be double |
| `UNKNOWN` | No idea — placeholder |

Coarse buckets, deliberately. Nobody can calibrate "37%," and a free-entry percentage produces
false precision about imprecision. Required on every row; no default that lets someone skip the
question by not answering it.

### `is_verified` and append-only (D89)

Verification is a **property of a row, written at insert**, never a later update — that is what
keeps D80 intact. An establishing actor who agrees with an unverified observation appends a new row
carrying the same value with `is_verified=True`, and the original stays on the record. The
disagreement between what the field recorded and what the organization established is itself
information worth keeping.

The establishing actor's authority is checked **against the row's `domain`** (D89), not globally.

### Vendor and domain are both required

The alternative considered was making the whole price block optional but requiring vendor *within*
it, with an "Other" escape hatch. **"Other" must never be a `Vendor` row** — a garbage-bucket vendor
becomes the most-recent observation for everything and permanently poisons rung 1 of the ladder.

The chosen shape: `vendor` is non-nullable on the model, and the *screen* makes the whole row
optional — a row with no cost is dropped, a row with a cost must name a vendor. Inline vendor
creation on the grid means nobody ever reaches for "Other."

If that proves too strict in practice, the relaxation is `null=True` plus an *Unspecified vendor*
label that display scores below any named vendor. Null is queryable-around; a fake row is not.
That is a one-line guard change, not a redesign.

`domain` is required for the symmetrical reason (D87): an observation always answers **who quoted
it** and **who it was for**. A null domain is not "unknown" — it is a price nobody negotiated, which
would match for every actor everywhere and let the laziest entry outrank the careful one. Prices
cross sites through the actor's *visibility*, carrying their origin with them, not through a
placeless tier.

---

## Meta

```python
class Meta:
    db_table = "part_price_observation"
    ordering = ["-observed_at", "-created_at"]
    constraints = [
        models.CheckConstraint(
            condition=models.Q(unit_cost__gte=0),
            name="ppo_unit_cost_non_negative",
        ),
        models.CheckConstraint(
            condition=models.Q(quantity__isnull=True) | models.Q(quantity__gt=0),
            name="ppo_quantity_positive_or_null",
        ),
    ]
    indexes = [
        # The chip's two facts: part + vendor, narrowed to visible domains.
        models.Index(
            fields=["part", "vendor", "domain", "-observed_at"],
            name="ppo_part_vendor_domain_idx",
        ),
        # The same, restricted to established prices — the second of the two facts (D91).
        models.Index(
            fields=["part", "vendor", "is_verified", "-observed_at"],
            name="ppo_part_vendor_verified_idx",
        ),
        # History page and picker: everything for this part, any vendor.
        models.Index(fields=["part", "-observed_at"], name="ppo_part_recent_idx"),
        # "Everything we have ever been quoted by this vendor" — vendor detail page.
        models.Index(fields=["vendor", "-observed_at"], name="ppo_vendor_recent_idx"),
    ]
```

**No unique constraint.** Two observations for the same part+vendor+domain+date are legitimate —
different quantities, a correction, two people entering the same quote. Deduplication is a UI
concern (warn on an exact duplicate at commit), never a database one.

### Why `-observed_at` is in the composite index

Every display query is `filter(...).order_by("-observed_at").first()`. Without the sort column in
the index, each is an index scan plus a sort. With it, both of the chip's facts are index-only
lookups. This matters because
[`PartPricePolicy.suggest_many()`](../control_layer_architecture.md) resolves them for every line on
a PO at once — and D91 doubled the query count per line, from one ladder walk to two point lookups.
Two indexed lookups still beat one sorted scan.

---

## New columns on `PurchaseOrderLine`

`app/procurement/models/purchasing/purchase_order_line.py`

| Column | Type | Notes |
| :--- | :--- | :--- |
| `unit_cost_source` | `CharField(20)`, choices, `blank=True`, default `""` | Where this line's price came from |
| `unit_cost_asserted_at` | `DateField`, `null=True, blank=True` | The `observed_at` of the observation it came from — **not** today's date. This is what makes staleness renderable |
| `unit_cost_confidence` | `CharField(10)`, choices, `blank=True` | How sure **this Buyer** is about this line (D88). Same five values as the observation's `confidence` |

### `unit_cost_source` values

| Value | Meaning |
| :--- | :--- |
| `QUOTED` | The Buyer has a quote or confirmation from this vendor for this order |
| `LAST_PAID` | Filled from an `INVOICED` observation via the chip's **Use this** |
| `LAST_ORDERED` | Filled from an `ORDERED` observation — never verified against an invoice |
| `ESTIMATED` | The Buyer typed a number, or took one from the cross-vendor picker (D92) |
| `UNKNOWN` | Nobody knows yet. Go find out |
| `""` (blank) | Pre-existing rows from before this build |

`LAST_PAID` and `LAST_ORDERED` are reachable **only** through the chip, which is vendor-scoped and
therefore true. The picker is deliberately cross-vendor, so a value taken from it lands as
`ESTIMATED` with today's `unit_cost_asserted_at` — an owner, not a provenance chain (D92). A false
provenance would be worse than none.

### Why confidence lives on the line as well as the observation

They answer different questions. The observation's `confidence` is how sure the *observer* was on
the day; the line's is how sure *this Buyer* is about *this order*. Copying a confident 14-month-old
price into today's line is legitimately less certain than the original was.

The Buyer may downgrade on copy. **The system never downgrades silently** — that is an opinion a
machine has no standing to hold, and a number quietly marked less trustworthy than the person who
entered it believes is its own kind of lie.

Together with `unit_cost_source`, this is what makes a PO total honest without anyone declaring a
pricing basis (D88): *"$4,210 — could be $3,400 to $5,600, 6 of 9 lines are estimates."*

These two columns are what let a PO line render as *"$12.50 — last paid to Acme, 14 months ago"*
instead of *"$12.50"*. The staleness **is** the signal; a number without it is the problem this kit
exists to solve.

They also make a PO's total honest: a draft can say *"$4,210.00 estimated — 6 of 9 lines are
guesses"* rather than presenting a fiction as a figure.

### Migration note

Adding these is a schema change, so per the project's always-apply rule this is a **full reset**:
`python refresh_project.py`. Do not write an incremental migration.

---

## Dependency direction

```
administration.Domain ──┐
parts.Part ─────────────┼──> procurement.PartPriceObservation
procurement.Vendor ─────┘           │
                                    └── (optional, nullable) ──> procurement.PurchaseOrderLine
```

Everything the table depends on already sits below `procurement`. The only outward edge is the
nullable `source_po_line`, which stays inside the same app. **No new cross-app dependency is
created by the model layer** — the one inversion in this kit is the session breadcrumb (D81), which
lives entirely in the presentation layer.
