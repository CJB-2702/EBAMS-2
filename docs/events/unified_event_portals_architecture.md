# Unified Event Portals & Dynamic Event Card Architecture

This document serves as the comprehensive architectural reference for the unified event management engine, sub-application event portals, dynamic domain detail card fragments, visual design contracts, personnel rosters, and interactive UI controls in **EBAMS-2**.

---

## 1. Executive Summary & Core Objectives

The **Unified Event Engine** standardizes event tracking across all organizational sub-applications—Maintenance, Dispatching, Inventory, Procurement, Asset Management, and Administration. 

### Key Deliverables:
- **Centralized Event Architecture**: Relocated `AssetEvent` to `app/events/models/asset_event.py` as the single source of truth for event-to-asset relationships.
- **Dynamic Detail Card Engine**: Standardized `build_activity_card()` in `app/events/presentation_layer/tools/generic_cards.py` to automatically resolve domain-specific MTI proxy models and inject dynamic detail fragment templates (`card.detail_template`).
- **Domain HSL Color-Coded Headers**: Visual differentiation across all 7 event domain types with 0px radius chamfered containers.
- **Rich Personnel & Supply Chain Traceability**: Integrated full personnel lists (crew rosters, operators, requesters, buyers, vendors, safety inspectors) directly into expanded card layouts.
- **Global & Local Comment Collapse Controls**: Integrated one-click comment collapsing across individual card headers and a top-level page toggle.
- **Multi-Density Event Portals**: Delivered composite event feeds (`/events/`) and sub-application event portals supporting `format=large`, `format=medium`, and `format=condensed`.

---

## 2. Architecture & Data Model

### 2.1 Relocation & Integration of `AssetEvent`
`AssetEvent` links domain assets to events with explicit role tracking. 

```
                                  ┌───────────────────────────┐
                                  │        Event (Base)       │
                                  └─────────────▲─────────────┘
                                                │
          ┌──────────────────┬──────────────────┼──────────────────┬──────────────────┐
          │                  │                  │                  │                  │
┌─────────┴─────────┐ ┌──────┴──────────┐ ┌─────┴───────────┐ ┌────┴─────────────┐ ┌──┴───────────────┐
│ MaintenanceDetail │ │DispatchingDetail│ │ InventoryDetail │ │ AssetMgmtDetail │ │ AdminDetail     │
└───────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
          │                  │                  │                  │                  │
          └──────────────────┴──────────────────┼──────────────────┴──────────────────┘
                                                │
                                      ┌─────────┴─────────┐
                                      │    AssetEvent     │
                                      │ (role, asset, ev) │
                                      └─────────▲─────────┘
                                                │
                                      ┌─────────┴─────────┐
                                      │       Asset       │
                                      └───────────────────┘
```

- **Location**: `app/events/models/asset_event.py`
- **Backward Compatibility**: `app/assets/models/core/asset_event.py` re-exports `AssetEvent` to avoid breaking legacy imports.
- **Fields**:
  - `asset`: ForeignKey → `Asset` (CASCADE)
  - `event`: ForeignKey → `Event` (CASCADE)
  - `role`: CharField (e.g. `subject`, `dispatched_unit`, `consumed_by`, `target_asset`)

---

## 3. Dynamic Detail Card Fragment Engine

### 3.1 Adapter Resolution (`generic_cards.py`)
`build_activity_card(thread, user)` resolves the event's domain detail model, attaches asset links, computes header color schemes, and sets the template fragment path:

| Event Type (`event_type`) | Proxy Detail Model | Template Fragment Path |
| :--- | :--- | :--- |
| `maintenance` | `MaintenanceDetail` | `events/fragments/details/maintenance_card.html` |
| `dispatching` | `DispatchingDetail` | `events/fragments/details/dispatching_card.html` |
| `reservation` | `DispatchingDetail` | `events/fragments/details/reservation_card.html` |
| `inventory` | `InventoryDetail` | `events/fragments/details/inventory_card.html` |
| `procurement` | `InventoryDetail` / `Event` | `events/fragments/details/procurement_card.html` |
| `asset_management` | `AssetManagementDetail` | `events/fragments/details/asset_management_card.html` |
| `administration` | `AdministrationDetail` | `events/fragments/details/administration_card.html` |
| Generic / System | `Event` | `events/fragments/details/generic_card.html` |

