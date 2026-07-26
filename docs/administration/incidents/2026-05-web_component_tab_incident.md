---
type: "Technical Decision"
title: "Web Component Tab Incident"
description: "Three iterations of custom-element web components were tried as the tab switcher for the user edit page."
tags: [technical-decisions, technical-decision, incident-history]
context_tier: 2
---

# Web Component Tab Incident

- **Date:** 2026-05
- **Affected page:** `/administration/users/<pk>/edit/` (and any other page that adopted the same web-component tab pattern).

## What failed

Three iterations of custom-element web components were tried as the tab switcher for the user edit page. In every attempt, only the first tab worked. The other tabs never showed content. The first tab appeared to work only because its `is-active` (or `active`) class was baked into the static HTML and was never re-managed by the JS.

The iterations:

- `<tabbed-content>` — original component. Child-scoping issues with `<li>` parents. Shadow-DOM and CSS scoping problems.
- `<tabbed-content-alt>` — no shadow-DOM issues. Worked for small examples; failed for larger dynamic components. `MutationObserver`-based init fired before grandchild `<li>` panels were parsed, so `_tabPanels` captured an empty array and clicks never toggled anything.
- `<tabs-container>` (`tabbed_content_alt2.js`) — minimal rewrite that ran `querySelectorAll` directly in `connectedCallback`. Same root timing issue: `connectedCallback` fires on the opening tag, before children exist, so the buttons/panels NodeLists were empty.

## Root cause

Two intertwined HTML/DOM realities:

1. **`connectedCallback` fires too early.** It runs on the opening tag of a custom element, before the parser has reached the closing tag — so child nodes do not yet exist when `connectedCallback` runs. Any `querySelectorAll` for descendants returns an empty NodeList, and any `_tabPanels.length === 0` initialization path silently does nothing.
2. **Custom element names are not HTML parser scoping boundaries.** The original `<dual-listbox>` used custom element names (`<left-listbox>`, `<right-listbox>`) as direct `<li>` parents. The parser treated those custom elements as transparent for the purposes of `<li>` auto-closing, so inner `<li>` items implicitly closed their ancestor tab-panel `<li>`, ejecting list items and corrupting the tab container structure.

## What changed

- HTMX-driven tabs adopted as the default tab implementation. See [../../../harness/UX_UI/history/2026-05-htmx-driven-tabs.md](../../../harness/UX_UI/history/2026-05-htmx-driven-tabs.md) and [../../UX_UI/components/tabs.md](../../../harness/UX_UI/components/tabs.md).
- Dual-listbox slot containers replaced with real `<ul data-slot="left">` lists in the parser's special category, so `<li>` traversal stops correctly. See [../../UX_UI/components/dual_listbox.md](../../../harness/UX_UI/components/dual_listbox.md).
- Two non-negotiable rules added for any future custom-element tab implementation:
  1. **Defer init past parse.** Either listen for `DOMContentLoaded`, use a `MutationObserver` with `subtree: true` gated on `tabPanels.length > 0`, or call `customElements.define(...)` inside a `DOMContentLoaded` handler so upgrades happen after the full tree is parsed.
  2. **Never put `<li>` children inside a custom element that is itself inside a `<li>`** without a real `<ul>` / `<ol>` between them.

## Why this is in the decision system

The combination of parser-timing surprises and HTML5 scoping rules is not obvious from training data, and re-deriving it from first principles would cost another half-day. Encoding the constraint here means future engineers and AI agents skip the failure mode entirely.
