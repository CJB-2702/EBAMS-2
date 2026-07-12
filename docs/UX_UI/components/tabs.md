# Tabs — allowable implementation approaches

Four allowable tab strategies, ranked by preference. Pick the one that matches the page's content size and interactivity profile. Background on the failed web-component-only path: [../technical_decisions/incident_history/2026-05-web_component_tab_incident.md](../technical_decisions/incident_history/2026-05-web_component_tab_incident.md).

## Approach 1 — HTMX (preferred for large pages)

**Use case.** Pages where the combined content across all tabs is heavy — many forms, many lists, many database-driven panels (for example `/administration/users/<pk>/edit/`).

**Rule.** Prefer this when the total content across all tabs exceeds **1,000 lines** of template code. Lazy-loading each tab over HTMX keeps the initial page load light.

**Pattern.** One canonical URL, branch on the `HX-Request` header plus a `?view=` query parameter (per [../Architecture.md](../Architecture.md) HTMX rules).

```html
<div class="tabs">
  <ul>
    <li class="is-active"
        hx-get="/administration/users/2/edit?view=information"
        hx-target="#tabs-content"
        hx-push-url="true">
      <a>Information</a>
    </li>
    <li hx-get="/administration/users/2/edit?view=permissions"
        hx-target="#tabs-content"
        hx-push-url="true">
      <a>Permissions</a>
    </li>
    <li hx-get="/administration/users/2/edit?view=data-access"
        hx-target="#tabs-content"
        hx-push-url="true">
      <a>Data Access</a>
    </li>
  </ul>
</div>

<div id="tabs-content">
  {% include tab_partial %}
</div>
```

In the view, branch on the request: full page on a hard load, partial fragment on HTMX nav.

**Why this scales.** F5 still works (every `?view=` URL renders a full page). Browser back/forward works via `hx-push-url="true"`. No third-party tab library, no custom-element timing pitfalls.

---

## Approach 2 — Web components (preferred for small pages)

**Use case.** Smaller, self-contained tabbed widgets where the combined content is light enough to ship in the initial response and no part of the tab content needs to be lazy-loaded.

**Rule.** Use the approved web-component pattern from the component library. Two non-negotiable requirements pulled from the [Web Component Tab Incident](../technical_decisions/incident_history/2026-05-web_component_tab_incident.md):

1. **Defer init past parse.** Do not call `querySelectorAll` in `connectedCallback` — it fires on the opening tag, before children exist. Either defer to `DOMContentLoaded`, gate on a `tabPanels.length > 0` MutationObserver with `subtree: true`, or call `customElements.define(...)` inside a `DOMContentLoaded` handler so upgrades happen after the full tree is parsed.
2. **Never put `<li>` children inside a custom element that is itself inside a `<li>`** without a real `<ul>` / `<ol>` between them. Custom element names are not parser scoping boundaries — an inner `<li>` will implicitly close the outer one and corrupt the tab structure. Use `<ul data-slot="left">` (as in `<dual-listbox-alt>`) when you need to pass list data to a slotted child.

If a working canonical implementation is not yet checked in, fall back to **Approach 1** for the current page and reopen the component only when the timing-safe scaffold has been merged with a kitchen-sink demo proving it works under server-rendered HTML.

---

## Approach 3 — Static HTML pages (fallback for simple navigation)

**Use case.** Rare cases where each "tab" is really a distinct top-level resource and full page reloads between them are acceptable.

**Rule.** Render distinct URLs for each tab; hardcode `is-active` on the current page's tab.

**Why use it.** Zero JS, zero HTMX, dead-simple. Falls out of URL routing for free. Pair with `hx-boost` on the main content container for a smoothed transition.

---

## Approach 4 — Native JavaScript (discouraged)

**Use case.** Quick client-side toggling when neither HTMX nor a web component is appropriate. Treat as a stop-gap.

**Strongly discouraged** in favour of Approach 1 or 2, because:
- No URL state — F5 always returns to the first tab. Violates the F5 rule.
- No browser back/forward integration.
- All tab content is shipped on every page load even when only one tab is shown.
- Tends to grow into a custom mini-framework as features are bolted on.

---

## Quick decision matrix

| Scenario | Approach |
| :--- | :--- |
| Total tab content > 1,000 lines, or any tab fetches a lot of data | **1 — HTMX** |
| Small self-contained tabbed widget, all content cheap to render once | **2 — Web Component** |
| Each "tab" is really a distinct resource page | **3 — Static HTML** |
| Anything else | Reconsider; if truly stuck, **4 — Native JS** with a comment justifying it |
