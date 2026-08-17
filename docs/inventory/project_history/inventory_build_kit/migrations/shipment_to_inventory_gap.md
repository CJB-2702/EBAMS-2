# Shipment-to-Inventory Gap & Intake Workflows

This document explicitly defines the transactional boundary where physical inventory stock is created from vendor shipments, addressing the gap between Procurement's pre-possession tracking (`Shipment`) and Inventory's post-possession custody (`ActiveInventory`).

---

## 1. The Inventory Creation Boundary

### Core Rule: Stock Creation Happens Only on Session Commit
Inventory stock is **never** created directly by receiving a vendor invoice, placing a purchase order, or updating a shipment's transit status in Procurement.

```
┌───────────────────────────────────────────────┐
│        PROCUREMENT APP (`Shipment`)           │
│   Pre-possession tracking (In Transit)        │
└───────────────────────┬───────────────────────┘
                        │
                        │ Physical arrival at Warehouse Dock
                        ▼
┌───────────────────────────────────────────────┐
│         INVENTORY INTAKE APPLICATION          │
│   Intake Session / Pseudo Scan Session        │
└───────────────────────┬───────────────────────┘
                        │
                        │ INVENTORY CREATION BOUNDARY
                        │ (Session Commit: `status = CLOSED`)
                        ▼
┌───────────────────────────────────────────────┐
│         ACTIVE INVENTORY IN STOCK             │
│   Placed in Target Warehouse "Intake" Room    │
│   (storage_location = NULL, is_unassigned = True)│
└───────────────────────────────────────────────┘
```

The transactional boundary for creating physical stock records in `ActiveInventory` occurs **strictly upon Intake Session Commit** (`IntakeSession.status = CLOSED`).

---

## 2. Resolving the Gap: Dual UI Entry Points

To bridge the gap between quick manual paperwork intake and full barcode scanning, the Inventory Application provides **two distinct UI buttons** on the Intake Dashboard:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   INVENTORY INTAKE DASHBOARD                           │
│                                                                        │
│  [  📥 Intake from Package  ]       [  🔍 Intake from Scan Session  ]   │
│   (Quick Manual Paperwork Entry)     (Full Barcode Scanning Workflow) │
└────────────────────────────────────────────────────────────────────────┘
```

### Option A: `Intake from Package` (Quick Manual Entry)
- **Target User**: Receiving clerks handling a paper packing slip or manual delivery with known quantities where item-by-item barcode scanning is not required.
- **Workflow**:
  1. User selects target `Warehouse` and vendor `Shipment` / Package.
  2. UI displays a quick table of shipment lines with inputs for `Quantity Accepted` and `Quantity Rejected`.
  3. User submits the form.
- **Backend Execution (Pseudo Scan Session)**:
  - The system automatically generates a **Pseudo Intake Session** (`intake_method = 'MANUAL_PACKAGE'`).
  - Under the hood, it creates `ItemAllocation` records for each accepted/rejected line.
  - Automatically executes session completion (`status = CLOSED`).
  - Instantly injects stock into the target Warehouse's protected **`Intake` Room** (`storage_location = NULL`, `is_unassigned = True`).
  - Transactionally updates Procurement's `ShipmentLine.quantity_accepted`.

### Option B: `Intake from Scan Session` (Full Scanning Engine)
- **Target User**: Dock operators performing barcode scanning (GS1-128, 1D/2D), serial number logging, and multi-shipment blind receiving.
- **Workflow**:
  1. Operator opens an `IntakeSession` (Warehouse required, Room optional).
  2. Scans items interactively. Live `ItemAllocation` records are built.
  3. If discrepancies or damaged items exist, session moves to `RECONCILING` status, locking commit until resolved via the `PartReconciliationSession` engine.
  4. On final commit (`status = CLOSED`), stock is injected into the Warehouse's **`Intake` Room** (`storage_location = NULL`, `is_unassigned = True`).

---

## 3. Warehouse "Intake" Room & Unassigned Stock

To replace ad-hoc `UnassignedInventory` tables, every physical stock item initially created by an intake session resides in the Warehouse's **`Intake` Room**.

### Rules for the `Intake` Room:
1. **Automatic Provisioning**: Whenever a new `Warehouse` is created, the system automatically provisions an **`Intake` Room** (`room_name = "Intake"`, `is_intake_room = True`).
2. **Immutability & Protection**:
   - The `Intake` Room **cannot be deleted** (`is_deletable = False`).
   - The `Intake` Room **cannot be renamed** (`is_renamable = False`).
3. **Room Selection & Default Behavior**:
   - Intake sessions require selecting a `Warehouse`.
   - Selecting a destination `Room` is optional. If no room is specified, the system displays a UI notification warning (*"No specific room selected. Defaulting destination to the 'Intake' Room"*), allows submission, and defaults to the Warehouse's `Intake` Room.
4. **Stock Attributes**:
   - Stock created in the `Intake` Room has `storage_location = NULL`.
   - Stock carries `is_unassigned = True` on `ActiveInventory`.
   - A subsequent **Putaway Movement** is required to move items from the `Intake` Room into specific destination Rooms and 3D Storage Locations (`storage_location != NULL`, `is_unassigned = False`).
