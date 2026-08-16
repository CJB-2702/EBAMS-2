---
okf_version: "0.1"
type: "Kit Document"
title: "The Purchasing System"
description: "How purchase orders behave: two independent axes, the allocation policy and its cap, propagation down to demands, line editing after placement, and cost."
tags: [starter-kit, procurement, purchase-orders, policy, okf]
context_tier: 2
personas: [backend, business]
---

# The Purchasing System

**A PurchaseOrder is a commercial document placed with a vendor.** It is a *peer* of
PartDemand, never nested under it: a PO can exist with zero linked demands, which is how
proactive and bulk restocking is modeled.

---

## 1. Two axes

Like a demand, an order answers two different questions with two independent columns.

### `status` — where is this order in the world?

```
draft ──▶ placed ──▶ partially_received ──▶ received
  │          │              │
  └──────────┴──────────────┴──▶ cancelled
```

- `partially_received` can still be cancelled: a vendor discontinuing the rest of an
  order after a part shipment is ordinary.
- **A received PO cannot be cancelled.** The goods are here.
- `partially_received` is **computed, not chosen** — it follows from any accepted
  shipment quantity existing against the PO at all. Only the terminal close-out is human.

### `approval_state` — has a manager blessed this?

```
"" (unsubmitted) ──▶ pending_approval ──▶ approved
                            │      ▲
                            ▼      │
                         denied ───┘
                            │
       cancelled ◀──────────┴────── (from either non-terminal state)
```

- Blank is a real value meaning "not yet submitted", following the demand-side
  precedent.
- **Approved is not revocable through this axis.** An approved order is cancelled
  through `status` instead, never demoted back through this one.
- Submitting for approval is **always available, never automatic**. There are no cost
  thresholds in this build.
- **Self-approval is legal** — one person may hold both `buy` and `purchase_approve` —
  and the actor is always recorded.

The two axes are separate for the same reason the demand carries four: "has a manager
blessed this" and "where is this order in the world" are different questions.

---

## 2. Allocation — the load-bearing idea

`PurchaseOrderDemandLink` claims some of an order line's units as answering a specific
demand. Everything difficult about purchasing lives here.

### The cap is per demand, never per line

A demand's outstanding need is `quantity_requested - purchased_qty`, and the write path
enforces that as a real cap.

**A PO line is always free to carry more ordered quantity than the sum of its
allocations.** That covers three legitimate cases at once: proactive/bulk restocking, a
vendor minimum order quantity, and reserve for a demand that does not exist yet.

The legacy manager had this backwards — it capped against the *line's* remaining
quantity and silently allocated the demand's full quantity with no partial option, which
made splitting one demand across two POs impossible. That is the exact case the
many-to-many join exists for.

### Validation on every allocation

| Check | Hard or soft |
| :--- | :--- |
| Quantity greater than zero | hard |
| **Part match** — the demand's part must equal the line's part | hard. Enforced in the guard rather than the database because it spans three tables |
| One allocation per pairing (edit the existing row, never add a second) | hard |
| The per-demand cap | special — see below |

### `AllocationCapExceeded` is a choice, not a failure

Exceeding the cap raises an exception carrying the numbers needed to present an explicit
choice: **raise the demand's `quantity_requested` to cover the allocation**, or **leave
the excess unallocated on the PO line**. Raising the request to make a bulk buy fit is
falsifying what somebody asked for, so the UI carries a strong warning; the manager
method is only the mechanical half.

The current cap is additionally **binary**: the allocated quantity must equal the full
outstanding amount, or nothing is allocated. Partial allocation against a single demand
is not offered — a buyer who cannot cover the whole outstanding need purchases more
later.

### Auto-approval on link

Creating an allocation **auto-promotes the demand to `approved` by default**. This is
not a shortcut around Gate 1 — Gate 1 still blocks `purchasing_state` from leaving unset
without approval. What changes is how approval is usually *reached*: purchasing
routinely acts before an approver signs off, directed through outside channels, and
hard-blocking the buyer would stop daily work waiting on a step the organization already
decided informally.

A buyer who wants the strict approve-first process for a given item passes
`auto_approve=False`; Gate 1 then holds and the purchasing axis waits for an approver.

### De-link versus release

The words are not interchangeable:

- **de-link** — the buyer changed their mind about the pairing. Soft delete.
  `purchasing_state` does **not** roll backward: purchased means money moved, and
  de-linking does not un-move it.
