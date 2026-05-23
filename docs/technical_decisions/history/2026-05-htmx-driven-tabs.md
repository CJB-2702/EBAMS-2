# HTMX-driven tabs as the default tab implementation

- **Date:** 2026-05
- **Context / feature:** User edit page (`/administration/users/<pk>/edit/`) and any other non-trivial tabbed surface.

## Decision

Tabs default to **HTMX-driven**: one canonical URL with a `?view=<tab-name>` query parameter, server-side branching on the `HX-Request` header, and `hx-push-url="true"` so back/forward and F5 work.

Web-component tab switchers remain allowed for small, self-contained widgets (Approach 2 in [../../UX_UI/tabs.md](../../UX_UI/tabs.md)) but **only** when the canonical implementation in the component library defers initialization past parse and uses real `<ul>` / `<ol>` containers for slotted list data. Web components are not the default any more.

## Rationale

Three iterations of custom-element tab switchers failed in production-shaped templates:

- `<tabbed-content>` — shadow-DOM and CSS scoping issues with `<li>` parents.
- `<tabbed-content-alt>` — `MutationObserver`-based init fired before grandchild `<li>` panels were parsed; `_tabPanels` captured empty arrays.
- `<tabs-container>` (`tabbed_content_alt2.js`) — `querySelectorAll` in `connectedCallback`, which fires on the opening tag before children exist.

Compounding issue: custom element names (`<left-listbox>`, `<right-listbox>`) used as direct `<li>` parents were *not* parser scoping boundaries, so inner `<li>` items implicitly closed their ancestor tab-panel `<li>`, corrupting the tab structure.

HTMX-driven tabs sidestep all of these: there is no `connectedCallback` race, no shadow DOM, and the HTML parser sees ordinary `<div class="tabs"><ul><li>` markup.

## What "good" looks like

- Each `<li>` carries `hx-get="...?view=<name>"`, `hx-target="#tabs-content"`, and `hx-push-url="true"`.
- The server branches on `HX-Request`: full page on hard load, partial fragment on HTMX nav.
- Each tab's content is a separate partial; only the visible tab is sent over the wire.
- Active-tab highlight is a small click handler that toggles `is-active` on the `<li>` (HTMX only swaps content, not the nav).

## Related

- [../../UX_UI/tabs.md](../../UX_UI/tabs.md) — the four allowable tab strategies and when to use each.
- [../incident_history/2026-05-web_component_tab_incident.md](../incident_history/2026-05-web_component_tab_incident.md) — the underlying incident.
