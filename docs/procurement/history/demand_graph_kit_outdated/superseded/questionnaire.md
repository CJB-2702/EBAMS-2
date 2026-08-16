---
okf_version: "0.1"
type: "Kit Document"
title: "Demand Graph Surfaces — Starter Kit Questionnaire"
description: "The 20-question pre-kit questionnaire for the demand-graph search/detail/part-utility surfaces, answered and with the Stage 2 interrogation folded in."
tags: [starter-kit, questionnaire, procurement, graphs]
context_tier: 2
---

# Starter Kit Questionnaire — Demand Graph Surfaces

**Status:** `COMPLETE` — answered 2026-08-15, interrogation folded in the same day.

This is the permanent record of what was known, assumed, and unknown at the outset. Answers below are the
developer's, with Stage 2 interrogation results folded in under the questions they refine. Where the
interrogation **reversed** an earlier answer, the reversal is marked inline — this document does not
pretend the first answer was never given.

Confirmed answers carry forward into `decisions.md`. Remaining unknowns carry forward into
`open_questions.md` and the two study documents.

---

## A. Goals

### G1 — In one sentence, with no nouns from your schema: what does this let someone do that they cannot do today?

**Answer:** Find, in one place, every stalled or out-of-balance chunk of purchasing work for a given part —
and be told what to do about it — instead of opening clusters one at a time and doing the arithmetic by hand.

Today the only way in is from an entity already on screen (a demand, a PO line, a shipment line), each
linking to *its own* graph. There is no way to ask "show me what needs attention", and no way to ask "show
me everything happening for this part".

---

### G2 — What is this explicitly NOT? Name the adjacent system it will be mistaken for.

**Answer:** Four negations.

1. **Not a scored drift metric.** No weighted composite score, at any granularity — not per graph, and not
   per PO line. *(Interrogation: a per-PO-line score was briefly floated and then declined. A PO line has no
   demand of its own, so "imbalance" for a line would have to mean something different from what it means
   for a graph — two definitions of the same word is exactly the trap to avoid.)* Imbalance is expressed as
   plain quantities and a small set of named states. See R4 and the imbalance study document.
2. **Not a stock / inventory level view.** Intake remains out of scope project-wide (D47);
   `intake_qty_recorded` stays permanently `0`. **The shipment is the source of truth within procurement** —
   a shipment carries its own summary, and procurement answers "what is in flight" from it without reaching
   into inventory.
3. **Not a replacement for the existing single-graph visualizer.** That page exists and works. This kit
   re-homes its URL and adds surfaces around it; it does not redesign it.
4. **Not a demand forecasting or reorder-point tool.** It reports on demand someone already raised.

**Binding requirement attached to this question:** the developer's position is that the surface *"is only
useful if it has suggestions."* Suggested actions are therefore **core scope, not a nice-to-have** — a
release that lists imbalanced graphs without telling the user what to do about them does not satisfy G1.

---

### G3 — What is the single record everything else hangs off, and what is the *only* thing the rest of the app is allowed to know about it?

**Answer:** `GraphSummary` — one row per connected component of the Demand / PO-Line / Shipment-Line network.

The narrow contract, established by D79/D81 and **unchanged by this kit**: the rest of the app knows a
`GraphSummary` only by the `graph` FK on its own row. A demand, a PO line, and a shipment line each carry
`graph_id`; any page wanting cluster-wide numbers does `WHERE graph_id = X` and reads materialized columns.
Nobody traverses. Nobody recomputes. `GraphSummaryManager` is the only writer of any derived column.

**Amended by this kit:** the manager's exclusive-writer rule now covers *derived* columns only. M6 adds a
small set of human-editable columns, which are the sole exception and are never touched by
`recalculate()`. That boundary is load-bearing and is called out again in M6 and R3.

---

### G4 — Which of this data is authoritative for us, and which mirrors a system we do not control?

**Answer:** All of it is ours. Every number on `GraphSummary` derives from rows this system owns and is
recomputed by `GraphSummaryManager.recalculate()`. Nothing mirrors a vendor system.

