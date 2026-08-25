---
okf_version: "0.1"
type: "Concept & Naming Specification"
title: "Three Issuance Portals — Naming, Routes, and Navigation"
description: "Splits part issuance into three named workflows with distinct URLs, left-nav entries, and staging queues: single-part grab from a location, bulk issuance from demands, and bulk issuance from selected inventory rows."
tags: [inventory, issuance, portals, navigation, routes, workflow]
context_tier: 2
personas: [business, frontend, backend]
created: 2026-08-24
created_by: Christian Bissett
updated: 2026-08-24
updated_by: Claude (on behalf of Christian Bissett)
---

# Three Issuance Portals — Naming, Routes, and Navigation

**Status:** Proposed. Supersedes the single `/inventory/issue-parts/` workspace that tried to serve all three of these at once.

---

## 1. The problem this fixes

There is one screen today and it has been asked to be three things. It carries a
demand pool, a stock pool, a pairing tool, and a commit form on one route, with
`d_`-prefixed and `s_`-prefixed filter namespaces so the two searches do not read
each other's values. Selecting a queued line is a full-page navigation to a URL
fragment (`#inventory-association`) that scrolls the user to a card in the middle
of the page. Both are symptoms of the same thing: **distinct workflows crammed
into one route**.

They are not modes of one portal. They differ in what the user walks up holding,
what question they are answering, and what a finished session looks like:

| | The user arrives holding… | They are asking… | Done when… |
| :-- | :-- | :-- | :-- |
| **A** | a part in their hand | "let me just take this" | one part is recorded |
| **B** | a stack of paperwork for one person | "what does this person get?" | a receipt is signed |
| **C** | a bin of one part | "who is waiting on this?" | the bin is distributed |

A screen that serves all three serves none of them well. Each gets its own name,
its own URL, its own left-nav entry, and — the load-bearing part — **its own
staging queue**.

---

## 2. The three portals

### A. Issue Parts from a Location

> *"I need this one part. Let me go get it."*

**Route:** `/inventory/issue-parts/from-location/`
**Left nav:** `Issue from Location` — icon `place`
**Grain:** one part, one shelf, one person. Not a batch.

The user browses warehouse → room → the room's SVG map → shelf, finds the
physical thing, and virtually grabs it. Spatial navigation is the whole point:
this portal exists because sometimes you know *where* something is long before
you know what its part number is.

Commits immediately on grab by default (**Direct Issue Now**) — there is no
multi-line queue of A's own to build, because a queue is what you need when you
are assembling *someone else's* order, and here the user is the order.

A demand may optionally be attached to the grab. It is not required, and asking
for one first would defeat the portal.

A second action, **Stage Stock into Active Session**, exists for the case where
the user standing at the shelf is filling one line of a larger order they will
review before signing — grab three different parts off three different shelves
for the same handover, say. That action requires a demand (disabled until one
is picked) and writes the line straight into **B's** queue via the same
`add_stock_lines` entry point B's own bin picker uses (§4) — A still has no
queue of its own; it either commits on the spot or borrows B's.

### B. Bulk Issue Parts from Demands

> *"Bob is at the counter with paperwork for six demands."*

**Route:** `/inventory/issue-parts/from-demands/`
**Left nav:** `Bulk Issue from Demands` — icon `assignment_turned_in`
**Grain:** many demands → one recipient → one receipt.

**Demand first, always.** The user picks the demands, and stock is the easy half
filled in afterwards from the bins holding each demand's part. This portal must
never become a stock browser with a demand attached — that is portal C, and
conflating them is the mistake this document exists to prevent.

Structure:

1. **Recipient header**, first and required. One handover, one person. Typed
   explicitly — never inferred from `requested_by`, because a manager routinely
   raises demands against themselves and a member of staff collects the parts.
2. **Demand pool**, unfiltered by default, with the full filter set of
   `/procurement/demands/` including filter-by-requester.
3. **The receipt**, grouped by demand, with a per-line bin picker scoped to that
   line's part.
4. **Summary** with a per-demand completion bar.
5. **Commit**, producing one `PartIssueSession`.

Demands are queued into this portal from two places: its own demand pool, and
`/procurement/demands/`'s bulk "Queue for Part Issuance" action. Both are
demand-grain, which is why both are allowed.

### C. Bulk Issue from Inventory

> *"This shelf and that shelf are going out today. Who is waiting on any of it?"*

**Route:** `/inventory/issue-parts/from-inventory/`
**Left nav:** `Bulk Issue from Inventory` — icon `call_split`
**Grain:** many stock rows → many demands → many recipients.
**Status:** not yet built.

The inverse of B, and the reason B must stay pure. The user builds a queue of
**active inventory rows**, then works forward from that stock to the demands it
can satisfy.

THE UNIT IS THE BALANCE ROW, NOT THE PART. An `ActiveInventory` row is
`location + part number` (plus a serial, for serialised stock), and that is what
goes in the queue. It matters because the same part sits in several bins and the
clerk emptying a specific shelf cares which one: "PN-1002 in BIN-A-03" is the
thing being distributed, and "PN-1002" in the abstract is not something anyone
can physically hand over.

The workflow is therefore:

1. **Select stock.** Bin by bin, or in bulk off the stock list and the spatial
   locator — both of which link *into* this portal rather than staging into
   someone else's queue.
2. **Find demands for it.** Per queued row, a utility lists every open demand
   for that part across all requesters, ordered by priority and need date, with
   the balance on hand shown against the total outstanding.
