# SVG Spatial Mapping & Visual GUI Migration Plan

This document explicitly details the migration of the **Storeroom Visual GUI & SVG Layout Mapping System** from legacy `asset_management` to the `ebams2` architecture.

---

## 1. Executive Summary & Architecture Evolution

In legacy `asset_management`, the interactive SVG layout viewer was a core visual feature allowing staff to view storeroom maps, click interactive rack/shelf shapes, and manage bin inventory visually.

In `ebams2`, this feature is refactored into a high-performance **HTMX-driven Spatial Mapping Engine**:

- **Model Alignment**: `Storeroom.svg_content` ──► `Room.svg_layout` (under `app/inventory/models/room.py`).
- **Coordinate Mapping**: SVG shape identifiers map directly to standardized `StorageLocation` 3D XYZ coordinates (`major_coord`, `minor_coord`, `atomic_coord` formatted as 4-digit zero-padded strings).
- **HTMX Server-Driven Interactivity**: Raw SVG markup is processed by a Control Layer adapter that injects `hx-get`, `hx-target`, and `hx-swap` attributes directly onto SVG element nodes (`<rect>`, `<path>`, `<g>`). Clicking a shelf on the interactive SVG instantly swaps out the location detail drawer without heavy JavaScript frameworks.

---

## 2. Legacy System Analysis (`asset_management`)

### Legacy Model & Service Setup
- **Storage**: `Storeroom.raw_svg` (original uploaded XML) and `Storeroom.svg_content` (scaled layout XML).
- **Parsing Logic (`StoreroomLayoutService`)**:
  - Parsed XML using BeautifulSoup / `lxml`.
  - Searched for an Inkscape layer group: `<g inkscape:label="locations">` or `<g id="locations">`.
  - Extracted child elements (`<rect>`, `<path>`, `<g>`) containing `inkscape:label` or `id` attributes.
  - Paired label strings with legacy `Location` records in the database.
  - Scaled height/width to fit an 800px display box while injecting inline styles.

---

## 3. Target System Architecture (`ebams2`)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LEGACY INKSCAPE SVG FILE                        │
│  <g id="locations">                                                    │
│    <rect id="loc_0010_0005_0001" inkscape:label="0010-0005-0001" />    │
│  </g>                                                                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    │ Upload & Processing
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│            CONTROL LAYER ADAPTER (`RoomSvgAdapter`)                    │
│  1. Sanitizes XML & Strips Malicious Tags                              │
│  2. Scales viewBox to 100% Responsive Aspect Ratio                     │
│  3. Matches element IDs to StorageLocation XYZ Coordinates             │
│  4. Injects HTMX Attributes onto SVG Location Nodes                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    │ Renders Server-Side Fragment
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   BULMA + HTMX VISUAL PORTAL                           │
│  <svg class="room-spatial-map" viewBox="0 0 1200 800">                 │
│    <rect id="loc_0010_0005_0001"                                      │
│          class="spatial-location-node stock-active"                    │
│          hx-get="/inventory/locations/0010-0005-0001/drawer/"          │
│          hx-target="#spatial-location-drawer"                          │
│          hx-swap="innerHTML" />                                        │
│  </svg>                                                                │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Control Layer Adapter Specification

All SVG parsing, sanitization, scaling, and attribute injection reside in the control layer under `app/inventory/control_layer/adapters/room_svg_adapter.py`.

