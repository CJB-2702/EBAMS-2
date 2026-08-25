---
type: Architecture Pattern
title: Destination Picker as Shared Utility — Pattern & Consumption Model
description: How any page can use the destination picker without reimplementing backend logic or understanding internal mechanics. Data-attribute-driven consumption for reduced backend duplication.
---

# Destination Picker as Shared Utility

## Goal

Enable **any page** in the inventory system to offer warehouse → room → location selection **without**:
1. Rewriting the warehouse/room/location queries.
2. Knowing the picker's internal architecture.
3. Coupling to the picker's template structure.
4. Violating the F5 rule.

## The pattern: "Smart context + dumb template"

### Backend (Smart, Reusable)

`DestinationPickerContext` owns all the logic:
- Warehouse queries, filtering by accessibility + active status.
- Room lookups, thumbnail SVG extraction.
- RoomLocation and StorageLocation assembly.
- Domain-aware stock annotation.
- State extraction from URL query params.

**A page never calls this logic twice; it's in one place.**

### Frontend (Dumb, Data-Attribute-Driven)

`_destination_picker.html` is a generic template that:
- Reads data attributes set by the backend context.
- Renders warehouse select, room grid, location table, SVG map.
- Contains only the markup; no custom page logic.
- Syncs user interactions back to data attributes + URL via simple JS.

**A page includes this template; it doesn't know how the state got there.**

---

## Consumption model

### Step 1: Backend builder call (one line per page)

```python
# app/inventory/presentation_layer/entrypoints/audits.py (or any page)
def audit_list(request):
    # ... other logic ...
    
    # Get destination picker state — one call, reusable builder
    picker_state = DestinationPickerContext.build_state(
        request,
        source_warehouse_id=user_warehouse_id,
        part_id=None  # optional
    )
    
    context = {"audit_list": audits, ...}
    context.update(picker_state)  # Injects all picker vars into template
    return render(request, "inventory/audits/index.html", context)
```

### Step 2: Template include (one line per page)

```django
<!-- app/inventory/templates/inventory/audits/index.html -->
{% extends "inventory/base.html" %}

{% block content %}
<div class="columns">
  <div class="column is-3">
    {% comment %} Reuse the picker — no page-specific markup {% endcomment %}
    {% include "inventory/movements/_destination_picker.html" with source_warehouse_id=source_warehouse_id %}
  </div>
  
  <div class="column is-9">
    {# Audit list or detail view #}
  </div>
</div>
{% endblock %}
```

### Step 3: Optional — read picker state from page JS

If the page needs to react to picker selections (e.g., filter an adjacent list):

```javascript
// Page JS reads data attributes without knowing picker internals
const picker = document.getElementById('destination-card');
const roomId = picker.dataset.roomId;
const locCode = picker.dataset.loc;
const slocId = picker.dataset.sloc;

// Trigger page-specific logic when location changes
document.addEventListener('pickerLocationSelected', (e) => {
  // The picker fires custom events when user selects
  filterAdjacentList(e.detail.sloc);
});
```

---

## Data-Attribute Contract

The `#destination-card` div is the "public API" — any page can read these attributes without reimplementing:

```html
<div id="destination-card"
     data-warehouse-id="{{ warehouse_id }}"      <!-- int | null —— currently selected warehouse -->
     data-room-id="{{ room_id }}"                <!-- int | null —— currently selected room -->
     data-loc="{{ loc }}"                        <!-- str —— RoomLocation display code (e.g. "0001-0001") -->
     data-sloc="{{ sloc }}"                      <!-- int | null —— StorageLocation pk -->
     data-source-warehouse="{{ source_warehouse_id }}"  <!-- int —— source (to detect cross-warehouse) -->
     data-part-id="{{ part_id }}">              <!-- int | null —— optional for stock display -->
</div>
```

**Rules for data attributes:**
- Always present, even if null/empty.
- Updated by the picker's internal JS on user interaction.
- Read by consuming pages to drive other UI sections.
- Synchronized to URL query params (F5-safe).

---

## Real-world example: Audit detail page

**Scenario:** An audit detail page shows a list of stock in a specific room. User has already selected a room in the audit start page. Now we want the room/location picker available as a sidebar so the user can jump to auditing a different location without losing their spot.

### Backend (movements.py pattern, reused)

```python
# app/inventory/presentation_layer/entrypoints/audits.py

def audit_detail(request, pk):
    audit = get_object_or_404(AuditSession.objects.select_related('room'), pk=pk)
    
    # Reuse: one context builder call
    picker_state = DestinationPickerContext.build_state(
        request,
        source_warehouse_id=audit.room.warehouse_id,
        part_id=None
    )
    
    context = {
        "audit": audit,
        "audit_lines": audit.audit_session_lines.select_related('part'),
        **picker_state,  # Unpacks {warehouses, rooms, selected_warehouse, ...}
    }
    return render(request, "inventory/audits/detail.html", context)
```

### Template (include pattern, reused)

