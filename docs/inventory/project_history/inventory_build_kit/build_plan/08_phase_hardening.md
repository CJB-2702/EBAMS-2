# Phase 8 — Hardening, Documentation & Kit Closure

**Persona:** all (code-architect review pass recommended). **Depends on:** Phases 1–7.

## Goal
The application is trustworthy after any full reset, documented for future sessions, and the planning
kit is retired properly.

## Work items

### 1. Cross-phase invariant tests (`app/inventory/tests/test_invariants.py`)
- **Conservation:** for the full seed run, per part:
  `Σ intake GOOD allocations − Σ issues (signed) ± audit variances == Σ ActiveInventory.quantity_on_hand`,
  and movements net to zero.
- **Seam exclusivity:** static greps asserted in tests — no `ActiveInventory` writes outside
  `StockLedgerManager`; no `quantity_accepted` writes outside procurement's manager; no `PartIssue`
  creation outside `PartIssuanceOrchestrator`.
- **Serialized integrity:** every non-empty serial appears at most once across live stock; every
  serialized stock row has `quantity_on_hand ∈ {0, 1}`.
- **Reconciliation barrier** and **domain-gate** end-to-end negatives.

### 2. Seed & demo completeness
One command (`python refresh_project.py`) yields a demo covering: two scoped warehouses, SVG-mapped
room, unassigned + located + serialized stock, one shipment in every intake state, a RECONCILING
session, movements of all four types, issues of all three types + a return, audits fresh/stale/never.
Verify with the dev-login skill walkthrough of every page in `09_ui_review_map.md`.

### 3. Performance pass
- `select_related`/`prefetch_related` on every list search (stock, movements, issues, sessions).
- SVG adapter output cached on the Room row (invalidate on layout upload or stock-state change of
  its locations — a `processed_svg_stale` flag is acceptable).
- Pagination on every ledger.

### 4. Accessibility & UX sweep
Breadcrumbs on every page incl. errors; `<h1>` per page; keyboard path through scan portal, drawer,
and wizards; WCAG AA on the spatial-map state colors (add pattern/border cues so stock state is not
color-only).

### 5. Documentation
- `docs/inventory.md` + `docs/inventory/` (incidents/, project_history/, tech_debt/,
  decisions_pending/ skeleton) — domain summary, model graph, seam map (ledger, accept_line,
  record_issuance), pointers to FD decisions.
- Tech debt entries: per-location second-tier SVG (FD-22), cross-session pulling if slipped (FD-26),
  RMA queue integration, reservation/allocation engine (quantity_allocated is stored but no
  reservation workflow ships in this build).
- `docs/context_bundles/inventory.md` quick loader.

### 6. Kit closure
- Back-propagate any rule changes discovered during the build into `inventory_build_kit/` (starter
  material is durable), then archive via
  `/kit-complete inventory inventory_build_kit "<summary>"`.
- Delete `inventory_build_kit/build_plan/` UI-phase scaffolding? **No** — the build_plan folder is
  part of the kit archive; the UI Review Map is superseded by the built app (front-end-kit lifecycle
  rule: the application is the truth).

## Acceptance checklist
- [ ] Fresh clone → `refresh_project.py` → every route in the UI map reachable and populated.
- [ ] Invariant suite green in CI-equivalent local run.
- [ ] `docs/inventory/` exists and indexes the FD record.
- [ ] Kit archived; memory.md closing line added.
