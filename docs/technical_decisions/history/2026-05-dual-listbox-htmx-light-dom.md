# Dual listbox: HTMX-first light-DOM components with toast alerts

- **Date:** 2026-05-18
- **Context / feature:** Many-to-many editing surfaces across the administration portal (roles, groups, permissions, organizations, divisions, domains).

## Decision

Dual-listbox UI is rebuilt as **light-DOM** custom elements (`<dual-list-box>`, `<list-box>`) driven by HTMX-first move buttons and a fixed-position `<toast-alert>` for feedback. Move buttons POST to a per-relationship endpoint, which returns a `<toast-alert>` plus the refreshed fragment for `outerHTML` swap. No page reload, no Django `messages.html` rendering.

## Rationale

The previous architecture submitted a form, redirected, and re-rendered the full page with Django messages. This:

- Lost scroll position and any in-progress page state.
- Made it hard to target specific listboxes from HTMX elsewhere on the page (shadow DOM boundaries blocked queries).
- Required per-page CSRF/messages plumbing.

The new approach keeps the rebuild local: just the dual-listbox region is swapped, the toast escapes positioned ancestors by mounting on `document.body`, and CSRF is handled by the project-wide `htmx:configRequest` listener. Components are light-DOM so HTMX `hx-target="#…"` selectors work without `global #…` workarounds.

## What changed

- New components at `app/static/web_components/dual_listbox.js` and `list_box.js` (and `toast_alert.js`).
- Per-relationship endpoints follow the naming `<entity>_move_<relationship>` and accept `item_ids: int[]` and `direction: "add" | "remove"`.
- Each fragment template is named `_<relationship>_dlb_only.html`, has no outer wrapper, and is targeted by `outerHTML swap:1s`.
- The `users/edit.html` page (roles, groups, permissions, organizations, divisions, domains) is the canonical example and has been migrated.

## Implications

- All future dual-listbox surfaces use this pattern.
- Several detail pages still use the old form-submission pattern and need migration — tracked in [../tech_debt/dual_listbox_migration_plan.md](../tech_debt/dual_listbox_migration_plan.md).

## Related

- [../../UX_UI/dual_listbox.md](../../UX_UI/dual_listbox.md) — the canonical component guide.
- [../../UX_UI/Examples/dual_listbox_markup.md](../../UX_UI/Examples/dual_listbox_markup.md) — verbatim fragment and endpoint markup.
