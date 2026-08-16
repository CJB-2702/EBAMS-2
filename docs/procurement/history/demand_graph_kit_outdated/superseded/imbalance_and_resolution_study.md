---
okf_version: "0.1"
type: "Study"
title: "Imbalance and Resolution — Study"
description: "What 'unresolved' means for a demand graph: which quantities are compared, the named imbalance states, the precedence rule, and the suggested action attached to each."
tags: [starter-kit, study, procurement, graphs]
context_tier: 2
---

# Imbalance and Resolution — Study

> # ⚠ SUPERSEDED — 2026-08-16
>
> **This document describes a model the kit no longer uses. Do not build from it.**
> Authority is [`decisions.md`](decisions.md) and [`model_diagram.md`](model_diagram.md).
>
> It is kept, not rewritten, because §1 and §2 are the best-argued reasoning in the kit and rewriting them
> to fit the current model would leave the surviving conclusions unsupported. Read it as *why we got here*,
> never as *what to build*.
>
> **What changed:**
>
> | This document says | Now |
> | :--- | :--- |
> | One `GraphImbalance` enum, precedence-ordered, five values (§4) | **Three independent axes** — `POImbalanceState`, `ShipmentImbalanceState`, `LinearStatus` (D9) |
> | A precedence chain and truth table (§4–§5) | **No precedence anywhere** (D27). The truth table describes an enum that does not exist. |
> | Never compare against ordered quantity (§1) | **Reversed** (D25). `PO_QUANTITY_EXCEEDS_DEMAND` is a real state. §1's bulk-restock scenario is still true — it is simply accepted. |
> | No over-condition except `OVER_DELIVERED` (§2) | **Partially superseded** (D25). Still no `OVER_ALLOCATED`; other over-conditions exist. |
> | `resolution_state` has `ACCEPTED_AS_IS` (§6) | **Removed** (D26). `OPEN` / `RESOLVED` only. |
> | `is_flagged` (§6) | Renamed **`manually_flagged`** (D13) |
> | The worklist filter is `imbalance != NONE AND resolution_state != RESOLVED` (§6) | **There is no worklist** (D27). Staff filter the list on state columns. |
> | One suggested action per row (§8) | **Suggestions live on the detail page** (D27); the list shows states. |
>
> **What survives intact:** §7 (no staleness component — still D11), §10's fan-out warning on
> `po_qty_allocated`, and the tone constraint in §8 (never accusatory — still D12).

**Resolves questionnaire R4 and M3.** Written to a strong recommended position throughout, at the
developer's instruction — each section states a recommendation and the reasoning that produced it, so the
thing to react to is a claim, not a menu.

---

## 1. The correction this study exists to make

The obvious formula is wrong, and it is worth stating plainly before anything is built on it.

The instinct is to compare **what was demanded** against **what was ordered**:

```
under  =  demand_qty  >  po_qty_purchased + po_qty_waiting_for_purchase
over   =  po_qty_purchased + po_qty_waiting_for_purchase  >  demand_qty
```

Both halves are wrong, because `quantity_ordered` and `quantity_allocated` are different numbers and only
one of them is about this demand.

`PurchaseOrderLine.quantity_ordered` is how many units the line buys.
`PurchaseOrderDemandLink.quantity_allocated` is how many of those units are claimed as fulfilling a
specific demand. D14 is explicit that a purchase order may exist with **zero** linked demands — that is how
proactive and bulk restocking is modelled, deliberately.

So consider a line ordering 1000 widgets for stock, against which someone later allocates a 10-unit demand.
The graph now holds `demand_qty = 10`, `quantity_ordered = 1000`, `quantity_allocated = 10`. That graph is
**completely healthy** — 990 units of intentional stock, and a demand fully covered. The formula above
reports it as over-ordered by 990. Every bulk restock in the system would light up the worklist, and the
worklist would be abandoned inside a week.

> **Recommendation 1.** Imbalance compares `demand_qty` against **allocated** quantities, never against
> ordered quantities. `quantity_ordered` describes the commercial document; `quantity_allocated` describes
> the commitment to this demand. Only the second is a claim about whether the demand is covered.

A useful way to hold it: **ordered vs. allocated is not an imbalance, it is inventory strategy.** The
difference is unallocated stock the business chose to buy. Nothing about it needs resolving.