**On received vs. accepted quantities.** The developer's position: intake records the quantities actually
recorded, and a mismatch between the shipment line's base quantity and what was received is **expected and
acceptable** — it reflects reality (the vendor shipped 12 against an order for 10). The base
`ShipmentLine.quantity` is **never adjusted** to paper over the difference.

*(Interrogation outcome: a distinct `quantity_received` column does not exist today — `ShipmentLine` has
`quantity` and `quantity_accepted`; `Shipment` has `received_date` but no received quantity. Resolved:
**this kit reads `quantity_accepted`** and treats it as the arrival figure. A separate received-vs-accepted
distinction is deferred and will be resolved later, outside this kit — carried in `open_questions.md`.)*

**Consequence for wording:** an "over" condition is frequently *a vendor fact learned late*, not a data
error. Suggested actions must not read as accusations of mistakes.

---

## B. Personas

### P1 — Name each persona and the one sentence they would use to describe their job here. Which is the highest-volume user?

**Answer:** Confirmed as drafted.

- **Buyer / Purchasing staff** — *"I need to know what to chase today and what to order."* **Highest volume
  by a wide margin.** The fast read path exists for this persona.
- **Planner / Demand owner** — *"I raised a demand for this part; where is it?"* Arrives part-first.
- **Operations Administrator** — *"Which of my areas is falling behind?"* Wants counts, not rows.
- **Auditor** — *"Show me this got handled."* Rare, historical, read-only.

---

### P2 — For each persona, what do they do 50 times a day versus once a month?

**Answer:** Confirmed as drafted.

| Persona | 50× a day | Once a month |
| :--- | :--- | :--- |
| Buyer | Open the unresolved worklist; filter by part; act on a graph and return | Review a part's long-run pattern |
| Planner | Look up one part's status | — |
| Ops Admin | — | Scan unresolved counts by domain |
| Auditor | — | Trace one historical graph's resolution |

**The read path that must stay fast:** *unresolved graphs, filtered by part and/or domain, ordered
worst-first.*

**Write paths:** the graph surfaces create nothing. Graphs are maintained as a side effect of
demand/PO/shipment writes that already exist. Actions the user *takes* leave through existing write paths
(allocate, place PO, receive). The one exception is M6's human-editable resolution columns.

---

### P3 — Fill in the capability × role matrix.

**Answer:** **Read is granted to all users** — deliberately simple for now. Gating happens where it already
exists: a user who wants to *solve* a problem needs the existing edit permissions on the PO, the demand, or
the shipment. The graph surfaces do not introduce a second permission vocabulary for the same acts.

| Capability | All authenticated users |
| :--- | :---: |
| Search/list graphs | R |
| Filter to unresolved | R |
| Filter/search by part | R |
| View one graph + swimlane diagram | R |
| See over/under direction | R |
| See suggested next action | R |
| View a part's activity across its graphs | R |
| See unresolved counts by domain | R |
| Set resolution / flag / priority on a graph | C/U — *see M6* |
| Act on the suggestion (allocate, order, receive) | Governed by existing per-entity permissions, unchanged |

**Row-level scoping still applies on top of this** — "read for all users" is about *capability*, not about
which rows are visible. See P4.

---

### P4 — Is any of this data restricted to a subset of users? Default or exception, and roughly what percentage?

**Answer:** This reverses the prior situation by design. When the graph was a computed artifact with no row
of its own, it could not carry a domain. **Now that it is materialized as a real table, it gets a
`primary_domain` column**, and that column is the scoping guard.

**Two different rules, deliberately:**

| Surface | Rule |
| :--- | :--- |
| **Search / list** | Filter on `GraphSummary.primary_domain` — a single indexed column, which is what keeps the hot read path fast. |
| **Individual graph view** | The view already loads every member. Compute the set of domains present across members; the user must hold **at least one** of them. |

**Accepted leakage, explicitly.** On the detail view, once a user is admitted by holding *any* one member's
domain, out-of-domain members are **displayed** (as plain text, no link through — the existing rule). This
is knowingly more permissive than strict row-level scoping. **Mark it as an anti-pattern in the code.** The
developer accepts this leakage as the cost of a graph being legible at all: a graph you can only half-see
is not useful, and the members are already reachable through the entities that link to them.

