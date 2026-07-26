---
type: "UX Guide"
title: "The `format=` density contract"
description: "A single query parameter — format= — chooses the visual density of a collection or detail page, **or** an HTMX fragment variant of the same canonical URL."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# The `format=` density contract

A single query parameter — `format=` — chooses the visual density of a collection or detail page, **or** an HTMX fragment variant of the same canonical URL. The same value means the same visual density on list and detail surfaces for that resource type.

Collection URLs follow the plural-resource pattern in [../Architecture.md](../Architecture.md) (`endpoint_patterns.md`). Singular URLs follow the detail pattern (`…/event/<id>`). Use the same `format=` vocabulary for **both**.

---

## Density values (full pages)

| `format` value | Purpose |
| :--- | :--- |
| **`condensed`** (default) | Table: column titles and one row per record; show only fields native to that table when possible. Omit `format` or set `format=condensed`. |
| **`medium`** | Short, full-width rows or boxes — richer than a flat table (joins, summaries), still scannable. |
| **`large`** | Card list: complex relationships and expected interactivity (actions, expandable regions, embedded controls). |

**Default:** for collection GET requests with no `format`, render `condensed`. For singular GET requests with no `format`, use the same default density as the list for that resource type so navigation between list and detail does not change visual scale.

---

## HTMX fragment values

The same query parameter selects HTMX-only response variants:

- `format=htmx-search-results` — fragment-only response containing the results list partial (see [components/searchbars.md](components/searchbars.md)).
- `format=htmx-focused` — fragment-only response suited to HTMX, with paged rows.
- `format=htmx-<custom>` — predictable, per-screen custom variants. Document the name in the view or app docs so clients and tests stay aligned.

---

## Mutual exclusion and defaults

- The server accepts **at most one** `format` value per request.
- **Do not combine** density values (`condensed`, `medium`, `large`) with HTMX fragment values (`htmx-*`). If a client sends conflicting values, the view must **reject** the request (e.g. 400) or apply a documented precedence rule. Prefer validation over silent merge.

| | Full page (typical) | Fragment-only (HTMX) |
| :--- | :--- | :--- |
| **List density** | `condensed` / `medium` / `large` | Not used — use `hx-select` on a full page when possible. |
| **HTMX** | N/A | `htmx-search-results`, `htmx-focused`, etc. |

Pagination and sorting remain query parameters alongside `format`.

---

## Custom formats and dedicated fragment paths

- **Custom `format` values** are allowed when a screen needs behaviour or markup that does not fit the standard densities or shared HTMX names. Use predictable names on the **canonical** URL (e.g. `…/event/<id>?format=htmx-event-timeline`).
- **Dedicated fragment routes** are an **exception** when branching on `format=` makes the view unmaintainable — heavy portal-specific logic, many partials, or clear ownership boundaries. In that case you may expose a sub-path such as `…/event/<id>/fragments/<portalname>`. Prefer `format=` on the canonical URL first; add a fragment path only when the trade-off is justified.

---

## Widgets

Some key data types may expose **widgets**: fully custom markup and behaviour.

- **Dedicated routes** are allowed for bespoke experiences, e.g.:
  - `…/events-application/event/<event-id>/get-widget`
  - `…/events-application/events-widget-list`
- When a widget is "just another view" of an existing resource, prefer the canonical URL + `format=` pattern so the same addressable resource does not sprawl across duplicate paths.
