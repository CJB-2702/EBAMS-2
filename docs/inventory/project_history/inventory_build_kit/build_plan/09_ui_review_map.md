# UI Review Map — Old App vs Proposed New App, Page by Page

**Purpose:** this is the steering document. Each numbered page pairs the OLD implementation
(`asset_management/app/presentation/templates/…`, Flask + Bootstrap, observed behavior) with the
proposed NEW page (Bulma + HTMX per `harness/UX_UI/`). Redirect individual pages here; phase files
defer to this document for UI. OLD entries describe what the page *does*, including the parts we are
deliberately not keeping. NEW entries cite the phase that builds them.

Legend for verdicts: **KEEP** (interaction concept retained), **REWORK** (concept retained, mechanics
changed to meet harness law), **REPLACE** (old workflow discarded — new-system docs govern).

---

## 1. Inventory landing

**OLD — `inventory/index.html`**
- Link-hub page of buttons/cards into arrivals, active inventory, issue parts, storerooms, POs.
- No live data; navigation only.

**NEW — `/inventory/` (Phase 2)** — verdict: KEEP (shape), REWORK (content)
```
[ Stock ]  [ Intake ]      ← cards with live counts (on-hand rows, open sessions)
[ Movements ] [ Issues ]   ← recent-activity minis
[ Audits ] [ Warehouses ]
```
- Every card always renders (rule 5), shows count badges and one primary action.
- Breadcrumb root for the whole app.

---

## 2. Storeroom index → Warehouse index

**OLD — `storeroom/index.html`**
- Gradient hero header; left column "Create New Storeroom" inline form card (name, major location,
  address); right: card per storeroom with badges (major location, location count, item count) and
  buttons View / Build / Edit / Delete (JS confirm + hidden form).
- Flat list of storerooms across all major locations.

**NEW — `/inventory/warehouses` + `/inventory/warehouse/<id>` (Phase 3)** — verdict: REWORK
- Two-tier topography replaces the flat list: warehouse table (condensed default: name, code,
  division, domain chips, room count, active) → warehouse detail.
- Warehouse detail:
```
[ Warehouse facts card ][ Domain chips card ]
[ Rooms card: row per room — name, Intake badge, location count, SVG thumbnail, → detail/builder ]
[ Add Room form card ]
```
- Create is a wizard route (`/inventory/warehouses/create`, FD-19): facts → domain dual-listbox →
  optional rooms. No inline create-card on the index (creation populates M2M domains — wizard rule).
- Delete: modal confirm (destructive — allowed), blocked by `RoomPolicy`/stock guards with reason.
- Intake Room appears with a lock icon; rename/delete controls absent for it.

---

## 3. Storeroom create / edit → Room forms

**OLD — `storeroom/create.html`, `storeroom/edit.html`**
- Plain form pages (name, major location, address; edit adds Danger Zone delete card).

**NEW (Phase 3)** — verdict: KEEP (simple forms stay simple)
- Room add/edit as form cards on the warehouse detail page (no dedicated create page — a Room is one
  FK + strings, not wizard-worthy). Danger-zone equivalent: deactivate/delete buttons in the card
  footer per `form_style_guide.md`, guarded server-side.

---

## 4. Storeroom build → Room Layout Builder

**OLD — `storeroom/build.html`** (the SVG heart, tier 1)
- Header actions: View Processed SVG / View Raw SVG (new tab), View Summary, Edit, Back.
- Location Viewer card: left ⅔ SVG display area (processed `svg_content`), right ⅓ location cards
  sidebar + **Add Location** form; card footer: *"Delete current locations and bins and upload
  new"* SVG file input.
- Clicking an SVG shape (`data-location-id`) or a sidebar card selects a location — page state via
  query params, HTMX `hx-boost` + `hx-select` re-render of the whole selector container.
- When a location is selected: second **Bin Viewer** card appears (location's `bin_layout_svg`,
  bin cards, Add Bin form, bin-layout upload footer).
