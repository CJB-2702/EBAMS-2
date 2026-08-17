# Fable Decisions — Inventory Application Build

Decision record produced while converting `inventory_build_kit/` into the phased build plan
(`inventory_build_kit/build_plan/`). Every entry is a conflict found between build-kit documents,
between the kit and this repo's actual code, or between the kit and harness persona guidance
(`.claude/agents/backend-engineer.md`, `.claude/agents/frontend-engineer.md`, `harness/Architecture/`,
`harness/UX_UI/`). Per instruction, these were resolved without stopping to ask; each records the
call made and the reasoning. `inventory_build_kit_review.md` was treated as binding except where it
contradicts code that already exists in this repo.

Numbering is FD-# so implementation agents can cite decisions in commits and code comments.

---

## A. Kit vs. actual repo code

### FD-1 — Part model is `parts.Part`, not `parts.PartDefinition`
Kit documents (`part_movements.md`, `part_issues.md`, `model_migration_plan.md`) FK to
`'parts.PartDefinition'`. The repo has `parts.Part` (`app/parts/models/core/part.py`).
**Decision:** all FKs target `parts.Part`. The kit name is a drafting artifact, not a rename request —
nothing in the review record asks to rename the parts model.

### FD-2 — Domain scoping model is `administration.Domain`, not `administration.DataDomain`
Kit references `DataDomain` throughout. The repo model is `Domain`
(`app/administration/models/data_ownership/domains.py`).
**Decision:** use `administration.Domain` everywhere the kit says `DataDomain`. Same concept, real name.

### FD-3 — `Division` lives in `administration`, not `core_domain`
`model_migration_plan.md` writes `ForeignKey('core_domain.Division', ...)`. The real model is
`app/administration/models/data_ownership/divisions.py`.
**Decision:** `Warehouse.division → administration.Division`.

### FD-4 — User FKs target `administration.User`
Kit files mix `auth.User` and `administration.User`. Existing inventory code (`PartIssue.issued_to`)
uses `administration.User`.
**Decision:** `administration.User` (via string reference) for every operator/actor/recipient FK,
matching the repo's existing convention.

### FD-5 — Keep and extend the existing `PartIssue`; do not create a parallel `PartIssuance`
The kit specs a new `PartIssuance` model (`part_issues.md`, `model_migration_plan.md`). But
`app/inventory/models/issuance/part_issue.py` already exists, with a deliberate design the kit
predates or ignores:

- **signed quantity** (negative row = return; decision D39 in its docstring) — the kit instead has
  only positive `quantity_issued`;
- the **write-path seam**: rows are only created through `PartIssuanceOrchestrator` calling
  `PartDemandContext.record_issuance()` in one transaction (D12);
- `PROTECT` on `part_demand` as the cross-app delete guard (D7).

**Decision:** the build extends `PartIssue` in place rather than introducing `PartIssuance`:
- keep the name, table (`part_issue`), signed-quantity semantics, and orchestrator seam;
- add stock provenance: `active_inventory` FK (PROTECT, null until Phase 6 backfills the workflow),
  `serial_number`, `unit_cost_at_issue`;
- add `issued_to_asset` (nullable FK to `assets.Asset`) and an `issue_type` discriminator
  (`FOR_PART_DEMAND`, `DIRECT_TO_ASSET`, `DIRECT_TO_USER`);
- relax `part_demand` to nullable **only** for direct issues, with a check constraint requiring
  `part_demand` when `issue_type = FOR_PART_DEMAND` and at least one of
  (`part_demand`, `issued_to_asset`, `issued_to`) always set;
- `record_issuance()` is called iff `part_demand` is set; direct issues never touch procurement.

Reasoning: two tables meaning "material left stock" is exactly the alias-purging problem the review's
Decision 9 (`ActiveInventory` exclusively) exists to prevent; and silently discarding the signed-return
convention would orphan an already-shipped procurement seam.

### FD-6 — `ShipmentContext.accept_line` already exists: integrate, don't rebuild
The review specs the seam as future work; `app/procurement/control_layer/shipment_context.py:272`
already implements `accept_line` with validator, lock recompute, and narration.
**Decision:** `IntakeCommitOrchestrator` calls the existing method. Any gap found (e.g. cumulative-total
semantics per FD-10) is fixed inside the procurement control layer with its existing guard/narrator
pattern — never bypassed with raw updates.

