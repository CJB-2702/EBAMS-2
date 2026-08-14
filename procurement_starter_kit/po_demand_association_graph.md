---
okf_version: "0.1"
type: "Reference"
title: "PO ↔ Demand Association Graph — full-network resolution vs. routine per-line reads"
description: "Corrects an implicit assumption in earlier docs: PurchaseOrderDemandLink is a true many-to-many, in both directions, and can chain across POs and demands. Defines the bounded, fast per-entity read every page actually needs, and the separate, genuine graph-traversal resolution the admin visualizer needs — plus how packages extend the graph."
tags: [reference, demand-and-purchasing, packages, graph, tension]
context_tier: 2
personas: [backend, business]
---

# PO ↔ Demand Association Graph

## 1. The assumption this corrects

Nothing in the schema ever restricted `PurchaseOrderDemandLink` to "many demands, one line" — the
model doc has always said "one allocation per pairing," with no cardinality limit on either side
(`models/purchase_order_demand_link.md`). But every document that *talks about* the relationship —
[shared_demand_sessions.md](shared_demand_sessions.md) most of all — was written and read as if the
sharing only ever ran one direction: **one PO line, several demands.** The other direction was
always equally legal and is, in practice, equally common: **one demand, allocated across several PO
lines** — split across vendors, backorder re-sourced elsewhere, bought in two batches. And those two
directions compose: demand A's second line might be shared with demand B, whose other line sits on
a PO demand A has never touched. Nothing stops this from chaining.

**Nothing here is a schema change.** The many-to-many already exists exactly as built. This document
exists because the *read side* — every place that answers "what's going on with this demand" or
"what's going on with this PO" — needs to be honest about which of two very different questions it
is answering:

1. **"What does this one entity need to know about itself?"** — bounded, shallow, fast. Every
   routine page (demand detail, PO detail) needs only this.
2. **"What is the full set of demands and purchase orders entangled with this one, transitively?"**
   — a real graph traversal, unbounded in principle, needed by exactly one surface: the admin
   association-graph visualizer. Nothing else should ever need it.

Conflating these — building routine pages against a full graph walk "to be safe," or building the
diagnostic tool against a one-hop read "because it's usually small" — is the mistake this document
prevents.

---

## 2. Question 1: the shallow, bounded read (every routine page)

Nothing changes about **arrival**. [shared_demand_sessions.md §3](shared_demand_sessions.md) already
gets this right: a demand spanning several lines is evaluated **per line**, independently, and the
results are concatenated — `attributable_arrived_qty` plus a list of `sessions`, one per shared
line. That is already the correct shape for "a demand touches several lines," and needs no changes.

**Purchasing coverage needs the same treatment, and didn't get it.** The derivation in
[../front-end-kit/procurement/part_demand_workflows.md](../front-end-kit/procurement/part_demand_workflows.md)'s
Rules section only handled a demand's *single* line (1:1, or shared with other demands on that one
line) — it silently assumed a demand has at most one active `PurchaseOrderDemandLink`. That's the
same mistake `shared_demand_sessions.md` avoided for arrival, made fresh for purchasing. The fix is
identical in shape:

```
for each active PurchaseOrderDemandLink this demand holds:
    line = link.purchase_order_line
    line_covers_everyone = line.quantity_ordered >= Σ quantity_requested
                            (across every demand actively linked to `line`)
    this_link's contribution = line's PO status if line_covers_everyone, else "Partial"

demand's overall purchasing display = combine per-link contributions:
    - one active link            → that link's contribution, unqualified
    - two or more active links   → show each, same sentence shape as the arrival case:
      "PO 4021 (Purchased) covers one line; PO 4030 is Partial on the other" — never collapsed
      into a single misleading status
```

This is still a **one-hop-plus-one** read per demand: the demand's own links, and for each linked
line, that line's *other* direct links (to compute the shared-coverage sum) — never those other
demands' *other* lines. It terminates in a small, predictable number of queries regardless of how
tangled the wider graph gets, because it never follows an edge more than one line deep from the
seed demand. **Update `part_demand_workflows.md`'s purchasing axis card to this corrected formula** —
flagged here as a required follow-up, not done in this document.

---

## 3. Question 2: the full graph (admin visualizer only)

### 3.1 The actual question

Given a starting point — a demand, a PO, or a package — find **everything transitively entangled
with it**: every demand that shares any line with any PO reachable from the seed, and every PO
reachable that way, continued until no new node is discovered. This is a real graph problem, not a
bounded read, and it is only ever asked by a human explicitly investigating a tangle (support,
audit, "why does cancelling this PO refuse to let go of that demand"), never by a page rendered on
every request.

### 3.2 Node and edge types

The graph has (at least) two node types and grows a third once packages are included:

