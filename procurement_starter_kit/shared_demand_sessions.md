---
okf_version: "0.1"
type: "Reference"
title: "Shared Demand Sessions — when 'how much of my demand arrived' has no answer"
description: "The attribution rule: a PO line serving exactly one demand yields a per-demand arrival quantity; a PO line serving two or more forms a shared demand session, where the only truthful answer is a session total. Includes the computation rules and the struct that produces them."
tags: [reference, demand-and-purchasing, attribution, packages, tension]
context_tier: 2
personas: [backend, business]
---

# Shared Demand Sessions

*"How much of my demand has arrived?"* is the most common question business asks of this system,
and for a large fraction of demands it is **not answerable** — not because the data is missing, but
because the fact does not exist.

This document defines when it is answerable, what to say when it is not, and the logic that
decides which case applies. It exists as its own document because the tension is real, permanent,
and will be re-litigated by anyone who has not read this.

Read alongside [purchase_ordering_system.md](purchase_ordering_system.md) (allocation mechanics)
and [models/package.md](models/package.md) (what physically arrived).

---

## 1. Why the question is flawed

A `PurchaseOrderLine` buys 100 units of a part. Three demands are allocated against it: 50, 30,
20. A package arrives containing 60 accepted units.

Which demand got them?

There is no answer. The 60 units are **fungible** — identical parts in a box, with nothing
physically distinguishing one requester's units from another's. Nobody at the vendor decided the
shipment was "Alice's 50 and 10 of Bob's." The shipment is 60 units against a line.

Any per-demand number the system produced here would be an invention:

- **Proportional split** (30 / 18 / 12) is arithmetic dressed as fact, and it is wrong the moment a
  receiver hands all 60 to whoever needed them first — which is what actually happens.
- **First-come attribution** (50 to Alice, 10 to Bob) is a policy guess the system was never told.
- **Asking a human to attribute at receipt** produces a number, but an invented one, recorded as
  though it were observed. That is worse than saying nothing, because it launders a guess into the
  audit trail.

So the system does not answer. It says something true instead.

---

## 2. The rule

### Case A — sole demand on the line: **attributable**

> If a `PurchaseOrderLine` has **exactly one** active `PurchaseOrderDemandLink`, then that demand's
> arrived quantity **is** the sum of accepted package-line quantities pointing at that PO line.

Nothing is shared, so nothing needs dividing. This is a real, reportable per-demand number, and it
is the number every business question wants.

```
qty_arrived_for_demand = Σ PackageLine.quantity_accepted
                         WHERE PackageLine.purchase_order_line = line
```

### Case B — two or more demands on the line: **shared demand session**

> If a `PurchaseOrderLine` has **two or more** active `PurchaseOrderDemandLink` rows, those demands
> form a **shared demand session** on that line. The only valid statement is the session total —
> never a per-demand figure.

The truthful report is two numbers and a membership list:

```
session_allocated = Σ PurchaseOrderDemandLink.quantity_allocated   (across the session)
session_arrived   = Σ PackageLine.quantity_accepted                (for the line)
session_members   = the demands in the session
```

Read as: *"This demand is in a shared demand session of 100 units across 3 demands, of which 60
have arrived."*

**The system must never divide `session_arrived` among members.** Not in a struct, not in a
report, not in a tooltip, not as an "estimate."

---

## 3. A demand spans multiple sessions

A demand allocated across several PO lines (split across vendors, backorder re-sourced elsewhere)
is evaluated **per line**, not per demand. Each of its lines independently falls into Case A or
Case B.

So a demand's full arrival picture is:

| Component | Meaning |
| :--- | :--- |
| `attributable_arrived_qty` | Σ arrivals from lines where this demand is the **sole** demand |
| `sessions` | One entry per line where it shares — each with `session_allocated`, `session_arrived`, `member_count` |
| `unallocated_qty` | `quantity_requested − purchased_qty` — never bought at all |

A demand can be fully attributable, fully shared, or both at once. The UI must be able to say
*"12 units arrived for you, plus you're in a shared session of 40 with 25 arrived."* That sentence
is longer than a single number and it is the honest one.

