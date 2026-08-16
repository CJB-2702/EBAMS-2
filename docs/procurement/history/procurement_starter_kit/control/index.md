---
okf_version: "0.1"
type: "Process Guide"
title: "Control Layer — Workflow Index"
description: "The five workflow documents, the full class inventory for both apps, and the naming/ownership rules every workflow follows."
tags: [process-guide, demand-and-purchasing, control-layer, index]
context_tier: 2
personas: [backend]
---

# Control Layer — Workflow Index

Each document in this folder defines a **task**: the business goal, the ordered steps, and which
control-layer classes it touches. No UI, no routes, no templates — those belong to the front-end
kit.

---

## The five workflows

| Document | Covers |
| :--- | :--- |
| [create_demand.md](create_demand.md) | `create_demand` — a simple form, one document |
| [part_demand_lifecycle.md](part_demand_lifecycle.md) | `approve_reject_demand` · `cancel_demand` · `delete_or_deactivate_demand` · `record_issuance_and_return` · `complete_demand_rollup` |
| [create_purchase_order_wizard.md](create_purchase_order_wizard.md) | `create_purchase_order` · initial `allocate_demand_to_po_line` · vendor selection (replaces the dropped `create_vendor`) |
| [purchase_order_line_editing.md](purchase_order_line_editing.md) | line editing with audit snapshots · `cancel_purchase_order_line` · `allocate_demand_to_po_line` · de-link |
| [purchase_order_lifecycle.md](purchase_order_lifecycle.md) | `place_purchase_order` · `close_out_shipment` · `cancel_purchase_order` · the PO event emitter |
| [package_lifecycle.md](package_lifecycle.md) | `create_package` · `advance_package_status` · `inspect_and_accept_package_line` · the line-splitting wizard · `derive_demand_arrival` |

Plus one concept document outside this folder:
[../shared_demand_sessions.md](../shared_demand_sessions.md) — when per-demand arrival is a real
number and when it is a shared session, and the struct that computes both.

Weighting, per D44: the PO wizard and line editing are the highest-traffic Buyer surfaces,
package status updates are the highest-volume surface overall (and ideally machine-fed),
`record_issuance_and_return` is the Requester's daily path, and everything in
`part_demand_lifecycle.md` besides issuance is low-frequency and correctness-first.

---

## Class inventory — `app/procurement/control_layer/`

### Demand side

| Class | File | Role |
| :--- | :--- | :--- |
| `PartDemandStruct` | `domain_structs/part_demand_struct.py` | Aggregated read model: the demand, its part, its allocations, derived outstanding quantities. `to_dict()` |
| `PartDemandContext` | `part_demand_context.py` | Entry point around one `demand_id`. Owns `from_struct()` and every domain verb |
| `PartDemandFactory` | `factories/part_demand_factory.py` | Stateless creation of the hub row + its initializing journal rows |
| `PartDemandStateManager` | `managers/part_demand_state_manager.py` | The **only** writer of the four snapshot columns. Journal insert + snapshot refresh, one transaction |
| `PartDemandQuantityManager` | `managers/part_demand_quantity_manager.py` | Recomputes `purchased_qty`; applies the caller-supplied `issued_qty` |
| `PartDemandIssuanceManager` | `managers/part_demand_issuance_manager.py` | The inward seam surface (D12). Backs `record_issuance` |
| `DemandCompletionHandler` | `handlers/demand_completion_handler.py` | The D43 auto-complete rollup check |
| `PartDemandTransitionStateMachine` | `guards/part_demand_state_guard.py` | Legal-transition dicts per axis + gates D9–D11, fail-open per D13 |
| `PartDemandDeletionPolicy` | `guards/part_demand_deletion_guard.py` | D6's hard-delete-only-while-untouched check |
| ~~`PartDemandApprovalPolicy`~~ | — | **Not built (D62).** Its only job was the permission + domain check, and permissions are deferred to the presentation layer |
| `PartDemandNarrator` | `narrators/part_demand_narrator.py` | Journal and audit strings |
| `PartDemandCreateAdaptor` | `adapters/part_demand_create_adaptor.py` | Maps the create form payload |

### Purchasing side