```django
{% extends "inventory/base.html" %}

{% block content %}
<div class="columns">
  {# Left: destination picker (generic, reused, no page-specific logic) #}
  <div class="column is-3">
    <div class="sticky-sidebar">
      {% include "inventory/movements/_destination_picker.html" with source_warehouse_id=audit.room.warehouse_id %}
    </div>
  </div>
  
  {# Right: audit detail #}
  <div class="column is-9">
    <h2>Audit: {{ audit.room.room_name }}</h2>
    <table class="table">
      <thead>
        <tr><th>Part</th><th>Expected</th><th>Counted</th></tr>
      </thead>
      <tbody>
        {% for line in audit_lines %}
        <tr>
          <td>{{ line.part.part_number }}</td>
          <td>{{ line.expected_qty }}</td>
          <td><input type="number" name="counted_qty_{{ line.id }}"></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<script>
  {# Page-specific logic: when picker location changes, optionally sync to audit scope #}
  document.getElementById('destination-card').addEventListener('change', (e) => {
    const newRoomId = e.target.dataset.roomId;
    // Could navigate to a different audit in that room, or filter the table
    if (newRoomId && newRoomId != {{ audit.room.id }}) {
      alert(`Switch to auditing room ${newRoomId}?`);
    }
  });
</script>
{% endblock %}
```

### What the page author does **not** need to know:

- How warehouses are queried (filtered by domain/accessibility).
- How room SVGs are extracted and rendered.
- How location search works (client-side filtering? HTMX? custom logic?).
- Where the state is stored (URL params, data attrs, JS vars).
- How room selection syncs to the URL.

**All of that is in the context builder and the `_destination_picker.html` template.** The page author just plugs it in.

---

## Comparison: Before vs. After

### Before (current, before refactor)

**Putaway page:**
```python
def putaway_worklist(request):
    # Inline warehouse/room/location query logic (100 lines)
    warehouses = Warehouse.objects.filter(...)
    selected_warehouse = ...
    # ... room filtering ...
    # ... SVG rendering ...
    # ... location assembly ...
    return render(request, "putaway.html", {...})
```

**Movement portal:**
```python
def movement_portal(request):
    # Copy-pasted the same 100 lines from putaway
    warehouses = Warehouse.objects.filter(...)
    # ... identical logic ...
```

**Future audit page (if needed):**
```python
def audit_start(request):
    # Copy-pasted again (100 lines) ...
```

**Result:** 3 copies of the same logic, each potentially drifting (different domain filtering, different SVG rendering, etc.).

### After (with DestinationPickerContext)

**Putaway page:**
```python
def putaway_worklist(request):
    picker_state = DestinationPickerContext.build_state(request, source_warehouse_id=...)
    return render(request, "putaway.html", {"...": "...", **picker_state})
```

**Movement portal:**
```python
def movement_portal(request):
    picker_state = DestinationPickerContext.build_state(request, source_warehouse_id=...)
    return render(request, "create.html", {"...": "...", **picker_state})
```

**Audit start page:**
```python
def audit_start(request):
    picker_state = DestinationPickerContext.build_state(request, source_warehouse_id=...)
    return render(request, "audit_start.html", {"...": "...", **picker_state})
```

**Result:** Single source of truth. Any fix to warehouse filtering, SVG rendering, or accessibility rules applies everywhere.

---

## Future extension: Custom events

To make the picker even more useful for pages that need to react to user selections, the picker template could fire custom DOM events:

```javascript
// In _destination_picker.html, after location selection:
const event = new CustomEvent('destinationLocationSelected', {
  detail: {
    warehouseId: warehouseId,
    roomId: roomId,
    loc: locCode,
    sloc: slocId,
  }
});
document.getElementById('destination-card').dispatchEvent(event);
```

Consuming pages listen for it:

```javascript
document.getElementById('destination-card').addEventListener(
  'destinationLocationSelected',
  (e) => {
    // Filter adjacent list, highlight a row, etc.
    updateAdjacentUI(e.detail.slocId);
  }
);
```

---

## Design principles

1. **Control logic reuse > Template reuse.**
   - The expensive part (queries, filtering, domain checks) is in `DestinationPickerContext`.
   - Template duplication across a few pages is less critical than logic duplication.

2. **Data attributes as public API.**
   - Pages don't import or call picker JS; they read/listen to data attributes.
   - Decouples the picker's internal mechanics from consuming pages.

3. **F5 rule first.**
   - All state lives in URL params + data attributes, not hidden JS variables.
   - A bookmark or deep link works without HTMX or JS running first.

4. **Progressive enhancement.**
   - Without JS: form works (select tags, form submit, full page reload).
   - With JS: smooth client-side filtering, custom events, optional HTMX fragments.
   - Not a hard dependency.

---

## Maintenance and growth

### When adding a 4th page (issuance, transfer, etc.)

1. Call `DestinationPickerContext.build_state()` in the entrypoint.
2. `{% include %}` the template.
3. Done. No query logic to copy.

### When changing warehouse filtering logic

1. Edit `DestinationPickerContext.build_state()` once.
2. All 4+ pages using the picker get the change.
3. No PRs to find and update copies.

### When adding custom filtering (e.g., "only active warehouses in North region")

1. Add a parameter to `build_state()`: `region_code=None`.
2. If region_code is set, filter warehouses by it.
3. Consuming pages pass it or leave it empty.
4. Picker still doesn't change; state-building is just more selective.

---

## References

- [`UNIFIED_LOCATION_PICKER_DESIGN.md`](./UNIFIED_LOCATION_PICKER_DESIGN.md) — Design evaluation (why this pattern, not lazy-load).
- [`DESTINATION_PICKER_REFACTOR_SUMMARY.md`](./DESTINATION_PICKER_REFACTOR_SUMMARY.md) — Implementation details.
- [`app/inventory/control_layer/destination_picker.py`](./app/inventory/control_layer/destination_picker.py) — Backend context (the "smart" part).
- [`app/inventory/templates/inventory/movements/_destination_picker.html`](./app/inventory/templates/inventory/movements/_destination_picker.html) — Template (the "dumb" part).
