# Search bars

Two distinct search patterns live in this app, and they are **not interchangeable**:

1. **`<search-dropdown>`** — a form-associated custom element that pairs an input with an HTMX-loaded dropdown of `<li>` results. **Use this when the search produces a single picked value** that becomes a form field (e.g. picking a permission, a user, an asset).
2. **Plain HTMX search input** — a vanilla `<input>` with `hx-get` that swaps a results region. **Use this when the search drives a list view** (e.g. filtering a table of assets, the *Available* column of a [dual listbox](dual_listbox.md)).

For verbatim markup and the full `<search-dropdown>` web component source see [Examples/search_dropdown_component.md](Examples/search_dropdown_component.md).

---

## Decision table

| Situation | Pattern |
| :--- | :--- |
| Pick **one** related record to attach to a form field (FK, single tag, owner) | `<search-dropdown>` |
| Pick **one of many** for an inline edit (replace a row's owner without leaving the row) | `<search-dropdown>` |
| Filter a **list view** (assets table, events feed) | Plain HTMX input → `?format=htmx-search-results` |
| Filter the *Available* column of a **dual listbox** | Plain HTMX input scoped to that column ([dual_listbox.md](dual_listbox.md)) |
| Type-ahead with **>8 options** for a `<select>` field | `<search-dropdown>` |
| Global "search the whole app" bar in the header | Plain HTMX input, results target a portal-level container |

---

## 1. `<search-dropdown>` — picking a single value

A reusable, **form-associated** custom element that pairs an input with a dropdown of `<li>` results. Backed by an open shadow root; results are projected into a default `<slot>`. Source: `app/static/web_components/search_dropdown.js`.

### Why a custom element

- **Form participation** via `ElementInternals.setFormValue()` — the picked value submits with the surrounding `<form>` exactly like a native input.
- **HTMX attribute pass-through** — `hx-get`, `hx-target`, `hx-trigger`, etc. on the host element are forwarded to the internal `<input>`.
- **Shadow-DOM-correct `hx-target`** — defaults to `global #<host-id>` so swaps hit the host element in the document, not a stale node inside the shadow tree.
- **No JS bindings on consumer pages** — register the script once, drop the tag, done.

### Server contract — what the endpoint must return

- **URL:** the canonical collection URL for the resource (e.g. `…/permissions`, `…/users`).
- **Query:** `format=htmx-search-results`, `q=<typed text>`, plus any scope params (`group_id=…`, `org_id=…`).
- **Response body:** **only `<li>` elements** — no surrounding `<ul>`, `<div>`, or template wrapper. The component swaps `innerHTML` into its slot.
- **Each `<li>`** that should be selectable has a `data-value="<id>"`. Disabled / informational rows omit `data-value` (or set `aria-disabled="true"` / class `is-disabled`).
- **Pagination:** include a sentinel `<li>` (e.g. *"Showing 25 of 412 — refine your search…"*) when the result is truncated.

### Rules

- **Do not nest** a `<search-dropdown>` inside another `<search-dropdown>`.
- **One per form field.** Two related records → two separate elements with distinct `name=` attributes.
- **Do not** reach into the shadow DOM from page CSS. Style hooks: `::slotted(li)`, `::slotted(li.is-disabled)`, `::slotted(li.is-family-monospace)`. New variants are added to the component, not to a stylesheet.
- **Always set `name=`** on the host element if the picked value should submit with the form.
- **The `q` parameter is fixed.** Internal input is `name="q"` — endpoint must read `q`, not `query` or `term`.
- **Keep the `<li>` markup flat.** Nested interactive children steal click events from the component's selection handler.

### Common pitfalls

- **Empty results show no feedback.** Always render a "No matches" `<li class="is-disabled">`.
- **`hx-target` set to a stale element.** Don't override unless you know the shadow-DOM caveat above.
- **Picking does not update the form.** Forgot `data-value` on the `<li>`, or forgot `name=` on the host.
- **Results wrapped in a `<ul>` or `<div>`.** The component provides the `<ul>`; wrapping breaks slot projection.

---

## 2. Plain HTMX search input — filtering a list

For list-filtering use cases, use a plain Bulma input plus `hx-get` to the canonical list URL with `format=htmx-search-results`.

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
- **Two `format=` values in one URL.** The server should reject this (see [format_contract.md](format_contract.md)).
- **Server returns a fully-rendered page** to a search request. Search responses are fragments.
- **No `hx-push-url`** on a list filter — back button is broken, bookmarks don't work.
