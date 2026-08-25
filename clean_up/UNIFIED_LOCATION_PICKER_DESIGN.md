---
type: Design Evaluation
title: Unified Location Picker Widget — Approach & Justification
description: Cost/benefit analysis of a shared destination-picker backend utility with front-end sync via HTMX + data attributes, and whether lazy-loading breaks the F5 rule.
context_tier: 1
---

# Unified Location Picker Widget — Design Evaluation

## Problem statement

Today, every page needing to let a user pick a putaway destination (Warehouse → Room → RoomLocation → StorageLocation) rebuilds the same backend query logic inline:
- `_destination_state()` in `movements.py` assembles warehouse list, filters rooms by warehouse, renders SVG thumbnails, etc.
- Movement portal and putaway both consume this.
- Future pages (audits, issuance, etc.) may need the same picker but will copy-paste the logic again.

**Desired outcome:** One reusable backend builder that returns structured destination state (warehouses, selected room, SVG, locations, metadata), and a front-end component that consumes it via data attributes so pages don't need to know its internals.

---

## Current architecture (bespoke)

### movements.py — single page, bespoke picker

```python
def _destination_state(request, *, source_warehouse_id, part_id=None) -> dict:
    # Queries warehouses, filters by accessibility, assembles rooms,
    # renders SVG, builds location table, handles selection state.
    # Returns: {warehouses, selected_warehouse, rooms, room_locations, map_svg, ...}
```

**Consumers:**
- `movement_portal()` — single-stock move, destination is *optional* (inter-warehouse goes to Intake Room)
- `putaway_worklist()` — batch putaway, destination is *required* (must have a StorageLocation)

Both inline-template the same HTML structure (`destination-card`); both handle the same query-param state machine.

### Result

- **Code smell:** ~100 lines of overlapping query/state logic across two functions + one template fragment `_destination_target.html`.
- **Single-page fallback:** full page render works without JS; SVG map and search filter are enhancements.
- **F5 safe:** all state (warehouse, room, location selection) lives in URL query params. Reload reproduces the exact state.

---

## Proposed architecture (unified, with design questions)

### Option A: Server-side builder only (no lazy load)

**Backend:** A reusable class/function pair.

```python
# app/inventory/control_layer/destination_picker.py
class DestinationPickerContext:
    @classmethod
    def build_state(cls, request, *, source_warehouse_id, part_id=None, **kwargs) -> dict:
        """Assembles full destination picker state from query params.
        
        Returns: {
            warehouses: [...],
            selected_warehouse: Warehouse | None,
            rooms: [...],
            selected_room: Room | None,
            room_locations: [...],
            storage_locations: [...],
            map_svg: str | None,
            selected_storage_location: StorageLocation | None,
            ...
        }
        """
        # Centralized query logic; movements.py calls this once.
```

**Front-end:** Pages include the picker HTML into their initial render, populated with data attributes.

```html
<!-- Any page needing destination picker includes this: -->
<div 
    id="destination-picker"
    data-source-warehouse="{{ source_warehouse_id }}"
    data-part-id="{{ part_id }}"
    data-selected-room-id="{{ selected_room.pk }}"
    data-selected-location-id="{{ selected_location.pk }}">
  
  <!-- Warehouse dropdown, room grid, location table, SVG map -->
  <!-- All state lives in data-* attrs and URL params, not JS vars -->
</div>
```

**Advantages:**
- ✅ Single source of control logic reuse.
- ✅ F5 safe — full page render includes initialized picker state.
- ✅ State lives in URL + data attributes, not hidden JS.
- ✅ HTMX fragments can re-query and update the picker without reloading the page.
- ✅ No lazy-load violation.

**Disadvantages:**
- ⚠️ Builder function returns a large dict; not all pages need all fields.
- ⚠️ Picker HTML is still bespoke per page (can be templated, but not a true "drop-in component").

### Option B: Lazy-load picker via HTMX (breaks F5 rule)