### 3.2 Dynamic Template Inclusion
The expanded card shell (`app/events/templates/events/fragments/event_card.html`) dynamically includes the domain fragment:
```django
{% if card.detail_template %}
  {% include card.detail_template with card=card %}
{% endif %}
```

---

## 4. Visual Design Contract & Domain Color Schemes

Every event card features sharp corners (`border-radius: 0px !important`), depth layering (`depth-1` for outer card, `depth-2` for inner containers), and custom HSL color-coded headers.

### Domain Color Palette Matrix:

| Event Domain | Header Background | Header Border | Title Text | Badge Style | Icon |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Maintenance** | `#fffbeb` (Amber) | `#f59e0b` | `#92400e` | `#fef3c7` / `#92400e` | `build` |
| **Dispatching** | `#eef2ff` (Indigo) | `#6366f1` | `#3730a3` | `#e0e7ff` / `#3730a3` | `local_shipping` |
| **Reservation** | `#f3e8ff` (Purple) | `#a855f7` | `#6b21a8` | `#f3e8ff` / `#6b21a8` | `bookmark` |
| **Inventory** | `#ecfdf5` (Emerald)| `#10b981` | `#047857` | `#d1fae5` / `#047857` | `inventory_2` |
| **Procurement** | `#f0fdf4` (Teal) | `#14b8a6` | `#0f766e` | `#ccfbf1` / `#0f766e` | `shopping_cart` |
| **Asset Mgmt** | `#f1f5f9` (Slate) | `#64748b` | `#334155` | `#e2e8f0` / `#334155` | `precision_manufacturing` |
| **Administration**| `#fff1f2` (Rose) | `#f43f5e` | `#be123c` | `#ffe4e6` / `#be123c` | `admin_panel_settings` |
| **Generic / System**|`#f8fafc` (Neutral)| `#94a3b8` | `#475569` | `#f1f5f9` / `#475569` | `event` |

---

## 5. Rich Personnel & Supply Chain Traceability

To eliminate ambiguity during operational reviews, expanded detail views expose full personnel lists and supply chain originators:

- **Maintenance**: Lead Technician, Assistant Technicians, Inspector, Sign-off Supervisor.
- **Dispatching & Reservations**: Assigned Driver/Operator, Dispatch Coordinator, Reserved For, Passenger/Crew Roster.
- **Procurement**: Purchasing Agent, Approved By, Buyer Contact, and linked Part Demand Requesters.
- **Inventory**: Issuing Storekeeper, Recipient, Storage Bin/Location.
- **Asset Management**: Current Custodian, Transferring Officer, Security Auditor.
- **Administration**: Target User, Acting Administrator, Granted Roles / Scope.

---

## 6. Interactive UI Capabilities

### 6.1 Collapse / Expand Comments Infrastructure
- **Card-Level Toggle**: The comment card header in `comments_card.html` is interactive (`cursor: pointer`). Clicking toggles `.comments-card-body` visibility while preserving comment filter button interactions (`stopPropagation()`).
- **Global Toggle**: `#global-comments-toggle` in `ev_list_large.html` allows users to collapse or expand all comment threads on the page in a single click.
- **Base Script**: `window.__toggleCommentsSection()` and `window.__toggleAllComments()` are defined globally in `app/events/templates/events/ev_base.html`.

### 6.2 Density Switching (`format=`)
- `format=large`: Expanded cards with full metadata, detail fragments, direct file attachments, and activity threads.
- `format=medium`: Summary rows with left domain color accents, tags, and truncations.
- `format=condensed`: Flat, high-density tabular event list.

---

## 7. Sub-Application Event Portals & Dev Workflows

### 7.1 Registered Portal Routes
- **Composite Event Hub**: `/events/`
- **Maintenance Events**: `/maintenance/events-portal`
- **Dispatching Events**: `/dispatching/events`
- **Inventory & Parts Events**: `/parts/events/`
- **Asset Management Events**: `/assets/events/`
- **Administration Events**: `/administration/events/`

### 7.2 Developer Workflows & Seeding
- **Seed Command**: `python manage.py seed_events_dev` populates sample events across all 7 domain types with proxy detail records.
- **Full Refresh Command**: `python refresh_project.py` wipes database/cache/uploads, regenerates migrations, applies schema, loads fixtures, and seeds dev data.

---

## 8. Origin Entity Navigation & Single Event Page Integration

