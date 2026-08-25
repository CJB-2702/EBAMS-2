---
okf_version: "0.1"
type: "Reference"
title: "Storeroom Designer — Legacy Page Catalog"
description: "Card-by-card anatomy of the four legacy storeroom designer pages, with the screenshot for each and where its content landed in EBAMS-2."
tags: [inventory, topography, port, legacy, ui]
created: 2026-08-24
created_by: Christian Bissett
updated: 2026-08-24
updated_by: Christian Bissett
---

# Storeroom Designer — Legacy Page Catalog

Captured 2026-08-24 against the legacy Flask app on port 5000, logged in as
`admin`. Screenshots in `legacy_ui/screenshots/`; the manifest with HTTP status
and page titles is `legacy_ui/screenshots/_manifest.json`.

Seed state at capture: two storerooms (`main_storeroom` with 7 locations / 9
bins / a layout SVG, `annex_storeroom` empty), zero active inventory rows —
which is why none of the legacy stock guards are visible in the screenshots.

---

## `/inventory/storeroom/index` — Storerooms

`00_storeroom_index.png`

| Card | Contents | Landed in EBAMS-2 as |
| :--- | :--- | :--- |
| Purple page banner | "STOREROOMS / Manage and organize your inventory storage locations" | Standard `page-hero` on the warehouse index. |
| **Create New Storeroom** | Storeroom name, Major Location select, Address/Notes textarea, Create button. Sits above the list. | Split: warehouse fields → `/inventory/warehouses/create/`; room name → the "Add a room" card on warehouse detail. |
| One card per storeroom | Major location + address, badge row (`ID`, `N Locations`, `N Bins`, `Has Layout`), created/updated timestamps, then four actions: View Summary, Build & Manage, Edit, **Delete**. Right rail shows the layout thumbnail, or a "Layout Update Pending" hourglass when there is none. | Warehouse index table (name / code / division / room count / status) → warehouse detail, where each room card carries its own thumbnail, a Locations & layout button, and Edit. **Delete is not ported** — retirement lives on the edit page. |

## `/inventory/storeroom/create` — Create Storeroom

`01_storeroom_create.png`

Standalone version of the index's create card, plus an optional SVG file input
that would create the storeroom and parse its locations in one shot. EBAMS-2
separates creation from layout upload: a room is created empty, then its layout
is uploaded on the builder page where the reconciliation result can actually be
reviewed.

## `/inventory/storeroom/<id>/view` — Summary

`02_storeroom_1_view.png`, `06_storeroom_2_view_no_svg.png`

| Card | Contents | Landed in EBAMS-2 as |
| :--- | :--- | :--- |
| Header | Name, major location, "Build & Manage" button. | Room detail `page-hero` with "Locations & layout" + "Edit room". |
| Three stat tiles | Locations / Total Bins / Inventory Items. | Not ported as tiles; the counts are in the locations table and the warehouse facts rail. Worth revisiting. |
| **location Viewer** | Read-only map on the left, clickable location list on the right (each entry showing `ID: n` and a bin count). | Room detail's Room map card + the location drawer. |
| **Locations** grid | One card per location, each embedding its own bin-layout SVG and bin list, or a "No bin layout SVG uploaded yet" / "No bins found" empty state. | The `Storage locations` table plus a per-location Z-picker page. Deliberately not a grid of embedded SVGs — that page grew unbounded with location count. |

## `/inventory/storeroom/<id>/build` — Storeroom Designer

`03_storeroom_1_build.png`, `04_storeroom_1_build_loc3.png` (a location selected),
`07_storeroom_2_build_no_svg.png` (empty state)

This is the page the port is named after.

| Card | Contents | Landed in EBAMS-2 as |
| :--- | :--- | :--- |
| Header actions | View Processed SVG, View Raw SVG, View Summary, Edit Storeroom, Back to List. | Spatial map link + breadcrumbs. The two raw-SVG routes are skipped (see README). |
| **location Viewer** | Interactive map; clicking a shape selects that location (highlighted red in `04`). Right pane lists locations with `ID: n` badges and bin counts, then an **Add Location** form (Location ID + Display Name). | The Locations & layout page: `Current layout` card on the left, `Locations` table + "Add a location manually" on the right. The two-field Location ID / Display Name pair collapses to one coordinate field, since `display_code` is now derived. |
| Upload strip | *"Delete Current locations and bins and upload new:"* file input + Upload, plus Processed/Raw SVG buttons. | `Upload layout` card — explicitly **non**-destructive, followed by the reconciliation card, which legacy had no equivalent of. |
| **Bin Viewer `<code>`** | Appears only once a location is selected. Bin-layout SVG on the left, bin list with `ID: n` badges on the right, **Add Bin** (Bin Tag) form, and a *"Delete current Bins and upload new layout"* strip. | Its own page at `/inventory/room-location/<pk>/layout/`, same three-part shape. |

Note the two hidden `<form id="deleteLocationForm">` / `<form id="deleteBinForm">`
elements in `build.html` — the delete routes existed but had no visible trigger
in the rendered page at capture time.

## `/inventory/storeroom/<id>/edit` — Edit Storeroom

`05_storeroom_1_edit.png`

| Card | Contents | Landed in EBAMS-2 as |
| :--- | :--- | :--- |
| Form | Storeroom Name, Major Location select, Address/Notes, Cancel + Save Changes. Changing the major location is refused when inventory exists. | Split across warehouse edit (code, address, division, domains) and room edit (name, description, excluded domains). Division is fixed after creation rather than conditionally blocked. |
| **Danger Zone** (red) | *"This will permanently delete the storeroom, all its locations, and all bins. This action cannot be undone."* + Delete Storeroom, behind a JS `confirm()`. | Replaced by a **Lifecycle** card: Retire / Reactivate, no confirm dialog needed because nothing is destroyed. |
