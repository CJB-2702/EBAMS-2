---
type: "UX Guide"
title: "Modals & dialogs"
description: "Modal and dialog components use the native HTML <dialog> element styled with Bulma cards."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Modals & dialogs

Modal and dialog components use the native HTML `<dialog>` element styled with Bulma cards. The `commandfor` and `command` attributes provide a declarative way to trigger and control dialogs without JavaScript event listeners.

## Overview

- **`<dialog>`** — native HTML element for modal behaviour (backdrop, focus trap, Escape to close).
- **Bulma `.card`** — provides the visual card styling and structure.
- **`.modal-styled`** (in `custom_css.css`) — the app's recommended modal treatment: centered sizing, square corners, and a red flush-corner close button. Add this class alongside `.card` on every new dialog.
- **`commandfor` & `command`** — declarative control of dialog state.

---

## When to use a modal — and when not to

A modal interrupts. That is its only real feature, and it is a cost. Reach for one when the interruption *is* the point.

**Use a modal for:**

| Case | Why a modal fits |
| :--- | :--- |
| **Destructive confirmation** — delete, release, cancel | The user must stop and answer before anything else happens. |
| **Read-only browsing of a large set** — "Browse all files", full-size image, log detail | Nothing is being composed; the user looks and dismisses. |
| **A single-field capture that ends immediately** — rename, add a comment | One field, one submit, no relationship to the rest of the page state. |

**Do not use a modal for assignment.** Attaching items from a pool to the record being edited — manufacturers to a part, tasks to a maintenance activity, users to an event, documents to an asset — belongs **in the page**, as a left-heavy assignment card pair or a dual listbox.

| Instead of | Use | Guide |
| :--- | :--- | :--- |
| "Add manufacturers" modal | Left-heavy assignment card pair (2/3 pool + 1/3 assigned) | [left_heavy_assignment_card_pair.md](left_heavy_assignment_card_pair.md) |
| "Manage members" modal | Dual listbox | [../components/dual_listbox.md](../components/dual_listbox.md) |
| "Pick one related record" modal | Search dropdown, inline | [../search/searchbars.md](../search/searchbars.md) |

Why this is a rule and not a preference:

- **The F5 rule.** A modal holding staged, uncommitted selections loses them on refresh. An in-page card backed by the session-draft pattern does not — see [multi_step_flows.md](multi_step_flows.md).
- **Assignment needs the surrounding context.** You choose manufacturers *because of* what the part is. A modal covers the very information the decision depends on.
- **Modals do not compose.** Two assignments in one creation flow means two modals opened in sequence, with no way to see both results at once. Two cards stacked on one scrolling page is just… the page.
- **Nested modals are not allowed.** Once assignment lives in a modal, anything it needs (create-a-new-manufacturer, search a sub-pool) has nowhere to go.

If a create or edit flow needs several assignments, that is the signal it is a **multi-card wizard**, not a form with modals. See [multi_step_flows.md](multi_step_flows.md).

---

## Basic structure

```html
<button class="button is-primary" commandfor="demo-dialog" command="show-modal">
  Open Dialog
</button>

<dialog id="demo-dialog" class="card modal-styled" style="padding: 0;">
  <header class="card-header">
    <p class="card-header-title">Dialog Title</p>
    <button class="delete is-large" aria-label="close"
            commandfor="demo-dialog" command="close"></button>
  </header>

  <div class="card-content">
    <div class="content">
      <!-- Dialog content here -->
    </div>
  </div>

  <footer class="card-footer custom-card-footer">
    <div class="card-footer-secondaries">
      <button class="button is-small is-light" commandfor="demo-dialog" command="close">Cancel</button>
    </div>
    <button class="button is-primary card-footer-primary" commandfor="demo-dialog" command="close">Save</button>
  </footer>
</dialog>
```

Reference implementation: the "Browse all files" dialog in [app/events/templates/events/fragments/direct_attachments_card.html](../../../app/events/templates/events/fragments/direct_attachments_card.html).

## `commandfor` and `command` attributes

| Attribute | Meaning |
| :--- | :--- |
| `commandfor` | Points to the `id` of the target `<dialog>` element. |
| `command="show-modal"` | Opens the dialog (`dialog.showModal()`). |
| `command="close"` | Closes the dialog (`dialog.close()`). |

## Dialog anatomy

| Region | Class | Role |
| :--- | :--- | :--- |
| Header | `.card-header` + `.card-header-title` | Title + close button (`.delete`, styled by `.modal-styled` as a red square flush with the top-right corner). |
| Content | `.card-content` + `.content` | The main body of the dialog. Divided from the header by `.card-header`'s project-wide `border-bottom` (see [../visual_language.md](../visual_language.md)), not Bulma's default box-shadow. |
| Footer | `.card-footer.custom-card-footer` | Action buttons; follows the same geometry as the canonical card footer (see [../form_style_guide.md](../form_style_guide.md)). |

## `.modal-styled` — the recommended pattern

Add `.modal-styled` alongside `.card` on every dialog. It provides:

- **Centered position** — `position: fixed; top/left: 50%; transform: translate(-50%, -50%)`. Bulma's `.card` sets `position: relative`, which clobbers the browser's built-in `dialog:modal` auto-centering (`position: fixed; margin: auto`) — `.modal-styled` restores centering explicitly.
- **Sizing** — `width: 80vw`, capped at `max-width: 800px`, `max-height: 80vh`.
- **Square corners** — `border-radius: 0 !important`, consistent with the rest of the app's sharp-corner rule.
- **Close button** — repositions `.delete` to `position: absolute; top: 0; right: 0`, flush with the dialog's corner, square (`border-radius: 0`) and colored `var(--bulma-danger)` (red) instead of Bulma's default translucent circle.
- **Correct closed state** — `.modal-styled { display: none; }` by default, with `.modal-styled[open] { display: flex; flex-direction: column; }` restoring layout only once the dialog is actually open.

### Pitfall: don't set `display` inline on the `<dialog>` tag

If a dialog's body needs internal flex/column layout (e.g. a scrolling content area), do **not** add `display: flex` to the dialog's own inline `style=""`. An inline style outranks the browser's default `dialog:not([open]) { display: none; }` rule, so the modal would render open on every page load instead of staying a popup. `.modal-styled[open]` already supplies `display: flex; flex-direction: column;` — let it handle this instead of inlining it.

## Styling notes

Set `style="padding: 0;"` on the dialog element to remove default padding and let the card handle all spacing. The card-footer geometry classes (`custom-card-footer`, `card-footer-secondaries`, `card-footer-primary`) work identically inside a dialog.

## Browser support and accessibility

- The native `<dialog>` element is supported in all modern browsers. `commandfor`/`command` (the Invoker Commands API) are natively supported in current Chrome/Edge — no JS is used or needed to wire them up. Do not add a `document.addEventListener('click', ...)` polyfill for this; it double-handles clicks the browser already processes natively and causes hover/focus state glitches (e.g. a stuck `:focus` color on the close button).
- Close button has `aria-label="close"` for screen readers.
- `<dialog>` provides built-in focus management and backdrop.
- Escape key closes the dialog automatically.
- Modal behaviour traps focus within the dialog.
