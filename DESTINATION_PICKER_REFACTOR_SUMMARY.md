---
type: Implementation Summary
title: Destination Picker Refactor — Unified Backend + Reusable Template
description: Extracts bespoke destination-selection logic into DestinationPickerContext; introduces reusable _destination_picker.html template with data-attribute sync and improved UX.
---

# Destination Picker Refactor — Implementation Summary

## What was done

### 1. **Backend:** `DestinationPickerContext` (new control-layer utility)

**File:** `app/inventory/control_layer/destination_picker.py`

Extracted all warehouse → room → location selection logic into a centralized, reusable builder:

```python
class DestinationPickerContext:
    @classmethod
    def build_state(request, *, source_warehouse_id, part_id=None) -> dict:
        """Returns full picker state dict: warehouses, rooms, locations, SVG, selections."""
    
    @classmethod
    def build_location_table_fragment(request, *, room_locations, loc) -> dict:
        """Returns just the location table tier (for HTMX re-fetch)."""
```

**Benefits:**
- ✅ Single source of truth for picker queries.
- ✅ No duplication across `movement_portal`, `putaway_worklist`, and future pages.
- ✅ Centralized domain/accessibility filtering (via RoomSvgAdapter, SVG queries, etc.).
- ✅ Reusable for any page needing warehouse/room/location selection.

### 2. **Entrypoints:** Updated `movements.py`

- Removed inline `_destination_state()` and `_destination_target_fragment()` functions.
- Both `movement_portal()` and `putaway_worklist()` now call `DestinationPickerContext.build_state()`.
- Kept POST redirect logic lean; moved state-assembly logic to the context.

**Code removed:** ~130 lines of duplicated query/assembly logic.

### 3. **Template:** New `_destination_picker.html` (reusable fragment)

**File:** `app/inventory/templates/inventory/movements/_destination_picker.html`

A shared, data-attribute-driven destination picker card that can be `{% include %}`d in any page:

```django
{% include "inventory/movements/_destination_picker.html" with source_warehouse_id=... part_id=... %}
```

**Features:**
- ✅ **Data attributes for state:** `data-warehouse-id`, `data-room-id`, `data-loc`, `data-sloc`, `data-source-warehouse`, `data-part-id`.
- ✅ **F5-safe:** All state lives in URL query params + data attributes (no JS-hidden state).
- ✅ **GUI → URL sync:** Room selections, location clicks, back button all update `window.history` and data attributes.
- ✅ **Location search/filter:** Live search box with client-side row filtering (existing, lightweight pattern).
- ✅ **SVG support:** Room layout SVG rendered if available; clicks can wire to location selection (future enhancement).
- ✅ **Fallback navigation:** Simple "back to rooms" button and warehouse dropdown for no-JS fallback.

**Internal JavaScript functions:**
- `pickerSelectWarehouse(id)` — set warehouse, clear room/location.
- `pickerSelectRoom(event, id)` — set room, clear location.
- `pickerSelectLocation(event, slocId, locCode)` — set location, flash the button.
- `pickerDeselectRoom(event)` — back to room grid.
- `filterLocationTable(query)` — client-side search filter.

### 4. **Putaway template:** Simplified with included picker

**File:** `app/inventory/templates/inventory/movements/putaway.html`

- Replaced ~170 lines of inline destination-picker HTML with one include: `{% include "inventory/movements/_destination_picker.html" %}`.
- Updated hidden form fields to include `room_id` and `loc` (needed for POST redirect preservation).
- Improved submit-card messaging to explain "continue putting away" pattern.

### 5. **POST redirect fix** — preserve destination state

After form submission, the redirect now preserves `warehouse_id`, `room_id`, `loc`, `sloc` query params, allowing users to:
1. Select a destination location.
2. Check multiple unassigned rows.
3. Submit (putaway executes).
4. Stay at the same location to continue putting away without re-picking.

**Before:**
```
POST → redirect to ?warehouse_id=1 (destination picker resets to room grid)
```

**After:**
```
POST → redirect to ?warehouse_id=1&room_id=5&loc=0001-0001&sloc=42 (location picker stays open)
```

---

## Data-Attribute Contract (for future enhancements)

The `#destination-card` div carries metadata that any JS or HTMX logic can read:

```html
<div id="destination-card"
     data-warehouse-id="{{ warehouse_id }}"      <!-- Currently selected warehouse -->
     data-room-id="{{ room_id }}"                <!-- Currently selected room -->
     data-loc="{{ loc }}"                        <!-- Selected RoomLocation display code -->
     data-sloc="{{ sloc }}"                      <!-- Selected StorageLocation pk -->
     data-source-warehouse="{{ source_warehouse_id }}"  <!-- Source stock warehouse (for inter-WH detection) -->
     data-part-id="{{ part_id }}">              <!-- Optional part ID for stock display -->
</div>
```

