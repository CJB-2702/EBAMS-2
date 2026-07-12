---
type: "UX Example"
title: "Left Heavy Assignment Card Pair"
description: "A pattern for assigning items from a large pool (left card, 2/3 width) to a target entity (right card, 1/3 width) using local session states before form submission."
tags: [ux-ui, ux-example, examples]
context_tier: 3
---

# Left Heavy Assignment Card Pair

A pattern for assigning items from a large pool (left card, 2/3 width) to a target entity (right card, 1/3 width) using local session states before form submission. 

## Key Characteristics
1. **App-Like Geometry**: Fixed height (`height: 580px; display: flex; flex-direction: column; overflow: hidden`) on both cards so headers, filter bars, and footers remain fixed while lists scroll vertically.
2. **Sticky Table Headers**: Column titles (`thead th`) use `position: sticky` and solid backgrounds to remain visible when table rows scroll underneath.
3. **Zero-Gap Footer**: The "Select All" button aligns to the left wall (via `pl-0`) to preserve clean alignment with the card's vertical border.
4. **Header Select All Checkbox**: The header column features a checkbox that selects/deselects all visible and enabled items, functioning in sync with the footer's toggle button.

---

## HTML Structure

```html
<div class="columns is-variable is-4" id="assignment-row">

  <!-- LEFT Card (2/3) — Available Pool -->
  <div class="column is-8">
    <div class="pc" style="display:flex;flex-direction:column;height:580px;overflow:hidden">
      
      <!-- Card Header -->
      <div class="pc-header">
        <div class="pc-header-title">
          <span class="icon"><span class="material-icons" aria-hidden="true">list</span></span>
          Available Items
        </div>
        <span class="is-size-7 has-text-grey"><span id="avail-count">0</span> shown</span>
      </div>

      <!-- Filter + Search Bar -->
      <div class="px-3 py-2" style="border-bottom:1px solid var(--bulma-border-weak);background:var(--bulma-scheme-main-bis)">
        <div class="is-flex is-align-items-center" style="gap:0.5rem;flex-wrap:wrap">
          <!-- Text search -->
          <div class="control has-icons-left" style="flex:1;min-width:140px">
            <input type="search" id="search-items" class="input is-small" placeholder="Search..." autocomplete="off">
            <span class="icon is-small is-left"><span class="material-icons" aria-hidden="true" style="font-size:0.9rem">search</span></span>
          </div>
          <!-- Filter dropdown -->
          <div class="select is-small">
            <select id="filter-category">
              <option value="">All Categories</option>
              <!-- Options -->
            </select>
          </div>
        </div>
      </div>

      <!-- Scrollable Table Container -->
      <div id="avail-scroll" style="flex:1;overflow-y:auto;min-height:0">
        <table id="avail-table" class="table is-fullwidth is-hoverable" style="margin:0">
          <thead>
            <tr>
              <!-- Header select-all checkbox -->
              <th style="width:2.5rem"><input type="checkbox" id="avail-header-check" aria-label="Select all visible"></th>
              <th>Name</th>
              <th>Category</th>
              <th style="width:2.5rem"></th>
            </tr>
          </thead>
          <tbody id="avail-body">
            <tr class="avail-row" data-id="1">
              <td><input type="checkbox" class="avail-check"></td>
              <td>Example Item</td>
              <td>Example Category</td>
              <td><a href="#" class="has-text-grey"><span class="icon"><span class="material-icons">open_in_new</span></span></a></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Card Footer -->
      <footer class="card-footer custom-card-footer">
        <!-- Zero-gap container on left (pl-0) -->
        <div class="card-footer-secondaries pl-0 pr-3">
          <button type="button" id="btn-select-all" class="button is-small is-light">Select All</button>
        </div>
        <button type="button" id="btn-assign" class="button is-link card-footer-primary">
          <span class="icon"><span class="material-icons" aria-hidden="true">arrow_forward</span></span>
          <span>Assign Selected</span>
        </button>
      </footer>
    </div>
  </div>

  <!-- RIGHT Card (1/3) — Assigned Items -->
  <div class="column">
    <div class="pc" style="display:flex;flex-direction:column;height:580px;overflow:hidden">
      
      <!-- Card Header -->
      <div class="pc-header">
        <div class="pc-header-title">
          <span class="icon"><span class="material-icons" aria-hidden="true">check_circle</span></span>
          Applied / Assigned
        </div>
        <span class="is-size-7 has-text-grey"><span id="assigned-count">0</span> applied</span>
      </div>

      <!-- Scrollable List Container -->
      <div style="flex:1;overflow-y:auto;min-height:0">
        <table class="table is-fullwidth is-hoverable" style="margin:0">
          <tbody id="assigned-body">
            <!-- Dynamically populated or empty row -->
          </tbody>
        </table>
      </div>

      <!-- Card Footer -->
      <footer class="card-footer" style="padding:0">
        <button type="button" id="btn-remove" class="button is-danger is-light card-footer-primary" style="flex:1;border-radius:0">
          <span class="icon"><span class="material-icons" aria-hidden="true">remove_circle_outline</span></span>
          <span>Remove Selected</span>
        </button>
      </footer>
    </div>
  </div>

</div>
```

