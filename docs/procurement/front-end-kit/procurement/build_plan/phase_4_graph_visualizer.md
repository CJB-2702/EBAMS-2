---
okf_version: "0.1"
type: "Process Guide"
title: "Phase 4 — Graph Association Visualizer"
description: "Build brief for the deferred diagnostic page rendering the full transitive PO/demand/package network as three linked columns, including the deliberate domain-scoping exception it requires."
tags: [front-end-kit, procurement, build-plan, phase-4, graph, diagnostic]
context_tier: 2
personas: [frontend, backend]
---

# Phase 4 — Graph Association Visualizer

**Prerequisites: Phases 0, 1, 2, and 3.** Build last. Its route name is declared in Phase 0; the
inbound links from demand, PO, and package pages are built by their own waves.

**This is deliberately a "build once it is needed" page.** It exists to make an invisible tangle
visible when someone is already confused — not to be part of anyone's daily flow. Do not sequence it
ahead of the pages it links out from.

## Goal

Answer one question the shallow reads on every other page cannot: *what does touching this actually
affect?* Seeded from one demand, PO, or package, render the whole connected network.

## Definition of done

- One route, seeded by exactly one of three query parameters.
- Three columns render as real server-side markup with no JavaScript; connectors layer on top.
- Truncation is stated plainly whenever the safety cap is hit.
- The page writes nothing, anywhere.

---

## 1. Context to load

| Document | Why |
| :--- | :--- |
| [../graph_association_visualizer.md](../graph_association_visualizer.md) | **Primary spec.** Layout, column contents, connector rendering, seed parameters, truncation. Marked WIP — expect to make judgment calls and record them |
| [../../../procurement_starter_kit/po_demand_association_graph.md](../../../procurement_starter_kit/po_demand_association_graph.md) | **Read first.** Defines the graph, traversal granularity, the safety cap, and why this is a separate surface from every routine card. §3.2 node types, §3.3 PO-inclusive traversal, §3.4 the cap, §3.5 the resolver |
| [../../../procurement_starter_kit/decisions.md](../../../procurement_starter_kit/decisions.md) | **D70** — many-to-many in both directions, no schema change, one new resolver class |
| [phase_0_schema_and_shell.md](phase_0_schema_and_shell.md) | §6 the declared route name |

### Code to read

| Path | Why |
| :--- | :--- |
| [../../../app/procurement/models/purchasing/purchase_order_demand_link.py](../../../app/procurement/models/purchasing/purchase_order_demand_link.py) | One of the two edge types |
| [../../../app/procurement/models/packages/package_line.py](../../../app/procurement/models/packages/package_line.py) | `purchase_order_line` — the other edge type |
| [../../../app/procurement/control_layer/domain_structs/](../../../app/procurement/control_layer/domain_structs/) | Struct conventions the resolver's output should follow |
| [../../../harness/Architecture/patterns/oop_control_patterns.md](../../../harness/Architecture/patterns/oop_control_patterns.md) | Suffix vocabulary — this is a `Resolver`-shaped read, place it correctly |

---

## 2. The one deliberate rule break

Every other page in this build enforces: **a record outside your domain is exposed data, never
navigable.** This page breaks that on purpose, because its entire job is showing what crosses
domain boundaries — scoping it the same way would defeat its point.

**Mark it explicitly.** Per project convention, the domain-scoping bypass carries a
`# DELIBERATE ANTI-PATTERN` comment naming what is being bypassed and why, so a future reader finds
a decision rather than an oversight.

**Access:** not admin-gated. Anyone can reach it by following the link from a demand page. This
reverses the sector document's original admin-only framing — that document is WIP and this build
plan is newer.

**Compensating control: the page never writes anything.** No inline actions, no edit affordances, no
form posts. Every row is a read-only reference that click-throughs to its real page — where normal
domain rules apply again and an out-of-domain record will refuse. Strict read-only is what makes the
bypass safe; do not add a single write action here later without revisiting this.

---

## 3. The page

**Page type:** full-width diagnostic canvas. No hero, no side rail, nothing competing for space.

| Region | Placement | Contents |
| :--- | :--- | :--- |
| Seed picker | Full width, top | How you got here — §4 |
| Three columns | Full width | **Demands** (left) · **PO Lines**, grouped by PO (center) · **Packages** (right) |
| Connector overlay | Across all three | Lines from each demand to every PO line it links to, and from each PO line to every package line pointing at it |

