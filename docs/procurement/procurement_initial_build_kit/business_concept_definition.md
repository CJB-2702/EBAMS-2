---
okf_version: "0.1"
type: "Kit Document"
title: "Business Concept Definition — Procurement"
description: "What the procurement application does for the people who use it: capabilities, personas, and the operational workflows behind each one. No tables, no classes."
tags: [starter-kit, procurement, business, okf]
context_tier: 1
personas: [business]
---

# Business Concept Definition — Procurement

The one-sentence version: **procurement lets an organization state a material need,
turn it into money spent with a vendor, watch the material arrive, and see at any
moment where the gap is between what was asked for, what was bought, and what
actually turned up.**

Everything below is a consequence of that sentence.

---

## The problem it solves

Four different people touch the same physical part, and each of them holds a
different fact about it:

- A mechanic knows a pump is needed by Friday.
- A buyer knows an order was cut to a vendor last Tuesday for ten of them.
- A receiver knows a box arrived this morning with eight in it, one dented.
- A storeman knows four were handed to the mechanic and the rest are on a shelf.

Nobody holds all four facts. The failure the application exists to prevent is the
ordinary one: the mechanic chases the buyer, the buyer chases the vendor, the
receiver has a box with a packing slip that matches no order they can find, and
nobody notices that only eight of ten arrived until the job is halted.

The system records each of those four facts **where and when it is actually known**,
by the person who knows it, and then does the arithmetic between them automatically.

---

## Capability 1 — Raising and tracking a need

Anyone with a genuine requirement records what part they need, how many, by when, and
how urgently. The request is not a purchase; it is a statement that something is
required. It is fenced to a *domain* — the organizational unit meant to receive the
part — so it is visible to the people responsible for fulfilling it and nobody else.

From then on, that one need carries four **independent** answers, because in real
operations they genuinely move at different times and in different directions:

1. **Is the need real and authorized?** Projected → Required → Approved (or Rejected,
   which loops back to Required on resubmission, or Cancelled).
2. **Has money been cleared to move?** Nothing decided → Approved → Purchased (or
   Denied, or Cancelled).
3. **Where is the material physically?** Nothing sent → vendor acknowledged → in
   production → ready to ship → shipped → delivered to a depot → delivered locally.
4. **Has it reached the person who asked?** Not issued → partially issued → issued,
   plus two states for material that is out on loan or physically moved before the
   books caught up.

Every movement on any of those four is written to a permanent journal with who moved
it, when, from what, to what, and whether the system moved it automatically. That
journal exists because the previous system audited one of these dimensions properly
and the other three not at all, so there was no record of who marked something issued
or why.

A fifth, simpler label — the **pipeline status** — is carried alongside for people who
do not want to read four axes: *nothing committed / allocated but not bought / bought
but not arrived / partly delivered / delivered*.

**Business rule that surprises people:** a need is marked complete automatically when
money has moved *and* the material reached the requester. Physical shipment tracking
is deliberately excluded from that test, because shipment tracking is a high-volume
background process nobody in the completion path touches, and blocking completion on
it would leave every finished request looking unfinished.

---

## Capability 2 — Buying

A buyer builds a purchase order against a vendor: a header with dates and costs, and
one line per part with a quantity and a unit price. The order is built entirely as a
draft in the buyer's own session — nothing exists in the shared record until they
submit it, so a half-built order never appears in anyone else's list.

The buyer then **claims** parts of each order line as answering specific needs. This
claim — the allocation — is the load-bearing idea in the whole application:

- One need can be split across several orders.
- One order line can answer several needs at once.
- An order line is free to buy far more than anyone asked for. Bulk restocking,
  vendor minimum order quantities, and buying ahead for needs that do not exist yet
  are all normal, and an order with **zero** linked needs is a perfectly healthy
  record.

Claiming a need against a line also approves that need by default, because in real
purchasing departments the authorization has usually happened through a phone call
before the buyer acts, and hard-blocking the buyer on a checkbox stops daily work. A
buyer who wants the strict approve-first process for a particular item can opt out,
and then the need genuinely waits for an approver.

Orders carry a **separate approval track** from their lifecycle: "has a manager
blessed this" and "where is this order in the world" are different questions. An order
moves Unsubmitted → Pending Approval → Approved on one axis, and Draft → Placed →
Partially Received → Received on the other. Placing an order is the moment money is
declared to have moved, and it pushes that fact down to every need the order answers.

Orders stay editable after they are placed, because vendors substitute parts,
short-ship, and re-price after the fact, and the record should say what happened
rather than what was originally typed. The permissiveness is paid for in audit: every
change to a placed order posts a machine comment carrying a snapshot of the row as it
stood beforehand.

---

## Capability 3 — Receiving

A box arrives. The receiver records **what the packing slip says** — part, quantity —
and that record never changes afterward to accommodate paperwork.

