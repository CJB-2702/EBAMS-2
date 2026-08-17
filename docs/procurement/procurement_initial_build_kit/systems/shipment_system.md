---
okf_version: "0.1"
type: "Kit Document"
title: "The Shipment System"
description: "How arrivals behave: the physical record, allocation to order lines, the one place a quantity is divided, acceptance, propagation back to demands, and the intake boundary."
tags: [starter-kit, procurement, shipments, receiving, policy, okf]
context_tier: 2
personas: [backend, business]
---

# The Shipment System

**A Shipment is what the vendor actually shipped.** A ShipmentLine is *one physical line
item, exactly as the packing slip described it*, and it never changes to accommodate
paperwork.

Shipments live in procurement rather than inventory because a shipment in transit is
**pre-possession**. Nothing about a shipment references a storeroom, a bin, or a stock
level.

---

## 1. The intake boundary

This is the hardest line in the application and it is worth stating before anything else.

**The last verb procurement owns is `accept`.** Accepting into stock, put-away, bin
assignment, and stock levels are the later Inventory build. If a field asking "where did
you put it" ever appears in this sector, it belongs to a different kit.

The boundary is exactly `ShipmentLine.quantity_accepted`.

The legacy application merged the two concepts into `ArrivalHeader`/`ArrivalLine`, which
was simultaneously "a shipment that arrived" and "the receiving transaction" — and that
conflation is why receipts there could only ever be attributed to PO lines, never to
demands.

---

## 2. Status

```
awaiting_shipment ──▶ shipped ──▶ delivered_to_depot ──▶ delivered_to_local ──▶ accepted
        │      ▲          │  ▲             │
        ▼      │          ▼  │             │
   backordered─┘        lost─┘             │
        │                 │                │
        └────────┬────────┴────────────────┴──▶ cancelled
```

- `backordered` re-enters at `shipped` — backordered items ship in pieces.
- `lost` re-enters at `shipped` — a shipment found after being written off.
- **`accepted` means inspected and intact. It does not mean stocked**; stocked is
  intake's word, and intake is not built.

The guard **fails open**, like the demand axes: shipment status is very high volume and
ideally machine-fed, so a guard that cannot decide must not stop the feed.

---

## 3. Two ways in, plus one forward-planning path

| Path | Situation | What happens |
| :--- | :--- | :--- |
| **Create against a PO** | The order is known | Lines auto-allocate to the header PO's matching line by part. One vendor, one order, one box takes zero per-line work |
| **Reactive receive** | A box arrived, the paperwork has not | `purchase_order` is null, `domain` is mandatory. Lines land with **no allocations at all** — the whole arrived quantity sits as unallocated remainder |
| **Basic Shipment Manager** | A buyer planning expected boxes from a vendor's shipping confirmation | Forward-looking, PO-scoped, session-only until one all-or-nothing submit |

A shipment is never free of a domain. When a PO is supplied its domain is copied; when
one is not, an explicit domain is required — otherwise the record would be ownerless.

Every shipment gets an `events.Event` thread at creation.

### The auto-allocation is a default, not a binding

Resolution is by part: find the header PO's *single* active line for this part. If there
is no match (a vendor substitution, a wrong shipment, a bonus item) **or more than one**
(the one-line-per-part rule was breached), the line is recorded **unallocated rather than
refused**. The soft rule degrading gracefully, by design.

Allocations are editable afterward, and editing them is expected — one physical box
routinely holds items from several orders to the same vendor.

---

## 4. Allocation to order lines

`PurchaseOrderShipmentLink` points some or all of an arriving line at a PO line. One verb
— `allocate` — takes a quantity, so the full and partial cases are the same code path
rather than two that drift. Un-pointing is `deallocate`, a soft delete of the link, and
it **never touches the arriving line's own quantity**.

This reversed an earlier design where `ShipmentLine` carried a single `purchase_order_line`
FK and a line answering several orders was handled by **splitting it into sibling rows**.
That made the physical record and the commercial mapping the same column, so recording a
mapping meant destructively rewriting an arrived quantity. Now the shipment line stays
exactly as the packing slip described it, forever, and every commercial decision about it
is an appendable, soft-deletable row beside it.

### Rules

| Rule | Behaviour |
| :--- | :--- |
| Part must match between arriving line and PO line | hard refusal |
| Quantity greater than zero | hard refusal |
| **Sum of a line's active allocations ≤ the line's own quantity** | **hard refusal** |
| Allocating across POs (a line on a different order than the header) | **legal** — flagged, never blocked |

The allocation cap is one of the few things in this application that genuinely blocks,
and the reason is stated in the guard: over-allocation is not a business event a manager
needs to see, it is a claim that more of a box was assigned than was in the box.
Over-*receipt* against a PO line is a different thing entirely and stays legal and merely
visible — vendors do over-ship.

### The unallocated remainder

`line.quantity − Σ active allocations` is **never a discrepancy**. It is a real and
ordinary business state: *this much arrived and nobody has said which order it answers
yet.* That state existed under the old design too, as a null FK; the only thing that
changed is that it is now a quantity rather than a whole-row boolean.