---

## 2. The second consequence: "over" mostly is not a thing

`PurchaseOrderDemandLinkValidator` raises `AllocationCapExceeded` when an allocation would exceed a demand's
outstanding requested quantity (D28). Over-allocation is therefore **guarded against at the moment it is
attempted**, and only reachable when a user deliberately overrides via `allow_raise_request` — at which
point the demand's own quantity is raised to match, and the graph is balanced again by construction.

> **Recommendation 2.** There is no `OVER_ORDERED` / `OVER_ALLOCATED` state. It is already prevented
> upstream, and a state that fires approximately never is a state that misleads the person reading the enum
> into thinking the system checks for something it does not.

This also avoids the vocabulary collision flagged in questionnaire M1: "over-allocation" already has a
precise meaning in this codebase (`AllocationCapExceeded`) and must not acquire a second one.

**The real "over" is on the arrival side**, where nothing guards it: a vendor ships 12 against an order for
10, and `qty_accepted` exceeds what anyone asked for. That is a genuine, common, unpreventable condition —
and per questionnaire G4 it is usually *a vendor fact learned late*, not anybody's mistake.

---

## 3. The axes that actually matter

Three independent comparisons, each answering a different operational question:

| # | Comparison | Question it answers | Actionable? |
| :--- | :--- | :--- | :--- |
| A | `demand_qty` vs `po_qty_allocated` | Is the demand covered by a commitment at all? | **Yes** — allocate, or raise a PO |
| B | `po_qty_allocated` vs `po_qty_allocated_purchased` | Is the commitment on a real, placed order, or stuck in a draft? | **Yes** — place the order |
| C | `qty_accepted` vs `demand_qty` | Did more (or less) arrive than was asked for? | **Yes** — absorb, return, or reconcile |

Axis B is the one that is easy to miss. A demand can be fully allocated and still completely stalled,
because the purchase order it is allocated to was never placed. That graph looks covered on axis A and is
doing nothing in the world. It is precisely the sort of thing this surface exists to catch, and it is
invisible to any formula that only compares demand against allocation.

---

## 4. Recommended states

> **Recommendation 3.** One enum, `GraphImbalance`, evaluated in **precedence order, first match wins** —
> mirroring `GraphSummaryManager._derive_status`'s existing documented approach (D86) rather than
> introducing a second style on the same model.
>
> **Do not fold these into `GraphSummaryStatus`.** That column answers *"where is this in the workflow"*;
> this one answers *"is this a problem"*. D71/D76 already established for `PurchaseOrder` that those are
> separate axes deserving separate columns, and the same reasoning applies unchanged.

| Precedence | State | Condition | Meaning |
| :--- | :--- | :--- | :--- |
| 1 | `UNATTACHED` | no member demands (`demand_qty = 0` with ≥1 PO line or shipment line) | Purchasing activity with nothing requesting it |
| 2 | `OVER_DELIVERED` | `qty_accepted > demand_qty` | More arrived than was ever asked for |
| 3 | `UNDER_ALLOCATED` | `demand_qty > po_qty_allocated` | Demand not fully committed to any order |
| 4 | `AWAITING_PLACEMENT` | fully allocated, but `po_qty_allocated_purchased < po_qty_allocated` | Committed, but sitting on an unplaced order |
| 5 | `NONE` | none of the above | Nothing needs a human |

### Why this precedence

- **`UNATTACHED` first** because a graph with no demand has `demand_qty = 0`, which makes almost every other
  comparison degenerate — it would read as over-delivered the instant anything arrives. It has to be caught
  before the arithmetic runs. **This is also the answer to questionnaire M3**, decided by example as
  requested: the demand-less condition from R3 is a *value in this enum*, not a standalone boolean.
- **`OVER_DELIVERED` above `UNDER_ALLOCATED`** because over-delivery involves material physically present
  and unaccounted for — money already spent and stock already occupying space. Under-allocation is a
  *future* problem; over-delivery is a *present* one. This is the ordering most likely to be challenged and
  the one to challenge if any.
- **`AWAITING_PLACEMENT` last among the real states** because it is the mildest: everything is correct,
  someone just has not pressed the button yet.

