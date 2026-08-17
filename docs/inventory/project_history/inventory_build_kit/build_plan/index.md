# Inventory Application — Phased Build Plan

Executable plan for building `app/inventory/` in `ebams2`: warehouse topography, dock intake engine,
active stock, part movements with the SVG spatial GUI, part issuance, and inventory auditing.

**Read order for any implementation agent picking up a phase:**
1. [`00_source_manifest.md`](00_source_manifest.md) — which sources are authoritative vs reference.
2. [`/fable_decisions.md`](../../fable_decisions.md) — binding conflict resolutions (FD-1…FD-28).
3. Your phase file below, plus the specific kit documents it links.
4. The harness docs your persona file points to (`backend-engineer.md` / `frontend-engineer.md`).

## Phase overview

| Phase | File | Persona lead | Delivers | Depends on |
| :--- | :--- | :--- | :--- | :--- |
| 1 | [`01_phase_topography.md`](01_phase_topography.md) | backend | `Warehouse`, `Room`, `StorageLocation` models + control layer + seeds; `Part.qty_per_scan`/`sn_expected` | — |
| 2 | [`02_phase_active_inventory.md`](02_phase_active_inventory.md) | backend | `ActiveInventory` (serialized grain), `StockLedgerManager`, stock search + list UI | 1 |
| 3 | [`03_phase_svg_spatial_engine.md`](03_phase_svg_spatial_engine.md) | frontend + backend | `RoomSvgAdapter`, Room Layout Builder, spatial map page + location drawer; topography admin UI | 1, 2 |
| 4 | [`04_phase_intake_engine.md`](04_phase_intake_engine.md) | backend | `IntakeSession`, `ItemAllocation`, reconciliation parent+child models, `IntakeCommitOrchestrator`, `ShipmentLine.comments`, line splitting; Auto Intake portal | 2 |
| 5 | [`05_phase_scan_session_and_reconciliation.md`](05_phase_scan_session_and_reconciliation.md) | backend + frontend | Barcode scan engine, FIFO cascade, Reconciliation Hub UI, session lifecycle portal | 4 |
| 6 | [`06_phase_movements_and_issuance.md`](06_phase_movements_and_issuance.md) | backend + frontend | `PartMovement` + movement/putaway portals on the SVG map; `PartIssue` extension + issuance portal + demand-detail rows | 2, 3 (4 for real stock) |
| 7 | [`07_phase_auditing.md`](07_phase_auditing.md) | backend + frontend | `AuditSession`/`AuditSessionLine`/`InventoryAuditLog`, inline edit, staleness badges | 2 (6 for `UNRECORDED_TRANSFER` links) |
| 8 | [`08_phase_hardening.md`](08_phase_hardening.md) | all | Cross-phase tests, seed completeness, docs (`docs/inventory/`), kit archive | 1–7 |

The **UI Review Map** — [`09_ui_review_map.md`](09_ui_review_map.md) — is the steering document:
old-app page vs proposed new page, side by side, per workflow. Review it before Phases 3–7 begin;
redirections there override the phase files' UI sections.

## Ground rules for every phase

- **Schema changes → full reset.** After any model change: `python refresh_project.py` (always-apply
  rule 1). Never stack incremental migrations. Every phase that adds models must also extend
  `seed_dev`-reachable seed data so the reset workflow stays one command.
- **Layer law.** Writes only in `control_layer/`; entrypoints thin; complex reads in
  `presentation_layer/search/` or struct loaders; models are schema+constraints only (FD-14, FD-15).
- **Vocabulary.** Struct / Context / Factory / Handler / Manager / Policy / Validator / StateMachine /
  Narrator / Adaptor / Orchestrator; guards in `*_guard.py`.
- **Quantities:** `DecimalField(max_digits=12, decimal_places=3)` via shared constants (FD-8).
- **Frontend law:** Bulma + HTMX, sharp corners, F5 rule, single canonical URL + `format=` (FD-17),
  no assignment in modals (FD-18), one-page wizards with session drafts (FD-19), cards render when
  empty (always-apply rule 5).
- **Authorization:** two-tier gate everywhere stock is touched — Django permission
  (`inventory.<verb>` perms defined in Phase 1) + effective-domain check via
  `RoomDomainPolicy.effective_domains(room)` (FD-14). Deny before any DB mutation.
- **Naming bans:** `UnassignedInventory`, `InventoryItem`, `PartIssuance` (FD-11, FD-5).
- **Foreign-app schema boundary:** only `Part.qty_per_scan`, `Part.sn_expected`,
  `ShipmentLine.comments` (FD-28) plus procurement control-layer verbs listed in FD-27.
- Each phase ends with its **acceptance checklist** green and a short line appended to
  `dev_tools/memory.md`.

## Handoff protocol

Each phase file is self-contained for one implementation agent: goal, inputs, deliverables (models →
control → search → routes → templates → seeds → tests), acceptance checklist. Phases 3–7 assume the
prior phases' code exists; if an agent finds a mismatch between a phase file and the code, the code
and `fable_decisions.md` win, and the mismatch gets a one-line note in the phase file.
