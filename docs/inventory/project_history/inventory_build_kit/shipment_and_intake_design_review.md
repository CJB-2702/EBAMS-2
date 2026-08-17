---
okf_version: "0.1"
type: "Technical Decision"
title: "Shipment vs. Intake — Design Review"
description: "Business-process capture of the Procurement/Inventory terminology and boundary discussion that precedes the inventory build: why 'package' splits into 'shipment' (Procurement) and 'intake' (Inventory), the parallel-not-nested relationship between them, the proposed two-axis demand status, and the open questions carried into the build."
tags: [technical-decisions, technical-decision, procurement, inventory, shipment, intake]
context_tier: 2
personas: [business, backend]
---

# Shipment vs. Intake — Design Review

Status: **pre-build discussion, captured for the inventory build kit.** This document is a business-
process capture from a planning conversation, produced by the Business Architect persona ahead of
`inventory_build_kit` work starting. It records the reasoning and the open questions, not a finished
schema — the data-model sketch in §4 is the shape proposed in conversation and still needs an
architecture pass before it is built.

---

## 1. The terminology problem this started from

"Package" was being used for two different things in the procurement build:

- **The vendor's shipment story** — what was sent, its tracking number, its transit status. A
  paperwork/tracking concept, owned by Procurement, existing from the moment an order goes out —
  **pre-possession**.
- **The physical box** — counted, inspected, opened by someone standing at a dock. A physical-
  custody concept — **post-possession**.

Procurement's existing package/shipment tracking had already absorbed the second concept
(`inspect_and_accept_package_line`, performed by "Receiving staff") purely because Inventory's
intake system didn't exist yet to own it. That was a scoping stopgap, not a considered boundary —
the original package model doc says so directly: *"Intake remains out of scope... the later
Inventory build."*

**Decision: split the noun along the boundary that was already implied.**

- **Procurement owns "Shipment."** Renamed from "Package." Covers the vendor's claim and its
  transit status only — creation, tracking number, carrier, status through delivery. No physical
  inspection screens, no acceptance workflow, no "what's in the box" language. That vocabulary was
  borrowed from a stage Procurement no longer performs.
- **Inventory owns "Package" as the physical intake record.** A new, separate build. This is where
  a box is actually opened, counted, and reconciled against what was expected.

---

## 2. Why intake needs its own header, not a child of shipment

Working question: can a package be received and intaken **without** a shipment record ever having
existed for it?

**Answer: yes**, and once that's true, Package cannot be modeled as a child of Shipment. A box can
show up unmarked — no tracking number, no prior shipment record — and still needs to be received,
counted, and (eventually, optionally) tied back to a purchase order. Real business scenarios that
produce this, not edge cases:

- A vendor drop-ships ahead of the shipping paperwork catching up.
- Someone hand-carries parts back from a supplier visit.
- A proactive stock-up happens before anyone cuts an order for it.
- A return or internal transfer gets processed as a fresh receipt.

**Decision: Package is a separate header, parallel to Shipment, not nested under it.** Both
independently reference the purchase order (when one exists) rather than Package hanging off
Shipment. This is deliberate, not an oversight — it's what allows the two records to diverge
without either being wrong: Shipment records what the vendor's paperwork said; Package records what
physically happened. Divergence between them is signal (an over-ship, an unmarked item, a mismatch),
not an error state to eliminate.

---

## 3. The two-axis demand status

Because Shipment and Package now track genuinely independent processes, a single demand needs two
independent status axes rather than one combined status trying to answer both questions at once —
consistent with this project's existing pattern of tracking multiple independent status dimensions
on a demand rather than one bare status column.

- **Shipment axis** — the vendor's tracked journey (Awaiting Shipment → Shipped → Delivered →
  Lost). Meaningless if no shipment record exists.
- **Intake/routing axis** — physical processing once material is in hand (proposed stages:
  Received → Routing/Sorting → Stocked; exact stage list still open, see §5).

### Why an absent shipment status must not read as "pending"