### The naming, deliberately

`UNDER_ALLOCATED` and not `UNDER_ORDERED` — the whole point of §1 is that ordering is not the measure.
`UNATTACHED` and not `DEMAND_LESS` — it describes the relationship rather than an absence, and it survives
the case where a demand is later attached.

---

## 5. Truth table

Filling in questionnaire R4's requested table, restated against the axes that survived §3. `—` marks
combinations the guards make unreachable.

| # | No demand | accepted > demand | allocated < demand | placed < allocated | State | Reachable? |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| 1 | no | no | no | no | `NONE` | yes |
| 2 | no | no | yes | no | `UNDER_ALLOCATED` | yes |
| 3 | no | no | no | yes | `AWAITING_PLACEMENT` | yes |
| 4 | no | no | yes | yes | `UNDER_ALLOCATED` | yes — partly allocated, and that part unplaced |
| 5 | no | yes | no | no | `OVER_DELIVERED` | yes — the classic vendor overship |
| 6 | no | yes | yes | * | `OVER_DELIVERED` | yes — overshipped against a partial allocation |
| 7 | yes | * | * | * | `UNATTACHED` | yes — early PO, or a reactively received shipment |
| 8 | no | * | * | * | — | over-allocation unreachable; see §2 |

**The answer to "AND or OR"** that R4 asked for: neither. It is a **precedence chain**, which is the third
option the question did not offer and the one the existing codebase already uses. AND produces a nearly
empty worklist; OR produces a graph in three states at once with no way to sort. Precedence gives every
graph exactly one state, one action, and a sortable column.

---

## 6. Is `NONE` the same as "resolved"?

No, and conflating them is the trap.

`NONE` means *the arithmetic currently balances*. It is derived, it is recomputed on every
`recalculate()`, and it can flip back the moment anything changes.

**Resolved** is a human statement: *"I looked at this and it is finished, or it is fine as it is."* It is
the column that lets a legitimately-permanently-imbalanced graph leave the worklist — the vendor overshipped
12 against a demand for 10, everything was accepted, the business is done, and the graph will read
`OVER_DELIVERED` forever. Without a human override that row is immortal noise, which is the failure mode
that kills worklists (questionnaire M6).

> **Recommendation 4.** The worklist filter is **`imbalance != NONE` AND `resolution_state != RESOLVED`**.
> Two columns, one derived and one human, deliberately not merged.

### Recommended human columns

| Column | Type | Written by |
| :--- | :--- | :--- |
| `resolution_state` | enum: `OPEN` (default) / `RESOLVED` / `ACCEPTED_AS_IS` | `GraphResolutionManager` only |
| `is_flagged` | boolean, default `False` | `GraphResolutionManager` only |
| `priority` | reuse `DemandPriority` (`low` / `medium` / `high` / `critical`), nullable | `GraphResolutionManager` only |

`RESOLVED` and `ACCEPTED_AS_IS` are split because they mean different things to the next person: *"this got
fixed"* versus *"this is permanently lopsided and that is fine."* The second is the vendor-overship case and
it is common enough to deserve its own word rather than being filed under a word that implies action was
taken.

`priority` reuses `DemandPriority` rather than inventing a parallel vocabulary — questionnaire M1's standing
concern about words meaning two things.

> **Recommendation 5.** These three columns are the **only** exception to "`GraphSummaryManager` writes
> every column on `GraphSummary`". `recalculate()` must never touch them, and that boundary should be
> stated in the model docstring, since the whole model's discipline is otherwise the opposite.

Their behaviour across merges and splits is decided in
[`graph_formation_policies_study.md`](graph_formation_policies_study.md) §4.

---

## 7. Why there is no staleness / age component

Age is the most obviously useful signal here and it is **deliberately excluded from v1**.

The reason is that there is nothing trustworthy to measure it with. Questionnaire M5 declined to add
last-activity columns to `GraphSummary`, on the sound grounds that keeping them current would mean every
demand, PO, and shipment write reaching over to touch the graph — an ongoing tax on every entity in the
sector for a display nicety. And the timestamps that already exist do not mean what staleness needs:

- `updated_at` moves on **every** `recalculate()`, which fires whenever any member changes for any reason,
  including merges caused by an unrelated graph. It means *"last recomputed"*, not *"last happened"*.
