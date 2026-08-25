---
okf_version: "0.1"
type: "Process Guide"
title: "Graph Association Visualizer — Front-End Plan"
description: "HIGH PRIORITY. Demand-seeded page rendering the full transitive PO/demand/package association network as three linked columns, plus the control layer that resolves it — the graph builder/resolver, the is_in_status_graph flag with its allocate-time and de-link-time policy hooks, worst-of status aggregation, the quantity-coverage ceiling, and the resolver's write of real purchasing/shipment state through the state manager."
tags: [front-end-kit, procurement, admin, diagnostic, graph, high-priority]
context_tier: 2
personas: [frontend, business, backend]
---

# Graph Association Visualizer — Front-End Plan

**Status: high priority.** Build this ahead of its usual place in the sequence.

**Page:** `/procurement/graph-association-visualizer?demand_id=<id>` — **demand-seeded only.** No
`po_id`/`package_id` entry points — scope reduced deliberately; see §2.

**Read this alongside [../../procurement_starter_kit/po_demand_association_graph.md](../../procurement_starter_kit/po_demand_association_graph.md) first**
for the conceptual framing (why `PurchaseOrderDemandLink` is many-to-many in both directions, why
that matters). **This document is now the authoritative spec for the actual algorithm, classes, and
the new `is_in_status_graph` column** — deliberately kept here rather than split back into the
starter kit, per the requester's explicit call to centralize it. Where the two disagree, this
document wins.

## Why this exists, and why it's not purely diagnostic anymore

Originally scoped as an admin-only "visualize the tangle" tool, sitting alongside — never replacing
— a shallow, one-hop read every routine page could use on its own. That shallow read is still
correct for the ordinary case (a demand on one line, or sharing a line with others). But **for a
demand that participates in a real multi-hop graph, the shallow read cannot produce a truthful
purchasing/shipment status at all** — the true state depends on the worst status and the total
quantity across the *whole* connected network, not just this demand's immediate line. So this page
is not just where you go to look at a tangle; it is **where that graph gets resolved and the
demands' real `purchasing_state`/`shipment_state` get corrected** (§5.6). Everything else reads
those ordinary state columns as it always has — no graph-only shadow fields to interpret.

The resolver is not exclusive to this page. The de-link policy (§5.2b) instantiates the same
resolver when an allocation is removed, so the flag and the states settle on that write too.

---

## 1. Page layout

**Page type:** Full-width diagnostic canvas — no hero, no side rail.

| Region | Placement | Contents |
| :--- | :--- | :--- |
| Seed strip | Full width, top | The seed demand's own identity (id, part, qty requested) and its resolved graph-level status (§5.4–§5.5), computed fresh on this load |
| Three columns | Full width, below | **Demands** (left) · **PO Lines**, grouped by PO (center) · **Packages** (right) |
| Connector overlay | Drawn across all three columns | Lines from each demand row to every PO line it's linked to (`PurchaseOrderDemandLink`), and from each PO line to every package line pointing at it (`PackageLine.purchase_order_line`) |

**Do not render the join rows as their own visible rows or a fourth column.** A
`PurchaseOrderDemandLink` or a `PackageLine.purchase_order_line` FK is never its own row here — it
**is** the connecting line drawn between the two rows it joins.

### Column contents

- **Demands column** — one row per `PartDemand` node in the resolved set: id, part,
  `quantity_requested`, priority, four-axis badges. Click-through to demand detail.
- **PO Lines column, grouped by PO** — POs as sub-headers (PO number, vendor, status badge), lines
  beneath: line number, part, `quantity_ordered`. A PO's unrelated lines still render, muted — the
  traversal is PO-inclusive (§5.3), so the display matches what was actually walked.
- **Packages column** — one row per `Package` (its lines collapse into the package row, with a
  small per-line breakdown on hover/expand) — package number, status badge, `mixed_po_assignments`.

### Connector rendering

Plain layered SVG: each column renders as ordinary server-rendered markup first (F5 rule), then an
SVG overlay positions `<line>` elements between connected rows using their rendered positions
(`getBoundingClientRect()`) — a bipartite line diagram, not a force-directed layout, doesn't need a
graph library. Hovering/focusing a row highlights only its own connector lines and dims the rest.

