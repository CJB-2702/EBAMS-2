---
okf_version: "0.1"
type: "Index"
title: "UX/UI Knowledge Bundle"
description: "Visual language, density contract, HTMX component patterns, and accessibility baseline."
tags: [ux-ui, index, okf]
context_tier: 1
personas: [frontend, code-architect]
---

# UX / UI

Bulma + HTMX conventions, component guides, and the density/format contract.

## Guides

- [Visual Language and Tokens](visual_language.md) — Bulma theme layer, square/chamfered corners, tokens.
- [The `format=` Density Contract](format_contract.md) — density query parameter and HTMX fragment rule.
- [Page Structure: Shell, Hero, Sidebars, Stat Bars](page_structure.md) — common page chrome.
- [Form & Action Layout Style Guide](form_style_guide.md) — action placement on cards and forms.
- [Accessibility Baseline](accessibility.md) — the accessibility floor for every page.

## Components — literal web components

How to use the reusable custom elements under `app/static/web_components/`.

- [Dual Listbox Component Guide](components/dual_listbox.md) — the `<dual-list-box>` / `<list-box>` Available/Selected pattern (+ [markup](components/dual_listbox_markup.md)).
- [File Browser](components/file_browser.md) — the `<file-browser>` progressive-enhancement file lister.
- [File Upload](components/file_upload.md) — the `<file-upload>` web component (Bulma file field, filename display, multi-file).
- [Search Dropdown](components/search_dropdown.md) — the `<search-dropdown>` picker component.

## Navigation

- [Tabs — Allowable Implementation Approaches](navigation/tabs.md) — ranked tab strategies (+ [HTMX markup](navigation/tabs_htmx_markup.md)).
- [Pagination and Shared Partials](navigation/pagination.md) — the shared pagination pattern.

## Search

- [Search & Select Patterns — Overview](search/list_management_patterns.md) — seven ways to search, pick, and assign items into a list, and which to reach for.
- [Search Bars](search/searchbars.md) — search-dropdown vs. plain HTMX list filter, and when to use each.
- [Search Row Cards Pattern](search/search_row_cards_pattern.md) — full-width row-card layout for search results and lists.

## File management

- [File Upload Field Markup](file_management/file_upload_markup.md) — the hand-written Bulma file-input pattern predating the `<file-upload>` component.

## Design patterns

- [Common Buttons & Iconography](design_patterns/common_buttons.md) — standard action buttons, icons, colors (+ [markup](design_patterns/button_markup.md)).
- [Chamfered Corners](design_patterns/chamfers.md) — the 45° corner bevel: how it works, how to add or remove it.
- [Modals & Dialogs](design_patterns/modals.md) — native `<dialog>` + Bulma cards; when to use a modal and why assignment never goes in one.
- [Multi-Step Flows](design_patterns/multi_step_flows.md) — session-backed draft flows and the multi-card wizard trigger rule.
- [Left Heavy Assignment Card Pair](design_patterns/left_heavy_assignment_card_pair.md) — paired-card assignment layout.
- [Card Footer Markup](design_patterns/card_footer_markup.md) — footer action layout for [form_style_guide.md](form_style_guide.md).
- [Page Hero Markup](design_patterns/page_hero_markup.md) — markup for [page_structure.md](page_structure.md).
- [Page Shell — Grid and Z-Index Values](design_patterns/page_grid_values.md) — exact pixel/stacking detail for [page_structure.md](page_structure.md).

## Skeletons

- [UI / Front-End — Skeleton Bundle](skeleton_instructions.md) — context-scan bundle for template/HTMX changes.
