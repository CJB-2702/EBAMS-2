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
- **`.modal-styled`** (in `custom_css.css`) — the app's recommended modal treatment: centered sizing, square corners, a `.pc-header`-style divider, and a red flush-corner close button. Add this class alongside `.card` on every new dialog.
- **`commandfor` & `command`** — declarative control of dialog state.

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
| Content | `.card-content` + `.content` | The main body of the dialog. Divided from the header by a solid `border-bottom` (same treatment as `.pc-header`), not Bulma's default box-shadow. |
| Footer | `.card-footer.custom-card-footer` | Action buttons; follows the same geometry as the canonical card footer (see [../form_style_guide.md](../form_style_guide.md)). |

## `.modal-styled` — the recommended pattern

Add `.modal-styled` alongside `.card` on every dialog. It provides:

- **Centered position** — `position: fixed; top/left: 50%; transform: translate(-50%, -50%)`. Bulma's `.card` sets `position: relative`, which clobbers the browser's built-in `dialog:modal` auto-centering (`position: fixed; margin: auto`) — `.modal-styled` restores centering explicitly.
- **Sizing** — `width: 80vw`, capped at `max-width: 800px`, `max-height: 80vh`.
- **Square corners** — `border-radius: 0 !important`, consistent with the rest of the app's sharp-corner rule.
- **Header/body divider** — replaces the default card-header box-shadow with a `1px solid var(--bulma-border-weak)` border-bottom, matching `.pc-header`.
- **Close button** — repositions `.delete` to `position: absolute; top: 0; right: 0`, flush with the dialog's corner, square (`border-radius: 0`) and colored `var(--bulma-danger)` (red) instead of Bulma's default translucent circle.
- **Correct closed state** — `.modal-styled { display: none; }` by default, with `.modal-styled[open] { display: flex; flex-direction: column; }` restoring layout only once the dialog is actually open.

### Pitfall: don't set `display` inline on the `<dialog>` tag

If a dialog's body needs internal flex/column layout (e.g. a scrolling content area), do **not** add `display: flex` to the dialog's own inline `style=""`. An inline style outranks the browser's default `dialog:not([open]) { display: none; }` rule, so the modal would render open on every page load instead of staying a popup. `.modal-styled[open]` already supplies `display: flex; flex-direction: column;` — let it handle this instead of inlining it.

## Styling notes

Set `style="padding: 0;"` on the dialog element to remove default padding and let the card handle all spacing. The card-footer geometry classes (`custom-card-footer`, `card-footer-secondaries`, `card-footer-primary`) work identically inside a dialog.

## Browser support and accessibility

- The native `<dialog>` element is supported in all modern browsers. The `commandfor` and `command` attributes require the browser's command API; a small polyfill or JS implementation may be needed for older targets.
- Close button has `aria-label="close"` for screen readers.
- `<dialog>` provides built-in focus management and backdrop.
- Escape key closes the dialog automatically.
- Modal behaviour traps focus within the dialog.