---

## 2. URL parameters — demand-seeded only (Tier 1 rule, scope reduced)

`?demand_id=<id>` is the **only** accepted seed. No `po_id`/`package_id` entry points — cut to keep
this page's first build small; a demand is the natural origin (a Requester or Buyer looking at one
demand wondering why its status looks odd), and PO-seeded or package-seeded views can be added later
if actually wanted.

**Inbound link:** demand detail's purchasing axis card (`part_demand_workflows.md` §2.4) — see that
document's revision below for exactly where and when it appears.

---

## 3. No safety cap or truncation UI — deliberately deferred

`po_demand_association_graph.md` raised a general safety-cap concern; **not built right now.** The
requester's assessment: real graphs here shouldn't exceed ~50 nodes given D28/D58's natural bounds
(§4 there), so the truncation banner, the "graph continues beyond N nodes" UI, and any hard node-
count cutoff are skipped for this pass. The resolver (§5.3) still terminates correctly on its own
(BFS over a finite, deduplicated node set) — this section is only about *not* building defensive UI
for a failure mode not expected to occur yet, not about the algorithm being unbounded in practice.
Revisit if real data ever approaches that size.

---

## 4. Key things to note

- **This page does write, and it writes through the normal write path.** The resolver corrects the
  real `purchasing_state`/`shipment_state` of every demand in the graph via
  `PartDemandStateManager.transition(...)` (§5.6). A read page performing writes on load is a
  deliberate, documented exception — not a general precedent for other read pages.
- **Empty/trivial graphs still render meaningfully** — a demand with exactly one line and no sharing
  produces a graph of one demand, one PO line, and whatever packages point at that line. Render it
  the same way as a larger tangle.

---

## 5. Control layer — the graph resolver

This section is the actual algorithm and class shapes, kept here per the requester's explicit
instruction rather than split into the starter kit. A backend implementer should be able to build
directly from this section.

### 5.1 Detecting the graph condition

The condition that makes a demand's status *not* resolvable from a one-hop read: any PO line it's
linked to also carries another active demand link.

```
def has_graph_condition(demand) -> bool:
    for link in PurchaseOrderDemandLink.objects.filter(part_demand=demand, is_active=True):
        sibling_count = PurchaseOrderDemandLink.objects.filter(
            purchase_order_line=link.purchase_order_line, is_active=True
        ).count()
        if sibling_count > 1:
            return True
    return False
```

This check (or its cached result, §5.2) is what decides whether a demand's purchasing display can
use the cheap one-hop formula or must defer to this page's cached graph resolution.

### 5.2 `PartDemand.is_in_status_graph` — new column, and its allocate-time policy hook

A new `BooleanField(default=False)` on `PartDemand`. **Not computed on read** — maintained
proactively at write time, the same shape as `Package.mixed_po_assignments`/`has_splits`:

> **Policy, added to `PurchaseOrderDemandLinkManager.allocate(...)` (or its validator/policy
> class):** any time an allocation causes a `PurchaseOrderLine` to carry **two or more** active
> `PurchaseOrderDemandLink` rows, set `is_in_status_graph = True` on **every** demand currently
> linked to that line — not just the newly-added one. The first demand on a line that just became
> shared retroactively becomes graph-eligible too, at the same moment.

**Why this column, not a computed property:** every list/detail read needs an instant, indexed
answer to "does this demand's display need the graph, or is the one-hop formula good enough" —
`has_graph_condition()` above is not something to run per row in a list query.

### 5.2b De-link policy — resolve on removal, and clear the flag when the graph is gone

The flag is **not** sticky-forward. Setting it on allocation without a matching teardown on de-link
leaves demands permanently flagged as graph-participants long after their last shared line was
removed, which pushes every later read down the expensive path for no reason and makes the flag
untrustworthy as a signal.

