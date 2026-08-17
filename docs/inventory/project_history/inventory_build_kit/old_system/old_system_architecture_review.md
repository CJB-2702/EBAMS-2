# Old System Architecture Review (`asset_management`)

> [!WARNING]
> **SUPERSEDED LEGACY CONTEXT**
> This document details the legacy application schema (`asset_management`). Concepts from this old system (such as `ArrivalHeader`, `ArrivalLine`, `package_headers`, and manual PO-line link tables) **do not exist in the new system** and poisoned earlier review drafts.
> 
> In the new architecture (`ebams2`):
> - **Intake Header**: `IntakeSession` (Model B) is the physical receiving unit (1-to-N `ItemAllocation`s).
> - **Procurement Boundary**: Intake tables *enhance* shipments without replacing them. Procurement `ShipmentLine.quantity_accepted` is written via `ShipmentContext.accept_line`.
> - **Stock Model**: Standardized on unified `ActiveInventory` exclusively.

---

## 1. Executive Summary & Monolithic Scope

In the old `asset_management` system, the `inventory` module was a monolithic container that encompassed:
1. **Physical Location Hierarchy**: `MajorLocation` → `Storeroom` → `Location` → `Bin`.
2. **Purchasing & Vendor Tracking**: `PurchaseOrderHeader`, `PurchaseOrderLine`, and `PartDemandLink` were embedded inside `data/inventory/purchasing`.
3. **Arrivals / Physical Receiving**: `ArrivalHeader` (`package_headers`) and `ArrivalLine` (`part_arrivals`) combined pre-possession vendor tracking (tracking number, carrier) with post-possession physical intake.
4. **Stock & Inventory Balance**: `ActiveInventory` (inheriting from `BinPrototype`) tracking `quantity_on_hand` and `quantity_allocated` per bin.
5. **Movements & Issuances**: `InventoryMovement` logging movements, and `PartIssue` linking directly to `InventoryMovement` and `PartDemand`.

---

## 2. Old Location Hierarchy

The old application structured physical storage into four fixed tiers:

```
[MajorLocation] (e.g., "Los Angeles Base / Site Alpha")
       │
       ▼
  [Storeroom] (e.g., "Main Avionics Bay", room_name, address, raw_svg/svg_content)
       │
       ▼
   [Location] (e.g., "Shelf 3-1", display_name, svg_element_id)
       │
       ▼
     [Bin]    (e.g., "Bin-A1", bin_tag, svg_element_id)
```

### Key Models & Schemas

#### 1. `MajorLocation` (`major_locations` table)
- Acted as the top-level organizational site or facility.
- Hardcoded foreign key dependencies across storerooms, arrivals, and inventory items.

#### 2. `Storeroom` (`storerooms` table)
- Belongs to a `major_location_id`.
- Contains `room_name`, `address`, `raw_svg`, and `svg_content` for visual storeroom mapping.
- Parent entity for physical inventory storage.

#### 3. `Location` (`locations` table)
- Belongs to a `storeroom_id`.
- Stores `location` identifier (e.g. `"3-1"`), `display_name`, `svg_element_id`, and `bin_layout_svg`.

#### 4. `Bin` (`bins` table)
- Belongs to a `location_id`.
- Stores `bin_tag` (e.g. `"Bin-A1"`). Unique constraint on `(location_id, bin_tag)`.
- Full hierarchical path computed via: `Storeroom > Location > Bin`.

---

## 3. Old Arrivals & Intake System

Physical receiving was modeled under `app/data/inventory/arrivals/`:

### Models: `ArrivalHeader` (`package_headers`) & `ArrivalLine` (`part_arrivals`)

```
[ArrivalHeader] (package_number, tracking_number, carrier, received_date, major_location_id, storeroom_id, status)
       │
       ▼ (1 to Many)
 [ArrivalLine]  (package_header_id, part_id, major_location_id, storeroom_id, quantity_received, condition, status)
       │
       ├─► [ArrivalPurchaseOrderLink] ──► [PurchaseOrderLine] (Many-to-Many linking with PO lines)
       └─► [InventoryMovement] ──► Updates [ActiveInventory]
```