**Backend:** A dedicated "fetch destination picker fragment" endpoint.

```python
def get_destination_picker_fragment(request):
    """Returns only the picker HTML, scoped by query params."""
    warehouse_id = request.GET.get("warehouse_id")
    room_id = request.GET.get("room_id")
    loc = request.GET.get("loc")
    sloc = request.GET.get("sloc")
    
    state = DestinationPickerContext.build_state(request, ...)
    return render(request, "_destination_picker.html", state)
```

**Front-end:** Initial page render has an empty anchor; HTMX populates it on load.

```html
<div id="destination-picker" 
     hx-get="{% url 'destination_picker_fragment' %}"
     hx-trigger="load"
     hx-include="[name=warehouse_id], [name=room_id], [name=loc]">
  <!-- Empty; filled by HTMX on page load -->
</div>
```

**Advantages:**
- ✅ True "drop-in widget" — one endpoint, any page just includes the `<div>`.
- ✅ Reduces duplicate template code across pages.
- ✅ Centralized endpoint means query logic is 100% unified.

**Disadvantages:**
- ❌ **Violates F5 rule.** Initial page render lacks picker content; reload fires HTMX trigger again, adding ~500ms latency to every page load. A user bookmarking the page loses the picker until HTMX runs.
- ❌ Picker state not in URL; if JS breaks, no fallback to plain form submission.
- ❌ Two network round-trips on page load (page, then picker fragment) instead of one.
- ❌ Harder to debug/inspect in DevTools (state lives in HTMX's hx-include, not visible in initial HTML).

---

## Decision: Recommend Option A with template composition

**Rationale:**

1. **F5 rule is load-bearing.** It's not aesthetic; it's foundational to the project's debugging, testability, and accessibility story. Breaking it for code reuse is a bad trade.

2. **Control logic reuse > template reuse.** The expensive part is warehouse/room/location queries, SVG rendering, domain filtering. That's what `DestinationPickerContext` centralizes. Template composition is secondary.

3. **State lives in URLs and data attributes.** When a user bookmarks a putaway session with a room and location selected, the URL preserves it. No lazy-load ambiguity.

4. **HTMX enhancements are still possible.** Pages can still use HTMX to re-fetch the picker fragment (with `format=htmx-destination-picker`) when the user changes filters, without breaking the initial render.

### Implementation sketch for Option A

#### 1. Backend: Centralized picker context

```python
# app/inventory/control_layer/destination_picker.py

class DestinationPickerContext:
    @classmethod
    def build_state(cls, request, *, source_warehouse_id, part_id=None):
        """Single source of truth for destination-picker state assembly."""
        # Existing _destination_state() logic, extracted here.
        # Reused by movement_portal, putaway_worklist, and any future page.
        ...
    
    @classmethod
    def build_target_fragment(cls, request, *, room_locations, loc):
        """Single source for location table + atomic-coord picker."""
        # Existing _destination_target_fragment() logic.
        ...
```

#### 2. Front-end: Picker card with data attributes

```html
<!-- Shared across all pages needing destination pick: -->
<div id="destination-picker" 
     data-warehouse-id="{{ warehouse_id }}"
     data-room-id="{{ room_id }}"
     data-loc="{{ loc }}"
     data-sloc="{{ selected_storage_location.pk }}"
     data-source-warehouse="{{ source_warehouse_id }}"
     data-part-id="{{ part_id }}">
  
  {# Warehouse select, room grid, location table, SVG map #}
  {# All driven by data-* attrs and URL params #}
  
  {# HTMX enhancements: #}
  <input 
      hx-get="{% url 'destination_picker_locations' %}"
      hx-target="#destination-locations-table"
      hx-include="#destination-picker"
      hx-trigger="change"
      ...>
</div>
```

#### 3. Pages consume the builder

```python
# movements.py
def putaway_worklist(request):
    ...
    destination = DestinationPickerContext.build_state(
        request, source_warehouse_id=selected_warehouse.pk
    )
    context = { ... }
    context.update(destination)
    return render(request, "inventory/movements/putaway.html", context)
```

#### 4. Template stays minimal

```django
{% include "inventory/_destination_picker_card.html" %}
```

The included snippet is shared; it reads `warehouse_id`, `room_id`, `loc`, `sloc`, etc. from context, no page-specific logic needed.

---

## Cost/benefit summary

| Aspect | Option A | Option B |
| --- | --- | --- |
| **F5 rule** | ✅ Preserved | ❌ Broken |
| **Code reuse** | ✅ Control logic centralized | ✅✅ Control + template both centralized |
| **State visibility** | ✅ URL + data attrs | ❌ Implicit in HTMX triggers |
| **Page load latency** | ✅ One round-trip | ❌ Two round-trips |
| **Fallback without JS** | ✅ Full form works | ❌ No picker, form incomplete |
| **Complexity** | ✅ Moderate | ⚠️ Higher (HTMX state management) |
| **Future extensibility** | ✅ Easy to add more pickers | ⚠️ Scaling concerns with multiple async loads |

---

## Exceptions and caveats

### When lazy-load *might* be justified

Lazy-load via HTMX could be acceptable **if and only if:**

1. **The component is purely decorative.** The page functions without it (e.g., a real-time notification bell, a sidebar widget). The putaway picker is *required* for the form to submit, so it doesn't qualify.

2. **The user never bookmarks intermediate states.** If picking a destination is ephemeral (one-off action, no session retention), lazy-load is less risky. Putaway sessions *are* bookmarked (warehouse + room + location selection is state the user may return to).

3. **Fallback to full page reload is acceptable.** If JS fails, the page still works (just slower). Putaway without the picker is *broken* — there's no form field to submit a location.

The putaway picker fails all three tests, so lazy-load is ruled out.

### Phased approach

1. **Phase 1 (now):** Extract `DestinationPickerContext`, use Option A. Build putaway first.
2. **Phase 2 (next page needing picker):** Reuse the builder; add to movement_portal if needed.
3. **Phase 3 (if template duplication becomes painful):** Extract a shared `_destination_picker_card.html` fragment.
4. **Phase 4+ (far future, only if justified):** If 5+ pages consume the picker and performance is a problem, revisit lazy-load with explicit downside acceptance.

---

## Recommended next steps

1. **Build `DestinationPickerContext`** (control layer reuse).
2. **Update `putaway_worklist()` and `movement_portal()`** to call it.
3. **Keep template inline for now** (duplicated across pages, but minimal).
4. **Mark picker `<div>` with data attributes** for future HTMX/JS enhancements.
5. **Defer template extraction** until a third page needs the picker (no premature abstraction).
6. **Document the approach** in a Tier 2 guide once the pattern is proven.

---

## Appendix: Data attribute contract for future enhancements

When GUI interactions (SVG clicks, table row selections) update the picker state, they should:

1. **Update the data attributes** (`data-room-id`, `data-loc`, `data-sloc`).
2. **Update the URL query params** (via `window.history.pushState` or HTMX's `hx-push-url`).
3. **Trigger HTMX re-fetch** (if needed) to update dependent fragments (e.g., location table).

Example: User clicks an SVG shape representing room location "0001-0001":

```javascript
// Set data attrs
document.getElementById('destination-picker').dataset.loc = '0001-0001';
document.getElementById('destination-picker').dataset.roomId = roomId;

// Push URL
const url = new URL(window.location);
url.searchParams.set('room_id', roomId);
url.searchParams.set('loc', '0001-0001');
window.history.pushState({}, '', url);

// Trigger HTMX re-fetch of location table
htmx.ajax('GET', '{% url "destination_picker_locations" %}?...',
  {target: '#destination-locations-table', swap: 'innerHTML'});
```

This keeps state synchronized across all three layers (data attrs, URL, DOM), making the page F5-safe and inspectable.