- **release** — the PO was cancelled and the vendor is not shipping. `is_active = False`,
  readable as history. `purchased_qty` recomputes across active rows only, freeing the
  buyer to re-allocate.

**Cancelling a whole line is the one case that rolls `purchasing_state` backward** to
unset, because there the thing that was going to spend the money is gone.

---

## 3. Propagation — what placing an order does to demands

| PO status | → `purchasing_state` | → `shipment_state` |
| :--- | :--- | :--- |
| `draft` | stays unset | `request_not_sent` |
| `placed` | → `purchased` | → `request_received_by_vendor` |
| `partially_received` | unchanged | unchanged (shipments drive it) |
| `received` | unchanged | → `delivered_to_local` (explicit close-out) |
| `cancelled` | → `cancelled` | unchanged — what arrived, arrived |

Every write goes through `PartDemandStateManager.transition()` with
`is_system_generated=True` and the actor set to whoever moved the PO. The handler never
assigns a snapshot column directly.

A demand linked to more than one PO takes the propagation from whichever PO moved.
*Purchased* means money moved for this demand somewhere; it is not a per-PO fact.

The `request_received_by_vendor` move is an **optimistic default**. The middle stretch of
the chain (production → prepared to ship → shipped) is advanced manually as vendor
updates arrive; nothing computes it.

**Refusals never fail the workflow.** A demand still unapproved (the buyer opted out of
auto-approve) will not move, and propagation skips it and *reports* the skip rather than
swallowing it. The PO is placed; that demand's purchasing axis waits for its approver —
exactly the case the opt-out exists to create.

**Marking received is never a quantity match.** An order that received 6 of a purchased
10 can be closed out, because that is what happened and the remaining 4 are not coming.

---

## 4. Lines stay editable after placement

Vendors substitute, short-ship, and re-price after an order goes out, and the record
should say what actually happened rather than what was originally typed.

The permissiveness is paid for in **audit rather than restriction**: every mutation on a
placed-or-later PO posts a machine comment carrying a JSON snapshot of the row as it
stood before the change — on edits and deletions alike.

Editable fields: `quantity_ordered`, `unit_cost`, `expected_delivery_date`, `notes`,
`part_id`, and the three unit-cost provenance fields.

**The one hard stop is the quantity floor.** A line's `quantity_ordered` cannot drop
below what has already been accepted against it in shipments. That is not a policy — a
number below what physically landed would simply be false. Because acceptance is derived
by allocation share, on a multi-allocation arriving line this floor can sit at a
fractional value; that is the honest number and the right one to guard with.

**Duplicate parts are a soft warning.** Adding a second active line for a part already on
the order tells the buyer and points at the existing line, but does not refuse. The rule
is about pricing simplicity (one part, one price, one line), not integrity — so relaxing
it later for split delivery dates or tiered pricing should be a guard change, not a
migration. A duplicate that gets through degrades gracefully: arriving shipment lines
land unassigned rather than mis-assigned.

**Cancelling a line** is a soft delete plus the audit snapshot, not a status value. It
releases the line's demand allocations, which returns those demands' purchasing state to
unset.

---

## 5. Cost

`PurchaseOrder.total_cost` is denormalized and recomputed on every line write by its own
manager — the only writer:

```
total_cost = Σ(quantity_ordered × unit_cost over non-deleted lines)
           + shipping_cost + tax_amount + other_amount
```

Line totals are annotated in **one query**, never summed in Python over per-line property
calls — the legacy model's `line_total` property issued a query per line on access.

---

## 6. Placing an order is also a price fact

Placing a PO writes one `ordered` price observation per line automatically. It is
self-maintaining because it costs nothing beyond work the buyer already did. See
[pricing_system.md](pricing_system.md).

---

## 7. Events

Each PO owns an `events.Event` thread carrying its narrated history and the machine
audit snapshots. Status changes additionally emit through a small in-app event
emitter/listener registry (`presentation_layer/tools/po_events/`) so other surfaces can
react without the context class knowing about them.

---

## 8. Permissions

| Codename | Grants |
| :--- | :--- |
| `procurement.buy` | PO create, header/line editing, allocation and de-linking, submit-for-approval, place, cancel |
| `procurement.purchase_approve` | approve or deny an order, **and nothing else** |

Placing is the buyer's act; approval is the manager's. An earlier rule letting an
approve-only holder place an order has been retired. Gates are enforced at the
entrypoint, never left to a template.
