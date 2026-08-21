# Inventory Application

The `inventory` application handles physical topography, stock ledger mutation, intake processes (interacting with the procurement system), and auditing. It follows the project's layered architecture strictly (`presentation_layer/`, `control_layer/`, `models/`).

## Sub-documents

* [intake_portal_workflow.md](inventory/intake_portal_workflow.md) — the seven-page intake portal, the stock-posting vs paperwork-closure split, cross-session visibility, and the intake data model. **Proposed**, supersedes the single-page session detail surface.
* [tech_debt/intake_shipment_graph_closure.md](inventory/tech_debt/intake_shipment_graph_closure.md) — sessions sharing shipments couple transitively; reconciliation completeness is a connected-component property. **Deferred**, warning-only mitigation.

## Domain Scope

The inventory module is composed of four major operational phases:

1. **Topography (Phases 1 & 3)**: Warehouses, Rooms, RoomLocations, and StorageLocations. Phase 3 introduced the SVG Spatial Engine for visual location picking.
2. **Stock Ledger & Movement (Phases 2 & 6)**: The `ActiveInventory` model represents currently available stock. Mutations to this table are strictly gated through `StockLedgerManager` (inject, withdraw, transfer). Phase 6 introduced part issuance tracking through `PartIssuanceOrchestrator`.
3. **Intake & Reconciliation (Phases 4 & 5)**: The bridge between Procurement (`Shipment`) and Inventory. Driven by `IntakeSession` (Manual or Scan), allocating `ItemAllocation` records against `ShipmentLine`s. Cross-session discrepancies and overages are resolved through the Reconciliation Hub. When a session closes, `IntakeCommitOrchestrator` pushes accepted quantities back across the seam via `ShipmentContext.accept_line`.
4. **Auditing (Phase 7)**: `AuditSession` tracks formal Full-Room and Spot Check counts, creating immutable `InventoryAuditLog` entries. Inline stealth audits are also supported directly from the Active Inventory grid.

## Architectural Seams & Invariants

The `inventory` application establishes several firm boundaries to ensure data integrity:

* **Procurement Seam Exclusivity**: `ActiveInventory` knows nothing about purchase orders. `IntakeCommitOrchestrator.close` is the singular bridge that aggregates session allocations and pushes acceptance to Procurement via `ShipmentContext.accept_line`. `ShipmentLine.quantity_accepted` can never be written by any other path in inventory.
* **Write Funneling**: No code outside of `StockLedgerManager` may directly create, update, or delete an `ActiveInventory` record.
* **Atomic Discrepancy Resolution**: Audit resolutions (e.g. `DIRECT_ADJUSTMENT`, `UNRECORDED_TRANSFER`) invoke `StockLedgerManager` in the exact same transaction that stamps the `InventoryAuditLog`, ensuring the ledger and the ledger history never decouple.
* **Negative Stock Barrier**: The database natively enforces `quantity_on_hand >= 0`, and the control layer throws `InsufficientStockError` before attempting invalid ledger withdrawals.

## Presentation Layer

The frontend avoids Single Page Application state traps. Instead, it relies on HTMX fragments:
* `_row.html` / `_results_card.html` / `_lines_table.html` for atomic row rendering and live filtering without full page reloads.
* Multi-step flows, such as Intake Sessions, are managed server-side via session state rather than client-side wizards.
* Forms strictly adhere to `harness/UX_UI/form_style_guide.md`.