**`primary_domain` derivation:** **most common domain by purchase-order-line count.** *(Interrogation
outcome — this reverses an earlier instinct to derive it from demands. Rationale: PO lines are the centre of
the purchasing process, so the domain doing the buying is the one that should own the graph in a list.)*

Open sub-cases carried to `open_questions.md` and the graph-formation study: what happens when a graph has
**no PO lines at all** (very common — every newly created demand is a single-member graph), and how ties
are broken. `recalculate()` runs constantly, so the rule must be deterministic or graphs will flap in and
out of people's search results.

**Known gap, accepted:** a graph whose `primary_domain` is not yours, but which contains your member, is
reachable by clicking through from your own entity yet **will not appear in your search**. Accepted on the
reasoning that *whoever linked the two items should hold both domains anyway*, so the person who cares can
find it. Logged as tech debt alongside R1's domain cardinality note.

---

## C. Business relationships

### R1 — For every link: one-to-many or many-to-many? What breaks the day it becomes many-to-many?

**Answer:**

**Existing, unchanged:**

| Link | Cardinality |
| :--- | :--- |
| `GraphSummary` → `PartDemand` | 1→many |
| `GraphSummary` → `PurchaseOrderLine` | 1→many |
| `GraphSummary` → `ShipmentLine` | 1→many |
| `PartDemand` ↔ `PurchaseOrderLine` | many↔many via `PurchaseOrderDemandLink` |
| `ShipmentLine` → `PurchaseOrderLine` | many→1 |

**New: `GraphSummary` → `Part`.** **One part per graph, enforced.** A graph may never contain members for
more than one part. *(Note on wording: the developer said "one to one"; the actual cardinality is
**many graphs to one part** — a part accumulates many graphs over time, which is exactly what M2 asks for.
The enforced constraint is "a graph has exactly one part", not "a part has exactly one graph".)*

**New: `GraphSummary` → `Domain` (`primary_domain`).** Modelled as many-graphs-to-one-domain. **The
developer acknowledges this is a simplification** — a graph's membership can genuinely span multiple
domains, so a single `primary_domain` is a lossy summary. Accepted for now under P4's two-rule policy.
**Logged as tech debt** for a future pass.

---

### R2 — When a record is created, what else must come into existence automatically? If it fails, does the original creation fail too?

**Answer:** Confirmed — **this kit creates nothing.**

The graph lifecycle is already fully wired (D82): node-init on isolated creation, coalescing merge on link
creation, bounded BFS split on unlink, and `recalculate()` as the mandatory last step of all three, inside
the transaction of the write that caused it, with no `commit` parameter (D66).

New derived columns (`part`, `primary_domain`, the demand-less flag, the imbalance state) are written by
`recalculate()` in that same transaction, exactly as `status` and `swimlane_diagram` already are. If that
write fails, the originating write fails with it. This is existing behavior and is correct.

---

### R3 — When a record is deleted or deactivated, what happens to everything pointing at it? Soft or hard?

**Answer:**

- **A graph that loses all of its nodes is deleted.** Already implied by the merge path; now stated
  explicitly so it is a rule rather than an emergent behavior.
- **A merged graph dies.** The absorbed row is hard-deleted; there is no tombstone and no redirect. A
  bookmarked URL to an absorbed graph 404s, and that is accepted *(confirmed under M5)*.
- **Member rows** remain soft-deleted (`deleted_at`), and every graph query filters
  `deleted_at__isnull=True`.
- **A demand-less graph needs a flag.** Nodes normally originate from a demand. A graph consisting only of
  PO lines and shipment lines is a distinct condition that must be visible.

**Deliberately deferred to a study document:** what *should* happen when POs are raised early, or shipments
arrive with nothing on file — the developer has explicitly not thought these through and does not want them
resolved by improvisation. See `graph_formation_policies_study.md`.

