# Example SVG Layouts (`_dev`)

This directory contains standardized, clean SVG layouts designed for the **EBAMS-2 SVG Spatial Engine** (`RoomSvgAdapter`).

## SVG Spatial Engine Layer Conventions

Per **FD-25** and **FD-29**, the spatial engine parses Inkscape layer groups and maps child shapes (`rect`, `path`, `g`, `circle`, `polygon`) directly to database topography records via exact code matching:

### 1. Room Tier (Tier 1 → Tier 2 Spatial Map)
- **Inkscape Layer / Group**: `<g id="locations" inkscape:label="locations">`
- **Target Record**: `RoomLocation.display_code` (e.g. `0001-0001` or `MAJOR-MINOR`).
- **Interactive Attribute Injected**: `hx-get="/inventory/room/<id>/?format=htmx-location-drawer&loc=<display_code>"`
- **Example File**: `_dev/6x4_grid_room_layout.svg` (24 room locations), `_dev/aisle_shelf_room_layout.svg` (20 aisle/shelf locations).

### 2. RoomLocation Tier / Z-Picker (Tier 2 → Tier 3 Spatial Map)
- **Inkscape Layer / Group**: `<g id="bins" inkscape:label="bins">`
- **Target Record**: `StorageLocation.atomic_coord` (e.g. `0001` to `0025`).
- **Interactive Attribute Injected**: `hx-get="/inventory/room-location/<id>/?format=htmx-storage-drawer&loc=<atomic_coord>"`
- **Example File**: `_dev/5x5_grid_bins_layout.svg` (25 bin storage locations).

## Included Layouts

1. **`6x4_grid_room_layout.svg`**: A 6cols x 4rows matrix (24 cells) labeled `0001-0001` through `0004-0006`. Used for matrix room layouts.
2. **`5x5_grid_bins_layout.svg`**: A 5x5 matrix (25 bins) labeled `0001` through `0025`. Used for Z-picker rack layouts.
3. **`aisle_shelf_room_layout.svg`**: 4 storage aisles (A1–A4) each containing 5 rack locations (`0001-0001` .. `0004-0005`).

## How to Upload via Layout Builder
1. Navigate to any Room or RoomLocation in the Inventory app.
2. Click **Layout builder**.
3. Choose one of the SVG files from `_dev/`.
4. Review the reconciliation output (matched, unmatched, orphaned shapes).
5. Click **Create selected** to automatically provision missing locations in the database.