### Architectural Flaws of the Old Arrival System:
1. **Conflated Responsibilities**: `ArrivalHeader` stored vendor tracking details (`carrier`, `tracking_number`) alongside dock receiving details (`received_date`, `storeroom_id`, `received_by_id`).
2. **Mandatory Major Location**: Arrivals required a `major_location_id` and optional `storeroom_id`.
3. **Complex Dual-Linking**: `ArrivalLine` maintained a `po_line_links` join table (`ArrivalPurchaseOrderLink`) to map received quantities against `PurchaseOrderLine`.
4. **Lack of Blind Receiving Engine**: Intaken items had to be manually linked or guessed, leading to data inconsistencies when vendors over-shipped or under-shipped.

---

## 4. Old Stock Tracking & `ActiveInventory`

Stock was tracked using `ActiveInventory`, which inherited from `BinPrototype`:

```python
class ActiveInventory(BinPrototype, UserCreatedBase):
    part_id = db.Column(db.Integer, db.ForeignKey('parts.id'), nullable=False)
    quantity_on_hand = db.Column(db.Float, default=0.0)
    quantity_allocated = db.Column(db.Float, default=0.0)
    last_movement_date = db.Column(db.DateTime, nullable=True)
    unit_cost_avg = db.Column('st_avg', db.Float, nullable=True)
```

- **Location Mixin (`BinPrototype`)**: Added `major_location_id`, `storeroom_id`, `location_id`, `bin_id`.
- **Unique Constraint**: `(part_id, storeroom_id, location_id, bin_id)`.
- **Unassigned Stock**: Allowed `location_id` and `bin_id` to be `NULL`, representing inventory at the storeroom level but not yet assigned to a bin.

---

## 5. Old Part Issuances System

Part issuance was handled by `PartIssue` (`part_issues` table):

```python
class PartIssue(UserCreatedBase):
    inventory_movement_id = db.Column(db.Integer, db.ForeignKey('inventory_movements.id'), unique=True)
    part_id = db.Column(db.Integer, db.ForeignKey('parts.id'))
    quantity_issued = db.Column(db.Float, nullable=False)
    unit_cost_at_issue = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    
    # Recipient Polymorphism
    issued_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    part_demand_id = db.Column(db.Integer, db.ForeignKey('part_demands.id'), nullable=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)
    
    issue_type = db.Column(db.String(30)) # 'DirectToUser', 'ForPartDemand'
    issued_from_storeroom_id = db.Column(db.Integer, db.ForeignKey('storerooms.id'))
```

### Limitations of Old Issuance:
- Tied tightly to legacy `part_demands` and individual `users` or `assets` via nullable foreign keys.
- Did not account for new multi-tier demand graphs, project/maintenance event constraints, or row-level ownership group security scoping.

---

## 6. Summary of Legacy System Pain Points

| Domain | Legacy Implementation | Identified Issues |
| :--- | :--- | :--- |
| **Site Topography** | `MajorLocation` top-level container | Rigid, does not align with Division / Organizational Hierarchy in `ebams2`. |
| **Storage Hierarchy** | `Storeroom` → `Location` → `Bin` | Inflexible location tagging; lacks standardized 3D (X, Y, Z) coordinate mapping. |
| **Security & Access** | No domain-level scoping on rooms | Any user with access to the site could view/move all room stock. |
| **Vendor Shipping vs Dock Intake** | Single `ArrivalHeader` for shipping & intake | Could not process physical packages arriving without prior shipping manifests or POs. |
| **Part Issuance** | `PartIssue` tied to legacy `part_demands` | Lacks integration with new Procurement `PartDemand` & `DemandGraph` architecture. |
