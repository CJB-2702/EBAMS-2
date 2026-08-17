# Phase 1 — Warehouse Topography Foundation (backend)

**Persona:** backend-engineer. **Kit inputs:** `new_system/new_system_architecture_overview.md` §2–3,
`migrations/model_migration_plan.md` §2.1–2.2 (field mapping only, FD-7), `new_system/part_movements.md` §2.
**Decisions in force:** FD-1…FD-4, FD-8, FD-14, FD-16, FD-28.

## Goal
The physical world exists in the database: warehouses under divisions, rooms with domain scoping and
a protected Intake Room, storage locations addressed by XYZ string coordinates. No stock yet.

## Deliverables

### Models (`app/inventory/models/topography/`)
All models: `AuditFieldsMixin` (+ `SoftDeleteMixin` where noted), no business logic.

- **`Warehouse`** — `name`, `code` (unique), `division FK administration.Division PROTECT`,
  `address` (Text, blank), `domains M2M administration.Domain related_name='warehouses'`,
  `is_active`. SoftDelete.
- **`Room`** — `warehouse FK CASCADE related_name='rooms'`, `room_name`, `description`,
  `svg_layout` (Text, blank — populated in Phase 3), `is_intake_room` (default False),
  `is_deletable` (default True), `is_renamable` (default True),
  `excluded_domains M2M administration.Domain blank related_name='excluded_rooms'`, `is_active`.
  Unique `(warehouse, room_name)`. SoftDelete.
- **`StorageLocation`** — `room FK CASCADE related_name='storage_locations'`,
  `major_coord`/`minor_coord`/`atomic_coord` (CharField(50)), `display_code` (CharField(150),
  computed on write by control layer), `is_active`. Unique
  `(room, major_coord, minor_coord, atomic_coord)`; index on `(room, display_code)`.

### Foreign-app change (FD-28, reset required)
- `parts.Part`: add `qty_per_scan = Decimal(12,3) default 1.000`, `sn_expected = Boolean default False`.

### Control layer (`app/inventory/control_layer/`)
- `constants.py` — `DECIMAL_PLACES = 3`, `MAX_DIGITS = 12`, status/choice frozen sets used repo-wide.
- `adapters/coordinate_adaptor.py` — `format_xyz_coordinate(value)` per `part_movements.md` §2
  (zfill(4) digits, never truncate, pass through non-numeric), + `build_display_code(x, y, z)`
  → `"X-Y-Z"`. Single source (FD-16).
- `factories/warehouse_factory.py` — `WarehouseFactory.create(...)`: warehouse + protected Intake Room
  (`room_name="Intake"`, `is_intake_room=True`, `is_deletable=False`, `is_renamable=False`) in one
  transaction (FD-14).
- `factories/storage_location_factory.py` — single + `StorageLocationBulkFactory` (used by Phase 3
  SVG builder); both route coordinates through the adaptor and set `display_code`.
- `guards/room_guard.py` — `RoomPolicy` (block rename/delete of intake rooms; block room delete while
  storage locations or stock exist), `RoomDomainPolicy.effective_domains(room)` =
  warehouse domains − room excluded domains, and `user_covers_room(user, room)` for the two-tier gate.
- `guards/topography_guard.py` — `WarehouseValidator`, `StorageLocationValidator` (coordinate
  non-empty, uniqueness pre-check for friendly errors).
- `managers/topography_manager.py` — update/deactivate verbs for warehouse/room/location.
- `domain_structs/` — `WarehouseStruct`, `RoomStruct` (with effective-domain slice),
  `StorageLocationStruct`; each with `to_dict()`.
- `topography_context.py` — `TopographyContext`: the single public entrypoint
  (`create_warehouse`, `add_room`, `add_storage_location`, `bulk_add_storage_locations`,
  `update_*`, `deactivate_*`).

### Permissions
Custom perms on `Warehouse.Meta`: `can_manage_topography`, `can_intake_stock`, `can_move_stock`,
`can_issue_parts`, `can_audit_stock` (later phases check these; defining them once here avoids
repeated resets).

### Seeds
`app/inventory/management/commands/seed_inventory_dev.py` (invoked from the master seed chain):
2 warehouses (different divisions/domain sets), each with Intake Room + 2–3 rooms (one with an
excluded domain), ~20 storage locations across numeric (`0010-0005-0001`) and non-numeric
(`AISLE-A12-…`) coordinates. Idempotent `get_or_create`.

### Tests (`app/inventory/tests/`)
- Coordinate adaptor: padding, no-truncate, non-numeric passthrough.
- Factory provisions Intake Room; `RoomPolicy` blocks its rename/delete.
- Effective-domain algebra incl. exclusion override; `user_covers_room` positive/negative.
- Unique constraints on Room and StorageLocation.

## Acceptance checklist
- [ ] `python refresh_project.py` completes; seeds produce the topography above.
- [ ] No model has methods beyond `__str__` (FD-14).
- [ ] All quantity/coordinate rules imported from the shared modules — zero duplicated literals.
- [ ] Tests green; line added to `dev_tools/memory.md`.
