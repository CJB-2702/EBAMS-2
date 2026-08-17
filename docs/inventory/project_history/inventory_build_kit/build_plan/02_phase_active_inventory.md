# Phase 2 — ActiveInventory & the Stock Ledger (backend, thin UI)

**Persona:** backend-engineer (frontend assists on the list page).
**Kit inputs:** `migrations/model_migration_plan.md` §4 (mapping only), `serialized_inventory_tracking.md`,
review Decisions 5, 8, 9. **Decisions in force:** FD-8, FD-11, FD-12.

## Goal
One stock table with the serialized/non-serialized dual grain, written exclusively through one
control-layer manager, plus a browsable stock list. Intake (Phase 4), movements/issuance (Phase 6),
and audits (Phase 7) all mutate stock **only** through this phase's `StockLedgerManager`.

## Deliverables

### Model (`app/inventory/models/stock/active_inventory.py`)
**`ActiveInventory`** — `warehouse FK CASCADE related_name='stock'`, `room FK CASCADE
related_name='stock'`, `storage_location FK PROTECT null/blank`, `part FK parts.Part PROTECT`,
`serial_number CharField(200) blank default ''` (FD-12 — empty string, never NULL),
`quantity_on_hand Decimal(12,3) default 0`, `quantity_allocated Decimal(12,3) default 0`,
`unit_cost_avg Decimal(12,3) null`, `is_unassigned Boolean default False`,
`last_audited_at DateTime null`, `last_audited_by FK administration.User SET_NULL null`
(audit columns land now to avoid a Phase 7 reset touching this table).

Constraints:
- `Unique(room, storage_location, part, serial_number)`.
- Check: `serial_number = '' OR quantity_on_hand <= 1.000` (serialized rows are unit rows).
- Check: `quantity_on_hand >= 0` and `quantity_allocated >= 0`.

### Control layer
- `managers/stock_ledger_manager.py` — **the only writer** to `ActiveInventory`:
  - `inject(warehouse, room, storage_location, part, qty, serial='', unit_cost=None)` — get-or-create
    the balance row inside `select_for_update`; enforces the NULL-location duplicate guard (FD-12);
    sets `is_unassigned` from `room.is_intake_room and storage_location is None`; rolls
    `unit_cost_avg` as a weighted average when a cost is supplied.
  - `withdraw(...)` — decrements; deletes serialized unit rows at zero; raises
    `InsufficientStockError` before any write.
  - `transfer(...)` — withdraw+inject in one transaction (Phase 6's movement primitive).
  - Every verb takes `actor` and asserts the two-tier gate via `RoomDomainPolicy` **before** touching
    rows.
- `guards/stock_guard.py` — `StockValidator` (qty > 0, serial implies qty == 1, serial uniqueness
  against live stock), `StockPolicy` (permission + domain gate helpers).
- `domain_structs/active_inventory_struct.py` — row struct + per-part and per-room aggregate slices.
- `errors.py` additions: `InsufficientStockError`, `SerialInUseError`, `DomainAccessDenied`.

### Search (`presentation_layer/search/active_inventory_search.py`)
Filterable queryset: warehouse, room, storage location, part (number/name text), serial, unassigned
flag, staleness (`last_audited_at` older than N days / never). Domain-scoped: rooms whose effective
domains the requesting user does not cover are excluded at query level.

### Routes & UI (thin this phase)
- `/inventory/active-inventory` — GET list. `format=condensed` table (default):
  Part | Warehouse | Room | Location | Serial | On hand | Allocated | Available | Avg cost |
  Last audited. Filter bar card above (always renders, rule 5). Pagination per harness.
  `format=htmx-search-results` for the filter bar. Row links to Phase 3's room map (placeholder
  until then) and Phase 6/7 actions arrive later — leave an Actions column stub.
- `/inventory/` — app landing page skeleton: cards for Stock / Intake / Movements / Issues / Audits
  (later phases fill hrefs; cards render now with "Not built yet" empty states).

### Seeds
Extend `seed_inventory_dev`: unassigned Intake-Room stock in each warehouse, located stock at several
storage locations, ≥3 serialized unit rows of an `sn_expected` part, one part present in two rooms.
Seed exclusively **through `StockLedgerManager.inject`** so the seam is exercised daily.

### Tests
- Dual grain: repeat non-serialized injects aggregate to one row; serialized injects create unit rows;
  duplicate serial rejected (`SerialInUseError`).
- Withdraw guards: insufficient stock, serialized zero-row cleanup.
- NULL-location duplicate guard: two concurrent-style injects into the Intake Room yield one row.
- Domain gate: user without room domain coverage gets `DomainAccessDenied`; search hides scoped rooms.

## Acceptance checklist
- [ ] `grep -rn "ActiveInventory.objects" app/inventory | grep -v stock_ledger_manager` shows reads only
  (`.create/.update/.delete/.save` appear nowhere outside the manager and tests).
- [ ] Reset + seed produces a browsable `/inventory/active-inventory` for a scoped dev user.
- [ ] F5 on any filtered list state reproduces it (filters are GET params).
- [ ] Tests green; memory.md line added.
