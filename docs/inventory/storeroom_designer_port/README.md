---
okf_version: "0.1"
type: "Technical Decision"
title: "Storeroom Designer Port"
description: "Port record for the legacy Flask storeroom designer into the EBAMS-2 inventory topography: route map, what changed on purpose, and what was skipped."
tags: [inventory, topography, port, legacy]
created: 2026-08-24
created_by: Christian Bissett
updated: 2026-08-24
updated_by: Christian Bissett
---

# Storeroom Designer Port

Port of the legacy Flask storeroom designer (`/inventory/storeroom/*` in
`~/REPOS/asset_management`) into the EBAMS-2 inventory topography.

- [data_model_comparison.md](data_model_comparison.md) — legacy vs new schema, field by field, and every behavioural rule that changed.
- [sequence_diagrams.md](sequence_diagrams.md) — mermaid sequences for warehouse CRUD, both layout uploads, and the two stock rejections.
- [page_catalog.md](page_catalog.md) — legacy page anatomy, card by card.
- `legacy_ui/screenshots/` — the legacy pages as captured on 2026-08-24.
- `new_ui/screenshots/` — the ported pages.

## Route map

| Legacy route | EBAMS-2 route | Note |
| :--- | :--- | :--- |
| `GET /inventory/storeroom/index` | `GET /inventory/warehouses/` + `GET /inventory/warehouse/<pk>/` | Legacy conflated "list of storerooms" with "create a storeroom". Split: warehouses list at the index, rooms live on their warehouse's detail page. |
| `GET|POST /inventory/storeroom/create` | `GET|POST /inventory/warehouses/create/` (warehouse)<br/>`POST /inventory/warehouse/<pk>/` action=`add_room` (room) | Creating a warehouse also provisions its Intake Room. |
| `GET /inventory/storeroom/<id>/view` | `GET /inventory/room/<pk>/` | The read surface: map + drill-down drawer + location table. |
| `GET /inventory/storeroom/<id>/build` | `GET|POST /inventory/room/<pk>/layout/` | The write surface. Same three jobs as legacy — see the map, manage locations, upload a layout — plus the reconciliation step legacy did not have. |
| *(bin viewer, second half of `/build`)* | `GET|POST /inventory/room-location/<pk>/layout/` | Its own canonical URL rather than a query param on the parent page. |
| `GET|POST /inventory/storeroom/<id>/edit` | `GET|POST /inventory/warehouse/<pk>/edit/`<br/>`GET|POST /inventory/room/<pk>/edit/` | Split, because the legacy storeroom carried both warehouse-ish fields (address) and room fields (name). |
| `POST /inventory/storeroom/<id>/delete` | `POST /inventory/warehouse/<pk>/edit/` action=`retire` | **Soft delete only.** Reversible via action=`reactivate`. Rooms retire the same way at `/inventory/room/<pk>/edit/`. |
| `POST /inventory/storeroom/<id>/add-location` | `POST /inventory/room/<pk>/layout/` action=`add_location` | |
| `POST /inventory/storeroom/<id>/upload-layout` | `POST /inventory/room/<pk>/layout/` action=`upload` | |
| `POST /inventory/storeroom/location/<id>/delete` | `POST /inventory/room/<pk>/layout/` action=`retire_location` | Soft; refused while stock sits underneath. |
| `POST /inventory/storeroom/location/<id>/add-bin` | `POST /inventory/room-location/<pk>/layout/` action=`add_bin` | |
| `POST /inventory/storeroom/location/<id>/upload-bin-layout` | `POST /inventory/room-location/<pk>/layout/` action=`upload` | |
| `POST /inventory/storeroom/location/bin/<id>/delete` | `POST /inventory/room-location/<pk>/layout/` action=`retire_bin` | Soft; refused while the bin holds stock. |
| `GET /inventory/storeroom/<id>/view-svg` | — | **Skipped.** Served the processed SVG as a raw file download. The layout renders inline on both the detail and builder pages; a second route serving the same bytes is redundant. |
| `GET /inventory/storeroom/<id>/view-raw-svg` | — | **Skipped.** EBAMS-2 does not keep the unsanitized original at all (FD-25). |

