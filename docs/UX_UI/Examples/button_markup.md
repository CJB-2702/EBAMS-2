# Button markup snippets

Canonical markup for the actions in [../common_buttons.md](../common_buttons.md). Material Icons (`<span class="icon"><span class="material-icons" aria-hidden="true">…</span></span>`) ship vendored.

## Save (primary, card-footer right slot)

```html
<button type="submit" class="button is-primary card-footer-primary">
  <span class="icon"><span class="material-icons" aria-hidden="true">save</span></span>
  <span>Save</span>
</button>
```

## Cancel (secondary, small, light)

```html
<a href="{% url 'role_detail' role.id %}" class="button is-small is-light">
  <span class="icon"><span class="material-icons" aria-hidden="true">close</span></span>
  <span>Cancel</span>
</a>
```

## Delete (small, danger-light, narrower than Cancel)

```html
<button type="submit"
        class="button is-small is-danger is-light"
        formaction="{% url 'role_delete' role.id %}"
        onclick="return confirm('Delete this role?');"
        style="max-width: 6rem;">
  <span class="icon"><span class="material-icons" aria-hidden="true">delete</span></span>
  <span>Delete</span>
</button>
```

## Edit (navigation, info-light — primary slot on read-only cards)

```html
<a href="{% url 'role_edit' role.id %}"
   class="button is-info is-light is-small card-footer-primary">
  <span class="icon"><span class="material-icons" aria-hidden="true">edit</span></span>
  <span>Edit</span>
</a>
```

## Refresh (HTMX, no full reload)

```html
<button type="button" class="button is-link is-light is-small"
        hx-get="{% url 'asset_list' %}?format=condensed"
        hx-target="#asset-list-container"
        hx-swap="innerHTML"
        hx-indicator=".asset-list-skeleton">
  <span class="icon"><span class="material-icons" aria-hidden="true">refresh</span></span>
  <span>Refresh</span>
</button>
```

## Table-row buttons (icon-only with tooltips)

Wrap actions in `.buttons.are-small` and right-align with `is-justify-content-flex-end`:

```html
<td class="has-text-right">
  <div class="buttons are-small is-justify-content-flex-end">
    <a class="button is-info is-light is-small"
       title="Edit {{ row.name }}"
       aria-label="Edit {{ row.name }}"
       href="{% url 'asset_edit' row.id %}">
      <span class="icon"><span class="material-icons" aria-hidden="true">edit</span></span>
    </a>
    <button type="submit"
            class="button is-danger is-light is-small"
            title="Delete {{ row.name }}"
            aria-label="Delete {{ row.name }}"
            onclick="return confirm('Delete {{ row.name }}?');">
      <span class="icon"><span class="material-icons" aria-hidden="true">delete</span></span>
    </button>
  </div>
</td>
```
