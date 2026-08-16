---
okf_version: "0.1"
type: "Kit Document"
title: "Decisions — Demand Graph Surfaces"
description: "Architectural decision log for the demand-graph surfaces kit: options considered, what was chosen, and why."
tags: [starter-kit, decisions, procurement, graphs]
context_tier: 2
---

# Decisions — Demand Graph Surfaces

> **AUTHORITY: [`all_statuses_review.md`](all_statuses_review.md) for status shape; the CODE for
> everything else.** This file is the reasoning record — *why* each choice was made and what was rejected.
> Where it disagrees with `all_statuses_review.md` or with what is in `app/procurement/`, they win and this
> file is stale. It is kept because the arguments here are not recoverable from the code.

Decision IDs are local to this kit (`D1`, `D2`, …). References to `D14`, `D28`, `D79`–`D88` and similar
point at [`procurement_starter_kit/decisions.md`](../procurement_starter_kit/decisions.md), which is the
prior art this kit builds on.

## Revision log

| Date | Change |
| :--- | :--- |
| 2026-08-15 | Kit generated. D1–D22. |
| 2026-08-15 (evening) | Three-axis rework: D9 rewritten, D10/D10b/D12 added, D23/D24 appended. |
| 2026-08-16 | **Review pass.** D7 reversed (D25). Search-surface shape settled (D27). Vocabulary locked (D28). D23/D24 and `ACCEPTED_AS_IS` were cut, then **un-cut** when `all_statuses_review.md` was made the status authority. |
| 2026-08-16 | **BUILT.** Schema, three status axes, identity columns, and the resolution write path are implemented and tested. See [`README.md`](README.md) for what exists and where. |

---

## D1 — The umbrella vocabulary is "graphs", and a graph is a network of nodes

**Options:** keep the entity-first navigation with no umbrella; adopt a new domain word; use "graphs".

**Chosen:** `graphs`, with **"node"** as the user-facing word for a member (a demand, a PO line, or a
shipment line).

**Why:** it matches what the code already calls this (`GraphSummary`, `MermaidSwimlaneBuilder`) and
introduces no new vocabulary. The known cost is the collision flagged in questionnaire M1 — "graph" reads
as *chart* to most people, and this app will eventually have charts. Mitigated by insisting on node/edge
language throughout and by the swimlane diagram carrying the network reading visually.

**"Package" is dead vocabulary** and must not reappear: D83 renamed `Package`/`PackageLine` →
`Shipment`/`ShipmentLine` throughout.

---

## D2 — `GraphSummary` gets a non-nullable `part` FK

**Options:** (a) no column, join out to members; (b) nullable column meaning "the shared part, or NULL if
members disagree"; (c) non-nullable column, cross-part graphs disallowed.

**Chosen:** (c).

**Why:** the primary use case is "find graphs for this part", and (a) makes that a three-way join across
member tables — the exact fan-out D79 exists to eliminate. (b) was offered as a hedge against the part-match
guard being relaxed later and was **rejected deliberately**: cross-part graphs are not a future to design
around, they are disallowed. All three member types already carry a `part` FK, so non-null is always
satisfiable from the first node.

**Consequence, priced:** `PurchaseOrderDemandLinkValidator` enforces part-matching as a *soft* rule kept
out of the database precisely so it could be relaxed later. That door is now closed, and the validator's
docstring — which currently advertises the rule as cheap to relax — is now misleading. See D3.

**This is a schema change** and triggers a full `refresh_project.py` reset.

---

## D3 — The part-match rule becomes load-bearing and must say so

**Chosen:** harden the check to a database-level guarantee if the migration cost is acceptable; otherwise
record the new dependency in `PurchaseOrderDemandLinkValidator`'s docstring.

**Why:** D2 makes a stored column depend on a rule that documents itself as easily relaxed. Whichever route
is taken, the next person to consider relaxing it must see the cost. Resolved in phase 1's control-layer
plan.

---