### FD-7 — No legacy data ETL
`migrations/model_migration_plan.md` reads like a data-migration runbook (copy `svg_content` into
`Room.svg_layout`, etc.). The old app is a different stack (Flask/SQLAlchemy/Bootstrap) with its own
database, and this repo's dev workflow is wipe-and-reseed (`refresh_project.py`; always-apply rule 1).
**Decision:** the plan treats `model_migration_plan.md` as a **conceptual field-mapping reference
only**. No ETL phase. Legacy SVG files are re-uploaded by hand through the new Room layout builder.
If a production cutover ever needs real data migration, that is a separate future kit.

---

## B. Conflicts inside the build kit

### FD-8 — Decimal precision is `DecimalField(max_digits=12, decimal_places=3)` everywhere
The review (binding, Decision 8) says 3 places with a `DECIMAL_PLACES = 3` constant. Newer new_system
docs (`part_movements.md`, `part_issues.md`, `model_migration_plan.md`) drafted `decimal_places=4`.
`unaccounted_inventory_discrepancies_solution.md` even uses `IntegerField` for audit quantities.
**Decision:** 3 places, everywhere, including audit session lines and logs. Constants module
`app/inventory/control_layer/constants.py` holds `DECIMAL_PLACES = 3` / `MAX_DIGITS = 12`.

### FD-9 — Reconciliation grain is parent + child (`PartReconciliationLine` exists)
`inventory_intake_kit/domain_model.md` (older) models resolution on `PartReconciliationSession`
directly. The review (Decision 4) and `overages_shortages_and_reconciliation.md` (newer) add a child
`PartReconciliationLine` per shipment line to prevent cross-vendor netting.
**Decision:** parent `PartReconciliationSession(intake_session, part)` for the operator's review UI +
child `PartReconciliationLine(reconciliation, shipment_line)` carrying the per-line quantities and
`resolution_type`. The parent's `resolution_type` column from the older doc is dropped; parent status
is derived (`RESOLVED` when all children resolved).

