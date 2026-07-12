# Modals & dialogs

Modal and dialog components use the native HTML `<dialog>` element styled with Bulma cards. The `commandfor` and `command` attributes provide a declarative way to trigger and control dialogs without JavaScript event listeners.

## Overview

- **`<dialog>`** — native HTML element for modal behaviour (backdrop, focus trap, Escape to close).
- **Bulma `.card`** — provides the visual card styling and structure.
- **`commandfor` & `command`** — declarative control of dialog state.

## Basic structure

```html
<button class="button is-primary" commandfor="demo-dialog" command="show-modal">
  Open Dialog
</button>

<dialog id="demo-dialog" class="card" style="padding: 0;">
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

## `commandfor` and `command` attributes

| Attribute | Meaning |
| :--- | :--- |
| `commandfor` | Points to the `id` of the target `<dialog>` element. |
| `command="show-modal"` | Opens the dialog (`dialog.showModal()`). |
| `command="close"` | Closes the dialog (`dialog.close()`). |

## Dialog anatomy

| Region | Class | Role |
| :--- | :--- | :--- |
| Header | `.card-header` + `.card-header-title` | Title + close button (`.delete` in the top-right corner). |
| Content | `.card-content` + `.content` | The main body of the dialog. |
| Footer | `.card-footer.custom-card-footer` | Action buttons; follows the same geometry as the canonical card footer (see [form_style_guide.md](form_style_guide.md)). |

## Styling notes

Set `style="padding: 0;"` on the dialog element to remove default padding and let the card handle all spacing. The card-footer geometry classes (`custom-card-footer`, `card-footer-secondaries`, `card-footer-primary`) work identically inside a dialog.

## Browser support and accessibility

- The native `<dialog>` element is supported in all modern browsers. The `commandfor` and `command` attributes require the browser's command API; a small polyfill or JS implementation may be needed for older targets.
- Close button has `aria-label="close"` for screen readers.
- `<dialog>` provides built-in focus management and backdrop.
- Escape key closes the dialog automatically.
- Modal behaviour traps focus within the dialog.