| Shipment axis | Intake axis | What it actually means |
| :--- | :--- | :--- |
| Tracked, In Transit | (nothing yet) | Normal case — vendor's promise is moving, hasn't arrived |
| Tracked, Delivered | Received / Routed / Stocked | Normal case — both axes agree |
| **No shipment record** | Received | **Unmarked arrival** — physically here, no vendor paper trail exists (yet, or ever) |
| Tracked, In Transit | Received | **Early/mismatched arrival** — arrived while its shipment still shows in transit; worth a look |

"No shipment record" and "Awaiting Shipment / In Transit" must render as visibly different states.
Both currently risk collapsing into "blank" or "pending," which would misreport an unmarked arrival
as "still waiting on the vendor" when the truth is "there was never a tracked promise to wait on."

### Attribution rule — reuse, don't reinvent

The old package-acceptance design already solved "does this arrival belong to one demand or many":
attribute to a demand only when a PO line has exactly one active demand link; when it has several,
report shared/session-level numbers only and never guess a proportional split. **Carry this rule
forward unchanged onto the intake/routing axis** — same ambiguity, same answer, regardless of which
app is asking.

---

## 4. Data-model sketch (proposed in conversation — needs an architecture pass)

Not a final schema. Recorded here as the shape discussed, to hand to whoever designs the actual
tables.

```
PurchaseOrder
  - qty_purchased
  - qty_shipped
  (verified / approved / rejected are NOT stored columns — see below)

PurchaseOrderLine

Shipment (Procurement — renamed from "Package")
  ShipmentLine
    - copies its PO line link the same way the old Package model did

Package (Inventory — new, parallel header, NOT a child of Shipment)
  IntakeLine
    - copied from a ShipmentLine (or created fresh, for an unmarked/PO-less receipt)
    - linked to the PO line the same way, then adjusted as reality diverges from the claim
    - serial number captured here, at the moment of physical arrival — the only point it's
      reliably true
```

### Verified / approved / rejected as calculated, not declared

`qty_verified`, `qty_approved`, `qty_rejected` on the purchase order are **derived from real intake
records**, not stored/settable flags. Same principle already trusted elsewhere in this system for
derived pricing basis: a number nobody can leave stale, calculated from what actually happened, is
more trustworthy than a status a person set once and forgot to update.

---

## 5. Open questions carried into the build

These are the items that don't yet have an owner or an answer. Listed so they're decided
deliberately rather than discovered mid-build.

1. **Who performs the shipment ↔ package match**, and when? Intake staff deliberately don't carry
   PO/vendor context, so something or someone else has to connect a physical Package to the
   Shipment (and PO) it fulfills — a distinct, likely deferred step, not part of either side's
   real-time happy path.
2. **Who resolves a box that spans multiple orders** (the old line-splitting-wizard case), now that
   the person opening the box may not have PO context to do it themselves?
3. **What happens to an intake line with no shipment match at all** (an unexpected item, or a fully
   unmarked receipt)? Proposed: recorded as-is, flagged, routed to a review queue — never dropped,
   never force-fit onto the wrong line. Does not block validating the lines that *did* match.
4. **Must an unmarked, PO-less receipt eventually get linked to a purchase order, or can it
   legitimately stay permanently unaccounted-for by paperwork?** A policy decision (dollar value?
   part type? category of receipt?) — not something the model can decide on its own.
5. **Exact stage list for the intake/routing axis.** Proposed starting point: Received →
   Routing/Sorting → Stocked. Needs confirmation before it's built as a fixed sequence.
6. **Review queue design and priority.** An unmatched-but-shipped item and a fully unmarked receipt
   are different severities (the second has zero documentation trail) — worth deciding whether they
   share one queue or are triaged separately.
7. **Package/IntakeLine table shape** (header fields, indexes, constraints) — explicitly deferred to
   backend/architecture review; this document only fixes the business requirement that a header
   exists and is parallel to, not nested under, Shipment.

---

## 6. Terminology carried forward

| Old term | New term | Owner |
| :--- | :--- | :--- |
| Package (procurement) | **Shipment** | Procurement |
| PackageLine (procurement) | **ShipmentLine** | Procurement |
| `inspect_and_accept_package_line` | *(removed from Procurement — moves to Inventory as intake)* | — |
| Package (physical, intake) | **Package** (retained, but now Inventory-owned) | Inventory |
| PackageLine (physical) | **IntakeLine** | Inventory |
