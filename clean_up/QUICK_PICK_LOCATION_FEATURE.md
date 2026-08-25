---
type: Feature Documentation
title: Quick Pick Location Bar — Progressive Search Dropdowns
description: Fast destination selection via chained search dropdowns with bidirectional sync to the destination card GUI.
---

# Quick Pick Location Bar — Progressive Search Dropdowns

## Overview

Added a "Quick Destination Picker" search bar at the top of the putaway page (`/inventory/putaway/`) that allows users to rapidly select a warehouse → room → storage location via progressive, interdependent search dropdowns.

**URL:** http://localhost:8000/inventory/putaway/

---

## UI Layout

Top card with 4 fields, enabled progressively left-to-right:

```
┌─────────────────────────────────────────────────────────┐
│ Quick Destination Picker                                │
├─────────────────────────────────────────────────────────┤
│ Warehouse   │ Room     │ Location          │ [Set]      │
│ [select ▼]  │[select ▼]│[search dropdown ▼]│ [btn]      │
└─────────────────────────────────────────────────────────┘
```

### Field behavior

| Field | Enabled by | Input type | Requirement |
| --- | --- | --- | --- |
| **Warehouse** | Always | Dropdown (`<select>`) | Optional |
| **Room** | Warehouse selected | Dropdown (`<select>`) | Optional |
| **Location** | Room selected | Search dropdown | **Required for submit** |
| **[Set] button** | Location selected | Button | N/A |

### Key design rule — one Location field, not three

Earlier revisions had separate Major (X) / Minor (Y) text inputs alongside
the Atomic (Z) search dropdown. That was **over-specified**: `storage_location_search`
(`app/inventory/presentation_layer/entrypoints/topography.py`) only ever
filtered on `warehouse_id`, `room_id`, and a free-text `q` against
`StorageLocation.display_code` — the major/minor values were included in the
request (`hx-include`) but silently ignored server-side. Meanwhile
`display_code` is already the full `"X-Y-Z"` string (`coordinate_adaptor.build_storage_location_display_code`),
so typing any fragment of major, minor, or atomic into one search box already
narrows the results. The dedicated Major/Minor inputs added a field a user
had to fill in without it doing anything. Resolution: collapsed to a single
`qp-location` search-dropdown that searches the full display code, matching
how the destination card's own Location Directory filter already works.

---

## How it works

### 1. Warehouse selection

User selects a warehouse from the dropdown:
- ✅ Enables the Room dropdown.
- ✅ Clears Room, Location.
- ✅ Updates URL: `?warehouse_id=1`
- ✅ Updates destination card → shows rooms for this warehouse.

### 2. Room selection

User selects a room from the dropdown:
- ✅ Enables the Location search dropdown.
- ✅ Clears Location.
- ✅ Updates URL: `?warehouse_id=1&room_id=5`
- ✅ Updates destination card → shows location table for this room.

### 3. Location selection

User searches and selects a location (matches any fragment of the full
`X-Y-Z` display code — major, minor, or atomic):
- ✅ Filters by the selected warehouse + room.
- ✅ Enables the [Set] button when selected.
- ✅ Updates URL: `?warehouse_id=1&room_id=5&sloc=42`

### 4. Submit (Set button)

User clicks [Set]:
- ✅ Applies the selected location to the destination card.
- ✅ Highlights the location row in the destination card table.
- ✅ Updates the "Destination" field at bottom.
- ✅ Same effect as clicking "Select" in the destination card table.

---

## Bidirectional sync

The quick pick bar and destination card stay in sync in both directions,
live where possible — not only after a full reload.

### Quick pick → Destination card

Every quick-pick selection (warehouse, room, location) navigates
(`window.location = url`), so the server re-renders the destination card
from the same query params. This is a full reload rather than a partial
patch, which is fine under the F5 rule but means each step is a page turn.

### Destination card → Quick pick

The destination card changes via two paths that do **not** navigate, so a
plain `DOMContentLoaded` sync (page-load only) missed them. Both are now
wired to resync the bar immediately, no reload required:

1. **Warehouse select in the card** — swaps `#destination-card` via HTMX
   (`hx-trigger="change"`). `putaway.html` listens for
   `htmx:afterSwap` on `#destination-card` and calls
   `syncDestinationCardToQuickPick()` after every swap.
