---
okf_version: "0.1"
type: "Kit Document"
title: "Starter Kit Questionnaire — Procurement (answered from the built system)"
description: "The standard 20-question kit questionnaire, answered retroactively against the procurement application as built. The fastest single-document route into how the app works."
tags: [starter-kit, procurement, questionnaire, okf]
context_tier: 1
personas: [backend, business]
---

# Starter Kit Questionnaire — Procurement

**Status:** `COMPLETE` (answered retroactively)

> **This questionnaire was filled in backwards.** Normally the developer answers it and
> the kit is built from the answers. Here the application already existed, so every
> answer below was reverse-engineered from `app/procurement/` — the code is the source,
> and where an answer states a rule, that rule is enforced somewhere you can go and read.
>
> Because of that, nothing here is speculative and there is no interrogation stage
> pending. What would normally be "unknown" is instead recorded in §Open items at the
> bottom: things the code itself marks as deferred or unresolved.

---

## A. Goals

### G1 — In one sentence, with no nouns from your schema: what does this let someone do that they cannot do today?

State a material need, watch it turn into money spent with a vendor, watch the material
physically arrive, and at any moment see the gap between what was asked for, what was
bought, and what actually turned up — without any of the four people involved having to
chase the other three.

### G2 — What is this explicitly NOT? Name the adjacent system it will be mistaken for.

**It is not an inventory system**, and that is the mistake it will be made repeatedly.
There are no stock levels, no bins, no storerooms, and no put-away anywhere in it. The
last verb it owns is `accept`, and the boundary is exactly `ShipmentLine.quantity_accepted`.

Shipments nonetheless live here rather than in inventory, because a shipment in transit is
**pre-possession** — the two are separated by ownership of the goods, not by the calendar.

Three lesser negations: it is not accounts-payable (invoices are a price source, nothing
pays anybody), not vendor management (a vendor is a name, a code, and a website), and not
a workflow engine (legal transitions are flat dicts in one readable file; configurable
per-organization approval templates were considered and deferred whole).

### G3 — What is the single record everything else hangs off, and what is the *only* thing the rest of the app is allowed to know about it?

**`PartDemand`**, and the rest of the codebase knows only **`PartDemand.id`**.

Consumer apps (Maintenance, Dispatching, Inventory) own their own link tables pointing
*inward* at this row. There is never a pointer outward. The one seam that crosses the
boundary is `PartDemandContext.record_issuance()`, which Inventory calls with a net
quantity — procurement cannot compute it, because the rows behind it live in an app
procurement may not import.

`PartDemand.source_module` looks like an exception but is not: it is a denormalized
filter/display convenience and is **never** a source of truth for origin.

### G4 — Which of this data is authoritative for us, and which mirrors a system we do not control?

**Authoritative:** demands, purchase orders and lines, both allocation tables, shipments
and arriving lines, acceptance, the demand journal, and every graph column.

**Mirrors somebody else's reality:**

- `Shipment.shipment_id` and `carrier` — the vendor's/carrier's identifiers. Stored as
  plain strings, never modelled.
- `PurchaseOrder.vendor_po_id` — their number for our order.
- `PartDemand.shipment_state`'s middle stretch (production → prepared to ship → shipped) —
  vendor-reported facts, typed in or ideally machine-fed, never computed.
- **Prices.** The whole reason they are observations rather than a `Part.unit_cost`
  column: a vendor's pricing is sovereign, changes without telling us, and differs by
  quantity and by day. We record what we observed and when, never a mirror of their
  price book.

---

## B. Personas

### P1 — Name each persona and the one sentence they would use to describe their job here. Which is the highest-volume user?

| Persona | Their sentence |
| :--- | :--- |
| Requester | "I say what I need and when, then check whether it is coming." |
| Approver / floor manager | "I confirm the need is real, and I close it out when the person has the part." |
| **Buyer** | "I turn needs into orders, decide what each line answers, and place them." |
| Purchasing manager | "I approve orders before they go out, and I work the list of clusters that do not add up." |
| Receiver | "I record what was in the box, say which orders it answers, and inspect it." |
| Price authority | "I decide which observed price everyone else is shown." |

