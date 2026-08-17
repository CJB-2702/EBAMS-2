# Phase 3 Deep-Dive — SVG Spatial Engine Migration Review

**Status:** review document, not an implementation spec. `03_phase_svg_spatial_engine.md` remains the
binding phase file; this document supplements it with a full old-app inventory, a gap/discrepancy list
found by reading the actual legacy source (not just the kit's summary), and an explicit
migrate/rework/drop checklist for you to sign off on before backend-engineer/frontend-engineer start
building. Personas: backend-engineer (adapter/model/route logic) + frontend-engineer (templates/HTMX)
reviewed jointly.

**FD-29 note:** this review predates FD-29 (three-tier spatial engine, `03b_svg_spatial_engine_build_
prompt.md`), which supersedes FD-22 and part of FD-24. References to FD-22/FD-24 below are left as
written (historical record of what was decided at review time) with inline strikethrough/superseded
notes added at the specific items FD-29 changed — item 15 and item 7 in particular flip from
drop/dropped to built.

**Why this file exists:** `svg_gui_mapping_migration.md` and FD-22…FD-25 describe the *target*
architecture and the gaps already caught. Rereading the legacy source directly (not the kit's
paraphrase of it) surfaced a few more mechanical details and one behavioral contradiction worth
flagging before build (see §4).

---

## 1. Old-app source map (`~/REPOS/asset_management`)

The old repo is Flask, not Django — "pages" are `@inventory_bp.route(...)` view functions rendering
Jinja templates, not fixed URLs on a running server. Paths below are file references, grouped by role.

### 1.1 SVG parsing/processing logic — **two independent, inconsistent implementations**

| File | Role | Parser | Used by |
| :--- | :--- | :--- | :--- |
| [`app/intermediate/inventory/locations/storeroom_layout_svg_parser.py`](~/REPOS/asset_management/app/intermediate/inventory/locations/storeroom_layout_svg_parser.py) (`StoreroomLayoutService`) | Parse `locations` layer for validation; **scale SVG to an 800px display box** | BeautifulSoup (`lxml`/`xml`/`html.parser` fallback chain) | `storeroom_visual_portal_tools.py`, `move_inventory_gui.py` preview endpoint |
| [`app/intermediate/inventory/locations/bin_layout_svg_parser.py`](~/REPOS/asset_management/app/intermediate/inventory/locations/bin_layout_svg_parser.py) (`BinLayoutService`) | Same, for the `bins` layer | BeautifulSoup | Declared but **not actually called** from any route found (`create_storeroom_location_from_svg` calls `StoreroomFactory.preprocess_svg` instead — see below). Dead code candidate. |
| [`app/business/inventory/locations/storeroom_factory.py`](~/REPOS/asset_management/app/business/inventory/locations/storeroom_factory.py) (`StoreroomFactory`) | **The actual upload pipeline**: `preprocess_svg()` (clean labels, dedupe-check, responsive viewBox) → create DB rows → `postprocess_svg()` (rewrite element `id`, inject `onclick="locationSelected(123)"`, `data-location-id`, `data-location-name`) | `xml.etree.ElementTree` | `storeroom/routes.py` (`storeroom_create`, `storeroom_upload_layout`, `location_upload_bin_layout`) |

**Finding:** the kit's summary (`svg_gui_mapping_migration.md` §2) describes only the BeautifulSoup
path. The actual upload/create flow runs through a **second, ElementTree-based** implementation with
different behavior (label cleaning + uniqueness validation + ID rewriting that the BS4 path doesn't
do). `RoomSvgAdapter` needs to fold in `StoreroomFactory`'s cleaning/uniqueness/matching logic, not
just the scaling logic — the kit's spec undersells this. `03_phase_svg_spatial_engine.md`'s
`extract_shape_codes()` + `process_and_enrich_svg()` split already covers this correctly in spirit
(extract → reconcile → inject), so no phase-file change needed, just calling this out so the
implementer reads `storeroom_factory.py` directly rather than trusting the kit doc alone.

### 1.2 Routes (`app/presentation/routes/inventory/`)

| File | Routes | Old behavior worth knowing |
| :--- | :--- | :--- |
| [`storeroom/routes.py`](~/REPOS/asset_management/app/presentation/routes/inventory/storeroom/routes.py) | `storeroom_index`, `storeroom_create` (GET/POST, optional SVG on create), `storeroom_build` (GET, HTMX-aware — swaps `build_partials.html`), `storeroom_view_svg` / `storeroom_view_raw_svg` (raw XML `Response`, `image/svg+xml`), `storeroom_view`, `storeroom_edit`, `storeroom_delete` (blocked if `active_inventory.count() > 0`), `storeroom_add_location`, `storeroom_upload_layout`, `location_delete` (blocked if inventory exists), `location_add_bin`, `location_upload_bin_layout`, `bin_delete` | See §4.1 — `storeroom_upload_layout` does **not** delete existing locations despite the UI label claiming it does. |
| [`inventory/move_inventory_gui.py`](~/REPOS/asset_management/app/presentation/routes/inventory/inventory/move_inventory_gui.py) | `move_inventory_gui` (4-step selector, HTMX partial swap on `#destinationSelector`), `submit_move_inventory_gui` (POST, full validation chain), `storeroom_preview_svg` (100×100 thumbnail `Response`, separate raster-ish endpoint) | Selection state fully lives in query params (`major_location_id`, `storeroom`, `location`, `bin`) — F5-safe already. `storeroom_preview_svg` is the dedicated thumbnail endpoint FD-24 replaces. |
| [`_view_builders/storeroom_visual_portal_tools.py`](~/REPOS/asset_management/app/presentation/routes/inventory/_view_builders/storeroom_visual_portal_tools.py) (`StoreroomVisualTools`) | Shared helper: `load_storeroom_locations`, `scale_svg_for_display`, `get_selected_location`, `prepare_bins_list`, `prepare_location_viewer_data`, `prepare_bin_viewer_data` | Cross-cutting glue reused by both `storeroom/build`+`view` and `move_inventory_gui`. `RoomSvgAdapter` + the Phase 3 view/entrypoint should absorb this role. |

### 1.3 Templates (`app/presentation/templates/inventory/`)

| File | Role | Reused by |
| :--- | :--- | :--- |
| [`storeroom/build.html`](~/REPOS/asset_management/app/presentation/templates/inventory/storeroom/build.html) | The SVG **builder/uploader** page — upload form, add-location/add-bin forms, location+bin viewer cascade, `hx-boost` container swap | — (this is the page **Phase 3's "Room Layout Builder" replaces**, FD-23) |
| [`storeroom/view.html`](~/REPOS/asset_management/app/presentation/templates/inventory/storeroom/view.html) | Read-mostly summary: SVG + anchor-scroll to location cards (not HTMX — plain `<a href="#...">` + JS `scrollIntoView`), per-location bin-layout SVG inline, stats badges | — (replaced by the flagship Room detail / spatial map page) |
| [`shared/_location_viewer.html`](~/REPOS/asset_management/app/presentation/templates/inventory/shared/_location_viewer.html) | **The reused viewer partial** — SVG display (⅔) + sidebar cards (⅓), driven by a `mode` param (`htmx`/`anchor`/`js`/`readonly`) and a `card_url_builder` macro passed in from the parent template | `storeroom/build.html` (mode=htmx), `storeroom/view.html` (mode=anchor), `move_inventory_gui.html` (mode=htmx) |
| [`shared/_bin_viewer.html`](~/REPOS/asset_management/app/presentation/templates/inventory/shared/_bin_viewer.html) | Second-tier viewer: bin-layout SVG + bin cards, same `mode` pattern | `storeroom/build.html`, `move_inventory_gui.html` |
| [`shared/_location_card.html`](~/REPOS/asset_management/app/presentation/templates/inventory/shared/_location_card.html), [`shared/_bin_card.html`](~/REPOS/asset_management/app/presentation/templates/inventory/shared/_bin_card.html) | Individual sidebar card partials | included by the two viewers above |
| [`storeroom/build_partials.html`](~/REPOS/asset_management/app/presentation/templates/inventory/storeroom/build_partials.html) | HTMX-only fragment returned when `HX-Request: true` on `/storeroom/<id>/build` | `storeroom_build` route |
| [`storeroom/index.html`](~/REPOS/asset_management/app/presentation/templates/inventory/storeroom/index.html), [`create.html`](~/REPOS/asset_management/app/presentation/templates/inventory/storeroom/create.html), [`edit.html`](~/REPOS/asset_management/app/presentation/templates/inventory/storeroom/edit.html) | Plain CRUD list/create/edit — gradient hero header, inline create-form card on index | — (UI Review Map pages 2–3 already cover the REWORK) |
| [`inventory/move_inventory_gui.html`](~/REPOS/asset_management/app/presentation/templates/inventory/inventory/move_inventory_gui.html) | The 4-step split-screen mover — sticky ⅓ form card + ⅔ progressive selector (major location → storeroom card grid w/ SVG thumbnails → `_location_viewer` → `_bin_viewer`) | — (UI Review Map page 7 already covers the port to Phase 6) |
| [`inventory/move_inventory_gui_partials.html`](~/REPOS/asset_management/app/presentation/templates/inventory/inventory/move_inventory_gui_partials.html) | HTMX fragment for the mover | `move_inventory_gui` route |
| [`inventory/stocking_gui.html`](~/REPOS/asset_management/app/presentation/templates/inventory/inventory/stocking_gui.html), [`inventory/initial_stocking.html`](~/REPOS/asset_management/app/presentation/templates/inventory/inventory/initial_stocking.html) | Putaway flow reusing the same `_location_viewer`/`_bin_viewer` pair, plus a **client-side JS queue that loses state on F5** | — (UI Review Map page 8; belongs to Phase 6 putaway, not Phase 3, but shares the viewer partials so the Phase 3 adapter/CSS work unblocks it) |

### 1.4 Data layer

| File | Fields worth knowing |
| :--- | :--- |
| [`app/data/inventory/inventory/storeroom.py`](~/REPOS/asset_management/app/data/inventory/inventory/storeroom.py) | `raw_svg` (Text, original upload), `svg_content` (Text, processed/scaled/postprocessed) — this is the `Room.svg_layout` analogue, but old system keeps **both** raw and processed; new system per FD-25 archives raw to media storage instead of a DB column |
| [`app/data/inventory/locations/location.py`](~/REPOS/asset_management/app/data/inventory/locations/location.py) | `location` (cleaned label, used as the join key back to SVG), `display_name`, `svg_element_id` (unprefixed then reprefixed `location-<id>` post-processing), `bin_layout_svg` (Text — the **second SVG tier**, one per location) |
| [`app/data/inventory/locations/bin.py`](~/REPOS/asset_management/app/data/inventory/locations/bin.py) | `bin_tag`, `svg_element_id`, unique on `(location_id, bin_tag)` |
| [`app/business/inventory/locations/storeroom_context.py`](~/REPOS/asset_management/app/business/inventory/locations/storeroom_context.py) | `add_location`/`remove_location` (blocks delete if `ActiveInventory` rows reference the location) — the delete-guard concept to carry into `StorageLocation` removal in the new system |
| [`app/business/inventory/storeroom_validation.py`](~/REPOS/asset_management/app/business/inventory/storeroom_validation.py) | Just a storeroom/major-location consistency check — no SVG-specific validation, confirms FD-25 is filling a real gap, not duplicating one |

### 1.5 Already confirmed present in `ebams2` (grounding check before planning further)

- [app/inventory/models/topography/room.py](app/inventory/models/topography/room.py) — `Room.svg_layout` (`TextField`) already exists; docstring already says "populated later by the Phase 3 room-layout builder."
- [app/inventory/models/topography/storage_location.py](app/inventory/models/topography/storage_location.py) — `major_coord`/`minor_coord`/`atomic_coord`/`display_code` already exist (Phase 1 built these).
- [app/inventory/control_layer/adapters/coordinate_adaptor.py](app/inventory/control_layer/adapters/coordinate_adaptor.py) — the `10 → 0010` zero-pad adaptor referenced by `09_ui_review_map.md` §4 already exists.
- `app/inventory/control_layer/adapters/room_svg_adapter.py` — **does not exist yet.** No warehouse/room templates exist yet either (`app/inventory/templates/inventory/` only has `active_inventory/`, `shipments/`, `base.html`, `home.html`). Phase 3 is starting from a clean slate on the frontend side; only the data model and coordinate adapter are pre-built.

---

## 2. What Phase 3 must reproduce vs. deliberately break from

This restates `09_ui_review_map.md` pages 1–4 and FD-17/22/23/24/25 in checklist form, cross-checked
against the source above.

### 2.1 Reproduce (KEEP the interaction concept)

- [ ] Click an SVG shape → detail panel updates without full navigation (old: JS `onclick` + `htmx.ajax()` manual call; new: native `hx-get`/`hx-target`/`hx-swap` per FD-17 — no custom JS needed).
- [ ] Selection state survives F5 (old: query params on `move_inventory_gui`, already F5-safe; `storeroom/build.html` used the same pattern; new: `?format=htmx-location-drawer&loc=<code>` full-render fallback).
- [ ] SVG responsively fills its container (old: `viewBox` + `width:100%`/height-auto scaling in `StoreroomLayoutService.scale_svg_for_display`; new: `RoomSvgAdapter` viewBox normalization, same idea, CSS-driven instead of inline `style=`).
- [ ] Shape → location match by label (old: `inkscape:label` on `<g id="locations">` children, `id` fallback; new: same source convention, matched against `display_code` instead of a free-text `location` string).
- [ ] Storeroom/Room card grid shows a live layout thumbnail when selecting a destination in the mover (old: dedicated `/storeroom-preview/<id>` endpoint scaling to 100×100; new: FD-24 — reuse the same sanitized `svg_layout` inline, CSS max-height, no separate endpoint).
- [ ] Upload workflow only replaces the layout after review, not blind — the **old system's actual code already doesn't delete locations on upload** (see §4.1) so "safe reconciliation" is a strict improvement in UX (a real preview/confirm step) more than a data-safety fix; still valuable, still build it.
- [ ] Manual "add a location that has no shape yet" escape hatch (old: `storeroom_add_location` form on the build page; new: add-location form card on room detail, per `09_ui_review_map.md` §4 point 4).
- [ ] Delete-location guard when active inventory exists (old: `StoreroomContext.remove_location` raises; new: equivalent guard belongs on the `StorageLocation` deletion path — confirm this exists/will exist in `RoomPolicy`/location manager, it's not explicitly named in `03_phase_svg_spatial_engine.md`).

### 2.2 Deliberately rework (concept kept, mechanics changed — already decided by FD-17/22/23/24/25)

- [ ] `hx-get` targets the canonical room URL + `format=` query, not a bespoke `.../drawer/` route (FD-17).
- [ ] Reconciliation-before-save on upload, replacing "just parse and go" (FD-23) — even though the old code didn't actually delete on upload, it also had **no undo/preview**: a bad SVG (wrong labels) silently created wrong locations with no review step. The reconciliation screen fixes a real gap either way.
- [ ] Sanitization is explicit and enforced (FD-25) — **the old system has none**: `ET.fromstring()` on raw user-uploaded XML, no size cap, no tag/attribute stripping, output later rendered with `|safe` in Jinja. This is a genuine XXE/script-injection exposure in the legacy app. Treat FD-25 as a security fix, not just a spec clarification.
- [ ] ~~Two-level drill-down (shape → shelf list → bin) collapses into one SVG tier with prefix-match fallback, instead of a second per-location SVG file (FD-22).~~ **Superseded by FD-29**: the two-level drill-down is built as two real image tiers (Room SVG → RoomLocation, RoomLocation SVG → StorageLocation), exact-match only — see item 15 below, now **P** not **D**.
- [ ] `onclick="locationSelected(123)"` + manual `htmx.ajax()` JS glue is dropped entirely in favor of native `hx-*` attributes (implied by FD-17 + the project's HTMX-first convention — no custom JS file needed for click handling, unlike old `move_inventory_gui.html`'s ~190 lines of selection/highlighting JS).
- [ ] CSS-class-based stock-state fill (`node-empty`/`node-has-stock`/`node-audit-stale`) replaces the old system's binary selected/unselected `fill: #ca3535 !important` inline-JS recoloring — old had no stock-density visualization on the map at all, this is new capability, not a port.

### 2.3 Explicitly drop (do not build)

- [ ] ~~**Per-location second-tier bin-layout SVG** (`Location.bin_layout_svg`, `_bin_viewer.html`, `location_upload_bin_layout` route, `BinLayoutService`) — FD-22 defers this to tech debt. The atomic (Z) coordinate choice happens in the drawer's location list instead of a second drawing.~~ **Superseded by FD-29** — this is un-deferred and built as the RoomLocation-tier Z-picker. Moved out of this section; see item 15.
- [ ] Separate raster-ish thumbnail endpoint (`storeroom_preview_svg`) — FD-24, inline reuse instead. (Still dropped — FD-29 doesn't touch this one.)
- [ ] `raw_svg` as a queryable DB column with its own `view-raw-svg` route — FD-25 archives the raw upload to media storage instead (still retrievable, just not a live DB text column with its own view route).
- [ ] The dead `BinLayoutService` (`bin_layout_svg_parser.py`) — confirmed unused by any live route in the old app; nothing to port, just noting it existed so it isn't mistaken for something that needs an equivalent.
- [ ] `onclick`-attribute injection into SVG markup (`postprocess_svg`'s `element.set('onclick', ...)`) — CSP-unfriendly and superseded by `hx-get`; FD-25's sanitizer should strip `on*` attributes anyway, which would strip this if it were still being generated.
- [ ] Anchor-scroll read-only mode (`storeroom/view.html`'s `mode='anchor'`, `scrollToLocationCard()`) — superseded by the drawer pattern; no read-only non-interactive variant is needed once every viewer is HTMX-driven.

---

## 3. Explicit migration checklist (for your review/sign-off)

Legend: **P** = port behavior, **R** = rework per FD decision, **D** = drop, **N** = net-new (no old equivalent).

| # | Item | Old reference | Verdict | Notes |
|---|------|---------------|:---:|-------|
| 1 | Parse `<g id/inkscape:label="locations">` children for shape codes | `storeroom_layout_svg_parser.py`, `storeroom_factory.py` | **P** | Consolidate the two old implementations into one `RoomSvgAdapter.extract_shape_codes()` |
| 2 | Label cleaning (spaces→dashes, strip apostrophes) | `StoreroomFactory._clean_label` | **P** | Still needed since Inkscape labels are free text; feed into `display_code`/prefix matching |
| 3 | Duplicate-label rejection | `StoreroomFactory.preprocess_svg` | **P** | Surface as a reconciliation-screen error, not a hard 500 |
| 4 | viewBox normalization + 100%-width responsive scaling | `scale_svg_for_display`, `_format_svg_for_display` | **P** | Per FD spec in `03_phase_svg_spatial_engine.md` §Backend adapter |
| 5 | Sanitize script/event-handler/external-ref XML | *(none — gap)* | **N** | FD-25; net-new security work, not a port |
| 6 | Exact shape-code → StorageLocation match | `postprocess_svg` label→id map | **P** | Adjusted to match `display_code` instead of raw `location` string |
| 7 | ~~Prefix (major_coord) → rack-level group match~~ | *(none — old had no prefix concept)* | **DROPPED** | Was FD-22's answer to the dropped second SVG tier; **superseded by FD-29** — the second tier is no longer dropped, so this fallback is never built. Shape matching is exact-only at every tier. |
| 8 | Inject click interactivity | `onclick` + JS `htmx.ajax()` | **R** | Native `hx-get`/`hx-target`/`hx-swap` (FD-17) |
| 9 | Stock-state visual fill on shapes | *(none)* | **N** | `node-empty`/`node-has-stock`/`node-audit-stale` classes |
| 10 | Raw upload retained for re-processing | `Storeroom.raw_svg` column | **R** | Archived to media storage, not a DB text column (FD-25) |
| 11 | Upload → auto-create locations, no confirm step | `storeroom_upload_layout` route | **R** | Reconciliation screen added (FD-23) — see §4.1 for the actual old delete behavior |
| 12 | Manual add-location form (shape-less locations) | `storeroom_add_location` | **P** | On room detail per UI Review Map §4 |
| 13 | Delete-location guard (blocks if inventory exists) | `StoreroomContext.remove_location` | **P** | Confirm equivalent guard exists for `StorageLocation` (see open question in §5) |
| 14 | Storeroom/Room card grid thumbnail | `storeroom_preview_svg` (100×100 raster endpoint) | **R** | Inline sanitized SVG reuse, CSS-scaled (FD-24) |
| 15 | Per-location bin-layout SVG (2nd tier) | `Location.bin_layout_svg`, `_bin_viewer.html`, `BinLayoutService` | **P** | **Un-deferred by FD-29** (supersedes FD-22): built as the RoomLocation-tier Z-picker (`RoomLocation.photo_gallery`/`current_layout`), not dropped |
| 16 | View raw/processed SVG in a new tab | `storeroom_view_svg`/`storeroom_view_raw_svg` routes | **D** | No stated replacement — flag in §5 if you want a lightweight "download/view current layout" link kept on the builder page |
| 17 | Anchor-scroll readonly viewer mode | `storeroom/view.html` `mode='anchor'` | **D** | Drawer pattern replaces it everywhere |
| 18 | 4-step query-param-driven mover (major location → storeroom cards → location viewer → bin viewer) | `move_inventory_gui.html` | **R** | Phase 6 scope, not Phase 3, but reuses the SVG map + card-grid work Phase 3 produces (Warehouse → Room → shape-click); bin step (4) is dropped per item 15 |
| 19 | Client-side JS selection queue in putaway (loses state on F5) | `stocking_gui.html`, `initial_stocking.html` | **R** | Phase 6 scope; session-backed draft (FD-19) instead of client JS |

---

## 4. Discrepancies found worth flagging before you sign off

### 4.1 The "upload deletes locations" claim doesn't match the code

`03_phase_svg_spatial_engine.md`'s acceptance checklist states: *"contrast: old system deleted
locations on upload; that behavior is **not** kept."* `09_ui_review_map.md` §4 calls this a "Hazard."
The `build.html` template's upload form even carries the label **"Delete current locations and bins
and upload new."**

Reading the actual route (`storeroom/routes.py::storeroom_upload_layout`, lines 301–381) — it does
**not** delete anything. It builds a set of `existing_locations` keyed by cleaned label, then for each
label in the new SVG: if the label is new, it creates a location; if the label already exists, it
just updates that location's `svg_element_id` in place. Nothing is ever deleted. Old locations whose
labels are absent from the new SVG are silently **orphaned** (kept in the DB, no longer matched to any
shape) — not deleted.

**This doesn't change the Phase 3 decision** (a reconciliation/confirm screen before commit is still
strictly better UX than silent auto-create-or-update), but the *reason* changes: the risk being fixed
is "no visibility into what an upload will do" and "silent orphaning," not "silent deletion." Recommend
correcting the acceptance-checklist wording so nobody re-derives a delete-guard that isn't needed, and
confirming the reconciliation screen's "orphaned locations" list (already in the phase file, `list —
no shape, kept, informational`) is understood as the fix for the *actual* old bug (silent orphaning),
not a fix for data loss that was never actually happening.

**Action needed from you:** confirm no change to `03_phase_svg_spatial_engine.md` is wanted beyond
this wording note, or say if you want the acceptance checklist line corrected.

### 4.2 Two independent SVG-parsing code paths in the old app

Covered in §1.1 — `StoreroomLayoutService` (BeautifulSoup, read-side scaling/validation) and
`StoreroomFactory` (ElementTree, write-side clean/create/postprocess) never share code and drift
independently (e.g., only `StoreroomFactory` cleans labels; only `StoreroomLayoutService` does the
800px scale-to-fit math). `RoomSvgAdapter` should be a single implementation covering both concerns
(BeautifulSoup, per FD-25's dependency choice) so this drift can't recur.

### 4.3 `BinLayoutService` appears to be dead code

No route in `storeroom/routes.py` calls `BinLayoutService.parse_svg_bins`; bin-layout uploads go
through `StoreroomFactory.preprocess_svg(..., location_or_bin="bin")` instead. Moot given item 15 is
dropped anyway, but worth knowing so it isn't mistaken for a currently-used feature when skimming the
old repo.

### 4.4 No stated replacement for "view raw/processed SVG in a new tab"

`storeroom_view_svg`/`storeroom_view_raw_svg` (debug/inspection links, `Response(..., mimetype=
'image/svg+xml')`) have no counterpart mentioned anywhere in the kit, FD list, or UI Review Map. Minor,
but a real feature a developer uploading layouts might miss. See open question in §5.

---

## 5. Open questions for you before backend/frontend start building

1. **§4.1 wording** — OK to leave `03_phase_svg_spatial_engine.md`'s acceptance-checklist line as-is
   (still directionally correct — old system's behavior around upload *was* unsafe, just via silent
   orphaning rather than deletion), or do you want it corrected for accuracy?
2. **Item 16** — do you want a lightweight "view current raw/processed SVG" link kept on the Room
   Layout Builder page (debug/support value), or is that fully out of scope?
3. **Item 13** — confirm whether a delete-guard for `StorageLocation` (blocking delete when
   stock/audit rows reference it) already exists elsewhere in the Phase 1/2 build, or needs to be
   added as part of Phase 3's location-management card.
4. **Dependency addition** — `beautifulsoup4` + `lxml` (both used by the old app already) need adding
   to `requirements`; confirm no objection before backend-engineer starts (should be routine, flagging
   per repo convention of calling out new deps).

---

## 6. Suggested next step

Once you've resolved §5, hand `03_phase_svg_spatial_engine.md` (unchanged, still the binding spec) plus
this review doc to backend-engineer for `RoomSvgAdapter` + `TopographyContext.upload_room_layout`, and
frontend-engineer for the four Phase 3 pages. No changes to the phase file are proposed here unless you
want the §4.1 wording fix.