### FD-10 — `IntakeSession` has no `dock_location` FK; Warehouse is the anchor
`domain_model.md` (older) gives the session `dock_location_id FK administration.Location` — a model
that does not exist. The newer architecture docs make `warehouse` mandatory and add optional
`room`.
**Decision:** `IntakeSession.warehouse` (PROTECT, required), `IntakeSession.room` (nullable; when null
the commit targets the warehouse's Intake Room with the standard UI warning), plus
`hardware_device_id`. No dock-location model. Also adopted from the review but missing from the older
table spec: `has_unlinked_allocations = BooleanField(default=False)`.

### FD-11 — Stock table is `ActiveInventory` only; `UnassignedInventory`/`InventoryItem` are purged
`intake_engine_integration.md` and `control_layer_map.md` still mention `UnassignedInventory` and
`InventoryItem`. Review Decision 9 standardizes on `ActiveInventory`.
**Decision:** one table. "Unassigned" is a state (`room = <intake room>`, `storage_location = NULL`,
`is_unassigned = True`), never a table. Implementation agents must not create any model with the
purged names.

### FD-12 — `ActiveInventory` uniqueness includes serial, with `serial_number` stored as `''` not `NULL`
Review Decision 5 + `serialized_inventory_tracking.md` require
`Unique(room, storage_location, part, serial_number)`. In SQL, `NULL != NULL`, so nullable
`serial_number` would let duplicate non-serialized balance rows slip through the constraint —
corrupting the aggregate-row grain. (`nulls_distinct=False` is Postgres-15-only; dev runs SQLite.)
**Decision:** `serial_number = CharField(max_length=200, blank=True, default="")` on `ActiveInventory`
(empty string = non-serialized), keeping the four-column unique constraint enforceable on both
engines. `storage_location` stays a nullable FK; Intake-Room rows rely on the `is_unassigned` flag +
a partial-duplicate guard in the control layer (`StockLedgerManager` is the only writer, inside
`select_for_update`), since NULL storage_location has the same SQL caveat. Serialized rows keep the
`quantity == 1.000` check constraint.

### FD-13 — Intake-side UI split: **Auto Intake portal** is the manual entry point; the scan engine is a later phase
`shipment_to_inventory_gap.md` describes dual buttons ("Intake from Package" quick form vs full
scanning engine). The review (Decision 3) supersedes the quick form with the **Auto Intake portal**
(monotonic floors, delta allocations, `auto_intake_workflow_guide.md`).
**Decision:** the Auto Intake portal *is* Option A — same pseudo-session mechanics, stricter rules.
The dashboard offers `Auto Intake` (built in Phase 4) and `Scan Session` (built in Phase 5; barcode
parsing, FIFO cascade, reconciliation hub). Nothing manual bypasses floors/caps.

### FD-14 — Warehouse Intake-Room auto-provisioning moves out of `Warehouse.save()`
`model_migration_plan.md` overrides `Warehouse.save()` to create the Intake Room — a direct violation
of the repo's "no business logic on models" rule.
**Decision:** `WarehouseFactory.create(...)` in the control layer creates the warehouse and its
protected Intake Room in one transaction; a `RoomPolicy` guard blocks rename/delete of
`is_intake_room` rows. Django admin/shell creation of a Warehouse without its Intake Room is treated
as an invalid state the seed and factory never produce (and a system check can flag).
Same ruling applies to `Room.get_effective_data_domains()`: the set-algebra
(warehouse domains − excluded domains) lives in a control-layer helper
(`RoomDomainPolicy.effective_domains(room)`), not as a model method.

### FD-15 — Audit "stealth session" logic follows the same layer rules
`unaccounted_inventory_discrepancies_solution.md` sketches `execute_inline_quantity_edit` as a bare
function in `control_layer/audit_engine.py`.
**Decision:** same behavior, project vocabulary: `AuditSessionContext` (verbs: `start`, `record_line`,
`finalize`, `inline_edit`) with `AuditNarrator` for log strings and `AuditSessionStateMachine`
guarding `OPEN → COMPLETED/CANCELLED`. `InventoryAuditLog` rows are append-only (no update/delete
paths exposed).

### FD-16 — XYZ coordinate padding is shared, single-sourced
Both `part_movements.md` and the SVG plan restate the 4-digit zero-pad / no-truncate rule.
**Decision:** one function `format_xyz_coordinate` in
`app/inventory/control_layer/adapters/coordinate_adaptor.py`; `StorageLocation.display_code` is
computed by the factory/manager on write (models hold no logic). Everything — movements, SVG shape
matching, putaway forms — imports it.

---

## C. Kit vs. persona / harness guidance (frontend-heavy)

### FD-17 — SVG drawer requests use the canonical-URL `format=` contract, not bespoke drawer routes
`svg_gui_mapping_migration.md` injects `hx-get="/inventory/rooms/{id}/locations/{coord}/drawer/"`.
The frontend rules forbid parallel partial-only routes: one canonical URL + `format=htmx-*`.
**Decision:** injected attributes become
`hx-get="/inventory/room/<id>?format=htmx-location-drawer&loc=<display_code>"`, target
`#location-detail-drawer`. The room page fully renders with the drawer server-side when `loc=` is
present, so F5 restores the exact state (F5 rule). The same pattern serves putaway target selection
(`format=htmx-putaway-target`).

### FD-18 — No assignment or movement flows in modals
The old app moved inventory from a Bootstrap modal on the active-inventory table, and
`part_issues.md` names an "HTMX Issuance Modal". Repo law: assignment never lives in a modal; modals
are destructive confirmations, read-only browsing, single-field captures.
**Decision:** movement and issuance are in-page workflows (movement portal, putaway portal, issuance
portal). Modals allowed only for: discard-stock confirmation, allocation delete confirmation, and the
single-field inline quantity edit (which may instead render as an inline row form — implementer's
choice, both compliant).

### FD-19 — Multi-record creation flows are single-URL long-page wizards
Intake scan sessions, auto intake, putaway, and issuance each populate multiple child rows in one
sitting → per `multi_step_flows.md` they are one-page multi-card wizards with progressive enablement
and session-backed drafts. The old app's step-chained URLs (`move_inventory_gui` re-loading with
query-param state) and the legacy arrivals portal's JS state machine are **not** carried over.
Query params on the movement GUI remain acceptable for *selection state* (they satisfy F5), but each
flow keeps a single canonical route.