**The buyer is the highest-volume user** and the application is built around that: the
busiest, densest, most-optimized screens in the codebase are the PO create wizard and the
Edit & Linkage portal.

### P2 — For each persona, what do they do 50 times a day versus once a month?

| Persona | 50×/day | Once a month |
| :--- | :--- | :--- |
| Requester | read "where is my stuff" | raise a demand |
| Approver | approve a demand from a filtered list | reject one |
| Buyer | add lines, allocate demands, place orders | cancel an order, raise a demand's quantity to cover a bulk buy |
| Purchasing manager | approve/deny | work the imbalance list |
| Receiver | record lines, accept quantities | resolve a drifted/unallocated box |
| Price authority | — | verify observations, paste a quote grid |

Consequences that show up in the code: the demand list and the graph rollups are the hot
read paths, which is why graph quantities are **materialized columns rather than a
traversal**, why `linear_status` is copied down onto each demand so a list never joins,
why `purchased_qty` and `total_cost` are denormalized, and why `PartPricePolicy` is
required to be O(1) queries in the number of lines rendered.

### P3 — Capability × role matrix

C = create, R = read, U = update, D = delete/deactivate, — = none.

| Capability | Requester | Approver / floor mgr | Buyer | Purchasing mgr | Receiver |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Demand — create / edit own | C R U D | R | R | R | R |
| Demand — edit any in domain | — | C R U D | R | R | R |
| Demand — approve / reject | — | U | *(auto on link)* | — | — |
| Demand — cancel | U (own) | U | **—** | — | — |
| Demand — issuance state | — | U | — | — | — |
| Purchase order — create / edit | — | — | C R U | R | R |
| PO line — add / edit / cancel | — | — | C U D | R | R |
| Allocation to demand | — | — | C U D | R | R |
| PO — submit for approval | — | — | U | U | — |
| PO — approve / deny | — | — | **—** | U | — |
| PO — place / cancel | — | — | U | — | — |
| Shipment — create / receive | — | — | — | — | C |
| Shipment — advance status | — | — | — | — | U |
| Shipment line — accept | — | — | — | — | U |
| Arrival → PO line allocation | — | — | R | R | C U D |
| Price — record observation | — | — | C | C | — |
| Price — verify | — | — | *(needs `price_establish`)* | *(needs `price_establish`)* | — |
| Graph — read | R | R | R | R | R |
| Graph — resolve / flag / prioritize | — | U | U | U | — |

The permission codenames behind the matrix: `procurement.request`,
`procurement.demand_manage`, `procurement.buy`, `procurement.purchase_approve`,
`procurement.receive`, `procurement.price_establish`.

Two cells matter more than the rest: **a buyer never cancels a demand**, and **placing is
the buyer's act while approval is the manager's** — an earlier rule letting an
approve-only holder place an order was explicitly retired.

### P4 — Is any of this data restricted to a subset of users? Is restriction the default or the exception, and roughly what percentage?

**Restriction is the default, on 100% of rows.** Every demand, order, shipment, and price
observation carries a mandatory `domain` FK, and every list/search in the sector filters on
the viewer's accessible domains, snapshotted at login.

Two refinements the code is explicit about:

- **An empty domain list means the user sees nothing.** That is the intended reading, not
  a bug to paper over by skipping the filter.
- **Out-of-fence records are not hidden where they are referenced.** They render as plain
  text with no link through, on a page the user already has access to. A page that
  silently drops rows looks broken.

`GraphSummary` is the one row type that is not itself domain-owned — each *member* is —
so the visualizer does not fence the lookup, only the links.

---

## C. Business relationships

### R1 — For every link: one-to-many or many-to-many? What breaks the day it becomes many-to-many?

