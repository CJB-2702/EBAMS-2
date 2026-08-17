# Phase 4 — Intake Engine Core & Auto Intake Portal (backend-heavy)

**Persona:** backend-engineer leads; frontend-engineer builds the portal.
**Kit inputs:** `inventory_intake_kit/domain_model.md` + `control_layer_map.md` (as amended),
`inventory_intake_kit/auto_intake_workflow_guide.md` (binding portal spec),
`inventory_intake_kit/overages_shortages_and_reconciliation.md`, `migrations/shipment_to_inventory_gap.md`,
review Decisions 1–4, 7. **Decisions in force:** FD-6, FD-9, FD-10, FD-11, FD-13, FD-27, FD-28.

## Goal
The inventory-creation boundary exists: stock enters `ActiveInventory` **only** via intake session
commit, procurement's `ShipmentLine.quantity_accepted` moves **only** via `ShipmentContext.accept_line`,
and operators can receive expected shipments through the Auto Intake portal.

## Deliverables

### Models (`app/inventory/models/intake/`)
- **`IntakeSession`** — `operator FK administration.User PROTECT`, `warehouse FK PROTECT`
  (required), `room FK Room PROTECT null/blank` (FD-10), `status`
  (`DRAFT/ACTIVE/RECONCILING/CLOSED` + `CANCELLED`), `intake_method` (`SCAN`, `MANUAL_PACKAGE`),
  `has_unlinked_allocations Boolean default False`, `started_at`, `closed_at`,
  `hardware_device_id`, notes. SoftDelete. Index `(operator, status)`.
- **`IntakeSessionShipmentLink`** — session FK CASCADE / `procurement.Shipment` FK PROTECT, unique
  pair. (Kit name `ScanningSessionShipmentAssociation` shortened to repo link-table convention;
  behavior identical.)
- **`ItemAllocation`** — session FK CASCADE `related_name='allocations'`,
  `shipment_line FK procurement.ShipmentLine PROTECT null/blank` (null = unmanifested/staged),
  `part FK parts.Part PROTECT`, `quantity Decimal(12,3)`, `serial_number` blank default '',
  `composite_sn` (indexed, `"{part_id}:{serial}"`), `condition` (`GOOD/REJECTED`),
  `intake_method` (`SCAN/MANUAL`). SoftDelete.
- **`PartReconciliationSession`** — session FK CASCADE, part FK PROTECT, `status PENDING/RESOLVED`,
  totals, resolved_by/at, notes. Unique `(intake_session, part)`. **No resolution_type here** (FD-9).
- **`PartReconciliationLine`** — reconciliation FK CASCADE, `shipment_line FK PROTECT`,
  expected/allocated/rejected quantities, `resolution_type`
  (`none/accepted_shortage/quarantined_overage/force_accepted_overage/rma_disposition`),
  notes. Unique `(part_reconciliation_session, shipment_line)`.

### Foreign-app changes (FD-28, reset required)
- `procurement.ShipmentLine.comments = JSONField(default=dict, blank=True)`.
- Procurement control layer (FD-27): `ShipmentLineManager.split_line(line, received_qty, actor)` +
  `ShipmentContext.split_line` verb with guard + narration — used on partial-receipt commit.

### Control layer (`app/inventory/control_layer/`)
- `intake_context.py` — **`IntakeContext`**, sole entrypoint (verbs per `control_layer_map.md`,
  minus scan-specific ones which land in Phase 5): `start_session`, `associate_shipment`,
  `create_manual_allocation`, `split_allocation`, `transition_to_reconciliation`,
  `resolve_line`, `close_session`, `cancel_session` (soft-delete sweep across children —
  review §5.4).
- `orchestrators/intake_commit_orchestrator.py` — **`IntakeCommitOrchestrator`**: on close, in one
  transaction — validate reconciliation barrier (no PENDING parents), compute cumulative accepted
  per shipment line across **closed** sessions, call `ShipmentContext.accept_line` per line
  (FD-6), call `split_line` for partials, inject GOOD allocations into stock via
  `StockLedgerManager.inject` targeting `session.room or warehouse intake room`
  (`storage_location=NULL`, unassigned), leave unmanifested allocations as quarantined intake-room
  stock and flag `has_unlinked_allocations`.
- `managers/auto_intake_manager.py` — the Auto Intake math (`auto_intake_workflow_guide.md` §3):
  existing balances per line, monotonic floors (A_user ≥ A_existing, R_user ≥ R_existing), shipped
  cap (A+R ≤ Q_line), delta computation, pseudo-session creation (`intake_method='MANUAL_PACKAGE'`,
  immediately committed via the orchestrator).
- `managers/reconciliation_manager.py` — generate parent+child tasks from line/allocation deltas;
  apply per-line resolutions; parent auto-resolves when children resolve.
- `guards/intake_guard.py` — `IntakeSessionStateMachine` (DRAFT→ACTIVE→RECONCILING→CLOSED, CANCELLED
  from non-closed), `AllocationValidator` (serial ⇒ qty 1.000; composite_sn unique vs session +
  live stock), `AutoIntakeValidator` (floors/caps), `IntakePolicy` (permission `can_intake_stock` +
  operator domain scope vs `Shipment` domain — review §5.5).
- `narrators/intake_narrator.py` — session and allocation audit strings.
- Structs for all new models.

### Routes & UI — Auto Intake portal
- `/inventory/intake` — Intake dashboard: two action cards — **Auto Intake** (live) and
  **Scan Session** (Phase 5; card renders with "coming" state) — plus recent-sessions table.
- `/inventory/intake/auto` — single-page portal, three stacked card zones per the guide:
  session metadata (operator locked, warehouse select — room optional with the intake-room-default
  warning notification), unfulfilled shipment search/select
  (`format=htmx-search-results`), lines matrix (`format=htmx-shipment-lines`) with existing
  allocation subtree, floor minimums shown under each input, live delta preview and cap validation
  (HTMX `hx-trigger="change"` re-render; server is the validator — JS is cosmetic). Submit → POST →
  303 to session summary. F5 mid-entry restores via session draft (FD-19).
- `/inventory/intake/session/<id>` — session detail: metadata card, allocations table, linked
  shipments card, commit summary (accepted per line), reconciliation card (populated Phase 5;
  renders empty until then).

### Seeds
Seed one fully-received shipment (closed pseudo-session → intake-room stock), one partially-received
shipment (split line left open), one session with an unmanifested allocation
(`has_unlinked_allocations=True`).

### Tests
Floors/caps/delta math (worked examples A–C from the guide verbatim), cumulative accept across two
sessions, partial-receipt split, unmanifested quarantine flow, reconciliation barrier blocks close,
cancel soft-delete sweep, stock created only on commit (assert no `ActiveInventory` rows while ACTIVE).

## Acceptance checklist
- [ ] `grep -rn "quantity_accepted" app/inventory` shows no writes — only orchestrator calls into
  `ShipmentContext.accept_line`.
- [ ] Auto Intake round-trip on seeds: receive partial, re-open portal, floors reflect existing
  allocations, second receipt tops up cumulatively.
- [ ] Dashboard and session pages honor rule 5 (cards render when empty).
- [ ] Tests green; memory.md line added.
