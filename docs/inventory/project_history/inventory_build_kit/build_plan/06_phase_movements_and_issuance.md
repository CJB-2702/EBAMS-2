# Phase 6 — Part Movements, Putaway GUI & Issuance

**Persona:** backend-engineer + frontend-engineer in tandem (this is the phase the user steers most —
re-read `09_ui_review_map.md` pages 5–9 before building).
**Kit inputs:** `new_system/part_movements.md`, `new_system/part_issues.md`,
`serialized_inventory_tracking.md` §2.3–3. **Decisions in force:** FD-5, FD-8, FD-16, FD-17, FD-18, FD-19.

## Goal
Stock relocates (putaway, inter-room, inter-warehouse, bin adjustment) through the SVG spatial GUI,
and material leaves stock through the issuance workflow that fulfills procurement demands via the
existing `PartIssuanceOrchestrator` seam.

## Deliverables

### Model: `PartMovement` (`app/inventory/models/movements/part_movement.py`)
Per `part_movements.md` §3 with corrections: `movement_number` (unique, `MOV-YYYY-#####` via
narrator/factory), part FK `parts.Part`, `quantity Decimal(12,3)` (FD-8), `serial_number` blank
default '', `movement_type` (PUTAWAY / INTER_ROOM / INTER_WAREHOUSE / BIN_ADJUSTMENT /
CYCLE_COUNT_ADJUSTMENT), from/to warehouse+room FKs PROTECT, from/to storage_location FKs PROTECT
null, `moved_by FK administration.User PROTECT`, `movement_date`, notes.

### Model: `PartIssue` extension (FD-5 — **extend, do not replace**)
Add to the existing model: `issue_type` (FOR_PART_DEMAND default / DIRECT_TO_ASSET /
DIRECT_TO_USER), `part_demand` → nullable, `issued_to_asset FK assets.Asset SET_NULL null`,
`active_inventory FK ActiveInventory PROTECT null`, `serial_number` blank default '',
`unit_cost_at_issue Decimal(12,3) null`. Check constraints: demand required when
`issue_type=FOR_PART_DEMAND`; at least one of demand/asset/user recipient. Signed-quantity return
convention unchanged.

### Control layer
- `managers/movement_manager.py` — `MovementManager.execute(...)`: classify movement type from
  source/destination, domain-gate the **destination** room (and source), run
  `StockLedgerManager.transfer`, write the `PartMovement` row, all in one transaction. Inter-warehouse
  transfers land in the destination warehouse's Intake Room as unassigned (per §1.3).
- `movement_context.py` — `MovementContext`: `putaway`, `move`, `adjust_bin` verbs + list/detail reads.
- `PartIssuanceOrchestrator` extension: accept stock provenance (`active_inventory_id`, qty, serial),
  withdraw via `StockLedgerManager`, snapshot `unit_cost_at_issue` from `unit_cost_avg`, then the
  existing `record_issuance()` call when demand-linked (FD-5). Direct issues skip procurement.
  Returns (negative rows) re-inject stock when a source `active_inventory` is present.
- `guards/movement_guard.py`, `guards/issuance_guard.py` — validators (qty vs available, serialized
  unit integrity) + policies (`can_move_stock` / `can_issue_parts` + domain gates).
- `narrators/` — movement + issuance numbering and audit strings.

### Routes & UI
1. **Movement portal** — `/inventory/movements/create?stock=<active_inventory_id>` — the old
   `move_inventory_gui` re-imagined (UI map p.6): left ⅓ sticky details card (part, serial,
   available, source, qty input, disabled destination summary, submit disabled until destination
   valid); right ⅔ destination selector: warehouse cards (map thumbnails, FD-24) → room cards →
   **Phase 3 SVG map with `format=htmx-putaway-target`** (clicking a shape fills the destination;
   prefix shapes expand to a location list in the drawer). Selection state carried in GET params
   (F5-safe); one canonical URL.
2. **Putaway worklist** — `/inventory/putaway` — replaces old initial-stocking pair (UI map p.7):
   left card = unassigned intake-room stock (filterable, checkbox select), right card = destination
   selector (same component as above, scoped to one warehouse). One page, batch submit → one
   `PartMovement` per row.
3. **Movements ledger** — `/inventory/movements` — condensed table: date, number, type chip, part,
   qty, serial, from → to, actor. Filters. Detail page `/inventory/movement/<id>`.
4. **Issuance portal** — `/inventory/issues/create` — in-page, no modal (FD-18, UI map p.8):
   demand-first flow (arrive from a PartDemand with `?demand=<id>`: demand summary card, eligible
   stock card filtered to the part with serial pick, qty, submit) and stock-first flow (arrive from
   stock row: recipient section — demand search / asset search / user select — as an assignment
   card pair). Session draft for multi-line issues (FD-19).
5. **Issues ledger** — `/inventory/issues` list + `/inventory/issue/<id>` detail (provenance card,
   recipient card, movement link, return action creating the signed negative row).
6. **Part Demand detail (procurement side)** — render the full-issue-rows table per
   `serialized_inventory_tracking.md` §3 (deliberate anti-pattern, review Decision 6): date, issuer,
   qty, serial, source location, recipient — directly on the demand view.

### Seeds
Putaway two seeded intake-room rows to locations; one inter-warehouse transfer; issues covering all
three types incl. one serialized issue and one return row.

### Tests
Movement classification matrix; serialized transfer moves the unit row intact; inter-warehouse lands
unassigned; issuance decrements stock + `record_issuance` fires only when demand-linked; return
re-injects; constraint tests on the extended `PartIssue`; domain-gate denials on destination room.

## Acceptance checklist
- [ ] Click-a-shelf putaway works end-to-end on the seeded SVG room, and F5 at any step reproduces it.
- [ ] `PartDemand` detail shows issue rows with serials, zero clicks.
- [ ] No movement or issuance UI exists inside any modal.
- [ ] `quantity_accepted`, demand `issued_qty`, and stock levels reconcile after the full seed run.
- [ ] Tests green; memory.md line added.