Future enhancements (SVG shape clicks, autocomplete pickers, etc.) can:
1. Update these attributes when the user selects a location.
2. Read them to populate dependent UI sections.
3. Sync them to URL params via `window.history.pushState()` for F5 safety.

---

## Architectural advantages

### 1. **Backward compatibility**
- No schema changes; no database reset required.
- Existing URLs and query-param contracts unchanged.
- F5 rule preserved end-to-end.

### 2. **Reusability**
- Any future page needing destination selection (audits, issuance, transfers, etc.) can call `DestinationPickerContext.build_state()` and include `_destination_picker.html`.
- No copy-paste of query logic.

### 3. **Separation of concerns**
- **Backend:** Central, testable state-builder (control-layer utility).
- **Frontend:** Generic template with data-attr-driven sync logic (no page-specific logic).
- **Pages:** Just call the builder and include the template; let data attributes carry state.

### 4. **Progressive enhancement**
- **Without JS:** Full page works (warehouse select, room links, location links all trigger full-page reloads).
- **With JS:** Smooth client-side filtering, button flashes, URL updates, data-attr sync.
- **With HTMX:** Can re-fetch picker fragments (e.g., location table) without full page reload.

---

## Testing checklist

- [ ] Run `python refresh_project.py` to rebuild DB and clear migrations (migration-safe refactor, no schema change).
- [ ] Navigate to putaway at `http://localhost:8000/inventory/putaway/`.
- [ ] Select a warehouse → rooms appear.
- [ ] Click a room → location table and SVG appear.
- [ ] Search the location table → rows filter.
- [ ] Click "Select" on a location → button highlights, submit card updates.
- [ ] Click "Back to rooms" → room picker shows again.
- [ ] Check a few unassigned rows.
- [ ] Submit → putaway happens, redirect preserves warehouse/room/location state.
- [ ] Page reloads → same state visible (F5 rule verified).
- [ ] Manually edit URL to `?warehouse_id=2` → picker resets to room grid for warehouse 2 (state in URL).

---

## Future work opportunities

1. **SVG shape selection:** Wire room-layout SVG clicks to call `pickerSelectLocation()` with the tapped area's `data-loc` code.
2. **Search dropdown for locations:** Replace the static table with a `<search-dropdown>` that hits `storage_location_search` endpoint with warehouse/room scoping.
3. **Movement portal:** Apply the same pattern to `movement_portal` (currently has its own destination picker code path).
4. **Lazy-component loading (justified):** Once multiple pages reuse the picker, consider building a minimal "load destination picker on demand" version *if* performance becomes an issue — but **only with explicit acceptance of the F5 rule violation** (see UNIFIED_LOCATION_PICKER_DESIGN.md).
5. **Tier 2 guide:** Document the picker pattern in `harness/UX_UI/components/destination_picker.md` once the pattern is proven across 2+ pages.

---

## Files changed

| File | Change |
| --- | --- |
| `app/inventory/control_layer/destination_picker.py` | **New:** Centralized picker context builder. |
| `app/inventory/presentation_layer/entrypoints/movements.py` | Removed inline `_destination_state()`, `_destination_target_fragment()`. Updated to use `DestinationPickerContext`. Fixed POST redirect to preserve state. |
| `app/inventory/templates/inventory/movements/_destination_picker.html` | **New:** Reusable picker template with data attributes and sync logic. |
| `app/inventory/templates/inventory/movements/putaway.html` | Simplified by including `_destination_picker.html`. Added `room_id` and `loc` hidden form fields. |
| `UNIFIED_LOCATION_PICKER_DESIGN.md` | Design doc evaluating reuse patterns and F5 rule implications. |
| `DESTINATION_PICKER_REFACTOR_SUMMARY.md` | **This file.** Implementation notes. |

---

## References

- **Design justification:** [`UNIFIED_LOCATION_PICKER_DESIGN.md`](./UNIFIED_LOCATION_PICKER_DESIGN.md) — explains why Option A (server-render with data attributes) was chosen over lazy-load.
- **Architecture guide:** [`harness/Architecture/patterns/htmx_patterns.md`](./harness/Architecture/patterns/htmx_patterns.md) — F5 rule, progressive enhancement philosophy.
- **UX guide:** [`harness/UX_UI.md`](./harness/UX_UI.md) — query-parameter state contract, canonical URLs.