Two entry points exist because two situations exist:

- **The order is known.** The receiver picks the purchase order, lists what came in,
  and each line is automatically pointed at the matching order line. The common case —
  one vendor, one order, one box — takes no per-line work at all.
- **The order is not known.** A box turned up and the paperwork has not. It is
  recorded anyway, against the receiving organization, with nothing pointed at any
  order. The unassigned quantity sits there as a real, ordinary state — "this much
  arrived and nobody has said yet which order it answers" — until somebody resolves it.

Separately, a buyer can plan a shipment *forward* from a vendor's shipping
confirmation: laying out which order lines are expected in which boxes before anything
physically arrives.

Pointing arrived material at order lines is a quantity-carrying claim, exactly like
the demand-side allocation, so one physical line can answer several orders — including
orders from different purchase orders to the same vendor, which is flagged but never
blocked.

**Inspection** is the receiver's second verb: how many of the arrived units were
actually accepted. Accepting more than shipped is legal, because vendors over-ship and
the honest record says so. An uninspected line and a line inspected-and-wholly-rejected
are deliberately different facts, never both recorded as zero.

**Where the application stops:** acceptance. Nothing here asks where you put it.

---

## Capability 4 — Knowing what a part costs

Prices are recorded as **observations**, never as a field on a part. Each observation
says: this vendor, this part, this unit cost, this quantity, on this date, learned this
way (a quote, a catalog, a manual entry, an order we placed, an invoice we paid), with
a stated confidence.

Placing a purchase order automatically records one observation per line, which makes
the price history self-maintaining at no cost to anyone — the buyer already typed the
number.

A second authority level exists on top: recording an observation is an ordinary buying
activity, but **verifying** one — making it the number everyone else is shown — is a
separate permission. There is also a bulk paste-a-grid entry path for a fresh vendor
quote sheet, and a backstop list of parts nobody has ever priced.

---

## Capability 5 — Seeing the whole picture: clusters

This is the capability that does not exist in the systems it replaces.

Because needs, order lines, and arriving lines are all connected many-to-many, the real
unit of "one procurement situation" is not any single record — it is the whole
connected cluster of them. Three needs answered by two order lines filled by four boxes
is *one situation*, and the only useful questions are asked of the whole thing at once:

- How much was asked for, committed, bought, shipped, and accepted?
- Is any of the demand not yet covered by an order?
- Did what we ordered actually turn up?
- Where in the pipeline is this, overall?

The system maintains those clusters automatically. A cluster is never created by
anybody: it forms when a record is created, merges when two records are linked, splits
when the link holding it together is removed, and dies when its members leave. It has a
visualizer page showing every member and every connection as a diagram, plus filtered
lists for the two questions a purchasing manager actually asks — *what have we not
committed to an order*, and *what did we not receive*.

On top of the arithmetic sits a **human ruling**, because arithmetic alone produces a
list nobody can ever work down. A vendor who over-ships 12 against a demand for 10
leaves a cluster permanently unbalanced, and that is fine — somebody marks it
*accepted as is* and it stops being noise. The distinction between "this got fixed"
and "this is permanently lopsided and that is correct" is preserved deliberately.

---

## Personas

| Persona | How they would describe their job here | Volume |
| :--- | :--- | :--- |
| **Requester** | "I say what I need and when I need it, and I check whether it is coming." | High — many small writes, then repeated reads |
| **Approver / floor manager** | "I confirm the need is real, and I close it out when the person has the part." Can act on any need in their domain, not only their own. | Medium |
| **Buyer** | "I turn needs into orders with vendors, decide what each line answers, and place them." | **Highest** — the application's busiest screens are theirs |
| **Purchasing manager** | "I approve or deny orders before they go out, and I work the list of clusters that do not add up." | Low volume, high consequence |
| **Receiver** | "I record what was in the box, say which orders it answers, and inspect it." | High during arrivals, bursty |
| **Price authority** | "I decide which observed price becomes the number everyone is shown." | Low |

Every one of these people is fenced to their own **domains**. A record outside a user's
domains is never listed and never reachable — but where it is referenced from a page
they can already see, it renders as plain text without a link, rather than vanishing
and making the page look broken.

---

## What this is explicitly not

- **Not an inventory system.** No stock levels, no bins, no put-away, no storerooms.
- **Not an accounts-payable system.** Invoices are a price observation source, not a
  tracked document. Nothing here pays anybody.
- **Not a vendor-management or sourcing system.** A vendor is a name, a code, and a
  website. There is no rating, no contract, no relationship to parts or manufacturing.
- **Not a workflow engine.** Legal transitions are written down flat, per axis, in one
  readable place. Configurable per-organization approval templates were considered and
  deferred whole.
- **Not a task list.** Several of the imbalance states are descriptive and will never
  clear on their own — every bulk restock produces one permanently. That is correct.
