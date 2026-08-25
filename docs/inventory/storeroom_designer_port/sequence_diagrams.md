---
okf_version: "0.1"
type: "Technical Decision"
title: "Storeroom Designer — Port Sequence Diagrams"
description: "Mermaid sequence diagrams for the ported warehouse CRUD and layout-builder flows, including the two stock-protection rejections."
tags: [inventory, topography, port, sequence-diagram]
created: 2026-08-24
created_by: Christian Bissett
updated: 2026-08-24
updated_by: Christian Bissett
---

# Storeroom Designer — Port Sequence Diagrams

Actors are the real collaborators, not abstractions: the entrypoint is
`app/inventory/presentation_layer/entrypoints/topography.py`, the context is
`TopographyContext`, and every guard named here is a real class in
`app/inventory/control_layer/guards/`.

## 1. Create a warehouse

The one thing worth noticing: the Intake Room is not a second step the operator
can forget. `WarehouseFactory` creates both rows inside one transaction, so a
`Warehouse` without an Intake Room is not a state the control layer can produce
(FD-14).

```mermaid
sequenceDiagram
    actor Op as Operator
    participant EP as topography.warehouse_create
    participant Perm as inventory_access
    participant Ad as WarehouseFormAdaptor
    participant Ctx as TopographyContext
    participant F as WarehouseFactory
    participant V as WarehouseValidator
    participant DB as Database

    Op->>EP: POST name, code, division, domains
    EP->>Perm: require_manage_topography()
    Perm-->>EP: ok
    EP->>Ad: from_post(request.POST)
    Ad-->>EP: {name, code, division_id, address, domain_ids}
    EP->>Ctx: create_warehouse(...)
    Ctx->>F: create(...)
    F->>V: check_code_unique(code)
    alt code already taken
        V-->>F: raise InventoryValidationError
        F-->>EP: propagate
        EP-->>Op: 200, form re-rendered with the operator's own values
    else code free
        V-->>F: ok
        F->>DB: BEGIN
        F->>DB: INSERT Warehouse
        F->>DB: INSERT Room (Intake, protected)
        F->>DB: COMMIT
        F-->>Ctx: warehouse
        Ctx-->>EP: TopographyContext(warehouse_id)
        EP-->>Op: 302 to warehouse detail
    end
```

## 2. Retire a warehouse — the soft delete

The legacy `storeroom_delete` route called `db.session.delete()` and took the
storeroom's whole location/bin tree with it. Nothing in this port does that.

```mermaid
sequenceDiagram
    actor Op as Operator
    participant EP as topography.warehouse_edit
    participant Ctx as TopographyContext
    participant M as TopographyManager
    participant DB as Database

    Op->>EP: POST action=retire
    EP->>Ctx: deactivate_warehouse(actor)
    Ctx->>M: deactivate_warehouse(warehouse)
    M->>DB: UPDATE is_active = False
    Note over DB: Row, rooms, locations, and stock<br/>history all survive untouched.
    M-->>EP: warehouse
    EP-->>Op: 302 to index — hidden from the default filter

    Op->>EP: GET ?show=inactive, then POST action=reactivate
    EP->>Ctx: reactivate_warehouse(actor)
    Ctx->>M: reactivate_warehouse(warehouse)
    M->>DB: UPDATE is_active = True
    EP-->>Op: 302 to detail
```

## 3. Upload a room layout — the happy path

Reconciliation never writes. It reports three buckets, and only the operator's
explicit "create selected" turns unmatched shapes into rows.

```mermaid
sequenceDiagram
    actor Op as Operator
    participant EP as topography.room_layout
    participant Ctx as TopographyContext
    participant Svg as RoomSvgAdapter
    participant Pol as LayoutReconciliationPolicy
    participant Rec as SvgReconciliationStruct
    participant Gal as GalleryManager
    participant Sess as request.session

    Op->>EP: POST action=upload, svg_file
    EP->>Ctx: upload_room_layout(room_id, file, actor)
    Ctx->>Svg: check_upload_size(bytes)
    Ctx->>Svg: sanitize(raw)
    Note over Svg: strips script / foreignObject / on* handlers /<br/>external hrefs, and the Inkscape `svg:` prefix
    Svg-->>Ctx: sanitized markup
    Ctx->>Svg: extract_shape_codes(group="locations")
    Svg-->>Ctx: ["0001-0001", "0002-0002"]
    Ctx->>Rec: build(shape_codes, existing_codes)
    Rec-->>Ctx: matched / unmatched_shapes / orphaned
    Ctx->>Pol: check_room_orphans(room, orphaned)
    Pol-->>Ctx: ok — no orphan holds stock
    Ctx->>Gal: add_image(sanitized file)
    Note over Gal: archived as a new version;<br/>the previous layout stays in photo_gallery
    Gal-->>Ctx: attachment set as current_layout
    Ctx-->>EP: reconciliation
    EP->>Sess: store reconciliation draft
    EP-->>Op: 302 back to the builder, reconciliation card visible

    Op->>EP: POST action=create_selected, unmatched_code[]
    EP->>Ctx: bulk_add_room_locations(coordinates)
    Ctx-->>EP: created rows
    EP->>Sess: pop draft
    EP-->>Op: 302, "Created N location(s)."
```

