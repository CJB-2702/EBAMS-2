---
type: "UX Example"
title: "Button markup snippets"
description: "Canonical markup for the actions in common_buttons.md."
tags: [ux-ui, ux-example, examples]
context_tier: 3
---

# Button markup snippets

Canonical markup for the actions in [common_buttons.md](common_buttons.md). Material Icons (`<span class="icon"><span class="material-icons" aria-hidden="true">…</span></span>`) ship vendored.

## Master button table

| Action | Material Icon | Color | Bulma classes | When to use |
| :--- | :--- | :--- | :--- | :--- |
| **Save** | `save` | Primary (blue) | `button is-primary card-footer-primary` | Commit form changes. Primary slot, bottom-right. |
| **Create** | `add` | Primary (blue) | `button is-primary card-footer-primary` | Create a new resource. List-page: top-right; create form: primary slot. |
| **Apply** | `check` | Primary (blue) | `button is-primary card-footer-primary` | Apply staged/filter changes. |
| **Submit** | `send` | Primary (blue) | `button is-primary card-footer-primary` | Submit to a workflow (e.g. submit an event for approval). |
| **Edit** | `edit` | Info (cyan) | `button is-info is-light is-small card-footer-primary` | Navigate to the edit form. Primary slot on read-only cards. |
| **Cancel** | `close` | Light grey | `button is-small is-light` | Discard unsaved changes. Secondary slot. |
| **Reset** | `restart_alt` | Light grey | `button is-small is-light` | Restore initial values without leaving the page. Secondary slot. |
| **Delete** | `delete` | Danger light (pink) | `button is-small is-danger is-light` | Remove a resource. Always small, always confirmed. |
| **Remove** | `remove` | Danger light (pink) | `button is-small is-danger is-light` | Detach an item from a relation. |
| **Refresh** | `refresh` | Link (blue) | `button is-link is-light` | Re-fetch the current view's data without a full page reload. |
| **Search** | `search` | n/a (icon-only) | inside `<search-dropdown>` | See [../search/searchbars.md](../search/searchbars.md). |
| **Filter** | `filter_list` | Light grey | `button is-light` | Open a filter panel or apply filter chips. |
| **Sort** | `sort` | Light grey | `button is-light` | Open the sort selector. |
| **Export** | `file_download` | Link (blue) | `button is-link is-light` | Download data (CSV, JSON). Always opens a download. |
| **Import** | `file_upload` | Link (blue) | `button is-link is-light` | Upload data. Opens a modal or dedicated page. |
| **Approve** | `check_circle` | Success (green) | `button is-success` | Affirmative state transition (approve, publish, activate). Solid. |
| **Reject** | `cancel` | Warning (yellow) | `button is-warning is-light` | Negative state transition that is **not destructive**. |
| **Restore** | `restore` | Success light (green) | `button is-small is-success is-light` | Undo a soft delete or revert. |
| **Copy** | `content_copy` | Light grey | `button is-small is-light` | Copy a value to the clipboard. Icon-only is acceptable. |
| **Settings** | `settings` | Light grey | `button is-light` | Open settings for the current resource. |
| **More / Menu** | `more_vert` | Light grey | `button is-small is-light` | Open a dropdown of less-frequent actions. Icon-only. |
| **Close** | `close` (or Bulma `.delete`) | n/a | `delete` (Bulma) inside `<dialog>` headers | Dismiss a modal or banner. Icon-only. |

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
