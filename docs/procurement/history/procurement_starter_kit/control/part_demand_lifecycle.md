---
okf_version: "0.1"
type: "Process Guide"
title: "Workflow — Part Demand Lifecycle"
description: "Everything that happens to a demand after creation: approval, cancellation, deletion, the inventory issuance seam, and the auto-complete rollup."
tags: [process-guide, demand-and-purchasing, control-layer, workflow, state-machine]
context_tier: 2
personas: [backend, business]
---

# Workflow — Part Demand Lifecycle

Every task that moves a demand after it exists. Creation is in
[create_demand.md](create_demand.md); everything driven by a PO is in
[purchase_order_lifecycle.md](purchase_order_lifecycle.md).

---

## The one write path

Every task below is a call to the same method. Nothing writes a snapshot column any other way.

```
PartDemandContext(demand_id).<domain verb>(...)
  └─ PartDemandStateManager.transition(axis, to_stage, actor, notes, commit=False)
       ├─ PartDemandTransitionStateMachine.check(axis, from, to)
       │    ├─ legal per the axis's transition dict?      (D23)
       │    ├─ cross-dimension gate satisfied?            (D9–D11)
       │    └─ undecidable → allow + flag_for_review      (D13)
       ├─ INSERT PartDemandUpdate
       ├─ UPDATE PartDemand.<axis>
       └─ DemandCompletionHandler.check()                 (D43)
```

`PartDemandTransitionStateMachine` holds one plain Python dict per axis — the legal-transition
shape visible in one glanceable place (D23). It is not a rules engine and must not grow into one;
the generalized version is deferred tech debt (D21).

### The complete gate set

Three gates, hardcoded, checked at execution time. There are no others.

1. **`purchasing_state` cannot leave `null` until `demand_state` reaches `Approved`** (D9).
2. **`demand_state` cannot reach `Cancelled` while any linked PO is still active** — a linked PO
   with `purchasing_state` in `Approved`/`Purchased` and the PO not itself cancelled (D10).
3. **`issuance_state` is gated on nothing** (D11). Issuing from stock on hand with no PO ever cut
   is legal at any time, from any purchasing or shipment state.

---

## `approve_reject_demand`

**Business goal.** An authorized person confirms a need is legitimate, unblocking purchasing.

**Actor.** Approver — the `approve` permission, independently grantable from `buy` (D2).

**Frequency.** Low (D44). The formal step is routinely bypassed: Purchasing acts first via outside
channels, and a Buyer's PO link auto-promotes the demand instead (D42). **Design this path for
correctness, not throughput** — but do not let its rarity tempt anyone into deleting it, because
it is the path that exists when someone deliberately wants the strict process.

### Steps

1. `PartDemandContext.approve(actor, notes=None)` or `.reject(actor, notes=None)`.
2. `PartDemandApprovalPolicy` checks the `approve` permission and domain access.
3. Transition `demand_state` → `Approved` or `Rejected`.
4. On `Approved`, gate 1 is now satisfied; `purchasing_state` becomes movable. Nothing moves it
   here — approval authorizes purchasing to begin, it is not itself a purchasing decision.

### Resubmission

`Rejected → Required` on resubmission. **Same row.** No new `PartDemand`, no reopen action, no
version (M5). The journal carries the full loop, however many times it happens.

`notes` stays optional even on `Rejected` (D15). No mandatory reason is enforced — a required
field here would be filled with "n/a" within a week.

---

## `cancel_demand`

**Business goal.** Close out a need that no longer exists.

**Actor.** Requester or Approver. **Never a Buyer** — a Buyer de-links instead (D4), see
[purchase_order_line_editing.md](purchase_order_line_editing.md).

**Frequency.** Rare, every type (D44).

### Steps

1. `PartDemandContext.cancel(actor, notes=None)`.
2. Gate 2 (D10): the state machine checks every linked `PurchaseOrderDemandLink` for an active PO.
   If one exists, the transition is refused with a message naming the PO that must be cancelled
   first — not a generic failure.
3. Transition `demand_state` → `Cancelled`. Terminal.

Cancelling the order before cancelling the request behind it is how real purchasing works. The
refusal is doing its job, and the message should make the next action obvious.

---

## `delete_or_deactivate_demand`

**Business goal.** Remove a demand created in error, without ever destroying a record something
happened against.

**Actor.** Requester or Approver.

### Steps

1. `PartDemandContext.delete(actor)`.
2. `PartDemandDeletionPolicy` decides which of two things happens (D6):
   - **Untouched** — zero `PurchaseOrderDemandLink` rows and no journal rows beyond the four
     initializers: **hard delete**.
   - **Anything else**: **soft delete** (`deleted_at`). Never a hard delete.

### The guard checks only this app's own tables (D7)

`PartDemandDeletionPolicy` looks at `PurchaseOrderDemandLink` and `PartDemandUpdate`. That is the
whole check. It does not know `inventory` exists, does not know Maintenance or Dispatching will
exist, and imports nothing from any of them.