### Drift

`Shipment.mixed_po_assignments` is set when any allocation points at a line on a different
PO than the header. It **blocks nothing**. It exists so the condition is queryable rather
than puzzled over, and the shipment list exposes it as a first-class filter because it is
a real standing job.

---

## 5. Acceptance, and the one division in the application

Inspection is physical and happens **once, per arriving line**: 120 turned up, 114 passed.

`quantity_accepted` may be less than, equal to, or **greater than** the shipped quantity.
Only `>= 0` is enforced. **Null is not zero** — an uninspected line and a line
inspected-and-wholly-rejected are different facts, so the accept input is never defaulted
to 0 and the templates render the two states differently.

Two questions get asked of a PO line once shipments arrive, and they have very different
epistemic status:

| Question | Answer |
| :--- | :--- |
| How much has been **shipped** against this line? | **Exact.** Sum of `quantity_allocated` on active allocations. A human decided each of those numbers deliberately |
| How much has been **accepted** against this line? | **Derived by proration.** If an arriving line allocated 100/20 across two PO lines was inspected as a whole, nobody inspected "the hundred" separately |

Proration by allocation share is confined to exactly one module —
`domain_structs/arrival_allocation.py` — so it stays findable. A line with **one**
allocation (overwhelmingly the common case) takes its accepted quantity whole and is not
prorated at all. An uninspected line contributes *nothing*, which is different from
contributing zero, and the unallocated remainder never receives a share.

### Why this is allowed here and forbidden on the demand side

The demand side forbids exactly this kind of division, and that prohibition stands. The
difference:

- On the **demand** side, an allocation is a *claim on future fungible units*. Nobody has
  decided whose units are whose; the division has no referent at all, so inventing one
  manufactures a fact.
- **Here**, the allocation is a *recording of a physical mapping a receiver already made*.
  The division has a referent; only the acceptance shortfall within it is unobserved, and
  proportional spreading is the one treatment that is symmetric across allocations,
  order-independent, and sums back to the physical total exactly.

That is a real weakening, not a free pass. If a business later needs exact per-order-line
acceptance, the answer is a per-allocation inspection column, not a better formula.

---

## 6. Propagation back to demands

Shipment status drives each linked demand's `shipment_state`:

| Shipment status | → demand `shipment_state` |
| :--- | :--- |
| `awaiting_shipment` | `vendor_prepared_to_ship` |
| `shipped` | `shipped` |
| `delivered_to_depot` | `delivered_to_depot` |
| `delivered_to_local` | `delivered_to_local` |
| `lost` | `lost` |
| `accepted` | **no change** — acceptance is inspection, not movement |

The path is `shipment line → PurchaseOrderShipmentLink → PO line → PurchaseOrderDemandLink
→ demand`, and every write goes through the state manager with `is_system_generated=True`.

**A demand behind several shipments takes the LEAST advanced status among them.**
Backordered items ship in pieces, so a demand's line can have arriving lines in several
shipments at different statuses. A demand with one box delivered and one still in transit
has *not* been delivered; taking the most advanced would report it complete while material
is still moving. `lost` sorts lowest of all — a lost box is the least progress there is.

Accepting quantity against a PO also nudges that PO to `partially_received`, computed from
any accepted quantity existing at all.

---

## 7. Control-layer surface

`ShipmentContext(shipment_id)`:

| Verb | Notes |
| :--- | :--- |
| `advance(to_status)` | guarded, then propagates to demands |
| `update_header(...)` | header fields only — **status is not here**; advancing is its own verb |
| `add_line` / `delete_line` | soft delete for the latter |
| `accept_line` | records `quantity_accepted` and rejection notes |
| `assign_line` | allocate some or all of an arriving line to a PO line; merges graphs |
| `release_allocation` | soft-delete a link; may split a graph |
| `attach_purchase_order` | link a PO to a shipment received without one, running auto-allocation against real lines |
| `delete` | soft-deletes the shipment **and every active line** |

Mutations on a shipment past a certain point require an audit comment, which is posted
along with a JSON snapshot of the pre-change state — the same discipline as PO lines.

---

## 8. The Inventory mirror

`app/inventory/` carries a thin duplicate **view/edit** surface over procurement's own
`Shipment`/`ShipmentLine` rows. There is no `inventory.Shipment` model: every read is a
plain queryset against procurement's models, and every write goes through procurement's
own `ShipmentContext` verbs — never a raw `.save()` duplicating logic those verbs own.

Deliberately narrower than procurement's own surface:

- **No create and no receive** — recording a brand-new shipment stays procurement's job.
- **No PO attach, no line reassignment, no line or shipment deletion** — order linkage is
  not an inventory concern.

Inventory's version keeps exactly the two verbs that belong to the physical/received side:
`advance_status` and `accept_line`.

---

## 9. Permissions

`procurement.receive` gates both creation paths, status advance, line acceptance, and
every mutation on the shipment edit page. Enforced at the entrypoint, never in a template.
Every list is domain-scoped.