| Class | File | Role |
| :--- | :--- | :--- |
| `PurchaseOrderStruct` | `domain_structs/purchase_order_struct.py` | Header + lines + allocations + all derived totals, one annotated query |
| `PurchaseOrderLineStruct` | `domain_structs/purchase_order_line_struct.py` | One line's derived quantities (see the line model doc) |
| `PurchaseOrderFulfillmentStruct` | `domain_structs/purchase_order_fulfillment_struct.py` | The four quantities, per-line attribution mode, package rollups. An ordinary within-app read since packages live here (D60/D63) |
| `PurchaseOrderContext` | `purchase_order_context.py` | Entry point around one `purchase_order_id` |
| `PurchaseOrderFactory` | `factories/purchase_order_factory.py` | Header + Event + lines + allocations, one transaction |
| `PurchaseOrderLineManager` | `managers/purchase_order_line_manager.py` | Line add/edit/cancel/reorder + the pre-state audit snapshot |
| `PurchaseOrderLineValidator` | `guards/purchase_order_line_guard.py` | D58's soft one-active-line-per-part check; the accepted-quantity floor |
| `PurchaseOrderDemandLinkManager` | `managers/purchase_order_demand_link_manager.py` | Allocate, de-link, release |
| `PurchaseOrderCostManager` | `managers/purchase_order_cost_manager.py` | Recomputes `total_cost` |
| `PurchaseOrderPropagationHandler` | `handlers/purchase_order_propagation_handler.py` | D40's status → demand-axes propagation |
| `PurchaseOrderStateMachine` | `guards/purchase_order_state_guard.py` | D27's legal PO status transitions |
| `PurchaseOrderDemandLinkValidator` | `guards/purchase_order_demand_link_guard.py` | D28's cap, the part-match check, duplicate pairing |
| `PurchaseOrderNarrator` | `narrators/purchase_order_narrator.py` | Machine-comment text for the Event stream |
| `PurchaseOrderDraftAdaptor` | `adapters/purchase_order_draft_adaptor.py` | Maps the wizard's session-backed draft payload |

### Tools

| Class | File | Role |
| :--- | :--- | :--- |
| `PurchaseOrderEventEmitter` | `presentation_layer/tools/po_events/emitter.py` | Fires on PO create and on each status change (D48) |
| `PurchaseOrderEventListener` | `presentation_layer/tools/po_events/listener.py` | Abstract listener interface — **defined, not implemented** |

### Package side — `app/procurement/control_layer/` (D63)

Packages are **procurement** classes, not inventory ones. An earlier draft of this document listed
them under `app/inventory/control_layer/`; that contradicted D59/D60 and is corrected here.

| Class | File | Role |
| :--- | :--- | :--- |
| `PackageFactory` | `factories/package_factory.py` | Creates a `Package` + its lines with copied PO links |
| `PackageContext` | `package_context.py` | Entry point around one `package_id` |
| `PackageLineManager` | `managers/package_line_manager.py` | Line add/accept/reassign; maintains `mixed_po_assignments` |
| `PackageStatusManager` | `managers/package_status_manager.py` | Status advance + `shipment_state` propagation, least-advanced rule |
| `PackageLineSplitHandler` | `handlers/package_line_split_handler.py` | The splitting wizard's split operation |
| `PackageStateMachine` | `guards/package_state_guard.py` | Legal package status transitions |
| `PackageLineValidator` | `guards/package_line_guard.py` | Quantities; part match on PO-line assignment |

## Class inventory — `app/inventory/control_layer/`

Two things live in `inventory`. That is the whole app this build.

| Class | File | Role |
| :--- | :--- | :--- |
| `PartIssuanceOrchestrator` | `orchestrators/part_issuance_orchestrator.py` | **The cross-app coordinator.** Writes `PartIssue`, computes the net, then calls into `procurement` |

`PartIssuanceOrchestrator` is the only class in either app carrying the `Orchestrator` suffix,
which is correct — it is the one place a *write* workflow legitimately crosses an app boundary.
Since packages now live in `procurement`, nothing else crosses at all.

---

## Rules every workflow follows

1. **One transaction per workflow.** Inner calls take `commit=False`; the outermost verb commits.
2. **Snapshot columns are never assigned directly.** `demand_state`, `purchasing_state`,
   `shipment_state`, `issuance_state` move only through `PartDemandStateManager.transition(...)`.
   `purchased_qty`, `issued_qty`, and `total_cost` move only through their manager.
3. **Guards fail open and flag** (D13). A guard that cannot decide allows the transition and sets
   `PartDemandUpdate.flagged_for_review`. It never blocks work on its own uncertainty.
4. **`procurement` never imports `inventory`.** No exceptions, and none needed — moving packages
   into `procurement` (D63) removed the only read that would have crossed. There is no
   `# DELIBERATE ANTI-PATTERN` anywhere in either app.
4a. **`commit=False` means "do not open your own transaction", never "do not write"** (D66).
   Every manager writes its columns either way; the outermost verb owns the transaction.
4b. **Derived quantities use correlated subqueries, never a joined `Sum()` next to another
   multi-row join** (D67) — that fanout silently doubles reported arrival quantities.
5. **Every mutation on a `Placed`-or-later PO posts a machine comment carrying the pre-state JSON
   snapshot** of the edited or deleted row (D57).
6. **Per-demand arrival is derived, never stored.** Exact for a sole-demand line, a session total
   otherwise (D55). No proportional splitting, anywhere, ever.
7. **Domain verbs, not CRUD verbs.** `context.approve(...)`, not `context.update_state(...)`.
8. **Writes live in the control layer.** Entrypoints parse, call a context verb, and return.
