# New System Architecture Overview (`ebams2`)

This document defines the architectural refactoring for Inventory Management in `ebams2`, detailing the separation of Procurement vs. Inventory, the introduction of Warehouse & Room domain-scoped topography, 3D coordinate storage mapping, Intake Sessions, Part Movements, and Part Issuances.

---

## 1. Domain Separation: Procurement vs. Inventory

In `ebams2`, Procurement and Inventory are split into two decoupled sub-applications following clean layered architecture guidelines.

```
┌─────────────────────────────────────────────────────────┐
│                    PROCUREMENT APP                      │
│                  (`app/procurement/`)                   │
├─────────────────────────────────────────────────────────┤
│  - Purchase Orders & Lines (`PurchaseOrder`, `POLine`)  │
│  - Part Demands & Demand Graphs (`PartDemand`)         │
│  - Vendor Shipments (`Shipment`, `ShipmentLine`)        │
│  - Pre-Possession Tracking & Carrier Manifests          │
└────────────────────────────┬────────────────────────────┘
                             │ (Asynchronous / Decoupled
                             │  Reconciliation)
                             ▼
┌─────────────────────────────────────────────────────────┐
│                     INVENTORY APP                       │
│                   (`app/inventory/`)                    │
├─────────────────────────────────────────────────────────┤
│  - Physical Topography (`Warehouse`, `Room`, `Storage`) │
│  - Dock Intake Engine (`IntakeSession`, `ItemAllocation`)│
│  - Active Inventory & "Intake" Room Stock               │
│  - Part Movements (`PartMovement`) & Putaway            │
│  - Part Issuances (`PartIssuance`) & Demand Fulfillment │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Warehouse & Room Storage Topography

The rigid legacy hierarchy (`MajorLocation` → `Storeroom` → `Location` → `Bin`) is replaced by a domain-scoped, organizational structure.

```
       [Division] (Core Domain / Org Hierarchy)
           │
           ▼
      [Warehouse] ── (Address, Assigned Data Domains)
           │
           ├───────────────┬────────────────────────────┐
           ▼               ▼                            ▼
   [Intake Room]      [Room A]                       [Room B]
(Auto-created,      (Domain Access                (Domain Access
 Immutable,          Inherited/Overridden)         Inherited/Overridden)
 storage_loc=NULL)         │                            │
                           ▼                            ▼
                 [StorageLocation]            [StorageLocation]
                 (Major X, Minor Y,           (Major X, Minor Y,
                  Atomic Z: 4-digit strings)   Atomic Z: 4-digit strings)
```

### 1. `Warehouse` Model (`app/inventory/models/warehouse.py`)
- Belongs to a **`Division`** (establishing organizational ownership).
- Contains physical **`Address`** details and assigned **Data Domains** (`DataDomain`).
- **Protected "Intake" Room Provisioning**: Every newly created Warehouse automatically provisions an immutable **`Intake` Room** (`is_intake_room = True`). The `Intake` Room **cannot be renamed or deleted**.

### 2. `Room` Model (`app/inventory/models/room.py`)
- Belongs to a **`Warehouse`**.
- **Domain Access Inheritance & Override**:
  - Inherits all Data Domains assigned to its parent Warehouse by default.
  - Administrators can **manually remove specific domain access** (`excluded_data_domains`).

### 3. `StorageLocation` & XYZ Coordinates (`app/inventory/models/storage_location.py`)
- Represents a storage spot within a Room mapped to **X, Y, Z space** (`major_coord`, `minor_coord`, `atomic_coord`).
- **String & 4-Digit Formatting Rule**:
  - Coordinates are stored as strings (`CharField`).
  - If a user enters a numeric value (e.g. `10`, `25`, `100`), the system auto-pads it with leading zeros to **4 digits** (`"0010"`, `"0025"`, `"0100"`).
  - **No Truncation**: Strings longer than 4 digits (e.g. `"12345"` or `"BAY-A-12"`) are preserved without truncation.

---

## 3. Intake Sessions, Dual Entry Points & Room Defaulting

### Dual Receiving UI Entry Points
1. **`Intake from Package` (Quick Manual Entry)**: Users manually input accepted/rejected quantities from a packing slip. The system generates a **Pseudo Scan Session**, executes session commit (`status = CLOSED`), and injects stock directly into the Warehouse's `Intake` Room (`storage_location = NULL`, `is_unassigned = True`).
2. **`Intake from Scan Session` (Full Scanning Engine)**: Operators perform barcode scanning, live allocation tracking, and handle discrepancy reconciliations via `PartReconciliationSession`.

### Warehouse & Room Selection Rules
- **Required Warehouse**: Intake sessions **must** specify a target `Warehouse`.
- **Room Selection & Warning**: Selecting a specific `Room` is optional. If no room is specified, the system displays a warning notification (*"No specific room selected. Defaulting destination to the 'Intake' Room"*), allows submission, and defaults stock placement to the Warehouse's protected **`Intake` Room**.

---

## 4. Part Movements & Putaway Workflow

For complete specifications, see **[`part_movements.md`](part_movements.md)**.

- **Putaway**: Stock initially residing in the `Intake` Room (`storage_location = NULL`, `is_unassigned = True`) is relocated into a designated `Room` + `StorageLocation` (`is_unassigned = False`).
- **Inter-Room & Inter-Warehouse Transfers**: Logged in `PartMovement` (`inventory_movements`), verifying domain access against `Room.get_effective_data_domains()`.

---

## 5. Part Issuances & Demand Integration

For complete specifications, see **[`part_issues.md`](part_issues.md)**.

- **Fulfillment**: `PartIssuance` records fulfill Procurement `PartDemand` lines for maintenance events, assets, or direct user allocations.
- **Security Scoping**: Enforces two-tier authorization (Django `can_issue_parts` permission + user's domain match against `Room`'s effective Data Domains).

---

## 6. Detailed Architectural Guides in this Build Kit

| Document | Description |
| :--- | :--- |
| **[intake_engine_integration.md](intake_engine_integration.md)** | Dock intake engine, barcode parsing, and `PartReconciliationSession` integration. |
| **[part_movements.md](part_movements.md)** | Putaway workflow, inter-room/inter-warehouse movements, and XYZ string formatting. |
| **[part_issues.md](part_issues.md)** | Part issuances, Procurement demand fulfillment, and domain access gates. |
| **[unaccounted_inventory_discrepancies_problem_statement.md](unaccounted_inventory_discrepancies_problem_statement.md)** | Problem statement & brainstorming baseline for found/lost stock, forced adjustments, and surplus/deficit merging. |
| **[svg_gui_mapping_migration.md](svg_gui_mapping_migration.md)** | SVG layout parsing, inkscape:label coordinate mapping, and HTMX server-driven interactive visual portal. |
