# Initial Prompt

Verbatim request that seeded this kit (passed to the Kit Builder as its invocation arguments):

> procurement — Procurement application (requisition, purchasing, and package shipment tracking).
> Seed context: [procurement_inventory_boundaries.md](procurement_inventory_boundaries.md)
> (app-boundary and build-order decisions) and the data-model/workflow description already agreed
> in this conversation (PartDemand hub with three status dimensions — approval, order, issue —
> tracked via a generic append-only PartDemandUpdate journal rather than bare status columns, plus
> a PartDemandPurchaseOrderLink many-to-many join table). Explicitly out of scope for this kit: no
> interface/registry/plugin system for consumer apps (Maintenance/Dispatching) to register against
> the hub — rejected as overkill, use plain FK links from consumer apps instead, following the
> hub/link precedent already used for Part.id.

## Referenced seed material

- [procurement_inventory_boundaries.md](procurement_inventory_boundaries.md) — the full design-review conversation this kit is built from: old Flask system review (`/home/cb/REPOS/asset_management/app/data/part_demands/`), the three app-boundary options considered (folded into `parts`, folded into `inventory`, standalone Procurement app — the last one chosen), the proposed build order (Procurement → Inventory → Maintenance → Dispatching), and the package placement decision. This kit resolves the open threads or explicitly defers them.
- The chat turn immediately preceding kit invocation, where the following was walked through and implicitly agreed (not yet locked into `decisions.md` — that happens after interrogation):
  - **`PartDemand`** (hub): part reference, requested-by, quantity, priority, needed-by date, notes, plus three **current-state snapshot fields** (one per dimension) kept denormalized for fast list/filter queries.
  - **`PartDemandUpdate`** (append-only journal): one row per state transition, any dimension — `(dimension, outcome/new stage, actor, timestamp, notes)`. Snapshot columns on `PartDemand` are refreshed alongside each insert, never written directly.
  - **Three dimensions**: Approval (`Requested → Pending Approval → Approved / Rejected`), Order/Purchasing (`Not Ordered → Ordered → Partially Received → Fully Received` / `Cancelled`), Issue/fulfillment (`Not Issued → Partially Issued → Fully Issued` / `Returned` / `Cancelled` — this track has nothing writing to it meaningfully until a future Inventory app exists).
  - **`PartDemandPurchaseOrderLink`** (many-to-many join): demand ↔ PO line, with `quantity_allocated`. A PO line does not require a linked demand (supports future proactive/bulk restocking).
  - Cross-dimension gate: Order should not leave `Not Ordered` until Approval reaches `Approved`.
  - Explicitly rejected: an interface/registry/plugin system (modeled on `detail_extensions`) for consumer apps to register against the hub — judged overkill given a small, known, fixed set of consumer apps and the existing hub/link precedent already solving the decoupling problem without one.
