---
okf_version: "0.1"
type: "Kit Document"
title: "Brainstorming Session — 2026-08-15"
description: "Narrative record of the session that produced this kit: how it ran, what was established, what reversed, and what carries into implementation."
tags: [starter-kit, brainstorming, procurement, graphs]
context_tier: 2
---

# Brainstorming Session — 2026-08-15

## Goal

Plan a utility surface over the existing demand-graph network: search graphs by part, show quantity
imbalance, filter to what needs attention, and suggest what to do about it.

## How the session ran

Four stages, in order: a naming deliberation, a business-persona pass to generate use cases, the
questionnaire, and a six-question interrogation. The kit was generated after the interrogation, with two
policy studies written to strong recommended positions at the developer's instruction.

The developer's framing at the outset — *"I have done a TON of deliberation and design back and forth and my
goal is to really find a way to do things best"* — set the tone: the value of the session was in finding the
decisions that were wrong, not in producing documents quickly.

---

## The five findings that changed the design

### 1. Graphs could not be queried by part at all

The developer flagged this as critical on instinct before any code was read, and was right.
`GraphSummary` carried its eight quantity columns, `status`, and the cached swimlane diagram — and nothing
identifying what the graph was *about*. `part_id` lived only on member rows.

The recommendation offered was a **nullable** column meaning "the shared part, or NULL if members disagree",
hedging against the part-match guard being relaxed later for kits or substitutes. **The developer rejected
the hedge** and closed the door instead: cross-part graphs are disallowed, the column is non-nullable.

That is the stronger decision, and it has a consequence worth tracking — a guard that documented itself as
cheap to relax is now load-bearing for a stored column (D3).

### 2. Comparing demand against *ordered* quantities would have broken the entire feature

The most valuable correction of the session, and it came from the developer, late, almost in passing:
*"consider we can add as many columns as needed, ex to po allocated, po_purchased as two separate columns."*

`quantity_ordered` and `quantity_allocated` are different numbers, and D14 permits a PO with zero linked
demands because that is how bulk restocking is modelled. A line ordering 1000 widgets with a 10-unit demand
allocated against it is **healthy** — but the drafted formula would have reported it as over-ordered by 990.
Every bulk restock in the system would have lit up the worklist, and the worklist would have been abandoned
within a week.

**Ordered vs. allocated is not an imbalance — it is inventory strategy.** (D7.)

Two things fell out of the correction. `OVER_ORDERED` disappeared as a state, because `AllocationCapExceeded`
already guards over-allocation upstream (D8) — the real "over" is on the arrival side, where nothing guards
it. And the case that had looked like a noise problem stopped being one: a brand-new demand with nothing
allocated evaluates to `UNDER_ALLOCATED` with the action *"raise a PO"*, which is the most useful row a
buyer can be shown. Those rows dominate the worklist as **work**, not noise.

### 3. Read-only was clean, and wrong

Questionnaire M6 said nothing on a graph should be human-editable. Clean, and it dodged the merge/split
problem entirely.

The interrogation priced the consequence: a vendor overships 12 against a demand for 10, everything is
accepted, the business is finished — and that graph reads `OVER_DELIVERED` **forever**, alongside every
other legitimately-closed-but-imbalanced graph. Within months the list is mostly noise, which is the normal
way this kind of tool dies.

The developer reversed to three human columns (D13). That reopened the merge/split question M6 had dodged,
which is resolved by a single principle rather than four arbitrary cases:

> **Configuration-derived state clears when the configuration changes; human judgment about importance
> propagates.** (D14.)

And because a resolution silently clearing is indistinguishable from lost input, clearing writes an
explanatory note to the members' activity trails (D15).

### 4. The activity feed was asking to merge three things, one of which did not exist

M5 asked for a merged, time-ordered activity section. The infrastructure turned out to be asymmetric:
`PurchaseOrder` and `Shipment` each have an `event` OneToOne with real comment threads; `PartDemand` has no
event FK at all — its Narrator writes `PartDemandUpdate` rows, an append-only *state-transition journal*.

Merging would have presented a state change and somebody's comment as peers. **Three separate labelled
feeds** (D16), and no comment thread built for `PartDemand` just to make them uniform.

### 5. Staleness cannot be measured honestly, so it is not built

Age is the most obviously useful signal for a worklist. M5 declined last-activity columns on sound grounds —
every demand, PO, and shipment write would have to reach over and touch the graph.

That leaves nothing trustworthy: `updated_at` moves on every `recalculate()` and means *last recomputed*;
`created_at` is destroyed by merges. Building staleness on either produces a number that looks meaningful
and is not (D11).

Partly covered anyway: `AWAITING_PLACEMENT` catches the most common way work goes quiet, and catches it
structurally rather than by a clock (D10).

---

## The naming question

The session opened with a proposed umbrella name for the surface. A codebase read surfaced that D81 in the
procurement kit had already considered and **rejected** a weighted drift-score formula under that same
vocabulary, keeping graph status as a plain label — so the candidate name arrived carrying a standing
rejection.

The developer settled on "graphs" for the umbrella, then went further and asked that the withdrawn
vocabulary be removed from the record entirely: *"I made a decision but I as a user can make wrong decisions
or change my mind... I want to see if it pops up naturally if I never mentioned it."*

Handled surgically: the **word** was removed from this kit, from D81, and from the model docstring; the
**decision** it was attached to — that graph status is a plain label, not a weighted score — survives
unchanged. The experiment runs cleanly, the rationale is not lost, and git preserves the original.

Worth noting as method rather than as trivia: removing a word to see whether it re-emerges on its own
merits is a legitimate test, and it only works if the removal is complete. A single surviving mention in a
document nobody reads is enough to re-anchor the answer months later.

---

## Decisions reached

22, recorded in [`decisions.md`](decisions.md). The load-bearing ones:

| | |
| :--- | :--- |
| **D2** | Non-nullable `part` FK; cross-part graphs disallowed |
| **D7** | Imbalance measures **allocated**, never ordered |
| **D9** | One precedence-ordered `GraphImbalance` enum, separate from `GraphSummaryStatus` |
| **D13** | Three human-editable columns — reversing M6 |
| **D14** | The survival principle for merges and splits |
| **D19** | The part surface is part-first, not a filtered list |

## Phases

| | |
| :--- | :--- |
| 1 | Graph identity and scope — the schema, and the one DB reset |
| 2 | Imbalance model — the vocabulary phases 3 and 4 consume |
| 3 | Resolution state — the only write path |
| 4 | Read surfaces — pure composition, stops before the UI |

## Carried into implementation

- **OQ1** — harden part-match to a DB constraint, or document the dependency (phase 1)
- **OQ2** — permission for the resolution controls; needs an admin-persona look at group fixtures (phase 3)
- **OQ4** — is `OVER_DELIVERED` correctly ranked above `UNDER_ALLOCATED`? Cheap to reverse
- **TD1/TD2** — `primary_domain` as a lossy summary, and the reachable-but-not-findable gap
- **OQ7** — received vs. accepted quantities, deferred by the developer out of kit scope

## The two things most likely to be got wrong at build time

1. **The `po_qty_allocated` fan-out.** It sums a second multi-row relation. `GraphSummaryManager`'s docstring
   already records that D67 caught this bug class once. It must be its own query, never annotated onto the
   member-line queryset — and it has a dedicated regression test in phase 1.
2. **`recalculate()` wiping the human columns.** Every other column on the model is derived, so the natural
   assumption silently destroys user input. Phase 3 asserts it directly rather than trusting the convention.