Cross-app protection is free: every consumer app owns its own link table with a `PROTECT` FK to
`PartDemand`. `inventory.PartIssue` already does this. Django raises `ProtectedError` before the
guard is even consulted.

This is the direct fix for the legacy `DemandOriginResolver`, which reached into
`maintenance`/`dispatching` model internals behind `try/except ImportError` guards to answer the
same question. The FK answers it with no imports and no optional-app handling at all.

---

## `record_issuance_and_return`

**Business goal.** Record that material physically changed hands — and, if some comes back, that
too.

**Actor.** Called from `app/inventory/`, never from a form in this app.

**Frequency.** High, daily (D44). This is the Requester's real job: mark it received and be done.

### The seam (D12)

```
inventory.PartIssuanceOrchestrator.issue(demand_id, issued_to, quantity, actor)
  ├─ INSERT inventory.PartIssue(quantity=+N or −N)
  ├─ net = sum(PartIssue.quantity for this demand)      ← computed in inventory
  └─ procurement.PartDemandContext.record_issuance(
         net_issued_qty=net, to_stage=..., actor=actor, commit=False)
       ├─ PartDemandQuantityManager sets issued_qty = net_issued_qty
       ├─ PartDemandStateManager.transition(issuance, to_stage, ...)
       └─ DemandCompletionHandler.check()
```

**`record_issuance` takes the net quantity as an argument.** It does not, and cannot, query
`PartIssue` to compute it — `procurement` may not look at `inventory`. This is the exact
point where the sanctioned convention break lives, and it is worth being blunt about the cost: if
anything ever creates a `PartIssue` row without this call, `issued_qty` drifts and nothing in this
app can detect it. The orchestrator is the only supported write path.

Both sides run in one transaction, opened by the orchestrator.

### Returns

A return is a **second, negative `PartIssue` row** against the same demand (D39). Not a return
table, not a `quantity_returned` column, not a boolean. `issued_qty` is always the net:

- Issue 10 → `issued_qty = 10`, `issuance_state = Issued Pending Reconciliation` if a return is
  expected, otherwise `Issued`.
- Return 1 → a `−1` row → `issued_qty = 9`.
- Return all 10 → `issued_qty = 0`, which is a **valid** resting value, not an error.

The legacy hub had `was_borrow_and_return` and `quantity_returned` columns that were never
populated in practice — that is the evidence this shape is the right one.

### What is never computed

`issuance_state` never auto-flips from comparing `issued_qty` to anything (D30, D36). A demand can
reach `Issued` at 4 units against 10 purchased, because the job only needed 4. Whoever handles the
material closes it out explicitly. `issued_qty`, `purchased_qty`, and `qty_from_accepted_packages` are
informational inputs to that judgment, never a gate on it.

`Partially Issued` and `Issued Pending Reconciliation` are everyday states, not edge cases (D44).

---

## `complete_demand_rollup`

**Business goal.** A demand reads as done when it is done, without anyone having to say so.

**Actor.** None. This is derived (D43).

### Steps

`DemandCompletionHandler.check()` runs after **every** write to `purchasing_state` or
`issuance_state` — never on `shipment_state` or `demand_state`. It transitions
`demand_state → Completed` when both hold:

- `purchasing_state` has progressed past `null` and past `Denied` — at least `Approved`.
- `issuance_state` has reached `Issued`.

Whichever condition is satisfied second is what fires it. The resulting `PartDemandUpdate` carries
`actor = null` and `is_system_generated = True`.

### Why `shipment_state` is excluded

This is the part that looks wrong until you look at how the queue is actually worked. A Requester
marks their material received and expects the demand to read as done, full stop. Shipment and
stocking tracking is a decoupled background process — high-volume, ideally fed by an external
system rather than typed in (D16's motivating case). Blocking `Completed` on an axis nobody in the
completion path touches would leave every finished demand looking unfinished.

So a demand can be `Completed` while `shipment_state` sits at `Delivered to Local Receiving
Location`, or at `Shipped`, or anywhere else. That is correct.

This supersedes D9a's original "all three other axes must be terminal" framing.

---

## Classes touched across this document

| Class | Role |
| :--- | :--- |
| `PartDemandContext` | Every domain verb: `approve`, `reject`, `resubmit`, `cancel`, `delete`, `record_issuance` |
| `PartDemandStateManager` | The single write path for all four axes |
| `PartDemandTransitionStateMachine` | Transition dicts + gates D9–D11 + fail-open |
| `PartDemandDeletionPolicy` | D6's hard-vs-soft decision |
| `PartDemandApprovalPolicy` | Permission + domain check on approve/reject |
| `PartDemandQuantityManager` | Applies the caller-supplied `issued_qty` |
| `PartDemandIssuanceManager` | Backs `record_issuance`, the inward seam |
| `DemandCompletionHandler` | The D43 rollup |
| `PartDemandNarrator` | Journal text |
| `inventory.PartIssuanceOrchestrator` | The cross-app coordinator (lives in the other app) |