### 8.1 Origin Entity Link Resolution (`generic_cards.py`)
`get_event_origin_link(thread, detail, asset_links)` evaluates the event's domain detail record and `AssetEvent` associations to construct a target navigation dictionary `{url, label, icon}`:
- **Maintenance Events**: Resolves link to `Maintenance Action` detail page (`reverse('maintenance_detail', kwargs={'pk': event.pk})`).
- **Dispatching Events**: Resolves link to `Dispatch` detail page (`reverse('dispatching_dispatch_detail', kwargs={'pk': event.pk})`).
- **Reservation Events**: Resolves link to `Reservation` detail page (`reverse('dispatching_reservation_detail', kwargs={'pk': event.pk})`).
- **Asset Linkage**: Resolves link to `Asset` detail page (`reverse('asset_detail', kwargs={'asset_id': asset.pk})`).
- **Personnel Linkage**: Resolves link to target `User` profile page (`reverse('user_detail', kwargs={'user_id': user.pk})`).
- **Universal Availability**: `origin_link` is exposed on `card.origin_link` and rendered across:
  1. Expanded event cards (`format=large` feed).
  2. Summary rows (`format=medium` feed).
  3. Single event detail pages (`/events/<hash>/`).

### 8.2 Unified Individual Event View & Attachment Galleries (`ev_detail.html`)
The single event view entrypoint `event_detail()` in `app/events/presentation_layer/entrypoints/events.py` resolves event context via `build_activity_card(event, request.user)` and renders `ev_detail.html`. `ev_detail.html` embeds the canonical `events/fragments/event_card.html` template shell and includes two dedicated file gallery cards below the composite card:
1. **Event File Attachments Gallery**: Standardized `<file-browser>` (`files_card.html`) and `<image-carousel>` (`gallery_card.html`) for standalone direct event attachments (`card.direct_attachments`).
2. **Comment Attachments Gallery**: Standardized `<file-browser>` (`files_card.html`) and `<image-carousel>` (`gallery_card.html`) aggregating all comment attachments across the event (`card.comment_attachments`).

The single event page inherits:
- Domain HSL visual styling and icon header.
- Dynamic domain detail sub-card fragment.
- Interactive comment thread & attachment uploader.
### 8.3 Zero-JS HTML Popover API Associated Assets Modal
Every composite event card (`event_card.html`) includes an **Assets** button in the header bar that pops up an interactive modal listing all primary and role-linked assets:
- **Zero-JS Architecture**: Uses native browser **HTML Popover API** (`popover` attribute and `popovertarget` / `popovertargetaction="hide"`) and **Invoker Commands** (`commandfor` and `command="show-modal"` / `command="close"`).
- **Data Rendering**: Lists `card.detail.asset` (Primary Asset), `card.asset_links` (Role-linked assets), and `card.detail.requested_assets` (Free-text requirement notes).
- **Light Dismiss**: Native backdrop overlay dismisses automatically when clicking outside or clicking the close button (`X`).

### 8.4 Multi-Filter URL Parameter Integration (`event_index`)
The event feed index (`/events/`) supports five URL filter parameters:
- `q`: Title search string (`?q=inspection`)
- `domain` / `domain_id`: Filter by domain ID (`?domain=1`)
- `asset` / `asset_id`: Filter by linked Asset ID across `AssetEvent` associations and `MaintenanceDetail.asset_id` (`?asset=8`)
- `status`: Filter by event status (`?status=complete`)
- `event_type`: Filter by event type (`?event_type=maintenance`)

**State Preservation**:
Active filters are sanitized into `base_query` and appended across density switches (`condensed`, `medium`, `large`) and HTMX request headers (`hx-get="{% url 'event_index' %}"`).

---

## 9. Technical Debt & Reversal Considerations

> [!NOTE]
> **Heuristic Origin Link Resolution vs. Future Generic Relation**
> 
> Currently, `get_event_origin_link()` resolves origin URLs by probing domain proxy attributes (`detail.asset`, `detail.requested_for`, `asset_links`).
> 
> **Reversal Path**:
> - If base `Event` is later upgraded with a formal Django `GenericForeignKey` (`origin_content_type` + `origin_object_id`), `get_event_origin_link()` can be simplified to call `event.origin_object.get_absolute_url()` without changing any template code.
> - If single event views (`ev_detail.html`) require custom non-card page layouts in future releases, `ev_detail.html` can be easily unbundled from `event_card.html` without affecting the composite feed engine.