## D4 — `primary_domain` is the search scope; membership domains are the detail scope

**Options:** graphs stay un-scoped as they are today; scope by any member domain; scope by a single stored
domain.

**Chosen:** two different rules for two different surfaces.

| Surface | Rule |
| :--- | :--- |
| Search / list | `WHERE primary_domain IN <user's domains>` |
| Detail view | Admit if the user holds **at least one** member's domain |

**Why:** the existing visualizer's rule (a graph is not itself domain-owned; each member is) works for a
page reached from a member you could already see, but it does not survive contact with a *list* page —
without a scope column, the list is a directory of every cluster in the company. A single indexed column is
what keeps the hot read path a plain `WHERE`.

**Derivation** (D5) and the accepted gap (D6) follow.

---

## D5 — `primary_domain` is derived by most-common PO line, with a fallback chain

**Chosen:** first rule yielding a domain wins — (1) most common across member PO lines; (2) most common
across member demands; (3) most common across member shipment lines. **Ties broken by lowest `domain_id`.**

**Why:** this **reverses an earlier instinct to derive it from demands**. PO lines are the centre of the
purchasing process, so the domain doing the buying is the one that should own the graph in a list. The
fallback chain is required because every newly created demand is a single-member graph with zero PO lines —
the majority of rows — for which the primary rule is undefined.