| Link | Cardinality |
| :--- | :--- |
| Demand → Part, Demand → Domain | many-to-one |
| Demand → journal rows | one-to-many, append-only |
| **Demand ↔ PO line** | **many-to-many, quantity-carrying** |
| PO → lines, PO → Vendor | one-to-many / many-to-one |
| PO → Shipments | one-to-many, **nullable** |
| Shipment → lines | one-to-many |
| **Shipment line ↔ PO line** | **many-to-many, quantity-carrying** |
| Any spine entity → GraphSummary | many-to-one |

Both many-to-many joins are the whole design, and both were arrived at by paying for the
alternative first:

- The legacy demand↔line manager capped allocation against the *line's* remaining quantity,
  which made splitting one demand across two POs impossible — the exact case the join
  exists for.
- The arrival↔line join replaced a single FK plus **row splitting**. Splitting made the
  physical record and the commercial mapping the same column, so recording a mapping meant
  destructively rewriting an arrived quantity.

The consequence of both, stated once and enforced everywhere: **you cannot attribute
arrival to a demand on a shared line.** Three demands on one line, sixty units arrive, the
units are fungible and nobody decided whose they were. That is why neither join table has a
`quantity_received` column, and why per-demand arrival is a *derived, sometimes-honest-only-
as-a-sentence* answer rather than a number.

### R2 — When a record is created, what else must come into existence automatically? For each: if it fails, does the original creation fail too?

| Creating | Also creates | Fails together? |
| :--- | :--- | :--- |
| PartDemand | four initializing journal rows (one per axis), a single-member GraphSummary | **yes** |
| PurchaseOrderLine / ShipmentLine | a single-member GraphSummary if unlinked | **yes** |
| ShipmentLine | an auto-allocation to the header PO's matching line | **no** — no match, or an ambiguous match, records the line **unallocated rather than refusing** |
| Either link row | a graph merge; on the demand side also a `purchased_qty` refresh and a default auto-approval | **yes** |
| Shipment | an `events.Event` thread, a drift-flag refresh, shipment_state propagation | Event **yes**; propagation refusals **no** |
| Placing a PO | one `ordered` price observation per line, propagation to every linked demand | observations **yes**; propagation refusals **no** |

The pattern: **structural side effects share the transaction; propagation to other
aggregates never fails the originating act.** A PO must not fail to be placed because one
of its demands is still unapproved — that is precisely the situation the auto-approve
opt-out exists to create. Skips are collected in a report and shown, never swallowed.

Two things the demand factory deliberately does **not** do: assign the domain (the caller
owns it, derived from the requester), and create the caller's own link row (it does not
know what a link row is, and never will).

### R3 — When a record is deleted or deactivated, what happens to everything pointing at it? Soft or hard?

| Record | Rule |
| :--- | :--- |
| PartDemand | **hard delete only while untouched** — no allocations, and no journal rows beyond the four initializers. Otherwise soft delete. Never a refusal |
| PO line | soft delete + JSON snapshot machine comment; **releases** its demand allocations, rolling those demands' purchasing state back to unset |
| PurchaseOrder | cancelled through status, never deleted. Propagates `cancelled` to purchasing; leaves shipment state alone — what arrived, arrived |
| Shipment | soft delete cascades to every active line |
| Link rows | soft delete, which may **split** the graph if it was the only bridge |
| PartDemandUpdate | never deleted, ever |

The deletion policy checks **only this app's own tables**. Cross-app protection is free:
consumer apps hold `PROTECT` FKs, so Django raises before the policy is consulted. This
replaced a legacy resolver that reached into other apps' model internals behind
`try/except ImportError`.

The **de-link vs release** distinction is load-bearing and the words are not
interchangeable: de-link means the buyer changed their mind (soft delete; purchasing state
does *not* roll back, because purchased means money moved and de-linking does not un-move
it), release means the order died (`is_active = False`, readable as history, freed for
re-allocation).

### R4 — When several constraints apply at once, must all pass or any pass? Write the truth table.