> **Policy, added to `PurchaseOrderDemandLinkManager.delink(...)` (and `release(...)`, which
> de-activates a whole PO's allocations for the same reason):** after the link row is
> soft-deleted / de-activated, instantiate a `PoDemandAssociationGraphResolver` seeded on the
> **de-linked demand** and `.resolve()` it. Then:
>
> 1. If the resolution finds **no** line in `visited_line_ids` carrying two or more active
>    `PurchaseOrderDemandLink` rows, the demand is no longer in a graph — set
>    `is_in_status_graph = False` on it.
> 2. If it **is** still in a graph, leave the flag `True` and let the resolve's own state writes
>    (§5.6) stand — the network it remains part of just got smaller, and its worst-of status and
>    quantity ceiling may both have moved.
> 3. Either way, **every other demand in `visited_demand_ids`** gets the same treatment in the same
>    transaction. Removing one demand from a shared line can drop that line to a single remaining
>    link, which un-graphs the *other* demand — the mirror image of the allocate-time rule where the
>    first demand on a newly-shared line retroactively becomes graph-eligible.

**Also run it on the abandoned side.** If the de-linked demand's own resolution no longer reaches
the line it was just removed from (the common case — that was its only tie to that PO), resolve a
second graph seeded from any one demand still on that line, so the demands left behind are
re-evaluated too. Skip this when the line has zero remaining active links; there is nothing left to
re-evaluate.

**Cost.** This makes de-link more expensive than it was — it now walks a BFS instead of touching one
row. That is accepted: de-linking is a deliberate, low-frequency Buyer action (D4), not a hot path,
and paying the walk once at write time is cheaper than every subsequent read guessing from a stale
flag. `allocate(...)` keeps its cheap sibling-count check (§5.2 above) — becoming graph-eligible is
knowable from one line, while *ceasing* to be requires the walk.

### 5.3 The resolver — breadth-first, PO-inclusive, deduplicated

Proposed class: **`PoDemandAssociationGraphResolver(seed_demand)`**, one public method,
`.resolve() -> GraphResolution`.

```
visited_demand_ids = {seed_demand.id}
visited_line_ids = set()
frontier = [seed_demand]

while frontier:
    next_frontier = []
    for demand in frontier:
        line_ids = PurchaseOrderDemandLink.objects.filter(
            part_demand=demand, is_active=True
        ).values_list('purchase_order_line_id', flat=True)

        for line_id in line_ids:
            if line_id in visited_line_ids:
                continue
            # PO-inclusive: pull in every line of this line's PO, not just this one —
            # a Buyer acts on a whole PO, so the graph treats the PO as the unit.
            po_id = PurchaseOrderLine.objects.values_list('purchase_order_id', flat=True).get(id=line_id)
            po_line_ids = set(
                PurchaseOrderLine.objects.filter(purchase_order_id=po_id).values_list('id', flat=True)
            )
            visited_line_ids |= po_line_ids

            new_demand_ids = set(
                PurchaseOrderDemandLink.objects.filter(
                    purchase_order_line_id__in=po_line_ids, is_active=True
                ).exclude(part_demand_id__in=visited_demand_ids)
                .values_list('part_demand_id', flat=True)
            )
            for d_id in new_demand_ids:
                visited_demand_ids.add(d_id)

    if new_demand_ids:
        next_frontier = list(PartDemand.objects.filter(id__in=new_demand_ids))
    frontier = next_frontier
```

(Sketch, not final code — bulk-fetch the frontier's demands in one query rather than per-id, as
shown; the point is the shape: BFS, dedupe on both node types, PO-inclusive line expansion.)

**Package join, after the line set is final:**

```
package_lines = PackageLine.objects.filter(purchase_order_line_id__in=visited_line_ids)
packages = {pl.package for pl in package_lines}   # distinct, via the FK
```

### 5.4 Aggregating package/purchase state — worst of

Two independent "worst of" rollups, each over the **distinct** header records touched by the graph
(not per-line, per-header):

- **Purchase state** = the least-advanced `PurchaseOrder.status` among every distinct PO owning a
  line in `visited_line_ids`. Ordering: `Draft < Placed < Partially Received < Received`.
  **`Cancelled` is not part of the linear order** — a cancelled PO in the mix is a distinct,
  flagged condition ("this network includes a cancelled order"), not simply "worse progress" than
  `Draft`. Surface it separately rather than forcing it into the ordinal comparison.
- **Package/shipment state** = the least-advanced `Package.status` among every distinct `Package`
  found via the package join (§5.3) — this is the existing "least advanced status wins" rule from
  `package_lifecycle.md`, generalized from "one demand, several packages" to "this whole graph,
  every package touching it."

### 5.5 The quantity ceiling — partial fulfillment cap

```
ordered_total   = Σ PurchaseOrderLine.quantity_ordered   for line in visited_line_ids
requested_total = Σ PartDemand.quantity_requested         for demand in visited_demand_ids

if ordered_total < requested_total:
    resolved_state_ceiling = "Partially Fulfilled"
```

This is a **cap**, applied after §5.4's status rollups: even if every PO in the graph is `Placed`
and every package `Accepted`, the graph's overall resolved state cannot claim better than
"Partially Fulfilled" while the total ordered quantity falls short of total requested quantity
across the network. When `ordered_total >= requested_total`, the ceiling doesn't apply and §5.4's
worst-of statuses stand as the resolved state directly.

### 5.6 Resolve, then write the real state

**On every resolve — this page's load, and the de-link policy (§5.2b) — the resolver writes the
graph-derived result onto every `PartDemand` in `visited_demand_ids` as their actual purchasing and
shipment state.** These are the real `purchasing_state` and `shipment_state` columns, not shadow
cache fields. For a demand in a graph, the graph result *is* the truth about where its purchase and
its shipment stand; storing that answer somewhere else and leaving the real columns holding a
one-hop value known to be wrong would mean every list, filter, export, and report reads the wrong
number while the right one sits in a field only one page knows to look at.

**Written through `PartDemandStateManager.transition(...)`, not `bulk_update`.** D22/D24's write
contract stands unchanged — the state manager remains the single write path for all four axes, and
the resolver is a caller of it like any other, not an exception to it. Per demand whose resolved
value differs from its stored value, one `transition(axis, to_stage, actor, notes)` call per axis
that moved:

- `purchasing_state` ← §5.4's worst-of purchase rollup, capped by §5.5.
- `shipment_state` ← §5.4's worst-of package rollup, capped by §5.5.
- Demands whose resolved value already matches are skipped — no no-op transitions, so the axis
  history stays a record of real movement rather than of page visits.
- `notes` identifies the writer (e.g. *"Graph resolution from demand #<seed>, N demands / M lines"*)
  so an axis history entry is traceable to the resolve that caused it, and distinguishable from a
  human's action.
- `actor` is the user who triggered the resolve — the viewer on this page, the de-linking Buyer in
  §5.2b. The transitions are attributable to a real person, not to a null system user.

**The resolve runs inside one transaction** covering all of the graph's transitions, so a graph is
never left half-corrected.

**Ordering caution for the implementer:** the state manager may enforce legal transitions per axis.
A graph resolve can legitimately move an axis **backward** (a newly-discovered cancelled PO in the
network, or a quantity ceiling that just started applying). If the axis machine forbids that,
the graph resolver needs an explicit, permitted "correction" transition reason rather than a
back-door write — resolve that when building `PartDemandStateManager`, and do not work around it by
writing the column directly.

**Retain one metadata column: `graph_resolved_at`** (timestamp). It is not a cache of the state —
the state is real now — but it answers "when was this graph last walked", which is what tells a
viewer whether a `is_in_status_graph` demand's displayed state was confirmed five seconds or five
months ago. `part_demand_workflows.md`'s purchasing axis card shows it, alongside the ordinary
state badges, whenever `is_in_status_graph` is true.

**Staleness is now bounded on the write side, not just the read side.** Because §5.2b resolves on
every de-link and §5.2 flags on every allocate, the states of a graph demand are corrected at each
structural change to the graph, not only when a human happens to open this page. Non-structural
drift (a PO's own status advancing, a package being accepted) still only lands on the demands at
the next resolve — that gap is real and `graph_resolved_at` is what makes it visible.

### 5.7 What's explicitly out of scope for this pass

- No safety cap / truncation handling (§3).
- No `po_id`/`package_id` seeding (§2).
- No background/scheduled re-resolution — states are only re-derived when a human opens this page
  for that demand, or when an allocation is de-linked/released (§5.2b). A PO or package advancing
  its own status does not push into the graph's demands until one of those happens.
- No permission model spec beyond "gate it, don't leave it open" — exact permission TBD alongside
  the rest of this kit's D62 enforcement pass.