2. **Location click in the card's table** — `pickerSelectLocation()` in
   `_destination_picker.html` updates `data-loc`/`data-sloc` in place (no
   swap, no reload) and now dispatches a `destination-card:selection-changed`
   custom event (bubbles to `document`), which `putaway.html` listens for
   and resyncs from.
3. **Room select / deselect in the card** still navigates the whole page,
   so the existing `DOMContentLoaded` listener covers it.

`syncDestinationCardToQuickPick()` reads `#destination-card`'s
`data-warehouse-id` / `data-room-id` / `data-sloc` attributes and mirrors
them onto `#qp-warehouse` / `#qp-room` / `#qp-location`, enabling/disabling
downstream fields to match.

---

## API endpoints used

| Field | Endpoint | Query params | Returns |
| --- | --- | --- | --- |
| Warehouse | (hardcoded `<select>`, from context) | N/A | N/A |
| Room | (hardcoded `<select>`, from context) | N/A | N/A |
| Location | `GET /inventory/storage-locations/search/` | `warehouse_id`, `room_id`, `q` | `<li data-value="{id}">...` |

The Location field uses the `<search-dropdown>` web component protocol: returns only `<li>` elements, no wrapper. `q` matches against `StorageLocation.display_code`, the full `"X-Y-Z"` code, so it covers major/minor/atomic in one box.

---

## Implementation details

### Files changed

| File | Change |
| --- | --- |
| `app/inventory/templates/inventory/movements/putaway.html` | Added quick pick card with progressive dropdowns + JS logic. |

### JavaScript functions in putaway.html

- `quickPickSelectWarehouse(id)` — Clear dependent fields, filter/enable room picker.
- `quickPickSelectRoom(roomId)` — Clear/enable the Location field.
- `quickPickSelectLocation(dropdown)` — Lookup location and trigger submit.
- `quickPickSubmit()` — Navigate to the selected location.
- `fetchLocationAndUpdate(slocId)` — Fetch location details from the DOM or server.
- `resetQuickPick()` — Clear all fields and disable.
- `resetQuickPickFromRoom()` — Clear the Location field after a room change.
- `syncDestinationCardToQuickPick()` — Mirror the destination card's current selection onto the bar.

Wired to fire on: `DOMContentLoaded` (initial load), `htmx:afterSwap` targeting
`#destination-card` (warehouse select in the card), and the
`destination-card:selection-changed` custom event dispatched by
`pickerSelectLocation()` in `_destination_picker.html` (location click in the
card's table) — see [Bidirectional sync](#bidirectional-sync) above.

---

## Testing

### Manual test flow

1. **Load putaway page** → http://localhost:8000/inventory/putaway/
2. **Select warehouse** from dropdown → Room field enables, destination card shows room grid.
3. **Search and select room** → Location field enables, destination card shows location table.
4. **Search and select a location** (matches any fragment of the `X-Y-Z` code) → [Set] button enables.
5. **Click [Set]** → Page reloads with location selected, destination card highlights the row.
6. **Refresh page (F5)** → Quick pick fields populate from URL params, destination card loads with selection.
7. **Select a warehouse in the destination card itself** → card swaps via HTMX; quick pick bar updates live, no reload.
8. **Click a location row in the destination card table** → quick pick bar updates live (Location field populates), no reload.

### Edge cases

- **Clear warehouse** → All fields reset.
- **Change warehouse** → Room, Location clear; destination card resets.
- **Change room** → Location clears; destination card updates to new room.

---

## Future enhancements

1. **Custom events:** Fire a `quickPickLocationSelected` event so other pages/widgets can react to a Set.
2. **Keyboard shortcuts:** Tab through fields, Enter to submit.
3. **Accessibility:** ARIA labels, keyboard navigation.

---

## Related documentation

- [`DESTINATION_PICKER_AS_UTILITY.md`](./DESTINATION_PICKER_AS_UTILITY.md) — Design pattern: how the quick pick integrates with the reusable destination picker context.
- [`_destination_picker.html`](./app/inventory/templates/inventory/movements/_destination_picker.html) — GUI-based location picker (room grid, location table, SVG).