Every derived status in the graph is a **precedence chain — first match wins**, never
AND/OR. That was a deliberate choice and it is stated in three separate docstrings.

The one place a real truth table exists is auto-completion:

| `purchasing_state` past unset/denied | `issuance_state == issued` | → `demand_state` |
| :---: | :---: | :--- |
| no | no | unchanged |
| yes | no | unchanged |
| no | yes | unchanged |
| **yes** | **yes** | **completed** (system-generated) |

`shipment_state` is **not a term in this table**, deliberately — see M3.

And the three cross-axis gates are independent conditions, not a combined rule: Gate 1
applies only to the purchasing axis, Gate 2 only to cancellation, and Gate 3 is the
*absence* of a rule on issuance.

### R5 — At what moment is each rule enforced, and what happens when the check cannot be decided?

| Rule | Enforced at | Hard or soft |
| :--- | :--- | :--- |
| Axis transition legality | transition time, in the state machine | hard refusal, naming the next action |
| The three gates | transition time | hard refusal (Gate 1, 2); Gate 3 does not exist |
| Per-demand allocation cap | allocation write | **neither** — raises a choice the caller must resolve |
| Part match on either allocation | write time | hard |
| Arrival allocation ≤ line quantity | write time | **hard, and one of the few genuine blocks** |
| PO line quantity ≥ accepted | line edit | hard — not a policy, a fact |
| One active line per part per PO | line add | **soft warning** — it is about pricing simplicity, not integrity |
| Duplicate price observation | record | soft warning |
| Domain fence | every query | hard, silent |
| Permissions | at the entrypoint, never the template | hard, 403 |

**Undecidable cases fail open.** The demand and shipment state machines both allow-and-flag
when they meet an unknown dimension or a stored value that is not a key in their dict: the
transition goes through, the reason is written into the journal note, and
`flagged_for_review` is set. The reasoning is explicit — shipment status is very
high-volume and ideally machine-fed, so a guard that cannot decide must not stop the feed,
and a demand must never be trapped in a state the guard does not recognize.

The two exceptions that block are the two where permitting the write would record a claim
that is simply false: over-allocating a box, and shrinking a line below what physically
landed.

### R6 — Which app owns this? Which apps must remain completely ignorant of it, and what are the permitted seams?

**`app/procurement/` owns** demands, orders, shipments, vendors, prices, and the graph.

**Permitted seams, and there are only these:**

| Seam | Direction | Shape |
| :--- | :--- | :--- |
| Consumer apps → PartDemand | inward | their own link table with a `PROTECT` FK to `PartDemand.id` |
| Inventory → procurement | inward | `PartDemandContext.record_issuance(net_qty)` — a caller-supplied number |
| Inventory → shipments | inward | a thin mirror surface reading procurement's rows and writing **only** through `ShipmentContext` verbs |
| procurement → events | outward | `Event` / activity threads on POs and shipments |
| procurement → parts, administration | outward | `Part` and `Domain` FKs |

**Procurement holds no FK into inventory, maintenance, or dispatching, and may not import
them.** The stated cost of that: if anything ever creates a `PartIssue` outside
`inventory.PartIssuanceOrchestrator`, `issued_qty` drifts and nothing in procurement can
detect it. The orchestrator is the only supported write path.

---

## D. Data model

### M1 — Glossary: every domain noun, and what it collides with

| Noun | Means here | Collides with |
| :--- | :--- | :--- |
| **Demand** | one person's stated need for a part | "demand" in forecasting/economics — this is not a forecast |
| **Allocation** | a quantity-carrying claim | used for **two different tables**: demand↔PO-line and arrival↔PO-line. Always say which |
| **Purchased** | money moved for this demand *somewhere* | not per-PO, and not "received" |
| **Shipment** | what the vendor sent | the legacy `ArrivalHeader`, which conflated "a shipment" with "the receiving transaction" |
| **Shipment line** | one packing-slip line, unchanging | legacy `ArrivalLine`, which was rewritten to record mappings |
| **Accepted** | inspected and intact | **not** stocked. Stocked is intake's word |
| **Domain** | the ownership/data fence | renamed project-wide from `OwnershipGroup` |
| **Graph** | one connected cluster of demands, lines, and arrivals | graph-as-chart. The visualizer draws one, but the noun is the cluster |
| **Status** | on GraphSummary, the **legacy** label | `linear_status` supersedes it. Both exist |
| **Issued** | handed to the requester | not "shipped", not "delivered" |
| **Source module** | display convenience | **not** an origin record |
| **Vendor** | commercial supplier | **not** a manufacturer, and unrelated to parts |
| **Price** | one observation, on a date | not a part attribute |

