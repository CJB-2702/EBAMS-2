---
okf_version: "0.1"
type: "Kit Document"
title: "The Pricing System"
description: "How the application knows what a part costs: observations rather than a price field, the record/verify authority split, and the self-maintaining feed from placed orders."
tags: [starter-kit, procurement, pricing, policy, okf]
context_tier: 2
personas: [backend, business]
---

# The Pricing System

**A price is an observation, never a property of a part.** `PartPriceObservation` records
that *this vendor* offered or charged *this unit cost* for *this part* at *this quantity*
on *this date*, learned *this way*, with *this confidence*.

There is no `Part.unit_cost` anywhere in this design, and there should not be one. A part
does not have a price; a vendor has a price for a part, on a day, at a quantity, and
those disagree constantly.

---

## 1. What an observation says

| Field | Meaning |
| :--- | :--- |
| `part`, `vendor`, `domain` | who is quoting what to whom. Domain is the security fence |
| `unit_cost`, `currency` | the number |
| `quantity` | nullable — a price is not always tied to a quantity break |
| `observed_at` | **the date the fact was true**, not the date it was typed |
| `source_type` | `part_create` / `quote` / `manual` / `ordered` / `invoiced` / `catalog` |
| `confidence` | `quoted` / `p10` / `p50` / `p100` / `unknown` |
| `is_verified` | whether this is the number everyone else is shown |
| `source_po_line` | set on rows written automatically when an order is placed |

Observations accumulate. A newer fact is a new row, never an edit to an older one.

---

## 2. Two facts, resolved in bulk

The policy answers exactly two questions per (part, vendor) pair, plus context:

- **Most recent observation** — what we last saw, verified or not.
- **Most recent verified observation** — what an authority stood behind.
- Plus counts: how many observations exist for this part at all, and how many are from a
  *different* vendor (so a buyer sees "we have prices for this from three other vendors").

**`facts_for_many` must be O(1) queries in the number of lines.** Three bulk queries
total, resolved in Python — never a query per part. A chip per line rendered by a per-line
policy call is the specific mistake this design exists to avoid.

Domain filtering happens **before** ordering on every query: domain scoping is a security
boundary, not a ranking preference.

---

## 3. The authority split

| Action | Permission |
| :--- | :--- |
| Record an observation | `procurement.buy` — ordinary buying activity |
| **Verify** an observation | `procurement.price_establish` **as well** |

Verifying is what makes a number the one everyone else is shown, so it is a genuinely
different authority. The two levels change what a control *means*, never where it is: the
bulk grid looks identical for both, and only the "Record as verified" checkbox appears or
does not.

Per-domain establish authority is a known open item — `price_establish` is currently a
single global permission.

---

## 4. Placing an order is itself a price fact

Placing a PO writes one `ordered` observation per line automatically, carrying the line's
unit cost and pointing back at the line through `source_po_line`.

This is the self-maintaining half of the system: it costs nothing beyond work the buyer
has already done, and it means price history exists even in an organization where nobody
ever remembers to record a quote.

---

## 5. Duplicate handling

The validator returns a **soft** `DuplicateObservationWarning` when an equivalent
observation already exists — same part, same vendor, same neighbourhood of date and cost.
It informs; it does not refuse. Recording the same price twice is harmless; blocking a
buyer mid-entry is not.

---

## 6. Surfaces

| Surface | Purpose |
| :--- | :--- |
| Price hub | Entry point to the pricing surfaces |
| **Bulk grid** | Paste a vendor's quote sheet and record many observations in one pass, through an adaptor that parses the grid before anything is written |
| **Unpriced parts** | The backstop list: parts nobody has ever priced |
| **Part price history** | One part's full observation history, plus the chip/picker/card format variants other pages embed |

---

## 7. Unit-cost provenance on the order line

Separately from observations, each `PurchaseOrderLine` carries three provenance columns —
`unit_cost_source` (`quoted` / `last_paid` / `last_ordered` / `estimated` / `unknown`),
`unit_cost_confidence`, and `unit_cost_asserted_at`. They record where the buyer got the
number they typed, which is what makes a later variance meaningful rather than mysterious.
