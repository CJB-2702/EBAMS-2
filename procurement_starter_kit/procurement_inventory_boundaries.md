---
type: "Technical Decision"
title: "Procurement, Inventory & Build-Order — Design Review"
description: "Status: **resolved, building now**. Cross-cutting — spans parts (existing) plus procurement, inventory, maintenance, and dispatching (not yet built)."
tags: [technical-decisions, technical-decision, parts, procurement, inventory, maintenance, dispatching]
context_tier: 2
---

# Procurement, Inventory & Build-Order — Design Review

Status: **resolved; this design is being built now**. Original proposal captured from a planning
discussion reviewing the sibling Flask project's `part_demands` module
(`/home/cb/REPOS/asset_management/app/data/part_demands/`,
`app/business/part_demands/`, `app/presentation/routes/part_demands/`) and deciding how the
equivalent concept should be structured for this project. Updated 2026-08-08 to reflect the
finalized boundary: Procurement encompasses demand, purchasing, and package shipment tracking
(pre-possession); Inventory handles issuance and will later handle stocking (post-possession).

## Starting point: the old system's `part_demands` module

`PartDemand` (old system) is a **hub-and-link** design: a context-agnostic hub row with no FK to
Action, Dispatch, or anything origin-specific. Consumers each own a thin link table pointing *at*
the hub instead:

- `MaintenanceDemandLink` (action → demand, unique)
- `DispatchConsumable.part_demand_id` (nullable FK)
- `PartDemandPurchaseOrderLink` (demand ↔ PO line, many-to-many with `quantity_allocated`)
- `PartIssue.part_demand_id` (fulfillment, polymorphic recipient: user/asset/demand)

State is split into **three independent dimensions** on the hub — `approval_status`,
`issue_status`, `order_status` — rather than one combined enum. A `PartDemandFactory` creates
only the hub row; the caller creates its own link row. A `DemandOriginResolver` walks the reverse
direction (given a `part_demand_id`, resolves asset/event/assigned-user context by checking which
link type exists) so the hub never needs to know who's pointing at it.

### What doesn't fit this project's conventions

- No OOP control-layer vocabulary — everything is a static method on a `Factory`/`SearchService`,
  no Manager/Guard/StateMachine/Narrator split (see
  [../../../harness/Architecture/patterns/oop_control_patterns.md](../../../harness/Architecture/patterns/oop_control_patterns.md)).
- Status fields are bare strings enumerated only in a docstring/dict — nothing stops illegal
  combinations (e.g. `issue_status='Fully Issued'` while `approval_status='Rejected'`).
- No ownership-group scoping (this project's `is_domain_limited` / domain-access-mapping pattern
  has no equivalent here).
- No audit-thread integration — this project has an `events` app with `ActivityThread`; the old
  system had no equivalent and the demand hub has no comment/activity trail.
- Cross-app reaching: the `delete()` route and `DemandOriginResolver` import directly from
  `maintenance`/`dispatching` internals with `try/except ImportError` guarding optional apps —
  a Flask-flat-namespace habit that violates this project's layered dependency direction.
- Backward-compat shims (`.status`, `.action`, `.action_id` properties) are migration residue with
  no reason to carry into a fresh build.

### Real gap found in the old model, not just a style issue

`approval_status` got real audit columns (`maintenance_approval_by_id`/`_date`,
`supply_approval_by_id`/`_date`); `issue_status` and `order_status` got **none** — no record of
who marked something issued, when, or why an order status changed. This is the natural failure
mode of tracking state as bare columns: the first dimension gets audit columns, later dimensions
either repeat the pattern (more column pairs per dimension) or get silently skipped, which is
what happened here.

## Where should Part Demand live? (app-boundary question)

Three positions were considered, in the order discussed:

### 1. Folded into `parts` (rejected)

Reasoning against: `parts` is a **stewardship** function — establishing and maintaining the
engineering record of what a part is (number, name, revisions, sourcing). Touched rarely,
deliberately, by someone acting as an engineering authority. Part Demand is a **coordination**
function — someone needs material now, and that need moves through approval and fulfillment.
Touched constantly, by different people, for a different kind of value (throughput, not record
correctness). Bundling them mixes a rare/deliberate change surface with a high-frequency
transactional one in the same app, same migration domain, same blast radius.

The only real reason raised *for* the merge was that the demand segment looks thin on its own
right now — which is true only because inventory/maintenance/dispatching don't exist yet. Once
built, demand becomes the busiest, most cross-referenced object in the graph (three status
dimensions, links to POs, arrivals, issues) — the same shape it had in the old system. Merging
now because it looks small risks having to un-merge a live, referenced model later.

### 2. Folded into `inventory` (rejected)

