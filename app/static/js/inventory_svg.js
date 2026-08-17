/**
 * Phase 3 / Phase 6 — SVG Spatial Engine Node Selection, Glowing & Location Directory Filtering.
 * Automatically handles SVG shape clicks and URL parameter (`loc`), applying the glowing `is-selected`
 * state, filtering the Location Directory table to items under the selected map area, and managing
 * the Deselect button.
 */
(function() {
  let activeLoc = null;

  function filterLocationDirectoryTable() {
    const searchInput = document.getElementById('loc-search-input');
    const textQuery = searchInput ? searchInput.value.toLowerCase().trim() : '';

    const rows = document.querySelectorAll('.loc-table-row');
    let visibleCount = 0;

    rows.forEach(function(row) {
      const rowLoc = (row.getAttribute('data-loc') || '').trim();
      const searchData = (row.getAttribute('data-search') || '').toLowerCase();

      const matchesLoc = !activeLoc || rowLoc === activeLoc;
      const matchesText = !textQuery || searchData.includes(textQuery);

      if (matchesLoc && matchesText) {
        row.style.display = '';
        visibleCount++;
      } else {
        row.style.display = 'none';
      }
    });

    const noMatchRow = document.getElementById('loc-table-no-match');
    if (noMatchRow) {
      noMatchRow.style.display = (visibleCount === 0) ? '' : 'none';
    }

    updateDeselectButtonUI();
  }

  function updateDeselectButtonUI() {
    const deselectBtn = document.getElementById('deselect-area-btn');
    const deselectLabel = document.getElementById('deselect-area-label');

    if (deselectBtn) {
      if (activeLoc) {
        deselectBtn.style.display = 'inline-flex';
        if (deselectLabel) {
          deselectLabel.textContent = 'Deselect map area (' + activeLoc + ')';
        }
      } else {
        deselectBtn.style.display = 'none';
      }
    }
  }

  function selectMapArea(locCode, options) {
    options = options || {};
    activeLoc = locCode ? locCode.trim() : null;

    // Highlight matching SVG shapes
    const allNodes = document.querySelectorAll('.spatial-node');
    allNodes.forEach(function(node) {
      node.classList.remove('is-selected');
    });

    if (activeLoc) {
      const locClean = activeLoc;
      const locIdFormat = 'loc_' + locClean.replace(/-/g, '_');

      allNodes.forEach(function(node) {
        const label = node.getAttribute('inkscape:label') || '';
        const id = node.getAttribute('id') || '';
        const dataLoc = node.getAttribute('data-loc-code') || '';
        const hxGet = node.getAttribute('hx-get') || '';

        const isMatch = label === locClean ||
                        id === locClean ||
                        id === locIdFormat ||
                        dataLoc === locClean ||
                        hxGet.includes('loc=' + encodeURIComponent(locClean)) ||
                        hxGet.includes('loc=' + locClean);

        if (isMatch) {
          node.classList.add('is-selected');
        }
      });
    }

    // Filter location directory table
    filterLocationDirectoryTable();

    // Update URL parameter without reload if supported
    if (!options.skipHistory && window.history && window.history.replaceState) {
      const url = new URL(window.location.href);
      if (activeLoc) {
        url.searchParams.set('loc', activeLoc);
      } else {
        url.searchParams.delete('loc');
      }
      window.history.replaceState({}, '', url.toString());
    }
  }

  function clearLocSelection(e) {
    if (e && e.preventDefault) e.preventDefault();
    selectMapArea(null);
  }

  function initFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const locParam = urlParams.get('loc');
    selectMapArea(locParam, { skipHistory: true });
  }

  document.addEventListener('DOMContentLoaded', initFromUrl);
  document.addEventListener('htmx:afterSwap', initFromUrl);

  document.addEventListener('click', function(e) {
    const spatialNode = e.target.closest('.spatial-node');
    if (spatialNode) {
      const hxGet = spatialNode.getAttribute('hx-get') || '';
      // If node has an active HTMX drawer fetch (e.g. topography room drawer), let HTMX handle it
      if (hxGet && hxGet.includes('format=htmx-')) {
        return;
      }

      const locCode = spatialNode.getAttribute('data-loc-code') ||
                      spatialNode.getAttribute('inkscape:label') ||
                      spatialNode.getAttribute('id') || '';

      if (locCode) {
        e.preventDefault();
        e.stopPropagation();
        // Toggle selection if already selected, otherwise set selection
        const newLoc = (activeLoc === locCode) ? null : locCode;
        selectMapArea(newLoc);
      }
    }
  });

  window.selectMapArea = selectMapArea;
  window.clearLocSelection = clearLocSelection;
  window.filterLocationTable = function(query) {
    filterLocationDirectoryTable();
  };
})();
