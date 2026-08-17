---
okf_version: "0.1"
type: "Kit Document"
title: "The Demand System"
description: "How a part demand behaves: the four independent state axes, the journal, the three cross-axis gates, auto-completion, quantities, and deletion."
tags: [starter-kit, procurement, demands, policy, okf]
context_tier: 2
personas: [backend, business]
---

# The Demand System

**A PartDemand is a statement that somebody needs a part.** It is not an order, not a
reservation, and not a stock movement. It is the hub every other record in the
application eventually points back at, and the only thing the rest of the codebase is
allowed to know about it is its `id`.

---

## 1. Four axes, not one status

A demand carries four **independent, orthogonal** state columns. They are not stages of
one workflow; they answer four different questions that genuinely move at different
times and can disagree.

| Axis | Column | The question | Default |
| :--- | :--- | :--- | :--- |
| Demand | `demand_state` | Is this need real and authorized? | `projected` |
| Purchasing | `purchasing_state` | Has money been cleared to move? | `""` (blank) |
| Shipment | `shipment_state` | Where is the material physically? | `request_not_sent` |
| Issuance | `issuance_state` | Has it reached the requester? | `not_issued` |

Plus a fifth, derived, read-only label: `linear_status`, copied down from the parent
graph, for anyone who wants one word instead of four.

Legal transitions per axis are declared as four flat dicts in
`guards/part_demand_state_guard.py`. **That file is not a rules engine and must not
grow into one** — the dicts exist so the legal shape is visible in one glanceable
place. Configurable per-organization approval templates were considered and deferred
whole.

### Axis 1 — `demand_state`

```
projected ──▶ required ──▶ approved ──▶ completed
     │            │  ▲          │
     │            ▼  │          │
     │        rejected          │
     │            │             │
     └────────────┴─────────────┴──▶ cancelled
```

- Rejected loops back to **the same row** on resubmission. No new demand, no reopen
  action, no versioning — the journal carries the loop however many times it happens.
- `cancelled` and `completed` are terminal, with no exits.
- **Nobody transitions into `completed` by hand.** It is written automatically (§4).

### Axis 2 — `purchasing_state`

```
"" (unset) ──▶ approved ──▶ purchased
     │             │            │
     ▼             ▼            ▼
  denied       cancelled    cancelled
     │             │            │
     └─────────────┴────────────┴──▶ "" (unset)
```

- Blank is a **real, meaningful value**: "no purchasing decision has been made yet",
  not missing data.
- Unset may go straight to `purchased`, because placing an order is often the first
  purchasing decision anyone records.
- `purchased → ""` is the one backward move in this axis, and it exists solely for line
  cancellation: cancelling the line that was going to buy the part returns the demand to
  "no decision made", which is then accurate.
- There is deliberately **no "manufactured onsite" value**. In-house fabrication is an
  ordinary PO against an internal vendor.

### Axis 3 — `shipment_state`

```
request_not_sent ──▶ request_received_by_vendor ──▶ production_in_progress
                                │                             │
                                └──────────────▶ vendor_prepared_to_ship ──▶ shipped
                                                        ▲                      │
                                          backordered ──┘                      │
                                                        ▲──────────────────────┤
                                                  lost ─┘                      │
                                                                               ▼
                                       delivered_to_depot ──▶ delivered_to_local ──▶ in_stock
```

- `backordered` re-enters the chain because backordered items ship in pieces.
- `lost` re-enters at `shipped` because written-off shipments are sometimes found.
- `delivered_to_local` is **this application's terminal stage**. `in_stock` exists as a
  surface for the later Inventory build and is never written here.

### Axis 4 — `issuance_state`

```
not_issued ──▶ partially_issued ──▶ issued ◀──▶ issued_pending_reconciliation
                      ▲                │
                      └────────────────┴──▶ issued_reconciliation_required ──▶ issued
```

- `issued_pending_reconciliation` is an **active loan** — this is out and expected back.
- `issued_reconciliation_required` is a **different question**: a physical movement
  already happened and the inventory books have not recorded it yet. Kept as a distinct
  value rather than overloading the first, because a later Inventory build needs to
  tell them apart.
- The `issued ↔ pending reconciliation` mechanics belong to Inventory; only the surface
  lives here.

---

## 2. The journal — nothing moves silently

`PartDemandUpdate` is append-only: one row per transition on any axis, carrying
dimension, from-stage, to-stage, actor, a narrated note, whether the system generated
it, and whether it was fail-open-flagged.

**There is no code path that writes a snapshot column without also writing its journal
row.** Both happen together, in one transaction, from `PartDemandStateManager` — the
single writer of all four axis columns. The snapshot columns are a cache; if they ever
disagree with the journal, the journal wins and the snapshots are rebuildable from it.

Creating a demand writes **four** initializing rows, one per axis, with a blank
`previous_stage`. Four rather than one, because that is what makes the journal a
complete account rather than a change log with an unexplained starting point.

---

## 3. The three gates — the complete cross-axis rule set

Within an axis, anything the dict allows is allowed. Across axes there are exactly
**three** rules, and there are no others.

**Gate 1 — purchasing requires approval.**
`purchasing_state` cannot leave unset until `demand_state` reaches `approved`. An
unapproved demand cannot be purchased against. In practice approval is usually reached
as a side effect of the buyer creating an allocation (§5 of the purchasing system), not
as a separate step waited on; this gate is what the buyer's opt-out re-arms. Returning
*to* unset is never gated.