Reasoning against: Demand sits on the boundary between two different business processes —
**origination** (why is this needed: a maintenance action, a dispatch, a general ask — Maintenance
/Dispatching's job) and **fulfillment** (how does it get supplied: sourced, ordered, received,
issued — Inventory's job). Demand itself answers neither; it's the record that a need exists and
is moving through both. Folding it into Inventory makes Inventory responsible for understanding
*why* things are needed, which isn't its job. Same category mismatch as option 1, different
partner. (Notably, the old system never merged them either — `part_demands` was its own module,
separate from `inventory`.)

### 3. Procurement (demand + purchasing + packages) and Inventory (issuance/stocking) as separate apps (current — adopted)

This reframes the split along **pre-possession vs. post-possession** lines instead of
**parts-vs-transactional**:

- **Procurement** — requisition, purchasing, and shipment tracking: "do we need this" (approval),
  "how/where do we buy it" (vendor, PO, order tracking), and "what did the vendor ship" (package
  tracking until acceptance). Paperwork/approval-driven, not day-to-day physical handling. Maps to
  a real organizational split many orgs already have: **Procurement** (requisite, purchasing, and
  receiving dock receiving). **Packages are pre-possession** — they are the vendor's shipment story
  and belong here, not in Inventory.
- **Inventory** — issuance and stocking: physical custody after possession. Part issuance (signed
  quantity to a person) is the write seam into the demand system. Later builds will add stock
  levels, locations, and movements. Maps to **Warehouse / Stores**.

Supporting evidence from the old system: `PartDemand.supply_approval_by_id` /
`supply_approval_date` already lived directly on the demand hub — i.e. the org already treats
"Supply approves this" and "the demand" as one continuous process, and Supply is also the team
that would go on to cut the PO. That's evidence Demand and Purchasing already share an actor/
rhythm, unlike Demand-and-Parts or Demand-and-Inventory.

**Dependency chain check** (walking the example workflow: Maintenance creates a demand → it gets
purchased → an intake record links to the PO → a part is issued and a movement record ties back
to the original demand, moving it to the issuance state):

- Maintenance → depends on Demand+Purchasing (creates a demand)
- Demand+Purchasing → self-contained (PO created)
- Inventory → depends on Demand+Purchasing (intake references the PO; issuance references the
  original demand and flips its state)

Nothing built earlier has to reach forward into something built later — the same one-directional-
reference discipline already used for `Part.id` (D3), applied one layer up. Demand+Purchasing is
also independently useful *before* Inventory exists (a working requisition/procurement tracker
even with no warehouse automation yet), unlike an ordering where Demand's fulfillment states are
meaningless until Inventory is built first.

**Open questions on this option — resolved 2026-08-08, see `decisions.md`:**

1. **Does every PO trace back to a demand?** Resolved (D14): no — a PO can have zero linked
   demands (proactive/bulk restocking is in scope). PO and Demand stay peers linked by
   `DemandSetLine`, PO is never nested under Demand.
2. **Who has authority to close out a demand on physical issuance?** Resolved (D12): the physical
   handoff is the truth — a future Inventory app's direct manager call auto-transitions
   `issue_state`, no separate Supply-side reconciliation/confirmation step.

## Build-order question

Reconsidered from "Maintenance first, then Inventory" (the old system's actual order — Maintenance
invented "I need parts for this action" locally first, then Dispatching needed the same concept
and it got promoted to the shared `part_demands` hub) to building the supply-chain apps before the
request-originating ones:

**Proposed order:** Demand + Purchasing → Inventory (intake/stocking/issuance) → Maintenance →
Dispatching.

Rationale: each stage should be independently valuable and only depend on what's already built.
Demand+Purchasing is useful standalone (a requisition/procurement tracker) with zero physical
fulfillment automation. Inventory then gives it real fulfillment mechanics to point at (PO lines,
storerooms, receiving). Maintenance and Dispatching, built last, generate demand against a system
that's actually ready to fulfill it — avoiding the old system's felt experience of building
request workflows against a fulfillment layer that didn't exist yet.

(An earlier, now-superseded proposal in this same discussion was Parts → Inventory → Demand (as
its own hub) → Maintenance/Dispatching. Rejected in favor of the above once Demand+Purchasing was
reframed as one Procurement-shaped app — see "Where should Part Demand live?" above.)

## Data-model shape for demand status tracking

Instead of the old system's three bare status columns (`approval_status`, `issue_status`,
`order_status`) with inconsistent per-dimension audit columns bolted on ad hoc, the proposed shape
is:

- The demand row keeps **current-state columns** (a live snapshot) for fast list/filter queries
  ("show me everything pending approval") without joining to history every time.
- A **generic append-only update/event table** — `(dimension, stage/outcome, actor, timestamp,
  notes)` — records every transition, across all three dimensions uniformly. The snapshot columns
  are refreshed alongside each insert; they are never written to directly.
- This is the same shape as this project's documented **StateMachine** guard pattern (see
  [../../../harness/Architecture/patterns/oop_control_patterns.md](../../../harness/Architecture/patterns/oop_control_patterns.md)
  — "explicit transitions for status-driven entities") applied uniformly across all three
  dimensions instead of ad hoc per-dimension column pairs.
- Demand-to-PO linking (many-to-many, e.g. old system's `PartDemandPurchaseOrderLink` with
  `quantity_allocated`) is a **separate, orthogonal** join table — it answers "which POs fulfill
  this demand and how much," not "what happened to this demand," and should not be folded into
  the update/event table.

**Open question, resolved 2026-08-08 (D15):** an update row's `notes` field stays optional free
text — no mandatory reason is required, even for Rejected/Cancelled outcomes.

## Status

The direction in this document held: the starter kit `procurement_starter_kit/` was
initiated, and its `questionnaire.md`, `decisions.md`, and `open_questions.md` are now the current
source of truth for this app's design. This document remains as the original design-review
reasoning that motivated the build order and app boundaries.