### FD-20 — The kit's route sketches are non-binding; endpoint patterns win
Kit URLs (`/inventory/intake/auto/commit/`, `/inventory/issuance/execute/`, etc.) predate the route
conventions. **Decision:** final routes follow `endpoint_patterns.md`
(collection plural / singular detail / `format=` variants); the build plan's route tables are the
authoritative list, and POST verbs land on the resource URL, not on `/execute/`-style RPC paths.

### FD-21 — Sound effects on scan events are kept but optional-progressive
`control_layer_map.md` mentions chime/beep on scan. Harness has no rule against it; it aids blind
receiving. **Decision:** keep as a small static JS enhancement gated behind a user toggle stored in
`localStorage`; page fully functions silent (F5/no-JS baseline unaffected).

---

## D. Gaps found in `svg_gui_mapping_migration.md` (flagged, as instructed, not re-derived)

### FD-22 — SUPERSEDED by FD-29 — The plan covers only ONE SVG tier; the old system had two
Old app: storeroom SVG → click a **location**; then each location could carry its own
`bin_layout_svg` → click a **bin** (see `_location_viewer.html` / `_bin_viewer.html` pairing in
`move_inventory_gui.html` steps 3–4). The migration plan maps only `Room.svg_layout` with shapes →
`StorageLocation` display codes.
**Decision:** Phase 3 ships the single-tier map: an SVG shape may address either a **full display
code** (`0010-0005-0001` → exact StorageLocation) or a **major-coordinate prefix** (`0010` → the
drawer lists all storage locations under that rack/aisle). This reproduces the practical two-level
drill-down (shape → shelf list → bin choice) inside the drawer without a second SVG document. A
per-location second-tier SVG (`StorageLocation`-level layout) is recorded as deferred tech debt, not
built.

### FD-23 — The plan omits the SVG **builder/uploader** workflow entirely
The old `storeroom/build.html` page (upload SVG → parse `locations` layer → auto-create location rows;
add-location/add-bin side forms; raw vs processed SVG views) has no counterpart in the migration plan,
which only describes rendering an already-stored layout.
**Decision:** the build plan adds a **Room Layout Builder** page (Phase 3): SVG upload →
`RoomSvgAdapter.extract_shape_codes()` → reconcile screen (shapes matched to existing
StorageLocations, unmatched shapes offered for bulk creation via `StorageLocationBulkFactory`,
orphaned locations listed) → save stores sanitized SVG on `Room.svg_layout`. Raw upload is archived to
media storage per the plan's step 6.1.

### FD-24 — SUPERSEDED in part by FD-29 — The plan omits thumbnails/previews used by the old selection grid
The old move GUI's storeroom card grid rendered per-storeroom SVG thumbnails
(`storeroom_preview_svg`). **Decision:** the room-cards grid in the new movement portal reuses the
sanitized `svg_layout` inline, CSS-scaled (`max-height` box, `viewBox` already normalized by the
adapter) — no separate preview endpoint, no raster conversion.

### FD-25 — Sanitization requirements made explicit
The plan says "sanitizes XML & strips malicious tags" without a spec. **Decision:** `RoomSvgAdapter`
strips `<script>`, `<foreignObject>`, event-handler attributes (`on*`), and external references
(`href`/`xlink:href` to non-`#` targets); rejects files > 2 MB; output is the only thing ever stored
or rendered with `|safe`. BeautifulSoup + `lxml` is an accepted new dependency (it's what the legacy
parser used).

---

## E. Scope rulings

