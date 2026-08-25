/* Bulk row selection + floating action bar.
 *
 * Used by the demand list and the active-inventory list, whose results regions
 * are htmx-swapped on every filter change. Everything here is delegated off
 * `document`, so a swapped-in table is live immediately with no re-binding —
 * an `htmx:afterSwap` hook would have to know every target id, and would miss
 * the one someone adds next.
 *
 * Markup contract (see harness/UX_UI/search/left_heavy_assignment_card_pair.md
 * for the header-checkbox/footer-toggle convention this mirrors):
 *
 *   <div data-bulk-scope="demands" data-bulk-field="demand_ids">
 *     <input type="checkbox" data-bulk-all>          header select-all
 *     <input type="checkbox" data-bulk-check value="42">   one per row
 *     <div data-bulk-bar hidden>
 *       <span data-bulk-count>0</span>
 *       <form data-bulk-form> ... </form>            ids injected on submit
 *     </div>
 *   </div>
 *
 * Selection is deliberately NOT persisted across a filter change: the rows the
 * user can no longer see are rows they can no longer verify, and silently
 * carrying them into a bulk write is how people queue things they never meant
 * to.
 */
(function () {
  'use strict';

  function scopeOf(el) {
    return el ? el.closest('[data-bulk-scope]') : null;
  }

  function checksIn(scope) {
    return Array.from(scope.querySelectorAll('[data-bulk-check]'));
  }

  function checkedIn(scope) {
    return checksIn(scope).filter(function (cb) { return cb.checked; });
  }

  function refresh(scope) {
    if (!scope) return;
    var all = checksIn(scope);
    var checked = checkedIn(scope);

    var header = scope.querySelector('[data-bulk-all]');
    if (header) {
      header.checked = all.length > 0 && checked.length === all.length;
      header.indeterminate = checked.length > 0 && checked.length < all.length;
    }

    var bar = scope.querySelector('[data-bulk-bar]');
    if (bar) bar.hidden = checked.length === 0;

    scope.querySelectorAll('[data-bulk-count]').forEach(function (node) {
      node.textContent = String(checked.length);
    });

    // Row highlight, so a long table still shows what is selected once the
    // checkbox column has scrolled out of view horizontally.
    all.forEach(function (cb) {
      var row = cb.closest('tr');
      if (row) row.classList.toggle('is-bulk-selected', cb.checked);
    });
  }

  document.addEventListener('change', function (e) {
    var t = e.target;
    if (!t) return;

    if (t.matches('[data-bulk-all]')) {
      var scope = scopeOf(t);
      if (!scope) return;
      checksIn(scope).forEach(function (cb) { cb.checked = t.checked; });
      refresh(scope);
      return;
    }
    if (t.matches('[data-bulk-check]')) {
      refresh(scopeOf(t));
    }
  });

  document.addEventListener('click', function (e) {
    var clear = e.target.closest ? e.target.closest('[data-bulk-clear]') : null;
    if (!clear) return;
    var scope = scopeOf(clear);
    if (!scope) return;
    e.preventDefault();
    checksIn(scope).forEach(function (cb) { cb.checked = false; });
    refresh(scope);
  });

  // Inject the checked ids as hidden fields at submit time rather than keeping
  // a shadow list in sync — the checkboxes are the single source of truth.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.matches || !form.matches('[data-bulk-form]')) return;

    var scope = scopeOf(form);
    if (!scope) return;

    var field = scope.getAttribute('data-bulk-field') || 'ids';
    form.querySelectorAll('input[data-bulk-injected]').forEach(function (n) {
      n.remove();
    });

    var checked = checkedIn(scope);
    if (checked.length === 0) {
      e.preventDefault();
      return;
    }
    checked.forEach(function (cb) {
      var hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = field;
      hidden.value = cb.value;
      hidden.setAttribute('data-bulk-injected', '');
      form.appendChild(hidden);
    });
  });

  // Fresh table swapped in: recompute from whatever came back (normally an
  // empty selection, since the new rows arrive unchecked).
  document.addEventListener('htmx:afterSwap', function () {
    document.querySelectorAll('[data-bulk-scope]').forEach(refresh);
  });

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-bulk-scope]').forEach(refresh);
  });
})();