Determinism matters more than the specific tie-break: `recalculate()` fires constantly, and a flapping
`primary_domain` would make graphs appear and disappear from search results with no visible cause. The
lowest-id tie-break matches the existing precedent in `GraphSummaryManager.merge` ("the lower `graph_id`
survives") for the same reason.

---

## D6 — Accepted domain leakage on the detail view, and an accepted findability gap

**Chosen:** two knowing compromises, both marked.

1. Once admitted to a graph detail page by holding *any* one member's domain, **out-of-domain members are
   displayed** as plain text with no link through. More permissive than row-level scoping elsewhere. Mark
   with `# DELIBERATE ANTI-PATTERN` and state the reasoning inline.
2. A graph whose `primary_domain` is not yours but which contains your member is **reachable by
   click-through yet absent from your search**.

**Why:** (1) a graph you can only half-see is not legible, and every member is already reachable through the
entity that links to it. (2) accepted on the reasoning that whoever linked the two items should hold both
domains anyway, so the person who cares can still find it.

Both are logged as tech debt. (2) is the first thing to revisit if users report "I know that graph exists
but I cannot find it."

---

## D7 — Imbalance is measured against **allocated**, never against **ordered**

> **⚠ REVERSED 2026-08-16 by [D25](#d25--d7-is-reversed-ordered-vs-demand-is-a-real-condition).** The text
> below is retained because it is the reasoning of record for why allocation is the *coverage* measure, and
> because the bulk-restock scenario it describes is real and still has to be lived with. But its conclusion
> — that ordered-vs-demand must never be surfaced — no longer holds.

**Chosen:** every imbalance comparison uses `PurchaseOrderDemandLink.quantity_allocated`, not
`PurchaseOrderLine.quantity_ordered`.

**Why — this is the kit's central correction.** They are different numbers and only one is about this
demand. D14 permits a PO with zero linked demands because that is how bulk restocking is modelled. A line
ordering 1000 widgets with a 10-unit demand allocated against it is **healthy**; an ordered-based comparison
reports it as over-ordered by 990. Every bulk restock would light up the worklist and the worklist would be
abandoned.

**Ordered vs. allocated is not an imbalance — it is inventory strategy.** The difference is unallocated
stock the business chose to buy, and nothing about it needs resolving.

Full reasoning: [`imbalance_and_resolution_study.md`](imbalance_and_resolution_study.md) §1.

---

## D8 — There is no over-allocated state; the real "over" is on arrival

> **⚠ PARTIALLY SUPERSEDED 2026-08-16.** D8's core claim survives: allocation *itself* is still guarded by
> `AllocationCapExceeded`, so there is no `OVER_ALLOCATED` state. But `PO_QUANTITY_EXCEEDS_DEMAND` (D10b)
> and `SHIPMENT_ALLOCATION_EXCEEDS_PO` (D10b) are over-conditions on different comparisons, and D25 keeps
> both. "The only over-condition" is no longer true.

**Chosen:** no `OVER_ORDERED` / `OVER_ALLOCATED` state. `OVER_DELIVERED` (`qty_accepted > demand_qty`) is
the only over-condition.

**Why:** `AllocationCapExceeded` (D28) already guards allocation from exceeding a demand's outstanding
request, and the override path raises the demand to match — leaving the graph balanced by construction. A
state that fires approximately never misleads the reader into thinking the system checks something it does
not. It also avoids the M1 collision: "over-allocation" already has a precise meaning here.

Arrival is where nothing guards it, and per questionnaire G4 an over-delivery is usually *a vendor fact
learned late* rather than anyone's mistake — which constrains the wording (D12).

---

## D9 — Three separate concern axes, not one complex enum

**Options:** one precedence-ordered enum trying to capture all states; separate enums per workflow; separate columns per concern.

**Chosen:** three separate enums, each with its own precedence chain:
- `POImbalanceState` — is the demand fully committed to purchase orders?
- `ShipmentImbalanceState` — did we receive what we ordered?
- `LinearStatus` — where in the end-to-end pipeline?

**Why:** a PO administrator needs allocation clarity; a shipment administrator needs delivery clarity. Folding both into one enum forces one reader's logic onto the other without adding insight. Three axes make each workflow's state machine crisp and independent, while the **linear status** gives a simple overall progression view.

**Previously considered:** a single precedence-ordered `GraphImbalance` enum with values like `UNATTACHED`, `OVER_DELIVERED`, `UNDER_ALLOCATED`, `AWAITING_PLACEMENT`. Rejected because it conflated two unrelated questions (commitment gaps vs. delivery gaps) and its precedence order would favor one reader over another.

---

## D10 — PO-side allows over-allocation; shipment-side tracks against ordered qty

**Chosen:** 
- PO side: a demand can have allocations on *multiple* PO lines (intentional multi-sourcing or overstocking). This is legitimate.
- Shipment side: the reference point is `po_qty_purchased` (what we actually ordered), not `demand_qty`.

**Why:** D14 (from the procurement kit) permits a PO with zero linked demands because that is how bulk restocking is modelled. By extension, a demand can allocate to multiple lines as an intentional strategy. `POImbalanceState.DEMAND_SATISFIED_EXCESS_ALLOCATED` labels this as healthy — not an error.

Shipments are arrivals against orders, not against demands, so tracking against `po_qty_purchased` is more actionable than tracking against demand. The demand's commitment is the PO side's problem; the shipment side's job is answering *"did we get what we ordered?"*

**Extended by D10b** with explicit visibility states for admin remediation.

---

## D10b — Explicit imbalance states for PO and shipment mismatches

**Chosen:** 
- Add `PO_QUANTITY_EXCEEDS_DEMAND` state to POImbalanceState
- Add `SHIPMENT_ALLOCATION_EXCEEDS_PO` state to ShipmentImbalanceState

**Why:** admins need fast visibility into cases requiring action:
- **PO_QUANTITY_EXCEEDS_DEMAND:** when ordered qty > demand qty, admins can immediately see they need to either raise demand to match the purchase, adjust allocations down, or accept intentional overpurchase. Without this state, the gap is hidden.
- **SHIPMENT_ALLOCATION_EXCEEDS_PO:** when more is allocated to shipments than we ordered, it signals an allocation error or mix-up. Admins see it immediately and can fix allocations, add demand, or clarify with receiving.

Both are discoverable in a simple worklist query and reduce the need for admins to reverse-calculate from imbalance combinations.

---

## D11 — No time or staleness component in v1

**Chosen:** ship with no age-based state, and say so explicitly rather than let the absence read as an
oversight.

**Why:** there is nothing trustworthy to measure with. Questionnaire M5 declined last-activity columns on
sound grounds (every demand, PO, and shipment write would have to reach over and touch the graph).
`updated_at` moves on every `recalculate()` — it means *last recomputed*, not *last happened*. `created_at`
is destroyed by merges. Building staleness on either would be a lie dressed as a metric.

Adding it later is a decision to reverse M5 and pay for the columns, made on its own merits when someone has
felt the absence.

---

## D12 — Error codes for end-state failures, not accusatory language

**Chosen:** if a graph's end state doesn't match (e.g., shipment delivered but commitment is incomplete), store an `error_code` that plainly describes the mismatch. No wording implies error or blame.

**Why:** the developer's emphasis is that a surface *"is only useful if it has suggestions"* and clear error messages. An `error_code` column documents *what* went wrong without accusation. E.g., a vendor overship is usually the system learning a vendor fact late, not anyone's mistake — the code documents the state, and the UI can phrase it neutrally: *"12 more units arrived than were ordered — accept surplus or return to vendor."*

**Example codes** (not exhaustive): `DELIVERY_EXCEEDS_PURCHASE_ORDER`, `PARTIAL_DELIVERY`, `UNPLACED_ORDER`. The code is a key; the UI renders it as human language at read time.

---

## D23, D24 — Demand auto-completion, and its accepted divergence — **BUILT**

**Chosen:** when a demand's parent graph reaches `LinearStatus.DELIVERED` and the demand's
`issuance_state` is anything other than `NOT_ISSUED`, `demand_state` is set to `COMPLETED`
automatically and locked.

**History, recorded so it is not re-litigated.** These two were briefly cut during the 2026-08-16
review pass on the grounds that they had no provenance in the questionnaire or brainstorming session,
were a demand-lifecycle change rather than a graph change, and collided with the procurement kit's own
D23/D24. The cut was **reversed** the same night when `all_statuses_review.md` was made the kit's status
authority — it specifies them, and the code already carried `DemandCompletionHandler`,
`PartDemandStateGuard`'s terminal-state set, and `demand_metrics`, all of which need
`DemandState.COMPLETED` to exist.

**The doc's wording is misleading and the code resolves it.** `all_statuses_review.md` says COMPLETED is
"removed from this axis", then says a demand is "marked complete" on that same axis. What it means is
that COMPLETED leaves the **manual** workflow, not the enum. It remains a `DemandState` value and remains
terminal; nobody transitions into it by hand any more.

**Accepted divergence (D24):** a locked demand can read COMPLETED while its parent graph reads an
earlier `linear_status` — a merge brought new members in, or more material arrived. The alternatives are
rewriting a completion record (breaks the audit trail) or snapshotting the demand at completion (a bigger
change than this pass). Revisit if users report confusion about a demand looking finished while its graph
needs attention.

**The number collision with the procurement kit's D23/D24 is real and unfixed.** Cite these as
"demand-graph D23", never bare "D23".

---

## D13 — The kit is not read-only: three human-editable columns

**Options:** fully read-only; a dismiss/snooze table; columns on `GraphSummary`.

**Chosen:** `resolution_state` (`OPEN` / `RESOLVED` — see D26), `manually_flagged`, and `priority`
(reusing `DemandPriority`), written **only** by `GraphResolutionManager`.

> **Amended 2026-08-16 by [D26](#d26--resolution_state-is-open--resolved-only).** `ACCEPTED_AS_IS` is
> removed. The paragraph below arguing for the split is superseded.

**Why — this reverses questionnaire M6's initial position, on a consequence surfaced at interrogation.**
Read-only was cleaner and dodged the merge/split problem entirely. But with no way to mark a graph done, the
worklist can never be worked down: a vendor overships 12 against a demand for 10, everything is accepted,
the business is finished — and that graph still appears in any list of incomplete graphs. Within months the
list is mostly noise, which is the failure mode that kills worklists.

`RESOLVED` and `ACCEPTED_AS_IS` are split because *"this got fixed"* and *"this is permanently lopsided and
that is fine"* mean different things to the next person, and the second is common enough to deserve its own
word.

`manually_flagged` (renamed from `is_flagged`) is explicit about intent: it is always a human's deliberate
action, and the column name clarifies that.

**There is no single stored "worklist filter".** D27 replaced the worklist with a plainly filterable list,
so "needs attention" is whatever combination of state columns the user filters on. The one place a
collective definition is still needed — the Ops Admin's count-by-domain rollup — uses **condition ≠
balanced**: any of the three state axes away from its resting value (`POImbalanceState.BALANCED`,
`ShipmentImbalanceState.BALANCED`, `LinearStatus.DELIVERED`), with `resolution_state != RESOLVED`.

---

## D14 — The survival principle for merges and splits

**Chosen:** one principle, four consequences.

> **Anything derived from a graph's configuration clears when the configuration changes. Anything
> expressing human judgment about importance propagates.**

| Event | `resolution_state` | `manually_flagged` | `priority` |
| :--- | :--- | :--- | :--- |
| Merge | Reset survivor to `OPEN` | `True` if either was | The more urgent of the two |
| Split | Reset **both** to `OPEN` | Copy to both | Copy to both |

**Why:** `resolution_state` is a statement about a specific set of nodes; when nodes join or leave, the
thing that was looked at no longer exists. Priority and flagging are about the underlying work — the part,
the urgency, the fact that somebody wants eyes on it — which restructuring does not invalidate.

Keeping the survivor's resolution on merge was rejected: a resolved graph would silently absorb an
unresolved one and stay resolved, making the absorbed graph's problem vanish from the worklist without
anyone addressing it.

**Priced cost:** a Buyer who resolves a graph may find it `OPEN` again after an unrelated allocation, with
no explanation. That is correct — the graph genuinely changed — but it will feel arbitrary. Mitigated by
D15.

---

## D15 — A cleared resolution writes a line to the members' activity trail

**Chosen:** when `recalculate()` clears a `resolution_state` because of a merge or split, record it on the
surviving members' existing activity threads.

**Why:** the graph carries no activity thread of its own (M5/M6), but its PO and shipment members do. A
Buyer who sees *"resolution cleared: this graph merged with another"* is being told the truth, rather than
concluding the system lost their input. Without it, D14's correct behaviour is indistinguishable from a bug.

---

## D16 — Three separate activity feeds, not one merged stream

**Chosen:** the graph detail page shows three labelled activity sections — one per node type — not an
interleaved chronological stream.

**Why:** the underlying infrastructure is **asymmetric**, and merging would paper over the asymmetry.
`PurchaseOrder` and `Shipment` each have an `event` OneToOne, and their Narrators write comments to
`activity_thread_id=<x>.event_id`, so real comment threads exist for both. `PartDemand` has **no** event FK
— `PartDemandNarrator` produces text for `PartDemandUpdate` rows, an append-only *state-transition journal*.
Those are different kinds of thing, and one stream would present a state change and a human comment as peers.

Building a comment thread for `PartDemand` purely to make the three uniform was considered and declined as
out of scope for this kit.

---

## D17 — `po_qty_waiting_for_purchase` is retired

**Chosen:** store `po_qty_ordered` and `po_qty_purchased`; derive waiting-for-purchase as the difference.

**Why:** the developer's own observation. Storing a difference alongside both of its operands is three
places for two facts to disagree, and `recalculate()` would have to keep all three consistent forever.

---

## D18 — A graph with zero members is deleted; merged graphs die without a tombstone

**Chosen:** stated as an explicit rule rather than emergent behaviour. Absorbed rows are **hard-deleted**,
with no tombstone and no redirect; a bookmarked URL to an absorbed graph **404s**, accepted.

**Because that 404 is a normal outcome rather than an error**, the detail view's not-found message should
say that a graph id which no longer resolves has most likely been absorbed into another. The view cannot
know which — the row is gone — but saying so converts a confusing dead end into an explicable one.

---

## D19 — The part surface is part-first, not a filtered graph list

**Chosen:** questionnaire M2's Reading B. The part-scoped surface is a **part-centric page showing a
collection of small individual graphs**, owning its own aggregate figures across them — not the graph list
with a filter applied.

**Why:** the developer's framing was a view of a part's activity *across* graphs (plural, historical), which
a filtered list does not deliver. More useful and more work, chosen deliberately.

---

## D20 — Clean cut on the URL move; the route name is the compatibility surface

**Chosen:** `procurement/graph/<id>/` → `procurement/graphs/<id>/`, moving into a new `urls_graphs.py`
alongside the other wave modules. No redirect from the old path. **Route name
`procurement_graph_visualizer` is unchanged.**

**Why:** matches extensions E2's clean-cut reasoning — the route is referenced only from templates inside
this project and always via `{% url %}` reverse by *name*, so changing the path breaks nothing. Renaming the
route for cosmetic plural consistency would touch every referencing template for no functional gain.

---

## D21 — No mirrored graph surface in `app/inventory/`

**Chosen:** explicitly no.

**Why:** D84's shipment mirror is precedent for a second app rendering procurement's rows, and someone will
eventually propose the same for graphs by analogy. The graph is a purchasing concept and receiving staff
have no use for it. Recorded so the answer exists before the question is asked.

---

## D22 — Read capability is granted to all authenticated users

**Chosen:** all four personas may read every graph surface. Row-level scoping (D4) still applies on top;
this is about *capability*, not visibility.

**Why:** deliberately simple for now. Gating happens where it already exists — a user who wants to *solve* a
problem needs the existing edit permissions on the PO, the demand, or the shipment. The graph surfaces do
not introduce a second permission vocabulary for the same acts.

**Open:** whether setting `resolution_state` / `manually_flagged` / `priority` (D13) needs its own
permission or rides on an existing one. Carried in `open_questions.md`.

---

## D25 — D7 is reversed: ordered-vs-demand is a real condition

**Options:** narrow D7 so ordered-vs-demand is an admin-only visibility state; drop
`PO_QUANTITY_EXCEEDS_DEMAND` and let D7/D8 stand; reverse D7 outright.

**Chosen: reverse D7 outright.** `PO_QUANTITY_EXCEEDS_DEMAND` (D10b) is a legitimate condition on equal
footing with the others, visible to anyone who filters for it.

**Why.** D7 argued that surfacing ordered-vs-demand would flood the worklist with every bulk restock and the
worklist would be abandoned. **That argument was about a worklist**, and D27 removes the worklist. On a
plainly filterable list there is no inbox to keep at zero, so a large population of legitimate overbuys is
not corrosive — it is simply a filter nobody has to apply. The condition is genuinely useful to the person
who *does* apply it: "what did we buy beyond what anyone asked for" is a real purchasing question with no
other answer in the system.

**Priced cost, stated plainly.** `PO_QUANTITY_EXCEEDS_DEMAND` will be the **largest population of any
non-balanced state in the system**, because every bulk restock produces one and nothing ever clears it.
D26 removes `ACCEPTED_AS_IS`, so there is no way to permanently silence an intentional overbuy, and D14
clears `RESOLVED` on every merge or split. **Overbought graphs are therefore permanent residents of this
state.** This is accepted: the state is descriptive, not a task list.

**The reasoning in D7 is not discarded** — allocation remains the measure of whether a demand is *covered*
(`DEMAND_EXCEEDS_ALLOCATION`). What is reversed is only the conclusion that the ordered comparison must
never be shown.

---

## D26 — `resolution_state` keeps all three values — **REVERSED, then BUILT with three**

**Built:** `OPEN` / `RESOLVED` / `ACCEPTED_AS_IS`.

**History.** A 2026-08-16 review decision briefly cut `ACCEPTED_AS_IS` on the developer's instruction
that a graph should be *"theoretically stateless except for the three human columns"*, reasoning that the
distinction it carried was narrative rather than structural. That was reversed the same night when
`all_statuses_review.md` became the status authority — it lists all three.

**Why three is defensible.** `RESOLVED` and `ACCEPTED_AS_IS` mean different things to the next reader:
*"this got fixed"* versus *"this is permanently lopsided and that is fine."* The second is the vendor
overship case, and it is common enough to deserve its own word rather than being filed under one that
implies action was taken.

**The unresolved tension, stated so it is not forgotten.** `ACCEPTED_AS_IS` is meant to silence a
permanently-imbalanced graph for good — but D14 clears `resolution_state` on every merge and split, so it
does not. An intentionally-overbought graph will return to `OPEN` the first time its cluster restructures.
Under D27's filterable list (rather than an inbox that must reach zero) this is survivable, but it means
`ACCEPTED_AS_IS` does not yet do the one job it exists for. **This is the sharpest open edge in the
build.** The fix, if wanted, is to exempt `ACCEPTED_AS_IS` from D14's reset while continuing to clear
`RESOLVED` — a one-line change in `GraphResolutionManager.carry_through_merge`.

---

## D27 — The search surface is a plainly filterable list, not a worklist

**Options:** severity-ranked worklist, worst-first; action-typed queues entered through a state picker;
a plain list with filterable state columns.

**Chosen:** a plain list. Staff filter on the state columns directly. **No precedence ordering, no
"worst-first", no queue picker, no landing page of counts.**

**Why:** with three independent state axes (D9) there is no defensible cross-axis ranking — precedence was a
property of the single enum that D9 discarded, and reviving it would mean choosing whose workflow outranks
whose. Filtering lets each reader assemble their own view without the kit deciding for them.

**What this kills, explicitly:**

- The precedence chain and its truth table (`imbalance_and_resolution_study.md` §4–§5).
- "Worst-first" as a capability. `functionality_and_roles.md` capability 1 is rewritten.
- **OQ5** (default worklist sort) — moot, struck.
- Per-row suggested actions. See below.

**Where the suggestion went.** Questionnaire G2 makes suggestions core scope — *"it's only useful if it has
suggestions."* On a three-axis filterable list a per-row suggestion column is unreadable, since one row can
be non-balanced on all three axes at once. **The list shows states; the detail page shows the suggestion.**
G2 is still satisfied, because on a filtered list the *filter itself is the action*: a user who filtered to
`DEMAND_EXCEEDS_ALLOCATION` already knows what every row needs.

---

## D28 — Vocabulary: states, condition, error code

**Chosen:** three words, each meaning exactly one thing.

| Word | Means | Where it lives |
| :--- | :--- | :--- |
| **state** | one value on one axis | `POImbalanceState`, `ShipmentImbalanceState`, `LinearStatus` |
| **condition** | the collective question *"does this graph need a human?"* — i.e. any axis away from its resting value | not a column; a phrase used in UI copy and in the D13 rollup definition |
| **error code** | a specific end-state mismatch, per D12 | `GraphSummary.error_code` |

**"Error modes" was considered as a rename for the three axes and rejected**, on three grounds:

1. `error_code` (D12) already owns the word "error" and means something narrower. Questionnaire M1's
   standing rule is that a word must not mean two things.
2. Several axis values are **healthy** — `DEMAND_SATISFIED_EXCESS_ALLOCATED` is labelled legitimate by D10,
   `PARTIAL_DELIVERY_RECEIVED` is routine, and `BALANCED` is the resting value. An enum called *error modes*
   whose values include `BALANCED` is a contradiction the reader must hold.
3. It reverses D12's tone rule. A vendor overship is *"a vendor fact learned late, not anybody's mistake"*;
   filing it under "error" re-imports the blame D12 removed.

**Revisit if** operations staff say "error mode" out loud in the field — user vocabulary beats internal
consistency. The fix at that point is to rename `error_code`, not the axes.