**Gate 2 — cancelling requires dead purchase orders.**
`demand_state` cannot reach `cancelled` while a linked PO is still live (draft, placed,
partially received, or received). Cancelling the order before cancelling the request
behind it is how real purchasing works, and the refusal names the specific PO that must
be cancelled first.

**Gate 3 — issuance is gated on nothing.**
Issuing from stock on hand, with no PO ever cut, is legal at any time from any
purchasing or shipment state. **The absence of a rule here is the rule.**

### Fail-open

When the guard cannot decide — an unknown dimension, or a stored value that is not a
key in its dict — the transition is **allowed and flagged**, with the reason carried
into the journal note and `flagged_for_review = True` on the row. A demand is never
trapped in a state the guard does not recognize. Refusals return a result object rather
than always raising, so bulk callers can skip one demand without failing a whole
workflow.

---

## 4. Auto-completion

A demand becomes `completed` automatically when **both** hold:

1. `purchasing_state` has progressed past unset and past denied (at least approved), and
2. `issuance_state` has reached `issued`.

Whichever condition is satisfied second is what fires it. The check runs after every
write to purchasing or issuance — **never** on shipment or demand state.

**`shipment_state` is deliberately excluded**, and this looks wrong until you look at
how the queue is actually worked. A requester marks their material received and expects
the demand to read as done. Shipment tracking is a decoupled, high-volume background
process ideally fed by an external system; blocking completion on an axis nobody in the
completion path touches would leave every finished demand looking unfinished. A demand
can therefore be `completed` while `shipment_state` sits at `shipped`. That is correct.

**Once completed, the demand is locked** and its state stops moving, even if the parent
graph's `linear_status` later changes. A demand's fulfillment is a point-in-time fact —
"I received X units on date Y and they went to the requester" — and unlike the graph,
which merges, splits, and re-derives constantly, that fact should not rewrite itself.

**Known, accepted divergence:** because the demand is frozen and the graph is not, a
locked demand can read `completed` / `delivered` while its parent graph reads something
earlier. The alternatives were rewriting a completion record (breaks the audit trail) or
snapshotting the demand at completion. Revisit if users report confusion.

---

## 5. Quantities

Three numbers, with three different epistemic statuses.

| Column | Written by | How |
| :--- | :--- | :--- |
| `quantity_requested` | the requester, or the D28 raise path | typed |
| `purchased_qty` | `PartDemandQuantityManager` | **recomputed** as the sum of `quantity_allocated` over the demand's active, non-deleted allocations |
| `issued_qty` | `PartDemandQuantityManager`, from a caller-supplied number | **applied**, never computed |

`issued_qty` cannot be recomputed here: the rows behind it (`inventory.PartIssue`) live
in another app that procurement holds no FK into and may not import. This is a sanctioned
convention break, and its cost is stated plainly in the code: if anything ever creates a
`PartIssue` without going through `inventory.PartIssuanceOrchestrator`, `issued_qty`
drifts and nothing in this app can detect it.

**No caps in either direction on `issued_qty`.** A work order might call for 5 gallons of
oil and need 4.5. A demand that issued 10 and had all 10 returned nets to 0, which is a
valid resting value, not an error. This app records what happened; it does not dictate
what should have.

**`issuance_state` never auto-flips from comparing quantities.** A demand can reach
`issued` at 4 units against 10 purchased, because the job only needed 4. Whoever handles
the material closes it out explicitly; the quantities are informational inputs to that
judgment, never a gate on it.

---

## 6. Deletion

| Condition | Result |
| :--- | :--- |
| No allocations **and** no journal rows beyond the four initializers | **hard delete** — untouched since creation |
| Any allocation exists | soft delete, reason names the count |
| Any journal activity beyond creation | soft delete |

Never a refusal: a demand is always removable one way or the other. The policy checks
**only this app's own tables**. It does not know Inventory exists. Cross-app protection
is free — every consumer app owns a link table with a `PROTECT` FK to PartDemand, so
Django raises `ProtectedError` before this policy is even consulted. This replaced a
legacy resolver that reached into other apps' model internals behind `try/except
ImportError` guards to answer the same question.

---

## 7. Control-layer surface

`PartDemandContext(demand_id)` is the entry point for everything above:

| Verb | What it does |
| :--- | :--- |
| `approve` / `reject` / `resubmit` / `mark_required` / `cancel` | axis 1 |
| `set_purchasing_state` / `clear_purchasing_state` | axis 2 — mostly driven by PO propagation rather than called directly |
| `advance_shipment` | axis 3 |
| `set_issuance_state` | axis 4, **without** recording a quantity |
| `record_issuance` | axis 4 **with** a net quantity — called from `app/inventory/`, never from a form in this app |
| `update_fields` | the plain descriptive fields |
| `refresh_purchased_qty`, `raise_requested_quantity` | quantities |
| `delete` | returns the deletion verdict |

Notes stay optional even on rejection: a mandatory reason field would be filled with
"n/a" within a week.

---

## 8. Permissions

| Codename | Who | Grants |
| :--- | :--- | :--- |
| `procurement.request` | Requester | create and edit demands. **Viewing never requires it** — anyone with domain access can read |
| `procurement.demand_manage` | Floor manager | transition demand/issuance state on **any** demand in their domain, not only their own |

Editing and cancelling are open to the requester who owns the row, or to anyone holding
`demand_manage`. **A buyer never cancels a demand**, and the UI must not render the
control at all when the check fails — not merely disable it.

Every list is fenced by the viewer's domains. An empty domain list means the user sees
no rows; that is the intended reading, not a bug to paper over.