```python
# app/inventory/control_layer/adapters/room_svg_adapter.py

from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional

class RoomSvgAdapter:
    """Control Layer adapter for parsing, scaling, and enriching Room SVG layouts."""

    @staticmethod
    def process_and_enrich_svg(
        raw_svg: str,
        room_id: int,
        location_stock_map: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Parses raw SVG XML, scales dimensions for responsive Bulma containers,
        and injects HTMX interactivity attributes onto storage location shapes.
        """
        if not raw_svg:
            return ""

        soup = BeautifulSoup(raw_svg, 'xml')
        svg_node = soup.find('svg')
        if not svg_node:
            return raw_svg

        # 1. Responsive ViewBox Scaling
        if not svg_node.get('viewBox') and svg_node.get('width') and svg_node.get('height'):
            w = svg_node['width'].replace('px', '')
            h = svg_node['height'].replace('px', '')
            svg_node['viewBox'] = f"0 0 {w} {h}"
        
        svg_node['width'] = "100%"
        svg_node['height'] = "auto"
        svg_node['class'] = svg_node.get('class', '') + " room-svg-canvas"

        # 2. Locate "locations" Layer Group
        locations_group = soup.find('g', id='locations') or soup.find('g', attrs={'inkscape:label': 'locations'})
        if not locations_group:
            return str(soup)

        # 3. Enrich Child Location Nodes with HTMX Data Attributes
        for element in locations_group.find_all(['rect', 'path', 'g'], recursive=False):
            coord_code = element.get('inkscape:label') or element.get('id')
            if not coord_code:
                continue

            # Standardize string coordinate matching (e.g. "0010-0005-0001")
            stock_info = location_stock_map.get(coord_code)

            # CSS Class assignment based on stock density & audit status
            classes = ["spatial-node"]
            if stock_info:
                if stock_info.get('has_stock'):
                    classes.append("node-has-stock")
                if stock_info.get('is_stale_audit'):
                    classes.append("node-audit-stale")
            else:
                classes.append("node-empty")

            element['class'] = " ".join(classes)
            element['cursor'] = "pointer"

            # Inject HTMX Data Attributes for Server-Driven Swap
            element['hx-get'] = f"/inventory/rooms/{room_id}/locations/{coord_code}/drawer/"
            element['hx-target'] = "#location-detail-drawer"
            element['hx-swap'] = "innerHTML"
            element['hx-trigger'] = "click"

        return str(soup)
```

---

## 5. Frontend Visual Portal (Bulma + HTMX Conventions)

Following `AGENTS.md` and `docs/UX_UI.md` sharp-corner aesthetic guidelines:

### CSS Styling (`app/static/css/inventory_svg.css`)
```css
/* Sharp-cornered SVG canvas styling */
.room-svg-canvas {
    border: 1px solid var(--bulma-border);
    background-color: var(--bulma-scheme-main-ter);
    border-radius: 0 !important;
}

/* Interactive SVG Node States */
.spatial-node {
    transition: fill 0.15s ease, stroke 0.15s ease;
    stroke: var(--bulma-border-dark);
    stroke-width: 1px;
}

.spatial-node:hover {
    stroke: var(--bulma-link);
    stroke-width: 2px;
    filter: brightness(1.15);
}

.node-empty {
    fill: #e2e8f0;
}

.node-has-stock {
    fill: #3b82f6; /* Blue indicator for active stock */
}

.node-audit-stale {
    fill: #f59e0b; /* Warning amber indicator for stale audit stock */
}
```

### HTMX Template Layout (`app/inventory/templates/inventory/room_spatial_map.html`)
```html
<div class="columns is-gapless">
    <!-- Interactive SVG Room Map (Left 8 Columns) -->
    <div class="column is-8">
        <div class="box is-radiusless p-2">
            <h3 class="title is-6 is-uppercase">{{ room.room_name }} — Spatial Map</h3>
            <div id="svg-canvas-wrapper">
                {{ processed_svg|safe }}
            </div>
        </div>
    </div>

    <!-- HTMX Swappable Location Detail Drawer (Right 4 Columns) -->
    <div class="column is-4">
        <div id="location-detail-drawer" class="box is-radiusless ml-2">
            <p class="has-text-grey is-size-7">Click any location node on the map to inspect stock and coordinates.</p>
        </div>
    </div>
</div>
```

---

## 6. Migration Execution Steps

1. **Database Schema Transformation**:
   - Legacy `storerooms.svg_content` values migrate to `inventory_rooms.svg_layout`.
   - Legacy `storerooms.raw_svg` is retained or archived in media storage if re-parsing is needed.
2. **Coordinate Synchronization**:
   - Ensure legacy location labels inside `<g id="locations">` are converted to 4-digit zero-padded XYZ string display codes (`StorageLocation.display_code`).
3. **Control Layer Integration**:
   - Implement `RoomSvgAdapter` in `app/inventory/control_layer/adapters/room_svg_adapter.py`.
4. **HTMX Visual Viewers**:
   - Build room spatial map templates supporting **Putaway Target Selection** (clicking an SVG shelf during putaway to auto-populate target coordinates) and **Audit Inspection**.