---

## Required CSS

Include the following structural rules in the template's `<style>` block:

```css
/* Scroll container must be relative for absolute sticky positioning context */
#avail-scroll {
  position: relative;
}

/* Sticky column headers with solid theme-aware backgrounds */
#avail-table thead th {
  position: sticky;
  top: 0;
  background-color: var(--bulma-table-background-color, var(--bulma-scheme-main));
  z-index: 10;
  box-shadow: inset 0 -2px 0 var(--bulma-border);
}
```

---

## JavaScript Interaction Pattern

Implement the following behavior to keep the header checkbox and the footer toggle button synchronized with visible/enabled options:

```javascript
(function () {
  'use strict';

  const availBody   = document.getElementById('avail-body');
  const headerCheck  = document.getElementById('avail-header-check');
  const btnSelectAll = document.getElementById('btn-select-all');

  // Sync header check and footer button label
  function updateHeaderCheckState() {
    if (!headerCheck) return;
    const visibleChecks = Array.from(availBody.querySelectorAll('.avail-row:not([hidden]) .avail-check:not(:disabled)'));
    
    if (visibleChecks.length === 0) {
      headerCheck.checked = false;
      headerCheck.indeterminate = false;
      if (btnSelectAll) btnSelectAll.textContent = 'Select All';
      return;
    }
    
    const checkedCount = visibleChecks.filter(cb => cb.checked).length;
    headerCheck.checked = checkedCount === visibleChecks.length;
    headerCheck.indeterminate = checkedCount > 0 && checkedCount < visibleChecks.length;

    if (btnSelectAll) {
      btnSelectAll.textContent = (checkedCount === visibleChecks.length) ? 'Deselect All' : 'Select All';
    }
  }

  // Header checkbox interaction
  if (headerCheck) {
    headerCheck.addEventListener('change', function () {
      const checked = this.checked;
      availBody.querySelectorAll('.avail-row:not([hidden]) .avail-check:not(:disabled)').forEach(cb => {
        cb.checked = checked;
      });
      if (btnSelectAll) {
        btnSelectAll.textContent = checked ? 'Deselect All' : 'Select All';
      }
    });
  }

  // Footer Button Toggle interaction
  if (btnSelectAll) {
    btnSelectAll.addEventListener('click', () => {
      const visibleChecks = Array.from(availBody.querySelectorAll('.avail-row:not([hidden]) .avail-check:not(:disabled)'));
      const allChecked = visibleChecks.length > 0 && visibleChecks.every(cb => cb.checked);
      visibleChecks.forEach(cb => { cb.checked = !allChecked; });
      updateHeaderCheckState();
    });
  }

  // Row checkbox state change propagation
  availBody.addEventListener('change', e => {
    if (e.target.classList.contains('avail-check')) {
      updateHeaderCheckState();
    }
  });

  // Call updateHeaderCheckState() at the end of filter changes (e.g. applyAllFilters)
})();
```
