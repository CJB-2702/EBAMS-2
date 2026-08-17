---
okf_version: "0.1"
type: "Kit Document"
title: "The Graph System"
description: "GraphSummary: what a cluster is, how it forms/merges/splits, the ten quantities and five derived statuses it maintains, the three human columns nothing may overwrite, and the visualizer."
tags: [starter-kit, procurement, graph, policy, okf]
context_tier: 2
personas: [backend, business]
---

# The Graph System

## 1. What problem this solves

Demands connect to purchase order lines many-to-many. Order lines connect to arriving
shipment lines many-to-many. Follow those edges and you get **connected components**:

```
demand A ─┐                    ┌─ shipment line X
          ├─ PO line 1 ────────┤
demand B ─┘                    └─ shipment line Y
                    │
demand C ── PO line 2
```

Everything in that picture is **one procurement situation**. There is no single record
you can point at to ask "did this work out?", because the answer is a property of the
whole cluster: three demands, two order lines, two boxes.

`GraphSummary` is one row per cluster. Every member — `PartDemand`, `PurchaseOrderLine`,
`ShipmentLine` — carries a direct `graph_id` FK back to it, so any page gets cluster-wide
numbers with a plain `WHERE graph_id = X`, never a join fan-out and never an on-request
traversal.

**This reverses an earlier design** in which a resolver walked the network on demand to
answer the same question. Materialized, not computed on read.

---

## 2. A graph is not a thing anyone creates

It forms, merges, splits, and dies as a **side effect** of writes to demands, order lines,
and shipment lines — none of it visible to the user doing the writing.

There is no create page. Despite three reverse FKs pointing at the table, no wizard
follows from them: the usual "more than one reverse FK a user would populate in one
sitting is a wizard" heuristic reads three here and would be wrong, because a user never
populates any of them.

`GraphSummaryManager` is the **only** writer of `graph_id` and of every derived
`GraphSummary` column. Four operations, all wired into write paths that already own graph
membership — no new write path exists solely for graph maintenance.

### `initialize_node`

A demand / order line / arriving line created with no link yet gets its own fresh
**single-member** graph, in the same transaction as its own creation. Called from
`PartDemandFactory`, `PurchaseOrderLineManager.add_line`, `ShipmentLineManager.add_line`.

### `merge`

Creating an active demand↔line allocation, or an arrival↔line allocation joining two
different graphs, **coalesces them**. Every member of the *smaller* graph (by row count)
is re-pointed onto the *larger* graph's id — cheap, because these clusters stay small —
the absorbed summary row is deleted, and the survivor is recalculated.

Wired into `PurchaseOrderDemandLinkManager.allocate()` and `ShipmentLineManager.allocate()`.

### `split_if_disconnected`

Deactivating a demand allocation, or releasing an arrival allocation, may sever the only
bridge holding a cluster together. A **bounded BFS** runs over the graph's own remaining
active edges from an arbitrary surviving member; unreachable members are re-pointed onto a
freshly created summary, and both summaries are recalculated.

No separate safety cap is needed — membership is already bounded by the graph itself, not
by an unbounded traversal target.

Wired into `PurchaseOrderDemandLinkManager.delink()` / `remove_for_line()` and
`ShipmentLineManager.deallocate()`.

### `recalculate`

Recomputes every quantity, every derived status, the identity columns, and the cached
diagram. **Always the last step of the other three** — never left for a caller to remember
separately.

**There is no `commit` parameter anywhere in this manager.** Every method writes
immediately, participating in whatever transaction the caller already holds — a direct
response to an earlier bug where `commit=False` silently meant "skip the write".

---

## 3. The quantities

All ten are recomputed from current member rows.

| Column | Source |
| :--- | :--- |
| `demand_qty` | Σ `PartDemand.quantity_requested` over members |
| `po_qty_allocated` | Σ `quantity_allocated` over active demand links on member PO lines |
| `po_qty_purchased` | the same sum, restricted to lines whose PO reached placed / partially received / received |
| `shipment_qty_allocated` | Σ `quantity_allocated` over active arrival links on member lines |
| `shipment_qty_accepted` | Σ `ShipmentLine.quantity_accepted` over members |
| `qty_shipments_in_route` | member line quantities where the shipment is shipped / at depot / backordered |
| `qty_shipments_delivered` | member line quantities where the shipment is delivered locally or accepted |
| `qty_accepted`, `qty_rejected` | inspection outcomes |
| `intake_qty_recorded` | reserved for the Inventory build |