## 4. Upload a layout that would orphan stock — **rejected**

This is the rule the port adds. The check runs **before** `_archive_layout`, so a
rejected upload leaves `current_layout` pointing at the layout that was already
there. There is no half-applied state to clean up.

```mermaid
sequenceDiagram
    actor Op as Operator
    participant EP as topography.room_layout
    participant Ctx as TopographyContext
    participant Svg as RoomSvgAdapter
    participant Rec as SvgReconciliationStruct
    participant Pol as LayoutReconciliationPolicy
    participant DB as Database
    participant Gal as GalleryManager

    Op->>EP: POST action=upload, new SVG missing shape "0001-0001"
    EP->>Ctx: upload_room_layout(...)
    Ctx->>Svg: sanitize + extract_shape_codes
    Svg-->>Ctx: ["0002-0002"]
    Ctx->>Rec: build(...)
    Rec-->>Ctx: orphaned = ("0001-0001",)
    Ctx->>Pol: check_room_orphans(room, orphaned)
    Pol->>DB: RoomLocation WHERE display_code IN orphaned<br/>AND storage_locations__stock IS NOT NULL
    DB-->>Pol: ["0001-0001"]
    Pol-->>Ctx: raise InventoryValidationError
    Note over Gal: never reached — nothing archived,<br/>current_layout unchanged
    Ctx-->>EP: propagate
    EP->>Op: 302 back with the error toast:<br/>"Upload rejected: the new layout has no shape for<br/>1 location(s) that still holds stock (0001-0001)."
```

## 5. Retire a bin — allowed vs refused

The legacy `LocationContext.remove_bin` had no inventory check whatsoever; only
the location-level delete did. This port checks at both tiers, so retiring the
parent is not a way around the child rule.

```mermaid
sequenceDiagram
    actor Op as Operator
    participant EP as topography.room_location_layout
    participant Ctx as TopographyContext
    participant M as TopographyManager
    participant Pol as StorageLocationPolicy
    participant DB as Database

    Op->>EP: POST action=retire_bin, storage_location_id
    EP->>Ctx: deactivate_storage_location(bin, actor)
    Ctx->>M: deactivate_storage_location(bin)
    M->>Pol: check_deactivate(bin)
    Pol->>DB: COUNT ActiveInventory WHERE storage_location = bin
    alt count > 0
        DB-->>Pol: 3
        Pol-->>M: raise InventoryValidationError
        M-->>EP: propagate
        EP-->>Op: 302 with "'0002-0002-0007' still holds 3 stock rows<br/>and cannot be retired. Move or issue the stock first."
    else count == 0
        DB-->>Pol: 0
        Pol-->>M: ok
        M->>DB: UPDATE is_active = False
        M-->>EP: bin
        EP-->>Op: 302, "Bin retired."
    end
```

Note the interaction with `StockLedgerManager.withdraw`: it **deletes** a balance
row the moment it reaches zero, so "a row exists" and "stock lives here" are the
same statement. A bin becomes retirable the instant its last unit is issued or
moved — no stale zero-quantity rows block it forever.

## 6. Drill down through the three tiers (read path, unchanged by this port)

Included for orientation — this is the legacy build page's "location viewer →
bin viewer" flow as it exists in EBAMS-2, where each tier is its own canonical
URL with a `format=` fragment rather than one page holding both viewers.

```mermaid
sequenceDiagram
    actor Op as Operator
    participant RD as GET /inventory/room/{id}/
    participant Svg as RoomSvgAdapter
    participant RLD as GET /inventory/room-location/{id}/
    participant Stock as ActiveInventory

    Op->>RD: open the room
    RD->>Svg: render_interactive_svg(layout, shape_targets)
    Svg-->>RD: SVG with hx-get on each matched shape
    RD-->>Op: map + empty drawer

    Op->>RD: click shape "0005-0002"
    Note right of Op: hx-get ...?format=htmx-location-drawer&loc=0005-0002
    RD-->>Op: drawer fragment
    alt location has its own Z layout
        Op->>RLD: follow to the Z-picker
        RLD->>Svg: render_interactive_svg(bin layout)
        RLD-->>Op: bin map
        Op->>RLD: click bin "0001"
        RLD->>Stock: rows for that storage location
        Stock-->>RLD: balances
        RLD-->>Op: stock drawer
    else exactly one bin and no Z layout
        Note over RD: the "skip tier 3" case —<br/>the drawer shows stock directly
        RD->>Stock: rows for the single storage location
        Stock-->>RD: balances
        RD-->>Op: stock in the tier-2 drawer
    end
```
