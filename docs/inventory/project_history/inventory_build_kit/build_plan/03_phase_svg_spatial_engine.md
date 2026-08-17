# Phase 3 — SVG Spatial Engine & Topography UI (frontend + backend)

**Persona:** frontend-engineer leads; backend-engineer builds the adapter and schema.
**Kit inputs:** `new_system/svg_gui_mapping_migration.md` (starting point, mechanics reference only —
its single-tier scope is superseded), old-app templates (`storeroom/build.html`, `storeroom/view.html`,
`_location_viewer.html`, `_bin_viewer.html`) as **visual reference only**.
**Decisions in force:** FD-17, FD-23, FD-25, FD-29 (FD-29 supersedes FD-22 and, in part, FD-24 — see
that entry in `fable_decisions.md` for the full reasoning); UI Review Map pages 1–4.

**Rewritten in place** per `03b_svg_spatial_engine_build_prompt.md` — the original single-SVG-tier
scope (FD-22's prefix-match drawer) never shipped any application code; this rewrite reflects the
architecture actually built, not a migration of live behavior.

## Goal
The retained centerpiece of the old system, rebuilt on Bulma+HTMX: three tiers of image-driven,
exact-match navigation — Warehouse → Room (image grid of room thumbnails), Room SVG → RoomLocation
(click a shape, exact XY match), RoomLocation SVG → StorageLocation (click a shape on that location's
own picker image, exact Z match) — ending in a server-rendered stock drawer.

## Schema (FD-29)

- `Room` — dropped `svg_layout` (TextField). Added `photo_gallery` (`OneToOneField → events.FileSet`,
  nullable, lazy) + `current_layout` (`ForeignKey → events.Attachment`, nullable) — same shape as
  `Asset.photo_gallery`/`primary_image`.
- **New `RoomLocation`** (`app/inventory/models/topography/room_location.py`) — `room` FK,
  `major_coord`/`minor_coord`, XY-only `display_code`, its own `photo_gallery`/`current_layout` pair
  for the Tier-3 Z-picker image. Unique on `(room, major_coord, minor_coord)`.
- `StorageLocation` — dropped `major_coord`/`minor_coord`; gained `room_location` FK. `display_code`
  is still the full 3-segment string (`RoomLocation.display_code` + `-` + `atomic_coord`), computed via
  `coordinate_adaptor.build_storage_location_display_code`. A `.room` property proxies
  `room_location.room` for the many call sites that read it.
- `coordinate_adaptor.py` — split into `build_room_location_display_code(major, minor)` and
  `build_storage_location_display_code(room_location_code, atomic)`, both still routed through the
  shared `format_xyz_coordinate` (FD-16, unchanged).

## Deliverables

### Backend: `control_layer/adapters/room_svg_adapter.py` (`RoomSvgAdapter`)
One implementation, parameterized by Inkscape group label, used at both tiers (03a's discrepancy note
#4.2 — never two independently-drifting parsers):
- **`sanitize(raw_svg) -> str`** (FD-25): strips `<script>`, `<foreignObject>`, `on*` attributes,
  external `href`/`xlink:href`; only sanitized output is ever stored or rendered — the raw upload
  itself is never persisted at all (stricter than FD-25's original wording).
- **`check_upload_size(raw_bytes)`**: rejects > 2 MB.
- **`normalize_viewbox(svg) -> str`**: ensures `viewBox`, sets `width=100%`, adds `room-svg-canvas`.
- **`extract_shape_codes(svg, group_label) -> list[str]`**: shape labels from
  `<g id|inkscape:label="{group_label}">` children — `"locations"` for the Room tier, `"bins"` for the
  RoomLocation tier — `inkscape:label` preferred, `id` fallback.
- **`render_interactive_svg(svg, group_label, shape_targets, canonical_url, format_param,
  drawer_target)`**: normalizes + injects `hx-get="<canonical_url>?format=<format_param>&loc=<code>"`,
  `hx-target="#<drawer_target>"`, `hx-swap="innerHTML"` (FD-17) onto every shape whose code **exactly**
  matches a `shape_targets` key. No prefix matching anywhere (FD-29 supersedes FD-22). Unmatched shapes
  get `node-empty`; matched get `node-has-stock`.
- Dependency: `beautifulsoup4` + `lxml`, added to `requirements.txt`.

### Backend: layout persistence + reconciliation (`TopographyContext`)
- `upload_room_layout(room_id, uploaded_file, actor)` — sanitize, extract Room-tier shapes, diff
  against existing `RoomLocation.display_code`s, archive the *sanitized* SVG as the room's
  `current_layout` via `events.GalleryManager`, return an `SvgReconciliationStruct` (`matched`,
  `unmatched_shapes`, `orphaned`). No auto-create/delete.
- `upload_room_location_layout(room_location_id, uploaded_file, actor)` — same shape, reconciles
  against `StorageLocation.atomic_coord` within that RoomLocation.
- `add_room_location`/`bulk_add_room_locations` and `add_storage_location`/`bulk_add_storage_locations`
  (signature now takes `room_location_id` + `atomic_coord`) are the "create selected unmatched shapes"
  seam the reconciliation screen calls.

### Pages (all sharp-cornered Bulma cards; every card renders when empty)

1. **Warehouse index** — `/inventory/warehouses/` — table of active warehouses.
   Warehouse detail `/inventory/warehouse/<id>/`: facts card, rooms card (each room row: name, intake
   lock icon, room-location count, inline sanitized-SVG thumbnail from `current_layout` — FD-24's "no
   separate preview endpoint" conclusion, unchanged — and a link to that room's layout builder).
2. **Room detail / spatial map** — `/inventory/room/<id>/` — the Tier-1→2 page. Left ⅔: Room-tier
   interactive SVG. Right ⅓: `#location-detail-drawer` — empty-state prompt; on shape click (or on
   full-page load with `?loc=<RoomLocation.display_code>` — **F5 rule**) shows: a link into the
   Z-picker when the RoomLocation has a `current_layout`; the stock drawer directly when it has exactly
   one child `StorageLocation` and no Z-picker (the "skip tier 3" shortcut); otherwise a plain list of
   its `StorageLocation`s. Below the map: a table of every RoomLocation with its storage-location count
   and Z-picker link.
3. **Room layout builder** — `/inventory/room/<id>/layout/` — upload card (file input, PRG POST) +
   reconciliation card (matched / unmatched shapes as checkbox rows feeding
   `bulk_add_room_locations` / orphaned, informational) — draft held in
   `request.session` keyed per room, cleared on "Create selected" or "Dismiss".
4. **RoomLocation Z-picker** — `/inventory/room-location/<id>/` — the Tier-2→3 page, structurally
   identical to the Room detail page one level down: interactive Z-picker SVG left, `#storage-detail-
   drawer` right (stock rows on shape click, `?loc=<atomic_coord>` F5-safe), table of storage locations
   below.
5. **RoomLocation layout builder** — `/inventory/room-location/<id>/layout/` — same upload +
   reconciliation shape as (3), reconciling against `StorageLocation.atomic_coord` and calling
   `bulk_add_storage_locations`.

**Not built this pass (unchanged from the original kit's backlog, not part of `03b`'s scope):**
storage-location/room-location manual add forms beyond the reconciliation "create selected" path, and
the warehouse-create wizard (`/inventory/warehouses/create`) — warehouses/rooms are still provisioned
through `TopographyContext`/`WarehouseFactory` (seed command, shell, or a future admin UI), not a
dedicated creation page.

### CSS (`app/static/css/inventory_svg.css`)
Sharp corners, `.spatial-node` hover/stroke states, `.node-empty`/`.node-has-stock`/`.node-audit-stale`
fills, `.room-thumbnail` scaling for the warehouse-detail grid. No rounded anything.

### Tests
- `test_room_svg_adapter.py` — sanitization (script/handler/external-ref strip, oversized reject),
  viewBox normalization, exact-only shape-code extraction, HTMX attribute injection (confirms no
  prefix-match leak).
- `test_svg_upload_reconciliation.py` — reconciliation-bucket correctness at both tiers against real
  `TopographyContext` calls with an in-memory upload; confirms only sanitized content is archived;
  confirms upload never creates/deletes RoomLocations by itself.
- `test_topography.py` — updated for the `RoomLocation` schema (uniqueness at both new tiers,
  `RoomPolicy.check_delete` now also blocked by existing RoomLocations).
- Fixtures: `app/inventory/tests/fixtures/room_layout_los_angeles.svg` (7 Room-tier shapes, relabeled
  to zero-padded `RoomLocation.display_code`s) and `room_location_layout_bins.svg` (9 RoomLocation-tier
  shapes, relabeled to zero-padded `atomic_coord`s) — both real Inkscape files from the legacy app's
  dev-seed data, relabeled per the new coordinate convention.

## Acceptance checklist
- [x] Seeded room with fixture SVG: clicking a shape swaps the drawer without reload; F5 on the URL
  reproduces the same drawer state — verified at both tiers.
- [x] Uploading a new SVG never orphan-deletes locations silently — reconciliation screen is the only
  path (contrast: old system deleted locations on upload; that behavior is **not** kept).
- [x] No parallel drawer route exists (`grep -rn "drawer" app/inventory/urls.py` → nothing).
- [x] Warehouse detail room-cards grid renders each room's thumbnail from its gallery `current_layout`,
  no separate preview endpoint.
- [x] Room detail: clicking a shape resolves to exactly one `RoomLocation` (no prefix/multi-match
  ambiguity).
- [x] RoomLocation with a Z-picker image: clicking a shape resolves to exactly one `StorageLocation`.
- [x] RoomLocation with no Z-picker image and exactly one child `StorageLocation`: drawer shows stock
  directly, no dead-end third click.
- [x] Sanitization (FD-25's spec) applies identically to Room-tier and RoomLocation-tier uploads.
- [x] Upload-then-reconcile screen exists at both tiers, matching FD-23's existing spec
  (matched/unmatched/orphaned).
- [x] `refresh_project.py` run cleanly; `seed_inventory_dev.py` produces a Room ("Spatial Map Demo")
  with a real, working two-image spatial map.
- [x] Old Phase 1 tests (`test_topography.py`) updated and green against the new `RoomLocation` shape.
- [x] New adapter/reconciliation tests using the two relabeled fixture SVGs.
- [x] `dev_tools/memory.md` line added per repo convention.
- [ ] Storage-location/room-location manual add forms and the warehouse-create wizard — deferred,
  out of `03b`'s scope.