- Hazard: uploading a new SVG **deletes existing locations/bins** first.

**NEW — `/inventory/room/<id>/layout` (Phase 3)** — verdict: KEEP concept / REWORK mechanics
```
[ Upload card: file input · current layout preview · raw/processed links ]
[ Reconciliation card (after upload, before save):
    ├ Matched shapes  → location list (green)
    ├ Unmatched shapes → checkbox rows, coordinate prefill, "Create selected" (BulkFactory)
    └ Orphaned locations → listed, kept (no silent delete)                       ]
[ Storage locations card: table + add-location form (X/Y/Z inputs, live pad preview 10→0010) ]
```
- **Deliberate change:** upload never deletes locations (FD-23) — the reconciliation step replaces
  the old destructive re-upload.
- **Deliberate change:** one SVG tier. The old per-location bin-layout SVG is not rebuilt (FD-22);
  atomic (Z) choice happens in the map drawer instead. Recorded as tech debt if missed in practice.
- Sanitization per FD-25; raw upload archived to media.

---

## 5. Storeroom view → Room detail / spatial map

**OLD — `storeroom/view.html`**
- Gradient hero; SVG display area with location highlight; sidebar location cards; selecting shows
  bins (bin cards + bin layout SVG); read-mostly summary with inventory glimpses.

**NEW — `/inventory/room/<id>` (Phase 3; flagship)** — verdict: KEEP
```
[ Room header card: name · warehouse · effective-domain chips · Intake badge ]
[ Spatial map card (⅔)                 ][ #location-detail-drawer card (⅓)  ]
[   processed SVG, shapes clickable    ][  empty: "Click a location…"       ]
[   fill = stock state:                ][  loaded: display code, coords,    ]
[   empty / has-stock / audit-stale    ][  stock rows (part·qty·serial·     ]
[                                      ][  staleness), links: move/putaway  ]
[ Storage locations table card (filterable)                                  ]
```
- Shape click = HTMX drawer swap via `?format=htmx-location-drawer&loc=<code>` (FD-17); the same URL
  with `?loc=` renders the drawer server-side on F5.
- Prefix-coded shapes (rack-level) list all child locations in the drawer (FD-22).
- Old two-card location→bin cascade collapses into the single drawer.

---

## 6. Active inventory view → Active inventory list

**OLD — `inventory/active_inventory_view.html`**
- Filters card (part number/name, major location→storeroom dependent dropdowns, search) → GET.
- Table: Part, Major Location, Storeroom, Location, Bin, On Hand, Allocated, Available, Avg Cost,
  Last Movement, Actions.
- Actions: **Move (Bootstrap modal** with dropdowns), link to Move GUI page, **Discard (modal)**.

**NEW — `/inventory/active-inventory` (Phase 2, enriched 6–7)** — verdict: REWORK
- Same filter-card + table shape (condensed default; `format=` densities), columns:
  Part | Warehouse | Room | Location | Serial | On hand | Allocated | Available | Avg cost |
  **Last audited badge** | Actions.
- **Deliberate change:** the move-in-modal is gone (FD-18). Actions = `Move` → movement portal
  (p.7), `Issue` → issuance portal (p.9), inline qty edit (p.12), `Discard` keeps its confirm modal
  (destructive — allowed) but executes as an audit adjustment (DAMAGE_SCRAP) so nothing vanishes
  unlogged.
- Serialized rows show serial chips; unassigned intake-room rows show an `Unassigned` tag linking to
  putaway.

---

## 7. Move Inventory GUI → Movement portal

**OLD — `inventory/move_inventory_gui.html`** (the SVG workflow you liked most)
- Left ⅓ sticky **Move Details** card: part, available qty, source path, qty input (pre-filled max),
  disabled destination echo fields, hidden ids, submit (disabled until location chosen).
