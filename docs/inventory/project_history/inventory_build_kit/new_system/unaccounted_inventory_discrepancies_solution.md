# Solution Architecture: Inventory Auditing Application (`AuditSession`)

> **Document Status**: Active Implementation Blueprint  
> **Complements**: [`unaccounted_inventory_discrepancies_problem_statement.md`](unaccounted_inventory_discrepancies_problem_statement.md)  
> **Target Sub-App**: `app/inventory/`

---

## 1. Simplified Architecture Overview

The `Inventory Auditing` sub-module provides a streamlined, session-based workflow for performing stock spot counts, room audits, direct inline edits, and discrepancy reconciliations. It operates as a **Record of Ground Truth**, eliminating approval gates and replacing them with atomic database commits and immutable audit logs.

### Dual Access & Entry Points
1. **`AuditSession` Workflow (Bulk / Room Count)**:
   - User clicks **Start Audit Session** from the Inventory navigation bar.
   - Selects target **`Warehouse`** and **`Room`**.
   - Inputs physical counts via barcode scanner or fast line entry.
   - System highlights variances (`counted_qty` vs `expected_qty`).
   - User clicks **Finalize Session** $\rightarrow$ `ActiveInventory` instantly updates, `last_audited_at` / `last_audited_by` are stamped, and `InventoryAuditLog` entries are written.
2. **Direct Row Edit (Stealth Single-Row Audit)**:
   - User edits quantity directly on an `ActiveInventory` row in the inventory table.
   - System **stealthily creates a single-line `AuditSession`** (`session_type="DIRECT_INLINE_EDIT"`), logs the delta in `InventoryAuditLog`, updates `quantity_on_hand`, and stamps `last_audited_at` / `last_audited_by`.

```mermaid
flowchart LR
    StartBulk[User Starts AuditSession] ──► Scan[Scan / Input Room Parts] ──► Calc[Calc Variance = Counted - Expected] ──► Commit[Finalize Session] ──► Audit[Update ActiveInventory + Stamp last_audited_at + Immutable Audit Log]
    
    StartInline[User Edits Qty on ActiveInventory Row] ──► Stealth[Stealth Single-Line AuditSession] ──► Audit
```

---

## 2. Model Schema Specification

### 2.1 `ActiveInventory` Field Additions (`app/inventory/models/active_inventory.py`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `last_audited_at` | `DateTimeField` | Timestamp of the most recent audit or direct quantity edit (nullable). |
| `last_audited_by` | `ForeignKey(User)` | User who conducted the most recent audit or direct quantity edit (nullable). |

### 2.2 `AuditSession` (`app/inventory/models/audit_session.py`)

Represents an active, completed, or stealth inline edit audit session.

| Field | Type | Description |
| :--- | :--- | :--- |
| `session_number` | `CharField` | Unique auto-generated string (e.g., `AUD-2026-00018`). |
| `warehouse` | `ForeignKey(Warehouse)` | Target warehouse being audited. |
| `room` | `ForeignKey(Room)` | Target room being audited (optional). |
| `session_type` | `CharField` | Choices: `FULL_ROOM_AUDIT`, `SPOT_CHECK`, `DIRECT_INLINE_EDIT`. |
| `status` | `CharField` | Choices: `OPEN`, `COMPLETED`, `CANCELLED`. |
| `conducted_by` | `ForeignKey(User)` | User who opened/conducted the count session. |
| `started_at` | `DateTimeField` | Auto-populated on session start. |
| `completed_at` | `DateTimeField` | Auto-populated on session completion. |
| `notes` | `TextField` | Operational notes or reasons for audit. |

### 2.3 `AuditSessionLine` (`app/inventory/models/audit_session_line.py`)

Represents an individual counted part line within an audit session.

| Field | Type | Description |
| :--- | :--- | :--- |
| `session` | `ForeignKey(AuditSession)` | Parent audit session. |
| `part` | `ForeignKey(Part)` | Target part SKU. |
| `storage_location` | `ForeignKey(StorageLocation)` | Storage location spot (nullable for unassigned/room stock). |
| `expected_qty` | `IntegerField` | System count snapshot from `ActiveInventory` at time of entry. |
| `counted_qty` | `IntegerField` | Physical count entered by operator. |
| `variance_qty` | `IntegerField` | Computed delta: `counted_qty - expected_qty`. |
| `discrepancy_type` | `CharField` | Choices: `MATCHED`, `SURPLUS_FOUND`, `DEFICIT_MISSING`. |
| `resolution_type` | `CharField` | Choices: `DIRECT_ADJUSTMENT`, `UNRECORDED_TRANSFER`. |
| `linked_movement` | `ForeignKey(PartMovement)` | Optional link if variance was resolved as an unrecorded transfer. |

