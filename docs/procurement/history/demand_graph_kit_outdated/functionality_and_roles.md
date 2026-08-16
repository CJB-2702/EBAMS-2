---
okf_version: "0.1"
type: "Kit Document"
title: "Functionality and Roles — Demand Graph Surfaces"
description: "Capability × persona matrix for the demand-graph surfaces, and the handoff contract to the front-end kit."
tags: [starter-kit, functionality, roles, procurement, graphs]
context_tier: 2
---

# Functionality and Roles — Demand Graph Surfaces

**This is the handoff contract to the front-end kit.** Every capability below is phrased as an action a
specific role performs on a specific thing.

> **Rewritten 2026-08-16** against D9, D25–D28. The previous version described a severity-ranked worklist
> built on a single precedence-ordered imbalance enum. Both are gone. If you are holding an older copy of
> this file, discard it — a front-end kit built from it designs the wrong screen.

---

## Personas

| Persona | How they describe the job | Volume |
| :--- | :--- | :--- |
| **Buyer / Purchasing** | *"I need to know what to chase today and what to order."* | **Highest, by a wide margin** |
| **Planner / Demand owner** | *"I raised a demand for this part; where is it?"* | Moderate, part-first |
| **Operations Administrator** | *"Which of my areas is falling behind?"* | Low, wants counts |
| **Auditor** | *"Show me this got handled."* | Rare, read-only, historical |

---

## The shape of the main surface (D27)

**The graph list is a plain filterable list, not a worklist.** Staff filter directly on the three state
columns. This is the single most important thing on this page and it governs every capability below.

There is **no** severity ranking, **no** "worst-first" default order, **no** queue picker, and **no**
landing page of counts. With three independent axes there is no defensible way to rank a PO-side problem
against a shipment-side one, and the kit declines to invent one.

**Consequence for suggestions.** Questionnaire G2 makes suggested actions core scope — *"it's only useful if
it has suggestions."* That obligation is met on the **detail page**, not per row. On a filtered list the
filter *is* the action: a user who filtered to `DEMAND_EXCEEDS_ALLOCATION` already knows what every row
needs. Three suggestion columns on one row would be unreadable.

### The three axes staff filter on

| Axis | Question it answers | Values |
| :--- | :--- | :--- |
| `po_imbalance_state` | Is the demand committed to purchase orders? | `DEMAND_EXCEEDS_ALLOCATION`, `ALLOCATION_EXCEEDS_PURCHASED`, `PO_QUANTITY_EXCEEDS_DEMAND`, `DEMAND_SATISFIED_EXCESS_ALLOCATED`, `BALANCED` |
| `shipment_imbalance_state` | Did we receive what we ordered? | `PO_ORDERED_NOT_ALLOCATED_TO_SHIPMENTS`, `SHIPMENT_ALLOCATION_EXCEEDS_PO`, `OVER_DELIVERED`, `PARTIAL_DELIVERY_RECEIVED`, `SHIPMENTS_ALLOCATED_AWAITING_DELIVERY`, `BALANCED` |
| `linear_status` | Where in the end-to-end pipeline? | `UNLINKED`, `PO_ALLOCATED_NOT_PURCHASED`, `PO_PURCHASED_NOT_SHIPPED`, `PARTIALLY_DELIVERED`, `DELIVERED` |

A graph's **condition** (D28) is the collective reading — any axis away from its resting value. It is a
phrase for UI copy and for the Ops Admin rollup, **not a stored column**.

> **Sizing note the front-end kit must plan for.** `PO_QUANTITY_EXCEEDS_DEMAND` will be the largest
> non-balanced population in the system by a wide margin — every bulk restock produces one and nothing
> clears it (D25). Do not design a screen that assumes non-balanced means small.

---

## Capability matrix

**Read capability is granted to every authenticated user** (D22). The matrix is therefore about *whose job
it is*, not about who is permitted — with one genuine exception, the resolution controls.

| Capability | Buyer | Planner | Ops Admin | Auditor |
| :--- | :---: | :---: | :---: | :---: |
| Filter the graph list on any of the three state columns | **R** (primary) | R | R | R |
| Filter out graphs already marked resolved | **R** (primary) | R | R | R |
| Find all graphs for a part | R | **R** (primary) | R | R |
| View one graph's nodes, quantities, and swimlane diagram | R | R | R | R |
| Read a graph's three states and its error code in plain language | **R** (primary) | R | R | R |
| See the suggested next action *(detail page only)* | **R** (primary) | R | R | — |
| View a part's activity across all its graphs | R | **R** (primary) | R | R |
| See condition-≠-balanced counts grouped by domain | R | — | **R** (primary) | R |
| Read the three node activity feeds on a graph | R | R | R | **R** (primary) |
| **Mark a graph resolved** | **C/U** | C/U | C/U | — |
| **Flag a graph for attention** | **C/U** | C/U | C/U | — |
| **Set a graph's priority** | **C/U** | C/U | C/U | — |
| Act on a suggestion (allocate, place PO, receive) | *governed by existing per-entity permissions, unchanged* | | | |