**Every metric is its own single-table aggregate with only forward (to-one) joins.** Never
a joined `Sum()` alongside another multi-row relation in the same queryset — that fans out
and silently multiplies, and it is a bug class this codebase has already been bitten by
once. No matter how much tidier one query looks, do not merge them.

### Identity columns

- `part` — the one part every member shares. Derived, and null if the cluster somehow
  spans parts.
- `primary_domain` — the single domain the cluster is searchable under. This is what the
  graph list page fences on.

---

## 4. The derived statuses

Three independent precedence chains, evaluated top to bottom, **first match wins** —
never AND/OR combinations.

### `linear_status` — where in the pipeline?

The one status a non-procurement reader can understand without knowing what an allocation
is. **Shared downward**: each member demand carries a copy, so a demand list can show
pipeline position without joining to the graph.

| Value | Condition |
| :--- | :--- |
| `unlinked` | `po_qty_allocated == 0` and `shipment_qty_allocated == 0` |
| `po_allocated_not_purchased` | `po_qty_allocated > 0` and `po_qty_purchased == 0` |
| `po_purchased_not_shipped` | `po_qty_purchased > 0` and `shipment_qty_accepted == 0` |
| `partially_delivered` | `0 < shipment_qty_accepted < demand_qty` |
| `delivered` | `shipment_qty_accepted >= demand_qty` |

Ordering follows the pipeline itself, so a graph always reports the **earliest stage it
has not cleared**. A final fallback returns `unlinked` for the odd case of shipment
allocations with no PO allocation and nothing accepted — material tracked against nothing
ordered.

### `po_imbalance_state` — are the demands committed to orders?

| Value | Condition | Meaning |
| :--- | :--- | :--- |
| `demand_exceeds_allocation` | `demand_qty > po_qty_allocated` | some demand has no order commitment yet |
| `allocation_exceeds_purchased` | `po_qty_allocated >= demand_qty` and `po_qty_purchased < demand_qty` | allocated, but the orders are not placed |
| `po_quantity_exceeds_demand` | `po_qty_purchased > demand_qty` | more bought than anyone asked for |
| `demand_satisfied_excess_allocated` | `po_qty_purchased >= demand_qty` and `po_qty_allocated > po_qty_purchased` | intentional overstocking; no action |
| `balanced` | otherwise | |

**The measure is allocation, not ordered quantity**, for the first two values. A line
ordering 1000 widgets against a 10-unit demand is *healthy* — it is how bulk restocking is
modeled — and an ordered-based comparison would report it as over-ordered by 990.

`po_quantity_exceeds_demand` deliberately surfaces the overbuy case anyway, as its own
filterable value rather than mixed into a ranked list, so an administrator can ask "what
did we buy beyond what anyone requested" — a real purchasing question with no other answer
in the system.

**Expect this to be the largest non-balanced population in the table.** Every bulk restock
produces one and nothing clears it automatically. That is correct and not a bug: this axis
is **descriptive, not a task list**.

### `shipment_imbalance_state` — did we receive what we ordered?

| Value | Condition |
| :--- | :--- |
| `po_ordered_not_allocated_to_shipments` | `po_qty_purchased > shipment_qty_allocated` |
| `shipment_allocation_exceeds_po` | `shipment_qty_allocated > po_qty_purchased` |
| `over_delivered` | `shipment_qty_accepted > po_qty_purchased` |
| `partial_delivery_received` | `0 < shipment_qty_accepted < po_qty_purchased` |
| `shipments_allocated_awaiting_delivery` | `shipment_qty_allocated > 0` and `shipment_qty_accepted == 0` |
| `balanced` | otherwise |

**The reference point is `po_qty_purchased`, never `demand_qty`.** Shipments are arrivals
against *orders*, not against demands. Whether the demand is covered at all is the PO
axis's question, and comparing arrivals to demand here would report the same PO-side
shortfall twice.

`over_delivered` is the genuine, common, unpreventable over-condition: a vendor ships 12
against an order for 10. Nothing guards it upstream, and it is usually the system learning
a vendor fact late rather than anybody's mistake. **Wording that surfaces it must never
imply error.**

