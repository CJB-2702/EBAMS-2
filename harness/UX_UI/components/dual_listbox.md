---
type: "UX Guide"
title: "Dual listbox component guide"
description: "A **dual listbox** presents two side-by-side lists — *Available* and *Selected* — with controls to move items between them."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Dual listbox component guide

A **dual listbox** presents two side-by-side lists — *Available* and *Selected* — with controls to move items between them. It is a deliberate, high-friction control: every move is explicit and visible. Use it when a multi-select must be **auditable**, **bulk-editable**, and **comprehensible at a glance**.

For verbatim markup and component fragments see [../Examples/dual_listbox_markup.md](../Examples/dual_listbox_markup.md).

---

## When to use

Pick **dual listbox** over a standard `<select multiple>` or tag-style multi-select when **all** of these hold:

| Condition | Why it matters |
| :--- | :--- |
| Editing a **many-to-many** relationship | Both sides of the relation should be visible at once. |
| The set of *selected* items can grow into the dozens | A flat tag chip strip becomes unscannable past ~10 entries. |
| The user needs to **review what is currently selected** before submitting | Selected list acts as a confirmation surface. |
| The **available** pool benefits from search / filter | Pairs naturally with a search bar over the *Available* side. |
| The change is **irreversible-ish** (saved on submit, not on click) | Dual listbox stages changes; nothing commits until POST. |

Pick a **standard multi-select** (or a single search dropdown) when:

- The expected selection is **0–3 items** (use a single `<search-dropdown>`; see [searchbars.md](searchbars.md)).
- The relation is **conceptually one-to-many on the form**.
- Selection is **immediate / autosaved** (use a chip add-remove pattern instead).
- The available pool is **fixed and small** (under ~8 options) — use checkboxes.

If two dual listboxes are needed on the same page, step back: that is usually a sign the page should be split into two edit screens, or the relation should be inverted.

**Never put an assignment control in a modal.** Whichever control you pick — dual listbox, left-heavy assignment card pair, or search dropdown — it lives in the page. See [modals.md](modals.md#when-to-use-a-modal--and-when-not-to) for the rule and its rationale, and [multi_step_flows.md](multi_step_flows.md) for how assignment cards stack inside a creation wizard.

---

## Anatomy

- **Two equal columns** in a Bulma `.columns` row, each a `.box` or `.card`.
- Each column has a **title with a count** (e.g. *Selected (12)*) — the count is always visible.
- Each column has its **own search bar** scoped to that column's contents.
- Movement controls live **between** columns: a vertically stacked pair of buttons. Prefer clickable rows with a chevron icon — fewer mouse trips.
- The form's **primary submit lives in the parent card footer**, not inside either listbox column. See [../form_style_guide.md](../form_style_guide.md).

---

## Implementation strategy

Two server-rendered lists driven by HTMX-first light-DOM web components (`<dual-list-box>`, `<list-box>`, `<toast-alert>`). Each move button is an HTMX POST that:

1. Calls the move endpoint (`<entity>_move_<relationship>`) with `direction: 'add' | 'remove'` and an array of `item_ids` extracted from the component API (`listBox('id').selected()`).
2. The endpoint performs the write via the control layer and returns **two** elements: a `<toast-alert>` followed by the refreshed `<dual-list-box>` fragment, replacing the entire dual listbox via `outerHTML swap:1s`.
3. The toast auto-dismisses after a configurable delay; the fragment shows the updated *Available* and *Selected* states with correct counts.

The toast component auto-mounts to `document.body` so it escapes positioned ancestors. CSRF is handled by the project's `htmx:configRequest` listener (see [../../Architecture/patterns/htmx_patterns.md](../../Architecture/patterns/htmx_patterns.md)).

For the previous form-submission + page-reload model and the rationale for migrating, see [../../../docs/administration/project_history/2026-05-dual-listbox-htmx-light-dom.md](../../../docs/administration/project_history/2026-05-dual-listbox-htmx-light-dom.md) and [../../technical_decisions/tech_debt/resolved/dual_listbox_migration_plan.md](../../technical_decisions/tech_debt/resolved/dual_listbox_migration_plan.md).

---

## REST-shaped API on the same URL

The same resource also exposes a JSON contract on the same URL for non-HTMX consumers (GET/PUT/PATCH on the collection endpoint). The HTMX endpoints are **not** a parallel API; they share the same view and dispatch on `format=`. Literal request/response shapes: [../Examples/dual_listbox_markup.md](../Examples/dual_listbox_markup.md).

---

## Accessibility

- Each list is a `<ul>` with `role="listbox"` and `aria-multiselectable="true"`.
- Each row's button uses the item's name as its accessible name.
- Column headers are real `<h2>` / `<h3>` elements so screen readers announce structure.
- Keyboard: Tab enters the *Available* search, Tab again moves to the first row; Enter moves a row to the other side; focused index is preserved after the swap.

---

## Common mistakes

- **One column doing all the work.** If *Selected* is just a comma-joined chip strip under *Available*, that is a tag input, not a dual listbox.
- **Auto-saving on every move.** Defeats the "review before commit" property; if autosave is wanted, use a chip pattern.
- **No count in the header.** Users cannot tell at a glance whether a change took effect.
- **Search bar that searches both sides.** Each column owns its own search state.
- **Putting Save inside one of the two columns.** Submit lives in the parent card footer.
