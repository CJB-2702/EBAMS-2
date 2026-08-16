---
okf_version: "0.1"
type: "Kit Document"
title: "Demand Graph Surfaces — Current State"
description: "What was built for the demand-graph surfaces, where it lives in the code, what is deliberately absent, and what is still open."
tags: [starter-kit, procurement, graphs]
context_tier: 2
---

# Demand Graph Surfaces — Current State

**Status: backend BUILT and tested, 2026-08-16.** Schema, derivations, and the one write path exist.
No UI beyond the pre-existing swimlane detail page.

This kit no longer describes a plan. It describes **what is in the code**, so read it as a map rather
than as a specification. Where it disagrees with `app/procurement/`, the code wins.

---

## The problem it solved

A `GraphSummary` — one row per connected component of the demand / PO-line / shipment-line network — was
reachable **only** by clicking through from an entity already on screen. The row carried quantities but
nothing identifying what it was about or whose it was, so there was no way to ask *"what needs attention?"*
or *"what is happening for this part?"*

Graphs are now findable by part and by domain, and carry three independent status axes describing whether
and how they need a human.

---

## What is in the code

### Documents that still matter

| File | Role |
| :--- | :--- |
| [`all_statuses_review.md`](all_statuses_review.md) | **Status authority.** Every axis on `PartDemand` and `GraphSummary`, with conditions. |
| [`decisions.md`](decisions.md) | The reasoning record — why each choice, and what was rejected. Stale where it disagrees with the code; kept because the arguments are not recoverable from it. |
| [`functionality_and_roles.md`](functionality_and_roles.md) | Capability × persona matrix. The handoff contract to `/front-end-kit`. |
| [`superseded/`](superseded/) | Working history — questionnaire, brainstorming, the original studies, the model diagram. Nothing here is current. Kept because this kit is untracked in git and deleting it would be permanent. |

Phase folders are **deleted**. They were build plans and the build is done.

### Schema

**No new tables.** Columns on two existing ones.

`GraphSummary` — [`app/procurement/models/graph/graph_summary.py`](../app/procurement/models/graph/graph_summary.py)

| Column | Meaning |
| :--- | :--- |
| `part` | The one part every member shares. Nullable **only** for the instant inside `initialize_node()` before a member exists to read it from. |
| `primary_domain` | Search scope. Most common by PO line, falling back to demands, then shipment lines; ties on lowest id. |
| `demand_qty` | Σ `quantity_requested` across member demands |
| `po_qty_allocated` | Σ `PurchaseOrderDemandLink.quantity_allocated` — units spoken for on any PO |
| `po_qty_purchased` | Same, restricted to lines whose PO reached `Placed`+ |
| `shipment_qty_allocated` | Σ `PurchaseOrderShipmentLink.quantity_allocated` |
| `shipment_qty_accepted` | Σ `ShipmentLine.quantity_accepted` — **the** arrival figure |
| `linear_status` | Pipeline position |
| `po_imbalance_state` | Is the demand committed to orders? |
| `shipment_imbalance_state` | Did we receive what we ordered? |
| `error_code` | Key naming an end-state mismatch, or `""` |
| `resolution_state` · `manually_flagged` · `priority` | **Human judgment.** The only columns `recalculate()` never touches. |

Retained from D81 and still read by the detail template: `qty_shipments_in_route`,
`qty_shipments_delivered`, `qty_accepted`, `qty_rejected`, `intake_qty_recorded` (always 0), `status`,
`swimlane_diagram`.

**Retired:** `po_qty_waiting_for_purchase`. It was `ordered − purchased` — three places for two facts to
disagree.

`PartDemand` gains `linear_status`, inherited from its parent graph.

### Enums

[`app/procurement/models/graph/enums.py`](../app/procurement/models/graph/enums.py) — `LinearStatus`,
`POImbalanceState`, `ShipmentImbalanceState`, `GraphResolutionState`, plus `RESTING_VALUES` (the filter
definition for "condition ≠ balanced").

### Control layer

| Class | Role |
| :--- | :--- |
| `GraphSummaryManager.recalculate()` | Derives every column except the three human ones. Also pushes `linear_status` down onto member demands. |
| `GraphSummaryManager._derive_part_id` / `_derive_primary_domain_id` | Identity |
| `GraphSummaryManager._derive_linear_status` / `_derive_po_imbalance_state` / `_derive_shipment_imbalance_state` / `_derive_error_code` | The four precedence chains |
| **`GraphResolutionManager`** *(new file)* | The **only** writer of `resolution_state`, `manually_flagged`, `priority`. Also owns merge/split survival. |

---

## The five things to know

**1. Three axes, not one score.** `linear_status`, `po_imbalance_state`, and `shipment_imbalance_state`
are independent, each derived by its own precedence chain (first match wins), and none writes another. A
PO administrator needs allocation clarity; a receiving administrator needs delivery clarity. There is
deliberately **no** cross-axis ranking, no severity score, and no single "needs attention" column — staff
filter the columns directly.

