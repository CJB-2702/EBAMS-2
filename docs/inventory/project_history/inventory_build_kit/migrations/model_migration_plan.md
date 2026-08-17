# Model Migration Plan: Legacy to `ebams2` Inventory

This document outlines the detailed database model changes, schema transformations, and migration strategies required to transition from legacy `asset_management` models to the `ebams2` Inventory and Procurement architecture.

---

## 1. Summary of Model Transformations

```
LEGACY MODEL (`asset_management`)              TARGET MODEL (`ebams2`)
─────────────────────────────────────────────  ──────────────────────────────────────────
MajorLocation                               ──► Warehouse (app/inventory/models/warehouse.py)
Storeroom                                   ──► Room (app/inventory/models/room.py)
Location + Bin                              ──► StorageLocation (app/inventory/models/storage_location.py)
ArrivalHeader (package_headers)             ──► Shipment (app/procurement/) AND
                                                IntakeSession (app/inventory/)
ArrivalLine (part_arrivals)                 ──► ShipmentLine (app/procurement/) AND
                                                IntakeLine (app/inventory/)
ActiveInventory                             ──► ActiveInventory (app/inventory/models/active_inventory.py)
PartIssue                                   ──► PartIssuance (app/inventory/models/issuance/)
```

---

## 2. Table-by-Table Migration Strategy

### 1. `MajorLocation` & `Storeroom` ──► `Warehouse` & `Room`

#### Legacy Schema (`major_locations` & `storerooms`):
- `major_locations`: `id`, `name`, `code`
- `storerooms`: `id`, `major_location_id`, `room_name`, `address`, `raw_svg`, `svg_content`

#### Target `ebams2` Schema:

```python
# app/inventory/models/warehouse.py
class Warehouse(UserCreatedBase):
    """Warehouse facility belonging to an organizational Division."""
    __tablename__ = 'inventory_warehouses'

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    division = models.ForeignKey('core_domain.Division', on_delete=models.PROTECT)
    address = models.TextField(blank=True, null=True)
    data_domains = models.ManyToManyField('administration.DataDomain', related_name='warehouses')
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            # Auto-provision protected "Intake" Room upon Warehouse creation
            Room.objects.create(
                warehouse=self,
                room_name="Intake",
                description="Default physical receiving room for newly intaken stock",
                is_intake_room=True,
                is_deletable=False,
                is_renamable=False
            )
```

```python
# app/inventory/models/room.py
class Room(UserCreatedBase):
    """Storage room within a Warehouse, with explicit domain access overrides."""
    __tablename__ = 'inventory_rooms'

    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='rooms')
    room_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    svg_layout = models.TextField(blank=True, null=True)
    
    # Intake Room Protection Flags
    is_intake_room = models.BooleanField(default=False)
    is_deletable = models.BooleanField(default=True)
    is_renamable = models.BooleanField(default=True)
    
    # Domain override set: domains explicitly removed from room access
    excluded_data_domains = models.ManyToManyField('administration.DataDomain', blank=True, related_name='excluded_rooms')
    is_active = models.BooleanField(default=True)

    def get_effective_data_domains(self):
        """Calculates inherited warehouse domains minus excluded room domains."""
        warehouse_domains = set(self.warehouse.data_domains.all())
        excluded = set(self.excluded_data_domains.all())
        return warehouse_domains - excluded
```

#### Migration Transformation:
1. Create `Warehouse` records for each legacy `MajorLocation` (assigning the default organizational `Division`).
2. The `Warehouse.save()` method automatically provisions the protected `"Intake"` `Room` (`is_intake_room = True`).
3. Convert legacy `Storeroom` records into custom `Room` records linked to the corresponding `Warehouse`.
4. Copy `address` to `Warehouse` and `svg_content` to `Room.svg_layout`.
5. Initialize `Room.excluded_data_domains` as empty (inheriting all parent warehouse domains).

---

### 2. `Location` & `Bin` ──► `StorageLocation` (XYZ Coordinates)

