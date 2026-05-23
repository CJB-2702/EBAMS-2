# `<search-dropdown>` — markup and component source

Reference markup and the full web component source for the picker described in [../searchbars.md](../searchbars.md).

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

## Plain HTMX list filter

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

## Component source (excerpt)

The full component lives at `app/static/web_components/search_dropdown.js`. Key behaviours:

- `formAssociated = true`, `attachInternals()`, `setFormValue(v)` for form participation.
- Open shadow root with a slotted `<ul>`; consumers project `<li>` results into the default slot.
- HTMX attribute pass-through for `hx-get`, `hx-post`, `hx-trigger`, `hx-target`, `hx-swap`, `hx-indicator`, `hx-headers`, `hx-vals`, `hx-params`, `hx-include`, `hx-sync`.
- Defaults `hx-target` to `global #<host-id>` so swaps reach the host element in the document, not the shadow root.
- Internal input fixed at `name="q"` so endpoints can rely on the query parameter name.
- Click handler reads `data-value` from the clicked `<li>` and stores it via `setFormValue`.

Treat the file as the authoritative source; this excerpt is a behaviour summary, not a re-implementation.
