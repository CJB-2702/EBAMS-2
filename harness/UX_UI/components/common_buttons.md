---
type: "UX Guide"
title: "Common buttons & iconography"
description: "The complete table of standard action buttons used across the app, paired with their **icon**, **semantic color**, and **Bulma class set**."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Common buttons & iconography

The complete table of standard action buttons used across the app, paired with their **icon**, **semantic color**, and **Bulma class set**. A "Save" button looks the same on every page, in every form, in every modal.

Icons come from **Material Icons** (vendored in `app.css`). Icons are **never decorative-only on a button** — every icon has the action's text label beside it, except in the [Icon-only buttons](#icon-only-buttons) cases listed below.

Markup pattern for every icon:

```html
<span class="icon"><span class="material-icons" aria-hidden="true">icon_name</span></span>
```

For canonical markup snippets see [../Examples/button_markup.md](../Examples/button_markup.md). For the full action → icon → color → Bulma-class table see [../Examples/button_markup.md#master-button-table](../Examples/button_markup.md#master-button-table).

---

## Master button table

Every standard action (Save, Create, Edit, Cancel, Delete, Refresh, Search, Filter, Export, Approve, Reject, etc.) has one fixed icon, semantic color, and Bulma class combination — never improvise a new pairing for an existing action. Full table: [../Examples/button_markup.md#master-button-table](../Examples/button_markup.md#master-button-table).

---

## Semantic colors — what each color *means*

| Color | Bulma class | Meaning |
| :--- | :--- | :--- |
| **Primary** (blue) | `is-primary` | The expected, intended action. **At most one** primary button per form/card. |
| **Info** (cyan) | `is-info` | Read-mostly navigation (Edit, View, Open). `is-light` by default. |
| **Link** (royal blue) | `is-link` | Side-effect-free actions (Refresh, Export, Import preview). |
| **Success** (green) | `is-success` | Affirmative state transitions (Approve, Activate, Restore). |
| **Warning** (yellow) | `is-warning` | Cautionary actions that are reversible (Reject, Archive, Deactivate). |
| **Danger** (red/pink) | `is-danger` | Destructive actions (Delete, Remove). **Always paired with `is-light`** in inline footers; solid `is-danger` only on dedicated confirmation pages. |
| **Light grey** | `is-light` (no color modifier) | Neutral / secondary (Cancel, Reset, Filter, Sort). |

The **light variant** (`is-light` in addition to a color class) softens the button so it does not compete with a true primary.

---

## Sizes

| Size | Class | When to use |
| :--- | :--- | :--- |
| Default | *(none)* | Primary actions, top-of-page navigation, form submits |
| Small | `is-small` | Secondary actions in card footers (Cancel, Reset, Delete) |
| Medium | `is-medium` | Hero CTAs (rare; only on the dashboard or empty-state cards) |
| Large | `is-large` | Reserved for empty-state primary CTAs ("Create your first asset") |

A footer row should never mix default-size and `is-small` *primary* buttons — pick one tier and stick to it.

---

## Icon-only buttons

Icon-only is acceptable for these actions **only**:

- **Close** (modal/banner dismiss) — `aria-label="close"` required.
- **Copy** (copy ID/slug to clipboard) — `aria-label="copy <value>"`.
- **More / Menu** (overflow dropdown) — `aria-label="more actions"`.
- **Search** trigger inside `<search-dropdown>`.
- **Sort direction toggle** in a column header.
- **Any button inside a `<table>` row** — see below.

Anywhere else, an icon must travel with a text label.

---

## Buttons in tables

> **Rule:** buttons inside a `<table>` row are rendered as **icon-only**. The action's text label moves to the `title` attribute (native hover tooltip) and `aria-label` (screen-reader equivalent).

### Why

Table rows are visually dense. Repeating "Edit / Delete / Restore" on every row creates noise and stretches the actions column out of proportion to the data columns.

### Rules

- **Always include both `title` and `aria-label`.** Both should contain the same text and **identify the specific row** ("Delete asset-beta", not just "Delete").
- **Sizes:** always `is-small`.
- **Color semantics are unchanged.** Edit stays `is-info is-light`, Delete stays `is-danger is-light`, Approve stays `is-success`, etc. Only the text label disappears.
- **Header column:** title the actions column "Actions" (or leave blank if obvious). Right-align with `has-text-right`.
- **Max 4 actions per row.** If you have more, collapse the rare ones behind a `more_vert` overflow button.

### When NOT to apply this rule

Outside tables, icon + text remains the default. The rule is **inside `<table>` rows only** — not inside a `.card` listing rows-as-boxes, not inside `.media`, not inside a `<dl>`.

---

## Common mistakes

- **Multiple primary buttons** on the same card. Pick one.
- **Solid `is-danger`** Delete in a card footer. Use `is-danger is-light`.
- **Icon without label** outside the [icon-only](#icon-only-buttons) list.
- **Different icons for the same action** across pages. Stick to this table.
- **Color drift:** using `is-warning` for Delete because "yellow looks less aggressive". Delete is `is-danger is-light`. Always.
- **Custom CSS to recolor a button.** If a new semantic is needed, add it to this table first.