## Navigation

The Topography group in both the inventory sidebar
(`app/inventory/templates/inventory/base.html`) and the topnav Inventory popover
(`app/public_app/templates/shared/topnav.html`) carries **Warehouses** and
**New Warehouse**. Everything else the port added is per-record and reached by
drilling in: warehouse detail → room card → **Locations & layout** →
per-location **Bins & layout**. The user-visible names for the two builder
surfaces are deliberately not "layout builder": that label hid the fact that
those pages are also where locations and bins are added and retired.

`New Warehouse` is wrapped in `{% if perms.inventory.can_manage_topography %}`
in both files. That is a departure from the convention in those templates, where
no other portal link is permission-gated — justified because
`warehouse_create` raises `PermissionDenied` outright, so an ungated entry would
be the only nav link in the app that leads to a guaranteed 403. The gate on the
view is what actually enforces access; hiding the link only avoids the dead end.

`warehouses/form.html` overrides `base_topography.html`'s unconditional
`nav_warehouses` block so the create page highlights its own entry while the
edit page keeps highlighting the list.

## Deliberate departures

1. **Nothing is hard-deleted.** Warehouses, rooms, XY locations, and bins all
   retire via `is_active`. The legacy `db.session.delete()` cascade — which
   removed a storeroom's whole location and bin tree — is not ported. Warehouse
   and room retirement are both reversible; `room_detail` deliberately 404s on a
   retired room, so `room_edit` is the surface that loads it and offers
   reactivation.
2. **A replacement layout that would orphan stock is rejected**, not accepted
   with a warning. The check runs before anything is archived.
3. **Bin deletion is guarded.** Legacy had no inventory check on bin deletion at
   all; the check existed only one tier up.
4. **The legacy build page's "Delete Current locations and bins and upload new"
   label described the actual behaviour** — an upload was destructive to the
   operator's mental model even where the code was additive. The new upload is
   explicitly non-destructive and says so.
5. **SVG element IDs are not written back into the file.** Legacy `postprocess_svg`
   rewrote each shape's `id` to its database primary key, which meant the stored
   SVG and the database had to stay in lockstep forever. Matching is by
   `inkscape:label` value instead.
6. **Every write is behind `inventory.can_manage_topography`.** Legacy gated the
   index on a module role and left several write routes on `@login_required`
   alone.

## Bug found and fixed during the port

`RoomSvgAdapter.sanitize` re-serialized Inkscape files with an `svg:` namespace
prefix (`<svg:svg>`, `<svg:rect>`). Inkscape declares the SVG namespace twice —
`xmlns` **and** `xmlns:svg` — and lxml then picks the prefixed form. A browser
parsing `<svg:svg>` inside an HTML document does not resolve it to a real SVG
element, so every Inkscape-authored layout rendered as a flat strip of label
text rather than a map. Since Inkscape is the assumed authoring tool for this
entire feature, this affected every layout in the app.

Fixed in `RoomSvgAdapter._strip_svg_prefix`, applied both on sanitize (new
uploads) and on `normalize_viewbox` (so layouts archived before the fix render
correctly without re-upload). Regression tests in
`app/inventory/tests/test_room_svg_adapter.py::InkscapeNamespacePrefixTests`.

## Tests

- `app/inventory/tests/test_topography_stock_guards.py` — the three stock rules, warehouse CRUD, room retire/reactivate, and the builder POST actions (22 tests).
- `app/inventory/tests/test_room_svg_adapter.py` — sanitization including the namespace-prefix regression.
- `app/inventory/tests/test_svg_upload_reconciliation.py` — reconciliation buckets (pre-existing, still green).