### 2.4 `InventoryAuditLog` (`app/inventory/models/audit_log.py`)

Immutable audit log table capturing every variance adjustment committed to `ActiveInventory`.

| Field | Type | Description |
| :--- | :--- | :--- |
| `audit_number` | `CharField` | Unique audit record identifier (`LOG-2026-00104`). |
| `audit_session_line` | `ForeignKey(AuditSessionLine)` | Reference to originating audit session line. |
| `part` | `ForeignKey(Part)` | Affected part SKU. |
| `warehouse` | `ForeignKey(Warehouse)` | Warehouse location. |
| `room` | `ForeignKey(Room)` | Room location. |
| `previous_qty` | `IntegerField` | System quantity prior to audit. |
| `new_qty` | `IntegerField` | System quantity after audit completion. |
| `variance_qty` | `IntegerField` | Net change (`new_qty - previous_qty`). |
| `reason_code` | `CharField` | Category code (`SPOT_COUNT_ADJUSTMENT`, `INLINE_QUANTITY_EDIT`, `UNRECORDED_TRANSFER`, `DAMAGE_SCRAP`). |
| `recorded_at` | `DateTimeField` | Timestamp of commit. |
| `recorded_by` | `ForeignKey(User)` | User who finalized the audit / direct edit. |

---

## 3. Direct Inventory Edit Control Layer Specification

When an inventory item quantity is updated directly from the inventory table UI:

```python
# app/inventory/control_layer/audit_engine.py

def execute_inline_quantity_edit(*, active_inventory_id: int, new_qty: int, user: User, reason_code: str = "INLINE_QUANTITY_EDIT") -> ActiveInventory:
    """
    Executes a direct inline quantity edit on an ActiveInventory row while stealthily
    wrapping the change inside a completed single-line AuditSession.
    """
    with transaction.atomic():
        item = ActiveInventory.objects.select_for_update().get(id=active_inventory_id)
        previous_qty = item.quantity_on_hand
        variance = new_qty - previous_qty
        
        if variance == 0:
            return item

        # 1. Create stealth AuditSession
        session = AuditSession.objects.create(
            session_number=generate_audit_session_number(),
            warehouse=item.warehouse,
            room=item.room,
            session_type="DIRECT_INLINE_EDIT",
            status="COMPLETED",
            conducted_by=user,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            notes=f"Direct inline edit of Qty from {previous_qty} to {new_qty}"
        )

        # 2. Create AuditSessionLine
        line = AuditSessionLine.objects.create(
            session=session,
            part=item.part,
            storage_location=item.storage_location,
            expected_qty=previous_qty,
            counted_qty=new_qty,
            variance_qty=variance,
            discrepancy_type="SURPLUS_FOUND" if variance > 0 else "DEFICIT_MISSING",
            resolution_type="DIRECT_ADJUSTMENT"
        )

        # 3. Create immutable InventoryAuditLog
        InventoryAuditLog.objects.create(
            audit_number=generate_audit_log_number(),
            audit_session_line=line,
            part=item.part,
            warehouse=item.warehouse,
            room=item.room,
            previous_qty=previous_qty,
            new_qty=new_qty,
            variance_qty=variance,
            reason_code=reason_code,
            recorded_at=timezone.now(),
            recorded_by=user
        )

        # 4. Update ActiveInventory row & audit timestamps
        item.quantity_on_hand = new_qty
        item.last_audited_at = timezone.now()
        item.last_audited_by = user
        item.save()

        return item
```

---

## 4. UI / HTMX Integration Pattern

Following `docs/Architecture/patterns/htmx_patterns.md` and `docs/UX_UI.md`:

1. **Active Inventory Table (`/inventory/active-inventory/`)**:
   - Displays **Last Audited** column showing formatted timestamp (e.g. `2 hours ago by @jdoe`) or a warning badge (`Never Audited` / `Stale (> 30 days)`).
   - Inline edit button triggers an HTMX modal or inline form. Submitting posts to `/inventory/active-inventory/<id>/update-qty/`.
2. **HTMX Response**:
   - Returns updated `<tr>` fragment replacing the table row, displaying the new quantity and updated `last_audited_at` badge seamlessly.
