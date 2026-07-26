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
- [Common Buttons & Iconography](components/common_buttons.md) — standard action buttons, icons, colors.
- [Chamfered Corners](components/chamfers.md) — the 45° corner bevel: how it works, how to add or remove it.
- [Dual Listbox Component Guide](components/dual_listbox.md) — the Available/Selected dual-list pattern.
- [Search Bars](components/searchbars.md) — search dropdown component.
- [File Upload](components/file_upload.md) — the `<file-upload>` web component (Bulma file field, filename display, multi-file).
- [Modals & Dialogs](components/modals.md) — native `<dialog>` + Bulma cards; when to use a modal and why assignment never goes in one.
- [Tabs — Allowable Implementation Approaches](components/tabs.md) — ranked tab strategies.
- [Pagination and Shared Partials](components/pagination.md) — the shared pagination pattern.
- [Multi-Step Flows](components/multi_step_flows.md) — session-backed draft flows and the multi-card wizard trigger rule.
- [Accessibility Baseline](accessibility.md) — the accessibility floor for every page.

## Skeletons

- [UI / Front-End — Skeleton Bundle](skeleton_instructions.md) — context-scan bundle for template/HTMX changes.

## Sub-bundles

- `components/` — button, chamfer, dual-listbox, modal, pagination, search-bar, tab, and multi-step-flow guides.
- [Examples/](Examples/index.md) — concrete markup for the component guides above.