3. **Allocate.** Split each row's quantity across the demands it will satisfy.
   One row may feed several demands; one demand may draw from several rows.
4. **Commit**, grouped by recipient.

Its natural output is **several receipts, not one** — each recipient gets their
own `PartIssueSession`, because a receipt is a handover to one person. That
difference in output shape is the clearest proof that C cannot be a mode of B:
B commits one session and C commits N, and no amount of shared UI reconciles
that.

It also inverts B's easy half. In B the demand is chosen and the bin is filled
in; in C the bin is chosen and the demand is filled in. Same two facts, opposite
order of discovery, and the screen that makes one effortless necessarily makes
the other awkward.

Note what portal C makes unnecessary. The old "Queue for Part Issuance" bulk
action on `/inventory/active-inventory/` was an attempt to do C's job from
within B — select stock rows, push them into the demand-first queue, then go
hunting for demands to justify them. It has been removed. That action is exactly
right for C and exactly wrong for B, which is the whole argument in miniature:
its stock-row grain is C's native unit and a foreign object in a demand-first
queue. When C exists, `/inventory/active-inventory/` and the Inventory Locator
both stage into it.

---

## 3. Route shape

All three live under one `/inventory/issue-parts/` stem, so the family is
legible in the address bar and the URLs sort together in logs:

```
/inventory/issue-parts/from-location/     A — single grab, spatial
/inventory/issue-parts/from-demands/      B — bulk, demand first
/inventory/issue-parts/from-inventory/    C — bulk, stock first       (planned)

/inventory/issues/                        the Issued Parts ledger (all three)
/inventory/issues/session/<pk>/           one receipt
/inventory/issue/<pk>/                    one issue line
```

Every portal writes `PartIssue` rows through `PartIssuanceOrchestrator` and shows
up in the same ledger. **The workflows are separate; the record is one.** A
storeroom manager asking "what left the building today" must never have to ask it
three times.

`/inventory/issue-parts/` with no suffix redirects to B, which is the highest-
volume path. Legacy `/inventory/issues/create/` redirects there too.

---

## 4. Separate queues, and why

Each portal that stages gets its own session key. They must not share one.

| Portal | Session key | Line shape |
| :-- | :-- | :-- |
| A | *(none of its own)* | *(commits on grab — Direct Issue Now, demand optional)* |
| B | `issuance_draft_<user_pk>` | `{demand_id, active_inventory_id, quantity, notes}` |
| C | `stock_distribution_draft_<user_pk>` | `{active_inventory_id, allocations: [{demand_id, quantity}]}` |

A shared queue was the original sin. Three surfaces wrote into one list with
three different line shapes distinguished by which keys happened to be set — a
demand-backed line, an ad-hoc line carrying an uncreated demand, and a bare stock
line with no requirement at all. Every consumer then had to re-derive which shape
it was holding, and the commit path had to tolerate all of them. Separate keys
mean each queue has exactly one shape, and a malformed line is a bug rather than
a fourth case to handle.

**A's "Stage Stock into Active Session" is the one deliberate exception**, and it
does not reopen that original sin: it does not have its own queue with its own
shape — it writes into B's queue, through B's own `add_stock_lines` function,
producing a line in B's exact shape (`demand_id` required). The button is
disabled until a demand is picked, so A can never hand B a demand-less or
ad-hoc-demand line — the one thing this section's history warns against. A
demand-less grab from A never touches B's queue; it always commits immediately
instead.

The topnav queue badge shows B's count, since B is the only portal with a
long-lived queue today. When C lands it needs its own badge or a combined
dropdown with two labelled sections — not a merged count, which would tell the
user nothing actionable.

---

## 5. Left navigation

The three sit together under their own label, so the choice between them is made
once, visibly, rather than discovered halfway through a workflow:

```
Inventory
  Overview
  Active Inventory
  Inventory Locator
  Intake
  Putaway
  Movements
  ──────────────────
  Issuance
    Issue from Location        place                 → A
    Bulk Issue from Demands    assignment_turned_in  → B
    Bulk Issue from Inventory  call_split            → C   (planned)
    Issued Parts Ledger        receipt_long          → the record
  ──────────────────
  Topography …
```

`Issue Parts` disappears as a nav entry. It named the *table* rather than a task,
and it is the ambiguity that let three workflows collect behind one link.

---

## 6. Naming rules

Every portal name states **what you start from**, because that is the only thing
that distinguishes them at the moment of choosing:

- *from Location* — you have a place
- *from Demands* — you have paperwork
- *from Inventory* — you have shelves to clear

`Bulk` prefixes B and C and is deliberately absent from A. It is the honest
signal of which screens build a multi-line session and which commit on the spot,
and it sets the expectation before the click rather than after.

Do not name a portal after its output. "Issue Parts", "Create Issue Session", and
"Part Issuance" all describe what every one of these does, which is exactly why
they are useless as names.

---

## 7. Consequences

- **B is being built now.** It is demand-only: no ad-hoc demand creation, no
  direct-to-asset issuance, no stock-first staging.
- **A stays as it is** and is renamed and re-routed for its primary path
  (Direct Issue Now, immediate commit). Its secondary path, staging a
  demand-anchored line for later review, deliberately writes into **B's**
  queue rather than one of its own — see §4.
- **C is not built.** Until it exists, "this shelf is going out, who wants it" is
  answered by filtering the demand pool in B by part number and choosing the bin
  by hand on every line — clumsy, and the clearest argument for building C.
- **`PartIssueSession` serves all three unchanged.** One recipient, one moment,
  demand-anchored lines. C commits several of them per run rather than one.