- `created_at` means *"when this component first formed"*, which merges destroy — the survivor keeps its
  own, the absorbed row's is deleted with it.

> **Recommendation 6.** Ship v1 with no time component, and say so explicitly rather than leaving its
> absence to be read as an oversight. Adding staleness later is a decision to reverse M5 and pay for the
> columns, and it should be made on its own merits when someone has felt the absence — not smuggled in now
> on a timestamp that does not mean what it appears to mean.

Note that a Buyer is not left blind: `AWAITING_PLACEMENT` catches the most common form of "stuck", and it
catches it by *structure* rather than by elapsed time, which is more precise anyway.

---

## 8. Suggested actions

Questionnaire G2 makes suggestions **core scope** — *"it's only useful if it has suggestions."* One action
per state, phrased as an instruction.

| State | Suggested action | Where the user goes |
| :--- | :--- | :--- |
| `UNATTACHED` | "No demand is requesting this material. Link it to an existing demand, or raise one." | the PO line / shipment line |
| `OVER_DELIVERED` | "{n} more units arrived than were requested. Raise the demand to match, or record the surplus." | the shipment line, or the demand |
| `UNDER_ALLOCATED` | "{n} units are not yet on any order. Allocate to an existing purchase order line, or raise a new order." | the demand |
| `AWAITING_PLACEMENT` | "Everything is allocated, but purchase order {po} has not been placed." | the purchase order |
| `NONE` | *(no action shown)* | — |

> **Recommendation 7.** Action text is **derived at read time by a Narrator**, never stored. The states are
> schema and change rarely; the wording is judgment and will be tuned for months. Storing the sentence would
> mean a migration and a full-table recalculate every time somebody improves a phrase.

**Tone constraint, from questionnaire G4.** An `OVER_DELIVERED` graph is usually the system *learning a
vendor fact late*, not a mistake anyone made. The wording says what happened and what to do; it never
implies error. "12 more units arrived than were requested" — not "excess receipt discrepancy".

---

## 9. The case that would have dominated the list, and why it does not

Every newly created `PartDemand` gets its own single-member graph (D82 node-init). By count, these will be
the most common rows in the table by a wide margin, and the questionnaire flagged them as a likely source of
noise.

They are not noise. A fresh demand for 10 units with nothing allocated evaluates to
`demand_qty (10) > po_qty_allocated (0)` ⇒ **`UNDER_ALLOCATED`**, with the action *"10 units are not yet on
any order."*

That is correct, it is the single most useful row a Buyer can be shown, and it means the worklist is
populated with real work from day one rather than needing a special case to hide the majority of its rows.
The questionnaire's "undecidable case" resolved itself once the comparison moved from ordered to allocated.

---

## 10. What this study asks the schema for

Feeding [`model_diagram.md`](model_diagram.md) and phase 1's data plan.

**New derived columns on `GraphSummary`:**

| Column | Derivation |
| :--- | :--- |
| `po_qty_allocated` | Σ `quantity_allocated` over active, non-deleted `PurchaseOrderDemandLink` rows whose line is a member |
| `po_qty_allocated_purchased` | the same sum, restricted to links whose line's `PurchaseOrder.status` has reached `Placed` or later |
| `po_qty_ordered` | Σ `quantity_ordered` across member lines — the total the documents buy |
| `imbalance` | the enum above, precedence-evaluated |

**Column being retired:** `po_qty_waiting_for_purchase`, per the developer's own suggestion — it is
`po_qty_ordered − po_qty_purchased` and does not need storing. Storing a difference alongside both of its
operands is three places for two facts to disagree.

**Implementation constraint that must not be lost.** `po_qty_allocated` sums across
`PurchaseOrderDemandLink`, which is a **second multi-row relation** relative to the member-line queryset.
`GraphSummaryManager`'s docstring records that D67 already caught exactly this bug class once — a joined
`Sum()` alongside another multi-row relation fans out and silently multiplies. **These two aggregates must
be their own separate queries** over `PurchaseOrderDemandLink`, filtered by
`purchase_order_line__graph_id`, never annotated onto the line queryset. Carried into phase 1's
control-layer plan as an explicit note.