### Row-level scoping applies on top of all of this

| Surface | Rule |
| :--- | :--- |
| Search / list | Only graphs whose `primary_domain` is in the user's domain set |
| Detail view | Admitted if the user holds **at least one** member's domain; out-of-domain nodes shown as plain text, no link through |

See D4/D5/D6 for the derivation and the two accepted compromises.

---

## Capability detail

### 1. Filter the graph list *(Buyer, primary)*

The main surface. Every row carries: the part, the three state values, the relevant quantities, and the
resolution/flag/priority columns. Filterable on all of them; sortable within a filtered view by part or by
quantity gap.

**What a row does not carry:** a severity rank, a single summary state, or a suggested action.

### 2. Find all graphs for a part *(Planner, primary)*

Part-first, not a filtered list (D19). The surface owns aggregate figures **across** that part's graphs, and
presents them as a collection of small individual graphs.

### 3. Read a graph's states in plain language

Each of the three axes renders as a sentence, not an enum name, produced at read time by a Narrator. Plus
`error_code` (D12) where present, rendered as human language rather than as a key.

### 4. See the suggested next action *(detail page)*

One instruction per non-balanced axis, produced at read time by a Narrator, never stored (the states are
schema and change rarely; the wording is judgment and will be tuned for months).

**Tone constraint, from questionnaire G4 and D12.** Never accusatory. An over-delivery is usually the system
*learning a vendor fact late*, not a mistake anyone made. *"12 more units arrived than were ordered"* — not
*"excess receipt discrepancy."*

### 5. Read the three node activity feeds

Three **separate labelled sections** (D16), not one merged stream: purchase order comments, shipment
comments, and demand state-transition history. They are genuinely different kinds of record, and merging
would present a state change and a human comment as peers.

### 6. Mark a graph resolved, flag it, set its priority

The kit's **only** write path (D13). Three columns on an existing row, written only by
`GraphResolutionManager`.

- `resolution_state` — `OPEN` / `RESOLVED`. **Two values only** (D26); `ACCEPTED_AS_IS` was removed.
- `manually_flagged` — somebody wants eyes on this.
- `priority` — reuses `DemandPriority` (`low` / `medium` / `high` / `critical`).

**Behaviour a user will notice and must be told about:** a resolution **clears** when the graph merges or
splits (D14), because the thing that was looked at no longer exists. D15 requires that clearing to be
written to the surviving nodes' activity trail, so it reads as an explanation rather than as lost input.

**A permanently-imbalanced graph will keep coming back.** With `ACCEPTED_AS_IS` gone there is no way to
silence one for good, and D14 clears `RESOLVED` on every restructure. Accepted (D26) — the list is a
reference surface, not an inbox that must reach zero. **The UI must not imply otherwise**: no "0 remaining"
celebration, no badge counts that read as unread mail.

---

## What no role can do

Stated because their absence is a design choice, not an omission:

| Not available | Why |
| :--- | :--- |
| Create a graph | A graph is not a thing anyone makes. It forms as a side effect of demand/PO/shipment writes (D82). **There is no create page.** |
| Delete a graph | Graphs die when they lose their last node, or when absorbed by a merge (D18). |
| Edit a graph's quantities, part, domain, or states | Every one is derived and written exclusively by `GraphSummaryManager.recalculate()`. |
| Comment on a graph | No activity thread of its own (M5/M6). Human narrative belongs on the nodes, which are stable and user-created; a graph merges and dies without warning. |
| Attach a document or photo to a graph | Same reasoning. |
| See a numeric drift or severity score | No scored metric at any granularity (D8, D27, and D81 in the procurement kit). Condition is named states and plain quantities. |
| Rank graphs worst-first | No cross-axis precedence exists (D27). Deliberate. |
| Mark a graph permanently accepted | `ACCEPTED_AS_IS` removed (D26). |
| Sort or filter by how long a graph has been stuck | No trustworthy timestamp exists; declined with the consequence accepted (D11). `LinearStatus` catches "stuck" structurally instead. |

---

## Handoff notes for the front-end kit

1. **Three reverse FKs into `GraphSummary`, and none of them implies a wizard.** The usual heuristic —
   more than one reverse FK a user would populate in one sitting → wizard — reads three and would be wrong.
   All three are written by `GraphSummaryManager`; a user never populates them. See `model_diagram.md`.
2. **Every surface here is a read surface**, except one small control that sets three columns on an existing
   row. There is no create flow anywhere in this kit.
3. **The list is the primary screen, and it is a *filtering* screen.** Its quality is entirely a function of
   how good the filter controls are. If only one thing gets designed well, it is the filter bar.
4. **Suggestions live on the detail page, never on a list row** (D27). A row carrying three suggestions is
   the failure mode to design against.
5. **The existing swimlane detail page is re-homed, not redesigned** (D20). Its route name is unchanged;
   only the URL path moves.
6. **Do not design this as an inbox.** See capability 6 — large permanent populations are expected and
   correct.
