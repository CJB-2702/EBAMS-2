# Phase 5 — Scan Sessions, Matching Engine & Reconciliation Hub

**Persona:** backend-engineer (matching engine) + frontend-engineer (scan portal, hub).
**Kit inputs:** `inventory_intake_kit/control_layer_map.md`, `part_reconciliation_workflow.md`,
`overages_and_shortages_guide.md`, `sequence_diagrams.md`, `intake_engine_integration.md` §2–4.
**Decisions in force:** FD-9, FD-13, FD-21, FD-26.

## Goal
Full blind receiving: live barcode scanning building `ItemAllocation` rows, algorithmic 1-to-1 /
FIFO N-to-M matching, quality splits, and the manager-facing Reconciliation Hub that gates session
close.

## Deliverables

### Control layer
- `managers/intake_matching_manager.py` — **`IntakeMatchingManager`**:
  - `parse_barcode(raw_payload)` → (sku, serial) for 1D/2D/GS1-128 (AI 01/21 minimum; unknown
    payload → manual-entry fallback, never a crash).
  - `find_target_line(session, part)` → line | None (1-to-1 direct link; ambiguous N-to-M → staged
    `shipment_line=NULL`; no match → unmanifested).
  - `execute_fifo_cascade(session, part)` — when staged totals cross a line's expected quantity,
    atomically re-link staged allocations oldest-line-first.
  - `validate_serial_uniqueness` delegates to Phase 2's `StockValidator`.
- `IntakeContext` additions: `process_scan(session_id, raw_payload, condition)`,
  `pull_external_allocation(session_id, allocation_id, target_line_id)` (**last work item**, may
  slip per FD-26).
- `reconciliation_manager` finishing: cross-line reassignment of allocations inside a session
  (dropdown reassignment), rejected-quantity propagation into `rejection_notes` on accept.

### Routes & UI
- **Scan session portal** — `/inventory/intake/session/<id>` gains its ACTIVE-state face: sticky
  scan-input card (autofocus text input; scanner-as-keyboard; `hx-post` per scan returning the
  updated allocation feed via `format=htmx-scan-feed`), live per-shipment-line progress card
  (expected / allocated / rejected bars), staged & unmanifested card, condition toggle
  (GOOD default, REJECTED for damaged), split-allocation control (single-field capture — modal
  permitted), optional chime toggle (FD-21). Plain-form fallback: manual allocation entry works
  without JS (F5 rule).
- **Session lifecycle controls** — start (from dashboard: pick warehouse, associate one or more
  unfulfilled shipments via in-page assignment card pair — **not** a modal), pause/resume (status
  stays ACTIVE; portal is stateless server-side), `Transition to Reconciliation`, `Close & Commit`
  (disabled with reason chips while parents PENDING).
- **Reconciliation Hub** — `/inventory/intake/reconciliations` — manager queue: sessions in
  RECONCILING with unresolved-part counts and severity chips; filter bar. Detail per parent
  (`/inventory/intake/reconciliation/<id>`): part header card, child **line** cards each showing
  expected/allocated/rejected and a resolution select (`accepted_shortage`, `quarantined_overage`,
  `force_accepted_overage`, `rma_disposition`) + notes; resolving all children resolves the parent
  (FD-9). Cross-session excess pulling UI (search other sessions' staged allocations, pull into a
  shortage line) is the final card — build last (FD-26).

### Seeds
A mid-flight ACTIVE scan session with staged N-to-M allocations, and a RECONCILING session with one
shortage parent (2 lines) and one overage parent — so the Hub is demonstrable after every reset.

### Tests
Barcode parse matrix; 1-to-1 vs N-to-M staging vs unmanifested routing; FIFO cascade re-link order;
split allocation conservation (good+rejected == original); resolution per child line without
cross-line netting (the §2.1 netting scenario as a regression test); close blocked until all parents
resolved; pull_external re-link audit comment.

## Acceptance checklist
- [ ] Simulated scan flood (management command or test) of 10 identical parts across 2 lines lands
  5/5 via FIFO cascade.
- [ ] Hub resolves a shortage and an overage end-to-end, then the session closes and stock +
  `quantity_accepted` reconcile with Phase 4 rules.
- [ ] Scan portal fully usable with keyboard only; silent by default.
- [ ] Tests green; memory.md line added.
