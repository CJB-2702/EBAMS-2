---
type: "UX Guide"
title: "Accessibility baseline"
description: "The accessibility floor every page must meet, plus per-component additions referenced from elsewhere in the UX_UI folder."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Accessibility baseline

The accessibility floor every page must meet, plus per-component additions referenced from elsewhere in the UX_UI folder.

---

## Baseline

- **Keyboard:** all interactive elements are focusable; logical tab order; visible focus ring (Bulma default plus the project's focus shadow).
- **Semantic HTML:** `<main>`, `<nav>`, `<header>`, headings in source order.
- **Color contrast:** meet WCAG AA where feasible for text and interactive controls. Light variants of buttons must still meet AA against the card surface.
- **Fonts inside form inputs:** prefer **monospace** faces with clear distinction among `0`, `O`, `I`, `1`, `l`.
- **RTL:** the canonical card-footer geometry (primary right, secondary left) and left-aligned tabs assume **LTR**. RTL is a future flip, not a current support claim.
- **Reduced motion:** HTMX swap animations honour `prefers-reduced-motion: reduce`. Do not introduce JS animations that ignore the OS preference.

---

## Component-specific accessibility (referenced from peer files)

- **Buttons:** every action has a text label except in the [icon-only exceptions](design_patterns/common_buttons.md#icon-only-buttons) list. Table-row buttons carry both `title` and `aria-label` with the row identifier.
- **Modals:** the native `<dialog>` element provides focus trap, backdrop, and Escape-to-close. Close buttons use `aria-label="close"`.
- **Dual listbox:** each column is a `<ul role="listbox" aria-multiselectable="true">` with a real heading element above it ([components/dual_listbox.md](components/dual_listbox.md)).
- **`<search-dropdown>`:** the host is form-associated and propagates the picked value to the surrounding form ([search/searchbars.md](search/searchbars.md)).

---

## Empty, loading, error states

- **Empty:** explain why there is no data and the next step (e.g. "No assets yet — create one"). Empty-state CTAs live in the card footer with full footer width, not centred inside the card content.
- **Loading:** HTMX `htmx-request` class on indicators; avoid layout shift where possible. Pair with a Bulma skeleton block in the same container so dimensions are preserved.
- **Error:** human-readable message; 403/404/500 pages are distinct in production and include breadcrumbs back to a useful starting point.

---

## What this baseline is not

- It is not a full WCAG audit. Specialised flows (data export, complex tables, drag-and-drop) need their own accessibility review.
- It is not a substitute for screen-reader testing. Components that change focus or visibility (modals, search dropdowns, listboxes) should be exercised with NVDA / VoiceOver before sign-off.