#### Legacy Schema (`locations` & `bins`):
- `locations`: `id`, `storeroom_id`, `location` (e.g. "Shelf A"), `display_name`
- `bins`: `id`, `location_id`, `bin_tag` (e.g. "Bin-01")

#### Target `ebams2` Schema:

```python
# app/inventory/models/storage_location.py
class StorageLocation(UserCreatedBase):
    """Standardized 3D Coordinate Storage Location in a Room."""
    __tablename__ = 'inventory_storage_locations'

    room = models.ForeignKey('inventory.Room', on_delete=models.CASCADE, related_name='storage_locations')
    
    # Coordinate Mapping (X, Y, Z)
    major_coord = models.CharField(max_length=50, help_text="X-Coordinate: Rack, Aisle, or Row")
    minor_coord = models.CharField(max_length=50, help_text="Y-Coordinate: Shelf or Level")
    atomic_coord = models.CharField(max_length=50, help_text="Z-Coordinate: Bin or Container tag")
    
    display_code = models.CharField(max_length=150, help_text="Computed: X-Y-Z (e.g., Aisle1-Shelf2-Bin3)")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['room', 'major_coord', 'minor_coord', 'atomic_coord'],
                name='unique_room_xyz_coordinates'
            )
        ]
```

#### Migration Transformation:
- Concatenate legacy `location` and `bin_tag` strings into structured coordinate fields:
  - `major_coord` = Legacy `Location.location` (or shelf identifier)
  - `minor_coord` = Legacy `Location.display_name` (or level)
  - `atomic_coord` = Legacy `Bin.bin_tag`
- Map foreign key from `storeroom_id` to new `room_id`.

---

### 3. `ArrivalHeader` & `ArrivalLine` ──► Procurement `Shipment` & Inventory Intake Engine (`inventory_intake_kit`)

#### Legacy Schema:
- Single `ArrivalHeader` (`package_headers`) tracking both carrier info and storeroom receipt.
- `ArrivalLine` (`part_arrivals`) linked to `package_headers` and `PurchaseOrderLine`.

#### Target `ebams2` Schema:

##### A. Procurement Vendor Shipment (`app/procurement/models/shipments/`)
```python
class Shipment(UserCreatedBase):
    """Procurement record of vendor shipment (Pre-possession tracking)."""
    __tablename__ = 'procurement_shipments'

    purchase_order = models.ForeignKey('procurement.PurchaseOrder', on_delete=models.CASCADE)
    tracking_number = models.CharField(max_length=100, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, default='IN_TRANSIT') # AWAITING, SHIPPED, DELIVERED
```

##### B. Inventory Dock Intake Engine (`app/inventory/models/intake/` — from `inventory_intake_kit`)

```python
class IntakeSession(UserCreatedBase):
    """Active receiving session at a dock for a specific Warehouse."""
    __tablename__ = 'inventory_intake_sessions'

    operator = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='intake_sessions')
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.PROTECT) # MANDATORY
    started_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default='DRAFT') # DRAFT, ACTIVE, RECONCILING, CLOSED
    hardware_device_id = models.CharField(max_length=100, blank=True)
```

```python
class ScanningSessionShipmentAssociation(UserCreatedBase):
    """Join table linking an IntakeSession to 1+ expected procurement Shipments."""
    __tablename__ = 'inventory_session_shipment_associations'

    intake_session = models.ForeignKey(IntakeSession, on_delete=models.CASCADE, related_name='shipment_associations')
    shipment = models.ForeignKey('procurement.Shipment', on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['intake_session', 'shipment'], name='unique_session_shipment')
        ]
```

```python
class ItemAllocation(UserCreatedBase):
    """Individual barcode scan event or manual intake allocation."""
    __tablename__ = 'inventory_item_allocations'

    intake_session = models.ForeignKey(IntakeSession, on_delete=models.CASCADE, related_name='allocations')
    shipment_line = models.ForeignKey('procurement.ShipmentLine', on_delete=models.PROTECT, null=True, blank=True)
    part = models.ForeignKey('parts.PartDefinition', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    serial_number = models.CharField(max_length=200, null=True, blank=True)
    composite_sn = models.CharField(max_length=400, null=True, blank=True, db_index=True)
    condition = models.CharField(max_length=30, default='GOOD') # GOOD, REJECTED
    intake_method = models.CharField(max_length=30, default='SCAN') # SCAN, MANUAL
```

