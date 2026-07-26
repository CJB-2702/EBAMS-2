---
type: "UX Guide"
title: "File browser component guide"
description: "A **file browser** renders an attachment set as switchable **Tiles** or **List** views with client-side filter and sort."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# File browser component guide

`<file-browser>` renders an **attachment set** (a part's library documents, a
comment's files, any collection of uploaded files) as a small file-manager: a
toolbar with search, type/uploader filters, and sort, over a body that switches
between a **Tiles** grid and a compact sortable **List**.

It is a **progressive-enhancement** component. The server renders one plain
`<a href>` per file as a light-DOM child; the component reads those children and
repaints them. With JS disabled, the raw links remain a usable file list — the
[F5 rule](../../ARCHITECTURE/HTMX_PATTERNS.md) holds.

Implemented at [app/static/web_components/file_browser.js](../../../app/static/web_components/file_browser.js).
First used on the part library — [app/parts/templates/parts/_library_section.html](../../../app/parts/templates/parts/_library_section.html).

---

## When to use

Reach for `<file-browser>` when **all** of these hold:

| Condition | Why it matters |
| :--- | :--- |
| You have a **set of uploaded files** to display | This is a file lister, not a generic list. |
| The set is **small-to-moderate** (up to ~a few dozen) | Filter/sort is **vanilla JS over DOM nodes** — no pagination, no server round trips. For large or paged sets, use an HTMX-backed table instead. |
| Users benefit from **switching Tiles ⇆ List** | Tiles for visual scanning (images), List for scanning by size/date/uploader. |
| The files are **already server-rendered on page load** | The component enhances existing markup; it does not fetch. |

Do **not** use it when:

- The set is large or must be **paginated / server-filtered** — use a normal table + HTMX (see [pagination.md](pagination.md), [searchbars.md](searchbars.md)).
- You only ever need one fixed layout of two or three files — a plain grid is lighter.

---

## Anatomy

- **Toolbar** (always rendered, even when empty):
  - **Search** — live substring match over filename + caption.
  - **Type chips** — All / Images / Documents / Video (only chips with matching files appear).
  - **Uploader filter** — a dropdown of distinct uploaders (hidden when there is only one).
  - **Sort** — Name / Size / Type / Date / Uploader, plus an asc·desc toggle. Default **Date descending** (newest first).
  - **View toggle** — Tiles ⇆ List, **persisted in `localStorage`**.
- **Body** — Tiles grid or List table. The Tiles grid adapts to the active
  type filter: **Images** render as large vertical gallery cards (thumbnail on
  top, size · date beneath); **All / Documents / Video** render as compact
  horizontal mini-cards (44px thumb left, name + caption stacked).
- **Empty state** — the toolbar and frame always render; the body shows `No files.` (empty set) or `No files match your filters.` (everything filtered out). Never hide the component when empty — see the [empty-cards rule](../../../.claude/CLAUDE.md).

---

## Data contract — light-DOM children

The server renders one child per file. The **visible spans are the no-JS
fallback**; the **`data-*` attributes are the machine-readable truth** the
component filters and sorts on.

```html
<file-browser default-view="tiles" storage-key="lib-file-browser-view">
  <a class="fb-item" href="{% url 'file_download' file_id=d.file_id %}"
     data-name="{{ d.filename }}"
     data-caption="{{ d.caption }}"
     data-type="image|document|video"
     data-thumb="{% url 'file_inline' file_id=d.file_id %}"   {# images only #}
     data-size="{{ d.file_size }}"                            {# bytes #}
     data-date="{{ d.created_at }}"                           {# ISO-8601, for sorting #}
     data-date-display="{{ d.created_at_display }}"           {# friendly, for display #}
     data-user="{{ d.created_by }}"
     data-id="{{ d.id }}">
    <span class="fb-thumb"><img src="…" alt=""></span>        {# fallback rendering #}
    <span class="fb-name">{{ d.filename }}</span>
    <span class="fb-caption">{{ d.caption }}</span>

    {# per-item actions stay SERVER-rendered (permissions live server-side) #}
    <span slot="actions">
      <form method="post" action="…">{% csrf_token %}…<button>Remove</button></form>
    </span>
  </a>
  {% empty %}
  <p class="has-text-grey is-size-7">No documents yet.</p>
  {% endfor %}
</file-browser>
```

### JS API

| Method | Effect |
| :--- | :--- |
| `el.setView("tiles" \| "list")` | Programmatically switch the view (persists like the in-toolbar toggle). Used by a page-level "toggle all" control to drive every `<file-browser>` at once, e.g. `document.querySelectorAll("file-browser").forEach(fb => fb.setView("list"))`. |

### Host attributes

| Attribute | Default | Meaning |
| :--- | :--- | :--- |
| `default-view` | `tiles` | Initial view when no stored preference exists. |
| `storage-key` | `file-browser-view` | `localStorage` key for the view preference. Give each distinct browser its own key if you don't want them to share state. |

### Per-item `data-*`

| Attribute | Used for |
| :--- | :--- |
| `data-name` | display + name sort + search |
| `data-caption` | display + search |
| `data-type` | type chips + type sort (`image` / `document` / `video`) |
| `data-thumb` | image thumbnail src (omit for non-images) |
| `data-size` | size column + size sort (bytes) |
| `data-date` | **date sort — ISO-8601 UTC**, so string compare is correct |
| `data-date-display` | human-friendly date shown in the UI |
| `data-user` | uploader filter + column |
| `data-id` | stable identity (unused by the component today; handy for actions) |

---

## Key rules

- **Two representations, one source.** Precise value in `data-*`, friendly value
  in the visible span. Sort on the attribute, display the span.
- **Dates are ISO in the attribute.** Emit `created_at.isoformat()` into
  `data-date`; put the friendly `"%b %d, %Y"` string in `data-date-display`.
  String comparison of ISO timestamps sorts correctly with no `Date` parsing.
- **Actions stay on the server.** Render Remove / Set-primary / etc. inside
  `<span slot="actions">` gated by the usual capability check. The component
  relocates that markup into each tile/row but never decides who may act.
- **One browser per logical group.** On the part library, each section (Base +
  each revision) gets its own `<file-browser>`, preserving the revision model.
- **Client-side only.** All filtering and sorting happen in the browser over the
  rendered children. This is deliberate for small sets; do not extend it to
  handle server pagination — switch components instead.

---

## Backend note

The attachment-set dict must supply the date twice and the uploader once. For
the parts library this lives in
[PartThreadManager.documents()](../../../app/parts/control_layer/managers/part_thread_manager.py):

```python
"created_at": a.created_at.isoformat(),          # ISO — client sort key
"created_at_display": a.created_at.strftime("%b %d, %Y"),
"created_by": str(a.created_by) if a.created_by_id else "—",
```

`created_at` is the **Attachment**'s timestamp — when the file was linked to
*this* section — not the underlying File's first-upload time.