House conventions hold throughout: singular `db_table` names, the
`Struct`/`Context`/`Factory`/`Manager`/`Handler`/`Policy`/`Validator`/`StateMachine`/
`Narrator`/`Adaptor` suffix vocabulary, and `*_guard.py`.

### M2 — Where two concepts overlap, which is concrete/primary and which is the restricted view?

Three pairs, all resolved the same way — **the physical or committing record is primary,
and the commercial interpretation of it is a separate, appendable row:**

1. **`PurchaseOrderDemandLink` is a peer join, not a restricted view of either side.** It
   carries attributes belonging to the pairing and to neither side alone.
2. **`ShipmentLine` is primary; `PurchaseOrderShipmentLink` is the interpretation.** The
   line is what the packing slip said and never changes; which orders it answers is a
   many-to-many mapping beside it.
3. **`PartDemandStruct` is primary and `PartDemandDetailStruct` extends it**, so the
   detail page is not a second read path — every field the list and edit views read is
   available through `.base`.

The order line's relationship to its header is the same idea inverted: **a line has no
status of its own**, because a line's state *is* its header's status. The legacy line
carried a cascaded copy, so header, line, and demand each held part of the same fact and
could disagree.

### M3 — Is this variation a type label, a set of capability flags, or a distinct class? Can a caller construct an invalid combination?

The most consequential answer in this kit. **Demand state is four independent enums, not
one enum and not a set of booleans.**

They are genuinely orthogonal — approval, funding, physical location, hand-off — and they
move at different times, in different directions, driven by different people and systems.
Combinations that look wrong are real: *approved + funding denied + delivered to depot +
not issued* happens when material arrives against a denied request.

Two constructions the model makes impossible or refuses:

- Writing an axis column without its journal row: there is **no code path** that does it.
- Skipping a stage: the dicts allow only declared moves, per axis.

One deliberate near-miss: `PurchasingState` and `PurchaseOrderApprovalState` both use
**blank as a real, meaningful value** ("no decision yet" / "unsubmitted") rather than as a
member of the enum. That is documented in both enums, because a reader will otherwise treat
it as missing data.

The graph statuses are the same shape one level up: **three independent axes plus a
separate error key**, never one combined health label — because "where in the pipeline" and
"does the arithmetic balance" are different questions and a single column would have to
lie about one of them.

### M4 — Is this attribute intrinsic to what the thing *is*, or to *where it is used*?

| Attribute | Verdict |
| :--- | :--- |
| `DemandPriority` | **intrinsic to the need** — lives on the demand |
| `GraphSummary.priority` | separate, and about the underlying *work*, set by a human |
| `quantity_allocated` on either link | intrinsic to **the pairing** — belongs on the join, not either side |
| `quantity_accepted` | intrinsic to the **arriving line**, because inspection happens to the physical line as a whole |
| `unit_cost_source` / `confidence` / `asserted_at` | intrinsic to **this line's price assertion**, not to the part |
| `mixed_po_assignments` | derived, about the shipment as a whole |
| `is_active` on the demand link | about the pairing's **fate**, distinct from soft delete |

The two conspicuous absences are the same question answered "neither": there is no
`quantity_received` on the demand link and no `quantity_accepted` on the arrival link,
because on a shared line the per-pairing number **does not exist**.

### M5 — How do users version and identify this? Can you trust their naming convention?