```python
class PartReconciliationSession(UserCreatedBase):
    """Isolated task workflow resolving discrepancies per part number before session close."""
    __tablename__ = 'inventory_part_reconciliations'

    intake_session = models.ForeignKey(IntakeSession, on_delete=models.CASCADE, related_name='reconciliations')
    part = models.ForeignKey('parts.PartDefinition', on_delete=models.PROTECT)
    status = models.CharField(max_length=30, default='PENDING') # PENDING, RESOLVED
    expected_quantity = models.DecimalField(max_digits=12, decimal_places=4)
    allocated_quantity = models.DecimalField(max_digits=12, decimal_places=4)
    rejected_quantity = models.DecimalField(max_digits=12, decimal_places=4)
    resolution_type = models.CharField(max_length=50, default='none') 
    # choices: accepted_shortage, force_accepted_overage, quarantined_overage, rma_disposition
    resolved_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['intake_session', 'part'], name='unique_session_part_reconciliation')
        ]
```

---

### 4. Legacy Inventory Stock ──► Unified `ActiveInventory` ("Intake" Room Stock)

Rather than maintaining a separate table for unassigned dock stock, all inventory in `ebams2` is unified under `ActiveInventory`. Physical stock initially created by dock receiving is assigned to the target Warehouse's protected **`Intake` Room** (`storage_location = NULL`, `is_unassigned = True`).

#### Target `ebams2` Schema:

```python
# app/inventory/models/active_inventory.py
class ActiveInventory(UserCreatedBase):
    """Unified stock model for both unassigned Intake room stock and put-away location stock."""
    __tablename__ = 'inventory_active'

    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE, related_name='stock')
    room = models.ForeignKey('inventory.Room', on_delete=models.CASCADE, related_name='stock')
    storage_location = models.ForeignKey('inventory.StorageLocation', on_delete=models.PROTECT, null=True, blank=True)
    part = models.ForeignKey('parts.PartDefinition', on_delete=models.PROTECT)
    
    # Quantities & Costs
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    quantity_allocated = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    unit_cost_avg = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    # Unassigned Stock Flag (True when room is Intake room and storage_location is NULL)
    is_unassigned = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['room', 'storage_location', 'part'],
                name='unique_active_inventory_location_part'
            )
        ]
```

---

### 5. `PartIssue` ──► `PartIssuance` (Demand Integrated)

#### Target `ebams2` Schema:

```python
# app/inventory/models/issuance/part_issuance.py
class PartIssuance(UserCreatedBase):
    """Record of part issuance to fulfill a PartDemand or Work Order."""
    __tablename__ = 'inventory_part_issuances'

    issuance_number = models.CharField(max_length=100, unique=True)
    part_demand = models.ForeignKey('procurement.PartDemand', on_delete=models.PROTECT, related_name='issuances')
    active_inventory = models.ForeignKey('inventory.ActiveInventory', on_delete=models.PROTECT)
    
    quantity_issued = models.DecimalField(max_digits=12, decimal_places=4)
    unit_cost_at_issue = models.DecimalField(max_digits=12, decimal_places=4)
    issued_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='issued_parts')
    issued_to_user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    issued_to_asset = models.ForeignKey('assets.Asset', on_delete=models.SET_NULL, null=True, blank=True)
    
    issue_date = models.DateTimeField(default=timezone.now)
```

---

## 3. Dev Reset & Migration Command Workflow

Following rule #1 of `AGENTS.md`:
- Schema alterations rely on **full database reset during active development**.
- Workflow:
  ```bash
  python dev_tools/delete_database_rebuild_models.py --seed
  ```
- Seed scripts (`app/inventory/fixtures/` or `dev_tools/seed_dev.py`) will seed sample `Warehouse`, `Room` (with domain overrides), `StorageLocation` (XYZ coordinates), `IntakeSession`, and `PartIssuance` records.
