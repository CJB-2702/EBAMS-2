---
type: "UX Guide"
title: "Search bars"
description: "Two distinct search patterns — the <search-dropdown> picker and a plain HTMX list filter — and which to use when."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Search bars

Two distinct search patterns live in this app, and they are **not interchangeable**:

1. **`<search-dropdown>`** — a form-associated custom element that pairs an input with an HTMX-loaded dropdown of `<li>` results. **Use this when the search produces a single picked value** that becomes a form field (e.g. picking a permission, a user, an asset). Full component guide: [../components/search_dropdown.md](../components/search_dropdown.md).
2. **Plain HTMX search input** — a vanilla `<input>` with `hx-get` that swaps a results region. **Use this when the search drives a list view** (e.g. filtering a table of assets, the *Available* column of a [dual listbox](../components/dual_listbox.md)).

For the full range of search-and-select/assignment patterns built on top of these two primitives (dual listbox, left-heavy assignment card pair, mini-card and wide-card combos, etc.), see [list_management_patterns.md](list_management_patterns.md).

---

## Decision table

| Situation | Pattern |
| :--- | :--- |
| Pick **one** related record to attach to a form field (FK, single tag, owner) | `<search-dropdown>` |
| Pick **one of many** for an inline edit (replace a row's owner without leaving the row) | `<search-dropdown>` |
| Filter a **list view** (assets table, events feed) | Plain HTMX input → `?format=htmx-search-results` |
| Filter the *Available* column of a **dual listbox** | Plain HTMX input scoped to that column ([dual_listbox.md](../components/dual_listbox.md)) |
| Type-ahead with **>8 options** for a `<select>` field | `<search-dropdown>` |
| Global "search the whole app" bar in the header | Plain HTMX input, results target a portal-level container |

---

## Plain HTMX search input — filtering a list

For list-filtering use cases, use a plain Bulma input plus `hx-get` to the canonical list URL with `format=htmx-search-results`.

```html
<div class="field">
  <p class="control has-icons-left">
    <input class="input is-family-monospace"
           type="search" name="q"
           hx-get="{% url 'asset_list' %}?format=htmx-search-results"
           hx-trigger="keyup changed delay:350ms, search"
           hx-target="#asset-list-container"
           hx-swap="innerHTML"
           hx-push-url="true"
           hx-indicator=".asset-list-skeleton"
           placeholder="search assets...">
    <span class="icon is-small is-left">
      <i class="fa-solid fa-magnifying-glass"></i>
    </span>
  </p>
</div>

<div id="asset-list-container">
  {% include "assets/_asset_list_rows.html" %}
</div>
```

### Rules

- **`type="search"`** so the browser provides a clear-X button and the `search` event fires on clear.
- **`hx-push-url="true"`** so the back button works after a search — keeps the F5 rule honest.
- **Same canonical URL** as the unfiltered list, with `?q=…&format=htmx-search-results`. Do not invent a `/search` route.
- **Debounce ~350 ms.** Less feels twitchy; more feels broken.
- **Indicator class** so the user sees the request is in flight; pair with a Bulma skeleton block.

---

## Common mistakes (across both patterns)

- **Using `<search-dropdown>` to filter a list.** It is a *picker*, not a *filter*.
- **Using a plain HTMX input as a picker** when you need a single value to submit with a form.
- **Two `format=` values in one URL.** The server should reject this (see [../format_contract.md](../format_contract.md)).
- **Server returns a fully-rendered page** to a search request. Search responses are fragments.
- **No `hx-push-url`** on a list filter — back button is broken, bookmarks don't work.

---

## Query-parameter contract (Tier 1 rule — see [../../UX_UI.md](../../UX_UI.md))

`hx-push-url` covers *writing* state to the URL as the user interacts. The other half — **reading**
that same state back out on a plain GET** — is just as required and easier to skip:

- Every filter field's current value comes from `request.GET`, not only from client-side state.
- Every "select an item to drive a detail panel" interaction (a master-detail pane, a clickable
  row/card that populates a side panel) accepts the selected id as a query parameter (e.g.
  `?line_id=<id>`) and renders already-selected on load — not only after a click.
- A link from another page that "deep-links" into a specific selection (e.g. a demand's edit page
  linking out to a PO's linkage tool with that demand's PO line pre-chosen) passes that selection as
  a query parameter the target page reads on load, rather than relying on the user to re-find and
  re-click it.

This is what makes such a page bookmarkable and reload-safe, and it is the direct fix for the
common legacy-app gap of a client-only JS selection with no URL sync — reloading such a page loses
the selection entirely.