**Do not render join rows as their own rows or a fourth column.** A `PurchaseOrderDemandLink` or a
`PackageLine.purchase_order_line` FK **is** the connecting line. If you find yourself wanting a table
row for a link, that is the join table leaking into the display — the line already says everything
the row would.

### Column contents

- **Demands** — id, part, `quantity_requested`, priority, four-axis badges (reuse Phase 1's badge
  set). Click-through to demand detail.
- **PO Lines, grouped by PO** — POs as sub-headers (number, vendor, status badge), lines beneath
  (line number, part, `quantity_ordered`). **A PO's unrelated lines still render, muted** — the
  column reads as "this whole PO," matching the PO-inclusive traversal choice. The reasoning that
  motivated PO-inclusive traversal (you act on a whole PO, not one line) applies equally to what gets
  shown.
- **Packages** — one row per `Package`, its lines collapsed into the row with a per-line breakdown on
  expand. Package number, status badge, `mixed_po_assignments` indicator.

### Connector rendering

**Plain layered SVG. Not a graph library.** Each column renders as an ordinary server-side
list/table first — real markup, works with no JavaScript, F5 rule — then an SVG overlay positions
`<line>` elements between connected rows using `getBoundingClientRect()` on load and on
resize/scroll. This is a bipartite line diagram, not a force-directed layout, and does not need
anything heavier.

**Hover or focus on a row highlights only its own connectors and dims the rest.** With a graph that
can legitimately have many crossing lines, "trace one node's edges" has to be easy or the page is
unreadable.

---

## 4. Seed parameters

The page's entire state is a query parameter, so it is linkable from anywhere and reproducible on
reload.

| Param | Effect |
| :--- | :--- |
| `?demand_id=<id>` | Seed from this demand |
| `?po_id=<id>` | Seed from this PO |
| `?package_id=<id>` | Seed from this package |

**Exactly one is required.** Reject none-or-more-than-one with a clear message, never a blank page.
There is no filter or results-list apparatus beyond the seed picker — this is a
single-graph-at-a-time viewer, not a search page.

**Inbound links** (built by their own waves, verified here):

| From | Seeded with |
| :--- | :--- |
| Demand detail's purchasing axis card | `?demand_id=` |
| PO detail's quick facts; PO Edit & Linkage | `?po_id=` |
| Package detail's quick facts | `?package_id=` |

Each should read as "zoom out from what I am looking at to the whole tangle," not as a separate
destination someone has to already know about.

---

## 5. The resolver

`PoDemandAssociationGraphResolver` (proposed, new) — breadth-first over
`PartDemand` / `PurchaseOrderLine` / `Package` nodes with an **explicit safety cap**. Bounded on
purpose, not assumed shallow.

**Nothing else in the application may ever call this class.** Every routine page uses the shallow
one-hop-plus-one read instead. If a sector page starts wanting graph data, that is a signal the
sector page is wrong, not that the resolver should be shared.

**Packages are the reason the cap is the real bound.** `mixed_po_assignments` lets one package bridge
lines across different POs with no demand in common, so the demand-side rules (D28's cap, D58's
one-line-per-part) do not constrain growth — only the resolver's own cap does.

### Truncation must be visible

When the cap is hit, a banner above the three columns: *"Showing the first N connected records. This
network continues beyond what is displayed."*

**Never silently render a partial graph as if it were complete.** A diagnostic tool that quietly
under-reports the very thing it exists to reveal is worse than one that admits its limit.

---

## 6. Key things to note

- **Empty and trivial graphs still render normally.** A demand with one line and no sharing produces
  one demand, one PO line, and whatever packages point at that line — render it exactly like a large
  tangle, no special case. This is also the best way to sanity-check the renderer before trusting it
  on something complex.
- **The sector document is WIP.** Where it is thin, decide, build, and record the decision — either
  in the sector document or as a starter-kit decision if the rule is durable.

## 7. Out of scope

- Any write action, of any kind, ever.
- Filtering, searching, or comparing multiple graphs.
- Export, print, or image download.
- Making the resolver available to any other page.
</content>
