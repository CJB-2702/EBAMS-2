# Pagination and shared partials

Pagination is a single Bulma pattern reused across every list view in the application. There is no per-app pagination component — the same markup, same query parameters, same partial.

---

## Query contract

| Parameter | Default | Notes |
| :--- | :--- | :--- |
| `page` | `1` | 1-indexed. |
| `count` | view-defined (e.g. 25) | Per-page count; views may cap this. |

Pagination parameters coexist with `format=` and `q=`. Combining `page` with `format=htmx-search-results` returns one fragment page of results; combining `page` with a density `format` (`condensed` / `medium` / `large`) returns one page of the full HTML view.

---

## Canonical markup

```html
<nav class="pagination is-centered" role="navigation" aria-label="pagination">
  <a href="?page={{ prev }}" class="pagination-previous">Previous</a>
  <a href="?page={{ next }}" class="pagination-next">Next page</a>
  <ul class="pagination-list">
    <li><a href="?page=1" class="pagination-link" aria-label="Goto page 1">1</a></li>
    <li><span class="pagination-ellipsis">&hellip;</span></li>
    <li>
      <a class="pagination-link is-current"
         aria-label="Page {{ current }}"
         aria-current="page">{{ current }}</a>
    </li>
    <li><span class="pagination-ellipsis">&hellip;</span></li>
    <li><a href="?page={{ total }}" class="pagination-link" aria-label="Goto page {{ total }}">{{ total }}</a></li>
  </ul>
</nav>
```

---

## Sticky table header (optional)

For wide tables, wrap the `<table>` in `.table-container` and apply a `position: sticky; top: 0;` rule to `<thead>`. Keep this opt-in per view — sticky headers cost a stacking context and can clash with portal dropdowns.

---

## Long lists must paginate

A view that returns more than `count` rows but does not implement pagination is a bug. Pages without an upper bound on row count violate the project's performance baseline (NFR-PERF) and should be flagged in review.