**2. The reference points differ on purpose.** The PO axis measures against `demand_qty`. The shipment
axis measures against `po_qty_purchased`, **not** demand — shipments are arrivals against orders. Comparing
arrivals to demand would report the same PO-side shortfall twice.

**3. Three columns invert the model's entire discipline.** Every other column on `GraphSummary` is written
exclusively by `recalculate()`. `resolution_state`, `manually_flagged`, and `priority` are written **only**
by `GraphResolutionManager`. The surrounding convention is uniform enough that the natural assumption
silently wipes user input — `test_recalculate_never_overwrites_the_human_judgment_columns` asserts against
it rather than trusting the docstring.

**4. `po_qty_allocated` is a fan-out trap.** It sums across `PurchaseOrderDemandLink`, a second multi-row
relation. A joined `Sum()` alongside another multi-row relation silently multiplies — the bug class already
caught once in `PurchaseOrderFulfillmentStruct`. These aggregates are **their own queries** and must stay
that way; `test_po_qty_allocated_does_not_fan_out_across_shipment_links` guards it.

**5. A graph is not a thing anyone makes.** It forms, merges, splits, and dies as a side effect of
demand/PO/shipment writes, invisibly to the user doing the writing. There is **no create page**, and despite
three reverse FKs into `GraphSummary`, **no wizard follows from them** — the usual heuristic reads three and
would be wrong.

---

## Behaviour users will notice

- **A resolution clears when the graph merges or splits.** The statement was about a specific set of nodes;
  once nodes join or leave, the thing that was looked at no longer exists. Flag and priority survive —
  configuration-derived state clears, human judgment about importance propagates. A Buyer will experience
  this as their resolution being undone by an unrelated allocation, so it needs an explanation in the UI.
- **`PO_QUANTITY_EXCEEDS_DEMAND` will be the largest non-balanced population in the table.** Every bulk
  restock produces one and nothing clears it. Correct, not a bug — the axis is descriptive, not a task list.
  **Do not design the list as an inbox that must reach zero.**
- **A graph can be reachable by click-through yet absent from your search.** Search filters on
  `primary_domain`; the detail view admits on *any* member domain. First thing to revisit if users say
  "I know that graph exists but I cannot find it."

---

## Deliberately absent

| Not built | Why |
| :--- | :--- |
| Create or delete a graph | Not a thing anyone makes; dies when it loses its last node or is absorbed |
| A numeric drift or severity score | Named states and plain quantities only |
| Cross-axis ranking / "worst-first" | No defensible way to rank a PO problem against a shipment one |
| Staleness or age filtering | No trustworthy timestamp exists. `updated_at` means *last recomputed*; `created_at` is destroyed by merges. `LinearStatus` catches "stuck" structurally instead. |
| Activity thread, comments, or attachments on a graph | Narrative belongs on the nodes, which are stable and user-created. A graph merges and dies without warning. |
| `quantity_received` distinct from `quantity_accepted` | Deferred to the intake build |

---

## Open — pick up here

| # | Item | Notes |
| :--- | :--- | :--- |
| **1** | **`ACCEPTED_AS_IS` does not survive a merge, so it does not do its job.** | It exists to silence a permanently-imbalanced graph for good, but the merge/split reset clears it along with `RESOLVED`. **The sharpest open edge.** One-line fix in `GraphResolutionManager.carry_through_merge` if you want it exempted. |
| 2 | No read surfaces, no routes, no list page | Everything above is backend. `/front-end-kit` consumes `functionality_and_roles.md`. |
| 3 | Cleared resolutions write nothing to the members' activity trail | Decided (D15), not built. Without it a cleared resolution reads as lost input. |
| 4 | Part-match rule is still a soft validator check | `GraphSummary.part` now depends on it. Either harden to a DB constraint or update `PurchaseOrderDemandLinkValidator`'s docstring, which still advertises it as cheap to relax. |
| 5 | No permission codename for the resolution controls | Currently rides on existing procurement permissions. Needs an admin-persona look at the group fixtures. |
| 6 | `decisions.md` numbering collides with the procurement kit | Cite as "demand-graph D23", never bare "D23". |
| 7 | `dev_user_scope.json` fixture is broken | References domain 9; `dev_ownership` defines 1–8. **Pre-existing, not from this build** — it fails on every `refresh_project.py`. |

---

## Verification

```
82 tests, all passing
19 seeded graphs, all with part and primary_domain populated
linear_status:  po_purchased_not_shipped 9 · unlinked 7 · delivered 2 · po_allocated_not_purchased 1
po_imbalance:   balanced 13 · demand_exceeds_allocation 5 · allocation_exceeds_purchased 1
shipment:       balanced 8 · awaiting_delivery 7 · allocation_exceeds_po 3 · not_allocated 1
error codes:    SHIPMENT_ALLOCATION_EXCEEDS_ORDER × 3
```

Schema changes require a full reset — `python refresh_project.py`. Do not accumulate incremental
migrations.
