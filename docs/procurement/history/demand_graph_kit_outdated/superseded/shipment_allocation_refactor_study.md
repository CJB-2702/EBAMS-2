---
okf_version: "0.1"
type: "Study"
title: "Shipment Allocation Refactor — Study"
description: "Replacing ShipmentLine's single purchase_order_line FK with a PO-line ↔ shipment-line allocation table: what it reverses, the objection it must answer, the proposed schema, and the consequences for the demand graph."
tags: [starter-kit, study, procurement, shipments, graphs, refactor]
context_tier: 2
---

# Shipment Allocation Refactor — Study

> **STATUS: DRAFT FOR REVIEW — not agreed, not planned, not phased.**
>
> Written to a recommended position throughout so there is a claim to react to rather than a menu.
> Sections marked **`OQ-S<n>`** are the ones only the developer can settle; everything else is a
> recommendation with its reasoning attached. Once this document is edited and accepted, the phase
> plans in this kit are rebuilt against it — see §10 for what specifically moves.

---

## 1. The change

`ShipmentLine` currently points at **exactly one** `PurchaseOrderLine` by nullable FK. A physical
line item that fulfils several PO lines is handled by **splitting it into sibling rows**
(`split_from` preserves lineage), driven by a wizard.

**The change: a shipment line may be allocated across many PO lines through a join table carrying
quantities**, exactly as a demand is already allocated across many PO lines through
`PurchaseOrderDemandLink`.

The network becomes symmetric. Today one side of the graph is a real many-to-many with quantities
and the other is an FK with a splitting workaround; after this, both sides are the same shape.

```
        PartDemand ──< PurchaseOrderDemandLink >── PurchaseOrderLine ──< ShipmentLineAllocation >── ShipmentLine
                              (exists)                                        (NEW — this study)
```

---

## 2. What this reverses, and the objection it has to answer

This is not a gap being filled. It is a decision being reversed, and the reversal is only legitimate
if it answers the original objection.

**D59** (procurement kit) and the `ShipmentLine` docstring both record that a
`PurchaseOrderShipmentLink` many-to-many was drafted and deliberately removed:

> With a link table, an arriving line's quantity and the sum of its links can disagree, so there are
> two numbers for one physical fact and a reconciliation problem between them — which the legacy
> design carried as `ArrivalLine.quantity_available_for_linking`, a column existing only to describe
> a discrepancy the schema made possible. With splitting, each row's quantity **is** the fact and the
> rows sum to the shipment by construction.

That objection is real and it does not go away. Two things have changed since it was written, and
together they answer it.

**First: the discrepancy is now derived, never stored.** The legacy design's actual sin was storing
`quantity_available_for_linking` — a third number alongside both of its operands, which
[D17 of this kit] already names as *"three places for two facts to disagree."* The unallocated
remainder of a shipment line is `quantity − Σ allocations`. It is computed where it is displayed and
stored nowhere. There is exactly one number for the physical fact (`ShipmentLine.quantity`) and one
number per pairing (`quantity_allocated`); the gap between them is arithmetic, not state.

**Second: this kit's policy on mistakes has changed** (decision B of the 2026-08-15 review session).
Over-allocation is no longer blocked at write time on the PO side — the user is allowed to link
whatever they link, and the graph surfaces report the resulting imbalance as a named state with a
suggested action. That is precisely the disposition a shipment-side link table requires: a drift
between `quantity` and `Σ allocations` becomes **a visible, named, actionable graph state** rather
than a schema-level impossibility.

> **Recommendation S1.** Proceed with the link table, on the explicit condition that the remainder is
> **derived and never stored**, and that both under- and over-allocation are permitted and surfaced as
> graph states rather than blocked. Record the reversal against D59 by name so the original reasoning
> is not lost — it was correct for the design it was written for.

### Why splitting is not enough any more

Stated so the reversal is not read as taste:

1. **Splitting destroys the physical record.** One box, one packing-slip line, sixty units — after a
   split there are two rows of thirty, and the thing the vendor actually sent no longer exists as a
   row. Every downstream count (inspection, acceptance, the intake build's reconciliation) is then
   performed against an artefact of our bookkeeping rather than against the item.
2. **It is a user action for a data problem.** D59 conceded this — *"the cost is that splitting is an
   explicit user action, which is why it gets a wizard."* A wizard is a large, permanent UI surface
   maintained to work around a schema shape.
3. **It cannot represent partial allocation at all.** A sixty-unit arrival where forty are known to
   fulfil a PO line and twenty are unidentified must currently either be split (inventing a
   twenty-unit row nobody shipped) or assigned whole to the wrong line. With allocations it is one
   row, one allocation of forty, and a derived remainder of twenty.
4. **The intake build makes it worse.** `inventory_build_kit/shipment_and_intake_design_review.md`
   §5 carries two open questions — *"who resolves a box that spans multiple orders"* and *"what
   happens to an intake line with no shipment match"* — that are both consequences of the FK. An
   allocation table is the shape those answers want.

---

## 3. Proposed table

Mirrors `PurchaseOrderDemandLink` deliberately: same suffix family, same soft-delete + `is_active`
split, same "peer join row, not a restricted view of either side" framing (M2).

### Name — **`OQ-S1`**

| Candidate | For | Against |
| :--- | :--- | :--- |
| **`ShipmentLineAllocation`** *(recommended)* | Says what it carries (an allocation with a quantity); parallel to the `allocations` related_name already used by `PurchaseOrderDemandLink` | Does not name both sides |
| `PurchaseOrderShipmentLink` | The name the rejected draft used; naming continuity with the reversal | Reusing a rejected name invites confusion with the thing that was removed; also names the *headers*, not the lines |
| `ShipmentLineDemandLink` | Fits D50's `<thing>DemandLink` family | **Wrong** — it links to a PO line, not a demand |

### Columns

| Field | Kind | Notes |
| :--- | :--- | :--- |
| `shipment_line` | FK → `ShipmentLine`, **PROTECT**, `related_name="allocations"` | PROTECT, not CASCADE: an allocation is a record of a physical arrival being claimed, and must block a hard delete of the line |
| `purchase_order_line` | FK → `PurchaseOrderLine`, **CASCADE**, `related_name="shipment_allocations"` | CASCADE mirrors `PurchaseOrderDemandLink` — an allocation to a deleted draft line is meaningless |
| `quantity_allocated` | decimal(12,3), `> 0` | How much of this shipment line is claimed as fulfilling this PO line |
| `is_active` | bool, default `True` | Same two-verb split as `PurchaseOrderDemandLink`: **de-link** (the user changed their mind) is a soft delete; **release** (the PO was cancelled) sets `is_active = False` and stays readable as history |
| `notes` | text, blank | Why this pairing exists — the vendor-consolidation explanation |
| *audit + soft delete* | — | `AuditFieldsMixin`, `SoftDeleteMixin`, as every other table |

**Deliberately absent:** any acceptance or received quantity. See §5.

### Constraints and indexes

```python
constraints = [
    UniqueConstraint(fields=["shipment_line", "purchase_order_line"],
                     name="uniq_sla_shipment_line_po_line"),
    CheckConstraint(condition=Q(quantity_allocated__gt=0),
                    name="sla_quantity_allocated_positive"),
]
indexes = [
    Index(fields=["shipment_line", "is_active"], name="sla_shpline_active_idx"),
    Index(fields=["purchase_order_line", "is_active"], name="sla_poline_active_idx"),
]
```

One allocation per pairing — a user wanting more edits the existing row, never creates a second.
Identical to `uniq_podl_demand_line`.

> **No constraint that `Σ quantity_allocated <= ShipmentLine.quantity`.** Per Recommendation S1 and
> the kit's decision B, over-allocation is permitted and reported, not blocked. A DB constraint here
> would also be unenforceable across rows without a trigger.

---

## 4. What happens to the existing columns — **`OQ-S2`**

| Column | Recommendation | Reasoning |
| :--- | :--- | :--- |
| `ShipmentLine.purchase_order_line` | **Drop** | Keeping it as a "primary" allocation creates two sources of truth for the same edge and a rule about which wins. The graph BFS, the fulfillment struct, and the templates all move to the link table together. |
| `ShipmentLine.split_from` | **Keep** | Splitting remains legal and occasionally right (a genuinely mis-packed line). It stops being the *mechanism* for multi-PO arrivals, so it becomes rare — but lineage on the splits that do happen is still worth preserving. |
| `Shipment.has_splits` (D69) | **Keep, re-scope** | Still a real lock trigger for the bulk tool; it just fires far less often. |
| `Shipment.mixed_po_assignments` (D59) | **Re-derive** | Currently computed from `line.purchase_order_line.purchase_order`. Becomes "any allocation on any line points at a different PO than the header's" — same flag, new source. |
| `ShipmentLine.quantity_accepted` | **Keep, unchanged** | §5. |

The alternative — keep the FK as a denormalized "primary allocation" for read convenience — is
listed only to be rejected: it is the `po_qty_waiting_for_purchase` mistake in a new place.

---

## 5. Where acceptance lives — the load-bearing question

**Recommendation S2: `quantity_accepted` stays on `ShipmentLine` and the allocation table carries no
acceptance column of any kind.**

This is D55's reasoning, applied unchanged to the new table. `PurchaseOrderDemandLink` has no
`quantity_received` column, and the docstring explains exactly why:

> The problem is not where the number is stored — it is that for a shared PO line the number does not
> exist. Three demands on one line, sixty units arrive: the units are fungible, nobody decided whose
> they were, and any attribution a receiver typed would be an invention recorded as an observation.

A shipment line allocated across two PO lines has the identical property. Someone inspects a box and
finds 58 of 60 good. Which PO line got the two bad ones? Nobody decided; the units are fungible; any
answer typed into an allocation row would be an invention recorded as an observation.

**So:** arrival is recorded once, physically, on `ShipmentLine.quantity_accepted`. Per-PO-line
acceptance is **derived** — exact when the line has exactly one active allocation, and reported as a
shared figure otherwise, reusing the attribution-mode machinery
`procurement_starter_kit/shared_demand_sessions.md` already defines for the demand side.

This has a consequence worth stating plainly: **acceptance attribution becomes ambiguous in a place
it currently is not.** Today a shipment line has one PO line, so acceptance attributes exactly. After
this change it may not. That ambiguity is not created by the schema — it is created by the vendor
consolidating two orders into one box — and the current schema hides it by forcing a split. This
change stops hiding it.

---

## 6. Consequences for the demand graph

This is why the refactor lands in *this* kit rather than being deferred: it changes the graph's edge
set, and every quantity column this kit defines on the shipment side.

### 6.1 The edge changes shape

`GraphSummaryManager`'s BFS currently reads `ShipmentLine.purchase_order_line_id` as a direct edge
([graph_summary_manager.py](../app/procurement/control_layer/managers/graph_summary_manager.py)).
After this change it reads the allocation table, exactly as it already does for
`PurchaseOrderDemandLink`.

**This is a simplification, not a complication.** The manager currently has two edge-traversal
idioms; it ends up with one, applied twice. Node-init, merge, and split all become symmetric across
the two link tables.

**New:** de-linking a shipment allocation now triggers `split_if_disconnected`, which it cannot today
(reassigning an FK moves an edge but never severs a component in the same way). One more caller for
an existing path.

### 6.2 The fan-out trap now exists on both sides

`po_qty_allocated` already sums a second multi-row relation, which is the D67 bug this kit's phase 1
carries a dedicated regression test for. **`shipment_qty_allocated` acquires exactly the same
property.** It must be its own query over the allocation table filtered by
`shipment_line__graph_id`, never annotated onto the member shipment-line queryset.

Phase 1's fan-out regression test gets a twin.

### 6.3 The three shipment quantity columns

| Column | Before this refactor | After |
| :--- | :--- | :--- |
| `shipment_qty_allocated` | Σ `ShipmentLine.quantity` — a lie, since nothing was allocated | Σ `ShipmentLineAllocation.quantity_allocated` over active links to member lines — **the name becomes true** |
| `shipment_qty_delivered` | Σ `ShipmentLine.quantity` where shipment status is delivered | Unchanged in definition. **`OQ-S3`:** does it become allocation-weighted, or stay the physical figure? Recommendation: **stay physical** — it answers "how much material reached the dock", which is not an allocation question. |
| `shipment_qty_accepted` | Σ `ShipmentLine.quantity_accepted` | Unchanged — §5 keeps acceptance on the line |

This resolves a naming problem the current kit has: `ShipmentImbalanceState.SHIPMENT_ALLOCATION_EXCEEDS_PO`
compares `shipment_qty_allocated` against `po_qty_purchased`, but before this refactor there is no
shipment-side allocation for it to measure — it is comparing raw arrival quantity to purchased
quantity and calling the difference an "allocation mismatch." **After this refactor that state means
what its name says.**

### 6.4 The demand-less / unallocated arrival becomes representable

A shipment line with zero allocations is now a first-class, expressible state — *"material arrived
and nobody has said what it is for"* — rather than a null FK. Combined with the derived remainder,
the graph can distinguish:

- fully allocated arrival
- partially allocated arrival (`Σ allocations < quantity`)
- over-allocated arrival (`Σ allocations > quantity`) — permitted per decision B, reported
- unallocated arrival (no active allocations)

**`OQ-S4`:** do any of these earn their own `ShipmentImbalanceState` value, or are they reported as
plain derived quantities on the detail surface? Recommendation: **one new state,
`SHIPMENT_ARRIVAL_NOT_ALLOCATED`**, for the fully-unallocated case, since it is the one with an
obvious suggested action ("this arrived against nothing — allocate it to a PO line"). The partial and
over cases are quantities, not states.

---

## 7. What this costs — code inventory

Not an implementation plan; a scale check. Files that read or write
`ShipmentLine.purchase_order_line` today:

| Layer | Files |
| :--- | :--- |
| Models | `shipments/shipment_line.py` (drop FK, rewrite docstring — it currently argues *against* this design) |
| Control | `shipment_line_manager.py` (`resolve_purchase_order_line`, `create`, `reassign`), `shipment_context.py`, `shipment_line_split_handler.py`, `basic_shipment_manager_submit_handler.py`, `shipment_status_manager.py`, `graph_summary_manager.py`, `guards/shipment_line_guard.py` |
| Structs | `purchase_order_fulfillment_struct.py`, `shipment_struct.py`, `purchase_order_struct.py`, `part_demand_struct.py`, `graph_diagram_struct.py` |
| Presentation | `search/purchase_order_line_search.py`, the shipment entrypoints |
| Templates | `shipments/edit.html`, `shipments/detail.html`, `purchase_orders/detail.html` |
| Seeds | `seed_procurement_dev.py` — several of D89's eleven graph scenarios are built around the FK, and the "shipment-line split across two PO lines" scenario changes meaning entirely |
| Tests | `test_graph_summary_manager.py` and the shipment-side suites |
| Docs | `procurement_starter_kit/decisions.md` (D59 reversal, D69 re-scope), `models/package.md`, `po_demand_association_graph.md`, `front-end-kit/procurement/packages/*` (the splitting wizard's justification changes), `inventory_build_kit/shipment_and_intake_design_review.md` §4 |

A new manager (`ShipmentLineAllocationManager`) and guard (`shipment_line_allocation_guard.py`)
mirroring `PurchaseOrderDemandLinkManager` / `purchase_order_demand_link_guard.py`.

---

## 8. Open questions for the developer

| # | Question | Recommendation |
| :--- | :--- | :--- |
| **OQ-S1** | Table name | `ShipmentLineAllocation` |
| **OQ-S2** | Drop `ShipmentLine.purchase_order_line`, or keep it as a denormalized primary? | **Drop** — two sources of truth otherwise |
| **OQ-S3** | Does `shipment_qty_delivered` stay physical or become allocation-weighted? | Stay physical |
| **OQ-S4** | Does the unallocated arrival get its own `ShipmentImbalanceState`? | Yes — one value, `SHIPMENT_ARRIVAL_NOT_ALLOCATED` |
| **OQ-S5** | Does this refactor belong **inside** this kit as a new phase 0, or as its own kit that this one depends on? | See §10 |
| **OQ-S6** | Does the splitting wizard survive at all, or is it retired along with its justification? | Survives, demoted — splitting a genuinely mis-packed line is still real |
| **OQ-S7** | Is an allocation permitted to a PO line on a **different PO** than the shipment header's? | Yes — that is the vendor-consolidation case this exists for; `mixed_po_assignments` already flags it |
| **OQ-S8** | Part-match rule: must `allocation.shipment_line.part == allocation.purchase_order_line.part`? | **Yes, and it is load-bearing** — this kit's `GraphSummary.part` is non-nullable and asserted across members (D2/D3), so a cross-part allocation would break graph identity, not just tidiness |

---

## 9. What this does **not** change

- **Acceptance stays on the line** (§5). No `quantity_accepted` on the allocation row, ever.
- **No stored remainder.** `quantity − Σ allocations` is derived at read time.
- **The intake boundary.** Inventory's `Package`/`IntakeLine` remain a parallel header, not a child
  of `Shipment`. This refactor makes their eventual matching easier; it does not perform it.
- **The graph's materialized shape.** `GraphSummary` still holds one row per connected component with
  every metric denormalized onto it. Only the edge source changes.

---

## 10. Effect on this kit — **`OQ-S5`**

Two routes:

**(a) A new phase 0 inside this kit.** The demand-graph surfaces kit already forces one full schema
reset; folding the allocation table into it means one reset instead of two, and phase 1's fan-out
work is written once against its final shape rather than being rewritten in a follow-up.

**(b) Its own kit that this one depends on.** Cleaner scope — this kit is *"make graphs findable and
judgeable"*, and re-plumbing the shipment side is a different job with its own questionnaire,
its own reversal of D59, and its own front-end consequences (the splitting wizard).

> **Recommendation: (b), built first.** The scope argument is decisive — §7 lists roughly thirty
> files across every layer plus a front-end wizard whose justification evaporates, which is a kit,
> not a phase. But it must be built **before** this kit, not after: `shipment_qty_allocated`,
> `SHIPMENT_ALLOCATION_EXCEEDS_PO`, and the phase-1 fan-out test all describe a shipment-side
> allocation that does not exist yet. Building the graph surfaces first means writing them against
> the FK and rewriting them immediately.

**If (b) is chosen, this kit's phase plans change as follows** — the resync that is currently queued
should account for it rather than be done twice:

| Where | Change |
| :--- | :--- |
| Phase 1 data plan | `shipment_qty_allocated` sources from the allocation table; second fan-out regression test |
| Phase 2 | `SHIPMENT_ALLOCATION_EXCEEDS_PO` becomes meaningful; possible new `SHIPMENT_ARRIVAL_NOT_ALLOCATED` (OQ-S4) |
| Phase 4 | `GraphDetailStruct`'s shipment node list gains per-allocation rows; the swimlane diagram gains the new edge type |
| README / model_diagram | Declared dependency on the shipment-allocation kit |
| `open_questions.md` | OQ-S1…S8 tracked until that kit exists |

---

## Reviewer checklist

- [ ] §2's reversal of D59 is accepted, or the objection is judged unanswered
- [ ] §5's "acceptance stays on the line" is accepted — this is the one that is expensive to change later
- [ ] OQ-S1 … OQ-S8 answered
- [ ] OQ-S5 route chosen: phase 0 of this kit, or its own kit built first
- [ ] Once accepted, D59 gets a reversal entry in `procurement_starter_kit/decisions.md` and the
      `ShipmentLine` docstring is rewritten — it currently argues against this design in detail