- Right ⅔ **Destination Selector** card, 4 progressive steps in one container:
  1. Major location dropdown (submits GET),
  2. storeroom **card grid with SVG thumbnails**,
  3. location step = shared `_location_viewer` (SVG ⅔ + location cards ⅓) — **clicking an SVG shape
     selects the location** (delegated JS → `htmx.ajax` re-render of selector+form, pushState),
  4. bin step = `_bin_viewer` with Skip-Bin option; selected shapes recolored (red location / blue
     bin).
- Whole state lives in query params → back/F5-safe. "Change X" buttons walk back a step.

**NEW — `/inventory/movements/create?stock=<id>` (Phase 6)** — verdict: KEEP (this exact feel)
```
[ Move details card (⅓, sticky) ][ Destination selector card (⅔)            ]
[  part · serial · available    ][  Step chips: Warehouse › Room › Location ]
[  qty input (max-capped)       ][  1 Warehouse cards (SVG thumbnails)      ]
[  source path                  ][  2 Room cards (SVG thumbnails)           ]
[  destination echo (read-only) ][  3 Room SVG map — click shape to select  ]
[  [Move] (progressive enable)  ][    (?format=htmx-putaway-target)         ]
```
- Selection state in GET params exactly as old (F5 rule already satisfied there — kept).
- Bulma cards replace Bootstrap; sharp corners; step-back links kept ("Change room" etc.).
- Old step 4 (bin SVG) folds into the drawer: clicking a rack-prefix shape lists atomic locations to
  pick; exact-coded shapes select directly. Skip-location putaway is not offered here (destination
  must be a StorageLocation; intake-room drops happen via inter-warehouse moves automatically).
- Serialized stock: qty input locks to 1.000 with the serial shown.

---

## 8. Initial stocking + Stocking GUI → Putaway worklist

**OLD — `inventory/initial_stocking.html` + `stocking_gui.html`**
- Two-page flow. Page 1: search unassigned inventory (HTMX dependent dropdowns
  major-location→storeroom, part search), results → build a queue (client-side), then either
  "classic" dropdown stocking (storeroom→location→bin selects) or jump to Stocking GUI.
- Page 2 (`stocking_gui`): items table with checkboxes; location viewer (SVG + location cards, JS
  select); optional bin viewer; Selection Summary card; submit builds movements. Selection state
  partly client-side JS (breaks on F5).

**NEW — `/inventory/putaway` (Phase 6)** — verdict: REWORK into one page
```
[ Warehouse select card ]
[ Unassigned stock card (left) ][ Destination selector (right)              ]
[  filter · checkbox rows      ][  Room cards → SVG map, click to target    ]
[  (intake-room rows only)     ][  target echo + per-batch qty confirm      ]
[ Batch summary card: N items → location · [Put away] ]
```
- One canonical URL, one sitting, session-draft for the selection set (FD-19) — F5-safe where the
  old page lost its JS queue.
- The old "classic dropdown" alternative is dropped; the SVG selector with a plain
  select-fallback (no-JS baseline: destination select list) covers both audiences.
- Each row becomes a PUTAWAY `PartMovement`; serialized rows carry their serial visibly.

---

## 9. Issue Parts → Issuance portal

**OLD — `inventory/issue_parts.html`**
- Filters card; paginated available-inventory table with checkbox rows; **Issue Queue** card fed by
  checkboxes (client-side); **Link to Part Demands** card: selected queue item + approval-state
  filter + tabs (*By Maintenance Event ID* / *By Part ID*) to search demands and link; then issue
  submission (recipient user/asset). Heavy client-side state; F5 loses the queue; workflow was
  admittedly never fully thought through.

**NEW — `/inventory/issues/create` (Phase 6)** — verdict: REPLACE (workflow), KEEP (queue feel)
- Demand-first (primary, from procurement demand page `?demand=<id>`):
```
[ Demand summary card: part · required · already issued (full rows w/ serials) ]
[ Eligible stock card: rows for that part (location, available, serial) — pick + qty ]
[ Confirm card: recipient (defaults from demand) · notes · [Issue] ]
```
- Stock-first (from a stock row `?stock=<id>`): recipient section is an in-page assignment card
  pair — search demands (approved filter kept from old UI) / or direct-to-asset / direct-to-user
  selects (FD-5 issue types). **No tabs-in-modal, no client-only queue** — draft lines persist in
  session (FD-19) and render as a queue card that survives F5.
