---
type: Architecture Guide
title: HTMX Patterns
description: Conventions for layering HTMX interactivity on a static-first Django MPA.
tags: [architecture, htmx, frontend, progressive-enhancement]
---

# HTMX & Progressive Enhancement Guidelines

## Core philosophy: "Enhanced, not defined"

The application must remain a functional Django Multi-Page Application (MPA) at its core. HTMX is used to layer interactivity and "snappiness" on top of standard browser behaviours.

**Note:** These are loose guidelines intended to keep the codebase maintainable and the user experience consistent. They are not firm rules; specific widgets or complex interfaces may require exceptions at the developer's discretion.

---

## 1. The baseline: static-first development

- **The F5 rule:** Every page and state should be reachable and functional via a standard static page reload.
- **Session-driven state:** Use Django `request.session` to track transient UI states, wizard progress, or "just updated" flags.
- **Django source of truth:** Prefer getting the **full page** back from the server. Use HTMX to pluck the relevant components out of that full response.

---

## 2. General interaction patterns

### A. Editing existing models
1. **POST** the data to the standard Django update endpoint.
2. The server processes the change and redirects (303) to the detail or parent page.
3. HTMX fetches the full target page but uses `hx-select` to isolate the specific component.
4. **Feedback:** Include a Django "Success" message. Use an Out-of-Band (OOB) swap or a client-side trigger to flash this message.

### B. Adding data to existing items
1. POST to the creation endpoint.
2. The server re-renders or redirects to the **entire parent entity**.
3. HTMX replaces the entire parent container. This ensures side effects (updated counts, "last activity" timestamps) update automatically.

### C. The creation workflow: namespaced session sub-components

For adding sub-fields or related data to an item before it is committed (e.g. adding an "Assigned User" while on `/events/create`):

1. **Namespaced storage:** store draft information under a nested dictionary specific to the feature, e.g. `request.session['event_draft']`.
2. **POST via HTMX:** submit the sub-component data to a specialised session-update endpoint.
3. **No DB commit:** the server validates and updates the nested dictionary. Set `request.session.modified = True`.
4. **Full page refresh / HX-Get:** the server responds with a redirect or HTMX-triggered fetch of the full `/events/create` page.
5. **Template logic:** the Django template reads the session dict to render badges/rows as if they were saved.
6. **Finalisation & cleanup:** on submit, pull data from session, bulk commit, and `del request.session['event_draft']`.

---

## 3. The search-bar exception (partial templates)

Search results use a dedicated partial template for speed and reduced server load.

- **URL contract:** the **same canonical route** as the normal list (no parallel `/search` path). Add `format=htmx-search-results` plus the search query (`q`). The view branches on `format` and returns **only** the results fragment.
- **Example URL:** `.../comments?format=htmx-search-results&q=query`.

For markup see [../Examples/htmx_csrf_and_search_snippets.md](../Examples/htmx_csrf_and_search_snippets.md).

---

## 4. Visual feedback: Bulma skeletons

Use Bulma's skeleton/loading states for round-trip feedback.

- **Indicator targeting:** the `.htmx-indicator` class on Bulma skeleton elements.
- **Implementation:** wrap components in a container that toggles between real data and skeleton during the request.

---

## 5. CSRF, Django middleware, and HTTP methods

HTMX may use `hx-get`, `hx-post`, `hx-put`, `hx-patch`, and `hx-delete` so the browser sends the same verbs as the OOP endpoint design (see [endpoint_patterns.md](endpoint_patterns.md)). That aligns with REST-style routes while keeping CSRF protection.

**Base template hook:** include a `htmx:configRequest` listener once in the project base template so every HTMX request sends the CSRF token header. See [../Examples/htmx_csrf_and_search_snippets.md](../Examples/htmx_csrf_and_search_snippets.md). Middleware requirements and PUT/PATCH body-parsing detail: [../Examples/csrf_and_http_methods.md](../Examples/csrf_and_http_methods.md).

---

## 6. Full documents vs fragment-only responses

There is **no** conflict between "prefer `hx-select`" and "partials via query parameters."

- **Default:** the server renders a **full HTML page** for the resource URL. HTMX uses `hx-select="#fragment-id"` to pull a piece of that response into the DOM — without a separate route. The URL stays canonical; the "partial" is a slice of the full document.
- **When a fragment-only response is required** (§3 search results, §7 focused widgets): keep the **same canonical URL** and branch on **query parameters** (`format=htmx-search-results`, `format=htmx-focused`). The view returns **only** the partial template for that request.

**Prefer `hx-select`** for the default case. Avoid creating many `_partial.html` files **unless** you are in the fragment-only cases above.

**Boosting:** use `hx-boost="true"` on top-level navigation and main content containers to convert standard links into AJAX requests automatically.

**CSS transitions:** utilise `htmx-swapping` and `htmx-settling` classes to smooth out replacement of large components.

**Status codes:** return appropriate HTTP status codes (e.g. `422 Unprocessable Entity` for validation errors).

---

## 7. Exceptions to the rule

Full-page refreshes and session-dict state are the standard. **Focused widgets** (real-time search bar, complex drag-and-drop kanban, live notification bell) may return **fragment-only** HTML and use specialised HTMX triggers (`hx-trigger="keyup changed delay:500ms"`). Implement with the **same canonical URL + `format=`** pattern from §6, not ad-hoc duplicate routes.