| Node type | Identity |
| :--- | :--- |
| `PartDemand` | one demand |
| `PurchaseOrderLine` | one line (carries its owning `PurchaseOrder` as an attribute, not a separate node — see §3.3) |
| `PackageLine` (rolled up to `Package` for display) | one package line — see §4 |

| Edge | Connects | Source |
| :--- | :--- | :--- |
| Demand ↔ Line | `PartDemand` — `PurchaseOrderLine` | Active `PurchaseOrderDemandLink` rows |
| Line ↔ Package | `PurchaseOrderLine` — `PackageLine` | `PackageLine.purchase_order_line` |

### 3.3 Traversal granularity — a deliberate choice, flagged for confirmation

The literal edges in the schema connect a demand to a specific **line**, not to a PO as a whole. Two
traversal granularities are both defensible, and this document picks one — confirm before building:

- **Line-strict**: a new demand only enters the graph if it shares an *actual line* with something
  already in the graph. Narrower, and can under-represent real entanglement — two demands can be on
  the same PO, on different lines that share nothing, and a Buyer cancelling that PO affects both,
  even though line-strict traversal would never connect them.
- **PO-inclusive (chosen)**: once *any* line of a PO is reachable, **every** demand on **every**
  line of that PO is pulled into the graph — the PO is treated as the unit of entanglement, because
  that's the unit a Buyer actually acts on (you place, cancel, or amend a whole PO, not one line in
  isolation). Rendering still happens at line granularity (§5 — the visualizer draws edges to
  specific lines, not a blob per PO), only the "is this node in scope" decision is PO-wide.

**Chosen: PO-inclusive**, because the tool exists to answer "what does touching this PO affect,"
and a line-strict answer would under-report that. Flagged as a judgment call, not a re-derivation of
an existing decision — confirm before the resolver is built.

### 3.4 Why this should resolve fast, and why it still needs a real bound

**Expected to terminate in a handful of hops in practice.** Two existing rules already suppress
runaway fan-out:
- **D58** (one active line per part per PO) keeps a single PO from offering many parallel paths for
  the same part.
- **D28** (allocation capped at outstanding request) means a demand's total allocation across all
  its lines is bounded by what it actually needs — a demand can't sprawl across an unbounded number
  of lines just because nothing stops it arithmetically.

Real purchasing data is sparse: most demands touch one line, most lines carry one to three demands,
and multi-line demands exist specifically to solve a shortfall (backorder, re-source), which is
uncommon relative to the everyday one-line case. Chains beyond one or two hops should be rare.

**"Should be rare" is not a bound.** The resolver must still be written as a real breadth-first
traversal with an explicit safety cap (a max node count and/or max hop count, whichever is hit
first), not a fixed-depth query assuming shallow data — a data-entry mistake or an unusual bulk-
consolidation order could produce a real chain, and the tool must degrade gracefully (truncate with
a visible "graph continues beyond N nodes, showing the first N" notice) rather than time out or
silently under-report.

### 3.5 Proposed control-layer class

`PoDemandAssociationGraphResolver` (naming a suggestion, not a built target) — the **only** class
that performs the full traversal. Every routine page keeps using the shallow read in §2; nothing
else should import this class. Input: a seed (`demand_id` **xor** `purchase_order_id` **xor**
`package_id`). Output: the node and edge sets described in §3.2/§4, safety-capped per §3.4.

---

## 4. Packages make this worse, not just bigger

A `PackageLine` points at exactly one `PurchaseOrderLine` — but per `mixed_po_assignments`
(`models/package.md`), a single `Package`'s lines can point at lines across **several different
POs** (a physical box legitimately containing items from more than one order). That means a
`Package` is itself a second, independent way for two otherwise-unrelated POs to become entangled —
two POs that share no demand and no Buyer decision can still show up connected in the graph purely
because one box happened to ship parts from both.

This is a **real** entanglement worth surfacing (a shipment-tracking fact, not a data error), and
the visualizer should show it — hence the third column (§5) — but it means the graph's growth isn't
bounded by demand-side rules (D28/D58) alone. A single mixed package can, in principle, bridge
between two otherwise-disconnected demand/PO clusters that D28/D58 would have kept apart. The
resolver's safety cap (§3.4) is what actually protects against this in practice, not the demand-side
rules, which don't reach into package-mediated connections at all.

---

## 5. What the visualizer renders (spec lives in the front-end kit)

Full page spec: [../front-end-kit/procurement/graph_association_visualizer.md](../front-end-kit/procurement/graph_association_visualizer.md).
Summary for this document's purposes: three columns — Demands, PO Lines, Packages — populated from
§3's resolved node/edge sets, connected by drawn lines rather than rendering the join rows
(`PurchaseOrderDemandLink`, the `PackageLine.purchase_order_line` FK) as their own visible rows. The
lines **are** the join rows, shown as a relationship, not a record.