### `error_code` — the axes disagreeing

A key (not a sentence) naming an end-state mismatch, or `""`. It fires **only where the
three axes contradict each other** in a way a human should look at — a graph reporting
itself finished while an upstream axis says it is not. An axis being individually
non-balanced is ordinary and is *not* an error; it is already visible on its own column.

| Key | Fires when |
| :--- | :--- |
| `DELIVERED_WITH_UNCOMMITTED_DEMAND` | delivered, yet part of the demand was never committed to any order — usually means material was received against the wrong graph |
| `DELIVERY_EXCEEDS_PURCHASE_ORDER` | delivered, and more arrived than was ordered |
| `SHIPMENT_ALLOCATION_EXCEEDS_ORDER` | more was mapped to shipments than was ever ordered — always an allocation mix-up, never a physical fact |

Rendered as human language at read time, and never accusatorily.

### `status` — legacy

`balanced` / `awaiting_purchase` / `awaiting_shipment` / `awaiting_acceptance`, the *next
unmet stage* checked upstream-first. Kept because existing narrators and the graph detail
template read it, and **superseded in intent by `linear_status`**, which answers the same
question against the allocation-based quantities rather than the shipment-count ones. Do
not add values here; add them to `LinearStatus`.

---

## 5. The three human columns

`resolution_state`, `manually_flagged`, and `priority` are written **only** by
`GraphResolutionManager`, and `recalculate()` must never touch them.

| Column | Values | Question |
| :--- | :--- | :--- |
| `resolution_state` | `open` / `resolved` / `accepted_as_is` | has a person ruled on this? |
| `manually_flagged` | bool | does somebody want eyes on it? |
| `priority` | the demand priority scale, nullable | how urgent is the underlying work? |

**Why the inversion exists.** A derived state answers "does the arithmetic currently
balance", which flips back the instant anything changes. It cannot express *"I looked at
this and I am finished with it."* Without that, a legitimately-permanently-imbalanced
graph — the vendor overshipped 12 against a demand for 10, everything was accepted, the
business is done — is **immortal noise in every filtered list**, which is the failure mode
that kills a worklist nobody can ever get to the bottom of.

`resolved` and `accepted_as_is` are kept distinct because they mean different things to
the next reader: *"this got fixed"* versus *"this is permanently lopsided and that is
fine."*

`resolution_state` is **cleared back to `open` on merge and split**: the ruling was about a
specific set of nodes, and when nodes join or leave, the thing that was looked at no longer
exists.

> **The one rule that is easy to break.** Every other column on `GraphSummary` is derived,
> and the surrounding convention is uniform enough that the natural assumption
> ("everything on this model is derived") will silently wipe a user's input on the next
> unrelated allocation. That is why these three live behind their own manager rather than
> being three more assignments inside `recalculate()`'s `update_fields`.

---

## 6. The visualizer

`GraphSummary.swimlane_diagram` caches mermaid `flowchart LR` source — three subgraphs
(swimlanes), one per member type, with edges drawn between them. It is rebuilt by
`recalculate()`, so the view reads a column and **never builds a diagram per request**.

The visualizer page is **the only page in the application that renders graph membership
directly**. Every other page uses an entity's own `graph_id`-scoped rollup numbers. It
reads the summary and its three member querysets straight off their FKs — no BFS, no
recursion, nothing resembling the retired resolver.

**Domain handling is deliberately unusual here.** There is no fence on the graph lookup
itself: a `GraphSummary` is not itself domain-owned — each *member* is, through its parent.
A member outside the viewer's accessible domains still renders, as plain text with no link
through, following the same cross-domain-reference rule as every other page in the sector.
Never a 404 on a whole graph just because one member happens to be out of fence.

The **list** page, by contrast, does fence — on `primary_domain` — and offers exactly two
filters, which are the two questions a purchasing manager actually asks: resolution state,
and manually flagged.

---

## 7. What reads the graph

| Reader | Reads |
| :--- | :--- |
| Demand list / detail | `linear_status`, copied down onto the demand itself |
| PO and shipment detail | the entity's own `graph_id` rollups |
| Graph list | `primary_domain`, `resolution_state`, `manually_flagged` |
| Graph visualizer | everything, plus the cached diagram and the member lists |