Three identifier pairs, ours and theirs, never conflated:

| Ours | Theirs |
| :--- | :--- |
| `Shipment.shipment_number` (generated `SHP-<date>-<hex>`) | `Shipment.shipment_id` — what is printed on the label |
| `PurchaseOrder.po_number` | `vendor_po_id` |
| `PurchaseOrderLine.line_number` | — |

**Their identifier is the one a receiver searches by**, because they have a box in hand and
read the label — so `shipment_id` is a first-class filter on the receiving queue even
though it is untrusted, non-unique, free text.

"Current" is not a concept in this app: prices are observations (newest and
newest-*verified* are two different answers, resolved separately), the journal is
append-only, and rejection loops back onto the **same demand row** rather than creating a
version.

### M6 — Which entities carry free-form human content?

| Entity | Carries |
| :--- | :--- |
| PartDemand | `notes`, plus a `notes` field on **every journal row** |
| PurchaseOrder | `notes`, an `Event` thread, and machine audit comments with JSON snapshots |
| PurchaseOrderLine | `notes` |
| Both link tables | `notes` |
| Shipment | `notes`, an `Event` thread, machine audit comments |
| ShipmentLine | `rejection_notes` |
| PartPriceObservation | `notes` |

Notes stay **optional everywhere, including on rejection** — a mandatory reason field
would be filled with "n/a" within a week. The audit obligation is met by the machine
snapshot instead, which nobody can degrade.

---

## E. Migration defaults

### X1 — What is today's behavior, and does the new default reproduce it exactly?

Not applicable in the usual sense — this kit documents rather than changes. But the
application itself is a rewrite of a legacy procurement module, and it was a **clean cut
with no shims**. The specific legacy behaviours it deliberately does not reproduce:

| Legacy | Replaced by |
| :--- | :--- |
| `ArrivalHeader`/`ArrivalLine` conflating shipment and receiving transaction | `Shipment` + `ShipmentLine`, with receipt attributable to demands |
| `ArrivalLine.quantity_available_for_linking` | the unallocated remainder, derived |
| Line status cascaded from the PO header | no line status at all |
| `is_fake_for_inventory_adjustments` on lines | nothing |
| Allocation capped against the line's remaining quantity | capped per demand |
| `line_total` property issuing a query per line | one annotated aggregate |
| `DemandOriginResolver` importing other apps behind `try/except` | inward-only `PROTECT` FKs |
| Audit columns on one demand dimension only | one uniform journal across all four |
| Client-only selection in the linkage portal | `?line_id=` round-tripping through the URL |
| Splitting shipment lines to record a mapping | quantity-carrying allocation rows |
| On-demand graph traversal (`PoDemandAssociationGraphResolver`) | materialized `GraphSummary` + `graph_id` FKs |

---

## Open items

Recorded because the code itself marks them open, not because this kit is unsure.

1. **Per-domain price-establish authority.** `procurement.price_establish` is a single
   global permission; scoping it per domain is a marked TODO at the guard's call site.
2. **The completed-demand / live-graph divergence.** A locked `completed` demand can read
   `delivered` while its parent graph reads something earlier, after a merge or a later
   arrival. Accepted; revisit if users report confusion.
3. **`issued_qty` drift.** Undetectable from inside procurement if anything writes a
   `PartIssue` outside the orchestrator.
4. **Binary allocation.** The per-demand cap currently requires allocating the *entire*
   outstanding amount or nothing. Partial allocation against one demand is not offered;
   whether that is permanent or a simplification is not recorded anywhere in the code.
5. **`GraphSummaryStatus` (`status`) is live legacy.** Superseded by `linear_status` but
   still written by `recalculate()` and still read by narrators and the graph detail
   template. Two columns answering nearly the same question is a known cost.
6. **`intake_qty_recorded`** on GraphSummary is reserved for the Inventory build and is
   currently always zero.
7. **The process-template workflow engine** — per-organization configurable approval
   flows — was deferred whole to tech debt.