**Reopened by M6.** Because graphs now carry human-editable columns, R3 acquires a question it did not have
when the kit was read-only: **when a graph merges or splits, what happens to a human-set resolution, flag,
or priority?** A merge/split is invisible to the user — it fires as a side effect of an allocation — so
these values can silently vanish or silently duplicate. Resolved in the study document with a recommended
position, not left to the implementer.

---

### R4 — When several constraints apply at once, must all pass or any pass? Write the truth table.

**Answer:** **Deferred to a dedicated study document, by explicit request.** This is the definition of
"unresolved", it is the load-bearing decision of the whole kit, and the developer wants it thought through
properly rather than answered in a questionnaire cell.

The raw material and the specific sub-questions — what "under" means, what "over" means, whether age
matters, and whether the combination is AND or OR — are carried into
`imbalance_and_resolution_study.md`, which takes a **strong recommended position** on each rather than
presenting open options *(developer's instruction at interrogation)*.

The one thing settled here: the existing four-value `GraphSummaryStatus`
(`BALANCED` / `AWAITING_PURCHASE` / `AWAITING_SHIPMENT` / `AWAITING_ACCEPTANCE`) does **not** answer this.
`BALANCED` is not the opposite of "unresolved" — a brand-new demand with nothing ordered is
`AWAITING_PURCHASE`, which is normal, not a problem. "Unresolved" is a second axis.

---

### R5 — At what moment is each rule enforced? What happens when the check cannot be decided?

**Answer:** Settled by P4 and R2 rather than answered separately.

Everything the hot read path filters or sorts on is **computed at `recalculate()` time and stored** —
`part`, `primary_domain`, the demand-less flag, and whatever the imbalance study lands on. This follows
D79's materialization philosophy and is what makes list filtering a plain indexed `WHERE`.

The cost is accepted knowingly: changing the definition of "unresolved" later means a migration plus a
full-table recalculate. Given this project's development-time migration strategy (full reset), that cost is
low today and rises only after production data exists.

**Suggested-action text** is *not* stored. It is derived at read time by a Narrator from the stored state,
so wording can be tuned without a migration.

**The undecidable case** — a single-member graph with no links and all-zero quantities, which every new
demand creates and which will dominate the table by count — is a named case in the imbalance study, not an
afterthought.

---

### R6 — Which app owns this? Which apps must remain ignorant, and what are the permitted seams?

**Answer:** Confirmed. `app/procurement/` owns it unambiguously.

`app/parts/` must remain completely ignorant of graphs. `GraphSummary.part` is procurement pointing *at*
parts — the existing allowed direction, matching `PartDemand.part`. Parts never points back.

**No mirrored graph surface in `app/inventory/`.** D84's shipment mirror is precedent for a second app
rendering procurement's rows, and someone will eventually propose the same for graphs. The answer is no:
the graph is a purchasing concept and receiving staff have no use for it.

---

## D. Data model

### M1 — Glossary: list every domain noun. Mark collisions.

**Answer:**

| Noun | Means here | Collides with |
| :--- | :--- | :--- |
| **Graph** | One connected component of the demand→PO→shipment network; a `GraphSummary` row | ⚠️ **Charts.** Mitigation: the UI must make it read as a **network of nodes**, not a chart — node/edge language throughout, and the swimlane diagram carries that visually. |
| **Node** | A member of a graph: a demand, a PO line, or a shipment line | Adopted as the primary user-facing word for a member. |
| **Cluster** | Informal synonym for graph used during planning | Not code vocabulary. Avoid in the UI; use "graph". |
| **Unresolved** | *(defined in the imbalance study)* a graph needing human action | "Resolved" is not currently a status anywhere in procurement — the word is free. |
| **Over / Under** | Direction of quantity imbalance on a graph | ⚠️ **"Over-allocation" already exists** with a specific meaning: `AllocationCapExceeded`, an allocation exceeding a demand's outstanding requested quantity (D28). "Over" must not mean two things — the imbalance study names its states distinctly. |
| **Member** | Synonym for node; retained in code where it already exists | Clean |
| **Swimlane** | The three-lane mermaid diagram of a graph's nodes | Clean; already `MermaidSwimlaneBuilder` |
| **Balanced** | Existing `GraphSummaryStatus` value: nothing outstanding | Not the opposite of "unresolved" — see R4 |
| **Shipment** | The pre-possession delivery record | The word "package" is **dead vocabulary** — D83 renamed `Package`/`PackageLine` → `Shipment`/`ShipmentLine` throughout. Do not reintroduce it. |
| **Domain** | The Data Domain access primitive | ⚠️ Do **not** use "domain" loosely to mean "entity type" or "area of the system". In this project the word has exactly one meaning and it is an access-control one. |

**Settled naming:** URL segment is `graphs/`. The kit uses "graph" and "node" throughout.

**House conventions:** singular `db_table`; `Struct` / `Context` / `Manager` / `Policy` / `Narrator` suffix
vocabulary; guard files end `_guard.py`; audit columns on every table.

---

### M2 — Where two concepts overlap, which is concrete/primary and which is the restricted view?

**Answer:** **The part is the subject; graphs are episodes in its history.** The part-scoped surface is a
part-centric page showing **a collection of small individual graphs**, not a graph list with a filter
applied.

This is the more useful and more expensive reading, and it is chosen deliberately. It means the part
surface owns its own aggregate figures across graphs, not just a filtered row set.

---

### M3 — Is this variation a type label, capability flags, or a distinct class? Can a caller construct an invalid combination?

**Answer:** **Resolved by the imbalance study**, which takes a position rather than leaving it open. The
question is whether "the way a graph is out of balance" is one enum or several booleans.

Two constraints the study must respect:

1. **Do not fuse it into `GraphSummaryStatus`.** That column answers "where is this in the workflow";
   imbalance answers "is this a problem". D71/D76 already established for `PurchaseOrder` that those are
   separate axes deserving separate columns. Same reasoning applies.
2. **R3's demand-less flag is the first concrete instance of this question.** Whether it is a standalone
   boolean or a value in the imbalance enum is decided in the study, and that decision sets the pattern.

---

### M4 — Is this attribute intrinsic to what the thing *is*, or to *where it is used*?

**Answer:** **Intrinsic. `GraphSummary` gets a `part` FK.**

**The finding that prompted the question:** verified against `app/procurement/models/graph/graph_summary.py`
— there was **no** `part` column. The model carried the eight D81 quantity columns, `status`,
`swimlane_diagram`, and audit fields. `part_id` lived only on member rows. Graphs could not be queried by
part without joining out to three member tables — the exact fan-out D79 exists to eliminate.

**The developer's ruling:** *"yes i want a part id on a graph. I will not allow different po lines to have
different part ids."*

This is stronger than the recommendation that was offered. A nullable "or NULL if members disagree" column
was proposed as a hedge against the part-match guard being relaxed later. **The developer rejected the
hedge and closed the door instead** — cross-part graphs are not a future to design around, they are
disallowed. The column is therefore **non-nullable**, which is safe: all three member types
(`PartDemand`, `PurchaseOrderLine`, `ShipmentLine`) already carry a `part` FK, so every graph has a part
from the moment its first node exists.

**Consequence to honor:** `PurchaseOrderDemandLinkValidator` currently enforces part-matching as a *soft*
validator rule, deliberately kept out of the database so it could be relaxed later. That relaxation is now
foreclosed. Whether the rule should be hardened to a database constraint to match its new load-bearing
status is a question for the control-layer plan.

**This is a schema change** and triggers a full `refresh_project.py` reset per the project's migration
strategy.

---

### M5 — How do users version and identify this? What does "current" mean, and is it the same as "newest"?

**Answer:**

1. **Identity:** the integer PK is fine. *(Developer note: "arguably these should just be computed rows" —
   an acknowledgement that the graph's identity is inherently unstable, since merges destroy ids. No
   human-readable label is required.)*
2. **"Recent" / last activity:** **no last-activity columns.** Three additional timestamp columns were
   considered and **rejected** — keeping them current would mean every demand, PO, and shipment write
   reaching over to touch the graph, which is a large ongoing tax on every entity for a display nicety.

   **Instead:** the graph detail page gains an **activity section** below the three-column node split,
   showing time-ordered updates labelled by which node they came from (this PO, this demand, this shipment).

   *(Interrogation finding — the infrastructure is asymmetric. `PurchaseOrder` and `Shipment` each have an
   `event` OneToOne and their Narrators write comments to `activity_thread_id=<x>.event_id`, so comment
   threads exist for both. `PartDemand` has **no** event FK — `PartDemandNarrator` produces text for
   `PartDemandUpdate` rows, an append-only state-transition journal, not a comment thread.)*

   **Resolution: keep the three feeds separate.** Do not merge them into one interleaved stream and do not
   build a comment thread for `PartDemand` just to make them uniform. Three labelled sections, each showing
   what that entity type actually has.
3. **Merged graphs die and are deleted.** No tombstone, no redirect. A stale bookmark 404s.

---

### M6 — Which entities carry free-form human content?

**Answer:** *(This answer was **reversed during interrogation** — the reversal is the substance of it.)*

**Initial position:** nothing on a graph is human-editable. Clean, and it dodged R3's merge/split problem
entirely.

**The consequence that reversed it:** with no way to mark a graph done, the worklist can never be worked
down. A vendor overships 12 against a demand for 10, everything is accepted, the business is finished — but
that graph is permanently "over" and sits on the Buyer's list forever, along with every other
legitimately-closed-but-imbalanced graph. Within months the list is mostly noise, which is the failure mode
that kills worklists.

**Final position: a small set of human-editable columns on `GraphSummary`, for resolution, flagging, and
priority.** No free-form comments, no documents, no attachments — the graph does not get an activity
thread of its own (M5 already routes human narrative to the nodes, which are stable and user-created).

**The rules this creates:**

- These columns are the **only** exception to "`GraphSummaryManager` writes every column".
  `recalculate()` must never touch them.
- **Merge/split survival is now an open problem** — see R3 — and is resolved with a recommended position in
  the graph-formation study rather than improvised at implementation time.
- The kit is **no longer read-only**. It has one small write path, which needs a Manager, a Policy, and a
  place in the permission model.

---

## E. Migration defaults

### X1 — What is today's behavior, and does the new default reproduce it? Clean cut or shims?

**Answer:**

**Today:** the single-graph visualizer lives at `procurement/graph/<int:graph_id>/`, route name
`procurement_graph_visualizer`, wired directly in `app/procurement/urls.py`. It is reached from a member's
own `graph_id`. There is no list page and no part-scoped page.

**Change:** `graph/<id>/` → `graphs/<id>/`, moving into a new `urls_graphs.py` alongside the other wave
modules, matching the file-per-wave convention already in `urls.py`.

**Clean cut — no redirect from the old path.** Justification matches extensions E2: the route is referenced
only from templates inside this project and always via `{% url %}` reverse by route **name**, so changing
the path breaks nothing as long as the name is stable. There are no external consumers, and dev does full
rebuilds. **Keep the route name `procurement_graph_visualizer` unchanged** — the name is the real
compatibility surface, and renaming it for cosmetic plural consistency would touch every template that
references it for no functional gain.

---

## Sign-off

- [x] Every question answered or explicitly deferred to a named study document.
- [x] Pre-filled inference markers reviewed and removed.
- [x] **Status set to `COMPLETE`.**

**Deferred by design, each to a named document:**

| Deferred item | Goes to |
| :--- | :--- |
| R3 — early POs, unattached shipments, demand-less graphs; merge/split survival of human-set columns | `graph_formation_policies_study.md` |
| R4 / M3 — the definition of "unresolved", over/under semantics, whether age matters, enum vs. flags | `imbalance_and_resolution_study.md` |
| P4 — `primary_domain` when a graph has no PO lines; tie-breaking | `graph_formation_policies_study.md` |
| G4 — received vs. accepted as distinct quantities | `open_questions.md` (out of kit scope) |
| R1 — `primary_domain` as a lossy single-FK summary of multi-domain membership | tech debt |
| P4 — graphs findable by click-through but absent from search | tech debt |
