# Phase 7 — Inventory Auditing (AuditSession, inline edits, staleness)

**Persona:** backend-engineer + frontend-engineer.
**Kit inputs:** `new_system/unaccounted_inventory_discrepancies_solution.md` (+ problem statement for
context). **Decisions in force:** FD-8 (Decimals, not Integers), FD-15, FD-18.

## Goal
Ground-truth corrections: room/spot count sessions and direct inline quantity edits, every change
wrapped in an audit session and an immutable log, with staleness surfaced on stock views.

## Deliverables

### Models (`app/inventory/models/audit/`)
- **`AuditSession`** — `session_number` (`AUD-YYYY-#####`), warehouse FK, room FK null,
  `session_type` (FULL_ROOM_AUDIT / SPOT_CHECK / DIRECT_INLINE_EDIT), `status`
  (OPEN / COMPLETED / CANCELLED), conducted_by, started/completed_at, notes.
- **`AuditSessionLine`** — session FK CASCADE, part FK, storage_location FK null, serial_number
  blank default '', `expected_qty` / `counted_qty` / `variance_qty` **Decimal(12,3)** (FD-8),
  `discrepancy_type` (MATCHED / SURPLUS_FOUND / DEFICIT_MISSING), `resolution_type`
  (DIRECT_ADJUSTMENT / UNRECORDED_TRANSFER), `linked_movement FK PartMovement SET_NULL null`.
- **`InventoryAuditLog`** — append-only: `audit_number` (`LOG-YYYY-#####`), line FK PROTECT, part /
  warehouse / room FKs, previous/new/variance quantities (Decimal), `reason_code`
  (SPOT_COUNT_ADJUSTMENT / INLINE_QUANTITY_EDIT / UNRECORDED_TRANSFER / DAMAGE_SCRAP), recorded_at/by.
  No update/delete code paths anywhere.

(`ActiveInventory.last_audited_at/by` already exist from Phase 2.)

### Control layer (FD-15 — project vocabulary, not the kit's bare function)
- `audit_session_context.py` — **`AuditSessionContext`**: `start(warehouse, room, type)`,
  `record_line(...)` (snapshots expected from stock at entry time), `finalize()` (atomic: apply
  variances through `StockLedgerManager`, stamp `last_audited_*`, write log rows),
  `cancel()`, `inline_edit(active_inventory_id, new_qty, actor)` — the stealth single-line
  COMPLETED session per the kit's blueprint.
- `guards/audit_guard.py` — `AuditSessionStateMachine` (OPEN→COMPLETED/CANCELLED),
  `AuditValidator` (counted ≥ 0; serialized lines count 0 or 1), `AuditPolicy`
  (`can_audit_stock` + room domain gate).
- `narrators/audit_narrator.py` — numbering + log strings.
- UNRECORDED_TRANSFER resolution creates the paired `PartMovement` (CYCLE_COUNT_ADJUSTMENT) via
  `MovementContext` and links it.

### Routes & UI
- **Audit dashboard** — `/inventory/audits` — sessions table + `Start Audit Session` (single-field+
  selects card, in page).
- **Count portal** — `/inventory/audit/<id>` — one-page session: header card; fast-entry line card
  (part search or scan input reusing the Phase 5 scan input component; location select); running
  lines table with live variance chips (green MATCHED / amber SURPLUS / red DEFICIT); finalize card
  (summary of net changes; confirm modal allowed — destructive confirmation).
- **Inline edit** — on `/inventory/active-inventory` rows: edit control per row → single-field
  capture (modal or inline row form, FD-18 both compliant) → POSTs to the stock row's canonical URL →
  returns updated `<tr>` fragment (`format=htmx-row`). Row shows **Last audited** badge:
  `never` (warning), `stale > 30 days` (amber), else relative timestamp + user.
- **Audit log** — `/inventory/audit-logs` — read-only filterable ledger.

### Seeds
One completed room audit with a surplus and a deficit line; one inline edit; stock rows spanning
fresh / stale / never-audited badges.

### Tests
Inline edit creates session+line+log and updates stock atomically; zero-variance edit is a no-op;
finalize applies all variances or none (forced-failure rollback test); UNRECORDED_TRANSFER produces
the linked movement; log immutability (no exposed mutation path); staleness query cutoffs.

## Acceptance checklist
- [ ] Every quantity change to `ActiveInventory` outside intake/movement/issuance is traceable to an
  `InventoryAuditLog` row.
- [ ] Inline edit round-trip via HTMX and via plain form POST (F5 rule) both work.
- [ ] Tests green; memory.md line added.
