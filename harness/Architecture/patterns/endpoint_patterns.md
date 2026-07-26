---
type: Architecture Guide
title: Endpoint Patterns
description: Object-oriented design guidelines for the entrypoint and HTTP surface of the project.
tags: [architecture, endpoints, presentation-layer, oop]
---

# Django Object-Oriented Endpoint Design Guidelines

## 1. Purpose

This document standardises the entrypoint surface of the project. Functional views are acceptable for simple data retrieval (read-only lists); class-based views are the default for resource-specific endpoints. This ensures code reuse, modularity, and predictable URLs.

## 2. Core philosophy

- **Resource-centric.** Use Class-Based Views (CBVs) for operations tied to a specific model instance or resource lifecycle.
- **Predictable routing.** Align URL structures with the model name and standard HTTP methods.
- **DRY.** Use inheritance and mixins to share permissions, validation, and logging.

---

## 3. Implementation standards

### 3.1 List views (functional exception)

Functional views are permitted for broad entry points that aggregate data or provide complex filtering for a collection.

**Path pattern:** a plural resource segment followed by a named action, with a trailing slash. Example: `events-application/view-events`.

**Creation portals:** screens whose purpose is to **create** a new instance use the path `application/plural-class/create/`. Example: `events-application/events/create`.

### 3.2 Plural / collection routes (OOP)

For the **collection** — listing items and performing **bulk** operations — use Class-Based Views on the plural resource path.

Example path: `events-application/events`.

| Method | Purpose | Request body |
| :--- | :--- | :--- |
| GET | View the list of items. Query parameters for pagination, filters, sort. | None |
| DELETE | Bulk delete: remove the rows whose ids are named in the body. | Structured body listing ids. |
| PATCH | Bulk mutation: one logical command applied to many rows. | `{command, ids, value}`. |

### 3.3 Single-resource operations (the OOP standard)

For viewing, creating, updating, and deleting **one** resource, **Class-Based Views must be used**. Map directly to the model name.

Example path: `events-application/event/<id-or-slug>`.

| Method | Purpose |
| :--- | :--- |
| GET | Retrieve resource details. |
| POST | Create or perform a state-changing action. |
| PUT / PATCH | Update an existing resource. Prefer PATCH for partial updates. |
| DELETE | Remove a resource. |

### 3.4 Child collections (nested under a parent)

When a resource belongs to another resource (comments on an event), expose the child collection under the parent's detail path. Example: `events-application/event/<event-id>/comments`.

| Method | Purpose |
| :--- | :--- |
| GET | List child items for that parent. |
| POST | Create a new child item associated with that parent. The body carries the child's fields. The parent is identified **only** by the URL. |

Operations on **one** child row use the child detail pattern: extend the path with the child's own id after the plural segment.

### 3.5 HTMX and partial templates (query parameters, not extra routes)

When a response must be a **partial** fragment instead of a full document, **do not** introduce parallel URL paths whose only job is to name a template variant. Keep one canonical route and branch on **query parameters**.

This complements [htmx_patterns.md](htmx_patterns.md): the **default** pattern is a **full-page** response with HTMX using **`hx-select`** to extract a fragment. When bandwidth or UX requires a **fragment-only** body (search, live widgets), use the **`format=`** query parameter on the **same** URL.

Examples (illustrative):

- **Search GET** (same path as the list): add `format=htmx-search-results` and `q=` — return only the results list partial.
- **Child collection GET**: add `format=htmx-focused&pagination=true&page=1&count=5` — return a paged fragment.
- **Single resource GET**: same canonical detail URL with `?format=htmx-event-focused-view` for a focused widget.

Treat these query parameters as part of the public contract for each route.

For broader HTMX conventions (headers, targets, OOB updates, `hx-put`/`hx-patch`/`hx-delete` with CSRF), see [htmx_patterns.md](htmx_patterns.md).

---

## 4. Guidelines for logic placement

1. **Entry points (views) should be thin.** Their responsibility is to parse requests, call the control layer or search, and return responses.
2. **Mixins** for cross-cutting concerns (export, audit behaviour) rather than duplicating code.
3. **Encapsulation:** Logic related to the state of a domain object lives in the control layer (see [oop_control_patterns.md](oop_control_patterns.md)), invoked by the view.

---

## 5. Summary table

| Feature | Entry-point style | Example URL | Recommended usage |
| :--- | :--- | :--- | :--- |
| Global list | Functional view | Path with plural segment and named action | Filtering, searching, dashboarding |
| Creation portal | Functional or CBV | `application/plural-class/create` | Dedicated create flow, wizard, or empty form |
| Collection (list + bulk) | Class-based view | Plural collection root | GET for list; DELETE for bulk delete; PATCH for bulk command |
| CRUD on one row | Class-based view | Singular resource plus id | View, edit, delete, update |
| Child collection | Class-based view | Parent detail path plus plural child segment | GET to list children; POST to create a child scoped to the parent |
| Single child row | Class-based view | Child collection path plus child id | View, edit, or delete one child |
| Partial / HTMX fragment | Same route as the matching GET | Canonical path plus query params | Return a partial instead of duplicating paths |
| State actions | Class-based view | Singular resource plus id and optional sub-path | Specialised transitions (e.g. cancel) |

---

## 6. Exceptions

Functional views may still be used for:
- Webhooks with non-standard payloads.
- Simple redirects or static page rendering.