### FD-26 — Cross-session excess pulling is deferred inside Phase 5
`intake_engine_integration.md` includes pulling overage allocations from another session into a
shortage. It is real scope but is the most stateful, least-specified corner of reconciliation.
**Decision:** the data model supports it from day one (allocations are session-FK'd and reassignable);
the UI/manager verb (`pull_external_allocation`) is the final work item of Phase 5 and may slip to a
follow-up without blocking session close (a shortage is then simply `accepted_shortage`).

### FD-27 — Shipment-line splitting on partial receipt is procurement-side work
`overages_shortages_and_reconciliation.md` §1.2 requires splitting a shipment line when a partial
receipt commits. That mutates procurement models, so it belongs to the procurement control layer
(`ShipmentLineManager.split_line`), invoked via a new `ShipmentContext` verb — implemented in Phase 4
alongside the commit orchestrator, with the same guard/narrator treatment as `accept_line`.

### FD-28 — `Part.qty_per_scan` / `Part.sn_expected` and `ShipmentLine.comments` are the only foreign-app schema changes
Confirming the kit's intent as a hard boundary for implementation agents: the inventory build may add
these three columns (Phase 1 / Phase 4 respectively, full DB reset per always-apply rule 1) and
nothing else outside `app/inventory/`.

---

## F. Post-hoc scope change (decided in a later planning conversation, build prompt `03b_svg_spatial_engine_build_prompt.md`)

### FD-29 — Three-tier SVG spatial engine, superseding FD-22's prefix-match single tier and FD-24's "why" (not its conclusion)
FD-22 shipped Phase 3 as a single SVG tier: a Room map where shapes match a `StorageLocation.
display_code` exactly, or a `major_coord` prefix (the drawer then lists all child locations as text).
A follow-up planning conversation (not itself a kit document — see the build prompt) decided this
under-delivers relative to the old app's actual two-level drill-down (location shape → bin shape) and
re-scoped the build before it started, so no application code built under FD-22's original shape ever
shipped — this is a pre-implementation course correction, not a migration of live behavior.

**Decision:** ship three tiers of **image-driven, exact-match-only** selection instead of one tier with
a prefix-match fallback:

1. **Warehouse → Room** — image grid of room thumbnails (`Room.photo_gallery`/`current_layout`, an
   `events.FileSet` gallery pair mirroring `Asset.photo_gallery`/`primary_image`, replacing the flat
   `Room.svg_layout` text column). FD-24's conclusion — reuse the sanitized layout inline, CSS-scaled,
   no separate preview endpoint — is **unchanged**; only the field it reads from changed shape.
2. **Room SVG → RoomLocation** — a new `RoomLocation` model (`room` FK, `major_coord`/`minor_coord`,
   XY-only `display_code`) sits between `Room` and `StorageLocation`. A Room-tier shape resolves to
   **exactly one** `RoomLocation` by exact `display_code` match — no prefix matching, no drawer text
   list standing in for a second image.
3. **RoomLocation SVG → StorageLocation** — `RoomLocation` carries its own `photo_gallery`/
   `current_layout` pair (the old app's dropped second SVG tier, `Location.bin_layout_svg`/
   `_bin_viewer.html`, un-deferred). A shape on that image resolves to exactly one `StorageLocation` by
   exact `atomic_coord` match. `StorageLocation` drops its own `major_coord`/`minor_coord` columns
   entirely (single source of truth moves to `RoomLocation`) and gains a `room_location` FK in their
   place; `display_code` is still the full 3-segment string end users see
   (`build_storage_location_display_code` composes it from the parent `RoomLocation.display_code` +
   `atomic_coord`, both routed through the shared `format_xyz_coordinate` per FD-16).

**UX shortcut, not separately specified elsewhere:** a `RoomLocation` with no `current_layout` and
exactly one child `StorageLocation` skips straight to the stock drawer — no pointless third click when
there is nothing to disambiguate.

**Reconciliation (FD-23) and sanitization (FD-25) are unchanged in spec, only doubled in application**:
`RoomSvgAdapter` sanitizes/extracts/reconciles identically at both tiers (`locations` group label for
Room-tier uploads, `bins` group label for RoomLocation-tier uploads — same adapter, no drift between
two parsers per 03a's discrepancy note #4.2). `TopographyContext.upload_room_layout` and
`upload_room_location_layout` are the two entrypoints; both archive only the *sanitized* SVG (the raw
upload is never persisted at all, which is stricter than FD-25's original "output is the only thing
ever rendered `|safe`" — here it is also the only thing ever stored).

**Reasoning:** the single-tier prefix-match design traded a real second image for a text list inside
the drawer — cheaper to build, but it throws away the old app's actual best-liked interaction (click a
shelf shape, then click a bin shape) for a fallback the old app never had. Since no code had shipped
under FD-22 yet, restoring the two-image drill-down cost a schema level (`RoomLocation`) rather than a
migration.