**The same per-line-then-combine shape applies to purchasing coverage, not just arrival** — see
[po_demand_association_graph.md](po_demand_association_graph.md) §2, which also covers the fully
general case (a demand's lines can themselves connect to a wider network of other POs and demands)
and draws the line between this kind of bounded per-entity read and the separate, genuine graph
traversal the admin visualizer needs.

---

## 4. The remedy is a Buyer action, not a formula

A business that genuinely needs per-demand arrival tracking has a lever: **give each demand its own
PO line.** One line, one demand, Case A, exact numbers.

The cost is more lines on the PO and losing the single-line-per-part simplicity for that part. The
benefit is attributability. That trade belongs to the Buyer, on the specific order, with knowledge
of whether anyone will actually ask — not to a system-wide policy and not to an invented split.

Where attribution matters most (serial-tracked items, `serial_number_tracking_required`, high-value
parts, safety-critical work), one-line-per-demand should be the guidance. Where it does not (bulk
consumables, common hardware), a shared session is the efficient and correct shape.

---

## 5. Computation — `PurchaseOrderFulfillmentStruct`

`app/procurement/control_layer/domain_structs/purchase_order_fulfillment_struct.py`

### No anti-pattern — this is an ordinary within-app read (D60/D63)

An earlier draft of this section described the struct as a `# DELIBERATE ANTI-PATTERN` reading
`app/inventory/` models from inside `app/procurement/`. **That is superseded.** Packages live in
`procurement` (D59/D60), so `Package`/`PackageLine` are this app's own tables and nothing crosses a
boundary. There is no `# DELIBERATE ANTI-PATTERN` anywhere in either app.

The prediction that motivated the exception is worth keeping, though, because it still holds in the
other direction: **if a class in `procurement` ever needs to read `inventory`, that is the signal
the boundary was drawn in the wrong place** — revisit the placement rather than adding an
exception. The inward write seam stays `PartDemandContext.record_issuance(...)` (D12), and no
`procurement` model holds an FK into `inventory`.

### The four quantities

Per PO line, no overloaded word among them:

| Field | Meaning | Source |
| :--- | :--- | :--- |
| `qty_ordered` | What the vendor was told to send | `PurchaseOrderLine.quantity_ordered` |
| `qty_allocated` | What demands have claimed | Σ `PurchaseOrderDemandLink.quantity_allocated`, active only |
| `qty_from_accepted_packages` | What physically arrived and was accepted | Σ `PackageLine.quantity_accepted` for this line |
| `qty_issued` | What reached people | Σ `PartDemand.issued_qty` across linked demands |

`qty_issued` is deliberately a **rollup of the demand side**, not an inventory number — it answers
"has this order's material reached anyone," which is the manager's real question, and it comes
from `PartDemand.issued_qty` which this app already owns.

### Attribution mode per line

Every line in the struct carries an explicit mode, computed from its active demand-link count:

| Links | `attribution_mode` | Exposes |
| :---: | :--- | :--- |
| 0 | `unlinked` | Proactive/bulk stock. Arrival is real; no demand claims it |
| 1 | `attributable` | `qty_arrived_for_demand` — a real per-demand number |
| ≥2 | `shared_session` | `session_allocated`, `session_arrived`, `session_members`. **No per-demand field exists on this branch at all** |

The per-demand field is *absent*, not null, in `shared_session` mode. A field that is sometimes a
number and sometimes null invites a caller to default it to zero and report a lie; a field that
does not exist forces the caller to handle the case.

### Package-level rollup

The struct also carries, per package: total shipped quantity, total accepted quantity, line count,
and `mixed_po_assignments` — answering the manager's direct question, *"how many items came in for
this package."*

### Exceptions surfaced, never swallowed

- **Over-receipt** — `qty_from_accepted_packages > qty_ordered` on a line. Legal (vendors
  over-ship), flagged for visibility.
- **Mixed PO assignment** — a package whose header PO disagrees with one or more of its lines. See
  [models/package.md](models/package.md).
- **Unassigned package lines** — arrived, not yet pointed at any PO line.

Per D13, none of these block anything. They are reported.
