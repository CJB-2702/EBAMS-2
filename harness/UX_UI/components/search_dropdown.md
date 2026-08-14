---
type: "UX Guide"
title: "Search dropdown component guide"
description: "The <search-dropdown> web component — a form-associated custom element that pairs an input with an HTMX-loaded dropdown of picked results. Source: app/static/web_components/search_dropdown.js."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Search dropdown component guide

`<search-dropdown>` is a reusable, **form-associated** custom element that pairs an input with a dropdown of `<li>` results. Backed by an open shadow root; results are projected into a default `<slot>`. Source: `app/static/web_components/search_dropdown.js`.

**Use this when the search produces a single picked value** that becomes a form field (e.g. picking a permission, a user, an asset). For the decision between this component and a plain HTMX list filter, see [../search/searchbars.md](../search/searchbars.md).

---

## Why a custom element

- **Form participation** via `ElementInternals.setFormValue()` — the picked value submits with the surrounding `<form>` exactly like a native input.
- **HTMX attribute pass-through** — `hx-get`, `hx-target`, `hx-trigger`, etc. on the host element are forwarded to the internal `<input>`.
- **Shadow-DOM-correct `hx-target`** — defaults to `global #<host-id>` so swaps hit the host element in the document, not a stale node inside the shadow tree.
- **No JS bindings on consumer pages** — register the script once, drop the tag, done.

---

## Page-level script registration

```html
<script defer src="{% static 'web_components/search_dropdown.js' %}"></script>
```

## Usage A — permission picker for a role form

```html
<search-dropdown
    id="permission-picker"
    name="permission_id"
    placeholder="search permissions..."
    hx-get="{% url 'permissions_portal_index' %}?format=htmx-search-results&group_id={{ group.id }}"
    hx-trigger="keyup changed delay:300ms, search">
  {# server-rendered <li> results swap into here via HTMX #}
</search-dropdown>
```

The corresponding view returns **only `<li>` elements** (no `<ul>` wrapper), each with `data-value`:

```html
{% for permission in results %}
  <li data-value="{{ permission.id }}" class="is-family-monospace">
    {{ permission.codename }}
    <span class="has-text-grey is-size-7"> — {{ permission.name }}</span>
  </li>
{% empty %}
  <li class="is-disabled">No matches.</li>
{% endfor %}
```

## Usage B — inline owner change on a single row

```html
<form method="post" action="{% url 'asset_set_owner' asset.id %}"
      hx-post="{% url 'asset_set_owner' asset.id %}"
      hx-target="#asset-row-{{ asset.id }}"
      hx-swap="outerHTML">
  {% csrf_token %}
  <search-dropdown
      name="owner_id"
      placeholder="change owner..."
      hx-get="{% url 'users_search' %}?format=htmx-search-results"
      hx-trigger="keyup changed delay:300ms, search">
  </search-dropdown>
</form>
```

---

## Server contract — what the endpoint must return

- **URL:** the canonical collection URL for the resource (e.g. `…/permissions`, `…/users`).
- **Query:** `format=htmx-search-results`, `q=<typed text>`, plus any scope params (`group_id=…`, `org_id=…`).
- **Response body:** **only `<li>` elements** — no surrounding `<ul>`, `<div>`, or template wrapper. The component swaps `innerHTML` into its slot.
- **Each `<li>`** that should be selectable has a `data-value="<id>"`. Disabled / informational rows omit `data-value` (or set `aria-disabled="true"` / class `is-disabled`).
- **Pagination:** include a sentinel `<li>` (e.g. *"Showing 25 of 412 — refine your search…"*) when the result is truncated.

---

## Rules

- **Do not nest** a `<search-dropdown>` inside another `<search-dropdown>`.
- **One per form field.** Two related records → two separate elements with distinct `name=` attributes.
- **Do not** reach into the shadow DOM from page CSS. Style hooks: `::slotted(li)`, `::slotted(li.is-disabled)`, `::slotted(li.is-family-monospace)`. New variants are added to the component, not to a stylesheet.
- **Always set `name=`** on the host element if the picked value should submit with the form.
- **The `q` parameter is fixed.** Internal input is `name="q"` — endpoint must read `q`, not `query` or `term`.
- **Keep the `<li>` markup flat.** Nested interactive children steal click events from the component's selection handler.

---

## Component source (excerpt)

The full component lives at `app/static/web_components/search_dropdown.js`. Key behaviours:

- `formAssociated = true`, `attachInternals()`, `setFormValue(v)` for form participation.
- Open shadow root with a slotted `<ul>`; consumers project `<li>` results into the default slot.
- HTMX attribute pass-through for `hx-get`, `hx-post`, `hx-trigger`, `hx-target`, `hx-swap`, `hx-indicator`, `hx-headers`, `hx-vals`, `hx-params`, `hx-include`, `hx-sync`.
- Defaults `hx-target` to `global #<host-id>` so swaps reach the host element in the document, not the shadow root.
- Internal input fixed at `name="q"` so endpoints can rely on the query parameter name.
- Click handler reads `data-value` from the clicked `<li>` and stores it via `setFormValue`.

Treat the file as the authoritative source; this excerpt is a behaviour summary, not a re-implementation.

---

## Common pitfalls

- **Empty results show no feedback.** Always render a "No matches" `<li class="is-disabled">`.
- **`hx-target` set to a stale element.** Don't override unless you know the shadow-DOM caveat above.
- **Picking does not update the form.** Forgot `data-value` on the `<li>`, or forgot `name=` on the host.
- **Results wrapped in a `<ul>` or `<div>`.** The component provides the `<ul>`; wrapping breaks slot projection.