- Old approval-state filter concept is kept as a demand-search filter.

---

## 10. Part issues list / detail / edit → Issues ledger

**OLD — `part_issues_list.html`, `part_issue_detail.html`, `part_issue_edit.html`**
- List: filters + table (ID, date, part, type badge, issued-to, demand, asset, qty, cost, issuer,
  actions). Detail: info/part/location/movement/recipients/audit cards; link to demand lifecycle.
  Edit: notes-and-details form with read-only core.

**NEW — `/inventory/issues`, `/inventory/issue/<id>` (Phase 6)** — verdict: KEEP
- Same ledger shape; adds Serial column and signed-quantity rendering (returns show negative in red
  with a `Return` chip). Detail cards: issue facts, stock provenance (warehouse/room/location/serial,
  unit cost at issue), recipient, linked movement, demand link.
- **Deliberate change:** no edit page for quantities — an issue row is immutable history; corrections
  are returns (negative rows) or audit adjustments. Notes remain editable in place.

---

## 11. Movements view → Movements ledger

**OLD — `inventory/movements_view.html`**
- Filters + table: date/time, type, part, qty Δ, location, storeroom, from → to, unit cost,
  reference badges (Arrival #, Issue #).

**NEW — `/inventory/movements`, `/inventory/movement/<id>` (Phase 6)** — verdict: KEEP
- Same ledger: date, movement number, type chip (PUTAWAY / INTER_ROOM / INTER_WAREHOUSE /
  BIN_ADJUSTMENT / CYCLE_COUNT_ADJUSTMENT), part, qty, serial, from → to (warehouse/room/location
  path), actor, reference links (intake session, issue, audit line). Detail page adds narrator
  history card.

---

## 12. (NEW-only) Inline audit & audit portal

**OLD** — no equivalent (quantities were edited nowhere, or via discard/move workarounds).

**NEW — Phase 7** — pages per `07_phase_auditing.md`: audit dashboard, count portal (fast entry +
variance chips), inline row edit on the stock table (single-field capture; stealth session), audit
log ledger, staleness badges. Steer here freely — this is the least legacy-anchored UI.

---

## 13. Arrivals portal → Intake dashboard / Auto Intake / Scan session

**OLD — `inventory/arrivals/*` (creation portal, linkage portal, header form, unlinked-part modal,
big `arrivals_creation_portal.js`)**
- Single ArrivalHeader mixing carrier data with receiving; JS state machine builds lines against PO
  lines; unlinked parts added through a modal; dual-linking table to PO lines afterward.
- **Explicitly untrusted** (old-system review §3: conflated responsibilities, no blind receiving).

**NEW — Phases 4–5** — verdict: REPLACE entirely (new-system docs govern)
- `/inventory/intake` dashboard: `Auto Intake` + `Scan Session` cards + recent sessions.
- `/inventory/intake/auto`: three stacked zones (session metadata / unfulfilled shipment selector /
  lines matrix with floors, caps, live deltas) per `auto_intake_workflow_guide.md` §2.1 — this is
  the binding UI spec, not the old portal.
- `/inventory/intake/session/<id>`: scan portal (sticky scan input, allocation feed, line progress
  bars, staged/unmanifested card, split control) and lifecycle controls.
- `/inventory/intake/reconciliations` + detail: manager hub with per-line resolution cards (FD-9).
- Nothing from the old arrivals UI is carried except one idea worth keeping: the **always-visible
  lines-summary card** during entry (old `lines_summary.html`) → the Auto Intake delta preview and
  the scan portal's progress card serve that role.
