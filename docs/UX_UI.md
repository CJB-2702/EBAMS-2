# UX / UI — Tier 1 Anchor

This file is the **concept anchor** for the front-end. It states the visual language, the page-structure rules, and the contracts that hold every Bulma + HTMX surface together. Detail and markup live in the Tier 2 files below.

---

## Core ideas

- **Server-rendered MPA, enhanced with HTMX.** Every page is reachable and functional via a plain full-page reload (the "F5 rule"). HTMX layers interactivity on top — it never *defines* a state that does not exist without it.
- **Bulma is the chrome.** Layout, components, and tokens come from vendored Bulma. The project CSS layer adds sharp corners, dark-mode tokens, and a small set of named patterns (page hero, card footer, dual listbox). No forks of Bulma, no per-page custom colour scales.
- **Sharp corners everywhere.** All Bulma radius variables are pinned to zero. No pill buttons, no rounded cards. This is a hard rule, not a taste call.
- **One canonical URL per resource.** Density (`condensed` / `medium` / `large`) and HTMX fragments (`htmx-*`) are chosen by a single `format=` query parameter. Parallel "fragment-only" URLs are an anti-pattern; the same view branches on `format=`.
- **Primary actions live in the card footer.** Forms wrap their content in a card; the footer carries one primary action on the right and small secondaries on the left. Delete is always small, always confirmed, never primary.
- **Multi-step flows are one URL.** A "step 1 of 3" is one scrolling page with later sections disabled until earlier ones validate. Splitting a draft across `/create/step-1`, `/create/step-2` is reserved for genuinely exceptional cases.
- **Accessibility is the floor, not a feature.** Keyboard navigation, semantic HTML, WCAG AA contrast, and labelled controls are baseline; specific components extend that floor with their own rules.

---

## Sub-specifications

| Topic | File |
| :--- | :--- |
| Visual tokens, sharp corners, dark-mode strategy | [UX_UI/visual_language.md](UX_UI/visual_language.md) |
| Page shell, hero, sidebars, stat bars, portal patterns | [UX_UI/page_structure.md](UX_UI/page_structure.md) |
| `format=` density contract and HTMX fragment variants | [UX_UI/format_contract.md](UX_UI/format_contract.md) |
| Card footer geometry, primary/secondary slot rules, inline forms | [UX_UI/form_style_guide.md](UX_UI/form_style_guide.md) |
| Multi-step flows, session-backed drafts, namespaced state | [UX_UI/multi_step_flows.md](UX_UI/multi_step_flows.md) |
| Native `<dialog>` + Bulma card modals; `commandfor`/`command` | [UX_UI/modals.md](UX_UI/modals.md) |
| Allowable tab strategies; HTMX vs web component vs static | [UX_UI/tabs.md](UX_UI/tabs.md) |
| Standard buttons, icon set, semantic colours, table-row rules | [UX_UI/common_buttons.md](UX_UI/common_buttons.md) |
| Dual listbox: when, anatomy, session-staged commit | [UX_UI/dual_listbox.md](UX_UI/dual_listbox.md) |
| `<search-dropdown>` picker vs plain HTMX list filter | [UX_UI/searchbars.md](UX_UI/searchbars.md) |
| Pagination and other shared partials | [UX_UI/pagination.md](UX_UI/pagination.md) |
| Accessibility baseline | [UX_UI/accessibility.md](UX_UI/accessibility.md) |

---

## Reference directionality

This anchor references **only** files inside `UX_UI/`. Tier 2 files inside that folder may reference each other and Tier 3 examples within `UX_UI/Examples/` (concrete markup snippets, component sources), but never back upward. Backend concerns referenced by UX rules — `format=` query semantics, CSRF middleware, endpoint shapes — live under [Architecture.md](Architecture.md); a frontend task should not require reading the architecture anchor in full, only the specific cross-cutting line items embedded here.
